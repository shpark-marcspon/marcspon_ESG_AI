"""결과 꼴 셋의 정의: scope12.result@2 · scope3.llm-first.result@2 · scope3.colab.result@1. TypedDict(모르는 키 금지)
→ JSON 스키마.

이 파일이 inventory 결과 JSON 의 원천이다(밴드 RR1, sid:MARC-ENT-268). 경로(service/schemas/inventory.py 와
service/apis/inventory.py)가 이 TypedDict 를 응답 꼴로 그대로 쓰고, 그 이름이 OpenAPI components 이름이 된다 —
이름을 바꾸면 generated/ 가 바뀐다. 경로가 쌍둥이 Schema 를 다시 적게 되면 이 문장은 거짓이다.
키의 이름·차례는 serializer 의 글자를 따른다(engines/scope12/engine_1/serialize.py,
engines/scope3/llm_first_1/serialize.py, engines/scope3/llm_first_1/ranking.py 의 to_json 둘,
engines/scope3/colab_157/serialize.py — 손으로 남고 tests/contracts/test_shapes.py 가 이 꼴과 견준다).
응답 본문은 serializer 의 글자 그대로다(ninja 는 이 꼴의 차례로 dump 하므로 차례가 어긋나면 본문이 바뀐다 —
tests/test_route_bodies.py 가 바이트로 잰다). scope3.colab.result@1 은 GET …/scope3/runs/{run_id}/result 의 응답 꼴이다
(service/apis/scope3_runs.py — 경로가 schema_version 글자 하나로 저장된 결과를 고른다).
「없음」이 값인 칸은 늘 있는 키의 `X | None`, 「없으면 키를 뺀다」는 칸은 NotRequired. 수는 실제 꼴대로 —
십진은 문자열(co2e·activityAmount 등), 비용·점수는 float. 갈래는 판별 칸(kind·status)으로 가른다.
고정 파일은 inventory/tests/data/flow-shapes/<결과 꼴 id>.schema.json 이고 test_flow_shapes.py 가 글자로 견준다.
꼴을 바꾸면 새 판이다(scope12 는 밴드 RR1 에서 @1 → @2). 다만 NotRequired 칸을 더하기만 하면 같은 판이다 — 그 칸이 없는
옛 결과도 그대로 맞는다(scope3.colab.result@1 의 줄 input, S3R2 — MARC-ISSUE-524).

이 파일은 흐름 등록 길(apps.py 의 ready → registration.py)에서 들이지 않는다. API 시작(config/api.py 가 경로를
import)에는 실린다 — 경로의 응답 꼴이다.
흐름도 run_flow 도 결과를 꼴로 검사하지 않는다 — 저장하는 쪽(실행기)이 RESULT_SHAPES 로 검사할 수 있게 둔다.
"""

from collections.abc import Mapping
from typing import Annotated, Final, Literal, NotRequired, TypedDict

from pydantic import ConfigDict, Field, TypeAdapter, with_config

FORBID: Final = ConfigDict(extra="forbid")

# ── 엔진의 낱말(두 벌) ──────────────────────────────────────────────────────────────────────────
# 계약은 엔진을 import 하지 않는다(.importlinter inventory-contracts-not-engines, 밴드 EN1). 그래서 결과 꼴이 쓰는
# 엔진의 Literal 17개(와 코랩 판의 일곱 — 아래 scope3.colab.result@1 절)를 같은 값·차례로 여기 다시 적는다. 엔진과
# 어긋나면 tests/flows/test_vocab.py 가 빨개진다.
# 엔진 Scope 1·2(engines/scope12/engine_1): types.py 의 일곱과 aggregate.py 의 GroupKey
Gas = Literal["CO2", "CH4", "N2O"]
FactorGas = Literal["CO2", "CH4", "N2O", "CO2e"]
CalorificBasis = Literal["net", "gross"]
FacilityUse = Literal["power_generation", "other"]
FactorKind = Literal["combustion", "purchased_energy"]
SourceType = Literal["stationary_combustion", "mobile_combustion", "purchased_electricity", "purchased_heat"]
Scope = Literal[1, 2]
GroupKey = Literal["orgUnit", "period", "scope", "sourceType"]
# 엔진 Scope 3(engines/scope3/llm_first_1): types.py 의 여섯, calc.py 의 NumberField, llm_steps.py 의 FailureKind,
# shortlister.py 의 ShortlistMethod
SupportedCategory = Literal[1, 2, 4, 6, 7, 9]
Confidence = Literal["high", "medium", "low"]
Basis = Literal["activity", "distance", "spend"]
CandidateBasis = Literal["physical", "spend"]
FallbackReason = Literal["no_activity_candidates", "unit_mismatch", "llm_found_none_suitable"]
LicenseStatus = Literal["ok", "disputed", "unverified"]
NumberField = Literal["quantity", "amount", "weightKg", "distanceKm", "valueRaw", "multiplier"]
FailureKind = Literal["schema_mismatch", "refusal", "truncated", "provider_error", "timeout", "budget_exceeded"]
ShortlistMethod = Literal["lexical-v1", "lexical-v2"]

# ── scope12.result@2 (engines/scope12/engine_1/serialize.py 의 output_to_dict 에 schemaVersion) ──────────────────


@with_config(FORBID)
class CitedSource(TypedDict):
    kind: Literal["cited"]
    title: str
    url: str
    checkedOn: str
    locator: NotRequired[str]
    note: NotRequired[str]


@with_config(FORBID)
class DefinitionSource(TypedDict):
    kind: Literal["definition"]
    note: str


@with_config(FORBID)
class SyntheticSource(TypedDict):
    kind: Literal["synthetic"]
    note: str


Source = Annotated[CitedSource | DefinitionSource | SyntheticSource, Field(discriminator="kind")]

# "from" 은 파이썬 낱말이라 이 칸을 가진 꼴 셋은 함수 꼴로 짓고 설정(FORBID)은 다음 줄에서 단다(데코레이터 자리가 없다).
# 키의 차례는 serializer 의 글자 그대로다(engines/scope12/engine_1/serialize.py 의
# unit_conversion_to_dict·failure_to_dict).
# 바탕 꼴에서 물려받게 하면 물려받은 칸이 앞으로 간다(@1 의 어긋남: from·to·kind).
UnitConversionJson = TypedDict("UnitConversionJson", {"from": str, "to": str, "factor": str, "source": Source})
with_config(FORBID)(UnitConversionJson)


@with_config(FORBID)
class InvalidActivityFailure(TypedDict):
    kind: Literal["invalid_activity"]
    field: str
    value: str
    reason: str


@with_config(FORBID)
class FactorNotFoundFailure(TypedDict):
    kind: Literal["factor_not_found"]
    criteria: dict[str, str]


@with_config(FORBID)
class FactorAmbiguousFailure(TypedDict):
    kind: Literal["factor_ambiguous"]
    criteria: dict[str, str]
    candidateIds: list[str]


@with_config(FORBID)
class FactorKindMismatchFailure(TypedDict):
    kind: Literal["factor_kind_mismatch"]
    factorId: str
    expected: FactorKind
    actual: FactorKind


@with_config(FORBID)
class FactorIncompleteFailure(TypedDict):
    kind: Literal["factor_incomplete"]
    factorId: str
    reason: str


@with_config(FORBID)
class InvalidReferenceValueFailure(TypedDict):
    kind: Literal["invalid_reference_value"]
    where: str
    value: str


@with_config(FORBID)
class CalorificBasisMismatchFailure(TypedDict):
    kind: Literal["calorific_basis_mismatch"]
    factorId: str
    required: CalorificBasis
    actual: CalorificBasis


UnitConversionNotFoundFailure = TypedDict(
    "UnitConversionNotFoundFailure",
    {"kind": Literal["unit_conversion_not_found"], "from": str, "to": str, "context": str},
)
with_config(FORBID)(UnitConversionNotFoundFailure)

UnitConversionAmbiguousFailure = TypedDict(
    "UnitConversionAmbiguousFailure",
    {"kind": Literal["unit_conversion_ambiguous"], "from": str, "to": str, "factors": list[str]},
)
with_config(FORBID)(UnitConversionAmbiguousFailure)


@with_config(FORBID)
class GwpSetNotFoundFailure(TypedDict):
    kind: Literal["gwp_set_not_found"]
    gwpSetId: str


@with_config(FORBID)
class GwpSetAmbiguousFailure(TypedDict):
    kind: Literal["gwp_set_ambiguous"]
    gwpSetId: str


@with_config(FORBID)
class GwpValueMissingFailure(TypedDict):
    kind: Literal["gwp_value_missing"]
    gwpSetId: str
    gas: Gas


FailureJson = Annotated[
    InvalidActivityFailure
    | FactorNotFoundFailure
    | FactorAmbiguousFailure
    | FactorKindMismatchFailure
    | FactorIncompleteFailure
    | InvalidReferenceValueFailure
    | CalorificBasisMismatchFailure
    | UnitConversionNotFoundFailure
    | UnitConversionAmbiguousFailure
    | GwpSetNotFoundFailure
    | GwpSetAmbiguousFailure
    | GwpValueMissingFailure,
    Field(discriminator="kind"),
]


# 산정등급. 엔진(engines/scope12/engine_1/types.py 의 ParameterTiers)은 int 로 들고 있고 값은 1~4 뿐이다.
Tier = Literal[1, 2, 3, 4]


@with_config(FORBID)
class ParameterTiersJson(TypedDict):
    calorific: Tier
    co2: Tier
    nonCo2: Tier
    oxidation: Tier | None


@with_config(FORBID)
class StepJson(TypedDict):
    """한 연산 단계. 손으로 따라갈 수 있게 식과 결과를 문자열로 싣는다. conversion 은 환산 단계에만 있다."""

    label: str
    formula: str
    result: str
    unit: str
    conversion: NotRequired[UnitConversionJson]


@with_config(FORBID)
class EvidenceFactorJson(TypedDict):
    id: str
    version: str
    source: Source


@with_config(FORBID)
class EvidenceGwpSetJson(TypedDict):
    id: str
    label: str
    source: Source


@with_config(FORBID)
class EvidenceJson(TypedDict):
    factor: EvidenceFactorJson
    gwpSet: EvidenceGwpSetJson
    calorificBasis: CalorificBasis | None
    oxidationFactor: str | None
    sector: str | None
    parameterTiers: ParameterTiersJson | None
    facilityUse: FacilityUse | None
    steps: list[StepJson]


@with_config(FORBID)
class EnergyJson(TypedDict):
    value: str
    unit: str


@with_config(FORBID)
class GasResultJson(TypedDict):
    gas: FactorGas
    mass: str
    massUnit: Literal["t"]
    gwp: Annotated[str | None, Field(description="적용한 GWP. 이미 환산된 계수(CO2e)면 null")]
    co2e: str


@with_config(FORBID)
class RowOkJson(TypedDict):
    rowId: str
    orgUnit: str
    period: str
    scope: Scope
    sourceType: SourceType
    status: Literal["ok"]
    co2e: Annotated[str, Field(description="반올림하지 않은 정확한 값 (tCO2eq)")]
    unit: Literal["tCO2eq"]
    energy: Annotated[EnergyJson | None, Field(description="연소일 때만. 구매 전력·열은 null")]
    gases: list[GasResultJson]
    evidence: EvidenceJson


@with_config(FORBID)
class RowFailedJson(TypedDict):
    rowId: str
    orgUnit: str
    period: str
    scope: Scope | None
    sourceType: SourceType | None
    status: Literal["failed"]
    failure: FailureJson


RowJson = Annotated[RowOkJson | RowFailedJson, Field(discriminator="status")]


@with_config(FORBID)
class TotalsJson(TypedDict):
    co2e: Annotated[str, Field(description="성공한 행의 정확한 합 (tCO2eq). complete 가 false 면 부분합이다")]
    co2eByGas: dict[FactorGas, str]
    okRowCount: int
    failedRowIds: list[str]
    complete: bool


@with_config(FORBID)
class GroupJson(TypedDict):
    key: dict[GroupKey, str]
    co2e: str
    co2eByGas: dict[FactorGas, str]
    okRowCount: int
    failedRowIds: list[str]
    complete: bool


@with_config(FORBID)
class AggregationJson(TypedDict):
    by: list[GroupKey]
    groups: list[GroupJson]
    total: TotalsJson


@with_config(FORBID)
class Scope12Body(TypedDict):
    gwpSetId: str
    rows: list[RowJson]
    aggregation: AggregationJson


# Scope12Body 를 물려받지 않는다: 물려받으면 schemaVersion 이 맨 끝으로 간다(serializer 는 맨 앞에 둔다).
# 둘의 칸이 같은지는 tests/test_route_shapes.py 가 묶는다.
@with_config(FORBID)
class Scope12Result(TypedDict):
    """scope12.result@2."""

    schemaVersion: Literal["scope12.result@2"]
    gwpSetId: str
    rows: list[RowJson]
    aggregation: AggregationJson


# ── scope3.llm-first.result@2 (flows/scope3_llm_first_1.py 가 engines/scope3/llm_first_1/serialize.py 로 조립한 것) ─


@with_config(FORBID)
class AdjustmentSourceJson(TypedDict):
    url: str
    checkedOn: str


@with_config(FORBID)
class AdjustmentJson(TypedDict):
    currency: str
    targetCurrency: str
    targetPriceYear: int
    multiplier: str
    synthetic: bool
    source: AdjustmentSourceJson | None


@with_config(FORBID)
class ComputedCalc(TypedDict):
    status: Literal["computed"]
    co2e: str
    unit: Literal["tCO2eq"]
    factorId: str
    factorValueRaw: str
    factorUnit: str
    activityAmount: str
    formula: str
    adjustment: AdjustmentJson | None
    synthetic: bool


@with_config(FORBID)
class NeedsDistanceCalc(TypedDict):
    status: Literal["needs_distance"]
    factorId: str


@with_config(FORBID)
class MissingQuantityCalc(TypedDict):
    status: Literal["missing_quantity"]
    factorId: str


@with_config(FORBID)
class MissingAmountCalc(TypedDict):
    status: Literal["missing_amount"]
    factorId: str


@with_config(FORBID)
class NeedsCurrencyAdjustmentCalc(TypedDict):
    status: Literal["needs_currency_adjustment"]
    factorId: str
    currency: str | None
    targetCurrency: str
    targetPriceYear: int


@with_config(FORBID)
class InvalidNumberCalc(TypedDict):
    status: Literal["invalid_number"]
    factorId: str
    field: NumberField


@with_config(FORBID)
class UnitMismatchCalc(TypedDict):
    status: Literal["unit_mismatch"]
    factorId: str
    rowUnit: str | None
    factorUnit: str


@with_config(FORBID)
class UnsupportedFactorUnitCalc(TypedDict):
    status: Literal["unsupported_factor_unit"]
    factorId: str
    factorUnit: str


@with_config(FORBID)
class NotCalculatedCalc(TypedDict):
    status: Literal["not_calculated"]
    reason: str


CalcJson = Annotated[
    ComputedCalc
    | NeedsDistanceCalc
    | NeedsCurrencyAdjustmentCalc
    | MissingQuantityCalc
    | MissingAmountCalc
    | InvalidNumberCalc
    | UnitMismatchCalc
    | UnsupportedFactorUnitCalc
    | NotCalculatedCalc,
    Field(discriminator="status"),
]


@with_config(FORBID)
class PickJson(TypedDict):
    factorId: str
    reason: str
    confidence: Confidence


@with_config(FORBID)
class ClassificationJson(TypedDict):
    category: SupportedCategory | Literal["other"]
    keywords: list[str]
    confidence: Confidence
    reason: str


@with_config(FORBID)
class LlmFailureJson(TypedDict):
    kind: FailureKind
    detail: str


@with_config(FORBID)
class MemoryEntryJson(TypedDict):
    key: str
    category: SupportedCategory
    factorId: str
    confirmedBy: str
    confirmedAt: str
    label: NotRequired[str]


@with_config(FORBID)
class BasisJson(TypedDict):
    used: Basis
    fellBack: bool
    fallbackReason: FallbackReason | None


@with_config(FORBID)
class CandidateStatsJson(TypedDict):
    total: int
    shown: int
    lexicalMatches: int
    method: ShortlistMethod


@with_config(FORBID)
class RecommendedDecision(TypedDict):
    status: Literal["recommended"]
    source: Literal["memory", "llm"]
    category: SupportedCategory
    picks: list[PickJson]
    basis: BasisJson
    classification: ClassificationJson | None
    memoryEntry: MemoryEntryJson | None
    candidates: CandidateStatsJson | None


@with_config(FORBID)
class MemoryFactorMissingDecision(TypedDict):
    status: Literal["memory_factor_missing"]
    source: Literal["memory"]
    memoryEntry: MemoryEntryJson


@with_config(FORBID)
class MemoryCategoryMismatchDecision(TypedDict):
    status: Literal["memory_category_mismatch"]
    source: Literal["memory"]
    memoryEntry: MemoryEntryJson
    factorCategories: list[int]


@with_config(FORBID)
class MemoryFactorExcludedDecision(TypedDict):
    status: Literal["memory_factor_excluded"]
    source: Literal["memory"]
    memoryEntry: MemoryEntryJson
    licenseStatus: LicenseStatus


@with_config(FORBID)
class ClassificationFailedDecision(TypedDict):
    status: Literal["classification_failed"]
    source: Literal["llm"]
    llm: LlmFailureJson


@with_config(FORBID)
class UnsupportedCategoryDecision(TypedDict):
    status: Literal["unsupported_category"]
    source: Literal["llm"]
    classification: ClassificationJson


@with_config(FORBID)
class NoCandidatesDecision(TypedDict):
    status: Literal["no_candidates"]
    source: Literal["llm"]
    category: SupportedCategory
    classification: ClassificationJson
    physical: FallbackReason


@with_config(FORBID)
class NoSuitableFactorDecision(TypedDict):
    status: Literal["no_suitable_factor"]
    source: Literal["llm"]
    category: SupportedCategory
    classification: ClassificationJson
    physical: FallbackReason


@with_config(FORBID)
class RecommendationFailedDecision(TypedDict):
    status: Literal["recommendation_failed"]
    source: Literal["llm"]
    category: SupportedCategory
    classification: ClassificationJson
    basis: CandidateBasis
    llm: LlmFailureJson


DecisionJson = Annotated[
    RecommendedDecision
    | MemoryFactorMissingDecision
    | MemoryCategoryMismatchDecision
    | MemoryFactorExcludedDecision
    | ClassificationFailedDecision
    | UnsupportedCategoryDecision
    | NoCandidatesDecision
    | NoSuitableFactorDecision
    | RecommendationFailedDecision,
    Field(discriminator="status"),
]


@with_config(FORBID)
class LexicalEvidenceJson(TypedDict):
    rank: int
    score: float
    matchedTerms: list[str]


@with_config(FORBID)
class CandidateEvidenceJson(TypedDict):
    id: str
    lexical: NotRequired[LexicalEvidenceJson]
    rrfScore: NotRequired[float]
    rank: int


@with_config(FORBID)
class ShortlistTraceJson(TypedDict):
    basis: CandidateBasis
    method: ShortlistMethod
    total: int
    shownIds: list[str]
    evidence: list[CandidateEvidenceJson]
    failure: None


@with_config(FORBID)
class Scope3RowJson(TypedDict):
    rowId: str
    groupKey: str
    calc: CalcJson


@with_config(FORBID)
class Scope3GroupJson(TypedDict):
    key: str
    rowIds: list[str]
    decision: DecisionJson
    shortlists: list[ShortlistTraceJson]


@with_config(FORBID)
class PromptUsageJson(TypedDict):
    calls: int
    attempts: int
    costUsd: float


@with_config(FORBID)
class UsageJson(TypedDict):
    calls: int
    attempts: int
    costUsd: float
    byPrompt: dict[str, PromptUsageJson]


@with_config(FORBID)
class ShortlistInfoJson(TypedDict):
    method: ShortlistMethod
    description: str


@with_config(FORBID)
class Scope3Done(TypedDict):
    """scope3.llm-first.result@2 — 끝까지 돈 것."""

    schemaVersion: Literal["scope3.llm-first.result@2"]
    status: Literal["done"]
    rows: list[Scope3RowJson]
    groups: list[Scope3GroupJson]
    usage: UsageJson
    shortlist: ShortlistInfoJson


@with_config(FORBID)
class AdjustmentProblemJson(TypedDict):
    index: int
    kind: Literal["invalid_multiplier", "missing_source"]
    message: str


@with_config(FORBID)
class RejectedJson(TypedDict):
    kind: Literal["duplicate_row_id", "invalid_adjustments"]
    rowId: str | None
    problems: list[AdjustmentProblemJson]


@with_config(FORBID)
class Scope3Rejected(TypedDict):
    """scope3.llm-first.result@2 — 입력이 틀려 한 묶음도 판단하지 않은 것."""

    schemaVersion: Literal["scope3.llm-first.result@2"]
    status: Literal["rejected"]
    rejected: RejectedJson


Scope3Result = Annotated[Scope3Done | Scope3Rejected, Field(discriminator="status")]

# ── scope3.colab.result@1 (engines/scope3/colab_157/serialize.py 의 result_to_dict — 흐름 scope3.colab@157) ──────────
# 처분 ⑦: 수 칸(amount·spendKrw·value·co2e·expectedCo2e)은 코랩과 같은 float 셈의 repr(float) 왕복 표기 — 십진
# 정확값이 아니고 `1e-05` 같은 지수 표기도 온다. NaN·inf·없음은 null 이고 그 줄의 missing 이 까닭을 적는다.
# 엔진 colab_157/purchase.py 의 Literal 셋(ColabOrigin·ColabStep·ColabMissing)과 colab_157/activity.py 의 둘
# (ColabActivityKind·ColabActivityStep — S3C-b1, 거리 값은 S3C-b2a 에서 더함), colab_157/factor_book.py 의 하나
# (FactorSheetHow — S3C-b2a)를 다시 적는다.
ColabOrigin = Literal["rule", "ai", "estimate"]
ColabStep = Literal["group", "factor", "spend"]
ColabMissing = Literal["amount", "factor", "factorValue"]
ColabActivityKind = Literal[
    "transport_spend", "travel_spend", "waste", "transport_distance", "travel_distance", "commute"
]
ColabActivityStep = Literal["mapping", "unit", "fx", "factor", "mode", "distance"]
FactorSheetHow = Literal["reloaded", "kept_initial", "empty", "initial"]
# 결과 시트 일곱의 줄 kind(S3C-c1a — colab_157/energy.py 의 ColabEnergyKind 를 다시 적는다. C3·C8·C13 은 c1a, 넷은 c1b)
ColabEnergyKind = Literal[
    "fuel_energy", "leased_asset", "leased_out_asset", "product_use", "product_eol", "franchise", "investment"
]


@with_config(FORBID)
class ColabFactorJson(TypedDict):
    """대표 계수(구매_USEPA 의 NAICS Title 과 보고연도 원화 열의 값). source 는 코랩 후보의 source 글자."""

    title: str | None
    value: str | None
    unit: Literal["kgCO2e/KRW"]
    column: str | None
    source: str


@with_config(FORBID)
class ColabRecommendationJson(TypedDict):
    title: str
    value: str | None
    expectedCo2e: str | None


@with_config(FORBID)
class ColabGroupLlmJson(TypedDict):
    """그룹 이름 LLM 한 번. answer 는 코랩이 쓴 글자(실패면 "Unknown"), reason 은 실패의 core.llm kind."""

    outcome: Literal["success", "truncated", "refusal", "failed"]
    answer: str
    reason: str | None


@with_config(FORBID)
class ColabGroupJson(TypedDict):
    key: str
    name: str
    reason: str
    family: str
    category: str
    llm: ColabGroupLlmJson | None


@with_config(FORBID)
class ColabOriginStepJson(TypedDict):
    step: ColabStep
    origin: ColabOrigin
    via: str


@with_config(FORBID)
class ColabRowInputJson(TypedDict):
    """그 줄의 입력 칸(MARC-ISSUE-524 — 템플릿 엑셀 줄의 글자를 다시 싣는다). 키 열여섯(짓는 쪽은 늘 다 싣는다), 그
    시트에 원천 열이 없거나 칸이 비면(빈 글·NaN·없음) null. useMonths 는 S3R3 에 더한 키라 검사에서 NotRequired 다 —
    그 전(키 열다섯)에 저장된 결과도 같은 판으로 통과한다(다시 셈 0, 없으면 null 취급).
    글은 글자 그대로(공백도 걷지 않음), 수는 repr(float)(정수 입력도 "13.0").
    원천은 처리기 key 별 코랩 결과 frame 의 열(표준화 이름 바꿈 뒤 — colab_157/serialize.py 의 원천 표):

    - country: 국가(C15 밖 전부)
    - site: 사업장(C1·C2·C3·C4·C5·C7·C9), C6-1·C6-2 는 출장주체(바꿈 뒤 「사업장」)
    - name: C1 품목명(상세 품목명/서비스명 — 그룹 이름으로 덮기 전) · C2 자산명(상세 자산명) · C4 자재명→제품명 ·
      C9 제품명→자재명 · C5 폐기물 종류→상세폐기물명(→ 는 카테고리에서 값이 든 첫 열) · C8·C13 자산명(임차·임대자산명)
      · C11·C12 제품명 · C14 프랜차이즈명 · C15 피투자기업명
    - vehicle: C4-2·C9-2 운송수단, C6-2 출장항목(바꿈 뒤 「이동수단」) — 지출 kind 의 mode 는 null 이라 입력 글을 여기
    - energy: C3 연료/에너지명 · C8·C13 에너지종류(바꿈 뒤 「에너지원」) · C11 에너지명 · C14 연료 종류
    - people: C6-1·C6-2·C7 인원수
    - buildingArea·usedArea: C8-2·C13-2 건물전체 면적·사용 면적
    - buildingPeople·ownPeople: C8-3·C13-3 건물전체 인원수·자사 인원수
    - productCount: C11 제품수량 · sales·weight·weightUnit: C12 판매량·제품중량·제품중량 단위 · stores: C14 가맹점 수
    - useMonths: C11 수명(개월) 혹은 평균 사용기간(개월)(바꿈 뒤 「수명(개월)」)
    """

    country: str | None
    site: str | None
    name: str | None
    vehicle: str | None
    energy: str | None
    people: str | None
    buildingArea: str | None
    usedArea: str | None
    buildingPeople: str | None
    ownPeople: str | None
    productCount: str | None
    sales: str | None
    weight: str | None
    weightUnit: str | None
    stores: str | None
    useMonths: NotRequired[str | None]  # S3R3 — 키 열다섯 판(093f16c3~S3R3)의 저장 결과도 통과(MARC-ENT-539)


@with_config(FORBID)
class ColabRowJson(TypedDict):
    """C1·C2 의 줄 하나. co2e(tCO2eq)·formula·추천의 expectedCo2e 는 코랩 후처리(구매금액 × 계수 / 1000) 뒤의 값."""

    rowId: str
    kind: Literal["purchase"]  # 지출·폐기물 줄(ColabActivityRowJson)과 가르는 판별 칸(S3C-b1 에서 더함)
    month: int | None
    amount: str | None
    spendKrw: str | None
    spendNote: str
    factor: ColabFactorJson
    co2e: str | None
    unit: Literal["tCO2eq"]
    formula: str
    recommendations: list[ColabRecommendationJson]
    group: ColabGroupJson
    origin: ColabOrigin | None
    originSteps: list[ColabOriginStepJson]
    missing: list[ColabMissing]
    input: NotRequired[ColabRowInputJson]  # S3R2 — 이 칸 전에 저장된 결과에는 없다(같은 판, 다시 셈 0)


@with_config(FORBID)
class ColabActivityAmountJson(TypedDict):
    """활동량. Spend: 금액(value·unit "KRW")과 셈의 기준 금액(USD 갈래면 USD), 폐기물: 처리량(입력 단위)과 kg 값·
    단위환산비고. unit·baseUnit 은 코랩 글자."""

    value: str | None
    unit: str
    baseValue: str | None
    baseUnit: str
    note: str | None


@with_config(FORBID)
class ColabActivityFactorJson(TypedDict):
    """쓴 계수(계수 책의 시트·제목·값·단위·열·NAICS 코드). 폐기물은 title·code 가 null(코랩이 이름을 안 낸다)."""

    sheet: str
    title: str | None
    value: str | None
    unit: str
    column: str | None
    code: str | None
    sourceText: NotRequired[str]  # S3Q1 — 경로가 읽을 때 붙이는 책 머리 출처 글(저장 결과에는 없다, 엔진 0줄)


@with_config(FORBID)
class ColabBiogenicJson(TypedDict):
    """C5 의 화석·생물기원 나눔(tCO2eq). co2e 는 fossilCo2e 와 같은 화석기원 몫이다."""

    fossilCo2e: str | None
    biogenicCo2e: str | None
    fcf: str | None
    note: str | None


@with_config(FORBID)
class ColabModeJson(TypedDict):
    """정규화한 이동·운송수단과 그 산정 출처. 줄 origin 에 넣는지는 kind 별이다 — 지출 kind(C6-2 정규화이동수단)는 넣지
    않고, 거리 kind(transport_distance·travel_distance·commute — 운송수단이 계수를 정한다)는 넣는다."""

    value: str
    origin: ColabOrigin


@with_config(FORBID)
class ColabActivityOriginStepJson(TypedDict):
    step: ColabActivityStep
    origin: ColabOrigin
    via: str


@with_config(FORBID)
class ColabDistanceJson(TypedDict):
    """거리 줄의 거리(S3C-b2a). km 는 셈에 쓴 거리(두 번째 길 포함, repr(float)) — 코랩 결과 칸 「운송거리(km)」(입력값
    이거나 본 고리 값, None 가능)와 다를 수 있다. via 는 거리의 길(input·geocode·ai_straight·ai_road·none, 공항 AI 로
    지점을 바꿨으면 끝에 +airport — 거리 kind 가 더할 수 있다). geoMode 는 거리 길에 넘긴 mode(운송 표준코드 그대로,
    템플릿 입력 거리면 null). departure·arrival 은 원문. roundTrip(거리왕복계수 1·2)·people·trips·workdays 는 출장·통근
    줄 몫이고 C4-1·C9-1 은 null."""

    km: str | None
    via: str
    geoMode: str | None
    departure: str | None
    arrival: str | None
    roundTrip: str | None
    people: str | None
    trips: str | None
    workdays: str | None


@with_config(FORBID)
class ColabActivityRowJson(TypedDict):
    """C4-2·C9-2·C6-2·C5 의 줄 하나(S3C-b1)와 거리 줄(C4-1·C9-1 — S3C-b2a). co2e(tCO2eq)·formula 는 코랩 결과 행의
    「배출량(tCO2e)」·「계산식」(C6 은 후처리 뒤, C5 는 화석기원). origin 은 숫자에 닿는 단계 가운데 가장 약한 것,
    factor 단계가 없으면 null — 숫자에 닿는 단계는 kind 별이다: 지출·폐기물 kind 는 mapping·unit·fx·factor(mode 는
    넣지 않음), 거리 kind 는 거기에 mode·distance 를 더한다. distance 는 거리 kind 만(그 밖은 null)."""

    rowId: str
    kind: ColabActivityKind
    month: int | None
    activity: ColabActivityAmountJson
    factor: ColabActivityFactorJson
    co2e: str | None
    unit: Literal["tCO2eq"]
    formula: str
    treatment: str | None
    biogenic: ColabBiogenicJson | None
    mode: ColabModeJson | None
    distance: ColabDistanceJson | None
    origin: ColabOrigin | None
    originSteps: list[ColabActivityOriginStepJson]
    missing: list[ColabMissing]
    input: NotRequired[ColabRowInputJson]  # S3R2 — ColabRowJson 과 같다


@with_config(FORBID)
class ColabEnergyMatchJson(TypedDict):
    """에너지 계수 사슬의 매칭(코랩 `_LAST_EF_MATCH_INFO["energy"]` — C11·C14 결과의 EF매핑방식·EF매핑점수).
    type 은 코랩 match_type 글자(exact_raw·alias_exact·alias_contains·contains·fuzzy·unit_priority_alias·
    legacy_lookup·not_found …), score 는 그 점수(repr(float), legacy_lookup 이면 null)."""

    type: str
    score: str | None


@with_config(FORBID)
class ColabAllocationJson(TypedDict):
    """임차·임대 자산(C8·C13)의 배분. method 는 코랩 「산정방식」(에너지사용량·면적배분·인원배분), buildingTotal 은
    「건물전체사용량」, areaRatio·personRatio 는 「면적비율」·「인원비율」(그 방식이 아니면 null)."""

    method: str
    buildingTotal: str | None
    areaRatio: str | None
    personRatio: str | None


@with_config(FORBID)
class ColabProductUseJson(TypedDict):
    """판매제품 사용(C11). years 는 코랩 「사용기간(년)」, totalUsage 는 「총사용량」(제품수량 × 제품당 사용량 ×
    사용기간)."""

    years: str | None
    totalUsage: str | None


@with_config(FORBID)
class ColabInvestmentJson(TypedDict):
    """투자(C15). share 는 지분율(%), scope1·scope2 는 피투자기업 배출량(입력 칸의 수)."""

    share: str | None
    scope1: str | None
    scope2: str | None


C12Treatment = Literal["매립", "소각", "재활용"]
"""C12 처리방법 셋(엔진 C12_TREATMENTS 와 같은 글자·차례 — 「기타」 칸은 엔진에 없다)."""
C12Branch = Literal["code", "name", "average"]
"""C12 계수를 고른 길(엔진 C12Factor.branch)."""


@with_config(FORBID)
class ColabC12PartJson(TypedDict):
    """C12 처리방법 하나(S3Q1). share 는 0~1 수(엔진 `_pct` 뒤 — 웹이 %), factor 는 kgCO2eq/kg(비중이 하나도 없는 줄은
    처리방법 평균), used 는 가중에 들었는가. 둘 다 repr(float), NaN·없음은 null."""

    treatment: C12Treatment
    share: str | None
    factor: str | None
    used: bool


@with_config(FORBID)
class ColabC12TreatmentsJson(TypedDict):
    """C12 줄의 처리방법별 값(S3Q1 — 셈에 닿지 않는 보기 칸). shareTotal 은 used 비중의 합(표시용, 비중이 하나도 없으면
    null), parts 는 셋(엔진 차례). 가중 배출계수는 줄의 factor.value 다."""

    branch: C12Branch
    shareTotal: str | None
    parts: list[ColabC12PartJson]


@with_config(FORBID)
class ColabEnergyRowJson(TypedDict):
    """결과 시트 일곱(C3·C8·C11·C12·C13·C14·C15 — S3C-c1a 에서 세움)의 줄 하나. 칸 꼴은 ColabActivityRowJson 을
    본뜬다. activity 는 사용량(입력 값·단위)과 환산 뒤(baseValue·baseUnit), note 는 단위환산비고. factor 는 쓴
    계수(sheet 에너지·에너지_C3·폐기물_C12, title 은 EF매핑명, unit 은 EF단위 글자) — 계수를 쓰지 않는 kind
    (investment)면 null.
    co2e·formula 는 코랩 결과 행의 「배출량(tCO2e)」·「계산식」(C12 는 화석기원). match 는 에너지 계수 사슬을 탄 줄만,
    allocation 은 C8·C13, biogenic 은 C12, product 는 C11, investment 는 C15 만(그 밖은 null). origin 은 숫자에 닿는
    단계(unit·factor) 가운데 가장 약한 것, factor 단계가 없으면 null."""

    rowId: str
    kind: ColabEnergyKind
    month: int | None
    activity: ColabActivityAmountJson
    factor: ColabActivityFactorJson | None
    co2e: str | None
    unit: Literal["tCO2eq"]
    formula: str
    match: ColabEnergyMatchJson | None
    allocation: ColabAllocationJson | None
    biogenic: ColabBiogenicJson | None
    product: ColabProductUseJson | None
    investment: ColabInvestmentJson | None
    origin: ColabOrigin | None
    originSteps: list[ColabActivityOriginStepJson]
    missing: list[ColabMissing]
    treatments: NotRequired[ColabC12TreatmentsJson]  # S3Q1 — product_eol 만, 이 칸 전 결과에는 없다(같은 판)
    input: NotRequired[ColabRowInputJson]  # S3R2 — ColabRowJson 과 같다


@with_config(FORBID)
class ColabProcessedSheetJson(TypedDict):
    sheet: str
    category: str
    status: Literal["processed"]
    rows: list[Annotated[ColabRowJson | ColabActivityRowJson | ColabEnergyRowJson, Field(discriminator="kind")]]


@with_config(FORBID)
class ColabNotTargetSheetJson(TypedDict):
    sheet: str
    status: Literal["not_target"]


@with_config(FORBID)
class ColabNotYetSupportedSheetJson(TypedDict):
    sheet: str
    category: str
    status: Literal["not_yet_supported"]
    band: Literal["S3C-b", "S3C-c"]


@with_config(FORBID)
class ColabEmptySheetJson(TypedDict):
    sheet: str
    category: str
    status: Literal["empty"]


@with_config(FORBID)
class ColabFailedSheetJson(TypedDict):
    sheet: str
    category: str
    status: Literal["failed"]
    error: str


ColabSheetJson = Annotated[
    ColabProcessedSheetJson
    | ColabNotTargetSheetJson
    | ColabNotYetSupportedSheetJson
    | ColabEmptySheetJson
    | ColabFailedSheetJson,
    Field(discriminator="status"),
]


@with_config(FORBID)
class ColabFactorBookJson(TypedDict):
    sheet: str
    column: str | None
    year: int
    reload: Literal["reloaded", "kept_initial"]
    reloadProblem: str | None


@with_config(FORBID)
class ColabFactorSheetJson(TypedDict):
    """계수 시트 하나의 읽기(S3C-b1, 거리 운송 계수 `운송` 은 S3C-b2a): 다시 읽음 / 첫 읽기를 그대로 씀 / 둘 다 비었음 /
    첫 읽기만 씀(initial — 맵을 첫 읽기로만 짓는 시트). header 는 쓴 머리글 줄(0부터), rows 는 읽힌 줄 수."""

    sheet: str
    read: FactorSheetHow
    header: int | None
    rows: int


@with_config(FORBID)
class Scope3ColabDone(TypedDict):
    """scope3.colab.result@1 — 끝까지 돈 것. llmCalls: 프롬프트 id → 갈래(success·failed:<kind> …) → 부른 수."""

    schemaVersion: Literal["scope3.colab.result@1"]
    status: Literal["done"]
    reportYear: int
    factorBook: ColabFactorBookJson
    factorSheets: list[ColabFactorSheetJson]
    sheets: list[ColabSheetJson]
    llmCalls: dict[str, dict[str, int]]


@with_config(FORBID)
class ColabRejectedJson(TypedDict):
    reason: Literal["reader_problem", "factor_book", "legacy_template"]
    detail: str


@with_config(FORBID)
class Scope3ColabRejected(TypedDict):
    """scope3.colab.result@1 — 템플릿을 못 읽음·계수 책을 못 지음·새 v1 템플릿이 아님."""

    schemaVersion: Literal["scope3.colab.result@1"]
    status: Literal["rejected"]
    rejected: ColabRejectedJson


Scope3ColabResult = Annotated[Scope3ColabDone | Scope3ColabRejected, Field(discriminator="status")]

RESULT_SHAPES: Final[
    Mapping[
        str,
        TypeAdapter[Scope12Result]
        | TypeAdapter[Scope3Done | Scope3Rejected]
        | TypeAdapter[Scope3ColabDone | Scope3ColabRejected],
    ]
] = {
    "scope12.result@2": TypeAdapter(Scope12Result),
    "scope3.llm-first.result@2": TypeAdapter[Scope3Done | Scope3Rejected](Scope3Result),
    "scope3.colab.result@1": TypeAdapter[Scope3ColabDone | Scope3ColabRejected](Scope3ColabResult),
}
"""결과 꼴 id → 검사기. validate_python(결과, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
