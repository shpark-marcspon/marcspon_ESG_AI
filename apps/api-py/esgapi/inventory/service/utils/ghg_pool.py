"""온실가스 풀의 순수 도움말(django 0 — .importlinter 다): 선택 목록·검사 규칙(S20 「확인」)·Decimal 글자.

선택 목록은 새 수치를 만들지 않는다:
  가스      고정 차례 일곱(S20 [확인])
  단위      inventory/data/unit-conversions.json 에 나오는 단위 이름 14개만. 종류(질량·부피·에너지·전력량)로 나눈 것은
            [우리 해석 — EDK 단위 목록 실물 없음]. 파일과 어긋나면 순수 시험이 빨갛다
  국가      reference 낱줄의 region 값(GLOBAL·KR) [우리 해석 — 이름]
  산업      reference 대응표(mappings.kr-ets.json)의 부문 넷 + 기타 [우리 해석]. 대응표와 어긋나면 순수 시험이 빨갛다
factorUnit 기본값은 default_factor_unit 한 곳이다(MARC-ENT-474 권장안 — 답이 오면 여기만 고친다).
selectors·services·actions 가 돌려주는 갈래(Forbidden·NotFound·Invalid·HasChildren·InUse)와 보기(…View)도 여기 둔다
(경로가 HTTP 로 바꾼다 — 403·404·422·409).
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Final

from esgapi.core.permissions import forbidden_message

LEVELS: Final = ("scope", "source_type", "activity", "facility")
GASES: Final = ("CO2", "CH4", "N2O", "HFCs", "PFCs", "SF6", "NF3")

UNITS: Final[dict[str, tuple[str, ...]]] = {
    "mass": ("g", "kg", "t"),
    "volume": ("L", "kL", "m3", "Nm3", "kNm3"),
    "energy": ("MJ", "GJ", "TJ"),
    "electricity": ("kWh", "MWh", "GWh"),
}
MASS_UNITS: Final = UNITS["mass"]
EMISSION_UNITS: Final[dict[str, tuple[str, ...]]] = {"mass": ("tCO2-eq", "kgCO2-eq")}
DEFAULT_EMISSION_UNIT: Final = ("mass", "tCO2-eq")

COUNTRIES: Final = (("GLOBAL", "전 세계"), ("KR", "대한민국"))
INDUSTRIES: Final = (
    ("energy_industries", "에너지산업"),
    ("manufacturing_construction", "제조업ㆍ건설업"),
    ("commercial_public", "상업ㆍ공공"),
    ("residential_other", "가정ㆍ기타"),
    ("other", "기타"),
)

NAME_MAX: Final = 100
SOURCE_MAX: Final = 200
NOTE_MAX: Final = 1000
TOOLTIP_MAX: Final = 1000
SEARCH_MAX: Final = 100
YEAR_MIN: Final = 1990
YEAR_MAX: Final = 2100
TIERS: Final = (1, 2, 3)

# DecimalField(max_digits=30, decimal_places=12) 에 들어가는 꼴: 정수부 18자리·소수부 12자리까지. 지수 표기·부호 없음.
# ASCII 숫자만(\d 는 유니코드 숫자 「١٢」·「１２」 도 받는다 — 검증 R1).
_DECIMAL: Final = re.compile(r"[0-9]{1,18}(\.[0-9]{1,12})?")


def parent_level(level: str) -> str | None:
    """그 단의 부모 단(범위는 None). 단 이름이 아니면 ValueError."""
    index = LEVELS.index(level)
    return LEVELS[index - 1] if index else None


def is_unit(kind: str, unit: str) -> bool:
    return unit in UNITS.get(kind, ())


def unit_kind(unit: str) -> str | None:
    """단위 이름의 종류(UNITS 의 칸 이름 — mass·volume·energy·electricity). 목록 밖이면 None."""
    for kind, units in UNITS.items():
        if unit in units:
            return kind
    return None


def default_factor_unit(ncv_enabled: bool, input_unit: str) -> str:
    """가스 계수의 단위 기본값(MARC-ENT-474 권장안): 순발열량 켬 → kg/TJ, 끔 → kg/<투입 단위>."""
    return "kg/TJ" if ncv_enabled else f"kg/{input_unit}"


def is_factor_unit(text: str) -> bool:
    """`<질량>/<단위>` 꼴(둘 다 목록 안)."""
    mass, slash, per = text.partition("/")
    return slash == "/" and mass in MASS_UNITS and any(per in units for units in UNITS.values())


def parse_decimal(text: str) -> Decimal | None:
    """요청의 숫자 글자 → Decimal. 꼴이 아니면(지수·부호·빈 글자·자릿수 넘침) None."""
    return Decimal(text) if _DECIMAL.fullmatch(text) else None


def decimal_text(value: Decimal) -> str:
    """응답의 숫자 글자: 지수 표기 0, 끝 0 걷음(「1234.500」 → 「1234.5」, 「0.0100」 → 「0.01」)."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def clean_name(text: str, *, limit: int = NAME_MAX) -> str | None:
    """앞뒤 공백을 걷은 이름. 비었거나 길면 None."""
    cleaned = text.strip()
    return cleaned if 0 < len(cleaned) <= limit else None


@dataclass(frozen=True)
class GasDraft:
    gas: str
    enabled: bool
    factor: str | None
    gwp: str | None


@dataclass(frozen=True)
class FactorDraft:
    """요청의 계수 한 건(글자 그대로). 검사는 check_factor."""

    name: str
    source: str
    base_year: int | None
    tier: int | None
    country_code: str
    industry_code: str
    input_unit: tuple[str, str] | None
    emission_unit: tuple[str, str] | None
    ncv_enabled: bool
    ncv: str | None
    ncv_unit: tuple[str, str] | None
    factor_unit: str | None
    gases: Sequence[GasDraft]
    note: str


@dataclass(frozen=True)
class GasValues:
    gas: str
    enabled: bool
    factor: Decimal | None
    gwp: Decimal | None


@dataclass(frozen=True)
class FactorValues:
    """검사를 지난 계수 한 건 — 판 한 줄 + 가스 일곱 줄(고정 차례)."""

    name: str
    source: str
    base_year: int
    tier: int
    country_code: str
    industry_code: str
    input_unit: tuple[str, str]
    emission_unit: tuple[str, str]
    ncv: Decimal | None
    ncv_unit: tuple[str, str] | None
    factor_unit: str
    gases: tuple[GasValues, ...]
    note: str


def _number(text: str | None, field: str, errors: dict[str, str]) -> Decimal | None:
    if text is None:
        return None
    value = parse_decimal(text)
    if value is None:
        errors[field] = "숫자 글자가 아니다(정수 18자리·소수 12자리까지, 지수·부호 없음)"
    return value


def _gases(drafts: Sequence[GasDraft], errors: dict[str, str]) -> tuple[GasValues, ...]:
    given: dict[str, GasDraft] = {}
    for draft in drafts:
        if draft.gas not in GASES or draft.gas in given:
            errors["gases"] = "가스는 일곱 가지가 한 번씩이다"
            return ()
        given[draft.gas] = draft
    values: list[GasValues] = []
    for gas in GASES:
        draft = given.get(gas, GasDraft(gas, enabled=False, factor=None, gwp=None))
        factor = _number(draft.factor, f"gases.{gas}.factor", errors)
        gwp = _number(draft.gwp, f"gases.{gas}.gwp", errors)
        if draft.enabled:
            if factor is None or factor <= 0:
                errors.setdefault(f"gases.{gas}.factor", "켠 가스의 배출계수는 0 보다 크다")
            if gwp is None or gwp <= 0:
                errors.setdefault(f"gases.{gas}.gwp", "켠 가스의 GWP 는 0 보다 크다")
        values.append(GasValues(gas, draft.enabled, factor, gwp))
    if not any(value.enabled for value in values):
        errors.setdefault("gases", "켠 가스가 하나 이상이다")
    return tuple(values)


def check_factor(draft: FactorDraft) -> FactorValues | dict[str, str]:
    """S20 「확인」 의 검사. 지나면 FactorValues, 아니면 {칸: 까닭}(경로가 422 fields 로)."""
    errors: dict[str, str] = {}
    name = clean_name(draft.name)
    if name is None:
        errors["name"] = f"배출계수명은 1~{NAME_MAX}자다"
    source = clean_name(draft.source, limit=SOURCE_MAX)
    if source is None:
        errors["source"] = f"출처는 1~{SOURCE_MAX}자다"
    if draft.base_year is None or not YEAR_MIN <= draft.base_year <= YEAR_MAX:
        errors["baseYear"] = f"기준연도는 {YEAR_MIN}~{YEAR_MAX} 다"
    if draft.tier not in TIERS:
        errors["tier"] = "Tier 는 1·2·3 이다"
    if draft.country_code not in dict(COUNTRIES):
        errors["countryCode"] = "국가 목록 밖이다"
    if draft.industry_code not in dict(INDUSTRIES):
        errors["industryCode"] = "산업 목록 밖이다"
    if draft.input_unit is None or not is_unit(*draft.input_unit):
        errors["inputUnit"] = "투입량 기준단위가 목록 밖이다"
    emission = draft.emission_unit or DEFAULT_EMISSION_UNIT
    if emission[1] not in EMISSION_UNITS.get(emission[0], ()):
        errors["emissionUnit"] = "배출량 기준단위가 목록 밖이다"
    ncv = _number(draft.ncv, "ncv", errors)
    if draft.ncv_enabled:
        if ncv is None or ncv <= 0:
            errors.setdefault("ncv", "순발열량을 켜면 값(0 초과)이 있다")
        if draft.ncv_unit is None or not is_unit(*draft.ncv_unit):
            errors["ncvUnit"] = "순발열량을 켜면 단위가 목록 안에 있다"
    elif draft.ncv is not None or draft.ncv_unit is not None:
        errors["ncv"] = "순발열량을 끄면 값과 단위가 없다"
    factor_unit = draft.factor_unit
    if factor_unit is not None and not is_factor_unit(factor_unit):
        errors["factorUnit"] = "<질량>/<단위> 꼴이다"
    _check_unit_kinds(draft, errors)
    if len(draft.note) > NOTE_MAX:
        errors["note"] = f"비고는 {NOTE_MAX}자까지다"
    gases = _gases(draft.gases, errors)
    if errors or name is None or source is None or draft.input_unit is None:
        return errors
    if draft.base_year is None or draft.tier is None:
        return errors
    return FactorValues(
        name=name,
        source=source,
        base_year=draft.base_year,
        tier=draft.tier,
        country_code=draft.country_code,
        industry_code=draft.industry_code,
        input_unit=draft.input_unit,
        emission_unit=emission,
        ncv=ncv if draft.ncv_enabled else None,
        ncv_unit=draft.ncv_unit if draft.ncv_enabled else None,
        factor_unit=factor_unit or default_factor_unit(draft.ncv_enabled, draft.input_unit[1]),
        gases=gases,
        note=draft.note,
    )


def _check_unit_kinds(draft: FactorDraft, errors: dict[str, str]) -> None:
    """단위 종류 정합(M1·M3): 순발열량 켬 → ncvUnit·factorUnit 분모가 energy, 끔 → 분모 종류 = 투입 단위 종류.
    factorUnit 을 비우면 default_factor_unit 을 본다(그 값은 늘 지난다 — 순수 시험). 같은 종류 안의 접두 차이
    (MJ ↔ TJ, L ↔ kL)는 거절하지 않는다 — 셈 때 unit-conversions.json 으로 맞추는 것은 S12a. 꼴·목록 검사에 이미
    걸린 칸은 덧쓰지 않는다."""
    ncv_unit = draft.ncv_unit
    if draft.ncv_enabled and ncv_unit is not None and is_unit(*ncv_unit) and unit_kind(ncv_unit[1]) != "energy":
        errors.setdefault("ncvUnit", "순발열량 단위는 에너지(energy) 단위다")
    if draft.input_unit is None or not is_unit(*draft.input_unit):
        return
    factor_unit = draft.factor_unit or default_factor_unit(draft.ncv_enabled, draft.input_unit[1])
    if not is_factor_unit(factor_unit):
        return
    per_kind = unit_kind(factor_unit.partition("/")[2])
    if draft.ncv_enabled and per_kind != "energy":
        errors.setdefault("factorUnit", "순발열량을 켜면 분모가 에너지(energy) 단위다")
    elif not draft.ncv_enabled and per_kind != unit_kind(draft.input_unit[1]):
        errors.setdefault("factorUnit", "순발열량을 끄면 분모가 투입량 기준단위와 같은 종류다")


def check_facility(unit: tuple[str, str] | None, tooltip: str) -> dict[str, str]:
    """잎(자산/시설)의 칸 검사 — 1차 단위는 목록 안, 툴팁 1,000자까지. 비면 지남."""
    errors: dict[str, str] = {}
    if unit is None or not is_unit(*unit):
        errors["unit"] = "1차 단위가 목록 밖이다"
    if len(tooltip) > TOOLTIP_MAX:
        errors["tooltip"] = f"툴팁은 {TOOLTIP_MAX}자까지다"
    return errors


# ── 갈래(경로가 HTTP 로 바꾼다) ─────────────────────────────────────


@dataclass(frozen=True)
class Forbidden:
    """그 동작을 할 수 없는 주체다(403). 값은 core/permissions.py 의 표."""

    operation_id: str

    @property
    def message(self) -> str:
        return forbidden_message(self.operation_id)


@dataclass(frozen=True)
class NotFound:
    """없거나 삭제 표시된 노드·계수·판이다(404 — 아무것도 바꾸지 않았다. 일괄이면 하나라도)."""


@dataclass(frozen=True)
class Invalid:
    """칸 검사·단 규칙·겹침에 걸렸다(422 fields.<칸>)."""

    fields: Mapping[str, str]


@dataclass(frozen=True)
class HasChildren:
    """삭제 안 된 자식이 있는 노드다(409 has_children — 요청 전체 거절)."""

    ids: frozenset[int]


@dataclass(frozen=True)
class InUse:
    """회사 선택·입력이 쓰는 노드·계수다(409 in_use). 회사 선택 몫은 K1b-2b(풀 id 만 — 회사 정보 0), 입력 몫은 S12a."""

    ids: frozenset[int]


# ── 보기 ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NodeInfo:
    """판정용 노드 한 줄(삭제 안 된 것)."""

    id: int
    level: str
    parent_id: int | None
    facility_code_id: int | None


@dataclass(frozen=True)
class FactorInfo:
    """판정용 계수 정체 한 줄(삭제 안 된 것)."""

    id: int
    facility_node_id: int
    is_default: bool
    sort_order: int
    current_version: int


@dataclass(frozen=True)
class NodeView:
    """열 목록의 한 줄. 잎의 name 은 시설 코드 이름이다(코드 이름 고침이 따라온다)."""

    id: int
    level: str
    name: str
    parent_id: int | None
    sort_order: int
    child_count: int
    facility_code_id: int | None = None
    facility_code: str | None = None


@dataclass(frozen=True)
class FactorSummary:
    """잎 상세의 계수 한 줄 — 지금 판의 이름·투입 단위."""

    id: int
    name: str
    input_unit: tuple[str, str]
    is_default: bool
    sort_order: int
    version: int


@dataclass(frozen=True)
class FacilityView:
    id: int
    parent_id: int
    facility_code_id: int
    facility_code: str
    facility_name: str
    unit: tuple[str, str]
    tooltip: str
    factors: list[FactorSummary]


@dataclass(frozen=True)
class FactorView:
    """계수 한 건의 판 하나(GET·만들기·고치기의 답). createdAt = 정체를 만든 때, updatedAt = 이 판을 만든 때."""

    id: int
    facility_node_id: int
    version: int
    is_default: bool
    sort_order: int
    name: str
    source: str
    base_year: int
    tier: int
    country_code: str
    industry_code: str
    input_unit: tuple[str, str]
    emission_unit: tuple[str, str]
    ncv: Decimal | None
    ncv_unit: tuple[str, str] | None
    factor_unit: str
    gases: tuple[GasValues, ...]
    note: str
    seed_record_ids: tuple[str, ...]
    seed_gwp_set_id: str | None
    created_at: datetime
    updated_at: datetime
    versions: tuple[int, ...] = field(default=())

    @property
    def ncv_enabled(self) -> bool:
        return self.ncv is not None


def options() -> Mapping[str, object]:
    """선택 목록 응답의 몸(경로 GET /admin/ghg-options)."""
    return {
        "gases": list(GASES),
        "units": [{"kind": kind, "units": list(units)} for kind, units in UNITS.items()],
        "countries": [{"code": code, "name": name} for code, name in COUNTRIES],
        "industries": [{"code": code, "name": name} for code, name in INDUSTRIES],
        "defaults": {
            "emissionUnit": {"kind": DEFAULT_EMISSION_UNIT[0], "unit": DEFAULT_EMISSION_UNIT[1]},
            "factorUnitWithNcv": default_factor_unit(True, ""),
            "factorUnitWithoutNcv": default_factor_unit(False, "<투입 단위>"),
        },
    }


# ── 씨앗(④ — manage.py seed_ghg_pool) ─────────────────────────────────
# 값은 reference 낱줄의 value_raw 와 gwp-sets.json 에서만 온다(수치를 지어내지 않는다 — 운영 규칙 4). 씨앗 파일
# (inventory/data/ghg-pool-seed.json)에는 낱줄 id·이름·단위 글자만 있다. 단위 규칙(감독 보정 B4): 한 묶음의 가스
# 낱줄은 분모가 같아야 하고(다르면 건너뜀), 분자는 「<질량 접두><기체>」 꼴만(kgC/TJ·CO2e 낱줄은 쓰지 않는다).
# 질량 접두가 kg 가 아니면 unit-conversions.json 의 「<접두> → kg」 값을 곱한다(새 수치 0).
# factorUnit 은 kg/<분모> 하나.
SEED_GASES: Final = ("CO2", "CH4", "N2O")  # 씨앗이 켜는 가스(MARC-ENT-463 — 넷은 관리자 입력)
UNIT_NOTATION: Final[dict[str, str]] = {"N㎥": "Nm3"}  # 낱줄 단위 표기 → 단위 이름(R6 — 이것 하나만)


@dataclass(frozen=True)
class SeedRecord:
    """씨앗이 읽는 reference 낱줄의 칸(값은 value_raw 글자 그대로)."""

    id: str
    value_raw: str | None
    unit_numerator: str
    unit_denominator: str
    gas: str


@dataclass(frozen=True)
class SeedFactor:
    seed_key: str
    draft: FactorDraft
    record_ids: tuple[str, ...]


@dataclass(frozen=True)
class SeedSkip:
    seed_key: str
    reason: str


def _raw_number(record: SeedRecord) -> Decimal | None:
    """value_raw → Decimal(천 단위 쉼표를 걷는다). 꼴이 아니면 None."""
    return None if record.value_raw is None else parse_decimal(record.value_raw.replace(",", ""))


def _unit_name(notation: str) -> str:
    return UNIT_NOTATION.get(notation, notation)


def seed_factor(
    spec: Mapping[str, Any],
    *,
    leaf_key: str,
    input_unit: tuple[str, str],
    records: Mapping[str, SeedRecord],
    gwp: Mapping[str, str],
    mass_to_kg: Mapping[str, str],
) -> SeedFactor | SeedSkip:
    """씨앗 파일의 계수 묶음 하나 → 계수 초안(또는 건너뜀과 까닭). 순수하다(DB 0)."""
    key = f"{leaf_key}#{spec['key']}"
    gas_ids: Mapping[str, str] = spec.get("gases") or {}
    if set(gas_ids) != set(SEED_GASES):
        return SeedSkip(key, "가스 낱줄이 CO2·CH4·N2O 셋이 아니다")
    ncv_id = spec.get("ncv")
    wanted = [str(gas_ids[gas]) for gas in SEED_GASES] + ([str(ncv_id)] if ncv_id is not None else [])
    missing = [record_id for record_id in wanted if record_id not in records]
    if missing:
        return SeedSkip(key, f"적재본에 없는 낱줄: {', '.join(missing)}")
    gases: list[GasDraft] = []
    denominators: set[str] = set()
    for gas in SEED_GASES:
        record = records[str(gas_ids[gas])]
        numerator = record.unit_numerator.replace(" ", "")
        prefix = numerator[: -len(gas)] if numerator.endswith(gas) else None
        if record.gas != gas or prefix not in MASS_UNITS:
            return SeedSkip(
                key,
                f"{record.id}: 단위 {record.unit_numerator}/{record.unit_denominator} 는 「<질량><기체>」 꼴이 아니다",
            )
        value = _raw_number(record)
        if value is None:
            return SeedSkip(key, f"{record.id}: 값이 없거나 숫자 꼴이 아니다")
        if prefix != "kg":
            factor = mass_to_kg.get(prefix)
            if factor is None:
                return SeedSkip(key, f"{record.id}: {prefix} → kg 환산이 환산표에 없다")
            value *= Decimal(factor)
        denominators.add(_unit_name(record.unit_denominator))
        if gas not in gwp:
            return SeedSkip(key, f"GWP 세트에 {gas} 가 없다")
        gases.append(GasDraft(gas, enabled=True, factor=decimal_text(value), gwp=gwp[gas]))
    if len(denominators) != 1:
        return SeedSkip(key, f"가스 낱줄의 분모가 다르다: {', '.join(sorted(denominators))}")
    per = denominators.pop()
    ncv_text: str | None = None
    ncv_unit: tuple[str, str] | None = None
    if ncv_id is not None:
        record = records[str(ncv_id)]
        value = _raw_number(record)
        if value is None:
            return SeedSkip(key, f"{record.id}: 순발열량 값이 없거나 숫자 꼴이 아니다")
        if _unit_name(record.unit_denominator) != input_unit[1] or unit_kind(record.unit_numerator) != "energy":
            return SeedSkip(
                key,
                f"{record.id}: 순발열량 단위 {record.unit_numerator}/{record.unit_denominator} 가 투입 단위와 안 맞다",
            )
        ncv_text, ncv_unit = decimal_text(value), ("energy", record.unit_numerator)
    draft = FactorDraft(
        name=str(spec.get("name", "")),
        source=str(spec.get("source", "")),
        base_year=spec.get("baseYear"),
        tier=spec.get("tier"),
        country_code=str(spec.get("countryCode", "")),
        industry_code=str(spec.get("industryCode", "")),
        input_unit=input_unit,
        emission_unit=None,
        ncv_enabled=ncv_id is not None,
        ncv=ncv_text,
        ncv_unit=ncv_unit,
        factor_unit=f"kg/{per}",
        gases=tuple(gases),
        note=str(spec.get("note", "")),
    )
    checked = check_factor(draft)
    if not isinstance(checked, FactorValues):
        return SeedSkip(key, "검사에 걸렸다: " + ", ".join(f"{name} {why}" for name, why in checked.items()))
    return SeedFactor(key, draft, tuple(wanted))
