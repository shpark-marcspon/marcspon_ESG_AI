"""큐에 넣는 자리. 일감 하나(enqueue_job)나 흐름의 실행 하나(enqueue_run — X1b-1)의 쪽지를 브로커(Celery)에 넣는다.

enqueue_run 은 enqueue_job 과 같은 꼴이다(쪽지 `{company_id, run_id}` 십진 숫자 글자, 이름 `runs.execute` 로 보냄,
브로커 없으면 기록 한 줄 `queue_unconfigured`, 못 닿으면 기록 `queue_send_failed` 뒤 던짐, retry=False). 부르는 곳은
실행 만들기(on_commit)와 runs 의 다시 넣기 명령(requeue_runs)이다. 아래 글은 일감 쪽의 것이고 실행에도 같다.

부르는 곳은 둘이다: services.confirm_upload(`transaction.on_commit(…, robust=True)` 로 건다)와 다시 넣기 명령
(management/commands/requeue_jobs.py. 트랜잭션 블록을 나온 뒤에 부른다).

  - 커밋된 **뒤에만** 불린다. 그 쓰기의 블록이 되돌려지면 불리지 않는다.
    (워커가 쪽지를 받았는데 행이 아직 안 보이는 일이 없다.)
  - 쪽지에는 `company_id` 와 `job_id` 뿐이다. 둘 다 십진 숫자 **글자**다
    (esgapi/config/celery.py 의 on_task_prerun 이 `job_id` 를 글자일 때만 로그에 싣는다.
    정수로 보내면 로그의 job_id 칸이 소리 없이 빠진다).
    바이트·주소·저장소 키·파일 이름을 싣지 않는다(워커가 표에서 읽는다).
  - 태스크를 **이름으로** 보낸다(`jobs.<kind>`. core/calc/jobs.py 의 task_name). core 는 업무 모듈을 import 하지
    않는다(`.importlinter` 계약 가): 태스크의 정의는 esgapi/reconcile/tasks.py 에 있다.
  - 브로커 설정이 없으면(CELERY_BROKER_URL 없음) 기록 한 줄(`queue_unconfigured`)을 남기고 돌아간다. 일감은
    `queued` 에 머문다(서버는 브로커 없이도 뜬다).
  - 브로커에 못 닿으면 **그대로 던진다**. 던지기 앞에 일감 id 를 실은 한 줄(`queue_send_failed`)을 남긴다(예외의
    클래스 이름만. 예외의 글에는 브로커 주소가 들 수 있다).
    올림 확인에서는 요청이 그래도 200 이다(robust=True: Django 가 기록만 남기고 삼킨다. 커밋은 이미
    끝났다). 그때 행은 `queued` 인데 쪽지가 없다. 그 틈은 올림 확인을 다시 부르거나(끝나지 않은
    일감마다 다시 넣는다) 다시 넣기 명령이 메운다. 같은 쪽지가 여러 번 나가도 워커의 「잡기」가 거른다.
  - `retry=False`: 못 닿으면 kombu 가 되풀이해 붙지 않고 바로 던진다. 한 번의 최악 시간은 esgapi/config/celery.py 의
    client-config(연결 2초·읽기 5초·두 번까지)가 묶는다.

★ 테스트가 바꿔 끼우는 틈 셋(전부 「부를 때 모듈 속성으로 읽는다」):
    hooks.enqueue_job        services 가 부를 때 읽는다.  monkeypatch.setattr(hooks, "enqueue_job", spy)
    hooks.celery_app         monkeypatch.setattr(hooks, "celery_app", lambda: fake)
    hooks.broker_settings    monkeypatch.setattr(hooks, "broker_settings", lambda: settings)
  `from … import enqueue_job` 으로 들이면 그 길이 막힌다.
★ 업무·보안 층의 테스트는 소켓 막기 밖이다. 그 두 층에서는 진짜 celery_app() 으로 send_task 를 부르지 않는다
  (늘 가짜 앱이거나 브로커 없는 설정이다).
"""

import logging
from typing import Any

from esgapi.config.env import BrokerSettings
from esgapi.core.calc.jobs import RUN_TASK_NAME, SEGMENT_TASK_NAME, task_name
from esgapi.core.conf import app_config

logger = logging.getLogger(__name__)


def celery_app() -> Any:
    """이 프로세스의 Celery 앱. ★ 이음매다. 부를 때 들인다(이 모듈을 import 해도 celery 가 딸려 오지 않는다)."""
    from esgapi.config.celery import app

    return app


def broker_settings() -> BrokerSettings | None:
    """이 서버의 브로커 설정. 없으면 None. ★ 이음매다."""
    return app_config().broker


def enqueue_job(*, company_id: int, job_id: int, kind: str) -> None:
    """일감 하나의 쪽지를 큐에 넣는다. 브로커 설정이 없으면 넣지 않는다. 못 닿으면 던진다."""
    broker = broker_settings()
    if broker is None:
        logger.warning(
            "queue_unconfigured job_id=%s kind=%s (CELERY_BROKER_URL 이 없다. 일감은 queued 에 머문다)", job_id, kind
        )
        return
    name = task_name(kind)  # 모르는 종류는 여기서 ValueError 다(기록 없이 던진다)
    try:
        celery_app().send_task(
            name,
            kwargs={"company_id": str(company_id), "job_id": str(job_id)},
            queue=broker.queue_name,
            retry=False,
        )
    except Exception as err:
        logger.error("queue_send_failed job_id=%s kind=%s error=%s", job_id, kind, type(err).__name__)
        raise


def enqueue_run(*, company_id: int, run_id: int) -> None:
    """실행 하나의 쪽지를 큐에 넣는다. 브로커 설정이 없으면 넣지 않는다. 못 닿으면 던진다(enqueue_job 과 같다)."""
    broker = broker_settings()
    if broker is None:
        logger.warning("queue_unconfigured run_id=%s (CELERY_BROKER_URL 이 없다. 실행은 queued 에 머문다)", run_id)
        return
    try:
        celery_app().send_task(
            RUN_TASK_NAME,
            kwargs={"company_id": str(company_id), "run_id": str(run_id)},
            queue=broker.queue_name,
            retry=False,
        )
    except Exception as err:
        logger.error("queue_send_failed run_id=%s error=%s", run_id, type(err).__name__)
        raise


def enqueue_segment(*, company_id: int, run_id: int, run_attempt: int, countdown: int = 0) -> None:
    """펼침 구획 쪽지 하나를 큐에 넣는다(RM1b — `runs.segment`). enqueue_run 과 같은 꼴: 쪽지 `{company_id, run_id,
    run_attempt}` 십진 숫자 글자 셋(run_attempt = 주차한 지휘 시도), 브로커 없으면 기록 한 줄, 못 닿으면 기록 뒤 던짐.
    countdown(초)은 send_task 의 인자다(놓은 구획을 바로 다시 잡지 않게)."""
    broker = broker_settings()
    if broker is None:
        logger.warning("queue_unconfigured run_id=%s (CELERY_BROKER_URL 이 없다. 구획 쪽지를 넣지 않는다)", run_id)
        return
    try:
        celery_app().send_task(
            SEGMENT_TASK_NAME,
            kwargs={"company_id": str(company_id), "run_id": str(run_id), "run_attempt": str(run_attempt)},
            queue=broker.queue_name,
            retry=False,
            countdown=countdown,
        )
    except Exception as err:
        logger.error("queue_send_failed run_id=%s error=%s", run_id, type(err).__name__)
        raise
