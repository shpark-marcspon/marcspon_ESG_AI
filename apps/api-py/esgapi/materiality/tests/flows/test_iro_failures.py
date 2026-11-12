"""1부 → 2부 한 실행(flows/iro_155.py)의 갈래(밴드 IR2b — 발주서 §3 S6·S7·S9): 입력 거부(dateRange·today·토픽
이름 겹침 — 공급사 호출 0), 1부 잘림 경고, 돈 문 하나가 두 부를 덮음. 공급사는 모의만. 기대값은 손셈."""

from datetime import datetime
from typing import Any, cast

import pytest

from esgapi.core.flows.types import FlowInputError, FlowStepFailed
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import Truncated
from esgapi.materiality.flows import part2_155
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.support import CALL_USD, SEARCH_USD, USAGE

PART1_CALL = CALL_USD + SEARCH_USD
"""1부 호출 하나(토큰 0.045 + web_search 1건 0.01)."""


def rejected(received: dict[str, Any], **changes: Any) -> FlowStepFailed:
    mock = MockProvider("openai")
    support.script_iro(mock, received)
    with pytest.raises(FlowStepFailed) as raised:
        support.run_iro(support.iro_inputs(received, **changes), support.spy2(mock))
    assert raised.value.step == "load"
    assert isinstance(raised.value.__cause__, FlowInputError)
    assert mock.calls == []
    return raised.value


# ── S6 입력 거부 ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "date_range",
    ["최근 1년", "", "2024-01-01", "2025-02-29~오늘까지", "2025-01-02~2025-01-01", "2025-07-01~오늘까지"],
)
def test_a_bad_date_range_stops_before_any_call(date_range: str) -> None:
    received = support.received2()
    received["dateRange"] = date_range
    failed = rejected(received)
    message = str(failed.__cause__)
    assert message.startswith("dateRange 문법 밖")
    if date_range:
        assert date_range not in message  # 받은 글은 싣지 않는다


@pytest.mark.parametrize("today", [None, datetime(2025, 6, 30, 9, 0), "2025-06-30", True, 20250630])
def test_a_missing_or_wrong_today_stops_before_any_call(today: object) -> None:
    failed = rejected(support.received2(), today=today)
    assert str(failed.__cause__).startswith("today 는 date 여야 한다")


def test_duplicate_topic_names_stop_before_any_call() -> None:
    received = support.received2()
    received["topics"][1]["topic"] = received["topics"][0]["topic"]
    failed = rejected(received)
    assert "materiality.input@1 꼴이 아니다" in str(failed.__cause__)


def test_a_bad_input_shape_is_checked_before_the_date_range() -> None:
    received = support.received2()
    del received["dateRange"]
    failed = rejected(received)
    assert "materiality.input@1 꼴이 아니다" in str(failed.__cause__)


# ── S7 1부 잘림 ────────────────────────────────────────────────────────────────────────────


def script_cut_regulation(mock: MockProvider, received: dict[str, Any], *, second: str | None) -> None:
    """첫 토픽 규제가 한 번 잘리고, second 가 None 이면 재시도도 잘림, 아니면 재시도에서 그 답으로 끝남."""
    names = support.topic_names(received)
    mock.enqueue(Truncated(text='{"topic_name": "가상', usage=USAGE))
    if second is None:
        mock.enqueue(Truncated(text='{"topic_name": "가상 둘째', usage=USAGE))
    else:
        mock.enqueue_text(second, USAGE, hosted_calls=1)
    mock.enqueue_text(support.regulation_answer_dated(names[1]), USAGE, hosted_calls=1)
    mock.enqueue_text(support.keywords_answer(names), USAGE, hosted_calls=1)
    for name in names:
        mock.enqueue_text(support.controversy_answer_dated(name), USAGE, hosted_calls=1)
    support.script_part2(mock)


def test_part1_truncation_after_the_retry_becomes_one_warning() -> None:
    received = support.received2()
    mock = MockProvider("openai")
    script_cut_regulation(mock, received, second=None)
    done = support.run_iro(support.iro_inputs(received), support.spy2(mock))
    result = support.result(done)
    assert len(mock.calls) == 15
    truncated = [w for w in result["warnings"] if w["code"] == "answer_truncated"]
    assert truncated == [
        {
            "code": "answer_truncated",
            "message": "답이 출력 상한에서 잘렸다(읽혔으면 그 부분으로 done, 못 읽었으면 failed·truncated).",
            "topic": "가상토픽 하나",
            "phase": "regulation",
            "subtopic": None,
        }
    ]
    assert result["part1"]["topics"][0]["regulation"]["failure"]["kind"] == "truncated"
    assert result["part2"]["topics"][0]["subtopics"][0]["impact"]["status"] == "done"


def test_part1_retry_that_finishes_leaves_no_warning() -> None:
    received = support.received2()
    mock = MockProvider("openai")
    script_cut_regulation(mock, received, second=support.regulation_answer_dated(support.topic_names(received)[0]))
    done = support.run_iro(support.iro_inputs(received), support.spy2(mock))
    result = support.result(done)
    assert len(mock.calls) == 15
    assert [w for w in result["warnings"] if w["code"] == "answer_truncated"] == []


# ── S9 돈 문 하나가 두 부를 덮는다 ───────────────────────────────────────────────────────────


def calls(done: Any, *steps: str) -> list[dict[str, Any]]:
    return [c for step in steps for c in cast("list[dict[str, Any]]", done.steps[step].data["calls"])]


def test_the_cap_reached_in_part1_stops_part1_and_all_of_part2() -> None:
    received = support.received2()
    mock = MockProvider("openai")
    support.script_iro(mock, received)
    done = support.run_iro(support.iro_inputs(received, max_cost_usd=3 * PART1_CALL), support.spy2(mock))
    assert len(mock.calls) == 3  # 규제 둘 + 키워드, 컨트로버시부터 안 부름
    assert [c["ending"] for c in calls(done, "controversy")] == ["budget_exceeded"] * 2
    assert [c["ending"] for c in calls(done, *part2_155.PHASES2)] == ["budget_exceeded"] * 6  # pathway 는 부르지 않음
    result = support.result(done)
    for t in result["part2"]["topics"]:
        for s in t["subtopics"]:
            assert s["impact"]["failure"] == {"kind": "budget_exceeded", "message": "budget_exceeded (run)"}
            assert s["financial"]["failure"] == {"kind": "budget_exceeded", "message": "budget_exceeded (run)"}
            assert s["pathway"]["status"] == "not_run"


def test_part2_counts_the_part1_spend() -> None:
    received = support.received2()
    mock = MockProvider("openai")
    support.script_iro(mock, received)
    cap = 5 * PART1_CALL + 2 * support.CALL_USD2 - 0.001  # 1부 다섯 0.275 + 2부 둘 0.072 에 닿게(넘는 셈 오차 없이)
    done = support.run_iro(support.iro_inputs(received, max_cost_usd=cap), support.spy2(mock))
    assert len(mock.calls) == 7
    assert done.steps[part2_155.SEED].data["spentUsd"] == pytest.approx(5 * PART1_CALL)
    assert [c["ending"] for c in calls(done, "impact")] == ["done", "done", "budget_exceeded"]
