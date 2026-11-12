"""실행(표 run_runs)을 워커가 잡는 순수 규칙: 잡아도 되는가, 그리고 시도 상한의 셈.

갈래는 일감의 것(core/calc/jobs.py 의 claim_decision)과 같은 이름·타입이다 — Take·AlreadyFinished·LeaseHeld·Exhausted.
다른 것은 상한이 세는 수 하나다: 일감은 잡은 횟수(attempts)를, 실행은 **진행 없이 끝난 시도 수**(stalled_attempts)를
센다. 진행 = 단계 안 체크포인트의 done 이 저장된 값보다 커졌거나 단계가 끝났다(progress_attempt 에 그 시도 번호).
그래서 진행이 있는 한 시도는 몇 번이고 이어진다(쪽 수가 유한하므로 끝난다).

      queued                      잡는다. 셈 그대로(앞 시도는 끝내기 RunDeferred 가 이미 셌다)
      processing · 임대가 지났다   앞 시도가 끝내기 없이 죽었다. 그 시도(= 지금의 attempts, 늘리기 **앞**)가
                                  진행을 남기지 않았으면(progress_attempt ≠ attempts) 셈 +1. 그 뒤 잡는다
      processing · 임대가 남았다   안 잡는다(LeaseHeld)
      done · failed               안 잡는다(AlreadyFinished)
      셈이 상한에 닿았다           안 잡는다(Exhausted). 부른 쪽이 failed·attempts_exhausted 로 끝낸다

★ 늘린 뒤의 attempts 와 견주면 늘 달라 진행 있던 시도도 센다(발주서 개정 5 F1 — P20 이 문다).
"""

from dataclasses import dataclass
from datetime import datetime

from esgapi.core.calc.jobs import AlreadyFinished, ClaimDecision, Exhausted, LeaseHeld, Take


@dataclass(frozen=True, slots=True)
class RunClaim:
    """판정과, 그 판정 뒤 행에 적을 stalled_attempts(Take·Exhausted 일 때 쓴다)."""

    decision: ClaimDecision
    stalled_attempts: int


def run_claim(
    *,
    status: str,
    lease_expires_at: datetime | None,
    attempts: int,
    stalled_attempts: int,
    progress_attempt: int | None,
    now: datetime,
    max_attempts: int,
) -> RunClaim:
    if status == "done" or status == "failed":
        return RunClaim(AlreadyFinished(), stalled_attempts)
    if status == "processing" and lease_expires_at is not None and lease_expires_at > now:
        return RunClaim(LeaseHeld(lease_expires_at), stalled_attempts)
    stalled = stalled_attempts
    if status == "processing" and progress_attempt != attempts:  # 늘리기 앞의 attempts = 죽은 시도의 번호
        stalled += 1
    if stalled >= max_attempts:
        return RunClaim(Exhausted(), stalled)
    return RunClaim(Take(attempts + 1), stalled)
