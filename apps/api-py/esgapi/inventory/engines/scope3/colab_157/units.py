"""무게 단위 → kg 환산과 AI 배수 — 코랩 `convert_to_base_unit`(`:3997`, base_type="weight")·`normalize_unit`(`:3992`)·
`_ai_unit_conversion_factor`(`:3809`). C5(폐기물 처리량)가 쓴다.

- 규칙표 `WEIGHT_TO_KG`(`:3683`)에 없는 단위는 AI 에게 배수를 묻는다: JSON 프롬프트(`_call_claude_json`, 최대 셋) →
  실패면 단순 프롬프트(`_call_claude_text(retries=2)`, 글에서 첫 숫자) → 그래도 없으면 None(1:1 통과, 판단근거 `none`).
- 코랩의 `@lru_cache` 는 None 도 기억한다(실패도 캐시). 여기는 실행 하나의 `UnitFactorCache` — 열쇠는 코랩 인자
  그대로 `(unit_raw, base_unit, context)`, 값은 None 까지. 예외(답이 dict 가 아닌 JSON)는 lru_cache 처럼 기억하지 않고
  밖으로 낸다(코랩은 그 시트가 `[error]`).
- 빈 단위 버릇(코랩 C5 `_safe_text(row.get("단위") or "kg")` — 열이 있고 칸이 비면 "")은 부르는 쪽(waste.py) 몫이고,
  여기서 ""는 규칙표 밖이라 AI 를 부른다(`unit_raw=""`).
"""

import re
from dataclasses import dataclass, field
from typing import Final, Literal

from esgapi.inventory.engines.scope3.colab_157.constants import WEIGHT_TO_KG
from esgapi.inventory.engines.scope3.colab_157.llm import (
    LlmContext,
    call_claude_json,
    call_claude_text,
    json_get,
)
from esgapi.inventory.engines.scope3.colab_157.purchase import normalize_unit, to_float

UNIT_FACTOR_PROMPT: Final = "inventory/scope3-colab-unit-factor@1"
UNIT_FACTOR_SIMPLE_PROMPT: Final = "inventory/scope3-colab-unit-factor-simple@1"

UnitVia = Literal["rule", "ai", "none"]


@dataclass
class UnitFactorCache:
    """코랩 `_ai_unit_conversion_factor` 의 lru_cache 자리(실행 하나). 실패(None)도 기억한다."""

    factors: dict[tuple[str, str, str], float | None] = field(default_factory=dict[tuple[str, str, str], float | None])


@dataclass(frozen=True)
class UnitConversion:
    """코랩 `convert_to_base_unit` 의 (환산값, 기준단위, 환산비율, 원본단위, 판단근거)."""

    value: float | None
    unit: str
    ratio: float
    unit_raw: str
    via: UnitVia


def _ask_unit_factor(context: LlmContext, unit_raw: str, base_unit: str, hint: str) -> float | None:
    """코랩 `_ai_unit_conversion_factor`(`:3809-3842`) 본문(캐시 밖)."""
    variables = {
        "unit_raw": unit_raw,
        "base_unit": base_unit,
        "context_line": f"맥락: {hint}" if hint else "",
    }
    parsed = call_claude_json(context, UNIT_FACTOR_PROMPT, variables, 80)
    factor = to_float(json_get(parsed, "factor")) if parsed else None
    if factor is not None and factor > 0:
        return factor

    simple = {"unit_raw": unit_raw, "base_unit": base_unit, "context_part": f"(맥락: {hint}) " if hint else ""}
    text = call_claude_text(context, UNIT_FACTOR_SIMPLE_PROMPT, simple, 30, 2)
    if text:
        m = re.search(r"[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?", text.replace(",", ""))
        if m:
            f2 = to_float(m.group())
            if f2 is not None and f2 > 0:
                return f2
    return None


def ai_unit_conversion_factor(
    context: LlmContext, cache: UnitFactorCache, unit_raw: str, base_unit: str, hint: str = ""
) -> float | None:
    """lru_cache 꼴: 같은 인자면 한 번만 부른다(None 도 기억)."""
    key = (unit_raw, base_unit, hint)
    if key in cache.factors:
        return cache.factors[key]
    factor = _ask_unit_factor(context, unit_raw, base_unit, hint)
    cache.factors[key] = factor
    return factor


def convert_weight_to_kg(
    context: LlmContext, cache: UnitFactorCache, value: float | None, unit_raw: str
) -> UnitConversion:
    """코랩 `convert_to_base_unit(value, unit_raw, "weight")`(`:3997-4037`)."""
    if value is None:
        return UnitConversion(None, unit_raw, 1.0, unit_raw, "none")
    u = normalize_unit(unit_raw or "")
    ratio = WEIGHT_TO_KG.get(u)
    if ratio is not None:
        return UnitConversion(value * ratio, "kg", ratio, unit_raw, "rule")
    ai_ratio = ai_unit_conversion_factor(context, cache, unit_raw, "kg")
    if ai_ratio is not None:
        return UnitConversion(value * ai_ratio, "kg", ai_ratio, unit_raw, "ai")
    return UnitConversion(value, unit_raw, 1.0, unit_raw, "none")
