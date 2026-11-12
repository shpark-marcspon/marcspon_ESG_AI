"""꼴 materiality.result@2(contracts/shapes.py, 밴드 IR2a): 고정 스키마 파일과 글자까지 같고, @1 파일은 그대로이며, 1부
칸은 @1 과 같은 TypedDict 이고, 지은 예시가 꼴에 맞아 JSON 왕복하며, 2부 갈래의 칸 집합이 발주서 §2-1 표와 같고 섞임·
모르는 키·좁은 칸 밖 값을 거부한다(발주서 §3 S1).

예시(tests/data/examples/result2-sample.json)는 손으로 지은 합성이다(1부 칸은 result-sample.json 그대로, 2부는 전부
지어낸 「가상…」). 프론트가 2부 화면을 짓는 데 쓴다.
"""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast, get_args, get_type_hints

import pytest
from pydantic import ValidationError

from esgapi.materiality.contracts import shapes

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes"
EXAMPLES = DATA / "examples"
V2 = shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2]


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def check(result: dict[str, Any]) -> None:
    assert next(iter(result)) == "schemaVersion"
    shapes.RESULT_SHAPES[result["schemaVersion"]].validate_python(result, strict=True)


def rejected(result: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        V2.validate_python(result, strict=True)


def at(result: dict[str, Any], path: tuple[Any, ...]) -> Any:
    node: Any = result
    for step in path:
        node = node[step]
    return node


def test_the_v2_schema_is_pinned_and_v1_keeps_its_file() -> None:
    text = json.dumps(V2.json_schema(), ensure_ascii=False, indent=2) + "\n"
    pinned = (PINNED / "materiality.result@2.schema.json").read_text(encoding="utf-8")
    assert text == pinned
    v1 = shapes.RESULT_SHAPES[shapes.RESULT_SHAPE]
    assert json.dumps(v1.json_schema(), ensure_ascii=False, indent=2) + "\n" == (
        PINNED / "materiality.result@1.schema.json"
    ).read_text(encoding="utf-8")
    assert set(shapes.RESULT_SHAPES) == {"materiality.result@1", "materiality.result@2"}
    assert (
        hashlib.sha256(pinned.encode()).hexdigest()[:16] == "d8a2b7515152125b"
    )  # C0 에 감독에게 알린 값(IR2b — 기간 경고 코드 둘)


def test_part1_fields_are_the_v1_types() -> None:
    v1 = get_type_hints(shapes.MaterialityResult, include_extras=True)
    v2 = get_type_hints(shapes.MaterialityResult2, include_extras=True)
    for key in ("company", "scope", "part1"):
        assert v2[key] is v1[key]
    assert list(v2) == ["schemaVersion", "company", "scope", "settings", "part1", "part2", "warnings"]
    settings1 = get_type_hints(shapes.MaterialitySettings)
    settings2 = get_type_hints(shapes.MaterialitySettings2)
    assert {k: settings2[k] for k in settings1} == settings1
    assert list(settings2) == [*settings1, "part2"]


def test_the_example_fits_and_round_trips() -> None:
    result = load("result2-sample.json")
    check(result)
    assert result["part1"] == load("result-sample.json")["part1"]  # 1부 칸은 @1 예시 그대로
    dumped = json.loads(V2.dump_json(result))
    assert dumped == result
    sub = result["part2"]["topics"][0]["subtopics"][0]
    statuses = {
        (s["impact"]["status"], s["financial"]["status"], s["pathway"]["status"])
        for t in result["part2"]["topics"]
        for s in t["subtopics"]
    }
    assert statuses == {("done", "done", "done"), ("failed", "failed", "not_run"), ("done", "done", "not_run")}
    assert [r["i"] for r in sub["pathway"]["rows"]] == [1, 2]
    assert sub["pathway"]["rows"][1]["riskType"] is None


def keys(cls: Any) -> list[str]:
    return list(get_type_hints(cls))


def test_branch_fields_are_the_order_table() -> None:
    """발주서 §2-1 표의 칸 그대로."""
    assert keys(shapes.MaterialityPart2Done) == ["status", "input", "topics"]
    assert keys(shapes.MaterialityPart2TopicResult) == ["topic", "description", "subtopics"]
    assert keys(shapes.MaterialitySubtopicResult) == [
        "name",
        "description",
        "autofilled",
        "impact",
        "financial",
        "pathway",
    ]
    assert keys(shapes.MaterialityImpactDone) == ["status", "parsed", "rows"]
    assert keys(shapes.MaterialityPart2Failed) == ["status", "raw", "parseError", "failure"]
    assert keys(shapes.MaterialityImpactRow) == ["impactDefinition", "impactType", "valueChainActivities", "context"]
    assert keys(shapes.MaterialityFinancialRow) == [
        "impactDefinition",
        "impactType",
        "riskType",
        "valueChainActivities",
        "context",
    ]
    assert keys(shapes.MaterialityPathwayRow) == [
        "i",
        "impactDefinition",
        "impactDriver",
        "businessImpact",
        "financialImpact",
        "impactType",
        "riskType",
        "context",
    ]
    assert keys(shapes.MaterialityContext) == ["regulations", "controversies"]
    assert keys(shapes.MaterialityContextItem) == ["title", "summary", "url"]
    assert keys(shapes.MaterialityWarning2) == ["code", "message", "topic", "phase", "subtopic"]
    assert keys(shapes.MaterialityPart2Settings) == ["model", "maxOutputTokens", "latestEventMode", "promptIds"]
    assert keys(shapes.Part2Input) == [
        "company",
        "industry",
        "valueChain",
        "latestEventMode",
        "topics",
        "subtopics",
        "source",
    ]
    v1_codes = set(get_args(shapes.WarningCode))
    v2_codes = set(get_args(shapes.WarningCode2))
    assert v2_codes - v1_codes == {
        "answer_truncated",
        "xlsx_cell_truncated",
        "value_chain_activity_unknown",
        "pathway_row_mismatch",
        "rows_dropped",
        "impact_type_unexpected",
        "items_out_of_range",
        "item_date_unreadable",
    }
    assert v1_codes <= v2_codes


def test_missing_or_extra_keys_are_rejected() -> None:
    base = load("result2-sample.json")
    broken: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    broken.append({**base, "usage": {"calls": 9}})
    broken.append({**base, "schemaVersion": "materiality.result@1"})
    sub = ("part2", "topics", 0, "subtopics", 0)
    for path in (
        ("settings", "part2"),
        ("part2",),
        ("part2", "input"),
        ("part2", "topics", 0),
        sub,
        (*sub, "impact"),
        (*sub, "impact", "rows", 0),
        (*sub, "impact", "rows", 0, "context"),
        (*sub, "impact", "rows", 0, "context", "regulations", 0),
        (*sub, "financial", "rows", 0),
        (*sub, "pathway", "rows", 0),
        ("part2", "topics", 1, "subtopics", 0, "impact"),
        ("part2", "topics", 1, "subtopics", 0, "pathway"),
        ("warnings", 0),
    ):
        nested = copy.deepcopy(base)
        at(nested, path)["extra"] = None
        broken.append(nested)
    for path, key in (
        (("settings", "part2"), "maxOutputTokens"),
        (("settings", "part2", "promptIds"), "pathway"),
        (sub, "autofilled"),
        ((*sub, "pathway", "rows", 0), "context"),
        ((*sub, "financial", "rows", 0), "riskType"),
        (("part2", "topics", 1, "subtopics", 0, "impact"), "parseError"),
        (("warnings", 0), "phase"),
        (("warnings", 0), "subtopic"),
    ):
        missing = copy.deepcopy(base)
        del at(missing, path)[key]
        broken.append(missing)
    for result in broken:
        rejected(result)


def test_narrow_fields_and_branches() -> None:
    base = load("result2-sample.json")
    sub = ("part2", "topics", 0, "subtopics", 0)
    failed = base["part2"]["topics"][1]["subtopics"][0]["impact"]
    done = at(base, (*sub, "impact"))
    changes: list[tuple[tuple[Any, ...], Any]] = [
        (("part2", "input", "source"), "upload"),
        (("settings", "part2", "maxOutputTokens"), -1),
        (("settings", "part2", "maxOutputTokens"), "32768"),
        ((*sub, "pathway", "rows", 0, "i"), "1"),  # 정수나 null
        ((*sub, "impact", "rows", 0, "impactType"), 1),  # 칸은 글자나 null
        ((*sub, "impact", "rows", 0, "valueChainActivities"), [None]),
        ((*sub, "impact", "parsed"), ["가상"]),  # 객체만
        ((*sub, "impact"), {**done, "failure": failed["failure"]}),  # done 에 failure
        ((*sub, "impact"), {**failed, "status": "done"}),  # done 에 raw
        ((*sub, "financial"), {"status": "not_run"}),
        ((*sub, "pathway"), {"status": "skipped", "message": "가상"}),
        (("part2", "topics", 1, "subtopics", 0, "impact", "failure", "kind"), "call_failed"),
        (("warnings", 0, "code"), "unknown_code"),
        (("warnings", 4, "phase"), "part2"),
        (("part2",), {"status": "done", "message": "가상"}),
    ]
    for path, value in changes:
        broken = copy.deepcopy(base)
        at(broken, path[:-1])[path[-1]] = value
        rejected(broken)
    not_run = copy.deepcopy(base)
    not_run["part2"] = {"status": "not_run", "message": "가상"}
    check(not_run)
