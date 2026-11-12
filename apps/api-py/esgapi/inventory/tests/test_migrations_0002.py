# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 inventory 0002_index_selections(밴드 K1b-2b ①): 되돌리면(→ 0001) 표 둘과 같은 회사 키·권한이 걷히고
풀 표 넷은 남으며, 다시 올리면 같은 제약으로 선다. 끝에 모든 앱을 맨 끝으로 올린다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 행 0(데이터 이전 0).
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from esgapi.core.isolation.grants import APP_ROLE

pytestmark = pytest.mark.django_db(transaction=True)

POOL = ("inventory", "0001_ghg_pool")
TABLES = ("inventory_index_selections", "inventory_years")
CONSTRAINTS_SQL = (
    "SELECT conname FROM pg_constraint WHERE conrelid::regclass::text = ANY(%s::text[]) AND contype IN ('u', 'c', 'f') "
    "AND conname LIKE 'inventory%%' ORDER BY conname"
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


def test_0002_goes_down_to_the_pool_and_comes_back_the_same() -> None:
    before = sql(CONSTRAINTS_SQL, [list(TABLES)])
    # 분모: 같은 회사 키 셋 · UNIQUE 하나 · CHECK 셋 · Django 외래 키 다섯(회사 둘·해·잎·판)
    assert len(before) == 13, before  # · S12a 0003 +1: CHECK inventory_selections_lock_pair(선택 행 잠금 짝)
    assert set(TABLES) <= tables()

    migrate(POOL)
    assert not set(TABLES) & tables()  # 정말 내려갔다
    assert {"ghg_index_nodes", "ghg_factors", "ghg_factor_versions", "ghg_factor_gases"} <= tables()  # 풀은 남는다

    migrate()
    assert sql(CONSTRAINTS_SQL, [list(TABLES)]) == before
    privileges = sql(
        "SELECT has_table_privilege(%s, t, 'INSERT'), has_table_privilege(%s, t, 'DELETE') "
        "FROM unnest(%s::text[]) AS t",
        [APP_ROLE, APP_ROLE, list(TABLES)],
    )
    assert privileges == [(True, False), (True, False)]
