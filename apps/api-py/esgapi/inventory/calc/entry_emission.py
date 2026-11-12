"""입력 행 하나의 배출량 셈(결정 MARC-ENT-463 — 디자인 산식, 밴드 S12a). 순수하다(django 0).

    활동량(행 단위) → 판 투입 단위 → [순발열량 켬: × ncv → ncv 단위 에너지] → 계수 분모 단위
      → × Σ(켠 가스의 계수 × GWP) → 계수 분자 질량 → t        = tCO2-eq

단위는 **잡은 판의 글자를 따른다**(input_unit · ncv_unit · factor_unit `<질량>/<단위>`). 계수 단위의 기본값
(default_factor_unit — MARC-ENT-474 권장안)은 판을 만들 때 한 번 쓰일 뿐 여기서는 부르지 않는다: 474 답이 와서
판의 factor_unit 이 `t/TJ` 로 바뀌면 같은 입력의 결과가 그대로 1/1000 이 된다.
환산은 부르는 쪽이 넘긴 쌍(unit-conversions.json)만 쓴다 — 같은 단위면 1, 쌍이 없으면 unit_conversion_missing
(역·다단을 유도하지 않는다). 산화계수는 없다(디자인 산식).
곱셈뿐이라 결과는 유한 소수다. 중간 반올림을 막으려고 넉넉한 정밀도 문맥에서 셈하고(Inexact 를 막는다),
끝에 한 번 소수 12자리 ROUND_HALF_UP[우리 해석 — 저장 칸 Decimal(30,12)]으로 자른다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Context, Decimal, Inexact, localcontext
from typing import Final

EMISSION_UNIT: Final = "t"
EMISSION_PLACES: Final = Decimal(10) ** -12
EMISSION_INTEGER_DIGITS: Final = 18  # Decimal(30,12) 의 정수부
_PRECISION: Final = 400  # 곱셈 몇 번의 정확한 결과가 들어가는 자릿수(넘치면 Inexact)


@dataclass(frozen=True)
class Gas:
    """켠 가스 한 줄의 값(계수 · GWP). 끈 가스는 넘기지 않는다."""

    factor: Decimal
    gwp: Decimal


@dataclass(frozen=True)
class Version:
    """잡은 판의 셈 칸. ncv 가 None 이면 순발열량 끔."""

    input_unit: str
    ncv: Decimal | None
    ncv_unit: str | None
    factor_unit: str
    gases: Sequence[Gas]


@dataclass(frozen=True)
class Problem:
    """셈할 수 없는 까닭(행의 emission_problem 칸 글자 — 40자 안)."""

    code: str


UNIT_CONVERSION_MISSING: Final = Problem("unit_conversion_missing")
FACTOR_UNIT_INVALID: Final = Problem("factor_unit_invalid")
EMISSION_OUT_OF_RANGE: Final = Problem("emission_out_of_range")


def _rate(source: str, target: str, conversions: Mapping[tuple[str, str], Decimal]) -> Decimal | None:
    if source == target:
        return Decimal(1)
    return conversions.get((source, target))


def emission(
    total: Decimal | None,
    row_unit: str,
    version: Version,
    conversions: Mapping[tuple[str, str], Decimal],
) -> Decimal | Problem | None:
    """행의 활동량 합(행 단위)의 배출량(tCO2-eq). 합이 없으면(빈 행·N/A — 부르는 쪽이 None 을 넘김) None."""
    if total is None:
        return None
    numerator, slash, denominator = version.factor_unit.partition("/")
    if slash != "/" or not numerator or not denominator:
        return FACTOR_UNIT_INVALID
    context = Context(prec=_PRECISION, traps=[Inexact])
    with localcontext(context):
        to_input = _rate(row_unit, version.input_unit, conversions)
        if to_input is None:
            return UNIT_CONVERSION_MISSING
        quantity = total * to_input
        if version.ncv is not None:
            if version.ncv_unit is None:
                return FACTOR_UNIT_INVALID
            to_denominator = _rate(version.ncv_unit, denominator, conversions)
            quantity = quantity * version.ncv
        else:
            to_denominator = _rate(version.input_unit, denominator, conversions)
        if to_denominator is None:
            return UNIT_CONVERSION_MISSING
        quantity = quantity * to_denominator
        weighted = sum((gas.factor * gas.gwp for gas in version.gases), Decimal(0))
        to_tonnes = _rate(numerator, EMISSION_UNIT, conversions)
        if to_tonnes is None:
            return UNIT_CONVERSION_MISSING
        tonnes = quantity * weighted * to_tonnes
    result = tonnes.quantize(EMISSION_PLACES, rounding=ROUND_HALF_UP, context=Context(prec=_PRECISION))
    if result.adjusted() >= EMISSION_INTEGER_DIGITS:
        return EMISSION_OUT_OF_RANGE
    return result
