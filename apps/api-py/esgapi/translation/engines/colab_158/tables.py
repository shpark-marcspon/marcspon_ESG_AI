"""표 도우미(코랩 셀 46 판): pipe 표 범위·행 나누기·재조립, 칸 번역 조각 모으기, 느슨한 JSON 읽기.

`_translate_table_section`(R/2812-2936)의 결정적 몫 — 조각 모으기(collect_table_fragments)와 재조립(`reassemble_table`)
— 이 여기, LLM 몫(칸 묶음 번역)은 translate.py 다. 셀 46 판 `escape_md_cell` 은 접지 않는다(셀 7 판과 다름).
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from esgapi.translation.engines.colab_158.gates import has_ko


def escape_md_cell(text: str | None) -> str:
    """셀 46 판 `_escape_md_cell`(R/2164-2171): strip 먼저, 줄바꿈 하나하나 → <br>, | → &#124;."""
    if text is None:
        return ""
    t = str(text).strip()
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\n", "<br>")
    t = t.replace("|", "&#124;")
    return t


def unescape_md_cell(text: str | None) -> str:
    """R/2174-2177."""
    if text is None:
        return ""
    return str(text).replace("&#124;", "|").strip()


def split_md_row(row: str) -> list[str]:
    """R/2180-2187."""
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [unescape_md_cell(c.strip()) for c in s.split("|")]


def is_pipe_row(line: str) -> bool:
    """R/2190-2192."""
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def is_separator(line: str) -> bool:
    """R/2195-2200."""
    s = line.strip()
    if not is_pipe_row(s):
        return False
    cells = split_md_row(s)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", (c or "").strip()) for c in cells)


def make_pipe_row(cells: Sequence[str]) -> str:
    """R/2203-2204."""
    return "| " + " | ".join(escape_md_cell(c) for c in cells) + " |"


def make_separator(n: int) -> str:
    """R/2207-2208."""
    return "| " + " | ".join(["---"] * n) + " |"


def find_table_ranges(lines: Sequence[str]) -> list[tuple[int, int]]:
    """R/2211-2228. pipe 행 + 바로 아래 구분 행이면 표의 시작, 이어지는 pipe 행까지."""
    ranges: list[tuple[int, int]] = []
    i, n = 0, len(lines)
    while i < n:
        if is_pipe_row(lines[i]) and i + 1 < n and is_separator(lines[i + 1]):
            k = i + 2
            while k < n and is_pipe_row(lines[k]):
                k += 1
            ranges.append((i, k))
            i = k
            continue
        i += 1
    return ranges


def parse_json_loose(raw: str) -> object:
    """R/2231-2246. 코드 울타리를 벗기고 읽고, 안 되면 첫 `{` ~ 마지막 `}` 를 읽는다. 못 읽으면 ValueError
    (json.JSONDecodeError 도 ValueError 다)."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:  # noqa: S110 — 코랩 꼴 그대로
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(raw[start : end + 1])
    raise ValueError("JSON 파싱 실패")


PURE_STRUCTURE_NOTES = frozenset({"merged_cells", "ambiguous_columns", "suspected_missing_cells"})


def is_pure_structure_note(s: str | None) -> bool:
    """R/2830-2839. 번역 대상이 아닌 내부 구조 진단 줄."""
    t = str(s or "").strip().lower()
    t = t.lstrip("-•* ").strip()
    t = t.replace(" ", "_")
    return t in PURE_STRUCTURE_NOTES


@dataclass
class TableRange:
    """pipe 표 하나(R/2890-2897)."""

    start: int
    end: int
    ridx: int
    header: list[str]
    body: list[list[str]]
    col_n: int


@dataclass
class TablePlan:
    """표 구획 하나의 번역 계획: 칸·주변 줄 조각(id·글)과 재조립 정보."""

    lines: list[str]
    fragments: list[dict[str, str]] = field(default_factory=list[dict[str, str]])
    line_frag_map: dict[int, str] = field(default_factory=dict[int, str])
    ranges: list[TableRange] = field(default_factory=list[TableRange])


def collect_table_fragments(section_text: str) -> TablePlan | None:
    """R/2819-2897. pipe 표가 없으면 None(코랩은 그 구획을 일반 구획처럼 번역한다 — R/2822-2824)."""
    lines = section_text.splitlines()
    ranges = find_table_ranges(lines)
    if not ranges:
        return None

    table_row_set: set[int] = set()
    for s, e in ranges:
        table_row_set.update(range(s, e))

    plan = TablePlan(lines=lines)
    for i, line in enumerate(lines):
        s = line.strip()
        if i in table_row_set or not s:
            continue
        if re.match(r"^\[[A-Z_]+(?:\s+\d+)?\]$", s, re.IGNORECASE):
            continue
        if is_pure_structure_note(s) and not has_ko(s):
            continue
        if has_ko(s):
            fid = f"L{i}"
            plan.line_frag_map[i] = fid
            plan.fragments.append({"id": fid, "text": s})

    for ridx, (start, end) in enumerate(ranges):
        raw_rows = lines[start:end]
        header = split_md_row(raw_rows[0])
        col_n = len(header)
        body: list[list[str]] = []
        for raw in raw_rows[2:]:
            cells = split_md_row(raw)
            if len(cells) < col_n:
                cells += [""] * (col_n - len(cells))
            elif len(cells) > col_n:
                cells = cells[: col_n - 1] + [" | ".join(cells[col_n - 1 :])]  # noqa: RUF005 — 코랩 꼴 그대로
            body.append(cells)
        for c, txt in enumerate(header):
            if has_ko(txt):
                plan.fragments.append({"id": f"T{ridx}_H{c}", "text": txt})
        for r, row in enumerate(body):
            for c, txt in enumerate(row):
                if has_ko(txt):
                    plan.fragments.append({"id": f"T{ridx}_R{r}C{c}", "text": txt})
        plan.ranges.append(TableRange(start=start, end=end, ridx=ridx, header=header, body=body, col_n=col_n))
    return plan


def reassemble_table(plan: TablePlan, translations: Mapping[str, str]) -> str:
    """R/2901-2936. 번역이 없는 칸·줄은 원래 글. 표는 같은 행·열 수로 다시 짓는다(구분 행은 `---`)."""
    lines = plan.lines
    range_by_start = {info.start: info for info in plan.ranges}
    out: list[str] = []
    i = 0
    while i < len(lines):
        if i in range_by_start:
            info = range_by_start[i]
            header = list(info.header)
            body = [list(r) for r in info.body]
            for c in range(len(header)):
                fid = f"T{info.ridx}_H{c}"
                if fid in translations:
                    header[c] = translations[fid]
            for r in range(len(body)):
                for c in range(len(body[r])):
                    fid = f"T{info.ridx}_R{r}C{c}"
                    if fid in translations:
                        body[r][c] = translations[fid]
            out.append(make_pipe_row(header))
            out.append(make_separator(info.col_n))
            for row in body:
                out.append(make_pipe_row(row))
            i = info.end
            continue
        if i in plan.line_frag_map:
            out.append(translations.get(plan.line_frag_map[i], lines[i]))
        else:
            out.append(lines[i])
        i += 1
    return "\n".join(out)
