# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 organization 0002·0003(밴드 K1b-1 ①): 사업장 행이 있는 DB(0001)에서 0002 가 서고 옛 행이 기본값
(본사 아님·인벤토리 켬·삭제 안 됨)이며, 0003 이 회사마다 본사를 정확히 하나 세운다(「본사」 이름 사업장이 있으면 그 행을
올린다). 0003 을 되돌리면 본사 표시만 걷히고 행은 남고, 다시 올려도 회사마다 하나다. 끝에 모든 앱을 맨 끝으로 올린다.

업무 층(진짜 DB, 주인 역할). transaction=True — 마이그레이션은 테스트 트랜잭션 밖에서 돈다. 이름·글은 지어낸 것이다.
"""

import importlib
from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from esgapi.organization.service.services.branches import HEADQUARTERS_NAME

pytestmark = pytest.mark.django_db(transaction=True)

INITIAL = ("organization", "0001_initial")
SCHEMA = ("organization", "0002_branches_facilities")
SEED = ("organization", "0003_headquarters_seed")


def migrate(*targets: tuple[str, str]) -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())


def sql(statement: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params or [])
        return cursor.fetchall() if cursor.description else []


def add_company(subdomain: str, licence: str) -> int:
    rows = sql(
        "INSERT INTO company (name, business_licence_number, subdomain, is_active, created_at, updated_at) "
        "VALUES (%s, %s, %s, true, now(), now()) RETURNING id",
        [f"{subdomain} 회사", licence, subdomain],
    )
    return int(rows[0][0])


def add_site(company_id: int, name: str) -> int:
    rows = sql(
        "INSERT INTO sites (company_id, name, created_at) VALUES (%s, %s, now()) RETURNING id", [company_id, name]
    )
    return int(rows[0][0])


def sites(company_id: int) -> list[tuple[Any, ...]]:
    return sql(
        "SELECT name, is_headquarters, inventory_enabled, deleted_at IS NULL FROM sites WHERE company_id = %s "
        "ORDER BY id",
        [company_id],
    )


@pytest.fixture
def back_to_the_leaf() -> Iterator[None]:
    yield
    migrate()  # 끝에 늘 다시 올린다(다음 시험이 0003 까지의 표를 본다)


def test_the_name_in_the_migration_is_the_service_name() -> None:
    seed = importlib.import_module("esgapi.organization.migrations.0003_headquarters_seed")
    assert seed.HEADQUARTERS_NAME == HEADQUARTERS_NAME == "본사"


@pytest.mark.usefixtures("back_to_the_leaf")
def test_old_rows_take_the_defaults_and_every_company_gets_one_headquarters() -> None:
    migrate(INITIAL)
    a = add_company("tenant-a", "111-11-11111")
    b = add_company("tenant-b", "222-22-22222")
    add_site(a, "가 공장")
    add_site(b, "나 공장")
    add_site(b, HEADQUARTERS_NAME)  # B 에는 「본사」 이름 사업장이 이미 있다 — 그 행을 올린다

    migrate(SCHEMA)
    # 옛 행은 기본값으로 채워졌고 본사는 아직 없다(0002 는 스키마만).
    assert sites(a) == [("가 공장", False, True, True)]
    assert sites(b) == [("나 공장", False, True, True), (HEADQUARTERS_NAME, False, True, True)]
    assert sql("SELECT count(*) FROM sites WHERE updated_at IS NULL") == [(0,)]

    migrate(SEED)
    assert sites(a) == [("가 공장", False, True, True), (HEADQUARTERS_NAME, True, True, True)]
    assert sites(b) == [("나 공장", False, True, True), (HEADQUARTERS_NAME, True, True, True)]  # 새 행 0

    # 되돌림: 본사 표시만 걷힌다(행은 남는다).
    migrate(SCHEMA)
    assert sql("SELECT count(*) FROM sites WHERE is_headquarters") == [(0,)]
    assert len(sites(a)) == len(sites(b)) == 2
    # 다시 올려도 회사마다 하나 — A 의 「본사」 행(앞에서 만든 것)을 다시 올린다(중복 0).
    migrate(SEED)
    assert sites(a) == [("가 공장", False, True, True), (HEADQUARTERS_NAME, True, True, True)]
    assert sites(b) == [("나 공장", False, True, True), (HEADQUARTERS_NAME, True, True, True)]


@pytest.mark.usefixtures("back_to_the_leaf")
def test_a_deleted_site_named_headquarters_is_not_raised_and_an_existing_headquarters_stays() -> None:
    migrate(SCHEMA)
    a = add_company("tenant-a", "111-11-11111")
    b = add_company("tenant-b", "222-22-22222")
    gone = add_site(a, HEADQUARTERS_NAME)
    sql("UPDATE sites SET deleted_at = now() WHERE id = %s", [gone])
    kept = add_site(b, "나 본점")
    sql("UPDATE sites SET is_headquarters = true WHERE id = %s", [kept])

    migrate(SEED)
    # A: 지운 「본사」 는 그대로(삭제 표시), 새 「본사」 하나. B: 이미 있는 본사(이름이 달라도) 그대로, 새 행 0.
    assert sites(a) == [(HEADQUARTERS_NAME, False, True, False), (HEADQUARTERS_NAME, True, True, True)]
    assert sites(b) == [("나 본점", True, True, True)]


@pytest.mark.usefixtures("back_to_the_leaf")
def test_the_schema_goes_back_to_0001_and_keeps_the_rows() -> None:
    migrate(SEED)
    a = add_company("tenant-a", "111-11-11111")
    add_site(a, "가 공장")
    migrate(INITIAL)
    columns = {row[0] for row in sql("SELECT column_name FROM information_schema.columns WHERE table_name = 'sites'")}
    assert columns == {"id", "company_id", "external_id", "name", "created_at"}
    assert sql("SELECT to_regclass('site_facilities'), to_regclass('organization_facility_codes')") == [(None, None)]
    assert sql("SELECT name FROM sites WHERE company_id = %s", [a]) == [("가 공장",)]
