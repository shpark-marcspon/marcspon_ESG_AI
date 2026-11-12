"""도구를 주지 않은 호출(`LlmClient.call`)이 도구 호출 답을 받았을 때(밴드 TL1 `MARC-TICK-180` 의 T4). 순수 층.

빈 글의 성공으로 접지 않는다: 재시도 불가 공급사 오류, 기록 한 줄 `provider_error`(상태 없음), 사용량·비용은 응답 것
그대로(누계에 든다), 대체 모델로 가지 않고 같은 모델도 다시 부르지 않는다. 토큰 수는 전부 가상(synthetic) 값이다.
"""

from pathlib import Path

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.cost import compute_cost_usd
from esgapi.core.llm.retry import RetryPolicy
from esgapi.core.llm.types import ProviderFailed, Scope
from esgapi.core.tests.llm_support import TAGS, USAGE_SYNTHETIC, harness, synthetic_config

REQUEST = CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock-with-fallback", tags=TAGS)


def test_a_tool_call_answer_to_a_plain_call_is_a_non_retryable_provider_error_with_its_cost_kept(
    prompt_root: Path,
) -> None:
    always_retry = {"mock": RetryPolicy(max_retries=2, base_delay_ms=0, max_delay_ms=0)}
    h = harness(prompt_root, provider_retry=always_retry)
    h.mock.enqueue_tool_calls([("tool_0", "{}")], usage=USAGE_SYNTHETIC)
    h.mock_b.enqueue_text("대체 모델은 불리지 않는다")

    result = h.client.call(REQUEST)

    assert isinstance(result, ProviderFailed)
    assert result.status is None
    assert result.retryable is False
    # 대체 모델로 가지 않고 같은 모델도 다시 부르지 않는다.
    assert len(h.mock.calls) == 1
    assert h.mock_b.calls == []
    assert h.sleeps == []
    pricing = synthetic_config().models["mock-synthetic"].pricing
    expected = compute_cost_usd(USAGE_SYNTHETIC, pricing)
    assert expected == 0.0001
    (attempt,) = result.meta.attempts
    assert attempt.kind == "provider_error"
    assert attempt.usage == USAGE_SYNTHETIC
    assert attempt.cost_usd == expected
    assert result.meta.total_cost_usd == expected
    (record,) = h.log.records
    assert record.result_kind == "provider_error"
    assert record.error_status is None
    assert record.to_json()["errorStatus"] is None
    assert record.cost_usd == expected
    assert record.input_tokens == USAGE_SYNTHETIC.input_tokens
    # 비용은 누계에 든다(다음 상한 확인이 본다).
    assert h.log.spent(Scope()) == expected
