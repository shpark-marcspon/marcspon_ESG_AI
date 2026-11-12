# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 inventory 0005_scope3_categories(밴드 S3K2a ①): 되돌리면(→ 0004) 카테고리 잠금 표와 제약·같은 회사 키·
권한이 걷히고, 다시 올리면 같은 제약으로 선다. 앱 역할은 SELECT·INSERT·UPDATE(DELETE 0). CHECK 셋(해 범위·카테고리
열넷·잠금 셋 짝)이 실제로 막는다. 끝에 모든 앱을 맨 끝으로 올린다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 데이터 이전 0.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from esgapi.core.isolation.grants import APP_ROLE
from esgapi.inventory.models import Scope3CategoryState

pytestmark = pytest.mark.django_db(transaction=True)

PERIODS = ("inventory", "0004_entry_periods_factors")
TABLE = "inventory_scope3_categories"
CONSTRAINTS_SQL = (
    "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
    "WHERE conrelid::regclass::text = %s AND contype IN ('u', 'c', 'f') ORDER BY 1"
)


def migrate(*targets: tuple[str, str]) -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())


def sql(statement: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params or [])
        return cursor.fetchall() if cursor.description else []


def tables() -> set[str]:
    return {name for (name,) in sql("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}


@pytest.fixture(autouse=True)
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()


def test_0005_goes_down_to_0004_and_comes_back_the_same() -> None:
    before = sql(CONSTRAINTS_SQL, [TABLE])
    definitions = dict(before)
    assert definitions["inventory_scope3_categories_company_id_uniq"] == "UNIQUE (company_id, id)"
    assert definitions["inventory_scope3_categories_unique"] == "UNIQUE (company_id, year, category)"
    assert {
        "inventory_scope3_categories_year_range",
        "inventory_scope3_categories_category_check",
        "inventory_scope3_categories_lock_triple",
    } <= set(definitions)
    foreign = [name for name, definition in before if definition.startswith("FOREIGN KEY")]
    assert len(foreign) == 1 and definitions[foreign[0]].startswith("FOREIGN KEY (company_id) REFERENCES company(id)")
    assert "same_company" not in " ".join(definitions)  # 같은 회사 복합 FK 0(runs·inventory_years FK 0)

    migrate(PERIODS)
    assert TABLE not in tables()
    assert "inventory_entry_periods" in tables()  # 0004 는 남는다

    migrate()
    assert sql(CONSTRAINTS_SQL, [TABLE]) == before
    privileges = sql(
        "SELECT has_table_privilege(%s, %s, 'SELECT'), has_table_privilege(%s, %s, 'INSERT'), "
        "has_table_privilege(%s, %s, 'UPDATE'), has_table_privilege(%s, %s, 'DELETE')",
        [APP_ROLE, TABLE] * 4,
    )
    assert privileges == [(True, True, True, False)]  # 지우지 않는 표


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"year": 1989}, "inventory_scope3_categories_year_range"),
        ({"category": "C10"}, "inventory_scope3_categories_category_check"),
        ({"locked_at": datetime(2026, 1, 1, tzinfo=UTC)}, "inventory_scope3_categories_lock_triple"),
        ({"locked_by_user_id": 1, "pinned_run_id": 1}, "inventory_scope3_categories_lock_triple"),
    ],
    ids=["year", "c10", "only-time", "no-time"],
)
def test_the_checks_refuse(companies: tuple[int, int], fields: dict[str, Any], constraint: str) -> None:
    values: dict[str, Any] = {"year": 2025, "category": "C4"} | fields
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        Scope3CategoryState.for_company(companies[0]).create(**values)
    assert constraint in str(caught.value)


def test_one_row_per_company_year_category(companies: tuple[int, int]) -> None:
    a, b = companies
    Scope3CategoryState.for_company(a).create(year=2025, category="C4")
    Scope3CategoryState.for_company(b).create(year=2025, category="C4")  # 다른 회사는 따로
    Scope3CategoryState.for_company(a).create(year=2024, category="C4")
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        Scope3CategoryState.for_company(a).create(year=2025, category="C4")
    assert "inventory_scope3_categories_unique" in str(caught.value)
    full = {"locked_at": datetime(2026, 1, 1, tzinfo=UTC), "locked_by_user_id": 7, "pinned_run_id": 8}
    Scope3CategoryState.for_company(a).create(year=2025, category="C5", **full)  # 셋 다 있으면 지난다
