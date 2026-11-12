# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 0007(밴드 GRJ1 ① — 근거 고침·재판단 칸 여섯). 옛 행(0006 의 표시·고침)은 남고 새 칸은 NULL 이며, 검토
GET 이 그 행을 evidence []·rejudges [] 로 읽는다. CHECK 넷이 주인 역할의 SQL 도 막고, 되돌리면 칸·제약이 사라지고
행은 남는다.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client

from esgapi.greenwash.tests.service import seed
from tests.support.http import login

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE = ("greenwash", "0006_ai_settings_terms")
AFTER = ("greenwash", "0007_review_mark_evidence")
NEW_COLUMNS = {
    "evidence_removed",
    "evidence_added",
    "evidence_edited_at",
    "evidence_edited_by_user_id",
    "evidence_basis_run_id",
    "rejudge_run_ids",
}
NEW_CHECKS = {
    "greenwash_review_marks_evidence_edit_check",
    "greenwash_review_marks_evidence_basis_check",
    "greenwash_review_marks_evidence_size_check",
    "greenwash_review_marks_rejudge_size_check",
}


def migrate(*targets: tuple[str, str]) -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())


def sql(statement: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params or [])
        return cursor.fetchall() if cursor.description else []


def columns() -> set[str]:
    rows = sql("SELECT column_name FROM information_schema.columns WHERE table_name = 'greenwash_review_marks'")
    return {str(row[0]) for row in rows}


def checks() -> set[str]:
    rows = sql(
        "SELECT conname FROM pg_constraint WHERE conrelid = 'greenwash_review_marks'::regclass AND contype = 'c'"
    )
    return {str(row[0]) for row in rows}


def old_review(company_id: int, run_id: int) -> None:
    """0006 의 표에 검토 하나와 표시 둘(채택 하나·등급 고침 하나)을 SQL 로."""
    sql(
        "INSERT INTO greenwash_reviews (created_at, updated_at, company_id, run_id, state) "
        "VALUES (now(), now(), %s, %s, 'in_review')",
        [company_id, run_id],
    )
    sql(
        "INSERT INTO greenwash_review_marks (created_at, updated_at, company_id, run_id, item_index, decision) "
        "VALUES (now(), now(), %s, %s, 0, 'adopted')",
        [company_id, run_id],
    )
    sql(
        "INSERT INTO greenwash_review_marks (created_at, updated_at, company_id, run_id, item_index, edited_level, "
        "level_edited_at, level_edited_by_user_id) VALUES (now(), now(), %s, %s, 1, 'Low', now(), 1)",
        [company_id, run_id],
    )


@pytest.fixture
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()


def test_0007_keeps_old_rows_and_reads_them_without_evidence(
    client: Client, companies: tuple[int, int], back_to_the_leaf: None
) -> None:
    a, _ = companies
    login(client)
    run_id = seed.run(a, result=seed.example("result-normal"))
    migrate(BEFORE)
    assert columns().isdisjoint(NEW_COLUMNS)  # 분모: 0006 에는 칸이 없다
    old_review(a, run_id)
    migrate(AFTER)
    assert columns() >= NEW_COLUMNS
    assert checks() >= NEW_CHECKS
    nulls = sql(
        "SELECT count(*) FROM greenwash_review_marks WHERE "
        + " AND ".join(f"{column} IS NULL" for column in sorted(NEW_COLUMNS))
    )
    assert nulls == [(2,)]
    got = client.get(f"/api/greenwash/runs/{run_id}/review").json()
    assert (got["schemaVersion"], got["evidence"], got["rejudges"]) == ("greenwash.review@3", [], [])
    assert [e["itemIndex"] for e in got["edits"]] == [1]  # 앞 고침 그대로


@pytest.mark.parametrize(
    "assignment",
    [
        "evidence_removed = '[]'::jsonb",  # 값만, added·때·사람 없음
        "evidence_removed = '[]'::jsonb, evidence_added = '[]'::jsonb, evidence_edited_at = now()",  # 사람 없음
        "evidence_basis_run_id = 7",  # 근거 고침 없는 기준
        "evidence_removed = '[]'::jsonb, evidence_added = to_jsonb(repeat('가', 131072)), evidence_edited_at = now(), "
        "evidence_edited_by_user_id = 1",  # 크기 그물
        "rejudge_run_ids = to_jsonb(repeat('1', 65536))",  # 크기 그물
    ],
    ids=["removed-only", "without-person", "basis-without-edit", "added-too-big", "rejudge-ids-too-big"],
)
def test_the_four_checks_hold_for_the_owner(companies: tuple[int, int], assignment: str) -> None:
    a, _ = companies
    old_review(a, 5001)
    with pytest.raises(IntegrityError), transaction.atomic():
        sql(f"UPDATE greenwash_review_marks SET {assignment} WHERE item_index = 0")
    # 분모: 넷 다 값이고 기준·재판단 id 가 있으면 된다
    sql(
        "UPDATE greenwash_review_marks SET evidence_removed = '[0]'::jsonb, evidence_added = '[]'::jsonb, "
        "evidence_edited_at = now(), evidence_edited_by_user_id = 1, evidence_basis_run_id = 7, "
        "rejudge_run_ids = '[7]'::jsonb WHERE item_index = 0"
    )


def test_rolling_back_to_0006_drops_the_columns_and_keeps_the_rows(
    companies: tuple[int, int], back_to_the_leaf: None
) -> None:
    a, _ = companies
    old_review(a, 5002)
    sql(
        "UPDATE greenwash_review_marks SET evidence_removed = '[]'::jsonb, evidence_added = '[]'::jsonb, "
        "evidence_edited_at = now(), evidence_edited_by_user_id = 1 WHERE item_index = 0"
    )
    migrate(BEFORE)
    assert columns().isdisjoint(NEW_COLUMNS)
    assert checks().isdisjoint(NEW_CHECKS)
    assert sql("SELECT item_index, decision FROM greenwash_review_marks WHERE run_id = 5002 ORDER BY 1") == [
        (0, "adopted"),
        (1, None),
    ]
