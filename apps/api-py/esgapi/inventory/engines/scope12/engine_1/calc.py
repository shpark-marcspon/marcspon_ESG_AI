"""Scope 1·2 배출량 계산. esg-lab `ts/ghg-calc/src/calc.ts` 를 옮긴 것이다.

계산 함수는 dataclass 만 받는다. 바깥에서 온 JSON(dict)은 activity.check_activity_row 와
tables.validate_tables 가 먼저 막는다. 단계의 label·formula 문장은 TS 와 글자까지 같다(골든이 잰다).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from esgapi.core.calc.decimal import (
    ZERO,
    Decimal,
    add,
    format_decimal,
    is_negative,
    mul,
    parse_decimal,
    parse_external_decimal,
)
from esgapi.inventory.engines.scope12.engine_1.activity import check_activity_row, check_amount
from esgapi.inventory.engines.scope12.engine_1.types import (
    SCOPE_OF,
    ActivityRow,
    CalcOptions,
    CalorificBasis,
    CalorificBasisMismatch,
    CombustionFactor,
    Energy,
    Err,
    Evidence,
    EvidenceFactor,
    EvidenceGwpSet,
    Factor,
    FactorAmbiguous,
    FactorIncomplete,
    FactorKind,
    FactorKindMismatch,
    FactorNotFound,
    Failure,
    Gas,
    GasResult,
    GwpSet,
    GwpSetAmbiguous,
    GwpSetNotFound,
    GwpValueMissing,
    InvalidActivity,
    InvalidReferenceValue,
    Ok,
    ParameterTiers,
    PurchasedEnergyFactor,
    ReferenceTables,
    RowFailed,
    RowOk,
    RowResult,
    Step,
)
from esgapi.inventory.engines.scope12.engine_1.units import convert_unit
from esgapi.inventory.tools.jsrepr import js_string

# 결과의 질량 단위. 기체별 배출량은 모두 이 단위로 환산한 뒤 GWP 를 곱한다.
RESULT_MASS_UNIT: Final = "t"
GASES: Final[tuple[Gas, ...]] = ("CO2", "CH4", "N2O")


def _ref_value(text: str, where: str) -> Ok[Decimal] | Err:
    """표의 값은 쓸 때마다 읽는다. 계수, 발열량, GWP, 산화계수는 음수일 수 없다."""
    value = parse_external_decimal(text)
    if value is None or is_negative(value):
        return Err(InvalidReferenceValue(where=where, value=text))
    return Ok(value)


def _tiers_text(tiers: ParameterTiers) -> str:
    return f"calorific={tiers.calorific},co2={tiers.co2},nonCo2={tiers.non_co2},oxidation={js_string(tiers.oxidation)}"


def _select_factor(row: ActivityRow, factors: Sequence[Factor]) -> Ok[Factor] | Err:
    combustion_row = row.source_type in ("stationary_combustion", "mobile_combustion")
    expected_kind: FactorKind = "combustion" if combustion_row else "purchased_energy"

    if row.factor_id is not None:
        criteria = {"factorId": row.factor_id}
        by_id = [f for f in factors if f.id == row.factor_id]
        if not by_id:
            return Err(FactorNotFound(criteria=criteria))
        if len(by_id) > 1:
            return Err(FactorAmbiguous(criteria=criteria, candidate_ids=tuple(f.id for f in by_id)))
        found = by_id[0]
        if found.kind != expected_kind:
            return Err(FactorKindMismatch(factor_id=found.id, expected=expected_kind, actual=found.kind))
        return Ok(found)

    # 이름으로 고를 때는 구분(부문, 매개변수별 산정등급, 시설의 쓰임, 그 밖의 구분)과 연도가 정확히 같아야 한다.
    # 비워 둔 쪽은 비워 둔 계수에만 맞는다.
    criteria = {"sourceType": row.source_type}
    if row.fuel is not None:
        criteria["fuel"] = row.fuel
    if row.sector is not None:
        criteria["sector"] = row.sector
    if row.parameter_tiers is not None:
        criteria["parameterTiers"] = _tiers_text(row.parameter_tiers)
    if row.facility_use is not None:
        criteria["facilityUse"] = row.facility_use
    if row.variant is not None:
        criteria["variant"] = row.variant
    if row.factor_year is not None:
        criteria["factorYear"] = str(row.factor_year)

    def matches(f: Factor) -> bool:
        if f.variant != row.variant or f.year != row.factor_year:
            return False
        if isinstance(f, CombustionFactor):
            return (
                expected_kind == "combustion"
                and f.fuel == row.fuel
                and f.combustion_type == ("stationary" if row.source_type == "stationary_combustion" else "mobile")
                and f.sector == row.sector
                and f.parameter_tiers == row.parameter_tiers
                and f.facility_use == row.facility_use
            )
        # 구매 전력·열 계수에는 부문·산정등급이 없다. 행에 적혀 있으면 맞는 계수가 없는 것이다.
        return (
            expected_kind == "purchased_energy"
            and f.energy_type == ("electricity" if row.source_type == "purchased_electricity" else "heat")
            and row.sector is None
            and row.parameter_tiers is None
            and row.facility_use is None
        )

    candidates = [f for f in factors if matches(f)]
    if not candidates:
        return Err(FactorNotFound(criteria=criteria))
    if len(candidates) > 1:
        return Err(FactorAmbiguous(criteria=criteria, candidate_ids=tuple(f.id for f in candidates)))
    return Ok(candidates[0])


def _select_gwp_set(gwp_set_id: str, sets: Sequence[GwpSet]) -> Ok[GwpSet] | Err:
    matches = [s for s in sets if s.id == gwp_set_id]
    if not matches:
        return Err(GwpSetNotFound(gwp_set_id=gwp_set_id))
    if len(matches) > 1:
        return Err(GwpSetAmbiguous(gwp_set_id=gwp_set_id))
    return Ok(matches[0])


def _gwp_of(gwp_set: GwpSet, gas: Gas) -> Ok[Decimal] | Err:
    text = gwp_set.values.get(gas)
    if text is None:
        return Err(GwpValueMissing(gwp_set_id=gwp_set.id, gas=gas))
    return _ref_value(text, f"gwpSets[{gwp_set.id}].values.{gas}")


@dataclass(frozen=True, slots=True)
class _Computed:
    energy: Energy | None
    gases: tuple[GasResult, ...]
    steps: list[Step]
    calorific_basis: CalorificBasis | None
    oxidation_factor: str | None


def _to_co2e(gas: Gas, mass_tonnes: Decimal, gwp_set: GwpSet, steps: list[Step]) -> Ok[GasResult] | Err:
    gwp = _gwp_of(gwp_set, gas)
    if isinstance(gwp, Err):
        return gwp
    co2e = mul(mass_tonnes, gwp.value)
    steps.append(
        Step(
            label=f"{gas} 환산",
            formula=f"{format_decimal(mass_tonnes)} t{gas} × GWP {format_decimal(gwp.value)} ({gwp_set.id})",
            result=format_decimal(co2e),
            unit="tCO2eq",
        )
    )
    return Ok(
        GasResult(gas=gas, mass=format_decimal(mass_tonnes), gwp=format_decimal(gwp.value), co2e=format_decimal(co2e))
    )


def _compute_combustion(
    amount: Decimal,
    row: ActivityRow,
    factor: CombustionFactor,
    gwp_set: GwpSet,
    tables: ReferenceTables,
    options: CalcOptions,
) -> Ok[_Computed] | Err:
    where = f"factors[{factor.id}]"
    basis = factor.calorific.basis
    if options.require_calorific_basis is not None and basis != options.require_calorific_basis:
        return Err(CalorificBasisMismatch(factor_id=factor.id, required=options.require_calorific_basis, actual=basis))
    for gas in GASES:
        count = sum(1 for e in factor.emission_factors if e.gas == gas)
        if count != 1:
            reason = f"{gas} 배출계수가 없다" if count == 0 else f"{gas} 배출계수가 {count}개다"
            return Err(FactorIncomplete(factor_id=factor.id, reason=reason))

    steps: list[Step] = []
    energy_unit = factor.calorific.energy_unit
    per_unit = factor.calorific.per_unit
    conversions = tables.unit_conversions

    # 사용량 단위를 발열량의 기준 단위로 맞춘다. 그 환산이 없고 사용량이 이미 에너지 단위이면
    # (예: 열량으로 계량한 연료) 발열량을 거치지 않고 에너지량으로 쓴다.
    as_quantity = convert_unit(amount, row.unit, per_unit, conversions, "사용량 → 발열량 기준 단위")
    if isinstance(as_quantity, Ok):
        if as_quantity.value.step is not None:
            steps.append(as_quantity.value.step)
        calorific = _ref_value(factor.calorific.value, f"{where}.calorific.value")
        if isinstance(calorific, Err):
            return calorific
        quantity = as_quantity.value.value
        energy = mul(quantity, calorific.value)
        basis_label = "순발열량" if basis == "net" else "총발열량"
        steps.append(
            Step(
                label="에너지량",
                formula=(
                    f"{format_decimal(quantity)} {per_unit} × {format_decimal(calorific.value)} "
                    f"{energy_unit}/{per_unit} ({basis_label})"
                ),
                result=format_decimal(energy),
                unit=energy_unit,
            )
        )
    else:
        if as_quantity.failure.kind != "unit_conversion_not_found":
            return as_quantity
        as_energy = convert_unit(amount, row.unit, energy_unit, conversions, "사용량(에너지) → 발열량 에너지 단위")
        if isinstance(as_energy, Err):
            # 두 길이 모두 없으면 먼저 시도한 쪽(사용량 단위 환산)의 실패를 돌려준다.
            return as_quantity if as_energy.failure.kind == "unit_conversion_not_found" else as_energy
        if as_energy.value.step is not None:
            steps.append(as_energy.value.step)
        energy = as_energy.value.value
        steps.append(
            Step(
                label="에너지량",
                formula=f"사용량이 에너지 단위({row.unit})로 주어져 발열량을 곱하지 않았다",
                result=format_decimal(energy),
                unit=energy_unit,
            )
        )

    oxidation: Decimal | None = None
    if factor.oxidation_factor is not None:
        parsed = _ref_value(factor.oxidation_factor, f"{where}.oxidationFactor")
        if isinstance(parsed, Err):
            return parsed
        oxidation = parsed.value

    gases: list[GasResult] = []
    for gas in GASES:
        ef = next((e for e in factor.emission_factors if e.gas == gas), None)
        if ef is None:
            return Err(FactorIncomplete(factor_id=factor.id, reason=f"{gas} 배출계수가 없다"))
        ef_value = _ref_value(ef.value, f"{where}.emissionFactors.{gas}")
        if isinstance(ef_value, Err):
            return ef_value

        energy_for_ef = convert_unit(
            energy, energy_unit, ef.per_energy_unit, conversions, f"{gas} 배출계수의 에너지 단위"
        )
        if isinstance(energy_for_ef, Err):
            return energy_for_ef
        if energy_for_ef.value.step is not None:
            steps.append(energy_for_ef.value.step)

        mass = mul(energy_for_ef.value.value, ef_value.value)
        formula = (
            f"{format_decimal(energy_for_ef.value.value)} {ef.per_energy_unit} × "
            f"{format_decimal(ef_value.value)} {ef.mass_unit}{gas}/{ef.per_energy_unit}"
        )
        # 산화계수는 CO2 에만 곱한다.
        if gas == "CO2" and oxidation is not None:
            mass = mul(mass, oxidation)
            formula += f" × 산화계수 {format_decimal(oxidation)}"
        steps.append(
            Step(label=f"{gas} 배출량", formula=formula, result=format_decimal(mass), unit=f"{ef.mass_unit}{gas}")
        )

        tonnes = convert_unit(mass, ef.mass_unit, RESULT_MASS_UNIT, conversions, f"{gas} 질량")
        if isinstance(tonnes, Err):
            return tonnes
        if tonnes.value.step is not None:
            steps.append(tonnes.value.step)

        gas_result = _to_co2e(gas, tonnes.value.value, gwp_set, steps)
        if isinstance(gas_result, Err):
            return gas_result
        gases.append(gas_result.value)

    return Ok(
        _Computed(
            energy=Energy(value=format_decimal(energy), unit=energy_unit),
            gases=tuple(gases),
            steps=steps,
            calorific_basis=basis,
            oxidation_factor=None if oxidation is None else format_decimal(oxidation),
        )
    )


def _as_gas(text: str) -> Gas | None:
    return next((gas for gas in GASES if gas == text), None)


def _compute_purchased(
    amount: Decimal,
    row: ActivityRow,
    factor: PurchasedEnergyFactor,
    gwp_set: GwpSet,
    tables: ReferenceTables,
) -> Ok[_Computed] | Err:
    where = f"factors[{factor.id}]"
    listed = [e.gas for e in factor.emission_factors]
    pre_aggregated = listed == ["CO2e"]
    per_gas = len(listed) == len(GASES) and all(listed.count(gas) == 1 for gas in GASES)
    if not pre_aggregated and not per_gas:
        received = ", ".join(listed) or "없음"
        return Err(
            FactorIncomplete(
                factor_id=factor.id,
                reason=f"배출계수는 CO2e 하나이거나 CO2·CH4·N2O 셋이어야 한다 (받은 것: {received})",
            )
        )

    steps: list[Step] = []
    conversions = tables.unit_conversions
    quantity = convert_unit(amount, row.unit, factor.per_unit, conversions, "사용량 → 배출계수 기준 단위")
    if isinstance(quantity, Err):
        return quantity
    if quantity.value.step is not None:
        steps.append(quantity.value.step)

    gases: list[GasResult] = []
    for ef in factor.emission_factors:
        ef_value = _ref_value(ef.value, f"{where}.emissionFactors.{ef.gas}")
        if isinstance(ef_value, Err):
            return ef_value
        mass = mul(quantity.value.value, ef_value.value)
        steps.append(
            Step(
                label=f"{ef.gas} 배출량",
                formula=(
                    f"{format_decimal(quantity.value.value)} {factor.per_unit} × "
                    f"{format_decimal(ef_value.value)} {ef.mass_unit}{ef.gas}/{factor.per_unit}"
                ),
                result=format_decimal(mass),
                unit=f"{ef.mass_unit}{ef.gas}",
            )
        )
        tonnes = convert_unit(mass, ef.mass_unit, RESULT_MASS_UNIT, conversions, f"{ef.gas} 질량")
        if isinstance(tonnes, Err):
            return tonnes
        if tonnes.value.step is not None:
            steps.append(tonnes.value.step)

        gas = _as_gas(ef.gas)
        if gas is None:
            # 이미 환산돼 공표된 계수(CO2e)다. GWP 를 곱하지 않는다.
            text = format_decimal(tonnes.value.value)
            gases.append(GasResult(gas="CO2e", mass=text, gwp=None, co2e=text))
            continue
        gas_result = _to_co2e(gas, tonnes.value.value, gwp_set, steps)
        if isinstance(gas_result, Err):
            return gas_result
        gases.append(gas_result.value)

    return Ok(_Computed(energy=None, gases=tuple(gases), steps=steps, calorific_basis=None, oxidation_factor=None))


def calculate_row(row: ActivityRow, tables: ReferenceTables, options: CalcOptions) -> RowResult:
    """활동 데이터 한 행을 계산한다. 실패는 예외나 0 이 아니라 `status: "failed"` 로 돌려준다."""
    scope = SCOPE_OF[row.source_type]

    def failed(failure: Failure) -> RowFailed:
        return RowFailed(
            row_id=row.id,
            org_unit=row.org_unit,
            period=row.period,
            scope=scope,
            source_type=row.source_type,
            failure=failure,
        )

    amount = check_amount(row.amount)
    if isinstance(amount, InvalidActivity):
        return failed(amount)
    combustion = scope == 1
    if combustion and (row.fuel is None or row.fuel == "") and row.factor_id is None:
        return failed(InvalidActivity(field="fuel", value="", reason="연소 행에 연료도 factorId 도 없다"))

    gwp_set = _select_gwp_set(options.gwp_set_id, tables.gwp_sets)
    if isinstance(gwp_set, Err):
        return failed(gwp_set.failure)
    factor = _select_factor(row, tables.factors)
    if isinstance(factor, Err):
        return failed(factor.failure)

    chosen = factor.value
    computed = (
        _compute_combustion(amount, row, chosen, gwp_set.value, tables, options)
        if isinstance(chosen, CombustionFactor)
        else _compute_purchased(amount, row, chosen, gwp_set.value, tables)
    )
    if isinstance(computed, Err):
        return failed(computed.failure)

    total = ZERO
    for gas in computed.value.gases:
        co2e = parse_decimal(gas.co2e)
        if co2e is None:
            raise AssertionError(f"unreachable: formatted decimal failed to parse: {gas.co2e}")
        total = add(total, co2e)
    steps = computed.value.steps
    steps.append(
        Step(
            label="합산",
            formula=" + ".join(f"{g.co2e} ({g.gas})" for g in computed.value.gases),
            result=format_decimal(total),
            unit="tCO2eq",
        )
    )

    is_combustion = isinstance(chosen, CombustionFactor)
    return RowOk(
        row_id=row.id,
        org_unit=row.org_unit,
        period=row.period,
        scope=scope,
        source_type=row.source_type,
        co2e=format_decimal(total),
        energy=computed.value.energy,
        gases=computed.value.gases,
        evidence=Evidence(
            factor=EvidenceFactor(id=chosen.id, version=chosen.version, source=chosen.source),
            gwp_set=EvidenceGwpSet(id=gwp_set.value.id, label=gwp_set.value.label, source=gwp_set.value.source),
            calorific_basis=computed.value.calorific_basis,
            oxidation_factor=computed.value.oxidation_factor,
            sector=chosen.sector if is_combustion else None,
            parameter_tiers=chosen.parameter_tiers if is_combustion else None,
            facility_use=chosen.facility_use if is_combustion else None,
            steps=tuple(steps),
        ),
    )


def calculate(rows: Sequence[ActivityRow], tables: ReferenceTables, options: CalcOptions) -> list[RowResult]:
    return [calculate_row(row, tables, options) for row in rows]


def calculate_raw_row(raw: object, tables: ReferenceTables, options: CalcOptions) -> RowResult:
    """바깥에서 온 행(JSON 을 읽은 값) 하나를 검사한 뒤 계산한다. 꼴이 틀린 행은 invalid_activity 로 돌아온다."""
    checked = check_activity_row(raw)
    if isinstance(checked, RowFailed):
        return checked
    return calculate_row(checked, tables, options)


def calculate_raw(rows: Sequence[object], tables: ReferenceTables, options: CalcOptions) -> list[RowResult]:
    return [calculate_raw_row(raw, tables, options) for raw in rows]
