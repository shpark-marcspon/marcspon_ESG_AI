"""Scope 3 줄 편집 사건 표(inventory_scope3_row_edits)의 읽기. 밴드 S3K2b-1 ①(결정 MARC-ENT-570). 쓰지 않는다.

★ 조회마다 회사 조건을 적는다(`Scope3RowEdit.for_company(company_id)`). 회사 id 는 부르는 쪽(인증 주체·작업 회사)이 정한
  것이다. 실행 id 는 외래 키가 아니다(MARC-ENT-210) — 남의 실행 id 로 불러도 그 회사 행만 나온다.
"""

from collections.abc import Collection
from typing import Any, Final, cast

from esgapi.inventory.models import Scope3RowEdit
from esgapi.inventory.service.utils.scope3_edits import EditKind, Event
from esgapi.inventory.service.utils.scope3_factors import Ai, Choice, Factor

_FIELDS: Final = (
    "id",
    "run_id",
    "category",
    "row_id",
    "kind",
    "reason",
    "created_at",
    "actor_user_id",
    "batch_id",
    "factor_choice",
    "factor_rank",
    "factor_title",
    "factor_value",
    "factor_source",
    "factor_unit",
    "co2e",
    "biogenic_co2e",
    "ai_factor_title",
    "ai_factor_value",
    "ai_factor_source",
    "ai_co2e",
)


def _factor(line: tuple[Any, ...]) -> Factor | None:
    choice, rank, title, value, source, unit, co2e, biogenic, ai_title, ai_value, ai_source, ai_co2e = line
    if choice is None:
        return None
    ai = Ai(title=ai_title, value=ai_value, source=ai_source, co2e=ai_co2e)
    return Factor(cast("Choice", choice), rank, title, value, source, unit, co2e, biogenic, ai)


def _event(line: tuple[object, ...]) -> Event:
    id_, run_id, category, row_id, kind, reason, at, user_id, batch_id, *factor = cast("tuple[Any, ...]", line)
    return Event(
        id=id_,
        run_id=run_id,
        category=category,
        row_id=row_id,
        kind=cast("EditKind", kind),
        reason=reason,
        at=at,
        actor_user_id=user_id,
        batch_id=None if batch_id is None else str(batch_id),
        factor=_factor(tuple(factor)),
    )


def events_of(company_id: int, run_ids: Collection[int]) -> list[Event]:
    """그 실행들의 사건 전부 — id 차례(쿼리 하나, run_ids 가 비면 0)."""
    if not run_ids:
        return []
    rows = Scope3RowEdit.for_company(company_id).filter(run_id__in=run_ids).order_by("id")
    return [_event(line) for line in rows.values_list(*_FIELDS)]


def history_page(
    company_id: int, run_id: int, row_id: str | None, *, offset: int, limit: int
) -> tuple[int, list[Event]]:
    """그 실행의 사건 — 새 것 먼저(id 내림). row_id 를 주면 그 줄만. (자르기 전 수, 쪽)."""
    rows = Scope3RowEdit.for_company(company_id).filter(run_id=run_id)
    if row_id is not None:
        rows = rows.filter(row_id=row_id)
    page = rows.order_by("-id").values_list(*_FIELDS)[offset : offset + limit]
    return rows.count(), [_event(line) for line in page]
