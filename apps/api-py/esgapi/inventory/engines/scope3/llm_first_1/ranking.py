"""후보 순위 함수. esg-lab `ts/scope3/src/domain/ranking.ts` 를 옮긴 것이다. 입출력이 없다.

점수는 TS 가 배정밀도(double)라 여기서도 float 다. 배출량·활동량에는 float 가 닿지 않는다
(`calc.py` 는 이 파일을 모른다).
옮기지 않은 것: `cosine`·`rankByEmbedding`·`embeddingQueryText`(임베딩 갈래).
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from esgapi.inventory.engines.scope3.llm_first_1.lexical_v1 import (
    ShortlistQuery,
    is_hangul_syllable,
    split_words,
    utf16_length,
)
from esgapi.inventory.engines.scope3.llm_first_1.types import Factor

# 미리 정한 기본값이다. 예제 세트를 보고 고른 값이 아니다(BM25 의 통상 기본값, RRF 논문의 k).
# 출처: esg-lab ts/scope3/src/domain/ranking.ts:11-13 (HEAD f1b2c77, 확인 2026-10-08).
BM25_K1: Final = 1.2
BM25_B: Final = 0.75
RRF_K: Final = 60

_ASCII_LOWER: Final = re.compile(r"[a-z]+")


@dataclass(frozen=True, slots=True)
class LexicalEvidence:
    rank: int
    score: float
    matched_terms: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        return {"rank": self.rank, "score": self.score, "matchedTerms": list(self.matched_terms)}


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """추린 후보 하나가 왜 그 자리에 왔는지. 순위는 1부터다. 낱말 검색에 걸리지 않았으면 `lexical` 이 없다.

    `rrf_score` 는 순위 합산 점수다(`fuse_rrf` 를 거쳤을 때만 있다). `rank` 는 자른 뒤에 붙는다(그 전에는 0).
    """

    id: str
    rank: int = 0
    lexical: LexicalEvidence | None = None
    rrf_score: float | None = None

    def to_json(self) -> dict[str, object]:
        """TS 와 같은 키 순서(id, lexical, rrfScore, rank). 없는 근거는 null 이 아니라 키가 없다."""
        out: dict[str, object] = {"id": self.id}
        if self.lexical is not None:
            out["lexical"] = self.lexical.to_json()
        if self.rrf_score is not None:
            out["rrfScore"] = self.rrf_score
        out["rank"] = self.rank
        return out


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    """`index` 는 후보 표에서의 순서다. 동점을 가르는 마지막 기준이다."""

    factor: Factor
    index: int
    score: float
    evidence: CandidateEvidence


def singular(word: str) -> str:
    """영어 복수형만 접는다(services → service, batteries → battery). 그 밖의 어형 변화는 건드리지 않는다."""
    if _ASCII_LOWER.fullmatch(word) is None or len(word) <= 3:
        return word
    if word.endswith("ies"):
        return f"{word[:-3]}y"
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokenize(text: str, *, bigrams: bool) -> list[str]:
    """글을 낱말 단위로 쪼갠다. 글자·숫자가 아닌 것에서 끊고, 두 글자(UTF-16 단위) 미만은 버린다.

    `bigrams` 를 켜면 한글 낱말은 두 글자 조각(`#` 접두)도 낱말로 더한다. 한국어 계수 이름은 띄어쓰기 없이 붙여 쓴
    복합어가 많아서다.
    """
    tokens: list[str] = []
    for raw in split_words(text):
        if utf16_length(raw) < 2:
            continue
        tokens.append(singular(raw))
        # JS 의 `/^[가-힣]+$/`: 낱말 전체가 한글 음절일 때만 조각을 만든다.
        if bigrams and all(is_hangul_syllable(ch) for ch in raw):
            tokens.extend(f"#{raw[i : i + 2]}" for i in range(len(raw) - 1))
    return tokens


def factor_text(factor: Factor) -> str:
    """계수 하나를 검색할 때 쓰는 글."""
    path = " > ".join(factor.category_path)
    return factor.name if path == "" else f"{factor.name} | {path}"


def _order(entry: RankedCandidate) -> tuple[float, int]:
    return (-entry.score, entry.index)


def rank_lexical_v2(candidates: Sequence[Factor], query: ShortlistQuery, *, bigrams: bool) -> list[RankedCandidate]:
    """낱말 단위 BM25. 낱말이 통째로 같아야 맞는다(`car` 는 `cargo` 에 맞지 않는다).

    드문 낱말일수록 무겁다: IDF 는 이번 호출에 넘어온 후보 집합에서 센다.
    점수가 0 인 후보(겹친 낱말 없음)는 돌려주지 않는다. 동점은 후보 표의 순서를 따른다.
    """
    docs: list[tuple[dict[str, int], int]] = []
    for factor in candidates:
        tokens = tokenize(factor_text(factor), bigrams=bigrams)
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        docs.append((counts, len(tokens)))
    average_length = sum(length for _, length in docs) / max(1, len(docs))
    # 영어 검색어에서는 한글 조각이 나오지 않는다. 한글 조각은 원문 글자에서만 만든다.
    # 차례는 JS 의 Set 과 같다(넣은 순서): 원문 글자의 낱말 먼저, 영어 검색어 뒤. 점수의 합이 이 차례로 더해진다.
    terms = list(
        dict.fromkeys(
            [
                *(token for text in query.texts for token in tokenize(text, bigrams=bigrams)),
                *(token for text in query.keywords for token in tokenize(text, bigrams=False)),
            ]
        )
    )
    idf: dict[str, float] = {}
    for term in terms:
        df = sum(1 for counts, _ in docs if term in counts)
        idf[term] = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
    ranked: list[RankedCandidate] = []
    for index, factor in enumerate(candidates):
        counts, length = docs[index]
        score = 0.0
        matched: list[str] = []
        for term in terms:
            tf = counts.get(term)
            if tf is None:
                continue
            matched.append(term)
            score += (idf[term] * tf * (BM25_K1 + 1)) / (
                tf + BM25_K1 * (1 - BM25_B + (BM25_B * length) / average_length)
            )
        if matched:
            evidence = CandidateEvidence(id=factor.id, lexical=LexicalEvidence(0, score, tuple(matched)))
            ranked.append(RankedCandidate(factor, index, score, evidence))
    ranked.sort(key=_order)
    return [_with_rank(entry, position + 1) for position, entry in enumerate(ranked)]


def _with_rank(entry: RankedCandidate, rank: int) -> RankedCandidate:
    lexical = entry.evidence.lexical
    if lexical is None:  # pragma: no cover  (rank_lexical_v2 는 겹친 낱말이 있는 후보만 낸다)
        return entry
    return replace(entry, evidence=replace(entry.evidence, lexical=replace(lexical, rank=rank)))


def fuse_rrf(rankings: Sequence[Sequence[RankedCandidate]], k: int = RRF_K) -> list[RankedCandidate]:
    """순위 합산(RRF). 각 순위표에서 r 등인 후보에 1/(k+r) 을 주고 더한다.

    한 순위표에 없는 후보는 그 표에서 0 을 받는다.

    동점은 후보 표의 순서를 따른다. 근거는 뒤 순위표의 것이 앞의 것에 덮여 합쳐진다(있는 칸만).
    """
    fused: dict[str, RankedCandidate] = {}
    for ranking in rankings:
        for position, entry in enumerate(ranking):
            current = fused.get(entry.factor.id) or RankedCandidate(
                entry.factor, entry.index, 0.0, CandidateEvidence(id=entry.factor.id)
            )
            score = current.score + 1 / (k + position + 1)
            evidence = CandidateEvidence(
                id=entry.factor.id,
                lexical=entry.evidence.lexical if entry.evidence.lexical is not None else current.evidence.lexical,
                rrf_score=score,
            )
            fused[entry.factor.id] = RankedCandidate(current.factor, current.index, score, evidence)
    return sorted(fused.values(), key=_order)
