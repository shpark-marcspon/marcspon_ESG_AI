# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
"""원고작성 AI 설정 판의 저장·적용 서비스와 표의 제약·마이그레이션(밴드 RPA1 B3 — materiality 의 판별 복사).
업무 층: 진짜 DB(주인 역할 — GRANT 는 보안 층 tests/security/test_drafting_ai_settings.py 가 잰다).

    저장      v1·v2·다른 회사 v1 · 모델 생략 = 코드 값의 정규형 · 글 바이트 그대로·메모 strip · 기본 글과 같은 글도
              접지 않음 ·
              받기 거절(모델·프롬프트) → 행 0 · 메모만 다른 판 = 새 번호·같은 글 sha
    번호 경합  동시 저장 둘 → v1·v2 · 다시 시도를 다 쓰면 NameConflict
    적용      v1 → v2 → 기본 · 같은 판 다시 Unchanged · 남의 판 SettingMissing · 받기가 좁아진 판 SettingUnusable · 동시
              적용 둘 → 적용 판 하나
    DB 제약   부분 unique·번호 꼴·적용 때·크기 CHECK 둘·title 41자 · 마이그레이션 올림·내림·다시

글·메모는 지어낸 것이다(synthetic).
"""

import dataclasses
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import DataError, IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import (
    AcceptedPrompts,
    AiModelSlotSpec,
    defaults,
    prompts_sha256,
    to_input,
    version_status,
)
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.config import LlmConfig
from esgapi.drafting.flows import prompt_model_v2 as pm
from esgapi.drafting.models import DraftingAiSettingRow
from esgapi.drafting.service.selectors import ai_settings as selectors
from esgapi.drafting.service.services import ai_settings as services
from esgapi.drafting.tests.flows.test_prompt_model_v2 import CONFIG, model_body, prompts_body

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 23, 1, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 23, 2, 0, tzinfo=UTC)
OPERATOR = 9


def save(
    company_id: int,
    *,
    memo: str = "",
    model_settings: AiModelSettingsIn | None = None,
    prompts: AiPromptsIn | None = None,
) -> services.Created | services.ModelRefused | services.PromptsRefused | services.NameConflict:
    return services.create_setting(
        company_id=company_id,
        created_by_user_id=OPERATOR,
        title="지어낸 판",
        memo=memo,
        model_settings=model_settings,
        prompts=prompts,
    )


def created(company_id: int, **kwargs: Any) -> services.Created:
    found = save(company_id, **kwargs)
    assert isinstance(found, services.Created), found
    return found


def rows(company_id: int) -> list[tuple[Any, ...]]:
    return [
        (r.name, r.applied, r.applied_at, r.memo, r.created_by_user_id)
        for r in DraftingAiSettingRow.for_company(company_id).order_by("id")
    ]


def statuses(company_id: int) -> dict[str, str]:
    page = selectors.ai_setting_page(company_id=company_id, limit=50, offset=0)
    return {h.name: version_status(h.applied, h.applied_at) for h in page.items}


# ── 저장 ──


def test_saving_numbers_the_versions_per_company(companies: tuple[int, int]) -> None:
    a, b = companies
    assert created(a).name == "v1"
    assert created(a).name == "v2"
    assert created(b).name == "v1"
    assert [name for name, *_ in rows(a)] == ["v1", "v2"]


def test_the_omitted_model_is_the_defaults_normal_form(companies: tuple[int, int]) -> None:
    a, _ = companies
    v1 = created(a)
    row = DraftingAiSettingRow.for_company(a).get(id=v1.id)
    assert row.model_settings == to_input(defaults(CONFIG, pm.MODELS))
    assert row.prompts is None
    assert row.title == "지어낸 판"


def test_the_text_is_kept_byte_for_byte_and_the_memo_is_stripped(companies: tuple[int, int]) -> None:
    a, _ = companies
    text = "  ⟦지어낸 지시 글⟧\r\n두 줄째  \n"
    body = prompts_body(draft_system=text)
    body["steps"][1]["prompts"][0]["memo"] = "  지어낸 메모  \n"
    v1 = created(a, prompts=body)
    stored: Any = DraftingAiSettingRow.for_company(a).get(id=v1.id).prompts
    found = stored["steps"][1]["prompts"][0]
    assert (found["key"], found["text"], found["memo"]) == ("draft_system", text, "지어낸 메모")


def test_the_default_texts_are_not_folded_to_null(companies: tuple[int, int]) -> None:
    a, _ = companies
    v1 = created(a, prompts=prompts_body())
    stored = DraftingAiSettingRow.for_company(a).get(id=v1.id).prompts
    assert stored is not None and stored == prompts_body()


def test_a_memo_only_change_is_a_new_version_with_the_same_text_sha(companies: tuple[int, int]) -> None:
    a, _ = companies
    first = prompts_body()
    second = prompts_body()
    second["steps"][1]["prompts"][0]["memo"] = "지어낸 다른 메모"
    v1, v2 = created(a, prompts=first), created(a, prompts=second)
    assert (v1.name, v2.name) == ("v1", "v2")
    shas = []
    for setting in (v1, v2):
        found = selectors.ai_setting_detail(company_id=a, setting_id=setting.id)
        assert isinstance(found, selectors.AiSetting) and found.prompts is not None
        accepted = pm.accept_prompts(found.prompts)
        assert isinstance(accepted, AcceptedPrompts)
        shas.append(prompts_sha256(accepted))
    assert shas[0] == shas[1]


@pytest.mark.parametrize(
    ("kwargs", "refused"),
    [
        pytest.param({"model_settings": {"steps": []}}, services.ModelRefused, id="model-steps"),
        pytest.param({"model_settings": model_body(temperature=None)}, services.ModelRefused, id="temperature-null"),
        pytest.param({"prompts": {"steps": []}}, services.PromptsRefused, id="prompt-steps"),
        pytest.param({"prompts": prompts_body(map_user=" ")}, services.PromptsRefused, id="prompt-empty"),
        pytest.param(
            {"prompts": prompts_body(map_user=pm.default_text("map_user").replace("{목차}", ""))},
            services.PromptsRefused,
            id="placeholder",
        ),
    ],
)
def test_a_refused_save_writes_nothing(companies: tuple[int, int], kwargs: dict[str, Any], refused: type) -> None:
    a, _ = companies
    assert isinstance(save(a, **kwargs), refused)
    assert rows(a) == []


# ── 번호 경합 ──


def _both_read_then_insert(monkeypatch: pytest.MonkeyPatch, a: int) -> dict[str, object]:
    """두 스레드가 번호를 다 센 뒤(장벽 — 둘 다 v1 을 셈) INSERT 로 간다."""
    barrier = threading.Barrier(2)
    names: Callable[[int], tuple[str, ...]] = selectors.setting_names
    first = threading.local()

    def names_then_wait(company_id: int) -> tuple[str, ...]:
        found = names(company_id)
        if not getattr(first, "done", False):
            first.done = True
            barrier.wait(timeout=10)
        return found

    monkeypatch.setattr(selectors, "setting_names", names_then_wait)
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            with transaction.atomic(durable=True):
                result: object = save(a, memo=name)
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result

    threads = [threading.Thread(target=call, args=(name,)) for name in ("one", "two")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]
    return results


@pytest.mark.django_db(transaction=True)
def test_two_overlapping_saves_get_v1_and_v2(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a, _ = companies
    results = _both_read_then_insert(monkeypatch, a)
    assert sorted(r.name for r in results.values() if isinstance(r, services.Created)) == ["v1", "v2"], results
    assert [name for name, *_ in rows(a)] == ["v1", "v2"]


def test_a_name_breach_past_the_retries_is_a_name_conflict(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    created(a)
    calls: list[int] = []

    def always_empty(company_id: int) -> tuple[str, ...]:
        calls.append(company_id)
        return ()

    monkeypatch.setattr(selectors, "setting_names", always_empty)  # 늘 v1 을 센다
    assert save(a) == services.NameConflict()
    assert len(calls) == services.NAME_RETRIES
    assert [name for name, *_ in rows(a)] == ["v1"]


# ── 적용 ──


def test_apply_moves_the_one_applied_version(companies: tuple[int, int]) -> None:
    a, b = companies
    v1, v2 = created(a), created(a)
    created(b)
    assert services.apply_setting(company_id=a, setting_id=v1.id, now=NOW) == services.Applied(None, v1.id, "v1")
    assert statuses(a) == {"v1": "applied", "v2": "testing"}
    assert services.apply_setting(company_id=a, setting_id=v2.id, now=LATER) == services.Applied(v1.id, v2.id, "v2")
    assert statuses(a) == {"v1": "past", "v2": "applied"}
    assert services.apply_setting(company_id=a, setting_id=None, now=LATER) == services.Applied(v2.id, None, None)
    assert statuses(a) == {"v1": "past", "v2": "past"}
    assert rows(b) == [("v1", False, None, "", OPERATOR)]  # 남의 회사 판은 그대로


def test_applying_the_applied_version_again_changes_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    v1 = created(a)
    services.apply_setting(company_id=a, setting_id=v1.id, now=NOW)
    assert services.apply_setting(company_id=a, setting_id=v1.id, now=LATER) == services.Unchanged()
    assert rows(a) == [("v1", True, NOW, "", OPERATOR)]


def test_applying_a_foreign_version_is_missing(companies: tuple[int, int]) -> None:
    a, b = companies
    mine, theirs = created(a), created(b)
    for wrong in (theirs.id, theirs.id + mine.id + 1000):
        assert services.apply_setting(company_id=a, setting_id=wrong, now=NOW) == selectors.SettingMissing()
    assert selectors.ai_setting_detail(company_id=a, setting_id=theirs.id) == selectors.SettingMissing()
    assert rows(b) == [("v1", False, None, "", OPERATOR)]


class NarrowSource:
    """받기를 좁힌 원천: 칸 둘의 허용 경로를 light-openai-41 하나로(저장 경로가 밖이 된다)."""

    def config(self) -> LlmConfig:
        return CONFIG

    def steps(self) -> Sequence[AiModelSlotSpec]:
        return tuple(dataclasses.replace(slot, routes=("light-openai-41",)) for slot in pm.MODELS)


def test_a_version_the_rules_no_longer_take_is_not_applied(companies: tuple[int, int]) -> None:
    a, _ = companies
    v1 = created(a, model_settings=model_body(route="standard-openai-41", temperature=0.3))
    found = services.apply_setting(company_id=a, setting_id=v1.id, now=NOW, models=NarrowSource())
    assert found == services.SettingUnusable("ai_model_route_unknown", "v1")
    assert rows(a) == [("v1", False, None, "", OPERATOR)]
    assert services.apply_setting(company_id=a, setting_id=None, now=NOW, models=NarrowSource()) == services.Unchanged()


def test_a_saved_text_the_narrowed_rules_refuse_is_not_applied(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """저장 글을 지금 받기로 다시 받는다(TR4 ③ 검증 B1): 글 상한을 10자로 좁히면 저장 글 판은 적용되지 않는다."""
    a, _ = companies
    v1 = created(a, prompts=prompts_body(draft_system="지어낸 초안 지침 — 열 글자보다 길다"))
    code_text = created(a)  # 분모: 코드 글 판(prompts NULL)은 좁혀도 적용된다
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)
    found = services.apply_setting(company_id=a, setting_id=v1.id, now=NOW)
    assert found == services.SettingUnusable("ai_prompt_text_length", "v1")
    assert not DraftingAiSettingRow.for_company(a).filter(applied=True).exists()
    assert isinstance(services.apply_setting(company_id=a, setting_id=code_text.id, now=NOW), services.Applied)


@pytest.mark.django_db(transaction=True)
def test_two_overlapping_applies_leave_one_applied(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a, _ = companies
    v1, v2 = created(a), created(a)
    barrier = threading.Barrier(2)
    lock: Callable[[int], Any] = selectors.lock_settings

    def wait_then_lock(company_id: int) -> Any:
        barrier.wait(timeout=10)  # 둘이 함께 잠그러 간다 — 하나는 줄을 선다
        return lock(company_id)

    monkeypatch.setattr(selectors, "lock_settings", wait_then_lock)
    results: dict[int, object] = {}
    guard = threading.Lock()

    def call(setting_id: int) -> None:
        try:
            with transaction.atomic(durable=True):
                result: object = services.apply_setting(company_id=a, setting_id=setting_id, now=NOW)
        except BaseException as err:
            result = err
        finally:
            connections.close_all()
        with guard:
            results[setting_id] = result

    threads = [threading.Thread(target=call, args=(sid,)) for sid in (v1.id, v2.id)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]
    assert all(isinstance(r, services.Applied) for r in results.values()), results
    assert sum(1 for _, applied, *_ in rows(a) if applied) == 1


# ── DB 의 제약 ──

COLUMNS = "created_at, updated_at, company_id, name, title, model_settings, prompts, memo, created_by_user_id, applied"


def _insert(
    company_id: int,
    name: str,
    *,
    applied: bool = False,
    at: str = "NULL",
    title: str = "'지어낸 판'",
    model: str = "'{}'",
    prompts: str = "NULL",
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO drafting_ai_settings ({COLUMNS}, applied_at) "
            f"VALUES (now(), now(), %s, %s, {title}, {model}::jsonb, {prompts}::jsonb, '', 1, %s, {at})",
            [company_id, name, applied],
        )


@pytest.mark.parametrize(
    ("second", "constraint"),
    [
        pytest.param(
            {"name": "v2", "applied": True, "at": "now()"}, "drafting_ai_settings_one_applied_uniq", id="two-applied"
        ),
        pytest.param({"name": "v1"}, "drafting_ai_settings_company_name_uniq", id="same-name"),
    ],
)
def test_the_unique_rules_hold_in_sql(companies: tuple[int, int], second: dict[str, Any], constraint: str) -> None:
    a, b = companies
    _insert(a, "v1", applied=True, at="now()")
    _insert(b, "v1", applied=True, at="now()")  # 분모: 다른 회사는 같은 번호·적용 하나가 된다
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        _insert(a, second["name"], applied=second.get("applied", False), at=second.get("at", "NULL"))


@pytest.mark.parametrize(
    ("name", "changes", "constraint"),
    [
        pytest.param("x1", {}, "drafting_ai_settings_name_check", id="name"),
        pytest.param("v0", {}, "drafting_ai_settings_name_check", id="name-zero"),
        pytest.param("v1", {"applied": True}, "drafting_ai_settings_applied_check", id="applied-without-time"),
        pytest.param(
            "v1",
            {"prompts": "jsonb_build_object('t', repeat('a', 131100))"},
            "drafting_ai_settings_prompts_size_check",
            id="prompts-size",
        ),
        pytest.param(
            "v1",
            {"model": "jsonb_build_object('t', repeat('a', 4100))"},
            "drafting_ai_settings_model_settings_size_check",
            id="model-size",
        ),
        pytest.param("v1", {"title": "''"}, "drafting_ai_settings_title_check", id="title-empty"),
    ],
)
def test_the_checks_hold_in_sql(
    companies: tuple[int, int], name: str, changes: dict[str, Any], constraint: str
) -> None:
    a, _ = companies
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        _insert(a, name, **changes)
    _insert(a, "v1", applied=True, at="now()")  # 분모: 맞는 행은 들어간다


def test_a_41_char_title_is_refused_by_the_db(companies: tuple[int, int]) -> None:
    a, _ = companies
    with pytest.raises((IntegrityError, DataError)), transaction.atomic():
        _insert(a, "v1", title="'" + "가" * 41 + "'")
    _insert(a, "v1", title="'" + "가" * 40 + "'")  # 분모: 40자는 들어간다


def test_a_saved_text_the_module_slot_rule_refuses_is_not_applied(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """모듈 자리 지킴도 다시 받기에 든다(P23): accept_prompts 를 거절로 바꾸면 저장 글 판은 적용되지 않는다."""
    a, _ = companies
    v1 = created(a, prompts=prompts_body())
    refused = core_ai_settings.PromptRefused(
        "ai_prompt_placeholder_missing", "지어낸 거절", "prompts.steps.0.prompts.1.text"
    )
    monkeypatch.setattr(pm, "accept_prompts", lambda given: refused)
    found = services.apply_setting(company_id=a, setting_id=v1.id, now=NOW)
    assert found == services.SettingUnusable("ai_prompt_placeholder_missing", "v1")
    assert not DraftingAiSettingRow.for_company(a).filter(applied=True).exists()


# ── 마이그레이션 ──


def _migrate(*targets: tuple[str, str | None]) -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())


def _tables() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'drafting%%'")
        return {str(row[0]) for row in cursor.fetchall()}


FIRST: set[str] = {"drafting_projects", "drafting_project_documents", "drafting_outlines", "drafting_outline_nodes"}


@pytest.mark.django_db(transaction=True)
def test_the_migration_goes_up_down_and_up_again() -> None:
    """0002 만 내린다 — 0001 의 표 넷은 그대로(기존 표 0줄)."""
    assert _tables() == FIRST | {"drafting_ai_settings"}
    try:
        _migrate(("drafting", "0001_initial"))
        assert _tables() == FIRST
    finally:
        _migrate()
    assert _tables() == FIRST | {"drafting_ai_settings"}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid = 'drafting_ai_settings'::regclass "
            "AND contype IN ('c', 'u') UNION SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'drafting_ai_settings' AND indexname LIKE '%%_uniq'"
        )
        names = sorted(str(row[0]) for row in cursor.fetchall())
    assert names == sorted(
        f"drafting_ai_settings_{n}"
        for n in (
            "company_name_uniq",
            "one_applied_uniq",
            "name_check",
            "applied_check",
            "prompts_size_check",
            "model_settings_size_check",
            "title_check",
        )
    )
