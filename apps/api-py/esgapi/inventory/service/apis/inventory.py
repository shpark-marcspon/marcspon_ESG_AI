"""AI 온실가스 인벤토리의 경로. config/api.py 가 이 router 를 /inventory 아래에 걸어 두었다.

하는 일은 셋뿐이다: 요청에서 값을 꺼낸다 → services 의 함수를 부른다 → 갈래를 응답으로 바꾼다.
"""

from typing import Any, Final

from django.http import HttpRequest
from ninja import Router, Status

from esgapi.core.auth.bearer import company_of, company_scoped_auth_or_next, permitted
from esgapi.core.exceptions import ApplicationError, ErrorBody, ErrorDetail
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES
from esgapi.inventory.contracts.shapes import Scope12Body
from esgapi.inventory.service.actions import scope3_shortlist as actions
from esgapi.inventory.service.apis.dashboard import router as dashboard_router
from esgapi.inventory.service.apis.entries import router as entries_router
from esgapi.inventory.service.apis.ghg_pool import router as ghg_pool_router
from esgapi.inventory.service.apis.index_selection import router as index_selection_router
from esgapi.inventory.service.apis.scope3_edits import router as scope3_edits_router
from esgapi.inventory.service.apis.scope3_excel import router as scope3_excel_router
from esgapi.inventory.service.apis.scope3_runs import router as scope3_runs_router
from esgapi.inventory.service.apis.scope3_state import router as scope3_state_router
from esgapi.inventory.service.apis.scope12_excel import router as scope12_excel_router
from esgapi.inventory.service.schemas.inventory import (
    CalcIn,
    Scope3ClassifyIn,
    Scope3ClassifyOut,
    Scope3ShortlistIn,
    Scope3ShortlistOut,
)
from esgapi.inventory.service.services import inventory as services
from esgapi.user.service.apis.auth import session_cookie

router = Router()
router.add_router(
    "", ghg_pool_router
)  # K1b-2a: 온실가스 풀 열둘(/admin/ghg-index·/admin/ghg-factors·/admin/ghg-options)
router.add_router(
    "", index_selection_router
)  # K1b-2b: 고객사 인덱스 선택 둘(/scope12/index-tree·/scope12/index-selections)
router.add_router("", entries_router)  # S12a: Scope 1·2 입력 열(/scope12/years·/scope12/rows·…)
router.add_router("", scope3_runs_router)  # S3K1: Scope 3 코랩 둘(/scope3/template·/scope3/runs/{id}/result)
router.add_router("", dashboard_router)  # S12a-3: Scope 1·2 대시보드(/scope12/dashboard)
router.add_router("", scope12_excel_router)  # S12b: Scope 1·2 엑셀 셋(/scope12/years/{year}/template·/export·/uploads)
router.add_router("", scope3_state_router)  # S3K2a: Scope 3 연도 상태·잠금 셋(/scope3/years/{year}·…/lock)
router.add_router("", scope3_excel_router)  # S3D1: Scope 3 데이터 엑셀(/scope3/years/{year}/export)
router.add_router("", scope3_edits_router)  # S3K2b-1: Scope 3 줄 덧판 넷(/scope3/runs/{id}/categories/…·edits·history)

# 오류 문장에 싣는 문제의 수. 틀린 표 하나가 문제를 수천 건 낼 수 있다.
_SHOWN_PROBLEMS: Final = 20
# 문제 하나의 문장(`where: problem`)에서 싣는 글자 수. 넘으면 잘라 끝에 … 를 붙인다(그래서 최대 이 값 + 1자).
# 어림. 2026-10-08 감독이 정함, 근거는 재지 않았다.
_PROBLEM_CHARS: Final = 200


def _shown(where: str, problem: str) -> str:
    """문제 하나의 문장. 받은 값(과 where 에 든 받은 키)이 길어도 _PROBLEM_CHARS 자까지만 싣는다.

    파이썬 str 은 코드 포인트 단위라 자른 자리에서 글자(대리쌍)가 반으로 갈리지 않는다.
    """
    line = f"{where}: {problem}"
    return line if len(line) <= _PROBLEM_CHARS else line[:_PROBLEM_CHARS] + "…"


@router.post(
    "/calc",
    operation_id="inventory_calc",
    response={200: Scope12Body, **TOKEN_BODY_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    # 응답은 dict 그대로다: 주지 않은 키(선택 칸)를 null 로 채워 내보내지 않는다.
    exclude_unset=True,
    by_alias=True,
    tags=["인벤토리"],
)
def calc(request: HttpRequest, body: CalcIn) -> dict[str, Any] | Status[ErrorBody]:
    """Scope 1·2 배출량을 계산하고 집계한다. 저장하지 않는다(같은 입력이면 같은 출력).

    행 하나가 실패해도 200 이다: 그 행의 status 가 "failed" 이고 집계의 complete 가 false 다.
    고객사 사용자면 된다(Bearer 또는 옛 교환 쿠키 — 권한 표 customer, 역할을 가리지 않는다).
    """
    permitted(request, "inventory_calc")
    if len(body.rows) > services.MAX_ROWS:
        message = f"한 번에 {services.MAX_ROWS}행까지 계산한다 (받은 것: {len(body.rows)}행)"
        return Status(413, ErrorBody(error=ErrorDetail(code="too_many_rows", message=message)))

    result = services.calc_rows(
        rows=[row.model_dump(exclude_unset=True) for row in body.rows],
        tables=body.tables if "tables" in body.model_fields_set else None,
        gwp_set_id=body.gwpSetId,
        group_by=body.groupBy,
    )
    if isinstance(result, services.TablesRejected):
        # 어디가 왜 틀렸는지와 함께 받은 값을 싣는다(TS 원본과 같은 문장, 예: `음수다: "-21"`).
        # 사용자 결정 2026-10-08(MARC-ISSUE-45 의 3번): 「일단 값을 싣고, 보안상 문제가 되면 뺀다」.
        # 되돌릴 때는 p.problem 을 p.summary(값 없는 문장)로 바꾼다.
        # 문장은 순수 층(engines/scope12/engine_1/tables.py)이 TS 와 글자까지 같게 낸다. 길이는 여기서 묶는다(_shown):
        # 음수 갈래 말고는 받은 값이 통째로 문장에 들고(65자 넘는 문자열·객체·긴 kind), where 에는 받은 키가 든다.
        shown = "; ".join(_shown(p.where, p.problem) for p in result.problems[:_SHOWN_PROBLEMS])
        more = len(result.problems) - _SHOWN_PROBLEMS
        tail = f" (외 {more}건)" if more > 0 else ""
        raise ApplicationError("invalid_input", "invalid_tables", f"기준정보 표에 문제가 있다: {shown}{tail}")
    return result.output


# ── Scope 3 ───────────────────────────────────────────────────────────


@router.post(
    "/scope3/shortlist",
    operation_id="inventory_scope3_shortlist",
    response={200: Scope3ShortlistOut, **TOKEN_BODY_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    exclude_unset=True,
    by_alias=True,
    tags=["인벤토리"],
)
def scope3_shortlist(request: HttpRequest, body: Scope3ShortlistIn) -> dict[str, Any]:
    """Scope 3 의 한 품목에 맞을 배출계수 후보를 추린다(낱말 검색). 생성 모델을 부르지 않고 저장하지 않는다.

    후보가 없으면 빈 목록이 아니라 `status: "no_candidates"` 로 답한다.
    패키지에 실린 사본(600건)만 들인 DB 에는 Scope 3 후보가 없다(늘 `no_candidates`).
    고객사 사용자면 된다(Bearer 또는 옛 교환 쿠키 — 역할을 가리지 않는다).
    """
    permitted(request, "inventory_scope3_shortlist")
    given = body.model_dump(exclude_unset=True)
    return actions.scope3_shortlist_output(
        row=given["row"],
        category=body.category,
        keywords=given.get("keywords"),
        basis=given.get("basis"),
        method=given.get("method"),
        bigrams=given.get("bigrams"),
        size=given.get("size"),
        license_text=given.get("license"),
    )


@router.post(
    "/scope3/classify",
    operation_id="inventory_scope3_classify",
    response={200: Scope3ClassifyOut, **TOKEN_BODY_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    exclude_unset=True,
    by_alias=True,
    tags=["인벤토리"],
)
def scope3_classify(request: HttpRequest, body: Scope3ClassifyIn) -> dict[str, Any] | Status[ErrorBody]:
    """행을 품목으로 묶어 묶음마다 Scope 3 범주를 묻는다. 저장하지 않는다.

    ★ 지금 이 경로가 부르는 것은 모의 공급사의 경로(`mock`)뿐이다. 떠 있는 서버에는 그 경로가 없어
    503 `llm_not_configured` 로 답한다(실제 공급사를 부르는 길이 없다). 답이 나올 때는 `synthetic: true` 다.
    수량·금액·무게·거리는 프롬프트에 넣지 않는다. 분류에 실패한 묶음도 200 이다(그 묶음의 status 로 드러난다).
    한 번에 1,000행·20묶음까지다. 넘으면 413 (`too_many_rows` · `too_many_groups`)이고 아무것도 묻지 않는다.
    """
    principal = permitted(request, "inventory_scope3_classify")
    if len(body.rows) > services.SCOPE3_MAX_ROWS:
        # 묶기 전에 건다: 묶음의 상한(20)은 행을 전부 훑어 묶은 뒤에야 알 수 있다.
        message = f"한 번에 {services.SCOPE3_MAX_ROWS}행까지 분류한다 (받은 것: {len(body.rows)}행)"
        return Status(413, ErrorBody(error=ErrorDetail(code="too_many_rows", message=message)))
    rows = [row.model_dump(exclude_unset=True) for row in body.rows]
    result = services.scope3_classify_output(rows=rows, company_id=company_of(principal))
    if isinstance(result, services.Scope3TooManyGroups):
        message = f"한 번에 {services.SCOPE3_MAX_GROUPS}묶음까지 분류한다 (받은 것: {result.count}묶음)"
        return Status(413, ErrorBody(error=ErrorDetail(code="too_many_groups", message=message)))
    if isinstance(result, services.Scope3DuplicateRowId):
        raise ApplicationError("invalid_input", "duplicate_row_id", "rowId 가 겹친다")
    return result.output
