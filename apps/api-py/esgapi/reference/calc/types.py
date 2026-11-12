"""조립이 받는 값(계수 낱줄, 대응표)과 내놓는 값(조립된 계수와 근거, 또는 실패 갈래)의 꼴.

낱줄의 정본은 esg-lab 의 `schemas/factor.schema.json`, 대응표의 정본은 `schemas/factor-mapping.schema.json` 이다.
여기 dataclass 는 조립이 읽는 칸만 옮긴 부분 사본이다.

조립 조건(request)은 dataclass 가 아니라 **JSON 을 푼 값 그대로**(dict)다. 까닭: 빠진 칸·틀린 칸을 조립 함수가
스스로 가려 「무엇이 빠졌는가」를 실패 갈래로 돌려주기 때문이다(기본값이 없다는 것이 규칙이다).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal, get_args

type Json = dict[str, Any]

FuelState = Literal["고체", "기체", "액체"]
FacilityGroup = Literal["A", "B", "C"]
MappingBasis = Literal["guideline", "assumed"]

# ── 계수 낱줄 ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceRef:
    """낱줄이 어디서 왔는가. jsonl 의 `source{…}` 블록 그대로다."""

    id: str
    name: str
    url: str
    version: str
    retrieved: str
    file_name: str
    file_sha256: str
    locator: str


@dataclass(frozen=True)
class FactorRecord:
    """계수 표의 한 줄(조립이 읽는 칸).

    ★ `value`(float) 칸이 없다. 일부러다: 조립은 `value_raw`(출처 표기 그대로의 글자)만 읽는다.
    """

    id: str
    record_type: str
    name_original: str
    category_path: tuple[str, ...]
    value_raw: str | None
    value_status: str
    unit_numerator: str
    unit_denominator: str
    gas: str
    gas_basis: str
    heating_value_basis: str | None
    conditions: Mapping[str, str]
    source: SourceRef
    synthetic: bool = False


# ── 대응표 (mappings.kr-ets.json) ─────────────────────────────────────


@dataclass(frozen=True)
class Guideline:
    name: str
    version: str
    url: str


@dataclass(frozen=True)
class SectorEntry:
    key: str
    label: str
    ksic_divisions: tuple[str, ...]
    ch4_condition: str
    n2o_condition: str
    source_id: str
    locator: str


@dataclass(frozen=True)
class SectorException:
    code_prefix: str
    sector: str
    raw: str


@dataclass(frozen=True)
class SectorOverlap:
    division: str
    sectors: tuple[str, ...]
    exceptions: tuple[SectorException, ...]
    source_id: str
    locator: str


@dataclass(frozen=True)
class FuelNameEntry:
    table: str
    ipcc_name: str
    domestic_names: tuple[str, ...]
    basis: MappingBasis
    note: str | None
    source_id: str
    locator: str
    # 있으면 이 대응은 이 매개변수에만 쓰인다(부생연료 1·2호의 CO2 Tier 1). 없으면 그 표의 모든 매개변수.
    parameters: tuple[str, ...] | None = None


@dataclass(frozen=True)
class NationalNameEntry:
    """별표 12 안에서 발열량 표의 이름 → 배출계수 표의 이름(두 표가 같은 연료를 다르게 적을 때)."""

    fuel: str
    ef_name: str
    basis: MappingBasis
    note: str | None
    source_id: str
    locator: str


@dataclass(frozen=True)
class FuelStateEntry:
    fuel: str
    state: FuelState
    basis: MappingBasis
    quote: str
    note: str | None
    source_id: str
    locator: str


@dataclass(frozen=True)
class TierMinimumEntry:
    activity: str
    fuel_state: FuelState
    parameter: str
    group: FacilityGroup
    tier: int
    source_id: str
    locator: str


@dataclass(frozen=True)
class AssemblyMapping:
    guideline: Guideline
    sectors: tuple[SectorEntry, ...]
    sector_overlaps: tuple[SectorOverlap, ...]
    fuel_names: tuple[FuelNameEntry, ...]
    fuel_states: tuple[FuelStateEntry, ...]
    tier_minimums: tuple[TierMinimumEntry, ...]
    # 없는 대응표도 읽는다. 없으면 별표 12 의 두 표가 같은 이름을 쓰는 연료만 조립된다.
    national_ef_names: tuple[NationalNameEntry, ...] = ()


# ── 실패 갈래 ─────────────────────────────────────────────────────────

FailureKind = Literal[
    "missing_input",
    "invalid_input",
    "unsupported_combustion_type",
    "fuel_state_unknown",
    "fuel_state_conflict",
    "sector_not_defined",
    "sector_ambiguous",
    "tier_combination_invalid",
    "tier_requires_site_values",
    "tier_minimum_not_found",
    "fuel_name_not_mapped",
    "fuel_name_ambiguous",
    "record_not_found",
    "record_ambiguous",
    "record_value_missing",
    "invalid_value_raw",
    "unit_notation_unknown",
    "guideline_version_mismatch",
    # 구매 전력에만 있다
    "record_condition_unknown",
]
FAILURE_KINDS: Final[tuple[str, ...]] = get_args(FailureKind)


@dataclass(frozen=True)
class Failure:
    """조립하지 못한 까닭. `kind` 가 갈래의 이름이고 `fields` 는 갈래마다 다른 곁칸이다(TS 의 판별 유니온)."""

    kind: FailureKind
    fields: Mapping[str, Any] = field(default_factory=dict[str, Any])

    def to_json(self) -> Json:
        return {"kind": self.kind, **self.fields}


@dataclass(frozen=True)
class Assembled:
    """조립된 계수 한 건과 근거. 둘 다 JSON 꼴의 dict 다(camelCase)."""

    factor: Json
    evidence: Json

    def to_json(self) -> Json:
        return {"factor": self.factor, "evidence": self.evidence}


@dataclass(frozen=True)
class Ok[T]:
    value: T
    ok: Literal[True] = True


@dataclass(frozen=True)
class Failed:
    failure: Failure
    ok: Literal[False] = False


type Step[T] = Ok[T] | Failed
type AssemblyResult = Ok[Assembled] | Failed


def fail(kind: FailureKind, **fields: Any) -> Failed:
    return Failed(Failure(kind, fields))


def result_to_json(result: AssemblyResult) -> Json:
    """TS CLI 가 찍는 것과 같은 꼴: `{ok: true, value: {factor, evidence}}` / `{ok: false, failure}`."""
    if isinstance(result, Failed):
        return {"ok": False, "failure": result.failure.to_json()}
    return {"ok": True, "value": result.value.to_json()}


def text_of(value: object) -> str:
    """실패에 싣는 「받은 값」의 글자. 문자열은 그대로, 그 밖은 JSON 표기(TS 는 `String(value)` 였다)."""
    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return repr(value)
