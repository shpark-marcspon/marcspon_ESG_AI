"""데이터 검증 실행 목록(GET /dataverify/runs 의 몸 — 밴드 DV1g, MARC-ISSUE-336·MARC-ENT-420). runs(실행·단계·결과)·
user(이름)를 엮어 조립하므로 Action 이다(translation service/actions/batches.py 꼴). 꼴은 contracts/run_list_shapes.py.

    runs(company_id, user_id, statuses, mine, limit, offset)   한 쪽(DataverifyRunPage)

규칙(발주서 DV1g §2-2·1-5):
  - 실행은 run_page_brief(module="dataverify") 로만(회사 조건). 거름은 상태 집합(statuses — None 이면 안 거름)과 만든
    사람(mine 이면 부른 사람). 기업명·보고연도·이름 거름은 하지 않는다(옵션 안 경로 — MARC-ISSUE-336).
  - 옵션 본문은 읽지 않는다(HD1 347 ①): source·input.company 의 이름·보고연도는 그 경로의 값, 항목 수는 input.data 와
    테마의 꼴·길이만 투영해 받는다(BRIEF_VALUES·BRIEF_SHAPES). 감싼 글자에 \\u0000 이 든 줄만 본문이 와 옛 셈 그대로.
  - 옵션에서 싣는 값(source·기업명·보고연도·항목 수)과 요약은 꼴을 다시 잰다 — 꼴이 아니면 그 칸만 null(ninja 가
    응답을 검사해 꼴 밖 값이면 쪽 전체가 500 이 된다).
  - failedStep 은 failed 실행만, currentStep 은 processing 실행의 running 단계(step_lines_of), stages·checks 는 done
    실행의 요약(results_of 의 schema_versions — 결과 본문 result@2 는 읽지 않는다).
★ 쿼리 수: 실행 쪽 2(줄·count — run_page_brief) · 단계 1 · 요약 1 · 이름 1 = 많아야 5. 쪽이 비면 뒤 셋 0,
  processing 이 없으면 단계 0, done 이 없으면 요약 0(빈 입력이면 쿼리 0 — batches.py 선례).
"""

from collections.abc import Collection, Mapping
from typing import Any, Final, cast

from pydantic import TypeAdapter, ValidationError

from esgapi.core.schemas import to_seoul_iso
from esgapi.dataverify.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES, DataverifyDigest
from esgapi.dataverify.contracts.options_shapes import DataverifySource
from esgapi.dataverify.contracts.run_list_shapes import (
    DataverifyPerson,
    DataverifyRunPage,
    DataverifyRunRow,
    DataverifyRunStatus,
)
from esgapi.dataverify.contracts.shapes import Year
from esgapi.dataverify.engines.colab_156.inputs import THEMES
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.selectors.runs import BriefRun
from esgapi.user.service.selectors.user import people_of

MODULE: Final = "dataverify"
UNKNOWN_USER: Final = "알 수 없는 사용자"
SOURCE: Final = TypeAdapter[Any](DataverifySource)
YEAR: Final = TypeAdapter[str](Year)


def _source(options: Mapping[str, object]) -> Any:
    """옵션 source 를 꼴로 다시 잰다(strict). 없거나 꼴이 아니면 None."""
    if "source" not in options:
        return None
    try:
        return SOURCE.validate_python(options["source"], strict=True)
    except ValidationError:
        return None


def _field(value: object, key: str) -> object:
    """dict 면 그 열쇠의 값, 아니면(없음·꼴 밖) None."""
    return cast("dict[str, object]", value).get(key) if isinstance(value, dict) else None


def _company(options: Mapping[str, object]) -> object:
    return _field(options.get("input"), "company")


def _name(options: Mapping[str, object]) -> str | None:
    name = _field(_company(options), "name")
    return name if isinstance(name, str) else None


def _year(options: Mapping[str, object]) -> str | None:
    year = _field(_company(options), "reportingYear")
    try:
        return YEAR.validate_python(year, strict=True)
    except ValidationError:
        return None


def _items(options: Mapping[str, object]) -> int | None:
    """검증 대상 테마(엔진 상수 THEMES — 「환경」)의 항목 수. 입력·data·그 테마가 꼴이 아니면 None, 테마가 없으면 0
    (결과 scope.itemCount 와 같은 셈 — 엔진은 없는 테마를 빈 목록으로 본다)."""
    data = _field(options.get("input"), "data")
    if not isinstance(data, dict):
        return None
    count = 0
    for theme in THEMES:
        items = cast("dict[str, object]", data).get(theme, [])
        if not isinstance(items, list):
            return None
        count += len(cast("list[object]", items))
    return count


# run_page_brief 가 투영할 옵션 경로(HD1 347 ① — 위 _source·_name·_year·_items 가 읽는 자리 그대로)
BRIEF_VALUES: Final[Mapping[str, tuple[str, ...]]] = {
    "source": ("source",),
    "name": ("input", "company", "name"),
    "year": ("input", "company", "reportingYear"),
}
BRIEF_SHAPES: Final[Mapping[str, tuple[str, ...]]] = {
    "data": ("input", "data"),
    **{f"theme{i}": ("input", "data", theme) for i, theme in enumerate(THEMES)},
}


def _brief_options(run: BriefRun) -> dict[str, object]:
    """투영한 값으로 지은 작은 옵션(_source·_name·_year 가 읽는 자리만). 없는 경로와 JSON null 은 둘 다 None 이라 셈이
    같다(_source 는 None 을 꼴 밖으로 · _name·_year 는 None 을 꼴 밖으로 본다)."""
    values = run.values
    company = {"name": values["name"], "reportingYear": values["year"]}
    return {"source": values["source"], "input": {"company": company}}


def _brief_items(run: BriefRun) -> int | None:
    """_items 와 같은 셈을 꼴·길이로: data 가 객체가 아니면 None, 테마가 없으면 0, 목록이면 길이, 그 밖 None."""
    if run.shapes["data"][0] != "object":
        return None
    count = 0
    for i in range(len(THEMES)):
        kind, length = run.shapes[f"theme{i}"]
        if kind is None:
            continue
        if kind != "array" or length is None:
            return None
        count += length
    return count


def _digests(company_id: int, run_ids: Collection[int]) -> dict[int, DataverifyDigest]:
    """done 실행의 요약(실행 id → digest). 요약 전의 옛 실행·꼴 밖 요약은 열쇠가 없다."""
    results = run_selectors.results_of(company_id=company_id, run_ids=run_ids, schema_versions={DIGEST_SHAPE})
    found: dict[int, DataverifyDigest] = {}
    for run_id, rows in results.items():
        body = next((r.body for r in rows if r.schema_version == DIGEST_SHAPE), None)
        try:
            DIGEST_SHAPES[DIGEST_SHAPE].validate_python(body, strict=True)
        except ValidationError:
            continue
        found[run_id] = cast("DataverifyDigest", body)
    return found


def _current(company_id: int, run_ids: Collection[int]) -> dict[int, str]:
    """processing 실행의 running 단계 이름(실행 id → 이름 — 선언 차례로 처음). 없으면 열쇠가 없다."""
    lines = run_selectors.step_lines_of(company_id=company_id, run_ids=run_ids)
    found: dict[int, str] = {}
    for run_id, steps in lines.items():
        running = next((s.name for s in steps if s.status == "running"), None)
        if running is not None:
            found[run_id] = running
    return found


def _row(
    run: BriefRun,
    person: DataverifyPerson,
    current: Mapping[int, str],
    digests: Mapping[int, DataverifyDigest],
) -> DataverifyRunRow:
    digest = digests.get(run.id) if run.status == "done" else None
    options = run.whole if run.whole is not None else _brief_options(run)
    return {
        "id": run.id,
        "status": cast("DataverifyRunStatus", run.status),
        "createdAt": to_seoul_iso(run.created_at),
        "finishedAt": None if run.finished_at is None else to_seoul_iso(run.finished_at),
        "createdBy": person,
        "source": _source(options),
        "companyName": _name(options),
        "reportingYear": _year(options),
        "itemCount": _items(options) if run.whole is not None else _brief_items(run),
        "failedStep": run.failed_step if run.status == "failed" else None,
        "currentStep": current.get(run.id) if run.status == "processing" else None,
        "stages": None if digest is None else digest["stages"],
        "checks": None if digest is None else digest["checks"],
    }


def runs(
    *,
    company_id: int,
    user_id: int,
    statuses: Collection[str] | None,
    mine: bool,
    limit: int,
    offset: int,
) -> DataverifyRunPage:
    """그 회사의 데이터 검증 실행 한 쪽. statuses 는 상태 집합(None = 안 거름), mine 이면 user_id 가 만든 것만."""
    page = run_selectors.run_page_brief(
        company_id=company_id,
        module=MODULE,
        statuses=statuses,
        created_by_user_id=user_id if mine else None,
        limit=limit,
        offset=offset,
        values=BRIEF_VALUES,
        shapes=BRIEF_SHAPES,
    )
    found = list(page.runs)
    current = _current(company_id, [r.id for r in found if r.status == "processing"])
    digests = _digests(company_id, [r.id for r in found if r.status == "done"])
    wanted = {r.created_by_user_id for r in found}
    names = people_of(company_id, wanted)

    def person(user: int) -> DataverifyPerson:
        known = names.get(user)
        return {"userId": user, "name": known[1] if known is not None and known[1].strip() else UNKNOWN_USER}

    return {
        "count": page.count,
        "isNext": offset + len(found) < page.count,
        "results": [_row(run, person(run.created_by_user_id), current, digests) for run in found],
    }
