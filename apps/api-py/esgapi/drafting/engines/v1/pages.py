"""쪽 → 조각과 S2 묶음(처분 ⑥·⑨). 쪽 = 조각, 1부터. 빈 쪽(글 0)은 표시만 하고 묶음·재료에 싣지 않는다.

pages_of(texts)       쪽 글 목록 → Page(1부터, 8,000자에서 자름 — truncated). 자르기 전에 escape_heads 를 거친다
escape_heads(text)    표지 흉내 바꿈(474·RP2b ⑦ — 진짜 표지는 block·engines/v2 만 단다. 경고 0): 줄 머리의
                      「[PAGE n]」 → 「［PAGE n］」, 줄 머리의 「[B 」·「[T 」 → 「［B 」·「［T 」, 문장 표지 글자
                      「⟨」·「⟩」 → 「〈」·「〉」(어디서든). 바꿈 글자는 다 BMP 한 자리라 UTF-16 길이가 그대로다
                      (engines/v2 의 문장 범위가 원문 위에 선다)
block(page)           「[PAGE n]」 머리 + 쪽 글
batches(pages)        글 있는 쪽을 차례대로 묶음 글자 합 24,000 안으로(쪽을 쪼개지 않는다 — 쪽 하나는 늘 들어간다)
batch_text(batch)     묶음의 글(블록을 빈 줄로 이음)
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

PAGES_MAX: Final = 300
PAGE_MAX_CHARS: Final = 8000
BATCH_MAX_CHARS: Final = 24000
JOIN: Final = "\n\n"
HEAD_LOOKALIKE: Final = re.compile(r"^(\s*)\[(PAGE\s+\d+)\]", re.MULTILINE)
MARKER_LOOKALIKE: Final = re.compile(r"^(\s*)\[([BT] )", re.MULTILINE)
SENTENCE_MARKS: Final = str.maketrans({"⟨": "〈", "⟩": "〉"})


@dataclass(frozen=True, slots=True)
class Page:
    number: int
    text: str
    truncated: bool

    @property
    def empty(self) -> bool:
        return not self.text


def escape_heads(text: str) -> str:
    heads = MARKER_LOOKALIKE.sub("\\1［\\2", HEAD_LOOKALIKE.sub("\\1［\\2］", text))
    return heads.translate(SENTENCE_MARKS)


def pages_of(texts: Sequence[str]) -> list[Page]:
    return [
        Page(number=at, text=text[:PAGE_MAX_CHARS], truncated=len(text) > PAGE_MAX_CHARS)
        for at, text in enumerate((escape_heads(t.strip()) for t in texts), start=1)
    ]


def block(page: Page) -> str:
    return f"[PAGE {page.number}]\n{page.text}"


def batches(pages: Sequence[Page]) -> list[list[Page]]:
    found: list[list[Page]] = []
    size = 0
    for page in pages:
        if page.empty:
            continue
        length = len(block(page))
        if found and size + len(JOIN) + length <= BATCH_MAX_CHARS:
            found[-1].append(page)
            size += len(JOIN) + length
        else:
            found.append([page])
            size = length
    return found


def batch_text(batch: Sequence[Page]) -> str:
    return JOIN.join(block(page) for page in batch)
