"""Gemini API(`models.generate_content`) 어댑터. SDK 클라이언트는 밖에서 만들어 넣는다(키를 여기서 찾지 않는다).

캐싱은 공급사가 앞부분 일치로 자동 적용(implicit caching)하므로 표시할 것이 없고, 고정 지침을 앞에 두는 것으로 충분하다.
구조화 출력은 `responseMimeType` + `responseJsonSchema` 다. 스키마는 그대로 보내고 값의 검증은 호출 층이 한다.

SDK 의 자체 재시도는 켜지 않는다(`retry_options` 를 주지 않으면 google-genai 2.28.0 은 한 번만 부른다).
일시 오류(429·5xx)는 호출 층이 다시 부른다(retry.py 의 DEFAULT_PROVIDER_RETRY): SDK 안의 재시도는 호출 기록에 남지 않고
호출 간격 조절을 지나지 않으며 공급사가 요구한 대기를 따르지 않는다.

★ 시간 제한: 동기 호출이라 중단 신호가 없다. 요청마다 `http_options.timeout`(ms)으로 건다. SDK 는 이 값을 HTTP 시간
제한으로
  쓰는 동시에 서버에 마감 시간(X-Server-Timeout 머리)으로도 보낸다. esg-lab 이 2026-10-02 실제 호출에서 받은 답:
  마감이 10초 미만이면 400 ("Manually set deadline 1s is too short. Minimum allowed deadline is 10s.").
  → 무효 조건: 이 어댑터에 10,000ms 미만의 시간 제한을 주면 시간 초과가 아니라 400 오류가 날 것이다(이 저장소에서는
  재지 않았다).
"""

import base64
import re
from dataclasses import replace
from typing import Any, Protocol, cast

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from esgapi.core.llm.errors import LiveSetupError, LlmConfigError, soft_deadline_in
from esgapi.core.llm.providers.redact import redact_keys
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


class GeminiModels(Protocol):
    def generate_content(self, **kwargs: Any) -> genai_types.GenerateContentResponse: ...


class GeminiLike(Protocol):
    """어댑터가 쓰는 SDK 표면. 실제 `genai.Client` 가 이 모양이고, 테스트는 가짜를 넣는다."""

    @property
    def models(self) -> GeminiModels: ...


def create_gemini_client(api_key: str) -> GeminiLike:
    """키를 인자로 받아 SDK 클라이언트를 만든다. 키를 환경 변수에서 읽지 않는다.

    `vertexai=False`·`enterprise=False` 를 명시한다: 비워 두면 SDK 가 환경 변수(GOOGLE_GENAI_USE_VERTEXAI 등)를 보고
    Vertex AI 쪽으로 붙으려 든다.
    """
    if api_key.strip() == "":
        raise LiveSetupError("Gemini 키가 비었다")
    return cast("GeminiLike", genai.Client(api_key=api_key, vertexai=False, enterprise=False))


# 출력이 정책으로 막힌 종료 사유. 거부로 옮긴다.
_BLOCKED_FINISH = frozenset({"SAFETY", "RECITATION", "LANGUAGE", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"})


def _media_type(part: PdfPart | ImagePart) -> str:
    return "application/pdf" if isinstance(part, PdfPart) else part.media_type


# 도구 호출 고리(TL1)는 OpenAI·모의 공급사만 받는다. 호출 층을 거치지 않고 포트를 직접 부르는 길에서 조용히 빼지 않는다.
_NO_TOOLS = "Gemini 어댑터는 도구 칸(tools·turns·system_placement 등)을 싣지 않는다"


class GeminiProvider:
    name = "gemini"

    def __init__(self, client: GeminiLike | None = None) -> None:
        self._client = client

    def build_request(self, request: ProviderRequest) -> dict[str, object]:
        """REST 본문과 같은 꼴(camelCase, 첨부는 base64 글자)이다. dry-run 과 기록에 쓰는 것이고 esg-lab 과 같다.

        SDK 에 넘기는 값은 `_sdk_arguments` 가 따로 만든다(파이썬 SDK 는 첨부를 바이트로 받는다).
        """
        if request.uses_tools:
            raise LlmConfigError(_NO_TOOLS)
        parts: list[dict[str, object]] = []
        for part in request.user:
            if isinstance(part, TextPart):
                parts.append({"text": part.text})
            else:
                parts.append({"inlineData": {"mimeType": _media_type(part), "data": part.base64}})
        config: dict[str, object] = {"maxOutputTokens": request.max_output_tokens}
        if request.system:
            config["systemInstruction"] = "\n\n".join(segment.text for segment in request.system)
        if request.json_schema is not None:
            config["responseMimeType"] = "application/json"
            config["responseJsonSchema"] = request.json_schema.schema
        if request.temperature is not None:
            config["temperature"] = request.temperature
        return {"model": request.api_model_id, "contents": [{"role": "user", "parts": parts}], "config": config}

    def _sdk_arguments(self, request: ProviderRequest, options: InvokeOptions) -> dict[str, object]:
        parts: list[genai_types.Part] = []
        for part in request.user:
            if isinstance(part, TextPart):
                parts.append(genai_types.Part(text=part.text))
            else:
                blob = genai_types.Blob(mime_type=_media_type(part), data=base64.b64decode(part.base64))
                parts.append(genai_types.Part(inline_data=blob))
        config = genai_types.GenerateContentConfig(
            max_output_tokens=request.max_output_tokens,
            http_options=genai_types.HttpOptions(timeout=round(options.timeout_ms)),
        )
        if request.system:
            config.system_instruction = "\n\n".join(segment.text for segment in request.system)
        if request.json_schema is not None:
            config.response_mime_type = "application/json"
            config.response_json_schema = request.json_schema.schema
        if request.temperature is not None:
            config.temperature = request.temperature
        contents = [genai_types.Content(role="user", parts=parts)]
        return {"model": request.api_model_id, "contents": contents, "config": config}

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        if self._client is None:
            return ProviderError(
                status=None, retryable=False, message="Gemini 클라이언트가 주입되지 않았다", sent=False
            )
        if request.uses_tools:
            return ProviderError(status=None, retryable=False, message=_NO_TOOLS, sent=False)
        try:
            arguments = self._sdk_arguments(request, options)
        except Exception as error:
            return _unsent(error)
        try:
            response = self._client.models.generate_content(**arguments)
        except Exception as error:
            if (deadline := soft_deadline_in(error)) is not None:
                raise deadline from None  # Celery 소프트 제한은 삼키지 않는다(LH2 — errors.soft_deadline_in)
            return _map_error(error)

        candidate = response.candidates[0] if response.candidates else None
        feedback = response.prompt_feedback
        block_reason = feedback.block_reason if feedback is not None else None
        model_id = response.model_version
        # 입력이 막히면 후보가 없고 prompt_feedback.block_reason 만 온다. usage 가 같이 오지 않아도 거부로 돌려준다.
        if candidate is None and block_reason is not None:
            zero = Usage(input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0)
            usage = _to_usage(response.usage_metadata) if response.usage_metadata is not None else zero
            return Refusal(text="", category=block_reason.value, usage=usage, model_id=model_id)
        if response.usage_metadata is None:
            return ProviderError(status=None, retryable=False, message="응답에 usageMetadata 가 없다")
        usage = _to_usage(response.usage_metadata)
        if candidate is None:
            return ProviderError(status=None, retryable=False, message="응답에 후보가 없다")

        # 생각(thought) 부분은 답이 아니므로 뺀다.
        parts = candidate.content.parts if candidate.content is not None and candidate.content.parts else []
        text = "".join(part.text for part in parts if not part.thought and part.text is not None)
        finish = candidate.finish_reason.value if candidate.finish_reason is not None else "None"
        if finish == "STOP":
            return Completed(text=text, usage=usage, model_id=model_id)
        if finish == "MAX_TOKENS":
            return Truncated(text=text, usage=usage, model_id=model_id)
        if finish in _BLOCKED_FINISH:
            return Refusal(text=text, category=finish, usage=usage, model_id=model_id)
        return ProviderError(status=None, retryable=False, message=f"예상하지 못한 finishReason: {finish}")


def _to_usage(usage: genai_types.GenerateContentResponseUsageMetadata) -> Usage:
    # prompt_token_count 는 캐시에서 읽은 토큰(cached_content_token_count)을 포함한 합계다. 나머지를 비캐시 입력으로
    # 센다.
    # (esg-lab 이 2026-10-02 gemini-3.1-flash-lite 실제 호출로 확인: 같은 요청을 두 번 보내면 promptTokenCount 는
    # 7127 로 같고
    #  첫 호출에는 cachedContentTokenCount 필드가 없고 둘째는 4076 이었다. 이 저장소에서는 실호출로 다시 재지 않았다.)
    # 캐시 적중이 없으면 공급사가 필드를 아예 보내지 않는다. 0 으로 센다.
    # 자동 캐시에는 쓰기 과금이 따로 없어 캐시 쓰기 토큰은 항상 0 이다.
    # 생각 토큰(thoughts_token_count)은 candidates_token_count 에 들어 있지 않고 출력 단가로 과금되므로 출력에 더한다.
    # 생각 토큰 수는 기록에 따로도 남긴다(thinking_tokens). 공급사가 필드를 보내지 않으면 남기지 않는다.
    cache_read = usage.cached_content_token_count or 0
    thinking = usage.thoughts_token_count
    return Usage(
        input_tokens=max(0, (usage.prompt_token_count or 0) - cache_read),
        output_tokens=(usage.candidates_token_count or 0) + (thinking or 0),
        cache_read_tokens=cache_read,
        cache_write_tokens=0,
        thinking_tokens=thinking,
    )


def _ancestor_names(error: Exception) -> frozenset[str]:
    return frozenset(cls.__name__ for cls in type(error).__mro__)


def _map_error(error: Exception) -> ProviderResponse:
    if isinstance(error, genai_errors.APIError):
        status = error.code
        kind = _error_kind(status)
        retryable = kind in ("rate_limited", "server_error")
        retry_after = retry_info_delay_ms(cast("object", getattr(error, "details", None))) if retryable else None
        message = redact_keys(error.message or str(error))
        return ProviderError(
            status=status, retryable=retryable, message=message, retry_after_ms=retry_after, error_kind=kind
        )
    # SDK 는 HTTP 층(httpx)의 예외를 감싸지 않고 그대로 올린다. httpx 를 직접 import 하지 않으려고 조상 클래스의
    # 이름으로 가른다
    # (TimeoutException ⊂ TransportError. 연결 실패 ConnectError 도 TransportError 의 갈래다).
    names = _ancestor_names(error)
    message = redact_keys(str(error))
    if "TimeoutException" in names or isinstance(error, TimeoutError):
        return ProviderTimeout(message=message)
    if "TransportError" in names or isinstance(error, ConnectionError):
        # 연결부터 실패(ConnectError)면 요청이 나가지 않았다(LH2 sent — 실패 시도의 보수 어림 밖).
        return ProviderError(
            status=None,
            retryable=True,
            message=message,
            sent="ConnectError" not in names,
            error_kind="connection",
        )
    return ProviderError(status=None, retryable=False, message=message)


def _error_kind(status: int) -> ErrorKind:
    """오류의 이름(types.ErrorKind). 근거(2026-11-11 확인):
    https://aistudio.google.com/docs/troubleshooting — 429·408·5xx 는 일시 오류,
    https://aistudio.google.com/docs/api-errors — 402 payment_required(선불 크레딧 소진, 「Don't retry」).
    429 의 일 한도(quota_exceeded)와 분 한도는 가를 길이 없어 둘 다 rate_limited(추정). 503 은 「overloaded or down」
    이라 과부하로 단정하지 않고 server_error(보수 — 횟수 갈래, LB1 감독 처분)."""
    if status == 402:
        return "quota_exhausted"
    if status == 429:
        return "rate_limited"
    if status == 408 or status >= 500:
        return "server_error"
    return "other"


def _unsent(error: Exception) -> ProviderResponse:
    """요청을 만들다(조립) 던졌다 → 공급사로 나가지 않았다(LH3 Q2): `_map_error` 의 값에 `sent=False` 만 바꾼다
    (status·retryable·message 그대로 — 실패 시도의 보수 어림 밖). 조립 중의 Celery 소프트 제한은 삼키지 않는다."""
    if (deadline := soft_deadline_in(error)) is not None:
        raise deadline from None
    mapped = _map_error(error)
    return replace(mapped, sent=False) if isinstance(mapped, ProviderError) else mapped


_RETRY_DELAY = re.compile(r"([0-9]+(?:\.[0-9]+)?)s")


def retry_info_delay_ms(body: object) -> int | None:
    """오류 본문의 `google.rpc.RetryInfo.retryDelay`("55s" 꼴)를 ms 로 읽는다. 없거나 읽을 수 없으면 None.

    파이썬 SDK 의 `APIError.details` 가 응답 본문(JSON 을 읽은 값)이다. esg-lab 이 2026-10-02 무료 등급 429 에서 받은
    실제 모양:
    `{"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "55s"}]}}`.
    """
    if not isinstance(body, dict):
        return None
    error = cast("dict[str, object]", body).get("error")
    if not isinstance(error, dict):
        return None
    details = cast("dict[str, object]", error).get("details")
    if not isinstance(details, list):
        return None
    for detail in cast("list[object]", details):
        if not isinstance(detail, dict):
            continue
        entry = cast("dict[str, object]", detail)
        kind = entry.get("@type")
        delay = entry.get("retryDelay")
        if not isinstance(kind, str) or not kind.endswith("google.rpc.RetryInfo") or not isinstance(delay, str):
            continue
        match = _RETRY_DELAY.fullmatch(delay)
        if match is not None:
            return round(float(match[1]) * 1000)
    return None
