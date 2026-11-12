"""`round_decimal` 의 빈틈 둘(밴드 MUT1). 변이 시험(MUT0)이 살아남은 변이로 찾은 자리를 지킨다. 순수 층.

옛 평평한 파일 `esgapi/core/tests/test_calc_decimal.py` 는 그대로 두고 여기에 더한다.
"""

import pytest

from esgapi.core.calc.decimal import Decimal, RoundingMode, round_decimal


@pytest.mark.parametrize("mode", ["half_up", "half_even", "down"])
@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (Decimal(25, 1), 3, "2.500"),
        (Decimal(5, 1), 3, "0.500"),
        (Decimal(125, 2), 4, "1.2500"),
        (Decimal(-25, 1), 3, "-2.500"),
    ],
)
def test_a_value_with_fewer_decimals_than_digits_is_padded_with_zeros(
    value: Decimal, digits: int, expected: str, mode: RoundingMode
) -> None:
    # 소수 자리(scale)가 1 이상이고 digits 보다 적은 값은 0 을 채우는 가지로 간다.
    # scale 0 인 값은 그 가지의 지수 `digits - scale` 이 `digits + scale` 과 같아 이 자리를 못 지킨다.
    assert round_decimal(value, digits, mode) == expected


@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (Decimal(-5, 1), 3, "-0.500"),  # 0 을 채우는 가지
        (Decimal(-1234, 4), 3, "-0.123"),  # 반올림 가지
        (Decimal(-5, 1), 0, "-1"),  # half_up 은 절댓값에: -0.5 → -1
    ],
)
def test_a_negative_value_below_one_in_magnitude_keeps_its_leading_zero(
    value: Decimal, digits: int, expected: str
) -> None:
    assert round_decimal(value, digits, "half_up") == expected
