"""문서 올리기의 경로 셋을 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다.

★ 이 층의 연결은 주인 역할이다(DB 에 RLS 는 없다). 앱 역할 연결의 테넌트 경계·권한·「커밋된 뒤에 실제로 돈다」는
  보안 층(tests/security/test_documents.py·test_tenant_paths.py)이 잰다. 행 수는 <Row>.unscoped 로 센다(분모).
★ 저장소는 가짜 어댑터를 끼운다(`services.default_storage`). 떠 있는 저장소에서 도는지는 통합 층이 잰다.
★ 갈고리(`hooks.enqueue_job`)는 스스로 돌지 않는다: pytest-django 가 테스트를 트랜잭션으로 감싸 바깥 커밋이 오지
  않는다. `django_capture_on_commit_callbacks` 로 잡아 세고, 실행까지 볼 때는 execute=True 로 돌린다.

core 는 업무 모듈을 import 하지 않는다(계약 가). 로그인은 tests.support.http.login, 테넌트는 뿌리 conftest 의 tenants,
회사 id 는 같은 곳의 companies(박아 두지 않는다). 문서 id 는 숫자라 셀 수 있다
→ 남의 것·없는 것은 이웃 id(±1·±2)로도 잰다.
"""

import re
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.conf import app_config
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.core.permissions import CUSTOMER, OPERATION_POLICY, OPERATOR
from esgapi.core.resources import queue as hooks
from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import JobRow
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

Capture = Callable[..., AbstractContextManager[list[Callable[[], Any]]]]
PDF = b"%PDF-1.7 synthetic " + b"x" * 81  # 100바이트. 지어낸 바이트다(PDF 가 아니다)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """이음매(`services.default_storage`)에 가짜 저장소를 꽂는다."""
    return plug_storage(monkeypatch, FakeStorage())


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """이음매(`hooks.enqueue_job`)에 꽂은 탐지기가 받은 인자들."""
    calls: list[dict[str, Any]] = []

    def spy(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(hooks, "enqueue_job", spy)
    return calls


def create(client: Client, body: dict[str, Any] | None = None, **more: Any) -> Any:
    payload = {"fileName": "보고서 2025.pdf", "sizeBytes": len(PDF), **more} if body is None else body
    return client.post("/api/documents", data=payload, content_type="application/json")


def confirm(client: Client, document_id: int | str) -> Any:
    return client.post(f"/api/documents/{document_id}/confirm")


def created_and_uploaded(client: Client, fake: FakeStorage, data: bytes = PDF) -> tuple[int, str]:
    """문서를 만들고 가짜 저장소에 그 바이트를 심는다(클라이언트가 올린 셈). (문서 id, ETag)를 돌려준다."""
    document_id: int = create(client).json()["document"]["id"]
    etag = fake.put(DocumentRow.unscoped.get(pk=document_id).storage_key, data)
    return document_id, etag


def state(document_id: int) -> tuple[str, str | None, int]:
    row = DocumentRow.unscoped.get(pk=document_id)
    return row.status, row.etag, JobRow.unscoped.filter(document_id=document_id).count()


def error_of(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def neighbours(*ids: int) -> list[int]:
    """숫자 id 와 그 이웃(±1·±2) 가운데 양수, 차례대로."""
    return sorted({n for i in ids for n in range(i - 2, i + 3) if n > 0})


# ── 만들기 ────────────────────────────────────────────────────────────


def test_create_makes_one_row_and_hands_out_an_upload_url(
    client: Client, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, _ = companies
    me = login(client)
    response = create(client)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"document", "upload"}
    document = body["document"]
    # 응답에 저장소의 자리·테넌트·올린 사람이 없다.
    assert set(document) == {
        "id",
        "fileName",
        "status",
        "sizeBytes",
        "etag",
        "createdAt",
        "uploadedAt",
        "reportYear",
        "previousDocumentId",
        "pageCount",
        "hasText",
    }
    assert (document["fileName"], document["status"], document["sizeBytes"]) == (
        "보고서 2025.pdf",
        "awaiting_upload",
        100,
    )
    assert (document["etag"], document["uploadedAt"]) == (None, None)

    rows = list(DocumentRow.unscoped.all())
    assert len(rows) == 1
    row = rows[0]
    assert row.id == document["id"] and type(document["id"]) is int  # 문서 id 는 숫자다(처분 1)
    assert (row.company_id, row.uploaded_by, row.status, row.size_bytes) == (
        a,
        me["user"]["id"],
        "awaiting_upload",
        100,
    )
    # 키는 세션의 회사 id 로 시작하고(서브도메인 글자가 아니다) 파일 이름의 글자가 없다. 키의 UUID 는 문서 id 가 아니다.
    key = re.fullmatch(rf"companies/{a}/documents/([0-9a-f-]{{36}})/original", row.storage_key)
    assert key is not None and str(uuid.UUID(key.group(1))) == key.group(1), row.storage_key
    assert "tenant-a" not in row.storage_key
    assert (row.etag, row.sha256, row.uploaded_at) == (None, None, None)
    assert JobRow.unscoped.count() == 0  # 일감은 올림 확인이 만든다

    # 가짜 어댑터가 받은 것: 그 키와, 말한 크기(서명 조건).
    assert fake.presigned == [(row.storage_key, 100)]
    upload = body["upload"]
    assert set(upload) == {"url", "method", "expiresInSeconds"}
    assert (upload["method"], upload["expiresInSeconds"]) == ("PUT", 300)
    assert upload["url"].startswith(f"https://fake-storage.invalid/companies/{a}/documents/")
    # 서명된 주소는 표에 남지 않는다.
    assert upload["url"] not in str(DocumentRow.unscoped.values().get())
    assert (fake.head_calls, fake.get_calls) == ([], [])


def test_a_customer_cannot_create_when_the_cell_is_operator_only(
    client: Client, tenants: None, fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """쿠키 세션은 역할과 무관하게 고객사 사용자다(가2 — viewer 도 만든다). 칸을 운영 관리자 몫으로 옮기면 403 이고
    행도 서명도 0 이다."""
    login(client, role="viewer")
    monkeypatch.setitem(OPERATION_POLICY, "core_documents_create", OPERATOR)
    assert error_of(create(client)) == (403, "FORBIDDEN")
    assert (DocumentRow.unscoped.count(), fake.presigned) == (0, [])
    monkeypatch.setitem(OPERATION_POLICY, "core_documents_create", CUSTOMER)
    assert create(client).status_code == 201  # 분모: 옮기기 전에는 만든다


def test_admin_can_create(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client, role="admin")
    assert create(client).status_code == 201


def test_without_a_session_every_document_path_is_401(client: Client, tenants: None, fake: FakeStorage) -> None:
    some = 1
    assert error_of(create(client)) == (401, "NO_SESSION")
    assert error_of(confirm(client, some)) == (401, "NO_SESSION")
    assert error_of(client.get(f"/api/documents/{some}")) == (401, "NO_SESSION")
    # 인증이 꼴 검사보다 먼저다: 쿠키 없이 틀린 id(숫자가 아닌 것, 옛 uuid 꼴)도 401 이다.
    assert error_of(client.get("/api/documents/not-a-uuid")) == (401, "NO_SESSION")
    assert error_of(client.get(f"/api/documents/{uuid.uuid4()}")) == (401, "NO_SESSION")
    assert (DocumentRow.unscoped.count(), fake.presigned) == (0, [])


@pytest.mark.parametrize(
    "body",
    [
        {"fileName": "", "sizeBytes": 100},
        {"fileName": "a" * 256, "sizeBytes": 100},
        {"fileName": "a\x00b.pdf", "sizeBytes": 100},
        {"fileName": "a\nb.pdf", "sizeBytes": 100},
        {"fileName": 7, "sizeBytes": 100},
        {"sizeBytes": 100},
        {"fileName": "a.pdf"},
        {"fileName": "a.pdf", "sizeBytes": 0},
        {"fileName": "a.pdf", "sizeBytes": -1},
        {"fileName": "a.pdf", "sizeBytes": True},
        {"fileName": "a.pdf", "sizeBytes": "100"},
        {"fileName": "a.pdf", "sizeBytes": 1.5},
        {"fileName": "a.pdf", "sizeBytes": None},
        {"fileName": "a.pdf", "sizeBytes": 100, "tenantId": "tenant-b"},
        {"fileName": "a.pdf", "sizeBytes": 100, "uploadedBy": "someone"},
        {"fileName": "a.pdf", "sizeBytes": 100, "storageKey": "tenants/tenant-b/documents/x/original"},
    ],
    ids=[
        "empty-name",
        "name-256",
        "name-nul",
        "name-newline",
        "name-not-text",
        "no-name",
        "no-size",
        "size-0",
        "size-negative",
        "size-true",
        "size-text",
        "size-float",
        "size-null",
        "tenant-in-body",
        "user-in-body",
        "key-in-body",
    ],
)
def test_a_malformed_body_is_422_and_makes_nothing(
    client: Client, tenants: None, fake: FakeStorage, body: dict[str, Any]
) -> None:
    login(client)
    response = create(client, body)
    assert error_of(response) == (422, "VALIDATION_ERROR")
    assert (DocumentRow.unscoped.count(), fake.presigned) == (0, [])
    # 받은 값을 되돌려 보내지 않는다.
    assert "tenant-b" not in response.content.decode()


def test_a_name_of_255_characters_is_accepted(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    assert create(client, {"fileName": "가" * 255, "sizeBytes": 1}).status_code == 201


def test_a_size_over_the_limit_is_413_and_makes_nothing(
    client: Client, tenants: None, fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    plug_storage(monkeypatch, fake, max_upload_bytes=1000)
    login(client)
    assert error_of(create(client, sizeBytes=1001)) == (413, "UPLOAD_TOO_LARGE")
    assert (DocumentRow.unscoped.count(), fake.presigned) == (0, [])  # 행 0, 서명 호출 0
    # 상한과 같은 값은 된다.
    assert create(client, sizeBytes=1000).status_code == 201
    assert [size for _key, size in fake.presigned] == [1000]


def test_the_default_limit_is_the_written_default_when_storage_is_not_configured() -> None:
    assert app_config().storage is None  # 테스트 설정에는 저장소 키가 없다
    assert services.max_upload_bytes() == 50 * 1024 * 1024
    assert services.default_storage() is None


def test_without_storage_settings_create_and_confirm_are_503(client: Client, tenants: None) -> None:
    """저장소를 끼우지 않았다: 진짜 `default_storage` 가 설정을 읽고 None 을 준다."""
    assert app_config().storage is None
    login(client)
    assert error_of(create(client)) == (503, "STORAGE_UNCONFIGURED")
    assert DocumentRow.unscoped.count() == 0
    assert error_of(confirm(client, 1)) == (503, "STORAGE_UNCONFIGURED")
    # 저장소 없음이 상한보다 먼저다.
    assert error_of(create(client, sizeBytes=10**12)) == (503, "STORAGE_UNCONFIGURED")


def test_a_tenant_id_that_cannot_be_a_key_is_409_and_makes_nothing(
    client: Client, tenants: None, fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """세션의 회사 id 가 키의 토막이 될 꼴(양의 정수)이 아니면 키를 짓지 않는다(갈래·code 는 옛 이름 그대로 — C1).

    주체의 company_id 는 교환·토큰이 양의 정수로만 싣는다 → HTTP 로는 닿지 않는다.
    그래서 경로가 부르는 `permitted` 를 바꿔 끼워 잰다.
    """
    from dataclasses import replace

    from esgapi.core.auth.principal import Principal
    from esgapi.core.service.apis import documents as core_api

    login(client)
    real = core_api.permitted

    def odd_tenant(request: Any, operation_id: str) -> Principal:
        return replace(real(request, operation_id), company_id=0)

    monkeypatch.setattr(core_api, "permitted", odd_tenant)
    assert error_of(create(client)) == (409, "TENANT_ID_NOT_STORABLE")
    assert (DocumentRow.unscoped.count(), fake.presigned) == (0, [])


# ── 올림 확인 ─────────────────────────────────────────────────────────


def test_confirm_before_the_upload_is_409_and_changes_nothing(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    document_id = create(client).json()["document"]["id"]
    assert error_of(confirm(client, document_id)) == (409, "NOT_UPLOADED")
    assert state(document_id) == ("awaiting_upload", None, 0)
    assert len(fake.head_calls) == 1


def test_confirm_after_the_upload_marks_it_and_queues_one_parse_job(
    client: Client, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, _ = companies
    login(client)
    document_id, etag = created_and_uploaded(client, fake)
    response = confirm(client, document_id)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"document", "jobs"}
    document = body["document"]
    assert (document["id"], document["status"], document["sizeBytes"]) == (document_id, "uploaded", 100)
    # ETag 는 저장소가 준 글자 그대로다(따옴표째).
    assert document["etag"] == etag
    assert etag.startswith('"') and etag.endswith('"') and len(etag) == 34
    assert document["uploadedAt"] is not None

    assert len(body["jobs"]) == 1
    job = body["jobs"][0]
    assert set(job) == {
        "id",
        "kind",
        "status",
        "attempts",
        "errorCode",
        "errorMessage",
        "summary",
        "createdAt",
        "finishedAt",
    }
    assert (job["kind"], job["status"], job["attempts"], job["summary"]) == ("parse", "queued", 0, {})
    assert (job["errorCode"], job["errorMessage"], job["finishedAt"]) == (None, None, None)

    row = DocumentRow.unscoped.get(pk=document_id)
    assert (row.status, row.etag, row.sha256) == ("uploaded", etag, None)  # sha256 칸은 쓰지 않는다
    assert row.uploaded_at is not None
    jobs = list(JobRow.unscoped.all())
    assert len(jobs) == 1
    assert (jobs[0].id, jobs[0].company_id, jobs[0].document_id) == (job["id"], a, document_id)
    assert type(job["id"]) is int  # 일감 id 도 숫자다(처분 1)
    assert (jobs[0].lease_expires_at, jobs[0].finished_at) == (None, None)


def test_confirming_twice_keeps_one_job_and_does_not_ask_the_storage_again(
    client: Client, tenants: None, fake: FakeStorage
) -> None:
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    first = confirm(client, document_id).json()
    assert len(fake.head_calls) == 1
    second = confirm(client, document_id)
    assert second.status_code == 200
    assert second.json() == first  # 같은 답
    assert len(fake.head_calls) == 1  # 둘째에는 head 를 다시 부르지 않았다
    assert JobRow.unscoped.count() == 1


def test_a_size_other_than_the_declared_one_is_409_and_changes_nothing(
    client: Client, tenants: None, fake: FakeStorage
) -> None:
    login(client)
    document_id, _etag = created_and_uploaded(client, fake, PDF + b"!")  # 말한 것보다 한 바이트 길다
    response = confirm(client, document_id)
    assert error_of(response) == (409, "UPLOAD_SIZE_MISMATCH")
    assert state(document_id) == ("awaiting_upload", None, 0)
    # 다시 올리면(말한 크기로) 된다: 문서는 그대로 남아 있었다.
    fake.put(DocumentRow.unscoped.get(pk=document_id).storage_key, PDF)
    assert confirm(client, document_id).status_code == 200


@pytest.mark.parametrize(
    ("failure", "code"),
    [(StorageDenied("가짜 403"), "STORAGE_DENIED"), (StorageUnavailable("가짜 닿지 못함"), "STORAGE_UNAVAILABLE")],
    ids=["denied", "unavailable"],
)
def test_a_storage_failure_is_503_and_is_not_read_as_not_uploaded(
    client: Client, tenants: None, fake: FakeStorage, failure: StorageDenied | StorageUnavailable, code: str
) -> None:
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    fake.fail_with = failure
    response = confirm(client, document_id)
    assert error_of(response) == (503, code)
    assert "가짜" not in response.content.decode()  # 속사정은 응답에 싣지 않는다
    assert state(document_id) == ("awaiting_upload", None, 0)


def test_confirm_of_an_unknown_id_is_404_and_a_non_uuid_is_422(
    client: Client, tenants: None, fake: FakeStorage
) -> None:
    login(client)
    mine = create(client).json()["document"]["id"]
    unknown = [n for n in neighbours(mine) if n != mine]
    assert unknown  # 분모
    assert [error_of(confirm(client, n)) for n in unknown] == [(404, "NOT_FOUND")] * len(unknown)
    assert error_of(confirm(client, "not-a-uuid")) == (422, "VALIDATION_ERROR")
    assert error_of(confirm(client, str(uuid.uuid4()))) == (422, "VALIDATION_ERROR")  # 옛 uuid 꼴은 이제 꼴 틀림
    assert fake.head_calls == []


def test_a_customer_cannot_confirm_when_the_cell_is_operator_only(
    client: Client, tenants: None, fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """칸을 운영 관리자 몫으로 옮기면 고객사 사용자(쿠키 세션)의 확인이 403 이고 상태·일감·저장소 확인이 0 이다."""
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    viewer = Client()
    login(viewer, sub="edk-user-2", role="viewer")
    monkeypatch.setitem(OPERATION_POLICY, "core_documents_confirm", OPERATOR)
    assert error_of(confirm(viewer, document_id)) == (403, "FORBIDDEN")
    assert state(document_id) == ("awaiting_upload", None, 0)
    assert fake.head_calls == []
    monkeypatch.setitem(OPERATION_POLICY, "core_documents_confirm", CUSTOMER)
    # 분모: 옮기기 전에는 viewer 세션도 확인한다(성공 코드를 박는다 — K2a 검증 권고 4)
    assert confirm(viewer, document_id).status_code == 200


def test_another_tenants_document_is_404_even_without_rls(client: Client, tenants: None, fake: FakeStorage) -> None:
    """DB 에 RLS 는 없다. 남의 문서는 「없다」다: selectors 가 세션의 회사로 조회를 연다(for_company).
    숫자 id 는 셀 수 있다: A 의 문서와 B 의 문서의 이웃(±1·±2)을 B 의 눈으로 넣어도 B 의 것만 보인다.

    무효 조건: 주인 역할 연결에서 잰 것이다. 앱 역할 연결의 경계는 보안 층(test_tenant_paths.py)이 잰다.
    """
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    assert error_of(other.get(f"/api/documents/{document_id}")) == (404, "NOT_FOUND")
    assert error_of(confirm(other, document_id)) == (404, "NOT_FOUND")
    assert state(document_id) == ("awaiting_upload", None, 0)
    assert fake.head_calls == []
    theirs = create(other).json()["document"]["id"]
    candidates = neighbours(document_id, theirs)
    assert DocumentRow.unscoped.count() == 2 and {document_id, theirs} <= set(candidates)  # 분모
    assert [n for n in candidates if other.get(f"/api/documents/{n}").status_code == 200] == [theirs]
    assert [n for n in candidates if client.get(f"/api/documents/{n}").status_code == 200] == [document_id]


# ── 갈고리 ────────────────────────────────────────────────────────────


def test_a_confirmed_upload_registers_one_callback_that_enqueues_the_job(
    client: Client,
    companies: tuple[int, int],
    fake: FakeStorage,
    enqueued: list[dict[str, Any]],
    django_capture_on_commit_callbacks: Capture,
) -> None:
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    with django_capture_on_commit_callbacks() as callbacks:
        assert confirm(client, document_id).status_code == 200
    assert len(callbacks) == 1
    assert enqueued == []  # 아직 불리지 않았다: 커밋 뒤에만 불린다(이 층에서는 바깥 커밋이 오지 않는다)
    callbacks[0]()
    job = JobRow.unscoped.get()
    assert enqueued == [{"company_id": companies[0], "job_id": job.id, "kind": "parse"}]


def test_confirming_again_enqueues_again_once_per_unfinished_job(
    client: Client,
    companies: tuple[int, int],
    fake: FakeStorage,
    enqueued: list[dict[str, Any]],
    django_capture_on_commit_callbacks: Capture,
) -> None:
    a, _ = companies
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    assert confirm(client, document_id).status_code == 200
    first = JobRow.unscoped.get()

    # 이미 uploaded 인 문서에 다시: 끝나지 않은 일감(1)만큼 다시 넣는다(쪽지를 잃었을 때의 길).
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        assert confirm(client, document_id).status_code == 200
    assert len(callbacks) == 1
    assert enqueued == [{"company_id": a, "job_id": first.id, "kind": "parse"}]

    # 끝나지 않은 일감이 둘이면 둘.
    second = JobRow.unscoped.create(company_id=a, document_id=document_id, kind="parse", status="processing")
    enqueued.clear()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        assert confirm(client, document_id).status_code == 200
    assert len(callbacks) == 2
    assert sorted(call["job_id"] for call in enqueued) == sorted([first.id, second.id])

    # 끝난 일감은 다시 넣지 않는다.
    JobRow.unscoped.filter(pk=first.id).update(status="done")
    JobRow.unscoped.filter(pk=second.id).update(status="failed")
    enqueued.clear()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        assert confirm(client, document_id).status_code == 200
    assert (len(callbacks), enqueued) == (0, [])
    assert JobRow.unscoped.count() == 2  # 새 일감을 만들지도 않았다


def test_a_refused_confirm_registers_nothing(
    client: Client,
    tenants: None,
    fake: FakeStorage,
    enqueued: list[dict[str, Any]],
    django_capture_on_commit_callbacks: Capture,
) -> None:
    login(client)
    not_yet = create(client).json()["document"]["id"]
    mismatched, _etag = created_and_uploaded(client, fake, PDF + b"!")
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        assert error_of(confirm(client, not_yet)) == (409, "NOT_UPLOADED")
        assert error_of(confirm(client, mismatched)) == (409, "UPLOAD_SIZE_MISMATCH")
        assert error_of(confirm(client, max(not_yet, mismatched) + 1)) == (404, "NOT_FOUND")  # 없는 숫자 id
        fake.fail_with = StorageUnavailable("가짜")
        assert error_of(confirm(client, not_yet)) == (503, "STORAGE_UNAVAILABLE")
        fake.fail_with = StorageDenied("가짜")
        assert error_of(confirm(client, not_yet)) == (503, "STORAGE_DENIED")
    assert (len(callbacks), enqueued) == (0, [])


def test_a_hook_that_raises_does_not_fail_the_request(
    client: Client,
    tenants: None,
    fake: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Capture,
) -> None:
    """갈고리가 던져도 응답은 200 이고 행은 queued 다(robust=True). 실행까지 해야 뜻이 있다(execute=True)."""
    called: list[dict[str, Any]] = []

    def broken(**kwargs: Any) -> None:
        called.append(kwargs)
        raise RuntimeError("가짜 브로커가 죽었다")

    monkeypatch.setattr(hooks, "enqueue_job", broken)
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = confirm(client, document_id)
    assert response.status_code == 200
    assert (len(callbacks), len(called)) == (1, 1)  # 정말 불렸고, 던졌다
    assert state(document_id)[0] == "uploaded"
    assert list(JobRow.unscoped.values_list("status", flat=True)) == ["queued"]


# ── 잠금 ──────────────────────────────────────────────────────────────


def test_confirm_reads_the_document_for_update(client: Client, tenants: None, fake: FakeStorage) -> None:
    """올림 확인이 낸 SQL 가운데 core_documents 를 FOR UPDATE 로 읽는 문이 있다.

    무효 조건: 글자를 본 것이다. 두 연결의 경합을 돌린 것이 아니다.
    """
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    with CaptureQueriesContext(connection) as queries:
        assert confirm(client, document_id).status_code == 200
    statements = [q["sql"] for q in queries.captured_queries]
    locking = [s for s in statements if "FOR UPDATE" in s]
    assert len(locking) == 1, statements
    assert 'FROM "core_documents"' in locking[0]
    # 잠근 뒤에 적는다: FOR UPDATE 가 UPDATE·INSERT 보다 앞이다.
    order = [i for i, s in enumerate(statements) if "FOR UPDATE" in s or s.startswith(("UPDATE", "INSERT"))]
    assert statements[order[0]] == locking[0]
    # 업무 표(core_documents·run_jobs)의 문만 거른 순서는 그대로다. 감사 줄(AU1a — 처분 ⑰)은 그 둘 **뒤**에 정확히 하나
    # (업무 블록이 닫힌 뒤 따로 쓴다 — 처분 ⑨ (가)).
    business = [i for i in order[1:] if '"core_documents"' in statements[i] or '"run_jobs"' in statements[i]]
    assert [statements[i].split()[0] for i in business] == ["UPDATE", "INSERT"]
    audit = [i for i in order[1:] if statements[i].startswith('INSERT INTO "core_audit_events"')]
    assert len(audit) == 1, statements
    assert audit[0] > business[-1]
    assert sorted(business + audit) == order[1:]  # 그 밖의 쓰기 0


def test_the_confirm_route_names_the_person_on_the_upload_line(
    client: Client, tenants: None, fake: FakeStorage
) -> None:
    """AU1a: 경로가 주체의 사람 id 를 넘긴다 — 감사 줄의 행위자는 그 고객사 사용자(service)다."""
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    assert confirm(client, document_id).status_code == 200
    row = DocumentRow.unscoped.get(pk=document_id)
    lines = AuditEventRow.for_company(row.company_id).filter(action="upload")
    assert [(r.actor_kind, r.actor_user_id, r.target_id) for r in lines] == [
        ("service", int(row.uploaded_by), document_id)
    ]


# ── 상태 보기 ─────────────────────────────────────────────────────────


def test_get_shows_the_document_and_its_jobs_to_every_role(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    document_id, _etag = created_and_uploaded(client, fake)
    before = client.get(f"/api/documents/{document_id}")
    assert before.status_code == 200
    assert (before.json()["document"]["status"], before.json()["jobs"]) == ("awaiting_upload", [])

    confirmed = confirm(client, document_id).json()
    assert client.get(f"/api/documents/{document_id}").json() == confirmed

    viewer = Client()
    login(viewer, sub="edk-user-2", role="viewer")
    seen = viewer.get(f"/api/documents/{document_id}")
    assert (seen.status_code, seen.json()) == (200, confirmed)
    # 상태 보기는 저장소에 묻지 않는다.
    assert len(fake.head_calls) == 1


def test_get_of_an_unknown_id_is_404_and_a_non_uuid_is_422(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    mine = create(client).json()["document"]["id"]
    unknown = [n for n in neighbours(mine) if n != mine]
    assert unknown  # 분모
    assert [error_of(client.get(f"/api/documents/{n}")) for n in unknown] == [(404, "NOT_FOUND")] * len(unknown)
    assert error_of(client.get("/api/documents/not-a-uuid")) == (422, "VALIDATION_ERROR")
    assert error_of(client.get(f"/api/documents/{uuid.uuid4()}")) == (
        422,
        "VALIDATION_ERROR",
    )  # 옛 uuid 꼴은 이제 꼴 틀림


def test_get_works_without_storage_settings(client: Client, companies: tuple[int, int]) -> None:
    """상태 보기는 저장소가 없어도 답한다(표만 읽는다)."""
    a, _ = companies
    login(client)
    row = DocumentRow.unscoped.create(
        company_id=a,
        uploaded_by="someone",
        file_name="a.pdf",
        storage_key=f"companies/{a}/documents/x/original",
        size_bytes=1,
        status="awaiting_upload",
    )
    assert client.get(f"/api/documents/{row.id}").status_code == 200


# ── 계약 먼저(밴드 XC): 보고 연도·앞 판·쪽 수 ─────────────────────────
# (X1b-2a: 두 칸의 501 시험은 몸 시험으로 갈음 — core/tests/service/apis/test_documents.py 의
#  test_a_create_with_report_year_is_201_and_stores_it·test_a_create_with_previous_is_422_and_writes_nothing)


def test_a_create_with_nulls_is_the_same_201(client: Client, tenants: None, fake: FakeStorage) -> None:
    login(client)
    response = create(client, reportYear=None, previousDocumentId=None)
    assert response.status_code == 201
    assert (DocumentRow.unscoped.count(), len(fake.presigned)) == (1, 1)


def test_the_new_document_fields_are_null(client: Client, tenants: None, fake: FakeStorage) -> None:
    """만들기·확인·조회 셋 모두에서 새 칸 셋은 null 이다(서버가 아직 채우지 않는다)."""
    login(client)
    created = create(client).json()["document"]
    document_id, _ = created["id"], fake.put(DocumentRow.unscoped.get(pk=created["id"]).storage_key, PDF)
    confirmed = confirm(client, document_id).json()["document"]
    got = client.get(f"/api/documents/{document_id}").json()["document"]
    for document in (created, confirmed, got):
        assert (document["reportYear"], document["previousDocumentId"], document["pageCount"]) == (None, None, None)
    assert DocumentRow.unscoped.count() == 1  # 분모
