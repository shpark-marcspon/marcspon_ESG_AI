"""그린워싱 결과·검토(밴드 G1b — greenwash_reviews·greenwash_review_marks)를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 남의 회사(§3-4-1·5 — 감독 처분 2, 테스트 감독 39 동의): A 의 실행 id 로 B 의 세션 → 결과·검토 GET·표시 PUT 404,
     그 run_id 의 검토·표시 행 0, 감사 0. 분모: A 의 세션으로 같은 요청 200·행 ≥ 1·감사 ≥ 1(회사 A).
  ⓑ 앱 역할은 검토 표 둘을 지우거나 비우지 못한다(DELETE·TRUNCATE → 42501 — 표시 지우기는 NULL 로 UPDATE).
     분모: 앱 역할의 UPDATE 는 된다.
  ⓒ 표시 → 검토의 같은 회사 복합 외래 키: 검토 행 없는 (회사, 실행)의 표시, 남의 회사의 검토를 가리키는 표시는
     그 문에서 23503(NOT DEFERRABLE). 분모: 같은 회사의 검토가 있으면 들어간다.
  ⓓ 경합(§3-4-6, 연결 둘·진짜 커밋 — test_documents_race.py 꼴): 확정이 먼저 잠그면 겹친 표시 PUT 은 409, 표시가
     섞이지 않는다 · 검토 행이 없을 때 확정 둘이 겹치면 하나 200·하나 409, 검토 행 하나, confirm 감사 하나.
  ⓔ 운영 관리자 Bearer(§3-4-4) → 그린워싱 경로 넷(결과·검토 GET·PUT·목록 줄) 회사가 둘이라 400 company_ambiguous, 행 0.
  ⓕ 이웃 id(§3-4-2): B 의 세션에 A 의 실행 id 와 없는 id 의 응답이 상태·본문 바이트까지 같다.
  ⓖ 목록 줄(§3-4-3): B 의 세션의 GET /greenwash/checks 에 A 의 문서·실행 0. 분모: A 의 세션에는 A 의 것.
  ⓗ 엑셀 보고서(G1b-2a): A 의 실행 id 로 B 의 세션·Bearer → report(확정 전·확정본) 404, 이웃 id 와 바이트 같음,
     download 감사 0. 분모: A 의 세션으로 200 xlsx·감사 한 줄(회사 A).
  ⓘ 목록 줄의 묶음 읽기(G1b-2b): 묶음 selector 셋에 A·B id 를 섞어 A 의 회사로 → B 의 행 0, A 의 행 ≥ 1 · 묶음 읽기
     뒤의 목록 줄에 B 세션은 A 의 실행·문서 0. 분모: A 세션에는 A 의 것(failedPageCount 값).
  ⓙ 보고서 응답(G1b-2b ③): 같은 응답에서 Content-Type xlsx 와 X-Content-Type-Options: nosniff.
  ⓚ 검토 고침(G1b-3 — 표시 표의 고침 칸 아홉): 남의 회사 실행에 edits PUT → 404·표시 표 행·값 그대로 · 앱 역할이 새
     칸을 UPDATE 함(0001 의 표 단위 GRANT 가 덮음 — 마이그레이션 0004 에 GRANT 줄 없음). 분모: DELETE 는 42501 그대로.
     같은 run_id·itemIndex 에 남의 회사 행이 있어도 A 의 표시·고침 UPDATE 가 그 행을 안 건드림(쓰기 회사 조건).

검토 표의 run_id 는 외래 키가 아니다(MARC-ENT-210 (1)) — 같은 회사는 쓰는 길(actions 가 세션의 회사로 실행을 먼저
찾는다)이 지키고 ⓐ 가 잰다. Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다.
무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다.
"""

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import psycopg
import pytest
from django.db import DatabaseError, connection, connections, transaction
from django.test import Client
from psycopg import sql

from esgapi.core.service.selectors import documents as document_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from tests.security.conftest import count
from tests.security.test_runs import owner_document
from tests.support.http import customer_bearer, login

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
REVIEWS: Final = "greenwash_reviews"
MARKS: Final = "greenwash_review_marks"
EXAMPLE: Final = (
    Path(__file__).resolve().parents[2] / "esgapi/greenwash/tests/data/contract-examples/result-normal.json"
)


def owner_done_run(owner: Owner, company_id: int) -> int:
    """끝난 그린워싱 실행 하나와 그 결과(계약 예시 result-normal — 문장 넷). 주인 역할로."""
    document_id = owner_document(owner, company_id)
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, %s, 'greenwash', 'greenwash.colab@E0', '{}', '{}', 'service', 'done', 1, 0, 7) "
        "RETURNING id",
        [company_id, document_id],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, 'greenwash.result@1', %s::jsonb)",
        [company_id, run_id, EXAMPLE.read_text(encoding="utf-8")],
    )
    return run_id


def session(tenant: str, sub: str) -> Client:
    client = Client()
    login(client, sub=sub, tenant_id=tenant)
    return client


def rows_of(owner: Owner, table: str, run_id: int) -> int:
    query = sql.SQL("SELECT count(*) FROM {} WHERE run_id = %s").format(sql.Identifier(table))
    row = owner.execute(query, [run_id]).fetchone()
    assert row is not None
    return int(row[0])


def review_audit(owner: Owner) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT company_id, action, target_id FROM core_audit_events "
        "WHERE action IN ('adopt', 'exclude', 'confirm') ORDER BY id"
    ).fetchall()


def put(client: Client, run_id: int, body: dict[str, Any]) -> Any:
    return client.put(f"/api/greenwash/runs/{run_id}/review", data=body, content_type="application/json")


NOW: Final = datetime(2026, 10, 19, 21, 0, tzinfo=UTC)
ADOPT_ONE: Final = {"marks": [{"itemIndex": 0, "decision": "adopted", "excludeReason": None}]}


# ── ⓐ 남의 회사 ──


def test_another_companys_result_and_review_are_not_found(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = owner_done_run(owner, a)
    theirs = session("tenant-b", "edk-user-2")
    assert theirs.get(f"/api/greenwash/runs/{run_id}/result").status_code == 404
    assert theirs.get(f"/api/greenwash/runs/{run_id}/review").status_code == 404
    assert put(theirs, run_id, ADOPT_ONE).status_code == 404
    assert put(theirs, run_id, {"state": "confirmed", "marks": []}).status_code == 404
    assert (rows_of(owner, REVIEWS, run_id), rows_of(owner, MARKS, run_id)) == (0, 0)
    assert review_audit(owner) == []

    mine = session("tenant-a", "edk-user-1")
    assert mine.get(f"/api/greenwash/runs/{run_id}/result").status_code == 200
    assert mine.get(f"/api/greenwash/runs/{run_id}/review").status_code == 200
    saved = put(mine, run_id, ADOPT_ONE)
    assert (saved.status_code, saved.json()["state"]) == (200, "in_review")
    assert (rows_of(owner, REVIEWS, run_id), rows_of(owner, MARKS, run_id)) == (1, 1)
    assert review_audit(owner) == [(a, "adopt", run_id)]
    # 확정한 뒤에도 B 는 그대로 404(잠김 409 를 새지 않는다)
    assert put(mine, run_id, {"state": "confirmed", "marks": []}).status_code == 200
    assert put(theirs, run_id, ADOPT_ONE).status_code == 404
    assert [row[0] for row in review_audit(owner)] == [a, a]
    assert count(owner, REVIEWS) == 1  # B 의 회사로 쓴 행 0


# ── ⓑ 지울 수 없음 ──


def denied(statement: str) -> str | None:
    """앱 역할로 문 하나를 보내고 그 SQLSTATE(된 것이면 None)."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement)
    except DatabaseError as error:
        return getattr(error.__cause__, "sqlstate", None)
    return None


@pytest.mark.parametrize("table", [REVIEWS, MARKS])
@pytest.mark.parametrize("verb", ["delete", "truncate"])
def test_app_role_cannot_remove_a_review_row(owner: Owner, companies: tuple[int, int], table: str, verb: str) -> None:
    a, _ = companies
    run_id = owner_done_run(owner, a)
    assert put(session("tenant-a", "edk-user-1"), run_id, ADOPT_ONE).status_code == 200
    before = (count(owner, REVIEWS), count(owner, MARKS))
    assert before == (1, 1)  # 분모: 두 표 다 한 행
    statement = f"DELETE FROM {table}" if verb == "delete" else f"TRUNCATE {table} CASCADE"
    assert denied(statement) == "42501"  # insufficient_privilege
    assert (count(owner, REVIEWS), count(owner, MARKS)) == before
    assert denied(f"UPDATE {MARKS} SET decision = NULL") is None  # 분모: 지우기 = NULL 로 UPDATE 는 된다


# ── ⓒ 같은 회사 복합 외래 키 ──


def insert_mark(company_id: int, run_id: int, index: int = 0) -> str | None:
    return denied(
        f"INSERT INTO {MARKS} (created_at, updated_at, company_id, run_id, item_index, decision, exclude_reason) "
        f"VALUES (now(), now(), {company_id}, {run_id}, {index}, 'adopted', NULL)"
    )


def test_a_mark_needs_a_review_of_the_same_company(owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    run_id = owner_done_run(owner, a)
    assert insert_mark(a, run_id) == "23503"  # 검토 행이 없다
    owner.execute(
        f"INSERT INTO {REVIEWS} (created_at, updated_at, company_id, run_id, state) "
        "VALUES (now(), now(), %s, %s, 'in_review')",
        [a, run_id],
    )
    assert insert_mark(b, run_id) == "23503"  # 남의 회사의 검토를 가리킨다
    assert insert_mark(a, run_id) is None  # 분모: 같은 회사의 검토가 있으면 들어간다
    deferrable = owner.execute(
        "SELECT condeferrable FROM pg_constraint WHERE conname = 'greenwash_review_marks_run_id_same_company_fk'"
    ).fetchall()
    assert deferrable == [(False,)]
    assert json.loads(EXAMPLE.read_text(encoding="utf-8"))["items"]  # 분모: 예시에 문장이 있다


@pytest.mark.parametrize(
    ("decision", "reason", "state"),
    [
        ("NULL", "'사유'", "23514"),  # 미검토인데 사유 — NULL 3값 논리로 새던 갈래(검증 2 B1)
        ("'excluded'", "NULL", "23514"),
        ("'adopted'", "'사유'", "23514"),
        ("'other'", "NULL", "23514"),
        ("NULL", "NULL", None),  # 분모: 미검토(지운 표시)
        ("'adopted'", "NULL", None),
        ("'excluded'", "'사유'", None),
    ],
)
def test_the_decision_check_holds_for_the_app_role(
    owner: Owner, companies: tuple[int, int], decision: str, reason: str, state: str | None
) -> None:
    """표시 표의 CHECK(decision ⇔ 사유)를 앱 역할의 INSERT 로 잰다 — 앱 코드를 지나지 않는 길."""
    a, _ = companies
    run_id = owner_done_run(owner, a)
    owner.execute(
        f"INSERT INTO {REVIEWS} (created_at, updated_at, company_id, run_id, state) "
        "VALUES (now(), now(), %s, %s, 'in_review')",
        [a, run_id],
    )
    got = denied(
        f"INSERT INTO {MARKS} (created_at, updated_at, company_id, run_id, item_index, decision, exclude_reason) "
        f"VALUES (now(), now(), {a}, {run_id}, 0, {decision}, {reason})"
    )
    assert got == state
    assert rows_of(owner, MARKS, run_id) == (0 if state else 1)


# ── ⓓ 경합 ──


def race(monkeypatch: pytest.MonkeyPatch, company_id: int, run_id: int, calls: dict[str, bool]) -> dict[str, object]:
    """스레드마다(연결 하나·durable 블록 하나) actions.put_review 를 부른다. calls = 이름 → confirm.
    두 스레드가 다 실행을 읽은 뒤(장벽) 잠금으로 간다. 이름이 「mark」인 스레드는 「confirm」 스레드가 검토 행을 잠근
    뒤에야 잠그러 간다(확정이 먼저 잠그는 차례를 못 박는다). 돌려주는 것: 이름 → 결과(또는 예외)."""
    from esgapi.greenwash.service.actions import review as actions
    from esgapi.greenwash.service.selectors import review as selectors

    barrier = threading.Barrier(len(calls))
    confirm_locked = threading.Event()
    role = threading.local()
    reviewable: Callable[..., Any] = actions._reviewable  # pyright: ignore[reportPrivateUsage]
    lock_review: Callable[..., Any] = selectors.lock_review

    def reviewable_then_wait(*args: Any, **kwargs: Any) -> Any:
        found = reviewable(*args, **kwargs)
        barrier.wait(timeout=10)
        return found

    def ordered_lock(**kwargs: Any) -> Any:
        if getattr(role, "name", "") == "mark":
            assert confirm_locked.wait(timeout=10)
        found = lock_review(**kwargs)
        if getattr(role, "name", "") == "confirm":
            confirm_locked.set()
        return found

    monkeypatch.setattr(actions, "_reviewable", reviewable_then_wait)
    if "mark" in calls:
        monkeypatch.setattr(selectors, "lock_review", ordered_lock)
    results: dict[str, object] = {}
    guard = threading.Lock()
    marks: dict[str, list[dict[str, Any]]] = {
        "confirm": [],
        "mark": [{"itemIndex": 0, "decision": "excluded", "excludeReason": "겹친 PUT 의 사유"}],
    }

    def call(name: str, confirm: bool) -> None:
        role.name = "confirm" if confirm and "mark" in calls else name
        try:
            with transaction.atomic(durable=True):
                result: object = actions.put_review(
                    company_id=company_id,
                    actor_kind="service",
                    actor_user_id=7,
                    run_id=run_id,
                    confirm=confirm,
                    marks=marks["confirm" if confirm else "mark"],  # pyright: ignore[reportArgumentType]
                    now=NOW,
                )
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result

    threads = [threading.Thread(target=call, args=(name, confirm)) for name, confirm in calls.items()]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]
    return results


def kind_of(result: object) -> str:
    return type(result).__name__ if not isinstance(result, dict) else "state"


def test_a_put_that_overlaps_a_confirm_is_locked(
    owner: Owner, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    run_id = owner_done_run(owner, a)
    assert put(session("tenant-a", "edk-user-1"), run_id, ADOPT_ONE).status_code == 200  # 검토 행 in_review
    results = race(monkeypatch, a, run_id, {"confirm": True, "mark": False})
    assert {name: kind_of(r) for name, r in results.items()} == {"confirm": "state", "mark": "ReviewLocked"}
    assert owner.execute(
        f"SELECT state, confirmed_by_user_id FROM {REVIEWS} WHERE run_id = %s", [run_id]
    ).fetchall() == [("confirmed", 7)]
    # 표시가 섞이지 않았다: 확정이 채운 채택 넷 그대로(겹친 PUT 의 제외 0)
    assert owner.execute(
        f"SELECT item_index, decision, exclude_reason FROM {MARKS} WHERE run_id = %s ORDER BY item_index", [run_id]
    ).fetchall() == [(i, "adopted", None) for i in range(4)]
    assert [row[1] for row in review_audit(owner)] == ["adopt", "confirm"]  # 첫 PUT 의 adopt + 확정. exclude 0


def test_two_first_confirms_make_one_review(
    owner: Owner, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    run_id = owner_done_run(owner, a)
    assert rows_of(owner, REVIEWS, run_id) == 0  # 분모: 검토 행 없음 — 만들기 경합
    results = race(monkeypatch, a, run_id, {"first": True, "second": True})
    assert sorted(kind_of(r) for r in results.values()) == ["ReviewLocked", "state"]
    assert (rows_of(owner, REVIEWS, run_id), rows_of(owner, MARKS, run_id)) == (1, 4)
    assert [row[1] for row in review_audit(owner)] == ["confirm"]


# ── ⓔ 운영 관리자 ──

GREENWASH_FOUR: Final[tuple[tuple[str, str, dict[str, Any] | None], ...]] = (
    ("get", "/api/greenwash/runs/{run_id}/result", None),
    ("get", "/api/greenwash/runs/{run_id}/review", None),
    ("put", "/api/greenwash/runs/{run_id}/review", {"marks": []}),
    ("get", "/api/greenwash/checks", None),
)


def send(client: Client, method: str, url: str, body: dict[str, Any] | None) -> Any:
    if body is None:
        return getattr(client, method)(url)
    return getattr(client, method)(url, data=body, content_type="application/json")


def test_an_operator_bearer_with_two_companies_is_400_on_the_greenwash_routes(
    owner: Owner, companies: tuple[int, int]
) -> None:
    from esgapi.user.service.services.user import create_operator
    from esgapi.user.service.utils.login import UserCreated

    a, _ = companies
    run_id = owner_done_run(owner, a)
    created = create_operator(username="gw-ops", name="운영자", password="Blue-Harbor-7310")
    assert isinstance(created, UserCreated)
    owner.execute("UPDATE users SET is_initial = false WHERE id = %s", [created.user_id])
    logged = Client().post(
        "/api/auth/login",
        data={"username": "gw-ops", "password": "Blue-Harbor-7310"},
        content_type="application/json",
    )
    assert logged.status_code == 200, logged.content.decode()
    operator = Client(headers={"Authorization": f"Bearer {logged.json()['access']}"})
    assert operator.get("/api/users/me").status_code == 200  # 분모: 토큰은 산 것이다
    for method, path, body in GREENWASH_FOUR:
        response = send(operator, method, path.replace("{run_id}", str(run_id)), body)
        assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS"), path
    assert (count(owner, REVIEWS), count(owner, MARKS)) == (0, 0)
    assert review_audit(owner) == []


# ── ⓕ 이웃 id ──


@pytest.mark.parametrize(("method", "path", "body"), GREENWASH_FOUR[:3], ids=["result", "review-get", "review-put"])
def test_another_companys_id_answers_like_a_missing_id(
    owner: Owner, companies: tuple[int, int], method: str, path: str, body: dict[str, Any] | None
) -> None:
    a, _ = companies
    run_id = owner_done_run(owner, a)
    missing = run_id + 1000
    assert owner.execute("SELECT count(*) FROM run_runs WHERE id = %s", [missing]).fetchone() == (0,)  # 분모
    theirs = session("tenant-b", "edk-user-2")
    got = send(theirs, method, path.replace("{run_id}", str(run_id)), body)
    none = send(theirs, method, path.replace("{run_id}", str(missing)), body)
    assert (got.status_code, got.content) == (none.status_code, none.content)
    assert got.status_code == 404
    mine = send(session("tenant-a", "edk-user-1"), method, path.replace("{run_id}", str(run_id)), body)
    assert mine.status_code == 200  # 분모: 제 회사로는 보인다


# ── ⓖ 목록 줄 ──


@pytest.mark.parametrize("via", ["session", "bearer"])
def test_the_checks_list_shows_only_my_company(owner: Owner, companies: tuple[int, int], via: str) -> None:
    a, b = companies
    a_runs = {owner_done_run(owner, a)}  # owner_document 는 회사마다 문서 하나(같은 storage_key)
    b_run = owner_done_run(owner, b)
    a_documents = {
        int(row[0]) for row in owner.execute("SELECT document_id FROM run_runs WHERE company_id = %s", [a]).fetchall()
    }
    assert len(a_runs) == 1 and len(a_documents) == 1  # 분모: A 의 실행·문서 하나

    if via == "session":
        theirs = session("tenant-b", "edk-user-2")
    else:
        theirs = Client(
            headers={"Authorization": f"Bearer {customer_bearer(Client(), company_id=b, subdomain='tenant-b')}"}
        )
    seen = theirs.get("/api/greenwash/checks")
    assert seen.status_code == 200
    body = seen.json()
    assert [r["runId"] for r in body["runs"]] == [b_run]
    assert {d["documentId"] for d in body["documents"]}.isdisjoint(a_documents)
    assert len(body["documents"]) == 1

    mine = session("tenant-a", "edk-user-1").get("/api/greenwash/checks").json()
    assert {r["runId"] for r in mine["runs"]} == a_runs  # 분모: A 의 세션에는 A 의 것
    assert {d["documentId"] for d in mine["documents"]} == a_documents
    assert [r["errorCode"] for r in mine["runs"]] == [None]  # done 줄은 null(밴드 G1e)


def test_the_checks_list_shows_my_failed_runs_error_code_only_to_my_company(
    owner: Owner, companies: tuple[int, int]
) -> None:
    """errorCode(밴드 G1e): A 의 실패 줄과 그 code 는 B 세션에 0, A 세션에는 정해진 code 글자 그대로. 남은 code 가
    있어도 failed 밖(processing·queued)은 null."""
    a, b = companies
    a_document = owner_document(owner, a)
    a_codes: dict[int, str | None] = {}
    for status, code in [("failed", "no_text_layer"), ("processing", "step_error"), ("queued", None)]:
        row = owner.execute(
            "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, "
            "versions, purpose, status, attempts, stalled_attempts, created_by_user_id, error_code, failed_step) "
            "VALUES (now(), now(), %s, %s, 'greenwash', 'greenwash.colab@E0', '{}', '{}', 'service', %s, 1, 0, 7, "
            "%s, 'extract') RETURNING id",
            [a, a_document, status, code],
        ).fetchone()
        assert row is not None
        a_codes[int(row[0])] = "no_text_layer" if status == "failed" else None
    b_run = owner_done_run(owner, b)

    theirs = session("tenant-b", "edk-user-2").get("/api/greenwash/checks")
    assert theirs.status_code == 200
    assert [(r["runId"], r["errorCode"]) for r in theirs.json()["runs"]] == [(b_run, None)]  # A 의 실패 줄·code 0
    assert "no_text_layer" not in theirs.content.decode()

    mine = session("tenant-a", "edk-user-1").get("/api/greenwash/checks").json()
    assert {r["runId"]: r["errorCode"] for r in mine["runs"]} == a_codes  # 분모: A 세션에는 보인다


# ── ⓗ 엑셀 보고서(G1b-2a) ──


def download_audit(owner: Owner) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT company_id, event, target_kind, target_id FROM core_audit_events WHERE action = 'download' "
        "AND event = 'greenwash_report_downloaded' ORDER BY id"
    ).fetchall()


@pytest.mark.parametrize("via", ["session", "bearer"])
def test_another_companys_report_is_not_found_and_not_audited(
    owner: Owner, companies: tuple[int, int], via: str
) -> None:
    a, b = companies
    run_id = owner_done_run(owner, a)
    if via == "session":
        theirs = session("tenant-b", "edk-user-2")
    else:
        theirs = Client(
            headers={"Authorization": f"Bearer {customer_bearer(Client(), company_id=b, subdomain='tenant-b')}"}
        )
    for query in ("", "?confirmed=true"):
        got = theirs.get(f"/api/greenwash/runs/{run_id}/report{query}")
        none = theirs.get(f"/api/greenwash/runs/{run_id + 1000}/report{query}")
        assert (got.status_code, got.content) == (none.status_code, none.content)
        assert got.status_code == 404
    assert download_audit(owner) == []

    mine = session("tenant-a", "edk-user-1").get(f"/api/greenwash/runs/{run_id}/report")
    assert mine.status_code == 200
    assert mine["Content-Disposition"] == 'attachment; filename="greenwash-report.xlsx"'
    assert download_audit(owner) == [(a, "greenwash_report_downloaded", "report", run_id)]


# ── ⓘ 목록 줄의 묶음 읽기(G1b-2b — MARC-ISSUE-219) ──


def owner_step(owner: Owner, company_id: int, run_id: int) -> None:
    owner.execute(
        "INSERT INTO run_steps (created_at, updated_at, company_id, run_id, name, position, status, data) "
        "VALUES (now(), now(), %s, %s, 'extract', 0, 'done', '{}'::jsonb)",
        [company_id, run_id],
    )


def document_of_run(owner: Owner, run_id: int) -> int:
    row = owner.execute("SELECT document_id FROM run_runs WHERE id = %s", [run_id]).fetchone()
    assert row is not None
    return int(row[0])


def test_the_batch_reads_return_no_rows_of_another_company(owner: Owner, companies: tuple[int, int]) -> None:
    """앱 역할로 부른 묶음 selector 셋: A 의 회사로 A·B 의 id 를 섞어 넣으면 B 의 행 0, A 의 행 ≥ 1(분모)."""
    a, b = companies
    a_run, b_run = owner_done_run(owner, a), owner_done_run(owner, b)
    owner_step(owner, a, a_run)
    owner_step(owner, b, b_run)
    a_document, b_document = document_of_run(owner, a_run), document_of_run(owner, b_run)
    steps = run_selectors.step_rows_of(company_id=a, run_ids=[a_run, b_run])
    results = run_selectors.results_of(company_id=a, run_ids=[a_run, b_run])
    documents = document_selectors.documents_of(company_id=a, document_ids=[a_document, b_document])
    assert (set(steps), set(results), set(documents)) == ({a_run}, {a_run}, {a_document})
    assert len(steps[a_run]) >= 1 and len(results[a_run]) >= 1  # 분모: A 의 행은 나온다
    assert all(d.company_id == a for d in documents.values())


def test_the_checks_list_after_the_batch_read_shows_only_my_company(owner: Owner, companies: tuple[int, int]) -> None:
    """묶음 읽기 뒤의 목록 줄: B 세션에 A 의 실행·문서·실패 쪽 수 0, A 세션에는 A 의 것(failedPageCount 1 — 분모)."""
    a, b = companies
    a_run, b_run = owner_done_run(owner, a), owner_done_run(owner, b)
    owner_step(owner, a, a_run)
    a_document = document_of_run(owner, a_run)
    theirs = session("tenant-b", "edk-user-2").get("/api/greenwash/checks")
    assert theirs.status_code == 200
    body = theirs.json()
    assert [r["runId"] for r in body["runs"]] == [b_run]
    assert a_document not in {d["documentId"] for d in body["documents"]}
    assert body["truncated"] is False
    mine = session("tenant-a", "edk-user-1").get("/api/greenwash/checks").json()
    assert [(r["runId"], r["failedPageCount"], len(r["steps"])) for r in mine["runs"]] == [(a_run, 1, 1)]
    assert [d["documentId"] for d in mine["documents"]] == [a_document]


# ── ⓙ 보고서 응답의 nosniff(G1b-2b ③ — MARC-ISSUE-255) ──


def test_the_report_download_says_nosniff_with_the_xlsx_type(owner: Owner, companies: tuple[int, int]) -> None:
    """앱 역할로 내려받은 보고서: 같은 응답에서 Content-Type 이 xlsx 이고 X-Content-Type-Options 가 nosniff."""
    a, _ = companies
    run_id = owner_done_run(owner, a)
    got = session("tenant-a", "edk-user-1").get(f"/api/greenwash/runs/{run_id}/report")
    assert got.status_code == 200
    assert got["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert got["X-Content-Type-Options"] == "nosniff"


# ── ⓚ 검토 고침(G1b-3) ──

EDIT_ONE: Final = {
    "marks": [],
    "edits": [{"itemIndex": 1, "level": "Low", "reasonBullets": ["지은 사유"], "fixParagraph": None}],
}
EDIT_COLUMNS: Final = (
    "decision, exclude_reason, edited_level, level_edited_at, level_edited_by_user_id, edited_reason_bullets, "
    "reasons_edited_at, reasons_edited_by_user_id, edited_fix_paragraph, fix_edited_at, fix_edited_by_user_id"
)


def mark_values(owner: Owner, run_id: int) -> list[tuple[Any, ...]]:
    return owner.execute(
        f"SELECT company_id, item_index, {EDIT_COLUMNS} FROM {MARKS} WHERE run_id = %s ORDER BY company_id, item_index",
        [run_id],
    ).fetchall()


def test_another_companys_run_cannot_take_edits(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = owner_done_run(owner, a)
    mine = session("tenant-a", "edk-user-1")
    saved = put(mine, run_id, EDIT_ONE)
    assert (saved.status_code, saved.json()["state"]) == (200, "in_review")  # 분모: A 의 세션은 고친다
    before = mark_values(owner, run_id)
    assert [(row[0], row[1], row[4]) for row in before] == [(a, 1, "Low")]
    theirs = session("tenant-b", "edk-user-2")
    bodies: list[dict[str, Any]] = [
        {"marks": [], "edits": [{"itemIndex": 1, "level": "High", "reasonBullets": None, "fixParagraph": "B"}]},
        {"marks": [], "edits": []},
        {"state": "confirmed", "marks": [], "edits": []},
    ]
    for body in bodies:
        assert put(theirs, run_id, body).status_code == 404
    assert mark_values(owner, run_id) == before
    assert count(owner, REVIEWS) == 1
    assert review_audit(owner) == []  # 고침만 — 감사 줄 0


def test_app_role_can_update_the_edit_columns_but_not_delete(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = owner_done_run(owner, a)
    assert put(session("tenant-a", "edk-user-1"), run_id, ADOPT_ONE).status_code == 200
    assert (
        denied(
            f"UPDATE {MARKS} SET edited_level = 'Mid', level_edited_at = now(), level_edited_by_user_id = 7, "
            "edited_reason_bullets = '[\"지은 사유\"]'::jsonb, reasons_edited_at = now(), "
            "reasons_edited_by_user_id = 7, "
            "edited_fix_paragraph = '지은 글', fix_edited_at = now(), fix_edited_by_user_id = 7"
        )
        is None
    )
    row = owner.execute(
        f"SELECT edited_level, edited_fix_paragraph FROM {MARKS} WHERE run_id = %s", [run_id]
    ).fetchone()
    assert row == ("Mid", "지은 글")
    assert denied(f"DELETE FROM {MARKS}") == "42501"  # 분모: 지우기는 그대로 막힘
    assert denied(f"UPDATE {MARKS} SET edited_level = 'high'") == "23514"  # CHECK(앱 역할에도)


def test_my_writes_leave_another_companys_row_on_the_same_item(owner: Owner, companies: tuple[int, int]) -> None:
    """run_id 는 외래 키가 아니라 B 의 검토·표시 행을 A 의 실행 id 로 손으로 심을 수 있다(주인 역할). A 의 세션이 같은
    itemIndex 에 표시·고침을 넣고(INSERT) 바꾸면(UPDATE) B 의 행은 값 그대로 — 쓰기의 회사 조건(services)."""
    a, b = companies
    run_id = owner_done_run(owner, a)
    owner.execute(
        f"INSERT INTO {REVIEWS} (created_at, updated_at, company_id, run_id, state) "
        "VALUES (now(), now(), %s, %s, 'in_review')",
        [b, run_id],
    )
    owner.execute(
        f"INSERT INTO {MARKS} (created_at, updated_at, company_id, run_id, item_index, decision, exclude_reason) "
        "VALUES (now(), now(), %s, %s, 1, 'excluded', 'B 의 사유')",
        [b, run_id],
    )
    theirs = [row for row in mark_values(owner, run_id) if row[0] == b]
    mine = session("tenant-a", "edk-user-1")
    assert put(mine, run_id, EDIT_ONE).status_code == 200  # INSERT
    changed: dict[str, Any] = {
        "marks": [{"itemIndex": 1, "decision": "adopted", "excludeReason": None}],
        "edits": [{"itemIndex": 1, "level": "High", "reasonBullets": None, "fixParagraph": "A 의 글"}],
    }
    assert put(mine, run_id, changed).status_code == 200  # UPDATE
    assert [row for row in mark_values(owner, run_id) if row[0] == b] == theirs
    assert [(row[0], row[2], row[4]) for row in mark_values(owner, run_id) if row[0] == a] == [(a, "adopted", "High")]
