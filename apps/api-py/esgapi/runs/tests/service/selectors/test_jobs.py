"""일감(run_jobs)의 selector·service·명령이 남의 회사 일감을 안 보고 안 고치는가. 업무 층(DB 에 RLS 는 없다).

MARC-ISSUE-177(밴드 X1b-2b): core/tests/test_selectors_tenant.py 에서 runs 의 일감 selector·service·명령을 재는 함수
여섯을 그대로 옮겼다(함수·도우미는 바이트 그대로 — 머리 글은 옛 파일의 것을 잇는다).
★ 무효 조건: 이 층은 파이썬 쪽 조건(Selector 의 `company_id` 조건과 Service 의 쓰기 조건)과 DB 의 같은 회사
  외래 키를 잰다. 앱 역할 연결의 경계는 보안 층(tests/security)이 잰다.
★ 회사 id 는 고정물(companies)이 준다(박아 두지 않는다). 문서·일감 id 는 숫자라 셀 수 있다 → 이웃 id(±1·±2)도 넣어 본다.
★ SQL 의 글자를 보는 테스트는 Django 가 내는 문의 꼴(`"표"."company_id" = <값>`)에 기댄다.
"""

import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import psycopg
import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from esgapi.config.env import BrokerSettings
from esgapi.core.calc.documents import JOB_KINDS
from esgapi.core.models import DocumentRow
from esgapi.core.resources import queue as hooks
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.selectors.documents import DocumentWithJobs, Job
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import JobRow
from esgapi.runs.service.selectors import jobs as job_selectors
from esgapi.runs.service.services.jobs import (
    Claimed,
    Deferred,
    Done,
    Failed,
    Finished,
    JobNotFound,
    JobUpdateError,
    Superseded,
    claim_job,
    finish_job,
)
from tests.support.patches import record_enqueued

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
LEASE_S = 90
MAX = 3
BROKER = BrokerSettings(
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="http://queue:9324/000000000000/esg-jobs",
    secure=False,
)


def no_enqueue(**_: Any) -> None:
    """큐에 넣지 않는다(이 층에는 브로커가 없다)."""


def seed(company_id: int, **job: Any) -> tuple[int, int]:
    """그 회사의 올림이 확인된 문서 하나와 그 분해 일감(queued) 하나. (문서 id, 일감 id). `job` 은 일감의 칸."""
    storage = FakeStorage()
    created = services.create_document(
        company_id=company_id,
        uploaded_by="user-1",
        file_name="a.pdf",
        size_bytes=5,
        max_upload_bytes=1000,
        storage=storage,
    )
    assert isinstance(created, services.DocumentCreated)
    storage.put(created.document.storage_key, b"12345")
    document_id = created.document.id
    confirmed = services.confirm_upload(
        company_id=company_id,
        document_id=document_id,
        storage=storage,
        now=NOW - timedelta(hours=1),
        enqueue=no_enqueue,
    )
    assert isinstance(confirmed, services.UploadConfirmed)
    job_id = confirmed.jobs[0].id
    JobRow.unscoped.filter(pk=job_id).update(updated_at=NOW - timedelta(hours=1), **job)
    return document_id, job_id


def refuse_foreign_job(document_id: int, company_id: int, **job: Any) -> None:
    """남의 문서에 일감을 ORM 으로 바로 걸려 한다. DB 가 그 문에서 거절한다(23503). 세이브포인트라 바깥은 산다."""
    fields: dict[str, Any] = {"kind": JOB_KINDS[0], "status": "queued", "attempts": 0, **job}
    with pytest.raises(IntegrityError) as refused, transaction.atomic():
        JobRow.unscoped.create(company_id=company_id, document_id=document_id, **fields)
    cause = refused.value.__cause__
    assert isinstance(cause, psycopg.Error)
    assert cause.sqlstate == "23503"


def job_row(job_id: int) -> dict[str, Any]:
    return JobRow.unscoped.filter(pk=job_id).values().get()


def sha256_of(document_id: int) -> str | None:
    return DocumentRow.unscoped.values_list("sha256", flat=True).get(pk=document_id)


def claim(job_id: int, company_id: int) -> Any:
    return claim_job(company_id=company_id, job_id=job_id, now=NOW, lease_s=LEASE_S, max_attempts=MAX)


def test_the_lock_reads_name_the_tenant_and_lock(companies: tuple[int, int]) -> None:
    """잠가 읽는 문 둘이 낸 SQL: 그 표의 회사 조건이 있고 FOR UPDATE 로 끝난다. 무효 조건: 글자만 봤다."""
    a, _ = companies
    a_document, a_job = seed(a)
    with CaptureQueriesContext(connection) as captured:
        assert selectors.lock_document(company_id=a, document_id=a_document) is not None
        assert job_selectors.lock_job(company_id=a, job_id=a_job) is not None
    statements = [query["sql"] for query in captured.captured_queries]
    assert len(statements) == 2, statements  # 분모: 문 둘
    for table, text in zip(("core_documents", "run_jobs"), statements, strict=True):
        assert f'FROM "{table}"' in text, text
        assert re.search(rf'"{table}"\."company_id" = {a}\b', text), text  # \b: A 가 1 이면 10 은 아니다
        assert text.rstrip().endswith("FOR UPDATE"), text


# ── 일감 ──


def test_a_job_is_claimed_only_under_its_tenant(companies: tuple[int, int]) -> None:
    a, b = companies
    _, a_job = seed(a)
    _, b_job = seed(b)
    assert JobRow.unscoped.count() == 2  # 분모: A 것 하나, B 것 하나
    before = job_row(a_job)

    assert claim(a_job, b) == JobNotFound()
    assert job_row(a_job) == before
    # 이웃 id(±1·±2)를 B 의 이름으로 잡으려 하면 B 의 것 하나만 잡힌다(A 의 행은 그대로).
    candidates = sorted(n for n in range(min(a_job, b_job) - 2, max(a_job, b_job) + 3) if n > 0 and n != b_job)
    assert a_job in candidates  # 분모
    assert [n for n in candidates if claim(n, b) != JobNotFound()] == []
    assert job_row(a_job) == before

    claimed = claim(a_job, a)
    assert isinstance(claimed, Claimed)
    assert (claimed.job.company_id, claimed.job.status, claimed.attempt) == (a, "processing", 1)
    assert claimed.document.company_id == a


def test_a_job_is_finished_only_under_its_tenant(companies: tuple[int, int]) -> None:
    a, b = companies
    a_document, a_job = seed(a, status="processing", attempts=1, lease_expires_at=NOW + timedelta(seconds=LEASE_S))
    before = job_row(a_job)

    for outcome in (Done({"pages": 1}, "a" * 64), Failed("rejected", "x"), Deferred()):  # 세 갈래 모두
        finished = finish_job(company_id=b, job_id=a_job, attempt=1, now=NOW, outcome=outcome)
        assert finished == Superseded(), outcome
        assert job_row(a_job) == before, outcome
    assert sha256_of(a_document) is None

    # 같은 시도를 주인의 이름으로 부르면 끝난다(위의 0행은 시도나 상태가 틀려서가 아니다).
    done = finish_job(company_id=a, job_id=a_job, attempt=1, now=NOW, outcome=Done({"pages": 1}, "a" * 64))
    assert done == Finished()
    assert (job_row(a_job)["status"], sha256_of(a_document)) == ("done", "a" * 64)


def test_done_does_not_write_another_tenants_document(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    """A 의 문서에 B 의 일감은 DB 가 걸지 못하게 한다(받침 ⑤). 그래도 끝내기의 문서 갱신이 B 의 조건인지 잰다:
    B 의 일감을 읽은 값이 A 의 문서를 가리킨다고 바꿔 끼우고 B 의 이름으로 Done 으로 끝내려 한다
    → 일감은 1행, 문서는 0행 → 오류, 되돌려진다.
    """
    a, b = companies
    a_document, _ = seed(a)
    refuse_foreign_job(
        a_document, b, status="processing", attempts=1, lease_expires_at=NOW + timedelta(seconds=LEASE_S)
    )
    b_document, b_job = seed(b, status="processing", attempts=1, lease_expires_at=NOW + timedelta(seconds=LEASE_S))
    before = job_row(b_job)
    real_find_job = job_selectors.find_job

    def pointing_at_a(*, company_id: int, job_id: int) -> Job | None:
        found = real_find_job(company_id=company_id, job_id=job_id)
        return None if found is None else replace(found, document_id=a_document)

    monkeypatch.setattr(job_selectors, "find_job", pointing_at_a)

    with pytest.raises(JobUpdateError, match="core_documents 의 갱신이 0행"), transaction.atomic():
        finish_job(company_id=b, job_id=b_job, attempt=1, now=NOW, outcome=Done({"pages": 1}, "a" * 64))
    assert (sha256_of(a_document), sha256_of(b_document)) == (None, None)
    assert job_row(b_job) == before  # 일감의 `done` 도 되돌려졌다(`processing` 그대로)


def test_stale_jobs_and_requeue_see_one_tenant(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> None:
    from esgapi.runs.management.commands import requeue_jobs

    lapsed: dict[str, Any] = {"status": "processing", "attempts": 1, "lease_expires_at": NOW - timedelta(seconds=1)}
    a, b = companies
    _, a_job = seed(a, **lapsed)
    _, b_job = seed(b, **lapsed)
    assert JobRow.unscoped.count() == 2  # 분모: 임대가 지난 일감이 회사마다 하나

    def stale(company_id: int) -> list[int]:
        return [job.id for job in job_selectors.stale_jobs(company_id=company_id, now=NOW, queued_older_than_s=LEASE_S)]

    assert stale(a) == [a_job]
    assert stale(b) == [b_job]

    sent = record_enqueued(monkeypatch)
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    monkeypatch.setattr(requeue_jobs, "now", lambda: NOW)
    out, err = StringIO(), StringIO()
    call_command("requeue_jobs", "--tenant", str(a), stdout=out, stderr=err)
    assert sent == [{"company_id": a, "job_id": a_job, "kind": JOB_KINDS[0]}]
    assert out.getvalue().splitlines()[-1] == "고른 수 1 · 넣은 수 1 · 실패한 수 0"
    assert err.getvalue() == ""

    # B 의 이름으로 부르면 B 것만 나간다(명령이 회사를 상수로 넘기면 여기가 틀린다).
    sent.clear()
    call_command("requeue_jobs", "--tenant", str(b), stdout=StringIO(), stderr=StringIO())
    assert sent == [{"company_id": b, "job_id": b_job, "kind": JOB_KINDS[0]}]


# ── SQL 의 글자 ──


def test_every_statement_on_the_two_tables_names_the_tenant(companies: tuple[int, int]) -> None:
    """올림 확인 → 상태 보기 → 잡기 → 끝내기(Done) → 고르기가 두 표에 낸 SELECT·UPDATE 전부에 회사 조건이 있다.

    무효 조건: 글자만 봤다(조건의 값이 옳은지는 위의 테스트들이 잰다). INSERT 는 세지 않는다(company_id 가 값이다).
    """
    a, _ = companies
    storage = FakeStorage()
    created = services.create_document(
        company_id=a,
        uploaded_by="user-1",
        file_name="a.pdf",
        size_bytes=5,
        max_upload_bytes=1000,
        storage=storage,
    )
    assert isinstance(created, services.DocumentCreated)
    storage.put(created.document.storage_key, b"12345")
    document_id = created.document.id

    with CaptureQueriesContext(connection) as captured:
        confirmed = services.confirm_upload(
            company_id=a, document_id=document_id, storage=storage, now=NOW, enqueue=no_enqueue
        )
        assert isinstance(confirmed, services.UploadConfirmed)
        job_id = confirmed.jobs[0].id
        assert isinstance(selectors.get_document(company_id=a, document_id=document_id), DocumentWithJobs)
        assert isinstance(claim(job_id, a), Claimed)
        done = Done({"pages": 1}, "a" * 64)
        assert finish_job(company_id=a, job_id=job_id, attempt=1, now=NOW, outcome=done) == Finished()
        assert job_selectors.stale_jobs(company_id=a, now=NOW, queued_older_than_s=LEASE_S) == ()

    statements = [
        text
        for text in (query["sql"] for query in captured.captured_queries)
        if text.startswith(("SELECT", "UPDATE")) and ('"core_documents"' in text or '"run_jobs"' in text)
    ]
    # 분모: 올림 확인 5(SELECT·SELECT FOR UPDATE·UPDATE·SELECT·SELECT) · 상태 보기 2 · 잡기 4 · 끝내기 3 · 고르기 1
    assert len(statements) == 15, statements
    assert len([text for text in statements if text.startswith("UPDATE")]) == 4, statements
    assert len([text for text in statements if text.rstrip().endswith("FOR UPDATE")]) == 2, statements
    missing = [text for text in statements if not re.search(rf'\."company_id" = {a}\b', text)]
    assert missing == []
