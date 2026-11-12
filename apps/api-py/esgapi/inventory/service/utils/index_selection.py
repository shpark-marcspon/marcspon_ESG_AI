"""고객사 인덱스 선택(S17)의 순수 도움말(django 0 — .importlinter 다). 밴드 K1b-2b(결정 MARC-ENT-469 3·4).

  DEFAULT_DECIMALS   해의 소수점 자릿수 기본값 — 한 곳(스펙-1 97행 [우리 해석], MARC-ENT-462 답이 오면 여기만)
  year_problem       고를 수 있는 해: 1990 ≤ 해 ≤ 올해. 올해는 부르는 쪽이 Asia/Seoul 로 정해 넘긴다
  rollup             트리 셈: 위 단 availableCount = 아래 잎 합(표시), 위 단 selected = 아래 고를 수 있는 잎(기본 계수
                     있음 — 시설 수는 보지 않는다, S12-05)이 다 골라짐
  facility_counts    코드별 시설 수(사업장의 자산/시설 목록에서 — 인벤토리 켠 사업장만은 부르는 쪽이 고른다)

연도 범위·자릿수는 표시·검사 값이다(배출계수 같은 수치가 아니다 — 출처 칸 없음).
"""

from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

from esgapi.inventory.service.utils.ghg_pool import NodeView

DEFAULT_DECIMALS: Final = 2
DECIMALS_RANGE: Final = (0, 3)
YEAR_FIRST: Final = 1990
YEAR_LAST: Final = 2100  # DB CHECK(inventory_years_year_range)의 위 끝 — 검사의 위 끝은 올해
MAX_SELECTIONS: Final = 1000
LEAF: Final = "facility"


def year_problem(year: int, today: date) -> str | None:
    """고를 수 없는 해면 까닭 글자, 고를 수 있으면 None."""
    if year < YEAR_FIRST:
        return f"{YEAR_FIRST}년부터 고를 수 있다"
    if year > today.year:
        return "올해보다 뒤의 해는 고를 수 없다"
    return None


@dataclass(frozen=True)
class TreeNode:
    """트리 한 줄. has_factor·has_data 는 잎만 값이 있다(위 단은 None)."""

    id: int
    level: str
    name: str
    parent_id: int | None
    facility_code_id: int | None
    available_count: int
    selected: bool
    has_factor: bool | None = None
    has_data: bool | None = None


@dataclass(frozen=True)
class Chosen:
    """그 해의 삭제 안 된 선택 한 줄(잎 id 로 찾는다)."""

    id: int
    factor_version_id: int
    hidden: bool


@dataclass(frozen=True)
class IndexTree:
    """GET 트리의 답: 해와 줄 전부(페이지 없음)."""

    year: int
    nodes: list[TreeNode]


@dataclass(frozen=True)
class SaveResult:
    """저장 뒤 숨기지 않은 선택 수 · 뺐지만 데이터가 있어 숨긴 수."""

    selected: int
    hidden_with_data: int


def facility_counts(codes: Iterable[int]) -> dict[int, int]:
    """시설의 코드 id 목록 → 코드 id 별 수."""
    return dict(Counter(codes))


def leaf_counts(nodes: Sequence[NodeView], by_code: Mapping[int, int]) -> dict[int, int]:
    """잎 id → 그 잎의 코드를 가진 이 회사 시설 수(없으면 0). 같은 코드의 잎이 여럿이면 저마다 같은 수다."""
    return {
        node.id: by_code.get(node.facility_code_id, 0)
        for node in nodes
        if node.level == LEAF and node.facility_code_id is not None
    }


def selectable(has_factor: bool) -> bool:
    """고를 수 있는 잎: 기본 계수가 있다. 이 회사에 그 코드의 시설이 없어도 고른다(S12-05, MARC-ENT-644 — 감독 판단 5 의
    시설 조건을 걷음. availableCount 는 표시로만 남는다)."""
    return has_factor


def rollup(
    nodes: Sequence[NodeView],
    leaf_counts: Mapping[int, int],
    selected: Collection[int],
    *,
    with_factor: Collection[int] = frozenset(),
    with_data: Collection[int] = frozenset(),
) -> list[TreeNode]:
    """nodes 차례 그대로 트리 줄을 짓는다. leaf_counts 는 잎 id → 이 회사 시설 수(없으면 0).
    selected 는 숨기지 않은 선택의 잎 id. 위 단은 아래 잎에서 셈한다(부모가 목록에 없는 줄은 뿌리로 본다)."""
    children: dict[int, list[int]] = {}
    for node in nodes:
        if node.parent_id is not None:
            children.setdefault(node.parent_id, []).append(node.id)
    by_id = {node.id: node for node in nodes}
    chosen = frozenset(selected)
    factored = frozenset(with_factor)
    data = frozenset(with_data)
    memo: dict[int, tuple[int, int, int]] = {}  # id → (시설 수 합, 고를 수 있는 잎 수, 그중 골라진 수)

    def tally(node_id: int) -> tuple[int, int, int]:
        if node_id in memo:
            return memo[node_id]
        node = by_id[node_id]
        if node.level == LEAF:
            count = leaf_counts.get(node_id, 0)
            can = selectable(node_id in factored)
            result = (count, int(can), int(can and node_id in chosen))
        else:
            total = can_total = chosen_total = 0
            for child in children.get(node_id, ()):
                count, can, picked = tally(child)
                total, can_total, chosen_total = total + count, can_total + can, chosen_total + picked
            result = (total, can_total, chosen_total)
        memo[node_id] = result
        return result

    lines: list[TreeNode] = []
    for node in nodes:
        count, can, picked = tally(node.id)
        if node.level == LEAF:
            lines.append(
                TreeNode(
                    id=node.id,
                    level=node.level,
                    name=node.name,
                    parent_id=node.parent_id,
                    facility_code_id=node.facility_code_id,
                    available_count=count,
                    selected=node.id in chosen,
                    has_factor=node.id in factored,
                    has_data=node.id in data,
                )
            )
        else:
            lines.append(
                TreeNode(
                    id=node.id,
                    level=node.level,
                    name=node.name,
                    parent_id=node.parent_id,
                    facility_code_id=None,
                    available_count=count,
                    selected=can > 0 and picked == can,
                )
            )
    return lines
