"""집계. esg-lab `ts/ghg-calc/test/aggregate.test.ts` 8건을 옮기고, 파이썬으로 옮기며 생긴 자리를 더했다. 순수 층."""

from typing import Any

from esgapi.inventory.engines.scope12.engine_1.aggregate import Aggregation, Group, Totals, aggregate, round_for_report
from esgapi.inventory.engines.scope12.engine_1.calc import calculate, calculate_raw
from esgapi.inventory.engines.scope12.engine_1.types import SCOPE_OF, ActivityRow, CalcOptions, RowOk
from esgapi.inventory.tests.support import COMMERCIAL, ELECTRICITY_ID, ETS_GWP, bare, load_tables, row

tables = load_tables()
ETS = CalcOptions(gwp_set_id=ETS_GWP)

activities: list[ActivityRow] = [
    row(id="a1", org_unit="site-1", period="2025-01", amount="1000"),
    row(id="a2", org_unit="site-1", period="2025-02", amount="333.333"),
    row(
        id="a3",
        org_unit="site-2",
        period="2025-01",
        fuel="city-gas-lng",
        sector=COMMERCIAL,
        amount="12345.678",
        unit="Nm3",
    ),
    bare(
        id="a4",
        org_unit="site-2",
        period="2025-01",
        source_type="purchased_electricity",
        factor_id=ELECTRICITY_ID,
        amount="1234.567",
        unit="MWh",
    ),
    bare(
        id="a5",
        org_unit="site-1",
        period="2025-01",
        source_type="purchased_electricity",
        factor_id=ELECTRICITY_ID,
        amount="777",
        unit="kWh",
    ),
]

# 기대값은 엔진과 따로 계산했다 (esg-lab 의 테스트에서 옮김: Python decimal, 반올림 없음).
#   a1 2.5596384 / a2 0.8532119467872 / a3 26.8724539692981 / a4 567.1731662102 / a5 0.3569620362
rows = calculate(activities, tables, ETS)
TOTAL = "597.8154325624853"


def group_of(result: Aggregation, **key: str) -> Group:
    return next(g for g in result.groups if g.key == key)


def test_totals_by_scope() -> None:
    result = aggregate(rows, ["scope"])
    assert [(g.key, g.co2e, g.ok_row_count) for g in result.groups] == [
        ({"scope": "1"}, "30.2853043160853", 3),
        ({"scope": "2"}, "567.5301282464", 2),
    ]
    assert result.total.co2e == TOTAL
    assert result.total.complete is True


def test_groups_by_org_period_source_type_are_sorted_by_key() -> None:
    result = aggregate(rows, ["orgUnit", "period", "sourceType"])
    assert ["|".join(g.key.values()) for g in result.groups] == [
        "site-1|2025-01|purchased_electricity",
        "site-1|2025-01|stationary_combustion",
        "site-1|2025-02|stationary_combustion",
        "site-2|2025-01|purchased_electricity",
        "site-2|2025-01|stationary_combustion",
    ]
    assert result.by == ("orgUnit", "period", "sourceType")


def test_no_group_key_means_one_group() -> None:
    result = aggregate(rows, [])
    assert len(result.groups) == 1
    assert result.groups[0].co2e == result.total.co2e


def test_per_gas_totals_add_up_to_the_total() -> None:
    total = aggregate(rows, []).total
    assert total.co2e_by_gas == {
        "CO2": "594.3899091441157",
        "CH4": "0.1467747274518",
        "N2O": "3.2787486909178",
    }
    assert list(total.co2e_by_gas) == ["CO2", "CH4", "N2O"]  # 기체의 순서


def test_a_failed_row_is_left_out_and_shown_not_added_as_zero() -> None:
    bad = row(id="bad", org_unit="site-1", period="2025-01", fuel="no-such-fuel")
    result = aggregate(calculate([*activities, bad], tables, ETS), ["orgUnit"])
    total = result.total
    assert (total.co2e, total.ok_row_count, total.failed_row_ids, total.complete) == (TOTAL, 5, ("bad",), False)
    site1, site2 = group_of(result, orgUnit="site-1"), group_of(result, orgUnit="site-2")
    assert (site1.failed_row_ids, site1.complete) == (("bad",), False)
    assert (site2.failed_row_ids, site2.complete) == ((), True)


def test_a_row_of_unknown_source_type_joins_no_scope_and_stays_failed() -> None:
    odd: dict[str, Any] = {
        "id": "odd",
        "orgUnit": "synthetic-site",
        "period": "2025",
        "sourceType": "scope3_travel",
        "amount": "1",
        "unit": "GJ",
    }
    with_unknown = [*rows, *calculate_raw([odd], tables, ETS)]
    result = aggregate(with_unknown, ["scope"])
    assert (result.total.co2e, result.total.failed_row_ids, result.total.complete) == (TOTAL, ("odd",), False)
    # 묶음의 이름은 "null" 이다(JS 의 String(null)). 파이썬의 str(None) 인 "None" 이 아니다.
    unknown = group_of(result, scope="null")
    assert (unknown.co2e, unknown.ok_row_count, unknown.failed_row_ids) == ("0", 0, ("odd",))


def test_no_rows_is_zero_and_complete() -> None:
    assert aggregate([], ["scope"]) == Aggregation(
        by=("scope",),
        groups=(),
        total=Totals(co2e="0", co2e_by_gas={}, ok_row_count=0, failed_row_ids=(), complete=True),
    )


def test_report_rounding_applies_once_to_the_exact_total() -> None:
    """반올림한 행을 더하지 않는다."""
    total = aggregate(rows, []).total
    assert round_for_report(total.co2e, 0, "half_up") == "598"
    assert round_for_report(total.co2e, 0, "down") == "597"
    assert round_for_report(total.co2e, 1, "half_up") == "597.8"
    # 반올림한 행을 더하면 어긋난다: 2.6 + 0.9 + 26.9 + 567.2 + 0.4 = 598.0 ≠ 597.8
    rounded = [round_for_report(r.co2e, 1, "half_up") for r in rows if isinstance(r, RowOk)]
    assert rounded == ["2.6", "0.9", "26.9", "567.2", "0.4"]


# ── 파이썬으로 옮기며 더한 것 ─────────────────────────────────────────


def test_two_rows_with_64_character_amounts_aggregate() -> None:
    """바깥 입력은 64자에서 막지만, 엔진이 자기가 낸 합(64자보다 길다)을 다시 읽는 자리에는 상한이 없다."""
    big = "9" * 64
    two = calculate([row(id="b1", amount=big), row(id="b2", amount=big)], tables, ETS)
    assert all(isinstance(r, RowOk) for r in two)
    result = aggregate(two, ["scope"])
    assert result.total.complete is True
    assert len(result.total.co2e) > 64
    first = two[0]
    assert isinstance(first, RowOk)
    # 두 행의 합 = 한 행의 두 배 (문자열까지)
    doubled = calculate([row(id="b3", amount=str(int(big) * 2))], tables, ETS)[0]
    assert not isinstance(doubled, RowOk)  # 65자라 실패한다: 합은 입력으로는 받지 못할 길이까지 간다
    assert result.groups[0].co2e == result.total.co2e


def test_groups_are_ordered_like_javascript_strings() -> None:
    """묶음의 순서는 JS 의 문자열 비교(UTF-16 코드 단위)다. 파이썬의 문자열 비교(코드 포인트)로는 이모지가 뒤로 간다."""
    names = ["￥-site", "😀-site", "가-site", 'a"site', "Z-site", "a-site"]
    heat = [
        bare(id=f"o{i}", org_unit=name, source_type="purchased_heat", amount="1", unit="GJ")
        for i, name in enumerate(names)
    ]
    result = aggregate(calculate(heat, tables, ETS), ["orgUnit"])
    ordered = [g.key["orgUnit"] for g in result.groups]
    assert ordered == ["Z-site", "a-site", 'a"site', "가-site", "😀-site", "￥-site"]
    assert ordered != sorted(names)  # 코드 포인트 순과 다르다는 것(이 테스트가 헛돌지 않는다는 것)


def test_a_null_value_and_the_text_null_do_not_share_a_group() -> None:
    """js_string(None) = "null" 이 글자 "null" 인 행과 한 묶음으로 섞이는가(RPT-22 3절, 밴드 CU2) — 아니다.

    orgUnit·period: None 은 행 검사(activity.py)에서 실패 행이 되고 그 키는 `?? ""` 로 "" 다. 글자 "null" 은 그대로
    "null" 이다. scope·sourceType: None 은 모르는 배출원 유형일 때뿐이고, 아는 값에 "null" 이 없다 — 그래서 "null"
    묶음에는 모르는 유형의 행만 든다(글자 "null" 인 sourceType 도 모르는 유형이라 거기 드는 것이 맞다).
    """
    base: dict[str, Any] = {"period": "2025", "sourceType": "purchased_heat", "amount": "1", "unit": "GJ"}
    raw = [
        {**base, "id": "n1", "orgUnit": None},
        {**base, "id": "n2", "orgUnit": "null"},
        {**base, "id": "n3", "orgUnit": "null-site", "period": None},
        {**base, "id": "n4", "orgUnit": "null-site", "period": "null"},
        {**base, "id": "n5", "orgUnit": "u", "sourceType": None},
        {**base, "id": "n6", "orgUnit": "u", "sourceType": "null"},
    ]
    result = aggregate(calculate_raw(raw, tables, ETS), ["orgUnit", "period"])
    members = {tuple(g.key.values()): (g.ok_row_count, g.failed_row_ids) for g in result.groups}
    assert members[("", "2025")] == (0, ("n1",))
    assert members[("null", "2025")] == (1, ())
    assert members[("null-site", "")] == (0, ("n3",))
    assert members[("null-site", "null")] == (1, ())

    by_type = aggregate(calculate_raw(raw, tables, ETS), ["sourceType"])
    assert "null" not in SCOPE_OF
    assert {str(s) for s in SCOPE_OF.values()}.isdisjoint({"null"})
    assert group_of(by_type, sourceType="null").failed_row_ids == ("n5", "n6")
    assert group_of(by_type, sourceType="null").ok_row_count == 0
