"""출장·통근 이동수단 정규화 — 코랩 `normalize_travel_mode`(`:8534`, 마지막 판) → `detect_travel_mode_rule`(`:1384`)
→ AI `_ai_normalize_travel_mode`(`:8523`). C6-2 의 「정규화이동수단」 이 쓰고, S3C-b2(C6-1·C7)가 다시 쓴다.

차례(코랩 그대로): ① 정규화 글(`_fix_norm`)에 앞 표(`TRAVEL_MODE_FIX_KEYWORDS`)의 낱말 → `rule_fix`
② 원문의 `detect_travel_mode_rule` 이 `unknown` 이 아님 → `rule` ③ 정규화 글이 비지 않으면 AI → `ai`
④ 나머지 → `"car"`(`default_car` — AI 실패도 여기).
AI 의 `@lru_cache` 는 None 도 기억한다 — 실행 하나의 `TravelModeCache`(열쇠 = 정규화 글, 값 None 까지).
"""

import re
from dataclasses import dataclass, field
from typing import Final, Literal

from esgapi.inventory.engines.scope3.colab_157.constants import TRAVEL_MODE_FIX_KEYWORDS
from esgapi.inventory.engines.scope3.colab_157.llm import LlmContext, call_claude_json, json_get
from esgapi.inventory.engines.scope3.colab_157.purchase import fix_norm, fix_text

TRAVEL_MODE_PROMPT: Final = "inventory/scope3-colab-travel-mode@1"
ModeVia = Literal["rule_fix", "rule", "ai", "default_car"]
_AI_MODES: Final = {"flight", "train", "subway", "taxi", "bus", "car"}


@dataclass
class TravelModeCache:
    """코랩 `_ai_normalize_travel_mode` 의 lru_cache 자리(실행 하나). 실패(None)도 기억한다."""

    modes: dict[str, str | None] = field(default_factory=dict[str, str | None])


@dataclass(frozen=True)
class TravelMode:
    value: str
    via: ModeVia


def safe_text_travel(x: object) -> str:
    """코랩 `_safe_text_travel`(`:1330`)."""
    s = fix_text(x)
    return "" if s.lower() in ["nan", "none", "null"] else s


def _has(text: str, keywords: list[str]) -> bool:
    return any(k in text for k in keywords)


_FLIGHT: Final = ["항공", "flight", "비행"]


def detect_travel_mode_rule(mode_text: object) -> str:
    """코랩 `detect_travel_mode_rule`(`:1384-1485`) 그대로(낱말·차례)."""
    text = safe_text_travel(mode_text).lower()
    if not text:
        return "unknown"
    text = re.sub(r"[\(\)\[\]\/,_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if _has(text, ["coach", "코치", "장거리버스"]):
        return "coach"
    if _has(text, ["bus", "shuttle", "버스", "고속버스", "시외버스", "전세버스", "공항버스", "셔틀", "광역버스"]):
        return "bus"
    if _has(text, ["퍼스트", "first class", "first"]) and _has(text, _FLIGHT):
        if _has(text, ["장거리", "long", "long-haul", "long haul"]):
            return "flight_long_first"
        return "flight_first"
    if _has(text, ["비즈니스", "business class"]) and _has(text, _FLIGHT):
        if _has(text, ["장거리", "long", "long-haul"]):
            return "flight_long_biz"
        if _has(text, ["단거리", "short", "short-haul", "유럽"]):
            return "flight_short_biz"
        return "flight_biz"
    if _has(text, ["프리미엄이코노미", "premium economy"]) and _has(text, ["장거리", "long"]):
        return "flight_long_prem"
    if _has(text, ["장거리", "long haul", "long-haul"]) and _has(text, _FLIGHT):
        return "flight_long"
    if _has(text, ["단거리", "short haul", "short-haul", "유럽"]) and _has(text, _FLIGHT):
        return "flight_short"
    if _has(text, ["국내선", "국내항공", "domestic flight"]):
        return "flight_dom"
    if _has(
        text,
        [
            "flight", "air", "airplane", "plane", "항공", "비행기", "항공편", "국제선",
            "대한항공", "아시아나", "제주항공", "진에어", "티웨이", "ke", "oz", "lj", "tw", "공항",
        ],
    ):  # fmt: skip
        return "flight"
    if _has(text, ["ktx", "srt", "train", "rail", "railway", "기차", "철도", "열차", "무궁화", "새마을"]):
        return "train"
    if _has(text, ["경전철", "트램", "tram", "light rail"]):
        return "tram"
    if _has(text, ["지하철", "전철", "subway", "metro"]):
        return "subway"
    if _has(text, ["hybrid", "하이브리드", "hev", "phev", "플러그인하이브리드"]):
        return "car_hybrid"
    if _has(
        text,
        [
            "전기차",
            "전기자동차",
            "electric car",
            "electric vehicle",
            "ev",
            "테슬라",
            "아이오닉",
            "ev6",
            "bev",
            "제네시스ev",
        ],
    ):
        return "car_ev"
    if _has(text, ["소형차", "경차", "small car", "minicar"]):
        return "car_small"
    if _has(text, ["중형차", "medium car", "중형"]):
        return "car_medium"
    if _has(text, ["대형차", "large car", "대형suv", "대형"]):
        return "car_large"
    if _has(text, ["car", "auto", "vehicle", "렌터카", "렌트카", "자가용", "승용차", "자동차", "차량"]):
        return "car"
    if _has(text, ["스쿠터", "경량오토바이", "소형오토바이", "moped", "scooter", "small motorcycle"]):
        return "motorcycle_small"
    if _has(text, ["대형오토바이", "리터바이크", "large motorcycle", "할리", "harley"]):
        return "motorcycle_large"
    if _has(text, ["오토바이", "motorcycle", "motorbike"]):
        return "motorcycle"
    if _has(text, ["taxi", "cab", "카카오t", "카카오택시", "택시"]):
        return "taxi"
    if _has(text, ["ferry foot", "foot passenger", "도보페리"]):
        return "ferry_foot"
    if _has(text, ["ferry", "페리", "선박", "배"]):
        return "ferry"
    if _has(text, ["도보", "walk", "walking"]):
        return "walk"
    if _has(text, ["자전거", "따릉이", "bike", "bicycle", "cycling"]):
        return "bicycle"
    return "unknown"


def ai_normalize_travel_mode(context: LlmContext, cache: TravelModeCache, text: str) -> str | None:
    """코랩 `_ai_normalize_travel_mode`(`:8523-8532`) + lru_cache. dict 아닌 JSON 답은 AttributeError(캐시 안 함)."""
    if text in cache.modes:
        return cache.modes[text]
    parsed = call_claude_json(context, TRAVEL_MODE_PROMPT, {"text": text}, 40)
    mode = fix_norm(json_get(parsed, "mode")) if parsed else ""
    found = mode if mode in _AI_MODES else None
    cache.modes[text] = found
    return found


def normalize_travel_mode(context: LlmContext, cache: TravelModeCache, mode: object) -> TravelMode:
    """코랩 `normalize_travel_mode`(`:8534-8566`)."""
    s = fix_norm(mode)
    for keywords, value in TRAVEL_MODE_FIX_KEYWORDS:
        if _has(s, keywords):
            return TravelMode(value, "rule_fix")
    try:
        rule_mode = detect_travel_mode_rule(mode)
    except Exception:  # 코랩 `except Exception: rule_mode = "unknown"`
        rule_mode = "unknown"
    if rule_mode and rule_mode != "unknown":
        return TravelMode(rule_mode, "rule")
    if s:
        ai_mode = ai_normalize_travel_mode(context, cache, s)
        if ai_mode:
            return TravelMode(ai_mode, "ai")
    return TravelMode("car", "default_car")
