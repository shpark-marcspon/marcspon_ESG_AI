"""감사 기록의 표(core_audit_events — AU1a)를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 앱 역할은 고치거나 지우지 못한다: UPDATE·DELETE·TRUNCATE 가 permission denied(42501), 행은 그대로
  ⓑ 앱 역할은 덧붙일 수 있다(회사 줄·회사 없는 줄 둘 다 — 제품의 record_event 로), 주인 연결이 센다(커밋됐다)
  ⓒ CHECK 가 앱 코드를 지나지 않는 길(주인 역할의 INSERT)에서도 모르는 행동·큰 detail·회사 없는 고객사 줄을 막는다
     (detail 크기는 1024 바이트가 들어가고 1025 가 막히는 짝까지)
  ⓓ 기록 지점(AU1a ②): HTTP 로그인 실패의 줄이 커밋된다(앱 역할 연결의 요청 뒤 주인 연결이 센다)
  ⓔ 비밀 0: 로그인 실패·모르는 아이디·성공·만들기·초기화·바꾸기·refresh·로그아웃의 한 세션 뒤 감사 표 전부를
     row_to_json 으로 떠서 비밀번호·해시·넣은 모르는 아이디·access·refresh·jti·family 가 0번(양성 대조: 만든 사용자의
     아이디는 나온다)
  ⓕ 회사 A 의 올림 줄은 company_id = A 이고 B 로 열면 0(분모: A 로 1)
  ⓖ 운영 관리자의 로그인 줄은 회사 칸이 NULL
  ⓗ 조회(AU1a ③ GET /audit-logs): 고객사 사용자 Bearer 는 403 이고 응답에 줄 0(분모: 운영 관리자는 같은 요청으로 ≥1)
  ⓘ companyId=B 로 고른 운영 관리자에게 A 의 줄 0(분모: companyId=A 로 ≥1)
  ⓙ 회사 없는 줄(운영 관리자의 로그인)은 어느 회사를 골라도 보인다(처분 ⑪ (가))
  ⓚ (AU1b-1) q 는 회사 경계를 넘지 않는다: A 의 줄에 B 사람의 id 가 실려도 A 를 고른 q 는 그 아이디로 0줄
     (분모: B 를 고르면 ≥1, 양성 대조: A 에서 actorUserId 로는 그 줄 1)
  ⓛ (AU1b-1) 행위자 목록(GET /audit-logs/actors): 고객사 사용자 Bearer 는 403 이고 응답에 사람 0(분모: 운영 관리자는
     같은 요청으로 ≥1)
  ⓜ (AU1b-1) companyId=B 로 고른 운영 관리자의 행위자 목록에 A 에만 있는 고객사 사람 0(분모: companyId=A 로 ≥1)

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(분모를 센다).
★ 뒤 밴드는 함수를 더하기만 한다(AU1b 의 행동 다섯 등 — 이 파일의 기존 함수의 단언을 바꾸지 않는다).
무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다. 주인 역할은 고치고 지울 수 있다
(지울 수 없음은 앱 역할에게만 — 2차 보존 정리의 자리).
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Final, LiteralString

import jwt
import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client

from esgapi.core.models import AuditEventRow
from esgapi.core.service.services import documents as document_services
from esgapi.core.service.services.audit import AuditRecorded, record_event
from esgapi.core.tests.resource_fakes import FakeStorage
from tests.security.conftest import count
from tests.security.test_login import OTHER_PASSWORD, PASSWORD, WRONG, customer, operator, try_login
from tests.support.http import bearer

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
TABLE = "core_audit_events"
NOW = datetime(2026, 10, 19, 3, 0, tzinfo=UTC)
INSERT = (
    f"INSERT INTO {TABLE} (company_id, at, actor_kind, actor_user_id, action, event, result, detail) "
    "VALUES (%s, now(), %s, NULL, %s, 'x_done', 'success', %s::jsonb)"
)


def owner_insert(owner: Owner, company_id: int | None, actor_kind: str, action: str, detail: str = "{}") -> None:
    owner.execute(INSERT, [company_id, actor_kind, action, detail])


# ── ⓐ·ⓑ 덧붙이기만 ──


@pytest.mark.parametrize(
    "statement",
    [f"UPDATE {TABLE} SET result = 'failure'", f"DELETE FROM {TABLE}", f"TRUNCATE {TABLE}"],
    ids=["update", "delete", "truncate"],
)
def test_app_role_cannot_change_or_remove_an_audit_line(
    owner: Owner, companies: tuple[int, int], statement: str
) -> None:
    owner_insert(owner, companies[0], "service", "login")
    with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(statement)
    assert getattr(caught.value.__cause__, "sqlstate", None) == "42501"  # insufficient_privilege
    assert owner.execute(f"SELECT result FROM {TABLE}").fetchall() == [("success",)]  # 행은 그대로


def test_app_role_appends_company_lines_and_lines_without_a_company(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    in_a = record_event(
        at=NOW, company_id=a, actor_kind="service", actor_user_id=1, action="upload", event="document_uploaded",
        result="success",
    )  # fmt: skip
    none = record_event(
        at=NOW, company_id=None, actor_kind="admin", actor_user_id=2, action="login", event="login_succeeded",
        result="success",
    )  # fmt: skip
    assert isinstance(in_a, AuditRecorded) and isinstance(none, AuditRecorded)
    assert count(owner, TABLE) == 2  # 커밋됐다(다른 연결이 센다)
    assert owner.execute(f"SELECT company_id, actor_kind FROM {TABLE} ORDER BY id").fetchall() == [
        (a, "service"),
        (None, "admin"),
    ]


# ── ⓒ CHECK ──


@pytest.mark.parametrize(
    ("company", "actor_kind", "action", "detail", "constraint"),
    [
        ("a", "service", "export", "{}", "core_audit_events_action_check"),
        ("a", "service", "login", '{"changed_fields": ["' + "a" * 1100 + '"]}', "core_audit_events_detail_size_check"),
        (None, "service", "login", "{}", "core_audit_events_service_company_check"),
    ],
    ids=["unknown-action", "detail-over-1024-bytes", "customer-line-without-a-company"],
)
def test_the_checks_refuse_what_the_app_would_not_write(
    owner: Owner, companies: tuple[int, int], company: str | None, actor_kind: str, action: str, detail: str,
    constraint: str,
) -> None:  # fmt: skip
    company_id = companies[0] if company == "a" else None
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        owner_insert(owner, company_id, actor_kind, action, detail)
    assert caught.value.diag.constraint_name == constraint
    assert count(owner, TABLE) == 0


def test_the_checks_let_the_edges_in(owner: Owner, companies: tuple[int, int]) -> None:
    """분모: 운영 관리자·명령의 회사 없는 줄과 1024 바이트 안의 detail 은 들어간다."""
    owner_insert(owner, None, "admin", "login")
    owner_insert(owner, None, "command", "setting_change")
    owner_insert(owner, companies[0], "service", "confirm", '{"changed_fields": ["' + "a" * 900 + '"]}')
    assert count(owner, TABLE) == 3


def detail_of_octets(owner: Owner, octets: int) -> str:
    """jsonb 의 글자(detail::text)가 정확히 octets 바이트인 detail. 주인 연결이 그 길이를 다시 잰다(분모)."""
    base = '{"changed_fields": [""]}'
    detail = '{"changed_fields": ["' + "a" * (octets - len(base)) + '"]}'
    row = owner.execute("SELECT octet_length(%s::jsonb::text)", [detail]).fetchone()
    assert row is not None and row[0] == octets
    return detail


def test_the_detail_check_lets_1024_bytes_in_and_refuses_1025(owner: Owner, companies: tuple[int, int]) -> None:
    owner_insert(owner, companies[0], "service", "setting_change", detail_of_octets(owner, 1024))
    with pytest.raises(psycopg.errors.CheckViolation) as caught:
        owner_insert(owner, companies[0], "service", "setting_change", detail_of_octets(owner, 1025))
    assert caught.value.diag.constraint_name == "core_audit_events_detail_size_check"
    assert count(owner, TABLE) == 1


# ── ⓓ~ⓖ 기록 지점(AU1a ②) ──


def lines(owner: Owner, where: LiteralString = "TRUE", params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    return owner.execute(
        f"SELECT event, result, reason, actor_kind, company_id FROM {TABLE} WHERE {where} ORDER BY id", params or []
    ).fetchall()


def test_a_failed_login_line_is_committed(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    customer(a)
    before = count(owner, TABLE)
    assert try_login(client, "kim", WRONG, "tenant-a").status_code == 401
    assert try_login(client, "ghost-" + uuid.uuid4().hex[:8], PASSWORD, "tenant-a").status_code == 401
    assert count(owner, TABLE) == before + 2  # 다른 연결이 센다 — 커밋됐다
    assert lines(owner, "event = 'login_failed'") == [
        ("login_failed", "failure", "wrong_password", "service", a),
        ("login_failed", "failure", "unknown_user", "anonymous", a),
    ]


def post(client: Client, path: str, body: dict[str, Any], access: str | None = None) -> Any:
    headers = {} if access is None else bearer(access)
    response = client.post(path, data=body, content_type="application/json", **headers)
    assert response.status_code in (200, 201, 204), response.content.decode()
    return response


def claims_of(token: str) -> list[str]:
    claims: dict[str, Any] = jwt.decode(token, options={"verify_signature": False})
    return [str(claims[k]) for k in ("jti", "fam") if k in claims]


RESET: Final = "Amber-Forest-6142"
CUSTOMER_NEW: Final = "Silver-Brook-3317"
CREATED: Final = "Quiet-Meadow-2604"


def test_no_secret_reaches_an_audit_line(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓔ 한 세션(처분 ⑬·개정 1 B5) 뒤 감사 표 전부를 떠서 찾는 글자가 0번 — 양성 대조로 아는 아이디는 나온다."""
    a, _ = companies
    ghost = "ghost-" + uuid.uuid4().hex[:8]
    tokens: list[str] = []

    def pair(response: Any) -> dict[str, Any]:
        body: dict[str, Any] = response.json()
        tokens.extend([body["access"], body["refresh"]])
        return body

    operator()
    first = pair(post(client, "/api/auth/login", {"username": "ops", "password": PASSWORD}))
    change = {"currentPassword": PASSWORD, "newPassword": OTHER_PASSWORD}
    ops = pair(post(client, "/api/users/me/password", change, first["access"]))["access"]
    made = {"companyId": a, "username": "kim", "name": "김담당", "password": CREATED}
    kim = post(client, "/api/users", made, ops).json()["id"]
    post(client, f"/api/users/{kim}/password-reset", {"companyId": a, "password": RESET}, ops)
    assert try_login(client, "kim", WRONG, "tenant-a").status_code == 401
    assert try_login(client, ghost, RESET, "tenant-a").status_code == 401
    signed_in = pair(try_login(client, "kim", RESET, "tenant-a"))
    change = {"currentPassword": RESET, "newPassword": CUSTOMER_NEW}
    changed = pair(post(client, "/api/users/me/password", change, signed_in["access"]))
    rotated = pair(post(client, "/api/auth/refresh", {"refresh": changed["refresh"]}))
    post(client, "/api/auth/revoke", {"refresh": rotated["refresh"]})

    dump = "\n".join(text for (text,) in owner.execute(f"SELECT row_to_json(t)::text FROM {TABLE} t ORDER BY id"))
    hashes = [h for (h,) in owner.execute("SELECT password FROM users") if h]
    secrets = [PASSWORD, OTHER_PASSWORD, CREATED, RESET, CUSTOMER_NEW, WRONG, ghost, *tokens, *hashes]
    secrets += [part for token in tokens for part in claims_of(token)]
    assert len(dump.splitlines()) >= 8  # 분모: 줄이 있다
    assert dump.count('"target_label":"kim"') >= 1  # 양성 대조: 덤프가 칸을 싣는다
    events = [json.loads(line)["event"] for line in dump.splitlines()]
    assert {"login_failed", "login_succeeded", "user_created", "password_reset", "password_changed", "logout"} <= set(
        events
    )
    assert [secret for secret in secrets if secret in dump] == []


def test_an_upload_line_belongs_to_its_company_only(owner: Owner, companies: tuple[int, int]) -> None:
    """ⓕ 회사 A 의 올림 줄은 A 로만 열린다(앱 역할 연결의 for_company)."""
    a, b = companies
    storage = FakeStorage()
    created = document_services.create_document(
        company_id=a, uploaded_by="7", file_name="a.pdf", size_bytes=5, max_upload_bytes=1000, storage=storage
    )
    assert isinstance(created, document_services.DocumentCreated)
    storage.put(created.document.storage_key, b"12345")
    confirmed = document_services.confirm_upload(
        company_id=a, document_id=created.document.id, storage=storage, now=NOW, actor_user_id=7
    )
    assert isinstance(confirmed, document_services.UploadConfirmed)
    assert lines(owner, "action = 'upload'") == [("document_uploaded", "success", None, "service", a)]
    assert (AuditEventRow.for_company(a).count(), AuditEventRow.for_company(b).count()) == (1, 0)


def test_an_operator_login_line_has_no_company(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓖ 운영 관리자의 로그인 줄은 회사 칸 NULL — 회사를 고르는 칸에 섞이지 않는 쪽."""
    operator()
    assert try_login(client, "ops", PASSWORD, None).status_code == 200
    assert lines(owner, "event = 'login_succeeded'") == [("login_succeeded", "success", None, "admin", None)]


def operator_access(client: Client) -> str:
    """운영 관리자를 만들고 로그인해 비밀번호를 한 번 바꾼 access(로그인·바꾸기 줄이 회사 없이 남는다)."""
    operator()
    first = post(client, "/api/auth/login", {"username": "ops", "password": PASSWORD}).json()
    change = {"currentPassword": PASSWORD, "newPassword": OTHER_PASSWORD}
    access: str = post(client, "/api/users/me/password", change, first["access"]).json()["access"]
    return access


def customer_access(client: Client, company_id: int) -> str:
    """회사 A(tenant-a)의 고객사 사용자 kim 이 로그인해 비밀번호를 바꾼 access(로그인 줄이 A 로 남는다)."""
    customer(company_id)
    first = try_login(client, "kim", PASSWORD, "tenant-a")
    assert first.status_code == 200, first.content.decode()
    change = {"currentPassword": PASSWORD, "newPassword": OTHER_PASSWORD}
    access: str = post(client, "/api/users/me/password", change, first.json()["access"]).json()["access"]
    return access


def audit_page(client: Client, access: str, company_id: int) -> Any:
    return client.get(f"/api/audit-logs?companyId={company_id}&limit=100", **bearer(access))


def test_a_customer_cannot_read_the_audit_lines(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓗ 고객사 사용자 Bearer 는 403 FORBIDDEN 이고 응답에 줄 0 — 분모: 운영 관리자의 같은 요청은 줄을 본다."""
    a, _ = companies
    access = customer_access(client, a)
    response = audit_page(client, access, a)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert "results" not in response.json()
    assert count(owner, TABLE) >= 1  # 분모: 줄이 있다(kim 의 로그인)
    seen = audit_page(Client(), operator_access(Client()), a)
    assert seen.status_code == 200
    assert len(seen.json()["results"]) >= 1


def test_an_operator_choosing_b_sees_no_line_of_a(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓘ companyId=B 로 고르면 A 의 줄 0(앱 역할 연결의 for_company ∪ 회사 없는 입구) — 분모: A 로 고르면 ≥1."""
    a, b = companies
    customer_access(Client(), a)
    of_a = {row_id for (row_id,) in owner.execute(f"SELECT id FROM {TABLE} WHERE company_id = %s", [a])}
    assert len(of_a) >= 1  # 분모: A 의 줄이 커밋돼 있다(로그인·바꾸기)
    access = operator_access(client)
    in_b = audit_page(client, access, b)
    in_a = audit_page(client, access, a)
    assert (in_b.status_code, in_a.status_code) == (200, 200)
    assert {line["id"] for line in in_b.json()["results"]} & of_a == set()
    assert {line["companyId"] for line in in_b.json()["results"]} <= {b, None}
    assert {line["id"] for line in in_a.json()["results"]} >= of_a


def test_a_line_without_a_company_is_seen_from_every_company(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """ⓙ 회사 없는 줄(운영 관리자의 로그인)은 A 를 골라도 B 를 골라도 보인다(처분 ⑪ (가))."""
    a, b = companies
    access = operator_access(client)
    companyless = {row_id for (row_id,) in owner.execute(f"SELECT id FROM {TABLE} WHERE company_id IS NULL")}
    assert len(companyless) >= 1  # 분모: 운영 관리자의 로그인 줄이 커밋돼 있다
    for company_id in (a, b):
        found = audit_page(client, access, company_id)
        assert found.status_code == 200
        assert {line["id"] for line in found.json()["results"]} >= companyless


PERSON_LINE = (
    f"INSERT INTO {TABLE} (company_id, at, actor_kind, actor_user_id, action, event, result, detail) "
    "VALUES (%s, now(), 'service', %s, 'login', 'login_succeeded', 'success', '{}'::jsonb) RETURNING id"
)


def test_q_does_not_cross_the_company_line(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓚ 주인 역할이 A 의 줄 하나를 B 사람의 id 로 넣는다 — A 를 고른 q 는 B 사람의 아이디로 0줄(이름을 고른 회사
    안에서만 푼다), 분모: B 를 고르면 그 사람의 줄 ≥1, 양성 대조: A 에서 actorUserId 로는 그 줄이 보인다."""
    a, b = companies
    park = customer(b, "park")
    row_a = owner.execute(PERSON_LINE, [a, park]).fetchone()
    row_b = owner.execute(PERSON_LINE, [b, park]).fetchone()
    assert row_a is not None and row_b is not None
    access = operator_access(client)

    def ids(query: str) -> list[int]:
        response = client.get(f"/api/audit-logs?{query}&limit=100", **bearer(access))
        assert response.status_code == 200, response.content.decode()
        return [line["id"] for line in response.json()["results"]]

    assert ids(f"companyId={a}&q=park") == []
    assert row_b[0] in ids(f"companyId={b}&q=park")  # 분모
    assert ids(f"companyId={a}&actorUserId={park}") == [row_a[0]]  # 양성 대조: 줄은 A 에서 보인다


def actor_list(client: Client, access: str, company_id: int) -> Any:
    return client.get(f"/api/audit-logs/actors?companyId={company_id}", **bearer(access))


def test_a_customer_cannot_read_the_actor_list(client: Client, owner: Owner, companies: tuple[int, int]) -> None:
    """ⓛ 고객사 사용자 Bearer 는 403 FORBIDDEN 이고 응답에 사람 0 — 분모: 운영 관리자의 같은 요청은 사람을 본다."""
    a, _ = companies
    access = customer_access(client, a)
    response = actor_list(client, access, a)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert "results" not in response.json()
    assert count(owner, TABLE) >= 1  # 분모: 줄이 있다(kim 의 로그인)
    seen = actor_list(Client(), operator_access(Client()), a)
    assert seen.status_code == 200
    assert len(seen.json()["results"]) >= 1


def test_an_operator_choosing_b_sees_no_person_only_in_a(
    client: Client, owner: Owner, companies: tuple[int, int]
) -> None:
    """ⓜ A 의 고객사 사람(kim — 로그인·바꾸기 줄이 A 로 남음)은 B 를 고른 행위자 목록에 0 — 분모: A 를 고르면 ≥1."""
    a, b = companies
    customer_access(Client(), a)
    of_a = {user_id for (user_id,) in owner.execute(f"SELECT DISTINCT actor_user_id FROM {TABLE} WHERE company_id = %s "
                                                    "AND actor_kind = 'service'", [a])}  # fmt: skip
    assert len(of_a) >= 1  # 분모: A 의 사람 줄이 커밋돼 있다
    access = operator_access(client)
    in_b, in_a = actor_list(client, access, b), actor_list(client, access, a)
    assert (in_b.status_code, in_a.status_code) == (200, 200)
    assert {line["actorUserId"] for line in in_b.json()["results"] if line["actorKind"] == "service"} & of_a == set()
    assert {line["actorUserId"] for line in in_a.json()["results"]} >= of_a
