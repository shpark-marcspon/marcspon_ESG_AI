# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""운영 관리자(kind admin, 회사 없음)의 데이터 검증 — 만들기·끝까지·결과·엑셀·목록(결정 MARC-ENT-390, 밴드 DV1e §3-2-4,
업무 층).

core/permissions.py 의 OPERATOR_RUN_MODULES 에 dataverify 가 들어 runs 의 경로가 저절로 연다(runs 의 식 0줄):
    만들기   문서 없는 POST /runs {module: dataverify} 201 — 행의 회사 = 작업 회사, created_by = 운영 관리자, 감사 admin
    끝까지   실행기(모의 공급사)로 done
    결과     GET /dataverify/runs/{id}/result 200, 본문 = 고객사 사용자가 읽는 것
    엑셀     GET /runs/{id}/files/dataverify-report.xlsx 200·PK
    목록     질의가 없으면 세 모듈 — 데이터 검증 실행이 든다
★ 작업 회사는 core/auth/bearer.py 의 포트를 회사 A 로 바꿔 끼운다(runs/tests/service/apis/test_runs_operator.py 꼴 —
  진짜 고르기 operator_work_company 는 user/tests 와 보안 층이 잰다). 운영 관리자의 access 는 core 의 토큰 함수로
  낸다(인증은 DB 를 읽지 않는다).
★ 공급사는 모의(tests/flows/test_runs_dataverify.py 의 scripted — 실제 호출 0). 입력은 전부 지어낸 것이다.
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
from esgapi.dataverify.tests.flows.support import options
from esgapi.dataverify.tests.flows.test_runs_dataverify import (
    World,
    execute,
    happy,
    result_body,
    run_of,
    scripted,
)
from tests.support.http import bearer, login

pytestmark = pytest.mark.django_db

OPERATOR_ID = 9101  # 운영 관리자의 사용자 id(토큰의 sub — 인증은 사용자 행을 읽지 않는다)


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


def operator_run(client: Client, world: World, monkeypatch: pytest.MonkeyPatch) -> int:
    """운영 관리자가 문서 없이 만들고 실행기(모의)로 끝까지 돌린 데이터 검증 실행."""
    scripted(monkeypatch, world)
    happy(world.mock)
    made = client.post(
        "/api/runs", data={"module": "dataverify", "options": options()}, content_type="application/json", **operator()
    )
    assert made.status_code == 201, made.content.decode()
    run_id: int = made.json()["id"]
    execute(world, run_id)
    assert world.mock.pending == 0
    return run_id


def test_an_operator_creates_a_documentless_dataverify_run_in_the_work_company(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = operator_run(client, world, monkeypatch)
    run = run_of(world, run_id)
    assert (run.company_id, run.module, run.document_id, run.created_by_user_id) == (
        world.company_a,
        "dataverify",
        None,
        OPERATOR_ID,
    )
    assert (run.status, run.error_code) == ("done", None)
    assert work_company[0] == world.company_a
    assert ("admin", OPERATOR_ID, "run_created") in run_lines(world.company_a)
    assert run_lines(world.company_b) == []


def test_the_operator_reads_the_same_result_and_workbook_as_the_customer(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = operator_run(client, world, monkeypatch)
    mine = client.get(f"/api/dataverify/runs/{run_id}/result", **operator())
    assert mine.status_code == 200, mine.content.decode()
    assert mine.json() == result_body(world, run_id)
    customer = Client()
    login(customer)
    theirs = customer.get(f"/api/dataverify/runs/{run_id}/result")
    assert (theirs.status_code, theirs.json()) == (200, mine.json())  # 분모: 고객사 사용자도 같은 본문

    workbook = client.get(f"/api/runs/{run_id}/files/dataverify-report.xlsx", **operator())
    assert workbook.status_code == 200
    assert workbook.content[:4] == b"PK\x03\x04"
    got = client.get(f"/api/runs/{run_id}", **operator()).json()
    assert (got["status"], got["files"], got["resultShapes"]) == (
        "done",
        ["dataverify-report.xlsx"],
        ["dataverify.result@2", "dataverify.digest@1"],
    )


def test_the_operator_list_without_a_module_has_the_dataverify_run(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = operator_run(client, world, monkeypatch)
    listed = client.get("/api/runs", **operator()).json()["results"]
    assert [(r["id"], r["module"]) for r in listed] == [(run_id, "dataverify")]
    picked = client.get("/api/runs", {"module": "dataverify"}, **operator()).json()["results"]
    assert [r["id"] for r in picked] == [run_id]


def test_the_operator_lists_the_work_company_runs_like_the_customer(
    client: Client, world: World, work_company: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """목록 GET /dataverify/runs(DV1g): 운영 관리자는 작업 회사의 실행을 고객사 사용자와 같은 본문으로 읽고, mine 은
    운영 관리자 자신(이름 행이 없는 운영 관리자 id 는 「알 수 없는 사용자」)."""
    run_id = operator_run(client, world, monkeypatch)
    customer = Client()
    login(customer)
    made = customer.post(
        "/api/runs", data={"module": "dataverify", "options": options()}, content_type="application/json"
    ).json()["id"]
    theirs = client.get("/api/dataverify/runs", **operator())
    assert theirs.status_code == 200, theirs.content.decode()
    assert [r["id"] for r in theirs.json()["results"]] == [made, run_id]
    mine = customer.get("/api/dataverify/runs")
    assert (mine.status_code, mine.json()) == (200, theirs.json())  # 분모: 고객사 사용자도 같은 본문
    rows = {r["id"]: r for r in theirs.json()["results"]}
    assert rows[run_id]["createdBy"] == {"userId": OPERATOR_ID, "name": "알 수 없는 사용자"}
    assert rows[run_id]["stages"] is not None
    own = client.get("/api/dataverify/runs", {"mine": "true"}, **operator()).json()
    assert [r["id"] for r in own["results"]] == [run_id]
    assert [r["id"] for r in customer.get("/api/dataverify/runs", {"mine": "true"}).json()["results"]] == [made]
