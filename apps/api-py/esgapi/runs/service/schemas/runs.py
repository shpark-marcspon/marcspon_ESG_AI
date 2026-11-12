"""실행(run)의 요청과 응답의 꼴(JSON). 필드 이름은 camelCase, id 는 int 다.

★ 계약 먼저: 경로(runs/service/apis/runs.py)는 아직 몸이 없고 501 을 낸다. 꼴이 openapi(generated/)에 서는 것이
  이 판의 일이다.
  X1a 가 이 파일을 core/service/schemas/ 에서 runs 앱으로 옮겼다 — 클래스 이름·docstring·Field(description)·기본값·
  pattern 은 바이트 같게.
★ 요청 본문에 테넌트·사용자의 칸이 없다(세션에서만 온다). 모르는 칸은 거절한다(StrictIn).
★ module·flowId 의 무늬는 흐름 레지스트리(core/flows/registry.py)의 MODULE_ID·VERSIONED_ID 에 ^…$ 를 붙인 것이다.
  같은지는 config/tests/test_api_contract.py 가 잰다.
★ options 는 JSON 객체 하나다. 모듈별 옵션의 꼴(그린워싱의 쪽 범위 등)은 그 흐름의 입력 꼴(input_shape)이 정하고
  X1b 가 그것으로 검사한다 — 그린워싱 옵션의 꼴은 검증 트랙(G1a/GC1)이 정한다.
★ launchKey(LK1 — 선택)의 무늬는 Idempotency-Key 와 같은 소문자 UUID(runs/calc/idempotency.py 의 KEY_PATTERN)다.
  같이 시작한 실행(사람 동작 한 번)의 묶음 열쇠라 응답은 바뀌지 않고, 운영 관리자 실행 기록이 묶음을 싣는다.
★ retrySegments(RM1c — 선택): done 실행에서 고른 구획만 같은 판으로 다시 도는 새 실행. keys 상한 10,000 은 펼침 단계
  max_segments 의 상한(core/flows/types.py 의 FanoutStep)이고 단계의 max_segments 밖·겹침·모르는 열쇠는 action 이
  거절한다(RETRY_SEGMENTS_UNKNOWN). 구획 목록(RunSegmentOut)은 data 를 싣지 않는다(열쇠·상태·시각만).
"""

from typing import Annotated, Literal

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import KstDateTime, LimitOffsetPage, StrictIn
from esgapi.runs.calc.idempotency import KEY_PATTERN

# 실행의 상태: 지금 일감(core/calc/documents.py 의 JobStatus) 글자 그대로. 단계의 상태는 pending·running 을 새로 둔다.
RunStatus = Literal["queued", "processing", "done", "failed"]
RunStepStatus = Literal["pending", "running", "done", "failed"]

MODULE_PATTERN = r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*)*$"
FLOW_ID_PATTERN = r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9-]*)+@[A-Za-z0-9]+$"


SEGMENT_SHA_PATTERN = r"^[0-9a-f]{64}$"


class RunRetrySegmentsIn(StrictIn):
    """done 실행에서 고른 구획만 다시(RM1c). 나머지 구획·앞 단계 산출은 앞 실행에서 옮겨 쓴다."""

    fromRunId: int = Field(description="고른 구획의 앞 실행 id(done 실행만)")
    step: str = Field(max_length=100, description="고른 구획의 펼침 단계 이름")
    keys: list[Annotated[str, Field(pattern=SEGMENT_SHA_PATTERN)]] = Field(
        min_length=1,
        max_length=10_000,
        description="다시 돌 구획의 열쇠 sha256(GET /runs/{run_id}/segments 의 keySha256). 겹치면 422",
    )


class RunIn(StrictIn):
    """문서 하나를 어떤 모듈(흐름)로 돌릴지(문서 없는 흐름은 문서 없이). 실행은 늘 새로 만든다."""

    module: str = Field(pattern=MODULE_PATTERN, description="모듈 id. 예: greenwash")
    flowId: str | None = Field(
        default=None, pattern=FLOW_ID_PATTERN, description="흐름 id@판. 없으면 그 모듈의 기본 흐름"
    )
    documentId: int | None = Field(
        default=None,
        description="돌릴 문서의 id. 문서 요구 흐름은 필수(없으면 422 DOCUMENT_REQUIRED), "
        "문서 없는 흐름은 주지 않는다(주면 422 DOCUMENT_NOT_ACCEPTED)",
    )
    options: dict[str, object] = Field(default={}, description="모듈별 옵션(JSON 객체). 꼴은 흐름의 입력 꼴이 정한다")
    resumeFromRunId: int | None = Field(
        default=None, description="앞 실행의 id. 주면 그 실행의 체크포인트를 참조해 멈춘 단계부터 새 실행으로 돈다"
    )
    launchKey: str | None = Field(
        default=None,
        pattern=KEY_PATTERN,
        description="선택. 소문자 UUID. 같이 시작한 실행(사람 동작 한 번)의 묶음 열쇠 — 다시 하기는 새 열쇠",
    )
    retrySegments: RunRetrySegmentsIn | None = Field(
        default=None,
        description="선택. done 실행에서 고른 구획만 같은 판으로 다시 도는 새 실행"
        "(resumeFromRunId 와 같이 줄 수 없다). AI 설정·흐름 판이 앞 실행과 다르면 409 "
        "RETRY_VERSION_CHANGED — 처음부터 새 실행으로",
    )


class RunCreatedOut(Schema):
    id: int
    status: RunStatus


class RunStepSegmentsOut(Schema):
    """펼침 단계의 구획 셈(RM1b). 끝난 실행에도 running 이 남을 수 있다(fail_run 에서 돌던 구획의 산출을 버림)."""

    planned: int | None = Field(
        description="계획된 구획 수. null = 아직 계획 전(단계 pending·running·failed 이고 구획 행 0). "
        "0 = 계획이 빈 채 단계가 끝남"
    )
    pending: int
    running: int
    done: int
    failed: int
    firstStartedAt: KstDateTime | None = Field(description="가장 이른 구획 시작. 시작한 구획이 없으면 null")
    lastFinishedAt: KstDateTime | None = Field(description="가장 늦은 구획 끝. 끝난 구획이 없으면 null")


class RunStepOut(Schema):
    """흐름이 선언한 단계 하나. 실행을 만들 때부터 전부 선언 차례로 실린다(처음에는 pending)."""

    step: str
    status: RunStepStatus
    done: int | None
    total: int | None
    segments: RunStepSegmentsOut | None = Field(
        default=None,
        description="펼침 단계의 구획 셈(RM1b). 장벽 단계·등록 밖 흐름은 null. 병렬로 돈 펼침 단계는 done·total 이 "
        "null 이고 이 칸이 갈음한다. 끝난 실행에도 running 이 남을 수 있다(fail_run 에서 돌던 구획의 산출을 버림)",
    )


class RunSummaryOut(Schema):
    id: int
    module: str
    flowId: str
    documentId: int | None = Field(description="실행한 문서의 id. 문서 없는 흐름의 실행이면 null")
    documentName: str | None = Field(description="실행한 문서의 파일 이름. 문서 없는 흐름의 실행이면 null")
    status: RunStatus
    createdAt: KstDateTime
    finishedAt: KstDateTime | None


class RunPageOut(LimitOffsetPage[RunSummaryOut]):
    pass


class RunOut(Schema):
    id: int
    module: str
    flowId: str = Field(description="흐름 id@판")
    documentId: int | None = Field(description="실행한 문서의 id. 문서 없는 흐름의 실행이면 null")
    options: dict[str, object]
    status: RunStatus
    steps: list[RunStepOut]
    createdAt: KstDateTime
    startedAt: KstDateTime | None
    finishedAt: KstDateTime | None
    failedStep: str | None
    errorCode: str | None
    errorMessage: str | None = Field(description="사람에게 보일 글. 단계 예외의 원문은 기록에만 남는다")
    resumedFromRunId: int | None = Field(description="이어서 돌린 앞 실행의 id. null = 처음부터 돈 실행")
    resultShapes: list[str] = Field(description="결과의 schemaVersion. 예: greenwash.result@1")
    files: list[str] = Field(description="출력 파일 이름. GET /runs/{run_id}/files/{name} 으로 내려받는다")


RunSegmentStatus = Literal["pending", "running", "done", "failed"]


class RunSegmentKeyOut(Schema):
    """구획 열쇠의 정규화 칸(kind·span 은 모듈이 정하는 표지 — span 은 위치만)."""

    kind: str
    span: str
    documentSha256: str | None
    parserVersion: str | None


class RunSegmentOut(Schema):
    """펼침 단계의 구획 하나(RM1c). 산출(data)은 싣지 않는다. 옮겨 온 구획은 attempts 0 이고 시각은 앞 실행의 것이다."""

    position: int = Field(description="계획 차례(0부터)")
    keySha256: str = Field(description="구획 열쇠의 sha256. retrySegments.keys 에 넣는 값")
    key: RunSegmentKeyOut
    status: RunSegmentStatus
    attempts: int = Field(description="이 실행에서 그 구획을 시작한 횟수. 앞 실행에서 옮겨 온 구획은 0")
    errorCode: str | None = Field(description="failed 일 때만")
    startedAt: KstDateTime | None
    finishedAt: KstDateTime | None


class RunSegmentPageOut(LimitOffsetPage[RunSegmentOut]):
    pass


class RunSegmentListQuery(Schema):
    """`GET /runs/{run_id}/segments` 의 조회 인자. step 은 그 흐름의 펼침 단계여야 한다(아니면 422 NOT_A_FANOUT)."""

    step: str = Field(max_length=100, description="펼침 단계 이름")
    status: RunSegmentStatus | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class RunListQuery(Schema):
    """`GET /runs` 의 조회 인자. 조건은 전부 「같다」다."""

    module: str | None = Field(default=None, description="모듈 id")
    status: RunStatus | None = None
    documentId: int | None = Field(default=None, description="그 문서의 실행만")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
