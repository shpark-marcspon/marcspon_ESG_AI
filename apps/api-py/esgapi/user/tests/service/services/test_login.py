"""로그인·잠금·refresh 잇기·로그아웃(업무 층, 주인 역할 연결).

해시는 MD5 로 바꿔 빠르게 돈다(이 파일의 autouse 고정물 — 제품 설정은 그대로다). 해시 횟수는 MD5 해시기의
encode·verify 를 세어 잰다(verify 안의 encode 는 한 번으로 친다 — 가짜 길은 make_password → encode 한 번,
진짜 길은 verify 한 번).
회사 id 는 상수로 박지 않는다 — tenants 고정물이 심고 organization 의 찾기(find_company)로 읽는다.
"""

import ast
import io
import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from django.contrib.auth.hashers import MD5PasswordHasher, make_password
from django.db.models import Max
from django.test import override_settings

from esgapi.core.auth.principal import Kind
from esgapi.core.auth.tokens import (
    AccessActive,
    RefreshActive,
    RefreshClaims,
    new_refresh_claims,
    read_access,
    read_refresh,
    sign_refresh,
)
from esgapi.core.calc.audit import AUDIT_ACTIONS
from esgapi.core.conf import app_config
from esgapi.core.models import AuditEventRow
from esgapi.core.observability.jsonlog import JsonFormatter
from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.models import RefreshToken, User
from esgapi.user.service.services import login as login_module
from esgapi.user.service.services.login import LoginPorts, login, refresh, revoke
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import (
    LoginOk,
    LoginRejected,
    RefreshOk,
    RefreshRejected,
    Revoked,
    TokenPair,
    UserCreated,
)

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
SECOND = timedelta(seconds=1)
LOCK = timedelta(seconds=600)
PASSWORD = "Blue-Harbor-7310"
OTHER_PASSWORD = "Green-Valley-4821"
WRONG = "Wrong-Lantern-5932"


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


class Hashes:
    """해시기를 부른 횟수. 안쪽 부름(verify 안의 encode)은 세지 않는다."""

    def __init__(self) -> None:
        self.calls = 0
        self._depth = 0

    def counted(self, method: Callable[..., object]) -> Callable[..., object]:
        def call(*args: object, **kwargs: object) -> object:
            if self._depth == 0:
                self.calls += 1
            self._depth += 1
            try:
                return method(*args, **kwargs)
            finally:
                self._depth -= 1

        return call


@pytest.fixture
def hashes(monkeypatch: pytest.MonkeyPatch) -> Hashes:
    """세기 시작은 부르는 쪽이 calls = 0 으로 정한다(계정을 만드는 해시를 빼려고)."""
    counter = Hashes()
    for name in ("encode", "verify"):
        monkeypatch.setattr(MD5PasswordHasher, name, counter.counted(getattr(MD5PasswordHasher, name)))
    return counter


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive), found
    return found.company.id


def ports(*, off: frozenset[str] = frozenset(), sole: int | None = None) -> LoginPorts:
    """서브도메인 → 쓸 수 있는 회사의 id. off 의 서브도메인은 비활성 회사처럼 None.
    sole 은 서브도메인 없는 로그인의 「하나뿐인 쓸 수 있는 회사」(UA1 — 기본 None: 회사 둘·비활성과 같은 답)."""

    def company_id_of_active(subdomain: str) -> int | None:
        if subdomain in off:
            return None
        found = find_company(subdomain)
        return found.company.id if isinstance(found, CompanyActive) else None

    return LoginPorts(company_id_of=company_id_of_active, sole_company_id=lambda: sole)


def customer(company_id: int, username: str = "kim", password: str = PASSWORD) -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name="김담당", password=password
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def operator(username: str = "ops", password: str = PASSWORD) -> int:
    created = create_operator(username=username, name="운영자", password=password)
    assert isinstance(created, UserCreated), created
    return created.user_id


def row(company_id: int | None, user_id: int) -> User:
    if company_id is None:
        return User.admin_by_id(user_id).get()
    return User.for_company(company_id).get(pk=user_id)


def lock_state(company_id: int | None, user_id: int) -> tuple[int, datetime | None]:
    current = row(company_id, user_id)
    return current.login_failed_count, current.login_expiry_at


@dataclass(frozen=True)
class Account:
    company_id: int | None
    user_id: int
    subdomain: str | None
    username: str


def account_of(kind: Kind) -> Account:
    if kind == "admin":
        return Account(None, operator(), None, "ops")
    a = company_id_of("tenant-a")
    return Account(a, customer(a), "tenant-a", "kim")


def attempt(account: Account, password: str, now: datetime) -> LoginOk | LoginRejected:
    return login(subdomain=account.subdomain, username=account.username, password=password, now=now, ports=ports())


def fail(account: Account, times: int, now: datetime) -> None:
    for _ in range(times):
        assert attempt(account, WRONG, now) == LoginRejected("invalid_credentials")


def pair_of(result: object) -> TokenPair:
    assert isinstance(result, LoginOk | RefreshOk), result
    return result.pair


def refresh_claims_of(token: str) -> RefreshClaims:
    read = read_refresh(token, secret=app_config().session_secret, now=T0, allow_expired=True)
    assert isinstance(read, RefreshActive), read
    return read.claims


def family_revoked(family: UUID) -> list[bool]:
    return [revoked is not None for revoked in RefreshToken.of_family(family).values_list("revoked_at", flat=True)]


# ── 로그인: 받아들임 ──────────────────────────────────────────────────


def test_a_customer_logs_in_with_the_right_password(tenants: None) -> None:
    a = company_id_of("tenant-a")
    user_id = customer(a)
    pair = pair_of(login(subdomain="tenant-a", username="kim", password=PASSWORD, now=T0, ports=ports()))
    assert (pair.kind, pair.is_initial) == ("service", True)
    assert pair.access_expires_at == T0 + timedelta(seconds=1800)
    assert pair.refresh_expires_at == T0 + timedelta(seconds=604800)
    read = read_access(pair.access, secret=app_config().session_secret, now=T0)
    assert isinstance(read, AccessActive), read
    claims = read.claims
    assert (claims.user_id, claims.kind, claims.level, claims.company_id, claims.company_is_active) == (
        str(user_id),
        "service",
        79,
        a,
        True,
    )
    assert claims.is_initial is True
    assert refresh_claims_of(pair.refresh).company_id == a
    assert RefreshToken.of_user(user_id).count() == 1
    assert row(a, user_id).last_login == T0


def test_an_operator_logs_in_without_a_subdomain(tenants: None) -> None:
    user_id = operator()
    pair = pair_of(login(subdomain=None, username="ops", password=PASSWORD, now=T0, ports=ports()))
    assert (pair.kind, pair.is_initial) == ("admin", True)
    read = read_access(pair.access, secret=app_config().session_secret, now=T0)
    assert isinstance(read, AccessActive), read
    assert (read.claims.user_id, read.claims.kind, read.claims.level) == (str(user_id), "admin", 99)
    assert (read.claims.company_id, read.claims.company_is_active) == (None, None)
    assert refresh_claims_of(pair.refresh).company_id is None


# ── 로그인: 거절은 하나(invalid_credentials), 해시는 한 번(K-B8) ─────────

MISSES: dict[str, tuple[str | None, str, str]] = {
    "wrong-password": ("tenant-a", "kim", WRONG),
    "unknown-username": ("tenant-a", "nobody", PASSWORD),
    "unknown-company": ("tenant-z", "kim", PASSWORD),
    "inactive-company": ("tenant-b", "kim", PASSWORD),
    "inactive-user": ("tenant-a", "off", PASSWORD),
    "unusable-password": ("tenant-a", "blank", PASSWORD),
    "operator-unknown": (None, "nobody", PASSWORD),
    "operator-inactive": (None, "ops-off", PASSWORD),
    "operator-wrong-password": (None, "ops", WRONG),
}


@pytest.fixture
def population(tenants: None) -> Iterator[None]:
    """가 회사: kim·off(꺼짐)·blank(쓸 수 없는 비밀번호). 나 회사: kim(회사가 꺼진 것으로 본다).
    운영: ops·ops-off(꺼짐)."""
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    customer(a)
    customer(b)
    off = customer(a, "off")
    User.for_company(a).filter(pk=off).update(is_active=False)
    User.for_company(a).create(
        company_id=a, kind="service", username="blank", name="빈칸", level=79, password=make_password(None)
    )
    operator()
    ops_off = operator("ops-off")
    User.admin_by_id(ops_off).update(is_active=False)
    yield


@pytest.mark.parametrize("case", list(MISSES))
def test_every_miss_is_invalid_credentials_after_exactly_one_hash(population: None, hashes: Hashes, case: str) -> None:
    subdomain, username, password = MISSES[case]
    hashes.calls = 0
    result = login(
        subdomain=subdomain, username=username, password=password, now=T0, ports=ports(off=frozenset({"tenant-b"}))
    )
    assert result == LoginRejected("invalid_credentials")
    assert hashes.calls == 1


def test_a_success_also_hashes_once(population: None, hashes: Hashes) -> None:
    hashes.calls = 0
    assert isinstance(
        login(
            subdomain="tenant-a", username="kim", password=PASSWORD, now=T0, ports=ports(off=frozenset({"tenant-b"}))
        ),
        LoginOk,
    )
    assert hashes.calls == 1


def test_a_miss_writes_no_token(population: None) -> None:
    for subdomain, username, password in MISSES.values():
        login(
            subdomain=subdomain, username=username, password=password, now=T0, ports=ports(off=frozenset({"tenant-b"}))
        )
    a = company_id_of("tenant-a")
    ids = list(User.for_company(a).values_list("pk", flat=True))
    assert ids  # 분모
    assert all(RefreshToken.of_user(user_id).count() == 0 for user_id in ids)


# ── 서브도메인 없는 고객사 길(UA1 — MARC-ENT-283, 처분 ⑩ ㄱ 운영 관리자 먼저) ─────────────────
# (username, password, 하나뿐인 쓸 수 있는 회사가 있는가). sole 이 없으면 회사 둘·하나뿐인 회사가 꺼짐과 같은
# 답(포트가 None — 그 판정은 apis 의 sole_company_id 가 하고 apis/test_login.py 가 진짜 포트로 잰다).
SOLE_MISSES: dict[str, tuple[str, str, bool]] = {
    "sole-wrong-password": ("kim", WRONG, True),
    "sole-unknown-username": ("nobody", PASSWORD, True),
    "sole-inactive-user": ("off", PASSWORD, True),
    "sole-unusable-password": ("blank", PASSWORD, True),
    "no-sole-company-customer": ("kim", PASSWORD, False),  # 회사 둘·하나뿐인 회사가 꺼짐
}


@pytest.mark.parametrize("case", list(SOLE_MISSES))
def test_every_miss_without_a_subdomain_is_invalid_credentials_after_exactly_one_hash(
    population: None, hashes: Hashes, case: str
) -> None:
    username, password, has_sole = SOLE_MISSES[case]
    sole = company_id_of("tenant-a") if has_sole else None
    hashes.calls = 0
    result = login(subdomain=None, username=username, password=password, now=T0, ports=ports(sole=sole))
    assert result == LoginRejected("invalid_credentials")
    assert hashes.calls == 1


def test_without_a_subdomain_a_customer_of_the_sole_company_logs_in_after_one_hash(
    population: None, hashes: Hashes
) -> None:
    a = company_id_of("tenant-a")
    kim = User.for_company(a).get(username="kim").pk
    hashes.calls = 0
    pair = pair_of(login(subdomain=None, username="kim", password=PASSWORD, now=T0, ports=ports(sole=a)))
    assert hashes.calls == 1
    assert pair.kind == "service"
    read = read_access(pair.access, secret=app_config().session_secret, now=T0)
    assert isinstance(read, AccessActive), read
    assert (read.claims.user_id, read.claims.company_id) == (str(kim), a)
    assert RefreshToken.of_user(kim).count() == 1


def test_without_a_subdomain_the_operator_comes_first(tenants: None, hashes: Hashes) -> None:
    """같은 아이디의 운영 관리자와 고객사 사용자(명령으로 겹치게 만든 경우)면 운영 관리자 길이다. 고객사 행은 보지
    않는다: 고객사의 비밀번호로는 401 이고 고객사 행의 셈은 0 그대로다."""
    a = company_id_of("tenant-a")
    ops = operator("kim")
    created = create_customer_user(
        actor_kind="admin", company_id=a, username="kim-c", name="김", password=OTHER_PASSWORD
    )
    assert isinstance(created, UserCreated)
    User.for_company(a).filter(pk=created.user_id).update(username="kim")  # 겹침 막기를 비켜 겹치게 둔다(DB 명령의 꼴)
    hashes.calls = 0
    assert login(subdomain=None, username="kim", password=OTHER_PASSWORD, now=T0, ports=ports(sole=a)) == (
        LoginRejected("invalid_credentials")
    )
    assert hashes.calls == 1
    assert lock_state(a, created.user_id) == (0, None)  # 고객사 행은 셈하지 않았다
    assert lock_state(None, ops) == (1, None)  # 운영 관리자 행에 셈
    assert pair_of(login(subdomain=None, username="kim", password=PASSWORD, now=T0, ports=ports(sole=a))).kind == (
        "admin"
    )


def test_without_a_subdomain_the_customer_lock_counts_and_a_locked_customer_is_not_hashed(
    tenants: None, hashes: Hashes
) -> None:
    a = company_id_of("tenant-a")
    kim = customer(a)
    for _ in range(5):
        assert login(subdomain=None, username="kim", password=WRONG, now=T0, ports=ports(sole=a)) == LoginRejected(
            "invalid_credentials"
        )
    assert lock_state(a, kim) == (5, T0 + LOCK)
    hashes.calls = 0
    assert login(subdomain=None, username="kim", password=PASSWORD, now=T0, ports=ports(sole=a)) == LoginRejected(
        "account_locked"
    )
    assert hashes.calls == 0


# ── 잠금의 경계(원문:48 — 5회 실패 10분) ───────────────────────────────

KINDS: list[Kind] = ["service", "admin"]


@pytest.mark.parametrize("kind", KINDS)
def test_four_failures_count_without_locking(tenants: None, kind: Kind) -> None:
    account = account_of(kind)
    fail(account, 4, T0)
    assert lock_state(account.company_id, account.user_id) == (4, None)


@pytest.mark.parametrize("kind", KINDS)
def test_the_fifth_failure_locks_for_ten_minutes(tenants: None, kind: Kind) -> None:
    account = account_of(kind)
    fail(account, 5, T0)
    assert lock_state(account.company_id, account.user_id) == (5, T0 + LOCK)


@pytest.mark.parametrize("kind", KINDS)
def test_a_locked_account_refuses_the_right_password_without_hashing(tenants: None, hashes: Hashes, kind: Kind) -> None:
    account = account_of(kind)
    fail(account, 5, T0)
    hashes.calls = 0
    assert attempt(account, PASSWORD, T0 + SECOND) == LoginRejected("account_locked")
    assert attempt(account, PASSWORD, T0 + LOCK) == LoginRejected("account_locked")  # 같은 초 = 잠김(K-B1)
    assert attempt(account, WRONG, T0 + LOCK) == LoginRejected("account_locked")
    assert hashes.calls == 0
    assert lock_state(account.company_id, account.user_id) == (5, T0 + LOCK)
    assert RefreshToken.of_user(account.user_id).count() == 0


@pytest.mark.parametrize("kind", KINDS)
def test_the_lock_lifts_one_second_after_the_expiry(tenants: None, kind: Kind) -> None:
    account = account_of(kind)
    fail(account, 5, T0)
    assert isinstance(attempt(account, PASSWORD, T0 + LOCK + SECOND), LoginOk)
    assert lock_state(account.company_id, account.user_id) == (0, None)


@pytest.mark.parametrize("kind", KINDS)
def test_a_failure_after_the_lock_lifted_counts_from_one(tenants: None, kind: Kind) -> None:
    account = account_of(kind)
    fail(account, 5, T0)
    fail(account, 1, T0 + LOCK + SECOND)
    assert lock_state(account.company_id, account.user_id) == (1, None)


@pytest.mark.parametrize("kind", KINDS)
def test_a_success_before_the_fifth_failure_resets_the_count(tenants: None, kind: Kind) -> None:
    account = account_of(kind)
    fail(account, 4, T0)
    assert isinstance(attempt(account, PASSWORD, T0 + SECOND), LoginOk)
    assert lock_state(account.company_id, account.user_id) == (0, None)
    fail(account, 4, T0 + 2 * SECOND)
    assert lock_state(account.company_id, account.user_id) == (4, None)  # 다시 넷째까지는 잠그지 않는다


# ── K-B2: 비밀번호를 보는 사이 커밋된 잠금이 이긴다 ─────────────────────


def checking_then(change: Callable[[], None]) -> Callable[[str, str], bool]:
    """맞다고 답하기 직전에 change 를 부르는 가짜 check_password(다른 요청의 커밋을 흉내 낸다)."""

    def check(password: str, encoded: str) -> bool:
        change()
        return True

    return check


def test_a_lock_committed_while_the_password_was_checked_wins(tenants: None, monkeypatch: pytest.MonkeyPatch) -> None:
    a = company_id_of("tenant-a")
    user_id = customer(a)
    User.for_company(a).filter(pk=user_id).update(login_failed_count=4)

    def lock() -> None:
        User.for_company(a).filter(pk=user_id).update(login_failed_count=5, login_expiry_at=T0 + LOCK)

    monkeypatch.setattr(login_module, "check_password", checking_then(lock))
    assert login(subdomain="tenant-a", username="kim", password=PASSWORD, now=T0, ports=ports()) == LoginRejected(
        "account_locked"
    )
    assert lock_state(a, user_id) == (5, T0 + LOCK)
    assert RefreshToken.of_user(user_id).count() == 0


def test_without_a_concurrent_lock_the_same_check_lets_in(tenants: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """분모: 아무것도 바꾸지 않는 같은 가짜면 들어가고 셈이 0 이 된다."""
    a = company_id_of("tenant-a")
    user_id = customer(a)
    User.for_company(a).filter(pk=user_id).update(login_failed_count=4)
    monkeypatch.setattr(login_module, "check_password", checking_then(lambda: None))
    assert isinstance(login(subdomain="tenant-a", username="kim", password=PASSWORD, now=T0, ports=ports()), LoginOk)
    assert lock_state(a, user_id) == (0, None)


# ── 두 길과 두 회사 ───────────────────────────────────────────────────


def test_an_operator_and_a_customer_with_the_same_username_each_reach_only_their_own_row(tenants: None) -> None:
    a = company_id_of("tenant-a")
    kim = customer(a, "kim", OTHER_PASSWORD)  # 고객사를 먼저(UA1 — 겹침 막기는 고객사 만들기 쪽뿐)
    ops = operator("kim", PASSWORD)
    # 운영 길에 고객사 사용자의 비밀번호 → 거절, 셈은 운영 관리자의 행에만
    assert login(subdomain=None, username="kim", password=OTHER_PASSWORD, now=T0, ports=ports()) == LoginRejected(
        "invalid_credentials"
    )
    assert (lock_state(None, ops)[0], lock_state(a, kim)[0]) == (1, 0)
    # 회사 길에 운영 관리자의 비밀번호 → 거절, 셈은 고객사 사용자의 행에만
    assert login(subdomain="tenant-a", username="kim", password=PASSWORD, now=T0, ports=ports()) == LoginRejected(
        "invalid_credentials"
    )
    assert (lock_state(None, ops)[0], lock_state(a, kim)[0]) == (1, 1)
    # 제 길이면 들어간다
    assert pair_of(login(subdomain=None, username="kim", password=PASSWORD, now=T0, ports=ports())).kind == "admin"
    assert (
        pair_of(login(subdomain="tenant-a", username="kim", password=OTHER_PASSWORD, now=T0, ports=ports())).kind
        == "service"
    )


def test_a_password_of_another_company_does_not_let_in(tenants: None) -> None:
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    alice_a = customer(a, "alice", PASSWORD)
    assert login(subdomain="tenant-b", username="alice", password=PASSWORD, now=T0, ports=ports()) == LoginRejected(
        "invalid_credentials"
    )
    assert lock_state(a, alice_a) == (0, None)  # 가 회사의 셈은 그대로

    alice_b = customer(b, "alice", OTHER_PASSWORD)
    assert login(subdomain="tenant-b", username="alice", password=PASSWORD, now=T0, ports=ports()) == LoginRejected(
        "invalid_credentials"
    )
    assert (lock_state(a, alice_a)[0], lock_state(b, alice_b)[0]) == (0, 1)
    pair = pair_of(login(subdomain="tenant-b", username="alice", password=OTHER_PASSWORD, now=T0, ports=ports()))
    read = read_access(pair.access, secret=app_config().session_secret, now=T0)
    assert isinstance(read, AccessActive), read
    assert (read.claims.user_id, read.claims.company_id) == (str(alice_b), b)


# ── refresh 잇기(rotate)·재사용·끊김 ──────────────────────────────────

LATER = T0 + timedelta(minutes=1)


def logged_in() -> tuple[int, int, TokenPair]:
    a = company_id_of("tenant-a")
    user_id = customer(a)
    return a, user_id, pair_of(login(subdomain="tenant-a", username="kim", password=PASSWORD, now=T0, ports=ports()))


def test_a_refresh_rotates_into_a_new_pair_of_the_same_family(tenants: None) -> None:
    _, user_id, first = logged_in()
    second = pair_of(refresh(first.refresh, now=LATER))
    assert second.refresh != first.refresh
    old, new = refresh_claims_of(first.refresh), refresh_claims_of(second.refresh)
    assert new.family == old.family
    assert new.jti != old.jti
    assert RefreshToken.by_jti(old.jti).values_list("used_at", flat=True).get() == LATER
    assert RefreshToken.of_user(user_id).count() == 2
    assert family_revoked(old.family) == [False, False]


def test_a_reused_refresh_revokes_the_whole_family(tenants: None) -> None:
    _, _, first = logged_in()
    second = pair_of(refresh(first.refresh, now=LATER))
    assert refresh(first.refresh, now=LATER + SECOND) == RefreshRejected("reused")
    family = refresh_claims_of(first.refresh).family
    assert family_revoked(family) == [True, True]  # 새 행도
    assert refresh(second.refresh, now=LATER + 2 * SECOND) == RefreshRejected("revoked")


def test_a_revoked_refresh_is_rejected(tenants: None) -> None:
    _, _, first = logged_in()
    assert revoke(first.refresh, now=LATER) == Revoked()
    assert revoke(first.refresh, now=LATER) == Revoked()  # 멱등
    assert refresh(first.refresh, now=LATER) == RefreshRejected("revoked")


def test_a_refresh_of_a_deactivated_user_is_inactive_and_revokes_the_family(tenants: None) -> None:
    a, user_id, first = logged_in()
    User.for_company(a).filter(pk=user_id).update(is_active=False)
    assert refresh(first.refresh, now=LATER) == RefreshRejected("inactive")
    assert family_revoked(refresh_claims_of(first.refresh).family) == [True]
    assert RefreshToken.of_user(user_id).count() == 1


def test_an_expired_refresh_is_rejected(tenants: None) -> None:
    _, _, first = logged_in()
    assert refresh(first.refresh, now=first.refresh_expires_at) == RefreshRejected("expired")


def test_garbage_is_an_unknown_refresh(tenants: None) -> None:
    assert refresh("garbage", now=T0) == RefreshRejected("unknown")
    assert revoke("garbage", now=T0) == RefreshRejected("unknown")


def forged(claims: RefreshClaims, *, user_id: int | None = None, company_id: int | None = None) -> str:
    """진짜 비밀로 서명한, 주장 한 칸을 바꾼 refresh(비밀이 샌 경우 — K-B3 의 바닥)."""
    changed = new_refresh_claims(
        user_id=str(user_id) if user_id is not None else claims.user_id,
        company_id=company_id if company_id is not None else claims.company_id,
        jti=claims.jti,
        family=claims.family,
        now=claims.issued_at,
    )
    return sign_refresh(changed, secret=app_config().session_secret)


def test_a_forged_company_in_a_refresh_reaches_no_user(tenants: None) -> None:
    """K-B3: 사용자는 refresh 주장의 company_id 로 읽는다(행의 user 를 따라가지 않는다)."""
    b = company_id_of("tenant-b")
    _, user_id, first = logged_in()
    claims = refresh_claims_of(first.refresh)
    result = refresh(forged(claims, company_id=b), now=LATER)
    assert isinstance(result, RefreshRejected), result
    assert RefreshToken.of_user(user_id).count() == 1  # 새 행 0


def test_a_forged_user_in_a_refresh_is_unknown(tenants: None) -> None:
    b = company_id_of("tenant-b")
    other = customer(b, "lee")
    _, user_id, first = logged_in()
    claims = refresh_claims_of(first.refresh)
    assert refresh(forged(claims, user_id=other, company_id=b), now=LATER) == RefreshRejected("unknown")
    assert refresh(forged(claims, user_id=other), now=LATER) == RefreshRejected("unknown")
    assert (RefreshToken.of_user(user_id).count(), RefreshToken.of_user(other).count()) == (1, 0)
    assert family_revoked(claims.family) == [False]  # 남의 jti 로는 그 계보를 건드리지 못한다


def test_an_operator_refresh_rotates(tenants: None) -> None:
    user_id = operator()
    first = pair_of(login(subdomain=None, username="ops", password=PASSWORD, now=T0, ports=ports()))
    second = pair_of(refresh(first.refresh, now=LATER))
    assert second.kind == "admin"
    assert refresh_claims_of(second.refresh).company_id is None
    assert RefreshToken.of_user(user_id).count() == 2


def test_logging_out_with_an_expired_refresh_still_revokes(tenants: None) -> None:
    _, user_id, first = logged_in()
    second = pair_of(refresh(first.refresh, now=LATER))
    much_later = T0 + timedelta(days=8)
    assert revoke(first.refresh, now=much_later) == Revoked()
    assert family_revoked(refresh_claims_of(second.refresh).family) == [True, True]
    assert RefreshToken.of_user(user_id).filter(revoked_at=much_later).count() == 2


# ── D9(CA): 감사 줄(note)의 extra 가 JSON 포매터의 글자에 실린다 ──────────────


def test_the_real_audit_note_reaches_the_json_text() -> None:
    """제품의 note(user/service/services/login.py)가 낸 기록을 이 포매터로 글자로 바꿔 본다(D9 의 빨강 자리)."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("esgapi.auth")
    logger.addHandler(handler)
    old_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        user = SimpleNamespace(pk=42, company_id=7, kind="service", username="kim")
        login_module.note("password_reset", user, now=T0, actor_user_id=9)  # pyright: ignore[reportArgumentType]
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    parsed = json.loads(stream.getvalue().strip())
    assert (parsed["event"], parsed["user_id"], parsed["company_id"], parsed["user_kind"]) == (
        "password_reset",
        42,
        7,
        "service",
    )
    assert (parsed["actor_user_id"], parsed["target_user_id"]) == (9, 42)


# ── AU1a: 감사 줄(note → core 의 record_event) ───────────────────────────────
# 줄은 표시(mark) 뒤의 것만 센다 — 계정을 만든 줄(user_created, 명령 꼴 → command)은 앞에 남는다.


def audit_mark() -> int:
    return AuditEventRow.unscoped.aggregate(top=Max("pk"))["top"] or 0


def audit_after(mark: int) -> list[AuditEventRow]:
    return list(AuditEventRow.unscoped.filter(pk__gt=mark).order_by("pk"))


def login_line(line: AuditEventRow) -> tuple[object, ...]:
    return (line.action, line.event, line.result, line.reason, line.actor_kind, line.company_id)


# MISSES 의 경우마다: (까닭, 행위자 갈래, 사람의 아이디(None = 누구인지 모름), 회사의 서브도메인(None = 회사 칸 NULL))
MISS_LINES: dict[str, tuple[str, str, str | None, str | None]] = {
    "wrong-password": ("wrong_password", "service", "kim", "tenant-a"),
    "unknown-username": ("unknown_user", "anonymous", None, "tenant-a"),
    "unknown-company": ("unknown_user", "anonymous", None, None),
    "inactive-company": ("unknown_user", "anonymous", None, None),  # 꺼진 회사는 찾지 못한 회사다(개정 1 N6)
    "inactive-user": ("inactive_user", "service", "off", "tenant-a"),
    "unusable-password": ("wrong_password", "service", "blank", "tenant-a"),
    "operator-unknown": ("unknown_user", "anonymous", None, None),
    "operator-inactive": ("inactive_user", "admin", "ops-off", None),
    "operator-wrong-password": ("wrong_password", "admin", "ops", None),
}


def test_the_audit_miss_table_covers_every_miss() -> None:
    assert set(MISS_LINES) == set(MISSES)  # 분모: 경우표 아홉 그대로


@pytest.mark.parametrize("case", list(MISSES))
def test_every_miss_writes_one_failure_line_and_still_hashes_once(population: None, hashes: Hashes, case: str) -> None:
    subdomain, username, password = MISSES[case]
    reason, actor_kind, who, company = MISS_LINES[case]
    mark = audit_mark()
    hashes.calls = 0
    result = login(
        subdomain=subdomain, username=username, password=password, now=T0, ports=ports(off=frozenset({"tenant-b"}))
    )
    assert result == LoginRejected("invalid_credentials")
    assert hashes.calls == 1  # 감사 쓰기는 해시를 돌지 않는다(K-B8)
    lines = audit_after(mark)
    company_id = None if company is None else company_id_of(company)
    assert [login_line(line) for line in lines] == [
        ("login", "login_failed", "failure", reason, actor_kind, company_id)
    ]
    line = lines[0]
    assert line.at == T0
    if who is None:
        # 누구인지 모름: 사람·대상 NULL, 넣은 아이디 글자 0(처분 ⑧)
        assert (line.actor_user_id, line.target_kind, line.target_id, line.target_label) == (None, None, None, None)
        assert line.detail == {}
        assert username not in json.dumps(
            [str(v) for v in AuditEventRow.unscoped.filter(pk=line.pk).values()[0].values()]
        )
    else:
        found = User.unscoped.get(username=who, company_id=company_id)
        assert (line.actor_user_id, line.target_kind, line.target_id, line.target_label) == (
            found.pk,
            "user",
            found.pk,
            who,
        )


def test_an_unknown_username_without_a_subdomain_is_set_on_the_sole_company(population: None) -> None:
    a = company_id_of("tenant-a")
    mark = audit_mark()
    assert login(subdomain=None, username="ghost-1a2b", password=PASSWORD, now=T0, ports=ports(sole=a)) == (
        LoginRejected("invalid_credentials")
    )
    lines = audit_after(mark)
    assert [login_line(line) for line in lines] == [
        ("login", "login_failed", "failure", "unknown_user", "anonymous", a)
    ]
    assert "ghost-1a2b" not in str(AuditEventRow.unscoped.filter(pk=lines[0].pk).values()[0])


@pytest.mark.parametrize("kind", KINDS)
def test_a_success_writes_one_line_of_the_person_on_their_company(tenants: None, kind: Kind) -> None:
    account = account_of(kind)
    mark = audit_mark()
    assert isinstance(attempt(account, PASSWORD, T0), LoginOk)
    lines = audit_after(mark)
    assert [login_line(line) for line in lines] == [
        ("login", "login_succeeded", "success", None, kind, account.company_id)
    ]
    assert (lines[0].actor_user_id, lines[0].target_id, lines[0].target_label) == (
        account.user_id,
        account.user_id,
        account.username,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_a_locked_account_writes_one_locked_line_per_attempt_without_hashing(
    tenants: None, hashes: Hashes, kind: Kind
) -> None:
    account = account_of(kind)
    fail(account, 5, T0)
    mark = audit_mark()
    hashes.calls = 0
    assert attempt(account, PASSWORD, T0 + SECOND) == LoginRejected("account_locked")
    assert hashes.calls == 0
    assert [login_line(line) for line in audit_after(mark)] == [
        ("login", "login_locked", "failure", "account_locked", kind, account.company_id)
    ]


def test_five_failures_write_five_lines(tenants: None) -> None:
    account = account_of("service")
    mark = audit_mark()
    fail(account, 5, T0)
    assert [line.reason for line in audit_after(mark)] == ["wrong_password"] * 5


def test_a_lock_committed_during_the_check_writes_a_locked_line(tenants: None, monkeypatch: pytest.MonkeyPatch) -> None:
    a = company_id_of("tenant-a")
    user_id = customer(a)

    def lock() -> None:
        User.for_company(a).filter(pk=user_id).update(login_failed_count=5, login_expiry_at=T0 + LOCK)

    monkeypatch.setattr(login_module, "check_password", checking_then(lock))
    mark = audit_mark()
    assert login(subdomain="tenant-a", username="kim", password=PASSWORD, now=T0, ports=ports()) == LoginRejected(
        "account_locked"
    )
    assert [login_line(line) for line in audit_after(mark)] == [
        ("login", "login_locked", "failure", "account_locked", "service", a)
    ]


# 로그아웃: 블록이 닫힌 뒤 감사 줄 하나와 로그 한 줄(event 뿐 — 개정 1 B6)


@pytest.mark.parametrize("kind", KINDS)
def test_a_logout_writes_one_line_of_the_refresh_person(
    tenants: None, kind: Kind, caplog: pytest.LogCaptureFixture
) -> None:
    account = account_of(kind)
    pair = pair_of(attempt(account, PASSWORD, T0))
    mark = audit_mark()
    with caplog.at_level(logging.INFO, logger="esgapi.auth"):
        assert revoke(pair.refresh, now=LATER) == Revoked()
    lines = audit_after(mark)
    assert [
        (line.action, line.event, line.result, line.actor_kind, line.actor_user_id, line.company_id) for line in lines
    ] == [("logout", "logout", "success", kind, account.user_id, account.company_id)]
    assert (lines[0].at, lines[0].target_kind, lines[0].target_label) == (LATER, None, None)
    logged = [r for r in caplog.records if r.name == "esgapi.auth" and getattr(r, "event", None) == "logout"]
    assert len(logged) == 1
    assert not hasattr(logged[0], "user_id")  # user 를 읽지 않는다 — 칸은 event 뿐


def test_an_expired_or_already_revoked_logout_still_writes_a_line(tenants: None) -> None:
    _, _, pair = logged_in()
    mark = audit_mark()
    much_later = T0 + timedelta(days=8)
    assert revoke(pair.refresh, now=much_later) == Revoked()  # 만료
    assert revoke(pair.refresh, now=much_later) == Revoked()  # 이미 끊김
    assert [line.event for line in audit_after(mark)] == ["logout", "logout"]


def test_an_unknown_token_logout_writes_nothing(tenants: None) -> None:
    mark = audit_mark()
    assert revoke("garbage", now=T0) == RefreshRejected("unknown")
    assert audit_after(mark) == []


def test_a_refresh_writes_no_audit_line(tenants: None) -> None:
    _, _, pair = logged_in()
    mark = audit_mark()
    assert isinstance(refresh(pair.refresh, now=LATER), RefreshOk)
    assert audit_after(mark) == []  # refresh 잇기는 기록하지 않는다(처분 ⑥ — 잡음)


# 깔때기: 사건 이름 → 행동 표가 제품의 note("…") 글자 전부를 덮고, 행동은 아홉 가운데 하나다.

USER_SERVICE = Path(__file__).resolve().parents[3] / "service"


def note_names() -> set[str]:
    names: set[str] = set()
    for path in sorted(USER_SERVICE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            called = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            first = node.args[0]
            if called == "note" and isinstance(first, ast.Constant) and isinstance(first.value, str):
                names.add(first.value)
    return names


def test_every_note_name_has_an_action_and_every_action_is_one_of_nine() -> None:
    names = note_names()
    assert len(names) == 8, names  # 분모: 로그인 셋·로그아웃·만들기·초기화·바꾸기·수정
    assert names == set(login_module.EVENT_ACTIONS)
    assert set(login_module.EVENT_ACTIONS.values()) <= set(AUDIT_ACTIONS)
