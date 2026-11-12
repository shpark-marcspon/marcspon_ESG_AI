"""번역 판(`layout=2`)의 쪽 글자 보존 셈(밴드 TRD1 ★③). 시험과 실측이 같이 쓴다.

쪽마다 `Counter(조각의 글 + 조각의 각주 표시)` 와 `Counter(글 블록의 글 + 표 칸 + 표의 footnote_marks)` 가
같으면 맞다. 양쪽 다 공백을 뺀 글자(`document` 의 `replace(" ", "")` 와 같은 정의)를 센다. 각주 표시를 양쪽에서
빼면 `char_count == 단위 합` 이다.
표 밖 숫자 조각의 각주 표시는 번역 판 블록 글에서 그 조각 글 바로 뒤에 붙어 있다(`blocks._with_marks`, 밴드 TRD2) —
그래서 글 블록 쪽 셈에 marks 를 따로 더하지 않는다.
조각 = `layout.page_chunks` 의 산출이다. 아주 작은 글(`MIN_VISIBLE_FONT_SIZE` 밑)·세로 줄·겹쳐 그린 글
거르기(켰을 때)로 버린 글은 양쪽 다 밖이다(거른 뒤를 센다). 위첨자는 조각 안에 남는다: 글자면 글 끝에, 숫자
뒤면 각주 표시로(그 조각이 표 칸이면 표의 footnote_marks 로 간다).
번역 판은 이 셈이 맞도록 짓는다. 표 상자 안이라도 칸에 들지 않은 조각은 글 블록으로 간다(빠짐 0). 칸에 든
조각은 글 블록에 넣지 않고, 두 표의 칸에 든 조각은 넓이가 가장 작은 표 하나에만 남는다(두 번 셈 0).
기본 판(1)에는 이 셈을 걸지 않는다.
"""

from collections import Counter


def _count(texts):
    return Counter("".join(texts).replace(" ", ""))


def char_balance(doc, page, chunks):
    """(빠진 글자, 남는 글자) 두 Counter. 둘 다 비면 맞다. chunks = 그 쪽의 `page_chunks` 산출."""
    have = _count([c.text for c in chunks] + [m for c in chunks for m in c.marks])
    blocks = [b["text"] for b in doc["blocks"] if b["page"] == page and b["kind"] != "table"]
    tables = [t for t in doc["tables"] if t["page"] == page]
    cells = [x for t in tables for row in t["cells"] for x in row]
    marks = [m["mark"] for t in tables for m in t["footnote_marks"]]
    units = _count(blocks + cells + marks)
    return have - units, units - have
