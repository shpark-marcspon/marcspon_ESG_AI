"""translate 단계의 호출 일지: 엔진 포트(`LlmGateway`)를 감싸 호출마다 답을 적고, 때때로 체크포인트로 남긴다.
다음 시도는 그 일지를 차례대로 되감아 공급사를 다시 부르지 않고 같은 답을 엔진에 준다(MARC-ISSUE-268 의 1, 밴드 TRR1).

엔진(engines/colab_158)은 0줄이다(MARC-ENT-442 — 코랩 동작 그대로): 엔진은 호출을 차례대로 부르므로 같은 입력·같은
답이면 같은 출력이다. 그래서 일지는 「n 번째 호출의 열쇠와 답」의 차례 목록이면 된다.

    열쇠        sha256(json.dumps([site, role, system, user, max_tokens, route], ensure_ascii=False)) — JSON 배열(이어
                붙이기가 아니다. 칸 경계가 글에 섞이지 않는다)
    칸 하나     {"k": 열쇠, "ok": 참/거짓, "boundUsd": 그 요청의 dry_run 위끝, "text"·"ending"(ok) | "error"(실패)}
                ok = 성공·잘림·거절(다리가 글로 돌려준 것). 실패(LlmCallFailed)도 적는다 — 재시작 유무와 무관하게 같은
                바이트가 되려면 실패도 같은 자리에서 같은 메시지로 다시 나야 한다
    되감기      일지의 다음 칸 열쇠가 이번 요청과 같으면 공급사 0 — 적은 답을 돌려주거나 LlmCallFailed(같은 메시지)를
                다시 던진다. 다르면 그 칸부터 뒤를 버리고 실제로 부른다(경고 한 줄 — 키·글 0)
    partial     {"v": 1, "sourceSha256", "calls"(계획 호출 수), "done", "journal": [칸…]}. sourceSha256·v·calls 가
                이번 실행과 다르거나 꼴이 틀리면 partial 전체를 무시한다(경고 한 줄)
    done        시도를 넘어 줄지 않는다: 앞 partial 의 done + 이 시도의 실제 호출 수(되감은 칸은 세지 않음). 일지를
                버려도 done 이 줄지 않아 실행기의 진행 판정(runs/service/services/runs.py step_progress)이 거짓이 되지
                않는다. total = max(계획 호출 수, done)
    체크포인트  마지막 체크포인트에서 CHECKPOINT_EVERY_S 가 지난 뒤 첫 실제 호출 끝에. 직렬화가 PARTIAL_MAX_BYTES 를
                넘으면 그 실행을 바로 실패로 끝낸다(JournalTooLarge — 건너뛰면 협조 마감·진행 기록이 사라져 같은
                자리에서 되풀이해 돈을 버린다. 경고 한 줄)

엔진 밖으로 빼내는 예외(엔진의 `except Exception` 이 삼키면 남은 호출이 돈을 쓴다 — 보고 ★②):
    (a) 호출 안의 소프트 시간 제한: core `soft_deadline_in` 이 값이면(celery·billiard import 0)
    (b) 체크포인트가 던지는 Exception 전부(왕복 실패·사건 쪽 예외·쓰기 실패) — RunYield(BaseException)는 그대로 지나간다
    (c) JournalTooLarge
    (d) OverBudget: 이 시도의 허용액(실행 중 상한 min(max_usd, prepare 위끝) − 이 실행의 지출)에서 **실제** 공급사
        호출마다 머리 여유(그 요청의 dry_run 위끝 × max(GUARD_FACTOR, 1 + 공급사 재시도 수) — tools/run_bound.py,
        감독 결정 D2)를 미리 빼고(되감은 칸은 0), 모자라면 부르지 않고 OverBudget — translate 가 결과 over_budget
        으로 끝낸다. 부른 뒤 되돌린다(밴드 TRE1 G2): 실비를 **알면** 허용액 += 머리 여유 − 실비, **모르면**(사용량
        없는 실패 시도가 있음 — core 가 그 몫을 0 으로 센다) 허용액 += 머리 여유 − (아는 몫 + 모름 시도 수 × 위끝)
        (공급사 재시도로 한 호출에 여럿 — 감독 결정 D1), 다리가 결과 없이 던지면(PromptError 등) 되돌림 0. 성공·
        잘림·거절·LlmCallFailed 모두 같은 규칙. 깎을 몫이 머리 여유를 넘으면 경고 한 줄(translation_bound_exceeded)
        이고 허용액은 그 몫으로 뺀다. 그래서 「이 실행의 실비 ≤ 상한」을 호출 전 판정이 지킨다 — prepare 위끝은 실측
        비율로 낮춘 어림이라 셈이 아니라 이 판정이 바닥이다. 일지가 어긋나 다시 부르는 몫·시도 사이 경로가 바뀌어
        계획 위끝이 낮게 잡힌 몫도 이것이 막는다(TRR1 가지 리뷰 M1·M2)
  넷 다 `_Escape(original)`(BaseException)로 감싸 던진다. 소프트 제한은 호출 하나 전체(위끝 어림·답 받기·체크포인트
  직렬화)에서 잡고, 나가기 전에 체크포인트를 한 번 해 본다(best-effort — 그 실패는 버린다). 흐름의 translate 가
  엔진 밖에서 `unescaped` 로 받아 원래 예외를 되던진다(OverBudget 은 결과 over_budget 으로 받는다) → run_flow →
  FlowStepFailed → 실행기 갈래(소프트 제한 = RunDeferred).
다리의 LlmCallFailed 밖 예외(PromptError·LlmConfigError 등)는 일지에 적지 않고 그대로 올린다(TRR1 앞과 같은 길 —
prepare 의 dry_run 이 같은 요청 꼴을 먼저 걸러 실제로는 드묾).
"""

import contextlib
import hashlib
import json
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast

from esgapi.core.llm.errors import soft_deadline_in
from esgapi.translation.engines.colab_158.ports import GatewayText, LlmCallFailed, Role
from esgapi.translation.engines.colab_158.prompts import Site
from esgapi.translation.tools.llm_bridge import LlmBridge

logger = logging.getLogger(__name__)

JOURNAL_VERSION: Final = 1
CHECKPOINT_EVERY_S: Final = 20.0
"""체크포인트 간격(초 — 어림, 잰 값이 아니다): 실행기의 마감 여유 60초(runs/calc/deadline.py)의 1/3. 마감은 체크포인트를
쓸 때만 보이므로 간격이 여유보다 짧아야 협조 마감이 소프트 제한보다 먼저 난다."""
PARTIAL_MAX_BYTES: Final = 8 * 1024 * 1024
"""partial 직렬화 상한: 단계 행 CHECK RUN_STEP_DATA_MAX_OCTETS 16MiB(runs/models.py) 아래 여유 절반. 지어낸 최악 꼴
(쪽 조각 300·A/B·자동수정, 원문 198,491자 — 모의 답 = 국문 글자 × 2.5 영문)이 약 4.2MiB(보고 ★④). 답이 출력
상한까지 길면 넘을 수 있다(이론 위끝 약 84MiB) — 그때는 실패로 끝낸다."""

type Ending = Literal["complete", "truncated", "refused"]
ENDINGS: Final = ("complete", "truncated", "refused")


class OverBudget(Exception):
    """이 시도의 남은 허용액이 다음 실제 호출의 머리 여유보다 작다 — 결과 over_budget(머리말 (d))."""


class JournalTooLarge(Exception):
    """partial 이 PARTIAL_MAX_BYTES 를 넘는다 — 그 실행은 실패한다(머리말)."""


class _Escape(BaseException):
    """엔진 밖으로 빼낼 예외를 싼다. translate 만 받는다(unescaped)."""

    def __init__(self, original: BaseException) -> None:
        super().__init__(type(original).__name__)
        self.original = original


def unescaped[T](call: Callable[[], T]) -> T:
    """엔진을 부르는 자리를 감싼다: 싼 예외를 풀어 원래 예외를 던진다."""
    try:
        return call()
    except _Escape as escape:
        raise escape.original from None


@dataclass(frozen=True, slots=True)
class Entry:
    key: str
    ok: bool
    bound_usd: float
    text: str | None = None
    ending: Ending | None = None
    error: str | None = None

    def to_json(self) -> dict[str, object]:
        if self.ok:
            return {"k": self.key, "ok": True, "boundUsd": self.bound_usd, "text": self.text, "ending": self.ending}
        return {"k": self.key, "ok": False, "boundUsd": self.bound_usd, "error": self.error}


@dataclass(frozen=True, slots=True)
class Resumed:
    """앞 시도가 남긴 일지(받을 수 없으면 빈 것)."""

    entries: tuple[Entry, ...]
    done: int


EMPTY: Final = Resumed(entries=(), done=0)


def call_key(site: str, role: str, system: str, user: str, max_tokens: int, route: str) -> str:
    body = json.dumps([site, role, system, user, max_tokens, route], ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _entry(raw: object) -> Entry | None:
    if not isinstance(raw, Mapping):
        return None
    item = cast("Mapping[str, object]", raw)
    key, ok, bound = item.get("k"), item.get("ok"), item.get("boundUsd")
    if not isinstance(key, str) or not isinstance(ok, bool) or isinstance(bound, bool):
        return None
    if not isinstance(bound, int | float):
        return None
    if ok:
        text, ending = item.get("text"), item.get("ending")
        if not isinstance(text, str) or ending not in ENDINGS:
            return None
        return Entry(key, True, float(bound), text=text, ending=ending)
    error = item.get("error")
    if not isinstance(error, str):
        return None
    return Entry(key, False, float(bound), error=error)


def read_resume(resume: Mapping[str, object] | None, *, source_sha256: str, calls: int) -> Resumed:
    """partial → 일지. 없으면 빈 것, 이번 실행과 맞지 않거나 꼴이 틀리면 경고 한 줄과 빈 일지(머리말 partial) — 저장된
    done 이 꼴에 맞으면 그 값은 살린다(일지를 통째로 버려도 진행 수가 줄지 않게 — 가지 리뷰 L4)."""
    if resume is None:
        return EMPTY
    head = (resume.get("v"), resume.get("sourceSha256"), resume.get("calls"))
    raw_done, journal = resume.get("done"), resume.get("journal")
    valid_done = isinstance(raw_done, int) and not isinstance(raw_done, bool) and raw_done >= 0
    done = cast("int", raw_done) if valid_done else 0
    if head != (JOURNAL_VERSION, source_sha256, calls) or not isinstance(journal, list):
        logger.warning("translation_journal_ignored reason=head")
        return Resumed(entries=(), done=done)
    if not valid_done:
        logger.warning("translation_journal_ignored reason=done")
        return EMPTY
    entries = [_entry(raw) for raw in cast("list[object]", journal)]
    if any(e is None for e in entries):
        logger.warning("translation_journal_ignored reason=entry")
        return Resumed(entries=(), done=done)
    return Resumed(entries=tuple(cast("list[Entry]", entries)), done=done)


def monotonic() -> float:
    """체크포인트 간격을 재는 시계. ★ 이음매다(시험이 바꿔 끼운다 — 부를 때 모듈 속성으로 읽는다)."""
    return time.monotonic()


class JournalGateway:
    """엔진 포트 하나(머리말). inner 는 실제로 부를 다리, checkpoint 는 StepContext.checkpoint 꼴."""

    def __init__(
        self,
        inner: LlmBridge,
        *,
        resume: Resumed,
        source_sha256: str,
        calls: int,
        checkpoint: Callable[..., None],
        allowance_usd: float,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.inner = inner
        self.source_sha256 = source_sha256
        self.calls = calls
        self._checkpoint = checkpoint
        self._clock = clock
        self._replay: Sequence[Entry] | None = resume.entries
        self._base_done = resume.done
        self.entries: list[Entry] = []
        self.real_calls = 0
        self._unflushed = False
        self.allowance_usd = allowance_usd
        """남은 허용액(USD). 실제 호출마다 머리 여유를 미리 빼고 부른 뒤 되돌린다(머리말 (d))."""
        self._last = self._now()

    def _now(self) -> float:
        return monotonic() if self._clock is None else self._clock()

    @property
    def done(self) -> int:
        return self._base_done + self.real_calls

    def complete(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> GatewayText:
        try:
            return self._complete(site, role, system, user, max_tokens)
        except LlmCallFailed:
            raise
        except Exception as err:
            if soft_deadline_in(err) is None:
                raise
            self._last_checkpoint()
            raise _Escape(err) from None

    def _complete(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> GatewayText:
        key = call_key(site, role, system, user, max_tokens, self.inner.route(role))
        replayed = self._replayed(key)
        if replayed is not None:
            return self._give(replayed)
        bound, guard = self.inner.guard_usd(site, role, system, user, max_tokens)
        if guard > self.allowance_usd:
            logger.warning("translation_journal_over_budget done=%s", self.done)
            raise _Escape(OverBudget("다음 호출의 머리 여유가 이 시도의 남은 허용액을 넘는다"))
        self.allowance_usd -= guard
        try:
            got = self.inner.complete(site, role, system, user, max_tokens)
        except LlmCallFailed as failed:
            self._settle(guard, bound)
            self._record(Entry(key, False, bound, error=str(failed)))
            raise
        except BaseException:
            self._settle(guard, bound)  # 다리가 결과 없이 던졌다 — last_cost_usd None 이라 되돌림 0
            raise
        self._settle(guard, bound)
        self._record(Entry(key, True, bound, text=got.text, ending=got.ending))
        return got

    def _settle(self, guard: float, bound: float) -> None:
        """부른 뒤 머리 여유를 되돌린다(머리말 (d)): 앎 = 실비, 모름 = 아는 몫 + 모름 시도 수 × 위끝, 결과 없음 = 0."""
        cost = self.inner.last_cost_usd
        if cost is None:
            return
        spent = cost + self.inner.last_unknown_attempts * bound
        if spent > guard:
            logger.warning("translation_bound_exceeded done=%s", self.done)
        self.allowance_usd += guard - spent

    def _last_checkpoint(self) -> None:
        """소프트 제한으로 나가기 전 체크포인트 한 번(best-effort): 지난 체크포인트 뒤 실제 호출이 있을 때만. 그 안의
        예외(넘침·사건 쪽·RunYield 포함)는 버린다 — 나가는 까닭은 소프트 제한이다."""
        with contextlib.suppress(BaseException):  # 나가는 길의 best-effort
            self.flush()

    def _replayed(self, key: str) -> Entry | None:
        replay = self._replay
        if replay is None:
            return None
        position = len(self.entries)
        if position >= len(replay):
            self._replay = None
            return None
        entry = replay[position]
        if entry.key != key:
            logger.warning("translation_journal_diverged position=%s kept=%s", position, len(replay))
            self._replay = None
            return None
        self.entries.append(entry)
        return entry

    @staticmethod
    def _give(entry: Entry) -> GatewayText:
        if not entry.ok:
            raise LlmCallFailed(entry.error)
        return GatewayText(text=cast("str", entry.text), ending=cast("Ending", entry.ending))

    def _record(self, entry: Entry) -> None:
        self.entries.append(entry)
        self.real_calls += 1
        self._unflushed = True
        if self._now() - self._last >= CHECKPOINT_EVERY_S:
            self.flush()

    def partial(self) -> dict[str, object]:
        return {
            "v": JOURNAL_VERSION,
            "sourceSha256": self.source_sha256,
            "calls": self.calls,
            "done": self.done,
            "journal": [e.to_json() for e in self.entries],
        }

    def flush(self) -> None:
        """체크포인트 하나(지난 체크포인트 뒤 실제 호출이 없으면 0). 넘침·체크포인트의 Exception 은 엔진 밖으로
        빼낸다(머리말)."""
        if not self._unflushed:
            return
        partial = self.partial()
        size = len(json.dumps(partial, ensure_ascii=False).encode("utf-8"))
        if size > PARTIAL_MAX_BYTES:
            logger.warning(
                "translation_journal_too_large bytes=%s limit=%s done=%s", size, PARTIAL_MAX_BYTES, self.done
            )
            raise _Escape(JournalTooLarge(f"호출 일지 {size}바이트가 상한 {PARTIAL_MAX_BYTES}바이트를 넘는다"))
        try:
            self._checkpoint(partial, done=self.done, total=max(self.calls, self.done))
        except Exception as err:
            raise _Escape(err) from None
        self._unflushed = False
        self._last = self._now()
