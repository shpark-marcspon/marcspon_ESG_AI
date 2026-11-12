"""단계 안 자리 진행(flows/progress_155, 밴드 IRW6 — 발주서 §3 S1~S7): regulation·controversy 는 토픽마다,
impact·financial·pathway 는 자리(토픽 × 서브토픽)마다 checkpoint(done/total)를 내고, 마지막 부분 산출물 == 그 단계 data,
resume 으로 다시 돌면 끝난 자리를 건너뛰어 요청·결과가 한 번 돈 실행과 같다. 틀린 resume 은 그 단계 실패(공급사 0),
resume 의 누계가 상한에 닿았으면 남은 자리는 budget_exceeded. 공급사는 모의만(실호출 0), 입력은 지어낸 「가상…」."""

import json
import math
from collections.abc import Mapping
from typing import Any, Final, cast

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowRun, FlowStepFailed, StepContext, StepOutput
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.types import ProviderRequest
from esgapi.materiality.flows import colab_155, iro_155, part2_155, progress_155
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.support import USAGE

TOPICS: Final = ("가상토픽 하나", "가상토픽 둘", "가상토픽 셋")
SUBTOPICS: Final = ("가상 서브 가", "가상 서브 나", "가상 서브 다", "가상 서브 라")
"""received3 의 자리 차례(토픽 입력 차례 → 서브토픽 차례)."""
UNREAD: Final = "가상 서브 나"
"""재무 답이 JSON 이 아닌 자리 — pathway 가 부르지 않고 건너뛴다(그래도 한 자리)."""
COUNTED: Final = ("regulation", "controversy", "impact", "financial", "pathway")


def received3() -> dict[str, Any]:
    """토픽 셋(산업 둘) · 서브토픽 넷(하나에 둘, 둘·셋에 하나씩)."""
    body = support.received2()
    body["topics"] = [{"topic": name, "description": f"{name}의 설명 — 가상의 관리"} for name in TOPICS]
    body["subtopicsByTopic"] = {
        **body["subtopicsByTopic"],
        "가상토픽 셋": [{"name": "가상 서브 라", "description": "가상 서브 라의 설명"}],
    }
    return body


def replies(given: Mapping[str, Any]) -> list[str]:
    """한 실행의 답을 호출 차례로: 규제 셋 → 키워드 → 컨트로버시 셋 → 영향 넷 → 재무 넷(UNREAD 는 JSON 아님) →
    Pathway 셋."""
    names = support.topic_names(given)
    out = [support.regulation_answer_dated(n) for n in names]
    out.append(support.keywords_answer(names))
    out += [support.controversy_answer_dated(n) for n in names]
    out += [support.impact_answer(s) for s in SUBTOPICS]
    out += ["가상 — JSON 아닌 재무 답" if s == UNREAD else support.financial_answer(s) for s in SUBTOPICS]
    out += [support.pathway_answer(s) for s in SUBTOPICS if s != UNREAD]
    return out


def mock_with(texts: list[str]) -> MockProvider:
    mock = MockProvider("openai")
    for text in texts:
        mock.enqueue_text(text, USAGE, hosted_calls=1)
    return mock


class Recorder:
    """사건을 적는다: 진행 (단계, done, total)·부분 산출물, 단계마다 그 단계 안 공급사 호출 수."""

    def __init__(self, mock: MockProvider) -> None:
        self.mock = mock
        self.progress: list[tuple[str, int, int]] = []
        self.partials: dict[tuple[str, int], Mapping[str, object]] = {}
        self.started_at: dict[str, int] = {}
        self.provider_calls: dict[str, int] = {}

    def step_started(self, flow_id: str, step: str) -> None:
        self.started_at[step] = len(self.mock.calls)

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        self.provider_calls[step] = len(self.mock.calls) - self.started_at[step]

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        self.provider_calls[step] = len(self.mock.calls) - self.started_at[step]

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        self.progress.append((step, done, total))
        self.partials[(step, done)] = partial

    def of(self, step: str) -> list[tuple[int, int]]:
        return [(done, total) for name, done, total in self.progress if name == step]


def body(request: ProviderRequest) -> bytes:
    return json.dumps(OpenAIProvider().build_request(request), ensure_ascii=False, sort_keys=True).encode()


def iro_once() -> tuple[FlowRun, Recorder, list[bytes]]:
    given = received3()
    mock = mock_with(replies(given))
    seen = Recorder(mock)
    done = run_flow(iro_155.FLOW, support.iro_inputs(given), iro_155.IroAdapters(llm=support.spy2(mock)), events=seen)
    assert mock.pending == 0
    return done, seen, [body(r) for r in mock.calls]


def slot_count(done: FlowRun) -> int:
    return len(part2_155.slots(cast("Mapping[str, Any]", done.steps[part2_155.SEED].data["input"]))[0])


def calls_before(done: FlowRun, step: str) -> int:
    """step 앞 단계들이 부른 공급사 수(호출 기록 = 공급사 호출 하나 — 잘림 0)."""
    names = iro_155.FLOW.steps[: iro_155.FLOW.steps.index(step)]
    return sum(len(cast("list[object]", done.steps[n].data.get("calls", []))) for n in names)


def resume_iro(once: FlowRun, step: str, resume: Mapping[str, object], texts: list[str]) -> tuple[FlowRun, Recorder]:
    mock = mock_with(texts)
    seen = Recorder(mock)
    before = iro_155.FLOW.steps[: iro_155.FLOW.steps.index(step)]
    again = run_flow(
        iro_155.FLOW,
        support.iro_inputs(received3()),
        iro_155.IroAdapters(llm=support.spy2(mock)),
        start_at=step,
        carried={name: once.steps[name] for name in before},
        resume=resume,
        events=seen,
    )
    return again, seen


# ── S1 진행 사건 ──


def test_each_counted_step_reports_done_over_total_per_slot_and_others_report_nothing() -> None:
    done, seen, _ = iro_once()
    slots = slot_count(done)
    assert slots == len(SUBTOPICS)
    topics = len(TOPICS)
    assert seen.of("regulation") == [(n, topics) for n in range(topics + 1)]
    assert seen.of("controversy") == [(n, topics) for n in range(topics + 1)]
    for step in ("impact", "financial", "pathway"):  # pathway 의 건너뜀 자리(UNREAD)도 한 자리
        assert seen.of(step) == [(n, slots) for n in range(slots + 1)], step
    assert {name for name, _, _ in seen.progress} == set(COUNTED)  # keywords·load·report·part2_seed·report_iro 0
    assert seen.provider_calls["pathway"] == slots - 1


# ── S2 마지막 부분 산출물 == 그 단계 data ──


def test_the_last_partial_of_each_counted_step_is_its_data() -> None:
    done, seen, _ = iro_once()
    for step in COUNTED:
        last = seen.of(step)[-1][0]
        assert seen.partials[(step, last)] == done.steps[step].data, step


# ── S3 이어 돌기 = 한 번 돈 것 ──


@pytest.mark.parametrize(("step", "k"), [("regulation", 2), ("controversy", 1), ("impact", 1)])
def test_resuming_mid_step_skips_finished_slots_and_ends_like_the_single_run(step: str, k: int) -> None:
    once, seen, once_bodies = iro_once()
    skipped = calls_before(once, step) + k
    total = seen.of(step)[-1][1]

    again, seen2 = resume_iro(once, step, seen.partials[(step, k)], replies(received3())[skipped:])

    assert seen2.provider_calls[step] == seen.provider_calls[step] - k  # controversy: 2(3 아님)
    assert seen2.of(step)[0] == (k + 1, total)  # 시작 checkpoint(0)를 다시 내지 않는다
    assert again.steps[step].data == once.steps[step].data
    assert again.output.results == once.output.results  # @2 · digest
    again_bodies = [body(r) for r in seen2.mock.calls]
    assert len(again_bodies) == len(once_bodies) - skipped
    assert again_bodies == once_bodies[skipped:]


# ── S4 끝난 부분 산출물로 다시 ──


@pytest.mark.parametrize("step", ["regulation", "controversy", "impact"])
def test_resuming_with_a_finished_partial_calls_nothing_in_that_step(step: str) -> None:
    once, seen, _ = iro_once()
    total = seen.of(step)[-1][1]
    skipped = calls_before(once, step) + seen.provider_calls[step]

    again, seen2 = resume_iro(once, step, seen.partials[(step, total)], replies(received3())[skipped:])

    assert seen2.provider_calls[step] == 0
    assert seen2.of(step) == []
    assert again.steps[step].data == seen.partials[(step, total)]
    assert again.output.results == once.output.results


# ── S5 틀린 resume → 그 단계 실패 · 공급사 0 ──


def _drop_key(partial: dict[str, Any]) -> None:
    del partial["calls"]


def _swap_topic(partial: dict[str, Any]) -> None:
    partial["answers"][0]["topic"] = TOPICS[1]


def _too_long(partial: dict[str, Any]) -> None:
    """끝난 partial 에 마지막 답을 하나 더 — 자리 차례는 맞고 길이만 넘친다."""
    partial["answers"] = [*partial["answers"], partial["answers"][-1]]


def _swap_subtopic(partial: dict[str, Any]) -> None:
    partial["answers"][0]["subtopic"] = SUBTOPICS[1]  # 2부 열쇠의 subtopic — 토픽은 같다


def _bool_spent(partial: dict[str, Any]) -> None:
    partial["spentUsd"] = True


def _less_spent(partial: dict[str, Any]) -> None:
    partial["spentUsd"] = 0.0  # 넘겨받은 키워드 뒤 누계(> 0)보다 작다


@pytest.mark.parametrize(
    ("step", "done", "spoil"),
    [
        ("controversy", 1, _drop_key),
        ("controversy", 1, _swap_topic),
        ("controversy", len(TOPICS), _too_long),
        ("controversy", 1, _bool_spent),
        ("controversy", 1, _less_spent),
        ("impact", 1, _swap_subtopic),
    ],
)
def test_a_wrong_resume_fails_the_step_without_calling_the_provider(step: str, done: int, spoil: Any) -> None:
    once, seen, _ = iro_once()
    partial = json.loads(json.dumps(seen.partials[(step, done)]))
    spoil(partial)
    mock = MockProvider("openai")
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(
            iro_155.FLOW,
            support.iro_inputs(received3()),
            iro_155.IroAdapters(llm=support.spy2(mock)),
            start_at=step,
            carried={name: once.steps[name] for name in iro_155.FLOW.steps[: iro_155.FLOW.steps.index(step)]},
            resume=partial,
        )
    assert caught.value.step == step
    assert isinstance(caught.value.__cause__, ValueError)
    assert mock.calls == []


@pytest.mark.parametrize("spent", [math.nan, math.inf, -math.inf])
def test_a_resume_spent_that_is_not_finite_is_refused(spent: float) -> None:
    """run_flow 는 NaN·Infinity 를 JSON 왕복에서 먼저 거른다(FlowInputError) — 여기는 단계 함수에 바로."""
    resume: dict[str, object] = {"answers": [], "calls": [], "spentUsd": spent}
    with pytest.raises(ValueError, match="spentUsd"):
        progress_155.start(StepContext(resume=resume), [("가상토픽 하나",)], 0.0)


# ── S6 resume 의 누계가 상한에 닿음 ──


def test_a_resume_spent_at_the_cap_leaves_the_rest_budget_exceeded_without_calls() -> None:
    once, seen, _ = iro_once()
    partial = json.loads(json.dumps(seen.partials[("controversy", 1)]))
    partial["spentUsd"] = support.COST

    again, seen2 = resume_iro(once, "controversy", partial, [])

    assert seen2.mock.calls == []
    answers = cast("list[dict[str, Any]]", again.steps["controversy"].data["answers"])
    assert answers[0] == partial["answers"][0]
    assert [a["failure"] for a in answers[1:]] == [{"kind": "budget_exceeded", "message": "budget_exceeded (run)"}] * (
        len(TOPICS) - 1
    )


# ── S7 1부 단독 흐름 ──


def test_the_part1_flow_alone_reports_regulation_and_controversy_progress() -> None:
    given = support.received()
    mock = MockProvider("openai")
    support.script_all(mock, given)
    seen = Recorder(mock)
    run_flow(
        colab_155.FLOW,
        support.inputs(received=given),
        colab_155.MaterialityAdapters(llm=support.spy(mock)),
        events=seen,
    )
    topics = len(support.topic_names(given))
    assert topics == 3
    assert seen.of("regulation") == [(n, topics) for n in range(topics + 1)]
    assert seen.of("controversy") == [(n, topics) for n in range(topics + 1)]
    assert {name for name, _, _ in seen.progress} == {"regulation", "controversy"}
