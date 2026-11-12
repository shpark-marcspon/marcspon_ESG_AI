"""흐름 scope3.colab@157 이 실행을 멈추는 자리와 멈추지 않는 자리(밴드 S3K3 — MARC-ISSUE-521, DB 0, `run_flow` 직접).

    멈춤(FlowStepFailed — 실행기가 failed 로 접는다)
      설정 결함 셋     가짜 공급사가 n 번째 부름에서 LiveSetupError·LlmConfigError·PromptError → __cause__ 그 예외,
                      step = 그 부름이 난 카테고리 단계
      공급사 거절      401·403·404·429 insufficient_quota·error_kind quota_exhausted(S3Q3 — 글에 그 code 가 없어도)
                      → __cause__ Scope3ProviderRejected
      비용 상한        n 번째 부름부터 BudgetExceeded → __cause__ Scope3BudgetExceeded, 공급사 부름 n 번
    멈추지 않음(코랩대로 done — MARC-ENT-442)
      공급사 5xx       결과 llmCalls 에 failed:provider_error(error_kind rate_limited·overloaded 도 같음 — S3Q3)
      데이터 탓 예외   처리기 하나가 ValueError → 그 시트 status failed·error, 남은 시트 processed
    로그              done 인데 시트·LLM 실패가 있으면 assemble 이 수만 실은 경고 한 줄(이름·오류 글 0), 없으면 0
    이어 돌기          설정을 고쳐 끝난 단계만 옮겨(실행기 _carried 꼴) 실패한 단계부터 → 끊김 없는 것과 같은 바이트

가짜 공급사는 resume 시험의 Provider(지은 답)를 감싼다. 템플릿·계수·답은 전부 지은 것이다.
"""

import logging
from collections.abc import Callable
from typing import cast

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowStepFailed
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError, PromptError
from esgapi.core.llm.types import BudgetExceeded, CallMeta, ErrorKind, LlmResult, ProviderFailed, Scope
from esgapi.inventory.engines.scope3.colab_157 import pipeline
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.flows.scope3_journal_157 import Scope3BudgetExceeded, Scope3ProviderRejected
from esgapi.inventory.tests.flows.test_scope3_colab_157_resume import (
    SHEETS,
    Provider,
    Rows,
    adapters_of,
    base,
    inputs_of,
    sha,
)

META = CallMeta(call_id="가상", prompt_id="가상", attempts=(), total_cost_usd=0.0, warnings=())


def rejected(
    status: int, message: str = "가상 공급사 글", error_kind: ErrorKind | None = None
) -> Callable[[], LlmResult[object]]:
    retryable = status >= 429 and error_kind != "quota_exhausted"
    return lambda: ProviderFailed(status=status, retryable=retryable, message=message, meta=META, error_kind=error_kind)


def raising(error: Exception) -> Callable[[], LlmResult[object]]:
    def go() -> LlmResult[object]:
        raise error

    return go


class Breaking(Provider):
    """from_call 번째 부름부터(포함) bad() 의 값을 돌려주거나 던진다. 그 전은 resume 시험의 지은 답."""

    def __init__(self, from_call: int, bad: Callable[[], LlmResult[object]]) -> None:
        super().__init__()
        self.from_call = from_call
        self.bad = bad
        self.steps: list[str] = []

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        if self.calls + 1 >= self.from_call:
            self.calls += 1
            return cast("LlmResult[T]", self.bad())
        return super().call(request)


def step_of_call(n: int) -> str:
    """끊김 없는 한 바퀴에서 n 번째 실제 부름이 난 카테고리 단계(일지 칸 수로 셈)."""
    done = run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(Provider()))
    seen = 0
    for step in colab.CATEGORY_STEPS:
        seen += len(cast("list[object]", done.steps[step].data["journal"]))
        if seen >= n:
            return step
    raise AssertionError(n)


# ── 멈춤 ──


@pytest.mark.parametrize("error", [LiveSetupError, LlmConfigError, PromptError])
@pytest.mark.parametrize("n", [1, 7])
def test_a_setup_error_fails_the_flow_at_the_step_that_called(error: type[Exception], n: int) -> None:
    provider = Breaking(n, raising(error("가상 설정 결함")))
    with pytest.raises(FlowStepFailed) as raised:
        run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(provider))
    assert type(raised.value.__cause__) is error
    assert raised.value.step == step_of_call(n)
    assert provider.calls == n  # 첫 결함에서 멈춤 — 뒤 부름 0


@pytest.mark.parametrize(
    "bad",
    [
        rejected(401),
        rejected(403),
        rejected(404),
        rejected(429, "Error code: 429 - {'code': 'insufficient_quota'}"),
        rejected(429, "Error code: 429 - {'code': 'credit_balance_exhausted'}", "quota_exhausted"),
        rejected(402, "가상 청구 오류", "quota_exhausted"),
        rejected(429, "가상 지출 상한 글", "quota_exhausted"),
    ],
    ids=["401", "403", "404", "429-quota", "429-credit-kind", "402-kind", "429-spend-cap-kind"],
)
def test_a_provider_refusal_fails_the_flow(bad: Callable[[], LlmResult[object]]) -> None:
    provider = Breaking(1, bad)
    with pytest.raises(FlowStepFailed) as raised:
        run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(provider))
    assert isinstance(raised.value.__cause__, Scope3ProviderRejected)
    assert raised.value.step == "c1"
    assert provider.calls == 1


@pytest.mark.parametrize("n", [1, 4, 12])
def test_a_budget_stop_fails_the_flow_at_the_first_call_over(n: int) -> None:
    provider = Breaking(n, lambda: BudgetExceeded(limit_usd=0.5, spent_usd=0.5, scope=Scope(), meta=META))
    with pytest.raises(FlowStepFailed) as raised:
        run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(provider))
    assert isinstance(raised.value.__cause__, Scope3BudgetExceeded)
    assert "비용 상한" in str(raised.value.__cause__)
    assert raised.value.step == step_of_call(n)
    assert provider.calls == n  # 넘은 첫 부름에서 멈춤 — 빈 줄로 끝까지 가지 않음


# ── 멈추지 않음 ──


def test_a_provider_5xx_stays_done_with_failed_counts(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=colab.logger.name):
        done = run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(Breaking(1, rejected(500))))
    (result,) = done.output.results
    (line,) = [r.getMessage() for r in caplog.records if r.name == colab.logger.name]
    assert line.startswith("scope3_result_problems failed_sheets=0 llm_failed=") and not line.endswith("=0")
    assert result["status"] == "done"
    counts = cast("dict[str, dict[str, int]]", result["llmCalls"])
    assert counts and all(set(c) == {"failed:provider_error"} for c in counts.values())


@pytest.mark.parametrize(
    "bad",
    [
        rejected(429, "Error code: 429 - {'code': 'rate_limit_exceeded'}", "rate_limited"),
        rejected(429, "Error code: 429", "rate_limited"),
        rejected(529, "가상 과부하", "overloaded"),
    ],
    ids=["429-rate", "429-no-body", "529-overloaded"],
)
def test_a_rate_limit_or_overload_stays_done_with_failed_counts(bad: Callable[[], LlmResult[object]]) -> None:
    done = run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(Breaking(1, bad)))
    (result,) = done.output.results
    assert result["status"] == "done"
    counts = cast("dict[str, dict[str, int]]", result["llmCalls"])
    assert counts and all(set(c) == {"failed:provider_error"} for c in counts.values())


def test_a_data_error_in_one_sheet_stays_done_with_that_sheet_failed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    real = pipeline.process_activity_sheet

    def broken(*args: object, **kwargs: object) -> object:
        if args[3] == "c7":  # (activity, template, sheet, processor.key, category) — 통근 시트만
            raise ValueError("가상 값 오류")
        return real(*args, **kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(pipeline, "process_activity_sheet", broken)
    with caplog.at_level(logging.WARNING, logger=colab.logger.name):
        done = run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(Provider()))
    problems = [r.getMessage() for r in caplog.records if r.name == colab.logger.name]
    assert problems == ["scope3_result_problems failed_sheets=1 llm_failed=0"]  # 시트 이름·오류 글 0
    (result,) = done.output.results
    assert result["status"] == "done"
    sheets = cast("list[dict[str, object]]", result["sheets"])
    failed = [s for s in sheets if s["status"] == "failed"]
    assert [(s["sheet"], s["error"]) for s in failed] == [("c7_임직원통근", "ValueError: 가상 값 오류")]
    assert {s["status"] for s in sheets if s is not failed[0]} <= {"processed", "not_target"}


def test_a_clean_run_logs_no_problem(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger=colab.logger.name):
        run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(Provider()))
    assert [r for r in caplog.records if r.name == colab.logger.name] == []


# ── 설정을 고쳐 이어 돌기 ──


@pytest.mark.parametrize("n", [1, 7, 20])
def test_after_fixing_the_setup_a_resume_redoes_only_the_failed_step(n: int) -> None:
    """실행기의 이어 돌기 꼴(resumeFromRunId — 끝난 단계만 옮김, 실패 단계 partial 0): 바이트 같음 · 옮긴 단계
    공급사 0."""
    want, total = base(SHEETS)
    rows = Rows()
    broken = Breaking(n, raising(LiveSetupError("가상 키 없음")))
    with pytest.raises(FlowStepFailed) as raised:
        run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(broken), events=rows)
    start = raised.value.step
    carried = {s: rows.finished[s] for s in colab.FLOW.steps[: colab.FLOW.steps.index(start)]}
    fixed = Provider()
    done = run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(fixed), start_at=start, carried=carried, resume=None)
    assert sha(done.steps[colab.ASSEMBLE].data) == want
    moved = sum(len(cast("list[object]", o.data["journal"])) for o in carried.values())
    assert fixed.calls == total - moved
    assert moved < n  # 실패 단계 안에서 이미 부른 것은 다시 부른다(그 단계 partial 은 옮기지 않음)


def test_a_budget_stop_inside_assemble_also_leaves_the_engine() -> None:
    """assemble(적지 않는 게이트웨이 — record=False)의 실제 부름이 상한에 닿아도 빼낸다(검증 권고 R4). 일지가 빈
    assemble 은 실제로 부르고, 첫 부름에서 멈춘다."""
    provider = Breaking(1, lambda: BudgetExceeded(limit_usd=0.5, spent_usd=0.5, scope=Scope(), meta=META))
    with pytest.raises(Scope3BudgetExceeded):
        colab.assemble_run(inputs_of(SHEETS), adapters_of(provider), ())
    assert provider.calls == 1
