# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 데이터 엑셀의 몸(밴드 S3D1 ① — service/actions/scope3_excel.py). 업무 층.

R 없음 NotFound · 해 범위 밖 Invalid · 요약 합 = 연도 상태 지금 결과 합(카테고리 열넷) · 시트 줄 수 = 본문 줄 수 ·
제외(Y·합에서 빠짐) · 계수 고침(Y·사건 co2e) · 잠긴 카테고리는 핀 실행 값(새 done 뒤에도) · 줄 0 인 R 은 머리만 ·
파일 이름은 회사 이름. 실행 행은 심는다(실행기 0). 값·이름은 지어낸 것이다.
"""

import io
from decimal import Decimal
from typing import Any

import pytest
from openpyxl import load_workbook

from esgapi.inventory.service.actions import scope3_edits as edits
from esgapi.inventory.service.actions import scope3_excel as actions
from esgapi.inventory.service.actions import scope3_state as state
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound
from esgapi.inventory.service.utils.scope3_state import CATEGORIES
from esgapi.inventory.tests.service.actions.test_scope3_factors import BUY, WHY, body, typed
from esgapi.inventory.tests.service.actions.test_scope3_state import (
    CUSTOMER,
    YEAR,
    done_body,
    of,
    plant,
    processed,
)
from esgapi.organization.service.selectors.organization import company_name

pytestmark = pytest.mark.django_db
SUMMARY = "Scope 3 배출량"
TOTAL = "총 배출량(tCO2eq)"
CO2E = "온실가스 배출량(tCO2eq)"


@pytest.fixture
def a(companies: tuple[int, int]) -> int:
    return companies[0]


def download(company_id: int, year: int = YEAR) -> actions.Download:
    found = actions.export(company_id, year)
    assert isinstance(found, actions.Download), found
    return found


def sheets(company_id: int) -> dict[str, list[dict[str, Any]]]:
    book = load_workbook(io.BytesIO(download(company_id).content))
    out: dict[str, list[dict[str, Any]]] = {}
    for sheet in book.worksheets:
        head, *lines = [list[Any](line) for line in sheet.iter_rows(values_only=True)]
        out[sheet.title] = [dict(zip(head, line, strict=True)) for line in lines]
    return out


def summary(company_id: int) -> dict[str, dict[str, Any]]:
    return {line["카테고리"]: line for line in sheets(company_id)[SUMMARY]}


def year_totals(company_id: int) -> dict[str, Decimal | None]:
    found = state.year_state(company_id, YEAR)
    assert isinstance(found, state.YearState)
    return {line.category: None if line.current is None else line.current.value.total for line in found.categories}


def data_rows(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [line for line in lines if line["행"] != "시트 합계"]


def test_no_base_run_is_not_found_and_a_bad_year_is_invalid(a: int) -> None:
    assert isinstance(actions.export(a, YEAR), NotFound)
    plant(a, done_body(processed(4, "1.0")), status="failed")  # done 이 아니면 R 이 아니다
    assert isinstance(actions.export(a, YEAR), NotFound)
    assert isinstance(actions.export(a, 1800), Invalid)


def test_the_summary_is_the_year_state_and_the_sheets_hold_every_row(a: int) -> None:
    plant(a, done_body(processed(4, "1.5", "2.25"), processed(5, "0.5"), processed(8, None)))
    found = sheets(a)
    lines = summary(a)
    totals = year_totals(a)
    assert list(lines) == [*CATEGORIES, "Scope 3 합계"]
    for category in CATEGORIES:
        expected = totals[category]
        assert lines[category][TOTAL] == (None if expected is None else float(expected)), category
    assert lines["Scope 3 합계"][TOTAL] == 4.25
    assert len(data_rows(found["C4_업스트림운송"])) == 2 and len(data_rows(found["C8_임차자산"])) == 1
    assert data_rows(found["C1_구매품서비스"]) == []  # 시트 0 — 머리만
    assert len(found) == 15
    for category, title in (("C4", "C4_업스트림운송"), ("C5", "C5_사업장폐기물")):
        sums = [line[CO2E] for line in found[title] if line["행"] == "시트 합계"]
        assert sum(sums) == lines[category][TOTAL]  # 요약 합 = 카테고리 시트 합계 줄의 합


def test_an_exclusion_is_marked_and_leaves_the_sum(a: int) -> None:
    run = plant(a, done_body(processed(4, "1.5", "2.25")))
    assert isinstance(edits.exclude(a, run, "C4", ["가상_C4!21"], WHY, CUSTOMER), edits.EditResult)
    lines = data_rows(sheets(a)["C4_업스트림운송"])
    assert [line["제외"] for line in lines] == [None, "Y"]
    assert summary(a)["C4"][TOTAL] == 1.5 == float(year_totals(a)["C4"] or 0)
    assert summary(a)["C4"]["제외 줄 수"] == 1


def test_a_fixed_factor_is_marked_and_counted(a: int) -> None:
    run = plant(a, body())
    before = summary(a)["C1"][TOTAL]
    checked = edits.check_factor(BUY, "custom", None, typed("2.0"), WHY)
    assert isinstance(edits.factor(a, run, "C1", checked, CUSTOMER), edits.EditResult)
    line = next(line for line in data_rows(sheets(a)["C1_구매품서비스"]) if line["행"] == "20")
    assert line["수정"] == "Y"
    after = summary(a)["C1"]
    assert after[TOTAL] != before and after[TOTAL] == float(year_totals(a)["C1"] or 0)
    assert after["수정 줄 수"] == 1


def test_a_locked_category_keeps_its_pinned_run(a: int) -> None:
    first = plant(a, done_body(processed(4, "1.0"), processed(5, "1.0")))
    found = state.lock(a, YEAR, "C4", first, CUSTOMER)
    assert isinstance(found, state.CategoryState)
    plant(a, done_body(processed(4, "7.0"), processed(5, "7.0")))
    lines = summary(a)
    assert (lines["C4"][TOTAL], lines["C5"][TOTAL]) == (1.0, 7.0)
    found = sheets(a)
    c4, c5 = found["C4_업스트림운송"], found["C5_사업장폐기물"]
    assert [line[CO2E] for line in data_rows(c4)] == [1.0]  # 잠긴 C4 의 줄은 핀 실행 본문(검증 B1)
    assert [line[CO2E] for line in c4 if line["행"] == "시트 합계"] == [1.0] == [lines["C4"][TOTAL]]
    assert [line[CO2E] for line in data_rows(c5)] == [7.0]
    assert of(state.year_state(a, YEAR), "C4").current.run_id == first  # type: ignore[union-attr, arg-type]


def test_a_base_run_with_no_rows_gives_head_only_sheets(a: int) -> None:
    plant(a, done_body())
    found = sheets(a)
    assert all(data_rows(lines) == [] for title, lines in found.items() if title != SUMMARY)
    assert summary(a)["Scope 3 합계"][TOTAL] is None


def test_the_file_name_carries_the_company_name(a: int) -> None:
    plant(a, done_body(processed(4, "1.0")))
    assert download(a).file_name == f"{YEAR}_{company_name(a)}_Scope3_데이터.xlsx"


def test_a_fix_on_another_run_lends_nothing_to_the_new_run(a: int) -> None:
    """옛 실행이 다른 카테고리의 핀이라 그 사건을 같이 읽어도(쿼리 하나), C1 의 새 실행 줄에는 붙지 않는다(검증 R1)."""
    first = plant(a, body())
    checked = edits.check_factor(BUY, "custom", None, typed("2.0"), WHY)
    assert isinstance(edits.factor(a, first, "C1", checked, CUSTOMER), edits.EditResult)
    assert isinstance(state.lock(a, YEAR, "C5", first, CUSTOMER), state.CategoryState)
    plant(a, body())
    line = next(line for line in data_rows(sheets(a)["C1_구매품서비스"]) if line["행"] == "20")
    assert line["수정"] is None and line[CO2E] == 0.5
    assert summary(a)["C1"]["수정 줄 수"] == 0
