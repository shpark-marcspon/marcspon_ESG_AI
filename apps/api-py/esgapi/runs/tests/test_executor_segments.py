"""실행기의 펼침 단계(RM1a ③ — T11~T14)를 진짜 DB·가짜 모듈로 끝까지 잰다. 업무 층.

가짜 흐름은 이 시험의 레지스트리에만 단다(tasks.REGISTRY·tasks.BINDINGS 를 바꿔 끼움 — 제품 흐름 등록 0, 트랙 규칙
「RM1c 전까지 제품 흐름에 펼침 0」): `probe.segmented@1` prepare(장벽) → spread(펼침 — 구획마다 모의 LLM 한 번) →
gather(모음 장벽). 정책만 다른 판 둘(`probe.segfail@1` fail_run · `probe.segempty@1` allow_empty=False)과 장벽만인
`probe.plain@1`. 호출 기록은 DB 싱크(비용은 모의 모델 단가 — 0 이 아님을 줄마다 단언). 값은 지어낸 것이다.
"""

import contextlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import pytest

from esgapi.config.env import JobSettings
from esgapi.core.flows.binding import BindingRegistry, DocumentInput, RunContext, RunRetryLater
from esgapi.core.flows.registry import REGISTRY, FlowRegistry, make_flow
from esgapi.core.flows.types import (
    Carried,
    FanoutStep,
    Flow,
    FlowStep,
    Segment,
    SegmentFailurePolicy,
    SegmentKey,
    SegmentOutput,
    StepContext,
    StepOutput,
    segment_key_sha256,
)
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sink_db import DbSink
from esgapi.core.llm.types import Tags
from esgapi.core.models import DocumentRow, LlmCallLogRow
from esgapi.core.service.selectors.llm_usage import usage_by_run, usage_by_segment
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs import context, tasks
from esgapi.runs.models import RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.services import runs as services
from esgapi.runs.service.services.runs import RunUpdateError
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7 (synthetic bytes for the segmented runner)"
NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
SOFT_S = 240
LATE = 10_000.0
COUNT = 20
PER_CALL_USD = Decimal("0.00014")  # 모의 모델 단가(input 1.0·output 2.0 /Mtok) × 가상 사용량 100/20


@dataclass
class Script:
    count: int = COUNT
    hooks: dict[int, Callable[[], None]] = field(default_factory=dict[int, Callable[[], None]])
    called: list[int] = field(default_factory=list[int])
    gather_calls: bool = False  # 모음 단계에서도 모의 호출 한 번(구획 밖 줄 — segment NULL)
    after_prepare: Callable[[], None] | None = None  # prepare 를 끝내기 전에 부름(시도를 그 단계 뒤에서 끊을 때)


@dataclass(frozen=True, slots=True)
class Inputs:
    document: DocumentInput


@dataclass(frozen=True, slots=True)
class Adapters:
    script: Script
    ctx: RunContext


def prepare(inputs: Inputs, adapters: Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    if adapters.script.after_prepare is not None:
        adapters.script.after_prepare()
    return StepOutput(data={"count": adapters.script.count})


def plan(inputs: Inputs, carried: Carried) -> tuple[Segment, ...]:
    count = cast("int", carried["prepare"].data["count"])
    return tuple(Segment(key=key_at(n, SHIFT[0]), input={"n": n}) for n in range(1, count + 1))


SHIFT = [""]  # plan 은 adapters 를 받지 않는다 — 시험이 바꾸는 계획의 꼬리


def key_at(n: int, shift: str = "") -> SegmentKey:
    return SegmentKey(kind="block", span=f"b{n}{shift}", document_sha256=None, parser_version="p1")


def call_llm(ctx: RunContext, company_id: int) -> None:
    client = ctx.llm()
    mock = client.provider("mock")
    assert isinstance(mock, MockProvider)
    mock.enqueue_text("구획 판정")
    client.call(
        CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags(str(company_id), "probe"))
    )


def spread(inputs: Inputs, adapters: Adapters, carried: Carried, segment: Segment, ctx: StepContext) -> SegmentOutput:
    n = cast("int", segment.input["n"])
    adapters.script.called.append(n)
    call_llm(adapters.ctx, adapters.ctx.company_id)
    hook = adapters.script.hooks.get(n)
    if hook is not None:
        hook()
    return SegmentOutput(data={"square": n * n})


def gather(inputs: Inputs, adapters: Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    if adapters.script.gather_calls:
        call_llm(adapters.ctx, adapters.ctx.company_id)
    segments: object = carried["spread"].data["segments"] if "spread" in carried else None
    return StepOutput(data={"results": [{"schemaVersion": "probe.segmented-result@1", "segments": segments}]})


def plain_judge(inputs: Inputs, adapters: Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    call_llm(adapters.ctx, adapters.ctx.company_id)
    return StepOutput(data={"results": [{"schemaVersion": "probe.segmented-result@1", "segments": []}]})


def segmented(flow_id: str, *, on_failure: SegmentFailurePolicy = "pass_to_gather", allow_empty: bool = True) -> Flow:
    return make_flow(
        module="probe",
        id=flow_id,
        input_shape="probe.document@1",
        inputs=Inputs,
        adapters=Adapters,
        result_shapes=("probe.segmented-result@1",),
        steps=(
            FlowStep(name="prepare", run=prepare),
            FanoutStep(
                name="spread", plan=plan, run=spread, on_failure=on_failure, allow_empty=allow_empty, max_segments=100
            ),
            FlowStep(name="gather", run=gather),
        ),
    )


SEGMENTED = segmented("probe.segmented@1")
FAIL_RUN = segmented("probe.segfail@1", on_failure="fail_run")
NO_EMPTY = segmented("probe.segempty@1", allow_empty=False)
PLAIN = make_flow(
    module="probe",
    id="probe.plain@1",
    input_shape="probe.document@1",
    inputs=Inputs,
    adapters=Adapters,
    result_shapes=("probe.segmented-result@1",),
    steps=(FlowStep(name="prepare", run=prepare), FlowStep(name="gather", run=plain_judge)),
)
FLOWS = (SEGMENTED, FAIL_RUN, NO_EMPTY, PLAIN)


class Binding:
    def __init__(self, script: Script) -> None:
        self.script = script

    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object:
        return Inputs(document=document)

    def adapters(self, ctx: RunContext) -> object:
        return Adapters(script=self.script, ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {}


class RetryAsked(Exception):
    pass


@dataclass
class World:
    storage: FakeStorage
    company_id: int
    script: Script
    mono: float = 0.0
    retries: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def retry(self, **kwargs: Any) -> RetryAsked:
        self.retries.append(kwargs)
        return RetryAsked()

    def late(self) -> None:
        self.mono += LATE


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    SHIFT[0] = ""
    made = World(FakeStorage(), companies[0], Script())
    plug_storage(monkeypatch, made.storage, max_upload_bytes=1000)
    flows = FlowRegistry()
    bindings = BindingRegistry()
    for flow in FLOWS:
        flows.register(flow)
        bindings.register(flow.id, Binding(made.script))
    sink = DbSink()
    monkeypatch.setattr(tasks, "REGISTRY", flows)
    monkeypatch.setattr(tasks, "BINDINGS", bindings)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "clock", lambda: NOW)
    monkeypatch.setattr(tasks, "monotonic", lambda: made.mono)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: SOFT_S)
    monkeypatch.setattr(tasks, "segment_parallel", lambda: 1)  # RM1b: 이 파일은 RM1a 직렬(상한 1 — 쪽지 0)을 잰다
    monkeypatch.setattr(context, "call_sink", lambda: sink)
    return made


def new_run(world: World, flow: Flow = SEGMENTED, *, resumed_from: int | None = None) -> int:
    company = world.company_id
    key = f"companies/{company}/documents/seg-{len(world.storage.objects)}/original"
    etag = world.storage.put(key, PDF)
    document = DocumentRow.for_company(company).create(
        company_id=company,
        uploaded_by="1",
        file_name="지은 문서.pdf",
        storage_key=key,
        size_bytes=len(PDF),
        etag=etag,
        status="uploaded",
    )
    run = RunRow.for_company(company).create(
        company_id=company,
        document_id=document.pk,
        module="probe",
        flow_id=flow.id,
        versions={"flow": flow.id},
        status="queued",
        created_by_user_id=7,
        resumed_from_run_id=resumed_from,
    )
    for position, name in enumerate(flow.steps):
        RunStepRow.for_company(company).create(
            company_id=company, run_id=run.pk, name=name, position=position, status="pending"
        )
    return run.pk


def execute(world: World, run_id: int) -> None:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(world.company_id), run_id=str(run_id))


def run_row(world: World, run_id: int) -> RunRow:
    found = RunRow.for_company(world.company_id).filter(pk=run_id).first()
    assert found is not None
    return found


def segment_statuses(world: World, run_id: int) -> list[str]:
    return list(
        RunSegmentRow.for_company(world.company_id)
        .filter(run_id=run_id)
        .order_by("position")
        .values_list("status", flat=True)
    )


def calls(world: World, run_id: int) -> list[LlmCallLogRow]:
    return list(LlmCallLogRow.for_company(world.company_id).filter(run_id=run_id).order_by("id"))


def spread_step(world: World, run_id: int) -> RunStepRow:
    found = RunStepRow.for_company(world.company_id).filter(run_id=run_id, name="spread").first()
    assert found is not None
    return found


# ── T11 끝까지 ─────────────────────────────────────────────────────────


def test_twenty_segments_end_done_with_a_row_and_a_call_each(world: World) -> None:
    run_id = new_run(world)
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.error_code) == ("done", None)
    assert segment_statuses(world, run_id) == ["done"] * COUNT
    step = spread_step(world, run_id)
    assert (step.status, step.done, step.total) == ("done", COUNT, COUNT)
    data = step.data or {}
    segments = cast("list[dict[str, object]]", data["segments"])
    assert [s["status"] for s in segments] == ["done"] * COUNT
    assert [cast("dict[str, object]", s["data"])["square"] for s in segments] == [n * n for n in range(1, COUNT + 1)]
    logged = calls(world, run_id)
    assert [r.segment for r in logged] == [segment_key_sha256(key_at(n)) for n in range(1, COUNT + 1)]
    assert {r.step for r in logged} == {"spread"}
    rows = RunSegmentRow.for_company(world.company_id).filter(run_id=run_id)
    assert {r.attempts for r in rows} == {1}


# ── T12 이어 돌기: 끝난 구획을 다시 부르지 않는다(호출 수·0 아닌 비용) ──────────────


def test_after_a_deadline_the_next_attempt_skips_the_ended_segments(world: World) -> None:
    world.script.hooks[7] = world.late  # 7번째 구획을 끝내고 적은 뒤 마감
    run_id = new_run(world)
    execute(world, run_id)
    assert (run_row(world, run_id).status, len(world.retries)) == ("queued", 1)  # 시도 1 RunDeferred
    assert segment_statuses(world, run_id) == ["done"] * 7 + ["pending"] * (COUNT - 7)
    assert world.script.called == list(range(1, 8))
    world.script.hooks.clear()
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.attempts, run.stalled_attempts) == ("done", 2, 0)
    assert world.script.called == list(range(1, COUNT + 1))  # 1~7 은 시도 2 가 부르지 않았다
    logged = calls(world, run_id)
    assert len(logged) == COUNT  # 모의 호출 수 = 구획 수(다시 부른 것 0)
    for line in logged:
        assert line.cost_usd is not None and line.cost_usd > 0  # 0 = 0 으로 지나가지 않게(★14)
    assert {line.cost_usd for line in logged} == {PER_CALL_USD}
    total = usage_by_run(company_id=world.company_id, run_ids=frozenset({run_id}))[run_id]
    assert total.cost_usd == PER_CALL_USD * COUNT  # 재시도를 합친 지출 = 한 번 몫
    by_segment = usage_by_segment(company_id=world.company_id, run_id=run_id, fanout_steps=frozenset({"spread"}))
    assert by_segment.recorded is True
    assert len(by_segment.by_segment) == COUNT
    assert all(u.cost_usd == PER_CALL_USD for u in by_segment.by_segment.values())


# ── T13 1차 0 변화 ─────────────────────────────────────────────────────


def test_a_barrier_flow_writes_no_segment_rows_and_null_segment_calls(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    planned: list[object] = []
    real = services.segments_planned

    def spy(**kwargs: Any) -> Any:
        planned.append(kwargs["step"])
        return real(**kwargs)

    monkeypatch.setattr(services, "segments_planned", spy)
    run_id = new_run(world, PLAIN)
    execute(world, run_id)
    assert planned == []  # 장벽 흐름에는 구획 사건 0
    assert run_row(world, run_id).status == "done"
    assert RunSegmentRow.for_company(world.company_id).filter(run_id=run_id).count() == 0
    logged = calls(world, run_id)
    assert len(logged) == 1  # 분모
    assert [r.segment for r in logged] == [None]


def test_every_product_flow_is_barrier_only_but_the_g1_engine() -> None:
    """트랙 규칙: 제품 레지스트리의 펼침 흐름은 그린워싱 2차 엔진 하나뿐(GE1b ③ — 실행 시작은 스위치, 기본 꺼짐)."""
    flows = [flow for module in REGISTRY.modules() for flow in REGISTRY.flows_of(module)]
    assert len(flows) >= 5  # 분모: 1차 흐름이 실제로 잡혔다
    assert {flow.id for flow in flows if set(flow.step_kinds) != {"barrier"}} == {"greenwash.engine@G1"}
    assert {flow.id for flow in flows if flow.fanouts or flow.result_checks} == {"greenwash.engine@G1"}


# ── T14 실패 정책·잠깐 오류·계획 불일치 ───────────────────────────────


def raise_transient() -> None:
    raise RunRetryLater("저장소에 잠깐 닿지 못함(지어낸 것)")


def raise_permanent() -> None:
    raise ValueError("구획 판정이 깨졌다(지어낸 것)")


def test_a_transient_segment_error_is_not_a_failure_and_the_next_attempt_calls_it_again(world: World) -> None:
    world.script.count = 3
    world.script.hooks[2] = raise_transient
    run_id = new_run(world)
    execute(world, run_id)
    assert (run_row(world, run_id).status, len(world.retries)) == ("queued", 1)
    assert segment_statuses(world, run_id) == ["done", "running", "pending"]  # failed 아님
    world.script.hooks.clear()
    execute(world, run_id)
    assert run_row(world, run_id).status == "done"
    assert world.script.called == [1, 2, 2, 3]  # 2 만 다시
    assert RunSegmentRow.for_company(world.company_id).get(run_id=run_id, position=1).attempts == 2


def test_a_permanent_failure_with_fail_run_fails_the_run_on_the_fanout_step(world: World) -> None:
    world.script.count = 5
    world.script.hooks[3] = raise_permanent
    run_id = new_run(world, FAIL_RUN)
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "segments_failed", "spread")
    assert world.script.called == [1, 2, 3]  # R3: 남은 구획은 부르지 않는다
    assert segment_statuses(world, run_id) == ["done", "done", "failed", "pending", "pending"]
    failed = RunSegmentRow.for_company(world.company_id).get(run_id=run_id, position=2)
    assert failed.error_code == "step_error"  # 표 밖 예외(ValueError)는 step_error — 빈 글이 아니다


def test_fail_run_with_a_failed_segment_from_an_earlier_attempt_fails_without_calling_it(world: World) -> None:
    """앞 시도가 구획을 failed 로 적고 단계 실패를 적기 전에 끊겼다(검증 ① R-a): 다음 시도는 끝난 failed 를 받아
    부르지 않고 segments_failed."""
    world.script.count = 5

    def fail_then_late() -> None:
        world.late()
        raise_permanent()

    world.script.hooks[3] = fail_then_late
    run_id = new_run(world, FAIL_RUN)
    execute(world, run_id)
    assert (run_row(world, run_id).status, len(world.retries)) == ("queued", 1)  # 실패를 적은 뒤 마감
    assert segment_statuses(world, run_id)[:3] == ["done", "done", "failed"]
    run = run_row(world, run_id)
    assert (run.progress_attempt, run.stalled_attempts) == (1, 0)  # 구획 실패도 진행(검증 ② R-a)
    world.script.hooks.clear()
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "segments_failed", "spread")
    assert world.script.called == [1, 2, 3]  # 시도 2 는 아무 구획도 부르지 않았다


def test_pass_to_gather_failure_then_deadline_the_next_attempt_does_not_call_it_again(world: World) -> None:
    world.script.count = 4

    def fail_then_late() -> None:
        world.late()
        raise_permanent()

    world.script.hooks[2] = fail_then_late
    run_id = new_run(world)
    execute(world, run_id)
    assert run_row(world, run_id).status == "queued"
    world.script.hooks.clear()
    execute(world, run_id)
    assert run_row(world, run_id).status == "done"
    assert world.script.called == [1, 2, 3, 4]  # 호출 수 고정 — 2 는 다시 안 부름
    assert len(calls(world, run_id)) == 4
    data = spread_step(world, run_id).data or {}
    segments = cast("list[dict[str, object]]", data["segments"])
    assert [(s["status"], s["errorCode"]) for s in segments] == [
        ("done", None),
        ("failed", "step_error"),
        ("done", None),
        ("done", None),
    ]


def test_a_different_plan_on_the_next_attempt_fails_with_segments_mismatch(world: World) -> None:
    world.script.count = 4
    world.script.hooks[2] = world.late
    run_id = new_run(world)
    execute(world, run_id)
    assert run_row(world, run_id).status == "queued"
    SHIFT[0] = "x"  # 결정적이지 않은 plan
    world.script.hooks.clear()
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "segments_mismatch", None)
    assert world.script.called == [1, 2]
    assert RunSegmentRow.for_company(world.company_id).filter(run_id=run_id).count() == 4  # 새 계획은 쓰지 않았다


def test_zero_segments_without_allow_empty_fails_with_segments_empty(world: World) -> None:
    world.script.count = 0
    run_id = new_run(world, NO_EMPTY)
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "segments_empty", "spread")


def test_zero_segments_with_allow_empty_gathers_an_empty_list(world: World) -> None:
    """계획됨 0(검증 ② R-c): 행 0 — 단계는 done 이고 모음은 빈 목록을 받는다."""
    world.script.count = 0
    run_id = new_run(world)
    execute(world, run_id)
    assert run_row(world, run_id).status == "done"
    assert RunSegmentRow.for_company(world.company_id).filter(run_id=run_id).count() == 0
    assert (spread_step(world, run_id).data or {}) == {"segments": []}


def test_an_update_error_on_segment_finished_fails_the_run_internal_not_the_segment(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(**kwargs: Any) -> Any:
        raise RunUpdateError("run_segments 의 갱신이 0행이다(지어낸 것)")

    monkeypatch.setattr(services, "segment_finished", broken)
    world.script.count = 3
    run_id = new_run(world)
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "internal", None)
    assert segment_statuses(world, run_id) == ["running", "pending", "pending"]  # 구획 실패로 접지 않았다
    assert world.script.called == [1]


def test_a_call_after_the_fanout_carries_no_segment(world: World) -> None:
    """구획 끝에 커서의 구획을 비운다(검증 ③ 권고): 모음 단계의 호출 줄은 step gather · segment NULL."""
    world.script.count = 2
    world.script.gather_calls = True
    run_id = new_run(world)
    execute(world, run_id)
    assert run_row(world, run_id).status == "done"
    assert [(r.step, r.segment) for r in calls(world, run_id)] == [
        ("spread", segment_key_sha256(key_at(1))),
        ("spread", segment_key_sha256(key_at(2))),
        ("gather", None),
    ]


def test_an_attempt_whose_only_ending_is_a_failed_segment_has_progressed(world: World) -> None:
    """구획 실패도 진행이다(검증 ② R-a·③ 블로커): 시도 1 은 prepare 를 끝낸 뒤 끊고, 시도 2 의 끝남은 구획 1 의 실패
    하나뿐이다 — 그 시도가 진행 없는 시도(stalled)로 세지 않고 progress_attempt = 2."""
    world.script.count = 3
    world.script.after_prepare = world.late  # prepare 의 끝은 적히고, 다음 사건(spread 시작)의 울타리에서 접힌다
    run_id = new_run(world)
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.progress_attempt, run.stalled_attempts) == ("queued", 1, 0)
    assert world.script.called == []
    world.script.after_prepare = None

    def fail_then_late() -> None:
        world.late()
        raise_permanent()

    world.script.hooks[1] = fail_then_late
    execute(world, run_id)
    run = run_row(world, run_id)
    assert (run.status, run.attempts, run.progress_attempt, run.stalled_attempts) == ("queued", 2, 2, 0)
    assert segment_statuses(world, run_id) == ["failed", "pending", "pending"]


def test_a_resumed_run_plans_its_fanout_from_scratch(world: World) -> None:
    """resumeFromRunId 로 이어 돈 실행(리뷰 M1 — 발주서 2-5 무효 조건): 앞 실행의 구획을 옮기지 않는다. 새 실행의
    run_segments 는 처음부터 생기고 구획 호출 수 = 전체(앞 실행에서 끝난 구획도 다시 부른다 — 옮김은 RM1c)."""
    world.script.count = 5
    world.script.hooks[3] = raise_permanent
    first = new_run(world, FAIL_RUN)
    execute(world, first)
    assert (run_row(world, first).status, world.script.called) == ("failed", [1, 2, 3])
    world.script.hooks.clear()
    world.script.called.clear()
    second = new_run(world, FAIL_RUN, resumed_from=first)
    # 이어 돌기는 끝난 장벽 단계(prepare)를 옮긴다(실행 만들기의 꼴을 손으로) — 펼침은 옮기지 않는다
    prepared = RunStepRow.for_company(world.company_id).get(run_id=first, name="prepare")
    RunStepRow.for_company(world.company_id).filter(run_id=second, name="prepare").update(
        status="done", data=prepared.data
    )
    execute(world, second)
    assert run_row(world, second).status == "done"
    assert world.script.called == [1, 2, 3, 4, 5]  # 앞 실행의 done 1·2 도 다시 부름
    assert segment_statuses(world, second) == ["done"] * 5
    assert len(calls(world, second)) == 5
    assert segment_statuses(world, first) == ["done", "done", "failed", "pending", "pending"]  # 앞 실행 그대로
