"""운영 관리자 실행 기록(AD-04 — AU1b-2)의 지표 다섯과 처리 시간의 셈. 순수하다(`.importlinter` 계약 다의
`esgapi.*.calc` — django·runs·core.service 를 모른다).

    MetricRun     지표가 보는 실행 하나(경로가 runs 의 무리를 이 꼴로 옮겨 담는다)
    RunUsage      실행 하나에 붙은 LLM 줄의 합(NULL 은 0 으로 채운 값 — core 의 selector llm_usage 가 낸다)
    month_bounds  「이번 달」: 서버 시계의 KST 그달 1일 00:00 ~ 다음 달 1일 00:00(처분 ⑤ ㉠)
    duration_sec  처리 시간 = finished_at − created_at(큐 대기 포함 — MARC-ENT-327), 초 버림. 끝나지 않았으면 None
    metrics       그달에 만든 실행 무리 → 지표 다섯(처분 ⑤ ㉡~㉧)

셈 규칙(처분 ⑤ — 감독 처분, ㉢ 은 사용자 결정 MARC-ENT-327):
  ㉡ 실행 수     무리 가운데 purpose='service' 의 수(상태 무관)
  ㉢㉣ 평균      service 이고 status='done' 인 실행의 정수 durationSec 들의 평균을 반올림(절반 위로). done 0 이면 None
  ㉤ 토큰       input + cache_read + cache_write + output(thinking 은 output 에 이미 든 몫이라 더하지 않는다)
  ㉥ 범위       service 실행의 id 에 해당하는 usage 만 더한다(테스트 실행의 LLM 합도 빠진다). 비용은 cost_usd 의 합
  ㉦ 실패율     service 가운데 끝난 것의 failed / (done + failed). 분모 0 이면 None
  ㉧ 테스트     purpose 는 여기 한 자리에서만 거른다(무리를 읽는 selector 는 거르지 않는다)
무효 조건: 이어서 재실행(resumed_from_run_id — X1b-2)이 오면 실패한 앞 실행과 이어 돈 새 실행이 같은 무리에 둘 다
든다 — 처리 시간·실패율을 사슬로 셀지 다시 묻는다. 비용은 web_search 건당 요금도 품어 토큰과 바탕이 「거의」 같다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

KST: Final = timezone(timedelta(hours=9))
SECOND: Final = timedelta(seconds=1)


@dataclass(frozen=True, slots=True)
class MetricRun:
    id: int  # usage 의 열쇠와 잇는 칸(테스트 실행의 LLM 합을 뺄 때 쓴다)
    status: str
    purpose: str
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class RunUsage:
    input: int
    cache_read: int
    cache_write: int
    output: int
    cost_usd: Decimal

    @property
    def tokens(self) -> int:
        """청구 토큰(㉤): 캐시에 걸리지 않은 입력 + 캐시 읽기 + 캐시 쓰기 + 출력."""
        return self.input + self.cache_read + self.cache_write + self.output


@dataclass(frozen=True, slots=True)
class RunMetrics:
    runs: int
    average_duration_sec: int | None
    tokens: int
    cost_usd: Decimal
    failure_rate: float | None


def month_bounds(now: datetime) -> tuple[datetime, datetime, str]:
    """now 가 든 KST 의 달: (그달 1일 00:00 KST, 다음 달 1일 00:00 KST, "YYYY-MM"). 끝은 포함하지 않는다."""
    local = now.astimezone(KST)
    start = datetime(local.year, local.month, 1, tzinfo=KST)
    end = datetime(local.year + 1, 1, 1, tzinfo=KST) if local.month == 12 else start.replace(month=local.month + 1)
    return start, end, f"{local.year:04d}-{local.month:02d}"


def duration_sec(created_at: datetime, finished_at: datetime | None) -> int | None:
    """처리 시간(초, 버림). 큐 대기를 품는다(MARC-ENT-327). 끝나지 않았으면 None."""
    if finished_at is None:
        return None
    return (finished_at - created_at) // SECOND


def _rounded_mean(values: Sequence[int]) -> int | None:
    if not values:
        return None
    return int((Decimal(sum(values)) / Decimal(len(values))).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def metrics(runs: Sequence[MetricRun], usage: Mapping[int, RunUsage]) -> RunMetrics:
    """그달에 만든 실행 무리와 실행별 LLM 합으로 지표 다섯(위 셈 규칙)."""
    service = [run for run in runs if run.purpose == "service"]
    durations = [
        took
        for run in service
        if run.status == "done" and (took := duration_sec(run.created_at, run.finished_at)) is not None
    ]
    used = [usage[run.id] for run in service if run.id in usage]
    done = sum(1 for run in service if run.status == "done")
    failed = sum(1 for run in service if run.status == "failed")
    return RunMetrics(
        runs=len(service),
        average_duration_sec=_rounded_mean(durations),
        tokens=sum(u.tokens for u in used),
        cost_usd=sum((u.cost_usd for u in used), Decimal(0)),
        failure_rate=None if done + failed == 0 else failed / (done + failed),
    )
