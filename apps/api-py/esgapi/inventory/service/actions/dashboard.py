"""Scope 1·2 대시보드(S1)의 조립. 밴드 S12a-3 ①(결정 MARC-ENT-469 1·7). HTTP 를 모른다. 쓰지 않는다.

★ 회사 id 는 부르는 쪽이 정한 것이다(고객사 사용자는 주체의 회사, 운영 관리자는 company_of 의 작업 회사).
★ 재료는 리스트(actions/entries.py 의 list_rows)와 같다 — 해 행·숨기지 않은 선택(selections_of)·paths_of·켠 사업장·
  year_rows. 켠 사업장 거름은 list_rows 의 _enabled_sites 와 같은 한 줄이다(남의 모듈의 `_` 함수를 들이지 않는다).
★ 도메인을 넘는 것(조직구조의 사업장)은 여기서만 부른다(services·selectors 는 남의 도메인 import 0 — .importlinter 바).
★ S3K2a ②: board 가 Scope 1·2(scope12_dashboard — 셈 0줄)에 Scope 3 칸을 붙인다. Scope 3 은 연도 상태
  (actions/scope3_state.year_values)와 같은 재료(카테고리마다 지금 결과 — 잠겼으면 핀, S3K2b-1: 제외 뺌)로
  **Scope 1·2 설정(configured)과 따로 늘 셈**한다(설정 안 된 해·unconfigured 길도). 합 = Scope 1·2 합 + Scope 3 합
  (None 은 빼고, 둘 다 None 이면 None) · 상위 5 의 share 는 Scope 3 합 대비(S12a-3 Q7). 해 범위 밖(1990~2100)이면
  Scope 3 은 없음(None·빈 목록).
★ DB1(599 e6): scope3_failed_sheets = 같은 지금 결과 값들의 failed 시트 수 합(연도 상태 failedSheets 와 같은 셈 —
  결과 없으면 0).
"""

from dataclasses import dataclass
from decimal import Decimal

from esgapi.inventory.service.actions import scope3_state
from esgapi.inventory.service.selectors import entries as selectors
from esgapi.inventory.service.selectors import ghg_pool as pool
from esgapi.inventory.service.selectors import index_selection as selections
from esgapi.inventory.service.utils.dashboard import Dashboard, EnabledSite, Line, dashboard, unconfigured
from esgapi.inventory.service.utils.entries import paths_of, sum_or_none
from esgapi.inventory.service.utils.ghg_pool import Invalid
from esgapi.inventory.service.utils.index_selection import DEFAULT_DECIMALS
from esgapi.inventory.service.utils.scope3_state import Ranked, Value, scope3_total, top_categories
from esgapi.organization.service.selectors.branches import search_sites


def scope12_dashboard(company_id: int, year: int) -> Dashboard:
    """그 회사 그 해의 Scope 1·2 합(뿌리별)·합계·사업장별·배출원 상위 5. 설정 안 된 해는 configured false."""
    sites = [
        EnabledSite(id=branch.id, name=branch.name)
        for branch in search_sites(company_id).branches
        if branch.inventory_enabled
    ]
    year_id = selections.year_of(company_id, year)
    if year_id is None:
        return unconfigured(year, DEFAULT_DECIMALS, sites)
    decimals = selectors.decimals_of(company_id, year_id)
    chosen = selections.selections_of(company_id, year_id)
    visible = {node_id for node_id, row in chosen.items() if not row.hidden}
    if not visible:
        return unconfigured(year, decimals, sites)
    nodes = pool.tree_nodes()
    return dashboard(
        year=year,
        decimals=decimals,
        visible=visible,
        nodes=nodes,
        paths=paths_of(nodes),
        sites=sites,
        lines=[
            Line(node_id=line.node_id, site_id=line.site_id, emission=line.emission, problem=line.problem)
            for line in selectors.year_rows(company_id, [year])
        ],
    )


@dataclass(frozen=True)
class Board:
    """대시보드 한 판: Scope 1·2(그대로) · Scope 3 합 · 1·2·3 합 · Scope 3 카테고리 상위 5."""

    scope12: Dashboard
    scope3: Decimal | None
    total: Decimal | None
    categories: tuple[Ranked, ...]
    scope3_failed_sheets: int  # 카테고리 지금 결과들의 failed 시트 수 합(연도 상태 failedSheets 의 합 — DB1, 599 e6)


def _scope3_values(company_id: int, year: int) -> dict[str, Value | None]:
    """카테고리 → 지금 결과 값(연도 상태와 같은 재료 — 제외 뺌, 이름 조회 0). 해 범위 밖이면 빈 dict."""
    found = scope3_state.year_values(company_id, year)
    return {} if isinstance(found, Invalid) else found


def board(company_id: int, year: int) -> Board:
    """그 회사 그 해의 대시보드(S1) — Scope 1·2 는 scope12_dashboard 그대로, Scope 3 은 configured 와 따로."""
    found = scope12_dashboard(company_id, year)
    lines = _scope3_values(company_id, year)
    values = {category: None if line is None else line.total for category, line in lines.items()}
    scope3 = scope3_total(values.values())
    total = sum_or_none([found.scope12, scope3])
    failed = sum(line.failed_sheets for line in lines.values() if line is not None)
    return Board(
        scope12=found,
        scope3=scope3,
        total=total,
        categories=top_categories(values, scope3),
        scope3_failed_sheets=failed,
    )
