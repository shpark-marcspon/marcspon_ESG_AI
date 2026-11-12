"""다리(tools/llm_bridge.py): 자리 → 프롬프트 id, 역할·파트 → 경로(처분 ⑨ 의 자리 · 모델 MARC-ENT-402), 갈래(개정 1
B4), temperature 안 실음. 실제 설정(models.json) + 모의 공급사 둘(개정 1 B3). 실호출 0."""

import pytest

from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import ProviderError, SystemSegment, TextPart
from esgapi.translation.engines.colab_158.plan import CallPlan, PlannedCall
from esgapi.translation.engines.colab_158.ports import LlmCallFailed
from esgapi.translation.tests.engines.colab_158.support import (
    LIGHT_MODEL,
    STANDARD_MODEL,
    client,
    cut,
    fail,
    ok,
    refuse,
)
from esgapi.translation.tools import llm_bridge
from esgapi.translation.tools.llm_bridge import LlmBridge, prompt_id, route_for


def bridge(part: str = "general") -> tuple[LlmBridge, MockProvider, MockProvider]:
    anthropic, openai = MockProvider("anthropic"), MockProvider("openai")
    return LlmBridge(client({"anthropic": anthropic, "openai": openai}), part=part, tenant="t"), anthropic, openai


def real_config() -> LlmConfig:
    return load_config(default_config_sources(synthetic=False))


def test_routes_by_role_and_part() -> None:
    """R/2110-2116 의 자리(CEO 면 standard, 아니면 light)·R/5326(검수는 light 고정 — W3)·R/6366(자동수정 = 번역
    모델). 모델은 MARC-ENT-402 — CEO gpt-4.1, 그 밖 gpt-4.1-mini."""
    assert [
        route_for(role, part) for role in ("translate", "review") for part in ("ceo_message", "story", "general")
    ] == [
        "standard-openai-41",
        "light-openai-41",
        "light-openai-41",
        "light-openai-41",
        "light-openai-41",
        "light-openai-41",
    ]
    assert prompt_id("table-batch") == "translation/table-batch@2"
    assert prompt_id("review") == "translation/review@1"


def test_the_routes_hold_one_openai_model_each_in_the_real_config() -> None:
    """경로마다 모델 하나 — 대체 모델이 없다(LlmClient.dry_run 이 첫 모델만 재도 위끝이다)."""
    config = real_config()
    assert config.routes[llm_bridge.TRANSLATE_ROUTE] == ("gpt-4.1-mini",)
    assert config.routes[llm_bridge.REVIEW_ROUTE] == ("gpt-4.1-mini",)
    assert config.routes[llm_bridge.CEO_TRANSLATE_ROUTE] == ("gpt-4.1",)
    assert config.models["gpt-4.1-mini"].entry.api_model_id == LIGHT_MODEL
    assert config.models["gpt-4.1"].entry.api_model_id == STANDARD_MODEL
    assert {config.models[m].entry.provider for m in ("gpt-4.1-mini", "gpt-4.1")} == {"openai"}


def test_a_completed_answer_is_sent_and_returned_unstripped() -> None:
    """★ 캐시 표시(@2 봉투)는 openai 요청에도 SystemSegment(cache=True) 로 실린다 — openai 공급사는 system 조각을
    이어 붙이고 표시를 쓰지 않는다(core/llm/providers/openai.py)."""
    b, anthropic, openai = bridge()
    openai.enqueue(ok("  답 글\n"))
    reply = b.complete("section", "translate", "\nSYS\n", "\nUSER\n", 4096)
    assert (reply.text, reply.ending) == ("  답 글\n", "complete")
    (sent,) = openai.calls
    assert sent.api_model_id == LIGHT_MODEL
    assert sent.max_output_tokens == 4096
    assert sent.temperature is None
    assert sent.system == (SystemSegment(text="\nSYS\n", cache=True),)
    assert sent.user == (TextPart(text="\nUSER\n"),)
    assert anthropic.calls == []


def test_ceo_translation_goes_to_the_standard_model_and_review_to_the_light_one() -> None:
    b, anthropic, openai = bridge("ceo_message")
    openai.enqueue(ok("x")).enqueue(ok("[]"))
    b.complete("section", "translate", "s", "u", 4096)
    b.complete("review", "review", "s", "u", 4096)
    assert [c.api_model_id for c in openai.calls] == [STANDARD_MODEL, LIGHT_MODEL]
    assert anthropic.calls == []


def test_truncated_and_refused_come_back_as_text() -> None:
    """개정 1 B4: 코랩은 잘림·거절에 예외를 내지 않고 그 글로 계속한다."""
    b, _, openai = bridge()
    openai.enqueue(cut('{"items": [')).enqueue(refuse("I can't help with that."))
    first = b.complete("table-batch", "translate", "s", "u", 8192)
    second = b.complete("section", "translate", "s", "u", 4096)
    assert (first.text, first.ending) == ('{"items": [', "truncated")
    assert (second.text, second.ending) == ("I can't help with that.", "refused")


def test_a_provider_failure_raises_the_port_exception() -> None:
    b, _, openai = bridge()
    openai.enqueue(fail())
    with pytest.raises(LlmCallFailed, match=r"^section: provider_error$"):
        b.complete("section", "translate", "s", "u", 4096)


def test_a_retryable_failure_on_the_standard_route_has_no_fallback() -> None:
    """경로 standard-openai-41 은 모델이 하나라 다시 해 볼 만한 실패도 대체 모델로 넘어가지 않는다(재시도 0 —
    provider_retry={}). 다른 공급사 호출 0."""
    b, anthropic, openai = bridge("ceo_message")
    openai.enqueue(ProviderError(status=503, retryable=True, message="가상 과부하"))
    with pytest.raises(LlmCallFailed, match=r"^section: provider_error$"):
        b.complete("section", "translate", "s", "u", 4096)
    assert [c.api_model_id for c in openai.calls] == [STANDARD_MODEL]
    assert anthropic.calls == []


def test_the_call_is_tagged_with_the_module() -> None:
    anthropic, openai = MockProvider("anthropic"), MockProvider("openai")
    sink = MemorySink()
    c = client({"anthropic": anthropic, "openai": openai}, log=sink)
    openai.enqueue(ok("x"))
    LlmBridge(c, part="general", tenant="tenant-a").complete("cell", "translate", "s", "u", 1024)
    (record,) = sink.records
    assert (record.tenant, record.module, record.prompt_id) == ("tenant-a", "translation", "translation/cell@2")


# ── dry-run(발주서 §3 S5 · 개정 2 M3) ──


def hand_plan(part: str = "general") -> CallPlan:
    """손으로 짠 계획: 영문 system 399자 + 줄바꿈 + 영문 user 400자 = 800자 → 200토큰(4자 = 1토큰, models.json
    tokenEstimate) × 3번, 영문 99자 + 줄바꿈 + 국문 100자 → 25 + 100 = 125토큰(cjkCharsPerToken 1) × 1번."""
    return CallPlan(
        part=part,
        calls=[
            PlannedCall("section", "translate", "a" * 399, "b" * 400, 4096, 3, 1, "single"),
            PlannedCall("review", "review", "a" * 99, "가" * 100, 4096, 1, 1, "single"),
        ],
        assumptions=["계획의 가정"],
        unestimated=[],
    )


def usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """models.json 단가(백만 토큰당 USD)로 손셈 — 단가는 손으로 박지 않는다(MARC-ENT-402)."""
    pricing = real_config().models[model].entry.pricing
    return (input_tokens * pricing.input + output_tokens * pricing.output) / 1e6


def test_dry_run_is_the_hand_count_and_calls_no_provider() -> None:
    """손셈: general = 번역 gpt-4.1-mini 3 × (200 입력 + 4096 출력) + 검수 gpt-4.1-mini (125 + 4096).
    ceo_message = 번역 gpt-4.1 3 × (200 + 4096) + 검수 gpt-4.1-mini (125 + 4096)."""
    b, anthropic, openai = bridge()
    report = b.dry_run(hand_plan())
    section, review = 3 * usd("gpt-4.1-mini", 200, 4096), usd("gpt-4.1-mini", 125, 4096)
    assert report["perSite"] == {
        "section": {"calls": 3, "estimateUsd": pytest.approx(section)},
        "review": {"calls": 1, "estimateUsd": pytest.approx(review)},
    }
    assert report["totalEstimateUsd"] == pytest.approx(section + review)
    ceo, ceo_anthropic, ceo_openai = bridge("ceo_message")
    ceo_total = ceo.dry_run(hand_plan("ceo_message"))["totalEstimateUsd"]
    assert ceo_total == pytest.approx(3 * usd("gpt-4.1", 200, 4096) + review)
    assert anthropic.calls == [] and openai.calls == []
    assert ceo_anthropic.calls == [] and ceo_openai.calls == []


def test_dry_run_states_the_assumptions_of_the_order() -> None:
    report = bridge()[0].dry_run(hand_plan())
    assumptions = report["assumptions"]
    assert isinstance(assumptions, list)
    assert assumptions[0] == "계획의 가정"
    assert "시도 하나 기준(재시도·대체 제외)" in assumptions
    assert any(str(a).startswith("cjkCharsPerToken = 1") and "출처 없는 가정" in str(a) for a in assumptions)
    assert any("모델이 하나뿐" in str(a) for a in assumptions)
    assert set(report) == {"perSite", "totalEstimateUsd", "assumptions", "unestimated", "warnings"}


def test_dry_run_of_a_real_plan_sums_each_planned_request() -> None:
    """지어낸 3쪽 문서(CEO): 합 = Σ(계획의 요청마다 `LlmClient.dry_run` 값 × 횟수). 두 모의 공급사 호출 0."""
    from esgapi.core.llm.client import CallRequest
    from esgapi.translation.engines.colab_158.plan import plan
    from esgapi.translation.tests.engines.colab_158.support import make_input
    from esgapi.translation.tests.engines.colab_158.test_plan import GLOSSARY, THREE_PAGES

    b, anthropic, openai = bridge("ceo_message")
    p = plan(make_input(THREE_PAGES, base=GLOSSARY, part="ceo_message"))
    expected = 0.0
    for call in p.calls:
        request = CallRequest[str](
            prompt=prompt_id(call.site),
            route=route_for(call.role, "ceo_message"),
            tags=b.tags,
            vars={"system": call.system, "user": call.user},
            max_output_tokens=call.max_tokens,
            temperature=None,
        )
        expected += b.client.dry_run(request).estimate.cost_upper_bound_usd * call.count
    report = b.dry_run(p)
    assert report["totalEstimateUsd"] == pytest.approx(expected)
    per_site = report["perSite"]
    assert isinstance(per_site, dict)
    assert sum(v["calls"] for v in per_site.values()) == 51
    assert anthropic.calls == [] and openai.calls == []
