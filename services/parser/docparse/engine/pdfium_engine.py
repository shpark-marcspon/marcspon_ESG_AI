"""pdfium 엔진 (pypdfium2). pymupdf 를 import 하지 않는다.

pdfium 은 낱 글자(글자, 원점, 상자, 글꼴, 행렬)와 낱 경로(점과 닫힘 표시, 채움·획)를 준다. 분해 규칙이 읽는 묶음
(줄·스팬, 낱말, 그리기 항목)은 여기서 다시 세운다. 문서나 쪽 번호에 기댄 예외는 없다.

줄·스팬·낱말·그리기 항목·책갈피·음영 상자(`CLEANROOM(PD1)` 자리)는 동작 명세 `band-handoffs/PD1-cleanroom-spec.md`,
`tests/test_engine.py`, PyMuPDF 를 돌려서 본 산출만 보고 썼다 (PyMuPDF·MuPDF 의 소스를 보지 않았다).

좌표: pdfium 은 PDF 사용자 공간(왼쪽 아래 원점, y 위로)을 준다. 여기서 CropBox 의 왼쪽 위를 원점으로, y 를 아래로
옮긴다.
/Rotate 는 `page.rect` 의 너비·높이에만 든다: 글자와 그림의 좌표는 돌리기 전의 것이다 (PyMuPDF 가 글과 그림을 읽을 때
쪽의 회전을 잠깐 0 으로 두는 것과 같게 했다. 돌아간 쪽에서는 그래서 `page.rect` 와 좌표가 어긋난다. 두 엔진 다 그렇다).
"""

import ctypes
import math
import struct
import zlib
from array import array
from collections import OrderedDict
from typing import cast

import pypdfium2 as pdfium
import pypdfium2.raw as C

from .types import PdfOpenError, Point, Rect

# 줄·공백·스팬·낱말의 문턱 (명세 3·4·5절). 값은 지어낸 PDF 로 PyMuPDF 를 돌려 경계를 재서 정했다
# (밴드 PD1 의 다시 쓰기. 잰 스크립트와 결과: out/band-PD1/rewrite/measure/). 틈·어긋남은 글자 크기의 배수다.
SPACE_GAP = 0.15  # 틈이 이 이상이면 공백을 지어 넣는다 (0.149 붙음 / 0.150 공백)
LINE_BREAK_GAP = 0.8  # 틈이 이 이상이거나 -이 이하이면 새 줄 (0.799 같은 줄 / 0.800 새 줄, 음수 쪽도 같다)
LINE_BREAK_SHIFT = 0.8  # 어긋남의 크기가 이 이상이면 새 줄 (0.799 / 0.800)
SAME_PLACE_REACH = 0.1  # 같은 글자의 원점이 가로·세로 모두 이 안이면 덧찍기 (0.099 버림 / 0.100 남김)
WIDE_SPACE_GAP = 0.3  # 지어 넣은 공백의 틈이 이것을 넘으면 따로 스팬 (0.300 한 스팬 / 0.301 따로. 명세의 1/3 과 다르다)
RAISED_SHIFT = 0.1  # 원점이 줄 머리 글자보다 이것(× 제 크기) 넘게 위면 올려 쓴 글자 (0.100 아님 / 0.101 올려 씀)
BLOCK_BREAK_SHIFT = 1.5  # 새 줄의 어긋남이 이것을 넘으면 새 블록 (1.500 같은 블록 / 1.505 새 블록)
BLOCK_INDENT = (
    0.5  # pt. 어긋남으로 끊긴 새 줄이 앞 줄의 머리보다 이것 넘게 오른쪽에서 시작하면 새 블록 (0.50 / 0.51. 명세에 없다)
)
# 앞 줄이 이 글자(숫자, 글머리표)로 시작하면 들여 쓴 다음 줄도 같은 블록에 남는다 (BMP 를 훑어 잰 집합. 명세에 없다)
LIST_MARKERS = frozenset(
    [
        0x2A,
        0xB7,
        0x2022,
        0x2023,
        0x2043,
        0x204C,
        0x204D,
        0x2219,
        0x25C9,
        0x25CB,
        0x25CF,
        0x25D8,
        0x25E6,
        0x2765,
        0x2767,
        0x29BE,
        0x29BF,
        *range(0x30, 0x3A),
        *range(0x2619, 0x2620),
        *range(0x2660, 0x2668),
    ]
)
SAME_DIRECTION_COS = 0.999  # 글자의 방향과 줄의 방향이 이루는 각의 코사인이 이 아래면 다른 방향 (2.56도 같은 줄 /
# 2.57도 새 블록. 명세에 없다)
SPACE_AFTER_BELOW = 0x700  # 앞 글자가 이 아래이거나
SPACE_AFTER_ZONE = (
    0x2000,
    0x20CF,
)  # 이 구역이면 틈에 공백을 짓는다 (U+06F9 지음 / U+0710 안 지음, U+20CF 지음 / U+2100 안 지음)
_SPACE = 0x20
_WORD_HEAD_SKIPPED = 0x200D  # 낱말의 머리에 올 수 없는 글자


def _breaks_word(code):
    """낱말을 가르는 글자인가 (U+0008~U+000D·U+0020·U+00A0·U+202A~U+202E 는 재서 확인, 그 밖의 U+0020 아래는 명세)."""
    return code <= _SPACE or code == 0xA0 or 0x202A <= code <= 0x202E


def _space_goes_after(code):
    return code != _SPACE and (code < SPACE_AFTER_BELOW or SPACE_AFTER_ZONE[0] <= code <= SPACE_AFTER_ZONE[1])


def _union(boxes):
    x0, y0, x1, y1 = zip(*boxes, strict=False)
    return (min(x0), min(y0), max(x1), max(y1))


# pdfium 이 뺀 공백을 되살릴 때의 어림 (`_blank_objects`, `_after_restored_space`). 명세의 밖이다.
DEFAULT_SPACE_WIDTH = 0.3  # 공백뿐인 글 객체의 너비를 어림할 글꼴 공백을 그 쪽에서 못 봤을 때 (글자 크기의 배수, 추정)
WIDE_SPACE_GUESS = 0.5  # 되살린 공백 뒤에 틈이 이만큼 더 있으면 넓은 공백(U+2003)이었다고 본다 (추정)

_PAGE_CACHE = 4
_TOC_MAX_DEPTH = 64  # 책갈피가 이보다 깊으면 돌고 도는 것으로 본다

_SEG_LINETO, _SEG_BEZIERTO, _SEG_MOVETO = C.FPDF_SEGMENT_LINETO, C.FPDF_SEGMENT_BEZIERTO, C.FPDF_SEGMENT_MOVETO


def _f32(values):
    """배정밀도 수를 단정밀도로 한 번 거친다 (PDF 엔진들은 좌표를 단정밀도로 셈한다)."""
    return array("f", values).tolist()


def _concat(m, n):
    """행렬 m 을 먼저, n 을 나중에 적용하는 행렬. (a, b, c, d, e, f): x' = a·x + c·y + e, y' = b·x + d·y + f."""
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (
        a * a2 + b * c2,
        a * b2 + b * d2,
        c * a2 + d * c2,
        c * b2 + d * d2,
        e * a2 + f * c2 + e2,
        e * b2 + f * d2 + f2,
    )


def _apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _page_matrix(crop, rotation):
    """(사용자 공간 → 쪽 좌표 행렬, 너비, 높이). crop = (왼, 아래, 오른, 위), rotation = 0·90·180·270."""
    base = {0: (1, 0, 0, -1), 90: (0, 1, 1, 0), 180: (-1, 0, 0, 1), 270: (0, -1, -1, 0)}[rotation % 360]
    m = (*base, 0.0, 0.0)
    xs, ys = zip(*(_apply(m, x, y) for x in (crop[0], crop[2]) for y in (crop[1], crop[3])), strict=False)
    return (*base, -min(xs), -min(ys)), max(xs) - min(xs), max(ys) - min(ys)


class _Char:
    """쪽의 글자 하나 (쪽 좌표: pt, 왼쪽 위 원점, y 아래로).

    c: 유니코드 번호 / box: (x0, y0, x1, y1) 글자의 상자 / ox, oy: 원점(바닥선 위의 시작 자리)
    size: 실효 크기(pt) / dx, dy: 글이 나아가는 방향(단위 벡터. 가로 글은 (1.0, 0.0))
    ex, ey: 끝점 = 원점에서 방향으로 글자의 너비만큼 간 자리(다음 글자가 이어질 자리)
    style: 스팬을 가르는 열쇠. 진짜 글자와 되살린 공백은 (글꼴 이름, 크기, r, g, b, a). 줄을 세우며 지어 넣는 글자의
    열쇠는 짓는 쪽이 정한다
    synthetic: PDF 에 없던, 엔진이 지어 넣은 글자인가 / obj: 글자가 든 글 객체의 차례 번호(같은 객체의 글자는 같다. 지어
    넣은 것은 None)
    blank_object: 줄에 넣을 글자가 아니라 「여기에 pdfium 이 뺀 공백이 있었다」는 표시인가. `_load_chars` 가 차례에 끼워
    준다.
        줄을 세우는 쪽은 이것을 `_restored_space` 에 건네기만 한다 (명세 3절 끝 「이음 약속」).
    """

    def __init__(self, c, box, ox, oy, size, dx, dy, ex, ey, style, synthetic=False, blank_object=False, obj=None):
        self.c, self.box, self.ox, self.oy, self.size = c, box, ox, oy, size
        self.dx, self.dy, self.ex, self.ey, self.style, self.synthetic = dx, dy, ex, ey, style, synthetic
        self.blank_object, self.obj = blank_object, obj


class Page:
    def __init__(self, doc, index):
        self.number = index
        self._page = doc._pdf[index]
        media = self._page.get_mediabox()
        crop = self._page.get_cropbox()
        crop = (max(crop[0], media[0]), max(crop[1], media[1]), min(crop[2], media[2]), min(crop[3], media[3]))
        if crop[2] <= crop[0] or crop[3] <= crop[1]:
            crop = media
        self._matrix, width, height = _page_matrix(crop, 0)
        self._content_size = tuple(_f32([width, height]))  # 글자·그림 좌표의 범위 (돌리기 전)
        _m, width, height = _page_matrix(crop, self._page.get_rotation())
        self._size = tuple(_f32([width, height]))
        self._objects = None
        self._lines = None

    @property
    def rect(self):
        return Rect(0.0, 0.0, self._size[0], self._size[1])

    def close(self):
        self._page.close()

    # ── 쪽의 객체: 글 객체의 차례, 경로, 그림 ──────────────────────────────

    def _load_objects(self):
        if self._objects is not None:
            return self._objects
        text_order, paths, images = {}, [], []
        mat = C.FS_MATRIX()
        left, bottom, right, top = (ctypes.c_float() for _ in range(4))

        def matrix_of(obj):
            C.FPDFPageObj_GetMatrix(obj, mat)
            return (mat.a, mat.b, mat.c, mat.d, mat.e, mat.f)

        def walk(count, get, holder, parent):
            for i in range(count(holder)):
                obj = get(holder, i)
                kind = C.FPDFPageObj_GetType(obj)
                if kind == C.FPDF_PAGEOBJ_TEXT:
                    text_order[ctypes.addressof(obj.contents)] = (len(text_order), obj, parent)
                elif kind == C.FPDF_PAGEOBJ_PATH:
                    paths.append((obj, _concat(matrix_of(obj), parent)))
                elif kind == C.FPDF_PAGEOBJ_IMAGE:
                    xs, ys = zip(
                        *(_apply(_concat(matrix_of(obj), parent), x, y) for x in (0, 1) for y in (0, 1)), strict=False
                    )
                    images.append(tuple(_f32([min(xs), min(ys), max(xs), max(ys)])))
                elif kind == C.FPDF_PAGEOBJ_SHADING and C.FPDFPageObj_GetBounds(obj, left, bottom, right, top):
                    # 음영(그라데이션)으로 칠한 자리도 그림으로 센다.
                    xs, ys = zip(
                        *(_apply(parent, x, y) for x in (left.value, right.value) for y in (bottom.value, top.value)),
                        strict=False,
                    )
                    images.append(_shading_image_box(*_f32([min(xs), min(ys), max(xs), max(ys)])))
                elif kind == C.FPDF_PAGEOBJ_FORM:
                    # 폼 안의 객체는 폼의 행렬을, 폼이 겹쳐 있으면 바깥 폼들의 행렬을 차례로 곱해야 쪽 좌표가 된다.
                    walk(C.FPDFFormObj_CountObjects, C.FPDFFormObj_GetObject, obj, _concat(matrix_of(obj), parent))

        walk(C.FPDFPage_CountObjects, C.FPDFPage_GetObject, self._page.raw, self._matrix)
        self._objects = (text_order, paths, images)
        return self._objects

    # ── 글자 ───────────────────────────────────────────────────────────────

    def _load_chars(self):
        """쪽의 글자를 내용 스트림의 차례로. pdfium 이 지어낸 공백·줄바꿈은 뺀다."""
        text_order = self._load_objects()[0]
        textpage = self._page.get_textpage()
        tp = textpage.raw
        try:
            n = C.FPDFText_CountChars(tp)
            rect, mat = C.FS_RECTF(), C.FS_MATRIX()
            ox, oy = ctypes.c_double(), ctypes.c_double()
            r, g, b, a = (ctypes.c_uint() for _ in range(4))
            name, flags = ctypes.create_string_buffer(256), ctypes.c_int()
            styles = {}  # 글 객체 → (차례, 크기, 방향, 스팬을 가르는 열쇠)
            found = []
            pm = self._matrix
            for i in range(n):
                obj = C.FPDFText_GetTextObject(tp, i)
                if not obj:
                    continue  # pdfium 이 지어낸 글자 (공백, 줄바꿈, 붙임표)
                key = ctypes.addressof(obj.contents)
                style = styles.get(key)
                if style is None:
                    C.FPDFText_GetMatrix(tp, i, mat)
                    font_size = C.FPDFText_GetFontSize(tp, i)
                    # 글자의 실효 크기 = 글꼴 크기 × 행렬의 배율. pdfium 의 글꼴 크기는 행렬을 품지 않는다 (Tf 의
                    # 값이다).
                    size = _f32([font_size * math.sqrt(abs(mat.a * mat.d - mat.b * mat.c))])[0]
                    # 글이 나아가는 방향: 글 행렬의 x 축을 쪽 좌표로 옮긴 것.
                    dx, dy = mat.a * pm[0] + mat.b * pm[2], mat.a * pm[1] + mat.b * pm[3]
                    norm = math.hypot(dx, dy)
                    dx, dy = (dx / norm, dy / norm) if norm else (1.0, 0.0)
                    length = C.FPDFText_GetFontInfo(tp, i, name, 256, flags)
                    font = name.value.decode("utf-8", "replace") if length else ""
                    C.FPDFText_GetFillColor(tp, i, r, g, b, a)
                    order = text_order[key][0] if key in text_order else len(text_order) + len(styles)
                    style = styles[key] = (
                        order,
                        size,
                        _f32([dx])[0],
                        _f32([dy])[0],
                        (font.split("+", 1)[-1], size, r.value, g.value, b.value, a.value),
                    )
                C.FPDFText_GetLooseCharBox(tp, i, rect)
                C.FPDFText_GetCharOrigin(tp, i, ox, oy)
                code = C.FPDFText_GetUnicode(tp, i)
                if code <= 32 and C.FPDFText_IsGenerated(tp, i) == 1:
                    continue  # 글 객체 안의 자간 조정 자리에 pdfium 이 지어 넣은 공백 (글 객체는 달려 있지만 PDF 의
                    # 글자가 아니다)
                if code == 2 and C.FPDFText_IsHyphen(tp, i) == 1:
                    code = 0x2D  # pdfium 은 줄 끝의 붙임표를 U+0002 로 바꿔 낸다. 붙임표로 되돌린다.
                found.append(
                    (style[0], i, code, rect.left, rect.bottom, rect.right, rect.top, ox.value, oy.value, style)
                )
        finally:
            textpage.close()
        blanks = self._blank_objects(text_order, found)
        found.sort(key=lambda t: (t[0], t[1]))
        coords = []
        for t in found:
            x0, y0 = _apply(pm, t[3], t[4])
            x1, y1 = _apply(pm, t[5], t[6])
            px, py = _apply(pm, t[7], t[8])
            coords.extend((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), px, py))
        coords = _f32(coords)
        pw, ph = self._content_size
        chars = []
        glyph = None  # 바로 앞 글자의 (글 객체, 상자, 원점)과 그 글자
        for k, t in enumerate(found):
            x0, y0, x1, y1, px, py = coords[6 * k : 6 * k + 6]
            if not _char_is_on_page((x0, y0, x1, y1), pw, ph):
                continue
            _order, size, dx, dy, key = t[9]
            if dx == 1.0 and dy == 0.0 and x0 < px < x1:
                # pdfium 의 상자는 「원점에서 글자 너비만큼」에 글리프의 그림 상자를 합친 것이다. 글리프가 원점보다
                # 왼쪽으로 삐져나온 글자는 왼쪽 끝이 원점보다 앞선다. 글자의 자리는 원점에서 시작하므로 원점으로 맞춘다.
                x0 = px
            if glyph is not None and glyph[0] == (t[0], *t[3:9]):
                # 글리프 하나가 글자 여럿으로 풀린 것(합자 ﬁ → f, i): 첫 글자가 글리프의 상자를 갖고, 나머지는 그 끝의
                # 너비 0 짜리다.
                head = glyph[1]
                box = (head.ex, y0, head.ex, y1) if abs(dx) >= abs(dy) else (x0, head.ey, x1, head.ey)
                chars.append(
                    ((t[0], k), _Char(t[2], box, head.ex, head.ey, size, dx, dy, head.ex, head.ey, key, obj=t[0]))
                )
                continue
            # 글자의 끝(다음 글자가 이어질 자리): 원점에서 방향으로 글자의 너비만큼. 너비는 상자에서 되찾는다.
            if abs(dx) >= abs(dy):
                advance = (x1 - x0) / abs(dx) if abs(dy) < 1e-6 else _unrotated_width(x1 - x0, y1 - y0, dx, dy)
            else:
                advance = (y1 - y0) / abs(dy) if abs(dx) < 1e-6 else _unrotated_width(x1 - x0, y1 - y0, dx, dy)
            ch = _Char(
                t[2], (x0, y0, x1, y1), px, py, size, dx, dy, px + dx * advance, py + dy * advance, key, obj=t[0]
            )
            glyph = ((t[0], *t[3:9]), ch)
            chars.append(((t[0], k), ch))
        extra = blanks + self._dropped_edge_spaces(text_order, chars)
        if extra:
            chars.extend(extra)
            chars.sort(key=lambda pair: pair[0])
        return [ch for _order, ch in chars]

    def _dropped_edge_spaces(self, text_order, chars):
        """글 객체의 앞뒤에서 pdfium 이 뺀 공백의 자리를 객체의 상자에서 되찾는다. [((차례, 자리), _Char)]

        pdfium 은 잇단 공백을 하나만 남긴다. 객체의 상자는 뺀 공백의 원점까지 두르고 있어서, 상자가 첫 글자의 원점보다
        왼쪽에서 시작하면 앞에, 남은 마지막 공백의 원점보다 오른쪽에서 끝나면 뒤에 공백이 더 있었던 것이다.
        뒤쪽은 상자가 공백 글리프의 그림 상자 때문에 늘어난 것일 수도 있어서, 늘어난 길이가 공백의 걸음(너비 + 자간)의
        정수배일 때만 믿는다. 자간은 그 객체의 이웃한 글자들에서 잰다.
        `_build_lines` 는 이것으로 펜을 옮기고 앞의 공백을 넓힌다 (공백을 더 넣지 않는다).
        """
        edges, gaps = {}, {}  # 객체의 차례 → (첫 글자, 마지막 글자), 이웃한 글자 사이의 틈들
        for (order, _k), ch in chars:
            first, last = edges.get(order, (ch, None))
            if last is not None and last.c != 32:
                gaps.setdefault(order, []).append(ch.ox - last.ex)
            edges[order] = (first, ch)
        by_order = {v[0]: v for v in text_order.values()}
        left, bottom, right, top = (ctypes.c_float() for _ in range(4))
        out = []
        for order, (first, last) in edges.items():
            if order not in by_order or first.dx != 1.0 or first.dy != 0.0:
                continue
            _order, obj, parent = by_order[order]
            if parent[1] or parent[2] or parent[0] <= 0 or not C.FPDFPageObj_GetBounds(obj, left, bottom, right, top):
                continue
            x0, x1 = sorted(
                _f32([_apply(parent, left.value, bottom.value)[0], _apply(parent, right.value, top.value)[0]])
            )
            reach = 0.01 * (first.size or 1.0)
            if x0 < first.ox - reach:
                out.append(
                    (
                        (order, -1),
                        _Char(
                            32,
                            (x0, first.oy, first.ox, first.oy),
                            x0,
                            first.oy,
                            first.size,
                            1.0,
                            0.0,
                            first.ox,
                            first.oy,
                            "edge",
                            True,
                            True,
                        ),
                    )
                )
            between = sorted(gaps.get(order, [0.0]))
            pitch = (last.ex - last.ox) + between[len(between) // 2]
            steps = round((x1 - last.ox) / pitch) if pitch > 0 else 0
            if last.c == 32 and steps >= 1 and abs((x1 - last.ox) - steps * pitch) <= 0.02:
                end = x1 + (last.ex - last.ox)
                out.append(
                    (
                        (order, float("inf")),
                        _Char(
                            32,
                            (last.ex, last.oy, end, last.oy),
                            last.ex,
                            last.oy,
                            last.size,
                            1.0,
                            0.0,
                            end,
                            last.oy,
                            "edge",
                            True,
                            True,
                        ),
                    )
                )
        return out

    def _blank_objects(self, text_order, found):
        """글자를 하나도 내지 않은 가로 글 객체를 「공백 하나」로 되살린다. [((차례, 자리), _Char)]

        pdfium 은 공백뿐인 글 객체를 글자 목록에서 뺀다. 그러면 그 공백의 너비만큼 다음 글자의 자리(펜)를 알 수 없어
        줄을 끊는 자리가 달라진다. 객체의 원점은 상자에서 알 수 있고, 너비는 같은 쪽의 같은 글꼴 공백에서 어림한다
        (같은 크기가 없으면 크기에 비례시킨다. 그 글꼴의 공백을 한 번도 못 봤으면 `DEFAULT_SPACE_WIDTH` 로 어림한다).
        `_build_lines` 는 이 공백이 줄을 잇는 자리에 있을 때만 쓴다.
        """
        seen = {t[0] for t in found}
        missing = [v for v in text_order.values() if v[0] not in seen]
        if not missing:
            return []
        widths = {}  # 글꼴 이름 → 공백 너비 / 글자 크기
        for t in found:
            if t[2] == 32 and t[5] > t[3] and t[9][2] == 1.0 and t[9][3] == 0.0:  # 가로로 놓인 공백만
                key = t[9][4]
                widths.setdefault(key[0], (t[5] - t[3]) / (key[1] or 1.0))
        out = []
        mat = C.FS_MATRIX()
        left, bottom, right, top = (ctypes.c_float() for _ in range(4))
        font_size = ctypes.c_float()
        name = ctypes.create_string_buffer(256)
        r, g, b, a = (ctypes.c_uint() for _ in range(4))
        for order, obj, parent in missing:
            font = C.FPDFTextObj_GetFont(obj)
            length = C.FPDFFont_GetBaseFontName(font, name, 256) if font else 0
            font_name = name.value.decode("utf-8", "replace").split("+", 1)[-1] if length else ""
            ratio = widths.get(font_name, DEFAULT_SPACE_WIDTH)
            if not C.FPDFTextObj_GetFontSize(obj, font_size) or not C.FPDFPageObj_GetMatrix(obj, mat):
                continue
            m = _concat((mat.a, mat.b, mat.c, mat.d, mat.e, mat.f), parent)
            if (
                abs(m[1]) > 1e-6
                or abs(m[2]) > 1e-6
                or m[0] <= 0
                or not C.FPDFPageObj_GetBounds(obj, left, bottom, right, top)
            ):
                continue  # 가로로 놓인 글만
            # 상자는 객체가 든 그릇의 좌표다. 폼 안이면 바깥 행렬(쪽 행렬까지 든 parent)을 곱한다.
            x0, y0 = _apply(parent, left.value, bottom.value)
            x1, _y1 = _apply(parent, right.value, top.value)
            size = _f32([font_size.value * math.sqrt(abs(m[0] * m[3]))])[0]
            ox, end = _f32([min(x0, x1), max(x0, x1) + ratio * size])
            oy = _f32([y0])[0]
            # 스팬을 가르는 열쇠는 글자의 것과 같은 꼴이다: 앞 글자와 글꼴·크기·색이 같으면 같은 스팬에 든다.
            C.FPDFPageObj_GetFillColor(obj, r, g, b, a)
            style = (font_name, size, r.value, g.value, b.value, a.value)
            out.append(((order, 0), _Char(32, (ox, oy, end, oy), ox, oy, size, 1.0, 0.0, end, oy, style, True, True)))
        return out

    # ── (나) 되살린 공백: 줄을 세우는 쪽이 부르는 것. 명세의 밖이고 다시 쓰지 않는다 ─────────────

    @staticmethod
    def _restored_space(line, pen, last_code, mark, gap, shift, *, space_gap, break_gap, baseline_shift):
        """`blank_object` 표시 하나를 지금 줄에 받아들인다. 받아들이지 않으면 None, 받아들이면 (새 펜, 새 「앞 글자
        번호」, 넣은 글자 또는 None).

        line: 지금 줄의 글자 목록(없으면 None). 받아들이면 이 목록을 고친다(공백 하나를 넣거나 끝의 공백을 넓힌다).
        pen: 앞 글자의 끝점 (x, y) / last_code: 앞에 받은 글자의 유니코드 번호 / mark: 표시(`_Char`, blank_object=True)
        gap, shift: 명세 3절의 「틈」과 「어긋남」을 `mark` 의 원점·크기로 잰 것
        space_gap, break_gap, baseline_shift: 명세 3절의 문턱 셋(공백을 짓기 시작하는 틈, 줄이 끊기는 틈, 줄이 끊기는
        어긋남)
        """
        if line is None or line[0].dx != 1.0 or (mark.style == "edge" and last_code != 32):
            return None  # 가로 줄에서만. 객체 가장자리의 것은 공백 뒤에서만 뜻이 있다 (pdfium 은 공백 뒤의 공백만 뺀다)
        if abs(shift) >= baseline_shift or not -space_gap < gap < break_gap:
            return None  # 지금 줄에 이어지는 자리가 아니다
        prev = line[-1]
        added = None
        if last_code != 32:
            # 공백뿐인 객체에서 온 것은 제 글꼴·크기·색으로 스팬이 갈린다 (앞 글자와 같으면 같은 스팬이다).
            added = _Char(
                32,
                (pen[0], prev.box[1], mark.ex, prev.box[3]),
                pen[0],
                pen[1],
                mark.size,
                1.0,
                0.0,
                mark.ex,
                pen[1],
                mark.style,
                True,
            )
            line.append(added)
        elif prev.c == 32 and mark.ex > prev.box[2]:
            # 빠진 공백들의 자리만큼 앞의 공백을 넓힌다 (공백 여럿의 상자를 합친 것과 같다).
            prev.box = (prev.box[0], prev.box[1], mark.ex, prev.box[3])
        return (mark.ex, pen[1]), 32, (added if mark.style != "edge" else None)

    @staticmethod
    def _after_restored_space(line, restored, ch, gap, shift, *, same_place, break_gap, baseline_shift):
        """되살린 공백 바로 뒤에 온 진짜 글자를 보고 그 공백을 고쳐 본다. 고친 것이 없으면 None, 있으면 (펜, 「앞 글자
        번호」, 틈).

        restored: `_restored_space` 가 돌려준 「넣은 글자」(줄의 마지막 글자일 때만 부른다) / ch: 지금 온 글자
        gap, shift: `ch` 의 틈과 어긋남 / same_place: 명세 3절의 덧찍기 거리 / break_gap, baseline_shift: 위와 같다
        돌려준 값이 있으면 그 펜·앞 글자 번호·틈으로 `ch` 의 판정을 이어 간다.
        """
        if abs(shift) >= baseline_shift:
            return None
        size = ch.size or 1.0
        if abs(ch.ox - restored.ox) / size < same_place and len(line) > 1:
            # 글자를 내지 않은 객체의 자리에서 다음 글자가 바로 시작한다: 공백이 아니라 너비 없는 글자였다
            # (U+200B 같은 것. pdfium 이 내지 않아 무엇인지는 모른다). 넣었던 공백을 도로 뺀다.
            line.pop()
            return (ch.ox, ch.oy), line[-1].c, 0.0
        if WIDE_SPACE_GUESS <= gap < break_gap:
            # 되살린 공백 뒤에 큰 틈이 더 있다: 보통 공백이면 다음 글자가 바로 붙는다. 너비는 공백만 하지만 자리를 따로
            # 옮겨 놓는 넓은 공백(U+2003)으로 본다 (추정). 그러면 그 뒤의 틈은 U+2003 뒤의 틈으로 판정된다.
            restored.c = 0x2003
            return (restored.ex, restored.ey), 0x2003, gap
        return None

    @staticmethod
    def _gap_is_dropped_spaces(line, ch, last_code, gap):
        """줄이 끊길 만큼 큰 앞쪽 틈이 「pdfium 이 뺀 잇단 공백」의 자리인가. 참이면 줄을 끊지 않고 공백도 더 넣지
        않는다.

        같은 글 객체 안에서 진짜 공백 바로 뒤가 크게 비었을 때다 (pdfium 은 잇단 공백을 하나만 남긴다).
        """
        return gap > 0 and last_code == 32 and not line[-1].synthetic and line[-1].obj == ch.obj

    # ── 줄, 스팬, 낱말 (CLEANROOM(PD1) 로 다시 쓴 자리) ────────────────────────────────────────

    def _build_lines(self):
        """[(블록 번호, [글자])] 줄의 목록. 명세 3절 (끝의 「이음 약속」 포함).

        글자를 내용 스트림의 차례로 따라가며, 앞 글자의 끝점(펜)에서 이 글자의 원점까지를 줄의 방향과 그 수직으로 재어
        붙일지·공백을 지을지·줄을 끊을지 정한다. 한 번 끊긴 줄로는 돌아가지 않는다.
        """
        if self._lines is not None:
            return self._lines
        lines = []
        line = None  # 지금 줄의 글자 목록
        block = -1
        pen = None  # 앞 글자의 끝점
        last_code = None  # 앞 글자의 유니코드 (되살린 공백이 바꿀 수 있다)
        received = None  # 바로 앞에 받은 진짜 글자 (덧찍기를 가릴 때 본다)
        restored = None  # 방금 `_restored_space` 가 줄에 넣은 글자

        def offsets(ch):
            """(틈, 어긋남): 펜에서 ch 의 원점까지를 줄의 방향·수직으로 재어 ch 의 크기로 나눈 것."""
            # 줄이 열린 뒤(line·pen 이 None 이 아닐 때)에만 부른다
            ux, uy = line[0].dx, line[0].dy  # pyright: ignore[reportOptionalSubscript]
            vx, vy = ch.ox - pen[0], ch.oy - pen[1]  # pyright: ignore[reportOptionalSubscript]
            size = ch.size or 1.0
            return (vx * ux + vy * uy) / size, (vy * ux - vx * uy) / size

        for ch in self._load_chars():
            if ch.blank_object:
                gap, shift = offsets(ch) if line is not None else (0.0, 0.0)
                taken = self._restored_space(
                    line,
                    pen,
                    last_code,
                    ch,
                    gap,
                    shift,
                    space_gap=SPACE_GAP,
                    break_gap=LINE_BREAK_GAP,
                    baseline_shift=LINE_BREAK_SHIFT,
                )
                if taken is not None:
                    pen, last_code, restored = taken
                continue
            size = ch.size or 1.0
            if (
                received is not None
                and received.c == ch.c
                and abs(ch.ox - received.ox) < SAME_PLACE_REACH * size
                and abs(ch.oy - received.oy) < SAME_PLACE_REACH * size
            ):
                continue  # 덧찍기
            received = ch
            new_line = new_block = False
            if line is None or ch.dx * line[0].dx + ch.dy * line[0].dy < SAME_DIRECTION_COS:
                new_line = new_block = True
            else:
                gap, shift = offsets(ch)
                if restored is not None and line[-1] is restored:
                    fixed = self._after_restored_space(
                        line,
                        restored,
                        ch,
                        gap,
                        shift,
                        same_place=SAME_PLACE_REACH,
                        break_gap=LINE_BREAK_GAP,
                        baseline_shift=LINE_BREAK_SHIFT,
                    )
                    if fixed is not None:
                        pen, last_code, gap = fixed
                if abs(shift) >= LINE_BREAK_SHIFT:
                    new_line = True
                    # 블록: 크게 어긋났거나, 앞 줄의 머리보다 오른쪽에서 시작하면 새 블록 (문단의 다음 줄은 머리로
                    # 되돌아온다).
                    # 앞 줄이 번호나 글머리표로 시작했으면 들여 쓴 줄도 그 블록이다.
                    head = line[0]
                    along = (ch.ox - head.ox) * head.dx + (ch.oy - head.oy) * head.dy
                    new_block = abs(shift) > BLOCK_BREAK_SHIFT or (along > BLOCK_INDENT and head.c not in LIST_MARKERS)
                elif gap >= LINE_BREAK_GAP:
                    new_line = not self._gap_is_dropped_spaces(line, ch, last_code, gap)
                elif gap <= -LINE_BREAK_GAP:
                    new_line = True
                elif gap >= SPACE_GAP and ch.c != _SPACE and _space_goes_after(last_code):
                    line.append(self._made_space(line[-1], pen, ch, gap))
            if new_line:
                if new_block:
                    block += 1
                line = []
                lines.append((block, line))
            line.append(ch)  # pyright: ignore[reportOptionalMemberAccess] — 첫 글자에서 new_line 이 참이라 위에서 열린다
            restored = None
            pen, last_code = (ch.ex, ch.ey), ch.c
        self._lines = lines
        return lines

    @staticmethod
    def _made_space(prev, pen, ch, gap):
        """틈에 지어 넣는 공백: 펜에서 ch 의 원점까지, 세로(가로 줄에서)는 앞 글자의 것. 크기와 스팬 열쇠는 ch 의 것."""
        if abs(ch.dx) >= abs(ch.dy):
            box = (min(pen[0], ch.ox), prev.box[1], max(pen[0], ch.ox), prev.box[3])
        else:
            box = (prev.box[0], min(pen[1], ch.oy), prev.box[2], max(pen[1], ch.oy))
        # 넓은 틈의 공백은 어느 이웃과도 같지 않은 열쇠를 줘서 혼자 스팬이 되게 한다.
        style = (ch.style, "wide space") if gap > WIDE_SPACE_GAP else ch.style
        return _Char(_SPACE, box, pen[0], pen[1], ch.size, ch.dx, ch.dy, ch.ox, ch.oy, style, synthetic=True)

    def get_text_blocks(self, chars=False):
        """[{"lines": [{"dir": (dx, dy), "spans": [...]}]}] (`types.py`). 명세 4절.

        스팬은 {"size", "bbox", "text"} 이고 chars=True 면 "text" 대신 "chars": [{"c", "bbox"}].
        블록은 줄의 블록 번호가 같은 것끼리 차례대로 묶는다.
        """
        blocks = []
        current = None
        for number, line in self._build_lines():
            if number != current:
                current = number
                blocks.append({"lines": []})
            head = line[0]
            level = head.dx == 1.0 and head.dy == 0.0  # 올려 쓴 글자는 정확히 가로인 줄에서만 가른다
            spans, key, run = [], None, None
            for ch in line:
                raised = level and head.oy - ch.oy > RAISED_SHIFT * (ch.size or 1.0)
                if run is None or (ch.style, raised) != key:
                    key, run = (ch.style, raised), []
                    spans.append(run)
                run.append(ch)
            out = []
            for run in spans:
                span = {"size": run[0].size, "bbox": _union([c.box for c in run])}
                if chars:
                    span["chars"] = [{"c": chr(c.c), "bbox": c.box} for c in run]
                else:
                    span["text"] = "".join(chr(c.c) for c in run)
                out.append(span)
            blocks[-1]["lines"].append({"dir": (head.dx, head.dy), "spans": out})
        return blocks

    def get_words(self):
        """[(x0, y0, x1, y1, 낱말, 블록 번호, 줄 번호, 낱말 번호)]. 명세 5절. 낱말은 줄을 넘지 않는다."""
        words = []
        current, line_no = None, 0
        for number, line in self._build_lines():
            line_no = line_no + 1 if number == current else 0
            current = number
            word_no = 0
            run = []
            for ch in [*line, None]:
                if ch is not None and not _breaks_word(ch.c):
                    if run or ch.c != _WORD_HEAD_SKIPPED:
                        run.append(ch)
                    continue
                if run:
                    x0, y0, x1, y1 = _union([c.box for c in run])
                    if x1 > x0 and y1 > y0:
                        words.append((x0, y0, x1, y1, "".join(chr(c.c) for c in run), number, line_no, word_no))
                        word_no += 1
                    run = []
        return words

    # ── 벡터 그림 ──────────────────────────────────────────────────────────

    def get_drawings(self):
        fill_mode, stroke = ctypes.c_int(), ctypes.c_int()
        r, g, b, a = (ctypes.c_uint() for _ in range(4))
        width = ctypes.c_float()
        fx, fy = ctypes.c_float(), ctypes.c_float()
        paths = []
        for obj, matrix in self._load_objects()[1]:
            if not C.FPDFPath_GetDrawMode(obj, fill_mode, stroke):
                continue
            filled, stroked = fill_mode.value != C.FPDF_FILLMODE_NONE, bool(stroke.value)
            if not (filled or stroked):
                continue
            segments = []
            for k in range(C.FPDFPath_CountSegments(obj)):
                seg = C.FPDFPath_GetPathSegment(obj, k)
                C.FPDFPathSegment_GetPoint(seg, fx, fy)
                segments.append(
                    (C.FPDFPathSegment_GetType(seg), fx.value, fy.value, bool(C.FPDFPathSegment_GetClose(seg)))
                )
            flat = []
            for _kind, x, y, _close in segments:
                flat.extend(_apply(matrix, x, y))
            flat = _f32(flat)
            segments = [(s[0], flat[2 * k], flat[2 * k + 1], s[3]) for k, s in enumerate(segments)]
            fill_rgba = stroke_rgba = stroke_width = None
            if filled and C.FPDFPageObj_GetFillColor(obj, r, g, b, a):
                fill_rgba = (r.value, g.value, b.value, a.value)
            if stroked and C.FPDFPageObj_GetStrokeColor(obj, r, g, b, a):
                stroke_rgba = (r.value, g.value, b.value, a.value)
                C.FPDFPageObj_GetStrokeWidth(obj, width)
                stroke_width = width.value
            paths.append((segments, matrix, fill_rgba, stroke_rgba, stroke_width))
        return _paths_to_drawings(paths)

    # ── 그림, 렌더 ─────────────────────────────────────────────────────────

    def get_image_boxes(self):
        return list(self._load_objects()[2])

    def render_png(self, path, dpi, clip=None):
        pw, ph = self._size
        crop = (0, 0, 0, 0)
        if clip:
            x0, y0, x1, y1 = clip
            crop = (max(0.0, x0), max(0.0, ph - y1), max(0.0, pw - x1), max(0.0, y0))
        bitmap = self._page.render(scale=dpi / 72, crop=crop, rev_byteorder=True)
        try:
            _write_png(path, bitmap.width, bitmap.height, bitmap.stride, bitmap.n_channels, bytes(bitmap.buffer))
        finally:
            bitmap.close()


def _unrotated_width(box_w, box_h, dx, dy):
    """기운 글자: 두른 상자의 크기에서 기울기 전의 너비를 되찾는다 (45도에서는 풀리지 않아 상자의 긴 변을 쓴다)."""
    c, s = abs(dx), abs(dy)
    det = c * c - s * s
    if abs(det) < 1e-3:
        return max(box_w, box_h)
    return max(0.0, (box_w * c - box_h * s) / det)


def _char_is_on_page(box, page_width, page_height):
    """글자의 상자 (x0, y0, x1, y1) 가 쪽 (0, 0, page_width, page_height) 에 걸치는가. 명세 3절 「쪽 밖」.

    변만 맞닿은 것은 걸친 것이 아니다 (오른쪽 끝이 0.00 이면 빠지고 0.01 이면 남는 것을 재서 확인).
    """
    x0, y0, x1, y1 = box
    return x0 < page_width and x1 > 0 and y0 < page_height and y1 > 0


def _shading_image_box(x0, y0, x1, y1):
    """음영 객체의 두른 상자(쪽 좌표) → 그림 상자 (x0, y0, x1, y1), 값은 float. 명세 7절.

    바깥쪽 정수 눈금으로 넓힌다 (왼쪽·위는 내림, 오른쪽·아래는 올림). 눈금에 닿을락 말락 한 변을 봐주는 여유는
    두지 않았다: 지어낸 PDF 에서 PyMuPDF 는 눈금을 1/100000 pt 넘은 변도 다음 눈금으로 넓혔고, 네 보고서에서도
    여유 0 이 가장 많이 맞았다 (명세의 1/1000 과 다르다). 너비도 높이도 없는 상자는 칠할 자리가 없는 음영(클립이
    비었다)이고 PyMuPDF 는 (0, 0, 0, 0) 을 낸다.
    """
    if x0 == x1 and y0 == y1:
        return (0.0, 0.0, 0.0, 0.0)
    return (float(math.floor(x0)), float(math.floor(y0)), float(math.ceil(x1)), float(math.ceil(y1)))


def _path_to_items(segments, stroking):
    """경로 하나의 점 목록 → (항목 목록, Rect) 또는 None. 명세 1절.

    segments: [(갈래, x, y, 닫힘 표시)] 쪽 좌표. 갈래는 `_SEG_MOVETO`·`_SEG_LINETO`·`_SEG_BEZIERTO`.
    stroking: 획으로 읽는가(True) 채움으로 읽는가(False). 항목의 점은 `Point`, 상자는 `Rect`.
    """
    items = []
    reach = []  # 두른 상자에 드는 점
    pen = start = None  # 지금 자리, 부분 경로의 처음 점
    part = 0  # 지금 부분 경로(옮김이나 닫기 뒤)의 항목이 items 의 어디서부터인가
    drawn = []  # 부분 경로에서 그은 선의 끝점 전부 (제자리 선 포함). 곡선이 끼면 None
    origin = None  # drawn 의 선들이 시작한 점
    lines = 0  # 잇달아 남긴 선의 수 (사각을 가릴 때 센다)
    after_move = False
    moved = False  # 지금 부분 경로가 옮김으로 시작했는가 (닫은 뒤 옮김 없이 이어 그은 것은 닫아도 선이 더해지지 않는다.
    # 재서 확인)

    def is_box(p0, p1, p2, p3):
        """p0→p1 가로, p1→p2 세로, p2→p3 가로이고 p3 이 p0 의 바로 위아래인가 (닫으면 축에 나란한 직사각형)."""
        return p0.y == p1.y and p1.x == p2.x and p2.y == p3.y and p3.x == p0.x

    def line_to(p):
        nonlocal pen, lines, after_move
        reach.append(p)
        if p == pen and not after_move:
            return  # 제자리 선 (옮김 바로 뒤의 것만 남는다)
        items.append(("l", pen, p))
        pen, after_move = p, False
        lines += 1
        if stroking and lines == 4 and items[-4][1] == p:
            corners = [it[1] for it in items[-4:]]
            del items[-4:]
            items.append(
                (
                    "qu",
                    Rect(
                        min(c.x for c in corners),
                        min(c.y for c in corners),
                        max(c.x for c in corners),
                        max(c.y for c in corners),
                    ),
                )
            )
            lines = 0

    def close():
        nonlocal pen, part, drawn, origin, lines, after_move, moved
        made = items[part:]
        corners = None
        if drawn is not None and len(drawn) == 3 and is_box(origin, *drawn):
            corners = [origin, *drawn]
        elif (
            len(made) == 3
            and all(it[0] == "l" for it in made)
            and is_box(made[0][1], made[0][2], made[1][2], made[2][2])
        ):
            corners = [made[0][1], made[0][2], made[1][2], made[2][2]]
        if corners:
            points = cast("list[Point]", corners)  # 네 꼭짓점을 고른 뒤라 None 이 없다(표기만)
            del items[part:]
            items.append(
                (
                    "re",
                    Rect(
                        min(c.x for c in points),
                        min(c.y for c in points),
                        max(c.x for c in points),
                        max(c.y for c in points),
                    ),
                )
            )
            pen = corners[3]  # 네모 뒤에 옮김 없이 이어 그으면 셋째 선의 끝에서 나간다 (재서 확인)
        else:
            if pen != start and moved:
                items.append(("l", pen, start))
            pen = start
        part, drawn, origin, lines, after_move, moved = len(items), [], pen, 0, False, False

    def straight(p, closing):
        # 닫힘 표시가 붙은 「처음 점으로 가는 선」은 선이 아니라 경로 닫기다. 옮김 바로 뒤의 것만은 진짜 제자리 선이다
        # (pdfium 은 처음 점에 와 있을 때 닫으면 점을 더하지 않고 마지막 점에 표시만 한다).
        if not (closing and p == start) or after_move:
            line_to(p)
            if drawn is not None:
                drawn.append(p)
        if closing:
            close()

    k, n = 0, len(segments)
    while k < n:
        kind, x, y, closing = segments[k]
        p = Point(x, y)
        if kind == _SEG_MOVETO or pen is None:
            pen = start = origin = p
            part, drawn, lines, after_move, moved = len(items), [], 0, True, True
            if not reach:
                reach.append(p)
            k += 1
            if kind != _SEG_MOVETO and closing:
                close()
        elif kind == _SEG_BEZIERTO and k + 2 < n:
            c1, c2 = p, Point(segments[k + 1][1], segments[k + 1][2])
            end, closing = Point(segments[k + 2][1], segments[k + 2][2]), segments[k + 2][3]
            k += 3
            if (c1 == pen and c2 in (pen, end)) or (c1 == end and c2 == end):
                straight(end, closing)  # 제어점이 양 끝점에 겹친 곡선은 선이다 (재서 확인. 명세에 없다)
                continue
            items.append(("c", pen, c1, c2, end))
            reach.extend((c1, c2, end))
            pen, drawn, lines, after_move = end, None, 0, False
            if closing:
                close()
        else:
            straight(p, closing)
            k += 1
    if not items:
        return None
    return items, Rect(
        min(p.x for p in reach), min(p.y for p in reach), max(p.x for p in reach), max(p.y for p in reach)
    )


def _paths_to_drawings(paths):
    """쪽의 경로 객체들 → 그리기 항목 목록 [{"items", "rect", "color", "fill", "width", "fill_opacity"}]. 명세 2절.

    paths: 내용 스트림의 차례로 [(segments, matrix, fill_rgba, stroke_rgba, stroke_width)].
        segments: `_path_to_items` 가 받는 꼴 / matrix: 객체 좌표 → 쪽 좌표 (a, b, c, d, e, f)
        fill_rgba, stroke_rgba: (r, g, b, a) 0~255 이거나 None(채우지 않음·긋지 않음) / stroke_width: 객체에 적힌
        굵기(행렬을 곱하기 전)
    채우지도 긋지도 않는 경로는 이미 빠져 있다.
    """
    out = []
    for segments, matrix, fill_rgba, stroke_rgba, stroke_width in paths:
        if fill_rgba is not None:
            read = _path_to_items(segments, False)
            if read is not None:
                out.append(
                    {
                        "items": read[0],
                        "rect": read[1],
                        "color": None,
                        "fill": tuple(v / 255 for v in fill_rgba[:3]),
                        "width": None,
                        "fill_opacity": fill_rgba[3] / 255,
                    }
                )
        if stroke_rgba is not None:
            read = _path_to_items(segments, True)
            if read is None:
                continue
            color = tuple(v / 255 for v in stroke_rgba[:3])
            width = (stroke_width or 0.0) * math.sqrt(abs(matrix[0] * matrix[3] - matrix[1] * matrix[2]))
            last = out[-1] if out else None
            if last is not None and last["fill"] is not None and last["color"] is None and last["items"] == read[0]:
                last["color"], last["width"] = color, width  # 같은 꼴을 채우고 바로 그었다: 한 항목
            else:
                out.append(
                    {
                        "items": read[0],
                        "rect": read[1],
                        "color": color,
                        "fill": None,
                        "width": width,
                        "fill_opacity": None,
                    }
                )
    return out


def _write_png(path, width, height, stride, channels, data):
    """RGB(A) 바이트를 PNG 로 쓴다 (zlib 만 쓴다. 그림 라이브러리를 더하지 않으려고)."""
    rows = bytearray()
    row_bytes = width * 3
    for y in range(height):
        row = data[y * stride : y * stride + width * channels]
        if channels == 4:
            rgb = bytearray(row_bytes)
            rgb[0::3], rgb[1::3], rgb[2::3] = row[0::4], row[1::4], row[2::4]
            row = bytes(rgb)
        elif channels == 1:
            row = bytes(v for g in row for v in (g, g, g))
        rows.append(0)
        rows.extend(row)

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png)


class Document:
    def __init__(self, pdf, needs_pass=False):
        self._pdf = pdf
        self.needs_pass = needs_pass
        self._pages = OrderedDict()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        for page in self._pages.values():
            page.close()
        self._pages.clear()
        if self._pdf is not None:
            self._pdf.close()
            self._pdf = None

    def __len__(self):
        return len(self._pdf) if self._pdf is not None else 0

    def __getitem__(self, index):
        page = self._pages.get(index)
        if page is None:
            if not 0 <= index < len(self):
                raise IndexError(index)
            page = self._pages[index] = Page(self, index)
            while len(self._pages) > _PAGE_CACHE:
                self._pages.popitem(last=False)[1].close()
        else:
            self._pages.move_to_end(index)
        return page

    def get_toc(self):
        """[[단계, 제목, 쪽 번호]]. 명세 6절. 단계와 쪽 번호는 1부터, 빈 제목은 " ".
        쪽 번호는 문서 안의 쪽을 가리키지 않으면 -1."""
        if self._pdf is None:
            return []
        pdf, pages = self._pdf.raw, len(self._pdf)
        toc, seen = [], set()

        def walk(parent, level):
            mark = C.FPDFBookmark_GetFirstChild(pdf, parent)
            while mark:
                address = ctypes.addressof(mark.contents)
                if address in seen or level > _TOC_MAX_DEPTH:
                    return  # 돌고 도는 책갈피
                seen.add(address)
                size = C.FPDFBookmark_GetTitle(mark, None, 0)
                buffer = ctypes.create_string_buffer(size)
                C.FPDFBookmark_GetTitle(mark, buffer, size)
                title = buffer.raw[: max(0, size - 2)].decode("utf-16-le", "replace")
                dest = C.FPDFBookmark_GetDest(pdf, mark)
                if not dest:
                    action = C.FPDFBookmark_GetAction(mark)
                    if action and C.FPDFAction_GetType(action) == C.PDFACTION_GOTO:
                        dest = C.FPDFAction_GetDest(pdf, action)
                index = C.FPDFDest_GetDestPageIndex(pdf, dest) if dest else -1
                toc.append([level, title or " ", index + 1 if 0 <= index < pages else -1])
                walk(mark, level + 1)
                mark = C.FPDFBookmark_GetNextSibling(pdf, mark)

        walk(None, 1)
        return toc


def open_document(path):
    try:
        return Document(pdfium.PdfDocument(str(path)))
    except pdfium.PdfiumError as e:
        if getattr(e, "err_code", None) == C.FPDF_ERR_PASSWORD or "password" in str(e).lower():
            return Document(None, needs_pass=True)
        raise PdfOpenError(str(e)) from e
    except Exception as e:
        raise PdfOpenError(str(e)) from e
