"""실패 갈래 19종이 각각 한 번 이상 실제로 나오는가. 순수 층.

TS 원본에는 이 파일이 없다. 발주서 §3 「실패 19종 각각 하나 이상」을 한자리에서 세려고 더했다. TS 테스트가 재지 않은
갈래(`fuel_name_ambiguous`)와, 전력 쪽에서 재지 않은 갈래 넷(값 없음·이상 표기·모르는 단위·다른 고시 판)이 여기 있다.
"""

from dataclasses import replace
from typing import Any

from esgapi.reference.calc import FAILURE_KINDS, assemble_combustion_factor, assemble_purchased_electricity_factor
from esgapi.reference.calc.types import FactorRecord, Json
from esgapi.reference.tests.helpers import (
    ALL_RECORDS,
    GROUP_A,
    MAPPING,
    RECORDS,
    TIER1,
    assemble,
    by_id,
    failure_of,
    request,
    swap,
    with_version,
)

TABLE69: Json = {"energyType": "electricity", "source": "guideline_table69", "gasForm": "per_gas"}
GIR_CO2E: Json = {
    "energyType": "electricity",
    "source": "gir_published",
    "gasForm": "co2e",
    "gir": {
        "edition": 2025,
        "period": {"kind": "single_year", "year": 2023},
        "boundary": "consumption",
        "methodology": "ipcc_2006",
    },
}
CO2_ID = "kr-ets-byl12:ef:p3r3:CO2"
T69_CO2 = "kr-ets-byl06:elec:t69:CO2"


def _electricity(records: list[FactorRecord], req: Json = TABLE69) -> Json:
    return failure_of(assemble_purchased_electricity_factor(req, records, MAPPING))


def _swap_all(record_id: str, **patch: Any) -> list[FactorRecord]:
    """전력 조립이 읽는 묶음(지침 + GIR)에서 그 id 의 낱줄 하나를 가상 낱줄로 바꾼다."""
    return [*(r for r in ALL_RECORDS if r.id != record_id), replace(by_id(record_id), **patch, synthetic=True)]


def test_two_mappings_for_one_fuel_name_are_ambiguous() -> None:
    """한 연료에 대응이 둘이면 고르지 않는다(별표 10 의 IPCC 이름, 별표 12 배출계수 표의 이름 둘 다)."""
    diesel = next(e for e in MAPPING.fuel_names if e.table == "kr-ets-byl10" and "경유" in e.domestic_names)
    twin = replace(diesel, ipcc_name="synthetic 다른 이름")
    doubled = replace(MAPPING, fuel_names=(*MAPPING.fuel_names, twin))
    assert failure_of(assemble(doubled, tiers=TIER1)) == {
        "kind": "fuel_name_ambiguous",
        "fuel": "경유",
        "table": "kr-ets-byl10",
        "ipccNames": ["가스/디젤 오일", "synthetic 다른 이름"],
    }
    jet = next(e for e in MAPPING.national_ef_names if e.fuel == "항공유")
    two = replace(MAPPING, national_ef_names=(*MAPPING.national_ef_names, replace(jet, ef_name="synthetic 둘째")))
    assert failure_of(assemble(two, fuel="항공유")) == {
        "kind": "fuel_name_ambiguous",
        "fuel": "항공유",
        "table": "kr-ets-byl12",
        "ipccNames": ["항공유(JET-A1)", "synthetic 둘째"],
    }


def test_electricity_rows_fail_by_the_same_rules() -> None:
    """전력 낱줄도 값 없음·이상 표기·모르는 단위·다른 고시 판이면 실패한다."""
    assert _electricity(_swap_all(T69_CO2, value_raw=None, value_status="not_available_in_source")) == {
        "kind": "record_value_missing",
        "parameter": "CO2",
        "recordId": T69_CO2,
        "valueStatus": "not_available_in_source",
    }
    # 값 표기가 남아 있어도 상태가 ok 가 아니면 값이 없는 것이다
    assert _electricity(_swap_all(T69_CO2, value_status="not_available_in_source")) == {
        "kind": "record_value_missing",
        "parameter": "CO2",
        "recordId": T69_CO2,
        "valueStatus": "not_available_in_source",
    }
    assert _electricity(_swap_all(T69_CO2, value_raw="4.567e-1")) == {
        "kind": "invalid_value_raw",
        "parameter": "CO2",
        "recordId": T69_CO2,
        "valueRaw": "4.567e-1",
    }
    # 단위의 기체가 낱줄의 기체와 다르다 / 분모가 MWh 가 아니다
    assert _electricity(_swap_all(T69_CO2, unit_numerator="kgCH4")) == {
        "kind": "unit_notation_unknown",
        "parameter": "CO2",
        "recordId": T69_CO2,
        "unit": "kgCH4/MWh",
    }
    # 질량 단위 표에 없는 분자
    assert _electricity(_swap_all(T69_CO2, unit_numerator="kgCO2")) == {
        "kind": "unit_notation_unknown",
        "parameter": "CO2",
        "recordId": T69_CO2,
        "unit": "kgCO2/MWh",
    }
    assert _electricity(_swap_all(T69_CO2, unit_denominator="kWh")) == {
        "kind": "unit_notation_unknown",
        "parameter": "CO2",
        "recordId": T69_CO2,
        "unit": "tCO2/kWh",
    }
    old = with_version(by_id(T69_CO2).source, "synthetic 옛 고시")
    assert _electricity(_swap_all(T69_CO2, source=old)) == {
        "kind": "guideline_version_mismatch",
        "recordId": T69_CO2,
        "recordVersion": "synthetic 옛 고시",
        "guidelineVersion": MAPPING.guideline.version,
    }
    assert MAPPING.guideline.version == "환경부고시 제2025-64호 (2025-04-11 시행)"
    # GIR 공표 값은 고시의 판과 견주지 않는다(공표문의 판이 따로 있다).
    gir_old = with_version(by_id("gir-2025:main:r6").source, "synthetic 다른 공고")
    done = assemble_purchased_electricity_factor(GIR_CO2E, _swap_all("gir-2025:main:r6", source=gir_old), MAPPING)
    assert done.ok


def test_every_failure_kind_is_produced_at_least_once() -> None:
    """갈래의 목록(FAILURE_KINDS, 19)과 실제로 낸 갈래가 같다. 갈래를 더하고 여기를 잊으면 빨개진다."""
    seen = one_failure_of_every_kind()
    assert len(FAILURE_KINDS) == 19
    assert len(seen) == 19
    assert {failure["kind"] for failure in seen} == set(FAILURE_KINDS)


def one_failure_of_every_kind() -> list[Json]:
    """갈래마다 하나씩, 실제로 조립을 돌려 얻은 실패(JSON). 응답의 꼴을 재는 테스트(test_schemas.py)도 이것을 쓴다."""
    seen: list[Json] = []

    def kind_of(failure: Json) -> str:
        seen.append(failure)
        return str(failure["kind"])

    def combustion(records: list[FactorRecord] | None = None, **overrides: Any) -> str:
        rows = list(RECORDS) if records is None else records
        return kind_of(failure_of(assemble_combustion_factor(request(**overrides), rows, MAPPING)))

    diesel = next(e for e in MAPPING.fuel_names if e.table == "kr-ets-byl10" and "경유" in e.domestic_names)
    doubled = replace(MAPPING, fuel_names=(*MAPPING.fuel_names, replace(diesel, ipcc_name="synthetic")))
    no_state = replace(MAPPING, fuel_states=())
    no_minimum = replace(MAPPING, tier_minimums=())
    base = by_id("gir-2025:main:r6")
    odd_period = replace(base, id="gir-2025:synthetic-odd", conditions={**base.conditions, "기간": "작년"})

    kinds = [
        combustion(tiers=None),
        combustion(fuelState="liquid"),
        combustion(combustionType="mobile"),
        kind_of(failure_of(assemble(no_state))),
        combustion(fuelState="기체"),
        combustion(industry={"ksicCode": "09"}),
        combustion(industry={"ksicCode": "38"}),
        combustion(tiers={"kind": "explicit", "calorific": 2, "co2": 2, "oxidation": 1}),
        combustion(tiers={"kind": "group_minimum", "group": "C"}),
        kind_of(failure_of(assemble(no_minimum, tiers=GROUP_A))),
        combustion(fuel="도시가스(LPG)"),
        kind_of(failure_of(assemble(doubled, tiers=TIER1))),
        combustion([r for r in RECORDS if r.id != CO2_ID]),
        combustion([*RECORDS, replace(by_id(CO2_ID), id="synthetic:dup")]),
        combustion(swap(CO2_ID, value_raw=None, value_status="not_available_in_source")),
        combustion(swap(CO2_ID, value_raw="7.32e4")),
        combustion(swap(CO2_ID, unit_numerator="tCO2")),
        combustion(swap(CO2_ID, source=with_version(by_id(CO2_ID).source, "synthetic 옛 고시"))),
        kind_of(_electricity([*ALL_RECORDS, odd_period], GIR_CO2E)),
    ]
    assert len(kinds) == len(seen)
    return seen
