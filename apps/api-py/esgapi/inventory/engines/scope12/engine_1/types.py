"""엔진이 받는 기준정보 표와 활동 데이터, 내놓는 결과의 꼴.

수치는 전부 십진 문자열이다(JSON 의 수를 거치면 부동소수점이 끼어든다).
갈래(판별 유니온)는 `kind`·`status` 글자 필드를 둔 frozen dataclass 의 합이다. 실패는 예외가 아니라 값이다.

esg-lab `ts/ghg-calc/src/types.ts` 를 옮긴 것이다. 필드 이름은 파이썬 꼴(snake_case)이고,
JSON 으로 나갈 때의 이름(camelCase)과 키의 순서는 serialize.py 가 정한다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.inventory.engines.scope12.engine_1.provenance import Provenance

Gas = Literal["CO2", "CH4", "N2O"]
# `CO2e` 는 이미 환산돼 공표된 계수다. GWP 를 다시 곱하지 않는다.
FactorGas = Literal["CO2", "CH4", "N2O", "CO2e"]

CombustionType = Literal["stationary", "mobile"]
CalorificBasis = Literal["net", "gross"]
EnergyType = Literal["electricity", "heat"]
# 시설의 쓰임. 고체연료의 산화계수가 발전과 그 밖으로 갈린다.
FacilityUse = Literal["power_generation", "other"]
FactorKind = Literal["combustion", "purchased_energy"]
SourceType = Literal["stationary_combustion", "mobile_combustion", "purchased_electricity", "purchased_heat"]
Scope = Literal[1, 2]

# 연소는 Scope 1, 구매 전력·열은 Scope 2.
SCOPE_OF: Final[dict[SourceType, Scope]] = {
    "stationary_combustion": 1,
    "mobile_combustion": 1,
    "purchased_electricity": 2,
    "purchased_heat": 2,
}

# ── 기준정보 표 ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True, kw_only=True)
class ParameterTiers:
    """매개변수별 산정등급(1 IPCC 기본값, 2 국가 고유값, 3 사업장 고유값, 4 연속측정).

    한 계수 안에서도 매개변수마다 등급이 다를 수 있다. 표의 계수에서는 1~4 임을 validate_tables 가 본다.
    행에 적힌 것은 범위를 보지 않는다: 계수와 정확히 같은지만 견주므로 없는 등급은 「맞는 계수 없음」이 된다.
    """

    calorific: int  # 발열량
    co2: int  # CO2 배출계수
    non_co2: int  # CH4·N2O 배출계수
    oxidation: int | None  # 산화계수. 식에 산화계수 항이 없으면 None


@dataclass(frozen=True, slots=True, kw_only=True)
class UnitConversion:
    from_unit: str
    to_unit: str
    factor: str  # to 단위 값 = from 단위 값 × factor
    source: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class Calorific:
    value: str
    energy_unit: str
    per_unit: str
    basis: CalorificBasis


@dataclass(frozen=True, slots=True, kw_only=True)
class CombustionEmissionFactor:
    gas: str  # CO2·CH4·N2O. 표 검사는 빈 문자열만 막는다(빠진 기체·모르는 기체는 계산 때 factor_incomplete 로 드러난다)
    value: str
    mass_unit: str
    per_energy_unit: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CombustionFactor:
    """연료 연소 계수. sector·parameter_tiers·facility_use·variant 가 같은 연료·연소 유형의 계수를 가른다."""

    kind: Literal["combustion"] = "combustion"
    id: str
    version: str
    source: Provenance
    fuel: str
    combustion_type: CombustionType
    calorific: Calorific
    # CO2, CH4, N2O 가 모두 있어야 한다. 빠진 기체를 0 으로 치지 않는다.
    emission_factors: tuple[CombustionEmissionFactor, ...]
    # CO2 에만 곱한다. 없으면 식에 이 항이 없다.
    oxidation_factor: str | None = None
    year: int | None = None
    # 부문(CH4·N2O 기본 배출계수가 부문마다 다르다). 엔진은 뜻을 풀지 않고 같은지만 본다.
    sector: str | None = None
    parameter_tiers: ParameterTiers | None = None
    facility_use: FacilityUse | None = None
    # 위 셋에 들지 않는 그 밖의 구분(차종 등)
    variant: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PurchasedEmissionFactor:
    gas: str  # `CO2e` 하나이거나 CO2·CH4·N2O 셋 전부. 아니면 계산 때 factor_incomplete
    value: str
    mass_unit: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PurchasedEnergyFactor:
    """구매 전력·열 계수. 부문·산정등급 필드는 연소 계수에만 있다."""

    kind: Literal["purchased_energy"] = "purchased_energy"
    id: str
    version: str
    source: Provenance
    energy_type: EnergyType
    per_unit: str
    emission_factors: tuple[PurchasedEmissionFactor, ...]
    # 같은 에너지 종류 안의 구분(발전단·소비단, 공급자 등)
    variant: str | None = None
    year: int | None = None


Factor = CombustionFactor | PurchasedEnergyFactor


@dataclass(frozen=True, slots=True, kw_only=True)
class GwpSet:
    id: str
    label: str
    source: Provenance
    values: Mapping[str, str]  # 기체 → GWP. 빠진 기체는 계산 때 gwp_value_missing


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceTables:
    unit_conversions: tuple[UnitConversion, ...] = ()
    factors: tuple[Factor, ...] = ()
    gwp_sets: tuple[GwpSet, ...] = ()


# ── 활동 데이터 ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True, kw_only=True)
class ActivityRow:
    """활동 데이터 한 행.

    sector·parameter_tiers·facility_use 는 연소 행에만 쓴다(구매 전력·열 행에 적으면 맞는 계수가 없다).
    """

    id: str
    org_unit: str
    period: str
    source_type: SourceType
    amount: str
    unit: str
    # 연소: 연료 이름(계수의 fuel 과 같아야 한다). 구매 전력·열: 쓰지 않는다.
    fuel: str | None = None
    factor_year: int | None = None
    # 지정하면 이름·구분·연도 대신 이 id 로 계수를 고른다.
    factor_id: str | None = None
    sector: str | None = None
    parameter_tiers: ParameterTiers | None = None
    # 계수의 것과 같은지만 견준다. 모르는 값은 「맞는 계수 없음」이 된다.
    facility_use: str | None = None
    variant: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CalcOptions:
    # 기본값이 없다. 한국의 배출권거래제와 국가 인벤토리가 서로 다른 세트를 쓴다.
    gwp_set_id: str
    # 지정하면 이 종류가 아닌 발열량을 쓴 계수는 실패 처리한다.
    require_calorific_basis: CalorificBasis | None = None


# ── 실패의 갈래 (열둘) ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidActivity:
    kind: Literal["invalid_activity"] = "invalid_activity"
    field: str
    value: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorNotFound:
    kind: Literal["factor_not_found"] = "factor_not_found"
    criteria: dict[str, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorAmbiguous:
    kind: Literal["factor_ambiguous"] = "factor_ambiguous"
    criteria: dict[str, str]
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorKindMismatch:
    kind: Literal["factor_kind_mismatch"] = "factor_kind_mismatch"
    factor_id: str
    expected: FactorKind
    actual: FactorKind


@dataclass(frozen=True, slots=True, kw_only=True)
class FactorIncomplete:
    kind: Literal["factor_incomplete"] = "factor_incomplete"
    factor_id: str
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidReferenceValue:
    kind: Literal["invalid_reference_value"] = "invalid_reference_value"
    where: str
    value: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CalorificBasisMismatch:
    kind: Literal["calorific_basis_mismatch"] = "calorific_basis_mismatch"
    factor_id: str
    required: CalorificBasis
    actual: CalorificBasis


@dataclass(frozen=True, slots=True, kw_only=True)
class UnitConversionNotFound:
    kind: Literal["unit_conversion_not_found"] = "unit_conversion_not_found"
    from_unit: str
    to_unit: str
    context: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnitConversionAmbiguous:
    kind: Literal["unit_conversion_ambiguous"] = "unit_conversion_ambiguous"
    from_unit: str
    to_unit: str
    factors: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class GwpSetNotFound:
    kind: Literal["gwp_set_not_found"] = "gwp_set_not_found"
    gwp_set_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GwpSetAmbiguous:
    kind: Literal["gwp_set_ambiguous"] = "gwp_set_ambiguous"
    gwp_set_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GwpValueMissing:
    kind: Literal["gwp_value_missing"] = "gwp_value_missing"
    gwp_set_id: str
    gas: Gas


Failure = (
    InvalidActivity
    | FactorNotFound
    | FactorAmbiguous
    | FactorKindMismatch
    | FactorIncomplete
    | InvalidReferenceValue
    | CalorificBasisMismatch
    | UnitConversionNotFound
    | UnitConversionAmbiguous
    | GwpSetNotFound
    | GwpSetAmbiguous
    | GwpValueMissing
)

# ── 결과 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True, kw_only=True)
class Step:
    """한 연산 단계. 제3자가 손으로 따라갈 수 있게 식과 결과를 문자열로 남긴다."""

    label: str
    formula: str
    result: str
    unit: str
    conversion: UnitConversion | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class GasResult:
    gas: FactorGas
    # 기체 질량 (t). `CO2e` 계수이면 이미 tCO2eq 이다.
    mass: str
    mass_unit: Literal["t"] = "t"
    # 적용한 GWP. `CO2e` 계수이면 None (곱하지 않았다).
    gwp: str | None
    co2e: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Energy:
    value: str
    unit: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceFactor:
    id: str
    version: str
    source: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceGwpSet:
    id: str
    label: str
    source: Provenance


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    factor: EvidenceFactor
    gwp_set: EvidenceGwpSet
    calorific_basis: CalorificBasis | None
    oxidation_factor: str | None
    # 쓴 계수의 부문과 매개변수별 산정등급. 계수에 적혀 있지 않으면 None (구매 전력·열은 늘 None).
    sector: str | None
    parameter_tiers: ParameterTiers | None
    facility_use: FacilityUse | None
    steps: tuple[Step, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class RowOk:
    row_id: str
    org_unit: str
    period: str
    scope: Scope
    source_type: SourceType
    status: Literal["ok"] = "ok"
    # 반올림하지 않은 정확한 값.
    co2e: str
    unit: Literal["tCO2eq"] = "tCO2eq"
    # 연소일 때만. 계수의 에너지 단위 기준 (예: TJ).
    energy: Energy | None
    gases: tuple[GasResult, ...]
    evidence: Evidence


@dataclass(frozen=True, slots=True, kw_only=True)
class RowFailed:
    """배출원 유형을 알 수 없는 행은 scope 와 source_type 이 None 이다(추측하지 않는다)."""

    row_id: str
    org_unit: str
    period: str
    scope: Scope | None
    source_type: SourceType | None
    status: Literal["failed"] = "failed"
    failure: Failure


RowResult = RowOk | RowFailed


@dataclass(frozen=True, slots=True)
class Ok[T]:
    value: T


@dataclass(frozen=True, slots=True)
class Err:
    failure: Failure
