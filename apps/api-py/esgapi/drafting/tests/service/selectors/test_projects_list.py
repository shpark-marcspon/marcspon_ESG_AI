"""목록 읽기(service/selectors/projects.project_page — 밴드 RP2d). 업무 층: 진짜 DB.

    L1  만든 시각 내림 · 같은 시각이면 id 내림 · 문서 있음(EXISTS) · 판 번호(0 = 목차 없음) · 남의 회사 0
    L2  쪽 자름(limit·offset)과 전부의 수
    L3  쿼리 수는 프로젝트 수와 무관하게 둘(셈 하나 + 쪽 하나 — N+1 0)
글은 지어낸 것이다."""

from datetime import UTC, datetime

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from esgapi.drafting.contracts.wire import accept_outline
from esgapi.drafting.models import DraftingProject
from esgapi.drafting.service.actions import projects as actions
from esgapi.drafting.service.selectors import projects as selectors
from esgapi.drafting.service.services import projects as services

pytestmark = pytest.mark.django_db
USER = 3
OUTLINE = accept_outline({"nodes": [{"key": "top", "parentKey": None, "depth": 1, "title": "환경", "requirement": ""}]})


def new_project(company_id: int, name: str, *, document: bool = False, outlines: int = 0) -> int:
    project_id = services.create_project(company_id=company_id, year=2025, name=name, user_id=USER)
    if document:
        attached = services.attach_document(company_id=company_id, project_id=project_id, document_id=1, user_id=USER)
        assert isinstance(attached, int)
    for revision in range(outlines):
        nodes = [{**OUTLINE["nodes"][0], "title": f"환경 {revision}"}]
        put = actions.put_outline(company_id=company_id, project_id=project_id, outline={"nodes": nodes}, user_id=USER)
        assert isinstance(put, actions.OutlinePut)
    return project_id


def stamp(company_id: int, project_id: int, at: datetime) -> None:
    DraftingProject.for_company(company_id).filter(id=project_id).update(created_at=at)


def rows(page: selectors.ProjectPage) -> list[tuple[str, bool, int]]:
    return [(item.name, item.has_document, item.outline_revision) for item in page.projects]


def test_l1_newest_first_ties_by_id_with_document_and_revision(companies: tuple[int, int]) -> None:
    a, b = companies
    old = new_project(a, "가상 옛것", document=True, outlines=2)
    tie_low = new_project(a, "가상 같은 시각 하나")
    tie_high = new_project(a, "가상 같은 시각 둘", outlines=1)
    new_project(b, "가상 남의 것", document=True)
    stamp(a, old, datetime(2026, 1, 1, tzinfo=UTC))
    stamp(a, tie_low, datetime(2026, 3, 1, tzinfo=UTC))
    stamp(a, tie_high, datetime(2026, 3, 1, tzinfo=UTC))
    page = selectors.project_page(company_id=a, limit=20, offset=0)
    assert page.count == 3
    assert rows(page) == [("가상 같은 시각 둘", False, 1), ("가상 같은 시각 하나", False, 0), ("가상 옛것", True, 2)]
    assert page.projects[0].created_at == datetime(2026, 3, 1, tzinfo=UTC)
    assert rows(selectors.project_page(company_id=b, limit=20, offset=0)) == [("가상 남의 것", True, 0)]


def test_l2_limit_and_offset_cut_the_page_and_count_is_all(companies: tuple[int, int]) -> None:
    a, _ = companies
    for i in range(5):
        stamp(a, new_project(a, f"가상 {i}"), datetime(2026, 1, 1 + i, tzinfo=UTC))
    page = selectors.project_page(company_id=a, limit=2, offset=1)
    assert (page.count, [item.name for item in page.projects]) == (5, ["가상 3", "가상 2"])
    assert selectors.project_page(company_id=a, limit=2, offset=5).projects == []


@pytest.mark.parametrize("projects", [1, 6])
def test_l3_two_queries_whatever_the_number_of_projects(companies: tuple[int, int], projects: int) -> None:
    a, _ = companies
    for i in range(projects):
        new_project(a, f"가상 {i}", document=i % 2 == 0, outlines=1)
    with CaptureQueriesContext(connection) as seen:
        page = selectors.project_page(company_id=a, limit=20, offset=0)
    assert len(page.projects) == projects
    assert len(seen.captured_queries) == 2
