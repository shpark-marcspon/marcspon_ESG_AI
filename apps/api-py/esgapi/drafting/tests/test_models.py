# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""원고작성 표 넷의 제약(models.py · migrations/0001_initial.py — 밴드 RP1 §3 S2). 업무 층: 진짜 DB(주인 역할 —
앱 역할의 GRANT 는 보안 층 tests/security 가 잰다). CHECK·unique 하나씩, 같은 회사 복합 외래 키(남의 회사 행을
가리키면 23503). 글은 지어낸 것이다."""

from collections.abc import Callable
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from esgapi.drafting.models import DraftingOutline, DraftingOutlineNode, DraftingProject, DraftingProjectDocument

pytestmark = pytest.mark.django_db
SHA = "a" * 64


def project(company_id: int, **changes: Any) -> DraftingProject:
    fields: dict[str, Any] = {"company_id": company_id, "year": 2025, "name": "가상 보고서", "created_by_user_id": 1}
    return DraftingProject.for_company(company_id).create(**(fields | changes))


def outline(company_id: int, project_id: int, **changes: Any) -> DraftingOutline:
    fields: dict[str, Any] = {
        "company_id": company_id,
        "project_id": project_id,
        "revision": 1,
        "sha256": SHA,
        "node_count": 1,
        "created_by_user_id": 1,
    }
    return DraftingOutline.for_company(company_id).create(**(fields | changes))


def node(company_id: int, outline_id: int, **changes: Any) -> DraftingOutlineNode:
    fields: dict[str, Any] = {
        "company_id": company_id,
        "outline_id": outline_id,
        "key": "a",
        "parent_key": "",
        "depth": 1,
        "position": 0,
        "title": "환경",
        "requirement": "",
    }
    return DraftingOutlineNode.for_company(company_id).create(**(fields | changes))


def refused(make: Callable[[], object], name: str) -> None:
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        make()
    assert name in str(caught.value)


def test_project_checks(companies: tuple[int, int]) -> None:
    a, _ = companies
    project(a, year=2000)
    project(a, year=2100, name="가" * 80)
    refused(lambda: project(a, year=1999), "drafting_projects_year_range")
    refused(lambda: project(a, year=2101), "drafting_projects_year_range")
    refused(lambda: project(a, name=""), "drafting_projects_name_length")
    refused(lambda: project(a, outline_revision=-1), "drafting_projects_outline_revision_range")


def test_document_kind_check(companies: tuple[int, int]) -> None:
    a, _ = companies
    p = project(a)

    def attach(kind: str) -> object:
        return DraftingProjectDocument.for_company(a).create(
            company_id=a, project_id=p.id, document_id=5, kind=kind, attached_by_user_id=1
        )

    attach("prior_report")
    refused(lambda: attach("other"), "drafting_project_documents_kind")


def test_outline_checks_and_revision_unique(companies: tuple[int, int]) -> None:
    a, _ = companies
    p = project(a)
    outline(a, p.id)
    outline(a, p.id, revision=2, node_count=300)
    refused(lambda: outline(a, p.id), "drafting_outlines_project_revision_unique")
    refused(lambda: outline(a, p.id, revision=0), "drafting_outlines_revision_range")
    refused(lambda: outline(a, p.id, revision=3, sha256="A" * 64), "drafting_outlines_sha256")
    refused(lambda: outline(a, p.id, revision=3, node_count=0), "drafting_outlines_node_count")
    refused(lambda: outline(a, p.id, revision=3, node_count=301), "drafting_outlines_node_count")


def test_node_checks_and_uniques(companies: tuple[int, int]) -> None:
    a, _ = companies
    o = outline(a, project(a).id)
    node(a, o.id, title="가" * 200, requirement="나" * 2000)
    node(a, o.id, key="b", position=1, depth=4)
    refused(lambda: node(a, o.id, position=9), "drafting_outline_nodes_key_unique")
    refused(lambda: node(a, o.id, key="c", position=1), "drafting_outline_nodes_position_unique")
    refused(lambda: node(a, o.id, key="c", position=2, depth=0), "drafting_outline_nodes_depth_range")
    refused(lambda: node(a, o.id, key="c", position=2, depth=5), "drafting_outline_nodes_depth_range")
    refused(lambda: node(a, o.id, key="c", position=-1), "drafting_outline_nodes_position_range")
    refused(lambda: node(a, o.id, key="c", position=2, title=""), "drafting_outline_nodes_title_length")
    refused(lambda: node(a, o.id, key="c", position=2, requirement="나" * 2001), "drafting_outline_nodes_requirement")


def test_rows_of_another_company_cannot_be_pointed_at(companies: tuple[int, int]) -> None:
    a, b = companies
    p = project(a)
    o = outline(a, p.id)
    refused(lambda: outline(b, p.id), "drafting_outlines_project_id_same_company_fk")
    refused(
        lambda: DraftingProjectDocument.for_company(b).create(
            company_id=b, project_id=p.id, document_id=5, kind="prior_report", attached_by_user_id=1
        ),
        "drafting_project_documents_project_id_same_company_fk",
    )
    refused(lambda: node(b, o.id), "drafting_outline_nodes_outline_id_same_company_fk")
