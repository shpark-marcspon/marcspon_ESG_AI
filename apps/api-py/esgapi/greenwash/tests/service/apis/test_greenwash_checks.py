# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""목록 줄 GET /greenwash/checks 의 몸(밴드 G1b §3-2-6). 업무 층: 진짜 DB, 세션은 EDK 교환(login — 회사 A 의 고객사
사용자). 실행(끝남·실패·도는 중·dry-run·다른 모듈·남의 회사)과 문서 둘 → 꼴 strict 통과, 그린워싱 실행·그 문서만,
levelCounts·review 요약, 이름(못 풀면 대체 글), 쿼리 수(실행 수와 무관한 상수 k — G1b-2b 묶음 읽기).

★ 실행·결과·단계 행은 seed(apps.get_model)로 심는다 — runs.models 를 import 하지 않는다(계약 나).
"""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.models import DocumentRow
from esgapi.greenwash.contracts.checks_shapes import CHECKS_SHAPES
from esgapi.greenwash.tests.service import seed
from tests.support.http import login

pytestmark = pytest.mark.django_db

NORMAL = seed.example("result-normal")  # items 넷, 쪽 8, High 1·Mid 2·Low 1
MANY = seed.example("result-many")  # items 36, 쪽 14
DRY = seed.example("result-dry-run")
URL = "/api/greenwash/checks"
UNKNOWN = "알 수 없는 사용자"
UPLOADED = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
SEOUL = ZoneInfo("Asia/Seoul")


def me(company_id: int) -> Any:
    return apps.get_model("user", "User").for_company(company_id).get(username="edk-user-1")


def checks(client: Client) -> dict[str, Any]:
    response = client.get(URL)
    assert response.status_code == 200, response.content.decode()
    body: dict[str, Any] = response.json()
    CHECKS_SHAPES["greenwash.checks@1"].validate_python(body, strict=True)
    return body


def put(client: Client, run_id: int, body: dict[str, Any]) -> None:
    response = client.put(f"/api/greenwash/runs/{run_id}/review", data=body, content_type="application/json")
    assert response.status_code == 200, response.content.decode()


def test_an_empty_company_has_no_rows(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    a = companies[0]
    body = checks(client)
    assert body == {
        "schemaVersion": "greenwash.checks@1",
        "currentUserId": me(a).pk,
        "companyName": apps.get_model("organization", "Company").for_company(a).get().name,
        "documents": [],
        "runs": [],
        "truncated": False,
    }


def test_the_rows_carry_the_greenwash_runs_and_their_documents(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    a, b = companies
    user = me(a)
    mine = seed.document(a, name="가상-보고서-2025.pdf", uploaded_by=str(user.pk))
    DocumentRow.for_company(a).filter(pk=mine).update(uploaded_at=UPLOADED)
    theirs = seed.document(a, name="가상-보고서-2026.pdf", uploaded_by="987654")  # 못 푸는 사람
    parts = {"parts": {"ceo": [1, 2], "company": [2, 3], "climate": []}}
    confirmed = seed.run(a, result=NORMAL, document_id=mine, created_by=user.pk, options=parts)
    seed.step(a, confirmed, "extract", 0, "done")
    seed.step(a, confirmed, "judge", 1, "done", 8, 8)
    one_page = {"parts": {"ceo": [5], "company": [], "climate": []}}
    failed = seed.run(
        a, status="failed", document_id=theirs, options=one_page, error_code="no_text_layer", failed_step="extract"
    )
    seed.step(a, failed, "extract", 0, "failed")
    running = seed.run(a, status="processing", document_id=mine, options=parts)
    seed.step(a, running, "judge", 0, "running", 1, 3)
    dry = seed.run(a, result=DRY, document_id=theirs)
    reviewing = seed.run(a, result=MANY, document_id=theirs)
    other_module = seed.run(a, module="inventory", document_id=mine)  # 다른 모듈 — 실리지 않는다
    other_company = seed.run(b, result=NORMAL)  # 남의 회사 — 실리지 않는다
    put(client, confirmed, {"state": "confirmed", "marks": []})
    put(client, reviewing, {"marks": [{"itemIndex": 3, "decision": "excluded", "excludeReason": "사유"}]})

    body = checks(client)
    runs = {r["runId"]: r for r in body["runs"]}
    assert set(runs) == {confirmed, failed, running, dry, reviewing}
    assert other_module not in runs and other_company not in runs
    assert runs[confirmed] == {
        "runId": confirmed,
        "documentId": mine,
        "createdAt": runs[confirmed]["createdAt"],
        "finishedAt": None,  # seed 는 끝난 때를 적지 않는다(아래 끝난 때 시험이 값을 잰다)
        "createdByUserId": user.pk,
        "status": "done",
        "errorCode": None,
        "failedPageCount": 1,  # result-normal 의 candidateStats.failedPages 하나
        "steps": [
            {"step": "extract", "status": "done", "done": None, "total": None},
            {"step": "judge", "status": "done", "done": 8, "total": 8},
        ],
        "checkedPages": 3,
        "levelCounts": {"High": 1, "Mid": 2, "Low": 1},
        "review": {
            "state": "confirmed",
            "reviewed": 4,
            "total": 4,
            "confirmedAt": runs[confirmed]["review"]["confirmedAt"],
            "confirmedBy": {"id": user.pk, "name": user.name},
        },
    }
    assert runs[confirmed]["createdAt"].endswith("+09:00")
    assert runs[confirmed]["review"]["confirmedAt"].endswith("+09:00")
    got = runs[failed]
    assert (got["status"], got["checkedPages"], got["levelCounts"], got["review"]) == ("failed", 1, None, None)
    assert got["errorCode"] == "no_text_layer"  # failedStep 은 싣지 않는다(G1e)
    assert (runs[running]["errorCode"], runs[dry]["errorCode"], runs[reviewing]["errorCode"]) == (None, None, None)
    assert runs[running]["steps"] == [{"step": "judge", "status": "running", "done": 1, "total": 3}]
    assert (runs[running]["levelCounts"], runs[running]["review"]) == (None, None)
    assert (runs[dry]["levelCounts"], runs[dry]["review"]) == (None, None)  # dry-run: 등급 수·검토 없음
    assert runs[reviewing]["review"] == {
        "state": "in_review",
        "reviewed": 1,
        "total": 36,
        "confirmedAt": None,
        "confirmedBy": None,
    }
    documents = {d["documentId"]: d for d in body["documents"]}
    assert documents == {
        mine: {
            "documentId": mine,
            "fileName": "가상-보고서-2025.pdf",
            "reportYear": None,
            "previousDocumentId": None,
            "pageCount": 8,
            "uploadedAt": "2026-10-19T21:00:00+09:00",
            "uploadedBy": {"userId": user.pk, "name": user.name},
        },
        theirs: {
            "documentId": theirs,
            "fileName": "가상-보고서-2026.pdf",
            "reportYear": None,
            "previousDocumentId": None,
            "pageCount": 14,  # 새 실행(result-many)의 쪽 수
            "uploadedAt": None,  # 올림 확인 전
            "uploadedBy": {"userId": 987654, "name": UNKNOWN},
        },
    }


def test_a_document_without_a_done_run_has_no_page_count(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    a = companies[0]
    document = seed.document(a, uploaded_by="not-a-number")
    seed.run(a, status="queued", document_id=document)
    (row,) = checks(client)["documents"]
    assert (row["pageCount"], row["uploadedBy"]) == (None, {"userId": 0, "name": UNKNOWN})


def test_the_error_code_is_the_run_records_code_only_when_failed(client: Client, companies: tuple[int, int]) -> None:
    """errorCode = failed 실행의 error_code 그대로(글자), 그 밖 null — 남은 값이 있어도(상태 가드, 밴드 G1e)."""
    login(client)
    a = companies[0]
    no_text = seed.run(a, status="failed", error_code="no_text_layer", failed_step="extract")
    step_error = seed.run(a, status="failed", error_code="step_error", failed_step="judge")
    done = seed.run(a, result=NORMAL)
    stale = seed.run(a, status="processing", error_code="step_error", failed_step="judge")  # 억지로 심은 남은 값
    queued = seed.run(a, status="queued")
    runs = {r["runId"]: r["errorCode"] for r in checks(client)["runs"]}
    assert runs == {no_text: "no_text_layer", step_error: "step_error", done: None, stale: None, queued: None}


ENDED = datetime(2026, 10, 20, 15, 30, 5, 123456, tzinfo=UTC)  # 한국 시각 다음 날 00:30:05 — 자정 넘김


def test_the_finished_at_is_the_run_records_end_in_seoul_time(client: Client, companies: tuple[int, int]) -> None:
    """finishedAt(GCB1 — checks@1 runs[].finishedAt) = Run.finished_at 을 +09:00 글자로 그대로. 끝나지 않은 실행
    (queued·processing)은 null, failed·dry-run 도 끝났으면 값."""
    login(client)
    a = companies[0]
    done = seed.run(a, result=NORMAL, finished_at=ENDED)
    failed = seed.run(a, status="failed", error_code="step_error", failed_step="judge", finished_at=ENDED)
    dry = seed.run(a, result=DRY, finished_at=ENDED)
    queued = seed.run(a, status="queued")
    processing = seed.run(a, status="processing")
    runs = {r["runId"]: r["finishedAt"] for r in checks(client)["runs"]}
    assert runs == {
        done: "2026-10-21T00:30:05.123456+09:00",
        failed: "2026-10-21T00:30:05.123456+09:00",
        dry: "2026-10-21T00:30:05.123456+09:00",
        queued: None,
        processing: None,
    }
    stored = apps.get_model("runs", "RunRow").for_company(a).get(pk=done).finished_at
    assert stored == ENDED and runs[done] == stored.astimezone(SEOUL).isoformat()  # 실행 기록 값 그대로


FIXED_QUERIES = 9
"""actions/checks.py 머리말의 상수 k(실행 1개 이상 — 실행 수와 무관): 회사 이름 1 · 실행 쪽 2(줄·수) · 검토 2 · 단계 1 ·
결과 1 · 문서 1 · 이름 1."""


def queries(client: Client) -> int:
    with CaptureQueriesContext(connection) as captured:
        checks(client)
    return len(captured.captured_queries)


def test_the_query_count_is_a_constant_k_whatever_the_run_count(client: Client, companies: tuple[int, int]) -> None:
    """실행 1개와 5개(끝난 넷 — 각자 문서 · 실패 하나)에서 같은 k(G1b-2b — 단계·결과·문서는 묶음 읽기 하나씩)."""
    login(client)
    a = companies[0]
    assert queries(client) == 3  # 빈 회사(실행 0): 회사 이름 1 · 실행 쪽 2 — 묶음·검토·이름 읽기는 쿼리 0
    seed.run(a, result=NORMAL)
    one = queries(client)
    for _ in range(3):
        seed.run(a, result=NORMAL)
    seed.run(a, status="failed")
    five = queries(client)
    assert one == five == FIXED_QUERIES, (one, five)
    print(f"목록 줄 쿼리: 실행 1 = {one}, 실행 5 = {five}")


def test_another_companys_session_sees_none_of_mine(client: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    seed.run(a, result=NORMAL)
    login(client, sub="edk-user-2", tenant_id="tenant-b")
    body = checks(client)
    assert (body["documents"], body["runs"]) == ([], [])
