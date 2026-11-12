"""요청과 일감의 식별자를 로그까지 나르는 자리. 순수: 표준 라이브러리만 쓴다(django·celery 를 모른다).

    REQUEST_ID_HEADER     요청과 응답의 헤더 이름
    accept_request_id     받은 값이 규칙에 맞으면 그 값, 아니면 새로 지은 값. 거절하지 않는다
    bind_request_id …     요청 하나가 도는 동안 그 id 를 싣고 내린다(미들웨어가 부른다)
    bind_task …           태스크 하나가 도는 동안 태스크와 일감·실행의 id 를 싣고 내린다(워커의 신호가 부른다)

값은 contextvars 에 있다: 일꾼 프로세스 하나가 요청(태스크) 하나를 처리하는 동안만 보이고, 내리면 사라진다.
★ 테넌트 id 를 받는 자리가 없다. 로그에 테넌트를 싣지 않는다(jsonlog.py 의 닫힌 목록).
"""

import re
import uuid
from contextvars import ContextVar, Token

REQUEST_ID_HEADER = "X-Request-ID"
# 받은 값을 그대로 응답 헤더와 로그에 싣는다. 그래서 글자와 길이를 좁게 묶는다(줄바꿈·공백·쉼표·따옴표가 없다).
_ACCEPTED = re.compile(r"[A-Za-z0-9._-]{1,64}")

_request_id: ContextVar[str | None] = ContextVar("esgapi_request_id", default=None)
_task: ContextVar[dict[str, str] | None] = ContextVar("esgapi_task", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_request_id(raw: str | None) -> str:
    """받은 값이 규칙에 통째로 맞으면 그 값을, 아니면(없음·빈 값·긴 값·그 밖의 글자) 버리고 새로 지은 값을 돌려준다."""
    if raw is not None and _ACCEPTED.fullmatch(raw) is not None:
        return raw
    return new_request_id()


def bind_request_id(value: str) -> Token[str | None]:
    return _request_id.set(value)


def unbind_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def current_request_id() -> str | None:
    return _request_id.get()


def bind_task(*, task_id: str, task_name: str, job_id: str | None, run_id: str | None = None) -> None:
    """도는 태스크의 id·이름과 일감(또는 흐름의 실행 — X1b-1)의 id 를 싣는다. 없는 id 의 칸은 만들지 않는다.

    실행 id 를 job_id 칸에 섞지 않는다(두 표 run_jobs·run_runs 의 id 를 로그를 읽는 사람이 헷갈리지 않게).
    """
    bound = {"task_id": task_id, "task_name": task_name}
    if job_id is not None:
        bound["job_id"] = job_id
    if run_id is not None:
        bound["run_id"] = run_id
    _task.set(bound)


def unbind_task() -> None:
    _task.set(None)


def current_task() -> dict[str, str] | None:
    bound = _task.get()
    return None if bound is None else dict(bound)
