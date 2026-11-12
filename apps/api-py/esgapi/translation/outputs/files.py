"""결과(`translation.result@1`)에서 지을 Word 를 고른다(발주서 처분 ⑨) — 코랩이 짓는 조건 그대로. docx 를 직접 import
하지 않는다(짓기는 docx_bilingual·docx_qa).

문체마다(코랩 셀 차례 — 병기본 셀 55 → 검수 셀 65 → 자동수정 셀 67):
- 병기본(`bilingual`) = `variants[].bilingualText` 로 늘(셀 55 — 병기 txt 가 있으면. 쪽 번역 실패 W7 의 쪽도 그 글에
  든다).
- 검수 Word(`qa`) = 그 문체의 `pages[]` 가 전부 `review.status ∈ {reviewed, parse_failed}` 일 때만. 코랩은 검수 LLM
  호출이 실패하면 셀 65 가 멈춰 Word 가 0 이다 — `call_failed`·`not_run` 이 하나라도 있으면 안 짓고 까닭을 남긴다.
  내용은 `(pageNum, translated, issues)` 차례대로(셀 65 R/6269 — display 글은 TR1a 의 `Page.translated`).
  W7 의 쪽도 코랩은 검수한다(공통 쪽 R/6219 — 번역 txt 에 `[TRANSLATION_ERROR page=n]` 글로 들어 있다, ★g).
- 자동수정 적용본(`autofix`) = `autofix.status == "done"` 일 때만 `autofix.bilingualText` 로(셀 67 R/6939-6947).
`status: rejected` 면 아무것도 짓지 않는다(문체 0). 이름은 짓지 않는다(처분 ⑩ — kind·variant 만).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.translation.contracts.shapes import Page, ReviewIssue, TranslationDone, TranslationRejected, Variant
from esgapi.translation.outputs.docx_bilingual import render_bilingual
from esgapi.translation.outputs.docx_qa import QaIssue, QaSection, render_qa
from esgapi.translation.outputs.failures import WordFailed

WordKind = Literal["bilingual", "qa", "autofix"]
SkipReason = Literal["review_stopped", "autofix_stopped", "autofix_not_run"]

REVIEWED: Final = frozenset({"reviewed", "parse_failed"})
"""검수 Word 를 짓는 검수 갈래. call_failed·not_run 은 코랩에서 셀 65 가 멈춘 자리다."""


@dataclass(frozen=True, slots=True)
class BilingualSource:
    text: str


@dataclass(frozen=True, slots=True)
class QaSource:
    sections: tuple[QaSection, ...]


@dataclass(frozen=True, slots=True)
class PlannedWord:
    kind: WordKind
    variant: str
    source: BilingualSource | QaSource


@dataclass(frozen=True, slots=True)
class SkippedWord:
    kind: WordKind
    variant: str
    reason: SkipReason
    detail: str
    """review_stopped 면 멈춘 쪽과 갈래(「쪽 3 call_failed」), autofix_not_run 이면 notRunReason, autofix_stopped 면
    멈춘 쪽과 꼴."""


@dataclass(frozen=True, slots=True)
class WordPlan:
    planned: tuple[PlannedWord, ...]
    skipped: tuple[SkippedWord, ...]


@dataclass(frozen=True, slots=True)
class BuiltWord:
    kind: WordKind
    variant: str
    content: bytes | WordFailed


@dataclass(frozen=True, slots=True)
class WordFiles:
    built: tuple[BuiltWord, ...]
    skipped: tuple[SkippedWord, ...]


def qa_issue(issue: ReviewIssue) -> QaIssue:
    """결과의 이슈 칸 → 코랩 키(issue_type·severity·original_span·suggestion·reason). `source` 는 Word 에 없다."""
    return QaIssue(
        issue_type=issue["issueType"],
        severity=issue["severity"],
        original_span=issue["originalSpan"],
        suggestion=issue["suggestion"],
        reason=issue["reason"],
    )


def qa_sections(pages: Sequence[Page]) -> tuple[QaSection, ...]:
    return tuple(
        QaSection(
            page_num=page["pageNum"],
            content=page["translated"],
            issues=tuple(qa_issue(issue) for issue in page["review"]["issues"]),
        )
        for page in pages
    )


def _stopped_review(variant: Variant) -> str | None:
    """검수가 멈춘 첫 쪽(「쪽 n <갈래>」) — 없으면 None."""
    for page in variant["pages"]:
        status = page["review"]["status"]
        if status not in REVIEWED:
            return f"쪽 {page['pageNum']} {status}"
    return None


def plan_word_files(result: TranslationDone | TranslationRejected) -> WordPlan:
    planned: list[PlannedWord] = []
    skipped: list[SkippedWord] = []
    if result["status"] == "rejected":
        return WordPlan((), ())
    variants = result["variants"]

    for variant in variants:  # 셀 55
        planned.append(PlannedWord("bilingual", variant["label"], BilingualSource(variant["bilingualText"])))

    for variant in variants:  # 셀 65
        stopped = _stopped_review(variant)
        if stopped is None:
            planned.append(PlannedWord("qa", variant["label"], QaSource(qa_sections(variant["pages"]))))
        else:
            skipped.append(SkippedWord("qa", variant["label"], "review_stopped", stopped))

    for variant in variants:  # 셀 67
        autofix = variant["autofix"]
        if autofix["status"] == "done":
            planned.append(PlannedWord("autofix", variant["label"], BilingualSource(autofix["bilingualText"])))
        elif autofix["status"] == "stopped":
            stop = autofix["stop"]
            skipped.append(
                SkippedWord("autofix", variant["label"], "autofix_stopped", f"쪽 {stop['pageNum']} {stop['kind']}")
            )
        else:
            skipped.append(SkippedWord("autofix", variant["label"], "autofix_not_run", autofix["notRunReason"]))

    return WordPlan(tuple(planned), tuple(skipped))


def build_word_files(result: TranslationDone | TranslationRejected) -> WordFiles:
    """지을 Word 를 고르고 짓는다. 짓다 실패한 것은 `BuiltWord.content` 가 `WordFailed`(접지 않는다 — §1-9)."""
    plan = plan_word_files(result)
    built: list[BuiltWord] = []
    for item in plan.planned:
        source = item.source
        if isinstance(source, BilingualSource):
            content = render_bilingual(source.text)
        else:
            content = render_qa(source.sections, item.variant)
        built.append(BuiltWord(item.kind, item.variant, content))
    return WordFiles(tuple(built), plan.skipped)
