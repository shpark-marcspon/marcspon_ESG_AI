"""실행마다의 LLM 합(core/service/selectors/llm_usage.py 의 usage_by_run — AU1b-2)을 진짜 DB 로 잰다. 업무 층.

재는 것: 실행마다 토큰 넷·비용의 합 · NULL 은 0 · run_id 가 NULL 인 줄(동기 계산)은 0 · 남의 회사 줄은 같은 run_id
값이어도 합에 안 듦(양성 대조: 그 회사로 읽으면 그 값) · thinking 은 output 에 더하지 않음 · 빈 집합은 쿼리 0.
AD4D usage_by_step: 단계마다의 합 · 단계 NULL 줄이 하나라도 있으면 recorded False · 줄 없음은 recorded True ·
남의 회사 줄은 같은 실행·단계여도 안 듦 · 쿼리 1.
RM1a usage_by_segment: (단계, 구획)마다의 합 = 그 단계 몫 · 펼침 단계의 구획 NULL 줄이 있으면 recorded False(장벽 단계의
NULL 줄은 보지 않음) · 남의 회사 줄은 안 듦 · 쿼리 1.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pytest_django import DjangoAssertNumQueries

from esgapi.core.calc.run_metrics import RunUsage
from esgapi.core.models import LlmCallLogRow
from esgapi.core.service.selectors.llm_usage import (
    SegmentUsage,
    StepUsage,
    usage_by_run,
    usage_by_segment,
    usage_by_step,
)

pytestmark = pytest.mark.django_db

RUN_X = 9_000_001
RUN_Y = 9_000_002


def call(company_id: int, run_id: int | None, **counts: Any) -> None:
    values: dict[str, Any] = {
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "thinking_tokens": None,
        "cost_usd": None,
        **counts,
    }
    LlmCallLogRow.for_company(company_id).create(
        company_id=company_id, module="greenwash", ts=datetime(2026, 10, 5, tzinfo=UTC), call_id="c", attempt=1,
        prompt_id="p", prompt_version=1, template_hash="t", request_hash="r", duration_ms=1.0,
        result_kind="success", run_id=run_id, **values,
    )  # fmt: skip


def test_each_run_gets_the_sum_of_its_lines(companies: tuple[int, int]) -> None:
    a, _ = companies
    call(a, RUN_X, input_tokens=10, cache_read_tokens=1, cache_write_tokens=2, output_tokens=5, cost_usd=Decimal("0.1"))
    call(
        a, RUN_X, input_tokens=20, cache_read_tokens=3, cache_write_tokens=4, output_tokens=6, cost_usd=Decimal("0.02")
    )
    call(a, RUN_Y, input_tokens=7, output_tokens=1, cost_usd=Decimal("0.00000001"))
    assert usage_by_run(company_id=a, run_ids=frozenset({RUN_X, RUN_Y})) == {
        RUN_X: RunUsage(input=30, cache_read=4, cache_write=6, output=11, cost_usd=Decimal("0.12")),
        RUN_Y: RunUsage(input=7, cache_read=0, cache_write=0, output=1, cost_usd=Decimal("0.00000001")),
    }
    assert usage_by_run(company_id=a, run_ids=frozenset({RUN_Y}))[RUN_Y].tokens == 8  # 고른 실행만


def test_nulls_count_as_zero_and_a_run_without_lines_has_no_key(companies: tuple[int, int]) -> None:
    a, _ = companies
    call(a, RUN_X)  # 상한에 막힌 줄: 토큰·비용 전부 NULL
    found = usage_by_run(company_id=a, run_ids=frozenset({RUN_X, RUN_Y}))
    assert found == {RUN_X: RunUsage(input=0, cache_read=0, cache_write=0, output=0, cost_usd=Decimal(0))}


def test_lines_without_a_run_are_not_counted(companies: tuple[int, int]) -> None:
    a, _ = companies
    call(a, None, input_tokens=500, cost_usd=Decimal(5))  # 동기 계산의 호출
    call(a, RUN_X, input_tokens=1)
    assert usage_by_run(company_id=a, run_ids=frozenset({RUN_X}))[RUN_X].input == 1
    assert LlmCallLogRow.for_company(a).count() == 2  # 분모: 줄은 둘 다 있다


def test_another_companys_line_with_the_same_run_id_is_not_counted(companies: tuple[int, int]) -> None:
    a, b = companies
    call(a, RUN_X, input_tokens=10, cost_usd=Decimal("0.1"))
    call(b, RUN_X, input_tokens=1000, cost_usd=Decimal(9))
    assert usage_by_run(company_id=a, run_ids=frozenset({RUN_X})) == {
        RUN_X: RunUsage(input=10, cache_read=0, cache_write=0, output=0, cost_usd=Decimal("0.1"))
    }
    # 양성 대조: B 로 읽으면 B 의 줄이 그 값으로 실린다
    assert usage_by_run(company_id=b, run_ids=frozenset({RUN_X}))[RUN_X].input == 1000


def test_thinking_tokens_are_not_added_to_output(companies: tuple[int, int]) -> None:
    a, _ = companies
    call(a, RUN_X, input_tokens=1, output_tokens=20, thinking_tokens=7)  # thinking 은 output 20 안의 몫
    found = usage_by_run(company_id=a, run_ids=frozenset({RUN_X}))[RUN_X]
    assert (found.output, found.tokens) == (20, 21)


def test_an_empty_set_reads_nothing(django_assert_num_queries: DjangoAssertNumQueries) -> None:
    with django_assert_num_queries(0):
        assert usage_by_run(company_id=1, run_ids=frozenset()) == {}


def test_one_query_for_many_runs(companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries) -> None:
    a, _ = companies
    call(a, RUN_X, input_tokens=1)
    call(a, RUN_Y, input_tokens=2)
    with django_assert_num_queries(1):
        assert len(usage_by_run(company_id=a, run_ids=frozenset({RUN_X, RUN_Y}))) == 2


# ── 단계마다(AD4D — usage_by_step) ──


def test_each_step_gets_the_sum_of_its_lines_and_the_run_is_recorded(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    call(a, RUN_X, step="extract", input_tokens=10, output_tokens=5, cost_usd=Decimal("0.1"))
    call(a, RUN_X, step="judge", input_tokens=20, cache_read_tokens=3, cache_write_tokens=4, output_tokens=6)
    call(a, RUN_X, step="judge", input_tokens=1, cost_usd=Decimal("0.02"))
    call(a, RUN_Y, step="judge", input_tokens=99)  # 다른 실행
    with django_assert_num_queries(1):
        found = usage_by_step(company_id=a, run_id=RUN_X)
    assert found == StepUsage(
        by_step={
            "extract": RunUsage(input=10, cache_read=0, cache_write=0, output=5, cost_usd=Decimal("0.1")),
            "judge": RunUsage(input=21, cache_read=3, cache_write=4, output=6, cost_usd=Decimal("0.02")),
        },
        recorded=True,
    )
    total = usage_by_run(company_id=a, run_ids=frozenset({RUN_X}))[RUN_X]
    assert sum(u.tokens for u in found.by_step.values()) == total.tokens  # 단계의 합 = 실행의 합


def test_one_line_without_a_step_makes_the_run_unrecorded(companies: tuple[int, int]) -> None:
    a, _ = companies
    call(a, RUN_X, step="judge", input_tokens=5)
    call(a, RUN_X, input_tokens=7)  # 단계 밖(또는 AD4D 앞) 줄
    found = usage_by_step(company_id=a, run_id=RUN_X)
    assert found.recorded is False
    assert set(found.by_step) == {"judge"}  # 아는 단계는 담기지만 부르는 쪽이 통째로 「모름」으로 낸다
    call(a, RUN_Y, input_tokens=7)  # 지난 실행: NULL 줄만
    assert usage_by_step(company_id=a, run_id=RUN_Y) == StepUsage(by_step={}, recorded=False)
    assert usage_by_step(company_id=a, run_id=9_000_003) == StepUsage(by_step={}, recorded=True)  # 줄 없음


def test_another_companys_line_on_the_same_run_and_step_is_not_counted(companies: tuple[int, int]) -> None:
    a, b = companies
    call(a, RUN_X, step="judge", input_tokens=5)
    call(b, RUN_X, step="judge", input_tokens=1000)  # B 꼬리표 줄이 A 의 실행·단계 이름을 달았다
    call(b, RUN_X, input_tokens=1)  # B 의 NULL 줄도 A 의 recorded 를 바꾸지 않는다
    assert usage_by_step(company_id=a, run_id=RUN_X) == StepUsage(
        by_step={"judge": RunUsage(input=5, cache_read=0, cache_write=0, output=0, cost_usd=Decimal(0))},
        recorded=True,
    )
    assert usage_by_step(company_id=b, run_id=RUN_X).by_step["judge"].input == 1000  # 양성 대조


# ── 구획마다(RM1a — usage_by_segment) ──

SHA_1 = "1" * 64
SHA_2 = "2" * 64


def test_each_segment_gets_the_sum_of_its_lines_inside_the_run_total(
    companies: tuple[int, int], django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    a, _ = companies
    call(a, RUN_X, step="prepare", input_tokens=50, cost_usd=Decimal("0.5"))  # 장벽 단계 — 구획 칸 NULL
    call(a, RUN_X, step="spread", segment=SHA_1, input_tokens=10, cost_usd=Decimal("0.1"))
    call(a, RUN_X, step="spread", segment=SHA_1, input_tokens=1, output_tokens=2, cost_usd=Decimal("0.01"))
    call(a, RUN_X, step="spread", segment=SHA_2, input_tokens=20, cost_usd=Decimal("0.2"))
    call(a, RUN_Y, step="spread", segment=SHA_1, input_tokens=999)  # 다른 실행
    with django_assert_num_queries(1):
        found = usage_by_segment(company_id=a, run_id=RUN_X, fanout_steps=frozenset({"spread"}))
    assert found == SegmentUsage(
        by_segment={
            ("spread", SHA_1): RunUsage(input=11, cache_read=0, cache_write=0, output=2, cost_usd=Decimal("0.11")),
            ("spread", SHA_2): RunUsage(input=20, cache_read=0, cache_write=0, output=0, cost_usd=Decimal("0.2")),
        },
        recorded=True,  # 장벽 단계(prepare)의 NULL 줄은 recorded 를 바꾸지 않는다
    )
    total = usage_by_run(company_id=a, run_ids=frozenset({RUN_X}))[RUN_X]
    spread = usage_by_step(company_id=a, run_id=RUN_X).by_step["spread"]
    assert sum(u.cost_usd for u in found.by_segment.values()) == spread.cost_usd  # 구획의 합 = 그 단계의 몫
    assert total.cost_usd == spread.cost_usd + Decimal("0.5")


def test_a_fanout_line_without_a_segment_makes_the_run_unrecorded(companies: tuple[int, int]) -> None:
    a, b = companies
    call(a, RUN_X, step="spread", segment=SHA_1, input_tokens=5)
    call(a, RUN_X, step="spread", input_tokens=7)  # 펼침 단계인데 구획 밖(plan 안 호출·RM1a 앞)
    found = usage_by_segment(company_id=a, run_id=RUN_X, fanout_steps=frozenset({"spread"}))
    assert found.recorded is False
    assert set(found.by_segment) == {("spread", SHA_1)}
    assert usage_by_segment(company_id=a, run_id=RUN_X, fanout_steps=frozenset()).recorded is True  # 장벽만이면 본다 0
    call(b, RUN_Y, step="spread", segment=SHA_1, input_tokens=1000)  # 남의 회사 줄은 같은 실행 id 여도 0
    assert usage_by_segment(company_id=a, run_id=RUN_Y, fanout_steps=frozenset({"spread"})) == SegmentUsage(
        by_segment={}, recorded=True
    )
