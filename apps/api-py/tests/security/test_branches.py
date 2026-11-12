"""사업장(/branches)·사업장별 자산/시설·자산/시설 코드 목록(밴드 K1b-1 ③ — 발주서 §3-4)의 경계를 앱 역할로 잰다. 보안 층
(테스트 d9 허락 「가」 — 새 파일).

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 회사 A 의 고객사 사용자가 B 의 사업장 id·자산/시설 id·ids[] 로 읽기·저장·토글·삭제 → 404, B 의 행 그대로(주인
     연결로 셈). 분모: 같은 요청을 A 의 id 로 보내면 지난다. 목록에 B 의 사업장 0
  ⓑ 코드 목록 쓰기 넷(/admin/facility-codes)은 고객사 사용자 Bearer 에 403, 코드 행 그대로. 분모: 운영 관리자는 지난다
  ⓒ 회사 A 가 쓰는 코드를 운영 관리자가 지운 뒤에도 A 의 사업장 상세에 그 코드 글자·이름이 그대로 보이고, 새 선택
     목록(/facility-codes)에서만 빠진다(ce ② 고침 b② — 하드 지우기 0)
  ⓓ 운영 관리자의 작업 회사가 A 면 만든 사업장·자산/시설의 company_id 가 A
  ⓔ 본문의 companyId → 422(만들기·저장), 행 0
  ⓕ 앱 역할은 site_facilities·organization_facility_codes·sites 를 지우지 못한다(42501 — 지우기는 삭제 표시)
  (401 은 tests/security/test_tenant_paths.py 의 test_without_a_session_it_is_401 매개가 잰다)

★ 자산/시설 코드 목록(organization_facility_codes)이 격리 표(회사 칸 표)에서 빠지는 까닭: 모든 고객사가 같이 쓰는
  공통 목록 하나다(결정 MARC-ENT-469 3). 회사 칸이 없고 회사 데이터를 싣지 않으며, 쓰기는 운영 관리자만이고(권한 표),
  코드를 쓰는 회사 행의 셈은 1차에 늘 빈 집합(facility_codes_in_use — 회사 넘는 집계 0, K1b-2a 가 ce 허락으로 채운다).
  그래서 conftest 의 owner 가 비우는 tenant_tables 밖이다 — 이 파일은 시험마다 그 표를 따로 비운다(codes 고정물).
Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(행을 심고 분모를 센다).
★ 뒤 밴드는 함수를 더하기만 한다. 이름·글은 지어낸 것이다.
"""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client

from tests.security.seed import add_company
from tests.security.test_operator_company import customer_client, operator_client

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
CODES = "organization_facility_codes"


@pytest.fixture(autouse=True)
def codes(owner: Owner) -> Iterator[None]:
    """공통 코드 목록은 tenant_tables 밖이라 owner 가 비우지 않는다 — 앞뒤로 비운다(site_facilities 도 CASCADE)."""
    owner.execute(f"TRUNCATE {CODES} CASCADE")
    yield
    owner.execute(f"TRUNCATE {CODES} CASCADE")


def add_code(owner: Owner, name: str) -> int:
    row = owner.execute(
        f"INSERT INTO {CODES} (code, name, sort_order, created_at, updated_at) VALUES (NULL, %s, 0, now(), now()) "
        "RETURNING id",
        [name],
    ).fetchone()
    assert row is not None
    owner.execute(f"UPDATE {CODES} SET code = 'F' || lpad(id::text, 4, '0'), sort_order = id WHERE id = %s", [row[0]])
    return int(row[0])


def add_site(owner: Owner, company_id: int, name: str) -> int:
    row = owner.execute(
        "INSERT INTO sites (company_id, name, created_at) VALUES (%s, %s, now()) RETURNING id", [company_id, name]
    ).fetchone()
    assert row is not None
    return int(row[0])


def add_facility(owner: Owner, company_id: int, site_id: int, code_id: int, detail: str) -> int:
    row = owner.execute(
        "INSERT INTO site_facilities (company_id, site_id, facility_code_id, detail_name, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, now(), now()) RETURNING id",
        [company_id, site_id, code_id, detail],
    ).fetchone()
    assert row is not None
    return int(row[0])


def site_facts(owner: Owner, company_id: int) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT id, name, inventory_enabled, deleted_at IS NULL FROM sites WHERE company_id = %s ORDER BY id",
        [company_id],
    ).fetchall()


def facility_facts(owner: Owner, company_id: int) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT id, site_id, facility_code_id, detail_name, deleted_at IS NULL FROM site_facilities "
        "WHERE company_id = %s ORDER BY id",
        [company_id],
    ).fetchall()


def seen_of(owner: Owner, site_id: int) -> str:
    """사업장의 지금 판(주인 연결로 읽은 updated_at) — PUT 본문 updatedAt(K1b-3)."""
    row = owner.execute("SELECT updated_at FROM sites WHERE id = %s", [site_id]).fetchone()
    assert row is not None
    return str(row[0].isoformat())


def send(client: Client, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    if method == "GET":
        return client.get("/api" + path)
    return getattr(client, method.lower())("/api" + path, data=body or {}, content_type="application/json")


def code_of(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


@pytest.fixture
def two(owner: Owner) -> tuple[int, int]:
    a = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    b = add_company(owner, "tenant-b", name="나 회사", licence="000-00-00002")
    return a, b


# ── ⓐ 남의 회사 id ─────────────────────────────────────────────────────


def test_another_companys_ids_are_404_and_change_nothing(owner: Owner, two: tuple[int, int]) -> None:
    a, b = two
    boiler = add_code(owner, "보일러")
    mine = add_site(owner, a, "가 공장")
    my_row = add_facility(owner, a, mine, boiler, "1호기")
    theirs = add_site(owner, b, "나 공장")
    their_row = add_facility(owner, b, theirs, boiler, "1호기")
    customer = customer_client(a, "tenant-a")
    before = (site_facts(owner, b), facility_facts(owner, b))

    def save(row: int, seen: str = "2026-01-02T03:04:05+09:00") -> dict[str, Any]:
        rows = [{"id": row, "facilityCodeId": boiler, "detailName": "2호기"}]
        return {"name": "새 이름", "inventoryEnabled": True, "facilities": rows, "updatedAt": seen}

    tried = [
        ("GET", f"/branches/{theirs}", None),
        ("PUT", f"/branches/{theirs}", save(their_row)),
        ("PUT", f"/branches/{mine}", save(their_row, seen_of(owner, mine))),  # 내 사업장에 남의 자산/시설 id
        ("POST", "/branches/inventory", {"ids": [mine, theirs], "enabled": False}),
        ("POST", "/branches/delete", {"ids": [mine, theirs]}),
    ]
    for method, path, body in tried:
        assert code_of(send(customer, method, path, body)) == (404, "NOT_FOUND"), (method, path)
    # K1b-3: B 의 사업장에 B 의 진짜 판·틀린 판으로 저장 → 둘 다 404(409 0 — 판이 맞는지로 B 의 행이 있음이 새지 않는다)
    assert [row[0] for row in site_facts(owner, b)] == [theirs]  # B 의 행이 있다(없어서 404 가 아니다)
    for seen in (seen_of(owner, theirs), "2000-01-01T00:00:00+09:00"):
        assert code_of(send(customer, "PUT", f"/branches/{theirs}", save(their_row, seen))) == (404, "NOT_FOUND"), seen
    assert (site_facts(owner, b), facility_facts(owner, b)) == before  # 남의 행 그대로
    assert [row[1:] for row in site_facts(owner, a)] == [("가 공장", True, True)]  # 내 행도 그대로(일부만 처리 0)
    assert len(tried) == 5  # 분모: 고리 다섯

    listed = send(customer, "GET", "/branches").json()["results"]
    assert [row["id"] for row in listed] == [str(mine)]  # 목록에 남의 것 0
    # 분모: 같은 요청을 내 id 로 보내면 지난다
    detail = send(customer, "GET", f"/branches/{mine}")
    assert detail.status_code == 200
    assert send(customer, "PUT", f"/branches/{mine}", save(my_row, detail.json()["updatedAt"])).status_code == 200
    assert send(customer, "POST", "/branches/inventory", {"ids": [mine], "enabled": False}).json() == {"count": 1}
    assert send(customer, "POST", "/branches/delete", {"ids": [mine]}).json() == {"count": 1}
    assert (site_facts(owner, b), facility_facts(owner, b)) == before


# ── ⓑ 코드 목록 쓰기는 운영 관리자만 ─────────────────────────────────────────


def test_the_code_writes_are_403_for_a_customer(owner: Owner, two: tuple[int, int]) -> None:
    a, _ = two
    boiler = add_code(owner, "보일러")
    customer = customer_client(a, "tenant-a")
    operator, _ = operator_client(owner)
    tried = [
        ("GET", "/admin/facility-codes", None),
        ("POST", "/admin/facility-codes", {"name": "냉동기"}),
        ("PATCH", f"/admin/facility-codes/{boiler}", {"name": "증기 보일러"}),
        ("POST", "/admin/facility-codes/delete", {"ids": [boiler]}),
    ]
    before = owner.execute(f"SELECT id, code, name, deleted_at FROM {CODES} ORDER BY id").fetchall()
    for method, path, body in tried:
        assert code_of(send(customer, method, path, body)) == (403, "FORBIDDEN"), (method, path)
    assert owner.execute(f"SELECT id, code, name, deleted_at FROM {CODES} ORDER BY id").fetchall() == before
    # 분모: 운영 관리자는 넷 다 지난다(회사 둘이어도 — 회사를 고르지 않는다)
    assert [send(operator, method, path, body).status_code for method, path, body in tried] == [200, 201, 200, 200]


# ── ⓒ 지운 코드는 쓰는 행에 그대로 ─────────────────────────────────────────


def test_a_deleted_code_stays_on_the_branch_and_leaves_the_pick_list(owner: Owner, two: tuple[int, int]) -> None:
    a, _ = two
    customer = customer_client(a, "tenant-a")
    operator, _ = operator_client(owner)
    made = send(operator, "POST", "/admin/facility-codes", {"name": "보일러"}).json()
    rows = [{"facilityCodeId": int(made["id"]), "detailName": "1호기"}]
    branch = send(customer, "POST", "/branches", {"name": "가 공장", "facilities": rows})
    assert branch.status_code == 201, branch.content.decode()
    assert [item["id"] for item in send(customer, "GET", "/facility-codes").json()["items"]] == [made["id"]]  # 분모

    assert send(operator, "POST", "/admin/facility-codes/delete", {"ids": [int(made["id"])]}).json() == {"count": 1}
    detail = send(customer, "GET", f"/branches/{branch.json()['id']}").json()
    assert [(f["facilityCode"], f["facilityName"], f["detailName"]) for f in detail["facilities"]] == [
        (made["code"], "보일러", "1호기")
    ]
    assert send(customer, "GET", "/facility-codes").json()["items"] == []  # 새 선택 목록에서만 빠진다
    assert owner.execute(f"SELECT count(*) FROM {CODES} WHERE deleted_at IS NOT NULL").fetchone() == (1,)  # 행은 남음


# ── ⓓ 운영 관리자의 작업 회사 ────────────────────────────────────────────


def test_the_operator_writes_into_the_work_company(owner: Owner) -> None:
    a = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    boiler = add_code(owner, "보일러")
    operator, _ = operator_client(owner)
    rows = [{"facilityCodeId": boiler, "detailName": "1호기"}]
    made = send(operator, "POST", "/branches", {"name": "가 공장", "facilities": rows})
    assert made.status_code == 201, made.content.decode()
    assert owner.execute("SELECT array_agg(DISTINCT company_id) FROM sites").fetchone() == ([a],)
    assert owner.execute("SELECT array_agg(DISTINCT company_id) FROM site_facilities").fetchone() == ([a],)
    assert owner.execute("SELECT count(*) FROM site_facilities").fetchone() == (1,)  # 분모


# ── ⓔ 본문의 회사 칸 ────────────────────────────────────────────────────


def test_a_body_company_id_is_422(owner: Owner, two: tuple[int, int]) -> None:
    a, b = two
    mine = add_site(owner, a, "가 공장")
    customer = customer_client(a, "tenant-a")
    tried: list[tuple[str, str, dict[str, Any]]] = [
        ("POST", "/branches", {"name": "나 공장", "companyId": b}),
        (
            "PUT",
            f"/branches/{mine}",
            {
                "name": "나 공장",
                "inventoryEnabled": True,
                "facilities": [],
                "updatedAt": seen_of(owner, mine),
                "companyId": b,
            },
        ),
        ("POST", "/branches/delete", {"ids": [mine], "companyId": b}),
    ]
    for method, path, body in tried:
        assert code_of(send(customer, method, path, body)) == (422, "VALIDATION_ERROR"), (method, path)
    assert [row[1:] for row in site_facts(owner, a)] == [("가 공장", True, True)]
    assert site_facts(owner, b) == []


# ── ⓕ 앱 역할은 지우지 못한다 ────────────────────────────────────────────


def denied(statement: str) -> tuple[str | None, str]:
    """앱 역할로 문 하나를 보내고 (SQLSTATE, DB 의 원문 첫 줄). 된 것이면 (None, "")."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement)
    except DatabaseError as error:
        return getattr(error.__cause__, "sqlstate", None), str(error.__cause__).splitlines()[0]
    return None, ""


def test_the_app_role_cannot_delete_branch_rows(owner: Owner, two: tuple[int, int]) -> None:
    a, _ = two
    boiler = add_code(owner, "보일러")
    site = add_site(owner, a, "가 공장")
    add_facility(owner, a, site, boiler, "1호기")
    for table in ("site_facilities", CODES, "sites"):
        assert denied(f"DELETE FROM {table}") == ("42501", f"permission denied for table {table}"), table
    # 분모: 앱 역할은 삭제 표시(UPDATE)는 된다
    assert denied(f"UPDATE site_facilities SET deleted_at = now() WHERE company_id = {a}") == (None, "")
    assert owner.execute("SELECT count(*) FROM site_facilities WHERE deleted_at IS NOT NULL").fetchone() == (1,)
    assert owner.execute(f"SELECT count(*) FROM {CODES}").fetchone() == (1,)
