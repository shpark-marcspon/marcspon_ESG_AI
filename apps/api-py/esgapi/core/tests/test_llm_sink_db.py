"""호출 기록의 DB 싱크(esgapi/core/llm/sink_db.py). 업무 층.

★ 여기서 재는 것은 싱크의 동작이다: 왕복, 갈래 셋, 합계의 WHERE(for_company), 메모리 누계, 설정과 관리 명령.
  진짜 커밋·롤백은 보안 층(tests/security/test_llm_log.py)이 잰다.
  테스트마다 pytest-django 의 트랜잭션 안이다. 행의 회사(company_id)는 꼬리표(Tags.tenant. 기록의 tenant — 회사 id 의
  십진 숫자 글자)에서 온다. 회사 id 는 고정물(companies)이 준다:
  기록(RECORD 등)은 `of(<기록>, <회사 id>)` 로 꼬리표를 단다.
  연결에 싣는 테넌트는 없다(RLS 를 걷어냈다). 이 연결은 모든 회사의 행을 본다: 거르는 것은 WHERE 뿐이다.
  「트랜잭션 밖」(싱크가 스스로 열어 줄마다 커밋)은 여기서 잴 수 없다(테스트의 트랜잭션을 벗어나지 못한다).
  보안 층이 잰다.
"""

import io
import json
import logging
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast, get_args

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from esgapi.config.env import LlmSettings
from esgapi.core.llm.budget import BudgetExhausted, BudgetGuard, BudgetLimit
from esgapi.core.llm.errors import LiveSetupError
from esgapi.core.llm.log import MISSING, CallRecord, RecordBody
from esgapi.core.llm.setup import build_client, make_sink
from esgapi.core.llm.sink_db import (
    BadRun,
    BadStep,
    DbSink,
    NoTenant,
    WriteFailed,
    Written,
    record_from_row,
)
from esgapi.core.llm.types import LlmResultKind, Scope, Tags
from esgapi.core.management.commands import llm_call
from esgapi.core.models import LLM_RESULT_KINDS, LlmCallLogRow
from esgapi.core.tests.test_llm_sinks import RECORD

pytestmark = pytest.mark.django_db

FULL = replace(
    RECORD,
    attempt=3,
    response_model_id="mock-synthetic-2026",
    thinking_tokens=0,
    error_status=503,
    retry_after_ms=7000,
    provider_retry=1,
    previous_error_status=429,
    retry_wait_ms=7000.5,
    duration_ms=12.25,
    result_kind="provider_error",
    warnings=("cache_not_applied", "usage_unreported"),
)
# 상태 코드 없이 실패한 줄: 두 칸이 「있고 None」이다(칸 없음이 아니다).
NO_STATUS = replace(RECORD, error_status=None, provider_retry=1, previous_error_status=None, retry_wait_ms=1000)
# 공급사를 부르기 전에 상한에 막힌 줄: 공급사·모델·토큰·비용이 전부 None.
BLOCKED = replace(
    RECORD,
    provider=None,
    model=None,
    api_model_id=None,
    input_tokens=None,
    output_tokens=None,
    cache_read_tokens=None,
    cache_write_tokens=None,
    cost_usd=None,
    result_kind="budget_exceeded",
    warnings=(),
)
# CHECK(result_kind) 를 어기는 줄. DB 가 거절한다.
BAD = replace(RECORD, result_kind=cast("Any", "no-such-kind"))


def of(record: CallRecord, company_id: int) -> CallRecord:
    """그 회사 id 의 글자를 꼬리표로 단 기록(행의 company_id 가 된다)."""
    return replace(record, tenant=str(company_id))


def seed(company_id: int, module: str, cost_usd: float | None) -> None:
    """다른 싱크 객체로 행을 심는다(다른 프로세스가 쓴 행인 셈이다). 행의 회사는 꼬리표다."""
    DbSink().record(replace(RECORD, tenant=str(company_id), module=module, cost_usd=cost_usd))


def test_result_kinds_in_the_model_match_the_call_layer() -> None:
    """CHECK 제약이 굳힌 갈래와 호출 층의 갈래가 같다. 갈래를 더하고 마이그레이션을 안 내면 여기서 빨개진다."""
    assert get_args(LlmResultKind) == LLM_RESULT_KINDS


# ── 왕복 ──


@pytest.mark.parametrize("record", [RECORD, FULL, NO_STATUS, BLOCKED], ids=["plain", "full", "no-status", "blocked"])
def test_a_record_survives_the_round_trip_through_the_table(record: CallRecord, companies: tuple[int, int]) -> None:
    record = of(record, companies[0])
    sink = DbSink()
    sink.record(record)
    assert sink.outcomes == (Written(),)
    row = LlmCallLogRow.unscoped.get()
    back = record_from_row(row)
    assert back.to_json() == record.to_json()
    # 열쇠의 차례와 「칸 없음」도 같다(JSON 글자로 견준다. 수는 float 칸을 거쳐 12 가 12.0 이 되므로 값으로만 같다).
    assert list(back.to_json()) == list(record.to_json())
    assert (back.error_status is MISSING, back.previous_error_status is MISSING) == (
        record.error_status is MISSING,
        record.previous_error_status is MISSING,
    )
    # ts 는 밀리초·Z 꼴 그대로 돌아온다.
    assert back.ts == record.ts
    assert (row.company_id, back.tenant, row.created_at is not None) == (companies[0], str(companies[0]), True)


def test_ts_with_real_milliseconds_comes_back_as_the_same_text(companies: tuple[int, int]) -> None:
    a, _ = companies
    DbSink().record(replace(of(RECORD, a), ts="2026-10-08T01:02:03.456Z"))
    assert record_from_row(LlmCallLogRow.unscoped.get()).ts == "2026-10-08T01:02:03.456Z"


def test_missing_and_none_are_kept_apart_in_the_row(companies: tuple[int, int]) -> None:
    a, _ = companies
    sink = DbSink()
    sink.record(of(RECORD, a))
    sink.record(replace(of(NO_STATUS, a), attempt=1))
    plain, no_status = LlmCallLogRow.unscoped.order_by("attempt")
    assert (plain.has_error_status, plain.error_status) == (False, None)
    assert (no_status.has_error_status, no_status.error_status) == (True, None)
    assert (no_status.has_previous_error_status, no_status.previous_error_status) == (True, None)


def test_a_body_is_never_written_and_dropping_it_is_logged(
    caplog: pytest.LogCaptureFixture, companies: tuple[int, int]
) -> None:
    """build_client 의 문을 지나지 않고 본문이 든 기록이 와도 본문은 DB 에 가지 않는다(칸이 없다)."""
    a, _ = companies
    sink = DbSink()
    with caplog.at_level(logging.WARNING, logger="esgapi.core.llm.sink_db"):
        sink.record(replace(of(RECORD, a), body=RecordBody(request={"secret": "고객 본문"}, response_text="답")))
    assert sink.outcomes == (Written(),)
    assert "body" not in record_from_row(LlmCallLogRow.unscoped.get()).to_json()
    assert "본문을 버렸다" in caplog.text
    assert "고객 본문" not in caplog.text


# ── 갈래 셋 ──


def test_written(companies: tuple[int, int]) -> None:
    a, _ = companies
    sink = DbSink()
    sink.record(of(RECORD, a))
    assert sink.outcomes == (Written(),)
    assert LlmCallLogRow.unscoped.count() == 1


def test_the_row_is_stored_under_the_tag_company(caplog: pytest.LogCaptureFixture, companies: tuple[int, int]) -> None:
    """행의 회사는 꼬리표다. 견줄 세션의 회사가 없어 틀린 꼬리표도 알리는 갈래가 없다(sink_db.py 의 무효 조건)."""
    _, b = companies
    sink = DbSink()
    with caplog.at_level(logging.WARNING, logger="esgapi.core.llm.sink_db"):
        sink.record(of(RECORD, b))
    assert sink.outcomes == (Written(),)
    row = LlmCallLogRow.unscoped.get()
    assert (row.company_id, record_from_row(row).tenant) == (b, str(b))
    assert [line for line in caplog.records if line.name == "esgapi.core.llm.sink_db"] == []


def test_a_bad_tag_writes_nothing_and_the_line_goes_to_the_log(caplog: pytest.LogCaptureFixture) -> None:
    """NoTenant 는 꼬리표의 꼴이 틀릴 때뿐이다(트랜잭션 안팎은 가르지 않는다)."""
    sink = DbSink()
    with caplog.at_level(logging.WARNING, logger="esgapi.core.llm.sink_db"):
        sink.record(replace(RECORD, tenant="Tenant A"))  # 회사 id 의 꼴이 아니다(숫자 글자가 아니다)
    assert sink.outcomes == (NoTenant(),)
    assert LlmCallLogRow.unscoped.count() == 0
    # 쓰지 못한 줄은 logging 에만 남는다: to_json() 그대로.
    assert '"callId":"call-synthetic"' in caplog.text
    assert "no_tenant" in caplog.text

    # 빈 꼬리표도 같다.
    sink.record(replace(RECORD, tenant=""))
    assert sink.outcomes == (NoTenant(), NoTenant())
    assert LlmCallLogRow.unscoped.count() == 0


@pytest.mark.parametrize(
    "tag", ["0", "-1", "01", "1.0", "", " 1", "1 ", "1\n", "+1", "1e3", "tenant-a", "１", "1" * 20], ids=repr
)
def test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing(tag: str) -> None:
    """꼬리표는 회사 id 의 십진 숫자 글자(^[1-9][0-9]{0,18}$)만 받는다. 밖이면 NoTenant: 쓰는 문도 묻는 문도 0."""
    sink = DbSink()
    with CaptureQueriesContext(connection) as captured:
        sink.record(replace(RECORD, tenant=tag))
        assert sink.spent(Scope(tenant=tag)) == 0.0001  # 메모리 누계만(그 꼬리표의 열쇠)
    assert sink.outcomes == (NoTenant(),)
    assert captured.captured_queries == []
    assert LlmCallLogRow.unscoped.count() == 0


def test_a_rejected_insert_is_reported_and_the_next_record_is_still_written(companies: tuple[int, int]) -> None:
    """세이브포인트가 하는 일: 거절된 INSERT 뒤에도 같은 트랜잭션을 쓸 수 있다."""
    a, _ = companies
    sink = DbSink()
    sink.record(of(BAD, a))
    assert sink.outcomes == (WriteFailed(error_class="IntegrityError", sqlstate="23514"),)
    assert LlmCallLogRow.unscoped.count() == 0
    # 그 뒤 같은 트랜잭션에서 다음 기록이 쓰인다(꼬리표의 회사로).
    sink.record(of(RECORD, a))
    assert sink.outcomes[-1] == Written()
    assert LlmCallLogRow.unscoped.get().company_id == a


@pytest.mark.parametrize(
    ("record", "error_class", "sqlstate"),
    [
        (replace(RECORD, call_id="c" * 65), "DataError", "22001"),  # 칸보다 긴 글자: 자르지 않는다
        (replace(RECORD, attempt=-1), "IntegrityError", "23514"),
        (replace(RECORD, ts="어제"), "ValueError", None),  # DB 에 가기 전에 난 것
    ],
    ids=["too-long", "negative-attempt", "bad-ts"],
)
def test_other_rejections_are_write_failed_too(
    record: CallRecord, error_class: str, sqlstate: str | None, companies: tuple[int, int]
) -> None:
    a, _ = companies
    sink = DbSink()
    sink.record(of(record, a))
    assert sink.outcomes == (WriteFailed(error_class=error_class, sqlstate=sqlstate),)
    assert LlmCallLogRow.unscoped.count() == 0
    sink.record(of(RECORD, a))
    assert LlmCallLogRow.unscoped.count() == 1


def test_inside_an_already_broken_transaction_record_and_spent_do_not_raise(companies: tuple[int, int]) -> None:
    a, _ = companies
    sink = DbSink()
    sink.record(of(RECORD, a))
    with transaction.atomic():
        transaction.set_rollback(True)  # 이 블록은 되돌려질 것이고, 그 전까지 조회를 받지 않는다
        sink.record(replace(of(RECORD, a), attempt=1))
        assert sink.outcomes[-1] == WriteFailed(error_class="TransactionManagementError", sqlstate=None)
        # spent 도 던지지 않고 메모리 누계를 준다(두 줄의 비용).
        assert sink.spent(Scope(tenant=str(a))) == 0.0002
    assert LlmCallLogRow.unscoped.count() == 1


def test_only_the_latest_outcomes_are_kept(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> None:
    a, _ = companies
    monkeypatch.setattr("esgapi.core.llm.sink_db.OUTCOMES_KEPT", 3)
    sink = DbSink()
    for _ in range(5):
        sink.record(of(RECORD, a))  # 쓰인다(Written). 목록은 셋만 남는다
    assert len(sink.outcomes) == 3
    # 누계는 목록이 아니라 합이다: 다섯 줄이 다 들어 있다.
    assert sink.spent(Scope()) == 0.0005


# ── 합계 ──


def test_the_tenant_sum_reads_only_that_tenant_and_that_module_from_the_table(companies: tuple[int, int]) -> None:
    """★ WHERE 가 하는 일. 이 연결은 두 회사의 행을 다 본다: 거르는 것은 for_company 의 WHERE 뿐이다."""
    a, b = companies
    seed(a, "scope3", 0.0001)
    seed(a, "translate", 0.0002)
    seed(b, "scope3", 0.0004)
    seed(a, "scope3", None)  # 비용이 없는 줄(오류·시간 초과·상한에 막힌 줄)은 0 으로
    assert LlmCallLogRow.unscoped.count() == 4

    fresh = DbSink()  # 메모리 누계 0: 아래 값은 전부 표에서 온다
    assert fresh.spent(Scope(tenant=str(a))) == 0.0003
    assert fresh.spent(Scope(tenant=str(a), module="scope3")) == 0.0001
    assert fresh.spent(Scope(tenant=str(a), module="nothing")) == 0
    # 어느 회사든 표에 묻는다. 답은 그 회사의 행만이다(A 의 0.0003 이 섞이지 않는다).
    assert fresh.spent(Scope(tenant=str(b))) == 0.0004
    assert fresh.spent(Scope(tenant=str(b), module="translate")) == 0  # A 의 translate 0.0002 가 있다
    # 숫자 id 의 이웃(±1·±2)으로 물어도 남의 행이 섞이지 않는다(없는 회사는 0).
    others = [n for n in range(min(a, b) - 2, max(a, b) + 3) if n > 0 and n not in (a, b)]
    assert others  # 분모
    assert [fresh.spent(Scope(tenant=str(n))) for n in others] == [0] * len(others)
    # 전역·모듈만의 범위는 묻지 않는다: 메모리 누계만.
    assert fresh.spent(Scope()) == 0
    assert fresh.spent(Scope(module="scope3")) == 0


def test_an_empty_tenant_scope_does_not_ask_the_table(companies: tuple[int, int]) -> None:
    """빈 글자·꼴 밖의 범위는 메모리 누계만이다(for_company 는 양의 정수만 받아 묻지 않는다)."""
    a, _ = companies
    seed(a, "scope3", 0.0001)
    assert LlmCallLogRow.unscoped.count() == 1  # 물었다면 0.0001 이 나온다
    assert DbSink().spent(Scope(tenant="")) == 0
    for text in (f"0{a}", f"{a}.0", f" {a}", "tenant-a"):  # 꼴 밖: 표에 묻지 않는다(묻는 문 0)
        with CaptureQueriesContext(connection) as captured:
            assert DbSink().spent(Scope(tenant=text)) == 0, text
        assert captured.captured_queries == [], text


def test_the_global_scope_is_the_memory_total_of_this_object(companies: tuple[int, int]) -> None:
    a, b = companies
    seed(b, "scope3", 0.0004)  # 다른 객체가 쓴 행
    sink = DbSink()
    sink.record(of(RECORD, a))
    sink.record(replace(of(RECORD, a), module="translate", cost_usd=0.0002))
    assert sink.spent(Scope()) == 0.0003
    assert sink.spent(Scope(module="translate")) == 0.0002


def test_unwritten_lines_still_count_towards_spent(companies: tuple[int, int]) -> None:
    """돈은 이미 나갔다. 쓰지 못한 줄(NoTenant·WriteFailed)의 비용도 메모리 누계에 든다."""
    a, _ = companies
    sink = DbSink()
    sink.record(replace(RECORD, tenant="Tenant A"))  # 꼴이 틀린 꼬리표 → NoTenant. 열쇠는 꼬리표(Tenant A)
    sink.record(replace(of(BAD, a), cost_usd=0.0002))  # WriteFailed. 열쇠는 꼬리표(A 의 id)
    assert [outcome.kind for outcome in sink.outcomes] == ["no_tenant", "write_failed"]
    assert LlmCallLogRow.unscoped.count() == 0
    assert sink.spent(Scope(tenant=str(a))) == 0.0002  # 꼴이 틀린 꼬리표의 0.0001 은 그 꼬리표의 열쇠로 갔다
    assert sink.spent(Scope()) == 0.0003
    assert sink.spent(Scope(tenant="Tenant A")) == 0.0001  # 그 열쇠의 몫(돈은 사라지지 않았다)


def test_the_answer_is_the_larger_of_the_table_and_the_memory(companies: tuple[int, int]) -> None:
    a, _ = companies
    seed(a, "scope3", 0.0001)  # 다른 객체가 쓴 행
    sink = DbSink()
    assert sink.spent(Scope(tenant=str(a))) == 0.0001  # 표가 크다
    sink.record(replace(of(BAD, a), cost_usd=0.0005))  # 쓰지 못했다: 메모리에만 있다
    assert sink.spent(Scope(tenant=str(a))) == 0.0005  # 메모리가 크다(더하지 않는다. 둘 다 하한이다)


# ── BudgetGuard 와 같이 ──


def test_rows_written_by_another_sink_object_exhaust_the_budget_of_a_new_one(companies: tuple[int, int]) -> None:
    """객체를 넘는다(같은 연결·같은 트랜잭션이다. 프로세스를 넘는 증거는 보안 층에 있다)."""
    a, _ = companies
    limit = BudgetLimit(scope=Scope(tenant=str(a)), limit_usd=0.0002)
    tags = Tags(tenant=str(a), module="scope3")
    other = DbSink()
    other.record(of(RECORD, a))
    # 넘기 직전은 통과한다.
    assert BudgetGuard([limit], DbSink()).check(tags) is None
    other.record(replace(of(RECORD, a), attempt=1))
    exhausted = BudgetGuard([limit], DbSink()).check(tags)
    assert isinstance(exhausted, BudgetExhausted)
    assert exhausted.spent_usd == 0.0002


def test_a_wrong_tag_counts_against_the_limit_of_the_tagged_company(companies: tuple[int, int]) -> None:
    """★ 행·누계·상한이 다 꼬리표로 간다(budget.py 도 상한을 꼬리표로 고른다).

    A 의 일에서 꼬리표를 B 로 준 호출의 비용은 B 의 상한을 채우고, A 의 상한은 보지 못한다.
    꼬리표를 세션에서 만드는 일은 호출하는 모듈의 거리다(sink_db.py 의 머리말).
    """
    a, b = companies
    limits = [
        BudgetLimit(scope=Scope(tenant=str(a)), limit_usd=0.0001),
        BudgetLimit(scope=Scope(tenant=str(b)), limit_usd=0.0001),
    ]
    sink = DbSink()
    sink.record(of(RECORD, b))  # 꼬리표가 틀린 호출. 행과 누계는 B 의 것
    assert LlmCallLogRow.unscoped.get().company_id == b
    guard = BudgetGuard(limits, sink)
    exhausted = guard.check(Tags(str(b), "scope3"))
    assert isinstance(exhausted, BudgetExhausted)  # 꼬리표의 회사가 막힌다
    assert (exhausted.limit, exhausted.spent_usd) == (limits[1], 0.0001)
    assert guard.check(Tags(str(a), "scope3")) is None  # 진짜 회사의 상한은 그 비용을 못 본다


# ── 설정 ──


def test_make_sink_builds_the_db_sink_and_bodies_are_refused() -> None:
    settings = LlmSettings(log_sink="db")
    assert isinstance(make_sink(settings), DbSink)
    with pytest.raises(LiveSetupError, match="본문"):
        build_client(settings, mock=True, store_bodies=True)
    # 넘겨받은 싱크가 DB 싱크여도 같다.
    with pytest.raises(LiveSetupError, match="본문"):
        build_client(LlmSettings(), mock=True, sink=DbSink(), store_bodies=True)
    # 다른 싱크는 본문을 받는다.
    build_client(LlmSettings(), mock=True, store_bodies=True)


# ── 관리 명령 ──

HELLO = ("--prompt", "core/hello@1", "--var", "name=김", "--route", "mock", "--mock-text", '{"ok":true}')


def run(*args: str) -> tuple[int, str, str]:
    """(종료 코드, 표준 출력, 표준 오류)."""
    out, err = io.StringIO(), io.StringIO()
    try:
        call_command("llm_call", *args, stdout=out, stderr=err)
    except CommandError as error:
        return error.returncode, str(error), err.getvalue()
    except SystemExit as exit_:
        return int(exit_.code or 0), out.getvalue(), err.getvalue()
    return 0, out.getvalue(), err.getvalue()


@pytest.fixture
def memory_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """명령이 읽는 설정을 기본값(싱크 memory)으로 고정한다. 환경에 무엇이 있든 --sink 만 본다."""
    monkeypatch.setattr(llm_call, "app_config", lambda: SimpleNamespace(llm=LlmSettings()))


@pytest.mark.usefixtures("memory_default")
def test_command_writes_one_row_for_the_given_tenant(companies: tuple[int, int]) -> None:
    a, _ = companies
    code, output, errors = run(*HELLO, "--sink", "db", "--tenant", str(a), "--module", "scope3")
    assert (code, errors) == (0, "")
    assert json.loads(output)["kind"] == "success"
    row = LlmCallLogRow.unscoped.get()
    assert (row.company_id, record_from_row(row).tenant, row.module, row.result_kind, row.provider) == (
        a,
        str(a),
        "scope3",
        "success",
        "mock",
    )
    assert json.loads(output)["meta"]["callId"] == row.call_id


@pytest.mark.usefixtures("memory_default")
def test_command_reads_the_sink_from_settings_too(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> None:
    a, _ = companies
    monkeypatch.setattr(llm_call, "app_config", lambda: SimpleNamespace(llm=LlmSettings(log_sink="db")))
    code, _, _ = run(*HELLO, "--tenant", str(a))
    assert code == 0
    assert LlmCallLogRow.unscoped.count() == 1


@pytest.mark.usefixtures("memory_default")
def test_command_keeps_the_row_of_a_call_that_did_not_succeed(companies: tuple[int, int]) -> None:
    """답을 심지 않은 모의 공급사는 provider_error 다. 종료 1 이지만 기록 줄은 남는다(명령이 커밋한다)."""
    a, _ = companies
    code, output, errors = run(
        "--prompt", "core/hello@1", "--var", "name=김", "--route", "mock", "--sink", "db", "--tenant", str(a)
    )
    assert (code, errors) == (1, "")
    assert json.loads(output)["kind"] == "provider_error"
    kinds = set(LlmCallLogRow.unscoped.values_list("result_kind", flat=True))
    assert kinds == {"provider_error"}


@pytest.mark.usefixtures("memory_default")
def test_command_refuses_the_db_sink_without_an_explicit_tenant() -> None:
    code, output, _ = run(*HELLO, "--sink", "db")
    assert code == 2
    assert "--tenant" in output
    assert LlmCallLogRow.unscoped.count() == 0


@pytest.mark.usefixtures("memory_default")
def test_command_refuses_bodies_with_the_db_sink(companies: tuple[int, int]) -> None:
    a, _ = companies
    code, output, _ = run(*HELLO, "--sink", "db", "--tenant", str(a), "--store-bodies")
    assert code == 2
    assert "LiveSetupError" in output
    assert LlmCallLogRow.unscoped.count() == 0


@pytest.mark.usefixtures("memory_default")
def test_command_dry_run_needs_no_tenant_and_writes_nothing() -> None:
    code, output, _ = run(*HELLO, "--sink", "db", "--dry-run")
    assert code == 0
    assert json.loads(output)["dryRun"] is True
    assert LlmCallLogRow.unscoped.count() == 0


@pytest.mark.usefixtures("memory_default")
def test_command_reports_a_line_that_was_not_written(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    """기록이 Written 이 아니면 stderr 에 갈래 이름 한 줄, 종료 1. 여기서는 모듈 이름이 칸보다 길다."""
    a, _ = companies
    code, output, errors = run(*HELLO, "--sink", "db", "--tenant", str(a), "--module", "m" * 101)
    assert code == 1
    assert json.loads(output)["kind"] == "success"  # 호출은 성공했고 돈도 나갔다. 기록만 못 남았다
    assert "write_failed" in errors
    assert LlmCallLogRow.unscoped.count() == 0


# ── 실행 id(X1b-1 — CallRecord.run_id → 행의 run_id) ──


def test_a_run_id_survives_the_round_trip_and_a_line_without_one_stays_null(companies: tuple[int, int]) -> None:
    a, _ = companies
    sink = DbSink()
    with_run = replace(of(RECORD, a), run_id="42", call_id="call-run")
    sink.record(with_run)
    sink.record(replace(of(RECORD, a), call_id="call-plain"))
    assert sink.outcomes == (Written(), Written())
    rows = {row.call_id: row for row in LlmCallLogRow.for_company(a)}
    assert (rows["call-run"].run_id, rows["call-plain"].run_id) == (
        42,
        None,
    )  # 외래 키가 아니다: 없는 실행 id 도 남는다
    back = record_from_row(rows["call-run"])
    assert back.to_json() == with_run.to_json()
    assert list(back.to_json())[-1] == "runId"  # 있을 때만 있는 칸(끝)
    assert "runId" not in record_from_row(rows["call-plain"]).to_json()


@pytest.mark.parametrize("run_id", ["0", "01", "-1", "", "run-1", "1" * 20], ids=repr)
def test_a_run_id_outside_the_decimal_shape_writes_nothing(companies: tuple[int, int], run_id: str) -> None:
    """실행 id 가 있는데 십진 숫자 글자가 아니면 BadRun: NULL 로 접어 쓰지 않는다(실행 밖 줄로 섞이지 않게)."""
    a, _ = companies
    sink = DbSink()
    with CaptureQueriesContext(connection) as captured:
        sink.record(replace(of(RECORD, a), run_id=run_id))
    assert sink.outcomes == (BadRun(),)
    assert captured.captured_queries == []
    assert LlmCallLogRow.for_company(a).count() == 0
    sink.record(replace(of(RECORD, a), run_id="1"))  # 분모: 꼴이 맞으면 쓴다
    assert sink.outcomes[-1] == Written()


# ── 단계 이름(AD4D — CallRecord.step → 행의 step) ──


def test_a_step_survives_the_round_trip_and_a_line_without_one_stays_null(companies: tuple[int, int]) -> None:
    a, _ = companies
    sink = DbSink()
    with_step = replace(of(RECORD, a), run_id="42", step="judge", call_id="call-step")
    sink.record(with_step)
    sink.record(replace(of(RECORD, a), run_id="42", call_id="call-between"))
    sink.record(replace(of(RECORD, a), step="가" * 100, call_id="call-long"))  # 상한 그대로는 쓴다
    assert sink.outcomes == (Written(), Written(), Written())
    rows = {row.call_id: row for row in LlmCallLogRow.for_company(a)}
    assert (rows["call-step"].step, rows["call-between"].step, rows["call-long"].step) == ("judge", None, "가" * 100)
    back = record_from_row(rows["call-step"])
    assert back.to_json() == with_step.to_json()
    assert list(back.to_json())[-2:] == ["runId", "step"]  # 있을 때만 있는 칸(runId 뒤)
    assert "step" not in record_from_row(rows["call-between"]).to_json()


@pytest.mark.parametrize("step", ["", "가" * 101], ids=["empty", "101"])
def test_a_step_outside_one_to_a_hundred_characters_writes_nothing(companies: tuple[int, int], step: str) -> None:
    """단계 이름이 있는데 1~100자가 아니면 BadStep: DB 에 가지 않는다(WriteFailed 아님), NULL 로 접어 쓰지 않는다."""
    a, _ = companies
    sink = DbSink()
    with CaptureQueriesContext(connection) as captured:
        sink.record(replace(of(RECORD, a), run_id="42", step=step))
    assert sink.outcomes == (BadStep(),)
    assert captured.captured_queries == []
    assert LlmCallLogRow.for_company(a).count() == 0
    sink.record(replace(of(RECORD, a), run_id="42", step="judge"))  # 분모: 꼴이 맞으면 쓴다
    assert sink.outcomes[-1] == Written()


# ── 구획(RM1a — CallRecord.segment → 행의 segment) ──


def test_a_segment_survives_the_round_trip_and_a_barrier_line_stays_null(companies: tuple[int, int]) -> None:
    a, _ = companies
    sink = DbSink()
    sha = "ab" * 32
    in_segment = replace(of(RECORD, a), run_id="42", step="spread", segment=sha, call_id="call-segment")
    barrier = replace(of(RECORD, a), run_id="42", step="prepare", call_id="call-barrier")
    sink.record(in_segment)
    sink.record(barrier)
    assert sink.outcomes == (Written(), Written())
    rows = {row.call_id: row for row in LlmCallLogRow.for_company(a)}
    assert (rows["call-segment"].segment, rows["call-barrier"].segment) == (sha, None)
    back = record_from_row(rows["call-segment"])
    assert back.to_json() == in_segment.to_json()
    assert list(back.to_json())[-3:] == ["runId", "step", "segment"]  # 있을 때만 있는 칸(step 뒤)
    plain = record_from_row(rows["call-barrier"]).to_json()
    assert "segment" not in plain
    assert plain == barrier.to_json()  # 장벽 흐름의 줄은 칸까지 그대로(수는 값으로 — record_from_row 무효 조건)
    assert list(plain) == list(barrier.to_json())
