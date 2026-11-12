"""그린워싱의 경로 아홉. config/api.py 가 이 router 를 /greenwash 아래에 Bearer 인증(머리가 없으면 옛 교환 쿠키,
K2b)을 꽂아 건다.

    GET /greenwash/runs/{run_id}/result                       한 실행의 결과(greenwash.result@1)            세 역할
    GET /greenwash/runs/{run_id}/result2                      2차 엔진 실행의 결과(greenwash.result@2)       세 역할
    GET /greenwash/runs/{run_id}/review                       한 실행의 검토 상태(greenwash.review@3)       세 역할
    PUT /greenwash/runs/{run_id}/review                       검토 표시·고침·근거 저장(본문 GreenwashReviewUpdate) 회사
    POST /greenwash/runs/{run_id}/items/{item_index}/rejudge  문장 하나 재판단 만들기(202 GreenwashRejudgeCreated) 회사
    GET /greenwash/compare?base=&target=                      두 판(문서)의 비교(greenwash.compare@1)       세 역할
    GET /greenwash/runs/{run_id}/report?confirmed=            엑셀 보고서 내려받기(xlsx 바이트)             세 역할
    GET /greenwash/terms/default                              기본 단어 목록(GreenwashDefaultTerms)         세 역할
    GET /greenwash/checks                                     목록 줄(greenwash.checks@1)                   고객사

몸: 기본 단어 목록(엔진의 상수), 결과·검토 GET·PUT 셋(G1b-1 — service/actions/review.py), 2차 결과(GE1b ④ —
service/actions/engine_g1.run_result2 — 흐름 engine@G1 실행만, E0 실행은 404), 목록 줄(G1b-1 —
service/actions/checks.py), 엑셀 보고서(G1b-2a — service/actions/report.py). 비교는 권한을 본 뒤 501
`not_implemented` 다(MARC-ENT-354 1 — 1차에 문서 비교 없음). 경로는 models 를 import 하지 않는다(`.importlinter`
계약 라) — 갈래를 응답으로 바꿀 뿐이다.
오류: 실행 없음·남의 회사·그린워싱 아님 404 NOT_FOUND · 끝나지 않음 409 RUN_NOT_DONE · dry-run 409 NO_REVIEW ·
확정됨 409 REVIEW_LOCKED · 표시·고침 규칙 어김 400 INVALID_REVIEW(한국어 한 문장) · 보고서는 dry-run 409 NO_REPORT ·
확정본인데 확정 전 409 NOT_CONFIRMED.
응답 꼴은 openapi 에 그대로 올라 프론트가 타입을 받는다.
★ 501 은 오류의 종류(ErrorKind)에 없어 ApplicationError 로 내지 못한다 — error_response 를 직접 돌려준다(XC 와 같은 꼴).
★ id 는 int 다(BigInt 가 최종 계약). 비교의 base·target 은 문서(판) id 이고 대표 실행은 서버가 고른다.
★ 테넌트·사용자 id 는 인증 주체(토큰)에서만 온다(본문·쿼리에 그 칸이 없다).
"""

from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from ninja import Router, Status
from ninja.params.functions import Query
from pydantic import Field

from esgapi.core.auth.bearer import company_of, permitted
from esgapi.core.conf import now
from esgapi.core.exceptions import ApplicationError, ErrorBody, error_response
from esgapi.core.permissions import OPERATOR_RUN_MODULES
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES, StrictIn
from esgapi.greenwash.contracts.checks_shapes import GreenwashChecks
from esgapi.greenwash.contracts.compare_shapes import GreenwashCompareResult
from esgapi.greenwash.contracts.rejudge_shapes import GreenwashRejudgeCreated
from esgapi.greenwash.contracts.result2_shapes import GreenwashResult2
from esgapi.greenwash.contracts.review_shapes import (
    GreenwashReviewEditIn,
    GreenwashReviewEvidenceIn,
    GreenwashReviewMark,
    GreenwashReviewState,
)
from esgapi.greenwash.contracts.shapes import GreenwashResult
from esgapi.greenwash.contracts.terms_shapes import GreenwashDefaultTerms
from esgapi.greenwash.flows.colab_e0 import DEFAULT_TERMS as GREEN_TERMS
from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.service.actions import checks as check_actions
from esgapi.greenwash.service.actions import engine_g1 as g1_actions
from esgapi.greenwash.service.actions import rejudge as rejudge_actions
from esgapi.greenwash.service.actions import report as report_actions
from esgapi.greenwash.service.actions import review as actions
from esgapi.runs.service.actions import runs as run_actions

router = Router(tags=["그린워싱"])

# operation_id 는 손으로 적는다(`<모듈>_<동작>`). 표는 esgapi/config/tests/test_api_contract.py 가 못 박는다.


class GreenwashReviewUpdate(StrictIn):
    """검토 표시·고침 저장의 본문. 모르는 칸을 거절하고 타입을 바꿔 받지 않는다(StrictIn).

    marks 는 그 실행의 표시 전부를 바꿔 넣는다(없는 문장은 미검토가 된다). 고침은 건드리지 않는다.
    edits 는 생략·null 이면 고침 그대로, 목록이면 그 실행의 고침 전부를 바꿔 넣는다([] = 다 지움). 채택·제외는 건드리지
    않는다. 칸은 평평한 값(null = 그 칸 고침 없음)이고 때·사람은 서버가 넣는다.
    state 는 confirmed 나 생략(null)만 받는다 — pending → in_review 는 서버가 바꾸므로 클라이언트가 말할 상태는
    확정뿐이다(그 밖의 값은 꼴 검사에서 400). 서버 규칙(꼴의 규칙은 contracts/review_shapes.py 머리말):
    - 표시나 고침이 하나라도 있으면 상태가 in_review 로 간다. 고침은 서버가 앞뒤 공백을 지우고(판정 사유는 항목마다,
      빈 항목은 버림) AI 값과 같은 칸을 고침 없음으로 접은 뒤에 센다. 둘 다 0 이고 state 가 없으면 pending 그대로,
      in_review 에서 marks = [] 면 in_review 그대로다.
    - confirmed 로 보내면 표시 없는 문장을 서버가 adopted 로 채우고 confirmedAt·confirmedBy 를 넣어 확정·잠근다.
      응답의 marks 는 그 실행 결과의 items 전부다(화면이 다 채워 보내도 결과는 같다).
    - 확정된 실행에 PUT 하면(edits 만 실어도) 409 `REVIEW_LOCKED`(legacyCode `review_locked`).
    - excludeReason 은 1차에 자유 글이다(사유 코드 목록은 마크스폰 확인 전).
    """

    # confirmed 면 확정한다. 생략하거나 null 이면 상태는 서버 규칙대로(표시나 고침이 있으면 in_review).
    state: Literal["confirmed"] | None = None
    marks: list[GreenwashReviewMark]
    # 고친 등급·판정 사유·수정 방향. 생략·null = 고침 그대로, 목록 = 고침 전부 바꿔 넣기([] = 다 지움).
    edits: list[GreenwashReviewEditIn] | None = None
    # 근거 고침(GRJ1 — 지운 AI 칩·더한 조각). 생략·null = 그대로, 목록 = 근거 고침 전부 바꿔 넣기([] = 다 지움).
    evidence: list[GreenwashReviewEvidenceIn] | None = None


def _not_implemented() -> HttpResponse:
    return error_response(501, "not_implemented", "아직 없다")


NOT_FOUND_AND_501: dict[int, type[ErrorBody]] = {404: ErrorBody, 501: ErrorBody}
"""몸이 아직 없는 비교가 선언하는 것: 없는 문서(404), 아직 없는 몸(501)."""
NOT_FOUND: dict[int, type[ErrorBody]] = {404: ErrorBody}
"""몸이 있는 결과·검토 셋·보고서: 없는 실행(404). 409·400 은 TOKEN_*_ERROR_RESPONSES 에 든다."""


def _refused(refusal: actions.Refusal) -> ApplicationError:
    """actions 의 거절 갈래 → 오류(config/api.py 가 상태 코드로 바꾼다)."""
    match refusal:
        case actions.NotFound():
            return ApplicationError("not_found", "not_found", "그런 실행이 없다")
        case actions.RunNotDone():
            return ApplicationError("conflict", "run_not_done", "실행이 아직 끝나지 않았다")
        case actions.NoReview():
            return ApplicationError("conflict", "no_review", "dry-run 실행에는 검토가 없다")
        case actions.ReviewLocked():
            return ApplicationError("conflict", "review_locked", "확정된 검토는 고칠 수 없다")
        case actions.RejudgeRunning():
            return ApplicationError("conflict", "rejudge_running", "다시 판단하고 있는 문장이 있다")
        case actions.InvalidReview(message=message):
            return ApplicationError("invalid_input", "invalid_review", message)


def _report_refused(refusal: report_actions.Refusal) -> ApplicationError:
    """보고서의 거절 갈래 → 오류. 404·RUN_NOT_DONE 은 결과·검토와 같은 글이다."""
    match refusal:
        case actions.NotFound() | actions.RunNotDone():
            return _refused(refusal)
        case report_actions.NoReport():
            return ApplicationError("conflict", "no_report", "dry-run 실행에는 엑셀 보고서가 없다")
        case report_actions.NotConfirmed():
            return ApplicationError("conflict", "not_confirmed", "검토를 확정한 뒤에 확정본을 받을 수 있다")


RunId = Annotated[int, Field(description="실행 id")]


@router.get(
    "/runs/{run_id}/result",
    operation_id="greenwash_result_get",
    response={200: GreenwashResult, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def result_get(request: HttpRequest, run_id: RunId) -> dict[str, object]:
    """한 실행의 결과(greenwash.result@1). 세 역할 모두 본다."""
    principal = permitted(request, "greenwash_result_get")
    found = actions.run_result(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone):
        raise _refused(found)
    return found


@router.get(
    "/runs/{run_id}/result2",
    operation_id="greenwash_result2_get",
    response={200: GreenwashResult2, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def result2_get(request: HttpRequest, run_id: RunId) -> dict[str, object]:
    """2차 엔진(greenwash.engine@G1) 실행의 결과(greenwash.result@2). 세 역할 모두 본다. 1차(E0) 실행·없는 실행·남의
    회사는 404, 끝나지 않으면 409 RUN_NOT_DONE. 실행 시작 스위치와 무관(실행이 없으면 404)."""
    principal = permitted(request, "greenwash_result2_get")
    found = g1_actions.run_result2(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone):
        raise _refused(found)
    return found


@router.get(
    "/runs/{run_id}/review",
    operation_id="greenwash_review_get",
    response={200: GreenwashReviewState, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def review_get(request: HttpRequest, run_id: RunId) -> GreenwashReviewState:
    """한 실행의 검토 상태(greenwash.review@2). 표시가 없으면 state = pending, marks = [], 고침이 없으면 edits = [].
    AI 원본(고치기 전의 등급·판정 사유·수정 방향)은 결과 GET 의 items[itemIndex] 다."""
    principal = permitted(request, "greenwash_review_get")
    found = actions.review_state(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, actions.NotFound | actions.RunNotDone | actions.NoReview):
        raise _refused(found)
    return found


@router.put(
    "/runs/{run_id}/review",
    operation_id="greenwash_review_put",
    response={200: GreenwashReviewState, **NOT_FOUND, **TOKEN_BODY_ERROR_RESPONSES},
)
def review_put(request: HttpRequest, run_id: RunId, body: GreenwashReviewUpdate) -> GreenwashReviewState:
    """검토 표시·고침을 저장하고 새 상태를 돌려준다. 회사 업무를 하는 누구나(권한 표 COMPANY — 고객사 사용자와 작업
    회사의 운영 관리자, MARC-ENT-374).

    서버 규칙: 표시나 (정규화 뒤) 고침이 있으면 in_review · 고친 칸마다 editedAt·editedBy 는 그 칸 값이 바뀐 PUT 의
    때·사람 · state = confirmed 면 미검토를 adopted 로 채우고 confirmedAt·confirmedBy 를 넣어 잠근다(응답 marks = 결과
    items 전부). 오류: 확정된 실행 409 `REVIEW_LOCKED`(legacyCode `review_locked`) · 실행이 done 이 아님 409
    `RUN_NOT_DONE`(legacyCode `run_not_done`) · dry-run 실행 409 `NO_REVIEW`(legacyCode `no_review`) · 확정하려는데
    대기·진행 중인 재판단이 있음 또는 재판단이 대기·진행 중인 문장의 근거를 바꿈 409 `REJUDGE_RUNNING`(legacyCode
    `rejudge_running`) · 표시·고침 규칙 어김 400
    `INVALID_REVIEW`(legacyCode `invalid_review`, 한국어 한 문장) · 실행이 없거나 남의 회사 404.
    409 는 TOKEN_BODY_ERROR_RESPONSES(⊃ ERROR_RESPONSES)에 든다.
    """
    principal = permitted(request, "greenwash_review_put")
    saved = actions.put_review(
        company_id=company_of(principal),
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        run_id=run_id,
        confirm=body.state == "confirmed",
        marks=body.marks,
        edits=body.edits,
        evidence=body.evidence,
        now=now(),
    )
    if isinstance(saved, actions.NotFound | actions.RunNotDone | actions.NoReview | actions.ReviewLocked):
        raise _refused(saved)
    if isinstance(saved, actions.RejudgeRunning):
        raise _refused(saved)
    if isinstance(saved, actions.InvalidReview):
        raise _refused(saved)
    return saved


ItemIndex = Annotated[int, Field(ge=0, description="결과 items 의 차례(0부터)")]


def _rejudge_refused(refusal: rejudge_actions.Refusal) -> ApplicationError:
    """재판단 만들기의 거절 → 오류. 규칙 1·2·3·5 는 검토와 같은 글, create_run 의 거절은 POST /runs 와 같은
    kind·code(71 조건 (3) — 이 길에서 닿는 것은 옵션·판 거절뿐이다)."""
    match refusal:
        case actions.NotFound() | actions.RunNotDone() | actions.NoReview() | actions.ReviewLocked():
            return _refused(refusal)
        case rejudge_actions.ItemNotFound():
            return ApplicationError("not_found", "not_found", "그런 문장이 없다")
        case actions.RejudgeRunning():
            return ApplicationError("conflict", "rejudge_running", "그 문장은 지금 다시 판단하고 있다")
        case rejudge_actions.NothingToRejudge():
            return ApplicationError("conflict", "nothing_to_rejudge", "근거가 바뀌지 않아 다시 판단할 것이 없다")
        case rejudge_actions.CreateRefused(refusal=created):
            if isinstance(created, run_actions.OptionsRejected):
                return ApplicationError("invalid_input", "invalid_options", created.message)
            if isinstance(created, run_actions.VersionsRejected):
                return ApplicationError("conflict", "ai_setting_unusable", created.message)
            raise RuntimeError(f"재판단 만들기에서 닿지 않는 create_run 거절: {type(created).__name__}")


@router.post(
    "/runs/{run_id}/items/{item_index}/rejudge",
    operation_id="greenwash_item_rejudge",
    response={202: GreenwashRejudgeCreated, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def item_rejudge(request: HttpRequest, run_id: RunId, item_index: ItemIndex) -> Status[GreenwashRejudgeCreated]:
    """검토 화면의 [재판단]: 문장 하나를 지금 근거(남긴 AI 칩 + 더한 조각)로, 그 점검을 돌린 AI 설정 판 그대로 한 번
    다시 판단하는 실행을 만든다(202 — 대기). 본문 없음. 진행·결과는 검토 GET(greenwash.review@3)의 rejudges 로 읽는다.
    회사 업무를 하는 누구나(권한 표 COMPANY — 검토 PUT 과 같다).

    오류: 실행이 없거나 남의 회사·문장 번호가 결과 밖 404 · 실행이 done 이 아님 409 `RUN_NOT_DONE` · dry-run 409
    `NO_REVIEW` · 확정된 검토 409 `REVIEW_LOCKED` · 그 문장의 재판단이 대기·진행 중 409 `REJUDGE_RUNNING` · 근거가
    마지막 판단 때와 같음 409 `NOTHING_TO_REJUDGE` · 점검의 AI 설정 판을 지금 쓸 수 없음 409 `AI_SETTING_UNUSABLE`.
    """
    principal = permitted(request, "greenwash_item_rejudge")
    if principal.kind == "admin" and "greenwash" not in OPERATOR_RUN_MODULES:  # POST /runs 와 같은 검사(71 조건 (2))
        raise ApplicationError("forbidden", "forbidden", "운영 관리자는 이 모듈의 실행을 만들 수 없다")
    made = rejudge_actions.create_rejudge(
        company_id=company_of(principal),
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        run_id=run_id,
        item_index=item_index,
        now=now(),
    )
    if not isinstance(made, rejudge_actions.RejudgeCreated):
        raise _rejudge_refused(made)
    return Status(202, {"rejudgeRunId": made.rejudge_run_id})


@router.get(
    "/compare",
    operation_id="greenwash_compare_get",
    response={200: GreenwashCompareResult, **NOT_FOUND_AND_501, **TOKEN_ERROR_RESPONSES},
)
def compare_get(
    request: HttpRequest,
    base: Annotated[int, Field(description="앞 판(문서) id")],
    target: Annotated[int, Field(description="이번 판(문서) id")],
) -> HttpResponse:
    """두 판(문서)의 비교(greenwash.compare@1). 판마다 대표 실행은 서버가 고른다. 세 역할 모두 본다. 지금은 501."""
    permitted(request, "greenwash_compare_get")
    return _not_implemented()


# 엑셀 보고서의 200 은 xlsx 바이트다. response= 에 200 을 적지 않고 이것으로만 선언한다(core 의 runs.FILE_RESPONSE 꼴).
XLSX = xlsx.MEDIA_TYPE
REPORT_RESPONSE = {
    "responses": {
        200: {
            "description": "엑셀 보고서의 바이트(Content-Disposition: attachment)",
            "content": {XLSX: {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


@router.get(
    "/runs/{run_id}/report",
    operation_id="greenwash_report_get",
    response={**NOT_FOUND, **TOKEN_ERROR_RESPONSES},
    openapi_extra=REPORT_RESPONSE,
)
def report_get(
    request: HttpRequest,
    run_id: RunId,
    confirmed: bool = Query(False, description="true 면 채택한 문장만(확정본). 그 실행이 확정 전이면 409"),
) -> HttpResponse:
    """한 실행의 엑셀 보고서 내려받기(xlsx 한 파일, Content-Disposition: attachment). 세 역할 모두 받는다.

    엑셀은 그 실행 결과에서 늘 다시 짓는다. 확정본(confirmed = true)은 채택한 문장만 싣고 요약을 그것으로 다시 센다.
    내려받을 때마다 감사 download 한 줄.

    오류: confirmed = true 인데 확정 전 409 `NOT_CONFIRMED`(legacyCode `not_confirmed`) · 실행이
    done 이 아님 409 `RUN_NOT_DONE`(legacyCode `run_not_done`) · dry-run 실행(엑셀이 없다) 409
    `NO_REPORT`(legacyCode `no_report`) · 실행이 없거나 남의 회사 404.
    """
    principal = permitted(request, "greenwash_report_get")
    made = report_actions.report(
        company_id=company_of(principal),
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        run_id=run_id,
        confirmed=confirmed,
        now=now(),
    )
    if not isinstance(made, report_actions.Report):
        raise _report_refused(made)
    response = HttpResponse(made.content, content_type=xlsx.MEDIA_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{report_actions.FILE_NAME}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@router.get(
    "/terms/default",
    operation_id="greenwash_terms_default",
    response={200: GreenwashDefaultTerms, **TOKEN_ERROR_RESPONSES},
)
def terms_default(request: HttpRequest) -> GreenwashDefaultTerms:
    """기본 단어 목록(노트북의 GREEN_TERMS, 차례 그대로). 세 역할 모두 본다. 테넌트 행을 읽지 않는 공용 값이다.

    화면은 사용자가 더하는 단어가 이 목록과 겹치는지 키 규칙(GreenwashDefaultTerms 의 설명)으로 견주어 막는다.
    """
    permitted(request, "greenwash_terms_default")
    return {"terms": list(GREEN_TERMS)}


@router.get(
    "/checks",
    operation_id="greenwash_checks_get",
    response={200: GreenwashChecks, **TOKEN_ERROR_RESPONSES},
)
def checks_get(request: HttpRequest) -> GreenwashChecks:
    """그린워싱 문서 목록(GW-01)의 원재료(greenwash.checks@1): 그 회사의 그린워싱 실행 전부와 그 문서들, 지금 사용자
    id, 회사 이름. 차례는 정하지 않는다(화면이 정렬한다). 회사 업무를 하는 누구나(권한 표 COMPANY — 고객사 사용자와
    작업 회사의 운영 관리자).

    levelCounts·review 는 끝난 실행만 값이다. levelCounts 는 효력 등급(고친 등급 ?? AI 등급)으로 센 수다(G1b-3).
    reportYear·previousDocumentId 는 문서의 칸 그대로(비어 있으면 null), pageCount 는 그 문서의 끝난 실행 결과에서
    온다(없으면 null).
    """
    principal = permitted(request, "greenwash_checks_get")
    return check_actions.checks(company_id=company_of(principal), user_id=int(principal.user_id))
