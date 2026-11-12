"""숫자 표기 규칙. TS `notation.test.ts` 6건의 뜻을 옮겼고, 갈래마다 하나 이상과 언어 차이의 본보기를 더했다.

★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import pytest

from esgapi.reconcile.calc.notation import classify_cell, locate_quote, normalize_text, scan_numbers
from esgapi.reconcile.calc.types import CELL_KINDS, SIGN_RULES, TOKEN_KINDS

# ── 표 칸 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "value", "decimals"),
    [
        ("1,234", "1234", 0),
        ("1234", "1234", 0),
        ("12.50", "12.50", 2),
        ("0.5", "0.5", 1),
        ("-12", "-12", 0),
        ("−12", "-12", 0),
        ("(123)", "-123", 0),
        ("(2,720)", "-2720", 0),
        ("△12", "-12", 0),
        ("31.0%", "31.0", 1),
        ("1.2배", "1.2", 1),
        ("59,498명", "59498", 0),
        ("24만 톤", "24", 0),
        ("１，２３４", "1234", 0),
        ("1,557,077,275", "1557077275", 0),
    ],
)
def test_cell_value(raw: str, value: str, decimals: int) -> None:
    cell = classify_cell(raw)
    assert cell.kind == "value"
    assert cell.number is not None
    assert (cell.number.value, cell.number.decimals) == (value, decimals)


def test_cell_keeps_sign_and_suffix_as_marks() -> None:
    def number(raw: str):
        found = classify_cell(raw).number
        assert found is not None
        return found

    assert (number("(123)").sign, number("(123)").flags) == ("paren_negative", ("paren_negative_assumed",))
    assert (number("△12").sign, number("△12").flags) == ("triangle_negative", ("triangle_negative",))
    assert (number("▲ 3").sign, number("▲ 3").value, number("▲ 3").flags) == (
        "triangle_ambiguous",
        "3",
        ("sign_ambiguous",),
    )
    assert (number("31.0%").percent, number("31.0%").unit_suffix) == (True, "%")
    assert number("24만 톤").unit_suffix == "만 톤"
    assert "year_like" in number("2025").flags  # 연도 표시 (심은 파손 1 이 지운다)
    assert "year_like" in number("2100").flags
    assert "year_like" not in number("2,025").flags
    assert "year_like" not in number("2101").flags
    # 부호 여섯 갈래가 다 나온다.
    seen = {number(raw).sign for raw in ("12", "-12", "+12", "(12)", "△12", "▼12")}
    assert seen == set(SIGN_RULES)
    # 0 에는 음수 부호를 붙이지 않는다.
    assert number("-0.0").value == "0.0"
    assert number("(0)").value == "0"


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("", "blank"),
        ("-", "no_value_marker"),
        ("–", "no_value_marker"),
        ("N/A", "no_value_marker"),
        ("해당 없음", "no_value_marker"),
        ("2025년", "year"),
        ("FY2024", "year"),
        ("’25년", "text_with_digits"),
        ("04", "code"),
        ("6(1)", "code"),
        ("29(1)(가)①", "code"),
        ("1.2.3", "code"),
        ("2025.7.1", "date"),
        ("10~20", "range"),
        ("65-66", "range"),
        ("3~17%", "range"),
        ("116,818 15,649", "multi_number"),
        ("64, 216", "multi_number"),
        ("1,23", "multi_number"),
        ("21.1 10.2", "multi_number"),
        ("20.00 40.00 60.00", "multi_number"),
        ("Scope 1", "text_with_digits"),
        ("기준연도 대비 42% 감축", "text_with_digits"),
        ("3년", "text_with_digits"),
        ("305-1 직접 온실가스 배출량(Scope 1)", "text_with_digits"),
        ("전력", "text"),
    ],
)
def test_cell_non_value(raw: str, kind: str) -> None:
    cell = classify_cell(raw)
    assert cell.kind == kind
    assert cell.number is None


def test_every_cell_kind_is_reachable() -> None:
    raws = ["", "12", "-", "FY2024", "04", "2025.7.1", "10~20", "1 2", "Scope 1", "전력"]
    assert {classify_cell(raw).kind for raw in raws} == set(CELL_KINDS)


# ── 글 속 숫자 ───────────────────────────────────────────────────────────────


def kinds(text: str) -> list[tuple[str, str]]:
    return [(token.raw, token.kind) for token in scan_numbers(text)]


def with_units(text: str) -> list[tuple[str, str, str | None]]:
    return [(t.raw, t.kind, t.number.unit_suffix if t.number else None) for t in scan_numbers(text)]


def test_text_separates_values_from_the_rest() -> None:
    assert kinds("2025년 Scope 1 배출량은 22,253 tCO2eq로 전년 대비 1.1% 줄었다.") == [
        ("2025", "year"),
        ("1", "identifier"),
        ("22,253", "value"),
        ("2", "identifier"),
        ("1.1%", "value"),
    ]
    assert kinds("GRI 305-1, ISO 14001, RE100, CO2") == [
        ("305", "identifier"),
        ("1", "identifier"),
        ("14001", "identifier"),
        ("100", "identifier"),
        ("2", "identifier"),
    ]
    assert kinds("제3조에 따라 2차 협력사 12개사를 3월 15일 점검했다") == [
        ("3", "ordinal"),
        ("2", "ordinal"),
        ("12", "value"),
        ("3", "date_part"),
        ("15", "date_part"),
    ]
    assert kinds("문의 02-1234-5678, 발간 2025.7.1") == [
        ("02", "identifier"),
        ("1234", "identifier"),
        ("5678", "identifier"),
        ("2025.7", "date_part"),
        ("1", "date_part"),
    ]
    # 숫자 바로 뒤가 아니면 어디서든 덩어리를 낸다: 쉼표·마침표 뒤의 숫자도 버리지 않는다.
    assert kinds("비중은 각각 10,20,30%이고 12,5%") == [
        ("10", "value"),
        ("20", "value"),
        ("30%", "value"),
        ("12", "value"),
        ("5%", "value"),
    ]
    # 「조 원」은 순번(제3조)이 아니라 금액 단위다. 숫자에 붙은 로마자 단위는 값이고, 한 글자나 글자+숫자는 식별자다.
    assert with_units("자산 333.6조 원, 발전 28MW와 5.02GWh의 전력, 3R 활동, 24X365") == [
        ("333.6", "value", "조 원"),
        ("28", "value", "MW"),
        ("5.02", "value", "GWh"),
        ("3", "identifier", None),
        ("24", "identifier", None),
        ("365", "identifier", None),
    ]
    assert kinds("용수 재이용1) 107,967톤, 단기(1~5년)") == [
        ("1", "marker"),
        ("107,967", "value"),
        ("1", "range_part"),
        ("5", "range_part"),
    ]
    assert kinds("1. 개요") == [("1", "marker")]
    # 단위 낱말 뒤에 다른 낱말이 이어지면 단위가 아니다 (`배출량` 의 배, `개국` 의 개, `회차`).
    assert with_units("2025 배출량, 76개국, 3회차, 3,200명이다, 187조 9,673억 원") == [
        ("2025", "year", None),
        ("76", "value", None),
        ("3", "ordinal", None),
        ("3,200", "value", "명"),
        ("187", "value", None),
        ("9,673", "value", "억 원"),
    ]
    assert kinds("2050 탄소중립, 근속 10년, 직원 3,200명") == [("2050", "year"), ("10", "value"), ("3,200", "value")]


def test_text_reads_value_unit_suffix_and_sign() -> None:
    amount, change = scan_numbers("투자액 30억 원, 증감 -3.2%")
    assert amount.number is not None
    assert (amount.number.value, amount.number.unit_suffix, amount.number.decimals) == ("30", "억 원", 0)
    assert change.raw == "-3.2%"
    assert change.number is not None
    assert (change.number.value, change.number.percent, change.number.sign, change.number.decimals) == (
        "-3.2",
        True,
        "minus",
        1,
    )


def test_text_counts_which_occurrence_a_repeated_number_is() -> None:
    text = "여성 120명, 남성 120명, 합계 240명"
    tokens = scan_numbers(text)
    assert [(token.raw, token.occurrence) for token in tokens] == [("120", 1), ("120", 2), ("240", 1)]
    second = tokens[1]
    assert locate_quote(text, "120", 2) == (second.start, second.end, 2)
    assert locate_quote("여성 120명", "121", 1) is None
    assert locate_quote("여성 120명", "120", 2) is None
    assert locate_quote("여성 120명", "", 1) is None
    assert locate_quote("여성 120명", "120", 0) is None


def test_every_token_kind_is_reachable() -> None:
    text = "2025년 3월, Scope 1, 제3조, 1) 10~20 그리고 42%"
    assert {token.kind for token in scan_numbers(text)} == set(TOKEN_KINDS)


def test_the_order_of_the_branches_is_the_meaning() -> None:
    """갈래의 차례가 뜻이다(심은 파손 3 이 연도 판정을 순번 앞으로 옮긴다)."""
    # 순번(ORDINAL_AFTER)이 연도보다 먼저다: `2025호` 는 연도 꼴이지만 순번이다.
    assert kinds("제도 2025호 시행") == [("2025", "ordinal")]
    assert kinds("2025차 회의") == [("2025", "ordinal")]
    # 날짜 범위가 이름표보다 먼저다.
    assert kinds("No. 2025.7.1")[0] == ("2025.7", "date_part")


# ── JS 와 파이썬이 달리 읽는 자리 (TS 와 같은지는 지은 문서 골든이 값으로 잰다. 여기는 뜻을 적어 둔다) ──


def test_js_word_boundary_treats_hangul_as_a_non_word() -> None:
    """`위\\b`·`기\\b`·`종\\b`: JS 의 `\\b` 는 ASCII 낱말 기준이라 「위 뒤가 ASCII 낱말 글자일 때」만 맞는다."""
    assert kinds("3위A") == [("3", "ordinal")]
    assert kinds("3위 ") == [("3", "value")]
    assert kinds("3위") == [("3", "value")]
    assert kinds("2기B") == [("2", "ordinal")]
    assert kinds("2기 ") == [("2", "value")]
    assert kinds("4종9") == [("4", "ordinal"), ("9", "value")]
    assert kinds("4종 ") == [("4", "value")]


def test_only_ascii_digits_are_digits() -> None:
    """JS 의 `\\d` 는 ASCII 숫자뿐이다. 아랍-인도 숫자와 전각 숫자는 글 속에서 숫자 덩어리가 아니다."""
    assert kinds("١٢٣ 과 １２３ 사이의 45") == [("45", "value")]
    assert classify_cell("١٢٣").kind == "text"
    # 칸은 NFKC 를 거치므로 전각 숫자는 숫자가 된다(아랍-인도 숫자는 그대로다).
    assert classify_cell("１２３").kind == "value"
    assert normalize_text("１，２３４") == "1,234"


def test_whitespace_is_the_js_set() -> None:
    """JS 의 `\\s`·`trim()`: U+FEFF 는 빈칸이고 U+0085·U+001C 는 빈칸이 아니다(파이썬은 반대)."""
    assert normalize_text("﻿ 34 ﻿") == "34"
    assert normalize_text("a\u0085b") == "a\u0085b"
    assert normalize_text("a\u001cb") == "a b"  # 제어 글자(U+0000~001F)는 빈칸으로 바꾼다
    assert classify_cell("﻿34").kind == "value"
    assert classify_cell("\u008534").kind == "multi_number"  # U+0085 는 떼어지지 않아 「숫자 하나」가 아니다
    # 부호는 「그 앞이 빈칸이거나 여는 괄호」일 때만 숫자의 것이다.
    raws = [token.raw for token in scan_numbers("﻿-7 과 \u0085-8 과 \u001c-9")]
    assert raws == ["-7", "8", "9"]


def test_positions_are_utf16() -> None:
    """자리는 UTF-16 이다: 이모지 하나가 두 자리다. (심은 파손 2 가 코드포인트로 바꾼다)"""
    text = "😀 +7.5% 달성"
    (token,) = scan_numbers(text)
    assert (token.raw, token.start, token.end) == ("+7.5%", 3, 8)
    assert locate_quote("😀 12 😀 12", "12", 2) == (9, 11, 2)
    # 앞뒤 글의 창(12자)도 UTF-16 으로 센다: 이모지 여섯이면 창이 다 차서 그 앞의 이름표가 보이지 않는다.
    assert kinds("Scope" + "😀" * 6 + " 5")[-1] == ("5", "value")
    assert kinds("Scope 5")[-1] == ("5", "identifier")


def test_dollar_does_not_match_before_a_trailing_newline() -> None:
    assert classify_cell("12\n").kind == "value"  # 칸은 정규화가 줄바꿈을 지운다
    assert kinds("제\n3") == [("3", "value")]  # `제$` 는 줄바꿈 앞에서 맞지 않는다
