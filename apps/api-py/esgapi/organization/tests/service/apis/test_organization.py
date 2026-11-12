"""사업장의 경로(/sites)를 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다.

★ 이 층의 연결은 주인 역할이다. 행 수는 Site.unscoped 로 센다(분모). 회사 id 는 상수로 박지 않는다 —
  Company.by_subdomain 으로 읽는다(식별 열은 되돌림에 안 돌아간다).
"""

from typing import Any

import pytest
from django.test import Client

from esgapi.core.permissions import CUSTOMER, OPERATION_POLICY, OPERATOR
from esgapi.organization.models import Company, Site
from tests.support.http import login

pytestmark = pytest.mark.django_db


def company_id_of(subdomain: str) -> int:
    row = Company.by_subdomain(subdomain)
    assert row is not None, subdomain
    return row.pk


def post_site(client: Client, **body: Any) -> Any:
    return client.post("/api/sites", data=body, content_type="application/json")


def test_tenant_header_is_not_a_way_in(client: Client, tenants: None) -> None:
    """TS 뼈대의 X-Tenant-Id 같은 헤더를 보내도 세션이 생기지 않는다."""
    response = client.get("/api/sites", headers={"X-Tenant-Id": "tenant-a"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NO_SESSION"


# ── 권한(동작 → 필요한 것. 쿠키 세션은 역할과 무관하게 고객사 사용자 — K2a 가2) ─────────


def test_a_customer_cannot_create_a_site_when_the_cell_is_operator_only(
    client: Client, tenants: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    login(client, role="viewer")
    monkeypatch.setitem(OPERATION_POLICY, "accounts_sites_create", OPERATOR)
    response = post_site(client, name="공장")
    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "FORBIDDEN",
        "message": "이 일은 운영 관리자만 한다",
        "fields": None,
        "legacyCode": "forbidden",
    }
    assert Site.unscoped.count() == 0
    monkeypatch.setitem(OPERATION_POLICY, "accounts_sites_create", CUSTOMER)
    assert post_site(client, name="공장").status_code == 201  # 분모: 옮기기 전에는 viewer 세션도 만든다


@pytest.mark.parametrize("role", ["editor", "admin"])
def test_editor_and_admin_create_a_site_in_their_own_tenant(client: Client, tenants: None, role: str) -> None:
    login(client, role=role)
    response = post_site(client, name="공장", externalId="edk-site-9")
    assert response.status_code == 201
    assert response.json()["site"]["name"] == "공장"
    assert list(Site.unscoped.values_list("company_id", "name", "external_id")) == [
        (company_id_of("tenant-a"), "공장", "edk-site-9")
    ]


def test_site_body_cannot_carry_a_tenant(client: Client, tenants: None) -> None:
    login(client, role="editor")
    response = post_site(client, name="공장", tenantId="tenant-b")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert Site.unscoped.count() == 0
