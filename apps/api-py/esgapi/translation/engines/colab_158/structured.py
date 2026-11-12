"""구조 글(코랩 셀 7 의 글 몫): 구조 태그 복원, Word 표 칸 → Markdown pipe 표, txt·md 갈래.

docx 를 여는 몫(`docx_to_structured_txt`·`_iter_docx_blocks`)은 TR1b 의 읽개가 한다 — 그 읽개는 표마다 칸 글의 목록을
`table_rows_to_markdown` 에 넘긴다. `_escape_md_cell` 은 판이 둘: 여기 셀 7 판(연속 줄바꿈·빈칸을 접음)은 docx 읽기에,
셀 46 판(접지 않음)은 표 재조립에 쓴다(tables.escape_md_cell).
"""

import re
from collections.abc import Sequence

TAG_PATTERN = (
    r"(?:PAGE|BLOCK|TABLE|VISUAL|HEADER|FOOTER|PAGE_NUMBER|CAPTION|NOTES|"
    r"MARKDOWN_TABLE|STRUCTURE_NOTES|QUALITY_CHECK|MERGE_QUALITY_CHECK|"
    r"UNREADABLE|POSSIBLY_MISSING)(?:\s+\d+)?"
)


def normalize_structured_tags(raw: str) -> str:
    """pandoc/Word 변환 과정에서 생긴 구조 태그 변형만 복원한다(R/129-161).

    약점 W1 그대로: 끝의 `re.sub(r'\\n{{3,}}', …)` 는 f-문자열이 아니라 {{3,}} 가 글자 `{` 의 반복이다 — 빈 줄 셋 이상을
    접지 않는다(R/160).
    """
    if not raw:
        return raw

    raw = raw.replace("\r\n", "\n").replace("\r", "\n")

    raw = re.sub(rf"\*\*\s*(\[{TAG_PATTERN}\])\s*\*\*", r"\1", raw, flags=re.IGNORECASE)
    raw = re.sub(rf"__\s*(\[{TAG_PATTERN}\])\s*__", r"\1", raw, flags=re.IGNORECASE)

    raw = re.sub(
        rf"^\s{{0,3}}#{{1,6}}\s*(\[{TAG_PATTERN}\])\s*$",
        r"\1",
        raw,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    raw = re.sub(rf"\\\[({TAG_PATTERN})\\\]", r"[\1]", raw, flags=re.IGNORECASE)

    raw = re.sub(r"[ \t]+\n", "\n", raw)
    raw = re.sub(r"\n{{3,}}", "\n\n", raw)
    return raw


def escape_md_cell_docx(text: str | None) -> str:
    """셀 7 판 `_escape_md_cell`(R/185-198): 칸 안 줄바꿈 → <br>(연속은 하나), | → &#124;, 빈칸·탭 접음, 앞뒤 strip."""
    if text is None:
        return ""
    t = str(text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"\n+", "<br>", t)
    t = t.replace("|", "&#124;")
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def table_rows_to_markdown(rows: Sequence[Sequence[str | None]]) -> list[str]:
    """`_table_to_markdown_lines` 의 글 몫(R/201-224): 행마다 칸 글의 목록 → pipe 표 줄. 칸이 다 빈 행은 버리고, 열 수는
    가장 긴 행에 맞춰 빈 칸을 채운다. 행이 없으면 빈 목록."""
    kept: list[list[str]] = []
    for row in rows:
        cells = [escape_md_cell_docx(cell) for cell in row]
        if any(cells):
            kept.append(cells)

    if not kept:
        return []

    col_n = max(len(r) for r in kept)
    norm_rows: list[list[str]] = []
    for r in kept:
        if len(r) < col_n:
            r = r + [""] * (col_n - len(r))
        elif len(r) > col_n:
            r = r[:col_n]
        norm_rows.append(r)

    out: list[str] = []
    out.append("| " + " | ".join(norm_rows[0]) + " |")
    out.append("| " + " | ".join(["---"] * col_n) + " |")
    for r in norm_rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return out


def preprocess_structured_text(raw: str) -> str:
    """txt·md 갈래(R/283-292): 읽은 글에 `normalize_structured_tags` 만. (코랩은 파일 — 우리는 글.)"""
    return normalize_structured_tags(raw)
