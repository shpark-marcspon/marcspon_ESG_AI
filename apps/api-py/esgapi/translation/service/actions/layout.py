"""블록·좌표 결과 읽기(GET /translation/runs/{run_id}/layout 의 몸 — 밴드 TRS3, MARC-ENT-471 ③).

result.py 와 같은 꼴이다 — runs 의 selectors(find_run·run_results)로만 읽고, 둘 다 회사 조건이 붙어 남의 회사 실행은
없는 실행이다. 몸은 셋째 결과 행 translation.layout@1 그대로다(새 꼴·투영 0). 갈래:
    결과 본문   module translation · status done · 결과 translation.layout@1 이 있음 → 그 본문(done·rejected 둘 다)
    NotFound    없음·남의 회사·다른 모듈·끝났는데 layout@1 없음(워드 흐름 translation.colab@158 은 이 꼴을 내지 않는다)
    RunNotDone  그 회사·영문번역 실행이지만 끝나지 않음(queued·processing·failed)
"""

from typing import Any, cast

from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.translation.contracts.layout_shapes import LAYOUT_SHAPE
from esgapi.translation.service.actions.result import MODULE, NotFound, Refusal, RunNotDone


def run_layout(*, company_id: int, run_id: int) -> dict[str, Any] | Refusal:
    """끝난 영문번역 PDF 실행의 블록·좌표 결과 본문(translation.layout@1)."""
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE:
        return NotFound()
    if run.status != "done":
        return RunNotDone(run.status)
    results = run_selectors.run_results(company_id=company_id, run_id=run_id)
    body = next((r.body for r in results if r.schema_version == LAYOUT_SHAPE), None)
    if not isinstance(body, dict):  # 워드 흐름의 끝난 실행 — 없는 결과는 없는 실행으로(result_get 과 같은 글)
        return NotFound()
    return cast("dict[str, Any]", body)
