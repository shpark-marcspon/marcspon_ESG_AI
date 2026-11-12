"""JS 의 글자 다루기를 그대로 흉내 내는 도우미. TS 원본과 **같은 자리·같은 갈래**를 내려면 여기를 거친다.

두 언어가 다른 자리(전부 esg-lab `ts/reconcile` 의 정규식·문자열 연산에서 온다):

- 문자열 자리: JS 는 UTF-16 자리, 파이썬은 코드포인트. 보충 평면 글자(U+10000 이상, 이모지)는 JS 에서 두 자리다.
  → `to_units` 로 「UTF-16 자리 하나 = 글자 하나」인 문자열로 바꿔 그 위에서 자르고 찾는다(대행 글자 둘로 쪼갠다).
- `\\s`·`trim()`: JS 는 U+FEFF 를 빈칸으로 보고 U+001C~1F·U+0085 를 빈칸으로 보지 않는다. 파이썬은 반대다.
  → `WS`(정규식의 글자 묶음 안쪽)와 `js_trim`.
- `\\d`: JS 는 ASCII 숫자뿐, 파이썬 `re` 는 유니코드 숫자(아랍-인도 숫자, 전각 숫자)까지. → 정규식에 `[0-9]` 만 쓴다.
- `$`: JS 는 문자열의 끝뿐, 파이썬은 끝의 줄바꿈 앞에서도 맞는다. → `\\Z` 나 `fullmatch`.
- `.`: JS 는 `\\n \\r U+2028 U+2029` 를 안 먹고 파이썬은 `\\n` 만 안 먹는다. → `NOT_LINE_END`.
- `Math.round`: 0.5 를 위로 올린다. 파이썬 `round()` 는 짝수로 간다. → `js_round`.
"""

import math
import re
from typing import Final

# JS 의 WhiteSpace + LineTerminator (ECMA-262 `\s` 와 `String.prototype.trim` 이 같은 집합을 쓴다).
JS_WHITESPACE: Final = "\t\n\x0b\x0c\r                  　﻿"
# 정규식의 글자 묶음 안에 넣는 꼴: `[{WS}]` 가 JS 의 `\s`, `[^{WS}]` 가 `\S`.
WS: Final = "".join(f"\\u{ord(ch):04x}" for ch in JS_WHITESPACE)
# JS 의 `.` 이 먹는 글자 하나(줄 끝 글자 넷을 뺀 것).
NOT_LINE_END: Final = "[^\\n\\r\\u2028\\u2029]"

_SURROGATE: Final = re.compile("[\ud800-\udfff]")
_FIRST_SUPPLEMENTARY: Final = "\U00010000"


def js_trim(text: str) -> str:
    return text.strip(JS_WHITESPACE)


def to_units(text: str) -> str:
    """UTF-16 자리 하나가 글자 하나인 문자열. 보충 평면 글자는 대행 글자 둘(high, low)이 된다.

    그런 글자가 없으면 받은 문자열 그대로다(네 보고서의 블록 글·칸 글에는 하나도 없다).
    """
    if text == "" or max(text) < _FIRST_SUPPLEMENTARY:
        return text
    out: list[str] = []
    for ch in text:
        point = ord(ch)
        if point >= 0x10000:
            point -= 0x10000
            out.append(chr(0xD800 + (point >> 10)))
            out.append(chr(0xDC00 + (point & 0x3FF)))
        else:
            out.append(ch)
    return "".join(out)


def from_units(units: str) -> str:
    """`to_units` 의 거꾸로: 짝이 맞는 대행 글자 둘을 글자 하나로 되돌린다. 짝 없는 것은 그대로 둔다(JS 와 같다)."""
    if _SURROGATE.search(units) is None:
        return units
    return units.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")


def unit_length(text: str) -> int:
    """JS 의 `text.length`."""
    return len(to_units(text))


def unit_slice(text: str, start: int, end: int | None = None) -> str:
    """JS 의 `text.slice(start, end)` (자리는 UTF-16, 음수 자리는 쓰지 않는다)."""
    units = to_units(text)
    return from_units(units[start:end])


def js_round(value: float) -> int:
    """JS 의 `Math.round`: 가장 가까운 정수, 꼭 절반이면 큰 쪽(+∞ 쪽)."""
    floor = math.floor(value)
    return floor + 1 if value - floor >= 0.5 else floor
