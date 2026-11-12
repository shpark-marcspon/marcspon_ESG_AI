"""중대성평가 IRO 코랩 1부의 실행 상수(셀 8 러너·셀 11 공통 입력·셀 17·20·22 의 호출). 부르는 곳은 흐름(IR1b)이다.

코랩 값 그대로다. 실제로 부르는 모델·사용량은 실행기의 기록이 진실이다.
"""

from typing import Final

MODEL: Final = "gpt-4o"
"""셀 11 model(R/364)."""
TEMPERATURE: Final = 0.1
"""셀 8 run_web_search_prompt 의 temperature(R/106)."""
SEARCH_CONTEXT_SIZE: Final = "low"
"""셀 8 web_search 도구의 search_context_size(R/114). user_location 은 approximate·입력의 userLocation."""
POLL_TRIES: Final = 12
"""셀 8 폴링 횟수(R/99)."""
POLL_SLEEP_SECONDS: Final = 0.6
"""셀 8 폴링 간격(R/100)."""
RETRY_ON_INCOMPLETE: Final = 1
"""셀 8 incomplete 재시도 횟수(R/101)."""
CACHE_KEYS: Final = {
    "regulation": "reg_updates_v1",
    "keywords": "keyword_v1",
    "controversy": "non_fin_controversies_v1",
}
"""prompt_cache_key(셀 17 R/788 · 셀 20 R/874 · 셀 22 R/1087). 코랩은 TypeError 면 빼고 다시 만든다(IR1b)."""
UTM_SUFFIXES: Final = ("?utm_source=openai", "&utm_source=openai")
"""답 글에서 지우는 두 글(셀 17 R/795-796 · 셀 22 R/1096-1097). 이 둘뿐이다(W7)."""

# ── 2부(셀 46·50·55, 밴드 IR2a) ──
MODEL_PART2: Final = "gpt-4.1"
"""셀 46·50 model(R/2144·R/2417 — 셀 55 는 「위랑 동일한 값」)."""
PART2_SEARCH_CONTEXT_SIZE: Final = "low"
"""셀 8 subtopic_impactdef_prompt 의 web_search search_context_size(R/189). latest_event_mode 가 참일 때만 싣는다 —
user_location·tool_choice 는 싣지 않는다(코랩대로)."""
