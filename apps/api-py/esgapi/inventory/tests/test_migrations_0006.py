# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 inventory 0006_scope3_row_edits(밴드 S3K2b-1 ①): 되돌리면(→ 0005) 사건 표와 제약·같은 회사 키·권한이
걷히고, 다시 올리면 같은 제약으로 선다. 앱 역할은 SELECT·INSERT 만(UPDATE·DELETE 0). CHECK 넷(카테고리 열넷·kind 둘·
row_id 길이·걷은 사유 길이)이 실제로 막는다. batch_id 는 NULL 을 받는다. 끝에 모든 앱을 맨 끝으로 올린다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 데이터 이전 0.
"""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from django.db import DataError, IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from esgapi.core.isolation.grants import APP_ROLE
from esgapi.inventory.models import Scope3RowEdit

pytestmark = pytest.mark.django_db(transaction=True)

CATEGORIES_STEP = ("inventory", "0005_scope3_categories")
TABLE = "inventory_scope3_row_edits"
CONSTRAINTS_SQL = (
    "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
    "WHERE conrelid::regclass::text = %s AND contype IN ('u', 'c', 'f') ORDER BY 1"
)
INDEXES_SQL = "SELECT indexname FROM pg_indexes WHERE tablename = %s ORDER BY 1"


def migrate(*targets: tuple[str, str]) -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())


def sql(statement: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params or [])
        return cursor.fetchall() if cursor.description else []


def tables() -> set[str]:
    return {name for (name,) in sql("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}


def values(**over: Any) -> dict[str, Any]:
    return {
        "run_id": 9001,
        "category": "C5",
        "row_id": "가상_C5!20",
        "kind": "exclude",
        "reason": "가상 사유",
        "actor_kind": "service",
        "actor_user_id": 7,
    } | over


@pytest.fixture(autouse=True)
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()


def test_0006_goes_down_to_0005_and_comes_back_the_same() -> None:
    before = sql(CONSTRAINTS_SQL, [TABLE])
    indexes = sql(INDEXES_SQL, [TABLE])
    definitions = dict(before)
    assert definitions["inventory_scope3_row_edits_company_id_uniq"] == "UNIQUE (company_id, id)"
    assert {
        "inventory_scope3_row_edits_category_check",
        "inventory_scope3_row_edits_kind_check",
        "inventory_scope3_row_edits_row_id_check",
        "inventory_scope3_row_edits_reason_check",
    } <= set(definitions)
    foreign = [name for name, definition in before if definition.startswith("FOREIGN KEY")]
    assert len(foreign) == 1 and definitions[foreign[0]].startswith("FOREIGN KEY (company_id) REFERENCES company(id)")
    assert {("inv_s3_edits_run_row_idx",), ("inv_s3_edits_run_cat_idx",), ("inv_s3_edits_run_batch_idx",)} <= set(
        indexes
    )

    migrate(CATEGORIES_STEP)
    assert TABLE not in tables()
    assert "inventory_scope3_categories" in tables()  # 0005 는 남는다

    migrate()
    assert sql(CONSTRAINTS_SQL, [TABLE]) == before
    assert sql(INDEXES_SQL, [TABLE]) == indexes
    privileges = sql(
        "SELECT has_table_privilege(%s, %s, 'SELECT'), has_table_privilege(%s, %s, 'INSERT'), "
        "has_table_privilege(%s, %s, 'UPDATE'), has_table_privilege(%s, %s, 'DELETE')",
        [APP_ROLE, TABLE] * 4,
    )
    assert privileges == [(True, True, False, False)]  # 불변 사건 표


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"category": "C10"}, "inventory_scope3_row_edits_category_check"),
        ({"kind": "delete"}, "inventory_scope3_row_edits_kind_check"),
        ({"row_id": ""}, "inventory_scope3_row_edits_row_id_check"),
        ({"reason": ""}, "inventory_scope3_row_edits_reason_check"),
        ({"reason": "   "}, "inventory_scope3_row_edits_reason_check"),
    ],
    ids=["c10", "kind", "empty-row", "empty-reason", "blank-reason"],
)
def test_the_checks_refuse(companies: tuple[int, int], fields: dict[str, Any], constraint: str) -> None:
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        Scope3RowEdit.for_company(companies[0]).create(**values(**fields))
    assert constraint in str(caught.value)
    assert getattr(caught.value.__cause__, "sqlstate", None) == "23514"


def test_the_columns_stop_at_their_length(companies: tuple[int, int]) -> None:
    a = companies[0]
    Scope3RowEdit.for_company(a).create(**values(reason="가" * 300, row_id="가" * 64))
    for over in ({"reason": "가" * 301}, {"row_id": "가" * 65}):
        with pytest.raises(DataError), transaction.atomic():
            Scope3RowEdit.for_company(a).create(**values(**over))


def test_batch_id_takes_null_and_a_uuid(companies: tuple[int, int]) -> None:
    a = companies[0]
    batch = uuid4()
    Scope3RowEdit.for_company(a).create(**values())
    Scope3RowEdit.for_company(a).create(**values(batch_id=batch))
    assert list(Scope3RowEdit.for_company(a).order_by("id").values_list("batch_id", flat=True)) == [None, batch]
