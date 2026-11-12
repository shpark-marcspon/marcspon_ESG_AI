"""운영 관리자 실행 기록 경로(AU1b-2 — GET /run-logs·/run-logs/metrics, AD-04)를 잰다. 업무 층.

주인 역할 연결에서 잰다(앱 역할의 경계는 보안 층 tests/security/test_run_logs.py 의 ⓐⓑⓒ).
실행 행은 runs 의 표를 등록부(apps.get_model)로 연다 — user 의 시험은 esgapi.runs.models 를 import 하지 않는다(계약 나).
재는 것: 칸 전부·새 것 먼저·쪽 · 거르기 · 꼴 422 · 없는 회사 404 · 고객사 403(몸 앞 — 회사 세기·실행 읽기 0) ·
is_initial 403 · 만든 사람 이름(지금 이름, 남의 회사 사람 null) · 토큰·비용 = 그 실행의 LLM 줄 합 · 처리 시간은
대기 포함(MARC-ENT-327) · 지표 다섯(처분 ⑤ — 시계 고정) · 쿼리 수.
AD4S: 검토 칸(그린워싱 화면이 검토를 보이는 실행에만 — 검토 행 없으면 pending) · AI 설정 칸 · review 거르기(count·쪽
앞) · 교차 행(남의 회사 검토 행이 같은 run_id — M2) · 원천이 없으면 전부 null. 결과·검토 행도 등록부로 심는다.
AD4S ②: GET /run-logs/export — 거르기가 목록과 같은 집합 · 줄 값 · 상한(409·셈 뒤 읽기 0·감사 0) · 머리(파일 이름·
nosniff·no-store) · 감사 download 한 줄 · 고객사 403(몸 0) · 없는 회사 404 · 꼴 422.
AD4D: GET /run-logs/{run_id} — 지은 실행 셋((a) 단계 칸 있는 줄 · (b) 단계 NULL 줄만 · (c) 섞임)의 단계 값·
stepUsageRecorded·합계(= 목록 줄과 같음) · 줄 없는 단계 0 · 단계 시간 = 처음 시작 → 끝 · 실패 단계·오류 코드 · 파일 둘 ·
쿼리 수 · 없는 id·남의 회사 404(몸 같음) · 고객사 403(몸 0).
RF1: GET /run-logs/{run_id}/files/{name} — 출력 파일 바이트·머리 넷·감사 한 줄(고른 회사) · OPERATOR_RUN_MODULES 밖
모듈도 200(고객사 길 /runs 의 운영 관리자 404 와 대비) · 고객사 403(몸 0·읽기 0) · 없는·남의 실행 404(몸 같음) · 없는
이름·단계 산출 파일·객체 없음 404 RUN_FILE_NOT_FOUND · 503 셋 · 회사 둘 400 · 쿼리 수. 실패 갈래는 전부 감사 0.
"""

import io
import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Literal

import pytest
from django.apps import apps
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from openpyxl import load_workbook

from esgapi.config.env import LlmSettings
from esgapi.core.auth import bearer as bearer_module
from esgapi.core.calc.run_metrics import KST
from esgapi.core.models import AuditEventRow, DocumentRow, LlmCallLogRow
from esgapi.core.permissions import OPERATOR_RUN_MODULES
from esgapi.core.resources.ports.storage import StorageDenied, StorageUnavailable
from esgapi.core.service.services import documents as documents_services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.extras import ExtrasRegistry
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.user.models import User
from esgapi.user.service.apis import run_logs as run_logs_api
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated
from tests.support.http import bearer, bearer_pair
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

PASSWORD = "Blue-Harbor-7310"
CHANGED = "Green-Valley-4821"
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=KST)  # 지표 시험의 서버 시계
OUT_KEYS = {
    "id",
    "module",
    "flowId",
    "documentId",
    "documentName",
    "status",
    "createdAt",
    "startedAt",
    "finishedAt",
    "createdByUserId",
    "createdByName",
    "createdByUsername",
    "durationSec",
    "tokens",
    "costUsd",
    "isTest",
    "review",
    "aiSetting",
    "launchKey",
    "launchFirstRunId",
    "launchIndex",
    "launchSize",
    "resumedFromRunId",
}
METRIC_KEYS = {"month", "runs", "averageDurationSec", "tokens", "costUsd", "failureRate", "aiProviderMock"}


@pytest.fixture(autouse=True)
def fast_hasher() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


@pytest.fixture
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_logs_api, "now", lambda: NOW)


def run_rows() -> Any:
    """실행 표의 unscoped 매니저(주인 역할로 심는다). 남의 models 를 import 하지 않으려 등록부에서 꺼낸다."""
    return apps.get_model("runs", "RunRow")._meta.managers_map["unscoped"]


def customer(company_id: int, username: str, name: str = "김담당") -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name=name, password=PASSWORD
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def changed_access(client: Client, *, username: str, subdomain: str | None) -> str:
    """로그인하고 비밀번호를 한 번 바꿔(is_initial 끔) 새 access."""
    first = bearer_pair(client, username=username, password=PASSWORD, company_subdomain=subdomain)
    changed = client.post(
        "/api/users/me/password",
        data={"currentPassword": PASSWORD, "newPassword": CHANGED},
        content_type="application/json",
        **bearer(first["access"]),
    )
    assert changed.status_code == 200, changed.content.decode()
    return changed.json()["access"]


def operator_access(client: Client) -> str:
    created = create_operator(username="ops", name="운영자", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    return changed_access(client, username="ops", subdomain=None)


def document(company_id: int, name: str = "보고서.pdf") -> int:
    row = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name=name,
        storage_key=f"companies/{company_id}/documents/{DocumentRow.unscoped.count()}/original",
        size_bytes=1,
        status="uploaded",
    )
    return row.pk


def made(
    company_id: int,
    doc: int | None,
    *,
    created_at: datetime | None = None,
    took: timedelta | None = None,
    **extra: Any,
) -> int:
    """실행 한 줄. created_at 을 주면 그때로 옮기고, took 을 주면 finished_at = created_at + took."""
    values: dict[str, Any] = {
        "module": "greenwash",
        "flow_id": "greenwash.colab@E0",
        "status": "queued",
        "created_by_user_id": 7,
        **extra,
    }
    row = run_rows().create(company_id=company_id, document_id=doc, **values)
    if created_at is not None:
        moved: dict[str, Any] = {"created_at": created_at}
        if took is not None:
            moved["finished_at"] = created_at + took
        run_rows().filter(pk=row.pk).update(**moved)
    return row.pk


def call(
    company_id: int, run_id: int | None, *, input_tokens: int = 0, output_tokens: int = 0, cost: str = "0"
) -> None:
    LlmCallLogRow.for_company(company_id).create(
        company_id=company_id, module="greenwash", ts=NOW, call_id="c", attempt=1, prompt_id="p", prompt_version=1,
        template_hash="t", request_hash="r", duration_ms=1.0, result_kind="success", run_id=run_id,
        input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=Decimal(cost),
    )  # fmt: skip


def scanned(company_id: int, run_id: int, **body: Any) -> None:
    """그린워싱 결과 행 하나(greenwash.result@1, position 0). 기본은 점검한 실행(dryRun JSON null)."""
    apps.get_model("runs", "RunResultRow")._meta.managers_map["unscoped"].create(
        company_id=company_id,
        run_id=run_id,
        position=0,
        schema_version="greenwash.result@1",
        body={"schemaVersion": "greenwash.result@1", "dryRun": None, **body},
    )


def scan(company_id: int, doc: int, **extra: Any) -> int:
    """그린워싱 화면이 검토를 보이는 실행(done + 결과 dryRun null)."""
    run_id = made(company_id, doc, status="done", **extra)
    scanned(company_id, run_id)
    return run_id


def reviewed(company_id: int, run_id: int, state: str) -> None:
    """그린워싱 검토 행 하나(run_id 는 외래 키가 아니다 — 교차 행도 심을 수 있다)."""
    confirmed = state == "confirmed"
    apps.get_model("greenwash", "GreenwashReviewRow")._meta.managers_map["unscoped"].create(
        company_id=company_id,
        run_id=run_id,
        state=state,
        confirmed_at=NOW if confirmed else None,
        confirmed_by_user_id=1 if confirmed else None,
    )


def logs(client: Client, access: str, query: str) -> Any:
    return client.get(f"/api/run-logs?{query}", **bearer(access))


def metrics_of(client: Client, access: str, query: str) -> Any:
    return client.get(f"/api/run-logs/metrics?{query}", **bearer(access))


def page_ids(response: Any) -> list[int]:
    assert response.status_code == 200, response.content.decode()
    return [row["id"] for row in response.json()["results"]]


def error(response: Any) -> tuple[int, str | None]:
    """(상태, 오류 코드). 오류 몸이 아니면 코드는 None — 200 이 오면 단언이 (200, None) 으로 빨개진다."""
    return response.status_code, response.json().get("error", {}).get("code")


def at(day: int, hour: int = 10, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=KST)


# ── 목록 ────────────────────────────────────────────────────────────


def test_an_operator_reads_every_field_newest_first(client: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    access = operator_access(client)
    kim = customer(a, "kim", "김담당")
    older = made(a, document(a, "앞.pdf"), created_at=at(1), created_by_user_id=kim)
    newer = made(a, document(a, "뒤.pdf"), created_at=at(2), status="done", took=timedelta(seconds=90), purpose="test")
    made(b, document(b), created_at=at(3))  # 남의 회사
    response = logs(client, access, f"companyId={a}")
    assert page_ids(response) == [newer, older]
    body = response.json()
    assert (body["count"], body["isNext"]) == (2, False)
    first, second = body["results"]
    assert set(first) == OUT_KEYS
    assert first == {
        "id": newer,
        "module": "greenwash",
        "flowId": "greenwash.colab@E0",
        "documentId": first["documentId"],
        "documentName": "뒤.pdf",
        "status": "done",
        "createdAt": "2026-10-02T10:00:00+09:00",
        "startedAt": None,
        "finishedAt": "2026-10-02T10:01:30+09:00",
        "createdByUserId": 7,
        "createdByName": None,
        "createdByUsername": None,
        "durationSec": 90,
        "tokens": 0,
        "costUsd": 0.0,
        "isTest": True,
        "review": None,  # done 이지만 결과 행이 없다
        "aiSetting": None,
        "launchKey": None,  # LK1: 묶음 없이 만든 실행은 묶음 넷 null
        "launchFirstRunId": None,
        "launchIndex": None,
        "launchSize": None,
        "resumedFromRunId": None,
    }
    assert (second["createdByName"], second["createdByUsername"], second["durationSec"], second["isTest"]) == (
        "김담당",
        "kim",
        None,
        False,
    )
    paged = logs(client, access, f"companyId={a}&limit=1&offset=0").json()
    assert (paged["count"], paged["isNext"], [r["id"] for r in paged["results"]]) == (2, True, [newer])


def test_filters_reach_the_selector(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    green = made(a, document(a, "Alpha.pdf"), created_at=at(1), status="done", took=timedelta(seconds=1))
    other = made(a, document(a, "beta.pdf"), created_at=at(2), module="inventory", flow_id="inventory.x@1")
    assert page_ids(logs(client, access, f"companyId={a}")) == [other, green]  # 분모
    assert page_ids(logs(client, access, f"companyId={a}&module=greenwash")) == [green]
    assert page_ids(logs(client, access, f"companyId={a}&status=done")) == [green]
    assert page_ids(logs(client, access, f"companyId={a}&dateFrom=2026-10-02")) == [other]
    assert page_ids(logs(client, access, f"companyId={a}&dateTo=2026-10-01")) == [green]
    assert page_ids(logs(client, access, f"companyId={a}&q=ALPHA")) == [green]
    assert page_ids(logs(client, access, f"companyId={a}&q=alpha&status=queued")) == []


@pytest.mark.parametrize(
    "query",
    [
        "status=x",
        "dateFrom=1999-12-31",
        "dateTo=3000-01-01",
        "dateFrom=nope",
        "q=",
        f"q={'가' * 151}",
        "limit=101",
        "limit=0",
        "offset=-1",
        "module=",
        "review=bad",
        "review=",
    ],
)
def test_a_query_out_of_shape_is_422(client: Client, companies: tuple[int, int], query: str) -> None:
    a, _ = companies
    access = operator_access(client)
    assert error(logs(client, access, f"companyId={a}&{query}")) == (422, "VALIDATION_ERROR")


def test_the_date_ends_are_accepted(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    response = logs(client, access, f"companyId={a}&dateFrom=2000-01-01&dateTo=2999-12-31&q={'가' * 150}&limit=100")
    assert response.status_code == 200, response.content.decode()


def test_an_unknown_company_is_404(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    assert error(logs(client, access, "companyId=9000000")) == (404, "COMPANY_NOT_FOUND")
    assert error(metrics_of(client, access, "companyId=9000000")) == (404, "COMPANY_NOT_FOUND")
    assert logs(client, access, f"companyId={a}").status_code == 200  # 분모: 있는 회사는 지난다


# ── 권한 ──────────────────────────────────────────────────────────


def test_a_customer_gets_403_before_the_body_reads_anything(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    made(a, document(a), created_at=NOW)
    customer(a, "kim")
    access = changed_access(client, username="kim", subdomain="tenant-a")
    calls: list[str] = []
    real_ports = run_logs_api.company_ports
    real_page, real_cohort = operator_selectors.operator_run_page, operator_selectors.operator_run_cohort

    def ports() -> Any:
        calls.append("company_ports")
        return real_ports()

    def page(**kwargs: Any) -> Any:
        calls.append("operator_run_page")
        return real_page(**kwargs)

    def cohort(**kwargs: Any) -> Any:
        calls.append("operator_run_cohort")
        return real_cohort(**kwargs)

    monkeypatch.setattr(run_logs_api, "company_ports", ports)
    monkeypatch.setattr(operator_selectors, "operator_run_page", page)
    monkeypatch.setattr(operator_selectors, "operator_run_cohort", cohort)
    for send in (logs, metrics_of):
        with CaptureQueriesContext(connection) as seen:
            response = send(client, access, f"companyId={a}")
        assert error(response) == (403, "FORBIDDEN")
        assert {"results", "runs", "tokens"} & set(response.json()) == set()
        body_tables = ('"company"', '"run_runs"', '"core_llm_call_logs"', '"core_documents"')
        assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in body_tables)] == []
    assert calls == []  # 403 은 몸(회사 고르기) 앞이다
    # 분모: 운영 관리자의 같은 요청은 지나고 다 부른다
    operator = operator_access(Client())
    assert len(page_ids(logs(Client(), operator, f"companyId={a}"))) == 1
    assert metrics_of(Client(), operator, f"companyId={a}").status_code == 200
    assert calls == ["company_ports", "operator_run_page", "company_ports", "operator_run_cohort"]


def test_an_operator_before_changing_the_password_gets_403(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    create_operator(username="ops", name="운영자", password=PASSWORD)
    first = bearer_pair(client, username="ops", password=PASSWORD, company_subdomain=None)
    assert error(logs(client, first["access"], f"companyId={a}")) == (403, "PASSWORD_CHANGE_REQUIRED")
    assert error(metrics_of(client, first["access"], f"companyId={a}")) == (403, "PASSWORD_CHANGE_REQUIRED")


# ── 이름·토큰·비용·처리 시간 ─────────────────────────────────────────


def test_names_are_the_current_ones_and_other_companies_people_stay_null(
    client: Client, companies: tuple[int, int]
) -> None:
    a, b = companies
    access = operator_access(client)
    kim = customer(a, "kim", "김담당")
    park = customer(b, "park", "박담당")
    mine = made(a, document(a), created_at=at(1), created_by_user_id=kim)
    foreign = made(a, document(a), created_at=at(2), created_by_user_id=park)  # 남의 회사 사람의 id 가 실린 줄
    User.for_company(a).filter(pk=kim).update(name="김바뀜", username="kim2")
    rows = {row["id"]: row for row in logs(client, access, f"companyId={a}").json()["results"]}
    assert (rows[mine]["createdByName"], rows[mine]["createdByUsername"]) == ("김바뀜", "kim2")  # 지금 값
    assert (rows[foreign]["createdByName"], rows[foreign]["createdByUsername"]) == (None, None)
    assert rows[foreign]["createdByUserId"] == park  # id 는 그대로 싣는다


def test_tokens_and_cost_are_the_sum_of_the_runs_llm_lines(client: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    access = operator_access(client)
    used = made(a, document(a), created_at=at(1))
    idle = made(a, document(a), created_at=at(2))
    call(a, used, input_tokens=10, output_tokens=5, cost="0.25")
    call(a, used, input_tokens=1, output_tokens=0, cost="0.00000001")
    call(a, None, input_tokens=999, cost="9")  # 실행 밖(동기 계산) — 안 든다
    call(b, used, input_tokens=500, cost="5")  # 남의 회사 줄 — 안 든다
    rows = {row["id"]: row for row in logs(client, access, f"companyId={a}").json()["results"]}
    assert (rows[used]["tokens"], rows[used]["costUsd"]) == (16, 0.25000001)
    assert (rows[idle]["tokens"], rows[idle]["costUsd"]) == (0, 0.0)


def test_the_duration_includes_the_wait_from_created_at(
    client: Client, companies: tuple[int, int], fixed_clock: None
) -> None:
    """MARC-ENT-327: 만든 때 10:00 · 잡힌 때 10:05 · 끝난 때 10:10 인 done → 600 초(처리만이면 300)."""
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="done")
    run_rows().filter(pk=run_id).update(created_at=at(5, 10, 0), started_at=at(5, 10, 5), finished_at=at(5, 10, 10))
    [row] = logs(client, access, f"companyId={a}").json()["results"]
    assert (row["startedAt"], row["durationSec"]) == ("2026-10-05T10:05:00+09:00", 600)
    assert metrics_of(client, access, f"companyId={a}").json()["averageDurationSec"] == 600


# ── 지표 ──────────────────────────────────────────────────────────


def test_metrics_follow_the_rules_of_disposition_5(
    client: Client, companies: tuple[int, int], fixed_clock: None
) -> None:
    """서버 시계 2026-10-20 KST. 그달(10-01 00:00 KST ~ 11-01 00:00 KST)에 만든 service 실행만 센다."""
    a, b = companies
    access = operator_access(client)
    doc = document(a)
    start = datetime(2026, 10, 1, tzinfo=KST)
    fast = made(a, doc, created_at=start, status="done", took=timedelta(seconds=100))
    slow = made(a, doc, created_at=at(10), status="done", took=timedelta(seconds=201, microseconds=900000))
    failed = made(a, doc, created_at=at(11), status="failed", took=timedelta(seconds=5))
    made(a, doc, created_at=at(12))  # queued — 수에는 들고 평균·실패율에는 안 든다
    test_run = made(a, doc, created_at=at(13), status="failed", took=timedelta(seconds=1), purpose="test")
    before = made(a, doc, created_at=start - timedelta(microseconds=1), status="failed", took=timedelta(seconds=1))
    after = made(a, doc, created_at=datetime(2026, 11, 1, tzinfo=KST), status="failed", took=timedelta(seconds=1))
    made(b, document(b), created_at=at(10), status="failed", took=timedelta(seconds=1))  # 남의 회사
    call(a, fast, input_tokens=10, output_tokens=2, cost="0.1")
    call(a, failed, input_tokens=3, cost="0.02")
    for outside in (test_run, before, after):
        call(a, outside, input_tokens=1000, cost="9")  # 무리 밖·테스트 실행의 LLM 합은 안 든다
    body = metrics_of(client, access, f"companyId={a}").json()
    assert set(body) == METRIC_KEYS
    assert body == {
        "month": "2026-10",
        "runs": 4,
        "averageDurationSec": 151,  # (100 + 201) / 2 = 150.5 → 151(초 버림 뒤 절반 위로)
        "tokens": 15,
        "costUsd": 0.12,
        "failureRate": 1 / 3,
        "aiProviderMock": True,  # 시험 서버는 mock(LV1)
    }
    assert slow  # 그달의 done 둘째


def test_metrics_of_an_empty_month_are_zero_and_null(
    client: Client, companies: tuple[int, int], fixed_clock: None
) -> None:
    a, _ = companies
    access = operator_access(client)
    made(a, document(a), created_at=datetime(2026, 9, 30, tzinfo=KST), status="done", took=timedelta(seconds=1))
    assert metrics_of(client, access, f"companyId={a}").json() == {
        "month": "2026-10",
        "runs": 0,
        "averageDurationSec": None,
        "tokens": 0,
        "costUsd": 0.0,
        "failureRate": None,
        "aiProviderMock": True,  # 시험 서버는 LLM_RUN_MODE 없음 = mock(LV1)
    }


@pytest.mark.parametrize(("run_mode", "mock"), [("mock", True), ("live", False)])
def test_ai_provider_mock_follows_the_servers_run_mode_and_nothing_else_moves(
    client: Client,
    companies: tuple[int, int],
    fixed_clock: None,
    monkeypatch: pytest.MonkeyPatch,
    run_mode: Literal["mock", "live"],
    mock: bool,
) -> None:
    """LV1: aiProviderMock 은 응답한 서버의 LLM_RUN_MODE 가 live 가 아니면 참(AD-04 안내 띠). 다른 칸은 그대로."""
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), created_at=at(15), status="done", took=timedelta(minutes=2))
    call(a, run_id, input_tokens=10, output_tokens=2, cost="0.001")
    before = metrics_of(client, access, f"companyId={a}").json()
    settings = LlmSettings(openai_api_key="key-synthetic", log_sink="db", run_mode=run_mode, run_max_usd=0.3)
    monkeypatch.setattr(run_logs_api, "app_config", lambda: SimpleNamespace(llm=settings))
    after = metrics_of(client, access, f"companyId={a}").json()
    assert (before["aiProviderMock"], after["aiProviderMock"]) == (True, mock)
    assert {k: v for k, v in after.items() if k != "aiProviderMock"} == {
        k: v for k, v in before.items() if k != "aiProviderMock"
    }
    assert after["runs"] == 1  # 분모


# ── 쿼리 수 ──────────────────────────────────────────────────────


def body_queries(seen: CaptureQueriesContext) -> list[str]:
    """몸의 쿼리(회사 고르기·실행·LLM 합·이름 풀기) — 인증·토큰의 쿼리는 뺀다."""
    marks = (
        'FROM "company"',
        'FROM "run_runs"',
        'FROM "core_llm_call_logs"',
        '"users"."kind" = ',
        'FROM "greenwash_reviews"',
    )
    found: list[str] = []
    for query in seen.captured_queries:
        sql = query["sql"]
        if 'FROM "users"' in sql and "IN (" not in sql:
            continue  # 인증이 그 사람 하나를 읽는다
        if any(mark in sql for mark in marks):
            found.append(sql)
    return found


def test_query_counts(client: Client, companies: tuple[int, int], fixed_clock: None) -> None:
    a, _ = companies
    access = operator_access(client)
    with CaptureQueriesContext(connection) as empty_list:
        assert page_ids(logs(client, access, f"companyId={a}")) == []
    with CaptureQueriesContext(connection) as empty_metrics:
        assert metrics_of(client, access, f"companyId={a}").status_code == 200
    kim = customer(a, "kim")
    for day in (1, 2, 3):
        run_id = made(a, document(a), created_at=at(day), created_by_user_id=kim, status="done")
        scanned(a, run_id)
        call(a, run_id, input_tokens=1)
    with CaptureQueriesContext(connection) as full_list:
        assert len(page_ids(logs(client, access, f"companyId={a}"))) == 3
    with CaptureQueriesContext(connection) as full_metrics:
        assert metrics_of(client, access, f"companyId={a}").json()["runs"] == 3
    # 목록 = 회사 1 + 셈 1 + 쪽 1 + LLM 합 1(빈 쪽이면 0) + 이름 1(빈 쪽이면 0)
    # + 그린워싱 원천의 검토 가능 id 1·검토 상태 1(AD4S — 그 모듈 줄이 없으면 0, 검토 가능이 없으면 상태 0)
    assert (len(body_queries(empty_list)), len(body_queries(full_list))) == (3, 7)
    # 지표 = 회사 1 + 무리 1 + LLM 합 1(무리가 비면 0)
    assert (len(body_queries(empty_metrics)), len(body_queries(full_metrics))) == (2, 3)


# ── 검토·AI 설정(AD4S) ─────────────────────────────────────────────


def rows_of(client: Client, access: str, query: str) -> dict[int, Any]:
    response = logs(client, access, query)
    assert response.status_code == 200, response.content.decode()
    return {row["id"]: row for row in response.json()["results"]}


def test_the_review_is_shown_only_where_the_greenwash_screen_shows_it(
    client: Client, companies: tuple[int, int]
) -> None:
    a, _ = companies
    access = operator_access(client)
    doc = document(a)
    untouched = scan(a, doc)
    pending, in_review, confirmed = scan(a, doc), scan(a, doc), scan(a, doc)
    reviewed(a, pending, "pending")
    reviewed(a, in_review, "in_review")
    reviewed(a, confirmed, "confirmed")
    no_key = made(a, doc, status="done")
    apps.get_model("runs", "RunResultRow")._meta.managers_map["unscoped"].create(
        company_id=a, run_id=no_key, position=0, schema_version="greenwash.result@1", body={"items": []}
    )  # dryRun 키 없음 — 검토를 보인다(checks.py 의 result.get("dryRun") is None)
    queued = made(a, doc)
    failed = made(a, doc, status="failed")
    no_result = made(a, doc, status="done")
    dry_run = made(a, doc, status="done")
    scanned(a, dry_run, dryRun={"pagesChecked": 1})
    other_module = made(a, doc, status="done", module="inventory", flow_id="inventory.x@1")
    scanned(a, other_module)
    rows = rows_of(client, access, f"companyId={a}&limit=100")
    assert {run_id: row["review"] for run_id, row in rows.items()} == {
        untouched: "pending",
        pending: "pending",
        in_review: "in_review",
        confirmed: "confirmed",
        no_key: "pending",
        queued: None,
        failed: None,
        no_result: None,
        dry_run: None,
        other_module: None,  # 원천이 없는 모듈
    }


def test_the_review_filter_takes_the_same_rule(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    doc = document(a)
    untouched, pending, in_review, confirmed = scan(a, doc), scan(a, doc), scan(a, doc), scan(a, doc)
    reviewed(a, pending, "pending")
    reviewed(a, in_review, "in_review")
    reviewed(a, confirmed, "confirmed")
    queued = made(a, doc)
    dry_run = made(a, doc, status="done")
    scanned(a, dry_run, dryRun={"pagesChecked": 1})
    other_module = made(a, doc, status="done", module="inventory", flow_id="inventory.x@1")
    scanned(a, other_module)
    assert len(page_ids(logs(client, access, f"companyId={a}&limit=100"))) == 7  # 분모
    assert sorted(page_ids(logs(client, access, f"companyId={a}&review=pending"))) == sorted([untouched, pending])
    assert page_ids(logs(client, access, f"companyId={a}&review=in_review")) == [in_review]
    assert page_ids(logs(client, access, f"companyId={a}&review=confirmed")) == [confirmed]
    assert queued and dry_run and other_module  # 셋 다 어느 review 에도 들지 않는다
    # 검토 가능하지 않은 실행에 검토 행이 있어도(정상 길로는 안 생김) in_review·confirmed 거르기에 안 들고 칸은 null
    failed = made(a, doc, status="failed")
    no_result = made(a, doc, status="done")
    for run_id, state in ((dry_run, "confirmed"), (other_module, "confirmed"), (failed, "in_review")):
        reviewed(a, run_id, state)
    reviewed(a, no_result, "in_review")
    assert page_ids(logs(client, access, f"companyId={a}&review=confirmed")) == [confirmed]
    assert page_ids(logs(client, access, f"companyId={a}&review=in_review")) == [in_review]
    rows = rows_of(client, access, f"companyId={a}&limit=100")
    assert [rows[run_id]["review"] for run_id in (dry_run, other_module, failed, no_result)] == [None] * 4


def test_the_review_filter_counts_before_paging(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    doc = document(a)
    for _ in range(25):
        scan(a, doc)
    for _ in range(3):
        reviewed(a, scan(a, doc), "confirmed")
    body = logs(client, access, f"companyId={a}&review=pending").json()
    assert (body["count"], body["isNext"], len(body["results"])) == (25, True, 20)
    assert {row["review"] for row in body["results"]} == {"pending"}
    assert logs(client, access, f"companyId={a}").json()["count"] == 28  # 분모


def test_another_companys_review_row_does_not_reach_b(client: Client, companies: tuple[int, int]) -> None:
    """M2: 회사 A 의 검토 행(confirmed)이 run_id = B 의 실행 R_B 를 가리킨다. B 로 고르면 R_B 는 pending."""
    a, b = companies
    access = operator_access(client)
    r_b = scan(b, document(b))
    reviewed(a, r_b, "confirmed")  # 교차 행
    assert rows_of(client, access, f"companyId={b}")[r_b]["review"] == "pending"
    assert page_ids(logs(client, access, f"companyId={b}&review=confirmed")) == []
    assert page_ids(logs(client, access, f"companyId={b}&review=pending")) == [r_b]
    # 분모: B 에 confirmed 행을 심으면 R_B 는 confirmed
    reviewed(b, r_b, "confirmed")
    assert rows_of(client, access, f"companyId={b}")[r_b]["review"] == "confirmed"
    assert page_ids(logs(client, access, f"companyId={b}&review=confirmed")) == [r_b]


def test_the_ai_setting_comes_from_the_versions(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    doc = document(a)
    saved = made(a, doc, versions={"flow": "greenwash.colab@E0", "aiSetting": "v3", "aiSettingId": 12})
    default = made(a, doc, versions={"aiSetting": "colab-2026-01-15-v1", "aiSettingId": None})
    none = made(a, doc)
    other_module = made(a, doc, module="inventory", flow_id="inventory.x@1", versions={"aiSetting": "v3"})
    rows = rows_of(client, access, f"companyId={a}")
    assert {run_id: row["aiSetting"] for run_id, row in rows.items()} == {
        saved: {"id": 12, "name": "v3"},
        default: {"id": None, "name": "colab-2026-01-15-v1"},
        none: None,
        other_module: None,
    }


def test_without_a_source_every_review_is_null(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    access = operator_access(client)
    run_id = scan(a, document(a), versions={"aiSetting": "v3", "aiSettingId": 12})
    assert rows_of(client, access, f"companyId={a}")[run_id]["review"] == "pending"  # 분모
    monkeypatch.setattr(operator_selectors, "EXTRAS", ExtrasRegistry())
    row = rows_of(client, access, f"companyId={a}")[run_id]
    assert (row["review"], row["aiSetting"]) == (None, None)
    assert page_ids(logs(client, access, f"companyId={a}&review=pending")) == []


# ── 엑셀 내보내기(AD4S ②) ─────────────────────────────────────────


def export(client: Client, access: str, query: str) -> Any:
    return client.get(f"/api/run-logs/export?{query}", **bearer(access))


def sheet_rows(response: Any) -> list[tuple[object, ...]]:
    assert response.status_code == 200, response.content.decode()
    book = load_workbook(io.BytesIO(response.content))
    assert book.sheetnames == ["실행 기록"]
    return [tuple(cell.value for cell in row) for row in book["실행 기록"].iter_rows()]


def exported_audit() -> list[tuple[Any, ...]]:
    return list(
        AuditEventRow.unscoped.filter(event="run_logs_exported").values_list(
            "company_id", "action", "result", "target_kind", "target_id", "target_label"
        )
    )


def test_the_export_holds_the_same_runs_as_the_list(client: Client, companies: tuple[int, int]) -> None:
    """q·review·status 를 모두 준 같은 질의: 엑셀의 문서 열 = GET /run-logs?limit=100 의 문서 이름(차례째).
    q 가 한 줄 이상 뺀다(분모 — m7)."""
    a, b = companies
    access = operator_access(client)
    kept = [scan(a, document(a, f"Alpha {n}.pdf"), created_at=at(n)) for n in (1, 2, 3)]
    reviewed(a, kept[1], "confirmed")  # review=pending 이 뺀다
    scan(a, document(a, "beta.pdf"), created_at=at(4))  # q 가 뺀다
    made(a, document(a, "Alpha queued.pdf"), created_at=at(5))  # status·review 가 뺀다
    scan(b, document(b, "Alpha b.pdf"), created_at=at(6))  # 남의 회사
    query = f"companyId={a}&q=alpha&review=pending&status=done"
    listed = logs(client, access, f"{query}&limit=100").json()["results"]
    rows = sheet_rows(export(client, access, query))[1:]
    assert [row[2] for row in rows] == [row["documentName"] for row in listed] == ["Alpha 3.pdf", "Alpha 1.pdf"]
    assert len(sheet_rows(export(client, access, f"companyId={a}&review=pending&status=done"))) - 1 == 3  # 분모: q 없이


def test_an_exported_line_is_the_lines_values(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    kim = customer(a, "kim", "김담당")
    run_id = scan(
        a, document(a, "=1+1.pdf"), created_at=at(3), took=timedelta(seconds=90), created_by_user_id=kim,
        versions={"aiSetting": "v3", "aiSettingId": 12}, purpose="test",
    )  # fmt: skip
    reviewed(a, run_id, "in_review")
    call(a, run_id, input_tokens=10, output_tokens=5, cost="0.25")
    made(a, document(a, "대기.pdf"), created_at=at(4))  # queued — 수 칸 「–」, 올린 사람은 못 푼 id
    header, queued, done = sheet_rows(export(client, access, f"companyId={a}"))
    assert header[0] == "시각"
    assert done == (
        "2026-10-03T10:00:00+09:00", "그린워싱", "=1+1.pdf", "greenwash.colab@E0", "v3", "김담당", 90, 15, 0.25,
        "완료", "검토 중", "예",
    )  # fmt: skip
    assert queued[4:] == (None, "알 수 없는 사람", "–", "–", "–", "대기", None, None)


def test_the_exported_ai_setting_is_the_default_or_the_version_name(client: Client, companies: tuple[int, int]) -> None:
    """RL1(286): 기본 판(aiSettingId null)은 응답 name 이 아니라 「기본 설정」 · 판은 이름 · 판 없음은 빈칸."""
    a, _ = companies
    access = operator_access(client)
    doc = document(a)
    made(a, doc, created_at=at(1), versions={"aiSetting": "colab-2026-01-15-v1", "aiSettingId": None})
    made(a, doc, created_at=at(2), versions={"aiSetting": "v3", "aiSettingId": 12})
    made(a, doc, created_at=at(3))
    rows = sheet_rows(export(client, access, f"companyId={a}"))[1:]
    assert [row[4] for row in rows] == [None, "v3", "기본 설정"]  # 새 것 먼저


def test_the_export_cap_is_counted_before_reading(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    access = operator_access(client)
    monkeypatch.setattr(run_logs_api, "RUN_LOG_EXPORT_MAX", 2)
    doc = document(a)
    made(a, doc)
    made(a, doc)
    assert len(sheet_rows(export(client, access, f"companyId={a}"))) == 3  # 2건 = 상한 — 지난다
    assert len(exported_audit()) == 1
    made(a, doc)
    with CaptureQueriesContext(connection) as seen:
        response = export(client, access, f"companyId={a}")
    assert error(response) == (409, "RUN_LOG_EXPORT_TOO_LARGE")
    assert response.json()["error"]["legacyCode"] == "run_log_export_too_large"
    assert len(body_queries(seen)) == 2  # 회사 1 + 셈 1(행 읽기 0)
    assert len(exported_audit()) == 1  # 409 는 감사 0


def test_the_export_headers_and_its_audit_line(client: Client, companies: tuple[int, int], fixed_clock: None) -> None:
    a, _ = companies
    access = operator_access(client)
    made(a, document(a))
    response = export(client, access, f"companyId={a}")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    # 실행기록_2026-10-20_1200.xlsx(시계 고정 — KST)
    assert response["Content-Disposition"] == (
        "attachment; filename*=utf-8''%EC%8B%A4%ED%96%89%EA%B8%B0%EB%A1%9D_2026-10-20_1200.xlsx"
    )
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Cache-Control"] == "no-store"
    assert exported_audit() == [(a, "download", "success", "run_log_export", None, "실행기록_2026-10-20_1200.xlsx")]


def test_the_export_refuses_like_the_list(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    made(a, document(a))
    customer(a, "kim")
    kim = changed_access(client, username="kim", subdomain="tenant-a")
    calls: list[str] = []
    real = operator_selectors.operator_run_export

    def spy(**kwargs: Any) -> Any:
        calls.append("operator_run_export")
        return real(**kwargs)

    monkeypatch.setattr(operator_selectors, "operator_run_export", spy)
    refused = export(client, kim, f"companyId={a}")
    assert error(refused) == (403, "FORBIDDEN")
    assert refused.get("Content-Disposition") is None
    assert (calls, exported_audit()) == ([], [])
    operator = operator_access(Client())
    assert error(export(Client(), operator, "companyId=9000000")) == (404, "COMPANY_NOT_FOUND")
    for query in ("review=bad", "limit=1", "status=x"):
        response = export(Client(), operator, f"companyId={a}&{query}")
        if query == "limit=1":
            assert response.status_code == 200  # 쪽 칸은 받지 않는다(모르는 질의는 무시 — 목록과 같음)
        else:
            assert error(response) == (422, "VALIDATION_ERROR")
    assert len(sheet_rows(export(Client(), operator, f"companyId={a}"))) == 2  # 분모: 운영 관리자는 받는다
    assert calls == ["operator_run_export"] * 2


# ── 상세(AD4D — GET /run-logs/{run_id}) ──────────────────────────────


DETAIL_KEYS = OUT_KEYS | {"failedStep", "errorCode", "stepUsageRecorded", "steps", "files"}
STEP_KEYS = {"name", "position", "status", "startedAt", "finishedAt", "durationSec", "tokens", "costUsd"}


def detail(client: Client, access: str, run_id: int, company_id: int) -> Any:
    return client.get(f"/api/run-logs/{run_id}?companyId={company_id}", **bearer(access))


def step_rows() -> Any:
    return apps.get_model("runs", "RunStepRow")._meta.managers_map["unscoped"]


def staged(company_id: int, run_id: int, *steps: tuple[str, str, datetime | None, datetime | None]) -> None:
    """단계 행(이름·상태·처음 시작·끝)을 선언 차례로."""
    for position, (name, status, started, finished) in enumerate(steps):
        step_rows().create(
            company_id=company_id, run_id=run_id, name=name, position=position, status=status,
            started_at=started, finished_at=finished,
        )  # fmt: skip


def step_call(company_id: int, run_id: int, step: str | None, *, input_tokens: int, cost: str) -> None:
    LlmCallLogRow.for_company(company_id).create(
        company_id=company_id, module="greenwash", ts=NOW, call_id="c", attempt=1, prompt_id="p", prompt_version=1,
        template_hash="t", request_hash="r", duration_ms=1.0, result_kind="success", run_id=run_id, step=step,
        input_tokens=input_tokens, output_tokens=1, cost_usd=Decimal(cost),
    )  # fmt: skip


def three_steps(company_id: int, run_id: int) -> None:
    staged(
        company_id, run_id,
        ("extract", "done", at(5, 10, 1), at(5, 10, 2)),
        ("judge", "done", at(5, 10, 2), at(5, 10, 7)),
        ("report", "done", at(5, 10, 7), at(5, 10, 8)),
    )  # fmt: skip


def test_a_recorded_run_has_per_step_tokens_that_add_up_to_its_line(client: Client, companies: tuple[int, int]) -> None:
    """(a) 단계 칸이 실린 줄: 단계별 값 · 줄 없는 단계(report) 는 0 · 단계 합 == 줄의 tokens·costUsd == 목록 줄."""
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="done", created_at=at(5, 10, 0), took=timedelta(minutes=8))
    three_steps(a, run_id)
    step_call(a, run_id, "extract", input_tokens=10, cost="0.01")
    step_call(a, run_id, "judge", input_tokens=100, cost="0.2")
    step_call(a, run_id, "judge", input_tokens=20, cost="0.03")
    response = detail(client, access, run_id, a)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert set(body) == DETAIL_KEYS
    assert all(set(step) == STEP_KEYS for step in body["steps"])
    assert body["stepUsageRecorded"] is True
    assert [(s["name"], s["tokens"], s["costUsd"]) for s in body["steps"]] == [
        ("extract", 11, 0.01),
        ("judge", 122, 0.23),
        ("report", 0, 0.0),  # 기록된 실행에서 줄 없는 단계는 0(null 아님)
    ]
    assert sum(s["tokens"] for s in body["steps"]) == body["tokens"] == 133
    assert round(sum(s["costUsd"] for s in body["steps"]), 8) == body["costUsd"] == 0.24
    [line] = logs(client, access, f"companyId={a}").json()["results"]
    assert {key: body[key] for key in OUT_KEYS} == line  # 줄 칸은 목록의 줄과 같다


def test_a_run_before_ad4d_has_only_its_total(client: Client, companies: tuple[int, int]) -> None:
    """(b) 단계 NULL 줄만(지난 실행) · (c) 섞임: 단계 값 전부 null · stepUsageRecorded false · 합계는 그대로."""
    a, _ = companies
    access = operator_access(client)
    old = made(a, document(a), status="done", created_at=at(5, 10, 0), took=timedelta(minutes=8))
    mixed = made(a, document(a), status="done", created_at=at(6, 10, 0), took=timedelta(minutes=8))
    for run_id in (old, mixed):
        three_steps(a, run_id)
    step_call(a, old, None, input_tokens=40, cost="0.4")
    step_call(a, mixed, "judge", input_tokens=10, cost="0.1")
    step_call(a, mixed, None, input_tokens=5, cost="0.05")  # 단계 밖 줄 하나
    for run_id, total, cost in ((old, 41, 0.4), (mixed, 17, 0.15)):
        body = detail(client, access, run_id, a).json()
        assert body["stepUsageRecorded"] is False, run_id
        assert [(s["tokens"], s["costUsd"]) for s in body["steps"]] == [(None, None)] * 3, run_id
        assert (body["tokens"], body["costUsd"]) == (total, cost), run_id
    lines = {row["id"]: row for row in logs(client, access, f"companyId={a}").json()["results"]}
    assert (lines[mixed]["tokens"], lines[mixed]["costUsd"]) == (17, 0.15)  # 목록 줄의 합계와 같다


def test_a_step_name_outside_the_heads_folds_the_steps(client: Client, companies: tuple[int, int]) -> None:
    """RL1(290): 기록된 실행에 단계 머리에 없는 이름의 줄이 있으면 단계 합 ≠ 실행 합 — 단계 값 전부 null ·
    stepUsageRecorded false · 합계(줄 칸)는 그대로. 분모: 그 줄 앞에는 단계 값이 차고 합 = 합계."""
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="done", created_at=at(5, 10, 0), took=timedelta(minutes=8))
    three_steps(a, run_id)
    step_call(a, run_id, "judge", input_tokens=10, cost="0.1")
    body = detail(client, access, run_id, a).json()
    assert body["stepUsageRecorded"] is True
    assert [s["tokens"] for s in body["steps"]] == [0, 11, 0]
    assert sum(s["tokens"] for s in body["steps"]) == body["tokens"] == 11
    step_call(a, run_id, "retired", input_tokens=5, cost="0.05")
    body = detail(client, access, run_id, a).json()
    assert body["stepUsageRecorded"] is False
    assert [(s["tokens"], s["costUsd"]) for s in body["steps"]] == [(None, None)] * 3
    assert (body["tokens"], body["costUsd"]) == (17, 0.15)


def test_step_times_run_from_the_first_start_to_the_end(client: Client, companies: tuple[int, int]) -> None:
    """단계 시간 = 끝 − 처음 시작(초 버림). 실행의 만든 때가 아니다. 시작 전·끝나기 전은 null."""
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="processing", created_at=at(5, 9, 0))
    staged(
        a, run_id,
        ("extract", "done", at(5, 10, 0), at(5, 10, 1) + timedelta(seconds=30, microseconds=900000)),
        ("judge", "running", at(5, 10, 2), None),
        ("report", "pending", None, None),
    )  # fmt: skip
    steps = detail(client, access, run_id, a).json()["steps"]
    assert [(s["name"], s["status"], s["durationSec"]) for s in steps] == [
        ("extract", "done", 90),
        ("judge", "running", None),
        ("report", "pending", None),
    ]
    assert (steps[0]["startedAt"], steps[0]["finishedAt"][:19]) == ("2026-10-05T10:00:00+09:00", "2026-10-05T10:01:30")
    assert (steps[2]["startedAt"], steps[2]["finishedAt"]) == (None, None)


def test_a_failed_run_names_its_step_and_code_and_lists_its_files(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="failed", failed_step="judge", error_code="step_failed")
    staged(a, run_id, ("extract", "done", at(5), at(5)), ("judge", "failed", at(5), at(5)))
    files = apps.get_model("runs", "RunFileRow")._meta.managers_map["unscoped"]
    for step, name, size in (("extract", "pages.json", 20480), (None, "report.bin", 12)):
        files.create(
            company_id=a, run_id=run_id, step=step, name=name, media_type="application/json",
            storage_key=f"runs/{a}/{run_id}/{name}", size_bytes=size, sha256="0" * 64,
        )  # fmt: skip
    body = detail(client, access, run_id, a).json()
    assert (body["failedStep"], body["errorCode"], body["status"]) == ("judge", "step_failed", "failed")
    assert body["files"] == [
        {"name": "pages.json", "step": "extract", "mediaType": "application/json", "sizeBytes": 20480},
        {"name": "report.bin", "step": None, "mediaType": "application/json", "sizeBytes": 12},
    ]
    assert "storageKey" not in json_text(body) and "errorMessage" not in json_text(body)


def json_text(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False)


def test_a_missing_or_another_companys_run_is_the_same_404(client: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    access = operator_access(client)
    run_a = made(a, document(a))
    foreign = detail(client, access, run_a, b)
    missing = detail(client, access, run_a + 10_000, b)
    assert error(foreign) == (404, "RUN_NOT_FOUND")
    assert foreign.content == missing.content  # 남의 회사 실행과 없는 실행을 가르지 않는다
    assert error(detail(client, access, 2**63, a)) == (404, "RUN_NOT_FOUND")  # bigint 밖도 404(500 아님)
    assert error(client.get(f"/api/run-logs/abc?companyId={a}", **bearer(access))) == (404, "NOT_FOUND")  # 경로 없음
    assert error(detail(client, access, run_a, 9_000_000)) == (404, "COMPANY_NOT_FOUND")
    assert detail(client, access, run_a, a).status_code == 200  # 분모


def test_a_customer_gets_403_on_the_detail_before_the_body_reads_anything(
    client: Client, companies: tuple[int, int]
) -> None:
    a, _ = companies
    run_id = made(a, document(a))
    customer(a, "kim")
    access = changed_access(client, username="kim", subdomain="tenant-a")
    with CaptureQueriesContext(connection) as seen:
        response = detail(client, access, run_id, a)
    assert error(response) == (403, "FORBIDDEN")
    assert {"id", "steps", "files", "tokens"} & set(response.json()) == set()
    body_tables = ('"company"', '"run_runs"', '"run_steps"', '"run_files"', '"core_llm_call_logs"')
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in body_tables)] == []
    assert detail(Client(), operator_access(Client()), run_id, a).status_code == 200  # 분모


def test_the_detail_reads_a_fixed_number_of_queries(client: Client, companies: tuple[int, int]) -> None:
    """회사 1 + 실행 1 + 검토 가능 1 + 검토 상태 1(그린워싱 원천) + 단계 1 + 파일 1 + LLM 합 1 + 단계별 1 + 이름 1."""
    a, _ = companies
    access = operator_access(client)
    run_id = scan(a, document(a))
    three_steps(a, run_id)
    step_call(a, run_id, "judge", input_tokens=1, cost="0")
    marks = ('FROM "company"', 'FROM "run_runs"', 'FROM "run_steps"', 'FROM "run_files"', 'FROM "core_llm_call_logs"',
             'FROM "greenwash_reviews"', '"users"."kind" = ')  # fmt: skip
    with CaptureQueriesContext(connection) as seen:
        assert detail(client, access, run_id, a).status_code == 200
    found = [q["sql"] for q in seen.captured_queries if any(m in q["sql"] for m in marks)]
    found = [sql for sql in found if not ('FROM "users"' in sql and "IN (" not in sql)]  # 인증의 사용자 읽기는 뺀다
    assert len(found) == 9, found


# ── 문서 없는 실행(ND1) ──────────────────────────────────────────────


def bare_run(company_id: int, **extra: Any) -> int:
    """문서 없는 흐름의 실행(문서 칸 NULL — 지어낸 모듈 probe)."""
    return made(company_id, None, module="probe", flow_id="probe.bare@1", **extra)


def test_a_documentless_run_is_a_line_with_null_document_fields(client: Client, companies: tuple[int, int]) -> None:
    """목록 count 2 · 문서 없는 줄은 두 칸 null(LEFT JOIN — 줄이 빠지지 않는다) · q(문서 이름)로 거르면 빠진다 ·
    엑셀 두 줄, 문서 칸 빈칸 · 상세 200 두 칸 null. 분모: 문서 실행은 두 칸이 차 있다."""
    a, _ = companies
    access = operator_access(client)
    doc = document(a, "지은 보고서.pdf")
    with_document = made(a, doc, created_at=at(1))
    without = bare_run(a, created_at=at(2), status="done")
    listed = logs(client, access, f"companyId={a}").json()
    assert listed["count"] == 2
    assert [(r["id"], r["documentId"], r["documentName"]) for r in listed["results"]] == [
        (without, None, None),
        (with_document, doc, "지은 보고서.pdf"),
    ]
    assert page_ids(logs(client, access, f"companyId={a}&q=보고서")) == [with_document]
    header, bare_line, document_line = sheet_rows(export(client, access, f"companyId={a}"))
    assert (header[2], bare_line[2], document_line[2]) == ("문서", None, "지은 보고서.pdf")
    one = detail(client, access, without, a)
    assert one.status_code == 200, one.content.decode()
    assert (one.json()["documentId"], one.json()["documentName"]) == (None, None)


def test_a_documentless_line_reads_as_many_queries_as_a_document_line(
    client: Client, companies: tuple[int, int]
) -> None:
    """문서 이름은 같은 쿼리의 LEFT JOIN 이다 — 문서 없는 줄이 쿼리를 더하지 않는다."""
    a, b = companies
    access = operator_access(client)
    made(a, document(a), created_at=at(1), module="probe", flow_id="probe.one@1")  # 원천 없는 모듈 — 같은 조건
    bare_run(b, created_at=at(1))
    with CaptureQueriesContext(connection) as with_document:
        assert len(page_ids(logs(client, access, f"companyId={a}"))) == 1
    with CaptureQueriesContext(connection) as without:
        assert len(page_ids(logs(client, access, f"companyId={b}"))) == 1
    assert len(body_queries(without)) == len(body_queries(with_document))
    page = next(q for q in body_queries(without) if 'FROM "run_runs"' in q and "LIMIT" in q)
    assert 'LEFT OUTER JOIN "core_documents"' in page


# ── 결과 파일 받기(RF1) ──────────────────────────────────────────────


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1000)


def file_rows() -> Any:
    return apps.get_model("runs", "RunFileRow")._meta.managers_map["unscoped"]


def stored(storage: FakeStorage, company_id: int, run_id: int, *, step: str | None, name: str, data: bytes) -> None:
    """파일 행 하나와 가짜 저장소의 같은 키에 바이트(step None = 흐름의 출력 파일)."""
    key = f"runs/{company_id}/{run_id}/{step or 'out'}/{name}"
    storage.put(key, data)
    file_rows().create(
        company_id=company_id, run_id=run_id, step=step, name=name, media_type="application/vnd.ms-excel",
        storage_key=key, size_bytes=len(data), sha256="0" * 64,
    )  # fmt: skip


def file_get(client: Client, access: str, run_id: int, name: str, query: str) -> Any:
    return client.get(f"/api/run-logs/{run_id}/files/{name}?{query}", **bearer(access))


def downloads() -> list[tuple[Any, ...]]:
    return list(
        AuditEventRow.unscoped.filter(action="download")
        .order_by("id")
        .values_list("company_id", "actor_kind", "actor_user_id", "event", "result", "target_kind", "target_id",
                     "target_label")
    )  # fmt: skip


def test_the_operator_gets_the_output_file_bytes_and_one_audit_line(
    client: Client, companies: tuple[int, int], storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = companies
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: b)  # 작업 회사 ≠ 고른 회사
    access = operator_access(client)
    operator_id = User.unscoped.get(username="ops").pk
    run_id = made(a, document(a), status="done")
    stored(storage, a, run_id, step=None, name="report.xls", data=b"XLS-BYTES")
    response = file_get(client, access, run_id, "report.xls", f"companyId={a}")
    assert response.status_code == 200
    assert response.content == b"XLS-BYTES"
    assert response["Content-Type"] == "application/vnd.ms-excel"
    assert response["Content-Disposition"] == 'attachment; filename="report.xls"'
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Cache-Control"] == "no-store"
    assert downloads() == [
        (a, "admin", operator_id, "run_file_downloaded", "success", "run", run_id, "report.xls")
    ]  # company_id = 고른 회사(작업 회사 b 가 아니다)


@pytest.mark.parametrize("module", ["inventory", "reconcile"])
def test_a_run_of_any_module_gives_its_file_unlike_the_customer_path(
    client: Client, companies: tuple[int, int], storage: FakeStorage, monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
    assert module not in OPERATOR_RUN_MODULES
    a, _ = companies
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: a)
    access = operator_access(client)
    run_id = made(a, document(a), module=module, flow_id=f"{module}.probe@1", status="done")
    stored(storage, a, run_id, step=None, name="result.xlsx", data=b"ANY-MODULE")
    assert file_get(client, access, run_id, "result.xlsx", f"companyId={a}").content == b"ANY-MODULE"
    # 대비: 고객사 길(GET /runs/{id}/files/{name})의 운영 관리자는 OPERATOR_RUN_MODULES 밖이라 404 — 0 바뀜
    refused = client.get(f"/api/runs/{run_id}/files/result.xlsx", **bearer(access))
    assert error(refused) == (404, "NOT_FOUND")


def test_a_customer_gets_403_on_a_file_before_the_body_reads_anything(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    run_id = made(a, document(a), status="done")
    stored(storage, a, run_id, step=None, name="report.xls", data=b"XLS-BYTES")
    customer(a, "kim")
    access = changed_access(client, username="kim", subdomain="tenant-a")
    with CaptureQueriesContext(connection) as seen:
        response = file_get(client, access, run_id, "report.xls", f"companyId={a}")
    assert error(response) == (403, "FORBIDDEN")
    assert b"XLS-BYTES" not in response.content
    body_tables = ('"company"', '"run_runs"', '"run_files"', '"core_audit_events"')
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in body_tables)] == []
    assert downloads() == []
    ok = file_get(Client(), operator_access(Client()), run_id, "report.xls", f"companyId={a}")  # 분모
    assert ok.content == b"XLS-BYTES"


def test_a_missing_or_another_companys_run_is_the_same_404_on_a_file(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, b = companies
    access = operator_access(client)
    run_a = made(a, document(a), status="done")
    stored(storage, a, run_a, step=None, name="report.xls", data=b"XLS-BYTES")
    foreign = file_get(client, access, run_a, "report.xls", f"companyId={b}")
    missing = file_get(client, access, run_a + 10_000, "report.xls", f"companyId={b}")
    assert error(foreign) == (404, "RUN_NOT_FOUND")
    assert foreign.content == missing.content  # 남의 회사 실행과 없는 실행을 가르지 않는다
    assert error(file_get(client, access, 2**63, "report.xls", f"companyId={a}")) == (404, "RUN_NOT_FOUND")
    assert downloads() == []
    assert file_get(client, access, run_a, "report.xls", f"companyId={a}").content == b"XLS-BYTES"  # 분모


def test_an_unknown_name_a_step_file_or_a_missing_object_is_run_file_not_found(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="done")
    stored(storage, a, run_id, step="extract", name="pages.json", data=b"[1]")  # 단계 산출 파일
    file_rows().create(
        company_id=a,
        run_id=run_id,
        step=None,
        name="gone.xls",
        media_type="application/vnd.ms-excel",
        storage_key=f"runs/{a}/{run_id}/out/gone.xls",
        size_bytes=1,
        sha256="0" * 64,
    )  # fmt: skip — 행은 있는데 저장소에 객체가 없다
    for name in ("none.xls", "pages.json", "gone.xls"):
        assert error(file_get(client, access, run_id, name, f"companyId={a}")) == (404, "RUN_FILE_NOT_FOUND"), name
    assert downloads() == []
    # 분모: 같은 이름의 출력 파일 행이면 내준다
    stored(storage, a, run_id, step=None, name="pages.json", data=b"OUT")
    assert file_get(client, access, run_id, "pages.json", f"companyId={a}").content == b"OUT"


def test_the_store_refusals_are_the_three_503s_without_an_audit_line(
    client: Client, companies: tuple[int, int], storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="done")
    stored(storage, a, run_id, step=None, name="report.xls", data=b"X")
    storage.fail_with = StorageUnavailable("닿지 못함(시험)")
    assert error(file_get(client, access, run_id, "report.xls", f"companyId={a}")) == (503, "STORAGE_UNAVAILABLE")
    storage.fail_with = StorageDenied("거절(시험)")
    assert error(file_get(client, access, run_id, "report.xls", f"companyId={a}")) == (503, "STORAGE_DENIED")
    storage.fail_with = None
    monkeypatch.setattr(documents_services, "default_storage", lambda: None)
    assert error(file_get(client, access, run_id, "report.xls", f"companyId={a}")) == (503, "STORAGE_UNCONFIGURED")
    assert downloads() == []


def test_two_companies_without_a_company_id_is_ambiguous_on_a_file(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="done")
    stored(storage, a, run_id, step=None, name="report.xls", data=b"X")
    assert error(client.get(f"/api/run-logs/{run_id}/files/report.xls", **bearer(access))) == (
        400,
        "COMPANY_AMBIGUOUS",
    )
    assert downloads() == []


def test_a_file_reads_a_fixed_number_of_queries(
    client: Client, companies: tuple[int, int], storage: FakeStorage
) -> None:
    """회사 1 + 실행 1 + 파일 1 + 감사 쓰기 1."""
    a, _ = companies
    access = operator_access(client)
    run_id = made(a, document(a), status="done")
    stored(storage, a, run_id, step=None, name="report.xls", data=b"X")
    marks = ('FROM "company"', '"run_runs"', '"run_files"', '"core_audit_events"')
    with CaptureQueriesContext(connection) as seen:
        assert file_get(client, access, run_id, "report.xls", f"companyId={a}").status_code == 200
    found = [q["sql"] for q in seen.captured_queries if any(m in q["sql"] for m in marks)]
    assert len(found) == 4, found
