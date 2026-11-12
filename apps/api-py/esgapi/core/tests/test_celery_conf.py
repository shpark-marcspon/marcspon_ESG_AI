# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Celery 앱의 설정(esgapi/config/celery.py). 순수 층: dict 를 글자로 견준다. 연결을 열지 않는다(소켓이 막혀 있다).

★ 호스트 없는 `sqs://` 는 여기서 **dict 를 견주는 데만** 쓴다. send_task·워커·celery 명령에 넣지 않는다.
"""

import subprocess
import sys
from dataclasses import replace
from urllib.parse import urlsplit

import pytest

from esgapi.config import celery as celery_config
from esgapi.config.celery import broker_from_env, celery_conf, make_app, require_broker
from esgapi.config.env import BrokerSettings, ConfigError

LOCAL = BrokerSettings(
    url="sqs://queue:9324",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="http://queue:9324/000000000000/esg-jobs",
    secure=False,
)
PRODUCTION = BrokerSettings(
    url="sqs://",
    region="ap-northeast-2",
    queue_name="esg-jobs",
    queue_url="https://sqs.ap-northeast-2.amazonaws.com/123456789012/esg-jobs",
    secure=True,
)


def test_the_conf_is_exactly_these_names_and_values() -> None:
    """이름 하나를 빼거나 값을 바꾸면 빨개진다. 근거는 docs/development.md 의 「워커와 큐 (Celery)」."""
    assert celery_conf(LOCAL) == {
        "broker_url": "sqs://queue:9324",
        "task_ignore_result": True,
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        "task_acks_on_failure_or_timeout": True,
        "worker_prefetch_multiplier": 1,
        "task_soft_time_limit": 240,
        "task_time_limit": 300,
        "broker_transport_options": {
            "region": "ap-northeast-2",
            "is_secure": False,
            "visibility_timeout": 360,
            "wait_time_seconds": 10,
            "polling_interval": 1,
            "predefined_queues": {"esg-jobs": {"url": "http://queue:9324/000000000000/esg-jobs"}},
            "client-config": {
                "connect_timeout": 2,
                "read_timeout": 5,
                "retries": {"total_max_attempts": 2, "mode": "standard"},
            },
        },
        "worker_enable_remote_control": False,
        "worker_send_task_events": False,
        "task_default_queue": "esg-jobs",
        "task_create_missing_queues": False,
        "broker_connection_retry_on_startup": True,
        "task_serializer": "json",
        "accept_content": ["json"],
    }


def test_the_long_poll_comes_from_the_settings() -> None:
    """긴 폴링은 설정(CELERY_WAIT_TIME_SECONDS)의 값이 그대로 간다. 기본 10 은 위 시험이 잰다."""
    short = replace(LOCAL, wait_time_seconds=3)
    assert celery_conf(short)["broker_transport_options"]["wait_time_seconds"] == 3


@pytest.mark.parametrize("broker", [LOCAL, PRODUCTION])
def test_there_is_no_result_backend_and_the_queue_is_always_predefined(broker: BrokerSettings) -> None:
    conf = celery_conf(broker)
    assert "result_backend" not in conf
    assert not [name for name in conf if "result_backend" in name or "DB_REUSE" in name.upper()]
    assert conf["broker_transport_options"]["predefined_queues"] == {broker.queue_name: {"url": broker.queue_url}}
    assert conf["task_create_missing_queues"] is False


def test_the_broker_url_host_is_the_one_from_the_settings() -> None:
    """끝점은 브로커 주소의 호스트에서 온다. celery_conf 는 주소를 그대로 넘긴다(호스트를 떼지도 붙이지도 않는다)."""
    assert urlsplit(celery_conf(LOCAL)["broker_url"]).hostname == "queue"
    assert urlsplit(celery_conf(LOCAL)["broker_url"]).port == 9324
    assert "amazonaws" not in str(celery_conf(LOCAL))
    # 정식의 꼴: dict 만 본다. 연결을 열지 않는다.
    production = celery_conf(PRODUCTION)
    assert production["broker_url"] == "sqs://"
    assert production["broker_transport_options"]["is_secure"] is True


def test_the_numbers_come_from_the_settings() -> None:
    conf = celery_conf(
        BrokerSettings(
            url="sqs://queue:9324",
            region="us-east-1",
            queue_name="other",
            queue_url="http://queue:9324/000000000000/other",
            secure=False,
            visibility_timeout_s=40,
            task_soft_time_limit_s=12,
            task_time_limit_s=15,
        )
    )
    assert (conf["task_soft_time_limit"], conf["task_time_limit"]) == (12, 15)
    assert conf["broker_transport_options"]["visibility_timeout"] == 40
    assert conf["broker_transport_options"]["region"] == "us-east-1"
    assert conf["task_default_queue"] == "other"


def test_an_app_made_with_a_broker_carries_the_conf_without_connecting(blocked_network: list[object]) -> None:
    app = make_app(LOCAL)
    assert app.conf.task_acks_late is True
    assert app.conf.result_backend is None
    assert urlsplit(app.conf.broker_url).hostname == "queue"
    assert blocked_network == []  # 앱을 만들고 설정을 읽는 것만으로는 소켓을 열지 않는다


def test_this_process_has_no_broker_and_the_module_still_imports() -> None:
    """테스트 환경에는 CELERY_BROKER_URL 이 없다. 그래도 모듈은 import 되고 app 이 있다(태스크 파일이 그것을 쓴다)."""
    assert celery_config.SETTINGS is None
    assert celery_config.app.main == "esgapi"


def test_a_worker_refuses_to_start_without_a_broker() -> None:
    """★ SystemExit 여야 한다. 보통의 예외는 celery 의 Signal.send 가 삼켜 워커가 그대로 뜬다."""
    with pytest.raises(SystemExit, match="CELERY_BROKER_URL 이 없다"):
        require_broker(None)
    with pytest.raises(SystemExit, match="CELERY_BROKER_URL 이 없다"):
        celery_config.on_celeryd_init(sender="celery@test", conf=None)
    require_broker(LOCAL)  # 있으면 지나간다


def test_the_init_handler_is_connected_to_the_worker_start_signal() -> None:
    from celery.signals import celeryd_init

    receivers = [receiver for _, receiver in celeryd_init.receivers or []]
    assert any(getattr(r, "__name__", "") == "on_celeryd_init" for r in receivers)


def test_broker_from_env_reads_the_environment_and_names_every_problem() -> None:
    assert broker_from_env({}) is None
    env = {
        "CELERY_BROKER_URL": "sqs://queue:9324",
        "CELERY_BROKER_REGION": "ap-northeast-2",
        "CELERY_BROKER_SECURE": "false",
        "CELERY_QUEUE_URL": "http://queue:9324/000000000000/esg-jobs",
    }
    assert broker_from_env(env) == LOCAL
    with pytest.raises(ConfigError, match="CELERY_BROKER_URL 에 호스트가 없다"):
        broker_from_env({**env, "CELERY_BROKER_URL": "sqs://"})
    with pytest.raises(ConfigError, match="JOB_LEASE_SECONDS"):
        broker_from_env({**env, "JOB_LEASE_SECONDS": "10"})


def test_importing_the_module_does_not_start_django_and_raises_no_warning() -> None:
    """새 프로세스에서 `-W error` 로 들인다: Django 의 앱 등록이 돌지 않았고 설정도 읽지 않았다(브로커 키 없이)."""
    code = (
        "import esgapi.config.celery as c, sys\n"
        "import django.apps, django.conf\n"
        "assert not django.apps.apps.ready, 'Django 가 떴다'\n"
        "assert not django.conf.settings.configured, 'Django 설정을 읽었다'\n"
        "assert c.SETTINGS is None and c.app.main == 'esgapi'\n"
        "assert 'esgapi.reconcile.tasks' not in sys.modules\n"
    )
    env = {"PATH": "/usr/bin:/bin", "DJANGO_SETTINGS_MODULE": "esgapi.config.settings.base"}
    done = subprocess.run(
        [sys.executable, "-W", "error", "-c", code], env=env, capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr[-2000:]


def test_config_package_does_not_pull_celery_in() -> None:
    """config.env 를 들일 때 celery 가 딸려 오지 않는다(config/__init__.py 는 celery 모듈을 들이지 않는다)."""
    code = "import esgapi.config.env, sys\nassert 'celery' not in sys.modules and 'kombu' not in sys.modules\n"
    done = subprocess.run([sys.executable, "-W", "error", "-c", code], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
