"""구조화 출력의 스키마를 공급사가 받는 꼴로 다듬는다.

스키마는 Pydantic 이 낸 JSON Schema(`TypeAdapter(...).json_schema()`)다. esg-lab 은 zod 가 처음부터 닫힌 객체를 냈지만
Pydantic 은 `additionalProperties` 를 적지 않고, 기본값이 있는 칸을 `required` 에서 뺀다. OpenAI 의 strict 모드에 맞추는
규칙은 **openai 파이썬 SDK 3.26.0 의 `openai/lib/_pydantic.py: _ensure_strict_json_schema` 가 하는 일**을 읽고 그대로
옮겼다(2026-10-08 에 설치된 패키지의 소스를 읽음. 공식 문서를 다시 열지는 않았다):

    1. `type: object` 인데 `additionalProperties` 가 없으면 false 를 넣는다(이미 적혀 있으면 그대로 둔다)
    2. `properties` 가 있으면 그 칸 전부를 `required` 로 한다
    3. 값이 None 인 `default` 는 지운다
    4. `allOf` 가 하나뿐이면 풀어 넣는다
    5. `$ref` 곁에 다른 열쇠(description 등)가 있으면 `$ref` 를 가리키는 정의로 풀어 쓴다
    `$defs`·`$ref` 자체는 남긴다. 내려가는 자리는 `$defs`·`definitions`·`properties`·`items`·`anyOf`·`allOf` 다.

★ 무효 조건: 실제 공급사에 보내 본 적이 없다. 공급사가 이 꼴을 거부하면(400) 이 파일을 고친다. `Optional[X]` 는
  `anyOf: [X, {"type": "null"}]` 로 나가고, 기본값이 있어 required 에서 빠졌던 칸은 required 가 된다(모델은 그 칸을
  늘 채운다).
  값의 검증은 호출 층이 Pydantic 으로 다시 하므로, 여기서 바뀐 것이 틀린 답을 통과시키지는 않는다.
"""

from collections.abc import Mapping
from typing import cast

# 객체의 칸 이름이 열쇠인 자리. 이 아래의 열쇠는 스키마 낱말이 아니라 칸 이름이다.
_NAME_MAPS = frozenset({"properties", "$defs", "definitions"})


def _as_map(value: object) -> Mapping[str, object] | None:
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else None


def _as_list(value: object) -> list[object] | None:
    return cast("list[object]", value) if isinstance(value, list) else None


def to_strict_json_schema(schema: Mapping[str, object]) -> dict[str, object]:
    """OpenAI strict 가 받는 꼴로 다듬은 새 스키마를 돌려준다(규칙은 이 파일의 머리). 원본은 바꾸지 않는다."""
    return _strict(schema, root=schema)


def _resolve_ref(root: Mapping[str, object], ref: str) -> Mapping[str, object]:
    if not ref.startswith("#/"):
        raise ValueError(f"스키마의 $ref 가 #/ 로 시작하지 않는다: {ref}")
    node: Mapping[str, object] = root
    for key in ref[2:].split("/"):
        found = _as_map(node.get(key))
        if found is None:
            raise ValueError(f"스키마의 $ref 가 가리키는 곳이 없다: {ref}")
        node = found
    return node


def _strict(node: Mapping[str, object], *, root: Mapping[str, object]) -> dict[str, object]:
    out: dict[str, object] = dict(node)

    for names_key in ("$defs", "definitions"):
        named = _as_map(out.get(names_key))
        if named is not None:
            out[names_key] = {name: _strict_value(value, root=root) for name, value in named.items()}

    if out.get("type") == "object" and "additionalProperties" not in out:
        out["additionalProperties"] = False

    properties = _as_map(out.get("properties"))
    if properties is not None:
        out["required"] = list(properties)
        out["properties"] = {name: _strict_value(value, root=root) for name, value in properties.items()}

    if "items" in out:
        out["items"] = _strict_value(out["items"], root=root)

    any_of = _as_list(out.get("anyOf"))
    if any_of is not None:
        out["anyOf"] = [_strict_value(variant, root=root) for variant in any_of]

    all_of = _as_list(out.get("allOf"))
    if all_of is not None:
        only = _as_map(all_of[0]) if len(all_of) == 1 else None
        if only is not None:
            del out["allOf"]
            out.update(_strict(only, root=root))
        else:
            out["allOf"] = [_strict_value(entry, root=root) for entry in all_of]

    if "default" in out and out["default"] is None:
        del out["default"]

    ref = out.get("$ref")
    if isinstance(ref, str) and len(out) > 1:
        # `$ref` 곁의 열쇠가 가리키는 정의의 열쇠보다 앞선다.
        merged = {**_resolve_ref(root, ref), **out}
        del merged["$ref"]
        return _strict(merged, root=root)
    return out


def _strict_value(value: object, *, root: Mapping[str, object]) -> object:
    mapping = _as_map(value)
    return value if mapping is None else _strict(mapping, root=root)


# Anthropic 의 구조화 출력이 받지 않는 JSON Schema 제약(글자 길이, 수 범위, 배열 길이). 보내면 400 이라 지우고 보낸다
# (esg-lab 의 목록 아홉을 그대로 옮겼다). 값의 검증은 호출 층이 Pydantic 으로 하므로 제약 자체는 사라지지 않는다.
UNSUPPORTED_BY_ANTHROPIC = frozenset(
    {
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
    }
)


def strip_unsupported_schema_keys(schema: object) -> object:
    """스키마 낱말 자리에서만 지운다. `properties` 아래의 열쇠는 칸 이름이므로 건드리지 않는다. 원본은 바꾸지 않는다."""
    return _strip(schema, names=False)


def _strip(node: object, *, names: bool) -> object:
    items = _as_list(node)
    if items is not None:
        return [_strip(item, names=False) for item in items]
    mapping = _as_map(node)
    if mapping is None:
        return node
    out: dict[str, object] = {}
    for key, value in mapping.items():
        if not names and key in UNSUPPORTED_BY_ANTHROPIC:
            continue
        out[key] = _strip(value, names=not names and key in _NAME_MAPS)
    return out
