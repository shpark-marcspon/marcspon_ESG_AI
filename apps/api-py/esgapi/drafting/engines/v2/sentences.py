"""문장 나누기 `drafting-sentences@1`(밴드 RP2b §2-2, 결정 MARC-ENT-514 2번). 문단·제목 블록 글 → 문장 범위.

split(text)        블록 글 원문(strip 전) 위의 문장 범위 차례. 범위의 단위는 **UTF-16 자리** [start, end)(core 뷰의
                   boxes 와 같은 단위 — 보충 평면 글자는 두 자리). 앞뒤 공백은 범위 밖, 빈 문장 0. 번호는 0부터(차례)
pieces(text, spans) 범위마다 그 글(UTF-16 으로 자름)

규칙(바꾸면 SEGMENTER 판을 올린다 — 번호가 갈린다):
  끝 부호 `.`·`?`·`!`·`。` 뒤(닫는 따옴표·괄호까지) 가 공백이거나 글 끝이면 나눈다. 줄바꿈 하나만으로는 안 나눈다
  (PDF 줄 접힘 = 공백). 안 나누는 점: 날짜(`2024. 12. 31.`) · 줄 머리 번호(`1. 개요`) · 점 이어짐(`...`) ·
  약어(ABBREVIATIONS — `No. 3`·`e.g. 다음`). 소수점(`3.5`)은 뒤가 공백이 아니라 늘 안 나눈다.
표는 쓰지 않는다(행 하나 = 문장 하나, engines/v2/material).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

SEGMENTER: Final = "drafting-sentences@1"
ENDS: Final = frozenset(".?!。")
CLOSERS: Final = frozenset("\"'”’)]}）」』〉》")
ABBREVIATIONS: Final = frozenset(
    [
        "No",
        "no",
        "Vol",
        "vol",
        "p",
        "pp",
        "e.g",
        "i.e",
        "cf",
        "vs",
        "Mr",
        "Mrs",
        "Ms",
        "Dr",
        "St",
        "Fig",
        "fig",
        "approx",
    ]
)
DATE: Final = re.compile(r"\d{4}\.\s*\d{1,2}\.(?:\s*\d{1,2}\.)?")
LIST_HEAD: Final = re.compile(r"^[ \t]*\d{1,3}\.(?=\s)", re.MULTILINE)
WORD_BEFORE: Final = re.compile(r"[A-Za-z][A-Za-z.]*$")


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int


def _utf16(text: str) -> list[int]:
    """code point 자리 → UTF-16 자리(길이 n + 1)."""
    found = [0]
    for char in text:
        found.append(found[-1] + (2 if ord(char) > 0xFFFF else 1))
    return found


def _kept_dots(text: str) -> set[int]:
    kept: set[int] = set()
    for pattern in (DATE, LIST_HEAD):
        for match in pattern.finditer(text):
            kept |= {at for at in range(match.start(), match.end()) if text[at] == "."}
    return kept


def _ends_here(text: str, at: int, kept: set[int]) -> bool:
    if text[at] not in ENDS or at in kept:
        return False
    if text[at] != ".":
        return True
    dotted = (at > 0 and text[at - 1] == ".") or (at + 1 < len(text) and text[at + 1] == ".")
    word = WORD_BEFORE.search(text, 0, at)
    return not dotted and (word is None or word.group(0) not in ABBREVIATIONS)


def _cuts(text: str) -> list[tuple[int, int]]:
    """code point 범위(앞뒤 공백 뺌)."""
    kept = _kept_dots(text)
    bounds: list[int] = []
    at = 0
    while at < len(text):
        if _ends_here(text, at, kept):
            after = at + 1
            while after < len(text) and text[after] in CLOSERS:
                after += 1
            if after == len(text) or text[after].isspace():
                bounds.append(after)
                at = after
                continue
        at += 1
    found: list[tuple[int, int]] = []
    start = 0
    for end in [*bounds, len(text)]:
        lo, hi = start, end
        while lo < hi and text[lo].isspace():
            lo += 1
        while hi > lo and text[hi - 1].isspace():
            hi -= 1
        if lo < hi:
            found.append((lo, hi))
        start = end
    return found


def split(text: str) -> tuple[Span, ...]:
    units = _utf16(text)
    return tuple(Span(units[lo], units[hi]) for lo, hi in _cuts(text))


def pieces(text: str, spans: Sequence[Span]) -> tuple[str, ...]:
    raw = text.encode("utf-16-le")
    return tuple(raw[2 * span.start : 2 * span.end].decode("utf-16-le") for span in spans)
