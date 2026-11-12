"""후보 순위와 추리기. esg-lab `retrieval.test.ts` 의 lexical-v2 다섯·순위 합산 둘·방식 설정 둘과
`factors.test.ts` 의 lexical-v1 둘을 옮겼다. 순수 층.

옮기지 않은 것: 임베딩 색인·임베딩 방식·CLI 의 것(임베딩 갈래와 CLI 를 옮기지 않았다).
"""

import math

from esgapi.inventory.engines.scope3.llm_first_1.catalog import ListFactorCatalog
from esgapi.inventory.engines.scope3.llm_first_1.lexical_v1 import ShortlistQuery, shortlist
from esgapi.inventory.engines.scope3.llm_first_1.ranking import (
    BM25_B,
    BM25_K1,
    RRF_K,
    CandidateEvidence,
    RankedCandidate,
    factor_text,
    fuse_rrf,
    rank_lexical_v2,
)
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import (
    DEFAULT_SHORTLIST_METHOD,
    SHORTLIST_METHODS,
    LexicalV1Shortlister,
    LexicalV2Shortlister,
    default_shortlister,
    lexical_shortlister,
)
from esgapi.inventory.engines.scope3.llm_first_1.types import CandidateQuery, Factor
from esgapi.inventory.tests.scope3_catalog_support import HELPER_RECORDS, spend_factors


def ids(ranked: list[RankedCandidate]) -> list[str]:
    return [entry.factor.id for entry in ranked]


def keywords(*words: str) -> ShortlistQuery:
    return ShortlistQuery(texts=(), keywords=words)


def test_whole_words_only_car_does_not_match_cargo() -> None:
    factors = spend_factors(["Synthetic cargo ship", "Synthetic car rental", "Synthetic scar tissue"])
    ranked = rank_lexical_v2(factors, keywords("car"), bigrams=True)
    assert ids(ranked) == ["syn:s1"]
    assert ranked[0].evidence.lexical is not None
    assert ranked[0].evidence.lexical.matched_terms == ("car",)
    # 처음 방식은 부분 문자열로 맞춰 셋 다 걸린다.
    assert LexicalV1Shortlister().shortlist(factors, keywords("car"), 3).lexical_matches == 3


def test_rare_words_weigh_more_than_common_words() -> None:
    names = ["widget manufacturing", "gadget manufacturing", "gizmo manufacturing", "elevator repair"]
    factors = spend_factors([f"Synthetic {name}" for name in names])
    ranked = rank_lexical_v2(factors, keywords("elevator manufacturing"), bigrams=True)
    # elevator 는 한 건에만, manufacturing 은 세 건에 있다. 낱말 하나씩 겹쳤어도 드문 쪽이 위다.
    assert ids(ranked) == ["syn:s3", "syn:s0", "syn:s1", "syn:s2"]
    assert ranked[0].score > ranked[1].score * 2


def test_the_score_is_bm25_with_the_ported_constants() -> None:
    """상수는 TS 의 것이다(`ranking.ts:11-13`). 손으로 한 번 계산해 식을 못 박는다."""
    assert (BM25_K1, BM25_B, RRF_K) == (1.2, 0.75, 60)
    factors = spend_factors(["Synthetic pump", "Synthetic valve seal"])
    [only] = rank_lexical_v2(factors, keywords("pump"), bigrams=True)
    # 후보 2, pump 가 든 것 1 → idf = ln(1 + (2 - 1 + 0.5) / (1 + 0.5)) = ln 2. 글 길이 2 와 3, 평균 2.5.
    expected = (math.log(2) * 1 * 2.2) / (1 + 1.2 * (1 - 0.75 + (0.75 * 2) / 2.5))
    assert math.isclose(only.score, expected, rel_tol=1e-12)
    # b 가 0 이면 글 길이가 점수에 들지 않는다. 0.75 인 지금은 긴 글이 덜 받는다.
    shorter, longer = rank_lexical_v2(
        spend_factors(["Synthetic pump", "Synthetic pump with a very long descriptive name"]),
        keywords("pump"),
        bigrams=True,
    )
    assert (shorter.factor.id, longer.factor.id) == ("syn:s0", "syn:s1")
    assert shorter.score > longer.score


def test_ties_follow_table_order_and_unmatched_candidates_pad_in_table_order() -> None:
    names = ["Synthetic legal alpha", "Synthetic pump beta", "Synthetic pump gamma", "Synthetic legal delta"]
    factors = spend_factors(names)
    ranked = rank_lexical_v2(factors, keywords("pump"), bigrams=True)
    assert ids(ranked) == ["syn:s1", "syn:s2"]
    assert ranked[0].score == ranked[1].score
    outcome = LexicalV2Shortlister().shortlist(factors, keywords("pump"), 3)
    assert [factor.id for factor in outcome.factors] == ["syn:s1", "syn:s2", "syn:s0"]
    assert outcome.lexical_matches == 2
    assert outcome.total == 4
    assert [entry.lexical.rank if entry.lexical else None for entry in outcome.evidence] == [1, 2, None]
    assert [entry.rank for entry in outcome.evidence] == [1, 2, 3]
    # 표의 순서를 뒤집어 주면 동점인 둘의 차례도 뒤집힌다(동점을 가르는 것은 받은 차례뿐이다).
    reversed_outcome = LexicalV2Shortlister().shortlist(factors[::-1], keywords("pump"), 3)
    assert [factor.id for factor in reversed_outcome.factors] == ["syn:s2", "syn:s1", "syn:s3"]


def test_hangul_bigrams_can_be_switched_off() -> None:
    factors = spend_factors(["합성 폴리프로필렌수지", "합성 강판"])
    query = ShortlistQuery(texts=("프로필렌 원료",), keywords=())
    assert ids(rank_lexical_v2(factors, query, bigrams=True)) == ["syn:s0"]
    assert ids(rank_lexical_v2(factors, query, bigrams=False)) == []


def test_english_keywords_never_make_hangul_bigrams() -> None:
    """한글 조각은 원문 글자에서만 만든다. 검색어 자리에 한글이 와도 조각을 내지 않는다."""
    factors = spend_factors(["합성 폴리프로필렌수지", "합성 강판"])
    assert ids(rank_lexical_v2(factors, keywords("프로필렌 원료"), bigrams=True)) == []
    from_text = rank_lexical_v2(factors, ShortlistQuery(("프로필렌",), ("강판 sheet",)), bigrams=True)
    matched = {entry.factor.id: entry.evidence.lexical.matched_terms for entry in from_text if entry.evidence.lexical}
    assert matched == {"syn:s0": ("#프로", "#로필", "#필렌"), "syn:s1": ("강판",)}


def test_factor_text_joins_name_and_path() -> None:
    catalog = ListFactorCatalog(HELPER_RECORDS)
    steel = catalog.get("syn:steel-kg")
    legal = catalog.get("syn:spend-legal")
    assert steel is not None
    assert legal is not None
    assert factor_text(steel) == "합성 강판 (synthetic) | 합성 자재 > 금속"
    assert factor_text(legal) == "Synthetic Legal Services"


def entry(factor: Factor, index: int) -> RankedCandidate:
    return RankedCandidate(factor, index, 0.0, CandidateEvidence(id=factor.id))


def test_rrf_adds_one_over_k_plus_rank_and_gives_only_its_share_to_single_list_candidates() -> None:
    a, b, c = spend_factors(["A synthetic", "B synthetic", "C synthetic"])
    fused = fuse_rrf([[entry(a, 0), entry(b, 1)], [entry(b, 1), entry(c, 2), entry(a, 0)]])
    assert ids(fused) == ["syn:s1", "syn:s0", "syn:s2"]
    assert math.isclose(fused[0].score, 1 / (RRF_K + 2) + 1 / (RRF_K + 1), abs_tol=1e-12)
    assert math.isclose(fused[1].score, 1 / (RRF_K + 1) + 1 / (RRF_K + 3), abs_tol=1e-12)
    assert math.isclose(fused[2].score, 1 / (RRF_K + 2), abs_tol=1e-12)
    assert [candidate.evidence.rrf_score for candidate in fused] == [candidate.score for candidate in fused]
    assert fused[0].evidence.to_json() == {"id": "syn:s1", "rrfScore": fused[0].score, "rank": 0}


def test_rrf_ties_follow_table_order() -> None:
    a, b = spend_factors(["A synthetic", "B synthetic"])
    assert ids(fuse_rrf([[entry(b, 1), entry(a, 0)], [entry(a, 0), entry(b, 1)]])) == ["syn:s0", "syn:s1"]


def test_the_default_method_lives_in_one_place() -> None:
    assert DEFAULT_SHORTLIST_METHOD == "lexical-v2"
    assert SHORTLIST_METHODS == ("lexical-v1", "lexical-v2")
    assert default_shortlister().method == DEFAULT_SHORTLIST_METHOD
    assert isinstance(default_shortlister(), LexicalV2Shortlister)
    assert isinstance(lexical_shortlister("lexical-v1"), LexicalV1Shortlister)
    assert "안 씀" in lexical_shortlister("lexical-v2", bigrams=False).description
    assert default_shortlister().description == (
        "lexical-v2: 낱말 단위 BM25 (k1=1.2, b=0.75), 한글 두 글자 조각 씀, 동점은 표 순서"
    )


def test_the_v1_shortlister_gives_the_same_list_as_the_first_shortlist_function() -> None:
    names = ["Synthetic cargo ship", "Synthetic car rental", "Synthetic scar tissue", "Synthetic legal"]
    factors = spend_factors(names)
    outcome = LexicalV1Shortlister().shortlist(factors, keywords("car"), 2)
    assert [factor.id for factor in outcome.factors] == ["syn:s0", "syn:s1"]
    assert outcome.lexical_matches == 3
    first = shortlist(factors, keywords("car"), 2)
    assert first.factors == outcome.factors
    assert (first.total, first.lexical_matches) == (4, 3)
    assert [item.to_json() for item in outcome.evidence] == [
        {"id": "syn:s0", "lexical": {"rank": 1, "score": 3, "matchedTerms": ["car"]}, "rank": 1},
        {"id": "syn:s1", "lexical": {"rank": 2, "score": 3, "matchedTerms": ["car"]}, "rank": 2},
    ]


def test_v1_puts_overlapping_candidates_first_and_limits_the_count() -> None:
    catalog = ListFactorCatalog(HELPER_RECORDS)
    spend = catalog.candidates(CandidateQuery(1, "spend"))
    by_keyword = shortlist(spend, ShortlistQuery(("법률 자문",), ("legal services",)), 2)
    assert [factor.id for factor in by_keyword.factors] == ["syn:spend-legal", "syn:spend-computer"]
    assert by_keyword.total == 3
    korean = shortlist(catalog.candidates(CandidateQuery(1, "physical")), ShortlistQuery(("폴리프로필렌 수지",), ()), 1)
    assert [factor.id for factor in korean.factors] == ["syn:pp-kg"]


def test_v1_says_so_when_nothing_overlaps() -> None:
    catalog = ListFactorCatalog(HELPER_RECORDS)
    result = shortlist(catalog.candidates(CandidateQuery(1, "spend")), ShortlistQuery(("zzz",), ()), 2)
    assert result.lexical_matches == 0
    assert len(result.factors) == 2
    outcome = LexicalV1Shortlister().shortlist(catalog.candidates(CandidateQuery(1, "spend")), keywords("zzz"), 2)
    assert [item.to_json() for item in outcome.evidence] == [
        {"id": "syn:spend-computer", "rank": 1},
        {"id": "syn:spend-storage", "rank": 2},
    ]
