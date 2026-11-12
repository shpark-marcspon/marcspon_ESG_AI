"""실행기의 구획 쪽지(RM1b ③ — T11~T15)를 진짜 DB·가짜 모듈·가짜 브로커로 끝까지 잰다. 업무 층.

가짜 흐름·끼움은 RM1a 시험(test_executor_segments.py)의 것을 그대로 쓴다(`probe.segmented@1` 등 — 시험 레지스트리에만,
제품 흐름 등록 0). 가짜 브로커는 `queue.enqueue_segment`·`queue.enqueue_run` 을 바꿔 끼워 쪽지를 차례로 모으고, 시험이
쪽지를 하나씩 태스크 몸(`execute_segment`·`execute_run`)에 넣는다(워커·스레드 0 — 진짜 엇갈림은 밖, Q8).
시계(tasks.clock)는 시험이 움직인다(임대가 지난 구획의 이어받기). 값은 지어낸 것이다.
"""

import contextlib
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from django.core.management import call_command
from django.db import transaction

from esgapi.config.env import BrokerSettings
from esgapi.core.flows.binding import (
    BindingRegistry,
    DocumentInput,
    RunOptionsRejected,
    RunRetryLater,
    RunVersionsMismatch,
)
from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import FlowInputError, segment_key_sha256
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError, PromptError
from esgapi.core.llm.sink_db import DbSink
from esgapi.core.resources import queue
from esgapi.core.resources.ports.storage import StorageUnavailable
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs import context, tasks
from esgapi.runs.management.commands import requeue_runs
from esgapi.runs.models import RunResultRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.services import runs as services
from esgapi.runs.service.services.runs import EndDone, NothingToClaim, RunUpdateError, SegmentClaimed, Superseded
from esgapi.runs.tests.test_executor_segments import (
    COUNT,
    FAIL_RUN,
    FLOWS,
    NO_EMPTY,
    NOW,
    PLAIN,
    SETTINGS,
    SHIFT,
    SOFT_S,
    Binding,
    RetryAsked,
    Script,
    World,
    calls,
    key_at,
    new_run,
    run_row,
    segment_statuses,
    spread_step,
)
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

PARALLEL = 3
POLICIES = {"spread": "pass_to_gather"}
BROKER = BrokerSettings(  # 지어낸 로컬 흉내 값(쪽지는 가짜 브로커가 모은다 — 보내지 않는다)
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-runs",
    queue_url="http://queue:9324/q",
    secure=False,
)


class FailingBinding(Binding):
    """끼움의 입력 짓기가 시험이 고른 때부터 던진다(주차 뒤 쪽지 쪽만 — 앞 갈래 표의 끼움 줄)."""

    def __init__(self, script: Script, fail: list[Exception]) -> None:
        super().__init__(script)
        self.fail = fail

    def inputs(self, document: DocumentInput, options: Any) -> object:
        if self.fail:
            raise self.fail[0]
        return super().inputs(document, options)


@dataclass
class Par(World):
    """World + 시계·가짜 브로커(쪽지는 (종류, kwargs) — countdown 은 kwargs 에 남는다)·상한."""

    now: datetime = NOW
    notes: list[tuple[str, dict[str, Any]]] = field(default_factory=list[tuple[str, dict[str, Any]]])
    parallel: int = PARALLEL
    binding_fail: list[Exception] = field(default_factory=list[Exception])
    woken: int = 0  # 넣은 지휘 쪽지 수(깨우기)

    def segment_notes(self) -> list[dict[str, Any]]:
        return [kw for kind, kw in self.notes if kind == "segment"]

    def wakes(self) -> int:
        return sum(1 for kind, _ in self.notes if kind == "run")


def _world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], parallel: int) -> Par:
    SHIFT[0] = ""
    made = Par(FakeStorage(), companies[0], Script(), parallel=parallel)
    plug_storage(monkeypatch, made.storage, max_upload_bytes=1000)
    flows = FlowRegistry()
    bindings = BindingRegistry()
    for flow in FLOWS:
        flows.register(flow)
        bindings.register(flow.id, FailingBinding(made.script, made.binding_fail))
    sink = DbSink()
    sent: list[tuple[str, dict[str, Any]]] = []
    made.notes = sent
    monkeypatch.setattr(tasks, "REGISTRY", flows)
    monkeypatch.setattr(tasks, "BINDINGS", bindings)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "clock", lambda: made.now)
    monkeypatch.setattr(tasks, "monotonic", lambda: made.mono)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: SOFT_S)
    monkeypatch.setattr(tasks, "segment_parallel", lambda: made.parallel)
    monkeypatch.setattr(context, "call_sink", lambda: sink)

    def segment_note(**kw: Any) -> None:
        sent.append(("segment", kw))

    def run_note(**kw: Any) -> None:
        sent.append(("run", kw))

    monkeypatch.setattr(queue, "enqueue_segment", segment_note)
    monkeypatch.setattr(queue, "enqueue_run", run_note)
    return made


@pytest.fixture
def par(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> Par:
    return _world(monkeypatch, companies, PARALLEL)


@pytest.fixture
def make_world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> Callable[[int], Par]:
    return lambda parallel: _world(monkeypatch, companies, parallel)


def execute(world: Par, run_id: int) -> None:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(world.company_id), run_id=str(run_id))


def deliver(world: Par, kind: str, kw: dict[str, Any]) -> None:
    if kind == "run":
        world.woken += 1
        execute(world, int(kw["run_id"]))
        return
    note = {k: str(v) for k, v in kw.items() if k != "countdown"}
    tasks.execute_segment(world, **note)


def take_next(world: Par) -> None:
    kind, kw = world.notes.pop(0)
    deliver(world, kind, kw)


def drain(world: Par, *, rng: random.Random | None = None, limit: int = 400) -> int:
    """쪽지를 다 넣는다(rng 가 있으면 몰아 돌리는 차례를 섞는다). 넣은 쪽지 수를 돌려준다."""
    delivered = 0
    while world.notes:
        index = 0 if rng is None else rng.randrange(len(world.notes))
        kind, kw = world.notes.pop(index)
        deliver(world, kind, kw)
        delivered += 1
        assert delivered < limit, "쪽지가 끝나지 않는다"
    return delivered


def claim_directly(world: Par, run_id: int, attempt: int = 1) -> object:
    """쪽지 없이 잡기 블록 하나(시험이 쥔 채 버리는 쪽지)."""
    with transaction.atomic():
        return services.segment_claim(
            company_id=world.company_id,
            run_id=run_id,
            run_attempt=attempt,
            now=world.now,
            lease_s=SETTINGS.lease_s,
            parallel_max=world.parallel,
            max_attempts=SETTINGS.max_attempts,
            on_failure=POLICIES,
        )


def segment_rows(world: Par, run_id: int) -> list[RunSegmentRow]:
    return list(RunSegmentRow.for_company(world.company_id).filter(run_id=run_id).order_by("position"))


def results(world: Par, run_id: int) -> list[object]:
    return [r.body for r in RunResultRow.for_company(world.company_id).filter(run_id=run_id).order_by("position")]


# ── T11 상한 3 · 구획 20 ───────────────────────────────────────────────


def test_twenty_segments_with_cap_three_park_fan_out_and_wake_once(par: Par) -> None:
    run_id = new_run(par)
    execute(par, run_id)
    parked = run_row(par, run_id)
    assert (parked.status, parked.attempts) == ("processing", 1)
    assert parked.parked_at is not None
    assert (
        par.notes
        == [("segment", {"company_id": par.company_id, "run_id": run_id, "run_attempt": 1, "countdown": 0})] * PARALLEL
    )
    assert segment_statuses(par, run_id) == ["pending"] * COUNT
    assert par.script.called == []  # 지휘는 구획을 돌지 않는다

    fourth: list[object] = []
    # 쪽지 셋이 구획을 쥔 채(본문 안에서 다음 쪽지를 넣어) 넷째 잡기를 부른다 — 상한이 찼다(R9)
    par.script.hooks = {
        1: lambda: take_next(par),
        2: lambda: take_next(par),
        3: lambda: fourth.append(claim_directly(par, run_id)),
    }
    take_next(par)
    assert fourth == [NothingToClaim(wake=False)]
    assert par.wakes() == 0
    drain(par)
    assert par.woken == 1

    run = run_row(par, run_id)
    assert (run.status, run.error_code, run.attempts, run.parked_at) == ("done", None, 2, None)
    assert segment_statuses(par, run_id) == ["done"] * COUNT
    assert sorted(par.script.called) == list(range(1, COUNT + 1))  # 구획마다 한 번
    rows = segment_rows(par, run_id)
    assert {r.attempts for r in rows} == {1}
    assert {r.lease_expires_at for r in rows} == {None}
    step = spread_step(par, run_id)
    assert (step.status, step.done, step.total) == ("done", None, None)  # 병렬은 done/total 을 쓰지 않는다(R5)
    data = cast("dict[str, object]", step.data)
    squares = [cast("dict[str, object]", s["data"])["square"] for s in cast("list[dict[str, Any]]", data["segments"])]
    assert squares == [n * n for n in range(1, COUNT + 1)]  # 모음은 계획 차례
    logged = calls(par, run_id)
    assert len(logged) == COUNT
    assert sorted(r.segment or "" for r in logged) == sorted(segment_key_sha256(key_at(n)) for n in range(1, COUNT + 1))
    assert {r.step for r in logged} == {"spread"}
    assert all(r.cost_usd is not None and r.cost_usd > 0 for r in logged)


def test_the_conductor_is_woken_exactly_once(par: Par) -> None:
    run_id = new_run(par)
    execute(par, run_id)
    drain(par)
    assert par.woken == 1
    assert run_row(par, run_id).status == "done"


# ── T12 몰아 돌리는 차례 ──────────────────────────────────────────────


def test_three_shuffled_orders_and_the_serial_run_give_the_same_result(par: Par) -> None:
    par.parallel = 1
    serial = new_run(par)
    execute(par, serial)
    assert par.notes == []  # 상한 1 = RM1a 직렬(쪽지 0)
    assert run_row(par, serial).status == "done"
    expected = results(par, serial)
    assert expected and spread_step(par, serial).total == COUNT  # 직렬은 done/total 을 쓴다

    par.parallel = PARALLEL
    for seed in (11, 23, 37):
        run_id = new_run(par)
        execute(par, run_id)
        drain(par, rng=random.Random(seed))  # noqa: S311  (정한 씨앗의 차례 섞기 — 암호 아님)
        assert run_row(par, run_id).status == "done", seed
        assert results(par, run_id) == expected, seed
        assert spread_step(par, run_id).data == spread_step(par, serial).data, seed


# ── T13 잃은 쪽지·이어받기·다시 온 쪽지 ───────────────────────────────


def test_a_segment_held_by_a_dead_note_is_retaken_after_its_lease(par: Par) -> None:
    par.script.count = 3
    par.parallel = 2
    run_id = new_run(par)
    execute(par, run_id)
    held = claim_directly(par, run_id)  # 쥔 채 죽은 쪽지
    assert isinstance(held, SegmentClaimed) and held.position == 0
    par.now += timedelta(seconds=SETTINGS.lease_s + 1)
    drain(par)
    assert run_row(par, run_id).status == "done"
    rows = segment_rows(par, run_id)
    assert [(r.status, r.attempts) for r in rows] == [("done", 2), ("done", 1), ("done", 1)]
    assert sorted(par.script.called) == [1, 2, 3]

    # 죽은 줄 알았던 첫 쪽지가 늦게 끝내려 한다 — 이미 끝난 실행이라 Superseded, 행 그대로
    with transaction.atomic():
        late = services.segment_end(
            company_id=par.company_id,
            run_id=run_id,
            run_attempt=1,
            step="spread",
            key_sha256=held.key_sha256,
            attempt=held.attempt,
            outcome=EndDone(data={"square": -1}),
            now=par.now,
            lease_s=SETTINGS.lease_s,
            parallel_max=2,
            on_failure="pass_to_gather",
        )
    assert late == Superseded()


def test_an_old_note_of_a_retaken_segment_cannot_write(par: Par) -> None:
    par.script.count = 2
    par.parallel = 2
    run_id = new_run(par)
    execute(par, run_id)
    old = claim_directly(par, run_id)
    assert isinstance(old, SegmentClaimed)
    par.now += timedelta(seconds=SETTINGS.lease_s + 1)
    par.notes.clear()
    retaken = claim_directly(par, run_id)  # 이어받음(구획 시도 2)
    assert isinstance(retaken, SegmentClaimed) and (retaken.position, retaken.attempt) == (0, 2)
    with transaction.atomic():
        late = services.segment_end(
            company_id=par.company_id,
            run_id=run_id,
            run_attempt=1,
            step="spread",
            key_sha256=old.key_sha256,
            attempt=old.attempt,
            outcome=EndDone(data={"square": -1}),
            now=par.now,
            lease_s=SETTINGS.lease_s,
            parallel_max=2,
            on_failure="pass_to_gather",
        )
    assert late == Superseded()
    row = segment_rows(par, run_id)[0]
    assert (row.status, row.attempts, row.data) == ("running", 2, None)


def test_a_redelivered_note_with_the_same_attempt_never_ends_a_segment_twice(par: Par) -> None:
    """reject_on_worker_lost(1-6): 같은 쪽지가 다시 와 같은 run_attempt 로 또 잡아도 구획마다 끝남 한 번."""
    par.script.count = 4
    par.parallel = 2
    run_id = new_run(par)
    execute(par, run_id)
    first = dict(par.notes[0][1])
    # 첫 구획을 도는 동안 같은 쪽지가 다시 온다(워커를 잃은 꼴)
    par.script.hooks = {1: lambda: deliver(par, "segment", first)}
    drain(par)
    assert run_row(par, run_id).status == "done"
    rows = segment_rows(par, run_id)
    assert [(r.status, r.attempts) for r in rows] == [("done", 1)] * 4
    assert sorted(par.script.called) == [1, 2, 3, 4]


def test_the_late_note_after_an_exhausting_end_changes_nothing(par: Par) -> None:
    """감독 처분 D2: 소진으로 끝난 구획을 같은 시도의 늦은 쪽지가 끝내려 함 → 기록 한 줄·쪽지 0·예외 0."""
    par.script.count = 2
    par.parallel = 2
    run_id = new_run(par)
    execute(par, run_id)
    par.notes.clear()
    held: object = None
    for _ in range(SETTINGS.max_attempts):
        held = claim_directly(par, run_id)
        assert isinstance(held, SegmentClaimed) and held.position == 0
        par.now += timedelta(seconds=SETTINGS.lease_s + 1)
    assert isinstance(held, SegmentClaimed)
    # 넷째 잡기가 소진으로 끝내고 둘째 구획을 잡는다 — 그 쪽지(시도 셋)는 지금 둘째를 돈다고 치고, 셋째 쪽지가 늦게 온다
    exhausted = claim_directly(par, run_id)
    assert isinstance(exhausted, SegmentClaimed) and exhausted.position == 1
    assert segment_rows(par, run_id)[0].status == "failed"
    before = [(r.status, r.attempts, r.error_code, r.updated_at) for r in segment_rows(par, run_id)]
    run_before = run_row(par, run_id)

    calls_before = list(par.script.called)
    with transaction.atomic(), pytest.raises(services.SegmentAlreadyEnded):
        services.segment_end(
            company_id=par.company_id,
            run_id=run_id,
            run_attempt=1,
            step="spread",
            key_sha256=held.key_sha256,
            attempt=held.attempt,
            outcome=EndDone(data={"square": -1}),
            now=par.now,
            lease_s=SETTINGS.lease_s,
            parallel_max=2,
            on_failure="pass_to_gather",
        )

    # 태스크 쪽: 첫 구획을 돌던 늦은 쪽지가 끝냄 블록에 닿는다(잡기는 시험이 이미 준 것으로 바꿔 끼움)
    def late_claim(**_: Any) -> SegmentClaimed:
        return held

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(services, "segment_claim", late_claim)
        tasks.execute_segment(par, company_id=str(par.company_id), run_id=str(run_id), run_attempt="1")
    assert [(r.status, r.attempts, r.error_code, r.updated_at) for r in segment_rows(par, run_id)] == before
    after = run_row(par, run_id)
    assert (after.status, after.parked_at, after.updated_at) == (
        run_before.status,
        run_before.parked_at,
        run_before.updated_at,
    )
    assert par.notes == []  # 깨우기·이어 넣기 0
    assert par.script.called == [*calls_before, 1]


def test_when_every_note_is_lost_requeue_runs_reparks_and_the_run_ends(
    par: Par, monkeypatch: pytest.MonkeyPatch
) -> None:
    par.script.count = 4
    run_id = new_run(par)
    execute(par, run_id)
    par.notes.clear()  # 쪽지 전부 잃음(하드 제한·acks_on_failure_or_timeout)
    par.now += timedelta(seconds=SETTINGS.lease_s + 1)
    monkeypatch.setattr(requeue_runs, "now", lambda: par.now)
    monkeypatch.setattr(queue, "broker_settings", lambda: BROKER)
    call_command("requeue_runs", "--tenant", str(par.company_id))
    assert [kind for kind, _ in par.notes] == ["run"]
    take_next(par)  # 지휘 시도 2 가 다시 주차한다
    reparked = run_row(par, run_id)
    assert (reparked.status, reparked.attempts) == ("processing", 2)
    assert reparked.parked_at is not None
    assert [kw["run_attempt"] for kw in par.segment_notes()] == [2] * PARALLEL
    drain(par)
    assert run_row(par, run_id).status == "done"
    assert sorted(par.script.called) == [1, 2, 3, 4]


def test_reparking_without_progress_three_times_exhausts_the_run(par: Par, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = new_run(par)
    monkeypatch.setattr(requeue_runs, "now", lambda: par.now)
    monkeypatch.setattr(queue, "broker_settings", lambda: BROKER)
    execute(par, run_id)
    for _ in range(SETTINGS.max_attempts + 2):
        if run_row(par, run_id).status != "processing":
            break
        par.notes.clear()
        par.now += timedelta(seconds=SETTINGS.lease_s + 1)
        call_command("requeue_runs", "--tenant", str(par.company_id))
        drain_runs_only(par)
    run = run_row(par, run_id)
    assert (run.status, run.error_code) == ("failed", "attempts_exhausted")
    assert par.script.called == []


def drain_runs_only(world: Par) -> None:
    for kind, kw in list(world.notes):
        if kind == "run":
            world.notes.remove((kind, kw))
            deliver(world, kind, kw)


# ── T14 치명 여섯 × 직렬·병렬 · 앞 갈래 · 잠깐 오류 · fail_run · 합 넘침 ───────────


FATALS: list[tuple[Callable[[], Exception], str]] = [
    (lambda: LiveSetupError("키가 없다"), "setup_error"),
    (lambda: LlmConfigError("설정이 틀렸다"), "setup_error"),
    (lambda: PromptError("봉투가 없다"), "step_error"),
    (lambda: RunVersionsMismatch("판이 다르다"), "versions_mismatch"),
    (lambda: RunOptionsRejected("옵션이 틀렸다"), "options_rejected"),
    (lambda: FlowInputError("입력이 틀렸다"), "flow_input_invalid"),
]


@pytest.mark.parametrize("parallel", [1, 2], ids=["serial", "parallel"])
@pytest.mark.parametrize(("make", "code"), FATALS, ids=[code + str(i) for i, (_, code) in enumerate(FATALS)])
def test_a_run_fatal_error_in_a_segment_fails_the_run_on_the_fanout_step(
    make_world: Callable[[int], Par], parallel: int, make: Callable[[], Exception], code: str
) -> None:
    world = make_world(parallel)
    world.script.count = 5

    def boom() -> None:
        raise make()

    world.script.hooks = {2: boom}
    run_id = new_run(world)
    execute(world, run_id)
    drain(world)
    run = run_row(world, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", code, "spread")
    assert spread_step(world, run_id).status == "failed"
    assert run.parked_at is None
    assert sorted(world.script.called) == [1, 2]  # 남은 구획은 잡히지 않는다
    assert segment_statuses(world, run_id)[2:] == ["pending"] * 3


def test_document_unreachable_releases_the_segment_and_a_later_note_finishes_it(par: Par) -> None:
    par.script.count = 2
    par.parallel = 2
    run_id = new_run(par)
    execute(par, run_id)
    par.storage.fail_with = StorageUnavailable("닿지 못함")
    take_next(par)
    row = segment_rows(par, run_id)[0]
    assert (row.status, row.attempts, row.lease_expires_at) == ("running", 1, None)
    assert par.notes[-1] == (
        "segment",
        {"company_id": par.company_id, "run_id": run_id, "run_attempt": 1, "countdown": SETTINGS.retry_delay_s},
    )
    par.storage.fail_with = None
    drain(par)
    assert run_row(par, run_id).status == "done"


def test_a_binding_versions_mismatch_after_parking_fails_the_run_without_a_step(par: Par) -> None:
    run_id = new_run(par)
    execute(par, run_id)
    par.binding_fail.append(RunVersionsMismatch("판이 다르다"))
    take_next(par)
    run = run_row(par, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "versions_mismatch", None)
    assert par.script.called == []


def test_a_claimed_sha_missing_from_the_replanned_segments_is_a_mismatch(par: Par) -> None:
    run_id = new_run(par)
    execute(par, run_id)
    SHIFT[0] = "-other"  # 쪽지가 다시 센 계획이 저장된 것과 다르다
    take_next(par)
    run = run_row(par, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "segments_mismatch", "spread")
    assert par.script.called == []


def test_a_transient_error_is_released_with_a_delay_and_exhausts_after_three(par: Par) -> None:
    par.script.count = 2
    par.parallel = 2

    def flaky() -> None:
        raise RunRetryLater("공급사가 잠깐 막힘")

    par.script.hooks = {1: flaky}
    run_id = new_run(par)
    execute(par, run_id)
    delays: list[int] = []
    while par.notes:
        kind, kw = par.notes.pop(0)
        if kind == "segment":
            delays.append(kw["countdown"])
        deliver(par, kind, kw)
    assert SETTINGS.retry_delay_s in delays
    assert par.script.called.count(1) == SETTINGS.max_attempts
    rows = segment_rows(par, run_id)
    assert [(r.status, r.error_code) for r in rows] == [("failed", "attempts_exhausted"), ("done", None)]
    assert run_row(par, run_id).status == "done"  # pass_to_gather


def test_fail_run_wakes_on_the_first_failure_and_fails_with_segments_failed(par: Par) -> None:
    par.script.count = 6

    def bad() -> None:
        raise ValueError("지어낸 영구 실패")

    par.script.hooks = {2: bad}
    run_id = new_run(par, FAIL_RUN)
    execute(par, run_id)
    drain(par)
    run = run_row(par, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "segments_failed", "spread")
    assert par.woken == 1  # 먼저 기록된 실패에서 한 번
    assert segment_rows(par, run_id)[1].error_code == "step_error"


def test_the_parallel_data_sum_fails_the_step_where_it_crosses(par: Par, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "FANOUT_DATA_MAX_OCTETS", 40)  # 구획 data {"square": n} 셋째쯤에서 넘는다
    run_id = new_run(par)
    execute(par, run_id)
    drain(par)
    run = run_row(par, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "step_output_invalid", "spread")
    assert len(par.script.called) < COUNT


# ── T15 장벽 0 변화 ───────────────────────────────────────────────────


def test_a_barrier_flow_with_cap_three_sends_no_note_and_writes_no_segment(par: Par) -> None:
    run_id = new_run(par, PLAIN)
    execute(par, run_id)
    run = run_row(par, run_id)
    assert (run.status, run.parked_at) == ("done", None)
    assert par.notes == []
    assert segment_rows(par, run_id) == []


def test_a_claim_that_exhausts_the_last_segment_sends_one_conductor_note(par: Par) -> None:
    """마지막 남은 구획이 잡기의 소진으로 끝난다 → 그 쪽지가 커밋 뒤 지휘 쪽지 하나(NothingToClaim wake) → 실행 끝남."""
    par.script.count = 1
    par.parallel = 2
    run_id = new_run(par)
    execute(par, run_id)
    note = dict(par.segment_notes()[0])
    par.notes.clear()
    for _ in range(SETTINGS.max_attempts):  # 쥔 채 죽는 쪽지 셋
        assert isinstance(claim_directly(par, run_id), SegmentClaimed)
        par.now += timedelta(seconds=SETTINGS.lease_s + 1)
    deliver(par, "segment", note)
    assert [kind for kind, _ in par.notes] == ["run"]
    assert [(r.status, r.error_code) for r in segment_rows(par, run_id)] == [("failed", "attempts_exhausted")]
    drain(par)
    run = run_row(par, run_id)
    assert (run.status, run.parked_at) == ("done", None)  # pass_to_gather — 모음에 failed 로
    assert par.woken == 1
    assert par.script.called == []


def _released_with_delay(world: Par, run_id: int) -> None:
    row = segment_rows(world, run_id)[0]
    assert (row.status, row.attempts, row.lease_expires_at) == ("running", 1, None)
    assert world.notes[-1][1]["countdown"] == SETTINGS.retry_delay_s
    assert run_row(world, run_id).status == "processing"
    assert world.script.called == []


def test_a_note_whose_resume_point_is_another_step_releases_its_segment(par: Par) -> None:
    """R1(앞 갈래 표): 쪽지가 다시 읽은 이어 갈 자리(_plan.start_at)가 그 펼침이 아니면 놓는다."""
    par.script.count = 2
    run_id = new_run(par)
    execute(par, run_id)
    RunStepRow.for_company(par.company_id).filter(run_id=run_id, name="spread").update(
        status="done", data={"segments": []}
    )
    take_next(par)
    _released_with_delay(par, run_id)


@pytest.mark.parametrize(
    ("count", "code"), [(0, "segments_empty"), (101, "step_output_invalid")], ids=["empty", "over-max"]
)
def test_a_replan_failure_fails_the_run_on_the_fanout_step(par: Par, count: int, code: str) -> None:
    """R2(앞 갈래 표): plan_segments 의 예외(SegmentsEmpty·상한 넘음) → Fatal(표 code, step = 펼침)."""
    par.script.count = 3
    run_id = new_run(par, NO_EMPTY)
    execute(par, run_id)
    RunStepRow.for_company(par.company_id).filter(run_id=run_id, name="prepare").update(data={"count": count})
    take_next(par)
    run = run_row(par, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", code, "spread")
    assert par.script.called == []


def test_an_executor_defect_outside_the_table_releases_the_segment(par: Par, monkeypatch: pytest.MonkeyPatch) -> None:
    """R3(감독 답 Qn1): 앞 갈래 표 밖의 예외는 그 구획의 실패가 아니라 놓음(시도 상한이 끝낸다)."""
    par.script.count = 2
    run_id = new_run(par)
    execute(par, run_id)

    def broken(*args: object, **kwargs: object) -> object:
        raise KeyError("실행기의 결함")

    monkeypatch.setattr(tasks, "_plan", broken)
    take_next(par)
    _released_with_delay(par, run_id)


def test_only_an_already_ended_segment_is_swallowed_other_update_errors_rise(
    par: Par, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R4(감독 처분 D2): 태스크는 SegmentAlreadyEnded 만 삼킨다 — 다른 RunUpdateError 는 그대로 올린다."""
    par.script.count = 2
    run_id = new_run(par)
    execute(par, run_id)

    def broken(**kwargs: object) -> object:
        raise RunUpdateError("run_segments 의 갱신이 0행이다")

    monkeypatch.setattr(services, "segment_end", broken)
    kind, kw = par.notes.pop(0)
    with pytest.raises(RunUpdateError) as raised:
        deliver(par, kind, kw)
    assert type(raised.value) is RunUpdateError


# ── ④ 가지 리뷰 고침 ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "make", [lambda: LiveSetupError("키가 없다"), lambda: LlmConfigError("설정이 틀렸다")], ids=["live-setup", "config"]
)
def test_a_setup_error_while_binding_in_a_note_fails_the_fanout_step_at_once(
    par: Par, make: Callable[[], Exception]
) -> None:
    """리뷰 M3: 쪽지의 끼움(입력·어댑터 짓기)에서 난 키 없음·설정 오류도 치명 — 놓아 시도 셋을 헛돌지 않는다."""
    par.script.count = 3
    run_id = new_run(par)
    execute(par, run_id)
    par.binding_fail.append(make())
    drain(par)
    run = run_row(par, run_id)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "setup_error", "spread")
    assert spread_step(par, run_id).status == "failed"
    rows = segment_rows(par, run_id)
    assert [(r.status, r.attempts) for r in rows] == [("failed", 1), ("pending", 0), ("pending", 0)]  # 구획 시도 하나
    assert par.woken == 0
    assert par.script.called == []


def test_a_serial_attempt_ends_a_segment_that_a_note_had_leased(par: Par, monkeypatch: pytest.MonkeyPatch) -> None:
    """리뷰 N1: 상한이 2→1 로 바뀐 뒤 requeue 로 직렬 시도가 쪽지가 임대한 구획을 끝내도 임대 CHECK 를 지난다."""
    par.script.count = 2
    run_id = new_run(par)
    execute(par, run_id)
    held = claim_directly(par, run_id)
    assert isinstance(held, SegmentClaimed)
    assert segment_rows(par, run_id)[0].lease_expires_at is not None
    par.notes.clear()
    par.parallel = 1
    par.now += timedelta(seconds=SETTINGS.lease_s + 1)
    monkeypatch.setattr(requeue_runs, "now", lambda: par.now)
    monkeypatch.setattr(queue, "broker_settings", lambda: BROKER)
    call_command("requeue_runs", "--tenant", str(par.company_id))
    drain(par)
    run = run_row(par, run_id)
    assert (run.status, run.error_code) == ("done", None)
    assert [(r.status, r.lease_expires_at) for r in segment_rows(par, run_id)] == [("done", None), ("done", None)]
