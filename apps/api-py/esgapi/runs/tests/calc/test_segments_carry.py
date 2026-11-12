"""구획 옮김·짝짓기의 순수 판정(RM1c ① — T1·T2). DB 0. 값은 지어낸 것이다."""

from datetime import UTC, datetime

import pytest

from esgapi.runs.calc.segments import (
    Both,
    OnlyA,
    OnlyB,
    SegmentCarry,
    SegmentRef,
    carried_segments,
    data_octets,
    pair_segments,
)

AT = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def ref(position: int, sha: str, status: str = "done") -> SegmentRef:
    return SegmentRef(position=position, key_sha256=sha, key={"span": sha}, status=status, error_code=None)


# ── T1 짝짓기 ─────────────────────────────────────────────────────────


def test_the_same_keys_in_a_different_order_pair_up_in_a_s_order() -> None:
    a = (ref(0, "x"), ref(1, "y"), ref(2, "z"))
    b = (ref(0, "z"), ref(1, "x"), ref(2, "y"))
    pairs = pair_segments(a, b)
    assert pairs == (Both(a=a[0], b=b[1]), Both(a=a[1], b=b[2]), Both(a=a[2], b=b[0]))


def test_a_different_parser_version_leaves_every_segment_alone() -> None:
    a = (ref(0, "p1-a"), ref(1, "p1-b"))
    b = (ref(0, "p2-a"), ref(1, "p2-b"))
    assert pair_segments(a, b) == (OnlyA(a=a[0]), OnlyA(a=a[1]), OnlyB(b=b[0]), OnlyB(b=b[1]))


def test_one_empty_side_and_the_order_a_then_b_only() -> None:
    a = (ref(0, "x"),)
    assert pair_segments(a, ()) == (OnlyA(a=a[0]),)
    assert pair_segments((), a) == (OnlyB(b=a[0]),)
    assert pair_segments((), ()) == ()
    b = (ref(0, "w"), ref(1, "x"))
    assert pair_segments(a, b) == (Both(a=a[0], b=b[1]), OnlyB(b=b[0]))


@pytest.mark.parametrize("side", ["a", "b"])
def test_a_repeated_key_on_one_side_is_a_value_error(side: str) -> None:
    twice = (ref(0, "x"), ref(1, "x"))
    with pytest.raises(ValueError, match="같은 열쇠"):
        pair_segments(twice, ()) if side == "a" else pair_segments((), twice)


# ── T2 옮김 판정 ──────────────────────────────────────────────────────


def row(step: str, position: int, status: str, *, octets: int | None = None) -> SegmentCarry:
    done = status == "done"
    ended = status in {"done", "failed"}
    return SegmentCarry(
        step=step,
        position=position,
        kind="block",
        key={"kind": "block", "span": f"b{position}", "documentSha256": None, "parserVersion": "p1"},
        key_sha256=f"{step}-{position}",
        status=status,
        data={"square": position * position} if done else None,
        data_octets=octets if done else None,
        error_code="step_error" if status == "failed" else None,
        started_at=None if status == "pending" else AT,
        finished_at=AT if ended else None,
    )


START = (row("spread", 0, "done"), row("spread", 1, "failed"), row("spread", 2, "running"), row("spread", 3, "pending"))


def test_resume_keeps_the_done_of_the_start_step_and_makes_the_rest_pending() -> None:
    out = carried_segments(START, carried_steps=frozenset({"prepare"}), start_step="spread", previous_error=None)
    assert [(r.position, r.status) for r in out] == [(0, "done"), (1, "pending"), (2, "pending"), (3, "pending")]
    kept = out[0]
    assert (kept.data, kept.started_at, kept.finished_at) == ({"square": 0}, AT, AT)
    assert kept.data_octets == data_octets({"square": 0})  # 직렬 done(NULL)은 다시 센다
    for cleared in out[1:]:
        assert (cleared.data, cleared.error_code, cleared.started_at, cleared.finished_at) == (None, None, None, None)
        assert cleared.key_sha256 == f"spread-{cleared.position}"  # 열쇠는 그대로


def test_a_carried_done_fanout_step_keeps_every_row_and_a_later_step_none() -> None:
    rows = (
        row("spread", 0, "done", octets=99),
        row("spread", 1, "failed"),
        row("tail", 0, "done"),
        row("tail", 1, "pending"),
    )
    out = carried_segments(
        rows, carried_steps=frozenset({"prepare", "spread"}), start_step="gather", previous_error=None
    )
    assert [(r.step, r.position, r.status, r.data_octets) for r in out] == [
        ("spread", 0, "done", 99),  # 적힌 값은 그대로
        ("spread", 1, "failed", None),
    ]
    assert out[1].error_code == "step_error"


def test_a_carried_done_fanout_step_with_an_unended_row_is_a_runtime_error() -> None:
    rows = (row("spread", 0, "done"), row("spread", 1, "running"))
    with pytest.raises(RuntimeError, match="끝나지 않은"):
        carried_segments(rows, carried_steps=frozenset({"spread"}), start_step="gather", previous_error=None)


def test_after_segments_mismatch_the_start_step_is_planned_from_scratch() -> None:
    rows = (row("early", 0, "done"), *START)
    out = carried_segments(
        rows, carried_steps=frozenset({"early"}), start_step="spread", previous_error="segments_mismatch"
    )
    assert [(r.step, r.status) for r in out] == [("early", "done")]  # 옮긴 펼침은 그대로, 시작 단계 0


def test_a_retry_makes_the_chosen_pending_and_keeps_the_others_as_they_were() -> None:
    rows = (row("spread", 0, "done"), row("spread", 1, "failed"), row("spread", 2, "failed"), row("spread", 3, "done"))
    out = carried_segments(
        rows,
        carried_steps=frozenset({"prepare"}),
        start_step="spread",
        previous_error="segments_mismatch",  # 고른 다시는 B3 규칙 밖(done 앞뿐)
        retry_keys=frozenset({"spread-1", "spread-3"}),
    )
    assert [(r.position, r.status, r.error_code) for r in out] == [
        (0, "done", None),
        (1, "pending", None),
        (2, "failed", "step_error"),  # 안 고른 실패는 모음에 failed
        (3, "pending", None),
    ]


def test_data_octets_is_the_compact_json_bytes() -> None:
    assert data_octets({"square": 4}) == len(b'{"square": 4}')
    assert data_octets({"말": "가"}) == len('{"말": "가"}'.encode())
