"""실행기는 prefork 자식에서 태스크 하나를 동기로 돈다(처분 ⑥): 프로세스 안 스레드 동시 실행 0.
compose.yaml 의 워커 명령을 글로 읽는다(YAML 파서를 새로 들이지 않는다). 순수 층."""

import re
from pathlib import Path

from esgapi.config.celery import celery_conf
from esgapi.config.env import BrokerSettings

COMPOSE = Path(__file__).resolve().parents[5] / "compose.yaml"


def worker_command() -> str:
    text = COMPOSE.read_text(encoding="utf-8")
    block = text.split("\n  worker-py:\n", 1)[1]
    found = re.search(r"^    command: (.+)$", block, re.MULTILINE)
    assert found is not None
    return found.group(1)


def test_the_worker_pool_is_prefork_and_never_threads() -> None:
    command = worker_command()
    assert '"--pool", "prefork"' in command
    assert re.search(r"threads|gevent|eventlet|solo", command) is None


def test_a_worker_child_takes_one_note_at_a_time() -> None:
    broker = BrokerSettings(url="sqs://queue:9324", region="r", queue_name="q", queue_url="http://queue:9324/0/q")
    assert celery_conf(broker)["worker_prefetch_multiplier"] == 1
