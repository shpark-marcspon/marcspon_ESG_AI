"""운영 관리자의 실행 읽기(runs/service/selectors/operator.py — AU1b-2)를 진짜 DB 로 잰다. 업무 층.

권한 표의 줄(user_run_log_list·user_run_log_metrics)은 커밋 ② 가 더한다 — 여기서는 시험만 두 줄을 세운다(setitem, 제품
표는 그대로).
재는 것: 첫 줄 권한(고객사 kind 는 쿼리 0) · 함수마다 자기 칸을 읽는가(두 칸을 엇갈려 놓음) · 고른 회사의 실행만(남의
회사 0 — 분모: 그 회사로 고르면 ≥1) · 거르기 다섯 각각과 AND · q 의 % _ . 는 글자 · 새 것 먼저·쪽·count 는 거른 뒤 ·
문서 이름은 같은 회사 문서에서 · KST 날짜 경계 넷 · 무리의 달 경계 · 쿼리 수.
AD4D operator_run_detail: 첫 줄 권한(쿼리 0) · 줄 칸 + 실패 단계·오류 코드 + 단계 머리·파일 · 없거나 남의 회사 None ·
쿼리 수(실행 1 + 단계 1 + 파일 1 — 원천 없는 모듈).
RF1 operator_run_file: 첫 줄 권한(쿼리 0) · 출력 파일(step NULL) 행 · 단계 산출 파일만이면 RunFileMissing · 없거나 남의
회사 None · 모든 모듈 · 쿼리 수(실행 1 + 파일 1).
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from pytest_django import DjangoAssertNumQueries

from esgapi.core import permissions
from esgapi.core.calc.run_metrics import KST
from esgapi.core.models import DocumentRow
from esgapi.runs.models import RunFileRow, RunRow, RunStepRow
from esgapi.runs.service.selectors.operator import (
    CohortRun,
    ExportTooLarge,
    OperatorRunDetail,
    OperatorRunExport,
    OperatorRunPage,
    RunFileMissing,
    RunLogForbidden,
    operator_run_cohort,
    operator_run_detail,
    operator_run_export,
    operator_run_file,
    operator_run_page,
)

pytestmark = pytest.mark.django_db

MICRO = timedelta(microseconds=1)


@pytest.fixture(autouse=True)
def operator_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_run_log_list", permissions.OPERATOR)
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_run_log_metrics", permissions.OPERATOR)


def document(company_id: int, name: str = "보고서.pdf") -> int:
    row = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by="1",
        file_name=name,
        storage_key=f"companies/{company_id}/documents/{DocumentRow.unscoped.count()}/original",
        size_bytes=1,
        status="uploaded",
    )
    return row.pk


def made(company_id: int, doc: int | None, *, at: datetime | None = None, **extra: Any) -> int:
    values: dict[str, Any] = {
        "module": "greenwash",
        "flow_id": "greenwash.colab@E0",
        "status": "queued",
        "created_by_user_id": 7,
        **extra,
    }
    row = RunRow.for_company(company_id).create(company_id=company_id, document_id=doc, **values)
    if at is not None:
        RunRow.for_company(company_id).filter(pk=row.pk).update(created_at=at)
    return row.pk


def read(company_id: int, **filters: object) -> OperatorRunPage:
    options: dict[str, object] = {
        "module": None,
        "status": None,
        "date_from": None,
        "date_to": None,
        "q": None,
        "limit": 20,
        "offset": 0,
        **filters,
    }
    page = operator_run_page(actor_kind="admin", company_id=company_id, **options)  # type: ignore[arg-type]
    assert isinstance(page, OperatorRunPage)
    return page


def ids(page: OperatorRunPage) -> list[int]:
    return [run.id for run in page.runs]


def cohort(company_id: int, start: datetime, end: datetime) -> tuple[CohortRun, ...]:
    found = operator_run_cohort(actor_kind="admin", company_id=company_id, start=start, end=end)
    assert not isinstance(found, RunLogForbidden)
    return found


# ── 권한 ─────────────────────────────────────────────────────────────


def test_a_customer_kind_is_forbidden_before_anything_is_read(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    made(a, document(a))
    start, end = datetime(2000, 1, 1, tzinfo=UTC), datetime(2999, 1, 1, tzinfo=UTC)
    with django_assert_num_queries(0):
        refused_page = operator_run_page(
            actor_kind="service", company_id=a, module=None, status=None, date_from=None, date_to=None, q=None,
            limit=20, offset=0,
        )  # fmt: skip
        refused_cohort = operator_run_cohort(actor_kind="service", company_id=a, start=start, end=end)
    assert (refused_page, refused_cohort) == (RunLogForbidden(), RunLogForbidden())
    assert (read(a).count, len(cohort(a, start, end))) == (1, 1)  # 분모: 운영 관리자는 읽는다


def test_each_function_reads_its_own_cell(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    """두 칸을 엇갈려 놓는다: 자기 칸이 CUSTOMER 이고 남의 칸이 OPERATOR 면 service 가 지나고, 바꿔 놓으면 막힌다."""
    a, _ = companies
    start, end = datetime(2000, 1, 1, tzinfo=UTC), datetime(2999, 1, 1, tzinfo=UTC)

    def page_as_service() -> object:
        return operator_run_page(
            actor_kind="service", company_id=a, module=None, status=None, date_from=None, date_to=None, q=None,
            limit=20, offset=0,
        )  # fmt: skip

    def cohort_as_service() -> object:
        return operator_run_cohort(actor_kind="service", company_id=a, start=start, end=end)

    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_run_log_list", permissions.CUSTOMER)
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_run_log_metrics", permissions.OPERATOR)
    assert isinstance(page_as_service(), OperatorRunPage)
    assert cohort_as_service() == RunLogForbidden()

    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_run_log_list", permissions.OPERATOR)
    monkeypatch.setitem(permissions.OPERATION_POLICY, "user_run_log_metrics", permissions.CUSTOMER)
    assert page_as_service() == RunLogForbidden()
    assert cohort_as_service() == ()


# ── 회사 경계 ────────────────────────────────────────────────────────


def test_only_the_chosen_companys_runs_are_seen(companies: tuple[int, int]) -> None:
    a, b = companies
    in_a = made(a, document(a))
    in_b = made(b, document(b))
    start, end = datetime(2000, 1, 1, tzinfo=UTC), datetime(2999, 1, 1, tzinfo=UTC)
    assert (ids(read(a)), read(a).count) == ([in_a], 1)  # 남의 회사 실행 0
    assert [run.id for run in cohort(a, start, end)] == [in_a]
    # 분모: B 로 고르면 B 의 실행이 보인다
    assert (ids(read(b)), [run.id for run in cohort(b, start, end)]) == ([in_b], [in_b])


def test_the_document_name_comes_from_the_same_companys_document(companies: tuple[int, int]) -> None:
    a, b = companies
    made(b, document(b, "나 회사 보고서.pdf"))
    run_id = made(a, document(a, "가 회사 보고서.pdf"), created_by_user_id=11)
    [run] = read(a).runs
    assert (run.id, run.document_name, run.created_by_user_id, run.purpose) == (
        run_id,
        "가 회사 보고서.pdf",
        11,
        "service",
    )


# ── 거르기·차례·쪽 ───────────────────────────────────────────────────


def test_filters_each_and_together(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc_a, doc_b = document(a, "Alpha.pdf"), document(a, "beta.xlsx")
    green = made(a, doc_a, at=datetime(2026, 10, 1, 3, tzinfo=UTC), status="done")
    green_failed = made(a, doc_b, at=datetime(2026, 10, 2, 3, tzinfo=UTC), status="failed")
    other = made(a, doc_a, at=datetime(2026, 10, 3, 3, tzinfo=UTC), module="inventory", flow_id="inventory.x@1")
    assert read(a).count == 3  # 분모
    assert ids(read(a, module="greenwash")) == [green_failed, green]
    assert ids(read(a, status="failed")) == [green_failed]
    assert ids(read(a, date_from=date(2026, 10, 2))) == [other, green_failed]
    assert ids(read(a, date_to=date(2026, 10, 2))) == [green_failed, green]
    assert ids(read(a, q="ALPHA")) == [other, green]  # 대소문자 무시, 부분 일치
    together = read(
        a, module="greenwash", status="done", date_from=date(2026, 10, 1), date_to=date(2026, 10, 2), q="alp"
    )
    assert (together.count, ids(together)) == (1, [green])
    assert read(a, module="greenwash", q="beta", status="done").count == 0


def test_q_takes_percent_underscore_and_dot_as_letters(companies: tuple[int, int]) -> None:
    a, _ = companies
    percent = made(a, document(a, "100%_v1.pdf"))
    made(a, document(a, "kim"))
    assert read(a).count == 2  # 분모: q 없이 둘
    for needle in ("%", "_", "."):
        assert ids(read(a, q=needle)) == [percent], needle


def test_newest_first_paging_and_count_after_filtering(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = document(a)
    first = made(a, doc, at=datetime(2026, 10, 1, tzinfo=UTC))
    second = made(a, doc, at=datetime(2026, 10, 2, tzinfo=UTC), status="done")
    third = made(a, doc, at=datetime(2026, 10, 2, tzinfo=UTC))  # 같은 때 — id 내림
    fourth = made(a, doc, at=datetime(2026, 10, 3, tzinfo=UTC))
    assert ids(read(a)) == [fourth, third, second, first]
    page = read(a, limit=2, offset=1)
    assert (page.count, ids(page)) == (4, [third, second])
    queued = read(a, status="queued", limit=1, offset=1)
    assert (queued.count, ids(queued)) == (3, [third])


def test_dates_are_kst_days_including_both_ends(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = document(a)
    day_start = datetime(2026, 10, 2, tzinfo=KST)  # = 10-01T15:00Z
    next_day = datetime(2026, 10, 3, tzinfo=KST)
    before = made(a, doc, at=day_start - MICRO)
    start = made(a, doc, at=day_start)
    end = made(a, doc, at=next_day - MICRO)
    after = made(a, doc, at=next_day)
    day = date(2026, 10, 2)
    assert ids(read(a, date_from=day, date_to=day)) == [end, start]
    assert ids(read(a, date_from=day)) == [after, end, start]  # dateFrom KST 00:00:00 듦·그 1µs 앞 빠짐
    assert ids(read(a, date_to=day)) == [end, start, before]  # dateTo+1일 KST 00:00:00 빠짐·그 1µs 앞 듦
    assert read(a).count == 4  # 분모


def test_the_cohort_is_the_kst_month_with_its_columns(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = document(a)
    start, end = datetime(2026, 11, 1, tzinfo=KST), datetime(2026, 12, 1, tzinfo=KST)
    made(a, doc, at=start - MICRO)
    first = made(a, doc, at=start, status="done", purpose="test")
    last = made(a, doc, at=end - MICRO, status="failed")
    made(a, doc, at=end)
    found = cohort(a, start, end)
    assert [(run.id, run.status, run.purpose) for run in found] == [
        (first, "done", "test"),
        (last, "failed", "service"),
    ]
    assert found[0].created_at == start and found[0].finished_at is None
    assert len(cohort(a, start - MICRO, end + MICRO)) == 4  # 분모


# ── 쿼리 수 ──────────────────────────────────────────────────────────


def test_a_page_is_two_queries_and_a_cohort_is_one(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        made(a, document(a, name))
    # 셈 1 + 읽기 1(문서 이름은 같은 쿼리의 join) + 원천(그린워싱)의 검토 가능 id 1(AD4S — 비어 검토 상태는 0)
    with django_assert_num_queries(3):
        assert len(read(a).runs) == 3
    other = companies[1]
    made(other, document(other), module="inventory", flow_id="inventory.x@1")
    with django_assert_num_queries(2):  # 분모: 원천이 없는 모듈의 줄만이면 원천 쿼리 0
        assert len(read(other).runs) == 1
    with django_assert_num_queries(1):
        assert len(cohort(a, datetime(2000, 1, 1, tzinfo=UTC), datetime(2999, 1, 1, tzinfo=UTC))) == 3


# ── 내보내기(AD4S ②) ────────────────────────────────────────────────


def export(company_id: int, *, actor_kind: str = "admin", cap: int = 100, **filters: object) -> object:
    options: dict[str, object] = {
        "module": None, "status": None, "date_from": None, "date_to": None, "q": None, "review": None, **filters
    }  # fmt: skip
    return operator_run_export(actor_kind=actor_kind, company_id=company_id, cap=cap, **options)  # type: ignore[arg-type]


def test_the_export_is_forbidden_to_a_customer_kind_before_anything_is_read(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    made(a, document(a))
    with django_assert_num_queries(0):
        assert export(a, actor_kind="service") == RunLogForbidden()
    found = export(a)  # 분모: 운영 관리자는 읽는다
    assert isinstance(found, OperatorRunExport) and len(found.runs) == 1


def test_the_export_takes_every_filtered_run_and_stops_over_the_cap(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, b = companies
    doc = document(a)
    runs = [made(a, doc, at=datetime(2026, 10, day, tzinfo=UTC), module="inventory", flow_id="x@1") for day in (1, 2)]
    runs.append(made(a, doc, at=datetime(2026, 10, 3, tzinfo=UTC), module="inventory", flow_id="x@1"))
    made(b, document(b))  # 남의 회사
    found = export(a, cap=3)
    assert isinstance(found, OperatorRunExport)
    assert [run.id for run in found.runs] == runs[::-1]  # 쪽 없이 전부, 새 것 먼저
    with django_assert_num_queries(1):  # 셈만(행 읽기 0)
        assert export(a, cap=2) == ExportTooLarge(3)
    filtered = export(a, cap=2, date_from=date(2026, 10, 2))  # 거른 뒤의 수로 견준다
    assert isinstance(filtered, OperatorRunExport) and len(filtered.runs) == 2


# ── 상세(AD4D) ────────────────────────────────────────────────────────


def failed_with_children(company_id: int) -> int:
    """failed 실행(module inventory — 원천 없음) · 단계 둘 · 파일 둘(단계 산출·흐름 출력)."""
    run_id = made(company_id, document(company_id), module="inventory", flow_id="x@1", status="failed")
    RunRow.for_company(company_id).filter(pk=run_id).update(failed_step="judge", error_code="step_failed")
    for position, (name, status) in enumerate((("extract", "done"), ("judge", "failed"))):
        RunStepRow.for_company(company_id).create(
            company_id=company_id, run_id=run_id, name=name, position=position, status=status, data={"x": 1}
        )
    for step, name in (("extract", "pages.json"), (None, "report.bin")):
        RunFileRow.for_company(company_id).create(
            company_id=company_id, run_id=run_id, step=step, name=name, media_type="application/octet-stream",
            storage_key=f"runs/{company_id}/{run_id}/{name}", size_bytes=4, sha256="0" * 64,
        )  # fmt: skip
    return run_id


def test_the_detail_is_forbidden_to_a_customer_kind_before_anything_is_read(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    run_id = failed_with_children(a)
    with django_assert_num_queries(0):
        assert operator_run_detail(actor_kind="service", company_id=a, run_id=run_id) == RunLogForbidden()
    assert isinstance(operator_run_detail(actor_kind="admin", company_id=a, run_id=run_id), OperatorRunDetail)  # 분모


def test_the_detail_holds_the_line_the_failure_the_steps_and_the_files(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    run_id = failed_with_children(a)
    with django_assert_num_queries(3):  # 실행 1(문서 이름 join) + 단계 1 + 파일 1(원천 없는 모듈이라 검토 0)
        found = operator_run_detail(actor_kind="admin", company_id=a, run_id=run_id)
    assert isinstance(found, OperatorRunDetail)
    assert (found.run.id, found.run.status, found.run.document_name) == (run_id, "failed", "보고서.pdf")
    assert (found.failed_step, found.error_code) == ("judge", "step_failed")
    assert [(s.name, s.position, s.status) for s in found.steps] == [("extract", 0, "done"), ("judge", 1, "failed")]
    assert [(f.step, f.name) for f in found.files] == [("extract", "pages.json"), (None, "report.bin")]


def test_a_missing_or_another_companys_run_is_none(companies: tuple[int, int]) -> None:
    a, b = companies
    run_id = failed_with_children(a)
    assert operator_run_detail(actor_kind="admin", company_id=b, run_id=run_id) is None
    assert operator_run_detail(actor_kind="admin", company_id=a, run_id=run_id + 1000) is None
    assert operator_run_detail(actor_kind="admin", company_id=a, run_id=2**63) is None  # bigint 밖도 None(500 아님)
    assert operator_run_detail(actor_kind="admin", company_id=a, run_id=run_id) is not None  # 분모


# ── 문서 없는 실행(ND1) ──────────────────────────────────────────────


def test_a_documentless_run_is_read_with_no_document_and_q_leaves_it_out(companies: tuple[int, int]) -> None:
    """목록·내보내기·상세가 문서 칸 NULL 실행을 두 칸 None 으로 읽는다(LEFT JOIN — 빠지지 않는다). q(문서 이름)는
    그 줄을 뺀다. 분모: 문서 실행은 두 칸이 차 있다."""
    a, _ = companies
    doc = document(a, "지은 보고서.pdf")
    with_document = made(a, doc, at=datetime(2026, 10, 1, tzinfo=UTC))
    without = made(a, None, module="probe", flow_id="probe.bare@1", at=datetime(2026, 10, 2, tzinfo=UTC))
    page = read(a)
    assert page.count == 2
    assert [(r.id, r.document_id, r.document_name) for r in page.runs] == [
        (without, None, None),
        (with_document, doc, "지은 보고서.pdf"),
    ]
    assert [r.id for r in read(a, q="보고서").runs] == [with_document]
    exported = export(a)
    assert isinstance(exported, OperatorRunExport)
    assert [(r.id, r.document_name) for r in exported.runs] == [(without, None), (with_document, "지은 보고서.pdf")]
    found = operator_run_detail(actor_kind="admin", company_id=a, run_id=without)
    assert isinstance(found, OperatorRunDetail)
    assert (found.run.document_id, found.run.document_name) == (None, None)


# ── 결과 파일(RF1) ────────────────────────────────────────────────────


def test_the_file_is_forbidden_to_a_customer_kind_before_anything_is_read(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    run_id = failed_with_children(a)
    with django_assert_num_queries(0):
        found = operator_run_file(actor_kind="service", company_id=a, run_id=run_id, name="report.bin")
    assert found == RunLogForbidden()
    assert operator_run_file(actor_kind="admin", company_id=a, run_id=run_id, name="report.bin") is not None  # 분모


def test_the_file_is_the_output_row_of_a_run_of_any_module(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    run_id = failed_with_children(a)  # module inventory — OPERATOR_RUN_MODULES 밖
    with django_assert_num_queries(2):  # 실행 1 + 파일 1
        found = operator_run_file(actor_kind="admin", company_id=a, run_id=run_id, name="report.bin")
    assert not isinstance(found, (RunLogForbidden, RunFileMissing)) and found is not None
    assert (found.step, found.name, found.storage_key) == (None, "report.bin", f"runs/{a}/{run_id}/report.bin")


def test_a_step_files_name_or_an_unknown_name_is_missing(companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = failed_with_children(a)
    for name in ("pages.json", "none.bin"):  # 단계 산출 파일 · 없는 이름
        assert operator_run_file(actor_kind="admin", company_id=a, run_id=run_id, name=name) == RunFileMissing(), name


def test_a_missing_or_another_companys_run_has_no_file(companies: tuple[int, int]) -> None:
    a, b = companies
    run_id = failed_with_children(a)
    assert operator_run_file(actor_kind="admin", company_id=b, run_id=run_id, name="report.bin") is None
    assert operator_run_file(actor_kind="admin", company_id=a, run_id=run_id + 1000, name="report.bin") is None
    assert operator_run_file(actor_kind="admin", company_id=a, run_id=2**63, name="report.bin") is None
    assert operator_run_file(actor_kind="admin", company_id=a, run_id=run_id, name="report.bin") is not None  # 분모


# ── 같이 시작한 묶음(LK1 — _launches) ─────────────────────────────────

LAUNCH = "1a2b3c4d-1111-4222-8333-444455556666"  # 지어낸 소문자 UUID
LAUNCH_2 = "5e6f7a8b-9999-4aaa-8bbb-cccccccccccc"


def launch_cells(page: OperatorRunPage) -> dict[int, tuple[object, ...]]:
    return {r.id: (r.launch_key, r.launch_first_run_id, r.launch_index, r.launch_size) for r in page.runs}


def test_a_launch_is_counted_in_id_order_per_person_and_key(companies: tuple[int, int]) -> None:
    """차례 = id 오름(쪽 차례 created_at 내림과 다르다), 범위 = (회사, 만든 사람, 열쇠). 열쇠 없는 줄은 넷 다 None."""
    a, _ = companies
    doc = document(a)
    late = made(a, doc, at=datetime(2026, 10, 3, tzinfo=UTC), launch_key=LAUNCH)  # id 가 먼저 — 쪽에서는 맨 앞
    early = made(a, doc, at=datetime(2026, 10, 1, tzinfo=UTC), launch_key=LAUNCH)
    theirs = made(a, doc, launch_key=LAUNCH, created_by_user_id=8)  # 같은 열쇠·다른 사람 = 다른 묶음
    other = made(a, doc, launch_key=LAUNCH_2)
    plain = made(a, doc)
    assert launch_cells(read(a)) == {
        late: (LAUNCH, late, 1, 2),
        early: (LAUNCH, late, 2, 2),
        theirs: (LAUNCH, theirs, 1, 1),
        other: (LAUNCH_2, other, 1, 1),
        plain: (None, None, None, None),
    }


def test_launch_cells_ignore_filters_and_paging(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = document(a)
    ids = [made(a, doc, launch_key=LAUNCH, status=s) for s in ("done", "failed", "done")]
    assert launch_cells(read(a, status="failed")) == {ids[1]: (LAUNCH, ids[0], 2, 3)}
    assert launch_cells(read(a, limit=1)) == {ids[2]: (LAUNCH, ids[0], 3, 3)}  # 새 것 먼저
    detail = operator_run_detail(actor_kind="admin", company_id=a, run_id=ids[1])
    assert isinstance(detail, OperatorRunDetail)
    assert (detail.run.launch_index, detail.run.launch_size, detail.run.launch_first_run_id) == (2, 3, ids[0])


def test_launch_cells_stay_in_the_chosen_company(companies: tuple[int, int]) -> None:
    a, b = companies
    in_a = [made(a, document(a), launch_key=LAUNCH) for _ in range(2)]
    in_b = made(b, document(b), launch_key=LAUNCH)  # 같은 사람(7)·같은 열쇠·남의 회사
    assert launch_cells(read(b)) == {in_b: (LAUNCH, in_b, 1, 1)}
    assert launch_cells(read(a)) == {in_a[0]: (LAUNCH, in_a[0], 1, 2), in_a[1]: (LAUNCH, in_a[0], 2, 2)}


def test_the_launch_query_is_one_when_a_key_is_on_the_page_and_zero_otherwise(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    _, b = companies
    for _ in range(2):
        made(b, document(b), module="inventory", flow_id="inventory.x@1")  # 원천 없는 모듈 — 원천 쿼리 0
    with django_assert_num_queries(2):  # 셈 1 + 읽기 1 (열쇠 없는 쪽 — LK1 앞과 같다)
        assert len(read(b).runs) == 2
    made(b, document(b), module="inventory", flow_id="inventory.x@1", launch_key=LAUNCH)
    with django_assert_num_queries(3):  # + 묶음 1
        assert len(read(b).runs) == 3
    with django_assert_num_queries(2):  # 내보내기는 묶음을 세지 않는다(셈 1 + 읽기 1)
        found = export(b)
    assert isinstance(found, OperatorRunExport)
    assert {(r.launch_key, r.launch_first_run_id, r.launch_index, r.launch_size) for r in found.runs} == {
        (None, None, None, None),
        (LAUNCH, None, None, None),
    }


def test_resumed_from_is_read_as_a_cell(companies: tuple[int, int]) -> None:
    a, _ = companies
    doc = document(a)
    first = made(a, doc, status="failed")
    child = made(a, doc, resumed_from_run_id=first)
    assert {r.id: r.resumed_from_run_id for r in read(a).runs} == {first: None, child: first}
