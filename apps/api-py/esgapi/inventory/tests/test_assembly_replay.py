"""엔진 재통과: reference 가 조립한 계수가 inventory 엔진에 들어가 검산값을 글자까지 다시 내는가. 순수 층.

esg-lab `ts/factor-assembly/test/replay.test.ts` 의 뜻을 옮겼다. 두 가지를 잰다.
  (가) 조립한 계수가 엔진의 표 검사(validate_tables)를 문제 0 으로 지난다. 분모 74 = 골든 넷 + 별표 12 연료 29 × 조합 셋
       가운데 조립되는 70.
  (나) 조립한 계수 하나만 표에 넣고 검산 사례를 다시 계산하면 기대값과 글자까지 같다.
       줄 10 = synthetic 아닌 사례 9 + N01.

이 테스트는 기대값을 갖지 않는다: 사례의 기대값은 tests/data/handcalc-cases.json, N01 의 기대값은
tests/data/handcalc-assembly.json(둘 다 esg-lab 에서 글자 그대로 옮긴 사본, 출처는 tests/data/README.md)에서 읽는다.
TS 와의 대조(줄 10 의 다섯 칸)는 여기가 아니라 scripts/section4-PY8c.sh 가 한다(esg-lab 이 있는 기계에서만 된다).
"""

import json
from decimal import Decimal
from typing import Any

import pytest

from esgapi.inventory.data_loader import read_data
from esgapi.inventory.engines.scope12.engine_1.calc import calculate_raw_row
from esgapi.inventory.engines.scope12.engine_1.tables import TablesOk, validate_tables
from esgapi.inventory.engines.scope12.engine_1.types import CalcOptions, RowOk
from esgapi.inventory.tests.assembly_replay import replay_hand_cases, replay_spec, replay_summary, replay_tables
from esgapi.inventory.tests.support import hand_cases
from esgapi.reference.calc import Failed, assemble_combustion_factor, national_calorific_fuels
from esgapi.reference.tests.helpers import GOLDEN, GROUP_A, MAPPING, RECORDS, TIER1, TIER2, assemble, swap, value_of

CASES = hand_cases()
SPEC = replay_spec()
TABLES = replay_tables()
ROWS = replay_hand_cases(CASES, SPEC, RECORDS, MAPPING, TABLES)
REAL_IDS = ["H01", "H02", "H03", "H04", "H05", "H06", "H07", "H12", "H13"]
_SAMPLE: dict[str, Any] = read_data("factors.kr-ets-sample.json")
SAMPLE_IDS: set[str] = {factor["id"] for factor in _SAMPLE["factors"]}


def _row(case_id: str, rows: list[dict[str, Any]] = ROWS) -> dict[str, Any]:
    found = [row for row in rows if row["caseId"] == case_id]
    assert len(found) == 1, case_id
    return found[0]


def _problems(factor: dict[str, Any]) -> list[str]:
    """조립한 계수 하나를 패키지의 환산표·GWP 세트와 묶어 엔진의 표 검사에 넣는다. 문제의 목록(없으면 빈 목록)."""
    raw = {**read_data("unit-conversions.json"), **read_data("gwp-sets.json"), "factors": [factor]}
    checked = validate_tables(raw)
    if isinstance(checked, TablesOk):
        assert [f.id for f in checked.tables.factors] == [factor["id"]]
        return []
    return [f"{p.where}: {p.problem}" for p in checked.problems]


# ── (가) 표 검사 ──────────────────────────────────────────────────────


def test_every_assembled_factor_passes_the_engine_table_check() -> None:
    """분모 74: 골든 넷(연소 둘, 전력 둘) + 별표 12 연료 29 × 조합 셋 = 87 가운데 조립되는 70."""
    golden = sorted(GOLDEN.glob("*.expected.json"))
    assert len(golden) == 4
    checked = 0
    for path in golden:
        expected = json.loads(path.read_text(encoding="utf-8"))
        assert expected["ok"] is True, path.name
        assert _problems(expected["value"]["factor"]) == [], path.name
        checked += 1

    fuels = national_calorific_fuels(RECORDS)
    assert len(fuels) == 29
    per_mode = [0, 0, 0]
    for fuel in fuels:
        for index, tiers in enumerate([TIER2, GROUP_A, TIER1]):
            result = assemble(fuel=fuel, tiers=tiers, powerGeneration=False)
            if isinstance(result, Failed):
                continue
            assert _problems(result.value.factor) == [], (fuel, index)
            per_mode[index] += 1
            checked += 1
    assert (per_mode, checked) == ([22, 24, 24], 74)


def test_the_table_check_is_not_vacuous() -> None:
    """뒤집어 재기: 조립한 계수에서 꼭 있어야 하는 칸을 빼면 표 검사가 문제를 낸다."""
    factor = dict(value_of(assemble()).factor)
    del factor["calorific"]
    assert _problems(factor) != []


# ── (나) 검산 재통과 ──────────────────────────────────────────────────


def test_all_ten_rows_match() -> None:
    assert [case["id"] for case in CASES if not case["synthetic"]] == REAL_IDS
    assert [row["caseId"] for row in ROWS] == [*REAL_IDS, "N01"]
    assert [row["caseId"] for row in ROWS if row["outcome"]["status"] == "match"] == [*REAL_IDS, "N01"]
    assert replay_summary(ROWS) == {"total": 10, "matched": 10, "notReplayed": 0, "failed": 0}


@pytest.mark.parametrize("case_id", [*REAL_IDS, "N01"])
def test_replayed_value_equals_the_hand_calculation(case_id: str) -> None:
    """기대값은 사본 파일에서 다시 읽는다(재통과가 실어 준 expectedCo2e 를 믿지 않는다)."""
    row = _row(case_id)
    if case_id == "N01":
        (source,) = SPEC["assemblyCases"]
    else:
        (source,) = [case for case in CASES if case["id"] == case_id]
    assert source["id"] == case_id
    assert row["outcome"]["status"] == "match", row["outcome"]
    assert row["actualCo2e"] == source["expected"]["co2e"]
    assert row["expectedCo2e"] == source["expected"]["co2e"]


def test_the_engine_used_the_assembled_factor_and_not_a_sample() -> None:
    """결과의 근거(evidence.factor.id)가 조립한 계수의 id 다. 패키지의 표본 계수 id 는 하나도 쓰이지 않았다."""
    used = {row["outcome"]["assembledFactorId"] for row in ROWS}
    assert len(used) == 4
    assert used.isdisjoint(SAMPLE_IDS)
    # 표본 사례는 표본 계수의 id 를 갖고(그래서 무엇을 대신했는지 알 수 있다), 조립만 한 사례는 갖지 않는다.
    assert all(_row(case_id)["sampleFactorId"] in SAMPLE_IDS for case_id in REAL_IDS)
    assert _row("N01")["sampleFactorId"] is None
    # 재통과가 「다른 계수로 계산됐다」를 어긋남으로 적는 자리가 비어 있다.
    assert [row for row in ROWS if "differences" in row["outcome"]] == []


def test_assumed_mappings_are_carried_into_the_outcome() -> None:
    assert _row("H04")["outcome"]["assumptions"] == [
        "fuel_state: 도시가스(LNG) → 기체",
        "fuel_name: 도시가스(LNG) → 천연가스 (kr-ets-byl10)",
    ]
    assert _row("H01")["outcome"]["assumptions"] == []
    assert _row("H06")["outcome"]["assumptions"] == []


def test_group_minimum_is_larger_than_tier2() -> None:
    """A 그룹 최소 조합(N01)은 같은 사용량의 Tier 2 조합(H01)보다 크다. 값은 둘 다 사본 파일의 것이다."""
    assert Decimal(_row("N01")["actualCo2e"]) > Decimal(_row("H01")["actualCo2e"])


def test_evidence_of_the_assembled_factor_reaches_the_engine_result() -> None:
    """조립된 계수의 부문·매개변수별 산정등급·산화계수·출처가 엔진 결과의 근거까지 이어진다."""
    (extra,) = SPEC["assemblyCases"]
    factor = value_of(assemble_combustion_factor(extra["request"], RECORDS, MAPPING)).factor
    checked = validate_tables({**TABLES, "factors": [factor]})
    assert isinstance(checked, TablesOk)
    result = calculate_raw_row(extra["activity"], checked.tables, CalcOptions(gwp_set_id=extra["gwpSetId"]))
    assert isinstance(result, RowOk), result
    tiers = result.evidence.parameter_tiers
    assert tiers is not None
    assert (tiers.calorific, tiers.co2, tiers.non_co2, tiers.oxidation) == (2, 1, 1, 1)
    assert result.evidence.sector == extra["activity"]["sector"]
    assert result.evidence.oxidation_factor == "1"
    assert result.evidence.factor.id == factor["id"]
    assert result.evidence.factor.source == checked.tables.factors[0].source


# ── 뒤집어 재기 ───────────────────────────────────────────────────────


def test_a_different_sector_is_not_counted_as_a_pass() -> None:
    """조립 조건의 부문이 사례와 다르면 이름·부문으로 계수를 찾지 못한다. 통과 0."""
    wrong = {
        **SPEC,
        "assemblyCases": [],
        "electricityReplays": [],
        "replays": [
            {**r, "request": {**r["request"], "industry": {"sector": "residential_other"}}} for r in SPEC["replays"]
        ],
    }
    rows = replay_hand_cases(CASES, wrong, RECORDS, MAPPING, TABLES)
    summary = replay_summary(rows)
    # 전력 조건을 뺐으므로 전력 사례 둘(H06·H07)은 조건이 없어 돌지 않는다. 연소 일곱은 전부 실패다.
    assert summary == {"total": 9, "matched": 0, "notReplayed": 2, "failed": 7}
    assert rows[0]["outcome"]["status"] == "calculation_failed"
    assert rows[0]["outcome"]["failure"]["kind"] == "factor_not_found"
    assert rows[0]["actualCo2e"] is None


def test_a_case_without_a_condition_is_not_replayed_and_not_a_pass() -> None:
    empty: dict[str, Any] = {"replays": [], "notReplayed": [], "assemblyCases": []}
    rows = replay_hand_cases(CASES, empty, RECORDS, MAPPING, TABLES)
    assert replay_summary(rows) == {"total": 9, "matched": 0, "notReplayed": 9, "failed": 0}
    assert {row["outcome"]["reason"] for row in rows} == {"조립 조건이 적혀 있지 않다"}
    # 까닭을 적어 둔 것은 그 까닭이 나온다.
    (first,) = SPEC["replays"][:1]
    noted = {**empty, "notReplayed": [{"sampleFactorId": first["sampleFactorId"], "reason": "범위 밖"}]}
    reasons = [r["outcome"]["reason"] for r in replay_hand_cases(CASES, noted, RECORDS, MAPPING, TABLES)]
    assert reasons.count("범위 밖") == sum(1 for c in CASES if c["factor"]["id"] == first["sampleFactorId"])


def test_one_changed_character_in_a_record_is_a_mismatch() -> None:
    """경유 CO2 계수의 낱줄 값 한 글자(73,200 → 73,201): 경유 사례는 어긋남, 도시가스 사례는 그대로 맞음."""
    record_id = "kr-ets-byl12:ef:p3r3:CO2"
    (original,) = [r for r in RECORDS if r.id == record_id]
    assert original.value_raw == "73,200"
    rows = replay_hand_cases(CASES, SPEC, swap(record_id, value_raw="73,201"), MAPPING, TABLES)
    assert _row("H01", rows)["outcome"]["status"] == "mismatch"
    assert _row("H01", rows)["actualCo2e"] != _row("H01", rows)["expectedCo2e"]
    assert _row("H04", rows)["outcome"]["status"] == "match"
    assert _row("H06", rows)["outcome"]["status"] == "match"
