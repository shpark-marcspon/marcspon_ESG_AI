"""rows_of_runs(실행 묶음이 싣는 LLM 기록 행 — RX1a)를 진짜 DB 로 잰다: 그 회사의 그 실행 줄만
(남의 회사의 같은 run_id 줄 0), id 칸 없음·나머지 칸 전부, id 오름, 빈 입력은 쿼리 0.
★ 숫자는 전부 지어낸 것이다(synthetic).
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pytest_django import DjangoAssertNumQueries

from esgapi.core.models import LlmCallLogRow
from esgapi.core.service.selectors.llm_logs import rows_of_runs

pytestmark = pytest.mark.django_db


def a_log(company_id: int, run_id: int | None, call_id: str) -> None:
    LlmCallLogRow.for_company(company_id).create(
        company_id=company_id,
        module="probe",
        ts=datetime(2026, 10, 1, 1, 2, 3, 456000, tzinfo=UTC),
        call_id=call_id,
        attempt=0,
        provider="mock",
        model="mock-1",
        prompt_id="probe.judge",
        prompt_version=1,
        template_hash="t" * 64,
        request_hash="r" * 64,
        input_tokens=10,
        output_tokens=5,
        cost_usd=Decimal("0.00012345"),
        duration_ms=12.5,
        result_kind="success",
        warnings=["지어낸 경고"],
        run_id=run_id,
        step="judge",
    )


def test_only_that_companys_lines_of_those_runs(companies: tuple[int, int]) -> None:
    a, b = companies
    a_log(a, 7, "c1")
    a_log(a, 7, "c2")
    a_log(a, 8, "c3")
    a_log(a, None, "c4")
    a_log(b, 7, "c5")  # 남의 회사의 같은 run_id
    rows = rows_of_runs(company_id=a, run_ids={7})
    assert [row["call_id"] for row in rows] == ["c1", "c2"]
    assert "id" not in rows[0]
    columns = {field.attname for field in LlmCallLogRow._meta.concrete_fields} - {"id"}
    assert set(rows[0]) == columns  # 분모: 칸 전부
    assert rows[0]["company_id"] == a and rows[0]["cost_usd"] == Decimal("0.00012345")
    assert rows_of_runs(company_id=b, run_ids={7, 8})[0]["call_id"] == "c5"


def test_no_runs_no_query(companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries) -> None:
    with django_assert_num_queries(0):
        assert rows_of_runs(company_id=companies[0], run_ids=set()) == []
