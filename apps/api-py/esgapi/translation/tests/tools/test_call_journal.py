# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""호출 일지 체크포인트(MARC-ISSUE-268 의 1, 밴드 TRR1 T4·T6·T7, 순수): 체크포인트에서 끊고 partial 로 이은 실행이 한
번에 돈 실행과 result@1·Word 가 같고 공급사 호출 합도 같다. 소프트 제한·체크포인트 예외는 엔진에 삼켜지지 않고 단계
밖으로 나간다. 일지 어긋남·부서진 partial·상한 넘침의 갈래. 실호출 0 — 모의 공급사뿐, 문서는 지어낸 것."""

import hashlib
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowRun, FlowStepFailed, StepContext, StepOutput
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.retry import DEFAULT_PROVIDER_RETRY
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, ProviderError, ProviderRequest, ProviderResponse, Usage
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.tests.engines.colab_158.run_digest import _docx_sha  # pyright: ignore[reportPrivateUsage]
from esgapi.translation.tests.flows.support import binding, document, options
from esgapi.translation.tests.tools.budget_support import worst
from esgapi.translation.tools import call_journal, llm_bridge, run_bound

U = Usage(input_tokens=10, output_tokens=10, cache_read_tokens=0, cache_write_tokens=0)
EN = "The virtual company reviews its risks and opportunities. "
PARA = "가상기업은 지속가능한 경영을 위해 위험과 기회를 점검하고 이해관계자와 소통합니다. "


def ten_pages(pages: int = 10) -> str:
    """지어낸 쪽들(쪽마다 글이 달라 요청 열쇠가 겹치지 않는다)."""
    return "\n".join(f"[PAGE {n}]\n[BLOCK 1]\n가상 {n}쪽 제목\n" + (PARA * 5)[: 200 + n] for n in range(1, pages + 1))


def answer(request: ProviderRequest) -> ProviderResponse:
    """요청의 글로만 정해지는 답(차례와 무관 — 끊고 이어도 같은 요청엔 같은 답). 검수는 이슈 하나(자동수정이 돈다)."""
    system = "".join(s.text for s in request.system)
    if system == prompts.QA_SYSTEM_PROMPT:
        issue = {"issue_type": "GRAMMAR", "severity": "LOW", "original_span": "", "suggestion": "x", "reason": "y"}
        return Completed(text=json.dumps([issue]), usage=U)
    user = "".join(getattr(p, "text", "") for p in request.user)
    korean = len(re.findall(r"[가-힣]", user))
    return Completed(text="[BLOCK 1]\n" + (EN * 200)[: max(40, int(korean * 2.5))], usage=U)


def flaky(request: ProviderRequest) -> ProviderResponse:
    """answer 에 실패를 섞는다: 요청 글의 sha 가 3 의 배수면 공급사 오류(차례와 무관)."""
    body = json.dumps(request.to_json(), ensure_ascii=False, sort_keys=True).encode()
    if hashlib.sha256(body).digest()[0] % 3 == 0:
        return ProviderError(status=500, retryable=False, message="모의 실패")
    return answer(request)


@dataclass
class Provider:
    """늘 답하는 모의 openai(심은 답이 떨어지지 않게 부를 때마다 하나씩 더 심는다)."""

    reply: Any
    mock: MockProvider = field(default_factory=lambda: MockProvider("openai"))

    def client(self, log: MemorySink | None = None) -> LlmClient:
        for _ in range(5_000):
            self.mock.enqueue(self.reply)
        return LlmClient(
            config=load_config(default_config_sources(synthetic=False)),
            providers={"anthropic": MockProvider("anthropic"), "openai": self.mock},
            prompts=PackagePromptStore(),
            log=MemorySink() if log is None else log,
            provider_retry={},
            sleep=lambda _ms: None,
        )


GIVEN = options(style={"compareAb": True, "single": "B"}, ceoPageLimit=None, autofix=True)


def inputs(text: str, max_usd: float = 10_000.0) -> colab.TranslationRunInputs:
    return binding(max_usd=max_usd).inputs_with(document(text), GIVEN, company_id=1, versions={})


def adapters(llm: LlmClient, spent: float = 0.0) -> colab.TranslationAdapters:
    return colab.TranslationAdapters(llm=llm, tenant="1", mock=False, spent_usd=lambda: spent)


class Cut(BaseException):
    """사건 쪽이 시도를 접는다(실행기의 RunYield 자리 — BaseException)."""


@dataclass
class Events:
    """k 번째 체크포인트에서 접는 사건 받는 쪽(그 전 partial 을 쥔다)."""

    cut_at: int | None = None
    raise_error: Exception | None = None
    partials: list[dict[str, object]] = field(default_factory=lambda: [])
    progress: list[tuple[int, int]] = field(default_factory=lambda: [])

    def step_started(self, flow_id: str, step: str) -> None: ...
    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None: ...
    def step_failed(self, flow_id: str, step: str, reason: str) -> None: ...

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        self.partials.append(dict(partial))
        self.progress.append((done, total))
        if self.raise_error is not None:
            raise self.raise_error
        if self.cut_at is not None and len(self.partials) == self.cut_at:
            raise Cut


@pytest.fixture
def every_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """체크포인트를 실제 호출마다(간격 0)."""
    monkeypatch.setattr(call_journal, "CHECKPOINT_EVERY_S", 0.0)


def whole(text: str, reply: Any) -> tuple[FlowRun, int]:
    provider = Provider(reply)
    run = run_flow(colab.FLOW, inputs(text), adapters(provider.client()))
    return run, len(provider.mock.calls)


def prepared(text: str, reply: Any, max_usd: float = 10_000.0) -> StepOutput:
    """prepare 단계만(공급사 호출 0 — 다리의 dry_run 뿐)."""
    return colab.prepare(inputs(text, max_usd), adapters(Provider(reply).client()), {}, StepContext(resume=None))


def resumed(
    text: str,
    reply: Any,
    partial: Mapping[str, object] | None,
    *,
    spent: float = 0.0,
    max_usd: float = 10_000.0,
    events: Events | None = None,
) -> tuple[FlowRun, Provider]:
    """앞 partial 로 translate 부터 잇는다(새 클라이언트 — 공급사 호출은 이 시도의 것만 센다)."""
    provider = Provider(reply)
    run = run_flow(
        colab.FLOW,
        inputs(text, max_usd),
        adapters(provider.client(), spent),
        start_at="translate",
        carried={"prepare": prepared(text, reply)},  # prepare 는 지나게 — 상한은 translate 의 판정만 본다
        resume=partial,
        events=events or Events(),
    )
    return run, provider


def cut(text: str, reply: Any, k: int) -> tuple[dict[str, object], int]:
    """처음부터 돌리다 k 번째 체크포인트에서 접는다 → (그 partial, 그때까지 공급사 호출 수)."""
    provider = Provider(reply)
    events = Events(cut_at=k)
    with pytest.raises(Cut):
        run_flow(colab.FLOW, inputs(text), adapters(provider.client()), events=events)
    return events.partials[-1], len(provider.mock.calls)


def word(run: FlowRun) -> dict[str, str]:
    return {f.name: _docx_sha(f.content) for f in run.output.files}


def same_output(a: FlowRun, b: FlowRun) -> None:
    left, right = a.output.results[0], b.output.results[0]
    assert json.dumps(left, ensure_ascii=False, sort_keys=True) == json.dumps(right, ensure_ascii=False, sort_keys=True)
    assert word(a) == word(b)


# ── T4: 재시작 유무 같은 출력 ──


@pytest.mark.parametrize("reply", [answer, flaky], ids=["answers", "with_failures"])
@pytest.mark.parametrize("k", [1, 7, -1], ids=["first", "seventh", "last"])
def test_t4_a_run_cut_at_a_checkpoint_and_resumed_matches_the_whole_run(every_call: None, reply: Any, k: int) -> None:
    text = ten_pages()
    full, full_calls = whole(text, reply)
    k = full_calls - 1 if k == -1 else k
    partial, before = cut(text, reply, k)
    assert partial["done"] == before == k  # 간격 0 — 실제 호출마다 체크포인트
    again, provider = resumed(text, reply, partial)
    same_output(full, again)
    assert before + len(provider.mock.calls) == full_calls  # 되감은 칸은 공급사를 부르지 않는다
    if reply is flaky:
        journal = cast("list[dict[str, object]]", partial["journal"])
        failed_after = [r for r in provider.mock.calls if isinstance(flaky(r), ProviderError)]
        assert any(e["ok"] is False for e in journal) or failed_after  # 분모: 실패 답이 섞였다


def test_t4_the_done_count_runs_on_across_attempts_and_total_is_the_plan(every_call: None) -> None:
    text = ten_pages()
    partial, before = cut(text, answer, 5)
    events = Events()
    provider = Provider(answer)
    run_flow(
        colab.FLOW,
        inputs(text),
        adapters(provider.client()),
        start_at="translate",
        carried={"prepare": prepared(text, answer)},
        resume=partial,
        events=events,
    )
    calls = prepared(text, answer).data["calls"]
    assert events.progress[0] == (before + 1, calls)
    assert [d for d, _ in events.progress] == list(range(before + 1, before + 1 + len(events.progress)))


def test_t4_no_checkpoint_before_the_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """간격(20초)이 지나지 않으면 체크포인트 0 — 결과는 그대로."""
    monkeypatch.setattr(call_journal, "monotonic", lambda: 0.0)
    events = Events()
    run_flow(colab.FLOW, inputs(ten_pages(2)), adapters(Provider(answer).client()), events=events)
    assert events.partials == []


def test_t4_the_checkpoint_comes_after_the_first_call_past_the_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]

    def clock() -> float:
        now[0] += 7.0  # 부를 때마다 7초(시작 0·7·14·21…)
        return now[0]

    monkeypatch.setattr(call_journal, "monotonic", clock)
    events = Events()
    run_flow(colab.FLOW, inputs(ten_pages(2)), adapters(Provider(answer).client()), events=events)
    assert events.progress and events.progress[0][0] == 3  # 7 → 14·21·28: 셋째 호출 끝에 21초 지남


# ── T6: 소프트 제한·체크포인트 예외는 엔진 밖으로 ──


class SoftTimeLimitExceeded(Exception):
    pass


def soft_at(n: int) -> Any:
    seen = [0]

    def reply(request: ProviderRequest) -> ProviderResponse:
        seen[0] += 1
        if seen[0] == n:
            raise SoftTimeLimitExceeded("가짜 소프트 제한")
        return answer(request)

    return reply


@pytest.mark.parametrize("n", [1, 9])
def test_t6_a_soft_limit_inside_a_call_leaves_the_step_instead_of_a_page_error(n: int) -> None:
    provider = Provider(soft_at(n))
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(colab.FLOW, inputs(ten_pages()), adapters(provider.client()))
    assert caught.value.step == "translate"
    assert isinstance(caught.value.__cause__, SoftTimeLimitExceeded)
    assert len(provider.mock.calls) == n  # 그 뒤 공급사 호출 0


def test_t6_an_exception_from_the_checkpoint_stops_the_calls(every_call: None) -> None:
    provider = Provider(answer)
    events = Events(raise_error=RuntimeError("사건 쪽 쓰기 실패"))
    with pytest.raises(RuntimeError):
        run_flow(colab.FLOW, inputs(ten_pages()), adapters(provider.client()), events=events)
    assert len(provider.mock.calls) == 1 and len(events.partials) == 1


def test_t6_a_round_trip_failure_of_the_partial_fails_the_step(
    every_call: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """체크포인트의 왕복 실패(FlowOutputError — 사건이 아니라 run_flow 쪽 Exception)도 엔진에 삼켜지지 않는다."""
    provider = Provider(answer)
    real = call_journal.JournalGateway.partial

    def broken(self: call_journal.JournalGateway) -> dict[str, object]:
        return {**real(self), "bad": float("nan")}

    monkeypatch.setattr(call_journal.JournalGateway, "partial", broken)
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(colab.FLOW, inputs(ten_pages()), adapters(provider.client()))
    assert caught.value.step == "translate" and len(provider.mock.calls) == 1


# ── T7: 어긋남·부서진 partial·상한 넘침 ──


def test_t7_a_diverged_journal_calls_from_there_and_matches_the_whole_run(
    every_call: None, caplog: pytest.LogCaptureFixture
) -> None:
    text = ten_pages()
    full, full_calls = whole(text, answer)
    partial, before = cut(text, answer, 20)
    journal = list(partial["journal"])  # type: ignore[arg-type]
    journal[12] = {**journal[12], "k": "0" * 64}
    caplog.set_level(logging.WARNING)
    events = Events()
    provider = Provider(answer)
    again = run_flow(
        colab.FLOW,
        inputs(text),
        adapters(provider.client()),
        start_at="translate",
        carried={"prepare": prepared(text, answer)},
        resume={**partial, "journal": journal},
        events=events,
    )
    same_output(full, again)
    assert len(provider.mock.calls) == full_calls - 12
    assert "translation_journal_diverged position=12" in caplog.text
    assert events.progress[0][0] == before + 1  # done 은 줄지 않는다(앞 done + 이 시도의 실제 호출)


@pytest.mark.parametrize(
    "change",
    [{"v": 2}, {"sourceSha256": "0" * 64}, {"calls": 1}, {"done": -1}, {"journal": [{"k": 1}]}, {"journal": "x"}],
    ids=["v", "source", "calls", "done", "entry", "journal"],
)
def test_t7_a_broken_partial_is_ignored_whole(
    every_call: None, caplog: pytest.LogCaptureFixture, change: dict[str, object]
) -> None:
    text = ten_pages(3)
    full, full_calls = whole(text, answer)
    partial, _ = cut(text, answer, 4)
    caplog.set_level(logging.WARNING)
    events = Events()
    again, provider = resumed(text, answer, {**partial, **change}, events=events)
    same_output(full, again)
    assert len(provider.mock.calls) == full_calls
    assert "translation_journal_ignored" in caplog.text
    # 일지를 통째로 버려도 꼴에 맞는 done 은 살린다(가지 리뷰 L4) — done 자체가 틀린 꼴이면 0 부터
    kept_done = 0 if "done" in change else cast("int", partial["done"])
    assert events.progress[0][0] == kept_done + 1


def test_t7_a_partial_over_the_byte_limit_fails_the_run_at_once(
    every_call: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(call_journal, "PARTIAL_MAX_BYTES", 2_000)
    caplog.set_level(logging.WARNING)
    provider = Provider(answer)
    events = Events()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(colab.FLOW, inputs(ten_pages()), adapters(provider.client()), events=events)
    assert isinstance(caught.value.__cause__, call_journal.JournalTooLarge)
    calls = len(provider.mock.calls)
    assert calls == len(events.partials) + 1  # 넘친 체크포인트의 호출 뒤 공급사 0
    assert "translation_journal_too_large" in caplog.text


def test_call_key_is_a_json_array_not_a_concatenation() -> None:
    assert call_journal.call_key("a", "b", "c", "d", 1, "r") != call_journal.call_key("a", "b", "cd", "", 1, "r")


# ── T5 변형: 시도를 넘는 금액 상한(순수 — 지출은 adapters.spent_usd 로 심는다. 밴드 TRE1 에서 새 뜻으로 다시 씀) ──

NO_USAGE = ProviderError(status=500, retryable=False, message="모의 실패")
"""사용량 없는 실패(`cost_usd` None — 실비를 모른다). 다리는 LlmCallFailed, 엔진은 삼키고 계속한다."""
FACTOR = run_bound.guard_factor(DEFAULT_PROVIDER_RETRY["openai"].max_retries)
"""openai 경로의 머리 여유 배수(감독 결정 D2 — 기본 재시도 2 → 3)."""
CALL_USD = 10 * 0.4e-6 + 10 * 1.6e-6
"""answer 한 호출의 실비(사용량 U · gpt-4.1-mini 단가 0.4/1.6 per 1M — models.json)."""


def _total(text: str) -> float:
    return cast("float", prepared(text, answer).data["totalEstimateUsd"])


def guard_term(step: StepOutput) -> float:
    """prepare 위끝의 마지막 호출 여유 항(위끝 − Σ ρ × 자리 어림 — tools/run_bound.py)."""
    per_site = cast("dict[str, dict[str, float]]", step.data["perSite"])
    total = cast("float", step.data["totalEstimateUsd"])
    return total - sum(v["ratio"] * v["estimateUsd"] for v in per_site.values())


@pytest.mark.parametrize("cap_from", ["estimate", "max_usd"])
def test_t5_a_resumed_attempt_whose_spend_reached_the_cap_is_over_budget_without_calls(
    every_call: None, cap_from: str
) -> None:
    """실행 중 상한 = min(max_usd, 위끝): 지출 ≥ 상한이면 이은 시도가 over_budget·공급사 0 — 위끝 쪽(max_usd 가
    커도)과 max_usd 쪽 둘 다(min 을 지우면 estimate 갈래가 돈다 — P1)."""
    text = ten_pages()
    partial, _ = cut(text, answer, 20)
    total = _total(text)
    max_usd = 10_000.0 if cap_from == "estimate" else total / 2
    spent = min(max_usd, total)
    again, provider = resumed(text, answer, partial, spent=spent, max_usd=max_usd)
    result = cast("dict[str, Any]", again.output.results[0])
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "over_budget")
    assert provider.mock.calls == []


def test_t5_a_resumed_attempt_runs_on_while_each_guard_fits(every_call: None) -> None:
    """허용액 = 남은 호출의 실비 합 + 마지막 호출 여유 + ε → done(호출마다 머리 여유를 빼고 실비로 되돌린다 —
    되돌림을 지우면 남은 실비보다 큰 머리 여유가 쌓여 도중에 멈춘다(P2)). 지출 + 이 시도 실비 ≤ 상한."""
    text = ten_pages()
    _, full_calls = whole(text, answer)
    partial, cut_calls = cut(text, answer, 20)
    step = prepared(text, answer)
    total, guard = cast("float", step.data["totalEstimateUsd"]), guard_term(step)
    remaining = (full_calls - cut_calls) * CALL_USD
    spent = total - (remaining + guard + 1e-9)
    again, provider = resumed(text, answer, partial, spent=spent, max_usd=10_000.0)
    assert again.output.results[0]["status"] == "done"
    assert len(provider.mock.calls) == full_calls - cut_calls
    assert spent + len(provider.mock.calls) * CALL_USD <= total


def _bounds_of(text: str, reply: Any, partial: Mapping[str, object] | None, replayed: int) -> list[float]:
    """허용액을 넉넉히 둔 이은 시도의 실제 호출 위끝(차례대로 — 마지막 체크포인트 일지에서 되감은 앞 칸을 뺀 것)."""
    events = Events()
    resumed(text, reply, partial, events=events)
    journal = cast("list[dict[str, Any]]", events.partials[-1]["journal"])
    return [e["boundUsd"] for e in journal[replayed:]]


def _stops_after_k(text: str, partial: Mapping[str, object] | None, replayed: int, k: int) -> tuple[float, float]:
    """사용량 없는 실패만 내는 공급사로: 허용액 A = Σ_{j<k} b_j + F·b_k + ε 면 k+1 호출 뒤 멈춘다(모름 = 엄격 위끝만큼
    깎임, F = openai 머리 여유 배수). → (A, ε 없는 b 합)."""
    bounds = _bounds_of(text, NO_USAGE, partial, replayed)
    # 분모: k+1 번째의 머리 여유가 남은 (F − 1)·b_k 에 들지 않는다
    assert len(bounds) > k + 1 and FACTOR * bounds[k + 1] > (FACTOR - 1) * bounds[k] + 1e-12
    return sum(bounds[:k]) + FACTOR * bounds[k] + 1e-12, sum(bounds[: k + 1])


def test_t5_a_failed_call_of_unknown_cost_is_charged_its_strict_bound(every_call: None) -> None:
    """실비를 모르는 실패(사용량 0)는 엄격 위끝만큼 깎는다(G2a): 허용액 A 에서 정확히 k+1 호출 뒤 over_budget. 같은
    A 에서 실비를 아는 공급사(answer)는 되돌림으로 그보다 멀리 간다(모름을 0 으로 보면 실패 쪽도 끝까지 — P8)."""
    text = ten_pages()
    k = 4
    allowance, _ = _stops_after_k(text, None, 0, k)
    total = _total(text)
    failing, provider = resumed(text, NO_USAGE, None, spent=total - allowance, max_usd=10_000.0)
    result = cast("dict[str, Any]", failing.output.results[0])
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "over_budget")
    assert len(provider.mock.calls) == k + 1
    _, cheap = resumed(text, answer, None, spent=total - allowance, max_usd=10_000.0)
    assert len(cheap.mock.calls) > k + 1


def test_t5_the_first_attempt_judges_like_prepare() -> None:
    """첫 시도(지출 0·일지 빔)는 prepare 의 판정과 같다 — 위끝 = 상한이면 통과(마지막 호출 여유 항 — S4)."""
    text = ten_pages(2)
    total = _total(text)
    run = run_flow(colab.FLOW, inputs(text, total), adapters(Provider(answer).client()))
    assert run.output.results[0]["status"] == "done"


# ── TRR1 가지 리뷰 M1·M2·L3: 시도의 남은 허용액·호출 밖 소프트 제한(M1·M2 는 밴드 TRE1 에서 새 뜻으로 다시 씀) ──


def _real_bounds(events: Events, replayed: int) -> float:
    """마지막 체크포인트 일지에서 되감은 앞 칸을 뺀 칸(이 시도의 실제 호출)의 위끝 합."""
    journal = cast("list[dict[str, Any]]", events.partials[-1]["journal"])
    return sum(e["boundUsd"] for e in journal[replayed:])


def test_m1_a_journal_diverging_mid_way_stops_at_the_allowance(every_call: None) -> None:
    """일지가 5 번째에서 어긋나면 그 뒤 칸은 버려지고 다시 불린다 — 다시 부르는 몫도 호출 전 판정을 지난다. 사용량
    없는 실패 공급사(호출마다 엄격 위끝만큼 깎임)로 허용액 A = Σ_{j<3} b_j + F·b_3 + ε 면 넷을 부르고 멈춘다(머리 여유
    판정을 지우면 끝까지 돈다 — P3)."""
    text = ten_pages()
    partial, _ = cut(text, answer, 20)
    journal = [dict(e) for e in cast("list[dict[str, Any]]", partial["journal"])]
    journal[5]["k"] = "0" * 64  # 5 번째부터 어긋남
    diverged = {**partial, "journal": journal}
    allowance, charged = _stops_after_k(text, diverged, 5, 3)
    total = _total(text)
    events = Events()
    again, provider = resumed(text, NO_USAGE, diverged, spent=total - allowance, max_usd=10_000.0, events=events)
    result = cast("dict[str, Any]", again.output.results[0])
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "over_budget")
    assert len(provider.mock.calls) == 4
    assert _real_bounds(events, 5) == pytest.approx(charged) and charged <= allowance


def test_m2_a_cheap_mock_plan_does_not_let_a_live_translate_overspend(every_call: None) -> None:
    """prepare 를 mock 경로로(가상 단가·출력 상한 4000) 어림하고 translate 를 live 꼴 다리(gpt-4.1)로 이으면 계획
    위끝이 낮다 — 상한 = mock 계획 위끝이어도 깎인 몫(사용량 없는 실패 — 호출마다 엄격 위끝)은 상한 안에서
    over_budget 으로 멈춘다. 공급사는 최악 사용량(출력 상한 · 어림 입력 × 2 — 실비 ≤ 머리 여유)이고 실제 지출(장부
    합)이 상한 안이다."""
    text = ten_pages()
    given = options(part="ceo_message", style={"compareAb": True, "single": "B"}, ceoPageLimit=None)
    mock_inputs = binding().inputs_with(document(text), given, company_id=1, versions={})
    fake = MockProvider("mock")
    mock_llm = LlmClient(
        config=load_config(default_config_sources(synthetic=True)),
        providers={"mock": fake, "openai": MockProvider("openai"), "anthropic": MockProvider("anthropic")},
        prompts=PackagePromptStore(),
        log=MemorySink(),
        provider_retry={},
        sleep=lambda _ms: None,
    )
    mocked = colab.TranslationAdapters(llm=mock_llm, tenant="1", mock=True, spent_usd=lambda: 0.0)
    prepare = colab.prepare(mock_inputs, mocked, {}, StepContext(resume=None))
    limit = cast("float", prepare.data["totalEstimateUsd"])
    live = binding(max_usd=limit).inputs_with(document(text), given, company_id=1, versions={})
    provider = Provider(worst(answer))
    events = Events()
    log = MemorySink()
    run = run_flow(
        colab.FLOW,
        live,
        adapters(provider.client(log)),
        start_at="translate",
        carried={"prepare": prepare},
        events=events,
    )
    result = cast("dict[str, Any]", run.output.results[0])
    assert (result["status"], result["rejection"]["kind"]) == ("rejected", "over_budget")
    assert provider.mock.calls and fake.calls == []
    assert 0 < sum(r.cost_usd or 0 for r in log.records) <= limit


def test_l3_a_soft_limit_outside_the_provider_call_leaves_the_step_with_a_last_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """소프트 제한이 위끝 어림(dry_run) 자리에서 나도 엔진에 삼켜지지 않는다. 나가기 전 체크포인트 한 번
    (best-effort)."""
    monkeypatch.setattr(call_journal, "monotonic", lambda: 0.0)  # 정기 체크포인트 0
    seen = [0]
    real = llm_bridge.LlmBridge.guard_usd

    def bound(self: llm_bridge.LlmBridge, *args: Any) -> tuple[float, float]:
        seen[0] += 1
        if seen[0] == 6:
            raise SoftTimeLimitExceeded("가짜 소프트 제한")
        return real(self, *args)

    monkeypatch.setattr(llm_bridge.LlmBridge, "guard_usd", bound)  # 일지가 위끝·머리 여유를 묻는 자리(D2)
    provider = Provider(answer)
    events = Events()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(colab.FLOW, inputs(ten_pages()), adapters(provider.client()), events=events)
    assert isinstance(caught.value.__cause__, SoftTimeLimitExceeded)
    assert len(provider.mock.calls) == 5  # 그 뒤 공급사 0
    assert [p["done"] for p in events.partials] == [5]  # 나가기 전 체크포인트 하나
