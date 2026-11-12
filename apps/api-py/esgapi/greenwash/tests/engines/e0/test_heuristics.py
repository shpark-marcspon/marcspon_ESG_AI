# pyright: basic
# ↑ GW1 테스트의 사본(import 경로만 바꿈). 타입 표기 없는 GW1 의 꼴 그대로라 strict 를 끈다.
"""셀 14 의 0~4절: 쪽 글, 문장 가르기, 규칙 후보, 환경 낱말, 거르기, Low 판정, JSON 구제, 폴백 문구."""

from esgapi.greenwash.engines.e0 import heuristics as h
from esgapi.greenwash.tests.conftest import LOW, NONLOW, make_docs

NOTICE = "\n...\n(이 페이지 텍스트는 일부만 잘라서 제공되었습니다.)"


def test_page_text_is_cut_at_limit_with_notice():
    doc = make_docs(["가" * 3000])[0]
    out = h.get_page_text(doc, 2500)
    assert out == "가" * 2500 + NOTICE
    assert h.get_page_text(make_docs(["가" * 2500])[0], 2500) == "가" * 2500


def test_page_text_joins_single_newlines_and_keeps_paragraphs():
    doc = make_docs(["  첫 줄\n둘째 줄 끝\n\n\n\n다음 문단\t끝  "])[0]
    assert h.get_page_text(doc, 2500) == "첫 줄 둘째 줄 끝\n\n다음 문단 끝"


def test_split_sentences_cuts_after_marks_and_endings():
    text = "하나입니다 둘이다 셋? 넷! 다섯. 여섯"
    assert h.split_sentences_kor(text) == ["하나입니다", "둘이다", "셋?", "넷!", "다섯.", "여섯"]
    assert h.split_sentences_kor("   ") == []
    # 「다 」 뒤에서는 어디서나 끊긴다(낱말 가운데라도).
    assert h.split_sentences_kor("바다 건너 갑니다.") == ["바다", "건너 갑니다."]


def test_rule_candidates_need_env_word_and_will_phrase_and_stop_at_max():
    text = " ".join(
        [
            LOW[0],
            "매출을 확대해 나가겠습니다.",
            NONLOW[0],
            LOW[1],
            "폐기물 감축에 기여하고자 합니다.",
            "용수 절감을 지향합니다.",
        ]
    )
    got = [c["sentence"] for c in h.collect_rule_based_declaratives(text, max_n=3)]
    assert got == [LOW[0], LOW[1], "폐기물 감축에 기여하고자 합니다."]
    assert len(h.collect_rule_based_declaratives(text, max_n=5)) == 4


def test_env_words_have_no_boundary():
    # 흠 5: `rec`, `ets`, `배출`, `전력` 은 낱말 가운데에서도 걸린다.
    assert h.has_env_signal("We work directly with markets.")
    assert h.has_env_signal("전력을 다해 고객을 모십니다.")
    assert h.has_env_signal("인재를 배출했습니다.")
    assert not h.has_env_signal("고객과 함께 성장합니다.")
    assert not h.has_env_signal("환경 경영을 합니다.")


def test_set_env_keywords_is_a_process_global():
    try:
        h.set_env_keywords(extra_keywords=["고객"], include_general_env=True)
        assert h.has_env_signal("고객과 함께 성장합니다.")
        assert h.has_env_signal("환경 경영을 합니다.")
    finally:
        h.set_env_keywords()
    assert not h.has_env_signal("고객과 함께 성장합니다.")


def test_hard_label():
    assert h.is_hard_label("")
    assert h.is_hard_label("짧은 문장입니다.")  # 15자 미만
    assert h.is_hard_label("표 3 온실가스 배출량의 추이를 보여 줍니다.")
    assert h.is_hard_label("목차 온실가스 배출량과 감축 목표와 이행")
    assert h.is_hard_label("온실가스 감축 목표의 단계별 이행 체계 수립")  # 끝맺음 없음, 40자 미만, 명사로 끝남
    assert not h.is_hard_label("온실가스 감축 목표의 단계별 이행 체계를 세웠습니다.")


def test_promo_and_table_like():
    assert h.is_promo_like("혁신과 도전으로 미래 가치를 창출하겠습니다.")
    assert not h.is_promo_like("혁신으로 온실가스를 줄이겠습니다.")  # 환경 낱말이 있으면 홍보가 아니다
    assert h.is_table_like("구분 | 2023 | 2024")
    assert h.is_table_like("전력 12,300 11,800 11,200 10,900 10,400 9,900 9,500")  # 숫자가 4분의 1 이상
    assert h.is_table_like("감축률 12%% 달성")  # 단위가 잇달아 둘
    assert not h.is_table_like(NONLOW[0])


def test_low_declarative_rules():
    assert h.is_low_declarative(LOW[0])
    assert not h.is_low_declarative("매출을 확대해 나가겠습니다.")  # 환경 낱말 없음
    assert not h.is_low_declarative("재생에너지 사용을 30% 확대해 나가겠습니다.")  # 숫자
    assert not h.is_low_declarative("제3자 검증을 받은 재생에너지를 확대해 나가겠습니다.")  # 숫자·검증
    assert not h.is_low_declarative("인증 받은 재생에너지를 확대해 나가겠습니다.")
    assert not h.is_low_declarative("검증 받은 재생에너지를 확대해 나가겠습니다.")
    assert not h.is_low_declarative("원단위 기준의 재생에너지를 확대해 나가겠습니다.")
    assert not h.is_low_declarative("감축 계획을 수립하였고 온실가스 감축을 추진해 나가겠습니다.")  # 사실 시제
    assert not h.is_low_declarative("재생에너지를 사용했습니다.")  # 의지 표현 없음


def test_quality_score():
    assert h.sentence_quality_score_kor("") == 0.0
    assert h.sentence_quality_score_kor("온실가스 감축 목표를 세우고 이행 상황을 공개하고 있습니다.") == 0.7
    assert h.sentence_quality_score_kor("짧은 글") == 0.0
    assert h.sentence_quality_score_kor("Scope 1 emissions were reduced across all sites") == 0.0


def test_json_salvage_tries_array_before_object():
    # 흠 8: `[`…`]` 를 먼저 본다.
    assert h._json_loads_safe('{"a": 1}') == {"a": 1}
    assert h._json_loads_safe('결과: [{"sentence": "가"}] 끝') == [{"sentence": "가"}]
    assert h._json_loads_safe('결과: {"a": 1} 끝') == {"a": 1}
    fenced = '```json\n{"decision": "High", "risk_tags": ["가", "나"]}\n```'
    assert h._json_loads_safe(fenced) == ["가", "나"]  # dict 가 아니라 안쪽 배열이 잡힌다
    assert (
        h._json_loads_safe('말 {"decision": "High", "tags": ["가"], "more": ["나"]} 말') is None
    )  # `["가"], "more": ["나"]` 는 JSON 이 아니다
    assert h._json_loads_safe("JSON 이 아님") is None
    assert h._json_loads_safe("") is None


def test_as_str_list_and_polite_ending():
    assert h._as_str_list(["가", " ", 3, None, "나"], 3) == ["가", "3", "None"]
    assert h._as_str_list("글자열", 3) == []
    assert h._ensure_polite_ending("밝혀야 합니다.") == "밝혀야 합니다."
    assert h._ensure_polite_ending("밝혀야 합니다") == "밝혀야 합니다."
    assert h._ensure_polite_ending("밝혀야 함") == "밝혀야 함. 추가 보완이 필요합니다."
    assert h._ensure_polite_ending("좋다.") == "좋다. 추가 보완이 필요합니다."
    assert h._ensure_polite_ending("  ") == ""


def test_fallback_fix_paragraph_by_missing_fields():
    default = h._fallback_fix_paragraph([])
    assert default.startswith("해당 주장(성과/목표/효과)의 대상 범위와 기간을 먼저 명확히 해야 합니다.")
    assert default.endswith("구분 표기하는 것이 필요합니다.")
    scoped = h._fallback_fix_paragraph(["범위/경계", "산정 방법"])
    assert (
        "적용 범위(조직·사업·제품·지역·Scope" in scoped
        and "산정 방식(데이터 출처" in scoped
        and "용어의 정의" not in scoped
    )


def test_cap_text():
    assert h.cap_text("  가나다  ", 10) == "가나다"
    assert h.cap_text("가" * 12, 10) == "가" * 10 + "\n...(truncated)"
    assert h.cap_evidence_context("나" * 1601) == "나" * 1600 + "\n...(truncated)"
