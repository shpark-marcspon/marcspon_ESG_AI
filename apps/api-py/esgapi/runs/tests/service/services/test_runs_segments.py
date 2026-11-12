"""구획 기록의 쓰기(runs/service/services/runs.py 의 segments_planned·segment_started·segment_finished·segment_failed)와
읽기(selectors 의 segment_rows·ended_segments)를 진짜 DB 로 잰다. 업무 층(RM1a ② — T9).

재는 것: 첫 계획은 전부 pending · 같은 계획 두 번째는 0행 · 다른 계획은 PlanMismatch(쓰지 않음) · 남의 시도는 Superseded
(쓰지 않음) · 전이표(pending→running→done|failed, running→running 은 attempts +1) · 끝난 구획에 쓰기는 RunUpdateError ·
진행(progress_attempt)은 끝·실패에만 · ended_segments 는 done·failed 둘 다(단계 → sha) · 남의 회사 실행은 「없음」.
열쇠·값은 지어낸 것이다.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import transaction

from esgapi.core.flows.types import SegmentFailure, SegmentKey, SegmentOutput, segment_key_fields, segment_key_sha256
from esgapi.core.models import DocumentRow
from esgapi.runs.models import RunRow, RunSegmentRow
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.services import runs as services
from esgapi.runs.service.services.runs import PlanMismatch, Recorded, RunUpdateError, Superseded

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
LEASE_S = 330
STEP = "spread"


def key_at(n: int) -> SegmentKey:
    return SegmentKey(kind="block", span=f"b{n}", document_sha256=None, parser_version="p1")


KEYS = tuple(key_at(n) for n in range(1, 4))


def processing_run(company_id: int, *, attempt: int = 1) -> RunRow:
    document = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name="a.pdf",
        storage_key=f"documents/{company_id}/a-{attempt}.pdf",
        size_bytes=1,
        status="uploaded",
    )
    return RunRow.for_company(company_id).create(
        company_id=company_id,
        document_id=document.pk,
        module="probe",
        flow_id="probe.segmented@1",
        status="processing",
        attempts=attempt,
        created_by_user_id=7,
    )


def call(write: Any, **kwargs: Any) -> Any:
    with transaction.atomic():
        return write(**kwargs)


def plan(company_id: int, run_id: int, keys: tuple[SegmentKey, ...] = KEYS, attempt: int = 1) -> Any:
    return call(
        services.segments_planned,
        company_id=company_id,
        run_id=run_id,
        attempt=attempt,
        step=STEP,
        keys=keys,
        now=NOW,
        lease_s=LEASE_S,
    )


def start(company_id: int, run_id: int, n: int, attempt: int = 1) -> Any:
    return call(
        services.segment_started,
        company_id=company_id,
        run_id=run_id,
        attempt=attempt,
        step=STEP,
        key_sha256=segment_key_sha256(key_at(n)),
        now=NOW,
        lease_s=LEASE_S,
    )


def finish(company_id: int, run_id: int, n: int, attempt: int = 1) -> Any:
    return call(
        services.segment_finished,
        company_id=company_id,
        run_id=run_id,
        attempt=attempt,
        step=STEP,
        key_sha256=segment_key_sha256(key_at(n)),
        data={"square": n * n, "z": 0, "a": 1},
        now=NOW,
        lease_s=LEASE_S,
    )


def fail(company_id: int, run_id: int, n: int, attempt: int = 1) -> Any:
    return call(
        services.segment_failed,
        company_id=company_id,
        run_id=run_id,
        attempt=attempt,
        step=STEP,
        key_sha256=segment_key_sha256(key_at(n)),
        error_code="made_up_code",
        now=NOW,
        lease_s=LEASE_S,
    )


def statuses(company_id: int, run_id: int) -> list[tuple[int, str, int]]:
    return [
        (s.position, s.status, s.attempts)
        for s in selectors.segment_rows(company_id=company_id, run_id=run_id, step=STEP)
    ]


def test_the_first_plan_writes_every_segment_pending_in_plan_order(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = processing_run(a)
    assert plan(a, run.pk) == Recorded()
    rows = selectors.segment_rows(company_id=a, run_id=run.pk, step=STEP)
    assert [(s.position, s.status, s.attempts, s.kind) for s in rows] == [(n, "pending", 0, "block") for n in range(3)]
    assert [s.key_sha256 for s in rows] == [segment_key_sha256(k) for k in KEYS]
    assert [s.key for s in rows] == [segment_key_fields(k) for k in KEYS]
    run.refresh_from_db()
    assert run.progress_attempt is None  # 계획은 진행이 아니다


def test_the_same_plan_again_writes_nothing_and_a_different_plan_is_a_mismatch(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = processing_run(a)
    plan(a, run.pk)
    assert plan(a, run.pk) == Recorded()
    assert RunSegmentRow.for_company(a).filter(run_id=run.pk).count() == 3
    assert plan(a, run.pk, keys=(KEYS[1], KEYS[0], KEYS[2])) == PlanMismatch(stored=3, planned=3)
    assert plan(a, run.pk, keys=KEYS[:2]) == PlanMismatch(stored=3, planned=2)
    assert RunSegmentRow.for_company(a).filter(run_id=run.pk).count() == 3  # 쓰지 않았다


def test_the_transitions_and_the_progress_marks(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = processing_run(a)
    plan(a, run.pk)
    assert start(a, run.pk, 1) == Recorded()
    assert start(a, run.pk, 1) == Recorded()  # running → running(새 시도)
    run.refresh_from_db()
    assert run.progress_attempt is None  # 시작은 진행이 아니다
    assert finish(a, run.pk, 1) == Recorded()
    run.refresh_from_db()
    assert run.progress_attempt == 1
    start(a, run.pk, 2)
    assert fail(a, run.pk, 2) == Recorded()
    assert statuses(a, run.pk) == [(0, "done", 2), (1, "failed", 1), (2, "pending", 0)]
    rows = selectors.segment_rows(company_id=a, run_id=run.pk, step=STEP)
    assert rows[0].data == {"square": 1, "z": 0, "a": 1}  # 쓴 열쇠 차례 그대로
    assert list(rows[0].data or {}) == ["square", "z", "a"]
    assert (rows[0].error_code, rows[1].error_code, rows[1].data) == (None, "made_up_code", None)
    assert rows[0].started_at == NOW and rows[0].finished_at == NOW


@pytest.mark.parametrize("write", [start, finish, fail], ids=["start", "finish", "fail"])
@pytest.mark.parametrize("ended", ["done", "failed"])
def test_writing_to_an_ended_segment_is_an_update_error(companies: tuple[int, int], write: Any, ended: str) -> None:
    a, _ = companies
    run = processing_run(a)
    plan(a, run.pk)
    start(a, run.pk, 1)
    (finish if ended == "done" else fail)(a, run.pk, 1)
    with pytest.raises(RunUpdateError):
        write(a, run.pk, 1)
    assert statuses(a, run.pk)[0][1] == ended  # 되돌려졌다


@pytest.mark.parametrize("write", [finish, fail], ids=["finish", "fail"])
def test_finishing_a_pending_segment_is_an_update_error(companies: tuple[int, int], write: Any) -> None:
    a, _ = companies
    run = processing_run(a)
    plan(a, run.pk)
    with pytest.raises(RunUpdateError):
        write(a, run.pk, 1)


def test_another_attempt_writes_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = processing_run(a, attempt=2)
    assert plan(a, run.pk, attempt=1) == Superseded()
    assert RunSegmentRow.for_company(a).filter(run_id=run.pk).count() == 0
    plan(a, run.pk, attempt=2)
    assert start(a, run.pk, 1, attempt=1) == Superseded()
    start(a, run.pk, 1, attempt=2)
    assert finish(a, run.pk, 1, attempt=1) == Superseded()
    assert fail(a, run.pk, 1, attempt=1) == Superseded()
    assert statuses(a, run.pk)[0] == (0, "running", 1)


def test_ended_segments_has_done_and_failed_by_step_and_sha(companies: tuple[int, int]) -> None:
    a, b = companies
    run = processing_run(a)
    assert selectors.ended_segments(company_id=a, run_id=run.pk) == {}  # 계획 전
    plan(a, run.pk)
    assert selectors.ended_segments(company_id=a, run_id=run.pk) == {}  # 계획됨, 끝난 것 0
    start(a, run.pk, 1)
    finish(a, run.pk, 1)
    start(a, run.pk, 2)
    fail(a, run.pk, 2)
    start(a, run.pk, 3)  # running 은 끝나지 않았다
    assert selectors.ended_segments(company_id=a, run_id=run.pk) == {
        STEP: {
            segment_key_sha256(key_at(1)): SegmentOutput(data={"square": 1, "z": 0, "a": 1}),
            segment_key_sha256(key_at(2)): SegmentFailure(error_code="made_up_code"),
        }
    }
    assert selectors.ended_segments(company_id=b, run_id=run.pk) == {}  # 남의 회사는 「없음」
    assert selectors.segment_rows(company_id=b, run_id=run.pk, step=STEP) == ()
