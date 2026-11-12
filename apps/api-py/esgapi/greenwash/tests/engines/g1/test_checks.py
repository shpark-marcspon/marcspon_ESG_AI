"""코드 검사 넷과 안정 열쇠(engines/g1/checks.py — 밴드 GE1 T2·T3). 지어낸 문장만 쓴다."""

import unicodedata

import pytest

from esgapi.greenwash.engines.e0.heuristics import is_low_declarative
from esgapi.greenwash.engines.g1 import checks

DOC = "a" * 64
OTHER_DOC = "b" * 64
SENTENCE = "가상회사는 2030년까지 사업장 전력의 절반을 재생에너지로 바꾸었습니다."
DECLARATIVE = "가상회사는 친환경 경영을 지속적으로 추진하겠습니다."


# ── T2 검사 넷 ─────────────────────────────────────────────────────────


def test_quote_in_block_passes_across_block_boundaries_and_spacing() -> None:
    blocks = ["가상회사는 2030년까지 사업장 전력의", "절반을 재생에\n너지로 바꾸었습니다. 다음 문장."]
    got = checks.quote_in_block(SENTENCE, blocks)
    assert (got.name, got.ok, got.failure) == ("quote_in_block", True, None)


@pytest.mark.parametrize(
    "blocks",
    [
        [],
        ["가상회사는 2030년까지 사업장 전력의 3분의 1을 재생에너지로 바꾸었습니다."],
        ["바꾸었습니다.", SENTENCE[:10]],
    ],
)
def test_quote_in_block_fails_by_name(blocks: list[str]) -> None:
    got = checks.quote_in_block(SENTENCE, blocks)
    assert (got.ok, got.failure) == (False, "quote_not_found")


def test_quote_in_block_reads_blocks_in_the_given_order() -> None:
    blocks = ["절반을 재생에너지로 바꾸었습니다.", "가상회사는 2030년까지 사업장 전력의"]
    assert checks.quote_in_block(SENTENCE, blocks).failure == "quote_not_found"


def test_quote_in_block_rejects_an_empty_sentence() -> None:
    assert checks.quote_in_block("  ", ["무엇이든"]).failure == "quote_not_found"


def test_evidence_in_pool() -> None:
    assert checks.evidence_in_pool(["P2", "P5"], ["P1", "P2", "P5"]).ok
    assert checks.evidence_in_pool([], ["P1"]).ok
    got = checks.evidence_in_pool(["P2", "P9", "P9"], ["P1", "P2"])
    assert (got.ok, got.failure, got.offending) == (False, "evidence_outside_pool", ("P9",))


def test_category_in_list_with_an_empty_list_allows_null_only() -> None:
    assert checks.category_in_list(None, []).ok
    got = checks.category_in_list("과장", [])
    assert (got.ok, got.failure) == (False, "category_unknown")


def test_category_in_list_with_a_list() -> None:
    assert checks.category_in_list("과장", ["과장", "모호"]).ok
    assert checks.category_in_list(None, ["과장"]).ok
    assert checks.category_in_list("은폐", ["과장"]).failure == "category_unknown"


def test_level_rule_reads_the_e0_declarative_rule() -> None:
    assert is_low_declarative(DECLARATIVE)
    assert not is_low_declarative(SENTENCE)
    assert checks.level_rule("Low", DECLARATIVE).ok
    got = checks.level_rule("Low", SENTENCE)
    assert (got.ok, got.failure) == (False, "level_rule_broken")
    for level in ("High", "Mid", "None"):
        assert checks.level_rule(level, SENTENCE).ok
        assert checks.level_rule(level, DECLARATIVE).ok


def test_first_failure_follows_the_check_order() -> None:
    results = [
        checks.quote_in_block(SENTENCE, [SENTENCE]),
        checks.evidence_in_pool(["P9"], ["P1"]),
        checks.category_in_list("과장", []),
    ]
    assert checks.first_failure(results) == "evidence_outside_pool"
    assert checks.first_failure(results[:1]) is None


# ── T3 안정 열쇠 ───────────────────────────────────────────────────────


def test_stable_key_ignores_spacing_and_unicode_form() -> None:
    decomposed = "가상회사는　 2030년까지  사업장 전력의 절반을\n재생에너지로 바꾸었습니다. "
    nfd = unicodedata.normalize("NFD", SENTENCE)
    key = checks.stable_key(DOC, SENTENCE, 4)
    assert key == checks.stable_key(DOC, decomposed, 4) == checks.stable_key(DOC, nfd, 4)
    assert len(key) == checks.STABLE_KEY_CHARS == 32
    assert all(c in "0123456789abcdef" for c in key)


def test_stable_key_differs_by_page_and_document_and_sentence() -> None:
    key = checks.stable_key(DOC, SENTENCE, 4)
    assert key != checks.stable_key(DOC, SENTENCE, 5)
    assert key != checks.stable_key(OTHER_DOC, SENTENCE, 4)
    assert key != checks.stable_key(DOC, SENTENCE.replace("절반", "3분의 1"), 4)


def test_stable_key_does_not_join_spaces_that_split_words() -> None:
    """접기는 공백을 지우지 않는다 — 띄어쓰기만 다른 다른 문장(「재생 에너지」 대 「재생에너지」)은 다른 열쇠다."""
    assert checks.stable_key(DOC, SENTENCE, 4) != checks.stable_key(
        DOC, SENTENCE.replace("재생에너지", "재생 에너지"), 4
    )
