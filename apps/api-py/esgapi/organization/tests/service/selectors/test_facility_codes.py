"""코드 목록 selectors 의 사업장 쓰임 판정(밴드 S12S1 Q9 — 7a 허락 ②). 업무 층.

codes_on_site_facilities = 이름 붙은 입구 SiteFacility.used_code_ids 그대로(코드 id 만) · 자리 함수
facility_codes_in_use(관리자 화면 inUse·409)는 여전히 빈 집합이다(이 밴드 0줄). 사업장·코드는 services 로 짓는다.
이름은 지어낸 것이다.
"""

import pytest

from esgapi.inventory.service.selectors.entries import facilities_in_use
from esgapi.organization.service.selectors.facility_codes import codes_on_site_facilities, facility_codes_in_use
from esgapi.organization.service.services.branches import FacilityRow, insert_site_row, save_facilities
from esgapi.organization.service.services.facility_codes import create_code
from esgapi.organization.service.utils.entities import Branch, FacilityCodeInfo

pytestmark = pytest.mark.django_db


def made_code(name: str) -> int:
    made = create_code(actor_kind="admin", name=name)
    assert isinstance(made, FacilityCodeInfo), made
    return made.id


def test_codes_on_site_facilities_sees_every_company_and_the_placeholder_stays_empty(
    companies: tuple[int, int],
) -> None:
    a, b = companies
    used, other, idle = made_code("지어낸 설비 가"), made_code("지어낸 설비 나"), made_code("지어낸 설비 다")
    for company_id, code_id in ((a, used), (b, other)):
        branch = insert_site_row(company_id, name="지어낸 공장", inventory_enabled=True)
        assert isinstance(branch, Branch), branch
        rows = [FacilityRow(facility_code_id=code_id, detail_name="지어낸 세부")]
        assert save_facilities(company_id, branch.id, rows=rows, facilities_in_use=facilities_in_use) is None
    assert codes_on_site_facilities([used, other, idle]) == frozenset({used, other})
    assert facility_codes_in_use([used, other, idle]) == frozenset()  # 자리 함수 그대로(관리자 화면 길 밖)
