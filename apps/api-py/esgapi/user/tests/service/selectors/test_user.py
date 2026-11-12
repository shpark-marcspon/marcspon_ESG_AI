"""로그인의 읽기(find_customer·find_admin·account)와 목록의 거르기(list_customer_users — UA1). 업무 층, 주인 역할 연결.

자료는 User.unscoped 로 심는다(비밀번호는 쓸 수 없는 값 — 읽기만 잰다). 회사는 tenants 고정물이 심는다.
"""

from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth.hashers import make_password

from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyActive
from esgapi.user.models import User
from esgapi.user.service.permissions.user import Forbidden
from esgapi.user.service.selectors.user import (
    CustomerUserPage,
    UserStatus,
    account,
    find_admin,
    find_customer,
    list_customer_users,
)

pytestmark = pytest.mark.django_db


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    assert isinstance(found, CompanyActive), found
    return found.company.id


def insert(*, kind: str, username: str, company_id: int | None) -> int:
    level = 99 if kind == "admin" else 79
    row = User.unscoped.create(
        kind=kind, username=username, company_id=company_id, name="이름", level=level, password="!"
    )
    return row.pk


@pytest.fixture
def kims(tenants: None) -> tuple[int, int, int, int, int]:
    """kim 셋(가 회사·나 회사·운영)과 회사 둘의 id. (a, b, 가 kim, 나 kim, 운영 kim)."""
    a, b = company_id_of("tenant-a"), company_id_of("tenant-b")
    return (
        a,
        b,
        insert(kind="service", username="kim", company_id=a),
        insert(kind="service", username="kim", company_id=b),
        insert(kind="admin", username="kim", company_id=None),
    )


def test_find_customer_sees_only_its_company(kims: tuple[int, int, int, int, int]) -> None:
    a, b, kim_a, kim_b, _ = kims
    found_a, found_b = find_customer(a, "kim"), find_customer(b, "kim")
    assert found_a is not None and found_b is not None
    assert (found_a.pk, found_b.pk) == (kim_a, kim_b)
    assert find_customer(a, "nobody") is None


def test_find_customer_never_returns_an_operator(tenants: None) -> None:
    a = company_id_of("tenant-a")
    insert(kind="admin", username="ops", company_id=None)
    assert find_customer(a, "ops") is None


def test_find_admin_never_returns_a_customer(kims: tuple[int, int, int, int, int]) -> None:
    *_, ops = kims
    found = find_admin("kim")
    assert found is not None
    assert (found.pk, found.kind, found.company_id) == (ops, "admin", None)
    a = kims[0]
    insert(kind="service", username="lee", company_id=a)
    assert find_admin("lee") is None


def test_account_keeps_the_company_condition(kims: tuple[int, int, int, int, int]) -> None:
    a, b, kim_a, kim_b, ops = kims
    found = account(a, kim_a)
    assert found is not None and found.pk == kim_a
    assert account(b, kim_a) is None  # 남의 회사
    assert account(None, kim_a) is None  # 고객사 사용자를 운영 길로
    assert account(a, ops) is None  # 운영 관리자를 회사 길로
    operator = account(None, ops)
    assert operator is not None and operator.pk == ops
    assert account(a, kim_b) is None


# ── 목록의 거르기(UA1 — 처분 ③⑨) ───────────────────────────────────

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def page(company_id: int, *, q: str | None = None, status: UserStatus | None = None) -> CustomerUserPage:
    found = list_customer_users(
        actor_kind="admin", company_id=company_id, limit=100, offset=0, now=NOW, q=q, status=status
    )
    assert isinstance(found, CustomerUserPage), found
    return found


def test_the_list_leaves_out_rows_whose_password_cannot_be_used(kims: tuple[int, int, int, int, int]) -> None:
    a, _, a_kim, _, _ = kims  # kims 의 행은 비밀번호가 "!"(쓸 수 없는 값)
    lee = User.unscoped.create(
        kind="service", username="lee", company_id=a, name="이름", level=79, password=make_password("Blue-Harbor-7310")
    )
    unusable = User.unscoped.create(
        kind="service", username="edk", company_id=a, name="이름", level=79, password=make_password(None)
    )
    assert not User.unscoped.get(pk=unusable.pk).has_usable_password()  # 분모: Django 의 쓸 수 없는 값
    found = page(a)
    assert ([r.pk for r in found.rows], found.count) == ([lee.pk], 1)
    assert a_kim not in [r.pk for r in found.rows]


def test_status_and_q_filter_and_count_after_filtering(tenants: None) -> None:
    a = company_id_of("tenant-a")
    usable = make_password("Blue-Harbor-7310")

    def make(username: str, **fields: object) -> int:
        row = User.unscoped.create(
            kind="service", username=username, company_id=a, name="담당", level=79, password=usable, **fields
        )
        return row.pk

    active = make("active", is_initial=False)
    initial = make("initial", is_initial=True)
    locked = make("locked", is_initial=False, login_expiry_at=NOW)  # 같은 초 = 잠김
    expired = make("expired", is_initial=False, login_expiry_at=NOW - timedelta(seconds=1))
    off = make("off", is_active=False, login_expiry_at=NOW)
    assert {s: [r.pk for r in page(a, status=s).rows] for s in ("active", "initial", "locked", "inactive")} == {
        "active": [active, expired],
        "initial": [initial],
        "locked": [locked],
        "inactive": [off],
    }
    assert page(a).count == 5
    assert (page(a, q="LOCK").count, page(a, q="담당").count, page(a, q="lock", status="inactive").count) == (1, 5, 0)


def test_a_customer_is_forbidden_before_the_list_is_read(tenants: None) -> None:
    found = list_customer_users(actor_kind="service", company_id=company_id_of("tenant-a"), limit=1, offset=0, now=NOW)
    assert found == Forbidden("user_list")
