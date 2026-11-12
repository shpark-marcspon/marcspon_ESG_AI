"""펼침 단계의 맡김 갈래·구획 하나 돌기·계획 짓기·치명 접힘·합 검사 앞당김(RM1b ① — sid:MARC-TICK-567). 순수.

가짜 흐름 `probe.split@1`: prepare(장벽 — 구획 수) → spread(펼침 — 구획마다 숫자 하나, 또는 덧댐) → gather(모음 장벽).
이름·값은 지어낸 것이다(업무 모듈·실제 문서 0).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NoReturn, cast

import pytest

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.run import plan_segments, run_flow, run_segment
from esgapi.core.flows.types import (
    FANOUT_DATA_MAX_OCTETS,
    SEGMENT_DATA_MAX_OCTETS,
    Carried,
    FanoutStep,
    Flow,
    FlowInputError,
    FlowOutputError,
    FlowStep,
    FlowStepFailed,
    Segment,
    SegmentEnded,
    SegmentFailure,
    SegmentFailurePolicy,
    SegmentFatal,
    SegmentKey,
    SegmentOutput,
    SegmentPlanMismatch,
    SegmentsFailed,
    StepContext,
    StepOutput,
    segment_key_sha256,
)


@dataclass(frozen=True, slots=True)
class Inputs:
    count: int
    fail_at: frozenset[int] = frozenset()
    pad: int = 0  # 구획마다 data 에 덧대는 글자 수(합 검사)
    pad_at: tuple[tuple[int, int], ...] = ()  # (구획 n, 그 구획의 덧댐) — pad 를 갈음
    checkpoint_at: frozenset[int] = frozenset()


@dataclass(slots=True)
class Adapters:
    calls: list[int] = field(default_factory=list[int])


class Boom(Exception):
    """지어낸 구획 실패."""


def key_at(n: int) -> SegmentKey:
    return SegmentKey(kind="block", span=f"s{n}", document_sha256="e" * 64, parser_version="v1")


def prepare(inputs: Inputs, adapters: Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"count": inputs.count})


def plan(inputs: Inputs, carried: Carried) -> tuple[Segment, ...]:
    count = cast("int", carried["prepare"].data["count"])
    return tuple(Segment(key=key_at(n), input={"n": n}) for n in range(1, count + 1))


def spread(inputs: Inputs, adapters: Adapters, carried: Carried, segment: Segment, ctx: StepContext) -> SegmentOutput:
    n = cast("int", segment.input["n"])
    adapters.calls.append(n)
    if n in inputs.fail_at:
        raise Boom(f"구획 {n}")
    if n in inputs.checkpoint_at:
        ctx.checkpoint({"half": True}, done=1, total=2)
    pad = dict(inputs.pad_at).get(n, inputs.pad)
    if pad:
        return SegmentOutput(data={"n": n, "pad": "y" * pad})
    return SegmentOutput(data={"cube": n * n * n})


def gather(inputs: Inputs, adapters: Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(
        data={"results": [{"schemaVersion": "probe.split-result@1", "segments": carried["spread"].data["segments"]}]}
    )


def split_flow(*, on_failure: SegmentFailurePolicy = "pass_to_gather") -> Flow:
    return make_flow(
        module="probe",
        id="probe.split@1",
        input_shape="probe.input@1",
        inputs=Inputs,
        adapters=Adapters,
        result_shapes=("probe.split-result@1",),
        steps=(
            FlowStep(name="prepare", run=prepare),
            FanoutStep(name="spread", plan=plan, run=spread, on_failure=on_failure, allow_empty=True, max_segments=100),
            FlowStep(name="gather", run=gather),
        ),
    )


FLOW = split_flow()
FAIL_RUN = split_flow(on_failure="fail_run")
CARRIED: dict[str, StepOutput] = {"prepare": StepOutput(data={"count": 5})}


class Parked(BaseException):
    """실행기의 RunParked 꼴(BaseException — 흐름의 except Exception 이 잡지 못한다)."""


class Dispatcher:
    """맡김 받는 쪽. 받은 열쇠를 적고 Parked 로 나간다(returns=True 면 돌아온다 — 결함 꼴)."""

    def __init__(self, *, returns: bool = False, error: Exception | None = None) -> None:
        self.got: list[tuple[str, str, tuple[SegmentKey, ...]]] = []
        self.returns = returns
        self.error = error

    def dispatch(self, flow_id: str, step: str, pending: tuple[SegmentKey, ...]) -> NoReturn:
        self.got.append((flow_id, step, pending))
        if self.error is not None:
            raise self.error
        if not self.returns:
            raise Parked
        return self._back()  # 결함 꼴: 돌아온다(타입은 NoReturn 이라 우회)

    def _back(self) -> NoReturn:
        return cast("NoReturn", None)  # pyright: ignore[reportGeneralTypeIssues]


class Events:
    """두 포트의 사건을 적는다. fatal 이면 segment_failed 가 SegmentFatal 을, other 면 그 예외를 던진다."""

    def __init__(self, *, fatal: bool = False, other: Exception | None = None) -> None:
        self.seen: list[tuple[object, ...]] = []
        self.fatal = fatal
        self.other = other

    def step_started(self, flow_id: str, step: str) -> None:
        self.seen.append(("started", step))

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        self.seen.append(("finished", step))

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        self.seen.append(("failed", step, reason))

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        self.seen.append(("progress", step, done, total))

    def segments_planned(self, flow_id: str, step: str, keys: tuple[SegmentKey, ...]) -> None:
        self.seen.append(("planned", step, tuple(k.span for k in keys)))

    def segment_started(self, flow_id: str, step: str, key: SegmentKey) -> None:
        self.seen.append(("seg_started", key.span))

    def segment_finished(self, flow_id: str, step: str, key: SegmentKey, output: SegmentOutput) -> None:
        self.seen.append(("seg_finished", key.span))

    def segment_failed(self, flow_id: str, step: str, key: SegmentKey, err: Exception) -> str:
        self.seen.append(("seg_failed", key.span, type(err).__name__))
        if self.fatal:
            raise SegmentFatal(err) from err
        if self.other is not None:
            raise self.other
        return "made_up_code"

    def count(self, kind: str) -> int:
        return sum(1 for e in self.seen if e[0] == kind)


def sha(n: int) -> str:
    return segment_key_sha256(key_at(n))


def serial_bytes(inputs: Inputs) -> str:
    run = run_flow(FLOW, inputs, Adapters())
    return json.dumps(run.steps["spread"].data, ensure_ascii=False) + json.dumps(run.output.results)


# ── T1 구획 하나 돌기 ─────────────────────────────────────────────────


def test_run_segment_gives_the_same_data_the_serial_fanout_writes() -> None:
    run = run_flow(FLOW, Inputs(count=3), Adapters())
    entries = cast("list[dict[str, object]]", run.steps["spread"].data["segments"])
    for n, entry in zip(range(1, 4), entries, strict=True):
        got = run_segment(FLOW, "spread", Inputs(count=3), Adapters(), CARRIED, Segment(key=key_at(n), input={"n": n}))
        assert got == SegmentOutput(data=cast("dict[str, object]", entry["data"]))


def test_the_serial_fanout_bytes_are_those_written_by_hand() -> None:
    """직렬 data 바이트 그대로(RM1a 꼴) — 손으로 적은 글과 같다."""
    entries = [
        {
            "key": {"kind": "block", "span": f"s{n}", "documentSha256": "e" * 64, "parserVersion": "v1"},
            "keySha256": sha(n),
            "status": "done",
            "data": {"cube": n**3},
            "errorCode": None,
        }
        for n in (1, 2)
    ]
    want = json.dumps({"segments": entries}, ensure_ascii=False) + json.dumps(
        [{"schemaVersion": "probe.split-result@1", "segments": entries}]
    )
    assert serial_bytes(Inputs(count=2)) == want


def test_run_segment_checks_the_size_the_shape_and_forbids_checkpoints() -> None:
    segment = Segment(key=key_at(1), input={"n": 1})
    with pytest.raises(FlowOutputError, match="바이트를 넘는다"):
        run_segment(FLOW, "spread", Inputs(count=1, pad=SEGMENT_DATA_MAX_OCTETS), Adapters(), CARRIED, segment)
    with pytest.raises(FlowOutputError, match="체크포인트"):
        run_segment(FLOW, "spread", Inputs(count=1, checkpoint_at=frozenset({1})), Adapters(), CARRIED, segment)
    with pytest.raises(Boom):
        run_segment(FLOW, "spread", Inputs(count=1, fail_at=frozenset({1})), Adapters(), CARRIED, segment)
    with pytest.raises(FlowInputError):
        run_segment(FLOW, "gather", Inputs(count=1), Adapters(), CARRIED, segment)
    with pytest.raises(FlowInputError):
        run_segment(FLOW, "spread", object(), Adapters(), CARRIED, segment)
    with pytest.raises(FlowInputError):
        run_segment(FLOW, "spread", Inputs(count=1), object(), CARRIED, segment)


# ── T2 맡김 ───────────────────────────────────────────────────────────


def ended_of(*ns: int, failed: tuple[int, ...] = ()) -> dict[str, dict[str, SegmentEnded]]:
    done: dict[str, SegmentEnded] = {sha(n): SegmentOutput(data={"cube": n**3}) for n in ns}
    done.update({sha(n): SegmentFailure(error_code="made_up_code") for n in failed})
    return {"spread": done}


def test_dispatch_gets_the_unended_keys_in_plan_order_and_no_segment_runs() -> None:
    dispatcher, adapters, events = Dispatcher(), Adapters(), Events()
    with pytest.raises(Parked):
        run_flow(
            FLOW,
            Inputs(count=5),
            adapters,
            start_at="spread",
            carried=CARRIED,
            events=events,
            segment_events=events,
            segments_done=ended_of(2, 4),
            dispatch=dispatcher,
        )
    assert [(f, s, tuple(k.span for k in p)) for f, s, p in dispatcher.got] == [
        ("probe.split@1", "spread", ("s1", "s3", "s5"))
    ]
    assert adapters.calls == []
    assert events.count("seg_started") == 0 and events.count("planned") == 1 and events.count("failed") == 0


def test_an_ended_segment_outside_the_plan_is_a_mismatch_before_dispatching() -> None:
    """stray 검사가 맡김 앞이다 — 계획에 없는 끝난 구획이 있으면 맡기지 않고 SegmentPlanMismatch(그대로 올림)."""
    dispatcher, adapters = Dispatcher(), Adapters()
    stray = {"spread": {**ended_of(1)["spread"], sha(99): SegmentOutput(data={"cube": 0})}}
    with pytest.raises(SegmentPlanMismatch):
        run_flow(
            FLOW,
            Inputs(count=3),
            adapters,
            start_at="spread",
            carried={"prepare": StepOutput(data={"count": 3})},
            segments_done=stray,
            dispatch=dispatcher,
        )
    assert dispatcher.got == [] and adapters.calls == []


def test_a_dispatch_that_returns_fails_the_step() -> None:
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(FLOW, Inputs(count=2), Adapters(), dispatch=Dispatcher(returns=True))
    assert caught.value.step == "spread"
    assert isinstance(caught.value.__cause__, FlowOutputError)


def test_an_exception_from_the_dispatcher_goes_up_as_it_is() -> None:
    with pytest.raises(RuntimeError, match="받는 쪽"):
        run_flow(FLOW, Inputs(count=2), Adapters(), dispatch=Dispatcher(error=RuntimeError("받는 쪽")))


def test_plan_segments_is_the_plan_the_serial_fanout_records() -> None:
    events = Events()
    run_flow(FLOW, Inputs(count=4), Adapters(), events=events, segment_events=events)
    planned = next(e for e in events.seen if e[0] == "planned")[2]
    got = plan_segments(FLOW, "spread", Inputs(count=4), CARRIED | {"prepare": StepOutput(data={"count": 4})})
    assert tuple(s.key.span for s in got) == planned
    assert got == tuple(Segment(key=key_at(n), input={"n": n}) for n in range(1, 5))
    with pytest.raises(FlowInputError):
        plan_segments(FLOW, "prepare", Inputs(count=4), CARRIED)


# ── T3 다 끝남 · fail_run ─────────────────────────────────────────────


def test_all_ended_gathers_the_same_bytes_as_the_serial_run_without_dispatching() -> None:
    dispatcher, adapters = Dispatcher(), Adapters()
    run = run_flow(
        FLOW,
        Inputs(count=3),
        adapters,
        start_at="spread",
        carried={"prepare": StepOutput(data={"count": 3})},
        segments_done=ended_of(1, 2, 3),
        dispatch=dispatcher,
    )
    assert dispatcher.got == [] and adapters.calls == []
    got = json.dumps(run.steps["spread"].data, ensure_ascii=False) + json.dumps(run.output.results)
    assert got == serial_bytes(Inputs(count=3))


def test_fail_run_with_an_ended_failure_fails_without_dispatching() -> None:
    dispatcher = Dispatcher()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(
            FAIL_RUN,
            Inputs(count=4),
            Adapters(),
            start_at="spread",
            carried={"prepare": StepOutput(data={"count": 4})},
            segments_done=ended_of(1, failed=(3,)),
            dispatch=dispatcher,
        )
    assert caught.value.step == "spread"
    assert isinstance(caught.value.__cause__, SegmentsFailed)
    assert dispatcher.got == []


# ── T4 치명 접힘 ──────────────────────────────────────────────────────


def test_a_segment_fatal_folds_into_the_fanout_step_failure_with_the_original_cause() -> None:
    events, adapters = Events(fatal=True), Adapters()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(FLOW, Inputs(count=4, fail_at=frozenset({2})), adapters, events=events, segment_events=events)
    assert caught.value.step == "spread"
    assert isinstance(caught.value.__cause__, Boom)
    assert ("failed", "spread", "Boom: 구획 2") in events.seen
    assert adapters.calls == [1, 2]  # 뒤 구획을 부르지 않는다(pass_to_gather 여도)


def test_another_exception_from_segment_failed_goes_up_as_it_is() -> None:
    events = Events(other=RuntimeError("기록 결함"))
    with pytest.raises(RuntimeError, match="기록 결함"):
        run_flow(FLOW, Inputs(count=3, fail_at=frozenset({1})), Adapters(), events=events, segment_events=events)
    assert events.count("failed") == 0


# ── T5 합 검사 앞당김 ─────────────────────────────────────────────────


def test_the_serial_sum_check_fails_where_it_crosses_and_runs_nothing_after() -> None:
    pad = 500_000  # 구획 하나 ≈ 0.5MB(< SEGMENT_DATA_MAX_OCTETS) — 17째에서 FANOUT_DATA_MAX_OCTETS 를 넘는다
    assert pad < SEGMENT_DATA_MAX_OCTETS and 16 * pad < FANOUT_DATA_MAX_OCTETS < 17 * pad
    adapters = Adapters()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(FLOW, Inputs(count=20, pad=pad), adapters)
    assert caught.value.step == "spread"
    assert isinstance(caught.value.__cause__, FlowOutputError)
    assert adapters.calls == list(range(1, 18))


def test_just_under_the_sum_passes() -> None:
    adapters = Adapters()
    run = run_flow(FLOW, Inputs(count=16, pad=500_000), adapters)
    assert len(cast("list[object]", run.steps["spread"].data["segments"])) == 16


def padded_entry(n: int, pad: int) -> dict[str, object]:
    return {
        "key": {"kind": "block", "span": f"s{n}", "documentSha256": "e" * 64, "parserVersion": "v1"},
        "keySha256": sha(n),
        "status": "done",
        "data": {"n": n, "pad": "y" * pad},
        "errorCode": None,
    }


def octets_of(entries: list[dict[str, object]]) -> int:
    return len(json.dumps({"segments": entries}, ensure_ascii=False).encode("utf-8"))


def test_the_early_sum_check_has_exactly_the_end_check_threshold() -> None:
    """앞당긴 검사는 끝 검사와 같은 값이다: 펼친 data 가 정확히 FANOUT_DATA_MAX_OCTETS 면 통과,
    +1 이면 그 구획에서 실패하고 뒤 구획 run 0회."""
    pad = 500_000
    base = octets_of([padded_entry(n, pad) for n in range(1, 17)] + [padded_entry(17, 0)])
    last = FANOUT_DATA_MAX_OCTETS - base
    assert 0 < last < SEGMENT_DATA_MAX_OCTETS
    exact = [padded_entry(n, pad) for n in range(1, 17)] + [padded_entry(17, last)]
    assert octets_of(exact) == FANOUT_DATA_MAX_OCTETS

    adapters = Adapters()
    run = run_flow(FLOW, Inputs(count=17, pad=pad, pad_at=((17, last),)), adapters)
    assert run.steps["spread"].data == {"segments": exact}
    assert adapters.calls == list(range(1, 18))

    adapters = Adapters()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(FLOW, Inputs(count=18, pad=pad, pad_at=((17, last + 1), (18, 1))), adapters)
    assert caught.value.step == "spread" and isinstance(caught.value.__cause__, FlowOutputError)
    assert adapters.calls == list(range(1, 18))  # 18째는 부르지 않는다
