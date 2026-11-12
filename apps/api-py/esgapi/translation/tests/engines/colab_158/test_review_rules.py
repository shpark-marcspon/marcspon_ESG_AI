"""review_rules.py(코랩 셀 58·65·67 의 결정적 몫) — 손으로 지은 기대값(발주서 §3 S1 의 sanitize_issues 등)."""

import pytest

from esgapi.translation.engines.colab_158 import review_rules as rr

TRANSLATED = "[PAGE 1]\nABC Corp manages Virtual Site emissions."
GLOSSARY = {"가상사업장": "Virtual Site"}


def test_sanitize_issues() -> None:
    """R/5190-5260: 허용 유형만, 번역문에 없는 구간은 빈 글로, 구간과 같은 제안·용어집 value 를 바꾸는 제안·영문 「원문
    없음」 단독 이유·일관성 낱말 없는 TERMINOLOGY_INCONSISTENCY·겹침은 버린다."""
    keep_first = {
        "issue_type": "unnatural",
        "severity": "low",
        "original_span": "manages Virtual Site emissions",
        "suggestion": "oversees Virtual Site emissions",
        "reason": "가상 이유",
    }
    issues: list[object] = [
        keep_first,
        {"issue_type": "ADDITION", "suggestion": "x"},
        {"issue_type": "GRAMMAR", "original_span": "not in text", "suggestion": "x", "reason": "y"},
        {"issue_type": "UNNATURAL", "original_span": "ABC Corp", "suggestion": "abc  corp", "reason": "r"},
        {
            "issue_type": "UNNATURAL",
            "original_span": "manages Virtual Site emissions",
            "suggestion": "manages site",
            "reason": "r",
        },
        {"issue_type": "UNNATURAL", "suggestion": "Remove it", "reason": "unsupported addition"},
        {"issue_type": "UNNATURAL", "suggestion": "Remove it", "reason": "원문에 없는 표현"},
        {"issue_type": "TERMINOLOGY_INCONSISTENCY", "suggestion": "Use Site", "reason": "terms differ"},
        {"issue_type": "TERMINOLOGY_INCONSISTENCY", "suggestion": "Use Site", "reason": "inconsistent terms"},
        dict(keep_first),
        "not a dict",
    ]
    assert rr.sanitize_issues(issues, TRANSLATED, relevant_glossary=GLOSSARY) == [
        {
            "issue_type": "UNNATURAL",
            "severity": "LOW",
            "original_span": "manages Virtual Site emissions",
            "suggestion": "oversees Virtual Site emissions",
            "reason": "가상 이유",
        },
        {"issue_type": "GRAMMAR", "severity": "MEDIUM", "original_span": "", "suggestion": "x", "reason": "y"},
        # 국문 「원문에 없」 이유는 숫자·단위 정규식의 「원」에 걸려 버려지지 않는다(코랩도 이렇다 — R/5111)
        {
            "issue_type": "UNNATURAL",
            "severity": "MEDIUM",
            "original_span": "",
            "suggestion": "Remove it",
            "reason": "원문에 없는 표현",
        },
        {
            "issue_type": "TERMINOLOGY_INCONSISTENCY",
            "severity": "MEDIUM",
            "original_span": "",
            "suggestion": "Use Site",
            "reason": "inconsistent terms",
        },
    ]


def test_sanitize_issues_walks_whatever_json_came_back() -> None:
    """코랩은 `for issue in issues` — dict 는 키, 글자는 글자를 돌아 다 걸러지고, 수·null 은 TypeError, 글자 아닌 값에
    `.strip()` 은 AttributeError(셀이 멈춘다)."""
    assert rr.sanitize_issues({"a": 1}, TRANSLATED) == []
    assert rr.sanitize_issues("abc", TRANSLATED) == []
    with pytest.raises(TypeError):
        rr.sanitize_issues(5, TRANSLATED)
    with pytest.raises(TypeError):
        rr.sanitize_issues(None, TRANSLATED)
    with pytest.raises(AttributeError):
        rr.sanitize_issues([{"issue_type": 5}], TRANSLATED)


def test_review_raw_cleaning_and_parsing() -> None:
    """R/5332-5340: 울타리를 걷고 json.loads, 못 읽으면 이슈 0(W8)."""
    assert rr.clean_review_raw("  ```json\n[]\n```  ") == "[]"
    assert rr.parse_review_json("[]") == ([], True)
    assert rr.parse_review_json("not json") == ([], False)
    assert rr.parse_review_json('{"issues": []}') == ({"issues": []}, True)


def test_merge_review_issues_puts_glossary_rule_first() -> None:
    det = [
        {"issue_type": "GLOSSARY_VIOLATION", "severity": "HIGH", "original_span": "", "suggestion": "s", "reason": "r"}
    ]
    llm = [
        dict(det[0]),
        {"issue_type": "GRAMMAR", "severity": "LOW", "original_span": "", "suggestion": "t", "reason": "u"},
    ]
    merged = rr.merge_review_issues(det, llm)
    assert [(i["issue_type"], source) for i, source in merged] == [
        ("GLOSSARY_VIOLATION", "glossary_rule"),
        ("GRAMMAR", "model"),
    ]
    assert rr.severity_counts([i for i, _ in merged] + [{"severity": "CRITICAL"}]) == (1, 0, 1)


def test_bilingual_annotation_helpers() -> None:
    assert rr.strip_korean_bilingual_annotations("Title (제목)\nBody (2025)\n가상 줄") == "Title\nBody (2025)\n가상 줄"
    assert rr.extract_bilingual_korean_annotations("A (가 나) B (가  나) C (다)") == ["가 나", "다"]


def test_page_content_selection() -> None:
    """R/6099-6169: 병기가 국문 원문처럼 보이면(한글 30자 이상이고 라틴 1.3배·20 보다 많음) raw 영문."""
    korean = "[PAGE 1]\n" + "가" * 30
    assert rr.looks_like_korean_source_for_qa(korean)
    assert not rr.looks_like_korean_source_for_qa("가" * 30 + "a" * 30)
    assert rr.select_review_translation_content(1, {1: korean}, {1: " [PAGE 1]\nEnglish "}) == "[PAGE 1]\nEnglish"
    assert rr.select_review_translation_content(1, {1: "[PAGE 1]\nTitle (제목)"}, {1: "x"}) == "[PAGE 1]\nTitle (제목)"
    assert rr.select_display_translation_content(1, {}, {1: "[PAGE 1]\nTitle (제목)"}) == "[PAGE 1]\nTitle"


def test_llm_explanation_cleaning_and_page_extraction() -> None:
    """R/6405-6494."""
    text = (
        "[PAGE 1]\nHere is the corrected page:\nand the rest\nABC Corp grew.\n\n"
        "Note: x\nThe table header should be y\n- The Korean source shows z"
    )
    assert rr.clean_llm_explanation_lines(text) == "[PAGE 1]\nABC Corp grew."
    reply = "```text\nSure.\n[PAGE 2]\nFixed text.\n[PAGE 3]\nOther\n```"
    assert rr.extract_only_corrected_page_text(reply, 2) == "[PAGE 2]\nFixed text."
    assert rr.ensure_page_tag("Fixed", 4) == "[PAGE 4]\nFixed"
    assert rr.ensure_page_tag("[PAGE 9]\nFixed", 4) == "[PAGE 4]\nFixed"


def test_autofix_issue_filters_and_span_replacements() -> None:
    """R/6535-6644."""
    issues: list[object] = [
        {"issue_type": "grammar", "suggestion": "We grow", "original_span": "We grows"},
        {"issue_type": "ADDITION", "suggestion": "x"},
        {"issue_type": "OMISSION"},
        "s",
        {"issue_type": "UNNATURAL", "original_span": "x", "suggestion": "설명 한글"},
        {"issue_type": "UNNATURAL", "original_span": "We", "suggestion": "Here is fix"},
    ]
    actionable = rr.filter_actionable_issues(issues)
    assert [i["issue_type"] for i in actionable] == ["GRAMMAR", "UNNATURAL", "UNNATURAL"]
    fixed, applied = rr.simple_span_replacements("We grows. We grows.", actionable)
    assert fixed == "We grow. We grow."
    assert applied == [{"issue_type": "GRAMMAR", "original_span": "We grows", "suggestion": "We grow"}]
    assert rr.looks_like_explanation_or_bad_suggestion("")
    assert rr.looks_like_explanation_or_bad_suggestion("a" * 181)
    assert rr.looks_like_explanation_or_bad_suggestion("a\nb")
    assert not rr.looks_like_explanation_or_bad_suggestion("Fine text")
    assert rr.select_part_issues_for_page([], "page") == []
