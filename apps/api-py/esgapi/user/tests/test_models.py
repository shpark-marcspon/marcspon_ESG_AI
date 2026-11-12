"""사용자 표(users)의 제약 넷과 회사 범위(업무 층, 주인 역할 연결).

회사 id 를 상수로 박지 않는다: 식별 열은 되돌림에 안 돌아간다. 회사는 Company.register 로 만든다 — user 는 남의
models 를 import 하지 않으므로(.importlinter 「나」) 등록부에서 꺼낸다. 행 수는 User.unscoped 로 센다(분모).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction

from esgapi.user.models import RefreshToken, User

pytestmark = pytest.mark.django_db


def register(subdomain: str, licence: str) -> int:
    company: Any = apps.get_model("organization", "Company")
    row: Any = company.register(name=f"{subdomain} 회사", business_licence_number=licence, subdomain=subdomain)
    assert isinstance(row.pk, int)
    return row.pk


@pytest.fixture
def two() -> tuple[int, int]:
    """회사 둘의 id."""
    return register("tenant-a", "111-11-11111"), register("tenant-b", "222-22-22222")


def insert(*, kind: str, username: str, company_id: int | None, level: int = 79, name: str = "이름") -> User:
    return User.unscoped.create(
        kind=kind, username=username, company_id=company_id, name=name, level=level, password="!"
    )


def test_kind_and_company_go_together(two: tuple[int, int]) -> None:
    a, _ = two
    with pytest.raises(IntegrityError, match="users_kind_company_check"), transaction.atomic():
        insert(kind="admin", username="ops", company_id=a)  # 운영팀인데 회사가 있다
    with pytest.raises(IntegrityError, match="users_kind_company_check"), transaction.atomic():
        insert(kind="service", username="kim", company_id=None)  # 고객사 사용자인데 회사가 없다
    assert User.unscoped.count() == 0


@pytest.mark.parametrize("level", [0, 50, 80, 100])
def test_level_is_one_of_the_three(two: tuple[int, int], level: int) -> None:
    a, _ = two
    with pytest.raises(IntegrityError, match="users_level_values_check"), transaction.atomic():
        insert(kind="service", username="kim", company_id=a, level=level)
    assert User.unscoped.count() == 0


def test_the_three_levels_are_accepted(two: tuple[int, int]) -> None:
    a, _ = two
    for level in (99, 89, 79):
        insert(kind="service", username=f"kim-{level}", company_id=a, level=level)
    assert User.unscoped.count() == 3


def test_an_admin_username_is_unique_across_the_whole_table(two: tuple[int, int]) -> None:
    a, _ = two
    insert(kind="admin", username="ops", company_id=None, level=99)
    with pytest.raises(IntegrityError, match="users_admin_username_uniq"), transaction.atomic():
        insert(kind="admin", username="ops", company_id=None, level=99)
    # 고객사 사용자의 같은 username 은 운영팀의 것과 겹치지 않는다(조건부 UNIQUE 의 조건이 kind 다)
    insert(kind="service", username="ops", company_id=a)
    assert User.unscoped.count() == 2


def test_a_service_username_is_unique_within_its_company(two: tuple[int, int]) -> None:
    a, _ = two
    insert(kind="service", username="kim", company_id=a)
    with pytest.raises(IntegrityError, match="users_company_username_uniq"), transaction.atomic():
        insert(kind="service", username="kim", company_id=a)
    assert User.unscoped.count() == 1


def test_the_same_service_username_lives_in_two_companies(two: tuple[int, int]) -> None:
    a, b = two
    insert(kind="service", username="kim", company_id=a, name="가김")
    insert(kind="service", username="kim", company_id=b, name="나김")
    assert sorted(User.unscoped.values_list("company_id", "username", "name")) == sorted(
        [(a, "kim", "가김"), (b, "kim", "나김")]
    )


def test_for_company_opens_only_that_companys_rows(two: tuple[int, int]) -> None:
    a, b = two
    insert(kind="service", username="kim", company_id=a, name="가김")
    insert(kind="service", username="lee", company_id=a, name="가이")
    insert(kind="service", username="kim", company_id=b, name="나김")
    insert(kind="admin", username="ops", company_id=None, level=99)
    assert User.unscoped.count() == 4  # 분모
    assert sorted(User.for_company(a).values_list("company_id", "name")) == [(a, "가김"), (a, "가이")]
    assert list(User.for_company(b).values_list("company_id", "name")) == [(b, "나김")]
    neighbours = sorted(n for n in {a - 1, a + 1, b - 1, b + 1} - {a, b} if n > 0)  # 이웃 id(±1)
    assert neighbours
    for neighbour in neighbours:
        assert User.for_company(neighbour).count() == 0, neighbour


# ── 이름 붙은 입구(K2a) ───────────────────────────────────────────────


def test_the_operator_entrances_see_only_operators(two: tuple[int, int]) -> None:
    a, _ = two
    ops = insert(kind="admin", username="ops", company_id=None, level=99)
    kim = insert(kind="service", username="ops", company_id=a)  # 같은 username 의 고객사 사용자
    assert User.unscoped.count() == 2  # 분모
    assert list(User.admin_by_username("ops").values_list("pk", flat=True)) == [ops.pk]
    assert list(User.admin_by_id(ops.pk).values_list("pk", flat=True)) == [ops.pk]
    assert User.admin_by_id(kim.pk).count() == 0
    assert User.admin_by_username("nobody").count() == 0


def test_register_admin_makes_an_initial_level_99_operator(two: tuple[int, int]) -> None:
    row = User.register_admin(username="ops", name="운영자", password="!")
    assert (row.kind, row.company_id, row.level, row.is_initial) == ("admin", None, 99, True)
    with pytest.raises(IntegrityError, match="users_admin_username_uniq"), transaction.atomic():
        User.register_admin(username="ops", name="운영둘", password="!")


def test_the_refresh_entrances_filter_by_jti_family_and_user(two: tuple[int, int]) -> None:
    a, _ = two
    kim = insert(kind="service", username="kim", company_id=a)
    lee = insert(kind="service", username="lee", company_id=a)
    now = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
    family, other_family = uuid4(), uuid4()
    jtis = [uuid4() for _ in range(4)]
    for jti, fam, user in zip(jtis, [family, family, other_family, other_family], [kim, kim, kim, lee], strict=True):
        RefreshToken.issue(jti=jti, family=fam, user_id=user.pk, issued_at=now, expires_at=now + timedelta(days=7))
    assert list(RefreshToken.by_jti(jtis[0]).values_list("jti", flat=True)) == [jtis[0]]
    assert RefreshToken.by_jti(uuid4()).count() == 0
    assert sorted(RefreshToken.of_family(family).values_list("jti", flat=True)) == sorted(jtis[:2])
    assert sorted(RefreshToken.of_family(other_family).values_list("jti", flat=True)) == sorted(jtis[2:])
    assert sorted(RefreshToken.of_user(kim.pk).values_list("jti", flat=True)) == sorted(jtis[:3])
    assert list(RefreshToken.of_user(lee.pk).values_list("jti", flat=True)) == [jtis[3]]
