"""검수(코랩 셀 58 `review_page_pair` + 셀 65 의 쪽 돌기). 역할 review — 코랩은 파트와 무관하게 haiku 고정(W3).

system 은 `QA_SYSTEM_PROMPT` 그대로이고 번역 system 조립을 거치지 않는다(R/5328). 답은 첫 글 블록을 strip(R/5332) —
다리가 블록을 이은 글을 주므로 블록이 둘 이상일 때만 코랩과 갈린다(「코랩과 다른 자리」).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.glossary import (
    build_glossary_text,
    build_relevant_glossary,
    find_deterministic_glossary_violations,
)
from esgapi.translation.engines.colab_158.pages import remove_page_tag_lines
from esgapi.translation.engines.colab_158.ports import LlmGateway
from esgapi.translation.engines.colab_158.records import EngineWarning, VariantLabel
from esgapi.translation.engines.colab_158.review_rules import (
    clean_review_raw,
    extract_bilingual_korean_annotations,
    merge_review_issues,
    parse_review_json,
    sanitize_issues,
    strip_korean_bilingual_annotations,
)

SHAPE_PREFIX = "shape: "


class ReviewShapeError(Exception):
    """검수 이슈 JSON 의 값 꼴이 틀렸다(목록·객체·글자가 아닌 값, 글자가 아닌 칸) — 코랩은 같은 자리의 TypeError·
    AttributeError 로 셀 65 가 멈춘다(멈춤·`call_failed` 그대로). 글 = `shape: <원래 예외 이름>: <원래 글>` —
    호출 실패와 앞머리로 가른다(MARC-ISSUE-196 L2)."""


@dataclass(frozen=True)
class PairReview:
    """`review_page_pair` 한 번: 합친 이슈(출처와), JSON 을 읽었는가."""

    issues: list[tuple[dict[str, str], str]]
    parsed: bool


def review_page_pair(
    gateway: LlmGateway,
    source_content: str,
    translated_content: str,
    glossary: Mapping[str, str],
    page_num: int,
    variant_label: VariantLabel,
    warnings: list[EngineWarning],
    *,
    system: str,
) -> PairReview:
    """R/5262-5369. system = 검수 글(기본 `QA_SYSTEM_PROMPT` — texts.PromptTexts.review)."""
    relevant_glossary = build_relevant_glossary(glossary, source_content)
    glossary_text = build_glossary_text(relevant_glossary)
    source_for_review = f"[PAGE {page_num}]\n{remove_page_tag_lines(source_content)}"
    translated_for_model = strip_korean_bilingual_annotations(translated_content)
    translated_for_model = f"[PAGE {page_num}]\n{remove_page_tag_lines(translated_for_model)}"
    annotation_hints = extract_bilingual_korean_annotations(translated_content)
    if annotation_hints:
        annotation_hint_text = "\n".join(f"- {x}" for x in annotation_hints[:80])
    else:
        annotation_hint_text = "(No bilingual Korean annotations found on this page.)"
    user_prompt = prompts.review_user(
        variant_label, glossary_text, page_num, source_for_review, annotation_hint_text, translated_for_model
    )
    reply = gateway.complete("review", "review", system, user_prompt, prompts.MAX_TOKENS["review"])
    if reply.ending != "complete":
        code = "llm_truncated" if reply.ending == "truncated" else "llm_refused"
        warnings.append(
            EngineWarning(code=code, message=f"review: {reply.ending}", page_num=page_num, variant=variant_label)
        )
    raw = clean_review_raw(reply.text)
    llm_issues, parsed = parse_review_json(raw)
    if not parsed:
        warnings.append(
            EngineWarning(
                code="review_json_failed",
                message=f"JSON 파싱 실패 / PAGE {page_num} / STYLE {variant_label}",
                page_num=page_num,
                variant=variant_label,
            )
        )
    try:
        cleaned = sanitize_issues(llm_issues, translated_for_model, relevant_glossary=relevant_glossary)
    except (TypeError, AttributeError) as e:
        raise ReviewShapeError(f"{SHAPE_PREFIX}{type(e).__name__}: {e}") from e
    deterministic = find_deterministic_glossary_violations(source_for_review, translated_for_model, glossary)
    return PairReview(issues=merge_review_issues(deterministic, cleaned), parsed=parsed)
