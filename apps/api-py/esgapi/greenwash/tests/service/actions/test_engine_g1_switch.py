"""2차 엔진(greenwash.engine@G1)이 전역에 달린 뒤의 1차 길(밴드 GE1b ③ — T19 목록 몫 · T25 끔 · permits 74 조건 1~3).

    T25  스위치 기본 꺼짐(이 파일은 world 를 쓰지 않는다 — 켬 0): flowId G1 POST → 400 INVALID_OPTIONS · 행 0 · flowId
         없는 POST → 201 E0(스위치 무관) · DEFAULTS E0
    T19  1차 목록 GET /greenwash/checks: E0 실행 + G1 실행(같은 문서·G1 만 있는 문서·끝남·끝나지 않음)을 둔 응답 = G1 을
         넣기 전 응답(바이트) · 쿼리 수 같음 · 결과 묶음 읽기에 G1 실행 id 0
    74-1 1차 길에 G1 실행 id: 끝난 실행 → 결과·검토 GET·PUT·재판단·엑셀 404, 끝나지 않은 실행 → 결과·검토·재판단 409
         RUN_NOT_DONE · 엑셀 404(흐름을 먼저 본다) — 모두 쓰기 0(검토·표시·감사·실행 행)
★ 실행·결과 행은 seed(apps.get_model)로 심는다(runs.models import 0). 결과 본문은 계약 예시(result-normal ·
  result2/result2-normal). 문서·숫자는 지어낸 것이다.
"""

import json
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.flows.registry import REGISTRY
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.models import GreenwashReviewMarkRow, GreenwashReviewRow
from esgapi.greenwash.tests.service import seed
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

OPTIONS: dict[str, Any] = {"parts": {"ceo": [1], "company": [2], "climate": [3, 4]}}
NORMAL = seed.example("result-normal")
NORMAL2 = seed.example("result2/result2-normal")
PDF = b"%PDF-1.4 synthetic g1 switch"


def run_count(company: int) -> int:
    return run_selectors.run_page(
        company_id=company, module=None, status=None, document_id=None, limit=100, offset=0
    ).count


def uploaded(company: int, storage: FakeStorage) -> int:
    """POST /runs 가 받는 올린 문서(저장소에 바이트가 있음)."""
    document_id = seed.document(company)
    row = DocumentRow.for_company(company).get(pk=document_id)
    row.etag = storage.put(row.storage_key, PDF)
    row.size_bytes = len(PDF)
    row.save(update_fields=["etag", "size_bytes"])
    return document_id


# ── T25 끔(기본) ──


def test_a_g1_run_is_refused_while_the_switch_is_off_and_e0_is_untouched(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _b = companies
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    login(client)
    document_id = uploaded(a, storage)
    assert REGISTRY.default_of("greenwash").id == colab.FLOW_ID
    before = run_count(a)
    refused = client.post(
        "/api/runs",
        data={"module": "greenwash", "flowId": E.FLOW_ID, "documentId": document_id, "options": OPTIONS},
        content_type="application/json",
    )
    assert refused.status_code == 400, refused.content.decode()
    assert refused.json()["error"]["code"] == "INVALID_OPTIONS"
    assert "그린워싱 2차 엔진 실행은 아직 열려 있지 않아요" in refused.json()["error"]["message"]
    assert run_count(a) == before  # 행 0
    made = client.post(
        "/api/runs",
        data={"module": "greenwash", "documentId": document_id, "options": OPTIONS},
        content_type="application/json",
    )
    assert made.status_code == 201, made.content.decode()
    run = run_selectors.find_run(company_id=a, run_id=made.json()["id"])
    assert run is not None and run.flow_id == colab.FLOW_ID
    assert run_count(a) == before + 1


# ── T19 1차 목록 ──


def checks(client: Client) -> str:
    got = client.get("/api/greenwash/checks")
    assert got.status_code == 200, got.content.decode()
    return got.content.decode()


def counted(client: Client) -> int:
    with CaptureQueriesContext(connection) as captured:
        checks(client)
    return len(captured.captured_queries)


def test_g1_runs_leave_the_first_engine_list_byte_for_byte(
    client: Client, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _b = companies
    login(client)
    shared = seed.document(a)
    only_g1 = seed.document(a, name="가상-2차만.pdf")
    e0 = seed.run(a, result=NORMAL, document_id=shared)
    seed.run(a, status="queued", document_id=shared)
    before, before_queries = checks(client), counted(client)
    assert json.loads(before)["runs"] and len(json.loads(before)["documents"]) == 1  # 분모: E0 줄·문서 줄
    g1 = [
        seed.run(a, result=NORMAL2, document_id=shared, flow_id=E.FLOW_ID),
        seed.run(a, result=NORMAL2, document_id=only_g1, flow_id=E.FLOW_ID),
        seed.run(a, status="processing", document_id=only_g1, flow_id=E.FLOW_ID),
    ]
    read: list[int] = []
    real = run_selectors.results_of

    def spy(**kwargs: Any) -> Any:
        read.extend(kwargs["run_ids"])
        return real(**kwargs)

    monkeypatch.setattr(run_selectors, "results_of", spy)
    assert checks(client) == before
    assert set(read) == {e0}  # 결과 본문 묶음 읽기에 G1 0
    assert counted(client) == before_queries
    assert all(run_selectors.find_run(company_id=a, run_id=r) is not None for r in g1)  # 분모: G1 행이 있다


# ── 74-1 1차 길에 G1 실행 id ──


def writes(company: int) -> tuple[int, int, int, int]:
    return (
        GreenwashReviewRow.for_company(company).count(),
        GreenwashReviewMarkRow.for_company(company).count(),
        AuditEventRow.for_company(company).count(),
        run_count(company),
    )


def first_engine_paths(client: Client, run_id: int) -> dict[str, tuple[int, str]]:
    calls = {
        "result": client.get(f"/api/greenwash/runs/{run_id}/result"),
        "review": client.get(f"/api/greenwash/runs/{run_id}/review"),
        "review_put": client.put(
            f"/api/greenwash/runs/{run_id}/review",
            data={"marks": [{"itemIndex": 0, "decision": "adopted", "excludeReason": None}]},
            content_type="application/json",
        ),
        "rejudge": client.post(f"/api/greenwash/runs/{run_id}/items/0/rejudge"),
        "report": client.get(f"/api/greenwash/runs/{run_id}/report"),
    }
    return {name: (r.status_code, r.json()["error"]["code"]) for name, r in calls.items()}


def test_first_engine_paths_treat_a_done_g1_run_as_missing(client: Client, companies: tuple[int, int]) -> None:
    a, _b = companies
    login(client)
    run_id = seed.run(a, result=NORMAL2, flow_id=E.FLOW_ID)
    before = writes(a)
    assert first_engine_paths(client, run_id) == {
        "result": (404, "NOT_FOUND"),
        "review": (404, "NOT_FOUND"),
        "review_put": (404, "NOT_FOUND"),
        "rejudge": (404, "NOT_FOUND"),
        "report": (404, "NOT_FOUND"),
    }
    assert writes(a) == before


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_first_engine_paths_on_an_unfinished_g1_run(client: Client, companies: tuple[int, int], status: str) -> None:
    a, _b = companies
    login(client)
    run_id = seed.run(a, status=status, flow_id=E.FLOW_ID)
    before = writes(a)
    assert first_engine_paths(client, run_id) == {
        "result": (409, "RUN_NOT_DONE"),
        "review": (409, "RUN_NOT_DONE"),
        "review_put": (409, "RUN_NOT_DONE"),
        "rejudge": (409, "RUN_NOT_DONE"),  # 재판단은 끝남을 흐름보다 먼저 본다(검토와 같은 _done_run — critic R3)
        "report": (404, "NOT_FOUND"),
    }
    assert writes(a) == before
