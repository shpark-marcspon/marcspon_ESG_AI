"""다리의 TR2 몫: 자리별 봉투 판(MARC-ISSUE-213 — 쪽 system 일곱 자리는 캐시 표시), dry-run 이 설정 오류를 삼키지 않음
(MARC-ISSUE-196 의 2 — 공급사 호출 전), 계획과 다리의 파트가 어긋나면 거절(N8). 실호출 0 — 공급사는 MockProvider 와
클라이언트 없는 AnthropicProvider·OpenAIProvider(요청 몸만 짓는다). 경로는 셋 다 openai 다(MARC-ENT-402) — anthropic
몸 시험은 봉투의 캐시 표시가 그 공급사로 가면 cache_control 이 되는지를 남겨 둔 것이다."""

import json
from typing import cast

import pytest

from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.errors import LlmConfigError, PromptError
from esgapi.core.llm.prompts import PackagePromptStore, PromptRef, PromptTemplate, format_prompt_id
from esgapi.core.llm.providers.anthropic import AnthropicProvider
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Tags
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.plan import CallPlan, PlannedCall, plan
from esgapi.translation.tests.engines.colab_158.support import client, make_input, ok
from esgapi.translation.tools.llm_bridge import (
    PROMPT_VERSIONS,
    TRANSLATE_ROUTE,
    CallModel,
    LlmBridge,
    TranslationModels,
    prompt_ids,
    route_for,
)

CACHED = {"cell", "table-batch", "section", "polish", "editorial-qa", "glossary-repair", "korean-repair"}
SIMPLE = "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다."


def one_call(site: prompts.Site, max_tokens: int = 1024, part: str = "general") -> CallPlan:
    role = "review" if site == "review" else "translate"
    return CallPlan(part=part, calls=[PlannedCall(site, role, "가상 system", "가상 user", max_tokens, 1, 1, "single")])


@pytest.mark.parametrize("site", prompts.SITES)
def test_the_mock_receives_the_cache_mark_only_on_the_seven_sites(site: prompts.Site) -> None:
    anthropic, openai = MockProvider("anthropic"), MockProvider("openai")
    openai.enqueue(ok("x"))
    role = "review" if site == "review" else "translate"
    LlmBridge(client({"anthropic": anthropic, "openai": openai}), part="general", tenant="t").complete(
        site, role, "가상 system", "가상 user", 1024
    )
    (sent,) = openai.calls
    assert [segment.cache for segment in sent.system] == [site in CACHED]


@pytest.mark.parametrize("site", prompts.SITES)
def test_the_anthropic_body_carries_cache_control_only_on_the_seven_sites(site: prompts.Site) -> None:
    """★B: 클라이언트 없는 AnthropicProvider 의 `build_request` 를 dry-run 이 부른다 — 공급사 호출 0."""
    c = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"anthropic": AnthropicProvider(None), "openai": MockProvider("openai")},
        prompts=PackagePromptStore(),
        log=MemorySink(),
        provider_retry={},
    )
    role = "review" if site == "review" else "translate"
    report = c.dry_run(
        CallRequest[str](
            prompt=f"translation/{site}@{PROMPT_VERSIONS[site]}",
            route="light-anthropic",
            tags=Tags(tenant="t", module="translation"),
            vars={"system": "가상 system", "user": "가상 user"},
            max_output_tokens=1024 if role == "translate" else 4096,
            temperature=None,
        )
    )
    system = cast("list[dict[str, object]]", cast("dict[str, object]", report.request)["system"])
    assert [("cache_control" in block) for block in system] == [site in CACHED]


@pytest.mark.parametrize("site", prompts.SITES)
def test_the_openai_body_carries_the_system_text_whether_marked_or_not(site: prompts.Site) -> None:
    """★(2-3b): 캐시 표시는 openai 경로에서 무해하다 — 클라이언트 없는 OpenAIProvider 의 요청 몸에 system 글이 그대로
    실리고 캐시 칸은 없다(공급사 호출 0)."""
    c = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"anthropic": MockProvider("anthropic"), "openai": OpenAIProvider(None)},
        prompts=PackagePromptStore(),
        log=MemorySink(),
        provider_retry={},
    )
    role = "review" if site == "review" else "translate"
    report = c.dry_run(
        CallRequest[str](
            prompt=f"translation/{site}@{PROMPT_VERSIONS[site]}",
            route=route_for(role, "general"),
            tags=Tags(tenant="t", module="translation"),
            vars={"system": "가상 system", "user": "가상 user"},
            max_output_tokens=1024 if role == "translate" else 4096,
            temperature=None,
        )
    )
    body = json.dumps(report.request, ensure_ascii=False)
    assert "가상 system" in body
    assert "cache_control" not in body


def test_the_run_settings_name_every_site_with_its_version() -> None:
    assert prompt_ids() == [f"translation/{site}@{PROMPT_VERSIONS[site]}" for site in prompts.SITES]


def test_a_missing_provider_is_a_config_error_before_any_call() -> None:
    anthropic = MockProvider("anthropic")
    bridge = LlmBridge(client({"anthropic": anthropic}), part="general", tenant="t")
    with pytest.raises(LlmConfigError):
        bridge.dry_run(plan(make_input(SIMPLE)))
    assert anthropic.calls == []


def test_an_output_cap_over_the_model_limit_is_a_config_error() -> None:
    """출력 상한은 min(자리 값, 칸 위끝)(TR4 R4) — 모델 상한을 넘는 것은 칸 위끝 쪽이다."""
    anthropic = MockProvider("anthropic")
    huge = CallModel(TRANSLATE_ROUTE, 10**7)
    bridge = LlmBridge(
        client({"anthropic": anthropic, "openai": MockProvider("openai")}),
        part="general",
        tenant="t",
        models=TranslationModels(huge, huge, huge),
    )
    with pytest.raises(LlmConfigError):
        bridge.dry_run(one_call("section", max_tokens=10**7))
    assert anthropic.calls == []


class _Without:
    """패키지 봉투 중 하나만 없는 저장소(봉투 빠짐 = 배포 결함). 빠진 것은 패키지 저장소와 같은 PromptError."""

    def __init__(self, missing: str) -> None:
        self.inner = PackagePromptStore()
        self.missing = missing

    def get(self, ref: PromptRef) -> PromptTemplate:
        if format_prompt_id(ref) == self.missing:
            raise PromptError(f"프롬프트가 없다: {self.missing}")
        return self.inner.get(ref)


def test_a_missing_envelope_is_a_prompt_error_before_any_call() -> None:
    anthropic = MockProvider("anthropic")
    c = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"anthropic": anthropic, "openai": MockProvider("openai")},
        prompts=_Without("translation/section@2"),
        log=MemorySink(),
        provider_retry={},
    )
    with pytest.raises(PromptError):
        LlmBridge(c, part="general", tenant="t").dry_run(plan(make_input(SIMPLE)))
    assert anthropic.calls == []


def test_a_plan_of_another_part_is_refused() -> None:
    """N8: 경로가 파트에 달린다 — general 계획을 ceo_message 다리로 어림하면 위끝이 틀린다."""
    bridge = LlmBridge(client({"anthropic": MockProvider("anthropic")}), part="ceo_message", tenant="t")
    with pytest.raises(ValueError, match="파트"):
        bridge.dry_run(plan(make_input(SIMPLE)))
