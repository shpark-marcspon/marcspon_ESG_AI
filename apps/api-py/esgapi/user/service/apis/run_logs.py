"""user 의 운영 관리자 실행 기록 경로(AU1b-2 — AD-04): 운영 관리자 전용 실행 목록과 이번 달 지표 다섯, 목록과 같은
거르기의 전부를 엑셀 한 파일로 내려받기(AD4S — GET /run-logs/export). 실행은 runs 의
표(run_runs)이고 읽기는 runs 의 selector(operator_run_page·operator_run_cohort — 첫 줄이 권한 검사)다. LLM 합은 core 의
selector(usage_by_run), 셈은 core 의 순수 calc(run_metrics)다. 이 경로는 회사를 고르고, 쪽·무리를 받고, 사람 이름을
지금 값으로 풀고, 지표를 센다.

차례(/audit-logs 와 같다): 인증(Bearer) → permitted(is_initial → 표) → 회사 고르기(users.py 의 chosen_company — 같은
규칙) → 읽기 → LLM 합 → 이름 풀기(user 의 selectors.people_of — 고른 회사의 고객사 사용자 먼저, 못 푼 id 는 운영
관리자. 작업 회사로 실행을 만든 운영 관리자 — MARC-ENT-374). 고객사 사용자의 403 은 회사 세기·DB 읽기 0 이다.
models 를 직접 import 하지 않는다(`.importlinter` 계약 라).

처리 시간은 대기 포함(finished_at − created_at, 초 버림 — MARC-ENT-327). 지표의 「이번 달」은 서버 시계(core.conf.now)의
KST 그달이고 셈 규칙은 core/calc/run_metrics.py 의 머리글(처분 ⑤). 비용은 실행에 붙은 AI 호출만이다(동기 계산의 호출은
빠진다 — 추정). 실행기는 지금 모의 공급사만 싣는다(MARC-ENT-262) — 실호출 전의 토큰·비용은 모의 값이다.
날짜는 DATE_FLOOR~DATE_CEILING 밖이면 422(audit.py 와 같은 범위). 검토·AI 설정 칸과 review 거르기는 runs 의 selector 가
모듈의 원천(runs/extras.py)으로 채우고 거른다(AD4S).
내보내기(AD4S ②): 같은 거르기의 전부를 셈하고 RUN_LOG_EXPORT_MAX 를 넘으면 409 run_log_export_too_large(행 읽기 0·감사
0). 아니면 엑셀(user/service/utils/run_log_xlsx.py — 순수)을 짓고 감사 download 한 줄(run_logs_exported)을 남긴다.
응답은 Content-Disposition attachment(filename* UTF-8)·nosniff·Cache-Control no-store(회사 자료).
상세(AD4D — GET /run-logs/{run_id}): 같은 차례 → runs 의 operator_run_detail(없거나 남의 회사 = 404 run_not_found,
둘을 가르지 않는다) → LLM 합(usage_by_run — 줄 칸과 같은 셈)·단계별 합(usage_by_step) → 이름 풀기. run_id 는 int
변환기라 글자 경로(/run-logs/export·/metrics)와 겹치지 않고, 숫자가 아니면 경로 없음 404 다.
결과 파일 받기(RF1 — GET /run-logs/{run_id}/files/{name}, MARC-ENT-395): 같은 차례 → runs 의 operator_run_file(모든
모듈 — 상세와 같다. 흐름의 출력 파일(step NULL)만, 단계 산출 파일은 이름이 모호해 404 run_file_not_found) → 바이트는
runs 의 services/files.py 의 output_bytes(고객사 runs_file_get 과 같은 503 셋) → 바이트를 얻은 뒤에만 감사 download
한 줄(run_file_downloaded, company_id = 고른 회사 — 실패 갈래는 감사 0). 응답은 Content-Disposition attachment(이름은
표의 CHECK 로 [A-Za-z0-9._-] 뿐이라 따옴표 꼴)·nosniff·Cache-Control no-store(내보내기와 같다).
"""

from datetime import date
from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils import http as django_http
from ninja import Router
from ninja.params.functions import Query

from esgapi.core.auth.bearer import access_token_auth, permitted
from esgapi.core.calc.run_metrics import MetricRun, RunUsage, duration_sec, metrics, month_bounds
from esgapi.core.conf import app_config, now
from esgapi.core.exceptions import ApplicationError
from esgapi.core.schemas import to_seoul_iso
from esgapi.core.service.selectors import llm_usage
from esgapi.core.service.services.audit import record_event
from esgapi.runs.service.schemas.runs import RunStatus
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.services import files as file_services
from esgapi.user.service.apis.audit import DATE_CEILING, DATE_FLOOR
from esgapi.user.service.apis.users import chosen_company, company_ports
from esgapi.user.service.schemas.run_logs import (
    ReviewState,
    RunAiSettingOut,
    RunLogDetailOut,
    RunLogFileOut,
    RunLogOut,
    RunLogPageOut,
    RunLogStepOut,
    RunMetricsOut,
)
from esgapi.user.service.schemas.users import USER_ADMIN_ERROR_RESPONSES
from esgapi.user.service.selectors import user as selectors
from esgapi.user.service.utils import run_log_xlsx

router = Router(tags=["사용자 관리"])

FORBIDDEN = "운영 관리자만 실행 기록을 본다"
RUN_NOT_FOUND = "그 실행이 없다"
RUN_FILE_NOT_FOUND = "그 결과 파일이 없다"
# 감독 f8 10-22 값(어림). 셈과 읽기 사이에 실행이 늘면 상한을 조금 넘겨 읽을 수 있다 — 무해.
RUN_LOG_EXPORT_MAX = 10_000
# 내보내기의 200 은 xlsx 바이트다. response= 에 200 을 적지 않고 이것으로만 선언한다(greenwash 보고서와 같은 꼴).
EXPORT_RESPONSE = {
    "responses": {
        200: {
            "description": "실행 기록 엑셀(Content-Disposition: attachment, 「실행기록_YYYY-MM-DD_HHMM.xlsx」 KST)",
            "content": {run_log_xlsx.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}
# 결과 파일 받기의 200 은 이진 본문이다(runs 의 runs_file_get 과 같은 꼴 — import 하지 않는다).
FILE_RESPONSE = {
    "responses": {
        200: {
            "description": "실행 출력 파일의 바이트(Content-Disposition: attachment)",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


def run_out(
    run: operator_selectors.OperatorRun, usage: dict[int, RunUsage], names: dict[int, tuple[str, str]]
) -> RunLogOut:
    used = usage.get(run.id)
    known = names.get(run.created_by_user_id)
    return RunLogOut(
        id=run.id,
        module=run.module,
        flowId=run.flow_id,
        documentId=run.document_id,
        documentName=run.document_name,
        status=run.status,  # pyright: ignore[reportArgumentType] — DB 의 CHECK 가 네 값으로 묶는다
        createdAt=run.created_at,
        startedAt=run.started_at,
        finishedAt=run.finished_at,
        createdByUserId=run.created_by_user_id,
        createdByName=None if known is None else known[1],
        createdByUsername=None if known is None else known[0],
        durationSec=duration_sec(run.created_at, run.finished_at),
        tokens=0 if used is None else used.tokens,
        costUsd=0.0 if used is None else float(used.cost_usd),
        isTest=run.purpose == "test",
        review=run.review,  # pyright: ignore[reportArgumentType] — selector 가 REVIEW_STATES 셋으로 묶는다
        aiSetting=None if run.ai_setting is None else RunAiSettingOut(id=run.ai_setting[0], name=run.ai_setting[1]),
        launchKey=run.launch_key,
        launchFirstRunId=run.launch_first_run_id,
        launchIndex=run.launch_index,
        launchSize=run.launch_size,
        resumedFromRunId=run.resumed_from_run_id,
    )


@router.get(
    "/run-logs",
    operation_id="user_run_log_list",
    response={200: RunLogPageOut, **USER_ADMIN_ERROR_RESPONSES},
    auth=access_token_auth,
)
def run_log_list(
    request: HttpRequest,
    # 쿼리는 Annotated 꼴(ruff B008). 이름이 계약(camelCase).
    companyId: Annotated[int | None, Query(description="대상 고객사의 id. 없으면 하나뿐인 회사")] = None,
    module: Annotated[str | None, Query(min_length=1, max_length=64, description="모듈 id(예 greenwash)")] = None,
    status: Annotated[RunStatus | None, Query(description="실행 상태")] = None,
    dateFrom: Annotated[
        date | None,
        Query(
            ge=DATE_FLOOR,  # pyright: ignore[reportArgumentType]
            le=DATE_CEILING,  # pyright: ignore[reportArgumentType]
            description="만든 때가 KST 그날 00:00 부터(포함). 2000-01-01~2999-12-31 밖은 422",
        ),
    ] = None,
    dateTo: Annotated[
        date | None,
        Query(
            ge=DATE_FLOOR,  # pyright: ignore[reportArgumentType]
            le=DATE_CEILING,  # pyright: ignore[reportArgumentType]
            description="만든 때가 KST 그날 끝까지(포함). 2000-01-01~2999-12-31 밖은 422",
        ),
    ] = None,
    q: Annotated[
        str | None, Query(min_length=1, max_length=150, description="문서 이름의 부분 일치(대소문자 무시)")
    ] = None,
    review: Annotated[
        ReviewState | None,
        Query(description="검토 상태로 거른다(검토가 보이는 실행만 — pending 은 시작 안 한 검토도). 셋 밖은 422"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunLogPageOut:
    """운영 관리자만. 고른 회사의 실행을 모든 모듈에 걸쳐 새 것 먼저(만든 때 내림). 만든 사람의 이름은 지금 값이고,
    처리 시간은 큐 대기를 품는다(MARC-ENT-327). 토큰·비용은 그 실행에 붙은 AI 호출의 합(비용은 추정). 검토는 그 모듈
    화면이 검토를 보이는 실행에만 값(없으면 pending), AI 설정은 실행을 만들 때 적힌 판. review 는 count·쪽 앞에서
    거른다."""
    principal = permitted(request, "user_run_log_list")
    company_id = chosen_company(companyId, company_ports())
    page = operator_selectors.operator_run_page(
        actor_kind=principal.kind,
        company_id=company_id,
        module=module,
        status=status,
        date_from=dateFrom,
        date_to=dateTo,
        q=q,
        limit=limit,
        offset=offset,
        review=review,
    )
    if isinstance(page, operator_selectors.RunLogForbidden):
        raise ApplicationError("forbidden", "forbidden", FORBIDDEN)
    usage = llm_usage.usage_by_run(company_id=company_id, run_ids=frozenset(run.id for run in page.runs))
    names = selectors.people_of(company_id, {run.created_by_user_id for run in page.runs})
    return RunLogPageOut(
        count=page.count,
        isNext=offset + len(page.runs) < page.count,
        results=[run_out(run, usage, names) for run in page.runs],
    )


def line_of(
    run: operator_selectors.OperatorRun, usage: dict[int, RunUsage], names: dict[int, tuple[str, str]]
) -> run_log_xlsx.RunLogLine:
    """엑셀 한 줄의 재료 — GET /run-logs 의 줄(run_out)과 같은 값."""
    out = run_out(run, usage, names)
    return run_log_xlsx.RunLogLine(
        created_at=to_seoul_iso(run.created_at),
        module=out.module,
        document_name=out.documentName,
        flow_id=out.flowId,
        ai_setting=None
        if out.aiSetting is None
        else run_log_xlsx.DEFAULT_SETTING
        if out.aiSetting.id is None
        else out.aiSetting.name,
        created_by_name=out.createdByName,
        created_by_username=out.createdByUsername,
        duration_sec=out.durationSec,
        tokens=out.tokens,
        cost_usd=out.costUsd,
        status=out.status,
        review=out.review,
        is_test=out.isTest,
    )


@router.get(
    "/run-logs/export",
    operation_id="user_run_log_export",
    response={**USER_ADMIN_ERROR_RESPONSES},
    auth=access_token_auth,
    openapi_extra=EXPORT_RESPONSE,
)
def run_log_export(
    request: HttpRequest,
    companyId: Annotated[int | None, Query(description="대상 고객사의 id. 없으면 하나뿐인 회사")] = None,
    module: Annotated[str | None, Query(min_length=1, max_length=64, description="모듈 id(예 greenwash)")] = None,
    status: Annotated[RunStatus | None, Query(description="실행 상태")] = None,
    dateFrom: Annotated[
        date | None,
        Query(
            ge=DATE_FLOOR,  # pyright: ignore[reportArgumentType]
            le=DATE_CEILING,  # pyright: ignore[reportArgumentType]
            description="만든 때가 KST 그날 00:00 부터(포함). 2000-01-01~2999-12-31 밖은 422",
        ),
    ] = None,
    dateTo: Annotated[
        date | None,
        Query(
            ge=DATE_FLOOR,  # pyright: ignore[reportArgumentType]
            le=DATE_CEILING,  # pyright: ignore[reportArgumentType]
            description="만든 때가 KST 그날 끝까지(포함). 2000-01-01~2999-12-31 밖은 422",
        ),
    ] = None,
    q: Annotated[
        str | None, Query(min_length=1, max_length=150, description="문서 이름의 부분 일치(대소문자 무시)")
    ] = None,
    review: Annotated[
        ReviewState | None,
        Query(description="검토 상태로 거른다(검토가 보이는 실행만 — pending 은 시작 안 한 검토도). 셋 밖은 422"),
    ] = None,
) -> HttpResponse:
    """운영 관리자만. GET /run-logs 와 같은 거르기(쪽 없음)의 전부를 엑셀 한 파일로(새 것 먼저). 1만 건을 넘으면 409
    RUN_LOG_EXPORT_TOO_LARGE(기간을 좁힌다). 내려받으면 감사 기록 한 줄(download)."""
    principal = permitted(request, "user_run_log_export")
    company_id = chosen_company(companyId, company_ports())
    found = operator_selectors.operator_run_export(
        actor_kind=principal.kind,
        company_id=company_id,
        module=module,
        status=status,
        date_from=dateFrom,
        date_to=dateTo,
        q=q,
        review=review,
        cap=RUN_LOG_EXPORT_MAX,
    )
    if isinstance(found, operator_selectors.RunLogForbidden):
        raise ApplicationError("forbidden", "forbidden", FORBIDDEN)
    if isinstance(found, operator_selectors.ExportTooLarge):
        raise ApplicationError("conflict", "run_log_export_too_large", "내보낼 실행이 너무 많아요. 기간을 좁혀 주세요")
    usage = llm_usage.usage_by_run(company_id=company_id, run_ids=frozenset(run.id for run in found.runs))
    names = selectors.people_of(company_id, {run.created_by_user_id for run in found.runs})
    content = run_log_xlsx.workbook([line_of(run, usage, names) for run in found.runs])
    name = run_log_xlsx.file_name(now())
    record_event(
        at=now(),
        company_id=company_id,
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        action="download",
        event="run_logs_exported",
        result="success",
        target_kind="run_log_export",
        target_label=name,
    )
    response = HttpResponse(content, content_type=run_log_xlsx.MEDIA_TYPE)
    # RFC 6266: 한글 이름이라 filename*=utf-8''<퍼센트> 하나(core 의 documents.py 와 같은 꼴). django-stubs 에 이 함수가
    # 없다(Django 4.2+).
    disposition: str = django_http.content_disposition_header(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        as_attachment=True, filename=name
    )
    response["Content-Disposition"] = disposition
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"  # 회사 자료(감독 처분)
    return response


@router.get(
    "/run-logs/metrics",
    operation_id="user_run_log_metrics",
    response={200: RunMetricsOut, **USER_ADMIN_ERROR_RESPONSES},
    auth=access_token_auth,
)
def run_log_metrics(
    request: HttpRequest,
    companyId: Annotated[int | None, Query(description="대상 고객사의 id. 없으면 하나뿐인 회사")] = None,
) -> RunMetricsOut:
    """운영 관리자만. 고른 회사에서 이번 달(서버 시계의 KST 그달)에 만든 실행의 지표 다섯: 실행 수·평균 처리 시간
    (done, 큐 대기 포함 — MARC-ENT-327)·토큰·비용(실행에 붙은 AI 호출만, 추정)·실패율(failed / (done + failed)).
    테스트 실행은 뺀다."""
    principal = permitted(request, "user_run_log_metrics")
    company_id = chosen_company(companyId, company_ports())
    start, end, month = month_bounds(now())
    cohort = operator_selectors.operator_run_cohort(
        actor_kind=principal.kind, company_id=company_id, start=start, end=end
    )
    if isinstance(cohort, operator_selectors.RunLogForbidden):
        raise ApplicationError("forbidden", "forbidden", FORBIDDEN)
    usage = llm_usage.usage_by_run(company_id=company_id, run_ids=frozenset(run.id for run in cohort))
    found = metrics(
        [
            MetricRun(
                id=run.id,
                status=run.status,
                purpose=run.purpose,
                created_at=run.created_at,
                finished_at=run.finished_at,
            )
            for run in cohort
        ],
        usage,
    )
    return RunMetricsOut(
        month=month,
        runs=found.runs,
        averageDurationSec=found.average_duration_sec,
        tokens=found.tokens,
        costUsd=float(found.cost_usd),
        failureRate=found.failure_rate,
        aiProviderMock=app_config().llm.run_mode != "live",
    )


def step_out(step: run_selectors.RunStepHead, usage: llm_usage.StepUsage) -> RunLogStepOut:
    used = usage.by_step.get(step.name)
    return RunLogStepOut(
        name=step.name,
        position=step.position,
        status=step.status,  # pyright: ignore[reportArgumentType] — DB 의 CHECK 가 네 값으로 묶는다
        startedAt=step.started_at,
        finishedAt=step.finished_at,
        durationSec=None if step.started_at is None else duration_sec(step.started_at, step.finished_at),
        tokens=None if not usage.recorded else 0 if used is None else used.tokens,
        costUsd=None if not usage.recorded else 0.0 if used is None else float(used.cost_usd),
    )


@router.get(
    "/run-logs/{int:run_id}",
    operation_id="user_run_log_get",
    response={200: RunLogDetailOut, **USER_ADMIN_ERROR_RESPONSES},
    auth=access_token_auth,
)
def run_log_get(
    request: HttpRequest,
    run_id: int,
    companyId: Annotated[int | None, Query(description="대상 고객사의 id. 없으면 하나뿐인 회사")] = None,
) -> RunLogDetailOut:
    """운영 관리자만. 고른 회사의 실행 하나: 줄 칸(GET /run-logs 와 같은 값) + 실패 단계·오류 코드 + 단계마다 시각·
    시간·토큰·비용 + 결과 파일 이름. 단계별 토큰·비용은 AD4D 뒤 실행만(그 앞은 null — 합계만). 없거나 남의 회사
    실행이면 404 RUN_NOT_FOUND."""
    principal = permitted(request, "user_run_log_get")
    company_id = chosen_company(companyId, company_ports())
    found = operator_selectors.operator_run_detail(actor_kind=principal.kind, company_id=company_id, run_id=run_id)
    if isinstance(found, operator_selectors.RunLogForbidden):
        raise ApplicationError("forbidden", "forbidden", FORBIDDEN)
    if found is None:
        raise ApplicationError("not_found", "run_not_found", RUN_NOT_FOUND)
    usage = llm_usage.usage_by_run(company_id=company_id, run_ids=frozenset({run_id}))
    by_step = llm_usage.usage_by_step(company_id=company_id, run_id=run_id)
    # 단계 머리에 없는 이름의 줄이 있으면 단계 합 ≠ 합계 — 단계 값을 전부 null(stepUsageRecorded false)로 접는다.
    # (독스트링이 아니라 여기: 독스트링은 OpenAPI description 이 된다 — RL1 은 generated 0 바뀜)
    if set(by_step.by_step) - {step.name for step in found.steps}:
        by_step = llm_usage.StepUsage(by_step={}, recorded=False)
    names = selectors.people_of(company_id, {found.run.created_by_user_id})
    line = run_out(found.run, usage, names)
    return RunLogDetailOut(
        **line.model_dump(),
        failedStep=found.failed_step,
        errorCode=found.error_code,
        stepUsageRecorded=by_step.recorded,
        steps=[step_out(step, by_step) for step in found.steps],
        files=[
            RunLogFileOut(name=f.name, step=f.step, mediaType=f.media_type, sizeBytes=f.size_bytes) for f in found.files
        ],
    )


@router.get(
    "/run-logs/{int:run_id}/files/{name}",
    operation_id="user_run_log_file_get",
    response={**USER_ADMIN_ERROR_RESPONSES},
    auth=access_token_auth,
    openapi_extra=FILE_RESPONSE,
)
def run_log_file_get(
    request: HttpRequest,
    run_id: int,
    name: str,
    companyId: Annotated[int | None, Query(description="대상 고객사의 id. 없으면 하나뿐인 회사")] = None,
) -> HttpResponse:
    """운영 관리자만. 고른 회사의 실행(모든 모듈) 하나의 출력 파일(`files[]` 의 `step` 이 null 인 이름)을 바이트로.
    받으면 감사 기록 한 줄(download). 없거나 남의 회사 실행이면 404 RUN_NOT_FOUND, 그 이름의 출력 파일이 없으면 404
    RUN_FILE_NOT_FOUND."""
    principal = permitted(request, "user_run_log_file_get")
    company_id = chosen_company(companyId, company_ports())
    found = operator_selectors.operator_run_file(
        actor_kind=principal.kind, company_id=company_id, run_id=run_id, name=name
    )
    if isinstance(found, operator_selectors.RunLogForbidden):
        raise ApplicationError("forbidden", "forbidden", FORBIDDEN)
    if found is None:
        raise ApplicationError("not_found", "run_not_found", RUN_NOT_FOUND)
    if isinstance(found, operator_selectors.RunFileMissing):
        raise ApplicationError("not_found", "run_file_not_found", RUN_FILE_NOT_FOUND)
    data = file_services.output_bytes(found)  # 저장소 없음·거절·닿지 못함은 503 셋으로 던진다
    if data is None:  # 행은 있는데 객체가 없거나 상한을 넘는다
        raise ApplicationError("not_found", "run_file_not_found", RUN_FILE_NOT_FOUND)
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
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"  # 회사 자료(내보내기와 같다)
    return response
