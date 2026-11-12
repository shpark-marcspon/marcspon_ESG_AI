"""문서 목록·판 사슬·고치기·원본 내려받기(X1b-2a)의 회사 경계를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ B 의 세션으로 A 의 문서를 고치기·판 사슬·원본 → 404, A 의 문서 id 를 B 의 PATCH 본문 previousDocumentId 에 → 404
     (B 의 행 그대로). 만들기의 previousDocumentId 는 내 것·없는 것·남의 것 어느 id 든 422 PREVIOUS_VIA_PATCH(읽기 0,
     행 0) — 분모: B 는 제 문서로 200·201.
  ⓑ 목록에 남의 회사 것 0 — uploadedBy 에 A 의 사용자 id 를 넣어도 B 의 목록은 빈 쪽. 분모: A 로 보면 하나.
  (나) 원본 내려받기의 응답 머리(테스트 감독 허락 조건 — sid:MARC-TICK-71 노트 tv6Fyt8PmdZnjHUHIeHuA):
     Content-Type application/pdf 고정·X-Content-Type-Options nosniff·Content-Disposition attachment. 미들웨어
     (SecurityMiddleware)는 nosniff 를 주지 않는다 — 경로가 단다(감독 처분).
앱 역할이 문서 표에서 지우지 못하는 것은 tests/security/test_documents.py 가 그대로 잰다
(이 밴드는 권한을 넓히지 않는다).

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(분모를 센다).
저장소는 가짜 어댑터를 끼운다.
"""

from typing import Any

import psycopg
import pytest
from django.test import Client

from esgapi.core.tests.resource_fakes import FakeStorage
from tests.security.conftest import count
from tests.security.test_documents import upload_as
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage())


def b_session() -> Client:
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    return other


def chain_rows(owner: Owner) -> list[tuple[Any, ...]]:
    """주인 역할이 본 문서 행 전부: (id, 회사 id, 상태, 보고 연도, 앞 판, 고친 때)."""
    return owner.execute(
        "SELECT id, company_id, status, report_year, previous_document_id, updated_at FROM core_documents ORDER BY id"
    ).fetchall()


def patch(client: Client, document_id: int, body: dict[str, Any]) -> int:
    return client.patch(f"/api/documents/{document_id}", data=body, content_type="application/json").status_code


def test_another_companys_document_cannot_be_patched_chained_or_downloaded(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """ⓐ 경로 id 셋과 PATCH 본문의 앞 판. 남의 것은 「없다」(404)이고 두 회사의 행이 그대로다."""
    a, b = companies
    login(client, tenant_id="tenant-a")
    a_document = upload_as(client, fake, owner)
    other = b_session()
    b_document = upload_as(other, fake, owner)
    before = chain_rows(owner)
    assert [(row[0], row[1]) for row in before] == [(a_document, a), (b_document, b)]  # 분모: 회사마다 하나
    gets = len(fake.get_calls)

    assert patch(other, a_document, {"reportYear": 2025}) == 404
    assert other.get(f"/api/documents/{a_document}/versions").status_code == 404
    assert other.get(f"/api/documents/{a_document}/file").status_code == 404
    assert patch(other, b_document, {"previousDocumentId": a_document}) == 404
    assert chain_rows(owner) == before  # 두 회사의 행 그대로
    assert len(fake.get_calls) == gets  # 저장소에서 남의 원본을 읽지도 않았다

    # 분모: 각자 제 문서에는 닿는다.
    assert patch(other, b_document, {"reportYear": 2025}) == 200
    assert client.get(f"/api/documents/{a_document}/file").status_code == 200
    assert [row[3] for row in chain_rows(owner)] == [None, 2025]


@pytest.mark.parametrize("which", ["theirs", "mine", "unknown"])
def test_a_create_never_reads_the_previous_id(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, which: str
) -> None:
    """ⓐ 만들기의 previousDocumentId: 남의 id·내 id·없는 id 가 같은 422(읽기 0) — 남의 문서가 있는지 새지 않는다."""
    login(client, tenant_id="tenant-a")
    a_document = upload_as(client, fake, owner)
    other = b_session()
    b_document = upload_as(other, fake, owner)
    target = {"theirs": a_document, "mine": b_document, "unknown": max(a_document, b_document) + 10}[which]
    before = (count(owner, "core_documents"), len(fake.presigned))
    response = other.post(
        "/api/documents",
        data={"fileName": "b.pdf", "sizeBytes": 100, "previousDocumentId": target},
        content_type="application/json",
    )
    assert (response.status_code, response.json()["error"]["code"]) == (422, "PREVIOUS_VIA_PATCH")
    assert (count(owner, "core_documents"), len(fake.presigned)) == before == (2, 2)
    created = other.post(
        "/api/documents", data={"fileName": "b.pdf", "sizeBytes": 100}, content_type="application/json"
    )
    assert created.status_code == 201  # 분모: 앞 판 없이는 만든다


def test_the_list_never_shows_another_companys_documents(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """ⓑ 목록은 세션의 회사 것만. A 의 사용자 id 로 uploadedBy 를 걸어도 B 에는 빈 쪽."""
    a, b = companies
    me = login(client, tenant_id="tenant-a")
    a_document = upload_as(client, fake, owner)
    other = b_session()
    b_document = upload_as(other, fake, owner)
    assert owner.execute("SELECT company_id FROM core_documents ORDER BY id").fetchall() == [(a,), (b,)]  # 분모

    def ids(c: Client, query: str = "") -> list[int]:
        response = c.get(f"/api/documents{query}")
        assert response.status_code == 200
        return [item["id"] for item in response.json()["results"]]

    assert ids(client) == [a_document]  # 분모: A 로 보면 하나
    assert ids(other) == [b_document]
    a_user = me["user"]["id"]
    assert ids(client, f"?uploadedBy={a_user}") == [a_document]  # 분모: 그 칸은 실제로 거른다
    assert ids(other, f"?uploadedBy={a_user}") == []
    assert ids(other, "?latestOnly=true") == [b_document]


def test_the_original_is_served_as_a_pdf_attachment_that_is_not_sniffed(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """(나) 응답 머리 원문 — 저장소의 꼴이 무엇이든 Content-Type 은 application/pdf 고정이고 브라우저가 꼴을 짐작하지
    않으며(nosniff) 화면에 열지 않고 내려받는다(attachment). 감사 줄은 A 의 회사에 하나."""
    a, _ = companies
    login(client, tenant_id="tenant-a")
    document_id = upload_as(client, fake, owner)
    response = client.get(f"/api/documents/{document_id}/file")
    assert response.status_code == 200
    headers = {name: response[name] for name in ("Content-Type", "X-Content-Type-Options", "Content-Disposition")}
    print(f"원본 머리 {headers}")
    assert headers == {
        "Content-Type": "application/pdf",
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'attachment; filename="a.pdf"',
    }
    lines = owner.execute(
        "SELECT company_id, target_id FROM core_audit_events WHERE action = 'download' ORDER BY id"
    ).fetchall()
    assert lines == [(a, document_id)]
