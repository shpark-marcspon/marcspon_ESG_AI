"""Scope 3 카테고리 잠금 표(inventory_scope3_categories)의 읽기. 밴드 S3K2a ①. 쓰지 않는다.

★ 조회마다 회사 조건을 적는다(`Scope3CategoryState.for_company(company_id)`). 회사 id 는 부르는 쪽(인증 주체·작업
  회사)이 정한 것이다.
★ 행 잠금은 lock_row 하나(블록 안에서만 — 같은 (해, 카테고리)의 걸기·풀기를 줄 세운다. 잠김 판정은 이 잠금 아래에서).
★ 빈 행(셋 칸 NULL)은 안 잠김과 같다 — locks_of 는 잠긴 행만 준다.
"""

from dataclasses import dataclass
from datetime import datetime

from esgapi.inventory.models import Scope3CategoryState


@dataclass(frozen=True, slots=True)
class Lock:
    """잠긴 카테고리 하나: 잠근 때·사람(users.pk)·핀 실행 id."""

    locked_at: datetime
    locked_by_user_id: int
    pinned_run_id: int


@dataclass(frozen=True, slots=True)
class Row:
    """lock_row 가 잡은 행: id 와 잠금(안 잠겼으면 None)."""

    id: int
    lock: Lock | None


def _lock_of(row: Scope3CategoryState) -> Lock | None:
    if row.locked_at is None or row.locked_by_user_id is None or row.pinned_run_id is None:
        return None  # CHECK(lock_triple)로 셋은 같이 있거나 같이 없다
    return Lock(locked_at=row.locked_at, locked_by_user_id=row.locked_by_user_id, pinned_run_id=row.pinned_run_id)


def locks_of(company_id: int, year: int) -> dict[str, Lock]:
    """그 회사 그 해의 잠긴 카테고리 → 잠금(쿼리 하나)."""
    rows = Scope3CategoryState.for_company(company_id).filter(year=year, locked_at__isnull=False)
    found: dict[str, Lock] = {}
    for row in rows:
        lock = _lock_of(row)
        if lock is not None:
            found[row.category] = lock
    return found


def lock_row(company_id: int, year: int, category: str) -> Row | None:
    """그 (해, 카테고리) 행을 FOR UPDATE 로 읽는다(블록 안에서만). 행이 없으면 None."""
    row = Scope3CategoryState.for_company(company_id).select_for_update().filter(year=year, category=category).first()
    return None if row is None else Row(id=row.pk, lock=_lock_of(row))
