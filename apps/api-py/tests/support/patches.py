"""시험이 제품 코드의 이음매(문서로 밝힌 틈)에 가짜를 꽂는 되풀이 둘. 업무 층과 보안 층이 같이 쓴다.

    record_enqueued(monkeypatch)       큐 갈고리(core/resources/queue.py 의 enqueue_job)를 받은 kwargs 를 쌓기만 하는
                                       가짜로 바꾸고, 그 목록을 돌려준다. 부른 그 줄부터 쌓인다(픽스처가 아니라 함수인
                                       까닭: 시험 가운데서 꽂는 곳이 있다).
    plug_storage(monkeypatch, storage, *, max_upload_bytes=None)
                                       문서 저장소 이음매(services.default_storage)가 storage 를 주게 한다. None 이면
                                       저장소 설정이 없는 꼴이다. max_upload_bytes 를 주면 상한
                                       (services.max_upload_bytes)도 그 값으로 바꾼다. 받은 storage 를 그대로 돌려준다.

★ 둘 다 monkeypatch 로 바꿔 끼워 시험이 끝나면 되돌아간다. 각 시험이 직접 import 한다(pytest_plugins 를 쓰지 않는다).
★ 끼울 가짜 저장소는 인자로 받는다(FakeStorage 를 여기서 import 하지 않는다: 가짜의 자리는 sid:MARC-TICK-126 이 옮긴다).
★ 이음매 자체는 걷지 않는다(제품 코드다). 갈고리를 실패·불안정·트랜잭션을 보는 가짜로 바꾸는 시험은 시험마다 꼴이
  달라 여기 묶지 않는다.
"""

from typing import Any

import pytest

from esgapi.core.resources import queue as hooks
from esgapi.core.service.services import documents as services


def record_enqueued(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def spy(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(hooks, "enqueue_job", spy)
    return calls


def plug_storage[S](monkeypatch: pytest.MonkeyPatch, storage: S, *, max_upload_bytes: int | None = None) -> S:
    monkeypatch.setattr(services, "default_storage", lambda: storage)
    if max_upload_bytes is not None:
        limit = max_upload_bytes
        monkeypatch.setattr(services, "max_upload_bytes", lambda: limit)
    return storage
