"""국문 병기(코랩 셀 52, R/3622-4063): 영문 번역 쪽의 제목 첫 줄에만 원문 국문을 괄호로 붙인다.

BLOCK 은 첫 실질 줄, TABLE 은 제목·캡션 첫 줄, VISUAL 은 `title:` 의 첫 줄. 원문 쪽은 같은 번호의 뒤 조각이 이긴다
(코랩의 dict 만들기 — 합치지 않는다).
"""

import re
from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from esgapi.translation.engines.colab_158.pages import last_wins_map, parse_pages

SUBTAG_RE = re.compile(r"^\[[A-Z_]+(?:\s+\d+)?\]\s*$")
HAS_KOREAN_RE = re.compile(r"[가-힣]")
ALREADY_BILINGUAL_RE = re.compile(r"\([^)]*[가-힣][^)]*\)")
VISUAL_SUBLABEL_RE = re.compile(
    r"^(title|legend|axis_labels|labels_inside_shapes|annotations|caption)\s*:", re.IGNORECASE
)


def has_korean(s: str | None) -> bool:
    return bool(HAS_KOREAN_RE.search(str(s or "")))


def is_subtag(s: str | None) -> bool:
    return bool(SUBTAG_RE.match(str(s or "").strip()))


def is_pipe(s: str | None) -> bool:
    return str(s or "").strip().startswith("|")


def normalize_for_bilingual_check(s: str | None) -> str:
    """R/3665-3671."""
    t = str(s or "")
    t = re.sub(r"\([^)]*[가-힣][^)]*\)", "", t)
    t = re.sub(r"^(title|caption)\s*:\s*", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def has_latin(s: str | None) -> bool:
    return bool(re.search(r"[A-Za-z]", str(s or "")))


def is_original_english_like_line(s: str | None) -> bool:
    """R/3676-3686."""
    t = normalize_for_bilingual_check(s)
    if not t:
        return False
    if has_korean(t):
        return False
    if is_subtag(t) or is_pipe(t):
        return False
    return has_latin(t)


def exists_as_original_english_line(en_line: str, source_lines: Sequence[str] | None) -> bool:
    """R/3688-3727."""
    en_norm = normalize_for_bilingual_check(en_line).lower()
    if not en_norm:
        return False
    first_korean_idx: int | None = None
    first_english_match_idx: int | None = None
    for idx, src_line in enumerate(source_lines or []):
        src_norm = normalize_for_bilingual_check(src_line)
        if first_korean_idx is None and has_korean(src_norm):
            first_korean_idx = idx
        if first_english_match_idx is None and is_original_english_like_line(src_norm):  # noqa: SIM102 — 코랩 꼴 그대로
            if src_norm.lower() == en_norm:
                first_english_match_idx = idx
    if first_english_match_idx is None:
        return False
    if first_korean_idx is None:
        return True
    if first_korean_idx < first_english_match_idx:  # noqa: SIM103 — 코랩 꼴 그대로
        return False
    return True


def should_skip_bilingual_attach(en_line: str, kr_text: str, source_lines: Sequence[str] | None = None) -> bool:
    """R/3729-3753."""
    if not kr_text:
        return True
    if not has_korean(kr_text):
        return True
    if ALREADY_BILINGUAL_RE.search(str(en_line or "")):
        return True
    if exists_as_original_english_line(en_line, source_lines):  # noqa: SIM103 — 코랩 꼴 그대로
        return True
    return False


def attach(en_line: str, kr_text: str, source_lines: Sequence[str] | None = None) -> str:
    """R/3756-3759."""
    if should_skip_bilingual_attach(en_line, kr_text, source_lines=source_lines):
        return en_line
    return f"{str(en_line).rstrip()} ({str(kr_text).strip()})"


def first_diff_line(s_lines: Sequence[str], t_first: str, max_len: int = 80) -> str:
    """R/3762-3792."""
    t_first_norm = normalize_for_bilingual_check(t_first)
    for line in s_lines:
        s = normalize_for_bilingual_check(line)
        if not s:
            continue
        if is_subtag(s) or is_pipe(s):
            continue
        if not has_korean(s):
            continue
        if len(s) > max_len:
            continue
        if s == t_first_norm:
            continue
        return s
    return ""


def detect_top_level_tag(line: str) -> tuple[str, str | None] | None:
    """R/3795-3809."""
    s = line.strip()
    for pat, kind in [
        (r"^\[PAGE\s+(\d+)\]$", "PAGE"),
        (r"^\[BLOCK\s+(\d+)\]$", "BLOCK"),
        (r"^\[TABLE\s+(\d+)\]$", "TABLE"),
        (r"^\[VISUAL\s+(\d+)\]$", "VISUAL"),
    ]:
        m = re.match(pat, s, re.IGNORECASE)
        if m:
            return (kind, m.group(1))
    for pat, kind in [
        (r"^\[HEADER\]$", "HEADER"),
        (r"^\[FOOTER\]$", "FOOTER"),
        (r"^\[PAGE_NUMBER\]$", "PAGE_NUMBER"),
        (r"^\[(QUALITY_CHECK|UNREADABLE|POSSIBLY_MISSING|MERGE_QUALITY_CHECK)\]$", "META"),
    ]:
        if re.match(pat, s, re.IGNORECASE):
            return (kind, None)
    return None


@dataclass
class TopSection:
    kind: str
    num: str | None
    lines: list[str] = field(default_factory=list[str])


def split_top_level_sections(page_text: str) -> list[TopSection]:
    """R/3815-3827."""
    sections: list[TopSection] = []
    current: TopSection | None = None
    for line in page_text.splitlines():
        info = detect_top_level_tag(line)
        if info:
            if current:
                sections.append(current)
            kind, num = info
            current = TopSection(kind=kind, num=num, lines=[line.strip()])
        else:
            if current is None:
                current = TopSection(kind="TEXT", num=None)
            current.lines.append(line)
    if current:
        sections.append(current)
    return sections


@dataclass
class SubSection:
    label: str
    lines: list[str]


def split_subsections(lines: Sequence[str]) -> list[SubSection]:
    """R/3829-3839."""
    subs: list[SubSection] = []
    lbl, buf = "__ROOT__", list[str]()
    for line in lines[1:]:
        s = line.strip()
        if is_subtag(s) and not detect_top_level_tag(s):
            subs.append(SubSection(label=lbl, lines=buf))
            lbl, buf = s, []
        else:
            buf.append(line)
    subs.append(SubSection(label=lbl, lines=buf))
    return subs


def merge_block_section(t_lines: list[str], s_lines: list[str]) -> list[str]:
    """R/3846-3888."""
    if not t_lines:
        return t_lines
    out = [t_lines[0].strip()]
    t_body = t_lines[1:]
    s_body = s_lines[1:] if len(s_lines) > 1 else []
    t_first = ""
    for line in t_body:
        s = line.strip()
        if s and not is_subtag(s):
            t_first = s
            break
    s_title = first_diff_line(s_body, t_first)
    title_done = False
    for line in t_body:
        s = line.strip()
        if not title_done and s and not is_subtag(s):
            out.append(attach(line, s_title, source_lines=s_body))
            title_done = True
        else:
            out.append(line)
    deduped: list[str] = []
    prev_content: str | None = None
    for line in out:
        s = line.strip()
        if s and not is_subtag(s) and s == prev_content:
            continue
        deduped.append(line)
        if s:
            prev_content = s
    return deduped


def merge_table_section(t_lines: list[str], s_lines: list[str]) -> list[str]:
    """R/3897-3925."""
    if not t_lines:
        return t_lines
    out = [t_lines[0].strip()]
    t_subs = split_subsections(t_lines)
    s_subs = split_subsections(s_lines if s_lines else [t_lines[0]])
    title_done = False
    for idx, t_sub in enumerate(t_subs):
        lbl = t_sub.label
        s_sub_lines = s_subs[idx].lines if idx < len(s_subs) else []
        if lbl != "__ROOT__":
            out.append(lbl)
        if lbl in ("__ROOT__", "[CAPTION]") and not title_done:
            t_first = next(
                (
                    ln.strip()
                    for ln in t_sub.lines
                    if ln.strip() and not is_subtag(ln.strip()) and not is_pipe(ln.strip())
                ),
                "",
            )
            s_title = first_diff_line(s_sub_lines, t_first)
            first_done = False
            for line in t_sub.lines:
                s = line.strip()
                if not first_done and s and not is_subtag(s) and not is_pipe(s):
                    out.append(attach(line, s_title, source_lines=s_sub_lines))
                    first_done = True
                    title_done = True
                else:
                    out.append(line)
        else:
            out.extend(t_sub.lines)
    return out


@dataclass
class VisualSub:
    label: str
    inline: str
    body: list[str] = field(default_factory=list[str])


def parse_visual_sublabels(lines: Sequence[str]) -> list[VisualSub]:
    """R/3932-3945."""
    result: list[VisualSub] = []
    current: VisualSub | None = None
    for line in lines:
        s = line.strip()
        m = VISUAL_SUBLABEL_RE.match(s)
        if m:
            if current:
                result.append(current)
            current = VisualSub(label=m.group(1).lower(), inline=s[m.end() :].strip())
        else:
            if current is None:
                current = VisualSub(label="__root__", inline="")
            if s:
                current.body.append(line)
    if current:
        result.append(current)
    return result


def merge_visual_section(t_lines: list[str], s_lines: list[str]) -> list[str]:
    """R/3948-4005."""
    if not t_lines:
        return t_lines
    out = [t_lines[0].strip()]
    t_subs = parse_visual_sublabels(t_lines[1:])
    s_subs = parse_visual_sublabels(s_lines[1:] if len(s_lines) > 1 else [])
    s_map: defaultdict[str, deque[VisualSub]] = defaultdict(deque)
    for sub in s_subs:
        s_map[sub.label].append(sub)
    for t_sub in t_subs:
        label = t_sub.label
        s_sub = s_map[label].popleft() if s_map[label] else None
        inline_t = t_sub.inline
        inline_s = re.sub(r"^\(|\)$", "", (s_sub.inline if s_sub else "").strip()).strip()
        if label == "__root__":
            out.extend(t_sub.body)
            continue
        if label == "title":
            if inline_t:
                sources = [s_sub.inline, *s_sub.body] if s_sub else []
                out.append(f"title: {attach(inline_t, inline_s, source_lines=sources)}")
                out.extend(t_sub.body)
            else:
                out.append("title:")
                t_first = next((ln.strip() for ln in t_sub.body if ln.strip() and not is_subtag(ln.strip())), "")
                s_title = first_diff_line(s_sub.body if s_sub else [], t_first)
                title_done = False
                for line in t_sub.body:
                    s = line.strip()
                    if not title_done and s and not is_subtag(s):
                        out.append(attach(line, s_title, source_lines=(s_sub.body if s_sub else [])))
                        title_done = True
                    else:
                        out.append(line)
        else:
            out.append(f"{label}: {inline_t}" if inline_t else f"{label}:")
            out.extend(t_sub.body)
    return out


def attach_korean_originals(translated_text: str, source_text: str) -> str:
    """R/4012-4063. 번역 쪽마다 원문 쪽(같은 번호, 뒤 조각이 이김)의 구획을 (kind, num) 으로 먼저, 안 되면 kind 차례로
    맞춰 병기한다. 원문에 없는 쪽은 그대로."""
    source_map = last_wins_map(parse_pages(source_text))
    result_pages: list[str] = []
    for t_page in parse_pages(translated_text):
        t_content = t_page.content
        s_content = source_map.get(t_page.page_num, "")
        if not s_content:
            result_pages.append(t_content)
            continue
        t_sections = split_top_level_sections(t_content)
        s_sections = split_top_level_sections(s_content)
        s_by_key: defaultdict[tuple[str, str | None], deque[TopSection]] = defaultdict(deque)
        s_by_kind: defaultdict[str, deque[TopSection]] = defaultdict(deque)
        for sec in s_sections:
            s_by_key[(sec.kind, sec.num)].append(sec)
            s_by_kind[sec.kind].append(sec)
        merged_sections: list[str] = []
        for t_sec in t_sections:
            kind, num = t_sec.kind, t_sec.num
            s_sec: TopSection | None = None
            if s_by_key[(kind, num)]:
                s_sec = s_by_key[(kind, num)].popleft()
                _remove_same(s_by_kind[kind], s_sec)
            elif s_by_kind[kind]:
                s_sec = s_by_kind[kind].popleft()
            s_lines = s_sec.lines if s_sec else []
            if kind == "BLOCK":
                merged = merge_block_section(t_sec.lines, s_lines)
            elif kind == "TABLE":
                merged = merge_table_section(t_sec.lines, s_lines)
            elif kind == "VISUAL":
                merged = merge_visual_section(t_sec.lines, s_lines)
            else:
                merged = t_sec.lines
            merged_sections.append("\n".join(merged))
        result_pages.append("\n".join(merged_sections))
    return "\n\n".join(result_pages)


def _remove_same(queue: deque[TopSection], target: TopSection) -> None:
    """코랩의 `deque.remove(s_sec)`(R/4048-4051) — dict 의 == 비교로 처음 같은 것을 지운다(dataclass == 도 칸 비교)."""
    try:  # noqa: SIM105 — 코랩 꼴 그대로
        queue.remove(target)
    except ValueError:
        pass
