"""pdfium 없는 정규화 — 문장 글을 견주기 전에 같은 꼴로 만든다. 쓰는 곳: pdfium_locate(G1d)·compare(GR1).

정의는 옛 flows/pdfium_locate.py(지금 tools/pdfium_locate.py)에서 바이트 그대로 옮겼다(밴드 GR1, MARC-TICK-106).
비교(compare)가 pypdfium2 를 끌어오지 않게 하려고 나눴다.
규칙의 출처는 pdfium_locate 머리말의 측정 스크립트(probe.py)다.
"""

import unicodedata
from typing import Final

TRUNC_TAIL: Final = " ..."
"""노트북이 긴 문장 끝에 붙이는 잘림 꼬리(probe.py 의 TRUNC_TAIL)."""

# probe.py 의 집합 그대로.
QUOTES: Final = frozenset("'\"‘’‚‛“”„‟«»「」『』′″`´")
DASHES: Final = frozenset("‐‑‒–—―−﹣－-")
DROP: Final = frozenset("​‌‍⁠﻿\xad\x02￾￿")


def norm_chars(ch: str, tier: int) -> list[str]:
    """글자 하나 → 정규화 뒤 글자들. 1단: NFKC → 공백·보이지 않는 글자 제거 → casefold → 따옴표/대시 통일.
    2단: 그 위에 글자·숫자(str.isalnum)만 남긴다."""
    out: list[str] = []
    for c in unicodedata.normalize("NFKC", ch):
        if c in DROP or c.isspace():
            continue
        for cc in c.casefold():
            if cc in QUOTES:
                cc = '"'
            elif cc in DASHES:
                cc = "-"
            if tier >= 2 and not cc.isalnum():
                continue
            out.append(cc)
    return out


def norm_str(s: str, tier: int) -> str:
    return "".join(c for ch in s for c in norm_chars(ch, tier))


def strip_tail(sentence: str) -> str:
    """노트북의 잘림 꼬리 「 ...」를 뗀다."""
    return sentence.removesuffix(TRUNC_TAIL)
