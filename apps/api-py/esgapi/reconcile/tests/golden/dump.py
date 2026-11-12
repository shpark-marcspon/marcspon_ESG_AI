"""골든 덤프 (파이썬 쪽). `dump.mts` 가 TS 로 내는 것과 **같은 꼴의 JSON 값**을 `reconcile/calc` 로 낸다.

키 이름은 TS 의 것(camelCase)이다. 두 덤프는 글자가 아니라 값으로 견준다(`same`):
JS 는 `1.0` 을 `1` 로 적고 파이썬은 `1.0` 으로 적지만 값은 같다. 해시(`digest`)는 양쪽을 같은 정규화로 낸다:
TS 덤프도 파이썬이 읽어 들인 뒤 이 파일의 `canonical` 로 다시 적어 sha256 을 낸다.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any, cast

from esgapi.reconcile.calc import dec as decimal_helpers
from esgapi.reconcile.calc.count import count_ratio
from esgapi.reconcile.calc.document import DocumentInvalid, validate_document
from esgapi.reconcile.calc.facts import extract_document
from esgapi.reconcile.calc.kinds import KindContext, kind_of
from esgapi.reconcile.calc.mask import cell_text, mask_text
from esgapi.reconcile.calc.notation import classify_cell, locate_quote, normalize_text, scan_numbers
from esgapi.reconcile.calc.types import (
    CellNotation,
    Fact,
    FactWhere,
    Headers,
    NumberToken,
    ParsedNumber,
    StoredNumber,
)

Json = Any

# 네 문서의 구획 (`failed` 는 failedTables·pagesWithoutText 를 하나로 센 것). 여덟째 `places`(상자)는 `dump_places.py`
# 가 낸다.
SECTIONS = ("facts", "nonValues", "grids", "failed", "kinds", "count", "masks")
# 지은 문서에만 붙는 구획 둘.
CASE_SECTIONS = ("dec", "notation")


def where_json(where: FactWhere) -> Json:
    span = where.span
    return {
        "page": where.page,
        "sheet": where.sheet,
        "gridId": where.grid_id,
        "row": where.row,
        "col": where.col,
        "ref": where.ref,
        "blockId": where.block_id,
        "span": None if span is None else {"start": span.start, "end": span.end, "occurrence": span.occurrence},
    }


def headers_json(headers: Headers | None) -> Json:
    if headers is None:
        return None
    return {
        "row": [{"cell": ref.cell, "text": ref.text, "inherited": ref.inherited} for ref in headers.row],
        "col": [{"cell": ref.cell, "text": ref.text, "inherited": ref.inherited} for ref in headers.col],
    }


def stored_json(stored: StoredNumber | None) -> Json:
    if stored is None:
        return None
    return {
        "storedRaw": stored.stored_raw,
        "stored": stored.stored,
        "formatCode": stored.format_code,
        "display": stored.display,
        "displayStatus": stored.display_status,
        "isDate": stored.is_date,
        "formula": stored.formula,
    }


def fact_json(fact: Fact) -> Json:
    return {
        "id": fact.id,
        "docId": fact.doc_id,
        "bucket": fact.bucket,
        "where": where_json(fact.where),
        "raw": fact.raw,
        "value": fact.value,
        "decimals": fact.decimals,
        "sign": fact.sign,
        "percent": fact.percent,
        "unitSuffix": fact.unit_suffix,
        "flags": list(fact.flags),
        "footnoteMarks": list(fact.footnote_marks),
        "tableStatus": fact.table_status,
        "headers": headers_json(fact.headers),
        "stored": stored_json(fact.stored),
        "storedAsText": fact.stored_as_text,
    }


def number_json(number: ParsedNumber | None) -> Json:
    if number is None:
        return None
    return {
        "value": number.value,
        "decimals": number.decimals,
        "sign": number.sign,
        "percent": number.percent,
        "unitSuffix": number.unit_suffix,
        "flags": list(number.flags),
    }


def notation_json(notation: CellNotation) -> Json:
    return {"kind": notation.kind, "number": number_json(notation.number)}


def token_json(token: NumberToken) -> Json:
    return {
        "raw": token.raw,
        "start": token.start,
        "end": token.end,
        "occurrence": token.occurrence,
        "kind": token.kind,
        "number": number_json(token.number),
    }


class DumpInputError(Exception):
    """입력이 꼴 검사를 통과하지 못했다(골든의 입력은 통과해야 한다)."""


def dump_document(document_json: Json, doc_id: str) -> dict[str, Json]:
    """문서 하나의 구획 일곱(상자를 뺀 것)."""
    checked = validate_document(document_json)
    if isinstance(checked, DocumentInvalid):
        raise DumpInputError(f"document: {checked.where}: {checked.problem}")
    document = checked.document
    extraction = extract_document(document, doc_id)
    own = extract_document(document, doc_id, titles="own")
    with_kinds = extract_document(document, doc_id, kinds=True)
    if with_kinds.facts != extraction.facts:
        raise DumpInputError("종류를 켰더니 값 후보 목록이 달라졌다")

    fact_map = {fact.id: fact for fact in extraction.facts}
    mask_blocks = {b.id: mask_text(b.text) for b in document.blocks if b.kind != "table" and b.text is not None}
    mask_cells: dict[str, str] = {}
    for grid in extraction.grids:
        for row, cells in enumerate(grid.cells):
            for col, raw in enumerate(cells):
                if normalize_text(raw) != "":
                    mask_cells[f"{grid.id}:r{row}c{col}"] = cell_text(grid, row, col, raw, fact_map, True)

    ratio = count_ratio(extraction)
    return {
        "facts": [fact_json(fact) for fact in extraction.facts],
        "nonValues": [{"where": where_json(i.where), "raw": i.raw, "class": i.cls} for i in extraction.non_values],
        "grids": [
            {
                "id": grid.id,
                "page": grid.page,
                "header": {"rows": list(grid.header.rows), "cols": list(grid.header.cols), "basis": grid.header.basis},
                "status": grid.status,
                "innerHeaders": list(grid.inner_headers or ()),
                "footnoteMarks": [{"row": m.row, "col": m.col, "mark": m.mark} for m in grid.footnote_marks],
                "titleCandidates": list(grid.title_candidates),
                "unitLines": list(grid.unit_lines),
                "titleCandidatesOwn": list(own.grids[i].title_candidates),
            }
            for i, grid in enumerate(extraction.grids)
        ],
        "failed": {
            "failedTables": [{"id": t.id, "page": t.page} for t in extraction.failed_tables],
            "pagesWithoutText": list(extraction.pages_without_text),
        },
        "kinds": dict(with_kinds.kinds or {}),
        "count": {
            "docId": ratio.doc_id,
            "fileName": ratio.file_name,
            "valueCandidates": ratio.value_candidates,
            "tableCellsOk": ratio.table_cells_ok,
            "tableCellsLowConfidence": ratio.table_cells_low_confidence,
            "tableTextCellsOk": ratio.table_text_cells_ok,
            "tableTextCellsLowConfidence": ratio.table_text_cells_low_confidence,
            "sentences": ratio.sentences,
            "numberOnlyBlocks": ratio.number_only_blocks,
            "failedTables": ratio.failed_tables,
            "pagesWithoutText": ratio.pages_without_text,
            "tables": {"ok": ratio.tables_ok, "lowConfidence": ratio.tables_low_confidence},
            "nonValues": dict(ratio.non_values),
            "nonValueTotal": ratio.non_value_total,
        },
        "masks": {"blocks": mask_blocks, "cells": mask_cells},
    }


def _attempt(run: Any) -> Json:
    try:
        return run()
    except (ValueError, TypeError):
        return "(예외)"


def dump_cases(cases: Mapping[str, Json]) -> dict[str, Json]:
    """지은 문서에만 붙는 구획 둘: 십진 도우미와 표기 규칙의 낱개 본보기."""
    d = decimal_helpers
    dec_cases = cases["dec"]
    notation = cases["notation"]

    def kind_of_case(text: str, raw: str) -> Json:
        token = next((t for t in scan_numbers(text) if t.raw == raw and t.kind == "value"), None)
        if token is None or token.number is None:
            return None
        n = token.number
        where = FactWhere(None, None, None, None, None, None, None, None)
        fact = Fact(
            "",
            "",
            "sentence",
            where,
            token.raw,
            n.value,
            n.decimals,
            n.sign,
            n.percent,
            n.unit_suffix,
            n.flags,
            (),
            None,
            None,
            None,
            False,
        )
        return kind_of(fact, KindContext(text, token.start, token.end, ()))

    def quote_case(text: str, quote: str, occurrence: Json) -> Json:
        found = locate_quote(text, quote, occurrence)
        return None if found is None else {"start": found[0], "end": found[1], "total": found[2]}

    return {
        "dec": {
            "shift10": [_attempt(lambda v=v, e=e: d.show(d.shift10(d.dec(v), e))) for v, e in dec_cases["shift10"]],
            "roundToPow10": [
                _attempt(lambda v=v, e=e, m=m: d.show(d.round_to_pow10(d.dec(v), e, m)))
                for v, e, m in dec_cases["roundToPow10"]
            ],
            "compare": [_attempt(lambda a=a, b=b: d.compare(d.dec(a), d.dec(b))) for a, b in dec_cases["compare"]],
            "sub": [_attempt(lambda a=a, b=b: d.show(d.sub(d.dec(a), d.dec(b)))) for a, b in dec_cases["sub"]],
        },
        "notation": {
            "normalize": [normalize_text(text) for text in notation["cells"]],
            "cells": [notation_json(classify_cell(text)) for text in notation["cells"]],
            "texts": [[token_json(token) for token in scan_numbers(text)] for text in notation["texts"]],
            "masks": [mask_text(text) for text in notation["texts"]],
            "quotes": [quote_case(text, quote, occurrence) for text, quote, occurrence in notation["quotes"]],
            "kindOf": [kind_of_case(text, raw) for text, raw in notation["kindOf"]],
        },
    }


def canonical(value: Json) -> str:
    """값이 같으면 글자도 같은 JSON. 키는 가나다순, 정수인 실수(`800.0`)는 정수로 적는다."""

    def tidy(item: Json) -> Json:
        if isinstance(item, float) and math.isfinite(item) and item.is_integer():
            return math.trunc(item)
        if isinstance(item, dict):
            return {key: tidy(child) for key, child in cast("dict[str, Json]", item).items()}
        if isinstance(item, list):
            return [tidy(child) for child in cast("list[Json]", item)]
        return item

    return json.dumps(tidy(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(value: Json) -> str:
    return hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def size(section: str, value: Json) -> int:
    """구획의 건수(보고에 싣는 수). 해시와 함께 `lab-digest.json` 에 적는다."""
    if section == "failed":
        return len(value["failedTables"]) + len(value["pagesWithoutText"])
    if section == "count":
        return value["valueCandidates"]
    if section == "masks":
        return len(value["blocks"]) + len(value["cells"])
    if section == "places":
        return sum(1 for place in value["facts"] if place["found"])
    if section in ("dec", "notation"):
        return sum(len(items) for items in value.values())
    return len(value)


def first_difference(a: Json, b: Json, path: str = "") -> str | None:
    """두 값이 처음으로 갈리는 자리(사람이 읽는 한 줄). 같으면 None."""
    if isinstance(a, dict) and isinstance(b, dict):
        left, right = cast("dict[str, Json]", a), cast("dict[str, Json]", b)
        for key in sorted({*left, *right}):
            if key not in left or key not in right:
                return f"{path}.{key}: 한쪽에만 있다"
            found = first_difference(left[key], right[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(a, list) and isinstance(b, list):
        xs, ys = cast("list[Json]", a), cast("list[Json]", b)
        if len(xs) != len(ys):
            return f"{path}: 길이 {len(xs)} 대 {len(ys)}"
        for index, (x, y) in enumerate(zip(xs, ys, strict=True)):
            found = first_difference(x, y, f"{path}[{index}]")
            if found:
                return found
        return None
    if isinstance(a, bool) != isinstance(b, bool) or a != b:
        return f"{path}: {a!r} 대 {b!r}"
    return None
