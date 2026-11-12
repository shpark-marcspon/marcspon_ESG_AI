"""속성 테스트. esg-lab `ts/ghg-calc/test/property.test.ts` 의 다섯 속성을 hypothesis 로 옮겼다. 순수 층.

생성 범위는 TS(fast-check)와 같다: 사용량은 coef 0~10^12 × scale 0~6, 행의 틀 8종 × 조직 3 × 기간 3, 한 번에 최대 40행.
회수도 같다(300·300·300·50·100).

hypothesis 는 dev 의존성이다(MPL-2.0). 이미지에는 들어가지 않는다(docker/api-py.Dockerfile 의 --no-dev).
설정: database=None(예시 DB 를 쓰지 않는다), deadline=None(여러 러너가 같이 돌 때 기본 200ms 가 흔들린다),
derandomize=True(실행마다 같은 예시).
"""

import dataclasses
import json
from typing import Any, Final

from hypothesis import given, settings
from hypothesis import strategies as st

from esgapi.core.calc.decimal import Decimal, add, format_decimal, mul, parse_decimal
from esgapi.inventory.engines.scope12.engine_1.aggregate import GROUP_KEYS, GroupKey, aggregate
from esgapi.inventory.engines.scope12.engine_1.calc import calculate, calculate_row
from esgapi.inventory.engines.scope12.engine_1.serialize import row_result_to_dict
from esgapi.inventory.engines.scope12.engine_1.types import ActivityRow, CalcOptions, RowFailed, RowOk, RowResult
from esgapi.inventory.tests.support import COMMERCIAL, ELECTRICITY_ID, ETS_GWP, MANUFACTURING, TIER2, bare, load_tables

tables = load_tables()
OPTS = CalcOptions(gwp_set_id=ETS_GWP)


def dec(text: str) -> Decimal:
    value = parse_decimal(text)
    if value is None:
        raise AssertionError(f"not a decimal: {text}")
    return value


def total(values: list[str]) -> str:
    acc = dec("0")
    for value in values:
        acc = add(acc, dec(value))
    return format_decimal(acc)


def profile(runs: int) -> settings:
    return settings(max_examples=runs, database=None, deadline=None, derandomize=True)


# 소수 6자리까지의 음이 아닌 사용량
amounts = st.tuples(st.integers(min_value=0, max_value=10**12), st.integers(min_value=0, max_value=6)).map(
    lambda pair: format_decimal(Decimal(pair[0], pair[1]))
)

TEMPLATES: Final[list[dict[str, Any]]] = [
    {
        "source_type": "stationary_combustion",
        "fuel": "diesel",
        "sector": MANUFACTURING,
        "parameter_tiers": TIER2,
        "unit": "L",
    },
    {
        "source_type": "stationary_combustion",
        "fuel": "diesel",
        "sector": MANUFACTURING,
        "parameter_tiers": TIER2,
        "unit": "kL",
    },
    {
        "source_type": "stationary_combustion",
        "fuel": "city-gas-lng",
        "sector": COMMERCIAL,
        "parameter_tiers": TIER2,
        "unit": "Nm3",
    },
    {"source_type": "mobile_combustion", "fuel": "synthetic-fuel-a", "unit": "L"},
    {"source_type": "stationary_combustion", "fuel": "synthetic-fuel-b", "unit": "t"},
    {"source_type": "purchased_electricity", "factor_id": ELECTRICITY_ID, "unit": "kWh"},
    {"source_type": "purchased_heat", "unit": "GJ"},
    # 계수가 없는 행: 집계에서 0 이 아니라 실패로 남아야 한다
    {"source_type": "stationary_combustion", "fuel": "no-such-fuel", "unit": "L"},
]


def make_row(template: dict[str, Any], org_unit: str, period: str, amount: str) -> ActivityRow:
    return bare(**template, org_unit=org_unit, period=period, amount=amount)


def number_rows(rows: list[ActivityRow]) -> list[ActivityRow]:
    return [dataclasses.replace(r, id=f"p{i}") for i, r in enumerate(rows)]


def pick_keys(picks: list[bool]) -> list[GroupKey]:
    return [key for key, picked in zip(GROUP_KEYS, picks, strict=True) if picked]


activity = st.builds(
    make_row,
    st.sampled_from(TEMPLATES),
    st.sampled_from(["site-1", "site-2", "site-3"]),
    st.sampled_from(["2025-01", "2025-02", "2025-03"]),
    amounts,
)
activities = st.lists(activity, max_size=40).map(number_rows)
# 묶음 기준 넷의 부분열(순서는 그대로)
group_keys = st.lists(st.booleans(), min_size=4, max_size=4).map(pick_keys)


def ok_co2e(rows: list[RowResult]) -> list[str]:
    return [r.co2e for r in rows if isinstance(r, RowOk)]


@profile(300)
@given(activities, group_keys)
def test_row_sum_equals_total_equals_sum_of_group_totals(rows_in: list[ActivityRow], by: list[GroupKey]) -> None:
    """행 단위 합 = 집계 합 = 묶음 합의 합 (문자열까지)."""
    rows = calculate(rows_in, tables, OPTS)
    result = aggregate(rows, by)
    row_sum = total(ok_co2e(rows))
    assert result.total.co2e == row_sum
    assert total([g.co2e for g in result.groups]) == row_sum
    assert total(list(result.total.co2e_by_gas.values())) == row_sum
    # 실패한 행은 어디에도 0 으로 섞이지 않고 id 로 남는다
    failed_ids = [r.row_id for r in rows if isinstance(r, RowFailed)]
    assert list(result.total.failed_row_ids) == failed_ids
    assert sorted(i for g in result.groups for i in g.failed_row_ids) == sorted(failed_ids)
    assert sum(g.ok_row_count for g in result.groups) == len(rows) - len(failed_ids)


@profile(300)
@given(activity)
def test_row_total_equals_sum_of_its_gases(row_in: ActivityRow) -> None:
    """행의 합계 = 그 행의 기체별 환산값의 합."""
    result = calculate_row(row_in, tables, OPTS)
    if isinstance(result, RowOk):
        assert total([g.co2e for g in result.gases]) == result.co2e


@profile(300)
@given(activity, st.sampled_from(["2", "3", "0.5", "1.37"]))
def test_k_times_the_amount_is_exactly_k_times_the_emission(row_in: ActivityRow, k: str) -> None:
    """사용량 k 배 → 배출량 정확히 k 배 (k = 2, 3, 0.5, 1.37)."""
    base = calculate_row(row_in, tables, OPTS)
    scaled_amount = format_decimal(mul(dec(row_in.amount), dec(k)))
    scaled = calculate_row(dataclasses.replace(row_in, amount=scaled_amount), tables, OPTS)
    assert scaled.status == base.status
    if isinstance(base, RowOk) and isinstance(scaled, RowOk):
        assert scaled.co2e == format_decimal(mul(dec(base.co2e), dec(k)))
        for scaled_gas, base_gas in zip(scaled.gases, base.gases, strict=True):
            assert scaled_gas.mass == format_decimal(mul(dec(base_gas.mass), dec(k)))


@profile(50)
@given(activities)
def test_same_input_gives_same_output(rows_in: list[ActivityRow]) -> None:
    """같은 입력이면 같은 출력이다 (결정적). JSON 으로 적은 글자까지."""

    def render() -> str:
        return json.dumps([row_result_to_dict(r) for r in calculate(rows_in, tables, OPTS)], ensure_ascii=False)

    assert render() == render()


@profile(100)
@given(activities)
def test_row_order_does_not_change_the_totals(rows_in: list[ActivityRow]) -> None:
    """행 순서를 바꿔도 합계가 같다."""
    forward = aggregate(calculate(rows_in, tables, OPTS), ["scope"])
    backward = aggregate(calculate(list(reversed(rows_in)), tables, OPTS), ["scope"])
    assert backward.total.co2e == forward.total.co2e
    assert [(g.key, g.co2e) for g in backward.groups] == [(g.key, g.co2e) for g in forward.groups]
