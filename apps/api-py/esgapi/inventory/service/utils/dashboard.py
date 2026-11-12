"""Scope 1·2 대시보드(S1)의 셈 — 순수(django 0). 밴드 S12a-3 ①(결정 MARC-ENT-469 1·7, 스펙 S1).

재료는 리스트(actions/entries.py 의 list_rows)와 같다: 숨기지 않은 선택 잎 · paths_of(pool.tree_nodes()) · 켠 사업장 ·
year_rows 의 그 해 줄. 그래서 뿌리(Scope) 합은 리스트의 그 해 `scopes[].values[Y]` 와 같은 값이다.

  scopes      뿌리 노드마다(리스트와 같은 묶음·차례 — 숨기지 않은 선택 잎이 있는 뿌리만) 합과 배출원 상위 5.
              scope_order = 그 뿌리가 풀 뿌리 전체(nodes 의 parent 없는 노드, 트리 차례) 가운데 몇째(1부터 —
              숨김·선택과 무관, DB1 검증 B1: 화면이 Scope 1·2 자리를 목록 차례가 아니라 이것으로 잡는다)
  top_sources 뿌리마다 path[1](2단 — 배출원 유형)로 묶은 합, 큰 차례 5개. 같은 값은 트리 차례. 값 None 인 묶음은 빠지고
              0 은 든다. share = 그 뿌리 합 대비 퍼센트, 소수 첫째 자리 ROUND_HALF_UP(분모 0·None 이면 None — Q7)
  by_site     켠 사업장 전부(받은 차례)마다 뿌리별 그 사업장 합(값 없는 뿌리도 None 으로 줄을 냄 — Q6)
  complete    셈에 든 줄 가운데 emission_problem 이 있는 줄이 없음(빈 행·N/A 는 문제 아님)

합은 sum_or_none(prec 60) 그대로다. 반올림은 share 하나뿐이다.
"""

from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Final

from esgapi.inventory.service.utils.entries import sum_or_none
from esgapi.inventory.service.utils.ghg_pool import NodeView

TOP_SOURCES: Final = 5
SOURCE_DEPTH: Final = 1  # path 의 자리: 0 뿌리(Scope) · 1 배출원 유형(2단 — 상위 5 의 묶음 단, [우리 해석] 스펙 S1)
_SHARE_STEP: Final = Decimal("0.1")
_PRECISION: Final = 60  # sum_or_none 과 같은 정밀도(470 M3 — 28자리 넘는 합)


@dataclass(frozen=True)
class Line:
    """셈 재료 한 줄: 그 해 한 행의 잎·사업장·배출량·셈 문제."""

    node_id: int
    site_id: int
    emission: Decimal | None
    problem: str | None


@dataclass(frozen=True)
class EnabledSite:
    id: int
    name: str


@dataclass(frozen=True)
class Source:
    node_id: int
    name: str
    value: Decimal
    share: Decimal | None


@dataclass(frozen=True)
class ScopeTotal:
    scope_id: int
    scope_name: str
    value: Decimal | None
    top_sources: tuple[Source, ...]
    scope_order: int  # 풀 뿌리 전체 가운데 몇째(1부터, 트리 차례 — 숨김·선택과 무관)


@dataclass(frozen=True)
class SiteTotal:
    site_id: int
    site_name: str
    values: tuple[tuple[int, Decimal | None], ...]  # (뿌리 id, 그 사업장 합) — scopes 차례


@dataclass(frozen=True)
class Dashboard:
    year: int
    configured: bool
    decimals: int
    complete: bool
    scopes: tuple[ScopeTotal, ...]
    scope12: Decimal | None
    by_site: tuple[SiteTotal, ...]


def share(value: Decimal, whole: Decimal | None) -> Decimal | None:
    """value 가 whole 의 몇 퍼센트인지, 소수 첫째 자리 ROUND_HALF_UP. whole 이 0·None 이면 None."""
    if whole is None or whole == 0:
        return None
    with localcontext(prec=_PRECISION):
        return (value * 100 / whole).quantize(_SHARE_STEP, rounding=ROUND_HALF_UP)


def unconfigured(year: int, decimals: int, sites: Sequence[EnabledSite]) -> Dashboard:
    """설정 안 된 해(해 행 없음·숨기지 않은 선택 0) — 뿌리 0 · 합 None · 켠 사업장은 줄만 · complete 참."""
    return Dashboard(
        year=year,
        configured=False,
        decimals=decimals,
        complete=True,
        scopes=(),
        scope12=None,
        by_site=tuple(SiteTotal(site.id, site.name, ()) for site in sites),
    )


def dashboard(
    *,
    year: int,
    decimals: int,
    visible: Collection[int],
    nodes: Sequence[NodeView],
    paths: Mapping[int, tuple[NodeView, ...]],
    sites: Sequence[EnabledSite],
    lines: Iterable[Line],
) -> Dashboard:
    """그 해의 대시보드. visible = 숨기지 않은 선택 잎 id · nodes = 트리 차례(pool.tree_nodes())
    · paths = paths_of(nodes) · sites = 켠 사업장(차례대로) · lines = 그 해 줄(year_rows — 회사·숨김·삭제 거름)."""
    if not visible:
        return unconfigured(year, decimals, sites)
    order = {node.id: index for index, node in enumerate(nodes)}
    root_rank = {node.id: rank for rank, node in enumerate((n for n in nodes if n.parent_id is None), start=1)}
    site_ids = {site.id for site in sites}
    roots: dict[int, NodeView] = {}
    for node_id in visible:
        path = paths.get(node_id)
        if path:
            roots[path[0].id] = path[0]
    counted = [
        (paths[line.node_id], line)
        for line in lines
        if line.site_id in site_ids and line.node_id in visible and paths.get(line.node_id)
    ]
    by_root: dict[int, list[Decimal | None]] = defaultdict(list)
    by_source: dict[int, dict[int, list[Decimal | None]]] = defaultdict(lambda: defaultdict(list))
    by_root_site: dict[tuple[int, int], list[Decimal | None]] = defaultdict(list)
    for path, line in counted:
        root = path[0].id
        by_root[root].append(line.emission)
        by_root_site[(root, line.site_id)].append(line.emission)
        if len(path) > SOURCE_DEPTH:
            by_source[root][path[SOURCE_DEPTH].id].append(line.emission)
    names = {node.id: node.name for path, _ in counted for node in path}
    ordered = sorted(roots, key=lambda root: order.get(root, 0))
    scopes: list[ScopeTotal] = []
    for root in ordered:
        value = sum_or_none(by_root.get(root, ()))
        sums = [(source, sum_or_none(found)) for source, found in by_source.get(root, {}).items()]
        valued = [(source, total) for source, total in sums if total is not None]
        # 트리 차례로 놓은 뒤 값 큰 차례로 안정 정렬 — 같은 값은 트리 차례(값을 뒤집지 않는다: prec 28 반올림 0)
        valued.sort(key=lambda item: order.get(item[0], 0))
        valued.sort(key=lambda item: item[1], reverse=True)
        top = tuple(
            Source(node_id=source, name=names[source], value=total, share=share(total, value))
            for source, total in valued[:TOP_SOURCES]
        )
        scopes.append(
            ScopeTotal(
                scope_id=root,
                scope_name=roots[root].name,
                value=value,
                top_sources=top,
                scope_order=root_rank.get(root, 0),
            )
        )
    by_site = tuple(
        SiteTotal(
            site_id=site.id,
            site_name=site.name,
            values=tuple((root, sum_or_none(by_root_site.get((root, site.id), ()))) for root in ordered),
        )
        for site in sites
    )
    return Dashboard(
        year=year,
        configured=True,
        decimals=decimals,
        complete=all(line.problem is None for _, line in counted),
        scopes=tuple(scopes),
        scope12=sum_or_none(scope.value for scope in scopes),
        by_site=by_site,
    )
