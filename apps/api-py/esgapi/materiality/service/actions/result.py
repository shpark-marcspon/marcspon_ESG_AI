"""결과 읽기(GET /materiality/runs/{run_id}/result 의 몸 — 밴드 IR3b ②, 고친 판은 IRS3 ②).

runs 의 selectors(find_run·run_results)로만 읽는다 — 둘 다 회사 조건이 붙어 남의 회사 실행은 없는 실행이다. 남의
도메인(runs)을 엮으므로 Selector 가 아니라 Action 이다(dataverify service/actions/result.py 꼴). 갈래:
    결과 본문   module materiality · status done · 결과 materiality.result@2 가 있음 → 그 본문
    NotFound    없음·남의 회사·다른 모듈·끝났는데 @2 결과 없음(@1 행만 있어도 — 발주서 ④ 가)
    RunNotDone  그 회사·중대성평가 실행이지만 끝나지 않음(queued·processing·failed — ③ 가)
original_result 는 AI 원본 본문(run_results 행 그대로 — 고침 저장·엑셀의 재료), run_result 는 그 위에 지금 고침
(selectors/edits.current_edits — 주소마다 가장 큰 revision)을 덮은 고친 판이다(outputs/edits.apply — 새 dict, 꼴은
result@2 그대로. 고침이 없으면 원본 본문 그대로). run_results·run_files 는 읽기만 한다(밴드 IRS3, 결정 MARC-ENT-561).
"""

from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.materiality.contracts.shapes import RESULT_SHAPE_V2
from esgapi.materiality.outputs import edits
from esgapi.materiality.service.selectors import edits as edit_selectors
from esgapi.runs.service.selectors import runs as run_selectors

MODULE: Final = "materiality"


@dataclass(frozen=True, slots=True)
class NotFound:
    """실행이 없다(남의 회사·중대성평가 아닌 실행·@2 결과가 없는 실행도 이 갈래)."""


@dataclass(frozen=True, slots=True)
class RunNotDone:
    status: str


type Refusal = NotFound | RunNotDone


def original_result(*, company_id: int, run_id: int) -> dict[str, Any] | Refusal:
    """끝난 중대성평가 IRO 실행의 AI 원본 결과 본문(materiality.result@2 — 고침 전)."""
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE:
        return NotFound()
    if run.status != "done":
        return RunNotDone(run.status)
    results = run_selectors.run_results(company_id=company_id, run_id=run_id)
    body = next((r.body for r in results if r.schema_version == RESULT_SHAPE_V2), None)
    if not isinstance(body, dict):  # 끝난 실행에는 늘 있다 — 없으면(@1 행만 등) 없는 실행으로(데이터 검증과 같음)
        return NotFound()
    return cast("dict[str, Any]", body)


def run_result(*, company_id: int, run_id: int) -> dict[str, Any] | Refusal:
    """끝난 중대성평가 IRO 실행의 결과(materiality.result@2) — 지금 고침을 덮은 고친 판."""
    body = original_result(company_id=company_id, run_id=run_id)
    if isinstance(body, NotFound | RunNotDone):
        return body
    rows = edit_selectors.current_edits(company_id=company_id, run_id=run_id)
    return edits.apply(body, {row.pointer: row.value for row in rows})
