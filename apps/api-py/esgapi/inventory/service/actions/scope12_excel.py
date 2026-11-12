"""Scope 1·2 엑셀 내려받기 둘의 몸(밴드 S12b-1 ② — 결정 MARC-ENT-472 확정판 구조). HTTP 를 모른다. 읽기만 한다.

  template  일괄업로드 양식: 숨기지 않은 선택 잎(풀 트리 차례) × 그 잎 상세의 사업장 블록 — 값 칸 빔
  export    데이터 엑셀: 첫 시트 사업장별 Scope 합 · 연도별(리스트 그대로) · 상세 셋(행마다 칸 배출량·투입량·계수)

★ **있는 actions·selectors 만 읽는다**(새 selectors·services 0): `pool.tree_nodes`(scope=n 의 뿌리 — 감독 02 허락) ·
  `entries.list_rows`(잎 목록·3개년 값·추정) · `entries.index_detail`(잎마다 — 블록·행·잡은 판·메모·합) ·
  `entries.calc_version`·`entries.conversions` ·
  `utils.entries.custom_version`(직접입력) · `calc.entry_emission.emission`(칸 양 하나의 배출량 — G4). 총계는 저장 셈
  (RowView.emission) 그대로다 — 칸 배출량의 합과 끝자리에서 다를 수 있다.
★ 도메인을 넘는 것은 여기서만: 회사 이름(`organization.selectors.company_name`) · 켠 사업장 목록(`search_sites` +
  inventory_enabled — siteId 판정과 첫 시트의 사업장 줄. 회사 id 는 부르는 쪽이 company_of 로 정한 작업 회사).
★ 셈 계수 차례는 상세와 같다(판단 C): 직접입력 > 행 판 > 선택 판.
★ 질의는 잎마다 index_detail 한 번(N+1 — 1차 허용). 읽기를 atomic 으로 묶지 않는다(S12a 읽기 꼴 — 동시 저장 중이면
  잎끼리 다른 때의 값이 섞일 수 있다). 상세가 NotFound 인 잎(선택은 있으나 잎·판이 지워짐)은 건너뛴다.
★ Scope 는 뿌리 노드마다다(대시보드 S12a-3 와 같은 규칙 — 감독 02 D (나)): 첫 시트 열 = 숨기지 않은 선택 잎이 있는 뿌리
  (트리 차례, 머리 = 뿌리 이름), 끝 열 「Scope 1+2」 = 모든 뿌리 합(대시보드 합계와 같은 값). 쿼리 scope=n 은 풀 트리
  차례로 지우지 않은 뿌리 전부 중 n번째(이름이 아니라 차례 · 선택 잎이 없는 뿌리도 센다 — 그 뿌리에 선택 잎이 없으면
  데이터는 머리만 있는 빈 시트, 양식은 채울 줄 0 이라 NotFound · n 이 뿌리 수 밖이면 NotFound).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from esgapi.inventory.calc.entry_emission import Problem, Version, emission
from esgapi.inventory.service.actions import entries
from esgapi.inventory.service.selectors import ghg_pool as pool
from esgapi.inventory.service.utils.entries import (
    CustomView,
    IndexDetail,
    ListRow,
    RowList,
    RowView,
    ScopeGroup,
    custom_version,
    row_total,
)
from esgapi.inventory.service.utils.ghg_pool import FactorView, Invalid, NotFound
from esgapi.inventory.tools import scope12_xlsx as xlsx
from esgapi.organization.service.selectors.branches import search_sites
from esgapi.organization.service.selectors.organization import company_name

MEDIA_TYPE: Final = xlsx.MEDIA_TYPE
TEMPLATE_SCOPES: Final = ("1", "2")
EXPORT_SCOPES: Final = ("all", "1", "2")
BAD_TEMPLATE_SCOPE = "scope 는 1·2 가운데 하나다"
BAD_EXPORT_SCOPE = "scope 는 all·1·2 가운데 하나다"


@dataclass(frozen=True)
class Download:
    """내려받을 파일 하나(이름·바이트)."""

    file_name: str
    content: bytes


def _scope_of(text: str | None, allowed: tuple[str, ...], why: str) -> int | Invalid | None:
    if text is None or text == "all":
        return None if text is None or "all" in allowed else Invalid({"scope": why})
    if text not in allowed:
        return Invalid({"scope": why})
    return int(text)


def _groups(rows: RowList, scope: int | None) -> list[ScopeGroup] | NotFound:
    """리스트의 뿌리 묶음(트리 차례). scope 를 주면 풀 트리 차례로 **지우지 않은 뿌리 전부** 중 n번째 하나(선택 잎이
    없는 뿌리도 센다 — 감독 02 처분 B1). 그 뿌리에 숨기지 않은 선택 잎이 없으면 줄 0 인 빈 묶음, n 이 뿌리 수 밖이면
    NotFound."""
    if scope is None:
        return list(rows.scopes)
    roots = [node for node in pool.tree_nodes() if node.parent_id is None]
    if scope > len(roots):
        return NotFound()
    root = roots[scope - 1]
    found = next((group for group in rows.scopes if group.scope_id == root.id), None)
    empty = ScopeGroup(scope_id=root.id, scope_name=root.name, values=dict.fromkeys(rows.years), rows=())
    return [found or empty]


def _leaves(groups: Sequence[ScopeGroup]) -> list[ListRow]:
    """뿌리 차례 → 잎 차례(= 풀 트리 차례)의 잎 줄."""
    return [row for group in groups for row in group.rows]


def _details(company_id: int, year: int, leaves: Sequence[ListRow]) -> list[tuple[ListRow, IndexDetail]]:
    found: list[tuple[ListRow, IndexDetail]] = []
    for leaf in leaves:
        detail = entries.index_detail(company_id, year, leaf.node_id)
        if isinstance(detail, IndexDetail):  # NotFound(잎·판이 지워짐)는 건너뛴다
            found.append((leaf, detail))
    return found


def _enabled_sites(company_id: int) -> list[tuple[int, str]]:
    return [(site.id, site.name) for site in search_sites(company_id).branches if site.inventory_enabled]


def _listed(company_id: int, year: int) -> RowList | NotFound:
    rows = entries.list_rows(company_id, year)
    if isinstance(rows, Invalid) or not rows.configured:
        return NotFound()
    return rows


# ── 양식 ───────────────────────────────────────────────────────────


def template(company_id: int, year: int, scope: str | None, site_id: int | None) -> Download | NotFound | Invalid:
    """일괄업로드 양식. 해가 없거나 채울 줄이 0 이면 NotFound · 켠 사업장 아닌 siteId 도 NotFound · scope 밖 Invalid."""
    picked = _scope_of(scope, TEMPLATE_SCOPES, BAD_TEMPLATE_SCOPE)
    if isinstance(picked, Invalid):
        return picked
    site_name: str | None = None
    if site_id is not None:
        site_name = dict(_enabled_sites(company_id)).get(site_id)
        if site_name is None:
            return NotFound()  # 남의 회사·지운·꺼진 사업장 — 한 갈래(있나 없나를 가르지 않음)
    rows = _listed(company_id, year)
    if isinstance(rows, NotFound):
        return rows
    groups = _groups(rows, picked)
    if isinstance(groups, NotFound):
        return groups
    lines = [
        xlsx.TemplateLine(
            node_id=detail.node_id,
            path=detail.path,
            site_name=block.site_name,
            period=block.period,
            unit=detail.factor.input_unit[1],
        )
        for _, detail in _details(company_id, year, _leaves(groups))
        for block in detail.sites
        if site_id is None or block.site_id == site_id
    ]
    if not lines:
        return NotFound()
    content = xlsx.build_template(xlsx.TemplateBook(year=year, lines=lines))
    name = xlsx.template_file_name(year, company_name(company_id), site=site_name, scope=picked)
    return Download(name, content)


# ── 데이터 ─────────────────────────────────────────────────────────


def export(company_id: int, year: int, scope: str | None) -> Download | NotFound | Invalid:
    """데이터 엑셀. 해가 없거나 숨기지 않은 선택 0 이면 NotFound · 행 0 이면 머리·잎 줄만 · scope 밖 Invalid."""
    picked = _scope_of(scope, EXPORT_SCOPES, BAD_EXPORT_SCOPE)
    if isinstance(picked, Invalid):
        return picked
    rows = _listed(company_id, year)
    if isinstance(rows, NotFound):
        return rows
    groups = _groups(rows, picked)
    if isinstance(groups, NotFound):
        return groups
    details = _details(company_id, year, _leaves(groups))
    sites = _enabled_sites(company_id)
    book = xlsx.ExportBook(
        year=year,
        decimals=rows.decimals,
        roots=tuple(group.scope_name for group in groups),
        whole=picked is None,
        sites=[_summary(site_id, name, year, groups, details) for site_id, name in sites],
        yearly=[
            xlsx.YearlyLine(
                node_id=leaf.node_id,
                path=leaf.path,
                values=leaf.values,
                memo=detail.memo,
                estimated=leaf.estimated,
            )
            for leaf, detail in details
        ],
        leaves=[_leaf(detail) for _, detail in details],
    )
    return Download(xlsx.export_file_name(year, company_name(company_id), picked), xlsx.build_export(book))


def _summary(
    site_id: int,
    name: str,
    year: int,
    groups: Sequence[ScopeGroup],
    details: Sequence[tuple[ListRow, IndexDetail]],
) -> xlsx.SummarySite:
    """사업장 한 줄: 잎 상세의 Totals.by_site(그 해)를 뿌리 묶음마다 더함(리스트의 ScopeGroup — 대시보드와 같음)."""
    by_detail = {detail.node_id: detail for _, detail in details}
    values: list[Decimal | None] = []
    for group in groups:
        found = [
            line.values.get(year)
            for row in group.rows
            if row.node_id in by_detail
            for line in by_detail[row.node_id].totals.by_site
            if line.site_id == site_id
        ]
        values.append(_sum(found))
    return xlsx.SummarySite(name=name, values=tuple(values))


def _sum(values: Sequence[Decimal | None]) -> Decimal | None:
    return row_total(False, values)


def _leaf(detail: IndexDetail) -> xlsx.DetailLeaf:
    lines = [_row(block.site_name, row, detail) for block in detail.sites for row in block.rows]
    return xlsx.DetailLeaf(node_id=detail.node_id, path=detail.path, rows=lines)


def _shown(row: RowView, detail: IndexDetail) -> FactorView | CustomView:
    """행에 보일 계수: 행 덮어쓰기(직접입력·행 판), 없으면 선택의 잡은 판(판단 C)."""
    return row.factor if row.factor is not None else detail.factor


def _version(factor: FactorView | CustomView) -> Version:
    return custom_version(factor) if isinstance(factor, CustomView) else entries.calc_version(factor)


def _emission(amount: Decimal | None, unit: str, version: Version) -> Decimal | None:
    found = emission(amount, unit, version, entries.conversions())
    return None if isinstance(found, Problem) else found


def _row(site_name: str, row: RowView, detail: IndexDetail) -> xlsx.DetailRow:
    factor = _shown(row, detail)
    version = _version(factor)
    amounts = {value.slot: value.amount for value in row.values}
    cells: dict[str, xlsx.SheetCells] = {}
    for period in xlsx.PERIODS:
        folded = xlsx.fold(amounts, period)
        if period == "year":  # 「상세 데이터(년도)」 Y 칸 = 저장 셈(감독 C0 F)
            emissions: tuple[Decimal | None, ...] = (row.emission,)
        else:
            emissions = tuple(_emission(amount, row.unit, version) for amount in folded)
        cells[period] = xlsx.SheetCells(emissions=emissions, amounts=folded)
    gases = {gas.gas: gas for gas in factor.gases}
    return xlsx.DetailRow(
        site_name=site_name,
        detail_name=row.detail_name,
        unit=row.unit,
        na=row.na,
        problem=row.emission_problem,
        total=row.emission,
        amount_total=row_total(row.na, amounts.values()),
        cells=cells,
        ncv=factor.ncv,
        ncv_unit=factor.ncv_unit[1] if factor.ncv_unit is not None else None,
        gases=tuple(
            xlsx.GasCell(gases[name].factor, gases[name].gwp)
            if name in gases and gases[name].enabled
            else xlsx.GasCell(None, None)
            for name in xlsx.GASES
        ),
        source=factor.source,
    )
