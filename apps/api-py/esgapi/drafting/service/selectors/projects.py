"""읽기. 원고작성 프로젝트·달린 문서·목차 판(밴드 RP1 ①). 쓰지 않는다.

    project_head(company_id, project_id)        프로젝트 하나(연도·이름). 없거나 남의 회사면 None
    lock_project(company_id, project_id)        그 프로젝트 행을 FOR UPDATE(목차 판 번호 매김 — 변경 트랜잭션 안에서만.
                                                id·outline_revision 만 읽는다). 없거나 남의 회사면 None
    current_document(company_id, project_id)    지금 문서(가장 늦게 단 행). 없으면 None
    current_documents(company_id, project_ids)  current_document 의 묶음 꼴(프로젝트 id → 지금 문서 — 쿼리 하나, RPS1).
                                                문서 없는 프로젝트·남의 회사 id 는 열쇠가 없다
    current_outline(company_id, project_id)     지금 목차 판의 머리(가장 큰 revision). 없으면 None
    outline_at(company_id, outline_id)          목차 판 하나(마디째 — outline@1 정규형). 없거나 남의 회사면 None
    project_view(company_id, project_id)        GET 의 몸: 프로젝트 + 지금 문서 + 지금 목차(마디째). 없으면 None
    project_page(company_id, limit, offset)     목록 한 쪽(RP2d): 만든 시각 내림(같으면 id 내림) + 전부의 수. 쿼리 둘
                                                (셈 하나 + 쪽 하나 — 문서 있음은 EXISTS, 판 번호는 프로젝트 행의 칸,
                                                지금 목차 판 id 는 서브쿼리 — RPS1)

★ 조회마다 회사 조건을 적는다(<표>.for_company(company_id) — core/tests/test_selector_scope.py, MARC-ENT-487). 남의
  회사의 id 는 「없음」과 같다.
★ 잠금은 행 잠금(FOR UPDATE) 하나다 — 앱 역할의 칸 단위 UPDATE (outline_revision, updated_at) 가 그 권한이다(감독 처분
  10-29. advisory 잠금의 raw SQL 은 쓰지 않는다).
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from django.db.models import Exists, OuterRef, Subquery

from esgapi.drafting.models import DraftingOutline, DraftingOutlineNode, DraftingProject, DraftingProjectDocument


@dataclass(frozen=True, slots=True)
class ProjectHead:
    id: int
    year: int
    name: str
    created_by_user_id: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProjectLock:
    id: int
    outline_revision: int


@dataclass(frozen=True, slots=True)
class AttachedDocument:
    document_id: int
    kind: str
    attached_by_user_id: int
    attached_at: datetime


@dataclass(frozen=True, slots=True)
class OutlineHead:
    id: int
    project_id: int
    revision: int
    sha256: str
    node_count: int


@dataclass(frozen=True, slots=True)
class OutlineVersion(OutlineHead):
    outline: dict[str, Any]
    """drafting.outline@1 정규형(마디 position 차례)."""


@dataclass(frozen=True, slots=True)
class ProjectView:
    project: ProjectHead
    document: AttachedDocument | None
    outline: OutlineVersion | None


@dataclass(frozen=True, slots=True)
class ProjectListItem:
    id: int
    year: int
    name: str
    created_at: datetime
    has_document: bool
    outline_revision: int
    """마지막 목차 판 번호(0 = 목차 없음 — 표의 칸 그대로)."""
    outline_id: int | None
    """지금 목차 판 id(가장 큰 revision). 목차가 없으면 None."""


@dataclass(frozen=True, slots=True)
class ProjectPage:
    count: int
    projects: list[ProjectListItem]


def _head(row: DraftingOutline) -> OutlineHead:
    return OutlineHead(
        id=row.id, project_id=row.project_id, revision=row.revision, sha256=row.sha256, node_count=row.node_count
    )


def project_head(*, company_id: int, project_id: int) -> ProjectHead | None:
    row = DraftingProject.for_company(company_id).filter(id=project_id).first()
    if row is None:
        return None
    return ProjectHead(
        id=row.id,
        year=row.year,
        name=row.name,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
    )


def lock_project(*, company_id: int, project_id: int) -> ProjectLock | None:
    row = (
        DraftingProject.for_company(company_id)
        .filter(id=project_id)
        .only("id", "outline_revision")
        .select_for_update()
        .first()
    )
    return None if row is None else ProjectLock(id=row.id, outline_revision=row.outline_revision)


def current_document(*, company_id: int, project_id: int) -> AttachedDocument | None:
    row = DraftingProjectDocument.for_company(company_id).filter(project_id=project_id).order_by("-id").first()
    if row is None:
        return None
    return AttachedDocument(
        document_id=row.document_id,
        kind=row.kind,
        attached_by_user_id=row.attached_by_user_id,
        attached_at=row.created_at,
    )


def current_documents(*, company_id: int, project_ids: Collection[int]) -> dict[int, AttachedDocument]:
    """프로젝트들의 지금 문서(프로젝트 id → 가장 늦게 단 행). 쿼리 하나(project_ids 가 비면 0) — pg 의 DISTINCT ON.
    입력 길이의 상한은 부르는 쪽이 지킨다(목록 한 쪽)."""
    if not project_ids:
        return {}
    rows = (
        DraftingProjectDocument.for_company(company_id)
        .filter(project_id__in=project_ids)
        .order_by("project_id", "-id")
        .distinct("project_id")
    )
    return {
        row.project_id: AttachedDocument(
            document_id=row.document_id,
            kind=row.kind,
            attached_by_user_id=row.attached_by_user_id,
            attached_at=row.created_at,
        )
        for row in rows
    }


def current_outline(*, company_id: int, project_id: int) -> OutlineHead | None:
    row = DraftingOutline.for_company(company_id).filter(project_id=project_id).order_by("-revision").first()
    return None if row is None else _head(row)


def outline_at(*, company_id: int, outline_id: int) -> OutlineVersion | None:
    row = DraftingOutline.for_company(company_id).filter(id=outline_id).first()
    if row is None:
        return None
    nodes = DraftingOutlineNode.for_company(company_id).filter(outline_id=row.id).order_by("position")
    outline = {
        "nodes": [
            {
                "key": node.key,
                "parentKey": node.parent_key or None,
                "depth": node.depth,
                "title": node.title,
                "requirement": node.requirement,
            }
            for node in nodes
        ]
    }
    head = _head(row)
    return OutlineVersion(
        id=head.id,
        project_id=head.project_id,
        revision=head.revision,
        sha256=head.sha256,
        node_count=head.node_count,
        outline=outline,
    )


def project_view(*, company_id: int, project_id: int) -> ProjectView | None:
    project = project_head(company_id=company_id, project_id=project_id)
    if project is None:
        return None
    head = current_outline(company_id=company_id, project_id=project_id)
    return ProjectView(
        project=project,
        document=current_document(company_id=company_id, project_id=project_id),
        outline=None if head is None else outline_at(company_id=company_id, outline_id=head.id),
    )


def project_page(*, company_id: int, limit: int, offset: int) -> ProjectPage:
    projects = DraftingProject.for_company(company_id)
    documents = DraftingProjectDocument.for_company(company_id).filter(project_id=OuterRef("id"))
    outlines = DraftingOutline.for_company(company_id).filter(project_id=OuterRef("id")).order_by("-revision")
    rows = (
        projects.annotate(has_document=Exists(documents), outline_id=Subquery(outlines.values("id")[:1]))
        .order_by("-created_at", "-id")
        .only("id", "year", "name", "created_at", "outline_revision")[offset : offset + limit]
    )
    return ProjectPage(
        count=projects.count(),
        projects=[
            ProjectListItem(
                id=row.id,
                year=row.year,
                name=row.name,
                created_at=row.created_at,
                has_document=bool(cast("Any", row).has_document),  # annotate 칸(모델 타입에 없다)
                outline_revision=row.outline_revision,
                outline_id=cast("Any", row).outline_id,  # annotate 칸 — 목차 없으면 None
            )
            for row in rows
        ],
    )
