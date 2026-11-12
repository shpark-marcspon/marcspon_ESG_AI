"""고객사 사용자 관리 셋(K2c — 운영 관리자 전용 GET /users·POST /users·POST /users/{id}/password-reset)이 회사의
경계와 만나는 자리. 보안 층.

연결은 이 층 그대로다(앱 역할 esg_app, RLS 없음, 진짜 커밋, 직렬). 운영 관리자에게는 회사 범위가 없다: 대상 회사는
요청의 companyId(없으면 하나뿐인 회사)로 고르고 사용자는 그 회사의 User.for_company 로만 연다. 그래서 「남의 회사 행이
보이거나 바뀌었는가」는 앱 역할의 답만으로는 모른다 — 행·해시·셈·refresh 행은 주인 연결(owner)로 센다(분모).
업무 층(esgapi/user/tests/service/apis/test_users.py)은 같은 규칙을 주인 연결의 트랜잭션 안에서 잰다.
해시는 MD5 다(conftest 의 fast_hasher). 만들기의 해시는 제품 설정(Django 기본 PBKDF2)으로 되돌려 잰다.
"""

from typing import Any, Final

import psycopg
import pytest
from django.conf import global_settings
from django.test import Client, override_settings

from tests.security.conftest import count
from tests.security.seed import add_company
from tests.security.test_login import OTHER_PASSWORD, PASSWORD, answer, customer, operator
from tests.security.test_refresh import REJECTED, refresh, revoked_by_user
from tests.support.http import bearer, bearer_pair, customer_bearer

pytestmark = [pytest.mark.security, pytest.mark.usefixtures("fast_hasher")]

Owner = psycopg.Connection[tuple[Any, ...]]
NEW: Final = "Quiet-Meadow-2604"
AMBIGUOUS: Final = (400, "COMPANY_AMBIGUOUS")


def operator_access(client: Client) -> str:
    """운영 관리자(ops)를 만들고 로그인해 비밀번호를 한 번 바꾼(is_initial 끔) 뒤의 access."""
    operator()
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    change = {"currentPassword": PASSWORD, "newPassword": OTHER_PASSWORD}
    changed = post(client, "/api/users/me/password", change, first["access"])
    assert changed.status_code == 200, changed.content.decode()
    access: str = changed.json()["access"]
    return access


def post(client: Client, path: str, body: dict[str, Any], access: str) -> Any:
    return client.post(path, data=body, content_type="application/json", **bearer(access))


def listing(client: Client, access: str, query: str = "") -> Any:
    return client.get(f"/api/users{query}", **bearer(access))


def listed(response: Any) -> list[int]:
    assert response.status_code == 200, response.content.decode()
    return [user["id"] for user in response.json()["results"]]


def log_in(company_subdomain: str, username: str) -> dict[str, Any]:
    """그 고객사 사용자로 한 번 로그인한다(새 기기 — refresh 행 하나)."""
    return bearer_pair(Client(), username=username, password=PASSWORD, company_subdomain=company_subdomain)


def users(owner: Owner) -> list[tuple[Any, ...]]:
    """주인 역할이 본 사용자 행 전부(id 오름): 회사·kind·username·해시·is_initial·셈·잠금 끝·활성."""
    return owner.execute(
        "SELECT id, company_id, kind, username, password, is_initial, login_failed_count, login_expiry_at, is_active "
        "FROM users ORDER BY id"
    ).fetchall()


def refresh_rows(owner: Owner) -> list[tuple[Any, ...]]:
    """주인 역할이 본 refresh 행 전부(id 오름): 사용자·쓴 때·끊은 때."""
    return owner.execute("SELECT id, user_id, used_at, revoked_at FROM user_refresh_tokens ORDER BY id").fetchall()


def customers_of(owner: Owner, company_id: int) -> list[int]:
    """주인 역할이 본 그 회사의 고객사 사용자 id(오름)."""
    return [
        int(user_id)
        for (user_id,) in owner.execute(
            "SELECT id FROM users WHERE company_id = %s AND kind = 'service' ORDER BY id", [company_id]
        )
    ]


def operator_id(owner: Owner) -> int:
    row = owner.execute("SELECT id FROM users WHERE kind = 'admin' AND username = 'ops'").fetchone()
    assert row is not None
    return int(row[0])


# ── 목록·만들기·초기화가 고른 회사에만 닿는다 ──


def test_the_user_list_shows_only_the_named_company(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    kim, lee, park = customer(a, "kim"), customer(a, "lee"), customer(b, "park")
    access = operator_access(client)
    ops = operator_id(owner)
    # 분모: 두 회사 다 고객사 사용자가 있고 운영 관리자 행도 있다
    assert (customers_of(owner, a), customers_of(owner, b), count(owner, "users")) == ([kim, lee], [park], 4)

    seen_a = listing(client, access, f"?companyId={a}")
    seen_b = listing(client, access, f"?companyId={b}")
    assert listed(seen_a) == customers_of(owner, a)
    assert listed(seen_b) == customers_of(owner, b)
    assert (seen_a.json()["count"], seen_b.json()["count"]) == (2, 1)
    assert {user["companyId"] for user in seen_a.json()["results"]} == {a}
    assert {user["companyId"] for user in seen_b.json()["results"]} == {b}
    assert ops not in listed(seen_a) + listed(seen_b)  # 운영 관리자 행은 어느 목록에도 없다


def test_a_created_user_lands_in_the_named_company(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """B 를 골라 만들면 행은 B 의 고객사 사용자다(주인 연결이 본다 — 커밋됐다). 해시는 제품의 것(PBKDF2-SHA256)."""
    a, b = companies
    access = operator_access(client)
    before = count(owner, "users")
    # fast_hasher 를 이 요청에서만 걷는다: 보안 층의 설정은 제품 설정(base.py — PASSWORD_HASHERS 를 두지 않는다)이다
    with override_settings(PASSWORD_HASHERS=global_settings.PASSWORD_HASHERS):
        response = post(
            client, "/api/users", {"companyId": b, "username": "kim", "name": "김담당", "password": NEW}, access
        )
    assert response.status_code == 201, response.content.decode()
    assert NEW not in response.content.decode()
    body = response.json()
    row = owner.execute(
        "SELECT company_id, kind, level, is_initial, password FROM users WHERE id = %s", [body["id"]]
    ).fetchone()
    assert row is not None
    assert row[:4] == (b, "service", 79, True)
    assert str(row[4]).startswith("pbkdf2_sha256$")
    assert body["companyId"] == b
    assert count(owner, "users") == before + 1
    assert (customers_of(owner, a), customers_of(owner, b)) == ([], [body["id"]])


def test_a_reset_with_another_company_is_404_and_changes_nothing(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """B 의 사용자 id 를 companyId=A 로 초기화하면 404 user_not_found 이고 행·refresh 가 그대로다(주인 연결)."""
    a, b = companies
    park = customer(b, "park")
    log_in("tenant-b", "park")
    access = operator_access(client)
    before = (users(owner), refresh_rows(owner))
    assert revoked_by_user(owner, park) == [False]  # 분모: 끊을 계보가 있다

    response = post(client, f"/api/users/{park}/password-reset", {"companyId": a, "password": NEW}, access)
    assert answer(response) == (404, "USER_NOT_FOUND")
    assert (users(owner), refresh_rows(owner)) == before

    # 분모: 맞는 회사(B)로는 초기화된다
    fixed = post(client, f"/api/users/{park}/password-reset", {"companyId": b, "password": NEW}, access)
    assert fixed.status_code == 200, fixed.content.decode()
    assert (fixed.json()["id"], fixed.json()["companyId"]) == (park, b)
    assert revoked_by_user(owner, park) == [True]


# ── 누가 하는가 ──


def test_a_customer_gets_403_on_every_user_admin_operation_and_nothing_is_written(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """바꾼 뒤의 고객사 사용자(is_initial 아님)의 Bearer 로 셋 다 403 forbidden. 행 수·대상의 해시·is_initial·셈·
    refresh 행이 그대로다(주인 연결). 분모: 운영 관리자의 같은 요청 셋은 지난다."""
    a, _ = companies
    lee = customer(a, "lee")
    log_in("tenant-a", "lee")
    access = customer_bearer(client, company_id=a, subdomain="tenant-a")
    before = (users(owner), refresh_rows(owner))
    created = {"companyId": a, "username": "x", "name": "엑스", "password": NEW}
    reset = {"companyId": a, "password": NEW}

    responses = [
        listing(client, access, f"?companyId={a}"),
        post(client, "/api/users", created, access),
        post(client, f"/api/users/{lee}/password-reset", reset, access),
    ]
    assert [answer(response) for response in responses] == [(403, "FORBIDDEN")] * 3
    assert (users(owner), refresh_rows(owner)) == before
    assert revoked_by_user(owner, lee) == [False]

    operator = operator_access(Client())
    assert lee in listed(listing(client, operator, f"?companyId={a}"))
    assert post(client, "/api/users", created, operator).status_code == 201
    assert post(client, f"/api/users/{lee}/password-reset", reset, operator).status_code == 200
    assert revoked_by_user(owner, lee) == [True]


def test_a_reset_revokes_the_users_families_and_is_committed(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """HTTP 초기화: 그 사용자의 계보 전부에 revoked_at 이 적혀 커밋된다(주인 연결이 본다). 같은 회사의 다른 사용자의
    행은 그대로다. is_initial 참·셈 0·잠금 풀림."""
    a, _ = companies
    kim, lee = customer(a, "kim"), customer(a, "lee")
    kim_pairs = [log_in("tenant-a", "kim"), log_in("tenant-a", "kim")]
    lee_pair = log_in("tenant-a", "lee")
    owner.execute("UPDATE users SET is_initial = false, login_failed_count = 3 WHERE id = %s", [kim])
    access = operator_access(client)
    assert (revoked_by_user(owner, kim), revoked_by_user(owner, lee)) == ([False, False], [False])  # 분모

    response = post(client, f"/api/users/{kim}/password-reset", {"companyId": a, "password": NEW}, access)
    assert response.status_code == 200, response.content.decode()
    assert (response.json()["id"], response.json()["isInitial"]) == (kim, True)

    assert revoked_by_user(owner, kim) == [True, True]
    assert revoked_by_user(owner, lee) == [False]
    state = "SELECT is_initial, login_failed_count, login_expiry_at FROM users WHERE id = %s"
    assert owner.execute(state, [kim]).fetchone() == (True, 0, None)
    for pair in kim_pairs:
        assert answer(refresh(Client(), pair["refresh"])) == REJECTED
    assert refresh(Client(), lee_pair["refresh"]).status_code == 200  # 분모: 다른 사용자의 계보는 산다
    fresh = bearer_pair(Client(), username="kim", password=NEW, company_subdomain="tenant-a")
    assert fresh["isInitial"] is True


# ── companyId 생략 = 하나뿐인 회사 ──


def test_without_company_id_the_single_company_is_used(client: Client, owner: Owner) -> None:
    solo = add_company(owner, "solo")
    assert count(owner, "company") == 1  # 분모: 회사가 하나뿐이다
    access = operator_access(client)

    created = post(client, "/api/users", {"username": "kim", "name": "김담당", "password": NEW}, access)
    assert created.status_code == 201, created.content.decode()
    kim = created.json()["id"]
    assert created.json()["companyId"] == solo
    row = owner.execute("SELECT company_id, kind FROM users WHERE id = %s", [kim]).fetchone()
    assert row == (solo, "service")

    assert listed(listing(client, access)) == customers_of(owner, solo) == [kim]
    hash_before = owner.execute("SELECT password FROM users WHERE id = %s", [kim]).fetchone()
    reset = post(client, f"/api/users/{kim}/password-reset", {"password": "Amber-Forest-6142"}, access)
    assert (reset.status_code, reset.json()["companyId"]) == (200, solo)
    assert owner.execute("SELECT password FROM users WHERE id = %s", [kim]).fetchone() != hash_before


def test_without_company_id_two_companies_are_400_and_nothing_is_written(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """회사가 둘이면 companyId 를 생략(또는 null)한 셋 다 400 company_ambiguous 이고 행·refresh 가 그대로다."""
    a, b = companies
    kim = customer(a, "kim")
    customer(b, "park")
    log_in("tenant-a", "kim")
    access = operator_access(client)
    assert count(owner, "company") == 2  # 분모: 회사가 둘이다
    before = (users(owner), refresh_rows(owner))

    responses = [
        listing(client, access),
        post(client, "/api/users", {"username": "lee", "name": "이담당", "password": NEW}, access),
        post(client, "/api/users", {"companyId": None, "username": "lee", "name": "이담당", "password": NEW}, access),
        post(client, f"/api/users/{kim}/password-reset", {"password": NEW}, access),
        post(client, f"/api/users/{kim}/password-reset", {"companyId": None, "password": NEW}, access),
    ]
    assert [answer(response) for response in responses] == [AMBIGUOUS] * 5
    assert (users(owner), refresh_rows(owner)) == before
    assert listed(listing(client, access, f"?companyId={a}")) == [kim]  # 분모: 고르면 지난다


# ── 수정(UA1 — PATCH /users/{user_id}: 이름·사용 중지) ──


def patch(client: Client, user_id: int, body: dict[str, Any], access: str) -> Any:
    return client.patch(f"/api/users/{user_id}", data=body, content_type="application/json", **bearer(access))


def test_a_patch_with_another_company_is_404_and_changes_nothing(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """(UA1 ⓐ) B 의 사용자 id 를 companyId=A 로 고치면 404 user_not_found 이고 users·user_refresh_tokens 가 그대로다
    (주인 연결). 운영 관리자의 id 도 같다. 분모: B 로 고르면 고쳐진다(커밋)."""
    a, b = companies
    park = customer(b, "park")
    log_in("tenant-b", "park")
    access = operator_access(client)
    ops = operator_id(owner)
    before = (users(owner), refresh_rows(owner))
    assert revoked_by_user(owner, park) == [False]  # 분모: 끊을 계보가 있다
    for target in (park, ops):
        for body in ({"name": "남의이름"}, {"isActive": False}, {"name": "남", "isActive": False}):
            response = patch(client, target, {"companyId": a} | body, access)
            assert answer(response) == (404, "USER_NOT_FOUND"), (target, body)
    assert (users(owner), refresh_rows(owner)) == before

    assert patch(client, park, {"companyId": b, "isActive": False}, access).status_code == 200
    row = owner.execute("SELECT is_active FROM users WHERE id = %s", [park]).fetchone()
    assert row == (False,)
    assert revoked_by_user(owner, park) == [True]


def test_a_customer_gets_403_on_patch_and_nothing_is_written(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """(UA1 ⓑ) 바꾼 뒤의 고객사 사용자의 Bearer 로 PATCH 는 403 forbidden, 행·refresh 그대로(주인 연결).
    분모: 운영 관리자의 같은 요청은 지난다."""
    a, _ = companies
    lee = customer(a, "lee")
    log_in("tenant-a", "lee")
    access = customer_bearer(client, company_id=a, subdomain="tenant-a")
    before = (users(owner), refresh_rows(owner))
    body = {"companyId": a, "name": "엑스", "isActive": False}
    assert answer(patch(client, lee, body, access)) == (403, "FORBIDDEN")
    assert (users(owner), refresh_rows(owner)) == before
    assert patch(client, lee, body, operator_access(Client())).status_code == 200
    assert revoked_by_user(owner, lee) == [True]


def test_deactivating_revokes_every_family_and_is_committed_and_reactivating_does_not_revive(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """(UA1 ⓒ) 사용 중지가 그 사람의 계보 전부에 revoked_at 을 적고 커밋된다(주인 연결). 같은 회사의 남의 행은 그대로.
    다시 사용해도 옛 refresh 는 444. (이미 낸 access 가 만료까지 통하는 것(R13)은 이 시험이 재지 않는다.)"""
    a, _ = companies
    kim, lee = customer(a, "kim"), customer(a, "lee")
    kim_pairs = [log_in("tenant-a", "kim"), log_in("tenant-a", "kim")]
    lee_pair = log_in("tenant-a", "lee")
    access = operator_access(client)
    assert (revoked_by_user(owner, kim), revoked_by_user(owner, lee)) == ([False, False], [False])  # 분모

    off = patch(client, kim, {"companyId": a, "isActive": False}, access)
    assert off.status_code == 200, off.content.decode()
    assert revoked_by_user(owner, kim) == [True, True]
    assert revoked_by_user(owner, lee) == [False]
    assert owner.execute("SELECT is_active FROM users WHERE id = %s", [kim]).fetchone() == (False,)

    on = patch(client, kim, {"companyId": a, "isActive": True}, access)
    assert on.status_code == 200
    for pair in kim_pairs:
        assert answer(refresh(Client(), pair["refresh"])) == REJECTED
    assert refresh(Client(), lee_pair["refresh"]).status_code == 200  # 분모: 다른 사용자의 계보는 산다


def test_a_refresh_left_uncut_while_inactive_is_cut_on_reactivation(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """(UA1 개정 2 N1) 사용 중지와 refresh 잇기가 겹쳐 끊기지 않은 행이 남아도, 다시 사용(거짓 → 참)이 그것을 끊는다.
    같은 값을 다시 보내면 끊지 않는다."""
    a, _ = companies
    kim, lee = customer(a, "kim"), customer(a, "lee")
    kim_pair = log_in("tenant-a", "kim")
    log_in("tenant-a", "lee")
    owner.execute("UPDATE users SET is_active = false WHERE id = %s", [kim])  # 끊지 않고 끈 행
    access = operator_access(client)
    assert (revoked_by_user(owner, kim), revoked_by_user(owner, lee)) == ([False], [False])  # 분모
    assert patch(client, lee, {"companyId": a, "isActive": True}, access).status_code == 200  # 같은 값
    assert revoked_by_user(owner, lee) == [False]
    assert patch(client, kim, {"companyId": a, "isActive": True}, access).status_code == 200  # 거짓 → 참
    assert revoked_by_user(owner, kim) == [True]
    assert answer(refresh(Client(), kim_pair["refresh"])) == REJECTED


def test_a_deactivated_user_still_gets_invalid_credentials_on_login(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """(UA1 ⓓ) 사용 중지된 사람의 로그인은 지금처럼 401 invalid_credentials(MARC-ENT-282 의 1 — 따로 밝히지 않음).
    셈도 바뀌지 않는다. 분모: 다시 사용하면 같은 비밀번호로 들어온다."""
    a, _ = companies
    kim = customer(a, "kim")
    access = operator_access(client)
    assert patch(client, kim, {"companyId": a, "isActive": False}, access).status_code == 200
    counts = "SELECT login_failed_count, login_expiry_at FROM users WHERE id = %s"
    before = owner.execute(counts, [kim]).fetchone()
    body = {"companySubdomain": "tenant-a", "username": "kim", "password": PASSWORD}
    response = Client().post("/api/auth/login", data=body, content_type="application/json")
    assert answer(response) == (401, "INVALID_CREDENTIALS")
    assert owner.execute(counts, [kim]).fetchone() == before
    assert patch(client, kim, {"companyId": a, "isActive": True}, access).status_code == 200
    assert Client().post("/api/auth/login", data=body, content_type="application/json").status_code == 200


def test_the_list_query_does_not_reach_another_company(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """(UA1 ⓔ) q·status 로 걸러도 고른 회사의 행만 나온다. 분모: B 에 같은 글자의 사용자가 있고 B 로 고르면 나온다."""
    a, b = companies
    kim = customer(a, "kim")
    park = customer(b, "kimpark")
    access = operator_access(client)
    assert listed(listing(client, access, f"?companyId={a}&q=kim")) == [kim]
    assert listed(listing(client, access, f"?companyId={a}&q=park")) == []
    assert listed(listing(client, access, f"?companyId={a}&q=kim&status=initial")) == [kim]
    assert listed(listing(client, access, f"?companyId={b}&q=kim")) == [park]
    assert customers_of(owner, b) == [park]
