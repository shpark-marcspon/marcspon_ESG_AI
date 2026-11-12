"""원고작성 프로젝트의 쓰기 묶음(경로 PUT document·PUT outline 의 몸 — 밴드 RP1 ③). 남의 도메인(core 의 문서)을
엮거나 표 여럿을 한 트랜잭션으로 묶으므로 Action 이다(③ R1 — services 는 표마다 함수 하나).

    attach_document(company_id, project_id, document_id, user_id)
        문서 확인(같은 회사·올림 끝·글자 층) → 새 행. 갈래: 프로젝트 없음·문서 없음(남의 회사도) → ProjectMissing·
        DocumentMissing · 올림 미완 → DocumentNotUploaded · has_text false → DocumentNoTextLayer(null = 모름은 받는다)
    put_outline(company_id, project_id, outline, user_id)
        받기를 지난 목차(wire.accept_outline 정규형)를 한 트랜잭션으로: 프로젝트 행 잠금 → 지금 판과 sha 가 같으면 그
        판(멱등, 쓰기 0) → 아니면 revision +1·판·마디 INSERT

★ 겹친 PUT outline 둘은 프로젝트 행 잠금(selectors.lock_project — FOR UPDATE)으로 줄 선다 — 뒤의 것은 앞의 것이
  커밋한 판 번호를 읽는다(번호 겹침 0, unique 는 마지막 그물).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from django.db import transaction

from esgapi.core.service.selectors import documents as document_selectors
from esgapi.drafting.contracts.wire import outline_sha256
from esgapi.drafting.service.selectors import projects as selectors
from esgapi.drafting.service.services import projects as services
from esgapi.drafting.service.services.projects import ProjectMissing

UPLOADED: Final = "uploaded"


@dataclass(frozen=True, slots=True)
class DocumentMissing:
    """문서가 없다(남의 회사 id 도 같다)."""


@dataclass(frozen=True, slots=True)
class DocumentNotUploaded:
    """올림이 끝나지 않은 문서다."""


@dataclass(frozen=True, slots=True)
class DocumentNoTextLayer:
    """글자 층이 없는 문서다(has_text false)."""


@dataclass(frozen=True, slots=True)
class OutlinePut:
    outline_id: int
    revision: int
    sha256: str
    created: bool
    """False = 지금 판과 sha 가 같아 그 판을 돌려줌(쓰기 0)."""


type AttachRefusal = ProjectMissing | DocumentMissing | DocumentNotUploaded | DocumentNoTextLayer


@transaction.atomic
def attach_document(*, company_id: int, project_id: int, document_id: int, user_id: int) -> int | AttachRefusal:
    if selectors.project_head(company_id=company_id, project_id=project_id) is None:
        return ProjectMissing()
    found = document_selectors.find_document(company_id=company_id, document_id=document_id)
    if found is None:
        return DocumentMissing()
    if found.status != UPLOADED:
        return DocumentNotUploaded()
    if found.has_text is False:
        return DocumentNoTextLayer()
    return services.attach_document(
        company_id=company_id, project_id=project_id, document_id=document_id, user_id=user_id
    )


@transaction.atomic
def put_outline(
    *, company_id: int, project_id: int, outline: Mapping[str, Any], user_id: int
) -> OutlinePut | ProjectMissing:
    locked = selectors.lock_project(company_id=company_id, project_id=project_id)
    if locked is None:
        return ProjectMissing()
    sha = outline_sha256(outline)
    current = selectors.current_outline(company_id=company_id, project_id=project_id)
    if current is not None and current.sha256 == sha:
        return OutlinePut(outline_id=current.id, revision=current.revision, sha256=sha, created=False)
    revision = locked.outline_revision + 1
    nodes = list(outline["nodes"])
    services.bump_revision(company_id=company_id, project_id=project_id, revision=revision)
    outline_id = services.insert_outline(
        company_id=company_id,
        project_id=project_id,
        revision=revision,
        sha256=sha,
        node_count=len(nodes),
        user_id=user_id,
    )
    services.insert_nodes(company_id=company_id, outline_id=outline_id, nodes=nodes)
    return OutlinePut(outline_id=outline_id, revision=revision, sha256=sha, created=True)
