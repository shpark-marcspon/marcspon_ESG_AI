# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""계수 수정이 지금 결과 셈에 닿는 자리(밴드 S3K2b-2 ② — 결정 MARC-ENT-570·559). 업무 층. 값·이름은 지어낸 것이다.

합 = 다른 줄 + 고친 co2e · 고친 줄 제외·복구 · editedRows = 제외 ∪ 계수 고침 · 새 done 뒤 고친 값 0(옛 실행 히스토리
그대로, 같은 rowId) · 잠긴 카테고리는 핀 실행 고친 값 · 대시보드 합·상위 5 · Scope 1·2 칸 그대로.
"""

from decimal import Decimal

import pytest

from esgapi.inventory.service.actions import dashboard
from esgapi.inventory.service.actions import scope3_edits as edits
from esgapi.inventory.service.actions import scope3_state as state
from esgapi.inventory.tests.service.actions.test_scope3_factors import BUY, WHY, body, purchase, sheet, typed
from esgapi.inventory.tests.service.actions.test_scope3_state import CUSTOMER, YEAR, done_body, of, plant, processed

pytestmark = pytest.mark.django_db

OTHER = "가상_C1!30"


def two_rows() -> dict[str, object]:
    return {**done_body(sheet(1, purchase(BUY), purchase(OTHER))), "factorBook": body()["factorBook"]}


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


def fix(company_id: int, run: int, value: str = "2.0", row_id: str = BUY) -> None:
    checked = edits.check_factor(row_id, "custom", None, typed(value), WHY)
    assert isinstance(edits.factor(company_id, run, "C1", checked, CUSTOMER), edits.EditResult)


def line(company_id: int, category: str = "C1") -> state.CategoryState:
    found = state.year_state(company_id, YEAR)
    assert isinstance(found, state.YearState)
    return of(found, category)


def total(company_id: int) -> Decimal | None:
    current = line(company_id).current
    assert current is not None
    return current.value.total


def test_the_sum_takes_the_fixed_co2e(a: int) -> None:
    run = plant(a, two_rows())
    assert total(a) == Decimal("1.0")
    fix(a, run)
    assert total(a) == Decimal("2.5")
    assert line(a).edited_rows == 1


def test_a_fixed_row_can_be_excluded_and_restored_and_counts_once(a: int) -> None:
    run = plant(a, two_rows())
    fix(a, run)
    assert isinstance(edits.exclude(a, run, "C1", [BUY], WHY, CUSTOMER), edits.EditResult)
    assert (total(a), line(a).edited_rows) == (Decimal("0.5"), 1)
    fix(a, run, "4.0")  # 제외 뒤 계수 수정해도 제외 유지
    assert total(a) == Decimal("0.5")
    assert isinstance(edits.restore(a, run, "C1", [BUY], WHY, CUSTOMER), edits.EditResult)
    assert (total(a), line(a).edited_rows) == (Decimal("4.5"), 1)


def test_exclusion_and_fix_on_different_rows_count_two(a: int) -> None:
    run = plant(a, two_rows())
    fix(a, run)
    assert isinstance(edits.exclude(a, run, "C1", [OTHER], WHY, CUSTOMER), edits.EditResult)
    found = state.year_state(a, YEAR)
    assert isinstance(found, state.YearState)
    assert (of(found, "C1").edited_rows, found.edited_rows_unlocked) == (2, 2)


def test_a_new_done_run_drops_the_fixes_and_keeps_the_old_history(a: int) -> None:
    """570 — 새 실행은 같은 rowId 를 가져도 옛 사건을 받지 않는다(P2)."""
    old = plant(a, two_rows())
    fix(a, old)
    plant(a, two_rows())
    assert (total(a), line(a).edited_rows) == (Decimal("1.0"), 0)
    page = edits.history(a, old, None, offset=0, limit=20)
    assert isinstance(page, edits.HistoryPage)
    assert [item.kind for item in page.lines] == ["factor"]


def test_an_old_run_read_for_another_pin_lends_no_fix_to_the_new_run(a: int) -> None:
    """다른 카테고리의 핀 때문에 옛 실행의 사건이 같이 읽혀도 새 실행의 같은 rowId 는 받지 않는다(P2)."""
    both = {
        **done_body(sheet(1, purchase(BUY), purchase(OTHER)), processed(5, "1")),
        "factorBook": body()["factorBook"],
    }
    old = plant(a, both)
    fix(a, old)
    assert isinstance(state.lock(a, YEAR, "C5", old, CUSTOMER), state.CategoryState)
    plant(a, both)
    assert (total(a), line(a).edited_rows) == (Decimal("1.0"), 0)
    pinned = line(a, "C5").current
    assert pinned is not None and pinned.run_id == old


def test_a_locked_category_keeps_the_fix_of_its_pinned_run(a: int) -> None:
    old = plant(a, two_rows())
    fix(a, old)
    assert isinstance(state.lock(a, YEAR, "C1", old, CUSTOMER), state.CategoryState)
    plant(a, two_rows())
    assert (total(a), line(a).edited_rows) == (Decimal("2.5"), 1)
    found = state.year_state(a, YEAR)
    assert isinstance(found, state.YearState)
    assert found.edited_rows_unlocked == 0


def test_the_dashboard_counts_the_fix_and_leaves_scope12_alone(a: int) -> None:
    run = plant(a, two_rows())
    before = dashboard.board(a, YEAR)
    fix(a, run)
    after = dashboard.board(a, YEAR)
    assert (before.scope3, after.scope3) == (Decimal("1.0"), Decimal("2.5"))
    assert after.total == Decimal("2.5")
    assert [(item.category, item.value) for item in after.categories] == [("C1", Decimal("2.5"))]
    assert after.scope12 == before.scope12


def test_the_factor_answer_reads_events_once(a: int, django_assert_num_queries: object) -> None:
    run = plant(a, two_rows())
    state.year_state(a, YEAR)
    checked = edits.check_factor(BUY, "custom", None, typed(), WHY)
    with django_assert_num_queries(17):  # pyright: ignore[reportCallIssue, reportGeneralTypeIssues]
        edits.factor(a, run, "C1", checked, CUSTOMER)
