"""문서 selector 의 X1b-2a 몫(목록·판 사슬)을 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다(주인 역할).

행은 바로 심는다(올리기·저장소를 거치지 않음). 남의 회사 행은 늘 같이 심어 분모를 둔다.
"""

import uuid

import pytest

from esgapi.core.calc.versions import ChainTooLong
from esgapi.core.models import DocumentRow
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.selectors.documents import DocumentNotFound

pytestmark = pytest.mark.django_db


def stored(
    company_id: int,
    name: str = "a.pdf",
    *,
    status: str = "uploaded",
    by: str = "7",
    year: int | None = None,
    previous: int | None = None,
) -> int:
    return (
        DocumentRow.for_company(company_id)
        .create(
            company_id=company_id,
            uploaded_by=by,
            file_name=name,
            storage_key=f"companies/{company_id}/documents/{uuid.uuid4()}/original",
            size_bytes=5,
            status=status,
            report_year=year,
            previous_document_id=previous,
        )
        .id
    )


def listed(
    company_id: int,
    *,
    report_year: int | None = None,
    q: str | None = None,
    uploaded_by: int | None = None,
    latest_only: bool = False,
) -> list[int]:
    """조건에 맞는 문서 id 전부(한 쪽 100 — 시험의 행은 그보다 적다)."""
    page = selectors.list_documents(
        company_id=company_id,
        report_year=report_year,
        q=q,
        uploaded_by=uploaded_by,
        latest_only=latest_only,
        limit=100,
        offset=0,
    )
    assert page.count == len(page.documents)
    return [document.id for document in page.documents]


def test_the_list_shows_only_this_companys_uploaded_documents_newest_first(companies: tuple[int, int]) -> None:
    a, b = companies
    first, second = stored(a), stored(a)
    stored(a, status="awaiting_upload")  # 올림이 끝나지 않은 행은 싣지 않는다
    theirs = stored(b)
    assert listed(a) == [second, first]
    assert listed(b) == [theirs]  # 분모: B 로 1


def test_the_list_filters_by_year_name_uploader_and_pages(companies: tuple[int, int]) -> None:
    a, b = companies
    report = stored(a, "Report 2025.pdf", year=2025, by="7")
    memo = stored(a, "memo.pdf", year=2024, by="8")
    stored(b, "report-b.pdf", year=2025, by="7")
    assert listed(a, report_year=2025) == [report]
    assert listed(a, q="REPORT") == [report]  # 대소문자 무시 부분 일치
    assert listed(a, uploaded_by=8) == [memo]
    assert listed(a, uploaded_by=7) == [report]  # B 의 사용자 7 이 올린 것은 회사 조건에 걸려 0
    assert listed(a, uploaded_by=999) == []
    page = selectors.list_documents(
        company_id=a, report_year=None, q=None, uploaded_by=None, latest_only=False, limit=1, offset=1
    )
    assert (page.count, [d.id for d in page.documents]) == (2, [report])


def test_latest_only_keeps_the_last_uploaded_version_of_each_chain(companies: tuple[int, int]) -> None:
    a, _ = companies
    one = stored(a)
    two = stored(a, previous=one)
    three = stored(a, previous=two)
    lone = stored(a)
    assert listed(a, latest_only=True) == [lone, three]
    assert listed(a) == [lone, three, two, one]  # 분모: 거르지 않으면 넷


def test_the_neighbour_lookups_stay_inside_the_company(companies: tuple[int, int]) -> None:
    a, b = companies
    one = stored(a)
    two = stored(a, previous=one)
    assert selectors.previous_id_of(company_id=a, document_id=two) == one
    assert selectors.next_id_of(company_id=a, document_id=one) == two
    assert selectors.previous_id_of(company_id=b, document_id=two) is None
    assert selectors.next_id_of(company_id=b, document_id=one) is None


def test_the_version_chain_is_the_whole_chain_newest_first(companies: tuple[int, int]) -> None:
    a, b = companies
    one = stored(a)
    two = stored(a, previous=one)
    three = stored(a, previous=two)
    for member in (one, two, three):
        found = selectors.version_chain(company_id=a, document_id=member)
        assert not isinstance(found, DocumentNotFound | ChainTooLong)
        assert [d.id for d in found] == [three, two, one]
    assert selectors.version_chain(company_id=b, document_id=two) == DocumentNotFound()  # 남의 것 = 없음
    lone = selectors.version_chain(company_id=a, document_id=stored(a))
    assert not isinstance(lone, DocumentNotFound | ChainTooLong) and len(lone) == 1


def test_the_version_chain_refuses_a_chain_over_the_limit(companies: tuple[int, int]) -> None:
    a, _ = companies
    last: int | None = None
    for _ in range(101):
        last = stored(a, previous=last)
    assert last is not None
    assert selectors.version_chain(company_id=a, document_id=last) == ChainTooLong(100)
