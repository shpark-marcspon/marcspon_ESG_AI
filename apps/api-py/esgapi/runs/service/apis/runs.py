"""runs 의 경로: 실행(run) 다섯. config/api.py 가 이 router 를 /runs 아래에 **세션 인증을 꽂아** 건다.

    POST /runs                        문서 하나(또는 옵션만)를 모듈(흐름)로 돌리는 실행  고객사 사용자
    GET  /runs                        실행 목록(module·status·documentId 로 거름)       고객사 사용자
    GET  /runs/{run_id}               실행 하나와 단계마다의 상태                       고객사 사용자
    GET  /runs/{run_id}/files/{name}  실행의 출력 파일 하나를 내려받는다                고객사 사용자
    GET  /runs/{run_id}/segments      펼침 단계 하나의 구획 목록(data 0 — RM1c)          고객사 사용자

★ 몸은 X1b-1 이 채웠다(계약은 XC — operationId·경로·꼴·함수 이름·docstring 은 바이트 그대로, 응답 선언만 셋의 501 을
  걷고 만들기에 404 를 더함). 만들기의 `resumeFromRunId` 는 X1b-2b 가 채웠다(만들기의 501 선언을 걷음).
★ 하는 일은 셋뿐이다: 요청에서 값을 꺼낸다 → actions·selectors 를 부른다 → 갈래를 응답(schemas)으로 바꾼다. models 를
  import 하지 않는다(`.importlinter` 계약 라).
★ 다른 회사의 실행·문서는 「없다」와 구별되지 않는다(둘 다 404). 거절 code: 문서·실행 없음 NOT_FOUND(문서 경로와 같다),
  문서가 올라오기 전 DOCUMENT_NOT_UPLOADED(409), 모르는 모듈·흐름 UNKNOWN_FLOW(422), 끼움 없는 흐름
  FLOW_NOT_RUNNABLE(422 — 값은 맞는 꼴이나 이 서버에서 못 돈다), 문서 흐름에 documentId 없음
  DOCUMENT_REQUIRED(422), 문서 없는 흐름에 documentId 있음 DOCUMENT_NOT_ACCEPTED(422 — 남의·없는 문서면 그 앞에서
  404, ND1), 옵션 거절 INVALID_OPTIONS(400, 끼움의 글 그대로 — 크기 상한은 흐름마다), 끼움이 판 묶음을 지금 못
  지음 AI_SETTING_UNUSABLE(409, 끼움의 글 그대로 — 그린워싱의 못 받는 저장 판, G2c3).
  이어 돌기(resumeFromRunId): 앞 실행 없음(남의 것 포함) NOT_FOUND(404), 문서·흐름·단계·옵션이 앞과 다름
  RESUME_MISMATCH(422 — 어긋난 칸은 message 에만), 앞이 failed 아님 RESUME_NOT_FAILED(409), 이어 받은 실행이 이미
  있음 RESUME_ALREADY(409), 앞 실행과 같은 launchKey LAUNCH_KEY_REUSED(409 — LK1).
  고른 구획 다시(retrySegments — RM1c): 앞 실행 없음(남의 것 포함) NOT_FOUND(404), resumeFromRunId 와 같이·모듈·
  흐름·문서·옵션·단계가 앞과 다름 RETRY_MISMATCH(422), 앞이 done 아님 RETRY_NOT_DONE(409), 고른 단계가 펼침 밖·
  열쇠가 겹치거나 앞 그 단계에 없음 RETRY_SEGMENTS_UNKNOWN(422), AI 설정·흐름 판이 앞과 다름
  RETRY_VERSION_CHANGED(409 — 처음부터 새 실행으로). 차례는 runs/service/actions/runs.py 머리말.
  Idempotency-Key(IK1): 같은
  열쇠·다른 본문 IDEMPOTENCY_KEY_REUSED(409), 틀린 꼴의 열쇠 VALIDATION_ERROR(422 — 머리 무늬).
★ 만들기의 머리 `Idempotency-Key`(선택, 소문자 UUID — runs/calc/idempotency.py 의 KEY_PATTERN): 같은 사람이 같은
  열쇠·같은 본문으로 다시 보내면 앞 실행을 201 로 돌려준다(새 실행·쪽지·감사 0. 몸의 status 는 지금 값이라 첫 응답과
  다를 수 있다). 범위는 (세션 회사 company_of, 사람)이고, 운영 관리자의 모듈 403 은 열쇠 찾기 앞이다. 머리가 없으면
  IK1 앞과 같다(응답·행·감사·쪽지·검사 차례).
★ 본문 `launchKey`(선택, 소문자 UUID — LK1): 같이 시작한 실행의 묶음 열쇠. 응답은 바뀌지 않고 운영 관리자 실행
  기록(run-logs)이 묶음을 싣는다. Idempotency-Key 의 본문 sha 에 값이 있을 때만 들어간다(없으면 IK1 바이트).
★ 구획 목록(RM1c)은 그 실행이 보이는지(_visible — 없음·남의 것·운영 관리자 모듈 밖 → 404) 뒤에 step 이 그 흐름의
  펼침 단계인지(아니면 422 NOT_A_FANOUT)를 본다. 계획 차례, 산출(data) 0. 행 0(계획 전·계획됨 0)은 빈 쪽이다 —
  가르는 것은 GET /runs/{run_id} 의 segments 칸.
★ 내려받기는 그 실행의 **출력 파일**(단계 NULL)만 낸다 — 단계 산출 파일의 이름은 404. 서버 경유 이진이고 상한은 올림
  상한(max_upload_bytes — 어림)과 같다. 바이트를 읽은 뒤 응답 전에 감사 줄 하나(MARC-ENT-295 — action "download",
  record_event 는 던지지 않는다).
★ 쿠키 인증 객체(`session_cookie`)는 user 에 있고 runs 는 core 처럼 user 를 import 하지 못한다(계약 차). 그래서 이
  파일은 `auth=` 를 적지 않는다: config/api.py 가 `add_router("/runs", router, auth=[company_scoped_auth_or_next,
  session_cookie])` 로 꽂는다(K2b). 경로의 첫 문장은 core/auth/bearer.py 의 `permitted` 다(주체를 꺼내고 권한 표
  core/permissions.py 를 본다. 이름은 core/tests/test_permissions.py 의 CHECKERS 가 본다).
★ 저장소(documents.default_storage·max_upload_bytes)는 runs/service/services/files.py 의 output_bytes 가 **부를 때마다
  모듈 속성으로** 읽는다(테스트가 바꿔 끼운다 — RF1 이 바이트 읽기를 그리로 뺐다).
★ 운영 관리자(결정 MARC-ENT-374·380)는 작업 회사(company_of)에서 OPERATOR_RUN_MODULES(core/permissions.py —
  그 집합의 모듈)의 실행만 다룬다: 다른 모듈의 만들기는 403 forbidden(회사 고르기 전), 목록은 질의가 없으면 그
  모듈들 전부(다른 모듈을 고르면 빈 쪽), 하나·내려받기는 다른 모듈의 실행이면 404 not_found(남의 것과 같다).
"""

from django.http import HttpRequest, HttpResponse
from ninja import HeaderEx, P, Query, Router, Status

from esgapi.core.auth.bearer import company_of, permitted
from esgapi.core.auth.principal import Principal
from esgapi.core.conf import now
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.flows.registry import REGISTRY
from esgapi.core.flows.types import FlowRegistryError
from esgapi.core.permissions import OPERATOR_RUN_MODULES
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.core.service.services.audit import record_event
from esgapi.runs.calc.idempotency import KEY_PATTERN, body_sha256
from esgapi.runs.calc.segments import SegmentCounts
from esgapi.runs.service.actions import runs as actions
from esgapi.runs.service.schemas.runs import (
    RunCreatedOut,
    RunIn,
    RunListQuery,
    RunOut,
    RunPageOut,
    RunSegmentKeyOut,
    RunSegmentListQuery,
    RunSegmentOut,
    RunSegmentPageOut,
    RunStepOut,
    RunStepSegmentsOut,
    RunSummaryOut,
)
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.services import files as file_services

router = Router(tags=["실행"])

# operation_id 는 손으로 적는다(`<모듈>_<동작>`). 표는 esgapi/config/tests/test_api_contract.py 가 못 박는다.

# 내려받기의 200 은 이진 본문이다. response= 에 200 을 적지 않고 이것으로만 선언한다(나머지 응답 선언과 깊게 합쳐진다).
FILE_RESPONSE = {
    "responses": {
        200: {
            "description": "출력 파일의 바이트(Content-Disposition: attachment)",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


def _not_found(message: str) -> ApplicationError:
    return ApplicationError("not_found", "not_found", message)


def _visible(principal: Principal, run: selectors.Run) -> bool:
    """그 주체가 그 실행을 볼 수 있는가. 운영 관리자는 OPERATOR_RUN_MODULES 의 실행만(374·380), 고객사 사용자는 다."""
    return principal.kind != "admin" or run.module in OPERATOR_RUN_MODULES


def _summary_out(run: selectors.Run, document_name: str | None) -> RunSummaryOut:
    return RunSummaryOut(
        id=run.id,
        module=run.module,
        flowId=run.flow_id,
        documentId=run.document_id,
        documentName=document_name,
        status=run.status,  # pyright: ignore[reportArgumentType] — 표의 CHECK 가 넷으로 막는다(runs/models.py)
        createdAt=run.created_at,
        finishedAt=run.finished_at,
    )


def _fanout_names(flow_id: str) -> frozenset[str]:
    """그 흐름의 펼침 단계 이름(RM1b). 등록 밖 흐름은 빈 집합(구획 셈을 싣지 않는다)."""
    try:
        return frozenset(REGISTRY.get(flow_id).fanouts)
    except FlowRegistryError:
        return frozenset()


def _segments_out(status: str, counts: SegmentCounts | None) -> RunStepSegmentsOut:
    """펼침 단계 하나의 구획 셈. 행 0 이면 단계가 done 일 때만 계획됨 0, 그 밖은 계획 전(null)."""
    if counts is None:
        return RunStepSegmentsOut(
            planned=0 if status == "done" else None,
            pending=0,
            running=0,
            done=0,
            failed=0,
            firstStartedAt=None,
            lastFinishedAt=None,
        )
    return RunStepSegmentsOut(
        planned=counts.planned,
        pending=counts.pending,
        running=counts.running,
        done=counts.done,
        failed=counts.failed,
        firstStartedAt=counts.first_started_at,
        lastFinishedAt=counts.last_finished_at,
    )


def _segment_out(line: selectors.SegmentLine) -> RunSegmentOut:
    key = line.key
    return RunSegmentOut(
        position=line.position,
        keySha256=line.key_sha256,
        key=RunSegmentKeyOut(
            kind=str(key["kind"]),
            span=str(key["span"]),
            documentSha256=None if key.get("documentSha256") is None else str(key["documentSha256"]),
            parserVersion=None if key.get("parserVersion") is None else str(key["parserVersion"]),
        ),
        status=line.status,  # pyright: ignore[reportArgumentType] — 표의 CHECK 가 넷으로 막는다(runs/models.py)
        attempts=line.attempts,
        errorCode=line.error_code,
        startedAt=line.started_at,
        finishedAt=line.finished_at,
    )


def _run_out(company_id: int, run: selectors.Run) -> RunOut:
    steps = selectors.step_rows(company_id=company_id, run_id=run.id)
    fanouts = _fanout_names(run.flow_id)
    counts = selectors.segment_counts(company_id=company_id, run_id=run.id) if fanouts else {}
    results = selectors.run_results(company_id=company_id, run_id=run.id)
    files = selectors.run_files(company_id=company_id, run_id=run.id)
    return RunOut(
        id=run.id,
        module=run.module,
        flowId=run.flow_id,
        documentId=run.document_id,
        options=run.options,
        status=run.status,  # pyright: ignore[reportArgumentType]
        steps=[
            RunStepOut(
                step=s.name,
                status=s.status,  # pyright: ignore[reportArgumentType]
                done=s.done,
                total=s.total,
                segments=_segments_out(s.status, counts.get(s.name)) if s.name in fanouts else None,
            )
            for s in steps
        ],
        createdAt=run.created_at,
        startedAt=run.started_at,
        finishedAt=run.finished_at,
        failedStep=run.failed_step,
        errorCode=run.error_code,
        errorMessage=run.error_message,
        resumedFromRunId=run.resumed_from_run_id,
        resultShapes=[r.schema_version for r in results],
        files=[f.name for f in files if f.step is None],
    )


@router.post(
    "",
    operation_id="runs_create",
    response={201: RunCreatedOut, 404: ErrorBody, **TOKEN_BODY_ERROR_RESPONSES},
)
def runs_create(
    request: HttpRequest,
    body: RunIn,
    idempotency_key: HeaderEx[
        str | None,
        P(
            alias="Idempotency-Key",
            pattern=KEY_PATTERN,
            description="선택. 소문자 UUID. 같은 열쇠·같은 본문의 다시 보냄은 앞 실행을 201 로 돌려준다",
        ),
    ] = None,
) -> Status[RunCreatedOut] | HttpResponse:
    """문서 하나를 모듈(흐름)로 돌리는 실행을 새로 만든다(`queued`).
    회사 업무(권한 표 company — 고객사 사용자, 운영 관리자는 작업 회사로 그린워싱·영문번역·데이터 검증·
    중대성평가·원고작성 모듈만).

    `flowId` 가 없으면 그 모듈의 기본 흐름이다. `resumeFromRunId` 를 주면 그 실행의 체크포인트를 참조해 멈춘 단계부터
    도는 새 실행이 된다(앞 실행은 그대로 남는다). `Idempotency-Key` 머리(소문자 UUID)를 주면 같은 사용자·같은 본문의
    다시 보냄은 앞 실행을 201 로 돌려준다(새 실행 0). 같은 열쇠·다른 본문은 409. `launchKey` 는 같이 시작한 실행의
    묶음 열쇠다(이어 돌기에 앞 실행과 같은 열쇠는 409 — 다시 하기는 새 열쇠). `retrySegments` 를 주면 done 실행에서
    고른 구획만 같은 판으로 다시 도는 새 실행이 된다(나머지 구획·앞 단계 산출은 옮겨 쓴다 — 판이 다르면 409).
    """
    principal = permitted(request, "runs_create")
    if principal.kind == "admin" and body.module not in OPERATOR_RUN_MODULES:
        raise ApplicationError("forbidden", "forbidden", "운영 관리자는 이 모듈의 실행을 만들 수 없다")
    retry_in = body.retrySegments
    retry = (
        None
        if retry_in is None
        else actions.SegmentRetry(from_run_id=retry_in.fromRunId, step=retry_in.step, keys=tuple(retry_in.keys))
    )
    idempotency = None
    if idempotency_key is not None:
        sha = body_sha256(
            module=body.module,
            flow_id=body.flowId,
            document_id=body.documentId,
            options=body.options,
            resume_from=body.resumeFromRunId,
            launch_key=body.launchKey,
            retry=None if retry_in is None else (retry_in.fromRunId, retry_in.step, retry_in.keys),
        )
        idempotency = (idempotency_key, sha)
    result = actions.create_run(
        company_id=company_of(principal),
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        module=body.module,
        flow_id=body.flowId,
        document_id=body.documentId,
        options=body.options,
        resume_from=body.resumeFromRunId,
        now=now(),
        idempotency=idempotency,
        launch_key=body.launchKey,
        retry=retry,
    )
    if isinstance(result, actions.RunReplayed):  # 다시 보냄 — 앞 실행, status 는 지금 값(IK1)
        return Status(201, RunCreatedOut(id=result.run.id, status=result.run.status))  # pyright: ignore[reportArgumentType]
    if isinstance(result, actions.KeyReused):
        raise ApplicationError("conflict", "idempotency_key_reused", "같은 Idempotency-Key 로 다른 요청을 보냈다")
    if isinstance(result, actions.DocumentNotFound):
        raise _not_found("그런 문서가 없다")
    if isinstance(result, actions.DocumentNotUploaded):
        raise ApplicationError("conflict", "document_not_uploaded", "문서가 아직 올라오지 않았다(올림 확인 전)")
    if isinstance(result, actions.UnknownFlow):
        raise ApplicationError("validation", "unknown_flow", "그 모듈에 그런 흐름이 없다")
    if isinstance(result, actions.FlowNotRunnable):
        message = f"흐름 {result.flow_id} 은 아직 이 서버에서 돌릴 수 없다"
        raise ApplicationError("validation", "flow_not_runnable", message)
    if isinstance(result, actions.DocumentRequired):
        raise ApplicationError("validation", "document_required", "이 흐름은 문서가 있어야 한다(documentId)")
    if isinstance(result, actions.DocumentNotAccepted):
        raise ApplicationError("validation", "document_not_accepted", "이 흐름은 문서를 받지 않는다(입력은 options)")
    if isinstance(result, actions.OptionsRejected):
        raise ApplicationError("invalid_input", "invalid_options", result.message)
    if isinstance(result, actions.VersionsRejected):
        raise ApplicationError("conflict", "ai_setting_unusable", result.message)
    if isinstance(result, actions.ResumeNotFound):
        raise _not_found("그런 실행이 없다")
    if isinstance(result, actions.ResumeMismatch):
        raise ApplicationError("validation", "resume_mismatch", result.message)
    if isinstance(result, actions.ResumeNotFailed):
        raise ApplicationError("conflict", "resume_not_failed", "실패한 실행만 이어서 돌릴 수 있다")
    if isinstance(result, actions.ResumeAlready):
        raise ApplicationError("conflict", "resume_already", "그 실행을 이어 받은 실행이 이미 있다")
    if isinstance(result, actions.LaunchKeyReused):
        message = "다시 하기는 새 launchKey 로 — 앞 실행의 묶음에 넣을 수 없다"
        raise ApplicationError("conflict", "launch_key_reused", message)
    if isinstance(result, actions.RetryNotFound):
        raise _not_found("그런 실행이 없다")
    if isinstance(result, actions.RetryMismatch):
        raise ApplicationError("validation", "retry_mismatch", result.message)
    if isinstance(result, actions.RetryNotDone):
        raise ApplicationError("conflict", "retry_not_done", "끝난(done) 실행에서만 고른 구획을 다시 돌 수 있다")
    if isinstance(result, actions.RetrySegmentsUnknown):
        raise ApplicationError("validation", "retry_segments_unknown", result.message)
    if isinstance(result, actions.RetryVersionChanged):
        message = "AI 설정·흐름 판이 앞 실행과 달라 고른 구획만 다시 돌 수 없다 — 처음부터 새 실행으로"
        raise ApplicationError("conflict", "retry_version_changed", message)
    return Status(201, RunCreatedOut(id=result.run.id, status=result.run.status))  # pyright: ignore[reportArgumentType]


@router.get("", operation_id="runs_list", response={200: RunPageOut, **TOKEN_ERROR_RESPONSES})
def runs_list(request: HttpRequest, query: Query[RunListQuery]) -> RunPageOut:
    """이 회사의 실행 목록. 새 것 먼저. `module`·`status`·`documentId` 는 전부 「같다」로 거른다."""
    principal = permitted(request, "runs_list")
    company_id = company_of(principal)
    module = query.module
    modules: frozenset[str] | None = None  # 고객사 사용자는 모듈을 가리지 않는다
    if principal.kind == "admin":  # 운영 관리자는 OPERATOR_RUN_MODULES 의 실행만 본다(질의가 없으면 그 모듈들 전부)
        if module is None:
            modules = OPERATOR_RUN_MODULES
        elif module not in OPERATOR_RUN_MODULES:
            return RunPageOut(count=0, isNext=False, results=[])
    page = selectors.run_page(
        company_id=company_id,
        module=module,
        modules=modules,
        status=query.status,
        document_id=query.documentId,
        limit=query.limit,
        offset=query.offset,
    )
    return RunPageOut(
        count=page.count,
        isNext=query.offset + len(page.runs) < page.count,
        results=[_summary_out(run, document_name) for run, document_name in page.runs],
    )


@router.get(
    "/{run_id}",
    operation_id="runs_get",
    response={200: RunOut, 404: ErrorBody, **TOKEN_ERROR_RESPONSES},
)
def runs_get(request: HttpRequest, run_id: int) -> RunOut:
    """실행 하나. `steps` 는 흐름이 선언한 단계 전부를 선언 차례로 싣는다(처음에는 전부 `pending`)."""
    principal = permitted(request, "runs_get")
    company_id = company_of(principal)
    run = selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or not _visible(principal, run):
        raise _not_found("그런 실행이 없다")
    return _run_out(company_id, run)


@router.get(
    "/{run_id}/files/{name}",
    operation_id="runs_file_get",
    response={404: ErrorBody, **TOKEN_ERROR_RESPONSES},
    openapi_extra=FILE_RESPONSE,
)
def runs_file_get(request: HttpRequest, run_id: int, name: str) -> HttpResponse:
    """실행의 출력 파일 하나(`name` 은 `RunOut.files` 의 하나). 본문은 파일의 바이트, Content-Type 은 그 파일의 것."""
    principal = permitted(request, "runs_file_get")
    company_id = company_of(principal)
    if principal.kind == "admin":  # 출력 파일 행에는 모듈이 없다 — 실행을 먼저 본다
        run = selectors.find_run(company_id=company_id, run_id=run_id)
        if run is None or not _visible(principal, run):
            raise _not_found("그런 파일이 없다")
    found = selectors.output_file(company_id=company_id, run_id=run_id, name=name)
    if found is None:
        raise _not_found("그런 파일이 없다")
    data = file_services.output_bytes(found)  # 저장소 없음·거절·닿지 못함은 503 셋으로 던진다
    if data is None:  # 행은 있는데 객체가 없거나 상한을 넘는다 — 내줄 바이트가 없다
        raise _not_found("그런 파일이 없다")
    record_event(
        at=now(),
        company_id=company_id,
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        action="download",
        event="run_file_downloaded",
        result="success",
        target_kind="run",
        target_id=run_id,
        target_label=found.name,
    )
    response = HttpResponse(data, content_type=found.media_type)
    response["Content-Disposition"] = f'attachment; filename="{found.name}"'  # 이름은 [A-Za-z0-9._-] 뿐(표의 CHECK)
    return response


@router.get(
    "/{run_id}/segments",
    operation_id="runs_segments_list",
    response={200: RunSegmentPageOut, 404: ErrorBody, **TOKEN_ERROR_RESPONSES},
)
def runs_segments_list(request: HttpRequest, run_id: int, query: Query[RunSegmentListQuery]) -> RunSegmentPageOut:
    """실행의 펼침 단계 하나의 구획 목록(계획 차례). 산출(data)은 싣지 않는다. `keySha256` 이
    `retrySegments.keys` 에 넣는 값이다. `step` 이 그 흐름의 펼침 단계가 아니면 422."""
    principal = permitted(request, "runs_segments_list")
    company_id = company_of(principal)
    run = selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or not _visible(principal, run):
        raise _not_found("그런 실행이 없다")
    if query.step not in _fanout_names(run.flow_id):
        raise ApplicationError("validation", "not_a_fanout", f"단계 {query.step} 은 이 흐름의 펼침 단계가 아니다")
    page = selectors.segment_page(
        company_id=company_id,
        run_id=run.id,
        step=query.step,
        status=query.status,
        limit=query.limit,
        offset=query.offset,
    )
    return RunSegmentPageOut(
        count=page.count,
        isNext=query.offset + len(page.lines) < page.count,
        results=[_segment_out(line) for line in page.lines],
    )
