"""낱말 자르기가 TS(Node 22)와 같은 글자를 내는가. 순수 층.

표본 24개(BMP 밖 글자, İ, 전각 숫자, ㎥, 결합 문자, 서러게이트 길이)의 기대값은 esg-lab 의 함수를 Node 로 돌려 얻은
골든이다(tests/data/scope3/golden/unicode-samples.json. make-golden.sh 가 만든다).
무효 조건: Node 22.23.1 의 유니코드는 17.0, 파이썬 3.13 의 `unicodedata` 는 15.1 이다. 15.1 뒤에 더해진 글자의
일반 범주(L·N 인가)와 NFKC 는 다를 수 있다. 표본에는 그런 글자가 없다.
"""

import json
from typing import Any

import pytest

from esgapi.inventory.engines.scope3.llm_first_1.lexical_v1 import (
    ShortlistQuery,
    rank_lexical_v1,
    split_words,
    utf16_length,
)
from esgapi.inventory.engines.scope3.llm_first_1.normalize import normalize_item_name
from esgapi.inventory.engines.scope3.llm_first_1.ranking import singular, tokenize
from esgapi.inventory.engines.scope3.llm_first_1.units import unit_dim
from esgapi.inventory.tests.scope3_catalog_support import G1_GOLDEN, spend_factors

GOLDEN: dict[str, Any] = json.loads((G1_GOLDEN / "unicode-samples.json").read_text(encoding="utf-8"))
SAMPLES: list[dict[str, Any]] = GOLDEN["samples"]


def test_the_golden_has_24_samples_from_node_22() -> None:
    assert len(SAMPLES) == 24
    assert GOLDEN["node"].startswith("v22.")


@pytest.mark.parametrize("sample", SAMPLES, ids=[f"s{index:02d}" for index in range(len(SAMPLES))])
def test_unicode_samples_match_node(sample: dict[str, Any]) -> None:
    text: str = sample["text"]
    assert normalize_item_name(text) == sample["normalized"]
    assert unit_dim(text) == sample["unitDim"]
    assert tokenize(text, bigrams=True) == sample["tokens"]
    assert tokenize(text, bigrams=False) == sample["tokensNoBigrams"]
    # lexical-v1 의 낱말(복수형 접기 없음)과 한글 조각: 이름이 그 표본인 후보 하나에 표본으로 물어 겹친 것.
    [factor] = spend_factors([text])
    assert list(rank_lexical_v1([factor], ShortlistQuery((text,), ()))[0].matched) == sample["v1Matched"]


def test_plurals_fold_and_short_words_drop() -> None:
    words = ["services", "batteries", "glasses", "gas", "bus", "analysis", "cars"]
    assert [singular(word) for word in words] == ["service", "battery", "glass", "gas", "bus", "analysis", "car"]
    assert tokenize("Computer & Peripheral-Equipment Manufacturers, A 4", bigrams=True) == [
        "computer",
        "peripheral",
        "equipment",
        "manufacturer",
    ]
    assert tokenize("합성 강판", bigrams=True) == ["합성", "#합성", "강판", "#강판"]
    assert tokenize("폴리프로필렌", bigrams=False) == ["폴리프로필렌"]


def test_the_ss_us_is_exceptions_and_three_letter_words_stay() -> None:
    assert [singular(word) for word in ["glass", "class", "bus", "status", "analysis", "basis"]] == [
        "glass",
        "class",
        "bus",
        "status",
        "analysis",
        "basis",
    ]
    assert [singular(word) for word in ["gas", "its", "is", "as"]] == ["gas", "its", "is", "as"]
    assert singular("classes") == "class"
    assert singular("ladies") == "lady"
    # 영어 소문자로만 된 낱말만 접는다(숫자·한글·악센트가 섞이면 그대로).
    assert [singular(word) for word in ["m3s", "강판s", "cafés"]] == ["m3s", "강판s", "cafés"]


def test_bigrams_come_only_from_all_hangul_words() -> None:
    assert tokenize("폴리프로필렌", bigrams=True) == ["폴리프로필렌", "#폴리", "#리프", "#프로", "#로필", "#필렌"]
    # 한글과 영문·숫자가 붙은 낱말은 조각을 만들지 않는다(낱말 전체가 한글 음절이어야 한다).
    assert tokenize("a4용지", bigrams=True) == ["a4용지"]
    # 한글 자모(음절이 아닌 것)는 조각이 되지 않는다. NFKC 가 호환 자모(ㄱ U+3131)를 첫소리 자모(U+1100)로 바꾼다.
    assert tokenize("ㄱㄴㄷ", bigrams=True) == ["\u1100\u1102\u1103"]


def test_length_is_counted_in_utf16_units() -> None:
    assert utf16_length("𠮷") == 2
    assert utf16_length("가") == 1
    # BMP 밖 글자 하나는 JS 에서 길이 2 라 「두 글자 미만」에 걸리지 않는다. BMP 안의 한 글자는 버린다.
    assert tokenize("𠮷 가 b", bigrams=True) == ["𠮷"]


def test_underscore_and_combining_marks_split_words() -> None:
    r"""파이썬 `re` 의 `\w` 와 다른 자리: 밑줄과 결합 문자(Mn)는 글자가 아니다."""
    assert split_words("under_score") == ["under", "score"]
    assert split_words("가́나") == ["가", "나"]
    assert split_words("") == []
    assert split_words("---") == []
