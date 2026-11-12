"""단위 환산. esg-lab `ts/ghg-calc/src/units.ts` 를 옮긴 것이다."""

from collections.abc import Sequence
from dataclasses import dataclass

from esgapi.core.calc.decimal import Decimal, format_decimal, is_negative, mul, parse_external_decimal
from esgapi.inventory.engines.scope12.engine_1.types import (
    Err,
    InvalidReferenceValue,
    Ok,
    Step,
    UnitConversion,
    UnitConversionAmbiguous,
    UnitConversionNotFound,
)


@dataclass(frozen=True, slots=True)
class Converted:
    value: Decimal
    step: Step | None  # 같은 단위면 환산 단계가 없다


def convert_unit(
    value: Decimal,
    from_unit: str,
    to_unit: str,
    table: Sequence[UnitConversion],
    context: str,
) -> Ok[Converted] | Err:
    """환산표에서 (from, to) 쌍을 그대로 찾는다. 역방향을 유도하거나 여러 단계를 잇지 않는다.

    (역수는 유한 소수가 아닐 수 있고, 경로가 여럿이면 근거가 흐려진다.)
    표에 없는 조합은 실패다. 예: m3 → Nm3 는 온도·압력 없이는 환산할 수 없으므로 표에 두지 않는다.
    """
    if from_unit == to_unit:
        return Ok(Converted(value, None))
    matches = [c for c in table if c.from_unit == from_unit and c.to_unit == to_unit]
    if not matches:
        return Err(UnitConversionNotFound(from_unit=from_unit, to_unit=to_unit, context=context))
    first = matches[0]
    if any(c.factor != first.factor for c in matches):
        return Err(
            UnitConversionAmbiguous(from_unit=from_unit, to_unit=to_unit, factors=tuple(c.factor for c in matches))
        )
    factor = parse_external_decimal(first.factor)
    if factor is None or is_negative(factor):
        return Err(InvalidReferenceValue(where=f"unitConversions[{from_unit}->{to_unit}].factor", value=first.factor))
    converted = mul(value, factor)
    return Ok(
        Converted(
            converted,
            Step(
                label=f"단위 환산 ({context})",
                formula=f"{format_decimal(value)} {from_unit} × {format_decimal(factor)} {to_unit}/{from_unit}",
                result=format_decimal(converted),
                unit=to_unit,
                conversion=first,
            ),
        )
    )
