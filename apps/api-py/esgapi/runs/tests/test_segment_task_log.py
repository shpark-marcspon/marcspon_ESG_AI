# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""구획 쪽지(`runs.segment` — RM1b, 7a 덧붙임 1-5)도 지금의 `on_task_prerun`(config/celery.py — 0줄)이 run_id 를 싣는다.
순수 층: 신호를 손으로 쏜다(core/tests/test_observability_worker.py 와 같은 꼴). 쪽지의 회사·run_attempt 는 싣지 않는다.
"""

import json
import logging

import pytest
from celery.signals import task_postrun, task_prerun

from esgapi.core.observability import context
from esgapi.core.observability.jsonlog import JsonFormatter
from esgapi.core.resources import queue
from esgapi.runs import tasks


class FakeSegmentTask:
    name = tasks.segment_task.name


def line_now() -> str:
    record = logging.getLogger("esgapi.test").makeRecord("esgapi.test", logging.INFO, __file__, 1, "x", (), None)
    return JsonFormatter().format(record)


def test_a_segment_note_carries_the_run_id_and_never_the_company_or_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, object]] = []

    class FakeApp:
        def send_task(self, name: str, **kwargs: object) -> None:
            sent.append({"name": name, **kwargs})

    class Broker:
        queue_name = "esg-runs"

    monkeypatch.setattr(queue, "celery_app", FakeApp)
    monkeypatch.setattr(queue, "broker_settings", Broker)
    queue.enqueue_segment(company_id=7, run_id=41, run_attempt=2, countdown=5)
    assert sent == [
        {
            "name": "runs.segment",
            "kwargs": {"company_id": "7", "run_id": "41", "run_attempt": "2"},  # 십진 숫자 글자 셋
            "queue": "esg-runs",
            "retry": False,
            "countdown": 5,
        }
    ]

    task = FakeSegmentTask()
    note = sent[0]["kwargs"]
    assert isinstance(note, dict)
    task_prerun.send(sender=task, task_id="t-9", task=task, args=(), kwargs=dict(note))
    try:
        assert context.current_task() == {"task_id": "t-9", "task_name": "runs.segment", "run_id": "41"}
        line = line_now()
    finally:
        task_postrun.send(sender=task, task_id="t-9", task=task, args=(), kwargs={}, retval=None, state="SUCCESS")
    parsed = json.loads(line)
    assert parsed["run_id"] == "41"
    assert "company_id" not in parsed and "run_attempt" not in parsed
    assert context.current_task() is None
