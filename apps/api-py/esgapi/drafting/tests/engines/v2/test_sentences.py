"""문장 나누기 drafting-sentences@1(engines/v2/sentences.py — RP2b B2). 순수 층. 글은 지어낸 것이다."""

import pytest

from esgapi.drafting.engines.v2 import sentences
from esgapi.drafting.engines.v2.sentences import Span


def cut(text: str) -> list[str]:
    return list(sentences.pieces(text, sentences.split(text)))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2024. 12. 31. 기준", ["2024. 12. 31. 기준"]),  # 날짜
        ("1. 개요", ["1. 개요"]),  # 줄 머리 번호
        ("줄였다.” 다음", ["줄였다.”", "다음"]),  # 닫는 따옴표 뒤
        ("줄였다.) 다음", ["줄였다.)", "다음"]),  # 닫는 괄호 뒤
        ("등… 다음", ["등… 다음"]),  # 줄임표
        ("No. 3", ["No. 3"]),  # 약어
        ("3.5% 줄었다.", ["3.5% 줄었다."]),  # 소수점 · 끝
        ("약 1.2억 원. 다음", ["약 1.2억 원.", "다음"]),
        ("e.g. 다음", ["e.g. 다음"]),  # 영문 약어
        ("(주)가 밝혔다.", ["(주)가 밝혔다."]),
    ],
)
def test_the_exception_table_of_the_order(text: str, expected: list[str]) -> None:
    assert cut(text) == expected


def test_a_lone_line_break_does_not_split_but_an_end_mark_before_it_does() -> None:
    assert cut("가상 사업장은 물 사용량을\n줄였다. 다음 해에도\n이어 간다") == [
        "가상 사업장은 물 사용량을\n줄였다.",
        "다음 해에도\n이어 간다",
    ]
    assert cut("물음인가? 그렇다! 끝。 다음") == ["물음인가?", "그렇다!", "끝。", "다음"]
    assert cut("끝.\n다음") == ["끝.", "다음"]
    assert cut("붙은점.다음") == ["붙은점.다음"]  # 뒤가 공백이 아니면 안 나눔


def test_numbers_start_at_zero_and_spans_skip_outer_spaces() -> None:
    found = sentences.split("  첫 문장.   둘째 문장.  ")
    assert found == (Span(2, 7), Span(10, 16))  # 「첫 문장.」 5 자리 · 공백 셋 · 「둘째 문장.」 6 자리
    assert found[0].start == 2  # 번호 0 = 첫 문장(앞 공백은 범위 밖)
    assert sentences.split("") == () and sentences.split("  \n ") == ()


def test_spans_are_utf16_units_around_supplementary_plane_characters() -> None:
    text = "𝟙 가. 나"  # 𝟙 = U+1D7D9 — UTF-16 두 자리
    assert sentences.split(text) == (Span(0, 5), Span(6, 7))
    assert cut(text) == ["𝟙 가.", "나"]
    assert sentences.split("가. 𝟙𝟙. 나") == (Span(0, 2), Span(3, 8), Span(9, 10))


def test_same_text_same_spans() -> None:
    text = "가상 회사는 1,200 톤을 줄였다. 목표는 2030년이다. 그 밖은 없다."
    assert sentences.split(text) == sentences.split(text)
    assert len(sentences.split(text)) == 3
    assert sentences.SEGMENTER == "drafting-sentences@1"
