"""문서의 서비스 둘을 HTTP 없이 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다(주인 역할).

경로를 거치지 않고 함수를 직접 부른다: 바깥(저장소·시계·큐 넣기)을 인자로 넘길 수 있다는 것과, 그 차례를 본다.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from esgapi.core.calc.documents import BadTenantId
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.core.resources import queue as hooks
from esgapi.core.resources.ports.storage import PresignedUpload, StorageDenied
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.selectors.documents import DocumentNotFound
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import JobRow
from tests.support.patches import record_enqueued

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def make(storage: FakeStorage, company_id: int, **overrides: Any) -> services.DocumentCreated:
    options: dict[str, Any] = {
        "company_id": company_id,
        "uploaded_by": "user-1",
        "file_name": "a.pdf",
        "size_bytes": 5,
        "max_upload_bytes": 1000,
        "storage": storage,
        **overrides,
    }
    result = services.create_document(**options)
    assert isinstance(result, services.DocumentCreated)
    return result


def test_create_returns_the_document_and_the_signed_upload(companies: tuple[int, int]) -> None:
    a, _ = companies
    storage = FakeStorage(upload_ttl_s=77)
    created = make(storage, a)
    document = created.document
    assert (document.company_id, document.uploaded_by, document.file_name) == (a, "user-1", "a.pdf")
    assert (document.status, document.size_bytes, document.etag, document.uploaded_at) == (
        "awaiting_upload",
        5,
        None,
        None,
    )
    key_id = document.storage_key.removeprefix(f"companies/{a}/documents/").removesuffix("/original")
    assert document.storage_key == f"companies/{a}/documents/{key_id}/original" and str(uuid.UUID(key_id)) == key_id
    assert key_id != str(document.id)  # 키의 UUID 는 따로 지은 것이다(문서 id 가 아니다)
    assert created.upload == PresignedUpload(
        url=f"https://fake-storage.invalid/{document.storage_key}?size=5", expires_in_s=77
    )
    assert storage.presigned == [(document.storage_key, 5)]


def test_create_over_the_limit_or_with_an_unstorable_tenant_makes_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    storage = FakeStorage()
    over = services.create_document(
        company_id=a,
        uploaded_by="u",
        file_name="a.pdf",
        size_bytes=1001,
        max_upload_bytes=1000,
        storage=storage,
    )
    assert over == services.UploadTooLarge(max_bytes=1000)
    odd = services.create_document(
        company_id=0, uploaded_by="u", file_name="a.pdf", size_bytes=5, max_upload_bytes=1000, storage=storage
    )
    assert odd == BadTenantId()
    assert (DocumentRow.unscoped.count(), storage.presigned) == (0, [])


def test_a_failed_signing_leaves_no_row(companies: tuple[int, int]) -> None:
    """서명이 실패하면 예외다. 행과 서명이 한 블록이라 그 블록이 행을 되돌린다(감싸지 않고 부른다 — 고아 행이 없다)."""
    a, _ = companies

    class Broken(FakeStorage):
        def presign_upload(self, key: str, *, content_length: int) -> PresignedUpload:
            raise RuntimeError("가짜: 서명 실패")

    with pytest.raises(RuntimeError):
        make(Broken(), a)
    assert DocumentRow.unscoped.count() == 0


def test_a_confirm_that_fails_midway_leaves_nothing(
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
    companies: tuple[int, int],
) -> None:
    """④⑤ 는 한 블록이다: 갱신·일감을 만든 뒤 블록 안에서 던지면 그 블록이 되돌린다(감싸지 않고 부른다).
    문서는 `awaiting_upload`, 일감 0, 건 갈고리 0.
    """
    a, _ = companies
    storage = FakeStorage()
    document = make(storage, a).document
    storage.put(document.storage_key, b"12345")
    assert DocumentRow.unscoped.filter(pk=document.id, status="awaiting_upload").count() == 1  # 분모: 갱신 전

    def broken(**kwargs: Any) -> Any:
        raise RuntimeError("가짜: jobs_of 실패")

    monkeypatch.setattr(selectors, "jobs_of", broken)
    sent: list[dict[str, Any]] = []

    def enqueue(**kwargs: Any) -> None:
        sent.append(kwargs)

    with django_capture_on_commit_callbacks(execute=True) as callbacks, pytest.raises(RuntimeError):
        services.confirm_upload(company_id=a, document_id=document.id, storage=storage, now=NOW, enqueue=enqueue)
    assert DocumentRow.unscoped.get(pk=document.id).status == "awaiting_upload"
    assert JobRow.unscoped.count() == 0
    assert (len(callbacks), sent) == (0, [])


def test_the_db_refuses_a_size_below_one_and_an_unknown_status(companies: tuple[int, int]) -> None:
    a, _ = companies
    with pytest.raises(IntegrityError, match="core_documents_size_bytes_check"), transaction.atomic():
        make(FakeStorage(), a, size_bytes=0)
    document = make(FakeStorage(), a).document
    with pytest.raises(IntegrityError, match="core_documents_status_check"), transaction.atomic():
        DocumentRow.unscoped.filter(pk=document.id).update(status="queued")  # 일감의 상태는 문서의 상태가 아니다
    with pytest.raises(IntegrityError, match="run_jobs_status_check"), transaction.atomic():
        JobRow.unscoped.create(company_id=a, document_id=document.id, kind="parse", status="uploaded")
    with pytest.raises(IntegrityError, match="run_jobs_attempts_check"), transaction.atomic():
        JobRow.unscoped.create(company_id=a, document_id=document.id, kind="parse", status="queued", attempts=-1)
    # kind 에는 CHECK 가 없다(뒤 밴드가 종류를 더할 수 있다).
    JobRow.unscoped.create(company_id=a, document_id=document.id, kind="some-later-kind", status="queued")


def test_confirm_writes_the_given_clock_and_takes_the_enqueue_function_as_an_argument(
    django_capture_on_commit_callbacks: Any,
    companies: tuple[int, int],
) -> None:
    a, _ = companies
    storage = FakeStorage()
    document = make(storage, a).document
    etag = storage.put(document.storage_key, b"12345")
    sent: list[dict[str, Any]] = []

    def enqueue(**kwargs: Any) -> None:
        sent.append(kwargs)

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        result = services.confirm_upload(
            company_id=a, document_id=document.id, storage=storage, now=NOW, enqueue=enqueue
        )
    assert isinstance(result, services.UploadConfirmed)
    assert (result.document.status, result.document.etag, result.document.uploaded_at) == ("uploaded", etag, NOW)
    assert [(job.kind, job.status, job.attempts, job.company_id) for job in result.jobs] == [("parse", "queued", 0, a)]
    assert len(callbacks) == 1
    assert sent == [{"company_id": a, "job_id": result.jobs[0].id, "kind": "parse"}]
    row = DocumentRow.unscoped.get(pk=document.id)
    assert (row.uploaded_at, row.updated_at) == (NOW, NOW)


def test_each_unfinished_job_is_sent_with_its_own_id(
    django_capture_on_commit_callbacks: Any, companies: tuple[int, int]
) -> None:
    """일감이 둘이면 커밋 뒤의 부름도 둘이고, 저마다 제 일감의 id·종류로 불린다(마지막 일감으로 몰리지 않는다)."""
    a, _ = companies
    storage = FakeStorage()
    document = make(storage, a).document
    storage.put(document.storage_key, b"12345")
    sent: list[dict[str, Any]] = []

    def enqueue(**kwargs: Any) -> None:
        sent.append(kwargs)

    # 첫 확인이 일감 하나를 만든다(이 부름의 콜백은 잡지 않아 돌지 않는다).
    services.confirm_upload(company_id=a, document_id=document.id, storage=storage, now=NOW, enqueue=enqueue)
    assert sent == []
    # 둘째 일감을 손으로 심는다(지금의 서비스는 문서마다 하나만 만든다. kind 에는 CHECK 가 없다).
    JobRow.unscoped.create(company_id=a, document_id=document.id, kind="some-later-kind", status="queued")
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        result = services.confirm_upload(
            company_id=a, document_id=document.id, storage=storage, now=NOW, enqueue=enqueue
        )
    assert isinstance(result, services.UploadConfirmed)
    assert len({job.id for job in result.jobs}) == 2
    assert len(callbacks) == 2
    assert all(hasattr(callback, "__qualname__") for callback in callbacks)  # Django 5.2 의 robust 기록이 읽는다
    assert sent == [{"company_id": a, "job_id": job.id, "kind": job.kind} for job in result.jobs]
    assert sorted(call["kind"] for call in sent) == ["parse", "some-later-kind"]


def test_the_default_enqueue_is_read_from_the_hooks_module_at_call_time(
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Any,
    companies: tuple[int, int],
) -> None:
    """`enqueue` 를 안 주면 부를 때 hooks.enqueue_job 을 읽는다(함수 정의 때 묶이지 않았다)."""
    a, _ = companies
    storage = FakeStorage()
    document = make(storage, a).document
    storage.put(document.storage_key, b"12345")
    sent = record_enqueued(monkeypatch)
    with django_capture_on_commit_callbacks(execute=True):
        services.confirm_upload(company_id=a, document_id=document.id, storage=storage, now=NOW)
    assert [call["kind"] for call in sent] == ["parse"]
    assert services.confirm_upload.__kwdefaults__ == {"enqueue": None, "actor_user_id": None, "actor_kind": None}


def test_the_real_hook_without_a_broker_sends_nothing_and_takes_keywords_only(companies: tuple[int, int]) -> None:
    a, _ = companies
    hooks.enqueue_job(company_id=a, job_id=1, kind="parse")
    with pytest.raises(TypeError):
        hooks.enqueue_job("tenant-a", "job", "parse")  # pyright: ignore[reportCallIssue]


def test_a_foreign_tenant_gets_not_found_and_the_job_carries_the_document_rows_tenant(
    companies: tuple[int, int],
) -> None:
    """다른 테넌트의 이름으로 부르면 「없다」다(일감이 생기지 않는다). 생긴 일감의 company_id 는 문서 행의 것과 같다.

    ★ 이 테스트가 재는 것은 그 둘뿐이다. 「인자와 문서 행의 테넌트가 갈릴 때 일감이 문서 행의 것을 따른다」는 여기서
      잴 수 없다: selectors 의 tenant 조건이 먼저 「없다」로 돌려보낸다(인자 = 문서 행의 테넌트일 때만 일감이 생긴다).
    무효 조건: 여기서 「없다」를 만든 것은 selectors 의 tenant 조건이다(DB 에 RLS 는 없다).
    """
    a, b = companies
    storage = FakeStorage()
    document = make(storage, a).document
    storage.put(document.storage_key, b"12345")
    result = services.confirm_upload(company_id=b, document_id=document.id, storage=storage, now=NOW)
    assert result == DocumentNotFound()
    assert (storage.head_calls, JobRow.unscoped.count()) == ([], 0)
    assert selectors.get_document(company_id=b, document_id=document.id) == DocumentNotFound()

    done = services.confirm_upload(company_id=a, document_id=document.id, storage=storage, now=NOW)
    assert isinstance(done, services.UploadConfirmed)
    job_tenants = list(JobRow.unscoped.values_list("company_id", flat=True))
    assert job_tenants == [DocumentRow.unscoped.values_list("company_id", flat=True).get(pk=document.id)] == [a]
    assert [job.company_id for job in done.jobs] == [done.document.company_id]


def test_storage_branches_pass_through_unchanged(companies: tuple[int, int]) -> None:
    a, _ = companies
    storage = FakeStorage()
    document = make(storage, a).document
    assert (
        services.confirm_upload(company_id=a, document_id=document.id, storage=storage, now=NOW)
        == services.NotUploaded()
    )
    storage.put(document.storage_key, b"123456")
    assert services.confirm_upload(
        company_id=a, document_id=document.id, storage=storage, now=NOW
    ) == services.UploadSizeMismatch(expected=5, actual=6)
    storage.fail_with = StorageDenied("가짜 403")
    assert services.confirm_upload(company_id=a, document_id=document.id, storage=storage, now=NOW) == StorageDenied(
        "가짜 403"
    )
    assert (DocumentRow.unscoped.get().status, JobRow.unscoped.count()) == ("awaiting_upload", 0)


def test_selectors_give_the_jobs_in_creation_order(companies: tuple[int, int]) -> None:
    a, _ = companies
    storage = FakeStorage()
    document = make(storage, a).document
    for kind in ("parse", "later-1", "later-2"):
        JobRow.unscoped.create(company_id=a, document_id=document.id, kind=kind, status="queued")
    found = selectors.get_document(company_id=a, document_id=document.id)
    assert isinstance(found, selectors.DocumentWithJobs)
    assert [job.kind for job in found.jobs] == ["parse", "later-1", "later-2"]
    assert found.document == document


def test_a_job_cannot_outlive_its_document(companies: tuple[int, int]) -> None:
    """PROTECT: 일감이 걸린 문서는 ORM 으로 지워지지 않는다(앱 역할에는 DELETE 권한도 없다. 그것은 보안 층)."""
    a, _ = companies
    from django.db.models import ProtectedError

    document = make(FakeStorage(), a).document
    JobRow.unscoped.create(company_id=a, document_id=document.id, kind="parse", status="queued")
    with pytest.raises(ProtectedError):
        DocumentRow.unscoped.filter(pk=document.id).delete()


# ── AU1a: 올림의 감사 줄(upload — 옮김을 했을 때만, 블록이 닫힌 뒤) ─────────────────


def upload_lines(company_id: int) -> list[tuple[object, ...]]:
    return [
        (r.action, r.event, r.result, r.actor_kind, r.actor_user_id, r.target_kind, r.target_id, r.target_label, r.at)
        for r in AuditEventRow.for_company(company_id).order_by("pk")
    ]


def test_the_move_writes_one_upload_line_and_a_second_confirm_writes_none(companies: tuple[int, int]) -> None:
    a, b = companies
    storage = FakeStorage()
    document = make(storage, a).document
    storage.put(document.storage_key, b"12345")
    for _ in range(2):  # 두 번째는 멱등(이미 uploaded) — 0줄
        result = services.confirm_upload(
            company_id=a, document_id=document.id, storage=storage, now=NOW, actor_user_id=7
        )
        assert isinstance(result, services.UploadConfirmed)
    assert upload_lines(a) == [
        ("upload", "document_uploaded", "success", "service", 7, "document", document.id, "a.pdf", NOW)
    ]
    assert upload_lines(b) == []


def test_a_confirm_without_a_person_is_a_command_line(companies: tuple[int, int]) -> None:
    a, _ = companies
    storage = FakeStorage()
    document = make(storage, a).document
    storage.put(document.storage_key, b"12345")
    assert isinstance(
        services.confirm_upload(company_id=a, document_id=document.id, storage=storage, now=NOW),
        services.UploadConfirmed,
    )
    assert [line[3:5] for line in upload_lines(a)] == [("command", None)]


def test_refusals_and_storage_errors_write_no_line(companies: tuple[int, int]) -> None:
    a, b = companies
    storage = FakeStorage()
    document = make(storage, a).document

    def confirm(company_id: int) -> object:
        return services.confirm_upload(
            company_id=company_id, document_id=document.id, storage=storage, now=NOW, actor_user_id=7
        )

    assert confirm(a) == services.NotUploaded()
    storage.put(document.storage_key, b"123456")
    assert confirm(a) == services.UploadSizeMismatch(expected=5, actual=6)
    storage.fail_with = StorageDenied("가짜 403")
    assert confirm(a) == StorageDenied("가짜 403")
    assert confirm(b) == DocumentNotFound()
    assert (upload_lines(a), upload_lines(b)) == ([], [])
