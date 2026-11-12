"""Scope 1·2 엑셀 두 벌의 짓기(`tools/scope12_xlsx.py` — 밴드 S12b-1 ①). 순수 층.

확정판(MARC-ENT-472) 구조는 아래 글자 목록으로만 적는다 — 받은 파일·견본 값 0. 값은 모두 지어낸 것이다.
"""

import ast
import hashlib
import io
import re
import zipfile
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from esgapi.inventory.tools import scope12_xlsx as x
from esgapi.inventory.tools.scope12_xlsx import (
    DetailLeaf,
    DetailRow,
    ExportBook,
    GasCell,
    SheetCells,
    SummarySite,
    TemplateBook,
    TemplateLine,
    YearlyLine,
)

YEAR = 2031
PATH_A = ("Scope 1", "가상 연소", "가상 고체 연소", "가상 보일러")
PATH_B = ("Scope 2", "가상 간접", "가상 전력", "가상 수전")

# ── 확정판 구조(글자) ──
TEMPLATE_SHEETS = ["년도", "분기", "월"]
TEMPLATE_HEAD = [
    "ID(수정X)", "범위(수정X)", "배출원 유형(수정X)", "배출활동(수정X)", "자산/시설명(수정X)",
    "사업장(수정X)", "입력 주기(수정X)", "단위(수정X)",
]  # fmt: skip
EXPORT_SHEETS = ["온실가스 배출량", "연도별 배출량 데이터", "상세 데이터(년도)", "상세 데이터(분기)", "상세 데이터(월)"]
SUMMARY_HEAD = ["사업장명", "단위", "Scope 1", "Scope 2", "Scope 1+2"]
YEARLY_HEAD = [
    "ID", "범위", "배출원 유형", "배출활동", "자산/시설명", "단위", "2029년", "2030년", "2031년", "메모", "추정치",
]  # fmt: skip
DETAIL_FRONT = ["ID", "범위", "배출원 유형", "배출활동", "자산/시설명", "사업장", "상세 시설명", "재생에너지 사용 여부"]
GASES = ["CO2", "CH4", "N2O", "HFCs", "PFCs", "SF6", "NF3"]
QUARTERS = ["1분기", "2분기", "3분기", "4분기"]
MONTHS = [f"{m}월" for m in range(1, 13)]


def _line(node_id: int, site: str, period: str = "month", path: tuple[str, ...] = PATH_A) -> TemplateLine:
    return TemplateLine(node_id=node_id, path=path, site_name=site, period=period, unit="kg")


def _template() -> TemplateBook:
    return TemplateBook(
        year=YEAR,
        lines=[
            _line(11, "가상 사업장 가"),
            _line(11, "가상 사업장 나", "quarter"),
            _line(12, "가상 사업장 가", "year", PATH_B),
        ],
    )


def _open(data: bytes) -> list[Worksheet]:
    return list(load_workbook(io.BytesIO(data)).worksheets)


def _row(sheet: Worksheet, row: int) -> list[object]:
    return [cell.value for cell in sheet[row]]


def _cells(width: int, emission: str | None, amount: str | None) -> SheetCells:
    e = None if emission is None else Decimal(emission)
    a = None if amount is None else Decimal(amount)
    return SheetCells(emissions=(e,) * width, amounts=(a,) * width)


def _detail_row(
    site: str = "가상 사업장 가", *, na: bool = False, problem: str | None = None, ncv: str | None = None
) -> DetailRow:
    return DetailRow(
        site_name=site,
        detail_name="가상 보일러 1호",
        unit="kg",
        na=na,
        problem=problem,
        total=Decimal("7.5"),
        amount_total=Decimal("30"),
        cells={"year": _cells(1, "7.5", "30"), "quarter": _cells(4, "1.25", "5"), "month": _cells(12, "0.5", "2")},
        ncv=None if ncv is None else Decimal(ncv),
        ncv_unit=None if ncv is None else "TJ",
        gases=(GasCell(Decimal("2.5"), Decimal("1")), *(GasCell(None, None),) * 6),
        source="가상 출처",
    )


BOOK = ExportBook(
    year=YEAR,
    decimals=2,
    roots=("Scope 1", "Scope 2"),
    whole=True,
    sites=[SummarySite("가상 사업장 가", (Decimal("10.5"), Decimal("2"))), SummarySite("가상 사업장 나", (None, None))],
    yearly=[
        YearlyLine(11, PATH_A, {2029: None, 2030: Decimal("1"), 2031: Decimal("10.5")}, "가상 메모", True),
        YearlyLine(12, PATH_B, {2029: None, 2030: None, 2031: Decimal("2")}, "", False),
    ],
    leaves=[
        DetailLeaf(11, PATH_A, [_detail_row(), _detail_row("가상 사업장 나", ncv="0.5")]),
        DetailLeaf(12, PATH_B, [_detail_row(na=True)]),
    ],
)


# ── 3-1 양식 ──


def test_template_sheets_heads_and_lines() -> None:
    sheets = _open(x.build_template(_template()))
    assert [s.title for s in sheets] == TEMPLATE_SHEETS
    year, quarter, month = sheets
    assert _row(year, 1) == [*TEMPLATE_HEAD, "2029년", "2030년", "2031년"]
    assert _row(quarter, 1) == [*TEMPLATE_HEAD, *QUARTERS]
    assert _row(month, 1) == [*TEMPLATE_HEAD, *MONTHS]
    for sheet in sheets:  # 세 시트 다 같은 줄(G2) · 값 칸 빔
        assert sheet.max_row == 4
        assert [sheet.cell(r, 1).value for r in (2, 3, 4)] == [11, None, 12]  # 병합 칸은 첫 칸에만 값
        assert [sheet.cell(r, 6).value for r in (2, 3, 4)] == ["가상 사업장 가", "가상 사업장 나", "가상 사업장 가"]
        assert [sheet.cell(r, 7).value for r in (2, 3, 4)] == ["월", "분기", "년도"]
        assert [sheet.cell(r, 8).value for r in (2, 3, 4)] == ["kg"] * 3
        assert _row(sheet, 4)[1:5] == list(PATH_B)
        assert all(cell.value is None for r in (2, 3, 4) for cell in sheet[r][8:])


def test_template_merges_a_to_e_over_one_leafs_site_lines() -> None:
    for sheet in _open(x.build_template(_template())):
        assert sorted(str(r) for r in sheet.merged_cells.ranges) == ["A2:A3", "B2:B3", "C2:C3", "D2:D3", "E2:E3"]


def test_template_with_one_site_has_no_merge() -> None:
    book = TemplateBook(YEAR, [_line(11, "가상 사업장 가")])
    assert all(not s.merged_cells.ranges for s in _open(x.build_template(book)))


def test_template_without_lines_is_heads_only() -> None:
    assert all(s.max_row == 1 for s in _open(x.build_template(TemplateBook(YEAR, []))))


# ── 3-1 데이터 ──


def test_export_sheet_order() -> None:
    assert [s.title for s in _open(x.build_export(BOOK))] == EXPORT_SHEETS


def test_export_summary_sheet() -> None:
    summary = _open(x.build_export(BOOK))[0]
    assert _row(summary, 1) == SUMMARY_HEAD
    assert _row(summary, 2) == ["총계", "tCO2-eq", 10.5, 2, 12.5]
    assert _row(summary, 3) == ["가상 사업장 가", "tCO2-eq", 10.5, 2, 12.5]
    assert _row(summary, 4) == ["가상 사업장 나", "tCO2-eq", None, None, None]
    assert summary.cell(3, 3).number_format == "0.00"


def test_export_summary_one_root() -> None:
    sites = [SummarySite("가상 사업장 가", (Decimal("2"),))]
    summary = _open(x.build_export(replace(BOOK, roots=("Scope 2",), whole=False, sites=sites)))[0]
    assert _row(summary, 1) == ["사업장명", "단위", "Scope 2"]  # 끝 열 「Scope 1+2」 0
    assert _row(summary, 3) == ["가상 사업장 가", "tCO2-eq", 2]


def test_export_summary_columns_are_the_roots_and_the_last_is_all_of_them() -> None:
    sites = [SummarySite("가상 사업장 가", (Decimal("1"), Decimal("2"), Decimal("4")))]
    summary = _open(x.build_export(replace(BOOK, roots=("Scope 1", "가상 이름 바뀐 뿌리", "Scope 2"), sites=sites)))[0]
    assert _row(summary, 1) == ["사업장명", "단위", "Scope 1", "가상 이름 바뀐 뿌리", "Scope 2", "Scope 1+2"]
    assert _row(summary, 2) == ["총계", "tCO2-eq", 1, 2, 4, 7]


def test_export_yearly_sheet() -> None:
    yearly = _open(x.build_export(BOOK))[1]
    assert _row(yearly, 1) == YEARLY_HEAD
    assert _row(yearly, 2) == [11, *PATH_A, "tCO2-eq", None, 1, 10.5, "가상 메모", "Y"]
    assert _row(yearly, 3) == [12, *PATH_B, "tCO2-eq", None, None, 2, None, None]


def _detail_heads(columns: list[str], total: bool) -> tuple[list[object], list[object]]:
    group = ["단위", *columns, *(["총계"] if total else [])]
    pad: list[object] = [None] * (len(group) - 1)
    first: list[object] = [
        *DETAIL_FRONT, "온실가스 배출량 데이터", *pad, "투입량 데이터", *pad, "순발열량", "순발열량 단위",
        "온실가스별 배출계수", *[None] * 6, "온실가스별 GWP", *[None] * 6, "배출계수 출처", "산식",
    ]  # fmt: skip
    second: list[object] = [*[None] * 8, *group, *group, None, None, *GASES, *GASES, None, None]
    return first, second


@pytest.mark.parametrize(
    ("index", "columns", "total"),
    [(2, ["2031년"], False), (3, QUARTERS, True), (4, MONTHS, True)],
)
def test_export_detail_heads_and_merges(index: int, columns: list[str], total: bool) -> None:
    sheet = _open(x.build_export(BOOK))[index]
    first, second = _detail_heads(columns, total)
    assert _row(sheet, 1) == first
    assert _row(sheet, 2) == second
    group = 1 + len(columns) + (1 if total else 0)
    singles = [*range(1, 9), 9 + 2 * group, 10 + 2 * group, 25 + 2 * group, 26 + 2 * group]
    spans = [(9, group), (9 + group, group), (11 + 2 * group, 7), (18 + 2 * group, 7)]
    letter = get_column_letter
    want = {f"{letter(c)}1:{letter(c)}2" for c in singles}
    want |= {f"{letter(s)}1:{letter(s + n - 1)}1" for s, n in spans}
    want |= {f"{c}3:{c}5" for c in "ABCDE"}  # 잎 11: 머리 줄 + 행 둘
    want |= {f"{c}6:{c}7" for c in "ABCDE"}  # 잎 12: 머리 줄 + 행 하나
    assert {str(r) for r in sheet.merged_cells.ranges} == want


def test_export_detail_rows_quarter() -> None:
    sheet = _open(x.build_export(BOOK))[3]
    head = _row(sheet, 3)
    assert head[:5] == [11, *PATH_A]
    assert head[8:14] == ["tCO2-eq", 2.5, 2.5, 2.5, 2.5, 15]  # 배출량 칸 = 행 합 · 총계 = 저장 셈 합
    assert head[14:20] == ["kg", 10, 10, 10, 10, 60]  # 단위가 모두 같아 투입량도 합
    row = _row(sheet, 4)
    assert row[5:8] == ["가상 사업장 가", "가상 보일러 1호", None]  # 재생에너지 사용 여부 = 빈 칸
    assert row[8:14] == ["tCO2-eq", 1.25, 1.25, 1.25, 1.25, 7.5]
    assert row[14:20] == ["kg", 5, 5, 5, 5, 30]
    assert row[20:22] == [None, None]
    assert row[22:29] == [2.5, None, None, None, None, None, None]
    assert row[29:36] == [1, None, None, None, None, None, None]
    assert row[36:] == ["가상 출처", "활동량 × Σ(가스별 배출계수 × GWP) × 단위 환산"]
    ncv = _row(sheet, 5)
    assert ncv[20:22] == [0.5, "TJ"]
    assert ncv[37] == "활동량 × 순발열량 × Σ(가스별 배출계수 × GWP) × 단위 환산"


def test_export_detail_na_row_and_year_sheet() -> None:
    sheets = _open(x.build_export(BOOK))
    quarter = _row(sheets[3], 7)  # 잎 12 의 N/A 행
    assert quarter[9:14] == [None, None, None, None, "N/A"]
    assert quarter[15:20] == [None, None, None, None, "N/A"]
    leaf = _row(sheets[3], 6)
    assert leaf[9:14] == [None] * 5  # N/A 만 있는 잎 머리 = 빈 칸
    year = sheets[2]
    assert _row(year, 4)[8:12] == ["tCO2-eq", 7.5, "kg", 30]  # 년도 시트: Y 한 칸 · 총계 열 0(G3)
    assert _row(year, 7)[8:12] == ["tCO2-eq", "N/A", "kg", "N/A"]


def test_export_detail_problem_row() -> None:
    book = replace(BOOK, leaves=[DetailLeaf(11, PATH_A, [_detail_row(problem="unit_conversion_missing")])])
    row = _row(_open(x.build_export(book))[3], 4)
    assert row[9:14] == [None, None, None, None, "unit_conversion_missing"]
    assert row[15:20] == [5, 5, 5, 5, 30]  # 투입량은 그대로


def test_export_input_sum_needs_one_unit() -> None:
    other = replace(_detail_row(), unit="t")
    book = replace(BOOK, leaves=[DetailLeaf(11, PATH_A, [_detail_row(), other])])
    head = _row(_open(x.build_export(book))[3], 3)
    assert head[14:20] == [None] * 6


def test_export_without_rows_is_heads_and_leaf_lines() -> None:
    book = replace(BOOK, leaves=[DetailLeaf(11, PATH_A, [])], yearly=[], sites=[])
    sheets = _open(x.build_export(book))
    assert sheets[3].max_row == 3
    assert _row(sheets[3], 3)[:5] == [11, *PATH_A]


# ── 3-1 칸·결정성·안전 ──


def test_fold_sums_finer_slots_and_blanks_coarser() -> None:
    months = {f"{YEAR}-{m:02d}": Decimal(m) for m in range(1, 13)}
    assert x.fold(months, "quarter") == (Decimal(6), Decimal(15), Decimal(24), Decimal(33))
    assert x.fold(months, "year") == (Decimal(78),)
    assert x.fold(months, "month") == tuple(Decimal(m) for m in range(1, 13))
    quarters = {f"{YEAR}-Q{q}": Decimal(q) for q in range(1, 5)}
    assert x.fold(quarters, "month") == (None,) * 12
    assert x.fold(quarters, "year") == (Decimal(10),)
    assert x.fold({str(YEAR): Decimal(3)}, "quarter") == (None,) * 4
    assert x.fold({f"{YEAR}-01": None, f"{YEAR}-02": Decimal(1)}, "quarter") == (Decimal(1), None, None, None)


def test_same_input_same_bytes() -> None:
    for build in (lambda: x.build_template(_template()), lambda: x.build_export(BOOK)):
        first, second = build(), build()
        assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            assert {i.date_time for i in archive.infolist()} == {(1980, 1, 1, 0, 0, 0)}
            core = archive.read("docProps/core.xml")
            assert core.count(b"1980-01-01T00:00:00Z") == 2


def _sheet_xml(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return "".join(archive.read(n).decode() for n in archive.namelist() if n.startswith("xl/worksheets/"))


def test_decimal_cells_have_no_exponent() -> None:
    sites = [SummarySite("가상", (Decimal("1E+2"), Decimal("0.0000001")))]
    big = Decimal("123456789012345678.123456789012")
    xml = _sheet_xml(x.build_export(replace(BOOK, sites=[*sites, SummarySite("가상 큰", (big, None))])))
    numbers = re.findall(r"<v>([^<]*)</v>", xml)
    assert "100" in numbers and "0.0000001" in numbers and "123456789012345678.123456789012" in numbers
    assert not [n for n in numbers if "e" in n.lower()]


def test_text_cells_stay_text() -> None:
    risky = ["=1+1", "+1", "-1", "@SUM(A1)"]
    book = TemplateBook(YEAR, [_line(11, name) for name in risky])
    sheet = _open(x.build_template(book))[0]
    assert [sheet.cell(r, 6).value for r in range(2, 6)] == risky
    assert all(sheet.cell(r, 6).data_type == "s" for r in range(2, 6))
    assert "<f>" not in _sheet_xml(x.build_template(book))


def test_path_depth_must_be_four() -> None:
    with pytest.raises(ValueError, match="깊이"):
        x.build_template(TemplateBook(YEAR, [_line(11, "가상", path=PATH_A[:3])]))


def test_file_names() -> None:
    assert x.template_file_name(YEAR, "가상/회사") == "2031_가상_회사_온실가스 인벤토리_데이터_일괄업로드_양식.xlsx"
    assert (
        x.template_file_name(YEAR, "가상", site='가:상*?"<>|\\', scope=2)
        == "2031_가상_가_상________온실가스 인벤토리_scope 2 데이터_일괄업로드_양식.xlsx"
    )
    assert (
        x.template_file_name(YEAR, "가\x01상", scope=1)
        == "2031_가_상_온실가스 인벤토리_scope 1 데이터_일괄업로드_양식.xlsx"
    )
    assert x.export_file_name(YEAR, "가상", None) == "2031_가상_온실가스 인벤토리_지역기반_전체(scope 1+2) 데이터.xlsx"
    assert x.export_file_name(YEAR, "가상", 1) == "2031_가상_온실가스 인벤토리_scope 1 데이터.xlsx"
    assert x.export_file_name(YEAR, "가상", 2) == "2031_가상_온실가스 인벤토리_지역기반_scope 2 데이터.xlsx"


def test_tool_imports_no_django_or_esgapi() -> None:
    tree = ast.parse(Path(x.__file__).read_text(encoding="utf-8"))
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    allowed = ("io", "re", "zipfile", "collections", "dataclasses", "decimal", "typing", "openpyxl")
    assert names and all(name.split(".")[0] in allowed for name in names), names


def test_non_finite_decimal_is_a_blank_cell() -> None:  # 검증 R2(② — 감독 처분: 빈 칸)
    sites = [SummarySite("가상", (Decimal("NaN"), Decimal("Infinity")))]
    data = x.build_export(replace(BOOK, sites=sites))
    assert _row(_open(data)[0], 3) == ["가상", "tCO2-eq", None, None, None]
    assert "NaN" not in _sheet_xml(data) and "Infinity" not in _sheet_xml(data)


def test_year_sheet_problem_row_and_leaf_line() -> None:  # 검증 R3(②)
    rows = [_detail_row(problem="unit_conversion_missing"), _detail_row("가상 사업장 나")]
    year = _open(x.build_export(replace(BOOK, leaves=[DetailLeaf(11, PATH_A, rows)])))[2]
    assert _row(year, 3)[8:12] == ["tCO2-eq", 7.5, "kg", 60]  # 잎 머리 = 셈한 행만의 합 · 투입량은 둘 다
    assert _row(year, 4)[8:12] == ["tCO2-eq", "unit_conversion_missing", "kg", 30]
    assert _row(year, 5)[8:12] == ["tCO2-eq", 7.5, "kg", 30]
