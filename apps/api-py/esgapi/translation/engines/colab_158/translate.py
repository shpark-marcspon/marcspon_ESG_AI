"""번역(코랩 셀 46): 칸·표 묶음·일반 구획·윤문·범용 QA 게이트·용어집 보정·한국어 잔존 게이트·`translate_page`·A/B.

코랩의 셀 전역(CURRENT_PART·COMPANY_STYLE_PROMPT·TRANSLATION_MODEL·GENERIC_EDITORIAL_QA_LOGS)은 `Translator` 의 칸이다.
LLM 은 포트로만 — 역할 translate(모델은 다리가 파트로 고른다). `time.sleep` 은 지웠다. print 는 warnings 로.
JSON 답의 값 꼴은 정해져 있지 않다 — 코랩이 그 값에 dict·int 메서드를 부르는 자리에서 코랩과 같은 예외를 낸다
(그 예외는 쪽의 except 에 잡혀 W7 갈래로 간다).
"""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import cast

from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.gates import (
    EDITORIAL_POLISH_MAX_CHARS,
    EDITORIAL_POLISH_MIN_CHARS,
    ENABLE_EDITORIAL_POLISH,
    ENABLE_FINAL_PAGE_POLISH,
    ENABLE_GENERIC_EDITORIAL_QA_GATE,
    MAX_UNTRANSLATED_REPAIR_ROUNDS,
    STRICT_FAIL_ON_UNTRANSLATED_KOREAN,
    TABLE_BATCH_SIZE,
    apply_editorial_phrase_cleanup,
    collect_untranslated_korean_lines,
    fix_heading_body_merge,
    format_glossary_violations_for_prompt,
    has_ko,
    must_apply,
    should_run_page_level_text_gate,
    split_page_sections,
    structure_tag_signature,
    table_pipe_signature,
)
from esgapi.translation.engines.colab_158.glossary import (
    build_glossary_text,
    build_relevant_glossary,
    find_deterministic_glossary_violations,
)
from esgapi.translation.engines.colab_158.ports import LlmGateway
from esgapi.translation.engines.colab_158.records import EditorialQaLog, EngineWarning, VariantLabel
from esgapi.translation.engines.colab_158.tables import collect_table_fragments, parse_json_loose, reassemble_table
from esgapi.translation.engines.colab_158.texts import PromptTexts


class KoreanRemaining(ValueError):
    """보정 뒤에도 한국어가 남았다(코랩 STRICT_FAIL 의 ValueError — 같은 except 에 잡히고 `str(e)` 도 같다).
    `remaining` = 잔존 셈이 찾은 줄 전부(셈 그대로 40줄·줄당 300자까지 — 메시지는 코랩대로 앞 10줄만,
    MARC-ISSUE-212 의 1)."""

    def __init__(self, message: str, remaining: Sequence[str]) -> None:
        super().__init__(message)
        self.remaining = tuple(remaining)


def json_get(value: object, key: str, default: object) -> object:
    """`value.get(key, default)` — dict 가 아니면 코랩처럼 AttributeError."""
    if not isinstance(value, dict):
        raise AttributeError(f"'{type(value).__name__}' object has no attribute 'get'")
    return cast("dict[str, object]", value).get(key, default)


def json_has(value: object, key: str) -> bool:
    """`key in value`(dict 일 때만 — 부르는 쪽이 json_get 으로 dict 임을 이미 본 뒤)."""
    return isinstance(value, dict) and key in cast("dict[str, object]", value)


def json_is_dict(value: object) -> bool:
    return isinstance(value, dict)


def json_iter(value: object) -> list[object]:
    """`for x in value` — 목록·dict(키)·글자(글자)는 돌고, 그 밖은 코랩처럼 TypeError."""
    if isinstance(value, list | dict | str):
        return list(cast("Iterable[object]", value))
    raise TypeError(f"'{type(value).__name__}' object is not iterable")


def json_len(value: object) -> int:
    """`len(value)` — 목록·dict·글자만, 그 밖은 TypeError."""
    if isinstance(value, list | dict | str):
        return len(cast("Sequence[object]", value))
    raise TypeError(f"object of type '{type(value).__name__}' has no len()")


def int_or_100(value: object) -> tuple[int, bool]:
    """R/2693-2696 `try: int(data.get("quality_score", 100)) except Exception: 100`.

    (점수, 100 으로 쳤는가). 칸이 없을 때의 100 은 부르는 쪽이 따로 표시한다."""
    try:
        if isinstance(value, bool | int | float | str):
            return int(value), False
    except (ValueError, OverflowError):
        return 100, True
    return 100, True


class Translator:
    """한 번역 실행의 셀 전역. `warnings`·`qa_logs` 에 코랩의 print·로그 자리가 쌓인다."""

    def __init__(
        self,
        gateway: LlmGateway,
        *,
        part: str,
        company_style_prompt: str,
        industry_standards: str,
        warnings: list[EngineWarning],
        texts: PromptTexts,
    ) -> None:
        self.gateway = gateway
        self.texts = texts
        self.part = part
        self.company_style_prompt = company_style_prompt
        self.industry_standards = industry_standards
        self.warnings = warnings
        self.qa_logs: list[EditorialQaLog] = []
        self.variant: VariantLabel | None = None
        self.page_num: int | None = None

    # ── LLM ──

    def _warn(self, code: str, message: str) -> None:
        self.warnings.append(EngineWarning(code=code, message=message, page_num=self.page_num, variant=self.variant))

    def call(self, site: prompts.Site, system: str, user: str) -> str:
        """`_create_message` + `_response_text`(R/2147-2159): 답 글을 strip. 잘림·거절은 그 글로 계속하고 경고만."""
        reply = self.gateway.complete(site, "translate", system, user, prompts.MAX_TOKENS[site])
        if reply.ending == "truncated":
            self._warn("llm_truncated", f"{site}: 답이 출력 상한에서 잘려 그 글로 계속했다")
        elif reply.ending == "refused":
            self._warn("llm_refused", f"{site}: 모델이 거절한 글을 그대로 썼다")
        return reply.text.strip()

    # ── 구획 번역 ──

    def single_translate_fragment(self, text: str, glossary_text: str, system_prompt: str) -> str:
        """R/2249-2274."""
        if not has_ko(text):
            return text
        return self.call("cell", system_prompt, prompts.cell_user(glossary_text, text))

    def batch_translate_json(
        self, items: Sequence[dict[str, str]], glossary_text: str, system_prompt: str
    ) -> dict[str, str]:
        """R/2277-2337. 24칸씩 JSON 으로. 답을 못 읽으면(무엇이든 예외) 그 묶음은 칸 하나씩."""
        if not items:
            return {}
        out: dict[str, str] = {}
        for chunk_start in range(0, len(items), TABLE_BATCH_SIZE):
            chunk = items[chunk_start : chunk_start + TABLE_BATCH_SIZE]
            payload = json.dumps({"items": list(chunk)}, ensure_ascii=False, indent=2)
            raw = self.call(
                "table-batch",
                self.texts.table_batch_system(system_prompt),
                prompts.table_batch_user(glossary_text, payload),
            )
            try:
                parsed = parse_json_loose(raw)
                for obj in json_iter(json_get(parsed, "items", [])):
                    fid, tr = json_get(obj, "id", None), json_get(obj, "translation", None)
                    if fid is not None and tr is not None:
                        out[str(fid)] = str(tr).strip()
            except Exception as e:
                self._warn("table_json_fallback", f"JSON 파싱 실패 → 셀 단위 fallback 사용: {e}")
                for item in chunk:
                    out[item["id"]] = self.single_translate_fragment(item["text"], glossary_text, system_prompt)
        return out

    def translate_general_section(
        self, section_text: str, glossary_text: str, system_prompt: str, page_num: int | None = None
    ) -> str:
        """R/2340-2365."""
        if not has_ko(section_text):
            return section_text
        return self.call("section", system_prompt, prompts.section_user(glossary_text, section_text, page_num))

    def translate_table_section(self, section_text: str, glossary_text: str, system_prompt: str) -> str:
        """R/2812-2936. pipe 표가 없으면 일반 구획으로(쪽 번호 없이 — 코랩대로)."""
        plan = collect_table_fragments(section_text)
        if plan is None:
            return self.translate_general_section(section_text, glossary_text, system_prompt)
        translations = self.batch_translate_json(plan.fragments, glossary_text, system_prompt)
        return reassemble_table(plan, translations)

    # ── 윤문·범용 QA ──

    def editorial_polish_once(
        self, source_text: str, translated_text: str, glossary_text: str, system_prompt: str, page_num: int | None
    ) -> str:
        """R/2482-2549."""
        if not ENABLE_EDITORIAL_POLISH:
            return translated_text
        if not translated_text or not translated_text.strip():
            return translated_text
        plain_len = len(re.sub(r"\s+", "", translated_text))
        if self.part != "ceo_message" and plain_len < EDITORIAL_POLISH_MIN_CHARS:
            return translated_text
        if len(translated_text) > EDITORIAL_POLISH_MAX_CHARS:
            return translated_text
        before_tags = structure_tag_signature(translated_text)
        before_leftover = collect_untranslated_korean_lines(translated_text)
        polished = self.call(
            "polish",
            self.texts.polish_system(system_prompt),
            prompts.polish_user(glossary_text, source_text, translated_text, page_num),
        ).strip()
        polished = apply_editorial_phrase_cleanup(polished)
        if not polished:
            return translated_text
        after_tags = structure_tag_signature(polished)
        if before_tags and before_tags != after_tags:
            self._warn("polish_tags_changed", "윤문 결과 구조 태그가 달라져서 원 번역을 유지합니다.")
            return translated_text
        if len(collect_untranslated_korean_lines(polished)) > len(before_leftover):
            self._warn("polish_korean_increased", "윤문 결과 한국어 잔존이 늘어나서 원 번역을 유지합니다.")
            return translated_text
        return polished

    def _log_qa(
        self,
        page_num: int | None,
        reason: str,
        *,
        score: int | None = None,
        defaulted: bool = False,
        has_critical_issue: bool | None = None,
        issues: object = None,
        applied: bool = False,
        original_text: str = "",
        revised_text: str = "",
    ) -> None:
        """R/2578-2603(`issues or []` — 거짓이면 빈 목록)."""
        self.qa_logs.append(
            EditorialQaLog(
                page_num=page_num,
                reason=reason,
                quality_score=score,
                score_defaulted=defaulted,
                has_critical_issue=has_critical_issue,
                applied=applied,
                issues=issues or [],
                original_preview=original_text[:1200],
                revised_preview=revised_text[:1200],
                ran=not reason.startswith("skipped_"),
            )
        )

    def generic_editorial_quality_gate(
        self, source_text: str, translated_text: str, glossary_text: str, system_prompt: str, page_num: int | None
    ) -> str:
        """R/2606-2789."""
        if not ENABLE_GENERIC_EDITORIAL_QA_GATE:
            return translated_text
        if not translated_text or not str(translated_text).strip():
            return translated_text
        if not should_run_page_level_text_gate(translated_text):
            self._log_qa(page_num, "skipped_table_or_short_text", issues=[], original_text=translated_text)
            return translated_text
        if len(translated_text) > EDITORIAL_POLISH_MAX_CHARS:
            self._log_qa(page_num, "skipped_too_long", issues=[], original_text=translated_text)
            return translated_text
        before_tags = structure_tag_signature(translated_text)
        before_leftover = collect_untranslated_korean_lines(translated_text)
        raw = self.call(
            "editorial-qa",
            self.texts.editorial_qa_system(system_prompt),
            prompts.editorial_qa_user(glossary_text, source_text, translated_text, page_num),
        ).strip()
        try:
            data = parse_json_loose(raw)
        except Exception:
            self._warn("editorial_qa_json_failed", "Generic Editorial QA JSON 파싱 실패. 원문 번역을 유지합니다.")
            self._log_qa(page_num, "json_parse_failed", issues=[], original_text=translated_text, revised_text=raw)
            return translated_text
        score, defaulted = int_or_100(json_get(data, "quality_score", 100))
        if not json_has(data, "quality_score"):
            defaulted = True  # 칸이 없어 기본값 100(W2)
        has_critical_issue = bool(json_get(data, "has_critical_issue", False))
        issues: object = json_get(data, "issues", []) or list[object]()
        revised = str(json_get(data, "revised_text", "") or "").strip()

        def log(reason: str, revised_text: str = "", applied: bool = False) -> None:
            self._log_qa(
                page_num,
                reason,
                score=score,
                defaulted=defaulted,
                has_critical_issue=has_critical_issue,
                issues=issues,
                applied=applied,
                original_text=translated_text,
                revised_text=revised_text,
            )

        if not revised:
            log("no_revised_text")
            return translated_text
        issue_types = {str(json_get(issue, "type", "")).upper() for issue in json_iter(issues) if json_is_dict(issue)}
        if not must_apply(score, has_critical_issue, issue_types, json_len(issues)):
            log("score_and_issues_acceptable", revised)
            return translated_text
        if before_tags and before_tags != structure_tag_signature(revised):
            self._warn(
                "editorial_qa_tags_changed", "Generic Editorial QA 수정 결과 구조 태그가 달라져 원문 번역을 유지합니다."
            )
            log("structure_tag_changed", revised)
            return translated_text
        if len(collect_untranslated_korean_lines(revised)) > len(before_leftover):
            self._warn(
                "editorial_qa_korean_increased",
                "Generic Editorial QA 수정 후 한국어 잔존이 늘어나 원문 번역을 유지합니다.",
            )
            log("korean_leftover_increased", revised)
            return translated_text
        log("revised_text_applied", revised, applied=True)
        return revised

    # ── 용어집·한국어 게이트 ──

    def repair_glossary_violations_once(
        self, source_text: str, translated_text: str, glossary: Mapping[str, str], system_prompt: str, is_table: bool
    ) -> str:
        """R/2980-3041."""
        violations = find_deterministic_glossary_violations(source_text, translated_text, glossary)
        if not violations:
            return translated_text
        glossary_text = build_glossary_text(build_relevant_glossary(glossary, source_text))
        violation_text = format_glossary_violations_for_prompt(violations)
        table_rule = prompts.GLOSSARY_REPAIR_TABLE_RULE if is_table else prompts.GLOSSARY_REPAIR_STRUCTURE_RULE
        repaired = self.call(
            "glossary-repair",
            system_prompt,
            prompts.glossary_repair_user(glossary_text, violation_text, table_rule, source_text, translated_text),
        )
        if not repaired.strip():
            return translated_text
        return repaired

    def repair_untranslated_korean_once(
        self, source_text: str, translated_text: str, glossary_text: str, system_prompt: str, is_table: bool
    ) -> str:
        """R/3101-3187."""
        leftover = collect_untranslated_korean_lines(translated_text)
        if not leftover:
            return translated_text
        leftover_text = "\n".join(f"- {x}" for x in leftover)
        table_rule = prompts.KOREAN_REPAIR_TABLE_RULE if is_table else prompts.KOREAN_REPAIR_STRUCTURE_RULE
        repaired = self.call(
            "korean-repair",
            prompts.korean_repair_system(system_prompt),
            prompts.korean_repair_user(glossary_text, leftover_text, table_rule, source_text, translated_text),
        )
        if not repaired.strip():
            return translated_text
        if is_table:
            before_sig = table_pipe_signature(translated_text)
            if before_sig and before_sig != table_pipe_signature(repaired):
                self._warn(
                    "korean_repair_table_changed", "한국어 잔존 보정 결과 표 구조가 달라져서 원 번역을 유지합니다."
                )
                return translated_text
        if len(collect_untranslated_korean_lines(repaired)) < len(collect_untranslated_korean_lines(translated_text)):
            return repaired
        return translated_text

    def translation_quality_gate(
        self,
        source_text: str,
        translated_text: str,
        glossary: Mapping[str, str],
        glossary_text: str,
        system_prompt: str,
        is_table: bool,
    ) -> str:
        """R/3190-3240. 그래도 한국어가 남으면 KoreanRemaining(ValueError — 코랩 STRICT_FAIL, 쪽의 except 가 잡는다,
        W7)."""
        translated_text = self.repair_glossary_violations_once(
            source_text, translated_text, glossary, system_prompt, is_table
        )
        for _ in range(MAX_UNTRANSLATED_REPAIR_ROUNDS):
            if not collect_untranslated_korean_lines(translated_text):
                break
            translated_text = self.repair_untranslated_korean_once(
                source_text, translated_text, glossary_text, system_prompt, is_table
            )
        remaining = collect_untranslated_korean_lines(translated_text)
        if remaining:
            msg = (
                "[치명] 번역 결과에 한국어가 남아 있어 중단합니다.\n"
                "아래 문구를 GLOSSARY 또는 FINAL_GLOSSARY에 추가한 뒤 재실행하세요.\n"
                + "\n".join(f"- {x}" for x in remaining[:10])
            )
            if STRICT_FAIL_ON_UNTRANSLATED_KOREAN:
                raise KoreanRemaining(msg, remaining)
            self._warn("korean_remaining", msg)
        return translated_text

    # ── 쪽 ──

    def translate_one_style(
        self, page_content: str, glossary: Mapping[str, str], page_num: int, style_prompt: str
    ) -> str:
        """R/3279-3360 `_translate_one_style`."""
        active_glossary = build_relevant_glossary(glossary, page_content)
        active_glossary_text = build_glossary_text(active_glossary)
        sp = self.texts.page_system(self.company_style_prompt, style_prompt, self.industry_standards)
        out_parts: list[str] = []
        for sec in split_page_sections(page_content):
            sec_text = "\n".join(sec.lines).strip()
            if not sec_text:
                continue
            if sec.kind == "TABLE":
                translated = self.translate_table_section(sec_text, active_glossary_text, sp)
                translated = self.translation_quality_gate(
                    sec_text, translated, active_glossary, active_glossary_text, sp, is_table=True
                )
            else:
                translated = self.translate_general_section(sec_text, active_glossary_text, sp, page_num=page_num)
                translated = self.editorial_polish_once(sec_text, translated, active_glossary_text, sp, page_num)
                translated = self.translation_quality_gate(
                    sec_text, translated, active_glossary, active_glossary_text, sp, is_table=False
                )
            out_parts.append(translated)
        page_output = "\n\n".join(out_parts)
        if ENABLE_FINAL_PAGE_POLISH and should_run_page_level_text_gate(page_output):
            page_output = self.editorial_polish_once(page_content, page_output, active_glossary_text, sp, page_num)
        page_output = self.generic_editorial_quality_gate(page_content, page_output, active_glossary_text, sp, page_num)
        return fix_heading_body_merge(page_output)
