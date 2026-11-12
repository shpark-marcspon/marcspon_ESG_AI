"""inventory 의 쓰임새. 얇다: 표를 고르고, 순수 계산(engines/)을 부르고, 나갈 dict 로 바꾼다. 저장하지 않는다."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from esgapi.core.exceptions import ApplicationError
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError
from esgapi.core.llm.setup import llm_client
from esgapi.core.llm.types import Tags
from esgapi.inventory.data_loader import default_tables
from esgapi.inventory.engines.scope3.llm_first_1.catalog import ListFactorCatalog, Rejected
from esgapi.inventory.engines.scope3.llm_first_1.lexical_v1 import ShortlistQuery
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import (
    Classification,
    LlmFailure,
    LlmUsage,
    classify_request,
)
from esgapi.inventory.engines.scope3.llm_first_1.normalize import group_rows
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import (
    DEFAULT_SHORTLIST_SIZE,
    classify_group,
    first_duplicate_row_id,
    physical_candidates,
)
from esgapi.inventory.engines.scope3.llm_first_1.ranking import CandidateEvidence
from esgapi.inventory.engines.scope3.llm_first_1.serialize import (
    candidate_to_dict,
    classification_to_dict,
    failure_to_dict,
    usage_to_dict,
)
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import (
    DEFAULT_SHORTLIST_METHOD,
    ShortlistMethod,
    lexical_shortlister,
)
from esgapi.inventory.engines.scope3.llm_first_1.types import (
    LICENSE_STATUSES,
    CandidateBasis,
    CandidateQuery,
    Factor,
    FallbackReason,
    InputRow,
    LicenseStatus,
    SupportedCategory,
    TransportInfo,
)
from esgapi.inventory.engines.scope12.engine_1.aggregate import GroupKey, aggregate
from esgapi.inventory.engines.scope12.engine_1.calc import calculate_raw
from esgapi.inventory.engines.scope12.engine_1.serialize import output_to_dict
from esgapi.inventory.engines.scope12.engine_1.tables import TableProblem, TablesInvalid, validate_tables
from esgapi.inventory.engines.scope12.engine_1.types import CalcOptions

# 한 번에 계산하는 행의 상한. 넘으면 경로(service/apis/inventory.py)가 413 으로 답한다.
MAX_ROWS: Final = 1000


@dataclass(frozen=True, slots=True)
class CalcDone:
    """계산이 끝났다. 실패한 행이 있어도 여기로 온다(행마다 status 로 드러난다)."""

    output: dict[str, object]


@dataclass(frozen=True, slots=True)
class TablesRejected:
    """요청이 실어 온 기준정보 표가 검사에 걸렸다. 그 표로는 한 행도 계산하지 않는다."""

    problems: tuple[TableProblem, ...]


def calc_rows(
    *,
    rows: Sequence[Mapping[str, object]],
    tables: Mapping[str, object] | None,
    gwp_set_id: str,
    group_by: Sequence[GroupKey],
) -> CalcDone | TablesRejected:
    """활동 데이터 행을 계산하고 집계한다. tables 가 None 이면 패키지에 실린 표를 쓴다."""
    if tables is None:
        reference = default_tables()
    else:
        validated = validate_tables(dict(tables))
        if isinstance(validated, TablesInvalid):
            return TablesRejected(validated.problems)
        reference = validated.tables
    results = calculate_raw([dict(row) for row in rows], reference, CalcOptions(gwp_set_id=gwp_set_id))
    return CalcDone(output_to_dict(gwp_set_id=gwp_set_id, rows=results, aggregation=aggregate(results, group_by)))


# ── Scope 3: 후보 추리기와 분류 (저장하지 않는다) ─────────────────────

# 분류 호출의 경로. ★ 이 한 자리에만 있고 요청으로 받지 않는다. 모의 공급사의 경로다:
# 떠 있는 서버의 클라이언트에는 이 경로가 없어 분류 경로는 503 `llm_not_configured` 로 답한다(실호출의 길이 없다).
# 실제 경로를 여는 것은 실측 승인·상한·요청 밖 호출이 갖춰진 뒤의 일이다.
SCOPE3_ROUTE: Final = "mock"
# 그 경로의 주 모델이 이 공급사가 아니면 부르지 않는다(설정 파일이 `mock` 이라는 이름을 실제 모델에 걸어 두어도).
SCOPE3_PROVIDER: Final = "mock"
# 이용 조건의 기본. disputed(KEITI)는 요청이 명시해야만 후보가 된다(reference 의 기본과 같다).
SCOPE3_DEFAULT_LICENSES: Final[frozenset[LicenseStatus]] = frozenset({"ok", "unverified"})
# 한 번에 분류하는 묶음의 상한. 넘으면 경로가 413 으로 답한다. 요청 안에서 동기로 부르므로 둔 어림이다
# (gunicorn 의 30초와 묶인다. 실측한 값이 아니다).
SCOPE3_MAX_GROUPS: Final = 20
# 한 번에 분류하는 행의 상한. 넘으면 경로가 묶기 전에 413 으로 답한다. Scope 1·2 계산의 상한(MAX_ROWS)과 같은 값이고
# 어림이다(실측한 값이 아니다).
SCOPE3_MAX_ROWS: Final = MAX_ROWS
# 응답에 싣는 「빠진 줄」의 수. 총수는 따로 싣는다.
SCOPE3_SHOWN_REJECTED: Final = 20
SCOPE3_MODULE: Final = "inventory"
# 추린 목록의 길이의 기본. esg-lab ts/scope3/src/domain/pipeline.ts:24 의 값이다(순수 층의 DEFAULT_SHORTLIST_SIZE).
SCOPE3_DEFAULT_SIZE: Final = DEFAULT_SHORTLIST_SIZE


@dataclass(frozen=True, slots=True)
class Scope3Rejects:
    """후보 자격은 갖췄는데 `value_raw` 가 엄격 십진이 아니라 빠진 줄(앞의 몇 건과 총수). 조용히 빼지 않는다."""

    shown: tuple[Rejected, ...]
    total: int


@dataclass(frozen=True, slots=True)
class Scope3Shortlisted:
    """`fallback_reason` 은 기반을 고르지 않은 요청이 지출 기반으로 넘어갔을 때만 있다."""

    basis: CandidateBasis
    fallback_reason: FallbackReason | None
    method: ShortlistMethod
    description: str
    total: int
    lexical_matches: int
    factors: tuple[Factor, ...]
    evidence: tuple[CandidateEvidence, ...]
    rejects: Scope3Rejects


@dataclass(frozen=True, slots=True)
class Scope3NoCandidates:
    """조건에 맞는 후보가 없다(빈 목록으로 답하지 않는다). `physical` 은 활동·거리 기반 후보가 없던 까닭이다
    (지출 기반만 물은 요청은 그쪽을 보지 않았으므로 None)."""

    physical: FallbackReason | None
    rejects: Scope3Rejects


def scope3_shortlist(
    *,
    row: InputRow,
    category: SupportedCategory,
    keywords: Sequence[str],
    basis: CandidateBasis | None,
    method: ShortlistMethod,
    bigrams: bool,
    size: int,
    catalog: ListFactorCatalog,
) -> Scope3Shortlisted | Scope3NoCandidates:
    """한 품목의 후보를 추린다. 생성 모델을 부르지 않는다.

    `basis` 를 주지 않으면 파이프라인과 같은 차례다: 단위가 맞는 활동·거리 기반 후보가 있으면 그것,
    없으면 지출 기반(까닭을 같이 싣는다).
    """
    rejects = Scope3Rejects(catalog.rejected[:SCOPE3_SHOWN_REJECTED], len(catalog.rejected))

    used: CandidateBasis
    candidates: list[Factor]
    reason: FallbackReason | None = None
    if basis == "spend":
        used, candidates = "spend", catalog.candidates(CandidateQuery(category, "spend"))
    else:
        physical = physical_candidates(catalog, row, category)
        if not isinstance(physical, str):
            used, candidates = "physical", physical
        else:
            reason = physical
            if basis == "physical":
                return Scope3NoCandidates(reason, rejects)
            used, candidates = "spend", catalog.candidates(CandidateQuery(category, "spend"))
    if not candidates:
        return Scope3NoCandidates(reason, rejects)

    texts = (row.item_name, row.transport.mode) if row.transport is not None else (row.item_name,)
    shortlister = lexical_shortlister(method, bigrams=bigrams)
    outcome = shortlister.shortlist(candidates, ShortlistQuery(texts, tuple(keywords)), size)
    return Scope3Shortlisted(
        basis=used,
        fallback_reason=reason,
        method=outcome.method,
        description=shortlister.description,
        total=outcome.total,
        lexical_matches=outcome.lexical_matches,
        factors=outcome.factors,
        evidence=outcome.evidence,
        rejects=rejects,
    )


@dataclass(frozen=True, slots=True)
class Scope3GroupClassified:
    key: str
    row_ids: tuple[str, ...]
    classification: Classification


@dataclass(frozen=True, slots=True)
class Scope3GroupFailed:
    """그 묶음의 분류 호출이 성공이 아니었다(스키마 불일치, 거부, 잘림, 공급사 오류, 시간 초과, 상한)."""

    key: str
    row_ids: tuple[str, ...]
    llm: LlmFailure


@dataclass(frozen=True, slots=True)
class Scope3Classified:
    groups: tuple[Scope3GroupClassified | Scope3GroupFailed, ...]
    usage: LlmUsage


@dataclass(frozen=True, slots=True)
class Scope3TooManyGroups:
    count: int


@dataclass(frozen=True, slots=True)
class Scope3DuplicateRowId:
    row_id: str


def scope3_gateway() -> LlmClient:
    """분류 호출이 나가는 클라이언트. ★ 이음매다: 테스트는 이 자리를 모의 클라이언트로 바꾼다."""
    return llm_client()


def _llm_not_configured() -> ApplicationError:
    # 문장에는 경로 이름만 싣는다. 설정의 속사정(파일 경로, 키의 유무, 모델 이름)은 싣지 않는다.
    message = f"생성 모델 경로 {SCOPE3_ROUTE} 가 이 서버에 준비되어 있지 않다"
    return ApplicationError("unavailable", "llm_not_configured", message)


def _require_mock_route(client: LlmClient, row: InputRow, tags: Tags) -> None:
    """부르기 전에 경로를 본다(공급사를 부르지 않는 조립만 한다). 모의 공급사의 경로가 아니면 503 으로 끝낸다.

    걸리는 것: 경로가 설정에 없다(떠 있는 서버의 기본), 그 경로의 주 모델이 모의 공급사가 아니다, 대체 모델이 걸려
    있다(대체 모델의 공급사를 여기서 알 수 없어 통째로 거절한다), 그 공급사의 키가 없다.
    무효 조건: 조립 단계의 다른 설정 오류(출력 상한이 모델 상한을 넘음 등)도 `LlmConfigError` 라 같은 code 로 나간다.
    """
    try:
        report = client.dry_run(classify_request(row, SCOPE3_ROUTE, tags))
    except (LlmConfigError, LiveSetupError):
        raise _llm_not_configured() from None
    if report.provider != SCOPE3_PROVIDER or report.fallback_models:
        raise _llm_not_configured()


def scope3_classify(
    *, rows: Sequence[InputRow], company_id: int
) -> Scope3Classified | Scope3TooManyGroups | Scope3DuplicateRowId:
    """행을 묶음 키로 묶어 묶음마다 한 번(묶음의 첫 행으로) 범주를 묻는다. DB 를 읽지 않고 저장하지 않는다.

    숫자(수량·금액·무게·거리)는 프롬프트에 가지 않는다. 호출이 실패한 묶음은 갈래로 남는다(빈 결과로 바꾸지 않는다).
    """
    duplicate = first_duplicate_row_id(rows)
    if duplicate is not None:
        return Scope3DuplicateRowId(duplicate)
    groups = group_rows(rows)
    if len(groups) > SCOPE3_MAX_GROUPS:
        return Scope3TooManyGroups(len(groups))

    usage = LlmUsage()
    done: list[Scope3GroupClassified | Scope3GroupFailed] = []
    if not groups:
        return Scope3Classified((), usage)
    client = scope3_gateway()
    tags = Tags(tenant=str(company_id), module=SCOPE3_MODULE)  # 꼬리표의 칸 이름 tenant 는 그대로(C1). 값은 회사 id
    _require_mock_route(client, groups[0].rows[0], tags)
    for group in groups:
        row_ids = tuple(row.row_id for row in group.rows)
        classification = classify_group(client, group, SCOPE3_ROUTE, tags, usage)
        if isinstance(classification, LlmFailure):
            done.append(Scope3GroupFailed(group.key, row_ids, classification))
        else:
            done.append(Scope3GroupClassified(group.key, row_ids, classification))
    return Scope3Classified(tuple(done), usage)


# ── Scope 3: 요청의 dict ↔ 순수 층 ───────────────────────────────────


def _text(data: Mapping[str, object], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None


def scope3_row(data: Mapping[str, object]) -> InputRow:
    """요청의 행(주지 않은 선택 칸은 키가 없다) → 순수 층의 행. 추리기만 하는 요청에는 rowId·수량·금액이 없다."""
    moved = data.get("transport")
    transport: TransportInfo | None = None
    if isinstance(moved, Mapping):
        info = cast("Mapping[str, object]", moved)
        transport = TransportInfo(
            origin=_text(info, "origin") or "",
            destination=_text(info, "destination") or "",
            mode=_text(info, "mode") or "",
            weight_kg=_text(info, "weightKg"),
            distance_km=_text(info, "distanceKm"),
        )
    return InputRow(
        row_id=_text(data, "rowId") or "",
        item_name=_text(data, "itemName") or "",
        quantity=_text(data, "quantity"),
        unit=_text(data, "unit"),
        amount=_text(data, "amount"),
        currency=_text(data, "currency"),
        date=_text(data, "date") or "",
        org_unit=_text(data, "orgUnit") or "",
        transport=transport,
    )


def scope3_licenses(text: str | None) -> frozenset[LicenseStatus]:
    """`ok,unverified` 꼴의 글자 → 이용 조건 상태의 집합. 주지 않으면 기본. 모르는 이름은 조용히 빼지 않고 거절한다."""
    if text is None:
        return SCOPE3_DEFAULT_LICENSES
    names = [part.strip() for part in text.split(",")]
    found: frozenset[LicenseStatus] = frozenset(status for status in LICENSE_STATUSES if status in names)
    if len(found) != len(names):
        expected = ", ".join(LICENSE_STATUSES)
        raise ApplicationError("invalid_input", "invalid_license", f"license 는 {expected} 를 쉼표로 이은 것이다")
    return found


def _rejects_out(rejects: Scope3Rejects) -> dict[str, object]:
    return {
        "rejected": [{"id": entry.id, "reason": entry.reason} for entry in rejects.shown],
        "rejectedTotal": rejects.total,
    }


def scope3_shortlist_output(
    *,
    row: Mapping[str, object],
    category: SupportedCategory,
    keywords: Sequence[str] | None,
    basis: CandidateBasis | None,
    method: ShortlistMethod | None,
    bigrams: bool | None,
    size: int | None,
    catalog: ListFactorCatalog,
) -> dict[str, object]:
    """경로가 부른다: 주지 않은 칸에 기본을 채워 추리고, 나갈 dict 로 바꾼다."""
    result = scope3_shortlist(
        row=scope3_row(row),
        category=category,
        keywords=keywords or (),
        basis=basis,
        method=method or DEFAULT_SHORTLIST_METHOD,
        bigrams=True if bigrams is None else bigrams,
        size=SCOPE3_DEFAULT_SIZE if size is None else size,
        catalog=catalog,
    )
    if isinstance(result, Scope3NoCandidates):
        return {"status": "no_candidates", "physical": result.physical, "catalog": _rejects_out(result.rejects)}
    return {
        "status": "shortlisted",
        "basis": result.basis,
        "fallbackReason": result.fallback_reason,
        "method": result.method,
        "description": result.description,
        "total": result.total,
        "shown": len(result.factors),
        "lexicalMatches": result.lexical_matches,
        "candidates": [candidate_to_dict(factor) for factor in result.factors],
        "evidence": [entry.to_json() for entry in result.evidence],
        "catalog": _rejects_out(result.rejects),
    }


@dataclass(frozen=True, slots=True)
class Scope3ClassifyDone:
    output: dict[str, object]


def scope3_classify_output(
    *, rows: Sequence[Mapping[str, object]], company_id: int
) -> Scope3ClassifyDone | Scope3TooManyGroups | Scope3DuplicateRowId:
    """경로가 부른다: 분류하고 나갈 dict 로 바꾼다. `synthetic` 은 늘 참이다(경로가 모의 공급사뿐이다)."""
    result = scope3_classify(rows=[scope3_row(row) for row in rows], company_id=company_id)
    if not isinstance(result, Scope3Classified):
        return result
    groups: list[dict[str, object]] = []
    for group in result.groups:
        entry: dict[str, object] = {"key": group.key, "rowIds": list(group.row_ids)}
        if isinstance(group, Scope3GroupClassified):
            entry |= {"status": "classified", "classification": classification_to_dict(group.classification)}
        else:
            entry |= {"status": "classification_failed", "llm": failure_to_dict(group.llm)}
        groups.append(entry)
    return Scope3ClassifyDone(
        {"synthetic": True, "route": SCOPE3_ROUTE, "groups": groups, "usage": usage_to_dict(result.usage)}
    )
