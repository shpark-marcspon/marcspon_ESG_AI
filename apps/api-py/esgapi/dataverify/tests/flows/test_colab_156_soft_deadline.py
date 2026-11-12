"""흐름 dataverify.colab@156 에서 Celery soft limit 이 값이 되지 않고 밖으로 나가는가(MARC-ISSUE-414, 밴드 DVE1).

엔진(도구 실행기·HINTS 읽기)은 core 를 모르니 흐름이 「다시 던질지」 판별(core 의 soft_deadline_in)을 주입한다.
soft limit 은 시험 안 가짜 클래스로 짓는다 — soft_deadline_in 은 조상 클래스의 **이름**으로 가른다. 대조로 같은 자리의
ValueError 는 BASE 그대로 값(검사 기록의 runtime error·Plan 의 unparsable)이 된다.
"""

from typing import Any

import pytest

from esgapi.core.flows.types import FlowStepFailed
from esgapi.core.llm.errors import soft_deadline_in
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderRequest, ToolOutput
from esgapi.dataverify.engines.colab_156 import dispatch, loop
from esgapi.dataverify.tests.flows.support import inputs, result, run, spy

INSIGHT = """## 가상 인사이트

| 영역 | 지표 | 관찰 | 리스크 | 해석 |
|---|---|---|---|---|
| 환경 | 가상 지표 A | 가상 관찰 A | 가상 리스크 A | 가상 해석 A |
"""


class SoftTimeLimitExceeded(Exception):
    """시험의 가짜 Celery soft limit(이름만 같다)."""


def raising(error: BaseException) -> Any:
    def tool(*_args: Any, **_kwargs: Any) -> Any:
        raise error

    return tool


def outputs_of(request: ProviderRequest) -> list[str]:
    return [turn.output for turn in request.turns if isinstance(turn, ToolOutput)]


def review_calls_sum_check(mock: MockProvider) -> MockProvider:
    """Plan 한 걸음(산식 하나) → 검토 첫 걸음이 sum_check 를 부른다 → 검토 글 → 인사이트."""
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_tool_calls([("sum_check", '{"a": 1, "b": 2, "c": 3}')])
    mock.enqueue_text("가상 검토")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    return mock


def test_a_soft_limit_in_a_review_tool_leaves_the_flow_as_flow_step_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    error = SoftTimeLimitExceeded("가상 시간 제한")
    monkeypatch.setattr(dispatch, "tool_sum_check", raising(error))
    mock = review_calls_sum_check(MockProvider("openai"))
    with pytest.raises(FlowStepFailed) as raised:
        run(inputs(), spy(mock))
    assert raised.value.step == "review"
    assert soft_deadline_in(raised.value) is error
    assert len(mock.calls) == 2  # 검토 둘째 걸음·인사이트로 가지 않는다


def test_a_value_error_in_a_review_tool_is_still_a_runtime_error_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dispatch, "tool_sum_check", raising(ValueError("가상 값 오류")))
    mock = review_calls_sum_check(MockProvider("openai"))
    out = result(run(inputs(), spy(mock)))
    assert mock.pending == 0
    assert outputs_of(mock.calls[2]) == ['{"error": "runtime error in sum_check: 가상 값 오류"}']
    review = out["review"]
    assert review["status"] == "done"
    assert [(c["seq"], c["tool"], c["kind"], c["message"]) for c in review["checks"]] == [
        (1, "sum_check", "error", "runtime error in sum_check: 가상 값 오류")
    ]


def test_a_soft_limit_while_reading_hints_leaves_the_flow_at_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    error = SoftTimeLimitExceeded("가상 시간 제한")
    monkeypatch.setattr(loop.ast, "literal_eval", raising(error))
    mock = review_calls_sum_check(MockProvider("openai"))
    with pytest.raises(FlowStepFailed) as raised:
        run(inputs(), spy(mock))
    assert raised.value.step == "plan"
    assert soft_deadline_in(raised.value) is error
    assert len(mock.calls) == 1


def test_a_value_error_while_reading_hints_is_still_unparsable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loop.ast, "literal_eval", raising(ValueError("가상 읽기 오류")))
    mock = MockProvider("openai")
    mock.enqueue_text("['가상 산식']")
    mock.enqueue_text(INSIGHT, hosted_calls=1)
    out = result(run(inputs(), spy(mock)))
    assert out["plan"]["status"] == "failed"
    assert out["plan"]["failure"] == {
        "kind": "unparsable",
        "budgetSource": None,
        "message": "계산 Plan 의 답이 글자 원소의 python list 가 아니다",
    }
