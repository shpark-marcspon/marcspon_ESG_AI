"""기준정보의 표를 앱 역할로 잰다: 읽기만 되고, 테넌트 없이 읽히고, 정책이 없다. 보안 층.

기준정보(reference_*)에는 회사 칸이 없다. 그래서 test_owner.py 의 카탈로그 검사(company 와 company_id 칸이 있는 표)는
이 표들을 건너뛴다. 건너뛴 자리를 여기서 잰다.

자료는 주인 역할의 관리 명령(`manage.py import_factors`, 마이그레이션과 같은 설정)으로 테스트 DB 에 들인다.
`owner` 고정물은 테넌트의 표만 비우므로, 이 파일이 들인 행은 이 파일이 지운다.

무효 조건: 권한은 `esg_app` 역할로 잰 것이다. superuser 나 표의 주인에게는 GRANT 가 뜻이 없다
(로컬의 주인 역할이 그렇다).
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from io import StringIO
from typing import Any

import psycopg
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import ProgrammingError, connection, transaction
from django.test import Client
from psycopg import sql

from esgapi.reference.models import FactorRecordRow, MappingRow, SourceRow
from tests.security.conftest import API_PY_DIR, count, tenant_tables
from tests.support.http import login

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
TABLES = [
    "reference_factor_records",
    "reference_factor_scope3_categories",
    "reference_mappings",
    "reference_sources",
]
PRIVILEGES = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]


def reference_tables(owner: Owner) -> list[str]:
    """reference_ 로 시작하는 표 전부(카탈로그에서). 모듈이 표를 더하면 아래 검사가 그 표에도 걸린다."""
    rows = owner.execute(
        "SELECT relname FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' "
        "AND relname LIKE 'reference\\_%' ORDER BY relname"
    ).fetchall()
    return [name for (name,) in rows]


def _empty(owner_url: str) -> None:
    with psycopg.connect(owner_url, autocommit=True) as conn:
        conn.execute(sql.SQL("TRUNCATE {} CASCADE").format(sql.SQL(", ").join(map(sql.Identifier, TABLES))))


@pytest.fixture(scope="module")
def loaded(test_database: str) -> Iterator[None]:
    """패키지 사본 600건을 주인 역할로 들인다(migrate-py 컨테이너가 하는 것과 같은 설정). 끝나면 비운다."""
    _empty(test_database)
    subprocess.run(
        [sys.executable, "manage.py", "import_factors"],
        cwd=API_PY_DIR,
        env={
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "esgapi.config.settings.migrate",
            "DATABASE_URL_PY_OWNER": test_database,
        },
        check=True,
        capture_output=True,
    )
    yield
    _empty(test_database)


def test_the_reference_tables_are_exactly_the_four_and_none_is_a_tenant_table(owner: Owner) -> None:
    assert reference_tables(owner) == TABLES
    assert not set(TABLES) & set(tenant_tables(owner))
    # company_id 라는 이름의 칸이 없다(있으면 회사의 표로 잡혀 test_owner.py 의 카탈로그 검사가 그 표에도 걸린다).
    # 옛 회사 칸 이름 tenant_id 도 없다.
    columns = owner.execute(
        "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public' "
        "AND table_name = ANY(%s) AND column_name IN ('company_id', 'tenant_id')",
        [TABLES],
    ).fetchone()
    assert columns == (0,)


def test_app_role_may_select_and_nothing_else(owner: Owner) -> None:
    """GRANT: esg_app 은 표마다 SELECT 는 되고 INSERT·UPDATE·DELETE·TRUNCATE(와 REFERENCES·TRIGGER)는 안 된다."""
    tables = reference_tables(owner)
    assert tables == TABLES
    rows = owner.execute(
        "SELECT t, p, has_table_privilege('esg_app', t, p) FROM unnest(%s::text[]) AS t, unnest(%s::text[]) AS p "
        "ORDER BY t, p",
        [tables, PRIVILEGES],
    ).fetchall()
    assert len(rows) == len(tables) * len(PRIVILEGES)
    assert {(table, privilege) for table, privilege, allowed in rows if allowed} == {(t, "SELECT") for t in tables}
    # 번호열(범주 연결 표의 id)도 쓸 수 없다.
    sequences = owner.execute(
        "SELECT c.relname, has_sequence_privilege('esg_app', c.oid, 'USAGE') FROM pg_class c "
        "WHERE c.relnamespace = 'public'::regnamespace AND c.relkind = 'S' AND c.relname LIKE 'reference\\_%'"
    ).fetchall()
    assert sequences == [("reference_factor_scope3_categories_id_seq", False)]


def test_the_reference_tables_have_no_policy_and_no_row_security(owner: Owner) -> None:
    tables = reference_tables(owner)
    policies = owner.execute(
        "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = ANY(%s)", [tables]
    ).fetchone()
    assert policies == (0,)
    flags = owner.execute(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relnamespace = 'public'::regnamespace AND relname = ANY(%s) ORDER BY relname",
        [tables],
    ).fetchall()
    assert flags == [(table, False, False) for table in TABLES]


def test_app_role_reads_without_a_tenant(owner: Owner, loaded: None) -> None:
    """앱 역할의 연결이 테넌트 없이 기준정보를 읽는다(공용 자료. 기본 매니저가 범위를 요구하지 않는다)."""
    assert count(owner, "reference_factor_records") == 600  # 분모: 주인이 센 실제 행 수
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        assert cursor.fetchone() == ("esg_app",)
    assert FactorRecordRow.objects.count() == 600
    assert SourceRow.objects.count() == count(owner, "reference_sources") == 7
    assert MappingRow.objects.count() == 1


def test_two_tenants_get_the_same_reference_rows(client: Client, owner: Owner, tenants: None, loaded: None) -> None:
    """세션의 테넌트가 달라도 같은 답이다(전역 자료). 세션이 없으면 401 이다."""
    assert client.get("/api/reference/factors").status_code == 401
    answers: list[Any] = []
    for tenant_id in ("tenant-a", "tenant-b"):
        login(client, tenant_id=tenant_id, sub=f"user-of-{tenant_id}", role="viewer")
        factors = client.get("/api/reference/factors", {"source": "kr-ets-byl12", "limit": 200}).json()
        sources = client.get("/api/reference/sources").json()
        diesel = client.post(
            "/api/reference/assemble",
            data={
                "fuel": "경유",
                "combustionType": "stationary",
                "industry": {"sector": "manufacturing_construction"},
                "tiers": {"kind": "explicit", "calorific": 2, "co2": 2, "oxidation": 2},
            },
            content_type="application/json",
        ).json()
        assert (factors["total"], len(sources["sources"]), diesel["ok"]) == (108, 7, True)
        answers.append((factors, sources, diesel))
    assert answers[0] == answers[1]


def test_app_role_cannot_write_reference_rows(owner: Owner, loaded: None) -> None:
    """앱 역할의 연결로는 고치기·지우기·넣기가 전부 권한 오류다. 행은 그대로다."""

    def denied(action: Any) -> None:
        with pytest.raises(ProgrammingError, match="permission denied"), transaction.atomic():
            action()

    denied(lambda: FactorRecordRow.objects.filter(id="kr-ets-byl12:ef:p3r3:CO2").update(value_raw="1"))
    denied(lambda: FactorRecordRow.objects.filter(source_id="gir-2024").delete())
    denied(lambda: MappingRow.objects.create(guideline_version="synthetic", body={}))
    denied(lambda: SourceRow.objects.filter(id="kr-ets-byl12").update(license_status="ok"))
    row = owner.execute(
        "SELECT value_raw FROM reference_factor_records WHERE id = 'kr-ets-byl12:ef:p3r3:CO2'"
    ).fetchone()
    assert row == ("73,200",)
    assert (count(owner, "reference_factor_records"), count(owner, "reference_mappings")) == (600, 1)
    status = owner.execute("SELECT license_status FROM reference_sources WHERE id = 'kr-ets-byl12'").fetchone()
    assert status == ("unverified",)


def test_import_under_the_app_settings_stops_as_not_owner(owner: Owner) -> None:
    """앱 설정(앱 역할)으로 가져오기를 부르면 `not_owner` 로 멈춘다(권한 오류를 삼켜 「0건 들임」으로 끝내지 않는다)."""
    owner.execute(sql.SQL("TRUNCATE {} CASCADE").format(sql.SQL(", ").join(map(sql.Identifier, TABLES))))
    out = StringIO()
    with pytest.raises(CommandError, match=r"^not_owner: ") as stopped:
        call_command("import_factors", stdout=out)
    assert "주인 역할의 설정으로 돌린다" in str(stopped.value)
    assert out.getvalue() == ""  # 성공한 척하는 요약이 찍히지 않았다
    assert [count(owner, table) for table in TABLES] == [0, 0, 0, 0]
