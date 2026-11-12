"""구획 옮김·고른 구획만 다시·짝짓기(RM1c ① — T3~T9)를 진짜 DB·가짜 모듈로 잰다. 업무 층.

실행 만들기는 create_run(actions)을 그대로 부르고, 실행기는 RM1a·RM1b 시험의 가짜 흐름·끼움·가짜 브로커를 쓴다
(`probe.segmented@1` 과 판만 바꾼 `@2` — 시험 레지스트리에만, 제품 흐름 등록 0). 앞 실행의 구획 상태(running·pending
섞임)는 행을 손으로 써서 짓는다. 값은 지어낸 것이다.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from esgapi.core.flows.binding import BindingRegistry
from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import Flow, segment_key_fields, segment_key_sha256
from esgapi.core.models import AuditEventRow
from esgapi.runs.calc.segments import Both, data_octets, pair_segments
from esgapi.runs.models import RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.actions import runs as actions
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.services import runs as services
from esgapi.runs.tests import test_executor_parallel as parallel_tests
from esgapi.runs.tests.test_executor_parallel import Par, drain
from esgapi.runs.tests.test_executor_segments import (
    COUNT,
    FAIL_RUN,
    FLOWS,
    NOW,
    PLAIN,
    SEGMENTED,
    Binding,
    calls,
    key_at,
    new_run,
    raise_permanent,
    run_row,
    segment_statuses,
    segmented,
    spread_step,
)

pytestmark = pytest.mark.django_db

SEGMENTED_2 = segmented("probe.segmented@2")  # 판만 바꾼 흐름(계획·열쇠는 @1 과 같다)


class VersionedBinding(Binding):
    """판 몫을 시험이 바꾸는 끼움(지금 끼움이 짓는 판 ≠ 앞 판 — RetryVersionChanged)."""

    def __init__(self, base: Binding, version: list[dict[str, object]]) -> None:
        super().__init__(base.script)
        self.version = version

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return dict(self.version[0])


@dataclass
class Bench:
    par: Par
    sent: list[object]
    version: list[dict[str, object]]

    @property
    def company_id(self) -> int:
        return self.par.company_id


@pytest.fixture
def make_bench(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> Callable[[int], Bench]:
    def make(parallel: int) -> Bench:
        par = cast("Par", getattr(parallel_tests, "_world")(monkeypatch, companies, parallel))  # noqa: B009 — RM1b 의 틀
        version: list[dict[str, object]] = [{}]
        flows = FlowRegistry()
        bindings = BindingRegistry()
        for flow in (*FLOWS, SEGMENTED_2):
            flows.register(flow)
            bindings.register(flow.id, VersionedBinding(Binding(par.script), version))
        from esgapi.runs import tasks

        monkeypatch.setattr(tasks, "REGISTRY", flows)
        monkeypatch.setattr(tasks, "BINDINGS", bindings)
        monkeypatch.setattr(actions, "REGISTRY", flows)
        monkeypatch.setattr(actions, "BINDINGS", bindings)
        sent: list[object] = []  # create 가 블록 안에서 지은 지휘 쪽지(on_commit) — 시험 트랜잭션이라 불리지 않는다
        sending = getattr(actions, "_sending")  # noqa: B009

        def counted(send: object, **kw: Any) -> object:
            built = sending(send, **kw)
            sent.append(built)
            return built

        monkeypatch.setattr(actions, "_sending", counted)
        return Bench(par=par, sent=sent, version=version)

    return make


@pytest.fixture
def bench(make_bench: Callable[[int], Bench]) -> Bench:
    return make_bench(1)


def create(
    bench: Bench,
    *,
    flow: Flow = SEGMENTED,
    document_id: int | None,
    resume_from: int | None = None,
    retry: actions.SegmentRetry | None = None,
    options: Mapping[str, object] | None = None,
    module: str = "probe",
    flow_id: str | None = None,
    launch_key: str | None = None,
    company_id: int | None = None,
) -> object:
    return actions.create_run(
        company_id=bench.company_id if company_id is None else company_id,
        actor_kind="service",
        actor_user_id=7,
        module=module,
        flow_id=flow.id if flow_id is None else flow_id,
        document_id=document_id,
        options={} if options is None else options,
        resume_from=resume_from,
        now=NOW,
        launch_key=launch_key,
        retry=retry,
    )


def created_id(result: object) -> int:
    assert isinstance(result, actions.RunCreated), result
    return result.run.id


def execute(bench: Bench, run_id: int) -> None:
    from esgapi.runs.tests.test_executor_parallel import execute as run_once

    run_once(bench.par, run_id)
    drain(bench.par)


def segments(bench: Bench, run_id: int) -> list[RunSegmentRow]:
    return list(RunSegmentRow.for_company(bench.company_id).filter(run_id=run_id).order_by("step", "position"))


def snapshot(bench: Bench, run_id: int) -> list[tuple[object, ...]]:
    return [
        (r.position, r.status, r.attempts, r.data, r.error_code, r.started_at, r.finished_at, r.lease_expires_at)
        for r in segments(bench, run_id)
    ]


def failed_run(bench: Bench, statuses: list[str], *, flow: Flow = FAIL_RUN) -> int:
    """펼침 spread 에서 끝난 실패 실행을 손으로 짓는다(prepare done · spread failed · gather pending)."""
    run_id = new_run(bench.par, flow)
    company = bench.company_id
    RunRow.for_company(company).filter(pk=run_id).update(
        status="failed", attempts=1, error_code="segments_failed", failed_step="spread", finished_at=NOW
    )
    steps = RunStepRow.for_company(company).filter(run_id=run_id)
    steps.filter(name="prepare").update(status="done", data={"count": len(statuses)}, started_at=NOW, finished_at=NOW)
    steps.filter(name="spread").update(status="failed", started_at=NOW, finished_at=NOW)
    for position, status in enumerate(statuses):
        n = position + 1
        key = key_at(n)
        RunSegmentRow.for_company(company).create(
            company_id=company,
            run_id=run_id,
            step="spread",
            position=position,
            kind=key.kind,
            key=segment_key_fields(key),
            key_sha256=segment_key_sha256(key),
            status=status,
            attempts=0 if status == "pending" else 1,
            data={"square": n * n} if status == "done" else None,
            error_code="step_error" if status == "failed" else None,
            started_at=None if status == "pending" else NOW,
            finished_at=NOW if status in {"done", "failed"} else None,
            lease_expires_at=NOW + timedelta(seconds=90) if status == "running" else None,
        )
    return run_id


T3_STATUSES = ["done"] * 12 + ["failed"] + ["running"] * 2 + ["pending"] * 5


def document_of(bench: Bench, run_id: int) -> int:
    document = run_row(bench.par, run_id).document_id
    assert document is not None
    return document


def segment_sqls(captured: CaptureQueriesContext) -> list[str]:
    return [q["sql"] for q in captured.captured_queries if "run_segments" in q["sql"]]


def counts_of(bench: Bench) -> tuple[int, int, int, int]:
    company = bench.company_id
    return (
        RunRow.for_company(company).count(),
        RunSegmentRow.for_company(company).count(),
        AuditEventRow.for_company(company).count(),
        len(bench.sent),
    )


# ── T3 create_run 길 이어 돌기(635-4) ─────────────────────────────────


def test_a_resumed_fanout_run_carries_the_done_segments_and_makes_the_rest_pending(bench: Bench) -> None:
    previous = failed_run(bench, T3_STATUSES)
    before = snapshot(bench, previous)
    new = created_id(create(bench, flow=FAIL_RUN, document_id=document_of(bench, previous), resume_from=previous))
    rows = segments(bench, new)
    assert len(rows) == COUNT
    assert [r.status for r in rows] == ["done"] * 12 + ["pending"] * 8
    assert {r.attempts for r in rows} == {0}  # 옮겨 온 구획 = attempts 0
    assert {r.lease_expires_at for r in rows} == {None}
    old = {r.position: r for r in segments(bench, previous)}
    for r in rows[:12]:
        assert (r.data, r.key, r.key_sha256, r.started_at, r.finished_at) == (
            old[r.position].data,
            old[r.position].key,
            old[r.position].key_sha256,
            NOW,
            NOW,
        )
        assert r.data_octets == data_octets(cast("dict[str, object]", r.data))  # 직렬 done(NULL)을 채움
    for r in rows[12:]:
        assert (r.data, r.error_code, r.started_at, r.finished_at, r.data_octets) == (None, None, None, None, None)
    assert snapshot(bench, previous) == before  # 앞 실행 0 바뀜
    assert run_row(bench.par, new).resumed_from_run_id == previous


def test_resuming_a_barrier_flow_reads_no_segments(bench: Bench) -> None:
    previous = new_run(bench.par, PLAIN)
    RunRow.for_company(bench.company_id).filter(pk=previous).update(status="failed", error_code="step_error")
    with CaptureQueriesContext(connection) as captured:
        created_id(create(bench, flow=PLAIN, document_id=document_of(bench, previous), resume_from=previous))
    assert segment_sqls(captured) == []  # 펼침 없는 흐름은 구획 읽기 0(장벽 이어 돌기 쿼리 = BASE)
    assert len(captured.captured_queries) > 5  # 분모: 잰 블록이 실제로 문을 냈다


def test_a_carried_done_fanout_step_with_a_running_row_is_a_runtime_error(bench: Bench) -> None:
    previous = failed_run(bench, ["done", "running"])
    company = bench.company_id
    steps = RunStepRow.for_company(company).filter(run_id=previous)
    steps.filter(name="spread").update(status="done", data={"segments": []})
    RunRow.for_company(company).filter(pk=previous).update(error_code="step_error", failed_step="gather")
    before = counts_of(bench)
    with pytest.raises(RuntimeError, match="끝나지 않은"):
        create(bench, flow=FAIL_RUN, document_id=document_of(bench, previous), resume_from=previous)
    assert counts_of(bench) == before  # 블록째 되돌려졌다


def test_a_changed_carried_key_fails_with_mismatch_and_the_next_resume_starts_from_scratch(bench: Bench) -> None:
    """B3: 옮긴 행의 열쇠가 새 계획과 다르면 첫 시도 segments_mismatch — 다시 이어 돌면 시작 단계를 옮기지 않는다."""
    previous = failed_run(bench, ["done", "done", "pending"])
    document = document_of(bench, previous)
    second = created_id(create(bench, flow=FAIL_RUN, document_id=document, resume_from=previous))
    other = segment_key_sha256(key_at(99))
    RunSegmentRow.for_company(bench.company_id).filter(run_id=second, position=0).update(key_sha256=other)
    execute(bench, second)
    run = run_row(bench.par, second)
    assert (run.status, run.error_code) == ("failed", "segments_mismatch")
    assert bench.par.script.called == []
    third = created_id(create(bench, flow=FAIL_RUN, document_id=document, resume_from=second))
    assert segments(bench, third) == []  # 처음부터 계획
    execute(bench, third)
    assert run_row(bench.par, third).status == "done"
    assert bench.par.script.called == [1, 2, 3]
    assert segment_statuses(bench.par, third) == ["done"] * 3


# ── T4 실행기 끝까지(상한 1·2) ────────────────────────────────────────


@pytest.mark.parametrize("parallel", [1, 2])
def test_the_resumed_run_calls_only_the_eight_left_and_gathers_twenty(
    make_bench: Callable[[int], Bench], parallel: int
) -> None:
    bench = make_bench(parallel)
    previous = failed_run(bench, T3_STATUSES)
    new = created_id(create(bench, flow=FAIL_RUN, document_id=document_of(bench, previous), resume_from=previous))
    execute(bench, new)
    run = run_row(bench.par, new)
    assert (run.status, run.error_code) == ("done", None)
    assert sorted(bench.par.script.called) == list(range(13, COUNT + 1))  # 모의 호출 8
    logged = calls(bench.par, new)
    assert len(logged) == 8
    assert all(line.cost_usd is not None and line.cost_usd > 0 for line in logged)
    data = cast("dict[str, object]", spread_step(bench.par, new).data)
    gathered = cast("list[dict[str, Any]]", data["segments"])
    assert [s["status"] for s in gathered] == ["done"] * COUNT
    assert [cast("dict[str, object]", s["data"])["square"] for s in gathered] == [n * n for n in range(1, COUNT + 1)]
    counted = selectors.segment_counts(company_id=bench.company_id, run_id=new)["spread"]
    assert (counted.planned, counted.done) == (COUNT, COUNT)
    attempts = [r.attempts for r in segments(bench, new)]
    assert attempts == [0] * 12 + [1] * 8  # 옮겨 온 12 · 이 실행에서 돈 8


# ── T5 옮긴 done 펼침 · 옮긴 data_octets ───────────────────────────────


def gather_failed_run(bench: Bench) -> int:
    """spread 까지 끝나고 gather 에서 실패한 실행(실행기로 끝까지 돈 뒤 gather 를 failed 로)."""
    run_id = new_run(bench.par, SEGMENTED)
    execute(bench, run_id)
    company = bench.company_id
    RunRow.for_company(company).filter(pk=run_id).update(status="failed", error_code="step_error", failed_step="gather")
    RunStepRow.for_company(company).filter(run_id=run_id, name="gather").update(status="failed", data=None)
    bench.par.script.called.clear()
    return run_id


@pytest.mark.parametrize("parallel", [1, 2])
def test_a_carried_done_fanout_calls_no_segment_and_keeps_its_count(
    make_bench: Callable[[int], Bench], parallel: int
) -> None:
    bench = make_bench(parallel)
    previous = gather_failed_run(bench)
    new = created_id(create(bench, document_id=document_of(bench, previous), resume_from=previous))
    assert [r.status for r in segments(bench, new)] == ["done"] * COUNT  # 「계획됨 0」이 아니다
    execute(bench, new)
    assert run_row(bench.par, new).status == "done"
    assert bench.par.script.called == []
    assert calls(bench.par, new) == []
    assert selectors.segment_counts(company_id=bench.company_id, run_id=new)["spread"].planned == COUNT


def test_the_carried_octets_count_toward_the_parallel_sum(
    make_bench: Callable[[int], Bench], monkeypatch: pytest.MonkeyPatch
) -> None:
    bench = make_bench(2)
    previous = failed_run(bench, ["done"] * 12 + ["pending"] * 8, flow=SEGMENTED)
    new = created_id(create(bench, document_id=document_of(bench, previous), resume_from=previous))
    carried = sum(data_octets({"square": n * n}) for n in range(1, 13))
    monkeypatch.setattr(services, "FANOUT_DATA_MAX_OCTETS", carried + 5)  # 새 done 하나로 넘친다
    execute(bench, new)
    run = run_row(bench.par, new)
    assert (run.status, run.error_code, run.failed_step) == ("failed", "step_output_invalid", "spread")


# ── T6·T8 고른 구획만 다시 ─────────────────────────────────────────────


def done_run_with_failures(
    bench: Bench, *, count: int = 10, failing: tuple[int, ...] = (3, 7), flow: Flow = SEGMENTED
) -> int:
    bench.par.script.count = count
    for n in failing:
        bench.par.script.hooks[n] = raise_permanent
    run_id = new_run(bench.par, flow)
    execute(bench, run_id)
    assert run_row(bench.par, run_id).status == "done"
    bench.par.script.hooks.clear()
    bench.par.script.called.clear()
    return run_id


def shas(*ns: int) -> tuple[str, ...]:
    return tuple(segment_key_sha256(key_at(n)) for n in ns)


@pytest.mark.parametrize("parallel", [1, 2])
def test_a_retry_runs_only_the_chosen_segments_with_the_same_versions(
    make_bench: Callable[[int], Bench], parallel: int
) -> None:
    bench = make_bench(parallel)
    previous = done_run_with_failures(bench)
    before = snapshot(bench, previous)
    retry = actions.SegmentRetry(from_run_id=previous, step="spread", keys=shas(7, 3))
    new = created_id(create(bench, document_id=document_of(bench, previous), retry=retry))
    run = run_row(bench.par, new)
    assert (run.versions, run.options, run.resumed_from_run_id) == (run_row(bench.par, previous).versions, {}, previous)
    steps = {s.name: s for s in RunStepRow.for_company(bench.company_id).filter(run_id=new)}
    assert [steps[n].status for n in ("prepare", "spread", "gather")] == ["done", "pending", "pending"]
    statuses = [r.status for r in segments(bench, new)]
    assert statuses == ["done", "done", "pending", "done", "done", "done", "pending", "done", "done", "done"]
    execute(bench, new)
    assert run_row(bench.par, new).status == "done"
    assert sorted(bench.par.script.called) == [3, 7]  # 모의 호출 2
    assert len(calls(bench.par, new)) == 2
    data = cast("dict[str, object]", spread_step(bench.par, new).data)
    assert [s["status"] for s in cast("list[dict[str, Any]]", data["segments"])] == ["done"] * 10
    assert snapshot(bench, previous) == before


def test_an_imported_run_can_be_retried(bench: Bench) -> None:
    """넣은 실행(idempotency_key 가 묶음 열쇠 — R4)도 고른 다시 대상이다."""
    previous = done_run_with_failures(bench)
    RunRow.for_company(bench.company_id).filter(pk=previous).update(
        idempotency_key="bundle-0000", idempotency_sha256="0" * 64
    )
    retry = actions.SegmentRetry(from_run_id=previous, step="spread", keys=shas(3))
    created_id(create(bench, document_id=document_of(bench, previous), retry=retry))


def test_an_unchosen_failure_stays_failed_in_the_gather(bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    retry = actions.SegmentRetry(from_run_id=previous, step="spread", keys=shas(3))
    new = created_id(create(bench, document_id=document_of(bench, previous), retry=retry))
    execute(bench, new)
    assert bench.par.script.called == [3]
    data = cast("dict[str, object]", spread_step(bench.par, new).data)
    gathered = cast("list[dict[str, Any]]", data["segments"])
    assert [(s["status"], s["errorCode"]) for s in gathered][6] == ("failed", "step_error")
    assert sum(1 for s in gathered if s["status"] == "failed") == 1


def test_a_fail_run_done_run_retries_one_done_segment_and_twice(bench: Bench) -> None:
    previous = done_run_with_failures(bench, count=4, failing=(), flow=FAIL_RUN)
    retry = actions.SegmentRetry(from_run_id=previous, step="spread", keys=shas(2))
    document = document_of(bench, previous)
    first = created_id(create(bench, flow=FAIL_RUN, document_id=document, retry=retry))
    second = created_id(create(bench, flow=FAIL_RUN, document_id=document, retry=retry))  # D4: 여러 번
    assert first != second
    execute(bench, first)
    assert (run_row(bench.par, first).status, bench.par.script.called) == ("done", [2])


def test_without_retry_a_new_run_reads_and_writes_no_segments(bench: Bench) -> None:
    document = document_of(bench, new_run(bench.par, SEGMENTED))
    with CaptureQueriesContext(connection) as captured:
        new = created_id(create(bench, document_id=document))
    assert segment_sqls(captured) == []
    assert segments(bench, new) == []


# ── T7 거절 차례 — 행·쪽지·감사 0 ───────────────────────────────────────


@pytest.fixture
def done_previous(bench: Bench) -> int:
    return done_run_with_failures(bench)


def refused(bench: Bench, result: object, kind: type) -> None:
    assert isinstance(result, kind), result


def test_every_refusal_writes_nothing(bench: Bench, done_previous: int, companies: tuple[int, int]) -> None:
    previous = done_previous
    document = document_of(bench, previous)
    good = actions.SegmentRetry(from_run_id=previous, step="spread", keys=shas(3))
    other_document = document_of(bench, new_run(bench.par, SEGMENTED))  # 같은 회사의 다른 올린 문서
    before = counts_of(bench)
    other_company = companies[1]
    cases: list[tuple[dict[str, Any], type]] = [
        ({"document_id": 999_999, "retry": good}, actions.DocumentNotFound),
        ({"document_id": document, "retry": actions.SegmentRetry(999_999, "spread", shas(3))}, actions.RetryNotFound),
        ({"document_id": document, "retry": good, "resume_from": previous}, actions.RetryMismatch),
        ({"document_id": document, "retry": good, "options": {"pages": "2"}}, actions.RetryMismatch),
        ({"document_id": document, "retry": good, "flow_id": FAIL_RUN.id}, actions.RetryMismatch),
        ({"document_id": other_document, "retry": good}, actions.RetryMismatch),
        ({"document_id": document, "retry": good, "module": "other"}, actions.RetryMismatch),
        (
            {"document_id": document, "retry": actions.SegmentRetry(previous, "prepare", shas(3))},
            actions.RetrySegmentsUnknown,
        ),
        (
            {"document_id": document, "retry": actions.SegmentRetry(previous, "nope", shas(3))},
            actions.RetrySegmentsUnknown,
        ),
        (
            {"document_id": document, "retry": actions.SegmentRetry(previous, "spread", ())},
            actions.RetrySegmentsUnknown,
        ),
        (
            {"document_id": document, "retry": actions.SegmentRetry(previous, "spread", shas(3, 3))},
            actions.RetrySegmentsUnknown,
        ),
        (
            {"document_id": document, "retry": actions.SegmentRetry(previous, "spread", shas(99))},
            actions.RetrySegmentsUnknown,
        ),
    ]
    for kwargs, kind in cases:
        refused(bench, create(bench, **kwargs), kind)
    # 남의 회사의 실행 id(그 회사에서 본 이 실행) — 없음과 같다
    refused(bench, create(bench, document_id=None, retry=good, company_id=other_company), actions.RetryNotFound)
    # 앞 실행의 단계 이름이 지금 흐름과 다르다(마지막 — 앞 실행 행을 바꾼다)
    RunStepRow.for_company(bench.company_id).filter(run_id=previous, name="gather").update(name="renamed")
    refused(bench, create(bench, document_id=document, retry=good), actions.RetryMismatch)
    assert counts_of(bench) == before


def test_a_shape_mismatch_on_a_failed_run_is_the_422_first(bench: Bench) -> None:
    previous = failed_run(bench, ["done", "failed"])
    document = document_of(bench, previous)
    retry = actions.SegmentRetry(from_run_id=previous, step="spread", keys=shas(2))
    refused(
        bench, create(bench, flow=FAIL_RUN, document_id=document, retry=retry, options={"x": 1}), actions.RetryMismatch
    )
    refused(bench, create(bench, flow=FAIL_RUN, document_id=document, retry=retry), actions.RetryNotDone)


def test_the_same_launch_key_is_refused(bench: Bench, done_previous: int) -> None:
    RunRow.for_company(bench.company_id).filter(pk=done_previous).update(launch_key="launch-a")
    retry = actions.SegmentRetry(from_run_id=done_previous, step="spread", keys=shas(3))
    before = counts_of(bench)
    result = create(bench, document_id=document_of(bench, done_previous), retry=retry, launch_key="launch-a")
    refused(bench, result, actions.LaunchKeyReused)
    assert counts_of(bench) == before


def test_a_changed_binding_version_is_refused(bench: Bench, done_previous: int) -> None:
    bench.version[0] = {"probe": "v2"}  # 지금 끼움이 앞 옵션으로 짓는 판이 앞 판({flow})과 다르다
    retry = actions.SegmentRetry(from_run_id=done_previous, step="spread", keys=shas(3))
    before = counts_of(bench)
    refused(
        bench, create(bench, document_id=document_of(bench, done_previous), retry=retry), actions.RetryVersionChanged
    )
    assert counts_of(bench) == before


# ── T9 짝 selector ─────────────────────────────────────────────────────


def test_two_done_runs_of_two_flow_versions_pair_on_every_key(bench: Bench, companies: tuple[int, int]) -> None:
    first = done_run_with_failures(bench, count=COUNT, failing=(5,))
    second = done_run_with_failures(bench, count=COUNT, failing=(), flow=SEGMENTED_2)
    a = selectors.segment_refs(company_id=bench.company_id, run_id=first, step="spread")
    b = selectors.segment_refs(company_id=bench.company_id, run_id=second, step="spread")
    assert isinstance(a, selectors.Planned) and isinstance(b, selectors.Planned)
    pairs = pair_segments(a.refs, b.refs)
    assert len(pairs) == COUNT and all(isinstance(p, Both) for p in pairs)
    assert [r.status for r in a.refs].count("failed") == 1
    outputs = selectors.segment_outputs(company_id=bench.company_id, run_id=first, step="spread", shas=shas(4, 5, 6))
    assert outputs == {shas(4)[0]: {"square": 16}, shas(6)[0]: {"square": 36}}  # failed(5)는 빠진다
    assert isinstance(selectors.segment_refs(company_id=companies[1], run_id=first, step="spread"), selectors.NoRows)
    assert selectors.segment_outputs(company_id=companies[1], run_id=first, step="spread", shas=shas(4)) == {}
    assert isinstance(
        selectors.segment_refs(company_id=bench.company_id, run_id=first, step="gather"), selectors.NoRows
    )


def test_a_done_run_with_an_unfinished_step_before_the_chosen_one_is_refused(bench: Bench, done_previous: int) -> None:
    """방어(검증 1 권고 3 — ③′): done 실행인데 고른 단계 앞 단계에 data 가 없으면 RetryMismatch(엉뚱한 단계에 고른 열쇠
    규칙이 걸리지 않게)."""
    RunStepRow.for_company(bench.company_id).filter(run_id=done_previous, name="prepare").update(data=None)
    retry = actions.SegmentRetry(from_run_id=done_previous, step="spread", keys=shas(3))
    before = counts_of(bench)
    refused(bench, create(bench, document_id=document_of(bench, done_previous), retry=retry), actions.RetryMismatch)
    assert counts_of(bench) == before
