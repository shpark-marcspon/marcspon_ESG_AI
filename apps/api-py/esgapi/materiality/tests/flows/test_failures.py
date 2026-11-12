"""흐름 materiality.colab@155 의 실패 갈래(발주서 §3 S4·S5·S6·S8·S10): JSON 아님, 호출 실패·시간 초과, 잘림의 재시도,
실행 비용 상한, 걸음 1 의 함수 호출. 갈래를 접지 않고(§1-7), failure message 에 모델 글·공급사 메시지가 없다.
토픽 하나(호출 셋 — 규제 → 키워드 → 컨트로버시)로 본다. 공급사는 모의만(실호출 0)."""

import math
from typing import Any

import pytest

from esgapi.core.flows.types import FlowInputError, FlowStepFailed
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import Completed, ProviderError, Refusal, TextPart, Truncated, Usage
from esgapi.materiality.contracts import wire
from esgapi.materiality.flows import colab_155
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.support import CALL_USD, USAGE

TOPIC = "가상토픽 하나"
SECRET = "공급사가 돌려준 비밀스러운 메시지"
"""공급사 오류 메시지(결과·기록에 실리면 안 된다)."""


def one_topic() -> dict[str, Any]:
    return support.received(topics=1)


def regulation() -> str:
    return support.regulation_answer(TOPIC)


def keywords() -> str:
    return support.keywords_answer([TOPIC])


def controversy() -> str:
    return support.controversy_answer(TOPIC)


def go(mock: MockProvider, **changes: Any) -> Any:
    given: dict[str, Any] = {"received": one_topic(), **changes}
    return support.run(support.inputs(**given), support.spy(mock))


def topic_of(done: Any) -> dict[str, Any]:
    (only,) = support.result(done)["part1"]["topics"]
    return only


def calls_of(done: Any) -> list[dict[str, Any]]:
    return [call for phase in colab_155.PHASES for call in done.steps[phase].data["calls"]]


def error(status: int | None = 500) -> ProviderError:
    return ProviderError(status=status, retryable=False, message=SECRET)


def assert_no_secret(done: Any) -> None:
    text = repr(support.result(done)) + repr([done.steps[p].data for p in colab_155.PHASES])
    assert SECRET not in text


# ── S4 JSON 아님 ───────────────────────────────────────────────────────────────────────────


def test_answers_without_an_object_are_unparsable_with_the_ir1a_wording() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text("가상 답 — 객체가 없다", USAGE).enqueue_text(keywords(), USAGE)
    mock.enqueue_text("가상 답 — 역시 객체가 없다", USAGE)
    topic = topic_of(go(mock))
    assert topic["regulation"] == {
        "status": "failed",
        "raw": "가상 답 — 객체가 없다",
        "parseError": "No JSON object start '{' found",
        "failure": {"kind": "unparsable", "message": wire.UNPARSABLE},
    }
    assert topic["controversy"]["parseError"] == "ValueError(\"No JSON object start '{' found\")"  # repr(W8)
    assert topic["controversy"]["failure"]["kind"] == "unparsable"


def test_unparsable_keywords_mean_no_keywords_for_every_topic() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text(regulation(), USAGE).enqueue_text("가상 키워드 답 — JSON 없음", USAGE)
    mock.enqueue_text(controversy(), USAGE)
    done = go(mock)
    (part,) = mock.calls[2].user
    assert isinstance(part, TextPart)
    assert "keyword: (키워드 없음)\n" in part.text
    kw = support.result(done)["part1"]["keywords"]
    assert kw["status"] == "failed"
    assert kw["raw"] == "가상 키워드 답 — JSON 없음"
    assert kw["failure"] == {"kind": "unparsable", "message": "JSON 블록({ ... })을 찾지 못했다"}
    assert topic_of(done)["keywordStr"] == "(키워드 없음)"


# ── S5 호출 실패 ───────────────────────────────────────────────────────────────────────────


def test_call_failures_keep_their_core_kind_and_carry_no_provider_message() -> None:
    mock = MockProvider("openai")
    mock.enqueue(error(500)).enqueue(error(None)).enqueue(error(429))
    done = go(mock)
    topic = topic_of(done)
    # 규제: 코랩 None 은 빈 글 → 「Empty LLM output」(W8), raw ""
    assert topic["regulation"] == {
        "status": "failed",
        "raw": "",
        "parseError": "Empty LLM output",
        "failure": {"kind": "provider_error", "message": "provider_error status=500"},
    }
    # 키워드: raw null·core 갈래, 컨트로버시는 전부 (키워드 없음)
    assert support.result(done)["part1"]["keywords"] == {
        "status": "failed",
        "raw": None,
        "failure": {"kind": "provider_error", "message": "provider_error status=none"},
    }
    assert topic["keywordStr"] == "(키워드 없음)"
    # 컨트로버시: no_result
    assert topic["controversy"] == {
        "status": "failed",
        "raw": "",
        "parseError": "no_result",
        "failure": {"kind": "provider_error", "message": "provider_error status=429"},
    }
    assert [(c["ending"], c["attempts"]) for c in calls_of(done)] == [("provider_error", 1)] * 3
    assert_no_secret(done)


def test_a_slow_provider_is_a_timeout() -> None:
    mock = MockProvider("openai")
    mock.enqueue_text(regulation(), USAGE, hosted_calls=1)
    mock.enqueue(mock_reply(keywords()), delay_ms=colab_155.TIMEOUT_MS)
    mock.enqueue_text(controversy(), USAGE)
    done = go(mock)
    assert support.result(done)["part1"]["keywords"]["failure"] == {"kind": "timeout", "message": "timeout"}
    assert calls_of(done)[1]["ending"] == "timeout"


def mock_reply(text: str) -> Completed:
    return Completed(text=text, usage=USAGE)


# ── S6 incomplete ──────────────────────────────────────────────────────────────────────────


def test_a_cut_off_answer_is_asked_once_more_with_the_same_bytes() -> None:
    mock = MockProvider("openai")
    mock.enqueue(Truncated(text='{"topic_name": "가상', usage=USAGE)).enqueue_text(regulation(), USAGE)
    mock.enqueue_text(keywords(), USAGE).enqueue_text(controversy(), USAGE)
    done = go(mock)
    assert len(mock.calls) == 4
    assert mock.calls[0] == mock.calls[1]
    assert topic_of(done)["regulation"]["status"] == "done"
    first = calls_of(done)[0]
    assert (first["ending"], first["attempts"], first["costUsd"]) == ("done", 2, round(2 * CALL_USD, 6))


def test_two_cut_offs_keep_the_second_partial_text_as_truncated() -> None:
    mock = MockProvider("openai")
    mock.enqueue(Truncated(text="첫 부분 글", usage=USAGE)).enqueue(Truncated(text="둘째 부분 글", usage=USAGE))
    mock.enqueue_text(keywords(), USAGE).enqueue_text(controversy(), USAGE)
    done = go(mock)
    assert topic_of(done)["regulation"] == {
        "status": "failed",
        "raw": "둘째 부분 글",
        "parseError": "No JSON object start '{' found",
        "failure": {"kind": "truncated", "message": "truncated"},
    }
    assert (calls_of(done)[0]["ending"], calls_of(done)[0]["attempts"]) == ("truncated", 2)


def test_a_content_filter_is_a_refusal_without_retry() -> None:
    mock = MockProvider("openai")
    mock.enqueue(Refusal(text="", category="content_filter", usage=USAGE))
    mock.enqueue_text(keywords(), USAGE).enqueue_text(controversy(), USAGE)
    done = go(mock)
    assert len(mock.calls) == 3
    assert topic_of(done)["regulation"]["failure"] == {"kind": "refusal", "message": "refusal"}
    assert calls_of(done)[0]["attempts"] == 1


# ── S8 돈 문 ───────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", [None, 0, 0.0, -1.0, math.nan, math.inf, True, "1.0"])
def test_a_missing_or_bad_cap_stops_before_any_call(value: object) -> None:
    mock = MockProvider("openai")
    with pytest.raises(FlowStepFailed) as raised:
        go(mock, max_cost_usd=value)
    assert isinstance(raised.value.__cause__, FlowInputError)
    assert mock.calls == []


def test_the_cap_reached_after_the_second_call_stops_the_rest() -> None:
    mock = MockProvider("openai")
    support.script_all(mock, support.received(topics=3))
    given = support.inputs(received=support.received(topics=3), max_cost_usd=2 * CALL_USD)
    done = support.run(given, support.spy(mock))
    assert len(mock.calls) == 2
    endings = [c["ending"] for c in calls_of(done)]
    assert endings == ["done", "done", *["budget_exceeded"] * 5]
    assert [c["attempts"] for c in calls_of(done)][2:] == [0] * 5
    topics = support.result(done)["part1"]["topics"]
    assert topics[2]["regulation"]["failure"] == {"kind": "budget_exceeded", "message": "budget_exceeded (run)"}
    assert support.result(done)["part1"]["keywords"]["failure"]["kind"] == "budget_exceeded"
    assert {t["controversy"]["parseError"] for t in topics} == {"no_result"}


def test_the_cap_is_also_checked_before_the_retry() -> None:
    """첫 호출이 잘렸고 그 비용으로 상한에 닿으면 재시도를 부르지 않는다 — 첫 부분 글도 쓰지 않는다."""
    mock = MockProvider("openai")
    mock.enqueue(Truncated(text="첫 부분 글", usage=USAGE))
    done = go(mock, max_cost_usd=CALL_USD)
    assert len(mock.calls) == 1
    first = calls_of(done)[0]
    assert (first["ending"], first["attempts"]) == ("budget_exceeded", 1)
    assert topic_of(done)["regulation"]["raw"] == ""  # 부분 글을 버린다(호출 실패와 같은 묶음)


def test_a_cost_of_none_counts_as_zero() -> None:
    """사용량이 없는 시도(시간 초과)는 cost_usd None — 누계에 0 으로 든다."""
    mock = MockProvider("openai")
    mock.enqueue(mock_reply(regulation()), delay_ms=colab_155.TIMEOUT_MS)
    mock.enqueue_text(keywords(), USAGE).enqueue_text(controversy(), USAGE)
    done = go(mock, max_cost_usd=CALL_USD + 0.001)
    assert calls_of(done)[0]["costUsd"] == 0.0
    assert done.steps["regulation"].data["spentUsd"] == 0.0
    assert [c["ending"] for c in calls_of(done)] == ["timeout", "done", "done"]


# ── S10 부분 ───────────────────────────────────────────────────────────────────────────────


def test_a_function_call_in_the_single_step_is_a_provider_error() -> None:
    mock = MockProvider("openai")
    mock.enqueue_tool_calls([("look_up", "{}")], usage=Usage(10, 1, 0, 0))
    mock.enqueue_text(keywords(), USAGE).enqueue_text(controversy(), USAGE)
    done = go(mock)
    assert topic_of(done)["regulation"]["failure"] == {
        "kind": "provider_error",
        "message": "provider_error unexpected_function_call",
    }
    assert calls_of(done)[0]["ending"] == "partial"
