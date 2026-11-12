"""engines/colab_155/parsing.py: extract_json_obj(코랩 셀 8 — 값·예외 타입·문구), strip_utm(W7), 키워드 파싱(셀 20 의
탐욕 정규식 W6·처분 ⑩ 가), keyword_str(셀 22)(발주서 §3 S4). 코랩 코드와의 값 견줌은 section4 7단계."""

import json
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from esgapi.materiality.engines.colab_155 import parsing


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('앞 글 {"a": {"b": [1, 2]}} 뒤 글', {"a": {"b": [1, 2]}}),
        ('```json\n{"a": "x"}\n```', {"a": "x"}),
        ('{"a": "괄호 } 안"}', {"a": "괄호 } 안"}),
        ('{"a": "따옴표 \\" 와 } 괄호"}', {"a": '따옴표 " 와 } 괄호'}),
        ('{"a": "역빗금 \\\\"} 뒤', {"a": "역빗금 \\"}),
        ('{"a": 1} {"b": 2}', {"a": 1}),  # 두 객체면 첫 것
        ('  \n{"중첩": {"x": {"y": {}}}}  ', {"중첩": {"x": {"y": {}}}}),
    ],
)
def test_extract_json_obj_values(text: str, expected: dict[str, Any]) -> None:
    assert parsing.extract_json_obj(text) == expected


@pytest.mark.parametrize(
    ("text", "kind", "message"),
    [
        ("", ValueError, "Empty LLM output"),
        ("   \n ", ValueError, "Empty LLM output"),
        ("설명만", ValueError, "No JSON object start '{' found"),
        ('{"a": 1', ValueError, "No complete JSON object found (unbalanced braces)"),
        ('{"a": "}', ValueError, "No complete JSON object found (unbalanced braces)"),
        (
            '{"a": 1,}',
            json.JSONDecodeError,
            "Illegal trailing comma before end of object: line 1 column 8 (char 7)",
        ),
        (
            "{'a': 1}",
            json.JSONDecodeError,
            "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
        ),
    ],
)
def test_extract_json_obj_failures(text: str, kind: type[Exception], message: str) -> None:
    with pytest.raises(kind) as caught:
        parsing.extract_json_obj(text)
    assert type(caught.value) is kind
    assert str(caught.value) == message


JSON_VALUES = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=8),
    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=4), inner, max_size=3),
    max_leaves=8,
)


@settings(derandomize=True, max_examples=200, database=None)
@given(
    obj=st.dictionaries(st.text(max_size=6), JSON_VALUES, max_size=4),
    before=st.text(alphabet="가 ab:\n`", max_size=6),
    after=st.text(alphabet="가 ab:}\n`{", max_size=6),
    ascii_only=st.booleans(),
)
def test_extract_json_obj_reads_back_any_dict(obj: dict[str, Any], before: str, after: str, ascii_only: bool) -> None:
    """dict → json 글(앞뒤에 다른 글) → 같은 dict. 앞 글에 `{` 가 없어야 첫 `{` 가 그 객체다."""
    text = before + json.dumps(obj, ensure_ascii=ascii_only) + after
    assert parsing.extract_json_obj(text) == obj


def test_strip_utm_removes_only_the_two_forms() -> None:
    text = "https://a.go.kr/x?utm_source=openai · https://b.go.kr/y?k=1&utm_source=openai · ?utm_source=openai&k=2"
    assert parsing.strip_utm(text) == "https://a.go.kr/x · https://b.go.kr/y?k=1 · &k=2"
    kept = "https://c.go.kr/z?utm_source=other&utm_medium=openai"
    assert parsing.strip_utm(kept) == kept  # W7: 다른 utm 꼴은 그대로


def parsed(text: str) -> parsing.KeywordsParsed:
    out = parsing.parse_keywords(text)
    assert isinstance(out, parsing.KeywordsParsed)
    return out


def test_keywords_are_read_in_answer_order() -> None:
    out = parsed(
        '앞 ```json\n{"topics": [{"topic": "가상 둘", "keywords": ["가"]},'
        ' {"topic": "가상 하나", "keywords": []}]}\n```'
    )
    assert list(out.by_topic.items()) == [("가상 둘", ["가"]), ("가상 하나", [])]
    assert out.duplicates == ()


def test_a_duplicated_topic_keeps_its_first_place_and_the_last_keywords() -> None:
    """W6: 코랩 dict 컴프리헨션 — 같은 토픽이면 뒤 것의 값, 자리는 첫 것."""
    out = parsed(
        '{"topics": [{"topic": "가상 하나", "keywords": ["가"]}, {"topic": "가상 둘", "keywords": ["나"]},'
        ' {"topic": "가상 하나", "keywords": ["다"]}, {"topic": "가상 하나", "keywords": ["라"]}]}'
    )
    assert list(out.by_topic.items()) == [("가상 하나", ["라"]), ("가상 둘", ["나"])]
    assert out.duplicates == ("가상 하나",)


def test_the_greedy_pattern_spans_two_objects_and_fails() -> None:
    """W6: `\\{[\\s\\S]*\\}` 는 첫 `{` 부터 마지막 `}` 까지 — 객체 둘이면 JSON 이 아니다(코랩은 {})."""
    out = parsing.parse_keywords('{"topics": []} 설명 {"x": 1}')
    assert isinstance(out, parsing.KeywordsUnparsable)
    assert out.reason.startswith("JSON 파싱 오류")


def test_missing_topics_is_an_empty_mapping() -> None:
    assert parsed('{"other": 1}').by_topic == {}
    assert parsed('{"topics": []}').by_topic == {}


@pytest.mark.parametrize(
    "text",
    [
        "객체 없음",
        '{"topics": [',
        '{"topics": [{"topic": "가상 하나"}]}',  # KeyError — 코랩은 멈춘다(⑩)
        '{"topics": [{"keywords": ["가"]}]}',
        '{"topics": {"topic": "가상 하나"}}',  # dict 를 돌면 키 글 → TypeError
        '{"topics": ["가상 하나"]}',
        '{"topics": "가상"}',
        '{"topics": [{"topic": "가상 하나", "keywords": "가, 나"}]}',  # list[str] 아님(⑩)
        '{"topics": [{"topic": "가상 하나", "keywords": [1, 2]}]}',
        '{"topics": [{"topic": 1, "keywords": ["가"]}]}',
        '{"topics": [{"topic": ["가"], "keywords": ["가"]}]}',
    ],
)
def test_what_the_colab_cannot_read_is_unparsable(text: str) -> None:
    out = parsing.parse_keywords(text)
    assert isinstance(out, parsing.KeywordsUnparsable)
    assert "가상" not in out.reason  # 모델 글을 싣지 않는다


def test_keyword_str() -> None:
    by_topic = {"가상 하나": ["가", "나"], "가상 둘": []}
    assert parsing.keyword_str(by_topic, "가상 하나") == "가, 나"
    assert parsing.keyword_str(by_topic, "가상 둘") == "(키워드 없음)"
    assert parsing.keyword_str(by_topic, "가상 셋") == "(키워드 없음)"  # W6: 토픽명이 다르면 조용히
    assert parsing.NO_KEYWORDS == "(키워드 없음)"
