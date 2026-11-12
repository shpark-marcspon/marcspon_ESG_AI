"""실행 옵션 꼴 dataverify.options@1(contracts/options_shapes.py — 밴드 DV1d §3-1-8): 고정 스키마 파일과 바이트까지
같고, 칸은 input(필수 — 입력 꼴 그대로, 두 번째 정본 0)과 source(선택 — DV1f §3-1-1)이며 web_search·비용·id 칸이 없다.
순수 층.
"""

import json
from pathlib import Path

from esgapi.dataverify.contracts import options_shapes, shapes

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes" / "options"
ADAPTER = options_shapes.OPTIONS_SHAPES[options_shapes.SHAPE]


def test_the_json_schema_is_pinned_byte_for_byte() -> None:
    pinned = PINNED / "dataverify.options@1.schema.json"
    text = json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert pinned.read_bytes() == text.encode("utf-8")
    assert {p.name for p in PINNED.iterdir()} == {pinned.name}


def test_the_options_require_input_allow_source_and_forbid_others() -> None:
    schema = ADAPTER.json_schema()
    assert schema["required"] == ["input"] and list(schema["properties"]) == ["input", "source"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["input"]["$ref"] == "#/$defs/DataverifyInput"


def test_the_source_is_a_union_on_kind_of_file_and_paste() -> None:
    schema = ADAPTER.json_schema()
    source = schema["properties"]["source"]
    assert source["discriminator"] == {
        "mapping": {"file": "#/$defs/DataverifyFileSource", "paste": "#/$defs/DataverifyPasteSource"},
        "propertyName": "kind",
    }
    file, paste = schema["$defs"]["DataverifyFileSource"], schema["$defs"]["DataverifyPasteSource"]
    assert (file["required"], file["additionalProperties"]) == (["kind", "name"], False)
    assert (paste["required"], list(paste["properties"]), paste["additionalProperties"]) == (["kind"], ["kind"], False)
    name = file["properties"]["name"]
    assert (name["minLength"], name["maxLength"]) == (1, 255)
    assert name["pattern"] == r"^[^/\\\u0000-\u001f\u007f-\u009f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]+$"


def test_the_input_field_is_the_input_shape_itself() -> None:
    assert options_shapes.DataverifyOptions.__annotations__["input"] is shapes.DataverifyInput
    shape_defs = shapes.INPUT_SHAPES[shapes.INPUT_SHAPE].json_schema()["$defs"]
    option_defs = ADAPTER.json_schema()["$defs"]
    assert {k: v for k, v in option_defs.items() if k in shape_defs} == shape_defs
    assert set(shape_defs) == {"Company", "DataverifyInput", "EdkItem"}
    assert set(option_defs) == {*shape_defs, "DataverifyFileSource", "DataverifyPasteSource"}


def test_the_pinned_files_are_options_at_1_only() -> None:
    assert sorted(p.name for p in PINNED.iterdir()) == ["dataverify.options@1.schema.json"]
    assert options_shapes.SHAPE == "dataverify.options@1"


def test_no_web_search_cost_or_id_field() -> None:
    text = json.dumps(ADAPTER.json_schema(), ensure_ascii=False)
    for word in ("webSearch", "web_search", "maxCost", "companyId", "documentId", "runId"):
        assert word not in text
