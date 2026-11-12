"""Scope 3 코랩 흐름의 경로 둘의 몸(밴드 S3K1 ③): 빈 양식 바이트, 한 실행의 결과.

결과는 runs 의 selectors(find_run·run_results)로만 읽는다 — 둘 다 회사 조건이 붙어 남의 회사 실행은 없는 실행이다.
남의 도메인(runs)을 엮으므로 Selector 가 아니라 Action 이다(dataverify service/actions/result.py 꼴). 갈래:
    결과 본문   module inventory.scope3 · status done · 결과 scope3.colab.result@1 이 있음 → 그 본문(done·rejected)
    NotFound    없음·남의 회사·다른 모듈·끝났는데 그 결과가 없음(llm-first 결과 행만 있는 옛 실행 등)
    RunNotDone  그 회사·Scope 3 실행이지만 끝나지 않음(queued·processing·failed)
양식은 저장소에 넣은 빈 양식 v2.2(MARC-ENT-641 — 받은 양식에서 지은 사본) — 배포에 없으면 Unavailable.
결과 본문의 활동·에너지 줄 factor 에는 읽을 때 책 머리 출처 글(sourceText)을 더한다(S3Q1 Q9 — utils/scope3_sources.py,
저장된 결과는 그대로).

원본(S3Q1 ① — 결정 MARC-ENT-639, 발주서 Q1·Q2·Q4): 그 실행에 올린 엑셀(run.document_id 의 문서) 바이트 그대로. 실행은
runs 의 find_run(회사 조건)·module 로, 문서는 core 의 find_document(같은 회사 조건)로만 찾는다 — 남의 회사 실행·문서는
없는 것이다. 실행 상태는 보지 않는다(끝나지 않은 실행도 올린 파일은 있다). 읽기 길은 core 원본 내려받기 꼴(상한
max_upload_bytes · ETag 대조). 갈래:
    Original     바이트·이름(올린 이름 그대로)·꼴(.xlsx · .xls · 그 밖 octet-stream)
    NotFound     없음·남의 회사·Scope 3 아님·문서 null·문서 없음·아직 안 올라옴·저장소에 원본 없음
    Unavailable  저장소 설정 없음·거부·닿지 못함(503)
    Conflict     상한 넘음·올림 확인 뒤 원본이 바뀜(409 — core 꼴의 code)
"""

from dataclasses import dataclass
from typing import Any, Final, Literal, cast

from esgapi.core.resources.ports.storage import ObjectBytes, ObjectMissing, ObjectTooLarge, StorageDenied
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.services import documents
from esgapi.inventory.flows.binding_157 import MODULE, FileMissing
from esgapi.inventory.flows.scope3_colab_157 import RESULT_SHAPE
from esgapi.inventory.service.utils import scope3_files, scope3_sources
from esgapi.runs.service.selectors import runs as run_selectors

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FILE_NAME: Final = "Scope3_템플릿_수정본_v2.2.xlsx"
"""내려받는 이름(발주서 1-1 — 받은 파일의 이름에서 「 (1)」만 뺌)."""
XLS_MEDIA_TYPE: Final = "application/vnd.ms-excel"
OTHER_MEDIA_TYPE: Final = "application/octet-stream"
ORIGINAL_MEDIA_TYPES: Final = {".xlsx": MEDIA_TYPE, ".xls": XLS_MEDIA_TYPE}
"""원본의 꼴(올린 이름의 끝 — 대소문자 무시). 그 밖은 OTHER_MEDIA_TYPE(S3Q1 Q4)."""


@dataclass(frozen=True, slots=True)
class NotFound:
    """실행이 없다(남의 회사·Scope 3 아닌 실행·코랩 결과가 없는 실행도 이 갈래)."""


@dataclass(frozen=True, slots=True)
class RunNotDone:
    status: str


@dataclass(frozen=True, slots=True)
class Unavailable:
    """빈 양식이 배포에 없다(패키지 누락). 원본은 저장소 설정 없음·거부·닿지 못함(why 는 code 글자)."""

    why: str = "unavailable"


@dataclass(frozen=True, slots=True)
class Conflict:
    """원본이 상한보다 크거나 올림 확인 뒤 바뀌었다(core 원본 내려받기의 409 code 글자)."""

    why: Literal["object_too_large", "object_changed"]


@dataclass(frozen=True, slots=True)
class Original:
    """그 실행에 올린 파일(바이트 그대로). document_id·file_name 은 감사 줄의 대상."""

    document_id: int
    file_name: str
    media_type: str
    content: bytes


type Refusal = NotFound | RunNotDone


def run_result(*, company_id: int, run_id: int) -> dict[str, Any] | Refusal:
    """끝난 Scope 3 실행의 결과 본문(scope3.colab.result@1)."""
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE:
        return NotFound()
    if run.status != "done":
        return RunNotDone(run.status)
    results = run_selectors.run_results(company_id=company_id, run_id=run_id)
    body = next((r.body for r in results if r.schema_version == RESULT_SHAPE), None)
    if not isinstance(body, dict):
        return NotFound()
    return scope3_sources.with_sources(cast("dict[str, Any]", body), scope3_sources.packaged_sources())


def media_type_of(file_name: str) -> str:
    """올린 이름의 끝 → 내려줄 꼴(Q4)."""
    dot = file_name.rfind(".")
    return ORIGINAL_MEDIA_TYPES.get(file_name[dot:].lower(), OTHER_MEDIA_TYPE) if dot >= 0 else OTHER_MEDIA_TYPE


def original(*, company_id: int, run_id: int) -> Original | NotFound | Unavailable | Conflict:
    """그 회사 Scope 3 실행에 올린 원본(머리말 갈래). 회사 조건을 지난 뒤에만 저장소를 읽는다."""
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE or run.document_id is None:
        return NotFound()
    document = document_selectors.find_document(company_id=company_id, document_id=run.document_id)
    if document is None or document.status != "uploaded":
        return NotFound()
    storage = documents.default_storage()
    if storage is None:
        return Unavailable("storage_unconfigured")
    got = storage.get(document.storage_key, max_bytes=documents.max_upload_bytes())
    if isinstance(got, ObjectMissing):
        return NotFound()
    if isinstance(got, ObjectTooLarge):
        return Conflict("object_too_large")
    if not isinstance(got, ObjectBytes):
        return Unavailable("storage_denied" if isinstance(got, StorageDenied) else "storage_unavailable")
    if got.etag != document.etag:  # 올림 확인 뒤 같은 키에 다시 올라옴(core 꼴)
        return Conflict("object_changed")
    return Original(document.id, document.file_name, media_type_of(document.file_name), got.data)


def template() -> bytes | Unavailable:
    """빈 양식 v2.2 의 바이트(테넌트 행을 읽지 않는다 — 운영 관리자도 같은 바이트)."""
    content = scope3_files.TEMPLATE.read()
    return Unavailable() if isinstance(content, FileMissing) else content
