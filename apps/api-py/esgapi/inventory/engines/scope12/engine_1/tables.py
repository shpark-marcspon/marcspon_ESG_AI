"""바깥에서 읽은 기준정보 표(JSON 을 읽은 값)를 검사하고, 계산 함수가 받는 dataclass 로 바꾼다. 표 검사 층이다.

문제가 하나라도 있으면 그 표로 계산하지 않는다.
계수 조합이 맞는지(어느 연료에 어느 계수인지)는 보지 않는다. 그것은 표를 만드는 쪽의 일이다.

두 단계다.
  1. `_check`  esg-lab `ts/ghg-calc/src/tables.ts` 의 validateTables 를 옮긴 것.
               문제 목록의 where·problem 이 TS 와 글자까지 같다.
  2. `_build`  dataclass 로 바꾼다. TS 는 1 을 통과한 값을 그대로 믿고 넘겼다. 여기서는 1 이 보지 않던 칸
               (배출계수의 perEnergyUnit, 계수의 year·variant, 출처의 locator·note)의 꼴이 틀리면 문제로 돌려준다.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

from esgapi.core.calc.decimal import is_negative, parse_external_decimal
from esgapi.inventory.engines.scope12.engine_1.provenance import Cited, Definition, Provenance, Synthetic
from esgapi.inventory.engines.scope12.engine_1.types import (
    Calorific,
    CalorificBasis,
    CombustionEmissionFactor,
    CombustionFactor,
    CombustionType,
    EnergyType,
    FacilityUse,
    Factor,
    GwpSet,
    ParameterTiers,
    PurchasedEmissionFactor,
    PurchasedEnergyFactor,
    ReferenceTables,
    UnitConversion,
)
from esgapi.inventory.tools.jsrepr import as_array, as_integer, as_object, get, js_entries, js_json, js_string

TABLE_NAMES: Final = ("unitConversions", "factors", "gwpSets")

_URL: Final = re.compile(r"https?://")
_DATE: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


@dataclass(frozen=True, slots=True, kw_only=True)
class TableProblem:
    where: str
    # TS 와 같은 문장. 받은 값이 끝에 붙는 것이 있다(예: `음수다: "-21"`).
    problem: str
    # 받은 값을 뺀 문장. 지금 쓰는 제품 코드가 없다: 2026-10-08 사용자 결정으로 HTTP 응답(inventory/api.py)은
    # problem 을 쓴다(MARC-ISSUE-45 의 3번). 받은 값을 응답에서 다시 빼기로 하면(되돌릴 때) 이 칸을 쓴다.
    summary: str


@dataclass(frozen=True, slots=True)
class TablesOk:
    tables: ReferenceTables
    ok: Literal[True] = True


@dataclass(frozen=True, slots=True)
class TablesInvalid:
    problems: tuple[TableProblem, ...]
    ok: Literal[False] = False


class _Problems:
    def __init__(self) -> None:
        self.items: list[TableProblem] = []

    def add(self, where: str, problem: str, *, received: str | None = None) -> None:
        full = problem if received is None else f"{problem}: {received}"
        self.items.append(TableProblem(where=where, problem=full, summary=problem))


def _is_text(value: object) -> bool:
    return isinstance(value, str) and len(value) > 0


# ── 1. 검사 (TS 의 validateTables) ───────────────────────────────────


def _check_source(source: object, where: str, problems: _Problems) -> None:
    obj = as_object(source)
    if obj is None:
        problems.add(where, "출처(source)가 없다")
        return
    kind = get(obj, "kind")
    if kind == "cited":
        url = get(obj, "url")
        if not (isinstance(url, str) and _URL.match(url)):
            problems.add(where, "cited 출처에 url 이 없다")
        checked_on = get(obj, "checkedOn")
        if not (isinstance(checked_on, str) and _DATE.fullmatch(checked_on)):
            problems.add(where, "cited 출처에 확인 일자(checkedOn, YYYY-MM-DD)가 없다")
        if not _is_text(get(obj, "title")):
            problems.add(where, "cited 출처에 title 이 없다")
    elif kind in ("definition", "synthetic"):
        if not _is_text(get(obj, "note")):
            problems.add(where, f"{kind} 출처에 note 가 없다")
    else:
        problems.add(where, "알 수 없는 출처 종류", received=js_string(kind))


def _check_decimal(value: object, where: str, problems: _Problems) -> None:
    parsed = parse_external_decimal(value)
    if parsed is None:
        problems.add(where, "십진 문자열이 아니다", received=js_json(value))
    elif is_negative(parsed):
        problems.add(where, "음수다", received=js_json(value))


def _is_tier(value: object) -> bool:
    # bool 은 as_integer 가 거른다(파이썬에서 True == 1 이라 그냥 견주면 등급 1 로 통과한다).
    return as_integer(value) in (1, 2, 3, 4)


def _check_tiers(tiers: object, has_oxidation: bool, where: str, problems: _Problems) -> None:
    """매개변수별 산정등급. 산화계수의 등급은 산화계수가 있을 때만, 그리고 있을 때는 반드시 적는다."""
    obj = as_object(tiers)
    if obj is None:
        problems.add(where, "객체가 아니다")
        return
    for key in ("calorific", "co2", "nonCo2"):
        if not _is_tier(get(obj, key)):
            problems.add(f"{where}.{key}", "산정등급(1~4)이 아니다", received=js_json(get(obj, key)))
    oxidation = get(obj, "oxidation")
    if has_oxidation:
        if not _is_tier(oxidation):
            problems.add(f"{where}.oxidation", "산화계수가 있는데 그 산정등급(1~4)이 없다", received=js_json(oxidation))
    elif oxidation is not None:
        problems.add(f"{where}.oxidation", "산화계수가 없으면 그 산정등급은 null 이어야 한다")


def _check_unit_conversion(item: object, where: str, problems: _Problems) -> None:
    obj = as_object(item)
    if obj is None:
        problems.add(where, "객체가 아니다")
        return
    if not _is_text(get(obj, "from")) or not _is_text(get(obj, "to")):
        problems.add(where, "from/to 가 없다")
    _check_decimal(get(obj, "factor"), f"{where}.factor", problems)
    _check_source(get(obj, "source"), where, problems)


def _check_gwp_set(item: object, where: str, problems: _Problems) -> None:
    obj = as_object(item)
    if obj is None:
        problems.add(where, "객체가 아니다")
        return
    if not _is_text(get(obj, "id")) or not _is_text(get(obj, "label")):
        problems.add(where, "id/label 이 없다")
    _check_source(get(obj, "source"), where, problems)
    values = as_object(get(obj, "values"))
    if values is None:
        problems.add(where, "values 가 없다")
        return
    for gas, value in js_entries(values):
        _check_decimal(value, f"{where}.values.{gas}", problems)


def _check_factor(item: object, where: str, problems: _Problems) -> None:
    obj = as_object(item)
    if obj is None:
        problems.add(where, "객체가 아니다")
        return
    if not _is_text(get(obj, "id")) or not _is_text(get(obj, "version")):
        problems.add(where, "id/version 이 없다")
    _check_source(get(obj, "source"), where, problems)
    emission_factors = as_array(get(obj, "emissionFactors"))
    if emission_factors is None:
        problems.add(where, "emissionFactors 가 없다")
        return
    for j, entry in enumerate(emission_factors):
        entry_where = f"{where}.emissionFactors[{j}]"
        entry_obj = as_object(entry)
        if entry_obj is None:
            problems.add(entry_where, "객체가 아니다")
            continue
        _check_decimal(get(entry_obj, "value"), f"{entry_where}.value", problems)
        if not _is_text(get(entry_obj, "gas")) or not _is_text(get(entry_obj, "massUnit")):
            problems.add(entry_where, "gas/massUnit 이 없다")

    kind = get(obj, "kind")
    if kind == "combustion":
        if not _is_text(get(obj, "fuel")):
            problems.add(where, "fuel 이 없다")
        if get(obj, "combustionType") not in ("stationary", "mobile"):
            problems.add(where, "combustionType 이 stationary/mobile 이 아니다")
        calorific = as_object(get(obj, "calorific"))
        if calorific is None:
            problems.add(where, "calorific 이 없다")
            return
        _check_decimal(get(calorific, "value"), f"{where}.calorific.value", problems)
        if get(calorific, "basis") not in ("net", "gross"):
            problems.add(where, "calorific.basis 가 net/gross 가 아니다")
        if not _is_text(get(calorific, "energyUnit")) or not _is_text(get(calorific, "perUnit")):
            problems.add(where, "calorific 단위가 없다")
        has_oxidation = "oxidationFactor" in obj
        if has_oxidation:
            _check_decimal(obj["oxidationFactor"], f"{where}.oxidationFactor", problems)
        if "sector" in obj and not _is_text(obj["sector"]):
            problems.add(where, "sector 가 빈 문자열이거나 문자열이 아니다")
        if "facilityUse" in obj and obj["facilityUse"] not in ("power_generation", "other"):
            problems.add(where, "facilityUse 가 power_generation/other 가 아니다")
        if "parameterTiers" in obj:
            _check_tiers(obj["parameterTiers"], has_oxidation, f"{where}.parameterTiers", problems)
    elif kind == "purchased_energy":
        if get(obj, "energyType") not in ("electricity", "heat"):
            problems.add(where, "energyType 이 electricity/heat 가 아니다")
        if not _is_text(get(obj, "perUnit")):
            problems.add(where, "perUnit 이 없다")
    else:
        problems.add(where, "알 수 없는 계수 종류", received=js_string(kind))


def _check(tables: dict[str, object]) -> list[TableProblem]:
    problems = _Problems()
    for name in TABLE_NAMES:
        if as_array(get(tables, name)) is None:
            problems.add(name, "배열이 없다")
    if problems.items:
        return problems.items
    for i, item in enumerate(as_array(tables["unitConversions"]) or []):
        _check_unit_conversion(item, f"unitConversions[{i}]", problems)
    for i, item in enumerate(as_array(tables["gwpSets"]) or []):
        _check_gwp_set(item, f"gwpSets[{i}]", problems)
    for i, item in enumerate(as_array(tables["factors"]) or []):
        _check_factor(item, f"factors[{i}]", problems)
    return problems.items


# ── 2. dataclass 로 ───────────────────────────────────────────────────
# 여기 오는 값은 1 을 통과했다. 1 이 본 칸은 다시 문제로 적지 않고 좁히기만 한다(틀리면 None 이 돌아가 통째로 빠진다:
# 그런 일이 생기면 1 과 2 가 어긋난 것이므로 `_build` 가 문제 하나로 적는다).


def _combustion_type(value: object) -> CombustionType | None:
    return "stationary" if value == "stationary" else "mobile" if value == "mobile" else None


def _calorific_basis(value: object) -> CalorificBasis | None:
    return "net" if value == "net" else "gross" if value == "gross" else None


def _facility_use(value: object) -> FacilityUse | None:
    return "power_generation" if value == "power_generation" else "other" if value == "other" else None


def _energy_type(value: object) -> EnergyType | None:
    return "electricity" if value == "electricity" else "heat" if value == "heat" else None


def _text(obj: dict[str, object], key: str) -> str | None:
    value = get(obj, key)
    return value if isinstance(value, str) else None


def _optional_text(obj: dict[str, object], key: str, where: str, problems: _Problems) -> str | None:
    """없으면 None. 있는데 문자열이 아니면 문제로 적고 None."""
    if key not in obj:
        return None
    value = obj[key]
    if isinstance(value, str):
        return value
    problems.add(where, f"{key} 가 문자열이 아니다 (없으면 키를 뺀다)")
    return None


def _optional_year(obj: dict[str, object], where: str, problems: _Problems) -> int | None:
    if "year" not in obj:
        return None
    year = as_integer(obj["year"])
    if year is None:
        problems.add(where, "year 가 정수가 아니다 (없으면 키를 뺀다)")
    return year


def _build_source(source: object, where: str, problems: _Problems) -> Provenance | None:
    obj = as_object(source)
    if obj is None:
        return None
    kind = get(obj, "kind")
    note = _optional_text(obj, "note", f"{where}.source", problems)
    if kind == "cited":
        title, url, checked_on = _text(obj, "title"), _text(obj, "url"), _text(obj, "checkedOn")
        locator = _optional_text(obj, "locator", f"{where}.source", problems)
        if title is None or url is None or checked_on is None:
            return None
        return Cited(title=title, url=url, checked_on=checked_on, locator=locator, note=note)
    if note is None:
        return None
    return Definition(note=note) if kind == "definition" else Synthetic(note=note) if kind == "synthetic" else None


def _build_unit_conversion(obj: dict[str, object], where: str, problems: _Problems) -> UnitConversion | None:
    from_unit, to_unit, factor = _text(obj, "from"), _text(obj, "to"), _text(obj, "factor")
    source = _build_source(get(obj, "source"), where, problems)
    if from_unit is None or to_unit is None or factor is None or source is None:
        return None
    return UnitConversion(from_unit=from_unit, to_unit=to_unit, factor=factor, source=source)


def _build_gwp_set(obj: dict[str, object], where: str, problems: _Problems) -> GwpSet | None:
    set_id, label = _text(obj, "id"), _text(obj, "label")
    source = _build_source(get(obj, "source"), where, problems)
    values = {gas: value for gas, value in (as_object(get(obj, "values")) or {}).items() if isinstance(value, str)}
    if set_id is None or label is None or source is None:
        return None
    return GwpSet(id=set_id, label=label, source=source, values=MappingProxyType(values))


def _build_tiers(value: object) -> ParameterTiers | None:
    obj = as_object(value)
    if obj is None:
        return None
    calorific, co2, non_co2 = (as_integer(get(obj, key)) for key in ("calorific", "co2", "nonCo2"))
    if calorific is None or co2 is None or non_co2 is None:
        return None
    return ParameterTiers(calorific=calorific, co2=co2, non_co2=non_co2, oxidation=as_integer(get(obj, "oxidation")))


def _build_combustion(
    obj: dict[str, object], entries: list[dict[str, object]], where: str, problems: _Problems
) -> CombustionFactor | None:
    emission_factors: list[CombustionEmissionFactor] = []
    for j, entry in enumerate(entries):
        gas, value, mass_unit = _text(entry, "gas"), _text(entry, "value"), _text(entry, "massUnit")
        per_energy_unit = get(entry, "perEnergyUnit")
        if not isinstance(per_energy_unit, str) or not per_energy_unit:
            problems.add(f"{where}.emissionFactors[{j}]", "perEnergyUnit 이 없다")
            continue
        if gas is None or value is None or mass_unit is None:
            return None
        emission_factors.append(
            CombustionEmissionFactor(gas=gas, value=value, mass_unit=mass_unit, per_energy_unit=per_energy_unit)
        )

    factor_id, version, fuel = _text(obj, "id"), _text(obj, "version"), _text(obj, "fuel")
    source = _build_source(get(obj, "source"), where, problems)
    year = _optional_year(obj, where, problems)
    variant = _optional_text(obj, "variant", where, problems)
    calorific = as_object(get(obj, "calorific")) or {}
    value, energy_unit, per_unit = (
        _text(calorific, "value"),
        _text(calorific, "energyUnit"),
        _text(calorific, "perUnit"),
    )
    basis = _calorific_basis(get(calorific, "basis"))
    combustion_type = _combustion_type(get(obj, "combustionType"))
    facility_use = _facility_use(get(obj, "facilityUse"))
    if (
        factor_id is None
        or version is None
        or fuel is None
        or source is None
        or value is None
        or energy_unit is None
        or per_unit is None
        or basis is None
        or combustion_type is None
        or ("facilityUse" in obj and facility_use is None)
    ):
        return None
    return CombustionFactor(
        id=factor_id,
        version=version,
        source=source,
        fuel=fuel,
        combustion_type=combustion_type,
        calorific=Calorific(value=value, energy_unit=energy_unit, per_unit=per_unit, basis=basis),
        emission_factors=tuple(emission_factors),
        oxidation_factor=_text(obj, "oxidationFactor"),
        year=year,
        sector=_text(obj, "sector"),
        parameter_tiers=_build_tiers(obj["parameterTiers"]) if "parameterTiers" in obj else None,
        facility_use=facility_use,
        variant=variant,
    )


def _build_purchased(
    obj: dict[str, object], entries: list[dict[str, object]], where: str, problems: _Problems
) -> PurchasedEnergyFactor | None:
    emission_factors: list[PurchasedEmissionFactor] = []
    for entry in entries:
        gas, value, mass_unit = _text(entry, "gas"), _text(entry, "value"), _text(entry, "massUnit")
        if gas is None or value is None or mass_unit is None:
            return None
        emission_factors.append(PurchasedEmissionFactor(gas=gas, value=value, mass_unit=mass_unit))

    factor_id, version, per_unit = _text(obj, "id"), _text(obj, "version"), _text(obj, "perUnit")
    source = _build_source(get(obj, "source"), where, problems)
    year = _optional_year(obj, where, problems)
    variant = _optional_text(obj, "variant", where, problems)
    energy_type = _energy_type(get(obj, "energyType"))
    if factor_id is None or version is None or per_unit is None or source is None or energy_type is None:
        return None
    return PurchasedEnergyFactor(
        id=factor_id,
        version=version,
        source=source,
        energy_type=energy_type,
        per_unit=per_unit,
        emission_factors=tuple(emission_factors),
        variant=variant,
        year=year,
    )


def _build_factor(obj: dict[str, object], where: str, problems: _Problems) -> Factor | None:
    entries = [
        entry for entry in (as_object(e) for e in as_array(get(obj, "emissionFactors")) or []) if entry is not None
    ]
    if get(obj, "kind") == "combustion":
        return _build_combustion(obj, entries, where, problems)
    return _build_purchased(obj, entries, where, problems)


type _Builder[T] = Callable[[dict[str, object], str, _Problems], T | None]


def _build(tables: dict[str, object]) -> ReferenceTables | list[TableProblem]:
    problems = _Problems()
    unit_conversions: list[UnitConversion] = []
    gwp_sets: list[GwpSet] = []
    factors: list[Factor] = []

    def collect[T](name: str, build: _Builder[T], into: list[T]) -> None:
        for i, item in enumerate(as_array(tables[name]) or []):
            where = f"{name}[{i}]"
            before = len(problems.items)
            obj = as_object(item)
            built = build(obj, where, problems) if obj is not None else None
            if built is not None:
                into.append(built)
            elif len(problems.items) == before:
                problems.add(where, "검사를 통과했는데 읽지 못했다 (표 검사의 두 단계가 어긋났다)")

    collect("unitConversions", _build_unit_conversion, unit_conversions)
    collect("gwpSets", _build_gwp_set, gwp_sets)
    collect("factors", _build_factor, factors)
    if problems.items:
        return problems.items
    return ReferenceTables(unit_conversions=tuple(unit_conversions), factors=tuple(factors), gwp_sets=tuple(gwp_sets))


def validate_tables(tables: object) -> TablesOk | TablesInvalid:
    """바깥에서 읽은 기준정보 표의 구조와 출처를 검사하고 dataclass 로 바꾼다."""
    obj = as_object(tables)
    if obj is None:
        return TablesInvalid((TableProblem(where="$", problem="객체가 아니다", summary="객체가 아니다"),))
    problems = _check(obj)
    if problems:
        return TablesInvalid(tuple(problems))
    built = _build(obj)
    if isinstance(built, ReferenceTables):
        return TablesOk(built)
    return TablesInvalid(tuple(built))


def merge_tables(*parts: Mapping[str, object]) -> dict[str, object]:
    """여러 표(검사하기 전의 JSON 값)를 이어 붙인다.

    중복 id 는 여기서 걸러내지 않는다(계산 때 ambiguous 로 드러난다).
    """
    merged: dict[str, list[object]] = {name: [] for name in TABLE_NAMES}
    for part in parts:
        for name in TABLE_NAMES:
            value = part.get(name)
            items = as_array(value)
            if items is not None:
                merged[name].extend(items)
            elif value is not None:
                # JS 의 flatMap 은 배열이 아닌 값을 원소 하나로 넣는다. 그 원소는 표 검사가 「객체가 아니다」로 잡는다.
                merged[name].append(value)
    return dict(merged)
