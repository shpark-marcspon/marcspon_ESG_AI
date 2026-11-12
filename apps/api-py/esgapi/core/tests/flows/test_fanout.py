"""펼침 단계(RM1a — sid:MARC-ENT-618): 선언 검사·구획 열쇠·직렬 펼침·이어 돌기·실패 정책·크기·결과 검사 훅. 순수.

가짜 흐름 `probe.fan@1`: prepare(장벽 — 구획 수를 data 에) → spread(펼침 — 구획마다 숫자 하나) → gather(모음 장벽 —
carried 의 segments 를 결과로). 이름·값은 지어낸 것이다(업무 모듈·실제 문서 0).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

import pytest

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import (
    FANOUT_DATA_MAX_OCTETS,
    SEGMENT_DATA_MAX_OCTETS,
    Carried,
    FanoutStep,
    Flow,
    FlowInputError,
    FlowOutputError,
    FlowRegistryError,
    FlowStep,
    FlowStepFailed,
    ResultCheck,
    Segment,
    SegmentEnded,
    SegmentFailure,
    SegmentFailurePolicy,
    SegmentKey,
    SegmentOutput,
    SegmentPlanMismatch,
    SegmentsEmpty,
    SegmentsFailed,
    StepContext,
    StepOutput,
    segment_key_fields,
    segment_key_of,
    segment_key_sha256,
    segment_key_text,
)


@dataclass(frozen=True, slots=True)
class Inputs:
    count: int
    fail_at: frozenset[int] = frozenset()
    big_at: frozenset[int] = frozenset()
    checkpoint_at: frozenset[int] = frozenset()


@dataclass(slots=True)
class Adapters:
    calls: list[int] = field(default_factory=list[int])


def key_at(n: int) -> SegmentKey:
    return SegmentKey(kind="block", span=f"b{n}", document_sha256="d" * 64, parser_version="p1")


def prepare(inputs: Inputs, adapters: Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(data={"count": inputs.count})


def plan(inputs: Inputs, carried: Carried) -> tuple[Segment, ...]:
    count = cast("int", carried["prepare"].data["count"])
    return tuple(Segment(key=key_at(n), input={"n": n}) for n in range(1, count + 1))


def spread(inputs: Inputs, adapters: Adapters, carried: Carried, segment: Segment, ctx: StepContext) -> SegmentOutput:
    n = cast("int", segment.input["n"])
    adapters.calls.append(n)
    if n in inputs.fail_at:
        raise ValueError(f"구획 {n} 이 깨졌다")
    if n in inputs.checkpoint_at:
        ctx.checkpoint({"half": True}, done=1, total=2)
    if n in inputs.big_at:
        return SegmentOutput(data={"pad": "x" * (SEGMENT_DATA_MAX_OCTETS + 1)})
    return SegmentOutput(data={"square": n * n})


def gather(inputs: Inputs, adapters: Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(
        data={"results": [{"schemaVersion": "probe.fan-result@1", "segments": carried["spread"].data["segments"]}]}
    )


def fan_flow(
    *,
    on_failure: SegmentFailurePolicy = "pass_to_gather",
    allow_empty: bool = True,
    max_segments: int = 100,
    result_checks: tuple[ResultCheck, ...] = (),
) -> Flow:
    return make_flow(
        module="probe",
        id="probe.fan@1",
        input_shape="probe.input@1",
        inputs=Inputs,
        adapters=Adapters,
        result_shapes=("probe.fan-result@1",),
        steps=(
            FlowStep(name="prepare", run=prepare),
            FanoutStep(
                name="spread",
                plan=plan,
                run=spread,
                on_failure=on_failure,
                allow_empty=allow_empty,
                max_segments=max_segments,
            ),
            FlowStep(name="gather", run=gather),
        ),
        result_checks=result_checks,
    )


class Recorder:
    """두 포트(FlowEvents·SegmentEvents)의 사건을 차례로 적는다. failed_code 가 실패 구획의 code 다."""

    def __init__(self, failed_code: str = "made_up_code") -> None:
        self.seen: list[tuple[object, ...]] = []
        self.failed_code = failed_code
        self.raise_on: dict[str, BaseException] = {}

    def _maybe(self, what: str) -> None:
        err = self.raise_on.get(what)
        if err is not None:
            raise err

    def step_started(self, flow_id: str, step: str) -> None:
        self.seen.append(("started", step))

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        self.seen.append(("finished", step))

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        self.seen.append(("failed", step, reason))

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        self.seen.append(("progress", step, done, total, dict(partial)))
        self._maybe("progress")

    def segments_planned(self, flow_id: str, step: str, keys: tuple[SegmentKey, ...]) -> None:
        self.seen.append(("planned", step, tuple(k.span for k in keys)))
        self._maybe("planned")

    def segment_started(self, flow_id: str, step: str, key: SegmentKey) -> None:
        self.seen.append(("seg_started", key.span))
        self._maybe("started")

    def segment_finished(self, flow_id: str, step: str, key: SegmentKey, output: SegmentOutput) -> None:
        self.seen.append(("seg_finished", key.span))
        self._maybe("finished")

    def segment_failed(self, flow_id: str, step: str, key: SegmentKey, err: Exception) -> str:
        self.seen.append(("seg_failed", key.span, type(err).__name__))
        self._maybe("failed")
        return self.failed_code

    def count(self, kind: str) -> int:
        return sum(1 for e in self.seen if e[0] == kind)


def segments_of(flow: Flow, inputs: Inputs, adapters: Adapters, **kwargs: object) -> list[dict[str, object]]:
    run = run_flow(flow, inputs, adapters, **kwargs)  # pyright: ignore[reportArgumentType]
    body = run.output.results[0]
    return cast("list[dict[str, object]]", body["segments"])


# ── T1 선언 검사 ─────────────────────────────────────────────────────


def fanout(**overrides: object) -> FanoutStep[Inputs, Adapters]:
    values: dict[str, object] = {
        "name": "spread",
        "plan": plan,
        "run": spread,
        "on_failure": "fail_run",
        "allow_empty": False,
        "max_segments": 10,
    }
    values.update(overrides)
    built: FanoutStep[Inputs, Adapters] = FanoutStep(**values)  # pyright: ignore[reportArgumentType, reportUnknownVariableType]
    return built


def declare(*steps: object) -> Flow:
    return make_flow(
        module="probe",
        id="probe.fan@1",
        input_shape="probe.input@1",
        inputs=Inputs,
        adapters=Adapters,
        result_shapes=("probe.fan-result@1",),
        steps=cast("tuple[FlowStep[Inputs, Adapters], ...]", steps),
    )


def test_a_barrier_only_flow_has_barrier_kinds_no_checks_and_no_fanouts() -> None:
    flow = declare(FlowStep(name="prepare", run=prepare), FlowStep(name="gather", run=gather))
    assert flow.step_kinds == ("barrier", "barrier")
    assert flow.result_checks == ()
    assert dict(flow.fanouts) == {}


def test_a_fanout_flow_declares_its_kinds_and_fanouts() -> None:
    flow = fan_flow()
    assert flow.steps == ("prepare", "spread", "gather")
    assert flow.step_kinds == ("barrier", "fanout", "barrier")
    assert set(flow.fanouts) == {"spread"}


@pytest.mark.parametrize("where", ["first", "last"])
def test_a_fanout_cannot_be_the_first_or_last_step(where: str) -> None:
    barrier = FlowStep(name="prepare", run=prepare)
    steps = (fanout(), barrier) if where == "first" else (barrier, fanout())
    with pytest.raises(FlowRegistryError, match="첫·끝"):
        declare(*steps)


def test_two_fanouts_are_allowed() -> None:
    flow = declare(
        FlowStep(name="prepare", run=prepare),
        fanout(name="spread"),
        fanout(name="spread_again"),
        FlowStep(name="gather", run=gather),
    )
    assert flow.step_kinds == ("barrier", "fanout", "fanout", "barrier")


def test_fanout_fields_have_no_defaults() -> None:
    with pytest.raises(TypeError):
        FanoutStep(name="spread", plan=plan, run=spread, allow_empty=True, max_segments=1)  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError):
        FanoutStep(name="spread", plan=plan, run=spread, on_failure="fail_run", allow_empty=True)  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError):
        FanoutStep(name="spread", plan=plan, run=spread, on_failure="fail_run", max_segments=1)  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize(
    "overrides",
    [
        {"on_failure": None},
        {"on_failure": "retry"},
        {"max_segments": None},
        {"max_segments": 0},
        {"max_segments": 10_001},
        {"max_segments": True},
        {"allow_empty": None},
        {"plan": "not callable"},
    ],
)
def test_fanout_field_values_out_of_range_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(FlowRegistryError):
        declare(FlowStep(name="prepare", run=prepare), fanout(**overrides), FlowStep(name="gather", run=gather))


def test_run_step_refuses_a_fanout_name() -> None:
    flow = fan_flow()
    with pytest.raises(FlowInputError, match="장벽 단계가 아니다"):
        flow.run_step("spread", Inputs(count=1), Adapters(), {}, StepContext(resume=None))


def test_fanout_plan_and_run_check_the_inputs_and_adapters() -> None:
    fan = fan_flow().fanouts["spread"]
    with pytest.raises(FlowInputError):
        fan.plan(object(), {})
    with pytest.raises(FlowInputError):
        fan.run(Inputs(count=1), object(), {}, Segment(key=key_at(1), input={"n": 1}), StepContext(resume=None))


# ── T2 구획 열쇠 ─────────────────────────────────────────────────────


def test_the_key_text_is_the_same_whatever_the_field_order() -> None:
    fields = segment_key_fields(key_at(1))
    reordered = dict(reversed(list(fields.items())))
    assert list(reordered) != list(fields)
    assert segment_key_text(reordered) == segment_key_text(fields)
    assert segment_key_sha256(segment_key_of(reordered)) == segment_key_sha256(key_at(1))
    assert segment_key_text(fields) == (
        '{"documentSha256":"' + "d" * 64 + '","kind":"block","parserVersion":"p1","span":"b1"}'
    )


def test_one_letter_or_a_none_makes_a_different_key() -> None:
    base = key_at(1)
    others = [
        SegmentKey(kind="block", span="b2", document_sha256="d" * 64, parser_version="p1"),
        SegmentKey(kind="block", span="b1", document_sha256=None, parser_version="p1"),
        SegmentKey(kind="block", span="b1", document_sha256="d" * 64, parser_version=None),
        SegmentKey(kind="page", span="b1", document_sha256="d" * 64, parser_version="p1"),
    ]
    shas = {segment_key_sha256(k) for k in [base, *others]}
    assert len(shas) == 5
    assert all(len(s) == 64 for s in shas)


def test_a_key_round_trips_through_its_fields_and_none_is_kept_as_null() -> None:
    key = SegmentKey(kind="block", span="b1", document_sha256=None, parser_version=None)
    assert segment_key_fields(key) == {"kind": "block", "span": "b1", "documentSha256": None, "parserVersion": None}
    assert segment_key_of(segment_key_fields(key)) == key
    with pytest.raises(ValueError):
        segment_key_of({"kind": "block", "span": "b1"})


# ── T3 직렬 펼침 ─────────────────────────────────────────────────────


def test_barrier_fanout_gather_runs_every_segment_in_plan_order() -> None:
    events = Recorder()
    adapters = Adapters()
    got = segments_of(fan_flow(), Inputs(count=5), adapters, events=events, segment_events=events)
    assert [cast("dict[str, object]", s["key"])["span"] for s in got] == ["b1", "b2", "b3", "b4", "b5"]
    assert [s["status"] for s in got] == ["done"] * 5
    assert [s["data"] for s in got] == [{"square": n * n} for n in range(1, 6)]
    assert [s["errorCode"] for s in got] == [None] * 5
    assert [s["keySha256"] for s in got] == [segment_key_sha256(key_at(n)) for n in range(1, 6)]
    assert adapters.calls == [1, 2, 3, 4, 5]
    assert events.count("planned") == 1
    assert events.count("seg_started") == 5
    assert events.count("seg_finished") == 5
    assert [e[2:] for e in events.seen if e[0] == "progress"] == [(n, 5, {}) for n in range(1, 6)]
    assert [e[:2] for e in events.seen if e[0] in ("started", "finished")] == [
        ("started", "prepare"),
        ("finished", "prepare"),
        ("started", "spread"),
        ("finished", "spread"),
        ("started", "gather"),
        ("finished", "gather"),
    ]


def test_segments_run_in_reverse_give_the_same_gathered_list() -> None:
    """구획 run 은 다른 구획에 기대지 않는다(R2): 거꾸로 돌린 산출을 끝난 구획으로 주면 모음이 받는 목록이 같다."""
    flow = fan_flow()
    inputs = Inputs(count=5)
    forward = segments_of(flow, inputs, Adapters())
    fan = flow.fanouts["spread"]
    view = {"prepare": StepOutput(data={"count": 5})}
    reverse: dict[str, SegmentEnded] = {}
    for segment in reversed(fan.plan(inputs, view)):
        reverse[segment_key_sha256(segment.key)] = fan.run(inputs, Adapters(), view, segment, StepContext(resume=None))
    adapters = Adapters()
    again = segments_of(flow, inputs, adapters, segments_done={"spread": reverse})
    assert again == forward
    assert adapters.calls == []


# ── T4 끝난 구획 건너뛰기 ─────────────────────────────────────────────


def test_ended_segments_are_not_run_again() -> None:
    events = Recorder()
    adapters = Adapters()
    ended: dict[str, SegmentEnded] = {
        segment_key_sha256(key_at(2)): SegmentOutput(data={"square": 4}),
        segment_key_sha256(key_at(4)): SegmentOutput(data={"square": 16}),
        segment_key_sha256(key_at(5)): SegmentFailure(error_code="made_up_code"),
    }
    got = segments_of(
        fan_flow(), Inputs(count=5), adapters, events=events, segment_events=events, segments_done={"spread": ended}
    )
    assert adapters.calls == [1, 3]
    assert len(got) == 5
    assert [s["status"] for s in got] == ["done", "done", "done", "done", "failed"]
    assert got[4]["errorCode"] == "made_up_code"
    assert got[4]["data"] is None
    assert events.count("seg_started") == 2
    assert events.count("seg_failed") == 0
    assert [e[2:4] for e in events.seen if e[0] == "progress"] == [(4, 5), (5, 5)]


def test_an_ended_segment_outside_the_plan_is_a_plan_mismatch() -> None:
    stray = SegmentKey(kind="block", span="b99", document_sha256=None, parser_version=None)
    with pytest.raises(SegmentPlanMismatch):
        run_flow(
            fan_flow(),
            Inputs(count=2),
            Adapters(),
            segments_done={"spread": {segment_key_sha256(stray): SegmentOutput(data={})}},
        )


def test_segments_done_for_a_barrier_step_is_refused_before_any_step() -> None:
    adapters = Adapters()
    with pytest.raises(FlowInputError):
        run_flow(fan_flow(), Inputs(count=2), adapters, segments_done={"prepare": {}})
    assert adapters.calls == []


# ── T5 실패 정책 ─────────────────────────────────────────────────────


def test_fail_run_stops_at_the_first_failure_and_fails_the_step() -> None:
    events = Recorder()
    adapters = Adapters()
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(
            fan_flow(on_failure="fail_run"),
            Inputs(count=5, fail_at=frozenset({3})),
            adapters,
            events=events,
            segment_events=events,
        )
    assert caught.value.step == "spread"
    assert isinstance(caught.value.__cause__, SegmentsFailed)
    assert adapters.calls == [1, 2, 3]  # R3: 남은 구획 4·5 는 부르지 않는다
    assert events.count("seg_failed") == 1
    assert ("failed", "spread") in [e[:2] for e in events.seen]
    assert set(caught.value.completed) == {"prepare"}


def test_pass_to_gather_runs_everything_and_gathers_the_failure_with_its_code() -> None:
    events = Recorder(failed_code="made_up_code")
    adapters = Adapters()
    got = segments_of(
        fan_flow(on_failure="pass_to_gather"),
        Inputs(count=5, fail_at=frozenset({3})),
        adapters,
        events=events,
        segment_events=events,
    )
    assert adapters.calls == [1, 2, 3, 4, 5]
    assert [s["status"] for s in got] == ["done", "done", "failed", "done", "done"]
    assert got[2]["errorCode"] == "made_up_code"
    assert got[2]["data"] is None
    assert ("seg_failed", "b3", "ValueError") in events.seen


def test_without_segment_events_a_failed_segment_gets_step_error() -> None:
    got = segments_of(fan_flow(), Inputs(count=2, fail_at=frozenset({1})), Adapters())
    assert got[0]["errorCode"] == "step_error"


class Transient(Exception):
    """받는 쪽이 「잠깐 오류」로 다시 던지는 예외(지어낸 것)."""


def test_a_receiver_that_rethrows_gets_its_exception_out_of_run_flow_unwrapped() -> None:
    events = Recorder()
    events.raise_on["failed"] = Transient("다시")
    adapters = Adapters()
    with pytest.raises(Transient):
        run_flow(fan_flow(), Inputs(count=5, fail_at=frozenset({2})), adapters, events=events, segment_events=events)
    assert adapters.calls == [1, 2]
    assert events.count("failed") == 0  # step_failed 를 거치지 않는다


@pytest.mark.parametrize("what", ["planned", "started", "finished", "progress"])
def test_any_segment_receiver_exception_goes_out_unwrapped(what: str) -> None:
    events = Recorder()
    events.raise_on[what] = Transient(what)
    with pytest.raises(Transient):
        run_flow(fan_flow(), Inputs(count=3), Adapters(), events=events, segment_events=events)
    assert events.count("failed") == 0
    assert events.count("seg_failed") == 0


def test_a_segment_mismatch_from_the_receiver_goes_out_unwrapped() -> None:
    events = Recorder()
    events.raise_on["planned"] = SegmentPlanMismatch("다른 계획")
    with pytest.raises(SegmentPlanMismatch):
        run_flow(fan_flow(), Inputs(count=3), Adapters(), events=events, segment_events=events)


def test_a_checkpoint_inside_a_segment_fails_that_segment() -> None:
    events = Recorder()
    got = segments_of(
        fan_flow(), Inputs(count=3, checkpoint_at=frozenset({2})), Adapters(), events=events, segment_events=events
    )
    assert [s["status"] for s in got] == ["done", "failed", "done"]
    assert ("seg_failed", "b2", "FlowOutputError") in events.seen


# ── T6 계획·크기·결과 검사 ────────────────────────────────────────────


def flow_with_plan(planned: tuple[Segment, ...], **kwargs: object) -> Flow:
    def fixed(inputs: Inputs, carried: Carried) -> tuple[Segment, ...]:
        return planned

    values: dict[str, object] = {"on_failure": "pass_to_gather", "allow_empty": True, "max_segments": 3}
    values.update(kwargs)
    return declare(
        FlowStep(name="prepare", run=prepare),
        fanout(plan=fixed, **values),
        FlowStep(name="gather", run=gather),
    )


def cause_of(flow: Flow, adapters: Adapters | None = None) -> BaseException | None:
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(flow, Inputs(count=0), adapters or Adapters())
    assert caught.value.step == "spread"
    return caught.value.__cause__


def test_overlapping_keys_fail_the_step_before_any_segment() -> None:
    adapters = Adapters()
    cause = cause_of(flow_with_plan((Segment(key=key_at(1), input={"n": 1}),) * 2), adapters)
    assert isinstance(cause, FlowOutputError)
    assert "겹친다" in str(cause)
    assert adapters.calls == []


def test_more_segments_than_the_maximum_fail_the_step() -> None:
    planned = tuple(Segment(key=key_at(n), input={"n": n}) for n in range(1, 5))
    assert isinstance(cause_of(flow_with_plan(planned, max_segments=3)), FlowOutputError)


@pytest.mark.parametrize(
    "key",
    [
        SegmentKey(kind="Block", span="b1", document_sha256=None, parser_version=None),
        SegmentKey(kind="b" * 33, span="b1", document_sha256=None, parser_version=None),
        SegmentKey(kind="block", span="", document_sha256=None, parser_version=None),
        SegmentKey(kind="block", span="s" * 201, document_sha256=None, parser_version=None),
        SegmentKey(kind="block", span="b1", document_sha256="", parser_version=None),
        SegmentKey(kind="block", span="b1", document_sha256="D" * 64, parser_version=None),  # 대문자·꼴 밖
        SegmentKey(kind="block", span="b1", document_sha256=None, parser_version="p 1"),  # 빈칸
        SegmentKey(kind="block", span="b1", document_sha256=None, parser_version="p" * 65),
    ],
)
def test_a_key_of_the_wrong_shape_fails_the_step(key: SegmentKey) -> None:
    assert isinstance(cause_of(flow_with_plan((Segment(key=key, input={}),))), FlowOutputError)


def test_a_segment_input_that_does_not_round_trip_fails_the_step() -> None:
    assert isinstance(cause_of(flow_with_plan((Segment(key=key_at(1), input={"n": {1, 2}}),))), FlowOutputError)


def test_zero_segments_with_allow_empty_gathers_an_empty_list() -> None:
    events = Recorder()
    flow = flow_with_plan((), allow_empty=True)
    got = segments_of(flow, Inputs(count=0), Adapters(), events=events, segment_events=events)
    assert got == []
    assert ("planned", "spread", ()) in events.seen


def test_zero_segments_without_allow_empty_fails_with_segments_empty() -> None:
    assert isinstance(cause_of(flow_with_plan((), allow_empty=False)), SegmentsEmpty)


def test_a_segment_over_the_size_limit_fails_that_segment() -> None:
    events = Recorder()
    got = segments_of(
        fan_flow(), Inputs(count=2, big_at=frozenset({2})), Adapters(), events=events, segment_events=events
    )
    assert [s["status"] for s in got] == ["done", "failed"]
    assert ("seg_failed", "b2", "FlowOutputError") in events.seen


def test_a_fanout_whose_total_data_is_over_the_limit_fails_the_step() -> None:
    each = SEGMENT_DATA_MAX_OCTETS - 1024
    count = FANOUT_DATA_MAX_OCTETS // each + 1

    def wide(inputs: Inputs, adapters: Adapters, carried: Carried, segment: Segment, ctx: StepContext) -> SegmentOutput:
        return SegmentOutput(data={"pad": "x" * each})

    planned = tuple(Segment(key=key_at(n), input={"n": n}) for n in range(1, count + 1))
    cause = cause_of(flow_with_plan(planned, run=wide, max_segments=count))
    assert isinstance(cause, FlowOutputError)
    assert "바이트를 넘는다" in str(cause)


def test_a_result_check_that_raises_fails_the_last_step() -> None:
    seen: list[int] = []

    def refuse(results: tuple[dict[str, object], ...]) -> None:
        seen.append(len(results))
        raise ValueError("공통 칸이 없다")

    with pytest.raises(FlowStepFailed) as caught:
        run_flow(fan_flow(result_checks=(refuse,)), Inputs(count=2), Adapters())
    assert caught.value.step == "gather"
    assert isinstance(caught.value.__cause__, FlowOutputError)
    assert seen == [1]


def test_a_result_check_that_passes_changes_nothing() -> None:
    def accept(results: tuple[dict[str, object], ...]) -> None:
        return None

    assert segments_of(fan_flow(result_checks=(accept,)), Inputs(count=2), Adapters()) == segments_of(
        fan_flow(), Inputs(count=2), Adapters()
    )
