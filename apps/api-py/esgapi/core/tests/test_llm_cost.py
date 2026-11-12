"""비용 계산, 토큰 어림, 설정 파일. 순수 층. esg-lab 의 test/cost.test.ts(11건)를 옮긴 것이다.

손계산은 data/models.json 의 단가(USD/100만 토큰. 확인일은 checkedOn 과 항목 notes)로 했다.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.llm.config import Pricing, default_config_sources, load_config
from esgapi.core.llm.cost import HeuristicTokenEstimator, compute_cost_usd, round_usd
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.types import Usage

CONFIG = load_config(default_config_sources(synthetic=False))


def pricing(key: str) -> Pricing:
    return CONFIG.models[key].pricing


def usage(input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> Usage:
    return Usage(input_tokens, output_tokens, cache_read, cache_write)


# ── 비용 계산: 설정 파일 단가로 손계산한 사례 ──


@pytest.mark.parametrize(
    ("model", "used", "expected"),
    [
        # Haiku 4.5: 10,000×1 + 2,000×5 + 50,000×0.1 + 8,000×1.25 = 35,000 → $0.035
        ("claude-haiku-4-5", usage(10_000, 2_000, 50_000, 8_000), 0.035),
        # Sonnet 4.6: 120,000×3 + 4,000×15 = 420,000 → $0.42
        ("claude-sonnet-4-6", usage(120_000, 4_000), 0.42),
        # Sonnet 4.6: 캐시 읽기 2,000,000×0.3 = 600,000 → $0.6 (1M 을 넘겨도 장문 가산이 없다)
        ("claude-sonnet-4-6", usage(0, 0, 2_000_000), 0.6),
        # GPT-6 Luna 단문 구간: 200,000×0.1 + 1,000×0.5 = 20,500 → $0.0205
        ("gpt-6-luna", usage(200_000, 1_000), 0.0205),
        # GPT-6 Luna 장문 구간(입력 272K 초과): 300,000×0.2 + 1,000×0.75 = 60,750 → $0.06075
        ("gpt-6-luna", usage(300_000, 1_000), 0.06075),
        # GPT-6.1 Sol: 1,000×2 + 500×10 + 2,000×0.1 = 7,200 → $0.0072
        ("gpt-6.1-sol", usage(1_000, 500, 2_000), 0.0072),
    ],
)
def test_cost_matches_hand_calculation(model: str, used: Usage, expected: float) -> None:
    assert compute_cost_usd(used, pricing(model)) == expected


def test_long_context_boundary_is_short_and_cache_tokens_count_toward_it() -> None:
    # 경계 272,000 은 단문: 272,000×0.1 = 27,200 → $0.0272
    assert compute_cost_usd(usage(272_000, 0), pricing("gpt-6-luna")) == 0.0272
    # 합계 272,001 > 272,000 → 장문: 200,000×0.2 + 72,001×0.02 = 41,440.02 → $0.04144002
    assert compute_cost_usd(usage(200_000, 0, 72_001), pricing("gpt-6-luna")) == 0.04144002


def test_unreported_cache_tokens_count_as_zero() -> None:
    unreported = Usage(input_tokens=1_000_000, output_tokens=0, cache_read_tokens=None, cache_write_tokens=None)
    assert compute_cost_usd(unreported, pricing("claude-haiku-4-5")) == 1


def test_round_usd_rounds_half_up_like_the_original() -> None:
    """esg-lab 의 Math.round 는 절반을 위로 보낸다. 파이썬의 round 는 짝수 쪽으로 보내 값이 달라진다."""
    assert round_usd(0.5e-8) == 1e-8
    assert round_usd(2.5e-8) == 3e-8
    assert round_usd(0.1 + 0.2) == 0.3


# ── 토큰 어림 ──


def test_estimator_counts_four_latin_chars_or_one_cjk_char_per_token() -> None:
    estimator = HeuristicTokenEstimator(CONFIG.token_estimate)
    assert estimator.estimate("abcdefgh") == 2
    assert estimator.estimate("가나다") == 3
    assert estimator.estimate("가나 ab") == 3  # 2 + 3/4 → 올림 3
    assert estimator.estimate("") == 0


def test_estimator_matches_the_original_regex_ranges_and_utf16_length() -> None:
    estimator = HeuristicTokenEstimator(CONFIG.token_estimate)
    # 여섯 구간의 양 끝은 CJK 로 센다(한 글자 = 1토큰): 자모, 가나, 호환 자모, 한자 확장 A, 한자, 한글 음절.
    for edge in "ᄀᇿ぀ヿ㄰㆏㐀䶿一鿿가힯":
        assert estimator.estimate(edge * 4) == 4, hex(ord(edge))
    # 구간 바로 밖은 라틴으로 센다(네 글자 = 1토큰).
    for outside in "\u10ff\u1200\u303f\u3100\u312f\u3190\u33ff\u4dc0\u4dff\ua000\uabff\ud7b0":
        assert estimator.estimate(outside * 4) == 1, hex(ord(outside))
    # BMP 밖의 글자(그림 글자)는 JS 의 text.length 처럼 둘로 센다: 2글자 × 2 = 4 단위 → 1토큰. 3글자면 6 단위 → 2토큰.
    assert estimator.estimate("😀😀") == 1
    assert estimator.estimate("😀😀😀") == 2


# ── 설정 파일 ──


def test_real_models_all_have_sources_and_synthetic_models_stay_out_of_the_default() -> None:
    assert sorted(CONFIG.models) == [
        "claude-haiku-4-5",
        "claude-sonnet-4-6",
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4o",
        "gpt-6-luna",
        "gpt-6.1-sol",
    ]
    for model in CONFIG.models.values():
        assert len(model.entry.source_refs) > 0
        assert model.entry.synthetic is None
    with_synthetic = load_config(default_config_sources(synthetic=True))
    assert with_synthetic.models["mock-synthetic"].entry.synthetic is True


def test_copied_data_files_say_when_the_numbers_were_checked() -> None:
    """모델 설정 자료에는 확인 일자와 출처가 실려 있다(수치는 출처 없이 넣지 않는다)."""
    (real,) = default_config_sources(synthetic=False)
    body = json.loads(real.read_text(encoding="utf-8"))
    assert body["checkedOn"] == "2026-10-01"
    assert len(body["sources"]) == 29
    assert all(url.startswith("https://") for url in body["sources"].values())


MODEL: dict[str, Any] = {
    "provider": "p",
    "apiModelId": "m",
    "label": "m",
    "pricing": {"input": 1, "output": 1, "cacheWrite": 1, "cacheRead": 1},
    "contextWindowTokens": 10,
    "maxOutputTokens": 10,
    "minCacheTokens": 10,
    "pdf": {"maxPagesPerRequest": None, "maxRequestMb": 1},
    "structuredOutput": True,
    "lifecycle": {"status": "s", "retirement": None, "note": ""},
    "sourceRefs": [],
    "notes": [],
}
TOKEN_ESTIMATE = {"note": "", "latinCharsPerToken": 4, "latinBasis": "", "cjkCharsPerToken": 1, "cjkBasis": ""}
FILE: dict[str, Any] = {
    "checkedOn": "2026-10-01",
    "note": "",
    "sources": {"a": "https://example.com/a"},
    "tokenEstimate": TOKEN_ESTIMATE,
    "routes": {},
}
SOURCED = {**MODEL, "sourceRefs": ["a"]}


@pytest.mark.parametrize(
    ("name", "body", "message"),
    [
        ("no-source.json", {**FILE, "models": {"m": MODEL}}, "출처가 없다"),
        ("bad-ref.json", {**FILE, "models": {"m": {**MODEL, "sourceRefs": ["zzz"]}}}, "sources 에 없다"),
        ("unmarked.synthetic.json", {**FILE, "synthetic": True, "models": {"m": MODEL}}, "synthetic 표시가 없다"),
        ("marked-in-real.json", {**FILE, "models": {"m": {**SOURCED, "synthetic": True}}}, "synthetic 파일에 둬야"),
        ("bad-route.json", {**FILE, "models": {"m": SOURCED}, "routes": {"r": ["nope"]}}, "없는 모델 nope"),
        ("empty-route.json", {**FILE, "models": {"m": SOURCED}, "routes": {"r": []}}, "routes.r"),
        ("extra-key.json", {**FILE, "models": {"m": {**SOURCED, "price": 1}}}, "models.m.price"),
        (
            "negative-rate.json",
            {**FILE, "models": {"m": {**SOURCED, "pricing": {**MODEL["pricing"], "input": -1}}}},
            "input",
        ),
        ("text-number.json", {**FILE, "models": {"m": {**SOURCED, "maxOutputTokens": "10"}}}, "maxOutputTokens"),
        ("bad-date.json", {**FILE, "checkedOn": "2026/10/01", "models": {"m": SOURCED}}, "checkedOn"),
        ("bad-url.json", {**FILE, "sources": {"a": "not a url"}, "models": {"m": SOURCED}}, "sources.a"),
        (
            "no-estimate.json",
            {k: v for k, v in FILE.items() if k != "tokenEstimate"} | {"models": {"m": SOURCED}},
            "tokenEstimate",
        ),
    ],
)
def test_bad_config_files_are_rejected(tmp_path: Path, name: str, body: dict[str, Any], message: str) -> None:
    path = tmp_path / name
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(LlmConfigError, match=message):
        load_config([path])


def test_a_minimal_good_file_loads_and_duplicates_across_files_are_rejected(tmp_path: Path) -> None:
    """위의 거부 사례들이 「파일이 통째로 틀려서」 거부된 것이 아님을 보인다: 같은 뼈대의 옳은 파일은 읽힌다."""
    good = tmp_path / "good.json"
    good.write_text(json.dumps({**FILE, "models": {"m": SOURCED}, "routes": {"r": ["m"]}}), encoding="utf-8")
    config = load_config([good])
    assert [model.key for model in config.models.values()] == ["m"]
    assert config.routes == {"r": ("m",)}
    with pytest.raises(LlmConfigError, match="중복"):
        load_config([good, good])
    with pytest.raises(LlmConfigError, match="읽을 수 없다"):
        load_config([tmp_path / "missing.json"])


def test_gpt41_mini_prices_match_the_official_table_and_has_its_own_route() -> None:
    """gpt-4.1-mini(밴드 GM1 `MARC-TICK-134`): 단가와 경로 하나, 항목 notes 의 확인일."""
    model = CONFIG.models["gpt-4.1-mini"]
    price = model.entry.pricing
    # openai_pricing Standard 표 「| gpt-4.1-mini | $0.40 | $0.10 | - | $1.60 | - | - | - | - |」
    # 1,000,000×0.4 → $0.4 · 1,000,000×1.6 → $1.6 · 캐시 읽기 1,000,000×0.1 → $0.1
    assert compute_cost_usd(usage(1_000_000, 0), price) == 0.4
    assert compute_cost_usd(usage(0, 1_000_000), price) == 1.6
    assert compute_cost_usd(usage(0, 0, 1_000_000), price) == 0.1
    # 캐시 쓰기: openai_caching 「Other earlier models … No additional cache-write charge」 → 입력 단가 0.4 → $0.4
    assert compute_cost_usd(usage(0, 0, 0, 1_000_000), price) == 0.4
    # 장문 구간 칸이 전부 「-」라 장문 단가가 없다
    assert price.long_context is None
    assert CONFIG.routes["light-openai-41"] == ("gpt-4.1-mini",)
    assert any("2026-10-16 확인" in note for note in model.entry.notes)
