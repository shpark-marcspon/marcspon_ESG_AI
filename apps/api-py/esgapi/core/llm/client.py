"""호출 층의 입구. 모듈은 공급사 SDK 를 직접 부르지 않고 `LlmClient.call` 을 부른다.

호출 하나가 지나는 것:
    프롬프트 읽기·변수 치환 → 경로의 모델 순회(첫 모델이 주, 나머지가 대체) → 호출 직전의 비용 상한 확인
    → 공급사 호출 → 스키마 검증(어긋나면 같은 모델로 다시, 기본 2회) → 시도마다 호출 기록 한 줄

다음 모델로 넘어가는 실패는 공급사 쪽 장애뿐이다: 시간 초과와, 재시도 가능한 공급사 오류(한도 초과·5xx·연결 실패),
크레딧·청구 소진(quota_exhausted — 같은 모델은 다시 안 부르고 다른 공급사·키일 수 있는 다음 모델로, LB1 Q6).
스키마 불일치, 거부, 출력 잘림은 다른 공급사로 가도 같은 입력이라 대체하지 않는다. 잘못된 요청·인증 실패 같은 재시도
불가
오류는 설정이나 요청의 문제라 덮지 않고 그대로 돌려준다.
순서: 재시도 가능한 공급사 오류는 먼저 같은 모델을 다시 부르고(`provider_retry`, 설정된 공급사만 — 갈래 둘은
retry.py 머리: 한도 초과·과부하는 대기 예산, 그 밖은 횟수), 그래도 실패하면 다음 모델로.

openai·anthropic SDK 의 자체 재시도는 0 이다(LH1 — 어댑터의 머리). 그래서 공급사로 나간 HTTP 요청은 전부 이 층의
상한 확인과 기록 한 줄을 지난다. 남는 몫: 기록을 쓰기 전에 프로세스가 죽은 호출 하나(그 요청은 나갔으나 줄이 없다).

동기다. ★ 무효 조건 셋:
  - 시간 제한은 어댑터가 SDK 의 timeout 으로 건다. 호출 층이 밖에서 끊지 못한다: 어댑터(나 SDK)가 시간 제한을 지키지
  않으면
    `call` 은 그만큼 늦게 돌아온다. esg-lab 은 호출 층이 따로 시계를 걸어 끊었다(Promise.race).
  - 예산의 누적과 호출 간격은 프로세스 하나의 것이다(budget.py, throttle.py 의 머리).
  - 한 호출(`call`·`call_tools` 고리 한 번)의 벽시계 최악(LB1) = 경로 모델 수 × [timeout × (1 + max_retries +
    max_budget_retries) + 횟수 갈래 대기(≤ max_delay × 1.2 × max_retries)] + 예산 갈래 대기 합(≤ wait_budget_ms, 호출
    하나에서 모델·걸음을 넘어 합산 — retry.py). 늦게 오는 5xx·연결 끊김·429 는 시도마다 timeout 까지 걸릴 수 있다(시간
    초과 자체는 같은 모델을 다시 부르지 않는다). 기본값(120초, 재시도 2, 천장 8, 예산 30초)으로 모델 하나면 timeout 몫이
    120 × 11 — 작업의 soft 240·hard 300초(config/env.py)보다 길다. 실제로는 429·529 가 곧바로 오므로 예산 30초가
    벽시계를 정하지만, 숫자는 고치지 않았다(LH1 Q7 — 받아들임, 실행 층이 받는 것은 안 B). ★ 무효 조건: 예산 + 경로
    모델 수 × timeout 이 soft 240초를 넘으면 soft limit 이 먼저 끊는다.

실패 시도의 보수 어림(LH2, MARC-ISSUE-411 S2): 공급사가 과금했을 수 있는 실패 — 시간 초과, 상태 없는 공급사 오류,
2xx 인데 오류(anthropic 스트림의 error 사건)— 의 기록 줄에 `cost_bound_usd` = 그 시도의 한 번 최악(요청 JSON 의 토큰
어림 + 출력 상한, 그 모델 단가 — `_worst_once_usd`)을 싣는다. 장부 칸 `cost_usd` 는 None 그대로(실비를 모른다).
★ 무효 조건: HTTP 상태로 거절된 오류(4xx·5xx)는 과금 없음으로 본다 — 추정(공급사 문서로 재지 않았다). 요청이 나가지
  않은 오류(`ProviderError.sent=False` — 어댑터 앞 거절·연결 실패)도 0. 첨부(PDF·그림)의 base64 는 어림 밖이다(추정 —
  토큰이 글자 수로 정해지지 않는다). 공급사가 출력 상한보다 더 매기거나 단가가 틀리면 어림도 틀린다.
Celery 소프트 제한(LH2 S3): 어댑터·`_invoke`·도구 실행 자리는 SoftTimeLimitExceeded(조상 이름 — errors.soft_deadline_in)
를 공급사 오류로 삼키지 않고 다시 던진다. 같은 모델 재시도·대체 모델로 가지 않고, 던지기 전에 그 시도의 `timeout` 줄
하나(어림 포함)를 쓴다. 그 줄 쓰기가 던지면(싱크의 OSError·InterfaceError 등) 예외 이름만 logger 에 남기고 원래 소프트
제한을 던진다(LH3 Q4 — 그 줄은 없다. 「기록을 쓰기 전에 죽은 호출」과 같은 몫).
★ soft limit 뒤 기록의 시간은 받아들임(LH3 Q7 — MARC-ISSUE-413 I7): soft limit 뒤의 일은 순수 어림 셈과 줄 하나 쓰기다.
  DB 싱크면 연결 시간 상한 connect_timeout 2초(config/settings/base.py)뿐이고 문장 시간 상한(statement_timeout)은 두지
  않았다. hard 까지 60초(config/env.py soft 240·hard 300)를 넘길 길은 DB 가 멈춘 때뿐이고, 그때는 hard 가 죽이며 줄이
  없다(위 「기록을 쓰기 전에 죽은 호출」과 같은 몫).
web_search 의 실패 어림(LH3 Q3 — I3): web_search 를 실은 시도의 `cost_bound_usd` 에 건당 요금 × max_hosted_calls 를
더한다. max_hosted_calls 가 없으면(모듈의 call_tools 가 그렇게 싣는다) 1건으로 센다 — 과소, 받아들임(한 걸음에 공급사가
몇 번 검색할지 모른다).
dry-run 위끝의 캐시 쓰기 할증(LH3 Q8·Q9 — MARC-ISSUE-417): 캐시 지정 자리(SystemSegment.cache)의 몫은 쓰기 단가가 입력
단가보다 크면 쓰기 단가로 센다(`_bound_usd` — 위끝은 같거나 커질 뿐). openai·gemini 의 쓰기 단가가 입력과 같은 모델은 0
변화, anthropic·쓰기 단가가 더 큰 모델(가상 모델 포함)의 캐시 지정 요청만 오른다.
"""

import json
import logging
import math
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Literal, cast

from pydantic import TypeAdapter, ValidationError

from esgapi.core.llm.budget import BudgetGuard, BudgetLimit
from esgapi.core.llm.config import HostedToolPricing, LlmConfig, ModelConfig, Pricing, resolve_route
from esgapi.core.llm.cost import HeuristicTokenEstimator, TokenEstimator, compute_cost_usd, round_usd
from esgapi.core.llm.errors import LlmConfigError, soft_deadline_in
from esgapi.core.llm.log import MISSING, CallLogSink, CallRecord, Missing, RecordBody, sha256_json
from esgapi.core.llm.prompts import (
    PromptStore,
    PromptTemplate,
    RenderedPrompt,
    parse_prompt_id,
    render_prompt,
)
from esgapi.core.llm.providers.redact import redact_keys
from esgapi.core.llm.retry import (
    DEFAULT_PROVIDER_RETRY,
    NO_RETRY,
    RetryPolicy,
    default_jitter,
    next_retry,
    validate_retry_policies,
)
from esgapi.core.llm.schema import to_strict_json_schema
from esgapi.core.llm.types import (
    Attachment,
    Attempt,
    AttemptKind,
    BudgetExceeded,
    CallMeta,
    Completed,
    CutOff,
    DryRunEstimate,
    DryRunReport,
    FunctionTool,
    InvokeOptions,
    JsonSchemaSpec,
    LlmResult,
    LlmResultKind,
    LlmWarning,
    ProviderError,
    ProviderFailed,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
    Refusal,
    Refused,
    SchemaIssue,
    SchemaMismatch,
    Scope,
    Success,
    SystemPlacement,
    Tags,
    TextPart,
    TimedOut,
    Tool,
    ToolCallsRequested,
    ToolChoice,
    ToolExecutor,
    ToolExecutorRaised,
    ToolLoopDone,
    ToolLoopEstimate,
    ToolLoopFailed,
    ToolLoopFailure,
    ToolLoopPartial,
    ToolLoopResult,
    ToolOutput,
    ToolStep,
    Truncated,
    Turn,
    Usage,
    WebSearchTool,
)
from esgapi.core.resources.ports.llm import Provider

logger = logging.getLogger(__name__)

# 기본값 셋은 esg-lab 의 호출 층에서 그대로 옮겼다(출력 4096 토큰, 120초, 스키마 재시도 2회).
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_TIMEOUT_MS = 120_000
DEFAULT_SCHEMA_RETRIES = 2

# temperature 의 범위. OpenAI Responses 의 'between 0 and 2'(설치된 openai 3.26.0
# types/responses/response_create_params.py:260) 에 맞춘다. Gemini 는 같은 값을 그대로 싣는다.
TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 2.0
# temperature 를 받지 않는 공급사. 값을 주면 이 공급사의 모델이 경로에 있는 것만으로 거부한다.
#   anthropic: 설치된 anthropic 1.11.0 의 messages.stream 에 temperature 인자가 없어(패키지 안 'temperature' 0곳)
#     extra_body 없이는 실을 수 없다. API 참조(https://platform.claude.com/docs/en/api/messages/create, 2026-10-16
#     확인)에는 `temperature`(0.0~1.0, 기본 1.0)가 Deprecated 로 남아 있다: 'Models released after Claude Opus 4.6
#     do not support setting temperature. A value of 1.0 will be accepted for backwards compatibility, all other
#     values will be rejected with a 400 error.' Haiku 4.5 는 받는다
#     (https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide). Sonnet 4.6 이 'Opus 4.6 뒤' 에 드는지는
#     못 확인. extra_body 로 싣지 않기로 했다(감독 처분, MARC-TICK-136 노트).
TEMPERATURE_UNSUPPORTED_PROVIDERS: frozenset[str] = frozenset({"anthropic"})
# temperature 를 받지 않는 모델(api_model_id). 어댑터는 reasoning 을 보내지 않아 기본 추론 강도(medium)가 걸린다.
#   gpt-6-luna, gpt-6.1-sol: https://developers.openai.com/api/docs/guides/latest-model 'When reasoning effort is not
#     `none`, remove `temperature`, `top_p`, and `top_logprobs`.' (2026-10-16 확인).
#     gpt-6.1-sol 은 `none` 을 받지 않는다(같은 문서).
TEMPERATURE_UNSUPPORTED_MODELS: frozenset[str] = frozenset({"gpt-6-luna", "gpt-6.1-sol"})

# 도구 호출 고리(`call_tools`, 밴드 TL1 `MARC-TICK-180`)를 지나는 공급사와 모델. 경로 모델이 이 밖이면 공급사를 부르기
# 전에 LlmConfigError.
#   공급사: OpenAI 어댑터와 모의 공급사 둘만 도구 칸을 싣는다(anthropic·gemini 어댑터는 도구 칸을 거부한다).
#   모델(openai 의 api_model_id, 허용 목록): 고리는 store:false 로 앞 걸음을 다시 싣는다(`MARC-ENT-301`). 추론 모델은
#     추론 항목(암호화된 내용)까지 다시 실어야 할 수 있어(추정) 비추론 모델만 둔다. gpt-4.1: 모델 페이지
#     'Smartest non-reasoning model' (https://developers.openai.com/api/docs/models/gpt-4.1, 2026-10-19 확인).
#     gpt-4o: 모델 페이지에 reasoning 낱말이 없고 'our most capable model outside of our o-series models'
#     (https://developers.openai.com/api/docs/models/gpt-4o, 2026-10-23 확인 — 비추론은 추정). 중대성평가 1부 코랩의
#     모델(MARC-ENT-425, 밴드 IR1b).
#     ★ gpt-4.1·gpt-4o 는 2027-01-14 퇴역(models.json 의 lifecycle) — 퇴역 전에 바꾼다(MARC-ENT-305, MARC-ISSUE-188).
TOOL_PROVIDERS: frozenset[str] = frozenset({"openai", "mock", "mock-b"})
TOOL_MODELS: frozenset[str] = frozenset({"gpt-4.1", "gpt-4o"})


@dataclass(frozen=True)
class CallRequest[T = str]:
    """호출 하나.

    prompt       `모듈/이름@판`. 판을 빼면 거부한다.
    route        설정 파일의 경로 이름. 첫 모델이 주, 나머지가 대체 순서다.
    tags         기록과 비용 집계의 꼬리표(테넌트, 모듈).
    schema       주면 응답을 JSON 으로 받아 이 타입(Pydantic 모델 등)으로 검증한다. 없으면 `data` 는 응답 글자 그대로다.
    max_output_tokens  답의 출력 토큰 상한. 모델 설정에 추론 여유분이 있으면 호출 층이 더해 보낸다.
    max_schema_retries 스키마 불일치 때 같은 모델로 다시 부르는 횟수. 기본 2.
    temperature  표집 온도(0~2). None 이면 싣지 않는다(공급사 기본값). 값을 주면 경로의 모델이 전부 받는 모델이어야
                 한다 — 받지 않는 모델(`TEMPERATURE_UNSUPPORTED_*`)이 하나라도 있으면 공급사를 부르기 전에
                 LlmConfigError.
    """

    prompt: str
    route: str
    tags: Tags
    vars: Mapping[str, str] = field(default_factory=dict[str, str])
    schema: type[T] | None = None
    schema_name: str = "output"
    attachments: Sequence[Attachment] = ()
    max_output_tokens: int | None = None
    timeout_ms: float = DEFAULT_TIMEOUT_MS
    max_schema_retries: int = DEFAULT_SCHEMA_RETRIES
    temperature: float | None = None


@dataclass(frozen=True)
class ToolCallRequest:
    """도구 호출 고리 한 번(`LlmClient.call_tools`·`dry_run_tools`). 글 결과만 낸다(스키마 없음 — 구조화가 필요하면
    끝에 `call` 한 번).

    prompt·route·tags·vars·attachments·max_output_tokens·timeout_ms·temperature
                 `CallRequest` 와 같다. 출력 상한과 시간 한도는 걸음마다다.
    tools        모델에게 줄 도구(`FunctionTool`·`WebSearchTool`). 비우면 거부한다. core 는 도구 이름을 거르지 않는다
                 (모르는 이름도 실행 함수로 간다).
    max_steps    공급사 「걸음」 수의 상한(1 이상). 같은 모델 재시도는 걸음을 쓰지 않는다(기록·비용은 남는다).
    tool_choice·parallel_tool_calls  None 이면 싣지 않는다(공급사 기본값).
    max_cost_usd 고리 한 번의 비용 상한(USD, 0 보다 큼). 공급사를 부르기 전마다 이 고리의 지금까지 비용이 이 값
                 이상이면 막는다 — 닿으면 막는 상한이라 마지막 걸음만큼 넘을 수 있다. 기존 BudgetLimit 도 걸음마다 본다.
    max_hosted_calls  공급사가 실행하는 도구(web_search)의 응답 하나당 상한(OpenAI `max_tool_calls`, 1 이상).
    system_placement  system 글의 자리. "input_message" 면 input 맨 앞의 system 메시지로 싣는다(코랩의 꼴).

    경로는 모델 하나여야 하고(대체 없음 — 걸음 중간에 공급사가 바뀌면 앞 항목을 다른 꼴로 실어야 한다), 그 모델이
    도구를 받는 공급사·모델(`TOOL_PROVIDERS`·`TOOL_MODELS`)이어야 한다. web_search 를 실으면 그 모델에 건당 요금
    (`hostedToolPricing`)이 있어야 한다. 어긋나면 공급사를 부르기 전에 LlmConfigError.

    ★ 무효 조건: 요청(HTTP) 안에서 부르지 않는다 — 고리는 걸음 수 × timeout_ms 까지 걸려 gunicorn 의 30초를 넘는다.
    실행 층의 일감 안에서 부른다. 트랜잭션 블록 안에서도 부르지 않는다(기록 줄이 블록과 같이 되돌려진다).

    쓰는 예:
        tools = (FunctionTool(name="lookup", description="값 찾기", parameters={"type": "object", "properties": {}}),)

        def execute(name: str, arguments: str) -> str:
            return dispatch(name, arguments)  # 부르는 쪽의 분배기. 모르는 이름·인자 틀림도 글자로 돌려준다

        request = ToolCallRequest(prompt="m/insight@1", route="standard-openai-41", tags=tags, tools=tools, max_steps=6)
        match client.call_tools(request, execute):
            case ToolLoopDone(text=text, citations=citations): ...  # 끝난 답
            case ToolLoopPartial(text=text, pending=pending): ...  # 걸음이 다함
            case ToolLoopFailed(failure=failure, budget_source=source): ...
    """

    prompt: str
    route: str
    tags: Tags
    tools: Sequence[Tool]
    max_steps: int
    vars: Mapping[str, str] = field(default_factory=dict[str, str])
    attachments: Sequence[Attachment] = ()
    max_output_tokens: int | None = None
    timeout_ms: float = DEFAULT_TIMEOUT_MS
    temperature: float | None = None
    tool_choice: ToolChoice | None = None
    parallel_tool_calls: bool | None = None
    max_cost_usd: float | None = None
    max_hosted_calls: int | None = None
    system_placement: SystemPlacement = "instructions"


@dataclass(frozen=True)
class _RetryTrace:
    """같은 모델을 다시 부른 시도에 붙는 기록."""

    provider_retry: int
    previous_error_status: int | None
    retry_wait_ms: float


@dataclass(frozen=True)
class _Prepared:
    template: PromptTemplate
    rendered: RenderedPrompt
    models: tuple[ModelConfig, ...]
    # models 와 같은 순서의 어댑터. 첫 호출 전에 다 찾아 둔다: 대체 모델의 공급사가 등록되지 않았거나 키가 없으면
    # 주 모델을 부르기(= 돈을 쓰기) 전에 예외가 난다.
    providers: tuple[Provider, ...]


@dataclass(frozen=True)
class _Valid[T]:
    data: T


@dataclass(frozen=True)
class _Invalid:
    issues: tuple[SchemaIssue, ...]


@dataclass
class _CallState:
    """호출 하나(`call`) 또는 고리 한 번(`call_tools`)의 시도와 경고. 시도마다 기록 한 줄이 같은 `call_id` 로 남는다."""

    call_id: str
    template: PromptTemplate
    tags: Tags
    attempts: list[Attempt] = field(default_factory=list[Attempt])
    warnings: list[LlmWarning] = field(default_factory=list[LlmWarning])
    # 예산 갈래(한도 초과·과부하)로 이 호출에서 이미 기다린 합(ms — retry.py 머리의 단위: 모델·걸음을 넘어 합산).
    budget_waited_ms: float = 0.0

    def total_cost_usd(self) -> float:
        return round_usd(sum(attempt.cost_usd or 0 for attempt in self.attempts))

    def meta(self) -> CallMeta:
        return CallMeta(
            call_id=self.call_id,
            prompt_id=self.template.id,
            attempts=tuple(self.attempts),
            total_cost_usd=self.total_cost_usd(),
            warnings=tuple(self.warnings),
        )


@dataclass(frozen=True)
class _Answered[T]:
    """공급사가 답했다(오류·시간 초과도 답이다). `validated` 는 완료 응답일 때만 있다."""

    response: ProviderResponse
    validated: _Valid[T] | _Invalid | None


@dataclass(frozen=True)
class _Exhausted:
    """부르기 전에 상한에 닿았다. "guard" 는 BudgetLimit, "loop" 는 고리 한 번의 상한."""

    failure: BudgetExceeded
    source: Literal["guard", "loop"]


@dataclass(frozen=True)
class _ToolPrepared:
    template: PromptTemplate
    rendered: RenderedPrompt
    model: ModelConfig
    provider: Provider
    # 첫 걸음의 요청(앞 걸음 항목 없음). 걸음마다 turns 만 바꿔 싣는다.
    request: ProviderRequest


def _now_ms() -> float:
    return time.time_ns() // 1_000_000


def _sleep_ms(ms: float) -> None:
    time.sleep(ms / 1000)


class LlmClient:
    """
    providers       공급사 이름 → 어댑터. 설정 파일의 `provider` 값과 맞춘다.
    log             호출 기록의 싱크. 예산 상한도 누적 비용을 여기서 읽는다.
    limits          비용 상한들. 비우면 상한이 없다.
    store_bodies    기록에 요청 본문과 응답 글자를 그대로 남길지. 기본은 남기지 않고 해시만 남긴다.
    provider_retry  공급사 이름 → 같은 모델을 다시 부르는 설정. 주면 기본을 통째로 바꾼다({} 는 아무도 다시 부르지
    않는다).
    sleep           재시도 전의 대기(ms). 테스트는 실제로 기다리지 않는 것을 넣는다.
    jitter          재시도 대기의 흩뜨림(0~1 균등 — retry.py 머리). 기본 random.random. 테스트는 고정 값을 넣는다.
    """

    def __init__(
        self,
        *,
        config: LlmConfig,
        providers: Mapping[str, Provider],
        prompts: PromptStore,
        log: CallLogSink,
        limits: Sequence[BudgetLimit] = (),
        estimator: TokenEstimator | None = None,
        store_bodies: bool = False,
        now: Callable[[], float] = _now_ms,
        provider_retry: Mapping[str, RetryPolicy] | None = None,
        sleep: Callable[[float], None] = _sleep_ms,
        jitter: Callable[[], float] = default_jitter,
    ) -> None:
        self._config = config
        self._providers = providers
        self._prompts = prompts
        self._log = log
        self.budget = BudgetGuard(limits, log)
        self._estimator = estimator or HeuristicTokenEstimator(config.token_estimate)
        self._store_bodies = store_bodies
        self._now = now
        self._provider_retry = DEFAULT_PROVIDER_RETRY if provider_retry is None else provider_retry
        validate_retry_policies(self._provider_retry)
        self._sleep = sleep
        self._jitter = jitter

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        prepared = self._prepare(request)
        template, rendered = prepared.template, prepared.rendered
        state = _CallState(call_id=str(uuid.uuid4()), template=template, tags=request.tags)
        meta = state.meta

        schema_retries = cast("object", request.max_schema_retries)
        if isinstance(schema_retries, bool) or not isinstance(schema_retries, int) or schema_retries < 0:
            raise LlmConfigError(f"max_schema_retries 는 0 이상의 정수여야 한다: {schema_retries}")
        adapter: TypeAdapter[T] | None = None if request.schema is None else TypeAdapter(request.schema)

        failure: ProviderFailed | TimedOut | None = None
        for model, provider in zip(prepared.models, prepared.providers, strict=True):
            schema_json = None if adapter is None else adapter.json_schema()
            provider_request = self._build_provider_request(request, rendered, model, schema_json)
            _add_warnings(state.warnings, self._cache_warnings(rendered, model))

            mismatch: SchemaMismatch | None = None
            failure = None
            for _round in range(schema_retries + 1):
                answer = self._attempt_model(
                    state,
                    model=model,
                    provider=provider,
                    provider_request=provider_request,
                    rendered=rendered,
                    timeout_ms=request.timeout_ms,
                    adapter=adapter,
                    tools_expected=False,
                )
                if isinstance(answer, _Exhausted):
                    return answer.failure
                response, validated = answer.response, answer.validated

                match response:
                    case Completed():
                        if isinstance(validated, _Valid):
                            return Success(data=validated.data, text=response.text, meta=meta())
                        issues = validated.issues if isinstance(validated, _Invalid) else ()
                        mismatch = SchemaMismatch(issues=issues, raw_text=response.text, meta=meta())
                        continue
                    case Refusal():
                        return Refused(text=response.text, category=response.category, meta=meta())
                    case Truncated():
                        return CutOff(partial_text=response.text, meta=meta())
                    case ProviderError():
                        failure = ProviderFailed(
                            status=response.status,
                            retryable=response.retryable,
                            message=response.message,
                            meta=meta(),
                            error_kind=response.error_kind,
                            retry_after_ms=response.retry_after_ms,
                        )
                    case ProviderTimeout():
                        failure = TimedOut(message=response.message, meta=meta())
                    case ToolCallsRequested():
                        failure = ProviderFailed(
                            status=None,
                            retryable=False,
                            message="도구를 주지 않았는데 공급사가 도구 호출을 냈다",
                            meta=meta(),
                        )
                break

            if failure is None:
                if mismatch is None:
                    raise AssertionError("도달할 수 없는 상태: 실패도 불일치도 없이 재시도가 끝났다")
                # meta 는 모든 시도를 담도록 다시 만든다.
                return replace(mismatch, meta=meta())
            if not _should_fallback(failure):
                return failure
        if failure is None:
            raise LlmConfigError(f"경로 {request.route} 에 모델이 없다")
        # 마지막 모델까지 실패했다. meta 는 모든 시도를 담도록 다시 만든다.
        return replace(failure, meta=meta())

    def call_tools(self, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult:
        """도구 호출 고리. 걸음마다: 상한 확인 → 공급사 호출(같은 모델 재시도 포함, 시도마다 기록 한 줄 — `call` 과 같은
        코드) → 답에 함수 호출이 있으면 차례대로 실행하고 다음 걸음. 앞 걸음의 항목(답의 출력 차례 그대로, 그 뒤 결과)은
        우리가 다시 싣는다(store:false, 공급사 항목 id 없이 — MARC-ENT-301). 기록은 `call_id` 하나에 `attempt` 0,1,2… 로
        잇고, 함수 호출을 받은 걸음의 줄도 `success` 다(공급사 호출은 성공).

        끝남(ToolLoopDone): 함수 호출이 없는 답. 부분(ToolLoopPartial): `max_steps` 번째 답이 아직 함수를 부른다 — 더
        부르지 않는다. 실패(ToolLoopFailed): 어느 걸음이든 거부·잘림·공급사 오류·시간 초과·상한·실행 함수의 예외.
        web_search 처럼 공급사가 실행하는 도구는 세기만 한다(`hosted_calls`, 비용은 건수 × 건당).
        """
        prepared = self._prepare_tools(request)
        rendered, model, provider = prepared.rendered, prepared.model, prepared.provider
        state = _CallState(call_id=str(uuid.uuid4()), template=prepared.template, tags=request.tags)
        _add_warnings(state.warnings, self._cache_warnings(rendered, model))

        turns: list[Turn] = []
        steps: list[ToolStep] = []
        hosted_calls = 0
        step_no = 0
        while True:
            step_no += 1
            # 고리는 스키마를 받지 않는다: 답은 글 그대로다.
            answer: _Answered[str] | _Exhausted = self._attempt_model(
                state,
                model=model,
                provider=provider,
                provider_request=replace(prepared.request, turns=tuple(turns)),
                rendered=rendered,
                timeout_ms=request.timeout_ms,
                adapter=None,
                tools_expected=True,
                tool_step=step_no,
                loop_limit_usd=request.max_cost_usd,
            )
            if isinstance(answer, _Exhausted):
                return ToolLoopFailed(
                    failure=answer.failure,
                    steps=tuple(steps),
                    meta=state.meta(),
                    budget_source=answer.source,
                    hosted_calls=hosted_calls,
                )
            response = answer.response

            failure: ToolLoopFailure
            match response:
                case Completed():
                    return ToolLoopDone(
                        text=response.text,
                        citations=response.citations,
                        hosted_calls=hosted_calls + response.hosted_calls,
                        steps=tuple(steps),
                        meta=state.meta(),
                    )
                case ToolCallsRequested():
                    hosted_calls += response.hosted_calls
                    if step_no >= request.max_steps:
                        return ToolLoopPartial(
                            text=response.text,
                            pending=response.calls,
                            hosted_calls=hosted_calls,
                            steps=tuple(steps),
                            meta=state.meta(),
                        )
                    outputs: list[ToolOutput] = []
                    for tool_call in response.calls:
                        try:
                            output = execute(tool_call.name, tool_call.arguments)
                        except Exception as error:
                            if (deadline := soft_deadline_in(error)) is not None:
                                raise deadline from None  # Celery 소프트 제한은 실패 값으로 바꾸지 않는다(LH2)
                            # 삼키지 않는다. 메시지는 싣지 않는다(고객 데이터가 섞일 수 있다).
                            raised = ToolExecutorRaised(name=tool_call.name, error_class=type(error).__name__)
                            return ToolLoopFailed(
                                failure=raised, steps=tuple(steps), meta=state.meta(), hosted_calls=hosted_calls
                            )
                        outputs.append(ToolOutput(call_id=tool_call.call_id, output=output))
                    steps.append(
                        ToolStep(calls=response.calls, outputs=tuple(outputs), hosted_calls=response.hosted_calls)
                    )
                    # 다음 걸음의 입력: 이 답의 항목을 출력 차례 그대로 싣고, 그 뒤에 결과를 호출과 같은 차례로.
                    turns.extend(response.output)
                    turns.extend(outputs)
                    continue
                case Refusal():
                    failure = Refused(text=response.text, category=response.category, meta=state.meta())
                    # 거부·잘림 답 안에서 이미 돈 검색도 과금된다(_cost_usd 와 같은 갈래 — 624).
                    hosted_calls += response.hosted_calls
                case Truncated():
                    failure = CutOff(partial_text=response.text, meta=state.meta())
                    hosted_calls += response.hosted_calls
                case ProviderError():
                    failure = ProviderFailed(
                        status=response.status,
                        retryable=response.retryable,
                        message=response.message,
                        meta=state.meta(),
                        error_kind=response.error_kind,
                        retry_after_ms=response.retry_after_ms,
                    )
                case ProviderTimeout():
                    failure = TimedOut(message=response.message, meta=state.meta())
            return ToolLoopFailed(failure=failure, steps=tuple(steps), meta=state.meta(), hosted_calls=hosted_calls)

    def dry_run[T](self, request: CallRequest[T]) -> DryRunReport:
        """공급사를 부르지 않고 조립된 요청과 어림 토큰·비용만 돌려준다."""
        prepared = self._prepare(request)
        rendered = prepared.rendered
        model, provider = prepared.models[0], prepared.providers[0]
        schema_json = None if request.schema is None else TypeAdapter(request.schema).json_schema()
        provider_request = self._build_provider_request(request, rendered, model, schema_json)

        input_tokens = self._estimator.estimate(
            "\n".join([*(segment.text for segment in rendered.system), rendered.user])
        )
        upper_bound = Usage(
            input_tokens=input_tokens,
            output_tokens=provider_request.max_output_tokens,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )
        # 최악(LH1 Q6): 공급사에 실린 schema 의 토큰을 입력에 더한 한 번 × 스키마 다시 부르기까지의 시도 수.
        sent_schema = provider_request.json_schema
        schema_tokens = (
            0
            if sent_schema is None
            else self._estimator.estimate(json.dumps(sent_schema.schema, ensure_ascii=False, separators=(",", ":")))
        )
        max_attempts = 1 if request.schema is None else 1 + request.max_schema_retries
        cached = self._cached_tokens(provider_request)
        worst_once = _bound_usd(replace(upper_bound, input_tokens=input_tokens + schema_tokens), cached, model.pricing)
        return DryRunReport(
            prompt_id=prepared.template.id,
            provider=provider.name,
            model=model.key,
            request=provider.build_request(provider_request),
            estimate=DryRunEstimate(
                input_tokens=input_tokens,
                cacheable_tokens=self._cacheable_tokens(rendered),
                max_output_tokens=provider_request.max_output_tokens,
                cost_upper_bound_usd=_bound_usd(upper_bound, cached, model.pricing),
                unestimated_parts=tuple(part.type for part in request.attachments),
                schema_tokens=schema_tokens,
                max_attempts=max_attempts,
                worst_case_usd=round_usd(worst_once * max_attempts),
            ),
            fallback_models=tuple(fallback.key for fallback in prepared.models[1:]),
            warnings=tuple(self._cache_warnings(rendered, model)),
        )

    def dry_run_tools(self, request: ToolCallRequest) -> DryRunReport:
        """공급사를 부르지 않고 첫 걸음의 요청과 고리의 비용 위끝(`ToolLoopEstimate`)을 돌려준다. 거름은 `call_tools` 와
        같다(공급사 호출 전 LlmConfigError).

        입력 어림 = 프롬프트(system·user) + 어댑터가 싣는 도구 정의의 JSON 글자. 걸음 k 의 위끝은 앞 걸음 k−1 개가 출력
        상한을 다 써서 다시 실린 몫을 입력에 더한다. 도구 결과 글자는 어림할 수 없어 들지 않는다(경고).
        """
        prepared = self._prepare_tools(request)
        rendered, model, provider, first = prepared.rendered, prepared.model, prepared.provider, prepared.request
        body = provider.build_request(first)

        prompt_tokens = self._estimator.estimate(
            "\n".join([*(segment.text for segment in rendered.system), rendered.user])
        )
        input_tokens = prompt_tokens + self._estimator.estimate(_tools_json(body, first))
        max_out = first.max_output_tokens
        cached = self._cached_tokens(first)
        step_bounds = tuple(
            _bound_usd(
                Usage(
                    input_tokens=input_tokens + (step - 1) * max_out,
                    output_tokens=max_out,
                    cache_read_tokens=0,
                    cache_write_tokens=0,
                ),
                cached,
                model.pricing,
            )
            for step in range(1, request.max_steps + 1)
        )

        unestimated = ["tool_outputs"]
        warnings = self._cache_warnings(rendered, model)
        warnings.append(
            LlmWarning(
                code="tool_outputs_unestimated",
                message="도구 결과 글자가 다음 걸음의 입력에 쌓이는 몫은 어림할 수 없어 위끝에 들지 않는다.",
            )
        )
        hosted_usd = 0.0
        hosted = model.hosted_tool_pricing
        if any(isinstance(tool, WebSearchTool) for tool in request.tools) and hosted is not None:
            # 검색 내용 토큰은 모델 단가로 과금된다(openai_pricing) — 얼마나 실릴지 몰라 들지 않는다.
            unestimated.append("web_search_content")
            if request.max_hosted_calls is None:
                unestimated.append("web_search_calls")
                warnings.append(
                    LlmWarning(
                        code="hosted_calls_unbounded",
                        message="max_hosted_calls 가 없어 web_search 건수의 몫을 위끝에 넣지 못했다.",
                    )
                )
            else:
                hosted_usd = request.max_steps * request.max_hosted_calls * hosted.web_search_per_call
        retries = self._provider_retry.get(model.provider, NO_RETRY).max_retries
        return DryRunReport(
            prompt_id=prepared.template.id,
            provider=provider.name,
            model=model.key,
            request=body,
            estimate=DryRunEstimate(
                input_tokens=input_tokens,
                cacheable_tokens=self._cacheable_tokens(rendered),
                max_output_tokens=max_out,
                cost_upper_bound_usd=step_bounds[0],
                unestimated_parts=tuple(part.type for part in request.attachments),
                # 고리의 위끝은 tool_loop 몫이다(DryRunEstimate 의 독스트링).
                schema_tokens=0,
                max_attempts=1,
                worst_case_usd=step_bounds[0],
            ),
            fallback_models=(),
            warnings=tuple(warnings),
            tool_loop=ToolLoopEstimate(
                max_steps=request.max_steps,
                step_upper_bounds_usd=step_bounds,
                loop_upper_bound_usd=round_usd(sum(step_bounds) + hosted_usd),
                max_provider_calls=request.max_steps * (1 + retries),
                unestimated=tuple(unestimated),
            ),
        )

    def _prepare_tools(self, request: ToolCallRequest) -> _ToolPrepared:
        """고리의 입력 검사와 거름(공급사 호출 전), 그리고 첫 걸음의 요청(앞 걸음 항목 없음)."""
        _check_tool_request(request)
        _check_tool_models(resolve_route(self._config, request.route), request.tools)
        plain = CallRequest[str](
            prompt=request.prompt,
            route=request.route,
            tags=request.tags,
            vars=request.vars,
            attachments=request.attachments,
            max_output_tokens=request.max_output_tokens,
            timeout_ms=request.timeout_ms,
            temperature=request.temperature,
        )
        prepared = self._prepare(plain)
        model = prepared.models[0]
        first = replace(
            self._build_provider_request(plain, prepared.rendered, model, None),
            tools=tuple(request.tools),
            tool_choice=request.tool_choice,
            parallel_tool_calls=request.parallel_tool_calls,
            max_hosted_calls=request.max_hosted_calls,
            system_placement=request.system_placement,
        )
        return _ToolPrepared(
            template=prepared.template,
            rendered=prepared.rendered,
            model=model,
            provider=prepared.providers[0],
            request=first,
        )

    def _prepare[T](self, request: CallRequest[T]) -> _Prepared:
        template = self._prompts.get(parse_prompt_id(request.prompt))
        rendered = render_prompt(template, request.vars)
        models = resolve_route(self._config, request.route)
        _check_temperature(request.temperature, models)
        providers = tuple(self._provider(model) for model in models)
        return _Prepared(template=template, rendered=rendered, models=models, providers=providers)

    def provider(self, name: str) -> Provider | None:
        """등록된 어댑터. 없으면 None. (모의 공급사에 답을 심으려는 쪽이 꺼내 쓴다)"""
        return self._providers.get(name)

    def _provider(self, model: ModelConfig) -> Provider:
        provider = self._providers.get(model.provider)
        if provider is None:
            raise LlmConfigError(f"모델 {model.key} 의 공급사 {model.provider} 어댑터가 등록되지 않았다")
        return provider

    def _build_provider_request[T](
        self,
        request: CallRequest[T],
        rendered: RenderedPrompt,
        model: ModelConfig,
        schema_json: dict[str, object] | None,
    ) -> ProviderRequest:
        answer_tokens = (
            min(DEFAULT_MAX_OUTPUT_TOKENS, model.max_output_tokens)
            if request.max_output_tokens is None
            else request.max_output_tokens
        )
        if answer_tokens > model.max_output_tokens:
            raise LlmConfigError(
                f"max_output_tokens {answer_tokens} 이 모델 {model.key} 의 상한 {model.max_output_tokens} 을 넘는다"
            )
        # 요청의 상한은 답의 상한이다. 추론 토큰이 출력 상한을 같이 쓰는 모델에는 설정의 여유분을 더해 보낸다
        # (모델 상한을 넘기지는 않는다).
        max_output_tokens = min(model.max_output_tokens, answer_tokens + (model.reasoning_output_reserve_tokens or 0))
        json_schema: JsonSchemaSpec | None = None
        if schema_json is not None and model.structured_output:
            json_schema = JsonSchemaSpec(name=request.schema_name, schema=to_strict_json_schema(schema_json))
        return ProviderRequest(
            api_model_id=model.api_model_id,
            system=rendered.system,
            # 첨부(PDF·그림)가 글보다 앞에 간다.
            user=(*request.attachments, TextPart(text=rendered.user)),
            max_output_tokens=max_output_tokens,
            json_schema=json_schema,
            temperature=request.temperature,
        )

    def _attempt_model[T](
        self,
        state: _CallState,
        *,
        model: ModelConfig,
        provider: Provider,
        provider_request: ProviderRequest,
        rendered: RenderedPrompt,
        timeout_ms: float,
        adapter: TypeAdapter[T] | None,
        tools_expected: bool,
        tool_step: int | None = None,
        loop_limit_usd: float | None = None,
    ) -> _Answered[T] | _Exhausted:
        """공급사 호출 한 번과, 재시도 가능한 공급사 오류일 때 같은 모델을 다시 부르는 고리(`call` 과 `call_tools` 가
        같이 쓴다). 다시 부를 때마다 상한을 다시 보고, 어댑터(호출 간격 조절 포함)를 그대로 지나고, 기록을 한 줄 남긴다.

        tools_expected  도구를 준 고리의 걸음인지. 도구 호출 답은 고리면 `success`, 아니면(`call`) `provider_error`.
        tool_step       고리의 걸음 번호(시도에만 붙는다).
        loop_limit_usd  고리 한 번의 상한(`ToolCallRequest.max_cost_usd`). 이 호출의 지금까지 비용이 이 값 이상이면
                        막는다.
        """
        request_json = provider_request.to_json()
        request_hash = sha256_json(request_json)
        retry_policy = self._provider_retry.get(model.provider, NO_RETRY)
        retry: _RetryTrace | None = None
        count_done = budget_done = 0  # 이 모델의 횟수·예산 갈래 재시도 수(retry.py)
        while True:
            exhausted = self.budget.check(state.tags)
            if exhausted is not None:
                self._write(
                    state,
                    request_json,
                    request_hash,
                    logged_model=None,
                    kind="budget_exceeded",
                    attempt=len(state.attempts),
                    retry=retry,
                )
                over = BudgetExceeded(
                    limit_usd=exhausted.limit.limit_usd,
                    spent_usd=exhausted.spent_usd,
                    scope=exhausted.limit.scope,
                    meta=state.meta(),
                )
                return _Exhausted(failure=over, source="guard")
            spent = state.total_cost_usd()
            if loop_limit_usd is not None and spent >= loop_limit_usd:
                self._write(
                    state,
                    request_json,
                    request_hash,
                    logged_model=None,
                    kind="budget_exceeded",
                    attempt=len(state.attempts),
                    retry=retry,
                )
                over = BudgetExceeded(
                    limit_usd=loop_limit_usd,
                    spent_usd=spent,
                    scope=Scope(tenant=state.tags.tenant, module=state.tags.module),
                    meta=state.meta(),
                )
                return _Exhausted(failure=over, source="loop")

            started = self._now()
            try:
                response = _invoke(provider, provider_request, timeout_ms)
            except BaseException as error:
                if soft_deadline_in(error) is not None:
                    # 나간 요청이 장부·상한에 남게 그 시도의 줄 하나(LH2 Q8). 그 밖의 BaseException 은 BASE 그대로.
                    # 줄 쓰기가 던져도 올라가는 것은 소프트 제한이다(LH3 Q4 — 실행기가 그것으로 다시 넣기를 가른다).
                    try:
                        self._write(
                            state,
                            request_json,
                            request_hash,
                            logged_model=model,
                            kind="timeout",
                            duration_ms=self._now() - started,
                            retry=retry,
                            attempt=len(state.attempts),
                            cost_bound_usd=self._worst_once_usd(request_json, provider_request, model),
                        )
                    except Exception as write_error:
                        logger.warning("LLM 소프트 제한 뒤 기록 실패 %s", type(write_error).__name__)
                raise
            duration_ms = self._now() - started

            usage = None if isinstance(response, ProviderError | ProviderTimeout) else response.usage
            cost_usd = None if usage is None else _cost_usd(response, usage, model)
            cost_bound_usd = (
                self._worst_once_usd(request_json, provider_request, model) if _maybe_billed(response) else None
            )
            if usage is not None:
                _add_warnings(state.warnings, _usage_warnings(rendered, usage))

            validated: _Valid[T] | _Invalid | None = None
            kind: AttemptKind
            if isinstance(response, Completed):
                validated = _validate(adapter, response.text)
                kind = "success" if isinstance(validated, _Valid) else "schema_mismatch"
            elif isinstance(response, ToolCallsRequested):
                # 고리에서는 공급사 호출의 성공이다. 도구를 주지 않은 호출(`call`)이면 재시도 불가 공급사 오류로 적는다
                # (사용량·비용은 그대로).
                kind = "success" if tools_expected else "provider_error"
            elif isinstance(response, ProviderError):
                kind = "provider_error"
            else:
                kind = response.kind
            state.attempts.append(
                Attempt(
                    provider=provider.name,
                    model=model.key,
                    kind=kind,
                    usage=usage,
                    cost_usd=cost_usd,
                    duration_ms=duration_ms,
                    provider_retry=None if retry is None else retry.provider_retry,
                    tool_step=tool_step,
                )
            )
            self._write(
                state,
                request_json,
                request_hash,
                logged_model=model,
                kind=kind,
                usage=usage,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                response_text=None if isinstance(response, ProviderError | ProviderTimeout) else response.text,
                response_model_id=None if isinstance(response, ProviderError | ProviderTimeout) else response.model_id,
                error_status=response.status
                if isinstance(response, ProviderError)
                else None
                if isinstance(response, ToolCallsRequested) and not tools_expected
                else MISSING,
                retry_after_ms=response.retry_after_ms if isinstance(response, ProviderError) else None,
                retry=retry,
                attempt=len(state.attempts) - 1,
                cost_bound_usd=cost_bound_usd,
                error_kind=response.error_kind if isinstance(response, ProviderError) else None,
            )

            if not isinstance(response, ProviderError):
                return _Answered(response=response, validated=validated)
            decision = next_retry(
                retry_policy,
                response,
                maybe_billed=_maybe_billed(response),
                count_done=count_done,
                budget_done=budget_done,
                waited_ms=state.budget_waited_ms,
                jitter=self._jitter,
            )
            if decision is None:
                return _Answered(response=response, validated=validated)
            if decision.branch == "budget":
                budget_done += 1
                state.budget_waited_ms += decision.wait_ms
            else:
                count_done += 1
            self._sleep(decision.wait_ms)
            retry = _RetryTrace(
                provider_retry=count_done + budget_done,
                previous_error_status=response.status,
                retry_wait_ms=decision.wait_ms,
            )

    def _write(
        self,
        state: _CallState,
        request_json: dict[str, object],
        request_hash: str,
        *,
        logged_model: ModelConfig | None,
        kind: LlmResultKind,
        usage: Usage | None = None,
        cost_usd: float | None = None,
        duration_ms: float = 0,
        response_text: str | None = None,
        response_model_id: str | None = None,
        error_status: int | Missing | None = MISSING,
        retry_after_ms: int | None = None,
        retry: _RetryTrace | None = None,
        attempt: int,
        cost_bound_usd: float | None = None,
        error_kind: str | None = None,
    ) -> None:
        self._log.record(
            CallRecord(
                ts=_iso(self._now()),
                call_id=state.call_id,
                attempt=attempt,
                provider=None if logged_model is None else logged_model.provider,
                model=None if logged_model is None else logged_model.key,
                api_model_id=None if logged_model is None else logged_model.api_model_id,
                response_model_id=response_model_id,
                prompt_id=state.template.id,
                prompt_version=state.template.version,
                template_hash=state.template.hash,
                request_hash=request_hash,
                input_tokens=None if usage is None else usage.input_tokens,
                output_tokens=None if usage is None else usage.output_tokens,
                cache_read_tokens=None if usage is None else usage.cache_read_tokens,
                cache_write_tokens=None if usage is None else usage.cache_write_tokens,
                thinking_tokens=None if usage is None else usage.thinking_tokens,
                error_status=error_status,
                retry_after_ms=retry_after_ms,
                provider_retry=None if retry is None else retry.provider_retry,
                previous_error_status=MISSING if retry is None else retry.previous_error_status,
                retry_wait_ms=None if retry is None else retry.retry_wait_ms,
                cost_usd=cost_usd,
                duration_ms=duration_ms,
                result_kind=kind,
                tenant=state.tags.tenant,
                module=state.tags.module,
                warnings=tuple(warning.code for warning in state.warnings),
                body=RecordBody(request=request_json, response_text=response_text) if self._store_bodies else None,
                cost_bound_usd=cost_bound_usd,
                error_kind=error_kind,
            )
        )

    def _worst_once_usd(
        self, request_json: dict[str, object], provider_request: ProviderRequest, model: ModelConfig
    ) -> float:
        """실패 시도의 한 번 최악(LH2 Q4): 요청 JSON(도구 정의·앞 걸음 turns 포함, 첨부 base64 는 뺌 — 어림 밖)의 토큰
        어림을 입력으로, 출력 상한을 출력으로, 그 모델 단가로. 캐시 할인은 보지 않는다(보수). 캐시 지정 몫은 쓰기 단가가
        더 크면 그것으로(LH3 Q9 — `_bound_usd`). web_search 를 실었으면 건당 요금 × max_hosted_calls(없으면 1 —
        과소, 머리말의 받아들임. LH3 Q3)."""
        user = cast("list[dict[str, object]]", request_json.get("user", []))
        body = {**request_json, "user": [{k: v for k, v in part.items() if k != "base64"} for part in user]}
        input_tokens = self._estimator.estimate(json.dumps(body, ensure_ascii=False, separators=(",", ":")))
        worst = Usage(
            input_tokens=input_tokens,
            output_tokens=provider_request.max_output_tokens,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )
        hosted = model.hosted_tool_pricing
        searches = 0
        if hosted is not None and any(isinstance(tool, WebSearchTool) for tool in provider_request.tools):
            searches = 1 if provider_request.max_hosted_calls is None else provider_request.max_hosted_calls
        return _bound_usd(worst, self._cached_tokens(provider_request), model.pricing, searches, hosted)

    def _cached_tokens(self, provider_request: ProviderRequest) -> int:
        """공급사 요청의 캐시 지정 자리(SystemSegment.cache)의 토큰 어림(LH3 Q8 — 쓰기 할증의 몫)."""
        cacheable = [segment.text for segment in provider_request.system if segment.cache]
        return self._estimator.estimate("\n".join(cacheable)) if cacheable else 0

    def _cacheable_tokens(self, rendered: RenderedPrompt) -> int:
        cacheable = [segment.text for segment in rendered.system if segment.cache]
        return self._estimator.estimate("\n".join(cacheable)) if cacheable else 0

    def _cache_warnings(self, rendered: RenderedPrompt, model: ModelConfig) -> list[LlmWarning]:
        if not any(segment.cache for segment in rendered.system):
            return []
        tokens = self._cacheable_tokens(rendered)
        if tokens >= model.min_cache_tokens:
            return []
        return [
            LlmWarning(
                code="cache_below_minimum",
                message=f"캐시 대상 앞부분이 약 {tokens}토큰(어림)으로 모델 {model.key} 의 최소 "
                f"{model.min_cache_tokens}토큰에 못 미친다. 캐시가 걸리지 않는다.",
            )
        ]


def _iso(ms: float) -> str:
    """JS 의 `toISOString()` 과 같은 꼴: 2026-10-08T01:02:03.456Z"""
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _check_temperature(temperature: object, models: Sequence[ModelConfig]) -> None:
    """값을 주면 범위와, 경로의 모델 전부(주·대체)가 받는지를 공급사 호출 전에 본다. None 이면 아무것도 보지 않는다."""
    if temperature is None:
        return
    if isinstance(temperature, bool) or not isinstance(temperature, int | float) or not math.isfinite(temperature):
        raise LlmConfigError(f"temperature 는 수여야 한다: {temperature!r}")
    if not TEMPERATURE_MIN <= temperature <= TEMPERATURE_MAX:
        raise LlmConfigError(f"temperature {temperature} 이 범위 {TEMPERATURE_MIN}~{TEMPERATURE_MAX} 밖이다")
    for model in models:
        if model.provider in TEMPERATURE_UNSUPPORTED_PROVIDERS or model.api_model_id in TEMPERATURE_UNSUPPORTED_MODELS:
            raise LlmConfigError(
                f"모델 {model.key}({model.provider}/{model.api_model_id}) 은 temperature 를 받지 않는다. "
                "temperature 를 넘기려면 경로의 모델이 전부 받는 모델이어야 한다"
            )


def _check_tool_request(request: ToolCallRequest) -> None:
    max_steps = cast("object", request.max_steps)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise LlmConfigError(f"max_steps 는 1 이상의 정수여야 한다: {max_steps!r}")
    if not request.tools:
        raise LlmConfigError("도구 호출 고리에는 도구가 하나 이상 있어야 한다")
    for tool in cast("Sequence[object]", request.tools):
        if not isinstance(tool, FunctionTool | WebSearchTool):
            raise LlmConfigError(f"도구는 FunctionTool 이나 WebSearchTool 이어야 한다: {type(tool).__name__}")
    max_cost = cast("object", request.max_cost_usd)
    if max_cost is not None and (
        isinstance(max_cost, bool)
        or not isinstance(max_cost, int | float)
        or not math.isfinite(max_cost)
        or max_cost <= 0
    ):
        raise LlmConfigError(f"max_cost_usd 는 0 보다 큰 수여야 한다: {max_cost!r}")
    hosted = cast("object", request.max_hosted_calls)
    if hosted is not None and (isinstance(hosted, bool) or not isinstance(hosted, int) or hosted < 1):
        raise LlmConfigError(f"max_hosted_calls 는 1 이상의 정수여야 한다: {hosted!r}")
    tool_choice = cast("object", request.tool_choice)
    if tool_choice not in (None, "auto", "required", "none"):
        raise LlmConfigError(f"tool_choice 는 auto·required·none 중 하나여야 한다: {tool_choice!r}")
    placement = cast("object", request.system_placement)
    if placement not in ("instructions", "input_message"):
        raise LlmConfigError(f"system_placement 는 instructions·input_message 중 하나여야 한다: {placement!r}")


def _check_tool_models(models: Sequence[ModelConfig], tools: Sequence[Tool]) -> None:
    """고리를 지나는 경로인지 공급사 호출 전에 본다(`TOOL_PROVIDERS`·`TOOL_MODELS` 의 머리)."""
    if len(models) != 1:
        raise LlmConfigError(
            f"도구 호출 고리의 경로는 모델 하나여야 한다(대체 없음): {[model.key for model in models]}"
        )
    (model,) = models
    if model.provider not in TOOL_PROVIDERS:
        raise LlmConfigError(f"공급사 {model.provider} 는 도구 호출 고리를 지나지 않는다(TOOL_PROVIDERS)")
    if model.provider == "openai" and model.api_model_id not in TOOL_MODELS:
        raise LlmConfigError(
            f"모델 {model.key}({model.api_model_id}) 은 도구 호출 고리의 허용 목록(TOOL_MODELS) 밖이다"
        )
    if any(isinstance(tool, WebSearchTool) for tool in tools) and model.hosted_tool_pricing is None:
        # 건당 요금이 없으면 web_search 건수가 비용에서 조용히 빠진다(compute_cost_usd 는 요금이 없으면 건수를 안 본다).
        raise LlmConfigError(f"모델 {model.key} 에 web_search 건당 요금(hostedToolPricing)이 없다")


def _tools_json(body: object, request: ProviderRequest) -> str:
    """어댑터가 싣는 도구 정의의 JSON 글자(dry-run 의 입력 어림용). 본문에 "tools" 칸이 없으면 중립 꼴로."""
    tools = cast("dict[str, object]", body).get("tools") if isinstance(body, dict) else None
    if tools is None:
        tools = request.to_json().get("tools", [])
    return json.dumps(tools, ensure_ascii=False, separators=(",", ":"))


def _cost_usd(response: ProviderResponse, usage: Usage, model: ModelConfig) -> float:
    """토큰 비용 + 공급사가 실행한 도구(web_search)의 건수 × 건당 요금. 건수가 0 이면 토큰 비용 그대로다.

    잘림·거부도 그 응답 안에서 이미 돈 검색은 과금되니 센다(QC2 `MARC-ISSUE-349`)."""
    hosted_calls = (
        response.hosted_calls if isinstance(response, Completed | ToolCallsRequested | Truncated | Refusal) else 0
    )
    return compute_cost_usd(usage, model.pricing, hosted_calls, model.hosted_tool_pricing)


def _maybe_billed(response: ProviderResponse) -> bool:
    """공급사가 과금했을 수 있는 실패인가(LH2 Q4): 시간 초과 · 나간 요청의 상태 없는 오류 · 2xx 인 오류. HTTP 상태로
    거절된 4xx·5xx 와 나가지 않은 요청(sent=False)은 아니다(머리말의 ★ — 추정)."""
    if isinstance(response, ProviderTimeout):
        return True
    if not isinstance(response, ProviderError) or not response.sent:
        return False
    return response.status is None or 200 <= response.status < 300


def _bound_usd(
    usage: Usage, cached_tokens: int, pricing: Pricing, hosted_calls: int = 0, hosted: HostedToolPricing | None = None
) -> float:
    """위끝 어림(LH3 Q8·Q9): 입력 가운데 캐시 지정 몫(`cached_tokens`, 입력 합을 넘지 않게)을 캐시 쓰기로 센 값과
    전부 평 입력으로 센 값 가운데 큰 쪽. 그래서 쓰기 단가가 입력보다 클 때만 오르고 위끝은 줄지 않는다. 단가 견줌은
    `compute_cost_usd` 가 실제로 고른 구간(장문 포함)에서다 — 캐시 몫도 입력 합에 들어 구간은 둘이 같다."""
    cached = min(cached_tokens, usage.input_tokens)
    plain = compute_cost_usd(usage, pricing, hosted_calls, hosted)
    if cached == 0:
        return plain
    split = replace(
        usage, input_tokens=usage.input_tokens - cached, cache_write_tokens=(usage.cache_write_tokens or 0) + cached
    )
    return max(plain, compute_cost_usd(split, pricing, hosted_calls, hosted))


def _should_fallback(failure: ProviderFailed | TimedOut) -> bool:
    """시간 초과·재시도 가능한 공급사 오류·크레딧 소진(LB1 Q6 — 다음 모델은 다른 공급사·키일 수 있다)이면 다음
    모델로."""
    return isinstance(failure, TimedOut) or failure.retryable or failure.error_kind == "quota_exhausted"


def _add_warnings(target: list[LlmWarning], incoming: Sequence[LlmWarning]) -> None:
    for warning in incoming:
        if warning not in target:
            target.append(warning)


def _usage_warnings(rendered: RenderedPrompt, usage: Usage) -> list[LlmWarning]:
    if not any(segment.cache for segment in rendered.system):
        return []
    if usage.cache_read_tokens is None or usage.cache_write_tokens is None:
        return [
            LlmWarning(
                code="usage_unreported",
                message="공급사가 캐시 토큰 수를 보고하지 않았다. 비용은 캐시 토큰을 0 으로 두고 계산했다.",
            )
        ]
    if usage.cache_read_tokens + usage.cache_write_tokens == 0:
        return [
            LlmWarning(
                code="cache_not_applied", message="캐시 대상으로 표시했지만 응답의 캐시 읽기·쓰기 토큰이 0 이다."
            )
        ]
    return []


def _validate[T](adapter: TypeAdapter[T] | None, text: str) -> _Valid[T] | _Invalid:
    if adapter is None:
        # 스키마가 없는 호출의 T 는 기본값 str 이다.
        return _Valid(data=cast("T", text))
    try:
        json.loads(text)
    except json.JSONDecodeError as error:
        return _Invalid(issues=(SchemaIssue(path="", message=f"JSON 으로 읽을 수 없다: {error.msg}"),))
    try:
        # strict: 글자 "1" 을 수 1 로 바꿔 읽는 식의 느슨한 변환을 하지 않는다(JSON 의 타입 그대로).
        return _Valid(data=adapter.validate_json(text, strict=True))
    except ValidationError as error:
        return _Invalid(
            issues=tuple(
                SchemaIssue(path=".".join(str(part) for part in issue["loc"]), message=issue["msg"])
                for issue in error.errors()
            )
        )


def _invoke(provider: Provider, request: ProviderRequest, timeout_ms: float) -> ProviderResponse:
    try:
        return provider.invoke(request, InvokeOptions(timeout_ms=timeout_ms))
    except Exception as error:
        if (deadline := soft_deadline_in(error)) is not None:
            raise deadline from None  # Celery 소프트 제한은 공급사 오류로 바꾸지 않는다(LH2)
        # 어댑터는 던지지 않기로 했지만, 던졌다면 삼키지 않고 공급사 오류로 돌린다.
        return ProviderError(status=None, retryable=False, message=f"어댑터가 예외를 던졌다: {redact_keys(str(error))}")
