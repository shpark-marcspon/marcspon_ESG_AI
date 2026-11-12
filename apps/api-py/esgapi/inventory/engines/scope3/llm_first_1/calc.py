"""한 행의 배출량 = 활동량(또는 보정한 금액) × 계수. esg-lab `ts/scope3/src/domain/calc.ts` 를 옮긴 것이다.

결과는 tCO2eq 다(Scope 1·2 와 같은 단위, `sid:MARC-ENT-264`). 계수 분자가 kg CO2e 라서 kg 으로 곱한 끝에
× 0.001(units 의 kg → tonne 환산 계수)을 `_to_tonnes` 한 자리에서만 곱한다. 계수 칸(factor_unit·factor_value_raw)은
kg 그대로다. 분자가 t CO2e 인 계수를 받게 되면(`KG_CO2E_NUMERATORS` 가 바뀌면) 이 환산을 다시 정한다.

계산은 전부 십진 정확 연산이고(float 가 닿지 않는다) 생성 모델은 관여하지 않는다.
계산할 수 없는 사정은 0 이나 빈 값이 아니라 갈래(status)로 돌려준다. 반올림하지 않는다.

TS 와 다르게 한 것:
  - 바깥에서 온 수(수량·금액·무게·거리, 보정 계수, 계수의 value_raw)는 64자 상한으로 읽는다(`parse_external_decimal`).
  - TS 는 계수의 value_raw 와 보정 계수를 「이미 검사된 것」으로 단언했다. 여기서는 못 읽으면
    `invalid_number`(field "valueRaw"·"multiplier")로 돌려준다. 카탈로그(`catalog.py`)와 `check_adjustments` 를 거친
    값에서는 일어나지 않는 갈래다.
  - TS 의 `AdjustmentError` 예외는 문제 목록(`check_adjustments`)으로 바꿨다.
  - 행 입력(수량·금액·무게·거리)의 음수는 Scope 1·2 의 「음수 사용량」(`activity.check_amount`)처럼 거절해
    `invalid_number` 로 돌려준다. 0 은 받는다. 계수의 value_raw 와 보정 계수의 음수는 거절하지 않는다(재활용 크레딧 등).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.core.calc.decimal import Decimal, format_decimal, is_negative, mul, parse_decimal, parse_external_decimal
from esgapi.inventory.engines.scope3.llm_first_1.types import Factor, InputRow
from esgapi.inventory.engines.scope3.llm_first_1.units import conversion_factor, js_trim, unit_dim

# 이미 CO2 환산 kg 인 분자 단위 표기. 이 밖의 분자는 계산하지 않는다.
KG_CO2E_NUMERATORS: Final = frozenset({"kg CO2e", "kg CO2 eq"})

NumberField = Literal["quantity", "amount", "weightKg", "distanceKm", "valueRaw", "multiplier"]


@dataclass(frozen=True, slots=True)
class AdjustmentSource:
    url: str
    checked_on: str


@dataclass(frozen=True, slots=True)
class CurrencyAdjustment:
    """지출 기반 계수(USD, 기준 연도 가격)에 맞추는 환율·물가 보정 계수.

    금액 × multiplier = 계수의 통화·기준 연도 금액. 어떤 환율과 물가지수를 쓸지는 결정 대기라 저장소에 실제 값이 없다.
    출처(URL, 확인 일자)가 없으면 `synthetic` 이 참이어야 한다.
    """

    currency: str
    target_currency: str
    target_price_year: int
    multiplier: str
    synthetic: bool
    source: AdjustmentSource | None


@dataclass(frozen=True, slots=True)
class AdjustmentProblem:
    index: int
    kind: Literal["invalid_multiplier", "missing_source"]
    message: str


def check_adjustments(adjustments: Sequence[CurrencyAdjustment]) -> tuple[AdjustmentProblem, ...]:
    """보정 계수의 문제 목록. 비어 있으면 쓸 수 있다. 문장에는 받은 값을 싣지 않는다(통화 이름만)."""
    problems: list[AdjustmentProblem] = []
    for index, adjustment in enumerate(adjustments):
        if parse_external_decimal(adjustment.multiplier) is None:
            problems.append(AdjustmentProblem(index, "invalid_multiplier", "보정 계수가 십진 문자열이 아니다"))
        if not adjustment.synthetic and adjustment.source is None:
            message = f"{adjustment.currency} 보정 계수에 출처가 없다. 출처를 적거나 synthetic 으로 표시한다"
            problems.append(AdjustmentProblem(index, "missing_source", message))
    return tuple(problems)


# ── 결과: 9갈래 ──


@dataclass(frozen=True, slots=True, kw_only=True)
class Computed:
    """`co2e` 는 tCO2eq 의 십진 문자열이다(`unit`). 반올림하지 않는다. `formula` 는 그 값까지의 식(끝이 kg → t 환산).

    `activity_amount` 는 계수의 분모 단위로 맞춘 활동량. `synthetic` 은 가상 보정 계수가 들어간 결과면 참이다
    (실제 배출량으로 쓰지 않는다).
    """

    co2e: str
    unit: Literal["tCO2eq"] = "tCO2eq"
    factor_id: str
    factor_value_raw: str
    factor_unit: str
    activity_amount: str
    formula: str
    adjustment: CurrencyAdjustment | None
    synthetic: bool
    status: Literal["computed"] = "computed"


@dataclass(frozen=True, slots=True)
class NeedsDistance:
    """운송 행에 거리가 없다. 거리는 입력으로 받고 추정하지 않는다(0 으로 치지 않는다)."""

    factor_id: str
    status: Literal["needs_distance"] = "needs_distance"


@dataclass(frozen=True, slots=True)
class NeedsCurrencyAdjustment:
    """지출 기반 계수인데 그 통화의 환율·물가 보정 계수가 없다."""

    factor_id: str
    currency: str | None
    target_currency: str
    target_price_year: int
    status: Literal["needs_currency_adjustment"] = "needs_currency_adjustment"


@dataclass(frozen=True, slots=True)
class MissingQuantity:
    factor_id: str
    status: Literal["missing_quantity"] = "missing_quantity"


@dataclass(frozen=True, slots=True)
class MissingAmount:
    factor_id: str
    status: Literal["missing_amount"] = "missing_amount"


@dataclass(frozen=True, slots=True)
class InvalidNumber:
    factor_id: str
    field: NumberField
    status: Literal["invalid_number"] = "invalid_number"


@dataclass(frozen=True, slots=True)
class UnitMismatch:
    factor_id: str
    row_unit: str | None
    factor_unit: str
    status: Literal["unit_mismatch"] = "unit_mismatch"


@dataclass(frozen=True, slots=True)
class UnsupportedFactorUnit:
    factor_id: str
    factor_unit: str
    status: Literal["unsupported_factor_unit"] = "unsupported_factor_unit"


@dataclass(frozen=True, slots=True)
class NotCalculated:
    """추천이 없어 계산하지 않았다."""

    reason: str
    status: Literal["not_calculated"] = "not_calculated"


type CalcResult = (
    Computed
    | NeedsDistance
    | NeedsCurrencyAdjustment
    | MissingQuantity
    | MissingAmount
    | InvalidNumber
    | UnitMismatch
    | UnsupportedFactorUnit
    | NotCalculated
)


@dataclass(frozen=True, slots=True)
class _Amount:
    value: Decimal
    text: str


def _physical_amount(row: InputRow, factor: Factor) -> _Amount | CalcResult:
    transport = row.transport
    if transport is not None and transport.weight_kg is not None:
        if conversion_factor("tonne_km", factor.denominator_dim) is None:
            return UnitMismatch(factor.id, "tonne.km", factor.unit)
        weight = parse_external_decimal(transport.weight_kg)
        if weight is None or is_negative(weight):
            return InvalidNumber(factor.id, "weightKg")
        if transport.distance_km is None:
            return NeedsDistance(factor.id)
        distance = parse_external_decimal(transport.distance_km)
        if distance is None or is_negative(distance):
            return InvalidNumber(factor.id, "distanceKm")
        kg_to_tonne = parse_decimal(conversion_factor("kg", "tonne"))
        if kg_to_tonne is None:  # pragma: no cover  (conversion_factor("kg", "tonne") 은 늘 "0.001" 이다)
            raise AssertionError("kg → tonne 환산 계수가 없다")
        text = f"{transport.weight_kg} kg × 0.001 × {transport.distance_km} km"
        return _Amount(mul(mul(weight, kg_to_tonne), distance), text)
    to_factor = conversion_factor(unit_dim(row.unit), factor.denominator_dim)
    if to_factor is None:
        return UnitMismatch(factor.id, row.unit, factor.unit)
    if row.quantity is None:
        return MissingQuantity(factor.id)
    quantity = parse_external_decimal(row.quantity)
    if quantity is None or is_negative(quantity):
        return InvalidNumber(factor.id, "quantity")
    multiplier = parse_decimal(to_factor)
    if multiplier is None:  # pragma: no cover  (conversion_factor 는 십진 문자열만 낸다)
        raise AssertionError("환산 계수가 십진 문자열이 아니다")
    unit = row.unit if row.unit is not None else ""
    text = js_trim(f"{row.quantity} {unit}") if to_factor == "1" else f"{row.quantity} {unit} × {to_factor}"
    return _Amount(mul(quantity, multiplier), text)


def _to_tonnes(kg: Decimal) -> _Amount:
    """kg CO2e → tCO2eq. 배출량을 톤으로 바꾸는 자리는 여기 하나다. text 는 곱한 환산 계수의 글자(식의 끝)."""
    factor = conversion_factor("kg", "tonne")
    multiplier = parse_decimal(factor)
    if factor is None or multiplier is None:  # pragma: no cover  (kg → tonne 환산은 units 에 늘 있다)
        raise AssertionError("kg → tonne 환산 계수가 없다")
    return _Amount(mul(kg, multiplier), factor)


def calculate_row(row: InputRow, factor: Factor, adjustments: Sequence[CurrencyAdjustment] = ()) -> CalcResult:
    if factor.unit_numerator not in KG_CO2E_NUMERATORS:
        return UnsupportedFactorUnit(factor.id, factor.unit)
    value = parse_external_decimal(factor.value_raw)
    if value is None:
        return InvalidNumber(factor.id, "valueRaw")

    if factor.factor_type == "spend":
        spend = factor.spend
        if spend is None:
            return UnsupportedFactorUnit(factor.id, factor.unit)
        if row.amount is None:
            return MissingAmount(factor.id)
        amount = parse_external_decimal(row.amount)
        if amount is None or is_negative(amount):
            return InvalidNumber(factor.id, "amount")
        # 통화·대상 통화·기준 연도가 정확히 같은 보정 계수만 쓴다(가까운 연도로 대신하지 않는다).
        adjustment = next(
            (
                candidate
                for candidate in adjustments
                if candidate.currency == row.currency
                and candidate.target_currency == spend.currency
                and candidate.target_price_year == spend.price_year
            ),
            None,
        )
        if adjustment is None:
            return NeedsCurrencyAdjustment(factor.id, row.currency, spend.currency, spend.price_year)
        multiplier = parse_external_decimal(adjustment.multiplier)
        if multiplier is None:
            return InvalidNumber(factor.id, "multiplier")
        adjusted = mul(amount, multiplier)
        currency = row.currency if row.currency is not None else ""
        tonnes = _to_tonnes(mul(adjusted, value))
        return Computed(
            co2e=format_decimal(tonnes.value),
            factor_id=factor.id,
            factor_value_raw=factor.value_raw,
            factor_unit=factor.unit,
            activity_amount=format_decimal(adjusted),
            formula=(
                f"{row.amount} {currency} × {adjustment.multiplier} × {factor.value_raw} {factor.unit} × {tonnes.text}"
            ),
            adjustment=adjustment,
            synthetic=adjustment.synthetic,
        )

    amount = _physical_amount(row, factor)
    if not isinstance(amount, _Amount):
        return amount
    tonnes = _to_tonnes(mul(amount.value, value))
    return Computed(
        co2e=format_decimal(tonnes.value),
        factor_id=factor.id,
        factor_value_raw=factor.value_raw,
        factor_unit=factor.unit,
        activity_amount=format_decimal(amount.value),
        formula=f"{amount.text} × {factor.value_raw} {factor.unit} × {tonnes.text}",
        adjustment=None,
        synthetic=False,
    )
