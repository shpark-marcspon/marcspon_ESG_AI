"""엔진이 분해 규칙에 건네는 자료의 꼴. PDF 라이브러리의 타입을 쓰지 않는다 (좌표는 pt, 쪽의 왼쪽 위가 원점, y 는
아래로).

분해 규칙이 엔진에서 받는 것:

- 문서: `len(doc)`, `doc[i]`(쪽, 0부터), `doc.needs_pass`, `doc.get_toc()` → [[단계, 제목, 쪽 번호(1부터, 없으면 -1)]].
- 쪽:
  - `page.number`(0부터), `page.rect`(`Rect`. 쪽의 상자, 늘 (0, 0, 너비, 높이))
  - `page.get_text_blocks(chars=False)` → [{"lines": [{"dir": (dx, dy), "spans": [span]}]}]
    span = {"text", "bbox": (x0, y0, x1, y1), "size"} 이고 chars=True 면 "text" 대신 "chars": [{"c", "bbox"}].
  - `page.get_words()` → [(x0, y0, x1, y1, 낱말, 블록 번호, 줄 번호, 낱말 번호)]
  - `page.get_drawings()` → [{"items", "rect": Rect, "color", "fill", "width", "fill_opacity"}]
    items 의 항목: ("l", Point, Point) 선 / ("re", Rect) 네모 / ("qu", Rect) 사각(네 꼭짓점을 두른 상자) /
    ("c", Point × 4) 곡선.
    color·fill 은 (r, g, b) 0..1 이거나 None.
  - `page.get_image_boxes()` → [(x0, y0, x1, y1)] 쪽에 놓인 그림의 상자
  - `page.render_png(path, dpi, clip=None)`
"""

from typing import NamedTuple


class Point(NamedTuple):
    x: float
    y: float


class Rect:
    """상자. `width`·`height` 는 뒤집힌 상자에서 0 이고, `normalize()` 는 제자리에서 바로 세운다."""

    __slots__ = ("x0", "x1", "y0", "y1")

    def __init__(self, *args):
        if len(args) == 1:
            args = tuple(args[0])
        self.x0, self.y0, self.x1, self.y1 = (float(v) for v in args)

    def __iter__(self):
        return iter((self.x0, self.y0, self.x1, self.y1))

    def __getitem__(self, i):
        return (self.x0, self.y0, self.x1, self.y1)[i]

    def __len__(self):
        return 4

    def __eq__(self, other):
        return tuple(self) == tuple(other)

    def __repr__(self):
        return f"Rect({self.x0}, {self.y0}, {self.x1}, {self.y1})"

    @property
    def width(self):
        return max(0, self.x1 - self.x0)

    @property
    def height(self):
        return max(0, self.y1 - self.y0)

    def normalize(self):
        if self.x1 < self.x0:
            self.x0, self.x1 = self.x1, self.x0
        if self.y1 < self.y0:
            self.y0, self.y1 = self.y1, self.y0
        return self


class PdfOpenError(Exception):
    """PDF 를 열지 못했다 (깨진 파일, 지원하지 않는 형식)."""
