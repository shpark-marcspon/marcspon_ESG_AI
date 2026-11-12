"""인벤토리 해·고객사 인덱스 선택(회사 범위 표 둘)의 읽기. 밴드 K1b-2b ②. 쓰지 않는다.

★ 조회마다 회사 조건을 적는다(`InventoryYear.for_company(company_id)`·`CompanyIndexSelection.for_company(company_id)`).
  회사 id 는 부르는 쪽이 정한 것이다(고객사 사용자는 주체의 회사, 운영 관리자는 core/auth/bearer.py 의 company_of 가
  고른 작업 회사). 무효 조건: 그 값이 틀리면 그 틀린 회사로 가른다.
★ 행 잠금은 여기만(lock_year — 같은 회사·해의 저장 둘을 줄 세운다 · lock_selection — S12a: 한 인덱스의 입력·지움·
  메모·잠금을 줄 세운다. 잠김 판정은 이 잠금 아래에서 한다).
★ selections_with_data(S12a ②) = 그 잎의 선택에 삭제 안 된 입력 행이 있음(값 유무 무관 — 발주서 판단 1).
★ 회사를 넘는 읽기는 둘뿐이다(K1b-2b ④ — MARC-ISSUE-432): nodes_in_use·factors_in_use 가 모델의 이름 붙은 입구
  (CompanyIndexSelection.used_node_ids·used_factor_ids · S12a-2 InventoryEntryRow.used_factor_ids — 결정 MARC-ENT-487)를
  부른다. 돌려주는 것은 풀 id 집합뿐이다
  (회사 id·행 0 — 운영 관리자의 풀 지우기·고치기 판정용). .unscoped 0.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from esgapi.inventory.models import CompanyIndexSelection, InventoryEntryRow, InventoryYear
from esgapi.inventory.service.utils.index_selection import Chosen


@dataclass(frozen=True)
class SelectionState:
    """입력 쪽이 보는 선택 한 줄(S12a): 잡은 판 · 숨김 · 메모 · 잠금."""

    id: int
    factor_version_id: int
    hidden: bool
    memo: str
    locked_at: datetime | None
    locked_by_user_id: int | None


_STATE_FIELDS = ("id", "factor_version_id", "hidden", "memo", "locked_at", "locked_by_user_id")


def year_of(company_id: int, year: int) -> int | None:
    """그 회사의 그 해 행 id(없으면 None)."""
    return InventoryYear.for_company(company_id).filter(year=year).values_list("id", flat=True).first()


def lock_year(company_id: int, year: int) -> int | None:
    """그 회사의 그 해 행을 잠근다(블록 안에서만 부른다). 같은 해의 저장 둘이 여기서 줄을 선다."""
    row = InventoryYear.for_company(company_id).select_for_update().filter(year=year).first()
    return None if row is None else row.pk


def selections_of(company_id: int, year_id: int) -> dict[int, Chosen]:
    """그 해의 삭제 안 된 선택 — 잎 id → (선택 id, 잡은 판 id, 숨김)."""
    rows = CompanyIndexSelection.for_company(company_id).filter(inventory_year_id=year_id, deleted_at__isnull=True)
    return {
        node_id: Chosen(id=row_id, factor_version_id=version_id, hidden=hidden)
        for row_id, node_id, version_id, hidden in rows.values_list(
            "id", "facility_node_id", "factor_version_id", "hidden"
        )
    }


def nodes_in_use(ids: Collection[int]) -> frozenset[int]:
    """풀 잎 가운데 어느 회사든 고른 것(숨김 포함 · 삭제 표시 빼고). 풀 id 만."""
    return CompanyIndexSelection.used_node_ids(ids)


def factors_in_use(ids: Collection[int]) -> frozenset[int]:
    """풀 계수 가운데 어느 회사든 판을 잡은 것(선택 — 숨김 포함 · 삭제 표시 빼고) 또는 살아 있는 입력 행이 덮어쓴 것
    (S12a-2 — 히스토리 줄은 막지 않는다, 감독 길 i). 풀 id 만."""
    return CompanyIndexSelection.used_factor_ids(ids) | InventoryEntryRow.used_factor_ids(ids)


def selections_with_data(company_id: int, year_id: int, node_ids: Collection[int]) -> frozenset[int]:
    """잎 가운데 그 해의 삭제 안 된 선택에 삭제 안 된 입력 행이 있는 것(S17 저장이 뺀 잎을 지우지 않고 숨긴다)."""
    rows = InventoryEntryRow.for_company(company_id).filter(
        deleted_at__isnull=True,
        selection__deleted_at__isnull=True,
        selection__inventory_year_id=year_id,
        selection__facility_node_id__in=list(node_ids),
    )
    return frozenset(rows.values_list("selection__facility_node_id", flat=True))


def selection_of(company_id: int, year_id: int, node_id: int) -> SelectionState | None:
    """그 해·잎의 삭제 안 된 선택(숨김 포함). 없으면 None."""
    rows = CompanyIndexSelection.for_company(company_id).filter(
        inventory_year_id=year_id, facility_node_id=node_id, deleted_at__isnull=True
    )
    line = rows.values_list(*_STATE_FIELDS).first()
    return None if line is None else SelectionState(*line)


def selection_states(company_id: int, year_id: int) -> dict[int, SelectionState]:
    """그 해의 삭제 안 된 선택 전부 — 잎 id → 입력 쪽 보기(리스트의 메모·잠금 칸)."""
    rows = CompanyIndexSelection.for_company(company_id).filter(inventory_year_id=year_id, deleted_at__isnull=True)
    return {line[0]: SelectionState(*line[1:]) for line in rows.values_list("facility_node_id", *_STATE_FIELDS)}


def lock_selection(company_id: int, year_id: int, node_id: int) -> SelectionState | None:
    """그 해·잎의 삭제 안 된 선택을 잠근다(블록 안에서만 — 입력 저장은 lock_year 뒤). 없으면 None."""
    row = (
        CompanyIndexSelection.for_company(company_id)
        .select_for_update()
        .filter(inventory_year_id=year_id, facility_node_id=node_id, deleted_at__isnull=True)
        .first()
    )
    if row is None:
        return None
    return SelectionState(
        id=row.pk,
        factor_version_id=row.factor_version_id,
        hidden=row.hidden,
        memo=row.memo,
        locked_at=row.locked_at,
        locked_by_user_id=row.locked_by_user_id,
    )
