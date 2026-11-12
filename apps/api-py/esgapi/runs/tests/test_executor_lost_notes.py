"""사라진 쪽지 멈춤 둘(RM1c ③′ — T17·T18, 635-5)을 진짜 DB·가짜 모듈·가짜 브로커로 잰다. 업무 층.

RM1b 시험의 틀(test_executor_parallel — 가짜 흐름 `probe.segmented@1`, 쪽지를 모으는 가짜 브로커)을 쓴다. 쪽지가
「죽는」 것은 잡기 블록만 하고 끝냄을 부르지 않는 것으로, 쪽지를 「잃는」 것은 가짜 브로커에서 지우는 것으로 짓는다.
countdown 이 있는 쪽지는 넣을 때 시계를 그만큼 앞당긴다(브로커의 미룸 흉내). 값은 지어낸 것이다.
"""

from datetime import timedelta
from typing import Any, cast

import pytest
from django.db import transaction

from esgapi.runs import tasks
from esgapi.runs.models import RunResultRow
from esgapi.runs.service.services import runs as services
from esgapi.runs.service.services.runs import EndDone, NothingToClaim, SegmentClaimed, Superseded
from esgapi.runs.tests import test_executor_parallel as parallel_tests
from esgapi.runs.tests.test_executor_parallel import Par, claim_directly, deliver, execute
from esgapi.runs.tests.test_executor_segments import SETTINGS, new_run, run_row, segment_statuses

pytestmark = pytest.mark.django_db


@pytest.fixture
def two(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> Par:
    """상한 2 의 세계."""
    return cast("Par", getattr(parallel_tests, "_world")(monkeypatch, companies, 2))  # noqa: B009 — RM1b 의 틀


def drain_in_time(world: Par, *, limit: int = 100, seen: list[int] | None = None) -> list[int]:
    """쪽지를 차례로 넣는다. countdown 이 있는 쪽지는 넣기 전에 시계를 그만큼 앞당긴다.
    돌려주는 것은 넣은 미룬 쪽지의 countdown 목록. seen 을 주면 넣은 구획 쪽지마다의 countdown 을 차례로 쌓는다."""
    delayed: list[int] = []
    delivered = 0
    while world.notes:
        kind, kw = world.notes.pop(0)
        countdown = int(kw.get("countdown", 0) or 0)
        if kind == "segment" and seen is not None:
            seen.append(countdown)
        if kind == "segment" and countdown > 0:
            delayed.append(countdown)
            world.now += timedelta(seconds=countdown)
        deliver(world, kind, kw)
        delivered += 1
        assert delivered < limit, "쪽지가 끝나지 않는다"
    return delayed


def segment_note(world: Par, run_id: int, attempt: int = 1) -> None:
    """늦게 온(재전달된) 구획 쪽지 하나를 바로 넣는다."""
    tasks.execute_segment(world, company_id=str(world.company_id), run_id=str(run_id), run_attempt=str(attempt))


# ── T17 임대가 산 채 사슬이 끝남(M1) ───────────────────────────────────


def test_a_dead_note_holding_a_live_lease_is_taken_over_by_a_delayed_note(two: Par) -> None:
    two.script.count = 3
    run_id = new_run(two)
    execute(two, run_id)  # 주차 · 쪽지 둘
    assert len(two.segment_notes()) == 2
    two.notes.pop(0)  # 쪽지 하나는 잡기 블록만 하고 죽는다(끝냄 0 — 임대는 산 채)
    held = claim_directly(two, run_id)
    assert isinstance(held, SegmentClaimed) and held.position == 0
    seen: list[int] = []
    delayed = drain_in_time(two, seen=seen)
    assert delayed == [SETTINGS.lease_s + 1]  # 가장 이른 임대 끝 − now + 1, 하나만
    # X6(RM1c ③): 미룸은 마지막 끝냄이 바로 건다(끝냄 갈래의 ended.delay) — 0 초 쪽지가 잡기에서 다시 미루는 길이면
    # 구획 쪽지가 넷이 된다(남은 쪽지 · 이어 넣기 · 0 초 · 미룬 것)
    assert seen == [0, 0, SETTINGS.lease_s + 1]
    run = run_row(two, run_id)
    assert (run.status, run.error_code) == ("done", None)
    assert segment_statuses(two, run_id) == ["done"] * 3
    assert sorted(two.script.called) == [1, 2, 3]
    assert two.woken == 1


def test_a_claim_with_nothing_to_take_but_a_live_lease_delays_one_note(two: Par) -> None:
    two.script.count = 2
    run_id = new_run(two)
    execute(two, run_id)
    two.notes.clear()
    first = claim_directly(two, run_id)
    assert isinstance(first, SegmentClaimed)
    second = claim_directly(two, run_id)
    assert isinstance(second, SegmentClaimed)
    assert claim_directly(two, run_id) == NothingToClaim(wake=False)  # full — 산 쪽지가 끝내며 이어 넣는다(미룸 0)
    # 하나를 끝내면 남은 것은 임대 산 running 하나 — 잡기는 미룸을 준다
    with transaction.atomic():
        services.segment_end(
            company_id=two.company_id,
            run_id=run_id,
            run_attempt=1,
            step="spread",
            key_sha256=second.key_sha256,
            attempt=second.attempt,
            outcome=EndDone(data={"square": 4}),
            now=two.now,
            lease_s=SETTINGS.lease_s,
            parallel_max=2,
            on_failure="pass_to_gather",
        )
    assert claim_directly(two, run_id) == NothingToClaim(wake=False, delay=SETTINGS.lease_s + 1)


# ── T18 깨운 뒤 지휘 쪽지를 잃음(M2) ───────────────────────────────────


def lose_the_wake(world: Par, run_id: int) -> None:
    """구획을 다 끝내 지휘를 깨우게 하고, 그 지휘 쪽지를 가짜 브로커에서 지운다."""
    execute(world, run_id)
    while any(kind == "segment" for kind, _ in world.notes):
        index = next(i for i, (kind, _) in enumerate(world.notes) if kind == "segment")
        kind, kw = world.notes.pop(index)
        deliver(world, kind, kw)
    assert world.wakes() == 1
    world.notes.clear()  # 지휘 쪽지를 잃음
    row = run_row(world, run_id)
    assert (row.status, row.parked_at, row.lease_expires_at) == ("processing", None, None)


def test_within_a_lease_after_the_wake_a_late_note_adds_no_conductor_note(two: Par) -> None:
    """문턱 안(깨운 때 + lease_s − 1초까지): 늦은 구획 쪽지는 지휘 쪽지를 더하지 않는다(정상 깨움 뒤의 남은 쪽지)."""
    two.script.count = 2
    run_id = new_run(two)
    lose_the_wake(two, run_id)
    woken = cast("Any", run_row(two, run_id).updated_at)  # 깨운 때
    for after in (0, SETTINGS.lease_s - 1):
        two.now = woken + timedelta(seconds=after)
        segment_note(two, run_id)
        assert claim_directly(two, run_id) == Superseded()
    assert two.notes == []
    assert run_row(two, run_id).status == "processing"


def test_past_a_lease_a_woken_untaken_run_is_woken_once_and_finishes(two: Par) -> None:
    """문턱 넘어(processing · attempts=k · parked NULL · 임대 NULL): 늦은 쪽지 하나 = 깨움 하나 → done."""
    two.script.count = 2
    run_id = new_run(two)
    lose_the_wake(two, run_id)
    two.now = cast("Any", run_row(two, run_id).updated_at) + timedelta(seconds=SETTINGS.lease_s)
    assert claim_directly(two, run_id) == Superseded(wake=True)  # 쓰기 0 — 판정만
    segment_note(two, run_id)
    assert two.wakes() == 1
    drain_in_time(two)
    run = run_row(two, run_id)
    assert (run.status, run.error_code, run.attempts) == ("done", None, 2)


def test_two_late_notes_wake_twice_and_the_run_finishes_once(two: Par) -> None:
    two.script.count = 2
    run_id = new_run(two)
    lose_the_wake(two, run_id)
    two.now = cast("Any", run_row(two, run_id).updated_at) + timedelta(seconds=SETTINGS.lease_s + 1)
    segment_note(two, run_id)
    segment_note(two, run_id)
    assert two.wakes() == 2
    drain_in_time(two)
    run = run_row(two, run_id)
    assert (run.status, run.attempts) == ("done", 2)  # 둘째 지휘 쪽지는 claim_run 이 걸렀다
    assert RunResultRow.for_company(two.company_id).filter(run_id=run_id).count() == 1
    segment_note(two, run_id)  # 지휘가 잡은 뒤(시도가 늘었다)의 늦은 쪽지는 그냥 Superseded
    assert two.notes == []
