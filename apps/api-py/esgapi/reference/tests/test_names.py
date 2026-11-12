"""별표마다 이름이 다른 연료의 대응, 별표 12 안의 두 표 이름 대응, 연료 상태. 순수 층.

TS 원본 `ts/factor-assembly/test/names.test.ts` 의 16개를 차례대로 옮겼다. 기대하는 낱줄 id 와 값 표기는 esg-lab 이
지침 원문(환경부고시 제2025-64호 별표 10·11·12)에서 2026-10-03 에 대조한 것이다(band-reports/O-factor-coverage.md).
"""

from dataclasses import replace

from esgapi.reference.calc import AssemblyMapping, Failed, national_calorific_fuels
from esgapi.reference.calc.types import FuelNameEntry
from esgapi.reference.tests.helpers import (
    GROUP_A,
    MAPPING,
    RECORDS,
    TIER1,
    TIER2,
    assemble,
    failure_of,
    param,
    subset,
    value_of,
)

# ── 별표 12 안에서 발열량 표와 배출계수 표의 이름이 다른 연료 ──────────


def test_jet_fuel_tier2_co2_uses_the_emission_table_name() -> None:
    """항공유: CO2 Tier 2 는 배출계수 표의 「항공유(JET-A1)」 낱줄이고 추정 대응으로 남는다."""
    result = assemble(fuel="항공유")
    done = value_of(result)
    assert subset(
        param(result, "calorific"), {"recordId": "kr-ets-byl12:hv:p1r13:net", "value": "33.9", "nameMapping": None}
    )
    assert subset(
        param(result, "CO2"),
        {
            "recordId": "kr-ets-byl12:ef:p3r9:CO2",
            "valueRaw": "73,000",
            "nameUsed": "항공유(JET-A1)",
            "nameMapping": {
                "domestic": "항공유",
                "ipcc": "항공유(JET-A1)",
                "basis": "assumed",
                "table": "kr-ets-byl12",
            },
        },
    )
    assert subset(param(result, "CH4")["nameMapping"], {"ipcc": "제트용 등유", "basis": "assumed"})
    assert [a["detail"] for a in done.evidence["assumptions"]] == [
        "항공유 → 액체",
        "항공유 → 항공유(JET-A1) (kr-ets-byl12 배출계수 표)",
        "항공유 → 제트용 등유 (kr-ets-byl10)",
    ]
    note = done.factor["source"]["note"]
    assert "추정 대응 3건을 탔다" in note
    assert "항공유 → 항공유(JET-A1)" in note


def test_butane_typo_in_the_source_is_bridged_not_fixed() -> None:
    """부탄(LPG3호): 원문 오자로 보이는 「부탄(LPP3호)」 는 고치지 않고 대응으로 잇는다."""
    result = assemble(fuel="부탄(LPG3호)")
    assert subset(
        param(result, "CO2"), {"recordId": "kr-ets-byl12:ef:p3r16:CO2", "nameUsed": "부탄(LPP3호)", "value": "66300"}
    )
    assert any(r.name_original == "부탄(LPP3호)" for r in RECORDS)
    assert not any(r.name_original == "부탄(LPG3호)" and r.record_type == "emission_factor" for r in RECORDS)


def test_same_name_in_both_tables_skips_the_mapping() -> None:
    assert subset(param(assemble(), "CO2"), {"nameUsed": "경유", "nameMapping": None})


def test_fuel_absent_from_the_emission_table_is_not_replaced() -> None:
    """별표 12 배출계수 표에 없는 연료는 다른 연료로 대신하지 않는다(원유, 코크스의 Tier 2)."""
    for fuel in ["원유", "코크스"]:
        assert failure_of(assemble(fuel=fuel, powerGeneration=False)) == {
            "kind": "record_not_found",
            "parameter": "CO2",
            "criteria": {
                "source": "kr-ets-byl12",
                "record_type": "emission_factor",
                "gas": "CO2",
                "gas_basis": "gas_mass",
                "name": fuel,
            },
        }


# ── 별표 10·11 과 이름이 다른 연료 ─────────────────────────────────────


def test_b_a_oil_row_name_is_the_domestic_name() -> None:
    """B-A유: 별표 10 의 B-A유 표(국내에너지원 기준 열이 없다)의 행 이름이 곧 국내 이름이라 지침의 대응이다."""
    result = assemble(fuel="B-A유", tiers=GROUP_A)
    assert subset(
        param(result, "CO2"),
        {
            "recordId": "kr-ets-byl10:p3t1r2:CO2:0",
            "valueRaw": "75,100",
            "nameMapping": {"domestic": "B-A유", "ipcc": "B-A유", "basis": "guideline"},
        },
    )
    # 추정은 연료 상태 하나뿐이다
    assert [a["kind"] for a in value_of(result).evidence["assumptions"]] == ["fuel_state"]
    assert value_of(assemble(fuel="B-A유", tiers=GROUP_A, fuelState="액체")).evidence["assumptions"] == []


def test_naphtha_takes_an_assumed_mapping() -> None:
    """나프타: 별표 10 의 IPCC 이름이 「나프타」, 국내에너지원 기준이 「납사」 라서 추정 대응을 탄다."""
    co2 = param(assemble(fuel="나프타", tiers=GROUP_A), "CO2")
    assert subset(co2, {"nameUsed": "나프타", "nameMapping": {"ipcc": "나프타", "basis": "assumed"}})
    guideline = next(
        e
        for e in MAPPING.fuel_names
        if e.table == "kr-ets-byl10" and e.ipcc_name == "나프타" and e.basis == "guideline"
    )
    assert guideline.domestic_names == ("납사",)


def test_anthracite_and_bituminous_fuels_take_assumed_mappings() -> None:
    """무연탄 세 연료와 유연탄 두 연료는 별표 10 의 국내 이름(줄바꿈 칸 판단 포함)에서 추정 대응으로 잇는다."""
    for fuel, ipcc in [
        ("국내무연탄", "무연탄"),
        ("연료용 수입무연탄", "무연탄"),
        ("원료용 수입무연탄", "무연탄"),
        ("연료용 유연탄(역청탄)", "기타 역청탄"),
        ("원료용 유연탄(역청탄)", "점결탄"),
    ]:
        co2 = param(assemble(fuel=fuel, tiers=GROUP_A), "CO2")
        assert subset(co2["nameMapping"], {"domestic": fuel, "ipcc": ipcc, "basis": "assumed"})


def test_coke_is_guideline_in_table_11_and_assumed_in_table_10() -> None:
    result = assemble(fuel="코크스", tiers=TIER1)
    assert subset(param(result, "calorific")["nameMapping"], {"ipcc": "코크스로 코크스", "basis": "guideline"})
    assert subset(param(result, "CO2")["nameMapping"], {"ipcc": "코크스로 코크스", "basis": "assumed"})
    assert subset(param(result, "CO2"), {"recordId": "kr-ets-byl10:p2t0r10:CO2:0", "valueRaw": "107,000"})


def test_city_gas_lpg_has_no_mapping() -> None:
    """도시가스(LPG) 는 별표 10·11 에 대응이 없어 실패한다(LPG 로 대신하지 않는다)."""
    assert failure_of(assemble(fuel="도시가스(LPG)")) == {
        "kind": "fuel_name_not_mapped",
        "fuel": "도시가스(LPG)",
        "table": "kr-ets-byl10",
        "parameter": "CH4",
    }


# ── 부생연료 1·2호: 별표 10 주3·주4 의 CO2 규칙은 CO2 에만 쓴다 ─────────


def test_byproduct_fuel_ch4_n2o_have_no_mapping() -> None:
    """CH4·N2O 는 대응이 없어 실패한다(등유의 CH4 로 대신하지 않는다)."""
    for fuel in ["부생연료유1호", "부생연료유2호"]:
        assert failure_of(assemble(fuel=fuel, tiers=GROUP_A)) == {
            "kind": "fuel_name_not_mapped",
            "fuel": fuel,
            "table": "kr-ets-byl10",
            "parameter": "CH4",
        }


def _with_synthetic_non_co2() -> AssemblyMapping:
    def entry(domestic: str, ipcc: str) -> FuelNameEntry:
        return FuelNameEntry(
            table="kr-ets-byl10",
            ipcc_name=ipcc,
            domestic_names=(domestic,),
            basis="assumed",
            note="synthetic: 테스트용 CH4·N2O 대응. 지침에 없다",
            source_id="kr-ets-byl10",
            locator="synthetic",
            parameters=("CH4", "N2O"),
        )

    added = (entry("부생연료유1호", "기타 등유"), entry("부생연료유2호", "잔여 연료유"))
    return replace(MAPPING, fuel_names=(*MAPPING.fuel_names, *added))


def test_byproduct_fuel_co2_tier1_rows_when_non_co2_is_mapped() -> None:
    """CH4·N2O 대응이 있다면 CO2 Tier 1 은 기타 등유(1호)·잔여 연료유(2호)의 낱줄이다(CH4·N2O 대응은 synthetic)."""
    table = _with_synthetic_non_co2()
    first = assemble(table, fuel="부생연료유1호", tiers=GROUP_A)
    assert subset(
        param(first, "CO2"),
        {
            "recordId": "kr-ets-byl10:p1t0r10:CO2:0",
            "valueRaw": "71,900",
            "nameMapping": {"ipcc": "기타 등유", "basis": "assumed"},
        },
    )
    details = [a["detail"] for a in value_of(first).evidence["assumptions"]]
    assert "부생연료유1호 → 기타 등유 (kr-ets-byl10, CO2 만)" in details
    second = assemble(table, fuel="부생연료유2호", tiers=GROUP_A)
    assert subset(param(second, "CO2"), {"valueRaw": "77,400", "nameMapping": {"ipcc": "잔여 연료유"}})
    # Tier 2 의 CO2 는 별표 12 배출계수 표의 「부생연료 1호」 다
    tier2 = assemble(table, fuel="부생연료유1호")
    assert subset(param(tier2, "CO2"), {"nameUsed": "부생연료 1호", "valueRaw": "73,500"})


def test_a_co2_only_mapping_is_not_used_for_calorific() -> None:
    assert failure_of(assemble(fuel="부생연료유1호", tiers=TIER1)) == {
        "kind": "fuel_name_not_mapped",
        "fuel": "부생연료유1호",
        "table": "kr-ets-byl11",
        "parameter": "calorific",
    }


# ── 연료 상태 ──────────────────────────────────────────────────────────


def test_petroleum_coke_is_solid_and_needs_power_generation() -> None:
    assert failure_of(assemble(fuel="석유코크스")) == {
        "kind": "missing_input",
        "field": "powerGeneration",
        "reason": "고체연료의 Tier 2 산화계수는 발전부문과 기타부문이 다르다. 발전 여부가 필요하다 (기본값 없음)",
    }
    result = assemble(fuel="석유코크스", powerGeneration=False)
    assert subset(param(result, "oxidation"), {"recordId": "kr-ets-byl06:ox:1:t2:기타부문", "value": "0.98"})
    assert subset(value_of(result).evidence["fuelState"], {"value": "고체", "basis": "assumed"})


def test_propane_and_butane_are_gas() -> None:
    """프로판·부탄은 별표 12 의 석유(16)가 아니라 별표 6 의 문장대로 기체다."""
    for fuel in ["프로판(LPG1호)", "부탄(LPG3호)"]:
        assert subset(param(assemble(fuel=fuel), "oxidation"), {"recordId": "kr-ets-byl06:ox:2:t2", "value": "0.995"})


def test_every_table_12_fuel_has_a_state() -> None:
    """별표 12 의 연료(전기 제외 27개)는 전부 대응표에 상태가 있다."""
    fuels = [fuel for fuel in national_calorific_fuels(RECORDS) if not fuel.startswith("전기")]
    assert len(fuels) == 27
    assert [fuel for fuel in fuels if not any(e.fuel == fuel for e in MAPPING.fuel_states)] == []


# ── 추정 대응을 탄 자리는 근거에 빠짐없이 남는다 ───────────────────────


def test_every_assumed_mapping_is_left_in_the_evidence() -> None:
    """모든 연료 × 조합: 이름 대응이나 연료 상태가 assumed 이면 assumptions 에 그 항목이 있고 출처 note 에 적힌다."""
    checked = 0
    per_mode = [0, 0, 0]
    for fuel in national_calorific_fuels(RECORDS):
        for index, tiers in enumerate([TIER2, GROUP_A, TIER1]):
            result = assemble(fuel=fuel, tiers=tiers, powerGeneration=False)
            if isinstance(result, Failed):
                continue
            evidence = result.value.evidence
            assumptions = evidence["assumptions"]
            for p in evidence["parameters"]:
                used = p["nameMapping"]
                if used is not None and used["basis"] == "assumed":
                    detail = f"{used['domestic']} → {used['ipcc']}"
                    assert any(a["kind"] == "fuel_name" and a["detail"].startswith(detail) for a in assumptions)
            assert any(a["kind"] == "fuel_state" for a in assumptions) == (evidence["fuelState"]["basis"] == "assumed")
            note = result.value.factor["source"]["note"]
            if assumptions:
                assert f"추정 대응 {len(assumptions)}건을 탔다" in note
            else:
                assert "추정 대응" not in note
            checked += 1
            per_mode[index] += 1
    # 분모: 별표 12 순발열량 표의 연료 29개(전기 둘 포함) × 조합 셋 = 87. 그 가운데 조립된 것.
    assert len(national_calorific_fuels(RECORDS)) == 29
    assert (per_mode, checked) == ([22, 24, 24], 70)
