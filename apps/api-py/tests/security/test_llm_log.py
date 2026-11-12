"""호출 기록의 표(core_llm_call_logs)를 앱 역할로 잰다. 보안 층.

여기서 재는 것(업무 층은 주인 역할·롤백이라 못 재는 것):
  - 표가 회사 칸(company_id)의 표로 잡혀 test_owner.py 의 카탈로그 검사(정책 없음·GRANT)가 저절로 문다
  - 앱 역할은 읽고 덧붙이기만 한다: UPDATE·DELETE·TRUNCATE 가 없다
  - 행의 회사는 꼬리표(Tags.tenant 에 적힌 회사 id)의 것이고, 합계(spent)와 범위(for_company)는 그 회사의 줄만 센다
  - 꼬리표가 회사 id 의 꼴(십진 숫자 글자)이 아니면 쓰지 않는다. 트랜잭션 밖이면 싱크가 스스로 열어 쓰고 곧 커밋한다
  - 기록의 INSERT 가 실패해도 그 블록의 다른 쓰기가 커밋된다(세이브포인트)
  - 커밋된 행을 다른 연결이 센다(「프로세스를 넘는다」의 증거). 트랜잭션 밖에서도 표에 묻는다
  - 되돌려진 블록의 줄은 사라지고, 그 비용은 그 객체의 메모리 누계에만 남는다

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(분모를 센다).
회사 id 는 테스트마다 다르다(식별 열): 기록 줄은 record_of(회사 id) 로 짓는다.

무효 조건: 권한은 esg_app 역할로 잰 것이다. superuser 에게는 GRANT 가 걸리지 않는다.
"""

from dataclasses import replace
from decimal import Decimal
from typing import Any, cast

import psycopg
import pytest
from django.db import DatabaseError, connection, transaction

from esgapi.core.llm.log import CallRecord
from esgapi.core.llm.sink_db import DbSink, WriteFailed, Written
from esgapi.core.llm.types import Scope
from esgapi.core.models import LlmCallLogRow
from esgapi.organization.models import Site
from tests.security.conftest import count, tenant_tables
from tests.security.seed import LOG_INSERT, add_log

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
TABLE = "core_llm_call_logs"
PRIVILEGES = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]

RECORD = CallRecord(
    ts="2026-10-08T00:00:00.000Z",
    call_id="call-synthetic",
    attempt=0,
    provider="mock",
    model="mock-synthetic",
    api_model_id="mock-synthetic",
    response_model_id=None,
    prompt_id="t/plain@1",
    prompt_version=1,
    template_hash="a" * 64,
    request_hash="b" * 64,
    input_tokens=60,
    output_tokens=20,
    cache_read_tokens=0,
    cache_write_tokens=0,
    cost_usd=0.0001,
    duration_ms=12,
    result_kind="success",
    tenant="tenant-a",  # 꼴 밖(subdomain 글자)이다. 쓰는 줄은 record_of 로 회사 id 를 적는다
    module="scope3",
    warnings=(),
)


def record_of(company_id: int, **changes: Any) -> CallRecord:
    """RECORD 의 꼬리표를 그 회사 id 의 글자로(싱크가 받는 꼴)."""
    return replace(RECORD, tenant=str(company_id), **changes)


def bad_of(company_id: int) -> CallRecord:
    """CHECK(result_kind) 를 어기는 줄. 꼬리표는 옳아 싱크가 INSERT 를 시도하고 DB 가 거절한다."""
    return record_of(company_id, result_kind=cast("Any", "no-such-kind"))


# 싱크를 거치지 않는 날 INSERT 의 CHECK(result_kind) 를 어기는 꼴. 앱 역할의 연결로 넣어 DB 의 거절을 잰다.
BAD_RAW_INSERT = LOG_INSERT.replace("'success'", "'no-such-kind'")


def rows(owner: Owner) -> list[tuple[Any, ...]]:
    """주인 역할이 본 행 전부(분모)."""
    return owner.execute(f"SELECT company_id, module, result_kind FROM {TABLE} ORDER BY created_at").fetchall()


# ── 카탈로그와 권한 ──


def test_the_log_table_is_a_tenant_table_so_the_catalogue_checks_cover_it(owner: Owner) -> None:
    """test_owner.py 의 둘(정책·행 보안 없음 / SELECT 참·DELETE·TRUNCATE 거짓)은 tenant_tables 를 돈다."""
    assert TABLE in tenant_tables(owner)


def test_app_role_may_only_read_and_append(owner: Owner) -> None:
    held = owner.execute(
        "SELECT p, has_table_privilege('esg_app', %s, p) FROM unnest(%s::text[]) AS p", [TABLE, PRIVILEGES]
    ).fetchall()
    assert held == [
        ("SELECT", True),
        ("INSERT", True),
        ("UPDATE", False),
        ("DELETE", False),
        ("TRUNCATE", False),
        ("REFERENCES", False),
        ("TRIGGER", False),
    ]
    # 앱 역할은 superuser 도 표의 주인도 아니다(그렇다면 위의 답이 뜻이 없다).
    assert owner.execute(
        "SELECT rolsuper, rolbypassrls, (SELECT tableowner FROM pg_tables WHERE tablename = %s) = rolname "
        "FROM pg_roles WHERE rolname = 'esg_app'",
        [TABLE],
    ).fetchone() == (False, False, False)


@pytest.mark.parametrize(
    "statement",
    [
        f"UPDATE {TABLE} SET cost_usd = 0",
        f"DELETE FROM {TABLE}",
        f"TRUNCATE {TABLE}",
        f"UPDATE {TABLE} SET step = 'x'",  # AD4D: 단계 칸도 고치지 못한다(칸 단위 GRANT 0)
    ],
    ids=["update", "delete", "truncate", "update_step"],
)
def test_app_role_cannot_change_or_remove_a_log_line(owner: Owner, companies: tuple[int, int], statement: str) -> None:
    add_log(owner, companies[0], "scope3", "0.0001")
    with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(statement)
    assert getattr(caught.value.__cause__, "sqlstate", None) == "42501"  # insufficient_privilege
    assert owner.execute(f"SELECT cost_usd::text FROM {TABLE}").fetchall() == [("0.00010000",)]


# ── 격리 ──


def test_a_line_is_seen_only_inside_its_own_tenant(owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    sink = DbSink()
    with transaction.atomic():
        sink.record(record_of(a))
    assert sink.outcomes == (Written(),)
    assert rows(owner) == [(a, "scope3", "success")]
    add_log(owner, b, "scope3", "0.0004")  # 다른 프로세스가 쓴 B 의 줄
    assert count(owner, TABLE) == 2  # 분모: 주인이 센 2행(A 1, B 1)

    with transaction.atomic():
        assert list(LlmCallLogRow.for_company(a).values_list("company_id", "cost_usd")) == [(a, Decimal("0.00010000"))]
        assert list(LlmCallLogRow.for_company(b).values_list("company_id", "cost_usd")) == [(b, Decimal("0.00040000"))]
        fresh = DbSink()  # 메모리 누계 0: 표의 합계만 본다
        assert fresh.spent(Scope(tenant=str(a))) == 0.0001  # B 의 0.0004 는 들지 않는다
        assert fresh.spent(Scope(tenant=str(b))) == 0.0004  # A 의 0.0001 은 들지 않는다
        assert LlmCallLogRow.unscoped.count() == 2  # 분모: 범위 밖에서 세면 둘


def test_a_bad_tag_writes_nothing_and_outside_a_transaction_the_sink_commits(
    owner: Owner, companies: tuple[int, int]
) -> None:
    """트랜잭션 밖이면 싱크가 스스로 짧은 트랜잭션을 열어 쓰고 곧 커밋한다(주인의 연결이 본다). 꼬리표가 회사 id 의
    꼴이 아니면 안팎 없이 NoTenant 이고 INSERT 를 시도하지 않는다.
    """
    sink = DbSink()
    assert count(owner, TABLE) == 0  # 분모: 쓰기 전
    assert not connection.in_atomic_block
    sink.record(record_of(companies[0]))  # 트랜잭션 밖
    assert sink.outcomes == (Written(),)
    assert count(owner, TABLE) == 1  # 커밋됐다: 다른 연결(주인)이 본다
    sink.record(replace(RECORD, tenant="Tenant A"))  # 꼴이 틀린 꼬리표
    with transaction.atomic():
        sink.record(replace(RECORD, tenant=""))  # 빈 꼬리표(트랜잭션 안)
    assert [outcome.kind for outcome in sink.outcomes] == ["written", "no_tenant", "no_tenant"]
    assert count(owner, TABLE) == 1


def test_the_row_is_stored_under_the_tag_company(owner: Owner, companies: tuple[int, int]) -> None:
    """행의 회사는 꼬리표의 것이다(트랜잭션에 실린 회사가 없다. sink_db.py 의 머리말)."""
    a, b = companies
    sink = DbSink()
    with transaction.atomic():
        sink.record(record_of(b))
    assert sink.outcomes == (Written(),)
    assert rows(owner) == [(b, "scope3", "success")]
    with transaction.atomic():
        assert LlmCallLogRow.for_company(a).count() == 0  # 다른 회사의 범위에는 없다
        assert LlmCallLogRow.unscoped.count() == 1  # 분모


def test_a_rejected_insert_in_a_savepoint_keeps_the_outer_alive(owner: Owner, companies: tuple[int, int]) -> None:
    a, b = companies
    sink = DbSink()
    with transaction.atomic():
        with pytest.raises(DatabaseError) as caught, transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(BAD_RAW_INSERT, [b, "scope3", "0.0001"])
        assert getattr(caught.value.__cause__, "sqlstate", None) == "23514"  # CHECK(result_kind) 가 거절했다
        # 세이브포인트 안이었으므로 바깥은 살아 있다: 옳은 줄이 쓰이고 커밋된다.
        sink.record(record_of(a))
    assert sink.outcomes == (Written(),)
    assert rows(owner) == [(a, "scope3", "success")]


# ── 기록이 실패해도 요청은 산다 ──


def test_a_failed_log_insert_does_not_take_the_request_down_with_it(owner: Owner, companies: tuple[int, int]) -> None:
    """한 트랜잭션(= 블록 하나)에서: 업무 쓰기 → 실패하는 기록 → 커밋. 업무 쓰기가 남는다."""
    sink = DbSink()
    with transaction.atomic():
        Site.unscoped.create(company_id=companies[0], name="A 본사")
        sink.record(bad_of(companies[0]))
        # 실패한 뒤에도 같은 트랜잭션에서 읽고 쓸 수 있다.
        assert Site.unscoped.count() == 1
    assert sink.outcomes == (WriteFailed(error_class="IntegrityError", sqlstate="23514"),)
    assert count(owner, "sites") == 1  # 분모: 주인이 센 것
    assert count(owner, TABLE) == 0


def test_a_line_in_a_block_that_rolls_back_is_lost_but_the_object_remembers_the_cost(
    owner: Owner, companies: tuple[int, int]
) -> None:
    """★ 무효 조건을 사실로 잰다. 바깥 블록 안에서 쓴 기록 줄은 그 블록이 되돌려지면 같이 사라진다(그래서 LLM 호출을
    블록 안에서 하지 않는다). 돈은 이미 나갔다. 그 비용을 아는 것은 이 프로세스의 이 객체뿐이다.
    """
    a, _ = companies
    sink = DbSink()
    with transaction.atomic():
        sink.record(record_of(a))
        assert LlmCallLogRow.unscoped.count() == 1
        transaction.set_rollback(True)
    assert sink.outcomes == (Written(),)  # 쓰였다가 되돌려졌다
    assert count(owner, TABLE) == 0

    with transaction.atomic():
        assert sink.spent(Scope(tenant=str(a))) == 0.0001  # 같은 객체: 메모리 누계
        assert DbSink().spent(Scope(tenant=str(a))) == 0  # 다른 객체(= 다른 일꾼): 아무도 모른다


# ── 커밋된 행은 연결을 넘어 센다 ──


def test_a_new_sink_counts_rows_committed_by_another_connection(owner: Owner, companies: tuple[int, int]) -> None:
    """「프로세스를 넘는다」의 증거: 행을 쓴 것은 주인의 연결(다른 프로세스인 셈)이고, 세는 것은 앱 역할의 새 객체다.
    for_company 의 조건을 거친 SELECT 길도 같이 잰다.
    """
    a, b = companies
    add_log(owner, a, "scope3", "0.0001")
    add_log(owner, a, "translate", "0.0002")
    add_log(owner, b, "scope3", "0.0004")
    assert count(owner, TABLE) == 3

    fresh = DbSink()  # 메모리 누계 0
    with transaction.atomic():
        assert fresh.spent(Scope(tenant=str(a))) == 0.0003  # B 의 0.0004 는 들지 않는다
        assert fresh.spent(Scope(tenant=str(a), module="scope3")) == 0.0001
        assert fresh.spent(Scope(tenant=str(b))) == 0.0004  # 범위의 회사마다 표에 묻는다(꼬리표가 고른다)
        assert fresh.spent(Scope()) == 0  # 전역: 메모리 누계만
    with transaction.atomic():  # 다른 트랜잭션: 연결에 실린 것이 없어 같은 합이다
        assert fresh.spent(Scope(tenant=str(a))) == 0.0003
    assert fresh.spent(Scope(tenant=str(a))) == 0.0003  # 트랜잭션 밖에서도 표에 묻는다


# ── 단계 칸(AD4D — core 0002) ──


def test_app_role_appends_and_reads_a_line_with_a_step(owner: Owner, companies: tuple[int, int]) -> None:
    """앱 역할이 단계 이름이 든 줄을 넣고 읽는다(새 칸도 표 단위 SELECT, INSERT 에 든다). 고치기는 위의 update_step."""
    a, _ = companies
    sink = DbSink()
    sink.record(record_of(a, run_id="42", step="judge", call_id="call-step"))
    sink.record(record_of(a, run_id="42", call_id="call-between"))
    assert sink.outcomes == (Written(), Written())
    assert owner.execute(f"SELECT call_id, step FROM {TABLE} ORDER BY call_id").fetchall() == [
        ("call-between", None),
        ("call-step", "judge"),
    ]
    with transaction.atomic():
        seen = dict(LlmCallLogRow.for_company(a).values_list("call_id", "step"))
    assert seen == {"call-step": "judge", "call-between": None}
    assert owner.execute("SELECT has_column_privilege('esg_app', %s, 'step', 'UPDATE')", [TABLE]).fetchone() == (False,)
