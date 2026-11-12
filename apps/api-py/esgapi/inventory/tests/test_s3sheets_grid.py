"""읽힌 표의 주소·범위(`tools/scope3_sheets/grid.py`). 순수 층."""

import pytest

from esgapi.inventory.tools.scope3_sheets.grid import (
    MAX_RANGE_CELLS,
    AddressProblem,
    CellAddress,
    CellRange,
    Sheet,
    SheetRange,
    TextCell,
    column_letters,
    column_number,
    expand_range,
    format_address,
    format_range,
    merge_anchor,
    parse_address,
    parse_range,
    parse_sheet_range,
    range_size,
)


@pytest.mark.parametrize(
    ("text", "row", "column"),
    [("A1", 1, 1), ("Z9", 9, 26), ("AA10", 10, 27), ("AG73", 73, 33), ("XFD1048576", 1_048_576, 16_384)],
)
def test_an_address_round_trips(text: str, row: int, column: int) -> None:
    assert parse_address(text) == CellAddress(row, column)
    assert format_address(CellAddress(row, column)) == text
    assert column_letters(column_number(text.rstrip("0123456789"))) == text.rstrip("0123456789")


def test_dollar_signs_are_accepted_and_dropped() -> None:
    assert parse_address("$B$7") == CellAddress(7, 2)
    assert parse_range("$A$3:$A$19") == CellRange(CellAddress(3, 1), CellAddress(19, 1))


@pytest.mark.parametrize("text", ["", "a1", "A0", "A01", "XFE1", "A1048577", "AAAA1", "A１", "A1 ", "1A", "A", "A1:B2"])
def test_what_is_not_an_address_is_a_branch(text: str) -> None:
    assert parse_address(text) == AddressProblem("not_an_address", text)


def test_a_range_round_trips_and_a_single_cell_is_a_range_of_one() -> None:
    cells = parse_range("B3:D4")
    assert cells == CellRange(CellAddress(3, 2), CellAddress(4, 4))
    assert isinstance(cells, CellRange)
    assert format_range(cells) == "B3:D4"
    assert range_size(cells) == 6
    assert expand_range(cells) == ("B3", "C3", "D3", "B4", "C4", "D4")
    single = parse_range("C5")
    assert isinstance(single, CellRange)
    assert format_range(single) == "C5"
    assert expand_range(single) == ("C5",)


@pytest.mark.parametrize("text", ["B9:A3", "A3:A", "A1:B2:C3", ":A1", "A1:", "시트!A1"])
def test_what_is_not_a_range_is_a_branch(text: str) -> None:
    assert parse_range(text) == AddressProblem("not_a_range", text)


def test_a_sheet_range_keeps_the_sheet_name_and_strips_quotes() -> None:
    expected = CellRange(CellAddress(3, 1), CellAddress(19, 1))
    assert parse_sheet_range("배출계수_드롭다운!$A$3:$A$19") == SheetRange("배출계수_드롭다운", expected)
    assert parse_sheet_range("'가상 시트'!A3:A19") == SheetRange("가상 시트", expected)
    assert parse_sheet_range("A3:A19") == AddressProblem("not_a_range", "A3:A19")
    assert parse_sheet_range("시트!가나다") == AddressProblem("not_a_range", "시트!가나다")


def test_expanding_a_range_over_the_limit_is_a_branch_not_a_list() -> None:
    """시간이 아니라 갈래로 잰다: 상한을 한 칸 넘는 범위도 펼치지 않는다."""
    exactly = parse_range(f"A1:A{MAX_RANGE_CELLS}")
    over = parse_range(f"A1:A{MAX_RANGE_CELLS + 1}")
    wide = parse_range("A1:J1001")
    assert isinstance(exactly, CellRange) and isinstance(over, CellRange) and isinstance(wide, CellRange)
    expanded = expand_range(exactly)
    assert isinstance(expanded, tuple) and len(expanded) == MAX_RANGE_CELLS
    assert expand_range(over) == AddressProblem("range_too_large", f"A1:A{MAX_RANGE_CELLS + 1}")
    assert expand_range(wide) == AddressProblem("range_too_large", "A1:J1001")


def test_the_merge_anchor_is_the_top_left_cell_and_values_are_not_spread() -> None:
    sheet = Sheet("가상", {"A1": TextCell("가상 제목")}, ("A1:C2", "E5:F5"), ())
    assert merge_anchor(sheet, "B2") == "A1"
    assert merge_anchor(sheet, "F5") == "E5"
    assert merge_anchor(sheet, "D4") == "D4"
    assert merge_anchor(sheet, "가") == AddressProblem("not_an_address", "가")
    assert "B2" not in sheet.cells  # 병합의 값을 나머지 칸에 퍼뜨리지 않는다
