"""묶음 꼴 translation.batch@1 — 영문번역 묶음 목록·하나 보기(GET /translation/batches · GET /translation/documents/
{document_id}/batches/{batch_key} — 밴드 TR3b, MARC-ENT-392·393).

묶음 = (문서, batchKey). batchKey 는 실행 옵션의 batchId(소문자 uuid — 웹이 [번역 시작] 한 번에 짓는다), batchId 없는
실행은 `run-<실행 id>` 하나가 묶음 하나다. 묶음 안 파트마다 가장 새 실행이 `latest`(같은 파트를 다시 돌리면 새 것 —
393), 그 앞 실행이 `earlier`(새 것 먼저). 옵션 본문·결과 본문은 싣지 않는다 — 결과는 둘째 결과 translation.digest@1
(contracts/digest_shapes.py) 그대로다. **이 파일에 로직은 없다**(셈은 service/actions/batches.py).

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다. 이름은 `TranslationBatch` 로 시작한다(generated/ 의 schema
이름). 고정 파일은 tests/data/api-shapes/translation.batch@1.schema.json. 칸을 더하는 것은 @1 안, 빼거나 바꾸면 @2 다.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, TypedDict

from pydantic import Field, TypeAdapter, with_config

from esgapi.translation.contracts.digest_shapes import TranslationDigest
from esgapi.translation.contracts.shapes import FORBID, Count, Part

BATCH_SHAPE: Final = "translation.batch@1"
BATCH_KEY_PATTERN: Final = r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|run-[1-9][0-9]*)$"
"""batchKey 의 꼴 — 옵션 batchId(options_shapes.BATCH_ID_PATTERN) 또는 `run-<실행 id>`."""

RunStatus = Literal["queued", "processing", "done", "failed"]
StepStatus = Literal["pending", "running", "done", "failed"]
BatchState = Literal["active", "done", "failed"]
InputKind = Literal["word", "pdf"]
Time = Annotated[str, Field(description="ISO 8601(서울 시각, 오프셋 포함)")]
RunId = Annotated[int, Field(ge=1)]


@with_config(FORBID)
class TranslationBatchPerson(TypedDict):
    """사람 — id 와 지금 이름(지운·모르는 사람이면 「알 수 없는 사용자」)."""

    userId: Annotated[int, Field(ge=0)]
    """사용자 id. 문서 올린 사람 칸이 숫자가 아니면 0."""
    name: str


@with_config(FORBID)
class TranslationBatchDocument(TypedDict):
    """묶음의 문서."""

    id: Annotated[int, Field(ge=1)]
    fileName: str
    uploadedAt: Time | None
    """올림을 마친 시각. 아직 안 마쳤으면 null."""
    uploadedBy: TranslationBatchPerson


@with_config(FORBID)
class TranslationBatchPages(TypedDict):
    """번역할 쪽 범위(옵션 pages 그대로 — contracts/shapes.py PageRange). null 이면 그쪽 끝이 열린다."""

    start: int | None
    end: int | None


@with_config(FORBID)
class TranslationBatchStyle(TypedDict):
    """번역 문체(옵션 style 그대로 — contracts/shapes.py Style)."""

    compareAb: bool
    single: Literal["A", "B"]


@with_config(FORBID)
class TranslationBatchGlossaryCounts(TypedDict):
    """옵션 용어집의 짝 수. final 이 화면의 「고객사 용어집 n개」다."""

    base: Count
    final: Count


@with_config(FORBID)
class TranslationBatchStep(TypedDict):
    """실행의 단계 하나(GET /runs/{id} 의 steps 와 같은 값 — 선언 차례)."""

    step: str
    status: StepStatus
    done: int | None
    total: int | None


@with_config(FORBID)
class TranslationBatchRun(TypedDict):
    """파트의 최신 실행."""

    runId: RunId
    flowId: str
    """그 실행의 흐름 id 그대로(예: translation.colab@158 · translation.pdf@158 — 밴드 TRS3)."""
    status: RunStatus
    pages: TranslationBatchPages | None
    """옵션의 쪽 범위. 옵션 꼴이 어긋나면 null."""
    style: TranslationBatchStyle | None
    """옵션의 문체. 옵션 꼴이 어긋나면 null."""
    glossaryCounts: TranslationBatchGlossaryCounts
    createdAt: Time
    startedAt: Time | None
    finishedAt: Time | None
    failedStep: str | None
    """failed 실행이 멈춘 단계(실행기의 실패면 null). failed 가 아니면 null."""
    errorCode: str | None
    """failed 실행의 오류 code. failed 가 아니면 null."""
    steps: list[TranslationBatchStep]
    digest: TranslationDigest | None
    """끝난 실행의 요약(translation.digest@1). 끝나지 않았거나 요약을 남기기 전의 옛 실행이면 null — 「모름」이다."""


@with_config(FORBID)
class TranslationBatchEarlier(TypedDict):
    """같은 파트의 앞 실행 하나(회차 펼침)."""

    runId: RunId
    status: RunStatus
    createdAt: Time
    finishedAt: Time | None
    outcome: Literal["done", "partial", "rejected"] | None
    """그 실행 요약의 outcome. 끝나지 않았거나 요약이 없으면 null."""


@with_config(FORBID)
class TranslationBatchPart(TypedDict):
    """묶음의 파트 하나."""

    part: Part
    latest: TranslationBatchRun
    earlier: list[TranslationBatchEarlier]
    """같은 파트의 앞 실행(새 것 먼저)."""
    round: Annotated[int, Field(ge=1)]
    """회차 = earlier 수 + 1."""


@with_config(FORBID)
class TranslationBatch(TypedDict):
    """translation.batch@1 — 문서 하나의 묶음 하나."""

    batchKey: Annotated[str, Field(pattern=BATCH_KEY_PATTERN)]
    inputKind: InputKind
    """묶음 안 가장 새 실행의 흐름 id 가 translation.pdf@ 로 시작하면 pdf, 아니면 word(옛 실행 포함 — 밴드 TRS3)."""
    document: TranslationBatchDocument
    createdBy: TranslationBatchPerson
    """묶음 안 가장 새 실행을 만든 사람."""
    parts: list[TranslationBatchPart]
    """ceo_message·story·general 차례, 실행이 있는 파트만."""
    state: BatchState
    """파트 최신 실행만 본다. active = queued·processing 하나라도 · failed = 그 밖에 failed 실행이나 요약 outcome
    rejected·partial 하나라도 · done = 그 밖(요약이 없는 옛 done 실행 포함)."""
    doneParts: Count
    """최신 실행이 done 인 파트 수."""
    partCount: Annotated[int, Field(ge=1)]
    """parts 길이."""


@with_config(FORBID)
class TranslationBatchDetail(TranslationBatch):
    """묶음 하나 보기 — 묶음 + truncated."""

    truncated: bool
    """그 문서의 영문번역 실행이 읽기 상한(1,000)을 넘어 오래된 실행이 빠졌다."""


@with_config(FORBID)
class TranslationBatchPage(TypedDict):
    """묶음 목록 한 쪽(묶음 안 가장 새 실행이 새 것 먼저)."""

    companyName: str
    """요청의 회사 이름(고객사 사용자 = 소속 회사, 운영 관리자 = 작업 회사 — MARC-ENT-374). 회사 행이 없으면 ""(그린워싱
    checks 의 companyName 과 같은 값)."""
    count: Count
    """거른 뒤 묶음 수."""
    isNext: bool
    truncated: bool
    """그 회사의 영문번역 실행이 읽기 상한(1,000)을 넘어 오래된 실행이 빠졌다."""
    results: list[TranslationBatch]


BATCH_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    BATCH_SHAPE: TypeAdapter[TranslationBatch](
        Annotated[TranslationBatch, Field(title=BATCH_SHAPE, description="영문번역 묶음 하나.")]
    )
}
"""꼴 id → 검사기. validate_python(묶음, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
