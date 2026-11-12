"""TS 조립기가 낸 답과 글자까지 같은가. 순수 층.

golden/ 의 `*.expected.json` 은 esg-lab(HEAD f1b2c77)의 TS CLI 가 같은 조립 조건(`*.request.json`)으로 찍은 것이다
(만든 명령은 golden/README.md). 여기서 조립한 결과의 JSON 이 그것과 전체 일치해야 한다: 키 이름(camelCase),
값의 글자, 근거의 문장까지.

무효 조건: 골든은 그 HEAD 의 TS 와 그날의 계수 표로 만든 사진이다. TS 쪽이나 계수 표가 바뀌면 다시 찍어야 하고,
다시 찍지 않으면 이 테스트는 「옛 TS 와 같다」만 말한다.
"""

import json
from typing import Any

import pytest

from esgapi.reference.calc import assemble_combustion_factor, assemble_purchased_electricity_factor
from esgapi.reference.calc.types import result_to_json
from esgapi.reference.tests.helpers import ALL_RECORDS, GOLDEN, MAPPING, RECORDS

COMBUSTION = ["diesel-manufacturing-tier2", "lng-commercial-tier2"]
ELECTRICITY = ["electricity-table69", "electricity-gir2025-co2e"]

# 엔진(esg-lab `ts/ghg-calc/src/types.ts` 60행~)의 CombustionFactor·PurchasedEnergyFactor 가 갖는 키.
# `?` 가 붙은 것(없어도 되는 키)은 괄호 밖에 따로 적었다.
COMBUSTION_KEYS = {"kind", "id", "version", "source", "fuel", "combustionType", "calorific", "emissionFactors"}
COMBUSTION_OPTIONAL = {"sector", "parameterTiers", "facilityUse", "variant", "year", "oxidationFactor"}
PURCHASED_KEYS = {"kind", "id", "version", "source", "energyType", "perUnit", "emissionFactors"}
PURCHASED_OPTIONAL = {"variant", "year"}


def _load(name: str, part: str) -> Any:
    return json.loads((GOLDEN / f"{name}.{part}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", COMBUSTION)
def test_combustion_matches_the_ts_assembler(name: str) -> None:
    result = assemble_combustion_factor(_load(name, "request"), RECORDS, MAPPING)
    assert result_to_json(result) == _load(name, "expected")


@pytest.mark.parametrize("name", ELECTRICITY)
def test_electricity_matches_the_ts_assembler(name: str) -> None:
    result = assemble_purchased_electricity_factor(_load(name, "request"), ALL_RECORDS, MAPPING)
    assert result_to_json(result) == _load(name, "expected")


def test_factor_keys_are_the_engine_keys() -> None:
    """조립한 계수의 키가 엔진의 타입이 아는 키 안에 있고, 꼭 있어야 하는 키는 다 있다."""
    for name in COMBUSTION:
        keys = set(_load(name, "expected")["value"]["factor"])
        assert COMBUSTION_KEYS <= keys <= COMBUSTION_KEYS | COMBUSTION_OPTIONAL
    for name in ELECTRICITY:
        keys = set(_load(name, "expected")["value"]["factor"])
        assert PURCHASED_KEYS <= keys <= PURCHASED_KEYS | PURCHASED_OPTIONAL
    diesel = _load("diesel-manufacturing-tier2", "expected")["value"]["factor"]
    assert set(diesel["calorific"]) == {"value", "energyUnit", "perUnit", "basis"}
    assert set(diesel["emissionFactors"][0]) == {"gas", "value", "massUnit", "perEnergyUnit"}
    assert set(diesel["parameterTiers"]) == {"calorific", "co2", "nonCo2", "oxidation"}
    assert set(diesel["source"]) == {"kind", "title", "url", "checkedOn", "locator", "note"}
    table69 = _load("electricity-table69", "expected")["value"]["factor"]
    assert set(table69["emissionFactors"][0]) == {"gas", "value", "massUnit"}
