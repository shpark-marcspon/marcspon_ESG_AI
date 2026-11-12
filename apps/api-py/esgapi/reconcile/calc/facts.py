"""값 후보 뽑기. 문서 모델과 엑셀 격자에서 숫자를 전부 찾아 ID 를 붙인다.

esg-lab `ts/reconcile/src/domain/facts.ts`(509줄)를 옮겼다.
여기서 정하는 것은 「어디에 어떤 글자로 있는가」와 「값 후보인가」까지다. 뜻(지표·기간·단위·범위)은 붙이지 않는다.

ID: 표의 숫자 칸 `<표ID>:r<행>c<열>`, 글 칸 속 `…#n<k>`, 블록 `<블록ID>#n<k>`.
k 는 그 글의 숫자 덩어리 순번이다 — **값이 아닌 덩어리도 번호를 먹는다**.

엑셀 쪽 꼴(`StoredNumber`, `Grid.numeric`·`refs`, `extract_grids`)도 같이 옮겼다. 그 격자를 엑셀 파일에서 만드는 일은
여기 없다.
"""

import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Final, Literal

from esgapi.reconcile.calc.dec import dec, shift10, show
from esgapi.reconcile.calc.jstext import WS, from_units, to_units
from esgapi.reconcile.calc.kinds import classify_kinds
from esgapi.reconcile.calc.notation import classify_cell, normalize_text, scan_numbers
from esgapi.reconcile.calc.types import (
    DocBlock,
    DocModel,
    Extraction,
    Fact,
    FactWhere,
    FailedTable,
    Grid,
    GridHeader,
    HeaderRef,
    Headers,
    NonValue,
    Span,
)

# 엑셀의 수식 칸에 저장된 결과가 없을 때 격자에 싣는 글자. 값을 지어내지 않고 「읽지 못한 숫자」로 남긴다. facts.ts:139
FORMULA_WITHOUT_RESULT: Final = "#수식 결과 없음"

# facts.ts:141. `i` 플래그는 ASCII 로만 접는다: 보는 글(머리글)은 NFKC 를 거쳐 `ſ`·`K`(켈빈)가 이미 없고,
# 파이썬의 유니코드 접기는 JS 와 달리 `ı`·`İ` 를 i 로 본다.
_PAGE_REFERENCE_HEADER: Final = re.compile(
    r"페이지|쪽수|^쪽\Z|page|보고 ?위치|문단 ?번호|조항", re.IGNORECASE | re.ASCII
)
_UNIT_LINE: Final = re.compile(rf"단위[{WS}]*[:：]")  # facts.ts:142
_TITLE_MAX: Final = 200  # facts.ts:143 (UTF-16 자리)
_UNIT_LINE_CELL_MAX: Final = 60  # facts.ts:407 (UTF-16 자리)
# 쪽 번호로 볼 조건: 숫자뿐인 블록이고, 쉼표 없는 네 자리 이하 정수이고, 쪽의 위·아래 가장자리(높이의 8%)에 있다.
# facts.ts:357
_PAGE_MARGIN_RATIO: Final = 0.08
_PAGE_NUMBER: Final = re.compile(r"[0-9]{1,4}")
_FOOTNOTE_LINE: Final = re.compile(rf"[{WS}]*(?:[0-9]{{1,2}}\)|\*|※|주[{WS}]*[0-9]*\))")  # facts.ts:376

Titles = Literal["before3", "own"]


def cell_id(row: int, col: int) -> str:
    return f"r{row}c{col}"


def _clip(text: str, limit: int) -> str:
    """JS 의 `text.slice(0, limit)` (UTF-16 자리)."""
    units = to_units(text)
    return text if len(units) <= limit else from_units(units[:limit])


def _is_data_number(text: str) -> bool:
    notation = classify_cell(text)
    return notation.kind == "value" and notation.number is not None and "year_like" not in notation.number.flags


def _at(row: Sequence[str], col: int) -> str:
    return row[col] if col < len(row) else ""


def estimate_header(cells: Sequence[Sequence[str]]) -> GridHeader:
    """머리글 행·열 추정. `py/docparse` 의 `estimate_header` 와 같은 규칙이다(엑셀 격자에 쓴다). facts.ts:153-174"""
    if len(cells) == 0:
        return GridHeader((), (), "empty")
    first_data = next((i for i, row in enumerate(cells) if any(_is_data_number(c) for c in row)), -1)
    if first_data == -1:
        rows = [0]
        basis = "no_numeric_row"
    else:
        rows = list(range(first_data))
        basis = "rows_before_first_numeric_row"
        while len(rows) > 1 and sum(1 for c in cells[rows[-1]] if c != "") <= 1:
            rows.pop()
    body = cells[len(rows) :]
    cols: list[int] = []
    for j in range(len(cells[0])):
        if any(_is_data_number(_at(row, j)) or classify_cell(_at(row, j)).kind == "no_value_marker" for row in body):
            break
        cols.append(j)
    return GridHeader(tuple(rows), tuple(cols), basis)


def inner_header_rows(grid: Grid) -> tuple[int, ...]:
    """본문 중간의 머리글 행(추정): 첫 값 행보다 아래에 있고, 값 칸(머리글 열이 아닌 칸)에 값 후보 숫자·값 없음 표시가
    없고
    글자 칸이 둘 이상인 행. 추출 상태가 정상인 표에서만 본다. facts.ts:181-197
    """
    if grid.status != "ok":
        return ()
    header_rows = set(grid.header.rows)
    header_cols = set(grid.header.cols)
    rows: list[int] = []
    seen_data = False
    for row, cells in enumerate(grid.cells):
        if row in header_rows:
            continue
        kinds = ["skip" if col in header_cols else classify_cell(cell).kind for col, cell in enumerate(cells)]
        data = any(kind in ("value", "no_value_marker", "multi_number", "range") for kind in kinds) or any(
            kinds[col] == "text_with_digits" and any(token.kind == "value" for token in scan_numbers(cell))
            for col, cell in enumerate(cells)
        )
        if data:
            seen_data = True
        elif seen_data and sum(1 for kind in kinds if kind in ("text", "year", "text_with_digits")) >= 2:
            rows.append(row)
    return tuple(rows)


def _cell(grid: Grid, row: int, col: int) -> str:
    """JS 의 `grid.cells[row]?.[col] ?? ""`."""
    if row < 0 or row >= len(grid.cells):
        return ""
    cells = grid.cells[row]
    return cells[col] if 0 <= col < len(cells) else ""


def _header_rows_for(grid: Grid, inner_headers: tuple[int, ...], row: int) -> tuple[int, ...]:
    """이 행에 적용할 머리글 행: 위쪽에 본문 중간의 머리글 행이 있으면 가장 가까운 묶음, 없으면 표 맨 위의 머리글 행."""
    inner = [r for r in inner_headers if r < row]
    if not inner:
        return grid.header.rows
    block = [inner[-1]]
    i = len(inner) - 2
    while i >= 0 and inner[i] == block[0] - 1:
        block.insert(0, inner[i])
        i -= 1
    return tuple(block)


def _headers_for(grid: Grid, inner_headers: tuple[int, ...], row: int, col: int) -> Headers:
    header_rows = {*grid.header.rows, *inner_headers}
    row_refs: list[HeaderRef] = []
    # 이 행에 제 글자가 있는 머리글 열이 나오면, 그 오른쪽의 빈 칸은 위에서 물려받지 않는다.
    own_seen = False
    for j in grid.header.cols:
        own = normalize_text(_cell(grid, row, j))
        if own != "":
            own_seen = True
            row_refs.append(HeaderRef(cell_id(row, j), own, False))
            continue
        if own_seen:
            continue
        r = row - 1
        while r >= 0 and r not in header_rows and normalize_text(_cell(grid, r, j)) == "":
            r -= 1
        if r < 0 or r in header_rows:
            continue
        row_refs.append(HeaderRef(cell_id(r, j), normalize_text(_cell(grid, r, j)), True))
    col_refs: list[HeaderRef] = []
    for i in _header_rows_for(grid, inner_headers, row):
        c = col
        while c >= 0 and normalize_text(_cell(grid, i, c)) == "":
            c -= 1
        if c < 0:
            continue
        col_refs.append(HeaderRef(cell_id(i, c), normalize_text(_cell(grid, i, c)), c != col))
    return Headers(tuple(row_refs), tuple(col_refs))


def grid_facts(grid: Grid) -> tuple[list[Fact], list[NonValue]]:
    """격자 하나에서 값 후보와 그 밖의 숫자를 뽑는다. `(facts, non_values)`. facts.ts:241-354

    `grid.inner_headers` 가 None 이면 여기서 구해 쓴다(TS 는 격자에 적어 넣는다. 여기 격자는 얼어 있어
    적어 넣는 일은 `extract_document`·`extract_grids` 가 새 격자를 만들어 한다).
    """
    facts: list[Fact] = []
    non_values: list[NonValue] = []
    inner_headers = grid.inner_headers if grid.inner_headers is not None else inner_header_rows(grid)
    header_rows = {*grid.header.rows, *inner_headers}
    header_cols = set(grid.header.cols)
    for row, cells in enumerate(grid.cells):
        for col, raw in enumerate(cells):
            ref: str | None = None
            if grid.refs is not None and row < len(grid.refs) and col < len(grid.refs[row]):
                ref = grid.refs[row][col]
            where = FactWhere(grid.page, grid.sheet, grid.id, row, col, ref, None, None)
            stored = None
            if grid.numeric is not None and row < len(grid.numeric) and col < len(grid.numeric[row]):
                stored = grid.numeric[row][col]
            notation = classify_cell(raw)
            if raw == FORMULA_WITHOUT_RESULT:
                non_values.append(NonValue(grid.doc_id, where, raw, "formula_without_result"))
                continue
            if notation.kind in ("blank", "text") and stored is None:
                continue
            if row in header_rows or col in header_cols:
                if notation.kind != "no_value_marker":
                    non_values.append(NonValue(grid.doc_id, where, raw, "header"))
                continue
            headers = _headers_for(grid, inner_headers, row, col)
            marks = tuple(mark.mark for mark in grid.footnote_marks if mark.row == row and mark.col == col)
            page_ref = any(_PAGE_REFERENCE_HEADER.search(ref_.text) for ref_ in headers.col)

            if stored is not None:
                if stored.is_date:
                    shown = stored.display if stored.display is not None else stored.stored_raw
                    non_values.append(NonValue(grid.doc_id, where, shown, "date"))
                    continue
                negative = stored.stored.startswith("-")
                # 퍼센트 서식: 저장 값 0.123 은 12.3% 다. % 단위의 값으로 맞춘다(자리 옮김뿐이다).
                percent = stored.display_status == "rendered" and "%" in (stored.display or "")
                value = show(shift10(dec(stored.stored), 2)) if percent else stored.stored
                facts.append(
                    Fact(
                        id=f"{grid.id}:{cell_id(row, col)}",
                        doc_id=grid.doc_id,
                        bucket="table_cell",
                        where=where,
                        raw=stored.display if stored.display is not None else stored.stored_raw,
                        value=value,
                        decimals=len(value.split(".")[1]) if "." in value else 0,
                        sign="minus" if negative else "none",
                        percent=percent,
                        unit_suffix="%" if percent else None,
                        flags=("percent_format_scaled",) if percent else (),
                        footnote_marks=marks,
                        table_status=grid.status,
                        headers=headers,
                        stored=stored,
                        stored_as_text=False,
                    )
                )
                continue
            if notation.kind == "value" and notation.number is not None:
                if page_ref:
                    non_values.append(NonValue(grid.doc_id, where, raw, "page_reference"))
                    continue
                number = notation.number
                facts.append(
                    Fact(
                        id=f"{grid.id}:{cell_id(row, col)}",
                        doc_id=grid.doc_id,
                        bucket="table_cell",
                        where=where,
                        raw=raw,
                        value=number.value,
                        decimals=number.decimals,
                        sign=number.sign,
                        percent=number.percent,
                        unit_suffix=number.unit_suffix,
                        flags=number.flags,
                        footnote_marks=marks,
                        table_status=grid.status,
                        headers=headers,
                        stored=None,
                        stored_as_text=grid.kind == "sheet",
                    )
                )
                continue
            if notation.kind in ("no_value_marker", "year", "code", "date"):
                non_values.append(NonValue(grid.doc_id, where, raw, notation.kind))
                continue
            # 범위, 숫자 여럿, 글 속 숫자: 칸 안의 숫자 덩어리를 하나씩 본다.
            if page_ref:
                non_values.append(NonValue(grid.doc_id, where, raw, "page_reference"))
                continue
            for index, token in enumerate(scan_numbers(raw)):
                token_where = replace(where, span=Span(token.start, token.end, token.occurrence))
                if token.kind != "value":
                    non_values.append(NonValue(grid.doc_id, token_where, token.raw, token.kind))
                    continue
                if token.number is None:  # 값 갈래에는 늘 읽은 수가 있다(scan_numbers)
                    continue
                if notation.kind == "range":
                    non_values.append(NonValue(grid.doc_id, token_where, token.raw, "range_part"))
                    continue
                facts.append(
                    Fact(
                        id=f"{grid.id}:{cell_id(row, col)}#n{index + 1}",
                        doc_id=grid.doc_id,
                        bucket="table_text_cell",
                        where=token_where,
                        raw=token.raw,
                        value=token.number.value,
                        decimals=token.number.decimals,
                        sign=token.number.sign,
                        percent=token.number.percent,
                        unit_suffix=token.number.unit_suffix,
                        flags=token.number.flags,
                        footnote_marks=marks,
                        table_status=grid.status,
                        headers=headers,
                        stored=None,
                        stored_as_text=False,
                    )
                )
    return facts, non_values


def _is_page_number(raw: str, bbox: tuple[float, float, float, float], page_height: float | None) -> bool:
    if page_height is None or not _PAGE_NUMBER.fullmatch(normalize_text(raw)):
        return False
    y0, y1 = bbox[1], bbox[3]
    return y1 <= page_height * _PAGE_MARGIN_RATIO or y0 >= page_height * (1 - _PAGE_MARGIN_RATIO)


def _is_text_block(block: DocBlock) -> bool:
    return block.kind != "table" and classify_cell(block.text or "").kind in ("text", "text_with_digits")


def _own_titles(page_blocks: Sequence[DocBlock], block: DocBlock | None) -> tuple[str, ...]:
    """그 표의 제목(앞 표 뒤부터 이 표 앞까지, 각주 꼴은 앞 표의 것이라 뺀다)과 그 표의 각주(표 바로 뒤에 이어지는 각주
    꼴의 글).

    facts.ts:480-497
    """
    if block is None:
        return ()
    ordered = sorted(page_blocks, key=lambda item: item.order)
    earlier_tables = [other for other in ordered if other.kind == "table" and other.order < block.order]
    previous_table = earlier_tables[-1] if earlier_tables else None
    titles = [
        other
        for other in ordered
        if other.order < block.order
        and (previous_table is None or other.order > previous_table.order)
        and _is_text_block(other)
        and not _FOOTNOTE_LINE.match(other.text or "")
    ]
    titles.reverse()
    out = [_clip(normalize_text(other.text or ""), _TITLE_MAX) for other in titles[:3]]
    for other in ordered:
        if other.order <= block.order:
            continue
        if other.kind == "table" or not _is_text_block(other) or not _FOOTNOTE_LINE.match(other.text or ""):
            break
        out.append(_clip(normalize_text(other.text or ""), _TITLE_MAX))
    return tuple(out)


def extract_document(document: DocModel, doc_id: str, *, titles: Titles = "before3", kinds: bool = False) -> Extraction:
    """문서 모델 하나에서 격자와 값 후보를 뽑는다. facts.ts:379-477

    `titles`: 표 제목 후보를 고르는 방법. 기본 `before3` 은 표 앞의 글 블록 셋(옆 표의 제목·각주가 섞일 수 있다),
    `own` 은 그 표의 제목과 그 표의 각주만.
    `kinds`: 값 후보마다 종류를 붙인다(`kinds.py`). 기본은 끔. 켜도 값 후보는 버리지 않는다.
    """
    grids: list[Grid] = []
    facts: list[Fact] = []
    non_values: list[NonValue] = []
    failed_tables: list[FailedTable] = []
    heights = {page.page: page.height for page in document.pages}
    blocks_by_page: dict[int, list[DocBlock]] = {}
    for block in document.blocks:
        blocks_by_page.setdefault(block.page, []).append(block)
    table_block = {block.table_id: block for block in document.blocks if block.kind == "table"}

    for table in document.tables:
        if table.status == "failed":
            failed_tables.append(FailedTable(table.id, table.page))
            continue
        block = table_block.get(table.id)
        page_blocks = blocks_by_page.get(table.page, [])
        before_blocks = (
            [other for other in page_blocks if other.order < block.order and _is_text_block(other)]
            if block is not None
            else []
        )
        before_blocks.sort(key=lambda other: -other.order)
        before = [_clip(normalize_text(other.text or ""), _TITLE_MAX) for other in before_blocks[:3]]
        title_candidates = _own_titles(page_blocks, block) if titles == "own" else tuple(before)
        unit_lines = [text for text in before if _UNIT_LINE.search(text)]
        for cells in table.cells:
            for cell in cells:
                text = normalize_text(cell)
                if _UNIT_LINE.search(text) and len(to_units(text)) <= _UNIT_LINE_CELL_MAX:
                    unit_lines.append(text)
        grid = Grid(
            id=table.id,
            doc_id=doc_id,
            kind="pdf_table",
            page=table.page,
            sheet=None,
            cells=table.cells,
            header=table.header,
            status=table.status,
            footnote_marks=table.footnote_marks,
            title_candidates=title_candidates,
            unit_lines=tuple(dict.fromkeys(unit_lines)),
        )
        grid = replace(grid, inner_headers=inner_header_rows(grid))
        grids.append(grid)
        grid_found, grid_other = grid_facts(grid)
        facts.extend(grid_found)
        non_values.extend(grid_other)

    for block in document.blocks:
        if block.kind == "table" or block.text is None:
            continue
        text = block.text
        whole = classify_cell(text)
        if whole.kind in ("blank", "text"):
            continue
        number_only = whole.kind != "text_with_digits"
        if number_only and _is_page_number(text, block.bbox, heights.get(block.page)):
            where = FactWhere(block.page, None, None, None, None, None, block.id, None)
            non_values.append(NonValue(doc_id, where, text, "page_number"))
            continue
        for index, token in enumerate(scan_numbers(text)):
            span = Span(token.start, token.end, token.occurrence)
            token_where = FactWhere(block.page, None, None, None, None, None, block.id, span)
            if token.kind != "value":
                non_values.append(NonValue(doc_id, token_where, token.raw, token.kind))
                continue
            if token.number is None:  # 값 갈래에는 늘 읽은 수가 있다(scan_numbers)
                continue
            facts.append(
                Fact(
                    id=f"{block.id}#n{index + 1}",
                    doc_id=doc_id,
                    bucket="number_only_block" if number_only else "sentence",
                    where=token_where,
                    raw=token.raw,
                    value=token.number.value,
                    decimals=token.number.decimals,
                    sign=token.number.sign,
                    percent=token.number.percent,
                    unit_suffix=token.number.unit_suffix,
                    flags=token.number.flags,
                    footnote_marks=(),
                    table_status=None,
                    headers=None,
                    stored=None,
                    stored_as_text=False,
                )
            )

    extraction = Extraction(
        doc_id=doc_id,
        file_name=document.source.file_name,
        grids=tuple(grids),
        facts=tuple(facts),
        non_values=tuple(non_values),
        failed_tables=tuple(failed_tables),
        pages_without_text=tuple(page.page for page in document.pages if page.text_layer == "none"),
    )
    if kinds:
        extraction = replace(extraction, kinds=classify_kinds(document, extraction))
    return extraction


def extract_grids(grids: Sequence[Grid], doc_id: str, file_name: str) -> Extraction:
    """엑셀 격자 묶음에서 값 후보를 뽑는다. facts.ts:500-509"""
    facts: list[Fact] = []
    non_values: list[NonValue] = []
    kept: list[Grid] = []
    for grid in grids:
        ready = grid if grid.inner_headers is not None else replace(grid, inner_headers=inner_header_rows(grid))
        kept.append(ready)
        grid_found, grid_other = grid_facts(ready)
        facts.extend(grid_found)
        non_values.extend(grid_other)
    return Extraction(doc_id, file_name, tuple(kept), tuple(facts), tuple(non_values), (), ())
