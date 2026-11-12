# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
"""회사별 AI 설정 판의 저장·적용 서비스와 표의 제약(밴드 G2c2 §3-2-1~4). 업무 층: 진짜 DB(주인 역할 — GRANT 는 보안 층
tests/security 가 잰다).

    3-2-1  저장 → v1, 다시 → v2, 다른 회사 첫 저장 → v1, criteria.version 은 이름으로 덮임, 받기 거절 셋 → 행 0
    3-2-2  이름 경합: 동시 저장 둘 → v1·v2, 이름 밖 제약 위반은 올라옴
    3-2-3  적용 v1 → v2 → 기본 → v1: 늘 적용 ≤ 1·상태 셋, 같은 판 다시 → Unchanged, 두 연결 동시 적용 → 끝에 하나
    3-2-4  부분 unique·CHECK 를 SQL 로 어기면 DB 가 막음

기준 글은 지어낸 것이다(synthetic).
"""

import copy
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, connection, connections, transaction

from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.flows import colab_e0
from esgapi.greenwash.flows.criteria_e0 import default_criteria
from esgapi.greenwash.models import GreenwashAiSettingRow
from esgapi.greenwash.service.selectors import ai_settings as selectors
from esgapi.greenwash.service.services import ai_settings as services

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 20, 1, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 20, 2, 0, tzinfo=UTC)
OPERATOR = 9


def edited(text: str = "지어낸 기준 글: 근거 없이 쓴 「친환경」 낱말", version: str = "draft-1") -> GreenwashCriteria:
    """기본 판에서 high-4 줄의 글만 바꾼 기준표."""
    criteria = copy.deepcopy(default_criteria())
    criteria["version"] = version
    criteria["rows"][9]["text"] = text
    return criteria


def save(
    company_id: int, criteria: object, memo: str = ""
) -> (
    services.Created
    | services.CriteriaRefused
    | services.ModelRefused
    | services.PromptsRefused
    | services.TermsRefused
    | services.NameConflict
):
    return services.create_setting(
        company_id=company_id, created_by_user_id=OPERATOR, title="지어낸 판", criteria=criteria, memo=memo
    )


def rows(company_id: int) -> list[tuple[Any, ...]]:
    return list(
        GreenwashAiSettingRow.for_company(company_id)
        .order_by("id")
        .values_list("name", "applied", "applied_at", "memo", "created_by_user_id")
    )


def statuses(company_id: int) -> dict[str, str]:
    page = selectors.ai_setting_page(company_id=company_id, limit=100, offset=0)
    return {s.name: selectors.status_of(s.applied, s.applied_at) for s in page.items}


# ── 3-2-1 저장 ──


def test_saving_names_the_versions_per_company(companies: tuple[int, int]) -> None:
    a, b = companies
    first = save(a, edited(), memo="첫 판의 메모")
    second = save(a, edited("지어낸 둘째 글"))
    other = save(b, edited())
    assert (first, second, other) == (
        services.Created(first.id, "v1"),  # pyright: ignore[reportAttributeAccessIssue]
        services.Created(second.id, "v2"),  # pyright: ignore[reportAttributeAccessIssue]
        services.Created(other.id, "v1"),  # pyright: ignore[reportAttributeAccessIssue]
    )
    assert rows(a) == [("v1", False, None, "첫 판의 메모", OPERATOR), ("v2", False, None, "", OPERATOR)]
    assert rows(b) == [("v1", False, None, "", OPERATOR)]


def test_the_saved_criteria_carry_the_server_name_and_their_sha(companies: tuple[int, int]) -> None:
    a, _ = companies
    created = save(a, edited(version="whatever-the-client-said"))
    assert isinstance(created, services.Created)
    found = selectors.ai_setting_detail(company_id=a, setting_id=created.id)
    assert isinstance(found, selectors.AiSetting)
    assert found.criteria["version"] == "v1"
    assert found.criteria["rows"][9]["text"] == "지어낸 기준 글: 근거 없이 쓴 「친환경」 낱말"
    assert found.eval_prompt_sha256 == colab_e0.run_versions(found.criteria)["evalPromptSha256"]
    assert found.eval_prompt_sha256 != colab_e0.run_versions(None)["evalPromptSha256"]  # 분모: 기본 판과 다른 글


@pytest.mark.parametrize(
    ("broken", "code"),
    [
        pytest.param(lambda c: c.update(rows=c["rows"][:14]), "CRITERIA_ROWS_FIXED", id="fourteen-rows"),
        pytest.param(lambda c: c["rows"][9].update(text="   "), "CRITERIA_TEXT_LENGTH", id="blank-text"),
        pytest.param(lambda c: c.update(schemaVersion="greenwash.criteria@2"), "CRITERIA_SCHEMA_VERSION", id="shape"),
    ],
)
def test_a_refused_criteria_writes_nothing(
    companies: tuple[int, int], broken: Callable[[dict[str, Any]], None], code: str
) -> None:
    a, _ = companies
    criteria: dict[str, Any] = dict(edited())
    broken(criteria)
    refused = save(a, criteria)
    assert isinstance(refused, services.CriteriaRefused)
    assert refused.code == code and refused.message
    assert rows(a) == []
    assert isinstance(save(a, edited()), services.Created)  # 분모: 고친 기준표는 저장된다


def test_the_name_counts_only_this_companys_versions(companies: tuple[int, int]) -> None:
    a, b = companies
    for _ in range(3):
        save(b, edited())
    assert save(a, edited()) == services.Created(GreenwashAiSettingRow.for_company(a).get().id, "v1")


def test_the_page_shows_only_this_companys_versions(companies: tuple[int, int]) -> None:
    a, b = companies
    mine = save(a, edited())
    for _ in range(2):
        save(b, edited())
    assert isinstance(mine, services.Created)
    page = selectors.ai_setting_page(company_id=a, limit=10, offset=0)
    assert (page.total, [s.id for s in page.items], page.applied_id) == (1, [mine.id], None)
    assert selectors.ai_setting_page(company_id=b, limit=10, offset=0).total == 2  # 분모: 남의 판은 거기 있다


def test_the_page_is_newest_first_and_cut(companies: tuple[int, int]) -> None:
    a, _ = companies
    for i in range(3):
        save(a, edited(f"지어낸 글 {i}"))
    page = selectors.ai_setting_page(company_id=a, limit=2, offset=1)
    assert (page.total, [s.name for s in page.items]) == (3, ["v2", "v1"])


# ── 3-2-2 이름 경합 ──


def _both_read_then_insert(monkeypatch: pytest.MonkeyPatch, a: int) -> dict[str, object]:
    """두 스레드가 이름을 다 센 뒤(장벽 — 둘 다 v1 을 셈) INSERT 로 간다. 이름 → 결과(또는 예외)."""
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
                result: object = save(a, edited(f"지어낸 글 {name}"))
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


@pytest.mark.django_db(transaction=True)
def test_another_constraint_breach_is_not_retried(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a, _ = companies
    monkeypatch.setattr(colab_e0, "run_versions", lambda criteria: {"evalPromptSha256": "not-a-sha"})
    with pytest.raises(IntegrityError, match="greenwash_ai_settings_sha_check"):
        save(a, edited())
    assert rows(a) == []


def test_a_name_breach_past_the_retries_is_a_name_conflict(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    save(a, edited())
    monkeypatch.setattr(selectors, "setting_names", lambda company_id: ())  # 늘 v1 을 센다
    assert save(a, edited()) == services.NameConflict()
    assert [name for name, *_ in rows(a)] == ["v1"]


# ── 3-2-3 적용 ──


def test_apply_moves_the_one_applied_version(companies: tuple[int, int]) -> None:
    a, b = companies
    v1 = save(a, edited())
    v2 = save(a, edited("지어낸 둘째 글"))
    other = save(b, edited())
    assert isinstance(v1, services.Created) and isinstance(v2, services.Created) and isinstance(other, services.Created)
    assert statuses(a) == {"v1": "testing", "v2": "testing"}

    assert services.apply_setting(company_id=a, setting_id=v1.id, now=NOW) == services.Applied(None, v1.id, "v1")
    assert statuses(a) == {"v1": "applied", "v2": "testing"}
    assert services.apply_setting(company_id=a, setting_id=v2.id, now=LATER) == services.Applied(v1.id, v2.id, "v2")
    assert statuses(a) == {"v1": "past", "v2": "applied"}
    assert services.apply_setting(company_id=a, setting_id=None, now=LATER) == services.Applied(v2.id, None, None)
    assert statuses(a) == {"v1": "past", "v2": "past"}
    assert selectors.ai_setting_page(company_id=a, limit=10, offset=0).applied_id is None
    assert services.apply_setting(company_id=a, setting_id=v1.id, now=LATER) == services.Applied(None, v1.id, "v1")
    assert rows(a) == [("v1", True, LATER, "", OPERATOR), ("v2", False, LATER, "", OPERATOR)]
    assert rows(b) == [("v1", False, None, "", OPERATOR)]  # 남의 회사 판은 그대로


def test_applying_the_applied_version_again_changes_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    v1 = save(a, edited())
    assert isinstance(v1, services.Created)
    services.apply_setting(company_id=a, setting_id=v1.id, now=NOW)
    assert services.apply_setting(company_id=a, setting_id=v1.id, now=LATER) == services.Unchanged()
    assert rows(a) == [("v1", True, NOW, "", OPERATOR)]  # applied_at 그대로
    assert services.apply_setting(company_id=a, setting_id=None, now=LATER) == services.Applied(v1.id, None, None)
    assert services.apply_setting(company_id=a, setting_id=None, now=LATER) == services.Unchanged()  # 기본 판 다시


def test_applying_a_missing_or_foreign_version_is_missing(companies: tuple[int, int]) -> None:
    a, b = companies
    mine = save(a, edited())
    theirs = save(b, edited())
    assert isinstance(mine, services.Created) and isinstance(theirs, services.Created)
    services.apply_setting(company_id=a, setting_id=mine.id, now=NOW)
    for wrong in (theirs.id, theirs.id + mine.id + 1000):
        assert services.apply_setting(company_id=a, setting_id=wrong, now=LATER) == selectors.SettingMissing()
    assert rows(a) == [("v1", True, NOW, "", OPERATOR)]
    assert rows(b) == [("v1", False, None, "", OPERATOR)]
    assert selectors.ai_setting_detail(company_id=a, setting_id=theirs.id) == selectors.SettingMissing()


@pytest.mark.django_db(transaction=True)
def test_two_overlapping_applies_leave_one_applied(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a, _ = companies
    v1 = save(a, edited())
    v2 = save(a, edited("지어낸 둘째 글"))
    assert isinstance(v1, services.Created) and isinstance(v2, services.Created)
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


# ── 3-2-4 DB 의 제약 ──


COLUMNS = "created_at, updated_at, company_id, name, criteria, eval_prompt_sha256, memo, created_by_user_id, applied"


def _insert(company_id: int, name: str, *, applied: bool = False, at: str = "NULL", criteria: str = "'{}'") -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO greenwash_ai_settings ({COLUMNS}, model_settings, applied_at) "
            f"VALUES (now(), now(), %s, %s, {criteria}::jsonb, %s, '', 1, %s, '{{}}'::jsonb, {at})",
            [company_id, name, "a" * 64, applied],
        )


@pytest.mark.parametrize(
    ("second", "constraint"),
    [
        pytest.param(
            {"name": "v2", "applied": True, "at": "now()"}, "greenwash_ai_settings_one_applied_uniq", id="two-applied"
        ),
        pytest.param({"name": "v1"}, "greenwash_ai_settings_company_name_uniq", id="same-name"),
    ],
)
def test_the_unique_rules_hold_in_sql(companies: tuple[int, int], second: dict[str, Any], constraint: str) -> None:
    a, b = companies
    _insert(a, "v1", applied=True, at="now()")
    _insert(b, "v1", applied=True, at="now()")  # 분모: 다른 회사는 같은 이름·적용 하나가 된다
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        _insert(a, second["name"], applied=second.get("applied", False), at=second.get("at", "NULL"))


@pytest.mark.parametrize(
    ("name", "applied", "at", "criteria", "constraint"),
    [
        pytest.param("x1", False, "NULL", "'{}'", "greenwash_ai_settings_name_check", id="name"),
        pytest.param("v0", False, "NULL", "'{}'", "greenwash_ai_settings_name_check", id="name-zero"),
        pytest.param("v1", True, "NULL", "'{}'", "greenwash_ai_settings_applied_check", id="applied-without-time"),
        pytest.param(
            "v1",
            False,
            "NULL",
            "jsonb_build_object('t', repeat('a', 32800))",
            "greenwash_ai_settings_criteria_size_check",
            id="criteria-size",
        ),
    ],
)
def test_the_checks_hold_in_sql(
    companies: tuple[int, int], name: str, applied: bool, at: str, criteria: str, constraint: str
) -> None:
    a, _ = companies
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        _insert(a, name, applied=applied, at=at, criteria=criteria)
    _insert(a, "v1", applied=True, at="now()")  # 분모: 맞는 행은 들어간다


def test_the_sha_check_holds_in_sql(companies: tuple[int, int]) -> None:
    a, _ = companies
    with (
        pytest.raises(IntegrityError, match="greenwash_ai_settings_sha_check"),
        transaction.atomic(),
        connection.cursor() as c,
    ):
        c.execute(
            f"INSERT INTO greenwash_ai_settings ({COLUMNS}, model_settings) "
            "VALUES (now(), now(), %s, 'v1', '{}'::jsonb, %s, '', 1, false, '{}'::jsonb)",
            [a, "A" * 64],
        )
