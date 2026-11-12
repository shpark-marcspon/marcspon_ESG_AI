"""쪽 나누기(코랩 셀 17·18): 한 줄 전체가 `[PAGE n]` 인 줄로 조각을 가르고, 같은 번호의 조각을 합친다.

코랩은 파일을 읽어(셀 47 의 인코딩 넷) 나눈다 — 우리는 글을 받는다. 코랩 셀 사이의 파일 왕복(번역 조각을 빈 줄 하나로
이어 쓰고 다음 셀이 다시 읽어 나눔)은 `join_pages` 와 이 모듈의 나누기로 그대로 한다.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

PAGE_TAG_LINE_RE = re.compile(r"^\s*(?:\*\*)?\\?\[PAGE\s+(\d+)\\?\](?:\*\*)?\s*$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class PageChunk:
    """쪽 조각 하나(코랩의 {"page_num", "content"})."""

    page_num: int
    content: str


def parse_pages(text: str | None) -> list[PageChunk]:
    """R/550-579. 조각마다 `[PAGE n]\\n<본문 앞 빈 줄 뺌>` 를 rstrip. 태그가 없으면 빈 목록."""
    text = text or ""
    matches = list(PAGE_TAG_LINE_RE.finditer(text))
    pages: list[PageChunk] = []
    if not matches:
        return pages
    for idx, m in enumerate(matches):
        page_num = int(m.group(1))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].lstrip("\n")
        pages.append(PageChunk(page_num=page_num, content=f"[PAGE {page_num}]\n{body}".rstrip()))
    return pages


def remove_page_tag_lines(content: str | None) -> str:
    """R/596-611. 줄을 strip 해 `[PAGE n]` 꼴이면 버린다."""
    if not content:
        return ""
    lines: list[str] = []
    for line in str(content).splitlines():
        s = line.strip()
        if PAGE_TAG_LINE_RE.match(s):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def pages_to_map_merge(pages: Sequence[PageChunk]) -> tuple[dict[int, str], dict[int, int]]:
    """R/614-648. 쪽 번호 → 합친 글, 그리고 겹친 쪽 번호 → 나온 횟수(코랩은 이것을 print 한다 — 부르는 쪽이 경고로)."""
    page_map: dict[int, str] = {}
    duplicate_counts: dict[int, int] = {}
    for page in pages:
        pnum = page.page_num
        body = remove_page_tag_lines(page.content)
        if pnum not in page_map:
            page_map[pnum] = f"[PAGE {pnum}]\n{body}".rstrip()
            continue
        duplicate_counts[pnum] = duplicate_counts.get(pnum, 1) + 1
        existing = page_map[pnum].rstrip()
        new_body = body.strip()
        if new_body and new_body not in existing:
            page_map[pnum] = existing + "\n\n" + new_body
    return page_map, duplicate_counts


def last_wins_map(pages: Sequence[PageChunk]) -> dict[int, str]:
    """코랩 셀 52 의 `{p['page_num']: p['content'] for p in …}` — 같은 번호는 뒤 조각이 이긴다(합치지 않는다). 셀 57
    반영 검사는 이것을 쓰지 않고 합친다(MARC-ENT-451)."""
    return {p.page_num: p.content for p in pages}


def filter_range(page_map: dict[int, str], start: int | None, end: int | None) -> dict[int, str]:
    """코랩 셀 65·67 의 쪽 범위 거름(R/6111-6119·6825-6831). 키 차례는 그대로."""
    if start is None and end is None:
        return page_map
    return {
        pnum: content
        for pnum, content in page_map.items()
        if (start is None or pnum >= start) and (end is None or pnum <= end)
    }


def join_pages(parts: Sequence[str]) -> str:
    """코랩이 조각을 파일에 쓰는 꼴(R/3511·3524): 빈 줄 하나로 잇는다."""
    return "\n\n".join(parts)


def file_roundtrip(text: str) -> str:
    """코랩 셀 사이의 파일 왕복이 글에 하는 일: 텍스트 모드 읽기가 줄바꿈을 `\\n` 으로 통일한다."""
    return text.replace("\r\n", "\n").replace("\r", "\n")
