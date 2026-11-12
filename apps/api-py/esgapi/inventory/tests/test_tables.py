"""기준정보 표 검사. 순수 층.

esg-lab `ts/ghg-calc/test/tables.test.ts` 7건을 옮기고, dataclass 로 바꾸는 단계의 것을 더했다.
"""

import json
from typing import Any

import pytest

from esgapi.inventory.engines.scope12.engine_1.serialize import tables_to_dict
from esgapi.inventory.engines.scope12.engine_1.tables import (
    TableProblem,
    TablesInvalid,
    TablesOk,
    merge_tables,
    validate_tables,
)
from esgapi.inventory.tests.support import load_tables, package_parts, raw_tables, synthetic_tables


def problems_of(raw: object) -> list[tuple[str, str]]:
    result = validate_tables(raw)
    assert isinstance(result, TablesInvalid), "검사를 통과하면 안 된다"
    assert result.ok is False
    return [(p.where, p.problem) for p in result.problems]


def test_the_repository_data_files_pass() -> None:
    assert isinstance(validate_tables(raw_tables()), TablesOk)
    assert isinstance(validate_tables(synthetic_tables()), TablesOk)


def test_a_number_without_a_source_cannot_enter_the_tables() -> None:
    raw = raw_tables()
    del raw["factors"][0]["source"]
    assert problems_of(raw) == [("factors[0]", "출처(source)가 없다")]


def test_a_cited_source_needs_a_url_and_a_checked_date() -> None:
    raw = raw_tables()
    raw["gwpSets"][0]["source"] = {"kind": "cited", "title": "t", "url": "", "checkedOn": "어제"}
    assert [problem for _, problem in problems_of(raw)] == [
        "cited 출처에 url 이 없다",
        "cited 출처에 확인 일자(checkedOn, YYYY-MM-DD)가 없다",
    ]


def test_a_value_written_as_a_json_number_is_rejected() -> None:
    raw = raw_tables()
    raw["unitConversions"][0]["factor"] = 0.001
    assert problems_of(raw) == [("unitConversions[0].factor", "십진 문자열이 아니다: 0.001")]


def test_a_negative_factor_is_rejected() -> None:
    raw = raw_tables()
    raw["gwpSets"][0]["values"]["CH4"] = "-21"
    assert problems_of(raw) == [("gwpSets[0].values.CH4", '음수다: "-21"')]


def test_missing_arrays_and_non_objects_are_rejected() -> None:
    assert problems_of({"factors": [], "gwpSets": []}) == [("unitConversions", "배열이 없다")]
    assert problems_of(None) == [("$", "객체가 아니다")]
    assert problems_of([]) == [("$", "객체가 아니다")]


def test_every_number_in_the_data_files_is_synthetic_or_cited_with_url_and_date() -> None:
    tables = load_tables()
    for record in [*tables.factors, *tables.gwp_sets]:
        synthetic = record.id.startswith("synthetic")
        assert record.source.kind == ("synthetic" if synthetic else "cited"), record.id
    for conversion in tables.unit_conversions:
        assert conversion.source.kind == "definition"


# ── 파이썬으로 옮기며 더한 것 ─────────────────────────────────────────


def test_tables_survive_a_round_trip_through_the_dataclasses_letter_for_letter() -> None:
    """자료 파일 → dataclass → dict 가 글자까지(키의 순서까지) 같다. 값이나 선택 칸을 흘리지 않는다는 것."""
    for raw in (merge_tables(*package_parts()), merge_tables(synthetic_tables()), raw_tables()):
        result = validate_tables(raw)
        assert isinstance(result, TablesOk)
        assert json.dumps(tables_to_dict(result.tables), ensure_ascii=False) == json.dumps(raw, ensure_ascii=False)


def test_the_problem_keeps_a_summary_without_the_received_value() -> None:
    raw = raw_tables()
    raw["gwpSets"][0]["values"]["CH4"] = "-21"
    result = validate_tables(raw)
    assert isinstance(result, TablesInvalid)
    assert result.problems == (TableProblem(where="gwpSets[0].values.CH4", problem='음수다: "-21"', summary="음수다"),)


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (None, "null"),
        (True, "true"),
        (1.5, "1.5"),
        (2.0, "2"),
        (1e21, "1e+21"),
        (1e-7, "1e-7"),
        ("1e3", '"1e3"'),
        ("１２", '"１２"'),
        ('a"b', '"a\\"b"'),
        ([1, "2", None], '[1,"2",null]'),
        ({"b": 1, "a": [True]}, '{"b":1,"a":[true]}'),
        ("9" * 65, '"' + "9" * 65 + '"'),
    ],
)
def test_the_rejected_value_is_shown_the_way_json_stringify_shows_it(value: Any, shown: str) -> None:
    raw = raw_tables()
    raw["unitConversions"][0]["factor"] = value
    assert problems_of(raw) == [("unitConversions[0].factor", f"십진 문자열이 아니다: {shown}")]


def test_a_missing_value_is_shown_as_undefined() -> None:
    raw = raw_tables()
    del raw["unitConversions"][0]["factor"]
    assert problems_of(raw) == [("unitConversions[0].factor", "십진 문자열이 아니다: undefined")]


def test_unknown_kinds_are_named() -> None:
    raw = raw_tables()
    raw["factors"][0]["kind"] = "scope3"
    raw["gwpSets"][0]["source"] = {"note": "kind 가 없다"}
    assert problems_of(raw) == [
        ("gwpSets[0]", "알 수 없는 출처 종류: undefined"),
        ("factors[0]", "알 수 없는 계수 종류: scope3"),
    ]


def test_every_structural_problem_of_the_ts_validator() -> None:
    """TS 의 테스트가 보지 않던 문제 문장들. 글자는 TS 의 소스에서 옮겼다."""
    raw: dict[str, Any] = {
        "unitConversions": ["x", {"from": "", "to": "b", "factor": "1", "source": {"kind": "definition", "note": ""}}],
        "gwpSets": [7, {"id": "", "label": "l", "source": {"kind": "synthetic", "note": "n"}, "values": []}],
        "factors": [
            None,
            {"id": "f", "version": "", "source": {"kind": "synthetic", "note": "n"}, "emissionFactors": "none"},
            {
                "kind": "combustion",
                "id": "c",
                "version": "v",
                "source": {"kind": "cited", "title": "", "url": "ftp://x", "checkedOn": "2026-10-01"},
                "emissionFactors": [3, {"gas": "", "value": "1", "massUnit": "kg"}],
                "fuel": "",
                "combustionType": "both",
                "calorific": {"value": "x", "basis": "low", "energyUnit": "", "perUnit": "L"},
                "oxidationFactor": None,
            },
            {
                "kind": "combustion",
                "id": "c2",
                "version": "v",
                "source": {"kind": "synthetic", "note": "n"},
                "emissionFactors": [],
                "fuel": "f",
                "combustionType": "mobile",
            },
            {
                "kind": "purchased_energy",
                "id": "p",
                "version": "v",
                "source": {"kind": "synthetic", "note": "n"},
                "emissionFactors": [],
                "energyType": "steam",
            },
        ],
    }
    assert problems_of(raw) == [
        ("unitConversions[0]", "객체가 아니다"),
        ("unitConversions[1]", "from/to 가 없다"),
        ("unitConversions[1]", "definition 출처에 note 가 없다"),
        ("gwpSets[0]", "객체가 아니다"),
        ("gwpSets[1]", "id/label 이 없다"),
        ("gwpSets[1]", "values 가 없다"),
        ("factors[0]", "객체가 아니다"),
        ("factors[1]", "id/version 이 없다"),
        ("factors[1]", "emissionFactors 가 없다"),
        ("factors[2]", "cited 출처에 url 이 없다"),
        ("factors[2]", "cited 출처에 title 이 없다"),
        ("factors[2].emissionFactors[0]", "객체가 아니다"),
        ("factors[2].emissionFactors[1]", "gas/massUnit 이 없다"),
        ("factors[2]", "fuel 이 없다"),
        ("factors[2]", "combustionType 이 stationary/mobile 이 아니다"),
        ("factors[2].calorific.value", '십진 문자열이 아니다: "x"'),
        ("factors[2]", "calorific.basis 가 net/gross 가 아니다"),
        ("factors[2]", "calorific 단위가 없다"),
        ("factors[2].oxidationFactor", "십진 문자열이 아니다: null"),
        ("factors[3]", "calorific 이 없다"),
        ("factors[4]", "energyType 이 electricity/heat 가 아니다"),
        ("factors[4]", "perUnit 이 없다"),
    ]


def test_fields_the_ts_validator_did_not_look_at_are_checked_when_building() -> None:
    """TS 는 검사를 통과한 값을 타입만 믿고 넘겼다. dataclass 로 바꾸는 단계가 그 칸들을 본다(TS 와 다른 자리)."""
    raw = raw_tables()
    del raw["factors"][0]["emissionFactors"][1]["perEnergyUnit"]
    raw["factors"][0]["year"] = "2025"
    raw["factors"][1]["variant"] = 3
    raw["factors"][2]["year"] = True
    raw["gwpSets"][0]["source"]["locator"] = None
    raw["unitConversions"][0]["source"]["note"] = "ok"
    assert problems_of(raw) == [
        ("gwpSets[0].source", "locator 가 문자열이 아니다 (없으면 키를 뺀다)"),
        ("factors[0].emissionFactors[1]", "perEnergyUnit 이 없다"),
        ("factors[0]", "year 가 정수가 아니다 (없으면 키를 뺀다)"),
        ("factors[1]", "variant 가 문자열이 아니다 (없으면 키를 뺀다)"),
        ("factors[2]", "year 가 정수가 아니다 (없으면 키를 뺀다)"),
    ]


def test_json_has_no_integer_type_so_2_point_0_is_tier_2() -> None:
    """JSON 의 `2.0` 은 JS 에서 2 다. 등급과 연도는 정수인 실수도 받는다(TS 와 같게). bool 은 받지 않는다."""
    raw = raw_tables()
    raw["factors"][0]["parameterTiers"] = {"calorific": 2.0, "co2": 2, "nonCo2": 1, "oxidation": 2}
    raw["factors"][0]["year"] = 2025.0
    result = validate_tables(raw)
    assert isinstance(result, TablesOk)
    factor = result.tables.factors[0]
    assert factor.kind == "combustion"
    assert factor.parameter_tiers is not None
    assert (factor.parameter_tiers.calorific, type(factor.parameter_tiers.calorific), factor.year) == (2, int, 2025)


def test_merge_tables_only_concatenates() -> None:
    a = {"factors": [1], "gwpSets": None}
    b = {"factors": [2, 3], "unitConversions": "not-a-list", "extra": [9]}
    assert merge_tables(a, b) == {"unitConversions": ["not-a-list"], "factors": [1, 2, 3], "gwpSets": []}
    assert merge_tables() == {"unitConversions": [], "factors": [], "gwpSets": []}
