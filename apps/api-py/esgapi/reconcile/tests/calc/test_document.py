"""문서 모델 검증의 출력 — `validate_document` 가 내는 `DocumentOk(DocModel(...))` 전체를 == 로 견준다.

`calc/test_document_ts.py` 는 갯수·`isinstance`·두 문서의 == 만 본다. 여기서는 칸마다 서로 다르고 기본값이 아닌
값을 넣은 최소 문서 하나의 결과 전체를 견준다(MARC-ENT-280, 밴드 NK1). 입력 dict 는 시험 안에서 만든다.

★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

from typing import Any

from esgapi.reconcile.calc.document import DocumentInvalid, DocumentOk, validate_document
from esgapi.reconcile.calc.types import DocBlock, DocModel, DocPage, DocSource, DocTable, FootnoteMark, GridHeader

Json = Any


def raw_document() -> Json:
    return {
        "schema_version": "0.1",
        "source": {"file_name": "n.synthetic.pdf", "sha256": "ab" * 32, "page_count": 2},
        "pages": [
            {"page": 1, "height": 800, "text_layer": "present"},
            {"page": 2, "height": 842.5, "text_layer": "none"},
        ],
        "blocks": [
            {"id": "p1-b1", "kind": "heading", "page": 1, "bbox": [10, 20, 300, 40], "order": 1, "text": "배출 현황"},
            {"id": "p1-b2", "kind": "paragraph", "page": 1, "bbox": [11, 50, 310, 70], "order": 2, "text": "12톤"},
            {"id": "p2-b1", "kind": "table", "page": 2, "bbox": [1.5, 2, 30, 40], "order": 3, "table_id": "p2-t1"},
        ],
        "tables": [
            {
                "id": "p2-t1",
                "page": 2,
                "cells": [["구분", "2024"], ["배출", "12"]],
                "header": {"rows": [0], "cols": [0], "basis": "손으로 정함"},
                "method": "text",
                "status": "low_confidence",
                "footnote_marks": [{"row": 1, "col": 2, "mark": "a)"}],
            }
        ],
    }


def test_every_field_of_a_valid_document_reaches_the_model() -> None:
    assert validate_document(raw_document()) == DocumentOk(
        DocModel(
            source=DocSource("n.synthetic.pdf", "ab" * 32, 2),
            pages=(DocPage(1, 800, "present"), DocPage(2, 842.5, "none")),
            blocks=(
                DocBlock("p1-b1", "heading", 1, (10, 20, 300, 40), 1, "배출 현황", None),
                DocBlock("p1-b2", "paragraph", 1, (11, 50, 310, 70), 2, "12톤", None),
                DocBlock("p2-b1", "table", 2, (1.5, 2, 30, 40), 3, None, "p2-t1"),
            ),
            tables=(
                DocTable(
                    id="p2-t1",
                    page=2,
                    cells=(("구분", "2024"), ("배출", "12")),
                    header=GridHeader((0,), (0,), "손으로 정함"),
                    method="text",
                    status="low_confidence",
                    footnote_marks=(FootnoteMark(1, 2, "a)"),),
                ),
            ),
        )
    )


def test_a_boolean_is_not_a_number() -> None:
    raw = raw_document()
    raw["pages"][1]["height"] = True
    assert validate_document(raw) == DocumentInvalid("pages[1].height", "수여야 한다")
