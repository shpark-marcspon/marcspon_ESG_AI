"""Scope 3 줄 덧판 경로 다섯(밴드 S3K2b-1 ①·S3K2b-2 ① — 결정 MARC-ENT-570·469 4). apis/inventory.py 가 이 router 를
/inventory 아래에 붙인다(config/api.py 0줄).

`E` = /scope3/runs/{run_id}

    POST E/categories/{category}/exclusions    inventory_scope3_rows_exclude  회사 업무(COMPANY)
    POST E/categories/{category}/restorations  inventory_scope3_rows_restore  회사 업무(COMPANY)
    POST E/categories/{category}/factors       inventory_scope3_row_factor    회사 업무(COMPANY)
    GET  E/edits                               inventory_scope3_edits_get     회사 업무(COMPANY)
    GET  E/history?rowId=&page=&pageSize=      inventory_scope3_history_get   회사 업무(COMPANY)

몸: service/actions/scope3_edits.py. 편집은 그 실행에만 매인다(570 — 새 실행에 안 따라옴). 결과 GET 본문은 편집을
덮지 않는다(결과는 AI 원안 그대로). 인증: [company_scoped_auth_or_next, session_cookie]. 차례: permitted(첫 문장) →
company_of → actions.
오류: 몸 422 `fields.rowIds`·`fields.reason` · 그 실행 그 카테고리 줄이 아님 422 `fields.rowIds` · 모르는 카테고리·없는
실행·남의 회사 실행·다른 모듈 실행 404 `not_found`(같은 바이트) · 잠긴 카테고리 409 `locked` · 지금 결과 실행이 아님 409
`stale_run` · 고칠 수 없는 줄(C12·C15·칸이 모자란 줄) 409 `factor_not_editable` · 운영 관리자에 회사 둘 400
`company_ambiguous` — 어느 거절이든 행 0.
★ id 는 int 다. 테넌트 id 는 인증 주체(토큰)에서만 온다.
"""

from typing import Annotated, Final

from django.http import HttpRequest
from ninja import Router
from ninja.params.functions import Query

from esgapi.core.auth.bearer import company_of, permitted
from esgapi.core.auth.principal import Principal
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES, page_number_page
from esgapi.inventory.service.actions import scope3_edits as actions
from esgapi.inventory.service.apis.scope3_state import COMPANY_AUTH, category_out, refused
from esgapi.inventory.service.schemas.scope3_edits import (
    Scope3RowEditAiOut,
    Scope3RowEditByOut,
    Scope3RowEditFactorIn,
    Scope3RowEditFactorOut,
    Scope3RowEditHistoryOut,
    Scope3RowEditHistoryPageOut,
    Scope3RowEditIn,
    Scope3RowEditOut,
    Scope3RowEditResultOut,
    Scope3RowEditsOut,
)
from esgapi.inventory.service.utils.entries import Actor, Locked
from esgapi.inventory.service.utils.ghg_pool import NotFound
from esgapi.inventory.service.utils.scope3_factors import Custom, Factor

router = Router(tags=["인벤토리 Scope 3"])
RUN: Final = "/scope3/runs/{run_id}"
ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
BODY_ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_BODY_ERROR_RESPONSES, 404: ErrorBody}
Page = Annotated[int, Query(ge=1, le=100_000)]  # 끝없는 OFFSET 0(apis/entries.py 의 Page 와 같다)
PageSize = Annotated[int, Query(ge=1, le=100)]

LOCKED: Final = "잠긴 카테고리다 — 운영 관리자가 풀어야 고칠 수 있다"
NOT_EDITABLE: Final = "이 줄은 계수를 고칠 수 없다"


def _refused(found: object) -> ApplicationError:
    if isinstance(found, Locked):
        return ApplicationError("conflict", "locked", LOCKED)
    if isinstance(found, actions.FactorNotEditable):
        return ApplicationError("conflict", "factor_not_editable", NOT_EDITABLE)
    return refused(found)


def _actor(principal: Principal) -> Actor:
    return Actor(kind=principal.kind, user_id=int(principal.user_id))


def _by(person: tuple[int, str] | None) -> Scope3RowEditByOut | None:
    return None if person is None else Scope3RowEditByOut(id=str(person[0]), name=person[1])


def _factor_out(factor: Factor | None) -> Scope3RowEditFactorOut | None:
    if factor is None:
        return None
    ai = factor.ai
    return Scope3RowEditFactorOut(
        choice=factor.choice,
        rank=factor.rank,
        title=factor.title,
        value=factor.value,
        source=factor.source,
        unit=factor.unit,
        co2e=factor.co2e,
        biogenicCo2e=factor.biogenic_co2e,
        ai=Scope3RowEditAiOut(title=ai.title, value=ai.value, source=ai.source, co2e=ai.co2e),
    )


def _row_out(row: actions.RowState) -> Scope3RowEditOut:
    return Scope3RowEditOut(
        rowId=row.row_id,
        category=row.category,
        excluded=row.excluded,
        factor=_factor_out(row.factor),
        editedAt=row.at,
        editedBy=_by(row.by),
    )


def _result(found: object) -> Scope3RowEditResultOut:
    if not isinstance(found, actions.EditResult):
        raise _refused(found)
    return Scope3RowEditResultOut(category=category_out(found.category), rows=[_row_out(row) for row in found.rows])


@router.post(
    RUN + "/categories/{category}/exclusions",
    operation_id="inventory_scope3_rows_exclude",
    response={200: Scope3RowEditResultOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def rows_exclude(request: HttpRequest, run_id: int, category: str, body: Scope3RowEditIn) -> Scope3RowEditResultOut:
    """그 카테고리 지금 결과 실행의 줄들을 사유와 함께 산정에서 뺀다. 이미 빠진 줄은 건너뛴다."""
    principal = permitted(request, "inventory_scope3_rows_exclude")
    return _result(
        actions.exclude(company_of(principal), run_id, category, body.rowIds, body.reason, _actor(principal))
    )


@router.post(
    RUN + "/categories/{category}/restorations",
    operation_id="inventory_scope3_rows_restore",
    response={200: Scope3RowEditResultOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def rows_restore(request: HttpRequest, run_id: int, category: str, body: Scope3RowEditIn) -> Scope3RowEditResultOut:
    """뺀 줄을 사유와 함께 되돌린다(새 사건). 빠져 있지 않은 줄은 건너뛴다."""
    principal = permitted(request, "inventory_scope3_rows_restore")
    return _result(
        actions.restore(company_of(principal), run_id, category, body.rowIds, body.reason, _actor(principal))
    )


@router.post(
    RUN + "/categories/{category}/factors",
    operation_id="inventory_scope3_row_factor",
    response={200: Scope3RowEditResultOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def row_factor(request: HttpRequest, run_id: int, category: str, body: Scope3RowEditFactorIn) -> Scope3RowEditResultOut:
    """지금 결과 실행의 줄 하나의 계수를 사유와 함께 고른다(적용·추천·직접 입력). AI 를 다시 부르지 않는다."""
    principal = permitted(request, "inventory_scope3_row_factor")
    custom = None if body.custom is None else Custom(body.custom.title, body.custom.value, body.custom.source)
    checked = actions.check_factor(body.rowId, body.choice, body.rank, custom, body.reason)
    return _result(actions.factor(company_of(principal), run_id, category, checked, _actor(principal)))


@router.get(
    RUN + "/edits",
    operation_id="inventory_scope3_edits_get",
    response={200: Scope3RowEditsOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def edits_get(request: HttpRequest, run_id: int) -> Scope3RowEditsOut:
    """그 실행에서 사건이 하나라도 있는 줄의 지금 상태(rowId 차례). 옛 실행도 읽는다."""
    principal = permitted(request, "inventory_scope3_edits_get")
    found = actions.edits(company_of(principal), run_id)
    if isinstance(found, NotFound):
        raise _refused(found)
    return Scope3RowEditsOut(runId=str(found.run_id), rows=[_row_out(row) for row in found.rows])


@router.get(
    RUN + "/history",
    operation_id="inventory_scope3_history_get",
    response={200: Scope3RowEditHistoryPageOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def history_get(
    request: HttpRequest, run_id: int, rowId: str | None = None, page: Page = 1, pageSize: PageSize = 20
) -> Scope3RowEditHistoryPageOut:
    """그 실행의 편집 사건(새 것 먼저). rowId 를 주면 그 줄만. 옛 실행도 읽는다."""
    principal = permitted(request, "inventory_scope3_history_get")
    found = actions.history(company_of(principal), run_id, rowId, offset=(page - 1) * pageSize, limit=pageSize)
    if isinstance(found, NotFound):
        raise _refused(found)
    results = [
        Scope3RowEditHistoryOut(
            id=str(line.id),
            rowId=line.row_id,
            category=line.category,
            kind=line.kind,
            reason=line.reason,
            at=line.at,
            by=_by(line.by),
            batchId=line.batch_id,
            factor=_factor_out(line.factor),
        )
        for line in found.lines
    ]
    return Scope3RowEditHistoryPageOut(**page_number_page(found.count, page, pageSize, results))
