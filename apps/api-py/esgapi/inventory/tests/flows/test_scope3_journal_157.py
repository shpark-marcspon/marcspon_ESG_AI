"""흐름 scope3.colab@157 의 호출 일지(밴드 S3R1 T1 — DB 0): 열쇠 · 열쇠별 되감기 · done · 묶음/20s 체크포인트 ·
넘침 · 엔진 밖으로 빼내기 · partial 에 요청 글 0 · partial 읽기. S3K3: 설정 결함·공급사 거절·비용 상한은 실행을 멈추고
그 밖의 공급사 오류는 결과 값.

공급사는 시험 안 가짜 게이트웨이(엔진 포트 꼴), 글은 전부 지어낸 것이다.
"""

import json
import logging
from collections.abc import Callable, Iterable, Mapping
from typing import cast

import pytest

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError, PromptError
from esgapi.core.llm.types import BudgetExceeded, CallMeta, ErrorKind, LlmResult, ProviderFailed, Scope, Tags
from esgapi.inventory.engines.scope3.colab_157.llm import LlmFailed, LlmText, outcome_of
from esgapi.inventory.engines.scope3.colab_157.ports import LlmGateway
from esgapi.inventory.flows import scope3_journal_157 as journal
from esgapi.inventory.flows.scope3_journal_157 import (
    BATCH_CALLS,
    CHECKPOINT_EVERY_S,
    KINDS,
    Entry,
    JournalGateway,
    JournalTooLarge,
    Scope3BudgetExceeded,
    Scope3ProviderRejected,
    call_key,
    entry_of,
    read_resume,
    result_of,
    unescaped,
)

TAGS = Tags(tenant="가상회사", module="inventory")
PROMPT = "inventory/scope3-colab-group-name@1"
MARKER = "가상표지글-요청에만"
HEAD = {"v": 1, "templateSha256": "t" * 64, "factorBookSha256": "f" * 64, "step": "c1"}


def request(**variables: str) -> CallRequest[object]:
    return CallRequest[object](prompt=PROMPT, route="mock", tags=TAGS, vars=variables, max_output_tokens=20)


class SoftTimeLimitExceeded(Exception):
    """시험의 가짜 Celery soft limit(이름만 같다 — soft_deadline_in 은 조상 클래스의 이름으로 가른다)."""


class FakeYield(BaseException):
    """실행기의 RunYield 꼴(BaseException)."""


class Inner:
    """가짜 공급사 게이트웨이: 부름마다 「답-<n>」, raise_on 번째 부름에서 그 예외."""

    def __init__(self, raise_on: Mapping[int, BaseException] | None = None) -> None:
        self.seen: list[object] = []
        self.raise_on = dict(raise_on or {})

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        self.seen.append(request)
        n = len(self.seen)
        if n in self.raise_on:
            raise self.raise_on[n]
        return cast("LlmResult[T]", result_of(Entry("0" * 64, "success", f"답-{n}")))


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.step = 0.0

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        return value


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    made = Clock()
    monkeypatch.setattr(journal, "monotonic", made)
    return made


class Points:
    """checkpoint 받는 쪽: (partial, done, total) 를 쌓는다. error 를 주면 그것을 던진다."""

    def __init__(self, error: BaseException | None = None) -> None:
        self.got: list[tuple[dict[str, object], int, int]] = []
        self.error = error

    def __call__(self, partial: Mapping[str, object], *, done: int, total: int) -> None:
        self.got.append((dict(partial), done, total))
        if self.error is not None:
            raise self.error


def gateway(
    inner: LlmGateway, points: Points, *, replay: Iterable[Entry], carried: Iterable[Entry] = (), base_done: int = 0
) -> JournalGateway:
    return JournalGateway(inner, replay=replay, carried=carried, base_done=base_done, head=HEAD, checkpoint=points)


def engine_like(call: Callable[[], object]) -> object:
    """엔진의 넓은 except 자리(코랩 `except Exception`)."""
    try:
        return call()
    except Exception:
        return "삼켜짐"


# ── 열쇠 ──


def test_the_key_ignores_the_vars_order_and_keeps_the_text_boundaries() -> None:
    assert call_key(request(a="가", b="나")) == call_key(request(b="나", a="가"))
    assert call_key(request(a="가나", b="")) != call_key(request(a="가", b="나"))
    assert call_key(request(a="가")) != call_key(
        CallRequest[object](prompt=PROMPT, route="other", tags=TAGS, vars={"a": "가"}, max_output_tokens=20)
    )
    assert call_key(request(a="가")) != call_key(
        CallRequest[object](prompt=PROMPT, route="mock", tags=TAGS, vars={"a": "가"}, max_output_tokens=21)
    )
    key = call_key(request(a="가"))
    assert len(key) == 64 and int(key, 16) >= 0


@pytest.mark.parametrize("kind", KINDS)
def test_an_entry_comes_back_as_the_same_engine_outcome(kind: str) -> None:
    text = "" if kind in ("schema_mismatch", "provider_error", "timeout", "budget_exceeded") else "가상 답"
    entry = Entry("a" * 64, kind, text)
    rebuilt = result_of(entry)
    assert rebuilt.kind == kind
    assert entry_of(entry.key, rebuilt) == entry
    seen = outcome_of(cast("LlmResult[str]", rebuilt))
    if kind in ("success", "truncated", "refusal"):
        assert isinstance(seen, LlmText) and seen.text == text
    else:
        assert seen == LlmFailed(kind)


# ── 되감기 ──


def test_replay_is_a_queue_per_key_and_replayed_calls_never_reach_the_provider(clock: Clock) -> None:
    one, two = call_key(request(a="하나")), call_key(request(a="둘"))
    replay = [Entry(one, "success", "첫"), Entry(two, "success", "둘째"), Entry(one, "success", "셋째")]
    inner, points = Inner(), Points()
    gw = gateway(inner, points, replay=replay)
    got = [gw.call(request(a=a)) for a in ("둘", "하나", "하나")]
    assert [r.text for r in got if r.kind == "success"] == ["둘째", "첫", "셋째"]
    assert inner.seen == [] and gw.replayed == 3 and gw.real_calls == 0
    gw.call(request(a="하나"))  # 줄이 비면 실제로 부른다
    assert len(inner.seen) == 1 and gw.real_calls == 1
    assert [e.key for e in gw.entries] == [one]


def test_done_never_goes_down_across_attempts(clock: Clock) -> None:
    points = Points()
    first = gateway(Inner(), points, replay=())
    for n in range(3):
        first.call(request(a=f"줄{n}"))
    first.flush()
    saved, done, _ = points.got[-1]
    assert done == 3 == saved["done"]
    resumed = read_resume(saved, template_sha256="t" * 64, factor_book_sha256="f" * 64, step="c1")
    points2 = Points()
    second = gateway(Inner(), points2, replay=resumed.entries, carried=resumed.entries, base_done=resumed.done)
    for n in range(5):
        second.call(request(a=f"줄{n}"))  # 앞 셋은 되감김, 뒤 둘만 실제
    assert second.real_calls == 2 and second.done == 5
    assert [d for _, d, _ in points2.got] == [5]
    assert all(d >= 3 for _, d, _ in points2.got)
    assert len(second.entries) == 5


def test_a_checkpoint_comes_every_batch_of_real_calls(clock: Clock) -> None:
    points = Points()
    gw = gateway(Inner(), points, replay=())
    for n in range(BATCH_CALLS * 2 + 1):
        gw.call(request(a=f"줄{n}"))
    assert [d for _, d, _ in points.got] == [BATCH_CALLS, BATCH_CALLS * 2]


def test_a_real_call_after_twenty_seconds_checkpoints_before_the_batch_fills(clock: Clock) -> None:
    points = Points()
    gw = gateway(Inner(), points, replay=())
    clock.now = CHECKPOINT_EVERY_S + 1
    gw.call(request(a="하나"))
    assert [d for _, d, _ in points.got] == [1]


def test_replayed_calls_alone_checkpoint_after_twenty_seconds_with_the_same_done(clock: Clock) -> None:
    keys = [call_key(request(a=f"줄{n}")) for n in range(10)]
    inner, points = Inner(), Points()
    gw = gateway(inner, points, replay=[Entry(k, "success", "답") for k in keys], base_done=7)
    clock.step = 5.0
    for n in range(10):
        gw.call(request(a=f"줄{n}"))
    assert inner.seen == []
    assert points.got, "되감기만으로 20s 가 지났는데 체크포인트가 없다"
    assert {d for _, d, _ in points.got} == {7}


# ── 넘침·빼내기 ──


def test_a_partial_over_the_limit_fails_through_the_engines_broad_except(
    clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(journal, "PARTIAL_MAX_BYTES", 200)
    gw = gateway(Inner(), Points(), replay=())

    def calls() -> object:
        for n in range(BATCH_CALLS):
            engine_like(lambda n=n: gw.call(request(a=f"긴줄{n}" * 10)))
        return "끝"

    with pytest.raises(JournalTooLarge):
        unescaped(calls)


def test_a_soft_limit_in_a_call_leaves_the_engine_after_one_last_checkpoint(clock: Clock) -> None:
    error = SoftTimeLimitExceeded("가상 시간 제한")
    points = Points()
    gw = gateway(Inner({2: error}), points, replay=())

    def calls() -> object:
        engine_like(lambda: gw.call(request(a="하나")))
        return engine_like(lambda: gw.call(request(a="둘")))

    with pytest.raises(SoftTimeLimitExceeded) as raised:
        unescaped(calls)
    assert raised.value is error
    assert [d for _, d, _ in points.got] == [1]  # 나가기 전 체크포인트(끊긴 호출은 빠짐)


def test_no_last_checkpoint_when_nothing_is_new(clock: Clock) -> None:
    points = Points()
    gw = gateway(Inner({1: SoftTimeLimitExceeded("가상")}), points, replay=())
    with pytest.raises(SoftTimeLimitExceeded):
        unescaped(lambda: engine_like(lambda: gw.call(request(a="하나"))))
    assert points.got == []


def test_a_checkpoint_error_leaves_the_engine_and_a_yield_passes_as_is(clock: Clock) -> None:
    gw = gateway(Inner(), Points(ValueError("가상 쓰기 실패")), replay=())

    def calls() -> object:
        for n in range(BATCH_CALLS):
            engine_like(lambda n=n: gw.call(request(a=f"줄{n}")))
        return "끝"

    with pytest.raises(ValueError, match="가상 쓰기 실패"):
        unescaped(calls)
    yielding = gateway(Inner(), Points(FakeYield()), replay=())

    def yields() -> object:
        for n in range(BATCH_CALLS):
            engine_like(lambda n=n: yielding.call(request(a=f"줄{n}")))
        return "끝"

    with pytest.raises(FakeYield):
        unescaped(yields)


def test_a_plain_provider_exception_is_not_escaped(clock: Clock) -> None:
    gw = gateway(Inner({1: ValueError("가상")}), Points(), replay=())
    assert unescaped(lambda: engine_like(lambda: gw.call(request(a="하나")))) == "삼켜짐"


# ── partial ──


def test_the_partial_holds_keys_and_answers_but_not_the_request_text(clock: Clock) -> None:
    points = Points()
    gw = gateway(Inner(), points, replay=())
    for n in range(BATCH_CALLS):
        gw.call(request(product=f"{MARKER}{n}", cleaned=MARKER))
    partial, _, _ = points.got[-1]
    body = json.dumps(partial, ensure_ascii=False)
    assert MARKER not in body
    assert MARKER not in json.dumps(gw.journal(), ensure_ascii=False)
    assert set(partial) == {"v", "templateSha256", "factorBookSha256", "step", "done", "journal"}
    entries = cast("list[dict[str, object]]", partial["journal"])
    assert entries and all(set(e) == {"k", "kind", "text"} for e in entries)


def test_read_resume_drops_a_foreign_or_broken_partial_but_keeps_its_done(caplog: pytest.LogCaptureFixture) -> None:
    good = {**HEAD, "done": 4, "journal": [{"k": "b" * 64, "kind": "success", "text": "답"}]}
    args = {"template_sha256": "t" * 64, "factor_book_sha256": "f" * 64, "step": "c1"}
    assert read_resume(None, **args) == journal.EMPTY
    assert read_resume(good, **args).entries == (Entry("b" * 64, "success", "답"),)
    with caplog.at_level(logging.WARNING):
        for wrong in (
            {"templateSha256": "x" * 64},
            {"step": "c2"},
            {"v": 2},
            {"journal": [{"k": "짧음", "kind": "success", "text": ""}]},
        ):
            got = read_resume({**good, **wrong}, **args)
            assert got.entries == () and got.done == 4
        moved = read_resume({**good, "factorBookSha256": "g" * 64}, **args)
    assert moved.entries == (Entry("b" * 64, "success", "답"),)
    assert "scope3_journal_factor_book_changed" in caplog.text
    assert read_resume({**good, "done": -1}, **args) == journal.EMPTY


def test_a_gateway_that_does_not_record_never_counts_real_calls_as_progress(clock: Clock) -> None:
    """assemble 꼴(record=False): 실제 호출은 저장되지 않아 다음 시도가 또 낸다 — done 은 그대로(가지 리뷰 MEDIUM 1)."""
    points = Points()
    inner = Inner()
    gw = JournalGateway(inner, replay=(), head={"v": 1, "step": "assemble"}, checkpoint=points, record=False)
    for n in range(BATCH_CALLS * 2):
        gw.call(request(a=f"줄{n}"))
    assert len(inner.seen) == BATCH_CALLS * 2 and gw.real_calls == BATCH_CALLS * 2
    assert [d for _, d, _ in points.got] == [0, 0]  # 마감 확인용 체크포인트는 나되 진행은 0
    assert all(p["journal"] == [] for p, _, _ in points.got)


def test_the_last_checkpoint_does_not_swallow_a_keyboard_interrupt(clock: Clock) -> None:
    points = Points(KeyboardInterrupt())
    gw = gateway(Inner({2: SoftTimeLimitExceeded("가상")}), points, replay=())
    gw.call(request(a="하나"))
    with pytest.raises(KeyboardInterrupt):
        gw.call(request(a="둘"))


# ── 실행을 멈추는 빼냄(밴드 S3K3 — MARC-ISSUE-521): 설정 결함 셋 · 공급사 401·403·404·429 크레딧 소진 ──


class Answering:
    """가짜 공급사 게이트웨이: 부름마다 같은 결과 값(지어낸 ProviderFailed 등)."""

    def __init__(self, result: LlmResult[object]) -> None:
        self.result = result
        self.seen = 0

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        self.seen += 1
        return cast("LlmResult[T]", self.result)


def failed(
    status: int | None, *, retryable: bool = False, message: str = "가상 공급사 글", error_kind: ErrorKind | None = None
) -> LlmResult[object]:
    return ProviderFailed(status=status, retryable=retryable, message=message, meta=META, error_kind=error_kind)


META = CallMeta(call_id="가상", prompt_id="가상", attempts=(), total_cost_usd=0.0, warnings=())


class DerivedSetup(LiveSetupError):
    """시험 안 하위 클래스 — 정확 일치라 빼내지 않는다(실행기 표와 같은 뜻)."""


@pytest.mark.parametrize("error", [LiveSetupError, LlmConfigError, PromptError])
def test_a_setup_error_leaves_the_engine_without_a_journal_entry_or_checkpoint(
    clock: Clock, error: type[Exception]
) -> None:
    points = Points()
    inner = Inner({BATCH_CALLS + 1: error("가상 설정 결함")})
    gw = gateway(inner, points, replay=())
    for n in range(BATCH_CALLS):
        gw.call(request(a=f"줄{n}"))
    before = len(points.got)
    with pytest.raises(error, match="가상 설정 결함"):
        unescaped(lambda: engine_like(lambda: gw.call(request(a="셋"))))
    assert len(points.got) == before  # 나가기 전 체크포인트 0
    assert len(gw.entries) == BATCH_CALLS  # 그 칸 0


def test_a_subclass_of_a_setup_error_is_still_swallowed(clock: Clock) -> None:
    gw = gateway(Inner({1: DerivedSetup("가상")}), Points(), replay=())
    assert unescaped(lambda: engine_like(lambda: gw.call(request(a="하나")))) == "삼켜짐"


@pytest.mark.parametrize(
    ("status", "message", "said"),
    [
        (401, "가상 공급사 글", "status 401"),
        (403, "가상 공급사 글", "status 403"),
        (404, "가상 공급사 글", "모델·경로를 찾지 못했다(status 404)"),
        (429, "Error code: 429 - {'error': {'code': 'insufficient_quota'}}", "status 429 insufficient_quota"),
    ],
)
def test_a_provider_refusal_leaves_the_engine_as_rejected(clock: Clock, status: int, message: str, said: str) -> None:
    points = Points()
    inner = Answering(failed(status, retryable=status == 429, message=message))
    gw = gateway(inner, points, replay=())
    with pytest.raises(Scope3ProviderRejected) as raised:
        unescaped(lambda: engine_like(lambda: gw.call(request(a=MARKER))))
    assert said in str(raised.value)
    assert MARKER not in str(raised.value) and "가상 공급사 글" not in str(raised.value)  # 요청·공급사 글 0
    assert (inner.seen, gw.entries, points.got, gw.real_calls) == (1, [], [], 0)


@pytest.mark.parametrize(
    ("status", "retryable", "message"),
    [
        (500, True, "가상 서버 오류"),
        (429, True, "Error code: 429 - {'error': {'code': 'rate_limit_exceeded'}}"),
        (None, False, "가상 연결 실패"),
        (400, False, "가상 잘못된 요청"),
    ],
    ids=["500", "429-rate", "no-status", "400"],
)
def test_other_provider_failures_stay_result_values(
    clock: Clock, status: int | None, retryable: bool, message: str
) -> None:
    gw = gateway(Answering(failed(status, retryable=retryable, message=message)), Points(), replay=())
    got = unescaped(lambda: engine_like(lambda: gw.call(request(a="하나"))))
    assert outcome_of(cast("LlmResult[str]", got)) == LlmFailed("provider_error")
    assert [e.kind for e in gw.entries] == ["provider_error"]


# ── 크레딧·지출 상한 소진을 이름으로(밴드 S3Q3 — MARC-ISSUE-523): 호출 층의 error_kind quota_exhausted 가 가른다 ──


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (429, "Error code: 429 - {'error': {'code': 'credit_balance_exhausted'}}"),  # ① 글에 insufficient_quota 없음
        (402, "가상 청구 오류"),  # ② anthropic 402 billing_error
        (429, "가상 지출 상한 글"),  # ② anthropic 지출 상한(LB1 이 quota_exhausted 로 싣는 꼴)
        (None, "가상 공급사 글"),
    ],
    ids=["openai-credit", "anthropic-402", "anthropic-spend-cap", "no-status"],
)
def test_a_quota_exhausted_kind_leaves_the_engine_as_rejected(clock: Clock, status: int | None, message: str) -> None:
    points = Points()
    inner = Answering(failed(status, message=message, error_kind="quota_exhausted"))
    gw = gateway(inner, points, replay=())
    with pytest.raises(Scope3ProviderRejected) as raised:
        unescaped(lambda: engine_like(lambda: gw.call(request(a=MARKER))))
    assert "크레딧·할당량이 바닥났다" in str(raised.value) and f"status {status} quota_exhausted" in str(raised.value)
    assert MARKER not in str(raised.value) and message not in str(raised.value)  # 요청·공급사 글 0
    assert (inner.seen, gw.entries, points.got, gw.real_calls) == (1, [], [], 0)


def test_the_old_quota_text_without_a_kind_is_still_rejected(clock: Clock) -> None:
    """④ 옛 글 판정(error_kind 를 안 싣는 길의 안전망): 429 + insufficient_quota, error_kind None."""
    message = "Error code: 429 - {'error': {'code': 'insufficient_quota'}}"
    inner = Answering(failed(429, retryable=True, message=message))
    gw = gateway(inner, Points(), replay=())
    with pytest.raises(Scope3ProviderRejected, match="status 429 insufficient_quota"):
        unescaped(lambda: engine_like(lambda: gw.call(request(a="하나"))))


@pytest.mark.parametrize(
    ("status", "kind", "message"),
    [
        (429, "rate_limited", "Error code: 429 - {'error': {'code': 'rate_limit_exceeded'}}"),  # ③
        (529, "overloaded", "가상 과부하"),  # ③
        (503, "overloaded", "가상 과부하"),  # ③ openai server_is_overloaded
        (429, "rate_limited", "Error code: 429"),  # ⑤ 본문 없는 429 — 본문 기댐으로 충분(523 노트)
    ],
    ids=["429-rate", "529-overloaded", "503-overloaded", "429-no-body"],
)
def test_rate_limits_and_overloads_stay_result_values(clock: Clock, status: int, kind: ErrorKind, message: str) -> None:
    gw = gateway(Answering(failed(status, retryable=True, message=message, error_kind=kind)), Points(), replay=())
    got = unescaped(lambda: engine_like(lambda: gw.call(request(a="하나"))))
    assert outcome_of(cast("LlmResult[str]", got)) == LlmFailed("provider_error")
    assert [e.kind for e in gw.entries] == ["provider_error"]


def test_a_replayed_provider_error_is_not_escaped(clock: Clock) -> None:
    key = call_key(request(a="하나"))
    inner = Inner()
    gw = gateway(inner, Points(), replay=[Entry(key, "provider_error", "")])
    got = unescaped(lambda: engine_like(lambda: gw.call(request(a="하나"))))
    assert outcome_of(cast("LlmResult[str]", got)) == LlmFailed("provider_error")
    assert inner.seen == []


# ── 실행 비용 상한(S3K3 ②): 넘은 첫 부름에서 멈춤 · 되감은 상한 칸은 버리고 다시 부름 ──


def over_budget() -> LlmResult[object]:
    return BudgetExceeded(limit_usd=0.5, spent_usd=0.75, scope=Scope(), meta=META)


class OverAfter(Inner):
    """from_call 번째 부름부터 상한 초과(그 전은 Inner 의 「답-<n>」)."""

    def __init__(self, from_call: int) -> None:
        super().__init__()
        self.from_call = from_call

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        if len(self.seen) + 1 >= self.from_call:
            self.seen.append(request)
            return cast("LlmResult[T]", over_budget())
        return super().call(request)


def test_a_budget_stop_leaves_the_engine_at_the_first_call_over(clock: Clock) -> None:
    points = Points()
    inner = OverAfter(3)
    gw = gateway(inner, points, replay=())

    def calls() -> object:
        for n in range(6):
            engine_like(lambda n=n: gw.call(request(a=f"줄{n}")))
        return "끝"

    with pytest.raises(Scope3BudgetExceeded) as raised:
        unescaped(calls)
    assert "비용 상한" in str(raised.value) and "0.5 USD" in str(raised.value)
    assert len(inner.seen) == 3  # 넘은 첫 부름 뒤 부름 0
    assert [e.text for e in gw.entries] == ["답-1", "답-2"]  # 상한 칸 0
    assert len(points.got) == 1  # 앞 묶음의 체크포인트 하나뿐 — 나가기 전 체크포인트 0


def test_a_replayed_budget_entry_is_dropped_and_called_again(clock: Clock) -> None:
    key = call_key(request(a="하나"))
    inner = Inner()
    gw = gateway(inner, Points(), replay=[Entry(key, "budget_exceeded", ""), Entry(key, "success", "앞 답")])
    first = unescaped(lambda: engine_like(lambda: gw.call(request(a="하나"))))
    assert outcome_of(cast("LlmResult[str]", first)) == LlmText("앞 답", "success")  # 상한 칸은 건너뜀
    second = unescaped(lambda: engine_like(lambda: gw.call(request(a="하나"))))
    assert outcome_of(cast("LlmResult[str]", second)) == LlmText("답-1", "success")  # 줄이 비어 실제로 부름
    lonely = gateway(Inner(), Points(), replay=[Entry(key, "budget_exceeded", "")])
    got = unescaped(lambda: engine_like(lambda: lonely.call(request(a="하나"))))
    assert outcome_of(cast("LlmResult[str]", got)) == LlmText("답-1", "success")
    assert [e.kind for e in lonely.entries] == ["success"] and lonely.real_calls == 1
