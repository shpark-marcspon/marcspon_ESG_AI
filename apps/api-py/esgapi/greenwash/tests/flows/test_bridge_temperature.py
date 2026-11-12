"""대화 다리의 기본 경로와 temperature(밴드 GTE1 `MARC-TICK-140`): 기본 경로 light-openai-41 이 실제 설정에서
gpt-4.1-mini 하나이고, 다리가 코랩 온도 0.0 을 그 모델에 넘기며, temperature 를 받지 않는 모델이 든 경로는 공급사를
부르기 전에 LlmConfigError.

공급사는 모의(MockProvider)를 공급사 이름 openai 자리에 끼운다 — 실제 네트워크·키 0.
"""

import pytest

from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Tags
from esgapi.greenwash.engines.e0 import checker as checker_mod
from esgapi.greenwash.engines.e0.ports import HumanMessage, Message, SystemMessage
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows.colab_e0 import CHAT_ROUTE, LlmChatBridge

TAGS = Tags(tenant="tenant-synthetic", module="greenwash")


def real_client(mock: MockProvider, sink: MemorySink) -> LlmClient:
    """저장소 정본 models.json(가상 모델 없음)과 openai 자리의 모의 공급사."""
    return LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": mock},
        prompts=PackagePromptStore(),
        log=sink,
        store_bodies=True,
    )


def detect_call() -> list[Message]:
    pack = default_prompts(PROMPT_VERSION)
    return [SystemMessage(content=pack.detect_system_prompt), HumanMessage(content="합성 쪽 글")]


def test_the_default_route_is_gpt41_mini_alone_in_the_real_config() -> None:
    config = load_config(default_config_sources(synthetic=False))
    assert CHAT_ROUTE == "light-openai-41"
    assert config.routes[CHAT_ROUTE] == ("gpt-4.1-mini",)
    assert config.models["gpt-4.1-mini"].entry.provider == "openai"
    assert config.models["gpt-4.1-mini"].entry.api_model_id == checker_mod.MODEL_NAME
    mock = MockProvider("openai")
    assert LlmChatBridge(real_client(mock, MemorySink()), tags=TAGS).route == "light-openai-41"


def test_the_default_bridge_sends_float_zero_temperature_to_gpt41_mini() -> None:
    mock = MockProvider("openai").enqueue_text("[]")
    sink = MemorySink()
    reply = LlmChatBridge(real_client(mock, sink), tags=TAGS).invoke(detect_call())
    assert reply.content == "[]"
    (sent,) = mock.calls
    assert sent.api_model_id == "gpt-4.1-mini"
    assert (sent.temperature, type(sent.temperature), str(sent.temperature)) == (0.0, float, "0.0")
    # 기록 본문에 "temperature" 열쇠가 생긴다(값을 준 호출만 — LT1)
    (record,) = sink.records
    assert record.body is not None
    assert record.body.request["temperature"] == 0.0


@pytest.mark.parametrize("route", ["light-openai", "light-anthropic", "light"])
def test_a_route_with_a_model_that_refuses_temperature_fails_before_the_provider(route: str) -> None:
    mock = MockProvider("openai").enqueue_text("부르면 안 된다")
    sink = MemorySink()
    used = LlmChatBridge(real_client(mock, sink), route=route, tags=TAGS)
    with pytest.raises(LlmConfigError, match="temperature"):
        used.invoke(detect_call())
    assert mock.calls == []
    assert mock.pending == 1


# ── AS2b 3-4-1 판의 모델 설정으로 바꿔 끼운 다리 ──


def sent_by(bridge: LlmChatBridge, mock: MockProvider) -> tuple[str, float | None, int]:
    mock.enqueue_text("[]")
    bridge.invoke(detect_call())
    sent = mock.calls[-1]
    return sent.api_model_id, sent.temperature, sent.max_output_tokens


def test_with_model_sends_the_route_temperature_and_cap() -> None:
    mock = MockProvider("openai")
    base = LlmChatBridge(real_client(mock, MemorySink()), tags=TAGS)
    assert sent_by(base, mock) == ("gpt-4.1-mini", 0.0, 1300)  # 지은 그대로 == AS2b 앞
    assert sent_by(base.with_model("standard-openai-41", 0.7, 2000), mock) == ("gpt-4.1", 0.7, 2000)
    assert sent_by(base.with_model("light-openai-41", None, 1300), mock) == ("gpt-4.1-mini", None, 1300)  # 싣지 않음


def test_with_model_and_with_pack_keep_each_other() -> None:
    mock = MockProvider("openai")
    base = LlmChatBridge(real_client(mock, MemorySink()), tags=TAGS)
    pack = default_prompts(PROMPT_VERSION)
    model_then_pack = base.with_model("standard-openai-41", 0.7, 2000).with_pack(pack)
    pack_then_model = base.with_pack(pack).with_model("standard-openai-41", 0.7, 2000)
    for bridge in (model_then_pack, pack_then_model):
        assert bridge.pack is pack
        assert (bridge.route, bridge.temperature, bridge.max_output_tokens) == ("standard-openai-41", 0.7, 2000)
        assert sent_by(bridge, mock) == ("gpt-4.1", 0.7, 2000)
