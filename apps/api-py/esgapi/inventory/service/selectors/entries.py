"""Scope 1·2 입력 행·값·히스토리(회사 범위 표 셋)의 읽기. 밴드 S12a ②. 쓰지 않는다.

★ 조회마다 회사 조건을 적는다(`<표>.for_company(company_id)`). 회사 id 는 부르는 쪽이 정한 것이다(고객사 사용자는
  주체의 회사, 운영 관리자는 core/auth/bearer.py 의 company_of 가 고른 작업 회사). 무효 조건: 그 값이 틀리면 그 틀린
  회사로 가른다.
★ 행 잠금은 여기와 index_selection.py 의 lock_selection 뿐이다(lock_rows — 입력 저장이 선택 잠금 아래에서 그 사업장의
  행을 잠가 읽는다).
★ 「데이터 있음」(sites_in_use·facilities_in_use — 조직구조의 지우기·코드 바꾸기 판정, selections_with_data 와 한 뜻)
  = 삭제 안 된 입력 행이 있음(값 유무 무관 · 숨긴 선택의 행도 셈 — 발주서 판단 1). 사업장은 행 → 자산/시설 → 사업장을
  글자 조회로 따라간다(organization models import 0 — 계약 나·바).
"""

from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from esgapi.inventory.models import (
    CompanyIndexSelection,
    InventoryCustomFactor,
    InventoryEntryHistory,
    InventoryEntryPeriod,
    InventoryEntryRow,
    InventoryEntryValue,
    InventoryYear,
)
from esgapi.inventory.service.utils.entries import CustomView, gases_of


@dataclass(frozen=True)
class ValueState:
    id: int
    amount: Decimal | None
    estimated: bool


@dataclass(frozen=True)
class RowState:
    """살아 있는 입력 행 하나와 그 값(slot → 값)."""

    id: int
    site_facility_id: int
    site_id: int
    unit: str
    na: bool
    emission: Decimal | None
    emission_problem: str | None
    factor_version_id: int | None  # S12a-2 계수 덮어쓰기(둘 다 None = 선택의 잡은 판)
    custom_factor_id: int | None
    values: dict[str, ValueState] = field(default_factory=dict[str, ValueState])


@dataclass(frozen=True)
class EmissionLine:
    """리스트·상세 합의 재료 한 줄: (해, 잎, 사업장)의 행 배출량."""

    year: int
    node_id: int
    site_id: int
    emission: Decimal | None
    problem: str | None = None  # S12a-3: 행의 emission_problem(대시보드 complete — 리스트·상세는 읽지 않음)


@dataclass(frozen=True)
class HistoryRow:
    id: int
    created_at: datetime
    kind: str
    slot: str | None
    before: str | None
    after: str | None
    unit: str
    actor_kind: str
    actor_user_id: int | None
    reason: str | None
    before_version_id: int | None
    after_version_id: int | None
    before_custom_id: int | None
    after_custom_id: int | None


@dataclass(frozen=True)
class EstimatedLine:
    """추정 표시 값 한 칸의 자리(리스트 추정의 재료 — 사업장·주기 거름은 actions)."""

    node_id: int
    site_id: int
    selection_id: int
    slot: str


_ROW_FIELDS = (
    "id",
    "site_facility_id",
    "site_facility__site_id",
    "unit",
    "na",
    "emission",
    "emission_problem",
    "factor_version_id",
    "custom_factor_id",
)
_HISTORY_FIELDS = (
    "id",
    "created_at",
    "kind",
    "slot",
    "before",
    "after",
    "unit",
    "actor_kind",
    "actor_user_id",
    "reason",
    "before_version_id",
    "after_version_id",
    "before_custom_id",
    "after_custom_id",
)


def _with_values(company_id: int, found: list[RowState]) -> list[RowState]:
    values = InventoryEntryValue.for_company(company_id).filter(row_id__in=[row.id for row in found])
    by_row = {row.id: row for row in found}
    for value_id, row_id, slot, amount, estimated in values.values_list("id", "row_id", "slot", "amount", "estimated"):
        by_row[row_id].values[slot] = ValueState(id=value_id, amount=amount, estimated=estimated)
    return found


def rows_of(company_id: int, selection_id: int) -> list[RowState]:
    """그 선택의 살아 있는 행 전부와 값 — 행 id 차례."""
    rows = InventoryEntryRow.for_company(company_id).filter(selection_id=selection_id, deleted_at__isnull=True)
    found = [RowState(*line) for line in rows.order_by("id").values_list(*_ROW_FIELDS)]
    return _with_values(company_id, found)


def row_of(company_id: int, selection_id: int, row_id: int) -> RowState | None:
    """그 선택의 살아 있는 행 하나와 값(잠그지 않는다 — 사업장을 알아 잠그기 전에). 없으면 None."""
    rows = InventoryEntryRow.for_company(company_id).filter(
        selection_id=selection_id, pk=row_id, deleted_at__isnull=True
    )
    found = [RowState(*line) for line in rows.values_list(*_ROW_FIELDS)]
    return _with_values(company_id, found)[0] if found else None


def lock_rows(company_id: int, selection_id: int, site_id: int) -> list[RowState]:
    """그 선택·사업장의 살아 있는 행을 잠가 읽는다(블록 안에서만 — 선택 잠금 뒤). id 차례."""
    rows = (
        InventoryEntryRow.for_company(company_id)
        .select_for_update(of=("self",))
        .filter(selection_id=selection_id, site_facility__site_id=site_id, deleted_at__isnull=True)
        .order_by("id")
    )
    found = [RowState(*line) for line in rows.values_list(*_ROW_FIELDS)]
    return _with_values(company_id, found)


def alive_row_ids(company_id: int, selection_id: int, ids: Collection[int]) -> frozenset[int]:
    """ids 가운데 그 선택의 살아 있는 행(지우기·히스토리의 「있나」). 남의 회사·남의 선택 id 는 안 든다."""
    rows = InventoryEntryRow.for_company(company_id).filter(
        selection_id=selection_id, pk__in=list(ids), deleted_at__isnull=True
    )
    return frozenset(rows.values_list("id", flat=True))


def history_of(company_id: int, row_id: int, *, offset: int, limit: int) -> tuple[int, list[HistoryRow]]:
    """그 행의 바뀜 — 새 것 먼저(같은 때는 id 내림). (자르기 전 수, 쪽)."""
    rows = InventoryEntryHistory.for_company(company_id).filter(row_id=row_id)
    page = rows.order_by("-created_at", "-id").values_list(*_HISTORY_FIELDS)[offset : offset + limit]
    return rows.count(), [HistoryRow(*line) for line in page]


def history_line(company_id: int, row_id: int, history_id: int) -> HistoryRow | None:
    """그 행의 히스토리 줄 하나(복구 — S12). 남의 행·남의 회사 줄이면 None."""
    rows = InventoryEntryHistory.for_company(company_id).filter(row_id=row_id, pk=history_id)
    line = rows.values_list(*_HISTORY_FIELDS).first()
    return None if line is None else HistoryRow(*line)


def top_line_id(company_id: int, row_id: int) -> int | None:
    """그 행 히스토리의 맨 위(가장 새 — created_at·id 내림 첫) 줄 id. 줄이 없으면 None."""
    rows = InventoryEntryHistory.for_company(company_id).filter(row_id=row_id)
    return rows.order_by("-created_at", "-id").values_list("id", flat=True).first()


def periods_of(company_id: int, selection_ids: Collection[int]) -> dict[tuple[int, int], str]:
    """(선택, 사업장) → 입력주기(S7). 행이 없는 블록은 빠진다(부르는 쪽이 month 로)."""
    rows = InventoryEntryPeriod.for_company(company_id).filter(selection_id__in=list(selection_ids))
    return {
        (selection_id, site_id): period
        for selection_id, site_id, period in rows.values_list("selection_id", "site_id", "period")
    }


def custom_of(company_id: int, ids: Collection[int]) -> dict[int, CustomView]:
    """그 회사의 직접입력 계수(S9·S11). 남의 회사 id 는 안 든다."""
    found: dict[int, CustomView] = {}
    for row in InventoryCustomFactor.for_company(company_id).filter(pk__in=list(ids)):
        found[row.pk] = CustomView(
            id=row.pk,
            name=row.name,
            source=row.source,
            base_year=row.base_year,
            tier=row.tier,
            country_code=row.country_code,
            industry_code=row.industry_code,
            input_unit=(row.input_unit_kind, row.input_unit),
            ncv=row.ncv,
            ncv_unit=(row.ncv_unit_kind, row.ncv_unit) if row.ncv_unit_kind and row.ncv_unit else None,
            factor_unit=row.factor_unit,
            gases=gases_of(row.gases),
            note=row.note,
            created_at=row.created_at,
        )
    return found


def year_rows(company_id: int, years: Collection[int], *, node_id: int | None = None) -> list[EmissionLine]:
    """그 해들의 숨기지 않은·삭제 안 된 선택의 살아 있는 행 배출량(리스트·상세 합의 재료). node_id 면 그 잎만."""
    rows = InventoryEntryRow.for_company(company_id).filter(
        deleted_at__isnull=True,
        selection__deleted_at__isnull=True,
        selection__hidden=False,
        selection__inventory_year__year__in=list(years),
    )
    if node_id is not None:
        rows = rows.filter(selection__facility_node_id=node_id)
    lines = rows.values_list(
        "selection__inventory_year__year",
        "selection__facility_node_id",
        "site_facility__site_id",
        "emission",
        "emission_problem",  # S12a-3
    )
    return [EmissionLine(*line) for line in lines]


def estimated_lines(company_id: int, year_id: int) -> list[EstimatedLine]:
    """그 해 살아 있는 행의 추정 표시 값 칸(리스트의 행 추정 — 스펙-1 S2 [우리 해석]). 켠 사업장·블록 주기 칸으로
    거르는 것은 actions(470 M4 — 여기는 조직구조를 모른다)."""
    values = InventoryEntryValue.for_company(company_id).filter(
        estimated=True,
        row__deleted_at__isnull=True,
        row__selection__deleted_at__isnull=True,
        row__selection__inventory_year_id=year_id,
    )
    lines = values.values_list(
        "row__selection__facility_node_id", "row__site_facility__site_id", "row__selection_id", "slot"
    )
    return [EstimatedLine(*line) for line in lines]


def years_of(company_id: int) -> list[tuple[int, bool]]:
    """그 회사의 해 — (해, 숨기지 않은·삭제 안 된 선택이 있음). 새 해 먼저."""
    found = list(InventoryYear.for_company(company_id).order_by("-year").values_list("id", "year"))
    chosen = CompanyIndexSelection.for_company(company_id).filter(
        inventory_year_id__in=[year_id for year_id, _ in found], deleted_at__isnull=True, hidden=False
    )
    configured = frozenset(chosen.values_list("inventory_year_id", flat=True))
    return [(year, year_id in configured) for year_id, year in found]


def decimals_of(company_id: int, year_id: int) -> int:
    """그 해의 표시 자릿수(해 행이 있어야 한다 — 부르는 쪽이 year_of 로 본 뒤)."""
    found = InventoryYear.for_company(company_id).filter(pk=year_id).values_list("decimals", flat=True).first()
    if found is None:
        raise LookupError(f"inventory_years {year_id} 가 없다")
    return found


def sites_in_use(company_id: int, site_ids: Collection[int]) -> frozenset[int]:
    """사업장 가운데 살아 있는 입력 행이 그 자산/시설을 가리키는 것(숨긴 선택 포함 — 판단 1)."""
    rows = InventoryEntryRow.for_company(company_id).filter(
        deleted_at__isnull=True, site_facility__site_id__in=list(site_ids)
    )
    return frozenset(rows.values_list("site_facility__site_id", flat=True))


def facilities_in_use(company_id: int, ids: Collection[int]) -> frozenset[int]:
    """자산/시설 가운데 살아 있는 입력 행이 가리키는 것(숨긴 선택 포함 — 판단 1)."""
    rows = InventoryEntryRow.for_company(company_id).filter(deleted_at__isnull=True, site_facility_id__in=list(ids))
    return frozenset(rows.values_list("site_facility_id", flat=True))
