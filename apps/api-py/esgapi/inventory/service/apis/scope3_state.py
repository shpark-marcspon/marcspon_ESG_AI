"""Scope 3 연도 상태·카테고리 잠금 경로 셋(밴드 S3K2a ① — 결정 MARC-ENT-559·469 2). apis/inventory.py 가 이 router 를
/inventory 아래에 붙인다(config/api.py 0줄).

`L` = /scope3/years/{year}/categories/{category}/lock

    GET    /scope3/years/{year}  inventory_scope3_year_get  회사 업무(COMPANY)
    POST   L?runId=              inventory_scope3_lock      회사 업무(COMPANY)
    DELETE L                     inventory_scope3_unlock    운영 관리자만(OPERATOR — 작업 회사)

몸: service/actions/scope3_state.py. 「지금 결과」는 읽을 때 셈한다(잠겼으면 핀 실행, 아니면 그 해 만든 차례 마지막
done). 인증: [company_scoped_auth_or_next, session_cookie]. 풀기도 같은 인증이다 — permitted 가 고객사 주체를 403 으로
막고(DB 0) 운영 관리자만 company_of 에 닿는다(Scope 1·2 풀기 꼴). 차례: permitted(첫 문장) → company_of → actions.
오류: 해가 1990~2100 밖 422 `fields.year` · runId 빠짐·정수 아님 422 · 모르는 카테고리 404 `not_found` · runId 가 이
회사 실행이 아님(없음·남의 회사) 404 `not_found` · 셈한 시트 없는 카테고리 잠그기 409 `not_computed` · runId 가 지금
결과 실행이 아님 409 `stale_run` · 고객사가 풀기 403 `forbidden` · 운영 관리자에 회사 둘 400 `company_ambiguous`.
★ id 는 int 다. 테넌트 id 는 인증 주체(토큰)에서만 온다.
"""

from decimal import Decimal
from typing import Annotated

from django.http import HttpRequest
from ninja import Router
from ninja.params.functions import Query

from esgapi.core.auth.bearer import company_of, company_scoped_auth_or_next, permitted
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_ERROR_RESPONSES
from esgapi.inventory.service.actions import scope3_state as actions
from esgapi.inventory.service.schemas.scope3_state import (
    Scope3YearCategoryOut,
    Scope3YearCurrentOut,
    Scope3YearLatestOut,
    Scope3YearLockedByOut,
    Scope3YearOut,
)
from esgapi.inventory.service.utils.entries import Actor
from esgapi.inventory.service.utils.ghg_pool import Forbidden, Invalid, NotFound, decimal_text
from esgapi.user.service.apis.auth import session_cookie

router = Router(tags=["인벤토리 Scope 3"])
COMPANY_AUTH = [company_scoped_auth_or_next, session_cookie]
LOCK = "/scope3/years/{year}/categories/{category}/lock"
ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
RunIdQuery = Annotated[int, Query(description="잠글 때 사용자가 본 실행 id(그 카테고리의 지금 결과 실행이어야 한다)")]

NOT_FOUND = "그런 카테고리·실행이 없다"
NOT_COMPUTED = "셈한 시트가 없는 카테고리라 잠글 수 없다"
STALE = "그 실행은 이 카테고리의 지금 결과가 아니다 — 다시 불러 확인한다"
INVALID = "입력을 확인한다"


def refused(found: object) -> ApplicationError:
    match found:
        case Invalid(fields=fields):
            return ApplicationError(
                "validation", "validation_error", INVALID, fields={name: [why] for name, why in fields.items()}
            )
        case NotFound() | actions.RunNotFound():
            return ApplicationError("not_found", "not_found", NOT_FOUND)
        case actions.NotComputed():
            return ApplicationError("conflict", "not_computed", NOT_COMPUTED)
        case actions.StaleRun():
            return ApplicationError("conflict", "stale_run", STALE)
        case Forbidden():
            return ApplicationError("forbidden", "forbidden", found.message)
        case _:
            raise TypeError(f"모르는 갈래: {found!r}")


def _text(value: Decimal | None) -> str | None:
    return None if value is None else decimal_text(value)


def category_out(state: actions.CategoryState) -> Scope3YearCategoryOut:
    current = state.current
    return Scope3YearCategoryOut(
        category=state.category,
        current=None
        if current is None
        else Scope3YearCurrentOut(
            runId=str(current.run_id),
            total=_text(current.value.total),
            sheets=current.value.sheets,
            failedSheets=current.value.failed_sheets,
        ),
        locked=state.locked_at is not None,
        lockedAt=state.locked_at,
        lockedBy=None
        if state.locked_by is None
        else Scope3YearLockedByOut(id=str(state.locked_by[0]), name=state.locked_by[1]),
        editedRows=state.edited_rows,
    )


@router.get(
    "/scope3/years/{year}",
    operation_id="inventory_scope3_year_get",
    response={200: Scope3YearOut, **TOKEN_ERROR_RESPONSES},
    auth=COMPANY_AUTH,
)
def year_get(request: HttpRequest, year: int) -> Scope3YearOut:
    """그 해의 Scope 3 상태 — 기준 실행·가장 새 실행 · 카테고리 열넷의 지금 결과(잠겼으면 핀 실행)·잠금."""
    principal = permitted(request, "inventory_scope3_year_get")
    found = actions.year_state(company_of(principal), year)
    if isinstance(found, Invalid):
        raise refused(found)
    return Scope3YearOut(
        year=found.year,
        baseRunId=None if found.base_run_id is None else str(found.base_run_id),
        latest=None
        if found.latest is None
        else Scope3YearLatestOut.model_validate({"runId": str(found.latest[0]), "status": found.latest[1]}),
        categories=[category_out(state) for state in found.categories],
        editedRowsUnlocked=found.edited_rows_unlocked,
    )


@router.post(
    LOCK,
    operation_id="inventory_scope3_lock",
    response={200: Scope3YearCategoryOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def lock(request: HttpRequest, year: int, category: str, runId: RunIdQuery) -> Scope3YearCategoryOut:
    """카테고리를 잠근다(이미 잠겼으면 그대로 — 잠근 사람·때·핀 안 바뀜). runId 의 실행을 그 카테고리의 핀으로."""
    principal = permitted(request, "inventory_scope3_lock")
    actor = Actor(kind=principal.kind, user_id=int(principal.user_id))
    found = actions.lock(company_of(principal), year, category, runId, actor)
    if not isinstance(found, actions.CategoryState):
        raise refused(found)
    return category_out(found)


@router.delete(
    LOCK,
    operation_id="inventory_scope3_unlock",
    response={200: Scope3YearCategoryOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def unlock(request: HttpRequest, year: int, category: str) -> Scope3YearCategoryOut:
    """잠금을 푼다 — 운영 관리자만(작업 회사). 안 잠겼으면 그대로. 풀면 그 해 기준 실행으로 돌아간다."""
    principal = permitted(request, "inventory_scope3_unlock")
    found = actions.unlock(company_of(principal), year, category, actor_kind=principal.kind)
    if not isinstance(found, actions.CategoryState):
        raise refused(found)
    return category_out(found)
