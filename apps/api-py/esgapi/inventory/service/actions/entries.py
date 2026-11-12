"""Scope 1·2 입력(S2 리스트·S3 상세·S12 히스토리)의 유스케이스. 밴드 S12a ②(결정 MARC-ENT-463·469). HTTP 를 모른다.

  index_detail   ⓐ 상세: 켠 사업장마다 그 잎 코드의 자산/시설·입력 행·값 · 잡은 판 · Y-2·Y-1·Y 합 · 단위 목록 ·
                 자릿수 · 메모 · 잠금
  save_rows      ⓑ 한 사업장의 행 저장(판정 → 쓰기 → 셈). 응답은 ⓐ
  delete_rows    ⓒ 행 삭제 표시(값·히스토리 그대로)
  set_memo       ⓓ 인덱스 메모        lock_index ⓔ 잠그기      unlock_index ⓕ 풀기(운영 관리자만 — 첫 문장)
  set_decimals   ⓖ 해의 표시 자릿수(저장값 그대로)
  years          ⓗ 해 목록           list_rows ⓘ 리스트(뿌리 노드마다)   row_history ⓙ 행 히스토리(쪽)
  set_period     ⓚ 사업장 블록의 입력주기(S7 — S12a-2). 옛 주기 칸 값은 지우지 않고 숨긴다(판단 E)
  set_row_factor ⓛ 행 하나의 계수 바꿈(S9·S11 — 운영 관리자만, 첫 문장). 풀 계수의 지금 판 또는 직접입력
  restore        ⓜ 히스토리 줄의 뒤(after) 상태로 되돌리는 새 줄(S12 — 판단 D). 계수 줄은 운영 관리자만

★ 회사 id 는 부르는 쪽이 정한 것이다(고객사 사용자는 주체의 회사, 운영 관리자는 company_of 의 작업 회사).
★ **판 id 는 그 회사 선택 행에서만 얻는다**(pinned_version(선택.factor_version_id) — 요청에 판 칸 0, 418 노트 L3).
  풀의 계수를 고쳐 새 판이 서도 잡은 판은 그대로다(새로 잡기는 MARC-ISSUE-450).
★ 도메인을 넘는 것(조직구조의 사업장·자산/시설·사업장 잠금 · 사용자 이름)은 여기서만 부른다(services·selectors 는
  남의 도메인 import 0 — .importlinter 바). 꺼진 사업장의 행은 상세·리스트·합에서 빠진다(행은 남음 — 판단 9).
★ 셈 계수는 직접입력 > 행 판 > 선택 판 차례다(판단 C). 행 판은 풀 계수의 지금 판을 그 자리에서 잡는다 — 판 id 는
  요청에서 받지 않는다(계수 id 를 받아 current_version_id 로). 선택이 잡은 계수를 고르면 행 덮어쓰기는 None.
★ 행 값은 블록 입력주기의 칸만 셈·상세에 든다(옛 주기 칸 값은 DB 에 남는다 — 되바꾸면 다시 보인다).
★ 잠금 차례: 입력 저장·주기 = 해(lock_year) → 선택(lock_selection) → 사업장(lock_branch) → 행(lock_rows). 계수가
  닿는 계수 바꿈·복구는 해 → 잎(pool.lock_nodes — 풀 계수 지우기가 잎을 먼저 잠그므로 줄 섬) → 선택 → 사업장 → 행.
  지움·메모·잠그기·풀기(ⓒ~ⓕ)는 lock_selection 만 — 잠김 판정은 그 잠금 아래에서 한다. 조직구조의 사업장 지움은
  사업장만 잠그고 입력 행은 읽기만 한다(고리 0 — 발주서 2-7).
★ 쓰기는 `@transaction.atomic` 하나: 판정을 쓰기 전에 다 한다(하나라도 걸리면 0 씀). services 는 모듈 이름으로 부른다.
"""

from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from functools import cache
from typing import Any, Final

from django.db import transaction

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import is_allowed
from esgapi.inventory.calc.entry_emission import Gas, Problem, Version, emission
from esgapi.inventory.data_loader import read_data
from esgapi.inventory.service.selectors import entries as selectors
from esgapi.inventory.service.selectors import ghg_pool as pool
from esgapi.inventory.service.selectors import index_selection as selections
from esgapi.inventory.service.services import entries as services
from esgapi.inventory.service.services import index_selection as year_services
from esgapi.inventory.service.utils.entries import (
    DEFAULT_PERIOD,
    MAX_ROWS_PER_SAVE,
    MEMO_MAX,
    PERIODS,
    REASON_MAX,
    RESTORE_KIND,
    RESTORE_LOCKED,
    RESTORE_STALE,
    RESTORE_TOP,
    Actor,
    CustomView,
    FacilityLine,
    FactorRef,
    HistoryLine,
    HistoryPage,
    IndexDetail,
    ListRow,
    Locked,
    RestoreStale,
    RowInput,
    RowList,
    RowView,
    ScopeGroup,
    SiteBlock,
    SiteTotals,
    SlotValue,
    Totals,
    YearLine,
    amount_problem,
    conversions_of,
    custom_unit_problem,
    custom_version,
    decimal_text,
    list_years,
    paths_of,
    pool_unit_problem,
    reason_text,
    restore_problem,
    row_total,
    slots,
    sum_or_none,
    unit_options,
)
from esgapi.inventory.service.utils.ghg_pool import (
    DEFAULT_EMISSION_UNIT,
    FactorDraft,
    FactorValues,
    FactorView,
    Forbidden,
    Invalid,
    NotFound,
    check_factor,
    parse_decimal,
)
from esgapi.inventory.service.utils.index_selection import DECIMALS_RANGE, DEFAULT_DECIMALS
from esgapi.organization.service.selectors.branches import facilities_of, lock_branch, search_sites
from esgapi.organization.service.utils.entities import Branch
from esgapi.user.service.selectors.user import names_of

UNLOCK: Final = "inventory_scope12_unlock"
ROW_FACTOR: Final = "inventory_scope12_row_factor_save"  # 계수 바꿈 · 계수 줄 복구(운영 관리자만)
Q_MAX: Final = 100
TOO_MANY = f"한 번에 {MAX_ROWS_PER_SAVE}행까지 저장한다"
NOT_HERE = "이 사업장의 이 인덱스 자산/시설이 아니다"
HAS_ROW = "이 자산/시설에는 이미 행이 있다 — rowId 로 고친다"
TWICE = "같은 자산/시설을 두 번 보냈다"
NO_ROW = "이 사업장·인덱스의 행이 아니다"
BAD_UNIT = "고를 수 없는 단위다"
BAD_SLOT = "그 블록 입력주기의 칸이 아니다"
SLOT_TWICE = "같은 칸을 두 번 보냈다"
RACE = "행이 동시에 바뀌었다 — 다시 불러 저장한다"
MEMO_TOO_LONG = f"메모는 {MEMO_MAX}자까지다"
BAD_DECIMALS = f"소수점 자릿수는 {DECIMALS_RANGE[0]}~{DECIMALS_RANGE[1]}이다"
Q_TOO_LONG = f"검색어는 {Q_MAX}자까지다"
BAD_PERIOD = "입력주기는 month·quarter·year 가운데 하나다"
NEED_REASON = f"사유는 1~{REASON_MAX}자다"
REASON_TOO_LONG = f"사유는 {REASON_MAX}자까지다"
ONE_FACTOR = "factorId 와 custom 가운데 하나만 보낸다"
# 웹이 창 줄에 그대로 보인다(sid:MARC-ISSUE-558)
BAD_FACTOR = "이 시설에 없거나 삭제된 배출계수예요. 다른 배출계수를 골라 주세요"
BAD_EMISSION_UNIT = "직접입력 계수의 배출량 기준단위는 tCO2-eq 다"
NOT_RESTORABLE = "값·주기·계수 줄만 복구한다"
TOP_LINE = "맨 위 줄은 지금 상태다 — 복구하지 않는다"


@cache
def conversions() -> Mapping[tuple[str, str], Decimal]:
    """환산표(inventory/data/unit-conversions.json — 쌍 그대로)."""
    rows: Any = read_data("unit-conversions.json")["unitConversions"]
    return conversions_of(rows)


def calc_version(view: FactorView) -> Version:
    """잡은 판 → 셈 칸(켠 가스만 — 값이 빈 가스는 켜졌어도 셈에 0)."""
    return Version(
        input_unit=view.input_unit[1],
        ncv=view.ncv,
        ncv_unit=view.ncv_unit[1] if view.ncv_unit is not None else None,
        factor_unit=view.factor_unit,
        gases=tuple(
            Gas(factor=gas.factor, gwp=gas.gwp)
            for gas in view.gases
            if gas.enabled and gas.factor is not None and gas.gwp is not None
        ),
    )


RowFactor = FactorView | CustomView | None  # 행의 계수 덮어쓰기(None = 선택의 잡은 판)


def _row_factors(company_id: int, rows: Sequence[selectors.RowState]) -> dict[int, RowFactor]:
    """행 id → 덮어쓴 계수(직접입력 보기 또는 판 보기 — 판단 C). 덮어쓰지 않은 행은 None."""
    customs = selectors.custom_of(company_id, {row.custom_factor_id for row in rows if row.custom_factor_id})
    views: dict[int, FactorView] = {}
    for version_id in {row.factor_version_id for row in rows if row.factor_version_id is not None}:
        view = pool.pinned_version(version_id)
        if not isinstance(view, NotFound):
            views[version_id] = view
    found: dict[int, RowFactor] = {}
    for row in rows:
        if row.custom_factor_id is not None:
            found[row.id] = customs.get(row.custom_factor_id)
        elif row.factor_version_id is not None:
            found[row.id] = views.get(row.factor_version_id)
        else:
            found[row.id] = None
    return found


def _version_of(factor: RowFactor, pinned: FactorView) -> Version:
    """셈 계수 차례: 직접입력 > 행 판 > 선택 판(판단 C)."""
    if isinstance(factor, CustomView):
        return custom_version(factor)
    return calc_version(factor if factor is not None else pinned)


def _period_amounts(values: Mapping[str, Decimal | None], allowed: frozenset[str]) -> list[Decimal | None]:
    """블록 주기의 칸 값만(옛 주기 칸은 셈에서 빠진다 — 판단 E)."""
    return [amount for slot, amount in values.items() if slot in allowed]


def _figures(total: Decimal | None, unit: str, version: Version) -> tuple[Decimal | None, str | None]:
    found = emission(total, unit, version, conversions())
    if isinstance(found, Problem):
        return None, found.code
    return found, None


def _enabled_sites(company_id: int) -> list[Branch]:
    return [branch for branch in search_sites(company_id).branches if branch.inventory_enabled]


def _year_and_selection(
    company_id: int, year: int, node_id: int, *, lock: bool
) -> tuple[int, selections.SelectionState] | NotFound:
    """그 해·잎의 숨기지 않은 선택(lock 이면 잠가서). 해·선택이 없거나 숨김이면 NotFound."""
    year_id = selections.year_of(company_id, year)
    if year_id is None:
        return NotFound()
    found = (
        selections.lock_selection(company_id, year_id, node_id)
        if lock
        else selections.selection_of(company_id, year_id, node_id)
    )
    if found is None or found.hidden:
        return NotFound()
    return year_id, found


# ── ⓐ 상세 ────────────────────────────────────────────────────────


def _locked_by(company_id: int, user_id: int | None) -> tuple[int, str] | None:
    if user_id is None:
        return None
    # 잠근 사람의 kind 는 적지 않는다: 같은 id 를 두 갈래에 넘기면 고객사 쪽은 이 회사 고객사 사용자만, 운영 관리자
    # 쪽은 운영 관리자 입구만 풀어서 맞는 하나만 남는다(users.pk 는 두 kind 에 걸쳐 하나뿐).
    names = names_of(company_id, {user_id}, {user_id})
    return (user_id, names[user_id][1]) if user_id in names else (user_id, "")


def _totals(company_id: int, year: int, node_id: int, sites: Sequence[Branch]) -> Totals:
    years = list_years(year)
    site_ids = {site.id for site in sites}
    by: dict[tuple[int, int], list[Decimal | None]] = defaultdict(list)
    for line in selectors.year_rows(company_id, years, node_id=node_id):
        if line.site_id in site_ids:
            by[(line.site_id, line.year)].append(line.emission)
    by_site = tuple(
        SiteTotals(site.id, site.name, {y: sum_or_none(by.get((site.id, y), ())) for y in years}) for site in sites
    )
    all_years = {y: sum_or_none(total.values[y] for total in by_site) for y in years}
    return Totals(years=years, all=all_years, by_site=by_site)


def _row_view(row: selectors.RowState, detail_name: str, shown: Sequence[str], factor: RowFactor) -> RowView:
    values = tuple(
        SlotValue(slot, row.values[slot].amount, row.values[slot].estimated) for slot in shown if slot in row.values
    )
    return RowView(
        id=row.id,
        site_facility_id=row.site_facility_id,
        detail_name=detail_name,
        unit=row.unit,
        na=row.na,
        values=values,
        emission=row.emission,
        emission_problem=row.emission_problem,
        factor=factor,
        factor_version_id=row.factor_version_id if isinstance(factor, FactorView) else None,
    )


def _detail(
    company_id: int, year: int, node_id: int, year_id: int, chosen: selections.SelectionState
) -> IndexDetail | NotFound:
    leaf = pool.alive_nodes([node_id]).get(node_id)
    unit = pool.leaf_unit(node_id)
    version = pool.pinned_version(chosen.factor_version_id)
    if leaf is None or unit is None or isinstance(version, NotFound):
        return NotFound()
    path = paths_of(pool.tree_nodes()).get(node_id, ())
    sites = _enabled_sites(company_id)
    rows = selectors.rows_of(company_id, chosen.id)
    factors = _row_factors(company_id, rows)
    periods = selectors.periods_of(company_id, [chosen.id])
    blocks: list[SiteBlock] = []
    for site in sites:
        facilities = [
            row for row in facilities_of(company_id, site.id) if row.facility_code_id == leaf.facility_code_id
        ]
        if not facilities:
            continue  # 그 잎 코드의 자산/시설이 없는 사업장은 블록·합에 없다
        names = {facility.id: facility.detail_name for facility in facilities}
        mine = [row for row in rows if row.site_id == site.id and row.site_facility_id in names]
        with_row = {row.site_facility_id for row in mine}
        period = periods.get((chosen.id, site.id), DEFAULT_PERIOD)
        shown = slots(year, period)
        blocks.append(
            SiteBlock(
                site_id=site.id,
                site_name=site.name,
                facilities=tuple(FacilityLine(f.id, f.detail_name, f.id in with_row) for f in facilities),
                rows=tuple(_row_view(row, names[row.site_facility_id], shown, factors[row.id]) for row in mine),
                period=period,
                slots=shown,
            )
        )
    decimals = selectors.decimals_of(company_id, year_id)
    return IndexDetail(
        year=year,
        node_id=node_id,
        name=path[-1].name if path else "",
        path=tuple(node.name for node in path),
        decimals=decimals,
        memo=chosen.memo,
        locked_at=chosen.locked_at,
        locked_by=_locked_by(company_id, chosen.locked_by_user_id),
        unit_options=unit_options(unit[1], conversions()),
        factor_version_id=chosen.factor_version_id,
        factor=version,
        totals=_totals(company_id, year, node_id, [site for site in sites if site.id in {b.site_id for b in blocks}]),
        sites=tuple(blocks),
    )


def index_detail(company_id: int, year: int, node_id: int) -> IndexDetail | NotFound:
    """ⓐ 그 해·잎의 상세(읽기 — 쓰지 않는다). 해·선택이 없거나 숨긴 잎이면 NotFound."""
    found = _year_and_selection(company_id, year, node_id, lock=False)
    if isinstance(found, NotFound):
        return found
    year_id, chosen = found
    return _detail(company_id, year, node_id, year_id, chosen)


# ── ⓑ 저장 ────────────────────────────────────────────────────────


def _row_problems(
    rows: Sequence[RowInput],
    *,
    allowed_slots: frozenset[str],
    facility_ids: frozenset[int],
    current: Mapping[int, selectors.RowState],
    alive_by_facility: Mapping[int, int],
    units: tuple[str, ...],
) -> dict[str, str]:
    errors: dict[str, str] = {}
    seen: set[int] = set()
    for index, row in enumerate(rows):
        at = f"rows.{index}"
        if row.site_facility_id not in facility_ids:
            errors[f"{at}.siteFacilityId"] = NOT_HERE
        elif row.site_facility_id in seen:
            errors[f"{at}.siteFacilityId"] = TWICE
        elif row.row_id is None and row.site_facility_id in alive_by_facility:
            errors[f"{at}.siteFacilityId"] = HAS_ROW
        seen.add(row.site_facility_id)
        if row.row_id is not None:
            existing = current.get(row.row_id)
            if existing is None:
                errors[f"{at}.rowId"] = NO_ROW
            elif existing.site_facility_id != row.site_facility_id:
                errors.setdefault(f"{at}.siteFacilityId", NO_ROW)
        if row.unit not in units:
            errors[f"{at}.unit"] = BAD_UNIT
        seen_slots: set[str] = set()
        for place, value in enumerate(row.values):
            where = f"{at}.values.{place}"
            if value.slot not in allowed_slots:
                errors[f"{where}.slot"] = BAD_SLOT
            elif value.slot in seen_slots:
                errors[f"{where}.slot"] = SLOT_TWICE
            seen_slots.add(value.slot)
            if value.amount is not None:
                problem = amount_problem(value.amount)
                if problem is not None:
                    errors[f"{where}.amount"] = problem
    return errors


def _amount(text: str | None) -> Decimal | None:
    return None if text is None else parse_decimal(text)


def _changes(
    row: RowInput, row_id: int, before: selectors.RowState | None, actor: Actor
) -> tuple[list[services.ValueWrite], list[services.HistoryWrite]]:
    """한 행의 값 쓰기와 히스토리 줄. 단위 바뀜 unit(값 줄보다 먼저 — 470 M2), N/A 바뀜 na_on/na_off, 값이 바뀐
    칸마다 value(줄의 unit 은 새 단위). 같은 값은 0. 추정 표시만 바뀌면 값은 쓰고 히스토리 0(469 R5)."""
    writes: list[services.ValueWrite] = []
    lines: list[services.HistoryWrite] = []
    old_values = before.values if before is not None else {}

    def line(kind: str, slot: str | None, old: str | None, new: str | None) -> services.HistoryWrite:
        return services.HistoryWrite(row_id, kind, slot, old, new, row.unit, actor.kind, actor.user_id)

    if before is not None and before.unit != row.unit:
        lines.append(line("unit", None, before.unit, row.unit))
    old_na = before.na if before is not None else False
    if row.na != old_na:
        lines.append(line("na_on" if row.na else "na_off", None, None, None))
    for value in row.values:
        amount = _amount(value.amount)
        old = old_values.get(value.slot)
        old_amount = old.amount if old is not None else None
        if old is not None and old_amount == amount and old.estimated == value.estimated:
            continue
        if old is None and amount is None and not value.estimated:
            continue  # 없는 칸을 빈 칸으로 — 바뀜 0
        writes.append(services.ValueWrite(row_id, value.slot, amount, value.estimated, None if old is None else old.id))
        if old_amount != amount:
            lines.append(line("value", value.slot, decimal_text(old_amount), decimal_text(amount)))
    return writes, lines


@transaction.atomic
def save_rows(
    company_id: int, year: int, node_id: int, site_id: int, rows: Sequence[RowInput], actor: Actor
) -> IndexDetail | NotFound | Invalid | Locked:
    """ⓑ 한 사업장의 행 저장. 잠금 해 → 선택 → 사업장 → 행. 판정(422 fields.rows.<i>.<칸>)에 걸리면 0 씀.
    칸은 블록 입력주기의 것만 받는다(S12a-2). 셈은 행마다 직접입력 > 행 판 > 선택 판."""
    if len(rows) > MAX_ROWS_PER_SAVE:
        return Invalid({"rows": TOO_MANY})
    if selections.lock_year(company_id, year) is None:
        return NotFound()
    found = _year_and_selection(company_id, year, node_id, lock=True)
    if isinstance(found, NotFound):
        return found
    year_id, chosen = found
    site = lock_branch(company_id, site_id)
    if site is None or not site.inventory_enabled:
        return NotFound()
    if chosen.locked_at is not None:
        return Locked()
    leaf = pool.alive_nodes([node_id]).get(node_id)
    unit = pool.leaf_unit(node_id)
    pinned = pool.pinned_version(chosen.factor_version_id)
    if leaf is None or unit is None or isinstance(pinned, NotFound):
        return NotFound()
    facility_ids = frozenset(
        row.id for row in facilities_of(company_id, site_id) if row.facility_code_id == leaf.facility_code_id
    )
    current = {row.id: row for row in selectors.lock_rows(company_id, chosen.id, site_id)}
    alive_by_facility = {row.site_facility_id: row.id for row in current.values()}
    allowed = frozenset(
        slots(year, selectors.periods_of(company_id, [chosen.id]).get((chosen.id, site_id), DEFAULT_PERIOD))
    )
    errors = _row_problems(
        rows,
        allowed_slots=allowed,
        facility_ids=facility_ids,
        current=current,
        alive_by_facility=alive_by_facility,
        units=unit_options(unit[1], conversions()),
    )
    if errors:
        return Invalid(errors)

    new = [index for index, row in enumerate(rows) if row.row_id is None]
    made = services.insert_rows(
        company_id,
        chosen.id,
        [services.NewRow(rows[index].site_facility_id, rows[index].unit, rows[index].na) for index in new],
    )
    if isinstance(made, services.RowTaken):
        transaction.set_rollback(True)
        return Invalid({"rows": RACE})
    ids = dict(zip(new, made, strict=True))
    factors = _row_factors(company_id, list(current.values()))
    writes: list[services.ValueWrite] = []
    lines: list[services.HistoryWrite] = []
    figures: list[services.RowFigures] = []
    for index, row in enumerate(rows):
        row_id = row.row_id if row.row_id is not None else ids[index]
        before = current.get(row_id)
        row_writes, row_lines = _changes(row, row_id, before, actor)
        writes += row_writes
        lines += row_lines
        amounts = {slot: value.amount for slot, value in (before.values if before is not None else {}).items()}
        amounts |= {write.slot: write.amount for write in row_writes}
        version = _version_of(factors.get(row_id), pinned)
        total, problem = _figures(row_total(row.na, _period_amounts(amounts, allowed)), row.unit, version)
        figures.append(services.RowFigures(row_id, row.unit, row.na, total, problem))
    services.upsert_values(company_id, writes)
    services.insert_history(company_id, lines)
    services.update_rows(company_id, figures)
    return _detail(company_id, year, node_id, year_id, chosen)


# ── ⓒ~ⓖ ─────────────────────────────────────────────────────────


@transaction.atomic
def delete_rows(company_id: int, year: int, node_id: int, ids: Sequence[int]) -> int | NotFound | Locked:
    """ⓒ 행 삭제 표시. 하나라도 없거나 남의 것이면 NotFound(0 바뀜). 지운 수."""
    found = _year_and_selection(company_id, year, node_id, lock=True)
    if isinstance(found, NotFound):
        return found
    _, chosen = found
    if chosen.locked_at is not None:
        return Locked()
    wanted = frozenset(ids)
    if not wanted or selectors.alive_row_ids(company_id, chosen.id, wanted) != wanted:
        return NotFound()
    return services.mark_rows_deleted(company_id, wanted)


@transaction.atomic
def set_memo(company_id: int, year: int, node_id: int, memo: str) -> str | NotFound | Invalid | Locked:
    """ⓓ 인덱스 메모(2,000자까지). 저장한 메모."""
    if len(memo) > MEMO_MAX:
        return Invalid({"memo": MEMO_TOO_LONG})
    found = _year_and_selection(company_id, year, node_id, lock=True)
    if isinstance(found, NotFound):
        return found
    _, chosen = found
    if chosen.locked_at is not None:
        return Locked()
    services.set_memo(company_id, chosen.id, memo)
    return memo


@transaction.atomic
def lock_index(company_id: int, year: int, node_id: int, actor: Actor) -> IndexDetail | NotFound:
    """ⓔ 잠그기. 이미 잠겼으면 0 바뀜(잠근 사람·때 그대로). 응답은 ⓐ."""
    found = _year_and_selection(company_id, year, node_id, lock=True)
    if isinstance(found, NotFound):
        return found
    year_id, chosen = found
    if chosen.locked_at is None:
        services.set_lock(company_id, chosen.id, locked_by_user_id=actor.user_id)
        chosen = selections.selection_of(company_id, year_id, node_id) or chosen
    return _detail(company_id, year, node_id, year_id, chosen)


@transaction.atomic
def unlock_index(company_id: int, year: int, node_id: int, *, actor_kind: Kind) -> IndexDetail | NotFound | Forbidden:
    """ⓕ 풀기 — 운영 관리자만(경로의 permitted 에 더해 첫 문장에서 다시 — ALSO_INSIDE). 안 잠겼으면 0 바뀜."""
    if not is_allowed(UNLOCK, kind=actor_kind):
        return Forbidden(UNLOCK)
    found = _year_and_selection(company_id, year, node_id, lock=True)
    if isinstance(found, NotFound):
        return found
    year_id, chosen = found
    if chosen.locked_at is not None:
        services.set_lock(company_id, chosen.id, locked_by_user_id=None)
        chosen = selections.selection_of(company_id, year_id, node_id) or chosen
    return _detail(company_id, year, node_id, year_id, chosen)


@transaction.atomic
def set_decimals(company_id: int, year: int, decimals: int) -> int | NotFound | Invalid:
    """ⓖ 해의 표시 자릿수(저장값 그대로). 해가 없으면 NotFound. 저장한 자릿수."""
    low, high = DECIMALS_RANGE
    if not low <= decimals <= high:
        return Invalid({"decimals": BAD_DECIMALS})
    year_id = selections.year_of(company_id, year)
    if year_id is None:
        return NotFound()
    year_services.set_decimals(company_id, year_id, decimals)
    return decimals


# ── ⓗ~ⓙ 읽기 ───────────────────────────────────────────────────────


def years(company_id: int) -> list[YearLine]:
    """ⓗ 그 회사의 해(새 해 먼저) — configured = 숨기지 않은 선택이 있음."""
    return [YearLine(year, configured) for year, configured in selectors.years_of(company_id)]


def list_rows(company_id: int, year: int, q: str | None = None) -> RowList | Invalid:
    """ⓘ 리스트 — 숨기지 않은 선택 잎마다 Y-2·Y-1·Y 합(켠 사업장만), 뿌리 노드(Scope)마다 묶음과 합.
    q 는 잎·조상 이름 부분 일치(대소문자 무시). 설정 안 된 해는 configured false · 줄 0."""
    if q is not None and len(q) > Q_MAX:
        return Invalid({"q": Q_TOO_LONG})
    shown = list_years(year)
    year_id = selections.year_of(company_id, year)
    chosen = selections.selections_of(company_id, year_id) if year_id is not None else {}
    visible = {node_id: row for node_id, row in chosen.items() if not row.hidden}
    if year_id is None or not visible:
        decimals = DEFAULT_DECIMALS if year_id is None else selectors.decimals_of(company_id, year_id)
        return RowList(year=year, years=shown, configured=False, decimals=decimals, scopes=())
    paths = paths_of(pool.tree_nodes())
    site_ids = {site.id for site in _enabled_sites(company_id)}
    by: dict[tuple[int, int], list[Decimal | None]] = defaultdict(list)
    for line in selectors.year_rows(company_id, shown):
        if line.site_id in site_ids:
            by[(line.node_id, line.year)].append(line.emission)
    estimated = _estimated_nodes(company_id, year, year_id, site_ids)
    states = selections.selection_states(company_id, year_id)
    needle = q.casefold() if q else None
    groups: dict[int, list[ListRow]] = defaultdict(list)
    names: dict[int, str] = {}
    for node_id in visible:
        path = paths.get(node_id)
        if not path:
            continue
        if needle is not None and not any(needle in node.name.casefold() for node in path):
            continue
        state = states.get(node_id)
        names[path[0].id] = path[0].name
        groups[path[0].id].append(
            ListRow(
                node_id=node_id,
                path=tuple(node.name for node in path),
                values={y: sum_or_none(by.get((node_id, y), ())) for y in shown},
                has_memo=bool(state and state.memo),
                estimated=node_id in estimated,
                locked=bool(state and state.locked_at is not None),
            )
        )
    order = {node.id: index for index, node in enumerate(pool.tree_nodes())}
    scopes = tuple(
        ScopeGroup(
            scope_id=scope_id,
            scope_name=names[scope_id],
            values={y: sum_or_none(row.values[y] for row in lines) for y in shown},
            rows=tuple(sorted(lines, key=lambda row: order.get(row.node_id, 0))),
        )
        for scope_id, lines in sorted(groups.items(), key=lambda item: order.get(item[0], 0))
    )
    return RowList(
        year=year, years=shown, configured=True, decimals=selectors.decimals_of(company_id, year_id), scopes=scopes
    )


def _estimated_nodes(company_id: int, year: int, year_id: int, site_ids: Collection[int]) -> frozenset[int]:
    """추정 표시 값이 있는 잎 — 켠 사업장의 행·블록 입력주기의 칸만(470 M4 · S12a-2)."""
    lines = [line for line in selectors.estimated_lines(company_id, year_id) if line.site_id in site_ids]
    periods = selectors.periods_of(company_id, {line.selection_id for line in lines})
    return frozenset(
        line.node_id
        for line in lines
        if line.slot in slots(year, periods.get((line.selection_id, line.site_id), DEFAULT_PERIOD))
    )


def _ref_names(company_id: int, rows: Sequence[selectors.HistoryRow]) -> tuple[dict[int, str], dict[int, str]]:
    """factor 줄의 앞뒤 참조 이름 — (판 id → 판 이름, 직접입력 id → 이름)."""
    version_ids = {ref for row in rows for ref in (row.before_version_id, row.after_version_id) if ref is not None}
    custom_ids = {ref for row in rows for ref in (row.before_custom_id, row.after_custom_id) if ref is not None}
    versions: dict[int, str] = {}
    for version_id in version_ids:
        view = pool.pinned_version(version_id)
        versions[version_id] = "" if isinstance(view, NotFound) else view.name
    customs = {custom_id: view.name for custom_id, view in selectors.custom_of(company_id, custom_ids).items()}
    return versions, customs


def _ref(
    version_id: int | None, custom_id: int | None, versions: Mapping[int, str], customs: Mapping[int, str]
) -> FactorRef:
    if custom_id is not None:
        return FactorRef(version_id=None, custom_id=custom_id, name=customs.get(custom_id, ""))
    return FactorRef(version_id=version_id, custom_id=None, name=versions.get(version_id or 0, ""))


def _gone_version(version_id: int, node_id: int) -> bool:
    """판의 계수가 지워졌거나 이 잎의 것이 아니다(감독 길 i — 지운 풀 계수 판은 행에 다시 잡지 않는다)."""
    view = pool.pinned_version(version_id)
    return isinstance(view, NotFound) or pool.current_version_id(view.id, node_id) is None


def _stale(line: selectors.HistoryRow, row: selectors.RowState, allowed: frozenset[str], node_id: int) -> bool:
    """줄의 뒤 상태로 못 되돌림: value 줄은 칸이 지금 주기 밖이거나 단위가 행 단위와 다름 · factor 줄은 뒤 판의 풀
    계수가 지워짐(직접입력은 늘 됨). period 줄은 늘 됨."""
    if line.kind == "value":
        return line.slot not in allowed or line.unit != row.unit
    if line.kind == "factor" and line.after_version_id is not None:
        return _gone_version(line.after_version_id, node_id)
    return False


def row_history(
    company_id: int, year: int, node_id: int, row_id: int, *, offset: int, limit: int
) -> HistoryPage | NotFound:
    """ⓙ 행 히스토리(새 것 먼저). 그 해·잎의 살아 있는 행이 아니면 NotFound(지운 행 404). 줄마다 사유·복구 가능
    (restore_problem — 복구 판정과 한 함수)·factor 줄의 앞뒤 계수 이름(S12a-2)."""
    found = _year_and_selection(company_id, year, node_id, lock=False)
    if isinstance(found, NotFound):
        return found
    _, chosen = found
    row = selectors.row_of(company_id, chosen.id, row_id)
    if row is None:
        return NotFound()
    count, rows = selectors.history_of(company_id, row_id, offset=offset, limit=limit)
    customers = {row.actor_user_id for row in rows if row.actor_kind == "service" and row.actor_user_id is not None}
    operators = {row.actor_user_id for row in rows if row.actor_kind == "admin" and row.actor_user_id is not None}
    people = names_of(company_id, customers, operators)
    top = selectors.top_line_id(company_id, row_id)
    period = selectors.periods_of(company_id, [chosen.id]).get((chosen.id, row.site_id), DEFAULT_PERIOD)
    allowed = frozenset(slots(year, period))
    locked = chosen.locked_at is not None
    versions, customs = _ref_names(company_id, rows)
    return HistoryPage(
        count=count,
        lines=tuple(
            HistoryLine(
                id=line.id,
                at=line.created_at,
                kind=line.kind,
                slot=line.slot,
                before=line.before,
                after=line.after,
                unit=line.unit,
                actor_kind=line.actor_kind,
                actor_user_id=line.actor_user_id,
                actor_name=people[line.actor_user_id][1] if line.actor_user_id in people else None,
                reason=line.reason,
                restorable=restore_problem(
                    line.kind, top=line.id == top, locked=locked, stale=_stale(line, row, allowed, node_id)
                )
                is None,
                before_factor=(
                    _ref(line.before_version_id, line.before_custom_id, versions, customs)
                    if line.kind == "factor"
                    else None
                ),
                after_factor=(
                    _ref(line.after_version_id, line.after_custom_id, versions, customs)
                    if line.kind == "factor"
                    else None
                ),
            )
            for line in rows
        ),
    )


# ── ⓚ~ⓜ S12a-2(S7 입력주기 · S9·S11 계수 바꿈 · S12 복구) ───────────────────


def _block(
    company_id: int, year: int, node_id: int, site_id: int, *, factor_lock: bool
) -> tuple[int, selections.SelectionState, FactorView] | NotFound:
    """쓰기의 잠금 줄(해 → [잎] → 선택 → 사업장)과 블록 판정. 켠 사업장에 그 잎 코드 자산/시설이 없으면 NotFound.
    잠김 판정은 부르는 쪽(판정 차례가 동작마다 다르다)."""
    if selections.lock_year(company_id, year) is None:
        return NotFound()
    if factor_lock and node_id not in pool.lock_nodes({node_id}):
        return NotFound()
    found = _year_and_selection(company_id, year, node_id, lock=True)
    if isinstance(found, NotFound):
        return found
    year_id, chosen = found
    site = lock_branch(company_id, site_id)
    if site is None or not site.inventory_enabled:
        return NotFound()
    leaf = pool.alive_nodes([node_id]).get(node_id)
    pinned = pool.pinned_version(chosen.factor_version_id)
    if leaf is None or isinstance(pinned, NotFound):
        return NotFound()
    if not any(row.facility_code_id == leaf.facility_code_id for row in facilities_of(company_id, site_id)):
        return NotFound()
    return year_id, chosen, pinned


def _period_of(company_id: int, selection_id: int, site_id: int) -> str:
    return selectors.periods_of(company_id, [selection_id]).get((selection_id, site_id), DEFAULT_PERIOD)


def _refigure(
    company_id: int,
    rows: Sequence[selectors.RowState],
    *,
    year: int,
    period: str,
    pinned: FactorView,
    factors: Mapping[int, RowFactor],
) -> None:
    """행들의 셈 칸을 블록 주기 칸·행 계수로 다시 쓴다."""
    allowed = frozenset(slots(year, period))
    figures: list[services.RowFigures] = []
    for row in rows:
        amounts = {slot: value.amount for slot, value in row.values.items()}
        version = _version_of(factors.get(row.id), pinned)
        total, problem = _figures(row_total(row.na, _period_amounts(amounts, allowed)), row.unit, version)
        figures.append(services.RowFigures(row.id, row.unit, row.na, total, problem))
    services.update_rows(company_id, figures)


def _change_period(
    company_id: int,
    *,
    year: int,
    chosen: selections.SelectionState,
    site_id: int,
    pinned: FactorView,
    period: str,
    actor: Actor,
    reason: str | None,
) -> None:
    """블록 주기를 바꾸고(옛 칸 값 그대로) 블록의 살아 있는 행마다 period 줄 → 새 주기 칸만으로 다시 셈."""
    old = _period_of(company_id, chosen.id, site_id)
    services.upsert_period(company_id, chosen.id, site_id, period)
    rows = selectors.lock_rows(company_id, chosen.id, site_id)
    services.insert_history(
        company_id,
        [
            services.HistoryWrite(row.id, "period", None, old, period, row.unit, actor.kind, actor.user_id, reason)
            for row in rows
        ],
    )
    _refigure(company_id, rows, year=year, period=period, pinned=pinned, factors=_row_factors(company_id, rows))


@transaction.atomic
def set_period(
    company_id: int, year: int, node_id: int, site_id: int, period: str, actor: Actor
) -> IndexDetail | NotFound | Invalid | Locked:
    """ⓚ 사업장 블록의 입력주기(S7). 목록 밖 422 fields.period · 같으면 0 바뀜 · 행 없는 블록도 저장. 응답 ⓐ."""
    if period not in PERIODS:
        return Invalid({"period": BAD_PERIOD})
    found = _block(company_id, year, node_id, site_id, factor_lock=False)
    if isinstance(found, NotFound):
        return found
    year_id, chosen, pinned = found
    if chosen.locked_at is not None:
        return Locked()
    if _period_of(company_id, chosen.id, site_id) != period:
        _change_period(
            company_id,
            year=year,
            chosen=chosen,
            site_id=site_id,
            pinned=pinned,
            period=period,
            actor=actor,
            reason=None,
        )
    return _detail(company_id, year, node_id, year_id, chosen)


def _reason_problem(reason: str | None, *, required: bool) -> dict[str, str]:
    cleaned = reason_text(reason)
    if cleaned is None:
        return {"reason": NEED_REASON} if required else {}
    return {"reason": REASON_TOO_LONG} if len(cleaned) > REASON_MAX else {}


def _checked_custom(draft: FactorDraft) -> FactorValues | dict[str, str]:
    """직접입력 계수의 검사(S20 의 check_factor 그대로 — 오류는 fields.custom.<칸>)."""
    checked = check_factor(draft)
    if isinstance(checked, dict):
        return {f"custom.{key}": message for key, message in checked.items()}
    if checked.emission_unit != DEFAULT_EMISSION_UNIT:
        return {"custom.emissionUnit": BAD_EMISSION_UNIT}  # 직접입력 표에 배출량 단위 칸 0 — tCO2-eq 하나
    return checked


def _ref_or_pinned(
    version_id: int | None, custom_id: int | None, chosen: selections.SelectionState
) -> tuple[int | None, int | None]:
    """행 덮어쓰기(둘 다 None = 선택의 잡은 판) → 히스토리의 참조(판 또는 직접입력 정확히 하나)."""
    if version_id is None and custom_id is None:
        return chosen.factor_version_id, None
    return version_id, custom_id


def _change_factor(
    company_id: int,
    *,
    year: int,
    chosen: selections.SelectionState,
    row: selectors.RowState,
    pinned: FactorView,
    target: tuple[int | None, int | None],
    actor: Actor,
    reason: str | None,
) -> None:
    """행 계수를 target(판, 직접입력)으로 — 선택이 잡은 판이면 None(판단 C). factor 줄 하나 → 다시 셈."""
    version_id, custom_id = target
    if custom_id is None and version_id == chosen.factor_version_id:
        version_id = None
    if (version_id, custom_id) == (row.factor_version_id, row.custom_factor_id):
        return  # 같은 계수 — 0 바뀜
    before = _ref_or_pinned(row.factor_version_id, row.custom_factor_id, chosen)
    after = _ref_or_pinned(version_id, custom_id, chosen)
    services.set_row_factor(company_id, row.id, version_id=version_id, custom_id=custom_id)
    services.insert_history(
        company_id,
        [
            services.HistoryWrite(
                row.id,
                "factor",
                None,
                None,
                None,
                row.unit,
                actor.kind,
                actor.user_id,
                reason,
                before_version_id=before[0],
                after_version_id=after[0],
                before_custom_id=before[1],
                after_custom_id=after[1],
            )
        ],
    )
    moved = replace(row, factor_version_id=version_id, custom_factor_id=custom_id)
    _refigure(
        company_id,
        [moved],
        year=year,
        period=_period_of(company_id, chosen.id, row.site_id),
        pinned=pinned,
        factors=_row_factors(company_id, [moved]),
    )


def _locked_row(
    company_id: int, year: int, node_id: int, row_id: int
) -> tuple[int, selections.SelectionState, FactorView, selectors.RowState] | NotFound:
    """계수가 닿는 쓰기의 잠금 줄: 해 → 잎 → 선택 → 행의 사업장 → 행. 그 해·잎의 살아 있는 행이 아니면 NotFound."""
    year_id = selections.year_of(company_id, year)
    chosen = None if year_id is None else selections.selection_of(company_id, year_id, node_id)
    seen = None if chosen is None else selectors.row_of(company_id, chosen.id, row_id)
    if seen is None:
        return NotFound()
    found = _block(company_id, year, node_id, seen.site_id, factor_lock=True)
    if isinstance(found, NotFound):
        return found
    year_id, chosen, pinned = found
    row = next((line for line in selectors.lock_rows(company_id, chosen.id, seen.site_id) if line.id == row_id), None)
    if row is None:
        return NotFound()
    return year_id, chosen, pinned, row


def _unit_mismatch(node_id: int, values: FactorValues | None, version_id: int | None) -> dict[str, str] | NotFound:
    """직접입력(values)이나 풀의 판(version_id)을 잎 단위 선택지로 대조한다. 둘 다 없으면 볼 것이 없어 {}."""
    picked = values if values is not None or version_id is None else pool.pinned_version(version_id)
    if picked is None or isinstance(picked, NotFound):
        return {} if picked is None else picked
    leaf_unit = pool.leaf_unit(node_id)
    if leaf_unit is None:
        return NotFound()  # 잠근 뒤 잎이 사라짐(_detail 과 같은 갈래)
    row_units = unit_options(leaf_unit[1], conversions())
    if isinstance(picked, FactorView):
        return pool_unit_problem(row_units, picked, conversions())
    return custom_unit_problem(row_units, picked, conversions())


@transaction.atomic
def set_row_factor(
    company_id: int,
    year: int,
    node_id: int,
    row_id: int,
    *,
    factor_id: int | None,
    custom: FactorDraft | None,
    reason: str | None,
    actor: Actor,
) -> IndexDetail | NotFound | Invalid | Locked | Forbidden:
    """ⓛ 행 하나의 계수 바꿈(S9·S11) — 운영 관리자만(경로의 permitted 에 더해 첫 문장에서 다시 — ALSO_INSIDE).
    같은 잎의 삭제 안 된 풀 계수(그 지금 판을 잡음 — 잎을 잠근 뒤 다시 읽음) 또는 직접입력(새 행 — 고치지 않음).
    사유 필수. 직접입력(sid:MARC-ISSUE-548)과 고른 풀 계수(sid:MARC-ISSUE-558)는 잎 단위 선택지마다 셈할 수 있어야 한다
    (404 뒤·409 앞 422). 선택이 잡은 계수로 되돌리기는 대조하지 않는다 — 행 덮어쓰기를 풀 뿐이다. 응답 ⓐ."""
    if not is_allowed(ROW_FACTOR, kind=actor.kind):
        return Forbidden(ROW_FACTOR)
    errors = _reason_problem(reason, required=True)
    values: FactorValues | None = None
    if (factor_id is None) == (custom is None):
        errors["factorId"] = ONE_FACTOR
    elif custom is not None:
        checked = _checked_custom(custom)
        if isinstance(checked, dict):
            errors |= checked
        else:
            values = checked
    if errors:
        return Invalid(errors)
    found = _locked_row(company_id, year, node_id, row_id)
    if isinstance(found, NotFound):
        return found
    year_id, chosen, pinned, row = found
    version_id = None if factor_id is None else pool.current_version_id(factor_id, node_id)
    mismatch = _unit_mismatch(node_id, values, None if factor_id == pinned.id else version_id)
    if isinstance(mismatch, NotFound):
        return mismatch
    if mismatch:
        return Invalid(mismatch)  # 548·558: 잎 단위로 셈할 수 없는 계수 — 잠김보다 앞(Q2), 쓰기 0
    if chosen.locked_at is not None:
        return Locked()
    target: tuple[int | None, int | None]
    if factor_id is not None:
        if version_id is None:
            return Invalid({"factorId": BAD_FACTOR})
        target = (None, None) if factor_id == pinned.id else (version_id, None)
    elif values is not None:
        target = (None, services.insert_custom(company_id, values, actor))
    else:
        raise AssertionError("factorId 나 검사를 지난 직접입력 하나")
    _change_factor(
        company_id,
        year=year,
        chosen=chosen,
        row=row,
        pinned=pinned,
        target=target,
        actor=actor,
        reason=reason_text(reason),
    )
    return _detail(company_id, year, node_id, year_id, chosen)


@transaction.atomic
def restore(
    company_id: int, year: int, node_id: int, row_id: int, history_id: int, *, reason: str | None, actor: Actor
) -> IndexDetail | NotFound | Invalid | Locked | Forbidden | RestoreStale:
    """ⓜ 히스토리 줄의 뒤(after) 상태로 되돌리는 **새 줄**을 쌓는다(S12 — 판단 D, 지우기 0). value·period·factor 만,
    그 행의 맨 위 줄은 안 됨. factor 줄은 운영 관리자만(403)·사유 필수. 낡은 줄 409 restore_stale. 잠금 줄은 줄
    종류와 상관없이 계수 바꿈과 같다(해 → 잎 → 선택 → 사업장 → 행). 응답 ⓐ."""
    found = _locked_row(company_id, year, node_id, row_id)
    if isinstance(found, NotFound):
        return found
    year_id, chosen, pinned, row = found
    line = selectors.history_line(company_id, row_id, history_id)
    if line is None:
        return NotFound()
    period = _period_of(company_id, chosen.id, row.site_id)
    problem = restore_problem(
        line.kind,
        top=selectors.top_line_id(company_id, row_id) == line.id,
        locked=chosen.locked_at is not None,
        stale=_stale(line, row, frozenset(slots(year, period)), node_id),
    )
    if problem == RESTORE_KIND:
        return Invalid({"historyId": NOT_RESTORABLE})
    if line.kind == "factor" and not is_allowed(ROW_FACTOR, kind=actor.kind):
        return Forbidden(ROW_FACTOR)
    errors = _reason_problem(reason, required=line.kind == "factor")
    if errors:
        return Invalid(errors)
    if problem == RESTORE_TOP:
        return Invalid({"historyId": TOP_LINE})
    if problem == RESTORE_LOCKED:
        return Locked()
    if problem == RESTORE_STALE:
        return RestoreStale()
    cleaned = reason_text(reason)
    if line.kind == "value":
        _restore_value(
            company_id,
            year=year,
            period=period,
            chosen=chosen,
            row=row,
            line=line,
            pinned=pinned,
            actor=actor,
            reason=cleaned,
        )
    elif line.kind == "period":
        if line.after is not None and line.after != period:
            _change_period(
                company_id,
                year=year,
                chosen=chosen,
                site_id=row.site_id,
                pinned=pinned,
                period=line.after,
                actor=actor,
                reason=cleaned,
            )
    else:
        _change_factor(
            company_id,
            year=year,
            chosen=chosen,
            row=row,
            pinned=pinned,
            target=_restore_target(line, pinned, node_id),
            actor=actor,
            reason=cleaned,
        )
    return _detail(company_id, year, node_id, year_id, chosen)


def _restore_target(line: selectors.HistoryRow, pinned: FactorView, node_id: int) -> tuple[int | None, int | None]:
    """factor 줄 복구의 뒤 계수(판단 C — MARC-ENT-517 「다른 계수는 그 지금 판」): 직접입력은 그 행 그대로, 풀 판은 그
    **계수**의 지금 판(줄이 적은 옛 판이 아님), 선택이 잡은 계수면 None. 지운 계수는 _stale 이 먼저 409 로 막는다."""
    if line.after_version_id is None:
        return None, line.after_custom_id
    view = pool.pinned_version(line.after_version_id)
    if isinstance(view, NotFound) or view.id == pinned.id:
        return None, None
    return pool.current_version_id(view.id, node_id), None


def _restore_value(
    company_id: int,
    *,
    year: int,
    period: str,
    chosen: selections.SelectionState,
    row: selectors.RowState,
    line: selectors.HistoryRow,
    pinned: FactorView,
    actor: Actor,
    reason: str | None,
) -> None:
    """value 줄의 뒤 값으로 그 칸을 쓴다(추정 표시 그대로). 지금 값과 같으면 0 바뀜."""
    slot = line.slot or ""
    amount = _amount(line.after)
    old = row.values.get(slot)
    old_amount = old.amount if old is not None else None
    if old_amount == amount:
        return
    estimated = old.estimated if old is not None else False
    services.upsert_values(
        company_id, [services.ValueWrite(row.id, slot, amount, estimated, None if old is None else old.id)]
    )
    services.insert_history(
        company_id,
        [
            services.HistoryWrite(
                row.id,
                "value",
                slot,
                decimal_text(old_amount),
                decimal_text(amount),
                row.unit,
                actor.kind,
                actor.user_id,
                reason,
            )
        ],
    )
    values = {**row.values, slot: selectors.ValueState(old.id if old is not None else 0, amount, estimated)}
    moved = replace(row, values=values)
    _refigure(company_id, [moved], year=year, period=period, pinned=pinned, factors=_row_factors(company_id, [moved]))
