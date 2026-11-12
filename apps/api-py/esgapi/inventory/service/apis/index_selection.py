"""inventory 의 고객사 인덱스 선택 경로 둘(S17). 밴드 K1b-2b ③(결정 MARC-ENT-469 3·4·374).
service/apis/inventory.py 의 router 가 이 router 를 「""」 에 붙인다(config/api.py 0줄). 아래 경로는 /inventory 뒤의
것이다.

    GET /scope12/index-tree?year=                inventory_scope12_index_tree             회사 업무(COMPANY)
    PUT /scope12/index-selections/{year}         inventory_scope12_index_selections_save  〃

인증: [company_scoped_auth_or_next, session_cookie](회사 경로 — 고객사 사용자, 운영 관리자는 작업 회사로).
차례: permitted(첫 문장) → company_of(principal) → actions. 회사 id 는 인증 주체에서만(본문 companyId → 422).
경로는 models 를 import 하지 않는다(`.importlinter` 계약 라).
오류: 연도 밖·빠짐 422 `fields.year` · 잎 판정 422 `fields.facilityNodeIds`(스펙 400 → 앱 관례 422) · 운영 관리자에
회사 둘 400 `company_ambiguous`.
"""

from django.http import HttpRequest
from ninja import Router

from esgapi.core.auth.bearer import company_of, company_scoped_auth_or_next, permitted
from esgapi.core.exceptions import ApplicationError
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.inventory.service.actions import index_selection as actions
from esgapi.inventory.service.schemas.index_selection import (
    IndexSelectionSaveIn,
    IndexSelectionSaveOut,
    IndexTreeNodeOut,
    IndexTreeOut,
)
from esgapi.inventory.service.utils.ghg_pool import Invalid
from esgapi.inventory.service.utils.index_selection import TreeNode
from esgapi.user.service.apis.auth import session_cookie

router = Router(tags=["인덱스 선택"])
COMPANY_AUTH = [company_scoped_auth_or_next, session_cookie]
INVALID = "입력을 확인한다"


def _invalid(found: Invalid) -> ApplicationError:
    return ApplicationError(
        "validation", "validation_error", INVALID, fields={name: [why] for name, why in found.fields.items()}
    )


def _node_out(line: TreeNode) -> IndexTreeNodeOut:
    return IndexTreeNodeOut(
        id=str(line.id),
        level=line.level,
        name=line.name,
        parentId=None if line.parent_id is None else str(line.parent_id),
        facilityCodeId=None if line.facility_code_id is None else str(line.facility_code_id),
        availableCount=line.available_count,
        selected=line.selected,
        hasFactor=line.has_factor,
        hasData=line.has_data,
    )


@router.get(
    "/scope12/index-tree",
    operation_id="inventory_scope12_index_tree",
    response={200: IndexTreeOut, **TOKEN_ERROR_RESPONSES},
    auth=COMPANY_AUTH,
)
def index_tree(request: HttpRequest, year: int) -> IndexTreeOut:
    """공통 풀 트리 + 이 회사 시설 수 + 이 해의 선택. 페이지 없음. 해가 없으면 선택 0(해를 만들지 않는다)."""
    principal = permitted(request, "inventory_scope12_index_tree")
    found = actions.index_tree(company_of(principal), year)
    if isinstance(found, Invalid):
        raise _invalid(found)
    return IndexTreeOut(year=found.year, nodes=[_node_out(line) for line in found.nodes])


@router.put(
    "/scope12/index-selections/{year}",
    operation_id="inventory_scope12_index_selections_save",
    response={200: IndexSelectionSaveOut, **TOKEN_BODY_ERROR_RESPONSES},
    auth=COMPANY_AUTH,
)
def index_selections_save(request: HttpRequest, year: int, body: IndexSelectionSaveIn) -> IndexSelectionSaveOut:
    """그 해의 선택을 요청 잎 목록으로 맞춘다(해가 없으면 만든다). 고른 잎은 그때 기본 계수의 지금 판을 잡는다."""
    principal = permitted(request, "inventory_scope12_index_selections_save")
    found = actions.save_selections(company_of(principal), year, body.facilityNodeIds)
    if isinstance(found, Invalid):
        raise _invalid(found)
    return IndexSelectionSaveOut(selected=found.selected, hiddenWithData=found.hidden_with_data)
