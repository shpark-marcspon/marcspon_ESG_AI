"""inventory 의 Scope 1·2 입력 경로 열(S2 리스트·S3 상세·S12 히스토리). 밴드 S12a ③(결정 MARC-ENT-463·469 2·4).
service/apis/inventory.py 의 router 가 이 router 를 「""」 에 붙인다(config/api.py 0줄). 아래 경로는 /inventory 뒤의
것이다. `X` = /scope12/years/{year}/indexes/{node_id}(node_id = 공통 풀의 잎 id).

    GET    /scope12/years                       inventory_scope12_years           회사 업무(COMPANY)
    GET    /scope12/rows?year=&q=               inventory_scope12_rows            〃
    GET    X                                    inventory_scope12_index_detail    〃
    PUT    X/sites/{site_id}/rows               inventory_scope12_rows_save       〃
    POST   X/rows/delete                        inventory_scope12_rows_delete     〃
    PUT    X/memo                               inventory_scope12_memo_save       〃
    POST   X/lock                               inventory_scope12_lock            〃
    DELETE X/lock                               inventory_scope12_unlock          운영 관리자만(OPERATOR — 작업 회사)
    PUT    /scope12/years/{year}/decimals       inventory_scope12_decimals_save   회사 업무
    GET    X/rows/{row_id}/history?page=&pageSize=  inventory_scope12_row_history 〃
    PUT    X/sites/{site_id}/period             inventory_scope12_period_save     회사 업무(S12a-2 — S7)
    PUT    X/rows/{row_id}/factor               inventory_scope12_row_factor_save 운영 관리자만(S9·S11 — 작업 회사)
    POST   X/rows/{row_id}/history/{history_id}/restore  inventory_scope12_history_restore  회사 업무(S12 — 계수 줄은
                                                운영 관리자만: actions 가 row_factor_save 칸으로 다시 본다)

인증: [company_scoped_auth_or_next, session_cookie](회사 경로 — 고객사 사용자, 운영 관리자는 작업 회사로). 풀기도
같은 인증이다: permitted 가 고객사 주체를 403 으로 막고(DB 0) 운영 관리자만 company_of 에 닿는다. 계수 바꿈도 같은 꼴.
차례: permitted(첫 문장) → company_of(principal) → actions. 회사 id 는 인증 주체에서만(본문 companyId → 422).
판 id 는 요청에 없다 — 셈은 그 회사 선택 행이 잡은 판으로만. 경로는 models 를 import 하지 않는다
(`.importlinter` 계약 라).
오류: 해·선택·사업장·행이 없거나 남의 것·숨김·삭제 404 `not_found` · 칸 검사 422 `fields.<칸>`(rows.<i>.… · memo ·
decimals · q) · 잠긴 인덱스 쓰기 409 `locked` · 고객사가 풀기 403 `forbidden` · 운영 관리자에 회사 둘 400
`company_ambiguous` · 복구할 줄이 낡음(칸이 지금 주기 밖·단위 바뀜·지운 풀 계수) 409 `restore_stale` · 고객사가 계수
바꿈·계수 줄 복구 403 `forbidden` — 어느 거절이든 행 0.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated

from django.http import HttpRequest
from ninja import Router
from ninja.params.functions import Query

from esgapi.core.auth.bearer import company_of, company_scoped_auth_or_next, permitted
from esgapi.core.auth.principal import Principal
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES, page_number_page
from esgapi.inventory.service.actions import entries as actions
from esgapi.inventory.service.schemas.entries import (
    EntryCountOut,
    EntryCustomFactorOut,
    EntryDecimalsIn,
    EntryDecimalsOut,
    EntryFacilityOut,
    EntryFactorOut,
    EntryFactorRefOut,
    EntryHistoryActorOut,
    EntryHistoryOut,
    EntryHistoryPageOut,
    EntryIdsIn,
    EntryIndexOut,
    EntryListRowOut,
    EntryLockedByOut,
    EntryMemoIn,
    EntryMemoOut,
    EntryPeriodIn,
    EntryRestoreIn,
    EntryRowFactorIn,
    EntryRowOut,
    EntryRowsOut,
    EntrySaveIn,
    EntryScopeOut,
    EntrySiteOut,
    EntrySiteTotalOut,
    EntrySlotOut,
    EntryTotalsOut,
    EntryYearOut,
    EntryYearsOut,
)
from esgapi.inventory.service.schemas.ghg_pool import GhgFactorIn, GhgGasOut, GhgUnitIn, GhgUnitOut
from esgapi.inventory.service.utils.entries import (
    Actor,
    CustomView,
    FactorRef,
    IndexDetail,
    Locked,
    RestoreStale,
    RowInput,
    RowView,
    SlotInput,
)
from esgapi.inventory.service.utils.ghg_pool import (
    FactorDraft,
    FactorView,
    Forbidden,
    GasDraft,
    GasValues,
    Invalid,
    NotFound,
    decimal_text,
)
from esgapi.user.service.apis.auth import session_cookie

router = Router(tags=["Scope 1·2 입력"])
COMPANY_AUTH = [company_scoped_auth_or_next, session_cookie]
INDEX = "/scope12/years/{year}/indexes/{node_id}"
Page = Annotated[int, Query(ge=1, le=100_000)]  # 끝없는 OFFSET 0(organization 의 Page 와 같다)
PageSize = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str | None, Query(max_length=actions.Q_MAX)]
ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
BODY_ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_BODY_ERROR_RESPONSES, 404: ErrorBody}

NOT_FOUND = "그런 해·인덱스·사업장·행이 없다"
LOCKED = "잠긴 인덱스라 바꿀 수 없다"
INVALID = "입력을 확인한다"
STALE = "그 줄의 뒤 상태로 되돌릴 수 없다 — 칸·단위·계수가 바뀌었다"


def _refused(found: object) -> ApplicationError:
    """actions 의 거절 갈래 → 오류. 갈래가 아니면 부른 쪽이 잘못 넘긴 것이다."""
    match found:
        case NotFound():
            return ApplicationError("not_found", "not_found", NOT_FOUND)
        case Invalid(fields=fields):
            return ApplicationError(
                "validation", "validation_error", INVALID, fields={name: [why] for name, why in fields.items()}
            )
        case Locked():
            return ApplicationError("conflict", "locked", LOCKED)
        case Forbidden():
            return ApplicationError("forbidden", "forbidden", found.message)
        case RestoreStale():
            return ApplicationError("conflict", "restore_stale", STALE)
        case _:
            raise TypeError(f"모르는 갈래: {found!r}")


def _text(value: Decimal | None) -> str | None:
    return None if value is None else decimal_text(value)


def _values(by_year: Mapping[int, Decimal | None]) -> dict[str, str | None]:
    return {str(year): _text(value) for year, value in by_year.items()}


def _actor(principal: Principal) -> Actor:
    return Actor(kind=principal.kind, user_id=int(principal.user_id))


def _unit(pair: tuple[str, str] | None) -> GhgUnitOut | None:
    return None if pair is None else GhgUnitOut(kind=pair[0], unit=pair[1])


def _gases(gases: tuple[GasValues, ...]) -> list[GhgGasOut]:
    return [GhgGasOut(gas=gas.gas, enabled=gas.enabled, factor=_text(gas.factor), gwp=_text(gas.gwp)) for gas in gases]


def _pool_factor_out(view: FactorView, version_id: int) -> EntryFactorOut:
    return EntryFactorOut(
        versionId=str(version_id),
        factorId=str(view.id),
        name=view.name,
        source=view.source,
        version=view.version,
        inputUnit=GhgUnitOut(kind=view.input_unit[0], unit=view.input_unit[1]),
        ncvEnabled=view.ncv_enabled,
        ncv=_text(view.ncv),
        ncvUnit=_unit(view.ncv_unit),
        factorUnit=view.factor_unit,
        gases=_gases(view.gases),
        isCustom=False,
    )


def _custom_out(view: CustomView) -> EntryCustomFactorOut:
    return EntryCustomFactorOut(
        customId=str(view.id),
        name=view.name,
        source=view.source,
        baseYear=view.base_year,
        tier=view.tier,
        countryCode=view.country_code,
        industryCode=view.industry_code,
        inputUnit=GhgUnitOut(kind=view.input_unit[0], unit=view.input_unit[1]),
        ncvEnabled=view.ncv is not None,
        ncv=_text(view.ncv),
        ncvUnit=_unit(view.ncv_unit),
        factorUnit=view.factor_unit,
        gases=_gases(view.gases),
        note=view.note,
        isCustom=True,
    )


def _row_factor_out(row: RowView) -> EntryFactorOut | EntryCustomFactorOut | None:
    if isinstance(row.factor, CustomView):
        return _custom_out(row.factor)
    if row.factor is None or row.factor_version_id is None:
        return None
    return _pool_factor_out(row.factor, row.factor_version_id)


def _ref_out(ref: FactorRef | None) -> EntryFactorRefOut | None:
    if ref is None:
        return None
    return EntryFactorRefOut(
        versionId=None if ref.version_id is None else str(ref.version_id),
        customId=None if ref.custom_id is None else str(ref.custom_id),
        name=ref.name,
        isCustom=ref.is_custom,
    )


def _pair(unit: GhgUnitIn | None) -> tuple[str, str] | None:
    return None if unit is None else (unit.kind, unit.unit)


def _draft(body: GhgFactorIn) -> FactorDraft:
    """직접입력 계수 → FactorDraft(관리자 풀 경로의 꼴과 같다 — 검사는 actions 의 check_factor)."""
    return FactorDraft(
        name=body.name,
        source=body.source,
        base_year=body.baseYear,
        tier=body.tier,
        country_code=body.countryCode,
        industry_code=body.industryCode,
        input_unit=_pair(body.inputUnit),
        emission_unit=_pair(body.emissionUnit),
        ncv_enabled=body.ncvEnabled,
        ncv=body.ncv,
        ncv_unit=_pair(body.ncvUnit),
        factor_unit=body.factorUnit,
        gases=tuple(GasDraft(gas.gas, gas.enabled, gas.factor, gas.gwp) for gas in body.gases),
        note=body.note,
    )


def _row_out(row: RowView) -> EntryRowOut:
    return EntryRowOut(
        rowId=str(row.id),
        siteFacilityId=str(row.site_facility_id),
        detailName=row.detail_name,
        unit=row.unit,
        na=row.na,
        values=[EntrySlotOut(slot=v.slot, amount=_text(v.amount), estimated=v.estimated) for v in row.values],
        emission=_text(row.emission),
        emissionProblem=row.emission_problem,
        factor=_row_factor_out(row),
    )


def _index_out(found: IndexDetail) -> EntryIndexOut:
    return EntryIndexOut(
        year=found.year,
        nodeId=str(found.node_id),
        name=found.name,
        path=list(found.path),
        decimals=found.decimals,
        memo=found.memo,
        locked=found.locked_at is not None,
        lockedAt=found.locked_at,
        lockedBy=None
        if found.locked_by is None
        else EntryLockedByOut(id=str(found.locked_by[0]), name=found.locked_by[1]),
        unitOptions=list(found.unit_options),
        factor=_pool_factor_out(found.factor, found.factor_version_id),
        totals=EntryTotalsOut(
            years=list(found.totals.years),
            all=_values(found.totals.all),
            bySite=[
                EntrySiteTotalOut(siteId=str(site.site_id), siteName=site.site_name, values=_values(site.values))
                for site in found.totals.by_site
            ],
        ),
        sites=[
            EntrySiteOut(
                siteId=str(block.site_id),
                siteName=block.site_name,
                facilities=[
                    EntryFacilityOut(id=str(line.id), detailName=line.detail_name, hasRow=line.has_row)
                    for line in block.facilities
                ],
                rows=[_row_out(row) for row in block.rows],
                period=block.period,
                slots=list(block.slots),
            )
            for block in found.sites
        ],
    )


def _detail_or_refused(found: object) -> EntryIndexOut:
    if not isinstance(found, IndexDetail):
        raise _refused(found)
    return _index_out(found)


# ── ⓗ 해 · ⓘ 리스트 ───────────────────────────────────────────────


@router.get(
    "/scope12/years",
    operation_id="inventory_scope12_years",
    response={200: EntryYearsOut, **TOKEN_ERROR_RESPONSES},
    auth=COMPANY_AUTH,
)
def years(request: HttpRequest) -> EntryYearsOut:
    """그 회사의 인벤토리 해(새 해 먼저). configured = 숨기지 않은 인덱스 선택이 있다."""
    principal = permitted(request, "inventory_scope12_years")
    found = actions.years(company_of(principal))
    return EntryYearsOut(years=[EntryYearOut(year=line.year, configured=line.configured) for line in found])


@router.get(
    "/scope12/rows",
    operation_id="inventory_scope12_rows",
    response={200: EntryRowsOut, **TOKEN_ERROR_RESPONSES},
    auth=COMPANY_AUTH,
)
def rows(request: HttpRequest, year: int, q: Search = None) -> EntryRowsOut:
    """리스트 — 숨기지 않은 선택 잎마다 Y-2·Y-1·Y 배출량(켠 사업장 합), 뿌리 노드(Scope)마다 묶음과 합. 쪽 없음.
    `q` 는 잎·조상 이름 부분 일치(대소문자 무시). 설정 안 된 해는 200 + configured false · scopes 빈 목록."""
    principal = permitted(request, "inventory_scope12_rows")
    found = actions.list_rows(company_of(principal), year, q)
    if isinstance(found, Invalid):
        raise _refused(found)
    return EntryRowsOut(
        year=found.year,
        years=list(found.years),
        configured=found.configured,
        decimals=found.decimals,
        scopes=[
            EntryScopeOut(
                scopeId=str(group.scope_id),
                scopeName=group.scope_name,
                values=_values(group.values),
                rows=[
                    EntryListRowOut(
                        nodeId=str(row.node_id),
                        path=list(row.path),
                        values=_values(row.values),
                        hasMemo=row.has_memo,
                        estimated=row.estimated,
                        locked=row.locked,
                    )
                    for row in group.rows
                ],
            )
            for group in found.scopes
        ],
    )


# ── ⓐ~ⓕ 인덱스 하나 ────────────────────────────────────────────────


@router.get(
    INDEX,
    operation_id="inventory_scope12_index_detail",
    response={200: EntryIndexOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def index_detail(request: HttpRequest, year: int, node_id: int) -> EntryIndexOut:
    """그 해·잎의 상세 — 켠 사업장마다 그 잎 코드의 자산/시설·입력 행 · 잡은 판 · 세 해 합 · 단위 목록 · 메모 · 잠금."""
    principal = permitted(request, "inventory_scope12_index_detail")
    return _detail_or_refused(actions.index_detail(company_of(principal), year, node_id))


@router.put(
    INDEX + "/sites/{site_id}/rows",
    operation_id="inventory_scope12_rows_save",
    response={200: EntryIndexOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def rows_save(request: HttpRequest, year: int, node_id: int, site_id: int, body: EntrySaveIn) -> EntryIndexOut:
    """한 사업장의 입력 행 저장 — rowId 있는 줄은 고침(준 칸만), 없는 줄은 새 행. 잡은 판으로 셈해 행에 저장한다.
    값 바뀐 칸마다 히스토리. 하나라도 걸리면 0 씀(422 fields.rows.<i>.<칸>). 응답은 상세."""
    principal = permitted(request, "inventory_scope12_rows_save")
    given = [
        RowInput(
            site_facility_id=row.siteFacilityId,
            unit=row.unit,
            na=row.na,
            values=tuple(SlotInput(v.slot, v.amount, v.estimated) for v in row.values),
            row_id=row.rowId,
        )
        for row in body.rows
    ]
    found = actions.save_rows(company_of(principal), year, node_id, site_id, given, _actor(principal))
    return _detail_or_refused(found)


@router.post(
    INDEX + "/rows/delete",
    operation_id="inventory_scope12_rows_delete",
    response={200: EntryCountOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def rows_delete(request: HttpRequest, year: int, node_id: int, body: EntryIdsIn) -> EntryCountOut:
    """입력 행 여럿을 삭제 표시한다(값·히스토리 그대로). 하나라도 없거나 남의 것이면 404 — 행 0."""
    principal = permitted(request, "inventory_scope12_rows_delete")
    found = actions.delete_rows(company_of(principal), year, node_id, body.ids)
    if not isinstance(found, int):
        raise _refused(found)
    return EntryCountOut(count=found)


@router.put(
    INDEX + "/memo",
    operation_id="inventory_scope12_memo_save",
    response={200: EntryMemoOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def memo_save(request: HttpRequest, year: int, node_id: int, body: EntryMemoIn) -> EntryMemoOut:
    """인덱스 메모(빈 글자 = 지움)."""
    principal = permitted(request, "inventory_scope12_memo_save")
    found = actions.set_memo(company_of(principal), year, node_id, body.memo)
    if not isinstance(found, str):
        raise _refused(found)
    return EntryMemoOut(memo=found)


@router.post(
    INDEX + "/lock",
    operation_id="inventory_scope12_lock",
    response={200: EntryIndexOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def lock(request: HttpRequest, year: int, node_id: int) -> EntryIndexOut:
    """인덱스를 잠근다(이미 잠겼으면 그대로 — 잠근 사람·때 안 바뀜). 응답은 상세."""
    principal = permitted(request, "inventory_scope12_lock")
    return _detail_or_refused(actions.lock_index(company_of(principal), year, node_id, _actor(principal)))


@router.delete(
    INDEX + "/lock",
    operation_id="inventory_scope12_unlock",
    response={200: EntryIndexOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def unlock(request: HttpRequest, year: int, node_id: int) -> EntryIndexOut:
    """잠금을 푼다 — 운영 관리자만(작업 회사). 안 잠겼으면 그대로. 응답은 상세."""
    principal = permitted(request, "inventory_scope12_unlock")
    found = actions.unlock_index(company_of(principal), year, node_id, actor_kind=principal.kind)
    return _detail_or_refused(found)


@router.put(
    "/scope12/years/{year}/decimals",
    operation_id="inventory_scope12_decimals_save",
    response={200: EntryDecimalsOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def decimals_save(request: HttpRequest, year: int, body: EntryDecimalsIn) -> EntryDecimalsOut:
    """그 해의 표시 자릿수(저장값은 그대로). 해가 없으면 404, 범위 밖 422 fields.decimals."""
    principal = permitted(request, "inventory_scope12_decimals_save")
    found = actions.set_decimals(company_of(principal), year, body.decimals)
    if not isinstance(found, int):
        raise _refused(found)
    return EntryDecimalsOut(decimals=found)


# ── ⓙ 히스토리 ─────────────────────────────────────────────────────


@router.get(
    INDEX + "/rows/{row_id}/history",
    operation_id="inventory_scope12_row_history",
    response={200: EntryHistoryPageOut, **ERRORS_404},
    auth=COMPANY_AUTH,
)
def row_history(
    request: HttpRequest, year: int, node_id: int, row_id: int, page: Page = 1, pageSize: PageSize = 20
) -> EntryHistoryPageOut:
    """행 하나의 히스토리(새 것 먼저). 그 해·잎의 살아 있는 행이 아니면 404(지운 행도)."""
    principal = permitted(request, "inventory_scope12_row_history")
    found = actions.row_history(
        company_of(principal), year, node_id, row_id, offset=(page - 1) * pageSize, limit=pageSize
    )
    if isinstance(found, NotFound):
        raise _refused(found)
    results = [
        EntryHistoryOut(
            historyId=str(line.id),
            at=line.at,
            kind=line.kind,
            slot=line.slot,
            before=line.before,
            after=line.after,
            unit=line.unit,
            actor=EntryHistoryActorOut(
                kind=line.actor_kind,
                id=None if line.actor_user_id is None else str(line.actor_user_id),
                name=line.actor_name,
            ),
            reason=line.reason,
            restorable=line.restorable,
            beforeFactor=_ref_out(line.before_factor),
            afterFactor=_ref_out(line.after_factor),
        )
        for line in found.lines
    ]
    return EntryHistoryPageOut(**page_number_page(found.count, page, pageSize, results))


# ── ⓚ 입력주기 · ⓛ 계수 바꿈 · ⓜ 복구(S12a-2) ───────────────────────────


@router.put(
    INDEX + "/sites/{site_id}/period",
    operation_id="inventory_scope12_period_save",
    response={200: EntryIndexOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def period_save(request: HttpRequest, year: int, node_id: int, site_id: int, body: EntryPeriodIn) -> EntryIndexOut:
    """사업장 블록의 입력주기(S7 — month·quarter·year). 옛 주기 칸 값은 지우지 않고 숨기며 행마다 새 주기 칸으로
    다시 셈하고 히스토리 period 줄을 쌓는다. 같은 주기면 0 바뀜. 응답은 상세."""
    principal = permitted(request, "inventory_scope12_period_save")
    found = actions.set_period(company_of(principal), year, node_id, site_id, body.period, _actor(principal))
    return _detail_or_refused(found)


@router.put(
    INDEX + "/rows/{row_id}/factor",
    operation_id="inventory_scope12_row_factor_save",
    response={200: EntryIndexOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def row_factor_save(
    request: HttpRequest, year: int, node_id: int, row_id: int, body: EntryRowFactorIn
) -> EntryIndexOut:
    """행 하나의 계수 바꿈(S9·S11) — 운영 관리자만(작업 회사). factorId(같은 잎의 풀 계수 — 그 지금 판) 또는
    custom(행 전용 직접입력) 가운데 하나 + 사유. 둘 다·둘 다 없음 422 fields.factorId. 응답은 상세."""
    principal = permitted(request, "inventory_scope12_row_factor_save")
    found = actions.set_row_factor(
        company_of(principal),
        year,
        node_id,
        row_id,
        factor_id=body.factorId,
        custom=None if body.custom is None else _draft(body.custom),
        reason=body.reason,
        actor=_actor(principal),
    )
    return _detail_or_refused(found)


@router.post(
    INDEX + "/rows/{row_id}/history/{history_id}/restore",
    operation_id="inventory_scope12_history_restore",
    response={200: EntryIndexOut, **BODY_ERRORS_404},
    auth=COMPANY_AUTH,
)
def history_restore(
    request: HttpRequest, year: int, node_id: int, row_id: int, history_id: int, body: EntryRestoreIn
) -> EntryIndexOut:
    """히스토리 줄의 뒤(after) 상태로 되돌리는 새 줄을 쌓는다(S12 — 지우기 0). value·period·factor 만, 그 행의 맨 위
    줄은 422 fields.historyId. factor 줄은 운영 관리자만(403)·사유 필수. 낡은 줄 409 restore_stale. 응답은 상세."""
    principal = permitted(request, "inventory_scope12_history_restore")
    found = actions.restore(
        company_of(principal), year, node_id, row_id, history_id, reason=body.reason, actor=_actor(principal)
    )
    return _detail_or_refused(found)
