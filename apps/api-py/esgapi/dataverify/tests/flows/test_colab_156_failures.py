"""흐름 dataverify.colab@156 의 실패 갈래 → 결과 꼴 @2 의 failure·insight.partialText(밴드 DV1e §3-1-2·3-1-3).

고리(`ended`)와 끈 인사이트의 `call`(`ended_call`)이 같은 규칙이다: kind = core 의 갈래 이름, budgetSource 는
budget_exceeded 일 때만(끈 인사이트는 기존 상한뿐이라 "guard"), 부분 원문은 truncated(CutOff)일 때만. message 는 BASE
흐름의 글 그대로 — 손값으로 적고, scripts/section4-DV1e.sh 가 BASE 의 failure_message·ended_call 과 바이트로 견준다.
"""

from typing import Any, Final

import pytest

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import (
    BudgetExceeded,
    CallMeta,
    CutOff,
    LlmResult,
    ProviderError,
    ProviderFailed,
    Refused,
    SchemaMismatch,
    Scope,
    TimedOut,
    ToolExecutorRaised,
    ToolLoopFailed,
    ToolLoopFailure,
    Truncated,
    Usage,
)
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.tests.flows.support import inputs, result, run, spy

META: Final = CallMeta(
    call_id="가상-호출", prompt_id="dataverify/insight@1", attempts=(), total_cost_usd=0.0, warnings=()
)
PARTIAL: Final = "가상 부분 인사이트 — 잘린 모델 글"
USAGE: Final = Usage(input_tokens=100, output_tokens=20, cache_read_tokens=0, cache_write_tokens=0)


def budget() -> BudgetExceeded:
    return BudgetExceeded(limit_usd=1.0, spent_usd=1.0, scope=Scope(), meta=META)


LOOP_CASES: Final[list[tuple[ToolLoopFailure, Any, str, Any, str]]] = [
    (budget(), "guard", "budget_exceeded", "guard", "budget_exceeded (guard)"),
    (budget(), "loop", "budget_exceeded", "loop", "budget_exceeded (loop)"),
    (CutOff(partial_text=PARTIAL, meta=META), None, "truncated", None, "truncated"),
    (Refused(text="가상 거절 글", category=None, meta=META), None, "refusal", None, "refusal"),
    (
        ProviderFailed(status=503, retryable=True, message="가상 공급사 글", meta=META),
        None,
        "provider_error",
        None,
        "provider_error status=503",
    ),
    (
        ProviderFailed(status=None, retryable=False, message="가상 공급사 글", meta=META),
        None,
        "provider_error",
        None,
        "provider_error status=none",
    ),
    (TimedOut(message="가상 시간 글", meta=META), None, "timeout", None, "timeout"),
    (
        ToolExecutorRaised(name="sum_check", error_class="ValueError"),
        None,
        "tool_executor_raised",
        None,
        "tool_executor_raised sum_check ValueError",
    ),
]
CALL_CASES: Final[list[tuple[LlmResult[str], str, Any, str]]] = [
    (budget(), "budget_exceeded", "guard", "budget_exceeded"),
    (CutOff(partial_text=PARTIAL, meta=META), "truncated", None, "truncated"),
    (Refused(text="가상 거절 글", category=None, meta=META), "refusal", None, "refusal"),
    (
        ProviderFailed(status=429, retryable=True, message="가상 공급사 글", meta=META),
        "provider_error",
        None,
        "provider_error status=429",
    ),
    (TimedOut(message="가상 시간 글", meta=META), "timeout", None, "timeout"),
    (SchemaMismatch(issues=(), raw_text="가상 원문", meta=META), "schema_mismatch", None, "schema_mismatch"),
]


@pytest.mark.parametrize(
    ("failure", "source", "kind", "budget_source", "message"),
    LOOP_CASES,
    ids=[
        "budget_guard",
        "budget_loop",
        "truncated",
        "refusal",
        "provider_503",
        "provider_none",
        "timeout",
        "tool_raised",
    ],
)
def test_a_loop_failure_maps_to_the_core_kind(
    failure: ToolLoopFailure, source: Any, kind: str, budget_source: Any, message: str
) -> None:
    end = colab_156.ended(ToolLoopFailed(failure=failure, steps=(), meta=META, budget_source=source))
    assert colab_156.failure_of(end) == {"kind": kind, "budgetSource": budget_source, "message": message}
    assert end.parts is not None
    assert end.parts.partial_text == (PARTIAL if kind == "truncated" else None)


@pytest.mark.parametrize(
    ("failure", "kind", "budget_source", "message"),
    CALL_CASES,
    ids=["budget", "truncated", "refusal", "provider_429", "timeout", "schema_mismatch"],
)
def test_a_call_failure_follows_the_same_rule(
    failure: LlmResult[str], kind: str, budget_source: Any, message: str
) -> None:
    end = colab_156.ended_call(failure)
    assert colab_156.failure_of(end) == {"kind": kind, "budgetSource": budget_source, "message": message}
    assert end.parts is not None
    assert end.parts.partial_text == (PARTIAL if kind == "truncated" else None)


def test_a_budget_source_off_budget_exceeded_is_dropped() -> None:
    """core 가 상한 밖 갈래에 budget_source 를 실어도 결과에는 null(budgetSource 는 budget_exceeded 와 맞물린다)."""
    end = colab_156.ended(
        ToolLoopFailed(failure=TimedOut(message="", meta=META), steps=(), meta=META, budget_source="loop")
    )
    assert colab_156.failure_of(end)["budgetSource"] is None


def plan_and_review(mock: MockProvider) -> MockProvider:
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_text("가상 검토")
    return mock


@pytest.mark.parametrize("web_search", [True, False])
def test_a_truncated_insight_carries_the_partial_text_only_in_partial_text(web_search: bool) -> None:
    """고리·끈 인사이트(web_search=False 의 `call` 한 번) 두 갈래 모두(critic 권고 ①)."""
    mock = plan_and_review(MockProvider("openai"))
    mock.enqueue(Truncated(text=PARTIAL, usage=USAGE))
    out = result(run(inputs(web_search=web_search), spy(mock)))
    assert out["insight"] == {
        "status": "failed",
        "partial": None,
        "report": None,
        "rows": [],
        "rowsParsed": "none",
        "sources": [],
        "failure": {"kind": "truncated", "budgetSource": None, "message": "truncated"},
        "partialText": PARTIAL,
    }
    rest = {**out, "insight": {k: v for k, v in out["insight"].items() if k != "partialText"}}
    assert PARTIAL not in repr(rest)  # message·warnings·다른 칸에 0


@pytest.mark.parametrize("web_search", [True, False])
def test_an_insight_failing_otherwise_has_no_partial_text(web_search: bool) -> None:
    mock = plan_and_review(MockProvider("openai"))
    mock.enqueue(ProviderError(status=500, retryable=False, message="가상 공급사 오류 글"))
    out = result(run(inputs(web_search=web_search), spy(mock)))
    assert out["insight"]["failure"] == {
        "kind": "provider_error",
        "budgetSource": None,
        "message": "provider_error status=500",
    }
    assert out["insight"]["partialText"] is None


def test_a_truncated_plan_has_the_kind_but_no_partial_text_field() -> None:
    """부분 원문 칸은 인사이트에만(Q3 가). Plan 이 잘리면 kind truncated, 인사이트는 그대로 돈다."""
    mock = MockProvider("openai")
    mock.enqueue(Truncated(text=PARTIAL, usage=USAGE))
    mock.enqueue_text("가상 인사이트(표 없음)", hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    assert out["plan"]["failure"] == {"kind": "truncated", "budgetSource": None, "message": "truncated"}
    assert "partialText" not in out["plan"]
    assert PARTIAL not in repr(out)
    assert out["insight"]["status"] == "done"
