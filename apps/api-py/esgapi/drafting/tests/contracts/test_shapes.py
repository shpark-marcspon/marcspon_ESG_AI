"""꼴 drafting.outline@1·drafting.bullets@3(contracts/shapes.py — 밴드 RP1 §3 S1, RP2b B1 — @2 가 @1 을, RP2c B1 — @3
이 @2 를 갈음): 고정
스키마 파일과 바이트까지 같고, 지어낸 예시(tests/data/examples/*.json)가 꼴에 맞으며, 결과 꼴은 모르는 키·빠진 키·
갈래 섞임을 거부하고, 실패 갈래 이름은 core.llm 의 이름과 같다. 순수 층.

예시는 로직보다 먼저 손으로 지은 것이다(기업·글·숫자는 전부 지어낸 것). 프론트가 화면을 짓는 데 쓴다.

고정 파일 뽑기: `uv run python -c "import json; from esgapi.drafting.contracts import shapes as s;
print(json.dumps(s.RESULT_SHAPES[s.RESULT_SHAPE].json_schema(), ensure_ascii=False, indent=2))"`
"""

import copy
import json
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from pydantic import ValidationError

from esgapi.core.llm.types import LlmResultKind
from esgapi.drafting.contracts import shapes, wire

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes"
EXAMPLES = DATA / "examples"
ALL_SHAPES = {**shapes.OUTLINE_SHAPES, **shapes.RESULT_SHAPES}


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def rejected(result: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        shapes.check_result(result)


@pytest.mark.parametrize("shape", sorted(ALL_SHAPES))
def test_the_json_schema_is_pinned_byte_for_byte(shape: str) -> None:
    text = json.dumps(ALL_SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert (PINNED / f"{shape}.schema.json").read_bytes() == text.encode("utf-8")


def test_every_shape_is_pinned_and_nothing_else() -> None:
    assert sorted(p.name for p in PINNED.glob("*.schema.json")) == [
        "drafting.bullets@3.schema.json",
        "drafting.outline@1.schema.json",
    ]


@pytest.mark.parametrize("name", ["result-sample.json", "result-rejected-sample.json"])
def test_the_result_examples_fit_the_shape(name: str) -> None:
    result = load(name)
    assert next(iter(result)) == "schemaVersion"
    shapes.check_result(result)


def test_the_outline_example_fits_the_shape_and_the_tree_rules() -> None:
    shapes.OUTLINE_SHAPES[shapes.OUTLINE_SHAPE].validate_python(load("outline-sample.json"), strict=True)
    assert wire.accept_outline(load("outline-sample.json")) == load("outline-sample.json")  # 이미 정규형


def test_the_result_refuses_an_unknown_key_anywhere() -> None:
    for where in ("top", "leaf", "bullet", "source", "status"):
        result = load("result-sample.json")
        match where:
            case "top":
                result["usage"] = {}
            case "leaf":
                result["leaves"][0]["score"] = 1
            case "bullet":
                result["leaves"][0]["outcome"]["bullets"][0]["confidence"] = 0.9
            case "source":
                result["leaves"][0]["outcome"]["bullets"][0]["sources"][0]["quote"] = "x"
            case _:
                result["status"]["code"] = "over_budget"
        rejected(result)


def test_the_result_refuses_a_missing_key_and_mixed_branches() -> None:
    result = load("result-sample.json")
    del result["mapping"]
    rejected(result)
    mixed = load("result-sample.json")
    mixed["leaves"][2]["outcome"] = {"status": "no_material", "bullets": []}
    rejected(mixed)
    rejected_wrong = load("result-rejected-sample.json")
    rejected_wrong["status"]["stage"] = "after_draft"
    rejected(rejected_wrong)
    bad_page = load("result-sample.json")
    bad_page["leaves"][0]["pages"] = [0]
    rejected(bad_page)
    bad_sha = load("result-sample.json")
    bad_sha["outlineSha256"] = "A" * 64
    rejected(bad_sha)


def test_the_failure_kinds_are_core_names_plus_unparsable() -> None:
    kinds = set(get_args(shapes.FailureKind))
    assert kinds - {"unparsable"} <= set(get_args(LlmResultKind))
    assert "success" not in kinds and "unparsable" in kinds


def test_no_usage_or_cost_field() -> None:
    text = json.dumps(shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].json_schema(), ensure_ascii=False)
    for word in ("costUsd", "usage", "tokens", "inputTokens"):
        assert word not in text


def test_the_warning_codes_are_the_twelve_of_the_order() -> None:
    """RP2b §2-0 ⑧: source_empty_page(쪽 단위 검사)를 걷고 sentence_out_of_range 를 더함 — 열 개. RP2c §2-1:
    base_not_reused·
    source_block_missing 을 더함 — 열둘."""
    assert get_args(shapes.WarningCode) == (
        "page_truncated",
        "material_truncated",
        "mapping_incomplete",
        "unknown_key",
        "page_out_of_batch",
        "source_not_given",
        "sentence_out_of_range",
        "unsupported_bullet",
        "number_not_in_source",
        "bullets_capped",
        "base_not_reused",
        "source_block_missing",
    )


def test_examples_are_not_mutated_by_the_check() -> None:
    result = load("result-sample.json")
    before = copy.deepcopy(result)
    shapes.check_result(result)
    assert result == before


# ── RP2b B1: drafting.bullets@2 — 블록 id·문장 번호(0부터)·상자·basis ──


def first_source(result: dict[str, Any]) -> dict[str, Any]:
    return cast("dict[str, Any]", result["leaves"][0]["outcome"]["bullets"][0]["sources"][0])


def test_b1_only_bullets_at_3_is_a_result_shape() -> None:
    assert set(shapes.RESULT_SHAPES) == {"drafting.bullets@3"} == {shapes.RESULT_SHAPE}
    for version in ("drafting.bullets@1", "drafting.bullets@2"):
        old = load("result-sample.json")
        old["schemaVersion"] = version
        rejected(old)


@pytest.mark.parametrize("missing", ["blockId", "blockBox", "sentence", "page"])
def test_b1_a_source_without_a_field_is_refused(missing: str) -> None:
    result = load("result-sample.json")
    del first_source(result)[missing]
    rejected(result)


def test_b1_the_head_basis_and_the_sentence_index_are_required() -> None:
    no_basis = load("result-sample.json")
    del no_basis["basis"]
    rejected(no_basis)
    no_index = load("result-sample.json")
    del first_source(no_index)["sentence"]["index"]
    rejected(no_index)
    no_pages = load("result-sample.json")
    del no_pages["document"]["pages"]
    rejected(no_pages)
    for where in ("basis", "parser", "sentence", "page size"):
        extra = load("result-sample.json")
        match where:
            case "basis":
                extra["basis"]["sha256"] = "x"
            case "parser":
                extra["basis"]["parser"]["ocr"] = False
            case "sentence":
                first_source(extra)["sentence"]["text"] = "x"
            case _:
                extra["document"]["pages"][0]["rotation"] = 0
        rejected(extra)


def test_b1_null_sentence_and_null_basis_are_taken() -> None:
    result = load("result-sample.json")
    first_source(result)["sentence"] = None
    result["basis"] = None
    shapes.check_result(result)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("index", -1),
        ("boxes", []),
        ("boxes", [[1.0, 2.0, 3.0]]),
        ("boxes", [[1.0, 2.0, 3.0, 4.0, 5.0]]),
    ],
)
def test_b1_a_bad_sentence_is_refused(field: str, value: Any) -> None:
    result = load("result-sample.json")
    first_source(result)["sentence"][field] = value
    rejected(result)


@pytest.mark.parametrize("box", [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0, 5.0], []])
def test_b1_a_block_box_must_have_four_numbers(box: list[float]) -> None:
    result = load("result-sample.json")
    first_source(result)["blockBox"] = box
    rejected(result)


def test_b1_basis_values_are_bounded() -> None:
    for field, value in (("artifactId", 0), ("epoch", 0)):
        result = load("result-sample.json")
        result["basis"][field] = value
        rejected(result)
    layout = load("result-sample.json")
    layout["basis"]["parser"]["layout"] = 3
    rejected(layout)


def test_b1_basis_follows_schema_version_in_the_examples() -> None:
    for name in ("result-sample.json", "result-rejected-sample.json"):
        assert list(load(name))[:3] == ["schemaVersion", "basis", "base"]


# ── RP2c B1: drafting.bullets@3 — base·reusedFrom·basis.pagesSha256 ──


def test_b1_rp2c_the_new_fields_are_required() -> None:
    for where in ("base", "reusedFrom", "pagesSha256", "reason"):
        result = load("result-sample.json")
        match where:
            case "base":
                del result["base"]
            case "reusedFrom":
                del result["leaves"][0]["reusedFrom"]
            case "pagesSha256":
                del result["basis"]["pagesSha256"]
            case _:
                del result["base"]["reason"]
        rejected(result)


def test_b1_rp2c_unknown_fields_in_base_and_origin_are_refused() -> None:
    for where in ("base", "origin"):
        result = load("result-sample.json")
        if where == "base":
            result["base"]["documentId"] = 31
        else:
            result["leaves"][0]["reusedFrom"]["step"] = "draft"
        rejected(result)


def test_b1_rp2c_null_base_origin_and_pages_sha_are_taken() -> None:
    result = load("result-sample.json")
    result["base"] = None
    result["leaves"][0]["reusedFrom"] = None
    result["basis"]["pagesSha256"] = None
    shapes.check_result(result)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pagesSha256", "3f" * 31 + "3"),
        ("pagesSha256", "3F" * 32),
        ("runId", 0),
        ("reason", "other"),
        ("originRunId", 0),
        ("matched", 1),
    ],
)
def test_b1_rp2c_bad_values_are_refused(field: str, value: Any) -> None:
    result = load("result-sample.json")
    match field:
        case "pagesSha256":
            result["basis"]["pagesSha256"] = value
        case "originRunId":
            result["leaves"][0]["reusedFrom"]["runId"] = value
        case _:
            result["base"][field] = value
    rejected(result)


def test_b1_rp2c_reasons_and_matched_pair_as_in_the_flow() -> None:
    """matched true ∧ reason 값은 꼴로 막지 않는다(두 칸) — 흐름이 늘 reason is None 으로 matched 를 짓는다(reuse 시험이
    잰다). 꼴은 까닭 넷만 받는다."""
    result = load("result-sample.json")
    for reason in ("document", "versions", "settings", "base_rejected"):
        result["base"] = {"runId": 58, "outlineId": 11, "matched": False, "reason": reason}
        shapes.check_result(result)
