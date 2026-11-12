"""계수 책의 적재기: 읽힌 표(`Workbook`) → `FactorBook`. 파일도 DB 도 없다. 저장하지 않는다.

**읽힌 그대로 싣는다.** 하지 않는 것:
- 단위를 접거나 환산하지 않는다(L ↔ kg, kg ↔ t). 단위는 머리글 속 표기와 단위 열의 글자를 둘 다 원문으로 싣는다.
- 평균 줄을 뜻으로 가르지 않는다(값 열에 값이 있으면 계수 행이다. 빈 칸의 꼴만 남는다).
- `-` 를 0 으로 읽지 않는다(`Placeholder("-")`).
- 원화 열 셋 가운데 하나를 고르지 않는다. 수식을 다시 셈하지 않고, 공유 수식의 딸린 칸에 식을 지어 넣지 않는다.
- 같은 이름의 줄을 합치지 않는다. 값이 0 인 줄을 빼지 않는다. 빈 줄에서 읽기를 멈추지 않는다.
전력 계수의 값이 시트마다 다른 것, 휘발유·경유의 단위가 시트마다 다른 것은 마크스폰의 답 전이다. 여기서 고르지 않는다.

**칸 회계.** 적재된 시트마다 그 시트의 모든 칸이 제목·머리글 / 이름표 / 값 / 파생 / 덧붙은 칸 / 주석 /
(목록 시트의) 탭 안내 가운데 정확히 한 곳에 든다. 회계는 결과(행·주석·제목)에 실제로 실린 칸에서 다시 센다.
어디에도 안 든 칸은 버리지 않고 `Unaccounted` 로 `problems` 에 낸다.

줄의 갈래(머리글 줄 아래): 값 열에 칸이 하나라도 있으면 계수 행. 값 열이 다 비면 그 줄의 칸은 주석이다.
값 열에 든 수식 칸은 실을 자리가 없다(값은 수·글자·빈 칸뿐이다) — 그 칸은 `Unaccounted` 로 나온다.
"""

from dataclasses import dataclass

from esgapi.inventory.tools.scope3_sheets.factor_layout import (
    FACTOR_SHEETS,
    INDEX_SHEET,
    Column,
    FactorSheetShape,
    IndexSheetShape,
)
from esgapi.inventory.tools.scope3_sheets.grid import (
    AddressProblem,
    Cell,
    FormulaCell,
    NumberCell,
    Sheet,
    TextCell,
    Workbook,
    column_letters,
    parse_address,
)


@dataclass(frozen=True, slots=True)
class Placeholder:
    """값 자리에 든 글자(`-` 등). 0 도 빈 칸도 아니다."""

    text: str


@dataclass(frozen=True, slots=True)
class Empty:
    """값 자리가 비었다."""


@dataclass(frozen=True, slots=True)
class LabelEntry:
    column: str
    header: str
    cell: Cell  # 수로 든 이름표는 수인 채로


@dataclass(frozen=True, slots=True)
class ValueEntry:
    column: str
    header: str
    unit: str | None  # 머리글 속 단위 표기(원문)
    unit_cell: Cell | None  # 그 줄의 단위 열에 든 칸(원문). 단위 열이 없거나 비면 None
    content: NumberCell | Placeholder | Empty


@dataclass(frozen=True, slots=True)
class DerivedEntry:
    column: str
    header: str
    formula: str | None  # 그 칸의 식 글자. 공유 수식의 딸린 칸은 None
    master: str | None  # 공유 묶음의 으뜸 칸 주소. 공유 수식이 아니면 None
    master_formula: str | None  # 으뜸 칸의 식 글자(딸린 칸의 식이 아니다 — 밀어 옮기지 않은 원문)
    cached: TextCell | NumberCell | None  # 파일에 저장돼 있던 값


@dataclass(frozen=True, slots=True)
class ExtraEntry:
    column: str  # 머리글이 없는 열
    cell: Cell


@dataclass(frozen=True, slots=True)
class FactorRow:
    sheet: str
    row: int
    labels: tuple[LabelEntry, ...]
    values: tuple[ValueEntry, ...]  # 값 열마다 하나(비었으면 Empty)
    derived: tuple[DerivedEntry, ...]
    extras: tuple[ExtraEntry, ...]


@dataclass(frozen=True, slots=True)
class Note:
    """계수 행이 아닌 줄의 칸(제목, 산정식, 출처 각주)."""

    sheet: str
    cell: str
    content: Cell


@dataclass(frozen=True, slots=True)
class SheetLink:
    """`목록` 시트의 한 줄: 템플릿의 탭 ↔ 책의 탭."""

    row: int
    template_tab: Cell | None
    book_tab: Cell | None
    extras: tuple[ExtraEntry, ...]


@dataclass(frozen=True, slots=True)
class SheetAccount:
    """한 시트의 칸 회계. 갈래별 수의 합 + unaccounted == total."""

    sheet: str
    total: int
    title_header: int
    label: int
    value: int
    derived: int
    extra: int
    note: int
    link: int
    unaccounted: int


@dataclass(frozen=True, slots=True)
class HeaderMismatch:
    sheet: str
    cell: str
    expected: str | None  # None = 꼴에 없는 머리글 칸이 있다
    found: str | None  # None = 그 칸이 비었거나 글자가 아니다


@dataclass(frozen=True, slots=True)
class UnknownSheet:
    sheet: str


@dataclass(frozen=True, slots=True)
class MissingSheet:
    sheet: str


@dataclass(frozen=True, slots=True)
class Unaccounted:
    sheet: str
    cell: str


FactorProblem = HeaderMismatch | UnknownSheet | MissingSheet | Unaccounted


@dataclass(frozen=True, slots=True)
class FactorBook:
    rows: tuple[FactorRow, ...]
    notes: tuple[Note, ...]  # 머리글 줄 아래의 주석 칸
    titles: tuple[Note, ...]  # 머리글 줄과 그 위(제목·묶음 머리글·머리글)
    sheet_links: tuple[SheetLink, ...]
    accounts: tuple[SheetAccount, ...]  # 적재된 시트만
    sheet_names: tuple[str, ...]  # 책의 시트 이름(파일의 차례)
    problems: tuple[FactorProblem, ...]


def load_factor_book(workbook: Workbook) -> FactorBook:
    shapes = {shape.name: shape for shape in FACTOR_SHEETS}
    rows: list[FactorRow] = []
    notes: list[Note] = []
    titles: list[Note] = []
    links: list[SheetLink] = []
    accounts: list[SheetAccount] = []
    problems: list[FactorProblem] = []
    present = {sheet.name for sheet in workbook.sheets}
    for name in (INDEX_SHEET.name, *shapes):
        if name not in present:
            problems.append(MissingSheet(name))
    for sheet in workbook.sheets:
        if sheet.name == INDEX_SHEET.name:
            mismatches = _index_header_mismatches(sheet, INDEX_SHEET)
            if mismatches:
                problems.extend(mismatches)
                continue
            sheet_titles, sheet_links = _load_index(sheet, INDEX_SHEET)
            sheet_rows: list[FactorRow] = []
            sheet_notes: list[Note] = []
        elif sheet.name in shapes:
            shape = shapes[sheet.name]
            mismatches = _header_mismatches(sheet, shape)
            if mismatches:
                problems.extend(mismatches)
                continue
            sheet_titles, sheet_rows, sheet_notes = _load_factor_sheet(sheet, shape)
            sheet_links = []
        else:
            problems.append(UnknownSheet(sheet.name))
            continue
        account, unaccounted = _account(sheet, sheet_titles, sheet_rows, sheet_notes, sheet_links)
        titles.extend(sheet_titles)
        rows.extend(sheet_rows)
        notes.extend(sheet_notes)
        links.extend(sheet_links)
        accounts.append(account)
        problems.extend(unaccounted)
    return FactorBook(
        tuple(rows),
        tuple(notes),
        tuple(titles),
        tuple(links),
        tuple(accounts),
        tuple(sheet.name for sheet in workbook.sheets),
        tuple(problems),
    )


def _by_row(sheet: Sheet) -> dict[int, list[tuple[str, Cell]]]:
    """줄 번호 → [(열 글자, 칸)] (열 차례). 주소의 꼴이 아닌 열쇠는 넣지 않는다(회계가 Unaccounted 로 낸다)."""
    found: dict[int, list[tuple[int, Cell]]] = {}
    for address, cell in sheet.cells.items():
        parsed = parse_address(address)
        if isinstance(parsed, AddressProblem) or f"{column_letters(parsed.column)}{parsed.row}" != address:
            continue
        found.setdefault(parsed.row, []).append((parsed.column, cell))
    return {
        row: [(column_letters(column), cell) for column, cell in sorted(cells, key=_first)]
        for row, cells in found.items()
    }


def _first(pair: tuple[int, Cell]) -> int:
    return pair[0]


def _text_at(sheet: Sheet, address: str) -> str | None:
    cell = sheet.cells.get(address)
    return cell.text if isinstance(cell, TextCell) else None


def _header_mismatches(sheet: Sheet, shape: FactorSheetShape) -> list[HeaderMismatch]:
    expected = {f"{column.letter}{shape.header_row}": column.header for column in shape.columns}
    expected.update(dict(shape.group_headers))
    found = [
        HeaderMismatch(sheet.name, address, text, _text_at(sheet, address))
        for address, text in expected.items()
        if _text_at(sheet, address) != text
    ]
    for letter, _ in _by_row(sheet).get(shape.header_row, []):
        address = f"{letter}{shape.header_row}"
        if address not in expected:
            found.append(HeaderMismatch(sheet.name, address, None, _text_at(sheet, address)))
    return found


def _index_header_mismatches(sheet: Sheet, shape: IndexSheetShape) -> list[HeaderMismatch]:
    expected = {
        f"{shape.template_column}{shape.header_row}": shape.template_header,
        f"{shape.book_column}{shape.header_row}": shape.book_header,
    }
    return [
        HeaderMismatch(sheet.name, address, text, _text_at(sheet, address))
        for address, text in expected.items()
        if _text_at(sheet, address) != text
    ]


def _load_factor_sheet(sheet: Sheet, shape: FactorSheetShape) -> tuple[list[Note], list[FactorRow], list[Note]]:
    columns = {column.letter: column for column in shape.columns}
    value_columns = [column for column in shape.columns if column.role == "value"]
    unit_column = next((column.letter for column in shape.columns if column.role == "unit"), None)
    titles: list[Note] = []
    rows: list[FactorRow] = []
    notes: list[Note] = []
    by_row = _by_row(sheet)
    for row in sorted(by_row):
        cells = dict(by_row[row])
        if row <= shape.header_row:
            titles.extend(Note(sheet.name, f"{letter}{row}", cell) for letter, cell in cells.items())
            continue
        # 값 열에 칸이 하나라도 있으면 계수 행이다. 빈 줄 뒤에도 계속 본다(평균 줄이 뒤에 온다).
        if not any(column.letter in cells for column in value_columns):
            notes.extend(Note(sheet.name, f"{letter}{row}", cell) for letter, cell in cells.items())
            continue
        rows.append(_factor_row(sheet, row, cells, columns, value_columns, unit_column))
    return titles, rows, notes


def _factor_row(
    sheet: Sheet,
    row: int,
    cells: dict[str, Cell],
    columns: dict[str, Column],
    value_columns: list[Column],
    unit_column: str | None,
) -> FactorRow:
    labels: list[LabelEntry] = []
    derived: list[DerivedEntry] = []
    extras: list[ExtraEntry] = []
    for letter, cell in cells.items():
        column = columns.get(letter)
        if column is None:
            extras.append(ExtraEntry(letter, cell))  # 머리글 없는 열의 칸. 버리지 않는다
        elif column.role in ("label", "unit"):
            labels.append(LabelEntry(letter, column.header, cell))
        elif column.role == "derived" and isinstance(cell, FormulaCell):
            master = cell.shared.master if cell.shared is not None else None
            master_cell = sheet.cells.get(master) if master is not None else None
            master_formula = master_cell.formula if isinstance(master_cell, FormulaCell) else None
            derived.append(DerivedEntry(letter, column.header, cell.formula, master, master_formula, cell.cached))
        # 그 밖(값 열의 수식 칸, 파생 열의 수식 아닌 칸)은 어디에도 싣지 않는다 → 회계가 Unaccounted 로 낸다.
    unit_cell = cells.get(unit_column) if unit_column is not None else None
    values = tuple(
        ValueEntry(column.letter, column.header, column.unit, unit_cell, _content(cells.get(column.letter)))
        for column in value_columns
    )
    return FactorRow(sheet.name, row, tuple(labels), values, tuple(derived), tuple(extras))


def _content(cell: Cell | None) -> NumberCell | Placeholder | Empty:
    if isinstance(cell, NumberCell):
        return cell
    if isinstance(cell, TextCell):
        return Placeholder(cell.text)  # `-` 를 0 으로 읽지 않는다
    return Empty()


def _load_index(sheet: Sheet, shape: IndexSheetShape) -> tuple[list[Note], list[SheetLink]]:
    titles: list[Note] = []
    links: list[SheetLink] = []
    by_row = _by_row(sheet)
    for row in sorted(by_row):
        cells = dict(by_row[row])
        if row <= shape.header_row:
            titles.extend(Note(sheet.name, f"{letter}{row}", cell) for letter, cell in cells.items())
            continue
        extras = tuple(
            ExtraEntry(letter, cell)
            for letter, cell in cells.items()
            if letter not in (shape.template_column, shape.book_column)
        )
        links.append(SheetLink(row, cells.get(shape.template_column), cells.get(shape.book_column), extras))
    return titles, links


def _account(
    sheet: Sheet, titles: list[Note], rows: list[FactorRow], notes: list[Note], links: list[SheetLink]
) -> tuple[SheetAccount, list[Unaccounted]]:
    """결과에 실제로 실린 칸을 갈래별로 센다. 시트의 칸 가운데 어디에도 안 실린 것을 낸다."""
    title_cells = {note.cell for note in titles}
    note_cells = {note.cell for note in notes}
    label_cells = {f"{entry.column}{row.row}" for row in rows for entry in row.labels}
    value_cells = {
        f"{entry.column}{row.row}" for row in rows for entry in row.values if not isinstance(entry.content, Empty)
    }
    derived_cells = {f"{entry.column}{row.row}" for row in rows for entry in row.derived}
    extra_cells = {f"{entry.column}{row.row}" for row in rows for entry in row.extras}
    extra_cells |= {f"{entry.column}{link.row}" for link in links for entry in link.extras}
    link_cells: set[str] = set()
    for link in links:
        if link.template_tab is not None:
            link_cells.add(f"{INDEX_SHEET.template_column}{link.row}")
        if link.book_tab is not None:
            link_cells.add(f"{INDEX_SHEET.book_column}{link.row}")
    claimed = title_cells | note_cells | label_cells | value_cells | derived_cells | extra_cells | link_cells
    unaccounted = sorted((address for address in sheet.cells if address not in claimed), key=_address_order)
    account = SheetAccount(
        sheet=sheet.name,
        total=len(sheet.cells),
        title_header=len(title_cells),
        label=len(label_cells),
        value=len(value_cells),
        derived=len(derived_cells),
        extra=len(extra_cells),
        note=len(note_cells),
        link=len(link_cells),
        unaccounted=len(unaccounted),
    )
    return account, [Unaccounted(sheet.name, address) for address in unaccounted]


def _address_order(address: str) -> tuple[int, int, str]:
    parsed = parse_address(address)
    if isinstance(parsed, AddressProblem):
        return (0, 0, address)
    return (parsed.row, parsed.column, address)


def column_cells(book: FactorBook, sheet: str, column: str) -> tuple[tuple[int, Cell], ...]:
    """적재된 계수 행에서 한 이름표 열의 (줄 번호, 칸)을 줄 차례로. 빈 칸의 줄은 없다."""
    return tuple(
        (row.row, entry.cell)
        for row in book.rows
        if row.sheet == sheet
        for entry in row.labels
        if entry.column == column
    )
