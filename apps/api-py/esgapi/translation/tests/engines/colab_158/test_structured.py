"""structured.py(코랩 셀 7 의 글 몫) — 손으로 지은 기대값(발주서 §3 S1·S8 의 W1, §2-2 ★a·★b).

기대값은 러너가 코랩 줄(R/)을 읽고 적은 것이다. 코랩 코드와의 바이트 대조는 esg-lab TR1-o 몫(MARC-ENT-311).
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from esgapi.translation.engines.colab_158 import structured, tables

NORMALIZE_CASES = [
    ("**[BLOCK 1]**\n본문", "[BLOCK 1]\n본문"),  # R/137
    ("__[TABLE 2]__", "[TABLE 2]"),  # R/138
    ("## [PAGE 1]\n가", "[PAGE 1]\n가"),  # R/141-146
    ("    ## [PAGE 1]", "    ## [PAGE 1]"),  # 빈칸 넷이면 제목 줄이 아니다(\s{0,3})
    ("\\[PAGE 3\\]", "[PAGE 3]"),  # R/149
    ("본문  \n다음", "본문\n다음"),  # R/151 줄 끝 빈칸
    ("a\r\nb\rc", "a\nb\nc"),  # R/134
    ("**강조**", "**강조**"),  # 일반 강조는 그대로
    ("**[ESG]**", "**[ESG]**"),  # 구조 태그가 아니면 그대로
    ("", ""),
]


@pytest.mark.parametrize(("raw", "expected"), NORMALIZE_CASES)
def test_normalize_structured_tags(raw: str, expected: str) -> None:
    assert structured.normalize_structured_tags(raw) == expected


def test_normalize_case_count() -> None:
    assert len(NORMALIZE_CASES) == 10


def test_w1_blank_lines_are_not_collapsed_but_braces_are() -> None:
    """W1(R/160): `r'\\n{{3,}}'` 는 f-문자열이 아니라 「\\n + `{` 셋 이상 + `}`」 에만 맞는다(★b)."""
    assert structured.normalize_structured_tags("가\n\n\n\n나") == "가\n\n\n\n나"
    assert structured.normalize_structured_tags("가\n{{{}나") == "가\n\n나"
    assert structured.normalize_structured_tags("가\n{{}나") == "가\n{{}나"


# ★a: 두 판 `_escape_md_cell`(셀 7 R/185 · 셀 46 R/2164)이 갈라지는 입력
ESCAPE_CASES = [
    # (입력, 셀 7 판, 셀 46 판)
    ("a\n\nb", "a<br>b", "a<br><br>b"),  # 연속 줄바꿈: 셀 7 은 하나로
    ("a  b", "a b", "a  b"),  # 빈칸 둘: 셀 7 은 접음
    ("a\tb", "a b", "a\tb"),  # 탭
    ("\na", "<br>a", "a"),  # 앞 줄바꿈: 셀 7 은 <br> 뒤에 strip, 셀 46 은 strip 먼저
    (" a |b ", "a &#124;b", "a &#124;b"),  # 같다
    ("a \n b", "a <br> b", "a <br> b"),  # 같다
    (None, "", ""),
]


@pytest.mark.parametrize(("text", "docx", "table"), ESCAPE_CASES)
def test_the_two_escape_md_cell_versions(text: str | None, docx: str, table: str) -> None:
    assert structured.escape_md_cell_docx(text) == docx
    assert tables.escape_md_cell(text) == table


def test_table_rows_to_markdown() -> None:
    """R/201-224: 빈 행을 버리고, 가장 긴 행에 맞춰 칸을 채운다. 첫 행이 머리."""
    rows: list[list[str | None]] = [["항목", "2025"], ["", None], ["전력", "1,200\nMWh", "주석 | 가"], ["합계"]]
    assert structured.table_rows_to_markdown(rows) == [
        "| 항목 | 2025 |  |",
        "| --- | --- | --- |",
        "| 전력 | 1,200<br>MWh | 주석 &#124; 가 |",
        "| 합계 |  |  |",
    ]
    assert structured.table_rows_to_markdown([["", ""]]) == []


@given(st.text())
def test_normalize_leaves_no_carriage_return(raw: str) -> None:
    """성질: 줄바꿈을 먼저 \n 으로 통일하고(R/134) 뒤의 치환은 \r 을 만들지 않는다. (멱등은 아니다 — `****[BLOCK 1]****`
    는 한 번에 바깥 별표가 남는다: 코랩 정규식 그대로.)"""
    assert "\r" not in structured.normalize_structured_tags(raw)
    assert structured.normalize_structured_tags("****[BLOCK 1]****") == "**[BLOCK 1]**"
