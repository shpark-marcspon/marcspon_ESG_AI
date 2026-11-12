"""inventory 의 경로 열둘 — 온실가스 인덱스 풀(S19)·시설별 배출계수 풀(S20)·선택 목록. 밴드 K1b-2a ③
(결정 MARC-ENT-463·469 3, 감독 판단 1). service/apis/inventory.py 의 router 가 이 router 를 「""」 에 붙인다
(config/api.py 0줄 — inventory 라우터는 이미 /inventory). 아래 경로는 /inventory 뒤의 것이다.

    GET  /admin/ghg-index/nodes?parentId=&q=              inventory_admin_ghg_nodes_list        운영 관리자만
    POST /admin/ghg-index/nodes                            inventory_admin_ghg_nodes_create      〃 → 201(열 1~3)
    PATCH /admin/ghg-index/nodes/{node_id}                 inventory_admin_ghg_nodes_update      〃(열 1~3 이름)
    POST /admin/ghg-index/nodes/delete                     inventory_admin_ghg_nodes_delete      〃(잎이면 계수도)
    GET  /admin/ghg-index/facilities/{node_id}             inventory_admin_ghg_facilities_get    〃
    POST /admin/ghg-index/facilities                       inventory_admin_ghg_facilities_create 〃 → 201(열 4)
    PUT  /admin/ghg-index/facilities/{node_id}             inventory_admin_ghg_facilities_save   〃(defaultFactorId)
    POST /admin/ghg-index/facilities/{node_id}/factors     inventory_admin_ghg_factors_create    〃 → 201(판 1)
    GET  /admin/ghg-factors/{factor_id}?version=           inventory_admin_ghg_factors_get       〃(+ versions)
    PUT  /admin/ghg-factors/{factor_id}                    inventory_admin_ghg_factors_save      〃(새 판)
    POST /admin/ghg-factors/delete                         inventory_admin_ghg_factors_delete    〃(기본 승계)
    GET  /admin/ghg-options                                inventory_admin_ghg_options           〃

인증: 열둘 다 access_token_auth(Bearer — K1b-1 의 admin 넷 꼴). 차례: permitted(첫 문장) →
selectors·services·actions(그 첫 문장도 권한 표 — ALSO_INSIDE). 공통 풀이라 회사를 고르지 않는다(company_of 0).
경로는 models 를 import 하지 않는다(`.importlinter` 계약 라).
오류: 칸 검사·단 어긋남·겹침 422 `fields.<칸>` · 자식 있음 409 `has_children` · 쓰이는 노드·계수 409 `in_use` · 없는·
삭제된 id(경로·ids[]) 404 `not_found` — 어느 거절이든 행 0. 본문에 회사 칸이 없다(companyId → 422).
"""

from typing import Annotated

from django.http import HttpRequest
from ninja import Router, Status
from ninja.params.functions import Query

from esgapi.core.auth.bearer import access_token_auth, permitted
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.schemas.ghg_pool import (
    GhgCodeNameOut,
    GhgCountOut,
    GhgDefaultsOut,
    GhgFacilityCreateIn,
    GhgFacilityOut,
    GhgFacilitySaveIn,
    GhgFactorIn,
    GhgFactorOut,
    GhgFactorSummaryOut,
    GhgGasOut,
    GhgIdsIn,
    GhgNodeCreateIn,
    GhgNodeOut,
    GhgNodeRenameIn,
    GhgNodesOut,
    GhgOptionsOut,
    GhgUnitIn,
    GhgUnitKindOut,
    GhgUnitOut,
)
from esgapi.inventory.service.selectors import ghg_pool as selectors
from esgapi.inventory.service.services import ghg_pool as services
from esgapi.inventory.service.utils.ghg_pool import (
    COUNTRIES,
    DEFAULT_EMISSION_UNIT,
    GASES,
    INDUSTRIES,
    SEARCH_MAX,
    UNITS,
    FacilityView,
    FactorDraft,
    FactorView,
    Forbidden,
    GasDraft,
    HasChildren,
    InUse,
    Invalid,
    NodeView,
    NotFound,
    decimal_text,
    default_factor_unit,
)

router = Router(tags=["온실가스 풀"])
ParentId = Annotated[int | None, Query(ge=1)]
Search = Annotated[str | None, Query(max_length=SEARCH_MAX)]
Version = Annotated[int | None, Query(ge=1)]
ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
BODY_ERRORS_404: dict[int, type[ErrorBody]] = {**TOKEN_BODY_ERROR_RESPONSES, 404: ErrorBody}

NOT_FOUND = "그런 노드·계수·판이 없다"
HAS_CHILDREN = "삭제 안 된 하위 항목이 있어 지울 수 없다"
IN_USE = "쓰이고 있어 지울 수 없다"
INVALID = "입력을 확인한다"


def _refused(found: object) -> ApplicationError:
    """selectors·services·actions 의 거절 갈래 → 오류. 갈래가 아니면 부른 쪽이 잘못 넘긴 것이다."""
    match found:
        case NotFound():
            return ApplicationError("not_found", "not_found", NOT_FOUND)
        case Invalid(fields=fields):
            return ApplicationError(
                "validation", "validation_error", INVALID, fields={name: [why] for name, why in fields.items()}
            )
        case HasChildren():
            return ApplicationError("conflict", "has_children", HAS_CHILDREN)
        case InUse():
            return ApplicationError("conflict", "in_use", IN_USE)
        case Forbidden():
            return ApplicationError("forbidden", "forbidden", found.message)
        case _:
            raise TypeError(f"모르는 갈래: {found!r}")


def _unit(pair: tuple[str, str]) -> GhgUnitOut:
    return GhgUnitOut(kind=pair[0], unit=pair[1])


def _pair(unit: GhgUnitIn | None) -> tuple[str, str] | None:
    return None if unit is None else (unit.kind, unit.unit)


def _node_out(node: NodeView) -> GhgNodeOut:
    return GhgNodeOut(
        id=str(node.id),
        level=node.level,
        name=node.name,
        parentId=None if node.parent_id is None else str(node.parent_id),
        sortOrder=node.sort_order,
        childCount=node.child_count,
        facilityCodeId=None if node.facility_code_id is None else str(node.facility_code_id),
        facilityCode=node.facility_code,
    )


def _facility_out(found: FacilityView) -> GhgFacilityOut:
    return GhgFacilityOut(
        id=str(found.id),
        parentId=str(found.parent_id),
        facilityCodeId=str(found.facility_code_id),
        facilityCode=found.facility_code,
        facilityName=found.facility_name,
        unit=_unit(found.unit),
        tooltip=found.tooltip,
        factors=[
            GhgFactorSummaryOut(
                id=str(factor.id),
                name=factor.name,
                inputUnit=_unit(factor.input_unit),
                isDefault=factor.is_default,
                sortOrder=factor.sort_order,
                version=factor.version,
            )
            for factor in found.factors
        ],
    )


def _factor_out(found: FactorView) -> GhgFactorOut:
    return GhgFactorOut(
        id=str(found.id),
        facilityNodeId=str(found.facility_node_id),
        version=found.version,
        versions=list(found.versions),
        isDefault=found.is_default,
        sortOrder=found.sort_order,
        name=found.name,
        source=found.source,
        baseYear=found.base_year,
        tier=found.tier,
        countryCode=found.country_code,
        industryCode=found.industry_code,
        inputUnit=_unit(found.input_unit),
        emissionUnit=_unit(found.emission_unit),
        ncvEnabled=found.ncv_enabled,
        ncv=None if found.ncv is None else decimal_text(found.ncv),
        ncvUnit=None if found.ncv_unit is None else _unit(found.ncv_unit),
        factorUnit=found.factor_unit,
        gases=[
            GhgGasOut(
                gas=gas.gas,
                enabled=gas.enabled,
                factor=None if gas.factor is None else decimal_text(gas.factor),
                gwp=None if gas.gwp is None else decimal_text(gas.gwp),
            )
            for gas in found.gases
        ],
        note=found.note,
        seedRecordIds=list(found.seed_record_ids),
        seedGwpSetId=found.seed_gwp_set_id,
        createdAt=found.created_at,
        updatedAt=found.updated_at,
    )


def _draft(body: GhgFactorIn) -> FactorDraft:
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


# ── 노드(열 1~3, 목록은 넷 다) ────────────────────────────────────────


@router.get(
    "/admin/ghg-index/nodes",
    operation_id="inventory_admin_ghg_nodes_list",
    response={200: GhgNodesOut, **ERRORS_404},
    auth=access_token_auth,
)
def ghg_nodes_list(request: HttpRequest, parentId: ParentId = None, q: Search = None) -> GhgNodesOut:
    """운영 관리자만. 열 하나 — parentId 없음 → 범위 단, 있음 → 그 노드의 자식. q 는 이름(잎은 코드 이름) 부분 일치
    (대소문자 무시)인 노드와 그 조상(parentId 는 보지 않는다). 차례: 단 → 만든 차례. 페이지 없음."""
    principal = permitted(request, "inventory_admin_ghg_nodes_list")
    found = selectors.node_list(actor_kind=principal.kind, parent_id=parentId, q=q)
    if not isinstance(found, list):
        raise _refused(found)
    return GhgNodesOut(items=[_node_out(node) for node in found])


@router.post(
    "/admin/ghg-index/nodes",
    operation_id="inventory_admin_ghg_nodes_create",
    response={201: GhgNodeOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def ghg_nodes_create(request: HttpRequest, body: GhgNodeCreateIn) -> Status[GhgNodeOut]:
    """운영 관리자만. 열 1~3 노드 하나(범위는 부모 없음, 그 밖은 부모 단 = 자기 단 − 1)."""
    principal = permitted(request, "inventory_admin_ghg_nodes_create")
    found = services.create_node(actor_kind=principal.kind, level=body.level, parent_id=body.parentId, name=body.name)
    if not isinstance(found, NodeView):
        raise _refused(found)
    return Status(201, _node_out(found))


# 고정 경로(delete)를 {node_id} 앞에 건다.
@router.post(
    "/admin/ghg-index/nodes/delete",
    operation_id="inventory_admin_ghg_nodes_delete",
    response={200: GhgCountOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def ghg_nodes_delete(request: HttpRequest, body: GhgIdsIn) -> GhgCountOut:
    """운영 관리자만. 노드 여럿을 삭제 표시한다(잎이면 그 계수도). 하나라도 없거나 지웠으면 404, 요청 밖의 하위 항목이
    있으면 409 has_children, 쓰이면 409 in_use — 어느 쪽이든 행 0."""
    principal = permitted(request, "inventory_admin_ghg_nodes_delete")
    found = actions.delete_nodes(actor_kind=principal.kind, ids=body.ids)
    if not isinstance(found, int):
        raise _refused(found)
    return GhgCountOut(count=found)


@router.patch(
    "/admin/ghg-index/nodes/{node_id}",
    operation_id="inventory_admin_ghg_nodes_update",
    response={200: GhgNodeOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def ghg_nodes_update(request: HttpRequest, node_id: int, body: GhgNodeRenameIn) -> GhgNodeOut:
    """운영 관리자만. 열 1~3 노드의 이름. 잎은 PUT /admin/ghg-index/facilities/{node_id}."""
    principal = permitted(request, "inventory_admin_ghg_nodes_update")
    found = services.rename_node(actor_kind=principal.kind, node_id=node_id, name=body.name)
    if not isinstance(found, NodeView):
        raise _refused(found)
    return _node_out(found)


# ── 잎(자산/시설) ────────────────────────────────────────────────────


@router.post(
    "/admin/ghg-index/facilities",
    operation_id="inventory_admin_ghg_facilities_create",
    response={201: GhgFacilityOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def ghg_facilities_create(request: HttpRequest, body: GhgFacilityCreateIn) -> Status[GhgFacilityOut]:
    """운영 관리자만. 열 4 잎 하나 — 부모는 배출활동, 코드는 공통 목록의 살아 있는 것(같은 활동 아래 겹치면 422)."""
    principal = permitted(request, "inventory_admin_ghg_facilities_create")
    found = actions.create_facility(
        actor_kind=principal.kind,
        parent_id=body.parentId,
        facility_code_id=body.facilityCodeId,
        unit=_pair(body.unit),
        tooltip=body.tooltip,
    )
    if not isinstance(found, FacilityView):
        raise _refused(found)
    return Status(201, _facility_out(found))


@router.get(
    "/admin/ghg-index/facilities/{node_id}",
    operation_id="inventory_admin_ghg_facilities_get",
    response={200: GhgFacilityOut, **ERRORS_404},
    auth=access_token_auth,
)
def ghg_facilities_get(request: HttpRequest, node_id: int) -> GhgFacilityOut:
    """운영 관리자만. 잎 하나와 그 계수(삭제 안 된 것의 지금 판 — 만든 차례)."""
    principal = permitted(request, "inventory_admin_ghg_facilities_get")
    found = selectors.facility_detail(actor_kind=principal.kind, node_id=node_id)
    if not isinstance(found, FacilityView):
        raise _refused(found)
    return _facility_out(found)


@router.put(
    "/admin/ghg-index/facilities/{node_id}",
    operation_id="inventory_admin_ghg_facilities_save",
    response={200: GhgFacilityOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def ghg_facilities_save(request: HttpRequest, node_id: int, body: GhgFacilitySaveIn) -> GhgFacilityOut:
    """운영 관리자만. 잎 저장 — 코드·1차 단위·툴팁, defaultFactorId 가 있으면 기본 바꾸기(그 잎의 계수만)."""
    principal = permitted(request, "inventory_admin_ghg_facilities_save")
    found = actions.save_facility(
        actor_kind=principal.kind,
        node_id=node_id,
        facility_code_id=body.facilityCodeId,
        unit=_pair(body.unit),
        tooltip=body.tooltip,
        default_factor_id=body.defaultFactorId,
    )
    if not isinstance(found, FacilityView):
        raise _refused(found)
    return _facility_out(found)


@router.post(
    "/admin/ghg-index/facilities/{node_id}/factors",
    operation_id="inventory_admin_ghg_factors_create",
    response={201: GhgFactorOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def ghg_factors_create(request: HttpRequest, node_id: int, body: GhgFactorIn) -> Status[GhgFactorOut]:
    """운영 관리자만. 잎의 계수 하나(판 1, 가스 일곱). 그 잎의 첫 계수면 기본."""
    principal = permitted(request, "inventory_admin_ghg_factors_create")
    found = actions.create_factor(actor_kind=principal.kind, node_id=node_id, draft=_draft(body))
    if not isinstance(found, FactorView):
        raise _refused(found)
    return Status(201, _factor_out(found))


# ── 계수 ─────────────────────────────────────────────────────────────


@router.post(
    "/admin/ghg-factors/delete",
    operation_id="inventory_admin_ghg_factors_delete",
    response={200: GhgCountOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def ghg_factors_delete(request: HttpRequest, body: GhgIdsIn) -> GhgCountOut:
    """운영 관리자만. 계수 여럿을 삭제 표시한다. 기본을 지운 잎은 남은 첫 계수가 기본을 잇는다. 하나라도 없으면 404."""
    principal = permitted(request, "inventory_admin_ghg_factors_delete")
    found = actions.delete_factors(actor_kind=principal.kind, ids=body.ids)
    if not isinstance(found, int):
        raise _refused(found)
    return GhgCountOut(count=found)


@router.get(
    "/admin/ghg-factors/{factor_id}",
    operation_id="inventory_admin_ghg_factors_get",
    response={200: GhgFactorOut, **ERRORS_404},
    auth=access_token_auth,
)
def ghg_factors_get(request: HttpRequest, factor_id: int, version: Version = None) -> GhgFactorOut:
    """운영 관리자만. 계수의 판 하나(version 없음 → 지금 판)와 판 번호 목록."""
    principal = permitted(request, "inventory_admin_ghg_factors_get")
    found = selectors.factor_version(actor_kind=principal.kind, factor_id=factor_id, version=version)
    if not isinstance(found, FactorView):
        raise _refused(found)
    return _factor_out(found)


@router.put(
    "/admin/ghg-factors/{factor_id}",
    operation_id="inventory_admin_ghg_factors_save",
    response={200: GhgFactorOut, **BODY_ERRORS_404},
    auth=access_token_auth,
)
def ghg_factors_save(request: HttpRequest, factor_id: int, body: GhgFactorIn) -> GhgFactorOut:
    """운영 관리자만. 계수 고치기 = 새 판(version + 1, 바뀐 것이 없어도). 옛 판은 글자 그대로 남는다."""
    principal = permitted(request, "inventory_admin_ghg_factors_save")
    found = actions.save_factor(actor_kind=principal.kind, factor_id=factor_id, draft=_draft(body))
    if not isinstance(found, FactorView):
        raise _refused(found)
    return _factor_out(found)


# ── 선택 목록 ────────────────────────────────────────────────────────


@router.get(
    "/admin/ghg-options",
    operation_id="inventory_admin_ghg_options",
    response={200: GhgOptionsOut, **TOKEN_ERROR_RESPONSES},
    auth=access_token_auth,
)
def ghg_options(request: HttpRequest) -> GhgOptionsOut:
    """운영 관리자만. 가스 일곱·단위(종류별)·국가·산업·기본값(배출량 단위·factorUnit 두 갈래)."""
    principal = permitted(request, "inventory_admin_ghg_options")
    found = selectors.options(actor_kind=principal.kind)
    if isinstance(found, Forbidden):
        raise _refused(found)
    return GhgOptionsOut(
        gases=list(GASES),
        units=[GhgUnitKindOut(kind=kind, units=list(units)) for kind, units in UNITS.items()],
        countries=[GhgCodeNameOut(code=code, name=name) for code, name in COUNTRIES],
        industries=[GhgCodeNameOut(code=code, name=name) for code, name in INDUSTRIES],
        defaults=GhgDefaultsOut(
            emissionUnit=_unit(DEFAULT_EMISSION_UNIT),
            factorUnitWithNcv=default_factor_unit(True, ""),
            factorUnitWithoutNcv=default_factor_unit(False, "<투입 단위>"),
        ),
    )
