"""같은 모델을 다시 부르는 재시도의 설정과 대기 계산. 재시도 가능한 공급사 오류(`ProviderError.retryable`)에만 쓴다.
채팅(client.py)과 임베딩(embedding.py)이 이 파일의 `next_retry` 하나로 대기를 정한다(두 번째 정본 없음 — LB1).

갈래 둘(LB1 — MARC-ISSUE-672 안 A 의 2):
  예산 갈래  이름이 한도 초과·과부하(`WAIT_BUDGET_KINDS`)이고 과금됐을 수 있는 실패가 아닌 것(HTTP 상태로 거절된
             429·529·503 과부하). 횟수가 아니라 대기 예산(`wait_budget_ms`, 한 호출 — 채팅은 `call` 하나·`call_tools`
             고리 한 번에서 모델·걸음을 넘어 합산, 임베딩은 묶음 하나)과 천장(`max_budget_retries`, 한 모델 연속).
             공급사 대기(`retry_after_ms`)가 있으면 그것, 없으면 두 배 물러섬. 이번 대기가 남은 예산을 넘으면
             기다리지 않고 그 자리에서 실패 값으로(retry_after_ms 실음 → 다음 모델이나 실행 층).
  횟수 갈래  그 밖 재시도 가능(server_error·connection·과금됐을 수 있는 실패 — 스트림 중 과부하 200·상태 없는 오류).
             `max_retries`·두 배·상한 `max_delay_ms` 그대로(BASE). `max_retries` 의 뜻은 「과금됐을 수 있는 시도 수」
             라 영문번역의 머리 여유(translation/tools/run_bound.guard_factor)가 기댄다 — 예산 갈래를 여기 섞지 않는다.
  크레딧 소진(quota_exhausted)은 retryable=False 라 같은 모델 재시도 0(다음 모델로 — client._should_fallback).
지터(Q3 (가)): 0~1 균등 j 를 주입받아(기본 random.random) 공급사 대기는 × (1 + PROVIDER_WAIT_JITTER·j) — 그 값 아래로
  내리지 않는다, 물러섬은 × (1 − BACKOFF_JITTER·j). j = 0 이면 흩뜨림 없음(BASE 값 그대로).
★ 무효 조건(값): 예산 30초·천장 8·지터 폭은 어림(안 13 §8) — 실측(탐침 MARC-ENT-665)으로 다시. 예산 + 경로 모델 수 ×
  (1 + max_retries + max_budget_retries) × timeout 이 Celery soft 240초를 넘으면 실행 층(안 B)이 받기 전까지 soft limit
  이 먼저 끊는다(client.py 머리의 「한 호출의 벽시계 최악」). 공급사 대기가 예산을 넘는 429(예: gemini 무료 등급
  retryDelay 55초)는 BASE 에서는 기다렸지만 이제 기다리지 않고 다음 모델·실패로 가며 retry_after_ms 를 싣는다 — 긴
  대기는 실행 층(안 B)이 받는다. gemini 를 주 모델로 쓰게 되면 이 값을 다시 정한다(LB1 감독 처분 11-11).
"""

import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from math import ceil, isfinite
from typing import Literal

from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.types import ProviderError

# 예산 갈래의 값(어림 — 위 무효 조건). 이름은 LB1 발주서 Q2.
RATE_LIMIT_WAIT_BUDGET_MS = 30_000
RATE_LIMIT_MAX_RETRIES = 8
# 예산 갈래에 드는 이름(types.ErrorKind).
WAIT_BUDGET_KINDS: frozenset[str] = frozenset({"rate_limited", "overloaded"})
# 지터 폭(Q3 (가)).
PROVIDER_WAIT_JITTER = 0.2
BACKOFF_JITTER = 0.5


@dataclass(frozen=True)
class RetryPolicy:
    """max_retries: 횟수 갈래에서 첫 호출 뒤에 다시 부르는 최대 횟수(0 이면 다시 부르지 않는다).
    base_delay_ms: 첫 재시도 전의 대기. 그 뒤로 두 배씩 늘어난다(두 갈래 같다).
    max_delay_ms: 대기의 상한. 횟수 갈래에서 공급사가 이보다 긴 대기를 요구하면 다시 부르지 않는다.
    wait_budget_ms: 예산 갈래의 대기 합 상한(한 호출 — 머리말). 0 이면 예산 갈래도 다시 부르지 않는다.
    max_budget_retries: 예산 갈래에서 한 모델을 잇달아 다시 부르는 천장(아주 짧은 대기가 이어질 때 무한히 돌지 않게).
    """

    max_retries: int
    base_delay_ms: float
    max_delay_ms: float
    wait_budget_ms: float = RATE_LIMIT_WAIT_BUDGET_MS
    max_budget_retries: int = RATE_LIMIT_MAX_RETRIES


# 공급사 이름 → 호출 층의 재시도 설정. 여기에 없는 공급사는 호출 층에서 다시 부르지 않는다.
# 값(2회, 1초부터 두 배, 상한 60초)은 esg-lab 의 것을 그대로 옮겼다. 상한 60초는 무료 등급의 분당 한도 429 가 요구한
# 대기(esg-lab 이 2026-10-02 에 받은 실제 응답의 `retryDelay: "55s"`)를 따를 수 있는 값이다.
# - gemini: SDK(google-genai)는 `retry_options` 를 주지 않으면 한 번만 부른다(2.28.0 의 _api_client:
#   stop_after_attempt(1)).
# - openai, anthropic: SDK 의 자체 재시도를 끄고(`max_retries=0` — providers/openai.py·anthropic.py, LH1 Q1) 여기서
#   다시 부른다. 그래야 공급사로 나간 HTTP 요청이 전부 상한 확인과 기록 한 줄을 지난다(MARC-ENT-262). 횟수 2 는 끄기 전
#   SDK 기본값(openai 3.26.0·anthropic 1.11.0 의 `max_retries` 2)과 같다.
DEFAULT_PROVIDER_RETRY: Mapping[str, RetryPolicy] = {
    "gemini": RetryPolicy(max_retries=2, base_delay_ms=1_000, max_delay_ms=60_000),
    "openai": RetryPolicy(max_retries=2, base_delay_ms=1_000, max_delay_ms=60_000),
    "anthropic": RetryPolicy(max_retries=2, base_delay_ms=1_000, max_delay_ms=60_000),
}

# provider_retry 에 없는 공급사: 두 갈래 다 다시 부르지 않는다(감독 답 2 B2 — `provider_retry={}` 는 재시도 0).
NO_RETRY = RetryPolicy(max_retries=0, base_delay_ms=0, max_delay_ms=0, wait_budget_ms=0, max_budget_retries=0)


def validate_retry_policies(policies: Mapping[str, RetryPolicy]) -> None:
    for provider, policy in policies.items():
        if policy.max_retries < 0:
            raise LlmConfigError(f"공급사 {provider} 의 max_retries 는 0 이상의 정수여야 한다: {policy.max_retries}")
        if not policy.base_delay_ms >= 0 or not policy.max_delay_ms >= policy.base_delay_ms:
            raise LlmConfigError(
                f"공급사 {provider} 의 재시도 대기는 0 ≤ base_delay_ms ≤ max_delay_ms 여야 한다: "
                f"{policy.base_delay_ms}, {policy.max_delay_ms}"
            )
        if not policy.wait_budget_ms >= 0 or policy.max_budget_retries < 0:
            raise LlmConfigError(
                f"공급사 {provider} 의 대기 예산·천장은 0 이상이어야 한다: "
                f"{policy.wait_budget_ms}, {policy.max_budget_retries}"
            )


def retry_delay_ms(policy: RetryPolicy, retry_index: int, retry_after_ms: float | None) -> float | None:
    """`retry_index` 번째(0부터) 재시도 전에 기다릴 시간(ms). 다시 부르지 않아야 하면 None.

    공급사가 대기 시간을 알려 줬으면(`retry_after_ms`) 그 값을 따르고, 그 값이 상한을 넘으면 다시 부르지 않는다.
    알려 주지 않았으면 `base_delay_ms × 2^retry_index` 를 상한에서 자른다. 흩뜨리기 전의 값이다(횟수 갈래 — 지터는
    `next_retry` 가 얹는다).
    """
    if retry_index >= policy.max_retries:
        return None
    if retry_after_ms is not None:
        return None if retry_after_ms > policy.max_delay_ms else retry_after_ms
    return min(policy.base_delay_ms * 2**retry_index, policy.max_delay_ms)


type RetryBranch = Literal["budget", "count"]


@dataclass(frozen=True)
class RetryDecision:
    """다시 부르기 전에 기다릴 시간(ms — 지터 얹은 값)과 갈래."""

    wait_ms: float
    branch: RetryBranch


def in_wait_budget(error: ProviderError, *, maybe_billed: bool) -> bool:
    """예산 갈래인가: 이름이 한도 초과·과부하이고 과금됐을 수 있는 실패가 아니다(머리말)."""
    return error.error_kind in WAIT_BUDGET_KINDS and not maybe_billed


def next_retry(
    policy: RetryPolicy,
    error: ProviderError,
    *,
    maybe_billed: bool,
    count_done: int,
    budget_done: int,
    waited_ms: float,
    jitter: Callable[[], float],
) -> RetryDecision | None:
    """같은 모델을 다시 부를지와 그 전의 대기. 다시 부르지 않으면 None.

    count_done·budget_done  이 모델에서 이미 한 횟수·예산 갈래 재시도 수
    waited_ms               이 호출(머리말의 단위)에서 예산 갈래로 이미 기다린 합
    jitter                  0~1 을 내는 함수(범위 밖이면 잘라 쓴다)
    """
    if not error.retryable:
        return None
    spread = min(1.0, max(0.0, jitter()))
    # 두 배 물러섬의 차례는 이 모델의 재시도 전체(두 갈래 합 — BASE 의 retry_index 와 같은 뜻).
    backoff = min(policy.base_delay_ms * 2 ** (count_done + budget_done), policy.max_delay_ms)
    if in_wait_budget(error, maybe_billed=maybe_billed):
        if budget_done >= policy.max_budget_retries:
            return None
        if error.retry_after_ms is not None:
            wait = error.retry_after_ms * (1 + PROVIDER_WAIT_JITTER * spread)
        else:
            wait = backoff * (1 - BACKOFF_JITTER * spread)
        if waited_ms + wait > policy.wait_budget_ms:
            return None
        return RetryDecision(wait_ms=wait, branch="budget")
    if count_done >= policy.max_retries:
        return None
    if error.retry_after_ms is not None:
        if error.retry_after_ms > policy.max_delay_ms:
            return None
        return RetryDecision(wait_ms=error.retry_after_ms * (1 + PROVIDER_WAIT_JITTER * spread), branch="count")
    return RetryDecision(wait_ms=backoff * (1 - BACKOFF_JITTER * spread), branch="count")


def default_jitter() -> float:
    """0~1 균등(표준 라이브러리 random — 새 의존 0). 시험은 고정 값을 주입한다."""
    return random.random()  # noqa: S311 — 재시도 대기의 흩뜨림이다(보안 용도 아님)


def _now_ms() -> float:
    return time.time() * 1000


def retry_after_ms_from_headers(headers: Mapping[str, str], *, now_ms: float | None = None) -> int | None:
    """공급사 응답 머리의 대기 요구(ms — 기록 칸이 정수라 올림). `retry-after-ms`(수, ms)가 먼저, 없으면
    `retry-after` — 초(수) × 1000, 또는 HTTP 날짜(RFC 9110 의 IMF-fixdate 등 — `email.utils.parsedate_to_datetime`)면
    그 시각까지 남은 ms(`now_ms` 기준, 주지 않으면 지금 시계. 지난 날짜는 0). 읽을 수 없거나 음수·무한이면
    None(호출 층의 기본 대기).

    `x-should-retry` 머리는 의도적으로 따르지 않는다: 다시 부를지는 어댑터의 `retryable` 규칙(429·5xx·연결 실패) 하나로
    정한다.
    """
    for name, scale in (("retry-after-ms", 1.0), ("retry-after", 1_000.0)):
        value = headers.get(name)
        if value is None:
            continue
        try:
            number = float(value)
        except ValueError:
            if name == "retry-after" and (waited := _http_date_ms(value, now_ms)) is not None:
                return waited
            continue
        if isfinite(number) and number >= 0:
            return ceil(number * scale)
    return None


def _http_date_ms(value: str, now_ms: float | None) -> int | None:
    """HTTP 날짜 꼴 `retry-after` 까지 남은 ms. 못 읽으면 None, 지났으면 0. 시간대 없는 날짜는 UTC 로 본다."""
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    now = _now_ms() if now_ms is None else now_ms
    return max(0, ceil(when.timestamp() * 1000 - now))
