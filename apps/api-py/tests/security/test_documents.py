"""문서의 표 둘(core_documents·run_jobs)과 경로 셋을 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  - 두 표가 테넌트의 표로 잡혀 test_owner.py 의 카탈로그 검사(정책 없음·GRANT)가 저절로 문다
  - 한 회사의 문서·일감은 다른 회사의 세션과 다른 회사의 인자로 부른 selector·service 에 안 보인다(① 조건)
  - 회사를 정하지 않은 조회는 거절되고, 다른 회사의 이름으로는 쓰지 못한다(② 기본 매니저)
  - 남의 회사 문서에 건 일감은 주인 역할로 넣어도 DB 가 거절한다(⑤ 같은 회사 외래 키)
  - 앱 역할은 두 표에서 지우지 못한다
  - 일감의 summary 는 작은 요약이다(DB 의 CHECK)
  - 큐에 넣는 갈고리는 그 블록이 **커밋된 뒤에** 불리고, 되돌려진 블록·거절된 요청에서는 불리지 않는다
  - 올림 확인의 저장소 head 는 트랜잭션 밖에서 돈다

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(분모를 센다).
저장소는 가짜 어댑터를 끼운다(이 층은 저장소를 재지 않는다).

무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다. ①② 는 역할과 무관하게
파이썬에서 걸리지만 unscoped·날 SQL 로 붙는 길은 막지 못한다(제품 코드의 그 길은 순수 층의 받침 ④ 가 막는다).
"""

import re
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import Client

from esgapi.core.isolation.managers import CrossCompanyWriteError, UnscopedQueryError
from esgapi.core.models import DocumentRow
from esgapi.core.resources import queue as hooks
from esgapi.core.resources.ports.storage import HeadResult
from esgapi.core.service.selectors import documents as selectors
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import JobRow
from tests.security.conftest import count, tenant_tables
from tests.security.seed import add_job
from tests.support.http import login
from tests.support.patches import plug_storage, record_enqueued

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
TABLES = ("core_documents", "run_jobs")
PRIVILEGES = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
PDF = b"%PDF-1.7 synthetic " + b"x" * 81  # 100바이트. 지어낸 바이트다
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage())


def upload_as(client: Client, fake: FakeStorage, owner: Owner) -> int:
    """client 의 세션으로 문서를 만들고, 가짜 저장소에 바이트를 심고, 올림을 확인한다. 문서 id 를 돌려준다."""
    created = client.post(
        "/api/documents", data={"fileName": "a.pdf", "sizeBytes": len(PDF)}, content_type="application/json"
    )
    assert created.status_code == 201, created.content.decode()
    document_id: int = created.json()["document"]["id"]
    row = owner.execute("SELECT storage_key FROM core_documents WHERE id = %s", [document_id]).fetchone()
    assert row is not None
    fake.put(row[0], PDF)
    confirmed = client.post(f"/api/documents/{document_id}/confirm")
    assert confirmed.status_code == 200, confirmed.content.decode()
    return document_id


def facts(owner: Owner) -> list[tuple[Any, ...]]:
    """주인 역할이 본 문서 행 전부(분모): (회사 id, 상태, 크기, ETag 가 있는가, 그 문서의 일감 수)."""
    return owner.execute(
        "SELECT d.company_id, d.status, d.size_bytes, d.etag IS NOT NULL, "
        "(SELECT count(*) FROM run_jobs j WHERE j.document_id = d.id) "
        "FROM core_documents d ORDER BY d.created_at"
    ).fetchall()


# ── 카탈로그와 권한 ──


def test_both_tables_are_tenant_tables_so_the_catalogue_checks_cover_them(owner: Owner) -> None:
    """test_owner.py 의 둘(정책·행 보안 없음 / SELECT 참·DELETE·TRUNCATE 거짓)은 tenant_tables 를 돈다."""
    assert set(tenant_tables(owner)) >= set(TABLES)


@pytest.mark.parametrize("table", TABLES)
def test_app_role_may_read_insert_and_update_only(owner: Owner, table: str) -> None:
    held = owner.execute(
        "SELECT p, has_table_privilege('esg_app', %s, p) FROM unnest(%s::text[]) AS p", [table, PRIVILEGES]
    ).fetchall()
    assert held == [
        ("SELECT", True),
        ("INSERT", True),
        ("UPDATE", True),
        ("DELETE", False),
        ("TRUNCATE", False),
        ("REFERENCES", False),
        ("TRIGGER", False),
    ]
    assert owner.execute(
        "SELECT rolsuper, rolbypassrls, (SELECT tableowner FROM pg_tables WHERE tablename = %s) = rolname "
        "FROM pg_roles WHERE rolname = 'esg_app'",
        [table],
    ).fetchone() == (False, False, False)


@pytest.mark.parametrize("statement", ["DELETE FROM run_jobs", "DELETE FROM core_documents", "TRUNCATE run_jobs"])
def test_app_role_cannot_delete_from_either_table(
    client: Client, owner: Owner, tenants: None, fake: FakeStorage, statement: str
) -> None:
    login(client, tenant_id="tenant-a")
    upload_as(client, fake, owner)
    with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(statement)
    assert getattr(caught.value.__cause__, "sqlstate", None) == "42501"  # insufficient_privilege
    assert (count(owner, "core_documents"), count(owner, "run_jobs")) == (1, 1)  # 행 그대로


# ── 격리 ──


def test_another_tenant_sees_nothing_and_changes_nothing(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, b = companies
    login(client, tenant_id="tenant-a")
    document_id = upload_as(client, fake, owner)
    before = facts(owner)
    assert before == [(a, "uploaded", 100, True, 1)]  # 분모: 주인이 센 A 의 행(문서 1, 일감 1)
    head_calls = len(fake.head_calls)

    # A 자신은 본다.
    assert client.get(f"/api/documents/{document_id}").status_code == 200

    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    seen = other.get(f"/api/documents/{document_id}")
    assert (seen.status_code, seen.json()["error"]["code"]) == (404, "NOT_FOUND")
    confirmed = other.post(f"/api/documents/{document_id}/confirm")
    assert (confirmed.status_code, confirmed.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert len(fake.head_calls) == head_calls  # 저장소에 묻지도 않았다
    assert facts(owner) == before  # 행이 그대로다

    # 경로를 건너뛰고 selector·service 를 B 의 인자로 바로 불러도 0행이다. 고치려 해도 대상이 0행이다.
    def enqueue(**kwargs: Any) -> None:
        raise AssertionError(f"B 의 올림 확인이 큐에 넣으려 했다: {kwargs}")

    with transaction.atomic():
        assert selectors.find_document(company_id=b, document_id=document_id) is None
        assert selectors.jobs_of(company_id=b, document_id=document_id) == ()
        assert selectors.get_document(company_id=b, document_id=document_id) == selectors.DocumentNotFound()
        confirmed_by_b = services.confirm_upload(
            company_id=b, document_id=document_id, storage=fake, now=NOW, enqueue=enqueue
        )
        assert confirmed_by_b == selectors.DocumentNotFound()
        assert DocumentRow.for_company(b).filter(pk=document_id).update(file_name="뺏었다") == 0
        assert JobRow.for_company(b).filter(document_id=document_id).update(status="failed") == 0
        # 분모: 같은 연결에서 A 의 인자로는 보이고, 범위 밖에서 세면 문서 1·일감 1 이다
        # (위의 0 이 「아무에게도 안 보임」이 아니다).
        assert selectors.find_document(company_id=a, document_id=document_id) is not None
        assert len(selectors.jobs_of(company_id=a, document_id=document_id)) == 1
        assert (DocumentRow.unscoped.count(), JobRow.unscoped.count()) == (1, 1)
    assert len(fake.head_calls) == head_calls  # B 의 올림 확인은 저장소에 묻지도 않았다
    assert facts(owner) == before
    assert owner.execute("SELECT count(*) FROM core_documents WHERE file_name = '뺏었다'").fetchone() == (0,)


def test_an_unscoped_query_on_either_table_is_refused(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """테넌트를 정하지 않은 조회(기본 매니저, 역방향 관계 매니저)는 DB 로 가기 전에 UnscopedQueryError 다."""
    login(client, tenant_id="tenant-a")
    document_id = upload_as(client, fake, owner)
    with pytest.raises(UnscopedQueryError):
        DocumentRow.objects.count()
    with pytest.raises(UnscopedQueryError):
        JobRow.objects.count()
    with pytest.raises(UnscopedQueryError):
        DocumentRow.objects.filter(pk=document_id).first()
    with pytest.raises(UnscopedQueryError):
        JobRow.objects.filter(document_id=document_id).update(status="failed")
    document = DocumentRow.for_company(companies[0]).get(pk=document_id)
    reverse = "jobs"  # JobRow.document 의 related_name(타입 검사기는 역방향 관계를 모른다)
    with pytest.raises(UnscopedQueryError):
        getattr(document, reverse).count()  # 역방향 관계 매니저도 기본 매니저의 꼴이다
    assert (count(owner, "core_documents"), count(owner, "run_jobs")) == (1, 1)  # 실제로는 있다
    assert (DocumentRow.unscoped.count(), JobRow.unscoped.count()) == (1, 1)  # 앱 역할도 범위 밖에서는 본다
    assert owner.execute("SELECT status FROM run_jobs").fetchall() == [("queued",)]  # 고쳐지지 않았다


def test_each_tenant_gets_its_own_documents(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, b = companies
    login(client, tenant_id="tenant-a")
    a_document = upload_as(client, fake, owner)
    other = Client()
    login(other, sub="edk-user-2", tenant_id="tenant-b")
    b_document = upload_as(other, fake, owner)
    assert [row[0] for row in facts(owner)] == [a, b]
    keys = owner.execute("SELECT id, storage_key FROM core_documents ORDER BY created_at").fetchall()
    assert [document_id for document_id, _ in keys] == [a_document, b_document]
    # 키의 회사 토막은 세션의 회사 id(subdomain 이 아니다), UUID 토막은 따로 지은 것(문서 id 가 아니다).
    key_ids: list[str] = []
    for company_id, (document_id, key) in zip((a, b), keys, strict=True):
        shape = re.fullmatch(rf"companies/{company_id}/documents/([0-9a-f-]{{36}})/original", key)
        assert shape is not None, key
        assert shape.group(1) != str(document_id)
        key_ids.append(shape.group(1))
    assert len(set(key_ids)) == 2
    assert other.get(f"/api/documents/{a_document}").status_code == 404
    assert client.get(f"/api/documents/{b_document}").status_code == 404


# ── 쓰기의 경계 (기본 매니저의 범위) ──


def test_a_document_for_another_tenant_is_refused_by_the_manager(owner: Owner, companies: tuple[int, int]) -> None:
    """서비스는 인자의 테넌트로 범위를 열고 같은 값으로 쓴다(그 길로는 어긋날 수 없다). 그래서 범위를 직접 연다."""
    a, b = companies
    with pytest.raises(CrossCompanyWriteError), transaction.atomic():
        DocumentRow.for_company(a).create(
            company_id=b,
            uploaded_by="someone",
            file_name="a.pdf",
            storage_key=f"companies/{b}/documents/x/original",
            size_bytes=5,
            status="awaiting_upload",
        )
    with pytest.raises(UnscopedQueryError), transaction.atomic():
        DocumentRow.objects.create(
            company_id=a,
            uploaded_by="someone",
            file_name="a.pdf",
            storage_key=f"companies/{a}/documents/x/original",
            size_bytes=5,
            status="awaiting_upload",
        )  # 범위를 열지 않았다
    assert count(owner, "core_documents") == 0


def test_a_job_for_another_tenant_is_refused_by_the_manager(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """일감은 ORM 으로 직접 넣어 잰다(서비스는 일감의 테넌트를 문서 행에서 읽으므로 서비스로는 이 길을 못 만든다)."""
    login(client, tenant_id="tenant-a")
    document_id = upload_as(client, fake, owner)
    a, b = companies
    with pytest.raises(CrossCompanyWriteError), transaction.atomic():
        JobRow.for_company(a).create(company_id=b, document_id=document_id, kind="parse", status="queued")
    with pytest.raises(CrossCompanyWriteError), transaction.atomic():
        JobRow.for_company(a).filter(document_id=document_id).update(company_id=b)
    with pytest.raises(UnscopedQueryError), transaction.atomic():
        JobRow.objects.create(company_id=a, document_id=document_id, kind="parse", status="queued")  # 범위 없음
    assert count(owner, "run_jobs") == 1
    assert owner.execute("SELECT company_id FROM run_jobs").fetchall() == [(a,)]


def test_a_job_on_another_tenants_document_is_refused_by_the_db(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """받침 ⑤: 일감의 (company_id, document_id) 는 문서의 (company_id, id) 를 가리킨다(migrations/0001).

    A 의 문서 id 를 아는 B 가 **자기 회사의** 일감을 그 문서에 걸려 하면 DB 가 그 문에서 거절한다(23503,
    NOT DEFERRABLE). 기본 매니저는 외래 키의 값을 보지 않으므로(범위의 조건이 아니다) 이것은 DB 만 막는다.
    주인 역할로 넣어도, 앱 역할의 ORM(unscoped)으로 넣어도 같다.
    """
    a, b = companies
    login(client, tenant_id="tenant-a")
    document_id = upload_as(client, fake, owner)
    assert owner.execute("SELECT company_id FROM core_documents WHERE id = %s", [document_id]).fetchall() == [
        (a,)
    ]  # 분모: 문서 행은 있다(A 의 것)
    assert count(owner, "run_jobs") == 1  # 분모: A 의 일감 하나(올림 확인이 만든 것)

    with pytest.raises(psycopg.errors.ForeignKeyViolation) as by_owner:
        add_job(owner, b, document_id)
    assert by_owner.value.sqlstate == "23503"

    with pytest.raises(IntegrityError) as by_app, transaction.atomic():
        JobRow.unscoped.create(company_id=b, document_id=document_id, kind="parse", status="queued")
    cause = by_app.value.__cause__
    assert isinstance(cause, psycopg.Error)
    assert cause.sqlstate == "23503"

    assert owner.execute(
        "SELECT company_id, count(*) FROM run_jobs WHERE document_id = %s GROUP BY 1 ORDER BY 1", [document_id]
    ).fetchall() == [(a, 1)]  # B 의 일감은 0행
    # A 의 상태 보기에도 A 의 일감만 나온다.
    assert len(client.get(f"/api/documents/{document_id}").json()["jobs"]) == 1


# ── summary 의 크기 ──


def test_summary_is_a_small_summary_enforced_by_the_db(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """경계(4096)는 재지 않는다: 재는 것이 PostgreSQL 이 jsonb 를 다시 적은 글자의 길이라 파이썬의 길이와 어긋난다.

    넉넉히 넘는 값(5,000자 글자 하나)은 거절, 넉넉히 작은 값(100자)은 받는다. 주인 연결로도, 앱 역할로도.
    """
    login(client, tenant_id="tenant-a")
    document_id = upload_as(client, fake, owner)
    big = '{"note": "' + "x" * 5000 + '"}'
    small = '{"note": "' + "x" * 100 + '"}'

    with pytest.raises(psycopg.errors.CheckViolation, match="run_jobs_summary_size_check"):
        add_job(owner, companies[0], document_id, summary=big)
    add_job(owner, companies[0], document_id, summary=small)
    assert count(owner, "run_jobs") == 2

    with pytest.raises(DatabaseError, match="run_jobs_summary_size_check"), transaction.atomic():
        JobRow.unscoped.filter(document_id=document_id).update(summary={"note": "x" * 5000})
    with transaction.atomic():
        assert JobRow.unscoped.filter(document_id=document_id).update(summary={"note": "x" * 100}) == 2
    sizes = owner.execute("SELECT octet_length(summary::text) FROM run_jobs").fetchall()
    assert all(size <= 4096 for (size,) in sizes) and len(sizes) == 2


# ── 갈고리의 때 ──


def test_the_hook_runs_after_the_commit(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """미들웨어를 거친 성공 요청에서 갈고리가 불린 순간: 트랜잭션 밖이고, 다른 연결이 그 일감을 queued 로 본다."""
    seen: list[tuple[bool, tuple[Any, ...] | None, dict[str, Any]]] = []

    def spy(**kwargs: Any) -> None:
        visible = owner.execute("SELECT status, company_id FROM run_jobs WHERE id = %s", [kwargs["job_id"]]).fetchone()
        seen.append((connection.in_atomic_block, visible, kwargs))

    monkeypatch.setattr(hooks, "enqueue_job", spy)
    login(client, tenant_id="tenant-a")
    upload_as(client, fake, owner)

    assert len(seen) == 1
    in_atomic_block, visible, kwargs = seen[0]
    assert in_atomic_block is False  # (a) 커밋이 끝난 뒤다
    assert visible == ("queued", companies[0])  # (b) 주인 연결(다른 연결)이 그 행을 본다
    assert (kwargs["company_id"], kwargs["kind"]) == (companies[0], "parse")


def test_a_hook_that_raises_leaves_the_commit_and_the_200(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """진짜 커밋에서: 갈고리가 던져도 응답은 200 이고(upload_as 가 단언한다) 문서·일감 행은 커밋돼 있다."""
    calls: list[int] = []

    def broken(**kwargs: Any) -> None:
        calls.append(kwargs["job_id"])
        raise RuntimeError("가짜 브로커가 죽었다")

    monkeypatch.setattr(hooks, "enqueue_job", broken)
    login(client, tenant_id="tenant-a")
    upload_as(client, fake, owner)
    assert len(calls) == 1
    assert facts(owner) == [(companies[0], "uploaded", 100, True, 1)]


def test_a_refused_request_never_calls_the_hook(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = record_enqueued(monkeypatch)
    login(client, tenant_id="tenant-a")
    created = client.post(
        "/api/documents", data={"fileName": "a.pdf", "sizeBytes": 100}, content_type="application/json"
    )
    document_id = created.json()["document"]["id"]
    assert client.post(f"/api/documents/{document_id}/confirm").status_code == 409  # 아직 안 올렸다
    assert client.post(f"/api/documents/{document_id + 1}/confirm").status_code == 404  # 없는 문서(행은 하나뿐)
    assert calls == []
    assert facts(owner) == [(companies[0], "awaiting_upload", 100, False, 0)]


def test_a_callback_registered_in_a_block_that_rolls_back_is_dropped(owner: Owner, tenants: None) -> None:
    """버리는 주체는 블록이다(요청마다의 트랜잭션이 없다): on_commit 을 건 블록이 예외로 되돌려지면 콜백은 0 번.

    같은 꼴로 블록이 커밋되면 1 번 불린다(대조: 콜백이 걸리기는 했다는 것).
    """
    calls: list[str] = []
    assert not connection.in_atomic_block  # 진짜 블록이다(세이브포인트가 아니다)

    with pytest.raises(RuntimeError), transaction.atomic():
        transaction.on_commit(lambda: calls.append("called-after-rollback"), robust=True)
        raise RuntimeError("가짜: 블록 안의 실패")
    assert calls == []
    with transaction.atomic():
        transaction.on_commit(lambda: calls.append("called-after-commit"), robust=True)
    assert calls == ["called-after-commit"]


def test_the_storage_head_runs_outside_a_transaction(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """올림 확인의 head(바깥 호출)는 트랜잭션을 쥐지 않은 채 돈다. 잠금·갱신·일감은 그 뒤의 블록 하나다."""
    seen: list[bool] = []
    original = fake.head

    def recording(key: str) -> HeadResult:
        seen.append(connection.in_atomic_block)
        return original(key)

    def quiet(**kwargs: Any) -> None:
        pass

    monkeypatch.setattr(fake, "head", recording)
    monkeypatch.setattr(hooks, "enqueue_job", quiet)
    login(client, tenant_id="tenant-a")
    upload_as(client, fake, owner)  # 200 을 단언한다
    assert seen == [False]  # 분모: head 1 번
    assert facts(owner) == [(companies[0], "uploaded", 100, True, 1)]


def test_a_hook_registered_in_a_block_that_rolls_back_is_never_called(
    client: Client, owner: Owner, companies: tuple[int, int], fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """올림 확인의 블록 안에서 던지면(갱신·일감 뒤의 jobs_of) 그 블록이 되돌려져 갈고리는 0 번, 행은 처음 그대로."""
    calls: list[int] = []

    def spy(**kwargs: Any) -> None:
        calls.append(kwargs["job_id"])

    def broken(**kwargs: Any) -> Any:
        raise RuntimeError("가짜: jobs_of 실패")

    monkeypatch.setattr(hooks, "enqueue_job", spy)
    login(client, tenant_id="tenant-a")
    created = client.post(
        "/api/documents", data={"fileName": "a.pdf", "sizeBytes": len(PDF)}, content_type="application/json"
    )
    document_id = created.json()["document"]["id"]
    row = owner.execute("SELECT storage_key FROM core_documents WHERE id = %s", [document_id]).fetchone()
    assert row is not None
    fake.put(row[0], PDF)
    assert facts(owner) == [(companies[0], "awaiting_upload", 100, False, 0)]  # 분모: 문서 1
    monkeypatch.setattr(selectors, "jobs_of", broken)
    assert client.post(f"/api/documents/{document_id}/confirm").status_code == 500  # 예상 못 한 예외(E2: 503 → 500)
    assert calls == []
    assert facts(owner) == [(companies[0], "awaiting_upload", 100, False, 0)]
