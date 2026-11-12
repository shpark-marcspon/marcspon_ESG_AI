"""한 줄 JSON 포매터와 logging 설정(esgapi/core/observability/jsonlog.py). 순수 층.

★ 진짜 `logging.config.dictConfig` 를 부르지 않는다(부르면 뿌리 로거에서 pytest 의 처리기가 떨어진다).
  포매터의 출력은 기록을 손으로 지어 `JsonFormatter().format(record)` 로 잰다.
"""

import json
import logging
import re
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.observability import context
from esgapi.core.observability.jsonlog import (
    ACCESS_FIELDS,
    FIELDS,
    JsonFormatter,
    gunicorn_logging_config,
    logging_config,
)

API_PY_DIR = Path(__file__).resolve().parents[3]

# 이름은 X1b-1 앞의 것이다(셈은 스물둘 — +1 run_id).
TWENTY_ONE = [
    "ts",
    "level",
    "logger",
    "pid",
    "message",
    "request_id",
    "task_id",
    "task_name",
    "job_id",
    "method",
    "path",
    "status",
    "duration_ms",
    "code",
    "event",
    "user_kind",
    "user_id",
    "company_id",
    "actor_user_id",
    "target_user_id",
    "run_id",
    "exc",
]


class FakeRequest:
    """Django 가 4xx·5xx 의 기록에 싣는 요청 객체의 흉내. 미들웨어가 request_id 를 실어 둔 꼴이다."""

    def __init__(self, request_id: object) -> None:
        self.request_id = request_id
        self.COOKIES = {"esg_session": "COOKIE-SECRET"}


def record_of(
    msg: object,
    *args: object,
    level: int = logging.INFO,
    extra: dict[str, Any] | None = None,
    exc_info: Any = None,
    name: str = "esgapi.test",
) -> logging.LogRecord:
    return logging.getLogger(name).makeRecord(name, level, __file__, 1, msg, args, exc_info, extra=extra)


def line_of(msg: object, *args: object, **more: Any) -> str:
    return JsonFormatter().format(record_of(msg, *args, **more))


def test_the_fields_are_exactly_these_twenty_one() -> None:
    assert list(FIELDS) == TWENTY_ONE
    assert len(set(FIELDS)) == 22  # E2 +1: 접근 줄의 code · X1b-1 +1: 실행 태스크의 run_id
    assert list(ACCESS_FIELDS) == ["method", "path", "status", "duration_ms", "code"]


def test_a_plain_line_is_one_line_of_json_with_the_five_fixed_fields() -> None:
    line = line_of("일감 %s 을 끝냈다", "job-1", level=logging.WARNING, name="esgapi.some.module")
    assert "\n" not in line
    parsed = json.loads(line)
    assert list(parsed) == ["ts", "level", "logger", "pid", "message"]
    assert (parsed["level"], parsed["logger"], parsed["message"]) == (
        "WARNING",
        "esgapi.some.module",
        "일감 job-1 을 끝냈다",
    )
    assert type(parsed["pid"]) is int
    assert "일감" in line  # 한글을 \u 로 바꾸지 않는다


def test_newlines_quotes_and_backslashes_stay_inside_one_line() -> None:
    line = line_of('첫 줄\n둘째 "줄"\t\\ 끝')
    assert "\n" not in line
    assert json.loads(line)["message"] == '첫 줄\n둘째 "줄"\t\\ 끝'


def test_the_timestamp_is_utc_in_milliseconds_ending_with_z() -> None:
    record = record_of("x")
    record.created = 1_791_886_922.8704  # 2026-10-13T10:22:02.870Z
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["ts"] == "2026-10-13T10:22:02.870Z"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", json.loads(line_of("x"))["ts"])


def test_extra_names_outside_the_list_are_not_carried() -> None:
    line = line_of(
        "x",
        extra={
            "password": "PASSWORD-SECRET",
            "cookie": "COOKIE-SECRET",
            "body": "BODY-SECRET",
            "tenant_id": "tenant-a",
            "user_id": "user-1",
            "status_code": 404,
            "data": {"kwargs": "TASK-KWARGS"},
            "request": object(),
        },
    )
    assert set(json.loads(line)) == {"ts", "level", "logger", "pid", "message"}
    for secret in ("SECRET", "tenant-a", "user-1", "TASK-KWARGS"):
        assert secret not in line


def test_the_four_access_fields_are_carried_when_they_are_text_or_whole_numbers() -> None:
    parsed = json.loads(
        line_of("request", extra={"method": "GET", "path": "/healthz", "status": 200, "duration_ms": 3})
    )
    assert list(parsed)[5:] == ["method", "path", "status", "duration_ms"]
    assert (parsed["method"], parsed["path"], parsed["status"], parsed["duration_ms"]) == ("GET", "/healthz", 200, 3)
    assert set(parsed) <= set(FIELDS)


def test_an_access_field_of_another_type_is_dropped() -> None:
    parsed = json.loads(line_of("x", extra={"method": b"GET", "path": ["/a"], "status": True, "duration_ms": 1.5}))
    assert set(parsed) == {"ts", "level", "logger", "pid", "message"}


def test_inside_a_request_the_line_carries_the_request_id() -> None:
    token = context.bind_request_id("req-1")
    try:
        assert json.loads(line_of("x"))["request_id"] == "req-1"
    finally:
        context.unbind_request_id(token)
    assert "request_id" not in json.loads(line_of("x"))


def test_a_record_that_brings_the_request_object_carries_its_id() -> None:
    """Django 는 4xx·5xx 의 줄을 미들웨어가 끝난 뒤에 낸다(contextvar 는 비었다). 그 기록은 요청 객체를 싣고 온다."""
    line = line_of("Not Found: %s", "/x", extra={"request": FakeRequest("req-late"), "status_code": 404})
    parsed = json.loads(line)
    assert parsed["request_id"] == "req-late"
    assert set(parsed) == {"ts", "level", "logger", "pid", "message", "request_id"}
    assert "COOKIE-SECRET" not in line


def test_the_bound_id_wins_over_the_one_on_the_request_object() -> None:
    token = context.bind_request_id("req-bound")
    try:
        assert json.loads(line_of("x", extra={"request": FakeRequest("req-late")}))["request_id"] == "req-bound"
    finally:
        context.unbind_request_id(token)


def test_a_request_id_that_is_not_text_is_not_carried() -> None:
    assert "request_id" not in json.loads(line_of("x", extra={"request": FakeRequest(12345)}))
    assert "request_id" not in json.loads(line_of("x", extra={"request": object()}))


def test_inside_a_task_the_line_carries_the_task_and_the_job() -> None:
    context.bind_task(task_id="t-1", task_name="jobs.parse", job_id="job-1")
    try:
        parsed = json.loads(line_of("x"))
    finally:
        context.unbind_task()
    assert (parsed["task_id"], parsed["task_name"], parsed["job_id"]) == ("t-1", "jobs.parse", "job-1")
    assert set(parsed) <= set(FIELDS)
    assert "task_id" not in json.loads(line_of("x"))


def test_inside_a_run_task_the_line_carries_the_run_id() -> None:
    context.bind_task(task_id="t-2", task_name="runs.execute", job_id=None, run_id="41")
    try:
        parsed = json.loads(line_of("x"))
    finally:
        context.unbind_task()
    assert (parsed["task_name"], parsed["run_id"]) == ("runs.execute", "41")
    assert "job_id" not in parsed
    assert set(parsed) <= set(FIELDS)


def test_an_exception_goes_into_one_field_on_the_same_line() -> None:
    try:
        raise ValueError("깨진 값")
    except ValueError:
        line = line_of("실패했다", level=logging.ERROR, exc_info=sys.exc_info())
    assert "\n" not in line
    parsed = json.loads(line)
    assert list(parsed) == ["ts", "level", "logger", "pid", "message", "exc"]
    assert parsed["exc"].startswith("Traceback (most recent call last):\n")
    assert parsed["exc"].endswith("ValueError: 깨진 값")
    assert parsed["message"] == "실패했다"


def test_no_exception_no_field() -> None:
    assert "exc" not in json.loads(line_of("x", exc_info=(None, None, None)))


def test_a_record_whose_message_cannot_be_built_still_yields_one_line() -> None:
    line = line_of("%d 건", "글자")  # getMessage 가 TypeError 를 낸다
    assert "\n" not in line
    assert json.loads(line)["message"] == repr("%d 건")


def test_the_config_is_the_old_one_plus_the_formatter() -> None:
    """수준(INFO)·처리기(하나)·보내는 곳(표준 출력)은 그대로다. 더한 것은 포매터와, 처리기가 그것을 쓴다는 한 칸이다."""
    config = logging_config()
    assert config == {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": "esgapi.core.observability.jsonlog.JsonFormatter"}},
        "handlers": {"stdout": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout", "formatter": "json"}},
        "root": {"handlers": ["stdout"], "level": "INFO"},
    }
    assert f"{JsonFormatter.__module__}.{JsonFormatter.__qualname__}" == config["formatters"]["json"]["()"]
    assert logging_config() is not config  # 부를 때마다 새 dict 다(받은 쪽이 고쳐도 번지지 않는다)


def test_the_gunicorn_config_adds_only_the_two_gunicorn_loggers() -> None:
    config = gunicorn_logging_config()
    loggers = config.pop("loggers")
    assert config == logging_config()
    assert loggers == {
        "gunicorn.error": {"level": "INFO", "handlers": ["stdout"], "propagate": False, "qualname": "gunicorn.error"},
        "gunicorn.access": {"level": "INFO", "handlers": [], "propagate": False, "qualname": "gunicorn.access"},
    }


def test_gunicorn_writes_no_access_log_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    """접근 줄은 미들웨어가 낸다. gunicorn 의 것이 켜지면 요청 하나에 두 줄이고, 그 줄에는 쿼리 문자열이 든다."""
    monkeypatch.setenv("PORT", "18999")
    conf = runpy.run_path(str(API_PY_DIR / "gunicorn.conf.py"))
    assert conf["accesslog"] is None
    assert conf["logconfig_dict"] == gunicorn_logging_config()
    # logconfig_dict 가 있으면 gunicorn 은 accesslog 가 꺼져 있어도 gunicorn.access 로 기록을 보낸다.
    access = conf["logconfig_dict"]["loggers"]["gunicorn.access"]
    assert access["handlers"] == []
    assert access["propagate"] is False
    assert (conf["bind"], conf["workers"], conf["graceful_timeout"], conf["timeout"]) == ("0.0.0.0:18999", 2, 10, 30)


# ── D9(CA): 감사 줄의 extra 가 JSON 글자에 실린다 ─────────────────────────


def test_the_audit_extra_is_in_the_json_text() -> None:
    """포매터가 낸 JSON 글자를 본다(LogRecord 가 아니다). 이름 칸은 소문자 이름, id 칸은 정수만."""
    extra: dict[str, Any] = {
        "event": "password_reset",
        "user_id": 42,
        "company_id": 7,
        "user_kind": "service",
        "actor_user_id": 9,
        "target_user_id": 42,
    }
    line = line_of("password_reset", extra=extra, name="esgapi.auth")
    parsed = json.loads(line)
    assert {name: parsed[name] for name in extra} == extra
    assert '"actor_user_id":9' in line and '"event":"password_reset"' in line
    assert set(parsed) <= set(FIELDS)


def test_audit_fields_of_another_shape_are_dropped() -> None:
    parsed = json.loads(
        line_of(
            "x",
            extra={
                "event": "Has Space",
                "user_kind": "x" * 60,
                "user_id": "42",
                "company_id": True,
                "actor_user_id": 1.5,
                "target_user_id": None,
            },
        )
    )
    assert set(parsed) == {"ts", "level", "logger", "pid", "message"}


@pytest.mark.parametrize(
    ("code", "kept"),
    [
        ("NO_SESSION", True),
        ("VALIDATION_ERROR", True),
        ("HTTP_405", True),
        ("no_session", False),
        ("NOT FOUND", False),
        ("SECRET-token=abc", False),
        (401, False),
        ("A" * 65, False),
    ],
)
def test_the_access_code_is_kept_only_in_upper_snake(code: object, kept: bool) -> None:
    """밴드 E2: 접근 줄의 code 는 대문자 snake 글자만 싣는다. 그 밖의 글자·수는 버린다."""
    record = logging.LogRecord("esgapi.access", logging.INFO, __file__, 1, "request", None, None)
    record.__dict__.update({"status": 401, "code": code})
    line = json.loads(JsonFormatter().format(record))
    assert ("code" in line) is kept
    if kept:
        assert line["code"] == code
