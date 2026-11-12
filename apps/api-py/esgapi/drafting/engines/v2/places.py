"""출처 상자(결과 drafting.bullets@2 의 source — 결정 MARC-ENT-514 2번·512 ③). 뷰는 글자 자리를 실은 것(places=True).

source(block, index, view, document_id)
    blockBox = 블록 bbox(표면 표 bbox). sentence = 문단이면 view.boxes(블록 id, 문장 범위) · 표 행이면 그 행 칸마다
    view.boxes(<표id>:r<R>c<C>, 0, 칸 글 UTF-16 길이) 의 합집합 하나(§2-0 ④). index 가 None 이거나 상자가 None·빈
    것이면 sentence null(못 냄 — 경고 0, null 이 말한다).
"""

from collections.abc import Sequence
from typing import Any

from .material import TABLE, Box, GivenBlock, ViewLike


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _union(boxes: Sequence[Box]) -> list[list[float]]:
    if not boxes:
        return []
    return [
        [
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        ]
    ]


def _boxes(block: GivenBlock, index: int, view: ViewLike) -> list[list[float]]:
    if block.kind == TABLE:
        found: list[Box] = []
        for col, text in enumerate(block.cells.get(index, ())):
            found += view.boxes(f"{block.id}:r{index}c{col}", 0, _utf16_length(text)) or ()
        return _union(found)
    span = block.spans.get(index)
    if span is None:
        return []
    return [list(box) for box in view.boxes(block.id, span.start, span.end) or ()]


def source(block: GivenBlock, index: int | None, view: ViewLike, document_id: int) -> dict[str, Any]:
    boxes = [] if index is None else _boxes(block, index, view)
    return {
        "documentId": document_id,
        "blockId": block.id,
        "page": block.page,
        "blockBox": list(block.bbox),
        "sentence": {"index": index, "boxes": boxes} if boxes else None,
    }
