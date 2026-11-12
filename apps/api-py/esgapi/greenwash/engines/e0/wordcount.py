# pyright: basic
# ruff: noqa: SIM108, UP006, UP035
# ↑ GW1 사본이라 본문을 고치지 않는다(AST 대조). 끈 규칙은 이 파일이 실제로 어기는 것만:
#   if-else 블록; typing.List 꼴; typing 의 옛 이름
"""의심 낱말 목록과 낱말 세기(AI 없음).

노트북(AI그린워싱 점검_E0의 사본.ipynb)의 셀 22·24 소스에서 기계로 뽑아 글자 그대로 옮겼다.
흠을 고치지 않는다(py/greenwash/README.md 의 「일부러 남긴 흠」). 원본 대조(tests/notebook_probe.py)가 같음을 잰다.
"""

import re
from collections import Counter
from typing import Dict, List, Tuple

GREEN_TERMS = [
    "친환경",
    "저탄소",
    "탄소중립",
    "기후중립",
    "지속가능",
    "생분해",
    "광분해",
    "자연분해",
    "그린",
    "green",
    "녹색",
    "에코",
    "eco프리",
    "free",
    "제로",
    "zero",
    "무첨가",
    "천연",
    "유기농자연친화",
    "환경친화",
    "자연적",
    "동물친화",
    "동물보호청정기술",
    "청정에너지",
    "청정연료",
    "청정전력",
    "클린",
    "clean",
    "무공해",
    "플라스틱 중립",
    "탈플라스틱",
    "바이오",
    "bio",
    "산림벌채 중단",
    "최초",
    "유일",
    "최고",
]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    t = text.lower()

    # 하이픈/언더바/중점/슬래시 등을 공백으로 통일 (net-zero, net/zero 등)
    t = re.sub(r"[\-_/·•∙]", " ", t)

    # 괄호/따옴표 등은 공백 처리
    t = re.sub(r"[(){}\[\]\"'“”‘’]", " ", t)

    # 공백 정리
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_term(term: str) -> str:
    if not term:
        return ""
    t = term.lower().strip()
    t = re.sub(r"[\-_/·•∙]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_flexible_pattern(term: str) -> re.Pattern:
    """
    term을 받아 유연하게 매칭하는 regex를 만든다.

    규칙:
    - term 내부 공백을 \\s*로 바꿔서 띄어쓰기 변형 허용
      예) "탄소 중립" -> "탄\\s*소\\s*중\\s*립"
    - 영문/숫자 포함 구문도 공백 변형 허용
      예) "net zero" -> "net\\s*zero"
    - term이 너무 짧으면(예: '청정') 오탐이 많아지므로:
      * 기본적으로 단어 경계(\b) 또는 한글 경계 유사 처리 적용
    """
    t = normalize_term(term)
    if not t:
        return re.compile(r"$^")  # match nothing

    parts = t.split(" ")
    escaped_parts = [re.escape(p) for p in parts if p]
    core = r"\s*".join(escaped_parts)

    # 오탐 방지: 아주 짧은 단어(2글자 이하 or 3글자 이하 한글 단일어)는 경계 강화
    # - 예: "청정"은 "공기청정기" 같은 합성어에 걸릴 수 있음 → 경계 필요
    # - 한글의 \b가 완벽하지 않아서, 앞뒤가 한글/영문/숫자면 막는 방식 사용
    is_short = (len(t.replace(" ", "")) <= 2) or ((" " not in t) and len(t) <= 3)
    if is_short:
        # 앞뒤가 (한글/영문/숫자)로 붙어있으면 제외
        pat = rf"(?<![0-9a-z가-힣]){core}(?![0-9a-z가-힣])"
    else:
        pat = core

    return re.compile(pat, flags=re.IGNORECASE)


def build_patterns_from_terms(terms: List[str]) -> Dict[str, re.Pattern]:
    """
    terms(list)를 받아 {원문 term: compiled_pattern} 딕셔너리 생성
    """
    patterns = {}
    for term in terms:
        nt = normalize_term(term)
        if not nt:
            continue
        patterns[term] = build_flexible_pattern(term)
    return patterns


DEFAULT_EXCLUDE_PATTERNS = [
    r"공기\s*청정\s*기",  # "청정" 관련 대표 오탐 예시
    r"정수\s*기",
]


EXCLUDE_REGEX = [re.compile(p, flags=re.IGNORECASE) for p in DEFAULT_EXCLUDE_PATTERNS]


def mask_excluded_phrases(text: str) -> str:
    """
    제외 패턴에 해당하는 부분은 공백으로 마스킹하여 오탐을 줄인다.
    """
    t = text
    for rx in EXCLUDE_REGEX:
        t = rx.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def count_green_terms_in_text(text: str, terms: List[str]) -> Counter:
    cnt = Counter()
    if not text:
        return cnt

    norm = normalize_text(text)
    norm = mask_excluded_phrases(norm)

    patterns = build_patterns_from_terms(terms)

    for term, rx in patterns.items():
        hits = rx.findall(norm)
        if hits:
            cnt[term] += len(hits)
    return cnt


def count_green_terms_in_docs(docs, terms: List[str]) -> Tuple[Counter, List[Tuple[int, Counter]]]:
    total_counter = Counter()
    per_page_stats = []

    for idx, doc in enumerate(docs):
        page_no = idx + 1
        text = doc.page_content or ""
        page_counter = count_green_terms_in_text(text, terms)

        if page_counter:
            per_page_stats.append((page_no, page_counter))
            total_counter.update(page_counter)

    return total_counter, per_page_stats
