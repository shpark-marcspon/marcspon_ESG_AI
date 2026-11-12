"""읽기. 문서와 그 일감들, 문서 목록과 판 사슬(X1b-2a). 표의 행을 바깥에 내줄 꼴(Document·Job)로 바꾼다. 쓰지 않는다.

★ 조회마다 회사 조건을 적는다. 이 파일에서 표를 읽는 문은 `_documents`·`_jobs` 둘이고 나머지는 그 뒤에 조건을
  잇는다. 남의 행은 SQL 에서 0행이다 → 「없다」. 회사는 인자로 받는다(세션도 DB 설정도 읽지 않는다).
  두 표의 기본 매니저는 회사를 정하지 않은 조회를 거절한다(DocumentRow.for_company 로만 열린다 — core/isolation).
  DB 의 RLS 는 없다. 이 조건은 업무 층 core/tests/test_selectors_tenant.py 가, 앱 역할 연결에서의 경계는 보안 층
  tests/security 가 잰다.
  무효 조건: 조건의 입력은 세션·쪽지의 회사 id 다. 그 값이 틀리면 그 틀린 회사로 가른다.
★ 잠그지 않는 읽기는 Document·Job 을, 잠그는 읽기(lock_document)는 ORM 행을 돌려준다(Service 가 이어서 쓰는 재료다).
★ 판 사슬 걷기(core/calc/versions.py)는 이 파일의 previous_id_of·next_id_of 를 받아 걷는다 — 걷는 한 걸음도
  회사 조건 안이다(남의 회사 문서는 사슬에 보이지 않는다. DB 의 같은 회사 외래 키가 사슬이 회사를 넘지 못하게도 막는다).
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db.models import Exists, OuterRef, QuerySet

from esgapi.core.calc.documents import DocumentStatus, JobStatus
from esgapi.core.calc.versions import ChainTooLong, chain_of
from esgapi.core.models import DocumentRow
from esgapi.runs.models import JobRow


@dataclass(frozen=True, slots=True)
class Document:
    id: int
    company_id: int
    uploaded_by: str
    file_name: str
    storage_key: str
    size_bytes: int
    etag: str | None
    status: DocumentStatus
    created_at: datetime
    uploaded_at: datetime | None
    report_year: int | None
    previous_document_id: int | None
    page_count: int | None  # NULL = 모른다(올림 확인이 못 쟀다)
    has_text: bool | None  # 앞 TEXT_PROBE_PAGES 쪽의 글자 층. NULL = 모른다


@dataclass(frozen=True, slots=True)
class Job:
    id: int
    company_id: int
    document_id: int
    kind: str
    status: JobStatus
    attempts: int
    error_code: str | None
    error_message: str | None
    summary: dict[str, Any]
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class DocumentNotFound:
    """그런 문서가 없다. 다른 회사의 문서도 이 갈래다(둘을 구별하지 않는다)."""


@dataclass(frozen=True, slots=True)
class DocumentWithJobs:
    document: Document
    jobs: tuple[Job, ...]


def _document_status(value: str) -> DocumentStatus:
    if value == "awaiting_upload" or value == "uploaded":
        return value
    raise ValueError(f"core_documents.status 에 모르는 값이 있다: {value}")  # CHECK 제약이 막으므로 오지 않는다


def _job_status(value: str) -> JobStatus:
    if value == "queued" or value == "processing" or value == "done" or value == "failed":
        return value
    raise ValueError(f"run_jobs.status 에 모르는 값이 있다: {value}")  # CHECK 제약이 막으므로 오지 않는다


def document_of(row: DocumentRow) -> Document:
    return Document(
        id=row.id,
        company_id=row.company_id,
        uploaded_by=row.uploaded_by,
        file_name=row.file_name,
        storage_key=row.storage_key,
        size_bytes=row.size_bytes,
        etag=row.etag,
        status=_document_status(row.status),
        created_at=row.created_at,
        uploaded_at=row.uploaded_at,
        report_year=row.report_year,
        previous_document_id=row.previous_document_id,
        page_count=row.page_count,
        has_text=row.has_text,
    )


def job_of(row: JobRow) -> Job:
    return Job(
        id=row.id,
        company_id=row.company_id,
        document_id=row.document_id,
        kind=row.kind,
        status=_job_status(row.status),
        attempts=row.attempts,
        error_code=row.error_code,
        error_message=row.error_message,
        summary=dict(row.summary),
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


def _documents(company_id: int) -> "QuerySet[DocumentRow]":
    """그 회사의 문서 행. 이 파일에서 core_documents 를 읽는 문은 여기 하나다."""
    return DocumentRow.for_company(company_id)


def _jobs(company_id: int) -> "QuerySet[JobRow]":
    """그 회사의 일감 행. 이 파일에서 run_jobs 를 읽는 문은 여기 하나다."""
    return JobRow.for_company(company_id)


def find_document(*, company_id: int, document_id: int) -> Document | None:
    """그 회사의 그 문서. 없으면(남의 것이어도) None. 잠그지 않는다."""
    row = _documents(company_id).filter(pk=document_id).first()
    return None if row is None else document_of(row)


def documents_of(*, company_id: int, document_ids: Collection[int]) -> dict[int, Document]:
    """그 회사의 문서들(문서 id → Document). find_document 의 묶음 꼴 — 쿼리 하나(document_ids 가 비면 0). 없는 것·남의
    것은 열쇠가 없다. 잠그지 않는다. 입력 길이의 상한은 부르는 쪽이 지킨다(목록 줄 G1b-2b)."""
    return {row.id: document_of(row) for row in _documents(company_id).filter(pk__in=document_ids)}


def lock_document(*, company_id: int, document_id: int) -> DocumentRow | None:
    """그 회사의 그 문서 행을 FOR UPDATE 로 읽는다. 변경 트랜잭션 안에서만 부른다(밖이면 Django 가 던진다)."""
    return _documents(company_id).select_for_update().filter(pk=document_id).first()


def jobs_of(*, company_id: int, document_id: int) -> tuple[Job, ...]:
    """그 문서의 일감 가운데 그 회사의 것 전부, 만든 차례로."""
    rows = _jobs(company_id).filter(document_id=document_id).order_by("created_at", "id")
    return tuple(job_of(row) for row in rows)


def get_document(*, company_id: int, document_id: int) -> DocumentWithJobs | DocumentNotFound:
    """문서 하나와 그 일감들. 권한 가름은 경로 쪽에 있다(여기는 회사 조건만)."""
    document = find_document(company_id=company_id, document_id=document_id)
    if document is None:
        return DocumentNotFound()
    return DocumentWithJobs(document, jobs_of(company_id=company_id, document_id=document_id))


# ── 목록과 판 사슬(X1b-2a) ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DocumentPage:
    count: int  # 조건에 맞는 전부의 수
    documents: tuple[Document, ...]


def list_documents(
    *,
    company_id: int,
    report_year: int | None,
    q: str | None,
    uploaded_by: int | None,
    latest_only: bool,
    limit: int,
    offset: int,
) -> DocumentPage:
    """그 회사의 `uploaded` 문서 한 쪽. 새 것 먼저(created_at 내림, 같으면 id 내림).

    report_year 「같다」, q 파일 이름의 부분 일치(대소문자 무시), uploaded_by 올린 사용자 id 「같다」
    (남의 회사 사용자 id 면 회사 조건에 걸려 빈 쪽), latest_only 면 「`uploaded` 인 뒤 판이 없는 것」
    (판 사슬의 마지막)만. None·False 는 거르지 않음.
    `awaiting_upload` 는 올림이 끝나지 않은 행이라 싣지 않는다.
    """
    rows = _documents(company_id).filter(status="uploaded")
    if report_year is not None:
        rows = rows.filter(report_year=report_year)
    if q is not None:
        rows = rows.filter(file_name__icontains=q)
    if uploaded_by is not None:
        rows = rows.filter(uploaded_by=str(uploaded_by))
    if latest_only:
        later = _documents(company_id).filter(previous_document_id=OuterRef("pk"), status="uploaded")
        rows = rows.filter(~Exists(later))
    rows = rows.order_by("-created_at", "-id")
    return DocumentPage(count=rows.count(), documents=tuple(document_of(row) for row in rows[offset : offset + limit]))


def previous_id_of(*, company_id: int, document_id: int) -> int | None:
    """그 회사의 그 문서가 가리키는 앞 판 id. 첫 판이거나 문서가 없으면(남의 것이어도) None."""
    return _documents(company_id).filter(pk=document_id).values_list("previous_document_id", flat=True).first()


def next_id_of(*, company_id: int, document_id: int) -> int | None:
    """그 회사에서 그 문서를 앞 판으로 가리키는 문서(뒤 판) id. 없으면 None(갈래 금지라 많아야 하나)."""
    return _documents(company_id).filter(previous_document_id=document_id).values_list("id", flat=True).first()


def version_chain(*, company_id: int, document_id: int) -> tuple[Document, ...] | DocumentNotFound | ChainTooLong:
    """그 문서가 든 판 사슬 전부, 새 판 먼저. 문서가 없으면(남의 것이어도) DocumentNotFound, 사슬이 상한을 넘으면
    ChainTooLong. 사슬의 문서는 상태를 가리지 않는다(앞 판을 가리키는 행은 PATCH 로만 서고 PATCH 는 `uploaded`
    끼리다)."""
    if find_document(company_id=company_id, document_id=document_id) is None:
        return DocumentNotFound()
    ids = chain_of(
        document_id,
        previous_of=lambda i: previous_id_of(company_id=company_id, document_id=i),
        next_of=lambda i: next_id_of(company_id=company_id, document_id=i),
    )
    if isinstance(ids, ChainTooLong):
        return ids
    rows = {row.id: row for row in _documents(company_id).filter(pk__in=ids)}
    return tuple(document_of(rows[i]) for i in ids if i in rows)


def raw_documents(*, company_id: int, document_ids: Collection[int]) -> list[dict[str, object]]:
    """그 회사의 문서 행 그대로(칸 이름(attname) → 값, id 오름) — 실행 묶음(RX1a)의 내보내기가 싣는 재료. 없는 것·남의
    것은 빠진다. 한 쿼리(document_ids 가 비면 0)."""
    if not document_ids:
        return []
    return [dict(row) for row in _documents(company_id).filter(pk__in=document_ids).order_by("id").values()]
