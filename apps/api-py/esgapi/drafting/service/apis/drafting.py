"""원고작성의 경로 아홉(밴드 RP1 ③ 다섯 · RP2d 목록·docx 둘 · RP2c 목차 차이 하나 · RPS1 실행 목록 하나).
config/api.py 가 이 router 를 /drafting 아래에 Bearer 인증(머리가 없으면 옛 교환 쿠키, K2b)을 꽂아 건다(/materiality 와
같은 auth).

    POST /drafting/projects                         drafting_projects_create        {year, name} → 201 프로젝트
    GET  /drafting/projects?limit=&offset=          drafting_projects_list          목록 한 쪽(최신순, RP2d)
    GET  /drafting/projects/{project_id}            drafting_project_get            프로젝트 + 지금 문서·지금 목차
    PUT  /drafting/projects/{project_id}/document   drafting_project_document_put   {documentId} → 200 프로젝트
    PUT  /drafting/projects/{project_id}/outline    drafting_outline_put            drafting.outline@1 → 200 판
    GET  /drafting/projects/{project_id}/outline/changes?baseRunId=
                                                    drafting_outline_changes        앞 실행 목차 → 지금 목차 잎
                                                    차이(RP2c)
    GET  /drafting/projects/{project_id}/runs?limit=&offset=
                                                    drafting_project_runs           프로젝트의 원고작성 실행 한 쪽
                                                    (새 것 먼저, RPS1)
    GET  /drafting/runs/{run_id}/result             drafting_result_get             drafting.bullets@3
    GET  /drafting/runs/{run_id}/result.docx        drafting_result_download        결과 docx(attachment, RP2d)
전부 회사 업무(고객사 사용자·운영 관리자 — 운영 관리자는 작업 회사 company_of, MARC-ENT-419).

몸 꼴: 요청·목차 답 contracts/api_shapes.py · 프로젝트·목록 응답 service/schemas/projects.py(시각 칸 KstDateTime) ·
결과 contracts/shapes.py. 몸: service/actions/projects.py(문서 달기·목차 판 묶음)·service/services/projects.py(만들기)·
service/selectors/projects.py(읽기)·service/actions/runs.py(목록·프로젝트의 latestRun·실행 목록 — RPS1)·
service/actions/result.py(결과)·service/actions/changes.py(목차
차이)·service/actions/download.py(결과 docx — 짓기는
outputs/docx.py).
경로는 models 를 import 하지 않는다(`.importlinter` 계약 라) — 갈래를 응답으로 바꿀 뿐이다. 실행 만들기·상태는 runs 의
경로(POST /runs {module:"drafting", options:{projectId}}·GET /runs/{id})다.
오류: 프로젝트·문서·실행 없음(남의 회사 id 도) 404 NOT_FOUND · 문서 올림 미완·목차 트리 규칙 어김 422 VALIDATION_ERROR
(fields 에 칸) · 글자 층 없는 문서 422 DOCUMENT_NO_TEXT_LAYER · 실행이 끝나지 않음 409 RUN_NOT_DONE.
★ id 는 int 다. 테넌트 id 는 인증 주체(토큰)에서만 온다(쿼리·본문에 그 칸이 없다).
"""

from typing import Annotated, Any

from django.http import HttpRequest, HttpResponse
from ninja import Query, Router, Status
from pydantic import Field

from esgapi.core.auth.bearer import company_of, permitted
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES
from esgapi.drafting.contracts import wire
from esgapi.drafting.contracts.api_shapes import (
    DraftingDocumentPutIn,
    DraftingOutlinePut,
    DraftingOutlinePutIn,
    DraftingProjectCreateIn,
)
from esgapi.drafting.contracts.shapes import DraftingResult
from esgapi.drafting.outputs import docx as docx_output
from esgapi.drafting.service.actions import changes as changes_actions
from esgapi.drafting.service.actions import download as download_actions
from esgapi.drafting.service.actions import projects as actions
from esgapi.drafting.service.actions import result as result_actions
from esgapi.drafting.service.actions import runs as runs_actions
from esgapi.drafting.service.schemas.projects import (
    DraftingOutlineChanges,
    DraftingOutlineChangesQuery,
    DraftingProject,
    DraftingProjectListQuery,
    DraftingProjectPage,
    DraftingProjectRunsQuery,
    DraftingRunPage,
)
from esgapi.drafting.service.selectors import projects as selectors
from esgapi.drafting.service.services import projects as services
from esgapi.drafting.service.services.projects import ProjectMissing

router = Router(tags=["원고작성"])

# operation_id 는 손으로 적는다(`<모듈>_<동작>`). 표는 esgapi/config/tests/test_api_contract.py 가 못 박는다.

NOT_FOUND: dict[int, type[ErrorBody]] = {404: ErrorBody}
PROJECT_MISSING = "그런 원고작성 프로젝트가 없다"
DOCUMENT_MISSING = "그런 문서가 없다"
NOT_UPLOADED = "올림이 끝나지 않은 문서다"
NO_TEXT_LAYER = "글자 층이 없는 문서다(스캔본은 받지 않는다)"
CHANGES_MISSING = "견줄 프로젝트·목차·끝난 실행이 없다"

ProjectId = Annotated[int, Field(description="원고작성 프로젝트 id")]
RunId = Annotated[int, Field(description="실행 id")]


def _project_out(view: selectors.ProjectView, latest_run: dict[str, Any] | None) -> dict[str, Any]:
    project, document, outline = view.project, view.document, view.outline
    return {
        "id": project.id,
        "year": project.year,
        "name": project.name,
        "createdByUserId": project.created_by_user_id,
        "createdAt": project.created_at,
        "document": None
        if document is None
        else {
            "documentId": document.document_id,
            "kind": document.kind,
            "attachedByUserId": document.attached_by_user_id,
            "attachedAt": document.attached_at,
        },
        "outline": None
        if outline is None
        else {
            "outlineId": outline.id,
            "revision": outline.revision,
            "sha256": outline.sha256,
            "outline": outline.outline,
        },
        "latestRun": latest_run,
    }


def _view(company_id: int, project_id: int) -> dict[str, Any]:
    view = selectors.project_view(company_id=company_id, project_id=project_id)
    if view is None:
        raise ApplicationError("not_found", "not_found", PROJECT_MISSING)
    latest = runs_actions.latest_runs(company_id=company_id, project_ids=[project_id])
    return _project_out(view, latest.get(project_id))


def _refused(refusal: object) -> ApplicationError:
    """actions 의 거절 갈래 → 오류(config/api.py 가 상태 코드로 바꾼다)."""
    match refusal:
        case ProjectMissing():
            return ApplicationError("not_found", "not_found", PROJECT_MISSING)
        case actions.DocumentMissing():
            return ApplicationError("not_found", "not_found", DOCUMENT_MISSING)
        case actions.DocumentNotUploaded():
            return ApplicationError(
                "validation", "validation_error", NOT_UPLOADED, fields={"documentId": [NOT_UPLOADED]}
            )
        case actions.DocumentNoTextLayer():
            return ApplicationError("validation", wire.DOCUMENT_NO_TEXT_LAYER, NO_TEXT_LAYER)
        case changes_actions.NotFound():
            return ApplicationError("not_found", "not_found", CHANGES_MISSING)
        case runs_actions.NotFound():
            return ApplicationError("not_found", "not_found", PROJECT_MISSING)
        case result_actions.NotFound():
            return ApplicationError("not_found", "not_found", "그런 실행이 없다")
        case result_actions.RunNotDone():
            return ApplicationError("conflict", "run_not_done", "실행이 아직 끝나지 않았다")
        case _:
            raise TypeError(f"모르는 거절 갈래: {type(refusal).__name__}")


@router.post(
    "/projects",
    operation_id="drafting_projects_create",
    response={201: DraftingProject, **TOKEN_BODY_ERROR_RESPONSES},
)
def projects_create(request: HttpRequest, body: DraftingProjectCreateIn) -> Status[dict[str, Any]]:
    """원고작성 프로젝트 하나(연도·이름)를 만든다. 문서·목차는 비어 있다(null)."""
    principal = permitted(request, "drafting_projects_create")
    company_id = company_of(principal)
    project_id = services.create_project(
        company_id=company_id, year=body.year, name=body.name, user_id=int(principal.user_id)
    )
    return Status(201, _view(company_id, project_id))


@router.get(
    "/projects",
    operation_id="drafting_projects_list",
    response={200: DraftingProjectPage, **TOKEN_ERROR_RESPONSES},
)
def projects_list(request: HttpRequest, query: Query[DraftingProjectListQuery]) -> dict[str, Any]:
    """이 회사의 원고작성 프로젝트 한 쪽(만든 시각 내림, 같으면 id 내림). 줄마다 문서가 달렸는지·지금 문서 이름, 지금
    목차 판 번호·id(목차 없으면 null), 가장 새 원고작성 실행(latestRun — 없으면 null)을 싣는다."""
    principal = permitted(request, "drafting_projects_list")
    return runs_actions.project_page(company_id=company_of(principal), limit=query.limit, offset=query.offset)


@router.get(
    "/projects/{project_id}",
    operation_id="drafting_project_get",
    response={200: DraftingProject, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def project_get(request: HttpRequest, project_id: ProjectId) -> dict[str, Any]:
    """프로젝트 하나 + 지금 문서(가장 늦게 단 것) + 지금 목차 판(가장 큰 revision, 마디째) + 가장 새 원고작성 실행."""
    principal = permitted(request, "drafting_project_get")
    return _view(company_of(principal), project_id)


@router.put(
    "/projects/{project_id}/document",
    operation_id="drafting_project_document_put",
    response={200: DraftingProject, **NOT_FOUND, **TOKEN_BODY_ERROR_RESPONSES},
)
def project_document_put(request: HttpRequest, project_id: ProjectId, body: DraftingDocumentPutIn) -> dict[str, Any]:
    """전년도 보고서를 단다(새 행 — 지금 문서는 가장 늦게 단 것). 같은 회사의 올림이 끝난 문서만, 글자 층이 없으면
    (hasText false) 422 DOCUMENT_NO_TEXT_LAYER(null = 아직 모름은 받는다)."""
    principal = permitted(request, "drafting_project_document_put")
    company_id = company_of(principal)
    found = actions.attach_document(
        company_id=company_id, project_id=project_id, document_id=body.documentId, user_id=int(principal.user_id)
    )
    if not isinstance(found, int):
        raise _refused(found)
    return _view(company_id, project_id)


@router.put(
    "/projects/{project_id}/outline",
    operation_id="drafting_outline_put",
    response={200: DraftingOutlinePut, **NOT_FOUND, **TOKEN_BODY_ERROR_RESPONSES},
)
def outline_put(request: HttpRequest, project_id: ProjectId, body: DraftingOutlinePutIn) -> dict[str, Any]:
    """목차를 통째로 넣는다(drafting.outline@1). 지금 판과 sha 가 같으면 그 판(멱등), 아니면 새 판(revision +1). 실행은
    만들 때의 판을 읽으므로 큐 중에 바꿔도 실행은 그대로다."""
    principal = permitted(request, "drafting_outline_put")
    try:
        outline = wire.accept_outline(body.model_dump())
    except wire.OutlineRejected as error:
        raise ApplicationError("validation", "validation_error", str(error), fields={"nodes": [str(error)]}) from None
    found = actions.put_outline(
        company_id=company_of(principal), project_id=project_id, outline=outline, user_id=int(principal.user_id)
    )
    if isinstance(found, ProjectMissing):
        raise _refused(found)
    return {"outlineId": found.outline_id, "revision": found.revision, "sha256": found.sha256}


@router.get(
    "/projects/{project_id}/outline/changes",
    operation_id="drafting_outline_changes",
    response={200: DraftingOutlineChanges, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def outline_changes(
    request: HttpRequest, project_id: ProjectId, query: Query[DraftingOutlineChangesQuery]
) -> dict[str, Any]:
    """앞 실행(baseRunId)이 읽은 목차 판 → 지금 목차 판의 잎 차이(same·changed·added, 지운 key)와 문서가 같은가.
    목차 차이만 — 실제로 옮겼는지는 결과의 base·reusedFrom 이다. 프로젝트·목차·실행 없음·남의 회사·다른 프로젝트·
    끝나지 않은 실행은 한 글 404."""
    principal = permitted(request, "drafting_outline_changes")
    found = changes_actions.outline_changes(
        company_id=company_of(principal), project_id=project_id, base_run_id=query.baseRunId
    )
    if isinstance(found, changes_actions.NotFound):
        raise _refused(found)
    return found


@router.get(
    "/projects/{project_id}/runs",
    operation_id="drafting_project_runs",
    response={200: DraftingRunPage, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def project_runs(request: HttpRequest, project_id: ProjectId, query: Query[DraftingProjectRunsQuery]) -> dict[str, Any]:
    """그 프로젝트의 원고작성 실행 한 쪽(옵션 projectId 가 그 프로젝트 — 만든 시각 내림, 같으면 id 내림). 줄마다 상태·
    시각·목차 판·이어 받은 앞 실행·다시 짓는 잎·진행(processing)·잎 셈(끝났고 @3 결과가 있을 때). 프로젝트 없음·남의
    회사는 한 글 404."""
    principal = permitted(request, "drafting_project_runs")
    found = runs_actions.project_runs(
        company_id=company_of(principal), project_id=project_id, limit=query.limit, offset=query.offset
    )
    if isinstance(found, runs_actions.NotFound):
        raise _refused(found)
    return found


@router.get(
    "/runs/{run_id}/result",
    operation_id="drafting_result_get",
    response={200: DraftingResult, **NOT_FOUND, **TOKEN_ERROR_RESPONSES},
)
def result_get(request: HttpRequest, run_id: RunId) -> dict[str, Any]:
    """한 실행의 결과(drafting.bullets@3). 끝나지 않은 실행은 409 RUN_NOT_DONE, 실패의 까닭은 GET /runs/{id} 다."""
    principal = permitted(request, "drafting_result_get")
    found = result_actions.run_result(company_id=company_of(principal), run_id=run_id)
    if isinstance(found, result_actions.NotFound | result_actions.RunNotDone):
        raise _refused(found)
    return found


# 결과 docx 의 200 은 docx 바이트다. response= 에 200 을 적지 않고 이것으로만 선언한다(greenwash 보고서와 같은 꼴).
DOWNLOAD_RESPONSE = {
    "responses": {
        200: {
            "description": "결과 docx 의 바이트(Content-Disposition: attachment, 「drafting-<run_id>.docx」)",
            "content": {docx_output.MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}}},
        }
    }
}


@router.get(
    "/runs/{run_id}/result.docx",
    operation_id="drafting_result_download",
    response={**NOT_FOUND, **TOKEN_ERROR_RESPONSES},
    openapi_extra=DOWNLOAD_RESPONSE,
)
def result_download(request: HttpRequest, run_id: RunId) -> HttpResponse:
    """한 실행의 결과(drafting.bullets@3)를 목차 머리 + bullet + 출처 쪽의 docx 한 파일로 내려받는다(늘 다시 짓는다).
    끝나지 않은 실행은 409 RUN_NOT_DONE, 없거나 남의 회사·다른 모듈 실행은 404(결과 경로와 같은 갈래)."""
    principal = permitted(request, "drafting_result_download")
    made = download_actions.result_docx(company_id=company_of(principal), run_id=run_id)
    if not isinstance(made, download_actions.Docx):
        raise _refused(made)
    response = HttpResponse(made.content, content_type=docx_output.MEDIA_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{made.file_name}"'  # 이름은 ASCII 뿐
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"  # 회사 자료
    return response
