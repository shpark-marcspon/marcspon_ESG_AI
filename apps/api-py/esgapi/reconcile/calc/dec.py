"""십진 도우미. esg-lab `ts/reconcile/src/domain/dec.ts`(48줄)를 옮겼다.

커널은 `esgapi.core.calc.decimal`(PY4 가 옮긴 `(coef, scale)`)을 **import 한다**. 베끼지 않는다.
reconcile 이 다른 업무 모듈을 import 하는 자리는 없다(커널은 core 에 있다. 밴드 PY8a 가 inventory/calc 에서 옮겼다).
값은 십진 문자열과 정수로만 다룬다. 나눗셈이 없고 단위 환산은 10 의 거듭제곱 자리 옮김뿐이다(`shift10`).
"""

from typing import Literal

from esgapi.core.calc.decimal import Decimal, RoundingMode, add, format_decimal, parse_decimal, round_decimal

__all__ = ["Decimal", "RoundingMode", "compare", "dec", "neg", "round_to_pow10", "shift10", "show", "sub"]


def dec(text: str) -> Decimal:
    """십진 문자열을 읽는다. 못 읽으면 예외다(부르는 쪽이 이미 표기 규칙으로 거른 뒤에만 부른다)."""
    parsed = parse_decimal(text)
    if parsed is None:
        raise ValueError(f"십진 문자열이 아니다: {text}")
    return parsed


def _renormalize(coef: int, scale: int) -> Decimal:
    """커널의 정규형(끝자리 0 없음)으로 되돌린다."""
    return dec(format_decimal(Decimal(coef, scale)))


def neg(value: Decimal) -> Decimal:
    return Decimal(-value.coef, value.scale)


def sub(a: Decimal, b: Decimal) -> Decimal:
    return add(a, neg(b))


def compare(a: Decimal, b: Decimal) -> Literal[-1, 0, 1]:
    """a - b 의 부호."""
    diff = sub(a, b).coef
    return 0 if diff == 0 else -1 if diff < 0 else 1


def shift10(value: Decimal, exp: int) -> Decimal:
    """값 × 10^exp. exp 는 음수일 수 있다. 정수가 아니면 예외다(TS 의 RangeError)."""
    if type(exp) is not int:
        raise ValueError(f"자리 옮김은 정수여야 한다: {exp}")
    if exp >= 0:
        return _renormalize(value.coef * 10**exp, value.scale)
    return _renormalize(value.coef, value.scale - exp)


def round_to_pow10(value: Decimal, exp: int, mode: RoundingMode) -> Decimal:
    """10^exp 의 배수로 반올림한다(exp 가 3 이면 천 단위, -1 이면 소수 첫째 자리)."""
    if exp <= 0:
        return dec(round_decimal(value, -exp, mode))
    scaled = shift10(value, -exp)
    return shift10(dec(round_decimal(scaled, 0, mode)), exp)


def show(value: Decimal) -> str:
    return format_decimal(value)
