"""Anthropic Messages API 어댑터. SDK 클라이언트는 밖에서 만들어 넣는다(키를 여기서 찾지 않는다).

프롬프트 캐싱(cache_control), PDF·이미지 블록, 구조화 출력(output_config.format)은 이 파일 안에만 있다.
SDK 의 자체 재시도는 끈다(`SDK_MAX_RETRIES` 0 — LH1 Q1). 다시 부르기는 호출 층(retry.py)이 시도마다 상한 확인과 기록
한 줄을 지나며 한다. 공급사가 머리로 준 대기(`retry-after-ms`·`retry-after`)는 오류의 `retry_after_ms` 로 옮긴다.
시간 제한은 요청마다 SDK 의 `timeout`(초)으로 건다.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from typing import Any, Protocol, cast

import anthropic
from anthropic.types import Message
from anthropic.types import Usage as AnthropicUsage

from esgapi.core.llm.errors import LiveSetupError, LlmConfigError, soft_deadline_in
from esgapi.core.llm.providers.redact import redact_keys
from esgapi.core.llm.retry import retry_after_ms_from_headers
from esgapi.core.llm.schema import strip_unsupported_schema_keys
from esgapi.core.llm.types import (
    Completed,
    ErrorKind,
    ImagePart,
    InvokeOptions,
    PdfPart,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
    ProviderTimeout,
    Refusal,
    TextPart,
    Truncated,
    Usage,
)


class AnthropicStream(Protocol):
    def get_final_message(self) -> Message: ...


class AnthropicMessages(Protocol):
    def stream(self, **kwargs: Any) -> AbstractContextManager[AnthropicStream]: ...


class AnthropicLike(Protocol):
    """어댑터가 쓰는 SDK 표면. 실제 `anthropic.Anthropic` 이 이 모양이고, 테스트는 가짜를 넣는다."""

    @property
    def messages(self) -> AnthropicMessages: ...


# SDK 의 자체 재시도 횟수 0: SDK 안에서 다시 보낸 요청은 호출 층의 상한 확인·기록에 보이지 않는다(MARC-ISSUE-306 m2).
# 올리지 않는다 — 재시도는 retry.py 의 DEFAULT_PROVIDER_RETRY 로.
SDK_MAX_RETRIES = 0


def create_anthropic_client(api_key: str) -> AnthropicLike:
    """키를 인자로 받아 SDK 클라이언트를 만든다. 키를 환경 변수에서 읽지 않는다.

    ★ SDK 는 키 말고도 환경 변수를 읽는다(anthropic 1.11.0: ANTHROPIC_AUTH_TOKEN, ANTHROPIC_BASE_URL,
      ANTHROPIC_CUSTOM_HEADERS …). 파이썬 SDK 는 `auth_token=None` 이 「환경에서 읽어라」여서 esg-lab 처럼 null 로
      막을 수 없다. live 기동은 그 이름들이 있으면 멈춘다(config/env.py 의 SDK_ENV_PREFIXES — LH1 Q3).
    """
    if api_key.strip() == "":
        raise LiveSetupError("Anthropic 키가 비었다")
    return cast("AnthropicLike", anthropic.Anthropic(api_key=api_key, max_retries=SDK_MAX_RETRIES))


# 설치된 anthropic 1.11.0 의 messages.stream 에 temperature 인자가 없다. extra_body 로 싣지 않는다(MARC-TICK-136).
_NO_TEMPERATURE = "Anthropic 어댑터는 temperature 를 싣지 않는다(설치된 SDK 에 인자가 없다)"
# 도구 호출 고리(TL1)는 OpenAI·모의 공급사만 받는다. 호출 층을 거치지 않고 포트를 직접 부르는 길에서 조용히 빼지 않는다.
_NO_TOOLS = "Anthropic 어댑터는 도구 칸(tools·turns·system_placement 등)을 싣지 않는다"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, client: AnthropicLike | None = None, *, now: Callable[[], float] | None = None) -> None:
        """`now`: HTTP 날짜 꼴 `retry-after` 를 남은 ms 로 바꿀 때의 지금(ms, epoch). 없으면 시계 — 시험이 고정한다."""
        self._client = client
        self._now = now

    def build_request(self, request: ProviderRequest) -> dict[str, object]:
        if request.temperature is not None:
            # 조용히 빼고 보내지 않는다. 호출 층은 이 공급사의 모델에 값이 오면 미리 거른다(client.py 의 표).
            raise LlmConfigError(_NO_TEMPERATURE)
        if request.uses_tools:
            raise LlmConfigError(_NO_TOOLS)
        system: list[dict[str, object]] = [{"type": "text", "text": segment.text} for segment in request.system]
        # 캐시는 앞부분 일치라 마지막 캐시 구획에만 표시하면 그 앞까지 함께 걸린다.
        cached = [index for index, segment in enumerate(request.system) if segment.cache]
        if cached:
            system[cached[-1]]["cache_control"] = {"type": "ephemeral"}

        content: list[dict[str, object]] = []
        for part in request.user:
            match part:
                case TextPart():
                    content.append({"type": "text", "text": part.text})
                case PdfPart():
                    source = {"type": "base64", "media_type": "application/pdf", "data": part.base64}
                    content.append({"type": "document", "source": source})
                case ImagePart():
                    source = {"type": "base64", "media_type": part.media_type, "data": part.base64}
                    content.append({"type": "image", "source": source})

        params: dict[str, object] = {
            "model": request.api_model_id,
            "max_tokens": request.max_output_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        if system:
            params["system"] = system
        if request.json_schema is not None:
            schema = strip_unsupported_schema_keys(request.json_schema.schema)
            params["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        return params

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        if self._client is None:
            return ProviderError(
                status=None, retryable=False, message="Anthropic 클라이언트가 주입되지 않았다", sent=False
            )
        if request.temperature is not None:
            return ProviderError(status=None, retryable=False, message=_NO_TEMPERATURE, sent=False)
        if request.uses_tools:
            return ProviderError(status=None, retryable=False, message=_NO_TOOLS, sent=False)
        try:
            params = self.build_request(request)
        except Exception as error:
            return _unsent(error)
        try:
            # 출력이 길면 비스트리밍 요청은 HTTP 시간 제한에 걸리므로 항상 스트림으로 받아 합친다.
            with self._client.messages.stream(**params, timeout=options.timeout_ms / 1000) as stream:
                message = stream.get_final_message()
        except Exception as error:
            # Celery 소프트 제한은 삼키지 않는다(LH2 — errors.soft_deadline_in). send 중엔 SDK 가 APIConnectionError 로
            # 싸서 __cause__ 에, 스트림을 읽는 중엔 날 예외로 온다.
            if (deadline := soft_deadline_in(error)) is not None:
                raise deadline from None
            return _map_error(error, now_ms=None if self._now is None else self._now())

        usage = _to_usage(message.usage)
        model_id = message.model
        text = "".join(block.text for block in message.content if block.type == "text")

        match message.stop_reason:
            case "end_turn" | "stop_sequence":
                return Completed(text=text, usage=usage, model_id=model_id)
            case "refusal":
                category = message.stop_details.category if message.stop_details else None
                return Refusal(text=text, category=category, usage=usage, model_id=model_id)
            case "max_tokens" | "model_context_window_exceeded":
                return Truncated(text=text, usage=usage, model_id=model_id)
            case _:
                # tool_use, pause_turn, None: 도구를 주지 않았으므로 나올 수 없는 종료다.
                reason = message.stop_reason
                return ProviderError(status=None, retryable=False, message=f"예상하지 못한 stop_reason: {reason}")


def _to_usage(usage: AnthropicUsage) -> Usage:
    # input_tokens 는 캐시 읽기·쓰기를 뺀 값이다. (esg-lab 이 2026-10-02 claude-haiku-4-5 실제 호출로 확인: 같은 요청을
    # 두 번 보내면 input_tokens 는 15 로 같고 첫 호출은 cache_creation_input_tokens 6832, 둘째는 cache_read_input_tokens
    # 6832 였다. 이 저장소에서는 실호출로 다시 재지 않았다.) 공급사가 보고하지 않은 캐시 토큰은 None 으로 남긴다.
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_input_tokens,
        cache_write_tokens=usage.cache_creation_input_tokens,
    )


def _map_error(error: Exception, *, now_ms: float | None = None) -> ProviderResponse:
    message = redact_keys(str(error))
    # 순서가 뜻이다: APITimeoutError 는 APIConnectionError 의 갈래다.
    if isinstance(error, anthropic.APITimeoutError):
        return ProviderTimeout(message=message)
    if isinstance(error, anthropic.APIConnectionError):
        # 소프트 제한이 싸인 것은 invoke 가 먼저 다시 던졌다 — 여기 오는 연결 오류는 BASE 처럼 재시도 가능(LH2 Q7).
        return ProviderError(
            status=None,
            retryable=True,
            message=message,
            sent=not _never_connected(error),
            error_kind="connection",
        )
    if isinstance(error, anthropic.APIStatusError):
        status = error.status_code
        kind = _error_kind(status, error.type, error.body)
        # 429 와 5xx(529 과부하 포함)를 재시도 가능으로 본다. 지출 상한·청구 소진은 기다려도 안 풀려 불가, 스트림 중
        # 과부하 사건(HTTP 200 — SDK 가 `event: error` 를 APIStatusError 로 올린다)은 가능(LB1 — 과금됐을 수 있는
        # 실패라 횟수 갈래로 다시 부른다, retry.py).
        retryable = kind != "quota_exhausted" and (status == 429 or status >= 500 or kind == "overloaded")
        retry_after = retry_after_ms_from_headers(error.response.headers, now_ms=now_ms) if retryable else None
        return ProviderError(
            status=status, retryable=retryable, message=message, retry_after_ms=retry_after, error_kind=kind
        )
    return ProviderError(status=None, retryable=False, message=message)


# 429 가운데 지출 상한(월 한도)에 닿은 것: 본문 `error.details.error_code`. retry-after 가 없고 기다려도 안 풀린다.
# https://platform.claude.com/docs/en/api/rate-limits#reaching-your-spend-cap (2026-11-11 확인)
SPEND_CAP_ERROR_CODE = "enforced_spend_limit_reached"


def _error_kind(status: int, error_type: str | None, body: object) -> ErrorKind:
    """오류의 이름(types.ErrorKind). 근거(2026-11-11 확인): https://platform.claude.com/docs/en/api/errors — 402
    billing_error · 429 rate_limit_error · 529 overloaded_error, 스트림 중 오류 사건은 HTTP 200 뒤에 `overloaded_error`
    꼴로 온다(https://platform.claude.com/docs/en/build-with-claude/streaming#error-events)."""
    if status == 529 or error_type == "overloaded_error":
        return "overloaded"
    if status == 402 or (status == 429 and _details_code(body) == SPEND_CAP_ERROR_CODE):
        return "quota_exhausted"
    if status == 429:
        return "rate_limited"
    if status >= 500:
        return "server_error"
    return "other"


def _details_code(body: object) -> object:
    """본문 `error.details.error_code`(없으면 None). 본문은 SDK 가 JSON 을 읽은 값이다(모양을 믿지 않는다)."""
    error = cast("dict[str, object]", body).get("error") if isinstance(body, dict) else None
    details = cast("dict[str, object]", error).get("details") if isinstance(error, dict) else None
    return cast("dict[str, object]", details).get("error_code") if isinstance(details, dict) else None


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
