"""request ID 와 일감의 id 를 싣는 자리(esgapi/core/observability/context.py). 순수 층."""

import inspect
import re

import pytest

from esgapi.core.observability import context

HEX32 = re.compile(r"[0-9a-f]{32}")


def test_the_header_name() -> None:
    assert context.REQUEST_ID_HEADER == "X-Request-ID"


@pytest.mark.parametrize("raw", ["abc-123_.X", "a", "a" * 64])
def test_a_well_formed_id_is_kept_as_it_is(raw: str) -> None:
    assert context.accept_request_id(raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "has space",
        " ",
        "a" * 65,
        "한글",
        "line\nbreak",
        "trailing-newline\n",
        "semi;colon",
        "a,b",  # 같은 헤더가 둘 오면 Django 가 쉼표로 잇는다
        'quo"te',
    ],
)
def test_anything_else_is_dropped_and_a_new_id_is_made(raw: str | None) -> None:
    made = context.accept_request_id(raw)
    assert made != raw
    assert HEX32.fullmatch(made)


def test_a_made_id_is_different_every_time() -> None:
    assert len({context.new_request_id() for _ in range(50)}) == 50
    assert context.accept_request_id(None) != context.accept_request_id(None)


def test_the_request_id_is_seen_only_while_bound() -> None:
    assert context.current_request_id() is None
    token = context.bind_request_id("req-1")
    try:
        assert context.current_request_id() == "req-1"
    finally:
        context.unbind_request_id(token)
    assert context.current_request_id() is None


def test_the_task_is_seen_only_while_bound() -> None:
    assert context.current_task() is None
    context.bind_task(task_id="t-1", task_name="jobs.parse", job_id="job-1")
    try:
        assert context.current_task() == {"task_id": "t-1", "task_name": "jobs.parse", "job_id": "job-1"}
    finally:
        context.unbind_task()
    assert context.current_task() is None


def test_without_a_job_id_there_is_no_such_field() -> None:
    context.bind_task(task_id="t-1", task_name="jobs.parse", job_id=None)
    try:
        assert context.current_task() == {"task_id": "t-1", "task_name": "jobs.parse"}
    finally:
        context.unbind_task()


def test_what_is_handed_out_is_a_copy() -> None:
    context.bind_task(task_id="t-1", task_name="jobs.parse", job_id="job-1")
    try:
        handed = context.current_task()
        assert handed is not None
        handed["tenant"] = "tenant-a"
        assert context.current_task() == {"task_id": "t-1", "task_name": "jobs.parse", "job_id": "job-1"}
    finally:
        context.unbind_task()


def test_bind_task_has_no_place_for_a_tenant() -> None:
    """인자는 이름으로만 받는 넷이다(X1b-1 +1: run_id). 테넌트를 받을 자리가 없다."""
    parameters = inspect.signature(context.bind_task).parameters
    assert list(parameters) == ["task_id", "task_name", "job_id", "run_id"]
    assert [parameter.kind for parameter in parameters.values()] == [inspect.Parameter.KEYWORD_ONLY] * 4


def test_a_run_id_gets_its_own_field_and_never_the_job_id_one() -> None:
    """실행 태스크(runs.execute — X1b-1)는 run_id 칸에 싣는다. job_id 칸에 섞지 않는다."""
    context.bind_task(task_id="t-2", task_name="runs.execute", job_id=None, run_id="41")
    try:
        assert context.current_task() == {"task_id": "t-2", "task_name": "runs.execute", "run_id": "41"}
    finally:
        context.unbind_task()
