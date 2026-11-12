"""request ID 미들웨어(esgapi/core/observability/middleware.py). 순수 층: DB 에 닿지 않는다.

미들웨어 하나를 가짜 안쪽(get_response)과 함께 직접 부른다. 설정에 걸린 사슬은 Django 테스트 클라이언트로
`/healthz` 를 불러 본다(테넌트 미들웨어가 트랜잭션을 열지 않는 경로다).
접근 줄의 **칸**은 pytest 의 caplog 로 읽고, **한 줄 JSON 으로 나간 글**은 이 테스트가 로거에 걸었다 떼는 처리기로
읽는다(뿌리 로거의 처리기와 수준은 건드리지 않는다).
"""

import io
import json
import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pytest
from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import Client, RequestFactory

from esgapi.core.observability import context
from esgapi.core.observability.jsonlog import FIELDS, JsonFormatter, logging_config
from esgapi.core.observability.middleware import RequestIdMiddleware

HEX32 = re.compile(r"[0-9a-f]{32}")
ACCESS = "esgapi.access"


@contextmanager
def json_lines(logger_name: str) -> Generator[io.StringIO]:
    """그 로거에 한 줄 JSON 처리기를 걸었다가 뗀다. 기록이 나는 그 순간에 지은 글이 담긴다."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)


def parsed(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def answering(status: int = 200, seen: dict[str, Any] | None = None) -> RequestIdMiddleware:
    def inner(request: HttpRequest) -> HttpResponse:
        if seen is not None:
            seen["bound"] = context.current_request_id()
            seen["on_request"] = getattr(request, "request_id", None)
        return HttpResponse(b"body", status=status, headers={"X-Other": "kept"})

    return RequestIdMiddleware(inner)


@pytest.mark.parametrize("status", [200, 404, 503])
def test_every_response_carries_the_header_and_nothing_else_changes(status: int) -> None:
    response = answering(status)(RequestFactory().get("/x"))
    assert HEX32.fullmatch(response["X-Request-ID"])
    assert (response.status_code, response.content, response["X-Other"]) == (status, b"body", "kept")


@pytest.mark.parametrize("sent", ["abc-123_.X", "a" * 64])
def test_a_well_formed_id_comes_back(sent: str) -> None:
    response = answering()(RequestFactory().get("/x", headers={"X-Request-ID": sent}))
    assert response["X-Request-ID"] == sent


@pytest.mark.parametrize("sent", ["has space", "a" * 65, "semi;colon", "a,b", ""])
def test_a_malformed_id_is_replaced_not_refused(sent: str) -> None:
    response = answering()(RequestFactory().get("/x", headers={"X-Request-ID": sent}))
    assert response.status_code == 200
    assert response["X-Request-ID"] != sent
    assert HEX32.fullmatch(response["X-Request-ID"])


def test_the_id_is_bound_inside_and_gone_after() -> None:
    seen: dict[str, Any] = {}
    request = RequestFactory().get("/x", headers={"X-Request-ID": "req-1"})
    assert context.current_request_id() is None
    response = answering(seen=seen)(request)
    assert seen == {"bound": "req-1", "on_request": "req-1"}
    assert response["X-Request-ID"] == "req-1"
    assert getattr(request, "request_id", None) == "req-1"  # Django 가 뒤에 내는 4xx·5xx 의 줄이 여기서 읽는다
    assert context.current_request_id() is None


def test_the_id_is_gone_even_when_the_inside_raises() -> None:
    def broken(request: HttpRequest) -> HttpResponse:
        raise RuntimeError("안쪽이 던졌다")

    with pytest.raises(RuntimeError):
        RequestIdMiddleware(broken)(RequestFactory().get("/x"))
    assert context.current_request_id() is None


def test_one_access_record_per_request_with_the_four_fields(caplog: pytest.LogCaptureFixture) -> None:
    middleware = answering(404)
    with caplog.at_level(logging.INFO, logger=ACCESS):
        middleware(RequestFactory().post("/documents/1/confirm"))
        middleware(RequestFactory().get("/healthz"))
    records = [record for record in caplog.records if record.name == ACCESS]
    assert len(records) == 2
    first = records[0]
    assert (first.levelname, first.getMessage()) == ("INFO", "request")
    assert (first.__dict__["method"], first.__dict__["path"], first.__dict__["status"]) == (
        "POST",
        "/documents/1/confirm",
        404,
    )
    assert type(first.__dict__["duration_ms"]) is int
    assert first.__dict__["duration_ms"] >= 0
    assert (records[1].__dict__["method"], records[1].__dict__["path"]) == ("GET", "/healthz")


def test_the_access_line_is_one_json_line_with_the_request_id() -> None:
    with json_lines(ACCESS) as stream:
        response = answering(503)(RequestFactory().get("/x", headers={"X-Request-ID": "req-1"}))
    lines = parsed(stream)
    assert len(lines) == 1
    assert set(lines[0]) == {"ts", "level", "logger", "pid", "message", "request_id", *FIELDS[9:13]}
    assert (lines[0]["logger"], lines[0]["request_id"], lines[0]["status"]) == (ACCESS, "req-1", 503)
    assert lines[0]["request_id"] == response["X-Request-ID"]


def test_the_query_the_cookie_and_the_authorization_are_not_logged() -> None:
    factory = RequestFactory()
    factory.cookies["esg_session"] = "COOKIE-SECRET"
    request = factory.post(
        "/x?token=QUERY-SECRET",
        data=b'{"password": "BODY-SECRET"}',
        content_type="application/json",
        headers={"Authorization": "Bearer HEADER-SECRET", "User-Agent": "AGENT-SECRET"},
    )
    with json_lines(ACCESS) as stream:
        answering()(request)
    text = stream.getvalue()
    assert parsed(stream)[0]["path"] == "/x"
    assert "SECRET" not in text
    assert "token" not in text


def test_the_settings_put_the_middleware_first_and_use_the_json_config() -> None:
    assert settings.MIDDLEWARE == [
        "esgapi.core.observability.middleware.RequestIdMiddleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
        "esgapi.core.tenancy.middleware.TenantMiddleware",
    ]
    assert logging_config() == settings.LOGGING


def test_through_the_configured_chain_healthz_carries_the_header(client: Client) -> None:
    """설정에 걸린 사슬을 지난다. /healthz 는 트랜잭션을 열지 않는 경로라 DB 없이 돈다."""
    made = client.get("/api/healthz")
    assert made.status_code == 200
    assert HEX32.fullmatch(made["X-Request-ID"])
    with json_lines(ACCESS) as stream:
        echoed = client.get("/api/healthz?probe=QUERY-SECRET", headers={"X-Request-ID": "probe-1"})
    assert echoed["X-Request-ID"] == "probe-1"
    lines = parsed(stream)
    assert len(lines) == 1
    assert (lines[0]["request_id"], lines[0]["method"], lines[0]["path"], lines[0]["status"]) == (
        "probe-1",
        "GET",
        "/api/healthz",
        200,
    )
    assert "QUERY-SECRET" not in stream.getvalue()
    assert context.current_request_id() is None


# ── CA: 접근 줄의 user_id(인증된 요청만) ────────────────────────────────


class _Authed:
    """인증(SessionCookie)이 request.auth 에 넣는 세션의 흉내 — 접근 줄은 user_id 칸만 읽는다."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id


def authenticating(user_id: str | None) -> RequestIdMiddleware:
    def inner(request: HttpRequest) -> HttpResponse:
        if user_id is not None:
            setattr(request, "auth", _Authed(user_id))  # noqa: B010  (ninja 가 인증 뒤 싣는 칸)
        return HttpResponse(status=200)

    return RequestIdMiddleware(inner)


def test_the_access_line_carries_the_user_id_of_an_authenticated_request() -> None:
    with json_lines(ACCESS) as stream:
        authenticating("42")(RequestFactory().get("/sites"))
        authenticating(None)(RequestFactory().get("/healthz"))
        authenticating("not-a-number")(RequestFactory().get("/x"))
    lines = parsed(stream)
    assert [line.get("user_id") for line in lines] == [42, None, None]
    assert all(set(line) <= set(FIELDS) for line in lines)


def test_the_access_line_user_id_is_the_same_for_both_ways() -> None:
    """(K2b) 두 길(Bearer 의 Principal·옛 교환 쿠키의 Session)이 같은 뜻의 user_id 를 싣는다. 토큰·username 글자 0."""
    from datetime import UTC, datetime

    from esgapi.core.auth.principal import Principal
    from esgapi.core.tenancy.session import Session

    ways: list[object] = [
        Principal(user_id="42", company_id=7, kind="service", is_initial=False, via="bearer"),
        Session(user_id="42", tenant_id="tenant-a", company_id=7, role="editor", expires_at=datetime.now(UTC)),
    ]

    def answering_as(auth: object) -> RequestIdMiddleware:
        def inner(request: HttpRequest) -> HttpResponse:
            setattr(request, "auth", auth)  # noqa: B010  (ninja 가 인증 뒤 싣는 칸)
            return HttpResponse(status=200)

        return RequestIdMiddleware(inner)

    with json_lines(ACCESS) as stream:
        for auth in ways:
            answering_as(auth)(RequestFactory().get("/sites"))
    lines = parsed(stream)
    assert [line["user_id"] for line in lines] == [42, 42]
    assert "tenant-a" not in stream.getvalue() and "editor" not in stream.getvalue()


# ── 접근 줄의 오류 code(밴드 E2 ⑤) ──


def _answer(response: HttpResponse) -> RequestIdMiddleware:
    return RequestIdMiddleware(lambda request: response)


def _access(caplog: pytest.LogCaptureFixture, response: HttpResponse) -> dict[str, Any]:
    with caplog.at_level(logging.INFO, logger=ACCESS):
        _answer(response)(RequestFactory().get("/sites"))
    (record,) = [record for record in caplog.records if record.name == ACCESS]
    return record.__dict__


def test_an_error_response_puts_its_code_on_the_access_record(caplog: pytest.LogCaptureFixture) -> None:
    body = {"error": {"code": "NO_SESSION", "message": "m", "fields": None, "legacyCode": "no_session"}}
    record = _access(caplog, JsonResponse(body, status=401))
    assert (record["status"], record["code"]) == (401, "NO_SESSION")


def test_only_the_code_is_taken_not_the_message_or_fields(caplog: pytest.LogCaptureFixture) -> None:
    body = {"error": {"code": "VALIDATION_ERROR", "message": "secret-m", "fields": {"secretField": ["x"]}}}
    record = _access(caplog, JsonResponse(body, status=422))
    assert record["code"] == "VALIDATION_ERROR"
    assert "secret" not in json.dumps({k: v for k, v in record.items() if k in ("code", "method", "path", "status")})


@pytest.mark.parametrize(
    "response",
    [
        JsonResponse({"status": "ok"}, status=200),
        HttpResponse(b"not json", status=500),
        JsonResponse({"detail": "x"}, status=404),
        HttpResponse(b"{broken", status=400, content_type="application/json"),
    ],
    ids=["ok", "text-500", "other-shape", "broken-json"],
)
def test_no_code_when_the_body_is_not_the_error_shape(caplog: pytest.LogCaptureFixture, response: HttpResponse) -> None:
    assert "code" not in _access(caplog, response)
