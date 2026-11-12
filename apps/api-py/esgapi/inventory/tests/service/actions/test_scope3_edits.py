# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 줄 덧판의 몸(밴드 S3K2b-1 ① — service/actions/scope3_edits.py). 업무 층.

제외·복구 → 사건·지금 상태·히스토리 · 같은 상태 다시 = 사건 0 · 섞인 요청 · 몸 422 · 잠김 409 locked(사건 0) · 옛 실행
409 stale_run(사건 0) · 다른 해·다른 흐름·해 꼴 아님 stale_run · 거절 때 상태 행 0 · 남의 회사·없는 실행·다른 모듈
NotFound · 두 역할 · 히스토리 쪽 넘김·rowId 거름·새 것 먼저 · 한 요청 = 한 batch_id.
실행 행은 심는다(실행기 0). 값·이름은 지어낸 것이다.
"""

from collections.abc import Callable
from typing import Any

import pytest

from esgapi.inventory.models import Scope3CategoryState, Scope3RowEdit
from esgapi.inventory.service.actions import scope3_edits as actions
from esgapi.inventory.service.actions import scope3_state
from esgapi.inventory.service.actions.scope3_state import StaleRun
from esgapi.inventory.service.utils.entries import Actor, Locked
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound
from esgapi.inventory.service.utils.scope3_edits import ROW_IDS_UNKNOWN
from esgapi.inventory.tests.service.actions.test_scope3_state import (
    CUSTOMER,
    OPERATOR,
    YEAR,
    done_body,
    failed,
    plant,
    processed,
    runs_model,
)

pytestmark = pytest.mark.django_db

WHY = "가상 사유"
ROW1, ROW2, ROW3 = "가상_C5!20", "가상_C5!21", "가상_C5!22"
OTHER = "가상_C11!20"


def body() -> dict[str, object]:
    return done_body(processed(5, "1", "2", "3"), processed(11, "4"), failed(6))


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


@pytest.fixture
def b(companies: tuple[int, int]) -> int:
    return companies[1]


def events(company_id: int) -> list[tuple[int, str, str, str]]:
    rows = Scope3RowEdit.for_company(company_id).order_by("id")
    return list(rows.values_list("run_id", "category", "row_id", "kind"))


def states(company_id: int) -> int:
    return Scope3CategoryState.for_company(company_id).count()


def done(found: object) -> actions.EditResult:
    assert isinstance(found, actions.EditResult), found
    return found


def now(company_id: int, run_id: int) -> dict[str, bool]:
    found = actions.edits(company_id, run_id)
    assert isinstance(found, actions.Edits), found
    return {row.row_id: row.excluded for row in found.rows}


def page(
    company_id: int, run_id: int, row_id: str | None = None, offset: int = 0, limit: int = 20
) -> actions.HistoryPage:
    found = actions.history(company_id, run_id, row_id, offset=offset, limit=limit)
    assert isinstance(found, actions.HistoryPage), found
    return found


# ── 쓰기 ──


def test_exclude_then_restore_leaves_events_state_and_history(a: int) -> None:
    run = plant(a, body())
    found = done(actions.exclude(a, run, "C5", [ROW1, ROW2], f"  {WHY} ", CUSTOMER))
    assert [(row.row_id, row.category, row.excluded) for row in found.rows] == [(ROW1, "C5", True), (ROW2, "C5", True)]
    assert found.category.category == "C5"
    assert events(a) == [(run, "C5", ROW1, "exclude"), (run, "C5", ROW2, "exclude")]
    assert set(Scope3RowEdit.for_company(a).values_list("reason", "actor_kind", "actor_user_id")) == {
        (WHY, "service", CUSTOMER.user_id)
    }
    assert now(a, run) == {ROW1: True, ROW2: True}

    done(actions.restore(a, run, "C5", [ROW1], "가상 복구", OPERATOR))
    assert now(a, run) == {ROW1: False, ROW2: True}
    lines = page(a, run)
    assert lines.count == 3
    assert [(line.row_id, line.kind, line.reason) for line in lines.lines] == [
        (ROW1, "restore", "가상 복구"),
        (ROW2, "exclude", WHY),
        (ROW1, "exclude", WHY),
    ]
    assert Scope3RowEdit.for_company(a).filter(kind="restore").get().actor_kind == "admin"


def test_the_same_state_again_makes_no_event_and_answers_200(a: int) -> None:
    run = plant(a, body())
    done(actions.exclude(a, run, "C5", [ROW1], WHY, CUSTOMER))
    again = done(actions.exclude(a, run, "C5", [ROW1], "다른 가상 사유", CUSTOMER))
    assert [row.excluded for row in again.rows] == [True]
    assert len(events(a)) == 1
    done(actions.restore(a, run, "C5", [ROW1], WHY, CUSTOMER))
    done(actions.restore(a, run, "C5", [ROW1], WHY, CUSTOMER))
    assert len(events(a)) == 2


def test_restoring_a_row_never_edited_makes_no_event(a: int) -> None:
    run = plant(a, body())
    found = done(actions.restore(a, run, "C5", [ROW1], WHY, CUSTOMER))
    assert found.rows == ()  # 사건이 있는 줄만 — 원안 그대로인 줄은 editedAt 이 없다
    assert events(a) == []


def test_a_mixed_request_writes_only_the_rows_that_change(a: int) -> None:
    run = plant(a, body())
    done(actions.exclude(a, run, "C5", [ROW1], WHY, CUSTOMER))
    found = done(actions.exclude(a, run, "C5", [ROW1, ROW2], WHY, CUSTOMER))
    assert [(row.row_id, row.excluded) for row in found.rows] == [(ROW1, True), (ROW2, True)]
    assert events(a) == [(run, "C5", ROW1, "exclude"), (run, "C5", ROW2, "exclude")]


def test_one_request_is_one_batch_and_two_requests_are_two(a: int) -> None:
    run = plant(a, body())
    done(actions.exclude(a, run, "C5", [ROW1, ROW2], WHY, CUSTOMER))
    done(actions.exclude(a, run, "C5", [ROW3], WHY, CUSTOMER))
    batches = [line.batch_id for line in reversed(page(a, run).lines)]
    assert batches[0] is not None and batches[0] == batches[1]
    assert batches[2] is not None and batches[2] != batches[0]


@pytest.mark.parametrize(
    ("row_ids", "reason", "field"),
    [
        ([], WHY, "rowIds"),
        ([ROW1, ROW1], WHY, "rowIds"),
        ([ROW1], "", "reason"),
        ([ROW1], "   ", "reason"),
        ([ROW1], "가" * 301, "reason"),
    ],
    ids=["no-rows", "repeated", "empty", "blank", "long"],
)
def test_a_bad_body_is_422_and_writes_nothing(a: int, row_ids: list[str], reason: str, field: str) -> None:
    run = plant(a, body())
    found = actions.exclude(a, run, "C5", row_ids, reason, CUSTOMER)
    assert isinstance(found, Invalid) and field in found.fields
    assert (events(a), states(a)) == ([], 0)


def test_the_body_goes_before_the_category_and_the_run(a: int) -> None:
    assert isinstance(actions.exclude(a, 999_999, "C10", [], WHY, CUSTOMER), Invalid)


@pytest.mark.parametrize("wrong", [OTHER, "가상_C5!99", ""], ids=["other-category", "unknown", "empty"])
def test_a_row_of_another_category_is_422_and_leaves_no_state_row(a: int, wrong: str) -> None:
    run = plant(a, body())
    found = actions.exclude(a, run, "C5", [ROW1, wrong], WHY, CUSTOMER)
    assert found == Invalid({"rowIds": ROW_IDS_UNKNOWN})
    assert (events(a), states(a)) == ([], 0)  # ④ 가 둔 빈 상태 행도 되돌림


def test_a_failed_sheet_has_no_rows_to_edit(a: int) -> None:
    run = plant(a, body())
    assert isinstance(actions.exclude(a, run, "C6", ["가상_C6!20"], WHY, CUSTOMER), Invalid)
    assert (events(a), states(a)) == ([], 0)


@pytest.mark.parametrize("edit", [actions.exclude, actions.restore], ids=["exclude", "restore"])
def test_a_locked_category_is_409_and_keeps_the_state_row(a: int, edit: Callable[..., object]) -> None:
    run = plant(a, body())
    assert isinstance(scope3_state.lock(a, YEAR, "C5", run, CUSTOMER), scope3_state.CategoryState)
    before = list(Scope3CategoryState.for_company(a).values_list("id", "locked_at", "pinned_run_id"))
    found = edit(a, run, "C5", [ROW1], WHY, CUSTOMER)
    assert isinstance(found, Locked)  # 잠근 실행 자신이어도
    assert events(a) == []
    assert list(Scope3CategoryState.for_company(a).values_list("id", "locked_at", "pinned_run_id")) == before


def test_another_category_of_the_same_run_stays_open_while_one_is_locked(a: int) -> None:
    run = plant(a, body())
    scope3_state.lock(a, YEAR, "C5", run, CUSTOMER)
    done(actions.exclude(a, run, "C11", [OTHER], WHY, CUSTOMER))
    assert events(a) == [(run, "C11", OTHER, "exclude")]


def test_an_old_run_is_409_stale_and_writes_nothing(a: int) -> None:
    old = plant(a, body())
    plant(a, body())  # 새 done
    assert isinstance(actions.exclude(a, old, "C5", [ROW1], WHY, CUSTOMER), StaleRun)
    assert (events(a), states(a)) == ([], 0)


def test_a_run_replaced_in_its_own_year_is_stale_and_the_current_of_another_year_is_open(a: int) -> None:
    """해는 실행의 options.reportYear 다 — 다른 해의 실행은 그 해에서 지금 결과면 고친다, 밀렸으면 stale."""
    older = plant(a, body(), year=YEAR - 1)
    newer = plant(a, body(), year=YEAR - 1)
    plant(a, body())
    assert isinstance(actions.exclude(a, older, "C5", [ROW1], WHY, CUSTOMER), StaleRun)
    done(actions.exclude(a, newer, "C5", [ROW1], WHY, CUSTOMER))
    assert events(a) == [(newer, "C5", ROW1, "exclude")]


@pytest.mark.parametrize(
    "made",
    [
        {"flow": "scope3.llm-first@1"},
        {"purpose": "test"},
        {"status": "failed"},
        {"status": "processing"},
        {"year": True},
        {"year": "2025"},
        {"year": 1989},
        {"year": 2101},
    ],
    ids=["other-flow", "purpose-test", "failed", "processing", "bool-year", "text-year", "too-early", "too-late"],
)
def test_a_run_that_cannot_be_current_is_stale(a: int, made: dict[str, Any]) -> None:
    plant(a, body())
    run = plant(a, body(), **made)
    assert isinstance(actions.exclude(a, run, "C5", [ROW1], WHY, CUSTOMER), StaleRun)
    assert (events(a), states(a)) == ([], 0)


def test_no_current_result_is_stale(a: int) -> None:
    run = plant(a, done_body(), status="failed")
    assert isinstance(actions.exclude(a, run, "C5", [ROW1], WHY, CUSTOMER), StaleRun)
    assert states(a) == 0


@pytest.mark.parametrize("category", ["C10", "C16", "c5", ""], ids=["c10", "c16", "lower", "empty"])
def test_an_unknown_category_is_not_found(a: int, category: str) -> None:
    run = plant(a, body())
    assert isinstance(actions.exclude(a, run, category, [ROW1], WHY, CUSTOMER), NotFound)


def test_another_company_missing_and_other_module_runs_are_not_found(a: int, b: int) -> None:
    theirs = plant(b, body())
    other_module = plant(a, body())
    runs_model("RunRow").for_company(a).filter(pk=other_module).update(module="greenwash")
    for run in (theirs, theirs + 1_000_000, other_module):
        assert isinstance(actions.exclude(a, run, "C5", [ROW1], WHY, CUSTOMER), NotFound)
        assert isinstance(actions.restore(a, run, "C5", [ROW1], WHY, CUSTOMER), NotFound)
        assert isinstance(actions.edits(a, run), NotFound)
        assert isinstance(actions.history(a, run, None, offset=0, limit=20), NotFound)
    assert (events(a), events(b), states(a), states(b)) == ([], [], 0, 0)


def test_the_operator_acts_on_the_working_company(a: int) -> None:
    run = plant(a, body())
    done(actions.exclude(a, run, "C5", [ROW1], WHY, Actor("admin", 42)))
    assert Scope3RowEdit.for_company(a).get().actor_user_id == 42


# ── 읽기 ──


def test_the_state_is_per_row_in_row_id_order_with_edited_rows_only(a: int) -> None:
    run = plant(a, body())
    done(actions.exclude(a, run, "C5", [ROW2, ROW1], WHY, CUSTOMER))
    found = actions.edits(a, run)
    assert isinstance(found, actions.Edits)
    assert found.run_id == run
    assert [row.row_id for row in found.rows] == [ROW1, ROW2]
    assert actions.edits(a, plant(a, body())) == actions.Edits(run_id=found.run_id + 1, rows=())


def test_an_unknown_person_reads_as_none(a: int) -> None:
    run = plant(a, body())
    done(actions.exclude(a, run, "C5", [ROW1], WHY, Actor("service", 987_654)))
    found = actions.edits(a, run)
    assert isinstance(found, actions.Edits)
    assert found.rows[0].by is None
    assert page(a, run).lines[0].by is None


def test_history_pages_filters_and_goes_newest_first(a: int) -> None:
    run = plant(a, body())
    for reason in ("가상 하나", "가상 둘"):
        done(actions.exclude(a, run, "C5", [ROW1], reason, CUSTOMER))
        done(actions.restore(a, run, "C5", [ROW1], reason, CUSTOMER))
    done(actions.exclude(a, run, "C5", [ROW2], "가상 셋", CUSTOMER))
    whole = page(a, run)
    assert whole.count == 5
    ids = [line.id for line in whole.lines]
    assert ids == sorted(ids, reverse=True)
    assert whole.lines[0].row_id == ROW2
    first, second = page(a, run, limit=2), page(a, run, offset=2, limit=2)
    assert (first.count, second.count) == (5, 5)
    assert [line.id for line in (*first.lines, *second.lines)] == ids[:4]
    only = page(a, run, ROW1)
    assert only.count == 4 and {line.row_id for line in only.lines} == {ROW1}
    assert page(a, run, "없는 줄").count == 0
    assert page(a, run, offset=100).lines == ()


def test_history_stays_on_its_run(a: int) -> None:
    old = plant(a, body())
    done(actions.exclude(a, old, "C5", [ROW1], WHY, CUSTOMER))
    new = plant(a, body())
    done(actions.exclude(a, new, "C5", [ROW2], WHY, CUSTOMER))
    assert [line.row_id for line in page(a, old).lines] == [ROW1]
    assert [line.row_id for line in page(a, new).lines] == [ROW2]
    assert now(a, old) == {ROW1: True}
    assert now(a, new) == {ROW2: True}


def test_the_result_body_stays_the_original(a: int) -> None:
    original = body()
    run = plant(a, original)
    done(actions.exclude(a, run, "C5", [ROW1], WHY, CUSTOMER))
    (row,) = runs_model("RunResultRow").for_company(a).filter(run_id=run)
    assert row.body == original
