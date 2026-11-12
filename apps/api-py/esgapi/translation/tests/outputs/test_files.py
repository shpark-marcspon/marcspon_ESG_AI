"""결과에서 지을 Word 고르기(발주서 §3 S6, 처분 ⑨): TR1a 의 예시 결과(`tests/data/examples/result-sample.json` — 고치지
않고 읽어 사본을 바꾼다)에서 코랩이 짓는 조건 그대로 고르는가.
"""

import copy
import io
import json
from pathlib import Path
from typing import Any

import docx
import pytest

from esgapi.translation.outputs.docx_qa import QaIssue, QaSection
from esgapi.translation.outputs.failures import WordFailed
from esgapi.translation.outputs.files import (
    BilingualSource,
    QaSource,
    SkippedWord,
    build_word_files,
    plan_word_files,
    qa_sections,
)

SAMPLE = Path(__file__).parents[1] / "data" / "examples" / "result-sample.json"


def sample() -> Any:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def two_variants() -> Any:
    result = sample()
    single = result["variants"][0]
    a, b = copy.deepcopy(single), copy.deepcopy(single)
    a["label"], b["label"] = "A", "B"
    result["variants"] = [a, b]
    return result


def kinds(plan_result: Any) -> list[tuple[str, str]]:
    return [(item.kind, item.variant) for item in plan_word_files(plan_result).planned]


def test_the_sample_is_what_this_test_assumes() -> None:
    """예시가 바뀌면 이 시험의 전제를 다시 본다: single 하나, 쪽 셋(reviewed·parse_failed·reviewed), 자동수정 done."""
    variant = sample()["variants"][0]
    assert variant["label"] == "single"
    assert [p["review"]["status"] for p in variant["pages"]] == ["reviewed", "parse_failed", "reviewed"]
    assert variant["autofix"]["status"] == "done"


def test_a_rejected_result_builds_nothing() -> None:
    result = sample()
    result["status"] = "rejected"
    result["variants"] = []
    assert plan_word_files(result).planned == ()
    assert plan_word_files(result).skipped == ()
    built = build_word_files(result)
    assert built.built == () and built.skipped == ()


def test_single_builds_all_three_and_parse_failed_pages_still_get_the_qa_word() -> None:
    plan = plan_word_files(sample())
    assert [(i.kind, i.variant) for i in plan.planned] == [
        ("bilingual", "single"),
        ("qa", "single"),
        ("autofix", "single"),
    ]
    assert plan.skipped == ()
    variant = sample()["variants"][0]
    bilingual, qa, autofix = (i.source for i in plan.planned)
    assert bilingual == BilingualSource(variant["bilingualText"])  # 셀 55
    assert autofix == BilingualSource(variant["autofix"]["bilingualText"])  # 셀 67
    assert isinstance(qa, QaSource)
    assert [s.page_num for s in qa.sections] == [1, 2, 3]
    assert qa.sections[0].content == variant["pages"][0]["translated"]  # display 글(셀 65 R/6269)


def test_a_and_b_follow_the_colab_cell_order() -> None:
    assert kinds(two_variants()) == [
        ("bilingual", "A"), ("bilingual", "B"), ("qa", "A"), ("qa", "B"), ("autofix", "A"), ("autofix", "B"),
    ]  # fmt: skip


@pytest.mark.parametrize("status", ["call_failed", "not_run"])
def test_a_stopped_review_skips_the_qa_word_with_its_reason(status: str) -> None:
    """코랩은 검수 LLM 호출이 실패하면 셀 65 가 멈춰 검수 Word 가 0 이다."""
    result = sample()
    page = result["variants"][0]["pages"][1]
    page["review"] = {
        "status": status,
        "issues": [],
        "counts": {"high": 0, "medium": 0, "low": 0},
        "message": "가상 실패" if status == "call_failed" else None,
    }
    plan = plan_word_files(result)
    assert [(i.kind, i.variant) for i in plan.planned] == [("bilingual", "single"), ("autofix", "single")]
    assert plan.skipped == (SkippedWord("qa", "single", "review_stopped", f"쪽 2 {status}"),)


def test_autofix_stopped_and_not_run_are_skipped_with_their_reasons() -> None:
    result = two_variants()
    result["variants"][0]["autofix"] = {
        "status": "stopped",
        "pages": [],
        "translatedText": None,
        "bilingualText": None,
        "stop": {"kind": "remaining_korean", "pageNum": 3, "remainingKorean": ["가상"], "message": "가상"},
        "notRunReason": None,
    }
    result["variants"][1]["autofix"] = {
        "status": "not_run",
        "pages": [],
        "translatedText": None,
        "bilingualText": None,
        "stop": None,
        "notRunReason": "earlier_variant_stopped",
    }
    plan = plan_word_files(result)
    assert [(i.kind, i.variant) for i in plan.planned] == [
        ("bilingual", "A"),
        ("bilingual", "B"),
        ("qa", "A"),
        ("qa", "B"),
    ]
    assert plan.skipped == (
        SkippedWord("autofix", "A", "autofix_stopped", "쪽 3 remaining_korean"),
        SkippedWord("autofix", "B", "autofix_not_run", "earlier_variant_stopped"),
    )


def test_issues_move_to_the_colab_keys() -> None:
    page = sample()["variants"][0]["pages"][0]
    first = page["review"]["issues"][0]
    (section,) = qa_sections([page])
    assert section == QaSection(
        page_num=1,
        content=page["translated"],
        issues=tuple(
            QaIssue(
                issue_type=i["issueType"],
                severity=i["severity"],
                original_span=i["originalSpan"],
                suggestion=i["suggestion"],
                reason=i["reason"],
            )
            for i in page["review"]["issues"]
        ),
    )
    assert section.issues[0].issue_type == first["issueType"] == "GLOSSARY_VIOLATION"


def test_build_word_files_builds_words_and_keeps_a_failure_as_its_own_value() -> None:
    result = sample()
    result["variants"][0]["autofix"]["bilingualText"] = "[PAGE 1]\n가상\x01깨진 글"
    files = build_word_files(result)
    assert [(b.kind, b.variant) for b in files.built] == [
        ("bilingual", "single"),
        ("qa", "single"),
        ("autofix", "single"),
    ]
    bilingual, qa, autofix = (b.content for b in files.built)
    assert isinstance(bilingual, bytes) and isinstance(qa, bytes)
    assert isinstance(autofix, WordFailed)  # W10 — 접지 않는다
    assert docx.Document(io.BytesIO(bilingual)).paragraphs[0].text == "[PAGE 1]"
    assert docx.Document(io.BytesIO(qa)).paragraphs[0].text == "QA Report - Style single"
