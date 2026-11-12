# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 inventory 0004_entry_periods_factors(밴드 S12a-2 ①): 되돌리면(→ 0003) 주기·직접입력 표 둘과 행·
히스토리 칸·제약·같은 회사 키·권한이 걷히고 slot·kind CHECK 가 0003 글자로 돌아가며, 다시 올리면 같은 제약으로 선다.
끝에 모든 앱을 맨 끝으로 올린다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 행 0(데이터 이전 0).
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from esgapi.core.isolation.grants import APP_ROLE

pytestmark = pytest.mark.django_db(transaction=True)

ENTRIES = ("inventory", "0003_entries")
NEW_TABLES = ("inventory_custom_factors", "inventory_entry_periods")
TOUCHED = ("inventory_entry_history", "inventory_entry_rows", "inventory_entry_values")
CONSTRAINTS_SQL = (
    "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) FROM pg_constraint "
    "WHERE conrelid::regclass::text = ANY(%s::text[]) AND contype IN ('u', 'c', 'f') ORDER BY 1, 2"
)
NEW_COLUMNS = (
    "SELECT table_name, column_name FROM information_schema.columns WHERE table_name = ANY(%s::text[]) "
    "AND column_name IN ('factor_version_id', 'custom_factor_id', 'reason', 'before_version_id', 'after_version_id', "
    "'before_custom_id', 'after_custom_id') ORDER BY 1, 2"
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


def definition(name: str) -> str:
    ((found,),) = sql("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = %s", [name])
    return str(found)


@pytest.fixture(autouse=True)
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()


def test_0004_goes_down_to_the_entries_and_comes_back_the_same() -> None:
    every = [*NEW_TABLES, *TOUCHED]
    before = sql(CONSTRAINTS_SQL, [every])
    names = {name for _, name, _ in before}
    # 분모: 같은 회사 키 둘 · 같은 회사 외래 키 다섯 · UNIQUE 하나 · CHECK 여덟(직접입력 넷 · 주기 · 행 · 히스토리 둘의
    # 새것과 넓힌 kind) · Django 외래 키(주기 셋 · 직접입력 회사 · 행 둘 · 히스토리 넷)
    assert {
        "inventory_entry_periods_company_id_uniq",
        "inventory_custom_factors_company_id_uniq",
        "inventory_entry_periods_selection_id_same_company_fk",
        "inventory_entry_periods_site_id_same_company_fk",
        "inventory_entry_rows_custom_factor_id_same_company_fk",
        "inventory_entry_history_before_custom_id_same_company_fk",
        "inventory_entry_history_after_custom_id_same_company_fk",
        "inventory_entry_periods_unique",
        "inventory_entry_periods_period_check",
        "inventory_custom_factors_tier_check",
        "inventory_custom_factors_base_year_range",
        "inventory_custom_factors_ncv_consistent",
        "inventory_custom_factors_ncv_positive",
        "inventory_entry_rows_one_factor",
        "inventory_entry_history_factor_refs",
    } <= names
    assert "Q[1-4]" in definition("inventory_entry_values_slot_format")
    assert "'factor'" in definition("inventory_entry_history_kind_check")
    assert len(sql(NEW_COLUMNS, [list(TOUCHED)])) == 7

    migrate(ENTRIES)
    assert not set(NEW_TABLES) & tables()  # 정말 내려갔다
    assert set(TOUCHED) <= tables()  # 0003 의 표 셋은 남는다
    assert sql(NEW_COLUMNS, [list(TOUCHED)]) == []  # 행·히스토리 칸도 걷혔다
    assert "Q[1-4]" not in definition("inventory_entry_values_slot_format")  # 0003 글자로
    assert "'factor'" not in definition("inventory_entry_history_kind_check")
    assert not sql("SELECT 1 FROM pg_constraint WHERE conname = 'inventory_entry_rows_one_factor'")

    migrate()
    assert sql(CONSTRAINTS_SQL, [every]) == before
    privileges = sql(
        "SELECT t, has_table_privilege(%s, t, 'INSERT'), has_table_privilege(%s, t, 'UPDATE'), "
        "has_table_privilege(%s, t, 'DELETE') FROM unnest(%s::text[]) AS t ORDER BY t",
        [APP_ROLE, APP_ROLE, APP_ROLE, list(NEW_TABLES)],
    )
    assert privileges == [
        ("inventory_custom_factors", True, False, False),  # 고치지 않는 표
        ("inventory_entry_periods", True, True, False),
    ]
