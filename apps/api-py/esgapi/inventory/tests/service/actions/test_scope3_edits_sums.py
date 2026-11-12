# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 줄 덧판이 지금 결과 셈에 닿는 자리(밴드 S3K2b-1 ② — 결정 MARC-ENT-570·559, 발주서 Q5·Q6, 이슈 549). 업무 층.

제외 → 합이 줄어듦·전부 제외 → null(시트 수·잠금 자격 그대로) · editedRows·editedRowsUnlocked · 새 done → 잠기지 않은
카테고리 0, 옛 실행 히스토리 그대로(같은 rowId) · 잠긴 카테고리는 핀 실행 제외 유지·경고 수에 안 듦 · 풀면 R 의 값 ·
대시보드 합·상위 5·share · Scope 1·2 칸 그대로 · 쿼리 수 넷 · 549(본문 한 번·쪽 호출·운영 관리자 이름).
값·이름은 지어낸 것이다.
"""

from collections.abc import Generator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from esgapi.inventory.service.actions import dashboard
from esgapi.inventory.service.actions import scope3_edits as edits
from esgapi.inventory.service.actions import scope3_state as state
from esgapi.inventory.service.utils.dashboard import share
from esgapi.inventory.service.utils.entries import Actor
from esgapi.inventory.service.utils.scope3_state import Value
from esgapi.inventory.tests.service.actions.test_scope3_state import (
    CUSTOMER,
    YEAR,
    current,
    done_body,
    of,
    plant,
    processed,
)
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.user.service.services.user import create_operator
from esgapi.user.service.utils.login import UserCreated

pytestmark = pytest.mark.django_db

WHY = "가상 사유"
ROW1, ROW2, ROW3 = "가상_C5!20", "가상_C5!21", "가상_C5!22"
OTHER = "가상_C11!20"


def body(*c5: str, c11: str = "4") -> dict[str, object]:
    return done_body(processed(5, *(c5 or ("1", "2", "3"))), processed(11, c11))


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


def year(company_id: int) -> state.YearState:
    found = state.year_state(company_id, YEAR)
    assert isinstance(found, state.YearState), found
    return found


def exclude(company_id: int, run: int, category: str, *row_ids: str) -> None:
    assert isinstance(edits.exclude(company_id, run, category, list(row_ids), WHY, CUSTOMER), edits.EditResult)


def restore(company_id: int, run: int, category: str, *row_ids: str) -> None:
    assert isinstance(edits.restore(company_id, run, category, list(row_ids), WHY, CUSTOMER), edits.EditResult)


def lock(company_id: int, run: int, category: str) -> None:
    assert isinstance(state.lock(company_id, YEAR, category, run, CUSTOMER), state.CategoryState)


def unlock(company_id: int, category: str) -> None:
    assert isinstance(state.unlock(company_id, YEAR, category, actor_kind="admin"), state.CategoryState)


@contextmanager
def queries(expected: int) -> Generator[None]:
    with CaptureQueriesContext(connection) as caught:
        yield
    assert len(caught.captured_queries) == expected, [q["sql"][:90] for q in caught.captured_queries]


# ── 합 ──


def test_an_exclusion_leaves_the_sum_and_a_restoration_brings_it_back(a: int) -> None:
    run = plant(a, body())
    assert current(year(a), "C5") == (run, Value(Decimal(6), 1, 0))
    exclude(a, run, "C5", ROW1, ROW3)
    found = year(a)
    assert current(found, "C5") == (run, Value(Decimal(2), 1, 0))
    assert current(found, "C11") == (run, Value(Decimal(4), 1, 0))
    restore(a, run, "C5", ROW1)
    assert current(year(a), "C5") == (run, Value(Decimal(3), 1, 0))


def test_excluding_every_row_gives_null_and_keeps_the_sheet_and_the_right_to_lock(a: int) -> None:
    run = plant(a, body())
    exclude(a, run, "C5", ROW1, ROW2, ROW3)
    assert current(year(a), "C5") == (run, Value(None, 1, 0))
    lock(a, run, "C5")  # 시트 단위 자격 그대로
    assert of(year(a), "C5").locked_at is not None


def test_the_answer_of_an_exclusion_carries_the_new_sum_and_count(a: int) -> None:
    run = plant(a, body())
    found = edits.exclude(a, run, "C5", [ROW1], WHY, CUSTOMER)
    assert isinstance(found, edits.EditResult)
    line = found.category
    assert line.current is not None and line.current.value.total == Decimal(5)
    assert line.edited_rows == 1


# ── 570 ──


def test_edited_rows_count_per_category_and_the_unlocked_sum(a: int) -> None:
    run = plant(a, body())
    assert year(a).edited_rows_unlocked == 0
    exclude(a, run, "C5", ROW1, ROW2)
    exclude(a, run, "C11", OTHER)
    found = year(a)
    assert (of(found, "C5").edited_rows, of(found, "C11").edited_rows, of(found, "C1").edited_rows) == (2, 1, 0)
    assert found.edited_rows_unlocked == 3
    restore(a, run, "C5", ROW1)
    found = year(a)
    assert (of(found, "C5").edited_rows, found.edited_rows_unlocked) == (1, 2)  # 제외 뒤 복구 = 0


def test_a_new_done_drops_the_unlocked_edits_and_the_old_history_stays(a: int) -> None:
    old = plant(a, body())
    exclude(a, old, "C5", ROW1)
    new = plant(a, body())  # 같은 시트·엑셀 줄 — 같은 rowId
    found = year(a)
    assert current(found, "C5") == (new, Value(Decimal(6), 1, 0))  # 옮겨 붙지 않는다
    assert (of(found, "C5").edited_rows, found.edited_rows_unlocked) == (0, 0)
    lines = edits.history(a, old, None, offset=0, limit=20)
    assert isinstance(lines, edits.HistoryPage)
    assert [(line.row_id, line.kind) for line in lines.lines] == [(ROW1, "exclude")]
    assert edits.edits(a, new) == edits.Edits(run_id=new, rows=())


def test_a_locked_category_keeps_its_pinned_exclusions_outside_the_warning(a: int) -> None:
    first = plant(a, body())
    exclude(a, first, "C5", ROW1)
    exclude(a, first, "C11", OTHER)
    lock(a, first, "C5")
    found = year(a)
    assert (of(found, "C5").edited_rows, of(found, "C11").edited_rows) == (1, 1)
    assert found.edited_rows_unlocked == 1  # 잠긴 C5 는 핀이 지킨다
    second = plant(a, body("10", "20", "30", c11="40"))
    found = year(a)
    assert current(found, "C5") == (first, Value(Decimal(5), 1, 0))  # 핀 실행의 제외 그대로
    assert of(found, "C5").edited_rows == 1
    assert current(found, "C11") == (second, Value(Decimal(40), 1, 0))
    assert (of(found, "C11").edited_rows, found.edited_rows_unlocked) == (0, 0)
    unlock(a, "C5")
    found = year(a)
    assert current(found, "C5") == (second, Value(Decimal(60), 1, 0))  # 풀면 R 의 값
    assert of(found, "C5").edited_rows == 0


# ── 대시보드 ──


def test_the_dashboard_sums_as_the_year_state_does(a: int) -> None:
    run = plant(a, body("1", "2", "3", c11="4"))
    before = dashboard.board(a, YEAR)
    assert before.scope3 == Decimal(10)
    assert [(line.category, line.value) for line in before.categories] == [("C5", Decimal(6)), ("C11", Decimal(4))]
    exclude(a, run, "C5", ROW2, ROW3)
    after = dashboard.board(a, YEAR)
    assert (after.scope3, after.total) == (Decimal(5), Decimal(5))
    assert [(line.category, line.value) for line in after.categories] == [("C11", Decimal(4)), ("C5", Decimal(1))]
    assert [line.share for line in after.categories] == [share(Decimal(4), Decimal(5)), share(Decimal(1), Decimal(5))]
    assert after.scope12 == before.scope12
    totals = [line.current.value.total for line in year(a).categories if line.current is not None]
    assert after.scope3 == sum(total for total in totals if total is not None)


def test_a_fully_excluded_category_leaves_the_top_list(a: int) -> None:
    run = plant(a, body())
    exclude(a, run, "C5", ROW1, ROW2, ROW3)
    assert [line.category for line in dashboard.board(a, YEAR).categories] == ["C11"]


def test_a_pinned_exclusion_reaches_the_dashboard(a: int) -> None:
    first = plant(a, body())
    exclude(a, first, "C5", ROW1)
    lock(a, first, "C5")
    plant(a, body("10", "20", "30", c11="40"))
    assert dashboard.board(a, YEAR).scope3 == Decimal(45)


# ── 쿼리 수(BASE 값 + events_of 1 − 549 로 걷은 수 — C0-4) ──


def test_the_year_state_reads_the_events_once(a: int) -> None:
    plant(a, body())
    with queries(5):  # BASE 4 + events_of 1
        year(a)


def test_the_dashboard_reads_no_names(a: int) -> None:
    run = plant(a, body())
    lock(a, run, "C5")
    with queries(7):  # BASE 9 + events_of 1 − 이름 2(549 ②) − 핀 = R 본문 1(549 ⑥)
        dashboard.board(a, YEAR)


def test_the_lock_answer_picks_the_base_once(a: int) -> None:
    run = plant(a, body())
    with queries(17):  # BASE 21 + events_of 1 − _base 3(549 ①) − 핀 = R 본문 1(549 ⑥) − 이름 1(549 ③)
        lock(a, run, "C5")


@pytest.mark.parametrize("rows", [(ROW1,), (ROW1, ROW2, ROW3)], ids=["one", "three"])
def test_the_exclusion_answer_does_not_grow_with_rows(a: int, rows: tuple[str, ...]) -> None:
    """561 L1·L4: 사건은 쓰기 전 한 번만 읽고 쓴 것을 합친다 — 줄 수와 상관없다(bulk_create 한 번, 7a 허락)."""
    run = plant(a, body())
    with queries(17):  # BASE 19 − events_of 2(561 L4)
        exclude(a, run, "C5", *rows)


# ── 549 ──


def spy(monkeypatch: pytest.MonkeyPatch, name: str) -> list[Any]:
    calls: list[Any] = []
    real = getattr(run_selectors, name)

    def wrapped(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(run_selectors, name, wrapped)
    return calls


def test_lock_picks_the_base_only_once(a: int, monkeypatch: pytest.MonkeyPatch) -> None:
    run = plant(a, body())
    calls = spy(monkeypatch, "run_page")
    lock(a, run, "C5")
    assert len(calls) == 1


def test_a_pin_on_the_base_run_reads_its_body_once(a: int, monkeypatch: pytest.MonkeyPatch) -> None:
    run = plant(a, body())
    lock(a, run, "C5")
    calls = spy(monkeypatch, "results_of")
    year(a)
    assert [call["run_ids"] for call in calls] == [[run]]


def test_a_pin_on_an_older_run_reads_each_body_once(a: int, monkeypatch: pytest.MonkeyPatch) -> None:
    first = plant(a, body())
    lock(a, first, "C5")
    second = plant(a, body())
    calls = spy(monkeypatch, "results_of")
    lock(a, first, "C5")  # 멱등 — 판정에 읽은 핀 본문을 응답에 다시 쓴다
    assert sorted(call["run_ids"][0] for call in calls) == [first, second]


@pytest.mark.parametrize(("runs", "pages"), [(200, 1), (201, 2)], ids=["exactly-a-page", "one-more"])
def test_no_empty_page_is_asked(a: int, monkeypatch: pytest.MonkeyPatch, runs: int, pages: int) -> None:
    for _ in range(runs):
        plant(a, status="failed")
    calls = spy(monkeypatch, "run_page")
    year(a)
    assert len(calls) == pages


def test_an_operators_lock_shows_the_operators_name(a: int) -> None:
    made = create_operator(username="ops-s3", name="가상 운영자", password="가상-비밀-글자-12345")
    assert isinstance(made, UserCreated)
    run = plant(a, body())
    assert isinstance(state.lock(a, YEAR, "C5", run, Actor("admin", made.user_id)), state.CategoryState)
    assert of(year(a), "C5").locked_by == (made.user_id, "가상 운영자")
