"""스키마 검증."""

import pytest
from jsonschema import Draft202012Validator

from docparse.document import load_schema, parse_pdf, validate

from . import pdfbuild
from .conftest import hline, put


def minimal_doc():
    table = {
        "id": "p1-t1",
        "page": 1,
        "bbox": [0, 0, 10, 10],
        "n_rows": 2,
        "n_cols": 2,
        "cells": [["a", "b"], ["1", "2"]],
        "header": {"rows": [0], "cols": [0], "basis": "rows_before_first_numeric_row"},
        "method": "lines",
        "status": "ok",
        "notes": [],
        "footnote_marks": [],
    }
    return {
        "schema_version": "0.1",
        "source": {"file_name": "synthetic.pdf", "sha256": "0" * 64, "page_count": 1},
        "parser": {
            "name": "docparse",
            "version": "0.1.0",
            "table_strategy": "auto",
            "llm_used": False,
            "ocr_used": False,
        },
        "pages": [
            {
                "page": 1,
                "width": 100.0,
                "height": 100.0,
                "text_layer": "present",
                "char_count": 4,
                "image_coverage": 0.0,
                "columns": 1,
                "notes": [],
            }
        ],
        "sections": [
            {"id": "s1", "title": None, "level": 1, "page_start": 1, "page_end": 1, "basis": "no_title_found"}
        ],
        "blocks": [
            {
                "id": "p1-b1",
                "kind": "table",
                "page": 1,
                "bbox": [0, 0, 10, 10],
                "order": 1,
                "section_id": "s1",
                "table_id": "p1-t1",
            }
        ],
        "tables": [table],
    }


def test_schema_itself_is_valid_json_schema():
    Draft202012Validator.check_schema(load_schema())


def test_minimal_document_passes():
    assert validate(minimal_doc()) == []


def test_table_without_status_is_rejected():
    doc = minimal_doc()
    del doc["tables"][0]["status"]
    errors = validate(doc)
    assert errors and any("status" in e for e in errors)


def test_table_status_is_one_of_three_values():
    schema = load_schema()
    assert schema["$defs"]["table"]["properties"]["status"]["enum"] == ["ok", "low_confidence", "failed"]
    doc = minimal_doc()
    doc["tables"][0]["status"] = "empty"
    assert validate(doc)


def test_failed_table_must_have_no_cells_and_ok_table_must_have_cells():
    failed = minimal_doc()
    failed["tables"][0].update({"status": "failed", "method": "none", "cells": [], "n_rows": 0, "n_cols": 0})
    assert validate(failed) == []
    swallowed = minimal_doc()
    swallowed["tables"][0].update({"cells": [], "n_rows": 0, "n_cols": 0})  # status=ok 인 빈 표
    assert validate(swallowed)
    failed_with_cells = minimal_doc()
    failed_with_cells["tables"][0]["status"] = "failed"
    assert validate(failed_with_cells)


@pytest.mark.parametrize("field", ["text_layer", "page"])
def test_page_requires_text_layer(field):
    doc = minimal_doc()
    del doc["pages"][0][field]
    assert validate(doc)


def test_block_kind_and_required_payload():
    doc = minimal_doc()
    doc["blocks"][0]["kind"] = "figure"
    assert validate(doc)
    para = minimal_doc()
    para["blocks"][0] = {
        "id": "p1-b1",
        "kind": "paragraph",
        "page": 1,
        "bbox": [0, 0, 1, 1],
        "order": 1,
        "section_id": None,
    }
    assert validate(para)  # 문단에는 text 가 있어야 한다
    para["blocks"][0]["text"] = "본문"
    assert validate(para) == []


def test_ocr_or_llm_flag_cannot_be_true():
    doc = minimal_doc()
    doc["parser"]["ocr_used"] = True
    assert validate(doc)


def test_parser_output_passes_schema(tmp_path, synthetic_ruled_page):
    pdf = tmp_path / "synthetic_ruled.pdf"
    synthetic_ruled_page.parent.save(pdf)
    doc = parse_pdf(pdf)
    assert validate(doc) == []
    assert len(doc["tables"]) == 1 and doc["tables"][0]["status"] == "ok"
    assert [b["kind"] for b in doc["blocks"]] == ["table"]


def test_parser_output_with_failed_table_passes_schema(tmp_path):
    doc = pdfbuild.Doc()
    page = doc.new_page(width=300, height=200)
    for i, (name, a, b) in enumerate((("Item", "2023", "2024"), ("Alpha", "10", "11"), ("Beta", "20", "21"))):
        put(page, 40, 60 + 14 * i, name)
        put(page, 180, 60 + 14 * i, a, right=True)
        put(page, 240, 60 + 14 * i, b, right=True)
        hline(page, 40, 240, 64 + 14 * i)
    hline(page, 40, 240, 50)
    pdf = tmp_path / "synthetic_full_width_rules.pdf"
    doc.save(pdf)
    parsed = parse_pdf(pdf, strategy="lines")
    assert validate(parsed) == []
    assert [(t["status"], t["method"], t["cells"]) for t in parsed["tables"]] == [("failed", "none", [])]
