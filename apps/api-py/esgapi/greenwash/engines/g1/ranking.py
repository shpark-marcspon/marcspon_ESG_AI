"""순위 짜기(AI 0): 차례·RRF·구조 따라가기(P-s)·갈래 번갈아 합침·섹션째 넓히기. 랩 `semgraph/retrieve.py`·
`fixunits.{_graph,_section_expand}`·`facets._alt` 를 옮겼다.

  P-s(기본 순위 층 — D2) = RRF(벡터, BM25) 위에 구조 따라가기: 씨앗 = 상위 5(무게 1/순위), 관계 무게 다음 단락 0.6 ·
  같은 섹션 0.3 · 같은 쪽 0.3, 가운데 마디(섹션·쪽)는 1/√차수, 두 걸음. 최종 = RRF/최대 + 0.5 × 넓힘/최대.
"""

import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Final

SEEDS: Final = 5
LAMBDA: Final = 0.5
RRF_K: Final = 60
STRUCT_W: Final[Mapping[str, float]] = {"next_block": 0.6, "section_contains": 0.3, "on_page": 0.3}
SEC_MIN, SEC_TOP, CAP_S = 3, 20, 120


def ranks(scores: Sequence[float]) -> list[int]:
    """점수 내림차순의 자리 차례(같은 점수는 앞 자리 먼저 — sorted 는 안정)."""
    return sorted(range(len(scores)), key=lambda i: -scores[i])


def rrf(*orders: Sequence[int]) -> dict[int, float]:
    s: dict[int, float] = defaultdict(float)
    for order in orders:
        for r, i in enumerate(order):
            s[i] += 1 / (RRF_K + r + 1)
    return dict(s)


def by_score(scores: Mapping[int, float]) -> list[int]:
    return sorted(scores, key=lambda i: -scores[i])


class Graph:
    def __init__(self, edges: Sequence[tuple[str, str, str]], weights: Mapping[str, float]) -> None:
        self.adj: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for a, b, rel in edges:
            w = weights.get(rel)
            if w:
                self.adj[a].append((b, w))
                self.adj[b].append((a, w))

    def deg(self, n: str) -> int:
        return max(1, len(self.adj[n]))

    def spread(self, seeds: Mapping[str, float], hops: int = 2) -> dict[str, float]:
        acc: dict[str, float] = defaultdict(float)
        frontier = dict(seeds)
        for _ in range(hops):
            nxt: dict[str, float] = defaultdict(float)
            for n, s in frontier.items():
                for m, w in self.adj[n]:
                    v = s * w / math.sqrt(self.deg(n) if ":" in n else 1) / math.sqrt(self.deg(m) if ":" in m else 1)
                    nxt[m] = max(nxt[m], v)
            for m, v in nxt.items():
                if ":" not in m and m not in seeds:
                    acc[m] = max(acc[m], v)
            frontier = nxt
        return dict(acc)


def structure_graph(ids: Sequence[str], sections: Sequence[str], pages: Sequence[Sequence[int]]) -> Graph:
    """단락 차례대로: 같은 섹션의 다음 단락 · 섹션 마디 · 쪽 마디."""
    edges: list[tuple[str, str, str]] = []
    for i, pid in enumerate(ids):
        if i + 1 < len(ids) and sections[i + 1] == sections[i]:
            edges.append((pid, ids[i + 1], "next_block"))
        edges.append((pid, f"sec:{sections[i]}", "section_contains"))
        edges.extend((pid, f"page:{pg}", "on_page") for pg in pages[i])
    return Graph(edges, STRUCT_W)


def expand(c_scores: Mapping[int, float], ids: Sequence[str], graph: Graph, hops: int = 2) -> list[int]:
    top = by_score(c_scores)
    seeds = {ids[i]: 1 / (r + 1) for r, i in enumerate(top[:SEEDS])}
    acc = graph.spread(seeds, hops)
    cmax = max(c_scores.values(), default=0.0) or 1.0
    amax = max(acc.values(), default=0.0) or 1.0
    idx = {u: i for i, u in enumerate(ids)}
    final: dict[int, float] = defaultdict(float)
    for i, s in c_scores.items():
        final[i] += s / cmax
    for u, s in acc.items():
        final[idx[u]] += LAMBDA * s / amax
    return sorted(final, key=lambda i: -final[i])


def alternate(a: Sequence[str], c: Sequence[str], cap: int) -> list[str]:
    """두 차례를 번갈아 합쳐 cap 개까지(겹침은 처음 것)."""
    out: list[str] = []
    seen: set[str] = set()
    n = max(len(a), len(c))
    for k in range(n):
        for p in (a[k] if k < len(a) else None, c[k] if k < len(c) else None):
            if p and p not in seen and len(out) < cap:
                seen.add(p)
                out.append(p)
    return out


def section_expand(
    cand: Sequence[str], sec_of: Mapping[str, str], members_of: Mapping[str, Sequence[str]]
) -> list[str]:
    """상위 20 에 같은 섹션이 셋 이상이면 그 섹션 단락을 다 넣는다(120개까지, 많은 섹션부터)."""
    c = Counter(sec_of[p] for p in cand[:SEC_TOP])
    out = list(cand)
    have = set(out)
    for s, n in c.most_common():
        if n < SEC_MIN:
            break
        for p in members_of.get(s, ()):
            if p not in have and len(out) < CAP_S:
                have.add(p)
                out.append(p)
    return out
