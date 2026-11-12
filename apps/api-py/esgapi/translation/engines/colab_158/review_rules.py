"""검수·자동수정의 결정적 몫: 셀 58 의 병기 걷기·이슈 거름(`sanitize_issues`), 셀 65 의 쪽 내용 고르기, 셀 67 의 설명문
걷기·직접 치환·이슈 거름. LLM 몫은 review.py·autofix.py 다.

모델 이슈는 JSON 그대로라 값의 꼴이 정해져 있지 않다. 코랩이 (issue.get(k) or 기본).strip() 처럼 글자 메서드를 부르는
자리에서 값이 글자가 아니면 코랩은 AttributeError 로 멈춘다 — `_text_or` 가 같은 자리에서 같은 예외를 낸다.
"""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import cast

from esgapi.translation.engines.colab_158.gates import collect_untranslated_korean_lines, has_ko

type Issue = dict[str, object]


def _text_or(value: object, default: str) -> str:
    """`(value or default).strip()` — 값이 거짓이면 기본, 글자면 strip, 그 밖은 코랩처럼 AttributeError."""
    picked = value or default
    if not isinstance(picked, str):
        raise AttributeError(f"'{type(picked).__name__}' object has no attribute 'strip'")
    return picked.strip()


def _json_object(value: object) -> dict[str, object] | None:
    """JSON 객체(dict)면 그것, 아니면 None. JSON 의 키는 늘 글자다."""
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def strip_korean_bilingual_annotations(text: str) -> str:
    """R/5042-5053. 줄마다 국문이 든 괄호(앞 빈칸 포함)를 지운다."""
    return "\n".join(re.sub(r"\s*\([^)]*[가-힣][^)]*\)", "", line) for line in text.splitlines())


def extract_bilingual_korean_annotations(text: str | None, max_items: int = 80) -> list[str]:
    """R/5056-5069."""
    anns: list[str] = []
    for m in re.finditer(r"\(([^)]*[가-힣][^)]*)\)", text or ""):
        s = re.sub(r"\s+", " ", m.group(1)).strip()
        if s and s not in anns:
            anns.append(s)
        if len(anns) >= max_items:
            break
    return anns


SOURCE_ABSENT_PATTERNS = [
    "원문에 없",
    "원본에 없",
    "원문에는 없",
    "원본에는 없",
    "원문에서 확인",
    "원본에서 확인",
    "출처가 없",
    "근거가 없",
    "korean source does not",
    "not in the korean source",
    "not found in the source",
    "unsupported",
    "hallucination",
    "source missing",
]

ALLOWED_ISSUE_TYPES = frozenset(
    {
        "GLOSSARY_VIOLATION",
        "TERMINOLOGY_INCONSISTENCY",
        "TAG_MODIFIED",
        "OMISSION",
        "UNTRANSLATED",
        "NUMBER_UNIT_ERROR",
        "GRAMMAR",
        "UNNATURAL",
        "TABLE_CONTENT",
        "VISUAL_CONTENT",
    }
)


def is_source_absent_only_false_positive(item: Mapping[str, str]) -> bool:
    """R/5092-5115."""
    itype = (item.get("issue_type") or "").strip()
    combined = " ".join(
        [str(item.get("reason") or ""), str(item.get("suggestion") or ""), str(item.get("original_span") or "")]
    ).lower()
    if not any(p.lower() in combined for p in SOURCE_ABSENT_PATTERNS):
        return False
    if itype in {"UNNATURAL", "TABLE_CONTENT", "VISUAL_CONTENT", "GRAMMAR"}:
        if re.search(r"\d|%|원|명|건|년|월|등급|grade|rating|amount|number|unit", combined):  # noqa: SIM103 — 코랩 꼴 그대로
            return False
        return True
    return False


def normalize_issue_text_for_compare(text: str | None) -> str:
    """R/5123-5134."""
    if text is None:
        return ""
    t = str(text).strip().lower()
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", t)


def normalize_glossary_compare(text: str | None) -> str:
    """R/5136-5149."""
    if text is None:
        return ""
    t = str(text)
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", t).strip().lower()


def contains_glossary_value(text: str, glossary: Mapping[str, str]) -> list[str]:
    """R/5152-5168."""
    if not text or not glossary:
        return []
    norm_text = normalize_glossary_compare(text)
    found: list[str] = []
    for en in glossary.values():
        norm_en = normalize_glossary_compare(en)
        if norm_en and norm_en in norm_text:
            found.append(en)
    return found


def suggestion_preserves_glossary_values(original_span: str, suggestion: str, glossary: Mapping[str, str]) -> bool:
    """R/5171-5188."""
    values = contains_glossary_value(original_span, glossary)
    if not values:
        return True
    norm_suggestion = normalize_glossary_compare(suggestion)
    for en in values:
        norm_en = normalize_glossary_compare(en)
        if norm_en and norm_en not in norm_suggestion:
            return False
    return True


CONSISTENCY_KEYWORDS = [
    "일관",
    "통일",
    "다르게 번역",
    "서로 다른",
    "혼용",
    "inconsistent",
    "consistency",
    "different english",
    "multiple english",
]


def sanitize_issues(
    issues: object, translated_content: str, relevant_glossary: Mapping[str, str] | None = None
) -> list[dict[str, str]]:
    """R/5190-5260. `issues` 는 검수 모델의 JSON 그대로(목록이 아니면 코랩처럼 그 원소를 돈다 — dict 면 키, 글자면 글자,
    수면 TypeError)."""
    cleaned: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    glossary: Mapping[str, str] = relevant_glossary if relevant_glossary is not None else {}
    if not isinstance(issues, list | dict | str):
        raise TypeError(f"'{type(issues).__name__}' object is not iterable")
    elements = cast("Iterable[object]", issues)  # dict 면 키, 글자면 글자 — 아래에서 dict 가 아니라 걸러진다
    for element in elements:
        raw = _json_object(element)
        if raw is None:
            continue
        itype = _text_or(raw.get("issue_type"), "UNNATURAL").upper()
        if itype not in ALLOWED_ISSUE_TYPES:
            continue
        span = _text_or(raw.get("original_span"), "")
        if span and span not in translated_content:
            span = ""
        item = {
            "issue_type": itype,
            "severity": _text_or(raw.get("severity"), "MEDIUM").upper(),
            "original_span": span,
            "suggestion": _text_or(raw.get("suggestion"), ""),
            "reason": _text_or(raw.get("reason"), ""),
        }
        if item["original_span"] and item["suggestion"]:  # noqa: SIM102 — 코랩 꼴 그대로
            if normalize_issue_text_for_compare(item["original_span"]) == normalize_issue_text_for_compare(
                item["suggestion"]
            ):
                continue
        if item["issue_type"] in {"UNNATURAL", "GRAMMAR", "TERMINOLOGY_INCONSISTENCY"}:  # noqa: SIM102 — 코랩 꼴 그대로
            if item["original_span"] and item["suggestion"]:  # noqa: SIM102 — 코랩 꼴 그대로
                if not suggestion_preserves_glossary_values(item["original_span"], item["suggestion"], glossary):
                    continue
        if is_source_absent_only_false_positive(item):
            continue
        if item["issue_type"] == "TERMINOLOGY_INCONSISTENCY":
            combined = f"{item['suggestion']} {item['reason']}".lower()
            if not any(k in combined for k in CONSISTENCY_KEYWORDS):
                continue
        key = (item["issue_type"], item["severity"], item["original_span"], item["suggestion"], item["reason"])
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def merge_review_issues(
    deterministic: Sequence[dict[str, str]], llm: Sequence[dict[str, str]]
) -> list[tuple[dict[str, str], str]]:
    """R/5352-5369. 용어집 검사 이슈가 앞, 같은 다섯 칸은 하나. 이슈마다 출처(glossary_rule·model)를 붙여 돌려준다."""
    merged: list[tuple[dict[str, str], str]] = []
    seen: set[tuple[str, ...]] = set()
    for issue, source in [*((d, "glossary_rule") for d in deterministic), *((m, "model") for m in llm)]:
        key = tuple(issue.get(k, "") for k in ("issue_type", "severity", "original_span", "suggestion", "reason"))
        if key in seen:
            continue
        seen.add(key)
        merged.append((issue, source))
    return merged


def clean_review_raw(raw: str) -> str:
    """R/5332-5333 의 울타리 걷기(첫 블록 글을 strip 한 뒤)."""
    return re.sub(r"^```json|^```|```$", "", raw.strip(), flags=re.MULTILINE).strip()


def parse_review_json(raw: str) -> tuple[object, bool]:
    """R/5335-5340. (읽은 값, 읽었는가). 못 읽으면 ([], False) — 코랩 W8(print 뿐, 이슈 0)."""
    try:
        return json.loads(raw), True
    except json.JSONDecodeError:
        return [], False


def severity_counts(issues: Sequence[Mapping[str, str]]) -> tuple[int, int, int]:
    """R/5571-5574(QA Word 요약표): 글자가 정확히 HIGH·MEDIUM·LOW 인 것만."""
    sev = [i.get("severity") for i in issues]
    return sev.count("HIGH"), sev.count("MEDIUM"), sev.count("LOW")


# ── 셀 65: 쪽 내용 고르기 ──


def count_hangul_chars(text: str | None) -> int:
    return len(re.findall(r"[가-힣]", str(text or "")))


def count_latin_chars(text: str | None) -> int:
    return len(re.findall(r"[A-Za-z]", str(text or "")))


def remove_structure_tags_for_qa(text: str | None) -> str:
    """R/6086-6096."""
    lines: list[str] = []
    for line in str(text or "").splitlines():
        s = line.strip()
        if re.fullmatch(r"\[[A-Z_]+(?:\s+\d+)?\]", s, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\[PAGE\s+\d+\]", s, flags=re.IGNORECASE):
            continue
        lines.append(line)
    return "\n".join(lines)


def looks_like_korean_source_for_qa(text: str | None) -> bool:
    """R/6099-6108."""
    body = remove_structure_tags_for_qa(text)
    h = count_hangul_chars(body)
    e = count_latin_chars(body)
    return h >= 30 and h > max(e * 1.3, 20)


def select_review_translation_content(pnum: int, bilingual_map: Mapping[int, str], raw_map: Mapping[int, str]) -> str:
    """R/6133-6150. 병기 쪽이 국문 원문처럼 보이면 raw 영문 쪽."""
    bilingual_content = (bilingual_map.get(pnum) or "").strip()
    raw_content = (raw_map.get(pnum) or "").strip()
    if bilingual_content and not looks_like_korean_source_for_qa(bilingual_content):
        return bilingual_content
    if raw_content:
        return raw_content
    return bilingual_content


def select_display_translation_content(pnum: int, raw_map: Mapping[int, str], bilingual_map: Mapping[int, str]) -> str:
    """R/6153-6169. raw 영문 쪽이 먼저, 없으면 병기를 걷은 글."""
    raw_content = (raw_map.get(pnum) or "").strip()
    bilingual_content = (bilingual_map.get(pnum) or "").strip()
    if raw_content:
        return raw_content
    return strip_korean_bilingual_annotations(bilingual_content).strip()


# ── 셀 67: 자동수정의 결정적 몫 ──

APPLY_PART_QA_AUTOFIX = True
PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS = 1
STRICT_FAIL_ON_REMAINING_KOREAN_AFTER_PART_QA_AUTOFIX = True
PART_QA_AUTOFIX_ISSUE_TYPES = ALLOWED_ISSUE_TYPES
"""R/6372-6383 — 검수의 열 유형과 같은 집합."""


def strip_code_fence(text: str | None) -> str:
    """R/6399-6403."""
    t = str(text or "").strip()
    t = re.sub(r"^```(?:text|markdown)?", "", t, flags=re.IGNORECASE).strip()
    return re.sub(r"```$", "", t).strip()


EXPLANATION_PATTERNS = [
    r"The Korean source shows",
    r"The Korean source",
    r"The table header should be",
    r"The category labels should be",
    r"The corrected translation",
    r"Here is",
    r"I have corrected",
    r"Explanation:",
    r"Note:",
    r"to match the Korean table title",
    r"should be",
]


def clean_llm_explanation_lines(text: str | None) -> str:
    """R/6405-6461."""
    cleaned: list[str] = []
    skipping = False
    for line in str(text or "").splitlines():
        s = line.strip()
        if not s:
            skipping = False
            cleaned.append(line)
            continue
        if re.match(r"^\[[A-Z_]+(?:\s+\d+)?\]$", s, flags=re.IGNORECASE):
            skipping = False
            cleaned.append(line)
            continue
        if any(re.search(p, s, flags=re.IGNORECASE) for p in EXPLANATION_PATTERNS):
            skipping = True
            continue
        if re.match(r"^[-•]\s*(The Korean source|The table header|The category labels)", s, flags=re.IGNORECASE):
            skipping = True
            continue
        if skipping:
            if re.match(r"^(and|the|these|this|therefore|so|it)\b", s, flags=re.IGNORECASE):
                continue
            if re.search(r"[가-힣]", s) and re.search(
                r"(should|Korean|source|table|label|title)", s, flags=re.IGNORECASE
            ):
                continue
            skipping = False
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def ensure_page_tag(text: str | None, pnum: int) -> str:
    """R/6490-6494."""
    t = str(text or "").strip()
    if not re.search(rf"^\[PAGE\s+{pnum}\]\s*$", t, flags=re.IGNORECASE | re.MULTILINE):
        t = f"[PAGE {pnum}]\n" + re.sub(r"^\[PAGE\s+\d+\]\s*\n?", "", t, flags=re.IGNORECASE)
    return t.strip()


def extract_only_corrected_page_text(text: str, page_num: int) -> str:
    """R/6464-6486."""
    t = strip_code_fence(text)
    m = re.search(rf"^\s*\[PAGE\s+{page_num}\]\s*$", t, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        t = t[m.start() :].strip()
    next_page = re.search(rf"^\s*\[PAGE\s+(?!{page_num}\b)\d+\]\s*$", t, flags=re.IGNORECASE | re.MULTILINE)
    if next_page:
        t = t[: next_page.start()].strip()
    t = clean_llm_explanation_lines(t)
    return ensure_page_tag(t, page_num)


def collect_remaining_korean_lines_in_english(text: str | None, max_items: int = 40) -> list[str]:
    """R/6510-6532 — 셀 46 의 한국어 잔존 셈과 같은 셈이다."""
    return collect_untranslated_korean_lines(text, max_items=max_items)


def filter_actionable_issues(issues: Sequence[object] | None) -> list[Issue]:
    """R/6535-6552. 자동수정 유형이고 제안·구간·이유 가운데 하나라도 있는 이슈. 값은 str() 로 본다."""
    out: list[Issue] = []
    for issue in issues or []:
        found = _json_object(issue)
        if found is None:
            continue
        raw = dict(found)
        itype = str(raw.get("issue_type") or "").strip().upper()
        if itype not in PART_QA_AUTOFIX_ISSUE_TYPES:
            continue
        suggestion = str(raw.get("suggestion") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        span = str(raw.get("original_span") or "").strip()
        if not (suggestion or span or reason):
            continue
        raw["issue_type"] = itype
        out.append(raw)
    return out


def select_part_issues_for_page(part_issues: Sequence[Issue], page_text: str) -> list[Issue]:
    """R/6555-6571. 코랩에서 파트 이슈는 늘 빈 목록이다(W4 — R/6870)."""
    selected: list[object] = []
    for issue in part_issues:
        span = str(issue.get("original_span") or "").strip()
        if span:
            if span in page_text:
                selected.append(issue)
        else:
            selected.append(issue)
    return filter_actionable_issues(selected)


BAD_SUGGESTION_PATTERNS = [
    r"The Korean source shows",
    r"The Korean source",
    r"The table header should be",
    r"The category labels should be",
    r"should be translated",
    r"should be changed",
    r"to match the Korean",
    r"corrected translation",
    r"Here is",
    r"Explanation",
    r"Note:",
]


def looks_like_explanation_or_bad_suggestion(text: str | None) -> bool:
    """R/6574-6611."""
    s = str(text or "").strip()
    if not s:
        return True
    if any(re.search(p, s, flags=re.IGNORECASE) for p in BAD_SUGGESTION_PATTERNS):
        return True
    if re.search(r"[가-힣]", s):
        return True
    if len(s) > 180:
        return True
    return "\n" in s or "\r" in s


def simple_span_replacements(text: str | None, issues: Sequence[Issue]) -> tuple[str, list[dict[str, str]]]:
    """R/6614-6644. 구간이 글에 있으면 전부 바꾼다(`str.replace`). 적용 기록의 issue_type 은 str() 로."""
    out = str(text or "")
    applied: list[dict[str, str]] = []
    for issue in issues:
        span = str(issue.get("original_span") or "").strip()
        suggestion = str(issue.get("suggestion") or "").strip()
        if not span or not suggestion:
            continue
        if span == suggestion:
            continue
        if looks_like_explanation_or_bad_suggestion(suggestion):
            continue
        if span in out:
            out = out.replace(span, suggestion)
            applied.append(
                {"issue_type": str(issue.get("issue_type")), "original_span": span, "suggestion": suggestion}
            )
    return out, applied


UNTRANSLATED_FALLBACK_ISSUE: Issue = {
    "issue_type": "UNTRANSLATED",
    "severity": "HIGH",
    "original_span": "",
    "suggestion": "Translate all remaining Korean text into English.",
    "reason": "Raw English translation still contains Korean Hangul text.",
}
"""R/6883-6889 — 이슈가 없는데 한국어가 남은 쪽에 넣는 이슈."""


def page_has_korean(text: str) -> bool:
    return has_ko(text)
