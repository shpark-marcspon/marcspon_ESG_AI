"""고객사 사용자 관리 경로 셋(K2c — 운영 관리자 전용 GET /users·POST /users·POST /users/{id}/password-reset). 업무 층.

주인 역할 연결에서 잰다(앱 역할 연결의 경계와 커밋은 보안 층 tests/security/test_user_admin.py).
회사: 뿌리 conftest 의 tenants(tenant-a·tenant-b 둘) — 하나뿐인 회사는 seed_company 명령으로 하나만 심는다
(user 의 테스트는 organization 의 models 를 import 하지 않는다 — 계약 나).
비밀번호 해시는 빠른 MD5 로 바꾼다(제품의 PBKDF2 는 test_a_created_user_is_a_fresh_customer 하나가 잰다).
"""

import io
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client, override_settings

from esgapi.user.management.commands import create_user as create_user_command
from esgapi.user.management.commands import reset_password as reset_password_command
from esgapi.user.models import RefreshToken, User
from esgapi.user.service.actions import password as actions
from esgapi.user.service.apis import login as login_api
from esgapi.user.service.apis import users as users_api
from esgapi.user.service.services import user as services
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
NEW = "Quiet-Meadow-2604"
OUT_KEYS = {
    "id",
    "companyId",
    "username",
    "name",
    "isActive",
    "isInitial",
    "isLocked",
    "branchId",
    "lastLoginAt",
    # UA1(처분 ④·⑤): 만든 때·회사 이름
    "createdAt",
    "companyName",
}


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


@pytest.fixture
def solo(db: None) -> int:
    """회사 하나뿐(시드 명령 — 사용자 결정 「시드로하자」). 그 회사의 id."""
    call_command("seed_company", name="홀로 회사", business_licence_number="333-33-33333", subdomain="solo")
    sole = users_api.find_sole_company()
    assert isinstance(sole, users_api.SoleCompany), sole
    return sole.company.id


def customer(company_id: int, username: str = "kim") -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name="김담당", password=PASSWORD
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def operator_access(client: Client, username: str = "ops", *, change: bool = True) -> str:
    """운영 관리자를 만들고 로그인한다. change 면 비밀번호를 한 번 바꿔(is_initial 끔) 새 access."""
    created = create_operator(username=username, name="운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    first = bearer_pair(client, username=username, password=PASSWORD, company_subdomain=None)
    if not change:
        access: str = first["access"]
        return access
    changed = post(
        client, "/api/users/me/password", {"currentPassword": PASSWORD, "newPassword": CHANGED}, first["access"]
    )
    assert changed.status_code == 200, changed.content.decode()
    return changed.json()["access"]


def customer_access(client: Client, subdomain: str, username: str) -> str:
    """고객사 사용자의 access(비밀번호를 바꾼 뒤 — is_initial 이 아닌 고객사 사용자)."""
    first = bearer_pair(client, username=username, password=PASSWORD, company_subdomain=subdomain)
    changed = post(
        client, "/api/users/me/password", {"currentPassword": PASSWORD, "newPassword": CHANGED}, first["access"]
    )
    assert changed.status_code == 200, changed.content.decode()
    return changed.json()["access"]


def post(client: Client, path: str, body: dict[str, Any], access: str) -> Any:
    return client.post(path, data=body, content_type="application/json", **bearer(access))


def listing(client: Client, access: str, query: str = "") -> Any:
    return client.get(f"/api/users{query}", **bearer(access))


def error(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def usernames(response: Any) -> list[str]:
    assert response.status_code == 200, response.content.decode()
    return [user["username"] for user in response.json()["results"]]


def rows(company_id: int) -> list[tuple[int, str, str, bool, int, datetime | None]]:
    return [
        (r.pk, r.username, r.password, r.is_initial, r.login_failed_count, r.login_expiry_at)
        for r in User.for_company(company_id).order_by("id")
    ]


def unrevoked(user_id: int) -> int:
    return RefreshToken.of_user(user_id).filter(revoked_at__isnull=True).count()


def fixed_clock(moment: datetime) -> Callable[[], datetime]:
    def clock() -> datetime:
        return moment

    return clock


# ── 목록 ────────────────────────────────────────────────────────────


def test_the_list_shows_only_the_named_companys_customers(client: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    kim, lee, park = customer(a, "kim"), customer(a, "lee"), customer(b, "park")
    access = operator_access(client)
    body = listing(client, access, f"?companyId={a}").json()
    assert [user["id"] for user in body["results"]] == [kim, lee]  # id 오름
    assert (body["count"], body["isNext"]) == (2, False)
    assert {user["companyId"] for user in body["results"]} == {a}
    assert set(body["results"][0]) == OUT_KEYS
    assert body["results"][0]["branchId"] is None
    # 분모: B 에도 사용자가 있고 B 로는 B 것만 — 운영 관리자 행(ops)은 어느 목록에도 없다
    assert [user["id"] for user in listing(client, access, f"?companyId={b}").json()["results"]] == [park]
    assert "ops" not in usernames(listing(client, access, f"?companyId={a}")) + usernames(
        listing(client, access, f"?companyId={b}")
    )


def test_the_list_pages_by_limit_and_offset(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    for name in ("kim", "lee", "park"):
        customer(a, name)
    access = operator_access(client)

    def page(limit: int, offset: int) -> tuple[list[str], int, bool]:
        body = listing(client, access, f"?companyId={a}&limit={limit}&offset={offset}").json()
        return [u["username"] for u in body["results"]], body["count"], body["isNext"]

    assert page(1, 0) == (["kim"], 3, True)
    assert page(1, 2) == (["park"], 3, False)
    assert page(100, 0) == (["kim", "lee", "park"], 3, False)
    assert page(20, 3) == ([], 3, False)  # 끝을 넘은 offset
    assert listing(client, access, f"?companyId={a}&limit=0").status_code == 422
    assert listing(client, access, f"?companyId={a}&limit=101").status_code == 422
    assert listing(client, access, f"?companyId={a}&offset=-1").status_code == 422


def test_the_list_of_an_unknown_company_is_404(client: Client, companies: tuple[int, int]) -> None:
    access = operator_access(client)
    assert error(listing(client, access, f"?companyId={max(companies) + 1000}")) == (404, "COMPANY_NOT_FOUND")


def test_is_locked_is_the_logins_judgement_to_the_second(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """같은 초엔 isLocked 참이고 그때 로그인은 account_locked, +1초면 거짓이고 로그인 200(두 자리가 같은 답)."""
    a, _ = companies
    kim = customer(a, "kim")
    access = operator_access(client)
    until = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=5)
    User.for_company(a).filter(pk=kim).update(login_failed_count=5, login_expiry_at=until)
    for moment, locked in ((until, True), (until + timedelta(seconds=1), False)):
        clock = fixed_clock(moment)
        monkeypatch.setattr(users_api, "now", clock)
        monkeypatch.setattr(login_api, "now", clock)
        assert listing(client, access, f"?companyId={a}").json()["results"][0]["isLocked"] is locked
        response = client.post(
            "/api/auth/login",
            data={"companySubdomain": "tenant-a", "username": "kim", "password": PASSWORD},
            content_type="application/json",
        )
        assert (response.status_code == 401 and response.json()["error"]["code"] == "ACCOUNT_LOCKED") is locked
        assert (response.status_code == 200) is not locked


# ── 만들기 ──────────────────────────────────────────────────────────


def test_a_created_user_is_a_fresh_customer(
    client: Client, companies: tuple[int, int], caplog: pytest.LogCaptureFixture
) -> None:
    a, _ = companies
    access = operator_access(client)
    with (
        override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"]),
        caplog.at_level("INFO", logger="esgapi.auth"),
    ):
        response = post(
            client, "/api/users", {"companyId": a, "username": "kim", "name": "김담당", "password": NEW}, access
        )
    assert response.status_code == 201, response.content.decode()
    body = response.json()
    assert set(body) == OUT_KEYS  # 비밀번호 칸 0
    assert (body["companyId"], body["username"], body["isInitial"], body["isLocked"]) == (a, "kim", True, False)
    row = User.for_company(a).get(pk=body["id"])
    assert (row.kind, row.level, row.is_initial, row.company_id) == ("service", 79, True, a)
    assert row.password.startswith("pbkdf2_sha256$")
    assert NEW not in response.content.decode()
    assert NEW not in caplog.text
    # HTTP 몫의 user_created(actor_user_id 가 실린 것). 앞의 운영 관리자 만들기(명령 몫 — actor 없음)는 뺀다.
    created = [r for r in caplog.records if r.getMessage() == "user_created" and hasattr(r, "actor_user_id")]
    assert [(getattr(r, "target_user_id", None), getattr(r, "company_id", None)) for r in created] == [(row.pk, a)]
    assert getattr(created[0], "actor_user_id", None) == User.admin_by_username("ops").get().pk


def test_the_same_username_in_the_same_company_is_409_but_another_company_is_fine(
    client: Client, companies: tuple[int, int]
) -> None:
    a, b = companies
    access = operator_access(client)
    body = {"username": "kim", "name": "김담당", "password": NEW}
    assert post(client, "/api/users", body | {"companyId": a}, access).status_code == 201
    assert error(post(client, "/api/users", body | {"companyId": a}, access)) == (409, "USERNAME_TAKEN")
    assert post(client, "/api/users", body | {"companyId": b}, access).status_code == 201  # 회사 안 unique(결정 02:56)
    assert [r[1] for r in rows(a)] == ["kim"]


def test_create_refusals_write_nothing(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    base = {"companyId": a, "username": "kim", "name": "김담당", "password": NEW}
    assert error(post(client, "/api/users", base | {"companyId": max(companies) + 1000}, access)) == (
        404,
        "COMPANY_NOT_FOUND",
    )
    assert error(post(client, "/api/users", base | {"password": "short"}, access)) == (400, "PASSWORD_REJECTED")
    for extra in ({"kind": "admin"}, {"level": 99}, {"isInitial": False}, {"companyId": True}):
        assert post(client, "/api/users", base | extra, access).status_code == 422, extra
    assert rows(a) == []
    assert post(client, "/api/users", base, access).status_code == 201  # 분모: 그 칸들을 빼면 만든다


# ── 초기화 ──────────────────────────────────────────────────────────


def test_a_reset_starts_over_and_cuts_only_that_users_refresh(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    kim, lee = customer(a, "kim"), customer(a, "lee")
    customer_access(Client(), "tenant-a", "kim")
    customer_access(Client(), "tenant-a", "lee")
    User.for_company(a).filter(pk=kim).update(login_failed_count=3, login_expiry_at=datetime.now(UTC))
    assert unrevoked(kim) == unrevoked(lee) == 1  # 분모: 바꾸기가 낸 새 계보 하나씩
    access = operator_access(client)
    response = post(client, f"/api/users/{kim}/password-reset", {"companyId": a, "password": NEW}, access)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert (body["id"], body["isInitial"], body["isLocked"]) == (kim, True, False)
    row = User.for_company(a).get(pk=kim)
    assert (row.is_initial, row.login_failed_count, row.login_expiry_at) == (True, 0, None)
    assert row.check_password(NEW)
    assert (unrevoked(kim), unrevoked(lee)) == (0, 1)


def test_a_reset_of_an_exchange_user_is_404_and_never_opens_a_password_login(
    client: Client, companies: tuple[int, int]
) -> None:
    """(CA·D5) 교환이 만든 행(비밀번호 쓸 수 없음 — EDK 사용자)은 초기화하지 않는다: 404 user_not_found, 행 그대로,
    그 username 으로 비밀번호 로그인이 열리지 않는다."""
    from tests.support.http import login as exchange_login

    a, _ = companies
    exchange_login(Client(), sub="edk-user-1", tenant_id="tenant-a")
    edk = User.for_company(a).get(username="edk-user-1")
    assert not edk.has_usable_password()  # 분모: 교환 행이다
    access = operator_access(client)
    response = post(client, f"/api/users/{edk.pk}/password-reset", {"companyId": a, "password": NEW}, access)
    assert error(response) == (404, "USER_NOT_FOUND")
    assert User.for_company(a).get(pk=edk.pk).password == edk.password
    login = Client().post(
        "/api/auth/login",
        data={"companySubdomain": "tenant-a", "username": "edk-user-1", "password": NEW},
        content_type="application/json",
    )
    assert error(login) == (401, "INVALID_CREDENTIALS")


def test_a_reset_outside_the_named_company_is_404_and_changes_nothing(
    client: Client, companies: tuple[int, int]
) -> None:
    a, b = companies
    kim, park = customer(a, "kim"), customer(b, "park")
    access = operator_access(client)
    ops = User.admin_by_username("ops").get().pk
    before = (rows(a), rows(b), User.admin_by_id(ops).get().password)
    for target, company in ((park, a), (kim, b), (ops, a), (max(kim, park, ops) + 1000, a)):
        response = post(client, f"/api/users/{target}/password-reset", {"companyId": company, "password": NEW}, access)
        assert error(response) == (404, "USER_NOT_FOUND"), (target, company)
    assert (rows(a), rows(b), User.admin_by_id(ops).get().password) == before
    # 분모: 맞는 회사로는 초기화된다
    assert (
        post(client, f"/api/users/{kim}/password-reset", {"companyId": a, "password": NEW}, access).status_code == 200
    )


def test_a_reset_with_a_rejected_password_is_400_and_changes_nothing(
    client: Client, companies: tuple[int, int]
) -> None:
    a, _ = companies
    kim = customer(a, "kim")
    access = operator_access(client)
    before = rows(a)
    response = post(client, f"/api/users/{kim}/password-reset", {"companyId": a, "password": "kim"}, access)
    assert error(response) == (400, "PASSWORD_REJECTED")
    assert rows(a) == before


# ── companyId 생략 = 하나뿐인 회사 ──────────────────────────────────


def test_without_company_id_the_single_company_is_used(client: Client, solo: int) -> None:
    sid = solo
    access = operator_access(client)
    created = post(client, "/api/users", {"username": "kim", "name": "김담당", "password": NEW}, access)
    assert created.status_code == 201, created.content.decode()
    assert created.json()["companyId"] == sid
    explicit, omitted, null = (
        listing(client, access, f"?companyId={sid}"),
        listing(client, access),
        post(client, "/api/users", {"companyId": None, "username": "lee", "name": "이담당", "password": NEW}, access),
    )
    assert omitted.json() == explicit.json()  # 생략과 명시가 같은 회사면 같은 답(분모)
    assert null.status_code == 201 and null.json()["companyId"] == sid
    kim = created.json()["id"]
    reset = post(client, f"/api/users/{kim}/password-reset", {"password": "Amber-Forest-6142"}, access)
    assert (reset.status_code, reset.json()["id"]) == (200, kim)


def test_without_company_id_two_companies_are_400_and_nothing_is_written(
    client: Client, companies: tuple[int, int]
) -> None:
    a, b = companies
    kim = customer(a, "kim")
    access = operator_access(client)
    before = (rows(a), rows(b))
    assert error(listing(client, access)) == (400, "COMPANY_AMBIGUOUS")
    assert error(post(client, "/api/users", {"username": "lee", "name": "이담당", "password": NEW}, access)) == (
        400,
        "COMPANY_AMBIGUOUS",
    )
    assert error(post(client, f"/api/users/{kim}/password-reset", {"password": NEW}, access)) == (
        400,
        "COMPANY_AMBIGUOUS",
    )
    assert error(post(client, f"/api/users/{kim}/password-reset", {"companyId": None, "password": NEW}, access)) == (
        400,
        "COMPANY_AMBIGUOUS",
    )
    assert (rows(a), rows(b)) == before
    assert listing(client, access, f"?companyId={a}").status_code == 200  # 분모: 고르면 지난다


def test_with_one_company_an_unknown_company_id_is_404_and_writes_nothing(client: Client, solo: int) -> None:
    """회사가 하나뿐이어도 없는 companyId 를 적으면 하나뿐인 회사로 바꿔 읽지 않는다.
    404 company_not_found, 행 0 변화(검증 권고 2)."""
    kim = customer(solo, "kim")
    access = operator_access(client)
    before = rows(solo)
    unknown = solo + 1000
    assert error(listing(client, access, f"?companyId={unknown}")) == (404, "COMPANY_NOT_FOUND")
    body = {"companyId": unknown, "username": "lee", "name": "이담당", "password": NEW}
    assert error(post(client, "/api/users", body, access)) == (404, "COMPANY_NOT_FOUND")
    reset = {"companyId": unknown, "password": NEW}
    assert error(post(client, f"/api/users/{kim}/password-reset", reset, access)) == (404, "COMPANY_NOT_FOUND")
    assert rows(solo) == before
    assert listing(client, access, f"?companyId={solo}").status_code == 200  # 분모: 그 회사의 id 로는 지난다


def test_without_company_id_and_no_company_it_is_404(client: Client, db: None) -> None:
    access = operator_access(client)
    assert error(listing(client, access)) == (404, "COMPANY_NOT_FOUND")
    assert error(post(client, "/api/users", {"username": "kim", "name": "김담당", "password": NEW}, access)) == (
        404,
        "COMPANY_NOT_FOUND",
    )


# ── 누가 하는가 ─────────────────────────────────────────────────────


def counting_ports(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """회사 고르기 포트를 감싸 호출을 센다(포트 공장 자체를 부른 것도 센다)."""
    calls: list[str] = []
    real = users_api.company_ports

    def wrapped() -> users_api.CompanyPorts:
        calls.append("company_ports")
        ports = real()

        def by_id(company_id: int) -> Any:
            calls.append("company_by_id")
            return ports.company_by_id(company_id)

        def sole() -> Any:
            calls.append("sole_company")
            return ports.sole_company()

        return users_api.CompanyPorts(company_by_id=by_id, sole_company=sole)

    monkeypatch.setattr(users_api, "company_ports", wrapped)
    return calls


def test_a_customer_gets_403_on_all_three_and_nothing_is_read_or_written(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    customer(a, "kim")
    lee = customer(a, "lee")
    access = customer_access(client, "tenant-a", "kim")
    before = (rows(a), unrevoked(lee))
    calls = counting_ports(monkeypatch)
    responses = [
        listing(client, access, f"?companyId={a}"),
        listing(client, access),
        post(client, "/api/users", {"companyId": a, "username": "x", "name": "엑스", "password": NEW}, access),
        post(client, f"/api/users/{lee}/password-reset", {"companyId": a, "password": NEW}, access),
    ]
    assert [error(r) for r in responses] == [(403, "FORBIDDEN")] * 4
    assert all("results" not in r.json() for r in responses)
    assert calls == []  # 403 은 몸(회사 고르기) 앞이다
    assert (rows(a), unrevoked(lee)) == before
    # 분모: 운영 관리자의 같은 요청은 지나고 회사 고르기를 부른다
    operator = operator_access(Client())
    assert listing(client, operator, f"?companyId={a}").status_code == 200
    assert calls == ["company_ports", "company_by_id"]


def test_an_operator_before_changing_the_password_gets_403_on_all_three(
    client: Client, companies: tuple[int, int]
) -> None:
    a, _ = companies
    kim = customer(a, "kim")
    access = operator_access(client, change=False)
    responses = [
        listing(client, access, f"?companyId={a}"),
        post(client, "/api/users", {"companyId": a, "username": "x", "name": "엑스", "password": NEW}, access),
        post(client, f"/api/users/{kim}/password-reset", {"companyId": a, "password": NEW}, access),
    ]
    assert [error(r) for r in responses] == [(403, "PASSWORD_CHANGE_REQUIRED")] * 3
    assert [r[1] for r in rows(a)] == ["kim"]


def test_the_command_and_http_call_the_same_service_and_action(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """명령과 HTTP 가 같은 함수를 부른다(감싸 센다). 명령은 actor_kind="admin", HTTP 는 토큰의 kind(admin)."""
    a, _ = companies
    seen: list[tuple[str, str]] = []
    real_create, real_reset = services.create_customer_user, actions.reset_password
    assert create_user_command.create_customer_user is real_create
    assert reset_password_command.reset_password is real_reset

    def create(**kwargs: Any) -> Any:
        seen.append(("create", kwargs["actor_kind"]))
        return real_create(**kwargs)

    def reset(**kwargs: Any) -> Any:
        seen.append(("reset", kwargs["actor_kind"]))
        return real_reset(**kwargs)

    for module in (services, create_user_command):
        monkeypatch.setattr(module, "create_customer_user", create)
    for module in (actions, reset_password_command):
        monkeypatch.setattr(module, "reset_password", reset)

    stdin = io.StringIO(f"{PASSWORD}\n")
    call_command(
        "create_user", "--company", "tenant-a", "--username", "kim", "--name", "김담당", "--password-stdin", stdin=stdin
    )
    stdin = io.StringIO(f"{NEW}\n")
    call_command("reset_password", "--company", "tenant-a", "--username", "kim", "--password-stdin", stdin=stdin)
    access = operator_access(client)
    lee = post(client, "/api/users", {"companyId": a, "username": "lee", "name": "이담당", "password": NEW}, access)
    assert (
        post(
            client, f"/api/users/{lee.json()['id']}/password-reset", {"companyId": a, "password": CHANGED}, access
        ).status_code
        == 200
    )
    assert seen == [("create", "admin"), ("reset", "admin"), ("create", "admin"), ("reset", "admin")]


# ── 수정(UA1 — PATCH /users/{user_id}, 결정 MARC-ENT-281 의 4) ───────────────


def patch(client: Client, user_id: int, body: dict[str, Any], access: str) -> Any:
    return client.patch(f"/api/users/{user_id}", data=body, content_type="application/json", **bearer(access))


def refresh_with(client: Client, refresh: str) -> Any:
    return client.post("/api/auth/refresh", data={"refresh": refresh}, content_type="application/json")


def test_a_rename_changes_only_the_name_and_answers_the_full_shape(client: Client, solo: int) -> None:
    kim, lee = customer(solo, "kim"), customer(solo, "lee")
    customer_access(Client(), "solo", "kim")
    access = operator_access(client)
    before = rows(solo)
    response = patch(client, kim, {"name": "김새이름"}, access)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert set(body) == OUT_KEYS
    assert (body["id"], body["name"], body["isActive"], body["companyId"], body["companyName"]) == (
        kim,
        "김새이름",
        True,
        solo,
        "홀로 회사",
    )
    row = User.for_company(solo).get(pk=kim)
    assert row.name == "김새이름"
    assert rows(solo) == before  # 이름 밖의 칸(비밀번호·is_initial·셈·잠금)은 그대로
    assert [r.name for r in User.for_company(solo).filter(pk=lee)] == ["김담당"]  # 남의 행 그대로
    assert unrevoked(kim) == 1  # 이름만 바꾸면 refresh 를 끊지 않는다


def test_deactivating_cuts_every_refresh_and_reactivating_keeps_them_dead(
    client: Client, companies: tuple[int, int]
) -> None:
    a, _ = companies
    kim, lee = customer(a, "kim"), customer(a, "lee")
    first = bearer_pair(Client(), username="kim", password=PASSWORD, company_subdomain="tenant-a")
    second = bearer_pair(Client(), username="kim", password=PASSWORD, company_subdomain="tenant-a")
    customer_access(Client(), "tenant-a", "lee")
    assert (unrevoked(kim), unrevoked(lee)) == (2, 1)  # 분모: kim 의 계보 둘(끊기지 않은 것)
    access = operator_access(client)

    off = patch(client, kim, {"companyId": a, "isActive": False}, access)
    assert off.status_code == 200, off.content.decode()
    assert off.json()["isActive"] is False
    assert (unrevoked(kim), unrevoked(lee)) == (0, 1)  # 그 사람 것만 끊는다
    login = Client().post(
        "/api/auth/login",
        data={"companySubdomain": "tenant-a", "username": "kim", "password": PASSWORD},
        content_type="application/json",
    )
    assert error(login) == (401, "INVALID_CREDENTIALS")  # 사용 중지 로그인은 그대로(MARC-ENT-282 의 1)

    on = patch(client, kim, {"companyId": a, "isActive": True}, access)
    assert on.status_code == 200 and on.json()["isActive"] is True
    row = User.for_company(a).get(pk=kim)
    assert (row.is_active, row.is_initial, row.login_failed_count) == (True, True, 0)  # 켜기만 한다
    for old in (first["refresh"], second["refresh"]):
        assert error(refresh_with(Client(), old)) == (444, "TOKEN_NOT_VALID")  # 옛 refresh 는 되살아나지 않는다


def test_reactivating_cuts_a_refresh_left_uncut_and_the_same_value_cuts_nothing(
    client: Client, companies: tuple[int, int]
) -> None:
    """(개정 2 N1) 거짓→참으로 바뀔 때도 끊기지 않은 refresh 를 끊는다. 같은 값을 다시 보내면 끊지 않는다(멱등)."""
    a, _ = companies
    kim, lee = customer(a, "kim"), customer(a, "lee")
    customer_access(Client(), "tenant-a", "kim")
    customer_access(Client(), "tenant-a", "lee")
    User.for_company(a).filter(pk=kim).update(is_active=False)  # 끊지 않고 끈 행(경합·DB 명령의 자리)
    assert (unrevoked(kim), unrevoked(lee)) == (1, 1)
    access = operator_access(client)
    assert patch(client, lee, {"companyId": a, "isActive": True}, access).status_code == 200  # 같은 값
    assert unrevoked(lee) == 1
    assert patch(client, kim, {"companyId": a, "isActive": True}, access).status_code == 200  # 거짓 → 참
    assert unrevoked(kim) == 0
    assert patch(client, kim, {"companyId": a, "isActive": True}, access).status_code == 200  # 다시 같은 값: 멱등
    assert User.for_company(a).get(pk=kim).is_active is True


def test_name_and_active_change_together(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    kim = customer(a, "kim")
    access = operator_access(client)
    body = patch(client, kim, {"companyId": a, "name": "김둘", "isActive": False}, access).json()
    assert (body["name"], body["isActive"]) == ("김둘", False)
    row = User.for_company(a).get(pk=kim)
    assert (row.name, row.is_active) == ("김둘", False)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": None},
        {"isActive": None},
        {"name": None, "isActive": None},
        {"name": ""},
        {"name": "가" * 21},
        {"isActive": "false"},
        {"isActive": 0},
        {"name": "김", "level": 99},
        {"name": "김", "isInitial": False},
        {"name": "김", "companyId": True},
    ],
    ids=[
        "empty",
        "name-null",
        "active-null",
        "both-null",
        "name-empty",
        "name-21",
        "active-str",
        "active-int",
        "level",
        "is-initial",
        "company-true",
    ],
)
def test_a_patch_with_nothing_to_change_or_a_bad_field_is_422_and_writes_nothing(
    client: Client, companies: tuple[int, int], body: dict[str, Any]
) -> None:
    a, _ = companies
    kim = customer(a, "kim")
    access = operator_access(client)
    before = (rows(a), [r.name for r in User.for_company(a)], [r.is_active for r in User.for_company(a)])
    assert error(patch(client, kim, {"companyId": a} | body, access)) == (422, "VALIDATION_ERROR")
    assert (rows(a), [r.name for r in User.for_company(a)], [r.is_active for r in User.for_company(a)]) == before
    assert patch(client, kim, {"companyId": a, "name": "김"}, access).status_code == 200  # 분모: 맞는 본문은 지난다


def test_a_patch_outside_the_named_company_is_404_and_changes_nothing(
    client: Client, companies: tuple[int, int]
) -> None:
    from tests.support.http import login as exchange_login

    a, b = companies
    kim, park = customer(a, "kim"), customer(b, "park")
    customer_access(Client(), "tenant-a", "kim")
    customer_access(Client(), "tenant-b", "park")
    exchange_login(Client(), sub="edk-user-1", tenant_id="tenant-a")
    edk = User.for_company(a).get(username="edk-user-1")
    assert not edk.has_usable_password()  # 분모: 교환 행이다
    access = operator_access(client)
    ops = User.admin_by_username("ops").get()

    def state() -> Any:
        return (
            [(r.pk, r.name, r.is_active, r.password) for r in User.unscoped.order_by("id")],
            [(r.jti, r.revoked_at) for user_id in (kim, park, ops.pk, edk.pk) for r in RefreshToken.of_user(user_id)],
        )

    before = state()
    for target, company in ((park, a), (kim, b), (ops.pk, a), (edk.pk, a), (max(kim, park, ops.pk, edk.pk) + 1000, a)):
        for body in ({"name": "남의이름"}, {"isActive": False}):
            response = patch(client, target, {"companyId": company} | body, access)
            assert error(response) == (404, "USER_NOT_FOUND"), (target, company, body)
    assert state() == before
    assert (
        patch(client, kim, {"companyId": a, "isActive": False}, access).status_code == 200
    )  # 분모: 맞는 회사로는 된다


def test_a_customer_gets_403_on_patch_and_nothing_is_read_or_written(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    customer(a, "kim")
    lee = customer(a, "lee")
    access = customer_access(client, "tenant-a", "kim")
    before = (rows(a), [r.is_active for r in User.for_company(a)], unrevoked(lee))
    calls = counting_ports(monkeypatch)
    assert error(patch(client, lee, {"companyId": a, "isActive": False}, access)) == (403, "FORBIDDEN")
    assert calls == []  # 403 은 몸(회사 고르기) 앞이다
    assert (rows(a), [r.is_active for r in User.for_company(a)], unrevoked(lee)) == before


def test_an_operator_before_changing_the_password_gets_403_on_patch(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    kim = customer(a, "kim")
    access = operator_access(client, change=False)
    assert error(patch(client, kim, {"companyId": a, "name": "김"}, access)) == (403, "PASSWORD_CHANGE_REQUIRED")
    assert User.for_company(a).get(pk=kim).name == "김담당"


def test_patch_users_me_is_not_the_update_route(client: Client, companies: tuple[int, int]) -> None:
    """`{int:user_id}` 라 /users/me 를 가로채지 않는다: PATCH /users/me 는 405(GET·POST 의 자리)."""
    access = operator_access(client)
    response = client.patch("/api/users/me", data={"name": "x"}, content_type="application/json", **bearer(access))
    assert response.status_code == 405
    assert client.get("/api/users/me", **bearer(access)).status_code == 200


def test_a_patch_without_company_id_uses_the_single_company(client: Client, solo: int) -> None:
    kim = customer(solo, "kim")
    access = operator_access(client)
    response = patch(client, kim, {"name": "김홀로"}, access)
    assert (response.status_code, response.json()["companyId"]) == (200, solo)


# ── 목록의 거르기·새 칸(UA1 — 처분 ③④⑤⑨) ────────────────────────────


def test_the_list_carries_created_at_and_the_company_name(client: Client, solo: int) -> None:
    kim = customer(solo, "kim")
    access = operator_access(client)
    item = listing(client, access).json()["results"][0]
    joined = User.for_company(solo).get(pk=kim).date_joined
    assert item["companyName"] == "홀로 회사"
    assert item["createdAt"].endswith("+09:00")
    assert datetime.fromisoformat(item["createdAt"]) == joined


def test_the_list_leaves_out_exchange_rows(client: Client, companies: tuple[int, int]) -> None:
    from tests.support.http import login as exchange_login

    a, _ = companies
    customer(a, "kim")
    exchange_login(Client(), sub="edk-user-1", tenant_id="tenant-a")
    assert User.for_company(a).filter(username="edk-user-1").exists()  # 분모: 교환 행이 있다
    access = operator_access(client)
    body = listing(client, access, f"?companyId={a}").json()
    assert ([u["username"] for u in body["results"]], body["count"]) == (["kim"], 1)


def test_q_matches_part_of_the_username_or_the_name_ignoring_case(client: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    for username, name in (("Kim.One", "김하나"), ("lee", "이담당"), ("park", "박KIMBAP")):
        create_customer_user(actor_kind="admin", company_id=a, username=username, name=name, password=PASSWORD)
    customer(b, "kim")  # 남의 회사의 같은 글자
    access = operator_access(client)

    def found(q: str) -> tuple[list[str], int]:
        body = listing(client, access, f"?companyId={a}&q={q}").json()
        return [u["username"] for u in body["results"]], body["count"]

    assert found("kim") == (["Kim.One", "park"], 2)  # 아이디·이름, 대소문자 무시, 남의 회사 0
    assert found("담당") == (["lee"], 1)
    assert found("zzz") == ([], 0)
    assert listing(client, access, f"?companyId={a}&q=").status_code == 422
    assert listing(client, access, f"?companyId={a}&q={'k' * 151}").status_code == 422
    assert listing(client, access, f"?companyId={a}&q={'k' * 150}").status_code == 200


def test_status_filters_by_the_four_states_to_the_second(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    active, initial, locked, off = (customer(a, n) for n in ("active", "initial", "locked", "off"))
    until = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=5)
    User.for_company(a).filter(pk__in=[active, locked]).update(is_initial=False)
    User.for_company(a).filter(pk=locked).update(login_failed_count=5, login_expiry_at=until)
    User.for_company(a).filter(pk=off).update(is_active=False, login_expiry_at=until)  # 꺼짐이 잠김보다 앞선다
    access = operator_access(client)

    def found(status: str) -> tuple[list[int], int]:
        body = listing(client, access, f"?companyId={a}&status={status}").json()
        return [u["id"] for u in body["results"]], body["count"]

    monkeypatch.setattr(users_api, "now", fixed_clock(until))  # 같은 초 = 잠김
    assert {s: found(s) for s in ("active", "initial", "locked", "inactive")} == {
        "active": ([active], 1),
        "initial": ([initial], 1),
        "locked": ([locked], 1),
        "inactive": ([off], 1),
    }
    monkeypatch.setattr(users_api, "now", fixed_clock(until + timedelta(seconds=1)))  # 잠금이 지났다
    assert found("locked") == ([], 0)
    assert found("active") == ([active, locked], 2)
    assert listing(client, access, f"?companyId={a}&status=blocked").status_code == 422
    assert listing(client, access, f"?companyId={a}").json()["count"] == 4  # 분모: 거르지 않으면 넷


# ── 만들기의 아이디 꼴(UA1 — 처분 ⑥) ──────────────────────────────────


@pytest.mark.parametrize(
    "username", ["김담당", "ｋｉｍ", "kim one", "kim\u00e9"], ids=["hangul", "fullwidth", "space", "accent"]
)
def test_a_username_outside_ascii_is_422_and_makes_nothing(
    client: Client, companies: tuple[int, int], username: str
) -> None:
    a, _ = companies
    access = operator_access(client)
    body = {"companyId": a, "username": username, "name": "새담당", "password": NEW}
    assert error(post(client, "/api/users", body, access)) == (422, "VALIDATION_ERROR")
    assert rows(a) == []
    ascii_body = body | {"username": "Kim_1.a@b+c-d"}
    assert post(client, "/api/users", ascii_body, access).status_code == 201  # 분모: ASCII 글자는 지난다


def test_a_customer_with_an_operators_username_is_409_and_makes_nothing(
    client: Client, companies: tuple[int, int]
) -> None:
    """(UA1 — 겹침 막기) 운영 관리자 ops 와 같은 아이디의 고객사 사용자는 409 username_taken, 행 0."""
    a, _ = companies
    access = operator_access(client)
    body = {"companyId": a, "username": "ops", "name": "겹침", "password": NEW}
    assert error(post(client, "/api/users", body, access)) == (409, "USERNAME_TAKEN")
    assert rows(a) == []
    assert post(client, "/api/users", body | {"username": "ops2"}, access).status_code == 201  # 분모
