"""BM25(engines/g1/lexical.py — 밴드 GE1 T6): 낱말 나눔과 손셈."""

import math

import pytest

from esgapi.greenwash.engines.g1 import lexical


def test_tokens_are_ascii_words_and_hangul_bigrams() -> None:
    assert lexical.tokens("Scope 1,234 배출량 저감") == ["scope", "1234", "배출", "출량", "저감"]
    assert lexical.tokens("물") == ["물"]


def test_bm25_matches_a_hand_count() -> None:
    bm = lexical.BM25(["탄소 감축", "탄소 탄소", "물 사용"])
    # n=3, df(탄소)=2 → idf = log(1 + 1.5/2.5). 길이 2·2·2 → 평균 2 → 길이 보정 1.
    idf = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
    s1 = idf * 1 * 2.2 / (1 + 1.2)
    s2 = idf * 2 * 2.2 / (2 + 1.2)
    assert bm.scores("탄소") == pytest.approx([s1, s2, 0.0])


def test_bm25_length_normalisation_uses_b() -> None:
    bm = lexical.BM25(["탄소", "탄소 물 물 물"])
    idf = math.log(1 + (2 - 2 + 0.5) / (2 + 0.5))
    avg = (1 + 4) / 2
    want = [idf * 2.2 / (1 + 1.2 * (1 - 0.75 + 0.75 * n / avg)) for n in (1, 4)]
    assert bm.scores("탄소") == pytest.approx(want)
