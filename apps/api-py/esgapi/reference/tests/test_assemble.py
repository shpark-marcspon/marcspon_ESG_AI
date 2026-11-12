"""고정연소 조립. 순수 층: 패키지의 자료 사본(지침 낱줄 560건)과 대응표에서 낱줄을 골라 묶는다.

TS 원본 `ts/factor-assembly/test/assemble.test.ts` 의 38개(`it` 35 + `it.each` 3)를 차례대로 옮겼다.
기대하는 낱줄 id 와 값 표기는 esg-lab 이 지침 원문(환경부고시 제2025-64호 별표 6·10·11·12)에서 2026-10-02 에
대조한 것이다(band-reports/N-factor-assembly.md). 여기서 새로 정한 수치는 없다.
"""

import re
from dataclasses import replace
from typing import Any

import pytest

from esgapi.reference.calc import assemble_combustion_factor
from esgapi.reference.calc.types import Json
from esgapi.reference.tests.helpers import (
    GROUP_A,
    MAPPING,
    RECORDS,
    TIER1,
    assemble,
    by_id,
    failure_of,
    request,
    subset,
    swap,
    synthetic,
    value_of,
    with_version,
)

CO2_ID = "kr-ets-byl12:ef:p3r3:CO2"
HV_ID = "kr-ets-byl12:hv:p1r5:net"
OX_ID = "kr-ets-byl06:ox:3:t2"

# 실패의 곁칸 글자(운영 코드 assemble.py·policy.py·sector.py 의 글 그대로). 실패는 칸 전부를 == 로 견준다.
NEEDS_POWER_GENERATION = "고체연료의 Tier 2 산화계수는 발전부문과 기타부문이 다르다. 발전 여부가 필요하다 (기본값 없음)"
TIER_REASON = "산정등급은 1~4 의 정수다"
SITE_VALUES = (
    "별표 6 고정연소 각 절 「5. 매개변수별 관리기준」 Tier 3: 사업자가 개발하거나 공급자가 분석한 값 (제16조), "
    "Tier 4: 연속측정"
)
OXIDATION_FOLLOWS_CO2 = (
    "별표 6 고정연소 각 절 「4. 배출량 산정방법론」: 산화계수는 CO2 배출계수와 동일한 산정등급을 사용하여야 한다"
)
NON_CO2_TIER_ONE = "별표 6 고정연소 각 절 「3. 보고대상 온실가스」 표: CH4·N2O 의 산정방법론은 Tier 1 뿐이다"
OVERLAP_LOCATOR = "PDF 4쪽 부문 정의 아래 주석 (*, **)"
LIQUID_LOCATOR = "PDF 15쪽 「3. 고정연소 (액체연료)」 1. 배출활동 개요"


def missing(field: str, reason: str) -> Json:
    return {"kind": "missing_input", "field": field, "reason": reason}


def invalid(field: str, value: str, reason: str) -> Json:
    return {"kind": "invalid_input", "field": field, "value": value, "reason": reason}


def not_found(parameter: str, **criteria: str) -> Json:
    return {"kind": "record_not_found", "parameter": parameter, "criteria": criteria}


def calorific_criteria(name: str, source: str = "kr-ets-byl12") -> Json:
    return {"source": source, "record_type": "heating_value", "heating_value_basis": "net", "name": name}


def co2_criteria(name: str, source: str = "kr-ets-byl12") -> Json:
    return {"source": source, "record_type": "emission_factor", "gas": "CO2", "gas_basis": "gas_mass", "name": name}


def oxidation_criteria(state: str, tier: int, **sector: str) -> Json:
    return {
        "source": "kr-ets-byl06",
        "record_type": "oxidation_factor",
        "연료 상태": state,
        "산정등급": f"Tier {tier}",
        **sector,
    }


def pick(parameters: list[Json]) -> Json:
    return {
        p["parameter"]: {"tier": p["tier"], "recordId": p["recordId"], "valueRaw": p["valueRaw"], "value": p["value"]}
        for p in parameters
    }


# ── 산정등급 조합별 조립 (경유, 제조업·건설업) ─────────────────────────


def test_all_tier2_picks_national_tables_and_liquid_oxidation() -> None:
    """전부 Tier 2: 발열량·CO2 계수는 별표 12, CH4·N2O 는 별표 10, 산화계수는 액체연료 Tier 2."""
    done = value_of(assemble())
    assert pick(done.evidence["parameters"]) == {
        "calorific": {"tier": 2, "recordId": HV_ID, "valueRaw": "35.2", "value": "35.2"},
        "CO2": {"tier": 2, "recordId": CO2_ID, "valueRaw": "73,200", "value": "73200"},
        "CH4": {"tier": 1, "recordId": "kr-ets-byl10:p1t0r12:CH4:2", "valueRaw": "3", "value": "3"},
        "N2O": {"tier": 1, "recordId": "kr-ets-byl10:p1t0r12:N2O:5", "valueRaw": "0.6", "value": "0.6"},
        "oxidation": {"tier": 2, "recordId": "kr-ets-byl06:ox:3:t2", "valueRaw": "0.99", "value": "0.99"},
    }
    assert subset(
        done.factor,
        {
            "kind": "combustion",
            "id": "kr-ets:stationary:경유:manufacturing_construction:cv2_co2ef2_ch4n2o1_ox2",
            "fuel": "경유",
            "combustionType": "stationary",
            "sector": "manufacturing_construction",
            "parameterTiers": {"calorific": 2, "co2": 2, "nonCo2": 1, "oxidation": 2},
            "calorific": {"value": "35.2", "energyUnit": "MJ", "perUnit": "L", "basis": "net"},
            "emissionFactors": [
                {"gas": "CO2", "value": "73200", "massUnit": "kg", "perEnergyUnit": "TJ"},
                {"gas": "CH4", "value": "3", "massUnit": "kg", "perEnergyUnit": "TJ"},
                {"gas": "N2O", "value": "0.6", "massUnit": "kg", "perEnergyUnit": "TJ"},
            ],
            "oxidationFactor": "0.99",
        },
    )
    assert "facilityUse" not in done.factor
    assert done.evidence["assumptions"] == []


def test_group_a_minimum_takes_only_calorific_from_the_national_table() -> None:
    """A 그룹 최소기준: 발열량만 별표 12(Tier 2)이고 CO2 계수는 별표 10(Tier 1), 산화계수 1.0."""
    done = value_of(assemble(tiers=GROUP_A))
    tiers = done.evidence["tiers"]
    assert subset(
        tiers,
        {"values": {"calorific": 2, "co2": 1, "nonCo2": 1, "oxidation": 1}, "basis": "group_minimum", "group": "A"},
    )
    assert len([loc for loc in tiers["locators"] if loc.startswith("별표 5")]) == 3
    assert subset(
        pick(done.evidence["parameters"]),
        {
            "calorific": {"tier": 2, "recordId": HV_ID, "value": "35.2"},
            "CO2": {"tier": 1, "recordId": "kr-ets-byl10:p1t0r12:CO2:0", "valueRaw": "74,100", "value": "74100"},
            "oxidation": {"tier": 1, "recordId": "kr-ets-byl06:ox:3:t1", "value": "1.0"},
        },
    )
    # CO2 계수가 국가 고유값(별표 12)에서 오면 안 된다.
    co2 = next(p for p in done.evidence["parameters"] if p["parameter"] == "CO2")
    assert co2["sourceId"] == "kr-ets-byl10"
    assert subset(co2["nameMapping"], {"domestic": "경유", "ipcc": "가스/디젤 오일", "basis": "guideline"})
    assert done.factor["emissionFactors"][0] == {
        "gas": "CO2",
        "value": "74100",
        "massUnit": "kg",
        "perEnergyUnit": "TJ",
    }
    assert done.factor["oxidationFactor"] == "1.0"
    assert done.factor["id"] == "kr-ets:stationary:경유:manufacturing_construction:cv2_co2ef1_ch4n2o1_ox1"


def test_group_b_minimum_equals_all_tier2() -> None:
    b = value_of(assemble(tiers={"kind": "group_minimum", "group": "B"}))
    explicit = value_of(assemble())
    assert b.factor["id"] == explicit.factor["id"]
    assert b.factor["emissionFactors"] == explicit.factor["emissionFactors"]
    assert b.evidence["tiers"]["basis"] == "group_minimum"


def test_all_tier1_takes_calorific_from_table_11_by_mass() -> None:
    """전부 Tier 1: 발열량은 별표 11(질량 기준), CO2 계수는 별표 10."""
    done = value_of(assemble(tiers=TIER1))
    assert subset(
        pick(done.evidence["parameters"]),
        {
            "calorific": {"tier": 1, "recordId": "kr-ets-byl11:p1t0r11", "valueRaw": "43.0"},
            "CO2": {"tier": 1, "recordId": "kr-ets-byl10:p1t0r12:CO2:0", "value": "74100"},
            "oxidation": {"tier": 1, "recordId": "kr-ets-byl06:ox:3:t1"},
        },
    )
    # 별표 11 의 발열량은 TJ/Gg 다. 리터로 잰 사용량에 쓰려면 밀도가 있어야 하고, 조립은 그것을 지어내지 않는다.
    assert done.factor["calorific"] == {"value": "43.0", "energyUnit": "TJ", "perUnit": "Gg", "basis": "net"}
    assert subset(
        done.evidence["parameters"][0]["nameMapping"],
        {"domestic": "경유", "ipcc": "가스/디젤 오일", "basis": "guideline"},
    )


def test_every_parameter_carries_its_source_and_rule() -> None:
    """조립된 계수는 낱줄마다 출처(낱줄 id, 위치, 파일 해시, 확인 일자)와 규칙을 싣는다."""
    done = value_of(assemble())
    parameters = done.evidence["parameters"]
    assert [p["parameter"] for p in parameters] == ["calorific", "CO2", "CH4", "N2O", "oxidation"]
    for p in parameters:
        record = by_id(p["recordId"])
        assert p["locator"] == record.source.locator
        assert p["fileSha256"] == record.source.file_sha256
        assert p["url"].startswith("https://www.law.go.kr/")
        assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", p["retrieved"])
        assert len(p["rule"]) > 0
    assert parameters[1]["conditions"] == {"병합 셀": "원문 표에서 등유 행과 한 칸을 같이 쓴다"}
    source = done.factor["source"]
    assert subset(source, {"kind": "cited", "url": MAPPING.guideline.url, "checkedOn": "2026-10-02"})
    for p in parameters:
        assert p["locator"] in source["locator"]
    assert "발열량 Tier 2, CO2 계수 Tier 2, CH4·N2O 계수 Tier 1, 산화계수 Tier 2" in source["note"]
    assert done.factor["version"] == MAPPING.guideline.version
    assert subset(done.evidence["fuelState"], {"value": "액체", "basis": "guideline"})


# ── 부문별 CH4·N2O 선택 ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("sector", "ch4_id", "ch4", "n2o_id", "n2o"),
    [
        ("energy_industries", "kr-ets-byl10:p1t0r12:CH4:1", "3", "kr-ets-byl10:p1t0r12:N2O:5", "0.6"),
        ("manufacturing_construction", "kr-ets-byl10:p1t0r12:CH4:2", "3", "kr-ets-byl10:p1t0r12:N2O:5", "0.6"),
        ("commercial_public", "kr-ets-byl10:p1t0r12:CH4:3", "10", "kr-ets-byl10:p1t0r12:N2O:6", "0.6"),
        ("residential_other", "kr-ets-byl10:p1t0r12:CH4:4", "10", "kr-ets-byl10:p1t0r12:N2O:6", "0.6"),
    ],
)
def test_diesel_by_sector(sector: str, ch4_id: str, ch4: str, n2o_id: str, n2o: str) -> None:
    done = value_of(assemble(industry={"sector": sector}))
    assert subset(
        pick(done.evidence["parameters"]),
        {"CH4": {"recordId": ch4_id, "value": ch4}, "N2O": {"recordId": n2o_id, "value": n2o}},
    )
    assert done.factor["sector"] == sector
    entry = next(s for s in MAPPING.sectors if s.key == sector)
    assert by_id(ch4_id).conditions["부문"] == entry.ch4_condition


def test_city_gas_ch4_splits_by_sector() -> None:
    """도시가스(LNG): 부문에 따라 CH4 가 1 과 5 로 갈린다."""

    def ch4(sector: str) -> str:
        done = value_of(assemble(fuel="도시가스(LNG)", industry={"sector": sector}))
        return str(done.factor["emissionFactors"][1]["value"])

    sectors = ["energy_industries", "manufacturing_construction", "commercial_public", "residential_other"]
    assert [ch4(sector) for sector in sectors] == ["1", "1", "5", "5"]


def test_sector_from_the_industry_code() -> None:
    def sector(code: str) -> Json:
        return value_of(assemble(industry={"ksicCode": code})).evidence["sector"]

    assert subset(sector("35"), {"key": "energy_industries", "basis": "ksic_division", "ksicCode": "35"})
    assert subset(sector("2011"), {"key": "manufacturing_construction", "basis": "ksic_division"})
    assert sector("47")["key"] == "commercial_public"
    assert sector("01")["key"] == "residential_other"


def test_overlapping_industry_codes_are_not_chosen() -> None:
    """두 부문에 겹치는 업종 코드(38, 58, 59)는 고르지 않고 실패한다."""
    notes = {
        "38": ["(383)은제조업ㆍ건설업계수를적용한다"],
        "58": ["(5821)은상업ㆍ공공배출계수를적용한다"],
        "59": ["(5912)은상업ㆍ공공배출계수를적용한다"],
    }
    for code in ["38", "58", "59", "381", "5811", "591"]:
        assert failure_of(assemble(industry={"ksicCode": code})) == {
            "kind": "sector_ambiguous",
            "ksicCode": code,
            "division": code[:2],
            "candidates": ["manufacturing_construction", "commercial_public"],
            "notes": notes[code[:2]],
            "locator": OVERLAP_LOCATOR,
        }


def test_an_overlap_without_its_footnote_names_both_sector_locators() -> None:
    """겹침 항목이 대응표에 없으면 주석도 없고, locator 는 두 부문의 자리를 잇는다."""
    bare = replace(MAPPING, sector_overlaps=())
    assert failure_of(assemble_combustion_factor(request(industry={"ksicCode": "38"}), RECORDS, bare)) == {
        "kind": "sector_ambiguous",
        "ksicCode": "38",
        "division": "38",
        "candidates": ["manufacturing_construction", "commercial_public"],
        "notes": [],
        "locator": "PDF 4쪽 ② 제조업ㆍ건설업 / PDF 4쪽 ③ 상업ㆍ공공",
    }


def test_a_footnoted_longer_code_decides_the_sector() -> None:
    """원문 주석이 더 자세한 코드로 정해 준 경우에만 그 부문을 쓴다."""

    def sector(code: str) -> Json:
        return value_of(assemble(industry={"ksicCode": code})).evidence["sector"]

    assert subset(sector("383"), {"key": "manufacturing_construction", "basis": "ksic_exception"})
    assert sector("38310")["key"] == "manufacturing_construction"
    assert subset(sector("5821"), {"key": "commercial_public", "basis": "ksic_exception"})
    assert sector("5912")["key"] == "commercial_public"


def test_a_given_sector_assembles_even_for_an_overlapping_code() -> None:
    sector = value_of(assemble(industry={"sector": "commercial_public"})).evidence["sector"]
    assert subset(sector, {"key": "commercial_public", "basis": "input", "ksicCode": None})


def test_industry_codes_outside_the_guideline_fail() -> None:
    for code in ["09", "34", "48", "00"]:
        assert failure_of(assemble(industry={"ksicCode": code})) == {
            "kind": "sector_not_defined",
            "ksicCode": code,
            "division": code[:2],
        }


def test_the_first_ch4_row_is_not_the_commercial_one() -> None:
    """심은 파손 대비: 부문을 무시하고 첫 CH4 낱줄을 집으면 상업·공공의 값이 틀린다."""
    done = value_of(assemble(industry={"sector": "commercial_public"}))
    first = next(
        r for r in RECORDS if r.source.id == "kr-ets-byl10" and r.gas == "CH4" and r.name_original == "가스/디젤 오일"
    )
    assert first.id == "kr-ets-byl10:p1t0r12:CH4:1"
    assert next(p for p in done.evidence["parameters"] if p["parameter"] == "CH4")["recordId"] != first.id


# ── 산화계수: 연료 상태와 발전 여부 ────────────────────────────────────

COAL: Json = {"fuel": "아역청탄", "fuelState": "고체"}


def test_oxidation_by_state_and_tier() -> None:
    """액체 Tier 2 는 0.99, 기체 Tier 2 는 0.995, Tier 1 은 상태와 무관하게 1.0."""
    assert value_of(assemble()).factor["oxidationFactor"] == "0.99"
    assert value_of(assemble(fuel="도시가스(LNG)")).factor["oxidationFactor"] == "0.995"
    assert value_of(assemble(tiers=GROUP_A)).factor["oxidationFactor"] == "1.0"
    last = value_of(assemble(fuel="도시가스(LNG)", tiers=GROUP_A)).evidence["parameters"][-1]
    assert subset(last, {"recordId": "kr-ets-byl06:ox:2:t1", "value": "1.0"})


def test_solid_tier2_splits_by_power_generation() -> None:
    """고체연료 Tier 2 는 발전 0.99, 그 밖 0.98 이고 계수에 시설의 쓰임이 실린다."""
    power = value_of(assemble(**COAL, powerGeneration=True))
    other = value_of(assemble(**COAL, powerGeneration=False))
    assert subset(power.evidence["parameters"][-1], {"recordId": "kr-ets-byl06:ox:1:t2:발전부문", "value": "0.99"})
    assert subset(other.evidence["parameters"][-1], {"recordId": "kr-ets-byl06:ox:1:t2:기타부문", "value": "0.98"})
    assert power.factor["facilityUse"] == "power_generation"
    assert other.factor["facilityUse"] == "other"
    assert power.factor["id"] != other.factor["id"]
    assert power.evidence["fuelState"] == {"value": "고체", "basis": "input", "locator": None}
    assert power.factor["calorific"] == {"value": "19.9", "energyUnit": "MJ", "perUnit": "kg", "basis": "net"}


def test_solid_tier2_without_power_generation_is_not_guessed() -> None:
    assert failure_of(assemble(**COAL)) == missing("powerGeneration", NEEDS_POWER_GENERATION)


def test_a_missing_oxidation_row_names_the_sector_only_for_solid_tier2() -> None:
    """산화 낱줄이 없을 때 criteria: 고체 Tier 2 만 「산화계수 부문」(발전부문/기타부문)이 있고, 그 밖에는 키가 없다."""
    no_oxidation = [r for r in RECORDS if r.record_type != "oxidation_factor"]

    def failed(**overrides: Any) -> Json:
        return failure_of(assemble_combustion_factor(request(**overrides), no_oxidation, MAPPING))

    assert failed(**COAL, powerGeneration=True) == not_found(
        "oxidation", **oxidation_criteria("고체", 2, **{"산화계수 부문": "발전부문"})
    )
    assert failed(**COAL, powerGeneration=False) == not_found(
        "oxidation", **oxidation_criteria("고체", 2, **{"산화계수 부문": "기타부문"})
    )
    assert failed(**COAL, tiers=GROUP_A) == not_found("oxidation", **oxidation_criteria("고체", 1))
    assert failed() == not_found("oxidation", **oxidation_criteria("액체", 2))
    assert failed(tiers=TIER1) == not_found("oxidation", **oxidation_criteria("액체", 1))


def test_solid_tier1_needs_no_power_generation() -> None:
    """고체연료라도 Tier 1 이면 발전 여부가 필요 없고 계수에 싣지 않는다."""
    factor = value_of(assemble(**COAL, tiers=GROUP_A)).factor
    assert factor["oxidationFactor"] == "1.0"
    assert "facilityUse" not in factor
    given = value_of(assemble(powerGeneration=True)).factor
    assert "facilityUse" not in given
    assert given["oxidationFactor"] == "0.99"


def test_a_fuel_without_a_mapped_state_needs_the_state() -> None:
    """대응표에 상태가 없는 연료는 상태를 직접 받아야 한다(석탄이니 고체겠지 하고 넘기지 않는다)."""
    without = replace(MAPPING, fuel_states=tuple(e for e in MAPPING.fuel_states if e.fuel != "아역청탄"))
    result = assemble_combustion_factor(request(fuel="아역청탄", powerGeneration=True), RECORDS, without)
    assert failure_of(result) == {
        "kind": "fuel_state_unknown",
        "fuel": "아역청탄",
        "reason": "대응표에 그 연료의 상태(고체·기체·액체)가 없다. 조립 조건의 fuelState 로 직접 준다",
    }


def test_two_mapped_states_for_one_fuel_are_not_chosen() -> None:
    diesel = next(e for e in MAPPING.fuel_states if e.fuel == "경유")
    doubled = replace(MAPPING, fuel_states=(*MAPPING.fuel_states, diesel))
    assert failure_of(assemble_combustion_factor(request(), RECORDS, doubled)) == {
        "kind": "fuel_state_unknown",
        "fuel": "경유",
        "reason": "대응표에 그 연료의 상태가 둘 이상 적혀 있다",
    }


# ── 추정 대응을 탔을 때의 표시 ─────────────────────────────────────────


def test_city_gas_marks_two_assumptions() -> None:
    """도시가스(LNG): 연료 상태와 이름 대응 두 곳이 추정이고 근거와 계수의 출처에 남는다."""
    done = value_of(assemble(fuel="도시가스(LNG)", industry={"sector": "commercial_public"}))
    evidence = done.evidence
    assert [[a["kind"], a["detail"]] for a in evidence["assumptions"]] == [
        ["fuel_state", "도시가스(LNG) → 기체"],
        ["fuel_name", "도시가스(LNG) → 천연가스 (kr-ets-byl10)"],
    ]
    for a in evidence["assumptions"]:
        assert len(a["note"]) > 10
    assert evidence["fuelState"]["basis"] == "assumed"
    ch4 = next(p for p in evidence["parameters"] if p["parameter"] == "CH4")
    assert subset(ch4["nameMapping"], {"domestic": "도시가스(LNG)", "ipcc": "천연가스", "basis": "assumed"})
    assert subset(ch4, {"recordId": "kr-ets-byl10:p2t0r18:CH4:3", "value": "5"})
    # 발열량과 CO2 계수는 별표 12 에 그 이름 그대로 있어 대응표를 타지 않는다.
    assert subset(evidence["parameters"][0], {"recordId": "kr-ets-byl12:hv:p1r20:net", "nameMapping": None})
    assert subset(
        evidence["parameters"][1], {"recordId": "kr-ets-byl12:ef:p3r18:CO2", "value": "56100", "nameMapping": None}
    )
    note = done.factor["source"]["note"]
    assert "추정 대응 2건을 탔다" in note
    assert "도시가스(LNG) → 천연가스 (kr-ets-byl10)" in note
    assert done.factor["calorific"] == {"value": "38.9", "energyUnit": "MJ", "perUnit": "Nm3", "basis": "net"}


def test_all_tier1_keeps_the_table_11_assumption_too() -> None:
    evidence = value_of(assemble(fuel="도시가스(LNG)", tiers=TIER1)).evidence
    assert [a["detail"] for a in evidence["assumptions"]] == [
        "도시가스(LNG) → 기체",
        "도시가스(LNG) → 천연가스 (kr-ets-byl11)",
        "도시가스(LNG) → 천연가스 (kr-ets-byl10)",
    ]


def test_guideline_only_assembly_has_no_assumption_mark() -> None:
    done = value_of(assemble(tiers=TIER1))
    assert done.evidence["assumptions"] == []
    assert "추정" not in done.factor["source"]["note"]


def test_a_given_state_that_disagrees_with_the_mapping_fails() -> None:
    """입력한 연료 상태가 대응표와 다르면 조립하지 않는다(산화계수가 조용히 바뀌지 않는다)."""
    for given in ["기체", "고체"]:
        assert failure_of(assemble(fuelState=given, powerGeneration=False)) == {
            "kind": "fuel_state_conflict",
            "fuel": "경유",
            "given": given,
            "mapped": "액체",
            "basis": "guideline",
            "locator": LIQUID_LOCATOR,
        }
    assert failure_of(assemble(fuel="도시가스(LNG)", fuelState="액체")) == {
        "kind": "fuel_state_conflict",
        "fuel": "도시가스(LNG)",
        "given": "액체",
        "mapped": "기체",
        "basis": "assumed",
        "locator": "PDF 10쪽 「2. 고정연소 (기체연료)」 1. 배출활동 개요",
    }
    assert value_of(assemble(fuelState="액체")).evidence["fuelState"] == {
        "value": "액체",
        "basis": "input",
        "locator": None,
    }


def test_a_given_state_skips_the_mapped_assumption() -> None:
    evidence = value_of(assemble(fuel="도시가스(LNG)", fuelState="기체")).evidence
    assert evidence["fuelState"]["basis"] == "input"
    assert [a["kind"] for a in evidence["assumptions"]] == ["fuel_name"]


# ── 낱줄 없음과 중복 ───────────────────────────────────────────────────


def test_an_unmapped_fuel_name_is_not_replaced_by_a_similar_one() -> None:
    # 별표 12 에는 「도시가스(LPG)」 가 있지만 별표 10 의 국내에너지원 기준에는 없다.
    assert failure_of(assemble(fuel="도시가스(LPG)", fuelState="기체")) == {
        "kind": "fuel_name_not_mapped",
        "fuel": "도시가스(LPG)",
        "table": "kr-ets-byl10",
        "parameter": "CH4",
    }
    # 「LPG」 는 별표 10·11 에 대응이 있지만 별표 12 의 이름은 「프로판(LPG1호)」 다.
    assert failure_of(assemble(fuel="LPG", fuelState="기체")) == not_found("calorific", **calorific_criteria("LPG"))
    assert failure_of(assemble(fuel="synthetic-없는 연료", fuelState="액체")) == not_found(
        "calorific", **calorific_criteria("synthetic-없는 연료")
    )


def test_line_broken_cells_split_as_judged_case_by_case() -> None:
    """줄바꿈 칸의 이름은 건별 판단대로 갈린다: 무연탄 칸은 두 이름, 가스 코크스 칸은 꺾인 한 이름."""

    def names(table: str, ipcc: str) -> tuple[str, ...] | None:
        found = [e for e in MAPPING.fuel_names if e.table == table and e.ipcc_name == ipcc and e.basis == "guideline"]
        return found[0].domestic_names if found else None

    assert names("kr-ets-byl10", "무연탄") == ("국내 무연탄", "수입 무연탄")
    assert names("kr-ets-byl11", "무연탄") == ("국내 무연탄", "수입 무연탄")
    assert names("kr-ets-byl10", "가스 코크스") == ("가스공장 코크스",)
    # 칸의 글자 그대로(띄어쓰기 있음)는 지침의 대응이다.
    # 별표 12 의 「국내무연탄」(띄어쓰기 없음)은 따로 추정 대응을 탄다.
    direct = value_of(assemble(fuel="국내 무연탄", fuelState="고체", tiers=TIER1))
    co2 = next(p for p in direct.evidence["parameters"] if p["parameter"] == "CO2")
    assert subset(co2["nameMapping"], {"ipcc": "무연탄", "basis": "guideline"})
    assert direct.evidence["assumptions"] == []
    # 「가스공장」 이나 「코크스」 만으로는 가스 코크스가 되지 않는다(두 이름으로 가르지 않았다).
    byl10 = [e for e in MAPPING.fuel_names if e.table == "kr-ets-byl10"]
    assert [e for e in byl10 if "가스공장" in e.domestic_names] == []
    assert [e.ipcc_name for e in byl10 if "코크스" in e.domestic_names] == ["코크스로 코크스"]


def test_a_missing_row_is_record_not_found_with_what_was_sought() -> None:
    without = [r for r in RECORDS if r.id != "kr-ets-byl10:p1t0r12:N2O:5"]
    assert failure_of(assemble_combustion_factor(request(), without, MAPPING)) == {
        "kind": "record_not_found",
        "parameter": "N2O",
        "criteria": {
            "source": "kr-ets-byl10",
            "record_type": "emission_factor",
            "gas": "N2O",
            "gas_basis": "gas_mass",
            "name": "가스/디젤 오일",
            "부문": "에너지산업제조업건설업",
        },
    }
    no_ch4 = [r for r in RECORDS if r.id != "kr-ets-byl10:p1t0r12:CH4:2"]
    assert failure_of(assemble_combustion_factor(request(), no_ch4, MAPPING)) == {
        "kind": "record_not_found",
        "parameter": "CH4",
        "criteria": {
            "source": "kr-ets-byl10",
            "record_type": "emission_factor",
            "gas": "CH4",
            "gas_basis": "gas_mass",
            "name": "가스/디젤 오일",
            "부문": "제조업건설업",
        },
    }
    no_oxidation = [r for r in RECORDS if r.record_type != "oxidation_factor"]
    assert failure_of(assemble_combustion_factor(request(), no_oxidation, MAPPING)) == not_found(
        "oxidation", **oxidation_criteria("액체", 2)
    )


def test_two_rows_for_the_same_condition_are_ambiguous() -> None:
    """같은 조건의 낱줄이 둘이면 record_ambiguous 다(앞의 것을 집지 않는다)."""
    twin = synthetic(by_id(CO2_ID), id="synthetic:kr-ets-byl12:ef:dup", value_raw="70,000")
    assert failure_of(assemble_combustion_factor(request(), [*RECORDS, twin], MAPPING)) == {
        "kind": "record_ambiguous",
        "parameter": "CO2",
        "criteria": co2_criteria("경유"),
        "recordIds": [CO2_ID, "synthetic:kr-ets-byl12:ef:dup"],
    }


def test_carbon_basis_and_gross_calorific_rows_are_not_picked() -> None:
    """탄소 기준 계수(kgC/TJ)나 총발열량을 CO2 계수·발열량으로 집지 않는다."""
    evidence = value_of(assemble()).evidence
    assert by_id(evidence["parameters"][1]["recordId"]).gas_basis == "gas_mass"
    assert by_id(evidence["parameters"][0]["recordId"]).heating_value_basis == "net"
    no_net = [r for r in RECORDS if r.id != HV_ID]
    assert failure_of(assemble_combustion_factor(request(), no_net, MAPPING)) == not_found(
        "calorific", **calorific_criteria("경유")
    )
    no_co2 = [r for r in RECORDS if r.id != CO2_ID]
    assert failure_of(assemble_combustion_factor(request(), no_co2, MAPPING)) == not_found(
        "CO2", **co2_criteria("경유")
    )
    # Tier 1 은 별표 11·10 의 IPCC 이름으로 찾는다
    no_ipcc_hv = [r for r in RECORDS if r.id != "kr-ets-byl11:p1t0r11"]
    assert failure_of(assemble_combustion_factor(request(tiers=TIER1), no_ipcc_hv, MAPPING)) == not_found(
        "calorific", **calorific_criteria("가스/디젤 오일", "kr-ets-byl11")
    )
    no_ipcc_co2 = [r for r in RECORDS if r.id != "kr-ets-byl10:p1t0r12:CO2:0"]
    assert failure_of(assemble_combustion_factor(request(tiers=TIER1), no_ipcc_co2, MAPPING)) == not_found(
        "CO2", **co2_criteria("가스/디젤 오일", "kr-ets-byl10")
    )


def test_empty_value_other_edition_and_unknown_unit_fail() -> None:
    """값이 비어 있는 낱줄, 다른 고시 판의 낱줄, 모르는 단위의 낱줄은 실패다."""

    def failed(records: list[Any]) -> Json:
        return failure_of(assemble_combustion_factor(request(), records, MAPPING))

    assert failed(swap(CO2_ID, value_raw="-", value_status="not_available_in_source")) == {
        "kind": "record_value_missing",
        "parameter": "CO2",
        "recordId": CO2_ID,
        "valueStatus": "not_available_in_source",
    }
    # 다른 고시 판: 매개변수 다섯 자리마다
    for record_id in [HV_ID, CO2_ID, "kr-ets-byl10:p1t0r12:CH4:2", "kr-ets-byl10:p1t0r12:N2O:5", OX_ID]:
        old = with_version(by_id(record_id).source, "synthetic 옛 고시")
        assert failed(swap(record_id, source=old)) == {
            "kind": "guideline_version_mismatch",
            "recordId": record_id,
            "recordVersion": "synthetic 옛 고시",
            "guidelineVersion": "환경부고시 제2025-64호 (2025-04-11 시행)",
        }
    assert failed(swap(CO2_ID, unit_numerator="tCO2")) == {
        "kind": "unit_notation_unknown",
        "parameter": "CO2",
        "recordId": CO2_ID,
        "unit": "tCO2/TJ",
    }
    # 발열량: 분모(사용량 단위)를 모름 / 분자(에너지 단위)를 모름
    for patch, unit in [({"unit_denominator": "gal"}, "MJ/gal"), ({"unit_numerator": "kcal"}, "kcal/L")]:
        assert failed(swap(HV_ID, **patch)) == {
            "kind": "unit_notation_unknown",
            "parameter": "calorific",
            "recordId": HV_ID,
            "unit": unit,
        }
    # 산화계수가 무차원이 아닌 가상 낱줄: unit 에는 분자만 싣는다
    assert failed(swap(OX_ID, unit_numerator="%")) == {
        "kind": "unit_notation_unknown",
        "parameter": "oxidation",
        "recordId": OX_ID,
        "unit": "%",
    }


# ── 입력 누락과 틀린 입력 ──────────────────────────────────────────────


def raw(**patch: Any) -> Json:
    return failure_of(assemble_combustion_factor({**request(), **patch}, RECORDS, MAPPING))


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("fuel", "국내 연료명이 없다"),
        ("combustionType", "연소 유형이 없다 (기본값 없음)"),
        ("industry", "사업장의 부문도 업종 코드도 없다 (기본값 없음)"),
        ("tiers", "적용할 산정등급을 정하지 않았다 (기본값 없음)"),
    ],
)
def test_a_missing_field_is_named(field: str, reason: str) -> None:
    """빠지면 조립하지 않고 빠진 것을 알려 준다."""
    copy = request()
    del copy[field]
    failure = failure_of(assemble_combustion_factor(copy, RECORDS, MAPPING))
    assert failure == missing(field, reason)


def test_a_request_that_is_not_an_object_is_missing() -> None:
    not_objects: list[object] = [None, [], "경유"]
    for given in not_objects:
        assert failure_of(assemble_combustion_factor(given, RECORDS, MAPPING)) == missing("request", "조립 조건이 없다")


def test_tiers_or_industry_that_are_not_objects_are_missing() -> None:
    """None 이 아니어서 조립의 첫 검사를 지나도, 객체가 아니면 정책·부문 쪽에서 빠진 것으로 본다."""
    for tiers in ["T2", [2, 2, 2]]:
        assert raw(tiers=tiers) == missing("tiers", "적용할 산정등급을 정하지 않았다 (기본값 없음)")
    assert raw(industry="제조업") == missing("industry", "사업장의 부문도 업종 코드도 없다 (기본값 없음)")


def test_partial_tiers_are_not_filled_in() -> None:
    """산정등급의 일부만 주면 나머지를 채우지 않는다."""
    partial = "매개변수별 산정등급이 빠졌다 (기본값 없음)"
    assert raw(tiers={"kind": "explicit", "calorific": 2, "co2": 2}) == missing("tiers.oxidation", partial)
    assert raw(tiers={"kind": "explicit", "co2": 2, "oxidation": 2}) == missing("tiers.calorific", partial)
    assert raw(tiers={"kind": "group_minimum"}) == missing(
        "tiers.group", "시설 규모 그룹(A·B·C)이 빠졌다 (기본값 없음)"
    )
    assert raw(tiers={}) == missing(
        "tiers.kind", "산정등급을 직접 줄지(explicit) 그룹 최소기준을 따를지(group_minimum) 정하지 않았다"
    )
    assert raw(industry={}) == missing("industry", "사업장의 부문도 업종 코드도 없다 (기본값 없음)")
    assert raw(fuel="") == missing("fuel", "국내 연료명이 없다")


def test_wrong_values() -> None:
    assert raw(tiers={"kind": "explicit", "calorific": 2, "co2": 2, "oxidation": "2"}) == invalid(
        "tiers.oxidation", "2", TIER_REASON
    )
    assert raw(tiers={"kind": "explicit", "calorific": True, "co2": 2, "oxidation": 2}) == invalid(
        "tiers.calorific", "true", TIER_REASON
    )
    assert raw(tiers={"kind": "group_minimum", "group": "D"}) == invalid(
        "tiers.group", "D", "시설 규모 그룹은 A, B, C 중 하나다"
    )
    assert raw(tiers={"kind": "tier2"}) == invalid("tiers.kind", "tier2", "explicit 또는 group_minimum")
    sector_keys = (
        "부문 키는 energy_industries, manufacturing_construction, commercial_public, residential_other 중 하나다"
    )
    assert raw(industry={"sector": "manufacturing"}) == invalid("industry.sector", "manufacturing", sector_keys)
    assert raw(industry={"sector": 3}) == invalid("industry.sector", "3", sector_keys)
    ksic = "한국표준산업분류 코드는 숫자 2~5자리 문자열이다 (앞 두 자리가 중분류)"
    assert raw(industry={"ksicCode": 20}) == invalid("industry.ksicCode", "20", ksic)
    assert raw(industry={"ksicCode": "C20"}) == invalid("industry.ksicCode", "C20", ksic)
    assert raw(industry={"sector": "commercial_public", "ksicCode": "20"}) == invalid(
        "industry", "commercial_public + 20", "부문과 업종 코드 가운데 하나만 준다"
    )
    assert raw(fuelState="liquid") == invalid("fuelState", "liquid", "고체, 기체, 액체 중 하나다")
    assert raw(powerGeneration="yes") == invalid("powerGeneration", "yes", "true 또는 false")
    assert raw(combustionType="mobile") == {"kind": "unsupported_combustion_type", "combustionType": "mobile"}


def test_tier_combinations_the_guideline_forbids() -> None:
    # 산화계수는 CO2 배출계수와 같은 등급이어야 한다(별표 6).
    for co2, oxidation in [(2, 1), (1, 2)]:
        assert raw(tiers={"kind": "explicit", "calorific": 2, "co2": co2, "oxidation": oxidation}) == {
            "kind": "tier_combination_invalid",
            "reason": f"CO2 배출계수는 Tier {co2} 인데 산화계수는 Tier {oxidation} 이다",
            "locator": OXIDATION_FOLLOWS_CO2,
        }
    # CH4·N2O 는 Tier 1 뿐이다(True 는 1 이 아니다)
    for non_co2, text in [(2, "2"), (True, "true")]:
        assert raw(tiers={"kind": "explicit", "calorific": 2, "co2": 2, "oxidation": 2, "nonCo2": non_co2}) == {
            "kind": "tier_combination_invalid",
            "reason": f"CH4·N2O 에 Tier {text} 은 없다",
            "locator": NON_CO2_TIER_ONE,
        }


def test_non_co2_tier_1_given_explicitly_is_accepted() -> None:
    done = value_of(assemble(tiers={"kind": "explicit", "calorific": 2, "co2": 2, "oxidation": 2, "nonCo2": 1}))
    assert done.factor["parameterTiers"] == {"calorific": 2, "co2": 2, "nonCo2": 1, "oxidation": 2}


def test_tier_3_and_4_need_site_values() -> None:
    """Tier 3·4 는 사업장의 값이 있어야 해서 고시의 표로는 조립하지 않는다(C 그룹 최소기준 포함)."""
    for tiers, parameter, tier in [
        ({"kind": "group_minimum", "group": "C"}, "발열량", 3),
        ({"kind": "explicit", "calorific": 2, "co2": 3, "oxidation": 3}, "CO2 배출계수", 3),
        ({"kind": "explicit", "calorific": 4, "co2": 2, "oxidation": 2}, "발열량", 4),
    ]:
        assert raw(tiers=tiers) == {
            "kind": "tier_requires_site_values",
            "parameter": parameter,
            "tier": tier,
            "reason": SITE_VALUES,
        }


def test_a_missing_group_minimum_fails() -> None:
    thin = replace(MAPPING, tier_minimums=tuple(e for e in MAPPING.tier_minimums if e.parameter != "배출계수"))
    assert failure_of(assemble_combustion_factor(request(tiers=GROUP_A), RECORDS, thin)) == {
        "kind": "tier_minimum_not_found",
        "fuelState": "액체",
        "group": "A",
        "parameter": "배출계수",
        "found": 0,
    }


# ── 십진 정확도: value_raw 에서만 읽는다 ───────────────────────────────


def test_values_come_from_value_raw_with_only_commas_removed() -> None:
    done = value_of(assemble())
    for p in done.evidence["parameters"]:
        assert p["valueRaw"] == by_id(p["recordId"]).value_raw
        assert p["value"] == p["valueRaw"].replace(",", "")
    factor = done.factor
    assert [e["value"] for e in factor["emissionFactors"]] == ["73200", "3", "0.6"]
    texts = [factor["calorific"]["value"], factor["oxidationFactor"], *(e["value"] for e in factor["emissionFactors"])]
    assert all(isinstance(text, str) for text in texts)


def test_a_value_a_float_would_break_is_carried_as_text() -> None:
    precise = swap(CO2_ID, value_raw="73,200.10000000000000000001")
    factor = value_of(assemble_combustion_factor(request(), precise, MAPPING)).factor
    assert factor["emissionFactors"][0]["value"] == "73200.10000000000000000001"


@pytest.mark.parametrize(
    "value_raw", ["7.32e4", "73 200", "73,20", "1,2", "+73200", "73200 kg", "", "-", "-73,200", "７３２００"]
)
def test_odd_notation_fails(value_raw: str) -> None:
    odd = swap(CO2_ID, value_raw=value_raw)
    assert failure_of(assemble_combustion_factor(request(), odd, MAPPING)) == {
        "kind": "invalid_value_raw",
        "parameter": "CO2",
        "recordId": CO2_ID,
        "valueRaw": value_raw,
    }
