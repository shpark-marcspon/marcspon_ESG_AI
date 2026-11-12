"""숫자 가림. TS `compare.test.ts` 의 「숫자 가림 (D·F)」 4건의 뜻을 `mask_text`·`cell_text` 높이에서 옮겼다.

★ TS 와 다르게 한 것: TS 는 요청 글 조립(`renderDocument`·`renderTableList`·`renderRowList`)을 거쳐 재지만 그 조립은
옮기지 않았다. 여기서는 조립이 부르는 두 함수를 직접 잰다(「요청 글 전체에 값이 남지 않는다」는 조립을 옮길 때 다시
잰다).
`hybrid.test.ts` 의 `unmaskedValues` 단언은 PY6b 로 넘겼다(감독 결정 2026-10-08).
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import pytest

from esgapi.reconcile.calc.facts import extract_document
from esgapi.reconcile.calc.mask import MASK, cell_text, mask_text
from esgapi.reconcile.calc.notation import normalize_text
from esgapi.reconcile.calc.types import DocModel, Extraction, Fact, Grid, GridHeader
from esgapi.reconcile.tests.support import TableSpec, synthetic_document


# 문서·뽑기는 시험마다(함수 범위) 짓는다. 모듈 상수로 두면 mutmut 이 변이를 켜기 전에 한 번 굳어 facts.py 의 변이가
# 이 시험들에 보이지 않는다(scripts/weekly.sh 의 ② — 거짓 생존. MARC-ISSUE-154, FT1).
@pytest.fixture
def document() -> DocModel:
    return synthetic_document(
        "a",
        [
            TableSpec(
                "p1-t1",
                cells=[
                    ["구분", "단위", "2023", "2024"],
                    ["Scope 1", "tCO2eq", "48,217", "39,604"],
                    ["감축률", "%", "17.3%", "기준연도 대비 26.5% 감축"],
                ],
                header=GridHeader((0,), (0, 1), "rows_before_first_numeric_row"),
                before=["2023년 배출량은 48,217 tCO2eq 이다"],
            )
        ],
    )


@pytest.fixture
def extraction(document: DocModel) -> Extraction:
    return extract_document(document, "a", titles="own")


@pytest.fixture
def facts(extraction: Extraction) -> dict[str, Fact]:
    return {fact.id: fact for fact in extraction.facts}


@pytest.fixture
def grid(extraction: Extraction) -> Grid:
    return extraction.grids[0]


VALUES = ["48,217", "39,604", "17.3", "26.5", "48217", "39604"]


def masked_parts(document: DocModel, grid: Grid, facts: dict[str, Fact], mask: bool) -> list[str]:
    """요청 글이 실을 조각 전부: 글 블록과 표의 칸."""
    parts = [
        mask_text(normalize_text(b.text or "")) if mask else normalize_text(b.text or "")
        for b in document.blocks
        if b.kind != "table"
    ]
    for row, cells in enumerate(grid.cells):
        parts.extend(cell_text(grid, row, col, raw, facts, mask) for col, raw in enumerate(cells))
    return parts


def test_no_candidate_number_is_left_and_header_years_and_row_names_stay(
    document: DocModel, grid: Grid, facts: dict[str, Fact]
) -> None:
    parts = masked_parts(document, grid, facts, mask=True)
    joined = "\n".join(parts)
    for value in VALUES:
        assert value not in joined
    assert cell_text(grid, 1, 2, "48,217", facts, True) == MASK
    assert cell_text(grid, 2, 2, "17.3%", facts, True) == f"{MASK}%"  # 단위 접미는 남긴다 (심은 파손 9)
    assert cell_text(grid, 0, 2, "2023", facts, True) == "2023"  # 머리글의 연도는 값 후보가 아니다
    assert "Scope 1" in parts
    assert f"2023년 배출량은 {MASK} tCO2eq 이다" in parts
    assert cell_text(grid, 2, 3, "기준연도 대비 26.5% 감축", facts, True) == f"기준연도 대비 {MASK} 감축"
    # 가리지 않으면 값이 그대로 실린다.
    assert "48,217" in masked_parts(document, grid, facts, mask=False)


def test_the_mask_is_one_symbol_whatever_the_number_of_digits(
    document: DocModel, grid: Grid, facts: dict[str, Fact]
) -> None:
    assert "\n".join(masked_parts(document, grid, facts, mask=True)).count(MASK) == 5
    # 길이가 자릿수를 흘리지 않는다 (심은 파손 9 가 자릿수만큼의 기호로 가린다).
    assert cell_text(grid, 1, 2, "48,217", facts, True) == cell_text(grid, 1, 3, "39,604", facts, True) == MASK
    assert mask_text("1 과 1,234,567.89") == f"{MASK} 과 {MASK}"


def test_header_texts_keep_their_years_and_lose_nothing_else(extraction: Extraction) -> None:
    """TS 의 「F 의 표 목록에도 값 후보 숫자가 남지 않는다」: 표 목록은 머리글을 `maskText` 로 싣는다."""
    headers = {ref.text for fact in extraction.facts if fact.headers for ref in (*fact.headers.row, *fact.headers.col)}
    assert {"2023", "2024", "Scope 1", "tCO2eq"} <= headers
    for text in headers:
        assert mask_text(text) == text  # 연도와 이름표 번호는 값 후보가 아니라 남는다
        assert MASK not in mask_text(text)


def test_candidate_numbers_inside_headers_titles_and_footnotes_are_masked_too() -> None:
    document = synthetic_document(
        "a",
        [
            TableSpec(
                "p1-t1",
                cells=[["허용 오차 4.75% 이내 배출량", "tCO2eq", "48,217", "39,604"]],
                before=["중요성 기준 6.25% 미만"],
            )
        ],
    )
    own = extract_document(document, "a", titles="own")
    header = "허용 오차 4.75% 이내 배출량 > tCO2eq"
    titles = [mask_text(title) for title in own.grids[0].title_candidates]
    assert mask_text(header) == f"허용 오차 {MASK} 이내 배출량 > tCO2eq"
    assert titles == [f"중요성 기준 {MASK} 미만"]
    for text in (mask_text(header), *titles):
        assert "4.75" not in text
        assert "6.25" not in text


def test_mask_text_works_in_utf16_positions() -> None:
    assert mask_text("😀 +7.5% 달성 😀 12개") == f"😀 {MASK} 달성 😀 {MASK}개"
    assert mask_text("") == ""
    assert mask_text("2025년 Scope 1 제3조") == "2025년 Scope 1 제3조"


def test_cell_text_without_mask_is_the_normalized_text(grid: Grid, facts: dict[str, Fact]) -> None:
    assert cell_text(grid, 1, 2, " 48,217\n", facts, False) == "48,217"
    # 격자에 없는 칸(값 후보가 아닌 글 칸)은 그 안의 값 후보만 가린다.
    assert cell_text(grid, 9, 9, "전년 대비 12% 증가", facts, True) == f"전년 대비 {MASK} 증가"
