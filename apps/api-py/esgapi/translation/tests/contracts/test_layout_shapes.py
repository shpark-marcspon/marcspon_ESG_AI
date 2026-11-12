"""꼴 translation.layout@1(contracts/layout_shapes.py — 밴드 TRD2 S1): 고정 스키마 파일과 글자까지 같고, 흐름이 지은
결과가 strict 로 맞으며, 모르는 키·빠진 키·범위 밖 값을 거부한다. 문서·글은 지어낸 것."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from esgapi.translation.contracts.layout_shapes import LAYOUT_SHAPE, LAYOUT_SHAPES

PINNED = Path(__file__).resolve().parents[1] / "data" / "flow-shapes" / f"{LAYOUT_SHAPE}.schema.json"
ADAPTER = LAYOUT_SHAPES[LAYOUT_SHAPE]


def a_layout() -> dict[str, Any]:
    member = {"id": "p1-b2", "key": "k0102", "kind": "heading", "bbox": [40, 80.5, 280, 96], "source": "물 관리"}
    table = {"id": "p1-t1", "key": None, "kind": "table", "bbox": [40, 200, 560, 300], "source": "| 구분 | 2024 |"}
    cell = {"row": 2, "col": 1, "id": "p1-t1:r2c1", "bbox": None, "source": "1,200"}
    return {
        "schemaVersion": "translation.layout@1",
        "status": "done",
        "sourceSha256": "0" * 64,
        "source": {
            "pdfSha256": "1" * 64,
            "pageCount": 3,
            "parser": {"name": "docparse", "version": "0.0-virtual", "layout": 2},
            "adapter": "pdf_tags@1",
        },
        "pages": [{"page": 1, "width": 595, "height": 842.0, "textLayer": "present"}],
        "units": [
            {"tag": "BLOCK 1", "page": 1, "kind": "block", "members": [member]},
            {"tag": "TABLE 1", "page": 1, "kind": "table", "members": [table], "cells": [cell], "rows": [0, 2]},
            {"tag": None, "page": 1, "kind": "header", "members": [{**member, "kind": "paragraph"}]},
        ],
        "variants": [
            {
                "label": "single",
                "stage": "autofix",
                "units": [
                    {"tag": "BLOCK 1", "page": 1, "level": "block", "translations": ["Water stewardship"]},
                    {
                        "tag": "TABLE 1",
                        "page": 1,
                        "level": "cell",
                        "translations": None,
                        "cells": [{"row": 2, "col": 1, "text": "1,200"}],
                    },
                    {"tag": None, "page": 1, "level": "source_only", "translations": None},
                ],
                "unplaced": [{"page": 1, "text": "[BLOCK 9]\nstray"}],
            }
        ],
        "skipped": {"emptyTables": ["p2-t1"], "imageOnlyPages": [3]},
        "warnings": [
            {"code": "image_only_page", "page": 3, "tag": None, "variant": None},
            {"code": "tag_extra", "page": 1, "tag": "BLOCK 9", "variant": "single"},
        ],
    }


def test_the_json_schema_is_pinned() -> None:
    assert json.dumps(ADAPTER.json_schema(), ensure_ascii=False, indent=2) + "\n" == PINNED.read_text(encoding="utf-8")


def test_a_layout_fits() -> None:
    ADAPTER.validate_python(a_layout(), strict=True)


def test_a_rejected_layout_without_a_parser_fits() -> None:
    base = a_layout()
    rejected: dict[str, Any] = {
        **base,
        "status": "rejected",
        "source": {**base["source"], "pageCount": None, "parser": None},
        "pages": [],
        "units": [],
        "variants": [],
        "skipped": {"emptyTables": [], "imageOnlyPages": []},
        "warnings": [],
    }
    ADAPTER.validate_python(rejected, strict=True)


def broken() -> list[dict[str, Any]]:
    base = a_layout()
    out: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    out.append({**base, "extra": 1})
    out.append({**base, "schemaVersion": "translation.result@1"})
    out.append({**base, "status": "failed"})
    edits: list[tuple[tuple[str | int, ...], str, Any]] = [
        (("source", "parser"), "layout", 1),  # 번역 판 2 만
        (("units", 0, "members", 0), "bbox", [1, 2, 3]),
        (("units", 0), "tag", "PAGE 1"),
        (("variants", 0, "units", 0), "level", "partial"),
        (("pages", 0), "width", -1),
        (("warnings", 0), "code", "unknown"),
        (("variants", 0), "stage", "polished"),
        (("units", 1, "cells", 0), "row", -1),
    ]
    for path, key, value in edits:
        changed = copy.deepcopy(base)
        at: Any = changed
        for step in path:
            at = at[step]
        at[key] = value
        out.append(changed)
    return out


@pytest.mark.parametrize("value", broken())
def test_a_broken_layout_is_rejected(value: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(value, strict=True)
