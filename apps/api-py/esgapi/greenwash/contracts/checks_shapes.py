"""목록 줄 꼴 greenwash.checks@1 — `GET /greenwash/checks` 의 응답. 문서 목록 화면(GW-01)의 줄을 짓는 원재료를 한 번에
싣는다: 그 회사의 그린워싱 실행 전부와 그 실행들의 문서, 지금 사용자 id, 회사 이름(웹 CheckRowsSource 꼴 — 밴드 G1b).
TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/checks/greenwash.checks@1.schema.json.
클래스 이름이 openapi 의 구성요소 이름이 되므로 `GreenwashCheck` 로 시작한다(등급 수·확정한 사람은 결과·검토 꼴의 것을
그대로 쓴다 — 새 구성요소가 아니다).

**이 파일에 로직은 없다.** 규칙(service/actions/checks.py):
- 차례는 서버가 정하지 않는다(웹이 정렬한다). 페이지네이션 없음 — 실행은 새 것 먼저 RUNS_MAX(1000)까지, 넘으면
  truncated 가 true(G1b-2b).
- id 는 int 다(웹 어댑터가 글자로 바꾼다). 때는 +09:00 이 붙은 ISO 8601.
- reportYear·previousDocumentId 는 문서의 칸 그대로다(PATCH /documents/{id} — 비어 있으면 null. G1b-2a).
- pageCount 는 그 문서의 끝난 실행 결과(source.pageCount)에서 온다. 없으면 null.
- uploadedAt 은 올림 확인 전 문서면 null.
- levelCounts·review 는 끝난 실행만 값이고 그 밖에는 null. dry-run 실행은 review 가 null.
  levelCounts 는 효력 등급(검토에서 고친 등급 ?? AI 등급)으로 센 결과 items 전부다(G1b-3 — 꼴은 그대로, 뜻만).
  review.reviewed = 표시한 문장 수, review.total = 결과 items 수.
- 이름(uploadedBy.name·confirmedBy.name)을 못 풀면 「알 수 없는 사용자」.
- uploadedBy.userId 0 = 알 수 없음(문서의 올린 사람 칸이 사용자 id 가 아닐 때 — 이름도 「알 수 없는 사용자」).
- errorCode 는 failed 실행만 실행 기록의 error code 그대로(글자 — enum 아님), 그 밖 null(밴드 G1e).
- failedPageCount 는 끝난 실행 결과의 읽지 못한 쪽(candidateStats.failedPages) 수. 끝나지 않음·dry-run·결과 없음은
  null(G1b-2b).
"""

from collections.abc import Mapping
from typing import Final, Literal, TypedDict

from pydantic import TypeAdapter, with_config

from esgapi.greenwash.contracts.review_shapes import GreenwashReviewer, GreenwashReviewStateName
from esgapi.greenwash.contracts.shapes import FORBID, Count, LevelCounts

SHAPE: Final = "greenwash.checks@1"

GreenwashCheckRunStatus = Literal["queued", "processing", "done", "failed"]
"""실행의 상태(GET /runs/{id} 의 status 와 같다)."""
GreenwashCheckStepStatus = Literal["pending", "running", "done", "failed"]
"""단계의 상태(GET /runs/{id} 의 steps[].status 와 같다)."""


@with_config(FORBID)
class GreenwashCheckUploader(TypedDict):
    """문서를 올린 사람."""

    userId: int
    """사용자 id."""
    name: str
    """화면에 보일 이름. 못 풀면 「알 수 없는 사용자」."""


@with_config(FORBID)
class GreenwashCheckDocument(TypedDict):
    """그린워싱 실행이 하나라도 있는 문서 하나."""

    documentId: int
    fileName: str
    """올린 파일의 이름."""
    reportYear: int | None
    """보고 연도(문서의 칸). 비어 있으면 null."""
    previousDocumentId: int | None
    """수정본이면 앞 판 문서 id(문서의 칸). 비어 있으면 null."""
    pageCount: Count | None
    """쪽 수(그 문서의 끝난 실행 결과에서). 모르면 null."""
    uploadedAt: str | None
    """올린 때(+09:00 ISO 8601). 올림 확인 전이면 null."""
    uploadedBy: GreenwashCheckUploader
    """올린 사람."""


@with_config(FORBID)
class GreenwashCheckStep(TypedDict):
    """실행 단계 하나(GET /runs/{id} 의 steps 와 같은 꼴)."""

    step: str
    status: GreenwashCheckStepStatus
    done: int | None
    total: int | None


@with_config(FORBID)
class GreenwashCheckReview(TypedDict):
    """끝난 실행의 검토 요약."""

    state: GreenwashReviewStateName
    reviewed: Count
    """표시한 문장 수."""
    total: Count
    """결과의 문장 수."""
    confirmedAt: str | None
    """확정한 때(+09:00 ISO 8601). 확정 전이면 null."""
    confirmedBy: GreenwashReviewer | None
    """확정한 사람. 확정 전이면 null."""


@with_config(FORBID)
class GreenwashCheckRun(TypedDict):
    """그린워싱 실행 하나."""

    runId: int
    documentId: int
    createdAt: str
    """만든 때(+09:00 ISO 8601)."""
    finishedAt: str | None
    """끝난 때(+09:00 ISO 8601). done·failed 로 끝났을 때만, 그 밖 null(runs 의 finished_at 그대로)."""
    createdByUserId: int
    """실행을 만든 사용자 id."""
    status: GreenwashCheckRunStatus
    errorCode: str | None
    """실패 까닭 code(실행 기록 그대로 — no_text_layer·step_error·attempts_exhausted 등). failed 일 때만, 그 밖 null."""
    failedPageCount: Count | None
    """읽지 못한 쪽 수(결과 candidateStats.failedPages 의 수 — 쪽·까닭은 결과에). 끝난 실행만(dry-run 은 null)."""
    steps: list[GreenwashCheckStep]
    """단계(선언 차례)."""
    checkedPages: Count
    """점검할 쪽 수(옵션 parts 셋의 합집합)."""
    levelCounts: LevelCounts | None
    """결과의 등급별 문장 수 — 효력 등급(검토에서 고친 등급 ?? AI 등급)으로 센다. 끝난 실행만."""
    review: GreenwashCheckReview | None
    """검토 요약. 끝난 실행만(dry-run 실행은 null)."""


@with_config(FORBID)
class GreenwashChecks(TypedDict):
    """greenwash.checks@1 — 그린워싱 문서 목록의 원재료. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.checks@1"]
    currentUserId: int
    """지금 사용자 id(「내가 올린 것만」 거르기)."""
    companyName: str
    """회사 이름."""
    documents: list[GreenwashCheckDocument]
    runs: list[GreenwashCheckRun]
    truncated: bool
    """실행이 RUNS_MAX(1000)를 넘어 오래된 것이 빠졌으면 true(새 것 먼저 RUNS_MAX 까지 싣는다)."""


CHECKS_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashChecks]]] = {SHAPE: TypeAdapter(GreenwashChecks)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
