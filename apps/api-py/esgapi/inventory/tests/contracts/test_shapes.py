"""손으로 적는 serializer 의 글자가 결과 꼴(TypedDict)의 뼈대를 따르는가(밴드 CU1 ⑤, RR1 에서 좁힘). 순수 층.

결과 JSON 의 원천은 contracts/shapes.py 의 TypedDict 다(sid:MARC-ENT-268). 고정 스키마(tests/data/flow-shapes/)와
경로의 응답 꼴(→ generated/openapi.json)은 그것에서 기계로 나온다 — 경로가 같은 객체를 쓰는지는
tests/test_route_shapes.py(T1)가 묶는다. 손으로 남는 것은 serializer(engines/scope12/engine_1/serialize.py,
engines/scope3/llm_first_1/serialize.py·ranking.py 의 to_json)와 경로 전용 꼴(service/schemas/inventory.py 의
Scope 3 추리기·분류 맨 위)이고, 이 파일은 그것들이 실제로 낸 dict 를 뼈대(키의 차례·있어야 하는가·
null 이 되는가·판별 값·중첩)로 견준다:
키가 뼈대의 차례대로 나오고, 빠진 키는 「없어도 되는」 칸뿐이며, null 은 「null 이 되는」 칸에만 있는지.
잎의 타입은 견주지 않는다. 상수 하나인 잎(판별 칸의 값, unit 의 "tCO2eq" 따위)은 그 값까지 견준다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import pytest
from pydantic import TypeAdapter

from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import Classification, LlmFailure, LlmUsage, PromptUsage
from esgapi.inventory.engines.scope3.llm_first_1.ranking import CandidateEvidence, LexicalEvidence
from esgapi.inventory.engines.scope3.llm_first_1.serialize import classification_to_dict, failure_to_dict, usage_to_dict
from esgapi.inventory.engines.scope3.llm_first_1.types import InputRow
from esgapi.inventory.service.schemas import inventory as ninja
from esgapi.inventory.service.services import inventory as services
from esgapi.inventory.tests.engines.scope3.llm_first_1.test_pipeline import CASES as SHORTLIST_CASES
from esgapi.inventory.tests.engines.scope3.llm_first_1.test_pipeline import ROWS, catalog, setup_with_replies
from esgapi.inventory.tests.test_flow_shapes import CASES as FLOW_CASES
from esgapi.inventory.tests.test_flow_shapes import flow_result

type Json = Mapping[str, Any]

# ── 뼈대 ──


@dataclass(frozen=True, slots=True)
class Leaf:
    """잎. 상수 하나(const, 값 하나의 enum)면 그 값, 아니면 None. 여러 값 enum 이면 choices 에 그 값들(차례대로)."""

    const: object = None
    choices: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class Field:
    key: str
    required: bool
    nullable: bool
    shape: "Shape"


@dataclass(frozen=True, slots=True)
class Obj:
    fields: tuple[Field, ...]


@dataclass(frozen=True, slots=True)
class Arr:
    item: "Shape"


@dataclass(frozen=True, slots=True)
class Map:
    value: "Shape"


@dataclass(frozen=True, slots=True)
class Union:
    """판별 칸이 있으면 (그 이름, 판별 값 차례로 줄 세운 갈래), 없으면 (None, 적힌 차례의 갈래).
    갈래의 판별 칸은 상수 하나이거나 여러 값 enum 이다(그 값 가운데 하나면 그 갈래 — S3C-b1 의 활동 줄 kind)."""

    tag: str | None
    branches: tuple["Shape", ...]


type Shape = Leaf | Obj | Arr | Map | Union


def is_null(node: Json) -> bool:
    return node.get("type") == "null"


def tag_of(branch: "Shape", tag: str) -> tuple[str, ...]:
    """갈래의 판별 값들: 상수면 그 하나, 여러 값 enum 이면 그 값 전부."""
    assert isinstance(branch, Obj)
    (found,) = [field for field in branch.fields if field.key == tag]
    assert isinstance(found.shape, Leaf)
    if found.shape.choices:
        return tuple(str(choice) for choice in found.shape.choices)
    return (str(found.shape.const),)


def shape_of(node: Json, defs: Json) -> Shape:
    while "$ref" in node:
        node = defs[str(node["$ref"]).rsplit("/", 1)[-1]]
    variants: Sequence[Json] | None = node.get("oneOf") or node.get("anyOf")
    if variants is not None:
        branches = [shape_of(variant, defs) for variant in variants if not is_null(variant)]
        if len(branches) == 1:
            return branches[0]
        tag = cast("str | None", cast("Json", node.get("discriminator") or {}).get("propertyName"))
        if tag is None:
            # 판별 칸 없이 잎끼리 합친 것(Literal[1, 2] | Literal["other"])은 잎이다
            return Leaf() if all(isinstance(branch, Leaf) for branch in branches) else Union(None, tuple(branches))
        return Union(tag, tuple(sorted(branches, key=lambda branch: tag_of(branch, tag))))
    if "properties" in node:
        required = set(node.get("required", ()))
        fields: list[Field] = []
        for key, sub in cast("Json", node["properties"]).items():
            nullable = is_null(sub) or any(is_null(variant) for variant in sub.get("anyOf", ()))
            fields.append(Field(key, key in required, nullable, Leaf() if is_null(sub) else shape_of(sub, defs)))
        return Obj(tuple(fields))
    if node.get("type") == "array":
        return Arr(shape_of(node.get("items", {}), defs))
    extra = node.get("additionalProperties")
    if node.get("type") == "object" and isinstance(extra, Mapping):
        return Map(shape_of(cast("Json", extra), defs))
    if "const" in node:
        return Leaf(cast("object", node["const"]))
    enum = cast("list[object] | None", node.get("enum"))
    if enum is not None and len(enum) == 1:
        return Leaf(enum[0])
    return Leaf(choices=tuple(enum)) if enum else Leaf()


def shape(schema: Json) -> Shape:
    return shape_of(schema, cast("Json", schema.get("$defs", {})))


def typed(target: object) -> Shape:
    return shape(TypeAdapter[object](target).json_schema())


# ── 뼈대가 무는 것 ──


def test_the_skeleton_sees_keys_order_and_null() -> None:
    """뼈대가 실제로 무는 것: 키 하나를 더하거나, 차례를 바꾸거나, null 을 빼면 같지 않다."""
    base = typed(shapes.LlmFailureJson)
    assert isinstance(base, Obj)
    kind, detail = base.fields
    assert base != Obj((detail, kind))
    assert base != Obj((kind, detail, Field("extra", True, False, Leaf())))
    nullable = typed(shapes.BasisJson)
    assert isinstance(nullable, Obj)
    assert [(f.key, f.nullable) for f in nullable.fields] == [
        ("used", False),
        ("fellBack", False),
        ("fallbackReason", True),
    ]


# ── ② serializer 의 글자 ↔ 뼈대 ──


def fits(value: object, expected: Shape, where: str = "$") -> list[str]:
    """그 값이 뼈대에 맞지 않는 자리들. 키의 차례까지 본다."""
    problems: list[str] = []
    match expected:
        case Obj(fields):
            if not isinstance(value, Mapping):
                return [f"{where}: 객체가 아니다"]
            data = cast("Mapping[str, object]", value)
            declared = [field.key for field in fields]
            if list(data) != [key for key in declared if key in data]:
                problems.append(f"{where}: 키 {list(data)} 가 차례 {declared} 와 다르다")
            for field in fields:
                if field.key not in data:
                    if field.required:
                        problems.append(f"{where}.{field.key}: 없다")
                    continue
                if data[field.key] is None:
                    if not field.nullable:
                        problems.append(f"{where}.{field.key}: null 이 되지 않는 칸이다")
                    continue
                problems += fits(data[field.key], field.shape, f"{where}.{field.key}")
        case Arr(item):
            for index, entry in enumerate(cast("list[object]", value)):
                problems += fits(entry, item, f"{where}[{index}]")
        case Map(entry_shape):
            for key, entry in cast("Mapping[str, object]", value).items():
                problems += fits(entry, entry_shape, f"{where}[{key}]")
        case Union(tag, branches):
            if tag is None:
                if all(fits(value, branch, where) for branch in branches):
                    problems.append(f"{where}: 맞는 갈래가 없다")
            else:
                chosen = cast("Mapping[str, object]", value)[tag]
                (branch,) = [b for b in branches if str(chosen) in tag_of(b, tag)]
                problems += fits(value, branch, where)
        case Leaf(const):
            if const is not None and value != const:
                problems.append(f"{where}: {value!r} 는 상수 {const!r} 가 아니다")
    return problems


@pytest.mark.parametrize("case", FLOW_CASES)
def test_flow_results_follow_the_typed_dict_key_order(case: str) -> None:
    result = flow_result(case)
    # 모르는 판은 KeyError — 조용히 Scope3 로 치지 않는다(S3C-a 개정 1 B4)
    target = {
        "scope12.result@2": shapes.Scope12Result,
        "scope3.llm-first.result@2": shapes.Scope3Result,
        "scope3.colab.result@1": shapes.Scope3ColabResult,
    }[str(result["schemaVersion"])]
    assert fits(result, typed(target)) == []


def test_an_enum_discriminator_picks_its_branch() -> None:
    """enum 판별 갈래를 고른다: 줄의 kind 가 여러 값 enum 갈래의 값 하나면 그 갈래의 뼈대로 잰다(S3C-b1)."""
    sheet = typed(shapes.ColabProcessedSheetJson)
    assert isinstance(sheet, Obj)
    (rows,) = [field.shape for field in sheet.fields if field.key == "rows"]
    assert isinstance(rows, Arr) and isinstance(rows.item, Union)
    waste = fits({"rowId": "가상!9", "kind": "waste"}, rows.item)
    assert (
        [tag_of(branch, "kind") for branch in rows.item.branches],
        "$.activity: 없다" in waste and "$.biogenic: 없다" in waste and "$.amount: 없다" not in waste,
    ) == (
        [
            (
                "fuel_energy",
                "leased_asset",
                "leased_out_asset",
                "product_use",
                "product_eol",
                "franchise",
                "investment",
            ),
            ("purchase",),
            ("transport_spend", "travel_spend", "waste", "transport_distance", "travel_distance", "commute"),
        ],
        True,
    )


def test_the_calc_route_output_follows_the_body_key_order() -> None:
    for case in FLOW_CASES[:8]:
        result = dict(flow_result(case))
        del result["schemaVersion"]
        assert fits(result, typed(shapes.Scope12Body)) == [], case


def request_row(case_row: InputRow) -> dict[str, object]:
    """순수 층의 행 → 경로가 받는 행의 dict(주지 않은 칸은 키가 없다)."""
    data: dict[str, object] = {"itemName": case_row.item_name}
    if case_row.unit is not None:
        data["unit"] = case_row.unit
    if case_row.transport is not None:
        data["transport"] = {"mode": case_row.transport.mode, "weightKg": case_row.transport.weight_kg}
    return data


def test_the_shortlist_route_output_follows_the_ninja_key_order() -> None:
    expected = typed(ninja.Scope3ShortlistOut)
    statuses: set[object] = set()
    for case in SHORTLIST_CASES:
        output = services.scope3_shortlist_output(
            row=request_row(case.row),
            category=case.category,
            keywords=None,
            basis=None,
            method=None,
            bigrams=None,
            size=None,
            catalog=catalog(case.records),
        )
        assert fits(output, expected) == [], case.name
        statuses.add(output["status"])
    assert statuses == {"shortlisted", "no_candidates"}  # 분모: 두 갈래를 다 지났다


def test_the_classify_route_output_follows_the_ninja_key_order(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = setup_with_replies()
    monkeypatch.setattr(services, "scope3_gateway", lambda: setup.client)
    rows = [{"rowId": r.row_id, "itemName": r.item_name, "unit": r.unit} for r in ROWS]
    result = services.scope3_classify_output(rows=rows, company_id=7)
    assert isinstance(result, services.Scope3ClassifyDone)
    assert fits(result.output, typed(ninja.Scope3ClassifyOut)) == []


def test_the_small_pieces_follow_their_skeleton() -> None:
    usage = LlmUsage(calls=2, attempts=3, cost_usd=0.5, by_prompt={"p": PromptUsage(2, 3, 0.5)})
    evidence = CandidateEvidence(id="a", rank=1, lexical=LexicalEvidence(rank=1, score=0.5, matched_terms=("x",)))
    pieces: list[tuple[object, object]] = [
        (classification_to_dict(Classification(1, ("steel",), "high", "가상")), shapes.ClassificationJson),
        (failure_to_dict(LlmFailure("refusal", "가상")), shapes.LlmFailureJson),
        (usage_to_dict(usage), shapes.UsageJson),
        (evidence.to_json(), shapes.CandidateEvidenceJson),
    ]
    for value, typed_dict in pieces:
        assert fits(value, typed(typed_dict)) == []
