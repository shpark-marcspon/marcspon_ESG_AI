"""Scope 1·2 일괄업로드 양식 읽기(밴드 S12b-2 ① — 결정 MARC-ENT-472). xlsx 바이트 → 값이 찬 줄.

    read_upload(data, year)   UploadBook(값이 찬 줄 + 줄·칸 오류) · UploadProblem(파일 오류 글)

순수하다: 표준 라이브러리와 같은 `tools/` 만 쓴다(django 0 — 순수 시험이 단언). zip·XML 을 아는 것은 `xlsx_reader`
뿐이고, 양식 꼴(시트 이름·머리·주기)은 `scope12_xlsx` 의 글자를 import 한다(두 벌 금지). 값이 맞는지(잎·사업장·칸 값)는
부르는 쪽(`service/actions/scope12_upload.py`)이 그 해의 상태와 대 본다.

★ 칸 글자: 수 칸은 `NumberCell.decimal`(같은 배정밀도 수의 가장 짧은 왕복 표기 — Excel 이 적은 `1234.5670000000001`
  도 `1234.567` 이 된다), 글자 칸은 앞뒤 공백을 걷는다. 공백만이면 빈 칸이다. 참거짓은 `TRUE`·`FALSE` 글자로 와 금액
  오류가 된다.
★ 병합: A 는 같은 잎 줄들에 세로로 병합돼 딸린 줄에는 칸이 없다. 시트마다 병합을 **한 번만** 파싱해 A 열의 것만 시작
  줄 차례로 두고 이분 탐색으로 찾는다(`merge_anchor` 를 줄마다 부르면 줄 × 병합 수다). 겹친 병합은 Excel 이 짓지
  않으므로 파일 오류다. B~E 는 읽지 않아 병합도 보지 않는다.
★ 머리 밖 칸(마지막 머리 오른쪽의 메모 등)은 읽지 않는다. 1행의 머리 밖 칸은 파일 오류다(그 해의 양식이 아니다).

★ 무효 조건:
- 날짜 서식 칸은 수로 읽힌다(읽개가 서식을 읽지 않는다): 날짜를 넣으면 일련번호가 값으로 들어간다.
- `t="e"` 칸(`#N/A` 등)은 읽개가 파일째 거절한다. 글에는 칸 주소만 있고 시트 이름은 없다(읽개가 아는 것은 zip 항목
  이름이다).
- 양식에는 사업장 id 가 없다. 내려받은 뒤 두 사업장 이름을 맞바꾸면 값이 다른 사업장에 든다 — 이름이 유일하다는 것만
  지킨다.
"""

from bisect import bisect_right
from dataclasses import dataclass
from itertools import pairwise
from typing import Final

from esgapi.inventory.tools.scope3_sheets.grid import (
    AddressProblem,
    Cell,
    CellAddress,
    FormulaCell,
    NumberCell,
    Sheet,
    TextCell,
    Workbook,
    format_address,
    parse_address,
    parse_range,
)
from esgapi.inventory.tools.scope12_xlsx import PERIODS, TEMPLATE_HEAD, TEMPLATE_SHEETS, template_columns
from esgapi.inventory.tools.xlsx_reader import GHG_UPLOAD_MAX_BYTES, ProblemKind, ReaderProblem, read_workbook

UPLOAD_LINES_MAX: Final = 300
"""한 번에 받는 값이 찬 줄 수(세 시트 합). 줄마다 저장 한 번이고 그동안 그 해 잠금을 쥔다 — 값의 근거는 보고의 실측."""

NOT_XLSX: Final = "엑셀 파일(.xlsx)을 읽지 못했어요"
TOO_LARGE: Final = "파일이 너무 크거나 복잡해요 — 받은 양식에 값만 넣어 주세요"
NOT_TEMPLATE: Final = "이 해의 일괄업로드 양식이 아니에요"
TOO_MANY_LINES: Final = f"한 번에 {UPLOAD_LINES_MAX}줄까지 올려요 — 나눠서 올려 주세요"
BAD_ID: Final = "ID 칸이 양식과 달라요 — 받은 양식의 ID 를 그대로 두세요"
FORMULA: Final = "수식은 넣을 수 없어요 — 값으로 넣어 주세요"
SAME_LINE: Final = "같은 줄이 두 번이에요"

_HEAD_WIDTH: Final = len(TEMPLATE_HEAD)
_ID_COLUMN: Final = 1
_SITE_COLUMN: Final = 6
_UNIT_COLUMN: Final = 8
_CELL_REFUSED: Final[frozenset[ProblemKind]] = frozenset({"unsupported_cell_type", "bad_number"})
_TOO_LARGE: Final[frozenset[ProblemKind]] = frozenset(
    {
        "too_many_bytes",
        "too_many_entries",
        "entry_too_large",
        "opened_entries_too_large",
        "too_many_sheets",
        "too_many_shared_strings",
        "too_many_cells",
        "too_many_merges",
        "xml_too_deep",
        "too_many_xml_elements",
    }
)


@dataclass(frozen=True, slots=True)
class UploadProblem:
    """파일째 거절. 글에 칸 값은 없다."""

    message: str


@dataclass(frozen=True, slots=True)
class LineProblem:
    """줄·칸 하나의 오류. address = `<시트>!<칸>`."""

    address: str
    message: str


@dataclass(frozen=True, slots=True)
class UploadCell:
    label: str  # 그 칸의 1행 머리(`3월`·`2분기`·`2025년`)
    address: str  # `<시트>!<칸>`
    text: str


@dataclass(frozen=True, slots=True)
class UploadLine:
    sheet: str
    period: str  # 시트의 주기(month·quarter·year)
    row: int
    address: str  # `<시트>!A<행>` — 줄 오류의 주소
    node_id: int
    site: str
    unit: str
    cells: tuple[UploadCell, ...]


@dataclass(frozen=True, slots=True)
class UploadBook:
    lines: tuple[UploadLine, ...]
    problems: tuple[LineProblem, ...]


@dataclass(frozen=True, slots=True)
class _MergeSpans:
    """A 열 병합: 시작 줄 차례의 (시작 줄, 끝 줄)."""

    starts: tuple[int, ...]
    ends: tuple[int, ...]

    def anchor_of(self, row: int) -> int:
        """그 줄의 A 값이 있는 줄(병합 밖이면 그 줄)."""
        index = bisect_right(self.starts, row) - 1
        return self.starts[index] if index >= 0 and row <= self.ends[index] else row


def _text(cell: Cell | None) -> str:
    """칸의 글자(앞뒤 공백 걷음). 없는 칸·수식은 빈 글자."""
    if isinstance(cell, NumberCell):
        return cell.decimal
    return cell.text.strip() if isinstance(cell, TextCell) else ""


def _exact(cell: Cell | None) -> str:
    """수정하지 않는 글자 칸(사업장·단위) — 이름의 공백까지 그대로 대 본다."""
    return cell.text if isinstance(cell, TextCell) else _text(cell)


def _reader_problem(problem: ReaderProblem) -> UploadProblem:
    if problem.kind in _CELL_REFUSED:
        _, _, address = problem.where.rpartition("!")
        return UploadProblem(f"{address} 칸을 읽지 못했어요 — 값을 고쳐 다시 올려 주세요")
    return UploadProblem(TOO_LARGE if problem.kind in _TOO_LARGE else NOT_XLSX)


def _spans(sheet: Sheet) -> _MergeSpans | None:
    """병합을 한 번 파싱한다. 주소가 틀렸거나 A 열 병합이 겹치면 None."""
    found: list[tuple[int, int]] = []
    for merge in sheet.merges:
        cells = parse_range(merge)
        if isinstance(cells, AddressProblem):
            return None
        if cells.first.column == _ID_COLUMN:
            found.append((cells.first.row, cells.last.row))
    found.sort()
    if any(after[0] <= before[1] for before, after in pairwise(found)):
        return None
    return _MergeSpans(tuple(start for start, _ in found), tuple(end for _, end in found))


def _head_is(sheet: Sheet, columns: tuple[str, ...]) -> bool:
    found: dict[int, str] = {}
    for address, cell in sheet.cells.items():
        where = parse_address(address)
        if not isinstance(where, AddressProblem) and where.row == 1:
            found[where.column] = cell.text if isinstance(cell, TextCell) else ""
    return found == dict(enumerate(columns, start=1))


def _sheets_of(book: Workbook, year: int) -> list[tuple[Sheet, str, tuple[str, ...]]] | None:
    """양식 차례의 (시트, 주기, 머리). 시트 셋·머리가 그 해 양식과 글자까지 같지 않으면 None."""
    by_name = {sheet.name: sheet for sheet in book.sheets}
    if set(by_name) != set(TEMPLATE_SHEETS):
        return None
    found: list[tuple[Sheet, str, tuple[str, ...]]] = []
    for name, period in zip(TEMPLATE_SHEETS, PERIODS, strict=True):
        columns = template_columns(year, period)
        if not _head_is(by_name[name], columns):
            return None
        found.append((by_name[name], period, columns))
    return found


def _value_rows(sheet: Sheet, width: int) -> dict[int, list[int]]:
    """값 칸에 무엇이든 찬 줄 → 그 칸 열 번호(열 차례). 공백만인 칸은 빈 칸이다."""
    rows: dict[int, list[int]] = {}
    for address, cell in sheet.cells.items():
        where = parse_address(address)
        if isinstance(where, AddressProblem) or where.row == 1:
            continue
        if _HEAD_WIDTH < where.column <= width and (isinstance(cell, FormulaCell) or _text(cell) != ""):
            rows.setdefault(where.row, []).append(where.column)
    return {row: sorted(columns) for row, columns in sorted(rows.items())}


def _node_id(sheet: Sheet, spans: _MergeSpans, row: int) -> int | None:
    text = _text(sheet.cells.get(format_address(CellAddress(spans.anchor_of(row), _ID_COLUMN))))
    if not text.isascii() or not text.isdecimal() or len(text) > 18:
        return None
    return int(text)


def _read_sheet(
    sheet: Sheet, period: str, columns: tuple[str, ...], spans: _MergeSpans
) -> tuple[list[UploadLine], list[LineProblem], int]:
    """그 시트의 줄 · 오류 · 값이 찬 줄 수(오류 줄 포함)."""
    lines: list[UploadLine] = []
    problems: list[LineProblem] = []
    seen: set[tuple[int, str]] = set()
    rows = _value_rows(sheet, len(columns))
    for row, filled in rows.items():
        line_address = f"{sheet.name}!{format_address(CellAddress(row, _ID_COLUMN))}"
        node_id = _node_id(sheet, spans, row)
        site = _exact(sheet.cells.get(format_address(CellAddress(row, _SITE_COLUMN))))
        unit = _exact(sheet.cells.get(format_address(CellAddress(row, _UNIT_COLUMN))))
        if node_id is None:
            problems.append(LineProblem(line_address, BAD_ID))
            continue
        if (node_id, site) in seen:
            problems.append(LineProblem(line_address, SAME_LINE))
            continue
        seen.add((node_id, site))
        cells: list[UploadCell] = []
        for column in filled:
            address = format_address(CellAddress(row, column))
            where = f"{sheet.name}!{address}"
            cell = sheet.cells[address]
            if isinstance(cell, FormulaCell):
                problems.append(LineProblem(where, FORMULA))
            else:
                cells.append(UploadCell(columns[column - 1], where, _text(cell)))
        lines.append(UploadLine(sheet.name, period, row, line_address, node_id, site, unit, tuple(cells)))
    return lines, problems, len(rows)


def read_upload(data: bytes, year: int) -> UploadBook | UploadProblem:
    """어떤 바이트를 받아도 예외를 내지 않는다. 줄은 시트 차례(년도·분기·월) → 행 차례다."""
    book = read_workbook(data, max_bytes=GHG_UPLOAD_MAX_BYTES)
    if isinstance(book, ReaderProblem):
        return _reader_problem(book)
    sheets = _sheets_of(book, year)
    if sheets is None:
        return UploadProblem(NOT_TEMPLATE)
    lines: list[UploadLine] = []
    problems: list[LineProblem] = []
    filled = 0
    for sheet, period, columns in sheets:
        spans = _spans(sheet)
        if spans is None:
            return UploadProblem(NOT_TEMPLATE)
        found, wrong, count = _read_sheet(sheet, period, columns, spans)
        lines += found
        problems += wrong
        filled += count
    if filled > UPLOAD_LINES_MAX:
        return UploadProblem(TOO_MANY_LINES)
    return UploadBook(tuple(lines), tuple(problems))
