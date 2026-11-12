# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""워커의 로그: Celery 의 신호 셋에 건 받는 쪽(esgapi/config/celery.py). 순수 층: 워커도 브로커도 띄우지 않는다.

신호를 손으로 쏜다(`task_prerun.send(…)`). 진짜 워커(prefork 의 자식)에서 그 신호가 서는지는 컨테이너 층이 잰다.
★ 진짜 `logging.config.dictConfig` 를 부르지 않는다(부르면 뿌리 로거에서 pytest 의 처리기가 떨어진다).
  탐지기로 바꿔 끼운다.
"""

import json
import logging
import logging.config
from typing import Any

import pytest
from celery.signals import setup_logging, task_postrun, task_prerun

from esgapi.config import celery as celery_config
from esgapi.core.observability import context
from esgapi.core.observability.jsonlog import FIELDS, JsonFormatter, logging_config

NOTE = {"tenant_id": "tenant-a", "job_id": "job-1"}  # 쪽지의 kwargs(core/resources/queue.py 가 싣는 둘)


class FakeTask:
    name = "jobs.parse"


def line_now() -> str:
    """지금 로그 한 줄을 내면 나갈 글."""
    record = logging.getLogger("esgapi.test").makeRecord("esgapi.test", logging.INFO, __file__, 1, "x", (), None)
    return JsonFormatter().format(record)


def test_our_receivers_are_connected_to_the_three_signals() -> None:
    for signal, receiver in (
        (setup_logging, celery_config.on_setup_logging),
        (task_prerun, celery_config.on_task_prerun),
        (task_postrun, celery_config.on_task_postrun),
    ):
        assert any(connected is receiver for _, connected in signal.receivers or []), receiver.__name__


def test_while_a_task_runs_the_lines_carry_the_task_and_the_job_and_never_the_tenant() -> None:
    task = FakeTask()
    assert context.current_task() is None
    task_prerun.send(sender=task, task_id="t-1", task=task, args=(), kwargs=dict(NOTE))
    try:
        assert context.current_task() == {"task_id": "t-1", "task_name": "jobs.parse", "job_id": "job-1"}
        line = line_now()
    finally:
        task_postrun.send(
            sender=task, task_id="t-1", task=task, args=(), kwargs=dict(NOTE), retval=None, state="SUCCESS"
        )
    assert context.current_task() is None
    parsed = json.loads(line)
    assert (parsed["task_id"], parsed["task_name"], parsed["job_id"]) == ("t-1", "jobs.parse", "job-1")
    assert set(parsed) <= set(FIELDS)
    assert "tenant-a" not in line
    assert "tenant" not in line
    assert "task_id" not in json.loads(line_now())  # 끝난 뒤의 줄에는 없다


class FakeRunTask:
    name = "runs.execute"


def test_a_run_task_carries_the_run_id_as_text_and_never_the_company() -> None:
    """실행 태스크(X1b-1)의 쪽지 `{company_id, run_id}`: run_id 는 run_id 칸에, 회사는 싣지 않는다.
    글자가 아니면 뺀다."""
    task = FakeRunTask()
    note = {"company_id": "7", "run_id": "41"}
    task_prerun.send(sender=task, task_id="t-2", task=task, args=(), kwargs=dict(note))
    try:
        assert context.current_task() == {"task_id": "t-2", "task_name": "runs.execute", "run_id": "41"}
        line = line_now()
    finally:
        task_postrun.send(
            sender=task, task_id="t-2", task=task, args=(), kwargs=dict(note), retval=None, state="SUCCESS"
        )
    parsed = json.loads(line)
    assert parsed["run_id"] == "41"
    assert "company_id" not in parsed and "job_id" not in parsed
    task_prerun.send(sender=task, task_id="t-3", task=task, args=(), kwargs={"company_id": "7", "run_id": 41})
    try:
        assert context.current_task() == {"task_id": "t-3", "task_name": "runs.execute"}  # 정수면 칸을 만들지 않는다
    finally:
        task_postrun.send(sender=task, task_id="t-3", task=task, args=(), kwargs={}, retval=None, state="SUCCESS")


@pytest.mark.parametrize("kwargs", [{}, {"tenant_id": "tenant-a"}, {"job_id": 123}, {"job_id": None}, None, ["job-1"]])
def test_without_a_text_job_id_in_the_note_there_is_no_job_field(kwargs: Any) -> None:
    celery_config.on_task_prerun(task_id="t-2", task=FakeTask(), kwargs=kwargs)
    try:
        assert context.current_task() == {"task_id": "t-2", "task_name": "jobs.parse"}
        assert "tenant-a" not in line_now()
    finally:
        celery_config.on_task_postrun()
    assert context.current_task() is None


def test_setting_up_logging_applies_our_config_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """워커가 로그를 세울 때의 신호. 받는 쪽이 있으면 Celery 는 자기 꼴로 뿌리 로거를 세우지 않는다."""
    applied: list[dict[str, Any]] = []
    monkeypatch.setattr(logging.config, "dictConfig", applied.append)
    setup_logging.send(
        sender=None, loglevel=logging.INFO, logfile=None, format="[%(asctime)s] %(message)s", colorize=False
    )
    assert len(applied) == 1
    config = applied[0]
    # 자식 프로세스가 죽은 줄을 내는 로거. Celery 가 걸던 수준(ERROR) 그대로, 같은 처리기로, 위로 넘기지 않게.
    assert config.pop("loggers") == {"multiprocessing": {"level": "ERROR", "handlers": ["stdout"], "propagate": False}}
    assert config == logging_config()  # 그 밖은 Django 가 쓰는 설정과 같다
    assert "loggers" not in logging_config()  # Django 의 LOGGING 에는 번지지 않는다
