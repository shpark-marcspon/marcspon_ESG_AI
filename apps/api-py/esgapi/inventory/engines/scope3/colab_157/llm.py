"""코랩의 생성 모델 부르기(셀 7 `:192-270`, 셀 20 `safe_json_loads` `:2695`)의 **글 해석 몫**과 부름 한 번의 갈래.

코랩은 `client.messages.create` 를 바로 부르고 실패를 `except` 로 받는다. 우리는 `core.llm` 의 `LlmClient`(포트
`LlmGateway`)를 부르고, 그 결과 갈래를 코랩이 본 꼴로 내린다:
- `Success` → 응답 글자(코랩 `_extract_response_text(res)` — 첫 텍스트 블록).
- `CutOff`(출력 상한) → 잘린 글자. 코랩도 `max_tokens` 에 걸린 답을 예외 없이 받는다.
- `Refused` → 그 글자. 코랩도 거절을 예외 없이 받는다(텍스트 블록이 없으면 빈 글자).
- 그 밖(`ProviderFailed`·`TimedOut`·`BudgetExceeded`·`SchemaMismatch`) → `LlmFailed`(코랩의 `except Exception` 자리).
재시도·대기는 `core.llm` 이 한다(코랩 `_call_claude_text` 의 `time.sleep` 재시도 — 「코랩과 다른 자리」).
"""

import contextlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, Literal, cast

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.types import LlmResult, Tags
from esgapi.inventory.engines.scope3.colab_157.ports import LlmGateway


@dataclass(frozen=True)
class LlmText:
    text: str
    via: Literal["success", "truncated", "refusal"]
    kind: Literal["text"] = "text"


@dataclass(frozen=True)
class LlmFailed:
    """코랩에서 예외가 났을 자리. `reason` 은 core.llm 결과의 kind."""

    reason: str
    kind: Literal["failed"] = "failed"


type LlmOutcome = LlmText | LlmFailed


@dataclass
class LlmCalls:
    """실행 하나의 부름 기록: 프롬프트 id → 갈래별 수. 비용은 core.llm 의 기록(log)이 갖는다."""

    by_prompt: dict[str, dict[str, int]] = field(default_factory=dict[str, dict[str, int]])

    def record(self, prompt: str, outcome: LlmOutcome) -> None:
        slot = self.by_prompt.setdefault(prompt, {})
        key = outcome.via if isinstance(outcome, LlmText) else f"failed:{outcome.reason}"
        slot[key] = slot.get(key, 0) + 1


@dataclass(frozen=True)
class LlmContext:
    gateway: LlmGateway
    route: str
    tags: Tags
    calls: LlmCalls
    # 넓은 except 가 다시 던질지의 판별(S3L1, MARC-ISSUE-414) — 흐름이 core 의 soft_deadline_in 으로 짓는다. None = BASE
    reraise: Callable[[BaseException], bool] | None = None


def reraises(context: LlmContext, error: BaseException) -> bool:
    """포트 길을 감싼 넓은 except 자리의 판별: 참이면 그 자리는 삼키지 않고 다시 던진다(Celery soft limit)."""
    return context.reraise is not None and context.reraise(error)


def outcome_of(result: LlmResult[str]) -> LlmOutcome:
    match result.kind:
        case "success":
            return LlmText(result.text, "success")
        case "truncated":
            return LlmText(result.partial_text, "truncated")
        case "refusal":
            return LlmText(result.text, "refusal")
        case _:
            return LlmFailed(result.kind)


def call_text(context: LlmContext, prompt: str, variables: dict[str, str], max_output_tokens: int) -> LlmOutcome:
    """글자로 받는 부름 한 번(schema 없음 — `CallRequest` 는 글자 그대로 돌려준다)."""
    request = CallRequest[str](
        prompt=prompt,
        route=context.route,
        tags=context.tags,
        vars=variables,
        max_output_tokens=max_output_tokens,
    )
    outcome = outcome_of(context.gateway.call(request))
    context.calls.record(prompt, outcome)
    return outcome


def safe_json_loads(text: str) -> object:
    """코랩 `:2695-2700` 그대로: 코드 울타리를 걷고 `json.loads`. 못 읽으면 `json.JSONDecodeError`."""
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def extract_json_object(text: str | None) -> object:
    """코랩 `_extract_json_object`(`:234-248`) 그대로: 통째로 못 읽으면 첫 `{...}` 만 다시. 실패는 None.

    C1·C2 길은 부르지 않는다(단위 환산 등 S3C-b·c 의 `_call_claude_json` 이 쓴다). 글 해석 몫이라 함께 옮겼다.
    """
    if not text:
        return None
    with contextlib.suppress(Exception):  # 코랩 `except Exception: pass`
        return safe_json_loads(text)
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return safe_json_loads(match.group())
        except Exception:  # 코랩 `except Exception: return None`
            return None
    return None


# ── S3C-b1: 코랩 `_call_claude_text`(`:213`)·`_call_claude_json`(`:251`)의 재시도 꼴 ──
# 전송 재시도·대기는 core.llm 이 한다(위). 여기는 코랩이 **글을 보고** 다시 부르는 몫만 옮긴다: 빈 글이면 다시,
# JSON 을 못 읽으면 user 글 끝에 덧붙임을 달아 다시. 코랩의 `time.sleep` 은 옮기지 않았다(「코랩과 다른 자리」).
# JSON 프롬프트 파일은 system 구획(`:259` 글자 그대로)과 user 끝의 `{{json_retry}}` 를 둔다 — 첫 부름은 빈 글,
# 2·3번째는 `JSON_RETRY_SUFFIX`(`:261`).

JSON_RETRY_SUFFIX: Final = "\n\n반드시 JSON 객체 하나만 출력하라. 다른 설명/문장은 절대 포함하지 마라."  # 읽기판 :261
JSON_RETRY_VARIABLE: Final = "json_retry"


def call_claude_text(
    context: LlmContext, prompt: str, variables: dict[str, str], max_output_tokens: int, retries: int
) -> str | None:
    """코랩 `_call_claude_text`(`:213-231`): 글을 strip 해 비지 않으면 돌려주고, 빈 글·실패면 `retries` 번까지 다시."""
    for _ in range(retries):
        outcome = call_text(context, prompt, variables, max_output_tokens)
        if isinstance(outcome, LlmText):
            text = outcome.text.strip()
            if text:
                return text
    return None


def call_claude_json(
    context: LlmContext, prompt: str, variables: dict[str, str], max_output_tokens: int, retries: int = 3
) -> object:
    """코랩 `_call_claude_json`(`:251-269`): 부름마다 `_call_claude_text(retries=1)`, 못 읽으면 덧붙임을 달아 다시.

    돌려주는 값은 `extract_json_object` 의 것 그대로(dict 가 아닐 수도 있다 — 코랩은 부르는 쪽이 `.get` 한다).
    """
    for attempt in range(retries):
        suffix = "" if attempt == 0 else JSON_RETRY_SUFFIX
        text = call_claude_text(context, prompt, {**variables, JSON_RETRY_VARIABLE: suffix}, max_output_tokens, 1)
        parsed = extract_json_object(text)
        if parsed is not None:
            return parsed
    return None


def json_get(parsed: object, key: str) -> object:
    """코랩 `parsed.get(key)` 의 자리: dict 가 아니면 코랩처럼 AttributeError(부르는 쪽 함수 밖으로 나간다)."""
    if isinstance(parsed, dict):
        return cast("dict[str, object]", parsed).get(key)
    raise AttributeError(f"'{type(parsed).__name__}' object has no attribute 'get'")
