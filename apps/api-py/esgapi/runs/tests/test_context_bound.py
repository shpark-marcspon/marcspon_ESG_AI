# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행기까지 — 소프트 제한과 실패 시도의 보수 어림(밴드 LH2 S9 — MARC-ISSUE-411 S2·S3). 업무 층:
test_context_live.py 의 실행기 세계(가짜 흐름·저장소 가짜·태스크 직접 부름)와 OpenAI SDK 의 가짜 HTTP 를 빌려 쓴다.

  소프트 제한  공급사(진짜 SDK + 가짜 HTTP · 모의 공급사)가 진짜 celery.exceptions.SoftTimeLimitExceeded 를 던지면
               호출 층이 삼키지 않고 단계 밖으로 → FlowStepFailed.__cause__ → outcome_of 가 RunDeferred(queued·다시
               넣기 청 하나).
               그 시도의 timeout 줄 하나는 남는다. BASE 는 공급사 오류 값으로 삼켜져 흐름이 계속해 done 이었다(대조값)
  live 셈      한 시도 안 시간 초과 둘의 어림이 그 실행의 spent 에 들어가 셋째 호출이 공급사 전 budget_exceeded
               (BASE 는 실패 시도가 0 이라 셋째도 공급사로 갔다 — 대조값). 장부(DB 의 cost_usd)는 None 그대로
  기록 실패    (LH3 T2 — MARC-ISSUE-413 I4) 소프트 제한 뒤 그 줄 쓰기가 OSError·DatabaseError 로 던져도 실행은
               RunDeferred(BASE 는 싱크의 예외가 FlowStepFailed 로 싸여 RunFailed(step_error) — failed 였다, 대조값)
★ _transient 가 isinstance 로 가르므로 진짜 celery 예외로만 잰다(m5). 네트워크 0 — test_context_live 의 no_network.
"""

from typing import Any

import httpx
import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.db.utils import DatabaseError

from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.log import CallRecord
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import ProviderTimeout
from esgapi.runs import context
from esgapi.runs.tests import test_context_live, test_executor
from esgapi.runs.tests.test_context_live import CHAT_ROUTE, FakeOpenAI, chat, lines, live_settings, tags, timeout, use
from esgapi.runs.tests.test_executor import ProbeAdapters, World, execute, new_run, row

pytestmark = pytest.mark.django_db

executor_world = test_executor.world
no_network = test_context_live.no_network
fake = test_context_live.fake


@pytest.fixture
def world(executor_world: World) -> World:
    return executor_world


def soft_limit(request: httpx.Request, _: int) -> httpx.Response:
    raise SoftTimeLimitExceeded("합성 소프트 제한")


def test_a_soft_limit_inside_a_live_call_defers_the_run(
    world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI
) -> None:
    use(monkeypatch, world, live_settings())
    fake.chat = soft_limit
    test_context_live.at_first_item(world, lambda adapters: chat(adapters, world))
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.error_code, len(world.retries)) == ("queued", None, 1)
    assert len(fake.seen) == 1  # 같은 모델 재시도 0
    assert [(r.result_kind, r.cost_usd) for r in lines(world, run_id)] == [("timeout", None)]


def test_a_soft_limit_inside_a_mock_call_defers_the_run(world: World) -> None:
    def act(i: int, adapters: ProbeAdapters) -> None:
        if i != 0:
            return
        client = adapters.ctx.llm()
        provider = client.provider("mock")
        assert isinstance(provider, MockProvider)

        def boom(_: object) -> Any:
            raise SoftTimeLimitExceeded("합성 소프트 제한")

        provider.enqueue(boom)
        client.call(CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=tags(world)))

    world.script.before_item = act
    run_id = new_run(world)
    execute(world, run_id)
    assert (row(world, run_id).status, len(world.retries)) == ("queued", 1)


def worst_once_for_the_chat_route(world: World) -> float:
    """같은 요청을 같은 모델 설정·단가로 시간 초과시켜 잰 한 번 최악(기준값 — 메모리 싱크)."""
    sink = MemorySink()
    probe = MockProvider("openai")
    probe.enqueue(ProviderTimeout(message="합성"))
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": probe},
        prompts=PackagePromptStore(),
        log=sink,
    )
    client.call(CallRequest(prompt="core/hello@1", vars={"name": "김"}, route=CHAT_ROUTE, tags=tags(world)))
    (record,) = sink.records
    assert record.cost_bound_usd is not None and record.cost_bound_usd > 0
    return record.cost_bound_usd


def test_two_timeouts_in_one_attempt_count_against_the_run_limit(
    world: World, monkeypatch: pytest.MonkeyPatch, fake: FakeOpenAI
) -> None:
    worst = worst_once_for_the_chat_route(world)
    use(monkeypatch, world, live_settings(run_max_usd=worst * 1.5))
    fake.chat = timeout
    got = test_context_live.at_first_item(
        world, lambda adapters: (chat(adapters, world), chat(adapters, world), chat(adapters, world))
    )
    run_id = new_run(world)
    execute(world, run_id)
    ((first, second, third),) = got
    assert (first.kind, second.kind, third.kind) == ("timeout", "timeout", "budget_exceeded")
    assert third.spent_usd == pytest.approx(2 * worst, abs=1e-8)
    assert len(fake.seen) == 2  # 셋째는 공급사에 가지 않았다(BASE 는 3)
    assert [(r.result_kind, r.cost_usd) for r in lines(world, run_id)] == [
        ("timeout", None),
        ("timeout", None),
        ("budget_exceeded", None),
    ]


class FailingSink:
    """record 가 늘 던지는 싱크(LH3 T2)."""

    accepts_bodies = False

    def __init__(self, error: Exception) -> None:
        self.error = error

    def record(self, record: CallRecord) -> None:
        raise self.error

    def spent(self, scope: object) -> float:
        return 0.0


@pytest.mark.parametrize("sink_error", [OSError, DatabaseError])
def test_a_soft_limit_whose_line_cannot_be_written_still_defers_the_run(
    world: World, monkeypatch: pytest.MonkeyPatch, sink_error: type[Exception]
) -> None:
    monkeypatch.setattr(context, "call_sink", lambda: FailingSink(sink_error("합성 싱크 실패")))

    def act(i: int, adapters: ProbeAdapters) -> None:
        if i != 0:
            return
        client = adapters.ctx.llm()
        provider = client.provider("mock")
        assert isinstance(provider, MockProvider)

        def boom(_: object) -> Any:
            raise SoftTimeLimitExceeded("합성 소프트 제한")

        provider.enqueue(boom)
        client.call(CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=tags(world)))

    world.script.before_item = act
    run_id = new_run(world)
    execute(world, run_id)
    run = row(world, run_id)
    assert (run.status, run.error_code, len(world.retries)) == ("queued", None, 1)  # BASE: failed·step_error
