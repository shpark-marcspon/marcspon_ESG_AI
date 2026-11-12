"""용어집(코랩 셀 14·15·57): 짝 목록 접기, 정확 매칭, 결정적 위반 검사, 반영 검사 보고.

R/375-388 의 쓰는 곳 0 함수와 그 결과 상수는 옮기지 않는다(D1 — 함수 이름에 실재 기업 이름 조각). 셀 11 의
`build_glossary_text` 는 셀 15 판이 덮는다(마지막 정의가 이긴다).
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

type Glossary = dict[str, str]
"""국문 key → 영문 value. 넣은 차례가 뜻을 가진다(길이가 같은 key 의 정렬 차례)."""


def fold_glossary(base: Iterable[tuple[str, str]], final: Iterable[tuple[str, str]]) -> Glossary:
    """`{**GLOSSARY, **FINAL_GLOSSARY}`(R/368-372) — 같은 key 는 자리는 base, 값은 final. 목록 안 같은 key 는
    dict 처럼 뒤가 이긴다(자리는 처음 나온 곳)."""
    folded: Glossary = {}
    for ko, en in base:
        folded[ko] = en
    for ko, en in final:
        folded[ko] = en
    return folded


def normalize_space(text: str | None) -> str:
    """R/412-428."""
    if text is None:
        return ""
    t = str(text)
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"[\u200b\u200c\u200d]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def glossary_source_term_present(term_kr: str, source_text: str) -> bool:
    """R/431-442. 부분 매칭을 추론하지 않는다(`in` 그대로)."""
    if not term_kr or not source_text:
        return False
    return term_kr in source_text


def target_term_present(expected_en: str, translated_text: str) -> bool:
    """R/445-466. 대소문자·줄바꿈/연속 공백 차이만 허용."""
    if not expected_en:
        return True
    expected_norm = normalize_space(expected_en).lower()
    translated_norm = normalize_space(translated_text).lower()
    if not expected_norm:
        return True
    return expected_norm in translated_norm


def build_relevant_glossary(glossary: Mapping[str, str], source_text: str) -> Glossary:
    """R/469-484. 원문에 key 가 정확히 나온 짝만, key 길이 내림차순(안정 정렬 — 같은 길이는 넣은 차례)."""
    if not glossary:
        return {}
    items: list[tuple[str, str]] = []
    for kr, en in glossary.items():
        if glossary_source_term_present(kr, source_text):
            items.append((kr, en))
    items.sort(key=lambda x: len(x[0]), reverse=True)
    return dict(items)


def build_glossary_text(glossary: Mapping[str, str]) -> str:
    """셀 15 판(R/487-498)."""
    if not glossary:
        return "(No relevant glossary terms for this source text.)"
    items = sorted(glossary.items(), key=lambda x: len(x[0]), reverse=True)
    return "\n".join(f"- {k} -> {v}" for k, v in items)


def find_deterministic_glossary_violations(
    source_content: str, translated_content: str, glossary: Mapping[str, str]
) -> list[dict[str, str]]:
    """R/501-527. 이슈의 글자(제안·이유)는 코랩 그대로."""
    relevant_glossary = build_relevant_glossary(glossary, source_content)
    issues: list[dict[str, str]] = []
    for kr, expected_en in relevant_glossary.items():
        if target_term_present(expected_en, translated_content):
            continue
        issues.append(
            {
                "issue_type": "GLOSSARY_VIOLATION",
                "severity": "HIGH",
                "original_span": "",
                "suggestion": f"'{kr}'는 용어집에 따라 '{expected_en}'로 그대로 통일하는 것이 좋습니다.",
                "reason": (
                    f"원문에 용어집 용어 '{kr}'가 정확히 등장하지만, "
                    f"번역문에서 지정 번역어 '{expected_en}'가 확인되지 않았습니다. "
                    f"용어집 value는 대소문자와 줄바꿈/공백 차이를 제외하고 그대로 반영되어야 합니다."
                ),
            }
        )
    return issues


@dataclass(frozen=True)
class GlossaryMiss:
    """반영 검사의 미반영 하나(코랩 셀 57 의 violations 한 줄)."""

    page_num: int
    term_kr: str
    term_en: str
    source_count: int


def glossary_check(
    source_map: Mapping[int, str], translated_map: Mapping[int, str], glossary: Mapping[str, str]
) -> list[GlossaryMiss]:
    """셀 57(R/4975-5019)의 반영 검사. 원문 쪽(그 실행 쪽 범위로 거르고 같은 번호 조각을 합친 map)마다, 번역 쪽(같은
    번호를 합친 map, 없으면 빈 글)에 value 가 없으면 하나. 보고만 한다. 코랩과 다름(코랩은 원문 전체·번역은 뒤 조각이
    이김) — `MARC-ENT-451`."""
    misses: list[GlossaryMiss] = []
    for page_num, content in source_map.items():
        translated_content = translated_map.get(page_num, "")
        relevant_glossary = build_relevant_glossary(glossary, content)
        for term_kr, term_en in relevant_glossary.items():
            if not target_term_present(term_en, translated_content):
                misses.append(
                    GlossaryMiss(
                        page_num=page_num,
                        term_kr=term_kr,
                        term_en=term_en,
                        source_count=content.count(term_kr),
                    )
                )
    return misses
