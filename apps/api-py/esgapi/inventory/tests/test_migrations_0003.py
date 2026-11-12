# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 inventory 0003_entries(밴드 S12a ①): 되돌리면(→ 0002) 입력 표 셋·선택 칸 셋·같은 회사 키·권한이
걷히고 해·선택 표는 남으며, 다시 올리면 같은 제약으로 선다. 끝에 모든 앱을 맨 끝으로 올린다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 행 0(데이터 이전 0).
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from esgapi.core.isolation.grants import APP_ROLE

pytestmark = pytest.mark.django_db(transaction=True)

SELECTIONS = ("inventory", "0002_index_selections")
TABLES = ("inventory_entry_history", "inventory_entry_rows", "inventory_entry_values")
CONSTRAINTS_SQL = (
    "SELECT conname FROM pg_constraint WHERE conrelid::regclass::text = ANY(%s::text[]) AND contype IN ('u', 'c', 'f') "
    "ORDER BY conname"
)
PARTIAL_UNIQUE_SQL = "SELECT count(*) FROM pg_indexes WHERE indexname = 'inventory_entry_rows_unique_alive'"
SELECTION_COLUMNS = (
    "SELECT column_name FROM information_schema.columns WHERE table_name = 'inventory_index_selections' "
    "AND column_name IN ('memo', 'locked_at', 'locked_by_user_id') ORDER BY column_name"
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


def test_0003_goes_down_to_the_selections_and_comes_back_the_same() -> None:
    before = sql(CONSTRAINTS_SQL, [list(TABLES)])
    names = {name for (name,) in before}
    # 분모: 같은 회사 키 셋 · 같은 회사 외래 키 넷 · UNIQUE 하나 · CHECK 셋
    # · Django 외래 키 일곱(회사 셋·선택·자산/시설·행 둘).
    # 부분 UNIQUE(inventory_entry_rows_unique_alive — 삭제 안 된 것끼리)는 제약이 아니라 색인이다(따로 본다)
    assert {
        "inventory_entry_rows_company_id_uniq",
        "inventory_entry_values_company_id_uniq",
        "inventory_entry_history_company_id_uniq",
        "inventory_entry_rows_selection_id_same_company_fk",
        "inventory_entry_rows_site_facility_id_same_company_fk",
        "inventory_entry_values_row_id_same_company_fk",
        "inventory_entry_history_row_id_same_company_fk",
        "inventory_entry_values_unique",
        "inventory_entry_values_amount_nonneg",
        "inventory_entry_values_slot_format",
        "inventory_entry_history_kind_check",
    } <= names
    # S12a-2 +11: 0004 가 행·히스토리에 더한 것(CHECK 둘 · 같은 회사 짝 셋 · Django 외래 키 여섯 — test_migrations_0004)
    assert len(before) == 11 + 7 + 11, before
    assert sql(PARTIAL_UNIQUE_SQL) == [(1,)]
    assert len(sql(SELECTION_COLUMNS)) == 3

    migrate(SELECTIONS)
    assert not set(TABLES) & tables()  # 정말 내려갔다
    assert {"inventory_years", "inventory_index_selections"} <= tables()  # 해·선택은 남는다
    assert sql(SELECTION_COLUMNS) == []  # 칸 셋도 걷혔다
    assert not sql("SELECT 1 FROM pg_constraint WHERE conname = 'inventory_selections_lock_pair'")

    migrate()
    assert sql(CONSTRAINTS_SQL, [list(TABLES)]) == before
    assert sql(PARTIAL_UNIQUE_SQL) == [(1,)]
    privileges = sql(
        "SELECT has_table_privilege(%s, t, 'UPDATE'), has_table_privilege(%s, t, 'DELETE') "
        "FROM unnest(%s::text[]) AS t ORDER BY t",
        [APP_ROLE, APP_ROLE, sorted(TABLES)],
    )
    assert privileges == [(False, False), (True, False), (True, False)]  # history · rows · values
