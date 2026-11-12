# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 greenwash 0004(밴드 G1b-3 ①): 검토·표시 행이 있는 DB(0003)에서 0004 가 서고 옛 행의 값이 그대로·고침
칸은 NULL 이며, 검토 GET 이 그 행을 review@2·edits [] 로 읽는다. CHECK 넷이 주인 역할의 SQL 도 막고, 되돌리면 칸·제약이
지워지고 행은 남는다(고친 값은 잃는다). 끝에 모든 앱을 맨 끝 마이그레이션으로 다시 올린다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 이름·글은 지어낸 것이다.
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

BEFORE = ("greenwash", "0003_ai_settings_model_settings")
AFTER = ("greenwash", "0004_review_mark_edits")
LEAF = ("greenwash", "0007_review_mark_evidence")
EDIT_COLUMNS = {
    "edited_level",
    "level_edited_at",
    "level_edited_by_user_id",
    "edited_reason_bullets",
    "reasons_edited_at",
    "reasons_edited_by_user_id",
    "edited_fix_paragraph",
    "fix_edited_at",
    "fix_edited_by_user_id",
}
EDIT_CHECKS = {
    "greenwash_review_marks_level_edit_check",
    "greenwash_review_marks_reasons_edit_check",
    "greenwash_review_marks_fix_edit_check",
    "greenwash_review_marks_edit_level_check",
}


def migrate(*targets: tuple[str, str]) -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())


def columns() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'greenwash_review_marks'")
        return {str(row[0]) for row in cursor.fetchall()}


def checks() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'greenwash_review_marks'::regclass AND contype = 'c'"
        )
        return {str(row[0]) for row in cursor.fetchall()}


def sql(statement: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params or [])
        return cursor.fetchall() if cursor.description else []


def marks(run_id: int) -> list[tuple[Any, ...]]:
    return sql(
        "SELECT item_index, decision, exclude_reason FROM greenwash_review_marks WHERE run_id = %s ORDER BY item_index",
        [run_id],
    )


@pytest.fixture
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()  # 끝에 늘 다시 올린다(다음 시험이 0004 의 칸을 본다)


def old_review(company_id: int, run_id: int, state: str) -> None:
    """0003 의 표에 검토 하나와 표시 셋(채택·제외·decision NULL)을 SQL 로."""
    confirmed = state == "confirmed"
    sql(
        "INSERT INTO greenwash_reviews (created_at, updated_at, company_id, run_id, state, confirmed_at, "
        "confirmed_by_user_id) VALUES (now(), now(), %s, %s, %s, %s, %s)",
        [company_id, run_id, state, "2026-10-20T06:30:00+00:00" if confirmed else None, 987654 if confirmed else None],
    )
    for index, decision, reason in ((0, "adopted", None), (1, "excluded", "지은 사유"), (2, None, None)):
        sql(
            "INSERT INTO greenwash_review_marks (created_at, updated_at, company_id, run_id, item_index, decision, "
            "exclude_reason) VALUES (now(), now(), %s, %s, %s, %s, %s)",
            [company_id, run_id, index, decision, reason],
        )


def test_0004_keeps_old_rows_and_reads_them_as_review_at_2(
    client: Client, companies: tuple[int, int], back_to_the_leaf: None
) -> None:
    a, _ = companies
    login(client)
    in_review = seed.run(a, result=seed.example("result-normal"))
    confirmed = seed.run(a, result=seed.example("result-normal"))
    migrate(BEFORE)
    assert columns().isdisjoint(EDIT_COLUMNS)  # 분모: 0003 에는 칸이 없다
    old_review(a, in_review, "in_review")
    old_review(a, confirmed, "confirmed")
    before = (marks(in_review), marks(confirmed))

    migrate(AFTER)
    assert columns() >= EDIT_COLUMNS
    assert checks() >= EDIT_CHECKS
    assert (marks(in_review), marks(confirmed)) == before
    nulls = sql(
        "SELECT count(*) FROM greenwash_review_marks WHERE "
        + " AND ".join(f"{column} IS NULL" for column in sorted(EDIT_COLUMNS))
    )
    assert nulls == [(6,)]

    # 옛 행 이전: 검토 GET 이 edits [] · marks 는 앞과 같은 값. 지금 코드는 0007(GRJ1) 칸을 읽으므로 끝 판까지 올린 뒤
    # 읽는다(판 글자는 지금 코드의 @3 — 검토 JSON 은 저장하지 않는다)
    migrate(LEAF)
    got = client.get(f"/api/greenwash/runs/{in_review}/review").json()
    assert (got["schemaVersion"], got["state"], got["edits"]) == ("greenwash.review@3", "in_review", [])
    assert got["marks"] == [
        {"itemIndex": 0, "decision": "adopted", "excludeReason": None},
        {"itemIndex": 1, "decision": "excluded", "excludeReason": "지은 사유"},
    ]
    sealed = client.get(f"/api/greenwash/runs/{confirmed}/review").json()
    assert (sealed["state"], sealed["edits"], sealed["confirmedBy"]["name"]) == ("confirmed", [], "알 수 없는 사용자")


@pytest.mark.parametrize(
    "assignment",
    [
        "edited_level = 'Low'",  # 값만, 때·사람 없음
        "edited_level = 'high', level_edited_at = now(), level_edited_by_user_id = 1",  # 등급 값 밖
        "level_edited_at = now(), level_edited_by_user_id = 1",  # 때·사람만
        "edited_reason_bullets = '[\"가\"]'::jsonb, reasons_edited_at = now()",  # 사람 없음
        "edited_fix_paragraph = '가', fix_edited_by_user_id = 1",  # 때 없음
    ],
    ids=["level-value-only", "lowercase-level", "level-without-value", "reasons-without-person", "fix-without-time"],
)
def test_the_four_checks_hold_for_the_owner(companies: tuple[int, int], assignment: str) -> None:
    a, _ = companies
    old_review(a, 5001, "in_review")
    with pytest.raises(IntegrityError), transaction.atomic():
        sql(f"UPDATE greenwash_review_marks SET {assignment} WHERE item_index = 0")
    # 분모: 셋 다 값이면 된다
    sql(
        "UPDATE greenwash_review_marks SET edited_level = 'Low', level_edited_at = now(), level_edited_by_user_id = 1 "
        "WHERE item_index = 0"
    )


def test_rolling_back_to_0003_drops_the_columns_and_keeps_the_rows(
    client: Client, companies: tuple[int, int], back_to_the_leaf: None
) -> None:
    a, _ = companies
    login(client)
    run_id = seed.run(a, result=seed.example("result-normal"))
    body = {
        "marks": [{"itemIndex": 0, "decision": "excluded", "excludeReason": "지은 사유"}],
        "edits": [{"itemIndex": 1, "level": "Low", "reasonBullets": None, "fixParagraph": "고친 글"}],
    }
    assert (
        client.put(f"/api/greenwash/runs/{run_id}/review", data=body, content_type="application/json").status_code
        == 200
    )
    assert sql("SELECT edited_level FROM greenwash_review_marks WHERE item_index = 1") == [("Low",)]
    migrate(BEFORE)
    assert columns().isdisjoint(EDIT_COLUMNS)
    assert checks().isdisjoint(EDIT_CHECKS)
    assert marks(run_id) == [(0, "excluded", "지은 사유"), (1, None, None)]  # 행은 남고, 고친 값은 잃는다
