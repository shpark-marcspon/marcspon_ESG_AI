"""검산 재통과: 검산 사례를 손으로 묶은 표본 계수 대신 reference 가 조립한 계수로 다시 계산해 기대값과 글자까지 견준다.

esg-lab `ts/factor-assembly/src/domain/replay.ts` 를 옮긴 테스트 준비물이다(제품 코드가 아니다. wheel 에 안 실린다).
순수하다: DB 가 없고, 사례·조립 조건·낱줄·대응표·표를 값으로 받는다.

    uv run python -m esgapi.inventory.tests.assembly_replay --json

은 TS CLI `verify-handcalc --json` 과 같은 꼴(`{summary, rows}`)을 찍는다. §4 가 둘을 줄마다 견준다.

TS → 파이썬:
    compare              → compare          (표에 조립한 계수 하나만 넣고 계산, 기대값과 글자 대조)
    withAssumptions      → _assumptions
    replayHandCases      → replay_hand_cases
    replaySummary        → replay_summary
    cli.ts verifyHandcalc → main

TS 에 없는 갈래 하나: 조립한 계수가 엔진의 표 검사를 못 지나면 `calculation_failed` 에
`{"kind": "tables_invalid"}` 로 싣는다
(TS 는 타입이 맞으면 검사 없이 계산한다. 여기서는 조립 결과가 JSON 이라 표 검사를 거쳐야 엔진에 들어간다).
"""

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from esgapi.inventory.data_loader import read_data
from esgapi.inventory.engines.scope12.engine_1.calc import calculate_raw_row
from esgapi.inventory.engines.scope12.engine_1.serialize import failure_to_dict
from esgapi.inventory.engines.scope12.engine_1.tables import TablesInvalid, validate_tables
from esgapi.inventory.engines.scope12.engine_1.types import CalcOptions, RowFailed
from esgapi.inventory.tests.support import hand_cases, read_test_data
from esgapi.reference.calc import (
    AssemblyMapping,
    FactorRecord,
    Failed,
    assemble_combustion_factor,
    assemble_purchased_electricity_factor,
)

# 낱줄과 대응표는 reference 의 테스트 준비물이 읽은 것을 그대로 쓴다(둘째 로더를 만들지 않는다).
from esgapi.reference.tests.helpers import MAPPING, RECORDS

type Json = dict[str, Any]


def replay_tables() -> Json:
    """환산표와 GWP 세트만. 계수는 없다(계수는 사례마다 조립한 것 하나를 넣는다)."""
    return {
        "unitConversions": read_data("unit-conversions.json")["unitConversions"],
        "gwpSets": read_data("gwp-sets.json")["gwpSets"],
    }


def replay_spec() -> Json:
    spec: Json = read_test_data("handcalc-assembly.json")
    return spec


def _text(value: object) -> str:
    """JS 의 JSON.stringify 와 같은 글자(차이를 적는 문장에만 쓴다)."""
    return "undefined" if value is None else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def compare(
    activity: Mapping[str, Any],
    gwp_set_id: str,
    expected: Mapping[str, Any],
    factor: Mapping[str, Any],
    assumptions: Sequence[str],
    tables: Mapping[str, Any],
) -> Json:
    """`{actualCo2e, outcome}`. 표에는 조립한 계수 하나만 넣는다: 표본 계수가 섞여 그쪽으로 계산되는 일이 없다."""
    factor_id: str = factor["id"]
    factors = [factor]
    checked = validate_tables({**tables, "factors": factors})
    if isinstance(checked, TablesInvalid):
        problems = [{"where": p.where, "problem": p.problem} for p in checked.problems]
        failure: Json = {"kind": "tables_invalid", "problems": problems}
        return {
            "actualCo2e": None,
            "outcome": {"status": "calculation_failed", "assembledFactorId": factor_id, "failure": failure},
        }
    options = CalcOptions(gwp_set_id=gwp_set_id, require_calorific_basis="net")
    result = calculate_raw_row(dict(activity), checked.tables, options)
    if isinstance(result, RowFailed):
        return {
            "actualCo2e": None,
            "outcome": {
                "status": "calculation_failed",
                "assembledFactorId": factor_id,
                "failure": failure_to_dict(result.failure),
            },
        }
    differences: list[str] = []
    if result.co2e != expected["co2e"]:
        differences.append(f"co2e: 기대 {expected['co2e']}, 결과 {result.co2e}")
    energy = None if result.energy is None else {"value": result.energy.value, "unit": result.energy.unit}
    if energy != expected["energy"]:
        differences.append(f"energy: 기대 {_text(expected['energy'])}, 결과 {_text(energy)}")
    gases = {g.gas: {"mass": g.mass, "co2e": g.co2e} for g in result.gases}
    wanted: Mapping[str, Any] = expected["gases"]
    for gas in dict.fromkeys([*wanted, *gases]):
        want = wanted.get(gas)
        got = gases.get(gas)
        if want is None or got is None or want["mass"] != got["mass"] or want["co2e"] != got["co2e"]:
            differences.append(f"{gas}: 기대 {_text(want)}, 결과 {_text(got)}")
    if result.evidence.factor.id != factor_id:
        differences.append(f"계수: {result.evidence.factor.id} 로 계산됐다")
    outcome: Json = (
        {"status": "match", "assembledFactorId": factor_id, "assumptions": list(assumptions)}
        if not differences
        else {"status": "mismatch", "assembledFactorId": factor_id, "differences": differences}
    )
    return {"actualCo2e": result.co2e, "outcome": outcome}


def _assumptions(evidence: Mapping[str, Any]) -> list[str]:
    return [f"{a['kind']}: {a['detail']}" for a in evidence["assumptions"]]


def _retarget(activity: Mapping[str, Any], **patch: str) -> Json:
    """활동 데이터에서 계수를 가리키는 칸 하나만 바꾼다. 사용량·단위·부문·산정등급은 사례 그대로다."""
    return {**activity, **patch}


def replay_hand_cases(
    cases: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    records: Sequence[FactorRecord],
    mapping: AssemblyMapping,
    tables: Mapping[str, Any],
) -> list[Json]:
    """synthetic 이 아닌 검산 사례와 `assemblyCases` 를 조립한 계수로 다시 돌린다.

    구매 전력 사례는 `electricityReplays` 의 조건으로 조립하고 활동 데이터의 `factorId` 만 조립한 계수의 id 로 바꾼다.
    연소 사례는 활동 데이터의 연료 이름만 조립 조건의 국내 연료명으로 바꾼다(표본은 `diesel` 같은 별칭을 쓴다).
    그래서 이름으로 계수를 고르는 길을 탄다: 조립된 계수의 부문·산정등급이 사례의 것과 다르면 계수를 찾지 못해 실패한다.
    """
    rows: list[Json] = []
    for case in cases:
        if case["synthetic"]:
            continue
        sample_id: str = case["factor"]["id"]
        base: Json = {
            "caseId": case["id"],
            "title": case["title"],
            "sampleFactorId": sample_id,
            "expectedCo2e": case["expected"]["co2e"],
        }
        electricity = [e for e in spec.get("electricityReplays", []) if e["sampleFactorId"] == sample_id]
        if electricity:
            if len(electricity) > 1:
                reason = "구매 전력 조립 조건이 둘 이상 적혀 있다"
                rows.append({**base, "actualCo2e": None, "outcome": {"status": "not_replayed", "reason": reason}})
                continue
            assembled = assemble_purchased_electricity_factor(electricity[0]["request"], records, mapping)
            if isinstance(assembled, Failed):
                outcome: Json = {"status": "assembly_failed", "failure": assembled.failure.to_json()}
                rows.append({**base, "actualCo2e": None, "outcome": outcome})
                continue
            factor = assembled.value.factor
            # 사례는 표본 계수를 id 로 고른다. 그 id 만 조립한 계수의 id 로 바꾼다.
            activity = _retarget(case["activity"], factorId=factor["id"])
            rows.append({**base, **compare(activity, case["gwpSetId"], case["expected"], factor, [], tables)})
            continue
        replay = [e for e in spec["replays"] if e["sampleFactorId"] == sample_id]
        if len(replay) != 1:
            skipped = next((e for e in spec["notReplayed"] if e["sampleFactorId"] == sample_id), None)
            fallback = "조립 조건이 둘 이상 적혀 있다" if len(replay) > 1 else "조립 조건이 적혀 있지 않다"
            reason = skipped["reason"] if skipped is not None else fallback
            rows.append({**base, "actualCo2e": None, "outcome": {"status": "not_replayed", "reason": reason}})
            continue
        request: Mapping[str, Any] = replay[0]["request"]
        assembled = assemble_combustion_factor(request, records, mapping)
        if isinstance(assembled, Failed):
            outcome = {"status": "assembly_failed", "failure": assembled.failure.to_json()}
            rows.append({**base, "actualCo2e": None, "outcome": outcome})
            continue
        activity = _retarget(case["activity"], fuel=request["fuel"])
        value = assembled.value
        compared = compare(
            activity, case["gwpSetId"], case["expected"], value.factor, _assumptions(value.evidence), tables
        )
        rows.append({**base, **compared})
    for extra in spec["assemblyCases"]:
        base = {
            "caseId": extra["id"],
            "title": extra["title"],
            "sampleFactorId": None,
            "expectedCo2e": extra["expected"]["co2e"],
        }
        assembled = assemble_combustion_factor(extra["request"], records, mapping)
        if isinstance(assembled, Failed):
            outcome = {"status": "assembly_failed", "failure": assembled.failure.to_json()}
            rows.append({**base, "actualCo2e": None, "outcome": outcome})
            continue
        value = assembled.value
        compared = compare(
            extra["activity"], extra["gwpSetId"], extra["expected"], value.factor, _assumptions(value.evidence), tables
        )
        rows.append({**base, **compared})
    return rows


def replay_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """전부 통과인가. 범위 밖이라 돌리지 않은 사례(`not_replayed`)는 통과로 치지 않고 따로 센다."""
    matched = sum(1 for row in rows if row["outcome"]["status"] == "match")
    not_replayed = sum(1 for row in rows if row["outcome"]["status"] == "not_replayed")
    return {
        "total": len(rows),
        "matched": matched,
        "notReplayed": not_replayed,
        "failed": len(rows) - matched - not_replayed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="검산 사례를 reference 가 조립한 계수로 다시 계산한다")
    parser.add_argument("--json", action="store_true", help="TS CLI `verify-handcalc --json` 과 같은 꼴로 찍는다")
    options = parser.parse_args(argv)
    rows = replay_hand_cases(hand_cases(), replay_spec(), RECORDS, MAPPING, replay_tables())
    summary = replay_summary(rows)
    if options.json:
        sys.stdout.write(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n")
    else:
        for row in rows:
            outcome = row["outcome"]
            sys.stdout.write(
                f"{row['caseId']}  {outcome['status']}  결과 {row['actualCo2e']} / 기대 {row['expectedCo2e']}"
                f"  ← {outcome.get('assembledFactorId', '-')}\n"
            )
        sys.stdout.write(f"{json.dumps(summary, ensure_ascii=False)}\n")
    return 0 if summary["failed"] == 0 and summary["matched"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
