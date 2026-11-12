"""행 계산의 빈틈 둘(밴드 MUT1). 변이 시험(MUT0)이 살아남은 변이로 찾은 자리를 지킨다. 순수 층.

옛 평평한 파일 `esgapi/inventory/tests/test_calc.py` 는 그대로 두고 여기에 더한다.
"""

import dataclasses

import pytest

from esgapi.inventory.engines.scope12.engine_1.calc import calculate_row
from esgapi.inventory.engines.scope12.engine_1.provenance import Synthetic
from esgapi.inventory.engines.scope12.engine_1.types import (
    CalcOptions,
    FactorIncomplete,
    PurchasedEmissionFactor,
    PurchasedEnergyFactor,
    UnitConversion,
    UnitConversionAmbiguous,
)
from esgapi.inventory.tests.support import ETS_GWP, bare, diesel_factor, failure_of, load_tables, row

tables = load_tables()
ETS = CalcOptions(gwp_set_id=ETS_GWP)
SYNTHETIC = Synthetic(note="t")
GAS_VALUES = {"CO2": "0.4567", "CH4": "0.0000036", "N2O": "0.0000085", "CO2e": "0.46"}


def _electricity(gases: tuple[str, ...]) -> PurchasedEnergyFactor:
    return PurchasedEnergyFactor(
        id="gases",
        version="synthetic-1",
        source=SYNTHETIC,
        energy_type="electricity",
        per_unit="MWh",
        emission_factors=tuple(PurchasedEmissionFactor(gas=g, value=GAS_VALUES[g], mass_unit="t") for g in gases),
    )


# 기준정보 표 검사(`tables.validate_tables`)는 구매 계수의 기체 구성을 막지 않는다 — 막는 곳은 계산의 이 검사 하나다.
@pytest.mark.parametrize(
    ("gases", "received"),
    [
        (("CO2", "CH4", "N2O", "CO2e"), "CO2, CH4, N2O, CO2e"),  # 기체마다 하나지만 넷: CO2e 를 한 번 더 더하면 안 된다
        (("CO2", "CO2", "CH4"), "CO2, CO2, CH4"),  # 셋이지만 N2O 가 없고 CO2 가 둘
    ],
)
def test_a_purchased_factor_must_list_exactly_co2_ch4_n2o_or_co2e_alone(gases: tuple[str, ...], received: str) -> None:
    only = dataclasses.replace(tables, factors=(_electricity(gases),))
    result = calculate_row(bare(source_type="purchased_electricity", amount="1000", unit="MWh"), only, ETS)
    assert failure_of(result) == FactorIncomplete(
        factor_id="gases", reason=f"배출계수는 CO2e 하나이거나 CO2·CH4·N2O 셋이어야 한다 (받은 것: {received})"
    )


def test_an_ambiguous_usage_to_energy_conversion_is_reported_as_ambiguous_not_missing() -> None:
    # 사용량 단위 X → 발열량 기준 단위(L) 환산은 없고, X → 에너지 단위 환산은 계수가 둘(모호)이다.
    # 두 번째 길의 실패가 「없음」이 아니므로 첫 길의 not_found 가 아니라 그 모호함을 돌려줘야 한다.
    energy_unit = diesel_factor(tables).calorific.energy_unit
    source = tables.unit_conversions[0].source
    doubled = (
        UnitConversion(from_unit="X", to_unit=energy_unit, factor="1", source=source),
        UnitConversion(from_unit="X", to_unit=energy_unit, factor="2", source=source),
    )
    with_x = dataclasses.replace(tables, unit_conversions=(*tables.unit_conversions, *doubled))
    assert failure_of(calculate_row(row(unit="X"), with_x, ETS)) == UnitConversionAmbiguous(
        from_unit="X", to_unit=energy_unit, factors=("1", "2")
    )
