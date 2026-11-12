"""계수 책 적재기(`tools/scope3_sheets/factors.py`). 순수 층. 표본은 지은 것이다(`s3sheets_support`).

「원본에서 이 수가 나온다」는 여기서 재지지 않는다(게이트 밖의 원본 대조가 잰다). 여기는 지은 표본이 그 수로 읽히는지와,
적재기가 고르거나 메우거나 버리지 않는지를 잰다.
"""

from dataclasses import fields, replace

from esgapi.inventory.tests.s3sheets_support import (
    number,
    sample_factor_book,
    sheet_named,
    text,
    with_cell,
    with_sheet,
)
from esgapi.inventory.tools.scope3_sheets.factor_layout import FACTOR_SHEETS, INDEX_SHEET
from esgapi.inventory.tools.scope3_sheets.factors import (
    DerivedEntry,
    Empty,
    ExtraEntry,
    FactorBook,
    FactorRow,
    HeaderMismatch,
    MissingSheet,
    Note,
    Placeholder,
    SheetAccount,
    Unaccounted,
    UnknownSheet,
    ValueEntry,
    column_cells,
    load_factor_book,
)
from esgapi.inventory.tools.scope3_sheets.grid import FormulaCell, NumberCell, Sheet, TextCell, Workbook

# 시트 → (계수 행, 숫자 값 칸). 발주서의 원본 요약과 같게 지은 표본의 수다.
EXPECTED = {
    "에너지": (14, 62),
    "에너지_C3": (12, 12),
    "운송": (6, 6),
    "출장_통근": (11, 11),
    "폐기물_C5": (65, 65),
    "폐기물_C12": (73, 213),
    "구매_USEPA": (190, 190),
    "운송_Spend": (17, 17),
    "출장_Spend": (11, 11),
    "전력_국가별": (4, 4),
}


def loaded() -> FactorBook:
    return load_factor_book(sample_factor_book())


def rows_of(book: FactorBook, sheet: str) -> list[FactorRow]:
    return [row for row in book.rows if row.sheet == sheet]


def row_at(book: FactorBook, sheet: str, row: int) -> FactorRow:
    return next(item for item in book.rows if item.sheet == sheet and item.row == row)


def value_at(book: FactorBook, sheet: str, row: int, column: str) -> ValueEntry:
    return next(entry for entry in row_at(book, sheet, row).values if entry.column == column)


def test_every_sheet_loads_the_rows_and_value_cells_of_the_sample() -> None:
    book = loaded()
    assert book.problems == ()
    got = {
        name: (
            len(rows_of(book, name)),
            sum(1 for row in rows_of(book, name) for e in row.values if isinstance(e.content, NumberCell)),
        )
        for name in EXPECTED
    }
    assert got == EXPECTED
    assert len(book.rows) == 403
    assert sum(numbers for _, numbers in got.values()) == 591
    assert book.sheet_names == (INDEX_SHEET.name, *EXPECTED)


def test_every_cell_is_accounted_for_exactly_once() -> None:
    """칸 회계: 갈래별 합 == 시트의 칸 수, 어디에도 안 든 칸 0. 열한 시트 전부."""
    workbook = sample_factor_book()
    book = load_factor_book(workbook)
    assert [account.sheet for account in book.accounts] == [sheet.name for sheet in workbook.sheets]
    for account in book.accounts:
        parts = (
            account.title_header + account.label + account.value + account.derived + account.extra + account.note
        ) + account.link
        assert parts == account.total == len(sheet_named(workbook, account.sheet).cells), account.sheet
        assert account.unaccounted == 0, account.sheet
    assert [problem for problem in book.problems if isinstance(problem, Unaccounted)] == []
    assert sum(account.derived for account in book.accounts) == 654
    assert sum(account.value for account in book.accounts) == 591 + 8  # 숫자 값 칸 + `-`
    assert sum(account.total for account in book.accounts) == sum(len(sheet.cells) for sheet in workbook.sheets)


def test_a_cell_in_a_column_without_a_header_is_not_lost() -> None:
    """꼴에 없는 열에 칸을 하나 더하면 그 줄의 extras 로 나온다(사라지지 않는다). 회계도 맞는다."""
    workbook = with_cell(sample_factor_book(), "운송", "K5", text("가상 덧붙인 칸"))
    book = load_factor_book(workbook)
    assert row_at(book, "운송", 5).extras == (ExtraEntry("K", TextCell("가상 덧붙인 칸")),)
    assert [problem for problem in book.problems if isinstance(problem, Unaccounted)] == []
    account = next(account for account in book.accounts if account.sheet == "운송")
    assert (account.extra, account.unaccounted) == (1, 0)
    # 표본에 원래 있는 것: 머리글 없는 열의 글 하나.
    assert row_at(loaded(), "에너지", 17).extras == (ExtraEntry("J", TextCell("가상 머리글 없는 열의 글")),)


def test_a_cell_the_loader_has_no_place_for_is_reported_unaccounted_not_dropped() -> None:
    """값 열의 수식 칸, 파생 열의 수식 아닌 칸은 실을 자리가 없다. 버리지 않고 Unaccounted 로 낸다."""
    workbook = with_cell(sample_factor_book(), "운송", "E4", FormulaCell("E3*9", None, number("9.5")))
    workbook = with_cell(workbook, "구매_USEPA", "I5", number("9.5"))
    book = load_factor_book(workbook)
    assert [problem for problem in book.problems if isinstance(problem, Unaccounted)] == [
        Unaccounted("운송", "E4"),
        Unaccounted("구매_USEPA", "I5"),
    ]
    accounts = {account.sheet: account for account in book.accounts}
    assert (accounts["운송"].unaccounted, accounts["구매_USEPA"].unaccounted) == (1, 1)


def test_rows_after_a_blank_row_are_loaded() -> None:
    """빈 줄에서 읽기를 멈추지 않는다: 폐기물_C5 의 66행, 폐기물_C12 의 73행 뒤에 줄 셋씩이 있다."""
    book = loaded()
    assert [row.row for row in rows_of(book, "폐기물_C5")] == [*range(4, 66), 67, 68, 69]
    assert [row.row for row in rows_of(book, "폐기물_C12")] == [*range(3, 73), 74, 75, 76]
    # 뒤의 줄은 뜻으로 가르지 않는다. 빈 칸의 꼴만 남는다: 값 열 셋 가운데 하나만 찼다.
    tail = [[type(entry.content) for entry in row_at(book, "폐기물_C12", row).values] for row in (74, 75, 76)]
    assert tail == [[NumberCell, Empty, Empty], [Empty, NumberCell, Empty], [Empty, Empty, NumberCell]]
    assert "C" not in {entry.column for entry in row_at(book, "폐기물_C12", 74).labels}


def test_a_dash_in_a_value_cell_is_a_placeholder_not_zero() -> None:
    book = loaded()
    dashes = [
        (row.row, entry.column)
        for row in rows_of(book, "에너지")
        for entry in row.values
        if entry.content == Placeholder("-")
    ]
    assert dashes == [(row, column) for row in (17, 18) for column in "EFGH"]
    assert isinstance(value_at(book, "에너지", 17, "I").content, NumberCell)
    assert [e.content for row in book.rows for e in row.values if e.content == NumberCell("0", "0")] == []


def test_a_label_stored_as_a_number_stays_a_number() -> None:
    book = loaded()
    codes = dict(column_cells(book, "구매_USEPA", "D"))
    numeric = sorted(row for row, cell in codes.items() if isinstance(cell, NumberCell))
    assert numeric == [14, *range(78, 88)]  # 11줄
    assert codes[14] == NumberCell("900014", "900014")
    assert isinstance(codes[15], TextCell)
    assert all(isinstance(cell, NumberCell) for _, cell in column_cells(book, "에너지_C3", "A"))


def test_derived_cells_are_loaded_with_master_follower_and_cached_value() -> None:
    """원화 열 셋: 으뜸 칸은 식 글자, 딸린 칸은 식 글자 없이 으뜸 칸의 주소와 그 식, 둘 다 저장된 값."""
    book = loaded()
    derived = {name: [entry for row in rows_of(book, name) for entry in row.derived] for name in EXPECTED}
    assert {name: len(entries) for name, entries in derived.items() if entries} == {
        "구매_USEPA": 570,
        "운송_Spend": 51,
        "출장_Spend": 33,
    }
    masters = {name: sum(1 for entry in entries if entry.formula is not None) for name, entries in derived.items()}
    assert (masters["구매_USEPA"], masters["운송_Spend"], masters["출장_Spend"]) == (18, 3, 3)
    header = next(column.header for column in FACTOR_SHEETS[6].columns if column.letter == "I")
    assert row_at(book, "구매_USEPA", 36).derived[0] == DerivedEntry(
        "I", header, "F36/9.1", "I36", "F36/9.1", NumberCell("9.70365", "9.70365")
    )
    follower = row_at(book, "구매_USEPA", 37).derived[0]
    # 딸린 칸의 식을 지어내지 않는다: formula 는 None, master_formula 는 으뜸 칸의 글자 그대로(F37 로 밀지 않는다).
    assert follower == DerivedEntry("I", header, None, "I36", "F36/9.1", NumberCell("9.70375", "9.70375"))
    assert all(entry.cached is not None for entries in derived.values() for entry in entries)
    assert [f.name for f in fields(DerivedEntry)] == [
        "column",
        "header",
        "formula",
        "master",
        "master_formula",
        "cached",
    ]


def test_values_carry_the_header_the_unit_text_and_the_unit_cell_as_written() -> None:
    book = loaded()
    first = value_at(book, "에너지", 5, "I")
    assert (first.header, first.unit, first.unit_cell) == ("CO2eq\n(kgCO2eq/단위) ★", "(kgCO2eq/단위) ★", TextCell("L"))
    assert value_at(book, "전력_국가별", 3, "C").unit is None
    assert value_at(book, "전력_국가별", 3, "C").unit_cell == TextCell("kgCO2eq/kWh")
    assert value_at(book, "운송", 3, "E").unit_cell is None  # 단위 열이 없는 시트
    # 단위를 접지 않는다: 같은 뜻의 두 표기가 그대로 남는다.
    assert value_at(book, "구매_USEPA", 4, "F").unit == "(kgCO2eq/USD)"
    assert value_at(book, "운송_Spend", 4, "F").unit == "(kgCO2e/USD)"


def test_the_unit_text_of_every_value_and_derived_column_is_part_of_its_header() -> None:
    columns = [column for shape in FACTOR_SHEETS for column in shape.columns]
    with_unit = [column for column in columns if column.unit is not None]
    assert len(with_unit) == 24  # 값 열 15(머리글에 단위가 없는 하나를 뺀 것) + 파생 열 9
    assert [c.letter for c in with_unit if c.unit is not None and c.unit not in c.header] == []
    assert [column.header for column in columns if column.role == "value" and column.unit is None] == ["배출계수"]


def test_note_rows_and_title_rows_are_kept_with_their_cells() -> None:
    book = loaded()
    assert book.notes == (Note("에너지", "A19", TextCell("가상 출처 각주")),)
    energy_titles = {note.cell for note in book.titles if note.sheet == "에너지"}
    assert energy_titles == {"A1", "A2", "A3", "E3", "G3", *(f"{letter}4" for letter in "ABCDEFGHI")}


def test_one_different_header_letter_refuses_only_that_sheet() -> None:
    """머리글이 글자 하나만 달라도 그 시트는 적재하지 않는다(추측해서 맞추지 않는다). 다른 시트는 계속."""
    workbook = with_cell(sample_factor_book(), "운송", "E2", text("배출계수\n(kgCO2e/ton·km)"))
    book = load_factor_book(workbook)
    assert book.problems == (HeaderMismatch("운송", "E2", "배출계수\n(kgCO2eq/ton·km)", "배출계수\n(kgCO2e/ton·km)"),)
    assert rows_of(book, "운송") == []
    assert "운송" not in {account.sheet for account in book.accounts}
    assert len(book.rows) == 403 - 6
    assert len(rows_of(book, "출장_통근")) == 11


def test_missing_group_headers_extra_header_cells_and_index_headers_are_mismatches() -> None:
    workbook = with_cell(sample_factor_book(), "에너지", "E3", None)
    workbook = with_cell(workbook, "출장_통근", "H2", text("가상 새 열"))
    workbook = with_cell(workbook, "목록", "C5", number("9"))
    book = load_factor_book(workbook)
    assert book.problems == (
        HeaderMismatch("목록", "C5", INDEX_SHEET.book_header, None),
        HeaderMismatch("에너지", "E3", "← 발열량 기준", None),
        HeaderMismatch("출장_통근", "H2", None, "가상 새 열"),
    )
    assert book.sheet_links == ()
    assert {row.sheet for row in book.rows} == set(EXPECTED) - {"에너지", "출장_통근"}


def test_unknown_and_missing_sheets_are_reported() -> None:
    workbook = sample_factor_book()
    renamed = replace(sheet_named(workbook, "운송"), name="가상 시트")
    changed = Workbook(tuple(renamed if sheet.name == "운송" else sheet for sheet in workbook.sheets), ())
    book = load_factor_book(changed)
    assert book.problems == (MissingSheet("운송"), UnknownSheet("가상 시트"))
    assert len(book.rows) == 403 - 6


def test_two_rows_with_the_same_name_in_different_sheets_are_both_loaded_unchanged() -> None:
    """같은 이름의 줄(시트가 다르고 단위·값이 다른)을 합치지도 고르지도 않는다."""
    book = loaded()
    name = "가상에너지01"
    left = next(row for row in rows_of(book, "에너지") if TextCell(name) in [entry.cell for entry in row.labels])
    right = next(row for row in rows_of(book, "에너지_C3") if TextCell(name) in [entry.cell for entry in row.labels])
    assert (left.row, right.row) == (5, 4)
    assert (left.values[-1].unit_cell, right.values[0].unit_cell) == (TextCell("L"), TextCell("kg"))
    assert (left.values[-1].content, right.values[0].content) == (number("9.10055"), number("9.20041"))
    # 같은 시트 안에서 같은 짝이 두 줄인 것도 둘 다 있다.
    pairs = [tuple(entry.cell for entry in row.labels[:2]) for row in rows_of(book, "폐기물_C5")]
    assert len(pairs) == 65 and len(set(pairs)) == 63


def test_the_index_sheet_becomes_links_and_nothing_is_dropped() -> None:
    book = loaded()
    assert [link.row for link in book.sheet_links] == list(range(6, 27))
    assert all(isinstance(link.template_tab, TextCell) and link.extras == () for link in book.sheet_links)
    workbook = with_cell(sample_factor_book(), "목록", "D7", text("가상 덧붙인 칸"))
    changed = load_factor_book(workbook)
    assert changed.sheet_links[1].extras == (ExtraEntry("D", TextCell("가상 덧붙인 칸")),)
    assert [problem for problem in changed.problems if isinstance(problem, Unaccounted)] == []


def test_the_result_has_no_field_that_picks_or_converts() -> None:
    """적재 결과의 꼴에 「고른 값」·「환산값」·「정본」 칸이 없다."""
    assert [f.name for f in fields(FactorRow)] == ["sheet", "row", "labels", "values", "derived", "extras"]
    assert [f.name for f in fields(ValueEntry)] == ["column", "header", "unit", "unit_cell", "content"]
    assert [f.name for f in fields(SheetAccount)] == [
        "sheet",
        "total",
        "title_header",
        "label",
        "value",
        "derived",
        "extra",
        "note",
        "link",
        "unaccounted",
    ]


def test_an_empty_sheet_loads_as_a_header_mismatch_not_an_exception() -> None:
    workbook = with_sheet(sample_factor_book(), Sheet("운송", {}, (), ()))
    problems = load_factor_book(workbook).problems
    assert len(problems) == 6 and all(isinstance(problem, HeaderMismatch) for problem in problems)
