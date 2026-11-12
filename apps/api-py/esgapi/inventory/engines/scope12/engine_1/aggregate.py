"""집계. esg-lab `ts/ghg-calc/src/aggregate.ts` 를 옮긴 것이다.

집계 규칙: 합계는 행의 **정확한 값**을 더한 것이다. 반올림한 행 값을 더하지 않는다.
그래서 어떤 묶음으로 나눠도 (묶음 합의 합) = (전체 합) = (행 값의 합)이 문자열까지 같다.
보고용 자릿수는 round_for_report 로 합계에 한 번만 적용한다.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from esgapi.core.calc.decimal import (
    ZERO,
    Decimal,
    RoundingMode,
    add,
    format_decimal,
    parse_decimal,
    round_decimal,
)
from esgapi.inventory.engines.scope12.engine_1.types import FactorGas, RowFailed, RowResult
from esgapi.inventory.tools.jsrepr import js_json, js_sort_key, js_string

GroupKey = Literal["orgUnit", "period", "scope", "sourceType"]
GROUP_KEYS: Final[tuple[GroupKey, ...]] = ("orgUnit", "period", "scope", "sourceType")

_GAS_ORDER: Final[tuple[FactorGas, ...]] = ("CO2", "CH4", "N2O", "CO2e")


@dataclass(frozen=True, slots=True, kw_only=True)
class Totals:
    # 성공한 행의 정확한 합 (tCO2eq). 반올림하지 않는다.
    co2e: str
    # 기체 → 환산 합. 순서는 CO2·CH4·N2O·CO2e 이고 나온 적 없는 기체는 키가 없다.
    co2e_by_gas: dict[FactorGas, str]
    ok_row_count: int
    # 계산에 실패한 행. 합계에 0 으로 들어간 것이 아니라 빠져 있다.
    failed_row_ids: tuple[str, ...]
    # 실패한 행이 하나라도 있으면 False. 이때 co2e 는 부분합이다.
    complete: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Group(Totals):
    key: dict[GroupKey, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class Aggregation:
    by: tuple[GroupKey, ...]
    groups: tuple[Group, ...]
    total: Totals


@dataclass(slots=True)
class _Accumulator:
    co2e: Decimal = ZERO
    by_gas: dict[FactorGas, Decimal] = field(default_factory=dict[FactorGas, Decimal])
    ok_row_count: int = 0
    failed_row_ids: list[str] = field(default_factory=list[str])


def _must(text: str) -> Decimal:
    # 엔진이 자기가 낸 문자열을 다시 읽는 자리다. 64자 상한을 걸지 않는다(합은 입력보다 길 수 있다).
    value = parse_decimal(text)
    if value is None:
        raise ValueError(f"row result holds a non-decimal value: {text}")
    return value


def _accumulate(acc: _Accumulator, row: RowResult) -> None:
    if isinstance(row, RowFailed):
        acc.failed_row_ids.append(row.row_id)
        return
    acc.ok_row_count += 1
    acc.co2e = add(acc.co2e, _must(row.co2e))
    for gas in row.gases:
        acc.by_gas[gas.gas] = add(acc.by_gas.get(gas.gas, ZERO), _must(gas.co2e))


def _key_value(row: RowResult, key: GroupKey) -> str:
    """JS 의 `String(row[k])`: 모르는 Scope·배출원 유형(None)은 "null" 이라는 묶음이 된다."""
    if key == "orgUnit":
        return row.org_unit
    if key == "period":
        return row.period
    return js_string(row.scope if key == "scope" else row.source_type)


def _co2e_by_gas(acc: _Accumulator) -> dict[FactorGas, str]:
    return {gas: format_decimal(acc.by_gas[gas]) for gas in _GAS_ORDER if gas in acc.by_gas}


def aggregate(rows: Sequence[RowResult], by: Sequence[GroupKey]) -> Aggregation:
    total = _Accumulator()
    groups: dict[str, tuple[dict[GroupKey, str], _Accumulator]] = {}

    for row in rows:
        _accumulate(total, row)
        key: dict[GroupKey, str] = {k: _key_value(row, k) for k in by}
        group_id = js_json([key[k] for k in by])
        group = groups.get(group_id)
        if group is None:
            group = (key, _Accumulator())
            groups[group_id] = group
        _accumulate(group[1], row)

    # 묶음은 키 배열을 JSON 으로 적은 글자의 순서다(JS 의 문자열 비교 = UTF-16 코드 단위 순).
    ordered = sorted(groups.items(), key=lambda item: js_sort_key(item[0]))
    return Aggregation(
        by=tuple(by),
        groups=tuple(
            Group(
                key=key,
                co2e=format_decimal(acc.co2e),
                co2e_by_gas=_co2e_by_gas(acc),
                ok_row_count=acc.ok_row_count,
                failed_row_ids=tuple(acc.failed_row_ids),
                complete=not acc.failed_row_ids,
            )
            for _, (key, acc) in ordered
        ),
        total=Totals(
            co2e=format_decimal(total.co2e),
            co2e_by_gas=_co2e_by_gas(total),
            ok_row_count=total.ok_row_count,
            failed_row_ids=tuple(total.failed_row_ids),
            complete=not total.failed_row_ids,
        ),
    )


def round_for_report(value: str, digits: int, mode: RoundingMode) -> str:
    """보고용 반올림. 자릿수와 방식에 기본값이 없다. 부르는 쪽이 보고 기준에 맞춰 정한다."""
    return round_decimal(_must(value), digits, mode)
