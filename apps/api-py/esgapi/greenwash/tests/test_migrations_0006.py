# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 greenwash 0006(밴드 G2d §3-2-2): 판 행이 있는 DB 에서 0006 이 서고 그 행의 terms 는 NULL(코드 기본
목록 — 채우지 않는다)이며 크기 CHECK 를 지나고, 되돌리면 칸·제약이 지워진다. 끝에 모든 앱을 맨 끝 마이그레이션으로
다시 올린다. 크기 CHECK 는 상한(16384 — 문면 그대로)+1 이 IntegrityError·상한은 된다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 낱말은 지어낸 것이다.
"""

import json
from collections.abc import Iterator

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from esgapi.greenwash.models import AI_SETTING_TERMS_MAX_OCTETS

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE = ("greenwash", "0005_ai_settings_prompts")
AFTER = ("greenwash", "0006_ai_settings_terms")
CHECK = "greenwash_ai_settings_terms_size_check"
INSERT = (
    "INSERT INTO greenwash_ai_settings (created_at, updated_at, company_id, name, criteria, model_settings, terms, "
    "eval_prompt_sha256, memo, created_by_user_id, applied) "
    "VALUES (now(), now(), %s, %s, '{}'::jsonb, '{}'::jsonb, %s::jsonb, %s, '', 1, false)"
)


def migrate(*targets: tuple[str, str]) -> MigrationExecutor:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())
    return MigrationExecutor(connection)


def columns() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'greenwash_ai_settings'")
        return {str(row[0]) for row in cursor.fetchall()}


def constraints() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'greenwash_ai_settings'::regclass AND contype = 'c'"
        )
        return {str(row[0]) for row in cursor.fetchall()}


def of_octets(n: int) -> str:
    """jsonb::text 가 정확히 n 바이트인 JSON 글([{"text": "xxx…", "enabled": true}] — 머리 11 + 꼬리 20)."""
    return json.dumps([{"text": "x" * (n - 31), "enabled": True}])


def insert(company_id: int, name: str, terms: str | None) -> None:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(INSERT, [company_id, name, terms, "a" * 64])


def octets(company_id: int, name: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT octet_length(terms::text) FROM greenwash_ai_settings WHERE company_id = %s AND name = %s",
            [company_id, name],
        )
        (found,) = cursor.fetchone() or (None,)
    assert isinstance(found, int)
    return found


@pytest.fixture
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()


def test_0006_leaves_an_existing_row_null_and_rolls_back(companies: tuple[int, int], back_to_the_leaf: None) -> None:
    a, _ = companies
    migrate(BEFORE)
    assert "terms" not in columns()  # 분모: 0005 에는 칸이 없다
    assert CHECK not in constraints()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO greenwash_ai_settings (created_at, updated_at, company_id, name, criteria, model_settings, "
            "eval_prompt_sha256, memo, created_by_user_id, applied) "
            "VALUES (now(), now(), %s, 'v1', '{}'::jsonb, '{}'::jsonb, %s, '', 1, false)",
            [a, "a" * 64],
        )
    migrate(AFTER)
    assert "terms" in columns()
    assert CHECK in constraints()
    with connection.cursor() as cursor:
        cursor.execute("SELECT terms FROM greenwash_ai_settings WHERE company_id = %s", [a])
        assert cursor.fetchall() == [(None,)]  # 옛 행은 채우지 않는다(RunPython 0 — NULL = 코드 기본 목록)
    migrate(BEFORE)
    assert "terms" not in columns()
    assert CHECK not in constraints()
    migrate(AFTER)


def test_the_size_check_refuses_one_byte_over(companies: tuple[int, int]) -> None:
    a, _ = companies
    assert AI_SETTING_TERMS_MAX_OCTETS == 16384  # 0006 의 문면 값과 같다
    insert(a, "v1", of_octets(16384))  # 분모: 상한은 된다
    assert octets(a, "v1") == 16384
    with pytest.raises(IntegrityError, match=CHECK):
        insert(a, "v2", of_octets(16385))
    insert(a, "v3", None)  # NULL 은 지난다
