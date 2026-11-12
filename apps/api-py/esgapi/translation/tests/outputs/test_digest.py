"""요약 translation.digest@1(outputs/digest.py — 밴드 TR3a §3-1-2, 순수): 지어낸 결과마다 칸·outcome·glossaryMisses 의
범위 거름·files 는 실제로 지은 이름. 결과는 tests/data/examples/result-sample.json(지어낸 것)을 고쳐 짓는다.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES
from esgapi.translation.contracts.shapes import RESULT_SHAPE, RESULT_SHAPES
from esgapi.translation.flows.colab_158 import OUTPUT_FILES, word_name
from esgapi.translation.outputs.digest import digest

EXAMPLE = Path(__file__).resolve().parents[1] / "data" / "examples" / "result-sample.json"
ALL_FILES = frozenset(OUTPUT_FILES)
REJECTION_KINDS = (
    "no_pages",
    "ceo_page_limit",
    "unsupported_input",
    "too_large",
    "over_budget",
    "retry_source_not_found",
    "retry_source_mismatch",
)


def sample() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLE.read_text(encoding="utf-8")))


def summarize(result: dict[str, Any], built: frozenset[str] = ALL_FILES) -> dict[str, Any]:
    RESULT_SHAPES[RESULT_SHAPE].validate_python(result, strict=True)  # 지은 결과가 결과 꼴이다
    out = cast("dict[str, Any]", digest(result, built, name=word_name))
    DIGEST_SHAPES[DIGEST_SHAPE].validate_python(out, strict=True)
    assert next(iter(out)) == "schemaVersion"
    return out


def stopped_review(status: str, message: str | None) -> dict[str, Any]:
    return {"status": status, "issues": [], "counts": {"high": 0, "medium": 0, "low": 0}, "message": message}


def two_variants() -> dict[str, Any]:
    """A·B 둘 — B 는 A 를 베낀 것(번역 실패 없음·검수 다 돔·자동수정 안 돎)."""
    result = sample()
    a = result["variants"][0]
    a["label"] = "A"
    b = copy.deepcopy(a)
    b["label"] = "B"
    for fragment in b["fragments"]:
        fragment.update(status="translated", error=None)
    b["glossaryCheck"] = []
    b["autofix"] = {
        "status": "not_run",
        "pages": [],
        "translatedText": None,
        "bilingualText": None,
        "stop": None,
        "notRunReason": "disabled",
    }
    result["variants"] = [a, b]
    result["settings"]["variants"] = ["A", "B"]
    return result


def test_the_sample_is_summed_field_by_field() -> None:
    out = summarize(sample())
    assert out == {
        "schemaVersion": "translation.digest@1",
        "status": "done",
        "rejectionKind": None,
        "outcome": "partial",  # 쪽 3 번역 실패
        "pageCount": 3,
        "failedPages": [3],
        "variants": [
            {
                "label": "single",
                "reviewStatus": "reviewed",  # parse_failed 쪽은 멈춤이 아니다
                "reviewStoppedAt": None,
                "parseFailedPages": 1,
                "issueCount": 3,
                "issueCounts": {"high": 2, "medium": 0, "low": 1},
                "glossaryMisses": 1,
                "autofixStatus": "done",
                "autofixChangedPages": 2,
                "files": {
                    "bilingual": "translation-bilingual-single.docx",
                    "qa": "translation-qa-single.docx",
                    "autofix": "translation-autofix-single.docx",
                },
            }
        ],
        "warningCount": 1,
    }


def test_issue_count_counts_every_issue_and_the_severity_counts_only_the_three_words() -> None:
    result = sample()
    page = result["variants"][0]["pages"][0]
    page["review"]["issues"][0]["severity"] = "CRITICAL"  # 코랩대로 남는 글자 — counts 는 그대로 HIGH 하나 덜 셈
    page["review"]["counts"]["high"] -= 1
    (variant,) = summarize(result)["variants"]
    assert variant["issueCount"] == 3
    assert variant["issueCounts"] == {"high": 1, "medium": 0, "low": 1}
    assert sum(variant["issueCounts"].values()) < variant["issueCount"]


def test_a_clean_run_is_done() -> None:
    result = sample()
    variant = result["variants"][0]
    variant["fragments"][2].update(status="translated", error=None)
    out = summarize(result)
    assert (out["outcome"], out["failedPages"]) == ("done", [])


@pytest.mark.parametrize("status", ["call_failed", "not_run"])
def test_a_stopped_review_is_partial_and_names_the_first_stopped_page(status: str) -> None:
    result = sample()
    variant = result["variants"][0]
    variant["fragments"][2].update(status="translated", error=None)
    variant["pages"][1]["review"] = stopped_review(status, "가상 호출 실패" if status == "call_failed" else None)
    variant["pages"][2]["review"] = stopped_review("not_run", None)
    out = summarize(result)
    (summary,) = out["variants"]
    assert out["outcome"] == "partial"
    assert (summary["reviewStatus"], summary["reviewStoppedAt"]) == (status, 2)
    assert (summary["parseFailedPages"], summary["issueCount"]) == (0, 2)


def test_a_parse_failed_review_or_a_stopped_autofix_alone_is_done() -> None:
    """감독 처분 5: 자동수정 멈춤·검수 parse_failed 는 partial 로 치지 않는다."""
    result = sample()
    variant = result["variants"][0]
    variant["fragments"][2].update(status="translated", error=None)
    variant["autofix"] = {
        "status": "stopped",
        "pages": [],
        "translatedText": None,
        "bilingualText": None,
        "stop": {"kind": "remaining_korean", "pageNum": 1, "remainingKorean": ["가상"], "message": "가상 멈춤"},
        "notRunReason": None,
    }
    out = summarize(result, ALL_FILES - {"translation-autofix-single.docx"})
    (summary,) = out["variants"]
    assert out["outcome"] == "done"
    assert (summary["autofixStatus"], summary["autofixChangedPages"], summary["files"]["autofix"]) == (
        "stopped",
        0,
        None,
    )
    assert summary["parseFailedPages"] == 1


def test_the_not_run_autofix_has_no_changed_pages() -> None:
    out = summarize(two_variants())
    a, b = out["variants"]
    assert (a["label"], b["label"]) == ("A", "B")
    assert (b["autofixStatus"], b["autofixChangedPages"]) == ("not_run", 0)
    assert out["failedPages"] == [3]  # A 의 실패 쪽 — 어느 문체든


def test_failed_pages_are_sorted_and_unique_across_variants() -> None:
    result = two_variants()
    a, b = result["variants"]
    a["fragments"][0].update(status="error", error="가상 오류")
    b["fragments"][2].update(status="error", error="가상 오류")
    b["fragments"][1].update(status="error", error="가상 오류")
    assert summarize(result)["failedPages"] == [1, 2, 3]


def test_glossary_misses_count_only_the_target_pages() -> None:
    """엔진도 그 실행 쪽 범위만 낸다(MARC-ENT-451) — 요약은 번역 대상 쪽(document.pageNumbers) 밖 줄을 세지 않는다."""
    result = sample()
    check = result["variants"][0]["glossaryCheck"]
    (inside,) = check
    check.append({**inside, "pageNum": 7})  # 범위 밖
    check.append({**inside, "pageNum": 0})  # 범위 밖
    check.append({**inside, "pageNum": 3, "termKo": "가상설비", "termEn": "Virtual Facility"})
    (variant,) = summarize(result)["variants"]
    assert variant["glossaryMisses"] == 2


def test_page_count_is_the_distinct_target_pages() -> None:
    result = sample()
    result["document"]["pageNumbers"] = [1, 2, 2, 3]
    result["document"]["duplicatePages"] = {"2": 2}
    assert summarize(result)["pageCount"] == 3


def test_files_are_the_names_actually_built_not_the_plan() -> None:
    """Word 짓기 실패(WordFailed)로 빠진 파일은 null 이다 — 계획한 이름이 아니라 실제 지은 이름."""
    built = ALL_FILES - {"translation-qa-single.docx", "translation-bilingual-single.docx"}
    (variant,) = summarize(sample(), built)["variants"]
    assert variant["files"] == {"bilingual": None, "qa": None, "autofix": "translation-autofix-single.docx"}
    (none,) = summarize(sample(), frozenset())["variants"]
    assert none["files"] == {"bilingual": None, "qa": None, "autofix": None}


def test_a_b_files_use_the_lowercase_label() -> None:
    a, b = summarize(two_variants())["variants"]
    assert a["files"]["bilingual"] == "translation-bilingual-a.docx"
    assert b["files"]["qa"] == "translation-qa-b.docx"


@pytest.mark.parametrize("kind", REJECTION_KINDS)
def test_every_rejection_is_summarized_as_rejected(kind: str) -> None:
    result = sample()
    result.update(
        status="rejected",
        rejection={"kind": kind, "message": "가상 거절", "pageCount": None, "limit": None},
        variants=[],
        warnings=[],
    )
    out = summarize(result, frozenset())
    assert (out["status"], out["rejectionKind"], out["outcome"]) == ("rejected", kind, "rejected")
    assert (out["variants"], out["failedPages"], out["warningCount"]) == ([], [], 0)
    assert "가상 거절" not in json.dumps(out, ensure_ascii=False)  # 거절 글은 결과 경로가 싣는다


def test_the_rejection_kinds_match_the_result_shape() -> None:
    result_kinds = RESULT_SHAPES[RESULT_SHAPE].json_schema()["$defs"]["Rejection"]["properties"]["kind"]["enum"]
    schema = DIGEST_SHAPES[DIGEST_SHAPE].json_schema()
    digest_kinds = schema["$defs"]["TranslationDigest"]["properties"]["rejectionKind"]["anyOf"][0]["enum"]
    assert result_kinds == digest_kinds == list(REJECTION_KINDS)
