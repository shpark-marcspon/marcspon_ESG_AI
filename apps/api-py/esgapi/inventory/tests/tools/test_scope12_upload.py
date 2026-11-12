"""Scope 1·2 일괄업로드 양식 읽기(`tools/scope12_upload.py` — 밴드 S12b-2 ①). 순수 층.

시험 파일은 `build_template` 으로 짓거나(왕복) 손으로 적은 XML 조각으로 짓는다(칸 갈래). 값은 모두 지어낸 것이다.
"""

import ast
import io
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from openpyxl import load_workbook

from esgapi.inventory.tests.s3sheets_support import sheet_xml, xlsx_from_parts, zip_bytes
from esgapi.inventory.tools import scope12_upload as upload
from esgapi.inventory.tools import xlsx_reader
from esgapi.inventory.tools.scope3_sheets.grid import Workbook, column_letters, merge_anchor
from esgapi.inventory.tools.scope12_upload import (
    BAD_ID,
    FORMULA,
    NOT_TEMPLATE,
    NOT_XLSX,
    SAME_LINE,
    TOO_LARGE,
    LineProblem,
    UploadBook,
    UploadProblem,
    read_upload,
)
from esgapi.inventory.tools.scope12_xlsx import (
    PERIODS,
    TEMPLATE_SHEETS,
    TemplateBook,
    TemplateLine,
    build_template,
    template_columns,
)

YEAR = 2031
PATH = ("가상 범위", "가상 유형", "가상 활동", "가상 시설")


def template(*lines: tuple[int, str, str, str]) -> bytes:
    made = [TemplateLine(node, PATH, site, period, unit) for node, site, period, unit in lines]
    return build_template(TemplateBook(YEAR, made))


TWO_SITES = ((101, "가상 가", "month", "kg"), (101, "가상 나", "quarter", "kg"), (102, "가상 가", "year", "L"))


def filled(
    values: dict[tuple[str, str], int | float | str], lines: tuple[tuple[int, str, str, str], ...] = TWO_SITES
) -> bytes:
    """양식에 openpyxl 로 값을 넣어 저장한 바이트. 열쇠 = (시트, 칸)."""
    book = load_workbook(io.BytesIO(template(*lines)))
    for (sheet, address), value in values.items():
        book[sheet][address] = value
    saved = io.BytesIO()
    book.save(saved)
    return saved.getvalue()


def text_cell(address: str, text: str) -> str:
    return f'<c r="{address}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'


def head_row(period: str, year: int = YEAR) -> str:
    cells = (text_cell(f"{column_letters(i)}1", head) for i, head in enumerate(template_columns(year, period), start=1))
    return f'<row r="1">{"".join(cells)}</row>'


def hand(rows: str = "", *, sheet: str = "월", after: str = "") -> bytes:
    """손으로 적은 양식: 머리는 맞고, 시트 `sheet` 의 2행부터 `rows`."""
    parts: dict[str, bytes] = {}
    for name, period in zip(TEMPLATE_SHEETS, PERIODS, strict=True):
        parts[name] = sheet_xml(head_row(period) + (rows if name == sheet else ""), after if name == sheet else "")
    return zip_bytes(xlsx_from_parts(parts))


def line_row(value_cell: str, *, row: int = 2, node: str = "101") -> str:
    """월 시트의 한 줄: A·F·H + 값 칸."""
    site, unit = text_cell(f"F{row}", "가상 가"), text_cell(f"H{row}", "kg")
    return f'<row r="{row}"><c r="A{row}"><v>{node}</v></c>{site}{unit}{value_cell}</row>'


def read(data: bytes) -> UploadBook:
    found = read_upload(data, YEAR)
    assert isinstance(found, UploadBook), found
    return found


def refused(data: bytes) -> str:
    found = read_upload(data, YEAR)
    assert isinstance(found, UploadProblem), found
    return found.message


# ── 왕복 ──


def test_an_untouched_template_has_no_lines() -> None:
    assert read(template(*TWO_SITES)) == UploadBook((), ())


def test_filled_cells_come_back_with_line_and_address() -> None:
    book = read(filled({("월", "I2"): 12, ("월", "T2"): 0.5, ("분기", "J3"): "7.5", ("년도", "K4"): 3}))
    heads = [(ln.sheet, ln.period, ln.row, ln.address, ln.node_id, ln.site, ln.unit) for ln in book.lines]
    assert heads == [
        ("년도", "year", 4, "년도!A4", 102, "가상 가", "L"),
        ("분기", "quarter", 3, "분기!A3", 101, "가상 나", "kg"),
        ("월", "month", 2, "월!A2", 101, "가상 가", "kg"),
    ]  # fmt: skip
    assert [[(c.label, c.address, c.text) for c in line.cells] for line in book.lines] == [
        [(f"{YEAR}년", "년도!K4", "3")],
        [("2분기", "분기!J3", "7.5")],
        [("1월", "월!I2", "12"), ("12월", "월!T2", "0.5")],
    ]
    assert book.problems == ()


def test_the_year_sheet_keeps_every_year_column_for_the_caller_to_judge() -> None:
    book = read(filled({("년도", "I4"): 1, ("년도", "J4"): 2, ("년도", "K4"): 3}))
    assert [cell.label for cell in book.lines[0].cells] == [f"{YEAR - 2}년", f"{YEAR - 1}년", f"{YEAR}년"]


def test_the_id_of_a_merged_line_comes_from_the_first_line_of_the_merge() -> None:
    """A 는 같은 잎의 줄들에 병합돼 딸린 3행에는 칸이 없다."""
    data = filled({("월", "I3"): 1})
    (sheet,) = [s for s in _workbook(data).sheets if s.name == "월"]
    assert "A3" not in sheet.cells and "A2:A3" in sheet.merges
    assert read(data).lines[0].node_id == 101


def _workbook(data: bytes) -> Workbook:
    found = xlsx_reader.read_workbook(data)
    assert isinstance(found, Workbook), found
    return found


def test_spans_answer_like_merge_anchor_on_every_row() -> None:
    merged = [(100 + i // 3, f"가상 {i % 3}", "month", "kg") for i in range(12)]
    lines = (*merged, (200, "가상 외톨이", "year", "L"))
    for sheet in _workbook(template(*lines)).sheets:
        spans = upload._spans(sheet)  # pyright: ignore[reportPrivateUsage]
        assert spans is not None
        for row in range(1, 20):
            assert f"A{spans.anchor_of(row)}" == merge_anchor(sheet, f"A{row}")


def test_a_line_without_an_id_after_unmerging_is_a_line_problem() -> None:
    data = hand(f'<row r="2">{text_cell("F2", "가상 가")}<c r="I2"><v>1</v></c></row>')
    assert read(data) == UploadBook((), (LineProblem("월!A2", BAD_ID),))


@pytest.mark.parametrize(
    "cell", ['<c r="A2"><v>1.5</v></c>', '<c r="A2"><v>-1</v></c>', text_cell("A2", "가상"), text_cell("A2", "１０１")]
)
def test_an_id_that_is_not_a_whole_number_is_a_line_problem(cell: str) -> None:
    data = hand(f'<row r="2">{cell}<c r="I2"><v>1</v></c></row>')
    assert read(data).problems == (LineProblem("월!A2", BAD_ID),)


def test_the_same_leaf_and_site_twice_on_a_sheet_is_a_line_problem_on_the_second() -> None:
    cell2, cell3 = '<c r="I2"><v>1</v></c>', '<c r="I3"><v>2</v></c>'
    book = read(hand(line_row(cell2) + line_row(cell3, row=3)))
    assert [line.row for line in book.lines] == [2]
    assert book.problems == (LineProblem("월!A3", SAME_LINE),)


def test_two_lines_of_one_leaf_with_other_sites_are_two_lines() -> None:
    book = read(filled({("월", "I2"): 1, ("월", "I3"): 2}))
    assert [(line.node_id, line.site) for line in book.lines] == [(101, "가상 가"), (101, "가상 나")]


# ── 파일 오류 ──


def test_empty_and_not_xlsx_bytes_are_file_problems() -> None:
    assert refused(b"") == NOT_XLSX
    assert refused(b'{"name": 1}') == NOT_XLSX
    assert refused(zip_bytes({"note.txt": b"1"})) == NOT_XLSX


def test_a_missing_or_renamed_or_extra_sheet_is_not_the_template() -> None:
    heads = {name: sheet_xml(head_row(period)) for name, period in zip(TEMPLATE_SHEETS, PERIODS, strict=True)}
    assert isinstance(read_upload(zip_bytes(xlsx_from_parts(heads)), YEAR), UploadBook)  # 분모: 맞는 파일은 지난다
    missing = {name: xml for name, xml in heads.items() if name != "분기"}
    renamed = {("월별" if name == "월" else name): xml for name, xml in heads.items()}
    extra = {**heads, "가상": sheet_xml("")}
    for sheets in (missing, renamed, extra):
        assert refused(zip_bytes(xlsx_from_parts(sheets))) == NOT_TEMPLATE


def test_another_years_template_is_not_the_template() -> None:
    assert isinstance(read_upload(template(*TWO_SITES), YEAR), UploadBook)
    assert refused(build_template(TemplateBook(YEAR + 1, []))) == NOT_TEMPLATE


@pytest.mark.parametrize("address", ["H1", "I1", "T1"])
def test_one_character_off_in_a_head_is_not_the_template(address: str) -> None:
    assert refused(filled({("월", address): "가상 머리"})) == NOT_TEMPLATE


def test_a_head_past_the_last_column_is_not_the_template() -> None:
    assert refused(filled({("월", "U1"): "가상 머리"})) == NOT_TEMPLATE


def test_a_note_right_of_the_last_head_is_not_read() -> None:
    assert read(filled({("월", "U2"): "가상 메모"})) == UploadBook((), ())


@pytest.mark.parametrize("second", ["A3:A5", "A4:A5"])
def test_overlapping_id_merges_are_not_the_template(second: str) -> None:
    merges = f'<mergeCells count="2"><mergeCell ref="A2:A4"/><mergeCell ref="{second}"/></mergeCells>'
    assert refused(hand(after=merges)) == NOT_TEMPLATE


def test_merges_that_touch_without_overlapping_are_fine() -> None:
    merges = '<mergeCells count="2"><mergeCell ref="A2:A3"/><mergeCell ref="A4:A5"/></mergeCells>'
    rows = line_row('<c r="I2"><v>1</v></c>') + line_row('<c r="I4"><v>2</v></c>', row=4, node="102")
    book = read(hand(rows, after=merges))
    assert [line.node_id for line in book.lines] == [101, 102]


def test_a_merge_that_is_not_a_range_is_not_the_template() -> None:
    assert refused(hand(after='<mergeCells count="1"><mergeCell ref="가상"/></mergeCells>')) == NOT_TEMPLATE


def test_a_cell_the_reader_refuses_is_named_by_address_without_its_value() -> None:
    message = refused(hand(line_row('<c r="I2" t="e"><v>#N/A</v></c>')))
    assert "I2" in message
    assert "#N/A" not in message and "xl/" not in message


def test_a_number_too_long_for_a_decimal_is_named_by_address_too() -> None:
    message = refused(hand(line_row(f'<c r="I2"><v>{"9" * 200}</v></c>')))
    assert "I2" in message
    assert "999" not in message


@pytest.mark.parametrize(
    ("limit", "value"),
    [("MAX_CELLS", 1), ("MAX_MERGES", 0), ("MAX_XML_DEPTH", 2), ("MAX_XML_ELEMENTS", 5)],
)
def test_files_over_the_reader_limits_are_a_file_problem_not_an_exception(
    limit: str, value: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = filled({("월", "I2"): 1})
    assert isinstance(read_upload(data, YEAR), UploadBook)
    monkeypatch.setattr(xlsx_reader, limit, value)
    assert refused(data) == TOO_LARGE


def test_more_filled_lines_than_the_limit_is_a_file_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    data = filled({("월", "I2"): 1, ("월", "I3"): 2, ("월", "I4"): 3})
    monkeypatch.setattr(upload, "UPLOAD_LINES_MAX", 3)
    assert isinstance(read_upload(data, YEAR), UploadBook)
    monkeypatch.setattr(upload, "UPLOAD_LINES_MAX", 2)
    assert refused(data) == upload.TOO_MANY_LINES
    assert "나눠서" in upload.TOO_MANY_LINES


def test_the_line_limit_counts_lines_not_formula_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    formulas = '<c r="I2"><f>1+1</f></c><c r="J2"><f>1+1</f></c><c r="K2"><f>1+1</f></c>'
    monkeypatch.setattr(upload, "UPLOAD_LINES_MAX", 1)
    assert read(hand(line_row(formulas))).problems != ()


@given(st.binary(max_size=200))
@settings(max_examples=50, deadline=None)
def test_any_bytes_get_an_answer_not_an_exception(data: bytes) -> None:
    assert isinstance(read_upload(data, YEAR), UploadProblem)


# ── 칸 글자 ──


@pytest.mark.parametrize(
    ("cell", "text"),
    [
        ('<c r="I2"><v>12</v></c>', "12"),
        ('<c r="I2"><v>0.1</v></c>', "0.1"),
        ('<c r="I2"><v>1e-07</v></c>', "0.0000001"),
        ('<c r="I2"><v>0.30000000000000004</v></c>', "0.30000000000000004"),
        ('<c r="I2"><v>1234.5670000000001</v></c>', "1234.567"),
        ('<c r="I2"><v>-1</v></c>', "-1"),
        ('<c r="I2" t="b"><v>1</v></c>', "TRUE"),
        ('<c r="I2" t="b"><v>0</v></c>', "FALSE"),
        (text_cell("I2", "  3.5 "), "3.5"),
        (text_cell("I2", "1,000"), "1,000"),
        (text_cell("I2", "1e3"), "1e3"),
        (text_cell("I2", "NaN"), "NaN"),
    ],
)
def test_cell_text_is_the_shortest_decimal_or_the_stripped_text(cell: str, text: str) -> None:
    (line,) = read(hand(line_row(cell))).lines
    assert [c.text for c in line.cells] == [text]


@pytest.mark.parametrize("cell", [text_cell("I2", "   "), text_cell("I2", ""), '<c r="I2" s="1"/>'])
def test_blank_cells_do_not_make_a_line(cell: str) -> None:
    assert read(hand(line_row(cell))) == UploadBook((), ())


def test_a_formula_cell_is_a_cell_problem_even_with_a_stored_value() -> None:
    cells = '<c r="I2"><f>1+1</f><v>2</v></c><c r="J2"><v>5</v></c>'
    book = read(hand(line_row(cells)))
    assert book.problems == (LineProblem("월!I2", FORMULA),)
    assert [c.address for c in book.lines[0].cells] == ["월!J2"]


def test_a_shared_formula_follower_is_a_formula_too() -> None:
    cells = '<c r="I2"><f t="shared" ref="I2:J2" si="0">1+1</f><v>2</v></c><c r="J2"><f t="shared" si="0"/><v>2</v></c>'
    assert read(hand(line_row(cells))).problems == (LineProblem("월!I2", FORMULA), LineProblem("월!J2", FORMULA))


# ── 일의 양 · 순수 ──


def test_merges_are_parsed_once_per_sheet_however_many_lines_there_are(monkeypatch: pytest.MonkeyPatch) -> None:
    """최악 파일의 시간 단언: 벽시계 대신 일의 양. 병합 파싱은 병합 수 그대로고 줄 수에 곱해지지 않는다."""
    count = 2000
    merges = "".join(f'<mergeCell ref="A{row}:A{row + 1}"/>' for row in range(1000, 1000 + 2 * count, 2))
    rows = "".join(line_row(f'<c r="I{row}"><v>1</v></c>', row=row, node=str(row)) for row in range(2, 202))
    data = hand(rows, after=f'<mergeCells count="{count}">{merges}</mergeCells>')
    calls = 0
    real = upload.parse_range

    def counted(text: str) -> object:
        nonlocal calls
        calls += 1
        return real(text)

    monkeypatch.setattr(upload, "parse_range", counted)
    assert len(read(data).lines) == 200
    assert calls == count


def test_the_tool_imports_only_the_standard_library_and_tools() -> None:
    tree = ast.parse(Path(upload.__file__).read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    modules |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert modules == {
        "bisect",
        "dataclasses",
        "itertools",
        "typing",
        "esgapi.inventory.tools.scope12_xlsx",
        "esgapi.inventory.tools.scope3_sheets.grid",
        "esgapi.inventory.tools.xlsx_reader",
    }
