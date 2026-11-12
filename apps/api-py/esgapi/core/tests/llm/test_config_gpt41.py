"""gpt-4.1 항목(밴드 TL1 `MARC-TICK-180` 의 T5 앞몫): 단가·건당 요금·경로·한도·퇴역일, notes 의 확인일. 순수 층.

수치는 models.json 의 notes 가 인용한 공식 문서 글자에서 온다(2026-10-19 확인). 이 시험은 그 값을 계산으로 고정한다.
"""

from esgapi.core.llm.client import TOOL_MODELS, TOOL_PROVIDERS
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.cost import compute_cost_usd
from esgapi.core.llm.types import Usage

CONFIG = load_config(default_config_sources(synthetic=False))


def usage(inp: int, out: int, read: int = 0, write: int = 0) -> Usage:
    return Usage(input_tokens=inp, output_tokens=out, cache_read_tokens=read, cache_write_tokens=write)


def test_gpt41_prices_match_the_official_table_and_web_search_costs_ten_dollars_per_thousand_calls() -> None:
    model = CONFIG.models["gpt-4.1"]
    price = model.entry.pricing
    # openai_pricing Standard 표 「| gpt-4.1 | $2.00 | $0.50 | - | $8.00 | - | - | - | - |」
    assert compute_cost_usd(usage(1_000_000, 0), price) == 2.0
    assert compute_cost_usd(usage(0, 1_000_000), price) == 8.0
    assert compute_cost_usd(usage(0, 0, 1_000_000), price) == 0.5
    # 캐시 쓰기: openai_caching 「Other earlier models … No additional cache-write charge」 → 입력 단가 2.0
    assert compute_cost_usd(usage(0, 0, 0, 1_000_000), price) == 2.0
    assert price.long_context is None
    # Tools 표 「Web search (all models) | $10.00 / 1k calls」 → 건당 0.01
    hosted = model.hosted_tool_pricing
    assert hosted is not None
    assert hosted.web_search_per_call == 0.01
    assert compute_cost_usd(usage(0, 0), price, 1000, hosted) == 10.0


def test_gpt41_limits_route_retirement_and_check_dates() -> None:
    model = CONFIG.models["gpt-4.1"]
    entry = model.entry
    assert (model.provider, model.api_model_id) == ("openai", "gpt-4.1")
    assert entry.context_window_tokens == 1_047_576
    assert entry.max_output_tokens == 32_768
    assert entry.reasoning_output_reserve_tokens is None
    assert entry.lifecycle.retirement == "January 14, 2027"
    assert "https://developers.openai.com/api/docs/deprecations" in entry.lifecycle.note
    assert CONFIG.routes["standard-openai-41"] == ("gpt-4.1",)
    assert all(note.startswith("2026-10-19 확인") for note in entry.notes)
    assert "openai_model_gpt41" in entry.source_refs
    # 건당 요금은 이 모델과 gpt-4o(밴드 IR1b)에만 있다.
    assert [key for key, m in CONFIG.models.items() if m.hosted_tool_pricing is not None] == ["gpt-4.1", "gpt-4o"]


def test_the_tool_loop_allow_lists() -> None:
    assert sorted(TOOL_MODELS) == ["gpt-4.1", "gpt-4o"]
    assert sorted(TOOL_PROVIDERS) == ["mock", "mock-b", "openai"]
