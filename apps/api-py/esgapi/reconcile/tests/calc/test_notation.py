"""글 속 숫자 덩어리와 표 칸 하나의 읽기 — 밖으로 나가는 칸 전부(`raw`·`start`·`end`·`occurrence`·`kind`·`number`).

`calc/test_notation_ts.py` 는 `(raw, kind[, unit_suffix])` 만 투영해 본다. 여기서는 `scan_numbers` 의 결과 목록
전체, `classify_cell` 의 `CellNotation` 전체, `locate_quote` 의 자리 전체를 == 로 견준다(MARC-ENT-280, 밴드 NK1).
대상 함수는 시험 안에서 부른다 — 모듈 상수로 두면 mutmut 이 변이를 켜기 전에 굳는다.

★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import pytest

from esgapi.reconcile.calc.notation import classify_cell, locate_quote, scan_numbers
from esgapi.reconcile.calc.types import TOKEN_KINDS, CellNotation, NotationFlag, NumberToken, ParsedNumber, SignRule


def other(raw: str, start: int, end: int, occurrence: int, kind: str) -> NumberToken:
    """값이 아닌 덩어리(number 는 None)."""
    return NumberToken(raw, start, end, occurrence, kind, None)  # pyright: ignore[reportArgumentType]


def value(
    raw: str,
    start: int,
    end: int,
    occurrence: int,
    number: str,
    decimals: int = 0,
    sign: SignRule = "none",
    unit: str | None = None,
    flags: tuple[NotationFlag, ...] = (),
) -> NumberToken:
    percent = unit in ("%", "%p")
    return NumberToken(raw, start, end, occurrence, "value", ParsedNumber(number, decimals, sign, percent, unit, flags))


# ── 부호 (scan_numbers) ──────────────────────────────────────────────────────


def test_a_sign_right_before_a_number_is_read_with_its_kind_and_flag() -> None:
    # 글 맨 앞의 부호(start 0), +, △(음수 표지), ▲▼(뜻 모름), U+2212 빼기, 부호 없는 % 값.
    assert scan_numbers("-5 감소, 증감 +3, △2, ▲4, ▼1, −7 그리고 5%") == [
        value("-5", 0, 2, 1, "-5", sign="minus"),
        value("+3", 10, 12, 1, "3", sign="plus"),
        value("△2", 14, 16, 1, "-2", sign="triangle_negative", flags=("triangle_negative",)),
        value("▲4", 18, 20, 1, "4", sign="triangle_ambiguous", flags=("sign_ambiguous",)),
        value("▼1", 22, 24, 1, "1", sign="triangle_ambiguous", flags=("sign_ambiguous",)),
        value("−7", 26, 28, 1, "-7", sign="minus"),
        value("5%", 33, 35, 1, "5", unit="%"),
    ]


def test_percent_points_keep_their_unit_and_a_decimal_place() -> None:
    assert scan_numbers("증감 3.5%p 확대") == [value("3.5%p", 3, 8, 1, "3.5", decimals=1, unit="%p")]


# ── 갈래 (_token_kind) ───────────────────────────────────────────────────────


BRANCHES: list[tuple[str, list[NumberToken]]] = [
    # URL 안의 숫자는 번호다. URL 뒤의 숫자는 값이고, 같은 글자 5 의 두 번째다.
    (
        "주소 https://a.kr/2024/5 이후 5톤",
        [
            other("2024", 16, 20, 1, "identifier"),
            other("5", 21, 22, 1, "identifier"),
            value("5", 26, 27, 2, "5", unit="톤"),
        ],
    ),
    # URL 의 시작과 같은 자리(12345)와 끝과 같은 자리(7).
    ("12345@mail.com 과 www.a.kr/7", [other("12345", 0, 5, 1, "identifier"), other("7", 26, 27, 1, "identifier")]),
    # 숫자-숫자 는 번호, 숫자-글자 는 값.
    (
        "12-34 와 5-A",
        [other("12", 0, 2, 1, "identifier"), other("34", 3, 5, 1, "identifier"), value("5", 8, 9, 1, "5")],
    ),
    # 점 앞이 숫자가 아니면 값, 숫자.숫자. 뒤는 번호.
    (
        "a.5 와 버전 1.2.3",
        [value("5", 2, 3, 1, "5"), value("1.2", 9, 12, 1, "1.2", decimals=1), other("3", 13, 14, 1, "identifier")],
    ),
    # 날짜 자리(2025.7)와, 날짜 뒤 점 갈래의 날 15.
    ("2025.7.15, 끝", [other("2025.7", 0, 6, 1, "date_part"), other("15", 7, 9, 1, "date_part")]),
    ("1∼3", [other("1", 0, 1, 1, "range_part"), other("3", 2, 3, 1, "range_part")]),
    # 괄호 각주 표시는 두 자리까지.
    ("주석12) 와 주석123) 끝", [other("12", 2, 4, 1, "marker"), value("123", 10, 13, 1, "123")]),
    ("제3조", [other("3", 1, 2, 1, "ordinal")]),
    # 쉼표 든 수 뒤의 호는 순번이 아니다.
    ("1,000호", [value("1,000", 0, 5, 1, "1000")]),
    # 연도 셋: 년 앞, 따옴표 뒤 두 자리, 홀로 선 네 자리.
    (
        "2025년 과 ’24 와 2030 목표",
        [other("2025", 0, 4, 1, "year"), other("24", 9, 11, 1, "year"), other("2030", 14, 18, 1, "year")],
    ),
    # 월 뒤의 날은 두 자리까지, 회는 날이 아니다.
    ("3월 125일", [other("3", 0, 1, 1, "date_part"), value("125", 3, 6, 1, "125", unit="일")]),
    ("3월 15회", [other("3", 0, 1, 1, "date_part"), value("15", 3, 5, 1, "15", unit="회")]),
    ("코드 007 확인", [other("007", 3, 6, 1, "identifier")]),
    # 앞자리 0 은 값에서 지운다(쉼표 든 수는 앞자리 0 번호 갈래를 타지 않는다).
    ("0,123 증가", [value("0,123", 0, 5, 1, "123")]),
    # 같은 글자가 겹쳐 나오면 겹친 것도 센다: 11 은 111 안의 둘 다음 세 번째.
    ("111 11", [value("111", 0, 3, 1, "111"), value("11", 4, 6, 3, "11")]),
]


@pytest.mark.parametrize(("text", "tokens"), BRANCHES)
def test_each_branch_gives_the_whole_token_list(text: str, tokens: list[NumberToken]) -> None:
    assert scan_numbers(text) == tokens


def test_the_branch_table_reaches_every_token_kind() -> None:
    assert {token.kind for _, tokens in BRANCHES for token in tokens} == set(TOKEN_KINDS)


# ── 표 칸 (classify_cell) ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "cell"),
    [
        ("–5", CellNotation("value", ParsedNumber("-5", 0, "minus", False, None, ()))),  # U+2013
        ("12", CellNotation("value", ParsedNumber("12", 0, "none", False, None, ()))),
        ("3.5%p", CellNotation("value", ParsedNumber("3.5", 1, "none", True, "%p", ()))),
        ("0,123", CellNotation("value", ParsedNumber("123", 0, "none", False, None, ()))),
        # 빈칸을 뺀 글자가 연도 꼴이면 연도다(한 덩어리로는 읽히지 않는 칸).
        ("20 24", CellNotation("year", None)),
        ("FY2024", CellNotation("year", None)),
        ("1.2%p 3.4%p", CellNotation("multi_number", None)),
        # 괄호와 부호가 함께 있으면 값 하나로 읽지 않는다.
        ("-(5)", CellNotation("multi_number", None)),
    ],
)
def test_a_cell_is_read_whole(raw: str, cell: CellNotation) -> None:
    assert classify_cell(raw) == cell


# ── 원문 자리 (locate_quote) ─────────────────────────────────────────────────


def test_a_quote_is_found_by_its_occurrence_counting_overlaps() -> None:
    assert locate_quote("가 11", "11", 1) == (2, 4, 1)
    assert locate_quote("11 111", "11", 1) == (0, 2, 3)
    assert locate_quote("11 111", "11", 2) == (3, 5, 3)
    assert locate_quote("11 111", "11", 3) == (4, 6, 3)
    assert locate_quote("11 111", "11", 4) is None


def test_an_occurrence_that_is_not_an_int_finds_nothing() -> None:
    assert locate_quote("가 11", "11", 1.0) is None  # pyright: ignore[reportArgumentType]
    assert locate_quote("가 11", "11", True) is None
    assert locate_quote("가 11", "11", 0) is None
    assert locate_quote("가 11", "", 1) is None
