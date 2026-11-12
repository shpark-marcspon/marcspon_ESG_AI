"""교환이 회사의 경계와 만나는 자리. 보안 층: Django 의 연결은 앱 역할(esg_app)이다.

사용자 행의 조회는 토큰의 회사로 연다(User.for_company). 다른 회사에 같은 sub 의 행이 있어도 보지 않고, 이 회사의
별개 사용자로 만든다(처분 2 ㉡ — 조건부 UNIQUE 는 회사 안에서만 username 을 가른다). 남의 행은 그대로다.
토큰의 tenant_id 는 회사의 subdomain 이고, 쓸 수 있는 회사(is_active)일 때만 통한다.
교환의 나머지 갈래(401·403·upsert·쿠키)는 업무 층이 잰다(esgapi/user/tests).
"""

from typing import Any

import psycopg
import pytest
from django.test import Client

from tests.support import tokens
from tests.support.http import login

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]


def test_user_already_in_another_tenant_is_its_own_user(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """A 에 있는 sub 로 B 에 교환하면 B 의 별개 사용자가 생긴다(200). A 의 행은 옮겨지지도 덮이지도 않는다."""
    a, b = companies
    login(client, sub="edk-user-1", tenant_id="tenant-a", name="김담당", role="editor")
    response = Client().post(
        "/api/auth/exchange",
        data={"token": tokens.edk_token(sub="edk-user-1", tenant_id="tenant-b", name="나관리", role="admin")},
        content_type="application/json",
    )
    assert response.status_code == 200, response.content.decode()
    assert response.json()["tenant"]["id"] == "tenant-b"
    # 분모: 주인이 센 그 username 의 행 전부 — 회사마다 하나씩 둘.
    rows = owner.execute(
        "SELECT company_id, kind, name, level FROM users WHERE username = %s ORDER BY company_id = %s DESC",
        ["edk-user-1", a],
    ).fetchall()
    assert rows == [(a, "service", "김담당", 79), (b, "service", "나관리", 99)]


def test_exchange_for_an_inactive_company_is_403(owner: Owner, companies: tuple[int, int]) -> None:
    """등록됐어도 쓸 수 없는 회사(is_active = false)면 없는 회사와 같은 답이다 → 403 unknown_tenant. 사용자 행 0."""
    a, _ = companies
    owner.execute("UPDATE company SET is_active = false WHERE id = %s", [a])
    assert owner.execute("SELECT subdomain, is_active FROM company WHERE id = %s", [a]).fetchall() == [
        ("tenant-a", False)
    ]
    response = Client().post(
        "/api/auth/exchange",
        data={"token": tokens.edk_token(sub="edk-user-1", tenant_id="tenant-a")},
        content_type="application/json",
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNKNOWN_TENANT"
    assert owner.execute("SELECT count(*) FROM users").fetchone() == (0,)
