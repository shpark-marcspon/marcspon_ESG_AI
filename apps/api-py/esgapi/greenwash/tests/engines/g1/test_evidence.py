"""근거 찾기 F-b′(engines/g1/evidence.py — 밴드 GE1 T7·T8·T9). 포트는 모의(결정적 벡터 · 대본 갈래 · 대본 재순위)."""

import hashlib
from collections.abc import Sequence
from typing import NoReturn

import numpy as np
import pytest

from esgapi.greenwash.engines.g1 import evidence as E
from esgapi.greenwash.engines.g1.facets import FacetPlan
from esgapi.greenwash.engines.g1.passages import Built, Passage

CLAIM_TEXT = "가상회사는 모든 사업장의 전력을 재생에너지로 바꾸었습니다."


def vec(text: str) -> list[float]:
    """글 → 결정적 벡터(두 글자 조각 해시 주머니). 같은 낱말이 많으면 가깝다."""
    v = np.zeros(64, dtype=np.float32)
    t = "".join(text.split())
    for i in range(len(t) - 1):
        v[int(hashlib.sha256(t[i : i + 2].encode()).hexdigest(), 16) % 64] += 1.0
    return [float(x) for x in v]


def passage(pid: str, text: str, *, page: int, sid: str = "s1", members: Sequence[str] | None = None) -> Passage:
    return Passage(pid, "paragraph", [page], sid, list(members or [f"b-{pid}"]), text)


def doc() -> Built:
    ps = [
        passage("P1", "머리말 가상회사 소개입니다.", page=1),
        passage(
            "P2",
            "가상회사는 모든 사업장의 전력을 재생에너지로 바꾸었습니다. 앞으로도 노력합니다.",
            page=3,
            members=["b-claim", "b-x"],
        ),
        passage("P3", "재생에너지 전력 사용 비율 표: 국내 사업장 100%, 해외 사업장 40%.", page=40, sid="s9"),
        passage("P4", "요약: 가상회사는 모든 사업장의 전력을 재생에너지로 바꾸었습니다.", page=2),
        passage("P5", "협력회사 점검 결과와 공급망 관리 방침.", page=50, sid="s8"),
        passage("P6", "재생에너지 전환 범위에서 해외 일부 사업장은 빠졌습니다(주석).", page=41, sid="s9"),
    ]
    return Built(passages=tuple(ps), stat={}, units=(), titles={}, block_text={})


def index() -> E.Index:
    b = doc()
    return E.Index(b, np.asarray([vec(p.text) for p in b.passages], dtype=np.float32))


def plan(_: str) -> FacetPlan:
    return FacetPlan.model_validate(
        {
            "facets": [
                {
                    "name": "재생에너지 실적",
                    "keywords": ["재생에너지", "전력", "비율"],
                    "likelihood": "high",
                    "reason": "-",
                },
                {"name": "반대·한정 사실", "keywords": ["해외", "빠졌", "범위"], "likelihood": "mid", "reason": "-"},
            ]
        }
    )


def embed(texts: Sequence[str]) -> list[list[float]]:
    return [vec(t) for t in texts]


def rerank_all(claim: str, lines: str) -> E.RerankReply:
    ids = [line.split("]")[0].lstrip("[") for line in lines.splitlines()]
    return E.RerankReply(ids=tuple(reversed(ids)), complete=True)


PORTS = E.Ports(plan=plan, embed=embed, rerank=rerank_all)
CLAIM = E.Claim(text=CLAIM_TEXT, block_ids=("b-claim",))


# ── T7 자기 뺌 ─────────────────────────────────────────────────────────


def test_self_passages_are_the_target_block_and_the_same_sentence() -> None:
    assert index().self_passages(CLAIM) == ("P2", "P4")


def test_self_passages_never_come_back_as_evidence() -> None:
    got = E.find_evidence(index(), CLAIM, PORTS)
    assert isinstance(got, E.Found)
    assert got.self_excluded == ("P2", "P4")
    assert not {"P2", "P4"} & set(got.passage_ids)


def test_self_passages_are_left_out_of_the_ranked_candidates() -> None:
    shown: list[str] = []

    def rerank(claim: str, lines: str) -> E.RerankReply:
        shown.extend(line.split("]")[0].lstrip("[") for line in lines.splitlines())
        return E.RerankReply(ids=tuple(shown), complete=True)

    E.find_evidence(index(), CLAIM, E.Ports(plan=plan, embed=embed, rerank=rerank))
    assert shown and not {"P2", "P4"} & set(shown)


# ── T8 예산·문서 전체 ──────────────────────────────────────────────────


def test_evidence_stays_within_the_char_budget_and_follows_the_rerank_order() -> None:
    """GE1c ④: 예산 12,000(GE1 8,000) — 같은 자료(918·919자 단락 29)에서 열셋째까지 들고 열넷째에서 멈춘다."""
    long_ps = tuple(passage(f"P{i}", f"가상 재생에너지 전력 단락 {i}. " + "가" * 900, page=i) for i in range(1, 30))
    b = Built(passages=long_ps, stat={}, units=(), titles={}, block_text={})
    idx = E.Index(b, np.asarray([vec(p.text) for p in long_ps], dtype=np.float32))
    got = E.find_evidence(idx, E.Claim(text="가상 재생에너지 주장", block_ids=("none",)), PORTS)
    assert isinstance(got, E.Found)
    assert got.chars <= E.BUDGET_CHARS
    sizes = {idx.length[p] for p in idx.ids}
    assert E.BUDGET_CHARS == 12000
    assert max(sizes) * 13 <= E.BUDGET_CHARS < min(sizes) * 14
    assert len(got.passage_ids) == 13  # 열넷째에서 예산을 넘어 멈춘다


def test_evidence_comes_from_the_whole_document() -> None:
    got = E.find_evidence(index(), CLAIM, PORTS)
    assert isinstance(got, E.Found)
    pages = {index().by_id[p].page for p in got.passage_ids}
    assert pages & {40, 41, 50}  # 대상 쪽(3) 밖 단락이 근거로 온다


def test_evidence_text_names_each_passage() -> None:
    assert E.evidence_text(index(), ["P3"]) == "[P3 · p.40]\n" + doc().passages[2].text


# ── T9 실패·건짐 ───────────────────────────────────────────────────────


@pytest.mark.parametrize("stage", ["plan", "embed", "rerank"])
def test_provider_failure_is_a_failed_branch_not_an_empty_list(stage: str) -> None:
    def boom(*_: object) -> object:
        raise E.SearchFailed(stage, "provider_error")  # type: ignore[arg-type]

    ports = E.Ports(
        plan=boom if stage == "plan" else plan,  # type: ignore[arg-type]
        embed=boom if stage == "embed" else embed,  # type: ignore[arg-type]
        rerank=boom if stage == "rerank" else rerank_all,  # type: ignore[arg-type]
    )
    got = E.find_evidence(index(), CLAIM, ports)
    assert got == E.Failed(stage=stage, code="provider_error")  # type: ignore[arg-type]


def test_a_document_of_only_self_passages_is_empty_not_failed() -> None:
    b = Built(
        passages=(passage("P1", CLAIM_TEXT, page=1, members=["b-claim"]),), stat={}, units=(), titles={}, block_text={}
    )
    idx = E.Index(b, np.asarray([vec(CLAIM_TEXT)], dtype=np.float32))
    got = E.find_evidence(idx, CLAIM, PORTS)
    assert got == E.Empty(self_excluded=("P1",))


def test_a_cut_off_rerank_is_salvaged_with_named_warnings() -> None:
    def rerank(claim: str, lines: str) -> E.RerankReply:
        return E.RerankReply(ids=E.salvage_ids('{"order": ["P6", "[P'), complete=False)

    got = E.find_evidence(index(), CLAIM, E.Ports(plan=plan, embed=embed, rerank=rerank))
    assert isinstance(got, E.Found)
    assert got.passage_ids[0] == "P6"
    assert (got.returned, got.pool) == (1, 4)
    assert set(got.warnings) == {"rerank_cut_off", "rerank_partial"}


def test_salvage_ids_reads_ids_from_a_cut_reply() -> None:
    assert E.salvage_ids('{"order": ["P6", "[P3] 재생에너지 전력') == ("P6", "P3")


def test_a_complete_rerank_has_no_warning() -> None:
    got = E.find_evidence(index(), CLAIM, PORTS)
    assert isinstance(got, E.Found)
    assert got.warnings == ()
    assert got.returned == got.pool


def test_pid_of_takes_the_leading_id() -> None:
    assert E.pid_of("[P12] 글 앞부분") == "P12"
    assert E.pid_of("P3") == "P3"
    assert E.pid_of("모름") == "모름"


def test_section_widening_does_not_bring_self_passages_back() -> None:
    """같은 섹션 단락이 상위에 셋 이상이면 섹션째 넓히기가 그 섹션 단락을 다 넣는다 — 자기 단락도 그 섹션에 있다."""
    ps = [passage(f"P{i}", f"재생에너지 전력 실적 {i} 가상 단락입니다.", page=10 + i) for i in range(1, 6)]
    ps.append(passage("P9", CLAIM_TEXT, page=3, members=["b-claim"]))
    b = Built(passages=tuple(ps), stat={}, units=(), titles={}, block_text={})
    idx = E.Index(b, np.asarray([vec(p.text) for p in ps], dtype=np.float32))
    shown: list[str] = []

    def rerank(claim: str, lines: str) -> E.RerankReply:
        shown.extend(line.split("]")[0].lstrip("[") for line in lines.splitlines())
        return E.RerankReply(ids=tuple(shown), complete=True)

    got = E.find_evidence(idx, CLAIM, E.Ports(plan=plan, embed=embed, rerank=rerank))
    assert "P9" in shown  # 넓히기가 섹션째 넣었다(재순위에는 보인다)
    assert isinstance(got, E.Found)
    assert "P9" not in got.passage_ids


def test_unknown_and_outside_ids_from_the_reranker_are_dropped() -> None:
    def rerank(claim: str, lines: str) -> E.RerankReply:
        first = lines.splitlines()[0].split("]")[0].lstrip("[")
        return E.RerankReply(ids=("P999", "P2", first), complete=True)

    got = E.find_evidence(index(), CLAIM, E.Ports(plan=plan, embed=embed, rerank=rerank))
    assert isinstance(got, E.Found)
    assert got.returned == 1
    assert "P999" not in got.passage_ids and "P2" not in got.passage_ids


# ── 642-1 단락 0(GE1b T3) · 642-5 처분 ──


def refusing_ports() -> E.Ports:
    def no(*_: object) -> NoReturn:
        raise AssertionError("단락 0 이면 포트를 부르지 않는다")

    return E.Ports(plan=no, embed=no, rerank=no)


@pytest.mark.parametrize("shape", [(0,), (0, 0)])
def test_no_passages_is_empty_without_a_call(shape: tuple[int, ...]) -> None:
    """642-1: 단락 0 인 문서(빈 index — 옛 꼴 (0,) 도)는 Index 가 서고 근거 찾기는 부르기 0 으로 Empty."""
    empty = Built(passages=(), stat={}, units=(), titles={}, block_text={})
    idx = E.Index(empty, np.zeros(shape, dtype=np.float32))
    got = E.find_evidence(idx, E.Claim(text=CLAIM_TEXT, block_ids=("b-claim",)), refusing_ports())
    assert got == E.Empty(self_excluded=())


def test_a_first_passage_over_the_char_budget_leaves_the_evidence_empty() -> None:
    """642-5 처분(GE1c — 랩과 같음): 예산(12,000자)을 넘는 단락이 순서 첫째면 within_budget 은 거기서 멈춰 근거가
    빈다(고침 0 — 네 권 단락 최대 3,590자라 실제 문서에서는 0, 보고 642-5 잼)."""
    big = Built(
        passages=(passage("P1", "가" * (E.BUDGET_CHARS + 1), page=1), passage("P2", "짧은 가상 단락", page=2)),
        stat={},
        units=(),
        titles={},
        block_text={},
    )
    idx = E.Index(big, np.asarray([vec(p.text) for p in big.passages], dtype=np.float32))
    assert idx.within_budget(["P1", "P2"]) == []
    assert idx.within_budget(["P2", "P1"]) == ["P2"]


# ── GE1c ① T9 예산 인자 ────────────────────────────────────────────────


def _long_index() -> tuple[E.Index, E.Claim]:
    long_ps = tuple(passage(f"P{i}", f"가상 재생에너지 전력 단락 {i}. " + "가" * 900, page=i) for i in range(1, 30))
    b = Built(passages=long_ps, stat={}, units=(), titles={}, block_text={})
    return E.Index(b, np.asarray([vec(p.text) for p in long_ps], dtype=np.float32)), E.Claim(
        text="가상 재생에너지 주장", block_ids=("none",)
    )


@pytest.mark.parametrize("budget", [3000, 12000, 16000])
def test_t9_budget_argument_bounds_the_evidence_chars(budget: int) -> None:
    idx, claim = _long_index()
    got = E.find_evidence(idx, claim, PORTS, budget=budget)
    assert isinstance(got, E.Found)
    assert got.chars <= budget
    left = [p for p in idx.ids if p not in got.passage_ids]
    assert got.chars + min(idx.length[p] for p in left) > budget  # 다음 단락은 예산을 넘는다


def test_t9_a_smaller_budget_is_a_prefix_of_a_larger_one_and_no_argument_is_the_frozen_12000() -> None:
    idx, claim = _long_index()
    small = E.find_evidence(idx, claim, PORTS, budget=4000)
    big = E.find_evidence(idx, claim, PORTS, budget=16000)
    default = E.find_evidence(idx, claim, PORTS)
    assert isinstance(small, E.Found) and isinstance(big, E.Found) and isinstance(default, E.Found)
    assert big.passage_ids[: len(small.passage_ids)] == small.passage_ids
    assert len(big.passage_ids) > len(small.passage_ids)
    assert default == E.find_evidence(idx, claim, PORTS, budget=12000)
    assert default != E.find_evidence(idx, claim, PORTS, budget=8000)
