"""로그 한 줄을 JSON 하나로 낸다. 순수: 표준 라이브러리와 context 만 쓴다(django·celery·gunicorn 을 모른다).

    FIELDS                     줄에 실릴 수 있는 칸의 **닫힌 목록**(스물둘 — X1b-1 +1: 실행 태스크의 run_id).
                               이 밖의 칸은 어떤 줄에도 없다
    JsonFormatter              logging 의 포매터. 기록 하나를 한 줄 JSON 으로
    logging_config()           Django(`LOGGING`)와 워커(config/celery.py 의 setup_logging 신호)가 쓰는 설정
    gunicorn_logging_config()  gunicorn(`logconfig_dict`)이 쓰는 설정

★ 칸은 닫힌 목록이다. `extra=` 로 실려 온 이름은 접근 줄의 다섯(method·path·status·duration_ms·code)과 감사 줄의 여섯
  (AUDIT_FIELDS — event·user_kind 는 짧은 소문자 이름, 네 id 는 정수만. D9: 전에는 감사 로그의 extra 를 버렸다)만
  싣는다. 접근 줄의 user_id 는 인증된 요청만(정수). 테넌트 id·역할·username·이름·토큰·비밀번호·쿠키·헤더·쿼리 문자열·
  본문의 칸은 없다. 칸을 늘리려면 FIELDS 와 그 테스트(core/tests/test_observability_jsonlog.py)를 같이 고친다.
★ 글(message)과 예외(exc)는 부른 쪽이 적은 그대로다. 거기에 무엇을 적는지는 이 포매터가 거르지 못한다.
"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from esgapi.core.observability.context import current_request_id, current_task

# code = 오류 응답의 error.code(밴드 E2). 대문자 snake 글자만 싣고 꼴에 안 맞으면 버린다(CODE).
ACCESS_FIELDS = ("method", "path", "status", "duration_ms", "code")
# 감사 줄(로거 esgapi.auth — user/service/services/login.py 의 note)의 칸. 이름 칸 둘은 NAME 꼴의 글자, id 넷은 정수.
AUDIT_NAME_FIELDS = ("event", "user_kind")
AUDIT_ID_FIELDS = ("user_id", "company_id", "actor_user_id", "target_user_id")
AUDIT_FIELDS = (*AUDIT_NAME_FIELDS, *AUDIT_ID_FIELDS)
NAME = re.compile(r"[a-z][a-z_]{0,39}")
CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
FIELDS = (
    "ts",
    "level",
    "logger",
    "pid",
    "message",
    "request_id",
    "task_id",
    "task_name",
    "job_id",
    *ACCESS_FIELDS,
    *AUDIT_FIELDS,
    "run_id",  # X1b-1: 실행 태스크(runs.execute)의 실행 id — 끝에 둔다(앞 칸의 자리를 밀지 않게)
    "exc",
)


def _whole(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


class JsonFormatter(logging.Formatter):
    """기록 하나 → 한 줄 JSON. 던지지 않는다(글을 못 지으면 `repr(record.msg)` 를 쓴다)."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception:
            message = repr(record.msg)
        line: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds")[:-6] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "pid": record.process,
            "message": message,
        }
        # 요청 안이면 contextvar 에 있다. Django 가 미들웨어 밖에서 내는 4xx·5xx 의 줄은 요청 객체를 싣고 온다.
        request_id = current_request_id() or getattr(getattr(record, "request", None), "request_id", None)
        if isinstance(request_id, str):
            line["request_id"] = request_id
        task = current_task()
        if task is not None:
            line.update(task)
        for name in ACCESS_FIELDS:
            value = record.__dict__.get(name)
            if name == "code":
                if isinstance(value, str) and CODE.fullmatch(value):
                    line[name] = value
            elif isinstance(value, str) or _whole(value):
                line[name] = value
        for name in AUDIT_NAME_FIELDS:
            value = record.__dict__.get(name)
            if isinstance(value, str) and NAME.fullmatch(value):
                line[name] = value
        for name in AUDIT_ID_FIELDS:
            value = record.__dict__.get(name)
            if _whole(value):
                line[name] = value
        if record.exc_info and record.exc_info[0] is not None:
            line["exc"] = self.formatException(record.exc_info)
        return json.dumps(line, ensure_ascii=False, separators=(",", ":"))


def logging_config() -> dict[str, Any]:
    """기록은 표준 출력으로, 한 줄 JSON 으로. 컨테이너 플랫폼이 모아 간다. 수준은 INFO."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": "esgapi.core.observability.jsonlog.JsonFormatter"}},
        "handlers": {"stdout": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout", "formatter": "json"}},
        "root": {"handlers": ["stdout"], "level": "INFO"},
    }


def gunicorn_logging_config() -> dict[str, Any]:
    """gunicorn 자신의 줄(gunicorn.error)을 같은 꼴로 낸다. 접근 줄(gunicorn.access)은 내지 않는다.

    접근 기록은 미들웨어가 요청마다 한 줄로 낸다(esgapi.access). gunicorn 은 logconfig_dict 가 있으면 accesslog 가
    꺼져 있어도 gunicorn.access 로 기록을 보낸다. 그래서 그 로거를 처리기 없이, 위로 넘기지 않게 둔다.
    """
    config = logging_config()
    config["loggers"] = {
        "gunicorn.error": {"level": "INFO", "handlers": ["stdout"], "propagate": False, "qualname": "gunicorn.error"},
        "gunicorn.access": {"level": "INFO", "handlers": [], "propagate": False, "qualname": "gunicorn.access"},
    }
    return config
