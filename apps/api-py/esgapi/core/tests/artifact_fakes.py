"""문서 산출물(core.doc-artifact@1)의 시험 재료(밴드 RP2a ①). 지어낸 값만 — 실제 보고서·기업명 0.

    fake_document(sha256, …) · fake_places(sha256, …)   계약의 꼴 검사를 지나는 파서 출력 dict(판 1·2)
    block(…) · table(…) · section(…) · container(…)      그 안의 조각
    parsed_for(pdf, …)                                  FakeParser 의 표에 넣을 Parsed(원본 sha256 을 셈)
    FakeArtifactView.from_dicts(document, char_places)  지어낸 dict 로 짓는 읽기 뷰 — selectors.artifact_view 와 같은 꼴

모듈의 시험(RP2a ② drafting·RP2b)은 이것으로 선다. 다른 모듈의 시험 재료를 베끼지 않는다.
"""

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from esgapi.core.documents.contract import UNIT
from esgapi.core.documents.view import DocArtifactView
from esgapi.core.resources.ports.parser import Parsed

PARSER_VERSION = "0.1.0"


def _parser(layout: int, *, document: bool) -> dict[str, Any]:
    parser: dict[str, Any] = {"name": "docparse", "version": PARSER_VERSION, "table_strategy": "auto"}
    if document:
        parser |= {"llm_used": False, "ocr_used": False}
    if layout != 1:
        parser["layout"] = layout  # 판 1 은 칸이 없다(파서 스키마)
    return parser


def section(
    section_id: str, title: str | None, *, level: int = 1, page_start: int = 1, page_end: int = 1
) -> dict[str, Any]:
    return {
        "id": section_id,
        "title": title,
        "level": level,
        "page_start": page_start,
        "page_end": page_end,
        "basis": "pdf_outline" if title else "no_title_found",
    }


def block(
    block_id: str,
    text: str = "",
    *,
    page: int = 1,
    order: int = 1,
    kind: str = "paragraph",
    region: str | None = "body",
    section_id: str | None = None,
    table_id: str | None = None,
    bbox: Sequence[float] = (10.0, 10.0, 100.0, 20.0),
) -> dict[str, Any]:
    found: dict[str, Any] = {
        "id": block_id,
        "kind": kind,
        "page": page,
        "bbox": list(bbox),
        "order": order,
        "section_id": section_id,
    }
    if kind == "table":
        found["table_id"] = table_id
    else:
        found["text"] = text
    if region is not None:
        found["region"] = region
    return found


def table(
    table_id: str,
    cells: Sequence[Sequence[str]],
    *,
    page: int = 1,
    header_rows: Sequence[int] = (0,),
    header_cols: Sequence[int] = (0,),
    footnote_marks: Sequence[tuple[int, int, str]] = (),
) -> dict[str, Any]:
    return {
        "id": table_id,
        "page": page,
        "bbox": [10.0, 30.0, 190.0, 90.0],
        "n_rows": len(cells),
        "n_cols": max((len(row) for row in cells), default=0),
        "cells": [list(row) for row in cells],
        "header": {"rows": list(header_rows), "cols": list(header_cols), "basis": "rows_before_first_numeric_row"},
        "method": "lines",
        "status": "ok",
        "notes": [],
        "footnote_marks": [{"row": r, "col": c, "mark": m} for r, c, m in footnote_marks],
    }


def fake_document(
    sha256: str,
    *,
    layout: int = 2,
    page_count: int = 1,
    blocks: Sequence[Mapping[str, Any]] = (),
    tables: Sequence[Mapping[str, Any]] = (),
    sections: Sequence[Mapping[str, Any]] = (),
    no_text_pages: Sequence[int] = (),
) -> dict[str, Any]:
    """판 `layout` 의 문서 모델. 쪽은 1..page_count 전부(no_text_pages 는 text_layer none)."""
    return {
        "schema_version": "0.1",
        "source": {"file_name": "document.pdf", "sha256": sha256, "page_count": page_count},
        "parser": _parser(layout, document=True),
        "pages": [
            {
                "page": n,
                "width": 595.0,
                "height": 842.0,
                "text_layer": "none" if n in no_text_pages else "present",
                "char_count": 0 if n in no_text_pages else 10,
                "image_coverage": 0.0,
                "columns": 1,
                "notes": [],
            }
            for n in range(1, page_count + 1)
        ],
        "sections": [dict(s) for s in sections],
        "blocks": [dict(b) for b in blocks],
        "tables": [dict(t) for t in tables],
    }


def container(
    container_id: str, runs: Sequence[Mapping[str, Any]], *, page: int = 1, kind: str = "block"
) -> dict[str, Any]:
    return {
        "id": container_id,
        "kind": kind,
        "page": page,
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "runs": [dict(r) for r in runs],
    }


def run(start: int, y0: float, y1: float, x0: Sequence[float], x1: Sequence[float]) -> dict[str, Any]:
    return {"start": start, "y0": y0, "y1": y1, "x0": list(x0), "x1": list(x1)}


def fake_places(
    sha256: str, *, layout: int = 2, page_count: int = 1, containers: Sequence[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "source": {"file_name": "document.pdf", "sha256": sha256, "page_count": page_count},
        "parser": _parser(layout, document=False),
        "unit": UNIT,
        "containers": [dict(c) for c in containers],
        "unlinked": [],
    }


def fake_chart_labels(
    sha256: str,
    *,
    charts: Sequence[Mapping[str, Any]] = (),
    words: Sequence[Mapping[str, Any]] = (),
    page_count: int = 1,
) -> dict[str, Any]:
    """도표 라벨 0.1(파서 chartLabels 의 꼴, 밴드 CHL1). 도표·낱말은 지어낸 것을 그대로 싣는다."""
    return {
        "schema_version": "0.1",
        "source": {"file_name": "document.pdf", "sha256": sha256, "page_count": page_count},
        "llm_used": False,
        "ocr_used": False,
        "charts": [dict(c) for c in charts],
        "words": [dict(w) for w in words],
        "unlinked": [],
        "place_count": len(words),
    }


def parsed_for(
    pdf: bytes,
    *,
    layout: int = 2,
    page_count: int = 1,
    chart_labels: Mapping[str, Any] | None = None,
    **document: Any,
) -> Parsed:
    """원본 바이트의 sha256 으로 지은 Parsed(FakeParser 의 표 값). document 칸은 fake_document 에 넘긴다.
    chart_labels 는 그대로 싣는다(None = 파서가 내지 않음 — CHL1)."""
    sha = hashlib.sha256(pdf).hexdigest()
    return Parsed(
        document=fake_document(sha, layout=layout, page_count=page_count, **document),
        char_places=fake_places(sha, layout=layout, page_count=page_count),
        chart_labels=None if chart_labels is None else dict(chart_labels),
    )


class FakeArtifactView(DocArtifactView):
    """지어낸 dict 로 짓는 뷰. selectors.artifact_view 가 돌려주는 것과 같은 꼴(같은 클래스를 잇는다)."""

    @classmethod
    def from_dicts(
        cls,
        document: Mapping[str, Any],
        char_places: Mapping[str, Any] | None = None,
        *,
        chart_labels: Mapping[str, Any] | None = None,
        artifact_id: int = 1,
    ) -> "FakeArtifactView":
        """chart_labels=None 은 「칸 없음」(chart_labels() 가 None)이다 — DocArtifactView 의 기본값(「안 실음」)과
        일부러 다르다(CHL1 2-2)."""
        return cls(artifact_id=artifact_id, document=document, char_places=char_places, chart_labels=chart_labels)
