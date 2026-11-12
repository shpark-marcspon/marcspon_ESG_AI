"""PDF 하나를 문서 모델(dict)로 분해한다. 상태 없음: 입력은 파일 경로, 출력은 dict."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from . import __version__, annotate, charplaces, charts
from .blocks import body_font_size, build_text_blocks, classify
from .config import CHARTS_SCHEMA_PATH, PLACES_SCHEMA_PATH, SCHEMA_PATH
from .engine import PdfOpenError, open_pdf
from .layout import page_chunks
from .reading_order import reading_order
from .sections import page_title, sections_from_outline, sections_from_titles
from .tables import extract_tables

SCHEMA_VERSION = "0.1"
# 분해 판. 1 = 기본(그린워싱 등이 쓰는 판, 산출 바이트를 바꾸지 않는다). 2 = 번역 판: 머리글·꼬리말 띠(`region`)와
# 내용 해시 키(`key`)를 블록에 싣고 `parser.layout` 을 적는다. 판마다 따로 켜는 인자는 두지 않는다(다음 손질은 3 으로).
LAYOUTS = (1, 2)
MAX_RULE_SEGMENTS = 8000  # 이보다 괘선 토막이 많은 쪽(벡터 그림)은 괘선 기반을 건너뛰고 그 사실을 적는다


class ParseError(Exception):
    pass


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate(doc):
    """스키마 위반 메시지 목록 (없으면 빈 목록)."""
    v = Draft202012Validator(load_schema())
    return [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in v.iter_errors(doc)]


def validate_places(places):
    """글자 자리(곁 파일)의 스키마 위반 메시지 목록."""
    v = Draft202012Validator(json.loads(PLACES_SCHEMA_PATH.read_text(encoding="utf-8")))
    return [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in v.iter_errors(places)]


def _inside(c, box, pad=1.0):
    return box[0] - pad <= c.xc <= box[2] + pad and box[1] - pad <= c.yc <= box[3] + pad


def _image_coverage(page):
    area = 0.0
    for x0, y0, x1, y1 in page.get_image_boxes():
        area += max(0.0, x1 - x0) * max(0.0, y1 - y0)
    return round(min(1.0, area / (page.rect.width * page.rect.height)), 3)


def _table_strategy_for(page, strategy):
    if strategy == "text":
        return strategy, None
    n = sum(len(d["items"]) for d in page.get_drawings())
    if n > MAX_RULE_SEGMENTS:
        return "text", f"lines_strategy_skipped:too_many_drawing_items:{n}"
    return strategy, None


def parse_pdf(path, pages=None, strategy="auto", dedupe_overdrawn=False, engine=None, layout=1):
    """pages: 1부터 세는 쪽 번호 목록(None 이면 전 쪽).

    dedupe_overdrawn=True 면 같은 글자가 같은 자리에 또 그려진 것을 한 번만 뽑는다(`layout.overdrawn_spans`).
    버린 span 의 수는 쪽의 `notes` 에 `overdrawn_spans_dropped:<수>` 로 남는다. 기본은 끔이고 끄면 산출이 그대로다.
    layout: 분해 판(`LAYOUTS`). 기본 1 은 산출이 그대로다. 2 는 번역 판이다(밴드 TRD1, README 「분해 판」).
    """
    return _parse(path, pages, strategy, False, dedupe_overdrawn, engine, layout)[0]


def parse_pdf_places(path, pages=None, strategy="auto", dedupe_overdrawn=False, engine=None, layout=1):
    """(문서 모델, 글자 자리). 문서 모델은 `parse_pdf` 의 것과 같다. 글자 자리의 형식은
    `schemas/char-places.schema.json`."""
    return _parse(path, pages, strategy, True, dedupe_overdrawn, engine, layout)


def parse_opened_places(doc, path, pages=None, strategy="auto", dedupe_overdrawn=False, layout=1):
    """`parse_pdf_places` 와 같되 이미 연 문서를 받는다(닫는 것은 부르는 쪽). 산출은 경로 입구와 같다.

    path: 그 문서의 파일. `source` 의 이름과 해시를 여기서 읽는다(PDF 로 다시 열지 않는다).
    서비스(`app.py`)가 암호·쪽 수를 보려고 연 문서를 그대로 넘겨 PDF 를 한 번만 연다(밴드 PX2).
    """
    return _parse_opened(doc, Path(path), pages, strategy, True, dedupe_overdrawn, layout)


def validate_charts(labels):
    """도표 라벨(`schemas/chart-labels.schema.json`)의 위반 메시지 목록."""
    v = Draft202012Validator(json.loads(CHARTS_SCHEMA_PATH.read_text(encoding="utf-8")))
    return [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in v.iter_errors(labels)]


def label_charts(doc, document):
    """이미 연 PDF(`doc`)와 그 문서의 판 2 문서 모델로 도표 라벨(dict)을 낸다(밴드 CHL1). 다시 열지 않는다.

    규칙은 `charts.label_document` 그대로다. 낱말 자리(places)는 싣지 않는다(낱말이 그릇·좌표를 가진다).
    산출은 JSON 값으로 한 번 풀어 다시 짓는다(쓰는 바이트는 같다): 범례의 (이름, 색) 튜플이 배열이 되어 스키마 검사가
    JSON 과 같은 것을 보고, `source` 가 문서 모델의 객체와 갈린다(한쪽 이름을 고쳐도 다른 쪽이 따라 바뀌지 않게).
    판 1 의 문서 모델에는 붙이지 않는다(`ParseError`).
    """
    if document["parser"].get("layout") != 2:
        raise ParseError("도표 라벨은 분해 판 2 의 문서 모델에만 붙인다")
    labels, _places = charts.label_document(doc, document)
    return json.loads(json.dumps(labels, ensure_ascii=False))


def parse_pdf_charts(path, pages=None, strategy="auto", dedupe_overdrawn=False, engine=None, want_places=True):
    """판 2 로 분해하고 같은 열린 PDF 로 도표 라벨까지 낸다. CLI 가 쓴다.

    (문서 모델, 글자 자리 또는 None, 도표 라벨).
    """
    path = Path(path)
    if not path.is_file():
        raise ParseError(f"파일이 없다: {path}")
    try:
        doc = open_pdf(path, engine)
    except PdfOpenError as e:
        raise ParseError(f"PDF 를 열 수 없다: {path}: {e}") from e
    with doc:
        document, places = _parse_opened(doc, path, pages, strategy, want_places, dedupe_overdrawn, 2)
        return document, places, label_charts(doc, document)


def _parse(path, pages, strategy, want_places, dedupe_overdrawn=False, engine=None, layout=1):
    path = Path(path)
    if not path.is_file():
        raise ParseError(f"파일이 없다: {path}")
    try:
        doc = open_pdf(path, engine)
    except PdfOpenError as e:
        raise ParseError(f"PDF 를 열 수 없다: {path}: {e}") from e
    with doc:
        return _parse_opened(doc, path, pages, strategy, want_places, dedupe_overdrawn, layout)


def _parse_opened(doc, path, pages, strategy, want_places, dedupe_overdrawn, layout=1):
    if layout not in LAYOUTS:
        raise ParseError(f"알 수 없는 분해 판: {layout!r} ({', '.join(map(str, LAYOUTS))} 중 하나)")
    if doc.needs_pass:
        raise ParseError(f"암호가 걸린 PDF 다: {path}")
    n = len(doc)
    wanted = list(pages) if pages else list(range(1, n + 1))
    bad = [p for p in wanted if not 1 <= p <= n]
    if bad:
        raise ParseError(f"쪽 번호가 범위 밖이다 (1~{n}): {bad}")
    out_pages, blocks, tables, titles = [], [], [], []
    per_page = []
    for pno in wanted:
        page = doc[pno - 1]
        chunks, dropped = page_chunks(page, glyphs=want_places, dedupe_overdrawn=dedupe_overdrawn)
        notes = [f"{k}:{v}" for k, v in dropped.items() if v]
        chars = sum(len(c.text.replace(" ", "")) for c in chunks)
        has_text = chars > 0
        page_tables = []
        if has_text:
            used, note = _table_strategy_for(page, strategy)
            if note:
                notes.append(note)
            page_tables = (
                extract_tables(page, used, chunks=chunks, notes=notes, layout=layout)
                if layout >= 2
                else extract_tables(page, used, chunks=chunks, notes=notes)
            )
        if layout >= 2:
            # 번역 판: 표 상자 안이라도 어느 칸에도 들지 않은 조각(실패 표 안의 글 포함)은 글 블록으로 간다.
            # 칸에 든 조각은 상자 밖이어도 글 블록에 넣지 않는다(두 번 셈 0). 셈의 정의는 `balance.char_balance`.
            placed = {id(c) for t in page_tables for cs in t.cell_chunks.values() for c in cs}
            rest = [c for c in chunks if id(c) not in placed]
        else:
            rest = [c for c in chunks if not any(_inside(c, t.bbox) for t in page_tables)]
        text_blocks = build_text_blocks(rest, layout=layout) if layout >= 2 else build_text_blocks(rest)
        per_page.append((pno, page_tables, text_blocks))
        titles.append((pno, page_title(chunks, page.rect.height)))
        out_pages.append(
            {
                "page": pno,
                "width": round(page.rect.width, 1),
                "height": round(page.rect.height, 1),
                # 텍스트 계층이 없는 쪽(스캔본)은 none 으로 표시만 한다. OCR 을 하지 않는다.
                "text_layer": "present" if has_text else "none",
                "char_count": chars,
                "image_coverage": _image_coverage(page),
                "columns": 0,
                "notes": notes,
            }
        )
    toc = doc.get_toc()
    sections = sections_from_outline(toc, n) if toc else sections_from_titles(titles)
    body = body_font_size([b for _p, _t, bs in per_page for b in bs])

    def section_of(pno):
        hit = [s for s in sections if s["page_start"] <= pno <= s["page_end"]]
        return max(hit, key=lambda s: (s["level"], s["page_start"]))["id"] if hit else None

    containers, unlinked = [], []

    def place(cid, kind, pno, text, chunks):
        if not want_places or not text:
            return
        made, failed = charplaces.build_container(cid, kind, pno, text, chunks)
        (containers if made else unlinked).append(made or failed)

    for (pno, page_tables, text_blocks), meta in zip(per_page, out_pages, strict=False):
        items = [("table", t) for t in page_tables] + [("text", b) for b in text_blocks]
        boxes = [(it.bbox if kind == "table" else it["bbox"]) for kind, it in items]
        order, meta["columns"] = reading_order(boxes, meta["height"])
        t_no = 0
        for rank, idx in enumerate(order, 1):
            kind, it = items[idx]
            block = {"id": f"p{pno}-b{rank}", "page": pno, "order": rank, "section_id": section_of(pno)}
            if kind == "table":
                t_no += 1
                tid = f"p{pno}-t{t_no}"
                block.update({"kind": "table", "bbox": it.bbox, "table_id": tid})
                tables.append(
                    {
                        "id": tid,
                        "page": pno,
                        "bbox": it.bbox,
                        "n_rows": it.n_rows,
                        "n_cols": it.n_cols,
                        "cells": it.grid,
                        "header": it.header,
                        "method": it.method,
                        "status": it.status,
                        "notes": it.notes,
                        "footnote_marks": it.footnote_marks,
                    }
                )
                for i, row in enumerate(it.grid):
                    for j, text in enumerate(row):
                        place(f"{tid}:r{i}c{j}", "cell", pno, text, it.cell_chunks.get((i, j), []))
            else:
                block.update(
                    {
                        "kind": classify(it, body),
                        "bbox": it["bbox"],
                        "text": it["text"],
                        "font_size": round(it["size"], 1),
                    }
                )
                place(block["id"], "block", pno, it["text"], it["chunks"])
            blocks.append(block)
    source = {"file_name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "page_count": n}
    marked = {"layout": layout} if layout >= 2 else {}  # 기본 판(1)에는 그 칸이 없다
    if layout >= 2:
        annotate.annotate(blocks, tables, out_pages)
    places = None
    if want_places:
        places = {
            "schema_version": charplaces.SCHEMA_VERSION,
            "source": source,
            "parser": {"name": "docparse", "version": __version__, "table_strategy": strategy, **marked},
            "unit": "utf16",
            "containers": containers,
            "unlinked": unlinked,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "parser": {
            "name": "docparse",
            "version": __version__,
            "table_strategy": strategy,
            "llm_used": False,
            "ocr_used": False,
            **marked,
        },
        "pages": out_pages,
        "sections": sections,
        "blocks": blocks,
        "tables": tables,
    }, places
