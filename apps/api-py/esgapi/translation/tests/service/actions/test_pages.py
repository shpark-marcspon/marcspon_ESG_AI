# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""문서 쪽 수(GET /translation/documents/{document_id}/pages — 밴드 TRP6 §3-2, 결정 MARC-ENT-452). 업무 층, 저장소는
가짜(FakeStorage).

갈래(service/actions/pages.py 머리): 없는·남의 문서 404 · 올림 전 null(저장소 부름 0) · 저장소 넷·etag 다름·못 셈 null
(로그 까닭만 — 문서 글·키 0) · 그 밖 값. 쓰기·감사 0. ★ 바이트·이름은 지어낸 것이다.
"""

import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.test import Client, override_settings

from esgapi.core.models import DocumentRow
from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.translation.tests.docx_support import p, tbl, tc, tr, with_body
from esgapi.translation.tests.service import seed
from esgapi.user.service.services.user import create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

LIMIT = 1_000_000
TXT = "[PAGE 1]\n가상 본문\n[PAGE 2]\n나\n[PAGE 6]\n다\n".encode()
DOCX = with_body(p("[PAGE 1]") + p("가") + p("[PAGE 4]") + p("나"))
PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=LIMIT)


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


def uploaded(
    company_id: int,
    storage: FakeStorage,
    data: bytes,
    *,
    status: str = "uploaded",
    etag: str | None = "e-1",
    page_count: int | None = None,
) -> int:
    """그 회사 문서 행 하나와 저장소의 원본(같은 etag)."""
    key = f"companies/{company_id}/documents/trp6-{uuid.uuid4().hex}/original"
    row = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name="지은 추출본.txt",
        storage_key=key,
        size_bytes=len(data),
        etag=etag,
        status=status,
        uploaded_at=seed.START if status == "uploaded" else None,
        page_count=page_count,
    )
    storage.put(key, data, etag=etag or "e-1")
    return row.pk


def url(document_id: int) -> str:
    return f"/api/translation/documents/{document_id}/pages"


def pages(client: Client, document_id: int, **headers: Any) -> tuple[int, Any]:
    got = client.get(url(document_id), **headers)
    return got.status_code, got.json()


def counts() -> dict[str, int]:
    with connection.cursor() as cursor:
        found: dict[str, int] = {}
        for table in ("core_documents", "run_runs", "run_jobs", "core_audit_events"):
            cursor.execute(f"SELECT count(*) FROM {table}")
            row = cursor.fetchone()
            assert row is not None
            found[table] = row[0]
        return found


# ── 5 값 ──


def test_docx_and_txt_answer_the_largest_page_tag(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    docx, txt = uploaded(a, storage, DOCX), uploaded(a, storage, TXT)
    assert pages(client, docx) == (200, {"documentId": docx, "pageCount": 4})
    assert pages(client, txt) == (200, {"documentId": txt, "pageCount": 6})


def test_a_pdf_and_a_text_without_tags_are_null(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    """PDF 는 core 의 page_count(9)를 내지 않는다 — 영문번역은 PDF 를 받지 않는다(엔진도 거절)."""
    a, _ = companies
    login(client, tenant_id="tenant-a")
    pdf = uploaded(a, storage, b"%PDF-1.7\n[PAGE 3]\n", page_count=9)
    plain = uploaded(a, storage, "가상 본문\n태그 없음\n".encode())
    assert pages(client, pdf) == (200, {"documentId": pdf, "pageCount": None})
    assert pages(client, plain) == (200, {"documentId": plain, "pageCount": None})


# ── 6·7 못 읽음 → 200 null ──


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("missing", "object_missing"),
        ("too_large", "object_too_large"),
        ("denied", "storage_denied"),
        ("unavailable", "storage_unavailable"),
    ],
)
def test_a_storage_failure_is_null_with_the_reason_logged(
    client: Client,
    companies: tuple[int, int],
    storage: FakeStorage,
    caplog: pytest.LogCaptureFixture,
    failure: str,
    reason: str,
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = uploaded(a, storage, TXT)
    key = DocumentRow.for_company(a).get(pk=doc).storage_key
    match failure:
        case "missing":
            del storage.objects[key]
        case "too_large":
            storage.objects[key] = (TXT + b"x", "e-1")  # 행의 size_bytes 를 넘는 객체
        case "denied":
            storage.fail_with = StorageDenied("403")
        case _:
            storage.fail_with = StorageUnavailable("timeout")
    with caplog.at_level(logging.INFO, logger="esgapi.translation.service.actions.pages"):
        assert pages(client, doc) == (200, {"documentId": doc, "pageCount": None})
    leveled = [r for r in caplog.records if r.name == "esgapi.translation.service.actions.pages"]
    assert [r.levelno for r in leveled] == [logging.WARNING]  # 저장소 탓은 경고(TRS2)
    logged = [r.getMessage() for r in leveled]
    assert logged == [f"translation_pages_unreadable reason={reason}"]
    assert all(key not in line and "PAGE" not in line and "가상" not in line for line in logged)


def test_a_count_over_the_grid_limit_is_null_with_the_reason_logged(
    client: Client, companies: tuple[int, int], storage: FakeStorage, caplog: pytest.LogCaptureFixture
) -> None:
    """[PAGE n] 최댓값이 page_tags.MAX_PAGES(10,000)를 넘으면 null — 까닭 이름은 page_tags 의 것 그대로(가지 리뷰 ③)."""
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = uploaded(a, storage, "[PAGE 1]\n가\n[PAGE 10001]\n".encode())
    with caplog.at_level(logging.INFO, logger="esgapi.translation.service.actions.pages"):
        assert pages(client, doc) == (200, {"documentId": doc, "pageCount": None})
    logged = [
        (r.levelno, r.getMessage()) for r in caplog.records if r.name == "esgapi.translation.service.actions.pages"
    ]
    assert logged == [(logging.INFO, "translation_pages_unreadable reason=too_many_pages")]  # 사용자 파일 탓(TRS2)


def test_without_a_configured_storage_the_count_is_null(
    client: Client,
    companies: tuple[int, int],
    storage: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """저장소 설정이 없으면(S3_BUCKET 없음 — default_storage() 가 None) 500 이 아니라 200 null(갈래 3)."""
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = uploaded(a, storage, TXT)
    plug_storage(monkeypatch, None)
    with caplog.at_level(logging.WARNING, logger="esgapi.translation.service.actions.pages"):
        assert pages(client, doc) == (200, {"documentId": doc, "pageCount": None})
    logged = [r.getMessage() for r in caplog.records if r.name == "esgapi.translation.service.actions.pages"]
    assert logged == ["translation_pages_unreadable reason=storage_unconfigured"]


def test_a_changed_object_and_an_unfinished_upload_are_null(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    changed = uploaded(a, storage, TXT)
    key = DocumentRow.for_company(a).get(pk=changed).storage_key
    storage.objects[key] = (TXT, "e-other")
    assert pages(client, changed) == (200, {"documentId": changed, "pageCount": None})
    waiting = uploaded(a, storage, TXT, status="awaiting_upload")
    storage.get_calls.clear()
    assert pages(client, waiting) == (200, {"documentId": waiting, "pageCount": None})
    assert storage.get_calls == []  # 올림 전에는 저장소를 읽지 않는다


# ── 8 회사 범위 ──


def operator_headers(client: Client) -> dict[str, Any]:
    created = create_operator(username="ops", name="가상 운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": CHANGED},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    return bearer(str(changed.json()["access"]))


def test_another_companys_document_is_the_same_404_as_a_missing_one(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, b = companies
    theirs = uploaded(b, storage, TXT)
    mine = uploaded(a, storage, DOCX)
    login(client, tenant_id="tenant-a")
    other_status, other_body = pages(client, theirs)
    missing_status, missing_body = pages(client, max(theirs, mine) + 1_000)
    assert (other_status, missing_status) == (404, 404)
    assert other_body == missing_body and other_body["error"]["code"] == "NOT_FOUND"
    assert pages(client, mine) == (200, {"documentId": mine, "pageCount": 4})  # 분모


def test_the_operator_reads_the_single_work_companys_document_like_its_customer(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, b = companies
    doc = uploaded(b, storage, TXT)
    headers = operator_headers(client)
    assert client.get(url(doc), **headers).status_code == 400  # 분모: 회사 둘이면 고르지 못함
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM company WHERE id = %s", [a])  # 남는 회사 = tenant-b 하나
    as_operator = pages(client, doc, **headers)
    login(customer := Client(), tenant_id="tenant-b")
    assert as_operator == pages(customer, doc) == (200, {"documentId": doc, "pageCount": 6})


# ── 9 공격 docx ──


def test_a_vertical_merge_attack_answers_within_two_seconds(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    """python-docx 가 n² 로 13초 넘게 걸리는 세로 병합 docx(critic 탐침 700×2) — 경로는 read_document 를 부르지
    않는다."""
    a, _ = companies
    login(client, tenant_id="tenant-a")
    first = tr(*(tc("가", '<w:vMerge w:val="restart"/>') for _ in range(2)))
    rest = tr(*(tc("", "<w:vMerge/>") for _ in range(2)))
    attack = uploaded(a, storage, with_body(tbl(first + rest * 699) + p("[PAGE 3]")))
    normal = uploaded(a, storage, DOCX)
    start = time.perf_counter()
    answered = pages(client, attack)
    took = time.perf_counter() - start
    assert answered == (200, {"documentId": attack, "pageCount": 3})
    assert took < 2.0, f"{took:.2f}s"
    assert pages(client, normal) == (200, {"documentId": normal, "pageCount": 4})  # 분모


# ── 10 쓰기 0 ──


def test_reading_pages_writes_nothing(client: Client, companies: tuple[int, int], storage: FakeStorage) -> None:
    a, _ = companies
    login(client, tenant_id="tenant-a")
    doc = uploaded(a, storage, TXT)
    before = counts()
    assert pages(client, doc)[0] == 200
    assert pages(client, doc + 1_000)[0] == 404
    assert counts() == before
    assert DocumentRow.for_company(a).get(pk=doc).page_count is None  # 쪽 수를 행에 적지 않는다
