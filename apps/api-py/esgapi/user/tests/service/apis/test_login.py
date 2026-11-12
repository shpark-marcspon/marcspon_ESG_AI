"""로그인·refresh·revoke 와 자기 계정(/users/me·비밀번호 바꾸기)의 경로를 HTTP 로 잰다(K2a). 업무 층.

해시는 MD5 로 바꿔 빠르게 돈다(이 파일의 autouse 고정물 — 제품 설정은 그대로다).
회사 id 는 상수로 박지 않는다 — tenants 고정물이 심고 organization 의 찾기(find_company)로 읽는다.
★ 회사 경로(/sites·/documents …)는 K2a 에서 쿠키만 받는다(Bearer 는 K2b). 그래서 is_initial 의 403
  password_change_required 는 순수 층(core/tests/auth/test_bearer.py)이 잰다.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from django.test import Client, override_settings

from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config
from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.models import User
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair, login

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
NEW_PASSWORD = "Green-Valley-4821"
WRONG = "Wrong-Lantern-5932"
PAIR_KEYS = {"access", "refresh", "accessExpiresAt", "refreshExpiresAt", "isInitial", "kind"}


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive), found
    return found.company.id


def customer(subdomain: str = "tenant-a", username: str = "kim") -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id_of(subdomain), username=username, name="김담당", password=PASSWORD
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def operator(username: str = "ops") -> int:
    created = create_operator(username=username, name="운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    return created.user_id


def post(client: Client, path: str, body: dict[str, Any], **headers: Any) -> Any:
    return client.post(path, data=body, content_type="application/json", **headers)


def try_login(client: Client, body: dict[str, Any]) -> Any:
    return post(client, "/api/auth/login", body)


def status_code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def customer_pair(client: Client) -> dict[str, Any]:
    return bearer_pair(client, username="kim", password=PASSWORD, company_subdomain="tenant-a")


def change(client: Client, access: str, current: str, new: str) -> Any:
    return post(client, "/api/users/me/password", {"currentPassword": current, "newPassword": new}, **bearer(access))


# ── 로그인 ──


def test_a_customer_logs_in_and_gets_an_initial_pair(client: Client, tenants: None) -> None:
    customer()
    body = customer_pair(client)
    assert set(body) == PAIR_KEYS
    assert (body["isInitial"], body["kind"]) == (True, "service")


@pytest.mark.parametrize("extra", [{}, {"companySubdomain": None}], ids=["absent", "null"])
def test_an_operator_logs_in_without_a_company(client: Client, tenants: None, extra: dict[str, Any]) -> None:
    operator()
    response = try_login(client, {"username": "ops", "password": PASSWORD} | extra)
    assert response.status_code == 200, response.content.decode()
    assert response.json()["kind"] == "admin"


def test_an_empty_company_subdomain_is_422(client: Client, tenants: None) -> None:
    operator()
    response = try_login(client, {"companySubdomain": "", "username": "ops", "password": PASSWORD})
    assert response.status_code == 422


def test_an_extra_field_is_422(client: Client, tenants: None) -> None:
    customer()
    body = {"companySubdomain": "tenant-a", "username": "kim", "password": PASSWORD, "role": "admin"}
    assert try_login(client, body).status_code == 422
    # 분모: 그 칸을 빼면 지난다
    body.pop("role")
    assert try_login(client, body).status_code == 200


def test_every_wrong_login_answers_the_same(client: Client, tenants: None) -> None:
    """모르는 username·틀린 비밀번호·남의 회사가 같은 401 invalid_credentials 이고 본문 글자도 같다."""
    customer()
    customer("tenant-b", username="lee")
    bodies = [
        {"companySubdomain": "tenant-a", "username": "nobody", "password": PASSWORD},
        {"companySubdomain": "tenant-a", "username": "kim", "password": WRONG},
        {"companySubdomain": "tenant-a", "username": "lee", "password": PASSWORD},  # lee 는 B 의 사용자
    ]
    responses = [try_login(client, body) for body in bodies]
    assert [status_code(r) for r in responses] == [(401, "INVALID_CREDENTIALS")] * 3
    assert len({r.content for r in responses}) == 1
    # 분모: lee 는 자기 회사로는 들어간다
    assert try_login(client, bodies[2] | {"companySubdomain": "tenant-b"}).status_code == 200


def test_five_failures_lock_the_account(client: Client, tenants: None) -> None:
    customer()
    wrong = {"companySubdomain": "tenant-a", "username": "kim", "password": WRONG}
    answers = [status_code(try_login(client, wrong)) for _ in range(5)]
    assert answers == [(401, "INVALID_CREDENTIALS")] * 5
    right = wrong | {"password": PASSWORD}
    assert status_code(try_login(client, right)) == (401, "ACCOUNT_LOCKED")


def test_an_exchange_bridge_user_can_never_log_in(client: Client, tenants: None) -> None:
    """교환 다리가 만든 사용자는 쓸 수 없는 비밀번호다. 어떤 글자로도 들어가지 못한다."""
    login(Client(), sub="edk-user-1", tenant_id="tenant-a")
    for password in (PASSWORD, "!", "x"):
        body = {"companySubdomain": "tenant-a", "username": "edk-user-1", "password": password}
        assert status_code(try_login(client, body)) == (401, "INVALID_CREDENTIALS")


# ── /users/me ──


@pytest.mark.parametrize("header", [None, "Basic x"], ids=["absent", "basic"])
def test_me_without_a_bearer_is_401_no_token(client: Client, tenants: None, header: str | None) -> None:
    headers: dict[str, Any] = {} if header is None else {"HTTP_AUTHORIZATION": header}
    response = client.get("/api/users/me", **headers)
    assert status_code(response) == (401, "NO_TOKEN")
    assert set(response.json()) == {"error"}
    assert set(response.json()["error"]) == {"code", "message", "fields", "legacyCode"}


def test_me_with_a_bad_token_is_444(client: Client, tenants: None) -> None:
    customer()
    pair = customer_pair(client)
    assert status_code(client.get("/api/users/me", **bearer("not-a-token"))) == (444, "TOKEN_NOT_VALID")
    assert status_code(client.get("/api/users/me", **bearer(pair["refresh"]))) == (444, "TOKEN_NOT_VALID")
    # 분모: access 는 지난다
    assert client.get("/api/users/me", **bearer(pair["access"])).status_code == 200


def test_me_shows_a_customer(client: Client, tenants: None) -> None:
    user_id = customer()
    response = client.get("/api/users/me", **bearer(customer_pair(client)["access"]))
    assert response.status_code == 200
    assert response.json() == {
        "id": user_id,
        "username": "kim",
        "name": "김담당",
        "kind": "service",
        "companyId": company_id_of("tenant-a"),
        "isInitial": True,
    }
    assert isinstance(response.json()["id"], int)


def test_me_shows_an_operator_without_a_company(client: Client, tenants: None) -> None:
    operator()
    pair = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    body = client.get("/api/users/me", **bearer(pair["access"])).json()
    assert (body["kind"], body["companyId"]) == ("admin", None)


def forged_access(user_id: int, company_id: int) -> str:
    claims = new_access_claims(
        user_id=str(user_id),
        kind="service",
        level=79,
        company_id=company_id,
        company_is_active=True,
        is_initial=False,
        jti=uuid4(),
        now=datetime.now(UTC),
    )
    return sign_access(claims, secret=app_config().session_secret)


def test_a_token_with_another_company_is_user_unavailable(client: Client, tenants: None) -> None:
    """B 의 사용자 id 에 A 의 회사 id 를 실은 토큰(서명은 맞다): 그 회사 조건으로 읽어 없으니 401."""
    b_user = customer("tenant-b", username="lee")
    forged = client.get("/api/users/me", **bearer(forged_access(b_user, company_id_of("tenant-a"))))
    assert status_code(forged) == (401, "USER_UNAVAILABLE")
    # 분모: 같은 사용자의 제 회사 토큰은 지난다
    genuine = client.get("/api/users/me", **bearer(forged_access(b_user, company_id_of("tenant-b"))))
    assert genuine.status_code == 200


def test_an_initial_user_reaches_its_own_account(client: Client, tenants: None) -> None:
    """is_initial 이어도 /users/me 와 바꾸기는 열린다(INITIAL_ALLOWED)."""
    customer()
    access = customer_pair(client)["access"]
    assert client.get("/api/users/me", **bearer(access)).json()["isInitial"] is True
    assert status_code(change(client, access, WRONG, NEW_PASSWORD)) == (400, "CURRENT_PASSWORD_MISMATCH")


@pytest.mark.parametrize(
    ("path", "expected"),
    [("/api/sites", (403, "FORBIDDEN")), ("/api/documents/1/versions", (400, "COMPANY_AMBIGUOUS"))],
)
def test_an_operator_bearer_on_a_company_route_is_decided_by_the_bearer(
    client: Client, tenants: None, path: str, expected: tuple[int, str]
) -> None:
    """(K2b) 회사 경로는 Bearer 를 먼저 본다(쿠키로 넘어가지 않는다). 운영 관리자(MARC-ENT-374): 고객사 전용(사업장)은
    403 forbidden, 회사 업무(문서)는 작업 회사를 고르는데 회사가 둘(tenants)이라 400 company_ambiguous."""
    User.admin_by_id(operator()).update(is_initial=False)
    pair = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    assert status_code(client.get(path, **bearer(pair["access"]))) == expected


# ── 비밀번호 바꾸기 ──


def test_a_wrong_current_password_is_400(client: Client, tenants: None) -> None:
    customer()
    access = customer_pair(client)["access"]
    assert status_code(change(client, access, WRONG, NEW_PASSWORD)) == (400, "CURRENT_PASSWORD_MISMATCH")


def test_a_rejected_new_password_is_400(client: Client, tenants: None) -> None:
    # 8자 이상 하나(MARC-ENT-282) — 7자는 400. 숫자만 8자 "12345678"(전엔 400)은 이제 받는다.
    customer()
    access = customer_pair(client)["access"]
    assert status_code(change(client, access, PASSWORD, "1234567")) == (400, "PASSWORD_REJECTED")
    assert change(client, access, PASSWORD, "12345678").status_code == 200


def test_a_change_issues_a_new_pair_and_kills_the_old_refresh(client: Client, tenants: None) -> None:
    customer()
    old = customer_pair(client)
    response = change(client, old["access"], PASSWORD, NEW_PASSWORD)
    assert response.status_code == 200
    assert set(response.json()) == PAIR_KEYS
    assert response.json()["isInitial"] is False
    assert status_code(post(client, "/api/auth/refresh", {"refresh": old["refresh"]})) == (444, "TOKEN_NOT_VALID")
    # 분모: 새 refresh 는 지난다
    assert post(client, "/api/auth/refresh", {"refresh": response.json()["refresh"]}).status_code == 200


# ── refresh·revoke ──


def test_refresh_rotates_and_a_reuse_cuts_the_family(client: Client, tenants: None) -> None:
    customer()
    old = customer_pair(client)
    rotated = post(client, "/api/auth/refresh", {"refresh": old["refresh"]})
    assert rotated.status_code == 200
    assert set(rotated.json()) == PAIR_KEYS
    new = rotated.json()["refresh"]
    assert new != old["refresh"]
    assert status_code(post(client, "/api/auth/refresh", {"refresh": old["refresh"]})) == (444, "TOKEN_NOT_VALID")
    assert status_code(post(client, "/api/auth/refresh", {"refresh": new})) == (444, "TOKEN_NOT_VALID")


def test_revoke_is_idempotent_and_ends_the_refresh(client: Client, tenants: None) -> None:
    customer()
    refresh = customer_pair(client)["refresh"]
    assert post(client, "/api/auth/revoke", {"refresh": refresh}).status_code == 204
    assert post(client, "/api/auth/revoke", {"refresh": refresh}).status_code == 204
    assert status_code(post(client, "/api/auth/refresh", {"refresh": refresh})) == (444, "TOKEN_NOT_VALID")


@pytest.mark.parametrize("path", ["/api/auth/refresh", "/api/auth/revoke"])
def test_a_garbage_refresh_is_444(client: Client, tenants: None, path: str) -> None:
    assert status_code(post(client, path, {"refresh": "not-a-token"})) == (444, "TOKEN_NOT_VALID")


# ── 회사 칸 없는 고객사 로그인(UA1 — MARC-ENT-283, 처분 ⑩ ㄱ) ───────────────────


@pytest.fixture
def solo(db: None) -> int:
    """회사 하나뿐(시드 명령). 그 회사의 id."""
    from django.core.management import call_command

    call_command("seed_company", name="홀로 회사", business_licence_number="333-33-33333", subdomain="solo")
    return company_id_of("solo")


def solo_customer(company_id: int, username: str = "kim") -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name="김담당", password=PASSWORD
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def test_with_one_company_a_customer_logs_in_without_a_subdomain(client: Client, solo: int) -> None:
    solo_customer(solo)
    response = try_login(client, {"username": "kim", "password": PASSWORD})
    assert response.status_code == 200, response.content.decode()
    assert set(response.json()) == PAIR_KEYS
    assert (response.json()["kind"], response.json()["isInitial"]) == ("service", True)
    # 분모: 서브도메인을 적어도 같은 사람이다(지금 길 그대로)
    assert try_login(client, {"companySubdomain": "solo", "username": "kim", "password": PASSWORD}).status_code == 200


def test_with_one_inactive_company_the_customer_path_is_closed(client: Client, solo: int) -> None:
    from django.apps import apps

    solo_customer(solo)
    companies = apps.get_model("organization", "Company")._meta.managers_map["unscoped"]
    companies.filter(pk=solo).update(is_active=False)
    assert status_code(try_login(client, {"username": "kim", "password": PASSWORD})) == (401, "INVALID_CREDENTIALS")


def test_with_two_companies_a_customer_without_a_subdomain_is_401(client: Client, tenants: None) -> None:
    customer()
    assert status_code(try_login(client, {"username": "kim", "password": PASSWORD})) == (401, "INVALID_CREDENTIALS")
    assert customer_pair(client)["kind"] == "service"  # 분모: 서브도메인을 적으면 들어간다


def test_with_one_company_the_operator_still_comes_first(client: Client, solo: int) -> None:
    operator("ops")
    solo_customer(solo, "kim")
    assert try_login(client, {"username": "ops", "password": PASSWORD}).json()["kind"] == "admin"
    assert try_login(client, {"username": "kim", "password": PASSWORD}).json()["kind"] == "service"
