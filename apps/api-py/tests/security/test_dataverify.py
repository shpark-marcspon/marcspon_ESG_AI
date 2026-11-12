"""데이터 검증의 결과 경로 GET /dataverify/runs/{run_id}/result(밴드 DV1e §3-4-2)를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 남의 회사 실행의 결과: A 의 끝난 데이터 검증 실행(주인 역할로 심음 — 문서 없음) id 로 B 의 세션·Bearer → GET 결과
     404, 없는 이웃 id 와 상태·본문 바이트까지 같다. 분모: A 의 세션으로 200·심은 본문 그대로.
  ⓑ 세션 없이 401.
  ⓒ 운영 관리자 Bearer 는 회사 둘이라 400 `COMPANY_AMBIGUOUS` — 실행·결과 표 SELECT 0(MARC-ENT-390 — 회사 하나면 통과는
     test_operator_company ⑬).

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다. 결과는 계약 예시
result-sample(지어낸 값)에 표지 글을 심은 것이다.
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
EXAMPLE: Final = Path(__file__).resolve().parents[2] / "esgapi/dataverify/tests/data/examples/result-sample.json"
MARKER: Final = "Secret Marker Of Company A"
"""A 의 심은 결과에만 있는 글. B 쪽 어디에도 나오면 안 된다."""
OPTIONS: Final[dict[str, Any]] = {"input": {"schemaVersion": "dataverify.input@1", "company": {}, "data": {}}}
"""행의 옵션 칸(경로는 읽지 않는다 — 꼴만 지은 것)."""


def owner_done_dataverify(owner: Owner, company_id: int) -> int:
    """끝난 데이터 검증 실행 하나(문서 없음)와 그 결과(계약 예시 result-sample 에 표지 글). 주인 역할로."""
    body = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert body["schemaVersion"] == "dataverify.result@2"
    body["review"]["report"] = f"{MARKER} — 가상 검토 리포트"
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'dataverify', 'dataverify.colab@156', %s::jsonb, '{}', 'service', 'done', "
        "1, 0, 7) RETURNING id",
        [company_id, json.dumps(OPTIONS)],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, 'dataverify.result@2', %s::jsonb)",
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
    return f"/api/dataverify/runs/{run_id}/result"


# ── ⓐ ──


@pytest.mark.parametrize("via", VIA)
def test_another_companys_result_is_not_found_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], via: str
) -> None:
    a, b = companies
    run_id = owner_done_dataverify(owner, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2")
    hidden = theirs.get(result_url(run_id))
    missing = theirs.get(result_url(run_id + 1000))
    assert (hidden.status_code, hidden.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert (hidden.status_code, hidden.content) == (missing.status_code, missing.content)
    assert MARKER not in hidden.content.decode()
    mine = session_of(via, a, "tenant-a", "edk-user-1")
    shown = mine.get(result_url(run_id))
    assert shown.status_code == 200, shown.content.decode()
    assert shown.json()["review"]["report"].startswith(MARKER)  # 분모: 심은 본문 그대로
    assert shown.json()["schemaVersion"] == "dataverify.result@2"


# ── ⓑ ──


def test_without_a_session_the_result_is_401(owner: Owner, companies: tuple[int, int]) -> None:
    run_id = owner_done_dataverify(owner, companies[0])
    response = Client().get(result_url(run_id))
    assert response.status_code == 401
    assert MARKER not in response.content.decode()


# ── ⓒ ──


def test_an_operator_bearer_with_two_companies_is_400_ambiguous_without_reading_runs(
    owner: Owner, companies: tuple[int, int]
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    run_id = owner_done_dataverify(owner, companies[0])
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


# ── 실행 목록 GET /dataverify/runs(DV1g §3-4-2) ──
# ⓐ B 의 목록 바이트에 A 의 지어낸 기업명·출처 이름 글자 0(분모: A 의 목록에는 있음) ⓑ 세션 없이 401
# ⓒ 운영 관리자 Bearer 회사 둘 → 400 COMPANY_AMBIGUOUS(실행·단계·결과 표 SELECT 0)
# ⓓ mine=true 는 같은 회사 다른 사용자의 실행 0(분모: mine 없이는 보임).

LIST_URL: Final = "/api/dataverify/runs"
LIST_COMPANY: Final = "가상표지기업 에이"
LIST_SOURCE: Final = "가상-표지-에이.json"
"""A 의 심은 실행 옵션에만 있는 글(기업명·출처 이름). B 쪽 목록 어디에도 나오면 안 된다."""
DIGEST: Final[dict[str, Any]] = {
    "schemaVersion": "dataverify.digest@1",
    "stages": {k: {"status": "done", "partial": False} for k in ("plan", "review", "insight")},
    "checks": {"ok": 1, "fail": 0, "notComputed": 0, "naValues": 0, "toolErrors": 0},
}


def owner_listed_dataverify(owner: Owner, company_id: int, *, created_by: int = 987_654) -> int:
    """목록에 나올 끝난 데이터 검증 실행 하나(옵션에 표지 기업명·출처 이름, 결과 둘 — result@2 자리·digest@1).
    주인 역할로."""
    given: dict[str, Any] = {
        "input": {
            "schemaVersion": "dataverify.input@1",
            "company": {"name": LIST_COMPANY, "sasbIndustry": "가상", "materialTopics": [], "reportingYear": "2025"},
            "data": {"환경": []},
        },
        "source": {"kind": "file", "name": LIST_SOURCE},
    }
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'dataverify', 'dataverify.colab@156', %s::jsonb, '{}', 'service', 'done', "
        "1, 0, %s) RETURNING id",
        [company_id, json.dumps(given, ensure_ascii=False), created_by],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    for position, body in enumerate(({"schemaVersion": "dataverify.result@2", "review": MARKER}, DIGEST)):
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
    run_id = owner_listed_dataverify(owner, a)
    theirs = session_of(via, b, "tenant-b", "edk-user-2").get(LIST_URL)
    assert theirs.status_code == 200, theirs.content.decode()
    assert (theirs.json()["count"], theirs.json()["results"]) == (0, [])
    for word in (LIST_COMPANY, LIST_SOURCE, MARKER):
        assert word not in text_of(theirs) and word.encode() not in theirs.content
    mine = session_of(via, a, "tenant-a", "edk-user-1").get(LIST_URL)
    assert mine.status_code == 200, mine.content.decode()
    assert [r["id"] for r in mine.json()["results"]] == [run_id]  # 분모: A 의 목록에는 있다
    assert LIST_COMPANY in text_of(mine) and LIST_SOURCE in text_of(mine)
    assert MARKER not in text_of(mine)  # 결과 본문은 목록에 실리지 않는다


def test_without_a_session_the_list_is_401(owner: Owner, companies: tuple[int, int]) -> None:
    owner_listed_dataverify(owner, companies[0])
    response = Client().get(LIST_URL)
    assert response.status_code == 401
    assert LIST_COMPANY not in response.content.decode()


def test_an_operator_bearer_with_two_companies_lists_nothing_400_ambiguous(
    owner: Owner, companies: tuple[int, int]
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    owner_listed_dataverify(owner, companies[0])
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
    run_id = owner_listed_dataverify(owner, a)  # 같은 회사의 다른 사람(created_by 987654)이 만든 실행
    client = session_of(via, a, "tenant-a", "edk-user-1")
    own = client.get(LIST_URL, {"mine": "true"})
    assert own.status_code == 200, own.content.decode()
    assert (own.json()["count"], own.json()["results"]) == (0, [])
    every = client.get(LIST_URL)
    assert [r["id"] for r in every.json()["results"]] == [run_id]  # 분모: mine 없이는 보인다


# ── EDK 인벤토리 엑셀 둘(POST /dataverify/edk/read · GET /dataverify/edk/template — 밴드 DVX1) ──
# 상태 없는 읽기·공용 양식이다: 세션 없이 401(본문에 칸 값 0) · 운영 관리자 Bearer 는 회사 둘이어도 200(회사를
# 고르지 않는다 — 테넌트 행을 읽지 않는다. 결과 경로가 400 COMPANY_AMBIGUOUS 인 같은 주체가 분모) · 실행·결과·문서·감사
# 표에 SELECT 0 · 앱 역할로 본 행 수 그대로 · 고객사 Bearer·쿠키 세션도 같은 답.

EDK_READ: Final = "/api/dataverify/edk/read"
EDK_TEMPLATE: Final = "/api/dataverify/edk/template"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
EDK_SECRET: Final = "가상기밀항목 이"
"""지어낸 칸 값 — 401 본문에 나오면 안 된다."""
RUN_TABLES: Final = ('"run_runs"', '"run_steps"', '"run_results"', '"core_documents"', '"core_audit_events"')


def edk_book() -> bytes:
    from esgapi.dataverify.tests.tools import edk_xlsx_support as s

    return s.book([s.row(1, "환경", EDK_SECRET, [1, 2, 3]), s.row(2, "가상사회", "가상", [1, 2, 3])])


def post_edk(client: Client) -> Any:
    return client.generic("POST", EDK_READ, edk_book(), content_type=XLSX)


def owner_counts(owner: Owner) -> tuple[int, ...]:
    tables = ("run_runs", "run_steps", "run_results", "core_documents", "core_audit_events")
    found: list[int] = []
    for table in tables:
        row = owner.execute(f"SELECT count(*) FROM {table}").fetchone()  # 이름은 위 글자
        assert row is not None
        found.append(int(row[0]))
    return tuple(found)


def operator_with_two_companies(owner: Owner, companies: tuple[int, int], username: str) -> tuple[Client, int]:
    """운영 관리자 Bearer(회사 둘 — 작업 회사를 못 고른다)와 A 의 끝난 실행 하나(결과 경로 400 의 분모)."""
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    run_id = owner_done_dataverify(owner, companies[0])
    created = create_operator(username=username, name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login", data={"username": username, "password": "Blue-Harbor-7310"}, content_type="application/json"
    )
    assert logged.status_code == 200, logged.content.decode()
    return Client(headers={"Authorization": f"Bearer {logged.json()['access']}"}), run_id


def test_the_edk_read_is_401_without_a_session_and_an_operator_reads_without_touching_runs(
    owner: Owner, companies: tuple[int, int]
) -> None:
    operator, run_id = operator_with_two_companies(owner, companies, "ops-edk-read")
    assert operator.get(result_url(run_id)).json()["error"]["code"] == "COMPANY_AMBIGUOUS"  # 분모: 회사가 둘이다
    before = owner_counts(owner)
    assert before[0] >= 1  # 분모: 심은 실행이 있다 — 빈 표를 견준 것이 아니다
    anonymous = post_edk(Client())
    assert anonymous.status_code == 401
    assert EDK_SECRET not in anonymous.content.decode()
    with CaptureQueriesContext(connection) as seen:
        response = post_edk(operator)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert (body["ok"], body["itemCount"], body["skipped"]) == (True, 1, {"themes": 1, "items": 1})
    assert "가상사회" not in response.content.decode()
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in RUN_TABLES)] == []
    assert owner_counts(owner) == before
    customer = session_of("bearer", companies[0], "tenant-a", "edk-user-1")  # 분모: 고객사 사용자도 같은 답
    assert post_edk(customer).json() == body


def test_the_edk_template_is_401_without_a_session_and_an_operator_downloads_without_touching_runs(
    owner: Owner, companies: tuple[int, int]
) -> None:
    operator, run_id = operator_with_two_companies(owner, companies, "ops-edk-template")
    assert operator.get(result_url(run_id)).json()["error"]["code"] == "COMPANY_AMBIGUOUS"  # 분모: 회사가 둘이다
    before = owner_counts(owner)
    assert before[0] >= 1
    assert Client().get(EDK_TEMPLATE, {"year": 2025}).status_code == 401
    with CaptureQueriesContext(connection) as seen:
        response = operator.get(EDK_TEMPLATE, {"year": 2025})
    assert (response.status_code, response["Content-Type"], response["X-Content-Type-Options"]) == (
        200,
        XLSX,
        "nosniff",
    )
    assert [q["sql"] for q in seen.captured_queries if any(t in q["sql"] for t in RUN_TABLES)] == []
    assert owner_counts(owner) == before
    customer = session_of("session", companies[0], "tenant-a", "edk-user-1")  # 분모: 고객사 쿠키 세션도 같은 바이트
    assert customer.get(EDK_TEMPLATE, {"year": 2025}).content == response.content
