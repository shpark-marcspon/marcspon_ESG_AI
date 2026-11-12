"""설정에서 LlmClient 세우기(core/llm/setup.py), 어댑터 고르기(core/resources/llm.py). 순수 층."""

from pathlib import Path
from typing import Any

import pytest

from esgapi.config.env import LlmSettings
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.gemini import GeminiProvider
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.setup import build_client, make_sink
from esgapi.core.llm.sinks.jsonl import JsonlFileSink
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import InvokeOptions, ProviderError, ProviderRequest, Tags, TextPart
from esgapi.core.resources.llm import LIVE_PROVIDERS, MOCK_PROVIDERS, make
from esgapi.core.resources.ports.llm import Provider

REQUEST = CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags("t", "core"))
PLAIN = ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10)


# ── 어댑터 고르기 ──


def test_make_gives_the_mock_provider() -> None:
    """core/resources/llm.py 의 make("mock") 이 모의 공급사를 준다."""
    provider = make("mock")
    assert isinstance(provider, MockProvider)
    assert provider.name == "mock"
    assert isinstance(make("mock-b"), MockProvider)
    assert make("mock-b").name == "mock-b"


@pytest.mark.parametrize("name", LIVE_PROVIDERS)
@pytest.mark.parametrize("key", [None, "", "   "])
def test_live_provider_without_a_key_is_a_named_error_and_no_sdk_object_is_made(
    monkeypatch: pytest.MonkeyPatch, name: str, key: str | None
) -> None:
    made: list[str] = []
    for module, function in (
        ("openai", "create_openai_client"),
        ("anthropic", "create_anthropic_client"),
        ("gemini", "create_gemini_client"),
    ):
        monkeypatch.setattr(f"esgapi.core.llm.providers.{module}.{function}", made.append)
    with pytest.raises(LiveSetupError, match=name):
        make(name, api_key=key)
    assert made == []


def test_live_provider_gets_exactly_the_given_key(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def record(name: str) -> Any:
        def create(api_key: str) -> object:
            seen[name] = api_key
            return object()

        return create

    monkeypatch.setattr("esgapi.core.llm.providers.openai.create_openai_client", record("openai"))
    monkeypatch.setattr("esgapi.core.llm.providers.anthropic.create_anthropic_client", record("anthropic"))
    monkeypatch.setattr("esgapi.core.llm.providers.gemini.create_gemini_client", record("gemini"))
    kinds = {"openai": OpenAIProvider, "anthropic": AnthropicProvider, "gemini": GeminiProvider}
    for name in LIVE_PROVIDERS:
        provider = make(name, api_key=f"key-{name}-synthetic")
        assert isinstance(provider, kinds[name])
        assert provider.name == name
    assert seen == {name: f"key-{name}-synthetic" for name in LIVE_PROVIDERS}


@pytest.mark.parametrize("name", LIVE_PROVIDERS)
def test_assemble_only_adapter_builds_requests_but_cannot_call(name: str) -> None:
    provider = make(name, assemble_only=True)
    assert isinstance(provider.build_request(PLAIN), dict)
    response = provider.invoke(PLAIN, InvokeOptions(timeout_ms=1000))
    assert isinstance(response, ProviderError)
    assert "주입되지 않았다" in response.message


def test_unknown_provider_is_a_named_error() -> None:
    with pytest.raises(LiveSetupError, match="nope"):
        make("nope", api_key="key-synthetic")


# ── 설정에서 클라이언트 세우기 ──


def test_sink_follows_the_settings(tmp_path: Path) -> None:
    assert isinstance(make_sink(LlmSettings()), MemorySink)
    path = tmp_path / "calls.jsonl"
    assert isinstance(make_sink(LlmSettings(log_sink="jsonl", jsonl_path=str(path))), JsonlFileSink)
    with pytest.raises(LiveSetupError, match="LLM_JSONL_PATH"):
        make_sink(LlmSettings(log_sink="jsonl"))


def test_server_client_has_no_mock_route_and_starts_without_any_key() -> None:
    """키가 하나도 없어도 클라이언트는 선다. 모의 공급사와 가상 모델은 서버의 클라이언트에 싣지 않는다."""
    client = build_client(LlmSettings())
    with pytest.raises(LlmConfigError, match="경로 mock"):
        client.call(REQUEST)
    assert client.provider("mock") is None
    # 키 없는 공급사는 부를 때에야 오류가 난다(그 공급사를 안 쓰는 경로는 영향이 없다).
    with pytest.raises(LiveSetupError, match="anthropic"):
        client.call(CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="light", tags=Tags("t", "core")))


def test_mock_client_runs_end_to_end_with_the_packaged_prompt_and_data() -> None:
    sink = MemorySink()
    client = build_client(LlmSettings(), mock=True, sink=sink)
    mock = client.provider("mock")
    assert isinstance(mock, MockProvider)
    mock.enqueue_text("안녕하세요")
    result = client.call(REQUEST)
    assert result.kind == "success"
    assert (sink.records[0].prompt_id, sink.records[0].tenant, sink.records[0].module) == ("core/hello@1", "t", "core")


class Recorder:
    def __init__(self) -> None:
        self.asked: list[tuple[str, str | None, bool]] = []

    def __call__(self, name: str, *, api_key: str | None = None, assemble_only: bool = False) -> Provider:
        self.asked.append((name, api_key, assemble_only))
        return MockProvider(name)


def test_keys_go_from_settings_to_make_and_providers_are_made_lazily_once() -> None:
    recorder = Recorder()
    settings = LlmSettings(openai_api_key="key-o-synthetic", gemini_api_key="key-g-synthetic")
    client = build_client(settings, make=recorder)
    assert recorder.asked == []  # 세울 때는 아무 어댑터도 만들지 않는다
    assert client.provider("openai") is client.provider("openai")
    assert client.provider("gemini") is not None
    assert recorder.asked == [("openai", "key-o-synthetic", False), ("gemini", "key-g-synthetic", False)]
    assert client.provider("nope") is None


def test_rpm_wraps_only_live_providers_in_a_throttle() -> None:
    recorder = Recorder()
    throttled_client = build_client(LlmSettings(openai_api_key="key-synthetic", rpm=30), mock=True, make=recorder)
    live = throttled_client.provider("openai")
    assert live is not None
    assert not isinstance(live, MockProvider)  # 간격 조절로 감쌌다
    assert live.name == "openai"
    assert isinstance(throttled_client.provider("mock"), MockProvider)  # 모의 공급사는 감싸지 않는다
    plain = build_client(LlmSettings(openai_api_key="key-synthetic"), make=Recorder()).provider("openai")
    assert isinstance(plain, MockProvider)


def test_models_file_setting_replaces_the_packaged_file(tmp_path: Path) -> None:
    with pytest.raises(LlmConfigError, match="읽을 수 없다"):
        build_client(LlmSettings(models_file=str(tmp_path / "missing.json")))
    assert MOCK_PROVIDERS == ("mock", "mock-b")
