"""문서 모델(`document.json`, 형식 0.1)의 읽는 쪽 검증. 통과한 것만 `DocModel` 이 되어 `extract_document` 로 간다.

필수 칸은 **reconcile 쪽 집합**이다(esg-lab `ts/reconcile/src/adapters/files.ts:61-88` 의 zod 사본).
docpipe 쪽만 읽는 칸(`sections`·`parser`·`section_id`·`n_rows`·`n_cols`·`notes`)은 요구하지 않는다. 있어도 된다.
형식의 정본은 esg-lab `schemas/document.schema.json` 이다(사본: `tests/data/schemas/`). 여기 표가 정본과 어긋나지
않는지는 `tests/calc/test_document_ts.py` 가 `READ_FIELDS` 를 스키마와 견주어 본다.

거기에 `ts/docpipe/src/document.ts` 의 `parseDocument` 가 하는 교차 검사 셋을 더했다:
블록 id 겹침 · 없는 표를 가리키는 표 블록 · 글 블록에 `text` 없음.
★ TS 와 다르게 한 것: 셋째는 reconcile TS 보다 엄하다(TS 는 `block.text ?? ""` 로 빈 글로 읽는다).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast

from esgapi.reconcile.calc.shape import (
    Arr,
    Const,
    Enum,
    Field,
    Int,
    Json,
    Num,
    Obj,
    ReadField,
    Str,
    as_int,
    check,
    read_fields,
)
from esgapi.reconcile.calc.types import DocBlock, DocModel, DocPage, DocSource, DocTable, FootnoteMark, GridHeader

SCHEMA_VERSION: Final = "0.1"

SOURCE_SHAPE: Final = Obj({"file_name": Field(Str()), "sha256": Field(Str()), "page_count": Field(Int())})

DOCUMENT_SHAPE: Final = Obj(
    {
        "schema_version": Field(Const(SCHEMA_VERSION)),
        "source": Field(SOURCE_SHAPE),
        "pages": Field(
            Arr(Obj({"page": Field(Int()), "height": Field(Num()), "text_layer": Field(Enum(("present", "none")))}))
        ),
        "blocks": Field(
            Arr(
                Obj(
                    {
                        "id": Field(Str()),
                        "kind": Field(Enum(("paragraph", "table", "heading"))),
                        "page": Field(Int()),
                        "bbox": Field(Arr(Num(), length=4)),
                        "order": Field(Int()),
                        "text": Field(Str(), required=False),
                        "table_id": Field(Str(), required=False),
                    }
                )
            )
        ),
        "tables": Field(
            Arr(
                Obj(
                    {
                        "id": Field(Str()),
                        "page": Field(Int()),
                        "cells": Field(Arr(Arr(Str()))),
                        "header": Field(
                            Obj({"rows": Field(Arr(Int())), "cols": Field(Arr(Int())), "basis": Field(Str())})
                        ),
                        "method": Field(Enum(("lines", "text", "none"))),
                        "status": Field(Enum(("ok", "low_confidence", "failed"))),
                        "footnote_marks": Field(
                            Arr(Obj({"row": Field(Int()), "col": Field(Int()), "mark": Field(Str())}))
                        ),
                    }
                )
            )
        ),
    }
)

# 읽는 칸의 표(이름·필수 여부·enum). 계약 테스트의 재료다.
READ_FIELDS: Final[tuple[ReadField, ...]] = read_fields(DOCUMENT_SHAPE)


@dataclass(frozen=True, slots=True)
class DocumentOk:
    document: DocModel
    ok: Literal[True] = True


@dataclass(frozen=True, slots=True)
class DocumentInvalid:
    where: str  # 틀린 자리 (`blocks[3].bbox`, `blocks[7]`)
    problem: str
    ok: Literal[False] = False


DocumentResult = DocumentOk | DocumentInvalid


def read_source(raw: Mapping[str, Json]) -> DocSource:
    return DocSource(raw["file_name"], raw["sha256"], as_int(raw["page_count"]))


def _box(raw: Sequence[Json]) -> tuple[float, float, float, float]:
    return (raw[0], raw[1], raw[2], raw[3])


def validate_document(raw: Json) -> DocumentResult:
    """JSON 값(dict)을 검증해 `DocModel` 로. 틀리면 첫 번째로 틀린 자리 하나를 갈래로 돌려준다(예외가 아니다)."""
    problem = check(raw, DOCUMENT_SHAPE)
    if problem is not None:
        return DocumentInvalid(problem.where, problem.problem)
    data = cast("Mapping[str, Json]", raw)

    tables = tuple(
        DocTable(
            id=t["id"],
            page=as_int(t["page"]),
            cells=tuple(tuple(row) for row in t["cells"]),
            header=GridHeader(
                tuple(as_int(i) for i in t["header"]["rows"]),
                tuple(as_int(i) for i in t["header"]["cols"]),
                t["header"]["basis"],
            ),
            method=t["method"],
            status=t["status"],
            footnote_marks=tuple(
                FootnoteMark(as_int(m["row"]), as_int(m["col"]), m["mark"]) for m in t["footnote_marks"]
            ),
        )
        for t in data["tables"]
    )
    table_ids = {table.id for table in tables}
    blocks: list[DocBlock] = []
    block_ids: set[str] = set()
    for index, b in enumerate(data["blocks"]):
        block = DocBlock(
            id=b["id"],
            kind=b["kind"],
            page=as_int(b["page"]),
            bbox=_box(b["bbox"]),
            order=as_int(b["order"]),
            text=b.get("text"),
            table_id=b.get("table_id"),
        )
        where = f"blocks[{index}]"
        if block.id in block_ids:
            return DocumentInvalid(where, f"블록 id 가 겹친다: {block.id}")
        block_ids.add(block.id)
        if block.kind == "table":
            if not block.table_id or block.table_id not in table_ids:
                return DocumentInvalid(where, f"블록 {block.id} 가 없는 표를 가리킨다: {block.table_id}")
        elif block.text is None:
            return DocumentInvalid(where, f"블록 {block.id} 에 text 가 없다")
        blocks.append(block)

    return DocumentOk(
        DocModel(
            source=read_source(data["source"]),
            pages=tuple(DocPage(as_int(p["page"]), p["height"], p["text_layer"]) for p in data["pages"]),
            blocks=tuple(blocks),
            tables=tables,
        )
    )
