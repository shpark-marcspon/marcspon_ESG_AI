"""십진 도우미. TS 에는 따로 테스트가 없다(`match.test.ts` 의 「단위 환산」이 간접으로 잰다). 여기서는 직접 잰다.

TS 와 같은 값을 내는지는 지은 문서 골든의 구획 `dec` 가 따로 잰다(`test_golden_synthetic.py`).
"""

import pytest

from esgapi.reconcile.calc.dec import compare, dec, neg, round_to_pow10, shift10, show, sub


def test_dec_reads_decimal_strings_and_raises_on_anything_else() -> None:
    assert show(dec("12.50")) == "12.5"  # 커널의 정규형: 끝자리 0 없음
    assert show(dec("-0.050")) == "-0.05"
    for bad in ("", "1e5", "1,234", "+1", " 1", "１２", "١٢", "1.", ".5", "abc"):
        with pytest.raises(ValueError, match="십진 문자열이 아니다"):
            dec(bad)


def test_shift10_moves_the_decimal_point_both_ways() -> None:
    assert show(shift10(dec("12.5"), 3)) == "12500"
    assert show(shift10(dec("12.5"), -2)) == "0.125"
    assert show(shift10(dec("0.123"), 2)) == "12.3"  # 퍼센트 서식의 ×100
    assert show(shift10(dec("1200"), -2)) == "12"
    assert show(shift10(dec("0"), 5)) == "0"
    assert show(shift10(dec("-7"), 0)) == "-7"


def test_shift10_refuses_a_non_integer_exponent() -> None:
    with pytest.raises(ValueError, match="자리 옮김은 정수여야 한다"):
        shift10(dec("1"), 1.5)  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="자리 옮김은 정수여야 한다"):
        shift10(dec("1"), True)


def test_round_to_pow10_rounds_to_a_multiple_of_a_power_of_ten() -> None:
    assert show(round_to_pow10(dec("1250"), 2, "half_up")) == "1300"
    assert show(round_to_pow10(dec("1250"), 2, "half_even")) == "1200"
    assert show(round_to_pow10(dec("1350"), 2, "half_even")) == "1400"
    assert show(round_to_pow10(dec("1250"), 2, "down")) == "1200"
    assert show(round_to_pow10(dec("-1250"), 2, "half_up")) == "-1300"  # 절댓값에 반올림하고 부호를 붙인다
    assert show(round_to_pow10(dec("-1250"), 2, "down")) == "-1200"
    assert show(round_to_pow10(dec("12.345"), -2, "half_up")) == "12.35"
    assert show(round_to_pow10(dec("12.345"), -2, "half_even")) == "12.34"
    assert show(round_to_pow10(dec("12.345"), -2, "down")) == "12.34"
    assert show(round_to_pow10(dec("12.5"), 0, "half_even")) == "12"
    assert show(round_to_pow10(dec("499"), 3, "half_up")) == "0"
    assert show(round_to_pow10(dec("999"), 3, "half_up")) == "1000"


def test_compare_sub_neg() -> None:
    assert compare(dec("1"), dec("1.0")) == 0
    assert compare(dec("0.30"), dec("0.3")) == 0
    assert compare(dec("1"), dec("2")) == -1
    assert compare(dec("-1"), dec("-2")) == 1
    assert compare(dec("10"), dec("9.999")) == 1
    assert show(sub(dec("1"), dec("0.9"))) == "0.1"  # 이진 부동소수의 꼬리가 없다
    assert show(sub(dec("0.1"), dec("0.3"))) == "-0.2"
    assert show(neg(dec("0"))) == "0"
    assert show(neg(dec("-2.5"))) == "2.5"
