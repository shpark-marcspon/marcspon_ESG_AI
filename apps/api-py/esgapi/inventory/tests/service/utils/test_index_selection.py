"""고객사 인덱스 선택의 순수 도움말(밴드 K1b-2b ① — service/utils/index_selection.py). DB 0.

나무는 지어낸 것이다(범위 하나 → 유형 하나 → 활동 둘 → 잎 넷).
"""

import ast
from datetime import date
from pathlib import Path

import pytest

from esgapi.inventory.service.utils import index_selection
from esgapi.inventory.service.utils.ghg_pool import NodeView
from esgapi.inventory.service.utils.index_selection import (
    DEFAULT_DECIMALS,
    TreeNode,
    rollup,
    selectable,
    year_problem,
)

TODAY = date(2026, 10, 29)


@pytest.mark.parametrize(("year", "ok"), [(1989, False), (1990, True), (2026, True), (2027, False)])
def test_a_year_can_be_chosen_from_1990_to_this_year(year: int, ok: bool) -> None:
    assert (year_problem(year, TODAY) is None) is ok


def test_this_year_follows_the_given_day() -> None:
    assert year_problem(2027, date(2027, 1, 1)) is None  # 짝: 올해는 부르는 쪽이 넘긴 날의 해
    assert year_problem(2027, date(2026, 12, 31)) is not None


def view(node_id: int, level: str, parent_id: int | None, code: int | None = None) -> NodeView:
    return NodeView(
        id=node_id,
        level=level,
        name="" if level == "facility" else f"노드 {node_id}",
        parent_id=parent_id,
        sort_order=node_id,
        child_count=0,
        facility_code_id=code,
    )


NODES = [
    view(1, "scope", None),
    view(2, "source_type", 1),
    view(3, "activity", 2),
    view(4, "activity", 2),
    view(11, "facility", 3, code=101),
    view(12, "facility", 3, code=102),
    view(13, "facility", 4, code=103),
    view(14, "facility", 4, code=104),
]


def by_id(lines: list[TreeNode]) -> dict[int, TreeNode]:
    return {line.id: line for line in lines}


def test_rollup_keeps_the_order_and_sums_the_counts_upward() -> None:
    lines = rollup(NODES, {11: 2, 12: 1, 13: 0, 14: 4}, selected=set(), with_factor={11, 12, 13, 14})
    assert [line.id for line in lines] == [1, 2, 3, 4, 11, 12, 13, 14]
    counts = {line.id: line.available_count for line in lines}
    assert counts == {1: 7, 2: 7, 3: 3, 4: 4, 11: 2, 12: 1, 13: 0, 14: 4}


def test_only_leaves_carry_the_leaf_fields() -> None:
    lines = by_id(rollup(NODES, {11: 1}, selected={11}, with_factor={11}, with_data={11}))
    assert (lines[11].has_factor, lines[11].has_data, lines[11].facility_code_id) == (True, True, 101)
    assert (lines[12].has_factor, lines[12].has_data) == (False, False)
    assert (lines[3].has_factor, lines[3].has_data, lines[3].facility_code_id) == (None, None, None)


def test_an_upper_node_is_selected_when_every_selectable_leaf_below_is() -> None:
    # 고를 수 있는 잎 = 기본 계수 있음: 11·13·14. 12 는 계수 없음 — 셈 밖. 13 은 시설 0 이어도 셈 안(S12-05).
    counts, factored = {11: 1, 12: 1, 13: 0, 14: 1}, {11, 13, 14}
    some = by_id(rollup(NODES, counts, selected={11, 14}, with_factor=factored))
    assert (some[3].selected, some[4].selected, some[2].selected, some[1].selected) == (True, False, False, False)
    every = by_id(rollup(NODES, counts, selected={11, 13, 14}, with_factor=factored))
    assert (every[3].selected, every[4].selected, every[2].selected, every[1].selected) == (True, True, True, True)


def test_an_upper_node_without_a_selectable_leaf_is_not_selected() -> None:
    lines = by_id(rollup(NODES, {11: 1}, selected={11, 12, 13, 14}, with_factor=set()))
    assert [lines[n].selected for n in (1, 2, 3, 4)] == [False] * 4  # 기본 계수 0 — 고를 수 있는 잎 0
    assert [lines[n].selected for n in (11, 12, 13, 14)] == [True] * 4  # 잎은 고른 그대로 보인다


def test_selectable_needs_only_a_factor() -> None:
    """S12-05(MARC-ENT-644): 시설 수는 보지 않는다 — 시설 0 잎도 기본 계수가 있으면 고른다."""
    assert [selectable(True), selectable(False)] == [True, False]


def test_a_leaf_without_facilities_counts_toward_its_upper_node() -> None:
    """S12-05: 시설 0 잎(13)이 골라지지 않으면 위 단(4)은 골라짐이 아니다 — availableCount 는 표시로 그대로."""
    counts, factored = {11: 1, 12: 1, 13: 0, 14: 1}, {11, 12, 13, 14}
    lines = by_id(rollup(NODES, counts, selected={14}, with_factor=factored))
    assert (lines[4].selected, lines[4].available_count, lines[13].available_count) == (False, 1, 0)


def test_the_default_decimals_live_in_one_place() -> None:
    """DEFAULT_DECIMALS 의 값 2 는 utils 한 곳에만 있다 — 모델은 이름으로 들인다(MARC-ENT-462 답이 오면 여기만)."""
    assert DEFAULT_DECIMALS == 2
    models = Path(index_selection.__file__).parents[2] / "models.py"
    names = {node.id for node in ast.walk(ast.parse(models.read_text())) if isinstance(node, ast.Name)}
    assert "DEFAULT_DECIMALS" in names
