"""중대성평가 IRO 의 경로 여섯(밴드 IR3b·IR3c·IRW2·IRS3). config/api.py 가 이 router 를 /materiality 아래에 Bearer
인증(머리가 없으면 옛 교환 쿠키, K2b)을 꽂아 건다(/greenwash·/translation·/dataverify 와 같은 auth).

    GET /materiality/runs/{run_id}/result          한 실행의 결과(result@2 — 고친 판)   회사 업무(고객사·운영 관리자)
    GET /materiality/runs/{run_id}/result/edits    결과 고침(result-edits@1)            회사 업무(같음)
    POST /materiality/runs/{run_id}/result/edits   글 칸 고침 저장(MaterialityResultEditsIn)  회사 업무(같음)
    GET /materiality/runs/{run_id}/report          고친 판 최종 엑셀(xlsx 바이트)        회사 업무(같음)
    GET /materiality/runs                   실행 목록 한 쪽(새 것 먼저 — IR3c)    회사 업무(고객사 사용자·운영 관리자)
    POST /materiality/value-chain/read      가치사슬 엑셀(맨 바이트) → 행 | 거절(둘 다 200 — IRW2)  회사 업무(같음)

몸: service/actions/result.py(결과 — 지금 고침을 덮은 판) · service/actions/edits.py(고침 읽기·저장 — IRS3) ·
service/actions/report.py(고친 판 최종 엑셀 — IRS3 ③, 감사 download 한 줄) ·
service/actions/runs.py(목록 — 거름은 status 여러 값·mine, 검색·기간 거름은 없다) ·
service/actions/value_chain.py(가치사슬 읽기 — 상태 없음, 테넌트 행을 읽지 않아 company_of 를 부르지 않는다. 운영
관리자도 회사를 고르지 않고 같은 결과).
경로는 models 를 import 하지 않는다(`.importlinter` 계약 라) — 갈래를 응답으로 바꿀 뿐이다. 실행 만들기·상태·엑셀은
runs 의 경로(POST /runs {module:"materiality"}·GET /runs/{id}·
GET /runs/{id}/files/{materiality-websearch.xlsx|materiality-final-report.xlsx})다.
운영 관리자는 작업 회사(company_of)의 실행을 읽는다(MARC-ENT-419).
오류: 실행 없음·남의 회사·중대성평가 아님·끝났는데 @2 결과 없음 404 NOT_FOUND · 끝나지 않음(queued·processing·
failed) 409 RUN_NOT_DONE(데이터 검증·영문번역 결과 경로와 같은 code·글). 실패의 까닭은 GET /runs/{id} 다.
고침 저장: 낡은 baseRevision 409 EDIT_CONFLICT(웹은 GET …/result/edits 로 다시 읽는다) · 주소·값 규칙 어김 400
INVALID_EDIT(한국어 한 문장, 첫 어긋난 changes 차례) · 본문 꼴 422.
★ id 는 int 다. 테넌트 id 는 인증 주체(토큰)에서만 온다(쿼리·본문에 그 칸이 없다).
"""

from typing import Annotated

from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Schema
from pydantic import Field

from esgapi.core.auth.bearer import company_of, permitted
from esgapi.core.conf import now
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES, StrictIn
from esgapi.materiality.contracts.edit_shapes import (
    CHANGES_MAX,
    CHANGES_MIN,
    MaterialityResultEditChange,
    MaterialityResultEdits,
)
from esgapi.materiality.contracts.run_list_shapes import MaterialityRunPage, MaterialityRunStatus
from esgapi.materiality.contracts.shapes import MaterialityResult2
from esgapi.materiality.contracts.value_chain_shapes import MaterialityValueChainRead
from esgapi.materiality.outputs import final_xlsx
from esgapi.materiality.service.actions import edits as edit_actions
from esgapi.materiality.service.actions import report as report_actions
from esgapi.materiality.service.actions import result as actions
from esgapi.materiality.service.actions import runs as run_actions
from esgapi.materiality.service.actions import value_chain as value_chain_actions

router = Router(tags=["중대성평가 IRO"])

# operation_id 는 손으로 적는다(`<모듈>_<동작>`). 표는 esgapi/config/tests/test_api_contract.py 가 못 박는다.

NOT_FOUND: dict[int, type[ErrorBody]] = {404: ErrorBody}
"""없는 실행(404). 409 는 TOKEN_ERROR_RESPONSES 에 든다."""


def _refused(refusal: actions.Refusal) -> ApplicationError:
    """actions 의 거절 갈래 → 오류(config/api.py 가 상태 코드로 바꾼다)."""
    match refusal:
        case actions.NotFound():
            return ApplicationError("not_found", "not_found", "그런 실행이 없다")
        case actions.RunNotDone():
            return ApplicationError("conflict", "run_not_done", "실행이 아직 끝나지 않았다")


RunId = Annotated[int, Field(description="실행 id")]


@router.get(
    "/runs/{run_id}/result",
    operation_id="materiality_result_get",
    response={200: MaterialityResult2, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def result_get(request: HttpRequest, run_id: RunId) -> dict[str, object]:
    """한 실행의 결과(materiality.result@2). 1부(토픽·서브토픽 점수)와 2부(IRO)를 싣고, 단계가 끝나지 않은 실행은
    409 다."""
    principal = permitted(request, "materiality_result_get")
    found = actions.run_result(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone):
        raise _refused(found)
    return found


class MaterialityResultEditsIn(StrictIn):
    """결과 글 칸 고침 저장의 본문. 모르는 칸을 거절하고 타입을 바꿔 받지 않는다(StrictIn).

    baseRevision 은 화면이 읽은 GET …/result/edits 의 revision 이다(다르면 409 EDIT_CONFLICT — 다시 읽고 다시 보낸다).
    changes 는 고칠 칸마다 하나(1~200개). 칸 주소(JSON Pointer)·값의 규칙은 MaterialityResultEditChange 의 설명과
    머리말(contracts/edit_shapes.py). 맥락 항목(title·summary·url)은 같은 토픽·쪽·원본 url 의 항목 전부와 Pathway
    사본에 퍼진다. 한 저장 안에 같은 칸(같은 묶음)을 둘 보내면 400.
    """

    baseRevision: int = Field(ge=0)
    changes: list[MaterialityResultEditChange] = Field(min_length=CHANGES_MIN, max_length=CHANGES_MAX)


def _edit_refused(refusal: edit_actions.Refusal) -> ApplicationError:
    match refusal:
        case actions.NotFound() | actions.RunNotDone():
            return _refused(refusal)
        case edit_actions.Invalid(message=message):
            return ApplicationError("invalid_input", "invalid_edit", message)
        case edit_actions.EditConflict(revision=revision):
            return ApplicationError(
                "conflict", "edit_conflict", f"다른 사람이 먼저 고쳤다(지금 revision {revision}) — 다시 읽고 고친다"
            )


@router.get(
    "/runs/{run_id}/result/edits",
    operation_id="materiality_result_edits_get",
    response={200: MaterialityResultEdits, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def result_edits_get(request: HttpRequest, run_id: RunId) -> MaterialityResultEdits:
    """한 실행의 결과 고침(materiality.result-edits@1): 지금 revision 과 지금 값이 원문과 다른 칸(바른 주소·지금 값·AI
    원문·고친 때·고친 사람). 고침이 없으면 revision 0, edits []."""
    principal = permitted(request, "materiality_result_edits_get")
    found = edit_actions.edits_state(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone):
        raise _refused(found)
    return found


@router.post(
    "/runs/{run_id}/result/edits",
    operation_id="materiality_result_edits_post",
    response={200: MaterialityResultEdits, **NOT_FOUND, **TOKEN_BODY_ERROR_RESPONSES},
)
def result_edits_post(request: HttpRequest, run_id: RunId, body: MaterialityResultEditsIn) -> MaterialityResultEdits:
    """결과 글 칸 고침 저장. 저장하면 revision 이 하나 오르고 응답은 저장 뒤의 materiality.result-edits@1 이다. AI 원본
    (결과 행·저장 파일)은 그대로이고, GET …/result 와 GET …/report 가 고친 판을 낸다. 원문과 같은 값을 보내면 그 칸은
    되돌려진다(edits 에서 빠짐).

    오류: baseRevision 이 지금과 다름 409 `EDIT_CONFLICT`(legacyCode `edit_conflict`) · 주소·값 규칙 어김 400
    `INVALID_EDIT`(legacyCode `invalid_edit`) · 끝나지 않은 실행 409 `RUN_NOT_DONE` · 없는 실행·남의 회사 404."""
    principal = permitted(request, "materiality_result_edits_post")
    saved = edit_actions.save(
        company_id=company_of(principal),
        user_id=int(principal.user_id),
        run_id=run_id,
        base_revision=body.baseRevision,
        changes=[(change["pointer"], change["value"]) for change in body.changes],
        now=now(),
    )
    if not isinstance(saved, dict):
        raise _edit_refused(saved)
    return saved


REPORT_RESPONSE = {
    "responses": {
        200: {
            "description": "고친 판 최종 엑셀의 바이트(Content-Disposition: attachment)",
            "content": {final_xlsx.MEDIA: {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


@router.get(
    "/runs/{run_id}/report",
    operation_id="materiality_report_get",
    response={**NOT_FOUND, **TOKEN_ERROR_RESPONSES},
    openapi_extra=REPORT_RESPONSE,
)
def report_get(request: HttpRequest, run_id: RunId) -> HttpResponse:
    """한 실행의 최종 엑셀(materiality-final-report.xlsx) — 지금 고침을 덮은 고친 판으로 늘 다시 짓는다(시트 넷,
    RAW_JSON 도 고친 판). 저장된 출력 파일(GET /runs/{id}/files/…)은 AI 원본 판 그대로다. 내려받을 때마다 감사
    download 한 줄.

    오류: 끝나지 않은 실행 409 `RUN_NOT_DONE` · 없는 실행·남의 회사 404."""
    principal = permitted(request, "materiality_report_get")
    made = report_actions.report(
        company_id=company_of(principal),
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        run_id=run_id,
        now=now(),
    )
    if not isinstance(made, report_actions.Report):
        raise _refused(made)
    response = HttpResponse(made.content, content_type=final_xlsx.MEDIA)
    response["Content-Disposition"] = f'attachment; filename="{report_actions.FILE_NAME}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


class MaterialityRunListQuery(Schema):
    """`GET /materiality/runs` 의 조회 인자. count·isNext 는 거른 뒤 실행 수다."""

    status: list[MaterialityRunStatus] | None = Field(
        default=None, description="이 상태들만(여러 번 — ?status=queued&status=processing). 없으면 전부"
    )
    mine: bool = Field(default=False, description="true 면 내가 만든 실행만(운영 관리자도 같은 규칙)")
    limit: int = Field(default=20, ge=1, le=20)
    offset: int = Field(default=0, ge=0)


@router.get(
    "/runs",
    operation_id="materiality_runs_list",
    response={200: MaterialityRunPage, **TOKEN_ERROR_RESPONSES},
)
def runs_list(request: HttpRequest, query: Query[MaterialityRunListQuery]) -> MaterialityRunPage:
    """이 회사의 중대성평가 IRO 실행 한 쪽(새 것 먼저). 줄마다 기업명·산업·토픽 수·조사 기간·최신 이슈 반영·만든
    사람·실패/지금 단계·(끝났으면) 환경·사회 영향 줄 수와 재무 영향 경로 줄 수(요약 materiality.digest@1)를 싣고, 토픽
    이름·옵션 본문·결과 본문은 싣지 않는다."""
    principal = permitted(request, "materiality_runs_list")
    return run_actions.runs(
        company_id=company_of(principal),
        user_id=int(principal.user_id),
        statuses=query.status,
        mine=query.mine,
        limit=query.limit,
        offset=query.offset,
    )


# 가치사슬 표 엑셀은 맨 바이트 본문이다(multipart 경로가 없다 — 영문번역 용어집 읽기와 같은 꼴). 본문 꼴은 schema 가
# 아니라 이것으로만 선언한다. 본문 상한은 DATA_UPLOAD_MAX_MEMORY_SIZE(넘으면 config/api.py 의 413 body_too_large).
VALUE_CHAIN_READ_BODY = {
    "requestBody": {
        "required": True,
        "content": {value_chain_actions.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
    }
}


@router.post(
    "/value-chain/read",
    operation_id="materiality_value_chain_read",
    response={200: MaterialityValueChainRead, **TOKEN_BODY_ERROR_RESPONSES},
    openapi_extra=VALUE_CHAIN_READ_BODY,
)
def value_chain_read(request: HttpRequest) -> dict[str, object]:
    """가치사슬 표 엑셀 읽기(열 이름 「사업 부문·사업 내용·밸류체인·이해관계자·관련 비즈니스 활동」 — 「value chain」
    이름이 든 첫 보이는 시트, 위 20행 안의 머리, 병합 칸 채움). 본문은 xlsx 파일의 바이트 그대로다. 읽었으면
    `{ok: true, rows, rowCount}`, 못 읽었으면 `{ok: false, kind, row, column, message}` — 둘 다 200(빈 본문·JSON 본문은
    not_xlsx). 아무것도 저장하지 않는다. 웹은 사용자가 고친 표를 실행 입력 input.valueChain 에 싣는다."""
    permitted(request, "materiality_value_chain_read")
    return dict(value_chain_actions.read(request.body))
