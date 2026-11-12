"""OpenAI Responses API 어댑터. SDK 클라이언트는 밖에서 만들어 넣는다(키를 여기서 찾지 않는다).

캐싱은 공급사가 앞부분 일치로 자동 적용하므로 표시할 것이 없고, 고정 지침을 앞에 두는 것으로 충분하다.
SDK 의 자체 재시도는 끈다(`CHAT_SDK_MAX_RETRIES` 0 — LH1 Q1). 다시 부르기는 호출 층(retry.py)이 시도마다 상한 확인과
기록 한 줄을 지나며 한다. 공급사가 머리로 준 대기(`retry-after-ms`·`retry-after`)는 오류의 `retry_after_ms` 로 옮긴다.
시간 제한은 요청마다 SDK 의 `timeout`(초)으로 건다.

도구(밴드 TL1): 요청의 도구 칸은 기본값이 아닐 때만 싣는다. `"store": False` 는 도구 호출에도 그대로다 — 앞 걸음은
`previous_response_id` 로 잇지 않고 `turns` 로 다시 실으며, 다시 싣는 항목에 공급사 항목 id 를 싣지 않는다
(`MARC-ENT-301`).

임베딩 어댑터(OpenAIEmbeddingProvider)는 따로 둔다: Embeddings API, SDK 표면도 따로(OpenAIEmbeddingsLike).
"""

from collections.abc import Callable
from dataclasses import replace
from typing import Any, Protocol, cast

import openai
from openai.types import CreateEmbeddingResponse
from openai.types.responses import Response, ResponseUsage

from esgapi.core.llm.embedding_types import EmbeddingProviderRequest, EmbeddingProviderResponse, EmbeddingVectors
from esgapi.core.llm.errors import LiveSetupError, soft_deadline_in
from esgapi.core.llm.providers.redact import redact_keys
from esgapi.core.llm.retry import retry_after_ms_from_headers
from esgapi.core.llm.types import (
    AssistantText,
    Completed,
    ErrorKind,
    FunctionCall,
    FunctionTool,
    ImagePart,
    InvokeOptions,
    PdfPart,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
    Refusal,
    TextPart,
    Tool,
    ToolCallsRequested,
    ToolOutput,
    Truncated,
    Turn,
    UrlCitation,
    Usage,
    WebSearchTool,
)


class OpenAIResponses(Protocol):
    def create(self, **kwargs: Any) -> Response: ...


class OpenAILike(Protocol):
    """어댑터가 쓰는 SDK 표면. 실제 `openai.OpenAI` 가 이 모양이고, 테스트는 가짜를 넣는다."""

    @property
    def responses(self) -> OpenAIResponses: ...


# SDK 의 자체 재시도 횟수. 채팅은 0: SDK 안에서 다시 보낸 요청은 호출 층의 상한 확인·기록에 보이지 않는다(MARC-ISSUE-306
# m2). 올리지 않는다 — 재시도는 retry.py 의 DEFAULT_PROVIDER_RETRY 로.
# 임베딩도 0(LB1 Q5): 임베딩 길도 호출 층이 같은 정책(retry.py)으로 다시 부른다 — 공급사로 나간 HTTP 요청이 전부 상한
# 확인과 기록 한 줄을 지난다(embedding.py 머리).
CHAT_SDK_MAX_RETRIES = 0
EMBEDDING_SDK_MAX_RETRIES = 0


def create_openai_client(api_key: str) -> OpenAILike:
    """키를 인자로 받아 SDK 클라이언트를 만든다. 키를 환경 변수에서 읽지 않는다.

    ★ SDK 는 키 말고도 환경 변수를 읽는다(openai 3.26.0: OPENAI_BASE_URL, OPENAI_ORG_ID, OPENAI_PROJECT_ID,
      OPENAI_CUSTOM_HEADERS …). live 기동은 그 이름들이 있으면 멈춘다(config/env.py 의 SDK_ENV_PREFIXES — LH1 Q3).
    """
    if api_key.strip() == "":
        raise LiveSetupError("OpenAI 키가 비었다")
    return cast("OpenAILike", openai.OpenAI(api_key=api_key, max_retries=CHAT_SDK_MAX_RETRIES))


class OpenAIProvider:
    name = "openai"

    def __init__(self, client: OpenAILike | None = None, *, now: Callable[[], float] | None = None) -> None:
        """`now`: HTTP 날짜 꼴 `retry-after` 를 남은 ms 로 바꿀 때의 지금(ms, epoch). 없으면 시계 — 시험이 고정한다."""
        self._client = client
        self._now = now

    def build_request(self, request: ProviderRequest) -> dict[str, object]:
        content: list[dict[str, object]] = []
        for part in request.user:
            match part:
                case TextPart():
                    content.append({"type": "input_text", "text": part.text})
                case PdfPart():
                    data = f"data:application/pdf;base64,{part.base64}"
                    content.append({"type": "input_file", "filename": part.filename, "file_data": data})
                case ImagePart():
                    url = f"data:{part.media_type};base64,{part.base64}"
                    content.append({"type": "input_image", "detail": "auto", "image_url": url})

        system = "\n\n".join(segment.text for segment in request.system)
        items: list[dict[str, object]] = []
        if request.system and request.system_placement == "input_message":
            items.append({"role": "system", "content": system})
        items.append({"role": "user", "content": content})
        items.extend(_turn_item(turn) for turn in request.turns)
        params: dict[str, object] = {
            "model": request.api_model_id,
            "max_output_tokens": request.max_output_tokens,
            "input": items,
            "store": False,
        }
        if request.system and request.system_placement == "instructions":
            params["instructions"] = system
        if request.json_schema is not None:
            params["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": request.json_schema.name,
                    "schema": request.json_schema.schema,
                    "strict": True,
                }
            }
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.tools:
            params["tools"] = [_tool_param(tool) for tool in request.tools]
        if request.tool_choice is not None:
            params["tool_choice"] = request.tool_choice
        if request.parallel_tool_calls is not None:
            params["parallel_tool_calls"] = request.parallel_tool_calls
        if request.max_hosted_calls is not None:
            params["max_tool_calls"] = request.max_hosted_calls
        return params

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        if self._client is None:
            return ProviderError(
                status=None, retryable=False, message="OpenAI 클라이언트가 주입되지 않았다", sent=False
            )
        try:
            params = self.build_request(request)
        except Exception as error:
            return _unsent(error)
        try:
            response = self._client.responses.create(**params, timeout=options.timeout_ms / 1000)
        except Exception as error:
            if (deadline := soft_deadline_in(error)) is not None:
                raise deadline from None  # Celery 소프트 제한은 삼키지 않는다(LH2 — errors.soft_deadline_in)
            return _map_error(error, now_ms=None if self._now is None else self._now())

        if response.usage is None:
            return ProviderError(
                status=None, retryable=False, message=f"응답에 usage 가 없다 (status: {response.status})"
            )
        usage = _to_usage(response.usage)
        model_id = response.model

        # 항목을 응답의 차례대로 한 번 돈다: 글(message), 우리 쪽 도구 호출(function_call), 공급사가 실행한
        # 웹 검색(web_search_call — 세기만). 그 밖의 항목(추론 등)은 지금처럼 건너뛴다.
        text = ""
        refusal: str | None = None
        output: list[AssistantText | FunctionCall] = []
        citations: list[UrlCitation] = []
        hosted_calls = 0
        for item in response.output:
            if item.type == "function_call":
                output.append(FunctionCall(call_id=item.call_id, name=item.name, arguments=item.arguments))
                continue
            if item.type == "web_search_call":
                hosted_calls += 1
                continue
            if item.type != "message":
                continue
            message_text = ""
            for part in item.content:
                if part.type == "output_text":
                    message_text += part.text
                    citations.extend(
                        UrlCitation(
                            url=note.url, title=note.title, start_index=note.start_index, end_index=note.end_index
                        )
                        for note in part.annotations
                        if note.type == "url_citation"
                    )
                elif part.type == "refusal":
                    refusal = part.refusal
            text += message_text
            if message_text:
                output.append(AssistantText(text=message_text))

        # 갈래의 차례: 거부 > 완료되지 않음 > 도구 호출이 남은 완료 > 완료.
        if refusal is not None:
            return Refusal(text=refusal, category=None, usage=usage, model_id=model_id, hosted_calls=hosted_calls)
        if response.status == "incomplete":
            reason = response.incomplete_details.reason if response.incomplete_details else None
            if reason == "max_output_tokens":
                return Truncated(text=text, usage=usage, model_id=model_id, hosted_calls=hosted_calls)
            if reason == "content_filter":
                return Refusal(
                    text=text, category="content_filter", usage=usage, model_id=model_id, hosted_calls=hosted_calls
                )
            return ProviderError(status=None, retryable=False, message=f"응답이 완료되지 않았다: {reason}")
        if response.status == "completed":
            if any(isinstance(item, FunctionCall) for item in output):
                return ToolCallsRequested(
                    output=tuple(output), usage=usage, model_id=model_id, hosted_calls=hosted_calls
                )
            return Completed(
                text=text, usage=usage, model_id=model_id, citations=tuple(citations), hosted_calls=hosted_calls
            )
        return ProviderError(status=None, retryable=False, message=f"예상하지 못한 응답 상태: {response.status}")


def _tool_param(tool: Tool) -> dict[str, object]:
    match tool:
        case FunctionTool():
            param: dict[str, object] = {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters),
            }
            # strict 는 준 때만 싣는다(받은 코랩의 도구 정의에 strict 가 없다 — 공급사 기본을 따른다).
            if tool.strict is not None:
                param["strict"] = tool.strict
            return param
        case WebSearchTool():
            param = {"type": "web_search", "search_context_size": tool.search_context_size}
            # user_location 은 준 때만 싣는다(SDK `web_search_tool_param.UserLocation` 의 꼴, 키 차례는 코랩대로).
            if tool.user_location is not None:
                param["user_location"] = {"type": tool.user_location.type, "country": tool.user_location.country}
            return param


def _turn_item(turn: Turn) -> dict[str, object]:
    """앞 걸음의 항목을 입력 항목으로. 공급사 항목 id(`fc_…`·`msg_…`)는 싣지 않는다: store:false 라 보관되지 않았다."""
    match turn:
        case FunctionCall():
            return {"type": "function_call", "call_id": turn.call_id, "name": turn.name, "arguments": turn.arguments}
        case AssistantText():
            return {"role": "assistant", "content": turn.text}
        case ToolOutput():
            return {"type": "function_call_output", "call_id": turn.call_id, "output": turn.output}


def _to_usage(usage: ResponseUsage) -> Usage:
    # input_tokens 는 캐시 읽기·쓰기 토큰을 포함한 합계다. 나머지를 비캐시 입력으로 센다.
    # (esg-lab 이 2026-10-01 gpt-6-luna 실제 호출로 확인: 같은 요청을 두 번 보내면 input_tokens 는 6045 로 같고
    #  첫 호출은 cache_write_tokens 6042, 둘째는 cached_tokens 6042 였다. 이 저장소에서는 실호출로 다시 재지 않았다.)
    # output_tokens 는 추론 토큰(output_tokens_details.reasoning_tokens)을 포함하고, 추론 토큰도 max_output_tokens 를
    # 쓴다.
    details = usage.input_tokens_details
    cache_read: int = details.cached_tokens
    # 파이썬 SDK 의 타입은 이 칸을 늘 있는 것으로 적지만, 공급사가 빼고 보내면(구버전 응답) 없을 수 있다.
    cache_write = cast("int | None", getattr(details, "cache_write_tokens", None)) or 0
    # 추론 토큰 수는 기록에 따로도 남긴다(thinking_tokens). 출력 상한의 여유분을 정할 근거다. 공급사가 안 보내면
    # 남기지 않는다.
    output_details = cast("object | None", getattr(usage, "output_tokens_details", None))
    reasoning = cast("int | None", getattr(output_details, "reasoning_tokens", None))
    return Usage(
        input_tokens=max(0, usage.input_tokens - cache_read - cache_write),
        output_tokens=usage.output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        thinking_tokens=reasoning,
    )


def _map_error(error: Exception, *, now_ms: float | None = None) -> ProviderResponse:
    message = redact_keys(str(error))
    # 순서가 뜻이다: APITimeoutError 는 APIConnectionError 의 갈래다.
    if isinstance(error, openai.APITimeoutError):
        return ProviderTimeout(message=message)
    if isinstance(error, openai.APIConnectionError):
        return ProviderError(
            status=None,
            retryable=True,
            message=message,
            sent=not _never_connected(error),
            error_kind="connection",
        )
    if isinstance(error, openai.APIStatusError):
        status = error.status_code
        kind = _error_kind(status, error.code, error.type)
        # 429 와 5xx 만 재시도 가능으로 본다(esg-lab 의 RateLimitError·InternalServerError 와 같은 범위). 크레딧·지출
        # 소진 429 는 기다려도 안 풀려 불가(LB1).
        retryable = kind != "quota_exhausted" and (status == 429 or status >= 500)
        retry_after = retry_after_ms_from_headers(error.response.headers, now_ms=now_ms) if retryable else None
        return ProviderError(
            status=status, retryable=retryable, message=message, retry_after_ms=retry_after, error_kind=kind
        )
    return ProviderError(status=None, retryable=False, message=message)


# 429 가운데 크레딧·지출·사용 한도 소진(기다려도 안 풀린다 — 재시도 불가). SDK 3.26.0 의 `APIStatusError.code`·`.type`
# (본문 `error` 안의 칸). https://developers.openai.com/api/docs/guides/error-codes (2026-11-11 확인)
QUOTA_ERROR_CODES: frozenset[str] = frozenset(
    {
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
        "insufficient_quota",
    }
)
QUOTA_ERROR_TYPE = "insufficient_quota"
# 503 가운데 과부하(같은 문서: service_unavailable_error / server_is_overloaded). 그 밖 503 은 server_error.
OVERLOADED_ERROR_CODE = "server_is_overloaded"


def _error_kind(status: int, code: str | None, error_type: str | None) -> ErrorKind:
    """오류의 이름(types.ErrorKind) — 위 상수의 문서."""
    if status == 429:
        quota = code in QUOTA_ERROR_CODES or error_type == QUOTA_ERROR_TYPE
        return "quota_exhausted" if quota else "rate_limited"
    if status == 503 and code == OVERLOADED_ERROR_CODE:
        return "overloaded"
    if status >= 500:
        return "server_error"
    return "other"


def _unsent(error: Exception) -> ProviderResponse:
    """요청을 만들다(조립) 던졌다 → 공급사로 나가지 않았다(LH3 Q2): `_map_error` 의 값에 `sent=False` 만 바꾼다
    (status·retryable·message 그대로 — 실패 시도의 보수 어림 밖). 조립 중의 Celery 소프트 제한은 삼키지 않는다."""
    if (deadline := soft_deadline_in(error)) is not None:
        raise deadline from None
    mapped = _map_error(error)
    return replace(mapped, sent=False) if isinstance(mapped, ProviderError) else mapped


def _never_connected(error: Exception) -> bool:
    """연결부터 실패했다(SDK 가 싼 원인의 조상 이름 ConnectError — httpx·httpx2) → 요청이 나가지 않았다(LH2 sent).
    연결 단계의 시간 초과(ConnectTimeout)는 시간 초과 갈래라 여기 오지 않는다(나갔다고 보는 보수 어림)."""
    cause = error.__cause__
    return cause is not None and any(cls.__name__ == "ConnectError" for cls in type(cause).__mro__)


# ── 임베딩 ──


class OpenAIEmbeddings(Protocol):
    def create(self, **kwargs: Any) -> CreateEmbeddingResponse: ...


class OpenAIEmbeddingsLike(Protocol):
    """임베딩 어댑터가 쓰는 SDK 표면. 실제 `openai.OpenAI` 가 이 모양이고, 테스트는 가짜를 넣는다."""

    @property
    def embeddings(self) -> OpenAIEmbeddings: ...


def create_openai_embedding_client(api_key: str) -> OpenAIEmbeddingsLike:
    """키를 인자로 받아 SDK 클라이언트를 만든다. 키를 환경 변수에서 읽지 않는다(create_openai_client 의 ★ 와 같다).
    SDK 재시도는 EMBEDDING_SDK_MAX_RETRIES(0 — LB1 Q5, 다시 부르기는 호출 층)."""
    if api_key.strip() == "":
        raise LiveSetupError("OpenAI 키가 비었다")
    return cast("OpenAIEmbeddingsLike", openai.OpenAI(api_key=api_key, max_retries=EMBEDDING_SDK_MAX_RETRIES))


class OpenAIEmbeddingProvider:
    """OpenAI Embeddings API 어댑터.

    `encoding_format="float"` 를 늘 보낸다: 빼면 SDK 가 "base64" 로 보내고 스스로 되푼다(다른 길을 탄다).
    `dimensions` 는 보내지 않는다(모델의 기본 차원을 받고, 클라이언트가 설정의 차원과 견준다).
    답의 벡터는 `index` 로 차례를 맞춘다(응답의 차례에 기대지 않는다). index 가 0..n-1 이 아니면(겹침·빠짐) 재시도
    불가 오류다.
    """

    name = "openai"

    def __init__(self, client: OpenAIEmbeddingsLike | None = None, *, now: Callable[[], float] | None = None) -> None:
        """`now`: HTTP 날짜 꼴 `retry-after` 를 남은 ms 로 바꿀 때의 지금(ms, epoch). 없으면 시계 — 시험이 고정한다."""
        self._client = client
        self._now = now

    def build_request(self, request: EmbeddingProviderRequest) -> dict[str, object]:
        return {"model": request.api_model_id, "input": list(request.inputs), "encoding_format": "float"}

    def embed(self, request: EmbeddingProviderRequest, options: InvokeOptions) -> EmbeddingProviderResponse:
        if self._client is None:
            return ProviderError(
                status=None, retryable=False, message="OpenAI 클라이언트가 주입되지 않았다", sent=False
            )
        try:
            params = self.build_request(request)
        except Exception as error:
            unsent = _unsent(error)
            # 조립 오류는 _map_error 의 마지막 갈래(ProviderError)다.
            return (
                unsent
                if isinstance(unsent, ProviderError | ProviderTimeout)
                else ProviderError(status=None, retryable=False, message=redact_keys(str(error)), sent=False)
            )
        try:
            response = self._client.embeddings.create(**params, timeout=options.timeout_ms / 1000)
        except Exception as error:
            if (deadline := soft_deadline_in(error)) is not None:
                raise deadline from None  # Celery 소프트 제한은 삼키지 않는다(LH2 — errors.soft_deadline_in)
            mapped = _map_error(error, now_ms=None if self._now is None else self._now())
            # _map_error 는 오류와 시간 초과만 돌려준다.
            return (
                mapped
                if isinstance(mapped, ProviderError | ProviderTimeout)
                else ProviderError(status=None, retryable=False, message=redact_keys(str(error)))
            )
        # 파이썬 SDK 의 타입은 usage 를 늘 있는 것으로 적지만, 빠지면 토큰을 지어내지 않는다(비용 None).
        usage = cast("object | None", getattr(response, "usage", None))
        tokens = cast("int | None", getattr(usage, "prompt_tokens", None))
        ordered = sorted(response.data, key=lambda item: item.index)
        indexes = [item.index for item in ordered]
        if indexes != list(range(len(ordered))):
            # 겹치거나 빠진 index 는 입력과의 짝을 모른다. 그 답의 토큰·비용은 남지 않는다(오류 갈래라 사용량이 없다).
            return ProviderError(
                status=None,
                retryable=False,
                message=f"임베딩 응답의 모양이 다르다: index {indexes} 가 0..n-1 이 아니다",
            )
        return EmbeddingVectors(
            vectors=tuple(tuple(float(value) for value in item.embedding) for item in ordered),
            input_tokens=tokens,
            model_id=response.model,
        )
