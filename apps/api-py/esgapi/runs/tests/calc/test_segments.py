"""구획 쪽지의 순수 판정(runs/calc/segments.py — RM1b ②): 깨우기·잡기 고르기·이어 넣기. 값은 지어낸 것이다."""

import importlib
from datetime import UTC, datetime, timedelta

import pytest

from esgapi.runs.calc.segments import (
    SEGMENT_PARALLEL_DEFAULT,
    SegmentCounts,
    SegmentHead,
    claim_plan,
    delay_after,
    delayed_due,
    successor_due,
    wake_due,
)

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
LATER = NOW + timedelta(seconds=100)
EARLIER = NOW - timedelta(seconds=1)


def counts(pending: int = 0, running: int = 0, done: int = 0, failed: int = 0) -> SegmentCounts:
    return SegmentCounts(
        pending=pending, running=running, done=done, failed=failed, first_started_at=None, last_finished_at=None
    )


def head(position: int, status: str = "running", attempts: int = 1, lease: datetime | None = LATER) -> SegmentHead:
    return SegmentHead(
        position=position, key_sha256=f"{position:064x}", status=status, attempts=attempts, lease_expires_at=lease
    )


def test_the_module_imports_no_django() -> None:
    module = importlib.import_module("esgapi.runs.calc.segments")
    assert not [name for name in vars(module) if name.startswith("django")]
    assert SEGMENT_PARALLEL_DEFAULT == 2  # 감독 답 Q3


@pytest.mark.parametrize(
    ("policy", "after", "newly", "want"),
    [
        ("pass_to_gather", counts(done=3), 0, True),  # 끝나지 않은 것 0
        ("pass_to_gather", counts(done=2, failed=1), 1, True),
        ("pass_to_gather", counts(running=1, done=1, failed=1), 1, False),  # 남았다
        ("fail_run", counts(running=2, failed=1), 1, True),  # 첫 실패 0 → 1
        ("fail_run", counts(running=1, failed=2), 1, False),  # 앞에 실패가 있었다(이미 깼다)
        ("fail_run", counts(running=1, done=2), 0, False),  # 실패 없음·남음
        ("fail_run", counts(done=3), 0, True),  # fail_run 이어도 전부 done 이면 깨운다(B1b)
        ("fail_run", counts(running=1, failed=2), 2, True),  # 한 블록이 둘(소진) — 0 → 2
    ],
)
def test_wake_due(policy: str, after: SegmentCounts, newly: int, want: bool) -> None:
    assert wake_due(policy, after, newly) is want


def test_wake_due_refuses_a_newly_failed_outside_the_count() -> None:
    with pytest.raises(ValueError, match="밖"):
        wake_due("fail_run", counts(failed=1), 2)


def test_claim_plan_takes_the_earliest_claimable_in_plan_order() -> None:
    running = (head(4, lease=None), head(2, lease=LATER))  # 4 는 놓음(임대 NULL), 2 는 임대 산 것
    got = claim_plan(running, head(3, status="pending", attempts=0), now=NOW, parallel_max=3, max_attempts=3)
    assert got.take == head(3, status="pending", attempts=0) and got.alive == 1 and not got.full
    got = claim_plan(running, head(5, status="pending", attempts=0), now=NOW, parallel_max=3, max_attempts=3)
    assert got.take == head(4, lease=None)  # 놓은 running 이 계획 차례로 앞


def test_claim_plan_retakes_a_lapsed_lease() -> None:
    got = claim_plan((head(1, lease=NOW),), None, now=NOW, parallel_max=2, max_attempts=3)  # ≤ now 는 지났다
    assert got.take == head(1, lease=NOW) and got.alive == 0
    got = claim_plan((head(1, lease=EARLIER),), None, now=NOW, parallel_max=2, max_attempts=3)
    assert got.take == head(1, lease=EARLIER)


def test_claim_plan_is_full_at_the_cap_of_alive_leases() -> None:
    running = (head(1), head(2))
    got = claim_plan(running, head(3, status="pending", attempts=0), now=NOW, parallel_max=2, max_attempts=3)
    assert got.full and got.take is None and got.exhaust == ()
    got = claim_plan(running, head(3, status="pending", attempts=0), now=NOW, parallel_max=3, max_attempts=3)
    assert not got.full and got.take is not None  # 분모: 상한 밑이면 잡는다


def test_claim_plan_exhausts_claimable_running_at_the_attempt_cap() -> None:
    running = (head(1, attempts=3, lease=None), head(2, attempts=3, lease=LATER), head(5, attempts=2, lease=EARLIER))
    got = claim_plan(running, head(9, status="pending", attempts=0), now=NOW, parallel_max=3, max_attempts=3)
    assert got.exhaust == (head(1, attempts=3, lease=None),)  # 임대 산 2 는 소진 아님(돌고 있다)
    assert got.take == head(5, attempts=2, lease=EARLIER)


def test_claim_plan_exhausts_and_takes_nothing_when_nothing_is_left() -> None:
    got = claim_plan((head(1, attempts=3, lease=None),), None, now=NOW, parallel_max=2, max_attempts=3)
    assert got.exhaust == (head(1, attempts=3, lease=None),) and got.take is None


def test_claim_plan_refuses_wrong_heads() -> None:
    with pytest.raises(ValueError, match="running"):
        claim_plan((head(1, status="done"),), None, now=NOW, parallel_max=2, max_attempts=3)
    with pytest.raises(ValueError, match="pending"):
        claim_plan((), head(1, status="running"), now=NOW, parallel_max=2, max_attempts=3)
    with pytest.raises(ValueError, match="1 이상"):
        claim_plan((), None, now=NOW, parallel_max=0, max_attempts=3)


@pytest.mark.parametrize(
    ("policy", "after", "alive", "cap", "want"),
    [
        ("pass_to_gather", counts(pending=3, running=1), 1, 2, True),
        ("pass_to_gather", counts(pending=3, running=2), 2, 2, False),  # 상한
        ("pass_to_gather", counts(running=2), 2, 3, False),  # 남은 것은 다 돌고 있다
        ("pass_to_gather", counts(running=2), 1, 3, True),  # 놓은 running 하나
        ("fail_run", counts(pending=3, failed=1), 0, 2, False),  # 실패가 있다
        ("fail_run", counts(pending=3), 0, 2, True),
    ],
)
def test_successor_due(policy: str, after: SegmentCounts, alive: int, cap: int, want: bool) -> None:
    assert successor_due(on_failure=policy, counts=after, alive=alive, parallel_max=cap) is want


# ── 미룬 쪽지(RM1c ③′ M1) ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("unended", "alive", "cap", "due"),
    [
        (1, 1, 2, True),  # 남은 것이 전부 임대 산 running · 상한 밑
        (2, 1, 2, False),  # 잡을 것이 남았다(이어 넣기의 몫)
        (0, 0, 2, False),  # 끝났다(깨우기의 몫)
        (2, 2, 2, False),  # full — 산 쪽지가 끝내며 이어 넣는다
        (1, 1, 1, False),  # 상한 1 은 직렬(쪽지 0)
        (3, 2, 4, False),
        (3, 3, 4, True),
    ],
)
def test_delayed_due(unended: int, alive: int, cap: int, due: bool) -> None:
    assert delayed_due(unended=unended, alive=alive, parallel_max=cap) is due


def test_delay_after_is_the_earliest_lease_end_plus_one_second_at_least_one() -> None:
    now = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
    assert delay_after(now + timedelta(seconds=90), now) == 91
    assert delay_after(now + timedelta(seconds=89, milliseconds=1), now) == 91  # 올림
    assert delay_after(now - timedelta(seconds=5), now) == 1
