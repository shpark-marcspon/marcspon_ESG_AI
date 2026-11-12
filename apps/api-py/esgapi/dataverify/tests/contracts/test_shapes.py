"""꼴 dataverify.input@1·dataverify.result@2(contracts/shapes.py): 고정 스키마 파일과 글자까지 같고, 지은 예시가 결과
꼴에 맞으며, 결과 꼴은 모르는 키·빠진 키·갈래 섞임을 거부하고, 입력 꼴은 항목의 모르는 키를 받고 받은 dict 를
고치지 않는다(발주서 §3 S8). @2(DV1e §3-1-1·5): failure.kind 는 core.llm 의 갈래 이름(call_failed 없음)·budgetSource·
insight.partialText, openapi 에 겹치는 컴포넌트 이름 없음.

예시(tests/data/examples/result-sample.json)는 로직보다 먼저 손으로 지은 것이다(기업·항목·수는 전부 지어낸 것).
프론트가 화면을 짓는 데 쓴다.
"""

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from pydantic import ValidationError

from esgapi.core.llm.types import LlmResultKind, ToolLoopFailure
from esgapi.dataverify.contracts import shapes
from esgapi.greenwash.contracts import shapes as greenwash_shapes
from esgapi.translation.contracts import shapes as translation_shapes

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes"
EXAMPLE = DATA / "examples" / "result-sample.json"
ALL_SHAPES = {**shapes.INPUT_SHAPES, **shapes.RESULT_SHAPES}


def pinned_text(shape: str) -> str:
    return json.dumps(ALL_SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"


def load_example() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLE.read_text(encoding="utf-8")))


def check_result(result: dict[str, Any]) -> None:
    assert next(iter(result)) == "schemaVersion"
    shapes.RESULT_SHAPES[result["schemaVersion"]].validate_python(result, strict=True)


def edk_item(**extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ID": "E-001",
        "테마": "환경",
        "항목": "기후변화",
        "대분류": "온실가스 배출량",
        "중분류": "직접 배출량",
        "소분류": "Scope 1",
        "입력 방식": "직접 입력",
        "단위": "tCO2eq",
        "values": {"2022": "1,200", "2023": 1300, "2024": None, "2025": " 12 "},
        "핵심데이터": "Y",
        "메모": "",
    }
    item.update(extra)
    return item


def an_input() -> dict[str, Any]:
    return {
        "schemaVersion": "dataverify.input@1",
        "company": {
            "name": "가상건설",
            "sasbIndustry": "Engineering & Construction Services",
            "materialTopics": ["기후변화 대응", "안전보건"],
            "reportingYear": "2025",
        },
        "data": {"환경": [edk_item(), edk_item(ID=2, 담당자="가상 담당")], "사회": [edk_item(테마="사회")]},
    }


@pytest.mark.parametrize("shape", sorted(ALL_SHAPES))
def test_the_json_schema_is_pinned(shape: str) -> None:
    assert pinned_text(shape) == (PINNED / f"{shape}.schema.json").read_text(encoding="utf-8")


def test_every_shape_is_pinned() -> None:
    files = {p.name.removesuffix(".schema.json") for p in PINNED.glob("*.schema.json")}
    # 둘째 결과 dataverify.digest@1 의 고정 파일은 tests/contracts/test_digest_shapes.py 가 견준다(DV1g)
    assert set(ALL_SHAPES) == files - {"dataverify.digest@1"} == {"dataverify.input@1", "dataverify.result@2"}


def test_the_example_fits_the_result_shape() -> None:
    result = load_example()
    check_result(result)
    kinds = {check["kind"] for check in result["review"]["checks"]}
    assert kinds == {"value", "check", "search", "error"}  # 프론트가 갈래 넷을 다 본다
    notes = {
        year["note"] for check in result["review"]["checks"] if check["kind"] == "check" for year in check["years"]
    }
    assert notes == {None, "non-numeric", "division by zero"}
    assert any(check["kind"] == "value" and check["na"] for check in result["review"]["checks"])
    seqs = [check["seq"] for check in result["review"]["checks"]]
    assert seqs == list(range(1, len(seqs) + 1))


def test_a_missing_or_extra_key_is_rejected_by_the_result_shape() -> None:
    base = load_example()
    broken: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    broken.append({**base, "unknown": 1})
    broken.append({**base, "usage": {"calls": 3}})  # 사용량은 싣지 않는다
    broken.append({**base, "schemaVersion": "dataverify.result@1"})
    nested = copy.deepcopy(base)
    nested["review"]["checks"][0]["extra"] = 1
    broken.append(nested)
    item_extra = copy.deepcopy(base)
    item_extra["company"]["담당자"] = "가상 담당"
    broken.append(item_extra)
    no_na = copy.deepcopy(base)
    del no_na["review"]["checks"][1]["na"]
    broken.append(no_na)
    short_quad = copy.deepcopy(base)
    short_quad["review"]["checks"][1]["item"] = ["온실가스 배출량", "직접 배출량", "Scope 1"]
    broken.append(short_quad)
    number_value = copy.deepcopy(base)
    number_value["review"]["checks"][1]["value"] = 1300.0  # 수는 글자로
    broken.append(number_value)
    bad_note = copy.deepcopy(base)
    bad_note["review"]["checks"][3]["years"][0]["note"] = "skip"
    broken.append(bad_note)
    bad_kind = copy.deepcopy(base)
    bad_kind["review"]["checks"][0]["kind"] = "note"
    broken.append(bad_kind)
    seq_zero = copy.deepcopy(base)
    seq_zero["review"]["checks"][0]["seq"] = 0
    broken.append(seq_zero)
    bad_year = copy.deepcopy(base)
    bad_year["company"]["reportingYear"] = "25"
    broken.append(bad_year)
    for result in broken:
        with pytest.raises(ValidationError):
            shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)


def test_a_stage_cannot_mix_its_branches() -> None:
    base = load_example()
    failure: dict[str, Any] = {"kind": "provider_error", "budgetSource": None, "message": "가상 오류"}
    mixed: list[dict[str, Any]] = [
        {**base, "plan": {**base["plan"], "failure": failure}},  # done 에 failure
        {**base, "plan": {**base["plan"], "status": "failed"}},  # failed 에 partial·failure 없음
        {**base, "plan": {**base["plan"], "status": "not_run", "partial": None, "failure": None}},  # not_run 에 산식
        {**base, "review": {**base["review"], "status": "not_run", "partial": None, "report": None}},  # not_run 에 기록
        {**base, "review": {**base["review"], "partial": None}},  # done 에 partial null
        {**base, "insight": {**base["insight"], "status": "failed", "partial": None, "report": None}},  # failed 에 행
        {**base, "insight": {**base["insight"], "failure": failure}},  # done 에 failure
        {**base, "insight": {k: v for k, v in base["insight"].items() if k != "failure"}},  # failure 칸 없음
        {**base, "plan": {**base["plan"], "status": "skipped"}},
    ]
    for result in mixed:
        with pytest.raises(ValidationError):
            shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)
    not_run_plan: dict[str, Any] = {"status": "not_run", "partial": None, "formulas": [], "raw": None, "failure": None}
    failed_review: dict[str, Any] = {
        "status": "failed",
        "partial": None,
        "report": None,
        "checks": [],
        "failure": failure,
    }
    not_run_insight: dict[str, Any] = {
        "status": "not_run",
        "partial": None,
        "report": None,
        "rows": [],
        "rowsParsed": "none",
        "sources": [],
        "failure": None,
    }
    check_result({**base, "plan": not_run_plan, "review": failed_review, "insight": not_run_insight})
    failed_insight = {**not_run_insight, "status": "failed", "failure": failure, "partialText": None}
    check_result({**base, "insight": failed_insight})
    with pytest.raises(ValidationError):  # failed 에 failure 가 없음
        shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(
            {**base, "insight": {**failed_insight, "failure": None}}, strict=True
        )


def test_schema_version_must_be_the_first_key() -> None:
    base = load_example()
    moved = {"company": base["company"], **{k: v for k, v in base.items() if k != "company"}}
    with pytest.raises(AssertionError):
        check_result(moved)


def test_the_input_shape_accepts_unknown_item_keys_and_leaves_the_dict_alone() -> None:
    received = an_input()
    before = json.dumps(received, ensure_ascii=False)
    shapes.INPUT_SHAPES[shapes.INPUT_SHAPE].validate_python(received, strict=True)
    assert json.dumps(received, ensure_ascii=False) == before  # 키 차례·값의 타입이 그대로다
    assert received["data"]["환경"][1]["담당자"] == "가상 담당"
    assert received["data"]["환경"][0]["values"]["2022"] == "1,200"


def test_the_input_shape_accepts_data_without_the_target_theme() -> None:
    received = an_input()
    received["data"] = {"사회": [edk_item(테마="사회")]}
    shapes.INPUT_SHAPES[shapes.INPUT_SHAPE].validate_python(received, strict=True)
    received["data"] = {}
    shapes.INPUT_SHAPES[shapes.INPUT_SHAPE].validate_python(received, strict=True)


def test_the_input_shape_rejects_what_is_not_the_shape() -> None:
    base = an_input()
    broken: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    broken.append({**base, "themes": ["환경"]})  # 테마 칸은 없다(처분 ⑥)
    broken.append({**base, "company": {**base["company"], "담당자": "가상 담당"}})
    for key in shapes.EdkItem.__annotations__:
        missing = copy.deepcopy(base)
        del missing["data"]["환경"][0][key]
        broken.append(missing)
    nested_value = copy.deepcopy(base)
    nested_value["data"]["환경"][0]["values"]["2022"] = {"value": 1}
    broken.append(nested_value)
    a_bool = copy.deepcopy(base)
    a_bool["data"]["환경"][0]["values"]["2022"] = True
    broken.append(a_bool)
    not_a_list = copy.deepcopy(base)
    not_a_list["data"]["환경"] = edk_item()
    broken.append(not_a_list)
    for received in broken:
        with pytest.raises(ValidationError):
            shapes.INPUT_SHAPES[shapes.INPUT_SHAPE].validate_python(received, strict=True)


def test_check_input_returns_the_received_dict_itself() -> None:
    received = an_input()
    before = copy.deepcopy(received)
    assert shapes.check_input(received) is received
    assert received == before
    assert json.dumps(received, ensure_ascii=False) == json.dumps(before, ensure_ascii=False)
    with pytest.raises(ValidationError):
        shapes.check_input({**received, "themes": ["환경"]})


def test_fields_that_echo_the_model_take_any_json_value() -> None:
    """모델 인자를 비추는 칸(item·year·byName·raw·filter·limit·offset·args)은 받은 그대로다(가지 리뷰 1). 도구가 낸 값의
    칸(value·diff·tolerance·status·note·total·returned)은 그대로 좁다."""
    base = load_example()
    checks = base["review"]["checks"]
    wide = copy.deepcopy(base)
    wide["review"]["checks"][1]["item"] = [5, True, None, ["가"]]
    wide["review"]["checks"][1]["year"] = 2023.0
    wide["review"]["checks"][0]["filter"] = {"대분류": 5}
    wide["review"]["checks"][0]["limit"] = -1
    wide["review"]["checks"][3]["items"]["byName"]["total"] = [1, 2, 3, 4]
    wide["review"]["checks"][3]["years"][0]["year"] = {"y": 1}
    wide["review"]["checks"][7]["args"] = [1, 2]
    check_result(wide)
    narrow: list[tuple[int, str, Any]] = [
        (1, "value", 1300.0),
        (0, "total", -1),
        (0, "returned", "6"),
        (3, "tolerance", 1.1),
    ]
    for at, key, value in narrow:
        broken = copy.deepcopy(base)
        broken["review"]["checks"][at][key] = value
        with pytest.raises(ValidationError):
            check_result(broken)
    assert checks[1]["kind"] == "value"


def failed_insight(**failure: Any) -> dict[str, Any]:
    base = load_example()
    given: dict[str, Any] = {"kind": "truncated", "budgetSource": None, "message": "truncated", **failure}
    insight: dict[str, Any] = {
        "status": "failed",
        "partial": None,
        "report": None,
        "rows": [],
        "rowsParsed": "none",
        "sources": [],
        "failure": given,
        "partialText": "가상 부분 원문",
    }
    return {**base, "insight": insight}


def test_the_failure_kinds_are_the_core_kinds_and_call_failed_is_gone() -> None:
    """kind 글자는 계약에 손으로 적는다(계약은 core 를 import 하지 않는다) — core 의 갈래 집합과 견준다(★G)."""
    loop_kinds = {
        field.default
        for branch in get_args(ToolLoopFailure.__value__)
        for field in dataclasses.fields(branch)
        if field.name == "kind"
    }
    core_kinds = (set(get_args(LlmResultKind)) - {"success"}) | loop_kinds
    assert set(shapes.FailureKind.__args__) == core_kinds | {"unparsable"}
    check_result(failed_insight())
    for broken in (
        failed_insight(kind="call_failed"),
        failed_insight(budgetSource="loop", kind="unknown"),
        {k: v for k, v in failed_insight().items() if k != "insight"},
    ):
        with pytest.raises(ValidationError):
            check_result(broken)
    no_source = failed_insight()
    del no_source["insight"]["failure"]["budgetSource"]
    with pytest.raises(ValidationError):  # budgetSource 칸은 늘 있다(null 이라도)
        check_result(no_source)
    with pytest.raises(ValidationError):
        check_result(failed_insight(budgetSource="elsewhere"))


def test_partial_text_is_only_on_a_failed_insight() -> None:
    no_partial = failed_insight()
    del no_partial["insight"]["partialText"]
    with pytest.raises(ValidationError):  # failed 인사이트에 partialText 칸이 없으면 거절
        check_result(no_partial)
    base = load_example()
    for stage in ("plan", "review", "insight"):  # done 갈래에는 그 칸이 없다
        with pytest.raises(ValidationError):
            check_result({**base, stage: {**base[stage], "partialText": None}})


def defs_of(adapters: Any) -> set[str]:
    return {name for adapter in adapters.values() for name in adapter.json_schema().get("$defs", {})}


def test_no_component_name_is_shared_with_the_other_result_shapes() -> None:
    """openapi 는 이름이 같은 컴포넌트를 하나로 합친다 — 겹치면 남의 꼴을 조용히 덮는다(DV1e §3-1-5). JsonValue 는
    pydantic 의 같은 정의라 겹쳐도 된다."""
    ours = defs_of(shapes.RESULT_SHAPES)
    theirs = defs_of(translation_shapes.RESULT_SHAPES) | defs_of(greenwash_shapes.RESULT_SHAPES)
    assert ours & theirs <= {"JsonValue"}
    assert {"DataverifySettings", "DataverifyWarning", "DataverifyReviewDone"} <= ours
