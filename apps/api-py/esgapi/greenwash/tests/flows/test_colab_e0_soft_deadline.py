"""흐름 greenwash.colab@E0 에서 Celery soft limit 이 「실패한 쪽」·「못 찾은 위치」로 굳지 않고 밖으로 나가는가
(MARC-ISSUE-414, 밴드 GSL1).

엔진의 쪽 고리는 core 를 모르니 흐름이 「다시 던질지」 판별(core 의 soft_deadline_in)을 주입한다. 위치 도구는 직접 본다.
soft limit 은 시험 안 가짜 클래스로 짓는다 — soft_deadline_in 은 조상 클래스의 **이름**으로 가른다. 대조로 같은 자리의
ValueError 는 BASE 그대로 failed_pages·none_error 가 된다.
글은 전부 지은 것(sample_text), 대화는 대본대로 답하는 모의 대화다.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pytest

from esgapi.core.flows.types import FlowStepFailed
from esgapi.core.llm.errors import soft_deadline_in
from esgapi.greenwash.engines.e0.ports import ChatReply, Message, ScriptedChat
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows.test_colab_e0 import detect_pages
from esgapi.greenwash.tools.coordinates import PdfiumCoordinates

PAGE = 3
"""끊기는 쪽(표본의 점검 쪽 1·2·3·4 가운데 셋째)."""


class SoftTimeLimitExceeded(Exception):
    """시험의 가짜 Celery soft limit(이름만 같다)."""


class OnceFailingChat:
    """ScriptedChat 을 감싸, 탐지 프롬프트가 PAGE 쪽을 처음 물을 때 한 번만 error 를 낸다(그 뒤로는 대본대로)."""

    def __init__(self, error: BaseException) -> None:
        self.inner = ScriptedChat()
        self.error: BaseException | None = error
        self.sent: list[list[Message]] = self.inner.sent

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        if self.error is not None and messages[0].content == self.inner.pack.detect_system_prompt:
            page = int(messages[1].content.split("페이지", 1)[0].rsplit(" ", 1)[-1])
            if page == PAGE:
                error, self.error = self.error, None
                self.sent.append(list(messages))
                raise error
        return self.inner.invoke(messages)


@dataclass
class Checkpoints(s.Recorder):
    """judge 의 체크포인트(partial)를 끊지 않고 마지막 것까지 적어 둔다(실행기가 저장하는 값과 같은 자리)."""

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        super().step_progress(flow_id, step, done, total, partial)
        if step == "judge":
            self.saved = dict(partial)


def test_a_soft_limit_on_a_page_leaves_the_flow_and_the_resumed_run_judges_it_again() -> None:
    whole = s.result_of(s.run(s.inputs(), s.adapters()))
    error = SoftTimeLimitExceeded("가상 시간 제한")
    chat = OnceFailingChat(error)
    used = s.adapters(llm=chat)
    events = Checkpoints()

    # (a) 그 예외가 흐름 밖으로 나간다(실행기의 outcome_of 가 미룸으로 끝낼 사슬)
    with pytest.raises(FlowStepFailed) as raised:
        s.run(s.inputs(), used, events=events)
    assert raised.value.step == "judge"
    assert soft_deadline_in(raised.value) is error

    # (b) 체크포인트에 그 쪽은 「실패한 쪽」으로도 「끝난 쪽」으로도 없다
    assert events.saved is not None
    assert events.saved["done_pages"] == [1, 2]
    assert events.saved["failed"] == 0 and events.saved["failed_pages"] == []
    first_part = len(chat.sent)

    # (c) 이어 돌면 그 쪽부터 다시 판정하고, 끝 결과는 끊김 없이 돈 결과와 같다
    carried = {name: events.finished[name] for name in ("extract", "index")}
    resumed = s.run(s.inputs(), used, start_at="judge", carried=carried, resume=events.saved)
    assert s.result_of(resumed) == whole
    assert detect_pages(chat.sent[:first_part]) == [1, 2, PAGE]
    assert detect_pages(chat.sent[first_part:]) == [PAGE, 4]


def test_a_value_error_on_a_page_is_still_a_failed_page() -> None:
    """(d) 보통 예외는 BASE 그대로 삼켜 failed_pages 에 적고 실행은 끝까지 간다(흠 12·19)."""
    flow_run = s.run(s.inputs(), s.adapters(llm=OnceFailingChat(ValueError("가상 값 오류"))))
    judged = flow_run.steps["judge"].data
    assert judged["failed"] == 1
    assert judged["failed_pages"] == [{"page": PAGE, "error": "가상 값 오류"}]
    assert [f["page"] for f in s.result_of(flow_run)["candidateStats"]["failedPages"]] == [PAGE]


def _raising(error: BaseException) -> Callable[..., object]:
    """부르면 error 를 내는 _locate 대역."""

    def locate(*_args: object, **_kwargs: object) -> object:
        raise error

    return locate


def test_a_soft_limit_while_locating_leaves_the_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    error = SoftTimeLimitExceeded("가상 시간 제한")
    coordinates = PdfiumCoordinates()
    monkeypatch.setattr(coordinates, "_locate", _raising(error))
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        coordinates.locate(b"%PDF-1.4 not really", 1, "가상 문장")
    assert raised.value is error
    assert coordinates.stats().get("none_error", 0) == 0


def test_a_value_error_while_locating_is_still_none_error(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinates = PdfiumCoordinates()
    monkeypatch.setattr(coordinates, "_locate", _raising(ValueError("가상 값 오류")))
    assert coordinates.locate(b"%PDF-1.4 not really", 1, "가상 문장") is None
    stats = coordinates.stats()
    assert stats["none_error"] == 1 and stats["error:ValueError"] == 1
