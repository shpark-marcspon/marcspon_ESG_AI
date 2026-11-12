"""계정 수정 action(UA1 — update_customer_user)의 업무 층(주인 역할 연결).

권한이 첫 줄이고, 대상은 그 회사의 고객사 사용자(쓸 수 있는 비밀번호)뿐이며, is_active 가 바뀌면 그 사람의 끊기지 않은
refresh 를 모두 끊는다(처분 ②·개정 2 N1). 기록 줄에는 바뀐 칸의 이름만 싣는다.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.db.models import Max
from django.test import override_settings

from esgapi.core.models import AuditEventRow
from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.models import RefreshToken, User
from esgapi.user.service.actions.account import update_customer_user
from esgapi.user.service.permissions.user import Forbidden
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated, UserNotFound, UserUpdated

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
PASSWORD = "Blue-Harbor-7310"


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive), found
    return found.company.id


def customer(company_id: int, username: str) -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name="김담당", password=PASSWORD
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def issued(user_id: int) -> None:
    RefreshToken.issue(jti=uuid4(), family=uuid4(), user_id=user_id, issued_at=T0, expires_at=T0 + timedelta(days=7))


def unrevoked(user_id: int) -> int:
    return RefreshToken.of_user(user_id).filter(revoked_at__isnull=True).count()


def update(company_id: int, user_id: int, *, name: str | None = None, is_active: bool | None = None) -> object:
    return update_customer_user(
        actor_kind="admin", company_id=company_id, user_id=user_id, name=name, is_active=is_active, now=T0
    )


def state(*user_ids: int) -> list[Any]:
    return [
        (r.pk, r.name, r.is_active, r.is_initial, r.password, r.login_failed_count, r.login_expiry_at)
        for r in User.unscoped.filter(pk__in=user_ids).order_by("id")
    ] + [(r.jti, r.revoked_at) for user_id in user_ids for r in RefreshToken.of_user(user_id).order_by("jti")]


def test_deactivating_cuts_only_that_users_refresh_at_that_moment(tenants: None) -> None:
    a = company_id_of("tenant-a")
    kim, lee = customer(a, "kim"), customer(a, "lee")
    for user_id in (kim, kim, lee):
        issued(user_id)
    assert update(a, kim, is_active=False) == UserUpdated(kim)
    assert User.for_company(a).get(pk=kim).is_active is False
    assert RefreshToken.of_user(kim).filter(revoked_at=T0).count() == 2
    assert (unrevoked(kim), unrevoked(lee)) == (0, 1)  # 남의 행은 그대로


def test_reactivating_cuts_a_refresh_left_uncut_but_the_same_value_does_not(tenants: None) -> None:
    a = company_id_of("tenant-a")
    kim, lee = customer(a, "kim"), customer(a, "lee")
    issued(kim)
    issued(lee)
    User.for_company(a).filter(pk=kim).update(is_active=False)
    assert update(a, lee, is_active=True) == UserUpdated(lee)  # 같은 값
    assert unrevoked(lee) == 1
    assert update(a, kim, is_active=True) == UserUpdated(kim)  # 거짓 → 참(개정 2 N1)
    assert (unrevoked(kim), User.for_company(a).get(pk=kim).is_active) == (0, True)


def test_a_rename_keeps_every_other_field_and_every_refresh(tenants: None) -> None:
    a = company_id_of("tenant-a")
    kim = customer(a, "kim")
    issued(kim)
    before = User.for_company(a).get(pk=kim)
    assert update(a, kim, name="김새") == UserUpdated(kim)
    after = User.for_company(a).get(pk=kim)
    assert after.name == "김새"
    assert (after.is_active, after.is_initial, after.password, after.login_failed_count) == (
        before.is_active,
        before.is_initial,
        before.password,
        before.login_failed_count,
    )
    assert unrevoked(kim) == 1


def test_a_non_operator_is_forbidden_before_anything_is_read(tenants: None, monkeypatch: pytest.MonkeyPatch) -> None:
    a = company_id_of("tenant-a")
    kim = customer(a, "kim")
    issued(kim)
    before = state(kim)
    from esgapi.user.service.actions import account

    def no_lock(*_args: object) -> None:
        raise AssertionError("권한 앞에서 행을 읽었다")

    monkeypatch.setattr(account.selectors, "lock_account", no_lock)
    result = update_customer_user(actor_kind="service", company_id=a, user_id=kim, name="김", is_active=False, now=T0)
    assert result == Forbidden("user_update")
    assert state(kim) == before


def test_rows_outside_the_company_or_not_customers_are_not_found_and_unchanged(tenants: None) -> None:
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    kim, park = customer(a, "kim"), customer(b, "park")
    created = create_operator(username="ops", name="운영자", password=PASSWORD)
    assert isinstance(created, UserCreated)
    ops = created.user_id
    edk = customer(a, "edk-user-1")
    User.for_company(a).filter(pk=edk).update(password=make_password(None))  # 교환이 만든 행의 꼴(쓸 수 없는 값)
    for user_id in (kim, park, ops, edk):
        issued(user_id)
    before = state(kim, park, ops, edk)
    for company_id, user_id in ((a, park), (b, kim), (a, ops), (a, edk), (a, max(kim, park, ops, edk) + 1000)):
        assert update(company_id, user_id, name="남", is_active=False) == UserNotFound(), (company_id, user_id)
    assert state(kim, park, ops, edk) == before
    assert update(a, kim, is_active=False) == UserUpdated(kim)  # 분모: 맞는 회사의 고객사 사용자는 된다


def test_the_log_line_names_the_changed_fields_only(tenants: None, caplog: pytest.LogCaptureFixture) -> None:
    a = company_id_of("tenant-a")
    kim = customer(a, "kim")
    with caplog.at_level("INFO", logger="esgapi.auth"):
        update_customer_user(
            actor_kind="admin", company_id=a, user_id=kim, name="김비밀이름", is_active=False, now=T0, actor_user_id=7
        )
        update_customer_user(
            actor_kind="admin", company_id=a, user_id=kim, name="김비밀이름", is_active=None, now=T0, actor_user_id=7
        )
    records = [r for r in caplog.records if r.getMessage() == "user_updated"]
    assert [getattr(r, "changed_fields", None) for r in records] == [["name", "is_active"], []]
    assert [(getattr(r, "actor_user_id", None), getattr(r, "target_user_id", None)) for r in records] == [(7, kim)] * 2
    assert "김비밀이름" not in caplog.text


# ── AU1a: 수정의 감사 줄(setting_change · user_updated — 바뀐 칸의 이름만) ─────────


def audit_mark() -> int:
    return AuditEventRow.unscoped.aggregate(top=Max("pk"))["top"] or 0


def audit_after(mark: int) -> list[tuple[object, ...]]:
    """표시 뒤의 감사 줄: (행동, 사건, 결과, 행위자 갈래, 행위자 id, 회사, 대상 갈래, 대상 id, 대상 이름, detail)."""
    return [
        (r.action, r.event, r.result, r.actor_kind, r.actor_user_id, r.company_id, r.target_kind, r.target_id,
         r.target_label, r.detail)
        for r in AuditEventRow.unscoped.filter(pk__gt=mark).order_by("pk")
    ]  # fmt: skip


def test_an_update_over_http_names_the_changed_fields_and_by_command_is_a_command_line(tenants: None) -> None:
    a = company_id_of("tenant-a")
    kim = customer(a, "kim")
    mark = audit_mark()
    assert update_customer_user(
        actor_kind="admin", company_id=a, user_id=kim, name="김새이름", is_active=False, now=T0, actor_user_id=5
    ) == UserUpdated(kim)
    assert update(a, kim, name="김새이름", is_active=False) == UserUpdated(kim)  # 명령 꼴(사람 id 없음), 같은 값
    line = ("setting_change", "user_updated", "success")
    assert audit_after(mark) == [
        (*line, "admin", 5, a, "user", kim, "kim", {"changed_fields": ["name", "is_active"]}),
        (*line, "command", None, a, "user", kim, "kim", {"changed_fields": []}),  # 멱등도 한 줄(개정 1 N6)
    ]
    assert "김새이름" not in str(AuditEventRow.unscoped.filter(pk__gt=mark).values_list("detail", "target_label"))


def test_a_refused_update_writes_no_line(tenants: None, monkeypatch: pytest.MonkeyPatch) -> None:
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    kim = customer(a, "kim")
    mark = audit_mark()
    assert update(b, kim, name="남의") == UserNotFound()
    assert isinstance(
        update_customer_user(actor_kind="service", company_id=a, user_id=kim, name="x", is_active=None, now=T0),
        Forbidden,
    )
    assert audit_after(mark) == []
