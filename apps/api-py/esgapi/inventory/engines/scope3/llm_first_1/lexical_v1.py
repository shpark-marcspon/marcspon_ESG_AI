"""처음의 글자 수준 검색(lexical-v1). esg-lab `ts/scope3/src/domain/lexicalV1.ts` 를 옮긴 것이다.

낱말이 「이름 + 분류 경로」에 부분 문자열로 들어 있으면 3점, 원문 글자의 한글 두 글자 조각이 들어 있으면 1점.
점수가 같으면 표의 순서를 따른다. 뜻을 아는 검색이 아니다. 견줄 기준으로 남긴다.
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from esgapi.inventory.engines.scope3.llm_first_1.normalize import is_letter_or_number
from esgapi.inventory.engines.scope3.llm_first_1.types import Factor


@dataclass(frozen=True, slots=True)
class ShortlistQuery:
    # 품목명과 운송 수단 같은 원문 글자.
    texts: tuple[str, ...]
    # 분류 단계가 낸 영어 검색어.
    keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Shortlist:
    """`total` 은 추리기 전 후보 수. `lexical_matches` 가 0 이면 추린 목록은 표의 앞 순서일 뿐이다."""

    factors: tuple[Factor, ...]
    total: int
    lexical_matches: int


@dataclass(frozen=True, slots=True)
class V1Ranked:
    factor: Factor
    index: int
    score: int
    matched: tuple[str, ...]


def utf16_length(text: str) -> int:
    """JS 의 `text.length`(UTF-16 단위의 수). BMP 밖 글자 하나는 2 다."""
    return len(text) + sum(1 for ch in text if ord(ch) > 0xFFFF)


def split_words(text: str) -> list[str]:
    r"""JS 의 `text.normalize("NFKC").toLowerCase().split(/[^\p{L}\p{N}]+/u)` 에서 빈 조각을 뺀 것.

    글자·숫자(유니코드 일반 범주 L*·N*)가 아닌 글자에서 끊는다. 길이로 거르는 것은 부르는 쪽이 한다.
    """
    lowered = unicodedata.normalize("NFKC", text).lower()
    words: list[str] = []
    current: list[str] = []
    for ch in lowered:
        if is_letter_or_number(ch):
            current.append(ch)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words


def is_hangul_syllable(ch: str) -> bool:
    """JS 의 `/[가-힣]/`: 한글 음절 U+AC00~U+D7A3."""
    return "가" <= ch <= "힣"


def _words(text: str) -> list[str]:
    return [word for word in split_words(text) if utf16_length(word) >= 2]


def _hangul_bigrams(text: str) -> list[str]:
    grams: list[str] = []
    for word in _words(text):
        # 한글 음절은 BMP 안이라 UTF-16 단위로 자른 것과 코드 포인트로 자른 것이 같다.
        for first, second in pairwise(word):
            if is_hangul_syllable(first) and is_hangul_syllable(second):
                grams.append(first + second)
    return grams


def _search_text(factor: Factor) -> str:
    return unicodedata.normalize("NFKC", f"{factor.name} {' '.join(factor.category_path)}").lower()


def rank_lexical_v1(candidates: Sequence[Factor], query: ShortlistQuery) -> list[V1Ranked]:
    """후보 전체에 lexical-v1 의 점수를 매겨 줄 세운다. `matched` 는 겹친 낱말과 한글 두 글자 조각(`#` 접두)이다."""
    # JS 의 Set 은 넣은 순서를 지킨다: 원문 글자의 낱말 먼저, 영어 검색어 뒤.
    query_words = list(dict.fromkeys(word for text in (*query.texts, *query.keywords) for word in _words(text)))
    query_grams = list(dict.fromkeys(gram for text in query.texts for gram in _hangul_bigrams(text)))
    scored: list[V1Ranked] = []
    for index, factor in enumerate(candidates):
        text = _search_text(factor)
        score = 0
        matched: list[str] = []
        for word in query_words:
            if word in text:
                score += 3
                matched.append(word)
        for gram in query_grams:
            if gram in text:
                score += 1
                matched.append(f"#{gram}")
        scored.append(V1Ranked(factor, index, score, tuple(matched)))
    scored.sort(key=lambda entry: (-entry.score, entry.index))
    return scored


def shortlist(candidates: Sequence[Factor], query: ShortlistQuery, limit: int) -> Shortlist:
    """후보를 프롬프트에 넣을 수 있는 수로 추린다(lexical-v1)."""
    scored = rank_lexical_v1(candidates, query)
    matches = sum(1 for entry in scored if entry.score > 0)
    return Shortlist(tuple(entry.factor for entry in scored[:limit]), len(candidates), matches)
