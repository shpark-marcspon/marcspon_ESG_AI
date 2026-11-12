"""temperature 자리(밴드 LT1 `MARC-TICK-136`): 값이 없으면 본문·해시가 그대로, 값이 있으면 받는 어댑터가 싣고,
받지 않는 모델·공급사·범위 밖 값은 공급사를 부르기 전에 LlmConfigError. 순수 층.

실제 공급사로 가는 호출은 없다. SDK 클라이언트 자리에 가짜를 넣는다. 토큰 수와 본문은 전부 가상(synthetic) 값이다.
"""

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from google.genai import types as genai_types

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.config import LlmConfig, ModelConfig
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.log import sha256_json
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.gemini import GeminiProvider
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.types import ProviderError, ProviderRequest
from esgapi.core.tests.llm_support import TAGS, harness, synthetic_config
from esgapi.core.tests.test_llm_adapters import OPTIONS, PLAIN, REQUEST, FakeAnthropic, FakeOpenAI
from esgapi.core.tests.test_llm_gemini import FakeGemini

BASE = CallRequest(prompt="t/plain@1", vars={"question": "분류해 줘"}, route="mock", tags=TAGS)
COLD = 0.0

# 기준 커밋 d64d5e2(temperature 자리가 생기기 전)에서 잰 sha256. 값을 주지 않은 요청은 이것과 글자째 같아야 한다.
BASELINE = {
    "REQUEST.to_json": "63858d4be1627f83185648f6643804995427c9439b2b5f3d4faa14f8e068afa4",
    "PLAIN.to_json": "47a0165c0c12a7332310d9de172dbc1437a05d841b908be7458df27ca686baf1",
    "openai.build_request": "6e019d3c93cd23f7d95cc29b01bc2c4ca7767a019bfa89263cd10d5bdb9161d4",
    "anthropic.build_request": "5e07dd2a401fca069d6229882eb7d48e0d6fdc16252fd3de101535a61b1f3233",
    "gemini.build_request": "b269d1617d925fcab95ccef9d6b19934b935f59a25fa5b7c0bd02c597a6841d2",
    "call.request_hash": "deda24cad7fefb49beb73c426b9702520ebae57ef3b94240be66cac96caa1b0b",
}


def config_with_route(name: str, keys: tuple[str, ...], **extra: ModelConfig) -> LlmConfig:
    config = synthetic_config()
    return LlmConfig(
        models={**config.models, **extra},
        routes={**config.routes, name: keys},
        token_estimate=config.token_estimate,
    )


def renamed(key: str, new_key: str, api_model_id: str) -> ModelConfig:
    """실제 모델 설정을 다른 api_model_id 로 덧씌운 것. 설정 파일은 건드리지 않는다."""
    entry = synthetic_config().models[key].entry
    return ModelConfig(key=new_key, entry=entry.model_copy(update={"api_model_id": api_model_id}))


# ── 값이 없으면 기준과 글자째 같다 ──


def test_without_temperature_bodies_and_hashes_match_the_baseline_commit(prompt_root: Path) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("a")
    h.client.call(BASE)
    measured = {
        "REQUEST.to_json": sha256_json(REQUEST.to_json()),
        "PLAIN.to_json": sha256_json(PLAIN.to_json()),
        "openai.build_request": sha256_json(OpenAIProvider().build_request(REQUEST)),
        "anthropic.build_request": sha256_json(AnthropicProvider().build_request(REQUEST)),
        "gemini.build_request": sha256_json(GeminiProvider().build_request(REQUEST)),
        "call.request_hash": h.log.records[0].request_hash,
    }
    assert measured == BASELINE
    assert "temperature" not in REQUEST.to_json()
    assert h.mock.calls[0].temperature is None


# ── 값 0.0 은 실린다(0.0 이 거짓값이라 빠지는 실수를 문다) ──


def test_zero_temperature_goes_into_the_neutral_body_and_changes_the_hash(prompt_root: Path) -> None:
    h = harness(prompt_root, store_bodies=True)
    h.mock.enqueue_text("a").enqueue_text("b")
    h.client.call(BASE)
    h.client.call(replace(BASE, temperature=COLD))
    plain, cold = h.log.records
    assert cold.request_hash != plain.request_hash
    assert cold.body is not None
    assert cold.body.request["temperature"] == COLD
    assert replace(PLAIN, temperature=COLD).to_json()["temperature"] == COLD
    # 모의 공급사는 받아 기록만 한다.
    assert h.mock.calls[1].temperature == COLD
    assert MockProvider().build_request(replace(PLAIN, temperature=COLD)) == {"mock": True, **cold_plain()}


def cold_plain() -> dict[str, object]:
    return replace(PLAIN, temperature=COLD).to_json()


def test_openai_adapter_sends_zero_temperature() -> None:
    request = replace(REQUEST, temperature=COLD)
    assert OpenAIProvider().build_request(request)["temperature"] == COLD
    fake = FakeOpenAI(RuntimeError("가짜 SDK 는 답하지 않는다"))
    OpenAIProvider(fake).invoke(request, OPTIONS)
    (sent,) = fake.responses.seen
    assert sent["temperature"] == COLD


def test_gemini_adapter_sends_zero_temperature_in_both_bodies() -> None:
    request = replace(REQUEST, temperature=COLD)
    config = GeminiProvider().build_request(request)["config"]
    assert isinstance(config, dict)
    assert config["temperature"] == COLD
    fake = FakeGemini(RuntimeError("가짜 SDK 는 답하지 않는다"))
    GeminiProvider(fake).invoke(request, OPTIONS)
    (sent,) = fake.models.seen
    sdk_config = sent["config"]
    assert isinstance(sdk_config, genai_types.GenerateContentConfig)
    assert sdk_config.temperature == COLD


def test_anthropic_adapter_refuses_temperature_instead_of_dropping_it() -> None:
    request = replace(PLAIN, temperature=COLD)
    with pytest.raises(LlmConfigError, match="temperature"):
        AnthropicProvider().build_request(request)
    fake = FakeAnthropic(RuntimeError("부르면 안 된다"))
    result = AnthropicProvider(fake).invoke(request, OPTIONS)
    assert isinstance(result, ProviderError)
    assert not result.retryable
    assert fake.messages.seen == []


# ── 받지 않는 모델·공급사·범위 밖: 공급사를 부르기 전에 예외 ──


@pytest.mark.parametrize(
    ("route", "keys"),
    [
        ("openai-luna", ("gpt-6-luna",)),
        ("openai-sol", ("gpt-6.1-sol",)),
        ("anthropic-haiku", ("claude-haiku-4-5",)),
        ("anthropic-sonnet", ("claude-sonnet-4-6",)),
        # 주 모델은 받지만 대체 모델이 받지 않는다: 대체로 넘어갈 때 비로소 거부되지 않게 미리 거른다.
        ("mock-then-luna", ("mock-synthetic", "gpt-6-luna")),
        ("mock-then-haiku", ("mock-synthetic", "claude-haiku-4-5")),
    ],
)
def test_temperature_on_a_route_with_an_unsupported_model_is_refused_before_any_call(
    prompt_root: Path, route: str, keys: tuple[str, ...]
) -> None:
    h = harness(prompt_root, config=config_with_route(route, keys))
    h.mock.enqueue_text("부르면 안 된다")
    with pytest.raises(LlmConfigError, match="temperature 를 받지 않는다"):
        h.client.call(replace(BASE, route=route, temperature=COLD))
    with pytest.raises(LlmConfigError, match="temperature 를 받지 않는다"):
        h.client.dry_run(replace(BASE, route=route, temperature=COLD))
    assert h.mock.calls == []
    assert h.log.records == []


def test_the_same_unsupported_routes_without_temperature_are_not_checked(prompt_root: Path) -> None:
    mock, openai_stand_in = MockProvider(), MockProvider("openai")
    config = config_with_route("mock-then-luna", ("mock-synthetic", "gpt-6-luna"))
    h = harness(prompt_root, config=config, providers={"mock": mock, "openai": openai_stand_in})
    mock.enqueue_text("ok")
    result = h.client.call(replace(BASE, route="mock-then-luna"))
    assert result.kind == "success"
    report = h.client.dry_run(replace(BASE, route="mock-then-luna"))
    assert "temperature" not in cast("dict[str, object]", report.request)


def test_a_supported_openai_model_on_the_route_gets_the_value(prompt_root: Path) -> None:
    """gpt-4.1-mini 는 추론 모델이 아니라 받는다. 기준 커밋의 설정에는 없어 다른 모델 설정을 그 ID 로 덧씌운다."""
    mini = renamed("gpt-6-luna", "gpt-4.1-mini-synthetic", "gpt-4.1-mini")
    config = config_with_route("openai-mini", ("gpt-4.1-mini-synthetic",), **{mini.key: mini})
    h = harness(prompt_root, config=config, providers={"openai": OpenAIProvider()})
    report = h.client.dry_run(replace(BASE, route="openai-mini", temperature=COLD))
    body = cast("dict[str, object]", report.request)
    assert body["temperature"] == COLD
    assert body["model"] == "gpt-4.1-mini"


@pytest.mark.parametrize("value", [-0.1, 2.01, float("nan"), float("inf"), True, "0"])
def test_out_of_range_or_non_numeric_temperature_is_refused(prompt_root: Path, value: object) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("부르면 안 된다")
    with pytest.raises(LlmConfigError, match="temperature"):
        h.client.call(replace(BASE, temperature=value))  # type: ignore[arg-type]
    assert h.mock.calls == []


@pytest.mark.parametrize("value", [0, 0.0, 1.0, 2.0, 2])
def test_bounds_are_inclusive(prompt_root: Path, value: float) -> None:
    h = harness(prompt_root)
    h.mock.enqueue_text("ok")
    assert h.client.call(replace(BASE, temperature=value)).kind == "success"
    assert h.mock.calls[0].temperature == value


def test_provider_request_default_is_none() -> None:
    request = ProviderRequest(api_model_id="m", system=(), user=PLAIN.user, max_output_tokens=10)
    assert request.temperature is None
    assert request.to_json() == PLAIN.to_json()
