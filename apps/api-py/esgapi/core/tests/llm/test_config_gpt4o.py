"""gpt-4o 항목(밴드 IR1b `MARC-TICK-282` 의 71-1·71-2): 단가·건당 요금·경로·한도·퇴역일, notes 의 확인일. 순수 층.

수치는 models.json 의 notes 가 인용한 공식 문서 글자에서 온다(2026-10-23 확인). 이 시험은 그 값을 계산으로 고정한다.
"""

from esgapi.core.llm.client import TOOL_MODELS
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.cost import compute_cost_usd
from esgapi.core.llm.types import Usage

CONFIG = load_config(default_config_sources(synthetic=False))


def usage(inp: int, out: int, read: int = 0, write: int = 0) -> Usage:
    return Usage(input_tokens=inp, output_tokens=out, cache_read_tokens=read, cache_write_tokens=write)


def test_gpt4o_prices_match_the_official_table_and_web_search_costs_ten_dollars_per_thousand_calls() -> None:
    model = CONFIG.models["gpt-4o"]
    price = model.entry.pricing
    # openai_pricing Standard 표 「| gpt-4o | $2.50 | $10.00 | $1.25 |」(열 Input, Output, Cached input)
    assert compute_cost_usd(usage(1_000_000, 0), price) == 2.5
    assert compute_cost_usd(usage(0, 1_000_000), price) == 10.0
    assert compute_cost_usd(usage(0, 0, 1_000_000), price) == 1.25
    # 캐시 쓰기: openai_caching 「Other earlier models … No additional cache-write charge」 → 입력 단가 2.5
    assert compute_cost_usd(usage(0, 0, 0, 1_000_000), price) == 2.5
    assert price.long_context is None
    # Tools 표 「Web search (all models) | $10.00 / 1k calls」 → 건당 0.01
    hosted = model.hosted_tool_pricing
    assert hosted is not None
    assert hosted.web_search_per_call == 0.01
    assert compute_cost_usd(usage(0, 0), price, 1000, hosted) == 10.0
    # 손셈: 입력 1만 × 2.5/1M + 출력 2천 × 10/1M + 검색 1건 0.01 = 0.025 + 0.02 + 0.01 = 0.055
    assert round(compute_cost_usd(usage(10_000, 2_000), price, 1, hosted), 9) == 0.055


def test_gpt4o_limits_route_retirement_and_check_dates() -> None:
    model = CONFIG.models["gpt-4o"]
    entry = model.entry
    assert (model.provider, model.api_model_id) == ("openai", "gpt-4o")
    assert entry.context_window_tokens == 128_000
    assert entry.max_output_tokens == 16_384
    assert entry.reasoning_output_reserve_tokens is None
    assert entry.lifecycle.retirement == "January 14, 2027"
    assert "https://developers.openai.com/api/docs/deprecations" in entry.lifecycle.note
    assert "`gpt-4o-2024-08-06`" in entry.lifecycle.note
    assert CONFIG.routes["standard-openai-4o"] == ("gpt-4o",)
    assert all(note.startswith("2026-10-23 확인") for note in entry.notes)
    assert "openai_model_gpt4o" in entry.source_refs


def test_gpt4o_is_on_the_tool_loop_allow_list() -> None:
    assert "gpt-4o" in TOOL_MODELS
