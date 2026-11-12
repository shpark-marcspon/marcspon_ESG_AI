"""입력 템플릿의 드롭다운 정의를 목록으로 읽는다: 정의된 이름, 데이터 유효성, 교통수단 표준코드 표,
`C12` 시트 안의 목록, `드롭다운_매핑검토` 의 사전. 파일도 DB 도 없다.

여기 적힌 꼴(시트 이름, 머리글의 글자, 유효성 식의 글자)은 2026-10-13 에 받은 템플릿에서 읽어 적은 것이다.
항목의 이름·표준코드·사전의 낱말은 여기에 없다(읽을 때 메모리에만 있다).

하지 않는 것:
- 유효성 식을 셈하지 않는다. `OFFSET(…MATCH…)` 식은 꼴이 적어 둔 글자와 같은지만 보고, 목록은 그 열에서 읽는다.
- 유효성을 카테고리 시트의 어느 열·어느 머리글에 잇지 않는다(다음 밴드 S3b 의 일).
- 항목을 다듬지 않는다(앞뒤 공백·전각 그대로). 「고르지 않음」을 뜻하는 항목도 빼지 않는다.
- 매핑검토 사전을 정규화 사전으로 쓰지 않는다. 줄을 그대로 싣는다.
"""

import re
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.inventory.tools.scope3_sheets.grid import (
    AddressProblem,
    Cell,
    NumberCell,
    Sheet,
    TextCell,
    Workbook,
    column_letters,
    expand_range,
    parse_address,
    parse_range,
    parse_sheet_range,
)

DROPDOWN_SHEET: Final = "배출계수_드롭다운"
MAPPING_SHEET: Final = "드롭다운_매핑검토"
C12_SHEET: Final = "C12_판매제품폐기"

# 교통수단 표준코드 표: `배출계수_드롭다운` 의 M~P 열. 2행이 머리글, 3행부터 자료.
TRAVEL_CODE_HEADER_ROW: Final = 2
TRAVEL_CODE_HEADERS: Final = (
    ("M", "표시값(드롭다운)"),
    ("N", "표준코드"),
    ("O", "DEFRA Type"),
    ("P", "매핑 키워드"),
)

# `C12` 시트 안의 목록: 1행이 머리글, 2행부터 자료. (열쇠 열, 항목 열)
C12_HEADER_ROW: Final = 1
C12_HEADERS: Final = (
    ("AA", "대분류목록"),
    ("AC", "대분류_매핑"),
    ("AD", "중분류목록"),
    ("AF", "중분류_매핑"),
    ("AG", "소분류목록"),
)
# 그 시트의 `OFFSET` 유효성 둘의 식 글자. 셈하지 않는다 — 이 글자와 같은지만 본다.
C12_OFFSET_FORMULAS: Final = (
    "OFFSET($AD$2,MATCH($C22,$AC$2:$AC$31,0)-1,0,COUNTIF($AC$2:$AC$31,$C22),1)",
    "OFFSET($AG$2,MATCH($D22,$AF$2:$AF$73,0)-1,0,COUNTIF($AF$2:$AF$73,$D22),1)",
)

# `드롭다운_매핑검토`: 1행 요약의 머리글, 2행~ 요약, 13행 제목, 14행 사전의 머리글, 15행~ 사전.
MAPPING_SUMMARY_HEADER_ROW: Final = 1
MAPPING_SUMMARY_HEADERS: Final = (
    ("A", "구분"),
    ("B", "템플릿 시트/범위"),
    ("C", "기존 드롭다운/예시값"),
    ("D", "DB 기준 변경값"),
    ("E", "조치"),
)
MAPPING_TITLE_ROW: Final = 13
MAPPING_HEADER_ROW: Final = 14
MAPPING_HEADERS: Final = (("A", "매핑그룹"), ("B", "기존값"), ("C", "DB 기준값"))

_NAME: Final = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")

ValidationShape = Literal["defined_name", "range", "quoted_list", "offset", "number_range", "other"]
DropdownProblemKind = Literal[
    "missing_sheet",
    "bad_name_range",
    "empty_list_cell",
    "not_a_text_cell",
    "header_mismatch",
    "offset_formula_mismatch",
    "unknown_list_name",
]


@dataclass(frozen=True, slots=True)
class DropdownProblem:
    kind: DropdownProblemKind
    where: str  # `시트!칸` 이나 시트 이름, 정의된 이름
    detail: str


@dataclass(frozen=True, slots=True)
class ListItem:
    sheet: str
    cell: str
    text: str  # 칸의 글자 그대로


@dataclass(frozen=True, slots=True)
class NamedList:
    name: str
    refers_to: str  # 파일의 글자 그대로
    items: tuple[ListItem, ...]


@dataclass(frozen=True, slots=True)
class SheetValidation:
    sheet: str
    sqref: str
    shape: ValidationShape
    kind: str
    formula1: str | None
    formula2: str | None


@dataclass(frozen=True, slots=True)
class TravelCode:
    row: int
    display: str | None
    code: str | None
    defra_type: str | None
    keywords: str | None


@dataclass(frozen=True, slots=True)
class MappedItem:
    """`C12` 의 두 열짜리 목록 한 줄: 윗 단계의 항목(열쇠)과 그 아래 항목."""

    row: int
    key: str | None
    item: str | None


@dataclass(frozen=True, slots=True)
class C12Lists:
    major: tuple[ListItem, ...]  # AA
    middle: tuple[MappedItem, ...]  # AC · AD
    minor: tuple[MappedItem, ...]  # AF · AG


@dataclass(frozen=True, slots=True)
class SummaryRow:
    row: int
    cells: tuple[tuple[str, str], ...]  # (열, 글자)


@dataclass(frozen=True, slots=True)
class MappingEntry:
    row: int
    group: str | None
    old: str | None  # 기존값
    new: str | None  # DB 기준값


@dataclass(frozen=True, slots=True)
class MappingReview:
    summary: tuple[SummaryRow, ...]
    entries: tuple[MappingEntry, ...]


@dataclass(frozen=True, slots=True)
class Dropdowns:
    named_lists: tuple[NamedList, ...]
    validations: tuple[SheetValidation, ...]
    travel_codes: tuple[TravelCode, ...]
    c12: C12Lists
    mapping_review: MappingReview
    sheet_names: tuple[str, ...]  # 템플릿의 시트 이름(파일의 차례)
    problems: tuple[DropdownProblem, ...]


def _text(cell: Cell | None) -> str | None:
    """글자 칸은 글자, 수 칸은 십진 표기. 빈 칸과 수식 칸은 None."""
    if isinstance(cell, TextCell):
        return cell.text
    if isinstance(cell, NumberCell):
        return cell.decimal
    return None


def _sheet(workbook: Workbook, name: str) -> Sheet | None:
    return next((sheet for sheet in workbook.sheets if sheet.name == name), None)


def _rows_with(sheet: Sheet, letters: tuple[str, ...], after: int) -> list[int]:
    """그 열들 가운데 하나라도 칸이 있는 줄 번호(after 보다 큰 것)."""
    rows: set[int] = set()
    for address in sheet.cells:
        parsed = parse_address(address)
        if isinstance(parsed, AddressProblem):
            continue
        if parsed.row > after and column_letters(parsed.column) in letters:
            rows.add(parsed.row)
    return sorted(rows)


def _header_problems(sheet: Sheet, row: int, headers: tuple[tuple[str, str], ...]) -> list[DropdownProblem]:
    return [
        DropdownProblem("header_mismatch", f"{sheet.name}!{letter}{row}", "머리글의 글자가 꼴과 다르다")
        for letter, expected in headers
        if _text(sheet.cells.get(f"{letter}{row}")) != expected
    ]


def named_lists(workbook: Workbook) -> tuple[tuple[NamedList, ...], tuple[DropdownProblem, ...]]:
    """정의된 이름마다 그 범위의 칸을 목록으로. 빈 칸은 항목이 아니라 문제로 낸다."""
    lists: list[NamedList] = []
    problems: list[DropdownProblem] = []
    for defined in workbook.defined_names:
        target = parse_sheet_range(defined.refers_to)
        addresses = expand_range(target.cells) if not isinstance(target, AddressProblem) else target
        if isinstance(target, AddressProblem) or isinstance(addresses, AddressProblem):
            problems.append(
                DropdownProblem("bad_name_range", defined.name, "범위가 `시트!범위` 꼴이 아니거나 너무 크다")
            )
            continue
        sheet = _sheet(workbook, target.sheet)
        if sheet is None:
            problems.append(DropdownProblem("missing_sheet", defined.name, "이름이 가리키는 시트가 없다"))
            continue
        items: list[ListItem] = []
        for address in addresses:
            text = _text(sheet.cells.get(address))
            if text is None:
                problems.append(DropdownProblem("empty_list_cell", f"{sheet.name}!{address}", defined.name))
                continue
            items.append(ListItem(sheet.name, address, text))
        lists.append(NamedList(defined.name, defined.refers_to, tuple(items)))
    return tuple(lists), tuple(problems)


def validation_shape(kind: str, formula1: str | None) -> ValidationShape:
    """유효성 식의 꼴. 식을 셈하지 않고 글자만 본다."""
    if kind in ("decimal", "whole"):
        return "number_range"
    if kind != "list" or formula1 is None:
        return "other"
    if formula1.startswith("OFFSET("):
        return "offset"
    if len(formula1) >= 2 and formula1.startswith('"') and formula1.endswith('"'):
        return "quoted_list"
    if _NAME.fullmatch(formula1) is not None and isinstance(parse_address(formula1), AddressProblem):
        return "defined_name"
    if not isinstance(parse_range(formula1), AddressProblem):
        return "range"
    return "other"


def validations_of(sheet: Sheet) -> tuple[SheetValidation, ...]:
    return tuple(
        SheetValidation(
            sheet.name,
            validation.sqref,
            validation_shape(validation.kind, validation.formula1),
            validation.kind,
            validation.formula1,
            validation.formula2,
        )
        for validation in sheet.validations
    )


def travel_codes(workbook: Workbook) -> tuple[tuple[TravelCode, ...], tuple[DropdownProblem, ...]]:
    sheet = _sheet(workbook, DROPDOWN_SHEET)
    if sheet is None:
        return (), (DropdownProblem("missing_sheet", DROPDOWN_SHEET, "교통수단 표준코드 표의 시트가 없다"),)
    problems = _header_problems(sheet, TRAVEL_CODE_HEADER_ROW, TRAVEL_CODE_HEADERS)
    if problems:
        return (), tuple(problems)
    letters = tuple(letter for letter, _ in TRAVEL_CODE_HEADERS)
    codes = tuple(
        TravelCode(row, *(_text(sheet.cells.get(f"{letter}{row}")) for letter in letters))
        for row in _rows_with(sheet, letters, TRAVEL_CODE_HEADER_ROW)
    )
    return codes, ()


def c12_lists(workbook: Workbook) -> tuple[C12Lists, tuple[DropdownProblem, ...]]:
    empty = C12Lists((), (), ())
    sheet = _sheet(workbook, C12_SHEET)
    if sheet is None:
        return empty, (DropdownProblem("missing_sheet", C12_SHEET, "시트 안 목록이 있는 시트가 없다"),)
    problems = _header_problems(sheet, C12_HEADER_ROW, C12_HEADERS)
    if problems:
        return empty, tuple(problems)
    # OFFSET 식은 셈하지 않는다. 꼴이 적어 둔 글자와 같은지만 본다.
    offsets = sorted(v.formula1 or "" for v in validations_of(sheet) if v.shape == "offset")
    if offsets != sorted(C12_OFFSET_FORMULAS):
        problems.append(
            DropdownProblem("offset_formula_mismatch", C12_SHEET, "OFFSET 유효성의 식 글자가 꼴이 적어 둔 것과 다르다")
        )
    major = tuple(
        ListItem(sheet.name, f"AA{row}", text)
        for row in _rows_with(sheet, ("AA",), C12_HEADER_ROW)
        if (text := _text(sheet.cells.get(f"AA{row}"))) is not None
    )
    return C12Lists(major, _mapped(sheet, "AC", "AD"), _mapped(sheet, "AF", "AG")), tuple(problems)


def _mapped(sheet: Sheet, key_column: str, item_column: str) -> tuple[MappedItem, ...]:
    return tuple(
        MappedItem(row, _text(sheet.cells.get(f"{key_column}{row}")), _text(sheet.cells.get(f"{item_column}{row}")))
        for row in _rows_with(sheet, (key_column, item_column), C12_HEADER_ROW)
    )


def mapping_review(workbook: Workbook) -> tuple[MappingReview, tuple[DropdownProblem, ...]]:
    empty = MappingReview((), ())
    sheet = _sheet(workbook, MAPPING_SHEET)
    if sheet is None:
        return empty, (DropdownProblem("missing_sheet", MAPPING_SHEET, "매핑검토 시트가 없다"),)
    problems = _header_problems(sheet, MAPPING_SUMMARY_HEADER_ROW, MAPPING_SUMMARY_HEADERS)
    problems += _header_problems(sheet, MAPPING_HEADER_ROW, MAPPING_HEADERS)
    if problems:
        return empty, tuple(problems)
    summary_letters = tuple(letter for letter, _ in MAPPING_SUMMARY_HEADERS)
    summary = tuple(
        SummaryRow(
            row,
            tuple(
                (letter, text)
                for letter in summary_letters
                if (text := _text(sheet.cells.get(f"{letter}{row}"))) is not None
            ),
        )
        for row in _rows_with(sheet, summary_letters, MAPPING_SUMMARY_HEADER_ROW)
        if row < MAPPING_TITLE_ROW
    )
    entries = tuple(
        MappingEntry(
            row,
            _text(sheet.cells.get(f"A{row}")),
            _text(sheet.cells.get(f"B{row}")),
            _text(sheet.cells.get(f"C{row}")),
        )
        for row in _rows_with(sheet, ("A", "B", "C"), MAPPING_HEADER_ROW)
    )
    return MappingReview(summary, entries), ()


def read_dropdowns(workbook: Workbook) -> Dropdowns:
    lists, problems = named_lists(workbook)
    validations = tuple(validation for sheet in workbook.sheets for validation in validations_of(sheet))
    names = {named.name for named in lists} | {defined.name for defined in workbook.defined_names}
    unknown = tuple(
        DropdownProblem("unknown_list_name", f"{validation.sheet}!{validation.sqref}", "유효성이 없는 이름을 가리킨다")
        for validation in validations
        if validation.shape == "defined_name" and validation.formula1 not in names
    )
    codes, code_problems = travel_codes(workbook)
    c12, c12_problems = c12_lists(workbook)
    review, review_problems = mapping_review(workbook)
    return Dropdowns(
        lists,
        validations,
        codes,
        c12,
        review,
        tuple(sheet.name for sheet in workbook.sheets),
        (*problems, *unknown, *code_problems, *c12_problems, *review_problems),
    )
