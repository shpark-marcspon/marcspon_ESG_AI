"""비밀번호 바꾸기와 초기화(업무 층, 주인 역할 연결).

바꾸기의 현재 비밀번호 확인은 로그인과 같은 잠금 규칙이다(처분 B9 — 셈은 record_password_attempt 하나).
해시는 MD5 로 바꿔 빠르게 돈다(이 파일의 autouse 고정물). 해시 횟수는 services/test_login.py 와 같은 꼴로 센다.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth.hashers import MD5PasswordHasher, check_password
from django.db.models import Max
from django.test import override_settings

from esgapi.core.auth.principal import Kind
from esgapi.core.models import AuditEventRow
from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.models import RefreshToken, User
from esgapi.user.service.actions.password import change_password, reset_password
from esgapi.user.service.services.login import LoginPorts, login
from esgapi.user.service.services.user import ResetPrepared, create_customer_user, create_operator, prepare_reset
from esgapi.user.service.utils.login import (
    LoginOk,
    LoginRejected,
    PasswordChangeRejected,
    PasswordReset,
    TokenPair,
    UserCreated,
    UserNotFound,
)

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
LATER = T0 + timedelta(minutes=1)
LOCK = timedelta(seconds=600)
PASSWORD = "Blue-Harbor-7310"
NEW_PASSWORD = "Green-Valley-4821"
WRONG = "Wrong-Lantern-5932"
KINDS: list[Kind] = ["service", "admin"]


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
    counter = Hashes()
    for name in ("encode", "verify"):
        monkeypatch.setattr(MD5PasswordHasher, name, counter.counted(getattr(MD5PasswordHasher, name)))
    return counter


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive), found
    return found.company.id


def ports() -> LoginPorts:
    def company_id_of_active(subdomain: str) -> int | None:
        found = find_company(subdomain)
        return found.company.id if isinstance(found, CompanyActive) else None

    return LoginPorts(company_id_of=company_id_of_active, sole_company_id=lambda: None)


@dataclass(frozen=True)
class Account:
    company_id: int | None
    user_id: int
    subdomain: str | None
    username: str


def make(kind: Kind, username: str) -> Account:
    if kind == "admin":
        created = create_operator(username=username, name="운영자", password=PASSWORD)
        assert isinstance(created, UserCreated), created
        return Account(None, created.user_id, None, username)
    a = company_id_of("tenant-a")
    created = create_customer_user(
        actor_kind="admin", company_id=a, username=username, name="김담당", password=PASSWORD
    )
    assert isinstance(created, UserCreated), created
    return Account(a, created.user_id, "tenant-a", username)


def row(account: Account) -> User:
    if account.company_id is None:
        return User.admin_by_id(account.user_id).get()
    return User.for_company(account.company_id).get(pk=account.user_id)


def log_in(account: Account, password: str = PASSWORD, now: datetime = T0) -> LoginOk | LoginRejected:
    return login(subdomain=account.subdomain, username=account.username, password=password, now=now, ports=ports())


def change(account: Account, current: str, new: str = NEW_PASSWORD, now: datetime = T0) -> object:
    return change_password(company_id=account.company_id, user_id=account.user_id, current=current, new=new, now=now)


def unrevoked(user_id: int) -> int:
    return RefreshToken.of_user(user_id).filter(revoked_at__isnull=True).count()


# ── 바꾸기: 현재 비밀번호 확인의 잠금 ─────────────────────────────────


@pytest.mark.parametrize("kind", KINDS)
def test_a_wrong_current_password_counts_like_a_login(tenants: None, hashes: Hashes, kind: Kind) -> None:
    account = make(kind, "kim")
    for _ in range(4):
        assert change(account, WRONG) == PasswordChangeRejected("current_password_mismatch")
    assert (row(account).login_failed_count, row(account).login_expiry_at) == (4, None)

    assert change(account, WRONG) == PasswordChangeRejected("current_password_mismatch")
    assert (row(account).login_failed_count, row(account).login_expiry_at) == (5, T0 + LOCK)

    hashes.calls = 0
    assert change(account, PASSWORD, now=T0 + timedelta(seconds=1)) == PasswordChangeRejected("account_locked")
    assert hashes.calls == 0
    assert log_in(account, now=T0 + timedelta(seconds=1)) == LoginRejected("account_locked")
    assert hashes.calls == 0
    current = row(account)
    assert (current.login_failed_count, current.login_expiry_at, current.is_initial) == (5, T0 + LOCK, True)
    assert check_password(PASSWORD, current.password)


@pytest.mark.parametrize("kind", KINDS)
def test_a_login_lock_also_blocks_a_change(tenants: None, kind: Kind) -> None:
    account = make(kind, "kim")
    for _ in range(5):
        assert log_in(account, WRONG) == LoginRejected("invalid_credentials")
    assert change(account, PASSWORD) == PasswordChangeRejected("account_locked")


# ── 바꾸기: 성공 ──────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", KINDS)
def test_a_change_issues_a_fresh_pair_and_revokes_every_earlier_refresh(tenants: None, kind: Kind) -> None:
    account = make(kind, "kim")
    other = make(kind, "lee")
    for _ in range(2):  # 계보 둘
        assert isinstance(log_in(account), LoginOk)
    assert isinstance(log_in(other), LoginOk)
    assert (unrevoked(account.user_id), unrevoked(other.user_id)) == (2, 1)  # 분모

    pair = change(account, PASSWORD, now=LATER)
    assert isinstance(pair, TokenPair), pair
    assert pair.is_initial is False
    assert pair.kind == ("admin" if kind == "admin" else "service")
    current = row(account)
    assert current.is_initial is False
    assert check_password(NEW_PASSWORD, current.password)
    assert not check_password(PASSWORD, current.password)
    assert RefreshToken.of_user(account.user_id).filter(revoked_at=LATER).count() == 2  # 옛 계보 둘
    assert unrevoked(account.user_id) == 1  # 새 짝의 행 하나
    assert unrevoked(other.user_id) == 1  # 남의 행은 그대로
    assert isinstance(log_in(account, NEW_PASSWORD, now=LATER), LoginOk)


@pytest.mark.parametrize(
    "new",
    ["short1!", "Long-" * 205],
    ids=["short", "too-long"],
)
def test_a_new_password_the_validators_refuse_changes_nothing(tenants: None, new: str) -> None:
    account = make("service", "kim")
    assert isinstance(log_in(account), LoginOk)
    before = row(account).password
    result = change(account, PASSWORD, new)
    assert isinstance(result, PasswordChangeRejected), result
    assert result.reason == "password_rejected"
    assert result.messages
    assert all(new not in message for message in result.messages)
    current = row(account)
    assert (current.password, current.is_initial) == (before, True)
    assert unrevoked(account.user_id) == 1


@pytest.mark.parametrize(
    "new",
    ["password123", "12345678901"],
    ids=["common", "numeric"],
)
def test_a_new_password_the_removed_validators_refused_is_now_accepted(tenants: None, new: str) -> None:
    # 결정 MARC-ENT-282 가 바꾼 동작: 흔함·숫자만(전엔 password_rejected)을 이제 받는다 — 바꾸기가 되고 새 짝이 나온다.
    account = make("service", "kim")
    assert isinstance(log_in(account), LoginOk)
    pair = change(account, PASSWORD, new)
    assert isinstance(pair, TokenPair), pair
    assert pair.is_initial is False
    current = row(account)
    assert current.is_initial is False
    assert check_password(new, current.password)
    assert unrevoked(account.user_id) == 1  # 새 짝의 행 하나(옛 계보는 끊김)


def test_the_same_password_again_is_refused(tenants: None) -> None:
    account = make("service", "kim")
    result = change(account, PASSWORD, PASSWORD)
    assert isinstance(result, PasswordChangeRejected), result
    assert result.reason == "password_rejected"
    assert result.messages
    assert row(account).is_initial is True


def test_a_change_for_a_user_of_another_company_is_unavailable(tenants: None) -> None:
    account = make("service", "kim")
    b = company_id_of("tenant-b")
    assert change_password(
        company_id=b, user_id=account.user_id, current=PASSWORD, new=NEW_PASSWORD, now=T0
    ) == PasswordChangeRejected("user_unavailable")
    assert change_password(
        company_id=None, user_id=account.user_id, current=PASSWORD, new=NEW_PASSWORD, now=T0
    ) == PasswordChangeRejected("user_unavailable")
    assert row(account).login_failed_count == 0


# ── 초기화 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", KINDS)
def test_a_reset_restores_the_initial_state_and_revokes_every_refresh(tenants: None, kind: Kind) -> None:
    account = make(kind, "kim")
    other = make(kind, "lee")
    assert isinstance(change(account, PASSWORD), TokenPair)  # is_initial 거짓, 행 하나
    assert isinstance(log_in(account, NEW_PASSWORD), LoginOk)
    assert isinstance(log_in(other), LoginOk)
    for _ in range(5):
        assert log_in(account, WRONG) == LoginRejected("invalid_credentials")
    assert row(account).login_expiry_at == T0 + LOCK  # 분모: 잠겼다

    prepared = prepare_reset(company_id=account.company_id, username="kim", password="Quiet-Meadow-2604")
    assert isinstance(prepared, ResetPrepared), prepared
    assert reset_password(
        actor_kind="admin",
        company_id=prepared.company_id,
        user_id=prepared.user_id,
        password_hash=prepared.password_hash,
        now=LATER,
    ) == PasswordReset(account.user_id)
    current = row(account)
    assert (current.is_initial, current.login_failed_count, current.login_expiry_at) == (True, 0, None)
    assert check_password("Quiet-Meadow-2604", current.password)
    assert unrevoked(account.user_id) == 0
    assert unrevoked(other.user_id) == 1
    assert isinstance(log_in(account, "Quiet-Meadow-2604", now=LATER), LoginOk)


def test_a_reset_in_the_wrong_company_finds_no_user(tenants: None) -> None:
    account = make("service", "kim")
    assert isinstance(log_in(account), LoginOk)
    prepared = prepare_reset(company_id=account.company_id, username="kim", password="Quiet-Meadow-2604")
    assert isinstance(prepared, ResetPrepared), prepared
    b = company_id_of("tenant-b")
    for company_id in (b, None):
        assert (
            reset_password(
                actor_kind="admin",
                company_id=company_id,
                user_id=account.user_id,
                password_hash=prepared.password_hash,
                now=LATER,
            )
            == UserNotFound()
        )
    current = row(account)
    assert check_password(PASSWORD, current.password)
    assert unrevoked(account.user_id) == 1


def test_an_exchange_user_is_never_reset(tenants: None) -> None:
    """(CA·D5) 교환이 만든 행(쓸 수 없는 비밀번호)은 명령의 준비도 초기화 자체도 UserNotFound — 행 그대로."""
    from esgapi.user.service.services.user import upsert_user
    from esgapi.user.service.utils.tokens import EdkClaims

    a = company_id_of("tenant-a")
    claims = EdkClaims(
        issuer="https://edk.test", external_id="edk-user-1", tenant_id="tenant-a", role="editor", name="김"
    )
    upsert_user(a, claims)
    edk = User.for_company(a).get(username="edk-user-1")
    assert not edk.has_usable_password()  # 분모
    assert prepare_reset(company_id=a, username="edk-user-1", password="Quiet-Meadow-2604") == UserNotFound()
    prepared = prepare_reset(company_id=a, username=make("service", "kim") and "kim", password="Quiet-Meadow-2604")
    assert isinstance(prepared, ResetPrepared)  # 분모: 비밀번호 사용자는 준비된다
    assert (
        reset_password(
            actor_kind="admin", company_id=a, user_id=edk.pk, password_hash=prepared.password_hash, now=LATER
        )
        == UserNotFound()
    )
    assert User.for_company(a).get(pk=edk.pk).password == edk.password


def test_prepare_reset_finds_only_its_own_place(tenants: None) -> None:
    make("service", "kim")
    b = company_id_of("tenant-b")
    assert prepare_reset(company_id=b, username="kim", password="Quiet-Meadow-2604") == UserNotFound()
    assert prepare_reset(company_id=None, username="kim", password="Quiet-Meadow-2604") == UserNotFound()


# ── AU1a: 초기화·바꾸기의 감사 줄(setting_change) ────────────────────────────


def audit_mark() -> int:
    return AuditEventRow.unscoped.aggregate(top=Max("pk"))["top"] or 0


def audit_after(mark: int) -> list[tuple[object, ...]]:
    """표시 뒤의 감사 줄: (행동, 사건, 결과, 행위자 갈래, 행위자 id, 회사, 대상 갈래, 대상 id, 대상 이름, detail)."""
    return [
        (r.action, r.event, r.result, r.actor_kind, r.actor_user_id, r.company_id, r.target_kind, r.target_id,
         r.target_label, r.detail)
        for r in AuditEventRow.unscoped.filter(pk__gt=mark).order_by("pk")
    ]  # fmt: skip


def reset(account: Account, *, actor_user_id: int | None) -> object:
    prepared = prepare_reset(company_id=account.company_id, username=account.username, password="Quiet-Meadow-2604")
    assert isinstance(prepared, ResetPrepared), prepared
    return reset_password(
        actor_kind="admin",
        company_id=prepared.company_id,
        user_id=prepared.user_id,
        password_hash=prepared.password_hash,
        now=LATER,
        actor_user_id=actor_user_id,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_a_reset_over_http_is_the_operators_line_and_by_command_a_command_line(tenants: None, kind: Kind) -> None:
    account = make(kind, "kim")
    mark = audit_mark()
    assert reset(account, actor_user_id=5) == PasswordReset(account.user_id)
    assert reset(account, actor_user_id=None) == PasswordReset(account.user_id)
    line = ("setting_change", "password_reset", "success")
    target: tuple[object, ...] = (account.company_id, "user", account.user_id, "kim", {})
    assert audit_after(mark) == [(*line, "admin", 5, *target), (*line, "command", None, *target)]
    assert set(AuditEventRow.unscoped.filter(pk__gt=mark).values_list("at", flat=True)) == {LATER}


def test_a_reset_that_finds_no_user_writes_no_line(tenants: None) -> None:
    account = make("service", "kim")
    prepared = prepare_reset(company_id=account.company_id, username="kim", password="Quiet-Meadow-2604")
    assert isinstance(prepared, ResetPrepared), prepared
    mark = audit_mark()
    assert (
        reset_password(
            actor_kind="admin",
            company_id=company_id_of("tenant-b"),
            user_id=account.user_id,
            password_hash=prepared.password_hash,
            now=LATER,
            actor_user_id=5,
        )
        == UserNotFound()
    )
    assert audit_after(mark) == []


@pytest.mark.parametrize("kind", KINDS)
def test_a_change_is_the_persons_own_line(tenants: None, kind: Kind) -> None:
    account = make(kind, "kim")
    mark = audit_mark()
    assert isinstance(change(account, PASSWORD), TokenPair)
    assert audit_after(mark) == [
        ("setting_change", "password_changed", "success", kind, account.user_id, account.company_id, "user",
         account.user_id, "kim", {}),
    ]  # fmt: skip


def test_a_refused_change_writes_no_password_line(tenants: None) -> None:
    account = make("service", "kim")
    mark = audit_mark()
    assert isinstance(change(account, WRONG), PasswordChangeRejected)
    assert isinstance(change(account, PASSWORD, new="Short-1"), PasswordChangeRejected)
    assert isinstance(change(account, PASSWORD, new=PASSWORD), PasswordChangeRejected)
    assert audit_after(mark) == []
