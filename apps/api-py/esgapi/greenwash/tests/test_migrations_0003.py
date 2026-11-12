# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 greenwash 0003(밴드 AS2b §3-3-2): 판 행이 있는 DB 에서 0003 이 서고 그 행의 model_settings 가 이행
상수(그때의 코드 값)로 채워지며, 되돌리면 칸이 지워진다. 끝에 모든 앱을 맨 끝 마이그레이션으로 다시 올린다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 이름·글은 지어낸 것이다.
"""

import importlib
import json
from collections.abc import Iterator

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE = ("greenwash", "0002_ai_settings")
AFTER = ("greenwash", "0003_ai_settings_model_settings")
MIGRATION = importlib.import_module("esgapi.greenwash.migrations.0003_ai_settings_model_settings")


def migrate(*targets: tuple[str, str]) -> MigrationExecutor:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())
    return MigrationExecutor(connection)  # 새로 읽은 그래프·적용 기록


def columns() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'greenwash_ai_settings'",
        )
        return {str(row[0]) for row in cursor.fetchall()}


@pytest.fixture
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()  # 끝에 늘 다시 올린다(다음 시험이 0003 의 칸을 본다)


def test_0003_fills_an_existing_row_and_rolls_back(companies: tuple[int, int], back_to_the_leaf: None) -> None:
    a, _ = companies
    migrate(BEFORE)
    assert "model_settings" not in columns()  # 분모: 0002 에는 칸이 없다
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO greenwash_ai_settings (created_at, updated_at, company_id, name, criteria, "
            "eval_prompt_sha256, memo, created_by_user_id, applied) "
            "VALUES (now(), now(), %s, 'v1', '{}'::jsonb, %s, '', 1, false)",
            [a, "a" * 64],
        )
    migrate(AFTER)
    with connection.cursor() as cursor:
        cursor.execute("SELECT model_settings FROM greenwash_ai_settings WHERE company_id = %s", [a])
        (filled,) = cursor.fetchone() or ("null",)
    assert json.loads(str(filled)) == MIGRATION.MODEL_SETTINGS_BEFORE_AS2B  # 날 커서는 jsonb 를 글자로 준다
    with connection.cursor() as cursor:  # 기본값은 칸에 남지 않는다(preserve_default=False)
        cursor.execute(
            "SELECT column_default, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'greenwash_ai_settings' AND column_name = 'model_settings'"
        )
        assert cursor.fetchone() == (None, "NO")
    migrate(BEFORE)
    assert "model_settings" not in columns()
