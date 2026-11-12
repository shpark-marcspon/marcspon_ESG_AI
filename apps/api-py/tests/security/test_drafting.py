"""원고작성의 경로 여덟(밴드 RP1 ③ 다섯 + RP2d 목록·docx + RP2c 차이 — /drafting)과 POST /runs {module:"drafting"} 을
앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 남의 회사 프로젝트: A 의 프로젝트 id 로 B 의 세션·Bearer → GET 프로젝트·PUT 문서·PUT 목차 404, 없는 이웃 id 와 상태·
     본문 바이트까지 같다. A 의 행 그대로. 분모: A 의 세션으로 200. (RP2d) B 의 목록은 빈 쪽·표지 글 0, 분모: A 의
     목록에 그 프로젝트.
  ⓑ 남의 회사 문서: A 의 프로젝트에 B 의 올림 끝난 문서 → 404, 문서 달기 행 0. 분모: A 의 문서는 200·행 하나.
  ⓒ 남의 회사 projectId 로 실행 만들기: B 가 A 의 projectId 로 POST /runs → 409, 없는 projectId 와 응답 바이트 같음,
     실행 행 0. 분모: A 는 같은 몸으로 201.
     (RP2c) B 가 제 프로젝트로 base.runId = A 의 실행(옵션 projectId = B 의 프로젝트·done·@3 — 회사만 다름)을 주면
     409, 없는 실행 id 와 바이트 같음, 새 실행 행 0. 분모: 같은 실행을 B 회사에 심으면 201.
  ⓓ 남의 회사 결과: A 의 끝난 원고작성 실행(주인 역할로 심음) id 로 B → GET 결과 404, 없는 id 와 바이트 같음. 다른 모듈
     (중대성평가) 실행 id 도 404. 분모: A 로 200·심은 본문 그대로. (RP2d) 결과 docx 도 같다 — B 404·없는 id 와 바이트
     같음·다른 모듈 404, 분모: A 로 200 docx 에 표지 글(결과의 글이 문단에 실림).
     (RP2c) 목차 차이: B 가 제 프로젝트로 A 의 실행(옵션 projectId·versions.outlineId = B 의 것 — 회사만 다름) id 를
     주면 404, 없는 id 와 바이트 같음. 분모: 같은 실행을 B 회사에 심으면 200.
     (RPS1 B5) 프로젝트 실행 목록·목록·프로젝트의 latestRun: A 의 실행(옵션 projectId = B 의 프로젝트 id — 회사만
     다름)은 B 의 GET …/runs·목록·프로젝트 어디에도 0(회사 조건이 유일한 막음). B 가 A 의 프로젝트 id 로 GET …/runs →
     404, 없는 id 와 바이트 같음. 분모: 같은 실행을 B 회사에 심으면 B 의 실행 목록·latestRun 에 그것.
  ⓔ 세션 없이 여덟 다 401, 행 0.
  ⓕ 운영 관리자 Bearer 는 회사 둘이라 여덟 다 400 `COMPANY_AMBIGUOUS` — drafting 표 SELECT 0(MARC-ENT-419).
  ⓖ 앱 역할은 표 넷의 행을 지우지 못하고(DELETE 42501), 프로젝트의 outline_revision·updated_at 밖 칸과 다른 셋의 칸을
     고치지 못한다(UPDATE 42501). 분모: outline_revision 은 고쳐진다.
  ⓗ 앱 역할로 PUT 목차 두 번(다른 sha) → 200·revision 1·2(권한 오류 0), 같은 sha 다시 → 그 판(쓰기 0). 겹친 PUT: 다른
     연결이 프로젝트 행을 잠그고 판 1 을 쓰는 동안 들어온 PUT 은 기다렸다가 판 2 다(행 잠금이 없으면 판 1 이 겹쳐 실패 —
     심은 파손 P14).

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다. 결과는 계약 예시
result-sample(지어낸 값)에 표지 글을 심은 것이다.
무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다. ⓗ 의 겹침은 연결 둘(주인 역할의
트랜잭션 + 앱 역할 스레드)로 만든 것이다 — gunicorn 일꾼 둘의 요청으로 잰 것이 아니다.
"""

import io
import json
import threading
import time
from pathlib import Path
from typing import Any, Final

import docx
import psycopg
import pytest
from django.db import DatabaseError, connection, connections, transaction
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.tests.resource_fakes import FakeStorage
from tests.security.conftest import count
from tests.security.test_documents import upload_as
from tests.support.http import customer_bearer, login
from tests.support.patches import plug_storage, record_enqueued

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
EXAMPLE: Final = Path(__file__).resolve().parents[2] / "esgapi/drafting/tests/data/examples/result-sample.json"
MARKER: Final = "가상표지기업 에이 원고"
"""A 의 심은 결과·프로젝트 이름에만 있는 글. B 쪽 어디에도 나오면 안 된다."""
TABLES: Final = ("drafting_projects", "drafting_project_documents", "drafting_outlines", "drafting_outline_nodes")
VIA: Final = ("session", "bearer")
DOCX: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def outline(*titles: str) -> dict[str, Any]:
    """잎 하나씩인 첫 층 마디들의 목차(지어낸 제목)."""
    return {
        "nodes": [
            {"key": f"n{i}", "parentKey": None, "depth": 1, "title": title, "requirement": ""}
            for i, title in enumerate(titles, start=1)
        ]
    }


def session_of(via: str, company_id: int, tenant: str, sub: str) -> Client:
    if via == "session":
        client = Client()
        login(client, sub=sub, tenant_id=tenant)
        return client
    access = customer_bearer(Client(), company_id=company_id, subdomain=tenant)
    return Client(headers={"Authorization": f"Bearer {access}"})


def a_client(via: str, a: int) -> Client:
    return session_of(via, a, "tenant-a", "edk-user-1")


def b_client(via: str, b: int) -> Client:
    return session_of(via, b, "tenant-b", "edk-user-2")


def create_project(client: Client, name: str = MARKER) -> int:
    made = client.post("/api/drafting/projects", data={"year": 2025, "name": name}, content_type="application/json")
    assert made.status_code == 201, made.content.decode()
    return int(made.json()["id"])


def put(client: Client, url: str, body: dict[str, Any]) -> Any:
    return client.put(url, data=body, content_type="application/json")


def project_url(project_id: int, tail: str = "") -> str:
    return f"/api/drafting/projects/{project_id}{tail}"


def result_url(run_id: int) -> str:
    return f"/api/drafting/runs/{run_id}/result"


def docx_url(run_id: int) -> str:
    return f"/api/drafting/runs/{run_id}/result.docx"


LIST_URL: Final = "/api/drafting/projects"


def changes_url(project_id: int, run_id: int) -> str:
    return f"/api/drafting/projects/{project_id}/outline/changes?baseRunId={run_id}"  # RP2c


def drafting_rows(owner: Owner) -> tuple[int, ...]:
    return tuple(count(owner, table) for table in TABLES)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage())


# ── ⓐ ──


@pytest.mark.parametrize("via", VIA)
def test_another_companys_project_is_not_found_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    a, b = companies
    mine = a_client(via, a)
    project_id = create_project(mine)
    document_id = upload_as(mine, fake, owner)
    theirs = b_client(via, b)
    their_document = upload_as(theirs, fake, owner)  # B 의 몸이 꼴을 지나게 — 문서 달기는 B 의 문서로
    before = drafting_rows(owner)
    asks = (
        ("GET", "", None),
        ("PUT", "/document", {"documentId": their_document}),
        ("PUT", "/outline", outline("가상 목차")),
    )
    for method, tail, body in asks:
        if method == "GET":
            hidden, missing = theirs.get(project_url(project_id)), theirs.get(project_url(project_id + 1000))
        else:
            assert body is not None
            hidden = put(theirs, project_url(project_id, tail), body)
            missing = put(theirs, project_url(project_id + 1000, tail), body)
        assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND"), tail
        assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content), tail
        assert MARKER not in hidden.content.decode()
    assert drafting_rows(owner) == before == (1, 0, 0, 0)
    listed = theirs.get(LIST_URL)  # RP2d: 목록은 B 의 회사 것만(빈 쪽)
    assert (listed.status_code, listed.json()) == (200, {"count": 0, "isNext": False, "results": []})
    assert MARKER not in listed.content.decode()
    assert [row["id"] for row in mine.get(LIST_URL).json()["results"]] == [project_id]  # 분모
    shown = mine.get(project_url(project_id))  # 분모: A 의 세션으로는 보인다
    assert shown.status_code == 200, shown.content.decode()
    assert (shown.json()["name"], shown.json()["document"], shown.json()["outline"]) == (MARKER, None, None)
    assert put(mine, project_url(project_id, "/document"), {"documentId": document_id}).status_code == 200
    assert put(mine, project_url(project_id, "/outline"), outline("가상 목차")).status_code == 200


# ── ⓑ ──


@pytest.mark.parametrize("via", VIA)
def test_another_companys_document_cannot_be_attached(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    a, b = companies
    mine = a_client(via, a)
    project_id = create_project(mine)
    their_document = upload_as(b_client(via, b), fake, owner)
    refused = put(mine, project_url(project_id, "/document"), {"documentId": their_document})
    missing = put(mine, project_url(project_id, "/document"), {"documentId": their_document + 1000})
    assert (refused.status_code, refused.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert refused.content == missing.content
    assert count(owner, "drafting_project_documents") == 0
    my_document = upload_as(mine, fake, owner)  # 분모: 제 회사의 올림 끝난 문서는 달린다
    attached = put(mine, project_url(project_id, "/document"), {"documentId": my_document})
    assert attached.status_code == 200, attached.content.decode()
    assert attached.json()["document"]["documentId"] == my_document
    assert owner.execute("SELECT company_id, document_id FROM drafting_project_documents").fetchall() == [
        (a, my_document)
    ]


# ── ⓒ ──


def test_a_run_on_another_companys_project_is_refused_like_a_missing_project(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = companies
    sent = record_enqueued(monkeypatch)
    mine = a_client("bearer", a)
    project_id = create_project(mine)
    document_id = upload_as(mine, fake, owner)
    assert put(mine, project_url(project_id, "/document"), {"documentId": document_id}).status_code == 200
    assert put(mine, project_url(project_id, "/outline"), outline("가상 목차")).status_code == 200
    theirs = b_client("bearer", b)
    queued = len(sent)  # 올림 확인의 풀이 일감(parse)은 앞에서 이미 실렸다

    def run(client: Client, target: int) -> Any:
        body = {"module": "drafting", "options": {"projectId": target}}
        return client.post("/api/runs", data=body, content_type="application/json")

    hidden, missing = run(theirs, project_id), run(theirs, project_id + 1000)
    assert hidden.status_code == 409, hidden.content.decode()
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    assert (count(owner, "run_runs"), len(sent)) == (0, queued)
    made = run(mine, project_id)  # 분모: A 는 같은 몸으로 만든다
    assert made.status_code == 201, made.content.decode()
    assert owner.execute("SELECT company_id, module FROM run_runs").fetchall() == [(a, "drafting")]


def owner_based_run(owner: Owner, company_id: int, project_id: int, outline_id: int) -> int:
    """(RP2c) 이어 받을 수 있는 끝난 실행 하나 — 옵션 projectId·versions.outlineId 를 준 값으로, 결과 @3(계약 예시에
    표지 글). 주인 역할로. 회사만 바꿔 심으면 회사 조건 하나만 남는다."""
    body = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    body["document"]["fileName"] = MARKER
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'drafting', 'drafting.draft@v2', %s::jsonb, %s::jsonb, 'service', 'done', "
        "1, 0, 7) RETURNING id",
        [company_id, json.dumps({"projectId": project_id}), json.dumps({"outlineId": outline_id})],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, 'drafting.bullets@3', %s::jsonb)",
        [company_id, run_id, json.dumps(body, ensure_ascii=False)],
    )
    return run_id


def b_project(theirs: Client, fake: FakeStorage, owner: Owner, b: int) -> tuple[int, int]:
    """B 의 프로젝트(문서·목차 단 것)와 그 목차 판 id — 행이 B 회사에 있는지 먼저 단언한다."""
    project_id = create_project(theirs, "가상 비 원고")
    document_id = upload_as(theirs, fake, owner)
    assert put(theirs, project_url(project_id, "/document"), {"documentId": document_id}).status_code == 200
    outlined = put(theirs, project_url(project_id, "/outline"), outline("가상 목차"))
    assert outlined.status_code == 200, outlined.content.decode()
    found = owner.execute("SELECT company_id FROM drafting_projects WHERE id = %s", [project_id]).fetchall()
    assert found == [(b,)]
    return project_id, int(outlined.json()["outlineId"])


def test_a_base_run_of_another_company_is_refused_like_a_missing_run(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = companies
    sent = record_enqueued(monkeypatch)
    theirs = b_client("bearer", b)
    project_id, outline_id = b_project(theirs, fake, owner, b)
    hidden_run = owner_based_run(owner, a, project_id, outline_id)  # 회사만 A
    assert owner.execute("SELECT company_id FROM run_runs WHERE id = %s", [hidden_run]).fetchall() == [(a,)]
    before, queued = count(owner, "run_runs"), len(sent)

    def run(target: int) -> Any:
        base: dict[str, Any] = {"runId": target, "rebuild": []}
        body = {"module": "drafting", "options": {"projectId": project_id, "base": base}}
        return theirs.post("/api/runs", data=body, content_type="application/json")

    hidden, missing = run(hidden_run), run(hidden_run + 1000)
    assert hidden.status_code == 409, hidden.content.decode()
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    assert (count(owner, "run_runs"), len(sent)) == (before, queued)  # 새 실행 행 0
    own_run = owner_based_run(owner, b, project_id, outline_id)  # 분모: 같은 실행이 B 회사면 만든다
    made = run(own_run)
    assert made.status_code == 201, made.content.decode()
    assert count(owner, "run_runs") == before + 2


# ── ⓓ ──


def owner_done_run(owner: Owner, company_id: int, *, module: str = "drafting") -> int:
    """끝난 실행 하나(문서 없음)와 그 결과. drafting 이면 계약 예시 result-sample 에 표지 글. 주인 역할로."""
    body = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert body["schemaVersion"] == "drafting.bullets@3"
    body["document"]["fileName"] = MARKER
    flow, shape = ("drafting.draft@v2", "drafting.bullets@3")
    if module != "drafting":
        flow, shape, body = ("materiality.iro@155", "materiality.result@2", {"schemaVersion": "materiality.result@2"})
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, %s, %s, '{}', '{}', 'service', 'done', 1, 0, 7) RETURNING id",
        [company_id, module, flow],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, %s, %s::jsonb)",
        [company_id, run_id, shape, json.dumps(body, ensure_ascii=False)],
    )
    return run_id


@pytest.mark.parametrize("via", VIA)
def test_another_companys_result_is_not_found_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], via: str
) -> None:
    a, b = companies
    run_id = owner_done_run(owner, a)
    other_module = owner_done_run(owner, a, module="materiality")
    theirs = b_client(via, b)
    hidden, missing = theirs.get(result_url(run_id)), theirs.get(result_url(run_id + 1000))
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    mine = a_client(via, a)
    assert mine.get(result_url(other_module)).content == missing.content  # 제 회사여도 다른 모듈 실행은 없는 실행
    shown = mine.get(result_url(run_id))
    assert shown.status_code == 200, shown.content.decode()
    assert (shown.json()["schemaVersion"], shown.json()["document"]["fileName"]) == ("drafting.bullets@3", MARKER)
    # RP2d: 결과 docx 도 같은 갈래
    hidden, missing = theirs.get(docx_url(run_id)), theirs.get(docx_url(run_id + 1000))
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert mine.get(docx_url(other_module)).content == missing.content
    made = mine.get(docx_url(run_id))
    assert (made.status_code, made["Content-Type"]) == (200, DOCX), made.content[:200]
    paragraphs = [p.text for p in docx.Document(io.BytesIO(made.content)).paragraphs]
    assert any(text.startswith("2025년 Scope 1·2") for text in paragraphs)  # 분모: A 의 결과 글이 실렸다


@pytest.mark.parametrize("via", VIA)
def test_outline_changes_against_another_companys_run_is_not_found_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    a, b = companies
    theirs = b_client(via, b)
    project_id, outline_id = b_project(theirs, fake, owner, b)
    hidden_run = owner_based_run(owner, a, project_id, outline_id)  # 회사만 A
    assert owner.execute("SELECT company_id FROM run_runs WHERE id = %s", [hidden_run]).fetchall() == [(a,)]
    hidden, missing = theirs.get(changes_url(project_id, hidden_run)), theirs.get(changes_url(project_id, 10**9))
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    own_run = owner_based_run(owner, b, project_id, outline_id)  # 분모: 같은 실행이 B 회사면 200
    shown = theirs.get(changes_url(project_id, own_run))
    assert shown.status_code == 200, shown.content.decode()
    assert (shown.json()["baseRunId"], shown.json()["leaves"]) == (own_run, [{"key": "n1", "change": "same"}])


def runs_url(project_id: int) -> str:
    return f"/api/drafting/projects/{project_id}/runs"  # RPS1


@pytest.mark.parametrize("via", VIA)
def test_another_companys_run_with_the_same_project_id_is_not_a_run_of_the_project(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage, via: str
) -> None:
    a, b = companies
    theirs = b_client(via, b)
    project_id, outline_id = b_project(theirs, fake, owner, b)
    hidden_run = owner_based_run(owner, a, project_id, outline_id)  # 회사만 A — 옵션 projectId 는 B 의 프로젝트 id
    assert owner.execute("SELECT company_id FROM run_runs WHERE id = %s", [hidden_run]).fetchall() == [(a,)]
    listed = theirs.get(runs_url(project_id))
    assert listed.status_code == 200, listed.content.decode()
    assert listed.json() == {"count": 0, "isNext": False, "results": []}
    page = theirs.get(LIST_URL).json()
    assert [(row["id"], row["latestRun"]) for row in page["results"]] == [(project_id, None)]
    assert theirs.get(project_url(project_id)).json()["latestRun"] is None
    for response in (listed, theirs.get(LIST_URL), theirs.get(project_url(project_id))):
        assert MARKER not in response.content.decode()

    mine = a_client(via, a)
    a_project = create_project(mine)
    hidden, missing = theirs.get(runs_url(a_project)), theirs.get(runs_url(10**9))
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    assert mine.get(runs_url(a_project)).status_code == 200  # 분모: A 는 제 프로젝트를 읽는다

    own_run = owner_based_run(owner, b, project_id, outline_id)  # 분모: 같은 실행이 B 회사면 B 의 실행이다
    sibling = create_project(theirs, "가상 비 다른 원고")
    owner_based_run(owner, b, sibling, outline_id)  # 같은 회사의 다른 프로젝트 실행은 이 프로젝트의 것이 아니다
    shown = theirs.get(runs_url(project_id)).json()
    assert ([row["id"] for row in shown["results"]], shown["count"]) == ([own_run], 1)
    assert shown["results"][0]["leaves"] is not None  # 결과(@3)를 읽었다
    listed_rows = {row["id"]: row for row in theirs.get(LIST_URL).json()["results"]}
    assert listed_rows[project_id]["latestRun"]["id"] == own_run
    assert theirs.get(project_url(project_id)).json()["latestRun"]["id"] == own_run


# ── ⓔ ──


def test_without_a_session_every_drafting_path_is_401(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    project_id = create_project(a_client("bearer", a))
    run_id = owner_done_run(owner, a)
    before = drafting_rows(owner)
    anonymous = Client()
    responses = (
        anonymous.post("/api/drafting/projects", data={"year": 2025, "name": "x"}, content_type="application/json"),
        anonymous.get(project_url(project_id)),
        put(anonymous, project_url(project_id, "/document"), {"documentId": 1}),
        put(anonymous, project_url(project_id, "/outline"), outline("가상 목차")),
        anonymous.get(result_url(run_id)),
        anonymous.get(LIST_URL),  # RP2d
        anonymous.get(docx_url(run_id)),  # RP2d
        anonymous.get(changes_url(project_id, run_id)),  # RP2c
    )
    assert len(responses) == 8
    for response in responses:
        assert response.status_code == 401
        assert MARKER not in response.content.decode()
    assert drafting_rows(owner) == before == (1, 0, 0, 0)


# ── ⓕ ──


def test_an_operator_bearer_with_two_companies_is_400_ambiguous_without_reading_drafting(
    owner: Owner, companies: tuple[int, int]
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    a, _ = companies
    project_id = create_project(a_client("bearer", a))
    run_id = owner_done_run(owner, a)
    created = create_operator(username="ops", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    before = drafting_rows(owner)
    with CaptureQueriesContext(connection) as seen:
        responses = (
            operator.post("/api/drafting/projects", data={"year": 2025, "name": "x"}, content_type="application/json"),
            operator.get(project_url(project_id)),
            put(operator, project_url(project_id, "/document"), {"documentId": 1}),
            put(operator, project_url(project_id, "/outline"), outline("가상 목차")),
            operator.get(result_url(run_id)),
            operator.get(LIST_URL),  # RP2d
            operator.get(docx_url(run_id)),  # RP2d
            operator.get(changes_url(project_id, run_id)),  # RP2c
        )
    assert len(responses) == 8
    for response in responses:
        assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
        assert MARKER not in response.content.decode()
    work_tables = tuple(f'"{t}"' for t in (*TABLES, "run_runs", "run_results"))
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in work_tables)] == []
    assert drafting_rows(owner) == before == (1, 0, 0, 0)


# ── ⓖ ──


def denied(statement: str) -> tuple[str | None, str]:
    """앱 역할로 문 하나를 보내고 (SQLSTATE, DB 의 원문 첫 줄). 된 것이면 (None, "")."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement)
    except DatabaseError as error:
        return getattr(error.__cause__, "sqlstate", None), str(error.__cause__).splitlines()[0]
    return None, ""


def test_the_app_role_cannot_delete_or_rewrite_drafting_rows(
    owner: Owner, companies: tuple[int, int], fake: FakeStorage
) -> None:
    a, _ = companies
    mine = a_client("bearer", a)
    project_id = create_project(mine)
    document_id = upload_as(mine, fake, owner)
    assert put(mine, project_url(project_id, "/document"), {"documentId": document_id}).status_code == 200
    assert put(mine, project_url(project_id, "/outline"), outline("가상 목차")).status_code == 200
    rows = drafting_rows(owner)
    assert rows == (1, 1, 1, 1)  # 분모: 표 넷에 행이 있다
    for table in TABLES:
        assert denied(f"DELETE FROM {table}") == ("42501", f"permission denied for table {table}"), table
    rewrites = (
        ("drafting_projects", "name = 'x'"),
        ("drafting_projects", "year = 2024"),
        ("drafting_project_documents", "document_id = 1"),
        ("drafting_outlines", "sha256 = repeat('0', 64)"),
        ("drafting_outline_nodes", "title = 'x'"),
    )
    for table, assignment in rewrites:
        assert denied(f"UPDATE {table} SET {assignment}") == ("42501", f"permission denied for table {table}"), table
    assert drafting_rows(owner) == rows
    # 분모: 판 번호 칸(과 updated_at)은 고쳐진다 — 목차 넣기가 쓰는 칸 둘
    assert denied(f"UPDATE drafting_projects SET outline_revision = 5, updated_at = now() WHERE id = {project_id}") == (
        None,
        "",
    )
    assert owner.execute("SELECT outline_revision, name FROM drafting_projects").fetchall() == [(5, MARKER)]


# ── ⓗ ──


def test_two_outline_puts_with_different_sha_make_revision_two(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    mine = a_client("bearer", a)
    project_id = create_project(mine)
    first = put(mine, project_url(project_id, "/outline"), outline("가상 목차 하나"))
    second = put(mine, project_url(project_id, "/outline"), outline("가상 목차 하나", "가상 목차 둘"))
    again = put(mine, project_url(project_id, "/outline"), outline("가상 목차 하나", "가상 목차 둘"))
    assert (first.status_code, second.status_code, again.status_code) == (200, 200, 200), second.content.decode()
    assert (first.json()["revision"], second.json()["revision"]) == (1, 2)
    assert first.json()["sha256"] != second.json()["sha256"]
    assert again.json() == second.json()  # 같은 sha 는 지금 판(쓰기 0)
    assert owner.execute("SELECT revision, node_count FROM drafting_outlines ORDER BY revision").fetchall() == [
        (1, 1),
        (2, 2),
    ]
    assert owner.execute("SELECT outline_revision FROM drafting_projects").fetchall() == [(2,)]
    shown = mine.get(project_url(project_id)).json()["outline"]
    assert (shown["revision"], shown["outlineId"]) == (2, second.json()["outlineId"])


def test_an_outline_put_waits_for_another_writer_of_the_project_and_takes_the_next_revision(
    owner: Owner, companies: tuple[int, int], test_database: str
) -> None:
    """다른 연결(주인 역할의 트랜잭션)이 프로젝트 행을 잠그고 판 1 을 쓰는 동안 앱 역할 PUT 이 들어온다. 그 PUT 은
    잠금에서 기다렸다가(pg_stat_activity 의 Lock 기다림으로 확인) 커밋된 판 1 을 읽고 판 2 를 쓴다. 행 잠금
    (select_for_update)이 없으면 PUT 은 잠기지 않은 판 0 을 읽고 판 1 을 다시 써 unique 에 걸린다(P14)."""
    a, _ = companies
    access = customer_bearer(Client(), company_id=a, subdomain="tenant-a")
    project_id = create_project(Client(headers={"Authorization": f"Bearer {access}"}))
    outcome: list[Any] = []

    def put_in_thread() -> None:
        try:
            client = Client(headers={"Authorization": f"Bearer {access}"})
            outcome.append(put(client, project_url(project_id, "/outline"), outline("가상 목차 겹침")))
        except BaseException as error:  # 스레드 밖에서 단언한다
            outcome.append(error)
        finally:
            connections.close_all()

    with psycopg.connect(test_database) as other:  # autocommit 아님 — with 끝에 커밋
        other.execute("SELECT id FROM drafting_projects WHERE id = %s FOR UPDATE", [project_id])
        other.execute(
            "UPDATE drafting_projects SET outline_revision = 1, updated_at = now() WHERE id = %s", [project_id]
        )
        other.execute(
            "INSERT INTO drafting_outlines (created_at, updated_at, company_id, project_id, revision, sha256, "
            "node_count, created_by_user_id) VALUES (now(), now(), %s, %s, 1, repeat('a', 64), 1, 7)",
            [a, project_id],
        )
        worker = threading.Thread(target=put_in_thread)
        worker.start()
        deadline = time.monotonic() + 10
        waiting = 0
        while time.monotonic() < deadline and worker.is_alive():
            row = owner.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock'"
            ).fetchone()
            waiting = int(row[0]) if row else 0
            if waiting:
                break
            time.sleep(0.05)
        assert waiting == 1, outcome  # 분모: PUT 이 다른 쓰는 이의 잠금에 닿아 기다린다
    worker.join(timeout=10)
    assert len(outcome) == 1 and not isinstance(outcome[0], BaseException), outcome
    response = outcome[0]
    assert response.status_code == 200, response.content.decode()
    assert response.json()["revision"] == 2
    assert owner.execute("SELECT revision FROM drafting_outlines ORDER BY revision").fetchall() == [(1,), (2,)]
    assert owner.execute("SELECT outline_revision FROM drafting_projects").fetchall() == [(2,)]
