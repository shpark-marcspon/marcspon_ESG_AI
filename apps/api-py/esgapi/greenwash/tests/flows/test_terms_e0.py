"""판 대상 단어의 받기·켠 낱말·빈도 목록 합·sha(flows/terms_e0 — 밴드 G2d K6, 순수 층). 경로 쪽 400·422 는
tests/service/apis/test_ai_settings_terms.py.

낱말은 지어낸 것(「초록마루」 등)과 기본 목록(GREEN_TERMS)의 것이다.
"""

import hashlib
import json

import pytest

from esgapi.greenwash.engines.e0.gw1 import GREEN_TERMS, frequency_extras
from esgapi.greenwash.flows import colab_e0, terms_e0
from esgapi.greenwash.flows.terms_e0 import AcceptedTerms, TermsRefused, accept_terms


def pairs(*texts: str, off: tuple[int, ...] = ()) -> list[dict[str, object]]:
    return [{"text": t, "enabled": i not in off} for i, t in enumerate(texts)]


def accepted(given: object) -> AcceptedTerms:
    found = accept_terms(given)
    assert isinstance(found, AcceptedTerms), found
    return found


def refused(given: object) -> tuple[str, str]:
    found = accept_terms(given)
    assert isinstance(found, TermsRefused), found
    assert found.code == "TERMS_TEXT" or found.message == terms_e0.MESSAGES[found.code]  # 글 규칙 넷은 문장이 넷
    return found.code, found.field


def test_accepted_terms_are_stripped_and_kept_in_order() -> None:
    found = accepted(pairs("  초록마루 ", "친환경", "\t녹색", off=(1,)))
    assert terms_e0.terms_input(found) == [
        {"text": "초록마루", "enabled": True},
        {"text": "친환경", "enabled": False},
        {"text": "녹색", "enabled": True},
    ]
    assert terms_e0.used_terms(found) == ("초록마루", "녹색")


def test_the_default_list_is_accepted_as_it_is() -> None:
    found = accepted(pairs(*GREEN_TERMS))
    assert terms_e0.used_terms(found) == tuple(GREEN_TERMS) and len(GREEN_TERMS) == 37


@pytest.mark.parametrize(
    ("text", "message"),
    [
        pytest.param("", "TERMS_TEXT_LENGTH", id="empty"),
        pytest.param("   ", "TERMS_TEXT_LENGTH", id="blank"),
        pytest.param("가" * 31, "TERMS_TEXT_LENGTH", id="31"),
        pytest.param("녹색(가상)", "TERMS_TEXT_BRACKET", id="bracket"),
        pytest.param("「녹색」'", "TERMS_TEXT_BRACKET", id="quote"),
        pytest.param(".", "TERMS_TEXT_NO_LETTER", id="dot"),
        pytest.param("-", "TERMS_TEXT_NO_LETTER", id="dash"),
        pytest.param("녹\x00색", "TERMS_TEXT_INVISIBLE", id="nul"),
        pytest.param("녹\ud800색", "TERMS_TEXT_INVISIBLE", id="lone-surrogate"),
        pytest.param("녹\u0007색", "TERMS_TEXT_INVISIBLE", id="bell"),
        pytest.param("녹​색", "TERMS_TEXT_INVISIBLE", id="zero-width"),
        pytest.param("녹\n색", "TERMS_TEXT_INVISIBLE", id="newline"),
    ],
)
def test_a_bad_text_is_terms_text_at_its_index(text: str, message: str) -> None:
    found = accept_terms(pairs("친환경", text))
    assert isinstance(found, TermsRefused)
    assert (found.code, found.field, found.message) == ("TERMS_TEXT", "terms.1.text", terms_e0.MESSAGES[message])


def test_thirty_characters_are_fine() -> None:
    assert terms_e0.used_terms(accepted(pairs("가" * 30))) == ("가" * 30,)


def test_a_key_duplicate_points_at_the_later_one() -> None:
    assert refused(pairs("친환경", "탄소 중립", "녹색", "탄소중립")) == ("TERMS_DUPLICATE", "terms.3.text")
    assert refused(pairs("Eco", "eco", off=(0,))) == ("TERMS_DUPLICATE", "terms.1.text")  # 끈 것도 겹침


def test_the_count_includes_disabled_terms() -> None:
    words = [f"지어낸낱말{i}" for i in range(101)]
    assert refused(pairs(*words, off=tuple(range(60, 101)))) == ("TERMS_COUNT", "terms")
    assert len(accepted(pairs(*words[:100], off=tuple(range(60, 100)))).terms) == 100  # 분모: 100 은 된다


def test_none_enabled_is_refused() -> None:
    assert refused(pairs("친환경", "녹색", off=(0, 1))) == ("TERMS_NONE_ENABLED", "terms")


def test_the_order_is_text_then_duplicate_then_count_then_enabled() -> None:
    words = [f"지어낸낱말{i}" for i in range(101)]
    assert refused(pairs(*words, "지어낸낱말0", "(", off=tuple(range(102))))[0] == "TERMS_TEXT"
    assert refused(pairs(*words, "지어낸낱말0", off=tuple(range(102))))[0] == "TERMS_DUPLICATE"
    assert refused(pairs(*words, off=tuple(range(101))))[0] == "TERMS_COUNT"


@pytest.mark.parametrize(
    "given",
    [
        pytest.param("친환경", id="string"),
        pytest.param(None, id="none"),
        pytest.param([{"text": "친환경"}], id="no-enabled"),
        pytest.param([{"text": "친환경", "enabled": 1}], id="int-enabled"),
        pytest.param([{"text": 3, "enabled": True}], id="int-text"),
        pytest.param([{"text": "친환경", "enabled": True, "more": 1}], id="unknown-key"),
        pytest.param(["친환경"], id="plain-list"),
    ],
)
def test_a_wrong_shape_is_refused_as_a_value(given: object) -> None:
    assert refused(given) == ("TERMS_SHAPE", "terms")


def test_the_refused_characters_are_the_extra_terms_ones() -> None:
    assert terms_e0.TERM_REFUSED.pattern == colab_e0.EXTRA_TERM_REFUSED.pattern
    assert terms_e0.TERM_CHARS == colab_e0.EXTRA_TERM_CHARS


def test_extras_beyond_the_default_list_is_frequency_extras() -> None:
    extra = ("초록마루", "탄소 중립", "ECO", "eco프리", "녹색", "가상낱말")
    assert terms_e0.extras_beyond(GREEN_TERMS, extra) == frequency_extras(extra)
    assert terms_e0.extras_beyond(("초록마루",), extra) == ["탄소 중립", "ECO", "eco프리", "녹색", "가상낱말"]


def test_the_sha_is_the_compact_json_of_the_used_list() -> None:
    used = ("초록마루", "탄소 중립")
    text = '["초록마루","탄소 중립"]'
    assert terms_e0.terms_sha256(used) == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert json.dumps(list(used), ensure_ascii=False, separators=(",", ":")) == text
    assert terms_e0.terms_sha256(used) != terms_e0.terms_sha256(tuple(reversed(used)))  # 차례도 sha 에 든다
