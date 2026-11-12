"""Scope 1·2 대시보드(S1) 경로. 밴드 S12a-3 ②(결정 MARC-ENT-469 1·7). service/apis/inventory.py 의 router 가
이 router 를 「""」 에 붙인다(config/api.py 0줄). 아래 경로는 /inventory 뒤의 것이다.

    GET    /scope12/dashboard?year=     inventory_scope12_dashboard     회사 업무(COMPANY)

인증: [company_scoped_auth_or_next, session_cookie](회사 경로 — 고객사 사용자, 운영 관리자는 작업 회사로).
차례: permitted(첫 문장) → company_of(principal) → actions. 회사 id 는 인증 주체에서만. 하는 일은 셋뿐이다: 값 꺼냄 →
actions 부름 → 꼴. 오류: 운영 관리자에 회사 둘 400 `company_ambiguous` · year 가 정수 아님 422. 설정 안 된 해는 200 +
configured false(리스트 inventory_scope12_rows 와 같음).
S3K2a ②: Scope 3 칸(total.scope3·sum·scope3Categories)은 actions.board 가 연도 상태와 같은 재료로 configured 와 따로
셈한다. bySite[].scope3 는 1차 늘 null(템플릿의 사업장 칸은 등록 사업장과 안 이어짐).
"""

from decimal import Decimal

from django.http import HttpRequest
from ninja import Router

from esgapi.core.auth.bearer import company_of, company_scoped_auth_or_next, permitted
from esgapi.core.schemas import TOKEN_ERROR_RESPONSES
from esgapi.inventory.service.actions import dashboard as actions
from esgapi.inventory.service.schemas.dashboard import (
    Scope12DashboardCategoryOut,
    Scope12DashboardOut,
    Scope12DashboardScopeOut,
    Scope12DashboardSiteOut,
    Scope12DashboardSiteScopeOut,
    Scope12DashboardSourceOut,
    Scope12DashboardTotalOut,
)
from esgapi.inventory.service.utils.ghg_pool import decimal_text
from esgapi.user.service.apis.auth import session_cookie

router = Router(tags=["Scope 1·2 입력"])
COMPANY_AUTH = [company_scoped_auth_or_next, session_cookie]


def _text(value: Decimal | None) -> str | None:
    return None if value is None else decimal_text(value)


def _share(value: Decimal | None) -> str | None:
    """퍼센트는 소수 첫째 자리 글자 그대로(「12.5」·「100.0」 — 끝 0 을 걷지 않는다)."""
    return None if value is None else format(value, "f")


def _out(board: actions.Board) -> Scope12DashboardOut:
    found = board.scope12
    scope12 = _text(found.scope12)
    return Scope12DashboardOut(
        year=found.year,
        configured=found.configured,
        decimals=found.decimals,
        complete=found.complete,
        scopes=[
            Scope12DashboardScopeOut(
                scopeId=str(scope.scope_id),
                scopeName=scope.scope_name,
                scopeOrder=scope.scope_order,
                value=_text(scope.value),
                topSources=[
                    Scope12DashboardSourceOut(
                        nodeId=str(source.node_id),
                        name=source.name,
                        value=decimal_text(source.value),
                        share=_share(source.share),
                    )
                    for source in scope.top_sources
                ],
            )
            for scope in found.scopes
        ],
        # S3K2a ②: scope3 = 카테고리 지금 결과 합 · sum = Scope 1·2 합 + Scope 3 합(null 은 빼고 — 둘 다 null 이면 null)
        total=Scope12DashboardTotalOut(
            scope12=scope12,
            scope2Market=None,
            scope3=_text(board.scope3),
            sum=_text(board.total),
            scope3FailedSheets=board.scope3_failed_sheets,
        ),
        bySite=[
            Scope12DashboardSiteOut(
                siteId=str(site.site_id),
                siteName=site.site_name,
                scopes=[
                    Scope12DashboardSiteScopeOut(scopeId=str(scope_id), value=_text(value))
                    for scope_id, value in site.values
                ],
                scope3=None,
            )
            for site in found.by_site
        ],
        scope3Categories=[
            Scope12DashboardCategoryOut(
                category=line.category,
                name=line.name,
                value=decimal_text(line.value),
                share=_share(line.share),
            )
            for line in board.categories
        ],
    )


@router.get(
    "/scope12/dashboard",
    operation_id="inventory_scope12_dashboard",
    response={200: Scope12DashboardOut, **TOKEN_ERROR_RESPONSES},
    auth=COMPANY_AUTH,
)
def dashboard(request: HttpRequest, year: int) -> Scope12DashboardOut:
    """대시보드(S1) — 그 해 Scope 1·2 합(뿌리별)·합계·사업장별·배출원 상위 5. 셈은 리스트와 같은 재료(켠 사업장).
    Scope 3 합·카테고리 상위 5 는 연도 상태와 같은 재료(잠겼으면 핀)로 Scope 1·2 설정과 따로 셈한다. 시장기반·
    사업장별 Scope 3 칸은 1차에 늘 null. 설정 안 된 해는 200 + configured false(Scope 3 칸은 그대로 셈)."""
    principal = permitted(request, "inventory_scope12_dashboard")
    return _out(actions.board(company_of(principal), year))
