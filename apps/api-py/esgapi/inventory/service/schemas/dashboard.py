"""Scope 1·2 대시보드(S1) 경로의 응답 꼴(JSON). 밴드 S12a-3 ②(결정 MARC-ENT-469 1·7). 여기 적힌 것이 OpenAPI 문서와
프론트의 타입(generated/api.d.ts)이 된다.

필드 이름은 camelCase, **응답 id 는 숫자 id 의 십진 글자**, **Decimal 은 글자**(지수 표기 0·끝 0 걷음). 배출량은 늘
tCO2-eq(`unit`), 위치기반(`basis`). 빈 칸은 null 로 싣는다(exclude_unset 0).
시장기반 칸은 꼴만 지금 세운다 — 1차에는 늘 null(화면 「-」). Scope 3 합·카테고리 상위 5 는 S3K2a ② 가 채운다(연도
상태와 같은 재료 — Scope 1·2 설정과 따로). 사업장별 Scope 3 은 1차 늘 null. 타입은 S12a-3 의 꼴 그대로(지운 줄 0).
이름은 Scope12Dashboard 를 앞에 붙인다(OpenAPI 컴포넌트 이름이 Entry*·Ghg*·Scope3Colab*·결과 꼴과 겹치지 않게).
"""

from typing import Literal

from ninja import Schema
from pydantic import Field

from esgapi.inventory.service.schemas.entries import EMISSION_UNIT

SCOPE3_LATER = "1차 늘 null — Scope 3 템플릿의 사업장 칸은 등록 사업장과 안 이어진다(화면 「-」)"


class Scope12DashboardSourceOut(Schema):
    nodeId: str = Field(description="배출원 유형(풀 2단) 노드 id")
    name: str
    value: str = Field(description="그 유형 아래 행 배출량 합(켠 사업장, tCO2-eq 글자)")
    share: str | None = Field(
        description="그 Scope(뿌리) 합 대비 퍼센트 글자(0~100, 소수 첫째 자리 반올림 — 예 「12.5」). 분모 0 이면 null"
    )


class Scope12DashboardScopeOut(Schema):
    scopeId: str = Field(description="뿌리 노드 id(리스트 inventory_scope12_rows 의 scopeId 와 같음)")
    scopeName: str
    scopeOrder: int = Field(
        description="그 뿌리가 풀 뿌리 전체 가운데 몇째인지(1부터, 풀 트리 차례 — 숨김·선택과 무관). "
        "scopes 는 선택 잎이 있는 뿌리만 실으니 화면은 Scope 1·2 자리를 목록 차례가 아니라 이것으로 잡는다"
    )
    value: str | None = Field(description="그 해 켠 사업장 합(리스트의 그 해 값과 같음). 값 있는 행 0 이면 null")
    topSources: list[Scope12DashboardSourceOut] = Field(
        description="배출원 유형 상위 5 — 큰 차례, 같은 값은 풀 차례. 값 없는 유형은 빠지고 0 은 든다"
    )


class Scope12DashboardTotalOut(Schema):
    scope12: str | None = Field(description="Scope 1·2 합(뿌리 합들의 합). 값 0 이면 null")
    scope2Market: str | None = Field(description="1차 늘 null — 시장기반 2차(MARC-ENT-469 7)")
    scope3: str | None = Field(
        description="Scope 3 카테고리 지금 결과(잠겼으면 핀 실행, 아니면 그 해 기준 실행)의 합. 셈한 것 0 이면 null"
    )
    sum: str | None = Field(description="Scope 1·2 합 + Scope 3 합 — null 인 쪽은 빼고, 둘 다 null 이면 null")
    scope3FailedSheets: int = Field(
        description="Scope 3 카테고리 지금 결과들의 failed 시트 수 합"
        "(연도 상태 categories[].current.failedSheets 의 합). 결과 없으면 0"
    )


class Scope12DashboardSiteScopeOut(Schema):
    scopeId: str
    value: str | None = Field(description="그 사업장의 그 Scope 합. 값 있는 행 0 이면 null")


class Scope12DashboardSiteOut(Schema):
    siteId: str
    siteName: str
    scopes: list[Scope12DashboardSiteScopeOut] = Field(description="scopes 와 같은 차례·같은 수")
    scope3: str | None = Field(description=SCOPE3_LATER)


class Scope12DashboardCategoryOut(Schema):
    category: str = Field(description="「C1」~「C15」(C10 뺌)")
    name: str = Field(description="카테고리 이름(화면 글자와 같은 서버 상수)")
    value: str = Field(description="그 카테고리 지금 결과 합(tCO2-eq 글자)")
    share: str | None = Field(description="Scope 3 합 대비 퍼센트 글자(소수 첫째 자리 반올림). 분모 0 이면 null")


class Scope12DashboardOut(Schema):
    year: int
    configured: bool = Field(
        description="거짓이면 scopes 빈 목록, Scope 1·2 합 null(빈 상태 — 오류 아님) — Scope 3 은 따로"
    )
    decimals: int = Field(description="표시 자릿수(값 글자는 반올림하지 않음)")
    basis: Literal["location"] = "location"
    unit: Literal["tCO2-eq"] = EMISSION_UNIT
    complete: bool = Field(
        description="Scope 1·2 만 — 셈에 든 행 가운데 배출량 셈 문제(emissionProblem)가 있는 행이 없음"
    )
    scopes: list[Scope12DashboardScopeOut] = Field(description="뿌리 노드(Scope)마다 — 풀 차례")
    total: Scope12DashboardTotalOut
    bySite: list[Scope12DashboardSiteOut] = Field(description="인벤토리를 켠 사업장 전부(값 없는 곳은 null)")
    scope3Categories: list[Scope12DashboardCategoryOut] = Field(
        description="Scope 3 카테고리 상위 5 — 값 있는 카테고리만(0·음수 듦), 큰 차례·같으면 C 번호"
    )
