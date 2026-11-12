# pyright: reportMissingTypeStubs=false
"""소프트 제한 뒤 기록 줄 쓰기가 던져도 올라가는 것은 소프트 제한 그 자체다(밴드 LH3 T2 — MARC-ISSUE-413 I4). 순수 층.

  T2  대화(client)·임베딩 클라이언트, 싱크의 record 가 DatabaseError·InterfaceError·OSError 를 던짐 → 올라오는 것이
      진짜 celery.exceptions.SoftTimeLimitExceeded 그 객체(BASE 는 싱크의 예외가 올라왔다 — 대조) · logger 에는 예외
      이름만(예외의 글 0 — 키가 섞일 수 있다) · 소프트 제한이 아닌 갈래(정상 시간 초과)의 싱크 오류는 BASE 그대로 올라옴
★ 업무 층(outcome_of 가 RunDeferred)은 runs/tests/test_context_bound.py. 네트워크 0.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.db.utils import DatabaseError, InterfaceError

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.embedding import EmbeddingClient, EmbedRequest
from esgapi.core.llm.log import CallRecord
from esgapi.core.llm.providers.mock import MockEmbeddingProvider
from esgapi.core.llm.types import ProviderTimeout, Scope
from esgapi.core.tests.llm_support import TAGS, harness, synthetic_config, write_prompts

SECRET_TEXT = "합성-싱크-글"  # 예외의 글: logger 에 나오면 안 된다
SINK_ERRORS = [
    pytest.param(DatabaseError, id="DatabaseError"),
    pytest.param(InterfaceError, id="InterfaceError"),
    pytest.param(OSError, id="OSError"),
]


class FailingSink:
    """record 가 늘 던지는 싱크."""

    accepts_bodies = False

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.tried: list[CallRecord] = []

    def record(self, record: CallRecord) -> None:
        self.tried.append(record)
        raise self.error

    def spent(self, scope: Scope) -> float:
        return 0.0


def raising(error: BaseException) -> Callable[..., Any]:
    def handler(*_: object, **__: object) -> Any:
        raise error

    return handler


@pytest.mark.parametrize("sink_error", SINK_ERRORS)
def test_t2_client_raises_the_soft_limit_even_when_the_line_cannot_be_written(
    tmp_path: Path, blocked_network: list[object], caplog: pytest.LogCaptureFixture, sink_error: type[Exception]
) -> None:
    deadline = SoftTimeLimitExceeded("합성 소프트 제한")
    sink = FailingSink(sink_error(SECRET_TEXT))
    h = harness(write_prompts(tmp_path))
    h.client._log = sink  # pyright: ignore[reportPrivateUsage]
    h.mock.enqueue(raising(deadline))
    with caplog.at_level(logging.WARNING, logger="esgapi.core.llm.client"), pytest.raises(SoftTimeLimitExceeded) as up:
        h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    assert up.value is deadline
    assert [r.result_kind for r in sink.tried] == ["timeout"]  # 쓰려 한 줄은 그 시도의 timeout 하나
    assert sink_error.__name__ in caplog.text
    assert SECRET_TEXT not in caplog.text
    assert blocked_network == []


@pytest.mark.parametrize("sink_error", SINK_ERRORS)
def test_t2_embedding_raises_the_soft_limit_even_when_the_line_cannot_be_written(
    blocked_network: list[object], caplog: pytest.LogCaptureFixture, sink_error: type[Exception]
) -> None:
    deadline = SoftTimeLimitExceeded("합성 소프트 제한")
    sink = FailingSink(sink_error(SECRET_TEXT))
    mock = MockEmbeddingProvider()
    mock.enqueue(raising(deadline))
    client = EmbeddingClient(config=synthetic_config(), providers={"mock": mock}, log=sink)
    with (
        caplog.at_level(logging.WARNING, logger="esgapi.core.llm.embedding"),
        pytest.raises(SoftTimeLimitExceeded) as up,
    ):
        client.embed(EmbedRequest(inputs=("합성 하나",), route="mock-gw1", tags=TAGS, batch_size=1))
    assert up.value is deadline
    assert [r.result_kind for r in sink.tried] == ["timeout"]
    assert sink_error.__name__ in caplog.text
    assert SECRET_TEXT not in caplog.text
    assert blocked_network == []


def test_t2_a_sink_error_outside_the_soft_limit_branch_still_rises_like_base(
    tmp_path: Path, blocked_network: list[object]
) -> None:
    sink = FailingSink(OSError(SECRET_TEXT))
    h = harness(write_prompts(tmp_path))
    h.client._log = sink  # pyright: ignore[reportPrivateUsage]
    h.mock.enqueue(ProviderTimeout(message="합성"))
    with pytest.raises(OSError):
        h.client.call(CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS))
    assert blocked_network == []
