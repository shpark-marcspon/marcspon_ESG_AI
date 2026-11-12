"""단락의 구성 블록 → 블록 범위(result@2 근거 blockRanges — 감독 답 C1, 11-10). AI 0.

「이어짐」의 정의: 문서 뷰의 **body 블록 읽는 차례**(`view.blocks(region="body")`)에서 바로 이웃인 블록. 머리·꼬리
(region 이 body 아닌 블록)는 그 차례에 없으므로 쪽을 넘는 단락이 머리·꼬리를 사이에 두어도 한 범위다. 보정 e 가 뺀
body 블록(되풀이 글)이 사이에 끼면 그 블록은 단락에 없으니 범위가 갈린다 — 범위 [첫, 끝] 을 읽으면 body 차례에서 그
둘 사이 블록 전부가 나오고, 그것이 곧 구성 블록이다.
"""

from collections.abc import Iterable, Mapping, Sequence

from esgapi.greenwash.engines.g1.passages import DocumentView


def block_order(view: DocumentView) -> dict[str, int]:
    """블록 id → body 읽는 차례 번호."""
    return {b.id: i for i, b in enumerate(view.blocks(region="body"))}


def fold(members: Iterable[str], order: Mapping[str, int]) -> list[tuple[str, str]]:
    """구성 블록을 읽는 차례로 늘어놓아 이어진 블록끼리 [첫, 끝] 으로 접는다. 겹친 id 는 하나로. body 차례에 없는
    블록이 있으면 ValueError(보정 b 가 뺐어야 한다)."""
    ids = list(dict.fromkeys(members))
    missing = [b for b in ids if b not in order]
    if missing:
        raise ValueError(f"body 차례에 없는 블록: {missing[:3]}")
    ids.sort(key=order.__getitem__)
    out: list[tuple[str, str]] = []
    for b in ids:
        if out and order[b] == order[out[-1][1]] + 1:
            out[-1] = (out[-1][0], b)
        else:
            out.append((b, b))
    return out


def cap(ranges: Sequence[tuple[str, str]], limit: int) -> tuple[list[tuple[str, str]], bool]:
    """앞 limit 개와 잘렸는지."""
    return list(ranges[:limit]), len(ranges) > limit


def read(first: str, last: str, order: Mapping[str, int]) -> list[str]:
    """범위 [첫, 끝] 이 가리키는 블록 id(읽는 차례). 첫이 끝보다 뒤면 ValueError."""
    lo, hi = order[first], order[last]
    if lo > hi:
        raise ValueError(f"범위 차례가 거꾸로다: {first} > {last}")
    by_pos = {i: b for b, i in order.items()}
    return [by_pos[i] for i in range(lo, hi + 1)]
