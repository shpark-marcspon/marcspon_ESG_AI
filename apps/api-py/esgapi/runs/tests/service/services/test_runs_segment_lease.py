"""구획 쪽지의 기록·울타리(RM1b ② — T7~T10): 주차 · 잡기(상한·지난 임대·놓음·소진·Superseded·fail_run) · 끝냄(옛 쪽지·
두 번 끝냄·Fatal·합 넘침) · 깨우기 한 번 · parked_at 비움 · 다음 시도 비교와 넣기의 SQL · 셈 쿼리 하나. 업무 층.

진짜 DB(주인 역할). 열쇠·값은 지어낸 것이다. 엇갈림은 스레드로 재지 않는다 — 블록을 차례로 불러 잰다(진짜 동시성은
밖, 감독 답 Q8). 잠금 기다림만 둘째 연결로 잰다(transaction=True 시험 하나).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import OperationalError, connection, connections, transaction
from django.test.utils import CaptureQueriesContext

from esgapi.core.flows.types import FANOUT_DATA_MAX_OCTETS, SegmentKey, segment_key_sha256
from esgapi.core.models import DocumentRow
from esgapi.runs.models import RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.services import runs as services
from esgapi.runs.service.services.runs import (
    EndDone,
    Ended,
    EndFailed,
    EndFatal,
    EndReleased,
    Finished,
    NothingToClaim,
    RunDeferred,
    RunDone,
    RunFailed,
    RunParkedOutcome,
    RunUpdateError,
    SegmentClaimed,
    Superseded,
)

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
LEASE_S = 330
STEP = "spread"
K = 2  # 지휘 시도


def key_at(n: int) -> SegmentKey:
    return SegmentKey(kind="block", span=f"c{n}", document_sha256=None, parser_version="v1")


def sha(n: int) -> str:
    return segment_key_sha256(key_at(n))


def call(write: Any, **kwargs: Any) -> Any:
    with transaction.atomic():
        return write(**kwargs)


def processing_run(company_id: int, *, attempt: int = K, tag: str = "a") -> RunRow:
    document = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name="a.pdf",
        storage_key=f"documents/{company_id}/{tag}.pdf",
        size_bytes=1,
        status="uploaded",
    )
    run = RunRow.for_company(company_id).create(
        company_id=company_id,
        document_id=document.pk,
        module="probe",
        flow_id="probe.segmented@1",
        status="processing",
        attempts=attempt,
        created_by_user_id=7,
    )
    for position, name in enumerate(("prepare", STEP, "gather")):
        RunStepRow.for_company(company_id).create(
            company_id=company_id, run_id=run.pk, name=name, position=position, status="pending"
        )
    return run


def parked_run(company_id: int, n: int, *, tag: str = "a", park_at: datetime = NOW) -> RunRow:
    """계획 n 개를 NOW 에 적고 park_at 에 주차한 실행(시도 K)."""
    run = processing_run(company_id, tag=tag)
    keys = tuple(key_at(i) for i in range(1, n + 1))
    planned = call(
        services.segments_planned,
        company_id=company_id,
        run_id=run.pk,
        attempt=K,
        step=STEP,
        keys=keys,
        now=NOW,
        lease_s=LEASE_S,
    )
    assert isinstance(planned, services.Recorded)
    parked = call(
        services.finish_run,
        company_id=company_id,
        run_id=run.pk,
        attempt=K,
        now=park_at,
        outcome=RunParkedOutcome(lease_s=LEASE_S),
    )
    assert parked == Finished("processing")
    return run


def claim(
    company_id: int,
    run_id: int,
    *,
    now: datetime = NOW,
    cap: int = 2,
    max_attempts: int = 3,
    policy: str = "pass_to_gather",
    run_attempt: int = K,
) -> Any:
    return call(
        services.segment_claim,
        company_id=company_id,
        run_id=run_id,
        run_attempt=run_attempt,
        now=now,
        lease_s=LEASE_S,
        parallel_max=cap,
        max_attempts=max_attempts,
        on_failure={STEP: policy},
    )


def end(
    company_id: int,
    run_id: int,
    got: SegmentClaimed,
    outcome: Any,
    *,
    now: datetime = NOW,
    cap: int = 2,
    policy: str = "pass_to_gather",
    run_attempt: int = K,
) -> Any:
    return call(
        services.segment_end,
        company_id=company_id,
        run_id=run_id,
        run_attempt=run_attempt,
        step=got.step,
        key_sha256=got.key_sha256,
        attempt=got.attempt,
        outcome=outcome,
        now=now,
        lease_s=LEASE_S,
        parallel_max=cap,
        on_failure=policy,
    )


def row(company_id: int, run_id: int) -> RunRow:
    return RunRow.for_company(company_id).get(pk=run_id)


def segment(company_id: int, run_id: int, n: int) -> RunSegmentRow:
    return RunSegmentRow.for_company(company_id).get(run_id=run_id, step=STEP, key_sha256=sha(n))


def done(n: int) -> EndDone:
    return EndDone(data={"v": n})


# ── 주차 ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_parking_keeps_processing_sets_parked_at_and_draws_the_lease(companies: tuple[int, int]) -> None:
    a, _ = companies
    park_at = NOW + timedelta(seconds=60)  # 계획(NOW — 그때 임대 NOW+330)보다 늦게 주차한다: 주차가 임대를 당겨야 한다
    run = parked_run(a, 3, park_at=park_at)
    got = row(a, run.pk)
    assert (got.status, got.parked_at, got.lease_expires_at) == (
        "processing",
        park_at,
        park_at + timedelta(seconds=LEASE_S),
    )
    assert (got.stalled_attempts, got.attempts) == (0, K)
    other = processing_run(a, attempt=1, tag="b")  # 남의 시도는 주차 못 함
    assert (
        call(
            services.finish_run,
            company_id=a,
            run_id=other.pk,
            attempt=K,
            now=NOW,
            outcome=RunParkedOutcome(lease_s=LEASE_S),
        )
        == Superseded()
    )


# ── T7 잡기 ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_claims_go_in_plan_order_up_to_the_cap_then_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 4)
    first, second = claim(a, run.pk), claim(a, run.pk)
    assert (first.position, second.position) == (0, 1)
    assert first == SegmentClaimed(step=STEP, position=0, key_sha256=sha(1), attempt=1)
    assert claim(a, run.pk) == NothingToClaim(wake=False)  # 상한 2
    one = segment(a, run.pk, 1)
    assert (one.status, one.attempts, one.started_at, one.lease_expires_at) == (
        "running",
        1,
        NOW,
        NOW + timedelta(seconds=LEASE_S),
    )
    assert claim(a, run.pk, cap=3).position == 2  # 분모: 상한이 크면 잡는다


@pytest.mark.django_db
def test_a_lapsed_lease_and_a_released_segment_are_taken_again(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 3)
    first = claim(a, run.pk)
    second = claim(a, run.pk)
    assert end(a, run.pk, second, EndReleased()) == Ended(wake=False, successor=True)
    assert segment(a, run.pk, 2).lease_expires_at is None and segment(a, run.pk, 2).status == "running"
    again = claim(a, run.pk)  # 놓은 2 가 계획 차례로 3 보다 앞
    assert (again.position, again.attempt) == (1, 2)
    later = NOW + timedelta(seconds=LEASE_S)  # 1 의 임대가 지났다
    retaken = claim(a, run.pk, now=later, cap=3)
    assert (retaken.position, retaken.attempt) == (first.position, 2)


@pytest.mark.django_db
def test_the_third_attempt_exhausts_and_the_last_segment_wakes_once(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 1)
    for attempt in (1, 2, 3):
        got = claim(a, run.pk)
        assert got.attempt == attempt
        assert end(a, run.pk, got, EndReleased()).wake is False
    woke = claim(a, run.pk)  # 잡을 수 있는 running 이 셋째 시도 뒤 — 소진, 마지막 구획이라 깨움(B1a)
    assert woke == NothingToClaim(wake=True)
    seg = segment(a, run.pk, 1)
    assert (seg.status, seg.error_code, seg.lease_expires_at) == ("failed", "attempts_exhausted", None)
    got = row(a, run.pk)
    assert (got.parked_at, got.lease_expires_at, got.progress_attempt) == (None, None, K)
    assert claim(a, run.pk) == Superseded()  # 깬 뒤는 주차 아님


@pytest.mark.django_db
def test_an_exhausted_segment_beside_a_live_lease_delays_the_claim(companies: tuple[int, int]) -> None:
    """RM1c ③ X5(검증 3 권고): 잡기가 소진 하나를 끝낸 뒤 남은 것이 임대 산 running 하나면 미룸을 준다 — 소진 수를 뺀
    unended(count.unended − len(plan.exhaust))가 alive 와 같아야 미룸이 선다."""
    a, _ = companies
    run = parked_run(a, 2)
    first = claim(a, run.pk)
    assert first.position == 0
    alive = claim(a, run.pk)  # 2 는 임대 산 채 돈다
    assert alive.position == 1
    got = first
    for attempt in (1, 2, 3):
        assert (got.position, got.attempt) == (0, attempt)
        end(a, run.pk, got, EndReleased())
        if attempt < 3:
            got = claim(a, run.pk)
    later = NOW + timedelta(seconds=10)
    assert claim(a, run.pk, now=later) == NothingToClaim(wake=False, delay=LEASE_S - 10 + 1)
    exhausted = segment(a, run.pk, 1)
    assert (exhausted.status, exhausted.error_code) == ("failed", "attempts_exhausted")
    assert segment(a, run.pk, 2).status == "running"


@pytest.mark.django_db
def test_another_run_attempt_or_an_unparked_run_is_superseded(companies: tuple[int, int]) -> None:
    a, b = companies
    run = parked_run(a, 2)
    assert claim(a, run.pk, run_attempt=K + 1) == Superseded()
    assert claim(b, run.pk) == Superseded()  # 남의 회사 = 없음
    plain = processing_run(a, tag="p")  # 주차하지 않은 processing — 지휘가 임대를 쥐고 도는 중
    RunRow.for_company(a).filter(pk=plain.pk).update(lease_expires_at=NOW + timedelta(seconds=LEASE_S))
    # 임대 NULL(깨웠는데 아직 안 잡음)은 RM1c ③′ M2 — test_executor_lost_notes 가 잰다
    assert claim(a, plain.pk) == Superseded()
    assert RunSegmentRow.for_company(a).filter(run_id=run.pk, status="running").count() == 0


@pytest.mark.django_db
def test_fail_run_takes_nothing_after_a_failure(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 4)
    first = claim(a, run.pk, policy="fail_run")
    claim(a, run.pk, policy="fail_run")
    assert end(a, run.pk, first, EndFailed(code="step_error"), policy="fail_run") == Ended(wake=True, successor=False)
    # 깬 뒤 다시 주차한 꼴을 만들어(다음 지휘가 오기 전 같은 시도라면) 잡기가 실패를 보고 안 잡는지 잰다
    RunRow.for_company(a).filter(pk=run.pk).update(parked_at=NOW)
    assert claim(a, run.pk, policy="fail_run", cap=4) == NothingToClaim(wake=False)
    assert claim(a, run.pk, policy="pass_to_gather", cap=4).position == 2  # 분모: 정책이 다르면 잡는다


# ── T8 끝냄 ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_an_old_note_of_a_retaken_segment_is_superseded_and_writes_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 2)
    old = claim(a, run.pk)
    later = NOW + timedelta(seconds=LEASE_S)
    new = claim(a, run.pk, now=later)
    assert (new.position, new.attempt) == (old.position, 2)
    assert end(a, run.pk, old, done(1)) == Superseded()
    seg = segment(a, run.pk, 1)
    assert (seg.status, seg.attempts, seg.data) == ("running", 2, None)
    assert end(a, run.pk, new, done(1), now=later).wake is False  # 분모: 새 시도는 쓴다
    assert segment(a, run.pk, 1).status == "done"
    with pytest.raises(RunUpdateError, match="다시 끝내려"):
        end(a, run.pk, new, done(1), now=later)  # 같은 시도로 두 번


@pytest.mark.django_db
def test_done_writes_data_octets_and_the_lease_goes(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 2)
    got = claim(a, run.pk)
    assert end(a, run.pk, got, EndDone(data={"z": 1, "a": "가"})) == Ended(wake=False, successor=True)
    seg = segment(a, run.pk, 1)
    assert (seg.status, seg.data, seg.data_octets, seg.lease_expires_at, seg.finished_at) == (
        "done",
        {"z": 1, "a": "가"},
        len('{"z": 1, "a": "가"}'.encode()),
        None,
        NOW,
    )
    assert list(seg.data or {}) == ["z", "a"]  # 쓴 열쇠 차례
    assert row(a, run.pk).progress_attempt == K


@pytest.mark.django_db
@pytest.mark.parametrize("step", [STEP, None])
def test_fatal_fails_the_run_and_its_step_and_unparks_without_waking(
    companies: tuple[int, int], step: str | None
) -> None:
    a, _ = companies
    run = parked_run(a, 3)
    got = claim(a, run.pk)
    assert end(a, run.pk, got, EndFatal(code="setup_error", step=step)) == Ended(wake=False, successor=False)
    after = row(a, run.pk)
    assert (after.status, after.error_code, after.failed_step, after.parked_at, after.lease_expires_at) == (
        "failed",
        "setup_error",
        step,
        None,
        None,
    )
    steps = {s.name: s.status for s in RunStepRow.for_company(a).filter(run_id=run.pk)}
    assert steps[STEP] == ("failed" if step else "pending")
    assert segment(a, run.pk, 1).status == "failed"
    assert claim(a, run.pk) == Superseded()  # 남은 구획은 안 잡힌다


@pytest.mark.django_db
def test_a_done_over_the_step_sum_is_fatal_step_output_invalid(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 2)
    first = claim(a, run.pk)
    RunSegmentRow.for_company(a).filter(run_id=run.pk, key_sha256=sha(2)).update(
        status="done", data={"v": 0}, data_octets=FANOUT_DATA_MAX_OCTETS - 5, attempts=1
    )
    assert end(a, run.pk, first, EndDone(data={"v": 12345})) == Ended(wake=False, successor=False)  # 13바이트
    after = row(a, run.pk)
    assert (after.status, after.error_code, after.failed_step) == ("failed", "step_output_invalid", STEP)


@pytest.mark.django_db
def test_take_and_finish_clear_parked_at(companies: tuple[int, int]) -> None:
    a, _ = companies
    for tag, outcome in (
        ("d", RunDone(results=(), files=())),
        ("f", RunFailed(step=None, code="internal", message="m")),
        ("q", RunDeferred()),
    ):
        run = parked_run(a, 1, tag=tag)
        assert call(services.finish_run, company_id=a, run_id=run.pk, attempt=K, now=NOW, outcome=outcome)
        assert row(a, run.pk).parked_at is None
    run = parked_run(a, 1, tag="t")
    later = NOW + timedelta(seconds=LEASE_S + 1)  # 쪽지를 다 잃어 임대가 지났다 → requeue 의 Take
    taken = call(services.claim_run, company_id=a, run_id=run.pk, now=later, lease_s=LEASE_S, max_attempts=3)
    assert isinstance(taken, services.Claimed) and taken.attempt == K + 1
    assert row(a, run.pk).parked_at is None
    assert claim(a, run.pk, now=later) == Superseded()  # k 의 쪽지


# ── T9 깨우기 한 번 ───────────────────────────────────────────────────


def first_sql(write: Any) -> str:
    with CaptureQueriesContext(connection) as seen:
        write()
    statements = [q["sql"] for q in seen.captured_queries if not q["sql"].startswith(("SAVEPOINT", "RELEASE"))]
    return statements[0]


@pytest.mark.django_db
def test_the_first_statement_of_claim_and_end_locks_the_run_row(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 2)
    got: list[Any] = []
    lock = first_sql(lambda: got.append(claim(a, run.pk)))
    assert lock.startswith('SELECT "run_runs".') and lock.endswith("FOR UPDATE")
    lock = first_sql(lambda: end(a, run.pk, got[0], done(1)))
    assert lock.startswith('SELECT "run_runs".') and lock.endswith("FOR UPDATE")


@pytest.mark.django_db
def test_the_last_three_ends_wake_once(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 3)
    got = [claim(a, run.pk, cap=3) for _ in range(3)]
    wakes = [end(a, run.pk, one, done(i)) for i, one in enumerate(got)]
    assert [w.wake for w in wakes] == [False, False, True]
    assert row(a, run.pk).parked_at is None


@pytest.mark.django_db
def test_fail_run_all_done_wakes_once(companies: tuple[int, int]) -> None:
    """fail_run 에서 실패가 없어도 마지막 done 이 깨운다(B1b — 「fail_run 은 실패만」 꼴의 깨우기 0번)."""
    a, _ = companies
    run = parked_run(a, 2)
    got = [claim(a, run.pk, policy="fail_run") for _ in range(2)]
    wakes = [end(a, run.pk, one, done(i), policy="fail_run").wake for i, one in enumerate(got)]
    assert wakes == [False, True]


@pytest.mark.django_db
def test_fail_run_two_failures_wake_once(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 3)
    got = [claim(a, run.pk, policy="fail_run", cap=3) for _ in range(3)]
    first = end(a, run.pk, got[0], EndFailed(code="step_error"), policy="fail_run")
    second = end(a, run.pk, got[1], EndFailed(code="step_error"), policy="fail_run")
    assert first == Ended(wake=True, successor=False)
    assert second == Superseded()  # 깬 뒤 — 돌던 구획의 산출은 버린다(행 running 남음)
    assert segment(a, run.pk, 2).status == "running"


@pytest.mark.django_db(transaction=True)
def test_while_another_connection_holds_the_run_row_an_end_writes_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = parked_run(a, 2)
    got = claim(a, run.pk)
    other = connections.create_connection("default")
    try:
        other.ensure_connection()
        other.set_autocommit(False)
        with other.cursor() as cursor:
            cursor.execute("SELECT id FROM run_runs WHERE id = %s FOR UPDATE", [run.pk])
        with pytest.raises(OperationalError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '200ms'")
            services.segment_end(
                company_id=a,
                run_id=run.pk,
                run_attempt=K,
                step=got.step,
                key_sha256=got.key_sha256,
                attempt=got.attempt,
                outcome=done(1),
                now=NOW,
                lease_s=LEASE_S,
                parallel_max=2,
                on_failure="pass_to_gather",
            )
    finally:
        other.rollback()
        other.close()
    seg = segment(a, run.pk, 1)
    assert (seg.status, seg.data) == ("running", None)
    assert end(a, run.pk, got, done(1)).wake is False  # 분모: 잠금이 풀리면 쓴다


# ── T10 SQL ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_next_attempt_compares_without_reading_data_and_the_first_inserts_once(
    companies: tuple[int, int],
) -> None:
    a, _ = companies
    run = processing_run(a)
    keys = tuple(key_at(i) for i in range(1, 6))
    kwargs: dict[str, Any] = {
        "company_id": a,
        "run_id": run.pk,
        "attempt": K,
        "step": STEP,
        "keys": keys,
        "now": NOW,
        "lease_s": LEASE_S,
    }
    with CaptureQueriesContext(connection) as first:
        call(services.segments_planned, **kwargs)
    inserts = [q["sql"] for q in first.captured_queries if q["sql"].startswith('INSERT INTO "run_segments"')]
    assert len(inserts) == 1
    assert RunSegmentRow.for_company(a).filter(run_id=run.pk).count() == 5
    with CaptureQueriesContext(connection) as again:
        assert isinstance(call(services.segments_planned, **kwargs), services.Recorded)
    reads = [q["sql"] for q in again.captured_queries if 'FROM "run_segments"' in q["sql"]]
    assert reads and all('"run_segments"."data"' not in q and '"run_segments"."key"' not in q for q in reads)
    assert not [q for q in again.captured_queries if q["sql"].startswith("INSERT")]


@pytest.mark.django_db
def test_segment_counts_is_one_query_without_data(companies: tuple[int, int]) -> None:
    a, b = companies
    run = parked_run(a, 3)
    got = claim(a, run.pk)
    end(a, run.pk, got, done(1), now=NOW + timedelta(seconds=7))
    claim(a, run.pk)
    with CaptureQueriesContext(connection) as seen:
        counts = selectors.segment_counts(company_id=a, run_id=run.pk)
    assert len(seen.captured_queries) == 1
    assert '"run_segments"."data"' not in seen.captured_queries[0]["sql"]
    one = counts[STEP]
    assert (one.pending, one.running, one.done, one.failed) == (1, 1, 1, 0)
    assert (one.first_started_at, one.last_finished_at) == (NOW, NOW + timedelta(seconds=7))
    assert selectors.segment_counts(company_id=b, run_id=run.pk) == {}
