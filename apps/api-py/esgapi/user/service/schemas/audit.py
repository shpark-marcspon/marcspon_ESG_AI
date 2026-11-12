"""감사 기록 조회 경로(AU1a — AD-05, 운영 관리자 전용)의 응답 꼴. 필드 이름은 camelCase, id 는 정수(XC 의 꼴).

칸은 전부 required 이고 값이 없으면 null 이다. detail 을 통째로 내보내지 않는다 — 이름 있는 칸(changedFields)만.
뒤 밴드가 칸을 더할 때는 이름 있는 칸 하나씩(계약이 늘 닫힌 꼴). 행동·결과·행위자 갈래의 값은 core/calc/audit.py 의 것.
"""

from typing import Literal

from ninja import Schema
from pydantic import Field

from esgapi.core.calc.audit import ActorKind, AuditAction, AuditResult
from esgapi.core.schemas import KstDateTime, LimitOffsetPage

ACTION_DESCRIPTION = (
    "login 로그인 · logout 로그아웃 · upload 업로드 · setting_change 계정 설정 변경 · run 실행 · download 내려받기 · "
    "adopt 채택 · exclude 제외 · confirm 확정. 실행·내려받기·채택·제외·확정은 뒤 밴드가 기록을 시작한다"
)


class AuditEventOut(Schema):
    id: int
    at: KstDateTime = Field(description="일이 일어난 때")
    companyId: int | None = Field(description="그 줄의 회사. 운영 관리자·관리 명령·회사를 못 찾은 로그인은 null")
    actorKind: ActorKind = Field(
        description="admin 운영 관리자 · service 고객사 사용자 · command 관리 명령 · anonymous 모르는 아이디"
    )
    actorUserId: int | None = Field(description="한 사람의 id. command·anonymous 는 null")
    actorName: str | None = Field(description="그 사람의 지금 이름(읽을 때 푼다). 풀리지 않으면 null")
    actorUsername: str | None = Field(description="그 사람의 지금 아이디(읽을 때 푼다). 풀리지 않으면 null")
    action: AuditAction = Field(description=ACTION_DESCRIPTION)
    event: str = Field(description="사건 이름(예 login_failed·user_updated·document_uploaded)")
    result: AuditResult
    reason: str | None = Field(
        description="실패 까닭 코드(wrong_password·unknown_user·inactive_user·account_locked). 성공이면 null"
    )
    targetKind: str | None = Field(description="대상의 갈래(user·document …)")
    targetId: int | None
    targetLabel: str | None = Field(description="대상을 사람이 알아볼 글자(사용자 아이디·파일 이름) — 그때의 값")
    changedFields: list[str] | None = Field(description="계정 수정에서 바뀐 칸의 이름(값은 싣지 않는다)")
    module: str | None = Field(
        description="그 줄이 어느 모듈의 일인가(모듈 id — 예 greenwash). 모듈과 무관하거나 옛 줄이면 null"
    )
    requestId: str | None


class AuditPageOut(LimitOffsetPage[AuditEventOut]):
    pass


class AuditActorOut(Schema):
    """감사 기록에 나온 한 사람(AU1b-1 — 사람 고르기). 이름이 풀리지 않으면(지운 사람·남의 회사 사람) 이름 칸이 null."""

    actorKind: Literal["admin", "service"] = Field(description="admin 운영 관리자 · service 고객사 사용자")
    actorUserId: int = Field(description="그 사람의 id — GET /audit-logs 의 actorUserId 로 거른다")
    actorName: str | None = Field(description="그 사람의 지금 이름. 풀리지 않으면 null")
    actorUsername: str | None = Field(description="그 사람의 지금 아이디. 풀리지 않으면 null")


class AuditActorListOut(Schema):
    results: list[AuditActorOut] = Field(
        description="이름이 풀린 사람 먼저 아이디 차례(같으면 갈래·id), 풀리지 않은 사람은 맨 뒤 id 차례"
    )
