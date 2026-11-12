"""create_user: 운영 관리자(--admin)·고객사 사용자(--company) 하나를 만든다. 업무 층(주인 역할 연결).

비밀번호는 --password-stdin 으로 넘긴다(명령줄 인자로 받지 않는다). 출력에 비밀번호 글자가 없는지 본다.
"""

import io
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Max
from django.test import override_settings

from esgapi.core.models import AuditEventRow
from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.management.commands import create_user as command
from esgapi.user.models import User

pytestmark = pytest.mark.django_db
SECRET = "Blue-Harbor-7310"


@pytest.fixture
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def run(*args: str, secret: str = SECRET) -> tuple[str, str]:
    out, err = io.StringIO(), io.StringIO()
    call_command("create_user", *args, "--password-stdin", stdin=io.StringIO(secret + "\n"), stdout=out, stderr=err)
    return out.getvalue().strip(), err.getvalue()


def company_id(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive)
    return found.company.id


def test_an_operator_is_made_with_level_99_and_must_change_the_password(tenants: None) -> None:
    printed, err = run("--admin", "--username", "ops", "--name", "운영")
    user_id, kind, where = printed.split()
    assert (kind, where, err) == ("admin", "-", "")
    row = User.admin_by_id(int(user_id)).get()
    assert (row.kind, row.company_id, row.level, row.is_initial) == ("admin", None, 99, True)
    assert row.password.startswith("pbkdf2_sha256$")  # 설정의 기본 해시(PBKDF2) 그대로
    assert SECRET not in printed


def test_a_customer_user_is_made_in_that_company_with_level_79(tenants: None, fast_hasher: None) -> None:
    printed, _err = run("--company", "tenant-a", "--username", "kim", "--name", "김담당")
    user_id, kind, where = printed.split()
    assert (kind, where) == ("service", "tenant-a")
    row = User.for_company(company_id("tenant-a")).get(pk=int(user_id))
    assert (row.kind, row.level, row.is_initial, row.username) == ("service", 79, True, "kim")


def test_an_existing_username_is_not_overwritten(tenants: None, fast_hasher: None) -> None:
    run("--admin", "--username", "ops", "--name", "운영")
    before = list(User.admin_by_username("ops").values_list("pk", "name", "password"))
    with pytest.raises(CommandError, match="이미 있다") as caught:
        run("--admin", "--username", "ops", "--name", "다른 이름", secret="Other-Harbor-8421")
    assert caught.value.returncode == 1
    assert list(User.admin_by_username("ops").values_list("pk", "name", "password")) == before


def test_an_unknown_company_is_refused(tenants: None, fast_hasher: None) -> None:
    with pytest.raises(CommandError, match="회사가 없다"):
        run("--company", "nobody", "--username", "kim", "--name", "김")
    assert User.for_company(company_id("tenant-a")).count() == 0


def test_a_rejected_password_makes_nothing(tenants: None, fast_hasher: None) -> None:
    # 8자 이상 하나(MARC-ENT-282) — 7자는 거절(전엔 8자 숫자만 "12345678" 이 거절이었다).
    with pytest.raises(CommandError, match="쓸 수 없다") as caught:
        run("--admin", "--username", "ops", "--name", "운영", secret="1234567")
    assert "1234567" not in str(caught.value)
    assert not User.admin_by_username("ops").exists()


def test_an_eight_character_numeric_password_is_now_accepted(tenants: None, fast_hasher: None) -> None:
    # 결정 MARC-ENT-282 가 바꾼 동작: 숫자만 8자(전엔 거절)를 이제 받는다.
    printed, _err = run("--admin", "--username", "ops", "--name", "운영", secret="12345678")
    assert "12345678" not in printed
    assert User.admin_by_username("ops").count() == 1


@pytest.mark.parametrize(
    "argv",
    [
        ["--admin", "--company", "tenant-a", "--username", "x", "--name", "x"],  # 둘 다
        ["--username", "x", "--name", "x"],  # 둘 다 없음
    ],
    ids=["both", "neither"],
)
def test_admin_and_company_are_exclusive_and_argparse_exits_2(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        command.Command().run_from_argv(["manage.py", "create_user", *argv])
    assert caught.value.code == 2


def test_there_is_no_password_argument() -> None:
    with pytest.raises(SystemExit) as caught:
        command.Command().run_from_argv(
            ["manage.py", "create_user", "--admin", "--username", "x", "--name", "x", "--password", SECRET]
        )
    assert caught.value.code == 2


def counting(target: Callable[..., Any], calls: list[str], name: str) -> Callable[..., Any]:
    def wrapped(**kwargs: Any) -> Any:
        calls.append(name)
        return target(**kwargs)

    return wrapped


def test_the_command_calls_the_named_services(
    tenants: None, fast_hasher: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(command, "create_operator", counting(command.create_operator, calls, "create_operator"))
    monkeypatch.setattr(
        command, "create_customer_user", counting(command.create_customer_user, calls, "create_customer_user")
    )
    run("--admin", "--username", "ops", "--name", "운영")
    run("--company", "tenant-b", "--username", "lee", "--name", "이담당")
    assert calls == ["create_operator", "create_customer_user"]


def test_making_by_command_writes_one_command_line_each(tenants: None, fast_hasher: None) -> None:
    """AU1a(B4): 명령으로 만든 것은 감사 행위자 command·사람 NULL 줄 하나씩(명령 파일은 권한 인자 admin 그대로)."""
    mark = AuditEventRow.unscoped.aggregate(top=Max("pk"))["top"] or 0
    ops = int(run("--admin", "--username", "ops", "--name", "운영")[0].split()[0])
    kim = int(run("--company", "tenant-a", "--username", "kim", "--name", "김담당")[0].split()[0])
    lines = AuditEventRow.unscoped.filter(pk__gt=mark).order_by("pk")
    assert [(r.event, r.actor_kind, r.actor_user_id, r.company_id, r.target_id) for r in lines] == [
        ("user_created", "command", None, None, ops),
        ("user_created", "command", None, company_id("tenant-a"), kim),
    ]
