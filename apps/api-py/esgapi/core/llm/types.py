"""호출 층의 낱말: 꼬리표, 사용량, 공급사에 넘기는 중립 요청, 공급사의 답(6갈래), 호출 결과(7갈래),
도구 호출 고리의 낱말과 결과(3갈래).

부재는 갈래로 쓴다. 결과를 빈 값으로 삼키지 않는다: 갈래마다 frozen dataclass 하나이고 `kind` 가 갈래의 이름이다.
받는 쪽은 `match result:` 나 `isinstance` 로 가른다.

「있을 때만 있는 칸」(공급사가 보고했을 때만 있는 `thinking_tokens`, `retry_after_ms`)은 `None` 으로 접는다.
JSON 으로 낼 때는 그 칸을 내지 않는다(esg-lab 의 기록과 같은 꼴). JSON 의 열쇠는 esg-lab 과 같은 camelCase 다.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

# ── 꼬리표 ──


@dataclass(frozen=True)
class Tags:
    """호출 기록과 비용 집계에 쓰는 꼬리표."""

    tenant: str
    module: str


@dataclass(frozen=True)
class Scope:
    """상한이 걸리는 범위. 적은 꼬리표가 모두 맞는 호출이 든다. 둘 다 비우면 모든 호출이다."""

    tenant: str | None = None
    module: str | None = None

    def matches(self, tenant: str, module: str) -> bool:
        return (self.tenant is None or self.tenant == tenant) and (self.module is None or self.module == module)

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {}
        if self.tenant is not None:
            out["tenant"] = self.tenant
        if self.module is not None:
            out["module"] = self.module
        return out


# ── 사용량 ──


@dataclass(frozen=True)
class Usage:
    """토큰 사용량. `input_tokens` 는 캐시에 걸리지 않은 입력만 센다.

    공급사가 보고하지 않은 캐시 항목은 0 이 아니라 None 이다.
    `thinking_tokens` 는 생각·추론 토큰 수다. `output_tokens` 에 이미 든 몫이고 따로 과금하지 않는다.
    공급사가 보고했을 때만 있다(None = 보고하지 않음. 0 은 「0 이라고 보고함」이다).
    """

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    thinking_tokens: int | None = None

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {
            "inputTokens": self.input_tokens,
            "outputTokens": self.output_tokens,
            "cacheReadTokens": self.cache_read_tokens,
            "cacheWriteTokens": self.cache_write_tokens,
        }
        if self.thinking_tokens is not None:
            out["thinkingTokens"] = self.thinking_tokens
        return out


# ── 공급사에 넘기는 중립 요청 ──


@dataclass(frozen=True)
class SystemSegment:
    """시스템 지침 한 덩어리. `cache` 는 고정 앞부분(지침, 용어집)을 캐시 대상으로 표시한다."""

    text: str
    cache: bool


@dataclass(frozen=True)
class TextPart:
    text: str
    type: Literal["text"] = "text"


@dataclass(frozen=True)
class PdfPart:
    base64: str
    filename: str
    type: Literal["pdf"] = "pdf"


ImageMediaType = Literal["image/png", "image/jpeg", "image/webp", "image/gif"]


@dataclass(frozen=True)
class ImagePart:
    base64: str
    media_type: ImageMediaType
    type: Literal["image"] = "image"


type UserPart = TextPart | PdfPart | ImagePart
type Attachment = PdfPart | ImagePart


@dataclass(frozen=True)
class JsonSchemaSpec:
    name: str
    schema: dict[str, object]


# ── 도구 (밴드 TL1 `MARC-TICK-180`) ──
# core 는 도구의 낱말과 자리만 둔다. 도구의 몸(실행 함수)·스키마 상수·프롬프트는 부르는 모듈의 것이다.


@dataclass(frozen=True)
class FunctionTool:
    """호출 측(우리 서버)이 실행하는 도구. `parameters` 는 JSON 스키마.

    `strict` 는 None 이면 싣지 않는다(공급사 기본).
    """

    name: str
    description: str
    parameters: Mapping[str, object]
    strict: bool | None = None
    type: Literal["function"] = "function"


@dataclass(frozen=True)
class ApproximateLocation:
    """웹 검색의 대략 위치(OpenAI `user_location` 의 `type: "approximate"`). `country` 는 ISO 3166-1 두 글자."""

    country: str
    type: Literal["approximate"] = "approximate"


@dataclass(frozen=True)
class WebSearchTool:
    """공급사가 실행하는 내장 웹 검색(OpenAI `web_search`). 호출 수는 `hosted_calls` 로 세어 건당 요금이 붙는다.

    `user_location` 은 None 이면 싣지 않는다(공급사 기본 — 미국. 요청 해시도 그대로다).
    """

    search_context_size: Literal["low", "medium", "high"] = "medium"
    user_location: ApproximateLocation | None = None
    type: Literal["web_search"] = "web_search"


type Tool = FunctionTool | WebSearchTool


@dataclass(frozen=True)
class FunctionCall:
    """모델이 낸 도구 호출 하나. `arguments` 는 JSON 글자 그대로다(파싱은 실행 함수 몫).

    공급사의 항목 id(`fc_…`)를 두지 않는다: 다시 실을 때 싣지 않는다(공급사 쪽 보관 0, `MARC-ENT-301`).
    """

    call_id: str
    name: str
    arguments: str
    type: Literal["function_call"] = "function_call"


@dataclass(frozen=True)
class AssistantText:
    """모델이 도구 호출과 함께 낸 글 한 덩어리(공급사의 message 항목 하나)."""

    text: str
    type: Literal["assistant_text"] = "assistant_text"


@dataclass(frozen=True)
class ToolOutput:
    """도구 호출 하나의 결과 글자. 실행 함수가 돌려준 글자를 바꾸지 않고 싣는다."""

    call_id: str
    output: str
    type: Literal["tool_output"] = "tool_output"


# 모델이 낸 항목. ★ 추론 모델의 추론 항목(암호화된 내용)을 다시 실어야 하는 날에는 이 합에 갈래를 하나 더한다
# (`Turn`·어댑터의 해석과 조립·`turn_json` 이 같이 는다). 지금은 비추론 모델만 고리를 지난다(client.py 의 TOOL_MODELS).
type ModelItem = FunctionCall | AssistantText
type Turn = ModelItem | ToolOutput


@dataclass(frozen=True)
class UrlCitation:
    """답의 글에 붙은 출처 하나. 위치(`start_index`·`end_index`)는 공급사가 준 그대로다(그 글 덩어리 안의 위치)."""

    url: str
    title: str
    start_index: int
    end_index: int


SystemPlacement = Literal["instructions", "input_message"]
ToolChoice = Literal["auto", "required", "none"]


@dataclass(frozen=True)
class ProviderRequest:
    """공급사에 넘기는 중립 요청. 공급사 고유 형식으로 바꾸는 일은 어댑터가 한다.

    도구 칸(`tools` 부터 끝까지)은 도구 호출 고리(`LlmClient.call_tools`)만 채운다. 기본값이면 어댑터가 싣지 않는다.
      tools              실을 도구. 차례 그대로 싣는다
      tool_choice        None 이면 싣지 않는다(공급사 기본)
      parallel_tool_calls  None 이면 싣지 않는다
      max_hosted_calls   공급사가 실행하는 도구(web_search)의 응답 하나당 호출 상한(OpenAI `max_tool_calls`)
      system_placement   "instructions" 면 system 을 공급사의 지침 칸에, "input_message" 면 입력 맨 앞의 system 메시지로
      turns              앞 걸음의 항목(모델이 낸 것과 도구 결과). user 뒤에 차례대로 다시 싣는다
    """

    api_model_id: str
    system: tuple[SystemSegment, ...]
    user: tuple[UserPart, ...]
    max_output_tokens: int
    json_schema: JsonSchemaSpec | None = None
    # None 이면 공급사에 싣지 않는다(공급사 기본값). 받는 모델인지와 범위는 호출 층(client.py)이 미리 거른다.
    temperature: float | None = None
    tools: tuple[Tool, ...] = ()
    tool_choice: ToolChoice | None = None
    parallel_tool_calls: bool | None = None
    max_hosted_calls: int | None = None
    system_placement: SystemPlacement = "instructions"
    turns: tuple[Turn, ...] = ()

    @property
    def uses_tools(self) -> bool:
        """도구 칸 하나라도 기본값이 아니면 참. 도구를 모르는 어댑터는 이것이 참이면 조용히 빼지 않고 거부한다."""
        return bool(
            self.tools
            or self.turns
            or self.tool_choice is not None
            or self.parallel_tool_calls is not None
            or self.max_hosted_calls is not None
            or self.system_placement != "instructions"
        )

    def to_json(self) -> dict[str, object]:
        """요청 해시와 기록의 본문(`store_bodies`)에 쓰는 꼴. 열쇠는 esg-lab 의 ProviderRequest 와 같다.

        `temperature` 와 도구 칸은 기본값이 아닐 때만 싣는다: 값을 주지 않은 요청의 해시와 기록은 이 칸들이 생기기
        전과 글자째 같다.
        """
        out: dict[str, object] = {
            "apiModelId": self.api_model_id,
            "system": [{"text": segment.text, "cache": segment.cache} for segment in self.system],
            "user": [user_part_json(part) for part in self.user],
            "maxOutputTokens": self.max_output_tokens,
        }
        if self.json_schema is not None:
            out["jsonSchema"] = {"name": self.json_schema.name, "schema": self.json_schema.schema}
        if self.temperature is not None:
            out["temperature"] = self.temperature
        if self.tools:
            out["tools"] = [tool_json(tool) for tool in self.tools]
        if self.tool_choice is not None:
            out["toolChoice"] = self.tool_choice
        if self.parallel_tool_calls is not None:
            out["parallelToolCalls"] = self.parallel_tool_calls
        if self.max_hosted_calls is not None:
            out["maxHostedCalls"] = self.max_hosted_calls
        if self.system_placement != "instructions":
            out["systemPlacement"] = self.system_placement
        if self.turns:
            out["turns"] = [turn_json(turn) for turn in self.turns]
        return out


def tool_json(tool: Tool) -> dict[str, object]:
    match tool:
        case FunctionTool():
            out: dict[str, object] = {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters),
            }
            if tool.strict is not None:
                out["strict"] = tool.strict
            return out
        case WebSearchTool():
            out = {"type": "web_search", "searchContextSize": tool.search_context_size}
            if tool.user_location is not None:
                out["userLocation"] = {"type": tool.user_location.type, "country": tool.user_location.country}
            return out


def turn_json(turn: Turn) -> dict[str, object]:
    match turn:
        case FunctionCall():
            return {"type": "function_call", "callId": turn.call_id, "name": turn.name, "arguments": turn.arguments}
        case AssistantText():
            return {"type": "assistant_text", "text": turn.text}
        case ToolOutput():
            return {"type": "tool_output", "callId": turn.call_id, "output": turn.output}


def user_part_json(part: UserPart) -> dict[str, object]:
    match part:
        case TextPart():
            return {"type": "text", "text": part.text}
        case PdfPart():
            return {"type": "pdf", "base64": part.base64, "filename": part.filename}
        case ImagePart():
            return {"type": "image", "base64": part.base64, "mediaType": part.media_type}


@dataclass(frozen=True)
class InvokeOptions:
    """공급사 호출 한 번의 시간 제한(ms). 동기 호출이라 중단 신호가 없다: 어댑터가 SDK 의 timeout 으로 건다."""

    timeout_ms: float


# ── 공급사의 답: 6갈래 ──
# `model_id` 는 공급사가 응답에 적은 모델 ID 다. 요청한 ID 와 다를 수 있어(날짜 붙은 스냅숏) 기록에 따로 남긴다.


@dataclass(frozen=True)
class Completed:
    """`citations` 는 답의 글에 붙은 출처(차례대로, 겹침 그대로), `hosted_calls` 는 공급사가 실행한 도구 호출 수다."""

    text: str
    usage: Usage
    model_id: str | None = None
    citations: tuple[UrlCitation, ...] = ()
    hosted_calls: int = 0
    kind: Literal["completed"] = "completed"


@dataclass(frozen=True)
class ToolCallsRequested:
    """모델이 우리 쪽 도구를 불러 달라고 했다(끝나지 않은 답). `output` 은 응답의 항목 차례 그대로다.

    도구를 주지 않은 호출(`LlmClient.call`)이 이것을 받으면 성공으로 접지 않고 재시도 불가 공급사 오류로 돌린다.
    """

    output: tuple[ModelItem, ...]
    usage: Usage
    model_id: str | None = None
    hosted_calls: int = 0
    kind: Literal["tool_calls"] = "tool_calls"

    @property
    def calls(self) -> tuple[FunctionCall, ...]:
        return tuple(item for item in self.output if isinstance(item, FunctionCall))

    @property
    def text(self) -> str:
        return "".join(item.text for item in self.output if isinstance(item, AssistantText))


@dataclass(frozen=True)
class Refusal:
    """`hosted_calls` 는 거부 전에 공급사가 이미 실행한 도구 호출 수다(과금된다 — 장부에 센다)."""

    text: str
    category: str | None
    usage: Usage
    model_id: str | None = None
    hosted_calls: int = 0
    kind: Literal["refusal"] = "refusal"


@dataclass(frozen=True)
class Truncated:
    """`hosted_calls` 는 잘리기 전에 공급사가 이미 실행한 도구 호출 수다(과금된다 — 장부에 센다)."""

    text: str
    usage: Usage
    model_id: str | None = None
    hosted_calls: int = 0
    kind: Literal["truncated"] = "truncated"


# 공급사 오류의 이름(LB1 — 닫힌 낱말 여섯). 어댑터(providers/*.py)가 공식 문서의 상태·본문 코드로 가른다:
#   rate_limited     429 속도·토큰 한도(gemini 의 429 포함 — 일 한도도 여기, 가를 길이 없다)
#   quota_exhausted  크레딧·청구·지출 상한 소진(문서가 가르는 본문 코드·402 만). 기다려도 안 풀린다 — 재시도 불가
#   overloaded       공급사 과부하: anthropic 529·본문 type overloaded_error(HTTP 200 스트림 사건 포함), openai 503
#                    server_is_overloaded
#   server_error     그 밖 5xx(gemini 408 포함)
#   connection       상태 없는 연결 실패(SDK 의 APIConnectionError·httpx TransportError 갈래)
#   other            그 밖 모든 공급사 오류(4xx·어댑터 거절·모양 틀림·어댑터 예외). 이름을 주지 않은 오류의 기본값
# 같은 모델 재시도의 갈래(retry.py)와 결과 값·기록 줄의 이름(`errorKind`)이 이것을 쓴다. result_kind 는 그대로다.
type ErrorKind = Literal["rate_limited", "quota_exhausted", "overloaded", "server_error", "connection", "other"]


@dataclass(frozen=True)
class ProviderError:
    """`retry_after_ms` 는 공급사가 알려 준 「이만큼 뒤에 다시」(ms)다. 알려 줬을 때만 있다.

    `sent` 는 요청이 공급사로 나갔을 수 있는가(LH2 — 실패 시도의 보수 어림, client.py). 어댑터가 부르기 전에 거절했거나
    연결부터 실패했으면(조상 이름 ConnectError) False, 그 밖은 True(모르면 나갔다고 본다). 같음 비교에 들지 않는다.
    `error_kind` 는 오류의 이름(`ErrorKind` — LB1). 주지 않으면 "other"(같은 모델 재시도는 횟수 갈래 — retry.py).
    """

    status: int | None
    retryable: bool
    message: str
    retry_after_ms: int | None = None
    kind: Literal["error"] = "error"
    sent: bool = field(default=True, compare=False)
    error_kind: ErrorKind = "other"


@dataclass(frozen=True)
class ProviderTimeout:
    message: str
    kind: Literal["timeout"] = "timeout"


type ProviderResponse = Completed | ToolCallsRequested | Refusal | Truncated | ProviderError | ProviderTimeout

# ── 경고, 시도, 호출의 곁 정보 ──

WarningCode = Literal[
    "cache_below_minimum",
    "cache_not_applied",
    "usage_unreported",
    # 도구 호출 고리(TL1)의 dry-run 이 내는 둘. 위끝에 들지 않는 몫이 있다는 알림이다.
    "tool_outputs_unestimated",
    "hosted_calls_unbounded",
]


@dataclass(frozen=True)
class LlmWarning:
    code: WarningCode
    message: str


AttemptKind = Literal["success", "schema_mismatch", "refusal", "truncated", "provider_error", "timeout"]
LlmResultKind = Literal[
    "success", "schema_mismatch", "refusal", "truncated", "provider_error", "timeout", "budget_exceeded"
]


@dataclass(frozen=True)
class Attempt:
    """공급사를 한 번 부른 기록. 재시도와 대체 호출마다 하나씩 생긴다.

    `provider_retry` 는 공급사 오류 뒤에 같은 모델을 다시 부른 시도일 때만 있다: 몇 번째 재시도인지(1부터).
    `tool_step` 은 도구 호출 고리의 시도일 때만 있다: 몇 번째 걸음인지(1부터). 기록 줄(DB)에는 가지 않는다.
    """

    provider: str
    model: str
    kind: AttemptKind
    usage: Usage | None
    cost_usd: float | None
    duration_ms: float
    provider_retry: int | None = None
    tool_step: int | None = None

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {
            "provider": self.provider,
            "model": self.model,
            "kind": self.kind,
            "usage": None if self.usage is None else self.usage.to_json(),
            "costUsd": self.cost_usd,
            "durationMs": self.duration_ms,
        }
        if self.provider_retry is not None:
            out["providerRetry"] = self.provider_retry
        if self.tool_step is not None:
            out["toolStep"] = self.tool_step
        return out


@dataclass(frozen=True)
class CallMeta:
    """`total_cost_usd` 는 모든 시도의 비용 합이다. 사용량을 못 받은 시도(오류, 시간 초과)는 빼고 더한다."""

    call_id: str
    prompt_id: str
    attempts: tuple[Attempt, ...]
    total_cost_usd: float
    warnings: tuple[LlmWarning, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "callId": self.call_id,
            "promptId": self.prompt_id,
            "attempts": [attempt.to_json() for attempt in self.attempts],
            "totalCostUsd": self.total_cost_usd,
            "warnings": [{"code": warning.code, "message": warning.message} for warning in self.warnings],
        }


@dataclass(frozen=True)
class SchemaIssue:
    path: str
    message: str


# ── 호출 결과: 7갈래 ──


@dataclass(frozen=True)
class Success[T]:
    data: T
    text: str
    meta: CallMeta
    kind: Literal["success"] = "success"


@dataclass(frozen=True)
class SchemaMismatch:
    issues: tuple[SchemaIssue, ...]
    raw_text: str
    meta: CallMeta
    kind: Literal["schema_mismatch"] = "schema_mismatch"


@dataclass(frozen=True)
class Refused:
    text: str
    category: str | None
    meta: CallMeta
    kind: Literal["refusal"] = "refusal"


@dataclass(frozen=True)
class CutOff:
    partial_text: str
    meta: CallMeta
    kind: Literal["truncated"] = "truncated"


@dataclass(frozen=True)
class ProviderFailed:
    """`error_kind`·`retry_after_ms`(LB1)는 마지막 공급사 오류의 이름과 「이만큼 뒤에 다시」(ms). 공급사 오류에서 온
    실패일 때만 있고(호출 층이 싣는다), 모듈이 직접 만든 실패·도구를 안 준 호출의 도구 답은 None — JSON 에 내지
    않는다."""

    status: int | None
    retryable: bool
    message: str
    meta: CallMeta
    kind: Literal["provider_error"] = "provider_error"
    error_kind: ErrorKind | None = None
    retry_after_ms: int | None = None


@dataclass(frozen=True)
class TimedOut:
    message: str
    meta: CallMeta
    kind: Literal["timeout"] = "timeout"


@dataclass(frozen=True)
class BudgetExceeded:
    limit_usd: float
    spent_usd: float
    scope: Scope
    meta: CallMeta
    kind: Literal["budget_exceeded"] = "budget_exceeded"


type LlmResult[T] = Success[T] | SchemaMismatch | Refused | CutOff | ProviderFailed | TimedOut | BudgetExceeded


def result_json[T](result: LlmResult[T], data: object) -> dict[str, object]:
    """결과를 JSON 으로 낼 꼴. `data` 는 부르는 쪽이 JSON 으로 낼 수 있게 바꿔 넘긴다(성공이 아니면 쓰지 않는다)."""
    meta = result.meta.to_json()
    match result:
        case Success():
            return {"kind": result.kind, "data": data, "text": result.text, "meta": meta}
        case SchemaMismatch():
            issues = [{"path": issue.path, "message": issue.message} for issue in result.issues]
            return {"kind": result.kind, "issues": issues, "rawText": result.raw_text, "meta": meta}
        case Refused():
            return {"kind": result.kind, "text": result.text, "category": result.category, "meta": meta}
        case CutOff():
            return {"kind": result.kind, "partialText": result.partial_text, "meta": meta}
        case ProviderFailed():
            failed: dict[str, object] = {
                "kind": result.kind,
                "status": result.status,
                "retryable": result.retryable,
                "message": result.message,
            }
            # 있을 때만(LB1) — 이름 없는 실패의 JSON 은 바이트 그대로다.
            if result.error_kind is not None:
                failed["errorKind"] = result.error_kind
            if result.retry_after_ms is not None:
                failed["retryAfterMs"] = result.retry_after_ms
            failed["meta"] = meta
            return failed
        case TimedOut():
            return {"kind": result.kind, "message": result.message, "meta": meta}
        case BudgetExceeded():
            return {
                "kind": result.kind,
                "limitUsd": result.limit_usd,
                "spentUsd": result.spent_usd,
                "scope": result.scope.to_json(),
                "meta": meta,
            }


# ── 도구 호출 고리의 결과: 3갈래 (밴드 TL1) ──

# 실행 함수: (도구 이름, 인자 JSON 글자) → 결과 글자. 모르는 이름·인자 틀림도 결과 글자로 돌려준다(던지지 않는다).
type ToolExecutor = Callable[[str, str], str]


@dataclass(frozen=True)
class ToolStep:
    """도구를 실행한 걸음 하나: 그 답의 호출(차례대로)과 실행 결과(같은 차례), 그 답에서 공급사가 실행한 호출 수."""

    calls: tuple[FunctionCall, ...]
    outputs: tuple[ToolOutput, ...]
    hosted_calls: int


@dataclass(frozen=True)
class ToolExecutorRaised:
    """실행 함수가 예외를 던졌다. 메시지는 싣지 않는다(고객 데이터가 섞일 수 있다): 도구 이름과 예외 클래스만."""

    name: str
    error_class: str
    kind: Literal["tool_executor_raised"] = "tool_executor_raised"


# 고리의 실패. 고리는 스키마를 받지 않아 SchemaMismatch 는 들지 않는다.
type ToolLoopFailure = Refused | CutOff | ProviderFailed | TimedOut | BudgetExceeded | ToolExecutorRaised


@dataclass(frozen=True)
class ToolLoopDone:
    """도구 호출이 없는 답으로 끝났다. `text`·`citations` 는 그 마지막 답의 것, `hosted_calls` 는 모든 걸음의 합이다."""

    text: str
    citations: tuple[UrlCitation, ...]
    hosted_calls: int
    steps: tuple[ToolStep, ...]
    meta: CallMeta
    kind: Literal["done"] = "done"


@dataclass(frozen=True)
class ToolLoopPartial:
    """걸음이 다했는데 마지막 답이 아직 도구를 불렀다. 더 부르지 않고 그 답의 글과 남은 호출(`pending`)을 돌려준다."""

    text: str
    pending: tuple[FunctionCall, ...]
    hosted_calls: int
    steps: tuple[ToolStep, ...]
    meta: CallMeta
    kind: Literal["partial"] = "partial"


@dataclass(frozen=True)
class ToolLoopFailed:
    """`budget_source` 는 상한 실패일 때만: "guard" 는 기존 비용 상한(BudgetLimit), "loop" 는 고리 한 번의 상한
    (`max_cost_usd`). `steps` 는 실패 전까지 도구를 실행한 걸음이다.
    `hosted_calls`(MARC-ISSUE-624)는 실패까지 공급사가 실행한 도구(web_search) 호출의 누계: 앞 걸음들의 합 + 마지막
    답이 거부·잘림이면 그 답의 수(과금된다 — 장부 `_cost_usd` 와 같은 갈래). 공급사 오류·시간 초과·상한·실행 함수
    예외로 끝나면 앞 걸음들의 합만."""

    failure: ToolLoopFailure
    steps: tuple[ToolStep, ...]
    meta: CallMeta
    budget_source: Literal["guard", "loop"] | None = None
    hosted_calls: int = 0
    kind: Literal["failed"] = "failed"


type ToolLoopResult = ToolLoopDone | ToolLoopPartial | ToolLoopFailed


# ── dry-run 의 보고 ──


@dataclass(frozen=True)
class DryRunEstimate:
    """어림값이다. 실제 토큰 수가 아니다. PDF·이미지는 세지 않는다(`unestimated_parts` 에 종류만 적는다).

    `cost_upper_bound_usd` 는 입력 어림 + 출력 상한을 다 썼을 때의 비용 상한이다(한 번 — 스키마 다시 부르기·요청 schema
    토큰은 들지 않는다. 뜻은 LH1 앞 그대로). 캐시 지정 몫(`cacheable_tokens`)은 쓰기 단가가 입력 단가보다 클 때 쓰기
    단가로 센다(LH3 Q8 — `worst_case_usd` 도 같다. 위끝은 같거나 커질 뿐).
    LH1(MARC-ISSUE-167)이 끝에 더한 칸 셋:
      schema_tokens   공급사 요청에 실린 응답 schema JSON 의 어림 토큰(안 실리면 0)
      max_attempts    한 모델의 최대 시도 수: schema 가 있으면 1 + max_schema_retries, 없으면 1
      worst_case_usd  (입력 + schema 토큰, 출력 상한)을 다 쓴 한 번 × max_attempts
    ★ `worst_case_usd` 밖: 대체 모델, 공급사 오류의 같은 모델 재시도(오류 응답은 과금되지 않는다 — 추정),
    첨부(PDF·그림).
    도구 고리(`dry_run_tools`)의 값은 0·1·`cost_upper_bound_usd` 이다(고리의 위끝은 `ToolLoopEstimate` 몫).
    """

    input_tokens: int
    cacheable_tokens: int
    max_output_tokens: int
    cost_upper_bound_usd: float
    unestimated_parts: tuple[str, ...]
    schema_tokens: int
    max_attempts: int
    worst_case_usd: float


@dataclass(frozen=True)
class ToolLoopEstimate:
    """도구 호출 고리(`dry_run_tools`)의 비용 위끝. 어림값이다.

    걸음 k(1부터)의 위끝 = 입력 어림(프롬프트 + 도구 정의) + 앞 걸음 k−1 개가 출력 상한을 다 써서 다시 실린 몫을
    입력으로, 출력 상한을 출력으로 친 비용(캐시 읽기 할인 없이, 캐시 지정 몫은 쓰기 단가가 입력보다 클 때 쓰기 단가로
    — LH3 Q9). `loop_upper_bound_usd` = 걸음 위끝의 합 + (web_search 를
    싣고 `max_hosted_calls` 를 준 때) 걸음 수 × `max_hosted_calls` × 건당 요금.
    ★ 위끝이 아닌 몫: `unestimated` 에 적은 것(도구 결과 글자, 검색 내용 토큰, 상한 없는 web_search 건수)은 들지 않는다.
    `max_provider_calls` 는 기록 줄 기준(걸음 수 × (1 + 같은 모델 재시도 상한 — 횟수 갈래 max_retries)). ★ 무효
    조건(LB1 감독 답 2 B1): 예산 갈래(한도 초과·과부하 — HTTP 상태로 거절돼 과금 없는 시도, retry.py)의 줄은 이 셈에
    들지 않는다 — 그 줄 수는 걸음마다 max_budget_retries 까지 더 있을 수 있다. openai·anthropic 의 SDK 재시도는 0 이라
    (LH1) 기록 줄 수 = HTTP 요청 수다. 걸음 하나의 벽시계는 timeout_ms × (1 + 재시도 상한) + 재시도 대기까지
    (client.py 머리의 「한 호출 최악」).
    """

    max_steps: int
    step_upper_bounds_usd: tuple[float, ...]
    loop_upper_bound_usd: float
    max_provider_calls: int
    unestimated: tuple[str, ...]


@dataclass(frozen=True)
class DryRunReport:
    """`tool_loop` 은 도구 호출 고리의 dry-run(`dry_run_tools`)일 때만 있다. 없으면 JSON 에 칸이 실리지 않는다."""

    prompt_id: str
    provider: str
    model: str
    request: object
    estimate: DryRunEstimate
    fallback_models: tuple[str, ...]
    warnings: tuple[LlmWarning, ...]
    tool_loop: ToolLoopEstimate | None = None

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {
            "dryRun": True,
            "promptId": self.prompt_id,
            "provider": self.provider,
            "model": self.model,
            "request": self.request,
            "estimate": {
                "inputTokens": self.estimate.input_tokens,
                "cacheableTokens": self.estimate.cacheable_tokens,
                "maxOutputTokens": self.estimate.max_output_tokens,
                "costUpperBoundUsd": self.estimate.cost_upper_bound_usd,
                "unestimatedParts": list(self.estimate.unestimated_parts),
                "schemaTokens": self.estimate.schema_tokens,
                "maxAttempts": self.estimate.max_attempts,
                "worstCaseUsd": self.estimate.worst_case_usd,
            },
            "fallbackModels": list(self.fallback_models),
            "warnings": [{"code": warning.code, "message": warning.message} for warning in self.warnings],
        }
        if self.tool_loop is not None:
            out["toolLoop"] = {
                "maxSteps": self.tool_loop.max_steps,
                "stepUpperBoundsUsd": list(self.tool_loop.step_upper_bounds_usd),
                "loopUpperBoundUsd": self.tool_loop.loop_upper_bound_usd,
                "maxProviderCalls": self.tool_loop.max_provider_calls,
                "unestimated": list(self.tool_loop.unestimated),
            }
        return out
