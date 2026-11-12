"""영문번역의 결과 경로와 「실패 쪽만 다시」(밴드 TR2 §3-4)를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 남의 회사 실행의 결과: A 의 끝난 영문번역 실행(주인 역할로 심음) id 로 B 의 세션·Bearer → GET 결과 404, 없는 이웃
     id 와 상태·본문 바이트까지 같다. 분모: A 의 세션으로 200·심은 본문 그대로.
  ⓑ 남의 회사 실행을 `retry.fromRunId` 로: B 가 A 의 실행 id 를 옵션에 넣어 실행을 만들고 실행기(모의 공급사)로 끝까지
     돌리면 그 실행은 done·결과 rejected `retry_source_not_found` 이고, A 의 글(심은 표지 글)이 B 의 결과·단계 산출·
     호출 기록에 0, 공급사 호출 0, A 의 실행 넷 행은 그대로. 분모: 같은 실행 id 를 A 의 회사로 읽으면 앞 실행이 찾아진다
     (RetryFound — 심은 실행이 다시 돌릴 수 있는 꼴이다).
     ★ `retry.fromRunId` 는 옵션 안의 id 라 tests/security/test_tenant_paths.py 의 ID_FIELDS 검사(본문의 `id`·`…Id`
       칸을 이름으로 찾는다 — 옵션은 자유 JSON 이라 openapi 에 칸이 없다) 밖이다. 이 파일의 ⓑ 가 유일한 잠금이다.
  ⓒ 세션 없이 401, 운영 관리자 Bearer 는 회사 둘이라 400 `COMPANY_AMBIGUOUS`(MARC-ENT-380 — 회사 하나면 통과는
     test_operator_company ⑩).
  ⓓ 용어집 두 경로(밴드 TR3a §3-4 — 상태 없음, 회사를 고르지 않음): 세션 없이 401 둘 · 운영 관리자 Bearer(회사 둘)도
     200 둘(NOT_CHOOSING 갈래) · 고객사의 쿠키 세션(CSRF 머리 없음)·Bearer 로 읽기 200 — runs_create 와 같은 인증 틀
     (★F) · 읽은 뒤 두 회사의 표 행 그대로·공급사 호출 0 · 로그에 칸 값 0 · 공격 xlsx(DOCTYPE·100만 겹)도 200
     unsafe_xlsx 이고 2초 안.

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다. 문서·결과는 전부 지어낸 것이다.
무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다. 공급사는 MockProvider 뿐이다(키·
네트워크 0 — context.build_client 의 make 를 간다).
"""

import hashlib
import json
import logging
import time
from functools import partial
from pathlib import Path
from typing import Any, Final

import psycopg
import pytest
from django.test import Client
from psycopg import sql

from esgapi.config.env import JobSettings
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.resources import queue as hooks
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs import context, tasks
from esgapi.translation.flows.colab_158 import RetryFound
from esgapi.translation.service.actions.retry_source import RunRetrySource
from esgapi.translation.tests.tools import glossary_support
from tests.security.test_runs import TABLES
from tests.support.http import customer_bearer, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
EXAMPLE: Final = Path(__file__).resolve().parents[2] / "esgapi/translation/tests/data/examples/result-sample.json"
SOURCE: Final = "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다."
MARKER: Final = "Secret Marker Of Company A"
"""A 의 심은 결과에만 있는 글. B 쪽 어디에도 나오면 안 된다."""
OPTIONS: Final[dict[str, Any]] = {
    "company": {"name": "가상고객사", "preferredSubject": "가상 업종", "industryStandards": "GRI"},
    "part": "general",
    "style": {"compareAb": False, "single": "B"},
    "pages": {"start": None, "end": None},
    "ceoPageLimit": 6,
}
SETTINGS: Final = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)


class RetryAsked(Exception):
    """가짜 태스크의 retry 가 돌려주는 것(이 층에 브로커가 없다)."""


class FakeTask:
    def retry(self, **_: Any) -> RetryAsked:
        return RetryAsked()


def ignore(**_: Any) -> None:
    """큐 갈고리 자리: 쪽지를 버린다(실행기는 시험이 직접 부른다)."""


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def owner_text_document(owner: Owner, fake: FakeStorage, company_id: int, key: str) -> int:
    """그 회사의 지어낸 txt 문서 하나(바이트는 가짜 저장소에). 주인 역할로."""
    storage_key = f"companies/{company_id}/documents/tr2-{key}/original"
    etag = fake.put(storage_key, SOURCE.encode())
    row = owner.execute(
        "INSERT INTO core_documents (created_at, updated_at, company_id, uploaded_by, file_name, storage_key, "
        "size_bytes, etag, status) VALUES (now(), now(), %s, '1', 'synthetic.txt', %s, %s, %s, 'uploaded') "
        "RETURNING id",
        [company_id, storage_key, len(SOURCE.encode()), etag],
    ).fetchone()
    assert row is not None
    return int(row[0])


def owner_done_translation(owner: Owner, fake: FakeStorage, company_id: int) -> int:
    """끝난 영문번역 실행 하나와 그 결과(계약 예시 result-sample 에 표지 글·이 원문의 sha256). 주인 역할로.
    원문·문체가 B 의 실행과 같아 회사 조건만 없으면 다시 돌릴 앞 실행이 된다(ⓑ 가 회사 조건 하나를 잰다)."""
    document_id = owner_text_document(owner, fake, company_id, "a")
    body = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    body["document"]["sourceSha256"] = sha256_of(SOURCE)
    body["variants"][0]["translatedText"] = f"[PAGE 1]\n[BLOCK 1]\n{MARKER}\n{MARKER}."
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, %s, 'translation', 'translation.colab@158', %s::jsonb, '{}', 'service', 'done', "
        "1, 0, 7) RETURNING id",
        [company_id, document_id, json.dumps(OPTIONS)],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, 'translation.result@1', %s::jsonb)",
        [company_id, run_id, json.dumps(body, ensure_ascii=False)],
    )
    return run_id


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    """문서 저장소 틈에 가짜를 꽂고 큐 갈고리는 버린다."""
    monkeypatch.setattr(hooks, "enqueue_run", ignore)
    return plug_storage(monkeypatch, FakeStorage())


VIA: Final = ("session", "bearer")


def session_of(via: str, company_id: int, tenant: str, sub: str) -> Client:
    if via == "session":
        client = Client()
        login(client, sub=sub, tenant_id=tenant)
        return client
    access = customer_bearer(Client(), company_id=company_id, subdomain=tenant)
    return Client(headers={"Authorization": f"Bearer {access}"})


def result_url(run_id: int) -> str:
    return f"/api/translation/runs/{run_id}/result"


# ── ⓐ ──


@pytest.mark.parametrize("via", VIA)
def test_another_companys_result_is_not_found_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    a, b = companies
    run_id = owner_done_translation(owner, fake, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    hidden = theirs.get(result_url(run_id))
    missing = theirs.get(result_url(run_id + 1000))
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    shown = mine.get(result_url(run_id))
    assert shown.status_code == 200, shown.content.decode()
    assert shown.json()["variants"][0]["translatedText"].count(MARKER) == 2  # 분모: 심은 본문 그대로


# ── ⓑ ──


def table_rows(owner: Owner, company_id: int) -> dict[str, int]:
    found: dict[str, int] = {}
    for table in TABLES:
        query = sql.SQL("SELECT count(*) FROM {} WHERE company_id = %s").format(sql.Identifier(table))
        row = owner.execute(query, [company_id]).fetchone()
        assert row is not None
        found[table] = int(row[0])
    return found


@pytest.mark.parametrize("via", VIA)
def test_retry_from_another_companys_run_is_rejected_without_its_text(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, monkeypatch: pytest.MonkeyPatch, via: str
) -> None:
    a, b = companies
    a_run = owner_done_translation(owner, fake, a)
    assert isinstance(RunRetrySource().base(a, a_run), RetryFound)  # 분모: 제 회사로는 다시 돌릴 앞 실행이다
    a_before = table_rows(owner, a)

    anthropic, openai, sink = MockProvider("anthropic"), MockProvider("openai"), MemorySink()

    def make(name: str, **kwargs: Any) -> Any:
        if name == "anthropic":
            return anthropic
        if name == "openai":
            return openai
        return llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))
    monkeypatch.setattr(context, "call_sink", lambda: sink)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)

    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    b_document = owner_text_document(owner, fake, b, "b")
    given = {**OPTIONS, "retry": {"fromRunId": a_run, "pages": [1]}}
    created = theirs.post(
        "/api/runs",
        data={"module": "translation", "documentId": b_document, "options": given},
        content_type="application/json",
    )
    assert created.status_code == 201, created.content.decode()
    b_run = int(created.json()["id"])
    try:
        tasks.execute_run(FakeTask(), company_id=str(b), run_id=str(b_run))
    except RetryAsked:  # pragma: no cover — 거절은 다시 넣기를 청하지 않는다
        pytest.fail("실행기가 다시 넣기를 청했다")

    status = owner.execute("SELECT status, error_code FROM run_runs WHERE id = %s", [b_run]).fetchone()
    assert status == ("done", None)
    result = theirs.get(result_url(b_run))
    assert result.status_code == 200, result.content.decode()
    assert result.json()["status"] == "rejected"
    assert result.json()["rejection"]["kind"] == "retry_source_not_found"
    b_texts = owner.execute(
        "SELECT body::text FROM run_results WHERE run_id = %s "
        "UNION ALL SELECT coalesce(data::text, '') || coalesce(partial::text, '') FROM run_steps WHERE run_id = %s",
        [b_run, b_run],
    ).fetchall()
    assert len(b_texts) >= 2  # 분모: 결과 하나·단계 셋을 읽었다
    assert [text for (text,) in b_texts if MARKER in text] == []
    assert MARKER not in repr(sink.records)
    assert (anthropic.calls, openai.calls) == ([], [])
    assert table_rows(owner, a) == a_before


# ── ⓒ ──


def test_without_a_session_the_result_is_401(owner: Owner, companies: tuple[int, int], fake: FakeStorage) -> None:
    run_id = owner_done_translation(owner, fake, companies[0])
    assert Client().get(result_url(run_id)).status_code == 401


def test_an_operator_bearer_with_two_companies_is_400_ambiguous_on_the_result(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    run_id = owner_done_translation(owner, fake, companies[0])
    created = create_operator(username="ops", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    response = operator.get(result_url(run_id))
    assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
    assert MARKER not in response.content.decode()


# ── ⓓ ──

GLOSSARY_READ: Final = "/api/translation/glossary/read"
GLOSSARY_TEMPLATE: Final = "/api/translation/glossary/template"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SECRET_KO: Final = "비밀가상용어"
SECRET_EN: Final = "Secret Glossary Term"
"""로그에 새지 않아야 하는 칸 값(지어낸 것)."""


def read_glossary(client: Client, data: bytes) -> Any:
    return client.generic("POST", GLOSSARY_READ, data, content_type=XLSX)


def both_tables(owner: Owner, companies: tuple[int, int]) -> tuple[dict[str, int], dict[str, int]]:
    return table_rows(owner, companies[0]), table_rows(owner, companies[1])


def test_without_a_session_the_glossary_paths_are_401(companies: tuple[int, int], fake: FakeStorage) -> None:
    data = glossary_support.glossary([("가상설비", "Virtual Facility")])
    assert read_glossary(Client(), data).status_code == 401
    assert Client().get(GLOSSARY_TEMPLATE).status_code == 401
    mine = session_of("session", companies[0], "tenant-a", "edk-user-1")
    assert read_glossary(mine, data).status_code == 200  # 분모: 세션이 있으면 지난다


def test_an_operator_bearer_reads_and_downloads_without_choosing_a_company(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """회사가 둘이어도(결과 경로는 400 COMPANY_AMBIGUOUS — ⓒ) 용어집 둘은 회사를 고르지 않아 200, 회사 행은 그대로."""
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    created = create_operator(username="ops", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    run_id = owner_done_translation(owner, fake, companies[0])
    assert operator.get(result_url(run_id)).json()["error"]["code"] == "COMPANY_AMBIGUOUS"  # 분모: 회사가 둘이다
    before = both_tables(owner, companies)
    read = read_glossary(operator, glossary_support.glossary([("가상설비", "Virtual Facility")]))
    assert (read.status_code, read.json()["ok"], read.json()["rowCount"]) == (200, True, 1)
    template = operator.get(GLOSSARY_TEMPLATE)
    assert (template.status_code, template["Content-Type"]) == (200, XLSX)
    assert both_tables(owner, companies) == before


@pytest.mark.parametrize("via", VIA)
def test_a_customer_reads_by_cookie_without_csrf_or_by_bearer_and_nothing_is_written_or_logged(
    owner: Owner,
    companies: tuple[int, int],
    fake: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    via: str,
) -> None:
    """★F: 쿠키 세션은 CSRF 머리 없이 지난다 — runs_create 와 같은 인증 틀(`/translation` 과 `/runs` 는 같은 auth 목록,
    쿠키 인증은 csrf=False · SameSite=Lax). 읽기는 두 회사의 표 행·저장소 객체를 바꾸지 않고 공급사를 부르지 않으며,
    로그·거절 글에 칸의 값이 없다."""
    calls: list[str] = []

    def make(name: str, **_: Any) -> Any:
        calls.append(name)
        return MockProvider(name)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))
    client = session_of(via, companies[0], "tenant-a", "edk-user-1")
    created = client.post(
        "/api/runs",
        data={"module": "translation", "documentId": 999_999, "options": OPTIONS},
        content_type="application/json",
    )
    assert created.status_code == 404  # 분모: 같은 클라이언트로 runs_create 도 인증·권한을 지나 몸까지 간다(없는 문서)
    before = (both_tables(owner, companies), dict(fake.objects))
    caplog.set_level(logging.DEBUG)
    good = read_glossary(client, glossary_support.glossary([(SECRET_KO, SECRET_EN)]))
    bad = read_glossary(client, glossary_support.glossary([(SECRET_KO, SECRET_EN), (SECRET_KO, SECRET_EN)]))
    assert (good.status_code, good.json()["pairs"]) == (200, [{"ko": SECRET_KO, "en": SECRET_EN}])
    assert (bad.status_code, bad.json()["kind"], bad.json()["row"]) == (200, "duplicate_ko", 3)
    assert (both_tables(owner, companies), dict(fake.objects)) == before
    assert calls == []
    assert caplog.records  # 분모: 접근 줄이 잡혔다
    assert SECRET_KO not in caplog.text and SECRET_EN not in caplog.text
    assert SECRET_KO not in bad.content.decode()


@pytest.mark.parametrize("attack", ["doctype", "laughs", "deep"])
def test_an_attack_xlsx_through_the_path_is_200_unsafe_within_two_seconds(
    companies: tuple[int, int], fake: FakeStorage, attack: str
) -> None:
    plain = glossary_support.glossary([("가상설비", "Virtual Facility")])
    sheet = glossary_support.entries(plain)[glossary_support.SHEET]
    replaced = {
        "doctype": glossary_support.with_doctype(sheet),
        "laughs": glossary_support.laughs(),
        "deep": glossary_support.deep_sheet(1_000_000),
    }[attack]
    data = glossary_support.rezip(plain, replace={glossary_support.SHEET: replaced})
    client = session_of("bearer", companies[0], "tenant-a", "edk-user-1")
    started = time.perf_counter()
    response = read_glossary(client, data)
    elapsed = time.perf_counter() - started
    assert (response.status_code, response.json()["ok"], response.json()["kind"]) == (200, False, "unsafe_xlsx")
    assert elapsed < 2.0, elapsed
    assert read_glossary(client, plain).json()["ok"] is True  # 분모: 같은 파일의 정상 판은 읽힌다


# ── ⓔ 묶음 둘(밴드 TR3b §3-4 — 목록·하나 보기. zip 은 ③) ──
# 실행은 주인 역할로 심는다 — 옵션은 감싸지 않은 jsonb(옛 꼴)라 run_keys 의 옛 갈래로도 묶인다.

BATCH: Final = "0b1c2d3e-0000-4000-8000-0000000000b1"


def owner_batch_run(
    owner: Owner,
    company_id: int,
    document_id: int,
    batch_id: str | None,
    *,
    part: str = "general",
    module: str = "translation",
) -> int:
    """끝난 실행 하나(결과 없음 — 요약 없는 옛 실행 꼴). batch_id 가 None 이면 묶음 없는 실행."""
    options = {**OPTIONS, "part": part, **({"batchId": batch_id} if batch_id is not None else {})}
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id, finished_at) "
        "VALUES (now(), now(), %s, %s, %s, 'translation.colab@158', %s::jsonb, '{}', 'service', 'done', 1, 0, 7, "
        "now()) "
        "RETURNING id",
        [company_id, document_id, module, json.dumps(OPTIONS if module != "translation" else options)],
    ).fetchone()
    assert row is not None
    return int(row[0])


def batch_url(document_id: int, key: str) -> str:
    return f"/api/translation/documents/{document_id}/batches/{key}"


@pytest.mark.parametrize("via", VIA)
def test_another_companys_batch_is_404_like_a_missing_one(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """A 의 묶음(같은 batchId 를 B 도 씀)을 B 로: 하나 보기 404 — 없는 문서 id 와 상태·본문 바이트까지 같다. B 의 목록에
    A 의 묶음 0(documentId 로 A 의 문서를 집어도 빈 쪽). 분모: B 는 제 묶음을, A 는 제 묶음을 본다."""
    a, b = companies
    doc_a = owner_text_document(owner, fake, a, "batch-a")
    doc_b = owner_text_document(owner, fake, b, "batch-b")
    owner_batch_run(owner, a, doc_a, BATCH)
    single = owner_batch_run(owner, a, doc_a, None)
    owner_batch_run(owner, b, doc_b, BATCH)
    other = session_of(via, b, "tenant-b", "edk-user-2")
    theirs, missing = other.get(batch_url(doc_a, BATCH)), other.get(batch_url(doc_a + 1000, BATCH))
    assert (theirs.status_code, theirs.content) == (404, missing.content)
    assert other.get(batch_url(doc_a, f"run-{single}")).status_code == 404
    listed = other.get("/api/translation/batches").json()
    assert [(r["document"]["id"], r["batchKey"]) for r in listed["results"]] == [(doc_b, BATCH)]  # 분모: 제 것
    assert other.get(f"/api/translation/batches?documentId={doc_a}").json() == {
        "companyName": "나 회사",
        "count": 0,
        "isNext": False,
        "truncated": False,
        "results": [],
    }
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    assert mine.get(batch_url(doc_a, BATCH)).status_code == 200  # 분모
    assert {r["document"]["id"] for r in mine.get("/api/translation/batches").json()["results"]} == {doc_a}


def test_other_modules_and_a_batched_runs_run_key_are_404(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, _ = companies
    doc = owner_text_document(owner, fake, a, "batch-m")
    batched = owner_batch_run(owner, a, doc, BATCH)
    green = owner_batch_run(owner, a, doc, None, module="greenwash")
    verify = owner_batch_run(owner, a, doc, None, module="dataverify")
    mine = session_of("bearer", a, "tenant-a", "edk-user-1")
    for key in (f"run-{batched}", f"run-{green}", f"run-{verify}"):
        assert mine.get(batch_url(doc, key)).status_code == 404, key
    assert [r["batchKey"] for r in mine.get("/api/translation/batches").json()["results"]] == [BATCH]  # 분모


def test_without_a_session_the_batch_paths_are_401(companies: tuple[int, int]) -> None:
    assert Client().get("/api/translation/batches").status_code == 401
    assert Client().get(batch_url(1, BATCH)).status_code == 401
    mine = session_of("session", companies[0], "tenant-a", "edk-user-1")
    assert mine.get("/api/translation/batches").status_code == 200  # 분모


def test_the_operator_in_the_sole_company_sees_what_the_customer_sees(owner: Owner, fake: FakeStorage) -> None:
    """(MARC-ENT-380) 회사 하나(활성)면 운영 관리자 Bearer 의 목록·하나 보기 = 고객사 사용자의 것. mine 은 같은 규칙 —
    문서를 올린 사람(심은 문서는 사용자 1)이 아니면 빈 쪽. 회사 둘·없음·비활성 갈래는 test_operator_company ④ 의
    고리."""
    from tests.security.seed import add_company
    from tests.security.test_operator_company import operator_client

    solo = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    doc = owner_text_document(owner, fake, solo, "batch-op")
    owner_batch_run(owner, solo, doc, BATCH)
    operator, _admin = operator_client(owner)
    customer = Client(
        headers={"Authorization": f"Bearer {customer_bearer(Client(), company_id=solo, subdomain='tenant-a')}"}
    )
    for url in ("/api/translation/batches", batch_url(doc, BATCH)):
        got, want = operator.get(url), customer.get(url)
        assert (got.status_code, got.json()) == (200, want.json()), url
    assert operator.get("/api/translation/batches?mine=true").json()["count"] == 0
    assert operator.get("/api/translation/batches").json()["companyName"] == "가 회사"
    assert customer.get("/api/translation/batches?mine=true").json()["count"] == 0  # 고객사 사용자도 올린 사람이 아님


def owner_output(owner: Owner, fake: FakeStorage, company_id: int, run_id: int, name: str, data: bytes) -> None:
    key = f"runs/{company_id}/{run_id}/{name}"
    fake.put(key, data)
    owner.execute(
        "INSERT INTO run_files (created_at, company_id, run_id, step, name, media_type, storage_key, size_bytes, "
        "sha256) VALUES (now(), %s, %s, NULL, %s, 'application/octet-stream', %s, %s, %s)",
        [company_id, run_id, name, key, len(data), hashlib.sha256(data).hexdigest()],
    )


@pytest.mark.parametrize("via", VIA)
def test_another_companys_archive_is_404_and_my_zip_has_only_my_files(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """A·B 가 같은 batchId 로 자동수정 파일을 하나씩(지어낸 바이트). B 가 A 의 문서로 zip → 404(없는 문서와 바이트까지
    같음). A 의 zip 에는 A 의 바이트만. 분모: B 의 zip 은 B 의 바이트."""
    import io
    import zipfile

    a, b = companies
    doc_a = owner_text_document(owner, fake, a, "zip-a")
    doc_b = owner_text_document(owner, fake, b, "zip-b")
    owner_output(owner, fake, a, owner_batch_run(owner, a, doc_a, BATCH), "translation-autofix-b.docx", b"A-only")
    owner_output(owner, fake, b, owner_batch_run(owner, b, doc_b, BATCH), "translation-autofix-b.docx", b"B-only")
    other = session_of(via, b, "tenant-b", "edk-user-2")
    theirs = other.get(batch_url(doc_a, BATCH) + "/archive")
    missing = other.get(batch_url(doc_a + 1000, BATCH) + "/archive")
    assert (theirs.status_code, theirs.content) == (404, missing.content)

    def unzip(data: bytes) -> dict[str, bytes]:
        with zipfile.ZipFile(io.BytesIO(data)) as zipped:
            return {n: zipped.read(n) for n in zipped.namelist()}

    own = other.get(batch_url(doc_b, BATCH) + "/archive")
    assert unzip(b"".join(own.streaming_content)) == {"general-translation-autofix-b.docx": b"B-only"}  # pyright: ignore
    mine = session_of(via, a, "tenant-a", "edk-user-1").get(batch_url(doc_a, BATCH) + "/archive")
    assert unzip(b"".join(mine.streaming_content)) == {"general-translation-autofix-b.docx": b"A-only"}  # pyright: ignore


# ── ⓕ 문서 쪽 수(밴드 TRP6 §3-3 — GET /translation/documents/{document_id}/pages, MARC-ENT-452) ──
# A 의 문서는 [PAGE 37] 이 든 지어낸 txt 다 — SOURCE([PAGE 1])로는 B 의 값과 A 의 값을 가르지 못한다.

PAGED: Final = "[PAGE 1]\n가상 표지\n[PAGE 37]\n가상 본문입니다."


def owner_paged_document(owner: Owner, fake: FakeStorage, company_id: int, key: str, data: bytes) -> int:
    """그 회사의 지어낸 문서 하나(바이트 `data` 는 가짜 저장소에 — 쪽 번호가 눈에 띄는 꼴). 주인 역할로."""
    storage_key = f"companies/{company_id}/documents/trp6-{key}/original"
    etag = fake.put(storage_key, data)
    row = owner.execute(
        "INSERT INTO core_documents (created_at, updated_at, company_id, uploaded_by, file_name, storage_key, "
        "size_bytes, etag, status) VALUES (now(), now(), %s, '1', 'synthetic-pages', %s, %s, %s, 'uploaded') "
        "RETURNING id",
        [company_id, storage_key, len(data), etag],
    ).fetchone()
    assert row is not None
    return int(row[0])


def pages_url(document_id: int) -> str:
    return f"/api/translation/documents/{document_id}/pages"


@pytest.mark.parametrize("via", VIA)
def test_another_companys_page_count_is_404_like_a_missing_document(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """A 의 문서를 B 로: 404 — 없는 문서 id 와 상태·본문 바이트까지 같고 A 의 쪽 수(37) 0. 분모: A 는 37."""
    a, b = companies
    doc_a = owner_paged_document(owner, fake, a, "pages-a", PAGED.encode())
    other = session_of(via, b, "tenant-b", "edk-user-2")
    theirs, missing = other.get(pages_url(doc_a)), other.get(pages_url(doc_a + 1000))
    assert (theirs.status_code, theirs.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (theirs.status_code, theirs.content) == (missing.status_code, missing.content)
    assert "37" not in theirs.content.decode()
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    shown = mine.get(pages_url(doc_a))
    assert (shown.status_code, shown.json()) == (200, {"documentId": doc_a, "pageCount": 37})  # 분모


def test_without_a_session_the_page_count_is_401(owner: Owner, companies: tuple[int, int], fake: FakeStorage) -> None:
    doc = owner_paged_document(owner, fake, companies[0], "pages-401", PAGED.encode())
    assert Client().get(pages_url(doc)).status_code == 401
    mine = session_of("session", companies[0], "tenant-a", "edk-user-1")
    assert mine.get(pages_url(doc)).status_code == 200  # 분모


def test_the_operator_in_the_sole_company_reads_the_customers_page_count(owner: Owner, fake: FakeStorage) -> None:
    """(MARC-ENT-374·380) 회사 하나(활성)면 운영 관리자 Bearer 의 답 = 고객사 사용자의 답(37)."""
    from tests.security.seed import add_company
    from tests.security.test_operator_company import operator_client

    solo = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    doc = owner_paged_document(owner, fake, solo, "pages-op", PAGED.encode())
    operator, _admin = operator_client(owner)
    customer = Client(
        headers={"Authorization": f"Bearer {customer_bearer(Client(), company_id=solo, subdomain='tenant-a')}"}
    )
    got, want = operator.get(pages_url(doc)), customer.get(pages_url(doc))
    assert (
        (got.status_code, got.json()) == (want.status_code, want.json()) == (200, {"documentId": doc, "pageCount": 37})
    )


def test_a_vertical_merge_docx_through_the_path_answers_within_two_seconds(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """python-docx 로 13초 넘는 세로 병합 docx(700×2 — critic 탐침)도 경로는 2초 안에 답한다(read_document 0)."""
    from esgapi.translation.tests.docx_support import p, tbl, tc, tr, with_body

    first = tr(*(tc("가", '<w:vMerge w:val="restart"/>') for _ in range(2)))
    rest = tr(*(tc("", "<w:vMerge/>") for _ in range(2)))
    attack = owner_paged_document(
        owner, fake, companies[0], "pages-vmerge", with_body(tbl(first + rest * 699) + p("[PAGE 5]"))
    )
    normal = owner_paged_document(owner, fake, companies[0], "pages-plain", PAGED.encode())
    client = session_of("bearer", companies[0], "tenant-a", "edk-user-1")
    started = time.perf_counter()
    response = client.get(pages_url(attack))
    elapsed = time.perf_counter() - started
    assert (response.status_code, response.json()["pageCount"]) == (200, 5)
    assert elapsed < 2.0, elapsed
    assert client.get(pages_url(normal)).json()["pageCount"] == 37  # 분모: 정상 문서


# ── ⓖ layout 읽기(밴드 TRS3 — GET /translation/runs/{run_id}/layout, MARC-ENT-471 ③) ──


def owner_pdf_translation(owner: Owner, fake: FakeStorage, company_id: int, *, status: str = "done") -> int:
    """PDF 흐름(translation.pdf@158)의 영문번역 실행 하나. 끝났으면 결과 result@1·layout@1 둘(layout 의 원문에 MARKER —
    남의 회사에 새면 보인다). 주인 역할로. 몸은 계약 시험의 지어낸 layout(test_layout_shapes.a_layout)."""
    from esgapi.translation.tests.contracts.test_layout_shapes import a_layout

    document_id = owner_text_document(owner, fake, company_id, f"pdf-{status}")
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, %s, 'translation', 'translation.pdf@158', %s::jsonb, '{}', 'service', %s, "
        "1, 0, 7) RETURNING id",
        [company_id, document_id, json.dumps(OPTIONS), status],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    if status == "done":
        result = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        layout = a_layout()
        layout["units"][0]["members"][0]["source"] = MARKER
        for position, (shape, body) in enumerate((("translation.result@1", result), ("translation.layout@1", layout))):
            owner.execute(
                "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
                "VALUES (now(), %s, %s, %s, %s, %s::jsonb)",
                [company_id, run_id, position, shape, json.dumps(body, ensure_ascii=False)],
            )
    return run_id


def layout_url(run_id: int) -> str:
    return f"/api/translation/runs/{run_id}/layout"


@pytest.mark.parametrize("via", VIA)
def test_another_companys_layout_is_404_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    """A 의 끝난 PDF 실행을 B 로: 404, 없는 이웃 id 와 같은 답(글자까지) — A 의 원문(MARKER)이 새지 않는다.
    분모: A 로는 200 이고 MARKER 가 보인다."""
    a, b = companies
    run_id = owner_pdf_translation(owner, fake, a)
    other = session_of(via, b, "tenant-b", "edk-user-2")
    theirs, missing = other.get(layout_url(run_id)), other.get(layout_url(run_id + 1000))
    assert (theirs.status_code, theirs.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (theirs.status_code, theirs.content) == (missing.status_code, missing.content)
    assert MARKER not in theirs.content.decode()
    mine = session_of(via, a, "tenant-a", "edk-user-1").get(layout_url(run_id))
    assert mine.status_code == 200 and MARKER in mine.content.decode()


def test_a_word_run_has_no_layout_and_an_unfinished_pdf_run_is_409(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    """제 회사의 끝난 워드 실행(result@1 만)은 404, 끝나지 않은 PDF 실행은 409 RUN_NOT_DONE."""
    a, _ = companies
    word = owner_done_translation(owner, fake, a)
    running = owner_pdf_translation(owner, fake, a, status="processing")
    client = Client()
    login(client, tenant_id="tenant-a")
    got = client.get(layout_url(word))
    assert (got.status_code, got.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert client.get(result_url(word)).status_code == 200  # 분모: 같은 실행의 결과는 있다
    got = client.get(layout_url(running))
    assert (got.status_code, got.json()["error"]["code"]) == (409, "RUN_NOT_DONE")


def test_without_a_session_the_layout_is_401(owner: Owner, companies: tuple[int, int], fake: FakeStorage) -> None:
    run_id = owner_pdf_translation(owner, fake, companies[0])
    response = Client().get(layout_url(run_id))
    assert response.status_code == 401
    assert MARKER not in response.content.decode()


def test_the_operator_in_the_sole_company_reads_the_customers_layout(owner: Owner, fake: FakeStorage) -> None:
    """(MARC-ENT-374·380) 회사 하나(활성)면 운영 관리자 Bearer 의 답 = 고객사 사용자의 답(200, 같은 몸)."""
    from tests.security.seed import add_company
    from tests.security.test_operator_company import operator_client

    solo = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    run_id = owner_pdf_translation(owner, fake, solo)
    operator, _admin = operator_client(owner)
    customer = Client(
        headers={"Authorization": f"Bearer {customer_bearer(Client(), company_id=solo, subdomain='tenant-a')}"}
    )
    got, want = operator.get(layout_url(run_id)), customer.get(layout_url(run_id))
    assert (got.status_code, want.status_code) == (200, 200)
    assert got.json() == want.json() and got.json()["schemaVersion"] == "translation.layout@1"
