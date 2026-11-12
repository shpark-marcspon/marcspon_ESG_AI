"""Scope 1·2 입력(S12a — 결정 MARC-ENT-463·469 2·4, 테스트 6d 허락 H11 (아)(자)(타))의 보안 층. 앱 역할, 진짜 커밋.

입력 행·값·히스토리(inventory_entry_rows·values·history)는 회사 칸 표다(conftest 의 tenant_tables 에 저절로 든다).
여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 회사 둘이 같은 풀 잎을 고르고 같은 코드 자산/시설에 값을 넣어도 A 의 상세·리스트·히스토리는 A 의 것만 —
     응답 글자에 B 의 회사 이름·서브도메인·사업장 이름·행 id 가 0
  ⓑ (아) 경로가 회사 행 id({site_id}·{row_id})를 받는 entry_paths 마다 B 의 id 로 A 경로 → 404(대상 표는
     test_tenant_paths 의 분류에서 뽑는다 — 새 경로가 빠질 수 없다) · 본문의 회사 행 id(rows[].rowId·siteFacilityId·
     ids[])에 B 의 것 → 422·404 — 어느 쪽이든 B 의 행·값·히스토리 그대로(주인 연결로 셈)
  ⓒ A 의 저장·지움은 A 에만 든다
  ⓓ 앱 역할은 히스토리를 고치거나 지우지 못하고(42501), 행·값을 지우지 못한다(지우기는 삭제 표시)
  ⓔ (자)(타) 잠금 풀기(OPERATOR_COMPANY_OPERATIONS — 회사 경로의 운영 관리자 칸): 고객사 Bearer 403 · 고객사 사용자는
     제 회사에서도 403(잠금 그대로) · 운영 관리자는 회사 하나면 지나 풂(200) · 회사 둘이면 400 company_ambiguous.
     test_tenant_paths·test_operator_company 의 고리에서 이 소속으로 뺀 것이 재던 것을 여기서 다시 잰다.
  ⓕ (④ — sid:MARC-ISSUE-418) 조직구조 쪽 사용 중: A 의 쓰이는 사업장 지움·쓰이는 자산/시설 코드 바꿈은 409 in_use 이고
     그 응답 글자에 B 의 이름·사업장·자산/시설·id 0 · B 의 행은 A 의 사업장 지움을 막지 않는다(판정은 회사 조건).
  ⓖ (S12a-2 — 테스트 6d 허락 H11) 입력주기·행 계수 바꿈·히스토리 복구: B 의 site_id·row_id·history_id(B 의 직접입력을
     가리키는 factor 줄 포함)로 A 경로 404·B 0 바뀜 · A 응답에 B 이름·id 0 · 앱 역할은 직접입력 계수를 고치거나
     지우지 못하고 입력주기를 지우지 못한다(42501) · (e7 조건) 고객사 Bearer 로 factor 줄 복구 403 · 행·히스토리 0 바뀜.
     행 계수 바꿈은 운영 관리자 칸(OPERATOR_COMPANY_OPERATIONS)이라 회사 둘이면 늘 400 — 회사 둘 격리를 재는 자리에서만
     그 칸을 COMPANY 로 내려(monkeypatch — 경로 첫 문장과 action 첫 문장이 같은 표를 읽는다) 고객사 Bearer 로 보낸다.
시험마다 B 의 행이 실제로 있음을 첫 단언으로 둔다(분모 — 셈이 0 이면 격리 단언이 빈 채 초록이 된다, 6d 덧붙임).
(401·444·400 은 test_tenant_paths 의 entry_paths 분류가 다른 회사 경로와 같이 잰다 — AUTHENTICATED 에 든다.)
★ 공통 표(풀 넷·코드 목록)는 tenant_tables 밖이라 owner 고정물이 비우지 않는다 — 앞뒤로 비운다.
이름·값은 지어낸 것이다(셈: 계수 1 kg/kg · CO2 GWP 1 — 1000 kg 이면 1 tCO2-eq).
"""

from collections.abc import Iterator
from typing import Any, Final

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client

from esgapi.core.permissions import COMPANY, OPERATION_POLICY
from tests.security.seed import add_company
from tests.security.test_ghg_pool import CODES, POOL, one, seed
from tests.security.test_operator_company import customer_client, operator_client
from tests.security.test_tenant_paths import OPERATIONS, OPERATOR_COMPANY_OPERATIONS, openapi, operations

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
YEAR: Final = 2025
ROOT: Final = "/api/inventory/scope12"
B_SITE: Final = "나 회사의 남쪽 공장"
B_DETAIL: Final = "나 회사 3호기"
ENTRY_TABLES: Final = ("inventory_entry_rows", "inventory_entry_values", "inventory_entry_history")
ROW_FACTOR: Final = "inventory_scope12_row_factor_save"
B_CUSTOM: Final = "나 회사 직접 계수"


@pytest.fixture(autouse=True)
def empty_pool(owner: Owner) -> Iterator[None]:
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")
    yield
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")


def index_url(leaf: int) -> str:
    return f"{ROOT}/years/{YEAR}/indexes/{leaf}"


def place(
    owner: Owner, client: Client, company_id: int, code_id: int, leaf: int, site: str, detail: str
) -> dict[str, int]:
    """그 회사의 사업장 하나·자산/시설 하나 → 잎 고름(경로) → 1월 1000 kg 저장(경로). 사업장·자산/시설·행 id."""
    site_id = one(
        owner,
        "INSERT INTO sites (company_id, name, inventory_enabled, created_at) VALUES (%s, %s, true, now()) RETURNING id",
        [company_id, site],
    )
    facility_id = one(
        owner,
        "INSERT INTO site_facilities (company_id, site_id, facility_code_id, detail_name, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, now(), now()) RETURNING id",
        [company_id, site_id, code_id, detail],
    )
    chose = client.put(
        f"{ROOT}/index-selections/{YEAR}", data={"facilityNodeIds": [leaf]}, content_type="application/json"
    )
    assert chose.status_code == 200, chose.content.decode()
    saved = save(client, leaf, site_id, [row(facility_id, "1000")])
    assert saved.status_code == 200, saved.content.decode()
    row_id = int(saved.json()["sites"][0]["rows"][0]["rowId"])
    return {"site": site_id, "facility": facility_id, "row": row_id}


def row(facility_id: int, amount: str | None, row_id: int | None = None, slot: str = f"{YEAR}-01") -> dict[str, Any]:
    line: dict[str, Any] = {
        "siteFacilityId": facility_id,
        "unit": "kg",
        "values": [{"slot": slot, "amount": amount, "estimated": False}],
    }
    if row_id is not None:
        line["rowId"] = row_id
    return line


def save(client: Client, leaf: int, site_id: int, rows: list[dict[str, Any]]) -> Any:
    return client.put(f"{index_url(leaf)}/sites/{site_id}/rows", data={"rows": rows}, content_type="application/json")


def entries_of(owner: Owner, company_id: int) -> list[list[tuple[Any, ...]]]:
    """그 회사의 입력 행·값·히스토리 전부(주인 연결 — 격리 단언의 전·후)."""
    return [
        owner.execute(
            "SELECT id, selection_id, site_facility_id, unit, na, emission, deleted_at IS NULL "
            "FROM inventory_entry_rows WHERE company_id = %s ORDER BY id",
            [company_id],
        ).fetchall(),
        owner.execute(
            "SELECT id, row_id, slot, amount, estimated FROM inventory_entry_values WHERE company_id = %s ORDER BY id",
            [company_id],
        ).fetchall(),
        owner.execute(
            "SELECT id, row_id, kind, slot, before, after FROM inventory_entry_history WHERE company_id = %s "
            "ORDER BY id",
            [company_id],
        ).fetchall(),
    ]


@pytest.fixture
def both(owner: Owner, companies: tuple[int, int]) -> dict[str, Any]:
    """같은 풀 잎·같은 코드 — A 에 사업장 하나(1000 kg), B 에 사업장 하나(1000 kg)."""
    a, b = companies
    ids = seed(owner)
    mine = place(owner, customer_client(a, "tenant-a"), a, ids["code"], ids["leaf"], "가 회사의 공장", "가 1호기")
    theirs = place(owner, customer_client(b, "tenant-b"), b, ids["code"], ids["leaf"], B_SITE, B_DETAIL)
    return {**ids, "a": mine, "b": theirs}


def b_words(owner: Owner, b: int) -> tuple[str, ...]:
    names = owner.execute("SELECT name, subdomain FROM company WHERE id = %s", [b]).fetchone()
    assert names is not None
    return (*names, B_SITE, B_DETAIL, "companyId")


# ── ⓐ 읽기 ──


def test_detail_list_and_history_carry_only_my_company(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모: B 의 행·값·히스토리(value 한 줄)가 있다
    client = customer_client(a, "tenant-a")
    leaf = both["leaf"]
    detail = client.get(index_url(leaf))
    listed = client.get(f"{ROOT}/rows?year={YEAR}")
    history = client.get(f"{index_url(leaf)}/rows/{both['a']['row']}/history")
    for response in (detail, listed, history):
        assert response.status_code == 200, response.content.decode()
        text = response.content.decode()
        for word in b_words(owner, b):
            assert word not in text, word
    body = detail.json()
    assert [site["siteId"] for site in body["sites"]] == [str(both["a"]["site"])]  # A 의 사업장 하나
    assert [r["rowId"] for r in body["sites"][0]["rows"]] == [str(both["a"]["row"])]
    assert body["totals"]["all"][str(YEAR)] == "1"  # A 의 1000 kg 만(B 의 1 t 를 더하지 않았다)
    assert listed.json()["scopes"][0]["rows"][0]["values"][str(YEAR)] == "1"
    assert history.json()["count"] == 1
    assert entries_of(owner, b) == theirs


# ── ⓑ 경로·본문의 회사 행 id ──


def row_id_paths() -> list[tuple[str, str]]:
    """entry_paths 가운데 경로가 회사 행 id({site_id}·{row_id})를 받는 것 — 분류에서 뽑는다(새 경로가 빠지지 않게)."""
    return sorted(
        key
        for key, kind in OPERATIONS.items()
        if kind == "entry_paths" and ("{site_id}" in key[1] or "{row_id}" in key[1])
    )


def test_the_targets_come_from_the_entry_paths() -> None:
    found = operations(openapi())
    names = sorted(found[key]["operationId"] for key in row_id_paths())
    assert len(names) == 5  # 분모: 입력 저장({site_id})·히스토리({row_id})
    # · S12a-2 +3: 입력주기({site_id})·행 계수 바꿈({row_id})·복구({row_id}·{history_id})
    assert names == [
        "inventory_scope12_history_restore",
        "inventory_scope12_period_save",
        "inventory_scope12_row_factor_save",
        "inventory_scope12_row_history",
        "inventory_scope12_rows_save",
    ]


# S12a 의 둘(입력 저장·히스토리) — 위 시험이 그대로 잰다. 나머지(S12a-2 셋)는 아래 시험이 그 본문으로 잰다(둘을 합치면
# row_id_paths 전부 — 새 경로가 빠질 수 없다).
S12A_ROW_PATHS: Final = frozenset(
    {
        ("PUT", "/inventory/scope12/years/{year}/indexes/{node_id}/sites/{site_id}/rows"),
        ("GET", "/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/history"),
    }
)


def test_the_two_row_path_tests_cover_every_row_path() -> None:
    """아래 두 매개변수 시험(S12a 둘 · S12a-2 셋)이 row_id_paths() 를 빠짐·겹침 없이 나눈다 — 옛 경로 이름이 바뀌어
    옛 시험의 매개변수가 0 이 돼 넘어가는 것을 막는다(테스트 6d 조건, 10-30)."""
    every = set(row_id_paths())
    old = {key for key in every if key in S12A_ROW_PATHS}
    new = {key for key in every if key not in S12A_ROW_PATHS}
    assert old | new == every
    assert every >= S12A_ROW_PATHS
    assert len(S12A_ROW_PATHS) == 2


def history_ids(owner: Owner, row_id: int) -> list[int]:
    return [
        line
        for (line,) in owner.execute("SELECT id FROM inventory_entry_history WHERE row_id = %s ORDER BY id", [row_id])
    ]


def send_row_path(client: Client, method: str, url: str, op: str, mine: dict[str, int], factor: int) -> Any:
    """row_id_paths 의 한 경로를 그 동작의 바른 본문으로(본문의 id 는 늘 A 의 것 — 경로의 id 만 바꿔 잰다)."""
    if method == "GET":
        return client.get(url)
    body: dict[str, Any] = {
        "inventory_scope12_rows_save": {"rows": [row(mine["facility"], "5", mine["row"])]},
        "inventory_scope12_period_save": {"period": "quarter"},
        "inventory_scope12_row_factor_save": {"factorId": factor, "reason": "가 사유"},
        "inventory_scope12_history_restore": {},
    }[op]
    return getattr(client, method.lower())(url, data=body, content_type="application/json")


@pytest.mark.parametrize(
    "operation", [key for key in row_id_paths() if key in S12A_ROW_PATHS], ids=lambda key: f"{key[0]} {key[1]}"
)
def test_another_companys_row_id_on_my_path_is_not_found(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any], operation: tuple[str, str]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모
    method, path = operation
    client = customer_client(a, "tenant-a")
    url = "/api" + path.replace("{year}", str(YEAR)).replace("{node_id}", str(both["leaf"]))
    url = url.replace("{site_id}", str(both["b"]["site"])).replace("{row_id}", str(both["b"]["row"]))
    if method == "GET":
        response = client.get(url)
    else:  # 입력 저장 — 본문은 A 의 바른 줄(B 의 사업장 id 만 경로에)
        response = client.put(url, data={"rows": [row(both["a"]["facility"], "5")]}, content_type="application/json")
    assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND"), response.content.decode()
    assert entries_of(owner, b) == theirs
    # 짝: 같은 경로에 A 의 id 면 지난다(404 가 경로 꼴 탓이 아니다)
    mine = url.replace(f"/sites/{both['b']['site']}/", f"/sites/{both['a']['site']}/").replace(
        f"/rows/{both['b']['row']}/", f"/rows/{both['a']['row']}/"
    )
    again = (
        client.get(mine)
        if method == "GET"
        else client.put(
            mine, data={"rows": [row(both["a"]["facility"], "5", both["a"]["row"])]}, content_type="application/json"
        )
    )
    assert again.status_code == 200, again.content.decode()


@pytest.mark.parametrize(
    "operation", [key for key in row_id_paths() if key not in S12A_ROW_PATHS], ids=lambda key: f"{key[0]} {key[1]}"
)
def test_another_companys_ids_on_the_s12a_2_paths_are_not_found(
    owner: Owner,
    companies: tuple[int, int],
    both: dict[str, Any],
    operation: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모
    method, path = operation
    op = operations(openapi())[operation]["operationId"]
    if op in OPERATOR_COMPANY_OPERATIONS:  # 회사 둘이면 운영 관리자는 400 — 칸을 내려 고객사 Bearer 로 격리를 잰다
        monkeypatch.setitem(OPERATION_POLICY, op, COMPANY)
    client = customer_client(a, "tenant-a")
    mine = both["a"]
    # 짝(복구)에 쓸 A 의 둘째 줄 — 맨 위 줄은 복구하지 않는다
    assert save(client, both["leaf"], mine["site"], [row(mine["facility"], "4", mine["row"])]).status_code == 200
    mine_history = history_ids(owner, mine["row"])[0]
    their_history = history_ids(owner, both["b"]["row"])[0]
    theirs = entries_of(owner, b)
    url = "/api" + path.replace("{year}", str(YEAR)).replace("{node_id}", str(both["leaf"]))
    their_url = (
        url.replace("{site_id}", str(both["b"]["site"]))
        .replace("{row_id}", str(both["b"]["row"]))
        .replace("{history_id}", str(their_history))
    )
    response = send_row_path(client, method, their_url, op, mine, both["factor"])
    assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND"), response.content.decode()
    assert entries_of(owner, b) == theirs
    # 짝: 같은 경로에 A 의 id 면 지난다(404 가 경로 꼴 탓이 아니다)
    my_url = (
        url.replace("{site_id}", str(mine["site"]))
        .replace("{row_id}", str(mine["row"]))
        .replace("{history_id}", str(mine_history))
    )
    again = send_row_path(client, method, my_url, op, mine, both["factor"])
    assert again.status_code == 200, again.content.decode()
    text = again.content.decode()
    for word in b_words(owner, b):
        assert word not in text, word
    assert entries_of(owner, b) == theirs


def test_another_companys_ids_in_my_body_are_refused(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    mine = entries_of(owner, a)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모
    client = customer_client(a, "tenant-a")
    leaf, site = both["leaf"], both["a"]["site"]
    by_row = save(client, leaf, site, [row(both["a"]["facility"], "7", both["b"]["row"])])
    by_facility = save(client, leaf, site, [row(both["b"]["facility"], "7")])
    deleted = client.post(
        f"{index_url(leaf)}/rows/delete", data={"ids": [both["b"]["row"]]}, content_type="application/json"
    )
    assert by_row.status_code == 422 and "rows.0.rowId" in by_row.json()["error"]["fields"]
    assert by_facility.status_code == 422 and "rows.0.siteFacilityId" in by_facility.json()["error"]["fields"]
    assert (deleted.status_code, deleted.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert entries_of(owner, b) == theirs
    assert entries_of(owner, a) == mine  # 거절은 A 에도 0 씀


# ── ⓒ 쓰기 ──


def test_my_save_and_delete_land_only_in_my_company(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모
    client = customer_client(a, "tenant-a")
    leaf, mine = both["leaf"], both["a"]
    assert save(client, leaf, mine["site"], [row(mine["facility"], "2000", mine["row"])]).status_code == 200
    gone = client.post(f"{index_url(leaf)}/rows/delete", data={"ids": [mine["row"]]}, content_type="application/json")
    assert gone.json() == {"count": 1}
    assert entries_of(owner, b) == theirs
    a_rows, a_values, a_history = entries_of(owner, a)
    assert [line[-1] for line in a_rows] == [False]  # A 의 행은 삭제 표시(행째 남음)
    assert [line[3] for line in a_values] == [2000]  # 값은 그대로 남는다
    assert [line[2] for line in a_history] == ["value", "value"]
    written = owner.execute(
        "SELECT array_agg(DISTINCT company_id) FROM inventory_entry_history WHERE row_id = %s", [mine["row"]]
    ).fetchone()
    assert written == ([a],)


# ── ⓓ 앱 역할 권한 ──


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE inventory_entry_history SET after = '0' WHERE company_id = %s",
        "DELETE FROM inventory_entry_history WHERE company_id = %s",
        "DELETE FROM inventory_entry_values WHERE company_id = %s",
        "DELETE FROM inventory_entry_rows WHERE company_id = %s",
    ],
)
def test_the_app_role_cannot_rewrite_history_or_delete_entries(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any], statement: str
) -> None:
    _, b = companies
    before = entries_of(owner, b)
    assert [len(part) for part in before] == [1, 1, 1]  # 분모
    with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(statement, [b])  # 문은 위 매개 넷뿐
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error)
    assert cause.sqlstate == "42501"  # insufficient_privilege
    assert entries_of(owner, b) == before


# ── ⓔ 잠금 풀기(운영 관리자 칸의 회사 경로) ──


def locked_at(owner: Owner, company_id: int) -> list[bool]:
    return [
        locked
        for (locked,) in owner.execute(
            "SELECT locked_at IS NOT NULL FROM inventory_index_selections WHERE company_id = %s ORDER BY id",
            [company_id],
        )
    ]


def test_the_unlock_group_is_this_one() -> None:
    found = operations(openapi())
    entry_names = {found[key]["operationId"] for key, kind in OPERATIONS.items() if kind == "entry_paths"}
    assert len(entry_names) == 17  # 분모: entry_paths 열
    # · S12a-2 +3: 입력주기·행 계수 바꿈·복구
    # · S12a-3 +1: 대시보드
    # · S12b-1 +2: 엑셀 내려받기 둘
    assert entry_names >= OPERATOR_COMPANY_OPERATIONS - {"inventory_scope3_unlock"}  # 소속은 entry_paths 안
    # S3K2a: 빼낸 몫(Scope 3 카테고리 잠금 풀기)은 scope3_state_paths 안(tests/security/test_scope3_state.py)
    state_names = {found[key]["operationId"] for key, kind in OPERATIONS.items() if kind == "scope3_state_paths"}
    assert "inventory_scope3_unlock" in state_names
    # · S3K2a +1
    assert len(OPERATOR_COMPANY_OPERATIONS) == 3
    # · S12a-2 +1: 행 계수 바꿈
    # · S3K2a +1: Scope 3 카테고리 잠금 풀기(소속은 scope3_state_paths — tests/security/test_scope3_state.py)


def test_a_customer_cannot_unlock_even_in_the_own_company(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    assert [len(part) for part in entries_of(owner, b)] == [1, 1, 1]  # 분모
    client = customer_client(a, "tenant-a")
    lock = f"{index_url(both['leaf'])}/lock"
    assert client.post(lock).json()["locked"] is True  # 고객사 사용자는 잠근다
    assert locked_at(owner, a) == [True]
    refused = client.delete(lock)  # 고객사 Bearer — 제 회사의 잠금도 못 푼다
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN")
    assert locked_at(owner, a) == [True]
    blocked = save(client, both["leaf"], both["a"]["site"], [row(both["a"]["facility"], "9", both["a"]["row"])])
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (409, "LOCKED")  # 잠긴 동안 쓰기 409


def test_an_operator_with_two_companies_cannot_choose_whom_to_unlock(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    assert [len(part) for part in entries_of(owner, b)] == [1, 1, 1]  # 분모
    lock = f"{index_url(both['leaf'])}/lock"
    for company_id, subdomain in ((a, "tenant-a"), (b, "tenant-b")):
        assert customer_client(company_id, subdomain).post(lock).status_code == 200
    operator, _ = operator_client(owner)
    response = operator.delete(lock)  # 권한은 지나고 작업 회사를 고르다 멈춘다
    assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
    assert (locked_at(owner, a), locked_at(owner, b)) == ([True], [True])


@pytest.fixture
def solo(owner: Owner) -> int:
    """회사 하나(활성, subdomain tenant-a). 운영 관리자의 작업 회사가 그것 하나로 정해진다."""
    return add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")


def test_an_operator_unlocks_in_the_sole_company(owner: Owner, solo: int) -> None:
    ids = seed(owner)
    customer = customer_client(solo, "tenant-a")
    mine = place(owner, customer, solo, ids["code"], ids["leaf"], "가 회사의 공장", "가 1호기")
    assert [len(part) for part in entries_of(owner, solo)] == [1, 1, 1]  # 분모: 그 회사의 행이 있다
    lock = f"{index_url(ids['leaf'])}/lock"
    assert customer.post(lock).status_code == 200
    operator, _ = operator_client(owner)
    response = operator.delete(lock)
    assert response.status_code == 200, response.content.decode()
    assert (response.json()["locked"], response.json()["lockedBy"]) == (False, None)
    assert locked_at(owner, solo) == [False]
    again = save(customer, ids["leaf"], mine["site"], [row(mine["facility"], "3", mine["row"])])
    assert again.status_code == 200  # 풀린 뒤 고객사 사용자가 다시 쓴다


# ── ⓕ 조직구조 쪽 사용 중(④) ──


def test_my_in_use_refusals_carry_nothing_of_the_other_company(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모
    client = customer_client(a, "tenant-a")
    mine = both["a"]
    other_code = one(
        owner,
        "INSERT INTO organization_facility_codes (code, name, sort_order, created_at, updated_at) "
        "VALUES (NULL, %s, 1, now(), now()) RETURNING id",
        ["가 버너"],
    )
    refusals = [
        client.post("/api/branches/delete", data={"ids": [mine["site"]]}, content_type="application/json"),
        client.put(
            f"/api/branches/{mine['site']}",
            data={
                "name": "가 회사의 공장",
                "inventoryEnabled": True,
                "facilities": [{"id": mine["facility"], "facilityCodeId": other_code, "detailName": "가 1호기"}],
                "updatedAt": client.get(f"/api/branches/{mine['site']}").json()["updatedAt"],  # 지금 판(K1b-3)
            },
            content_type="application/json",
        ),
    ]
    their_ids = {str(both["b"][key]) for key in ("site", "facility", "row")} - {
        str(mine[key]) for key in ("site", "facility", "row")
    }
    for found in refusals:
        assert found.status_code == 409, found.content.decode()
        assert found.json()["error"]["code"] == "IN_USE"
        text = found.content.decode()
        for word in (*b_words(owner, b), *(f'"{value}"' for value in their_ids)):
            assert word not in text, (word, text)
    assert entries_of(owner, b) == theirs


def test_another_companys_rows_do_not_keep_my_site(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모: B 의 같은 코드 행이 살아 있다
    client = customer_client(a, "tenant-a")
    mine = both["a"]
    gone = client.post(
        f"{index_url(both['leaf'])}/rows/delete", data={"ids": [mine["row"]]}, content_type="application/json"
    )
    assert gone.json() == {"count": 1}
    dropped = client.post("/api/branches/delete", data={"ids": [mine["site"]]}, content_type="application/json")
    assert dropped.status_code == 200 and dropped.json() == {"count": 1}, dropped.content.decode()
    assert entries_of(owner, b) == theirs
    alive = owner.execute("SELECT deleted_at IS NULL FROM sites WHERE id = %s", [both["b"]["site"]]).fetchone()
    assert alive == (True,)


# ── ⓖ 입력주기·행 계수 바꿈·히스토리 복구(S12a-2) ──


CUSTOM_BODY: Final[dict[str, Any]] = {
    "name": B_CUSTOM,
    "source": "지어낸 출처",
    "baseYear": 2024,
    "tier": 1,
    "countryCode": "KR",
    "industryCode": "other",
    "inputUnit": {"kind": "mass", "unit": "kg"},
    "gases": [{"gas": "CO2", "enabled": True, "factor": "2", "gwp": "1"}],
}


def customs_of(owner: Owner, company_id: int) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT id, name FROM inventory_custom_factors WHERE company_id = %s ORDER BY id", [company_id]
    ).fetchall()


def factor_line(owner: Owner, row_id: int) -> int:
    found = owner.execute(
        "SELECT id FROM inventory_entry_history WHERE row_id = %s AND kind = 'factor' ORDER BY id", [row_id]
    ).fetchall()
    assert len(found) == 1, found
    return int(found[0][0])


@pytest.fixture
def b_custom(owner: Owner, companies: tuple[int, int], both: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> int:
    """B 의 행에 직접입력 계수(경로 — 칸을 내려 B 의 고객사 Bearer 로) → 값을 한 번 더 저장(factor 줄이 맨 위가 아님).
    B 의 factor 줄 id."""
    _, b = companies
    with monkeypatch.context() as patched:
        patched.setitem(OPERATION_POLICY, ROW_FACTOR, COMPANY)
        client = customer_client(b, "tenant-b")
        changed = client.put(
            f"{index_url(both['leaf'])}/rows/{both['b']['row']}/factor",
            data={"custom": CUSTOM_BODY, "reason": "나 사유"},
            content_type="application/json",
        )
        assert changed.status_code == 200, changed.content.decode()
    resaved = save(client, both["leaf"], both["b"]["site"], [row(both["b"]["facility"], "6", both["b"]["row"])])
    assert resaved.status_code == 200, resaved.content.decode()
    return factor_line(owner, both["b"]["row"])


def test_my_row_with_another_companys_history_line_is_not_found(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any], b_custom: int
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 3]  # 분모: B 의 행·값(1월 1000 → 6)·줄 셋(value·factor·value)
    assert [name for _, name in customs_of(owner, b)] == [B_CUSTOM]  # 분모: B 의 직접입력 하나
    client = customer_client(a, "tenant-a")
    mine = both["a"]
    restore = f"{index_url(both['leaf'])}/rows/{mine['row']}/history"
    for their_line in history_ids(owner, both["b"]["row"]):  # B 의 factor 줄(직접입력을 가리킴) 포함 — 전부
        response = client.post(
            f"{restore}/{their_line}/restore", data={"reason": "가 사유"}, content_type="application/json"
        )
        assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND"), response.content.decode()
    assert entries_of(owner, b) == theirs
    assert [len(part) for part in entries_of(owner, a)] == [1, 1, 1]  # A 에도 0 씀
    for response in (client.get(index_url(both["leaf"])), client.get(restore)):
        assert response.status_code == 200
        text = response.content.decode()
        for word in (*b_words(owner, b), B_CUSTOM):
            assert word not in text, word


def test_a_period_change_lands_only_in_my_company(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any]
) -> None:
    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모
    client = customer_client(a, "tenant-a")
    changed = client.put(
        f"{index_url(both['leaf'])}/sites/{both['a']['site']}/period",
        data={"period": "year"},
        content_type="application/json",
    )
    assert changed.status_code == 200, changed.content.decode()
    assert changed.json()["sites"][0]["period"] == "year"
    assert entries_of(owner, b) == theirs
    periods = owner.execute("SELECT company_id, site_id, period FROM inventory_entry_periods ORDER BY id").fetchall()
    assert periods == [(a, both["a"]["site"], "year")]  # B 의 블록 주기 행 0
    assert [line[2] for line in entries_of(owner, a)[2]] == ["value", "period"]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE inventory_custom_factors SET name = 'x' WHERE company_id = %s",
        "DELETE FROM inventory_custom_factors WHERE company_id = %s",
        "DELETE FROM inventory_entry_periods WHERE company_id = %s",
    ],
)
def test_the_app_role_cannot_rewrite_custom_factors_or_delete_periods(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any], b_custom: int, statement: str
) -> None:
    _, b = companies
    owner.execute(
        "INSERT INTO inventory_entry_periods (company_id, selection_id, site_id, period, created_at, updated_at) "
        "SELECT company_id, selection_id, %s, 'quarter', now(), now() FROM inventory_entry_rows WHERE id = %s",
        [both["b"]["site"], both["b"]["row"]],
    )
    before = (customs_of(owner, b), owner.execute("SELECT id, period FROM inventory_entry_periods").fetchall())
    assert (len(before[0]), len(before[1])) == (1, 1)  # 분모: B 의 직접입력 하나·주기 행 하나
    with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(statement, [b])  # 문은 위 매개 셋뿐
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error)
    assert cause.sqlstate == "42501"  # insufficient_privilege
    assert (customs_of(owner, b), owner.execute("SELECT id, period FROM inventory_entry_periods").fetchall()) == before


def test_a_customer_bearer_cannot_restore_a_factor_line(
    owner: Owner, solo: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(e7 조건) 복구는 COMPANY 칸이지만 factor 줄은 운영 관리자만 — action 안의 판정(ALSO_INSIDE 밖)을 보안 층에서
    잰다."""
    ids = seed(owner)
    customer = customer_client(solo, "tenant-a")
    mine = place(owner, customer, solo, ids["code"], ids["leaf"], "가 회사의 공장", "가 1호기")
    with monkeypatch.context() as patched:  # factor 줄을 만드는 동안만 칸을 내린다
        patched.setitem(OPERATION_POLICY, ROW_FACTOR, COMPANY)
        changed = customer.put(
            f"{index_url(ids['leaf'])}/rows/{mine['row']}/factor",
            data={"custom": CUSTOM_BODY, "reason": "가 사유"},
            content_type="application/json",
        )
        assert changed.status_code == 200, changed.content.decode()
    assert save(customer, ids["leaf"], mine["site"], [row(mine["facility"], "3", mine["row"])]).status_code == 200
    line = factor_line(owner, mine["row"])
    before = entries_of(owner, solo)
    assert [len(part) for part in before] == [1, 1, 3]  # 분모: 줄 셋(value·factor·value) — factor 줄은 맨 위가 아님
    custom_before = owner.execute("SELECT custom_factor_id, factor_version_id FROM inventory_entry_rows").fetchall()
    restore = f"{index_url(ids['leaf'])}/rows/{mine['row']}/history/{line}/restore"
    refused = customer.post(restore, data={"reason": "가 사유"}, content_type="application/json")
    assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN"), refused.content.decode()
    assert entries_of(owner, solo) == before
    assert (
        owner.execute("SELECT custom_factor_id, factor_version_id FROM inventory_entry_rows").fetchall()
        == custom_before
    )
    # 짝: 운영 관리자(작업 회사 = 이 회사 하나)는 같은 요청이 지난다 — 403 이 꼴·경로 탓이 아니다
    operator, _ = operator_client(owner)
    passed = operator.post(restore, data={"reason": "가 사유"}, content_type="application/json")
    assert passed.status_code == 200, passed.content.decode()
    assert passed.json()["sites"][0]["rows"][0]["factor"]["isCustom"] is True  # 뒤 상태 = 지금 상태(0 바뀜)


# ── ⓗ 대시보드(S12a-3 — 테스트 6d 허락 H9 (라)) ──


def test_the_dashboard_carries_only_my_company(
    owner: Owner, companies: tuple[int, int], both: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 의 대시보드에 B 의 사업장 이름·id·배출량 0 · A 의 합은 B 의 행(같은 잎·같은 코드)을 더하지 않는다
    · B 만 있는 해는 아무도 없는 해와 같은 응답 · 운영 관리자가 작업 회사 A 면 A 의 것만."""
    from django.urls import get_resolver

    from esgapi.core.auth import bearer as bearer_module

    a, b = companies
    theirs = entries_of(owner, b)
    assert [len(part) for part in theirs] == [1, 1, 1]  # 분모: B 의 행·값·히스토리가 있다(1000 kg — 1 t)
    chose = customer_client(b, "tenant-b").put(
        f"{ROOT}/index-selections/{YEAR + 1}", data={"facilityNodeIds": [both["leaf"]]}, content_type="application/json"
    )
    assert chose.status_code == 200, chose.content.decode()  # B 에만 있는 해
    assert customer_client(b, "tenant-b").get(f"{ROOT}/dashboard?year={YEAR + 1}").json()["configured"] is True  # 분모
    client = customer_client(a, "tenant-a")
    mine = client.get(f"{ROOT}/dashboard?year={YEAR}")
    assert mine.status_code == 200, mine.content.decode()  # 양성 대조: 제 회사의 해는 값이 있다
    body = mine.json()
    assert (body["configured"], body["total"]["scope12"], body["scopes"][0]["value"]) == (True, "1", "1")  # B 의 1 t 0
    assert [site["siteId"] for site in body["bySite"]] == [str(both["a"]["site"])]
    text = mine.content.decode()
    for word in b_words(owner, b):
        assert word not in text, word
    only_theirs = client.get(f"{ROOT}/dashboard?year={YEAR + 1}").json()
    nobodys = client.get(f"{ROOT}/dashboard?year={YEAR + 9}").json()
    assert only_theirs["configured"] is False
    assert {**only_theirs, "year": 0} == {**nobodys, "year": 0}  # 남의 해 ≡ 없는 해(해 칸 말고 같음)
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: a)
    operator, _ = operator_client(owner)
    seen = operator.get(f"{ROOT}/dashboard?year={YEAR}")
    assert seen.status_code == 200, seen.content.decode()
    assert seen.json() == body
    assert entries_of(owner, b) == theirs
