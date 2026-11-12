"""glossary.py(코랩 셀 14·15·57) — 손으로 지은 기대값(발주서 §3 S1·S9). 용어는 지어낸 것."""

from hypothesis import given
from hypothesis import strategies as st

from esgapi.translation.engines.colab_158.glossary import (
    GlossaryMiss,
    build_glossary_text,
    build_relevant_glossary,
    find_deterministic_glossary_violations,
    fold_glossary,
    glossary_check,
    target_term_present,
)


def test_folding_keeps_the_base_position_and_the_final_value() -> None:
    """S9 — `{**GLOSSARY, **FINAL_GLOSSARY}`(R/368-372): 같은 key 는 자리 base·값 final, 목록 안은 뒤 값."""
    base = [("가상사업장", "Virtual Site"), ("가상", "Virtual"), ("사업", "Business"), ("가상", "Imaginary")]
    final = [("신규", "New"), ("가상사업장", "Virtual Business Site")]
    folded = fold_glossary(base, final)
    assert list(folded.items()) == [
        ("가상사업장", "Virtual Business Site"),
        ("가상", "Imaginary"),
        ("사업", "Business"),
        ("신규", "New"),
    ]
    assert list(folded.items()) == list({**dict(base), **dict(final)}.items())


@given(
    st.lists(st.tuples(st.sampled_from(["가", "나", "다", "가나", "나다"]), st.text(max_size=3)), max_size=6),
    st.lists(st.tuples(st.sampled_from(["가", "나", "라", "가나", "라마"]), st.text(max_size=3)), max_size=6),
)
def test_folding_is_the_dict_unpacking(base: list[tuple[str, str]], final: list[tuple[str, str]]) -> None:
    """S9 성질: 같은 key·같은 길이 key 를 섞어도 차례·값이 `{**dict(A), **dict(B)}` 와 같다."""
    assert list(fold_glossary(base, final).items()) == list({**dict(base), **dict(final)}.items())


def test_relevant_glossary_is_exact_matches_sorted_by_key_length_stably() -> None:
    """R/469-484·487-498: 원문에 key 가 그대로 나온 짝만, 길이 내림차순 — 같은 길이는 넣은 차례."""
    glossary = {"가상": "Virtual", "사업장": "Site", "가상사업장": "Virtual Site", "부서": "Dept", "온실": "GH"}
    relevant = build_relevant_glossary(glossary, "가상사업장의 온실가스")
    assert list(relevant) == ["가상사업장", "사업장", "가상", "온실"]
    assert (
        build_glossary_text(relevant)
        == "- 가상사업장 -> Virtual Site\n- 사업장 -> Site\n- 가상 -> Virtual\n- 온실 -> GH"
    )
    assert build_glossary_text({}) == "(No relevant glossary terms for this source text.)"
    assert build_relevant_glossary({}, "가상") == {}


def test_target_term_present_allows_case_and_spacing_only() -> None:
    """R/445-466."""
    assert target_term_present("Virtual Site", "the virtual\n  site plan")
    assert not target_term_present("Virtual Site", "Virtual-Site")
    assert target_term_present("Board’s “Office” – A", 'board\'s "office" - a')
    assert target_term_present("A​B", "ab")
    assert target_term_present("", "anything")
    assert not target_term_present("Virtual Site", "")


def test_deterministic_violations_have_the_colab_wording() -> None:
    """R/501-527."""
    glossary = {"현황": "Overview", "가상사업장": "Virtual Business Site", "부서": "Dept"}
    issues = find_deterministic_glossary_violations("가상사업장 현황", "Virtual site overview", glossary)
    assert issues == [
        {
            "issue_type": "GLOSSARY_VIOLATION",
            "severity": "HIGH",
            "original_span": "",
            "suggestion": "'가상사업장'는 용어집에 따라 'Virtual Business Site'로 그대로 통일하는 것이 좋습니다.",
            "reason": "원문에 용어집 용어 '가상사업장'가 정확히 등장하지만, "
            "번역문에서 지정 번역어 'Virtual Business Site'가 "
            "확인되지 않았습니다. 용어집 value는 대소문자와 줄바꿈/공백 차이를 제외하고 그대로 반영되어야 합니다.",
        }
    ]


def test_glossary_check_walks_every_source_page() -> None:
    """셀 57(R/4975-5019)의 반영 검사: 받은 원문 쪽마다(번역에 없는 쪽은 빈 글로) 미반영을 센다. 쪽 범위 거름·같은 번호
    합침은 부르는 쪽(pipeline)이 한 map 으로 준다(MARC-ENT-451)."""
    glossary = {"가상사업장": "Virtual Business Site", "사업장": "Site Office", "현황": "Overview"}
    source = {1: "[PAGE 1]\n가상사업장 가상사업장", 2: "[PAGE 2]\n현황"}
    translated = {1: "[PAGE 1]\nVirtual Business Site"}
    assert glossary_check(source, translated, glossary) == [
        GlossaryMiss(1, "사업장", "Site Office", 2),
        GlossaryMiss(2, "현황", "Overview", 1),
    ]


def test_glossary_check_keeps_a_real_miss_with_its_source_count() -> None:
    """T3(MARC-ENT-451): 범위 안 쪽에 용어가 있고 번역 어느 조각에도 영문이 없으면 미반영 하나, source_count 는 그 쪽의
    나온 횟수."""
    glossary = {"가상설비": "Virtual Facility"}
    source = {2: "[PAGE 2]\n가상설비 점검\n\n가상설비 교체"}
    translated = {2: "[PAGE 2]\nInspection\n\nReplacement"}
    assert glossary_check(source, translated, glossary) == [GlossaryMiss(2, "가상설비", "Virtual Facility", 2)]
