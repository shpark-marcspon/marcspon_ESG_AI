"""운영 관리자 실행 기록(AU1b-2 — AD-04)의 응답 꼴. 필드 이름은 camelCase, id 는 정수(XC 의 꼴).

칸은 전부 required 이고 값이 없으면 null 이다. 실행의 options·error_message·단계 산출·LLM 프롬프트·응답 본문은 싣지
않는다(비밀 0). 검토(review)·AI 설정(aiSetting) 칸(AD4S)은 모듈의 원천이 채운다(runs/extras.py — 원천이 없는 모듈은
null). 뒤 밴드가 칸을 더할 때는 이름 있는 칸 하나씩(계약이 늘 닫힌 꼴). 실행 상태의 값은 runs 의 RunStatus.
실행 상세(AD4D — RunLogDetailOut)는 줄 칸(RunLogOut) 그대로에 실패 단계·오류 코드·단계(시각·토큰·비용)·결과 파일의
이름을 더한다. 단계별 토큰·비용은 단계 칸이 실린 LLM 줄(AD4D 뒤의 실행)로만 센다 — 단계를 모르는 줄이 하나라도 있으면
단계 값은 전부 null 이고 stepUsageRecorded false(줄 칸의 합계는 그대로).
같이 시작한 묶음 칸 넷(LK1 — launchKey·launchFirstRunId·launchIndex·launchSize)과 resumedFromRunId 는 runs 의
selector 가 채운다. 묶음은 같은 회사·같은 사람·같은 열쇠의 실행 전부(거르기·쪽과 무관), 차례는 id 오름. 묶음
없이 만든 실행은 넷 다 null(launchSize 1 이 아니다).
"""

from typing import Literal

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import KstDateTime, LimitOffsetPage
from esgapi.runs.service.schemas.runs import RunStatus, RunStepStatus

DURATION_DESCRIPTION = "처리 시간(초, 버림) = 끝난 때 − 만든 때(큐 대기 포함 — MARC-ENT-327). 끝나지 않았으면 null"
REVIEW_DESCRIPTION = (
    "검토 상태. 그 모듈 화면이 검토를 보이는 실행(그린워싱: 완료·결과 있음·점검 실행 아님)에만 값이고 검토를 시작하지"
    " 않았으면 pending. 그 밖의 실행·검토가 없는 모듈은 null"
)

# 검토 상태 셋(runs 의 operator.REVIEW_STATES 와 같은 값)
ReviewState = Literal["pending", "in_review", "confirmed"]


class RunAiSettingOut(Schema):
    id: int | None = Field(description="AI 설정 판의 id. 기본 판이면 null")
    name: str = Field(description="AI 설정 판의 이름(예 v3). 기본 판은 그 이름(예 colab-2026-01-15-v1)")


class RunLogOut(Schema):
    id: int
    module: str = Field(description="모듈 id. 예: greenwash")
    flowId: str = Field(description="흐름 id@판")
    documentId: int | None = Field(description="실행한 문서의 id. 문서 없는 흐름의 실행이면 null")
    documentName: str | None = Field(
        description="실행한 문서의 파일 이름(같은 회사의 문서). 문서 없는 흐름의 실행이면 null"
    )
    status: RunStatus
    createdAt: KstDateTime = Field(description="실행을 만든 때")
    startedAt: KstDateTime | None = Field(description="처음 잡힌 때. 한 번도 안 돌았으면 null")
    finishedAt: KstDateTime | None = Field(description="done·failed 로 끝난 때. 끝나지 않았으면 null")
    createdByUserId: int = Field(description="실행을 만든 사람의 id(올린 사람)")
    createdByName: str | None = Field(description="그 사람의 지금 이름(읽을 때 푼다). 풀리지 않으면 null")
    createdByUsername: str | None = Field(description="그 사람의 지금 아이디(읽을 때 푼다). 풀리지 않으면 null")
    durationSec: int | None = Field(description=DURATION_DESCRIPTION)
    tokens: int = Field(
        description="그 실행에 붙은 AI 호출의 청구 토큰 합(입력 + 캐시 읽기 + 캐시 쓰기 + 출력). 호출이 없으면 0"
    )
    costUsd: float = Field(description="그 실행에 붙은 AI 호출의 비용 합(USD, 추정). 호출이 없으면 0")
    isTest: bool = Field(description="테스트 실행(purpose=test)이면 true — 지표에서는 빠진다")
    review: ReviewState | None = Field(description=REVIEW_DESCRIPTION)
    aiSetting: RunAiSettingOut | None = Field(
        description="그 실행이 쓴 AI 설정 판(실행을 만들 때 적힌 값). AI 설정이 없는 모듈이거나 적히지 않았으면 null"
    )
    launchKey: str | None = Field(description="같이 시작한 묶음의 열쇠. 묶음 없이 만든 실행이면 null")
    launchFirstRunId: int | None = Field(
        description="묶음의 첫 실행 id(id 가 가장 작은 것). 묶음 없이 만든 실행이면 null"
    )
    launchIndex: int | None = Field(description="묶음 안 차례(1부터, id 오름). 묶음 없이 만든 실행이면 null")
    launchSize: int | None = Field(
        description="묶음의 실행 수(거르기·쪽과 무관 — 같은 회사·같은 사람·같은 열쇠 전부). "
        "묶음 없이 만든 실행이면 null"
    )
    resumedFromRunId: int | None = Field(description="이어서 돌린 앞 실행의 id. null = 처음부터 돈 실행")


STEP_TOKENS_DESCRIPTION = (
    "그 단계에서 일어난 AI 호출의 청구 토큰 합(줄 칸 tokens 와 같은 셈). 호출이 없으면 0. 단계를 모르는 실행"
    "(stepUsageRecorded false)이면 null"
)


class RunLogStepOut(Schema):
    name: str = Field(description="단계 이름(흐름이 선언한 이름)")
    position: int = Field(description="선언 차례(0부터)")
    status: RunStepStatus
    startedAt: KstDateTime | None = Field(description="처음 시작한 때(다시 넣기 뒤에도 그대로). 시작 전이면 null")
    finishedAt: KstDateTime | None = Field(description="done·failed 로 끝난 때. 끝나지 않았으면 null")
    durationSec: int | None = Field(
        description="단계 시간(초, 버림) = 끝난 때 − 처음 시작한 때(다시 넣기 대기 포함). 끝나지 않았으면 null"
    )
    tokens: int | None = Field(description=STEP_TOKENS_DESCRIPTION)
    costUsd: float | None = Field(
        description="그 단계에서 일어난 AI 호출의 비용 합(USD, 추정). 호출이 없으면 0. 단계를 모르는 실행이면 null"
    )


class RunLogFileOut(Schema):
    name: str = Field(description="파일 이름")
    step: str | None = Field(description="그 파일을 낸 단계. 흐름의 출력 파일이면 null")
    mediaType: str
    sizeBytes: int


class RunLogDetailOut(RunLogOut):
    failedStep: str | None = Field(description="실패한 단계 이름. 실패하지 않았거나 단계 밖에서 실패했으면 null")
    errorCode: str | None = Field(description="실패의 오류 코드(실행의 것 그대로). 실패하지 않았으면 null")
    stepUsageRecorded: bool = Field(
        description="단계별 토큰·비용을 아는가. AD4D 앞의 실행이나 단계 밖 AI 호출이 있는 실행은 false(합계만)"
    )
    steps: list[RunLogStepOut] = Field(description="단계(선언 차례)")
    files: list[RunLogFileOut] = Field(description="결과 파일(만든 차례 — 내려받기 경로는 없다)")


class RunLogPageOut(LimitOffsetPage[RunLogOut]):
    pass


class RunMetricsOut(Schema):
    """고른 회사에서 이번 달(서버 시계의 KST 그달 1일 00:00 ~ 다음 달 1일 00:00)에 만든 실행의 지표.
    테스트 실행은 뺀다."""

    month: str = Field(description="KST 의 달(YYYY-MM)")
    runs: int = Field(description="그달에 만든 실행 수(상태 무관)")
    averageDurationSec: int | None = Field(
        description="그달에 만든 실행 가운데 done 의 처리 시간(초) 평균, 반올림. done 이 없으면 null"
    )
    tokens: int = Field(description="그달에 만든 실행에 붙은 AI 호출의 청구 토큰 합")
    costUsd: float = Field(
        description="그달에 만든 실행에 붙은 AI 호출의 비용 합(USD, 추정 — 실행 밖 AI 호출은 빠진다)"
    )
    failureRate: float | None = Field(
        description="끝난 실행 가운데 failed 의 비율 failed / (done + failed), 0~1. 없으면 null"
    )
    aiProviderMock: bool = Field(
        description="AI 호출이 모의 공급사인가(LLM_RUN_MODE 가 live 가 아니면 참) — AD-04 안내 띠의 근거. "
        "응답한 서버의 설정이다(워커가 다른 값으로 뜨면 어긋난다 — 운영 점검표)"
    )
