"""흐름 greenwash.engine@G1 의 끼움(flows/binding_g1.G1Binding)에 꽂는 문서 포트 몸(밴드 GE1b ③). 도메인을 넘는 조립이라
actions 다(runs 의 실행 selector + core 의 문서 selector·문서 산출물의 짓는 길). 선례 drafting service/actions/
run_sources.RunArtifacts.

    RunG1Documents(parser)              for_run(company_id, run_id) → RunG1Document(그 실행의 문서 포트)
    RunG1Document.ensure()              그 실행의 문서(runs find_run 의 document_id) · 지금 etag(core find_document)로
                                        core/documents/services.ensure_artifact(판 2 · 쪽 상한 engine_g1.PAGE_MAX).
                                        있으면 찾기만(저장소·파서 0). 실행·문서·etag 가 없으면 ArtifactUnreadable
                                        (document_missing). 거절·못 읽음은 그 값, 잠깐 장애는 RunRetryLater(올라감)
    RunG1Document.view(ref)             읽기 뷰(그 문서에 이어진 것만 · 도표 라벨 실음(charts=True — GE1c ④, 단락 풀의
                                        도표 단위) · 글자 자리 안 읽음)
    RunG1Document.file_name()           문서의 올린 이름(없으면 빈 글자)

    run_result2(company_id, run_id)     GET /greenwash/runs/{run_id}/result2 의 몸(GE1b ④). 차례: 실행 없음·남의 회사·
                                        module 밖·흐름이 engine@G1 아님 → NotFound(404) · 끝나지 않음 → RunNotDone(409)
                                        · result@2 행 없음 → NotFound. 저장 본문을 result@2 꼴(RESULT2)로 읽어 돌려준다
                                        — 응답 열쇠 차례는 꼴의 차례(jsonb 가 바꾼 차례를 내보내지 않는다, 감독 53)

★ 부를 때마다 실행·문서를 다시 읽는다(값을 쥐지 않는다): 실행 도중 문서가 바뀌면(etag) 새 산출물을 받고, 끼움 쪽
  engine_g1.view_of 가 extract 의 sha·parserVersion 과 견줘 G1ArtifactChanged 로 이름 있게 끝낸다.
★ 쓰기는 core 의 짓는 길(ensure_artifact — 파서는 트랜잭션 밖)뿐이다. 이 파일에는 트랜잭션 블록·ORM 0
  (core/tests/test_transaction_rules 의 규칙을 예외 없이 지난다).
"""

from collections.abc import Callable
from typing import Any

from esgapi.core.documents import selectors as artifact_selectors
from esgapi.core.documents import services as artifact_services
from esgapi.core.documents.contract import ArtifactRef, ArtifactRefused, ArtifactUnreadable
from esgapi.core.documents.view import DocArtifactView
from esgapi.core.resources.ports.parser import DocumentParser
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.greenwash.contracts import result2_shapes as r2
from esgapi.greenwash.flows import binding_g1
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.service.actions.review import MODULE, NotFound, RunNotDone
from esgapi.runs.service.selectors import runs as run_selectors

MISSING = "document_missing"


class RunG1Document:
    def __init__(self, *, company_id: int, run_id: int, parser: Callable[[], DocumentParser]) -> None:
        self.company_id = company_id
        self.run_id = run_id
        self.parser = parser

    def _document_id(self) -> int | None:
        run = run_selectors.find_run(company_id=self.company_id, run_id=self.run_id)
        return None if run is None else run.document_id

    def ensure(self) -> ArtifactRef | ArtifactRefused | ArtifactUnreadable:
        document_id = self._document_id()
        if document_id is None:
            return ArtifactUnreadable(MISSING)
        found = document_selectors.find_document(company_id=self.company_id, document_id=document_id)
        if found is None or found.etag is None:
            return ArtifactUnreadable(MISSING)
        # Directive: 판 2 산출물은 drafting 과 같이 쓰고 find 길은 max_pages 를 안 본다 —
        # drafting PAGES_MAX 를 300 위로 올리면 여기 상한을 같이 본다.
        return artifact_services.ensure_artifact(
            self.company_id,
            document_id,
            found.etag,
            layout=binding_g1.PARSER_LAYOUT,
            parser=self.parser,
            max_pages=E.PAGE_MAX,
        )

    def view(self, ref: ArtifactRef) -> DocArtifactView:
        document_id = self._document_id()
        if document_id is None:
            raise E.G1DocumentFailed(MISSING)
        return artifact_selectors.artifact_view(
            company_id=self.company_id, document_id=document_id, artifact_id=ref.id, places=False, charts=True
        )

    def file_name(self) -> str:
        document_id = self._document_id()
        found = (
            None
            if document_id is None
            else document_selectors.find_document(company_id=self.company_id, document_id=document_id)
        )
        return "" if found is None else found.file_name


class RunG1Documents:
    def __init__(self, *, parser: Callable[[], DocumentParser]) -> None:
        self.parser = parser

    def for_run(self, company_id: int, run_id: int) -> RunG1Document:
        return RunG1Document(company_id=company_id, run_id=run_id, parser=self.parser)


def run_result2(*, company_id: int, run_id: int) -> dict[str, Any] | NotFound | RunNotDone:
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE or run.flow_id != E.FLOW_ID:
        return NotFound()
    if run.status != "done":
        return RunNotDone(run.status)
    results = run_selectors.run_results(company_id=company_id, run_id=run_id)
    body = next((r.body for r in results if r.schema_version == r2.SHAPE), None)
    if body is None:
        return NotFound()
    return r2.RESULT2.dump_python(r2.RESULT2.validate_python(body), mode="json")
