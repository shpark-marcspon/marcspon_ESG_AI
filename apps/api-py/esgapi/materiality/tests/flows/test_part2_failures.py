"""2부 단계의 실패 갈래(발주서 §3 S6·S7·S8·S9): JSON 아님 → failed·unparsable(재무면 Pathway 호출 0·not_run), 공급사
오류·시간 초과·거부(message 에 모델 글·공급사 메시지 0), 잘림(읽히면 done + answer_truncated, 못 읽으면 failed·truncated
+ answer_truncated, 재시도 0), 비용 상한(입력 검사·호출 앞 문·1부 지출 합침). 공급사는 모의만(실호출 0)."""

import json
import math
from typing import Any

import pytest

from esgapi.core.flows.types import FlowInputError, FlowStepFailed
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderError, ProviderTimeout, Refusal, Truncated
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.support import CALL_USD2, SUBTOPICS2, USAGE

A, B, C = SUBTOPICS2


def run_with(mock: MockProvider, **changes: Any) -> tuple[dict[str, Any], Any]:
    done = support.run2(support.inputs2(**changes), support.spy2(mock))
    return dict(support.result(done)), done


def subs(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for t in result["part2"]["topics"] for s in t["subtopics"]]


def enqueue(mock: MockProvider, replies: list[Any]) -> None:
    for reply in replies:
        if isinstance(reply, str):
            mock.enqueue_text(reply, USAGE)
        else:
            mock.enqueue(reply)


# ── S6 JSON 아님 ────────────────────────────────────────────────────────────────────────────


def test_unparsable_answers_per_phase() -> None:
    mock = MockProvider("openai")
    table = "| Topic | Subtopic | 영향 정의 |\n|---|---|---|\n| 가상 | 가상 | 가상 표 꼴 답 |"
    enqueue(
        mock,
        [
            table,
            support.impact_answer(B),
            support.impact_answer(C),
            support.financial_answer(A),
            table,
            support.financial_answer(C),
            "가상 글 답",
            support.pathway_answer(C),
        ],
    )
    result, _ = run_with(mock)
    a, b, c = subs(result)
    assert a["impact"] == {
        "status": "failed",
        "raw": table,
        "parseError": "JSONDecodeError: Expecting value: line 1 column 1 (char 0)",
        "failure": {"kind": "unparsable", "message": "모델의 답에서 JSON 객체를 읽지 못했다."},
    }
    assert a["financial"]["status"] == "done"
    assert a["pathway"]["status"] == "failed" and a["pathway"]["failure"]["kind"] == "unparsable"
    assert b["financial"]["status"] == "failed"
    assert b["pathway"] == {
        "status": "not_run",
        "message": "재무 영향이 실패했거나 rows 가 0 이라 부르지 않았다(코랩 셀 55 의 [MISSING fin_impact]).",
    }
    assert c["pathway"]["status"] == "done"
    assert len(mock.calls) == 8 and mock.pending == 0  # 재무 실패 자리의 Pathway 는 부르지 않음


def test_financial_with_no_rows_skips_pathway() -> None:
    mock = MockProvider("openai")
    empty = json.dumps({"topic": "가상", "subtopic": A, "impacts": []})
    enqueue(mock, [support.impact_answer(n) for n in SUBTOPICS2] + [empty, empty, empty])
    result, done = run_with(mock)
    assert [s["pathway"]["status"] for s in subs(result)] == ["not_run"] * 3
    assert done.steps["pathway"].data["calls"] == [] and len(mock.calls) == 6


# ── S7 실패 ─────────────────────────────────────────────────────────────────────────────────


def test_provider_failures_keep_no_model_or_provider_text() -> None:
    mock = MockProvider("openai")
    enqueue(
        mock,
        [
            ProviderError(status=500, retryable=False, message="가상 공급사 비밀 메시지"),
            ProviderTimeout(message="가상 시간 초과 메시지"),
            Refusal(text="가상 거부 글", category=None, usage=USAGE),
        ]
        + [support.financial_answer(n) for n in SUBTOPICS2]
        + [support.pathway_answer(n) for n in SUBTOPICS2],
    )
    result, done = run_with(mock)
    a, b, c = subs(result)
    assert a["impact"] == {
        "status": "failed",
        "raw": None,
        "parseError": None,
        "failure": {"kind": "provider_error", "message": "provider_error status=500"},
    }
    assert b["impact"]["failure"] == {"kind": "timeout", "message": "timeout"}
    assert c["impact"]["failure"] == {"kind": "refusal", "message": "refusal"}
    assert [x["ending"] for x in done.steps["impact"].data["calls"]] == ["provider_error", "timeout", "refusal"]
    text = json.dumps(result, ensure_ascii=False)
    assert "비밀" not in text and "가상 시간 초과 메시지" not in text and "가상 거부 글" not in text
    assert all(s["financial"]["status"] == "done" for s in (a, b, c))  # 실패 → 계속


# ── S8 잘림 ─────────────────────────────────────────────────────────────────────────────────


def test_truncated_readable_is_done_and_unreadable_is_failed_without_retry() -> None:
    mock = MockProvider("openai")
    cut = support.impact_answer(B)
    enqueue(
        mock,
        [
            Truncated(text=support.impact_answer(A), usage=USAGE),  # 읽힘(잘렸어도 JSON 이 닫혀 있다)
            Truncated(text=cut[: len(cut) // 2], usage=USAGE),  # 못 읽음
            support.impact_answer(C),
        ]
        + [support.financial_answer(n) for n in SUBTOPICS2]
        + [support.pathway_answer(n) for n in SUBTOPICS2],
    )
    result, done = run_with(mock)
    a, b, _ = subs(result)
    assert a["impact"]["status"] == "done" and len(a["impact"]["rows"]) == 1
    assert b["impact"]["status"] == "failed"
    assert b["impact"]["raw"] == cut[: len(cut) // 2]
    assert b["impact"]["failure"] == {"kind": "truncated", "message": "truncated"}
    assert len(mock.calls) == 9 and mock.pending == 0  # 재시도 0
    truncated = [(w["phase"], w["topic"], w["subtopic"]) for w in result["warnings"] if w["code"] == "answer_truncated"]
    assert truncated == [("impact", "가상토픽 하나", A), ("impact", "가상토픽 하나", B)]
    assert [x["ending"] for x in done.steps["impact"].data["calls"]] == ["truncated", "truncated", "done"]


# ── S9 돈 문 ────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cost", [None, 0, 0.0, -1.0, math.nan, math.inf, True, "5"])
def test_bad_cost_is_refused_before_any_call(cost: object) -> None:
    mock = MockProvider("openai")
    support.script_part2(mock)
    with pytest.raises(FlowStepFailed) as raised:
        support.run2(support.inputs2(max_cost_usd=cost), support.spy2(mock))
    assert isinstance(raised.value.__cause__, FlowInputError)
    assert mock.calls == []


def test_budget_stops_calls_from_the_fifth() -> None:
    """상한 = 4 호출 비용(0.144): 넷째 뒤 누계가 상한에 닿아 다섯째부터 부르지 않는다."""
    mock = MockProvider("openai")
    support.script_part2(mock)
    result, done = run_with(mock, max_cost_usd=4 * CALL_USD2 - 1e-9)  # 넷째 뒤 누계(0.144)가 상한을 넘게
    assert len(mock.calls) == 4
    endings = [c["ending"] for p in ("impact", "financial", "pathway") for c in done.steps[p].data["calls"]]
    # 영향 셋 + 재무 A 가 끝나고, 재무 B·C 와 (재무 A 가 끝난) Pathway A 가 문에 막힌다.
    # Pathway B·C 는 재무가 실패라 기록도 없다
    assert endings == ["done"] * 4 + ["budget_exceeded"] * 3
    b_fin = subs(result)[1]["financial"]
    assert b_fin["failure"] == {"kind": "budget_exceeded", "message": "budget_exceeded (run)"}
    assert [s["pathway"]["status"] for s in subs(result)] == ["failed", "not_run", "not_run"]
    assert subs(result)[0]["pathway"]["failure"] == {"kind": "budget_exceeded", "message": "budget_exceeded (run)"}


def test_part1_spending_is_counted() -> None:
    """1부가 이미 상한 − 1 호출 비용을 썼으면 2부는 하나만 부른다."""
    mock = MockProvider("openai")
    support.script_part2(mock)
    _, done = run_with(mock, max_cost_usd=1.0, part1_spent=1.0 - CALL_USD2 + 1e-9)
    assert len(mock.calls) == 1
    assert done.steps["impact"].data["spentUsd"] == pytest.approx(1.0 + 1e-9)


# ── latest 참(도구 고리)의 실패 갈래 ─────────────────────────────────────────────────────────


def test_tool_loop_failures() -> None:
    mock = MockProvider("openai")
    cut = support.impact_answer(A)
    mock.enqueue(Truncated(text=cut[: len(cut) // 2], usage=USAGE))  # 고리 실패(잘림)
    mock.enqueue_tool_calls([("lookup", "{}")], usage=USAGE)  # 걸음 1 에서 함수를 부름 → 부분
    mock.enqueue(ProviderError(status=429, retryable=False, message="가상 공급사 비밀 메시지"))
    enqueue(mock, [support.financial_answer(n) for n in SUBTOPICS2] + [support.pathway_answer(n) for n in SUBTOPICS2])
    done: Any = support.run2(support.inputs2(support.received2(latest=True)), support.spy2(mock))
    result = dict(support.result(done))
    a, b, c = subs(result)
    assert a["impact"]["failure"] == {"kind": "truncated", "message": "truncated"}
    assert a["impact"]["raw"] == cut[: len(cut) // 2]
    assert b["impact"] == {
        "status": "failed",
        "raw": None,
        "parseError": None,
        "failure": {"kind": "provider_error", "message": "provider_error unexpected_function_call"},
    }
    assert c["impact"]["failure"] == {"kind": "provider_error", "message": "provider_error status=429"}
    assert [x["ending"] for x in done.steps["impact"].data["calls"]] == ["truncated", "partial", "provider_error"]
    assert [w["subtopic"] for w in result["warnings"] if w["code"] == "answer_truncated"] == [A]
    assert "비밀" not in json.dumps(result, ensure_ascii=False)
    assert len(mock.calls) == 9
