"""목차 차이 보기(GET /drafting/projects/{project_id}/outline/changes 의 몸 — 밴드 RP2c, 처분 ⑦ 가).

drafting 의 selectors(프로젝트·목차 판·지금 문서) + runs 의 find_run(회사 조건) + core 의 find_document(회사 조건)를
엮으므로 Action 이다(service/actions/result.py 꼴). 목차 차이만 — 실제로 옮겼는지는 결과의 base·reusedFrom 이 말한다
(옮김은 분해 artifactId·pagesSha256 으로 가르고, 여기 document 는 문서 id·etag 로 가른다).
갈래:
    차이 dict   DraftingOutlineChanges 꼴
    NotFound    프로젝트·지금 목차 없음 · 실행 없음(남의 회사)·원고작성 아님·다른 프로젝트·끝나지 않음·앞 목차 판을 못
                읽음 — 한 갈래(경로는 한 글 404)
"""

from dataclasses import dataclass
from typing import Any

from esgapi.core.service.selectors import documents as document_selectors
from esgapi.drafting.contracts import wire
from esgapi.drafting.flows.draft_v2 import MODULE
from esgapi.drafting.service.selectors import projects as selectors
from esgapi.runs.service.selectors import runs as run_selectors


@dataclass(frozen=True, slots=True)
class NotFound:
    """프로젝트·목차·앞 실행 가운데 하나를 찾지 못했다."""


def outline_changes(*, company_id: int, project_id: int, base_run_id: int) -> dict[str, Any] | NotFound:
    if selectors.project_head(company_id=company_id, project_id=project_id) is None:
        return NotFound()
    head = selectors.current_outline(company_id=company_id, project_id=project_id)
    run = run_selectors.find_run(company_id=company_id, run_id=base_run_id)
    if head is None or run is None or run.module != MODULE or run.status != "done":
        return NotFound()
    base_outline_id = run.versions.get("outlineId")
    if run.options.get("projectId") != project_id or not isinstance(base_outline_id, int):
        return NotFound()
    base = selectors.outline_at(company_id=company_id, outline_id=base_outline_id)
    current = selectors.outline_at(company_id=company_id, outline_id=head.id)
    if base is None or base.project_id != project_id or current is None:
        return NotFound()
    changes, removed = wire.outline_changes(base.outline["nodes"], current.outline["nodes"])
    attached = selectors.current_document(company_id=company_id, project_id=project_id)
    found = (
        None
        if attached is None
        else document_selectors.find_document(company_id=company_id, document_id=attached.document_id)
    )
    same = (
        attached is not None
        and found is not None
        and run.versions.get("documentId") == attached.document_id
        and run.versions.get("documentEtag") == found.etag
    )
    return {
        "baseRunId": run.id,
        "baseOutlineId": base.id,
        "outlineId": current.id,
        "document": "same" if same else "changed",
        "leaves": [{"key": key, "change": change} for key, change in changes.items()],
        "removed": list(removed),
    }
