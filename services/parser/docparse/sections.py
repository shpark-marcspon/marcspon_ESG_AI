"""섹션 추정. PDF 책갈피가 있으면 그것을, 없으면 쪽 상단의 큰 글자를 쪽 제목으로 본다(휴리스틱)."""

from statistics import median

BASIS_OUTLINE = "pdf_outline"
BASIS_FONT = "page_top_largest_font"
BASIS_NONE = "no_title_found"


def page_title(chunks, page_height):
    """쪽 상단 35% 안에서 쪽 글자 크기 중앙값의 1.4배 이상인 글자 중 가장 큰 것."""
    cs = [c for c in chunks if len(c.text) >= 2]
    if not cs:
        return None
    body = median(c.size for c in cs)
    top = [c for c in cs if c.y0 < page_height * 0.35 and c.size >= body * 1.4]
    if not top:
        return None
    mx = max(c.size for c in top)
    parts = sorted((c for c in top if c.size >= mx - 0.5), key=lambda c: (round(c.y0), c.x0))
    return " ".join(c.text for c in parts)[:80]


def sections_from_outline(toc, page_count):
    out = []
    for k, (level, title, page) in enumerate(toc):
        if not 1 <= page <= page_count:
            continue
        nxt = next((p for lv, _t, p in toc[k + 1 :] if lv <= level and p >= page), None)
        end = max(page, (nxt - 1) if nxt and nxt > page else (page if nxt else page_count))
        out.append(
            {
                "id": f"s{len(out) + 1}",
                "title": title.strip(),
                "level": level,
                "page_start": page,
                "page_end": min(end, page_count),
                "basis": BASIS_OUTLINE,
            }
        )
    return out


def sections_from_titles(titles):
    """titles: [(쪽 번호, 제목 또는 None)] 쪽 순서대로. 같은 제목이 이어지면 한 섹션."""
    out, cur = [], None
    for page, title in titles:
        if title and title != cur:
            cur = title
            out.append(
                {
                    "id": f"s{len(out) + 1}",
                    "title": title,
                    "level": 1,
                    "page_start": page,
                    "page_end": page,
                    "basis": BASIS_FONT,
                }
            )
        elif not out:
            out.append(
                {"id": "s1", "title": None, "level": 1, "page_start": page, "page_end": page, "basis": BASIS_NONE}
            )
        else:
            out[-1]["page_end"] = page
    return out
