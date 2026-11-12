"""dataclass → JSON 으로 나갈 dict. 키의 이름(camelCase)과 순서가 esg-lab 의 TS 엔진이 내던 것과 같다(골든이 잰다).

규칙:
  - 「없음」이 값인 칸은 null 로 나간다: energy, gwp,
    evidence 의 calorificBasis·oxidationFactor·sector·parameterTiers·facilityUse.
  - 선택 칸은 없으면 키를 뺀다: 출처의 locator·note, 단계의 conversion, 계수의 oxidationFactor·year·sector 등.
"""

from esgapi.inventory.engines.scope12.engine_1.aggregate import Aggregation, Group, Totals
from esgapi.inventory.engines.scope12.engine_1.provenance import Cited, Provenance
from esgapi.inventory.engines.scope12.engine_1.types import (
    CombustionFactor,
    Evidence,
    Factor,
    Failure,
    GasResult,
    GwpSet,
    ParameterTiers,
    ReferenceTables,
    RowOk,
    RowResult,
    Step,
    UnitConversion,
)

type Json = dict[str, object]


def provenance_to_dict(source: Provenance) -> Json:
    if isinstance(source, Cited):
        out: Json = {"kind": source.kind, "title": source.title, "url": source.url, "checkedOn": source.checked_on}
        if source.locator is not None:
            out["locator"] = source.locator
        if source.note is not None:
            out["note"] = source.note
        return out
    return {"kind": source.kind, "note": source.note}


def tiers_to_dict(tiers: ParameterTiers) -> Json:
    return {"calorific": tiers.calorific, "co2": tiers.co2, "nonCo2": tiers.non_co2, "oxidation": tiers.oxidation}


def unit_conversion_to_dict(conversion: UnitConversion) -> Json:
    return {
        "from": conversion.from_unit,
        "to": conversion.to_unit,
        "factor": conversion.factor,
        "source": provenance_to_dict(conversion.source),
    }


def factor_to_dict(factor: Factor) -> Json:
    """계수 한 건. 키의 순서는 esg-lab 의 자료 파일(factors.*.json)이 적는 순서다."""
    out: Json = {
        "kind": factor.kind,
        "id": factor.id,
        "version": factor.version,
        "source": provenance_to_dict(factor.source),
    }
    if isinstance(factor, CombustionFactor):
        out["fuel"] = factor.fuel
        out["combustionType"] = factor.combustion_type
        if factor.sector is not None:
            out["sector"] = factor.sector
        if factor.parameter_tiers is not None:
            out["parameterTiers"] = tiers_to_dict(factor.parameter_tiers)
        if factor.facility_use is not None:
            out["facilityUse"] = factor.facility_use
        if factor.variant is not None:
            out["variant"] = factor.variant
        if factor.year is not None:
            out["year"] = factor.year
        out["calorific"] = {
            "value": factor.calorific.value,
            "energyUnit": factor.calorific.energy_unit,
            "perUnit": factor.calorific.per_unit,
            "basis": factor.calorific.basis,
        }
        out["emissionFactors"] = [
            {"gas": e.gas, "value": e.value, "massUnit": e.mass_unit, "perEnergyUnit": e.per_energy_unit}
            for e in factor.emission_factors
        ]
        if factor.oxidation_factor is not None:
            out["oxidationFactor"] = factor.oxidation_factor
        return out
    out["energyType"] = factor.energy_type
    if factor.variant is not None:
        out["variant"] = factor.variant
    if factor.year is not None:
        out["year"] = factor.year
    out["perUnit"] = factor.per_unit
    out["emissionFactors"] = [
        {"gas": e.gas, "value": e.value, "massUnit": e.mass_unit} for e in factor.emission_factors
    ]
    return out


def gwp_set_to_dict(gwp_set: GwpSet) -> Json:
    return {
        "id": gwp_set.id,
        "label": gwp_set.label,
        "source": provenance_to_dict(gwp_set.source),
        "values": dict(gwp_set.values),
    }


def tables_to_dict(tables: ReferenceTables) -> Json:
    return {
        "unitConversions": [unit_conversion_to_dict(c) for c in tables.unit_conversions],
        "factors": [factor_to_dict(f) for f in tables.factors],
        "gwpSets": [gwp_set_to_dict(s) for s in tables.gwp_sets],
    }


def failure_to_dict(failure: Failure) -> Json:
    match failure.kind:
        case "invalid_activity":
            return {"kind": failure.kind, "field": failure.field, "value": failure.value, "reason": failure.reason}
        case "factor_not_found":
            return {"kind": failure.kind, "criteria": dict(failure.criteria)}
        case "factor_ambiguous":
            return {
                "kind": failure.kind,
                "criteria": dict(failure.criteria),
                "candidateIds": list(failure.candidate_ids),
            }
        case "factor_kind_mismatch":
            return {
                "kind": failure.kind,
                "factorId": failure.factor_id,
                "expected": failure.expected,
                "actual": failure.actual,
            }
        case "factor_incomplete":
            return {"kind": failure.kind, "factorId": failure.factor_id, "reason": failure.reason}
        case "invalid_reference_value":
            return {"kind": failure.kind, "where": failure.where, "value": failure.value}
        case "calorific_basis_mismatch":
            return {
                "kind": failure.kind,
                "factorId": failure.factor_id,
                "required": failure.required,
                "actual": failure.actual,
            }
        case "unit_conversion_not_found":
            return {"kind": failure.kind, "from": failure.from_unit, "to": failure.to_unit, "context": failure.context}
        case "unit_conversion_ambiguous":
            return {
                "kind": failure.kind,
                "from": failure.from_unit,
                "to": failure.to_unit,
                "factors": list(failure.factors),
            }
        case "gwp_set_not_found" | "gwp_set_ambiguous":
            return {"kind": failure.kind, "gwpSetId": failure.gwp_set_id}
        case "gwp_value_missing":
            return {"kind": failure.kind, "gwpSetId": failure.gwp_set_id, "gas": failure.gas}


def step_to_dict(step: Step) -> Json:
    out: Json = {"label": step.label, "formula": step.formula, "result": step.result, "unit": step.unit}
    if step.conversion is not None:
        out["conversion"] = unit_conversion_to_dict(step.conversion)
    return out


def gas_result_to_dict(gas: GasResult) -> Json:
    return {"gas": gas.gas, "mass": gas.mass, "massUnit": gas.mass_unit, "gwp": gas.gwp, "co2e": gas.co2e}


def evidence_to_dict(evidence: Evidence) -> Json:
    factor, gwp_set = evidence.factor, evidence.gwp_set
    return {
        "factor": {"id": factor.id, "version": factor.version, "source": provenance_to_dict(factor.source)},
        "gwpSet": {"id": gwp_set.id, "label": gwp_set.label, "source": provenance_to_dict(gwp_set.source)},
        "calorificBasis": evidence.calorific_basis,
        "oxidationFactor": evidence.oxidation_factor,
        "sector": evidence.sector,
        "parameterTiers": None if evidence.parameter_tiers is None else tiers_to_dict(evidence.parameter_tiers),
        "facilityUse": evidence.facility_use,
        "steps": [step_to_dict(step) for step in evidence.steps],
    }


def row_result_to_dict(row: RowResult) -> Json:
    out: Json = {
        "rowId": row.row_id,
        "orgUnit": row.org_unit,
        "period": row.period,
        "scope": row.scope,
        "sourceType": row.source_type,
        "status": row.status,
    }
    if isinstance(row, RowOk):
        out["co2e"] = row.co2e
        out["unit"] = row.unit
        out["energy"] = None if row.energy is None else {"value": row.energy.value, "unit": row.energy.unit}
        out["gases"] = [gas_result_to_dict(gas) for gas in row.gases]
        out["evidence"] = evidence_to_dict(row.evidence)
    else:
        out["failure"] = failure_to_dict(row.failure)
    return out


def totals_to_dict(totals: Totals) -> Json:
    return {
        "co2e": totals.co2e,
        "co2eByGas": dict(totals.co2e_by_gas),
        "okRowCount": totals.ok_row_count,
        "failedRowIds": list(totals.failed_row_ids),
        "complete": totals.complete,
    }


def group_to_dict(group: Group) -> Json:
    return {"key": dict(group.key), **totals_to_dict(group)}


def aggregation_to_dict(aggregation: Aggregation) -> Json:
    return {
        "by": list(aggregation.by),
        "groups": [group_to_dict(group) for group in aggregation.groups],
        "total": totals_to_dict(aggregation.total),
    }


def output_to_dict(*, gwp_set_id: str, rows: list[RowResult], aggregation: Aggregation) -> Json:
    """esg-lab 의 CLI(`cli.ts calc`)가 표준 출력으로 내던 것과 같은 꼴."""
    return {
        "gwpSetId": gwp_set_id,
        "rows": [row_result_to_dict(row) for row in rows],
        "aggregation": aggregation_to_dict(aggregation),
    }
