"""실행의 문맥(runs/context.py): LLM 클라이언트는 mock 모드(기본)에서 모의 공급사만(P10 — live 는
test_context_live.py), 호출 기록의 run_id 는 싱크가 덮어 적는다(P18).
AD4D: 단계 커서(StepCursor) — 싱크가 기록마다 지금 단계를 step 으로 덮어 적고, 실행기의 사건(RowEvents)이 단계 시작에
적고 끝·실패에 비운다(사건의 DB 쓰기는 가짜로 바꿔 끼운다).
순수 층: 메모리 싱크. DB 싱크로 행의 run_id·step 을 재는 것은 test_executor.py(업무 층)."""

import contextlib
from collections.abc import Iterator
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from esgapi.config.env import LlmSettings
from esgapi.core.flows.types import StepOutput
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Tags
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.core.tests.test_llm_sinks import RECORD
from esgapi.runs import context, tasks
from esgapi.runs.context import ExecutorContext, RunCallSink, StepCursor
from esgapi.runs.service.services.runs import Recorded

KEYED = LlmSettings(openai_api_key="key-synthetic", anthropic_api_key="key-synthetic", gemini_api_key="key-synthetic")


def ctx(sink: RunCallSink, run_id: int = 41) -> ExecutorContext:
    return ExecutorContext(company_id=7, run_id=run_id, module="test", flow_id="test.flow@1", attempt=1, sink=sink)


def test_in_mock_mode_the_runner_builds_only_mock_clients_even_when_keys_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_RUN_MODE 가 mock(기본)이면 프로세스에 실제 공급사의 키가 있어도 실행기의 클라이언트에는 싣지 않는다
    (실호출 0 — MARC-ENT-262. live 의 갈래는 test_context_live.py)."""
    asked: list[dict[str, Any]] = []
    real = context.build_client

    def spy(settings: LlmSettings, **kwargs: Any) -> Any:
        asked.append({"settings": settings, **kwargs})
        return real(settings, **kwargs)

    monkeypatch.setattr(context, "app_config", lambda: type("C", (), {"llm": KEYED})())
    monkeypatch.setattr(context, "build_client", spy)
    client = ctx(RunCallSink(MemorySink(), 41)).llm()
    (only,) = asked
    assert only["mock"] is True
    assert (only["settings"].openai_api_key, only["settings"].anthropic_api_key, only["settings"].gemini_api_key) == (
        None,
        None,
        None,
    )
    assert isinstance(client.provider("mock"), MockProvider)


def test_every_record_of_the_run_carries_its_id_whatever_the_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(context, "app_config", lambda: type("C", (), {"llm": LlmSettings()})())
    inner = MemorySink()
    client = ctx(RunCallSink(inner, 41)).llm()
    mock = client.provider("mock")
    assert isinstance(mock, MockProvider)
    mock.enqueue_text("안녕하세요")
    client.call(CallRequest(prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags("7", "test")))
    assert len(inner.records) >= 1  # 분모
    assert {r.run_id for r in inner.records} == {"41"}


def test_the_sink_passes_spent_and_the_body_rule_of_its_inner() -> None:
    class NoBodies(MemorySink):
        accepts_bodies = False

    assert RunCallSink(NoBodies(), 1).accepts_bodies is False
    assert RunCallSink(MemorySink(), 1).accepts_bodies is True


# ── 단계 커서(AD4D) ────────────────────────────────────────────────────


def test_the_sink_writes_the_current_step_of_its_cursor_on_every_record() -> None:
    inner = MemorySink()
    cursor = StepCursor()
    sink = RunCallSink(inner, 41, cursor)
    plain = RunCallSink(inner, 41)  # 커서 없는 싱크(지금 부르는 자리 그대로)
    sink.record(RECORD)  # 단계 밖
    cursor.current = "extract"
    sink.record(RECORD)
    cursor.current = "judge"
    sink.record(replace(RECORD, step="덮어 적힘"))  # 들어온 step 은 커서의 것으로 덮는다
    plain.record(replace(RECORD, step="덮어 적힘"))  # 커서가 없으면 None
    cursor.current = None
    sink.record(RECORD)  # 단계 사이
    assert [(r.run_id, r.step) for r in inner.records] == [
        ("41", None),
        ("41", "extract"),
        ("41", "judge"),
        ("41", None),
        ("41", None),
    ]


def test_the_sink_writes_the_current_segment_of_its_cursor_on_every_record() -> None:
    """RM1a: 구획 안 호출은 커서의 구획 sha 를, 장벽 단계·구획 밖은 None 을 싣는다(들어온 값은 덮는다)."""
    inner = MemorySink()
    cursor = StepCursor()
    sink = RunCallSink(inner, 41, cursor)
    cursor.current = "prepare"
    sink.record(replace(RECORD, segment="덮어 적힘"))
    cursor.current, cursor.segment = "spread", "c" * 64
    sink.record(RECORD)
    cursor.segment = None
    sink.record(RECORD)
    RunCallSink(inner, 41).record(replace(RECORD, segment="덮어 적힘"))  # 커서가 없으면 None
    assert [(r.step, r.segment) for r in inner.records] == [
        ("prepare", None),
        ("spread", "c" * 64),
        ("spread", None),
        (None, None),
    ]


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> Iterator[tasks.RowEvents]:
    """DB 에 쓰지 않는 RowEvents: 블록은 빈 문맥, 행 쓰기는 늘 Recorded, 시계는 마감 앞."""

    def recorded(**_: object) -> Recorded:
        return Recorded()

    def block(**_: object) -> contextlib.nullcontext[None]:
        return contextlib.nullcontext()

    written = SimpleNamespace(step_started=recorded, step_progress=recorded, step_finished=recorded)
    monkeypatch.setattr(tasks, "services", written)
    monkeypatch.setattr(tasks, "transaction", SimpleNamespace(atomic=block))
    monkeypatch.setattr(tasks, "clock", lambda: None)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    yield tasks.RowEvents(company_id=7, run_id=41, attempt=1, deadline=1.0, lease_s=90, storage=FakeStorage())


def test_the_executor_events_set_the_cursor_at_the_start_and_clear_it_at_the_end(events: tasks.RowEvents) -> None:
    assert events.cursor.current is None
    events.step_started("probe.three@1", "extract")
    assert events.cursor.current == "extract"
    events.step_progress("probe.three@1", "extract", 1, 2, {})
    assert events.cursor.current == "extract"  # 진행은 그대로
    events.step_finished("probe.three@1", "extract", StepOutput(data={}))
    assert events.cursor.current is None


def test_a_failed_step_clears_the_cursor(events: tasks.RowEvents) -> None:
    events.step_started("probe.three@1", "judge")
    assert events.cursor.current == "judge"  # 분모
    events.step_failed("probe.three@1", "judge", "ValueError: 지어낸 실패")
    assert events.cursor.current is None


def test_the_events_write_on_the_cursor_they_are_given() -> None:
    cursor = StepCursor()
    given = tasks.RowEvents(
        company_id=7, run_id=41, attempt=1, deadline=1.0, lease_s=90, storage=FakeStorage(), cursor=cursor
    )
    assert given.cursor is cursor
