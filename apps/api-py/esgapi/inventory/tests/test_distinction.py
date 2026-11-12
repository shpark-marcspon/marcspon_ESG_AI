"""계수의 구분(부문, 매개변수별 산정등급, 시설의 쓰임, 그 밖의 구분)으로 고르기와 그 칸의 표 검사.

esg-lab `ts/ghg-calc/test/distinction.test.ts` 11건을 옮겼다. 순수 층.
"""

import dataclasses
from typing import Any

from esgapi.inventory.engines.scope12.engine_1.calc import calculate_row
from esgapi.inventory.engines.scope12.engine_1.provenance import Synthetic
from esgapi.inventory.engines.scope12.engine_1.tables import TablesInvalid, validate_tables
from esgapi.inventory.engines.scope12.engine_1.types import CalcOptions, FactorAmbiguous, ParameterTiers
from esgapi.inventory.tests.support import (
    ETS_GWP,
    MANUFACTURING,
    TIER2,
    bare,
    diesel_factor,
    diesel_raw,
    failure_of,
    load_tables,
    ok,
    raw_tables,
    row,
)

tables = load_tables()
ETS = CalcOptions(gwp_set_id=ETS_GWP)
diesel = diesel_factor(tables)
LOWER = ParameterTiers(calorific=2, co2=1, non_co2=1, oxidation=1)
# synthetic: 같은 연료·부문에 산정등급 조합만 다른 계수 (CO2 계수와 산화계수 값은 가상).
lower_tier = dataclasses.replace(
    diesel,
    id="synthetic:diesel:lower-tier",
    source=Synthetic(note="산정등급 조합만 다른 가상 계수"),
    parameter_tiers=LOWER,
    emission_factors=tuple(
        dataclasses.replace(e, value="70000") if e.gas == "CO2" else e for e in diesel.emission_factors
    ),
    oxidation_factor="1",
)
both = dataclasses.replace(tables, factors=(*tables.factors, lower_tier))

# ── 계수의 구분으로 고르기 ────────────────────────────────────────────


def test_same_fuel_and_sector_with_different_tiers_are_different_factors() -> None:
    tier2 = ok(calculate_row(row(), both, ETS))
    lower = ok(calculate_row(row(parameter_tiers=LOWER), both, ETS))
    assert tier2.evidence.factor.id == diesel.id
    assert lower.evidence.factor.id == "synthetic:diesel:lower-tier"
    assert tier2.evidence.parameter_tiers == TIER2
    assert lower.evidence.parameter_tiers == LOWER
    assert lower.co2e != tier2.co2e


def test_a_row_without_tiers_matches_only_a_factor_without_tiers() -> None:
    """둘 중 하나를 고르지 않는다."""
    assert failure_of(calculate_row(row(parameter_tiers=None), both, ETS)).kind == "factor_not_found"


def test_two_factors_equal_down_to_the_distinction_are_ambiguous() -> None:
    twice = dataclasses.replace(
        tables, factors=(*tables.factors, dataclasses.replace(diesel, id="synthetic:diesel:copy"))
    )
    failure = failure_of(calculate_row(row(), twice, ETS))
    assert isinstance(failure, FactorAmbiguous)
    assert failure.candidate_ids == (diesel.id, "synthetic:diesel:copy")


def test_facility_use_and_variant_must_match_exactly() -> None:
    power = dataclasses.replace(
        tables,
        factors=(
            dataclasses.replace(
                diesel, id="synthetic:diesel:power", facility_use="power_generation", variant="synthetic-구분"
            ),
        ),
    )
    assert failure_of(calculate_row(row(), power, ETS)).kind == "factor_not_found"
    mismatch = row(facility_use="other", variant="synthetic-구분")
    assert failure_of(calculate_row(mismatch, power, ETS)).kind == "factor_not_found"
    assert failure_of(calculate_row(row(facility_use="power_generation"), power, ETS)).kind == "factor_not_found"
    found = ok(calculate_row(row(facility_use="power_generation", variant="synthetic-구분"), power, ETS))
    assert found.evidence.facility_use == "power_generation"


def test_choosing_by_factor_id_ignores_the_distinction_and_evidence_carries_the_factors() -> None:
    by_id = bare(source_type="stationary_combustion", factor_id="synthetic:diesel:lower-tier", amount="1000", unit="L")
    result = ok(calculate_row(by_id, both, ETS))
    assert result.evidence.sector == MANUFACTURING
    assert result.evidence.parameter_tiers == LOWER


def test_evidence_of_a_factor_without_distinction_is_none() -> None:
    """지어내지 않는다."""
    plain = bare(source_type="stationary_combustion", fuel="synthetic-fuel-b", amount="1", unit="t")
    evidence = ok(calculate_row(plain, tables, ETS)).evidence
    assert (evidence.sector, evidence.parameter_tiers, evidence.facility_use) == (None, None, None)


def test_purchased_energy_is_chosen_by_variant_and_year_only() -> None:
    """부문이나 산정등급을 적은 구매 전력·열 행에는 맞는 계수가 없다."""
    heat: dict[str, Any] = {"source_type": "purchased_heat", "amount": "1", "unit": "GJ"}
    found = ok(calculate_row(bare(**heat), tables, ETS))
    assert found.evidence.factor.id == "synthetic:heat"
    assert (found.evidence.sector, found.evidence.parameter_tiers) == (None, None)
    assert failure_of(calculate_row(bare(**heat, sector=MANUFACTURING), tables, ETS)).kind == "factor_not_found"
    assert failure_of(calculate_row(bare(**heat, parameter_tiers=TIER2), tables, ETS)).kind == "factor_not_found"
    assert failure_of(calculate_row(bare(**heat, facility_use="other"), tables, ETS)).kind == "factor_not_found"
    assert failure_of(calculate_row(bare(**heat, variant="synthetic-구분"), tables, ETS)).kind == "factor_not_found"


# ── 기준정보 표 검사: 구분 필드 ───────────────────────────────────────


def with_diesel(**patch: Any) -> dict[str, Any]:
    raw = raw_tables()
    raw["factors"] = [{**diesel_raw(raw), **patch}]
    return raw


def problems(raw: object) -> list[str]:
    result = validate_tables(raw)
    return [f"{p.where}: {p.problem}" for p in result.problems] if isinstance(result, TablesInvalid) else []


TIER2_RAW: dict[str, Any] = {"calorific": 2, "co2": 2, "nonCo2": 1, "oxidation": 2}


def test_valid_distinctions_pass() -> None:
    assert problems(with_diesel()) == []
    assert problems(with_diesel(facilityUse="other")) == []


def test_tiers_outside_1_to_4_or_missing_are_rejected() -> None:
    assert problems(with_diesel(parameterTiers={"calorific": 2, "co2": "2", "nonCo2": 1, "oxidation": 2})) == [
        'factors[0].parameterTiers.co2: 산정등급(1~4)이 아니다: "2"'
    ]
    assert problems(with_diesel(parameterTiers={"calorific": 5, "co2": 2, "oxidation": 2})) == [
        "factors[0].parameterTiers.calorific: 산정등급(1~4)이 아니다: 5",
        "factors[0].parameterTiers.nonCo2: 산정등급(1~4)이 아니다: undefined",
    ]
    assert problems(with_diesel(parameterTiers="tier2")) == ["factors[0].parameterTiers: 객체가 아니다"]
    # 파이썬에서만 갈리는 자리: True == 1 이지만 등급 1 이 아니다. JS 의 `true === 1` 이 거짓인 것과 같다.
    assert problems(with_diesel(parameterTiers={**TIER2_RAW, "nonCo2": True})) == [
        "factors[0].parameterTiers.nonCo2: 산정등급(1~4)이 아니다: true"
    ]


def test_oxidation_factor_and_its_tier_come_together_or_not_at_all() -> None:
    assert problems(with_diesel(parameterTiers={**TIER2_RAW, "oxidation": None})) == [
        "factors[0].parameterTiers.oxidation: 산화계수가 있는데 그 산정등급(1~4)이 없다: null"
    ]
    raw = raw_tables()
    no_oxidation = {k: v for k, v in diesel_raw(raw).items() if k != "oxidationFactor"}
    assert problems({**raw, "factors": [no_oxidation]}) == [
        "factors[0].parameterTiers.oxidation: 산화계수가 없으면 그 산정등급은 null 이어야 한다"
    ]
    fixed = {**no_oxidation, "parameterTiers": {**TIER2_RAW, "oxidation": None}}
    assert problems({**raw, "factors": [fixed]}) == []


def test_sector_and_facility_use_formats() -> None:
    assert problems(with_diesel(sector="")) == ["factors[0]: sector 가 빈 문자열이거나 문자열이 아니다"]
    assert problems(with_diesel(facilityUse="발전")) == ["factors[0]: facilityUse 가 power_generation/other 가 아니다"]
