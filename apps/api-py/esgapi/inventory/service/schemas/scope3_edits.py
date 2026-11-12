"""Scope 3 줄 덧판 경로의 요청·응답 꼴(JSON). 밴드 S3K2b-1 ①(발주서 1-4 — 웹 S3W3 의 거울 원천).

필드 이름은 camelCase, **응답 id 는 숫자 id 의 십진 글자**. 이름은 Scope3RowEdit 를 앞에 붙인다(사람도 자기 꼴).
"""

from typing import Literal

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import KstDateTime, PageNumberPage, StrictIn
from esgapi.inventory.service.schemas.scope3_state import Scope3YearCategoryOut


class Scope3RowEditIn(StrictIn):
    rowIds: list[str] = Field(description="그 실행 그 카테고리의 줄 rowId — 1~2,000개, 겹침 0")
    reason: str = Field(description="사유 — 앞뒤 공백을 걷고 1~300자(제외·복구 둘 다 필수)")


class Scope3RowEditCustomIn(StrictIn):
    title: str = Field(description="계수 제목 — 앞뒤 공백을 걷고 1~200자")
    value: str = Field(description="계수 값 — 0보다 큰 십진 글자, 소수 10자리까지(지수 표기 거절)")
    source: str = Field(description="출처 — 앞뒤 공백을 걷고 1~200자")


class Scope3RowEditFactorIn(StrictIn):
    rowId: str = Field(description="그 실행 그 카테고리의 줄 rowId 하나")
    choice: Literal["applied", "recommended", "custom"] = Field(
        description="applied = AI 원안으로 되돌림 · recommended = 추천 순위 · custom = 직접 입력"
    )
    rank: int | None = Field(description="추천 순위 1~4 — recommended 일 때만")
    custom: Scope3RowEditCustomIn | None = Field(
        description="직접 입력 — custom 일 때만. 단위는 그 줄의 계수 단위 그대로"
    )
    reason: str = Field(description="사유 — 앞뒤 공백을 걷고 1~300자(필수)")


class Scope3RowEditByOut(Schema):
    id: str
    name: str = Field(description="고친 사람의 지금 이름")


class Scope3RowEditAiOut(Schema):
    title: str | None = Field(description="사건 때 AI 원안의 대표 계수 제목")
    value: str | None = Field(description="AI 원안의 계수 값(십진 글자)")
    source: str | None = Field(description="AI 원안 계수의 시트 이름")
    co2e: str | None = Field(description="AI 원안의 배출량(결과 본문 글자 그대로)")


class Scope3RowEditFactorOut(Schema):
    choice: Literal["applied", "recommended", "custom"]
    rank: int | None = Field(description="추천 순위 — recommended 일 때만")
    title: str | None
    value: str | None = Field(description="고른 계수 값(십진 글자)")
    source: str | None = Field(description="고른 계수의 출처")
    unit: str | None = Field(description="계수 단위 — 그 줄의 것 그대로")
    co2e: str | None = Field(description="고른 계수로 센 배출량(applied 면 결과 본문 글자 그대로)")
    biogenicCo2e: str | None = Field(description="생물기원 배출량 — 나눔이 있는 줄(C5)만")
    ai: Scope3RowEditAiOut = Field(description="사건 때 뜬 AI 원안")


class Scope3RowEditOut(Schema):
    rowId: str
    category: str = Field(description="「C1」~「C15」(C10 뺌)")
    excluded: bool = Field(description="지금 산정에서 빠져 있다")
    factor: Scope3RowEditFactorOut | None = Field(description="지금 계수 상태 — 계수 사건이 없는 줄은 null")
    editedAt: KstDateTime = Field(description="이 줄의 마지막 편집 때(제외·계수 어느 쪽이든)")
    editedBy: Scope3RowEditByOut | None = Field(description="마지막으로 고친 사람(못 찾으면 null)")


class Scope3RowEditsOut(Schema):
    runId: str
    rows: list[Scope3RowEditOut] = Field(description="사건이 하나라도 있는 줄만 — rowId 차례")


class Scope3RowEditResultOut(Schema):
    category: Scope3YearCategoryOut = Field(description="고친 뒤 그 카테고리 상태")
    rows: list[Scope3RowEditOut] = Field(description="보낸 줄 가운데 사건이 있는 줄의 지금 상태 — rowId 차례")


class Scope3RowEditHistoryOut(Schema):
    id: str
    rowId: str
    category: str
    kind: Literal["exclude", "restore", "factor"]
    reason: str
    at: KstDateTime
    by: Scope3RowEditByOut | None = Field(description="고친 사람(못 찾으면 null)")
    batchId: str | None = Field(description="한 요청의 사건을 묶는 글자(요청 하나 = 묶음 하나)")
    factor: Scope3RowEditFactorOut | None = Field(description="계수 사건의 값 — 제외·복구 줄은 null")


class Scope3RowEditHistoryPageOut(PageNumberPage[Scope3RowEditHistoryOut]):
    pass
