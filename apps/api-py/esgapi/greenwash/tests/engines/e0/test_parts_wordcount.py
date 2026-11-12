# pyright: basic, reportArgumentType=false
# ↑ GW1 테스트의 사본(import 경로만 바꿈). 타입 표기 없는 GW1 의 꼴 그대로라 strict 를 끈다.
#   일부러 틀린 꼴을 넣는 테스트가 있어 인자 꼴 검사도 끈다.
"""셀 16·19(쪽 입력, 파트별 묶기)와 셀 22·24(낱말 세기)."""

import pytest

from esgapi.greenwash.engines.e0 import wordcount as w
from esgapi.greenwash.engines.e0.parts import (
    _clip_pages_to_doc_range,
    build_results_by_part,
    build_section_pages,
    parse_pages,
)
from esgapi.greenwash.engines.e0.result import item_json
from esgapi.greenwash.tests.conftest import make_docs


@pytest.mark.parametrize(
    "given, want",
    [
        ("5", [5]),
        ("6~14", list(range(6, 15))),
        ("25-37,55~74", list(range(25, 38)) + list(range(55, 75))),
        ("9~7", [7, 8, 9]),  # 거꾸로 된 범위
        ("3,3, 4", [3, 4]),
        ("", []),
        (None, []),
        ("x, 2, a~b, 1~", [2]),
        ("3.5", []),
        ("-3", []),  # 하이픈이 물결로 바뀌어 `~3` 이 되고 버려진다
        ([3, "4", "x", 3], [3, 4]),
    ],
)
def test_parse_pages(given, want):
    assert parse_pages(given) == want


def test_parse_pages_rejects_other_types_and_clip_keeps_document_range():
    with pytest.raises(ValueError):
        parse_pages(3)
    assert _clip_pages_to_doc_range([0, 1, 4, 5, 4, "2", "x"], 4) == [1, 2, 4]
    assert _clip_pages_to_doc_range([1, 2], 0) == []


def test_page_in_two_parts_puts_the_result_in_both():
    # 흠 13
    section_pages, manual_pages = build_section_pages("1~2", "2", "2~3, 99", 3)
    assert section_pages == {"CEO 메시지": [1, 2], "회사소개": [2], "기후/환경 토픽": [2, 3]}
    assert manual_pages == [1, 2, 3]
    r = {"page": 2, "sentence": "문장", "level": "High", "fix_paragraph": "수정", "fix": "수정", "action": "수정"}
    by_part = build_results_by_part([r], section_pages)
    assert [len(v) for v in by_part.values()] == [1, 1, 1]
    item = item_json(r, section_pages)
    assert item["parts"] == ["CEO 메시지", "회사소개", "기후/환경 토픽"]
    assert item["span"] is None and "fix" not in item and "action" not in item


def count(text):
    return dict(w.count_green_terms_in_text(text, w.GREEN_TERMS))


def test_missing_commas_glue_six_terms_into_three():
    # 흠 11: 쉼표가 빠진 세 곳.
    for glued in ("eco프리", "유기농자연친화", "동물보호청정기술"):
        assert glued in w.GREEN_TERMS
    for lost in ("eco", "프리", "유기농", "자연친화", "동물보호", "청정기술"):
        assert lost not in w.GREEN_TERMS
    assert len(w.GREEN_TERMS) == 37
    assert count("eco프리 라인과 유기농자연친화 원료, 동물보호청정기술") == {
        "eco프리": 1,
        "유기농자연친화": 1,
        "동물보호청정기술": 1,
    }
    assert count("eco 라인과 플라스틱 프리, 유기농 원료, 자연친화 설계, 동물보호, 청정기술") == {}


def test_short_terms_need_a_boundary_so_particles_hide_them():
    assert count("친환경 제품") == {"친환경": 1}
    assert count("(친환경)") == {"친환경": 1}
    assert count("친환경을 향해, 친환경적 설계, 초저탄소") == {}  # 조사·접사가 붙으면 세지 않는다
    assert count("최고 수준") == {"최고": 1}
    assert count("최고의 품질, 세계최고") == {}
    assert count("그린워싱, 바이오매스, biology") == {}
    assert count("bio-기반 원료") == {"bio": 1}


def test_long_terms_have_no_boundary_and_spacing_bends_only_inside_spaced_terms():
    assert count("탄소중립을 선언") == {"탄소중립": 1}
    assert count("탄소 중립을 선언") == {}  # 낱말에 띄어쓰기가 없으면 띄어 쓴 꼴은 세지 않는다
    assert count("플라스틱중립, 플라스틱 중립, 플라스틱  중립") == {"플라스틱 중립": 3}
    assert count("freedom") == {"free": 1}
    assert count("Net-Zero 와 GREEN") == {"zero": 1, "green": 1}  # 소문자로, 하이픈은 공백으로


def test_exclude_patterns_mask_two_phrases():
    assert w.DEFAULT_EXCLUDE_PATTERNS == [r"공기\s*청정\s*기", r"정수\s*기"]
    assert w.mask_excluded_phrases("공기 청정 기 와 정수기 와 청정에너지") == "와 와 청정에너지"
    assert count("공기청정기술 청정에너지") == {"청정에너지": 1}
    assert count("청정에너지") == {"청정에너지": 1}


def test_count_in_docs_gives_total_and_pages_with_hits_only():
    docs = make_docs(["친환경 제품과 green 전력", "아무 낱말도 없는 쪽", "친환경 설비"])
    total, per_page = w.count_green_terms_in_docs(docs, w.GREEN_TERMS)
    assert dict(total) == {"친환경": 2, "green": 1}
    assert [(p, dict(c)) for p, c in per_page] == [(1, {"친환경": 1, "green": 1}), (3, {"친환경": 1})]
