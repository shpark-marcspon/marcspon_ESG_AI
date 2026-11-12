"""입력 꼴 drafting.outline@1 과 결과 꼴 drafting.bullets@3 의 정의. TypedDict → JSON 스키마(밴드 RP1 ①, 결정
MARC-ENT-501 — 1차 = 전년도 보고서 PDF + 목차 → 개조식 초안. @2 는 밴드 RP2b, 결정 MARC-ENT-514 2번 — @1 을 갈음.
@3 은 밴드 RP2c, 514 3번 — @2 를 갈음: 앞 실행 이어 받기 base·잎의 reusedFrom·basis.pagesSha256).

목차(outline)는 마디를 앞차례(부모가 먼저)로 나열한 목록이다. 꼴만 여기서 보고, 트리 규칙(key 꼴·겹침·depth·부모
차례·마디·잎 수)은 받기 contracts/wire.accept_outline 이 사람에게 보일 한 문장으로 막는다.

결과는 목차 잎마다 bullet 목록이다. bullet 의 출처(sources)는 모델이 댄 블록·문장 번호를 서버 코드
(engines/v2/checks.py)가 대 본 뒤의 것이다(준 블록인가 · 번호가 범위 안인가 · bullet 숫자가 출처 블록 글에 있는가) —
근거가 남지 않으면 unsupported 다(지우지 않는다). 출처는 블록(표면 표) 하나와 그 안의 문장(표면 행) 번호(0부터)이고,
상자는 PDF pt·왼쪽 위 원점(쪽 크기는 document.pages). 문장 자리를 못 내면 sentence null 하나로 말한다. 머리 basis 는
실행이 선 분해 한 벌, base 는 이어 받은 앞 실행(목차를 고친 뒤 — 같은 분해·판·설정이면 안 바뀐 잎을 옮긴다). 갈래는
판별 칸 status 로 가른다. 사용량·비용은 싣지
않는다(실행기의 기록이 진실이다).

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다(use_attribute_docstrings). 프론트는 고정 파일
tests/data/flow-shapes/*.schema.json 을 읽는다. 꼴을 바꾸면 새 판이다. openapi 는 이름이 같은 컴포넌트를 하나로
합치므로 이름마다 Drafting 머리를 단다.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, TypedDict

from pydantic import ConfigDict, Field, StrictInt, TypeAdapter, with_config

OUTLINE_SHAPE: Final = "drafting.outline@1"
RESULT_SHAPE: Final = "drafting.bullets@3"
FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True)

# 목차 상한(발주서 §2-1 · 처분 ⑨). 표의 CHECK(migrations/0001_initial.py)는 값을 문면에 굳힌다 — 바꾸면 새 마이그레이션.
KEY_PATTERN: Final = r"^[a-z0-9][a-z0-9-]{0,39}$"
KEY_MAX_CHARS: Final = 40
DEPTH_MAX: Final = 4
NODES_MAX: Final = 300
LEAVES_MAX: Final = 150
TITLE_MAX_CHARS: Final = 200
REQUIREMENT_MAX_CHARS: Final = 2000
# 결과 상한(처분 ⑨) — 엔진이 지킨다(bullets_capped·글 자름).
BULLETS_MAX: Final = 15
BULLET_MAX_CHARS: Final = 200

Page = Annotated[int, Field(ge=1)]
Count = Annotated[int, Field(ge=0)]
Box = Annotated[list[float], Field(min_length=4, max_length=4)]
"""[x0, y0, x1, y1] — PDF pt, 왼쪽 위 원점."""


# ── drafting.outline@1 ───────────────────────────────────────────────────────────────────────────────────────


@with_config(FORBID)
class DraftingOutlineNode(TypedDict):
    """목차 마디 하나(대·중·소·소소 = depth 1~4)."""

    key: str
    """마디 열쇠(목차 안에서 하나, `^[a-z0-9][a-z0-9-]{0,39}$`). 결과의 잎 key 가 이것이다."""
    parentKey: str | None
    """부모 마디의 key. 첫 층(depth 1)은 null. 부모는 목록에서 앞에 온다."""
    depth: StrictInt  # 요청 본문 안에서도 true 를 1 로 받지 않는다(config/tests/test_request_schemas_reject_bool)
    """층(1 = 대, 2 = 중, 3 = 소, 4 = 소소). 부모 depth + 1."""
    title: str
    """마디 제목(앞뒤 공백을 뺀 1~200자)."""
    requirement: str
    """그 마디에 쓸 요구 내용(0~2,000자). 잎만 S3 재료에 실린다."""


@with_config(FORBID)
class DraftingOutline(TypedDict):
    """drafting.outline@1 — 목차 통째. 마디를 앞차례로 나열한다(부모 → 자식, 형제는 목록 차례)."""

    nodes: list[DraftingOutlineNode]
    """마디 1~300(잎 1~150). 잎 = 자식이 없는 마디."""


# ── drafting.bullets@3 ───────────────────────────────────────────────────────────────────────────────────────

FailureKind = Literal[
    "unparsable",
    "provider_error",
    "timeout",
    "refusal",
    "truncated",
    "budget_exceeded",
    "schema_mismatch",
]
"""실패 갈래. unparsable 밖은 core.llm 의 LlmResult 갈래 이름이다(materiality 계약의 판별 복사 — 계약은 core 를
import 하지 않고, 시험이 견준다)."""


@with_config(FORBID)
class DraftingFailure(TypedDict):
    """호출이나 답 읽기가 실패한 까닭."""

    kind: FailureKind
    """unparsable = 모델의 답을 읽지 못함. 그 밖은 모델 호출의 실패 갈래(core.llm 의 이름 그대로)."""
    message: str
    """실패 갈래의 설명(모델 글·공급사 메시지·고객 데이터는 싣지 않는다)."""


@with_config(FORBID)
class DraftingParser(TypedDict):
    """분해한 파서."""

    name: str
    version: str
    layout: Literal[1, 2]
    """분해 판(2 = 머리글·꼬리말 갈림)."""


@with_config(FORBID)
class DraftingBasis(TypedDict):
    """실행이 선 문서 분해 한 벌(core 문서 산출물)."""

    artifactId: Annotated[int, Field(ge=1)]
    """core 문서 산출물 id."""
    parser: DraftingParser
    epoch: Annotated[int, Field(ge=1)]
    """산출물 판 열쇠의 EPOCH."""
    pagesSha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None
    """쪽 글 목록의 sha256(앞 실행 이어 받기의 분해 열쇠). null = 분해 행은 있으나 쪽 글을 펴지 않음(rejected
    too_large 행)."""


@with_config(FORBID)
class DraftingBase(TypedDict):
    """이어 받은 앞 실행(옵션 base.runId)과 이어 받았는가."""

    runId: Annotated[int, Field(ge=1)]
    """앞 실행 id."""
    outlineId: Annotated[int, Field(ge=1)]
    """앞 실행이 읽은 목차 판 id."""
    matched: bool
    """앞 실행과 분해·판·설정이 같아 안 바뀐 잎을 옮겼는가(false 면 전부 다시 지었다 — 경고 base_not_reused)."""
    reason: Literal["document", "versions", "settings", "base_rejected"] | None
    """matched false 의 까닭(document = 분해가 다름 · versions = 판이 다름 · settings = 경로·프롬프트가 다름 ·
    base_rejected = 앞 실행이 거절로 끝남). matched true 면 null."""


@with_config(FORBID)
class DraftingLeafOrigin(TypedDict):
    """옮긴 잎을 실제로 지은 실행."""

    runId: Annotated[int, Field(ge=1)]
    """그 잎을 지은 실행 id(옮김이 이어지면 처음 지은 실행)."""
    outlineId: Annotated[int, Field(ge=1)]
    """그 실행이 읽은 목차 판 id."""


@with_config(FORBID)
class DraftingSentence(TypedDict):
    """출처 블록 안의 문장 하나(표면 행 하나)."""

    index: Annotated[int, Field(ge=0)]
    """문장 번호(0부터 — 재료 표지·모델 답과 같은 번호). 표면 실제 행 번호(0부터, 빈 행이 빠져 건너뛸 수 있음)."""
    boxes: Annotated[list[Box], Field(min_length=1)]
    """그 문장의 줄 상자(줄마다 하나). 표 행이면 그 행 칸들의 합집합 하나."""


@with_config(FORBID)
class DraftingSource(TypedDict):
    """bullet 의 근거 한 블록(표면 표 하나)."""

    documentId: Annotated[int, Field(ge=1)]
    """전년도 보고서 문서 id(실행이 읽은 문서)."""
    blockId: str
    """분해의 블록 id(표면 표 id)."""
    page: Page
    """쪽 번호(1부터)."""
    blockBox: Box
    """블록(표) 상자."""
    sentence: DraftingSentence | None
    """근거 문장. null = 문장 자리를 못 냄(번호가 없거나 범위 밖, 또는 글자 자리가 없음) — 블록 상자만."""


@with_config(FORBID)
class DraftingBullet(TypedDict):
    """개조식 한 줄."""

    text: str
    """bullet 글(1~200자)."""
    sources: list[DraftingSource]
    """서버가 대 보고 남긴 근거(쪽 → 블록 차례 → 문장 번호 차례, 겹침 없음). 비면 unsupported 다."""
    unsupported: bool
    """근거 불명확(서버 판정 — 준 블록이 아니거나 bullet 의 숫자가 출처 블록 글에 없음). 지우지 않고 표시만."""


@with_config(FORBID)
class DraftingLeafDone(TypedDict):
    """잎의 초안을 지었다."""

    status: Literal["done"]
    bullets: list[DraftingBullet]
    """0~15 줄. 0 이면 모델이 근거로 쓸 사실을 찾지 못한 것이다."""


@with_config(FORBID)
class DraftingLeafNoMaterial(TypedDict):
    """그 잎에 달린 쪽이 없다(S2 가 어느 쪽에도 그 잎을 달지 않음) — 호출하지 않았다."""

    status: Literal["no_material"]


@with_config(FORBID)
class DraftingLeafFailed(TypedDict):
    """그 잎의 호출이나 답 읽기가 실패했다."""

    status: Literal["failed"]
    failure: DraftingFailure


@with_config(FORBID)
class DraftingLeafNotRun(TypedDict):
    """그 잎을 돌리지 않았다(실행이 rejected 로 멈춤)."""

    status: Literal["not_run"]
    reason: str
    """돌리지 않은 까닭(사람에게 보일 한 문장)."""


DraftingOutcome = Annotated[
    DraftingLeafDone | DraftingLeafNoMaterial | DraftingLeafFailed | DraftingLeafNotRun,
    Field(discriminator="status"),
]


@with_config(FORBID)
class DraftingLeaf(TypedDict):
    """목차 잎 하나의 결과(목차 차례)."""

    key: str
    """목차 마디 key."""
    titlePath: list[str]
    """대 → 잎 제목 경로."""
    pages: list[Page]
    """S2 가 이 잎에 단 쪽(쪽 차례, 겹침 없음). 옮긴 잎은 앞 실행의 쪽."""
    reusedFrom: DraftingLeafOrigin | None
    """앞 실행에서 옮긴 잎이면 그 잎을 지은 실행(쪽·bullet·상자를 그대로 옮김). null = 이 실행이 지음."""
    outcome: DraftingOutcome


@with_config(FORBID)
class DraftingStatusDone(TypedDict):
    """실행을 끝까지 돌렸다(잎마다의 성패는 outcome 이 말한다)."""

    status: Literal["done"]


@with_config(FORBID)
class DraftingStatusRejected(TypedDict):
    """공급사를 부르기 전에 멈췄다."""

    status: Literal["rejected"]
    code: Literal["over_budget", "too_large"]
    """over_budget = 비용 위끝이 상한(DRAFTING_RUN_MAX_USD)을 넘음, too_large = 쪽 수 상한(300)을 넘음."""
    stage: Literal["before_map", "before_draft"]
    """before_map = 쪽 → 목차 연결 전(호출 0), before_draft = 연결 뒤 초안 전(mapping 은 실리고 잎은 전부 not_run)."""
    message: str


DraftingStatus = Annotated[DraftingStatusDone | DraftingStatusRejected, Field(discriminator="status")]


@with_config(FORBID)
class DraftingPageSize(TypedDict):
    """쪽 크기(PDF pt — 상자의 축척)."""

    page: Page
    width: float
    height: float


@with_config(FORBID)
class DraftingDocument(TypedDict):
    """실행이 읽은 전년도 보고서."""

    documentId: Annotated[int, Field(ge=1)]
    fileName: str
    pageCount: Count
    """PDF 의 쪽 수."""
    textPages: Count
    """글자가 있는 쪽 수(빈 쪽 = 그림·스캔뿐)."""
    pages: list[DraftingPageSize]
    """분해한 쪽의 크기(쪽 오름). 분해 결과가 없으면(rejected too_large) 빈 목록."""


@with_config(FORBID)
class DraftingFailedBatch(TypedDict):
    """실패한 S2 묶음(그 쪽들은 어느 잎에도 달리지 않았다)."""

    firstPage: Page
    lastPage: Page
    failure: DraftingFailure


@with_config(FORBID)
class DraftingMapping(TypedDict):
    """S2(쪽 → 목차 잎) 묶음의 셈."""

    batches: Count
    """이 실행의 S2 묶음 수(호출 수 — 앞 실행을 이어 받아 다시 달 잎이 없으면 0 일 수 있음)."""
    failedBatches: list[DraftingFailedBatch]


@with_config(FORBID)
class DraftingStepPair(TypedDict):
    """단계 둘(map = S2 쪽 → 목차, draft = S3 개조식)의 값."""

    map: str
    draft: str


@with_config(FORBID)
class DraftingSettings(TypedDict):
    """실행이 쓴 경로·프롬프트."""

    routes: DraftingStepPair
    """모델 경로 이름(models.json 의 route — 모의 실행이면 mock)."""
    promptIds: DraftingStepPair
    """프롬프트 id@판."""


WarningCode = Literal[
    "page_truncated",
    "material_truncated",
    "mapping_incomplete",
    "unknown_key",
    "page_out_of_batch",
    "source_not_given",
    "sentence_out_of_range",
    "unsupported_bullet",
    "number_not_in_source",
    "bullets_capped",
    "base_not_reused",
    "source_block_missing",
]


@with_config(FORBID)
class DraftingWarning(TypedDict):
    """경고 하나."""

    code: WarningCode
    message: str
    """사람에게 보일 한 문장(모델 글을 옮기지 않는다)."""
    key: str | None
    """그 경고의 목차 잎 key(없으면 null)."""
    page: int | None
    """그 경고의 쪽(없으면 null)."""


@with_config(FORBID)
class DraftingResult(TypedDict):
    """drafting.bullets@3 — 원고작성 한 실행의 결과. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["drafting.bullets@3"]
    basis: DraftingBasis | None
    """실행이 선 분해 한 벌. 산출물을 얻지 못하고 거절됐으면(rejected too_large — 분해 거절) null."""
    base: DraftingBase | None
    """이어 받은 앞 실행(옵션 base). 옵션에 base 가 없으면 null."""
    projectId: Annotated[int, Field(ge=1)]
    outlineId: Annotated[int, Field(ge=1)]
    """실행이 읽은 목차 판의 id(만들 때 박은 판 — 큐 중에 목차를 고쳐도 이 판)."""
    outlineSha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    status: DraftingStatus
    document: DraftingDocument
    leaves: list[DraftingLeaf]
    """목차 잎 전부(목차 차례)."""
    mapping: DraftingMapping
    settings: DraftingSettings
    warnings: list[DraftingWarning]


OUTLINE_SHAPES: Final[Mapping[str, TypeAdapter[DraftingOutline]]] = {
    OUTLINE_SHAPE: TypeAdapter[DraftingOutline](
        Annotated[DraftingOutline, Field(title=OUTLINE_SHAPE, description="원고작성의 목차(대·중·소·소소).")]
    )
}
"""입력 꼴 id → 검사기."""
RESULT_SHAPES: Final[Mapping[str, TypeAdapter[DraftingResult]]] = {
    RESULT_SHAPE: TypeAdapter[DraftingResult](
        Annotated[DraftingResult, Field(title=RESULT_SHAPE, description="원고작성 한 실행의 결과(잎마다 개조식).")]
    )
}
"""결과 꼴 id → 검사기. validate_python(결과, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""


def check_result(result: Mapping[str, Any]) -> None:
    """결과 꼴(strict). 아니면 pydantic ValidationError."""
    RESULT_SHAPES[RESULT_SHAPE].validate_python(result, strict=True)
