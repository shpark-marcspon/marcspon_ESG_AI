"""Scope 1·2 대시보드의 순수 셈(service/utils/dashboard.py — 밴드 S12a-3 ①). DB 0.

값·이름은 지어낸 것이다(실제 회사·사업장·배출량 0). 손셈:
  뿌리 「범위 가」 = 1.5 + 2.25 = 3.75 · 뿌리 「범위 나」 = 0.5 · 합계 3.75 + 0.5 = 4.25
  유형 「유형 가1」 3.75 의 share = 3.75 / 3.75 × 100 = 100.0
"""

from decimal import Decimal

from esgapi.inventory.service.utils.dashboard import (
    TOP_SOURCES,
    Dashboard,
    EnabledSite,
    Line,
    SiteTotal,
    Source,
    dashboard,
    share,
    unconfigured,
)
from esgapi.inventory.service.utils.entries import paths_of
from esgapi.inventory.service.utils.ghg_pool import NodeView

YEAR = 2025
GA, NA = EnabledSite(1, "가 사업장"), EnabledSite(2, "나 사업장")


def node(node_id: int, level: str, name: str, parent: int | None, sort: int = 0) -> NodeView:
    return NodeView(id=node_id, level=level, name=name, parent_id=parent, sort_order=sort, child_count=0)


def tree(sources: int = 1, *, second_root: bool = True) -> list[NodeView]:
    """뿌리 가(10) 아래 유형 sources 개(11, 12, …) — 유형마다 활동 하나·잎 하나(잎 id = 유형 id × 100).
    second_root 면 뿌리 나(20) → 유형 21 → 활동 → 잎 2100. 차례는 tree_nodes 꼴(단 → sort_order → id)."""
    roots = [node(10, "scope", "범위 가", None, 0)]
    kinds: list[NodeView] = []
    acts: list[NodeView] = []
    leaves: list[NodeView] = []
    for index in range(sources):
        kind = 11 + index
        kinds.append(node(kind, "source_type", f"유형 가{index + 1}", 10, index))
        acts.append(node(kind * 10, "activity", f"활동 가{index + 1}", kind))
        leaves.append(node(kind * 100, "facility", f"잎 가{index + 1}", kind * 10))
    if second_root:
        roots.append(node(20, "scope", "범위 나", None, 1))
        kinds.append(node(21, "source_type", "유형 나1", 20))
        acts.append(node(210, "activity", "활동 나1", 21))
        leaves.append(node(2100, "facility", "잎 나1", 210))
    return [*roots, *kinds, *acts, *leaves]


def run(
    nodes: list[NodeView],
    lines: list[Line],
    *,
    visible: set[int] | None = None,
    sites: tuple[EnabledSite, ...] = (GA, NA),
) -> Dashboard:
    leaves = {n.id for n in nodes if n.level == "facility"}
    return dashboard(
        year=YEAR,
        decimals=2,
        visible=leaves if visible is None else visible,
        nodes=nodes,
        paths=paths_of(nodes),
        sites=sites,
        lines=lines,
    )


def line(node_id: int, emission: str | None, site: EnabledSite = GA, problem: str | None = None) -> Line:
    return Line(
        node_id=node_id, site_id=site.id, emission=None if emission is None else Decimal(emission), problem=problem
    )


def test_root_sums_total_and_by_site_by_hand() -> None:
    found = run(tree(), [line(1100, "1.5"), line(1100, "2.25", NA), line(2100, "0.5", NA)])
    assert found.configured and found.complete and found.decimals == 2
    assert [(s.scope_id, s.scope_name, s.value) for s in found.scopes] == [
        (10, "범위 가", Decimal("3.75")),
        (20, "범위 나", Decimal("0.5")),
    ]
    assert found.scope12 == Decimal("4.25")
    assert found.by_site == (
        SiteTotal(1, "가 사업장", ((10, Decimal("1.5")), (20, None))),
        SiteTotal(2, "나 사업장", ((10, Decimal("2.25")), (20, Decimal("0.5")))),
    )
    assert found.scopes[0].top_sources == (Source(11, "유형 가1", Decimal("3.75"), Decimal("100.0")),)
    assert [s.scope_order for s in found.scopes] == [1, 2]


def test_scope_order_is_the_rank_among_all_pool_roots_not_the_list_position() -> None:
    """검증 B1: 둘째 뿌리의 잎만 고른 회사 — scopes 는 하나지만 scope_order 는 2(화면이 「Scope 2」 자리에 그린다)."""
    found = run(tree(), [line(2100, "0.5")], visible={2100})
    (scope,) = found.scopes
    assert (scope.scope_id, scope.scope_name, scope.scope_order) == (20, "범위 나", 2)
    assert found.by_site[0].values == ((20, Decimal("0.5")),)


def test_top_five_of_six_sources_biggest_first_ties_in_tree_order() -> None:
    nodes = tree(6, second_root=False)
    # 유형 가1..가6 = 1 · 6 · 3 · 3 · 5 · 2 → 6(가2) 5(가5) 3(가3) 3(가4 — 같은 값 트리 차례) 2(가6), 1 빠짐
    values = ["1", "6", "3", "3", "5", "2"]
    found = run(nodes, [line((11 + i) * 100, v) for i, v in enumerate(values)], sites=(GA,))
    (scope,) = found.scopes
    assert scope.value == Decimal(20)
    assert len(scope.top_sources) == TOP_SOURCES == 5
    assert [(s.name, s.value) for s in scope.top_sources] == [
        ("유형 가2", Decimal(6)),
        ("유형 가5", Decimal(5)),
        ("유형 가3", Decimal(3)),
        ("유형 가4", Decimal(3)),
        ("유형 가6", Decimal(2)),
    ]
    assert [s.share for s in scope.top_sources] == [
        Decimal("30.0"),
        Decimal("25.0"),
        Decimal("15.0"),
        Decimal("15.0"),
        Decimal("10.0"),
    ]


def test_a_tie_keeps_tree_order_not_id_order() -> None:
    nodes = tree(2, second_root=False)
    # 유형 가2(12)의 sort_order 를 가1(11)보다 앞으로 — tree_nodes 차례는 단 → sort_order → id.
    nodes = [node(12, "source_type", "유형 가2", 10, -1) if n.id == 12 else n for n in nodes]
    nodes.sort(key=lambda n: (("scope", "source_type", "activity", "facility").index(n.level), n.sort_order, n.id))
    found = run(nodes, [line(1100, "2"), line(1200, "2")], sites=(GA,))
    assert [s.node_id for s in found.scopes[0].top_sources] == [12, 11]


def test_a_tie_beyond_28_digits_keeps_tree_order_and_order_by_value() -> None:
    """28자리 넘는 값의 차례도 정확하다(값을 뒤집으면 기본 문맥 prec 28 로 반올림돼 다른 값이 같아진다 — 검증 R1)."""
    big = "1" + "0" * 29
    found = run(tree(3, second_root=False), [line(1100, big), line(1200, big + "1"), line(1300, big)], sites=(GA,))
    assert [s.node_id for s in found.scopes[0].top_sources] == [12, 11, 13]


def test_a_none_source_is_left_out_and_zero_stays() -> None:
    found = run(tree(3, second_root=False), [line(1100, None), line(1200, "0"), line(1300, "4")], sites=(GA,))
    (scope,) = found.scopes
    assert [(s.node_id, s.value, s.share) for s in scope.top_sources] == [
        (13, Decimal(4), Decimal("100.0")),
        (12, Decimal(0), Decimal("0.0")),
    ]


def test_a_broken_path_is_not_counted() -> None:
    nodes = tree()
    # 잎 2100 의 활동(210)이 지워짐 — paths_of 가 그 줄을 뺀다(뿌리 나도 목록에서 빠진다).
    broken = [n for n in nodes if n.id != 210]
    found = run(broken, [line(1100, "1"), line(2100, "7")], visible={1100, 2100})
    assert [s.scope_id for s in found.scopes] == [10]
    assert found.scope12 == Decimal(1)


def test_a_one_step_path_counts_in_the_root_but_not_in_top_sources() -> None:
    """2단보다 짧은 줄(뿌리뿐 — 풀이 막지만 순수 층은 모른다)은 뿌리 합에만 들고 상위 5 묶음에는 없다."""
    nodes = [node(10, "scope", "범위 가", None)]
    found = run(nodes, [line(10, "2")], visible={10}, sites=(GA,))
    (scope,) = found.scopes
    assert (scope.value, scope.top_sources) == (Decimal(2), ())


def test_share_rounds_half_up_at_one_decimal() -> None:
    assert share(Decimal(1), Decimal(8)) == Decimal("12.5")  # 12.5 그대로
    assert share(Decimal(1), Decimal(16)) == Decimal("6.3")  # 6.25 → 6.3(HALF_UP — HALF_EVEN 이면 6.2)
    assert share(Decimal(1), Decimal(3)) == Decimal("33.3")
    assert share(Decimal(2), Decimal(3)) == Decimal("66.7")
    assert share(Decimal(1), Decimal(0)) is None
    assert share(Decimal(1), None) is None


def test_share_divides_by_the_root_sum() -> None:
    found = run(tree(2), [line(1100, "1"), line(1200, "3"), line(2100, "4")], sites=(GA,))
    first, second = found.scopes
    assert [s.share for s in first.top_sources] == [Decimal("75.0"), Decimal("25.0")]  # 분모 4(범위 가), 8 아님
    assert [s.share for s in second.top_sources] == [Decimal("100.0")]


def test_a_zero_root_has_no_share() -> None:
    found = run(tree(1, second_root=False), [line(1100, "0")], sites=(GA,))
    assert found.scopes[0].top_sources == (Source(11, "유형 가1", Decimal(0), None),)


def test_one_problem_line_makes_it_incomplete() -> None:
    clean = run(tree(), [line(1100, "1"), line(2100, None)])
    assert clean.complete  # 빈 행은 문제 아님
    found = run(tree(), [line(1100, "1"), line(2100, None, problem="factor_incomplete")])
    assert not found.complete


def test_lines_of_off_sites_hidden_leaves_or_unknown_nodes_are_not_counted() -> None:
    other = EnabledSite(3, "다 사업장")
    lines = [
        line(1100, "1"),
        line(1100, "100", other, problem="factor_incomplete"),  # 켠 사업장 밖
        line(2100, "200", problem="factor_incomplete"),  # 숨긴 선택(visible 밖)
        line(9999, "300"),  # 풀에 없는 잎
    ]
    found = run(tree(), lines, visible={1100})
    assert [(s.scope_id, s.value) for s in found.scopes] == [(10, Decimal(1))]
    assert found.complete
    assert found.scope12 == Decimal(1)


def test_a_root_whose_leaves_have_no_value_is_still_listed_with_none() -> None:
    found = run(tree(), [line(1100, "1")])
    assert [(s.scope_id, s.value, s.top_sources) for s in found.scopes][1] == (20, None, ())
    assert found.by_site[1].values == ((10, None), (20, None))


def test_sums_beyond_28_digits_keep_every_digit() -> None:
    big = "9" * 30
    found = run(tree(1, second_root=False), [line(1100, big), line(1100, "1", NA)])
    assert found.scope12 == Decimal("1" + "0" * 30)


def test_no_visible_leaf_is_unconfigured() -> None:
    found = run(tree(), [line(1100, "1")], visible=set())
    assert found == unconfigured(YEAR, 2, (GA, NA))
    assert (found.configured, found.scopes, found.scope12, found.complete) == (False, (), None, True)
    assert [(s.site_id, s.values) for s in found.by_site] == [(1, ()), (2, ())]
