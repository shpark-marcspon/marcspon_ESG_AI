"""engines/colab_156/schemas.py 의 도구 스키마 상수(코랩 R/387-514)가 고정한 지문과 손으로 적은 꼴을 지키는가
(발주서 DV1a §3 S5, DV1c 감독 결정 ⑥). 코랩 상수와의 견줌은 esg-lab `py/dvcolab`(MARC-ENT-310).
"""

import hashlib
import json

from esgapi.dataverify.engines.colab_156 import schemas

# json.dumps(TOOLS_RESPONSES, ensure_ascii=False, sort_keys=False) 의 sha256
# — 글자 하나(description 등)가 바뀌어도 빨갛다.
# BASE ccd3194 엔진에서 잰 값이다. DV1a 가 그 값이 코랩 상수와 같음을 보였다(손셈 원칙의 예외 — 발주서 §7-5).
TOOLS_SHA256 = "99f13cb04ccd5f496d743729dab619ab534915c970e2617f4ac89e7e46ab4b5d"

REQUIRED_BY_HAND = {
    "value_of_by_name": ["대분류", "중분류", "소분류", "단위", "year"],
    "sum_check": ["a", "b", "c", "tolerance"],
    "sum_n_check": ["addends", "target", "tolerance"],
    "ratio_check": ["d", "e", "f", "tolerance"],
    "sum_check_by_name": ["total", "a", "b", "years", "tolerance"],
    "sum_n_check_by_names": ["addends", "target", "years", "tolerance"],
    "ratio_check_by_name": ["numerator", "denominator", "expected", "years", "tolerance"],
}


def test_the_function_tools_keep_their_sha256() -> None:
    text = json.dumps(schemas.TOOLS_RESPONSES, ensure_ascii=False, sort_keys=False)
    assert hashlib.sha256(text.encode()).hexdigest() == TOOLS_SHA256


def test_the_web_search_tool() -> None:
    assert schemas.TOOLS_RESPONSES_websearch == [{"type": "web_search", "search_context_size": "medium"}]


def test_the_required_arguments_by_hand() -> None:
    got = {tool["name"]: tool["parameters"].get("required") for tool in schemas.TOOLS_RESPONSES}
    assert got == {**REQUIRED_BY_HAND, "search_items": None}  # search_items 는 required 가 없다


def test_there_are_eight_function_tools() -> None:
    names = [tool["name"] for tool in schemas.TOOLS_RESPONSES]
    assert names == [
        "value_of_by_name",
        "sum_check",
        "sum_n_check",
        "ratio_check",
        "sum_check_by_name",
        "sum_n_check_by_names",
        "ratio_check_by_name",
        "search_items",
    ]
    assert all(tool["type"] == "function" and "strict" not in tool for tool in schemas.TOOLS_RESPONSES)
