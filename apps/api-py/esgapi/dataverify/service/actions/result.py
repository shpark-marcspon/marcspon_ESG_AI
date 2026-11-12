"""결과 읽기(GET /dataverify/runs/{run_id}/result 의 몸 — 밴드 DV1e ②).

runs 의 selectors(find_run·run_results)로만 읽는다 — 둘 다 회사 조건이 붙어 남의 회사 실행은 없는 실행이다. 남의
도메인(runs)을 엮으므로 Selector 가 아니라 Action 이다(translation service/actions/result.py 꼴). 갈래:
    결과 본문   module dataverify · status done · 결과 dataverify.result@2 가 있음 → 그 본문
    NotFound    없음·남의 회사·다른 모듈·끝났는데 @2 결과 없음(@1 행만 있어도 — 발주서 Q6 가)
    RunNotDone  그 회사·데이터 검증 실행이지만 끝나지 않음(queued·processing·failed — Q5 가)
"""

from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.dataverify.contracts.shapes import RESULT_SHAPE
from esgapi.runs.service.selectors import runs as run_selectors

MODULE: Final = "dataverify"


@dataclass(frozen=True, slots=True)
class NotFound:
    """실행이 없다(남의 회사·데이터 검증 아닌 실행·@2 결과가 없는 실행도 이 갈래)."""


@dataclass(frozen=True, slots=True)
class RunNotDone:
    status: str


type Refusal = NotFound | RunNotDone


def run_result(*, company_id: int, run_id: int) -> dict[str, Any] | Refusal:
    """끝난 데이터 검증 실행의 결과 본문(dataverify.result@2)."""
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE:
        return NotFound()
    if run.status != "done":
        return RunNotDone(run.status)
    results = run_selectors.run_results(company_id=company_id, run_id=run_id)
    body = next((r.body for r in results if r.schema_version == RESULT_SHAPE), None)
    if not isinstance(body, dict):  # 끝난 실행에는 늘 있다 — 없으면(@1 시절 행 등) 없는 실행으로(영문번역과 같음)
        return NotFound()
    return cast("dict[str, Any]", body)
