"""한 행의 계산 9갈래. esg-lab `ts/scope3/test/calc.test.ts` 의 여덟과 그 기대 문자열을 옮겼다. 순수 층.

UT1 부터 결과는 tCO2eq(kg × 0.001)라 배출량·식의 기대 글자가 esg-lab(kg)과 다르다.
"""

import copy
import json
import re
from collections.abc import Callable
from dataclasses import replace
from typing import cast

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.core.calc.decimal import Decimal, equals, mul, parse_decimal
from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.llm_first_1.calc import (
    AdjustmentProblem,
    CalcResult,
    Computed,
    CurrencyAdjustment,
    InvalidNumber,
    MissingAmount,
    MissingQuantity,
    NeedsCurrencyAdjustment,
    NeedsDistance,
    UnitMismatch,
    UnsupportedFactorUnit,
    calculate_row,
    check_adjustments,
)
from esgapi.inventory.engines.scope3.llm_first_1.pipeline import PipelineResult, run_pipeline
from esgapi.inventory.engines.scope3.llm_first_1.serialize import calc_to_dict
from esgapi.inventory.tests.scope3_catalog_support import load_examples
from esgapi.inventory.tests.scope3_support import FACTOR_BY_ID, USD_2022, factor, row, transport
from esgapi.inventory.tests.test_flows import scope3_flow_result, scope3_harness
from esgapi.inventory.tests.test_scope3_golden_full import CONFIGS

# 테스트 전용 가상 환율·물가 보정 계수. 실제 환율이 아니다.
FX_SYNTHETIC = CurrencyAdjustment("KRW", "USD", 2022, "0.001", synthetic=True, source=None)


def test_activity_times_factor_is_exact_decimal() -> None:
    first = calculate_row(row("x", quantity="0.1", unit="kg"), FACTOR_BY_ID["syn:pp-kg"])
    assert first == Computed(
        co2e="0.000125",
        factor_id="syn:pp-kg",
        factor_value_raw="1.25",
        factor_unit="kg CO2e/kg",
        activity_amount="0.1",
        formula="0.1 kg × 1.25 kg CO2e/kg × 0.001",
        adjustment=None,
        synthetic=False,
    )
    second = calculate_row(row("x", quantity="1.5", unit="t"), FACTOR_BY_ID["syn:steel-kg"])
    assert isinstance(second, Computed)
    assert (second.co2e, second.activity_amount) == ("3.75", "1500")
    assert second.formula == "1.5 t × 1000 × 2.5 kg CO2e/kg × 0.001"
    assert calculate_row(row("x", quantity="0.3", unit="kg"), FACTOR_BY_ID["syn:truck"]).status == "unit_mismatch"


def test_unconvertible_unit_is_not_calculated() -> None:
    assert calculate_row(row("x", unit="대"), FACTOR_BY_ID["syn:steel-kg"]) == UnitMismatch(
        "syn:steel-kg", "대", "kg CO2e/kg"
    )


def test_missing_or_non_numeric_quantity_is_not_zero() -> None:
    steel = FACTOR_BY_ID["syn:steel-kg"]
    assert calculate_row(row("x", quantity=None), steel) == MissingQuantity("syn:steel-kg")
    assert calculate_row(row("x", quantity="1,000"), steel) == InvalidNumber("syn:steel-kg", "quantity")
    assert calculate_row(row("x", quantity="1e3"), steel) == InvalidNumber("syn:steel-kg", "quantity")
    assert calculate_row(row("x", quantity="１０"), steel) == InvalidNumber("syn:steel-kg", "quantity")


def test_external_numbers_are_capped_at_64_characters() -> None:
    steel = FACTOR_BY_ID["syn:steel-kg"]
    assert calculate_row(row("x", quantity="1" * 65), steel) == InvalidNumber("syn:steel-kg", "quantity")
    ok = calculate_row(row("x", quantity="1" * 64), steel)
    assert isinstance(ok, Computed)
    assert ok.co2e == "2" + "7" * 60 + ".7775"
    spend = FACTOR_BY_ID["syn:spend-computer"]
    assert calculate_row(row("x", amount="9" * 65), spend, [FX_SYNTHETIC]) == InvalidNumber(spend.id, "amount")
    long_multiplier = replace(FX_SYNTHETIC, multiplier="0." + "1" * 63)
    assert calculate_row(row("x"), spend, [long_multiplier]) == InvalidNumber(spend.id, "multiplier")
    long_value = factor("syn:long", "x", (1,), "activity", "kg", "1" * 65)
    assert calculate_row(row("x"), long_value) == InvalidNumber("syn:long", "valueRaw")
    exponent = factor("syn:exp", "x", (1,), "activity", "kg", "9e-05")
    assert calculate_row(row("x"), exponent) == InvalidNumber("syn:exp", "valueRaw")


def test_transport_row_without_distance_needs_distance() -> None:
    truck = FACTOR_BY_ID["syn:truck"]
    no_distance = row("x", quantity=None, unit=None, transport=transport(distance_km=None))
    assert calculate_row(no_distance, truck) == NeedsDistance("syn:truck")
    with_distance = row("x", quantity=None, unit=None, transport=transport(distance_km="300"))
    done = calculate_row(with_distance, truck)
    assert isinstance(done, Computed)
    assert (done.activity_amount, done.co2e) == ("6300", "0.63")
    assert done.formula == "21000 kg × 0.001 × 300 km × 0.1 kg CO2e/tonne.km × 0.001"
    bad_weight = row("x", transport=transport(weight_kg="21t", distance_km="300"))
    assert calculate_row(bad_weight, truck) == InvalidNumber("syn:truck", "weightKg")
    bad_distance = row("x", transport=transport(distance_km="약 300"))
    assert calculate_row(bad_distance, truck) == InvalidNumber("syn:truck", "distanceKm")
    # 운송 행은 톤·km 로만 잰다: 분모가 kg 인 계수와는 단위가 맞지 않는다.
    assert calculate_row(with_distance, FACTOR_BY_ID["syn:steel-kg"]) == UnitMismatch(
        "syn:steel-kg", "tonne.km", "kg CO2e/kg"
    )


def test_spend_basis_without_adjustment_needs_currency_adjustment() -> None:
    computer = FACTOR_BY_ID["syn:spend-computer"]
    assert calculate_row(row("x", amount="2000000", currency="KRW"), computer) == NeedsCurrencyAdjustment(
        "syn:spend-computer", "KRW", "USD", 2022
    )
    # 통화가 다른 보정 계수는 쓰지 않는다.
    other = calculate_row(row("x", amount="2000", currency="EUR"), computer, [FX_SYNTHETIC])
    assert other.status == "needs_currency_adjustment"
    # 금액이 이미 USD 여도 기준 연도 물가 보정이 필요하다.
    assert calculate_row(row("x", amount="2000", currency="USD"), computer).status == "needs_currency_adjustment"
    # 기준 연도가 다른 보정 계수도 쓰지 않는다.
    wrong_year = replace(FX_SYNTHETIC, target_price_year=2021)
    assert calculate_row(row("x"), computer, [wrong_year]).status == "needs_currency_adjustment"


def test_synthetic_adjustment_marks_the_result_synthetic() -> None:
    result = calculate_row(
        row("x", amount="2000000", currency="KRW"), FACTOR_BY_ID["syn:spend-computer"], [FX_SYNTHETIC]
    )
    assert result == Computed(
        co2e="1",
        factor_id="syn:spend-computer",
        factor_value_raw="0.5",
        factor_unit=f"kg CO2e/{USD_2022}",
        activity_amount="2000",
        formula=f"2000000 KRW × 0.001 × 0.5 kg CO2e/{USD_2022} × 0.001",
        adjustment=FX_SYNTHETIC,
        synthetic=True,
    )


def test_spend_basis_without_amount_is_missing_amount() -> None:
    result = calculate_row(row("x", amount=None, currency=None), FACTOR_BY_ID["syn:spend-computer"], [FX_SYNTHETIC])
    assert result == MissingAmount("syn:spend-computer")


def test_other_numerators_are_unsupported() -> None:
    other = factor("syn:co2", "x", (1,), "activity", "kg", "1", numerator="kg CO2")
    assert calculate_row(row("x"), other) == UnsupportedFactorUnit("syn:co2", "kg CO2/kg")
    assert calculate_row(row("x"), factor("syn:eq", "x", (1,), "activity", "kg", "2", numerator="kg CO2 eq")) == (
        Computed(
            co2e="0.02",
            factor_id="syn:eq",
            factor_value_raw="2",
            factor_unit="kg CO2 eq/kg",
            activity_amount="10",
            formula="10 kg × 2 kg CO2 eq/kg × 0.001",
            adjustment=None,
            synthetic=False,
        )
    )
    # 음수 계수는 TS 그대로 받는다(isDecimalString).
    negative = calculate_row(row("x"), factor("syn:neg", "x", (1,), "activity", "kg", "-0.5"))
    assert isinstance(negative, Computed)
    assert negative.co2e == "-0.005"


def test_adjustments_without_a_source_must_be_synthetic() -> None:
    assert [problem.kind for problem in check_adjustments([replace(FX_SYNTHETIC, synthetic=False)])] == [
        "missing_source"
    ]
    assert check_adjustments([replace(FX_SYNTHETIC, multiplier="1e-3")]) == (
        AdjustmentProblem(0, "invalid_multiplier", "보정 계수가 십진 문자열이 아니다"),
    )
    assert check_adjustments([FX_SYNTHETIC]) == ()


def test_negative_row_numbers_are_invalid_not_negative_emissions() -> None:
    """행 입력의 음수는 Scope 1·2 의 「음수 사용량」처럼 거절한다(D2). 0 은 Scope 1·2 처럼 받는다."""
    steel = FACTOR_BY_ID["syn:steel-kg"]
    assert calculate_row(row("x", quantity="-100"), steel) == InvalidNumber("syn:steel-kg", "quantity")
    spend = FACTOR_BY_ID["syn:spend-computer"]
    assert calculate_row(row("x", amount="-2000000"), spend, [FX_SYNTHETIC]) == InvalidNumber(spend.id, "amount")
    truck = FACTOR_BY_ID["syn:truck"]
    negative_weight = row("x", transport=transport(weight_kg="-21000", distance_km="300"))
    assert calculate_row(negative_weight, truck) == InvalidNumber("syn:truck", "weightKg")
    negative_distance = row("x", transport=transport(distance_km="-300"))
    assert calculate_row(negative_distance, truck) == InvalidNumber("syn:truck", "distanceKm")


def test_zero_row_numbers_are_computed_as_zero() -> None:
    zero_quantity = calculate_row(row("x", quantity="0"), FACTOR_BY_ID["syn:steel-kg"])
    assert isinstance(zero_quantity, Computed)
    assert zero_quantity.co2e == "0"
    zero_amount = calculate_row(row("x", amount="0"), FACTOR_BY_ID["syn:spend-computer"], [FX_SYNTHETIC])
    assert isinstance(zero_amount, Computed)
    assert zero_amount.co2e == "0"
    truck = FACTOR_BY_ID["syn:truck"]
    zero_weight = calculate_row(row("x", transport=transport(weight_kg="0", distance_km="300")), truck)
    zero_distance = calculate_row(row("x", transport=transport(distance_km="0")), truck)
    assert isinstance(zero_weight, Computed)
    assert isinstance(zero_distance, Computed)
    assert (zero_weight.co2e, zero_distance.co2e) == ("0", "0")


def test_negative_factor_value_and_multiplier_are_unchanged() -> None:
    """계수(valueRaw)·보정(multiplier)의 음수는 이 판에서 바꾸지 않는다: 재활용 크레딧 같은 음의 계수는 계산된다."""
    credit = calculate_row(row("x", quantity="2"), factor("syn:credit", "x", (1,), "activity", "kg", "-0.5"))
    assert isinstance(credit, Computed)
    assert credit.co2e == "-0.001"
    negative_multiplier = replace(FX_SYNTHETIC, multiplier="-0.001")
    spend = calculate_row(row("x", amount="2000000"), FACTOR_BY_ID["syn:spend-computer"], [negative_multiplier])
    assert isinstance(spend, Computed)
    assert spend.co2e == "-1"


# ── UT1: 결과는 tCO2eq(`sid:MARC-ENT-264`) ──
# kg 계수로 곱한 끝에서 한 번만 × 0.001 — 계산 층(T2)·서버 안(T3)에서 두 번 나누지 않고, 정밀도를 잃거나 지수 표기를
# 내지 않는다(T1). 옛 kg 결과 이름·옛 판은 꼴이 거절하고(T4), 계수 칸은 그대로다(T5). 옛 이름은 글자를 이어 붙여 짓는다.

SHAPE = "scope3.llm-first.result@2"
OLD_KEY = "emissions" + "KgCo2e"
PLAIN_DECIMAL = re.compile(r"-?[0-9]+(\.[0-9]+)?")
THOUSAND = Decimal(1000, 0)


def computed(result: CalcResult) -> Computed:
    assert isinstance(result, Computed), result
    return result


def activity() -> Computed:
    return computed(calculate_row(row("x", quantity="10", unit="kg"), FACTOR_BY_ID["syn:steel-kg"]))


def spend() -> Computed:
    return computed(calculate_row(row("x", amount="2000000"), FACTOR_BY_ID["syn:spend-computer"], [FX_SYNTHETIC]))


def moved() -> Computed:
    return computed(calculate_row(row("x", transport=transport(distance_km="300")), FACTOR_BY_ID["syn:truck"]))


def kg(*parts: str) -> Decimal:
    """시험이 따로 짓는 kg 값 — 계산 층의 함수를 거치지 않고 곱만 한다."""
    value = Decimal(1, 0)
    for part in parts:
        parsed = parse_decimal(part)
        assert parsed is not None
        value = mul(value, parsed)
    return value


# ── T1 정밀도·지수 표기 ──


def test_tonnes_keep_every_digit_without_exponent_or_trailing_zeros() -> None:
    one = factor("syn:one", "x", (1,), "activity", "kg", "1")
    tiny = computed(calculate_row(row("x", quantity="0.0000001", unit="kg"), one))
    assert tiny.co2e == "0.0000000001"
    whole = computed(calculate_row(row("x", quantity="1000", unit="kg"), one))
    assert whole.co2e == "1"
    big = computed(calculate_row(row("x", quantity="1" * 64), FACTOR_BY_ID["syn:steel-kg"]))
    assert big.co2e == "2" + "7" * 60 + ".7775"
    steel = computed(calculate_row(row("x", quantity="1.5", unit="t"), FACTOR_BY_ID["syn:steel-kg"]))
    assert steel.co2e == "3.75"
    for result in (tiny, whole, big, steel, activity(), spend(), moved()):
        assert PLAIN_DECIMAL.fullmatch(result.co2e), result.co2e
        assert "E" not in result.co2e and "e" not in result.co2e


# ── T2 한 번만 나눔(계산 층) ──


@pytest.mark.parametrize(
    ("make", "expected_kg"),
    [
        (activity, kg("10", "2.5")),
        (spend, kg("2000000", "0.001", "0.5")),
        (moved, kg("6300", "0.1")),  # 21000 kg × 0.001 × 300 km = 6300 tonne.km
    ],
    ids=["activity", "spend", "distance"],
)
def test_tonnes_times_a_thousand_is_the_kg_product(make: Callable[[], Computed], expected_kg: Decimal) -> None:
    result = make()
    tonnes = parse_decimal(result.co2e)
    assert tonnes is not None
    assert equals(mul(tonnes, THOUSAND), expected_kg), (result.co2e, expected_kg)
    assert result.formula.endswith(" × 0.001")


# ── T3 한 번만 나눔(서버 안: 직렬화·조립이 다시 환산하지 않는다) ──


def test_serializer_and_flow_carry_the_same_tonnes() -> None:
    name, shortlister, size, exclude, adjusted = CONFIGS[3]
    assert name == "d-exclude-disputed"  # 보정 계수를 쓰는 설정 — 지출 갈래도 계산된다
    rows = [example.row for example in load_examples()]
    flow = scope3_flow_result(scope3_harness(shortlister, size, exclude, adjusted).options, rows)
    direct = run_pipeline(rows, scope3_harness(shortlister, size, exclude, adjusted).options)
    assert isinstance(direct, PipelineResult)
    flow_rows = cast("list[dict[str, dict[str, object]]]", flow["rows"])
    seen = 0
    for entry, flow_row in zip(direct.rows, flow_rows, strict=True):
        if isinstance(entry.calc, Computed):
            seen += 1
            assert entry.calc.co2e == calc_to_dict(entry.calc)["co2e"] == flow_row["calc"]["co2e"]
            assert flow_row["calc"]["unit"] == "tCO2eq"
    assert seen > 0
    for result in (activity(), spend(), moved()):
        assert calc_to_dict(result)["co2e"] == result.co2e


# ── T4 옛 이름·옛 판 0 ──


def test_the_computed_keys_are_exactly_the_tonne_shape() -> None:
    assert list(calc_to_dict(spend())) == [
        "status",
        "co2e",
        "unit",
        "factorId",
        "factorValueRaw",
        "factorUnit",
        "activityAmount",
        "formula",
        "adjustment",
        "synthetic",
    ]
    # unit 은 실행 중 Literal 검사가 없다 — 「tCO2eq」 는 꼴 검사(strict)가 지킨다.
    calc_shape = TypeAdapter[object](shapes.CalcJson)
    for result in (activity(), spend(), moved()):
        calc_shape.validate_python(json.loads(json.dumps(calc_to_dict(result))), strict=True)


def done_result() -> dict[str, object]:
    """계산된 행이 있는 @2 결과. 꼴 검사를 통과한다."""
    _, shortlister, size, exclude, adjusted = CONFIGS[3]
    rows = [example.row for example in load_examples()]
    result = scope3_flow_result(scope3_harness(shortlister, size, exclude, adjusted).options, rows)
    result = json.loads(json.dumps(result))
    shapes.RESULT_SHAPES[SHAPE].validate_python(result, strict=True)
    return cast("dict[str, object]", result)


def first_computed(result: dict[str, object]) -> dict[str, object]:
    for flow_row in cast("list[dict[str, dict[str, object]]]", result["rows"]):
        if flow_row["calc"]["status"] == "computed":
            return flow_row["calc"]
    raise AssertionError("계산된 행이 없다")


def test_the_old_key_unit_or_version_is_rejected() -> None:
    base = done_result()
    with_old_key = copy.deepcopy(base)
    first_computed(with_old_key)[OLD_KEY] = "1"
    without_unit = copy.deepcopy(base)
    del first_computed(without_unit)["unit"]
    kg_unit = copy.deepcopy(base)
    first_computed(kg_unit)["unit"] = "kgCO2e"
    old_version = {**base, "schemaVersion": "scope3.llm-first.result@1"}
    for broken in (with_old_key, without_unit, kg_unit, old_version):
        with pytest.raises(ValidationError):
            shapes.RESULT_SHAPES[SHAPE].validate_python(broken, strict=True)
    assert "scope3.llm-first.result@1" not in shapes.RESULT_SHAPES
    assert OLD_KEY not in calc_to_dict(spend())


# ── T5 계수 칸 그대로 ──


def test_factor_fields_and_activity_amount_are_unchanged() -> None:
    picked = [
        (calc_to_dict(r)["factorUnit"], calc_to_dict(r)["factorValueRaw"], calc_to_dict(r)["activityAmount"])
        for r in (activity(), spend(), moved())
    ]
    assert picked == [
        ("kg CO2e/kg", "2.5", "10"),
        (FACTOR_BY_ID["syn:spend-computer"].unit, "0.5", "2000"),
        ("kg CO2e/tonne.km", "0.1", "6300"),
    ]
