# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""금액 바닥 안전(밴드 TRE1 S1·S4·S5, 순수): 어떤 입력에서도 이 실행의 실비 ≤ prepare 위끝(`totalEstimateUsd`).
위끝은 자리별 실측 비율로 낮춘 어림이라(tools/run_bound.py) 이것을 지키는 것은 실행 중 상한 min(max_usd, 위끝)과
호출 일지의 호출 전 판정이다(tools/call_journal.py 머리말 (d)). 실호출 0 — 모의 공급사뿐, 글은 지어낸 것."""

import json
import logging
from dataclasses import replace
from typing import Any, cast

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import StepContext
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.errors import PromptError
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.retry import DEFAULT_PROVIDER_RETRY
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, ProviderError, ProviderRequest, ProviderResponse, Usage
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.ports import LlmCallFailed
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.tests.flows.support import FakeStore, binding, default_versions, document, options
from esgapi.translation.tests.flows.test_colab_158 import found
from esgapi.translation.tests.tools.budget_support import worst
from esgapi.translation.tests.tools.test_call_journal import FACTOR, NO_USAGE, Events, Provider
from esgapi.translation.tools import call_journal, llm_bridge

KO = "가상기업은 지속가능한 경영을 위해 위험과 기회를 점검하고 이해관계자와 소통합니다. "
EN = "The virtual company reviews its risks and opportunities every year. "
CHEAP = Usage(input_tokens=10, output_tokens=10, cache_read_tokens=0, cache_write_tokens=0)


def pages(count: int, body: str = KO, chars: int = 400, table_rows: int = 0) -> str:
    out: list[str] = []
    for n in range(1, count + 1):
        out.append(f"[PAGE {n}]\n[BLOCK 1]\n가상 {n}쪽 제목\n" + (body * 40)[: chars + n])
        if table_rows:
            rows = "".join(f"| 가상 항목 {n}-{r} | {r * 7} |\n" for r in range(table_rows))
            out.append(f"[TABLE 1]\n| 구분 | 가상 값 |\n|---|---|\n{rows}")
    return "\n".join(out)


AB = {"compareAb": True, "single": "B"}
CASES: dict[str, tuple[str, dict[str, Any]]] = {
    "one_page": ("[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다.", options(autofix=False)),
    "ten_pages_korean": (pages(10), options(autofix=False)),
    "tables": (pages(3, chars=60, table_rows=12), options(autofix=False)),
    "english_only": (pages(3, body=EN), options(autofix=False)),
    "ceo_message": (pages(2), options(part="ceo_message", autofix=False)),
    "ab_autofix": (pages(4), options(style=AB, autofix=True)),
    "glossary": (pages(3), options(glossary={"final": [{"ko": "가상기업", "en": "Virtual Corp"}]}, autofix=True)),
    "retry": (pages(3), options(retry={"fromRunId": 7, "pages": [1, 2]}, autofix=True)),
}
"""S1 의 지어낸 입력(발주서 §3 S1 의 여덟)."""


def worst_text(request: ProviderRequest) -> ProviderResponse:
    """검수는 늘 이슈(자동수정이 돎), 표 묶음은 JSON 을 깸(칸 대체), 그 밖은 영문 + 국문 한 줄(한국어 보정이 돎)."""
    system = "".join(s.text for s in request.system)
    user = "".join(getattr(p, "text", "") for p in request.user)
    if system == prompts.QA_SYSTEM_PROMPT:
        issue = {"issue_type": "GRAMMAR", "severity": "HIGH", "page_num": 1, "original_span": "virtual"}
        return Completed(text=json.dumps([{**issue, "suggestion": "Virtual", "reason": "가상"}]), usage=CHEAP)
    if '"items"' in user:
        return Completed(text="not json", usage=CHEAP)
    return Completed(text="[BLOCK 1]\nVirtual Title\n" + EN * 3 + "\n남은 가상 문장", usage=CHEAP)


def cheap(request: ProviderRequest) -> ProviderResponse:
    if "".join(s.text for s in request.system) == prompts.QA_SYSTEM_PROMPT:
        return Completed(text="[]", usage=CHEAP)
    return Completed(text="[BLOCK 1]\nVirtual Title\nVirtual body.", usage=CHEAP)


PROVIDERS: dict[str, Any] = {"worst": worst(worst_text), "no_usage": NO_USAGE, "cheap": cheap}


def flow_inputs(case: str, max_usd: float) -> colab.TranslationRunInputs:
    text, given = CASES[case]
    store = FakeStore({(1, 7): found(text)}) if "retry" in given else None
    versions = default_versions() if "retry" in given else {}
    return binding(store, max_usd).inputs_with(document(text), given, company_id=1, versions=versions)


def bound_of(case: str, reply: Any) -> float:
    inputs = flow_inputs(case, 1e9)
    adapters = colab.TranslationAdapters(llm=Provider(reply).client(), tenant="1", mock=False, spent_usd=lambda: 0.0)
    step = colab.prepare(inputs, adapters, {}, StepContext(resume=None))
    assert step.data["rejection"] is None
    return cast("float", step.data["totalEstimateUsd"])


def run_case(case: str, reply: Any) -> tuple[str, float, float, list[dict[str, Any]]]:
    """→ (결과 status 또는 거절 종류, Σ 실비(장부), 위끝, 실제 호출 일지 칸)."""
    total = bound_of(case, reply)
    log = MemorySink()
    events = Events()
    adapters = colab.TranslationAdapters(llm=Provider(reply).client(log), tenant="1", mock=False, spent_usd=lambda: 0.0)
    run = run_flow(colab.FLOW, flow_inputs(case, total * 10), adapters, events=events)
    result = cast("dict[str, Any]", run.output.results[0])
    state = result["status"] if result["status"] == "done" else result["rejection"]["kind"]
    journal = cast("list[dict[str, Any]]", events.partials[-1]["journal"]) if events.partials else []
    return state, sum(r.cost_usd or 0 for r in log.records), total, journal


@pytest.fixture(autouse=True)
def every_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(call_journal, "CHECKPOINT_EVERY_S", 0.0)


# ── S1 바닥 안전 ──


@pytest.mark.parametrize("case", list(CASES))
def test_s1_the_worst_provider_never_spends_over_the_estimate(case: str) -> None:
    """출력 상한을 다 쓰고 입력이 어림의 2배인 공급사(실비 ≤ 머리 여유) — done 이든 over_budget 이든 Σ 실비 ≤ 위끝.
    max_usd = 위끝 × 10 이라 min 을 지우면(P1) 실행 중 상한이 커져 위끝을 넘는다."""
    state, spent, total, journal = run_case(case, PROVIDERS["worst"])
    assert state in ("done", "over_budget")
    assert journal  # 분모: 실제로 공급사를 불렀다
    assert spent <= total


@pytest.mark.parametrize("case", list(CASES))
def test_s1_failures_without_usage_are_charged_within_the_estimate(case: str) -> None:
    """사용량 없는 실패만(실비 모름 — 호출마다 엄격 위끝만큼 깎임): Σ 엄격 위끝(부른 호출) ≤ 위끝."""
    state, _, total, journal = run_case(case, PROVIDERS["no_usage"])
    assert state in ("done", "over_budget")
    assert journal and not any(e["ok"] for e in journal)
    assert sum(e["boundUsd"] for e in journal) <= total


@pytest.mark.parametrize("case", list(CASES))
def test_s1_a_cheap_provider_runs_to_done(case: str) -> None:
    state, spent, total, _ = run_case(case, PROVIDERS["cheap"])
    assert state == "done" and spent <= total


# ── S4 작은 문서 ──


def test_s4_a_tiny_plan_is_done_at_a_cap_equal_to_the_estimate() -> None:
    """짧은 영문 1쪽(계획 3호출 — 윤문·범용 QA·검수)에서 max_usd = 새 위끝이면 done. 마지막 호출 여유 항이 없으면
    상한(= Σ ρ × 어림, 호출 하나 위끝 남짓)이 첫 호출의 머리 여유(위끝 × 2)보다 작아 over_budget(P6)."""
    CASES["tiny"] = ("[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual body text.", options(autofix=False))
    try:
        total = bound_of("tiny", cheap)
        provider = Provider(cheap)
        adapters = colab.TranslationAdapters(llm=provider.client(), tenant="1", mock=False, spent_usd=lambda: 0.0)
        run = run_flow(colab.FLOW, flow_inputs("tiny", total), adapters)
    finally:
        del CASES["tiny"]
    assert run.output.results[0]["status"] == "done"
    assert len(provider.mock.calls) == 1  # 계획(위끝)은 셋이지만 짧은 영문은 검수 하나만 실제로 돈다


# ── S5 되돌림 (일지 하나를 바로 부른다) ──

SYSTEM, USER = "가상 체계 글", "가상 사용자 글 " * 20


def gateway(reply: Any, allowance: float) -> tuple[call_journal.JournalGateway, llm_bridge.LlmBridge, Provider]:
    provider = Provider(reply)
    bridge = llm_bridge.LlmBridge(provider.client(), part="general", tenant="1")
    journal = call_journal.JournalGateway(
        bridge,
        resume=call_journal.EMPTY,
        source_sha256="0" * 64,
        calls=100,
        checkpoint=lambda *_a, **_k: None,
        allowance_usd=allowance,
    )
    return journal, bridge, provider


def bound(bridge: llm_bridge.LlmBridge) -> float:
    return bridge.bound_usd("section", "translate", SYSTEM, USER, 512)


def call(journal: call_journal.JournalGateway) -> Any:
    return call_journal.unescaped(lambda: journal.complete("section", "translate", SYSTEM, USER, 512))


def test_s5_the_allowance_gets_the_unused_guard_back() -> None:
    """허용액 = 머리 여유 하나 + ε(열 호출의 실비) 인데 싼 공급사로 열 호출이 다 돈다(되돌림이 없으면 둘째에서
    over_budget — P2)."""
    _, bridge, _ = gateway(cheap, 0.0)
    b = bound(bridge)
    epsilon = 10 * (10 * 0.4e-6 + 10 * 1.6e-6) + 1e-12  # 열 호출의 실비(CHEAP · gpt-4.1-mini 단가)
    assert epsilon < FACTOR * b  # 분모: 되돌림이 없으면 둘째 호출의 머리 여유가 들지 않는다
    journal, _, provider = gateway(cheap, FACTOR * b + epsilon)
    for _ in range(10):
        call(journal)
    assert len(provider.mock.calls) == 10


def test_s5_a_cost_over_the_guard_logs_one_line_without_values(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)

    def dear(request: ProviderRequest) -> ProviderResponse:
        usage = Usage(
            input_tokens=5_000_000, output_tokens=request.max_output_tokens, cache_read_tokens=0, cache_write_tokens=0
        )
        return Completed(text="Virtual.", usage=usage)

    journal, bridge, _ = gateway(dear, 1_000.0)
    call(journal)
    lines = [r.getMessage() for r in caplog.records if "translation_bound_exceeded" in r.getMessage()]
    assert lines == ["translation_bound_exceeded done=0"]  # 값·키·글 0
    assert journal.allowance_usd < 1_000.0 - FACTOR * bound(bridge)  # 실비로 뺀다


def test_s5_failures_without_usage_take_exactly_the_strict_bound_each() -> None:
    """사용량 없는 실패: n 호출 뒤 허용액이 정확히 n × 엄격 위끝만큼 줄고, 허용액이 머리 여유(F·b) 아래가 되는
    자리에서 over_budget(모름을 0 으로 보면 끝없이 돈다 — P8)."""
    _, bridge, _ = gateway(NO_USAGE, 0.0)
    b = bound(bridge)
    start = 5 * b + 1e-9
    journal, _, provider = gateway(NO_USAGE, start)
    assert FACTOR == 3.0  # 분모: openai 기본 재시도 2(D2)
    for n in range(1, 4):  # 허용액 5b·4b·3b(+ε) 에서 부름
        with pytest.raises(LlmCallFailed):
            call(journal)
        assert journal.allowance_usd == pytest.approx(start - n * b, abs=1e-12)
    with pytest.raises(call_journal.OverBudget):  # 남은 2b + ε < 머리 여유 3b
        call(journal)
    assert len(provider.mock.calls) == 3


def test_s5_a_bridge_exception_keeps_the_whole_guard_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    """다리가 결과 없이 던지면(PromptError) 그 호출의 머리 여유는 되돌리지 않는다. 앞 호출의 실비가 다음 호출에 남지
    않는다(앎 → 예외 차례 — 다리 머리의 지움을 빼면 앞 실비로 되돌린다, P9)."""
    journal, bridge, _ = gateway(cheap, 1.0)
    b = bound(bridge)
    call(journal)
    after_first = journal.allowance_usd
    assert bridge.last_cost_usd is not None and bridge.last_cost_usd > 0

    def broken(_request: Any) -> Any:
        raise PromptError("가짜 봉투 오류")

    monkeypatch.setattr(bridge.client, "call", broken)
    with pytest.raises(PromptError):
        call(journal)
    assert bridge.last_cost_usd is None
    assert journal.allowance_usd == pytest.approx(after_first - FACTOR * b, abs=1e-12)


# ── ② TRL2 꼴 공급사 · 재시도로 모름 시도가 여럿(감독 결정 D1) ──

TRL2_USAGE: dict[str, tuple[int, int, int]] = {
    "section": (2_953, 1_227, 388),
    "polish": (3_582, 1_240, 411),
    "review": (3_758, 0, 86),
    "autofix": (3_513, 0, 1_186),
    "editorial-qa": (3_012, 2_944, 1_142),
}
"""TRL2 호출 표(MARC-TICK-382, 서버 장부 run 11)의 자리별 한 호출 평균 토큰(입력·캐시 읽기·출력). 숫자만."""


def three_column_pages(count: int = 6) -> str:
    """지어낸 3단 꼴 쪽(쪽마다 블록 셋·단락 9~20·글자 약 2,700)."""
    out: list[str] = []
    for n in range(1, count + 1):
        paras = 9 + (n * 5) % 12
        body = "\n".join((KO * 3)[: 2_700 // paras + n] for _ in range(paras))
        third = len(body) // 3
        blocks = [body[:third], body[third : 2 * third], body[2 * third :]]
        out.append(f"[PAGE {n}]\n" + "\n".join(f"[BLOCK {b}]\n{t}" for b, t in enumerate(blocks, 1)))
    return "\n".join(out)


def test_s1_a_trl2_shaped_provider_is_done_well_under_the_old_ceiling(monkeypatch: pytest.MonkeyPatch) -> None:
    """자리별 사용량을 TRL2 실측으로 심은 공급사·지어낸 6쪽(A/B·자동수정): done · Σ 실비 ≤ 위끝 ≤ 옛 엄격 합 × 0.3
    (live B 로 셈한 ρ 에서 약 0.27 — 발주서의 0.25 는 mock 단가 B 의 어림, 보고 ★①). ρ 표를 실측 아래로 낮추면
    위끝 < 실비(P5)."""
    current: list[str] = ["section"]
    real = llm_bridge.LlmBridge.complete

    def noting(self: llm_bridge.LlmBridge, site: Any, *args: Any) -> Any:
        current[0] = site
        return real(self, site, *args)

    monkeypatch.setattr(llm_bridge.LlmBridge, "complete", noting)

    def shaped(request: ProviderRequest) -> ProviderResponse:
        plain, cached, output = TRL2_USAGE.get(current[0], TRL2_USAGE["section"])
        usage = Usage(input_tokens=plain, output_tokens=output, cache_read_tokens=cached, cache_write_tokens=0)
        return replace(cheap(request), usage=usage)  # type: ignore[type-var]

    CASES["trl2_shaped"] = (three_column_pages(), options(style=AB, autofix=True))
    try:
        state, spent, total, journal = run_case("trl2_shaped", shaped)
        step = colab.prepare(
            flow_inputs("trl2_shaped", 1e9),
            colab.TranslationAdapters(llm=Provider(shaped).client(), tenant="1", mock=False, spent_usd=lambda: 0.0),
            {},
            StepContext(resume=None),
        )
    finally:
        del CASES["trl2_shaped"]
    assert state == "done" and journal
    assert spent <= total <= cast("float", step.data["ceilingUsd"]) * 0.3


def test_s5_provider_retries_of_unknown_cost_are_each_charged_the_strict_bound() -> None:
    """기본 재시도(openai 2회)로 나간 뒤 상태 없는 끊김이 둘 이어지고 셋째에 성공: 한 호출에 모름 시도 둘 → 깎인 몫 =
    아는 실비 + 2 × 엄격 위끝(감독 결정 D1 — 모름을 한 번만 세면 빨강, P10)."""
    _, bridge, _ = gateway(cheap, 0.0)
    b = bound(bridge)
    cut = ProviderError(status=None, retryable=True, message="모의 끊김", sent=True)
    client, mock = retry_client([cut, cut, cheap])
    retried = llm_bridge.LlmBridge(client, part="general", tenant="1")
    journal = call_journal.JournalGateway(
        retried,
        resume=call_journal.EMPTY,
        source_sha256="0" * 64,
        calls=1,
        checkpoint=lambda *_a, **_k: None,
        allowance_usd=1.0,
    )
    call(journal)
    assert len(mock.calls) == 3 and retried.last_unknown_attempts == 2
    known = cast("float", retried.last_cost_usd)
    assert known > 0
    assert journal.allowance_usd == pytest.approx(1.0 - known - 2 * b, abs=1e-12)


def retry_client(replies: list[Any]) -> tuple[LlmClient, MockProvider]:
    """운영 client 와 같은 기본 재시도(DEFAULT_PROVIDER_RETRY — openai 2회)의 클라이언트, 기다림 0."""
    mock = MockProvider("openai")
    for reply in replies:
        mock.enqueue(reply)
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"anthropic": MockProvider("anthropic"), "openai": mock},
        prompts=PackagePromptStore(),
        log=MemorySink(),
        provider_retry=DEFAULT_PROVIDER_RETRY,
        sleep=lambda _ms: None,
    )
    return client, mock


@pytest.mark.parametrize("room", [2.5, 3.0])
def test_s5_three_unknown_retries_never_take_more_than_the_allowance(room: float) -> None:
    """기본 재시도로 끊김(sent, status None)이 셋 — 한 호출에 모름 시도 셋 = 3b 깎임. 머리 여유 = max(2, 1 + 재시도
    2) × b = 3b 라 허용액 2.5b 면 부르지 않고(공급사 0), 3b(+ε) 면 불러도 허용액이 0 아래로 가지 않는다(실비(모름 =
    b) 합 ≤ 위끝 — 감독 결정 D2. 배수를 GUARD_FACTOR 로만 두면 2.5b 에서 들여보내 −0.5b — P11)."""
    _, bridge, _ = gateway(cheap, 0.0)
    b = bound(bridge)
    cut = ProviderError(status=None, retryable=True, message="모의 끊김", sent=True)
    client, mock = retry_client([cut, cut, cut])
    journal = call_journal.JournalGateway(
        llm_bridge.LlmBridge(client, part="general", tenant="1"),
        resume=call_journal.EMPTY,
        source_sha256="0" * 64,
        calls=1,
        checkpoint=lambda *_a, **_k: None,
        allowance_usd=room * b + 1e-12,
    )
    if room < FACTOR:
        with pytest.raises(call_journal.OverBudget):
            call(journal)
        assert mock.calls == []
    else:
        with pytest.raises(LlmCallFailed):
            call(journal)
        assert len(mock.calls) == 3
    assert journal.allowance_usd >= 0
