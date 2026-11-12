"""Scope 1·2 입력 행·값·히스토리와 선택 행의 메모·잠금 칸의 쓰기. 밴드 S12a ②. HTTP 를 모른다.

표 하나씩: 함수마다 `with transaction.atomic()` 블록 하나(여러 표는 actions 의 @transaction.atomic 이 이 함수들을 한
트랜잭션에서 부른다 — TWO_TABLE_FUNCTIONS 0). 회사 칸 표는 `<표>.for_company(company_id)` 로만 연다(읽지 않는다 —
읽기는 selectors). 행마다 `.create()`(bulk_create 0 — 회사 칸을 매니저가 채운다).
★ 제약 경합(IntegrityError)은 제약 이름으로 가린다(발주서 2-8): 살아 있는 행 겹침(inventory_entry_rows_unique_alive)만
  갈래(RowTaken)로 바꾸고, 나머지(짝 키·값 겹침·CHECK)는 판정·lock_selection 이 먼저 막으므로 다시 던진다(500).
  try 는 블록 **바깥**이다(블록이 저장점이라 바깥 트랜잭션은 산다).
★ 지우기는 삭제 표시(앱 역할에 DELETE 없음 · 값·히스토리 그대로). 히스토리·직접입력 계수는 넣기만(앱 역할
  SELECT·INSERT). 주기 행은 넣거나 고친다(S12a-2 — 옛 주기 칸 값은 그대로 남는다, 판단 E).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from esgapi.inventory.models import (
    CompanyIndexSelection,
    InventoryCustomFactor,
    InventoryEntryHistory,
    InventoryEntryPeriod,
    InventoryEntryRow,
    InventoryEntryValue,
)
from esgapi.inventory.service.services.ghg_pool import constraint_name
from esgapi.inventory.service.utils.entries import Actor, custom_gases
from esgapi.inventory.service.utils.ghg_pool import FactorValues

_ROW_UNIQUE = ("inventory_entry_rows_unique_alive",)


@dataclass(frozen=True)
class RowTaken:
    """같은 선택·자산/시설의 살아 있는 행이 경합으로 먼저 섰다(부르는 쪽이 422 로 다시 불러 저장하게 한다)."""


@dataclass(frozen=True)
class NewRow:
    site_facility_id: int
    unit: str
    na: bool


@dataclass(frozen=True)
class RowFigures:
    """행의 셈 칸(단위·N/A·배출량·셈 못 한 까닭)."""

    row_id: int
    unit: str
    na: bool
    emission: Decimal | None
    emission_problem: str | None


@dataclass(frozen=True)
class ValueWrite:
    """값 한 칸. value_id None = 새 칸(create), 아니면 그 칸을 고친다."""

    row_id: int
    slot: str
    amount: Decimal | None
    estimated: bool
    value_id: int | None = None


@dataclass(frozen=True)
class HistoryWrite:
    row_id: int
    kind: str
    slot: str | None
    before: str | None
    after: str | None
    unit: str
    actor_kind: str
    actor_user_id: int
    reason: str | None = None  # S12a-2: 계수 바꿈·복구의 사유
    before_version_id: int | None = None  # S12a-2: factor 줄의 앞뒤(판 또는 직접입력 하나씩 — CHECK)
    after_version_id: int | None = None
    before_custom_id: int | None = None
    after_custom_id: int | None = None


def insert_rows(company_id: int, selection_id: int, rows: Sequence[NewRow]) -> list[int] | RowTaken:
    """새 입력 행들(셈 칸은 비움 — update_rows 가 채운다). 만든 id(rows 차례)."""
    try:
        with transaction.atomic():
            table = InventoryEntryRow.for_company(company_id)
            made = [
                table.create(selection_id=selection_id, site_facility_id=row.site_facility_id, unit=row.unit, na=row.na)
                for row in rows
            ]
    except IntegrityError as exc:
        if constraint_name(exc) in _ROW_UNIQUE:
            return RowTaken()
        raise
    return [row.pk for row in made]


def update_rows(company_id: int, rows: Sequence[RowFigures]) -> int:
    """행의 단위·N/A·셈 칸을 고친다(살아 있는 행만). 바꾼 수."""
    changed = 0
    now = timezone.now()
    with transaction.atomic():
        for row in rows:
            changed += (
                InventoryEntryRow.for_company(company_id)
                .filter(pk=row.row_id, deleted_at__isnull=True)
                .update(
                    unit=row.unit,
                    na=row.na,
                    emission=row.emission,
                    emission_problem=row.emission_problem,
                    updated_at=now,
                )
            )
    return changed


def upsert_values(company_id: int, values: Sequence[ValueWrite]) -> int:
    """값 칸을 넣거나 고친다. 같은 칸 겹침(inventory_entry_values_unique)은 lock_selection 이 막는다 — 다시 던진다."""
    now = timezone.now()
    with transaction.atomic():
        table = InventoryEntryValue.for_company(company_id)
        for value in values:
            if value.value_id is None:
                table.create(row_id=value.row_id, slot=value.slot, amount=value.amount, estimated=value.estimated)
            else:
                InventoryEntryValue.for_company(company_id).filter(pk=value.value_id).update(
                    amount=value.amount, estimated=value.estimated, updated_at=now
                )
    return len(values)


def insert_history(company_id: int, lines: Sequence[HistoryWrite]) -> int:
    """히스토리 줄들(넣기만 — 고치지 않는다). 넣은 수."""
    with transaction.atomic():
        table = InventoryEntryHistory.for_company(company_id)
        for line in lines:
            table.create(
                row_id=line.row_id,
                kind=line.kind,
                slot=line.slot,
                before=line.before,
                after=line.after,
                unit=line.unit,
                actor_kind=line.actor_kind,
                actor_user_id=line.actor_user_id,
                reason=line.reason,
                before_version_id=line.before_version_id,
                after_version_id=line.after_version_id,
                before_custom_id=line.before_custom_id,
                after_custom_id=line.after_custom_id,
            )
    return len(lines)


def upsert_period(company_id: int, selection_id: int, site_id: int, period: str) -> int:
    """블록(선택 × 사업장)의 입력주기를 넣거나 고친다(S7). (selection, site) 겹침(inventory_entry_periods_unique)은
    lock_selection·lock_branch 가 줄 세워 막는다 — 다시 던진다(발주서 2-7)."""
    with transaction.atomic():
        table = InventoryEntryPeriod.for_company(company_id)
        changed = table.filter(selection_id=selection_id, site_id=site_id).update(
            period=period, updated_at=timezone.now()
        )
        if not changed:
            table.create(selection_id=selection_id, site_id=site_id, period=period)
    return 1


def insert_custom(company_id: int, values: FactorValues, actor: Actor) -> int:
    """행 전용 직접입력 계수 하나(S9·S11 — 넣기만, 고치지 않는다). 가스는 check_factor 를 지난 값의 글자(판단 B).
    만든 id."""
    ncv_unit = values.ncv_unit
    with transaction.atomic():
        made = InventoryCustomFactor.for_company(company_id).create(
            name=values.name,
            source=values.source,
            base_year=values.base_year,
            tier=values.tier,
            country_code=values.country_code,
            industry_code=values.industry_code,
            input_unit_kind=values.input_unit[0],
            input_unit=values.input_unit[1],
            ncv_enabled=values.ncv is not None,
            ncv=values.ncv,
            ncv_unit_kind=None if ncv_unit is None else ncv_unit[0],
            ncv_unit=None if ncv_unit is None else ncv_unit[1],
            factor_unit=values.factor_unit,
            note=values.note,
            gases=custom_gases(values.gases),
            actor_kind=actor.kind,
            actor_user_id=actor.user_id,
        )
    return made.pk


def set_row_factor(company_id: int, row_id: int, *, version_id: int | None, custom_id: int | None) -> int:
    """행의 계수 덮어쓰기 칸 둘(많아야 하나 — CHECK inventory_entry_rows_one_factor). 둘 다 None = 선택의 잡은 판.
    살아 있는 행만. 바꾼 수."""
    with transaction.atomic():
        return (
            InventoryEntryRow.for_company(company_id)
            .filter(pk=row_id, deleted_at__isnull=True)
            .update(factor_version_id=version_id, custom_factor_id=custom_id, updated_at=timezone.now())
        )


def mark_rows_deleted(company_id: int, ids: Collection[int]) -> int:
    """입력 행을 삭제 표시한다(값·히스토리 그대로). 바꾼 수."""
    if not ids:
        return 0
    now = timezone.now()
    with transaction.atomic():
        return (
            InventoryEntryRow.for_company(company_id)
            .filter(pk__in=list(ids), deleted_at__isnull=True)
            .update(deleted_at=now, updated_at=now)
        )


def set_memo(company_id: int, selection_id: int, memo: str) -> int:
    """선택 행의 메모(인덱스 메모 — 판단 3). 바꾼 수."""
    with transaction.atomic():
        return (
            CompanyIndexSelection.for_company(company_id)
            .filter(pk=selection_id, deleted_at__isnull=True)
            .update(memo=memo, updated_at=timezone.now())
        )


def set_lock(company_id: int, selection_id: int, *, locked_by_user_id: int | None, at: datetime | None = None) -> int:
    """선택 행의 잠금 칸 둘을 같이 켜거나(사람 id) 끈다(None — CHECK inventory_selections_lock_pair). 바꾼 수."""
    now = timezone.now()
    locked_at = None if locked_by_user_id is None else (at or now)
    with transaction.atomic():
        return (
            CompanyIndexSelection.for_company(company_id)
            .filter(pk=selection_id, deleted_at__isnull=True)
            .update(locked_at=locked_at, locked_by_user_id=locked_by_user_id, updated_at=now)
        )
