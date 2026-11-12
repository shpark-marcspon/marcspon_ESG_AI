"""엔진이 내는 기록(dataclass). 계약(translation.result@1)을 모른다 — contracts/wire.py 가 이것을 dict 로 받아 옮긴다.

코랩의 print("[주의] …")·로그 목록(GENERIC_EDITORIAL_QA_LOGS)·보고 dict(PART_QA_RESULTS·autofix report)의 자리다.
"""

from dataclasses import dataclass, field
from typing import Literal

type VariantLabel = Literal["single", "A", "B"]


@dataclass(frozen=True)
class EngineWarning:
    """경고 한 줄(코랩 print 자리마다 code 하나)."""

    code: str
    message: str
    page_num: int | None = None
    variant: VariantLabel | None = None


@dataclass(frozen=True)
class EditorialQaLog:
    """범용 QA 게이트 한 번(코랩 `_append_generic_editorial_qa_log` R/2578-2603).

    score_defaulted = W2(점수를 100 으로 친 것 — 칸이 없거나 정수로 못 읽음)."""

    page_num: int | None
    reason: str
    quality_score: int | None
    score_defaulted: bool
    has_critical_issue: bool | None
    applied: bool
    issues: object
    original_preview: str
    revised_preview: str
    ran: bool
    """게이트를 불렀는가(reason 이 skipped_… 가 아님)."""


@dataclass
class Fragment:
    """쪽 조각 하나의 번역(코랩 run_translation 한 바퀴)."""

    page_num: int
    status: Literal["translated", "error"]
    error: str | None
    editorial_qa: EditorialQaLog | None
    remaining_korean: tuple[str, ...] = ()
    """error 가 한국어 잔존(translate.KoreanRemaining)이면 잔존 셈이 찾은 줄(40줄까지), 그 밖은 빈 것
    (MARC-ISSUE-212 의 1)."""


@dataclass(frozen=True)
class ReviewIssue:
    issue_type: str
    severity: str
    original_span: str
    suggestion: str
    reason: str
    source: Literal["model", "glossary_rule"]


@dataclass(frozen=True)
class PageReview:
    """검수 쪽 하나. status: reviewed·parse_failed(W8)·call_failed(셀 65 가 멈춘 자리)·not_run(그 뒤)."""

    page_num: int
    translated: str
    bilingual: str
    status: Literal["reviewed", "parse_failed", "call_failed", "not_run"]
    issues: tuple[ReviewIssue, ...]
    message: str | None
    model_issues: tuple[dict[str, str], ...] = ()
    """자동수정에 넘기는 이슈(코랩 page_issues_by_page — 용어집 검사 + 모델, 합친 차례)."""
    counts: tuple[int, int, int] = (0, 0, 0)
    """(HIGH, MEDIUM, LOW) 이슈 수 — 코랩 QA Word 요약표의 셈(R/5571-5574, 글자가 정확히 그것인 것만)."""


@dataclass(frozen=True)
class SpanReplacement:
    issue_type: str
    original_span: str
    suggestion: str


@dataclass(frozen=True)
class KoreanRepairRound:
    changed: bool
    remaining_korean: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class AutofixPage:
    page_num: int
    changed: bool
    reason: str
    issue_count: int
    span_replacements: tuple[SpanReplacement, ...]
    korean_repair_rounds: tuple[KoreanRepairRound, ...]
    remaining_korean_after: tuple[str, ...]


@dataclass(frozen=True)
class AutofixStop:
    kind: Literal["remaining_korean", "call_failed"]
    page_num: int
    remaining_korean: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class AutofixRun:
    status: Literal["done", "stopped", "not_run"]
    pages: tuple[AutofixPage, ...] = ()
    translated_text: str | None = None
    bilingual_text: str | None = None
    stop: AutofixStop | None = None
    not_run_reason: Literal["disabled", "review_stopped", "earlier_variant_stopped"] | None = None


@dataclass
class VariantRun:
    label: VariantLabel
    translated_text: str = ""
    bilingual_text: str = ""
    fragments: list[Fragment] = field(default_factory=list[Fragment])
    pages: list[PageReview] = field(default_factory=list[PageReview])
    glossary_misses: list[tuple[int, str, str, int]] = field(default_factory=list[tuple[int, str, str, int]])
    autofix: AutofixRun = field(default_factory=lambda: AutofixRun(status="not_run", not_run_reason="disabled"))


@dataclass(frozen=True)
class Rejection:
    kind: Literal["no_pages", "ceo_page_limit", "unsupported_input"]
    message: str
    page_count: int | None = None
    limit: int | None = None


@dataclass
class TranslationRun:
    """엔진 한 번의 결과."""

    part: str
    variant_labels: tuple[VariantLabel, ...]
    page_numbers: list[int] = field(default_factory=list[int])
    duplicate_pages: dict[int, int] = field(default_factory=dict[int, int])
    rejection: Rejection | None = None
    variants: list[VariantRun] = field(default_factory=list[VariantRun])
    warnings: list[EngineWarning] = field(default_factory=list[EngineWarning])
