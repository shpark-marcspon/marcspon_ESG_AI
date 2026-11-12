"""인벤토리 해·고객사 인덱스 선택의 쓰기. 밴드 K1b-2b ②. HTTP 를 모른다.

표 하나씩: 함수마다 `with transaction.atomic()` 블록 하나(두 표는 actions 의 @transaction.atomic 이 이 함수들을 한
트랜잭션에서 부른다 — TWO_TABLE_FUNCTIONS 0). 회사 칸 표는 `<표>.for_company(company_id)` 로만 연다(읽지 않는다 —
읽기는 selectors).
★ 제약 경합(IntegrityError)은 제약 이름으로 가려 갈래로 바꾼다(모르는 제약은 다시 던진다 — 500). try 는 블록
  **바깥**이다(블록이 저장점이라 바깥 트랜잭션은 산다).
★ 지우기는 삭제 표시(앱 역할에 DELETE 없음). 지운 행은 숨기지 않는다(inventory_selections_hidden_alive).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from esgapi.inventory.models import CompanyIndexSelection, InventoryYear
from esgapi.inventory.service.services.ghg_pool import constraint_name

_YEAR_UNIQUE = ("inventory_years_company_year_unique",)
_SELECTION_UNIQUE = ("inventory_selections_node_unique_alive",)


@dataclass(frozen=True)
class YearTaken:
    """같은 회사·해의 행이 경합으로 먼저 섰다(부르는 쪽이 다시 읽는다)."""


@dataclass(frozen=True)
class SelectionTaken:
    """같은 해·잎의 살아 있는 선택이 경합으로 먼저 섰다."""


@dataclass(frozen=True)
class NewSelection:
    facility_node_id: int
    factor_version_id: int


def create_year(company_id: int, year: int) -> int | YearTaken:
    """그 회사의 해 행 하나(decimals 는 모델 기본값). 만든 id."""
    try:
        with transaction.atomic():
            row = InventoryYear.for_company(company_id).create(year=year)
    except IntegrityError as exc:
        if constraint_name(exc) in _YEAR_UNIQUE:
            return YearTaken()
        raise
    return row.pk


def insert_selections(company_id: int, year_id: int, rows: Sequence[NewSelection]) -> int | SelectionTaken:
    """새 선택 행들 — 행마다 for_company(company_id).create(bulk_create 0). 넣은 수."""
    try:
        with transaction.atomic():
            selections = CompanyIndexSelection.for_company(company_id)
            for row in rows:
                selections.create(
                    inventory_year_id=year_id,
                    facility_node_id=row.facility_node_id,
                    factor_version_id=row.factor_version_id,
                )
    except IntegrityError as exc:
        if constraint_name(exc) in _SELECTION_UNIQUE:
            return SelectionTaken()
        raise
    return len(rows)


def set_hidden(company_id: int, ids: Collection[int], *, hidden: bool) -> int:
    """삭제 안 된 선택의 숨김을 켜거나 끈다(잡은 판 그대로). 바꾼 수."""
    if not ids:
        return 0
    with transaction.atomic():
        return (
            CompanyIndexSelection.for_company(company_id)
            .filter(pk__in=list(ids), deleted_at__isnull=True)
            .update(hidden=hidden, updated_at=timezone.now())
        )


def mark_selections_deleted(company_id: int, ids: Collection[int]) -> int:
    """선택을 삭제 표시한다(숨김은 끈다 — CHECK). 바꾼 수."""
    if not ids:
        return 0
    now = timezone.now()
    with transaction.atomic():
        return (
            CompanyIndexSelection.for_company(company_id)
            .filter(pk__in=list(ids), deleted_at__isnull=True)
            .update(hidden=False, deleted_at=now, updated_at=now)
        )


def set_decimals(company_id: int, year_id: int, decimals: int) -> int:
    """해의 표시 자릿수(S12a — 표시만, 저장값 그대로). 바꾼 수."""
    with transaction.atomic():
        return (
            InventoryYear.for_company(company_id)
            .filter(pk=year_id)
            .update(decimals=decimals, updated_at=timezone.now())
        )
