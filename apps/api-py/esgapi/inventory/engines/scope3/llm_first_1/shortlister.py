"""후보 추리기: 범주·단위로 거른 후보를 프롬프트에 넣을 수로 줄인다. esg-lab `shortlister.ts`·`ports.ts` 에서 옮겼다.

순위는 `ranking.py`·`lexical_v1.py` 의 순수 함수가 내고 여기서는 자르고 근거를 붙인다.
방식은 낱말 검색 둘뿐이다. `embedding`·`hybrid` 는 옮기지 않았다: hybrid 는 낱말 순위와 임베딩 순위를 합치는
방식이라 임베딩 없이는 순위표가 하나뿐이다. 그래서 TS 의 `ShortlistOutcome` 의 실패 갈래(`ok: false`)도 없다.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal, Protocol

from esgapi.inventory.engines.scope3.llm_first_1.lexical_v1 import ShortlistQuery, rank_lexical_v1
from esgapi.inventory.engines.scope3.llm_first_1.ranking import (
    BM25_B,
    BM25_K1,
    CandidateEvidence,
    LexicalEvidence,
    RankedCandidate,
    rank_lexical_v2,
)
from esgapi.inventory.engines.scope3.llm_first_1.types import Factor
from esgapi.inventory.tools.jsrepr import js_string

ShortlistMethod = Literal["lexical-v1", "lexical-v2"]
SHORTLIST_METHODS: Final[tuple[ShortlistMethod, ...]] = ("lexical-v1", "lexical-v2")

# 방식을 고르지 않았을 때의 추리기. 기본값은 이 한 자리에만 있다.
DEFAULT_SHORTLIST_METHOD: Final[ShortlistMethod] = "lexical-v2"


@dataclass(frozen=True, slots=True)
class ShortlistOutcome:
    """`total` 은 추리기 전 후보 수, `lexical_matches` 는 낱말이 한 군데라도 겹친 후보 수."""

    method: ShortlistMethod
    factors: tuple[Factor, ...]
    evidence: tuple[CandidateEvidence, ...]
    total: int
    lexical_matches: int


class Shortlister(Protocol):
    """`description` 은 방식의 설정을 사람이 읽을 수 있게 적은 것이다."""

    method: ShortlistMethod
    description: str

    def shortlist(self, candidates: Sequence[Factor], query: ShortlistQuery, limit: int) -> ShortlistOutcome: ...


def _cut(
    method: ShortlistMethod, ranked: Sequence[RankedCandidate], total: int, lexical_matches: int, limit: int
) -> ShortlistOutcome:
    top = ranked[:limit]
    return ShortlistOutcome(
        method=method,
        factors=tuple(entry.factor for entry in top),
        evidence=tuple(replace(entry.evidence, rank=position + 1) for position, entry in enumerate(top)),
        total=total,
        lexical_matches=lexical_matches,
    )


def _pad_with_table_order(ranked: Sequence[RankedCandidate], candidates: Sequence[Factor]) -> list[RankedCandidate]:
    """낱말 검색의 순위 뒤에, 겹친 낱말이 없는 후보를 표 순서로 이어 붙인다. 낱말이 적게 겹쳐도 추린 수는 채운다."""
    seen = {entry.factor.id for entry in ranked}
    rest = [
        RankedCandidate(factor, index, 0.0, CandidateEvidence(id=factor.id))
        for index, factor in enumerate(candidates)
        if factor.id not in seen
    ]
    return [*ranked, *rest]


class LexicalV1Shortlister:
    """처음의 글자 수준 검색(부분 문자열 일치 3점, 한글 두 글자 겹침 1점, 동점은 표 순서)."""

    def __init__(self) -> None:
        self.method: ShortlistMethod = "lexical-v1"
        self.description = "lexical-v1: 부분 문자열 일치 3점 + 한글 두 글자 겹침 1점, 동점은 표 순서"

    def shortlist(self, candidates: Sequence[Factor], query: ShortlistQuery, limit: int) -> ShortlistOutcome:
        entries = [
            RankedCandidate(
                entry.factor,
                entry.index,
                entry.score,
                CandidateEvidence(
                    id=entry.factor.id,
                    # 순위는 줄 세운 뒤의 자리다(겹친 것이 없는 후보는 근거가 없다).
                    lexical=LexicalEvidence(position + 1, entry.score, entry.matched) if entry.score > 0 else None,
                ),
            )
            for position, entry in enumerate(rank_lexical_v1(candidates, query))
        ]
        matches = sum(1 for entry in entries if entry.score > 0)
        return _cut(self.method, entries, len(candidates), matches, limit)


class LexicalV2Shortlister:
    def __init__(self, *, bigrams: bool = True) -> None:
        self.method: ShortlistMethod = "lexical-v2"
        self._bigrams = bigrams
        use = "씀" if bigrams else "안 씀"
        self.description = (
            f"lexical-v2: 낱말 단위 BM25 (k1={js_string(BM25_K1)}, b={js_string(BM25_B)}), "
            f"한글 두 글자 조각 {use}, 동점은 표 순서"
        )

    def shortlist(self, candidates: Sequence[Factor], query: ShortlistQuery, limit: int) -> ShortlistOutcome:
        ranked = rank_lexical_v2(candidates, query, bigrams=self._bigrams)
        return _cut(self.method, _pad_with_table_order(ranked, candidates), len(candidates), len(ranked), limit)


def lexical_shortlister(method: ShortlistMethod, *, bigrams: bool = True) -> Shortlister:
    """낱말 검색 추리기를 방식 이름으로 만든다. `bigrams` 는 `lexical-v2` 에만 쓰인다."""
    return LexicalV1Shortlister() if method == "lexical-v1" else LexicalV2Shortlister(bigrams=bigrams)


def default_shortlister() -> Shortlister:
    """방식을 고르지 않았을 때의 추리기(`DEFAULT_SHORTLIST_METHOD`)."""
    return lexical_shortlister(DEFAULT_SHORTLIST_METHOD)
