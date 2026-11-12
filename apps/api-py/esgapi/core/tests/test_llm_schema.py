"""구조화 출력의 스키마를 공급사가 받는 꼴로 다듬기. 순수 층. (esg-lab 에는 없던 것: zod 가 하던 일을 Pydantic 에서
한다)
"""

from typing import Any, cast

import pytest
from openai.lib._pydantic import to_strict_json_schema as sdk_strict
from pydantic import BaseModel, Field, TypeAdapter

from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.schema import strip_unsupported_schema_keys, to_strict_json_schema
from esgapi.core.llm.types import JsonSchemaSpec, ProviderRequest, TextPart


class Item(BaseModel):
    name: str = Field(min_length=1, max_length=60, description="품목 이름")
    amount: float | None = None
    tags: list[str] = Field(default_factory=list[str], max_length=8)


class Table(BaseModel):
    title: str
    first: Item = Field(description="첫 줄")
    rows: list[Item]
    note: str = "없음"


class Node(BaseModel):
    label: str
    children: list["Node"] = Field(default_factory=list["Node"])


def objects(node: object) -> list[dict[str, Any]]:
    """스키마 안의 객체 스키마(type: object)를 전부 모은다."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        mapping = cast("dict[str, Any]", node)
        if mapping.get("type") == "object":
            found.append(mapping)
        for value in mapping.values():
            found.extend(objects(value))
    elif isinstance(node, list):
        for item in cast("list[object]", node):
            found.extend(objects(item))
    return found


def test_every_object_is_closed_and_every_property_is_required() -> None:
    raw = Table.model_json_schema()
    strict = to_strict_json_schema(raw)
    found = objects(strict)
    # Table 자신, $defs 의 Item, 그리고 `first` 자리에 풀어 쓴 Item — 셋이다. 하나도 못 찾고 통과하는 일을 막는다.
    assert len(found) == 3
    for schema in found:
        assert schema["additionalProperties"] is False
        assert schema["required"] == list(schema["properties"])
    # Pydantic 이 낸 원래 스키마에는 둘 다 없었다(그래서 이 함수가 필요하다).
    assert "additionalProperties" not in raw
    assert raw["required"] == ["title", "first", "rows"]
    assert cast("dict[str, Any]", strict)["required"] == ["title", "first", "rows", "note"]


def test_optional_stays_any_of_null_and_only_none_defaults_are_dropped() -> None:
    strict = cast("dict[str, Any]", to_strict_json_schema(Table.model_json_schema()))
    amount = strict["$defs"]["Item"]["properties"]["amount"]
    assert amount["anyOf"] == [{"type": "number"}, {"type": "null"}]
    assert "default" not in amount
    assert strict["properties"]["note"]["default"] == "없음"


def test_ref_with_siblings_is_unravelled_and_plain_refs_and_defs_are_kept() -> None:
    strict = cast("dict[str, Any]", to_strict_json_schema(Table.model_json_schema()))
    first = strict["properties"]["first"]
    # `$ref` 곁에 description 이 있으면 strict 가 받지 않는다. 가리키는 정의로 풀어 쓴다(곁의 열쇠가 앞선다).
    assert "$ref" not in first
    assert (first["type"], first["description"], first["additionalProperties"]) == ("object", "첫 줄", False)
    assert strict["properties"]["rows"]["items"] == {"$ref": "#/$defs/Item"}
    assert "Item" in strict["$defs"]


def test_self_referencing_model_keeps_its_ref() -> None:
    strict = cast("dict[str, Any]", to_strict_json_schema(Node.model_json_schema()))
    node = strict["$defs"]["Node"]
    assert node["additionalProperties"] is False
    assert node["required"] == ["label", "children"]
    assert node["properties"]["children"]["items"] == {"$ref": "#/$defs/Node"}


def test_an_explicit_additional_properties_is_left_alone_and_the_input_is_not_changed() -> None:
    raw = TypeAdapter(dict[str, int]).json_schema()
    before = dict(raw)
    assert to_strict_json_schema(raw)["additionalProperties"] == {"type": "integer"}
    assert raw == before
    table = Table.model_json_schema()
    to_strict_json_schema(table)
    assert "additionalProperties" not in table


@pytest.mark.parametrize("model", [Table, Node, Item])
def test_result_equals_what_the_openai_sdk_helper_makes(model: type[BaseModel]) -> None:
    """규칙의 근거가 openai SDK 의 도우미다. 설치된 SDK 가 같은 모델에서 내는 것과 같아야 한다(SDK 를 올리면 여기서
    드러난다).
    """
    assert to_strict_json_schema(model.model_json_schema()) == sdk_strict(model)


def test_anthropic_request_drops_the_constraints_it_rejects_and_keeps_field_names() -> None:
    strict = to_strict_json_schema(Table.model_json_schema())
    request = ProviderRequest(
        api_model_id="m",
        system=(),
        user=(TextPart(text="q"),),
        max_output_tokens=10,
        json_schema=JsonSchemaSpec(name="table", schema=strict),
    )
    body = cast("dict[str, Any]", AnthropicProvider().build_request(request))
    sent = body["output_config"]["format"]["schema"]
    name = sent["$defs"]["Item"]["properties"]["name"]
    assert name == {"description": "품목 이름", "title": "Name", "type": "string"}
    assert "maxItems" not in sent["$defs"]["Item"]["properties"]["tags"]
    assert sent == strip_unsupported_schema_keys(strict)
    # 원래 스키마에는 제약이 있었다(지울 것이 없어 통과한 것이 아니다).
    original = cast("dict[str, Any]", strict)["$defs"]["Item"]["properties"]
    assert (original["name"]["minLength"], original["name"]["maxLength"], original["tags"]["maxItems"]) == (1, 60, 8)
