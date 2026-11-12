"""engines/colab_155/outcomes.py: 답 글(또는 호출 실패) → 코랩 묶음, 키 차례까지(W8·W9)(발주서 §3 S6)."""

from typing import Any

from esgapi.materiality.engines.colab_155 import outcomes

TOPIC = "가상토픽 하나"
GOOD = '{"topic_name": "가상토픽 하나", "u": "https://example.go.kr/a?utm_source=openai"}'


def items(bundle: dict[str, Any]) -> list[tuple[str, Any]]:
    return list(bundle.items())


def test_regulation_success_strips_utm_and_keeps_raw_empty() -> None:
    assert items(outcomes.regulation_bundle(GOOD)) == [
        ("parsed", {"topic_name": TOPIC, "u": "https://example.go.kr/a"}),
        ("raw", None),
        ("parse_error", None),
    ]


def test_regulation_call_failure_and_empty_answer_are_the_same_branch() -> None:
    """W8: 코랩 셀 17 은 호출 실패(None)와 빈 답을 같은 갈래로 — 둘 다 「Empty LLM output」, str(예외)."""
    expected = [("parsed", None), ("raw", ""), ("parse_error", "Empty LLM output")]
    assert items(outcomes.regulation_bundle(None)) == expected
    assert items(outcomes.regulation_bundle("")) == expected


def test_regulation_failures_keep_the_text_and_str_of_the_error() -> None:
    assert items(outcomes.regulation_bundle("가상 설명?utm_source=openai")) == [
        ("parsed", None),
        ("raw", "가상 설명"),
        ("parse_error", "No JSON object start '{' found"),
    ]
    out = outcomes.regulation_bundle('{"a": 1,}')
    assert out["parse_error"] == "Illegal trailing comma before end of object: line 1 column 8 (char 7)"
    assert outcomes.regulation_bundle("   ")["raw"] == "   "  # 공백 글은 지우지 않고 그대로


def test_regulation_does_not_compare_the_topic_name() -> None:
    out = outcomes.regulation_bundle('{"topic_name": "다른 이름"}')
    assert out["parsed"] == {"topic_name": "다른 이름"}  # W9: 셀 17 은 topic_name_expected 를 안 더한다


def test_controversy_call_failure_is_no_result() -> None:
    assert items(outcomes.controversy_bundle(None, TOPIC)) == [
        ("json", None),
        ("raw_text", ""),
        ("parse_error", "no_result"),
    ]


def test_controversy_empty_answer_is_repr_of_the_error() -> None:
    """W8: 셀 22 는 repr(예외)."""
    assert items(outcomes.controversy_bundle("", TOPIC)) == [
        ("json", None),
        ("raw_text", ""),
        ("parse_error", "ValueError('Empty LLM output')"),
    ]
    out = outcomes.controversy_bundle("{'a': 1}", TOPIC)
    assert out["parse_error"] == (
        "JSONDecodeError('Expecting property name enclosed in double quotes: line 1 column 2 (char 1)')"
    )
    assert out["raw_text"] == "{'a': 1}"


def test_controversy_success_and_topic_name_mismatch() -> None:
    assert items(outcomes.controversy_bundle(GOOD, TOPIC)) == [
        ("json", {"topic_name": TOPIC, "u": "https://example.go.kr/a"}),
        ("raw_text", None),
        ("parse_error", None),
    ]
    out = outcomes.controversy_bundle('{"topic_name": "다른 이름", "results": {}}', TOPIC)
    assert list(out["json"].items()) == [  # W9: 끝에 topic_name_expected
        ("topic_name", "다른 이름"),
        ("results", {}),
        ("topic_name_expected", TOPIC),
    ]
    assert outcomes.controversy_bundle("{}", TOPIC)["json"] == {"topic_name_expected": TOPIC}
