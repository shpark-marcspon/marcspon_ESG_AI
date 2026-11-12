"""이슈 기반 자동수정(코랩 셀 67). 문체 하나의 raw 영문 번역을 쪽마다: 직접 치환 → LLM 최소 수정 → 한국어 보정 1회 →
남으면 멈춤(W7 — 코랩은 ValueError 로 셀이 멈춘다). 끝까지 가면 쪽을 이어 쓰고 다시 읽어 병기를 새로 짓는다.

LLM 은 역할 translate(코랩 PART_QA_AUTOFIX_MODEL = TRANSLATION_MODEL, R/6366). 파트 이슈는 늘 빈 목록(W4 — R/6870).
"""

import json
from collections.abc import Mapping

from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.bilingual import attach_korean_originals
from esgapi.translation.engines.colab_158.gates import table_pipe_signature
from esgapi.translation.engines.colab_158.glossary import build_glossary_text, build_relevant_glossary
from esgapi.translation.engines.colab_158.pages import file_roundtrip, join_pages
from esgapi.translation.engines.colab_158.ports import LlmCallFailed, LlmGateway
from esgapi.translation.engines.colab_158.records import (
    AutofixPage,
    AutofixRun,
    AutofixStop,
    EngineWarning,
    KoreanRepairRound,
    SpanReplacement,
    VariantLabel,
)
from esgapi.translation.engines.colab_158.review_rules import (
    PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS,
    STRICT_FAIL_ON_REMAINING_KOREAN_AFTER_PART_QA_AUTOFIX,
    UNTRANSLATED_FALLBACK_ISSUE,
    Issue,
    clean_llm_explanation_lines,
    collect_remaining_korean_lines_in_english,
    ensure_page_tag,
    extract_only_corrected_page_text,
    filter_actionable_issues,
    normalize_issue_text_for_compare,
    select_part_issues_for_page,
    simple_span_replacements,
)
from esgapi.translation.engines.colab_158.texts import PromptTexts

SAFE_CURRENT = "table_pipe_signature_changed_safe_current_used"


class _Stop(Exception):  # 코랩의 셀 멈춤 자리
    def __init__(self, stop: AutofixStop) -> None:
        super().__init__(stop.message)
        self.stop = stop


class Autofixer:
    def __init__(
        self,
        gateway: LlmGateway,
        glossary: Mapping[str, str],
        variant: VariantLabel,
        warnings: list[EngineWarning],
        *,
        texts: PromptTexts,
    ) -> None:
        self.gateway = gateway
        self.texts = texts
        self.glossary = glossary
        self.variant: VariantLabel = variant
        self.warnings = warnings

    def _call(self, site: prompts.Site, system: str, user: str, page_num: int) -> str:
        """`client.messages.create` + `_response_text_safe`(R/6389-6396). 실패는 셀 멈춤(call_failed)."""
        try:
            reply = self.gateway.complete(site, "translate", system, user, prompts.MAX_TOKENS[site])
        except LlmCallFailed as e:
            raise _Stop(AutofixStop(kind="call_failed", page_num=page_num, remaining_korean=(), message=str(e))) from e
        if reply.ending != "complete":
            code = "llm_truncated" if reply.ending == "truncated" else "llm_refused"
            self.warnings.append(
                EngineWarning(code=code, message=f"{site}: {reply.ending}", page_num=page_num, variant=self.variant)
            )
        return reply.text.strip()

    def repair_page(
        self, source_page_text: str, current_page_text: str, issues: list[Issue], page_num: int
    ) -> tuple[str, bool, str]:
        """R/6647-6739. (고친 글, changed, reason)."""
        glossary_text = build_glossary_text(build_relevant_glossary(self.glossary, source_page_text))
        issue_json = json.dumps(issues, ensure_ascii=False, indent=2)
        signature_before = table_pipe_signature(current_page_text)
        text = self._call(
            "autofix",
            self.texts.autofix_system(page_num),
            prompts.autofix_user(
                self.variant, glossary_text, issue_json, page_num, source_page_text, current_page_text
            ),
            page_num,
        )
        repaired = extract_only_corrected_page_text(text, page_num)
        if signature_before and signature_before != table_pipe_signature(repaired):
            self.warnings.append(
                EngineWarning(
                    code="autofix_table_changed",
                    message=(
                        f"PAGE {page_num} / STYLE {self.variant}: "
                        "표 pipe 구조가 바뀌어 LLM 보정본을 폐기하고 원문을 유지합니다."
                    ),
                    page_num=page_num,
                    variant=self.variant,
                )
            )
            safe_current = ensure_page_tag(clean_llm_explanation_lines(current_page_text), page_num)
            changed = normalize_issue_text_for_compare(safe_current) != normalize_issue_text_for_compare(
                current_page_text
            )
            return safe_current, changed, SAFE_CURRENT
        changed = normalize_issue_text_for_compare(repaired) != normalize_issue_text_for_compare(current_page_text)
        return repaired, changed, "llm_repair_applied" if changed else "no_change_needed"

    def repair_remaining_korean_once(
        self, source_page_text: str, current_page_text: str, page_num: int
    ) -> tuple[str, KoreanRepairRound]:
        """R/6742-6797."""
        remaining = collect_remaining_korean_lines_in_english(current_page_text)
        if not remaining:
            return current_page_text, KoreanRepairRound(changed=False, remaining_korean=(), reason=None)
        glossary_text = build_glossary_text(build_relevant_glossary(self.glossary, source_page_text))
        remaining_text = "\n".join(f"- {x}" for x in remaining)
        text = self._call(
            "autofix-korean",
            self.texts.autofix_korean_system(page_num),
            prompts.autofix_korean_user(glossary_text, remaining_text, page_num, source_page_text, current_page_text),
            page_num,
        )
        repaired = extract_only_corrected_page_text(text, page_num)
        before = table_pipe_signature(current_page_text)
        if before and before != table_pipe_signature(repaired):
            self.warnings.append(
                EngineWarning(
                    code="autofix_korean_table_changed",
                    message=f"PAGE {page_num} / STYLE {self.variant}: 한국어 잔존 보정 중 표 구조가 바뀌어 원문 유지",
                    page_num=page_num,
                    variant=self.variant,
                )
            )
            safe_current = ensure_page_tag(clean_llm_explanation_lines(current_page_text), page_num)
            return safe_current, KoreanRepairRound(
                changed=normalize_issue_text_for_compare(safe_current)
                != normalize_issue_text_for_compare(current_page_text),
                remaining_korean=tuple(collect_remaining_korean_lines_in_english(safe_current)),
                reason=SAFE_CURRENT,
            )
        return repaired, KoreanRepairRound(
            changed=normalize_issue_text_for_compare(repaired) != normalize_issue_text_for_compare(current_page_text),
            remaining_korean=tuple(collect_remaining_korean_lines_in_english(repaired)),
            reason=None,
        )

    def run(
        self,
        source_map: Mapping[int, str],
        raw_map: Mapping[int, str],
        page_issues_by_page: Mapping[int, list[dict[str, str]]],
        source_text_for_bilingual: str,
    ) -> AutofixRun:
        """R/6840-6968(문체 하나). 멈추면 쪽 결과를 버린다(코랩은 파일을 쓰지 않았다)."""
        try:
            pages = self._pages(source_map, raw_map, page_issues_by_page)
        except _Stop as stop:
            return AutofixRun(status="stopped", stop=stop.stop)
        fixed_map = dict(raw_map)
        for page_num, text in pages[1].items():
            fixed_map[page_num] = text
        written = join_pages([str(fixed_map[p]).strip() for p in sorted(fixed_map)])
        fixed_raw_text = file_roundtrip(written)
        bilingual = attach_korean_originals(fixed_raw_text, source_text_for_bilingual)
        return AutofixRun(
            status="done", pages=tuple(pages[0]), translated_text=fixed_raw_text, bilingual_text=bilingual
        )

    def _pages(
        self,
        source_map: Mapping[int, str],
        raw_map: Mapping[int, str],
        page_issues_by_page: Mapping[int, list[dict[str, str]]],
    ) -> tuple[list[AutofixPage], dict[int, str]]:
        part_issues = filter_actionable_issues([])  # W4: 코랩 result.get("part_issues") 는 늘 없다
        reports: list[AutofixPage] = []
        fixed: dict[int, str] = {}
        for pnum in sorted(set(source_map) & set(raw_map)):
            page_text = raw_map[pnum]
            page_issues = filter_actionable_issues(list(page_issues_by_page.get(pnum) or []))
            combined = select_part_issues_for_page(part_issues, page_text) + page_issues
            if not combined:
                if not collect_remaining_korean_lines_in_english(page_text):
                    continue
                combined = [dict(UNTRANSLATED_FALLBACK_ISSUE)]
            pre_replaced, applied = simple_span_replacements(page_text, combined)
            repaired, changed, reason = self.repair_page(source_map[pnum], pre_replaced, combined, pnum)
            rounds: list[KoreanRepairRound] = []
            for _ in range(PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS):
                if not collect_remaining_korean_lines_in_english(repaired):
                    break
                repaired, ko_round = self.repair_remaining_korean_once(source_map[pnum], repaired, pnum)
                rounds.append(ko_round)
            remaining_after = collect_remaining_korean_lines_in_english(repaired)
            if remaining_after and STRICT_FAIL_ON_REMAINING_KOREAN_AFTER_PART_QA_AUTOFIX:
                raise _Stop(
                    AutofixStop(
                        kind="remaining_korean",
                        page_num=pnum,
                        remaining_korean=tuple(remaining_after),
                        message=f"STYLE {self.variant} / PAGE {pnum} 자동수정 후에도 한국어가 남아 있습니다.\n"
                        + "\n".join(f"- {x}" for x in remaining_after[:10]),
                    )
                )
            fixed[pnum] = repaired
            reports.append(
                AutofixPage(
                    page_num=pnum,
                    changed=changed,
                    reason=reason,
                    issue_count=len(combined),
                    span_replacements=tuple(
                        SpanReplacement(
                            issue_type=a["issue_type"], original_span=a["original_span"], suggestion=a["suggestion"]
                        )
                        for a in applied
                    ),
                    korean_repair_rounds=tuple(rounds),
                    remaining_korean_after=tuple(remaining_after),
                )
            )
        return reports, fixed
