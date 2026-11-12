"""펼침 구획을 쪽지 여럿이 나눠 돌 때의 순수 판정(RM1b — sid:MARC-TICK-567). 시계·DB 는 인자로만 받는다.

    SEGMENT_PARALLEL_DEFAULT                     실행 하나에서 동시에 도는 구획 수의 기본(감독 답 Q3 — 어림)
    SegmentCounts                                한 펼침 단계의 구획 셈(selectors.segment_counts 가 채운다)
    wake_due(on_failure, counts, newly_failed)   이 블록 뒤 지휘를 깨울 때인가
    claim_plan(running, first_pending, …)        잡기 블록이 무엇을 소진으로 끝내고 무엇을 잡는가
    delayed_due(unended, alive, parallel_max)    이어 넣기 0 일 때 쪽지 하나를 임대 뒤로 미뤄 넣을 때인가(RM1c ③′)
    delay_after(earliest, now)                   그 미룸(가장 이른 임대 끝 − now + 1 초, 1 이상)
    data_octets(data)                            구획 data 를 json 기본 구분자로 적은 바이트(RM1c — services 에서 옮김)
    carried_segments(rows, …)                    새 실행(이어 돌기·고른 다시 — RM1c)이 앞 실행에서 옮길 구획 행
    pair_segments(a, b)                          두 실행의 구획을 열쇠 sha 로 짝짓는다(RM1c — 견줌 API 0)

뜻:
  잡을 수 있는 running = 임대 NULL(놓음·직렬의 것) 또는 임대 ≤ now(쥔 쪽지가 죽었다 — stale_runs 의 꼴)
  임대 산 running      = 임대 > now(다른 쪽지가 돌고 있다) — 이것만 동시 상한에 센다
  소진                  = 잡을 수 있는 running 가운데 attempts ≥ max_attempts(구획 시도 상한 — 잠깐 오류도 센다, Qn3)
  깨우기               = 끝나지 않은 구획 0, 또는 fail_run 이고 이 블록이 만든 failed 로 그 단계 failed 가 0 → ≥1
                         (뒤 블록은 parked_at 이 비어 Superseded — 그래서 한 번)

구획 옮김(RM1c — sid:MARC-TICK-572, 635-4):
  옮겨 온 구획 = attempts 0 인 done·failed(이 실행에서 끝난 행은 attempts ≥ 1). 시각(started_at·finished_at)은 앞 실행의
  것 그대로라 단계의 firstStartedAt 이 새 실행의 createdAt 보다 이를 수 있다.
  이어 돌기: 옮긴(done) 펼침 단계의 행은 전부 그대로 · 시작 단계(옮긴 단계 뒤 첫 끝나지 않은 단계)가 펼침이면 done 은
  done(data·시각 그대로), 나머지는 pending(칸 비움) · 그 뒤 단계의 행은 옮기지 않는다.
  고른 다시(done 실행에서): 시작 단계 = 고른 단계. 고른 열쇠는 pending, 안 고른 것은 상태 그대로(안 고른 failed 는
  모음에 failed).
  ★ 무효 조건: 앞 실행이 segments_mismatch 로 끝났으면 이어 돌기는 시작 단계의 구획을 옮기지 않는다(처음부터 — 옮기면
  같은 어긋남을 되풀이한다). 파서 판만 바뀐 배포 뒤의 이어 돌기·고른 다시는 옮긴 열쇠(parserVersion 이 든다)가 새 계획과
  달라 첫 시도 segments_mismatch 로 끝난다 — 흐름 판(versions)에는 파서 판이 없어 고른 다시도 409 가 아니다.
  다시 이어 돌면 처음부터다.
"""

import json
import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final

SEGMENT_PARALLEL_DEFAULT: Final = 2
"""실행 하나의 동시 구획 상한 기본(어림 — 감독 답 Q3). 1 이면 RM1a 직렬(쪽지 0).
금액 넘침 최악 ≈ (상한−1) × 구획 하나."""


@dataclass(frozen=True, slots=True)
class SegmentCounts:
    """한 펼침 단계의 구획 셈과 시각(가장 이른 시작·가장 늦은 끝 — 없으면 None)."""

    pending: int
    running: int
    done: int
    failed: int
    first_started_at: datetime | None
    last_finished_at: datetime | None

    @property
    def planned(self) -> int:
        return self.pending + self.running + self.done + self.failed

    @property
    def unended(self) -> int:
        return self.pending + self.running


def wake_due(on_failure: str, counts: SegmentCounts, newly_failed: int) -> bool:
    """구획 상태를 바꾼 블록 뒤(counts 는 그 블록이 쓴 뒤의 셈) 지휘를 깨울 때인가.

    끝나지 않은 구획 0 → 참(모음). fail_run 이고 이 블록이 failed 를 만들었고 그 앞에는 failed 가 0 이었다 → 참
    (첫 실패에서 깨움 — 돌던 구획의 산출은 버린다). 그 밖은 거짓."""
    if newly_failed < 0 or newly_failed > counts.failed:
        raise ValueError(f"이 블록이 만든 failed {newly_failed} 가 셈 failed {counts.failed} 밖이다")
    if counts.unended == 0:
        return True
    return on_failure == "fail_run" and newly_failed > 0 and counts.failed - newly_failed == 0


@dataclass(frozen=True, slots=True)
class SegmentHead:
    """구획 행의 머리(data 0): 계획 차례·열쇠 sha·상태·시작한 횟수·임대."""

    position: int
    key_sha256: str
    status: str
    attempts: int
    lease_expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class ClaimPlan:
    """잡기 블록이 할 일: exhaust 를 failed·attempts_exhausted 로 끝내고, take 가 있으면 그것을 잡는다.

    full = 임대 산 running 이 상한에 닿아 아무것도 하지 않음(exhaust·take 둘 다 빔)."""

    exhaust: tuple[SegmentHead, ...]
    take: SegmentHead | None
    alive: int
    full: bool


def claimable(head: SegmentHead, now: datetime) -> bool:
    """잡을 수 있는가: pending, 또는 running 이고 임대가 없거나 지났다."""
    if head.status == "pending":
        return True
    return head.status == "running" and (head.lease_expires_at is None or head.lease_expires_at <= now)


def claim_plan(
    running: tuple[SegmentHead, ...],
    first_pending: SegmentHead | None,
    *,
    now: datetime,
    parallel_max: int,
    max_attempts: int,
) -> ClaimPlan:
    """잡기의 판정. running = 그 단계의 running 전부, first_pending = 계획 차례 첫 pending(없으면 None).

    ① 임대 산 running ≥ parallel_max → 아무것도 안 함(full) ② 잡을 수 있는 running 가운데 attempts ≥ max_attempts 는
    소진 ③ 남은 잡을 수 있는 running 과 first_pending 가운데 계획 차례가 가장 앞인 것을 잡는다."""
    if parallel_max < 1 or max_attempts < 1:
        raise ValueError("parallel_max·max_attempts 는 1 이상이다")
    if any(head.status != "running" for head in running):
        raise ValueError("running 목록에 running 이 아닌 행이 있다")
    if first_pending is not None and first_pending.status != "pending":
        raise ValueError("first_pending 이 pending 이 아니다")
    alive = sum(1 for head in running if not claimable(head, now))
    if alive >= parallel_max:
        return ClaimPlan(exhaust=(), take=None, alive=alive, full=True)
    loose = sorted((head for head in running if claimable(head, now)), key=lambda head: head.position)
    exhaust = tuple(head for head in loose if head.attempts >= max_attempts)
    candidates = [head for head in loose if head.attempts < max_attempts]
    if first_pending is not None:
        candidates.append(first_pending)
    take = min(candidates, key=lambda head: head.position) if candidates else None
    return ClaimPlan(exhaust=exhaust, take=take, alive=alive, full=False)


def successor_due(*, on_failure: str, counts: SegmentCounts, alive: int, parallel_max: int) -> bool:
    """끝냄 블록 뒤 쪽지를 하나 더 넣을 때인가: 잡을 것이 남았고(끝나지 않은 것 가운데 임대 산 것 밖) 임대 산 running 이
    상한 밑이며, fail_run 에서 실패가 이미 있으면 아니다."""
    if on_failure == "fail_run" and counts.failed > 0:
        return False
    return counts.unended - alive > 0 and alive < parallel_max


def delayed_due(*, unended: int, alive: int, parallel_max: int) -> bool:
    """이어 넣기가 0 인 블록 뒤(RM1c ③′ M1 — 635-5): 끝나지 않은 구획이 전부 임대 산 running 이고(unended == alive > 0)
    상한이 차지 않았으면 참 — 그 임대를 쥔 쪽지가 죽었으면 임대가 끝난 뒤 잡으러 올 쪽지가 없다. 미룬 쪽지가 남아 헛돌면
    NothingToClaim 으로 끝날 뿐이다. full(alive ≥ 상한)은 거짓(산 쪽지가 끝내며 이어 넣는다)."""
    return 0 < alive < parallel_max and unended == alive


def delay_after(earliest: datetime, now: datetime) -> int:
    """미룬 쪽지의 countdown 초: 가장 이른 임대 끝 − now + 1(올림, 1 이상)."""
    return max(1, math.ceil((earliest - now).total_seconds()) + 1)


def data_octets(data: Mapping[str, object]) -> int:
    """jsonb 를 글로 적은 크기의 어림(json 기본 구분자 — core/flows/run.py 의 _octets 와 같은 꼴).
    병렬 끝냄이 적고(RM1b), 옮긴 done 의 빈 칸을 채운다(RM1c — 정본 하나)."""
    return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))


# ── 구획 옮김(RM1c) ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SegmentCarry:
    """옮길 구획 행 하나(새 실행에 쓸 칸 — attempts 는 늘 0, 임대는 늘 NULL 이라 싣지 않는다)."""

    step: str
    position: int
    kind: str
    key: Mapping[str, object]
    key_sha256: str
    status: str
    data: Mapping[str, object] | None
    data_octets: int | None
    error_code: str | None
    started_at: datetime | None
    finished_at: datetime | None


ENDED: Final = frozenset({"done", "failed"})


def _kept(row: SegmentCarry) -> SegmentCarry:
    """끝난 행을 그대로 옮긴다. done 의 data_octets 가 비었으면(직렬 — RM1b D1) 다시 센다."""
    if row.status not in ENDED:
        raise RuntimeError(f"옮길 단계 {row.step} 에 끝나지 않은 구획이 있다(#{row.position} {row.status})")
    if row.status == "done" and row.data_octets is None:
        if row.data is None:
            raise RuntimeError(f"옮길 단계 {row.step} 의 done 구획에 data 가 없다(#{row.position})")
        return replace(row, data_octets=data_octets(row.data))
    return row


def _pending(row: SegmentCarry) -> SegmentCarry:
    return replace(
        row, status="pending", data=None, data_octets=None, error_code=None, started_at=None, finished_at=None
    )


def carried_segments(
    rows: tuple[SegmentCarry, ...],
    *,
    carried_steps: Collection[str],
    start_step: str | None,
    previous_error: str | None,
    retry_keys: Collection[str] | None = None,
) -> tuple[SegmentCarry, ...]:
    """앞 실행의 구획 행 → 새 실행에 쓸 행(머리말의 표). rows 의 차례 그대로.

    carried_steps  새 실행이 done 으로 옮긴 단계 — 그 단계의 행은 전부 그대로(끝나지 않은 행이 있으면 RuntimeError)
    start_step     새 실행이 처음 도는 단계(없으면 None) — 이어 돌기는 done 만 done, 나머지 pending
    retry_keys     고른 다시의 고른 열쇠 sha(시작 = 고른 단계: 고른 것 pending, 나머지 그대로). None = 이어 돌기
    previous_error 앞 실행의 error_code — 이어 돌기에서 segments_mismatch 면 시작 단계 행 0(처음부터)"""
    out: list[SegmentCarry] = []
    for row in rows:
        if row.step in carried_steps:
            out.append(_kept(row))
        elif row.step == start_step:
            if retry_keys is not None:
                out.append(_pending(row) if row.key_sha256 in retry_keys else _kept(row))
            elif previous_error == "segments_mismatch":
                continue
            else:
                out.append(_kept(row) if row.status == "done" else _pending(row))
    return tuple(out)


# ── 구획 짝짓기(RM1c — 두 실행의 구획을 열쇠로) ───────────────────────


@dataclass(frozen=True, slots=True)
class SegmentRef:
    """구획 하나의 머리(data 0) — 짝짓기와 구획 목록이 쓴다."""

    position: int
    key_sha256: str
    key: Mapping[str, object]
    status: str
    error_code: str | None


@dataclass(frozen=True, slots=True)
class Both:
    """두 실행에 같은 열쇠의 구획이 있다."""

    a: SegmentRef
    b: SegmentRef


@dataclass(frozen=True, slots=True)
class OnlyA:
    a: SegmentRef


@dataclass(frozen=True, slots=True)
class OnlyB:
    b: SegmentRef


type SegmentPair = Both | OnlyA | OnlyB


def _by_sha(refs: tuple[SegmentRef, ...], side: str) -> dict[str, SegmentRef]:
    found: dict[str, SegmentRef] = {}
    for ref in refs:
        if ref.key_sha256 in found:
            raise ValueError(f"{side} 쪽에 같은 열쇠의 구획이 둘이다: {ref.key_sha256}")
        found[ref.key_sha256] = ref
    return found


def pair_segments(a: tuple[SegmentRef, ...], b: tuple[SegmentRef, ...]) -> tuple[SegmentPair, ...]:
    """열쇠 sha 로 짝짓는다(position 이 아니다). 차례 = A 의 차례(Both·OnlyA) 뒤 B 에만 있는 것(B 의 차례).
    한쪽 안에 같은 sha 가 둘이면 ValueError. 흐름 판은 열쇠 밖이라 같은 문서·파서면 판 A·B 가 짝지고, 파서 판이 다르면
    전부 Only 다."""
    in_b = _by_sha(b, "B")
    in_a = _by_sha(a, "A")
    pairs: list[SegmentPair] = [
        Both(a=ref, b=in_b[ref.key_sha256]) if ref.key_sha256 in in_b else OnlyA(a=ref) for ref in a
    ]
    pairs.extend(OnlyB(b=ref) for ref in b if ref.key_sha256 not in in_a)
    return tuple(pairs)
