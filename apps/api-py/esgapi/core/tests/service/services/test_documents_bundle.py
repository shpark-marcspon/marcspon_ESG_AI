"""실행 묶음의 문서 넣기 셋(import_document·set_imported_etag·restore_document_times — RX1a)을 진짜 DB 로 잰다.

★a(발주서 §2-1): create() 는 auto_now_add·auto_now 를 넣은 때로 찍고(넘긴 값을 덮는다), QuerySet.update() 는 auto_now 를
  안 채운다 — 그래서 시각은 넣은 뒤 update 로 되돌리고, 그 뒤의 etag 적기가 되돌린 updated_at 을 흔들지 않는다.
★ 문서는 전부 지어낸 것이다(synthetic).
"""

import uuid
from datetime import UTC, datetime

import pytest
from django.db import IntegrityError, transaction

from esgapi.core.models import DocumentRow
from esgapi.core.service.services.documents import import_document, restore_document_times, set_imported_etag

pytestmark = pytest.mark.django_db
OLD = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
OLDER = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)


def imported(company_id: int, *, previous: int | None = None, etag: str | None = None) -> int:
    return import_document(
        company_id=company_id,
        uploaded_by="42",
        storage_key=f"companies/{company_id}/documents/{uuid.uuid4()}/original",
        file_name="가상 보고서.pdf",
        size_bytes=3,
        sha256=None,
        status="uploaded",
        uploaded_at=OLD,
        report_year=2025,
        previous_document_id=previous,
        page_count=1,
        has_text=True,
        etag=etag,
    )


def test_create_stamps_now_and_update_restores_old_times(companies: tuple[int, int]) -> None:
    b = companies[1]
    before = datetime.now(UTC)
    document_id = imported(b)
    row = DocumentRow.for_company(b).get(pk=document_id)
    assert row.created_at >= before and row.updated_at >= before and row.uploaded_at == OLD
    assert row.etag is None and row.uploaded_by == "42" and row.company_id == b
    restore_document_times(company_id=b, times={document_id: (OLDER, OLD)})
    set_imported_etag(company_id=b, document_id=document_id, etag='"e1"')
    row = DocumentRow.for_company(b).get(pk=document_id)
    assert (row.created_at, row.updated_at, row.etag) == (OLDER, OLD, '"e1"')  # ★a: update 는 auto_now 를 안 채운다


def test_the_etag_is_written_once(companies: tuple[int, int]) -> None:
    b = companies[1]
    document_id = imported(b, etag='"from-bundle"')
    with pytest.raises(RuntimeError), transaction.atomic():
        set_imported_etag(company_id=b, document_id=document_id, etag='"e1"')
    assert DocumentRow.for_company(b).get(pk=document_id).etag == '"from-bundle"'


def test_another_companys_rows_are_not_touched(companies: tuple[int, int]) -> None:
    a, b = companies
    document_id = imported(a)
    with pytest.raises(RuntimeError), transaction.atomic():
        set_imported_etag(company_id=b, document_id=document_id, etag='"e1"')
    with pytest.raises(RuntimeError), transaction.atomic():
        restore_document_times(company_id=b, times={document_id: (OLDER, OLD)})
    assert DocumentRow.for_company(a).get(pk=document_id).etag is None


def test_the_previous_version_must_be_of_the_same_company(companies: tuple[int, int]) -> None:
    a, b = companies
    first = imported(b)
    assert DocumentRow.for_company(b).get(pk=imported(b, previous=first)).previous_document_id == first
    with pytest.raises(IntegrityError), transaction.atomic():
        imported(a, previous=first)  # 같은 회사 외래 키
