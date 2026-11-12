"""reset_password: 새 비밀번호·is_initial 참·셈 0·잠금 풀림·그 사용자의 refresh 전부 끊음. 업무 층(주인 역할 연결)."""

import io
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Max
from django.test import override_settings

from esgapi.core.conf import now
from esgapi.core.models import AuditEventRow
from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.management.commands import reset_password as command
from esgapi.user.models import RefreshToken, User
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated

pytestmark = pytest.mark.django_db
OLD = "Blue-Harbor-7310"
NEW = "Green-Valley-5528"


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def run(*args: str, secret: str = NEW) -> str:
    out = io.StringIO()
    call_command("reset_password", *args, "--password-stdin", stdin=io.StringIO(secret + "\n"), stdout=out)
    return out.getvalue().strip()


def company_id(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive)
    return found.company.id


def issued(user_id: int) -> None:
    moment = now()
    RefreshToken.issue(
        jti=uuid4(), family=uuid4(), user_id=user_id, issued_at=moment, expires_at=moment + timedelta(days=7)
    )


def made(result: Any) -> int:
    assert isinstance(result, UserCreated)
    return result.user_id


def test_a_locked_customer_is_reset_and_every_refresh_is_revoked(tenants: None) -> None:
    cid = company_id("tenant-a")
    target = made(create_customer_user(actor_kind="admin", company_id=cid, username="kim", name="김담당", password=OLD))
    other = made(create_customer_user(actor_kind="admin", company_id=cid, username="lee", name="이담당", password=OLD))
    for user_id in (target, target, other):
        issued(user_id)
    User.for_company(cid).filter(pk=target).update(
        is_initial=False, login_failed_count=5, login_expiry_at=now() + timedelta(minutes=10)
    )
    printed = run("--company", "tenant-a", "--username", "kim")
    assert printed.split() == [str(target), "service", "tenant-a"]
    assert NEW not in printed
    row = User.for_company(cid).get(pk=target)
    assert (row.is_initial, row.login_failed_count, row.login_expiry_at) == (True, 0, None)
    assert check_password(NEW, row.password)
    assert not RefreshToken.of_user(target).filter(revoked_at__isnull=True).exists()
    assert RefreshToken.of_user(other).filter(revoked_at__isnull=True).count() == 1  # 분모: 남의 행은 그대로


def test_an_operator_is_reset_by_the_admin_route(tenants: None) -> None:
    target = made(create_operator(username="ops", name="운영", password=OLD))
    issued(target)
    assert run("--admin", "--username", "ops").split() == [str(target), "admin", "-"]
    row = User.admin_by_id(target).get()
    assert row.is_initial and check_password(NEW, row.password)
    assert not RefreshToken.of_user(target).filter(revoked_at__isnull=True).exists()


def test_an_unknown_user_or_another_companys_user_is_refused(tenants: None) -> None:
    made(
        create_customer_user(
            actor_kind="admin", company_id=company_id("tenant-a"), username="kim", name="김담당", password=OLD
        )
    )
    with pytest.raises(CommandError, match="없다") as caught:
        run("--company", "tenant-b", "--username", "kim")
    assert caught.value.returncode == 1
    with pytest.raises(CommandError, match="없다"):
        run("--admin", "--username", "kim")  # 고객사 사용자는 운영 관리자 길로 보이지 않는다
    row = User.for_company(company_id("tenant-a")).get(username="kim")
    assert check_password(OLD, row.password)


def test_a_rejected_password_changes_nothing(tenants: None) -> None:
    # 8자 이상 하나(MARC-ENT-282) — 7자는 거절(전엔 흔한 8자 "password" 가 거절이었다).
    target = made(create_operator(username="ops", name="운영", password=OLD))
    with pytest.raises(CommandError, match="쓸 수 없다"):
        run("--admin", "--username", "ops", secret="passwor")
    assert check_password(OLD, User.admin_by_id(target).get().password)


def test_a_common_eight_character_password_is_now_accepted(tenants: None) -> None:
    # 결정 MARC-ENT-282 가 바꾼 동작: 흔한 8자 "password"(전엔 거절)를 이제 받는다.
    target = made(create_operator(username="ops", name="운영", password=OLD))
    assert run("--admin", "--username", "ops", secret="password").split() == [str(target), "admin", "-"]
    assert check_password("password", User.admin_by_id(target).get().password)


def test_the_command_calls_the_named_action(tenants: None, monkeypatch: pytest.MonkeyPatch) -> None:
    made(create_operator(username="ops", name="운영", password=OLD))
    calls: list[int] = []
    real = command.reset_password

    def wrapped(**kwargs: Any) -> Any:
        calls.append(kwargs["user_id"])
        return real(**kwargs)

    monkeypatch.setattr(command, "reset_password", wrapped)
    run("--admin", "--username", "ops")
    assert len(calls) == 1


def test_a_reset_by_command_writes_one_command_line(tenants: None) -> None:
    """AU1a(B4): 명령의 초기화는 감사 행위자 command·사람 NULL 줄 하나."""
    cid = company_id("tenant-a")
    target = made(create_customer_user(actor_kind="admin", company_id=cid, username="kim", name="김담당", password=OLD))
    mark = AuditEventRow.unscoped.aggregate(top=Max("pk"))["top"] or 0
    run("--company", "tenant-a", "--username", "kim")
    lines = AuditEventRow.unscoped.filter(pk__gt=mark).order_by("pk")
    assert [(r.event, r.actor_kind, r.actor_user_id, r.company_id, r.target_id) for r in lines] == [
        ("password_reset", "command", None, cid, target)
    ]
