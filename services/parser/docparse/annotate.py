"""번역 판(`layout=2`)의 블록 표지: 쪽의 띠(`region`)와 내용 해시 키(`key`). 기본 판(1)은 이 모듈을 부르지 않는다.

- region: footer = 상자의 y0 가 쪽 높이의 `reading_order.FOOTER_ZONE`(0.92) 아래(읽는 순서의 꼬리 띠와 같은 기준).
  header = 상자의 y1 이 쪽 높이의 `HEADER_ZONE` 위. 나머지 body. 읽는 순서는 바꾸지 않는다(빼고 넣는 것은 읽는 쪽 몫).
- key = "k" + sha256([쪽, 종류, 본문]) 앞 16자. 종류는 글 블록 "text"·표 "table" 둘뿐이다(블록의 `kind` 칸
  heading·paragraph 는 문서 전체 글자 크기 중앙값에 기대 쪽 범위에 흔들린다 — 밴드 TRD2, MARC-ISSUE-422 의 1).
  본문은 글 블록이면 NFKC 뒤 공백을 지운 글, 표면 칸 격자(`cells` 그대로).
  같은 쪽에서 같은 키가 또 나오면 읽는 차례대로 `-2`·`-3` 을 붙인다. 상자·차례·섹션은 넣지 않는다(좌표가 흔들리거나
  앞에 블록이 늘어도 같은 키). 위치 ID(`id`·`table_id`·글자 자리 그릇 ID)는 그대로 두고 키를 나란히 둔다.
"""

import hashlib
import json
import unicodedata

from .reading_order import FOOTER_ZONE

# 쪽 위 띠(머리글·탐색 띠): 상자의 아래 끝이 쪽 높이의 이 비율 안. 공개 보고서 여섯(2026-10-28 밴드 TRD1 ★⑤)에서
# 쪽의 20% 이상에 되풀이되는 위 띠 글은 아래 끝이 쪽 높이의 0.050~0.069 였고, 0.075 안에 든 블록은 전부 그 띠였다.
# 0.09 로 올리면 위 여백이 좁은 보고서의 본문 제목(0.077~0.092)이 걸리고, 0.06 은 탐색 띠 일부를 놓친다.
HEADER_ZONE = 0.075


def region_of(bbox, page_height):
    """body | header | footer"""
    if bbox[1] >= FOOTER_ZONE * page_height:
        return "footer"
    if bbox[3] <= HEADER_ZONE * page_height:
        return "header"
    return "body"


def _squeeze(text):
    return unicodedata.normalize("NFKC", text).replace(" ", "")


def content_key(page, kind, body):
    data = json.dumps([page, kind, body], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "k" + hashlib.sha256(data).hexdigest()[:16]


def annotate(blocks, tables, pages):
    """블록마다(읽는 차례대로 놓인 목록) `region`·`key` 를 덧붙인다. 블록 dict 를 고친다."""
    heights = {p["page"]: p["height"] for p in pages}
    cells = {t["id"]: t["cells"] for t in tables}
    seen = {}
    for block in blocks:
        pno = block["page"]
        block["region"] = region_of(block["bbox"], heights[pno])
        if block["kind"] == "table":
            key = content_key(pno, "table", cells[block["table_id"]])
        else:
            key = content_key(pno, "text", _squeeze(block["text"]))
        n = seen[(pno, key)] = seen.get((pno, key), 0) + 1
        block["key"] = key if n == 1 else f"{key}-{n}"
    return blocks
