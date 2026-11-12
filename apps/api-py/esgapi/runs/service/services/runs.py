"""흐름의 실행(표 run_runs)과 그 단계·결과·파일을 워커가 쓰는 자리. HTTP 도 Celery 도 모른다.

    claim_run(company_id, run_id, now, lease_s, max_attempts)       잡기: 행을 잠그고 판정한 뒤 `processing` 으로
    step_started · step_progress · step_finished(…, attempt, …)      단계 행 하나씩(흐름의 사건). 임대를 당긴다
    segments_planned · segment_started · segment_finished · segment_failed(…, attempt, …)
                                                                     구획 행(펼침 단계의 사건 — RM1a). 임대를 당긴다
    finish_run(company_id, run_id, attempt, now, outcome)            끝내기: done(결과·출력 파일 행)·failed,
                                                                     또는 다시 넣기, 또는 주차(RM1b)
    segment_claim(…, run_attempt, now, lease_s, parallel_max, max_attempts, on_failure)
                                                                     구획 쪽지의 잡기(RM1b): 구획 하나를 임대
    segment_end(…, run_attempt, step, key_sha256, attempt, outcome, now, lease_s, parallel_max, on_failure)
                                                                     구획 쪽지의 끝냄(RM1b): Done·Failed·Fatal·Released

읽기는 여기 없다(runs/service/selectors/runs.py 의 lock_run·step_rows). 이 파일이 표에 직접 하는 것은 쓰기뿐이다.
결과는 예외가 아니라 갈래로 돌려준다. 판정의 규칙은 runs/calc/claims.py(순수)에 있다.
**트랜잭션 안에서** 부른다(워커 runs/tasks.py 의 transaction.atomic(durable=True) 블록). 밖이면 던진다.
그래서 이 파일은 core/tests/test_transaction_rules.py 의 WORKER_SERVICES 다: 한 함수가 실행·단계·결과·파일 표에 같이
쓰지만 그 블록은 부르는 쪽(태스크)의 것이다. 저장소·흐름·LLM·큐는 이 파일에서 부르지 않는다(그 시험의 새 규칙 —
WORKER_SERVICES 파일에는 바깥 호출 이름의 부름이 0).

★ 중복은 큐가 아니라 여기서 막는다(runs/service/services/jobs.py 와 같은 꼴):
  - 잡기는 행을 잠근 뒤 상태와 임대를 본다. 끝난 실행·남이 쥔 실행은 잡지 않는다.
  - **잡기 뒤의 쓰기에는 늘 「processing 이고 attempts 가 내 시도」 조건이 있다**(울타리). 임대가 끝나 다른 워커가
    이어받았으면(attempts 가 늘었다) 0행이고 Superseded 다: 먼저 잡았던 워커는 늦게 쓰지 못한다.
  - 갱신한 행 수가 맞지 않으면 RunUpdateError 다(트랜잭션이 되돌려진다).
★ 진행(시도 상한의 셈 — runs/calc/claims.py): step_progress 는 받은 done 이 그 단계 행에 **저장돼 있던**
  done(NULL 이면 0)보다 클 때만, step_finished 는 늘 progress_attempt = 내 시도를 적는다. 끝내기 RunDeferred 는
  행의 progress_attempt 가 내 시도가 아니면 stalled_attempts +1(진행 없이 끝난 시도).
  부분 산출(partial)을 저장하는 자리는 step_progress 하나다. segment_finished·segment_failed 도 진행이다(구획 하나가
  끝났다). segments_planned·segment_started 는 진행이 아니다.
★ 구획의 전이(RM1a): pending→running · running→running(새 시도) · running→done|failed. done·failed 행에 쓰려 하면
  RunUpdateError(그 실행 안에서 끝 — 다시 부름은 RM1c 의 새 실행). 계획은 첫 시도가 전부 pending 으로 넣고, 다음
  시도는 저장된 (position, key_sha256) 목록과 같으면 0행, 다르면 PlanMismatch(실행기가 segments_mismatch 로 끝낸다).
★ 단계 행을 failed 로 쓰는 것은 끝내기(RunFailed{step})뿐이다 — 흐름의 step_failed 사건은 행을 쓰지 않는다(그 시도가
  다시 넣기로 끝나면 실행 queued · 단계 failed 의 어긋남이 생기므로).
★ 구획 쪽지(RM1b): 지휘 시도 k 가 펼침에 닿으면 finish_run(RunParkedOutcome)으로 주차(parked_at = now, status
  processing 그대로). 구획 쪽지의 블록(segment_claim·segment_end)은 **첫 문이 lock_run(FOR UPDATE)** 이고 조건은
  「processing · attempts = k · parked_at 있음」(아니면 Superseded). 구획 행의 쓰기 조건은
  「running · attempts = 내 구획 시도」 — 이어받긴 구획의 옛 쪽지는 Superseded, 같은 구획 시도로 두 번 끝내면
  RunUpdateError. 구획 상태를 바꾼 블록이 깨우기(runs/calc/segments.wake_due)를 만들면 parked_at·실행 임대를 비우고
  progress_attempt = k(잡기 Take 가 stalled 를 세지 않게) — 뒤 블록은 parked_at 이 비어
  Superseded 라 깨우기는 한 번. 쪽지는 부른 쪽(태스크)이 커밋 뒤 넣는다.
★ 사라진 쪽지 멈춤 둘(RM1c ③′ — 635-5):
  M1 끝냄(_ended)·잡기(take 없음·full 아님)에서 이어 넣기가 0 이고 끝나지 않은 구획이 전부 임대 산 running 이면
     (runs/calc/segments.delayed_due) 가장 이른 임대 끝 − now + 1 초 뒤 쪽지 하나(Ended.delay·NothingToClaim.delay).
     그 임대를 쥔 쪽지가 죽었으면 미룬 쪽지가 임대 뒤 이어받고, 살아 있으면 헛돌아 NothingToClaim 으로 끝난다.
  M2 잡기의 첫 문이 「processing · attempts = k · parked_at NULL · 임대 NULL」(깨웠는데 아직 지휘가 안 잡음)이고 깨운 때
     (updated_at)가 lease_s 보다 오래면 Superseded(wake=True) — 부른 쪽이 지휘 쪽지를 다시 넣는다(claim_run 이 중복을
     거른다 — 지휘가 잡으면 attempts 가 늘어 그 뒤 쪽지는 그냥 Superseded). 쓰기는 0. lease_s 문턱은 깨운 바로 뒤의 남은
     쪽지가 지휘 쪽지를 늘리지 않게 하는 좁힘이다(보고 ③′).
  ★ 무효 조건: 쪽지를 전부 잃으면(미룬 쪽지까지) 여전히 requeue_runs 다(E2 — 밴드 밖).
★ 실행 표 넷은 지우지 않는다(delete 0 — 앱 역할에 DELETE 도 없다). 결과·파일 행은 한 번 쓰고 끝(UPDATE 권한 없음).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import connection
from django.db.models import Case, F, QuerySet, Value, When
from django.db.models.functions import Coalesce

from esgapi.core.calc.jobs import (
    MAX_ERROR_CODE_CHARS,
    MAX_ERROR_MESSAGE_CHARS,
    AlreadyFinished,
    Exhausted,
    LeaseHeld,
    Take,
    lease_until,
)
from esgapi.core.flows.types import FANOUT_DATA_MAX_OCTETS, SegmentKey, segment_key_fields, segment_key_sha256
from esgapi.runs.calc.claims import run_claim
from esgapi.runs.calc.errors import RUN_ERROR_MESSAGES
from esgapi.runs.calc.segments import (
    SegmentCounts,
    claim_plan,
    data_octets,
    delay_after,
    delayed_due,
    successor_due,
    wake_due,
)
from esgapi.runs.models import RUN_RESULT_BODY_MAX_OCTETS, RunFileRow, RunResultRow, RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.selectors.jobs import NotInTransactionError
from esgapi.runs.service.selectors.runs import Run, RunNotFound


class RunUpdateError(Exception):
    """갱신한 행 수가 맞지 않는다. 조용히 넘어가지 않는다. 부른 쪽의 트랜잭션이 되돌려진다."""


class SegmentAlreadyEnded(RunUpdateError):
    """같은 구획 시도로 이미 끝난 구획 행을 다시 끝내려 했다(RM1b — 감독 처분 D2). 쪽지가 늦게 온 정상 경합이다(소진
    끝냄 뒤의 늦은 쪽지 등): 구획 쪽지 태스크는 이것만 받아 기록 한 줄로 삼킨다. 트랜잭션은 되돌려진다(쓰기 0)."""

    def __init__(self, *, step: str, position: int, attempt: int, status: str) -> None:
        super().__init__(f"run_segments 의 끝난 구획을 다시 끝내려 했다(단계 {step}, 시도 {attempt})")
        self.step = step
        self.position = position
        self.attempt = attempt
        self.status = status


def _require_transaction(name: str) -> None:
    if not connection.in_atomic_block:
        raise NotInTransactionError(f"{name} 는 transaction.atomic() 안에서만 부른다")


def _one(updated: int, table: str) -> None:
    if updated != 1:
        raise RunUpdateError(f"{table} 의 갱신이 {updated}행이다(1행이어야 한다)")


# ── 잡기 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Claimed:
    run: Run  # 잡은 뒤의 모습(`processing`, attempts = attempt)
    attempt: int


@dataclass(frozen=True, slots=True)
class NotClaimable:
    """끝난 실행이거나(AlreadyFinished) 다른 워커가 임대를 쥐고 있다(LeaseHeld). 쓰지 않았다."""

    why: AlreadyFinished | LeaseHeld


ClaimResult = Claimed | RunNotFound | Exhausted | NotClaimable


def claim_run(*, company_id: int, run_id: int, now: datetime, lease_s: int, max_attempts: int) -> ClaimResult:
    """실행 하나를 잡는다. 차례: ① FOR UPDATE 로 읽는다 → ② 판정(시도 상한의 셈) → ③ 읽은 상태·시도를 조건으로 쓴다.

    잡으면 `processing`·attempts+1·임대 = now + lease_s, started_at 은 비었을 때만(첫 잡기 한 번).
    진행 없이 끝난 시도가 상한에 닿았으면 `failed`·attempts_exhausted 로 끝낸다(Exhausted).
    """
    _require_transaction("claim_run")
    row = selectors.lock_run(company_id=company_id, run_id=run_id)  # ①
    if row is None:
        return RunNotFound()
    claim = run_claim(  # ②
        status=row.status,
        lease_expires_at=row.lease_expires_at,
        attempts=row.attempts,
        stalled_attempts=row.stalled_attempts,
        progress_attempt=row.progress_attempt,
        now=now,
        max_attempts=max_attempts,
    )
    decision = claim.decision
    if isinstance(decision, AlreadyFinished | LeaseHeld):
        return NotClaimable(decision)

    # ③ 울타리: 내가 읽은 상태와 시도 그대로일 때만 쓴다.
    guard = RunRow.for_company(company_id).filter(pk=run_id, status=row.status, attempts=row.attempts)
    if isinstance(decision, Exhausted):
        code = "attempts_exhausted"
        _one(
            guard.update(
                status="failed",
                stalled_attempts=claim.stalled_attempts,
                error_code=code,
                error_message=RUN_ERROR_MESSAGES[code],
                finished_at=now,
                lease_expires_at=None,
                parked_at=None,
                updated_at=now,
            ),
            "run_runs",
        )
        return decision

    assert isinstance(decision, Take)  # noqa: S101  (갈래를 다 걸렀다. 타입 검사기에게 알린다)
    _one(
        guard.update(
            status="processing",
            attempts=decision.attempt,
            stalled_attempts=claim.stalled_attempts,
            lease_expires_at=lease_until(now, lease_s),
            parked_at=None,
            started_at=Coalesce(F("started_at"), Value(now)),
            updated_at=now,
        ),
        "run_runs",
    )
    claimed = selectors.find_run(company_id=company_id, run_id=run_id)
    if claimed is None:
        raise RunUpdateError("방금 잡은 run_runs 의 행이 없다")
    return Claimed(claimed, decision.attempt)


# ── 단계의 사건 ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Recorded:
    pass


@dataclass(frozen=True, slots=True)
class Superseded:
    """내 시도가 더는 이 실행의 주인이 아니다(임대가 끝나 다른 워커가 이어받았거나 이미 끝났다). 쓰지 않았다.
    wake 는 segment_claim 만 쓴다(RM1c ③′ M2): 깨웠는데 아직 아무도 안 잡은 실행이면 참 — 부른 쪽이 지휘 쪽지를 다시
    넣는다(claim_run 이 중복을 거른다)."""

    wake: bool = False


@dataclass(frozen=True, slots=True)
class StoredFile:
    """저장소에 이미 쓴 파일 하나(행은 이것으로 적는다)."""

    name: str
    media_type: str
    storage_key: str
    size_bytes: int
    sha256: str


def _fence(*, company_id: int, run_id: int, attempt: int, now: datetime, lease_s: int, progressed: bool) -> bool:
    """울타리 + 임대 당김(+ 진행이면 progress_attempt). 내 시도가 아니면 False(0행)."""
    values: dict[str, object] = {"lease_expires_at": lease_until(now, lease_s), "updated_at": now}
    if progressed:
        values["progress_attempt"] = attempt
    updated = RunRow.for_company(company_id).filter(pk=run_id, status="processing", attempts=attempt).update(**values)
    if updated == 0:
        return False
    _one(updated, "run_runs")
    return True


def _step_guard(company_id: int, run_id: int, step: str) -> "QuerySet[RunStepRow]":
    """그 단계 행 하나를 고르는 쓰기의 조건(실행의 울타리는 _fence 가 먼저 섰다)."""
    return RunStepRow.for_company(company_id).filter(run_id=run_id, name=step)


def step_started(
    *, company_id: int, run_id: int, attempt: int, step: str, now: datetime, lease_s: int
) -> Recorded | Superseded:
    """단계 행을 running 으로(started_at 은 비었을 때만). 진행은 아니다(progress_attempt 그대로)."""
    _require_transaction("step_started")
    if not _fence(company_id=company_id, run_id=run_id, attempt=attempt, now=now, lease_s=lease_s, progressed=False):
        return Superseded()
    _one(
        _step_guard(company_id, run_id, step).update(
            status="running", started_at=Coalesce(F("started_at"), Value(now)), updated_at=now
        ),
        "run_steps",
    )
    return Recorded()


def step_progress(
    *,
    company_id: int,
    run_id: int,
    attempt: int,
    step: str,
    done: int,
    total: int,
    partial: Mapping[str, object],
    now: datetime,
    lease_s: int,
) -> Recorded | Superseded:
    """단계 안 체크포인트: done·total·partial 을 저장한다(partial 의 저장 자리는 여기 하나). 받은 done 이 저장돼 있던
    done(NULL 이면 0)보다 크면 진행이다(progress_attempt = 내 시도). 같은 done 을 다시 쓴 체크포인트는 진행이 아니다."""
    _require_transaction("step_progress")
    stored = next((s for s in selectors.step_rows(company_id=company_id, run_id=run_id) if s.name == step), None)
    if stored is None:
        raise RunUpdateError(f"run_steps 에 단계 {step} 의 행이 없다")
    progressed = done > (stored.done or 0)
    if not _fence(
        company_id=company_id, run_id=run_id, attempt=attempt, now=now, lease_s=lease_s, progressed=progressed
    ):
        return Superseded()
    _one(
        _step_guard(company_id, run_id, step).update(done=done, total=total, partial=dict(partial), updated_at=now),
        "run_steps",
    )
    return Recorded()


def step_finished(
    *,
    company_id: int,
    run_id: int,
    attempt: int,
    step: str,
    data: Mapping[str, object],
    files: tuple[StoredFile, ...],
    now: datetime,
    lease_s: int,
) -> Recorded | Superseded:
    """단계가 끝났다: 단계 행 done·data(체크포인트)와 그 단계의 파일 행. 늘 진행이다(progress_attempt = 내 시도).
    파일의 바이트는 부른 쪽이 블록 밖에서 이미 저장소에 썼다."""
    _require_transaction("step_finished")
    if not _fence(company_id=company_id, run_id=run_id, attempt=attempt, now=now, lease_s=lease_s, progressed=True):
        return Superseded()
    _one(
        _step_guard(company_id, run_id, step).update(status="done", data=dict(data), finished_at=now, updated_at=now),
        "run_steps",
    )
    _create_files(company_id=company_id, run_id=run_id, step=step, files=files)
    return Recorded()


# ── 구획(RM1a) ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PlanMismatch:
    """이어 도는 시도의 계획이 저장된 계획과 다르다. 쓰지 않았다(실행기가 SegmentPlanMismatch 로 올린다)."""

    stored: int  # 저장된 구획 수
    planned: int  # 이번 계획의 구획 수


def _segment_guard(company_id: int, run_id: int, step: str, key_sha256: str) -> "QuerySet[RunSegmentRow]":
    """그 구획 행 하나를 고르는 쓰기의 조건(실행의 울타리는 _fence 가 먼저 섰다)."""
    return RunSegmentRow.for_company(company_id).filter(run_id=run_id, step=step, key_sha256=key_sha256)


def segments_planned(
    *,
    company_id: int,
    run_id: int,
    attempt: int,
    step: str,
    keys: tuple[SegmentKey, ...],
    now: datetime,
    lease_s: int,
) -> Recorded | Superseded | PlanMismatch:
    """계획을 적는다. 그 단계의 구획 행이 없으면 계획 전부를 계획 차례로 pending 으로 넣는다(계획됨 0 이면 0행).
    있으면 저장된 (position, key_sha256) 목록과 견줘 같으면 0행, 다르면 PlanMismatch. 진행은 아니다.
    ★ 무효 조건: 계획됨 0 은 행이 없어 「계획 전」과 같게 보인다 — 다음 시도도 0개면 같고, 0이 아니면 새로 넣는다
      (plan 이 결정적이면 일어나지 않는다)."""
    _require_transaction("segments_planned")
    run = selectors.lock_run(company_id=company_id, run_id=run_id)
    if run is None:
        return Superseded()
    if not _fence(company_id=company_id, run_id=run_id, attempt=attempt, now=now, lease_s=lease_s, progressed=False):
        return Superseded()
    planned = [(position, segment_key_sha256(key)) for position, key in enumerate(keys)]
    stored = selectors.segment_plan(company_id=company_id, run_id=run_id, step=step)  # 두 칸만(635-2)
    if stored:
        return Recorded() if stored == planned else PlanMismatch(stored=len(stored), planned=len(planned))
    # INSERT 한 번(635-2). 행의 회사는 잠근 실행의 회사(7a 허락 — test_static_rules 의 CONSTRUCTOR_ALLOWED)
    RunSegmentRow.for_company(company_id).bulk_create(
        [
            RunSegmentRow(
                company_id=run.company_id,
                run_id=run_id,
                step=step,
                position=position,
                kind=key.kind,
                key=segment_key_fields(key),
                key_sha256=sha,
                status="pending",
            )
            for (position, sha), key in zip(planned, keys, strict=True)
        ]
    )
    return Recorded()


def segment_started(
    *, company_id: int, run_id: int, attempt: int, step: str, key_sha256: str, now: datetime, lease_s: int
) -> Recorded | Superseded:
    """구획 행을 running 으로(attempts +1, started_at 은 비었을 때만). pending·running 만 — 끝난 구획이면
    RunUpdateError. 진행은 아니다."""
    _require_transaction("segment_started")
    if not _fence(company_id=company_id, run_id=run_id, attempt=attempt, now=now, lease_s=lease_s, progressed=False):
        return Superseded()
    _one(
        _segment_guard(company_id, run_id, step, key_sha256)
        .filter(status__in=("pending", "running"))
        .update(
            status="running",
            attempts=F("attempts") + 1,
            started_at=Coalesce(F("started_at"), Value(now)),
            updated_at=now,
        ),
        "run_segments",
    )
    return Recorded()


def segment_finished(
    *,
    company_id: int,
    run_id: int,
    attempt: int,
    step: str,
    key_sha256: str,
    data: Mapping[str, object],
    now: datetime,
    lease_s: int,
) -> Recorded | Superseded:
    """구획이 끝났다: running → done·data. 진행이다(progress_attempt = 내 시도). running 이 아니면 RunUpdateError."""
    _require_transaction("segment_finished")
    if not _fence(company_id=company_id, run_id=run_id, attempt=attempt, now=now, lease_s=lease_s, progressed=True):
        return Superseded()
    _one(
        _segment_guard(company_id, run_id, step, key_sha256)
        .filter(status="running")
        # 구획 임대도 비운다(RM1b 리뷰 N1 — 쪽지가 잡았던 행을 직렬 시도가 끝내도 임대 CHECK 를 지나게. 직렬은 늘 NULL)
        .update(status="done", data=dict(data), finished_at=now, lease_expires_at=None, updated_at=now),
        "run_segments",
    )
    return Recorded()


def segment_failed(
    *,
    company_id: int,
    run_id: int,
    attempt: int,
    step: str,
    key_sha256: str,
    error_code: str,
    now: datetime,
    lease_s: int,
) -> Recorded | Superseded:
    """구획이 영구 실패로 끝났다: running → failed·error_code. 진행이다(구획 하나가 끝났다). running 이 아니면
    RunUpdateError. 잠깐 오류는 여기 오지 않는다(실행기가 행을 쓰지 않고 다시 던진다)."""
    _require_transaction("segment_failed")
    if not _fence(company_id=company_id, run_id=run_id, attempt=attempt, now=now, lease_s=lease_s, progressed=True):
        return Superseded()
    _one(
        _segment_guard(company_id, run_id, step, key_sha256)
        .filter(status="running")
        .update(
            status="failed",
            error_code=error_code[:MAX_ERROR_CODE_CHARS],
            finished_at=now,
            lease_expires_at=None,  # 리뷰 N1(위와 같음)
            updated_at=now,
        ),
        "run_segments",
    )
    return Recorded()


def _create_files(*, company_id: int, run_id: int, step: str | None, files: tuple[StoredFile, ...]) -> None:
    for file in files:
        RunFileRow.for_company(company_id).create(
            company_id=company_id,
            run_id=run_id,
            step=step,
            name=file.name,
            media_type=file.media_type,
            storage_key=file.storage_key,
            size_bytes=file.size_bytes,
            sha256=file.sha256,
        )


# ── 끝내기 ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RunDone:
    results: tuple[dict[str, object], ...]  # 흐름이 낸 차례. 각각 첫 키가 schemaVersion
    files: tuple[StoredFile, ...]  # 흐름의 출력 파일(저장소에 이미 썼다)


@dataclass(frozen=True, slots=True)
class RunFailed:
    step: str | None  # 단계에서 실패했을 때만. 실행기의 실패는 None
    code: str
    message: str  # 사람에게 보일 고정 글(예외의 원문이 아니다)


@dataclass(frozen=True, slots=True)
class RunDeferred:
    """이 시도를 접고 실행을 다시 넣는다(협조 마감·소프트 제한·잠깐 오류). 진행은 행의 progress_attempt 로 읽는다."""


RunOutcome = RunDone | RunFailed | RunDeferred


@dataclass(frozen=True, slots=True)
class RunParkedOutcome:
    """지휘 시도가 펼침 구획을 쪽지에 맡기고 주차한다(RM1b): parked_at = now·실행 임대 당김. status processing 그대로,
    stalled 0, 다시 넣기 없음. 깨우는 것은 구획 쪽지의 블록이다."""

    lease_s: int


@dataclass(frozen=True, slots=True)
class Finished:
    status: str  # 쓴 상태: done·failed·queued


def _too_large(body: object) -> bool:
    """jsonb 를 글로 적은 크기의 어림(json 의 기본 구분자 — PostgreSQL 이 jsonb 를 적는 꼴과 같다)."""
    return len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > RUN_RESULT_BODY_MAX_OCTETS


def _failed_values(*, step: str | None, code: str, message: str, now: datetime) -> dict[str, object]:
    return {
        "status": "failed",
        "failed_step": step,
        "error_code": code[:MAX_ERROR_CODE_CHARS],
        "error_message": message[:MAX_ERROR_MESSAGE_CHARS],
        "finished_at": now,
        "lease_expires_at": None,
        "parked_at": None,
        "updated_at": now,
    }


def finish_run(
    *, company_id: int, run_id: int, attempt: int, now: datetime, outcome: RunOutcome | RunParkedOutcome
) -> Finished | Superseded:
    """내가 잡은 시도(attempt)의 끝을 적는다. 조건은 「processing 이고 attempts 가 내 시도」다.

    RunDone      결과 행·출력 파일 행과 실행 done 을 한 블록에서. 결과 하나라도 크기 상한을 넘으면
                 failed·result_too_large
    RunFailed    실행 failed(+ step 이 있으면 그 단계 행 failed — 같은 블록)
    RunDeferred  실행 queued·임대 비움. 행의 progress_attempt 가 내 시도가 아니면 stalled_attempts +1
    RunParkedOutcome  주차(RM1b): parked_at = now·실행 임대 당김(status processing 그대로 — Finished("processing"))
    done·failed·queued 는 parked_at 도 비운다.
    """
    _require_transaction("finish_run")
    guard = RunRow.for_company(company_id).filter(pk=run_id, status="processing", attempts=attempt)
    if isinstance(outcome, RunDone) and any(_too_large(body) for body in outcome.results):
        code = "result_too_large"
        outcome = RunFailed(step=None, code=code, message=RUN_ERROR_MESSAGES[code])

    if isinstance(outcome, RunParkedOutcome):
        updated = guard.update(parked_at=now, lease_expires_at=lease_until(now, outcome.lease_s), updated_at=now)
        status = "processing"
    elif isinstance(outcome, RunDone):
        updated = guard.update(
            status="done",
            finished_at=now,
            lease_expires_at=None,
            parked_at=None,
            error_code=None,
            error_message=None,
            updated_at=now,
        )
        status = "done"
    elif isinstance(outcome, RunFailed):
        updated = guard.update(**_failed_values(step=outcome.step, code=outcome.code, message=outcome.message, now=now))
        status = "failed"
    else:
        updated = guard.update(
            status="queued",
            stalled_attempts=Case(
                When(progress_attempt=attempt, then=F("stalled_attempts")), default=F("stalled_attempts") + 1
            ),
            lease_expires_at=None,
            parked_at=None,
            updated_at=now,
        )
        status = "queued"
    if updated == 0:
        return Superseded()
    _one(updated, "run_runs")

    if isinstance(outcome, RunDone):
        for position, body in enumerate(outcome.results):
            RunResultRow.for_company(company_id).create(
                company_id=company_id,
                run_id=run_id,
                position=position,
                schema_version=str(body["schemaVersion"]),
                body=body,
            )
        _create_files(company_id=company_id, run_id=run_id, step=None, files=outcome.files)
    elif isinstance(outcome, RunFailed) and outcome.step is not None:
        _one(
            _step_guard(company_id, run_id, outcome.step).update(status="failed", finished_at=now, updated_at=now),
            "run_steps",
        )
    return Finished(status)


# ── 구획 쪽지(RM1b) ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SegmentClaimed:
    """구획 하나를 잡았다(running·attempts +1·구획 임대). attempt = 그 구획의 새 시도 번호(끝냄의 울타리)."""

    step: str
    position: int
    key_sha256: str
    attempt: int
    wake: bool = False


@dataclass(frozen=True, slots=True)
class NothingToClaim:
    """잡을 것이 없다(상한이 찼다·남은 것 없음·fail_run 이 이미 실패).
    wake 면 이 블록이 지휘를 깨웠다(소진 끝냄 — B1a). delay 면 그 초 뒤 구획 쪽지 하나(RM1c ③′ M1 — 남은 것이 전부
    임대 산 running)."""

    wake: bool
    delay: int | None = None


@dataclass(frozen=True, slots=True)
class EndDone:
    data: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class EndFailed:
    """영구 실패(그 구획만 — 표의 code)."""

    code: str


@dataclass(frozen=True, slots=True)
class EndFatal:
    """실행 전체가 성립하지 않는다: 구획 failed + 실행 failed(+ step 이 있으면 그 단계 행 failed). 깨우지 않는다."""

    code: str
    step: str | None


@dataclass(frozen=True, slots=True)
class EndReleased:
    """놓는다: running 그대로·구획 임대 비움. 진행 아님(구획 시도는 이미 셌다 — 셋째 뒤 잡기가 소진으로 끝낸다)."""


SegmentEndOutcome = EndDone | EndFailed | EndFatal | EndReleased


@dataclass(frozen=True, slots=True)
class Ended:
    """끝냄을 적었다. wake = 지휘를 깨웠다(부른 쪽이 커밋 뒤 enqueue_run) ·
    successor = 쪽지 하나 더(enqueue_segment)."""

    wake: bool
    successor: bool
    delay: int | None = None  # 이어 넣기 0 이고 남은 것이 전부 임대 산 running — 그 초 뒤 쪽지 하나(RM1c ③′ M1)


def _parked(*, company_id: int, run_id: int, run_attempt: int) -> RunRow | None:
    """블록의 첫 문: 실행 행을 FOR UPDATE 로 잠그고,
    「processing · attempts = run_attempt · parked_at 있음」이면 그 행."""
    row = selectors.lock_run(company_id=company_id, run_id=run_id)
    if row is None or row.status != "processing" or row.attempts != run_attempt or row.parked_at is None:
        return None
    return row


def _parked_step(counts: Mapping[str, SegmentCounts]) -> str | None:
    """끝나지 않은 구획이 남은 펼침 단계(주차한 단계). 없으면 None.
    둘 이상이면 RunUpdateError(지휘는 한 단계에서 주차)."""
    steps = sorted(step for step, count in counts.items() if count.unended > 0)
    if len(steps) > 1:
        raise RunUpdateError(f"끝나지 않은 구획이 단계 {len(steps)}개에 있다(주차는 한 단계)")
    return steps[0] if steps else None


def _wake(*, company_id: int, run_id: int, run_attempt: int, now: datetime) -> None:
    """지휘를 깨운다: parked_at·실행 임대를 비우고 progress_attempt = 그 시도(잡기 Take 가 stalled 를 세지 않는다)."""
    _one(
        RunRow.for_company(company_id)
        .filter(pk=run_id, status="processing", attempts=run_attempt)
        .update(parked_at=None, lease_expires_at=None, progress_attempt=run_attempt, updated_at=now),
        "run_runs",
    )


def segment_claim(
    *,
    company_id: int,
    run_id: int,
    run_attempt: int,
    now: datetime,
    lease_s: int,
    parallel_max: int,
    max_attempts: int,
    on_failure: Mapping[str, str],
) -> SegmentClaimed | NothingToClaim | Superseded:
    """구획 하나를 잡는다(쪽지의 T1). on_failure = 펼침 단계 → 그 정책(흐름의 선언 — 모르면 pass_to_gather).

    ① 첫 문 lock_run, 주차한 시도가 아니면 Superseded ② fail_run 이고 그 단계 failed ≥1 → 안 잡음 ③ claim_plan(상한 ·
    소진 · 계획 차례 첫 잡을 것) ④ 소진은 failed·attempts_exhausted(진행 — Q0-2)로 끝내고 깨우기 판정 ⑤ 잡으면
    running·attempts+1·구획 임대, 실행 임대 당김."""
    _require_transaction("segment_claim")
    row = selectors.lock_run(company_id=company_id, run_id=run_id)
    if row is None or row.status != "processing" or row.attempts != run_attempt:
        return Superseded()
    if row.parked_at is None:
        # RM1c ③′ M2: 깨웠는데(parked_at·임대 NULL) 실행 임대 한 번(lease_s)이 지나도 지휘가 잡지 않았다 — 깨우기 쪽지를
        # 잃었다고 보고 다시 넣는다(_wake 뒤 실행 행을 쓰는 것은 지휘의 잡기뿐이라 updated_at = 깨운 때)
        return Superseded(wake=row.lease_expires_at is None and row.updated_at <= now - timedelta(seconds=lease_s))
    counts = selectors.segment_counts(company_id=company_id, run_id=run_id)
    step = _parked_step(counts)
    if step is None:  # 끝나지 않은 것이 없는데 주차 중이다 — 깨운다(앞 블록이 깨우지 못한 꼴의 방어)
        _wake(company_id=company_id, run_id=run_id, run_attempt=run_attempt, now=now)
        return NothingToClaim(wake=True)
    # .get 은 쓰지 않는다 — core/tests/test_selector_scope.py 가 Service 의 .get 을 읽기로 센다
    policy = on_failure[step] if step in on_failure else "pass_to_gather"  # noqa: SIM401
    count = counts[step]
    if policy == "fail_run" and count.failed > 0:
        return NothingToClaim(wake=False)
    plan = claim_plan(
        selectors.running_segments(company_id=company_id, run_id=run_id, step=step),
        selectors.first_pending(company_id=company_id, run_id=run_id, step=step),
        now=now,
        parallel_max=parallel_max,
        max_attempts=max_attempts,
    )
    if plan.full:
        return NothingToClaim(wake=False)
    code = "attempts_exhausted"
    for head in plan.exhaust:
        _one(
            _segment_guard(company_id, run_id, step, head.key_sha256)
            .filter(status="running", attempts=head.attempts)
            .update(status="failed", error_code=code, finished_at=now, lease_expires_at=None, updated_at=now),
            "run_segments",
        )
    if not _fence(
        company_id=company_id,
        run_id=run_id,
        attempt=run_attempt,
        now=now,
        lease_s=lease_s,
        progressed=bool(plan.exhaust),
    ):
        raise RunUpdateError("잠근 실행의 울타리가 0행이다")
    if plan.exhaust:
        exhausted = len(plan.exhaust)
        after = SegmentCounts(
            pending=count.pending,
            running=count.running - exhausted,
            done=count.done,
            failed=count.failed + exhausted,
            first_started_at=count.first_started_at,
            last_finished_at=now,
        )
        if wake_due(policy, after, exhausted):
            _wake(company_id=company_id, run_id=run_id, run_attempt=run_attempt, now=now)
            return NothingToClaim(wake=True)
        if policy == "fail_run":  # 앞에 실패가 없었다면 위에서 깼다 — 방어
            return NothingToClaim(wake=False)
    take = plan.take
    if take is None:
        unended = count.unended - len(plan.exhaust)
        return NothingToClaim(
            wake=False,
            delay=_delay(
                company_id=company_id,
                run_id=run_id,
                step=step,
                now=now,
                unended=unended,
                alive=plan.alive,
                cap=parallel_max,
            ),
        )
    _one(
        _segment_guard(company_id, run_id, step, take.key_sha256)
        .filter(status=take.status, attempts=take.attempts)
        .update(
            status="running",
            attempts=F("attempts") + 1,
            started_at=Coalesce(F("started_at"), Value(now)),
            lease_expires_at=lease_until(now, lease_s),
            updated_at=now,
        ),
        "run_segments",
    )
    return SegmentClaimed(step=step, position=take.position, key_sha256=take.key_sha256, attempt=take.attempts + 1)


def segment_end(
    *,
    company_id: int,
    run_id: int,
    run_attempt: int,
    step: str,
    key_sha256: str,
    attempt: int,
    outcome: SegmentEndOutcome,
    now: datetime,
    lease_s: int,
    parallel_max: int,
    on_failure: str,
) -> Ended | Superseded:
    """구획 하나의 끝을 적는다(쪽지의 T2). attempt = 잡기가 준 그 구획의 시도 번호.

    ① 첫 문 lock_run, 주차한 시도가 아니면 Superseded ② 구획 행의 attempts ≠ attempt 면 Superseded(이어받긴 구획의 옛
    쪽지 — 행 그대로), 같은데 running 이 아니면 RunUpdateError(같은 시도의 두 번 끝냄) ③ outcome 대로 쓰고(Done 은
    data_octets — 단계 합이 FANOUT_DATA_MAX_OCTETS 를 넘으면 Fatal(step_output_invalid, 그 단계)) ④ Done·Failed 뒤
    깨우기 판정, 아니면 이어 넣기 판정."""
    _require_transaction("segment_end")
    if _parked(company_id=company_id, run_id=run_id, run_attempt=run_attempt) is None:
        return Superseded()
    head = selectors.segment_head(company_id=company_id, run_id=run_id, step=step, key_sha256=key_sha256)
    if head is None:
        raise RunUpdateError(f"run_segments 에 그 구획의 행이 없다(단계 {step})")
    if head.attempts != attempt:
        return Superseded()
    if head.status != "running":
        raise SegmentAlreadyEnded(step=step, position=head.position, attempt=attempt, status=head.status)
    segment = _segment_guard(company_id, run_id, step, key_sha256).filter(status="running", attempts=attempt)

    if isinstance(outcome, EndReleased):
        _one(segment.update(lease_expires_at=None, updated_at=now), "run_segments")
        if not _fence(
            company_id=company_id, run_id=run_id, attempt=run_attempt, now=now, lease_s=lease_s, progressed=False
        ):
            raise RunUpdateError("잠근 실행의 울타리가 0행이다")
        return _ended(
            company_id=company_id, run_id=run_id, step=step, now=now, wake=False, policy=on_failure, cap=parallel_max
        )

    if isinstance(outcome, EndDone):
        octets = data_octets(outcome.data)
        if selectors.done_octets(company_id=company_id, run_id=run_id, step=step) + octets > FANOUT_DATA_MAX_OCTETS:
            outcome = EndFatal(code="step_output_invalid", step=step)
        else:
            _one(
                segment.update(
                    status="done",
                    data=dict(outcome.data),
                    data_octets=octets,
                    finished_at=now,
                    lease_expires_at=None,
                    updated_at=now,
                ),
                "run_segments",
            )

    if isinstance(outcome, EndFatal):
        _one(
            segment.update(
                status="failed",
                error_code=outcome.code[:MAX_ERROR_CODE_CHARS],
                finished_at=now,
                lease_expires_at=None,
                updated_at=now,
            ),
            "run_segments",
        )
        values = _failed_values(step=outcome.step, code=outcome.code, message=RUN_ERROR_MESSAGES[outcome.code], now=now)
        _one(
            RunRow.for_company(company_id)
            .filter(pk=run_id, status="processing", attempts=run_attempt)
            .update(**values),
            "run_runs",
        )
        if outcome.step is not None:
            _one(
                _step_guard(company_id, run_id, outcome.step).update(status="failed", finished_at=now, updated_at=now),
                "run_steps",
            )
        return Ended(wake=False, successor=False)

    newly_failed = 0
    if isinstance(outcome, EndFailed):
        _one(
            segment.update(
                status="failed",
                error_code=outcome.code[:MAX_ERROR_CODE_CHARS],
                finished_at=now,
                lease_expires_at=None,
                updated_at=now,
            ),
            "run_segments",
        )
        newly_failed = 1
    if not _fence(company_id=company_id, run_id=run_id, attempt=run_attempt, now=now, lease_s=lease_s, progressed=True):
        raise RunUpdateError("잠근 실행의 울타리가 0행이다")
    found = selectors.segment_counts(company_id=company_id, run_id=run_id)
    if step not in found:
        raise RunUpdateError(f"방금 쓴 단계 {step} 의 구획 셈이 없다")
    counts = found[step]
    if wake_due(on_failure, counts, newly_failed):
        _wake(company_id=company_id, run_id=run_id, run_attempt=run_attempt, now=now)
        return Ended(wake=True, successor=False)
    return _ended(
        company_id=company_id,
        run_id=run_id,
        step=step,
        now=now,
        wake=False,
        policy=on_failure,
        cap=parallel_max,
        counts=counts,
    )


def _ended(
    *,
    company_id: int,
    run_id: int,
    step: str,
    now: datetime,
    wake: bool,
    policy: str,
    cap: int,
    counts: SegmentCounts | None = None,
) -> Ended:
    """깨우지 않은 끝냄의 이어 넣기 판정(runs/calc/segments.successor_due)."""
    if counts is None:
        found = selectors.segment_counts(company_id=company_id, run_id=run_id)
        if step not in found:
            raise RunUpdateError(f"단계 {step} 의 구획 셈이 없다")
        counts = found[step]
    alive = selectors.alive_segments(company_id=company_id, run_id=run_id, step=step, now=now)
    successor = successor_due(on_failure=policy, counts=counts, alive=alive, parallel_max=cap)
    delay = (
        None
        if successor
        else _delay(
            company_id=company_id, run_id=run_id, step=step, now=now, unended=counts.unended, alive=alive, cap=cap
        )
    )
    return Ended(wake=wake, successor=successor, delay=delay)


def _delay(*, company_id: int, run_id: int, step: str, now: datetime, unended: int, alive: int, cap: int) -> int | None:
    """미룬 쪽지의 초(RM1c ③′ M1 — runs/calc/segments.delayed_due). 그때가 아니면 None."""
    if not delayed_due(unended=unended, alive=alive, parallel_max=cap):
        return None
    earliest = selectors.earliest_lease(company_id=company_id, run_id=run_id, step=step, now=now)
    return None if earliest is None else delay_after(earliest, now)
