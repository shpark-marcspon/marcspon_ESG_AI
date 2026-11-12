"""후보 문장의 자리(AI 0): 쪽 글 · 문장 → 블록 짝 · 같은 열쇠 합침 · 구획 나누기. 흐름(flows/engine_g1)의 candidates·
judge·gather 단계가 부른다.

  쪽 글        뷰의 body 단위(passages.units_of — 표는 칸을 이은 글)를 읽는 차례로 줄바꿈 이은 글(발주서 2-4 R9 — pypdf
               쪽 글이 아니라 블록과 짝이 바로 되는 글). 2,500자 자름은 E0 get_page_text 가 한다.
  블록 짝      정규화(checks.squash — NFC + 공백 전부 지움) 뒤 그 쪽 body 단위 글에 문장이 드는 첫 단위(읽는
               차례) → 하나. 하나에 안 들고 이웃 둘을 이은 글에 들면 → 둘. 못 찾으면 None(그 후보는 항목이 아니라
               구획의 unplaced). 발주서는 「NFC + 공백 접기」로 적었으나 포함 검사(checks.quote_in_block)와 같은
               squash 를 쓴다 — PDF 줄 끊김이 낱말 안에도 들어 접기로는 짝이 덜 지어지고, 짝과 검사가 다른
               정규화면 짝을 지은 문장이 검사에 걸릴 수 있다.
  합침         같은 stableKey(문서 sha · fold 문장 · 쪽)의 후보는 첫 것 하나(계획 차례). 파트 이름은 합친다.
  구획         후보 8개씩(계획 차례). span = "c<첫 차례>-<끝 차례>" + 블록이 있으면 ":<첫 블록>~<끝 블록>"(블록
               id 가 `p4-b2` 꼴이라 발주서의 「b<첫>-<끝>」은 b·- 가 겹친다 — 검증 1 R4. 차례 번호가 있어 구획
               열쇠가 겹치지 않는다).
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, cast

from esgapi.greenwash.engines.g1.checks import squash, stable_key
from esgapi.greenwash.engines.g1.passages import Unit

SEGMENT_SIZE: Final = 8
SEGMENT_KIND: Final = "claims"


@dataclass(frozen=True, slots=True)
class PageUnits:
    """한 쪽의 body 단위(읽는 차례)."""

    page: int
    units: tuple[Unit, ...]

    @property
    def text(self) -> str:
        return "\n".join(u.text for u in self.units if u.text)


def pages_of(units: Iterable[Unit]) -> dict[int, PageUnits]:
    """단위 → 쪽마다 body 단위(읽는 차례 그대로)."""
    by: dict[int, list[Unit]] = {}
    for u in units:
        if u.region == "body":
            by.setdefault(u.page, []).append(u)
    return {p: PageUnits(page=p, units=tuple(us)) for p, us in sorted(by.items())}


def place(sentence: str, page: PageUnits) -> tuple[str, ...] | None:
    """문장 → 블록 id 하나나 이웃 둘(읽는 차례). 못 찾으면 None."""
    needle = squash(sentence)
    if not needle:
        return None
    texts = [squash(u.text) for u in page.units]
    for u, t in zip(page.units, texts, strict=True):
        if needle in t:
            return (u.id,)
    for i in range(len(page.units) - 1):
        if needle in texts[i] + texts[i + 1]:
            return (page.units[i].id, page.units[i + 1].id)
    return None


@dataclass(slots=True)
class Candidate:
    """후보 하나(계획 차례). block_ids 가 None 이면 unplaced."""

    sentence: str
    page: int
    block_ids: tuple[str, ...] | None
    stable_key: str
    parts: list[str] = field(default_factory=list[str])

    def to_json(self) -> dict[str, object]:
        return {
            "sentence": self.sentence,
            "page": self.page,
            "blockIds": list(self.block_ids) if self.block_ids is not None else None,
            "stableKey": self.stable_key,
            "parts": list(self.parts),
        }


def candidate_of(data: Mapping[str, object]) -> Candidate:
    """to_json 의 거꾸로(구획 입력에서 다시 짓는다)."""
    blocks = data["blockIds"]
    parts = data["parts"]
    return Candidate(
        sentence=str(data["sentence"]),
        page=int(str(data["page"])),
        block_ids=tuple(str(b) for b in cast("list[object]", blocks)) if isinstance(blocks, list) else None,
        stable_key=str(data["stableKey"]),
        parts=[str(p) for p in cast("list[object]", parts)] if isinstance(parts, list) else [],
    )


def merge(candidates: Iterable[Candidate]) -> list[Candidate]:
    """같은 stableKey 는 첫 것 하나(파트 이름은 합침, 차례는 첫 것의 자리)."""
    out: dict[str, Candidate] = {}
    for c in candidates:
        if c.stable_key in out:
            kept = out[c.stable_key]
            kept.parts = list(dict.fromkeys(kept.parts + c.parts))
        else:
            out[c.stable_key] = c
    return list(out.values())


def make_candidate(document_sha256: str, sentence: str, page: PageUnits, parts: Sequence[str]) -> Candidate:
    return Candidate(
        sentence=sentence,
        page=page.page,
        block_ids=place(sentence, page),
        stable_key=stable_key(document_sha256, sentence, page.page),
        parts=list(parts),
    )


def chunks(candidates: Sequence[Candidate], size: int = SEGMENT_SIZE) -> list[tuple[str, list[Candidate]]]:
    """후보 → (span, 구획의 후보). span 은 머리말의 꼴."""
    out: list[tuple[str, list[Candidate]]] = []
    for start in range(0, len(candidates), size):
        part = list(candidates[start : start + size])
        span = f"c{start + 1}-{start + len(part)}"
        blocks = [b for c in part for b in (c.block_ids or ())]
        if blocks:
            span += f":{blocks[0]}~{blocks[-1]}"
        out.append((span, part))
    return out
