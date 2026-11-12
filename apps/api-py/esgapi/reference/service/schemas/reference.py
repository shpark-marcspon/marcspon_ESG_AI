"""요청과 응답의 꼴(JSON). 여기 적힌 것이 OpenAPI 문서와 프론트의 타입(generated/api.d.ts)이 된다.

응답의 칸 이름은 camelCase 다(accounts 와 같게). 조회 인자(query)는 snake_case 다(발주서의 이름 그대로).

★ 조립 조건(AssembleIn·ElectricityIn)의 칸은 **전부 없어도 되게** 적었다. 빠진 칸은 400 이 아니라 조립의 실패 갈래
  (`missing_input`: 무엇이 빠졌는가)로 답한다 — 「기본값이 없다」는 것이 화면에 보여야 할 업무 규칙이기 때문이다.
  400 은 꼴이 틀린 것(모르는 칸, 글자 자리에 숫자)에만 난다.
★ 조립된 계수(CombustionFactorOut·PurchasedEnergyFactorOut)의 꼴은 계산 엔진의 계수와 같다
  (esg-lab `ts/ghg-calc/src/types.ts` 의 CombustionFactor·PurchasedEnergyFactor). 수치는 전부 십진 문자열이다.
"""

from typing import Any, Literal

from ninja import Schema
from pydantic import ConfigDict, Field, StrictBool, StrictInt, model_validator

from esgapi.core.schemas import LimitOffsetPage, Strict
from esgapi.reference.calc import FailureKind
from esgapi.reference.jsonl import LicenseStatus

RecordType = Literal["emission_factor", "heating_value", "energy_conversion", "oxidation_factor"]
Scope = Literal["scope1", "scope2", "scope3", "outside_of_scopes", "unspecified"]
GasName = Literal["CO2e", "CO2", "CH4", "N2O", "C", "none"]
MAX_LIMIT = 200

# ── 출처와 낱줄 ───────────────────────────────────────────────────────


class SourceOut(Schema):
    id: str
    name: str
    publisher: str
    url: str
    version: str
    retrieved: str = Field(description="원자료를 내려받아 확인한 날(YYYY-MM-DD)")
    fileName: str
    fileSha256: str
    licenseName: str
    licenseUrl: str
    licenseNote: str | None
    licenseStatus: LicenseStatus = Field(description="ok / unverified(확인하지 못했다) / disputed(문면이 충돌한다)")
    recordCount: int = Field(description="이 출처의 낱줄 수. 대응표만 가리키는 출처는 0")


class SourcesOut(Schema):
    sources: list[SourceOut]


class FactorOut(Schema):
    id: str
    sourceId: str
    licenseStatus: LicenseStatus
    licenseNote: str | None
    locator: str
    recordType: RecordType
    scope: Scope
    scope3Categories: list[int] = Field(description="이 낱줄이 후보인 Scope 3 범주. 후보일 뿐 확정이 아니다")
    scope3MappingBasis: str | None
    factorType: Literal["activity", "distance", "spend"]
    nameOriginal: str
    nameKo: str | None
    nameEn: str | None
    categoryPath: list[str]
    classification: dict[str, Any] | None
    value: float | None = Field(description="보여 주는 데만 쓴다. 계산에는 valueRaw 를 쓴다")
    valueRaw: str | None = Field(description="출처 표기 그대로의 글자")
    valueStatus: Literal["ok", "not_available_in_source", "not_applicable_in_source"]
    unit: str
    unitNumerator: str
    unitDenominator: str
    gas: GasName
    gasBasis: Literal["co2e", "gas_mass", "carbon_mass", "not_applicable"]
    heatingValueBasis: Literal["net", "gross"] | None
    conditions: dict[str, str]
    region: str
    year: int | None
    spend: dict[str, Any] | None
    synthetic: bool


_OLD = "옛 칸. 한 판만 싣는다 — count·isNext·results 를 읽는다(밴드 E2, C1 이 걷는다)"


class FactorsOut(LimitOffsetPage[FactorOut]):
    """limit/offset 목록 꼴 {count, isNext, results} + 이 조회가 낸 이용 조건 상태. 옛 넷(total·limit·offset·items)은
    같은 값으로 한 판 함께 싣는다(deprecated)."""

    licenses: list[LicenseStatus] = Field(description="이 조회가 낸 이용 조건 상태. 기본은 ok·unverified")
    total: int = Field(description=_OLD, json_schema_extra={"deprecated": True})
    limit: int = Field(description=_OLD, json_schema_extra={"deprecated": True})
    offset: int = Field(description=_OLD, json_schema_extra={"deprecated": True})
    items: list[FactorOut] = Field(description=_OLD, json_schema_extra={"deprecated": True})


class FactorQuery(Schema):
    """`GET /reference/factors` 의 조회 인자. 조건은 전부 「같다」이고 `q` 만 부분 일치다."""

    source: str | None = Field(default=None, description="출처 id (예: kr-ets-byl12)")
    recordType: RecordType | None = None
    record_type: RecordType | None = Field(
        default=None,
        description="옛 이름. 한 판만 받는다 — recordType 을 쓴다(둘 다 주면 422)",
        json_schema_extra={"deprecated": True},
    )
    scope: Scope | None = None
    gas: GasName | None = None
    q: str | None = Field(default=None, min_length=1, max_length=200, description="이름(원문·한글·영문)의 부분 일치")
    license: str | None = Field(
        default=None, description="낼 이용 조건 상태를 쉼표로. 기본 ok,unverified — disputed 는 명시해야만 나온다"
    )
    limit: int = Field(default=50, ge=1, le=MAX_LIMIT)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _one_record_type_name(self) -> "FactorQuery":
        if self.recordType is not None and self.record_type is not None:
            raise ValueError("recordType 과 옛 이름 record_type 을 함께 줄 수 없다")
        return self

    @property
    def record_type_given(self) -> str | None:
        """새 이름이 먼저, 없으면 옛 이름."""
        return self.recordType if self.recordType is not None else self.record_type


# ── 조립 조건 ─────────────────────────────────────────────────────────


class IndustryIn(Strict):
    sector: str | None = Field(default=None, description="부문 키. ksicCode 와 둘 중 하나만")
    ksicCode: str | None = Field(default=None, description="한국표준산업분류 코드(숫자 2~5자리)")


class TiersIn(Strict):
    kind: str | None = Field(default=None, description="explicit | group_minimum")
    calorific: StrictInt | None = None
    co2: StrictInt | None = None
    oxidation: StrictInt | None = None
    nonCo2: StrictInt | None = Field(default=None, description="CH4·N2O 는 Tier 1 뿐이다. 주려면 1")
    group: str | None = Field(default=None, description="group_minimum 일 때 시설 규모 그룹 A | B | C")


class AssembleIn(Strict):
    fuel: str | None = Field(default=None, description="국내 연료명(별표 12 의 이름)")
    combustionType: str | None = Field(default=None, description="stationary 만")
    industry: IndustryIn | None = None
    tiers: TiersIn | None = None
    fuelState: str | None = Field(default=None, description="고체 | 기체 | 액체. 대응표에 상태가 없는 연료에만")
    powerGeneration: StrictBool | None = Field(default=None, description="고체연료의 Tier 2 산화계수에만")


class PeriodIn(Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    kind: str | None = Field(default=None, description="single_year | three_year_average | not_stated")
    year: StrictInt | None = None
    from_: StrictInt | None = Field(default=None, alias="from")
    to: StrictInt | None = None


class GirIn(Strict):
    edition: StrictInt | None = Field(default=None, description="공표 판(2024 | 2025)")
    period: PeriodIn | None = None
    boundary: str | None = Field(default=None, description="generation(발전단) | consumption(소비단)")
    methodology: str | None = Field(default=None, description="ipcc_2006 | ipcc_1996_legacy")


class ElectricityIn(Strict):
    energyType: str | None = Field(default=None, description="electricity 만")
    source: str | None = Field(default=None, description="guideline_table69 | gir_published. 기본값이 없다")
    gasForm: str | None = Field(default=None, description="per_gas | co2e")
    gir: GirIn | None = Field(default=None, description="source 가 gir_published 일 때만, 그때는 전부")


# ── 조립 결과 ─────────────────────────────────────────────────────────


class ProvenanceOut(Schema):
    kind: Literal["cited"]
    title: str
    url: str
    checkedOn: str
    locator: str
    note: str


class ParameterTiersOut(Schema):
    calorific: int
    co2: int
    nonCo2: int
    oxidation: int


class CalorificOut(Schema):
    value: str
    energyUnit: str
    perUnit: str
    basis: Literal["net"]


class CombustionEmissionFactorOut(Schema):
    gas: Literal["CO2", "CH4", "N2O"]
    value: str
    massUnit: str
    perEnergyUnit: str


class CombustionFactorOut(Schema):
    kind: Literal["combustion"]
    id: str
    version: str
    source: ProvenanceOut
    fuel: str
    combustionType: Literal["stationary"]
    sector: str
    parameterTiers: ParameterTiersOut
    # 고체연료의 Tier 2 산화계수일 때만 있다. 그 밖에는 칸 자체가 없다(null 이 아니다).
    facilityUse: Literal["power_generation", "other"] | None = None
    calorific: CalorificOut
    emissionFactors: list[CombustionEmissionFactorOut]
    oxidationFactor: str


class NameMappingOut(Schema):
    domestic: str
    ipcc: str
    basis: Literal["guideline", "assumed"]
    locator: str
    table: str | None = None


class ParameterEvidenceOut(Schema):
    parameter: Literal["calorific", "CO2", "CH4", "N2O", "oxidation"]
    tier: int
    rule: str
    recordId: str
    sourceId: str
    sourceName: str
    url: str
    retrieved: str
    fileSha256: str
    locator: str
    nameUsed: str
    nameMapping: NameMappingOut | None
    valueRaw: str
    value: str
    unit: str
    conditions: dict[str, str]


class GuidelineOut(Schema):
    name: str
    version: str
    url: str


class FuelStateEvidenceOut(Schema):
    value: Literal["고체", "기체", "액체"]
    basis: Literal["guideline", "assumed", "input"]
    locator: str | None


class SectorEvidenceOut(Schema):
    key: str
    label: str
    basis: Literal["input", "ksic_division", "ksic_exception"]
    ksicCode: str | None
    locator: str


class TiersEvidenceOut(Schema):
    values: ParameterTiersOut
    basis: Literal["explicit", "group_minimum"]
    group: Literal["A", "B", "C"] | None
    locators: list[str]


class AssumptionOut(Schema):
    kind: Literal["fuel_name", "fuel_state"]
    detail: str
    note: str
    locator: str


class CombustionEvidenceOut(Schema):
    guideline: GuidelineOut
    fuelState: FuelStateEvidenceOut
    sector: SectorEvidenceOut
    tiers: TiersEvidenceOut
    parameters: list[ParameterEvidenceOut]
    assumptions: list[AssumptionOut] = Field(description="지침에 없는 추정 대응을 탄 자리. 있으면 그만큼 추정에 기댄다")


class CombustionAssembledOut(Schema):
    factor: CombustionFactorOut
    evidence: CombustionEvidenceOut


class FailureOut(Schema):
    """조립하지 못한 까닭. `kind` 가 갈래의 이름이고, 나머지 칸은 갈래마다 그 갈래의 것만 실린다(없는 칸은 빠진다).

    갈래 → 곁칸 (calc/types.py 의 FailureKind 와 TS 의 AssemblyFailure 그대로):
      missing_input               field, reason
      invalid_input               field, value, reason
      unsupported_combustion_type combustionType
      fuel_state_unknown          fuel, reason
      fuel_state_conflict         fuel, given, mapped, basis, locator
      sector_not_defined          ksicCode, division
      sector_ambiguous            ksicCode, division, candidates, notes, locator
      tier_combination_invalid    reason, locator
      tier_requires_site_values   parameter, tier, reason
      tier_minimum_not_found      fuelState, group, parameter, found
      fuel_name_not_mapped        fuel, table, parameter
      fuel_name_ambiguous         fuel, table, ipccNames
      record_not_found            parameter, criteria
      record_ambiguous            parameter, criteria, recordIds
      record_value_missing        parameter, recordId, valueStatus
      invalid_value_raw           parameter, recordId, valueRaw
      unit_notation_unknown       parameter, recordId, unit
      guideline_version_mismatch  recordId, recordVersion, guidelineVersion
      record_condition_unknown    recordId, field, value          (구매 전력에만)
    """

    kind: FailureKind
    field: str | None = None
    reason: str | None = None
    value: str | None = None
    combustionType: str | None = None
    fuel: str | None = None
    given: str | None = None
    mapped: str | None = None
    basis: str | None = None
    locator: str | None = None
    ksicCode: str | None = None
    division: str | None = None
    candidates: list[str] | None = None
    notes: list[str] | None = None
    parameter: str | None = None
    tier: int | None = None
    fuelState: str | None = None
    group: str | None = None
    found: int | None = None
    table: str | None = None
    ipccNames: list[str] | None = None
    criteria: dict[str, str] | None = None
    recordIds: list[str] | None = None
    recordId: str | None = None
    valueStatus: str | None = None
    valueRaw: str | None = None
    unit: str | None = None
    recordVersion: str | None = None
    guidelineVersion: str | None = None


class SourceLicenseOut(Schema):
    sourceId: str
    licenseStatus: LicenseStatus
    licenseName: str
    licenseUrl: str
    licenseNote: str | None


class AssembleOut(Schema):
    ok: bool
    value: CombustionAssembledOut | None = Field(default=None, description="ok 가 true 일 때만 있다")
    failure: FailureOut | None = Field(default=None, description="ok 가 false 일 때만 있다")
    licenses: list[SourceLicenseOut] = Field(description="조립에 쓰인 낱줄들의 출처와 이용 조건. 실패면 빈 목록")


class PurchasedEmissionFactorOut(Schema):
    gas: Literal["CO2", "CH4", "N2O", "CO2e"]
    value: str
    massUnit: str


class PurchasedEnergyFactorOut(Schema):
    kind: Literal["purchased_energy"]
    id: str
    version: str
    source: ProvenanceOut
    energyType: Literal["electricity"]
    variant: str
    # GIR 공표의 단년 값일 때만 있다.
    year: int | None = None
    perUnit: str
    emissionFactors: list[PurchasedEmissionFactorOut]


class ElectricityParameterEvidenceOut(Schema):
    gas: Literal["CO2", "CH4", "N2O", "CO2e"]
    recordId: str
    sourceId: str
    sourceName: str
    sourceVersion: str
    url: str
    retrieved: str
    fileSha256: str
    locator: str
    valueRaw: str
    value: str
    unit: str
    conditions: dict[str, str]


class SourceChoiceOut(Schema):
    value: Literal["guideline_table69", "gir_published"]
    basis: Literal["input"]
    note: str


class ElectricityEvidenceOut(Schema):
    request: dict[str, Any] = Field(description="조립 조건을 그대로 되적은 것. 출처 선택은 입력이다")
    co2eGwp: str | None = Field(description="CO2e 계수에 이미 들어 있는 GWP(공표문의 글). 기체별이면 null")
    sourceChoice: SourceChoiceOut
    rule: str
    parameters: list[ElectricityParameterEvidenceOut]


class ElectricityAssembledOut(Schema):
    factor: PurchasedEnergyFactorOut
    evidence: ElectricityEvidenceOut


class AssembleElectricityOut(Schema):
    ok: bool
    value: ElectricityAssembledOut | None = Field(default=None, description="ok 가 true 일 때만 있다")
    failure: FailureOut | None = Field(default=None, description="ok 가 false 일 때만 있다")
    licenses: list[SourceLicenseOut] = Field(description="조립에 쓰인 낱줄들의 출처와 이용 조건. 실패면 빈 목록")
