"""자바스크립트의 String()·JSON.stringify()·문자열 비교 흉내. 순수 층.

기대값은 JS 의 규칙에서 옮긴 것이다. TS 엔진이 실제로 낸 글자와의 대조는 test_golden.py 가 한다
(f-invalid-tables.stderr.txt, e-ordering.json, c-unknown-source.json).
"""

from typing import Any

import pytest

from esgapi.inventory.tools.jsrepr import MISSING, as_integer, js_entries, js_json, js_sort_key, js_string


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "null"),  # 파이썬의 str(None) 은 "None" 이다
        (MISSING, "undefined"),
        (True, "true"),  # 파이썬의 str(True) 는 "True" 다
        (False, "false"),
        ("x", "x"),
        (1, "1"),
        (2, "2"),
        (-7, "-7"),
        (2.0, "2"),
        (1.5, "1.5"),
        (-0.0, "0"),
        (0.1, "0.1"),
        (123456.789, "123456.789"),
        (1e21, "1e+21"),
        (1e20, "100000000000000000000"),
        (1e-6, "0.000001"),
        (1e-7, "1e-7"),
        (1.5e-10, "1.5e-10"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
        (5e-324, "5e-324"),
        (2**53, "9007199254740992"),
        (2**53 + 1, "9007199254740992"),  # JS 의 수는 배정밀도다
        (123456789012345678901234567890, "1.2345678901234568e+29"),
        (10**400, "Infinity"),
        (float("nan"), "NaN"),
        (float("-inf"), "-Infinity"),
        ([], ""),
        ([1, None, "a", [2, 3]], "1,,a,2,3"),
        ({"a": 1}, "[object Object]"),
    ],
)
def test_js_string(value: Any, expected: str) -> None:
    assert js_string(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (MISSING, "undefined"),
        (None, "null"),
        (True, "true"),
        ("-21", '"-21"'),
        ('a"b\\c\n\t\x01', '"a\\"b\\\\c\\n\\t\\u0001"'),
        ("한글 😀", '"한글 😀"'),
        ("\ud83d", '"\\ud83d"'),  # 짝 없는 서러게이트
        (0.001, "0.001"),
        (float("nan"), "null"),
        (float("inf"), "null"),
        ([1, "2", None, [2.5]], '[1,"2",null,[2.5]]'),
        ({"b": 1, "10": "x", "2": [True], "a": {"k": None}}, '{"2":[true],"10":"x","b":1,"a":{"k":null}}'),
        ({}, "{}"),
        ([], "[]"),
    ],
)
def test_js_json(value: Any, expected: str) -> None:
    assert js_json(value) == expected


def test_js_entries_puts_array_index_keys_first_in_numeric_order() -> None:
    obj: dict[str, object] = {"b": 1, "10": 2, "2": 3, "01": 4, "-1": 5, "4294967295": 6, "a": 7}
    assert [key for key, _ in js_entries(obj)] == ["2", "10", "b", "01", "-1", "4294967295", "a"]


def test_js_sort_key_orders_by_utf16_code_units() -> None:
    emoji, yen = "😀", "￥"  # U+1F600 (서러게이트 D83D DE00), U+FFE5
    assert emoji > yen  # 파이썬: 코드 포인트 순
    assert js_sort_key(emoji) < js_sort_key(yen)  # JS: 코드 단위 순
    assert sorted(["b", "a", "가", "Z"], key=js_sort_key) == ["Z", "a", "b", "가"]
    assert js_sort_key("\ud800") < js_sort_key("")  # 짝 없는 서러게이트로도 던지지 않는다


@pytest.mark.parametrize(
    ("value", "expected"),
    [(2, 2), (2.0, 2), (-3, -3), (0, 0), (2.5, None), (True, None), (False, None), ("2", None), (None, None)],
)
def test_as_integer_takes_json_integers_and_never_bools(value: Any, expected: int | None) -> None:
    result = as_integer(value)
    assert result == expected
    assert result is None or type(result) is int
