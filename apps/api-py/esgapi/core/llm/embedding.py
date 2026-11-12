"""임베딩 호출 길. 흐름은 공급사 SDK 를 직접 부르지 않고 `EmbeddingPort`(흐름의 어댑터)로 받는다.

호출 하나가 지나는 것:
    임베딩 경로 풀기(모델 하나) → 입력을 묶음으로 나누기(요청의 batch_size 와 모델의 max_inputs_per_request 가운데
    작은 쪽) → 묶음마다: 호출 직전의 비용 상한 확인 → 공급사 호출 → 모양 검사 → 기록 한 줄

채팅(client.py 의 LlmClient)과 다른 점 셋:
  - 프롬프트가 없다. 기록 줄의 prompt_id 는 "embedding", prompt_version 0, template_hash "" 다.
  - 대체 모델이 없다. 경로는 모델 하나를 가리킨다: 모델이 다르면 벡터 공간이 달라 섞을 수 없다.
  - 같은 모델 재시도는 묶음마다 호출 층이 채팅과 같은 정책(retry.next_retry — 대기 예산의 단위는 묶음 하나)으로 하고,
    시도마다 상한 확인·기록 한 줄(provider_retry·previous_error_status·retry_wait_ms)이다(LB1). SDK 의 자체 재시도는 0
    (EMBEDDING_SDK_MAX_RETRIES — LB1 Q5): 기록 줄 하나 = HTTP 요청 하나.

기록은 채팅과 같은 `CallLogSink` 로 간다(있는 CallRecord 꼴, 묶음마다 한 줄, 새 칸 embedding_inputs). 본문(입력
글자)은 싣지 않는다(해시만). 결과는 갈래 넷 가운데 하나로 돌려주고 던지지 않는다. 설정 오류(없는 경로, 어댑터 없음,
batch_size 범위, 빈 글자 입력)만 LlmConfigError 로 던진다.

★ 무효 조건:
  - 묶음의 토큰 합 상한(모델의 max_tokens_per_request)과 입력 하나의 상한(max_input_tokens)은 재지 않는다. 넘으면
    공급사가 거절하고 EmbedProviderFailed(retryable=False)가 된다. 토큰을 셀 도구가 없어서다(새 의존성 0).
  - 묶음 하나가 실패하면 그 embed 전체가 실패다. 앞 묶음의 비용은 기록에 남고 벡터는 버려진다. 단계 안 이어 돌기는
    흐름의 일이다.
  - 상한(limits)은 클라이언트에 준 싱크의 누계를 읽는다. 채팅과 다른 싱크 객체면 서로의 비용을 못 본다(메모리 싱크).
  - DB 싱크로 쓴 줄은 embedding_inputs 를 잃는다(표에 칸이 없다). 칸을 더하는 것은 마이그레이션이라 이 파일 밖이다.
  - DB 싱크는 트랜잭션 밖이면 쓰지 않는다. 흐름을 트랜잭션 밖에서 돌리면 임베딩 줄도 채팅 줄과 똑같이 남지 않는다.
  - 기록은 이 클라이언트가 한 번 쓴다. 포트를 감싸는 래퍼가 CallRecord 를 또 쓰면 줄이 둘이 된다. 한 실행의 줄을
    모으려면 래퍼가 아니라 싱크를 넘긴다(setup.build_embedding_client 의 sink=).
  - 시간 제한은 어댑터가 SDK 의 timeout 으로 건다(client.py 의 머리와 같다).
  - 실패 묶음의 보수 어림(LH2 Q5): 시간 초과·나간 요청의 상태 없는 오류·2xx 오류 줄에 `cost_bound_usd` = 입력 토큰
    어림 × 입력 단가 × (1 + SDK 재시도 — openai 의 EMBEDDING_SDK_MAX_RETRIES, LB1 Q5 뒤 0 이라 × 1). 장부 cost_usd
    는 None 그대로. 「성공·모양 틀림인데 토큰 None」 줄도 같은 어림을 싣는다(LH3 Q6 — 과금은 확실).
  - Celery 소프트 제한은 공급사 오류로 삼키지 않고 다시 던진다(client.py 머리와 같다 — 던지기 전에 timeout 줄 하나. 그
    줄 쓰기가 던지면 예외 이름만 logger 에 남기고 원래 소프트 제한을 던진다 — LH3 Q4).
"""

import logging
import math
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal, Protocol, cast

from esgapi.core.llm.budget import BudgetGuard, BudgetLimit
from esgapi.core.llm.client import DEFAULT_TIMEOUT_MS
from esgapi.core.llm.config import EmbeddingModelConfig, LlmConfig, resolve_embedding_route
from esgapi.core.llm.cost import HeuristicTokenEstimator, TokenEstimator, round_usd
from esgapi.core.llm.embedding_types import EmbeddingProviderRequest, EmbeddingProviderResponse, EmbeddingVectors
from esgapi.core.llm.errors import LlmConfigError, soft_deadline_in
from esgapi.core.llm.log import MISSING, CallLogSink, CallRecord, Missing, sha256_json
from esgapi.core.llm.providers.redact import redact_keys
from esgapi.core.llm.retry import (
    DEFAULT_PROVIDER_RETRY,
    NO_RETRY,
    RetryPolicy,
    default_jitter,
    next_retry,
    validate_retry_policies,
)
from esgapi.core.llm.types import (
    Attempt,
    AttemptKind,
    ErrorKind,
    InvokeOptions,
    LlmResultKind,
    ProviderError,
    Scope,
    Tags,
    Usage,
)
from esgapi.core.resources.ports.llm import EmbeddingProvider

logger = logging.getLogger(__name__)

__all__ = [
    "EMBEDDING_PROMPT_ID",
    "ClientEmbeddingPort",
    "EmbedBudgetExceeded",
    "EmbedDryRun",
    "EmbedMeta",
    "EmbedProviderFailed",
    "EmbedRequest",
    "EmbedResult",
    "EmbedTimedOut",
    "Embedded",
    "EmbeddingClient",
    "EmbeddingFailed",
    "EmbeddingPort",
    "EmbeddingProviderRequest",
    "EmbeddingProviderResponse",
    "EmbeddingVectors",
]

# 기록 줄의 prompt_id. prompt_version 0, template_hash "" 와 같이 쓴다(DB 표의 세 칸이 NOT NULL 이다).
EMBEDDING_PROMPT_ID: Final = "embedding"
_PER_MTOK = 1_000_000


@dataclass(frozen=True)
class EmbedRequest:
    """임베딩 호출 하나.

    inputs      임베딩할 글. 비면 공급사를 부르지 않고 빈 Embedded(기록 0). 빈 글자("")가 끼면 LlmConfigError.
    route       설정 파일의 임베딩 경로 이름(embeddingRoutes). 채팅의 경로와 이름 칸이 따로다.
    tags        기록과 비용 집계의 꼬리표(테넌트, 모듈).
    batch_size  묶음 하나의 입력 수. None 이면 모델의 max_inputs_per_request. 그보다 크거나 1 보다 작으면
                LlmConfigError.
    """

    inputs: Sequence[str]
    route: str
    tags: Tags
    batch_size: int | None = None
    timeout_ms: float = DEFAULT_TIMEOUT_MS


@dataclass(frozen=True)
class EmbedMeta:
    """`attempts` 는 공급사를 부른 묶음마다 하나. `total_cost_usd` 는 비용을 보고받은 시도의 합이다."""

    call_id: str
    model: str
    attempts: tuple[Attempt, ...]
    total_cost_usd: float


# ── 결과: 4갈래 ──


@dataclass(frozen=True)
class Embedded:
    """벡터는 입력 차례다."""

    vectors: tuple[tuple[float, ...], ...]
    meta: EmbedMeta
    kind: Literal["embedded"] = "embedded"


@dataclass(frozen=True)
class EmbedProviderFailed:
    """공급사 오류, 또는 답의 모양이 다르다(벡터 수·차원·유한하지 않은 수 — status None, 재시도 불가).

    `error_kind`·`retry_after_ms`(LB1)는 마지막 공급사 오류의 이름과 「이만큼 뒤에 다시」(ms) — 공급사 오류에서 온
    실패일 때만(모양 틀림은 None)."""

    status: int | None
    retryable: bool
    message: str
    meta: EmbedMeta
    kind: Literal["provider_error"] = "provider_error"
    error_kind: ErrorKind | None = None
    retry_after_ms: int | None = None


@dataclass(frozen=True)
class EmbedTimedOut:
    message: str
    meta: EmbedMeta
    kind: Literal["timeout"] = "timeout"


@dataclass(frozen=True)
class EmbedBudgetExceeded:
    limit_usd: float
    spent_usd: float
    scope: Scope
    meta: EmbedMeta
    kind: Literal["budget_exceeded"] = "budget_exceeded"


type EmbedResult = Embedded | EmbedProviderFailed | EmbedTimedOut | EmbedBudgetExceeded


@dataclass(frozen=True)
class EmbedDryRun:
    """공급사를 부르지 않은 어림. `input_tokens` 는 글자 수로 어림한 값이다(과금 근거 아님).

    request  공급사 고유 요청 본문(첫 묶음). 입력이 없으면 None.
    """

    provider: str
    model: str
    requests: int
    inputs: int
    input_tokens: int
    cost_usd: float
    request: object


@dataclass(frozen=True)
class _Prepared:
    model: EmbeddingModelConfig
    provider: EmbeddingProvider
    batches: tuple[tuple[str, ...], ...]


def _now_ms() -> float:
    return time.time_ns() // 1_000_000


def _sleep_ms(ms: float) -> None:
    time.sleep(ms / 1000)


def _iso(ms: float) -> str:
    """JS 의 `toISOString()` 과 같은 꼴(client.py 의 것과 같은 식)."""
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EmbeddingClient:
    """
    providers   공급사 이름 → 임베딩 어댑터. 설정 파일의 `provider` 값과 맞춘다.
    log         호출 기록의 싱크. 예산 상한도 누적 비용을 여기서 읽는다. 채팅과 같은 싱크를 넘기면 줄이 한곳에 모인다.
    limits      비용 상한들. 비우면 상한이 없다.
    estimator   dry-run 의 토큰 어림. 없으면 설정의 tokenEstimate 로 글자 수를 센다.
    provider_retry·sleep·jitter  같은 모델 재시도(LB1 — LlmClient 와 같은 이름·기본·뜻, retry.py). provider_retry 를
                주면 기본을 통째로 바꾼다({} 는 아무도 다시 부르지 않는다).
    """

    def __init__(
        self,
        *,
        config: LlmConfig,
        providers: Mapping[str, EmbeddingProvider],
        log: CallLogSink,
        limits: Sequence[BudgetLimit] = (),
        estimator: TokenEstimator | None = None,
        now: Callable[[], float] = _now_ms,
        provider_retry: Mapping[str, RetryPolicy] | None = None,
        sleep: Callable[[float], None] = _sleep_ms,
        jitter: Callable[[], float] = default_jitter,
    ) -> None:
        self._config = config
        self._providers = providers
        self._log = log
        self.budget = BudgetGuard(limits, log)
        self._estimator = estimator or HeuristicTokenEstimator(config.token_estimate)
        self._now = now
        self._provider_retry = DEFAULT_PROVIDER_RETRY if provider_retry is None else provider_retry
        validate_retry_policies(self._provider_retry)
        self._sleep = sleep
        self._jitter = jitter

    def embed(self, request: EmbedRequest) -> EmbedResult:
        prepared = self._prepare(request)
        model, provider = prepared.model, prepared.provider
        call_id = str(uuid.uuid4())
        attempts: list[Attempt] = []
        vectors: list[tuple[float, ...]] = []

        def meta() -> EmbedMeta:
            total = round_usd(sum(attempt.cost_usd or 0 for attempt in attempts))
            return EmbedMeta(call_id=call_id, model=model.key, attempts=tuple(attempts), total_cost_usd=total)

        for batch in prepared.batches:
            provider_request = EmbeddingProviderRequest(
                api_model_id=model.api_model_id, inputs=batch, dimensions=model.dimensions
            )
            request_hash = sha256_json(provider_request.to_json())

            def write(
                *,
                logged: bool,
                kind: LlmResultKind,
                input_tokens: int | None = None,
                cost_usd: float | None = None,
                duration_ms: float = 0,
                response_model_id: str | None = None,
                error_status: int | Missing | None = MISSING,
                retry_after_ms: int | None = None,
                batch: tuple[str, ...] = batch,
                request_hash: str = request_hash,
                cost_bound_usd: float | None = None,
                error_kind: str | None = None,
                retry: _RetryTrace | None = None,
            ) -> None:
                self._log.record(
                    CallRecord(
                        ts=_iso(self._now()),
                        call_id=call_id,
                        attempt=len(attempts) - 1 if logged else len(attempts),
                        provider=model.provider if logged else None,
                        model=model.key if logged else None,
                        api_model_id=model.api_model_id if logged else None,
                        response_model_id=response_model_id,
                        prompt_id=EMBEDDING_PROMPT_ID,
                        prompt_version=0,
                        template_hash="",
                        request_hash=request_hash,
                        input_tokens=input_tokens,
                        # 토큰을 보고받은 줄(성공과 모양 틀림)만 0. 오류·시간 초과·상한은 None.
                        output_tokens=None if input_tokens is None else 0,
                        cache_read_tokens=None,
                        cache_write_tokens=None,
                        cost_usd=cost_usd,
                        duration_ms=duration_ms,
                        result_kind=kind,
                        tenant=request.tags.tenant,
                        module=request.tags.module,
                        warnings=(),
                        error_status=error_status,
                        retry_after_ms=retry_after_ms,
                        provider_retry=None if retry is None else retry.provider_retry,
                        previous_error_status=MISSING if retry is None else retry.previous_error_status,
                        retry_wait_ms=None if retry is None else retry.retry_wait_ms,
                        embedding_inputs=len(batch),
                        body=None,
                        cost_bound_usd=cost_bound_usd,
                        error_kind=error_kind,
                    )
                )

            # 같은 모델 재시도(LB1 — 채팅과 같은 retry.next_retry. 대기 예산의 단위는 이 묶음 하나).
            retry: _RetryTrace | None = None
            count_done = budget_done = 0
            budget_waited_ms = 0.0
            while True:
                # 재시도 전에도 상한을 다시 본다(채팅과 같다).
                exhausted = self.budget.check(request.tags)
                if exhausted is not None:
                    write(logged=False, kind="budget_exceeded", retry=retry)
                    return EmbedBudgetExceeded(
                        limit_usd=exhausted.limit.limit_usd,
                        spent_usd=exhausted.spent_usd,
                        scope=exhausted.limit.scope,
                        meta=meta(),
                    )

                provider_retry = None if retry is None else retry.provider_retry
                started = self._now()
                try:
                    response = _invoke(provider, provider_request, request.timeout_ms)
                except BaseException as error:
                    if soft_deadline_in(error) is not None:
                        # 나간 요청이 장부·상한에 남게 그 묶음의 줄 하나(LH2 Q8). 그 밖의 BaseException 은 BASE 그대로.
                        attempts.append(
                            _attempt(provider, model, "timeout", None, None, self._now() - started, provider_retry)
                        )
                        # 줄 쓰기가 던져도 올라가는 것은 소프트 제한이다(LH3 Q4 — client.py 와 같다).
                        try:
                            write(
                                logged=True,
                                kind="timeout",
                                duration_ms=attempts[-1].duration_ms,
                                cost_bound_usd=self._worst_usd(batch, model),
                                retry=retry,
                            )
                        except Exception as write_error:
                            logger.warning("임베딩 소프트 제한 뒤 기록 실패 %s", type(write_error).__name__)
                    raise
                duration_ms = self._now() - started

                if isinstance(response, EmbeddingVectors):
                    tokens = response.input_tokens
                    # 모양이 틀린 답도 과금은 됐다. 비용은 남기고(상한이 본다) 결과는 오류로 돌린다.
                    cost_usd = None if tokens is None else round_usd(tokens * model.pricing.input / _PER_MTOK)
                    usage = (
                        None
                        if tokens is None
                        else Usage(
                            input_tokens=tokens, output_tokens=0, cache_read_tokens=None, cache_write_tokens=None
                        )
                    )
                    bad = _invalid_shape(response.vectors, len(batch), model.dimensions)
                    kind: AttemptKind = "success" if bad is None else "provider_error"
                    attempts.append(_attempt(provider, model, kind, usage, cost_usd, duration_ms, provider_retry))
                    write(
                        logged=True,
                        kind=kind,
                        input_tokens=tokens,
                        cost_usd=cost_usd,
                        duration_ms=duration_ms,
                        response_model_id=response.model_id,
                        error_status=MISSING if bad is None else None,
                        # 과금은 확실한데 토큰을 모른다 → 상한 셈에는 보수 어림(LH3 Q6). 장부 cost_usd 는 None 그대로.
                        cost_bound_usd=self._worst_usd(batch, model) if tokens is None else None,
                        retry=retry,
                    )
                    if bad is not None:
                        return EmbedProviderFailed(status=None, retryable=False, message=bad, meta=meta())
                    vectors.extend(response.vectors)
                    break
                if isinstance(response, ProviderError):
                    attempts.append(
                        _attempt(provider, model, "provider_error", None, None, duration_ms, provider_retry)
                    )
                    billed = response.sent and (response.status is None or 200 <= response.status < 300)
                    write(
                        logged=True,
                        kind="provider_error",
                        duration_ms=duration_ms,
                        error_status=response.status,
                        retry_after_ms=response.retry_after_ms,
                        cost_bound_usd=self._worst_usd(batch, model) if billed else None,
                        error_kind=response.error_kind,
                        retry=retry,
                    )
                    decision = next_retry(
                        self._provider_retry.get(model.provider, NO_RETRY),
                        response,
                        maybe_billed=billed,
                        count_done=count_done,
                        budget_done=budget_done,
                        waited_ms=budget_waited_ms,
                        jitter=self._jitter,
                    )
                    if decision is None:
                        return EmbedProviderFailed(
                            status=response.status,
                            retryable=response.retryable,
                            message=response.message,
                            meta=meta(),
                            error_kind=response.error_kind,
                            retry_after_ms=response.retry_after_ms,
                        )
                    if decision.branch == "budget":
                        budget_done += 1
                        budget_waited_ms += decision.wait_ms
                    else:
                        count_done += 1
                    self._sleep(decision.wait_ms)
                    retry = _RetryTrace(
                        provider_retry=count_done + budget_done,
                        previous_error_status=response.status,
                        retry_wait_ms=decision.wait_ms,
                    )
                    continue
                attempts.append(_attempt(provider, model, "timeout", None, None, duration_ms, provider_retry))
                write(
                    logged=True,
                    kind="timeout",
                    duration_ms=duration_ms,
                    cost_bound_usd=self._worst_usd(batch, model),
                    retry=retry,
                )
                return EmbedTimedOut(message=response.message, meta=meta())

        return Embedded(vectors=tuple(vectors), meta=meta())

    def _worst_usd(self, batch: tuple[str, ...], model: EmbeddingModelConfig) -> float:
        """실패 묶음의 보수 어림(LH2 Q5): 입력 토큰 어림 × 입력 단가 × (1 + SDK 재시도). SDK 재시도 수는 openai 어댑터의
        것(임베딩 어댑터가 있는 공급사는 openai 뿐 — 모의에도 같은 수를 곱한다. LB1 Q5 뒤 0). 여기서만 import 한다
        (SDK 를 고를 때에야 읽는다 — core/resources/llm.py 의 머리)."""
        from esgapi.core.llm.providers.openai import EMBEDDING_SDK_MAX_RETRIES

        tokens = sum(self._estimator.estimate(text) for text in batch)
        return round_usd(tokens * model.pricing.input / _PER_MTOK * (1 + EMBEDDING_SDK_MAX_RETRIES))

    def dry_run(self, request: EmbedRequest) -> EmbedDryRun:
        """공급사를 부르지 않고 묶음 수와 어림 토큰·비용, 첫 묶음의 조립된 요청만 돌려준다. 기록 0."""
        prepared = self._prepare(request)
        model, provider = prepared.model, prepared.provider
        input_tokens = sum(self._estimator.estimate(text) for batch in prepared.batches for text in batch)
        first = (
            None
            if not prepared.batches
            else provider.build_request(
                EmbeddingProviderRequest(
                    api_model_id=model.api_model_id, inputs=prepared.batches[0], dimensions=model.dimensions
                )
            )
        )
        return EmbedDryRun(
            provider=provider.name,
            model=model.key,
            requests=len(prepared.batches),
            inputs=sum(len(batch) for batch in prepared.batches),
            input_tokens=input_tokens,
            cost_usd=round_usd(input_tokens * model.pricing.input / _PER_MTOK),
            request=first,
        )

    def _prepare(self, request: EmbedRequest) -> _Prepared:
        model = resolve_embedding_route(self._config, request.route)
        provider = self._providers.get(model.provider)
        if provider is None:
            raise LlmConfigError(f"임베딩 모델 {model.key} 의 공급사 {model.provider} 어댑터가 등록되지 않았다")
        limit = model.max_inputs_per_request
        size = cast("object", limit if request.batch_size is None else request.batch_size)
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise LlmConfigError(f"batch_size 는 1 이상의 정수여야 한다: {size}")
        if size > limit:
            raise LlmConfigError(
                f"batch_size {size} 가 임베딩 모델 {model.key} 의 한 요청 입력 수 상한 {limit} 을 넘는다"
            )
        if isinstance(cast("object", request.inputs), str):
            raise LlmConfigError("inputs 가 글자 하나다. 글의 목록을 넘긴다")
        inputs = tuple(request.inputs)
        if any(text == "" for text in inputs):
            raise LlmConfigError("빈 글자는 임베딩할 수 없다")
        batches = tuple(inputs[start : start + size] for start in range(0, len(inputs), size))
        return _Prepared(model=model, provider=provider, batches=batches)


def _attempt(
    provider: EmbeddingProvider,
    model: EmbeddingModelConfig,
    kind: AttemptKind,
    usage: Usage | None,
    cost_usd: float | None,
    duration_ms: float,
    provider_retry: int | None = None,
) -> Attempt:
    return Attempt(
        provider=provider.name,
        model=model.key,
        kind=kind,
        usage=usage,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        provider_retry=provider_retry,
    )


@dataclass(frozen=True)
class _RetryTrace:
    """같은 모델을 다시 부른 시도에 붙는 기록(client._RetryTrace 와 같은 칸)."""

    provider_retry: int
    previous_error_status: int | None
    retry_wait_ms: float


def _invalid_shape(vectors: tuple[tuple[float, ...], ...], count: int, dimensions: int) -> str | None:
    if len(vectors) != count:
        return f"임베딩 응답의 모양이 다르다: 벡터 수 {len(vectors)} != 입력 수 {count}"
    for vector in vectors:
        if len(vector) != dimensions:
            return f"임베딩 응답의 모양이 다르다: 차원 {len(vector)} != 설정 {dimensions}"
    if not all(math.isfinite(value) for vector in vectors for value in vector):
        return "임베딩 응답의 모양이 다르다: 유한하지 않은 값이 있다"
    return None


def _invoke(
    provider: EmbeddingProvider, request: EmbeddingProviderRequest, timeout_ms: float
) -> EmbeddingProviderResponse:
    try:
        return provider.embed(request, InvokeOptions(timeout_ms=timeout_ms))
    except Exception as error:
        if (deadline := soft_deadline_in(error)) is not None:
            raise deadline from None  # Celery 소프트 제한은 공급사 오류로 바꾸지 않는다(LH2)
        # 어댑터는 던지지 않기로 했지만, 던졌다면 삼키지 않고 공급사 오류로 돌린다.
        return ProviderError(status=None, retryable=False, message=f"어댑터가 예외를 던졌다: {redact_keys(str(error))}")


# ── 흐름이 받는 포트 ──


class EmbeddingPort(Protocol):
    """흐름의 어댑터 꼴. 이름·인자·돌려주는 꼴이 esg-lab GW1(`py/greenwash/ports.py`)의 EmbeddingPort 와 같다.

    실행기가 감쌀 수 있게 메서드 둘로만 부른다. 실패는 EmbeddingFailed 로 던진다(흐름의 단계가 실패하면 실행기가
    감싼다).
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingFailed(Exception):
    """포트가 던지는 것. `result` 에 Embedded 가 아닌 갈래가 있다."""

    def __init__(self, result: EmbedProviderFailed | EmbedTimedOut | EmbedBudgetExceeded) -> None:
        super().__init__(f"임베딩이 실패했다: {result.kind}")
        self.result = result


class ClientEmbeddingPort:
    """EmbeddingClient 위의 EmbeddingPort. 묶음 크기는 흐름이 정한다(batch_size — core 에 흐름의 수를 두지 않는다)."""

    def __init__(self, client: EmbeddingClient, *, route: str, tags: Tags, batch_size: int | None = None) -> None:
        self._client = client
        self._route = route
        self._tags = tags
        self._batch_size = batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """embed 한 번(안에서 묶음으로 나뉜다)."""
        result = self._client.embed(
            EmbedRequest(inputs=tuple(texts), route=self._route, tags=self._tags, batch_size=self._batch_size)
        )
        if not isinstance(result, Embedded):
            raise EmbeddingFailed(result)
        return [list(vector) for vector in result.vectors]

    def embed_query(self, text: str) -> list[float]:
        """입력 하나로 embed 한 번."""
        return self.embed_documents([text])[0]
