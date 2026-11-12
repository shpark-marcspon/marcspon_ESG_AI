# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 연도 상태·카테고리 잠금의 몸(밴드 S3K2a ① — service/actions/scope3_state.py). 업무 층.

실행 0 · R 하나(Q11 갈래) · 새 done → 잠기지 않은 카테고리 **전부** 새 실행(559) · failed·rejected·진행 중·
purpose test·다른 해·다른 흐름·남의 회사 → R 그대로 · 이어 돌기 실행이 만든 차례대로 R · 잠금: 두 역할·runId 다름
stale·failed 만/empty not_computed·남의 회사 runId 404·멱등(핀 그대로)·잠근 뒤 새 done → 잠긴 것만 핀·풀면 R ·
풀기는 운영 관리자만 · 해 범위.
실행 행은 심는다(실행기 0 — 결과 본문 꼴은 scope3.colab.result@1, 줄 칸은 셈에 쓰는 것만). 값·이름은 지어낸 것이다.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import count
from typing import Any

import pytest
from django.apps import apps

from esgapi.inventory.flows.binding_157 import FLOW_ID, MODULE
from esgapi.inventory.flows.scope3_colab_157 import RESULT_SHAPE
from esgapi.inventory.models import Scope3CategoryState
from esgapi.inventory.service.actions import scope3_state as actions
from esgapi.inventory.service.utils.entries import Actor
from esgapi.inventory.service.utils.ghg_pool import Forbidden, Invalid, NotFound
from esgapi.inventory.service.utils.scope3_state import CATEGORIES, Value

pytestmark = pytest.mark.django_db

YEAR = 2025
CUSTOMER = Actor("service", 41)
OPERATOR = Actor("admin", 42)
_CLOCK = count()
T0 = datetime(2026, 3, 1, tzinfo=UTC)


def processed(n: int, *co2e: str | None) -> dict[str, object]:
    return {
        "sheet": f"가상_C{n}",
        "category": f"Category{n}",
        "status": "processed",
        "rows": [{"rowId": f"가상_C{n}!{20 + i}", "co2e": value} for i, value in enumerate(co2e)],
    }


def failed(n: int) -> dict[str, object]:
    return {"sheet": f"가상_C{n}", "category": f"Category{n}", "status": "failed", "error": "가상 실패"}


def empty(n: int) -> dict[str, object]:
    return {"sheet": f"가상_C{n}", "category": f"Category{n}", "status": "empty"}


def done_body(*sheets: dict[str, object]) -> dict[str, object]:
    return {"schemaVersion": RESULT_SHAPE, "status": "done", "reportYear": YEAR, "sheets": list(sheets), "llmCalls": {}}


REJECTED: dict[str, object] = {
    "schemaVersion": RESULT_SHAPE,
    "status": "rejected",
    "rejected": {"reason": "reader_problem", "detail": "가상"},
}


def runs_model(name: str) -> Any:
    return apps.get_model("runs", name)


def plant(
    company_id: int,
    body: dict[str, object] | None = None,
    *,
    status: str = "done",
    year: object = YEAR,
    flow: str = FLOW_ID,
    purpose: str = "service",
    resumed_from: int | None = None,
) -> int:
    """심은 Scope 3 실행 하나(만든 때는 부를 때마다 1분씩 뒤 — 만든 차례가 부른 차례). body 가 있으면 결과 행 하나."""
    at = T0 + timedelta(minutes=next(_CLOCK))
    runs = runs_model("RunRow").for_company(company_id)
    made = runs.create(
        company_id=company_id,
        module=MODULE,
        flow_id=flow,
        options={"reportYear": year},
        versions={},
        status=status,
        purpose=purpose,
        created_by_user_id=CUSTOMER.user_id,
        started_at=at,
        finished_at=at if status in ("done", "failed") else None,
        resumed_from_run_id=resumed_from,
    )
    runs.filter(pk=made.pk).update(created_at=at)
    if body is not None:
        runs_model("RunResultRow").for_company(company_id).create(
            company_id=company_id, run_id=made.pk, position=0, schema_version=RESULT_SHAPE, body=body
        )
    return int(made.pk)


def state(company_id: int, year: int = YEAR) -> actions.YearState:
    found = actions.year_state(company_id, year)
    assert isinstance(found, actions.YearState), found
    return found


def of(found: actions.YearState, category: str) -> actions.CategoryState:
    (only,) = [line for line in found.categories if line.category == category]
    return only


def current(found: actions.YearState, category: str) -> tuple[int, Value] | None:
    line = of(found, category).current
    return None if line is None else (line.run_id, line.value)


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


@pytest.fixture
def b(companies: tuple[int, int]) -> int:
    return companies[1]


# ── 연도 상태 ──


def test_no_runs_gives_fourteen_empty_categories(a: int) -> None:
    found = state(a)
    assert (found.year, found.base_run_id, found.latest) == (YEAR, None, None)
    assert [line.category for line in found.categories] == list(CATEGORIES)
    assert all(line.current is None and line.locked_at is None for line in found.categories)
    assert Scope3CategoryState.for_company(a).count() == 0  # GET 은 행을 만들지 않는다


def test_one_base_run_gives_every_q11_branch(a: int) -> None:
    run = plant(a, done_body(processed(4, "1.5", "2.5"), failed(4), failed(5), empty(6), processed(8, None)))
    found = state(a)
    assert (found.base_run_id, found.latest) == (run, (run, "done"))
    assert current(found, "C4") == (run, Value(Decimal(4), 1, 1))
    assert current(found, "C5") == (run, Value(None, 0, 1))
    assert current(found, "C6") == (run, Value(None, 0, 0))
    assert current(found, "C9") == (run, Value(None, 0, 0))
    assert current(found, "C8") == (run, Value(None, 1, 0))


def test_a_new_done_run_replaces_every_unlocked_category(a: int) -> None:
    """559: 다시 올리면 전부 다시 셈 — 새 실행이 C4 를 안 셌어도(시트 없음) C4 의 지금 결과는 새 실행 것."""
    first = plant(a, done_body(processed(4, "1"), processed(5, "2")))
    second = plant(a, done_body(processed(5, "7")))
    found = state(a)
    assert found.base_run_id == second
    assert current(found, "C4") == (second, Value(None, 0, 0))
    assert current(found, "C5") == (second, Value(Decimal(7), 1, 0))
    assert first != second


@pytest.mark.parametrize(
    ("later", "is_latest"),
    [
        ({"status": "failed"}, True),
        ({"status": "queued"}, True),
        ({"status": "processing"}, True),
        ({"body": REJECTED}, True),
        ({"purpose": "test"}, False),
        ({"year": YEAR - 1}, False),
        ({"year": True}, False),
        ({"flow": "scope3.llm-first@1"}, False),
    ],
    ids=["failed", "queued", "processing", "rejected", "purpose-test", "other-year", "bool-year", "other-flow"],
)
def test_a_later_run_that_does_not_count_keeps_the_base(a: int, later: dict[str, Any], is_latest: bool) -> None:
    base = plant(a, done_body(processed(4, "1")))
    body = later.pop("body", None)
    newer = plant(a, body, **later)
    found = state(a)
    assert found.base_run_id == base
    assert current(found, "C4") == (base, Value(Decimal(1), 1, 0))
    assert found.latest == ((newer, later.get("status", "done")) if is_latest else (base, "done"))


def test_another_companys_run_never_shows(a: int, b: int) -> None:
    mine = plant(a, done_body(processed(4, "1")))
    plant(b, done_body(processed(4, "99")))
    found = state(a)
    assert (found.base_run_id, current(found, "C4")) == (mine, (mine, Value(Decimal(1), 1, 0)))


def test_a_resumed_run_counts_in_creation_order(a: int) -> None:
    """이어 돌기 실행(resumed_from_run_id)도 새 행 — 만든 차례대로 R. 끝난 차례(finished_at)가 아니다."""
    broken = plant(a, status="failed")
    older_done = plant(a, done_body(processed(4, "1")))  # 이어 돌기보다 먼저 만듦
    resumed = plant(a, done_body(processed(4, "5")), resumed_from=broken)
    assert state(a).base_run_id == resumed
    # 만든 차례: 더 늦게 만든 실행이 먼저 끝났어도(finished_at 이 앞) 만든 차례가 이긴다
    runs = runs_model("RunRow").for_company(a)
    runs.filter(pk=resumed).update(finished_at=T0 - timedelta(days=1))
    assert state(a).base_run_id == resumed
    assert older_done < resumed


def test_the_year_is_1990_to_2100(a: int) -> None:
    assert isinstance(actions.year_state(a, 1989), Invalid)
    assert isinstance(actions.year_state(a, 2101), Invalid)
    assert isinstance(actions.year_state(a, 1990), actions.YearState)


# ── 잠금 ──


def test_lock_pins_the_current_run_for_both_roles(a: int) -> None:
    run = plant(a, done_body(processed(4, "1"), processed(5, "2")))
    first = actions.lock(a, YEAR, "C4", run, CUSTOMER)
    assert isinstance(first, actions.CategoryState)
    assert first.current == actions.Current(run, Value(Decimal(1), 1, 0))
    assert first.locked_at is not None and first.locked_by == (CUSTOMER.user_id, "")
    second = actions.lock(a, YEAR, "C5", run, OPERATOR)  # 운영 관리자 대행
    assert isinstance(second, actions.CategoryState) and second.locked_by == (OPERATOR.user_id, "")
    rows = {row.category: row.pinned_run_id for row in Scope3CategoryState.for_company(a)}
    assert rows == {"C4": run, "C5": run}


def test_lock_is_idempotent_and_keeps_the_pin(a: int) -> None:
    run = plant(a, done_body(processed(4, "1")))
    first = actions.lock(a, YEAR, "C4", run, CUSTOMER)
    again = actions.lock(a, YEAR, "C4", run, OPERATOR)
    assert isinstance(first, actions.CategoryState) and isinstance(again, actions.CategoryState)
    assert (again.locked_at, again.locked_by) == (first.locked_at, first.locked_by)
    assert Scope3CategoryState.for_company(a).count() == 1


def test_a_new_done_after_locking_changes_only_the_unlocked(a: int) -> None:
    first = plant(a, done_body(processed(4, "1"), processed(5, "2")))
    assert isinstance(actions.lock(a, YEAR, "C4", first, CUSTOMER), actions.CategoryState)
    second = plant(a, done_body(processed(4, "10"), processed(5, "20")))
    found = state(a)
    assert found.base_run_id == second
    assert current(found, "C4") == (first, Value(Decimal(1), 1, 0))  # 핀
    assert current(found, "C5") == (second, Value(Decimal(20), 1, 0))
    # 잠긴 C4 에 지금 결과 runId(핀)로 다시 걸면 멱등, 새 실행 id 로 걸면 stale
    assert isinstance(actions.lock(a, YEAR, "C4", first, CUSTOMER), actions.CategoryState)
    assert isinstance(actions.lock(a, YEAR, "C4", second, CUSTOMER), actions.StaleRun)
    # 풀면 R 로
    opened = actions.unlock(a, YEAR, "C4", actor_kind="admin")
    assert isinstance(opened, actions.CategoryState)
    assert opened.current == actions.Current(second, Value(Decimal(10), 1, 0))
    assert (opened.locked_at, opened.locked_by) == (None, None)
    assert Scope3CategoryState.for_company(a).get().pinned_run_id is None  # 행은 남고 칸만 빔


def test_a_stale_run_id_is_409_and_writes_nothing(a: int) -> None:
    old = plant(a, done_body(processed(4, "1")))
    plant(a, done_body(processed(4, "2")))
    assert isinstance(actions.lock(a, YEAR, "C4", old, CUSTOMER), actions.StaleRun)
    assert Scope3CategoryState.for_company(a).count() == 0  # 거절이면 빈 행도 되돌린다


@pytest.mark.parametrize("sheets", [[failed(4)], [empty(4)], []], ids=["failed-only", "empty", "no-sheet"])
def test_nothing_computed_is_409(a: int, sheets: list[dict[str, object]]) -> None:
    run = plant(a, done_body(processed(5, "1"), *sheets))
    assert isinstance(actions.lock(a, YEAR, "C4", run, CUSTOMER), actions.NotComputed)
    assert Scope3CategoryState.for_company(a).count() == 0


def test_no_base_run_is_not_computed(a: int) -> None:
    run = plant(a, status="failed")
    assert isinstance(actions.lock(a, YEAR, "C4", run, CUSTOMER), actions.NotComputed)


def test_a_run_id_of_another_company_or_none_is_404(a: int, b: int) -> None:
    plant(a, done_body(processed(4, "1")))
    theirs = plant(b, done_body(processed(4, "1")))
    assert isinstance(actions.lock(a, YEAR, "C4", theirs, CUSTOMER), actions.RunNotFound)
    assert isinstance(actions.lock(a, YEAR, "C4", 9_000_000, CUSTOMER), actions.RunNotFound)
    assert (Scope3CategoryState.for_company(a).count(), Scope3CategoryState.for_company(b).count()) == (0, 0)


def test_an_unknown_category_and_year_are_refused(a: int) -> None:
    run = plant(a, done_body(processed(4, "1")))
    assert isinstance(actions.lock(a, YEAR, "C10", run, CUSTOMER), NotFound)
    assert isinstance(actions.lock(a, YEAR, "c4", run, CUSTOMER), NotFound)
    assert isinstance(actions.lock(a, 1989, "C4", run, CUSTOMER), Invalid)
    assert isinstance(actions.unlock(a, YEAR, "C16", actor_kind="admin"), NotFound)
    assert Scope3CategoryState.for_company(a).count() == 0


def test_only_the_operator_unlocks(a: int) -> None:
    run = plant(a, done_body(processed(4, "1")))
    assert isinstance(actions.lock(a, YEAR, "C4", run, CUSTOMER), actions.CategoryState)
    assert isinstance(actions.unlock(a, YEAR, "C4", actor_kind="service"), Forbidden)
    assert Scope3CategoryState.for_company(a).get().locked_at is not None
    assert isinstance(actions.unlock(a, YEAR, "C4", actor_kind="admin"), actions.CategoryState)
    # 안 잠겼어도 200 꼴(행 없음도)
    assert isinstance(actions.unlock(a, YEAR, "C4", actor_kind="admin"), actions.CategoryState)
    assert isinstance(actions.unlock(a, YEAR, "C9", actor_kind="admin"), actions.CategoryState)
    assert Scope3CategoryState.for_company(a).count() == 1


def test_a_lock_in_one_year_does_not_touch_another(a: int) -> None:
    run = plant(a, done_body(processed(4, "1")))
    other = plant(a, done_body(processed(4, "3")), year=YEAR - 1)
    assert isinstance(actions.lock(a, YEAR, "C4", run, CUSTOMER), actions.CategoryState)
    found = state(a, YEAR - 1)
    assert of(found, "C4").locked_at is None
    assert current(found, "C4") == (other, Value(Decimal(3), 1, 0))
