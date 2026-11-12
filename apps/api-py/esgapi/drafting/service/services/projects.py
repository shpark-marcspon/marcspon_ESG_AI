"""쓰기. 원고작성 프로젝트·문서 달기·목차 판(밴드 RP1 ①·③). 읽기는 selectors/projects.py 로만. 함수 하나가 표
하나를 쓴다 — 목차 판의 셋(판 번호·판·마디)을 한 트랜잭션으로 묶는 것은 actions/projects.py 의 put_outline 이다(③ R1).

    create_project(company_id, year, name, user_id)            새 프로젝트 → id
    attach_document(company_id, project_id, document_id, …)    문서 달기 = 새 행(지금 = 가장 늦은 행). 없는 프로젝트면
                                                                ProjectMissing(행 0). 문서의 회사·올림 확인·글자 층은
                                                                부르는 쪽(actions — 남의 도메인)이 먼저 본다
    bump_revision(company_id, project_id, revision)            프로젝트의 outline_revision·updated_at(칸 단위 UPDATE)
    insert_outline(company_id, project_id, …)                  목차 판 머리 한 행 → id
    insert_nodes(company_id, outline_id, nodes)                그 판의 마디(position = 목록 차례)

★ 표는 불변 행이다(SELECT·INSERT). 고치는 칸은 프로젝트의 outline_revision·updated_at 둘뿐이고 QuerySet.update 하나로
  쓴다(save() 는 다른 칸도 쓰려다 권한 오류 — 앱 역할의 칸 단위 UPDATE 권한이 그 두 칸뿐이다).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from esgapi.drafting.models import DraftingOutline, DraftingOutlineNode, DraftingProject, DraftingProjectDocument
from esgapi.drafting.service.selectors import projects as selectors

PRIOR_REPORT = "prior_report"


@dataclass(frozen=True, slots=True)
class ProjectMissing:
    """프로젝트가 없다(남의 회사 id 도 같다)."""


@transaction.atomic
def create_project(*, company_id: int, year: int, name: str, user_id: int) -> int:
    row = DraftingProject.for_company(company_id).create(
        company_id=company_id, year=year, name=name, created_by_user_id=user_id
    )
    return row.id


@transaction.atomic
def attach_document(*, company_id: int, project_id: int, document_id: int, user_id: int) -> int | ProjectMissing:
    if selectors.project_head(company_id=company_id, project_id=project_id) is None:
        return ProjectMissing()
    row = DraftingProjectDocument.for_company(company_id).create(
        company_id=company_id,
        project_id=project_id,
        document_id=document_id,
        kind=PRIOR_REPORT,
        attached_by_user_id=user_id,
    )
    return row.id


@transaction.atomic
def bump_revision(*, company_id: int, project_id: int, revision: int) -> None:
    DraftingProject.for_company(company_id).filter(id=project_id).update(
        outline_revision=revision, updated_at=timezone.now()
    )


@transaction.atomic
def insert_outline(
    *, company_id: int, project_id: int, revision: int, sha256: str, node_count: int, user_id: int
) -> int:
    row = DraftingOutline.for_company(company_id).create(
        company_id=company_id,
        project_id=project_id,
        revision=revision,
        sha256=sha256,
        node_count=node_count,
        created_by_user_id=user_id,
    )
    return row.id


@transaction.atomic
def insert_nodes(*, company_id: int, outline_id: int, nodes: Sequence[Mapping[str, Any]]) -> None:
    # 행마다 create(마디 ≤ 300) — 회사 모델의 생성자 호출은 제품 코드에 두지 않는다(core/tests/isolation 의 규칙)
    for position, node in enumerate(nodes):
        DraftingOutlineNode.for_company(company_id).create(
            company_id=company_id,
            outline_id=outline_id,
            key=node["key"],
            parent_key=node["parentKey"] or "",
            depth=node["depth"],
            position=position,
            title=node["title"],
            requirement=node["requirement"],
        )
