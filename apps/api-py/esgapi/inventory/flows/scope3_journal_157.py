"""흐름 scope3.colab@157 의 호출 일지: 엔진 포트(`LlmGateway`)를 감싸 실제 공급사 호출마다 답을 적고, 묶음마다
체크포인트로 남긴다. 다음 시도·다음 카테고리 단계는 그 일지를 되감아 공급사를 다시 부르지 않고 같은 답을 엔진에 준다
(MARC-ISSUE-499, 사용자 결정 MARC-ENT-527, 밴드 S3R1). 꼴은 번역 일지(translation/tools/call_journal.py — TRR1)를
옮겼고 import 하지 않는다.

엔진(engines/scope3/colab_157)은 0줄이다(MARC-ENT-442): 같은 입력·같은 답이면 같은 출력이다. 단, 카테고리 단계는 거른
템플릿으로 엔진을 다시 돌려 부름의 **차례**가 한 번 돌기와 다를 수 있다(후처리·캐시 — 보고 C0-2). 그래서 되감기는
차례 목록이 아니라 **열쇠별 줄**이다: 같은 열쇠는 적힌 차례대로 하나씩 쓰고, 줄이 비었을 때만 실제로 부른다.

    열쇠        sha256(json.dumps([prompt, route, vars(열쇠 차례), max_output_tokens, schema_name, temperature],
                ensure_ascii=False)) — JSON 배열이라 칸 경계가 글에 섞이지 않는다. 꼬리표(tags)는 실행 하나에 같아
                뺐다. schema·attachments·timeout_ms·max_schema_retries 는 엔진이 주지 않아(engines/…/llm.py
                `call_text` — 글 요청뿐) 뺐다. 엔진이 그 칸을 주기 시작하면 열쇠에 넣는다.
                요청 본문(vars)은 일지에 넣지 않는다(7a 선 ③)
    칸 하나     {"k": 열쇠, "kind": 결과 갈래, "text": 글}. 엔진이 결과에서 읽는 것은 kind 와 글뿐이다
                (engines/…/llm.py `outcome_of`) — 되감을 때 그 갈래의 LlmResult 를 다시 짓는다(meta 는 빈 값)
    done        시도를 넘어 줄지 않는다: 앞 partial 의 done + 이 시도의 실제 호출 수(되감은 칸은 세지 않음).
                total = max(어림, done)
    체크포인트  (a) 실제 호출 BATCH_CALLS 번마다, 또는 마지막 체크포인트에서 CHECKPOINT_EVERY_S 가 지난 뒤 첫 호출 끝
                (b) 되감은 호출만으로도 CHECKPOINT_EVERY_S 가 지났으면(done 그대로 — 실행기의 협조 마감 확인용).
                그래서 체크포인트 사이 한 칸 ≤ 20s + G(호출 사이 순수 계산 최대 — C0 실측 1초 안)다.
                직렬화가 PARTIAL_MAX_BYTES 를 넘으면 실패(JournalTooLarge)

엔진 밖으로 빼내는 예외(엔진의 넓은 except 48곳 가운데 다시 던지는 곳은 11곳뿐이라 — 보고 C0):
    (a) 호출 안의 소프트 시간 제한(core `soft_deadline_in`) — 나가기 전에 체크포인트를 한 번 해 본다(best-effort)
    (b) 체크포인트가 던지는 Exception 전부(왕복 실패·사건 쪽 예외·쓰기 실패)
    (c) JournalTooLarge
    (d) 설정 결함 셋(core LiveSetupError·LlmConfigError·PromptError — 정확한 클래스만, 하위 클래스는 아님. 실행기 표
        runs/calc/errors.py 와 같은 뜻): 키 없음(mock 배포본 포함)·경로·프롬프트. 코랩은 키가 없으면 노트북 머리에서
        멈춘다 — 시트 실패로 삼키면 빈 결과가 done 이 된다(MARC-ISSUE-521, 밴드 S3K3). 실행기 code setup_error
        (PromptError 는 step_error)
    (e) 공급사가 이 실행의 호출을 받지 않는 결과(실제 부름의 ProviderFailed 가 status 401·403·404, 또는 크레딧·청구·
        지출 상한 소진 — 호출 층이 싣는 error_kind `quota_exhausted`(LB1: openai 429 소진 code·anthropic 402·지출
        상한·gemini 402), 또는 429 에 글 `insufficient_quota`(옛 판정 그대로 — error_kind 를 안 싣는 길의 안전망))
        → Scope3ProviderRejected(step_error). 다시 불러도 같아 남은 줄이 다 빈다.
        그 밖의 공급사 오류(5xx·429 속도 제한 rate_limited·과부하 overloaded·시간 초과·status 없음)는 코랩대로 결과
        값(LlmFailed — MARC-ENT-442). 되감은 provider_error 칸은 status·error_kind 가 없어(일지 칸 꼴) 빼내지 않는다
    (f) 실제 부름이 실행 비용 상한(BudgetExceeded — runs/context.py 의 실행 하나 누적, live 만)에 닿음 →
        Scope3BudgetExceeded(step_error, 글에 「비용 상한」). 넘은 첫 부름에서 멈춘다 — 남은 줄이 빈 채 done 이
        되지 않게(MARC-ISSUE-521). 되감은 budget_exceeded 칸(BASE 판 일지)은 빼내지도 되감지도 않고 버린 뒤 실제로
        다시 부른다: 이어 돈 실행은 상한 누적이 그 실행의 것부터 다시 세어져 상한이 남았을 수 있다
  모두 `_Escape(original)`(BaseException)로 싸 던지고, 흐름이 엔진 밖에서 `unescaped` 로 풀어 원래 예외를 되던진다
  → run_flow → FlowStepFailed → 실행기 갈래(소프트 제한 = RunDeferred, 그 밖은 failed). 실행기의 RunYield
  (BaseException)는 그대로 지나간다. (d)(e)(f) 는 그 칸을 일지에 적지 않고 체크포인트도 하지 않는다(실패한 실행은
  끝이다). 설정을 고친 뒤 이어 돌기(resumeFromRunId)는 끝난 단계만 옮기므로(runs 의 _carried·_plan — 실패한 단계의
  partial 은 옮기지 않음) 실패한 카테고리 단계를 처음부터 다시 돈다(앞 단계 일지는 되감음 — 공급사 0).
게이트웨이가 결과 값 대신 던진 그 밖의 예외(ValueError 등)는 일지에 적지 않고 엔진이 시트 실패로 남긴다 — 결정적이어야
바이트가 같다(되감는 단계가 그 요청을 다시 부른다). 실제 LlmClient.call 이 던지는 것은 공급사를 부르기 전의 설정 결함
(d) 과 soft limit 뿐이다.
"""

import hashlib
import json
import logging
import re
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Final, cast

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import LiveSetupError, LlmConfigError, PromptError, soft_deadline_in
from esgapi.core.llm.types import (
    BudgetExceeded,
    CallMeta,
    CutOff,
    LlmResult,
    ProviderFailed,
    Refused,
    SchemaMismatch,
    Scope,
    Success,
    TimedOut,
)
from esgapi.inventory.engines.scope3.colab_157.ports import LlmGateway

logger = logging.getLogger(__name__)

JOURNAL_VERSION: Final = 1
CHECKPOINT_EVERY_S: Final = 20.0
"""체크포인트 간격(초 — 어림): 실행기 마감 여유 60초(runs/calc/deadline.py)의 1/3(TRR1 과 같은 값)."""
BATCH_CALLS: Final = 2
"""묶음 = 실제 공급사 호출 n 번. n = max(1, ⌊20s ÷ 한 호출⌋), 한 호출은 [추정] 9.7s(MARC-ISSUE-499 「2,000건 120분」
÷ 지어낸 1,984행 판의 호출 743 — 보고 C0-4, 감독 n=2 결정)."""
PARTIAL_MAX_BYTES: Final = 8 * 1024 * 1024
"""partial·단계 data 직렬화 상한: 단계 행 CHECK RUN_STEP_DATA_MAX_OCTETS 16MiB(runs/models.py)의 절반. 지어낸 1,984행
판의 일지가 약 130KB(보고 C0-4)."""

KINDS: Final = ("success", "truncated", "refusal", "schema_mismatch", "provider_error", "timeout", "budget_exceeded")
_KEY: Final = re.compile(r"[0-9a-f]{64}")
_META: Final = CallMeta(call_id="journal", prompt_id="journal", attempts=(), total_cost_usd=0.0, warnings=())


SETUP_ERRORS: Final[tuple[type[Exception], ...]] = (LiveSetupError, LlmConfigError, PromptError)
"""엔진 밖으로 빼내는 설정 결함(머리말 (d)) — 정확한 클래스로 고른다."""
REJECTED_STATUSES: Final = frozenset({401, 403, 404})
QUOTA_STATUS: Final = 429
QUOTA_KIND: Final = "quota_exhausted"
"""크레딧·청구·지출 상한 소진의 이름(core types.ErrorKind — 어댑터가 공식 문서의 상태·본문 code 로 가른다, LB1)."""
QUOTA_MARK: Final = "insufficient_quota"
"""OpenAI 의 크레딧 소진 code(429 를 속도 제한과 가르는 글 — SDK 오류 글 「Error code: 429 - {본문}」에 실린다). 옛
판정이다: error_kind(QUOTA_KIND)가 먼저 가르고, 이 글은 error_kind 를 싣지 않은 429 의 안전망으로만 남겼다."""


class JournalTooLarge(Exception):
    """partial 이 PARTIAL_MAX_BYTES 를 넘는다 — 그 실행은 실패한다."""


class Scope3BudgetExceeded(Exception):
    """실행 비용 상한에 닿았다(머리말 (f)) — 그 실행은 실패한다(step_error). 글에 상한·누적 USD 만."""


class Scope3ProviderRejected(Exception):
    """공급사가 이 실행의 호출을 받지 않는다(머리말 (e)) — 그 실행은 실패한다(step_error). 글에 status 만(키·요청 0)."""


class _Escape(BaseException):
    """엔진 밖으로 빼낼 예외를 싼다. 흐름만 받는다(unescaped)."""

    def __init__(self, original: BaseException) -> None:
        super().__init__(type(original).__name__)
        self.original = original


def unescaped[T](call: Callable[[], T]) -> T:
    """엔진을 부르는 자리를 감싼다: 싼 예외를 풀어 원래 예외를 던진다."""
    try:
        return call()
    except _Escape as escape:
        raise escape.original from None


def monotonic() -> float:
    """체크포인트 간격을 재는 시계. ★ 이음매다(시험이 바꿔 끼운다 — 부를 때 모듈 속성으로 읽는다)."""
    return time.monotonic()


def call_key(request: CallRequest[object]) -> str:
    body = [
        request.prompt,
        request.route,
        dict(sorted(request.vars.items())),
        request.max_output_tokens,
        request.schema_name,
        request.temperature,
    ]
    return hashlib.sha256(json.dumps(body, ensure_ascii=False).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Entry:
    key: str
    kind: str
    text: str

    def to_json(self) -> dict[str, object]:
        return {"k": self.key, "kind": self.kind, "text": self.text}


def entry_of(key: str, result: LlmResult[object]) -> Entry:
    match result:
        case Success() | Refused():
            return Entry(key, result.kind, result.text)
        case CutOff():
            return Entry(key, result.kind, result.partial_text)
        case _:
            return Entry(key, result.kind, "")


def result_of(entry: Entry) -> LlmResult[object]:
    """칸 → 엔진이 보는 갈래(kind·글). 엔진은 schema 없이 부르므로 성공의 data 는 글 그대로다."""
    match entry.kind:
        case "success":
            return Success(data=entry.text, text=entry.text, meta=_META)
        case "truncated":
            return CutOff(partial_text=entry.text, meta=_META)
        case "refusal":
            return Refused(text=entry.text, category=None, meta=_META)
        case "schema_mismatch":
            return SchemaMismatch(issues=(), raw_text=entry.text, meta=_META)
        case "timeout":
            return TimedOut(message="journal", meta=_META)
        case "budget_exceeded":
            return BudgetExceeded(limit_usd=0.0, spent_usd=0.0, scope=Scope(), meta=_META)
        case _:
            return ProviderFailed(status=None, retryable=False, message="journal", meta=_META)


def provider_rejected(result: LlmResult[object]) -> Scope3ProviderRejected | None:
    """실제 부름의 결과가 머리말 (e) 면 그 예외(던지지 않고 돌려줌), 아니면 None."""
    if not isinstance(result, ProviderFailed):
        return None
    if result.status == 404:
        return Scope3ProviderRejected("공급사가 모델·경로를 찾지 못했다(status 404)")
    if result.status in REJECTED_STATUSES:
        return Scope3ProviderRejected(f"공급사가 호출을 거절했다(status {result.status})")
    if result.error_kind == QUOTA_KIND:
        return Scope3ProviderRejected(f"공급사의 크레딧·할당량이 바닥났다(status {result.status} {QUOTA_KIND})")
    if result.status == QUOTA_STATUS and QUOTA_MARK in result.message:
        return Scope3ProviderRejected(f"공급사의 크레딧·할당량이 바닥났다(status {QUOTA_STATUS} {QUOTA_MARK})")
    return None


def read_entries(raw: object) -> tuple[Entry, ...] | None:
    """JSON 목록 → 칸들. 꼴이 하나라도 틀리면 None."""
    if not isinstance(raw, list):
        return None
    out: list[Entry] = []
    for item in cast("list[object]", raw):
        if not isinstance(item, Mapping):
            return None
        value = cast("Mapping[str, object]", item)
        key, kind, text = value.get("k"), value.get("kind"), value.get("text")
        if not isinstance(key, str) or _KEY.fullmatch(key) is None or kind not in KINDS or not isinstance(text, str):
            return None
        out.append(Entry(key, cast("str", kind), text))
    return tuple(out)


@dataclass(frozen=True, slots=True)
class Resumed:
    """앞 시도가 이 단계에 남긴 일지(받을 수 없으면 빈 것)와 done."""

    entries: tuple[Entry, ...]
    done: int


EMPTY: Final = Resumed(entries=(), done=0)


def read_resume(
    resume: Mapping[str, object] | None, *, template_sha256: str, factor_book_sha256: str, step: str
) -> Resumed:
    """partial → 일지. v·templateSha256·step 이 다르거나 꼴이 틀리면 경고 한 줄과 빈 일지 — 저장된 done 이 꼴에 맞으면
    그 값은 살린다(일지를 버려도 진행 수가 줄지 않게). factorBookSha256 가 다르면 경고만(되감기는 그대로).
    ★ 그래서 일지를 버린 뒤 다시 부른 호출이 살린 done 위에 얹혀 진행 수(done)가 실제 호출 수보다 클 수 있다(과대 —
    진행 판정이 줄지 않는 쪽을 골랐다, 가지 리뷰 LOW 5)."""
    if resume is None:
        return EMPTY
    raw_done = resume.get("done")
    valid_done = isinstance(raw_done, int) and not isinstance(raw_done, bool) and raw_done >= 0
    done = cast("int", raw_done) if valid_done else 0
    if (resume.get("v"), resume.get("templateSha256"), resume.get("step")) != (JOURNAL_VERSION, template_sha256, step):
        logger.warning("scope3_journal_ignored reason=head step=%s", step)
        return Resumed(entries=(), done=done)
    entries = read_entries(resume.get("journal"))
    if not valid_done or entries is None:
        logger.warning("scope3_journal_ignored reason=shape step=%s", step)
        return Resumed(entries=(), done=done)
    if resume.get("factorBookSha256") != factor_book_sha256:
        logger.warning("scope3_journal_factor_book_changed step=%s", step)
    return Resumed(entries=entries, done=done)


def serialized_size(value: Mapping[str, object]) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


class JournalGateway:
    """엔진 포트 하나(머리말). inner 는 실제로 부를 게이트웨이, checkpoint 는 StepContext.checkpoint 꼴.

    replay   되감을 칸(앞 단계들의 일지 + 이 단계의 앞 시도 일지). 열쇠별 줄로 쓴다
    carried  이 단계에 이미 속한 칸(앞 시도 일지) — `entries` 의 앞머리가 된다
    head     partial 의 머리 칸(v·templateSha256·… — done·journal 은 이 게이트웨이가 붙인다)
    """

    def __init__(
        self,
        inner: LlmGateway,
        *,
        replay: Iterable[Entry],
        carried: Iterable[Entry] = (),
        base_done: int = 0,
        head: Mapping[str, object],
        checkpoint: Callable[..., None],
        estimate: int = 0,
        record: bool = True,
    ) -> None:
        self.inner = inner
        self._queues: dict[str, deque[Entry]] = {}
        for entry in replay:
            self._queues.setdefault(entry.key, deque()).append(entry)
        self.entries: list[Entry] = list(carried)
        self._base_done = base_done
        self._head = dict(head)
        self._checkpoint = checkpoint
        self._estimate = estimate
        self._record_entries = record
        self.real_calls = 0
        self.replayed = 0
        self._unflushed = 0
        self._last = monotonic()

    @property
    def done(self) -> int:
        # 적지 않는 게이트웨이(assemble)의 실제 호출은 저장되지 않아 다음 시도가 또 낸다 — 진행으로 세지 않는다
        # (가지 리뷰 MEDIUM 1: 세면 일지가 모자란 assemble 이 시도마다 진행인 척해 stalled 상한을 피한다)
        return self._base_done + (self.real_calls if self._record_entries else 0)

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        try:
            return cast("LlmResult[T]", self._call(cast("CallRequest[object]", request)))
        except _Escape:
            raise
        except Exception as err:
            if type(err) in SETUP_ERRORS:
                raise _Escape(err) from None  # (d) — 칸·체크포인트 0
            if soft_deadline_in(err) is None:
                raise
            self._last_checkpoint()
            raise _Escape(err) from None

    def _call(self, request: CallRequest[object]) -> LlmResult[object]:
        key = call_key(request)
        queue = self._queues.get(key)
        while queue and queue[0].kind == "budget_exceeded":
            queue.popleft()  # (f) 되감은 상한 칸은 버리고 다시 부른다
        if queue:
            entry = queue.popleft()
            self.replayed += 1
            if monotonic() - self._last >= CHECKPOINT_EVERY_S:
                self.flush(force=True)  # 되감기만으로 20s — done 그대로, 실행기의 마감 확인용
            return result_of(entry)
        got = self.inner.call(request)
        rejected = provider_rejected(got)
        if rejected is not None:
            raise _Escape(rejected)  # (e) — 칸·체크포인트 0
        if isinstance(got, BudgetExceeded):  # (f) — 칸·체크포인트 0, 뒤 부름 0
            raise _Escape(
                Scope3BudgetExceeded(f"실행 비용 상한에 닿았다(상한 {got.limit_usd} USD, 누적 {got.spent_usd} USD)")
            )
        if self._record_entries:
            self.entries.append(entry_of(key, got))
        self.real_calls += 1
        self._unflushed += 1
        if self._unflushed >= BATCH_CALLS or monotonic() - self._last >= CHECKPOINT_EVERY_S:
            self.flush()
        return got

    def _last_checkpoint(self) -> None:
        """소프트 제한으로 나가기 전 체크포인트 한 번(best-effort): 지난 체크포인트 뒤 실제 호출이 있을 때만. 그 안의
        예외(넘침·사건 쪽·RunYield 포함)는 버린다 — 나가는 까닭은 소프트 제한이다."""
        try:
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise  # 사람·프로세스의 멈춤은 삼키지 않는다(가지 리뷰 LOW 7)
        except BaseException as err:  # Exception·_Escape·실행기의 양보(RunYield — runs 를 import 하지 않는다)
            logger.info("scope3_journal_last_checkpoint_dropped error=%s", type(err).__name__)

    def partial(self) -> dict[str, object]:
        return {**self._head, "done": self.done, "journal": [e.to_json() for e in self.entries]}

    def journal(self) -> list[dict[str, object]]:
        """이 단계의 칸(단계 data 로 낼 것). 넘치면 JournalTooLarge."""
        out = [e.to_json() for e in self.entries]
        size = serialized_size({"journal": out})
        if size > PARTIAL_MAX_BYTES:
            logger.warning("scope3_journal_too_large bytes=%s limit=%s", size, PARTIAL_MAX_BYTES)
            raise JournalTooLarge(f"호출 일지 {size}바이트가 상한 {PARTIAL_MAX_BYTES}바이트를 넘는다")
        return out

    def flush(self, *, force: bool = False) -> None:
        """체크포인트 하나(force 가 아니면 지난 체크포인트 뒤 실제 호출이 없을 때 0). 넘침·체크포인트의 Exception 은
        엔진 밖으로 빼낸다(머리말)."""
        if not self._unflushed and not force:
            return
        partial = self.partial()
        size = serialized_size(partial)
        if size > PARTIAL_MAX_BYTES:
            logger.warning("scope3_journal_too_large bytes=%s limit=%s done=%s", size, PARTIAL_MAX_BYTES, self.done)
            raise _Escape(JournalTooLarge(f"호출 일지 {size}바이트가 상한 {PARTIAL_MAX_BYTES}바이트를 넘는다"))
        try:
            self._checkpoint(partial, done=self.done, total=max(self._estimate, self.done))
        except Exception as err:
            raise _Escape(err) from None
        self._unflushed = 0
        self._last = monotonic()
