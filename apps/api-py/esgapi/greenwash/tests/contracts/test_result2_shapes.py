"""결과 꼴 greenwash.result@2(contracts/result2_shapes.py — 밴드 GE1 T1·T4): 고정 스키마 파일과 바이트가 같고, 지은
예시 셋이 꼴과 꼴 밖 규칙에 맞으며, 모르는 키·근거 갈래 어김·블록 수·블록 범위 수와 꼴·글자 상한·실패 셈 어김을
거절한다.

예시(tests/data/contract-examples/result2/)는 지어낸 글이다. 고정 파일·예시는 하위 폴더 result2/ 에 둔다 — 뿌리의
result@1 집합 단언(test_shapes.py)에 걸리지 않게.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from esgapi.core.flows.types import segment_key_of, segment_key_sha256
from esgapi.greenwash.contracts import result2_shapes as r2

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes" / "result2"
EXAMPLES = DATA / "contract-examples" / "result2"
EXAMPLE_NAMES = ["result2-empty.json", "result2-failed.json", "result2-normal.json"]


def pinned_text() -> str:
    return json.dumps(r2.RESULT2.json_schema(), ensure_ascii=False, indent=2) + "\n"


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def first_item(result: dict[str, Any]) -> dict[str, Any]:
    return cast("dict[str, Any]", result["segments"][0]["items"][0])


# ── T1 꼴 ──────────────────────────────────────────────────────────────


def test_the_json_schema_is_pinned_byte_for_byte() -> None:
    pinned = PINNED / f"{r2.SHAPE}.schema.json"
    assert pinned.read_bytes() == pinned_text().encode("utf-8")
    assert {p.name for p in PINNED.iterdir()} == {pinned.name}


def test_the_examples_fit_and_start_with_schema_version() -> None:
    assert sorted(p.name for p in EXAMPLES.iterdir()) == EXAMPLE_NAMES
    for name in EXAMPLE_NAMES:
        value = load(name)
        assert next(iter(value)) == "schemaVersion"
        r2.check_result(value)
        for seg in value["segments"]:  # 구획 keySha256 = core 의 열쇠 sha(펼침 data 값 — GE1b ① 검증 1 B1)
            assert seg["keySha256"] == segment_key_sha256(segment_key_of(seg["key"])), (name, seg["key"]["span"])


def test_the_first_key_must_be_schema_version() -> None:
    value = load("result2-empty.json")
    moved = {k: value[k] for k in ("source", "schemaVersion", "failures", "segments")}
    with pytest.raises(r2.Result2Invalid):
        r2.check_result(moved)


@pytest.mark.parametrize(
    "where",
    ["top", "source", "segment", "item", "target", "verdict", "evidence", "checks", "module", "unplaced"],
)
def test_unknown_keys_are_rejected(where: str) -> None:
    value = load("result2-normal.json")
    seg = value["segments"][0]
    item = seg["items"][0]
    spot = {
        "top": value,
        "source": value["source"],
        "segment": seg,
        "item": item,
        "target": item["target"],
        "verdict": item["verdict"],
        "evidence": item["evidence"][0],
        "checks": item["checks"],
        "module": item["module"],
        "unplaced": seg["unplaced"][0],
    }[where]
    spot["extra"] = 1
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(value, strict=True)


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "document", "passageId": "P1", "page": 1},
        {"kind": "document", "passageId": "P1", "blockRanges": [["b1", "b1"]], "page": 1, "text": "글은 싣지 않는다"},
        {"kind": "document", "passageId": "P1", "blockIds": ["b1"], "page": 1},
        {"kind": "document", "passageId": "P1", "blockRanges": [["b1"]], "page": 1},
        {"kind": "document", "passageId": "P1", "blockRanges": [["b1", "b2", "b3"]], "page": 1},
        {"kind": "document", "passageId": "P1", "blockRanges": [["b1", ""]], "page": 1},
        {"kind": "document", "passageId": "P" * 17, "blockRanges": [["b1", "b1"]], "page": 1},
        {"kind": "criteria", "lineId": "l" * 25},
        {"kind": "criteria", "lineId": "high-1", "page": 1},
        {"kind": "human", "text": "사람 근거"},
        {"kind": "web", "url": "https://example.invalid"},
        {"kind": "document", "passageId": "P1", "blockRanges": [["b1", "b1"]], "page": 1, "span": [3]},
    ],
)
def test_evidence_branches_are_discriminated(bad: dict[str, Any]) -> None:
    value = load("result2-normal.json")
    first_item(value)["evidence"] = [bad]
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(value, strict=True)


@pytest.mark.parametrize("n", [0, 3])
def test_target_has_one_or_two_blocks(n: int) -> None:
    value = load("result2-normal.json")
    first_item(value)["target"]["blockIds"] = [f"b{i}" for i in range(n)]
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(value, strict=True)


def test_not_risky_is_an_item_and_failed_items_may_lack_a_verdict() -> None:
    normal = load("result2-normal.json")
    assert {i["verdict"]["level"] for i in normal["segments"][0]["items"]} >= {"None"}
    failed = load("result2-failed.json")
    assert first_item(failed)["verdict"] is None
    done = copy.deepcopy(normal)
    first_item(done)["verdict"] = None
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(done, strict=True)


def test_status_and_error_code_go_together() -> None:
    value = load("result2-normal.json")
    first_item(value)["errorCode"] = "quote_not_found"
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(value, strict=True)
    value = load("result2-failed.json")
    first_item(value)["errorCode"] = "made_up_code"
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(value, strict=True)


# ── T4 실패 셈·상한 ────────────────────────────────────────────────────


def test_failures_are_recounted_from_status() -> None:
    value = load("result2-failed.json")
    assert r2.count_failures(value["segments"]) == {"segments": 1, "items": 2}
    for wrong in ({"segments": 0, "items": 0}, {"segments": 1, "items": 1}, {"segments": 2, "items": 2}):
        bad = copy.deepcopy(value)
        bad["failures"] = wrong
        with pytest.raises(r2.Result2Invalid):
            r2.check_result(bad)


def test_failed_segment_has_no_items_and_keeps_its_code() -> None:
    value = load("result2-failed.json")
    value["segments"][1]["errorCode"] = None
    with pytest.raises(r2.Result2Invalid):
        r2.check_result(value)
    value = load("result2-failed.json")
    value["segments"][1]["items"] = copy.deepcopy(value["segments"][0]["items"][:1])
    value["failures"] = r2.count_failures(value["segments"])
    with pytest.raises(r2.Result2Invalid):
        r2.check_result(value)


def test_a_done_segment_has_no_error_code() -> None:
    value = load("result2-normal.json")
    value["segments"][0]["errorCode"] = "x"
    with pytest.raises(r2.Result2Invalid):
        r2.check_result(value)


def test_keys_do_not_repeat_inside_a_segment_and_spans_do_not_repeat() -> None:
    value = load("result2-normal.json")
    value["segments"][0]["items"][1]["key"] = value["segments"][0]["items"][0]["key"]
    with pytest.raises(r2.Result2Invalid):
        r2.check_result(value)
    value = load("result2-normal.json")
    value["segments"].append(copy.deepcopy(value["segments"][0]))
    with pytest.raises(r2.Result2Invalid):
        r2.check_result(value)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("target", "text"), "가" * (r2.TARGET_TEXT_MAX + 1)),
        (("reason",), "나" * (r2.REASON_MAX + 1)),
        (("module", "confirmed"), ["다"] * (r2.NOTE_LINES_MAX + 1)),
        (("module", "missing"), ["라" * (r2.NOTE_LINE_MAX + 1)]),
        (("module", "criteriaLines"), ["high-1"] * (r2.CRITERIA_LINES_MAX + 1)),
        (("evidence",), [{"kind": "criteria", "lineId": "high-1"}] * (r2.EVIDENCE_MAX + 1)),
        (("stableKey",), "f" * 31),
    ],
)
def test_over_the_limit_is_rejected(path: tuple[str, ...], value: object) -> None:
    result = load("result2-normal.json")
    spot = first_item(result)
    for name in path[:-1]:
        spot = spot[name]
    spot[path[-1]] = value
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(result, strict=True)


def test_evidence_ranges_are_capped_at_eight() -> None:
    result = load("result2-normal.json")
    over = [[f"b{i}", f"b{i}"] for i in range(r2.EVIDENCE_RANGES_MAX + 1)]
    first_item(result)["evidence"][0]["blockRanges"] = over
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(result, strict=True)
    first_item(result)["evidence"][0]["blockRanges"] = over[: r2.EVIDENCE_RANGES_MAX]
    first_item(result)["checks"]["truncated"] = ["evidence.blockRanges"]
    r2.check_result(result)


@pytest.mark.parametrize(
    "ranges",
    [
        [["b1", "b2"], ["b2", "b3"]],
        [["b1", "b1"], ["b1", "b1"]],
        [["b1", "b3"], ["b5", "b1"]],
    ],
)
def test_evidence_range_ends_do_not_repeat(ranges: list[list[str]]) -> None:
    result = load("result2-normal.json")
    first_item(result)["evidence"][0]["blockRanges"] = ranges
    r2.RESULT2.validate_python(result, strict=True)
    with pytest.raises(r2.Result2Invalid):
        r2.check_result(result)


@pytest.mark.parametrize("ranges", [[["b1", "b2"]], [["b1", "b1"], ["b3", "b3"]]])
def test_span_goes_with_one_single_block_range(ranges: list[list[str]]) -> None:
    result = load("result2-normal.json")
    evidence = [e for seg in result["segments"] for i in seg["items"] for e in i["evidence"]]
    spanned = next(e for e in evidence if e["kind"] == "document" and "span" in e)
    assert spanned["blockRanges"] == [[spanned["blockRanges"][0][0]] * 2]
    spanned["blockRanges"] = ranges
    r2.RESULT2.validate_python(result, strict=True)
    with pytest.raises(r2.Result2Invalid):
        r2.check_result(result)


# ── ④ 에서 더한 꼴 밖 규칙(검증 1 R2·R3, 감독 답 ⓒ ②) ──


def test_a_done_item_with_a_failed_check_is_refused() -> None:
    value = load("result2-normal.json")
    first_item(value)["checks"]["levelRule"] = "fail"
    with pytest.raises(r2.Result2Invalid, match="done 항목에 fail"):
        r2.check_result(value)


def test_a_check_error_code_needs_that_check_to_fail() -> None:
    value = load("result2-failed.json")
    item = next(i for i in value["segments"][0]["items"] if i["errorCode"] in r2.CHECK_OF_CODE)
    item["checks"][r2.CHECK_OF_CODE[item["errorCode"]]] = "pass"
    with pytest.raises(r2.Result2Invalid, match="fail 이 아니다"):
        r2.check_result(value)


def test_a_stable_key_does_not_repeat_across_segments() -> None:
    value = load("result2-normal.json")
    other = copy.deepcopy(value["segments"][0])
    other["key"]["span"] = "c9-9"
    other["items"] = other["items"][:1]
    value["segments"].append(other)
    with pytest.raises(r2.Result2Invalid, match="stableKey 가 결과 안에서 겹친다"):
        r2.check_result(value)


def test_budget_trimmed_is_recounted() -> None:
    value = load("result2-normal.json")
    value["budgetTrimmed"] = 1
    with pytest.raises(r2.Result2Invalid, match="budgetTrimmed"):
        r2.check_result(value)
    first_item(value)["checks"]["truncated"] = ["budget"]
    r2.check_result(value)


def test_ids_are_capped_at_sixteen_and_line_ids_at_twenty_four() -> None:
    assert (r2.ID_MAX, r2.LINE_ID_MAX) == (16, 24)
    value = load("result2-normal.json")
    first_item(value)["key"] = "k" * 17
    with pytest.raises(ValidationError):
        r2.RESULT2.validate_python(value, strict=True)
