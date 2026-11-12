"""순위 짜기(engines/g1/ranking.py — 밴드 GE1 T6): RRF 차례 · 번갈아 합침 · 섹션째 넓히기 120 · 구조 따라가기."""

import pytest

from esgapi.greenwash.engines.g1 import ranking


def test_rrf_sums_reciprocal_ranks() -> None:
    s = ranking.rrf([0, 1, 2], [2, 0])
    assert s[0] == pytest.approx(1 / 61 + 1 / 62)
    assert s[2] == pytest.approx(1 / 63 + 1 / 61)
    assert s[1] == pytest.approx(1 / 62)
    assert ranking.by_score(s) == [0, 2, 1]


def test_ranks_keep_ties_in_position_order() -> None:
    assert ranking.ranks([0.5, 0.9, 0.5]) == [1, 0, 2]


def test_alternate_interleaves_and_caps() -> None:
    assert ranking.alternate(["a", "b", "c"], ["x", "a", "y"], 10) == ["a", "x", "b", "c", "y"]
    assert ranking.alternate(["a", "b", "c"], ["x", "y"], 3) == ["a", "x", "b"]


def test_section_expand_adds_sections_seen_three_times_up_to_120() -> None:
    ids = [f"P{i}" for i in range(300)]
    sec_of = {p: ("big" if i >= 10 else f"s{i}") for i, p in enumerate(ids)}
    members = {"big": ids[10:]}
    for i in range(10):
        members[f"s{i}"] = [ids[i]]
    cand = ids[:10] + ids[10:13]
    out = ranking.section_expand(cand, sec_of, members)
    assert out[:13] == cand
    assert len(out) == ranking.CAP_S == 120
    assert len(set(out)) == len(out)


def test_section_expand_needs_three_in_the_top_twenty() -> None:
    ids = [f"P{i}" for i in range(40)]
    sec_of = {p: ("big" if i in (0, 1, 25) else f"s{i}") for i, p in enumerate(ids)}
    members = {"big": ["P0", "P1", "P25", "P39"]}
    cand = ids[:30]
    assert ranking.section_expand(cand, sec_of, members) == cand


def test_expand_lifts_a_neighbour_of_the_top_seed() -> None:
    ids = ["P0", "P1", "P2", "P3"]
    graph = ranking.structure_graph(ids, ["a", "a", "b", "c"], [[1], [1], [5], [6]])
    scores = {0: 1.0, 2: 0.4, 3: 0.39}
    order = ranking.expand(scores, ids, graph)
    assert order[0] == 0
    assert 1 in order  # 점수가 없던 이웃이 따라가기로 들어온다
    assert order.index(1) < order.index(3)
