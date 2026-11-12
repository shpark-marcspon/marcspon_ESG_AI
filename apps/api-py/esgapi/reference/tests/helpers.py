"""순수 테스트의 고정물: 패키지에 실린 자료 사본(esgapi/reference/data)에서 낱줄과 대응표를 읽는다. DB 가 없다.

TS 원본의 `test/helpers.ts` 와 같은 일을 한다. 거기는 esg-lab 의 전체 jsonl 에서 지침 출처만 걸러 읽었고,
여기는 이미 걸러 둔 사본(kr-ets-*·gir-* 600건)을 읽는다.
"""

import json
from dataclasses import replace
from importlib import resources
from pathlib import Path
from typing import Any

from esgapi.reference.calc import (
    Assembled,
    AssemblyMapping,
    AssemblyResult,
    FactorRecord,
    Failed,
    assemble_combustion_factor,
    mapping_from_json,
)
from esgapi.reference.calc.types import Json, SourceRef, result_to_json
from esgapi.reference.jsonl import read_records, to_calc

DATA = resources.files("esgapi.reference.data")
GOLDEN = Path(__file__).resolve().parent / "golden"


def _load_records() -> tuple[FactorRecord, ...]:
    with DATA.joinpath("factors.kr.jsonl").open(encoding="utf-8") as lines:
        return tuple(to_calc(record) for _, record in read_records(lines))


# 사본의 낱줄 전부(kr-ets-* 560 + gir-* 40)와 대응표.
ALL_RECORDS: tuple[FactorRecord, ...] = _load_records()
# 고정연소 조립이 읽는 것: 지침(kr-ets-*)의 낱줄만. TS 의 loadGuidelineRecords 와 같은 묶음이다.
RECORDS: tuple[FactorRecord, ...] = tuple(r for r in ALL_RECORDS if r.source.id.startswith("kr-ets-"))
MAPPING: AssemblyMapping = mapping_from_json(
    json.loads(DATA.joinpath("mappings.kr-ets.json").read_text(encoding="utf-8"))
)

TIER2: Json = {"kind": "explicit", "calorific": 2, "co2": 2, "oxidation": 2}
TIER1: Json = {"kind": "explicit", "calorific": 1, "co2": 1, "oxidation": 1}
GROUP_A: Json = {"kind": "group_minimum", "group": "A"}


def request(**overrides: Any) -> Json:
    """경유, 제조업·건설업, 전부 Tier 2. 필요한 칸만 덮어쓴다."""
    base: Json = {
        "fuel": "경유",
        "combustionType": "stationary",
        "industry": {"sector": "manufacturing_construction"},
        "tiers": TIER2,
    }
    return {**base, **overrides}


def assemble(mapping: AssemblyMapping = MAPPING, **overrides: Any) -> AssemblyResult:
    return assemble_combustion_factor(request(**overrides), RECORDS, mapping)


def value_of(result: AssemblyResult) -> Assembled:
    if isinstance(result, Failed):
        raise AssertionError(f"조립 실패: {result.failure.to_json()}")
    return result.value


def failure_of(result: AssemblyResult) -> Json:
    """실패의 `failure` 칸. API 가 내보내는 꼴(`result_to_json`)을 거쳐 읽고, 그 꼴이 `{"ok": False, "failure": …}`
    (키 둘, `ok` 는 False 그 자체)인지까지 본다. 견주는 쪽은 실패 dict 전체를 `==` 로 견준다(subset 이 아니다)."""
    if not isinstance(result, Failed):
        raise AssertionError(f"실패해야 하는데 조립됐다: {result.value.factor['id']}")
    out = result_to_json(result)
    if list(out) != ["ok", "failure"] or out["ok"] is not False:
        raise AssertionError(f"실패의 꼴이 {{ok: false, failure}} 가 아니다: {out}")
    failure: Json = out["failure"]
    return failure


def by_id(record_id: str) -> FactorRecord:
    found = [record for record in ALL_RECORDS if record.id == record_id]
    if len(found) != 1:
        raise AssertionError(f"낱줄이 없거나 둘이다: {record_id}")
    return found[0]


def synthetic(base: FactorRecord, **patch: Any) -> FactorRecord:
    """실제 낱줄 하나를 베껴 값·조건을 바꾼 가상 낱줄. 실제 값으로 쓰면 안 된다."""
    return replace(base, **patch, synthetic=True)


def with_version(source: SourceRef, version: str) -> SourceRef:
    return replace(source, version=version)


def swap(record_id: str, **patch: Any) -> list[FactorRecord]:
    """그 id 의 낱줄 하나를 가상 낱줄로 바꾼 묶음."""
    return [*(r for r in RECORDS if r.id != record_id), synthetic(by_id(record_id), **patch)]


def subset(actual: Any, expected: Any) -> bool:
    """vitest 의 toMatchObject: expected 에 적힌 칸만 견준다(dict 는 부분, 목록은 길이와 자리마다)."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(key in actual and subset(actual[key], value) for key, value in expected.items())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):  # pyright: ignore[reportUnknownArgumentType]
            return False
        return all(subset(a, e) for a, e in zip(actual, expected, strict=True))  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return bool(actual == expected)


def param(result: AssemblyResult, parameter: str) -> Json:
    found = [p for p in value_of(result).evidence["parameters"] if p["parameter"] == parameter]
    assert len(found) == 1
    return found[0]
