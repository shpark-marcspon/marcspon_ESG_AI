"""회사 표(company)의 제약과 뿌리 매니저의 입구(업무 층, 주인 역할 연결).

회사 id 를 상수로 박지 않는다: 식별 열은 되돌림에 안 돌아간다(테스트마다 값이 다르다).
"""

import pytest
from django.db import IntegrityError, transaction

from esgapi.core.isolation.managers import UnscopedQueryError
from esgapi.organization.models import Company

pytestmark = pytest.mark.django_db


def company(subdomain: str, licence: str) -> Company:
    return Company.register(name=f"{subdomain} 회사", business_licence_number=licence, subdomain=subdomain)


def test_register_makes_an_active_company() -> None:
    made = company("tenant-a", "111-11-11111")
    assert (made.pk > 0, made.is_active, made.subdomain) == (True, True, "tenant-a")
    assert Company.unscoped.count() == 1


def test_a_new_row_is_inactive_by_default() -> None:
    row = Company.unscoped.create(name="가", business_licence_number="111-11-11111", subdomain="tenant-a")
    assert row.is_active is False


@pytest.mark.parametrize("subdomain", ["Tenant-A", "-tenant", "tenant_a", "a" * 64, ""])
def test_a_subdomain_out_of_form_is_refused_by_the_db(subdomain: str) -> None:
    with pytest.raises(IntegrityError, match="company_subdomain_format"), transaction.atomic():
        company(subdomain, "111-11-11111")
    assert Company.unscoped.count() == 0


def test_a_licence_number_or_subdomain_is_unique() -> None:
    company("tenant-a", "111-11-11111")
    with pytest.raises(IntegrityError), transaction.atomic():
        company("tenant-b", "111-11-11111")
    with pytest.raises(IntegrityError), transaction.atomic():
        company("tenant-a", "222-22-22222")
    assert Company.unscoped.count() == 1


def test_for_company_opens_only_that_row() -> None:
    a = company("tenant-a", "111-11-11111")
    b = company("tenant-b", "222-22-22222")
    assert Company.unscoped.count() == 2  # 분모
    assert list(Company.for_company(a.pk)) == [a]
    assert list(Company.for_company(b.pk)) == [b]
    assert list(Company.for_company(max(a.pk, b.pk) + 1)) == []


def test_by_subdomain_finds_one_row_active_or_not() -> None:
    a = company("tenant-a", "111-11-11111")
    inactive = Company.unscoped.create(name="나", business_licence_number="222-22-22222", subdomain="tenant-b")
    assert Company.by_subdomain("tenant-a") == a
    assert Company.by_subdomain("tenant-b") == inactive
    assert Company.by_subdomain("tenant-c") is None
    with pytest.raises(UnscopedQueryError):
        Company.by_subdomain("")
