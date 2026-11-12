"""실행 옵션 꼴 materiality.options@1(contracts/options_shapes.py — 밴드 IR3a §3-1-8): 고정 스키마 파일과 바이트까지
같고, 칸은 input 하나(필수 — 입력 꼴 그대로, 두 번째 정본 0)이며 today·비용·web_search·id 칸이 없다. 입력·결과의 고정
파일은 이 밴드가 바꾸지 않는다(test_shapes.py 가 본다). 순수 층.

고정 파일 뽑기: `uv run python -c "import json; from esgapi.materiality.contracts import options_shapes as o;
print(json.dumps(o.OPTIONS_SHAPES[o.SHAPE].json_schema(), ensure_ascii=False, indent=2))"`
(test_shapes.py 의 PINNED 와 같은 길)
"""

import json
from pathlib import Path

from esgapi.materiality.contracts import options_shapes, shapes

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes" / "options"
ADAPTER = options_shapes.OPTIONS_SHAPES[options_shapes.SHAPE]


def test_the_json_schema_is_pinned_byte_for_byte() -> None:
    pinned = PINNED / "materiality.options@1.schema.json"
    text = json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert pinned.read_bytes() == text.encode("utf-8")


def test_the_pinned_files_are_options_at_1_only() -> None:
    assert sorted(p.name for p in PINNED.iterdir()) == ["materiality.options@1.schema.json"]
    assert options_shapes.SHAPE == "materiality.options@1"


def test_the_options_require_input_only_and_forbid_others() -> None:
    schema = ADAPTER.json_schema()
    assert schema["required"] == ["input"] and list(schema["properties"]) == ["input"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["input"]["$ref"] == "#/$defs/MaterialityInput"


def test_the_input_field_is_the_input_shape_itself() -> None:
    assert options_shapes.MaterialityOptions.__annotations__["input"] is shapes.MaterialityInput
    shape_defs = shapes.INPUT_SHAPES[shapes.INPUT_SHAPE].json_schema()["$defs"]
    assert ADAPTER.json_schema()["$defs"] == shape_defs


def test_no_today_cost_web_search_or_id_field() -> None:
    text = json.dumps(ADAPTER.json_schema()["properties"], ensure_ascii=False)
    for word in ("today", "webSearch", "web_search", "maxCost", "companyId", "documentId", "runId"):
        assert word not in text
    assert set(ADAPTER.json_schema()["$defs"]["MaterialityInput"]["properties"]).isdisjoint(
        {"today", "maxCostUsd", "webSearch"}
    )
