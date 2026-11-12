"""검산 사례 H01~H14 (오차 0). esg-lab `ts/ghg-calc/test/handcalc.test.ts` 를 옮겼다. 순수 층.

기대값은 엔진과 따로 계산한 것이다(tests/data/handcalc-cases.json. esg-lab 에서 옮긴 사본, 출처는 tests/data/README.md).
엔진의 결과와 문자열까지 같아야 한다.
"""

from typing import Any

import pytest

from esgapi.inventory.engines.scope12.engine_1.calc import calculate_raw_row
from esgapi.inventory.engines.scope12.engine_1.serialize import factor_to_dict
from esgapi.inventory.engines.scope12.engine_1.types import CalcOptions, RowOk
from esgapi.inventory.tests.support import hand_cases, load_tables

tables = load_tables()
CASES = hand_cases()


def test_there_are_fourteen_cases() -> None:
    assert [case["id"] for case in CASES] == [f"H{n:02d}" for n in range(1, 15)]


def is_subset(expected: Any, actual: Any) -> bool:
    """vitest 의 toMatchObject: 객체는 적힌 키만, 배열은 길이와 원소마다, 나머지는 같음."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and is_subset(v, actual[k]) for k, v in expected.items())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)  # pyright: ignore[reportUnknownArgumentType]
            and all(is_subset(e, a) for e, a in zip(expected, actual, strict=True))  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        )
    return bool(expected == actual)


def test_factors_and_gwp_copied_into_the_cases_equal_the_reference_tables() -> None:
    for case in CASES:
        factor = next(f for f in tables.factors if f.id == case["factor"]["id"])
        assert is_subset(case["factor"], factor_to_dict(factor)), case["id"]
        gwp_set = next(s for s in tables.gwp_sets if s.id == case["gwpSetId"])
        assert dict(gwp_set.values) == case["gwp"], case["id"]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_hand_calculated_case(case: dict[str, Any]) -> None:
    result = calculate_raw_row(case["activity"], tables, CalcOptions(gwp_set_id=case["gwpSetId"]))
    assert isinstance(result, RowOk), f"계산 실패: {result}"
    expected = case["expected"]
    assert result.co2e == expected["co2e"]
    energy = None if result.energy is None else {"value": result.energy.value, "unit": result.energy.unit}
    assert energy == expected["energy"]
    assert result.evidence.factor.id == expected["factorId"]
    assert result.evidence.gwp_set.id == case["gwpSetId"]
    assert {g.gas: {"mass": g.mass, "co2e": g.co2e} for g in result.gases} == expected["gases"]


def test_the_expected_strings_named_in_the_work_order() -> None:
    """발주서 §3 이 이름으로 든 세 값. 사례 파일이 바뀌어 조용히 통과하는 일을 막는다."""
    by_id = {case["id"]: case["expected"]["co2e"] for case in CASES}
    assert (by_id["H01"], by_id["H04"], by_id["H14"]) == ("2.5596384", "26.8724539692981", "0.000002278125")
