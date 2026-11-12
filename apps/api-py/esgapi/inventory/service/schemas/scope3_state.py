"""Scope 3 연도 상태·카테고리 잠금 경로의 응답 꼴(JSON). 밴드 S3K2a ①(발주서 1-4 — 웹 S3W3 의 거울 원천).
여기 적힌 것이 OpenAPI 문서와 프론트의 타입(generated/api.d.ts)이 된다.

필드 이름은 camelCase, **응답 id 는 숫자 id 의 십진 글자**, **수는 decimal_text 글자**(지수 표기 0·끝 0 걷음). 배출량은
tCO2-eq. 빈 칸은 null 로 싣는다. 이름은 Scope3Year 를 앞에 붙인다(Entry*·Scope3Colab*·Scope12Dashboard* 와 안 겹치게 —
잠근 사람도 EntryLockedByOut 을 다시 쓰지 않고 자기 꼴).
"""

from typing import Literal

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import KstDateTime


class Scope3YearLatestOut(Schema):
    runId: str = Field(description="그 해(options.reportYear) Scope 3 코랩 실행 가운데 가장 새 것의 id(어느 상태든)")
    status: Literal["queued", "processing", "done", "failed"]


class Scope3YearCurrentOut(Schema):
    runId: str = Field(description="이 카테고리의 지금 결과 실행 id — 잠겼으면 핀 실행, 아니면 그 해 기준 실행")
    total: str | None = Field(description="processed 시트 줄 co2e 합(제외된 줄 뺌 · tCO2-eq 글자). 수가 없으면 null")
    sheets: int = Field(description="processed 시트 수")
    failedSheets: int = Field(description="failed 시트 수")


class Scope3YearLockedByOut(Schema):
    id: str
    name: str = Field(description="잠근 사람의 지금 이름(못 찾으면 빈 글자)")


class Scope3YearCategoryOut(Schema):
    category: str = Field(description="「C1」~「C15」(C10 뺌)")
    current: Scope3YearCurrentOut | None = Field(description="그 해 기준 실행이 없고 안 잠겼으면 null")
    locked: bool
    lockedAt: KstDateTime | None
    lockedBy: Scope3YearLockedByOut | None
    editedRows: int = Field(
        description="지금 결과 실행에서 제외됐거나 계수가 AI 원안과 다른 줄 수 — 한 줄이 둘 다여도 1(MARC-ENT-570)"
    )


class Scope3YearOut(Schema):
    year: int
    baseRunId: str | None = Field(
        description="그 해 기준 실행 — 만든 차례 마지막 「실행 done + 결과 done」(없으면 null). 안 잠긴 카테고리의 것"
    )
    latest: Scope3YearLatestOut | None = Field(
        description="그 해 가장 새 실행(실패·진행 중·결과 rejected 도). 없으면 null"
    )
    categories: list[Scope3YearCategoryOut] = Field(description="열넷 — C 번호 차례")
    editedRowsUnlocked: int = Field(
        description="잠기지 않은 카테고리의 editedRows 합 — 다시 올리면 사라지는 고친 행 수(MARC-ENT-570 경고)"
    )
