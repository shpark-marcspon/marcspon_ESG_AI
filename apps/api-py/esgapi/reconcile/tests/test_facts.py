"""값 후보 뽑기. TS `facts.test.ts` 10건과 `compare.test.ts` 의 「제목·각주 잇기」 2건의 뜻을 옮겼고,
`xlsx.test.ts` 가운데 격자에서 값 후보를 뽑는 부분(저장 값·퍼센트 서식·날짜·글자로 든 숫자·결과 없는 수식·머리글)을
**지은 격자**로 옮겼다(엑셀 파일을 읽는 일은 옮기지 않았다).

★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import pytest

from esgapi.reconcile.calc.count import count_ratio
from esgapi.reconcile.calc.facts import (
    FORMULA_WITHOUT_RESULT,
    cell_id,
    estimate_header,
    extract_document,
    extract_grids,
    grid_facts,
)
from esgapi.reconcile.calc.types import (
    NON_VALUE_CLASSES,
    DocBlock,
    DocModel,
    Extraction,
    Fact,
    FootnoteMark,
    Grid,
    GridHeader,
    StoredNumber,
)
from esgapi.reconcile.tests.support import HEADER, BlockSpec, TableSpec, synthetic_document


# 문서·뽑기는 시험마다(함수 범위) 짓는다. 모듈 상수로 두면 mutmut 이 변이를 켜기 전에 한 번 굳어 그 값만 읽는 시험이
# 어느 변이에서도 원본을 본다(scripts/weekly.sh 의 ② — 거짓 생존. MARC-ISSUE-154). synthetic_document 는 머리글을 안
# 준 표에 estimate_header 를 부르므로 문서도 시험 안에서 짓는다(FT1).
@pytest.fixture
def document() -> DocModel:
    return synthetic_document(
        "facts",
        [
            TableSpec(
                "p1-t1",
                before=["환경 성과 (synthetic)", "(단위: tCO2eq)"],
                cells=[
                    ["구분", "", "단위", "2023", "2024", "페이지"],
                    ["온실가스 배출량1)", "직접(Scope 1)", "tCO2eq", "1,200", "1,350", "46"],
                    ["", "간접(Scope 2)", "tCO2eq", "5,000", "-", "46"],
                    ["합계", "", "tCO2eq", "6,200", "기준연도 대비 42% 감축", "47~48"],
                    ["목표연도", "", "", "2030", "2050", ""],
                ],
                footnotes=[FootnoteMark(1, 3, "2)")],
            ),
            TableSpec(
                "p1-t2",
                status="low_confidence",
                header=HEADER,
                cells=[["막대", "값"], ["가", "116,818 15,649"], ["나", "300"]],
            ),
            TableSpec("p2-t1", page=2, status="failed", cells=[]),
        ],
        [
            BlockSpec("p1-b1", "2025년 Scope 1 배출량은 22,253 tCO2eq이다."),
            BlockSpec("p1-b2", "17", bbox=(280, 770, 300, 790)),
            BlockSpec("p1-b3", "116,818", bbox=(100, 300, 150, 320)),
        ],
        no_text_pages=[2],
    )


@pytest.fixture
def extraction(document: DocModel) -> Extraction:
    return extract_document(document, "a")


@pytest.fixture
def by_id(extraction: Extraction) -> dict[str, Fact]:
    return {fact.id: fact for fact in extraction.facts}


def classes(extraction: Extraction, raw: str) -> list[str]:
    return [item.cls for item in extraction.non_values if item.raw == raw]


def test_a_numeric_cell_carries_raw_value_place_footnote_and_table_status(by_id: dict[str, Fact]) -> None:
    fact = by_id["p1-t1:r1c3"]
    assert (fact.bucket, fact.raw, fact.value, fact.decimals) == ("table_cell", "1,200", "1200", 0)
    assert (fact.footnote_marks, fact.table_status) == (("2)",), "ok")
    assert (fact.where.page, fact.where.grid_id, fact.where.row, fact.where.col) == (1, "p1-t1", 1, 3)


def test_row_and_column_header_candidates_and_inheritance_from_merged_cells(by_id: dict[str, Fact]) -> None:
    headers = by_id["p1-t1:r2c3"].headers
    assert headers is not None
    assert [(ref.cell, ref.text, ref.inherited) for ref in headers.row] == [
        ("r1c0", "온실가스 배출량1)", True),
        ("r2c1", "간접(Scope 2)", False),
        ("r2c2", "tCO2eq", False),
    ]
    assert [(ref.cell, ref.text, ref.inherited) for ref in headers.col] == [("r0c3", "2023", False)]
    # 제 글자가 있는 행(`합계`)은 오른쪽 빈 칸을 윗 묶음에서 물려받지 않는다.
    total = by_id["p1-t1:r3c3"].headers
    assert total is not None
    assert [ref.text for ref in total.row] == ["합계", "tCO2eq"]


def test_title_and_unit_line_candidates_go_on_the_grid(extraction: Extraction) -> None:
    grid = next(item for item in extraction.grids if item.id == "p1-t1")
    # 가까운 것부터 세 개. 숫자뿐인 블록(p1-b2, p1-b3)은 빠진다.
    assert grid.title_candidates == (
        "(단위: tCO2eq)",
        "환경 성과 (synthetic)",
        "2025년 Scope 1 배출량은 22,253 tCO2eq이다.",
    )
    assert grid.unit_lines == ("(단위: tCO2eq)",)


def test_header_years_page_columns_no_value_markers_and_page_numbers_are_not_candidates(
    extraction: Extraction, by_id: dict[str, Fact]
) -> None:
    assert classes(extraction, "2023") == ["header"]  # 머리글 행의 숫자 (심은 파손 4 가 값 후보로 만든다)
    assert classes(extraction, "46") == ["page_reference", "page_reference"]
    assert classes(extraction, "47~48") == ["page_reference"]
    assert classes(extraction, "-") == ["no_value_marker"]
    assert classes(extraction, "17") == ["page_number"]  # 쪽의 아래 8% (심은 파손 5 가 끈다)
    assert "p1-t1:r1c5" not in by_id
    assert "p1-b2#n1" not in by_id
    assert all("r0c" not in fact.id for fact in extraction.facts)


def test_page_number_needs_the_page_margin_and_a_short_integer() -> None:
    def classes_of(text: str, bbox: tuple[float, float, float, float]) -> list[str]:
        found = extract_document(synthetic_document("p", [], [BlockSpec("b", text, bbox=bbox)]), "a")
        return [item.cls for item in found.non_values] + [fact.bucket for fact in found.facts]

    assert classes_of("17", (280, 736, 300, 750)) == ["page_number"]  # y0 = 800 × 0.92
    assert classes_of("17", (280, 735.9, 300, 750)) == ["number_only_block"]
    assert classes_of("17", (280, 50, 300, 64)) == ["page_number"]  # y1 = 800 × 0.08
    assert classes_of("17", (280, 50, 300, 64.1)) == ["number_only_block"]
    assert classes_of("12345", (280, 770, 300, 790)) == ["number_only_block"]  # 다섯 자리
    assert classes_of("1,234", (280, 770, 300, 790)) == ["number_only_block"]  # 쉼표


def test_a_year_like_number_in_the_body_stays_a_candidate_with_a_mark(by_id: dict[str, Fact]) -> None:
    fact = by_id["p1-t1:r4c3"]
    assert (fact.value, fact.flags) == ("2030", ("year_like",))


def test_numbers_in_text_cells_sentences_and_number_only_blocks_get_buckets(by_id: dict[str, Fact]) -> None:
    cell = by_id["p1-t1:r3c4#n1"]
    assert (cell.bucket, cell.raw, cell.value) == ("table_text_cell", "42%", "42")
    sentence = by_id["p1-b1#n3"]  # 순번은 값이 아닌 덩어리(2025, 1)도 센다 (심은 파손 6 이 값 후보만 센다)
    assert (sentence.bucket, sentence.raw, sentence.value) == ("sentence", "22,253", "22253")
    assert sentence.where.block_id == "p1-b1"
    assert sentence.where.span is not None
    assert sentence.where.span.occurrence == 1
    block = by_id["p1-b3#n1"]
    assert (block.bucket, block.value) == ("number_only_block", "116818")


def test_low_confidence_tables_keep_the_mark_and_failed_tables_and_textless_pages_are_listed(
    extraction: Extraction, by_id: dict[str, Fact]
) -> None:
    assert (by_id["p1-t2:r2c1"].table_status, by_id["p1-t2:r2c1"].value) == ("low_confidence", "300")
    second = by_id["p1-t2:r1c1#n2"]
    assert (second.bucket, second.table_status, second.value) == ("table_text_cell", "low_confidence", "15649")
    assert [(table.id, table.page) for table in extraction.failed_tables] == [("p2-t1", 2)]
    assert extraction.pages_without_text == (2,)


def test_non_candidate_numbers_in_a_paragraph_are_kept_with_their_class(extraction: Extraction) -> None:
    found = [(item.raw, item.cls) for item in extraction.non_values if item.where.block_id == "p1-b1"]
    assert found == [("2025", "year"), ("1", "identifier"), ("2", "identifier")]


def test_stacked_tables_use_the_nearest_inner_header_row() -> None:
    stacked = extract_document(
        synthetic_document(
            "stacked",
            [
                TableSpec(
                    "p1-t1",
                    cells=[
                        ["자산", "금액", "비중"],
                        ["대출", "100", "40%"],
                        ["채권", "150", "60%"],
                        ["자산", "Scope 1", "Scope 2"],
                        ["대출", "7", "9"],
                        ["비고", "전년 대비 10.7% 증가", "투자 418억 원"],
                    ],
                )
            ],
        ),
        "a",
    )
    assert stacked.grids[0].inner_headers == (3,)
    by_cell = {fact.id: [ref.text for ref in fact.headers.col] for fact in stacked.facts if fact.headers}
    assert by_cell["p1-t1:r1c1"] == ["금액"]
    assert by_cell["p1-t1:r4c1"] == ["Scope 1"]
    assert by_cell["p1-t1:r4c2"] == ["Scope 2"]
    assert "p1-t1:r3c1" not in by_cell
    # 글 속에 값 후보 숫자가 든 행은 머리글이 아니라 데이터 행이다.
    text_cell = next(fact for fact in stacked.facts if fact.id == "p1-t1:r5c1#n1")
    assert (text_cell.bucket, text_cell.raw) == ("table_text_cell", "10.7%")


def test_ratio_count_buckets_add_up_to_all_candidates(extraction: Extraction) -> None:
    ratio = count_ratio(extraction)
    assert ratio.value_candidates == len(extraction.facts)
    buckets = (
        ratio.table_cells_ok,
        ratio.table_cells_low_confidence,
        ratio.table_text_cells_ok,
        ratio.table_text_cells_low_confidence,
        ratio.sentences,
        ratio.number_only_blocks,
    )
    assert sum(buckets) == ratio.value_candidates
    assert buckets == (6, 1, 1, 2, 1, 1)
    assert (ratio.failed_tables, ratio.pages_without_text) == (1, 1)
    assert (ratio.tables_ok, ratio.tables_low_confidence) == (1, 1)
    assert sum(ratio.non_values.values()) == ratio.non_value_total == len(extraction.non_values)


# ── 제목·각주 잇기 (TS compare.test.ts 102-118) ──────────────────────────────


@pytest.fixture
def titled() -> DocModel:
    return synthetic_document(
        "a",
        [
            TableSpec(
                "p1-t1", cells=[["Scope 1", "tCO2eq", "900", "950"]], before=["- 위 표의 제목 (국내 사업장 기준)"]
            ),
            TableSpec(
                "p1-t2",
                cells=[["Scope 1", "tCO2eq", "1,200", "1,350"]],
                before=["1) 위 표의 각주", "[참고] 아래 표의 제목 (국내외 사업장)"],
            ),
        ],
        extra_blocks=[
            DocBlock("after", "paragraph", 1, (0, 0, 1, 1), 99, "* 아래 표의 각주", None),
            DocBlock("body", "paragraph", 1, (0, 0, 1, 1), 100, "본문 글", None),
        ],
    )


def test_default_titles_are_the_three_blocks_before_so_neighbours_mix_in(titled: DocModel) -> None:
    assert extract_document(titled, "a").grids[1].title_candidates == (
        "[참고] 아래 표의 제목 (국내외 사업장)",
        "1) 위 표의 각주",
        "- 위 표의 제목 (국내 사업장 기준)",
    )


def test_own_titles_are_that_tables_title_and_its_footnotes_only(titled: DocModel) -> None:
    grids = extract_document(titled, "a", titles="own").grids
    assert grids[0].title_candidates == ("- 위 표의 제목 (국내 사업장 기준)", "1) 위 표의 각주")
    assert grids[1].title_candidates == ("[참고] 아래 표의 제목 (국내외 사업장)", "* 아래 표의 각주")


def test_titles_are_clipped_at_200_utf16_units() -> None:
    long = "가" * 199 + "😀" + "나"
    document = synthetic_document("t", [TableSpec("p1-t1", cells=[["이름", "값"], ["가", "1"]], before=[long])])
    (title,) = extract_document(document, "a").grids[0].title_candidates
    assert title == "가" * 199 + "\ud83d"  # 이모지의 앞 절반에서 잘린다(JS 의 slice 와 같다)


# ── 엑셀 격자 (지은 격자. TS xlsx.test.ts 의 값 후보 쪽) ─────────────────────


def stored(
    raw: str, *, display: str | None, status: str = "rendered", date: bool = False, formula: bool = False
) -> StoredNumber:
    return StoredNumber(raw, raw, "0.00", display, status, date, formula)  # pyright: ignore[reportArgumentType]


def sheet(cells: list[list[str]], numeric: list[list[StoredNumber | None]]) -> Grid:
    refs = tuple(tuple(f"{'ABCDEFG'[c]}{r + 1}" for c in range(len(row))) for r, row in enumerate(cells))
    return Grid(
        id="s1",
        doc_id="x",
        kind="sheet",
        page=None,
        sheet="Sheet1",
        cells=tuple(tuple(row) for row in cells),
        header=estimate_header(cells),
        status="ok",
        footnote_marks=(),
        title_candidates=(),
        unit_lines=(),
        numeric=tuple(tuple(row) for row in numeric),
        refs=refs,
    )


def test_sheet_values_are_the_stored_values_and_the_display_is_kept_apart() -> None:
    grid = sheet(
        [
            ["구분", "2024", "비율", "일자", "메모", "합계"],
            ["가", "1,234.57", "12.3%", "2025-07-01", "300", FORMULA_WITHOUT_RESULT],
        ],
        [
            [None, stored("2024", display="2024"), None, None, None, None],
            [
                None,
                stored("1234.5678", display="1,234.57"),
                stored("0.123", display="12.3%"),
                stored("45839", display="2025-07-01", date=True),
                None,
                None,
            ],
        ],
    )
    extraction = extract_grids([grid], "x", "x.xlsx")
    by_id = {fact.id: fact for fact in extraction.facts}
    # 값은 저장 값이고 화면 표기는 따로 남는다(둘이 다를 수 있다).
    value = by_id["s1:r1c1"]
    assert (value.value, value.raw, value.decimals, value.stored_as_text) == ("1234.5678", "1,234.57", 4, False)
    assert value.stored is not None
    assert value.where.ref == "B2"
    assert value.where.sheet == "Sheet1"
    # 퍼센트 서식: 저장 값 0.123 을 % 단위의 값 12.3 으로 (자리 옮김뿐).
    percent = by_id["s1:r1c2"]
    assert (percent.value, percent.percent, percent.unit_suffix, percent.flags) == (
        "12.3",
        True,
        "%",
        ("percent_format_scaled",),
    )
    # 글자로 든 숫자는 그 표시를 단다.
    assert (by_id["s1:r1c4"].value, by_id["s1:r1c4"].stored_as_text) == ("300", True)
    # 날짜 서식 칸과 결과 없는 수식은 값 후보가 아니다. 머리글의 연도도 아니다.
    found = {(item.where.ref, item.raw, item.cls) for item in extraction.non_values}
    assert ("D2", "2025-07-01", "date") in found
    assert ("F2", FORMULA_WITHOUT_RESULT, "formula_without_result") in found
    assert ("B1", "2024", "header") in found
    assert set(by_id) == {"s1:r1c1", "s1:r1c2", "s1:r1c4"}
    assert extraction.grids[0].inner_headers == ()
    assert (extraction.failed_tables, extraction.pages_without_text) == ((), ())


def test_a_negative_stored_value_and_an_unsupported_format() -> None:
    grid = sheet(
        [["구분", "값", "값2"], ["가", "-5.50", "0.5"]],
        [
            [None, None, None],
            [None, stored("-5.5", display="-5.50"), stored("0.5", display=None, status="unsupported_format")],
        ],
    )
    facts, _ = grid_facts(grid)
    negative, unsupported = facts
    assert (negative.value, negative.sign) == ("-5.5", "minus")
    # 지원하지 않는 서식은 화면 표기를 지어내지 않는다: 원문 글자는 저장된 글자다.
    assert (unsupported.raw, unsupported.percent) == ("0.5", False)


# ── 갈래마다 하나 이상 ────────────────────────────────────────────────────────


def test_every_non_value_class_is_reachable() -> None:
    document = synthetic_document(
        "classes",
        [
            TableSpec(
                "p1-t1",
                header=GridHeader((0,), (0,), "rows_before_first_numeric_row"),
                cells=[
                    ["구분", "2024", "쪽"],
                    ["가", "-", "12"],
                    ["나", "FY2025", "1"],
                    ["다", "04", "1"],
                    ["라", "2025.7.1", "1"],
                    ["마", "10~20", "1"],
                ],
            ),
            TableSpec(
                "p1-t2", header=HEADER, cells=[["구분", "값"], ["가", "10~20"], ["나", "3월 Scope 1 제2조 1) 끝"]]
            ),
        ],
        [BlockSpec("p1-b1", "17", bbox=(280, 770, 300, 790))],
    )
    found = {item.cls for item in extract_document(document, "a").non_values}
    sheet_grid = sheet([["구분", "값"], ["가", FORMULA_WITHOUT_RESULT]], [[None, None], [None, None]])
    found |= {item.cls for item in extract_grids([sheet_grid], "x", "x.xlsx").non_values}
    # `range` 는 꼴로만 있다: 범위 칸은 양 끝을 `range_part` 로 남긴다(칸 전체를 range 로 남기는 가지가 없다).
    assert found == set(NON_VALUE_CLASSES) - {"range"}


def test_estimate_header() -> None:
    assert estimate_header([]) == GridHeader((), (), "empty")
    assert estimate_header([["가", "나"], ["다", "라"]]) == GridHeader((0,), (0, 1), "no_numeric_row")
    assert estimate_header([["구분", "2023", "2024"], ["가", "1", "2"]]) == GridHeader(
        (0,), (0,), "rows_before_first_numeric_row"
    )
    # 값 행 바로 위의 행이 글자 하나뿐이면(묶음 제목) 머리글에서 뺀다. 맨 위 행은 남긴다.
    assert estimate_header([["구분", "2023"], ["묶음", ""], ["가", "1"]]).rows == (0,)
    assert cell_id(2, 4) == "r2c4"
