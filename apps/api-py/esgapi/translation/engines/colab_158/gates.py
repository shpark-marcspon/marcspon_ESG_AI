"""번역 게이트의 결정적 몫(코랩 셀 46): 상수, 한국어 잔존, 구조 태그·표 pipe 시그니처, 제목·본문 가르기, 쪽 단위 게이트
여부, 범용 QA 의 적용 판정(`must_apply`), 쪽 구획 나누기.

제목·본문 가르기 정규식(R/2449)은 실재 기업 이름 아홉을 뺀 일반 낱말 열여덟만 남겼다(처분 ⑧ — 「코랩과 다른 자리」:
제목 뒤 본문이 그 이름으로 시작하는 줄만 갈린다).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

# ── 상수(코랩 기본값, R/2125-2140·3050-3051) ──
ENABLE_EDITORIAL_POLISH = True
EDITORIAL_POLISH_MIN_CHARS = 120
EDITORIAL_POLISH_MAX_CHARS = 6000
EDITORIAL_POLISH_TEMPERATURE = 0.2
"""코랩에서 정의만 되고 어느 호출에도 넘기지 않는다(R/2128 — 쓰는 곳 0). 우리도 넘기지 않는다."""
ENABLE_FINAL_PAGE_POLISH = True
ENABLE_HEADING_BODY_MERGE_FIX = True
ENABLE_GENERIC_EDITORIAL_QA_GATE = True
GENERIC_EDITORIAL_QA_MIN_SCORE = 96
GENERIC_EDITORIAL_QA_SOFT_SCORE = 95
"""약한 이슈(COLLOCATION·TRANSLATIONESE·FLOW) 둘 이상이면 고친 글을 쓰는 점수 문턱 — `must_apply`(R/2715-2733)의 글자
95 를 상수로(TR4 Q5)."""
STRICT_FAIL_ON_UNTRANSLATED_KOREAN = True
MAX_UNTRANSLATED_REPAIR_ROUNDS = 2
TABLE_BATCH_SIZE = 24
"""표 칸 JSON 묶음의 칸 수(R/2282 의 글자 24)."""

HAS_KOREAN_RE = re.compile(r"[가-힣]")


def has_ko(text: str | None) -> bool:
    """R/2143-2144."""
    return bool(text and HAS_KOREAN_RE.search(str(text)))


def structure_tag_signature(text: str | None) -> list[str]:
    """R/2368-2374."""
    return re.findall(
        r"^\s*\[(?:PAGE\s+\d+|BLOCK\s+\d+|TABLE\s+\d+|VISUAL\s+\d+|HEADER|FOOTER|PAGE_NUMBER|CAPTION|ANNOTATION|"
        r"QUALITY_CHECK|UNREADABLE|POSSIBLY_MISSING|MERGE_QUALITY_CHECK)\]\s*$",
        str(text or ""),
        flags=re.IGNORECASE | re.MULTILINE,
    )


def apply_editorial_phrase_cleanup(text: str) -> str:
    """R/2378-2383 — 그대로 돌려준다(D1)."""
    return text


def collect_untranslated_korean_lines(text: str | None, max_items: int = 40) -> list[str]:
    """R/3054-3086. 셀 67 의 `_collect_remaining_korean_lines_in_english`(R/6510-6532)도 같은 셈이다."""
    found: list[str] = []
    seen: set[str] = set()
    for raw in str(text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if re.fullmatch(r"\[[A-Z_]+(?:\s+\d+)?\]", s, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", s):
            continue
        if has_ko(s):
            span = s[:300]
            if span not in seen:
                seen.add(span)
                found.append(span)
        if len(found) >= max_items:
            break
    return found


def table_pipe_signature(text: str | None) -> list[int]:
    """R/3089-3098(셀 67 R/6497-6503 도 같다)."""
    sig: list[int] = []
    for line in str(text or "").splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            sig.append(s.count("|"))
    return sig


def looks_like_report_heading_candidate(text: str | None) -> bool:
    """R/2386-2425."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if not s:
        return False
    if s.startswith("[") or s.startswith("|"):
        return False
    if len(s) < 8 or len(s) > 180:
        return False
    if re.search(r"[.!?]\s*$", s):
        return False
    if re.search(r"\([^)]*[가-힣][^)]*\)\s*$", s):
        return True
    words = re.findall(r"[A-Za-z][A-Za-z0-9&’'\-/]*", s)
    if not (2 <= len(words) <= 18):
        return False
    lower = s.lower()
    if re.match(
        r"^(we|it|this|these|the|our|i)\s+(are|is|have|has|will|can|must|should|live|believe|aim|seek)\b", lower
    ):
        return False
    cap_count = sum(1 for w in words if re.match(r"^[A-Z]", w))
    cap_ratio = cap_count / max(len(words), 1)
    if cap_ratio >= 0.55:
        return True
    if re.match(  # noqa: SIM103 — 코랩 꼴 그대로
        r"^(advancing|building|strengthening|expanding|enhancing|creating|sustaining|accelerating|improving)\b", lower
    ):
        return True
    return False


BODY_START_RE = re.compile(
    r"\s+(?=(?:The|This|These|Those|We|Our|It|In|As|Through|Building|Having|Guided|Against|With|By|For|From)\b)"
)
"""R/2448-2450 의 갈래에서 실재 기업 이름 아홉을 뺐다(처분 ⑧). 남은 일반 낱말 열여덟은 코랩 차례 그대로."""


def split_merged_heading_body_line(line: str | None) -> str:
    """R/2428-2460."""
    raw = str(line or "")
    s = raw.strip()
    if not s or len(s) < 60:
        return raw
    if s.startswith("|") or re.match(r"^\s*\[", raw):
        return raw
    m = re.match(r"^(.{8,180}?\([^()\n]*[가-힣][^()\n]*\))\s+([A-Z][A-Za-z0-9’'\-]+\b.*)$", s)
    if m:
        heading = m.group(1).strip()
        body = m.group(2).strip()
        if looks_like_report_heading_candidate(heading) and len(body) >= 30:
            return heading + "\n" + body
    for m in BODY_START_RE.finditer(s):
        idx = m.start()
        heading = s[:idx].strip()
        body = s[idx:].strip()
        if len(body) < 35:
            continue
        if looks_like_report_heading_candidate(heading):
            return heading + "\n" + body
    return raw


def fix_heading_body_merge(text: str) -> str:
    """R/2463-2480."""
    if not ENABLE_HEADING_BODY_MERGE_FIX:
        return text
    if not text:
        return text
    fixed_lines = [split_merged_heading_body_line(line) for line in str(text).splitlines()]
    out = "\n".join(fixed_lines)
    out = re.sub(r"\n{4,}", "\n\n\n", out)
    return out


def contains_table_like_text(text: str | None) -> bool:
    """R/2554-2565."""
    if not text:
        return False
    t = str(text)
    if re.search(r"^\s*\[(TABLE|MARKDOWN_TABLE)\b", t, flags=re.IGNORECASE | re.MULTILINE):
        return True
    lines = [ln.strip() for ln in t.splitlines()]
    pipe_rows = [ln for ln in lines if ln.startswith("|") and ln.endswith("|") and ln.count("|") >= 2]
    return len(pipe_rows) >= 2


def should_run_page_level_text_gate(text: str | None) -> bool:
    """R/2568-2575."""
    if not text or not str(text).strip():
        return False
    if contains_table_like_text(text):
        return False
    plain_len = len(re.sub(r"\s+", "", str(text)))
    return plain_len >= EDITORIAL_POLISH_MIN_CHARS


CRITICAL_ISSUE_TYPES = frozenset({"GRAMMAR", "GLOSSARY", "STRUCTURE", "KOREAN_LEFTOVER"})
SOFT_ISSUE_TYPES = frozenset({"COLLOCATION", "TRANSLATIONESE", "FLOW"})


def must_apply(score: int, has_critical_issue: bool, issue_types: set[str], issue_count: int) -> bool:
    """R/2715-2733. issue_types 는 dict 이슈의 str(type).upper() 집합, issue_count 는 `len(issues)`(dict 가 아닌 원소도
    센다 — 코랩대로)."""
    return (
        has_critical_issue
        or bool(issue_types & CRITICAL_ISSUE_TYPES)
        or score < GENERIC_EDITORIAL_QA_MIN_SCORE
        or (score < GENERIC_EDITORIAL_QA_SOFT_SCORE and issue_count >= 2 and bool(issue_types & SOFT_ISSUE_TYPES))
    )


TOP_TAG_RE = re.compile(
    r"^\[(PAGE\s+\d+|BLOCK\s+\d+|TABLE\s+\d+|VISUAL\s+\d+|"
    r"HEADER|FOOTER|PAGE_NUMBER|QUALITY_CHECK|UNREADABLE|"
    r"POSSIBLY_MISSING|MERGE_QUALITY_CHECK)\]\s*$",
    re.IGNORECASE,
)


@dataclass
class Section:
    """쪽 구획 하나(코랩 {"kind", "lines"}). kind 는 태그 첫 낱말의 대문자(PAGE·BLOCK·TABLE…) 또는 TEXT."""

    kind: str
    lines: list[str] = field(default_factory=list[str])


def split_page_sections(page_content: str) -> list[Section]:
    """R/2938-2963."""
    sections: list[Section] = []
    current: Section | None = None
    for line in page_content.splitlines():
        m = TOP_TAG_RE.match(line.strip())
        if m:
            if current:
                sections.append(current)
            tag = m.group(1).upper().split()[0]
            current = Section(kind=tag, lines=[line.rstrip()])
        else:
            if current is None:
                current = Section(kind="TEXT")
            current.lines.append(line.rstrip())
    if current:
        sections.append(current)
    return sections


def format_glossary_violations_for_prompt(violations: Sequence[dict[str, str]]) -> str:
    """R/2967-2977."""
    if not violations:
        return "(No glossary violations.)"
    lines: list[str] = []
    for v in violations:
        m = re.search(r"'(.+?)'.+?'(.+?)'", v.get("suggestion", ""))
        if m:
            lines.append(f"- {m.group(1)} -> {m.group(2)}")
        else:
            lines.append(f"- {v.get('suggestion', '')}")
    return "\n".join(lines)
