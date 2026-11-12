# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""작업 큐(Celery)의 앱 정의. 워커(compose 의 worker-py)와 큐에 넣는 쪽(api-py 의 갈고리)이 같은 `app` 을 쓴다.

    app                 Celery 앱. 워커의 명령이 가리킨다:  celery -A esgapi.config.celery worker …
    celery_conf(b)      설정을 **이름으로** 적는 한 곳(순수 함수. dict 를 돌려준다. 연결을 열지 않는다)
    SETTINGS            이 프로세스의 브로커 설정(환경 변수에서). 없으면 None
    require_broker(b)   브로커가 없으면 SystemExit. 워커가 뜰 때(celeryd_init 신호) 불린다

★ 이 모듈을 import 해도 Django 가 뜨지 않고, 브로커가 없어도 import 된다.
  설정은 `os.environ` 을 config/env.py 의 load_broker_settings 로 읽는다(Django 설정·app_config() 를 거치지 않는다).
  까닭: 태스크 파일(esgapi/reconcile/tasks.py)이 `@app.task` 때문에 import 때 `app` 이 있어야 하고, 테스트 환경에는
  브로커가 없다. 「브로커가 없으면 이름 있는 오류」는 import 가 아니라 **워커가 뜰 때** 낸다(require_broker).
  그 처리기는 SystemExit 로 끝낸다. 보통의 예외는 안 된다: celery 의 Signal.send 가 `except Exception` 으로 삼켜
  워커가 그대로 뜬다(celery 5.6.3 utils/dispatch/signal.py:281-286).
  `config/__init__.py` 는 이 모듈을 들이지 않는다(순수 테스트가 config.env 를 들일 때 celery 가 딸려 오지 않게).

★ 끝점은 브로커 주소의 **호스트**에서만 온다(kombu 5.6.2 transport/SQS.py 의 endpoint_url). 호스트 없는 `sqs://` 로는
  큐 주소가 로컬이어도 진짜 AWS 를 부른다. 그 꼴은 config/env.py 가 문제 목록으로 막는다. 정식의 `sqs://`(호스트 없음 +
  amazonaws.com 의 큐 주소 + TLS)는 설정 검사를 지난다. 이 저장소에서 그 꼴은 celery_conf 의 dict 를 견주는 데만 쓴다.

★ Django 와의 이음(celery 5.6.3 celery/fixups/django.py): 환경에 DJANGO_SETTINGS_MODULE 이 있으면 fixup 이 선다.
  워커에서는 태스크마다 앞뒤로 DB 연결을 닫는다(CELERY_DB_REUSE_MAX 를 주지 않는다) → 태스크마다 새 연결이다.
  태스크는 `app.autodiscover_tasks()` 가 INSTALLED_APPS 의 `<모듈>.tasks` 에서 찾는다(워커가 뜰 때. import 때가 아니다).

★ 로그: 워커의 `logging` 줄도 한 줄 JSON 이다(core/observability/jsonlog.py). `setup_logging` 신호에 받는 쪽을 걸면
  Celery 는 뿌리 로거를 건드리지 않고(celery 5.6.3 app/log.py 의 setup_logging_subsystem) print 를 로그로 돌리지도
  않는다. 그래서 설정(`celery_conf`)에 `worker_hijack_root_logger` 를 적지 않는다. 뜨는 배너는 Celery 가 print 로 찍는
  글 그대로다. 태스크가 도는 동안의 줄에는 task_id·task_name·job_id(실행 태스크는 run_id)가 실린다
  (task_prerun·task_postrun 신호. prefork 의 자식 프로세스에서 난다).
  ★ 쪽지의 `tenant_id` 는 읽지 않는다(로그에 테넌트를 싣지 않는다).
  부모 프로세스가 내는 `Task jobs.parse[<id>] received` 줄에는 job_id 칸이 없다.
  받는 쪽이 있으면 Celery 가 하지 않게 되는 것이 셋 더 있다: 줄이 표준 오류가 아니라 표준 출력으로 간다,
  `--loglevel` 을 듣지 않는다(수준은 설정의 INFO 다), `multiprocessing` 로거(자식 프로세스가 죽은 줄을 낸다)에
  처리기를 걸지 않는다. 마지막 것은 on_setup_logging 이 Celery 가 걸던 수준(ERROR) 그대로 건다. 걸지 않으면 그 줄이
  표준 오류에 시각도 수준도 없는 맨 글로 나간다.

SDK 의 타입: celery·kombu 에는 타입 정보가 없고 스텁도 들이지 않았다. celery 를 들이는 파일(이 파일,
core/resources/queue.py, reconcile/tasks.py, runs/tasks.py)의 머리에서만 pyright 의 규칙 넷을 끈다.
"""

import logging.config
import os
from collections.abc import Mapping
from typing import Any

from celery import Celery
from celery.signals import celeryd_init, setup_logging, task_postrun, task_prerun

from esgapi.config.env import BrokerSettings, ConfigError, load_broker_settings, load_job_settings
from esgapi.core.observability.context import bind_task, unbind_task
from esgapi.core.observability.jsonlog import logging_config

# 큐에 넣는 쪽(갈고리)이 브로커에 못 닿을 때의 최악 시간을 묶는다(botocore Config 로 간다. kombu SQS.py:758-760).
# 저장소 어댑터(core/resources/storage.py)와 같은 어림이다: 연결 2초 · 읽기 5초 · 두 번까지.
CLIENT_CONNECT_TIMEOUT_S = 2
CLIENT_READ_TIMEOUT_S = 5
CLIENT_TOTAL_MAX_ATTEMPTS = 2
# 폴링 간격. Celery 문서(「Using Amazon SQS」, 5.6.3)의 기본값 그대로를 이름으로 적는다.
# 긴 폴링은 설정에서 온다(env.BrokerSettings.wait_time_seconds, 환경 값 CELERY_WAIT_TIME_SECONDS).
# 그 기본 10 은 같은 문서의 값이다.
POLLING_INTERVAL_S = 1


def celery_conf(broker: BrokerSettings) -> dict[str, Any]:
    """브로커 설정 → Celery 설정. 이름과 값의 근거는 docs/development.md 의 「워커와 큐 (Celery)」에 있다.

    ★ `result_backend` 키가 없다(상태의 정본은 표 run_jobs 다. SQS 에는 결과 백엔드가 없다).
    ★ `predefined_queues` 가 늘 있다(Celery 가 큐를 만들지도 훑지도 않는다. 큐가 없으면 워커가 죽는다).
    """
    return {
        "broker_url": broker.url,
        "task_ignore_result": True,
        # 받자마자가 아니라 끝난 뒤에 ack 한다. 워커 프로세스를 잃으면 쪽지를 되돌린다(재전달은 큐의 visibility 뒤).
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        # 기본값 그대로(True)를 이름으로 적는다: 실패·시간 초과는 ack 된다. 그 쪽지는 다시 오지 않는다.
        # 복구의 닻은 큐가 아니라 표의 임대 + 다시 넣기다.
        "task_acks_on_failure_or_timeout": True,
        "worker_prefetch_multiplier": 1,  # 기본 4. 미리 쥔 쪽지는 visibility 를 깎는다(값은 어림)
        "task_soft_time_limit": broker.task_soft_time_limit_s,
        "task_time_limit": broker.task_time_limit_s,
        "broker_transport_options": {
            "region": broker.region,
            "is_secure": broker.secure,
            # ★ 미리 만든 큐에서는 쓰이지 않는다(큐의 속성이 이긴다). 「큐가 그렇게 만들어져 있다」는 앎을 적어 둔다.
            "visibility_timeout": broker.visibility_timeout_s,
            "wait_time_seconds": broker.wait_time_seconds,
            "polling_interval": POLLING_INTERVAL_S,
            "predefined_queues": {broker.queue_name: {"url": broker.queue_url}},
            "client-config": {
                "connect_timeout": CLIENT_CONNECT_TIMEOUT_S,
                "read_timeout": CLIENT_READ_TIMEOUT_S,
                "retries": {"total_max_attempts": CLIENT_TOTAL_MAX_ATTEMPTS, "mode": "standard"},
            },
        },
        # SQS 는 원격 제어 명령과 이벤트를 지원하지 않는다(Celery 문서).
        "worker_enable_remote_control": False,
        "worker_send_task_events": False,
        "task_default_queue": broker.queue_name,
        "task_create_missing_queues": False,
        "broker_connection_retry_on_startup": True,  # 워커는 브로커가 없어도 죽지 않고 다시 붙는다
        "task_serializer": "json",  # 쪽지는 id 둘뿐이다
        "accept_content": ["json"],
    }


def broker_from_env(env: Mapping[str, str]) -> BrokerSettings | None:
    """환경 변수 → 브로커 설정. 없으면 None. 틀린 값이 있으면 ConfigError(문제를 전부 모아 한 번에)."""
    problems: list[str] = []
    jobs = load_job_settings(env, problems)
    broker = load_broker_settings(env, problems, lease_s=jobs.lease_s)
    if problems:
        raise ConfigError("설정이 모자라다: " + " / ".join(problems))
    return broker


def make_app(broker: BrokerSettings | None) -> Celery:
    """앱을 만든다. 브로커가 없으면 설정을 싣지 않은 앱이다(태스크를 등록할 수는 있고, 워커로는 뜨지 않는다)."""
    made = Celery("esgapi")
    if broker is not None:
        made.conf.update(celery_conf(broker))
    made.autodiscover_tasks()
    return made


def require_broker(broker: BrokerSettings | None) -> None:
    """브로커 설정이 없으면 워커를 띄우지 않는다. ★ SystemExit 여야 한다(머리말)."""
    if broker is None:
        raise SystemExit(
            "CELERY_BROKER_URL 이 없다. 워커는 브로커 없이 뜨지 않는다"
            "(로컬 흉내는 sqs://queue:9324 꼴로 호스트를 적는다. 설명은 README 의 「워커와 큐 (Celery)」)"
        )


SETTINGS: BrokerSettings | None = broker_from_env(os.environ)
app = make_app(SETTINGS)


def on_celeryd_init(**_: object) -> None:
    """워커가 뜰 때 한 번 불린다. 이 프로세스의 브로커 설정이 없으면 여기서 끝낸다."""
    require_broker(SETTINGS)


def on_setup_logging(**_: object) -> None:
    """워커가 로그를 세울 때 불린다. 받는 쪽이 있으므로 Celery 는 자기 꼴로 뿌리 로거를 세우지 않는다."""
    config = logging_config()
    # 자식 프로세스가 죽은 줄(billiard 의 `Process … exited with …`)도 같은 꼴로 낸다. 수준은 Celery 가 걸던 ERROR.
    config["loggers"] = {"multiprocessing": {"level": "ERROR", "handlers": ["stdout"], "propagate": False}}
    logging.config.dictConfig(config)


def on_task_prerun(task_id: object = None, task: object = None, kwargs: object = None, **_: object) -> None:
    """태스크가 돌기 직전. 그 태스크와 일감(job_id)·실행(run_id — runs.execute)의 id 를 글자일 때만 로그에 싣는다.
    ★ kwargs 의 tenant_id·company_id 는 읽지 않는다."""
    job_id = kwargs.get("job_id") if isinstance(kwargs, dict) else None
    run_id = kwargs.get("run_id") if isinstance(kwargs, dict) else None
    bind_task(
        task_id=str(task_id),
        task_name=str(getattr(task, "name", "")),
        job_id=job_id if isinstance(job_id, str) else None,
        run_id=run_id if isinstance(run_id, str) else None,
    )


def on_task_postrun(**_: object) -> None:
    unbind_task()


celeryd_init.connect(on_celeryd_init, weak=False)
setup_logging.connect(on_setup_logging, weak=False)
task_prerun.connect(on_task_prerun, weak=False)
task_postrun.connect(on_task_postrun, weak=False)
