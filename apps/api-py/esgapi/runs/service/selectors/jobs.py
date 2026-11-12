"""읽기. 일감(표 run_jobs)을 잠가 읽기, 하나 읽기, 다시 넣을 것 고르기. 쓰지 않는다.

    lock_job(company_id, job_id)                         잡기의 ①: 그 행을 FOR UPDATE 로 읽는다(ORM 행을 돌려준다)
    find_job(company_id, job_id)                         하나 읽기(바깥에 내줄 꼴 Job 으로)
    stale_jobs(company_id, now, queued_older_than_s)      임대가 지난 `processing` 과 오래 머문 `queued`

★ 조회마다 회사 조건을 적는다. run_jobs 를 읽는 문은 `_jobs` 하나다(core/service/selectors/documents.py 와 같은 꼴).
  JobRow 의 기본 매니저는 회사를 정하지 않은 조회를 거절한다(core/isolation). DB 의 RLS 는 없다.
★ 잠그지 않는 읽기는 Job 을, 잠그는 읽기는 ORM 행을 돌려준다: 잠근 행은 Service 가 이어서 판정하고 쓰는 재료다
  (lease_expires_at 처럼 Job 에 없는 칸을 읽는다).
★ Job·job_of 는 core/service/selectors/documents.py 의 것이다(문서 상태 보기가 같은 꼴을 내보낸다).
"""

from datetime import datetime, timedelta

from django.db import connection
from django.db.models import Q, QuerySet

from esgapi.core.service.selectors.documents import Job, job_of
from esgapi.runs.models import JobRow


class NotInTransactionError(Exception):
    """트랜잭션 밖에서 불렀다(stale_jobs, 일감 쓰기의 잡기·끝내기)."""


def _jobs(company_id: int) -> "QuerySet[JobRow]":
    """그 회사의 일감 행. 이 파일에서 run_jobs 를 읽는 문은 여기 하나다."""
    return JobRow.for_company(company_id)


def lock_job(*, company_id: int, job_id: int) -> JobRow | None:
    """그 회사의 그 일감 행을 FOR UPDATE 로 읽는다. 변경 트랜잭션 안에서만 부른다(밖이면 Django 가 던진다)."""
    return _jobs(company_id).select_for_update().filter(pk=job_id).first()


def find_job(*, company_id: int, job_id: int) -> Job | None:
    """그 회사의 그 일감. 없으면(남의 것이어도) None. 잠그지 않는다."""
    row = _jobs(company_id).filter(pk=job_id).first()
    return None if row is None else job_of(row)


def stale_jobs(*, company_id: int, now: datetime, queued_older_than_s: int) -> tuple[Job, ...]:
    """쪽지를 잃었을 수 있는 일감: 임대가 지난(또는 임대가 없는) `processing` 과, 그만큼 오래 머문 `queued`.

    고르기만 한다(잠그지 않는다). 같은 일감이 두 번 넣어져도 잡기가 거른다.
    """
    if not connection.in_atomic_block:
        raise NotInTransactionError("stale_jobs 는 transaction.atomic() 안에서만 부른다")
    lapsed = Q(status="processing") & (Q(lease_expires_at__lte=now) | Q(lease_expires_at__isnull=True))
    waiting = Q(status="queued", updated_at__lte=now - timedelta(seconds=queued_older_than_s))
    return tuple(job_of(row) for row in _jobs(company_id).filter(lapsed | waiting).order_by("created_at", "id"))
