# pyright: basic
"""스캔 루프의 이어 돌기 꼭지(resume·checkpoint, 밴드 GL1). 꼭지가 없으면 GW1 그대로, 있으면 흐름의 judge 가 쓰는 꼴.

글은 전부 지은 것(sample_text), 대화는 대본대로 답하는 모의 대화다.
"""

import copy

import pytest

from esgapi.greenwash.engines.e0.checker import scan_report_greenwashing_pages
from esgapi.greenwash.engines.e0.ports import ScriptedChat
from esgapi.greenwash.tests.conftest import StubIndex

CONFIG = {"debug": True, "debug_pages": 2}
PARTIAL_KEYS = {"done_pages", "results", "agg", "failed", "failed_pages"}


class _FailingChat:
    """탐지 프롬프트의 user 글이 가리키는 쪽이 fail_pages 에 들면 예외를 낸다(쪽 하나가 죽는 길)."""

    def __init__(self, fail_pages):
        self.inner = ScriptedChat()
        self.fail_pages = set(fail_pages)
        self.sent = self.inner.sent

    def invoke(self, messages):
        if messages[0].content == self.inner.pack.detect_system_prompt:
            page = int(messages[1].content.split("페이지", 1)[0].rsplit(" ", 1)[-1])
            if page in self.fail_pages:
                self.sent.append(list(messages))
                raise RuntimeError(f"가상의 실패: {page}쪽")
        return self.inner.invoke(messages)


class _Stop(Exception):
    pass


def _scan(docs, pages, chat, **hooks):
    return scan_report_greenwashing_pages(
        docs, pages, evidence_allowed_pages=pages, config=dict(CONFIG), vectorstore=StubIndex(), llm=chat, **hooks
    )


def _fields(out):
    return (out.results, out.agg, out.failed, out.failed_pages, out.pages_norm, out.allowed_norm, out.total_pages)


def _texts(sent):
    return [[(m.role, m.content) for m in msgs] for msgs in sent]


# (a) 꼭지 없음 = 지금
@pytest.mark.parametrize("fail_pages", [[], [2]])
def test_no_hooks_is_the_plain_call(sample_docs, fail_pages):
    plain_chat, hooked_chat = _FailingChat(fail_pages), _FailingChat(fail_pages)
    plain = _scan(sample_docs, [1, 2, 3, 4], plain_chat)
    hooked = _scan(sample_docs, [1, 2, 3, 4], hooked_chat, resume=None, checkpoint=None)
    assert _fields(hooked) == _fields(plain)
    assert list(hooked.agg) == list(plain.agg)
    assert _texts(hooked_chat.sent) == _texts(plain_chat.sent)
    assert plain.failed == len(fail_pages)
    assert list(hooked.agg) == ["raw", "hard_dropped", "non_env_dropped", "promo_dropped", "table_dropped", "kept"]


def test_an_empty_resume_starts_from_the_beginning(sample_docs):
    """판정은 truthiness(if resume:) — 빈 dict 는 이어 돌기가 아니다(흐름이 빈 resume 을 넘길 수 있다)."""
    plain_chat, empty_chat = ScriptedChat(), ScriptedChat()
    plain = _scan(sample_docs, [1, 2, 3, 4], plain_chat)
    empty = _scan(sample_docs, [1, 2, 3, 4], empty_chat, resume={})
    assert _fields(empty) == _fields(plain)
    assert _texts(empty_chat.sent) == _texts(plain_chat.sent)


# (b) checkpoint 는 쪽마다 한 번, 실패한 쪽에도
def test_checkpoint_once_per_page_including_a_failed_one(sample_docs):
    calls = []

    def checkpoint(partial, done, total):
        calls.append((copy.deepcopy(partial), done, total))

    out = _scan(sample_docs, [1, 2, 3, 4], _FailingChat([2]), checkpoint=checkpoint)
    assert [(d, t) for _, d, t in calls] == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert all(set(p) == PARTIAL_KEYS for p, _, _ in calls)
    assert [p["done_pages"] for p, _, _ in calls] == [[1], [1, 2], [1, 2, 3], [1, 2, 3, 4]]
    assert [p["failed"] for p, _, _ in calls] == [0, 1, 1, 1]
    assert calls[1][0]["failed_pages"] == [{"page": 2, "error": "가상의 실패: 2쪽"}]
    last = calls[-1][0]
    assert (last["results"], last["agg"], last["failed"], last["failed_pages"]) == (
        out.results,
        out.agg,
        out.failed,
        out.failed_pages,
    )


def test_an_exception_from_checkpoint_is_not_a_page_failure(sample_docs):
    """checkpoint 는 쪽 실패를 삼키는 try 밖에서 불린다 — 끊김은 그대로 올라간다."""

    def checkpoint(partial, done, total):
        raise _Stop(done)

    with pytest.raises(_Stop):
        _scan(sample_docs, [1, 2, 3, 4], ScriptedChat(), checkpoint=checkpoint)


# (c) resume: 끝난 쪽은 대화 포트를 다시 부르지 않고, 결과는 끊김 없는 실행과 같다
@pytest.mark.parametrize("fail_pages", [[], [1]])
def test_resume_after_the_second_page_is_the_whole_run(sample_docs, fail_pages):
    whole_chat = _FailingChat(fail_pages)
    whole = _scan(sample_docs, [1, 2, 3, 4], whole_chat)

    chat = _FailingChat(fail_pages)
    saved = {}

    def stop_after_two(partial, done, total):
        if done == 2:
            saved.update(copy.deepcopy(partial))
            raise _Stop(done)

    with pytest.raises(_Stop):
        _scan(sample_docs, [1, 2, 3, 4], chat, checkpoint=stop_after_two)
    assert saved["done_pages"] == [1, 2] and saved["failed"] == len(fail_pages)
    first_part = len(chat.sent)

    progress = []
    resumed = _scan(sample_docs, [1, 2, 3, 4], chat, resume=saved, checkpoint=lambda p, d, t: progress.append((d, t)))
    assert progress == [(3, 4), (4, 4)]
    assert _fields(resumed) == _fields(whole)
    # 앞 둘째 쪽까지의 호출은 다시 일어나지 않는다: 두 다리를 이은 메시지가 끊김 없는 실행과 같다
    assert _texts(chat.sent) == _texts(whole_chat.sent)
    assert len(chat.sent) > first_part


def test_resume_does_not_alias_the_saved_partial(sample_docs):
    saved = {
        "done_pages": [1],
        "results": [],
        "agg": dict.fromkeys(("raw", "kept"), 0),
        "failed": 0,
        "failed_pages": [],
    }
    before = copy.deepcopy(saved)
    _scan(sample_docs, [1, 2], ScriptedChat(), resume=saved)
    assert saved == before


# (d) 빈 쪽 목록·범위 밖 쪽만 → checkpoint 0 회, 결과는 꼭지 없는 것과 같음
@pytest.mark.parametrize("pages", [[], [0, 99, "x"]])
def test_no_pages_never_checkpoints(sample_docs, pages):
    calls = []
    plain = _scan(sample_docs, pages, ScriptedChat())
    hooked = _scan(sample_docs, pages, ScriptedChat(), checkpoint=lambda *a: calls.append(a), resume=None)
    assert calls == []
    assert _fields(hooked) == _fields(plain)
    assert hooked.results == [] and hooked.failed == 0 and hooked.pages_norm == []
    assert list(hooked.agg) == ["raw", "hard_dropped", "non_env_dropped", "promo_dropped", "table_dropped", "kept"]
