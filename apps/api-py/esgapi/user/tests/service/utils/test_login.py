"""잠금의 규칙(is_locked·after_failure). 순수 층: DB 없음.

같은 초 = 아직 잠김(K-B1). 잠금이 지났는지는 now > login_expiry_at 로 본다 — 같은 초면 지나지 않았다.
"""

from datetime import UTC, datetime, timedelta

import pytest

from esgapi.user.service.utils.login import LockState, after_failure, is_locked

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
SECOND = timedelta(seconds=1)
LOCK = timedelta(seconds=600)


def test_no_expiry_is_not_locked() -> None:
    assert is_locked(None, NOW) is False


@pytest.mark.parametrize(
    ("expiry", "locked"),
    [(NOW + SECOND, True), (NOW, True), (NOW - SECOND, False)],
    ids=["expiry-after-now", "same-second", "expiry-passed"],
)
def test_locked_until_and_including_the_expiry(expiry: datetime, locked: bool) -> None:
    assert is_locked(expiry, NOW) is locked


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_the_first_four_failures_only_count(count: int) -> None:
    assert after_failure(LockState(count, None), NOW) == LockState(count + 1, None)


def test_the_fifth_failure_locks_for_ten_minutes() -> None:
    assert after_failure(LockState(4, None), NOW) == LockState(5, NOW + LOCK)


def test_a_failure_after_the_lock_passed_starts_again_at_one() -> None:
    assert after_failure(LockState(5, NOW - SECOND), NOW) == LockState(1, None)


def test_a_failure_in_the_same_second_as_the_expiry_keeps_counting() -> None:
    """now == expiry 는 아직 지나지 않았다(now > expiry 일 때만 셈을 0 으로 본다).
    부르는 쪽은 잠김이면 여기까지 오지 않는다(is_locked 가 먼저 막는다)."""
    assert after_failure(LockState(5, NOW), NOW) == LockState(6, NOW + LOCK)
