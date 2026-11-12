"""교환·세션의 경로(/auth/exchange·/auth/logout·/me)를 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다.

★ 이 층의 연결은 주인 역할이다(DB 에 RLS 는 없다 — 격리는 조회마다의 회사 조건과 core/isolation). 여기서는
  회사 경계를 재지 않는다(「A 의 세션이 B 의 것을 못 본다」, 연결 재사용, 앱 역할의 권한은 앱 역할로 붙는
  tests/security 가 잰다). 행 수는 <Model>.unscoped 로 센다. 그것이 실제 행 수(분모)다.
★ 회사 id 는 상수로 박지 않는다(식별 열은 되돌림에 안 돌아간다). organization 의 찾기(find_company)로 읽는다 —
  user 는 남의 models 를 import 하지 않는다(.importlinter 「나」). 회사의 행 수는 등록부의 unscoped 로 센다.
"""

import time
from typing import Any

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction
from django.test import Client

from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.models import User
from tests.support import keys, tokens
from tests.support.http import login

pytestmark = pytest.mark.django_db


def post_exchange(client: Client, token: str) -> Any:
    return client.post("/api/auth/exchange", data={"token": token}, content_type="application/json")


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive), found
    return found.company.id


def companies() -> Any:
    """회사 표의 unscoped 매니저(주인 역할로 센다). 남의 models 를 import 하지 않으려 등록부에서 꺼낸다."""
    return apps.get_model("organization", "Company")._meta.managers_map["unscoped"]


def test_unknown_tenant_is_403_and_nothing_is_created(client: Client, tenants: None) -> None:
    response = post_exchange(client, tokens.edk_token(tenant_id="tenant-zzz"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNKNOWN_TENANT"
    assert "esg_session" not in response.cookies
    # 회사도 사용자도 생기지 않았다.
    assert (companies().count(), User.unscoped.count()) == (2, 0)


def test_an_inactive_company_is_403_unknown_tenant(client: Client, tenants: None) -> None:
    """등록됐지만 쓸 수 없는(is_active 거짓) 회사로 교환하면 미등록과 같은 답이다. 사용자를 만들지 않는다."""
    companies().create(name="다 회사", business_licence_number="333-33-33333", subdomain="tenant-c")
    assert companies().filter(subdomain="tenant-c", is_active=False).count() == 1  # 정말 비활성이다
    response = post_exchange(client, tokens.edk_token(tenant_id="tenant-c"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNKNOWN_TENANT"
    assert "esg_session" not in response.cookies
    assert User.unscoped.count() == 0


def test_first_exchange_creates_the_user_and_sets_the_cookie(client: Client, tenants: None) -> None:
    body = login(client, sub="edk-user-1", name="김담당", role="editor")
    assert body["tenant"] == {"id": "tenant-a", "name": "가 회사"}
    assert body["role"] == "editor"
    assert body["user"]["name"] == "김담당"
    assert (body["user"]["issuer"], body["user"]["externalId"]) == (keys.ISSUER, "edk-user-1")
    assert "token" not in body and "session" not in body  # 세션은 본문에 싣지 않는다

    rows = list(User.unscoped.values_list("kind", "company_id", "username", "name", "level"))
    assert rows == [("service", company_id_of("tenant-a"), "edk-user-1", "김담당", 79)]

    cookie = client.cookies["esg_session"]
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"] == "Lax"
    assert cookie["path"] == "/"
    assert cookie["max-age"] == 3600


def test_second_exchange_upserts_name_and_role(client: Client, tenants: None) -> None:
    first = login(client, name="김담당", role="editor")
    second = login(client, name="김관리", role="admin")
    assert second["user"]["id"] == first["user"]["id"]  # 같은 사람
    assert (second["user"]["name"], second["role"]) == ("김관리", "admin")
    assert list(User.unscoped.values_list("name", "level")) == [("김관리", 99)]  # 행 수 그대로 1


def test_an_inactive_user_is_refused_and_not_overwritten(client: Client, tenants: None) -> None:
    """(CA·D3) 꺼진 사용자(is_active 거짓)는 교환으로 세션을 받지 못한다. 행의 이름·level 도 덮지 않는다."""
    login(client, sub="edk-user-1", name="김담당", role="editor")
    User.unscoped.filter(username="edk-user-1").update(is_active=False)
    client.cookies.clear()
    response = post_exchange(client, tokens.edk_token(sub="edk-user-1", name="김관리", role="admin"))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "USER_INACTIVE"
    assert "esg_session" not in response.cookies
    assert list(User.unscoped.values_list("name", "level", "is_active")) == [("김담당", 79, False)]


def test_an_exchange_does_not_take_over_a_password_user(client: Client, tenants: None) -> None:
    """(CA·D5) 같은 회사에 같은 username 의 비밀번호 사용자가 있으면 교환은 그 행을 덮지 않고 409 로 거절한다
    (EDK 토큰을 든 쪽이 비밀번호 사용자의 세션을 받지 못한다)."""
    from esgapi.user.service.services.user import create_customer_user
    from esgapi.user.service.utils.login import UserCreated

    created = create_customer_user(
        actor_kind="admin",
        company_id=company_id_of("tenant-a"),
        username="kim",
        name="김담당",
        password="Blue-Harbor-7310",
    )
    assert isinstance(created, UserCreated), created
    before = list(User.unscoped.values_list("name", "level", "password"))
    response = post_exchange(client, tokens.edk_token(sub="kim", name="침입자", role="admin"))
    assert (response.status_code, response.json()["error"]["code"]) == (409, "USERNAME_CONFLICT")
    assert "esg_session" not in response.cookies
    assert list(User.unscoped.values_list("name", "level", "password")) == before
    # 분모: 다른 username 이면 교환이 된다
    assert post_exchange(client, tokens.edk_token(sub="edk-user-1")).status_code == 200


def test_same_external_id_from_another_issuer_would_be_another_user(tenants: None) -> None:
    """(K1u-a 에서 다시 씀) 유니크는 (회사, username) 이다: 회사가 다르면 같은 username 을 쓸 수 있다.
    발급자 칸은 표에서 빠졌다(옛 users_issuer_external_id_uniq 자리)."""

    def insert(subdomain: str) -> None:
        User.for_company(company_id_of(subdomain)).create(
            kind="service", username="same-id", name="이름", level=79, password="!"
        )

    insert("tenant-a")
    insert("tenant-b")
    with pytest.raises(IntegrityError, match="users_company_username_uniq"), transaction.atomic():
        insert("tenant-b")
    assert User.unscoped.count() == 2


@pytest.mark.parametrize(
    ("make", "code"),
    [
        (lambda: tokens.edk_token(exp=int(time.time()) - 1), "EXPIRED"),
        (lambda: tokens.edk_token(key=keys.OTHER_KEY), "BAD_SIGNATURE"),
        (lambda: tokens.edk_token(aud="other"), "WRONG_AUDIENCE"),
        (lambda: tokens.edk_token(iss="https://evil.test"), "WRONG_ISSUER"),
        (lambda: tokens.alg_none_token(), "BAD_ALGORITHM"),
        (lambda: tokens.hs256_token(keys.EDK_PUBLIC_PEM.encode()), "BAD_ALGORITHM"),
        (lambda: tokens.edk_token(role="owner"), "BAD_CLAIMS"),
        (lambda: "garbage", "MALFORMED"),
    ],
)
def test_each_rejection_has_its_own_code_and_no_session(client: Client, tenants: None, make: Any, code: str) -> None:
    response = post_exchange(client, make())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == code
    assert "esg_session" not in response.cookies
    assert User.unscoped.count() == 0


def test_body_cannot_carry_tenant_or_user(client: Client, tenants: None) -> None:
    """본문에 tenantId 를 얹어 보내면 무시하지 않고 거절한다."""
    response = client.post(
        "/api/auth/exchange",
        data={"token": tokens.edk_token(tenant_id="tenant-a"), "tenantId": "tenant-b"},
        content_type="application/json",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert User.unscoped.count() == 0


def test_me_and_logout(client: Client, tenants: None) -> None:
    body = login(client, role="viewer")
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["userId"] == body["user"]["id"]
    assert (me.json()["tenantId"], me.json()["role"]) == ("tenant-a", "viewer")
    assert me.json()["companyId"] == company_id_of("tenant-a")  # 세션의 회사 = 교환한 회사

    out = client.post("/api/auth/logout")
    assert out.status_code == 204
    assert out.cookies["esg_session"].value == ""
    assert out.cookies["esg_session"]["max-age"] == 0
    assert client.get("/api/me").status_code == 401


def test_tampered_or_expired_cookie_is_401_with_its_own_code(client: Client, tenants: None) -> None:
    login(client)
    good = client.cookies["esg_session"].value
    client.cookies["esg_session"] = good[:-2] + ("AA" if not good.endswith("AA") else "BB")
    assert client.get("/api/me").json()["error"]["code"] == "SESSION_BAD_SIGNATURE"
    client.cookies["esg_session"] = "garbage"
    assert client.get("/api/me").json()["error"]["code"] == "SESSION_MALFORMED"
    client.cookies["esg_session"] = tokens.edk_token()  # EDK 토큰은 세션이 아니다
    assert client.get("/api/me").status_code == 401


def test_an_oversized_exchange_body_is_413_and_nothing_is_echoed(client: Client, tenants: None) -> None:
    """본문 상한(2.5MB)을 넘는 교환 요청. 세션이 없어도 닿는 경로라 여기서도 잰다. 받은 내용을 되돌리지 않는다."""
    response = post_exchange(client, "x" * (3 * 1024 * 1024))
    assert (response.status_code, response.json()["error"]["code"]) == (413, "BODY_TOO_LARGE")
    assert "xxx" not in response.content.decode()
    assert "esg_session" not in response.cookies
    assert User.unscoped.count() == 0


def test_unknown_path_is_404_in_the_one_error_shape(client: Client) -> None:
    response = client.get("/api/healthz/nope")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "그런 경로가 없다", "fields": None, "legacyCode": "not_found"}
    }
