# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""마이그레이션 0006(밴드 RM1b ② — T6): 칸 셋(parked_at·lease_expires_at·data_octets)과 CHECK 둘. 앞뒤로 옮겨 칸·제약이
서고 사라지는지, 옛 행(0005 의 직렬 done — data_octets NULL)이 지나는지, 한 방향 CHECK 가 무엇을 받고 무엇을 막는지,
0005 의 제약이 그대로인지 잰다. 값은 지어낸 것이다.
"""

from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)

BEFORE = ("runs", "0005_run_segments")
AFTER = ("runs", "0006_run_segment_lease")
NEW_CHECKS = {"run_segments_lease_running_check", "run_segments_data_octets_check"}
OLD_CHECKS = {
    "run_segments_status_check",
    "run_segments_position_check",
    "run_segments_attempts_check",
    "run_segments_key_sha256_check",
    "run_segments_status_fields_check",
    "run_segments_data_size_check",
}


def migrate(*targets: tuple[str, str]) -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())


def sql(statement: str, params: list[Any] | None = None) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(statement, params or [])
        return cursor.fetchall() if cursor.description else []


def columns(table: str) -> set[str]:
    rows = sql("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [table])
    return {str(row[0]) for row in rows}


def checks() -> set[str]:
    rows = sql("SELECT conname FROM pg_constraint WHERE conrelid = 'run_segments'::regclass AND contype = 'c'")
    return {str(row[0]) for row in rows}


def a_run(company_id: int) -> int:
    sql(
        "INSERT INTO run_runs (created_at, updated_at, company_id, module, flow_id, options, versions, purpose, "
        "status, attempts, stalled_attempts, created_by_user_id) "
        "VALUES (now(), now(), %s, 'probe', 'probe.segmented@1', '{}', '{}', 'service', 'processing', 1, 0, 7)",
        [company_id],
    )
    return int(sql("SELECT max(id) FROM run_runs")[0][0])


def a_segment(company_id: int, run_id: int, position: int, status: str, tail: str = "", values: str = "") -> None:
    data = "'{\"v\": 1}'" if status == "done" else "NULL"
    code = "'made_up'" if status == "failed" else "NULL"
    sql(
        "INSERT INTO run_segments (created_at, updated_at, company_id, run_id, step, position, kind, key, key_sha256, "
        f"status, attempts, data, error_code{tail}) VALUES (now(), now(), %s, %s, 'spread', %s, 'block', '{{}}', "
        f"%s, %s, 1, {data}, {code}{values})",
        [company_id, run_id, position, f"{position:064x}", status],
    )


def refused(statement: str) -> str:
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        sql(statement)
    cause: Any = caught.value.__cause__
    return str(cause.diag.constraint_name)


@pytest.fixture
def at_0005() -> Any:
    migrate(BEFORE)
    yield
    migrate()  # 다음 시험을 위해 잎으로


def test_0006_adds_three_null_columns_and_two_checks_and_reverses(companies: tuple[int, int], at_0005: Any) -> None:
    a, _ = companies
    assert "parked_at" not in columns("run_runs")
    assert {"lease_expires_at", "data_octets"} & columns("run_segments") == set()
    assert checks() == OLD_CHECKS
    run = a_run(a)
    a_segment(a, run, 0, "done")  # RM1a 직렬의 done(data_octets 칸이 아직 없다)
    a_segment(a, run, 1, "running")

    migrate(AFTER)
    assert "parked_at" in columns("run_runs")
    assert {"lease_expires_at", "data_octets"} <= columns("run_segments")
    assert checks() == OLD_CHECKS | NEW_CHECKS
    assert sql("SELECT parked_at FROM run_runs WHERE id = %s", [run]) == [(None,)]
    assert sql("SELECT lease_expires_at, data_octets FROM run_segments ORDER BY position") == [(None, None)] * 2

    migrate(BEFORE)
    assert "parked_at" not in columns("run_runs")
    assert checks() == OLD_CHECKS
    assert sql("SELECT count(*) FROM run_segments") == [(2,)]  # 행은 남는다


def test_the_lease_check_is_one_way_and_data_octets_belongs_to_done(companies: tuple[int, int], at_0005: Any) -> None:
    a, _ = companies
    migrate(AFTER)
    run = a_run(a)
    a_segment(a, run, 0, "running", ", lease_expires_at", ", now()")  # running·임대
    a_segment(a, run, 1, "running")  # running·임대 NULL(놓음·직렬) — 된다
    a_segment(a, run, 2, "done", ", data_octets", ", 9")
    a_segment(a, run, 3, "done")  # 직렬 done 은 NULL 그대로 — 된다
    assert sql("SELECT count(*) FROM run_segments") == [(4,)]
    base = (
        "INSERT INTO run_segments (created_at, updated_at, company_id, run_id, step, position, kind, key, key_sha256, "
        "status, attempts, data, error_code, {extra}) VALUES (now(), now(), {company}, {run}, 'spread', 9, 'block', "
        "'{{}}', '{sha}', {rest})"
    )
    sha = "f" * 64

    def row(extra: str, rest: str) -> str:
        return base.format(extra=extra, company=a, run=run, sha=sha, rest=rest)

    lease = "run_segments_lease_running_check"
    octets = "run_segments_data_octets_check"
    assert refused(row("lease_expires_at", "'done', 1, '{\"v\": 1}', NULL, now()")) == lease
    assert refused(row("lease_expires_at", "'pending', 0, NULL, NULL, now()")) == lease
    assert refused(row("lease_expires_at", "'failed', 1, NULL, 'x', now()")) == lease
    assert refused(row("data_octets", "'running', 1, NULL, NULL, 3")) == octets
    assert refused(row("data_octets", "'failed', 1, NULL, 'x', 3")) == octets
    assert refused(row("data_octets", "'done', 1, '{\"v\": 1}', NULL, -1")) == octets
    # 0005 의 제약은 그대로 선다
    assert refused(row("data_octets", "'done', 1, NULL, NULL, 3")) == "run_segments_status_fields_check"
