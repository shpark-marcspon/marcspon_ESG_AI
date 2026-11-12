"""구획 기록 표 run_segments(RM1a ② — T7)를 진짜 DB 로 잰다. 업무 층(주인 역할 — 권한은 tests/security/test_owner.py).

재는 것: 남의 회사 실행에 걸면 23503(같은 회사 FK) · CHECK(상태·차례·시도·sha 꼴·상태와 칸의 짝·data 크기) ·
UNIQUE 둘((run, step, sha)·(run, step, position)) · 표는 for_company 로만 열린다. 값은 지어낸 것이다.
"""

from typing import Any

import pytest
from django.db import IntegrityError, transaction

from esgapi.core.isolation.managers import UnscopedQueryError
from esgapi.core.models import DocumentRow
from esgapi.runs.models import RUN_SEGMENT_DATA_MAX_OCTETS, RunRow, RunSegmentRow

pytestmark = pytest.mark.django_db

SHA = "a" * 64
KEY = {"kind": "block", "span": "b1", "documentSha256": None, "parserVersion": None}


def a_run(company_id: int) -> RunRow:
    document = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name="a.pdf",
        storage_key=f"documents/{company_id}/a.pdf",
        size_bytes=1,
        status="uploaded",
    )
    return RunRow.for_company(company_id).create(
        company_id=company_id,
        document_id=document.pk,
        module="probe",
        flow_id="probe.segmented@1",
        status="processing",
        created_by_user_id=7,
    )


def segment(company_id: int, run_id: int, **extra: Any) -> RunSegmentRow:
    values: dict[str, Any] = {
        "step": "spread",
        "position": 0,
        "kind": "block",
        "key": KEY,
        "key_sha256": SHA,
        "status": "pending",
        **extra,
    }
    return RunSegmentRow.for_company(company_id).create(company_id=company_id, run_id=run_id, **values)


def refused(make: Any) -> tuple[str, str]:
    """세이브포인트 안에서 만들어 보고 (SQLSTATE, 제약 이름)."""
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        make()
    cause: Any = caught.value.__cause__
    return str(cause.sqlstate), str(cause.diag.constraint_name)


def test_a_segment_cannot_point_at_another_companys_run(companies: tuple[int, int]) -> None:
    a, b = companies
    b_run = a_run(b)
    assert refused(lambda: segment(a, b_run.pk)) == ("23503", "run_segments_run_id_same_company_fk")
    assert segment(b, b_run.pk).company_id == b  # 분모: 같은 회사면 들어간다


@pytest.mark.parametrize(
    ("extra", "constraint"),
    [
        ({"status": "waiting"}, "run_segments_status_check"),
        ({"position": -1}, "run_segments_position_check"),
        ({"attempts": -1}, "run_segments_attempts_check"),
        ({"key_sha256": "A" * 64}, "run_segments_key_sha256_check"),
        ({"key_sha256": "a" * 63}, "run_segments_key_sha256_check"),
        ({"status": "done"}, "run_segments_status_fields_check"),  # done 인데 data 없음
        ({"status": "done", "data": {}, "error_code": "x"}, "run_segments_status_fields_check"),
        ({"status": "failed"}, "run_segments_status_fields_check"),  # failed 인데 code 없음
        ({"status": "failed", "error_code": "x", "data": {}}, "run_segments_status_fields_check"),
        ({"status": "running", "data": {}}, "run_segments_status_fields_check"),
        ({"status": "pending", "error_code": "x"}, "run_segments_status_fields_check"),
        (
            {"status": "done", "data": {"x": "a" * RUN_SEGMENT_DATA_MAX_OCTETS}},
            "run_segments_data_size_check",
        ),
    ],
)
def test_the_checks_refuse_what_the_runner_would_not_write(
    companies: tuple[int, int], extra: dict[str, Any], constraint: str
) -> None:
    a, _ = companies
    run = a_run(a)
    assert refused(lambda: segment(a, run.pk, **extra)) == ("23514", constraint)


def test_the_status_and_field_pairs_that_are_allowed(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = a_run(a)
    segment(a, run.pk, position=0, key_sha256="0" * 64, status="pending")
    segment(a, run.pk, position=1, key_sha256="1" * 64, status="running", attempts=1)
    segment(a, run.pk, position=2, key_sha256="2" * 64, status="done", data={"x": "a" * 1000})
    segment(a, run.pk, position=3, key_sha256="3" * 64, status="failed", error_code="made_up_code")
    assert RunSegmentRow.for_company(a).filter(run_id=run.pk).count() == 4  # 분모


def test_the_unique_keys(companies: tuple[int, int]) -> None:
    a, _ = companies
    run = a_run(a)
    segment(a, run.pk)
    assert refused(lambda: segment(a, run.pk, position=1)) == ("23505", "run_segments_run_step_sha_uniq")
    assert refused(lambda: segment(a, run.pk, key_sha256="b" * 64)) == ("23505", "run_segments_run_step_position_uniq")
    segment(a, run.pk, step="spread_again")  # 분모: 다른 단계면 같은 열쇠·차례도 된다
    segment(a, a_run_second(a).pk)  # 다른 실행도 된다


def a_run_second(company_id: int) -> RunRow:
    first = RunRow.for_company(company_id).first()
    assert first is not None
    return RunRow.for_company(company_id).create(
        company_id=company_id,
        document_id=first.document_id,
        module="probe",
        flow_id="probe.segmented@1",
        status="queued",
        created_by_user_id=7,
    )


def test_the_table_opens_only_through_for_company() -> None:
    with pytest.raises(UnscopedQueryError):
        list(RunSegmentRow.objects.all())
