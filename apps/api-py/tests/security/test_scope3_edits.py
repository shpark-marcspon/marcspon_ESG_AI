"""Scope 3 줄 덧판(S3K2b-1 — 결정 MARC-ENT-570·469 4, 테스트 6d 허락)의 보안 층. 앱 역할, 진짜 커밋.

사건 표(inventory_scope3_row_edits)는 회사 칸 표다(conftest 의 tenant_tables 에 저절로 든다). 경로 다섯
(scope3_edit_paths)은 회사 행인 실행 id 를 경로에 받는다. 여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 메서드마다 — 양성 대조(A 가 제 실행으로 2xx, 쓰기는 유효한 본문) · B 의 실행 id 404 · 다른 모듈 실행 404 · 없는 id
     404, 셋이 같은 바이트 · 거절 때 쓰기 0(사건 표·상태 표)
  ⓐ-2 운영 관리자는 작업 회사(A)에만 — 메서드마다 B 의 실행 id 404 · 쓰기 0 · A 양성 200
  ⓑ 읽기: 응답 글자에 B 의 사건·사유 0(A·B 가 같은 rowId 를 가져도) · 사건은 고친 회사에만
  ⓒ 불변: 앱 역할은 사건을 고치지도 지우지도 못한다(42501) · 칸 단위 UPDATE 0 · 칸 수 분모 · INSERT 양성
시험마다 B 의 행이 실제로 있음을 첫 단언으로 둔다(분모). 401·444·400 은 test_tenant_paths 의 분류가 잰다.
실행 행은 주인 역할로 심는다(실행기 0). 이름·값은 지어낸 것이다.
"""

import json
from collections.abc import Callable
from typing import Any, Final

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client
from django.urls import get_resolver

from esgapi.core.auth import bearer as bearer_module
from tests.security.test_operator_company import customer_client, operator_client
from tests.security.test_scope3_state import done_body, owner_run

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
ROOT: Final = "/api/inventory/scope3/runs"
TABLE: Final = "inventory_scope3_row_edits"
STATES: Final = "inventory_scope3_categories"
ROW: Final = "가상_C4!20"
BODY: Final = {"rowIds": [ROW], "reason": "가상 사유"}
SECRET: Final = "나 회사 가상 사유"


def post(url: str) -> Callable[[Client, int], Any]:
    return lambda client, run: client.post(f"{ROOT}/{run}/{url}", data=BODY, content_type="application/json")


def get(url: str) -> Callable[[Client, int], Any]:
    return lambda client, run: client.get(f"{ROOT}/{run}/{url}")


METHODS: Final = {
    "exclude": post("categories/C4/exclusions"),
    "restore": post("categories/C4/restorations"),
    "edits": get("edits"),
    "history": get("history"),
}


def owner_event(owner: Owner, company_id: int, run_id: int, reason: str) -> None:
    owner.execute(
        f"INSERT INTO {TABLE} (company_id, run_id, category, row_id, kind, reason, actor_kind, actor_user_id, "
        "created_at) VALUES (%s, %s, 'C4', %s, 'exclude', %s, 'service', 7, now())",
        [company_id, run_id, ROW, reason],
    )


def owner_other_module_run(owner: Owner, company_id: int) -> int:
    row = owner.execute(
        "INSERT INTO run_runs (created_at, updated_at, company_id, document_id, module, flow_id, options, versions, "
        "purpose, status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, NULL, 'greenwash', 'greenwash.check@1', '{\"reportYear\": 2025}', '{}', 'service', "
        "'done', 1, 0, 7) RETURNING id",
        [company_id],
    ).fetchone()
    assert row is not None
    run_id = int(row[0])
    owner.execute(
        "INSERT INTO run_results (created_at, company_id, run_id, position, schema_version, body) "
        "VALUES (now(), %s, %s, 0, 'scope3.colab.result@1', %s::jsonb)",
        [company_id, run_id, json.dumps(done_body("1"), ensure_ascii=False)],
    )
    return run_id


def counts(owner: Owner) -> tuple[Any, ...]:
    edits = owner.execute(f"SELECT count(*) FROM {TABLE}").fetchone()
    states = owner.execute(f"SELECT count(*) FROM {STATES}").fetchone()
    assert edits is not None and states is not None
    return edits[0], states[0]


@pytest.mark.parametrize("method", list(METHODS))
def test_foreign_other_module_and_missing_runs_are_the_same_404(
    owner: Owner, companies: tuple[int, int], method: str
) -> None:
    a, b = companies
    mine = owner_run(owner, a, "1", minutes=0)
    theirs = owner_run(owner, b, "2", minutes=5)
    other = owner_other_module_run(owner, a)
    owner_event(owner, b, theirs, SECRET)
    assert counts(owner) == (1, 0)  # 분모: B 의 사건이 있다
    client = customer_client(a, "tenant-a")
    call = METHODS[method]
    foreign = call(client, theirs)
    assert foreign.status_code == 404, foreign.content.decode()
    assert foreign.json()["error"]["code"] == "NOT_FOUND"
    assert foreign.content == call(client, other).content == call(client, theirs + 1_000_000).content
    assert counts(owner) == (1, 0)  # 거절 때 쓰기 0(사건·상태 행)
    positive = call(client, mine)  # 양성 대조: 제 실행은 지난다
    assert positive.status_code == 200, positive.content.decode()


@pytest.mark.parametrize("method", list(METHODS))
def test_an_operator_reaches_only_the_working_company(
    owner: Owner, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    """운영 관리자의 회사는 작업 회사(A)다 — 경로의 B 실행 id 로 B 에 닿지 않는다. 회사가 둘이라 작업 회사를 꽂아 잰다
    (회사 둘의 400 은 test_tenant_paths 의 고리). 업무 층은 주인 역할이라 못 재는 자리(검증 ① B2)."""
    a, b = companies
    mine = owner_run(owner, a, "1", minutes=0)
    theirs = owner_run(owner, b, "2", minutes=5)
    owner_event(owner, b, theirs, SECRET)
    assert counts(owner) == (1, 0)  # 분모: B 의 실행·사건이 있다
    operator, _ = operator_client(owner)
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: a)
    call = METHODS[method]
    foreign = call(operator, theirs)
    assert foreign.status_code == 404, foreign.content.decode()
    assert foreign.json()["error"]["code"] == "NOT_FOUND"
    assert foreign.content == call(operator, theirs + 1_000_000).content
    assert SECRET not in foreign.content.decode()
    assert counts(owner) == (1, 0)  # 거절 때 쓰기 0
    positive = call(operator, mine)  # 양성 대조: 작업 회사의 실행은 지난다
    assert positive.status_code == 200, positive.content.decode()


def test_events_stay_in_the_company_that_wrote_them(owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    mine = owner_run(owner, a, "1", minutes=0)
    theirs = owner_run(owner, b, "2", minutes=5)
    owner_event(owner, b, theirs, SECRET)
    client = customer_client(a, "tenant-a")
    assert METHODS["exclude"](client, mine).status_code == 200
    rows = owner.execute(f"SELECT company_id, run_id FROM {TABLE} ORDER BY id").fetchall()
    assert rows == [(b, theirs), (a, mine)]
    history = METHODS["history"](client, mine)
    edits = METHODS["edits"](client, mine)
    assert history.json()["count"] == 1
    assert len(edits.json()["rows"]) == 1
    for response in (history, edits):
        assert SECRET not in response.content.decode()
        assert f'"{theirs}"' not in response.content.decode()


def test_a_same_numbered_event_of_b_does_not_reach_a(owner: Owner, companies: tuple[int, int]) -> None:
    """B 의 회사 칸으로 A 의 실행 id 를 적은 사건도 A 에겐 없다 — 조회는 실행 id 만이 아니라 회사로 거른다."""
    a, b = companies
    mine = owner_run(owner, a, "1", minutes=0)
    owner_event(owner, b, mine, SECRET)
    assert counts(owner) == (1, 0)  # 분모
    client = customer_client(a, "tenant-a")
    assert METHODS["edits"](client, mine).json()["rows"] == []
    assert METHODS["history"](client, mine).json()["count"] == 0
    year = client.get("/api/inventory/scope3/years/2025").json()
    (c4,) = [line for line in year["categories"] if line["category"] == "C4"]
    assert c4["current"]["total"] == "1"  # B 의 사건이 A 의 합을 건드리지 않는다


def denied(statement: str, params: list[Any]) -> str | None:
    """앱 역할(Django 연결)로 돌린 문의 SQLSTATE(되면 None)."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement, params)
    except DatabaseError as error:
        return getattr(error.__cause__, "sqlstate", None)
    return None


def test_the_app_role_can_only_add_events(owner: Owner, companies: tuple[int, int]) -> None:
    a, _ = companies
    run = owner_run(owner, a, "1", minutes=0)
    owner_event(owner, a, run, "가상 사유")
    columns = owner.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        [TABLE],
    ).fetchall()
    # 분모: id·회사·실행·카테고리·줄·kind·사유·actor 둘·때·묶음 — 칸이 늘면 빨강(권한을 다시 본다)
    # S3K2b-2 +12: factor_choice·factor_rank·factor_title·factor_value·factor_source·factor_unit·co2e·biogenic_co2e·
    #   ai_factor_title·ai_factor_value·ai_factor_source·ai_co2e
    assert len(columns) == 11 + 12
    rows = owner.execute(
        "SELECT attname, has_column_privilege('esg_app', %s, attname, 'UPDATE') FROM pg_attribute "
        "WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped ORDER BY attnum",
        [TABLE, TABLE],
    ).fetchall()
    assert {name for name, updatable in rows if updatable} == set()  # 칸 단위 UPDATE 0
    assert denied(f"UPDATE {TABLE} SET reason = '가상 고침' WHERE company_id = %s", [a]) == "42501"
    assert denied(f"UPDATE {TABLE} SET kind = 'restore' WHERE company_id = %s", [a]) == "42501"
    assert denied(f"DELETE FROM {TABLE} WHERE company_id = %s", [a]) == "42501"
    assert counts(owner)[0] == 1
    # 양성 대조: 제품 길의 INSERT 는 된다
    assert METHODS["restore"](customer_client(a, "tenant-a"), run).status_code == 200
    assert counts(owner)[0] == 2


# ── 계수 수정(S3K2b-2 — 6d 조건 ②: 양성 대조 + 404 같은 바이트 + 거절 때 쓰기 0, 사건·상태·실행 표 셋 다) ──

FACTOR_BODY: Final = {
    "rowId": ROW,
    "choice": "custom",
    "rank": None,
    "custom": {"title": "가상 계수", "value": "2.0", "source": "가상 출처"},
    "reason": "가상 사유",
}


def factor(client: Client, run: int, category: str = "C4") -> Any:
    url = f"{ROOT}/{run}/categories/{category}/factors"
    return client.post(url, data=FACTOR_BODY, content_type="application/json")


def editable_run(owner: Owner, company_id: int, minutes: int) -> int:
    """고칠 수 있는 줄 하나를 품은 실행(지어낸 구매 꼴)."""
    run = owner_run(owner, company_id, "1", minutes=minutes)
    line = {
        "rowId": ROW,
        "kind": "purchase",
        "amount": "1000.0",
        "factor": {"title": "가상", "value": "1.0", "unit": "kgCO2e/KRW", "column": "가상 열"},
        "co2e": "1.0",
    }
    body = done_body("1")
    body["sheets"][0]["rows"] = [line]
    owner.execute(
        "UPDATE run_results SET body = %s::jsonb WHERE run_id = %s", [json.dumps(body, ensure_ascii=False), run]
    )
    return run


def all_counts(owner: Owner) -> tuple[Any, ...]:
    runs = owner.execute("SELECT count(*) FROM run_runs").fetchone()
    assert runs is not None
    return (*counts(owner), runs[0])


def test_a_factor_post_is_404_alike_for_others_and_writes_nothing(owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    mine = editable_run(owner, a, 0)
    theirs = editable_run(owner, b, 5)
    other = owner_other_module_run(owner, a)
    client = customer_client(a, "tenant-a")
    before = all_counts(owner)
    answers = [factor(client, theirs), factor(client, other), factor(client, 999_999), factor(client, mine, "C10")]
    assert {response.status_code for response in answers} == {404}
    assert len({response.content for response in answers}) == 1
    assert all_counts(owner) == before  # 거절 때 쓰기 0
    positive = factor(client, mine)
    assert positive.status_code == 200, positive.content.decode()
    assert all_counts(owner)[0] == before[0] + 1  # 양성 대조: 같은 길이 A 의 실행에는 쓴다


def test_a_row_id_longer_than_the_column_is_a_422_and_writes_nothing(owner: Owner, companies: tuple[int, int]) -> None:
    """rowId 는 스키마 상한이 없다 — 칸(64자)보다 길어도 줄 판정이 쓰기 앞에서 422 로 막는다(500 아님)."""
    a, _ = companies
    mine = editable_run(owner, a, 0)
    client = customer_client(a, "tenant-a")
    before = all_counts(owner)
    url = f"{ROOT}/{mine}/categories/C4/factors"
    response = client.post(url, data=FACTOR_BODY | {"rowId": "가" * 65}, content_type="application/json")
    assert response.status_code == 422, response.content.decode()
    assert list(response.json()["error"]["fields"]) == ["rowId"]
    assert all_counts(owner) == before


def test_the_operator_edits_factors_only_in_the_working_company(
    owner: Owner, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = companies
    mine = editable_run(owner, a, 0)
    theirs = editable_run(owner, b, 5)
    client, _ = operator_client(owner)
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: a)
    before = all_counts(owner)
    assert factor(client, theirs).status_code == 404
    assert all_counts(owner) == before
    assert factor(client, mine).status_code == 200


def test_the_app_role_cannot_rewrite_a_factor_event(owner: Owner, companies: tuple[int, int]) -> None:
    a = companies[0]
    run = editable_run(owner, a, 0)
    assert factor(customer_client(a, "tenant-a"), run).status_code == 200
    with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"UPDATE {TABLE} SET co2e = '0.0'")
    assert getattr(caught.value.__cause__, "sqlstate", None) == "42501"
