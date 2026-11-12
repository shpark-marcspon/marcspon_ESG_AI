"""행 검사: 바깥에서 온 행(JSON 값) → ActivityRow. 순수 층.

TS 는 배출원 유형과 사용량만 보고 나머지 칸은 타입을 믿었다. 여기서는 꼴이 틀린 칸을 invalid_activity 로 가른다
(TS 와 다른 자리. 「TS 와 다르게 한 것」에 적었다). 배출원 유형과 사용량의 갈래는 TS 와 같고 test_calc.py 가 잰다.
"""

from typing import Any

import pytest

from esgapi.inventory.engines.scope12.engine_1.activity import check_activity_row
from esgapi.inventory.engines.scope12.engine_1.types import ActivityRow, InvalidActivity, ParameterTiers, RowFailed

BASE: dict[str, Any] = {
    "id": "r1",
    "orgUnit": "site-1",
    "period": "2025-01",
    "sourceType": "stationary_combustion",
    "amount": "10",
    "unit": "L",
}


def test_a_full_row_becomes_a_dataclass() -> None:
    raw = {
        **BASE,
        "fuel": "diesel",
        "factorYear": 2025,
        "factorId": "f1",
        "sector": "manufacturing_construction",
        "parameterTiers": {"calorific": 2, "co2": 2, "nonCo2": 1, "oxidation": None},
        "facilityUse": "other",
        "variant": "v",
        "memo": "모르는 칸은 버린다",
    }
    assert check_activity_row(raw) == ActivityRow(
        id="r1",
        org_unit="site-1",
        period="2025-01",
        source_type="stationary_combustion",
        amount="10",
        unit="L",
        fuel="diesel",
        factor_year=2025,
        factor_id="f1",
        sector="manufacturing_construction",
        parameter_tiers=ParameterTiers(calorific=2, co2=2, non_co2=1, oxidation=None),
        facility_use="other",
        variant="v",
    )


def test_absent_optional_fields_are_none() -> None:
    row = check_activity_row(BASE)
    assert isinstance(row, ActivityRow)
    assert (row.fuel, row.factor_year, row.factor_id, row.sector, row.parameter_tiers, row.facility_use) == (
        None,
        None,
        None,
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    ("patch", "field", "value", "reason"),
    [
        ({"id": 5}, "id", "5", "문자열이 아니다"),
        ({"orgUnit": None}, "orgUnit", "null", "문자열이 아니다"),
        ({"period": ["2025"]}, "period", "2025", "문자열이 아니다"),
        ({"unit": 3}, "unit", "3", "문자열이 아니다"),
        ({"amount": 10}, "amount", "10", "십진 문자열이 아니다"),
        ({"amount": None}, "amount", "null", "십진 문자열이 아니다"),
        ({"amount": "1e3"}, "amount", "1e3", "십진 문자열이 아니다"),
        ({"amount": "-1"}, "amount", "-1", "음수 사용량"),
        # 선택 칸의 null 은 「없음」이 아니다. 없으면 키를 뺀다.
        ({"fuel": None}, "fuel", "null", "문자열이 아니다 (없으면 키를 뺀다)"),
        ({"factorId": 7}, "factorId", "7", "문자열이 아니다 (없으면 키를 뺀다)"),
        ({"sector": None}, "sector", "null", "문자열이 아니다 (없으면 키를 뺀다)"),
        ({"facilityUse": False}, "facilityUse", "false", "문자열이 아니다 (없으면 키를 뺀다)"),
        ({"variant": {}}, "variant", "[object Object]", "문자열이 아니다 (없으면 키를 뺀다)"),
        ({"factorYear": "2025"}, "factorYear", "2025", "정수가 아니다 (없으면 키를 뺀다)"),
        ({"factorYear": None}, "factorYear", "null", "정수가 아니다 (없으면 키를 뺀다)"),
        ({"factorYear": True}, "factorYear", "true", "정수가 아니다 (없으면 키를 뺀다)"),
        ({"factorYear": 2025.5}, "factorYear", "2025.5", "정수가 아니다 (없으면 키를 뺀다)"),
    ],
)
def test_a_malformed_field_is_a_failed_row_that_keeps_its_scope(
    patch: dict[str, Any], field: str, value: str, reason: str
) -> None:
    result = check_activity_row({**BASE, **patch})
    assert isinstance(result, RowFailed)
    assert (result.scope, result.source_type) == (1, "stationary_combustion")
    assert result.failure == InvalidActivity(field=field, value=value, reason=reason)


def test_missing_required_fields() -> None:
    for key, value in [("id", "undefined"), ("orgUnit", "undefined"), ("period", "undefined"), ("unit", "undefined")]:
        raw = {k: v for k, v in BASE.items() if k != key}
        result = check_activity_row(raw)
        assert isinstance(result, RowFailed)
        assert result.failure == InvalidActivity(field=key, value=value, reason="문자열이 아니다")
    # 사용량이 없는 행: TS 와 같은 갈래다(String(undefined)).
    result = check_activity_row({k: v for k, v in BASE.items() if k != "amount"})
    assert isinstance(result, RowFailed)
    assert result.failure == InvalidActivity(field="amount", value="undefined", reason="십진 문자열이 아니다")
    # 식별 칸이 없거나 문자열이 아니어도 실패한 행의 식별 칸은 문자열이다(없으면 빈 문자열).
    result = check_activity_row({"sourceType": "purchased_heat", "id": 7, "amount": "1", "unit": "GJ"})
    assert isinstance(result, RowFailed)
    assert (result.row_id, result.org_unit, result.period, result.scope) == ("7", "", "", 2)


@pytest.mark.parametrize(
    "tiers",
    [
        None,
        "tier2",
        [],
        {"calorific": 2, "co2": 2, "nonCo2": 1},  # oxidation 키가 없다
        {"calorific": 2, "co2": 2, "nonCo2": 1, "oxidation": "2"},
        {"calorific": True, "co2": 2, "nonCo2": 1, "oxidation": 2},
        {"calorific": 2, "co2": None, "nonCo2": 1, "oxidation": 2},
    ],
)
def test_malformed_parameter_tiers_are_a_failed_row(tiers: Any) -> None:
    result = check_activity_row({**BASE, "parameterTiers": tiers})
    assert isinstance(result, RowFailed)
    assert result.failure.kind == "invalid_activity"
    assert result.failure.field == "parameterTiers"


def test_tier_values_are_not_range_checked_in_a_row() -> None:
    """행의 등급은 계수와 같은지만 견준다. 7 같은 값은 여기서 막지 않고 「맞는 계수 없음」이 된다(TS 와 같다)."""
    row = check_activity_row({**BASE, "parameterTiers": {"calorific": 7, "co2": 2.0, "nonCo2": 1, "oxidation": 2}})
    assert isinstance(row, ActivityRow)
    assert row.parameter_tiers == ParameterTiers(calorific=7, co2=2, non_co2=1, oxidation=2)
