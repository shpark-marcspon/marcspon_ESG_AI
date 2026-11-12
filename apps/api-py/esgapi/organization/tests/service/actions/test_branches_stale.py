"""save_branch 의 낡은 판 거절(밴드 K1b-3 ① — 발주서 2-2·3-1 · sid:MARC-ISSUE-427). 업무 층(진짜 DB, 주인 역할, 롤백).

판(seen_at)은 잠근 행의 updated_at 과 견준다 — 다르면 Stale 이고 아무것도 쓰지 않는다. 경로 층의 409·422 는
service/apis/test_branches.py 의 「낡은 판 거절」 절, 진짜 두 연결의 경합은 test_branches_save_race.py(②).
이름·글은 지어낸 것이다.
"""

import dataclasses
import inspect
from datetime import timedelta

import pytest

from esgapi.organization.models import Company, FacilityCode, Site, SiteFacility
from esgapi.organization.service.actions import branches as actions
from esgapi.organization.service.services.branches import FacilityRow

pytestmark = pytest.mark.django_db


@pytest.fixture
def company_id() -> int:
    return Company.register(name="가 회사", business_licence_number="111-11-11111", subdomain="tenant-a").pk


def facts(site: Site) -> tuple[object, ...]:
    row = Site.unscoped.values_list("name", "inventory_enabled", "updated_at").get(pk=site.pk)
    lines = tuple(SiteFacility.unscoped.filter(site_id=site.pk).values_list("id", "detail_name", "deleted_at"))
    return (*row, lines)


def test_the_version_is_a_required_keyword() -> None:
    """seen_at 은 기본값 없는 키워드 — 빠뜨린 부름이 조용히 견줌을 건너뛰지 않는다."""
    seen_at = inspect.signature(actions.save_branch).parameters["seen_at"]
    assert seen_at.kind is inspect.Parameter.KEYWORD_ONLY
    assert seen_at.default is inspect.Parameter.empty
    assert dataclasses.fields(actions.Stale) == ()  # 지금 판을 싣지 않는다(웹이 GET 으로 다시 읽음 — 판단 1)


def test_an_old_version_is_stale_and_writes_nothing(company_id: int) -> None:
    code = FacilityCode.objects.create(name="보일러", code="F0001").pk
    site = Site.for_company(company_id).create(name="가 공장")
    line = SiteFacility.for_company(company_id).create(site=site, facility_code_id=code, detail_name="1호기")
    seen = Site.unscoped.get(pk=site.pk).updated_at
    before = facts(site)
    for wrong in (seen - timedelta(microseconds=1), seen + timedelta(microseconds=1)):
        found = actions.save_branch(
            company_id, site.pk, seen_at=wrong, name="나 공장", inventory_enabled=False, facilities=[]
        )
        assert found == actions.Stale(), wrong
        assert facts(site) == before  # 이름·인벤토리·updated_at·줄(1호기 지움 0) 그대로
    kept = [FacilityRow(code, "1호기", id=line.pk)]
    saved = actions.save_branch(
        company_id, site.pk, seen_at=seen, name="나 공장", inventory_enabled=True, facilities=kept
    )
    assert not isinstance(saved, actions.SaveRefused), saved
    assert saved.branch.updated_at > seen  # 고친 뒤의 판(PUT 응답이 싣는 값)
    assert saved.branch.updated_at == Site.unscoped.get(pk=site.pk).updated_at


def test_a_missing_branch_is_not_found_before_the_version(company_id: int) -> None:
    """없는·남의 사업장은 판을 보지 않고 NotFound(404 — 판으로 있음이 새지 않는다)."""
    other = Company.register(name="나 회사", business_licence_number="222-22-22222", subdomain="tenant-b").pk
    theirs = Site.for_company(other).create(name="나 공장")
    seen = Site.unscoped.get(pk=theirs.pk).updated_at
    found = actions.save_branch(company_id, theirs.pk, seen_at=seen, name="x", inventory_enabled=True, facilities=[])
    assert found == actions.NotFound()
