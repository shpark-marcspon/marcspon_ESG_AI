"""실행기가 끼움(flows/binding_v2.DraftingBinding)에 꽂는 포트 몸(밴드 RP1 ②, RP2a ②). 도메인을 넘는 조립이라 actions 다
(drafting 의 selectors + core 의 문서 selectors·문서 산출물 포트·호출 기록 selector).

    RunProjectSource()    project·outline·document — 프로젝트의 지금 판·판 하나·문서의 올림 상태(회사 조건)
    RunArtifacts(parser)  ensure(company, document, etag) — core 문서 산출물(core/documents/services.ensure_artifact,
                          판 2·쪽 상한 engines/v1/pages.PAGES_MAX). 있으면 저장소·파서 0. 원본 못 읽음 →
                          ArtifactUnreadable(document_missing·storage_unconfigured·object_changed·저장소 결과 타입),
                          저장소·파서 잠깐 장애 → RunRetryLater(다시 넣음). 쓰기는 core 의 짓는 길만(산출물·uses 행)
                          view(company, document, artifact, places=False) — 읽기 뷰(그 문서에 이어진 것만. 글자
                          자리는 places=True 일 때만 — report 의 상자, RP2b)
                          file_name(company, document) — 문서의 올린 이름(없으면 None)
    spent_usd(company, run)  그 실행의 호출 기록 cost_usd 합(translation/apps.py _spent_usd 의 판별 복사)
    RunBaseSource()       base(company, run) — 앞 실행 이어 받기(밴드 RP2c). runs 의 selectors(find_run·run_results — 둘
                          다 회사 조건)로만 읽는다(translation service/actions/retry_source.py 꼴). 원고작성 아니면
                          None, 결과는 drafting.bullets@3 본문만(없으면 None — 끼움이 거절한다)
"""

from collections.abc import Callable, Mapping
from typing import Any, cast

from esgapi.core.documents import selectors as artifact_selectors
from esgapi.core.documents import services as artifact_services
from esgapi.core.documents.contract import ArtifactRef, ArtifactRefused, ArtifactUnreadable
from esgapi.core.documents.view import DocArtifactView
from esgapi.core.resources.ports.parser import DocumentParser
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.selectors import llm_usage
from esgapi.drafting.contracts.shapes import RESULT_SHAPE
from esgapi.drafting.engines.v1 import pages
from esgapi.drafting.flows.binding_v2 import PARSER_LAYOUT, BaseFacts, DocumentFacts, OutlineFacts, ProjectFacts
from esgapi.drafting.flows.draft_v2 import MODULE
from esgapi.drafting.service.selectors import projects as selectors
from esgapi.runs.service.selectors import runs as run_selectors

UPLOADED = "uploaded"


class RunProjectSource:
    def project(self, company_id: int, project_id: int) -> ProjectFacts | None:
        if selectors.project_head(company_id=company_id, project_id=project_id) is None:
            return None
        outline = selectors.current_outline(company_id=company_id, project_id=project_id)
        document = selectors.current_document(company_id=company_id, project_id=project_id)
        return ProjectFacts(
            project_id=project_id,
            outline_id=None if outline is None else outline.id,
            outline_sha256=None if outline is None else outline.sha256,
            document_id=None if document is None else document.document_id,
        )

    def outline(self, company_id: int, outline_id: int) -> OutlineFacts | None:
        found = selectors.outline_at(company_id=company_id, outline_id=outline_id)
        if found is None:
            return None
        return OutlineFacts(project_id=found.project_id, sha256=found.sha256, outline=found.outline)

    def document(self, company_id: int, document_id: int) -> DocumentFacts | None:
        found = document_selectors.find_document(company_id=company_id, document_id=document_id)
        return None if found is None else DocumentFacts(uploaded=found.status == UPLOADED, etag=found.etag)


class RunArtifacts:
    def __init__(self, *, parser: Callable[[], DocumentParser]) -> None:
        self.parser = parser

    def ensure(
        self, company_id: int, document_id: int, etag: str
    ) -> ArtifactRef | ArtifactRefused | ArtifactUnreadable:
        return artifact_services.ensure_artifact(
            company_id, document_id, etag, layout=PARSER_LAYOUT, parser=self.parser, max_pages=pages.PAGES_MAX
        )

    def view(self, company_id: int, document_id: int, artifact_id: int, *, places: bool = False) -> DocArtifactView:
        return artifact_selectors.artifact_view(
            company_id=company_id, document_id=document_id, artifact_id=artifact_id, places=places
        )

    def file_name(self, company_id: int, document_id: int) -> str | None:
        found = document_selectors.find_document(company_id=company_id, document_id=document_id)
        return None if found is None else found.file_name


def spent_usd(company_id: int, run_id: int) -> float:
    found = llm_usage.usage_by_run(company_id=company_id, run_ids=frozenset({run_id})).get(run_id)
    return 0.0 if found is None else float(found.cost_usd)


class RunBaseSource:
    def base(self, company_id: int, run_id: int) -> BaseFacts | None:
        run = run_selectors.find_run(company_id=company_id, run_id=run_id)
        if run is None or run.module != MODULE:
            return None
        results = run_selectors.run_results(company_id=company_id, run_id=run_id)
        body = next((r.body for r in results if r.schema_version == RESULT_SHAPE), None)
        project_id = run.options.get("projectId")
        return BaseFacts(
            run_id=run.id,
            project_id=project_id if isinstance(project_id, int) and not isinstance(project_id, bool) else None,
            status=run.status,
            versions=run.versions,
            result=cast("Mapping[str, Any]", body) if isinstance(body, Mapping) else None,
        )
