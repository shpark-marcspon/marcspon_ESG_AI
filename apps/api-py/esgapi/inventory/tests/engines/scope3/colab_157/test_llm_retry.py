"""S6 코랩 재시도 꼴: 공급사에 가는 글자(system·user 첫/2/3번째)가 코랩 f-문자열과 같은가, 빈 글·실패의 재시도 수.

아래 `colab_*` 는 읽기판의 f-문자열을 **글자 그대로** 옮긴 것이다(`_ai_unit_conversion_factor`
`:3817-3825`·`:3833-3835`, `_ai_normalize_travel_mode` `:8525-8528`, `_call_claude_json` 의 system `:259`·덧붙임
`:261`). 프롬프트 파일·변수 짓기가 코랩과 어긋나면 여기서 빨개진다. 따옴표 꼴만 ruff format 이 바꿨다(글자는 같다).
"""

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderError, ProviderRequest
from esgapi.inventory.engines.scope3.colab_157.llm import call_claude_json, call_claude_text
from esgapi.inventory.engines.scope3.colab_157.travel_mode import (
    TRAVEL_MODE_PROMPT,
    TravelModeCache,
    ai_normalize_travel_mode,
)
from esgapi.inventory.engines.scope3.colab_157.units import (
    UNIT_FACTOR_PROMPT,
    UNIT_FACTOR_SIMPLE_PROMPT,
    UnitFactorCache,
    ai_unit_conversion_factor,
)
from esgapi.inventory.tests.engines.scope3.colab_157.support import llm_context
from esgapi.inventory.tests.scope3_llm_support import user_text


# ── 코랩 글자 그대로(읽기판) ──
def colab_sys_prompt() -> str:
    return "Return only valid JSON, with no other text before or after it."  # :259


def colab_retry(prompt: str) -> str:
    return prompt + "\n\n반드시 JSON 객체 하나만 출력하라. 다른 설명/문장은 절대 포함하지 마라."  # :261


def colab_unit_prompt(unit_raw: str, base_unit: str, context: str = "") -> str:
    # :3817-3825
    return f"""단위 환산 배수를 추정하라.
입력 단위: {unit_raw}
목표(기준) 단위: {base_unit}
{f"맥락: {context}" if context else ""}

"1 {unit_raw}"가 "{base_unit}" 몇 개에 해당하는지 배수(factor)를 계산하라.
화학/물리적으로 정확한 값을 모르면, 온실가스 배출량 산정에 통상적으로 쓰이는
표준 환산값(예: 표준상태 기준 밀도, 발열량 등)을 근거로 최선의 추정값을 제시하라.
JSON으로만 답하라: {{"factor": <숫자>}}"""


def colab_simple_prompt(unit_raw: str, base_unit: str, context: str = "") -> str:
    # :3833-3835 (마지막 조각은 코랩도 자리표시 없는 f-문자열이다)
    return (
        f'"1 {unit_raw}"는 "{base_unit}" 단위로 몇인가? '
        f"{f'(맥락: {context}) ' if context else ''}"
        f"설명 없이 숫자(배수)만 답하라."
    )


def colab_travel_prompt(text: str) -> str:
    # :8525-8528
    return f"""다음 출장/통근 이동수단을 아래 6개 중 하나로 변환하라.
입력값: {text}
가능한 값: flight, train, subway, taxi, bus, car
JSON으로만 답하라: {{"mode": "<value>"}}"""


def system_text(request: ProviderRequest) -> str:
    return "\n".join(segment.text for segment in request.system)


def failed() -> ProviderError:
    return ProviderError(status=None, retryable=False, message="가상: 실패")


def sent(mock: MockProvider) -> list[tuple[str, str, int]]:
    return [(system_text(c), user_text(c), c.max_output_tokens) for c in mock.calls]


def test_unit_factor_texts_match_the_colab_for_every_attempt() -> None:
    """JSON 셋(80) 모두 실패 → 단순 둘(30, system 없음) 모두 실패 → None."""
    mock = MockProvider()
    got = ai_unit_conversion_factor(llm_context(mock), UnitFactorCache(), "가상단위", "kg")
    assert got is None
    first = colab_unit_prompt("가상단위", "kg")
    simple = colab_simple_prompt("가상단위", "kg")
    sys = colab_sys_prompt()
    assert sent(mock) == [
        (sys, first, 80),
        (sys, colab_retry(first), 80),
        (sys, colab_retry(first), 80),
        ("", simple, 30),
        ("", simple, 30),
    ]


def test_unit_factor_texts_with_a_context_match_the_colab() -> None:
    mock = MockProvider()
    ai_unit_conversion_factor(llm_context(mock), UnitFactorCache(), "가상단위", "kg", "가상 맥락")
    first = colab_unit_prompt("가상단위", "kg", "가상 맥락")
    assert [u for _, u, _ in sent(mock)] == [
        first,
        colab_retry(first),
        colab_retry(first),
        colab_simple_prompt("가상단위", "kg", "가상 맥락"),
        colab_simple_prompt("가상단위", "kg", "가상 맥락"),
    ]


def test_travel_mode_texts_match_the_colab() -> None:
    mock = MockProvider()
    assert ai_normalize_travel_mode(llm_context(mock), TravelModeCache(), "가상이동") is None
    first = colab_travel_prompt("가상이동")
    sys = colab_sys_prompt()
    assert sent(mock) == [(sys, first, 40), (sys, colab_retry(first), 40), (sys, colab_retry(first), 40)]


def test_json_retry_stops_at_the_first_parsed_answer() -> None:
    """첫 답은 JSON 이 아님 → 덧붙임을 단 2번째 답이 읽힌다(셋째는 부르지 않는다)."""
    mock = MockProvider().enqueue_text("가상 설명 글").enqueue_text('{"factor": 9.5}')
    assert ai_unit_conversion_factor(llm_context(mock), UnitFactorCache(), "가상단위", "kg") == 9.5
    first = colab_unit_prompt("가상단위", "kg")
    assert [user_text(c) for c in mock.calls] == [first, colab_retry(first)]


def test_empty_text_is_retried_by_call_claude_text() -> None:
    """코랩 `_call_claude_text`: strip 해 빈 글이면 다시(실패도 다시), `retries` 번까지."""
    mock = MockProvider().enqueue_text("").enqueue(failed()).enqueue_text("  9.5 \n")
    got = call_claude_text(llm_context(mock), UNIT_FACTOR_SIMPLE_PROMPT, simple_vars(), 30, 3)
    assert (got, len(mock.calls)) == ("9.5", 3)

    mock = MockProvider().enqueue_text("").enqueue_text(" ").enqueue_text("9.5")
    assert call_claude_text(llm_context(mock), UNIT_FACTOR_SIMPLE_PROMPT, simple_vars(), 30, 2) is None
    assert mock.pending == 1  # 셋째 답은 부르지 않았다


def test_the_simple_prompt_is_called_twice_when_both_are_empty() -> None:
    mock = MockProvider().enqueue(failed()).enqueue(failed()).enqueue(failed()).enqueue_text("").enqueue_text("")
    assert ai_unit_conversion_factor(llm_context(mock), UnitFactorCache(), "가상단위", "kg") is None
    assert [c.max_output_tokens for c in mock.calls] == [80, 80, 80, 30, 30]


def test_call_claude_json_sends_an_empty_suffix_first() -> None:
    """`{{json_retry}}` 변수: 첫 부름은 빈 글, 다음부터 덧붙임. 세 번 다 못 읽으면 None."""
    mock = MockProvider().enqueue_text("가상").enqueue_text("가상").enqueue_text("가상")
    variables = {"text": "가상이동"}
    assert call_claude_json(llm_context(mock), TRAVEL_MODE_PROMPT, variables, 40) is None
    first = colab_travel_prompt("가상이동")
    assert [user_text(c) for c in mock.calls] == [first, colab_retry(first), colab_retry(first)]


def test_json_prompt_ids_are_the_files() -> None:
    assert (UNIT_FACTOR_PROMPT, UNIT_FACTOR_SIMPLE_PROMPT, TRAVEL_MODE_PROMPT) == (
        "inventory/scope3-colab-unit-factor@1",
        "inventory/scope3-colab-unit-factor-simple@1",
        "inventory/scope3-colab-travel-mode@1",
    )


def simple_vars() -> dict[str, str]:
    return {"unit_raw": "가상단위", "base_unit": "kg", "context_part": ""}
