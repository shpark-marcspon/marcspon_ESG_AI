"""실행 옵션 꼴 drafting.options@2(contracts/options_shapes.py — 밴드 RP1 §3 S1, RP2c B2 — @2 가 @1 을 갈음): 고정
스키마
파일과 바이트까지 같고, 칸은 projectId(정수 ≥ 1)와 선택 base{runId, rebuild} 이며 목차·문서·비용 칸이 없다. @1 의 몸
{projectId} 는 그대로 지난다. 순수 층."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from esgapi.drafting.contracts import options_shapes

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes" / "options"
ADAPTER = options_shapes.OPTIONS_SHAPES[options_shapes.SHAPE]


def test_the_json_schema_is_pinned_byte_for_byte() -> None:
    text = json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert (PINNED / "drafting.options@2.schema.json").read_bytes() == text.encode("utf-8")
    assert sorted(p.name for p in PINNED.iterdir()) == ["drafting.options@2.schema.json"]


def test_the_options_are_project_id_and_an_optional_base() -> None:
    schema = ADAPTER.json_schema()
    assert schema["required"] == ["projectId"] and list(schema["properties"]) == ["projectId", "base"]
    assert schema["additionalProperties"] is False
    base = schema["$defs"]["DraftingOptionsBase"]
    assert base["required"] == ["runId", "rebuild"] and base["additionalProperties"] is False
    assert base["properties"]["rebuild"]["maxItems"] == 150
    ADAPTER.validate_python({"projectId": 7}, strict=True)
    ADAPTER.validate_python({"projectId": 7, "base": {"runId": 1, "rebuild": []}}, strict=True)


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"projectId": 0},
        {"projectId": "7"},
        {"projectId": True},
        {"projectId": 7, "outlineId": 1},
        {"projectId": 7.0},
        {"projectId": 7, "base": {"runId": 1}},
        {"projectId": 7, "base": {"runId": 0, "rebuild": []}},
        {"projectId": 7, "base": {"runId": True, "rebuild": []}},
        {"projectId": 7, "base": {"runId": 1, "rebuild": ["Bad Key"]}},
        {"projectId": 7, "base": {"runId": 1, "rebuild": [f"k{n}" for n in range(151)]}},
        {"projectId": 7, "base": {"runId": 1, "rebuild": [], "x": 1}},
    ],
)
def test_the_options_refuse(options: object) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(options, strict=True)


def test_the_options_example_fits_the_shape() -> None:
    ADAPTER.validate_python(
        json.loads((DATA / "examples" / "options-sample.json").read_text(encoding="utf-8")), strict=True
    )
