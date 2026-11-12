"""request ID 미들웨어. 요청마다 id 를 받거나 지어 응답 헤더와 로그에 싣고, 접근 줄 하나를 낸다.

`MIDDLEWARE` 의 **맨 앞**(가장 바깥)이다. 까닭: 테넌트 미들웨어와 경로 안에서 나는 모든 기록(오류 응답과 그 기록,
`on_commit` 갈고리의 기록)에 id 가 실려야 한다.

  - id 는 두 곳에 싣는다: contextvar(요청이 도는 동안의 모든 로그 줄)와 `request.request_id`.
    Django 는 4xx·5xx 의 줄(`django.request`)을 미들웨어 사슬이 끝난 뒤에 낸다. 그때 contextvar 는 이미 비어 있고,
    그 기록은 요청 객체를 싣고 온다. 포매터가 거기서 id 를 읽는다(jsonlog.py).
  - 접근 줄은 로거 `esgapi.access` 의 한 줄이다: method·path·status·duration_ms, 오류 응답이면 code(본문의
    error.code — 밴드 E2), 인증된 요청이면 user_id(세션의 사용자
    id — 정수. 인증이 request.auth 에 넣은 세션에서 읽는다). ★ path 는 `request.path` 다
    (쿼리 문자열이 없다). 원격 주소·user-agent·쿠키·헤더·본문을 싣지 않는다. gunicorn 의 접근 로그는 꺼 두었다
    (gunicorn.conf.py. 켜면 두 벌이다).
  - 요청에서 읽는 것은 헤더 `X-Request-ID` 하나다. 규칙에 안 맞는 값은 거절하지 않고 버린다(context.py).
  - 안쪽이 던지는 예외는 Django 가 미들웨어 층마다 응답으로 바꿔 준다. 그래서 `except` 가 없다.
  - 405(경로는 있는데 메서드가 없음)는 여기서 오류 꼴로 바꾼다(밴드 E2). ninja 는 405 를 예외로 던지지 않고
    `PathView._not_allowed()` 가 `HttpResponseNotAllowed`(text/html 「Method not allowed」)를 바로 돌려준다 —
    config/api.py 의 처리기에 닿지 않는다. 맨 바깥인 여기가 그 응답을 만나는 한 자리다. `Allow` 머리는 남긴다.
    꼴(`core/exceptions.py` 의 ErrorDetail 과 같은 키 넷)을 여기 글로 적는 까닭: 이 파일은 esgapi 에서 context 만
    들인다(core/tests/test_observability_layers.py).
"""

import json
import logging
import time
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse

from esgapi.core.observability.context import (
    REQUEST_ID_HEADER,
    accept_request_id,
    bind_request_id,
    unbind_request_id,
)

access_log = logging.getLogger("esgapi.access")


def authenticated_user_id(request: HttpRequest) -> int | None:
    """인증(SessionCookie)이 request.auth 에 넣어 둔 세션의 사용자 id(십진 글자 → 정수). 인증이 없거나 실패한 요청이면
    None. 세션의 꼴을 import 하지 않고 칸 이름으로 읽는다(이 파일은 esgapi 에서 context 만 들인다 —
    core/tests/test_observability_layers.py)."""
    user_id: object = getattr(getattr(request, "auth", None), "user_id", None)
    return int(user_id) if isinstance(user_id, str) and user_id.isdigit() else None


def error_code(response: HttpResponse) -> str | None:
    """4xx·5xx 의 JSON 본문 {"error": {"code": …}} 에서 code. 그 꼴이 아니거나 흘려 보내는 응답이면 None.
    code 하나만 꺼낸다(message·fields 는 싣지 않는다 — 받은 칸 이름이 들 수 있다)."""
    if response.status_code < 400 or getattr(response, "streaming", False):
        return None
    if "json" not in str(response.get("Content-Type", "")):
        return None
    try:
        body: object = json.loads(response.content)
    except ValueError:
        return None
    detail: object = body.get("error") if isinstance(body, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    code: object = detail.get("code") if isinstance(detail, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return code if isinstance(code, str) else None


def method_not_allowed(response: HttpResponseNotAllowed) -> JsonResponse:
    """ninja·Django 의 405 → 오류 꼴 하나. Allow 머리는 옮겨 싣는다."""
    body = {
        "error": {
            "code": "METHOD_NOT_ALLOWED",
            "message": "이 경로에 그 메서드는 없다",
            "fields": None,
            "legacyCode": None,
        }
    }
    out = JsonResponse(body, status=405)
    if response.has_header("Allow"):
        out["Allow"] = response["Allow"]
    return out


class RequestIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = accept_request_id(request.headers.get(REQUEST_ID_HEADER))
        setattr(request, "request_id", request_id)  # noqa: B010  (django-types 의 HttpRequest 에 이 속성이 없다)
        token = bind_request_id(request_id)
        started = time.monotonic()
        try:
            response = self.get_response(request)
            if isinstance(response, HttpResponseNotAllowed):
                response = method_not_allowed(response)
            response[REQUEST_ID_HEADER] = request_id
            extra: dict[str, object] = {
                "method": request.method or "",
                "path": request.path,
                "status": response.status_code,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
            code = error_code(response)
            if code is not None:
                extra["code"] = code
            user_id = authenticated_user_id(request)
            if user_id is not None:
                extra["user_id"] = user_id
            access_log.info("request", extra=extra)
            return response
        finally:
            unbind_request_id(token)
