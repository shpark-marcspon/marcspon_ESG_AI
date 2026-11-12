# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 greenwash 0005(밴드 AS3a-2 §3-2-2): 판 행이 있는 DB 에서 0005 가 서고 그 행의 prompts·title 은 NULL
(채우지 않는다 — MARC-ENT-387 노트)이며 CHECK 셋을 지나고, 되돌리면 칸·제약이 지워진다. 끝에 모든 앱을 맨 끝
마이그레이션으로 다시 올린다. 크기 CHECK 둘은 상한+1 이 IntegrityError·상한은 됨, 이름 CHECK 는 빈 글이 IntegrityError,
prompts_size 는 postgres 의 octet_length(prompts::text) 와 같다(AS3a-1 ★D).

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 이름·글은 지어낸 것이다.
"""

import json
from collections.abc import Iterator

import pytest
from django.db import DataError, IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from esgapi.core.calc.ai_settings import AcceptedPrompts, prompts_input, prompts_size
from esgapi.core.contracts.ai_setting_shapes import PROMPTS_MAX_OCTETS
from esgapi.greenwash.flows import prompt_model_e0

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE = ("greenwash", "0004_review_mark_edits")
AFTER = ("greenwash", "0005_ai_settings_prompts")
CHECKS = {
    "greenwash_ai_settings_prompts_size_check",
    "greenwash_ai_settings_model_settings_size_check",
    "greenwash_ai_settings_title_check",
}
INSERT = (
    "INSERT INTO greenwash_ai_settings (created_at, updated_at, company_id, name, criteria, model_settings, prompts, "
    "title, eval_prompt_sha256, memo, created_by_user_id, applied) "
    "VALUES (now(), now(), %s, %s, '{}'::jsonb, %s::jsonb, %s::jsonb, %s, %s, '', 1, false)"
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
    """jsonb::text 가 정확히 n 바이트인 JSON 글({"a": "xxx…"} — 머리 7 + 꼬리 2)."""
    return json.dumps({"a": "x" * (n - 9)})


def insert(company_id: int, name: str, *, model: str = "{}", prompts: str | None = None, title: str | None = None):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(INSERT, [company_id, name, model, prompts, title, "a" * 64])


@pytest.fixture
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()


def test_0005_leaves_an_existing_row_null_and_rolls_back(companies: tuple[int, int], back_to_the_leaf: None) -> None:
    a, _ = companies
    migrate(BEFORE)
    assert {"prompts", "title"}.isdisjoint(columns())  # 분모: 0004 에는 칸이 없다
    assert CHECKS.isdisjoint(constraints())
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO greenwash_ai_settings (created_at, updated_at, company_id, name, criteria, model_settings, "
            "eval_prompt_sha256, memo, created_by_user_id, applied) "
            "VALUES (now(), now(), %s, 'v1', '{}'::jsonb, '{}'::jsonb, %s, '', 1, false)",
            [a, "a" * 64],
        )
    migrate(AFTER)
    assert {"prompts", "title"} <= columns()
    assert constraints() >= CHECKS
    with connection.cursor() as cursor:
        cursor.execute("SELECT prompts, title FROM greenwash_ai_settings WHERE company_id = %s", [a])
        assert cursor.fetchall() == [(None, None)]  # 옛 행은 채우지 않는다(RunPython 0)
    migrate(BEFORE)
    assert {"prompts", "title"}.isdisjoint(columns())
    assert CHECKS.isdisjoint(constraints())
    migrate(AFTER)


def test_the_size_checks_refuse_one_byte_over(companies: tuple[int, int]) -> None:
    a, _ = companies
    insert(a, "v1", prompts=of_octets(PROMPTS_MAX_OCTETS))  # 분모: 상한은 된다
    insert(a, "v2", model=of_octets(4096))
    with pytest.raises(IntegrityError, match="greenwash_ai_settings_prompts_size_check"):
        insert(a, "v3", prompts=of_octets(PROMPTS_MAX_OCTETS + 1))
    with pytest.raises(IntegrityError, match="greenwash_ai_settings_model_settings_size_check"):
        insert(a, "v4", model=of_octets(4097))


def test_the_title_check_refuses_an_empty_name(companies: tuple[int, int]) -> None:
    """빈 글은 CHECK 가, 41자는 칸 varchar(40) 가 막는다(둘 다 받기의 422 가 먼저 — 여기는 마지막 그물)."""
    a, _ = companies
    insert(a, "v1", title="가" * 40)  # 분모: 40자는 된다
    with pytest.raises(IntegrityError, match="greenwash_ai_settings_title_check"):
        insert(a, "v2", title="")
    with pytest.raises(DataError):
        insert(a, "v3", title="가" * 41)


def test_prompts_size_is_the_octets_postgres_counts(companies: tuple[int, int]) -> None:
    """core prompts_size(정규형) == octet_length(prompts::text) — 한글·4바이트 글자·줄바꿈·탭·따옴표가 섞인 글."""
    a, _ = companies
    texts = ["찾기 글\n둘째 줄\t탭", '판정 "따옴표" \\ 글 😀', "다듬기 글 \u0001 제어", "Low 글"]
    given = {
        "steps": [
            {
                "key": "judge",
                "prompts": [
                    {"key": key, "text": text, "memo": f"  지어낸 메모 {i} 😀  "}
                    for i, ((key, _, _), text) in enumerate(zip(prompt_model_e0.PROMPTS, texts, strict=True))
                ],
            }
        ]
    }
    accepted = prompt_model_e0.accept_prompts(given)  # pyright: ignore[reportArgumentType]
    assert isinstance(accepted, AcceptedPrompts)
    insert(a, "v1", prompts=json.dumps(prompts_input(accepted), ensure_ascii=False))
    with connection.cursor() as cursor:
        cursor.execute("SELECT octet_length(prompts::text) FROM greenwash_ai_settings WHERE company_id = %s", [a])
        (octets,) = cursor.fetchone() or (None,)
    assert octets == prompts_size(accepted)
