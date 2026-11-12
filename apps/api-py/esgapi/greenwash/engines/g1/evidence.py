"""근거 찾기 F-b′(문서 전체, 단락 단위). 랩 `esg-lab/out/MB1/drivers/gm2_fb.py`(pool_for·assemble)를 옮겼다.

주장 하나:
  ① 자기 뺌 = 대상 블록을 품은 단락 전부 + 대상 문장(공백 지운 글)이 든 단락. 순위 입구와 마지막 근거에서 뺀다.
     섹션째 넓히기가 다시 넣은 자기 단락은 재순위 줄에는 보이고 근거에는 안 든다(랩과 같음).
  ② 갈래 짜기(포트 plan — luna, 말 목록은 포트가 쥔다) → 주장 글 + 갈래 글을 한 번에 임베딩(포트 embed).
  ③ 기본 순위 P-s(ranking 머리말) · 갈래마다 벡터·BM25 → RRF 상위 15 → 가능성 차례로 돌아가며 합침
     → 기본 순위 상위 50 과 번갈아 80 → 섹션째 넓히기 120.
  ④ 재순위(포트 rerank — luna, 줄마다 「[단락id] 글 앞 300자」). 잘린 응답은 포트가 앞에서 id 를 건져 complete=False 로.
  ⑤ 재순위 차례 + 나머지 후보 + 기본 순위 나머지 → 12,000자 예산(처음 넘는 단락에서 멈춤 —
     GE1c 가 b1 2단을 보고 8,000자에서 올림, 얼린 규칙 esg-lab/out/GE1c/rules.frozen.md).
결과는 판별 유니온: 찾음(found) · 찾았는데 없음(empty) · 찾기 실패(failed — 포트가 SearchFailed 를 던짐). 실패를 빈
목록으로 접지 않는다. 쪽 거름은 없다(점검 쪽 밖 단락도 근거가 된다 — E0 와 다른 점).
"""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict

from esgapi.greenwash.engines.g1 import ranking
from esgapi.greenwash.engines.g1.facets import Facet, FacetPlan, facets_of, order_by_likelihood
from esgapi.greenwash.engines.g1.lexical import BM25
from esgapi.greenwash.engines.g1.passages import Built, Passage

TOP: Final = 15
BASE_TOP: Final = 50
CAP_B: Final = 80
BUDGET_CHARS: Final = 12000
"""근거 글자 예산(GE1c ④ 얼린 값 — GE1 은 8000). extract 단계가 이 값을 data 에 싣고 index·judge 가 견준다
(flows/engine_g1.check_built — 이어 돌기에서 값이 바뀌면 G1ArtifactChanged)."""
LINE_CHARS: Final = 300
PARTIAL_SHARE: Final = 0.5

Stage = Literal["plan", "embed", "rerank"]
EvidenceWarning = Literal["rerank_cut_off", "rerank_partial"]

Vectors = npt.NDArray[np.float32]


class SearchFailed(Exception):
    """포트(갈래 짜기·임베딩·재순위)의 공급사 실패. stage = 어느 걸음에서."""

    def __init__(self, stage: Stage, code: str) -> None:
        super().__init__(f"근거 찾기 {stage} 실패: {code}")
        self.stage: Stage = stage
        self.code = code


@dataclass(frozen=True, slots=True)
class RerankReply:
    ids: tuple[str, ...]
    """돌려받은 단락 id(돌려받은 차례, 겹침·모르는 id 그대로 — 엔진이 거른다)."""
    complete: bool
    """False = 출력 상한에서 잘린 응답에서 건진 id."""


class RerankOrder(BaseModel):
    """greenwash/ge-rerank@1 의 답 꼴."""

    model_config = ConfigDict(extra="forbid")

    order: list[str]


PlanPort = Callable[[str], FacetPlan]
EmbedPort = Callable[[Sequence[str]], Sequence[Sequence[float]]]
RerankPort = Callable[[str, str], RerankReply]


@dataclass(frozen=True, slots=True)
class Ports:
    plan: PlanPort
    embed: EmbedPort
    rerank: RerankPort


@dataclass(frozen=True, slots=True)
class Claim:
    text: str
    block_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Found:
    passage_ids: tuple[str, ...]
    """근거 단락(근거 차례 — 판정에 보이는 차례)."""
    chars: int
    self_excluded: tuple[str, ...]
    facets: tuple[Facet, ...]
    pool: int
    """재순위에 보낸 후보 수."""
    returned: int
    """재순위가 돌려준 후보 안 id 수."""
    warnings: tuple[EvidenceWarning, ...]
    kind: Literal["found"] = "found"


@dataclass(frozen=True, slots=True)
class Empty:
    """찾았는데 예산 안에 든 단락이 없다(자기 단락뿐인 문서 등)."""

    self_excluded: tuple[str, ...]
    kind: Literal["empty"] = "empty"


@dataclass(frozen=True, slots=True)
class Failed:
    stage: Stage
    code: str
    kind: Literal["failed"] = "failed"


type Outcome = Found | Empty | Failed


def unit_rows(m: Vectors) -> Vectors:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (m / norms).astype(np.float32)


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text or ""))


class Index:
    """한 문서의 찾는 자리: 단락·단락 벡터(행 = 단락 차례, 정규화)·BM25·구조 그래프."""

    def __init__(self, built: Built, vectors: Vectors) -> None:
        ps = built.passages
        if not ps and vectors.size == 0:  # 642-1: 단락 0 — 빈 행렬(옛 index 의 (0,) 도)을 (0, 0) 으로
            vectors = np.zeros((0, 0), dtype=np.float32)
        if vectors.shape[0] != len(ps):
            raise ValueError(f"단락 벡터 {vectors.shape[0]}줄 ≠ 단락 {len(ps)}개")
        self.passages: tuple[Passage, ...] = ps
        self.ids = [p.id for p in ps]
        self.idx = {pid: i for i, pid in enumerate(self.ids)}
        self.by_id = {p.id: p for p in ps}
        self.length = {p.id: len(p.text) for p in ps}
        self.vectors = unit_rows(vectors)
        self.bm25 = BM25([p.text for p in ps])
        self.graph = ranking.structure_graph(self.ids, [p.section_id for p in ps], [p.pages for p in ps])
        self.sec_of = {p.id: p.section_id for p in ps}
        members: dict[str, list[str]] = defaultdict(list)
        for p in ps:
            members[p.section_id].append(p.id)
        self.members_of = dict(members)
        self._squashed = [_squash(p.text) for p in ps]

    def self_passages(self, claim: Claim) -> tuple[str, ...]:
        blocks = set(claim.block_ids)
        needle = _squash(claim.text)
        out = [
            p.id
            for p, sq in zip(self.passages, self._squashed, strict=True)
            if blocks & set(p.members) or (needle and needle in sq)
        ]
        return tuple(out)

    def _rrf(self, qvec: Vectors, qtext: str, drop: set[int]) -> dict[int, float]:
        va = [i for i in ranking.ranks(list(self.vectors @ qvec)) if i not in drop]
        vb = [i for i in ranking.ranks(self.bm25.scores(qtext)) if i not in drop]
        return ranking.rrf(va, vb)

    def base_order(self, qvec: Vectors, qtext: str, drop: set[int]) -> list[str]:
        """P-s: RRF(벡터, BM25) + 구조 따라가기. 자기 단락 뺌."""
        cs = self._rrf(qvec, qtext, drop)
        return [self.ids[i] for i in ranking.expand(cs, self.ids, self.graph) if i not in drop]

    def facet_top(self, fvec: Vectors, facet: Facet, drop: set[int]) -> list[str]:
        cs = self._rrf(fvec, facet.query, drop)
        return [self.ids[i] for i in ranking.by_score(cs)[:TOP]]

    def lines(self, ids: Sequence[str]) -> str:
        return "\n".join(f"[{p}] " + self.by_id[p].text.replace("\n", " / ")[:LINE_CHARS] for p in ids)

    def within_budget(self, order: Sequence[str], budget: int = BUDGET_CHARS) -> list[str]:
        used = 0
        got: list[str] = []
        for p in order:
            used += self.length[p]
            if used > budget:
                break
            got.append(p)
        return got


def find_evidence(index: Index, claim: Claim, ports: Ports, *, budget: int = BUDGET_CHARS) -> Outcome:
    """budget = 근거 글자 예산(GE1c — 2단 측정이 예산을 바꿔 잰다. 넘기지 않으면 BUDGET_CHARS)."""
    if not index.passages:  # 642-1: 단락 0 인 문서 — 부르기 0, 찾았는데 없음
        return Empty(self_excluded=())
    drop_ids = index.self_passages(claim)
    drop = {index.idx[p] for p in drop_ids}
    try:
        facets = facets_of(ports.plan(claim.text))
        vecs = np.asarray(ports.embed([claim.text, *(f.query for f in facets)]), dtype=np.float32)
    except SearchFailed as err:
        return Failed(stage=err.stage, code=err.code)
    vecs = unit_rows(vecs)
    base = index.base_order(vecs[0], claim.text, drop)
    per = [(f, index.facet_top(vecs[k + 1], f, drop)) for k, f in enumerate(facets)]
    rr = order_by_likelihood(per, TOP)
    cand = ranking.alternate(rr, base[:BASE_TOP], CAP_B)
    cand = ranking.section_expand(cand, index.sec_of, index.members_of)
    try:
        reply = ports.rerank(claim.text, index.lines(cand))
    except SearchFailed as err:
        return Failed(stage=err.stage, code=err.code)
    in_cand = set(cand)
    top = [p for p in dict.fromkeys(reply.ids) if p in in_cand]
    warnings: list[EvidenceWarning] = []
    if not reply.complete:
        warnings.append("rerank_cut_off")
    if len(top) < PARTIAL_SHARE * len(cand):
        warnings.append("rerank_partial")
    seen = set(top)
    order = top + [p for p in cand if p not in seen]
    seen |= set(order)
    order += [p for p in base if p not in seen]
    dropped = set(drop_ids)
    order = [p for p in order if p not in dropped]
    got = index.within_budget(order, budget)
    if not got:
        return Empty(self_excluded=drop_ids)
    return Found(
        passage_ids=tuple(got),
        chars=sum(index.length[p] for p in got),
        self_excluded=drop_ids,
        facets=facets,
        pool=len(cand),
        returned=len(top),
        warnings=tuple(warnings),
    )


def evidence_text(index: Index, passage_ids: Sequence[str]) -> str:
    """판정에 보일 근거 글: 단락마다 「[단락id · p.첫쪽]」 머리 + 글."""
    return "\n\n".join(f"[{p} · p.{index.by_id[p].page}]\n{index.by_id[p].text}" for p in passage_ids)


PID: Final = re.compile(r"\[?(P\d+)")


def salvage_ids(text: str) -> tuple[str, ...]:
    """잘린 재순위 응답에서 단락 id 를 앞에서부터 건진다(랩 facets._rerank 의 정규식 길)."""
    return tuple(m.group(1) for m in PID.finditer(text))


def pid_of(item: str) -> str:
    """luna 가 id 대신 「[P12] 글…」 줄을 통째로 돌려주는 때가 있다(랩 sg1d._pid) — 앞의 id 만."""
    m = re.match(r"\s*\[?(P\d+)", item)
    return m.group(1) if m else item
