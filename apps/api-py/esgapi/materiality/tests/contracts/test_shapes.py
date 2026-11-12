"""꼴 materiality.input@1·materiality.result@1(contracts/shapes.py): 고정 스키마 파일과 글자까지 같고, 지은 예시가 꼴에
맞으며, 결과 꼴은 모르는 키·빠진 키·갈래 섞임을 거부하고, part2 는 not_run 만 받고, 입력 꼴은 토픽 중복·모르는 키를
거부하고 받은 dict 를 고치지 않는다(발주서 §3 S1).

예시(tests/data/examples/*-sample.json)는 로직보다 먼저 손으로 지은 것이다(기업·토픽·답은 전부 지어낸 것). 프론트가
화면을 짓는 데 쓴다.
"""

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from pydantic import ValidationError

from esgapi.core.llm.types import LlmResultKind, ToolLoopFailure
from esgapi.dataverify.contracts import shapes as dataverify_shapes
from esgapi.greenwash.contracts import shapes as greenwash_shapes
from esgapi.inventory.contracts import shapes as inventory_shapes
from esgapi.materiality.contracts import shapes
from esgapi.translation.contracts import shapes as translation_shapes

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes"
EXAMPLES = DATA / "examples"
ALL_SHAPES = {**shapes.INPUT_SHAPES, **shapes.RESULT_SHAPES}


def pinned_text(shape: str) -> str:
    return json.dumps(ALL_SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def check_result(result: dict[str, Any]) -> None:
    assert next(iter(result)) == "schemaVersion"
    shapes.RESULT_SHAPES[result["schemaVersion"]].validate_python(result, strict=True)


def rejected_result(result: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)


def rejected_input(received: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        shapes.INPUT_SHAPES[shapes.INPUT_SHAPE].validate_python(received, strict=True)


@pytest.mark.parametrize("shape", sorted(ALL_SHAPES))
def test_the_json_schema_is_pinned(shape: str) -> None:
    assert pinned_text(shape) == (PINNED / f"{shape}.schema.json").read_text(encoding="utf-8")


def test_every_shape_is_pinned() -> None:
    files = {p.name.removesuffix(".schema.json") for p in PINNED.glob("*.schema.json")}
    # 둘째 결과 materiality.digest@1 의 고정 파일은 tests/contracts/test_digest_shapes.py 가 견준다(IR3c)
    pinned = files - {"materiality.digest@1"}
    assert set(ALL_SHAPES) == pinned == {"materiality.input@1", "materiality.result@1", "materiality.result@2"}


def test_the_examples_fit_their_shapes() -> None:
    received = load("input-sample.json")
    assert shapes.check_input(received) is received
    result = load("result-sample.json")
    check_result(result)
    topics = result["part1"]["topics"]
    assert [t["topic"] for t in topics] == [t["topic"] for t in received["topics"]]  # 입력 차례
    statuses = {(t["regulation"]["status"], t["controversy"]["status"]) for t in topics}
    assert statuses == {("done", "done"), ("failed", "failed"), ("not_run", "not_run")}  # 프론트가 갈래를 다 본다
    assert {item["region"] for item in topics[0]["regulation"]["items"]} == {"KR", "EU"}
    assert topics[0]["controversy"]["topicNameMismatch"] is True
    assert result["company"] == received["company"]


def test_a_missing_or_extra_key_is_rejected_by_the_result_shape() -> None:
    base = load("result-sample.json")
    broken: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    broken.append({**base, "unknown": 1})
    broken.append({**base, "usage": {"calls": 3}})  # 사용량은 싣지 않는다
    broken.append({**base, "schemaVersion": "materiality.result@2"})
    for path, key in (
        (("scope",), "extra"),
        (("settings",), "extra"),
        (("part1",), "extra"),
        (("part1", "keywords"), "failure"),
        (("part1", "topics", 0), "extra"),
        (("part1", "topics", 0, "regulation", "items", 0), "secondary_url"),
        (("part1", "topics", 0, "controversy", "items", 0), "extra"),
        (("part1", "topics", 1, "regulation", "failure"), "budgetSource"),
        (("warnings", 0), "extra"),
    ):
        nested = copy.deepcopy(base)
        at: Any = nested
        for step in path:
            at = at[step]
        at[key] = None
        broken.append(nested)
    for path, key in (
        (("scope",), "whitelist"),
        (("settings", "promptIds"), "keywords"),
        (("part1", "topics", 0), "keywordStr"),
        (("part1", "topics", 0, "regulation"), "selfCheck"),
        (("part1", "topics", 0, "regulation", "items", 0), "region"),
        (("part1", "topics", 1, "regulation"), "parseError"),
        (("warnings", 0), "topic"),
    ):
        missing = copy.deepcopy(base)
        at = missing
        for step in path:
            at = at[step]
        del at[key]
        broken.append(missing)
    for result in broken:
        rejected_result(result)


def test_narrow_fields_stay_narrow() -> None:
    base = load("result-sample.json")
    changes: list[tuple[tuple[Any, ...], Any]] = [
        (("scope", "whitelist"), "cell17"),  # 셀 17 현행 판은 대조 전용 — 결과에 오지 않는다
        (("scope", "sector"), "public"),
        (("scope", "topicCount"), -1),
        (("settings", "temperature"), 0.1),  # 수는 글자로
        (("part1", "topics", 0, "regulation", "items", 0, "title"), 5),  # 항목 칸은 글자나 null
        (("part1", "topics", 0, "regulation", "topicNameMismatch"), True),  # 셀 17 은 견주지 않는다
        (("part1", "topics", 0, "controversy", "items", 0, "region"), "KR"),
        (("part1", "topics", 0, "regulation", "parsed"), ["가상"]),  # 객체만
        (("part1", "topics", 0, "regulation", "selfCheck"), "가상 메모"),
        (("part1", "topics", 1, "regulation", "failure", "kind"), "call_failed"),
        (("part1", "keywords", "byTopic", 0, "keywords"), [1, 2]),
        (("warnings", 0, "code"), "unknown_code"),
    ]
    for path, value in changes:
        broken = copy.deepcopy(base)
        at: Any = broken
        for step in path[:-1]:
            at = at[step]
        at[path[-1]] = value
        rejected_result(broken)


def test_a_branch_cannot_mix_its_fields() -> None:
    base = load("result-sample.json")
    done_reg = base["part1"]["topics"][0]["regulation"]
    failed = base["part1"]["topics"][1]["regulation"]
    failure = failed["failure"]
    keywords = base["part1"]["keywords"]

    def with_topic(index: int, side: str, outcome: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(base)
        result["part1"]["topics"][index][side] = outcome
        return result

    rejected_result(with_topic(0, "regulation", {**done_reg, "failure": failure}))  # done 에 failure
    rejected_result(with_topic(0, "regulation", {**done_reg, "status": "failed"}))  # failed 에 parsed
    rejected_result(with_topic(1, "regulation", {**failed, "status": "not_run"}))  # not_run 에 raw
    rejected_result(with_topic(1, "regulation", {**failed, "failure": None}))  # failed 에 failure 없음
    rejected_result(with_topic(2, "controversy", {"status": "skipped", "message": "가상"}))
    rejected_result(with_topic(0, "controversy", done_reg))  # 규제 항목은 컨트로버시 자리에 못 온다
    wrongs: list[dict[str, Any]] = [
        {**keywords, "status": "failed"},
        {"status": "failed", "raw": None, "failure": failure, "byTopic": []},
        {"status": "not_run", "message": "가상", "raw": None},
    ]
    for wrong in wrongs:
        result = copy.deepcopy(base)
        result["part1"]["keywords"] = wrong
        rejected_result(result)
    for good in ({"status": "failed", "raw": None, "failure": failure}, {"status": "not_run", "message": "가상"}):
        result = copy.deepcopy(base)
        result["part1"]["keywords"] = good
        check_result(result)


def test_part2_takes_only_not_run() -> None:
    base = load("result-sample.json")
    for part2 in (
        {"status": "done", "message": "가상"},
        {"status": "not_run", "message": "가상", "data": None},
        {"status": "not_run"},
        None,
    ):
        rejected_result({**base, "part2": part2})


def test_schema_version_must_be_the_first_key() -> None:
    base = load("result-sample.json")
    moved = {"company": base["company"], **{k: v for k, v in base.items() if k != "company"}}
    with pytest.raises(AssertionError):
        check_result(moved)


def test_the_input_shape_rejects_duplicate_topics_and_what_is_not_the_shape() -> None:
    base = load("input-sample.json")
    broken: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    broken.append({**base, "unknown": 1})
    broken.append({**base, "topics": [*base["topics"], {"topic": "가상토픽 둘", "description": "다른 설명"}]})
    broken.append({**base, "topics": []})
    broken.append({**base, "industries": []})
    broken.append({**base, "userLocation": "kr"})
    broken.append({**base, "userLocation": "KOR"})
    broken.append({**base, "sector": "public"})
    broken.append({**base, "latestEventMode": "false"})
    broken.append({**base, "company": {"name": "가상물류", "담당자": "가상 담당"}})
    broken.append({**base, "industries": [{"standard": "SASB", "industry_name": "가상", "description": "가상"}]})
    row = dict(base["valueChain"][0])
    del row["stakeholder"]
    broken.append({**base, "valueChain": [row]})
    broken.append({**base, "subtopicsByTopic": {"가상토픽 하나": [{"name": "가상"}]}})
    for received in broken:
        rejected_input(received)
    with pytest.raises(ValidationError, match="topic 이 겹친다"):
        shapes.check_input({**base, "topics": [base["topics"][0], base["topics"][0]]})


def test_the_input_shape_takes_null_optional_parts_and_leaves_the_dict_alone() -> None:
    received = load("input-sample.json")
    before = json.dumps(received, ensure_ascii=False)
    assert shapes.check_input(received) is received
    assert json.dumps(received, ensure_ascii=False) == before  # 키 차례·값이 그대로다
    shapes.check_input({**received, "subtopicsByTopic": None, "valueChain": None})
    shapes.check_input({**received, "subtopicsByTopic": {"가상 다른 토픽": []}, "valueChain": []})


def test_the_failure_kinds_are_the_core_kinds() -> None:
    """kind 글자는 계약에 손으로 적는다(계약은 core 를 import 하지 않는다) — core 의 갈래 집합과 견준다."""
    loop_kinds = {
        field.default
        for branch in get_args(ToolLoopFailure.__value__)
        for field in dataclasses.fields(branch)
        if field.name == "kind"
    }
    core_kinds = (set(get_args(LlmResultKind)) - {"success"}) | loop_kinds
    assert set(get_args(shapes.FailureKind)) == core_kinds | {"unparsable"}


def test_the_item_keys_follow_cell_33() -> None:
    """표시 칸 차례는 코랩 셀 33 R/1651·1653 그대로(region 은 보기에만)."""
    assert shapes.REGULATION_ITEM_KEYS == (
        "title",
        "summary",
        "jurisdiction",
        "authority",
        "event_date",
        "publish_date",
        "status",
        "primary_url",
    )
    assert shapes.CONTROVERSY_ITEM_KEYS == ("title", "date", "summary", "severity", "status", "url")


def defs_of(adapters: Any) -> set[str]:
    return {name for adapter in adapters.values() for name in adapter.json_schema().get("$defs", {})}


def test_no_component_name_is_shared_with_the_other_shapes() -> None:
    """openapi 는 이름이 같은 컴포넌트를 하나로 합친다 — 겹치면 남의 꼴을 조용히 덮는다. JsonValue 는 pydantic 의 같은
    정의라 겹쳐도 된다."""
    ours = defs_of(shapes.RESULT_SHAPES) | defs_of(shapes.INPUT_SHAPES)
    theirs: set[str] = set()
    for other in (translation_shapes, greenwash_shapes, dataverify_shapes, inventory_shapes):
        theirs |= defs_of(other.RESULT_SHAPES) | defs_of(getattr(other, "INPUT_SHAPES", {}))
    assert ours & theirs <= {"JsonValue"}
    assert all(name.startswith("Materiality") or name == "JsonValue" for name in ours)
