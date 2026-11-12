"""주인 역할의 연결에서도 남의 문서·일감이 안 나오고 안 고쳐지는가. 업무 층(DB 에 RLS 는 없다).

★ 무효 조건: 이 층은 파이썬 쪽 조건(Selector 의 `company_id` 조건과 Service 의 쓰기 조건)과 DB 의 같은 회사
  외래 키를 잰다. 앱 역할 연결의 경계는 보안 층(tests/security)이 잰다.
★ 남의 회사의 것은 같은 길(서비스)로 한 벌 더 심는다. 남의 문서에 건 일감은 만들 수 없다: ORM 으로 넣으려 하면
  DB 의 같은 회사 외래 키(받침 ⑤, migrations/0001)가 그 문에서 거절한다(23503). 그 거절도 여기서 잰다.
★ 회사 id 는 고정물(companies)이 준다(박아 두지 않는다). 문서·일감 id 는 숫자라 셀 수 있다 → 이웃 id(±1·±2)도 넣어 본다.
★ SQL 의 글자를 보는 테스트는 Django 가 내는 문의 꼴(`"표"."company_id" = <값>`)에 기댄다.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from django.db import IntegrityError, transaction

from esgapi.core.calc.documents import JOB_KINDS
from esgapi.core.models import DocumentRow
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.selectors.documents import DocumentNotFound, DocumentWithJobs
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import JobRow

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
Capture = Callable[..., AbstractContextManager[list[Callable[[], Any]]]]


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


# ── 문서 ──


def test_a_document_is_found_only_by_its_tenant(companies: tuple[int, int]) -> None:
    a, b = companies
    a_document, _ = seed(a)
    b_document, b_job = seed(b)
    assert DocumentRow.unscoped.count() == 2  # 분모: A 것 하나, B 것 하나

    found = selectors.find_document(company_id=a, document_id=a_document)
    assert found is not None and (found.id, found.company_id) == (a_document, a)
    assert selectors.find_document(company_id=b, document_id=a_document) is None

    seen = selectors.get_document(company_id=a, document_id=a_document)
    assert isinstance(seen, DocumentWithJobs) and seen.document.id == a_document
    assert selectors.get_document(company_id=b, document_id=a_document) == DocumentNotFound()

    locked = selectors.lock_document(company_id=a, document_id=a_document)
    assert locked is not None and (locked.pk, locked.company_id) == (a_document, a)
    assert selectors.lock_document(company_id=b, document_id=a_document) is None

    # B 의 눈으로도 본다: B 는 자기 문서와 그 일감을 받는다(부르는 쪽이 회사를 상수로 넘기면 여기가 빈다).
    theirs = selectors.get_document(company_id=b, document_id=b_document)
    assert isinstance(theirs, DocumentWithJobs) and theirs.document.id == b_document
    assert [job.id for job in theirs.jobs] == [b_job]

    # 숫자 id 는 셀 수 있다: 두 문서 id 와 그 이웃(±1·±2)을 B 의 눈으로 넣어 보면 B 의 것 하나만 나온다.
    candidates = sorted(n for n in range(min(a_document, b_document) - 2, max(a_document, b_document) + 3) if n > 0)
    assert a_document in candidates and b_document in candidates  # 분모
    assert [n for n in candidates if selectors.find_document(company_id=b, document_id=n) is not None] == [b_document]
    assert [n for n in candidates if selectors.find_document(company_id=a, document_id=n) is not None] == [a_document]


def test_another_tenants_job_on_my_document_is_refused_and_never_listed(
    django_capture_on_commit_callbacks: Capture, companies: tuple[int, int]
) -> None:
    """B 가 A 의 문서에 일감을 걸려 하면 DB 가 거절한다(받침 ⑤). A 가 보는 일감과 A 가 큐에 넣는 쪽지는 A 의 것뿐이고,
    B 의 눈에는 A 의 문서에 걸린 일감이 하나도 없다. B 의 일감은 B 의 문서에 있다(분모).
    """
    a, b = companies
    a_document, a_job = seed(a)
    b_document, b_job = seed(b)
    refuse_foreign_job(a_document, b)
    assert JobRow.unscoped.filter(document_id=a_document).count() == 1  # 그 문서에 걸린 일감은 A 의 것 하나
    assert JobRow.unscoped.count() == 2  # 분모: A 것 하나, B 것 하나

    assert [job.id for job in selectors.jobs_of(company_id=a, document_id=a_document)] == [a_job]
    assert [job.id for job in selectors.jobs_of(company_id=b, document_id=a_document)] == []
    assert [job.id for job in selectors.jobs_of(company_id=b, document_id=b_document)] == [b_job]
    assert [job.id for job in selectors.jobs_of(company_id=a, document_id=b_document)] == []
    seen = selectors.get_document(company_id=a, document_id=a_document)
    assert isinstance(seen, DocumentWithJobs) and [job.id for job in seen.jobs] == [a_job]
    # 문서는 문서 표의 조건으로 찾는다: B 의 일감이 걸려 있어도 A 의 문서가 B 에게 나가지 않는다.
    assert selectors.get_document(company_id=b, document_id=a_document) == DocumentNotFound()

    sent: list[dict[str, Any]] = []

    def spy(**note: Any) -> None:
        sent.append(note)

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        confirmed = services.confirm_upload(
            company_id=a, document_id=a_document, storage=FakeStorage(), now=NOW, enqueue=spy
        )
    assert isinstance(confirmed, services.UploadConfirmed) and [job.id for job in confirmed.jobs] == [a_job]
    assert len(callbacks) == 1
    assert sent == [{"company_id": a, "job_id": a_job, "kind": JOB_KINDS[0]}]


# ── 묶음 읽기(목록 줄 G1b-2b): 남의 회사 id 가 섞인 입력 → 남의 것은 빠지고 제 것은 나온다 ──
# (runs 의 step_rows_of·results_of 는 runs/tests/service/selectors/test_runs.py — core 는 runs 를 import 하지
# 않는다, .importlinter 계약 가)


def test_documents_of_leaves_out_another_tenants_documents(companies: tuple[int, int]) -> None:
    a, b = companies
    a_document, _ = seed(a)
    b_document, _ = seed(b)
    mixed = [a_document, b_document, a_document + b_document + 10]
    assert set(selectors.documents_of(company_id=a, document_ids=mixed)) == {a_document}  # 분모: 제 것은 나온다
    assert set(selectors.documents_of(company_id=b, document_ids=mixed)) == {b_document}
    assert selectors.documents_of(company_id=b, document_ids=[a_document]) == {}
