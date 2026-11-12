"""원고작성 프로젝트·문서 달기·목차 판의 쓰기(service/services/projects.py — 밴드 RP1 §3 S2. 목차 판의 묶음
put_outline 은 ③ R1 로 service/actions/projects.py 에 옮김 — 표마다 쓰는 services 를 그 묶음으로 잰다).
업무 층: 진짜 DB.

    put_outline  같은 sha 두 번 → 판 하나(쓰기 0) · 다른 sha → revision 2, 판 1 그대로(마디째) · 없는·남의 프로젝트 →
                 ProjectMissing(행 0) · 프로젝트의 outline_revision 이 판 번호를 따라간다
    attach       새 행(지금 = 가장 늦은 행) · 남의 프로젝트 → ProjectMissing(행 0)
글은 지어낸 것이다."""

from typing import Any

import pytest

from esgapi.drafting.contracts.wire import accept_outline, outline_sha256
from esgapi.drafting.models import DraftingOutline, DraftingOutlineNode, DraftingProject, DraftingProjectDocument
from esgapi.drafting.service.actions import projects as actions
from esgapi.drafting.service.selectors import projects as selectors
from esgapi.drafting.service.services import projects as services

pytestmark = pytest.mark.django_db
USER = 3


def tree(*titles: str) -> dict[str, Any]:
    nodes = [{"key": "top", "parentKey": None, "depth": 1, "title": "환경", "requirement": ""}]
    nodes += [
        {"key": f"leaf-{i}", "parentKey": "top", "depth": 2, "title": t, "requirement": f"요구 {i}"}
        for i, t in enumerate(titles)
    ]
    return dict(accept_outline({"nodes": nodes}))


def new_project(company_id: int) -> int:
    return services.create_project(company_id=company_id, year=2025, name="가상 보고서", user_id=USER)


def test_the_same_outline_twice_is_one_version(companies: tuple[int, int]) -> None:
    a, _ = companies
    p = new_project(a)
    first = actions.put_outline(company_id=a, project_id=p, outline=tree("배출"), user_id=USER)
    again = actions.put_outline(company_id=a, project_id=p, outline=tree("배출"), user_id=USER)
    assert isinstance(first, actions.OutlinePut) and isinstance(again, actions.OutlinePut)
    assert (first.revision, first.created, again.created) == (1, True, False)
    assert again.outline_id == first.outline_id and again.sha256 == outline_sha256(tree("배출"))
    assert DraftingOutline.for_company(a).count() == 1
    assert DraftingOutlineNode.for_company(a).count() == 2


def test_a_new_outline_is_revision_2_and_revision_1_stays(companies: tuple[int, int]) -> None:
    a, _ = companies
    p = new_project(a)
    first = actions.put_outline(company_id=a, project_id=p, outline=tree("배출"), user_id=USER)
    second = actions.put_outline(company_id=a, project_id=p, outline=tree("배출", "에너지"), user_id=USER)
    assert isinstance(first, actions.OutlinePut) and isinstance(second, actions.OutlinePut)
    assert second.revision == 2 and second.created
    old = selectors.outline_at(company_id=a, outline_id=first.outline_id)
    assert old is not None and old.outline == tree("배출") and old.revision == 1
    new = selectors.outline_at(company_id=a, outline_id=second.outline_id)
    assert new is not None and new.outline == tree("배출", "에너지") and new.node_count == 3
    assert DraftingProject.for_company(a).get(id=p).outline_revision == 2
    head = selectors.current_outline(company_id=a, project_id=p)
    assert head is not None and head.id == second.outline_id
    # 옛 판으로 되돌아가도 새 판(revision 3) — 판은 sha 가 아니라 「지금 판」과 견준다
    third = actions.put_outline(company_id=a, project_id=p, outline=tree("배출"), user_id=USER)
    assert isinstance(third, actions.OutlinePut) and third.revision == 3


def test_another_company_project_is_missing(companies: tuple[int, int]) -> None:
    a, b = companies
    p = new_project(a)
    assert actions.put_outline(company_id=b, project_id=p, outline=tree("배출"), user_id=USER) == (
        services.ProjectMissing()
    )
    assert actions.put_outline(company_id=a, project_id=p + 999, outline=tree("배출"), user_id=USER) == (
        services.ProjectMissing()
    )
    assert services.attach_document(company_id=b, project_id=p, document_id=1, user_id=USER) == (
        services.ProjectMissing()
    )
    assert DraftingOutline.for_company(b).count() == 0 and DraftingProjectDocument.for_company(b).count() == 0
    assert selectors.project_view(company_id=b, project_id=p) is None


def test_attaching_again_is_a_new_row_and_the_latest_is_current(companies: tuple[int, int]) -> None:
    a, _ = companies
    p = new_project(a)
    view = selectors.project_view(company_id=a, project_id=p)
    assert view is not None and view.document is None and view.outline is None
    services.attach_document(company_id=a, project_id=p, document_id=11, user_id=USER)
    services.attach_document(company_id=a, project_id=p, document_id=12, user_id=USER)
    assert DraftingProjectDocument.for_company(a).count() == 2
    current = selectors.current_document(company_id=a, project_id=p)
    assert current is not None and (current.document_id, current.kind) == (12, "prior_report")
    actions.put_outline(company_id=a, project_id=p, outline=tree("배출"), user_id=USER)
    view = selectors.project_view(company_id=a, project_id=p)
    assert view is not None and view.outline is not None and view.outline.outline == tree("배출")
    assert (view.project.year, view.project.name) == (2025, "가상 보고서")


def test_two_projects_of_one_company_do_not_see_each_other(companies: tuple[int, int]) -> None:
    """지금 문서·지금 목차는 그 프로젝트의 행만 집는다(검증 B1 — 회사 조건만으로는 남의 프로젝트 행이 섞인다)."""
    a, _ = companies
    p1, p2 = new_project(a), new_project(a)
    services.attach_document(company_id=a, project_id=p1, document_id=21, user_id=USER)
    first = actions.put_outline(company_id=a, project_id=p1, outline=tree("배출"), user_id=USER)
    assert isinstance(first, actions.OutlinePut)
    assert selectors.current_document(company_id=a, project_id=p2) is None
    assert selectors.current_outline(company_id=a, project_id=p2) is None
    view = selectors.project_view(company_id=a, project_id=p2)
    assert view is not None and view.document is None and view.outline is None
    services.attach_document(company_id=a, project_id=p2, document_id=22, user_id=USER)
    second = actions.put_outline(company_id=a, project_id=p2, outline=tree("배출", "에너지"), user_id=USER)
    assert isinstance(second, actions.OutlinePut) and second.revision == 1  # 판 번호는 프로젝트마다
    current = selectors.current_document(company_id=a, project_id=p1)
    assert current is not None and current.document_id == 21
    head = selectors.current_outline(company_id=a, project_id=p1)
    assert head is not None and head.id == first.outline_id
