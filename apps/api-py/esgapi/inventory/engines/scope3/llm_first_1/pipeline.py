"""묶음의 판단과 실행. esg-lab `ts/scope3/src/domain/pipeline.ts` 를 옮긴 것이다.

순서는 고정이다: 확정 매핑 기억 → 범주 분류 → 후보 조회 → 추리기 → top-3 추천 → (첫째 추천으로) 계산.
기억에 있으면 생성 모델을 부르지 않는다. 활동(물량·거리) 기반 후보를 먼저 보고, 없거나 단위가 맞지 않거나
모델이 쓸 만한 것이 없다고 하면 지출 기반으로 넘어간다. 추천하지 못한 사정은 종류별 갈래로 남긴다.

TS 와 다르게 한 것:
  - 동기다(TS 의 async 를 옮기지 않았다. `core.llm` 이 동기다).
  - `GroupDecision` 은 TS 의 열 갈래에서 `shortlist_failed`(임베딩에서만 난다)를 뺀 아홉이다.
  - `rowId` 가 겹치거나 보정 계수가 틀렸을 때 TS 는 예외를 던졌다. 여기서는 `PipelineRejected` 갈래로 돌려준다.
  - 추리기의 임베딩 비용(`embeddingCostUsd`)은 없다.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from esgapi.core.llm.types import Success, Tags
from esgapi.inventory.engines.scope3.llm_first_1.calc import (
    AdjustmentProblem,
    CalcResult,
    CurrencyAdjustment,
    NotCalculated,
    calculate_row,
    check_adjustments,
)
from esgapi.inventory.engines.scope3.llm_first_1.lexical_v1 import ShortlistQuery
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import (
    CLASSIFY_PROMPT,
    RECOMMEND_PROMPT,
    Classification,
    LlmFailure,
    LlmUsage,
    classify_request,
    describe_failure,
    recommend_request,
    record_usage,
)
from esgapi.inventory.engines.scope3.llm_first_1.memory import MappingMemory, MemoryEntry
from esgapi.inventory.engines.scope3.llm_first_1.normalize import RowGroup, group_rows
from esgapi.inventory.engines.scope3.llm_first_1.ports import FactorCatalog, LlmGateway
from esgapi.inventory.engines.scope3.llm_first_1.ranking import CandidateEvidence
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import Shortlister, ShortlistMethod, default_shortlister
from esgapi.inventory.engines.scope3.llm_first_1.types import (
    Basis,
    CandidateBasis,
    CandidateQuery,
    Factor,
    FactorPick,
    FallbackReason,
    InputRow,
    LicenseStatus,
    SupportedCategory,
)
from esgapi.inventory.engines.scope3.llm_first_1.units import activity_dim, conversion_factor

# 한 번의 추천 호출에 넣는 후보 수의 기본. 출처: esg-lab ts/scope3/src/domain/pipeline.ts:24 (HEAD f1b2c77).
DEFAULT_SHORTLIST_SIZE: Final = 25


@dataclass(frozen=True, slots=True)
class PipelineOptions:
    """`exclude_license_statuses`: 이 이용 조건 상태의 계수를 후보에서 뺀다(순수 층의 기본은 빼지 않음 — TS 그대로.
    서버의 기본은 업무 층이 정한다). `adjustments` 가 없으면 지출 기반 계산은 `needs_currency_adjustment` 로 끝난다.
    """

    client: LlmGateway
    store: FactorCatalog
    memory: MappingMemory
    route: str
    tags: Tags
    exclude_license_statuses: tuple[LicenseStatus, ...] = ()
    shortlist_size: int = DEFAULT_SHORTLIST_SIZE
    shortlister: Shortlister = field(default_factory=default_shortlister)
    adjustments: tuple[CurrencyAdjustment, ...] = ()


@dataclass(frozen=True, slots=True)
class BasisTrace:
    """어느 기반의 계수를 썼는지와, 지출 기반으로 넘어갔다면 그 까닭."""

    used: Basis
    fell_back: bool
    fallback_reason: FallbackReason | None


@dataclass(frozen=True, slots=True)
class CandidateStats:
    """추천 호출에 넣기 전 후보 수, 추려서 넣은 수, 검색어와 겹친 후보 수, 추린 방식.

    `lexical_matches` 가 0 이면 추린 목록은 표의 앞 순서일 뿐이다.
    """

    total: int
    shown: int
    lexical_matches: int
    method: ShortlistMethod


# ── 묶음 하나에 대한 판단: 9갈래 ──


@dataclass(frozen=True, slots=True)
class Recommended:
    """`picks` 의 첫째가 대표 결과, 전체가 후보 목록이다. 기억에서 온 것은 하나다.

    `candidates` 는 추천 호출에 넣은 후보의 규모다(기억에서 온 판단은 None).
    """

    source: Literal["memory", "llm"]
    category: SupportedCategory
    picks: tuple[FactorPick, ...]
    basis: BasisTrace
    classification: Classification | None
    memory_entry: MemoryEntry | None
    candidates: CandidateStats | None
    status: Literal["recommended"] = "recommended"


@dataclass(frozen=True, slots=True)
class MemoryFactorMissing:
    """기억의 계수 id 가 지금 표에 없다. 생성 모델로 넘기지 않고 사람에게 돌린다."""

    memory_entry: MemoryEntry
    source: Literal["memory"] = "memory"
    status: Literal["memory_factor_missing"] = "memory_factor_missing"


@dataclass(frozen=True, slots=True)
class MemoryCategoryMismatch:
    """기억의 범주가 그 계수의 Scope 3 범주 후보에 없다. 기억이 잘못됐거나 표가 바뀐 것이다."""

    memory_entry: MemoryEntry
    factor_categories: tuple[int, ...]
    source: Literal["memory"] = "memory"
    status: Literal["memory_category_mismatch"] = "memory_category_mismatch"


@dataclass(frozen=True, slots=True)
class MemoryFactorExcluded:
    """기억의 계수가 이용 조건 설정으로 제외돼 있다."""

    memory_entry: MemoryEntry
    license_status: LicenseStatus
    source: Literal["memory"] = "memory"
    status: Literal["memory_factor_excluded"] = "memory_factor_excluded"


@dataclass(frozen=True, slots=True)
class ClassificationFailed:
    llm: LlmFailure
    source: Literal["llm"] = "llm"
    status: Literal["classification_failed"] = "classification_failed"


@dataclass(frozen=True, slots=True)
class UnsupportedCategory:
    """AI 적용 범주(1·2·4·6·7·9) 밖이거나 판단 불가."""

    classification: Classification
    source: Literal["llm"] = "llm"
    status: Literal["unsupported_category"] = "unsupported_category"


@dataclass(frozen=True, slots=True)
class NoCandidates:
    """활동 기반도 지출 기반도 후보가 없다(빈 추천이 아니다)."""

    category: SupportedCategory
    classification: Classification
    physical: FallbackReason
    source: Literal["llm"] = "llm"
    status: Literal["no_candidates"] = "no_candidates"


@dataclass(frozen=True, slots=True)
class NoSuitableFactor:
    """후보는 있었지만 생성 모델이 쓸 만한 것이 없다고 답했다."""

    category: SupportedCategory
    classification: Classification
    physical: FallbackReason
    source: Literal["llm"] = "llm"
    status: Literal["no_suitable_factor"] = "no_suitable_factor"


@dataclass(frozen=True, slots=True)
class RecommendationFailed:
    category: SupportedCategory
    classification: Classification
    basis: CandidateBasis
    llm: LlmFailure
    source: Literal["llm"] = "llm"
    status: Literal["recommendation_failed"] = "recommendation_failed"


type GroupDecision = (
    Recommended
    | MemoryFactorMissing
    | MemoryCategoryMismatch
    | MemoryFactorExcluded
    | ClassificationFailed
    | UnsupportedCategory
    | NoCandidates
    | NoSuitableFactor
    | RecommendationFailed
)


@dataclass(frozen=True, slots=True)
class RowResult:
    row: InputRow
    group_key: str
    decision: GroupDecision
    calc: CalcResult


@dataclass(frozen=True, slots=True)
class ShortlistTrace:
    """추천 호출 한 번에 넣은 후보 목록. 추리기가 정답을 떨어뜨렸는지 보려고 id 와 후보별 근거까지 남긴다."""

    basis: CandidateBasis
    method: ShortlistMethod
    total: int
    shown_ids: tuple[str, ...]
    evidence: tuple[CandidateEvidence, ...]


@dataclass(frozen=True, slots=True)
class GroupResult:
    """`shortlists` 는 추천 호출마다 하나다(호출이 실패했어도 남는다).

    기억에서 온 묶음과 추천까지 못 간 묶음은 비어 있다.
    """

    key: str
    row_ids: tuple[str, ...]
    decision: GroupDecision
    shortlists: tuple[ShortlistTrace, ...]


@dataclass(frozen=True, slots=True)
class ShortlistInfo:
    method: ShortlistMethod
    description: str


@dataclass(frozen=True, slots=True)
class PipelineResult:
    rows: tuple[RowResult, ...]
    groups: tuple[GroupResult, ...]
    usage: LlmUsage
    shortlist: ShortlistInfo


@dataclass(frozen=True, slots=True)
class PipelineRejected:
    """입력이 틀려 한 묶음도 판단하지 않았다(생성 모델을 부르지 않았다)."""

    kind: Literal["duplicate_row_id", "invalid_adjustments"]
    row_id: str | None = None
    problems: tuple[AdjustmentProblem, ...] = ()


@dataclass(frozen=True, slots=True)
class _Picked:
    picks: tuple[FactorPick, ...]
    candidates: CandidateStats


def _recommend(
    options: PipelineOptions,
    usage: LlmUsage,
    row: InputRow,
    category: SupportedCategory,
    basis: CandidateBasis,
    candidates: Sequence[Factor],
    keywords: tuple[str, ...],
    trace: list[ShortlistTrace],
) -> _Picked | LlmFailure:
    texts = (row.item_name, row.transport.mode) if row.transport is not None else (row.item_name,)
    short = options.shortlister.shortlist(candidates, ShortlistQuery(texts, keywords), options.shortlist_size)
    shown_ids = tuple(factor.id for factor in short.factors)
    trace.append(ShortlistTrace(basis, short.method, short.total, shown_ids, short.evidence))
    result = options.client.call(recommend_request(row, category, basis, short.factors, options.route, options.tags))
    record_usage(usage, RECOMMEND_PROMPT, result.meta)
    if not isinstance(result, Success):
        return describe_failure(result)
    return _Picked(
        picks=tuple(FactorPick(pick.factor_id, pick.reason, pick.confidence) for pick in result.data.picks),
        candidates=CandidateStats(short.total, len(short.factors), short.lexical_matches, short.method),
    )


def _decide_from_memory(options: PipelineOptions, entry: MemoryEntry) -> GroupDecision:
    factor = options.store.get(entry.factor_id)
    if factor is None:
        return MemoryFactorMissing(entry)
    if entry.category not in factor.scope3_categories:
        return MemoryCategoryMismatch(entry, factor.scope3_categories)
    if factor.license_status in options.exclude_license_statuses:
        return MemoryFactorExcluded(entry, factor.license_status)
    reason = f"확정 매핑 기억 ({entry.confirmed_by}, {entry.confirmed_at})"
    return Recommended(
        source="memory",
        category=entry.category,
        picks=(FactorPick(entry.factor_id, reason, "high"),),
        basis=BasisTrace(factor.factor_type, False, None),
        classification=None,
        memory_entry=entry,
        candidates=None,
    )


def first_duplicate_row_id(rows: Sequence[InputRow]) -> str | None:
    """입력 차례로 처음 다시 나온 rowId. 겹치지 않으면 None. 묶기 전에 보고, 겹치면 한 묶음도 판단하지 않는다."""
    seen: set[str] = set()
    for row in rows:
        if row.row_id in seen:
            return row.row_id
        seen.add(row.row_id)
    return None


def classify_group(
    client: LlmGateway, group: RowGroup, route: str, tags: Tags, usage: LlmUsage
) -> Classification | LlmFailure:
    """묶음 하나의 범주를 묶음의 첫 행으로 한 번 묻고 사용량을 적는다. 호출이 성공이 아니면 그 실패의 갈래다.

    「행 → 묶음 → 묶음마다 분류」의 한 벌이다(밴드 CU1): 파이프라인의 `decide_group` 과 업무 층의 `scope3_classify`
    가 `first_duplicate_row_id` → `group_rows` → 묶음마다 이것의 차례로 부른다.
    """
    result = client.call(classify_request(group.rows[0], route, tags))
    record_usage(usage, CLASSIFY_PROMPT, result.meta)
    if not isinstance(result, Success):
        return describe_failure(result)
    data = result.data
    return Classification(data.category, tuple(data.keywords_en), data.confidence, data.reason)


def physical_candidates(
    store: FactorCatalog, row: InputRow, category: SupportedCategory, exclude: tuple[LicenseStatus, ...] = ()
) -> list[Factor] | FallbackReason:
    """활동(물량)·거리 기반 후보 가운데 그 행의 단위로 환산이 되는 것(표의 순서). 하나도 없으면 지출 기반으로 넘어갈
    까닭이다: 활동·거리 기반 후보가 있었는데 단위가 안 맞으면 `unit_mismatch`, 아예 없으면 `no_activity_candidates`.

    후보 고르기의 한 벌이다(밴드 CU1): 파이프라인의 `decide_group` 과 업무 층의 `scope3_shortlist` 가 이것을 부른다.
    `exclude` 는 파이프라인의 이용 조건 설정이다(업무 층은 표를 넘기기 전에 이미 거른다).
    """
    physical_all = store.candidates(CandidateQuery(category, "physical", exclude))
    dim = activity_dim(row.unit, row.transport)
    physical = [factor for factor in physical_all if conversion_factor(dim, factor.denominator_dim) is not None]
    if physical:
        return physical
    return "unit_mismatch" if physical_all else "no_activity_candidates"


def decide_group(
    options: PipelineOptions, group: RowGroup, usage: LlmUsage, trace: list[ShortlistTrace] | None = None
) -> GroupDecision:
    """묶음 하나를 판단한다. 분류와 추천은 묶음의 첫 행으로 묻는다."""
    if trace is None:
        trace = []
    remembered = options.memory.lookup(group.key)
    if remembered is not None:
        return _decide_from_memory(options, remembered)

    row = group.rows[0]
    classification = classify_group(options.client, group, options.route, options.tags, usage)
    if isinstance(classification, LlmFailure):
        return ClassificationFailed(classification)
    if classification.category == "other":
        return UnsupportedCategory(classification)
    category: SupportedCategory = classification.category
    exclude = options.exclude_license_statuses

    physical = physical_candidates(options.store, row, category, exclude)
    fallback_reason: FallbackReason
    if not isinstance(physical, str):
        outcome = _recommend(options, usage, row, category, "physical", physical, classification.keywords, trace)
        if isinstance(outcome, LlmFailure):
            return RecommendationFailed(category, classification, "physical", outcome)
        if outcome.picks:
            first = options.store.get(outcome.picks[0].factor_id)
            if first is None:  # pragma: no cover  (추천 스키마가 후보 밖 id 를 막는다)
                raise AssertionError("추천된 계수가 표에 없다")
            return Recommended(
                source="llm",
                category=category,
                picks=outcome.picks,
                basis=BasisTrace(first.factor_type, False, None),
                classification=classification,
                memory_entry=None,
                candidates=outcome.candidates,
            )
        fallback_reason = "llm_found_none_suitable"
    else:
        fallback_reason = physical

    spend = options.store.candidates(CandidateQuery(category, "spend", exclude))
    if not spend:
        if fallback_reason == "llm_found_none_suitable":
            return NoSuitableFactor(category, classification, fallback_reason)
        return NoCandidates(category, classification, fallback_reason)
    outcome = _recommend(options, usage, row, category, "spend", spend, classification.keywords, trace)
    if isinstance(outcome, LlmFailure):
        return RecommendationFailed(category, classification, "spend", outcome)
    if not outcome.picks:
        return NoSuitableFactor(category, classification, fallback_reason)
    return Recommended(
        source="llm",
        category=category,
        picks=outcome.picks,
        basis=BasisTrace("spend", True, fallback_reason),
        classification=classification,
        memory_entry=None,
        candidates=outcome.candidates,
    )


def calculate_for(
    store: FactorCatalog, adjustments: Sequence[CurrencyAdjustment], row: InputRow, decision: GroupDecision
) -> CalcResult:
    """묶음의 판단을 행에 펼쳐 대표 결과(첫째 추천)로 계산한다."""
    if not isinstance(decision, Recommended):
        return NotCalculated(decision.status)
    factor = store.get(decision.picks[0].factor_id)
    if factor is None:  # pragma: no cover  (추천된 계수는 표에서 온 것이다)
        raise AssertionError("추천된 계수가 표에 없다")
    return calculate_row(row, factor, adjustments)


def run_pipeline(rows: Sequence[InputRow], options: PipelineOptions) -> PipelineResult | PipelineRejected:
    """행을 묶어 묶음 단위로 판단하고 행에 펼친다. 묶음은 차례로 처리한다(호출 순서가 결과와 기록에 그대로 남는다)."""
    problems = check_adjustments(options.adjustments)
    if problems:
        return PipelineRejected("invalid_adjustments", problems=problems)
    duplicate = first_duplicate_row_id(rows)
    if duplicate is not None:
        return PipelineRejected("duplicate_row_id", row_id=duplicate)

    usage = LlmUsage()
    groups = group_rows(rows)
    decisions: dict[str, GroupDecision] = {}
    traces: dict[str, list[ShortlistTrace]] = {}
    for group in groups:
        trace: list[ShortlistTrace] = []
        decisions[group.key] = decide_group(options, group, usage, trace)
        traces[group.key] = trace

    key_of_row = {row.row_id: group.key for group in groups for row in group.rows}
    results = tuple(
        RowResult(
            row,
            key_of_row[row.row_id],
            decisions[key_of_row[row.row_id]],
            calculate_for(options.store, options.adjustments, row, decisions[key_of_row[row.row_id]]),
        )
        for row in rows
    )
    return PipelineResult(
        rows=results,
        groups=tuple(
            GroupResult(
                group.key, tuple(row.row_id for row in group.rows), decisions[group.key], tuple(traces[group.key])
            )
            for group in groups
        ),
        usage=usage,
        shortlist=ShortlistInfo(options.shortlister.method, options.shortlister.description),
    )
