"""같은 모델 재시도, 재시도와 상한·간격·대체 호출의 어울림, 대기 계산. 순수 층. esg-lab 의 test/retry.test.ts(15건)를
옮긴 것.

실제 공급사로 가는 호출은 없다. SDK 클라이언트 자리에 가짜를 넣고, 대기는 받아 적기만 한다.
오류 본문과 토큰 수는 전부 가상(synthetic) 값이다. 429 본문의 모양만 esg-lab 이 2026-10-02 에 받은 실제 응답을 따랐다.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.log import MISSING
from esgapi.core.llm.prompts import FilePromptStore
from esgapi.core.llm.providers.gemini import GeminiProvider, retry_info_delay_ms
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.retry import DEFAULT_PROVIDER_RETRY, RetryPolicy, retry_delay_ms
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.throttle import throttled
from esgapi.core.llm.types import (
    BudgetExceeded,
    ProviderError,
    ProviderFailed,
    ProviderRequest,
    ProviderResponse,
    Scope,
    Success,
)
from esgapi.core.tests.llm_support import TAGS, USAGE_SYNTHETIC, Harness, harness, synthetic_config

BASE = CallRequest(prompt="t/plain@1", vars={"question": "분류해 줘"}, route="mock", tags=TAGS)
GEMINI = replace(BASE, route="light-gemini-35")
POLICY = RetryPolicy(max_retries=2, base_delay_ms=1_000, max_delay_ms=60_000)
FAILED = ProviderError(status=503, retryable=True, message="과부하")


def quota_body(retry_delay: str | None = None) -> dict[str, Any]:
    details: list[dict[str, Any]] = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": []}]
    if retry_delay is not None:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay})
    error = {"code": 429, "message": "quota (synthetic)", "status": "RESOURCE_EXHAUSTED", "details": details}
    return {"error": error}


def quota_429(retry_delay: str | None = None) -> genai_errors.APIError:
    return genai_errors.APIError(429, quota_body(retry_delay))


def api_error(status: int) -> genai_errors.APIError:
    return genai_errors.APIError(status, {"error": {"code": status, "message": "synthetic"}})


def gemini_ok(finish: str = "STOP", text: str = "pong") -> genai_types.GenerateContentResponse:
    return genai_types.GenerateContentResponse.model_validate(
        {
            "modelVersion": "gemini-3.5-flash-lite",
            "candidates": [{"finishReason": finish, "content": {"role": "model", "parts": [{"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 100, "totalTokenCount": 1100},
        }
    )


# gemini-3.5-flash-lite 설정 단가(입력 0.30, 출력 2.50 USD/100만 토큰. data/models.json): 1000×0.30 + 100×2.50 = 550
# → 0.00055.
OK_COST = 0.00055

type GeminiReply = genai_types.GenerateContentResponse | Exception


class ScriptedGemini:
    """심은 순서대로 던지거나 돌려주는 가짜 Gemini SDK 클라이언트."""

    def __init__(self, replies: list[GeminiReply]) -> None:
        self._replies = replies
        self.sent = 0
        self.models = self

    def generate_content(self, **kwargs: Any) -> genai_types.GenerateContentResponse:
        index = self.sent
        self.sent += 1
        if index >= len(self._replies):
            raise RuntimeError("가짜 클라이언트에 심은 응답이 없다")
        reply = self._replies[index]
        if isinstance(reply, Exception):
            raise reply
        return reply


def gemini_harness(prompt_root: Path, replies: list[GeminiReply], **options: Any) -> tuple[Harness, ScriptedGemini]:
    sdk = ScriptedGemini(replies)
    return harness(prompt_root, providers={"gemini": GeminiProvider(sdk)}, **options), sdk


# ── Gemini 일시 오류의 같은 모델 재시도 (기본 설정) ──


def test_default_retries_gemini_openai_anthropic_twice_from_one_second_doubling_capped_at_sixty() -> None:
    policy = RetryPolicy(max_retries=2, base_delay_ms=1_000, max_delay_ms=60_000)
    assert {name: policy for name in ("gemini", "openai", "anthropic")} == DEFAULT_PROVIDER_RETRY


def test_retries_after_429_and_503_follow_the_provider_delay_and_log_every_attempt(prompt_root: Path) -> None:
    h, sdk = gemini_harness(prompt_root, [quota_429("7s"), api_error(503), gemini_ok()])

    result = h.client.call(GEMINI)

    assert isinstance(result, Success)
    assert result.data == "pong"
    assert sdk.sent == 3
    # 첫 대기는 429 본문의 retryDelay, 둘째는 알려 준 값이 없어 1초 × 2^1.
    assert h.sleeps == [7_000, 2_000]
    assert [(attempt.kind, attempt.provider_retry) for attempt in result.meta.attempts] == [
        ("provider_error", None),
        ("provider_error", 1),
        ("success", 2),
    ]
    rows = [
        (r.attempt, r.result_kind, r.error_status, r.provider_retry, r.previous_error_status, r.retry_wait_ms)
        for r in h.log.records
    ]
    assert rows == [
        (0, "provider_error", 429, None, MISSING, None),
        (1, "provider_error", 503, 1, 429, 7_000),
        (2, "success", MISSING, 2, 503, 2_000),
    ]
    assert h.log.records[0].retry_after_ms == 7_000
    assert "retryAfterMs" not in h.log.records[1].to_json()
    assert len({record.call_id for record in h.log.records}) == 1


def test_retried_call_is_billed_once_result_budget_and_log_agree(prompt_root: Path) -> None:
    h, _ = gemini_harness(prompt_root, [api_error(503), gemini_ok()])

    result = h.client.call(GEMINI)

    assert result.kind == "success"
    assert [attempt.cost_usd for attempt in result.meta.attempts] == [None, OK_COST]
    assert result.meta.total_cost_usd == OK_COST
    assert h.client.budget.spent(Scope()) == OK_COST
    assert [record.cost_usd for record in h.log.records] == [None, OK_COST]


def test_exhausted_retries_end_as_provider_error_after_three_calls(prompt_root: Path) -> None:
    h, sdk = gemini_harness(prompt_root, [api_error(503), api_error(503), api_error(503), gemini_ok()])

    result = h.client.call(GEMINI)

    assert isinstance(result, ProviderFailed)
    assert (result.status, result.retryable) == (503, True)
    assert sdk.sent == 3
    assert h.sleeps == [1_000, 2_000]
    assert len(result.meta.attempts) == 3
    assert result.meta.total_cost_usd == 0
    assert [record.provider_retry for record in h.log.records] == [None, 1, 2]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_non_retryable_error_is_called_once(prompt_root: Path, status: int) -> None:
    h, sdk = gemini_harness(prompt_root, [api_error(status), gemini_ok()])

    result = h.client.call(GEMINI)

    assert isinstance(result, ProviderFailed)
    assert (result.status, result.retryable) == (status, False)
    assert sdk.sent == 1
    assert h.sleeps == []
    assert len(h.log.records) == 1


def test_delay_longer_than_the_cap_is_not_retried_but_is_logged(prompt_root: Path) -> None:
    h, sdk = gemini_harness(prompt_root, [quota_429("3600s"), gemini_ok()])

    result = h.client.call(GEMINI)

    assert isinstance(result, ProviderFailed)
    assert result.status == 429
    assert sdk.sent == 1
    assert h.sleeps == []
    assert (h.log.records[0].error_status, h.log.records[0].retry_after_ms) == (429, 3_600_000)


@pytest.mark.parametrize(
    ("reply", "kind"),
    [(httpx.ReadTimeout("timed out"), "timeout"), (gemini_ok(finish="MAX_TOKENS", text="p"), "truncated")],
)
def test_timeout_and_truncation_are_not_retried(prompt_root: Path, reply: GeminiReply, kind: str) -> None:
    h, sdk = gemini_harness(prompt_root, [reply, gemini_ok()])
    assert h.client.call(GEMINI).kind == kind
    assert sdk.sent == 1
    assert h.sleeps == []


def test_empty_provider_retry_disables_gemini_retry_and_bad_policy_raises(prompt_root: Path) -> None:
    h, sdk = gemini_harness(prompt_root, [api_error(503), gemini_ok()], provider_retry={})
    assert h.client.call(GEMINI).kind == "provider_error"
    assert sdk.sent == 1
    with pytest.raises(LlmConfigError):
        gemini_harness(prompt_root, [], provider_retry={"gemini": RetryPolicy(-1, 0, 0)})
    with pytest.raises(LlmConfigError):
        gemini_harness(prompt_root, [], provider_retry={"gemini": RetryPolicy(1, 10, 5)})


# ── 재시도와 비용 상한·호출 간격·대체 호출 ──


def retrying(prompt_root: Path, *, limited: bool = True, policy: RetryPolicy = POLICY) -> Harness:
    limits = [BudgetLimit(scope=Scope(tenant=TAGS.tenant), limit_usd=0.00015)] if limited else []
    return harness(prompt_root, limits=limits, provider_retry={"mock": policy})


def test_by_default_the_call_layer_retries_gemini_openai_anthropic_but_not_mock(prompt_root: Path) -> None:
    """모의 공급사는 다시 부르지 않는다. openai·anthropic 은 SDK 재시도를 끈 대신 호출 층이 두 번 다시 부른다
    (LH1 Q1)."""
    h = harness(prompt_root)
    h.mock.enqueue(FAILED).enqueue_text("ok")
    assert h.client.call(BASE).kind == "provider_error"
    assert len(h.mock.calls) == 1

    for name, route in (("openai", "light-openai"), ("anthropic", "light-anthropic")):
        provider = MockProvider(name)
        for _ in range(3):
            provider.enqueue(ProviderError(status=429, retryable=True, message="한도"))
        other = harness(prompt_root, providers={name: provider})
        assert other.client.call(replace(BASE, route=route)).kind == "provider_error"
        assert len(provider.calls) == 3
        assert other.sleeps == [1000, 2000]


def test_budget_is_checked_right_before_each_retry(prompt_root: Path) -> None:
    h = retrying(prompt_root)

    def fail_while_another_call_spends(_request: ProviderRequest) -> ProviderResponse:
        # 첫 시도가 실패하는 사이에 같은 꼬리표의 다른 호출이 상한을 채웠다.
        h.log.add_spent(TAGS, 0.0002)
        return FAILED

    h.mock.enqueue(fail_while_another_call_spends)
    h.mock.enqueue_text("ok", USAGE_SYNTHETIC)

    result = h.client.call(BASE)

    assert isinstance(result, BudgetExceeded)
    assert (result.limit_usd, result.spent_usd) == (0.00015, 0.0002)
    assert len(h.mock.calls) == 1
    assert h.mock.pending == 1
    assert [(r.result_kind, r.provider_retry, r.previous_error_status) for r in h.log.records] == [
        ("provider_error", None, MISSING),
        ("budget_exceeded", 1, 503),
    ]


class Number(BaseModel):
    a: float


def test_retry_mixed_with_schema_retry_bills_each_paid_attempt_once(prompt_root: Path) -> None:
    h = retrying(prompt_root, limited=False)
    h.mock.enqueue(FAILED).enqueue_text("JSON 아님", USAGE_SYNTHETIC).enqueue(FAILED).enqueue_text(
        '{"a":1}', USAGE_SYNTHETIC
    )

    result = h.client.call(CallRequest(prompt="t/plain@1", vars=BASE.vars, route="mock", tags=TAGS, schema=Number))

    assert result.kind == "success"
    assert [(a.kind, a.provider_retry, a.cost_usd) for a in result.meta.attempts] == [
        ("provider_error", None, None),
        ("schema_mismatch", 1, 0.0001),
        ("provider_error", None, None),
        ("success", 1, 0.0001),
    ]
    assert result.meta.total_cost_usd == 0.0002
    assert sum(record.cost_usd or 0 for record in h.log.records) == pytest.approx(0.0002, abs=1e-12)
    assert [record.attempt for record in h.log.records] == [0, 1, 2, 3]


class StoppedClock:
    def __init__(self) -> None:
        self.waits: list[float] = []

    def now(self) -> float:
        return 0

    def sleep(self, ms: float) -> None:
        self.waits.append(ms)


def test_retried_calls_also_pass_through_the_throttle(prompt_root: Path) -> None:
    clock = StoppedClock()
    mock = MockProvider()
    mock.enqueue(FAILED).enqueue(FAILED).enqueue_text("ok")
    client = LlmClient(
        config=synthetic_config(),
        providers={"mock": throttled(mock, 60, clock)},
        prompts=FilePromptStore(prompt_root),
        log=MemorySink(),
        provider_retry={"mock": RetryPolicy(max_retries=2, base_delay_ms=0, max_delay_ms=0)},
        sleep=lambda _ms: None,
    )

    assert client.call(BASE).kind == "success"
    assert len(mock.calls) == 3
    # 분당 60회 → 시작 간격 1초. 가짜 시계가 멈춰 있어 둘째·셋째 호출은 1초, 2초를 기다린다.
    assert clock.waits == [1_000, 2_000]


def test_order_same_model_is_retried_first_then_the_next_model(prompt_root: Path) -> None:
    h = retrying(prompt_root, limited=False, policy=replace(POLICY, max_retries=1))
    h.mock.enqueue(FAILED).enqueue(FAILED)
    h.mock_b.enqueue_text("ok", USAGE_SYNTHETIC)

    result = h.client.call(replace(BASE, route="mock-with-fallback"))

    assert result.kind == "success"
    assert [(a.provider, a.kind, a.provider_retry) for a in result.meta.attempts] == [
        ("mock", "provider_error", None),
        ("mock", "provider_error", 1),
        ("mock-b", "success", None),
    ]
    assert h.sleeps == [1_000]


# ── 대기 시간 계산과 RetryInfo 읽기 ──


def test_delay_doubles_and_is_capped_and_is_none_when_retries_are_used_up() -> None:
    policy = RetryPolicy(max_retries=4, base_delay_ms=1_000, max_delay_ms=3_000)
    assert [retry_delay_ms(policy, index, None) for index in range(5)] == [1_000, 2_000, 3_000, 3_000, None]
    # 공급사가 알려 준 대기가 먼저다. 상한을 넘으면 다시 부르지 않는다.
    assert retry_delay_ms(policy, 0, 2_500) == 2_500
    assert retry_delay_ms(policy, 0, 0) == 0
    assert retry_delay_ms(policy, 0, 3_001) is None
    assert retry_delay_ms(RetryPolicy(0, 0, 0), 0, None) is None


def test_retry_info_delay_is_read_in_ms_or_none_when_absent_or_unreadable() -> None:
    assert retry_info_delay_ms(quota_body("55s")) == 55_000
    assert retry_info_delay_ms(quota_body("0.5s")) == 500
    assert retry_info_delay_ms(quota_body()) is None
    assert retry_info_delay_ms(quota_body("soon")) is None
    assert retry_info_delay_ms("본문이 JSON 이 아니다") is None
    assert retry_info_delay_ms({"error": {"details": "x"}}) is None
    assert retry_info_delay_ms(None) is None
    # SDK 의 예외가 본문을 details 에 싣는다(어댑터가 거기서 읽는다).
    assert retry_info_delay_ms(vars(quota_429("55s"))["details"]) == 55_000
