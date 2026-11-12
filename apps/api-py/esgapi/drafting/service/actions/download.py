"""결과 docx 내려받기(GET /drafting/runs/{run_id}/result.docx 의 몸 — 밴드 RP2d, 결정 MARC-ENT-504 「보기 + 내려받기」).

결과는 result.run_result 로 얻는다(갈래 NotFound·RunNotDone 그대로 — 결과 경로와 같은 404·409). 문서는 그 결과
(drafting.bullets@3)에서 늘 다시 짓는다(저장 0 — 짓기는 순수 outputs/docx.py).
"""

from dataclasses import dataclass

from esgapi.drafting.outputs import docx
from esgapi.drafting.service.actions import result as result_actions


@dataclass(frozen=True, slots=True)
class Docx:
    content: bytes
    file_name: str
    """ASCII 만(`drafting-<run_id>.docx`) — Content-Disposition 에 따옴표 꼴로 싣는다."""


def result_docx(*, company_id: int, run_id: int) -> Docx | result_actions.Refusal:
    """끝난 원고작성 실행의 결과를 docx 한 파일로. 갈래는 result.run_result 그대로."""
    found = result_actions.run_result(company_id=company_id, run_id=run_id)
    if isinstance(found, result_actions.NotFound | result_actions.RunNotDone):
        return found
    return Docx(content=docx.build(found, run_id=run_id), file_name=docx.file_name(run_id))
