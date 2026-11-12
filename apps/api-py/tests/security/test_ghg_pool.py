"""온실가스 인덱스 풀·시설별 배출계수 풀(K1b-2a — 결정 MARC-ENT-469 3·478)의 보안 층. 앱 역할, 진짜 커밋.

풀 표 넷(ghg_index_nodes·ghg_factors·ghg_factor_versions·ghg_factor_gases)은 **모든 고객사 공통 하나**라 회사 칸이
없다 —
그래서 격리 표(tests/security/conftest.py 의 tenant_tables)에서 빠지고, 회사 격리 대신 「누가 고치나」 와 「무엇을
고칠 수 있나」 를 잰다:
  ⓐ 고객사 사용자의 Bearer 는 경로 열둘 전부 403 FORBIDDEN 이고 풀 표 넷의 행 수가 그대로다
     (분모: 운영 관리자의 Bearer 는 같은 열둘을 지난다 — 200·201·404).
  ⓑ 앱 역할(esg_app)로 실제 SQL: 판·가스 UPDATE·DELETE, 노드·계수 DELETE 여섯이 42501 이다(SQLSTATE 와 DB 원문 둘 다)
     — 판은 넣고 나면 고치지 않고(고치기는 새 판, 회사 선택이 판을 잡는다 — K1b-2b), 지우기는 삭제 표시다.
     (분모: 같은 역할로 노드·계수 UPDATE(삭제 표시)는 되고, 넷 다 INSERT 된다.)
  ⓒ 풀 표 넷에 회사 칸이 없다(카탈로그).
★ 공통 표는 tenant_tables 밖이라 owner 고정물이 비우지 않는다 — 앞뒤로 비운다(코드 목록과 함께 CASCADE).
이름·값은 지어낸 것이다(실제 계수·GWP 0).
"""

from collections.abc import Iterator
from typing import Any, Final, LiteralString

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction
from django.test import Client

from tests.security.conftest import tenant_tables
from tests.security.seed import add_company
from tests.security.test_operator_company import customer_client, operator_client

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
POOL: Final = ("ghg_index_nodes", "ghg_factors", "ghg_factor_versions", "ghg_factor_gases")
CODES: Final = "organization_facility_codes"


@pytest.fixture(autouse=True)
def empty_pool(owner: Owner) -> Iterator[None]:
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")
    yield
    owner.execute(f"TRUNCATE {CODES}, {', '.join(POOL)} CASCADE")


def one(owner: Owner, statement: LiteralString, params: list[Any]) -> int:
    row = owner.execute(statement, params).fetchone()
    assert row is not None
    return int(row[0])


def seed(owner: Owner) -> dict[str, int]:
    """주인 역할로 나무 한 줄 + 잎 + 계수 하나(판 1, 가스 하나)를 넣는다."""
    code = one(
        owner,
        f"INSERT INTO {CODES} (code, name, sort_order, created_at, updated_at) VALUES (NULL, %s, 0, now(), now()) "
        "RETURNING id",
        ["가 보일러"],
    )
    node = (
        "INSERT INTO ghg_index_nodes (level, parent_id, name, sort_order, facility_code_id, unit_kind, unit, tooltip, "
        "seed_key, deleted_at, created_at, updated_at) "
        "VALUES (%s, %s, %s, 0, %s, %s, %s, '', NULL, NULL, now(), now()) RETURNING id"
    )
    scope = one(owner, node, ["scope", None, "범위 가", None, None, None])
    kind = one(owner, node, ["source_type", scope, "유형 가", None, None, None])
    act = one(owner, node, ["activity", kind, "활동 가", None, None, None])
    leaf = one(owner, node, ["facility", act, "", code, "mass", "kg"])
    factor = one(
        owner,
        "INSERT INTO ghg_factors (facility_node_id, is_default, sort_order, current_version, seed_key, deleted_at, "
        "created_at, updated_at) VALUES (%s, true, 0, 1, NULL, NULL, now(), now()) RETURNING id",
        [leaf],
    )
    version = one(
        owner,
        "INSERT INTO ghg_factor_versions (factor_id, version, name, source, base_year, tier, country_code, "
        "industry_code, input_unit_kind, input_unit, emission_unit_kind, emission_unit, ncv_enabled, ncv, "
        "ncv_unit_kind, ncv_unit, factor_unit, note, seed_record_ids, seed_gwp_set_id, created_at) VALUES "
        "(%s, 1, '계수 가', '지어낸 출처', 2024, 1, 'KR', 'other', 'mass', 'kg', 'mass', 'tCO2-eq', false, NULL, "
        "NULL, NULL, 'kg/kg', '', '[]'::jsonb, NULL, now()) RETURNING id",
        [factor],
    )
    owner.execute(
        "INSERT INTO ghg_factor_gases (factor_version_id, gas, enabled, factor, gwp) VALUES (%s, 'CO2', true, 1, 1)",
        [version],
    )
    return {"code": code, "scope": scope, "activity": act, "leaf": leaf, "factor": factor, "version": version}


def counts(owner: Owner) -> list[int]:
    return [one(owner, f"SELECT count(*) FROM {table}", []) for table in POOL]


def routes(ids: dict[str, int]) -> list[tuple[str, str, dict[str, Any] | None]]:
    unit = {"kind": "mass", "unit": "kg"}
    factor = {
        "name": "x",
        "source": "x",
        "baseYear": 2024,
        "tier": 1,
        "countryCode": "KR",
        "industryCode": "other",
        "inputUnit": unit,
        "gases": [{"gas": "CO2", "enabled": True, "factor": "1", "gwp": "1"}],
    }
    root = "/api/inventory/admin"
    leaf, fac = ids["leaf"], ids["factor"]
    return [
        ("GET", f"{root}/ghg-index/nodes", None),
        ("POST", f"{root}/ghg-index/nodes", {"level": "scope", "name": "범위 나"}),
        ("PATCH", f"{root}/ghg-index/nodes/{ids['scope']}", {"name": "범위 다"}),
        ("POST", f"{root}/ghg-index/nodes/delete", {"ids": [2_000_000_000]}),
        ("GET", f"{root}/ghg-index/facilities/{leaf}", None),
        (
            "POST",
            f"{root}/ghg-index/facilities",
            {"parentId": 2_000_000_000, "facilityCodeId": ids["code"], "unit": unit},
        ),
        ("PUT", f"{root}/ghg-index/facilities/{leaf}", {"facilityCodeId": ids["code"], "unit": unit}),
        ("POST", f"{root}/ghg-index/facilities/{leaf}/factors", factor),
        ("GET", f"{root}/ghg-factors/{fac}", None),
        ("PUT", f"{root}/ghg-factors/{fac}", factor),
        ("POST", f"{root}/ghg-factors/delete", {"ids": [2_000_000_000]}),
        ("GET", f"{root}/ghg-options", None),
    ]


def send(client: Client, method: str, path: str, body: dict[str, Any] | None) -> Any:
    if body is None:
        return getattr(client, method.lower())(path)
    return getattr(client, method.lower())(path, data=body, content_type="application/json")


def test_a_customer_is_refused_all_twelve_routes_and_the_pool_stays(owner: Owner) -> None:
    """ⓐ 고객사 사용자 403 열둘 · 행 0 바뀜. 분모: 운영 관리자는 같은 열둘을 지난다."""
    ids = seed(owner)
    company = add_company(owner, "tenant-a", name="가 회사", licence="000-00-00001")
    customer = customer_client(company)
    before = counts(owner)
    for method, path, body in routes(ids):
        refused = send(customer, method, path, body)
        assert (refused.status_code, refused.json()["error"]["code"]) == (403, "FORBIDDEN"), path
    assert counts(owner) == before
    operator, _ = operator_client(owner)
    passed = {(method, path): send(operator, method, path, body).status_code for method, path, body in routes(ids)}
    assert set(passed.values()) <= {200, 201, 404}, passed
    assert len(passed) == 12  # 분모: 열둘 다 보냈다
    assert sum(code in (200, 201) for code in passed.values()) == 9  # 없는 id 셋(지우기 둘·잎 만들기)만 404


DENIED = [
    ("UPDATE ghg_factor_versions SET name = 'x'", "ghg_factor_versions"),
    ("DELETE FROM ghg_factor_versions", "ghg_factor_versions"),
    ("UPDATE ghg_factor_gases SET enabled = false", "ghg_factor_gases"),
    ("DELETE FROM ghg_factor_gases", "ghg_factor_gases"),
    ("DELETE FROM ghg_index_nodes", "ghg_index_nodes"),
    ("DELETE FROM ghg_factors", "ghg_factors"),
]


def denied(statement: str) -> tuple[str | None, str]:
    """앱 역할로 문 하나를 보내고 (SQLSTATE, DB 의 원문 첫 줄). 된 것이면 (None, "")."""
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement)
    except DatabaseError as error:
        return getattr(error.__cause__, "sqlstate", None), str(error.__cause__).splitlines()[0]
    return None, ""


@pytest.mark.parametrize(("statement", "table"), DENIED, ids=[statement for statement, _ in DENIED])
def test_the_app_role_cannot_rewrite_a_version_or_delete_pool_rows(owner: Owner, statement: str, table: str) -> None:
    """ⓑ 여섯 다 42501 · 원문 「permission denied for table <표>」 · 행 그대로."""
    seed(owner)
    before = counts(owner)
    assert denied(statement) == ("42501", f"permission denied for table {table}")
    assert counts(owner) == before
    assert one(owner, "SELECT count(*) FROM ghg_factor_versions WHERE name = '계수 가'", []) == 1


def test_the_app_role_marks_deleted_and_inserts(owner: Owner) -> None:
    """ⓑ 분모: 노드·계수의 삭제 표시(UPDATE)는 되고, 넷 다 INSERT 된다(경로가 쓰는 권한)."""
    ids = seed(owner)
    assert denied(f"UPDATE ghg_factors SET is_default = false, deleted_at = now() WHERE id = {ids['factor']}") == (
        None,
        "",
    )
    assert denied(f"UPDATE ghg_index_nodes SET deleted_at = now() WHERE id = {ids['leaf']}") == (None, "")
    assert denied(
        "INSERT INTO ghg_index_nodes (level, parent_id, name, sort_order, tooltip, created_at, updated_at) "
        "VALUES ('scope', NULL, '범위 라', 0, '', now(), now())"
    ) == (None, "")
    assert denied(
        "INSERT INTO ghg_factors (facility_node_id, is_default, sort_order, current_version, created_at, updated_at) "
        f"VALUES ({ids['leaf']}, false, 0, 1, now(), now())"
    ) == (None, "")
    assert denied(
        "INSERT INTO ghg_factor_versions (factor_id, version, name, source, base_year, tier, country_code, "
        "industry_code, input_unit_kind, input_unit, emission_unit_kind, emission_unit, ncv_enabled, factor_unit, "
        f"note, seed_record_ids, created_at) VALUES ({ids['factor']}, 2, '새 판', 'x', 2024, 1, 'KR', 'other', "
        "'mass', 'kg', 'mass', 'tCO2-eq', false, 'kg/kg', '', '[]'::jsonb, now())"
    ) == (None, "")
    assert denied(
        f"INSERT INTO ghg_factor_gases (factor_version_id, gas, enabled) VALUES ({ids['version']}, 'CH4', false)"
    ) == (None, "")
    assert counts(owner) == [5, 2, 2, 2]


def test_the_pool_tables_have_no_company_column(owner: Owner) -> None:
    """ⓒ 풀 표 넷: 있음 · 회사 칸 0 · 격리 표(tenant_tables) 밖."""
    tenant = tenant_tables(owner)
    for table in POOL:
        assert owner.execute("SELECT to_regclass(%s) IS NOT NULL", [f"public.{table}"]).fetchone() == (True,), table
        columns = owner.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND column_name LIKE %s",
            [table, "compan%"],
        ).fetchall()
        assert columns == [], table
        assert table not in tenant, table
