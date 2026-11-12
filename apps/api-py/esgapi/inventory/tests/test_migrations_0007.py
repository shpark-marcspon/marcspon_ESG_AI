# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 inventory 0007_scope3_row_factors(밴드 S3K2b-2 ①): kind 에 factor 가 들고, 새 칸은 NULL 허용,
모양 CHECK 가 어긋난 행을 23514 로 막는다. 되돌리면(→ 0006) 칸·제약이 걷히고 다시 올리면 같다.
GRANT 는 그대로 SELECT·INSERT 다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 데이터 이전 0.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import DataError, IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from esgapi.core.isolation.grants import APP_ROLE
from esgapi.inventory.models import Scope3RowEdit

pytestmark = pytest.mark.django_db(transaction=True)

EDITS_STEP = ("inventory", "0006_scope3_row_edits")
TABLE = "inventory_scope3_row_edits"
SHAPE = "inventory_scope3_row_edits_factor_shape"
CHOICE = "inventory_scope3_row_edits_factor_choice_check"
RANK = "inventory_scope3_row_edits_factor_rank_check"
KIND = "inventory_scope3_row_edits_kind_check"
NEW_COLUMNS = {
    "factor_choice", "factor_rank", "factor_title", "factor_value", "factor_source", "factor_unit", "co2e",
    "biogenic_co2e", "ai_factor_title", "ai_factor_value", "ai_factor_source", "ai_co2e",
}  # fmt: skip
NO_FACTOR = {"factor_choice": None, "factor_title": None, "factor_value": None, "factor_source": None}
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


def columns() -> set[str]:
    return {
        name for (name,) in sql("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [TABLE])
    }


def values(**over: Any) -> dict[str, Any]:
    return {
        "run_id": 9001,
        "category": "C5",
        "row_id": "가상_C5!20",
        "kind": "factor",
        "reason": "가상 사유",
        "actor_kind": "service",
        "actor_user_id": 7,
        "factor_choice": "custom",
        "factor_title": "가상 계수",
        "factor_value": "2.0",
        "factor_source": "가상 출처",
    } | over


@pytest.fixture(autouse=True)
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()


def test_0007_goes_down_to_0006_and_comes_back_the_same() -> None:
    before = sql(CONSTRAINTS_SQL, [TABLE])
    assert {KIND, SHAPE, CHOICE, RANK} <= set(dict(before))
    assert columns() >= NEW_COLUMNS
    migrate(EDITS_STEP)
    assert columns().isdisjoint(NEW_COLUMNS)
    assert not {SHAPE, CHOICE, RANK} & set(dict(sql(CONSTRAINTS_SQL, [TABLE])))
    migrate()
    assert sql(CONSTRAINTS_SQL, [TABLE]) == before
    privileges = sql(
        "SELECT has_table_privilege(%s, %s, 'SELECT'), has_table_privilege(%s, %s, 'INSERT'), "
        "has_table_privilege(%s, %s, 'UPDATE'), has_table_privilege(%s, %s, 'DELETE')",
        [APP_ROLE, TABLE] * 4,
    )
    assert privileges == [(True, True, False, False)]  # 불변 사건 표 그대로


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"factor_choice": "applied", "factor_title": None, "factor_value": None, "factor_source": None},
        {"factor_choice": "recommended", "factor_rank": 4},
    ],
    ids=["custom", "applied-with-nothing", "recommended"],
)
def test_a_factor_event_of_the_right_shape_goes_in(companies: tuple[int, int], fields: dict[str, Any]) -> None:
    Scope3RowEdit.for_company(companies[0]).create(**values(**fields))


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        (NO_FACTOR | {"kind": "delete"}, KIND),
        ({"factor_choice": None}, SHAPE),
        ({"factor_choice": "가상"}, CHOICE),
        ({"factor_choice": "recommended"}, SHAPE),
        ({"factor_rank": 1}, SHAPE),
        ({"factor_choice": "applied", "factor_rank": 1}, SHAPE),
        ({"factor_choice": "recommended", "factor_rank": 0}, RANK),
        ({"factor_choice": "recommended", "factor_rank": 5}, RANK),
        ({"factor_title": None}, SHAPE),
        ({"factor_value": None}, SHAPE),
        ({"factor_source": None}, SHAPE),
        ({"kind": "exclude"}, SHAPE),
        (NO_FACTOR | {"kind": "restore", "co2e": "1.0"}, SHAPE),
        (NO_FACTOR | {"kind": "exclude", "ai_factor_source": "가상"}, SHAPE),
    ],
    ids=["kind", "no-choice", "bad-choice", "rec-no-rank", "custom-rank", "applied-rank", "rank-0", "rank-5",
         "no-title", "no-value", "no-source", "exclude-with-factor", "restore-with-co2e", "exclude-with-ai-source"],
)  # fmt: skip
def test_the_checks_refuse(companies: tuple[int, int], fields: dict[str, Any], constraint: str) -> None:
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        Scope3RowEdit.for_company(companies[0]).create(**values(**fields))
    assert constraint in str(caught.value)
    assert getattr(caught.value.__cause__, "sqlstate", None) == "23514"


def test_the_text_columns_have_their_lengths(companies: tuple[int, int]) -> None:
    with pytest.raises(DataError), transaction.atomic():
        Scope3RowEdit.for_company(companies[0]).create(**values(factor_title="가" * 301))
    Scope3RowEdit.for_company(companies[0]).create(**values(factor_title="가" * 300))
