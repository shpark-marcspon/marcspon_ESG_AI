"""말 목록(AI 0)과 갈래 짜기의 답 꼴. 랩 `semgraph/{sg1h.cmd_vocab, facets}.py` 를 옮겼다.

말 목록 = 섹션 제목 · 소제목 · 표 첫 행 칸 · 표 행 머리(행마다 첫 칸) — 나온 횟수 차례(같으면 글자 차례)로 1.2만 자까지,
「말(횟수)」를 ' · ' 로 잇는다. 갈래 짜기 프롬프트(greenwash/ge-facets@1)는 이 목록을 캐시 구획 끝에 둔다(같은 문서
안에서는 캐시가 걸린다). 답 꼴은 구조화 출력(FacetPlan)이고 갈래는 앞 8개까지 쓴다.
"""

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from esgapi.greenwash.engines.g1.passages import Built

VOCAB_CHARS: Final = 12000
FACETS_MAX: Final = 8
LIKE: Final = {"high": 0, "mid": 1, "low": 2}
NUMERIC: Final = re.compile(r"^[\d,.\s%()\-’'~]+$")

Likelihood = Literal["high", "mid", "low"]


def clean(s: str | None) -> str | None:
    t = re.sub(r"\s+", " ", re.sub(r"\d\)|\*", "", s or "")).strip(" ·-|")
    return t if 2 <= len(t) <= 40 and not NUMERIC.match(t) else None


def vocab(built: Built) -> str:
    cnt: Counter[str] = Counter()
    for title in built.titles.values():
        t = clean(title)
        if t:
            cnt[t] += 1
    for u in built.units:
        if u.kind == "heading":
            t = clean(u.text)
            if t:
                cnt[t] += 1
    for u in built.units:
        if u.kind != "table" or not u.rows:
            continue
        for cell in u.rows[0]:
            t = clean(cell)
            if t:
                cnt[t] += 1
        for r in u.rows[1:]:
            for cell in r:
                t = clean(cell)
                if t:
                    cnt[t] += 1
                    break
    items: list[str] = []
    used = 0
    for k, n in sorted(cnt.items(), key=lambda x: (-x[1], x[0])):
        t = f"{k}({n})"
        if used + len(t) + 3 > VOCAB_CHARS:
            break
        items.append(t)
        used += len(t) + 3
    return " · ".join(items)


class FacetOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    keywords: list[str]
    likelihood: Likelihood
    reason: str


class FacetPlan(BaseModel):
    """greenwash/ge-facets@1 의 답 꼴."""

    model_config = ConfigDict(extra="forbid")

    facets: list[FacetOut]


@dataclass(frozen=True, slots=True)
class Facet:
    name: str
    keywords: tuple[str, ...]
    likelihood: Likelihood

    @property
    def query(self) -> str:
        """갈래 하나의 찾는 글 = 이름 + 키워드(벡터·BM25 둘 다)."""
        return self.name + " " + " ".join(self.keywords)


def facets_of(plan: FacetPlan) -> tuple[Facet, ...]:
    return tuple(Facet(f.name, tuple(f.keywords), f.likelihood) for f in plan.facets[:FACETS_MAX])


def order_by_likelihood(per: Sequence[tuple[Facet, Sequence[str]]], top: int) -> list[str]:
    """갈래마다 상위 목록을 가능성 높은 갈래부터 돌아가며 한 개씩(겹침은 처음 것)."""
    ranked = sorted(enumerate(per), key=lambda x: (LIKE[x[1][0].likelihood], x[0]))
    out: list[str] = []
    seen: set[str] = set()
    for r in range(top):
        for _, (_, lst) in ranked:
            if r < len(lst) and lst[r] not in seen:
                seen.add(lst[r])
                out.append(lst[r])
    return out
