"""raw_documents(실행 묶음이 싣는 문서 행 그대로 — RX1a)를 진짜 DB 로 잰다: 그 회사의 그 문서만, 칸 전부, id 오름,
빈 입력은 쿼리 0. ★ 문서는 전부 지어낸 것이다(synthetic).
"""

import uuid

import pytest
from pytest_django import DjangoAssertNumQueries

from esgapi.core.models import DocumentRow
from esgapi.core.service.selectors.documents import raw_documents

pytestmark = pytest.mark.django_db


def a_document(company_id: int, name: str) -> int:
    return (
        DocumentRow.for_company(company_id)
        .create(
            company_id=company_id,
            uploaded_by="1",
            file_name=name,
            storage_key=f"companies/{company_id}/documents/{uuid.uuid4()}/original",
            size_bytes=3,
            status="uploaded",
            sha256=None,
        )
        .pk
    )


def test_rows_as_they_are_of_that_company(companies: tuple[int, int]) -> None:
    a, b = companies
    first, second = a_document(a, "가상 보고서 1.pdf"), a_document(a, "가상 보고서 2.pdf")
    other = a_document(b, "가상 남의 보고서.pdf")
    rows = raw_documents(company_id=a, document_ids={second, first, other})
    assert [row["id"] for row in rows] == [first, second]
    assert set(rows[0]) == {field.attname for field in DocumentRow._meta.concrete_fields}  # 분모: 칸 전부
    assert rows[0]["sha256"] is None and rows[0]["company_id"] == a


def test_no_ids_no_query(companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries) -> None:
    with django_assert_num_queries(0):
        assert raw_documents(company_id=companies[0], document_ids=()) == []
