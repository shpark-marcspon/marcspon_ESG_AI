"""조립: 조립 조건에 맞는 낱줄을 계수 표에서 하나씩 골라 엔진의 연소 계수 한 건으로 묶는다.

순수 함수다. 파일도 DB 도 읽지 않고(낱줄은 selectors 가 넘긴다), 수치를 만들지 않는다
(값은 전부 낱줄의 value_raw 에서 온다).
낱줄이 없거나 둘 이상이면 실패다. 비슷한 연료나 다른 부문·등급의 낱줄로 대신하지 않는다.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.reference.calc.policy import RULES, resolve_tiers
from esgapi.reference.calc.sector import resolve_sector
from esgapi.reference.calc.types import (
    Assembled,
    AssemblyMapping,
    AssemblyResult,
    FactorRecord,
    Failed,
    FuelState,
    Json,
    Ok,
    Step,
    fail,
    text_of,
)
from esgapi.reference.calc.value_raw import read_value_raw

# 지침의 별표가 계수 표에서 갖는 출처 id.
SOURCE_IDS: Final = {
    "oxidation": "kr-ets-byl06",
    "ipccFactors": "kr-ets-byl10",
    "ipccCalorific": "kr-ets-byl11",
    "national": "kr-ets-byl12",
}

# 매개변수와 등급마다 어느 별표에서 값을 가져오는지(별표 6 고정연소 각 절 「5. 매개변수별 관리기준」, 본문 제15조).
_RULE_CALORIFIC: Final = {
    1: "② 열량계수 Tier 1: 별표 11 의 IPCC 기본 발열량 (순발열량)",
    2: "② 열량계수 Tier 2: 별표 12 의 국가 고유 발열량 (순발열량)",
}
_RULE_CO2: Final = {
    1: "③ 배출계수 Tier 1: 별표 10 의 IPCC 기본 배출계수",
    2: "③ 배출계수 Tier 2: 제15조제2항의 국가 고유 배출계수 (별표 12)",
}
_RULE_NON_CO2: Final = "③ 배출계수 Tier 1: 별표 10 의 IPCC 기본 배출계수 (부문별). CH4·N2O 는 Tier 1 뿐이다"
_RULE_OXIDATION: Final = "④ 산화계수: 별표 6 의 그 연료 상태 절에 적힌 값"

_STATES: Final[tuple[str, ...]] = ("고체", "기체", "액체")

# 원문의 단위 표기 → 엔진의 단위 기호. 표에 없는 표기는 실패다(추측해 읽지 않는다).
_CALORIFIC_PER_UNIT: Final = {"L": "L", "kg": "kg", "N㎥": "Nm3", "Gg": "Gg"}
_ENERGY_UNITS: Final[tuple[str, ...]] = ("MJ", "TJ")


@dataclass(frozen=True)
class _NameUse:
    """낱줄을 찾은 이름과, 대응표로 바꿨다면 그 대응."""

    name: str
    mapping: Json | None


@dataclass(frozen=True)
class _Picked:
    record: FactorRecord
    value: str
    evidence: Json


def _unit(record: FactorRecord) -> str:
    return f"{record.unit_numerator}/{record.unit_denominator}"


def _pick_one(
    parameter: str,
    tier: int,
    rule: str,
    records: Sequence[FactorRecord],
    criteria: dict[str, str],
    matches: Callable[[FactorRecord], bool],
    name: _NameUse,
    guideline_version: str,
) -> Step[_Picked]:
    """조건에 맞는 낱줄을 정확히 하나 고르고 값을 십진 문자열로 읽는다."""
    found = [record for record in records if matches(record)]
    if not found:
        return fail("record_not_found", parameter=parameter, criteria=criteria)
    if len(found) > 1:
        return fail("record_ambiguous", parameter=parameter, criteria=criteria, recordIds=[r.id for r in found])
    record = found[0]
    if record.source.version != guideline_version:
        return fail(
            "guideline_version_mismatch",
            recordId=record.id,
            recordVersion=record.source.version,
            guidelineVersion=guideline_version,
        )
    if record.value_status != "ok" or record.value_raw is None:
        return fail("record_value_missing", parameter=parameter, recordId=record.id, valueStatus=record.value_status)
    value = read_value_raw(record.value_raw)
    if value is None:
        return fail("invalid_value_raw", parameter=parameter, recordId=record.id, valueRaw=record.value_raw)
    evidence: Json = {
        "parameter": parameter,
        "tier": tier,
        "rule": rule,
        "recordId": record.id,
        "sourceId": record.source.id,
        "sourceName": record.source.name,
        "url": record.source.url,
        "retrieved": record.source.retrieved,
        "fileSha256": record.source.file_sha256,
        "locator": record.source.locator,
        "nameUsed": name.name,
        "nameMapping": name.mapping,
        "valueRaw": record.value_raw,
        "value": value,
        "unit": _unit(record),
        "conditions": dict(record.conditions),
    }
    return Ok(_Picked(record=record, value=value, evidence=evidence))


def _note_assumption(assumptions: list[Json], detail: str, note: str | None, locator: str) -> None:
    if not any(a["kind"] == "fuel_name" and a["detail"] == detail for a in assumptions):
        assumptions.append({"kind": "fuel_name", "detail": detail, "note": note or "", "locator": locator})


def _ipcc_name(
    fuel: str, table: str, parameter: str, mapping: AssemblyMapping, assumptions: list[Json]
) -> Step[_NameUse]:
    """국내 연료명을 별표 10·11 의 IPCC 연료명으로 바꾼다. 대응이 없거나 둘이면 실패다.

    대응표 항목에 `parameters` 가 있으면 그 매개변수에만 쓴다(부생연료 1·2호는 CO2 만 등유·B-C유 계수를 쓴다.
    CH4·N2O 는 대응이 없어 실패한다).
    """
    found = [
        entry
        for entry in mapping.fuel_names
        if entry.table == table
        and fuel in entry.domestic_names
        and (entry.parameters is None or parameter in entry.parameters)
    ]
    if not found:
        return fail("fuel_name_not_mapped", fuel=fuel, table=table, parameter=parameter)
    if len(found) > 1:
        return fail("fuel_name_ambiguous", fuel=fuel, table=table, ipccNames=[e.ipcc_name for e in found])
    entry = found[0]
    if entry.basis == "assumed":
        only = "" if entry.parameters is None else f", {'·'.join(entry.parameters)} 만"
        _note_assumption(assumptions, f"{fuel} → {entry.ipcc_name} ({table}{only})", entry.note, entry.locator)
    used = {"domestic": fuel, "ipcc": entry.ipcc_name, "basis": entry.basis, "locator": entry.locator}
    return Ok(_NameUse(entry.ipcc_name, used))


def _national_ef_name(fuel: str, mapping: AssemblyMapping, assumptions: list[Json]) -> Step[_NameUse]:
    """별표 12 배출계수 표에서 찾을 이름. 발열량 표와 이름이 다른 연료만 대응표에 있고, 없으면 그 이름 그대로다."""
    national = SOURCE_IDS["national"]
    found = [entry for entry in mapping.national_ef_names if entry.fuel == fuel]
    if not found:
        return Ok(_NameUse(fuel, None))
    if len(found) > 1:
        return fail("fuel_name_ambiguous", fuel=fuel, table=national, ipccNames=[e.ef_name for e in found])
    entry = found[0]
    if entry.basis == "assumed":
        _note_assumption(assumptions, f"{fuel} → {entry.ef_name} ({national} 배출계수 표)", entry.note, entry.locator)
    used = {
        "domestic": fuel,
        "ipcc": entry.ef_name,
        "basis": entry.basis,
        "locator": entry.locator,
        "table": national,
    }
    return Ok(_NameUse(entry.ef_name, used))


def _fuel_state_of(fuel: str, given: object, mapping: AssemblyMapping, assumptions: list[Json]) -> Step[Json]:
    """연료 상태와 그 근거: {value, basis: guideline | assumed | input, locator}."""
    if given is not None and (not isinstance(given, str) or given not in _STATES):
        return fail("invalid_input", field="fuelState", value=text_of(given), reason="고체, 기체, 액체 중 하나다")
    found = [entry for entry in mapping.fuel_states if entry.fuel == fuel]
    if given is not None:
        # 입력이 대응표와 어긋나면 어느 쪽도 고르지 않는다(경유를 기체로 넣어 산화계수가 바뀌는 일을 막는다).
        clash = next((item for item in found if item.state != given), None)
        if clash is not None:
            return fail(
                "fuel_state_conflict",
                fuel=fuel,
                given=given,
                mapped=clash.state,
                basis=clash.basis,
                locator=clash.locator,
            )
        return Ok({"value": given, "basis": "input", "locator": None})
    if len(found) != 1:
        reason = (
            "대응표에 그 연료의 상태가 둘 이상 적혀 있다"
            if len(found) > 1
            else "대응표에 그 연료의 상태(고체·기체·액체)가 없다. 조립 조건의 fuelState 로 직접 준다"
        )
        return fail("fuel_state_unknown", fuel=fuel, reason=reason)
    entry = found[0]
    if entry.basis == "assumed":
        assumptions.append(
            {
                "kind": "fuel_state",
                "detail": f"{entry.fuel} → {entry.state}",
                "note": entry.note or "",
                "locator": entry.locator,
            }
        )
    return Ok({"value": entry.state, "basis": entry.basis, "locator": entry.locator})


def _tier_label(tiers: Mapping[str, int]) -> str:
    return (
        f"발열량 Tier {tiers['calorific']}, CO2 계수 Tier {tiers['co2']}, "
        f"CH4·N2O 계수 Tier {tiers['nonCo2']}, 산화계수 Tier {tiers['oxidation']}"
    )


def assemble_combustion_factor(
    request: object, records: Sequence[FactorRecord], mapping: AssemblyMapping
) -> AssemblyResult:
    """계수 낱줄 묶음과 대응표, 조립 조건으로 고정연소 계수 한 건을 조립한다.

    request 는 JSON 을 푼 dict 다:
      fuel             국내 연료명(별표 12 의 이름)
      combustionType   "stationary" 만
      industry         {sector} 또는 {ksicCode}
      tiers            {kind: "explicit", calorific, co2, oxidation} 또는 {kind: "group_minimum", group}
      fuelState?       대응표에 그 연료의 상태가 없을 때만. 대응표와 다른 상태를 주면 실패다
      powerGeneration? 고체연료에 Tier 2 산화계수를 쓸 때만(발전 0.99 대 그 밖 0.98)
    전부 고객사나 사업장 설정에서 오는 입력이다. 기본값이 없다: 빠졌거나 낱줄을 하나로 정할 수 없으면 계수를 내놓지
    않고 무엇이 문제인지를 돌려준다. 값이 None 인 칸은 빠진 칸으로 본다.
    """
    if not isinstance(request, Mapping):
        return fail("missing_input", field="request", reason="조립 조건이 없다")
    req = cast(Mapping[str, Any], request)
    fuel: object = req.get("fuel")
    if not isinstance(fuel, str) or fuel == "":
        return fail("missing_input", field="fuel", reason="국내 연료명이 없다")
    combustion_type: object = req.get("combustionType")
    if combustion_type is None:
        return fail("missing_input", field="combustionType", reason="연소 유형이 없다 (기본값 없음)")
    if combustion_type != "stationary":
        return fail("unsupported_combustion_type", combustionType=text_of(combustion_type))
    if req.get("industry") is None:
        return fail("missing_input", field="industry", reason="사업장의 부문도 업종 코드도 없다 (기본값 없음)")
    if req.get("tiers") is None:
        return fail("missing_input", field="tiers", reason="적용할 산정등급을 정하지 않았다 (기본값 없음)")
    power_generation: object = req.get("powerGeneration")
    if power_generation is not None and not isinstance(power_generation, bool):
        return fail("invalid_input", field="powerGeneration", value=text_of(power_generation), reason="true 또는 false")

    version = mapping.guideline.version
    assumptions: list[Json] = []

    state = _fuel_state_of(fuel, req.get("fuelState"), mapping, assumptions)
    if isinstance(state, Failed):
        return state
    fuel_state = cast(FuelState, state.value["value"])
    tiers = resolve_tiers(req["tiers"], fuel_state, mapping)
    if isinstance(tiers, Failed):
        return tiers
    sector = resolve_sector(req["industry"], mapping)
    if isinstance(sector, Failed):
        return sector
    t = tiers.value.values
    oxidation_tier = t["oxidation"]

    # 고체연료의 Tier 2 산화계수만 발전과 그 밖으로 갈린다. 그때 발전 여부가 없으면 어느 쪽인지 고르지 않는다.
    needs_facility_use = fuel_state == "고체" and oxidation_tier == 2
    if needs_facility_use and power_generation is None:
        return fail(
            "missing_input",
            field="powerGeneration",
            reason="고체연료의 Tier 2 산화계수는 발전부문과 기타부문이 다르다. 발전 여부가 필요하다 (기본값 없음)",
        )
    oxidation_sector = ("발전부문" if power_generation is True else "기타부문") if needs_facility_use else None

    direct = _NameUse(fuel, None)
    national = SOURCE_IDS["national"]
    ipcc_factors = SOURCE_IDS["ipccFactors"]

    # 발열량(배출량 산정에는 순발열량: 본문 제2조 24호, 별표 12 비고 2)
    calorific_name = direct
    if t["calorific"] == 1:
        mapped = _ipcc_name(fuel, SOURCE_IDS["ipccCalorific"], "calorific", mapping, assumptions)
        if isinstance(mapped, Failed):
            return mapped
        calorific_name = mapped.value
    calorific_source = SOURCE_IDS["ipccCalorific"] if t["calorific"] == 1 else national
    hv_name = calorific_name.name
    calorific = _pick_one(
        "calorific",
        t["calorific"],
        _RULE_CALORIFIC[t["calorific"]],
        records,
        {"source": calorific_source, "record_type": "heating_value", "heating_value_basis": "net", "name": hv_name},
        lambda r: (
            r.source.id == calorific_source
            and r.record_type == "heating_value"
            and r.heating_value_basis == "net"
            and r.name_original == hv_name
        ),
        calorific_name,
        version,
    )
    if isinstance(calorific, Failed):
        return calorific
    energy_unit = calorific.value.record.unit_numerator
    per_unit = _CALORIFIC_PER_UNIT.get(calorific.value.record.unit_denominator)
    if energy_unit not in _ENERGY_UNITS or per_unit is None:
        return fail(
            "unit_notation_unknown",
            parameter="calorific",
            recordId=calorific.value.record.id,
            unit=_unit(calorific.value.record),
        )

    # CO2 배출계수(Tier 2 는 별표 12 배출계수 표의 이름, Tier 1 은 별표 10 의 IPCC 이름)
    co2_mapped = (
        _ipcc_name(fuel, ipcc_factors, "CO2", mapping, assumptions)
        if t["co2"] == 1
        else _national_ef_name(fuel, mapping, assumptions)
    )
    if isinstance(co2_mapped, Failed):
        return co2_mapped
    co2_name = co2_mapped.value
    co2_source = ipcc_factors if t["co2"] == 1 else national
    co2 = _pick_one(
        "CO2",
        t["co2"],
        _RULE_CO2[t["co2"]],
        records,
        {
            "source": co2_source,
            "record_type": "emission_factor",
            "gas": "CO2",
            "gas_basis": "gas_mass",
            "name": co2_name.name,
        },
        lambda r: (
            r.source.id == co2_source
            and r.record_type == "emission_factor"
            and r.gas == "CO2"
            and r.gas_basis == "gas_mass"
            and r.name_original == co2_name.name
        ),
        co2_name,
        version,
    )
    if isinstance(co2, Failed):
        return co2

    # CH4·N2O 배출계수: 항상 별표 10 의 부문별 값.
    # 이름은 매개변수마다 따로 찾는다(대응이 일부 매개변수에만 있을 수 있다).
    non_co2: list[_Picked] = []
    for gas, condition in (("CH4", sector.value.entry.ch4_condition), ("N2O", sector.value.entry.n2o_condition)):
        mapped = _ipcc_name(fuel, ipcc_factors, gas, mapping, assumptions)
        if isinstance(mapped, Failed):
            return mapped
        name = mapped.value

        def matches(r: FactorRecord, gas: str = gas, condition: str = condition, name: _NameUse = name) -> bool:
            return (
                r.source.id == ipcc_factors
                and r.record_type == "emission_factor"
                and r.gas == gas
                and r.gas_basis == "gas_mass"
                and r.name_original == name.name
                and r.conditions.get("부문") == condition
            )

        picked = _pick_one(
            gas,
            1,
            _RULE_NON_CO2,
            records,
            {
                "source": ipcc_factors,
                "record_type": "emission_factor",
                "gas": gas,
                "gas_basis": "gas_mass",
                "name": name.name,
                "부문": condition,
            },
            matches,
            name,
            version,
        )
        if isinstance(picked, Failed):
            return picked
        non_co2.append(picked.value)

    # 산화계수
    oxidation_source = SOURCE_IDS["oxidation"]
    tier_text = f"Tier {oxidation_tier}"
    oxidation_criteria: dict[str, str] = {
        "source": oxidation_source,
        "record_type": "oxidation_factor",
        "연료 상태": fuel_state,
        "산정등급": tier_text,
    }
    if oxidation_sector is not None:
        oxidation_criteria["산화계수 부문"] = oxidation_sector
    oxidation = _pick_one(
        "oxidation",
        oxidation_tier,
        _RULE_OXIDATION,
        records,
        oxidation_criteria,
        lambda r: (
            r.source.id == oxidation_source
            and r.record_type == "oxidation_factor"
            and r.conditions.get("연료 상태") == fuel_state
            and r.conditions.get("산정등급") == tier_text
            # 발전 여부로 가르지 않는 자리에서는 부문 조건이 붙은 낱줄을 집지 않는다.
            and r.conditions.get("산화계수 부문") == oxidation_sector
        ),
        _NameUse(f"고정연소 ({fuel_state}연료)", None),
        version,
    )
    if isinstance(oxidation, Failed):
        return oxidation
    if oxidation.value.record.unit_numerator != "무차원":
        return fail(
            "unit_notation_unknown",
            parameter="oxidation",
            recordId=oxidation.value.record.id,
            unit=oxidation.value.record.unit_numerator,
        )

    emission_factors: list[Json] = []
    for picked_gas in (co2.value, *non_co2):
        record = picked_gas.record
        # 별표 10·12 의 배출계수 단위는 kg<기체>/TJ 다.
        if record.unit_numerator != f"kg{record.gas}" or record.unit_denominator != "TJ":
            return fail(
                "unit_notation_unknown",
                parameter=picked_gas.evidence["parameter"],
                recordId=record.id,
                unit=_unit(record),
            )
        emission_factors.append({"gas": record.gas, "value": picked_gas.value, "massUnit": "kg", "perEnergyUnit": "TJ"})

    parameters = [p.evidence for p in (calorific.value, co2.value, *non_co2, oxidation.value)]
    retrieved = max(p["retrieved"] for p in parameters)
    details = [a["detail"] for a in assumptions]
    assumed_note = (
        "" if not assumptions else f" 추정 대응 {len(assumptions)}건을 탔다 (지침에 없는 대응): {'; '.join(details)}."
    )
    tier_basis = f"{tiers.value.group} 그룹 최소기준" if tiers.value.basis == "group_minimum" else "직접 지정"
    cited = ", ".join(f"{p['parameter']} {p['valueRaw']} {p['unit']} ← {p['recordId']}" for p in parameters)
    source: Json = {
        "kind": "cited",
        "title": f"{mapping.guideline.name} ({version}): {cited}",
        "url": mapping.guideline.url,
        "checkedOn": retrieved,
        "locator": " | ".join(f"{p['sourceId']} {p['locator']}" for p in parameters),
        "note": (
            f"계수 조합기가 계수 표의 낱줄에서 조립했다. {_tier_label(t)} ({tier_basis}), "
            f"부문 {sector.value.entry.label}.{assumed_note}"
        ),
    }

    sector_key = sector.value.entry.key
    tier_tag = f"cv{t['calorific']}_co2ef{t['co2']}_ch4n2o{t['nonCo2']}_ox{oxidation_tier}"
    id_parts = ["kr-ets", "stationary", fuel, sector_key, tier_tag]
    if oxidation_sector is not None:
        id_parts.append("power" if power_generation is True else "other")

    factor: Json = {
        "kind": "combustion",
        "id": ":".join(id_parts),
        "version": version,
        "source": source,
        "fuel": fuel,
        "combustionType": "stationary",
        "sector": sector_key,
        "parameterTiers": dict(t),
    }
    if oxidation_sector is not None:
        factor["facilityUse"] = "power_generation" if power_generation is True else "other"
    factor["calorific"] = {
        "value": calorific.value.value,
        "energyUnit": energy_unit,
        "perUnit": per_unit,
        "basis": "net",
    }
    factor["emissionFactors"] = emission_factors
    factor["oxidationFactor"] = oxidation.value.value

    evidence: Json = {
        "guideline": {"name": mapping.guideline.name, "version": version, "url": mapping.guideline.url},
        "fuelState": state.value,
        "sector": sector.value.evidence,
        "tiers": {
            "values": dict(t),
            "basis": tiers.value.basis,
            "group": tiers.value.group,
            # 그룹 최소기준에서 왔을 때 별표 5 의 자리. CH4·N2O 의 Tier 1 과 산화계수 규칙은 별표 6 의 자리.
            "locators": [*tiers.value.locators, RULES["oxidationFollowsCo2"]],
        },
        "parameters": parameters,
        "assumptions": assumptions,
    }
    return Ok(Assembled(factor=factor, evidence=evidence))


def national_calorific_fuels(records: Sequence[FactorRecord]) -> list[str]:
    """별표 12 순발열량 표에 있는 연료의 이름(조립 조건의 `fuel` 에 올 수 있는 것)."""
    return [
        r.name_original
        for r in records
        if r.source.id == SOURCE_IDS["national"] and r.record_type == "heating_value" and r.heating_value_basis == "net"
    ]
