"""문서 모델의 읽는 쪽 검증. docpipe `schema-contract.test.ts` 9건 가운데 **옮길 수 있는 것**과 교차 검사 셋.

옮긴 뜻(구조 대조): 읽는 칸의 표(`READ_FIELDS`)를 정본 스키마 사본의 `properties`·`required`·`enum`·`type` 과 손으로
걸어 견준다.
  - 읽는 칸은 전부 정본에 있다 / 읽는 쪽이 필수로 보는 칸은 정본에서도 필수다 / enum 의 값이 같다 / 타입이 모순되지
    않는다
  - 구조 대조가 어긋남을 잡는다(읽는 쪽에 정본에 없는 칸을 더하면 모순이 나온다)
  - 정본이 허용하는 변형을 읽는 쪽도 받는다(선택 칸 없음, 모르는 칸 있음, 정수인 실수)
옮기지 않은 뜻: 「표본이 정본 스키마를 통과한다」류 — JSON Schema 검증기(`jsonschema`)가 api-py 에 없다(새 의존성 0).

★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.reconcile.calc.document import DOCUMENT_SHAPE, READ_FIELDS, DocumentInvalid, DocumentOk, validate_document
from esgapi.reconcile.calc.facts import extract_document
from esgapi.reconcile.calc.shape import Field, Obj, ReadField, Str, read_fields

HERE = Path(__file__).resolve().parents[1]
SCHEMAS = HERE / "data" / "schemas"
SYNTHETIC = HERE / "golden" / "synthetic"
Json = Any


def load(path: Path) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


def contradictions(fields: tuple[ReadField, ...], schema: Json) -> list[str]:
    """읽는 칸의 표와 정본 스키마의 모순(사람이 읽는 줄). 없으면 빈 목록. `test_places.py` 도 쓴다."""
    found: list[str] = []

    def resolve(node: Json) -> Json:
        while "$ref" in node:
            node = schema["$defs"][node["$ref"].removeprefix("#/$defs/")]
        return node

    for field in fields:
        node = schema
        parent_required = True
        missing = False
        for part in field.path.replace("[]", ".[]").split("."):
            node = resolve(node)
            if part == "[]":
                if node.get("type") != "array":
                    found.append(f"{field.path}: 정본에서 목록이 아니다")
                    missing = True
                    break
                node = node["items"]
                continue
            if part not in node.get("properties", {}):
                found.append(f"{field.path}: 정본에 없는 칸이다")
                missing = True
                break
            parent_required = part in node.get("required", [])
            node = node["properties"][part]
        if missing:
            continue
        node = resolve(node)
        if field.required and not field.path.endswith("[]") and not parent_required:
            found.append(f"{field.path}: 읽는 쪽은 필수로 보는데 정본에서는 선택이다")
        declared = node.get("type")
        types: list[Json] = cast("list[Json]", declared) if isinstance(declared, list) else [declared]
        if "const" in node:
            if field.enum != (node["const"],):
                found.append(f"{field.path}: 정본은 {node['const']!r} 하나인데 읽는 쪽은 {field.enum}")
        elif "enum" in node:
            # 읽는 쪽이 enum 으로 읽으면 값이 같아야 한다. 글자로만 읽으면(더 넓게 받으면) 모순이 아니다.
            if field.enum is not None and set(field.enum) != set(node["enum"]):
                found.append(f"{field.path}: enum 이 다르다 — 정본 {node['enum']} / 읽는 쪽 {list(field.enum)}")
            elif field.enum is None and field.type != "string":
                found.append(f"{field.path}: 정본은 enum(글자)인데 읽는 쪽은 {field.type}")
        elif field.enum is not None:
            found.append(f"{field.path}: 읽는 쪽은 enum 인데 정본은 아니다(정본이 받는 값을 읽는 쪽이 거절한다)")
        elif field.type not in types and not (field.type == "number" and "integer" in types):
            # 정본이 integer 인 칸을 읽는 쪽이 number 로 읽는 것은 더 넓게 받는 것이라 모순이 아니다.
            found.append(f"{field.path}: 타입이 다르다 — 정본 {declared} / 읽는 쪽 {field.type}")
        if "null" in types:
            found.append(f"{field.path}: 정본은 null 을 허용하는데 읽는 쪽은 받지 않는다")
        if field.type == "array":
            if field.length is not None and (node.get("minItems"), node.get("maxItems")) != (
                field.length,
                field.length,
            ):
                found.append(f"{field.path}: 길이 {field.length} 로 읽는데 정본의 길이 제한이 다르다")
            if field.min_length > node.get("minItems", 0):
                found.append(f"{field.path}: 읽는 쪽의 최소 길이 {field.min_length} 가 정본보다 엄하다")
    return found


def test_the_schema_copy_is_the_original_byte_for_byte() -> None:
    digest = hashlib.sha256((SCHEMAS / "document.schema.json").read_bytes()).hexdigest()
    assert digest == "cbdb3e38ad5c07e7c6c930f9d4533799dd33a713ae8cf82e0f00ad473e77469b"
    assert digest in (SCHEMAS / "README.md").read_text(encoding="utf-8")


def test_every_field_we_read_is_in_the_schema_with_a_compatible_type_and_requiredness() -> None:
    # 표는 시험 안에서 낸다 — 모듈 상수 READ_FIELDS 는 import 때 굳어 mutmut 의 변이가 닿지 않는다(MARC-ISSUE-154).
    # 상수가 따로 놀지 않게 같은지는 한 번 본다.
    fields = read_fields(DOCUMENT_SHAPE)
    assert fields == READ_FIELDS
    assert contradictions(fields, load(SCHEMAS / "document.schema.json")) == []
    paths = {field.path for field in fields}
    assert len(fields) == len(paths) == 40
    # 읽는 쪽이 요구하지 않는 칸(docpipe 쪽만 읽는다)이 표에 없다.
    assert not paths & {
        "parser",
        "sections",
        "blocks[].section_id",
        "tables[].n_rows",
        "tables[].n_cols",
        "tables[].notes",
    }
    optional = {field.path for field in fields if not field.required}
    assert optional == {"blocks[].text", "blocks[].table_id"}


def test_the_structural_comparison_catches_a_mismatch() -> None:
    schema = load(SCHEMAS / "document.schema.json")
    extra = read_fields(Obj({**DOCUMENT_SHAPE.fields, "made_up": Field(Str())}))
    assert contradictions(extra, schema) == ["made_up: 정본에 없는 칸이다"]
    # 정본에서 선택인 칸(blocks[].text)을 필수로 읽으면 모순이다.
    fields = read_fields(DOCUMENT_SHAPE)
    strict = tuple(ReadField(f.path, f.type, True, f.enum, f.length, f.min_length) for f in fields)
    assert contradictions(strict, schema) == [
        "blocks[].text: 읽는 쪽은 필수로 보는데 정본에서는 선택이다",
        "blocks[].table_id: 읽는 쪽은 필수로 보는데 정본에서는 선택이다",
    ]
    # enum 의 값이 다르면 모순이다.
    narrowed = copy.deepcopy(schema)
    narrowed["$defs"]["table"]["properties"]["status"]["enum"] = ["ok", "failed"]
    assert any("tables[].status: enum 이 다르다" in line for line in contradictions(fields, narrowed))


def test_the_synthetic_document_validates_and_unknown_fields_are_ignored() -> None:
    raw = load(SYNTHETIC / "document.json")
    checked = validate_document(raw)
    assert isinstance(checked, DocumentOk)
    assert checked.ok is True
    assert (len(checked.document.blocks), len(checked.document.tables), len(checked.document.pages)) == (34, 5, 3)
    # 모르는 칸은 지나친다: docpipe 쪽만 읽는 칸을 지워도, 처음 보는 칸을 더해도 같은 문서 모델이다.
    slim = copy.deepcopy(raw)
    del slim["parser"], slim["sections"]
    for block in slim["blocks"]:
        del block["section_id"]
    for table in slim["tables"]:
        del table["n_rows"], table["n_cols"], table["notes"]
    slim["blocks"][0]["font_size"] = 11.5
    slim["future_field"] = {"anything": [1, 2, 3]}
    slimmed = validate_document(slim)
    assert isinstance(slimmed, DocumentOk)
    assert slimmed.document == checked.document


def test_integral_floats_are_integers_like_in_js() -> None:
    raw = load(SYNTHETIC / "document.json")
    raw["blocks"][0]["page"] = 1.0
    raw["blocks"][0]["order"] = 1.0
    checked = validate_document(raw)
    assert isinstance(checked, DocumentOk)
    assert checked.document.blocks[0].page == 1
    assert type(checked.document.blocks[0].page) is int


def minimal() -> Json:
    return {
        "schema_version": "0.1",
        "source": {"file_name": "m.synthetic.pdf", "sha256": "0" * 64, "page_count": 1},
        "pages": [{"page": 1, "height": 800, "text_layer": "present"}],
        "blocks": [
            {"id": "p1-b1", "kind": "paragraph", "page": 1, "bbox": [0, 0, 1, 1], "order": 1, "text": "배출량 12톤"},
            {"id": "p1-b2", "kind": "table", "page": 1, "bbox": [0, 0, 1, 1], "order": 2, "table_id": "p1-t1"},
        ],
        "tables": [
            {
                "id": "p1-t1",
                "page": 1,
                "cells": [["구분", "값"], ["가", "3"]],
                "header": {"rows": [0], "cols": [0], "basis": "rows_before_first_numeric_row"},
                "method": "lines",
                "status": "ok",
                "footnote_marks": [],
            }
        ],
    }


def test_the_minimal_document_with_only_the_fields_we_read_goes_all_the_way_to_candidates() -> None:
    checked = validate_document(minimal())
    assert isinstance(checked, DocumentOk)
    assert [fact.id for fact in extract_document(checked.document, "m").facts] == ["p1-t1:r1c1", "p1-b1#n1"]


def change(path: list[str | int], value: Json) -> Json:
    raw = minimal()
    node = raw
    for key in path[:-1]:
        node = node[key]
    if value is ...:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return raw


@pytest.mark.parametrize(
    ("raw", "where", "problem"),
    [
        ([], "(맨 위)", "객체여야 한다"),
        (change(["schema_version"], "0.2"), "schema_version", "'0.1' 여야 한다"),
        (change(["source"], ...), "source", "칸이 없다"),
        (change(["source", "page_count"], "3"), "source.page_count", "정수여야 한다"),
        (change(["source", "page_count"], True), "source.page_count", "정수여야 한다"),
        (change(["pages", 0, "page"], 1.5), "pages[0].page", "정수여야 한다"),
        (change(["pages", 0, "height"], float("nan")), "pages[0].height", "수여야 한다"),
        (change(["pages", 0, "text_layer"], "ocr"), "pages[0].text_layer", "present | none 가운데 하나여야 한다"),
        (change(["blocks", 0, "bbox"], [0, 0, 1]), "blocks[0].bbox", "길이가 4 이어야 한다(받은 것 3)"),
        (change(["blocks", 0, "bbox"], [0, 0, 1, "1"]), "blocks[0].bbox[3]", "수여야 한다"),
        (change(["blocks", 0, "kind"], "figure"), "blocks[0].kind", "paragraph | table | heading 가운데 하나여야 한다"),
        (change(["blocks", 0, "text"], None), "blocks[0].text", "글자여야 한다"),
        (change(["blocks"], {}), "blocks", "목록이어야 한다"),
        (change(["tables", 0, "cells"], [["가", 1]]), "tables[0].cells[0][1]", "글자여야 한다"),
        (change(["tables", 0, "header", "rows"], ...), "tables[0].header.rows", "칸이 없다"),
        (
            change(["tables", 0, "status"], "partial"),
            "tables[0].status",
            "ok | low_confidence | failed 가운데 하나여야 한다",
        ),
        (
            change(["tables", 0, "footnote_marks"], [{"row": 1, "col": 1}]),
            "tables[0].footnote_marks[0].mark",
            "칸이 없다",
        ),
    ],
)
def test_a_wrong_shape_is_a_named_branch_not_an_exception(raw: Json, where: str, problem: str) -> None:
    checked = validate_document(raw)
    assert isinstance(checked, DocumentInvalid)
    assert (checked.ok, checked.where, checked.problem) == (False, where, problem)


def test_the_three_cross_checks() -> None:
    """docpipe `parseDocument` 의 교차 검사 셋. 빈 결과로 넘기지 않고 실패 갈래로 낸다."""
    duplicate = minimal()
    duplicate["blocks"].append({**duplicate["blocks"][0]})
    checked = validate_document(duplicate)
    assert isinstance(checked, DocumentInvalid)
    assert (checked.where, checked.problem) == ("blocks[2]", "블록 id 가 겹친다: p1-b1")

    for table_id in ("p9-t9", ..., ""):
        checked = validate_document(change(["blocks", 1, "table_id"], table_id))
        assert isinstance(checked, DocumentInvalid)
        assert checked.where == "blocks[1]"
        assert "없는 표를 가리킨다" in checked.problem

    # ★ TS 와 다르게 한 것: reconcile TS 는 text 없는 글 블록을 빈 글로 읽는다(`block.text ?? ""`). 여기서는 실패
    # 갈래다.
    checked = validate_document(change(["blocks", 0, "text"], ...))
    assert isinstance(checked, DocumentInvalid)
    assert (checked.where, checked.problem) == ("blocks[0]", "블록 p1-b1 에 text 가 없다")
    # 표 블록에는 text 가 없어도 된다.
    assert isinstance(validate_document(minimal()), DocumentOk)
