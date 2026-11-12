# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""같은 모델 재시도의 두 갈래·지터·HTTP 날짜·임베딩 재시도·고리 실패의 검색 수(밴드 LB1 경계 ② — MARC-ISSUE-672 안 A
의 2, MARC-ISSUE-624). 순수 층.

  S7  n 번 중 k 번 429(retry-after m초) → k 번 기다리고 성공, 줄 k+1, retry_wait_ms = 지터 얹은 값(k > max_retries)
  S8  529(retry-after 없음) 계속 → 예산까지 물러섬 → 넘길 대기는 안 기다리고 overloaded 실패 → 대체 모델로
  S9  retry-after > 남은 예산 → sleep 0 번, 결과에 retry_after_ms
  S10 아주 짧은 retry-after 계속 → 천장(8)에서 멈춤 · 예산은 호출 하나에서 모델을 넘어 합산
  S11 HTTP 날짜 retry-after(고정 시계 기준 미래·과거·못 읽음) — 진짜 SDK 예외
  S12 크레딧 소진 → 같은 모델 1번, 다음 모델로(Q6)
  S13 지터: 0·1 끝값(Q3 (가) — 공급사 대기 × 1.0~1.2, 물러섬 × 1.0~0.5) · 기본 jitter 는 random.random
  S14 500·연결 오류는 횟수 갈래(2회) + 지터 · 과금됐을 수 있는 과부하(200)도 횟수 갈래 · 시간 초과 재시도 0
  S15 임베딩: 429 둘 뒤 성공 → 줄 3·provider_retry 1,2 · 재시도 전 상한 확인 · 크레딧 소진 0 재시도 · {} 끔
  S16 624: ToolLoopFailed.hosted_calls 누계(잘림·거부 몫 포함, 그 밖 실패는 앞 걸음 합만)
  B2  provider_retry={} 면 429·529 도 재시도 0(감독 답 2)
★ 네트워크 0(뿌리 conftest 의 blocked_network). sleep·jitter·시계는 주입 — 시험이 실제로 기다리지 않는다.
"""

import random
from dataclasses import replace
from inspect import signature
from pathlib import Path

import httpx2
import openai
import pytest

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.embedding import Embedded, EmbeddingClient, EmbedProviderFailed, EmbedRequest
from esgapi.core.llm.embedding_types import EmbeddingVectors
from esgapi.core.llm.providers.mock import MockEmbeddingProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.retry import (
    DEFAULT_PROVIDER_RETRY,
    RATE_LIMIT_MAX_RETRIES,
    RATE_LIMIT_WAIT_BUDGET_MS,
    RetryPolicy,
    default_jitter,
    next_retry,
    retry_after_ms_from_headers,
)
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import (
    InvokeOptions,
    ProviderError,
    ProviderFailed,
    ProviderRequest,
    ProviderTimeout,
    Refusal,
    Scope,
    Success,
    TextPart,
    ToolLoopFailed,
    Truncated,
    WebSearchTool,
)
from esgapi.core.tests.llm.test_client_tool_loop import HOSTED, REQUEST, TOOLS, run
from esgapi.core.tests.llm_support import (
    TAGS,
    USAGE_SYNTHETIC,
    Harness,
    config_with,
    harness,
    synthetic_config,
    write_prompts,
)

POLICY = RetryPolicy(max_retries=2, base_delay_ms=1_000, max_delay_ms=60_000)
BASE = CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS)
FALLBACK = replace(BASE, route="mock-with-fallback")
OPTIONS = InvokeOptions(timeout_ms=10_000)
PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)


@pytest.fixture
def prompts(tmp_path: Path) -> Path:
    return write_prompts(tmp_path)


def limited(retry_after_ms: int | None = None) -> ProviderError:
    return ProviderError(429, True, "합성 한도", retry_after_ms=retry_after_ms, error_kind="rate_limited")


def overloaded(retry_after_ms: int | None = None) -> ProviderError:
    return ProviderError(529, True, "합성 과부하", retry_after_ms=retry_after_ms, error_kind="overloaded")


def retrying(prompts: Path, *, jitter: float = 0.0, policy: RetryPolicy = POLICY, **options: object) -> Harness:
    return harness(prompts, provider_retry={"mock": policy}, jitter=lambda: jitter, **options)  # pyright: ignore[reportArgumentType]


# ── S7 예산 갈래: max_retries 보다 많이 기다리고 성공 ────────────────────


def test_s7_k_rate_limits_with_a_wait_are_waited_out_beyond_max_retries(prompts: Path) -> None:
    h = retrying(prompts, jitter=0.5)
    for _ in range(4):
        h.mock.enqueue(limited(retry_after_ms=2_000))
    h.mock.enqueue_text("ok", USAGE_SYNTHETIC)

    result = h.client.call(BASE)

    assert isinstance(result, Success)
    # 공급사 대기 2초 × (1 + 0.2 × 0.5) = 2.2초, 네 번(max_retries 2 보다 많다 — 예산 갈래).
    assert h.sleeps == [2_200.0] * 4
    assert [r.provider_retry for r in h.log.records] == [None, 1, 2, 3, 4]
    assert [r.retry_wait_ms for r in h.log.records] == [None, 2_200.0, 2_200.0, 2_200.0, 2_200.0]
    assert [r.error_kind for r in h.log.records] == ["rate_limited"] * 4 + [None]


# ── S8 예산 끝 → 대체 모델로 ────────────────────────────────────────────


def test_s8_overloaded_without_a_wait_backs_off_until_the_budget_then_falls_back(prompts: Path) -> None:
    h = retrying(prompts)
    for _ in range(10):
        h.mock.enqueue(overloaded())
    h.mock_b.enqueue_text("ok", USAGE_SYNTHETIC)

    result = h.client.call(FALLBACK)

    assert isinstance(result, Success)
    # 1+2+4+8 = 15초, 다음 16초면 31초 > 예산 30초 — 기다리지 않고 다음 모델로.
    assert h.sleeps == [1_000, 2_000, 4_000, 8_000]
    assert [(a.provider, a.provider_retry) for a in result.meta.attempts] == [
        ("mock", None),
        ("mock", 1),
        ("mock", 2),
        ("mock", 3),
        ("mock", 4),
        ("mock-b", None),
    ]
    assert h.mock.pending == 5


def test_s8_without_a_fallback_the_failure_is_named_overloaded(prompts: Path) -> None:
    h = retrying(prompts)
    for _ in range(10):
        h.mock.enqueue(overloaded())
    result = h.client.call(BASE)
    assert isinstance(result, ProviderFailed)
    assert (result.status, result.retryable, result.error_kind) == (529, True, "overloaded")


# ── S9 남은 예산보다 긴 대기 ────────────────────────────────────────────


def test_s9_a_wait_longer_than_the_budget_is_not_slept_and_rides_on_the_result(prompts: Path) -> None:
    h = retrying(prompts)
    h.mock.enqueue(limited(retry_after_ms=45_000)).enqueue_text("ok")

    result = h.client.call(BASE)

    assert isinstance(result, ProviderFailed)
    assert h.sleeps == []
    assert (result.error_kind, result.retry_after_ms) == ("rate_limited", 45_000)
    assert len(h.mock.calls) == 1


# ── S10 천장·예산 합산 ──────────────────────────────────────────────────


def test_s10_tiny_waits_stop_at_the_ceiling(prompts: Path) -> None:
    h = retrying(prompts)
    for _ in range(20):
        h.mock.enqueue(limited(retry_after_ms=1))

    result = h.client.call(BASE)

    assert isinstance(result, ProviderFailed)
    assert len(h.mock.calls) == 1 + RATE_LIMIT_MAX_RETRIES == 9
    assert h.sleeps == [1.0] * RATE_LIMIT_MAX_RETRIES


def test_s10_the_budget_is_shared_by_the_models_of_one_call(prompts: Path) -> None:
    """예산은 호출 하나(_CallState) — 주 모델이 20초 기다렸으면 대체 모델은 남은 10초만."""
    h = harness(prompts, provider_retry={"mock": POLICY, "mock-b": POLICY}, jitter=lambda: 0.0)
    h.mock.enqueue(limited(retry_after_ms=20_000)).enqueue(limited(retry_after_ms=20_000))
    h.mock_b.enqueue(limited(retry_after_ms=12_000)).enqueue_text("ok")

    result = h.client.call(FALLBACK)

    assert isinstance(result, ProviderFailed)
    assert h.sleeps == [20_000]
    assert (len(h.mock.calls), len(h.mock_b.calls)) == (2, 1)
    assert result.retry_after_ms == 12_000


# ── S11 HTTP 날짜 retry-after ──────────────────────────────────────────

NOW_MS = 1_793_000_000_000.0  # 2026-10-26T07:33:20Z(지어낸 고정 시계)


@pytest.mark.parametrize(
    ("value", "want"),
    [
        pytest.param("Mon, 26 Oct 2026 07:33:30 GMT", 10_000, id="future"),
        pytest.param("Mon, 26 Oct 2026 07:33:00 GMT", 0, id="past"),
        pytest.param("Mon, 26 Oct 2026 07:33:25", 5_000, id="no-zone-is-utc"),
        pytest.param("다음 주 언젠가", None, id="unreadable"),
        pytest.param("", None, id="empty"),
    ],
)
def test_s11_http_date_retry_after_is_read_against_the_given_clock(value: str, want: int | None) -> None:
    assert retry_after_ms_from_headers({"retry-after": value}, now_ms=NOW_MS) == want


def test_s11_the_adapter_uses_its_injected_clock(blocked_network: list[object]) -> None:
    response = httpx2.Response(
        429,
        headers={"retry-after": "Mon, 26 Oct 2026 07:33:30 GMT"},
        request=httpx2.Request("POST", "https://x.invalid"),
    )
    error = openai.RateLimitError("합성", response=response, body=None)  # pyright: ignore[reportArgumentType]

    class Raising:
        class responses:
            @staticmethod
            def create(**_: object) -> object:
                raise error

    got = OpenAIProvider(Raising(), now=lambda: NOW_MS).invoke(PLAIN, OPTIONS)  # pyright: ignore[reportArgumentType]
    assert isinstance(got, ProviderError) and got.retry_after_ms == 10_000
    assert blocked_network == []


# ── S12 크레딧 소진 → 같은 모델 0, 다음 모델로 ───────────────────────────


def test_s12_quota_exhausted_is_called_once_then_the_next_model(prompts: Path) -> None:
    h = retrying(prompts)
    h.mock.enqueue(ProviderError(429, False, "합성 크레딧", error_kind="quota_exhausted")).enqueue_text("x")
    h.mock_b.enqueue_text("ok", USAGE_SYNTHETIC)

    result = h.client.call(FALLBACK)

    assert isinstance(result, Success)
    assert (len(h.mock.calls), len(h.mock_b.calls), h.sleeps) == (1, 1, [])


def test_s12_quota_exhausted_without_a_fallback_ends_named(prompts: Path) -> None:
    h = retrying(prompts)
    h.mock.enqueue(ProviderError(402, False, "합성 청구", error_kind="quota_exhausted"))
    result = h.client.call(BASE)
    assert isinstance(result, ProviderFailed) and result.error_kind == "quota_exhausted"


# ── S13 지터 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("jitter", "provider_wait", "backoff"),
    [(0.0, 2_000.0, 1_000.0), (1.0, 2_400.0, 500.0), (-3.0, 2_000.0, 1_000.0), (7.0, 2_400.0, 500.0)],
)
def test_s13_jitter_never_goes_below_the_provider_wait_and_halves_backoff_at_most(
    jitter: float, provider_wait: float, backoff: float
) -> None:
    def wait(error: ProviderError) -> float:
        got = next_retry(
            POLICY, error, maybe_billed=False, count_done=0, budget_done=0, waited_ms=0, jitter=lambda: jitter
        )
        assert got is not None
        return got.wait_ms

    assert wait(limited(retry_after_ms=2_000)) == provider_wait
    assert wait(limited()) == backoff
    assert wait(ProviderError(500, True, "합성", error_kind="server_error")) == backoff
    assert wait(ProviderError(500, True, "합성", retry_after_ms=2_000, error_kind="server_error")) == provider_wait


def test_s13_the_default_jitter_is_random_random(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(random, "random", lambda: 0.25)
    assert default_jitter() == 0.25
    # 제품의 기본(하네스는 0 을 준다).
    assert signature(LlmClient).parameters["jitter"].default is default_jitter
    assert signature(EmbeddingClient).parameters["jitter"].default is default_jitter


# ── S14 횟수 갈래 그대로 ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "error",
    [
        ProviderError(500, True, "합성 서버", error_kind="server_error"),
        ProviderError(None, True, "합성 끊김", error_kind="connection"),
        ProviderError(429, True, "이름 없는 한도"),  # 이름이 없으면(other) 횟수 갈래 — 모의·옛 호출의 BASE 그대로
    ],
)
def test_s14_server_and_connection_errors_keep_two_retries_with_jitter(prompts: Path, error: ProviderError) -> None:
    h = retrying(prompts, jitter=1.0)
    for _ in range(5):
        h.mock.enqueue(error)

    result = h.client.call(BASE)

    assert isinstance(result, ProviderFailed)
    assert len(h.mock.calls) == 3
    assert h.sleeps == [500.0, 1_000.0]


def test_s14_a_maybe_billed_overload_uses_the_count_branch(prompts: Path) -> None:
    """스트림 중 과부하(HTTP 200)는 과금됐을 수 있다 — 예산 갈래가 아니라 max_retries(§1-3, 영문번역 머리 여유)."""
    h = retrying(prompts)
    for _ in range(10):
        h.mock.enqueue(ProviderError(200, True, "합성 스트림 과부하", error_kind="overloaded"))

    result = h.client.call(BASE)

    assert isinstance(result, ProviderFailed)
    assert len(h.mock.calls) == 1 + POLICY.max_retries == 3
    assert all(r.cost_bound_usd is not None for r in h.log.records)


def test_s14_a_timeout_is_not_retried_and_falls_back(prompts: Path) -> None:
    h = retrying(prompts)
    h.mock.enqueue(ProviderTimeout(message="합성 시간 초과")).enqueue_text("x")
    h.mock_b.enqueue_text("ok")
    assert isinstance(h.client.call(FALLBACK), Success)
    assert (len(h.mock.calls), h.sleeps) == (1, [])


# ── B2 provider_retry={} ────────────────────────────────────────────────


@pytest.mark.parametrize("error", [limited(retry_after_ms=1), overloaded()])
def test_b2_an_empty_provider_retry_turns_the_budget_branch_off_too(prompts: Path, error: ProviderError) -> None:
    h = harness(prompts, provider_retry={}, jitter=lambda: 0.0)
    for _ in range(3):
        h.mock.enqueue(error)
    assert isinstance(h.client.call(BASE), ProviderFailed)
    assert (len(h.mock.calls), h.sleeps) == (1, [])


def test_b2_the_defaults_have_the_budget_and_a_missing_provider_has_none() -> None:
    assert all(
        (p.wait_budget_ms, p.max_budget_retries) == (RATE_LIMIT_WAIT_BUDGET_MS, RATE_LIMIT_MAX_RETRIES)
        for p in DEFAULT_PROVIDER_RETRY.values()
    )
    assert set(DEFAULT_PROVIDER_RETRY) == {"gemini", "openai", "anthropic"}


# ── S15 임베딩 재시도 ────────────────────────────────────────────────────


def embedding_client(
    provider: MockEmbeddingProvider, **options: object
) -> tuple[EmbeddingClient, MemorySink, list[float]]:
    sink = MemorySink()
    sleeps: list[float] = []
    options.setdefault("provider_retry", {"mock": POLICY})
    options.setdefault("jitter", lambda: 0.0)
    client = EmbeddingClient(
        config=synthetic_config(),
        providers={"mock": provider},
        log=sink,
        sleep=sleeps.append,
        **options,  # pyright: ignore[reportArgumentType]
    )
    return client, sink, sleeps


EMBED = EmbedRequest(inputs=("합성",), route="mock-gw1", tags=TAGS)


def test_s15_embedding_retries_two_rate_limits_then_succeeds(blocked_network: list[object]) -> None:
    provider = MockEmbeddingProvider().enqueue(limited(retry_after_ms=300)).enqueue(limited())
    client, sink, sleeps = embedding_client(provider)

    result = client.embed(EMBED)

    assert isinstance(result, Embedded)
    assert len(provider.calls) == 3
    assert sleeps == [300.0, 2_000.0]
    rows = [(r.result_kind, r.provider_retry, r.previous_error_status, r.retry_wait_ms) for r in sink.records]
    assert rows[1:] == [("provider_error", 1, 429, 300.0), ("success", 2, 429, 2_000.0)]
    assert rows[0][:2] == ("provider_error", None)
    assert [a.provider_retry for a in result.meta.attempts] == [None, 1, 2]
    assert blocked_network == []


def test_s15_embedding_rate_limits_use_the_wait_budget_beyond_max_retries_with_jitter() -> None:
    """429 넷(대기 없음) 뒤 성공 — 예산 갈래(max_retries 2 보다 많이)이고 물러섬에 주입 지터(1.0 → × 0.5)가 얹힌다
    (검증 ② B1: 임베딩이 채팅과 같은 next_retry 를 쓰는지)."""
    provider = MockEmbeddingProvider()
    for _ in range(4):
        provider.enqueue(limited())
    client, sink, sleeps = embedding_client(provider, jitter=lambda: 1.0)

    result = client.embed(EMBED)

    assert isinstance(result, Embedded)
    assert len(provider.calls) == 5
    assert sleeps == [500.0, 1_000.0, 2_000.0, 4_000.0]
    assert [r.provider_retry for r in sink.records] == [None, 1, 2, 3, 4]
    assert [r.retry_wait_ms for r in sink.records] == [None, 500.0, 1_000.0, 2_000.0, 4_000.0]
    assert sink.records[-1].result_kind == "success"


def test_s15_the_budget_is_checked_before_every_embedding_retry() -> None:
    provider = MockEmbeddingProvider().enqueue(limited())
    client, sink, _ = embedding_client(
        provider, limits=[BudgetLimit(scope=Scope(tenant=TAGS.tenant), limit_usd=0.00001)]
    )
    # 첫 시도 뒤 같은 꼬리표의 다른 호출이 상한을 채운 꼴: 장부에 비용 한 줄을 심는다.
    original = sink.record

    def record_and_spend(line: object) -> None:
        original(line)  # pyright: ignore[reportArgumentType]
        if len(sink.records) == 1:
            original(replace(sink.records[0], cost_usd=1.0, result_kind="success", attempt=99))

    sink.record = record_and_spend  # pyright: ignore[reportAttributeAccessIssue]
    result = client.embed(EMBED)

    assert result.kind == "budget_exceeded"
    assert len(provider.calls) == 1
    assert [(r.result_kind, r.provider_retry) for r in sink.records if r.attempt != 99] == [
        ("provider_error", None),
        ("budget_exceeded", 1),
    ]


def test_s15_credit_exhausted_embedding_is_not_retried() -> None:
    provider = MockEmbeddingProvider().enqueue(ProviderError(429, False, "합성 크레딧", error_kind="quota_exhausted"))
    client, _, sleeps = embedding_client(provider)
    result = client.embed(EMBED)
    assert isinstance(result, EmbedProviderFailed)
    assert (result.retryable, result.error_kind, len(provider.calls), sleeps) == (False, "quota_exhausted", 1, [])


def test_s15_an_empty_provider_retry_turns_embedding_retry_off() -> None:
    provider = MockEmbeddingProvider().enqueue(limited()).enqueue(limited())
    client, _, sleeps = embedding_client(provider, provider_retry={})
    assert isinstance(client.embed(EMBED), EmbedProviderFailed)
    assert (len(provider.calls), sleeps) == (1, [])


def test_s15_the_embedding_server_error_keeps_two_retries() -> None:
    provider = MockEmbeddingProvider()
    for _ in range(5):
        provider.enqueue(ProviderError(500, True, "합성", error_kind="server_error"))
    client, _, sleeps = embedding_client(provider)
    assert isinstance(client.embed(EMBED), EmbedProviderFailed)
    assert (len(provider.calls), sleeps) == (3, [1_000.0, 2_000.0])


def test_s15_vectors_after_a_retry_keep_their_order() -> None:
    vectors = EmbeddingVectors(vectors=((0.0,) * 256,), input_tokens=1, model_id="m")
    provider = MockEmbeddingProvider().enqueue(limited()).enqueue(vectors)
    client, _, _ = embedding_client(provider)
    result = client.embed(EMBED)
    assert isinstance(result, Embedded) and result.vectors == vectors.vectors


# ── S16 624 고리 실패의 검색 수 ─────────────────────────────────────────


def searching(prompts: Path) -> Harness:
    return harness(prompts, config=config_with(hosted_tool_pricing=HOSTED), provider_retry={})


SEARCH = replace(REQUEST, tools=(*TOOLS, WebSearchTool()))


@pytest.mark.parametrize(
    "last",
    [
        Truncated(text="잘림", usage=USAGE_SYNTHETIC, hosted_calls=1),
        Refusal(text="거부", category=None, usage=USAGE_SYNTHETIC, hosted_calls=1),
    ],
)
def test_s16_a_cut_or_refused_last_answer_adds_its_searches(prompts: Path, last: Truncated | Refusal) -> None:
    h = searching(prompts)
    h.mock.enqueue_tool_calls([("tool_a", "{}")], usage=USAGE_SYNTHETIC, hosted_calls=2)
    h.mock.enqueue(last)

    result, _ = run(h, SEARCH)

    assert isinstance(result, ToolLoopFailed)
    assert result.hosted_calls == 3
    assert [step.hosted_calls for step in result.steps] == [2]


@pytest.mark.parametrize(
    "last",
    [ProviderError(500, False, "합성"), ProviderTimeout(message="합성")],
)
def test_s16_a_provider_failure_keeps_the_earlier_steps_only(
    prompts: Path, last: ProviderError | ProviderTimeout
) -> None:
    h = searching(prompts)
    h.mock.enqueue_tool_calls([("tool_a", "{}")], usage=USAGE_SYNTHETIC, hosted_calls=2)
    h.mock.enqueue(last)
    result, _ = run(h, SEARCH)
    assert isinstance(result, ToolLoopFailed) and result.hosted_calls == 2


def test_s16_an_executor_exception_and_a_cap_keep_the_running_total(prompts: Path) -> None:
    h = searching(prompts)
    h.mock.enqueue_tool_calls([("tool_a", "{}")], usage=USAGE_SYNTHETIC, hosted_calls=2)

    def boom(_name: str, _arguments: str) -> str:
        raise RuntimeError("합성")

    raised = h.client.call_tools(SEARCH, boom)
    assert isinstance(raised, ToolLoopFailed) and raised.hosted_calls == 2

    h = searching(prompts)
    h.mock.enqueue_tool_calls([("tool_a", "{}")], usage=USAGE_SYNTHETIC, hosted_calls=4)
    capped, _ = run(h, replace(SEARCH, max_cost_usd=0.000001))
    assert isinstance(capped, ToolLoopFailed)
    assert (capped.budget_source, capped.hosted_calls) == ("loop", 4)


def test_s16_the_new_field_sits_after_budget_source_with_a_default() -> None:
    from dataclasses import fields

    names = [f.name for f in fields(ToolLoopFailed)]
    assert names == ["failure", "steps", "meta", "budget_source", "hosted_calls", "kind"]
