"""흐름 몸(코랩 셀 7 → 49 → 52 → 57 → 65 → 67, 실패 쪽만 다시는 셀 50 → 52~67): 입력 → `TranslationRun`. 계약을 모른다.

코랩은 셀 사이에 파일을 쓰고 다시 읽는다. 그 왕복이 글에 하는 일(조각을 빈 줄 하나로 잇기, 다시 [PAGE n] 로 나누기,
줄바꿈 통일)을 그대로 한다 — 실패 쪽의 [TRANSLATION_ERROR] 줄이 앞 쪽 끝에 붙는 것도 그래서다. `time.sleep`·파일 이름·
ZIP 은 없다. CEO 쪽 한도의 `eval_js` 경고 + SystemExit 는 rejection(ceo_page_limit)이다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from esgapi.translation.engines.colab_158.autofix import Autofixer
from esgapi.translation.engines.colab_158.bilingual import attach_korean_originals
from esgapi.translation.engines.colab_158.glossary import fold_glossary, glossary_check
from esgapi.translation.engines.colab_158.pages import (
    PageChunk,
    file_roundtrip,
    filter_range,
    join_pages,
    last_wins_map,
    pages_to_map_merge,
    parse_pages,
)
from esgapi.translation.engines.colab_158.ports import LlmGateway
from esgapi.translation.engines.colab_158.records import (
    AutofixRun,
    EngineWarning,
    Fragment,
    PageReview,
    Rejection,
    ReviewIssue,
    TranslationRun,
    VariantLabel,
    VariantRun,
)
from esgapi.translation.engines.colab_158.review import ReviewShapeError, review_page_pair
from esgapi.translation.engines.colab_158.review_rules import (
    APPLY_PART_QA_AUTOFIX,
    looks_like_korean_source_for_qa,
    select_display_translation_content,
    select_review_translation_content,
    severity_counts,
    strip_korean_bilingual_annotations,
)
from esgapi.translation.engines.colab_158.structured import preprocess_structured_text
from esgapi.translation.engines.colab_158.texts import DEFAULT_TEXTS, PromptTexts
from esgapi.translation.engines.colab_158.translate import KoreanRemaining, Translator

CEO_PAGE_LIMIT = 6
"""코랩 셀 49 의 값(R/3442) — 입력 ceoPageLimit 의 코랩 기본."""


@dataclass(frozen=True)
class EngineInput:
    """엔진의 입력(계약 translation.input@1 을 흐름이 풀어 넘긴다)."""

    text: str
    company_name: str
    preferred_subject: str
    industry_standards: str
    glossary_base: tuple[tuple[str, str], ...]
    glossary_final: tuple[tuple[str, str], ...]
    part: str
    compare_ab: bool
    single_style: str
    peer_group_style_prompt: str | None
    page_start: int | None
    page_end: int | None
    ceo_page_limit: int | None
    autofix: bool
    texts: PromptTexts = DEFAULT_TEXTS
    """고칠 수 있는 글 열넷(TR4 — AI 설정 판). 번역·검수·자동수정·호출 계획이 다 이 글을 읽는다."""


def variant_labels(inputs: EngineInput) -> tuple[VariantLabel, ...]:
    return ("A", "B") if inputs.compare_ab else ("single",)


def style_prompts(inputs: EngineInput) -> list[tuple[VariantLabel, str]]:
    """R/3362-3379. A/B 면 둘, 아니면 SINGLE_STYLE(코랩은 A·B 밖이면 ValueError — 입력 꼴이 막는다)."""
    texts = inputs.texts
    if inputs.compare_ab:
        return [("A", texts.style_a), ("B", texts.style_b)]
    return [("single", texts.style_a if inputs.single_style.strip().upper() == "A" else texts.style_b)]


def _merge(pages: list[PageChunk], label: str, run: TranslationRun, variant: VariantLabel | None) -> dict[int, str]:
    merged, dups = pages_to_map_merge(pages)
    if dups:
        run.warnings.append(
            EngineWarning(code="duplicate_pages", message=f"{label} 중복 PAGE 감지 및 병합: {dups}", variant=variant)
        )
    return merged


def source_and_pages(inputs: EngineInput) -> tuple[str, list[PageChunk], Rejection | None]:
    """셀 7(받은 글의 태그 복원 — 파일 왕복으로 줄바꿈 통일)과 셀 49 의 쪽 조각·범위·한도(R/3433-3457).
    호출 계획(plan.py)도 같은 자리에서 시작한다."""
    source_text = file_roundtrip(preprocess_structured_text(inputs.text))
    pages = parse_pages(source_text)
    if inputs.page_start is not None:
        pages = [p for p in pages if p.page_num >= inputs.page_start]
    if inputs.page_end is not None:
        pages = [p for p in pages if p.page_num <= inputs.page_end]
    if not pages:
        message = "번역 대상 페이지가 없습니다. PAGE_START/PAGE_END 또는 INPUT_FILE을 확인하세요."
        return source_text, pages, Rejection(kind="no_pages", message=message)
    if inputs.part == "ceo_message" and inputs.ceo_page_limit is not None and len(pages) > inputs.ceo_page_limit:
        return (
            source_text,
            pages,
            Rejection(
                kind="ceo_page_limit",
                message="CEO 페이지 수 초과로 실행 중단",
                page_count=len(pages),
                limit=inputs.ceo_page_limit,
            ),
        )
    return source_text, pages, None


def run(inputs: EngineInput, gateway: LlmGateway) -> TranslationRun:
    labels = variant_labels(inputs)
    result = TranslationRun(part=inputs.part, variant_labels=labels)
    glossary = fold_glossary(inputs.glossary_base, inputs.glossary_final)
    source_text, pages, rejection = source_and_pages(inputs)
    result.page_numbers = [p.page_num for p in pages]
    _, result.duplicate_pages = pages_to_map_merge(parse_pages(source_text))
    if rejection is not None:
        result.rejection = rejection
        return result

    translator = _translator(inputs, gateway, result)
    variants: dict[VariantLabel, VariantRun] = {label: VariantRun(label=label) for label in labels}
    outputs: dict[VariantLabel, list[str]] = {label: [] for label in labels}
    for page in pages:
        done, error = _translate_page(inputs, translator, variants, page.content, page.page_num, glossary)
        for label in labels:
            if error is None:
                outputs[label].append(done[label])
            else:
                outputs[label].append(f"[TRANSLATION_ERROR page={page.page_num}]\n" + page.content)
    translator.variant = None
    translator.page_num = None

    # 셀 49 의 파일 쓰기
    texts: dict[VariantLabel, str] = {label: file_roundtrip(join_pages(outputs[label])) for label in labels}
    return _after_translation(inputs, gateway, result, variants, texts, source_text, glossary)


def retry(
    inputs: EngineInput, gateway: LlmGateway, base: Mapping[VariantLabel, str], pages: Sequence[int]
) -> TranslationRun:
    """셀 50(실패 페이지만 재번역, R/3560-3616) 뒤 셀 52~67. base = 앞 실행의 문체별 번역 글(자동수정 전 — 셀 49 가 쓴
    파일). 원문 지도는 `parse_pages(원문)` 을 번호로(뒤 조각이 이김, 범위 거름 없음 — R/3568-3569), base 도 같은 꼴.
    고른 쪽마다 모든 문체를 한 try 로 — 하나라도 예외면 그 쪽은 전 문체 옛 글(코랩 print → 경고 retry_failed). 원문에
    없는 쪽은 retry_page_missing. 번호 차례로 빈 줄 하나로 이어 셀 52~67 을 전 쪽에 돈다.
    옛 `[TRANSLATION_ERROR page=n]` 줄이 `parse_pages` 로 앞 쪽 꼬리에 남는 것은 코랩 약점 그대로(MARC-ENT-297).
    fragments 는 다시 번역한 쪽만."""
    labels = variant_labels(inputs)
    result = TranslationRun(part=inputs.part, variant_labels=labels)
    glossary = fold_glossary(inputs.glossary_base, inputs.glossary_final)
    source_text, chunks, rejection = source_and_pages(inputs)
    result.page_numbers = [p.page_num for p in chunks]
    _, result.duplicate_pages = pages_to_map_merge(parse_pages(source_text))
    if rejection is not None:
        result.rejection = rejection
        return result

    source_map = last_wins_map(parse_pages(source_text))
    translated_maps = {label: last_wins_map(parse_pages(base[label])) for label in labels}
    translator = _translator(inputs, gateway, result)
    variants: dict[VariantLabel, VariantRun] = {label: VariantRun(label=label) for label in labels}
    for pnum in pages:
        if pnum not in source_map:
            result.warnings.append(
                EngineWarning("retry_page_missing", f"PAGE {pnum}: 원문에서 찾을 수 없음, 건너뜀", pnum)
            )
            continue
        done, error = _translate_page(inputs, translator, variants, source_map[pnum], pnum, glossary)
        if error is None:
            for label in labels:
                translated_maps[label][pnum] = done[label]
        else:
            result.warnings.append(EngineWarning("retry_failed", f"PAGE {pnum} 오류: {error}", pnum))
    translator.variant = None
    translator.page_num = None

    texts: dict[VariantLabel, str] = {
        label: file_roundtrip(join_pages([translated_maps[label][k] for k in sorted(translated_maps[label])]))
        for label in labels
    }
    return _after_translation(inputs, gateway, result, variants, texts, source_text, glossary)


def _translator(inputs: EngineInput, gateway: LlmGateway, result: TranslationRun) -> Translator:
    company_style = inputs.texts.company_style(
        inputs.part,
        inputs.company_name,
        inputs.preferred_subject,
        inputs.industry_standards,
        inputs.peer_group_style_prompt,
    )
    return Translator(
        gateway,
        part=inputs.part,
        company_style_prompt=company_style,
        industry_standards=inputs.industry_standards,
        warnings=result.warnings,
        texts=inputs.texts,
    )


def _translate_page(
    inputs: EngineInput,
    translator: Translator,
    variants: dict[VariantLabel, VariantRun],
    content: str,
    page_num: int,
    glossary: dict[str, str],
) -> tuple[dict[VariantLabel, str], str | None]:
    """쪽 하나를 모든 문체로(코랩 `translate_page` 와 그 except — R/3483-3500). 문체마다 조각 하나를 적는다."""
    translator.page_num = page_num
    done: dict[VariantLabel, str] = {}
    qa: dict[VariantLabel, int] = {}
    error: str | None = None
    remaining: tuple[str, ...] = ()
    try:
        for label, style_prompt in style_prompts(inputs):
            translator.variant = label
            before = len(translator.qa_logs)
            done[label] = translator.translate_one_style(content, glossary, page_num, style_prompt)
            if len(translator.qa_logs) > before:
                qa[label] = len(translator.qa_logs) - 1
    except Exception as e:  # 코랩 R/3497 의 except Exception(W7)
        error = str(e)
        if isinstance(e, KoreanRemaining):
            remaining = e.remaining
    for label in variants:
        log = translator.qa_logs[qa[label]] if label in qa else None
        variants[label].fragments.append(
            Fragment(
                page_num=page_num,
                status="translated" if error is None else "error",
                error=error,
                editorial_qa=log,
                remaining_korean=remaining,
            )
        )
    return done, error


def _after_translation(
    inputs: EngineInput,
    gateway: LlmGateway,
    result: TranslationRun,
    variants: dict[VariantLabel, VariantRun],
    texts: dict[VariantLabel, str],
    source_text: str,
    glossary: dict[str, str],
) -> TranslationRun:
    """셀 52~67: 병기 → 반영 검사 → 검수 → 자동수정. texts = 셀 49(또는 50)가 쓴 문체별 번역 파일의 글."""
    labels = result.variant_labels
    # 셀 57 반영 검사는 그 실행 쪽 범위 · 같은 번호 합침(코랩과 다름, MARC-ENT-451). 합침 경고는 셀 65 가 단다
    glossary_source_map = filter_range(
        pages_to_map_merge(parse_pages(source_text))[0], inputs.page_start, inputs.page_end
    )
    # 셀 52 병기
    for label in labels:
        variant = variants[label]
        variant.translated_text = texts[label]
        variant.bilingual_text = attach_korean_originals(variant.translated_text, source_text)
        # 셀 57: 반영 검사
        bilingual_map = pages_to_map_merge(parse_pages(variant.bilingual_text))[0]
        misses = glossary_check(
            glossary_source_map, filter_range(bilingual_map, inputs.page_start, inputs.page_end), glossary
        )
        variant.glossary_misses = [(m.page_num, m.term_kr, m.term_en, m.source_count) for m in misses]
        result.variants.append(variant)

    # 셀 65: 검수
    source_map = filter_range(
        _merge(parse_pages(source_text), "원문", result, None), inputs.page_start, inputs.page_end
    )
    issues_by_variant: dict[VariantLabel, dict[int, list[dict[str, str]]]] = {}
    stopped = False
    skipped: set[VariantLabel] = set()
    for variant in result.variants:
        label = variant.label
        bilingual_map = filter_range(
            _merge(parse_pages(variant.bilingual_text), f"병기 번역 {label}", result, label),
            inputs.page_start,
            inputs.page_end,
        )
        raw_map = filter_range(
            _merge(parse_pages(variant.translated_text), f"raw 영문 번역 {label}", result, label),
            inputs.page_start,
            inputs.page_end,
        )
        if not bilingual_map and not raw_map:
            # R/6209-6211: 두 map 이 다 비면 그 문체를 건너뛴다(PART_QA_RESULTS 에 안 들어가 자동수정도 안 돈다)
            result.warnings.append(
                EngineWarning("review_skipped", f"{label}: 병기 txt/raw txt 모두 없음", variant=label)
            )
            skipped.add(label)
            continue
        review_keys = set(bilingual_map) | set(raw_map)
        common = sorted(set(source_map) & review_keys)
        missing = sorted(set(source_map) - review_keys)
        extra = sorted(review_keys - set(source_map))
        if missing:
            result.warnings.append(
                EngineWarning("review_missing_pages", f"번역 txt에 없는 원문 페이지: {missing}", variant=label)
            )
        if extra:
            result.warnings.append(
                EngineWarning("review_extra_pages", f"원문 txt에 없는 번역 페이지: {extra}", variant=label)
            )
        by_page: dict[int, list[dict[str, str]]] = {}
        for pnum in common:
            bilingual_content = (bilingual_map.get(pnum) or "").strip()
            review_content = select_review_translation_content(pnum, bilingual_map, raw_map)
            display = select_display_translation_content(pnum, raw_map, bilingual_map)
            if (
                bilingual_content
                and looks_like_korean_source_for_qa(bilingual_content)
                and (raw_map.get(pnum) or "").strip()
            ):
                result.warnings.append(
                    EngineWarning(
                        "review_bilingual_looks_korean",
                        f"PAGE {pnum}: 병기 txt가 국문 원문처럼 보여 raw 로 대체",
                        pnum,
                        label,
                    )
                )
            if (
                not (raw_map.get(pnum) or "").strip()
                and display
                and looks_like_korean_source_for_qa(strip_korean_bilingual_annotations(bilingual_content).strip())
            ):
                result.warnings.append(
                    EngineWarning(
                        "review_display_looks_korean", f"PAGE {pnum}: 표시용 번역문이 국문 원문처럼 보임", pnum, label
                    )
                )
            bilingual_page = bilingual_map.get(pnum, "")
            if stopped:
                variant.pages.append(PageReview(pnum, display, bilingual_page, "not_run", (), None))
                continue
            try:
                pair = review_page_pair(
                    gateway,
                    source_map[pnum],
                    review_content,
                    glossary,
                    pnum,
                    label,
                    result.warnings,
                    system=inputs.texts.review,
                )
            except Exception as e:  # 코랩 셀 65 는 여기서 멈춘다(호출 실패·이슈 JSON 의 꼴 오류)
                stopped = True
                message = str(e) if isinstance(e, ReviewShapeError) else f"{type(e).__name__}: {e}"
                variant.pages.append(PageReview(pnum, display, bilingual_page, "call_failed", (), message))
                continue
            issues = tuple(
                ReviewIssue(
                    issue_type=i["issue_type"],
                    severity=i["severity"],
                    original_span=i["original_span"],
                    suggestion=i["suggestion"],
                    reason=i["reason"],
                    source="glossary_rule" if source == "glossary_rule" else "model",
                )
                for i, source in pair.issues
            )
            by_page[pnum] = [i for i, _ in pair.issues]
            variant.pages.append(
                PageReview(
                    pnum,
                    display,
                    bilingual_page,
                    "reviewed" if pair.parsed else "parse_failed",
                    issues,
                    None,
                    tuple(by_page[pnum]),
                    severity_counts(by_page[pnum]),
                )
            )
        issues_by_variant[label] = by_page
        if stopped:
            for later in result.variants[result.variants.index(variant) + 1 :]:
                _not_run_reviews(later, source_map, inputs)
            break

    # 셀 67: 자동수정
    if not (inputs.autofix and APPLY_PART_QA_AUTOFIX):
        return result
    if stopped:
        for variant in result.variants:
            variant.autofix = AutofixRun(status="not_run", not_run_reason="review_stopped")
        return result
    fix_source_map = filter_range(
        _merge(parse_pages(source_text), "원문", result, None), inputs.page_start, inputs.page_end
    )
    halted = False
    for variant in result.variants:
        if halted:
            variant.autofix = AutofixRun(status="not_run", not_run_reason="earlier_variant_stopped")
            continue
        if variant.label in skipped:
            variant.autofix = AutofixRun(status="not_run", not_run_reason="review_stopped")
            continue
        raw_map = filter_range(
            _merge(parse_pages(variant.translated_text), f"raw 번역 {variant.label}", result, variant.label),
            inputs.page_start,
            inputs.page_end,
        )
        fixer = Autofixer(gateway, glossary, variant.label, result.warnings, texts=inputs.texts)
        variant.autofix = fixer.run(fix_source_map, raw_map, issues_by_variant.get(variant.label, {}), source_text)
        halted = variant.autofix.status == "stopped"
    return result


def _not_run_reviews(variant: VariantRun, source_map: dict[int, str], inputs: EngineInput) -> None:
    """검수가 앞 문체에서 멈췄을 때 뒤 문체의 쪽(코랩은 그 문체를 돌지 않는다 — 쪽만 not_run 으로 적는다)."""
    raw_map = filter_range(
        pages_to_map_merge(parse_pages(variant.translated_text))[0], inputs.page_start, inputs.page_end
    )
    bilingual_map = filter_range(
        pages_to_map_merge(parse_pages(variant.bilingual_text))[0], inputs.page_start, inputs.page_end
    )
    for pnum in sorted(set(source_map) & (set(raw_map) | set(bilingual_map))):
        display = select_display_translation_content(pnum, raw_map, bilingual_map)
        variant.pages.append(PageReview(pnum, display, bilingual_map.get(pnum, ""), "not_run", (), None))
