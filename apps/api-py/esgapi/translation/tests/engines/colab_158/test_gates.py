"""gates.py(코랩 셀 46 의 결정적 판정) — 손으로 지은 기대값(발주서 §3 S1·S8 의 ⑧)."""

import pytest

from esgapi.translation.engines.colab_158 import gates


def test_constants_are_the_colab_defaults() -> None:
    """R/2125-2140·2282·3050-3051."""
    assert (
        gates.EDITORIAL_POLISH_MIN_CHARS,
        gates.EDITORIAL_POLISH_MAX_CHARS,
        gates.GENERIC_EDITORIAL_QA_MIN_SCORE,
        gates.MAX_UNTRANSLATED_REPAIR_ROUNDS,
        gates.TABLE_BATCH_SIZE,
        gates.EDITORIAL_POLISH_TEMPERATURE,
    ) == (120, 6000, 96, 2, 24, 0.2)


def test_untranslated_korean_lines() -> None:
    """R/3054-3086: 태그 줄·구분 줄은 빼고, 같은 줄은 한 번, 300자로 자르고, 40 줄까지."""
    text = "[BLOCK 1]\n가 나\nEnglish\n  가 나  \n| 한 | b |\n" + "다" * 310
    assert gates.collect_untranslated_korean_lines(text) == ["가 나", "| 한 | b |", "다" * 300]
    many = "\n".join(f"가{i}" for i in range(45))
    assert len(gates.collect_untranslated_korean_lines(many)) == 40


def test_structure_tag_signature_sees_blank_lines_next_to_tags() -> None:
    """R/2368-2374: 줄 끝 `\\s*$`·줄 앞 `^\\s*` 가 이웃 빈 줄을 먹는다 — 태그 사이 빈 줄이 바뀌어도 「태그가 바뀜」이다
    (코랩도 이렇다 — 윤문이 빈 줄만 바꿔도 원 번역을 유지한다)."""
    assert gates.structure_tag_signature("[PAGE 1]\n[CAPTION]\nx") == ["[PAGE 1]", "[CAPTION]"]
    assert gates.structure_tag_signature("[PAGE 1]\n\n[BLOCK 1]") == ["[PAGE 1]\n", "\n[BLOCK 1]"]
    assert gates.structure_tag_signature("[NOTES]\ntext [TABLE 1]") == []


def test_table_pipe_signature() -> None:
    assert gates.table_pipe_signature("| a | b |\n텍스트\n | c | d | e | ") == [3, 4]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Climate Action Strategy", True),  # 낱말 셋 다 대문자
        ("We are committed to change", False),  # 문장 시작
        ("short", False),  # 8자 미만
        ("Advancing low carbon goals", True),  # 동명사 제목
        ("기후 전략 (기후)", True),  # 국문 병기 제목
        ("A heading that ends.", False),  # 마침표
    ],
)
def test_heading_candidate(text: str, expected: bool) -> None:
    assert gates.looks_like_report_heading_candidate(text) is expected


def test_split_merged_heading_body_line() -> None:
    """R/2428-2460: 본문 시작 낱말 앞에서 제목·본문을 가른다."""
    line = "Climate Action Strategy The Company manages greenhouse gas emissions across all virtual sites."
    assert gates.split_merged_heading_body_line(line) == (
        "Climate Action Strategy\nThe Company manages greenhouse gas emissions across all virtual sites."
    )
    assert gates.split_merged_heading_body_line("Short line") == "Short line"


def test_names_removed_from_the_body_start_list_do_not_split() -> None:
    """처분 ⑧(S8): 갈래는 일반 낱말 열여덟뿐 — 본문이 그 밖의 고유 이름으로 시작하는 줄은 가르지 않는다. 원 정규식과
    갈라지는 경우(이름 아홉)는 「코랩과 다른 자리」 표와 TR1-o 의 차이 몫이다(이름을 시험에 적지 않는다)."""
    line = "Climate Action Strategy Acme expanded renewable energy use at every virtual site this year."
    assert gates.split_merged_heading_body_line(line) == line
    words = gates.BODY_START_RE.pattern.split("(?:")[1].split(")")[0].split("|")
    assert len(words) == 18


def test_fix_heading_body_merge_collapses_four_newlines() -> None:
    assert gates.fix_heading_body_merge("a\n\n\n\n\nb") == "a\n\n\nb"
    assert gates.fix_heading_body_merge("") == ""


def test_table_like_and_page_gate() -> None:
    """R/2554-2575."""
    assert gates.contains_table_like_text("[TABLE 1]\nx")
    assert gates.contains_table_like_text("[MARKDOWN_TABLE]")
    assert gates.contains_table_like_text("| a |\n| b |")
    assert not gates.contains_table_like_text("| a |\n텍스트")
    assert not gates.should_run_page_level_text_gate("가" * 119 + "   ")
    assert gates.should_run_page_level_text_gate("가 " * 120)
    assert not gates.should_run_page_level_text_gate("가" * 200 + "\n[TABLE 1]")


@pytest.mark.parametrize(
    ("score", "critical", "types", "count", "expected"),
    [
        (97, False, {"COLLOCATION"}, 1, False),  # 통과
        (96, False, set[str](), 0, False),  # 문턱과 같으면 통과(< 96 만 적용)
        (95, False, set[str](), 0, True),  # 문턱 아래
        (99, True, set[str](), 0, True),  # critical 칸
        (99, False, {"GRAMMAR"}, 1, True),  # critical 유형
        (94, False, {"FLOW", "TRANSLATIONESE"}, 2, True),  # soft 둘(이미 < 96 이라 늘 적용 — soft 절은 죽은 셈)
    ],
)
def test_must_apply(score: int, critical: bool, types: set[str], count: int, expected: bool) -> None:
    """R/2715-2733."""
    assert gates.must_apply(score, critical, types, count) is expected


def test_split_page_sections() -> None:
    """R/2938-2963: 꼭대기 태그마다 새 구획, CAPTION 은 꼭대기가 아니다, 태그 앞 글은 TEXT."""
    sections = gates.split_page_sections("머리\n[PAGE 1]\n[BLOCK 1]\n제목\n[TABLE 2] \n| a |\n[CAPTION]\n캡션")
    assert [(s.kind, s.lines) for s in sections] == [
        ("TEXT", ["머리"]),
        ("PAGE", ["[PAGE 1]"]),
        ("BLOCK", ["[BLOCK 1]", "제목"]),
        ("TABLE", ["[TABLE 2]", "| a |", "[CAPTION]", "캡션"]),
    ]


def test_format_glossary_violations_for_prompt() -> None:
    violation = {"suggestion": "'가상사업장'는 용어집에 따라 'Virtual Business Site'로 그대로 통일하는 것이 좋습니다."}
    assert gates.format_glossary_violations_for_prompt([violation]) == "- 가상사업장 -> Virtual Business Site"
    assert gates.format_glossary_violations_for_prompt([{"suggestion": "없음"}]) == "- 없음"
    assert gates.format_glossary_violations_for_prompt([]) == "(No glossary violations.)"
