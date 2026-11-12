"""request ID 와 로그를 진짜 경로에서 잰다. 업무 층: 요청이 미들웨어 둘(request ID, 테넌트)을 다 지나 DB 에 닿는다.

순수 층(test_observability_middleware.py)은 미들웨어 하나와 `/healthz` 만 본다. 여기서는 테넌트 미들웨어가
트랜잭션을 여는 경로의 401·404 를 본다.
"""

import io
import json
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import pytest
from django.test import Client

from esgapi.config.env import BrokerSettings
from esgapi.core.models import DocumentRow
from esgapi.core.observability.jsonlog import FIELDS, JsonFormatter
from esgapi.core.resources import queue
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.models import JobRow
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

Capture = Callable[..., AbstractContextManager[list[Callable[[], Any]]]]
PDF = b"%PDF-1.7 synthetic " + b"x" * 81  # 100바이트. 지어낸 바이트다(PDF 가 아니다)
BROKER = BrokerSettings(
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="http://queue:9324/000000000000/esg-jobs",
    secure=False,
)


class BrokerDown(Exception):
    pass


class DeadApp:
    """send_task 가 늘 던지는 가짜 Celery 앱(브로커에 못 닿는 꼴). 진짜 앱으로는 부르지 않는다."""

    def send_task(self, *args: Any, **kwargs: Any) -> None:
        raise BrokerDown("가짜 브로커가 죽었다 sqs://queue:9324")


def test_a_401_without_a_session_carries_the_header(client: Client) -> None:
    response = client.get("/api/me")
    assert response.status_code == 401
    assert len(response["X-Request-ID"]) == 32
    assert "request" not in str(response.json()).lower()  # 오류 본문에는 싣지 않는다(헤더에만)


def test_a_404_for_an_unknown_path_echoes_the_id_and_djangos_late_record_can_find_it(
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="django.request"):
        response = client.get("/api/no/such/path", headers={"X-Request-ID": "it-404"})
    assert response.status_code == 404
    assert response["X-Request-ID"] == "it-404"
    # Django 의 「Not Found: …」 줄은 미들웨어가 끝난 뒤에 난다. 그 기록이 싣고 온 요청 객체에 id 가 있어야 한다.
    late = [record for record in caplog.records if record.name == "django.request"]
    assert [record.getMessage() for record in late] == ["Not Found: /api/no/such/path"]
    assert getattr(late[0].__dict__["request"], "request_id", None) == "it-404"


def test_when_the_hook_cannot_reach_the_broker_the_line_names_the_job(
    client: Client,
    tenants: None,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: Capture,
) -> None:
    """올림 확인의 커밋 뒤 갈고리가 브로커에 못 닿는다. 응답은 200 이고, 기록 한 줄에 그 일감의 id 가 있다.

    ★ 이 층에서는 바깥 커밋이 오지 않아 갈고리를 요청이 끝난 뒤에 손으로 돌린다(execute=True). 그래서 이 줄에는
      request_id 가 없다. 진짜 요청에서 그 줄에 request_id 가 실리는지는 컨테이너 층의 로그가 잰다.
    """
    storage = plug_storage(monkeypatch, FakeStorage())
    monkeypatch.setattr(queue, "celery_app", lambda: DeadApp())
    monkeypatch.setattr(queue, "broker_settings", lambda: BROKER)
    login(client)
    created = client.post(
        "/api/documents", data={"fileName": "보고서 2025.pdf", "sizeBytes": len(PDF)}, content_type="application/json"
    )
    document_id: int = created.json()["document"]["id"]
    storage.put(DocumentRow.unscoped.get(pk=document_id).storage_key, PDF)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    queue.logger.addHandler(handler)
    try:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post(f"/api/documents/{document_id}/confirm")
    finally:
        queue.logger.removeHandler(handler)

    assert response.status_code == 200  # 갈고리가 던져도 요청은 끝났다(robust=True)
    assert len(callbacks) == 1
    job = JobRow.unscoped.get()
    assert job.status == "queued"
    lines = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(lines) == 1
    assert (lines[0]["level"], lines[0]["logger"]) == ("ERROR", queue.logger.name)
    assert lines[0]["message"] == f"queue_send_failed job_id={job.id} kind=parse error=BrokerDown"
    assert set(lines[0]) <= set(FIELDS)
    for absent in ("tenant-a", "가짜 브로커", "sqs://"):
        assert absent not in stream.getvalue()
