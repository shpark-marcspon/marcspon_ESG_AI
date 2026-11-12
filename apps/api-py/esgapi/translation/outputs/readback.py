# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
"""Word 바이트 → 읽기 JSON(처분 ⑬). 대조 명령 word_dump 와 시험 S2·S3 이 같이 쓰는 정본 하나다 — TR1-o 는 코랩 셀
54·63 이 지은 Word 를 같은 꼴로 읽어 견준다.

★ 우리가(또는 TR1-o 가 코랩으로) 지은 바이트만 연다 — 방어가 없다. 올린(남이 준) docx 는 `tools/docx_reader.read_docx`
로만 연다. 이 모듈을 import 하는 제품 모듈은 word_dump 하나다(tests/test_docx_imports.py — 가지 리뷰 M1).

몸의 직속 문단·표를 차례대로:
- 문단 `{"type": "paragraph", "spaceAfterPt", "runs": [run…]}` — run 은 `text`·`font`·`eastAsiaFont`·`sizePt`·`color`
  (16진, 없으면 null)·`bold`·`italic`(null = 상속)·`highlight`(WD_COLOR_INDEX 이름, 없으면 null)·`pageBreak`(run 안
  `w:br w:type="page"` — python-docx 의 `contains_page_break` 는 렌더된 쪽 나눔 표시라 쓰지 않는다).
- 표 `{"type": "table", "style", "rows": [[{"text", "fill"}…]…]}` — `fill` 은 칸 음영(없으면 null). 칸은 python-docx
  `row.cells` 그대로(병합 칸은 되풀이 — W12).
크기는 python-docx 가 읽은 pt(`w:sz` 반 포인트 — Pt(9.3) 은 9.0). 만든 시각 등 바이트마다 다른 것은 싣지 않는다.
"""

import io
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from docx.text.run import Run


def read_word(data: bytes) -> dict[str, Any]:
    document = Document(io.BytesIO(data))
    blocks: list[dict[str, Any]] = []
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            blocks.append(_paragraph(item))
        else:
            blocks.append(_table(item))
    return {"blocks": blocks}


def _paragraph(paragraph: Paragraph) -> dict[str, Any]:
    after = paragraph.paragraph_format.space_after
    return {
        "type": "paragraph",
        "spaceAfterPt": None if after is None else after.pt,
        "runs": [_run(run) for run in paragraph.runs],
    }


def _run(run: Run) -> dict[str, Any]:
    font = run.font
    size = font.size
    props = run.element.rPr
    fonts = None if props is None else props.rFonts
    highlight = font.highlight_color
    return {
        "text": run.text,
        "font": font.name,
        "eastAsiaFont": None if fonts is None else fonts.get(qn("w:eastAsia")),
        "sizePt": None if size is None else size.pt,
        "color": None if font.color.rgb is None else str(font.color.rgb),
        "bold": run.bold,
        "italic": run.italic,
        "highlight": None if highlight is None else highlight.name,
        "pageBreak": any(br.get(qn("w:type")) == "page" for br in run.element.iter(qn("w:br"))),
    }


def _table(table: Table) -> dict[str, Any]:
    style = table.style
    return {
        "type": "table",
        "style": None if style is None else style.name,
        "rows": [[_cell(cell) for cell in row.cells] for row in table.rows],
    }


def _cell(cell: _Cell) -> dict[str, Any]:
    props = cell._tc.tcPr
    shading = None if props is None else props.find(qn("w:shd"))
    return {"text": cell.text, "fill": None if shading is None else shading.get(qn("w:fill"))}
