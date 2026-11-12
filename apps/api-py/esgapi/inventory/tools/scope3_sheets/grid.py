"""읽힌 표의 값: 통합 문서 · 시트 · 칸의 갈래(글자 / 수 / 수식) · A1 주소와 범위.

여기에는 파일도 xlsx 도 없다. 바이트를 이 값으로 바꾸는 것은 `esgapi/inventory/tools/xlsx_reader.py` 하나다.

지키는 것:
- 빈 칸은 `Sheet.cells` 에 없다. 병합의 값을 나머지 칸에 퍼뜨리지 않는다(`merge_anchor` 로 왼쪽 위 칸만 묻는다).
- 수는 두 표기를 같이 싣는다: 파일 속 글자(`xml_text`)와 같은 배정밀도 수의 가장 짧은 왕복 표기(`decimal`, 십진 문자열).
  값을 고르는 것이 아니다. 같은 수의 두 표기다.
- 공유 수식의 딸린 칸은 식 글자가 없다(`formula is None`). 으뜸 칸의 주소만 가리킨다. **식을 지어내지 않는다.**
- 범위 펼치기에는 상한이 있다(`MAX_RANGE_CELLS`). `A1:XFD1048576` 한 줄이 170억 칸이다.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

# 한 범위를 칸의 목록으로 펼칠 때의 상한(어림). 넘으면 예외가 아니라 갈래(AddressProblem)로 답한다.
MAX_RANGE_CELLS: Final = 10_000
# Excel 시트의 끝(XFD1048576).
MAX_COLUMN: Final = 16_384
MAX_ROW: Final = 1_048_576

# ASCII 만. `\d` 는 전각 숫자를 받는다.
_ADDRESS: Final = re.compile(r"\$?([A-Z]{1,3})\$?([1-9][0-9]{0,6})")


@dataclass(frozen=True, slots=True)
class TextCell:
    text: str


@dataclass(frozen=True, slots=True)
class NumberCell:
    xml_text: str  # 파일 속 글자 그대로
    decimal: str  # 같은 배정밀도 수의 가장 짧은 왕복 표기(지수 없음, 엄격 십진)


@dataclass(frozen=True, slots=True)
class SharedFormula:
    """Excel 이 식 하나를 여러 칸에 밀어 쓴 묶음. 으뜸 칸만 식 글자를 갖는다."""

    index: int  # 묶음 번호(si)
    master: str  # 으뜸 칸의 주소
    ref: str  # 으뜸 칸이 적은 범위(ref)


@dataclass(frozen=True, slots=True)
class FormulaCell:
    formula: str | None  # 그 칸의 <f> 에 든 글자 그대로. 딸린 칸은 None
    shared: SharedFormula | None
    cached: TextCell | NumberCell | None  # 저장된 값. <v> 가 없으면 None


Cell = TextCell | NumberCell | FormulaCell


@dataclass(frozen=True, slots=True)
class Validation:
    kind: str  # 파일의 type 글자 그대로(list · decimal · whole …). 없으면 빈 글자
    sqref: str
    formula1: str | None
    formula2: str | None


@dataclass(frozen=True, slots=True)
class DefinedName:
    name: str
    refers_to: str  # 파일의 글자 그대로(`시트!$A$3:$A$19` 꼴)


@dataclass(frozen=True, slots=True)
class Sheet:
    name: str
    cells: Mapping[str, Cell]  # 주소("B7") → 칸. 빈 칸은 없다
    merges: tuple[str, ...]
    validations: tuple[Validation, ...]


@dataclass(frozen=True, slots=True)
class Workbook:
    sheets: tuple[Sheet, ...]  # workbook.xml 의 차례
    defined_names: tuple[DefinedName, ...]


@dataclass(frozen=True, slots=True)
class CellAddress:
    row: int  # 1 부터
    column: int  # 1 부터(A = 1)


@dataclass(frozen=True, slots=True)
class CellRange:
    first: CellAddress  # 왼쪽 위
    last: CellAddress  # 오른쪽 아래


@dataclass(frozen=True, slots=True)
class SheetRange:
    sheet: str
    cells: CellRange


@dataclass(frozen=True, slots=True)
class AddressProblem:
    kind: Literal["not_an_address", "not_a_range", "range_too_large"]
    text: str


def column_number(letters: str) -> int:
    number = 0
    for letter in letters:
        number = number * 26 + (ord(letter) - ord("A") + 1)
    return number


def column_letters(column: int) -> str:
    letters = ""
    while column > 0:
        column, rest = divmod(column - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def parse_address(text: str) -> CellAddress | AddressProblem:
    """`B7` · `$B$7`. 소문자, 0행, 시트 끝을 넘는 자리는 주소가 아니다."""
    match = _ADDRESS.fullmatch(text)
    if match is None:
        return AddressProblem("not_an_address", text)
    column, row = column_number(match.group(1)), int(match.group(2))
    if column > MAX_COLUMN or row > MAX_ROW:
        return AddressProblem("not_an_address", text)
    return CellAddress(row, column)


def format_address(address: CellAddress) -> str:
    return f"{column_letters(address.column)}{address.row}"


def parse_range(text: str) -> CellRange | AddressProblem:
    """`A3:A19` · `$A$3:$A$19` · 칸 하나(`B7`). 뒤집힌 범위(`B9:A3`)는 범위가 아니다."""
    first_text, colon, last_text = text.partition(":")
    first = parse_address(first_text)
    last = parse_address(last_text) if colon else first
    if isinstance(first, AddressProblem) or isinstance(last, AddressProblem):
        return AddressProblem("not_a_range", text)
    if last.row < first.row or last.column < first.column:
        return AddressProblem("not_a_range", text)
    return CellRange(first, last)


def format_range(cells: CellRange) -> str:
    if cells.first == cells.last:
        return format_address(cells.first)
    return f"{format_address(cells.first)}:{format_address(cells.last)}"


def parse_sheet_range(text: str) -> SheetRange | AddressProblem:
    """`시트!$A$3:$A$19` · `'시트 이름'!A1`. 시트 이름이 없으면 범위가 아니다."""
    sheet, bang, cells_text = text.rpartition("!")
    if not bang or not sheet:
        return AddressProblem("not_a_range", text)
    if len(sheet) >= 2 and sheet.startswith("'") and sheet.endswith("'"):
        sheet = sheet[1:-1].replace("''", "'")
    cells = parse_range(cells_text)
    if isinstance(cells, AddressProblem):
        return AddressProblem("not_a_range", text)
    return SheetRange(sheet, cells)


def range_size(cells: CellRange) -> int:
    return (cells.last.row - cells.first.row + 1) * (cells.last.column - cells.first.column + 1)


def expand_range(cells: CellRange) -> tuple[str, ...] | AddressProblem:
    """범위의 칸 주소를 줄 차례로. 칸 수가 상한을 넘으면 펼치지 않고 갈래로 답한다."""
    if range_size(cells) > MAX_RANGE_CELLS:
        return AddressProblem("range_too_large", format_range(cells))
    return tuple(
        format_address(CellAddress(row, column))
        for row in range(cells.first.row, cells.last.row + 1)
        for column in range(cells.first.column, cells.last.column + 1)
    )


def contains(cells: CellRange, address: CellAddress) -> bool:
    return (
        cells.first.row <= address.row <= cells.last.row and cells.first.column <= address.column <= cells.last.column
    )


def merge_anchor(sheet: Sheet, address: str) -> str | AddressProblem:
    """그 칸이 병합 안에 있으면 병합의 왼쪽 위 칸, 아니면 그 칸. 값을 퍼뜨리지는 않는다(주소만 답한다)."""
    here = parse_address(address)
    if isinstance(here, AddressProblem):
        return here
    for merge in sheet.merges:
        cells = parse_range(merge)
        if isinstance(cells, AddressProblem):
            return cells
        if contains(cells, here):
            return format_address(cells.first)
    return format_address(here)
