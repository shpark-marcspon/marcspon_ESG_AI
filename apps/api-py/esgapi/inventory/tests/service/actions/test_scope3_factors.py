# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportOptionalMemberAccess=false
"""Scope 3 줄 계수 수정의 판정·사건(밴드 S3K2b-2 ① — 결정 MARC-ENT-570·442, 발주서 Q5·Q6·Q7·Q8). 업무 층.

세 갈래 → 사건·edits·history · applied 는 고치지 않은 줄 · 같은 고름 사건 0 · 고칠 수 없는 줄 409 + 사건 0 + 상태 행 0 ·
잠김·옛 실행 409 · 제외된 줄도 받음 · C5 생물기원 · 결과 본문은 덮지 않음. 값·이름은 지어낸 것이다.
"""

from typing import Any

import pytest

from esgapi.inventory.models import Scope3CategoryState, Scope3RowEdit
from esgapi.inventory.service.actions import scope3_edits as edits
from esgapi.inventory.service.actions import scope3_state as state
from esgapi.inventory.service.utils.entries import Locked
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound
from esgapi.inventory.service.utils.scope3_factors import Custom
from esgapi.inventory.tests.service.actions.test_scope3_state import CUSTOMER, YEAR, done_body, of, plant
from esgapi.runs.service.selectors import runs as run_selectors

pytestmark = pytest.mark.django_db

WHY = "가상 사유"
BOOK = {"sheet": "가상_구매표", "column": "가상 열\n2025 기준"}
BUY, LOST, DRY = "가상_C1!20", "가상_C1!21", "가상_C1!22"
BURN = "가상_C5!20"
HOLD, BACK = "가상_C15!20", "가상_C12!20"


def purchase(row_id: str, **over: Any) -> dict[str, Any]:
    return {
        "rowId": row_id,
        "kind": "purchase",
        "amount": "1000.0",
        "factor": {"title": "가상 계수", "value": "0.5", "unit": "kgCO2e/KRW", "column": "가상 열\n2025 기준"},
        "co2e": "0.5",
        "recommendations": [
            {"title": "가상 추천 1", "value": "0.25", "expectedCo2e": "0.25"},
            {"title": "가상 추천 2", "value": "0.75", "expectedCo2e": "0.75"},
        ],
    } | over


def waste(row_id: str) -> dict[str, Any]:
    return {
        "rowId": row_id,
        "kind": "waste",
        "activity": {"value": "1000.0", "baseValue": "1000.0"},
        "factor": {"sheet": "가상_폐기물표", "title": None, "value": "2.0", "unit": "kgCO2eq/kg"},
        "co2e": "0.5",
        "treatment": "소각",
        "biogenic": {"fossilCo2e": "0.5", "biogenicCo2e": "1.5", "fcf": "0.25", "note": "가상"},
    }


def sheet(n: int, *rows: dict[str, Any]) -> dict[str, object]:
    return {"sheet": f"가상_C{n}", "category": f"Category{n}", "status": "processed", "rows": list(rows)}


def body() -> dict[str, object]:
    return {
        **done_body(
            sheet(
                1,
                purchase(BUY),
                purchase(LOST, factor={"title": None, "value": None, "unit": "kgCO2e/KRW"}, co2e=None),
                purchase(DRY, amount=None, co2e=None),
            ),
            sheet(5, waste(BURN)),
            sheet(
                12, {"rowId": BACK, "kind": "product_eol", "co2e": "1.0", "factor": {"value": "1.0", "unit": "가상"}}
            ),
            sheet(15, {"rowId": HOLD, "kind": "investment", "co2e": "1.0", "factor": None}),
        ),
        "factorBook": BOOK,
    }


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


def pick(company_id: int, run: int, row_id: str = BUY, choice: Any = "applied", **over: Any) -> Any:
    category = over.pop("category", "C1")
    rank, custom = over.pop("rank", None), over.pop("custom", None)
    checked = edits.check_factor(row_id, choice, rank, custom, over.pop("reason", WHY))
    return edits.factor(company_id, run, category, checked, CUSTOMER)


def typed(value: str = "2.0") -> Custom:
    return Custom("가상 직접 계수", value, "가상 출처")


def rows_of(company_id: int) -> list[Any]:
    return list(Scope3RowEdit.for_company(company_id).order_by("id"))


def state_rows(company_id: int) -> int:
    return Scope3CategoryState.for_company(company_id).count()


def total(company_id: int, category: str = "C1") -> object:
    found = state.year_state(company_id, YEAR)
    assert isinstance(found, state.YearState)
    current = of(found, category).current
    return None if current is None else current.value.total


def test_recommended_leaves_one_event_with_the_ai_original(a: int) -> None:
    run = plant(a, body())
    found = pick(a, run, choice="recommended", rank=2)
    assert isinstance(found, edits.EditResult)
    (row,) = rows_of(a)
    assert (row.kind, row.factor_choice, row.factor_rank, row.factor_title, row.factor_value, row.co2e) == (
        "factor",
        "recommended",
        2,
        "가상 추천 2",
        "0.75",
        "0.75",
    )
    assert (row.ai_factor_title, row.ai_factor_value, row.ai_co2e) == ("가상 계수", "0.5", "0.5")
    assert row.ai_factor_source == row.factor_source == "가상_구매표 가상 열 2025 기준"
    assert row.factor_unit == "kgCO2e/KRW"
    assert row.batch_id is not None
    (line,) = found.rows
    assert (line.row_id, line.excluded, line.factor.choice, line.factor.co2e) == (BUY, False, "recommended", "0.75")
    assert found.category.edited_rows == 1


def test_custom_is_counted_by_the_formula_and_seen_in_edits_and_history(a: int) -> None:
    run = plant(a, body())
    assert isinstance(pick(a, run, choice="custom", custom=typed()), edits.EditResult)
    found = edits.edits(a, run)
    assert isinstance(found, edits.Edits)
    (line,) = found.rows
    assert (line.factor.title, line.factor.value, line.factor.source, line.factor.co2e) == (
        "가상 직접 계수",
        "2.0",
        "가상 출처",
        "2.0",
    )
    assert line.factor.ai.co2e == "0.5"
    page = edits.history(a, run, None, offset=0, limit=20)
    assert isinstance(page, edits.HistoryPage)
    assert [(item.kind, item.factor.choice) for item in page.lines] == [("factor", "custom")]


def test_applied_goes_back_to_the_original_and_the_event_stays(a: int) -> None:
    run = plant(a, body())
    pick(a, run, choice="custom", custom=typed())
    found = pick(a, run, choice="applied")
    assert isinstance(found, edits.EditResult)
    assert found.category.edited_rows == 0
    assert found.rows[0].factor.co2e == "0.5"
    assert [row.factor_choice for row in rows_of(a)] == ["custom", "applied"]
    assert total(a) is not None


def test_the_same_choice_again_leaves_no_event(a: int) -> None:
    run = plant(a, body())
    assert isinstance(pick(a, run, choice="applied"), edits.EditResult)  # 고치지 않은 줄의 applied
    assert rows_of(a) == []
    pick(a, run, choice="custom", custom=typed("2.0"))
    assert isinstance(pick(a, run, choice="custom", custom=typed("2.00")), edits.EditResult)  # 저장 글자끼리 같다
    pick(a, run, choice="recommended", rank=1)
    pick(a, run, choice="recommended", rank=1, reason="다른 사유")
    assert [row.factor_choice for row in rows_of(a)] == ["custom", "recommended"]


def test_a_row_without_a_found_factor_takes_a_custom_value_into_the_sum(a: int) -> None:
    run = plant(a, body())
    before = total(a)
    assert isinstance(pick(a, run, LOST, "custom", custom=typed()), edits.EditResult)
    assert total(a) == before + 2  # pyright: ignore[reportOperatorIssue]
    assert rows_of(a)[0].ai_factor_value is None


def test_an_excluded_row_can_still_change_its_factor_and_stays_excluded(a: int) -> None:
    run = plant(a, body())
    assert isinstance(edits.exclude(a, run, "C1", [BUY], WHY, CUSTOMER), edits.EditResult)
    found = pick(a, run, choice="custom", custom=typed())
    assert isinstance(found, edits.EditResult)
    assert (found.rows[0].excluded, found.rows[0].factor.choice) == (True, "custom")


def test_a_c5_row_keeps_fossil_and_biogenic_apart(a: int) -> None:
    run = plant(a, body())
    found = pick(a, run, BURN, "custom", custom=typed("4.0"), category="C5")
    assert isinstance(found, edits.EditResult)
    fixed = found.rows[0].factor
    assert (fixed.co2e, fixed.biogenic_co2e) == (repr(4.0 - 4.0 * 0.75), repr(4.0 * 0.75))


@pytest.mark.parametrize(
    "row",
    [waste(BURN), {**waste(BURN), "treatment": "매립", "biogenic": None, "co2e": "2.0"}],
    ids=["fcf", "no-fcf"],
)
def test_a_c5_value_that_overflows_is_refused_and_leaves_nothing(a: int, row: dict[str, Any]) -> None:
    run = plant(a, {**done_body(sheet(5, row)), "factorBook": BOOK})
    found = pick(a, run, BURN, "custom", custom=typed("1" + "0" * 308), category="C5")
    assert isinstance(found, edits.FactorNotEditable)
    assert rows_of(a) == []
    assert state_rows(a) == 0


@pytest.mark.parametrize(
    ("row_id", "category"),
    [(HOLD, "C15"), (BACK, "C12"), (DRY, "C1")],
    ids=["c15", "c12", "no-amount"],
)
def test_rows_that_cannot_be_edited_leave_nothing(a: int, row_id: str, category: str) -> None:
    run = plant(a, body())
    found = pick(a, run, row_id, "custom", custom=typed(), category=category)
    assert isinstance(found, edits.FactorNotEditable)
    assert rows_of(a) == []
    assert state_rows(a) == 0


def test_a_row_of_no_factor_object_is_refused_even_as_applied(a: int) -> None:
    run = plant(a, body())
    assert isinstance(pick(a, run, HOLD, "applied", category="C15"), edits.FactorNotEditable)


@pytest.mark.parametrize(
    ("row_id", "category", "rank", "field"),
    [("가상_없는!1", "C1", None, "rowId"), (BUY, "C5", None, "rowId"), (BUY, "C1", 3, "rank"), (BURN, "C5", 1, "rank")],
    ids=["unknown", "other-category", "past-the-end", "not-purchase"],
)
def test_the_422s_after_the_row_hold_leave_no_state_row(
    a: int, row_id: str, category: str, rank: int | None, field: str
) -> None:
    run = plant(a, body())
    found = pick(a, run, row_id, "custom" if rank is None else "recommended", rank=rank, category=category,
                 custom=typed() if rank is None else None)  # fmt: skip
    assert isinstance(found, Invalid)
    assert set(found.fields) == {field}
    assert (rows_of(a), state_rows(a)) == ([], 0)


def test_a_bad_body_comes_before_anything_else(a: int) -> None:
    found = pick(a, 999_999, choice="custom", custom=typed("0"))
    assert isinstance(found, Invalid)
    assert found.fields == {"custom.value": "0보다 큰 수다"}


def test_a_locked_category_and_an_old_run_are_refused(a: int) -> None:
    old = plant(a, body())
    assert isinstance(state.lock(a, YEAR, "C5", old, CUSTOMER), state.CategoryState)
    assert isinstance(pick(a, old, BURN, "custom", custom=typed(), category="C5"), Locked)
    plant(a, body())
    assert isinstance(pick(a, old, choice="custom", custom=typed()), state.StaleRun)
    assert rows_of(a) == []


def test_unknown_category_and_foreign_runs_are_not_found(companies: tuple[int, int]) -> None:
    a, b = companies
    run = plant(a, body())
    assert isinstance(pick(a, run, category="C10"), NotFound)
    assert isinstance(pick(b, run), NotFound)
    assert isinstance(pick(a, 999_999), NotFound)


def test_the_result_body_is_not_touched(a: int) -> None:
    run = plant(a, body())
    (before,) = run_selectors.run_results(company_id=a, run_id=run)
    pick(a, run, choice="custom", custom=typed())
    (after,) = run_selectors.run_results(company_id=a, run_id=run)
    assert after.body == before.body
