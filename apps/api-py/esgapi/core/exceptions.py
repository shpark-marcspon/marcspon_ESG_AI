"""오류의 꼴은 하나다:

    {"error": {"code": "<갈래 이름>", "message": "<사람이 읽는 문장>", "fields": <칸별 문장 | null>, "legacyCode": …}}

EDK 리뉴얼의 오류 꼴(원문 :118-131)이다. code 는 대문자 snake(`NO_SESSION`·`REVIEW_LOCKED`·`VALIDATION_ERROR` …)이고
프론트는 code 로 가른다. fields 는 늘 키가 있고 422(요청 꼴)와 칸을 짚는 값 거절(fields 를 넘긴 것)에서 `{칸: [문장]}`.
legacyCode 는 옛 소문자 이름(`no_session` …)이다. 웹이 code 로 옮길 동안 한 판만 싣는다(deprecated, 밴드 C1 이 걷는다).

모듈은 HTTP 상태 코드도 대문자 글자도 모른다. 오류의 종류(ErrorKind)와 옛 소문자 이름만 말하고, 종류 → 상태 코드는
config/api.py 가, 소문자 → 대문자는 ErrorDetail 하나가 바꾼다(모듈 코드가 손대지 않게 — 밴드 E2).
"""

from typing import Any, Literal

from django.http import JsonResponse
from ninja import Schema
from pydantic import ConfigDict, model_validator

# 오류의 종류. 상태 코드와의 짝은 config/api.py 의 HTTP_STATUS 에 있다.
ErrorKind = Literal[
    "invalid_input",
    "unauthenticated",
    "forbidden",
    "not_found",
    "conflict",
    "unavailable",
    "token_not_valid",
    "validation",
]

# 세부 이름이 없는(code 가 종류 이름 그대로인) 옛 글자 → EDK 의 일반 이름. 여기 없는 것은 대문자로만 바꾼다.
GENERIC_CODES: dict[str, str] = {
    "invalid_input": "BAD_REQUEST",
    "unauthenticated": "UNAUTHORIZED",
}


def edk_code(code: str) -> str:
    """옛 소문자 이름 → 대문자 code. 이미 대문자면 그대로다."""
    return GENERIC_CODES.get(code, code.upper())


class ApplicationError(Exception):
    """모듈의 api.py·auth 가 던지면 config/api.py 의 처리기가 위 꼴의 응답으로 바꾼다."""

    def __init__(self, kind: ErrorKind, code: str, message: str, fields: dict[str, list[str]] | None = None) -> None:
        super().__init__(message)
        self.kind: ErrorKind = kind
        self.code = code
        self.message = message
        self.fields = fields


def _required_keys(schema: dict[str, Any]) -> None:
    # fields·legacyCode 는 기본값(null)이 있어도 본문에 늘 키가 있다. 생성 타입이 그것을 `?` 없이 말하게 한다.
    schema["required"] = ["code", "message", "fields", "legacyCode"]
    legacy = schema["properties"]["legacyCode"]
    legacy["deprecated"] = True
    legacy["description"] = "옛 소문자 code. 한 판만 싣는다 — code 를 읽는다"


class ErrorDetail(Schema):
    model_config = ConfigDict(json_schema_extra=_required_keys)

    code: str
    message: str
    fields: dict[str, list[str]] | None = None
    legacyCode: str | None = None

    @model_validator(mode="after")
    def _to_edk_code(self) -> "ErrorDetail":
        # 옛 소문자로 만들어도(모듈의 Status(413, ErrorBody(error=ErrorDetail(code="too_many_rows", …))) 같은 자리)
        # 나갈 때는 대문자 code + legacyCode 다. 이미 대문자면 손대지 않는다(두 번 지나도 같다).
        upper = edk_code(self.code)
        if upper != self.code:
            if self.legacyCode is None:
                self.legacyCode = self.code
            self.code = upper
        return self


class ErrorBody(Schema):
    error: ErrorDetail


def error_response(
    status: int,
    code: str,
    message: str,
    fields: dict[str, list[str]] | None = None,
    *,
    legacy_code: str | None = None,
) -> JsonResponse:
    detail = ErrorDetail(code=code, message=message, fields=fields, legacyCode=legacy_code)
    return JsonResponse({"error": detail.model_dump()}, status=status)


def unavailable() -> JsonResponse:
    """닿지 못함(DB 에 닿지 못함 등). 속사정은 기록에만 남기고 클라이언트에는 주지 않는다.

    상태 코드(503)가 여기 박힌 까닭: 테넌트 미들웨어는 ninja 밖에서 답해야 해서 config/api.py 를 거치지 못한다.
    """
    return error_response(503, "unavailable", "잠시 뒤 다시 시도해 달라")
