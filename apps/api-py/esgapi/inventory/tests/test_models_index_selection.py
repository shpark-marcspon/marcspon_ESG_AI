"""인벤토리 해·고객사 인덱스 선택(회사 범위 표 둘)의 DB 제약(밴드 K1b-2b ① — migrations/0002_index_selections).
업무 층, 주인 역할 연결.

거절마다 됨의 짝을 둔다(제약이 너무 넓어 모든 행을 막는 것도 잡는다). 회사·풀 자료는 conftest `companies` 와
services·actions 로 짓는다(organization models import 0). 이름·값은 지어낸 것이다(실제 계수 0).
앱 역할의 권한 집합은 tests/security/test_owner.py 가 앱 역할로 잰다 — 여기서는 DELETE 없음을 카탈로그로 한 번 더 본다.
"""

from typing import Any

import psycopg
import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from esgapi.core.isolation.grants import APP_ROLE
from esgapi.core.isolation.managers import UnscopedQueryError
from esgapi.inventory.models import CompanyIndexSelection, GhgFactorVersion, InventoryYear
from esgapi.inventory.service.utils.index_selection import DEFAULT_DECIMALS
from esgapi.inventory.tests.ghg_pool_support import activity, factor, leaf

pytestmark = pytest.mark.django_db


def refused(constraint: str, make: Any) -> None:
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        make()


def sqlstate_of(make: Any) -> str | None:
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        make()
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error)
    return cause.sqlstate


def year(company_id: int, value: int = 2025, **fields: Any) -> InventoryYear:
    return InventoryYear.for_company(company_id).create(year=value, **fields)


@pytest.fixture
def pool() -> tuple[int, int]:
    """(잎 id, 그 기본 계수의 지금 판 id) — 지어낸 잎 하나·계수 하나."""
    node_id = leaf(activity(), "가 보일러")
    made = factor(node_id)
    return node_id, GhgFactorVersion.objects.get(factor_id=made.id, version=made.version).pk


def select(company_id: int, year_id: int, pool: tuple[int, int], **fields: Any) -> CompanyIndexSelection:
    node_id, version_id = pool
    return CompanyIndexSelection.for_company(company_id).create(
        inventory_year_id=year_id, facility_node_id=node_id, factor_version_id=version_id, **fields
    )


# ── inventory_years ────────────────────────────────────────────────


def test_a_new_year_takes_the_default_decimals(companies: tuple[int, int]) -> None:
    a, _ = companies
    row = year(a)
    row.refresh_from_db()
    assert (row.year, row.decimals, row.company_id) == (2025, DEFAULT_DECIMALS, a)


def test_a_year_is_unique_per_company(companies: tuple[int, int]) -> None:
    a, b = companies
    year(a)
    refused("inventory_years_company_year_unique", lambda: year(a))
    year(b)  # 짝: 다른 회사는 같은 해를 따로
    year(a, 2024)  # 짝: 같은 회사의 다른 해
    assert InventoryYear.unscoped.filter(year=2025).count() == 2


@pytest.mark.parametrize("decimals", [-1, 4])
def test_decimals_out_of_range_are_refused(companies: tuple[int, int], decimals: int) -> None:
    a, _ = companies
    refused("inventory_years_decimals_range", lambda: year(a, decimals=decimals))


@pytest.mark.parametrize("decimals", [0, 3])
def test_decimals_at_the_ends_are_taken(companies: tuple[int, int], decimals: int) -> None:
    a, _ = companies
    assert year(a, decimals=decimals).decimals == decimals


@pytest.mark.parametrize("value", [1989, 2101])
def test_a_year_out_of_range_is_refused(companies: tuple[int, int], value: int) -> None:
    a, _ = companies
    refused("inventory_years_year_range", lambda: year(a, value))


@pytest.mark.parametrize("value", [1990, 2100])
def test_a_year_at_the_ends_is_taken(companies: tuple[int, int], value: int) -> None:
    a, _ = companies
    assert year(a, value).year == value


# ── inventory_index_selections ─────────────────────────────────────


def test_a_leaf_is_chosen_once_among_the_alive_of_a_year(companies: tuple[int, int], pool: tuple[int, int]) -> None:
    a, b = companies
    first = select(a, year(a).pk, pool)
    refused("inventory_selections_node_unique_alive", lambda: select(a, first.inventory_year_id, pool))
    select(b, year(b).pk, pool)  # 짝: 다른 회사는 같은 잎을 따로(풀은 공통)
    select(a, year(a, 2024).pk, pool)  # 짝: 같은 회사의 다른 해
    CompanyIndexSelection.for_company(a).filter(pk=first.pk).update(deleted_at=timezone.now())
    select(a, first.inventory_year_id, pool)  # 짝: 지운 선택 뒤에는 다시 고른다(새 행)
    assert CompanyIndexSelection.unscoped.filter(facility_node_id=pool[0]).count() == 4


def test_a_deleted_selection_cannot_be_hidden(companies: tuple[int, int], pool: tuple[int, int]) -> None:
    a, _ = companies
    row = select(a, year(a).pk, pool, hidden=True)  # 짝: 살아 있는 행은 숨긴다
    alive = CompanyIndexSelection.for_company(a).filter(pk=row.pk)
    refused("inventory_selections_hidden_alive", lambda: alive.update(deleted_at=timezone.now()))
    alive.update(hidden=False, deleted_at=timezone.now())  # 짝: 숨김을 풀고 지운다
    assert alive.get().deleted_at is not None


def test_a_selection_cannot_point_at_another_companys_year(companies: tuple[int, int], pool: tuple[int, int]) -> None:
    a, b = companies
    others = year(b)
    code = sqlstate_of(lambda: select(a, others.pk, pool))
    assert code == "23503"  # foreign_key_violation(inventory_index_selections_inventory_year_id_same_company_fk)
    assert select(a, year(a).pk, pool).company_id == a  # 짝: 제 회사의 해
    assert CompanyIndexSelection.unscoped.filter(inventory_year_id=others.pk).count() == 0


def test_a_chosen_version_cannot_be_removed(companies: tuple[int, int], pool: tuple[int, int]) -> None:
    """잡은 판을 가리키는 선택이 있으면 판 행은 DB 가 못 지운다(앱 역할은 판에 DELETE 도 없다 — 0001).
    Django 의 한 칸 외래 키는 DEFERRABLE 이라 커밋 전에 재도록 IMMEDIATE 로 돌린다."""
    a, _ = companies
    select(a, year(a).pk, pool)

    def remove() -> None:
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            # 판의 가스 줄은 걷고 판을 지운다 — 남는 막음은 선택의 외래 키뿐
            cursor.execute("DELETE FROM ghg_factor_gases WHERE factor_version_id = %s", [pool[1]])
            cursor.execute("DELETE FROM ghg_factor_versions WHERE id = %s", [pool[1]])

    with pytest.raises(IntegrityError, match='table "inventory_index_selections"'), transaction.atomic():
        remove()
    assert GhgFactorVersion.objects.filter(pk=pool[1]).exists()


# ── 매니저와 권한 ────────────────────────────────────────────────────


@pytest.mark.parametrize("model", [InventoryYear, CompanyIndexSelection])
def test_the_default_manager_refuses_without_a_company(model: type[InventoryYear | CompanyIndexSelection]) -> None:
    with pytest.raises(UnscopedQueryError):
        model.objects.all()


def test_for_company_opens_only_that_company(companies: tuple[int, int], pool: tuple[int, int]) -> None:
    a, b = companies
    select(a, year(a).pk, pool)
    select(b, year(b).pk, pool)
    assert InventoryYear.unscoped.count() == 2  # 분모: B 의 행도 있다
    assert [row.company_id for row in InventoryYear.for_company(a)] == [a]
    assert [row.company_id for row in CompanyIndexSelection.for_company(a)] == [a]


@pytest.mark.parametrize("table", ["inventory_years", "inventory_index_selections"])
def test_the_app_role_has_no_delete(table: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT has_table_privilege(%s, %s, 'SELECT'), has_table_privilege(%s, %s, 'DELETE')",
            [APP_ROLE, table, APP_ROLE, table],
        )
        assert cursor.fetchone() == (True, False)  # 짝: SELECT 는 있다(권한 표를 실제로 읽었다)
