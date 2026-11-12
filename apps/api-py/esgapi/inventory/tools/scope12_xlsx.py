"""Scope 1·2 엑셀 두 벌을 짓는 순수 도구(밴드 S12b-1 ① — 결정 MARC-ENT-472 확정판의 **구조만** 코드로 짓는다).

    build_template(TemplateBook)  일괄업로드 양식: 시트 「년도」·「분기」·「월」(같은 줄) · 머리 8열 + 칸 · 값 칸 빔
    build_export(ExportBook)      데이터 엑셀: 「온실가스 배출량」·「연도별 배출량 데이터」·「상세 데이터(…)」 셋
    template_file_name·export_file_name  내려받기 파일 이름(스펙 S4 5-3·S5 6-1 꼴, 이름 안 금지 글자는 `_`)
    fold                          행 칸 값(블록 입력주기) → 시트 주기의 칸(월→분기·년도, 분기→년도 더함. 더 굵으면 빔)

받은 확정판 파일은 저장소에 없다(G0 — 견본 값 0). 시트 이름·머리 글자·열 차례·병합 꼴만 여기 글자로 적는다.
평범한 dataclass 만 받는다 — django·esgapi 를 import 하지 않는다(순수 시험이 단언). 배출량 셈은 부르는 쪽(actions)이
`calc/entry_emission.py` 로 하고 여기는 받은 Decimal 을 칸에 놓을 뿐이다(반올림 0 — 칸 서식만 그 해 자릿수).

★ 같은 입력 → 같은 바이트: zip 항목 시각·문서 속성 시각을 고정한다(`_restamp` — dataverify/tools/edk_xlsx.py 의
  `_restamp`·`_fixed_core` 꼴을 옮겨 적음. business-modules-apart 라 import 하지 않는다).
★ 글 칸은 늘 글 칸이다(`data_type="s"` — `=`·`+`·`-`·`@` 로 시작하는 이름도 수식이 되지 않는다).
★ 숫자 칸은 `format(d, "f")` 글자 + `data_type="n"`: openpyxl 3.1.5 는 Decimal 을 float 로 바꿔 `1e-07` 지수 꼴로
  적고 18자리 정수부를 자른다(C0 실측) — 글자를 그대로 `<v>` 에 싣게 한다.
"""

import io
import re
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Final

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FIXED_DATE: Final = (1980, 1, 1, 0, 0, 0)
"""zip 항목의 시각(zip 이 적을 수 있는 가장 이른 시각 — 매번 같은 바이트)."""
FIXED_STAMP: Final = b"1980-01-01T00:00:00Z"
PATH_DEPTH: Final = 4  # 범위 · 배출원 유형 · 배출활동 · 자산/시설(풀의 LEVELS 넷)
GASES: Final = ("CO2", "CH4", "N2O", "HFCs", "PFCs", "SF6", "NF3")
PERIODS: Final = ("year", "quarter", "month")  # 시트 차례(굵은 것부터)
PERIOD_LABELS: Final = {"month": "월", "quarter": "분기", "year": "년도"}
_SUM_PRECISION: Final = 60  # Decimal(30,12) 여럿의 합이 잘리지 않는 자릿수(utils/entries.py 와 같은 값)

# ── 확정판 구조(글자 목록 — 값 0) ─────────────────────────────────────

TEMPLATE_SHEETS: Final = ("년도", "분기", "월")
TEMPLATE_HEAD: Final = (
    "ID(수정X)",
    "범위(수정X)",
    "배출원 유형(수정X)",
    "배출활동(수정X)",
    "자산/시설명(수정X)",
    "사업장(수정X)",
    "입력 주기(수정X)",  # [우리 해석] 확정판 G1 이 시트마다 다른 글자라 하나로
    "단위(수정X)",
)
SUMMARY_SHEET: Final = "온실가스 배출량"
YEARLY_SHEET: Final = "연도별 배출량 데이터"
DETAIL_SHEETS: Final = {"year": "상세 데이터(년도)", "quarter": "상세 데이터(분기)", "month": "상세 데이터(월)"}
EXPORT_SHEETS: Final = (SUMMARY_SHEET, YEARLY_SHEET, *DETAIL_SHEETS.values())
SUMMARY_HEAD: Final = ("사업장명", "단위")
SUMMARY_TOTAL: Final = "총계"
WHOLE_HEAD: Final = "Scope 1+2"  # 확정판 머리 글자 — 값은 모든 뿌리의 합
YEARLY_HEAD: Final = ("ID", "범위", "배출원 유형", "배출활동", "자산/시설명", "단위")
YEARLY_TAIL: Final = ("메모", "추정치")
DETAIL_HEAD: Final = (
    "ID",
    "범위",
    "배출원 유형",
    "배출활동",
    "자산/시설명",
    "사업장",
    "상세 시설명",
    "재생에너지 사용 여부",
)
EMISSION_GROUP: Final = "온실가스 배출량 데이터"
INPUT_GROUP: Final = "투입량 데이터"
NCV_HEAD: Final = ("순발열량", "순발열량 단위")
FACTOR_GROUP: Final = "온실가스별 배출계수"
GWP_GROUP: Final = "온실가스별 GWP"
DETAIL_TAIL: Final = ("배출계수 출처", "산식")
UNIT_HEAD: Final = "단위"
TOTAL_HEAD: Final = "총계"
EMISSION_UNIT: Final = "tCO2-eq"  # ghg_pool DEFAULT_EMISSION_UNIT 글자(순수라 import 0 — ② 시험이 대조)
NA_TEXT: Final = "N/A"
ESTIMATED_MARK: Final = "Y"
# 산식 글(MARC-ENT-463 의 기본 산식 둘 — calc/entry_emission.py 머리 주석과 같은 뜻. C0 감독 확인)
FORMULA_PLAIN: Final = "활동량 × Σ(가스별 배출계수 × GWP) × 단위 환산"
FORMULA_NCV: Final = "활동량 × 순발열량 × Σ(가스별 배출계수 × GWP) × 단위 환산"

_BAD_NAME: Final = re.compile(r'[/\\:*?"<>|\x00-\x1f\x7f]')
_HEAD_FONT: Final = Font(bold=True)
_CENTER: Final = Alignment(horizontal="center", vertical="center")


# ── 입력 꼴 ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TemplateLine:
    """양식 한 줄: 잎 하나 × 사업장 하나(그 잎 상세의 블록). 같은 잎의 줄은 이어 둔다(A~E 세로 병합)."""

    node_id: int
    path: tuple[str, ...]  # 범위 · 배출원 유형 · 배출활동 · 자산/시설(깊이 4)
    site_name: str
    period: str  # month · quarter · year(그 블록의 입력주기)
    unit: str  # 그 선택이 잡은 판의 입력 단위


@dataclass(frozen=True)
class TemplateBook:
    year: int
    lines: Sequence[TemplateLine]


@dataclass(frozen=True)
class SummarySite:
    """첫 시트의 사업장 한 줄 — 그 해(Y) 뿌리(Scope)마다 합(tCO2-eq, ExportBook.roots 차례). 값 없으면 None(빈 칸)."""

    name: str
    values: tuple[Decimal | None, ...]


@dataclass(frozen=True)
class YearlyLine:
    """「연도별 배출량 데이터」 한 줄 — 리스트(list_rows)의 줄 그대로."""

    node_id: int
    path: tuple[str, ...]
    values: Mapping[int, Decimal | None]  # Y-2·Y-1·Y
    memo: str
    estimated: bool


@dataclass(frozen=True)
class SheetCells:
    """상세 행 하나의 한 시트(주기) 칸: 배출량·투입량 칸(시트 칸 수만큼, 빈 칸 None)."""

    emissions: tuple[Decimal | None, ...]
    amounts: tuple[Decimal | None, ...]


@dataclass(frozen=True)
class GasCell:
    """가스 한 줄의 계수·GWP(꺼진 가스는 둘 다 None — 빈 칸)."""

    factor: Decimal | None
    gwp: Decimal | None


@dataclass(frozen=True)
class DetailRow:
    """상세 시트의 입력 행 하나(사업장 × 상세 시설). total 은 저장 셈(RowView.emission) 그대로."""

    site_name: str
    detail_name: str
    unit: str
    na: bool
    problem: str | None  # 셈 문제 글(상세 응답의 emissionProblem) — 배출량 칸 빔, 총계에 이 글
    total: Decimal | None
    amount_total: Decimal | None
    cells: Mapping[str, SheetCells]  # 주기(year·quarter·month) → 칸
    ncv: Decimal | None
    ncv_unit: str | None
    gases: tuple[GasCell, ...]  # GASES 차례 일곱
    source: str


@dataclass(frozen=True)
class DetailLeaf:
    """상세 시트의 잎 묶음 — 머리 줄(A~E · 합) + 행."""

    node_id: int
    path: tuple[str, ...]
    rows: Sequence[DetailRow]


@dataclass(frozen=True)
class ExportBook:
    year: int
    decimals: int
    roots: tuple[str, ...]  # 첫 시트의 Scope 열 = 뿌리 이름(트리 차례 — 대시보드 S12a-3 과 같은 묶음)
    whole: bool  # 참이면 끝 열 「Scope 1+2」 = 모든 뿌리 합(대시보드 합계와 같은 값)
    sites: Sequence[SummarySite]
    yearly: Sequence[YearlyLine]
    leaves: Sequence[DetailLeaf]


# ── 칸 ─────────────────────────────────────────────────────────────


def slot_labels(year: int, period: str) -> tuple[str, ...]:
    """시트 칸의 머리 글자: 월 「1월…12월」 · 분기 「1분기…4분기」 · 년도 「{Y}년」."""
    if period == "month":
        return tuple(f"{month}월" for month in range(1, 13))
    if period == "quarter":
        return tuple(f"{quarter}분기" for quarter in range(1, 5))
    if period == "year":
        return (f"{year}년",)
    raise ValueError(f"입력주기가 아니다: {period!r}")


def _slot_index(slot: str, period: str) -> int | None:
    """칸 글자(`YYYY-MM`·`YYYY-Qn`·`YYYY`) → 그 주기 시트의 칸 차례. 더 굵은 칸이면 None."""
    _, dash, rest = slot.partition("-")
    if not dash:  # 연 칸
        return 0 if period == "year" else None
    if rest.startswith("Q"):
        quarter = int(rest[1:])
        if period == "quarter":
            return quarter - 1
        return 0 if period == "year" else None
    month = int(rest)
    if period == "month":
        return month - 1
    if period == "quarter":
        return (month - 1) // 3
    return 0


def fold(values: Mapping[str, Decimal | None], period: str) -> tuple[Decimal | None, ...]:
    """행 칸 값 → 시트 주기의 칸 값. 같거나 더 잔 칸은 더하고, 더 굵은 칸은 빈 칸(None). 값이 없는 칸도 None."""
    width = len(slot_labels(0, period))
    found: list[list[Decimal]] = [[] for _ in range(width)]
    for slot, amount in values.items():
        index = _slot_index(slot, period)
        if index is not None and amount is not None:
            found[index].append(amount)
    return tuple(_sum(column) for column in found)


def _sum(values: Sequence[Decimal | None]) -> Decimal | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    with localcontext(prec=_SUM_PRECISION):
        return sum(present, Decimal(0))


def _put(sheet: Worksheet, row: int, column: int, value: str | int | Decimal | None, number_format: str = "") -> Cell:
    cell: Cell = sheet.cell(row=row, column=column)  # pyright: ignore[reportAssignmentType]
    if value is None or (isinstance(value, Decimal) and not value.is_finite()):
        return cell  # NaN·Infinity 는 빈 칸(숫자 칸에 「NaN」 글자를 넣으면 엑셀이 깨진 파일로 연다 — 검증 R2)
    if isinstance(value, Decimal):
        cell.value = format(value, "f")
        cell.data_type = "n"
        if number_format:
            cell.number_format = number_format
    elif isinstance(value, int):
        cell.value = value
    else:
        cell.value = value
        cell.data_type = "s"  # `=` 로 시작해도 글 칸(수식 주입 0)
    return cell


def _head(sheet: Worksheet, row: int, column: int, text: str) -> None:
    cell = _put(sheet, row, column, text)
    cell.font = _HEAD_FONT
    cell.alignment = _CENTER


def _number_format(decimals: int) -> str:
    return "0" if decimals <= 0 else "0." + "0" * decimals


def _path(path: tuple[str, ...]) -> tuple[str, ...]:
    if len(path) != PATH_DEPTH:
        raise ValueError(f"잎 줄의 깊이가 {PATH_DEPTH} 가 아니다: {len(path)}")
    return path


# ── 양식 ───────────────────────────────────────────────────────────


def template_columns(year: int, period: str) -> tuple[str, ...]:
    """양식 시트 하나의 1행 머리(8열 + 칸). 년도 시트 칸은 Y-2·Y-1·Y."""
    if period == "year":
        return (*TEMPLATE_HEAD, *(f"{y}년" for y in (year - 2, year - 1, year)))
    return (*TEMPLATE_HEAD, *slot_labels(year, period))


def build_template(book: TemplateBook) -> bytes:
    """일괄업로드 양식(xlsx 바이트). 세 시트 다 같은 줄(주기는 G열) · 값 칸 빔 · 같은 잎 줄들의 A~E 세로 병합."""
    workbook = Workbook()
    workbook.remove(workbook.worksheets[0])
    for title, period in zip(TEMPLATE_SHEETS, PERIODS, strict=True):
        sheet = workbook.create_sheet(title)
        for column, text in enumerate(template_columns(book.year, period), start=1):
            _head(sheet, 1, column, text)
        for offset, line in enumerate(book.lines):
            row = offset + 2
            path = _path(line.path)
            _put(sheet, row, 1, line.node_id)
            for column, name in enumerate(path, start=2):
                _put(sheet, row, column, name)
            _put(sheet, row, 6, line.site_name)
            _put(sheet, row, 7, PERIOD_LABELS[line.period])
            _put(sheet, row, 8, line.unit)
        _merge_runs(sheet, [line.node_id for line in book.lines], first_row=2, columns=5)
    return _save(workbook)


def _merge_runs(sheet: Worksheet, keys: Sequence[int], *, first_row: int, columns: int) -> None:
    """같은 열쇠가 이어진 줄들의 1~columns 열을 세로로 병합(줄 하나면 병합 0)."""
    start = 0
    for index in range(1, len(keys) + 1):
        if index == len(keys) or keys[index] != keys[start]:
            if index - start > 1:
                for column in range(1, columns + 1):
                    sheet.merge_cells(
                        start_row=first_row + start, end_row=first_row + index - 1,
                        start_column=column, end_column=column,
                    )  # fmt: skip
            start = index


# ── 데이터 ─────────────────────────────────────────────────────────


def build_export(book: ExportBook) -> bytes:
    """데이터 엑셀(xlsx 바이트) — 시트 다섯(EXPORT_SHEETS 차례)."""
    workbook = Workbook()
    workbook.remove(workbook.worksheets[0])
    number = _number_format(book.decimals)
    _summary(workbook.create_sheet(SUMMARY_SHEET), book, number)
    _yearly(workbook.create_sheet(YEARLY_SHEET), book, number)
    for period in PERIODS:
        _detail(workbook.create_sheet(DETAIL_SHEETS[period]), book, period, number)
    return _save(workbook)


def _summary(sheet: Worksheet, book: ExportBook, number: str) -> None:
    heads = [*SUMMARY_HEAD, *book.roots, *([WHOLE_HEAD] if book.whole else [])]
    for column, text in enumerate(heads, start=1):
        _head(sheet, 1, column, text)
    lines = [[*site.values, *([_sum(site.values)] if book.whole else [])] for site in book.sites]
    totals = [_sum([line[index] for line in lines]) for index in range(len(heads) - len(SUMMARY_HEAD))]
    for row, (name, cells) in enumerate(
        [(SUMMARY_TOTAL, totals), *((site.name, line) for site, line in zip(book.sites, lines, strict=True))], start=2
    ):
        _put(sheet, row, 1, name)
        _put(sheet, row, 2, EMISSION_UNIT)
        for column, value in enumerate(cells, start=3):
            _put(sheet, row, column, value, number)


def _yearly(sheet: Worksheet, book: ExportBook, number: str) -> None:
    years = (book.year - 2, book.year - 1, book.year)
    heads = (*YEARLY_HEAD, *(f"{y}년" for y in years), *YEARLY_TAIL)
    for column, text in enumerate(heads, start=1):
        _head(sheet, 1, column, text)
    for row, line in enumerate(book.yearly, start=2):
        _put(sheet, row, 1, line.node_id)
        for column, name in enumerate(_path(line.path), start=2):
            _put(sheet, row, column, name)
        _put(sheet, row, 6, EMISSION_UNIT)
        for column, year in enumerate(years, start=7):
            _put(sheet, row, column, line.values.get(year), number)
        _put(sheet, row, 10, line.memo or None)
        _put(sheet, row, 11, ESTIMATED_MARK if line.estimated else None)


@dataclass(frozen=True)
class DetailLayout:
    """상세 시트 하나의 열 자리(1부터). 년도 시트는 총계 열이 없다(G3)."""

    width: int
    has_total: bool

    @property
    def emission_unit(self) -> int:
        return len(DETAIL_HEAD) + 1

    @property
    def emission_first(self) -> int:
        return self.emission_unit + 1

    @property
    def emission_total(self) -> int:
        return self.emission_first + self.width

    @property
    def input_unit(self) -> int:
        return self.emission_first + self.width + (1 if self.has_total else 0)

    @property
    def input_first(self) -> int:
        return self.input_unit + 1

    @property
    def input_total(self) -> int:
        return self.input_first + self.width

    @property
    def ncv(self) -> int:
        return self.input_first + self.width + (1 if self.has_total else 0)

    @property
    def factor_first(self) -> int:
        return self.ncv + len(NCV_HEAD)

    @property
    def gwp_first(self) -> int:
        return self.factor_first + len(GASES)

    @property
    def tail(self) -> int:
        return self.gwp_first + len(GASES)

    @property
    def last(self) -> int:
        return self.tail + len(DETAIL_TAIL) - 1


def detail_layout(period: str) -> DetailLayout:
    return DetailLayout(width=len(slot_labels(0, period)), has_total=period != "year")


def detail_heads(year: int, period: str) -> tuple[tuple[str | None, ...], tuple[str | None, ...]]:
    """상세 시트 머리 두 줄(병합으로 가려지는 칸은 None)."""
    layout = detail_layout(period)
    labels = slot_labels(year, period)
    group = (UNIT_HEAD, *labels, *((TOTAL_HEAD,) if layout.has_total else ()))
    pad = (None,) * (len(group) - 1)
    first = (
        *DETAIL_HEAD, EMISSION_GROUP, *pad, INPUT_GROUP, *pad, *NCV_HEAD,
        FACTOR_GROUP, *(None,) * (len(GASES) - 1), GWP_GROUP, *(None,) * (len(GASES) - 1), *DETAIL_TAIL,
    )  # fmt: skip
    second = (
        *(None,) * len(DETAIL_HEAD), *group, *group, *(None,) * len(NCV_HEAD), *GASES, *GASES,
        *(None,) * len(DETAIL_TAIL),
    )  # fmt: skip
    return first, second


def detail_merges(period: str) -> tuple[str, ...]:
    """상세 시트 머리의 병합 범위(A1:A2 꼴) — 홑 머리는 세로, 묶음 머리는 가로."""
    layout = detail_layout(period)
    group = 1 + layout.width + (1 if layout.has_total else 0)
    singles = [*range(1, len(DETAIL_HEAD) + 1), layout.ncv, layout.ncv + 1, layout.tail, layout.tail + 1]
    spans = [
        (layout.emission_unit, group),
        (layout.input_unit, group),
        (layout.factor_first, len(GASES)),
        (layout.gwp_first, len(GASES)),
    ]
    found = [f"{get_column_letter(column)}1:{get_column_letter(column)}2" for column in singles]
    found += [f"{get_column_letter(start)}1:{get_column_letter(start + size - 1)}1" for start, size in spans]
    return tuple(sorted(found))


def _detail(sheet: Worksheet, book: ExportBook, period: str, number: str) -> None:
    layout = detail_layout(period)
    first, second = detail_heads(book.year, period)
    for column, text in enumerate(first, start=1):
        if text is not None:
            _head(sheet, 1, column, text)
    for column, text in enumerate(second, start=1):
        if text is not None:
            _head(sheet, 2, column, text)
    for merged in detail_merges(period):
        sheet.merge_cells(merged)
    row = 3
    for leaf in book.leaves:
        path = _path(leaf.path)
        start = row
        _leaf_row(sheet, row, leaf, period, layout, number)
        _put(sheet, row, 1, leaf.node_id)
        for column, name in enumerate(path, start=2):
            _put(sheet, row, column, name)
        row += 1
        for line in leaf.rows:
            _detail_row(sheet, row, line, period, layout, number)
            row += 1
        if row - start > 1:
            for column in range(1, 6):
                sheet.merge_cells(start_row=start, end_row=row - 1, start_column=column, end_column=column)


def _leaf_row(sheet: Worksheet, row: int, leaf: DetailLeaf, period: str, layout: DetailLayout, number: str) -> None:
    """잎 머리 줄: 배출량 칸·총계는 행 합. 투입량은 행 단위가 모두 같을 때만 합(그 단위 글자도)."""
    counted = [line for line in leaf.rows if not line.na and line.problem is None]
    _put(sheet, row, layout.emission_unit, EMISSION_UNIT)
    for index in range(layout.width):
        value = _sum([line.cells[period].emissions[index] for line in counted])
        _put(sheet, row, layout.emission_first + index, value, number)
    if layout.has_total:
        _put(sheet, row, layout.emission_total, _sum([line.total for line in counted]), number)
    units = {line.unit for line in leaf.rows}
    if len(units) == 1:
        _put(sheet, row, layout.input_unit, next(iter(units)))
        for index in range(layout.width):
            value = _sum([line.cells[period].amounts[index] for line in leaf.rows if not line.na])
            _put(sheet, row, layout.input_first + index, value, number)
        if layout.has_total:
            value = _sum([line.amount_total for line in leaf.rows if not line.na])
            _put(sheet, row, layout.input_total, value, number)


def _detail_row(sheet: Worksheet, row: int, line: DetailRow, period: str, layout: DetailLayout, number: str) -> None:
    _put(sheet, row, 6, line.site_name)
    _put(sheet, row, 7, line.detail_name)
    _put(sheet, row, layout.emission_unit, EMISSION_UNIT)
    _put(sheet, row, layout.input_unit, line.unit)
    cells = line.cells[period]
    if line.na:
        if layout.has_total:
            _put(sheet, row, layout.emission_total, NA_TEXT)
            _put(sheet, row, layout.input_total, NA_TEXT)
        else:
            _put(sheet, row, layout.emission_first, NA_TEXT)
            _put(sheet, row, layout.input_first, NA_TEXT)
    else:
        if line.problem is not None:
            at = layout.emission_total if layout.has_total else layout.emission_first
            _put(sheet, row, at, line.problem)
        else:
            for index, value in enumerate(cells.emissions):
                _put(sheet, row, layout.emission_first + index, value, number)
            if layout.has_total:
                _put(sheet, row, layout.emission_total, line.total, number)
        for index, value in enumerate(cells.amounts):
            _put(sheet, row, layout.input_first + index, value, number)
        if layout.has_total:
            _put(sheet, row, layout.input_total, line.amount_total, number)
    _put(sheet, row, layout.ncv, line.ncv)
    _put(sheet, row, layout.ncv + 1, line.ncv_unit)
    for index, gas in enumerate(line.gases):
        _put(sheet, row, layout.factor_first + index, gas.factor)
        _put(sheet, row, layout.gwp_first + index, gas.gwp)
    _put(sheet, row, layout.tail, line.source)
    _put(sheet, row, layout.tail + 1, FORMULA_NCV if line.ncv is not None else FORMULA_PLAIN)


# ── 저장·이름 ───────────────────────────────────────────────────────


def _save(workbook: Workbook) -> bytes:
    workbook.properties.creator = "esgapi"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return _restamp(buffer.getvalue())


def _restamp(data: bytes) -> bytes:
    """zip 항목 시각·차례와 문서 속성 시각을 고정해 다시 묶는다(edk_xlsx `_restamp` 꼴)."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for entry in source.infolist():
            content = source.read(entry.filename)
            if entry.filename == "docProps/core.xml":
                content = _fixed_core(content)
            info = zipfile.ZipInfo(entry.filename, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(info, content)
    return out.getvalue()


def _fixed_core(content: bytes) -> bytes:
    """문서 속성의 created·modified 를 고정 시각으로(openpyxl 은 저장할 때 지금 시각을 적는다)."""
    return re.sub(
        rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
        lambda m: m.group(1) + FIXED_STAMP + m.group(2),
        content,
    )


def clean_part(text: str) -> str:
    """파일 이름 한 토막: `/ \\ : * ? " < > |` 와 제어 문자 → `_`."""
    return _BAD_NAME.sub("_", text)


def template_file_name(year: int, company: str, *, site: str | None = None, scope: int | None = None) -> str:
    """양식 파일 이름 — 확정판 꼴. 사업장·Scope 를 고르면 그 토막만 끼운다(스펙 S4 5-3)."""
    middle = f"_{clean_part(site)}" if site is not None else ""
    kind = f"scope {scope} 데이터" if scope is not None else "데이터"
    return f"{year}_{clean_part(company)}{middle}_온실가스 인벤토리_{kind}_일괄업로드_양식.xlsx"


def export_file_name(year: int, company: str, scope: int | None) -> str:
    """데이터 엑셀 파일 이름(스펙 S5 6-1): 전체 「지역기반_전체(scope 1+2)」·1 「scope 1」·2 「지역기반_scope 2」."""
    kind = {None: "지역기반_전체(scope 1+2)", 1: "scope 1", 2: "지역기반_scope 2"}[scope]
    return f"{year}_{clean_part(company)}_온실가스 인벤토리_{kind} 데이터.xlsx"
