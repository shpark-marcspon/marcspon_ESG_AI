# pyright: reportPrivateUsage=false
"""어림이 「과금됐을 수 있는 몫」을 빠뜨리지 않는다(밴드 LH3 T4·T6·T7 — MARC-ISSUE-413 I3·I6, MARC-ISSUE-417). 순수 층.

  T4  web_search 를 실은 시도의 실패 어림 = 토큰 어림 + max_hosted_calls × 건당 요금(Q3 가) · max_hosted_calls 가 없으면
      1건(Q3 가-2 — 과소, 받아들임) · web_search 를 안 실으면 BASE 값
  T6  임베딩 「성공·토큰 None」 줄의 cost_bound_usd = 실패 묶음과 같은 보수 어림(Q6) · 토큰 있는 성공은 None ·
      그 어림으로 상한 셈을 하는 싱크면 토큰 없는 성공 둘 뒤 셋째가 공급사 전 budget_exceeded
  T7  dry-run 의 캐시 쓰기 할증(Q8·Q9): 캐시 지정 요청 · 쓰기 단가가 입력보다 큰 모델(anthropic 실모델·가상 모델)은
      cost_upper_bound_usd·worst_case_usd = 손셈 · 캐시 지정 없음·쓰기 단가 = 입력(openai)·쓰기 단가 < 입력(가짜 단가)은
      BASE 꼴 · 실패 어림(`_worst_once_usd`)도 같은 나눔
★ 단가·건당 요금은 설정(models.json·models.synthetic.json)에서 읽는다 — 숫자를 박지 않는다. 네트워크 0.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import CallRequest, LlmClient, ToolCallRequest
from esgapi.core.llm.config import HostedToolPricing, LlmConfig, resolve_embedding_route
from esgapi.core.llm.cost import HeuristicTokenEstimator, compute_cost_usd, round_usd
from esgapi.core.llm.embedding import EmbedBudgetExceeded, Embedded, EmbeddingClient, EmbedRequest
from esgapi.core.llm.embedding_types import EmbeddingVectors
from esgapi.core.llm.log import CallRecord
from esgapi.core.llm.prompts import FilePromptStore
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.mock import MockEmbeddingProvider, MockProvider
from esgapi.core.llm.providers.openai import EMBEDDING_SDK_MAX_RETRIES, OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import FunctionTool, ProviderTimeout, Scope, Usage, WebSearchTool
from esgapi.core.tests.llm_support import TAGS, config_with, harness, synthetic_config, write_prompts

CACHED = CallRequest(prompt="t/cached-long@1", vars={"question": "q"}, route="mock", tags=TAGS)
PLAIN = CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS)
TOOL = FunctionTool(name="lookup", description="합성 도구", parameters={"type": "object", "properties": {}})


@pytest.fixture
def prompts(tmp_path: Path) -> Path:
    return write_prompts(tmp_path)


def hand(input_tokens: int, cached: int, output_tokens: int, config: LlmConfig, key: str) -> float:
    """손셈: 캐시 지정 몫을 쓰기 단가로, 나머지를 평 입력으로(Q8)."""
    usage = Usage(
        input_tokens=input_tokens - cached, output_tokens=output_tokens, cache_read_tokens=0, cache_write_tokens=cached
    )
    return compute_cost_usd(usage, config.models[key].pricing)


def plain(input_tokens: int, output_tokens: int, config: LlmConfig, key: str) -> float:
    """BASE 꼴: 입력 전부 평 입력 단가."""
    usage = Usage(input_tokens=input_tokens, output_tokens=output_tokens, cache_read_tokens=0, cache_write_tokens=0)
    return compute_cost_usd(usage, config.models[key].pricing)


def real_client(prompts: Path, config: LlmConfig) -> LlmClient:
    """실공급사 어댑터를 SDK 없이(조립만) 실은 클라이언트 — dry-run 만 쓴다."""
    return LlmClient(
        config=config,
        providers={"anthropic": AnthropicProvider(None), "openai": OpenAIProvider(None), "mock": MockProvider()},
        prompts=FilePromptStore(prompts),
        log=MemorySink(),
    )


# ── T7 dry-run 할증 ──


def writes_dearer(config: LlmConfig, key: str) -> bool:
    pricing = config.models[key].pricing
    return pricing.cache_write > pricing.input


@pytest.mark.parametrize(("route", "key"), [("light-anthropic", "claude-haiku-4-5"), ("mock", "mock-synthetic")])
def test_t7_cached_requests_on_a_dearer_write_model_bound_the_cache_at_the_write_rate(
    prompts: Path, blocked_network: list[object], route: str, key: str
) -> None:
    config = synthetic_config()
    assert writes_dearer(config, key)
    estimate = real_client(prompts, config).dry_run(replace(CACHED, route=route)).estimate
    assert estimate.cacheable_tokens > 0
    expected = hand(estimate.input_tokens, estimate.cacheable_tokens, estimate.max_output_tokens, config, key)
    assert expected > plain(estimate.input_tokens, estimate.max_output_tokens, config, key)
    assert estimate.cost_upper_bound_usd == expected
    assert estimate.worst_case_usd == round_usd(expected * estimate.max_attempts)
    assert blocked_network == []


def test_t7_a_request_without_a_cache_marker_keeps_the_base_value(prompts: Path) -> None:
    config = synthetic_config()
    estimate = real_client(prompts, config).dry_run(replace(PLAIN, route="light-anthropic")).estimate
    assert estimate.cacheable_tokens == 0
    base = plain(estimate.input_tokens, estimate.max_output_tokens, config, "claude-haiku-4-5")
    assert (estimate.cost_upper_bound_usd, estimate.worst_case_usd) == (base, base)


@pytest.mark.parametrize(
    ("route", "key"),
    [("light-openai-41", "gpt-4.1-mini"), ("standard-openai-41", "gpt-4.1"), ("standard-openai-4o", "gpt-4o")],
)
def test_t7_a_model_whose_write_rate_is_not_dearer_keeps_the_base_value(prompts: Path, route: str, key: str) -> None:
    config = synthetic_config()
    assert not writes_dearer(config, key)
    estimate = real_client(prompts, config).dry_run(replace(CACHED, route=route)).estimate
    assert estimate.cacheable_tokens > 0
    assert estimate.cost_upper_bound_usd == plain(estimate.input_tokens, estimate.max_output_tokens, config, key)


def test_t7_a_cheaper_write_rate_never_lowers_the_bound(prompts: Path) -> None:
    base = synthetic_config().models["mock-synthetic"].pricing
    config = config_with(pricing=base.model_copy(update={"cache_write": base.input / 2}))
    estimate = real_client(prompts, config).dry_run(CACHED).estimate
    assert estimate.cacheable_tokens > 0
    assert estimate.cost_upper_bound_usd == plain(
        estimate.input_tokens, estimate.max_output_tokens, config, "mock-synthetic"
    )


def test_t7_the_tool_loop_steps_use_the_same_split(prompts: Path) -> None:
    config = synthetic_config()
    request = ToolCallRequest(
        prompt="t/cached-long@1", vars={"question": "q"}, route="mock", tags=TAGS, tools=(TOOL,), max_steps=2
    )
    report = harness(prompts, config=config).client.dry_run_tools(request)
    estimate, loop = report.estimate, report.tool_loop
    assert loop is not None and estimate.cacheable_tokens > 0
    out = estimate.max_output_tokens
    expected = tuple(
        hand(estimate.input_tokens + (step - 1) * out, estimate.cacheable_tokens, out, config, "mock-synthetic")
        for step in (1, 2)
    )
    assert loop.step_upper_bounds_usd == expected
    assert estimate.cost_upper_bound_usd == expected[0]


def timeout_bound(prompts: Path, config: LlmConfig, request: CallRequest[str] = CACHED) -> float:
    h = harness(prompts, config=config)
    h.mock.enqueue(ProviderTimeout(message="합성"))
    h.client.call(request)
    (record,) = h.log.records
    assert record.result_kind == "timeout" and record.cost_bound_usd is not None
    return record.cost_bound_usd


def test_t7_the_failed_attempt_bound_adds_the_write_premium_on_the_cache_share(prompts: Path) -> None:
    config = synthetic_config()
    pricing = config.models["mock-synthetic"].pricing
    assert pricing.cache_write > pricing.input
    level = config_with(pricing=pricing.model_copy(update={"cache_write": pricing.input}))
    cached = harness(prompts, config=config).client.dry_run(CACHED).estimate.cacheable_tokens
    premium = cached * (pricing.cache_write - pricing.input) / 1_000_000
    assert timeout_bound(prompts, config) == pytest.approx(timeout_bound(prompts, level) + premium, abs=1e-6)
    # 캐시 지정이 없는 요청은 두 단가에서 같다(BASE)
    assert timeout_bound(prompts, config, PLAIN) == timeout_bound(prompts, level, PLAIN)


# ── T4 web_search 실패 어림 ──


def hosted_from_settings() -> HostedToolPricing:
    """건당 요금은 설정의 실모델에서 읽는다(models.json — 새 수치 0)."""
    hosted = synthetic_config().models["gpt-4.1"].hosted_tool_pricing
    assert hosted is not None and hosted.web_search_per_call > 0
    return hosted


def tool_timeout_bound(prompts: Path, hosted: HostedToolPricing, request: ToolCallRequest) -> tuple[float, int]:
    h = harness(prompts, config=config_with(hosted_tool_pricing=hosted))
    h.mock.enqueue(ProviderTimeout(message="합성"))
    h.client.call_tools(request, lambda name, arguments: "")
    (record,) = h.log.records
    assert record.result_kind == "timeout" and record.cost_bound_usd is not None
    return record.cost_bound_usd, len(h.mock.calls)


SEARCH = ToolCallRequest(
    prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, tools=(WebSearchTool(),), max_steps=2
)


@pytest.mark.parametrize(("calls", "counted"), [(3, 3), (1, 1), (None, 1)])
def test_t4_a_failed_web_search_attempt_adds_the_per_call_fee(
    prompts: Path, blocked_network: list[object], calls: int | None, counted: int
) -> None:
    hosted = hosted_from_settings()
    request = replace(SEARCH, max_hosted_calls=calls)
    bound, sent = tool_timeout_bound(prompts, hosted, request)
    tokens_only, _ = tool_timeout_bound(prompts, HostedToolPricing(web_search_per_call=0.0), request)
    assert sent == 1
    assert bound == pytest.approx(tokens_only + counted * hosted.web_search_per_call, abs=1e-9)
    assert blocked_network == []


def test_t4_without_web_search_the_bound_is_the_base_value(prompts: Path) -> None:
    request = replace(SEARCH, tools=(TOOL,))
    with_fee, _ = tool_timeout_bound(prompts, hosted_from_settings(), request)
    without_fee, _ = tool_timeout_bound(prompts, HostedToolPricing(web_search_per_call=0.0), request)
    assert with_fee == without_fee


# ── T6 임베딩 「성공·토큰 None」 ──


def embedding_client(
    sink: MemorySink, replies: list[EmbeddingVectors], limits: tuple[BudgetLimit, ...] = ()
) -> EmbeddingClient:
    mock = MockEmbeddingProvider()
    for reply in replies:
        mock.enqueue(reply)
    return EmbeddingClient(config=synthetic_config(), providers={"mock": mock}, log=sink, limits=limits)


def vectors(tokens: int | None) -> EmbeddingVectors:
    dims = resolve_embedding_route(synthetic_config(), "mock-gw1").dimensions
    return EmbeddingVectors(vectors=(tuple(0.5 for _ in range(dims)),), input_tokens=tokens)


def embedding_hand(text: str) -> float:
    config = synthetic_config()
    model = resolve_embedding_route(config, "mock-gw1")
    tokens = HeuristicTokenEstimator(config.token_estimate).estimate(text)
    return round_usd(tokens * model.pricing.input / 1_000_000 * (1 + EMBEDDING_SDK_MAX_RETRIES))


def test_t6_a_success_without_tokens_carries_the_conservative_bound(blocked_network: list[object]) -> None:
    sink = MemorySink()
    result = embedding_client(sink, [vectors(None)]).embed(
        EmbedRequest(inputs=("합성 하나",), route="mock-gw1", tags=TAGS)
    )
    assert isinstance(result, Embedded)
    (record,) = sink.records
    assert (record.result_kind, record.cost_usd) == ("success", None)
    assert record.cost_bound_usd == embedding_hand("합성 하나")
    assert result.meta.total_cost_usd == 0  # 결과·Attempt 는 그대로
    assert blocked_network == []


def test_t6_a_success_with_tokens_has_no_bound() -> None:
    sink = MemorySink()
    embedding_client(sink, [vectors(7)]).embed(EmbedRequest(inputs=("합성 하나",), route="mock-gw1", tags=TAGS))
    (record,) = sink.records
    assert record.cost_usd is not None and record.cost_bound_usd is None


class BoundSink(MemorySink):
    """실행기의 상한 셈(runs/context.py RunCallSink)처럼 cost_usd 가 없으면 cost_bound_usd 를 센다 — core 시험은 runs 를
    import 하지 않는다(.importlinter)."""

    def __init__(self) -> None:
        super().__init__()
        self.total = 0.0

    def record(self, record: CallRecord) -> None:
        self.total += record.cost_usd if record.cost_usd is not None else (record.cost_bound_usd or 0.0)
        super().record(record)

    def spent(self, scope: Scope) -> float:
        return round_usd(self.total)


def test_t6_two_successes_without_tokens_reach_the_limit_before_the_third(blocked_network: list[object]) -> None:
    once = embedding_hand("합성 하나")
    sink = BoundSink()
    limit = BudgetLimit(scope=Scope(), limit_usd=once * 1.5)
    client = embedding_client(sink, [vectors(None), vectors(None), vectors(None)], (limit,))
    request = EmbedRequest(inputs=("합성 하나",), route="mock-gw1", tags=TAGS)
    results = [client.embed(request) for _ in range(3)]
    assert [type(r) for r in results] == [Embedded, Embedded, EmbedBudgetExceeded]
    assert [r.result_kind for r in sink.records] == ["success", "success", "budget_exceeded"]
    assert blocked_network == []
