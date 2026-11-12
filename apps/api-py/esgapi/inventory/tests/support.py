"""inventory 테스트가 같이 쓰는 준비물. esg-lab `ts/ghg-calc/test/fixtures.ts` 를 옮긴 것이다."""

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

from esgapi.inventory.data_loader import DATA_FILES, read_data
from esgapi.inventory.engines.scope12.engine_1.tables import TablesInvalid, merge_tables, validate_tables
from esgapi.inventory.engines.scope12.engine_1.types import (
    ActivityRow,
    CombustionFactor,
    Failure,
    ParameterTiers,
    ReferenceTables,
    RowFailed,
    RowOk,
    RowResult,
)

TEST_DATA = Path(__file__).resolve().parent / "data"
GOLDEN = TEST_DATA / "golden"


def read_test_data(name: str) -> Any:
    """시험 자료(tests/data) 하나를 JSON 그대로 읽는다."""
    return json.loads((TEST_DATA / name).read_text(encoding="utf-8"))


def synthetic_tables() -> dict[str, Any]:
    """가상 계수·가상 GWP 세트·환산표 (esg-lab 의 examples/factors.synthetic.json)."""
    tables: dict[str, Any] = read_test_data("examples/factors.synthetic.json")
    return tables


def package_parts() -> list[dict[str, object]]:
    """패키지에 실린 자료 셋(환산, GWP, 표본 계수)을 JSON 그대로."""
    return [read_data(name) for name in DATA_FILES]


def raw_tables() -> dict[str, Any]:
    """출처 있는 표(환산, GWP, 표본 계수)에 synthetic 계수와 synthetic GWP 세트를 얹은 표. 검사 전의 JSON 값이다.

    부를 때마다 새 사본이다(테스트가 고쳐 써도 된다).
    """
    synthetic = synthetic_tables()
    merged = merge_tables(*package_parts(), {"factors": synthetic["factors"], "gwpSets": synthetic["gwpSets"]})
    return copy.deepcopy(merged)


def validated(raw: object) -> ReferenceTables:
    result = validate_tables(raw)
    if isinstance(result, TablesInvalid):
        raise AssertionError(f"tables invalid: {result.problems}")
    return result.tables


def load_tables() -> ReferenceTables:
    return validated(raw_tables())


def hand_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = read_test_data("handcalc-cases.json")["cases"]
    return cases


ETS_GWP = "kr-ets-decree-annex2"
AR5_GWP = "ipcc-ar5-100y-kr-nid-2025"
SYNTHETIC_GWP = "synthetic-gwp"
DIESEL_ID = "kr-ets-sample:diesel:stationary:manufacturing:tier2"
ELECTRICITY_ID = "kr-ets-sample:electricity:2014-2016-avg"
# 표본 계수의 조합: 발열량·CO2 계수·산화계수 Tier 2, CH4·N2O 는 Tier 1 (지침에 Tier 1 뿐이다).
TIER2 = ParameterTiers(calorific=2, co2=2, non_co2=1, oxidation=2)
MANUFACTURING = "manufacturing_construction"
COMMERCIAL = "commercial_public"


def diesel_factor(tables: ReferenceTables) -> CombustionFactor:
    factor = next((f for f in tables.factors if f.id == DIESEL_ID), None)
    if not isinstance(factor, CombustionFactor):
        raise AssertionError("diesel fixture missing")
    return factor


def diesel_raw(raw: dict[str, Any]) -> dict[str, Any]:
    factor: dict[str, Any] = next(f for f in raw["factors"] if f["id"] == DIESEL_ID)
    return factor


def bare(**fields: Any) -> ActivityRow:
    """연료·구분이 없는 맨 행. 구매 전력·열이나 다른 연료에 쓴다."""
    merged: dict[str, Any] = {"id": "t1", "org_unit": "synthetic-site", "period": "2025", **fields}
    return ActivityRow(**merged)


_DIESEL_ROW = ActivityRow(
    id="t1",
    org_unit="synthetic-site",
    period="2025",
    source_type="stationary_combustion",
    fuel="diesel",
    sector=MANUFACTURING,
    parameter_tiers=TIER2,
    amount="1000",
    unit="L",
)


def row(**overrides: Any) -> ActivityRow:
    """경유 고정연소 1000 L (제조업·건설업, Tier 2 조합). 필요한 필드만 덮어쓴다."""
    return dataclasses.replace(_DIESEL_ROW, **overrides)


def ok(result: RowResult) -> RowOk:
    if not isinstance(result, RowOk):
        raise AssertionError(f"계산 실패: {result.failure}")
    return result


def failure_of(result: RowResult) -> Failure:
    if not isinstance(result, RowFailed):
        raise AssertionError(f"실패해야 하는데 성공: {result.co2e}")
    return result.failure
