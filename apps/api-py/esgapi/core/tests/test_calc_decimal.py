"""십진 연산. esg-lab `ts/kernel/test/decimal.test.ts` 10건을 옮겼다.

`ts/ghg-calc/test/decimal.test.ts` 7건은 그 가운데 앞의 일곱과 글자까지 같은 테스트다(옛 경로의 재수출을 쟀다).
파이썬에는 재수출이 없으므로 같은 일곱 함수가 둘을 다 맡는다.

순수 층: DB 도 Django 도 쓰지 않는다. 커널과 같이 inventory 에서 core 로 옮겼다(밴드 PY8a).
그 10건 가운데 출처(provenance)의 갈래를 재는 1건은 커널의 것이 아니라 inventory 에 남겼다
(`esgapi/inventory/tests/test_provenance.py`. core 는 업무 모듈을 import 하지 않는다 — 계약 가).
"""

from typing import Any

import pytest

from esgapi.core.calc.decimal import (
    EXTERNAL_MAX_LENGTH,
    ZERO,
    Decimal,
    RoundingMode,
    add,
    equals,
    format_decimal,
    is_decimal_string,
    is_negative,
    mul,
    parse_decimal,
    parse_external_decimal,
    round_decimal,
)


def d(text: str) -> Decimal:
    value = parse_decimal(text)
    if value is None:
        raise AssertionError(f"bad literal {text}")
    return value


# ── 십진 연산 ─────────────────────────────────────────────────────────


def test_sums_and_products_that_drift_in_floating_point_are_exact() -> None:
    assert format_decimal(add(d("0.1"), d("0.2"))) == "0.3"
    assert format_decimal(mul(d("1.1"), d("1.1"))) == "1.21"
    assert format_decimal(mul(d("0.0352"), d("73200"))) == "2576.64"


def test_notation_is_normalized() -> None:
    assert format_decimal(d("1.500")) == "1.5"
    assert format_decimal(d("0.000")) == "0"
    assert format_decimal(d("-0.0")) == "0"
    assert format_decimal(d("007")) == "7"
    assert format_decimal(d("-0.050")) == "-0.05"
    # 정규화가 값의 꼴 자체에 걸려 있다: 같은 값은 같은 (coef, scale) 이다.
    assert d("1.50") == Decimal(15, 1)
    assert d("0.000") == Decimal(0, 0)


# 거부하는 글자 10종 (TS 의 표 그대로)
@pytest.mark.parametrize("text", ["", " 1", "1e3", "1,000", "+1", ".5", "5.", "abc", "NaN", "Infinity"])
def test_non_decimal_strings_are_rejected(text: str) -> None:
    assert parse_decimal(text) is None


# 파이썬에서만 갈리는 자리: `\d` 는 전각·아랍 숫자를 받고, `$` 는 끝의 줄바꿈 앞에서 맞는다. 둘 다 거부해야 한다.
@pytest.mark.parametrize("text", ["１２", "١٢", "1\n", "\n1", "1 ", "1.5\n", "-", "--1", "1.2.3", "0x10", "1_000"])
def test_python_specific_look_alikes_are_rejected(text: str) -> None:
    assert parse_decimal(text) is None
    assert not is_decimal_string(text)


def test_non_strings_are_rejected() -> None:
    values: list[Any] = [1.5, None, 15, True, b"1.5", ["1"]]
    for value in values:
        assert parse_decimal(value) is None


def test_a_very_large_times_a_very_small_number_keeps_every_digit() -> None:
    product = mul(d("123456789012345678901234567890"), d("0.000000000000000000000000000001"))
    assert format_decimal(product) == "0.12345678901234567890123456789"


# ── 반올림 (엔진의 유일한 반올림 자리) ────────────────────────────────

# 반올림 표 13행 (TS 의 표 그대로). 음수는 절댓값에 반올림하고 부호를 붙인다: half_up -2.5 → -3, down -2.5 → -2.
ROUNDING: list[tuple[str, int, RoundingMode, str]] = [
    ("2.5", 0, "half_up", "3"),
    ("2.5", 0, "half_even", "2"),
    ("3.5", 0, "half_even", "4"),
    ("2.5", 0, "down", "2"),
    ("2.4999", 0, "half_up", "2"),
    ("2.5596384", 3, "half_up", "2.560"),
    ("2.5596384", 3, "down", "2.559"),
    ("-2.5", 0, "half_up", "-3"),
    ("-2.5", 0, "down", "-2"),
    ("0.0004", 3, "half_up", "0.000"),
    ("7", 2, "half_up", "7.00"),
    ("0.125", 2, "half_even", "0.12"),
    ("0.135", 2, "half_even", "0.14"),
]


@pytest.mark.parametrize(("value", "digits", "mode", "expected"), ROUNDING)
def test_rounding(value: str, digits: int, mode: RoundingMode, expected: str) -> None:
    assert round_decimal(d(value), digits, mode) == expected


def test_digits_must_be_a_non_negative_integer() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        round_decimal(d("1"), -1, "half_up")
    bad: Any = 1.5
    with pytest.raises(ValueError, match="non-negative integer"):
        round_decimal(d("1"), bad, "half_up")
    as_bool: Any = True  # 파이썬에서는 True 가 정수 1 로 통한다. 자릿수로 받지 않는다.
    with pytest.raises(ValueError, match="non-negative integer"):
        round_decimal(d("1"), as_bool, "half_up")


# ── 커널에 모으며 더한 것 ─────────────────────────────────────────────


def test_is_decimal_string_accepts_exactly_what_parse_decimal_accepts() -> None:
    for text in ["0", "-1.50", "007", "12.000"]:
        assert is_decimal_string(text)
    rejected: list[Any] = ["", " 1", "1e3", "1,000", "+1", ".5", "5.", 1.5, None]
    for text in rejected:
        assert not is_decimal_string(text)
        assert parse_decimal(text) is None


def test_zero_equals_is_negative() -> None:
    assert equals(d("0.00"), ZERO)
    assert equals(d("1.50"), d("1.5"))
    assert not equals(d("1.5"), d("1.51"))
    assert is_negative(d("-0.01"))
    assert not is_negative(d("-0.0"))


# ── 파이썬으로 옮기며 더한 것: 바깥 입력의 길이 상한 ──────────────────


def test_external_numbers_are_capped_at_64_characters() -> None:
    assert EXTERNAL_MAX_LENGTH == 64
    at_limit = "9" * 64
    assert parse_external_decimal(at_limit) == Decimal(int(at_limit), 0)
    assert parse_external_decimal("9" * 65) is None
    assert parse_external_decimal("-" + "9" * 63) is not None  # 부호와 소수점도 글자로 센다
    assert parse_external_decimal("-" + "9" * 64) is None
    # 엔진이 자기가 낸 문자열을 다시 읽는 parse_decimal 에는 상한이 없다.
    assert parse_decimal("9" * 65) == Decimal(int("9" * 65), 0)


def test_digits_beyond_the_interpreter_limit_are_none_not_an_exception() -> None:
    # 파이썬 3.13 은 4,300자리를 넘는 문자열 → 정수 변환을 ValueError 로 막는다. parse 는 던지지 않고 None 을 준다.
    assert parse_decimal("1" * 4300) is not None
    assert parse_decimal("1" * 4301) is None
    assert parse_decimal("0." + "1" * 5000) is None
