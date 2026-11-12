"""회사 찾기(find_company — 교환과 seed_company 의 입구)의 갈래, 사업장 조회의 회사 조건(업무 층)."""

import re
from datetime import UTC, datetime

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.auth.principal import principal_of_session
from esgapi.core.tenancy.session import Session
from esgapi.organization.models import Company, Site
from esgapi.organization.service.selectors.organization import SiteList, all_sites, find_company, list_sites
from esgapi.organization.service.utils.entities import CompanyActive, CompanyInactive, CompanyInfo, CompanyUnknown
from tests.support.http import login

pytestmark = pytest.mark.django_db


def test_an_active_company_is_found_with_its_id() -> None:
    row = Company.register(name="가 회사", business_licence_number="111-11-11111", subdomain="tenant-a")
    assert find_company("tenant-a") == CompanyActive(
        CompanyInfo(
            id=row.pk, name="가 회사", subdomain="tenant-a", business_licence_number="111-11-11111", is_active=True
        )
    )


def test_an_inactive_company_is_its_own_branch() -> None:
    row = Company.unscoped.create(name="나 회사", business_licence_number="222-22-22222", subdomain="tenant-b")
    found = find_company("tenant-b")
    assert isinstance(found, CompanyInactive)
    assert found.company.id == row.pk


def test_an_unknown_subdomain_is_unknown() -> None:
    Company.register(name="가 회사", business_licence_number="111-11-11111", subdomain="tenant-a")
    assert find_company("tenant-x") == CompanyUnknown()


# ── 사업장의 회사 조건(옛 accounts 의 test_selectors_tenant) ───────────────────────────
# 주인 역할의 연결에서도 남의 사업장이 안 나오는가(RLS 는 없다).
# ★ 무효 조건: 이 층은 파이썬 쪽 조건만 잰다(Site.for_company 의 company_id 조건). 앱 역할 연결의 경계는 보안 층이 잰다.
# ★ SQL 의 글자를 보는 테스트는 Django 가 내는 문의 꼴(`"sites"."company_id" = 값`)에 기댄다.

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
A_SITES = ["A 본사", "A 공장"]
B_SITES = ["B 본사", "B 공장", "B 창고"]


def company_id_of(subdomain: str) -> int:
    row = Company.by_subdomain(subdomain)
    assert row is not None, subdomain
    return row.pk


@pytest.fixture
def sites(tenants: None) -> tuple[int, int]:
    """두 회사의 사업장 다섯(A 둘, B 셋). 회사 id 둘을 돌려준다."""
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    for name in A_SITES:
        Site.for_company(a).create(name=name)
    for name in B_SITES:
        Site.for_company(b).create(name=name)
    return a, b


def test_all_sites_gives_one_tenants_sites_without_rls(sites: tuple[int, int]) -> None:
    a, b = sites
    assert Site.unscoped.count() == 5  # 분모: unscoped 에는 다섯 행이 다 보인다
    assert [site.name for site in all_sites(a)] == A_SITES
    assert {site.company_id for site in all_sites(a)} == {a}
    assert [site.name for site in all_sites(b)] == B_SITES
    neighbours = sorted(n for n in {a - 1, a + 1, b - 1, b + 1} - {a, b} if n > 0)  # 이웃 id(±1)
    assert neighbours
    for neighbour in neighbours:
        assert all_sites(neighbour) == [], neighbour

    session = principal_of_session(
        Session(user_id="user-1", tenant_id="tenant-a", company_id=a, role="viewer", expires_at=NOW)
    )
    listed = list_sites(session)
    assert isinstance(listed, SiteList) and [site.name for site in listed.sites] == A_SITES


def test_the_sites_route_shows_only_the_sessions_tenant_without_rls(client: Client, sites: tuple[int, int]) -> None:
    login(client, tenant_id="tenant-a")
    response = client.get("/api/sites")
    assert response.status_code == 200
    assert [site["name"] for site in response.json()["sites"]] == A_SITES
    assert Site.unscoped.count() == 5  # 분모

    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    assert [site["name"] for site in other.get("/api/sites").json()["sites"]] == B_SITES


def test_the_sites_query_names_the_tenant(client: Client, sites: tuple[int, int]) -> None:
    """`GET /sites` 가 sites 표에 낸 문에 회사 조건이 있다. 무효 조건: 글자만 봤다."""
    a, _ = sites
    login(client, tenant_id="tenant-a")
    with CaptureQueriesContext(connection) as captured:
        assert client.get("/api/sites").status_code == 200
    statements = [query["sql"] for query in captured.captured_queries if 'FROM "sites"' in query["sql"]]
    assert len(statements) == 1, statements  # 분모: sites 를 읽는 문 하나
    assert re.search(rf'"sites"\."company_id" = {a}\b', statements[0]), statements[0]
