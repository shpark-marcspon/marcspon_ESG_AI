"""Scope 3 줄 편집 사건 표의 쓰기. 밴드 S3K2b-1 ①(결정 MARC-ENT-570, 발주서 Q9). HTTP 를 모른다.

표 하나: 함수마다 `with transaction.atomic()` 블록 하나. 회사 칸 표는 `Scope3RowEdit.for_company(company_id)` 로만 연다
(읽기는 selectors). 앱 역할은 SELECT·INSERT 만이다 — 고쳐 쓰기·지우기 0, 복구도 새 사건이다.
★ 묶어 넣기(bulk_create 한 번 — 2,000줄이 FOR UPDATE 쥔 채 1초 가까이 걸려 플랫폼-서버 7a 가 허락): 생성자는 add_events
  한 함수 안, 만든 행은 같은 자리에서 for_company(company_id).bulk_create 로만 넣는다(매니저가 줄마다 회사를 확인한다).
  isolation 의 CONSTRUCTOR_ALLOWED 에 이 파일 하나. .save()·objects.bulk_create·ignore_conflicts 0.
★ 계수 사건(S3K2b-2)도 같은 자리다 — 생성자를 늘리지 않는다(561 L2 단언이 지킨다).
"""

from collections.abc import Sequence
from uuid import UUID

from django.db import transaction

from esgapi.inventory.models import Scope3RowEdit
from esgapi.inventory.service.utils.entries import Actor
from esgapi.inventory.service.utils.scope3_edits import EditKind, Event
from esgapi.inventory.service.utils.scope3_factors import Factor


def _factor_columns(factor: Factor | None) -> dict[str, object]:
    if factor is None:
        return {}
    return {
        "factor_choice": factor.choice,
        "factor_rank": factor.rank,
        "factor_title": factor.title,
        "factor_value": factor.value,
        "factor_source": factor.source,
        "factor_unit": factor.unit,
        "co2e": factor.co2e,
        "biogenic_co2e": factor.biogenic_co2e,
        "ai_factor_title": factor.ai.title,
        "ai_factor_value": factor.ai.value,
        "ai_factor_source": factor.ai.source,
        "ai_co2e": factor.ai.co2e,
    }


def add_events(
    company_id: int,
    run_id: int,
    category: str,
    kind: EditKind,
    reason: str,
    actor: Actor,
    row_ids: Sequence[str],
    batch_id: UUID,
    factor: Factor | None = None,
) -> list[Event]:
    """줄마다 사건 하나. batch_id 는 부르는 쪽이 요청마다 하나 — 한 요청의 사건을 묶는다. factor 는 kind factor 일 때만.
    쓴 사건을 돌려준다(응답이 다시 읽지 않게 — 561 L4)."""
    with transaction.atomic():
        made = Scope3RowEdit.for_company(company_id).bulk_create(
            [
                Scope3RowEdit(
                    company_id=company_id,
                    run_id=run_id,
                    category=category,
                    row_id=row_id,
                    kind=kind,
                    reason=reason,
                    actor_kind=actor.kind,
                    actor_user_id=actor.user_id,
                    batch_id=batch_id,
                    **_factor_columns(factor),
                )
                for row_id in row_ids
            ]
        )
    return [
        Event(
            id=line.pk,
            run_id=run_id,
            category=category,
            row_id=line.row_id,
            kind=kind,
            reason=reason,
            at=line.created_at,
            actor_user_id=actor.user_id,
            batch_id=str(batch_id),
            factor=factor,
        )
        for line in made
    ]
