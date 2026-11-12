# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""쪽지의 꼴과 그 끝 둘. 순수 층: 브로커도 워커도 DB 도 없다(DB 에 닿으면 pytest-django 가 막아 빨개진다).

    갈고리(core/resources/queue.py 의 enqueue_job)가 싣는 kwargs
      → 워커 신호(config/celery.py 의 on_task_prerun)가 로그 맥락에 싣는 job_id 칸
      → 워커 입구(reconcile/tasks.py 의 run_parse_job)가 꼴을 보고 조회 없이 건너뛰는 갈래

★ 쪽지의 두 값은 십진 숫자 **글자**다. on_task_prerun 은 job_id 가 글자일 때만 맥락에 싣는다: 정수로 보내면 그 칸이
  오류 없이 빠진다(아래 반례). config/celery.py 는 import 만 한다(고치지 않는다).
★ 무효 조건: 신호를 손으로 부른다. 진짜 워커(prefork 의 자식)에서 그 신호가 서는지는 컨테이너 층이 잰다.
"""

import logging
from typing import Any

import pytest

from esgapi.config import celery as celery_config
from esgapi.config.env import BrokerSettings, JobSettings
from esgapi.core.observability import context
from esgapi.core.resources import queue as hooks
from esgapi.reconcile import tasks

BROKER = BrokerSettings(
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="http://queue:9324/000000000000/esg-jobs",
    secure=False,
)
SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)


class FakeApp:
    """send_task 가 받은 kwargs 를 적어 두는 가짜 Celery 앱."""

    def __init__(self) -> None:
        self.notes: list[dict[str, Any]] = []

    def send_task(self, *_: Any, kwargs: dict[str, Any], **__: Any) -> None:
        self.notes.append(kwargs)


class FakeTask:
    name = "jobs.parse"


@pytest.fixture
def fake_app(monkeypatch: pytest.MonkeyPatch) -> FakeApp:
    app = FakeApp()
    monkeypatch.setattr(hooks, "celery_app", lambda: app)
    monkeypatch.setattr(hooks, "broker_settings", lambda: BROKER)
    return app


def prerun(kwargs: object) -> dict[str, str] | None:
    """on_task_prerun 에 쪽지를 먹이고, 태스크가 도는 동안의 로그 맥락을 꺼낸다(끝나면 걷는다)."""
    celery_config.on_task_prerun(task_id="t-1", task=FakeTask(), kwargs=kwargs)
    try:
        return context.current_task()
    finally:
        celery_config.on_task_postrun()


@pytest.mark.parametrize(("company_id", "job_id"), [(1, 1), (7, 42), (2**63 - 1, 2**63 - 1)])
def test_the_note_the_hook_sends_puts_the_job_id_into_the_worker_log(
    fake_app: FakeApp, company_id: int, job_id: int
) -> None:
    hooks.enqueue_job(company_id=company_id, job_id=job_id, kind="parse")
    (note,) = fake_app.notes
    assert note == {"company_id": str(company_id), "job_id": str(job_id)}  # 옛 이름(tenant_id)의 칸은 없다
    assert prerun(dict(note)) == {"task_id": "t-1", "task_name": "jobs.parse", "job_id": str(job_id)}
    assert context.current_task() is None  # 끝난 뒤에는 없다


def test_an_int_job_id_in_the_note_would_drop_the_field_silently() -> None:
    """반례(값을 글자로 두는 까닭): 정수 job_id 는 맥락에 실리지 않는다. 던지지도 않는다 — 소리 없이 빠진다."""
    assert prerun({"company_id": 7, "job_id": 42}) == {"task_id": "t-1", "task_name": "jobs.parse"}
    assert prerun({"company_id": "7", "job_id": "42"}) == {"task_id": "t-1", "task_name": "jobs.parse", "job_id": "42"}


@pytest.mark.parametrize(
    ("company_id", "job_id"),
    [
        ("0", "1"),
        ("-1", "1"),
        ("01", "1"),
        ("1.0", "1"),
        ("", "1"),
        (" 1", "1"),
        ("1\n", "1"),
        ("1" * 20, "1"),  # 19자리를 넘는다
        ("tenant-a", "1"),  # 옛 쪽지의 테넌트 글자
        ("1", "0"),
        ("1", "-1"),
        ("1", "01"),
        ("1", "1.0"),
        ("1", ""),
        ("1", "0b0e7c1e-0000-4000-8000-000000000001"),  # 옛 쪽지의 uuid 일감 id
    ],
    ids=repr,
)
def test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query(
    company_id: str, job_id: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """두 값 가운데 하나라도 ^[1-9][0-9]{0,18}$ 밖이면 잡기(조회)를 부르지 않고 「없음」의 줄 하나로 끝난다."""
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)

    def no_claim(**_: Any) -> Any:
        pytest.fail("꼴 밖의 쪽지로 잡기를 불렀다")

    monkeypatch.setattr(tasks, "claim_job", no_claim)
    with caplog.at_level(logging.INFO, logger=tasks.logger.name):
        tasks.run_parse_job(None, company_id=company_id, job_id=job_id)
    assert [record.getMessage() for record in caplog.records if record.name == tasks.logger.name] == [
        f"job_skipped job_id={job_id} kind=parse reason=JobNotFound"
    ]


def test_a_note_with_the_old_kwarg_name_is_a_type_error() -> None:
    """옛 이름(tenant_id)의 쪽지는 태스크가 받지 않는다(Celery 가 TypeError 로 끝낸다. 배포 없음 — 큐를 비운다)."""
    old: dict[str, str] = {"tenant_id": "tenant-a", "job_id": "1"}
    with pytest.raises(TypeError):
        tasks.run_parse_job(None, **old)
    with pytest.raises(TypeError):
        tasks.parse_job(**old)
