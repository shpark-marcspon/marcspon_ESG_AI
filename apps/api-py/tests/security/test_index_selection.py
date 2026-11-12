"""고객사 인덱스 선택(K1b-2b — 결정 MARC-ENT-469 3·4, 테스트 6d 허락 H11)의 보안 층. 앱 역할, 진짜 커밋.

인덱스 풀은 모든 고객사 공통이지만 **선택·해·시설 수는 회사 것**이다(inventory_years·inventory_index_selections 는
회사 칸 표 — conftest 의 tenant_tables 에 저절로 든다). 여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  ⓐ 회사 둘이 같은 풀 잎을 고르고 같은 코드 시설을 가져도 A 의 트리는 A 의 availableCount·selected 만 본다
  ⓑ A 의 저장은 A 에만 든다 — B 의 해·선택 행 그대로(주인 연결로 셈)
  ⓒ A 의 고객사 경로(트리·저장) 응답 글자에 B 의 회사 id·이름·서브도메인·사업장 이름이 0(플랫폼-서버 dc 조건)
  ⓓ 앱 역할은 해·선택을 지우지 못한다(42501 — 지우기는 삭제 표시)
  ⓔ (④ — MARC-ISSUE-432) B 가 고른 잎을 운영 관리자가 지우거나 코드·단위를 바꾸면 409 in_use 이고, 그 응답 글자에
     B 의 회사 id·이름·서브도메인·사업장·선택 id 가 0(회사 넘는 읽기는 풀 id 만 — 결정 MARC-ENT-487)
시험마다 B 의 행이 실제로 있음을 첫 단언으로 둔다(분모 — 셈이 0 이면 격리 단언이 빈 채 초록이 된다, 6d 덧붙임).
본문 facilityNodeIds 는 공통 풀 id 라 tests/security/test_tenant_paths.py 의 ID_FIELDS 가 못 본다 — 이 파일이 유일한
잠금이다. (401·444·400 은 test_tenant_paths 의 index_selection_paths 분류가 다른 회사 경로와 같이 잰다.)
★ 공통 표(풀 넷·코드 목록)는 tenant_tables 밖이라 owner 고정물이 비우지 않는다 — 앞뒤로 비운다.
이름·값은 지어낸 것이다.
"""

import json
from collections.abc import Iterator
from typing import Any, Final

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client

from tests.security.test_ghg_pool import CODES, POOL, one, seed
from tests.security.test_operator_company import customer_client, operator_client

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
YEAR: Final = 2025
TREE: Final = f"/api/inventory/scope12/index-tree?year={YEAR}"
SAVE: Final = f"/api/inventory/scope12/index-selections/{YEAR}"
B_SITE: Final = "나 회사의 남쪽 공장"


@pytest.fixture(autouse=True)
def empty_pool(owner: Owner) -> Iterator[None]:
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")
    yield
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")


def facilities(owner: Owner, company_id: int, code_id: int, name: str, n: int) -> int:
    """그 회사의 사업장 하나와 그 코드 자산/시설 n 줄. 사업장 id."""
    site = one(
        owner,
        "INSERT INTO sites (company_id, name, created_at) VALUES (%s, %s, now()) RETURNING id",
        [company_id, name],
    )
    for index in range(n):
        owner.execute(
            "INSERT INTO site_facilities (company_id, site_id, facility_code_id, detail_name, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, now(), now())",
            [company_id, site, code_id, f"{index}호기"],
        )
    return site


def b_rows(owner: Owner, b: int) -> list[tuple[Any, ...]]:
    return owner.execute(
        "SELECT s.id, s.facility_node_id, s.factor_version_id, s.hidden, s.deleted_at IS NULL, y.year "
        "FROM inventory_index_selections s JOIN inventory_years y ON y.id = s.inventory_year_id "
        "WHERE s.company_id = %s ORDER BY s.id",
        [b],
    ).fetchall()


def put(client: Client, ids: list[int]) -> Any:
    return client.put(SAVE, data={"facilityNodeIds": ids}, content_type="application/json")


@pytest.fixture
def both(owner: Owner, companies: tuple[int, int]) -> dict[str, int]:
    """A 에 시설 하나, B 에 시설 셋 — 같은 코드. B 는 그 잎을 이미 골랐다."""
    a, b = companies
    ids = seed(owner)
    facilities(owner, a, ids["code"], "가 회사의 공장", 1)
    facilities(owner, b, ids["code"], B_SITE, 3)
    assert put(customer_client(b, "tenant-b"), [ids["leaf"]]).status_code == 200
    return ids


def test_two_companies_see_only_their_own_tree(owner: Owner, companies: tuple[int, int], both: dict[str, int]) -> None:
    a, b = companies
    assert len(b_rows(owner, b)) == 1  # 분모: B 의 선택이 있다
    leaf = str(both["leaf"])
    client = customer_client(a, "tenant-a")
    assert put(client, []).status_code == 200  # A 에도 그 해가 선다(빈 선택) — 해 있는 두 회사의 트리를 견준다
    lines = {line["id"]: line for line in client.get(TREE).json()["nodes"]}
    assert (lines[leaf]["availableCount"], lines[leaf]["selected"]) == (1, False)  # B 의 셋·B 의 선택 0
    theirs = {line["id"]: line for line in customer_client(b, "tenant-b").get(TREE).json()["nodes"]}
    assert (theirs[leaf]["availableCount"], theirs[leaf]["selected"]) == (3, True)  # 짝: B 는 제 것을 본다


def test_a_save_lands_only_in_my_company(owner: Owner, companies: tuple[int, int], both: dict[str, int]) -> None:
    a, b = companies
    before = b_rows(owner, b)
    assert len(before) == 1  # 분모
    client = customer_client(a, "tenant-a")
    assert put(client, [both["leaf"]]).json() == {"selected": 1, "hiddenWithData": 0}
    assert put(client, []).json() == {"selected": 0, "hiddenWithData": 0}  # A 가 빼도 B 의 선택은 그대로
    assert b_rows(owner, b) == before
    mine = owner.execute(
        "SELECT company_id, deleted_at IS NULL FROM inventory_index_selections WHERE company_id <> %s", [b]
    ).fetchall()
    assert mine == [(a, False)]  # A 의 행은 A 의 회사 칸 · 뺀 뒤 삭제 표시


def test_a_customer_route_carries_nothing_of_the_other_company(
    owner: Owner, companies: tuple[int, int], both: dict[str, int]
) -> None:
    a, b = companies
    assert len(b_rows(owner, b)) == 1  # 분모
    names = owner.execute("SELECT name, subdomain FROM company WHERE id = %s", [b]).fetchone()
    assert names is not None
    client = customer_client(a, "tenant-a")
    texts = [client.get(TREE).content.decode(), put(client, [both["leaf"]]).content.decode()]
    for text in texts:
        for word in (*names, B_SITE, "companyId"):  # 회사 id 숫자는 노드 id 와 우연히 겹칠 수 있어 칸 이름으로 본다
            assert word not in text, word
    assert str(both["leaf"]) in texts[0]  # 분모: 트리는 실제로 그 잎을 실었다


@pytest.mark.parametrize("table", ["inventory_index_selections", "inventory_years"])
def test_the_app_role_cannot_delete_a_selection_or_a_year(
    owner: Owner, companies: tuple[int, int], both: dict[str, int], table: str
) -> None:
    _, b = companies
    before = b_rows(owner, b)
    assert len(before) == 1  # 분모
    with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {table} WHERE company_id = %s", [b])  # 표 이름은 위 매개 둘뿐
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error)
    assert cause.sqlstate == "42501"  # insufficient_privilege
    assert "permission denied" in str(cause)
    assert b_rows(owner, b) == before


def test_the_admin_cannot_delete_or_recode_a_leaf_another_company_chose(
    owner: Owner, companies: tuple[int, int], both: dict[str, int]
) -> None:
    _, b = companies
    before = b_rows(owner, b)
    assert len(before) == 1  # 분모: B 의 선택이 있다
    names = owner.execute("SELECT name, subdomain FROM company WHERE id = %s", [b]).fetchone()
    assert names is not None
    other = one(
        owner,
        f"INSERT INTO {CODES} (code, name, sort_order, created_at, updated_at) VALUES ('F9999', '다른 코드', 0, now(), "
        "now()) RETURNING id",
        [],
    )
    admin, _ = operator_client(owner)
    leaf = both["leaf"]
    root = "/api/inventory/admin/ghg-index"
    answers = [
        admin.post(f"{root}/nodes/delete", data={"ids": [leaf]}, content_type="application/json"),
        admin.put(
            f"{root}/facilities/{leaf}",
            data={"facilityCodeId": other, "unit": {"kind": "mass", "unit": "kg"}},
            content_type="application/json",
        ),
        admin.put(
            f"{root}/facilities/{leaf}",
            data={"facilityCodeId": both["code"], "unit": {"kind": "mass", "unit": "t"}},
            content_type="application/json",
        ),
        admin.post(
            "/api/inventory/admin/ghg-factors/delete", data={"ids": [both["factor"]]}, content_type="application/json"
        ),
    ]
    for response in answers:
        assert (response.status_code, response.json()["error"]["code"]) == (409, "IN_USE"), response.content.decode()
        error = response.json()["error"]
        assert set(error) == {"code", "message", "fields", "legacyCode"} and error["fields"] is None
        assert not any(ch.isdigit() for ch in error["message"])  # 어느 id 도 싣지 않는다(B 의 선택·회사 id 포함)
        text = json.dumps(response.json(), ensure_ascii=False)
        for word in (*names, B_SITE, "companyId"):
            assert word not in text, word
    assert b_rows(owner, b) == before  # 잡은 판·선택 그대로
    alive = owner.execute(
        "SELECT deleted_at IS NULL, facility_code_id, unit FROM ghg_index_nodes WHERE id = %s", [leaf]
    ).fetchone()
    assert alive == (True, both["code"], "kg")  # 풀 잎도 그대로
