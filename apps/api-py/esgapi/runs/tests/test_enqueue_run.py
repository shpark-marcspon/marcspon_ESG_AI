"""실행의 큐 넣기(core/resources/queue.py 의 enqueue_run). 순수 층: 가짜 앱을 끼운다. 브로커도 DB 도 없다.
(시험이 runs 에 있는 까닭: core/tests 가 runs 를 import 하는 예외 줄을 늘리지 않는다 — 발주서 개정 4 N10.)"""

import logging
from typing import Any

import pytest

from esgapi.config.env import BrokerSettings
from esgapi.core.calc.jobs import RUN_TASK_NAME
from esgapi.core.resources import queue as hooks

BROKER = BrokerSettings(
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="http://queue:9324/000000000000/esg-jobs",
    secure=False,
)


class FakeApp:
    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.error = error

    def send_task(self, *args: Any, **kwargs: Any) -> None:
        self.sent.append((args, kwargs))
        if self.error is not None:
            raise self.error


def test_the_note_carries_the_task_name_and_two_ids_as_text(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FakeApp()
    monkeypatch.setattr(hooks, "celery_app", lambda: app)
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    hooks.enqueue_run(company_id=9876543, run_id=41)
    assert RUN_TASK_NAME == "runs.execute"
    assert app.sent == [
        (("runs.execute",), {"kwargs": {"company_id": "9876543", "run_id": "41"}, "queue": "esg-jobs", "retry": False})
    ]


def test_without_a_broker_nothing_is_sent_and_one_line_says_so(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    app = FakeApp()
    monkeypatch.setattr(hooks, "celery_app", lambda: app)
    monkeypatch.setattr(hooks, "broker_settings", lambda: None)
    with caplog.at_level(logging.WARNING, logger=hooks.logger.name):
        hooks.enqueue_run(company_id=7, run_id=41)
    assert app.sent == []
    assert [r.getMessage().split(" ")[0] for r in caplog.records] == ["queue_unconfigured"]


def test_a_failed_send_is_logged_and_raised_as_is(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class Unreachable(Exception):
        pass

    error = Unreachable("sqs://queue:9324 에 닿지 않는다")
    monkeypatch.setattr(hooks, "celery_app", lambda: FakeApp(error))
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    with caplog.at_level(logging.ERROR, logger=hooks.logger.name), pytest.raises(Unreachable) as raised:
        hooks.enqueue_run(company_id=7, run_id=41)
    assert raised.value is error
    (line,) = [r.getMessage() for r in caplog.records]
    assert line == "queue_send_failed run_id=41 error=Unreachable"  # 주소는 싣지 않는다
