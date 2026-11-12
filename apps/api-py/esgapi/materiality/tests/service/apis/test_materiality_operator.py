# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""운영 관리자(kind admin, 회사 없음)의 중대성평가 IRO — 만들기·끝까지·결과·엑셀 둘·목록·이어 돌기(결정 MARC-ENT-419,
밴드 IR3b §3-2-4·5, 업무 층).

core/permissions.py 의 OPERATOR_RUN_MODULES 에 materiality 가 들어 runs 의 경로가 저절로 연다(runs 의 식 0줄):
    만들기    문서 없는 POST /runs {module: materiality} 201 — 행의 회사 = 작업 회사, created_by = 운영 관리자,
              감사 admin
    끝까지    실행기(모의 공급사 14 호출)로 done
    결과      GET /materiality/runs/{id}/result 200, 본문 = 고객사 사용자가 읽는 것
    엑셀 둘   GET /runs/{id}/files/{materiality-websearch.xlsx|materiality-final-report.xlsx} 200·PK
    목록      질의가 없으면 네 모듈 — 중대성평가 실행이 든다 · ?module=materiality 에도 든다
    이어 돌기  같은 회사 고객사 사용자의 report_iro 실패 실행을 resumeFromRunId 로 201·done·공급사 0,
              남의 회사 실행 id 404
★ 작업 회사는 core/auth/bearer.py 의 포트를 바꿔 끼운다(runs/tests/service/apis/test_runs_operator.py 꼴 — 진짜 고르기
  operator_work_company 는 user/tests 와 보안 층이 잰다). 운영 관리자의 access 는 core 의 토큰 함수로 낸다.
★ 공급사는 모의(tests/flows/test_runs_materiality.py 의 scripted — 실제 호출 0). 입력은 전부 지어낸 것이다.
"""

from typing import Any
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import get_resolver

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.core.models import AuditEventRow
from esgapi.materiality.flows import iro_155
from esgapi.materiality.tests.flows.support import options, script_iro
from esgapi.materiality.tests.flows.test_runs_materiality import (
    FILES,
    World,
    done_run,
    execute,
    once_failing,
    result_body,
    run_of,
    scripted,
)
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import bearer, login

pytestmark = pytest.mark.django_db

OPERATOR_ID = 9102  # 운영 관리자의 사용자 id(토큰의 sub — 인증은 사용자 행을 읽지 않는다)


@pytest.fixture
def work_company(monkeypatch: pytest.MonkeyPatch, world: World) -> list[int]:
    """작업 회사 = A(진짜 고르기는 user 의 operator_work_company). 부른 차례를 적는다."""
    asked: list[int] = []

    def chosen() -> int:
        asked.append(world.company_a)
        return world.company_a

    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", chosen)
    return asked


def operator() -> dict[str, Any]:
    claims = new_access_claims(
        user_id=str(OPERATOR_ID),
        kind="admin",
        level=99,
        company_id=None,
        company_is_active=None,
        is_initial=False,
        jti=uuid4(),
        now=now(),
    )
    return bearer(sign_access(claims, secret=app_config().session_secret))


def run_lines(company_id: int) -> list[tuple[str, int | None, str]]:
    rows = AuditEventRow.for_company(company_id).filter(action="run").order_by("id")
    return [(r.actor_kind, r.actor_user_id, r.event) for r in rows]


def operator_post(client: Client, body: dict[str, Any]) -> Any:
    return client.post("/api/runs", data=body, content_type="application/json", **operator())


def operator_run(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> int:
    """운영 관리자가 문서 없이 만들고 실행기(모의)로 끝까지 돌린 중대성평가 실행."""
    scripted(monkeypatch, world)
    given = options()
    script_iro(world.mock, given["input"])
    made = operator_post(client, {"module": "materiality", "options": given})
    assert made.status_code == 201, made.content.decode()
    run_id: int = made.json()["id"]
    execute(world, run_id)
    assert world.mock.pending == 0
    return run_id


# ── 3-2-4 만들기·결과·엑셀 둘·목록 ──


def test_an_operator_creates_a_documentless_materiality_run_in_the_work_company(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = operator_run(client, world, monkeypatch)
    run = run_of(world, run_id)
    assert (run.company_id, run.module, run.document_id, run.created_by_user_id) == (
        world.company_a,
        "materiality",
        None,
        OPERATOR_ID,
    )
    assert (run.status, run.error_code) == ("done", None)
    assert work_company[0] == world.company_a
    assert ("admin", OPERATOR_ID, "run_created") in run_lines(world.company_a)
    assert run_lines(world.company_b) == []


def test_the_operator_reads_the_same_result_and_both_workbooks_as_the_customer(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = operator_run(client, world, monkeypatch)
    mine = client.get(f"/api/materiality/runs/{run_id}/result", **operator())
    assert mine.status_code == 200, mine.content.decode()
    assert mine.json() == result_body(world, run_id)
    customer = Client()
    login(customer)
    theirs = customer.get(f"/api/materiality/runs/{run_id}/result")
    assert (theirs.status_code, theirs.json()) == (200, mine.json())  # 분모: 고객사 사용자도 같은 본문

    for name in FILES:
        workbook = client.get(f"/api/runs/{run_id}/files/{name}", **operator())
        assert workbook.status_code == 200, name
        assert workbook.content[:4] == b"PK\x03\x04", name
    got = client.get(f"/api/runs/{run_id}", **operator()).json()
    assert (got["status"], sorted(got["files"]), got["resultShapes"]) == (
        "done",
        sorted(FILES),
        ["materiality.result@2", "materiality.digest@1"],
    )


def test_the_operator_list_has_the_materiality_run_without_and_with_the_module(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = operator_run(client, world, monkeypatch)
    listed = client.get("/api/runs", **operator()).json()["results"]
    assert [(r["id"], r["module"]) for r in listed] == [(run_id, "materiality")]
    picked = client.get("/api/runs", {"module": "materiality"}, **operator()).json()["results"]
    assert [r["id"] for r in picked] == [run_id]


# ── 3-2-5 이어 돌기(⑧ 가) ──


def test_the_operator_resumes_a_customers_failed_run_of_the_work_company(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """★E: create_run(resume_from)은 앞 실행의 만든 사람을 보지 않는다 — 같은 회사 고객사 사용자의 실행을 운영
    관리자가 이어 받는다(지금 동작대로 짓는다)."""
    original = iro_155.PART2[iro_155.REPORT2]
    monkeypatch.setitem(iro_155.PART2, iro_155.REPORT2, once_failing(original))
    first = done_run(client, world, monkeypatch, options())  # 고객사 사용자(쿠키 세션)가 만든 실행
    assert (run_of(world, first).status, run_of(world, first).failed_step) == ("failed", "report_iro")
    monkeypatch.setitem(iro_155.PART2, iro_155.REPORT2, original)
    calls_before = len(world.mock.calls)

    response = operator_post(client, {"module": "materiality", "options": {}, "resumeFromRunId": first})
    assert response.status_code == 201, response.content.decode()
    resumed: int = response.json()["id"]
    execute(world, resumed)
    run = run_of(world, resumed)
    assert (run.status, run.company_id, run.created_by_user_id) == ("done", world.company_a, OPERATOR_ID)
    assert len(world.mock.calls) == calls_before  # 공급사 0
    assert run_selectors.run_results(company_id=world.company_a, run_id=resumed)[0].schema_version == (
        "materiality.result@2"
    )


def test_the_operator_cannot_resume_another_companys_run(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    other = Client()
    login(other, tenant_id="tenant-b")
    made = other.post(
        "/api/runs", data={"module": "materiality", "options": options()}, content_type="application/json"
    )
    assert made.status_code == 201, made.content.decode()
    theirs: int = made.json()["id"]
    response = operator_post(client, {"module": "materiality", "options": {}, "resumeFromRunId": theirs})
    assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND")


def test_the_operator_lists_the_work_companys_materiality_runs_like_the_customer(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """IR3c §3-2-5: GET /materiality/runs — 운영 관리자는 작업 회사의 실행 전부(고객사 사용자가 만든 것 포함)를 고객사
    사용자와 같은 본문으로 읽고, mine 은 운영 관리자 자신이 만든 것만."""
    theirs = done_run(client, world, monkeypatch, options())  # 고객사 사용자(client 로그인)가 만든 것
    mine = operator_run(client, world, monkeypatch)
    customer = Client()
    login(customer)
    seen = client.get("/api/materiality/runs", **operator())
    assert seen.status_code == 200, seen.content.decode()
    assert seen.json() == customer.get("/api/materiality/runs").json()
    assert [row["id"] for row in seen.json()["results"]] == [mine, theirs]
    assert seen.json()["results"][0]["createdBy"]["userId"] == OPERATOR_ID
    assert all(row["impactRows"] == 3 and row["pathwayRows"] == 6 for row in seen.json()["results"])
    picked = client.get("/api/materiality/runs", {"mine": "true"}, **operator()).json()
    assert [row["id"] for row in picked["results"]] == [mine]
    assert [row["id"] for row in customer.get("/api/materiality/runs", {"mine": "true"}).json()["results"]] == [theirs]
    assert work_company  # 작업 회사를 골랐다(포트를 거쳤다)
