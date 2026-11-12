"""중대성평가 IRO 실행 목록(GET /materiality/runs 의 몸 — 밴드 IR3c, MARC-ENT-419). runs(실행·단계·결과)·user(이름)를
엮어 조립하므로 Action 이다(dataverify service/actions/runs.py 꼴). 꼴은 contracts/run_list_shapes.py.

    runs(company_id, user_id, statuses, mine, limit, offset)   한 쪽(MaterialityRunPage)

규칙(발주서 IR3c §2-2·1-5):
  - 실행은 run_page_brief(module="materiality") 로만(회사 조건) — 옵션 본문은 읽지 않고 아래 경로만 투영한다(IRS2,
    MARC-ISSUE-444 — HD1 347 ① 꼴. 감싼 글자 안에 \\u0000 이 든 줄만 본문이 whole 로 와서 옛 셈 그대로).
    거름은 상태 집합(statuses — None 이면 안 거름)과 만든 사람(mine 이면 부른 사람). 검색·기간 거름은 하지 않는다
    (처분 ⑩).
  - 옵션에서 싣는 값(기업명·산업 기준과 이름·토픽 수·기간 글·최신 이슈 반영)은 꼴을 다시 잰다 — 꼴이 아니면 그 칸만
    null(ninja 가 응답을 검사해 꼴 밖 값이면 쪽 전체가 500 이 된다). 토픽 이름·설명·산업 설명·서브토픽·가치사슬은
    싣지 않는다.
  - failedStep 은 failed 실행만, currentStep 은 processing 실행의 running 단계(step_lines_of), 두 수는 done 실행의
    요약(results_of 의 schema_versions — 결과 본문 result@2 는 읽지 않는다).
★ 쿼리 수: 실행 쪽 2(줄·count) · 단계 1 · 요약 1 · 이름 1 = 많아야 5. 쪽이 비면 뒤 셋 0, processing 이 없으면 단계 0,
  done 이 없으면 요약 0.
"""

from collections.abc import Collection, Mapping
from typing import Final, cast

from pydantic import ValidationError

from esgapi.core.schemas import to_seoul_iso
from esgapi.materiality.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES, MaterialityDigest
from esgapi.materiality.contracts.run_list_shapes import (
    MaterialityPerson,
    MaterialityRunIndustry,
    MaterialityRunPage,
    MaterialityRunRow,
    MaterialityRunStatus,
)
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.selectors.runs import BriefRun
from esgapi.user.service.selectors.user import people_of

MODULE: Final = "materiality"
UNKNOWN_USER: Final = "알 수 없는 사용자"


def _input(options: Mapping[str, object]) -> dict[str, object]:
    """옵션 input(dict 가 아니면 빈 것 — 칸마다 null 이 된다)."""
    given = options.get("input")
    return cast("dict[str, object]", given) if isinstance(given, dict) else {}


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _company(given: Mapping[str, object]) -> str | None:
    company = given.get("company")
    return _text(cast("dict[str, object]", company).get("name")) if isinstance(company, dict) else None


def _industries(given: Mapping[str, object]) -> list[MaterialityRunIndustry] | None:
    """산업마다 기준·이름(글자)만. 목록이 아니거나 원소 하나라도 꼴이 아니면 None."""
    found = given.get("industries")
    if not isinstance(found, list):
        return None
    out: list[MaterialityRunIndustry] = []
    for item in cast("list[object]", found):
        if not isinstance(item, dict):
            return None
        standard, name = (
            cast("dict[str, object]", item).get("standard"),
            cast("dict[str, object]", item).get("industryName"),
        )
        if not isinstance(standard, str) or not isinstance(name, str):
            return None
        out.append({"standard": standard, "industryName": name})
    return out


def _topic_count(given: Mapping[str, object]) -> int | None:
    topics = given.get("topics")
    return len(cast("list[object]", topics)) if isinstance(topics, list) else None


def _latest(given: Mapping[str, object]) -> bool | None:
    mode = given.get("latestEventMode")
    return mode if isinstance(mode, bool) else None


# run_page_brief 가 투영할 옵션 경로(IRS2 444 — 위 _company·_industries·_text·_latest·_topic_count 가 읽는 자리 그대로).
# 산업은 목록 값을 통째로(원소의 description 도 올라오지만 응답엔 싣지 않는다 — 처분 D1 가)
BRIEF_VALUES: Final[Mapping[str, tuple[str, ...]]] = {
    "name": ("input", "company", "name"),
    "industries": ("input", "industries"),
    "dateRange": ("input", "dateRange"),
    "latest": ("input", "latestEventMode"),
}
BRIEF_SHAPES: Final[Mapping[str, tuple[str, ...]]] = {"topics": ("input", "topics")}


def _brief_input(run: BriefRun) -> dict[str, object]:
    """투영한 값으로 지은 작은 input(_company·_industries·_text·_latest 가 읽는 자리만). 없는 경로·JSON null·꼴 밖
    부모는 pg 에서 둘 다 NULL → None 이라 셈이 같다(그 함수들은 None 을 꼴 밖으로 본다)."""
    values = run.values
    return {
        "company": {"name": values["name"]},
        "industries": values["industries"],
        "dateRange": values["dateRange"],
        "latestEventMode": values["latest"],
    }


def _brief_topic_count(run: BriefRun) -> int | None:
    """_topic_count 와 같은 셈을 꼴·길이로: 목록이면 길이, 그 밖 None."""
    kind, length = run.shapes["topics"]
    return length if kind == "array" else None


def _digests(company_id: int, run_ids: Collection[int]) -> dict[int, MaterialityDigest]:
    """done 실행의 요약(실행 id → digest). 요약 전의 옛 실행·꼴 밖 요약은 열쇠가 없다."""
    results = run_selectors.results_of(company_id=company_id, run_ids=run_ids, schema_versions={DIGEST_SHAPE})
    found: dict[int, MaterialityDigest] = {}
    for run_id, rows in results.items():
        body = next((r.body for r in rows if r.schema_version == DIGEST_SHAPE), None)
        try:
            DIGEST_SHAPES[DIGEST_SHAPE].validate_python(body, strict=True)
        except ValidationError:
            continue
        found[run_id] = cast("MaterialityDigest", body)
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
    person: MaterialityPerson,
    current: Mapping[int, str],
    digests: Mapping[int, MaterialityDigest],
) -> MaterialityRunRow:
    given = _input(run.whole) if run.whole is not None else _brief_input(run)
    digest = digests.get(run.id) if run.status == "done" else None
    return {
        "id": run.id,
        "status": cast("MaterialityRunStatus", run.status),
        "createdAt": to_seoul_iso(run.created_at),
        "startedAt": None if run.started_at is None else to_seoul_iso(run.started_at),
        "finishedAt": None if run.finished_at is None else to_seoul_iso(run.finished_at),
        "createdBy": person,
        "companyName": _company(given),
        "industries": _industries(given),
        "topicCount": _topic_count(given) if run.whole is not None else _brief_topic_count(run),
        "dateRange": _text(given.get("dateRange")),
        "latestEventMode": _latest(given),
        "failedStep": run.failed_step if run.status == "failed" else None,
        "currentStep": current.get(run.id) if run.status == "processing" else None,
        "impactRows": None if digest is None else digest["impactRows"],
        "pathwayRows": None if digest is None else digest["pathwayRows"],
    }


def runs(
    *,
    company_id: int,
    user_id: int,
    statuses: Collection[str] | None,
    mine: bool,
    limit: int,
    offset: int,
) -> MaterialityRunPage:
    """그 회사의 중대성평가 IRO 실행 한 쪽. statuses 는 상태 집합(None = 안 거름), mine 이면 user_id 가 만든 것만."""
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

    def person(user: int) -> MaterialityPerson:
        known = names.get(user)
        return {"userId": user, "name": known[1] if known is not None and known[1].strip() else UNKNOWN_USER}

    return {
        "count": page.count,
        "isNext": offset + len(found) < page.count,
        "results": [_row(run, person(run.created_by_user_id), current, digests) for run in found],
    }
