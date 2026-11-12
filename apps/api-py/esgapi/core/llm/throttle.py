"""공급사 호출의 시작 간격을 벌린다(분당 요청 수 한도가 있는 키용). 요청 내용은 건드리지 않는다.

★ 무효 조건: 간격은 이 객체 하나(= 프로세스 하나, 스레드 하나) 안에서만 선다. gunicorn 일꾼이 둘이면 일꾼마다 따로 서서
  합친 호출 수는 분당 한도의 두 배까지 갈 수 있다. 스레드를 여럿 쓰는 일꾼에서는 잠금이 없어 간격이 겹칠 수 있다.
"""

import time
from dataclasses import replace
from typing import Protocol

from esgapi.core.llm.types import InvokeOptions, ProviderRequest, ProviderResponse, ProviderTimeout
from esgapi.core.resources.ports.llm import Provider


class ThrottleClock(Protocol):
    def now(self) -> float:
        """지금(ms). 기준점은 아무래도 좋고 뒤로 가지만 않으면 된다."""
        ...

    def sleep(self, ms: float) -> None: ...


class _RealClock:
    def now(self) -> float:
        return time.monotonic() * 1000

    def sleep(self, ms: float) -> None:
        time.sleep(ms / 1000)


class _Throttled:
    def __init__(self, provider: Provider, interval_ms: float, clock: ThrottleClock) -> None:
        self._provider = provider
        self._interval_ms = interval_ms
        self._clock = clock
        self._next_at = 0.0

    @property
    def name(self) -> str:
        return self._provider.name

    def build_request(self, request: ProviderRequest) -> object:
        return self._provider.build_request(request)

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        now = self._clock.now()
        start_at = max(now, self._next_at)
        wait_ms = start_at - now
        # 기다리는 시간도 호출의 시간 제한 안에 든다. 기다리다 마감을 넘길 것이면 기다리지도 부르지도 않는다
        # (자리도 잡지 않는다: 부르지 않은 호출이 다음 호출을 늦추지 않게).
        if wait_ms >= options.timeout_ms:
            return ProviderTimeout(message="호출 간격을 기다리면 시간 제한을 넘는다")
        self._next_at = start_at + self._interval_ms
        if wait_ms > 0:
            self._clock.sleep(wait_ms)
        # 공급사에는 기다린 만큼 줄어든 시간 제한을 넘긴다.
        return self._provider.invoke(request, replace(options, timeout_ms=options.timeout_ms - wait_ms))


def throttled(provider: Provider, requests_per_minute: float, clock: ThrottleClock | None = None) -> Provider:
    if not requests_per_minute > 0:
        raise ValueError(f"분당 요청 수는 양수여야 한다: {requests_per_minute}")
    return _Throttled(provider, 60_000 / requests_per_minute, clock or _RealClock())
