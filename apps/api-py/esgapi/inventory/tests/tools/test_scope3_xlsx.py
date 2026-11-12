# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 데이터 엑셀 순수 도구(밴드 S3D1 ① — tools/scope3_xlsx.py). 순수 층(DB 0).

빈 책(요약 + 머리만 카테고리 열넷) · 시트 꼴 머리(화면 headerOf 글자 + 엑셀 전용 열·단위 열) · 수 칸은 수 ·
비율·FCF 백분율 ·
제외 줄(Y·비율 빈 칸·합에서 빠짐) · 계수 고친 줄(Y·사건 co2e·계수·출처 글) · C5 생물기원(시트·요약) · 수단 이름표 ·
행 번호 차례 · 꼴 틀린 줄은 basic · 시트 꼴이 여럿이면 합집합 · 수식 글은 글 칸 · 같은 입력 같은 바이트 · 파일 이름 ·
django·esgapi import 0. 값·이름은 지어낸 것이다.
"""

import ast
import io
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from esgapi.inventory.tools import scope3_xlsx as xlsx

INPUT_NONE = dict.fromkeys(xlsx.INPUT_KEYS)


def purchase(row: int, co2e: str | None = "1.5", **over: Any) -> dict[str, Any]:
    return {
        "rowId": f"가상_C1!{row}",
        "kind": "purchase",
        "co2e": co2e,
        "spendKrw": "1000.0",
        "group": {"name": "가상 그룹"},
        "factor": {
            "title": "가상 계수",
            "value": "0.0015",
            "unit": "kgCO2e/KRW",
            "column": "가상",
            "source": "db_keyword",
        },
        "originSteps": [],
        "input": {**INPUT_NONE, "country": "가상국", "site": "가상 사업장", "name": f"가상 품목 {row}"},
    } | over


def waste(row: int, co2e: str = "2.0", biogenic: str = "0.5") -> dict[str, Any]:
    return {
        "rowId": f"가상_C5!{row}",
        "kind": "waste",
        "co2e": co2e,
        "activity": {"value": "10.0", "unit": "t", "baseValue": "10000.0", "baseUnit": "kg"},
        "factor": {"sheet": "폐기물_C5", "title": "가상 소각", "value": "0.2", "unit": "kg"},
        "treatment": "소각",
        "mode": None,
        "distance": None,
        "biogenic": {"fossilCo2e": co2e, "biogenicCo2e": biogenic, "fcf": "0.25", "note": "가상"},
        "originSteps": [],
        "input": {**INPUT_NONE, "site": "가상 사업장", "name": "가상 폐기물"},
    }


def commute(row: int, mode: str) -> dict[str, Any]:
    return {
        "rowId": f"가상_C7!{row}",
        "kind": "commute",
        "co2e": "1.0",
        "activity": {"value": "100.0", "unit": "km", "baseValue": None, "baseUnit": None},
        "factor": {"sheet": "가상_통근", "title": None, "value": "0.1", "unit": "kgCO2eq/km"},
        "treatment": None,
        "mode": {"value": mode},
        "distance": {"km": "10.0", "roundTrip": "2", "people": "3", "trips": None, "workdays": "200"},
        "biogenic": None,
        "originSteps": [],
        "input": None,
    }


def book(category: str, *sheets: xlsx.EngineSheet, **over: Any) -> xlsx.CategoryBook:
    fields: dict[str, Any] = {
        "category": category,
        "name": f"가상 {category}",
        "sheet_name": f"{category}_가상",
        "total": None,
        "sheets": len(sheets),
        "failed_sheets": 0,
        "engine_sheets": sheets,
    }
    return xlsx.CategoryBook(**(fields | over))


ALL = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C11", "C12", "C13", "C14", "C15")


def built(*books: xlsx.CategoryBook) -> Any:
    given = {one.category: one for one in books}
    content = xlsx.build_export(xlsx.ExportBook(2025, [given.get(c) or book(c) for c in ALL]))
    return load_workbook(io.BytesIO(content))


def rows(sheet: Worksheet) -> list[list[Any]]:
    return [list(line) for line in sheet.iter_rows(values_only=True)]


def by_head(sheet: Worksheet) -> list[dict[str, Any]]:
    head, *body = rows(sheet)
    return [dict(zip(head, line, strict=True)) for line in body]


def test_an_empty_book_has_a_summary_and_fourteen_head_only_sheets() -> None:
    found = built()
    assert found.sheetnames == ["Scope 3 배출량", *(f"{c}_가상" for c in ALL)]
    summary = rows(found["Scope 3 배출량"])
    assert summary[0] == [
        "카테고리",
        "카테고리 이름",
        "총 배출량(tCO2eq)",
        "생물기원 CO2(tCO2eq)",
        "시트 수",
        "실패 시트 수",
        "제외 줄 수",
        "수정 줄 수",
    ]
    assert [line[0] for line in summary[1:]] == [*ALL, "Scope 3 합계"]
    assert summary[1][2:] == [None, None, 0, 0, 0, 0]
    assert rows(found["C1_가상"]) == [
        ["시트", "행", "제외", "온실가스 배출량(tCO2eq)", "배출량 비율", "배출계수", "배출계수 단위", "수정"]
    ]


def test_the_c1_sheet_has_the_screen_heads_and_numbers() -> None:
    found = built(
        book("C1", xlsx.EngineSheet("가상_C1", [purchase(20), purchase(21, co2e="0.5")]), total=Decimal("2.0"))
    )
    sheet = found["C1_가상"]
    assert rows(sheet)[0] == [
        "시트",
        "행",
        "제외",
        "국가",
        "사업장",
        "그룹명",
        "품목명",
        "연간지출금액(원)",
        "온실가스 배출량(tCO2eq)",
        "배출량 비율",
        "배출계수",
        "배출계수 단위",
        "출처",
        "수정",
    ]
    first = by_head(sheet)[0]
    assert first["행"] == "20" and first["품목명"] == "가상 품목 20" and first["출처"] == "US EPA"
    assert first["온실가스 배출량(tCO2eq)"] == 1.5 and first["배출계수"] == 0.0015
    assert first["배출계수 단위"] == "kgCO2e/KRW"
    assert first["배출량 비율"] == 0.75
    cells = next(iter(sheet.iter_rows(min_row=2, max_row=2)))
    assert cells[8].data_type == "n" and cells[8].number_format == xlsx.NUMBER_FORMAT
    assert cells[9].number_format == xlsx.PERCENT_FORMAT
    assert cells[1].data_type == "s"  # 행 번호는 글
    total = by_head(sheet)[-1]
    assert (total["시트"], total["행"], total["온실가스 배출량(tCO2eq)"]) == ("가상_C1", "시트 합계", 2.0)
    summary = by_head(found["Scope 3 배출량"])[0]
    assert summary["총 배출량(tCO2eq)"] == 2.0 and summary["시트 수"] == 1


def test_an_excluded_row_is_marked_and_left_out_of_the_sheet_sum() -> None:
    found = built(
        book(
            "C1",
            xlsx.EngineSheet("가상_C1", [purchase(20), purchase(21, co2e="0.5")]),
            excluded=frozenset({"가상_C1!21"}),
        )
    )
    lines = by_head(found["C1_가상"])
    assert (lines[0]["제외"], lines[1]["제외"]) == (None, "Y")
    assert lines[1]["배출량 비율"] is None and lines[0]["배출량 비율"] == 1.0
    assert lines[2]["온실가스 배출량(tCO2eq)"] == 1.5
    assert by_head(found["Scope 3 배출량"])[0]["제외 줄 수"] == 1


def test_a_fixed_row_shows_the_event_values() -> None:
    fixed = xlsx.FixedFactor(value="0.003", unit="KRW", source="구매_USEPA 가상 열", co2e="3.0", biogenic_co2e=None)
    found = built(book("C1", xlsx.EngineSheet("가상_C1", [purchase(20)]), fixed={"가상_C1!20": fixed}))
    line = by_head(found["C1_가상"])[0]
    assert line["수정"] == "Y" and line["온실가스 배출량(tCO2eq)"] == 3.0
    assert (line["배출계수"], line["배출계수 단위"], line["출처"]) == (0.003, "kgCO2eq/KRW", "US EPA")
    assert by_head(found["Scope 3 배출량"])[0]["수정 줄 수"] == 1


def test_c5_carries_biogenic_and_fcf_and_its_summary() -> None:
    found = built(
        book(
            "C5", xlsx.EngineSheet("가상_C5", [waste(20), waste(21, "1.0", "0.25")]), excluded=frozenset({"가상_C5!21"})
        )
    )
    head, first, _, total = rows(found["C5_가상"])
    assert head == [
        "시트",
        "행",
        "제외",
        "사업장명",
        "폐기물",
        "처리 방법",
        "연간처리량",
        "연간처리량 단위",
        "온실가스 배출량(tCO2eq)",
        "배출량 비율",
        "생물기원 CO2(tCO2eq)",
        "배출계수",
        "배출계수 단위",
        "FCF",
        "수정",
    ]
    line = dict(zip(head, first, strict=True))
    assert (line["연간처리량"], line["연간처리량 단위"], line["FCF"]) == (10.0, "t", 0.25)
    assert line["배출계수 단위"] == "kgCO2eq/kg"  # 웹 factorUnitOf
    assert dict(zip(head, total, strict=True))["생물기원 CO2(tCO2eq)"] == 0.5  # 제외 줄 뺌
    summary = by_head(found["Scope 3 배출량"])
    assert summary[4]["생물기원 CO2(tCO2eq)"] == 0.5 and summary[0]["생물기원 CO2(tCO2eq)"] is None
    assert summary[-1]["생물기원 CO2(tCO2eq)"] == 0.5


def test_modes_use_the_screen_labels() -> None:
    found = built(book("C7", xlsx.EngineSheet("가상_C7", [commute(20, "bus"), commute(21, "가상_모름")])))
    lines = by_head(found["C7_가상"])
    assert (lines[0]["교통수단"], lines[1]["교통수단"]) == ("버스", "기타")
    assert lines[0]["연간근무일수"] == 200.0


def test_rows_follow_the_row_number_and_a_bad_row_is_basic() -> None:
    bad = {"rowId": "가상_C1!3", "co2e": "nan", "kind": "purchase"}  # originSteps 없음 → basic
    sheet = xlsx.EngineSheet("가상_C1", [purchase(20), {"rowId": "가상_C1!12#2", "co2e": "1"}, bad, "줄 아님"])
    lines = by_head(built(book("C1", sheet))["C1_가상"])
    assert [line["행"] for line in lines] == ["3", "12-2", "20", "시트 합계"]
    assert lines[0]["온실가스 배출량(tCO2eq)"] is None and lines[0]["그룹명"] is None


def test_two_layouts_in_one_category_share_one_head() -> None:
    far = {**waste(20), "rowId": "가상_C4!20", "kind": "transport_distance", "treatment": None}
    spend = {**far, "rowId": "가상_C4!21", "kind": "transport_spend"}
    found = built(book("C4", xlsx.EngineSheet("C4-1_가상", [far]), xlsx.EngineSheet("C4-2_가상", [spend])))
    head = rows(found["C4_가상"])[0]
    assert head[:6] == ["시트", "행", "제외", "자재명/품목명", "연간운송량", "연간운송량 단위"]
    assert "연간운송금액" in head and head.count("온실가스 배출량(tCO2eq)") == 1


def test_a_formula_like_text_stays_text() -> None:
    row = purchase(20, input={**INPUT_NONE, "name": "=1+1"})
    sheet = built(book("C1", xlsx.EngineSheet("가상_C1", [row])))["C1_가상"]
    cell = sheet.cell(row=2, column=7)
    assert (cell.value, cell.data_type) == ("=1+1", "s")


def test_same_input_same_bytes_and_the_file_name() -> None:
    one = xlsx.ExportBook(2025, [book(c) for c in ALL])
    assert xlsx.build_export(one) == xlsx.build_export(one)
    assert xlsx.export_file_name(2025, "가상/회사") == "2025_가상_회사_Scope3_데이터.xlsx"


@pytest.mark.parametrize(
    ("unit", "shown"),
    [("kg", "kgCO2eq/kg"), ("kgCO2e/KRW", "kgCO2e/KRW"), ("", ""), (None, None)],
)
def test_factor_unit_of(unit: str | None, shown: str | None) -> None:
    assert xlsx.factor_unit_of(unit) == shown


def test_the_tool_imports_no_django_or_esgapi() -> None:
    tree = ast.parse(Path(xlsx.__file__).read_text(encoding="utf-8"))
    names = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    names += [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not [name for name in names if name.split(".")[0] in ("django", "esgapi")]
