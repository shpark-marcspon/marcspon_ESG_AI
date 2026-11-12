"""행 계산. esg-lab `ts/ghg-calc/test/calc.test.ts` 30건을 옮기고, 파이썬으로 옮기며 생긴 자리를 더했다. 순수 층."""

import dataclasses
from typing import Any

import pytest

from esgapi.core.calc.decimal import Decimal
from esgapi.inventory.engines.scope12.engine_1.calc import calculate_raw_row, calculate_row
from esgapi.inventory.engines.scope12.engine_1.provenance import Synthetic
from esgapi.inventory.engines.scope12.engine_1.types import (
    CalcOptions,
    CalorificBasisMismatch,
    Err,
    FactorAmbiguous,
    FactorIncomplete,
    FactorKindMismatch,
    FactorNotFound,
    GwpSet,
    GwpSetAmbiguous,
    GwpSetNotFound,
    GwpValueMissing,
    InvalidActivity,
    InvalidReferenceValue,
    Ok,
    ParameterTiers,
    PurchasedEmissionFactor,
    PurchasedEnergyFactor,
    RowFailed,
    Step,
    UnitConversion,
    UnitConversionAmbiguous,
    UnitConversionNotFound,
)
from esgapi.inventory.engines.scope12.engine_1.units import Converted, convert_unit
from esgapi.inventory.tests.support import (
    AR5_GWP,
    COMMERCIAL,
    DIESEL_ID,
    ELECTRICITY_ID,
    ETS_GWP,
    MANUFACTURING,
    SYNTHETIC_GWP,
    TIER2,
    bare,
    diesel_factor,
    failure_of,
    load_tables,
    ok,
    row,
)

tables = load_tables()
ETS = CalcOptions(gwp_set_id=ETS_GWP)
SYNTHETIC = Synthetic(note="t")
ONE = Decimal(1, 0)


# ── 단위 환산 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("from_unit", "to_unit", "expected"),
    [
        ("L", "kL", "0.001"),
        ("kL", "L", "1000"),
        ("m3", "L", "1000"),
        ("kg", "t", "0.001"),
        ("t", "kg", "1000"),
        ("kWh", "MWh", "0.001"),
        ("kWh", "MJ", "3.6"),
        ("MWh", "GJ", "3.6"),
        ("MJ", "GJ", "0.001"),
        ("GJ", "TJ", "0.001"),
        ("MJ", "TJ", "0.000001"),
        ("Nm3", "kNm3", "0.001"),
    ],
)
def test_unit_conversion_factors(from_unit: str, to_unit: str, expected: str) -> None:
    result = convert_unit(ONE, from_unit, to_unit, tables.unit_conversions, "test")
    assert isinstance(result, Ok)
    assert result.value.step is not None
    assert result.value.step.result == expected


def test_same_unit_needs_no_conversion_step() -> None:
    assert convert_unit(ONE, "L", "L", [], "test") == Ok(Converted(ONE, None))


# 역방향을 유도하지 않는다: 표에 L → kg 이 없으면 kg → L 이 있어도(없지만) 실패다. m3 → Nm3 는 일부러 표에 없다.
@pytest.mark.parametrize(("from_unit", "to_unit"), [("m3", "Nm3"), ("L", "kg"), ("kWh", "L"), ("L", "liter")])
def test_unconvertible_pairs_fail_explicitly(from_unit: str, to_unit: str) -> None:
    result = convert_unit(ONE, from_unit, to_unit, tables.unit_conversions, "test")
    assert result == Err(UnitConversionNotFound(from_unit=from_unit, to_unit=to_unit, context="test"))


def test_the_reverse_direction_is_not_derived() -> None:
    """(a → b) 만 있는 표에서 (b → a) 는 찾지 못한다. 역수를 만들지 않는다(유한 소수가 아닐 수 있다)."""
    table = [UnitConversion(from_unit="a", to_unit="b", factor="4", source=SYNTHETIC)]
    assert isinstance(convert_unit(ONE, "a", "b", table, "test"), Ok)
    assert convert_unit(ONE, "b", "a", table, "test") == Err(
        UnitConversionNotFound(from_unit="b", to_unit="a", context="test")
    )


def test_negative_conversion_factor_is_invalid_reference_value() -> None:
    table = [UnitConversion(from_unit="a", to_unit="b", factor="-2", source=SYNTHETIC)]
    result = convert_unit(ONE, "a", "b", table, "test")
    assert result == Err(InvalidReferenceValue(where="unitConversions[a->b].factor", value="-2"))


def test_two_factors_for_one_pair_are_not_chosen_between() -> None:
    table = [
        UnitConversion(from_unit="a", to_unit="b", factor="2", source=SYNTHETIC),
        UnitConversion(from_unit="a", to_unit="b", factor="3", source=SYNTHETIC),
    ]
    result = convert_unit(ONE, "a", "b", table, "test")
    assert result == Err(UnitConversionAmbiguous(from_unit="a", to_unit="b", factors=("2", "3")))
    # 같은 계수가 두 번 적힌 것은 모호하지 않다(첫 줄을 쓴다).
    same = [table[0], table[0]]
    assert isinstance(convert_unit(ONE, "a", "b", same, "test"), Ok)


# ── 연료 연소 ─────────────────────────────────────────────────────────


def test_combustion_carries_energy_gases_total_and_evidence() -> None:
    result = ok(calculate_row(row(), tables, ETS))
    assert result.scope == 1
    assert result.energy is not None
    assert (result.energy.value, result.energy.unit) == ("35200", "MJ")
    assert [(g.gas, g.mass, g.mass_unit, g.gwp, g.co2e) for g in result.gases] == [
        ("CO2", "2.5508736", "t", "1", "2.5508736"),
        ("CH4", "0.0001056", "t", "21", "0.0022176"),
        ("N2O", "0.00002112", "t", "310", "0.0065472"),
    ]
    assert result.co2e == "2.5596384"
    assert result.unit == "tCO2eq"

    evidence = result.evidence
    assert evidence.factor.id == DIESEL_ID
    assert evidence.factor.version == "환경부고시 제2025-64호"
    assert evidence.factor.source.kind == "cited"
    assert evidence.gwp_set.source.kind == "cited"
    assert evidence.calorific_basis == "net"
    assert evidence.oxidation_factor == "0.99"
    assert evidence.sector == MANUFACTURING
    assert evidence.parameter_tiers == ParameterTiers(calorific=2, co2=2, non_co2=1, oxidation=2)
    assert evidence.facility_use is None
    assert "에너지량" in [s.label for s in evidence.steps]
    assert evidence.steps[-1] == Step(
        label="합산",
        formula="2.5508736 (CO2) + 0.0022176 (CH4) + 0.0065472 (N2O)",
        result="2.5596384",
        unit="tCO2eq",
    )
    # 환산 단계에는 쓴 환산 계수와 그 출처가 붙는다.
    conversions = [s.conversion for s in evidence.steps if s.conversion is not None]
    assert len(conversions) > 0
    assert all(conversion.source.kind == "definition" for conversion in conversions)


def test_step_labels_and_formulas_are_the_same_sentences_as_the_ts_engine() -> None:
    """단계의 한국어 문장을 글자까지 본다(TS 의 테스트는 「에너지량」과 마지막 「합산」만 봤다. 전부는 골든이 잰다)."""
    steps = ok(calculate_row(row(), tables, ETS)).evidence.steps
    assert [(s.label, s.formula, s.result, s.unit) for s in steps] == [
        ("에너지량", "1000 L × 35.2 MJ/L (순발열량)", "35200", "MJ"),
        ("단위 환산 (CO2 배출계수의 에너지 단위)", "35200 MJ × 0.000001 TJ/MJ", "0.0352", "TJ"),
        ("CO2 배출량", "0.0352 TJ × 73200 kgCO2/TJ × 산화계수 0.99", "2550.8736", "kgCO2"),
        ("단위 환산 (CO2 질량)", "2550.8736 kg × 0.001 t/kg", "2.5508736", "t"),
        ("CO2 환산", "2.5508736 tCO2 × GWP 1 (kr-ets-decree-annex2)", "2.5508736", "tCO2eq"),
        ("단위 환산 (CH4 배출계수의 에너지 단위)", "35200 MJ × 0.000001 TJ/MJ", "0.0352", "TJ"),
        ("CH4 배출량", "0.0352 TJ × 3 kgCH4/TJ", "0.1056", "kgCH4"),
        ("단위 환산 (CH4 질량)", "0.1056 kg × 0.001 t/kg", "0.0001056", "t"),
        ("CH4 환산", "0.0001056 tCH4 × GWP 21 (kr-ets-decree-annex2)", "0.0022176", "tCO2eq"),
        ("단위 환산 (N2O 배출계수의 에너지 단위)", "35200 MJ × 0.000001 TJ/MJ", "0.0352", "TJ"),
        ("N2O 배출량", "0.0352 TJ × 0.6 kgN2O/TJ", "0.02112", "kgN2O"),
        ("단위 환산 (N2O 질량)", "0.02112 kg × 0.001 t/kg", "0.00002112", "t"),
        ("N2O 환산", "0.00002112 tN2O × GWP 310 (kr-ets-decree-annex2)", "0.0065472", "tCO2eq"),
        ("합산", "2.5508736 (CO2) + 0.0022176 (CH4) + 0.0065472 (N2O)", "2.5596384", "tCO2eq"),
    ]
    # 사용량이 이미 에너지 단위면 발열량을 곱하지 않는다(검산 사례 H12 와 같은 입력).
    as_energy = ok(calculate_row(row(amount="35.2", unit="GJ"), tables, ETS)).evidence.steps
    assert [(s.label, s.formula) for s in as_energy[:2]] == [
        ("단위 환산 (사용량(에너지) → 발열량 에너지 단위)", "35.2 GJ × 1000 MJ/GJ"),
        ("에너지량", "사용량이 에너지 단위(GJ)로 주어져 발열량을 곱하지 않았다"),
    ]


def test_oxidation_factor_multiplies_co2_only() -> None:
    with_ox = ok(calculate_row(row(), tables, ETS))
    no_ox_tables = dataclasses.replace(
        tables,
        factors=tuple(
            dataclasses.replace(f, oxidation_factor=None) if f.id == DIESEL_ID and f.kind == "combustion" else f
            for f in tables.factors
        ),
    )
    without_ox = ok(calculate_row(row(), no_ox_tables, ETS))
    assert without_ox.gases[0].mass == "2.57664"
    assert with_ox.gases[0].mass == "2.5508736"
    assert without_ox.gases[1] == with_ox.gases[1]
    assert without_ox.gases[2] == with_ox.gases[2]
    assert without_ox.evidence.oxidation_factor is None


def test_stationary_and_mobile_combustion_of_one_fuel_use_different_factors() -> None:
    options = CalcOptions(gwp_set_id=SYNTHETIC_GWP)
    stationary = ok(
        calculate_row(
            bare(fuel="synthetic-fuel-a", amount="800", unit="L", source_type="stationary_combustion"), tables, options
        )
    )
    mobile = ok(
        calculate_row(
            bare(fuel="synthetic-fuel-a", amount="800", unit="L", source_type="mobile_combustion"), tables, options
        )
    )
    assert stationary.evidence.factor.id == "synthetic:fuel-a:stationary"
    assert mobile.evidence.factor.id == "synthetic:fuel-a:mobile"
    assert mobile.co2e != stationary.co2e
    assert (stationary.scope, mobile.scope) == (1, 1)


def test_required_calorific_basis_rejects_the_other_kind() -> None:
    # 경유 총발열량 37.8 MJ/L: 배출권거래제 배출량 보고 및 인증 지침(환경부고시 제2025-64호) 별표 12,
    # https://www.law.go.kr/LSW/flDownload.do?flSeq=151024615&bylClsCd=200201
    # (2026-10-01 확인. esg-lab 의 테스트에서 옮긴 값이다.)
    # 배출량 산정에는 순발열량을 쓴다(같은 표 비고 2).
    diesel = diesel_factor(tables)
    gross = dataclasses.replace(
        diesel,
        id="diesel-gross",
        variant="gross",
        calorific=dataclasses.replace(diesel.calorific, value="37.8", basis="gross"),
    )
    gross_tables = dataclasses.replace(tables, factors=(gross,))
    gross_row = row(variant="gross")
    net_only = CalcOptions(gwp_set_id=ETS_GWP, require_calorific_basis="net")
    assert failure_of(calculate_row(gross_row, gross_tables, net_only)) == CalorificBasisMismatch(
        factor_id="diesel-gross", required="net", actual="gross"
    )
    assert ok(calculate_row(gross_row, gross_tables, ETS)).evidence.calorific_basis == "gross"
    assert ok(calculate_row(row(), tables, net_only)).co2e == "2.5596384"


# ── 구매 전력·열 ──────────────────────────────────────────────────────


def test_electricity_is_amount_times_per_gas_factors_and_scope_2() -> None:
    sample_only = dataclasses.replace(
        tables, factors=tuple(f for f in tables.factors if f.id.startswith("kr-ets-sample:"))
    )
    result = ok(calculate_row(bare(source_type="purchased_electricity", amount="1", unit="MWh"), sample_only, ETS))
    assert result.scope == 2
    assert result.energy is None
    # 0.4567 + 0.0036×21/1000 + 0.0085×310/1000
    assert result.co2e == "0.4594106"


def test_pre_aggregated_co2e_factor_is_not_multiplied_by_gwp() -> None:
    heat = bare(source_type="purchased_heat", amount="15.5", unit="GJ")
    a = ok(calculate_row(heat, tables, CalcOptions(gwp_set_id=SYNTHETIC_GWP)))
    b = ok(calculate_row(heat, tables, CalcOptions(gwp_set_id=AR5_GWP)))
    assert [(g.gas, g.mass, g.mass_unit, g.gwp, g.co2e) for g in a.gases] == [
        ("CO2e", "0.88023725", "t", None, "0.88023725")
    ]
    assert b.co2e == a.co2e
    # GWP 를 곱한 단계가 없다.
    assert [s.label for s in a.evidence.steps] == [
        "단위 환산 (사용량 → 배출계수 기준 단위)",
        "CO2e 배출량",
        "단위 환산 (CO2e 질량)",
        "합산",
    ]


# ── GWP 세트 전환 ─────────────────────────────────────────────────────


def test_switching_the_gwp_set_changes_only_ch4_and_n2o() -> None:
    ets = ok(calculate_row(row(), tables, ETS))
    ar5 = ok(calculate_row(row(), tables, CalcOptions(gwp_set_id=AR5_GWP)))
    assert [g.mass for g in ets.gases] == [g.mass for g in ar5.gases]
    assert [g.gwp for g in ets.gases] == ["1", "21", "310"]
    assert [g.gwp for g in ar5.gases] == ["1", "28", "265"]
    assert ets.co2e == "2.5596384"
    assert ar5.co2e == "2.5594272"
    assert ar5.evidence.gwp_set.id == AR5_GWP


# ── 실패 갈래 ─────────────────────────────────────────────────────────


def test_a_row_without_a_factor_is_factor_not_found_not_zero() -> None:
    result = calculate_row(row(fuel="no-such-fuel"), tables, ETS)
    assert isinstance(result, RowFailed)
    assert not hasattr(result, "co2e")
    assert result.failure == FactorNotFound(
        criteria={
            "sourceType": "stationary_combustion",
            "fuel": "no-such-fuel",
            "sector": MANUFACTURING,
            "parameterTiers": "calorific=2,co2=2,nonCo2=1,oxidation=2",
        }
    )


def test_a_similar_factor_never_stands_in_for_a_different_distinction() -> None:
    assert failure_of(calculate_row(row(sector=COMMERCIAL), tables, ETS)).kind == "factor_not_found"
    # A 그룹 최소 조합(발열량만 Tier 2)을 달라고 하면 Tier 2 조합의 계수로 대신하지 않는다.
    lower = dataclasses.replace(TIER2, co2=1, oxidation=1)
    assert failure_of(calculate_row(row(parameter_tiers=lower), tables, ETS)) == FactorNotFound(
        criteria={
            "sourceType": "stationary_combustion",
            "fuel": "diesel",
            "sector": MANUFACTURING,
            "parameterTiers": "calorific=2,co2=1,nonCo2=1,oxidation=1",
        }
    )
    no_oxidation = failure_of(
        calculate_row(row(parameter_tiers=dataclasses.replace(TIER2, oxidation=None)), tables, ETS)
    )
    assert isinstance(no_oxidation, FactorNotFound)
    assert no_oxidation.criteria["parameterTiers"] == "calorific=2,co2=2,nonCo2=1,oxidation=null"  # None 이 아니다
    assert failure_of(calculate_row(row(facility_use="other"), tables, ETS)).kind == "factor_not_found"
    assert failure_of(calculate_row(row(variant="synthetic-구분"), tables, ETS)).kind == "factor_not_found"
    assert failure_of(calculate_row(row(factor_year=2025), tables, ETS)).kind == "factor_not_found"
    assert failure_of(calculate_row(row(source_type="mobile_combustion"), tables, ETS)).kind == "factor_not_found"


def test_unknown_factor_id_is_factor_not_found() -> None:
    assert failure_of(calculate_row(row(factor_id="nope"), tables, ETS)) == FactorNotFound(
        criteria={"factorId": "nope"}
    )


def test_two_matching_factors_are_not_chosen_between() -> None:
    diesel = diesel_factor(tables)
    doubled = dataclasses.replace(tables, factors=(*tables.factors, dataclasses.replace(diesel, id="dup")))
    failure = failure_of(calculate_row(row(), doubled, ETS))
    assert isinstance(failure, FactorAmbiguous)
    assert failure.candidate_ids == (DIESEL_ID, "dup")
    # id 로 골라도 같은 id 가 둘이면 고르지 않는다.
    same_id = dataclasses.replace(tables, factors=(*tables.factors, diesel))
    assert failure_of(calculate_row(row(factor_id=DIESEL_ID), same_id, ETS)) == FactorAmbiguous(
        criteria={"factorId": DIESEL_ID}, candidate_ids=(DIESEL_ID, DIESEL_ID)
    )


def test_a_combustion_row_pointing_at_an_electricity_factor_is_kind_mismatch() -> None:
    failure = failure_of(calculate_row(row(factor_id=ELECTRICITY_ID), tables, ETS))
    assert isinstance(failure, FactorKindMismatch)
    assert (failure.factor_id, failure.expected, failure.actual) == (ELECTRICITY_ID, "combustion", "purchased_energy")


def test_a_factor_missing_one_gas_fails_instead_of_counting_it_as_zero() -> None:
    diesel = diesel_factor(tables)
    without_ch4 = dataclasses.replace(
        diesel, emission_factors=tuple(e for e in diesel.emission_factors if e.gas != "CH4")
    )
    partial = dataclasses.replace(tables, factors=(without_ch4,))
    assert failure_of(calculate_row(row(), partial, ETS)) == FactorIncomplete(
        factor_id=DIESEL_ID, reason="CH4 배출계수가 없다"
    )
    twice = dataclasses.replace(diesel, emission_factors=(*diesel.emission_factors, diesel.emission_factors[1]))
    assert failure_of(calculate_row(row(), dataclasses.replace(tables, factors=(twice,)), ETS)) == FactorIncomplete(
        factor_id=DIESEL_ID, reason="CH4 배출계수가 2개다"
    )


def test_an_electricity_factor_with_co2_only_fails() -> None:
    co2_only = PurchasedEnergyFactor(
        id="co2-only",
        version="synthetic-1",
        source=SYNTHETIC,
        energy_type="electricity",
        per_unit="MWh",
        emission_factors=(PurchasedEmissionFactor(gas="CO2", value="0.5", mass_unit="t"),),
    )
    partial = dataclasses.replace(tables, factors=(co2_only,))
    result = calculate_row(bare(source_type="purchased_electricity", amount="1000", unit="MWh"), partial, ETS)
    assert failure_of(result) == FactorIncomplete(
        factor_id="co2-only", reason="배출계수는 CO2e 하나이거나 CO2·CH4·N2O 셋이어야 한다 (받은 것: CO2)"
    )
    empty = dataclasses.replace(tables, factors=(dataclasses.replace(co2_only, emission_factors=()),))
    result = calculate_row(bare(source_type="purchased_electricity", amount="1000", unit="MWh"), empty, ETS)
    assert failure_of(result) == FactorIncomplete(
        factor_id="co2-only", reason="배출계수는 CO2e 하나이거나 CO2·CH4·N2O 셋이어야 한다 (받은 것: 없음)"
    )


def test_an_unconvertible_unit_is_unit_conversion_not_found() -> None:
    assert failure_of(calculate_row(row(unit="kg"), tables, ETS)) == UnitConversionNotFound(
        from_unit="kg", to_unit="L", context="사용량 → 발열량 기준 단위"
    )
    failure = failure_of(calculate_row(row(fuel="city-gas-lng", sector=COMMERCIAL, unit="m3"), tables, ETS))
    assert isinstance(failure, UnitConversionNotFound)
    assert (failure.from_unit, failure.to_unit) == ("m3", "Nm3")


def test_an_ambiguous_unit_conversion_fails_the_row() -> None:
    """파이썬으로 옮기며 더함: unit_conversion_ambiguous 가 행 계산까지 올라온다(TS 는 convertUnit 만 봤다)."""
    doubled = dataclasses.replace(
        tables,
        unit_conversions=(
            *tables.unit_conversions,
            UnitConversion(from_unit="MJ", to_unit="TJ", factor="0.001", source=SYNTHETIC),
        ),
    )
    assert failure_of(calculate_row(row(), doubled, ETS)) == UnitConversionAmbiguous(
        from_unit="MJ", to_unit="TJ", factors=("0.000001", "0.001")
    )


def test_an_unknown_gwp_set_is_gwp_set_not_found() -> None:
    """기본 세트로 대신하지 않는다."""
    assert failure_of(calculate_row(row(), tables, CalcOptions(gwp_set_id="AR4"))) == GwpSetNotFound(gwp_set_id="AR4")


def test_two_gwp_sets_with_one_id_are_not_chosen_between() -> None:
    """파이썬으로 옮기며 더함: gwp_set_ambiguous 는 TS 에 테스트가 없었다."""
    doubled = dataclasses.replace(tables, gwp_sets=(*tables.gwp_sets, tables.gwp_sets[0]))
    assert failure_of(calculate_row(row(), doubled, ETS)) == GwpSetAmbiguous(gwp_set_id=ETS_GWP)


def test_a_gwp_set_missing_a_gas_is_gwp_value_missing() -> None:
    partial = dataclasses.replace(
        tables, gwp_sets=(GwpSet(id="partial", label="p", source=SYNTHETIC, values={"CO2": "1", "CH4": "20"}),)
    )
    assert failure_of(calculate_row(row(), partial, CalcOptions(gwp_set_id="partial"))) == GwpValueMissing(
        gwp_set_id="partial", gas="N2O"
    )


@pytest.mark.parametrize(
    ("amount", "reason"),
    [
        ("abc", "십진 문자열이 아니다"),
        ("1e3", "십진 문자열이 아니다"),
        ("", "십진 문자열이 아니다"),
        ("-1", "음수 사용량"),
    ],
)
def test_bad_amounts_are_invalid_activity(amount: str, reason: str) -> None:
    assert failure_of(calculate_row(row(amount=amount), tables, ETS)) == InvalidActivity(
        field="amount", value=amount, reason=reason
    )


def test_a_numeric_amount_is_rejected() -> None:
    """문자열만 받는다. JSON 의 수 1000 은 사용량이 아니다."""
    raw: dict[str, Any] = {
        "id": "t1",
        "orgUnit": "synthetic-site",
        "period": "2025",
        "sourceType": "stationary_combustion",
        "fuel": "diesel",
        "amount": 1000,
        "unit": "L",
    }
    result = calculate_raw_row(raw, tables, ETS)
    assert failure_of(result) == InvalidActivity(field="amount", value="1000", reason="십진 문자열이 아니다")
    assert isinstance(result, RowFailed)
    assert (result.scope, result.source_type) == (1, "stationary_combustion")


def test_a_non_decimal_table_value_is_invalid_reference_value() -> None:
    diesel = diesel_factor(tables)
    broken = dataclasses.replace(
        tables, factors=(dataclasses.replace(diesel, calorific=dataclasses.replace(diesel.calorific, value="35,2")),)
    )
    assert failure_of(calculate_row(row(), broken, ETS)) == InvalidReferenceValue(
        where=f"factors[{DIESEL_ID}].calorific.value", value="35,2"
    )


MISSING_KEY: Any = object()


@pytest.mark.parametrize("source_type", ["scope3_travel", MISSING_KEY, "", "toString", "__class__", None])
def test_an_unknown_source_type_is_never_calculated_as_another(source_type: Any) -> None:
    raw: dict[str, Any] = {"id": "t1", "orgUnit": "synthetic-site", "period": "2025", "amount": "15.5", "unit": "GJ"}
    if source_type is not MISSING_KEY:
        raw["sourceType"] = source_type
    shown = "" if source_type is MISSING_KEY or source_type is None else source_type
    assert calculate_raw_row(raw, tables, CalcOptions(gwp_set_id=SYNTHETIC_GWP)) == RowFailed(
        row_id="t1",
        org_unit="synthetic-site",
        period="2025",
        scope=None,
        source_type=None,
        failure=InvalidActivity(
            field="sourceType", value=shown, reason="알 수 없는 배출원 유형이거나 행이 객체가 아니다"
        ),
    )


def test_a_source_type_written_as_an_array_is_not_coerced_to_a_string() -> None:
    raw: dict[str, Any] = {
        "id": "t1",
        "orgUnit": "synthetic-site",
        "period": "2025",
        "sourceType": ["purchased_electricity"],
        "amount": "1",
        "unit": "TJ",
    }
    failure = failure_of(calculate_raw_row(raw, tables, CalcOptions(gwp_set_id=SYNTHETIC_GWP)))
    assert failure == InvalidActivity(
        field="sourceType", value="purchased_electricity", reason="알 수 없는 배출원 유형이거나 행이 객체가 아니다"
    )


@pytest.mark.parametrize("raw", [None, "row", [], 42, True, 1.5])
def test_a_row_that_is_not_an_object_is_invalid_activity_not_an_exception(raw: Any) -> None:
    result = calculate_raw_row(raw, tables, ETS)
    assert isinstance(result, RowFailed)
    assert (result.row_id, result.org_unit, result.period, result.scope) == ("", "", "", None)
    assert result.failure == InvalidActivity(
        field="sourceType", value="", reason="알 수 없는 배출원 유형이거나 행이 객체가 아니다"
    )


def test_a_negative_table_value_is_invalid_reference_value() -> None:
    diesel = diesel_factor(tables)
    broken = dataclasses.replace(
        tables, factors=(dataclasses.replace(diesel, calorific=dataclasses.replace(diesel.calorific, value="-35.2")),)
    )
    failure = failure_of(calculate_row(row(), broken, ETS))
    assert isinstance(failure, InvalidReferenceValue)
    assert failure.value == "-35.2"


def test_a_failed_row_keeps_its_org_unit_period_scope_and_source_type() -> None:
    result = calculate_row(row(id="x9", org_unit="site-9", period="2025-03", fuel="no-such-fuel"), tables, ETS)
    assert isinstance(result, RowFailed)
    assert (result.row_id, result.org_unit, result.period, result.scope, result.source_type, result.status) == (
        "x9",
        "site-9",
        "2025-03",
        1,
        "stationary_combustion",
        "failed",
    )


# ── 파이썬으로 옮기며 더한 것 ─────────────────────────────────────────


def test_a_combustion_row_with_neither_fuel_nor_factor_id_is_invalid_activity() -> None:
    """TS 에 테스트가 없던 갈래."""
    expected = InvalidActivity(field="fuel", value="", reason="연소 행에 연료도 factorId 도 없다")
    assert failure_of(calculate_row(bare(source_type="stationary_combustion", amount="1", unit="L"), tables, ETS)) == (
        expected
    )
    assert failure_of(calculate_row(row(fuel=""), tables, ETS)) == expected


def test_an_amount_longer_than_64_characters_is_a_failed_row() -> None:
    """바깥 입력의 길이 상한: 65자 사용량은 십진 문자열로 받지 않는다(실패 갈래). 64자는 받는다."""
    too_long = "1" * 65
    assert failure_of(calculate_row(row(amount=too_long), tables, ETS)) == InvalidActivity(
        field="amount", value=too_long, reason="십진 문자열이 아니다"
    )
    at_limit = ok(calculate_row(row(amount="1" * 64), tables, ETS))
    assert at_limit.co2e.startswith("2844042666666666666666666666666666666666666666666666666666666")


def test_a_table_value_longer_than_64_characters_is_invalid_reference_value() -> None:
    diesel = diesel_factor(tables)
    long_value = "0." + "1" * 63
    broken = dataclasses.replace(
        tables,
        factors=(dataclasses.replace(diesel, calorific=dataclasses.replace(diesel.calorific, value=long_value)),),
    )
    assert failure_of(calculate_row(row(), broken, ETS)) == InvalidReferenceValue(
        where=f"factors[{DIESEL_ID}].calorific.value", value=long_value
    )
