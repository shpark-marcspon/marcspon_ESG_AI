"""자바스크립트의 String(값)·JSON.stringify(값)·문자열 비교를 흉내 낸다.

왜 필요한가: esg-lab 의 TS 엔진이 내던 문자열을 글자까지 그대로 내야 하는 자리가 넷 있다.
  - 묶음 키: `String(row[k])` — None 은 "null" 이다(파이썬 str() 은 "None").
  - 묶음의 순서: `JSON.stringify(키 배열)` 을 문자열로 견준 순서. JS 의 문자열 비교는 UTF-16 코드 단위 순이다.
  - 표 검사의 문제 문장: `음수다: ${JSON.stringify(value)}` — 문자열은 따옴표째, 없는 키는 "undefined".
  - 실패 갈래의 value: `String(row.amount)` — 수 1000 은 "1000", 없는 키는 "undefined".

받는 값은 json.loads 가 내는 것들이다(dict, list, str, int, float, bool, None)와, 「키가 없음」을 뜻하는 MISSING.
"""

import enum
import json
import math
import re
from typing import Final, Literal, cast


class _Missing(enum.Enum):
    MISSING = enum.auto()


# JS 의 undefined: 객체에 그 키가 없다. None(JS 의 null)과 다르다.
MISSING: Final = _Missing.MISSING
type Missing = Literal[_Missing.MISSING]

_SAFE_INTEGER: Final = 2**53
_LONE_SURROGATE: Final = re.compile(r"[\ud800-\udfff]")
_ARRAY_INDEX: Final = re.compile(r"0|[1-9][0-9]{0,9}")


def get(obj: dict[str, object], key: str) -> object:
    """obj[key]. 키가 없으면 MISSING (JS 에서 없는 속성을 읽으면 undefined 인 것과 같다)."""
    return obj.get(key, MISSING)


def as_object(value: object) -> dict[str, object] | None:
    """JSON 의 객체면 그 dict, 아니면 None. (JS: typeof v === "object" && v !== null && !Array.isArray(v))"""
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def as_array(value: object) -> list[object] | None:
    """JSON 의 배열이면 그 list, 아니면 None. (JS: Array.isArray(v))"""
    return cast("list[object]", value) if isinstance(value, list) else None


def _js_float(value: float) -> str:
    """Number.prototype.toString. 파이썬의 repr 과 자릿수는 같고(둘 다 가장 짧은 표기) 지수로 넘어가는 자리가 다르다."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    mantissa, _, exponent = repr(abs(value)).partition("e")
    int_part, _, frac_part = mantissa.partition(".")
    digits = int_part + frac_part
    # 값 = 0.<digits> × 10^n
    n = len(int_part) + (int(exponent) if exponent else 0)
    stripped = digits.lstrip("0")
    n -= len(digits) - len(stripped)
    digits = stripped.rstrip("0")
    k = len(digits)
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return f"{sign}{digits[:n]}.{digits[n:]}"
    if -6 < n <= 0:
        return f"{sign}0.{'0' * -n}{digits}"
    e = n - 1
    head = digits[0] + ("." + digits[1:] if k > 1 else "")
    return f"{sign}{head}e{'+' if e >= 0 else '-'}{abs(e)}"


def _js_number(value: int | float) -> str:
    if isinstance(value, int):
        if abs(value) <= _SAFE_INTEGER:
            return str(value)
        # JS 의 수는 전부 배정밀도다. 2^53 을 넘는 JSON 정수는 읽을 때 이미 둥글려진다.
        try:
            return _js_float(float(value))
        except OverflowError:
            return "Infinity" if value > 0 else "-Infinity"
    return _js_float(value)


def js_string(value: object) -> str:
    """String(value)."""
    if value is MISSING:
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return _js_number(value)
    items = as_array(value)
    if items is not None:
        # Array.prototype.join: null 과 undefined 는 빈 문자열이 된다.
        return ",".join("" if item is None or item is MISSING else js_string(item) for item in items)
    if isinstance(value, dict):
        return "[object Object]"
    return str(value)


def _quote(text: str) -> str:
    # json.dumps(ensure_ascii=False) 와 JSON.stringify 는 짝 없는 서러게이트만 다르다(JS 는 \udxxx 로 적는다).
    return _LONE_SURROGATE.sub(lambda m: f"\\u{ord(m.group()):04x}", json.dumps(text, ensure_ascii=False))


def _own_keys(obj: dict[str, object]) -> list[str]:
    """JS 객체의 키 순서: 배열 인덱스 꼴의 키가 수의 순서로 먼저, 나머지는 넣은 순서."""
    indexes = sorted((key for key in obj if _ARRAY_INDEX.fullmatch(key) and int(key) < 2**32 - 1), key=int)
    index_set = set(indexes)
    return indexes + [key for key in obj if key not in index_set]


def js_entries(obj: dict[str, object]) -> list[tuple[str, object]]:
    """Object.entries(obj)."""
    return [(key, obj[key]) for key in _own_keys(obj)]


def js_json(value: object) -> str:
    """`${JSON.stringify(value)}` — 들여쓰기 없는 JSON. 없는 키(MISSING)는 "undefined" 다."""
    if value is MISSING:
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, (int, float)):
        text = _js_number(value)
        return "null" if text in ("NaN", "Infinity", "-Infinity") else text
    items = as_array(value)
    if items is not None:
        return "[" + ",".join(js_json(item) for item in items) + "]"
    obj = as_object(value)
    if obj is not None:
        return "{" + ",".join(f"{_quote(key)}:{js_json(item)}" for key, item in js_entries(obj)) + "}"
    return "null"


def js_sort_key(text: str) -> bytes:
    """JS 의 `a < b`(문자열)와 같은 순서를 주는 정렬 키: UTF-16 코드 단위의 순서.

    파이썬의 문자열 비교는 코드 포인트 순이라, BMP 밖의 글자(이모지 등)와 U+E000 뒤의 글자가 섞이면 순서가 갈린다.
    """
    return text.encode("utf-16-be", errors="surrogatepass")


def as_integer(value: object) -> int | None:
    """JSON 의 수가 정수면 그 값, 아니면 None. bool 은 수가 아니다(파이썬에서는 int 의 하위 타입이라 type 으로 가른다).

    JSON 에는 정수와 실수의 구분이 없다: `2.0` 은 JS 에서 2 와 같은 값이므로 여기서도 2 로 받는다.
    """
    if type(value) is int:
        return value
    if type(value) is float and value.is_integer():
        return int(value)
    return None
