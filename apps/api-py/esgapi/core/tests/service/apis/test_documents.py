"""문서 경로의 X1b-2a 몫을 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다(주인 역할).

    POST  /documents                  만들기의 보고 연도(저장)·앞 판(422 PREVIOUS_VIA_PATCH, 읽기 0)
    GET   /documents                  목록(올라온 것만·새 것 먼저·거르기 넷·쪽)
    GET   /documents/{id}/versions    판 사슬(새 판 먼저)
    PATCH /documents/{id}             보고 연도·앞 판(갈래 전부)
    GET   /documents/{id}/file        원본 내려받기(바이트·머리·409 갈래·감사 줄)
    POST  /documents/{id}/confirm     응답의 pageCount·hasText(시험이 지은 PDF)

옛 평평한 파일 core/tests/test_documents_api.py 의 몫(만들기·올림 확인·상태 보기)은 거기 그대로다. 앱 역할 연결의 회사
경계는 보안 층 tests/security/test_documents_chain.py 가 잰다. 저장소는 가짜(`services.default_storage`)다.
"""

from functools import partial
from typing import Any

import pytest
from django.test import Client

from esgapi.core.calc.versions import chain_of, chain_problem
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage, build_pdf
from esgapi.runs.models import JobRow
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

PDF = build_pdf(5, text="Hello")


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """이음매(`services.default_storage`)에 가짜 저장소를 꽂는다."""
    return plug_storage(monkeypatch, FakeStorage())


def error_of(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def create(client: Client, **more: Any) -> Any:
    body = {"fileName": "보고서 2025.pdf", "sizeBytes": len(PDF), **more}
    return client.post("/api/documents", data=body, content_type="application/json")


def uploaded(client: Client, fake: FakeStorage, name: str = "보고서 2025.pdf", data: bytes = PDF) -> int:
    """만들고 가짜 저장소에 바이트를 심고 올림 확인까지. 문서 id."""
    body = {"fileName": name, "sizeBytes": len(data)}
    document_id: int = client.post("/api/documents", data=body, content_type="application/json").json()["document"][
        "id"
    ]
    fake.put(DocumentRow.unscoped.get(pk=document_id).storage_key, data)
    assert client.post(f"/api/documents/{document_id}/confirm").status_code == 200
    return document_id


def patch(client: Client, document_id: int, body: dict[str, Any]) -> Any:
    return client.patch(f"/api/documents/{document_id}", data=body, content_type="application/json")


def listed(client: Client, query: str = "") -> list[int]:
    response = client.get(f"/api/documents{query}")
    assert response.status_code == 200, response.content.decode()
    return [item["id"] for item in response.json()["results"]]


def chain_fields(document_id: int) -> tuple[int | None, int | None]:
    row = DocumentRow.unscoped.get(pk=document_id)
    return row.report_year, row.previous_document_id


def downloads(company_id: int) -> list[tuple[str, int | None, str | None]]:
    lines = AuditEventRow.for_company(company_id).filter(action="download")
    return [(r.event, r.target_id, r.target_label) for r in lines]


# ── 만들기의 두 칸 (BASE 의 501 시험 test_a_create_with_report_year_or_previous_is_501_and_writes_nothing 의 짝) ──


def test_a_create_with_report_year_is_201_and_stores_it(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    response = create(client, reportYear=2025)
    assert response.status_code == 201
    document = response.json()["document"]
    assert (document["reportYear"], document["previousDocumentId"]) == (2025, None)
    assert chain_fields(document["id"]) == (2025, None)
    assert (DocumentRow.unscoped.count(), len(fake.presigned)) == (1, 1)


@pytest.mark.parametrize("which", ["mine", "unknown", "theirs"])
def test_a_create_with_previous_is_422_and_writes_nothing(
    client: Client, tenants: None, fake: FakeStorage, which: str
) -> None:
    """앞 판은 만들 때 받지 않는다: 내 것·없는 것·남의 것 어느 id 든 같은 422(읽기 0), 행·서명 0."""
    login(client)
    mine = uploaded(client, fake)
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    theirs = uploaded(other, fake)
    target = {"mine": mine, "unknown": max(mine, theirs) + 10, "theirs": theirs}[which]
    rows, presigned = DocumentRow.unscoped.count(), len(fake.presigned)
    assert rows == 2  # 분모
    response = create(client, previousDocumentId=target)
    assert error_of(response) == (422, "PREVIOUS_VIA_PATCH")
    assert (DocumentRow.unscoped.count(), len(fake.presigned)) == (rows, presigned)
    assert create(client, previousDocumentId=None).status_code == 201  # 분모: null 이면 만든다


@pytest.mark.parametrize("year", [1899, 2101])
def test_a_report_year_out_of_range_is_422(client: Client, tenants: None, fake: FakeStorage, year: int) -> None:
    login(client)
    assert error_of(create(client, reportYear=year)) == (422, "VALIDATION_ERROR")
    assert DocumentRow.unscoped.count() == 0
    assert create(client, reportYear=2100).status_code == 201  # 분모: 끝값은 받는다


# ── 목록 ──────────────────────────────────────────────────────────────


def test_the_list_answers_after_auth_with_this_companys_uploaded_documents(
    client: Client, tenants: None, fake: FakeStorage
) -> None:
    """BASE 의 test_each_run_operation_is_501_after_auth[core_documents_list] 의 짝: 인증 뒤 몸이 답한다.
    올라온 것만, 새 것 먼저. 남의 회사 것·`awaiting_upload` 는 안 실린다."""
    login(client)
    first = uploaded(client, fake, name="a.pdf")
    second = uploaded(client, fake, name="b.pdf")
    create(client)  # awaiting_upload — 안 실림
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    theirs = uploaded(other, fake)
    response = client.get("/api/documents")
    assert response.status_code == 200
    body = response.json()
    assert (body["count"], body["isNext"], [d["id"] for d in body["results"]]) == (2, False, [second, first])
    item = body["results"][0]
    assert (item["status"], item["pageCount"], item["hasText"], type(item["uploadedBy"])) == ("uploaded", 5, True, int)
    assert listed(other) == [theirs]  # 분모: B 로 보면 B 의 것 하나
    assert DocumentRow.unscoped.count() == 4


def test_the_list_filters_and_pages(client: Client, tenants: None, fake: FakeStorage) -> None:
    me = login(client)
    old = uploaded(client, fake, name="old report.pdf")
    new = uploaded(client, fake, name="New Report.pdf")
    assert patch(client, old, {"reportYear": 2024}).status_code == 200
    assert patch(client, new, {"reportYear": 2025}).status_code == 200
    colleague = Client()
    login(colleague, sub="edk-user-3")
    theirs = uploaded(colleague, fake, name="memo.pdf")
    assert listed(client) == [theirs, new, old]  # 분모
    assert listed(client, "?reportYear=2025") == [new]
    assert listed(client, "?q=REPORT") == [new, old]  # 대소문자 무시
    assert listed(client, f"?uploadedBy={me['user']['id']}") == [new, old]
    assert listed(client, "?uploadedBy=999999999") == []
    page = client.get("/api/documents?limit=1&offset=1").json()
    assert (page["count"], page["isNext"], [d["id"] for d in page["results"]]) == (3, True, [new])


def test_latest_only_keeps_the_last_of_each_chain(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    first, second, third = (uploaded(client, fake, name=f"v{n}.pdf") for n in (1, 2, 3))
    alone = uploaded(client, fake, name="alone.pdf")
    assert patch(client, second, {"previousDocumentId": first}).status_code == 200
    assert patch(client, third, {"previousDocumentId": second}).status_code == 200
    assert listed(client) == [alone, third, second, first]  # 분모: 거르지 않으면 넷
    assert listed(client, "?latestOnly=true") == [alone, third]


def test_a_nul_in_q_is_refused_not_a_500(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    uploaded(client, fake)
    assert error_of(client.get("/api/documents?q=a%00b")) == (422, "VALIDATION_ERROR")
    assert len(listed(client, "?q=2025")) == 1  # 분모


# ── 판 사슬 ───────────────────────────────────────────────────────────


def test_versions_answer_after_auth_newest_first(client: Client, tenants: None, fake: FakeStorage) -> None:
    """BASE 의 test_each_run_operation_is_501_after_auth[core_documents_versions] 의 짝."""
    login(client)
    first, second, third = (uploaded(client, fake, name=f"v{n}.pdf") for n in (1, 2, 3))
    assert patch(client, second, {"previousDocumentId": first}).status_code == 200
    assert patch(client, third, {"previousDocumentId": second}).status_code == 200
    for member in (first, second, third):
        response = client.get(f"/api/documents/{member}/versions")
        assert response.status_code == 200
        assert [d["id"] for d in response.json()] == [third, second, first]
    lonely = uploaded(client, fake)
    assert [d["id"] for d in client.get(f"/api/documents/{lonely}/versions").json()] == [lonely]


def test_versions_of_an_unknown_or_another_companys_document_is_404(
    client: Client, tenants: None, fake: FakeStorage
) -> None:
    login(client)
    mine = uploaded(client, fake)
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    assert error_of(other.get(f"/api/documents/{mine}/versions")) == (404, "NOT_FOUND")
    assert error_of(client.get(f"/api/documents/{mine + 10}/versions")) == (404, "NOT_FOUND")
    assert client.get(f"/api/documents/{mine}/versions").status_code == 200  # 분모


# ── 고치기(PATCH) ─────────────────────────────────────────────────────


def test_patch_changes_only_the_fields_sent_and_null_clears(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    first = uploaded(client, fake)
    second = uploaded(client, fake)
    response = patch(client, second, {"reportYear": 2025, "previousDocumentId": first})
    assert response.status_code == 200
    assert (response.json()["reportYear"], response.json()["previousDocumentId"]) == (2025, first)
    assert patch(client, second, {"reportYear": 2026}).json()["previousDocumentId"] == first  # 안 보낸 칸은 그대로
    assert chain_fields(second) == (2026, first)
    assert patch(client, second, {"previousDocumentId": first}).status_code == 200  # 같은 앞 판을 다시 — 지난다
    cleared = patch(client, second, {"previousDocumentId": None}).json()
    assert (cleared["reportYear"], cleared["previousDocumentId"]) == (2026, None)
    assert chain_fields(second) == (2026, None)


@pytest.mark.parametrize(
    "body",
    [{}, {"reportYear": "2025"}, {"reportYear": True}, {"reportYear": 1899}, {"previousDocumentId": "1"}, {"x": 1}],
    ids=["empty", "year-text", "year-true", "year-low", "previous-text", "unknown-field"],
)
def test_a_malformed_patch_is_422_and_changes_nothing(
    client: Client, tenants: None, fake: FakeStorage, body: dict[str, Any]
) -> None:
    login(client)
    document_id = uploaded(client, fake)
    assert error_of(patch(client, document_id, body)) == (422, "VALIDATION_ERROR")
    assert chain_fields(document_id) == (None, None)


def test_patch_refusals_are_codes_and_change_nothing(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    first, second, third = (uploaded(client, fake, name=f"v{n}.pdf") for n in (1, 2, 3))
    waiting: int = create(client).json()["document"]["id"]
    assert patch(client, second, {"previousDocumentId": first}).status_code == 200
    before = {i: chain_fields(i) for i in (first, second, third, waiting)}

    assert error_of(patch(client, first + 100, {"reportYear": 2025})) == (404, "NOT_FOUND")
    missing = patch(client, third, {"previousDocumentId": first + 100})
    assert error_of(missing) == (404, "NOT_FOUND")
    assert missing.json()["error"]["message"] == "앞 판 문서가 없다"  # 경로 id 의 404 와 다른 글
    assert error_of(patch(client, waiting, {"reportYear": 2025})) == (409, "NOT_UPLOADED")
    assert error_of(patch(client, third, {"previousDocumentId": waiting})) == (409, "NOT_UPLOADED")
    assert error_of(patch(client, third, {"previousDocumentId": third})) == (422, "VERSION_CHAIN_SELF")
    assert error_of(patch(client, third, {"previousDocumentId": first})) == (409, "VERSION_CHAIN_FORK")
    assert error_of(patch(client, first, {"previousDocumentId": second})) == (409, "VERSION_CHAIN_CYCLE")
    assert {i: chain_fields(i) for i in before} == before
    assert patch(client, third, {"previousDocumentId": second}).status_code == 200  # 분모: 바른 것은 선다


def test_patch_of_another_companys_document_or_previous_is_404(
    client: Client, tenants: None, fake: FakeStorage
) -> None:
    login(client)
    mine = uploaded(client, fake)
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    theirs = uploaded(other, fake)
    assert error_of(
        other.patch(f"/api/documents/{mine}", data={"reportYear": 2025}, content_type="application/json")
    ) == (
        404,
        "NOT_FOUND",
    )
    assert error_of(patch(client, mine, {"previousDocumentId": theirs})) == (404, "NOT_FOUND")
    assert (chain_fields(mine), chain_fields(theirs)) == ((None, None), (None, None))
    assert patch(client, mine, {"reportYear": 2025}).status_code == 200  # 분모


def test_too_long_a_chain_is_409_on_patch_and_versions(
    client: Client, tenants: None, fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """상한(VERSION_CHAIN_MAX 100) 자체는 서비스 시험이 판 백 개로 잰다. 여기는 갈래 → 409 code 만(상한을 2 로)."""
    login(client)
    first, second, third = (uploaded(client, fake, name=f"v{n}.pdf") for n in (1, 2, 3))
    assert patch(client, second, {"previousDocumentId": first}).status_code == 200  # 분모: 둘은 선다
    monkeypatch.setattr(services, "chain_problem", partial(chain_problem, limit=2))
    assert error_of(patch(client, third, {"previousDocumentId": second})) == (409, "VERSION_CHAIN_TOO_LONG")
    assert chain_fields(third) == (None, None)
    monkeypatch.setattr(selectors, "chain_of", partial(chain_of, limit=1))
    assert error_of(client.get(f"/api/documents/{second}/versions")) == (409, "VERSION_CHAIN_TOO_LONG")


# ── 원본 내려받기 ─────────────────────────────────────────────────────


def test_the_original_comes_back_as_a_pdf_attachment_with_one_audit_line(
    client: Client, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, _ = companies
    me = login(client)
    name = '보고서 "초안"; 2025.pdf'
    document_id = uploaded(client, fake, name=name)
    assert downloads(a) == []  # 분모: 올림 확인은 download 줄을 남기지 않는다
    response = client.get(f"/api/documents/{document_id}/file")
    assert response.status_code == 200
    assert response.content == PDF
    assert response["Content-Type"] == "application/pdf"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Disposition"] == (
        "attachment; filename*=utf-8''%EB%B3%B4%EA%B3%A0%EC%84%9C%20%22%EC%B4%88%EC%95%88%22%3B%202025.pdf"
    )
    assert downloads(a) == [("document_downloaded", document_id, name)]
    line = AuditEventRow.for_company(a).get(action="download")
    assert (line.actor_kind, line.actor_user_id, line.target_kind, line.result) == (
        "service",
        int(me["user"]["id"]),
        "document",
        "success",
    )


def test_an_ascii_name_is_quoted_in_the_header(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    document_id = uploaded(client, fake, name='a "b"; c.pdf')
    assert client.get(f"/api/documents/{document_id}/file")["Content-Disposition"] == (
        'attachment; filename="a \\"b\\"; c.pdf"'
    )


def test_the_original_of_a_document_not_yet_uploaded_is_409(
    client: Client, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, _ = companies
    login(client)
    waiting: int = create(client).json()["document"]["id"]
    fake.put(DocumentRow.unscoped.get(pk=waiting).storage_key, PDF)  # 저장소에는 있어도 확인 전이다
    assert error_of(client.get(f"/api/documents/{waiting}/file")) == (409, "NOT_UPLOADED")
    assert (fake.get_calls, downloads(a)) == ([], [])


def test_the_original_changed_after_the_confirm_is_409(
    client: Client, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, _ = companies
    login(client)
    document_id = uploaded(client, fake)
    key = DocumentRow.unscoped.get(pk=document_id).storage_key
    assert client.get(f"/api/documents/{document_id}/file").status_code == 200  # 분모
    fake.put(key, PDF, etag='"another"')  # 같은 키에 다시 올림
    assert error_of(client.get(f"/api/documents/{document_id}/file")) == (409, "OBJECT_CHANGED")
    assert len(downloads(a)) == 1  # 거절은 줄 0


@pytest.mark.parametrize(
    ("break_it", "expected"),
    [
        ("missing", (409, "OBJECT_MISSING")),
        ("too_large", (409, "OBJECT_TOO_LARGE")),
        ("denied", (503, "STORAGE_DENIED")),
        ("unavailable", (503, "STORAGE_UNAVAILABLE")),
    ],
)
def test_storage_refusals_of_the_original(
    client: Client,
    companies: tuple[int, int],
    fake: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
    break_it: str,
    expected: tuple[int, str],
) -> None:
    a, _ = companies
    login(client)
    document_id = uploaded(client, fake)
    key = DocumentRow.unscoped.get(pk=document_id).storage_key
    if break_it == "missing":
        del fake.objects[key]
    elif break_it == "too_large":
        monkeypatch.setattr(services, "max_upload_bytes", lambda: len(PDF) - 1)
    else:
        fake.fail_with = StorageDenied("가짜 403") if break_it == "denied" else StorageUnavailable("가짜")
    assert error_of(client.get(f"/api/documents/{document_id}/file")) == expected
    assert downloads(a) == []


def test_the_original_of_another_companys_or_an_unknown_document_is_404(
    client: Client, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, b = companies
    login(client)
    mine = uploaded(client, fake)
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    assert error_of(other.get(f"/api/documents/{mine}/file")) == (404, "NOT_FOUND")
    assert error_of(client.get(f"/api/documents/{mine + 10}/file")) == (404, "NOT_FOUND")
    assert (fake.get_calls.count(DocumentRow.unscoped.get(pk=mine).storage_key), downloads(a), downloads(b)) == (
        1,  # 올림 확인의 읽기 하나뿐(내려받기 0)
        [],
        [],
    )
    assert client.get(f"/api/documents/{mine}/file").status_code == 200  # 분모


# ── 올림 확인 응답의 쪽 수·글자 층 ───────────────────────────────────


def test_the_confirm_answers_with_the_measured_page_count_and_text_layer(
    client: Client, tenants: None, fake: FakeStorage
) -> None:
    login(client)
    answers: list[tuple[Any, Any, Any]] = []
    for data in (build_pdf(5, text="Hello"), build_pdf(4), b"%PDF-1.7 synthetic " + b"x" * 81):
        created = client.post(
            "/api/documents", data={"fileName": "a.pdf", "sizeBytes": len(data)}, content_type="application/json"
        )
        document_id: int = created.json()["document"]["id"]
        assert created.json()["document"]["hasText"] is None  # 올리기 전에는 모른다
        fake.put(DocumentRow.unscoped.get(pk=document_id).storage_key, data)
        confirmed = client.post(f"/api/documents/{document_id}/confirm").json()["document"]
        again = client.get(f"/api/documents/{document_id}").json()["document"]
        assert (again["pageCount"], again["hasText"]) == (confirmed["pageCount"], confirmed["hasText"])
        answers.append((confirmed["status"], confirmed["pageCount"], confirmed["hasText"]))
    assert answers == [("uploaded", 5, True), ("uploaded", 4, False), ("uploaded", None, None)]
    assert JobRow.unscoped.count() == 3  # 일감은 전과 같이 문서마다 하나
