"""값 후보 뽑기의 머리글 찾기(calc/facts.py 의 _headers_for·_header_rows_for·inner_header_rows·estimate_header)를
전체 == 로 견준다(FT1, MARC-ISSUE-155 의 표 2).

비공개 함수도 직접 부른다(순수 함수다). 결과는 Headers·튜플·GridHeader 전체로 견주고, 한 번은 같은 격자를
extract_document 의 Extraction 전체로 본다. 기대값은 자료 꼴 생성자와 글자·수로만 짓고 격자는 시험 안에서 짓는다.
기대값은 운영 코드가 지금 내는 값을 옮긴 것이고 facts.py 와 대조했다(FT1 보고 §3).
★ 표와 숫자는 전부 지어낸 것이다(synthetic).
"""

from esgapi.reconcile.calc.facts import (
    _header_rows_for,  # pyright: ignore[reportPrivateUsage]
    _headers_for,  # pyright: ignore[reportPrivateUsage]
    estimate_header,
    extract_document,
    inner_header_rows,
)
from esgapi.reconcile.calc.types import (
    DocBlock,
    DocModel,
    DocPage,
    DocSource,
    DocTable,
    Extraction,
    Fact,
    FactWhere,
    Grid,
    GridHeader,
    GridStatus,
    HeaderRef,
    Headers,
    NonValue,
    Span,
)


def grid(cells: list[list[str]], rows: tuple[int, ...], cols: tuple[int, ...], status: GridStatus = "ok") -> Grid:
    """입력 격자를 짓는다(머리글은 주어진 대로 — estimate_header 를 부르지 않는다)."""
    return Grid(
        id="g",
        doc_id="d",
        kind="pdf_table",
        page=1,
        sheet=None,
        cells=tuple(tuple(row) for row in cells),
        header=GridHeader(rows, cols, "given"),
        status=status,
        footnote_marks=(),
        title_candidates=(),
        unit_lines=(),
    )


def where(page: int, *, grid: str, row: int, col: int, span: Span | None = None) -> FactWhere:
    """기대값을 짓는 도우미(대상 함수를 부르지 않는다)."""
    return FactWhere(page, None, grid, row, col, None, None, span)


def test_headers_scan_up_for_row_headers_and_left_for_column_headers_and_the_grid_gives_the_whole_extraction() -> None:
    # 열 머리: 빈 칸이면 왼쪽으로 훑고(한 칸·세 칸, 짧은 머리글 행 밖은 빈 칸), 0 열까지 비면 그 머리글 행은
    # 건너뛴다. 행 머리: 빈 칸이면 위로 훑어 물려받고(둘 이상 건너뜀), 머리글 행에 닿으면 멈춘다. 제 글자가 있는
    # 머리글 열 뒤의 빈 열은 물려받지 않는다. 같은 격자를 문서의 표로 뽑아 Extraction 전체로도 본다.
    # `wide` 를 먼저 견준다(1 행 2 열이 맨 앞): 왼쪽 훑기가 1 열에 머물거나(`c = 1`) 오른쪽으로 가는(`c += 1`) 변이는
    # 빈 칸에서 끝나지 않으니 그 전에 빨개져야 한다.
    # 머리글 행 하나가 짧다(네 칸). 열 머리글은 왼쪽으로 한 칸·세 칸 훑고, 짧은 행 밖의 칸은 빈 칸이다.
    wide = grid([["구분", "2023", "", "2024"], ["가", "1", "2", "3", "4", "5", "6"]], (0,), (0,))

    # 머리글 행 둘(0·1)·머리글 열 둘(0·1). 6 행은 짧은 행이다.
    merged = grid(
        [
            ["", "", "", "2023", "", ""],
            ["구분", "", "", "tCO2eq", "", "2024"],
            ["", "A", "1", "2", "3", "4"],
            ["가", "", "5", "6", "7", "8"],
            ["", "", "9", "10", "11", "12"],
            ["", "B", "13", "14", "15", "16"],
            ["", "C"],
            ["", "", "17"],
        ],
        (0, 1),
        (0, 1),
    )

    document = DocModel(
        source=DocSource("h.synthetic.pdf", "0" * 64, 1),
        pages=(DocPage(1, 800, "present"),),
        blocks=(DocBlock("g-block", "table", 1, (50, 400, 500, 600), 1, None, "g"),),
        tables=(DocTable("g", 1, merged.cells, merged.header, "lines", "ok", ()),),
    )
    assert _headers_for(wide, (), 1, 2) == Headers(
        row=(HeaderRef("r1c0", "가", False),), col=(HeaderRef("r0c1", "2023", True),)
    )
    assert _headers_for(wide, (), 1, 6) == Headers(
        row=(HeaderRef("r1c0", "가", False),), col=(HeaderRef("r0c3", "2024", True),)
    )
    assert _headers_for(wide, (), 1, 3) == Headers(
        row=(HeaderRef("r1c0", "가", False),), col=(HeaderRef("r0c3", "2024", False),)
    )
    assert _headers_for(merged, (), 2, 2) == Headers(
        row=(HeaderRef("r2c1", "A", False),), col=(HeaderRef("r1c0", "구분", True),)
    )
    assert _headers_for(merged, (), 3, 3) == Headers(
        row=(HeaderRef("r3c0", "가", False),),
        col=(HeaderRef("r0c3", "2023", False), HeaderRef("r1c3", "tCO2eq", False)),
    )
    assert _headers_for(merged, (), 4, 4) == Headers(
        row=(HeaderRef("r3c0", "가", True), HeaderRef("r2c1", "A", True)),
        col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c3", "tCO2eq", True)),
    )
    assert _headers_for(merged, (), 5, 5) == Headers(
        row=(HeaderRef("r3c0", "가", True), HeaderRef("r5c1", "B", False)),
        col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c5", "2024", False)),
    )
    assert _headers_for(merged, (), 7, 2) == Headers(
        row=(HeaderRef("r3c0", "가", True), HeaderRef("r6c1", "C", True)), col=(HeaderRef("r1c0", "구분", True),)
    )
    assert extract_document(document, "d") == Extraction(
        doc_id="d",
        file_name="h.synthetic.pdf",
        grids=(
            Grid(
                id="g",
                doc_id="d",
                kind="pdf_table",
                page=1,
                sheet=None,
                cells=(
                    ("", "", "", "2023", "", ""),
                    ("구분", "", "", "tCO2eq", "", "2024"),
                    ("", "A", "1", "2", "3", "4"),
                    ("가", "", "5", "6", "7", "8"),
                    ("", "", "9", "10", "11", "12"),
                    ("", "B", "13", "14", "15", "16"),
                    ("", "C"),
                    ("", "", "17"),
                ),
                header=GridHeader(rows=(0, 1), cols=(0, 1), basis="given"),
                status="ok",
                footnote_marks=(),
                title_candidates=(),
                unit_lines=(),
                inner_headers=(),
            ),
        ),
        facts=(
            Fact(
                id="g:r2c2",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=2, col=2),
                raw="1",
                value="1",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(row=(HeaderRef("r2c1", "A", False),), col=(HeaderRef("r1c0", "구분", True),)),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r2c3",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=2, col=3),
                raw="2",
                value="2",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r2c1", "A", False),),
                    col=(HeaderRef("r0c3", "2023", False), HeaderRef("r1c3", "tCO2eq", False)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r2c4",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=2, col=4),
                raw="3",
                value="3",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r2c1", "A", False),),
                    col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c3", "tCO2eq", True)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r2c5",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=2, col=5),
                raw="4",
                value="4",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r2c1", "A", False),),
                    col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c5", "2024", False)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r3c2",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=3, col=2),
                raw="5",
                value="5",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(row=(HeaderRef("r3c0", "가", False),), col=(HeaderRef("r1c0", "구분", True),)),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r3c3",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=3, col=3),
                raw="6",
                value="6",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", False),),
                    col=(HeaderRef("r0c3", "2023", False), HeaderRef("r1c3", "tCO2eq", False)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r3c4",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=3, col=4),
                raw="7",
                value="7",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", False),),
                    col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c3", "tCO2eq", True)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r3c5",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=3, col=5),
                raw="8",
                value="8",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", False),),
                    col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c5", "2024", False)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r4c2",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=4, col=2),
                raw="9",
                value="9",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r2c1", "A", True)),
                    col=(HeaderRef("r1c0", "구분", True),),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r4c3",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=4, col=3),
                raw="10",
                value="10",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r2c1", "A", True)),
                    col=(HeaderRef("r0c3", "2023", False), HeaderRef("r1c3", "tCO2eq", False)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r4c4",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=4, col=4),
                raw="11",
                value="11",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r2c1", "A", True)),
                    col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c3", "tCO2eq", True)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r4c5",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=4, col=5),
                raw="12",
                value="12",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r2c1", "A", True)),
                    col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c5", "2024", False)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r5c2",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=5, col=2),
                raw="13",
                value="13",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r5c1", "B", False)),
                    col=(HeaderRef("r1c0", "구분", True),),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r5c3",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=5, col=3),
                raw="14",
                value="14",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r5c1", "B", False)),
                    col=(HeaderRef("r0c3", "2023", False), HeaderRef("r1c3", "tCO2eq", False)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r5c4",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=5, col=4),
                raw="15",
                value="15",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r5c1", "B", False)),
                    col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c3", "tCO2eq", True)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r5c5",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=5, col=5),
                raw="16",
                value="16",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r5c1", "B", False)),
                    col=(HeaderRef("r0c3", "2023", True), HeaderRef("r1c5", "2024", False)),
                ),
                stored=None,
                stored_as_text=False,
            ),
            Fact(
                id="g:r7c2",
                doc_id="d",
                bucket="table_cell",
                where=where(1, grid="g", row=7, col=2),
                raw="17",
                value="17",
                decimals=0,
                sign="none",
                percent=False,
                unit_suffix=None,
                flags=(),
                footnote_marks=(),
                table_status="ok",
                headers=Headers(
                    row=(HeaderRef("r3c0", "가", True), HeaderRef("r6c1", "C", True)),
                    col=(HeaderRef("r1c0", "구분", True),),
                ),
                stored=None,
                stored_as_text=False,
            ),
        ),
        non_values=(
            NonValue("d", where(1, grid="g", row=0, col=3), "2023", "header"),
            NonValue("d", where(1, grid="g", row=1, col=3), "tCO2eq", "header"),
            NonValue("d", where(1, grid="g", row=1, col=5), "2024", "header"),
        ),
        failed_tables=(),
        pages_without_text=(),
    )


def test_without_header_rows_row_headers_scan_up_to_row_zero() -> None:
    # `tall` 을 먼저 견준다: 위 훑기가 1 행에 머무는(`r = 1`) 변이는 no_header_rows 에서 끝나지 않으니 그 전에
    # 빨개져야 한다.
    # 머리글 행이 없다(rows=()). 행 머리는 0 행까지 훑는다.
    no_header_rows = grid([["갑", "", "1"], ["", "", "2"]], (), (0, 1))
    # 위로 두 칸 올라가 2 행에서 멈춘다(1 행에도 글자가 있다).
    tall = grid([["", "1"], ["을", "2"], ["갑", "3"], ["", "4"], ["", "5"]], (), (0,))
    assert _headers_for(tall, (), 4, 1) == Headers(row=(HeaderRef("r2c0", "갑", True),), col=())
    assert _headers_for(no_header_rows, (), 1, 2) == Headers(row=(HeaderRef("r0c0", "갑", True),), col=())
    assert _headers_for(no_header_rows, (), 0, 2) == Headers(row=(HeaderRef("r0c0", "갑", False),), col=())


def test_rows_below_inner_headers_take_the_nearest_run_of_consecutive_inner_header_rows() -> None:
    # 안쪽 머리글 행이 이어진 셋(3·4·5)과 떨어진 것(2 와 5·6). 위에 안쪽 머리글이 없으면 표 맨 위의 머리글 행.
    table = grid([["구분", "값"]], (0,), (0,))
    assert _header_rows_for(table, (3, 4, 5), 6) == (3, 4, 5)
    assert _header_rows_for(table, (3, 4, 5), 4) == (3,)
    assert _header_rows_for(table, (3, 4, 5), 3) == (0,)
    assert _header_rows_for(table, (2, 5, 6), 7) == (5, 6)
    assert _header_rows_for(table, (2, 5, 6), 4) == (2,)
    assert _header_rows_for(table, (1, 2, 4, 5, 6), 9) == (4, 5, 6)


def test_inner_header_rows_are_text_rows_after_the_first_data_row() -> None:
    # 값 칸이 `-`·숫자 여럿·범위인 행은 데이터 행이다(글 칸이 둘 있어도). 연도 칸도 글 칸으로 센다. 첫 값 행 앞의
    # 글 행과 글 칸이 하나뿐인 행은 머리글이 아니다. 정상이 아닌 표에서는 찾지 않는다.
    cells = [
        ["구분", "가", "나", "다"],
        ["비고", "설명", "내용", "기타"],
        ["a", "1", "2", "3"],
        ["b", "-", "설명", "내용"],
        ["c", "10~20, 30", "설명", "내용"],
        ["d", "10~20", "설명", "내용"],
        ["소계", "FY2025", "설명", ""],
        ["e", "4", "5", "6"],
        ["f", "설명", "", ""],
        ["g", "합계", "총계", ""],
    ]
    assert inner_header_rows(grid(cells, (0,), (0,))) == (6, 9)
    assert inner_header_rows(grid(cells, (0,), (0,), "low_confidence")) == ()


def test_estimate_header_drops_group_title_rows_and_stops_at_value_or_no_value_columns() -> None:
    # 머리글 3 행에서 묶음 제목 행(글 칸 하나) 떼기, 글 칸 둘인 행은 남김, 맨 위 행은 남김. 값 없음 표시만 든 열은
    # 머리글 열이 아니다. 본문 행이 맨 위 행보다 짧아도 된다.

    assert estimate_header(
        [["구분", "2023", "2024"], ["가", "나", "다"], ["묶음", "", ""], ["x", "1", "2"]]
    ) == GridHeader(rows=(0, 1), cols=(0,), basis="rows_before_first_numeric_row")
    assert estimate_header([["구분", "2023", "2024"], ["묶음", "소계", ""], ["x", "1", "2"]]) == GridHeader(
        rows=(0, 1), cols=(0,), basis="rows_before_first_numeric_row"
    )
    assert estimate_header([["", "제목"], ["Scope 1", "100"]]) == GridHeader(
        rows=(0,), cols=(0,), basis="rows_before_first_numeric_row"
    )
    assert estimate_header([["구분", "가", "값"], ["a", "-", "1"]]) == GridHeader(
        rows=(0,), cols=(0,), basis="rows_before_first_numeric_row"
    )
    assert estimate_header([["구분", "항목", "값"], ["a"], ["b", "x", "1"]]) == GridHeader(
        rows=(0,), cols=(0, 1), basis="rows_before_first_numeric_row"
    )
