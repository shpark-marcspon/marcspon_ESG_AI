# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
"""문장 위치(locate)의 pdfium 부분과 작은 순수 함수. 쓰는 곳은 `tools/coordinates.PdfiumCoordinates` 하나다.

글은 노트북대로 pypdf(`PypdfText`)이고 이 모듈은 그 글의 문장이 쪽의 어디에 있는지만 pdfium 글자 상자로 찾는다
(밴드 G1d, MARC-TICK-103). 정규화·줄 묶기의 규칙은 측정 스크립트에서 옮겼다 —
출처: esg-lab/out/loc-probe/probe.py, 2026-10-16 측정, 저장소 밖(실재 보고서의 글·쪽 범위·파일 이름은 옮기지 않았다).

좌표는 두 가지다. pdfium 의 글자 상자는 PDF 사용자 공간(왼쪽 아래 원점) `(left, bottom, right, top)` 이고, 결과로
내는 상자는 크롭 상자의 왼쪽 위 원점 `[left, top, right, bottom]` 이다(`to_top_left`. 파서 선례
services/parser/docparse/engine/pdfium_engine.py 의 Page).
"""

import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Final, cast

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from esgapi.greenwash.tools.textnorm import TRUNC_TAIL as TRUNC_TAIL
from esgapi.greenwash.tools.textnorm import norm_chars, norm_str
from esgapi.greenwash.tools.textnorm import strip_tail as strip_tail

Box = tuple[float, float, float, float]
"""pdfium 의 글자·줄 상자 (left, bottom, right, top), 왼쪽 아래 원점, pt."""

_LIGATURE_TWICE: Final = re.compile(r"(ff|fi|fl)\1")


# ── 정규화 (probe.py 의 norm_map) ─────────────────────────────────────────────


def norm_map(chars: Sequence[str], tier: int) -> tuple[str, list[int]]:
    """쪽의 글자(pdfium 글자 번호 차례) → (정규화 글, 정규화 글자마다 그 글자의 pdfium 번호)."""
    buf: list[str] = []
    pos: list[int] = []
    for index, ch in enumerate(chars):
        for c in norm_chars(ch, tier):
            buf.append(c)
            pos.append(index)
    return "".join(buf), pos


def find_all(hay: str, needle: str) -> list[int]:
    found: list[int] = []
    i = hay.find(needle)
    while i >= 0:
        found.append(i)
        i = hay.find(needle, i + 1)
    return found


def head_drops(sentence: str, tier: int, keep_min: float) -> Iterator[str]:
    """개선 ①: 띄어쓰기 단위 조각을 앞에서부터 하나씩 버린 나머지. 정규화(tier) 글자 수가 원 문장의 keep_min 이상인
    것만, 긴 것부터."""
    pieces = sentence.split()
    whole = len(norm_str(sentence, tier))
    for k in range(1, len(pieces)):
        rest = " ".join(pieces[k:])
        if len(norm_str(rest, tier)) < keep_min * whole:
            return
        yield rest


# ── 줄 묶기 (probe.py 의 group_lines) ─────────────────────────────────────────


def drop_unplaced(boxes: Sequence[Box]) -> list[Box]:
    """줄 묶기 전에 뺄 글자: 너비 0 이고(AND) 높이 0 인 글자, 그리고 앞 글자와 상자가 같은 글자(pdfium 이 합자를 풀어
    같은 상자로 낸 둘째 글자 — 측정 개정 2)."""
    kept: list[Box] = []
    prev: Box | None = None
    for box in boxes:
        left, bottom, right, top = box
        same = box == prev
        prev = box
        if (right - left <= 0 and top - bottom <= 0) or same:
            continue
        kept.append(box)
    return kept


def group_lines(boxes: Sequence[Box]) -> list[Box]:
    """글자 상자(차례대로) → 줄마다 상자. 같은 줄 = 세로 가운데가 현재 줄의 위아래에서 높이의 ±25% 안이고, 왼쪽 끝이
    현재 오른쪽 끝 − 0.5×높이 이상(뒤로 돌아가면 새 줄)."""
    lines: list[list[float]] = []
    for left, bottom, right, top in boxes:
        if lines:
            cur = lines[-1]
            cy = (bottom + top) / 2
            h = max(cur[3] - cur[1], top - bottom, 1.0)
            same_row = cur[1] - 0.25 * h <= cy <= cur[3] + 0.25 * h
            if same_row and left >= cur[4] - 0.5 * h:
                cur[0] = min(cur[0], left)
                cur[1] = min(cur[1], bottom)
                cur[2] = max(cur[2], right)
                cur[3] = max(cur[3], top)
                cur[4] = right
                continue
        lines.append([left, bottom, right, top, right])
    return [(x[0], x[1], x[2], x[3]) for x in lines]


def to_top_left(box: Box, crop: Box) -> list[float]:
    """pdfium 상자 (l, b, r, t) → 크롭 상자 왼쪽 위 원점의 [l − cx0, cy1 − t, r − cx0, cy1 − b], 소수 둘째 자리."""
    left, bottom, right, top = box
    cx0, cy1 = crop[0], crop[3]
    return [round(left - cx0, 2), round(cy1 - top, 2), round(right - cx0, 2), round(cy1 - bottom, 2)]


# ── 되읽기 (개선 ②③) ──────────────────────────────────────────────────────────


def readback_norm(text: str) -> str:
    """되읽은 글의 2단 정규화. 개선 ③: NFKC 뒤 합자가 두 번 나온 꼴(ff·fi·fl 이 이어 둘)을 하나로 줄인다."""
    return norm_str(_LIGATURE_TWICE.sub(r"\1", unicodedata.normalize("NFKC", text)), 2)


def is_subsequence(needle: str, hay: str) -> bool:
    it = iter(hay)
    return all(c in it for c in needle)


def readback_ok(needle: str, back: str, extra_max: float) -> bool:
    """개선 ②: 되읽은 글(2단)이 문장(2단, needle)을 차례대로 포함하고, 덧붙은 글자가 문장 길이의 extra_max 이하."""
    return bool(needle) and is_subsequence(needle, back) and len(back) - len(needle) <= extra_max * len(needle)


# ── pdfium ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PageText:
    """쪽 하나의 글자와 정규화 대응표. 상자·되읽기는 문서가 열려 있는 동안만."""

    textpage: pdfium.PdfTextPage
    chars: list[str]
    maps: dict[int, tuple[str, list[int]]]
    crop: Box
    rotation: int

    def charbox(self, index: int) -> Box:
        left, bottom, right, top = cast("tuple[float, float, float, float]", self.textpage.get_charbox(index))
        return (left, bottom, right, top)

    def bounded(self, box: Box) -> str:
        left, bottom, right, top = box
        return self.textpage.get_text_bounded(left, bottom, right, top)


def crop_box(page: pdfium.PdfPage) -> Box:
    """crop = cropbox 를 mediabox 안으로 자른 것(비면 mediabox). 파서 선례와 같다."""
    media = cast("tuple[float, float, float, float]", page.get_mediabox())
    crop = cast("tuple[float, float, float, float]", page.get_cropbox())
    clipped = (max(crop[0], media[0]), max(crop[1], media[1]), min(crop[2], media[2]), min(crop[3], media[3]))
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        return media
    return clipped


class PdfiumDocument:
    """pdfium 문서 하나. 쪽은 처음 물을 때 읽어(글자 번호 단위 FPDFText_GetUnicode) 대응표와 함께 들고 있는다.
    close() 는 문서와 그 쪽·텍스트 쪽을 함께 닫는다(pypdfium2 가 자식을 먼저 닫는다)."""

    def __init__(self, data: bytes) -> None:
        self.pdf = pdfium.PdfDocument(data)
        self.pages: dict[int, PageText] = {}

    def __len__(self) -> int:
        return len(self.pdf)

    @property
    def closed(self) -> bool:
        return not self.pdf.raw

    def page(self, index: int) -> PageText:
        """index 는 0부터. 범위 밖이면 IndexError."""
        if not 0 <= index < len(self.pdf):
            raise IndexError(f"쪽 범위 밖: {index + 1} / {len(self.pdf)}")
        if index not in self.pages:
            page = self.pdf[index]
            textpage = page.get_textpage()
            codes = [pdfium_c.FPDFText_GetUnicode(textpage, i) for i in range(textpage.count_chars())]
            chars = [chr(u) if u else "" for u in codes]
            self.pages[index] = PageText(
                textpage=textpage,
                chars=chars,
                maps={1: norm_map(chars, 1), 2: norm_map(chars, 2)},
                crop=crop_box(page),
                rotation=page.get_rotation(),
            )
        return self.pages[index]

    def close(self) -> None:
        self.pages.clear()
        self.pdf.close()
