# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""원고작성의 경로(밴드 RP1 §3 S14 다섯 + RP2d 둘 + RP2c 목차 차이 하나, 업무 층). 진짜 DB·가짜 저장소·대본 모의
공급사(tests/flows/test_runs_drafting.py 의 world 를 그대로 쓴다 — 실제 공급사·키·네트워크 0).

    S14-1  고객사 사용자: 만들기 201(문서·목차 null) → 문서 달기 → 목차 판 1 → 같은 sha 멱등 → 다른 sha 판 2 →
           POST /runs 201 → 끝나기 전 결과 409 RUN_NOT_DONE → 실행기 → 결과 200 = 결과 행 본문
    S14-2  404: 없는 프로젝트(셋)·없는 문서·남의 회사 문서·남의 회사 프로젝트·없는 실행·다른 모듈 실행
    S14-3  422 셋: 올림 미완(VALIDATION_ERROR fields.documentId) · 글자 층 없음(DOCUMENT_NO_TEXT_LAYER, null 은 받음) ·
           목차 트리 규칙(VALIDATION_ERROR fields.nodes) — 행 0
    S14-4  운영 관리자: 작업 회사(A)로 만들기·문서·목차·실행 만들기 201 — 행의 회사 = A, created_by = 운영 관리자
    S14-6  (RP2d) 목록: 최신순·hasDocument·outlineRevision(목차 없으면 null)·createdAt +09:00·쪽 자름 · 남의 회사 0 ·
           프로젝트 응답의 createdAt·document.attachedAt 도 +09:00
    S14-7  (RP2d) 결과 docx: 끝나기 전 409 RUN_NOT_DONE → 실행기 → 200 attachment(머리 넷) · 문단 = 결과 본문으로 지은
           것 · 없는·남의 회사·다른 모듈 실행 404
    S14-8  (RP2b B8 · RP2c) 결과 경로는 drafting.bullets@3 만 찾는다 — @1·@2 행만 있는 끝난 실행(옛 꼴)은 404
    B9     (RP2c) 목차 차이: 앞 실행 그대로면 잎 다 same·문서 same → 목차를 고치고(요구 바뀜·잎 지움·잎 더함) 문서를
           바꾸면 changed·same·added·removed·document changed(손셈) · 404 한 글: 없는 프로젝트·목차 없는 프로젝트·없는
           실행·남의 회사·다른 프로젝트의 실행·끝나지 않은 실행·다른 모듈 실행 · 쿼리 수 ★ 고정
    B3     (RPS1) 프로젝트 실행 목록: 끝남(@3)·진행(running 단계)·실패 손셈 200 · 새 것 먼저·쪽·count · 없는 프로젝트·
           남의 회사 404 한 글 · 조회 인자 422 · 고객사·운영 관리자 둘 다 200 · 목록 줄의 latestRun·documentName·
           outlineId · 프로젝트 GET 의 latestRun(진짜 실행기로 끝낸 실행의 잎 셈 = 결과 본문 손셈) · 시각 +09:00
    B3q    (RPS1) 쿼리 수는 줄 수와 무관: 목록 줄 1 == 줄 20 · 실행 줄 1 == 줄 20(값 ★ 고정)
    B4     (RPS1) 끝난 실행 20 의 쪽: results_of 부름 1 · find_run·run_results 0 · 읽은 본문 바이트 합 ★
★ 작업 회사는 core/auth/bearer.py 의 포트를 바꿔 끼운다(materiality/tests/service/apis/test_materiality_operator.py 꼴).
"""

import io
import json
from typing import Any, Final
from uuid import uuid4

import docx
import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import get_resolver

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.core.models import DocumentRow
from esgapi.drafting.contracts import shapes
from esgapi.drafting.models import DraftingOutline, DraftingProject, DraftingProjectDocument
from esgapi.drafting.outputs import docx as docx_output
from esgapi.drafting.tests.flows.test_runs_drafting import (
    PDF_BYTES,
    World,
    document,
    execute,
    result_body,
    run_of,
    script,
)
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import bearer, login

pytestmark = pytest.mark.django_db

OPERATOR_ID: Final = 9103  # 운영 관리자의 사용자 id(토큰의 sub — 인증은 사용자 행을 읽지 않는다)
LEAVES: Final = (("ghg", "온실가스 배출"), ("energy", "에너지 사용"), ("safety", "안전보건"))


def outline(*leaves: tuple[str, str]) -> dict[str, Any]:
    """첫 층 「환경」 아래 잎들(지어낸 제목). 열쇠는 tests/flows/support 의 대본(ghg·energy·safety)과 같다."""
    nodes: list[dict[str, Any]] = [{"key": "env", "parentKey": None, "depth": 1, "title": "환경", "requirement": ""}]
    nodes += [
        {"key": key, "parentKey": "env", "depth": 2, "title": title, "requirement": f"{title} 요구"}
        for key, title in leaves
    ]
    return {"nodes": nodes}


def put(client: Client, url: str, body: dict[str, Any]) -> Any:
    return client.put(url, data=body, content_type="application/json")


def create(client: Client, name: str = "지어낸 원고") -> Any:
    return client.post("/api/drafting/projects", data={"year": 2025, "name": name}, content_type="application/json")


def project_url(project_id: int, tail: str = "") -> str:
    return f"/api/drafting/projects/{project_id}{tail}"


def code(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def raw_document(world: World, company: int, *, status: str, has_text: bool | None) -> int:
    key = f"companies/{company}/documents/rp1-s14-{len(world.storage.objects)}/original"
    etag = world.storage.put(key, PDF_BYTES)
    row = DocumentRow.for_company(company).create(
        company_id=company,
        uploaded_by="1",
        file_name="지어낸 보고서.pdf",
        storage_key=key,
        size_bytes=len(PDF_BYTES),
        etag=etag,
        status=status,
        has_text=has_text,
    )
    return row.pk


def is_seoul(value: str) -> bool:
    return value.endswith("+09:00")


def texts(data: bytes) -> list[str]:
    return [p.text for p in docx.Document(io.BytesIO(data)).paragraphs]


def foreign_done_run(company: int, module: str) -> int:
    """끝난 실행 하나와 결과 행(빈 본문 — 갈래만 잰다). SQL 로 심는다(S14-2b 와 같은 까닭)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, "
            "versions, purpose, status, attempts, stalled_attempts, created_by_user_id) VALUES (now(), now(), %s, "
            "NULL, %s, 'materiality.iro@155', '{}', '{}', 'service', 'done', 1, 0, 1) RETURNING id",
            [company, module],
        )
        row = cursor.fetchone()
        assert row is not None
        run_id = int(row[0])
        cursor.execute(
            "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
            "VALUES (now(), %s, %s, 0, %s, '{}')",
            [company, run_id, shapes.RESULT_SHAPE],
        )
    return run_id


def drafting_rows(company: int) -> tuple[int, int, int]:
    return (
        DraftingProject.for_company(company).count(),
        DraftingProjectDocument.for_company(company).count(),
        DraftingOutline.for_company(company).count(),
    )


# ── S14-1 ──


def test_s14_1_the_five_paths_from_a_new_project_to_its_result(client: Client, world: World) -> None:
    login(client)
    made = create(client)
    assert made.status_code == 201, made.content.decode()
    body = made.json()
    project_id = body["id"]
    assert {k: body[k] for k in ("year", "name", "document", "outline")} == {
        "year": 2025,
        "name": "지어낸 원고",
        "document": None,
        "outline": None,
    }
    assert client.get(project_url(project_id)).json() == body

    document_id = document(world, world.company_a)
    attached = put(client, project_url(project_id, "/document"), {"documentId": document_id})
    assert attached.status_code == 200, attached.content.decode()
    assert {k: attached.json()["document"][k] for k in ("documentId", "kind")} == {
        "documentId": document_id,
        "kind": "prior_report",
    }

    first = put(client, project_url(project_id, "/outline"), outline(*LEAVES[:2]))
    same = put(client, project_url(project_id, "/outline"), outline(*LEAVES[:2]))
    assert (first.status_code, same.status_code) == (200, 200), first.content.decode()
    assert first.json()["revision"] == 1 and same.json() == first.json()  # 같은 sha 면 지금 판(멱등)
    assert DraftingOutline.for_company(world.company_a).count() == 1
    second = put(client, project_url(project_id, "/outline"), outline(*LEAVES))
    assert second.status_code == 200, second.content.decode()
    assert second.json()["revision"] == 2 and second.json()["sha256"] != first.json()["sha256"]
    shown = client.get(project_url(project_id)).json()["outline"]
    assert {k: shown[k] for k in ("outlineId", "revision", "sha256")} == second.json()
    assert [node["key"] for node in shown["outline"]["nodes"]] == ["env", "ghg", "energy", "safety"]

    created = client.post(
        "/api/runs", data={"module": "drafting", "options": {"projectId": project_id}}, content_type="application/json"
    )
    assert created.status_code == 201, created.content.decode()
    run_id = created.json()["id"]
    assert code(client.get(f"/api/drafting/runs/{run_id}/result")) == (409, "RUN_NOT_DONE")
    script(world)
    execute(world, run_id)
    assert run_of(world, run_id).status == "done"
    result = client.get(f"/api/drafting/runs/{run_id}/result")
    assert result.status_code == 200, result.content.decode()
    assert result.json() == result_body(world, run_id)
    shapes.check_result(result.json())
    assert result.json()["outlineId"] == second.json()["outlineId"]


# ── S14-2 ──


def test_s14_2_missing_and_foreign_ids_are_404(client: Client, world: World) -> None:
    login(client)
    project_id = create(client).json()["id"]
    missing = project_id + 1000
    for response in (
        client.get(project_url(missing)),
        put(client, project_url(missing, "/document"), {"documentId": document(world, world.company_a)}),
        put(client, project_url(missing, "/outline"), outline(*LEAVES)),
        put(client, project_url(project_id, "/document"), {"documentId": 10**9}),  # 없는 문서
        put(client, project_url(project_id, "/document"), {"documentId": document(world, world.company_b)}),
        client.get("/api/drafting/runs/999999999/result"),
    ):
        assert code(response) == (404, "NOT_FOUND"), response.content.decode()
    assert drafting_rows(world.company_a) == (1, 0, 0)

    theirs = Client()
    login(theirs, sub="edk-user-2", tenant_id="tenant-b")
    assert code(theirs.get(project_url(project_id))) == (404, "NOT_FOUND")  # 남의 회사 프로젝트
    assert code(put(theirs, project_url(project_id, "/outline"), outline(*LEAVES))) == (404, "NOT_FOUND")
    assert drafting_rows(world.company_a) == (1, 0, 0)


def test_s14_2b_a_done_run_of_another_module_is_not_a_drafting_result(client: Client, world: World) -> None:
    """결과 경로는 module 을 본다: 같은 회사의 끝난 다른 모듈 실행(결과 행 있음)도 없는 실행이다. 행은 SQL 로 심는다
    (남의 모듈 모델을 들이지 않는다 — .importlinter no-foreign-models 가 tests 까지 문다)."""
    login(client)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, "
            "versions, purpose, status, attempts, stalled_attempts, created_by_user_id) VALUES (now(), now(), %s, "
            "NULL, 'materiality', 'materiality.iro@155', '{}', '{}', 'service', 'done', 1, 0, 1) RETURNING id",
            [world.company_a],
        )
        row = cursor.fetchone()
        assert row is not None
        run_id = int(row[0])
        cursor.execute(
            "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
            "VALUES (now(), %s, %s, 0, %s, '{}')",
            [world.company_a, run_id, shapes.RESULT_SHAPE],
        )
    assert code(client.get(f"/api/drafting/runs/{run_id}/result")) == (404, "NOT_FOUND")


# ── S14-3 ──


def test_s14_3_three_422s_write_nothing(client: Client, world: World) -> None:
    login(client)
    project_id = create(client).json()["id"]
    waiting = raw_document(world, world.company_a, status="awaiting_upload", has_text=None)
    refused = put(client, project_url(project_id, "/document"), {"documentId": waiting})
    assert code(refused) == (422, "VALIDATION_ERROR")
    assert list(refused.json()["error"]["fields"]) == ["documentId"]
    scanned = raw_document(world, world.company_a, status="uploaded", has_text=False)
    assert code(put(client, project_url(project_id, "/document"), {"documentId": scanned})) == (
        422,
        "DOCUMENT_NO_TEXT_LAYER",
    )
    jumped = outline(*LEAVES)
    jumped["nodes"][1]["depth"] = 3  # 부모 depth + 1 이 아니다
    bad = put(client, project_url(project_id, "/outline"), jumped)
    assert code(bad) == (422, "VALIDATION_ERROR")
    assert list(bad.json()["error"]["fields"]) == ["nodes"]
    assert drafting_rows(world.company_a) == (1, 0, 0)
    unknown = raw_document(world, world.company_a, status="uploaded", has_text=None)  # 분모: null(모름)은 받는다
    assert put(client, project_url(project_id, "/document"), {"documentId": unknown}).status_code == 200
    assert drafting_rows(world.company_a) == (1, 1, 0)


# ── S14-4 ──


@pytest.fixture
def work_company(monkeypatch: pytest.MonkeyPatch, world: World) -> list[int]:
    """작업 회사 = A(진짜 고르기는 user 의 operator_work_company — 보안 층 test_operator_company 가 잰다)."""
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


def test_s14_4_the_operator_drafts_in_the_work_company(world: World, work_company: list[int]) -> None:
    ops = Client(**operator())  # 모든 요청에 Authorization 머리(쿠키 0)
    made = create(ops, "운영 관리자의 원고")
    assert made.status_code == 201, made.content.decode()
    project_id = made.json()["id"]
    assert made.json()["createdByUserId"] == OPERATOR_ID
    document_id = document(world, world.company_a)
    assert put(ops, project_url(project_id, "/document"), {"documentId": document_id}).status_code == 200
    assert put(ops, project_url(project_id, "/outline"), outline(*LEAVES)).status_code == 200
    created = ops.post(
        "/api/runs", data={"module": "drafting", "options": {"projectId": project_id}}, content_type="application/json"
    )
    assert created.status_code == 201, created.content.decode()
    run = run_of(world, created.json()["id"])
    assert (run.module, run.created_by_user_id) == ("drafting", OPERATOR_ID)
    assert drafting_rows(world.company_a) == (1, 1, 1) and drafting_rows(world.company_b) == (0, 0, 0)
    assert work_company  # 포트를 탔다


# ── S14-6 ──


def test_s14_6_the_list_is_newest_first_with_document_and_outline_revision(client: Client, world: World) -> None:
    login(client)
    older = create(client, "지어낸 앞 원고").json()["id"]
    newer = create(client, "지어낸 뒤 원고").json()["id"]
    document_id = document(world, world.company_a)
    attached = put(client, project_url(older, "/document"), {"documentId": document_id})
    assert attached.status_code == 200, attached.content.decode()
    assert is_seoul(attached.json()["createdAt"]) and is_seoul(attached.json()["document"]["attachedAt"])
    assert put(client, project_url(older, "/outline"), outline(*LEAVES[:1])).status_code == 200
    assert put(client, project_url(older, "/outline"), outline(*LEAVES)).status_code == 200

    listed = client.get("/api/drafting/projects")
    assert listed.status_code == 200, listed.content.decode()
    body = listed.json()
    assert (body["count"], body["isNext"]) == (2, False)
    assert [
        {k: row[k] for k in ("id", "year", "name", "hasDocument", "outlineRevision")} for row in body["results"]
    ] == [
        {"id": newer, "year": 2025, "name": "지어낸 뒤 원고", "hasDocument": False, "outlineRevision": None},
        {"id": older, "year": 2025, "name": "지어낸 앞 원고", "hasDocument": True, "outlineRevision": 2},
    ]
    assert all(is_seoul(row["createdAt"]) for row in body["results"])
    assert body["results"][1]["createdAt"] == client.get(project_url(older)).json()["createdAt"]
    cut = client.get("/api/drafting/projects?limit=1&offset=0").json()
    assert (cut["count"], cut["isNext"], [row["id"] for row in cut["results"]]) == (2, True, [newer])

    theirs = Client()
    login(theirs, sub="edk-user-2", tenant_id="tenant-b")
    assert theirs.get("/api/drafting/projects").json() == {"count": 0, "isNext": False, "results": []}


# ── S14-7 ──


def test_s14_7_the_result_docx_of_a_done_run(client: Client, world: World) -> None:
    login(client)
    project_id = create(client).json()["id"]
    attached = put(client, project_url(project_id, "/document"), {"documentId": document(world, world.company_a)})
    assert attached.status_code == 200, attached.content.decode()
    assert put(client, project_url(project_id, "/outline"), outline(*LEAVES)).status_code == 200
    created = client.post(
        "/api/runs", data={"module": "drafting", "options": {"projectId": project_id}}, content_type="application/json"
    )
    assert created.status_code == 201, created.content.decode()
    run_id = created.json()["id"]
    url = f"/api/drafting/runs/{run_id}/result.docx"
    assert code(client.get(url)) == (409, "RUN_NOT_DONE")
    script(world)
    execute(world, run_id)

    got = client.get(url)
    assert got.status_code == 200, got.content.decode(errors="replace")
    assert (got["Content-Type"], got["Content-Disposition"], got["X-Content-Type-Options"], got["Cache-Control"]) == (
        docx_output.MEDIA_TYPE,
        f'attachment; filename="drafting-{run_id}.docx"',
        "nosniff",
        "no-store",
    )
    expected = texts(docx_output.build(result_body(world, run_id), run_id=run_id))
    assert texts(got.content) == expected
    assert expected[0] == f"원고 초안 — 실행 {run_id}" and "환경" in expected
    assert texts(client.get(url).content) == expected  # 다시 받아도 같은 문단

    missing = client.get("/api/drafting/runs/999999999/result.docx")
    assert code(missing) == (404, "NOT_FOUND")
    other_module = foreign_done_run(world.company_a, "materiality")
    assert client.get(f"/api/drafting/runs/{other_module}/result.docx").content == missing.content
    theirs = Client()
    login(theirs, sub="edk-user-2", tenant_id="tenant-b")
    hidden = theirs.get(url)
    assert (hidden.status_code, hidden.content) == (404, missing.content)


# ── S14-8 (RP2b B8 · RP2c) ──


@pytest.mark.parametrize("shape", ["drafting.bullets@1", "drafting.bullets@2"])
def test_s14_8_a_done_run_with_only_an_older_bullets_row_is_404(client: Client, world: World, shape: str) -> None:
    """@3 가 @2 를 갈음(514 3번 — RP2b 때는 @2 가 @1 을): 같은 회사의 끝난 원고작성 실행이어도 결과 행이 옛 꼴뿐이면
    없는 실행이다. 행은 SQL 로 심는다(주인 역할 — S14-2b 와 같은 까닭). @3 행은 S14-1 이 200 으로 잰다."""
    login(client)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, "
            "versions, purpose, status, attempts, stalled_attempts, created_by_user_id) VALUES (now(), now(), %s, "
            "NULL, 'drafting', 'drafting.draft@v2', '{}', '{}', 'service', 'done', 1, 0, 1) RETURNING id",
            [world.company_a],
        )
        row = cursor.fetchone()
        assert row is not None
        run_id = int(row[0])
        cursor.execute(
            "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
            "VALUES (now(), %s, %s, 0, %s, %s)",
            [world.company_a, run_id, shape, f'{{"schemaVersion": "{shape}"}}'],
        )
    assert shapes.RESULT_SHAPE == "drafting.bullets@3"
    assert code(client.get(f"/api/drafting/runs/{run_id}/result")) == (404, "NOT_FOUND")
    assert code(client.get(f"/api/drafting/runs/{run_id}/result.docx")) == (404, "NOT_FOUND")


# ── B9 (RP2c) 목차 차이 ──


def changes_url(project_id: int, run_id: int) -> str:
    return project_url(project_id, f"/outline/changes?baseRunId={run_id}")


def done_project(client: Client, world: World) -> tuple[int, int]:
    """문서·목차(LEAVES)를 단 프로젝트와 그 위의 끝난 실행 하나. (projectId, runId)."""
    project_id = create(client).json()["id"]
    attached = put(client, project_url(project_id, "/document"), {"documentId": document(world, world.company_a)})
    assert attached.status_code == 200, attached.content.decode()
    assert put(client, project_url(project_id, "/outline"), outline(*LEAVES)).status_code == 200
    made = client.post(
        "/api/runs", data={"module": "drafting", "options": {"projectId": project_id}}, content_type="application/json"
    )
    assert made.status_code == 201, made.content.decode()
    run_id: int = made.json()["id"]
    script(world)
    execute(world, run_id)
    assert run_of(world, run_id).status == "done"
    return project_id, run_id


def test_b9_changes_by_hand(client: Client, world: World) -> None:
    login(client)
    project_id, run_id = done_project(client, world)
    base_outline = run_of(world, run_id).versions["outlineId"]
    unchanged = client.get(changes_url(project_id, run_id))
    assert unchanged.status_code == 200, unchanged.content.decode()
    assert unchanged.json() == {
        "baseRunId": run_id,
        "baseOutlineId": base_outline,
        "outlineId": base_outline,
        "document": "same",
        "leaves": [{"key": key, "change": "same"} for key, _ in LEAVES],
        "removed": [],
    }

    edited = outline(LEAVES[1], LEAVES[0], ("water", "용수 사용"))  # energy·ghg 차례 바꿈·safety 지움·water 더함
    edited["nodes"][2]["requirement"] = "온실가스 배출 요구와 감축"  # ghg 요구 바뀜
    put_outline = put(client, project_url(project_id, "/outline"), edited)
    assert put_outline.status_code == 200, put_outline.content.decode()
    other = put(client, project_url(project_id, "/document"), {"documentId": document(world, world.company_a)})
    assert other.status_code == 200, other.content.decode()
    with CaptureQueriesContext(connection) as seen:
        changed = client.get(changes_url(project_id, run_id))
    assert changed.status_code == 200, changed.content.decode()
    assert changed.json() == {
        "baseRunId": run_id,
        "baseOutlineId": base_outline,
        "outlineId": put_outline.json()["outlineId"],
        "document": "changed",
        "leaves": [
            {"key": "energy", "change": "same"},  # 형제 차례만 바뀜 → same
            {"key": "ghg", "change": "changed"},
            {"key": "water", "change": "added"},
        ],
        "removed": ["safety"],
    }
    assert len(seen.captured_queries) == CHANGES_QUERIES  # ★


CHANGES_QUERIES: Final = 9
"""★ 프로젝트 1 · 지금 목차 머리 1 · 실행 1 · 목차 판 둘 × (판 1 + 마디 1) · 지금 문서 달기 1 · core 문서 1 — 잎 수와
무관."""


def test_b9_every_missing_branch_is_one_404(client: Client, world: World) -> None:
    login(client)
    project_id, run_id = done_project(client, world)
    other_project, other_run = done_project(client, world)
    bare = create(client).json()["id"]  # 목차 없음
    pending = client.post(
        "/api/runs", data={"module": "drafting", "options": {"projectId": project_id}}, content_type="application/json"
    ).json()["id"]  # 끝나지 않음
    other_module = foreign_done_run(world.company_a, "materiality")
    missing = client.get(changes_url(project_id, run_id + 10_000))
    assert code(missing) == (404, "NOT_FOUND")
    theirs = Client()
    login(theirs, sub="edk-user-2", tenant_id="tenant-b")
    for response in (
        client.get(changes_url(project_id + 10_000, run_id)),
        client.get(changes_url(bare, run_id)),
        client.get(changes_url(project_id, other_run)),
        client.get(changes_url(other_project, run_id)),
        client.get(changes_url(project_id, pending)),
        client.get(changes_url(project_id, other_module)),
        theirs.get(changes_url(project_id, run_id)),
    ):
        assert (response.status_code, response.content) == (404, missing.content)
    assert client.get(changes_url(project_id, run_id)).status_code == 200  # 분모
    assert code(client.get(project_url(project_id, "/outline/changes"))) == (422, "VALIDATION_ERROR")


# ── B3·B3q·B4 (RPS1) 프로젝트 실행 목록 ──


def runs_url(project_id: int, query: str = "") -> str:
    return project_url(project_id, f"/runs{query}")


def leaf_body(*statuses: str, rejected: bool = False) -> dict[str, Any]:
    """잎 outcome 만 손으로 고른 결과 본문(셈만 잰다 — 꼴 검사는 결과 경로 시험 몫)."""
    status: dict[str, Any] = {"status": "rejected", "code": "too_large"} if rejected else {"status": "done"}
    leaves = [{"key": f"k{i}", "outcome": {"status": s}} for i, s in enumerate(statuses)]
    return {"schemaVersion": shapes.RESULT_SHAPE, "status": status, "leaves": leaves}


def plant_run(
    company: int,
    project_id: int,
    *,
    status: str,
    minutes: int,
    outline_id: int | None = None,
    base: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    steps: tuple[tuple[str, str, int | None, int | None], ...] = (),
) -> int:
    """원고작성 실행 하나(만든 시각 = 지금 + minutes 분)와 결과·단계. SQL 로 심는다(S14-2b 와 같은 까닭)."""
    options: dict[str, Any] = {"projectId": project_id, **({} if base is None else {"base": base})}
    versions = {} if outline_id is None else {"outlineId": outline_id}
    finished = "now() + make_interval(mins => %s + 1)" if status in ("done", "failed") else "NULL::timestamptz"
    params: list[Any] = [minutes, company, json.dumps(options), json.dumps(versions), status]
    if status in ("done", "failed"):
        params.append(minutes)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, "
            "versions, purpose, status, attempts, stalled_attempts, created_by_user_id, finished_at) VALUES "
            "(now() + make_interval(mins => %s), now(), %s, NULL, 'drafting', 'drafting.draft@v2', %s::jsonb, "
            f"%s::jsonb, 'service', %s, 1, 0, 1, {finished}) RETURNING id",
            params,
        )
        row = cursor.fetchone()
        assert row is not None
        run_id = int(row[0])
        if body is not None:
            cursor.execute(
                "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
                "VALUES (now(), %s, %s, 0, %s, %s::jsonb)",
                [company, run_id, body["schemaVersion"], json.dumps(body, ensure_ascii=False)],
            )
        for position, (name, step_status, done, total) in enumerate(steps):
            cursor.execute(
                "INSERT INTO run_steps (created_at, updated_at, company_id, run_id, name, position, status, done, "
                "total) VALUES (now(), now(), %s, %s, %s, %s, %s, %s, %s)",
                [company, run_id, name, position, step_status, done, total],
            )
    return run_id


def outlined_project(client: Client, world: World, name: str = "지어낸 원고") -> tuple[int, int]:
    """문서·목차(LEAVES)를 단 프로젝트(실행 없음). (projectId, outlineId)."""
    project_id = create(client, name).json()["id"]
    attached = put(client, project_url(project_id, "/document"), {"documentId": document(world, world.company_a)})
    assert attached.status_code == 200, attached.content.decode()
    outlined = put(client, project_url(project_id, "/outline"), outline(*LEAVES))
    assert outlined.status_code == 200, outlined.content.decode()
    return project_id, outlined.json()["outlineId"]


def three_runs(project_id: int, outline_id: int, company: int) -> tuple[int, int, int]:
    """끝남(@3 — 잎 done 2·no_material 1)·진행(map 3/8)·실패. 만든 차례 = 끝남 → 실패 → 진행."""
    done = plant_run(
        company,
        project_id,
        status="done",
        minutes=1,
        outline_id=outline_id,
        body=leaf_body("done", "no_material", "done"),
    )
    failed = plant_run(
        company,
        project_id,
        status="failed",
        minutes=2,
        outline_id=outline_id,
        base={"runId": done, "rebuild": ["ghg"]},
    )
    processing = plant_run(
        company,
        project_id,
        status="processing",
        minutes=3,
        outline_id=outline_id,
        steps=(("extract", "done", None, None), ("map", "running", 3, 8), ("draft", "pending", None, None)),
    )
    return done, failed, processing


def test_b3_the_runs_of_a_project_by_hand(client: Client, world: World) -> None:
    login(client)
    project_id, outline_id = outlined_project(client, world)
    other_project, _ = outlined_project(client, world, "지어낸 다른 원고")
    done, failed, processing = three_runs(project_id, outline_id, world.company_a)
    plant_run(world.company_a, other_project, status="done", minutes=4, body=leaf_body("done"))  # 다른 프로젝트
    got = client.get(runs_url(project_id))
    assert got.status_code == 200, got.content.decode()
    body = got.json()
    assert (body["count"], body["isNext"]) == (3, False)
    rows = body["results"]
    assert [row["id"] for row in rows] == [processing, failed, done]  # 새 것 먼저
    stripped = [{k: v for k, v in row.items() if k not in ("createdAt", "finishedAt")} for row in rows]
    assert stripped == [
        {
            "id": processing,
            "status": "processing",
            "outlineId": outline_id,
            "baseRunId": None,
            "rebuild": [],
            "progress": {"step": "map", "done": 3, "total": 8},
            "rejected": None,
            "leaves": None,
        },
        {
            "id": failed,
            "status": "failed",
            "outlineId": outline_id,
            "baseRunId": done,
            "rebuild": ["ghg"],
            "progress": None,
            "rejected": None,
            "leaves": None,
        },
        {
            "id": done,
            "status": "done",
            "outlineId": outline_id,
            "baseRunId": None,
            "rebuild": [],
            "progress": None,
            "rejected": False,
            "leaves": {"total": 3, "drafted": 2, "noMaterial": 1, "failed": 0, "notRun": 0},
        },
    ]
    assert all(is_seoul(row["createdAt"]) for row in rows)
    assert rows[0]["finishedAt"] is None and is_seoul(rows[1]["finishedAt"]) and is_seoul(rows[2]["finishedAt"])
    cut = client.get(runs_url(project_id, "?limit=1&offset=1")).json()
    assert (cut["count"], cut["isNext"], [row["id"] for row in cut["results"]]) == (3, True, [failed])

    missing = client.get(runs_url(project_id + 10_000))
    assert code(missing) == (404, "NOT_FOUND")
    theirs = Client()
    login(theirs, sub="edk-user-2", tenant_id="tenant-b")
    hidden = theirs.get(runs_url(project_id))
    assert (hidden.status_code, hidden.content) == (404, missing.content)
    for query in ("?limit=0", "?limit=51", "?offset=-1"):
        assert code(client.get(runs_url(project_id, query))) == (422, "VALIDATION_ERROR"), query
    assert client.get(runs_url(project_id, "?limit=50")).status_code == 200  # 분모: 위끝 50 은 받는다

    listed = {row["id"]: row for row in client.get("/api/drafting/projects").json()["results"]}
    assert listed[project_id]["latestRun"] == rows[0]
    assert (listed[project_id]["documentName"], listed[project_id]["outlineId"]) == ("지어낸 보고서.pdf", outline_id)
    assert listed[other_project]["latestRun"]["leaves"]["drafted"] == 1
    bare = create(client, "지어낸 빈 원고").json()["id"]
    shown = client.get("/api/drafting/projects").json()["results"][0]
    assert (shown["id"], shown["latestRun"], shown["documentName"], shown["outlineId"]) == (bare, None, None, None)
    assert client.get(project_url(project_id)).json()["latestRun"] == rows[0]
    assert client.get(project_url(bare)).json()["latestRun"] is None

    # 지금 문서 = 가장 늦게 단 것 · 지금 목차 = 가장 큰 판(latestRun.outlineId 는 실행이 읽은 판 그대로)
    newer = document(world, world.company_a)
    DocumentRow.for_company(world.company_a).filter(pk=newer).update(file_name="지어낸 새 보고서.pdf")
    assert put(client, project_url(project_id, "/document"), {"documentId": newer}).status_code == 200
    revised = put(client, project_url(project_id, "/outline"), outline(*LEAVES[:1]))
    assert revised.status_code == 200, revised.content.decode()
    row = next(r for r in client.get("/api/drafting/projects").json()["results"] if r["id"] == project_id)
    assert (row["documentName"], row["outlineId"], row["outlineRevision"]) == (
        "지어낸 새 보고서.pdf",
        revised.json()["outlineId"],
        2,
    )
    assert row["latestRun"]["outlineId"] == outline_id != row["outlineId"]


def test_b3_a_real_done_run_is_the_latest_run_with_its_leaf_counts(client: Client, world: World) -> None:
    login(client)
    project_id, run_id = done_project(client, world)
    result = result_body(world, run_id)
    by_status: dict[str, int] = {}
    for leaf in result["leaves"]:
        by_status[leaf["outcome"]["status"]] = by_status.get(leaf["outcome"]["status"], 0) + 1
    latest = client.get(project_url(project_id)).json()["latestRun"]
    assert (latest["id"], latest["status"], latest["outlineId"]) == (
        run_id,
        "done",
        run_of(world, run_id).versions["outlineId"],
    )
    assert latest["rejected"] is (result["status"]["status"] == "rejected")
    assert latest["leaves"] == {
        "total": len(LEAVES),
        "drafted": by_status.get("done", 0),
        "noMaterial": by_status.get("no_material", 0),
        "failed": by_status.get("failed", 0),
        "notRun": by_status.get("not_run", 0),
    }
    assert client.get(runs_url(project_id)).json()["results"] == [latest]


def test_b3_the_operator_reads_the_runs_of_the_work_company(
    client: Client, world: World, work_company: list[int]
) -> None:
    login(client)
    project_id, outline_id = outlined_project(client, world)
    three_runs(project_id, outline_id, world.company_a)
    mine = client.get(runs_url(project_id))
    ops = Client(**operator())
    theirs = ops.get(runs_url(project_id))
    assert (mine.status_code, theirs.status_code) == (200, 200), theirs.content.decode()
    assert theirs.json() == mine.json() and mine.json()["count"] == 3
    listed = ops.get("/api/drafting/projects")
    assert listed.status_code == 200 and listed.json()["results"][0]["latestRun"] == mine.json()["results"][0]
    assert work_company  # 포트를 탔다


def queries(client: Client, url: str) -> int:
    with CaptureQueriesContext(connection) as seen:
        response = client.get(url)
    assert response.status_code == 200, response.content.decode()
    return len(seen.captured_queries)


def one_run(company: int, project_id: int, outline_id: int | None, status: str, minutes: int) -> int:
    """실행 하나 — done 이면 @3 결과, processing 이면 running 단계(셋 다 묶음 쿼리를 타게)."""
    if status == "done":
        return plant_run(
            company, project_id, status="done", minutes=minutes, outline_id=outline_id, body=leaf_body("done")
        )
    steps = (("extract", "done", None, None), ("map", "running", 1, 2))
    return plant_run(company, project_id, status=status, minutes=minutes, outline_id=outline_id, steps=steps)


@pytest.mark.parametrize("status", ["done", "processing"])
def test_b3q_queries_do_not_grow_with_rows(client: Client, world: World, status: str) -> None:
    """줄 1 == 줄 20: 줄의 상태가 같으면 쿼리 수가 같다(단계·결과는 줄 수와 무관한 묶음 하나씩). 상태가 섞이면 둘 다
    타고, 그 위가 아래 ★ 이다."""
    login(client)
    first, outline_id = outlined_project(client, world, "지어낸 원고 0")
    one_run(world.company_a, first, outline_id, status, 0)
    one_list, one_runs = queries(client, "/api/drafting/projects"), queries(client, runs_url(first))
    for i in range(1, 20):
        project_id, outline_i = outlined_project(client, world, f"지어낸 원고 {i}")
        one_run(world.company_a, project_id, outline_i, status, i)
        one_run(world.company_a, first, outline_id, status, i)
    assert len(client.get("/api/drafting/projects").json()["results"]) == 20
    assert len(client.get(runs_url(first)).json()["results"]) == 20
    assert (queries(client, "/api/drafting/projects"), queries(client, runs_url(first))) == (one_list, one_runs)
    assert (one_list, one_runs) == (LIST_QUERIES - 1, RUNS_QUERIES - 1)  # ★ 단계·결과 가운데 하나만 탄다
    project_id, outline_i = outlined_project(client, world, "지어낸 섞인 원고")
    for i, mixed in enumerate(("done", "processing", "failed", "queued")):  # 섞인 쪽(실행·목록 둘 다)
        one_run(world.company_a, project_id, outline_i, mixed, 100 + i)
        one_run(world.company_a, first, outline_id, mixed, 100 + i)
        other, outline_o = outlined_project(client, world, f"지어낸 섞인 원고 {i}")
        one_run(world.company_a, other, outline_o, mixed, 200 + i)
    assert (queries(client, "/api/drafting/projects"), queries(client, runs_url(first))) == (
        LIST_QUERIES,
        RUNS_QUERIES,
    )


LIST_QUERIES: Final = 8
"""★ (세션 인증 몫 0) project_page 2 + 지금 문서 1 + core 문서 1 + run_page 2 + 단계 1 + 결과 1 — 줄 수와 무관."""
RUNS_QUERIES: Final = 5
"""★ (세션 인증 몫 0) 프로젝트 1 + run_page 2 + 단계 1 + 결과 1 — 줄 수와 무관."""


def test_b4_a_page_of_twenty_done_runs_reads_results_once(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    login(client)
    project_id, outline_id = outlined_project(client, world)
    for i in range(20):
        plant_run(
            world.company_a,
            project_id,
            status="done",
            minutes=i,
            outline_id=outline_id,
            body=leaf_body("done", "no_material", "failed"),
        )
    calls: dict[str, int] = {"results_of": 0, "find_run": 0, "run_results": 0}
    sizes: list[int] = []
    results_of, find_run, run_results = run_selectors.results_of, run_selectors.find_run, run_selectors.run_results

    def counted_results_of(**kwargs: Any) -> Any:
        calls["results_of"] += 1
        found = results_of(**kwargs)
        sizes.extend(len(json.dumps(r.body, ensure_ascii=False).encode()) for rows in found.values() for r in rows)
        return found

    def counted_find_run(**kwargs: Any) -> Any:
        calls["find_run"] += 1
        return find_run(**kwargs)

    def counted_run_results(**kwargs: Any) -> Any:
        calls["run_results"] += 1
        return run_results(**kwargs)

    monkeypatch.setattr(run_selectors, "results_of", counted_results_of)
    monkeypatch.setattr(run_selectors, "find_run", counted_find_run)
    monkeypatch.setattr(run_selectors, "run_results", counted_run_results)
    body = client.get(runs_url(project_id)).json()
    assert len(body["results"]) == 20 and all(row["leaves"]["failed"] == 1 for row in body["results"])
    assert calls == {"results_of": 1, "find_run": 0, "run_results": 0}
    assert len(sizes) == 20
    print(f"RPS1 B4 본문 바이트 합 {sum(sizes)} (줄 20)")  # ★ 보고
