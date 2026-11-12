"""쪽 글 어댑터 `drafting-blocks@1`(밴드 RP2a ②, 처분 ③ 가) — core 문서 산출물의 읽기 뷰(DocArtifactView)를 쪽 글
목록으로 편다. 순수다(django 0 — core/documents/view.py 는 표준 라이브러리만).

    page_texts(view)    쪽 1..마지막 쪽마다 글 하나. 쪽 안은 body 블록을 읽는 차례(order)대로 빈 줄로 잇는다:
                        문단·제목 = 블록 글 · 표 = 행마다 `| a | b |`(칸 글 + 그 칸의 각주 표시, 칸 안 `|` → `\\|`,
                        줄바꿈 → 공백, 칸이 다 빈 행은 버림). 머리글·꼬리말(region header·footer)은 뺀다.
                        글자 층 없는 쪽(text_layer none)·분해에 없는 쪽은 빈 글
    pages_sha256(texts) 쪽 글 목록의 지문 — json.dumps(ensure_ascii=False, separators=(",", ":")) 의 UTF-8 sha256
                        (흉내 이스케이프·자르기 전. 같으면 쪽 글이 같다 — RP2c 재사용 열쇠)
"""

import hashlib
import json
from collections.abc import Sequence
from typing import Final

from esgapi.core.documents.view import DocArtifactView, Table

ADAPTER: Final = "drafting-blocks@1"
JOIN: Final = "\n\n"
NO_TEXT: Final = "none"


def _cell(text: str, marks: Sequence[str]) -> str:
    joined = text + "".join(marks)
    return " ".join(joined.replace("|", "\\|").splitlines())


def table_lines(table: Table) -> list[str]:
    marks: dict[tuple[int, int], list[str]] = {}
    for mark in table.footnote_marks:
        marks.setdefault((mark.row, mark.col), []).append(mark.mark)
    lines: list[str] = []
    for r, row in enumerate(table.cells):
        cells = [_cell(text, marks.get((r, c), ())) for c, text in enumerate(row)]
        if any(cell.strip() for cell in cells):
            lines.append("| " + " | ".join(cells) + " |")
    return lines


def _page_text(view: DocArtifactView, page: int) -> str:
    parts: list[str] = []
    for block in view.body_blocks(page):
        if block.kind == "table":
            table = None if block.table_id is None else view.table(block.table_id)
            text = "" if table is None else "\n".join(table_lines(table))
        else:
            text = block.text.strip()
        if text:
            parts.append(text)
    return JOIN.join(parts)


def page_texts(view: DocArtifactView) -> list[str]:
    found = view.pages()
    last = max([view.page_count, *(p.page for p in found)], default=0)
    present = {p.page for p in found if p.text_layer != NO_TEXT}
    return [_page_text(view, n) if n in present else "" for n in range(1, last + 1)]


def pages_sha256(texts: Sequence[str]) -> str:
    dumped = json.dumps(list(texts), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()
