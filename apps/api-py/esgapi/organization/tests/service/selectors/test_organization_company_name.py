"""company_name(밴드 OP1 Q7): 회사 id 로 회사 이름 — 그린워싱 점검 목록의 companyName(운영 관리자에게는 회사 행이 없다).
업무 층. 없는 id 면 빈 글자."""

import pytest

from esgapi.organization.service.selectors.organization import CompanyActive, company_name, find_company

pytestmark = pytest.mark.django_db


def test_the_name_of_the_company_and_empty_for_none(tenants: None) -> None:
    found = find_company("tenant-a")
    assert isinstance(found, CompanyActive), found
    assert company_name(found.company.id) == "가 회사"
    assert company_name(found.company.id + 1_000_000) == ""
