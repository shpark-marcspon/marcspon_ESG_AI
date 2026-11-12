"""Scope 3 카테고리 잠금 표의 쓰기. 밴드 S3K2a ①(발주서 Q8). HTTP 를 모른다.

표 하나: 함수마다 `with transaction.atomic()` 블록 하나. 회사 칸 표는 `Scope3CategoryState.for_company(company_id)` 로만
연다(읽기는 selectors).
★ 첫 잠금 경합(Q8): 행이 없으면 FOR UPDATE 가 막을 것이 없다. 그래서 걸기는 먼저 ensure_row 로 빈 행(셋 칸 NULL)을
  두고, 그다음 selectors.lock_row 로 다시 읽는다. 두 걸기가 겹치면 둘째의 INSERT 는 첫째의 커밋을 기다렸다가 유일 제약
  (inventory_scope3_categories_unique)에 걸린다 — 저장점(블록) 안이라 그 위반만 「이미 있음」으로 삼키고 바깥 트랜잭션은
  산다. 행 하나·500 0. 모르는 제약(CHECK 등)은 다시 던진다(500 — index_selection.create_year 꼴).
  bulk_create(ignore_conflicts) 대신 이 꼴인 까닭: 모델 생성자를 제품 코드에서 부르지 않는다(isolation 의
  CONSTRUCTOR_ALLOWED 에 새 항목 0 — 7a C0-design ①).
★ 지우기 0(앱 역할에 DELETE 없음). 풀기는 셋 칸을 비운다.
"""

from datetime import datetime

from django.db import IntegrityError, transaction

from esgapi.inventory.models import Scope3CategoryState
from esgapi.inventory.service.services.ghg_pool import constraint_name

_UNIQUE = ("inventory_scope3_categories_unique",)


def ensure_row(company_id: int, year: int, category: str) -> None:
    """(해, 카테고리) 빈 행을 둔다 — 이미 있으면(경합으로 먼저 선 것 포함) 아무것도 안 한다."""
    try:
        with transaction.atomic():
            Scope3CategoryState.for_company(company_id).create(year=year, category=category)
    except IntegrityError as exc:
        if constraint_name(exc) in _UNIQUE:
            return
        raise


def set_lock(company_id: int, row_id: int, *, locked_at: datetime, user_id: int, run_id: int) -> None:
    """그 행을 잠근다(잠근 때·사람·핀 실행)."""
    with transaction.atomic():
        Scope3CategoryState.for_company(company_id).filter(pk=row_id).update(
            locked_at=locked_at, locked_by_user_id=user_id, pinned_run_id=run_id
        )


def clear_lock(company_id: int, row_id: int) -> None:
    """그 행의 잠금 셋 칸을 비운다(행은 남는다 — 빈 행 = 안 잠김)."""
    with transaction.atomic():
        Scope3CategoryState.for_company(company_id).filter(pk=row_id).update(
            locked_at=None, locked_by_user_id=None, pinned_run_id=None
        )
