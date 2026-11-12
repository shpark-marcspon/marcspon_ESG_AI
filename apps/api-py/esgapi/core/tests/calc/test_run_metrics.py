"""지표 다섯과 처리 시간의 셈(core/calc/run_metrics.py — AU1b-2 처분 ⑤·MARC-ENT-327). 순수 층(DB 없이).

재는 것: 「이번 달」의 KST 경계(UTC 15:00 의 짝·12월 → 다음 해 1월) · 처리 시간 = finished − created 의 초 버림 ·
끝나지 않은 실행 · 테스트 실행은 지표 전부(수·평균·토큰·비용·실패율)에서 빠짐 · 청구 토큰 = 넷의 합 · Decimal 합 ·
평균의 반올림(절반 위로) · 분모 0 → None.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from esgapi.core.calc.run_metrics import KST, MetricRun, RunMetrics, RunUsage, duration_sec, metrics, month_bounds

T0 = datetime(2026, 10, 5, 1, 0, tzinfo=UTC)


def run(run_id: int, status: str, *, took: float | None = None, purpose: str = "service") -> MetricRun:
    return MetricRun(
        id=run_id,
        status=status,
        purpose=purpose,
        created_at=T0,
        finished_at=None if took is None else T0 + timedelta(seconds=took),
    )


def usage(tokens: int = 0, cost: str = "0") -> RunUsage:
    return RunUsage(input=tokens, cache_read=0, cache_write=0, output=0, cost_usd=Decimal(cost))


def test_the_month_turns_at_kst_midnight_not_utc() -> None:
    assert month_bounds(datetime(2026, 10, 31, 15, 0, tzinfo=UTC)) == (
        datetime(2026, 11, 1, tzinfo=KST),
        datetime(2026, 12, 1, tzinfo=KST),
        "2026-11",
    )
    start, end, month = month_bounds(datetime(2026, 10, 31, 14, 59, 59, 999999, tzinfo=UTC))
    assert (start, end, month) == (datetime(2026, 10, 1, tzinfo=KST), datetime(2026, 11, 1, tzinfo=KST), "2026-10")
    assert start == datetime(2026, 9, 30, 15, 0, tzinfo=UTC)  # KST 1일 00:00 = 앞날 UTC 15:00


def test_december_rolls_into_january_of_the_next_year() -> None:
    assert month_bounds(datetime(2026, 12, 15, tzinfo=UTC)) == (
        datetime(2026, 12, 1, tzinfo=KST),
        datetime(2027, 1, 1, tzinfo=KST),
        "2026-12",
    )
    assert month_bounds(datetime(2026, 12, 31, 15, 0, tzinfo=UTC))[2] == "2027-01"


def test_duration_is_finished_minus_created_with_seconds_floored() -> None:
    ten = datetime(2026, 10, 5, 10, 0, tzinfo=KST)
    assert duration_sec(ten, ten + timedelta(minutes=10)) == 600
    assert duration_sec(ten, ten + timedelta(minutes=10, microseconds=900000)) == 600  # 버림
    assert duration_sec(ten, None) is None  # 끝나지 않았다


def test_no_runs_gives_zeroes_and_nones() -> None:
    assert metrics([], {}) == RunMetrics(
        runs=0, average_duration_sec=None, tokens=0, cost_usd=Decimal(0), failure_rate=None
    )


def test_the_failure_rate_is_failed_over_finished_and_none_without_a_finished_run() -> None:
    finished = [run(1, "done", took=1), run(2, "failed", took=1), run(3, "failed", took=1), run(4, "done", took=1)]
    assert metrics([*finished, run(5, "queued"), run(6, "processing")], {}).failure_rate == 0.5
    assert metrics([run(1, "done", took=1), run(2, "failed", took=1), run(3, "failed", took=1)], {}).failure_rate == (
        2 / 3
    )
    only_waiting = metrics([run(1, "queued"), run(2, "processing")], {})
    assert (only_waiting.runs, only_waiting.failure_rate) == (2, None)  # 분모 0 — 실행 수는 상태 무관


def test_the_average_is_over_done_runs_rounded_half_up() -> None:
    found = metrics([run(1, "done", took=1), run(2, "done", took=2), run(3, "failed", took=100), run(4, "queued")], {})
    assert (found.runs, found.average_duration_sec) == (4, 2)  # (1 + 2) / 2 = 1.5 → 2, failed·queued 는 평균 밖
    assert metrics([run(1, "done", took=1), run(2, "done", took=1.9)], {}).average_duration_sec == 1  # 초 버림 뒤 평균
    assert metrics([run(1, "failed", took=5)], {}).average_duration_sec is None  # done 0


def test_billed_tokens_are_the_four_counts_and_cost_is_a_decimal_sum() -> None:
    found = metrics(
        [run(1, "done", took=1), run(2, "done", took=1), run(3, "queued")],
        {
            1: RunUsage(input=10, cache_read=20, cache_write=30, output=40, cost_usd=Decimal("0.00000001")),
            2: RunUsage(input=1, cache_read=0, cache_write=0, output=2, cost_usd=Decimal("0.1")),
            99: usage(1000, "9"),  # 무리 밖 실행의 합은 열쇠가 있어도 안 든다
        },
    )
    assert (found.tokens, found.cost_usd) == (103, Decimal("0.10000001"))


def test_test_runs_are_left_out_of_every_metric_including_their_llm_usage() -> None:
    usage_of = {1: usage(10, "0.2"), 2: usage(50, "0.1")}
    service, testing = run(1, "done", took=4), run(2, "failed", took=8, purpose="test")
    found = metrics([service, testing], usage_of)
    assert found == RunMetrics(runs=1, average_duration_sec=4, tokens=10, cost_usd=Decimal("0.2"), failure_rate=0.0)
    # 분모: 그 실행을 service 로 바꾸면 수·평균·토큰·비용·실패율에 다 든다
    counted = metrics([service, run(2, "failed", took=8)], usage_of)
    assert counted == RunMetrics(runs=2, average_duration_sec=4, tokens=60, cost_usd=Decimal("0.3"), failure_rate=0.5)
