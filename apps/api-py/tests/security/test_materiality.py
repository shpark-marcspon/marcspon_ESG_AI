"""중대성평가 IRO 의 결과 경로 GET /materiality/runs/{run_id}/result(밴드 IR3b §3-4-2)를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 남의 회사 실행의 결과: A 의 끝난 중대성평가 실행(주인 역할로 심음 — 문서 없음) id 로 B 의 세션·Bearer → GET 결과
     404, 없는 이웃 id 와 상태·본문 바이트까지 같다. 분모: A 의 세션으로 200·심은 본문 그대로.
  ⓑ 세션 없이 401.
  ⓒ 운영 관리자 Bearer 는 회사 둘이라 400 `COMPANY_AMBIGUOUS` — 실행·결과 표 SELECT 0(MARC-ENT-419 — 회사 하나면 통과는
     test_operator_company ⑮).

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다. 결과는 계약 예시
result2-sample(지어낸 값)에 표지 글을 심은 것이다.
무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다.
"""

import json
from pathlib import Path
from typing import Any, Final

import psycopg
import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from tests.support.http import customer_bearer, login

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
EXAMPLE: Final = Path(__file__).resolve().parents[2] / "esgapi/materiality/tests/data/examples/result2-sample.json"
MARKER: Final = "가상표지기업 에이 IRO"
"""A 의 심은 결과에만 있는 글. B 쪽 어디에도 나오면 안 된다."""
OPTIONS: Final[dict[str, Any]] = {"input": {"schemaVersion": "materiality.input@1"}}
"""행의 옵션 칸(경로는 읽지 않는다 — 꼴만 지은 것)."""


def owner_done_materiality(owner: Owner, company_id: int) -> int:
    """끝난 중대성평가 IRO 실행 하나(문서 없음)와 그 결과(계약 예시 result2-sample 에 표지 글). 주인 역할로."""
    body = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert body["schemaVersion"] == "materiality.result@2"
    body["company"]["name"] = MARKER
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'materiality', 'materiality.iro@155', %s::jsonb, '{}', 'service', 'done', "
        "1, 0, 7) RETURNING id",
        [company_id, json.dumps(OPTIONS)],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, 'materiality.result@2', %s::jsonb)",
        [company_id, run_id, json.dumps(body, ensure_ascii=False)],
    )
    return run_id


VIA: Final = ("session", "bearer")


def session_of(via: str, company_id: int, tenant: str, sub: str) -> Client:
    if via == "session":
        client = Client()
        login(client, sub=sub, tenant_id=tenant)
        return client
    access = customer_bearer(Client(), company_id=company_id, subdomain=tenant)
    return Client(headers={"Authorization": f"Bearer {access}"})


def result_url(run_id: int) -> str:
    return f"/api/materiality/runs/{run_id}/result"


# ── ⓐ ──


@pytest.mark.parametrize("via", VIA)
def test_another_companys_result_is_not_found_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], via: str
) -> None:
    a, b = companies
    run_id = owner_done_materiality(owner, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    hidden = theirs.get(result_url(run_id))
    missing = theirs.get(result_url(run_id + 1000))
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    shown = mine.get(result_url(run_id))
    assert shown.status_code == 200, shown.content.decode()
    assert shown.json()["company"]["name"] == MARKER  # 분모: 심은 본문 그대로
    assert shown.json()["schemaVersion"] == "materiality.result@2"


# ── ⓑ ──


def test_without_a_session_the_result_is_401(owner: Owner, companies: tuple[int, int]) -> None:
    run_id = owner_done_materiality(owner, companies[0])
    response = Client().get(result_url(run_id))
    assert response.status_code == 401
    assert MARKER not in response.content.decode()


# ── ⓒ ──


def test_an_operator_bearer_with_two_companies_is_400_ambiguous_without_reading_runs(
    owner: Owner, companies: tuple[int, int]
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    run_id = owner_done_materiality(owner, companies[0])
    created = create_operator(username="ops", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    with CaptureQueriesContext(connection) as seen:
        response = operator.get(result_url(run_id))
    assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
    assert MARKER not in response.content.decode()
    run_tables = ('"run_runs"', '"run_results"')
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in run_tables)] == []


# ── 실행 목록 GET /materiality/runs(IR3c §3-4-2) ──
# ⓐ B 의 목록 바이트에 A 의 지어낸 기업명·산업명 글자 0(분모: A 의 목록에는 있음) ⓑ 세션 없이 401
# ⓒ 운영 관리자 Bearer 회사 둘 → 400 COMPANY_AMBIGUOUS(실행·단계·결과 표 SELECT 0)
# ⓓ mine=true 는 같은 회사 다른 사용자의 실행 0(분모: mine 없이는 보임).

LIST_URL: Final = "/api/materiality/runs"
LIST_COMPANY: Final = "가상표지기업 에이 목록"
LIST_INDUSTRY: Final = "가상표지 산업 에이"
"""A 의 심은 실행 옵션에만 있는 글(기업명·산업명). B 쪽 목록 어디에도 나오면 안 된다."""
LIST_DIGEST: Final[dict[str, Any]] = {"schemaVersion": "materiality.digest@1", "impactRows": 2, "pathwayRows": 1}


def owner_listed_materiality(owner: Owner, company_id: int, *, created_by: int = 987_654) -> int:
    """목록에 나올 끝난 중대성평가 IRO 실행 하나(옵션에 표지 기업명·산업명, 결과 둘 — 표지 result@2·digest@1).
    주인 역할로."""
    given: dict[str, Any] = {
        "input": {
            "schemaVersion": "materiality.input@1",
            "company": {"name": LIST_COMPANY},
            "industries": [{"standard": "SASB", "industryName": LIST_INDUSTRY, "description": "가상 설명"}],
            "topics": [{"topic": "가상토픽 하나", "description": "가상 설명"}],
            "dateRange": "2025-01-01~오늘까지",
            "latestEventMode": True,
        }
    }
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'materiality', 'materiality.iro@155', %s::jsonb, '{}', 'service', 'done', "
        "1, 0, %s) RETURNING id",
        [company_id, json.dumps(given, ensure_ascii=False), created_by],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    for position, body in enumerate(({"schemaVersion": "materiality.result@2", "company": MARKER}, LIST_DIGEST)):
        owner.execute(
            "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
            "VALUES (now(), %s, %s, %s, %s, %s::jsonb)",
            [company_id, run_id, position, body["schemaVersion"], json.dumps(body, ensure_ascii=False)],
        )
    return run_id


def text_of(response: Any) -> str:
    return json.dumps(response.json(), ensure_ascii=False)


@pytest.mark.parametrize("via", VIA)
def test_another_companys_list_carries_none_of_its_runs(owner: Owner, companies: tuple[int, int], via: str) -> None:
    a, b = companies
    run_id = owner_listed_materiality(owner, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2").get(LIST_URL)
    assert theirs.status_code == 200, theirs.content.decode()
    assert (theirs.json()["count"], theirs.json()["results"]) == (0, [])
    for word in (LIST_COMPANY, LIST_INDUSTRY, MARKER):
        assert word not in text_of(theirs) and word.encode() not in theirs.content
    mine = session_of(via, a, "tenant-a", "edk-user-1").get(LIST_URL)
    assert mine.status_code == 200, mine.content.decode()
    assert [r["id"] for r in mine.json()["results"]] == [run_id]  # 분모: A 의 목록에는 있다
    assert LIST_COMPANY in text_of(mine) and LIST_INDUSTRY in text_of(mine)
    assert (mine.json()["results"][0]["impactRows"], mine.json()["results"][0]["pathwayRows"]) == (2, 1)
    assert MARKER not in text_of(mine)  # 결과 본문은 목록에 실리지 않는다


def test_without_a_session_the_list_is_401(owner: Owner, companies: tuple[int, int]) -> None:
    owner_listed_materiality(owner, companies[0])
    response = Client().get(LIST_URL)
    assert response.status_code == 401
    assert LIST_COMPANY not in response.content.decode()


def test_an_operator_bearer_with_two_companies_lists_nothing_400_ambiguous(
    owner: Owner, companies: tuple[int, int]
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    owner_listed_materiality(owner, companies[0])
    created = create_operator(username="ops", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    with CaptureQueriesContext(connection) as seen:
        response = operator.get(LIST_URL)
    assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
    assert LIST_COMPANY not in text_of(response)
    run_tables = ('"run_runs"', '"run_steps"', '"run_results"')
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in run_tables)] == []


@pytest.mark.parametrize("via", VIA)
def test_mine_hides_another_users_run_of_the_same_company(owner: Owner, companies: tuple[int, int], via: str) -> None:
    a, _ = companies
    run_id = owner_listed_materiality(owner, a)  # 같은 회사의 다른 사람(created_by 987654)이 만든 실행
    client = session_of(via, a, "tenant-a", "edk-user-1")
    own = client.get(LIST_URL, {"mine": "true"})
    assert own.status_code == 200, own.content.decode()
    assert (own.json()["count"], own.json()["results"]) == (0, [])
    every = client.get(LIST_URL)
    assert [r["id"] for r in every.json()["results"]] == [run_id]  # 분모: mine 없이는 보인다


# ── 가치사슬 엑셀 읽기(POST /materiality/value-chain/read — 밴드 IRW2) ──
# 상태 없는 읽기다: 세션 없이 401 · 운영 관리자 Bearer 는 회사 둘이어도 200(회사를 고르지 않는다 — 테넌트 행을 읽지
# 않는다) · 두 경우 다 실행·결과 표에 닿지 않고 앱 역할로 본 행 수가 그대로.

VALUE_CHAIN_URL: Final = "/api/materiality/value-chain/read"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
VALUE_CHAIN_SECRET: Final = "가상기밀부문 이"
"""지어낸 칸 값 — 401 본문에 나오면 안 된다."""


def value_chain_book() -> bytes:
    from esgapi.materiality.tests.tools import value_chain_support

    return value_chain_support.table([(VALUE_CHAIN_SECRET, "", "업스트림", "가상협력사", "자재 조달")])


def post_value_chain(client: Client) -> Any:
    return client.generic("POST", VALUE_CHAIN_URL, value_chain_book(), content_type=XLSX)


def owner_counts(owner: Owner) -> tuple[int, ...]:
    tables = ("run_runs", "run_steps", "run_results", "core_documents", "core_audit_events")
    found: list[int] = []
    for table in tables:
        row = owner.execute(f"SELECT count(*) FROM {table}").fetchone()  # 이름은 위 글자
        assert row is not None
        found.append(int(row[0]))
    return tuple(found)


def test_without_a_session_the_value_chain_read_is_401(owner: Owner, companies: tuple[int, int]) -> None:
    before = owner_counts(owner)
    response = post_value_chain(Client())
    assert response.status_code == 401
    assert VALUE_CHAIN_SECRET not in response.content.decode()
    assert owner_counts(owner) == before


def test_an_operator_bearer_with_two_companies_reads_the_value_chain_without_touching_runs(
    owner: Owner, companies: tuple[int, int]
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    created = create_operator(username="ops-vc", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops-vc", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    before = owner_counts(owner)
    with CaptureQueriesContext(connection) as seen:
        response = post_value_chain(operator)
    assert response.status_code == 200, response.content.decode()
    assert (response.json()["ok"], response.json()["rowCount"]) == (True, 1)
    run_tables = ('"run_runs"', '"run_steps"', '"run_results"', '"core_documents"')
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in run_tables)] == []
    assert owner_counts(owner) == before
    customer = session_of("bearer", companies[0], "tenant-a", "edk-user-1")  # 분모: 고객사 사용자도 같은 답
    assert post_value_chain(customer).json() == response.json()


# ── 결과 고침 GET·POST /materiality/runs/{run_id}/result/edits(IRS3 ② — 6d: 분모 + 양성 대조 + 404 바이트 같음) ──
# ⓐ B 의 세션·Bearer 로 A 실행의 고침 읽기·저장 404(없는 이웃 id 와 상태·본문 바이트 같음, 고침 표 행 0) — 분모: A 로는
#    GET 200·POST 200(고친 값이 A 의 결과 GET 에 보임) ⓑ 세션 없이 401(쓰기 0) ⓒ 운영 관리자 Bearer 회사 둘 → 400
#    COMPANY_AMBIGUOUS(실행·결과·고침 표 SELECT 0, 쓰기 0).

EDIT_POINTER: Final = "/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition"
EDIT_SECRET: Final = "가상표지 고친 정의 에이"


def edits_url(run_id: int) -> str:
    return f"/api/materiality/runs/{run_id}/result/edits"


def edit_body(value: str = EDIT_SECRET, base: int = 0) -> dict[str, Any]:
    return {"baseRevision": base, "changes": [{"pointer": EDIT_POINTER, "value": value}]}


def edit_counts(owner: Owner) -> tuple[int, int]:
    heads = owner.execute("SELECT count(*) FROM materiality_result_edit_heads").fetchone()
    edits = owner.execute("SELECT count(*) FROM materiality_result_edits").fetchone()
    assert heads is not None and edits is not None
    return int(heads[0]), int(edits[0])


def send_edit(client: Client, method: str, run_id: int) -> Any:
    if method == "GET":
        return client.get(edits_url(run_id))
    return client.post(edits_url(run_id), data=edit_body(), content_type="application/json")


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("via", VIA)
def test_another_companys_edits_are_not_found_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], via: str, method: str
) -> None:
    a, b = companies
    run_id = owner_done_materiality(owner, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    hidden = send_edit(theirs, method, run_id)
    missing = send_edit(theirs, method, run_id + 1000)
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    assert edit_counts(owner) == (0, 0)  # B 의 저장은 A 의 실행에 머리·고침 0
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    shown = send_edit(mine, method, run_id)  # 분모(양성 대조): A 로는 2xx
    assert shown.status_code == 200, shown.content.decode()
    assert shown.json()["schemaVersion"] == "materiality.result-edits@1"
    if method == "POST":
        assert edit_counts(owner) == (1, 1)
        result = mine.get(result_url(run_id)).json()
        assert result["part2"]["topics"][0]["subtopics"][0]["impact"]["rows"][0]["impactDefinition"] == EDIT_SECRET
        assert EDIT_SECRET not in theirs.get(result_url(run_id)).content.decode()  # B 쪽은 여전히 404


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_without_a_session_edits_are_401(owner: Owner, companies: tuple[int, int], method: str) -> None:
    run_id = owner_done_materiality(owner, companies[0])
    response = send_edit(Client(), method, run_id)
    assert response.status_code == 401
    assert MARKER not in response.content.decode()
    assert edit_counts(owner) == (0, 0)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_an_operator_bearer_with_two_companies_is_400_on_edits_without_reading_runs(
    owner: Owner, companies: tuple[int, int], method: str
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    run_id = owner_done_materiality(owner, companies[0])
    created = create_operator(username="ops-ed", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops-ed", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    with CaptureQueriesContext(connection) as seen:
        response = send_edit(operator, method, run_id)
    assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
    assert MARKER not in response.content.decode()
    tables = ('"run_runs"', '"run_results"', '"materiality_result_edit_heads"', '"materiality_result_edits"')
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in tables)] == []
    assert edit_counts(owner) == (0, 0)


# ── 고친 판 최종 엑셀 GET /materiality/runs/{run_id}/report(IRS3 ③ — 6d: 분모 + 양성 대조 + 404 바이트 같음) ──
# ⓐ B 로 A 실행의 엑셀 404(없는 이웃 id 와 바이트 같음, 감사 download 0) — 분모: A 로는 200 xlsx·감사 한 줄
# ⓑ 세션 없이 401 ⓒ 운영 관리자 Bearer 회사 둘 → 400 COMPANY_AMBIGUOUS(실행·결과·고침 표 SELECT 0, 감사 0).


def report_url(run_id: int) -> str:
    return f"/api/materiality/runs/{run_id}/report"


def download_rows(owner: Owner) -> int:
    row = owner.execute("SELECT count(*) FROM core_audit_events WHERE action = 'download'").fetchone()
    assert row is not None
    return int(row[0])


@pytest.mark.parametrize("via", VIA)
def test_another_companys_report_is_not_found_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], via: str
) -> None:
    a, b = companies
    run_id = owner_done_materiality(owner, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    hidden = theirs.get(report_url(run_id))
    missing = theirs.get(report_url(run_id + 1000))
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER.encode() not in hidden.content
    assert download_rows(owner) == 0
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    shown = mine.get(report_url(run_id))  # 분모(양성 대조): A 로는 xlsx 와 감사 한 줄
    assert shown.status_code == 200, shown.content.decode(errors="replace")
    assert shown["Content-Type"] == XLSX
    assert download_rows(owner) == 1


def test_without_a_session_the_report_is_401(owner: Owner, companies: tuple[int, int]) -> None:
    run_id = owner_done_materiality(owner, companies[0])
    response = Client().get(report_url(run_id))
    assert response.status_code == 401
    assert MARKER.encode() not in response.content
    assert download_rows(owner) == 0


def test_an_operator_bearer_with_two_companies_is_400_on_the_report_without_reading_runs(
    owner: Owner, companies: tuple[int, int]
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    run_id = owner_done_materiality(owner, companies[0])
    created = create_operator(username="ops-rp", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": "ops-rp", "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    with CaptureQueriesContext(connection) as seen:
        response = operator.get(report_url(run_id))
    assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
    tables = ('"run_runs"', '"run_results"', '"materiality_result_edit_heads"', '"materiality_result_edits"')
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in tables)] == []
    assert download_rows(owner) == 0
