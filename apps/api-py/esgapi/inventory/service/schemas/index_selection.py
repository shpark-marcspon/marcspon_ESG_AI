"""고객사 인덱스 선택(S17) 경로의 요청·응답 꼴(JSON). 밴드 K1b-2b ③. 여기 적힌 것이 OpenAPI 문서와 프론트의
타입(generated/api.d.ts)이 된다.

필드 이름은 camelCase, **응답 id 는 숫자 id 의 십진 글자·요청 id 는 정수**(sid:MARC-ISSUE-92). 본문은 StrictIn —
모르는 칸(companyId 포함)은 422. 회사는 본문이 아니라 인증 주체에서만 정한다(core/auth/bearer.py 의 company_of).
`facilityNodeIds` 는 **공통 풀의 잎 id** 다(회사 행이 아니다 — 결정 MARC-ENT-469 3).
이름은 IndexSelection·IndexTree 를 앞에 붙인다(OpenAPI 컴포넌트 이름이 다른 모듈과 겹치지 않게).
"""

from typing import Annotated

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import StrictIn
from esgapi.inventory.service.utils.index_selection import MAX_SELECTIONS

NodeId = Annotated[int, Field(ge=1)]


class IndexTreeNodeOut(Schema):
    id: str
    level: str = Field(description="scope · source_type · activity · facility(관리자 경로의 단 글자 그대로)")
    name: str = Field(description="잎은 시설 코드 이름")
    parentId: str | None
    facilityCodeId: str | None = Field(default=None, description="잎만")
    availableCount: int = Field(description="이 회사의 인벤토리 켠 사업장의 그 코드 자산/시설 수(위 단은 아래 합)")
    selected: bool = Field(description="잎은 숨기지 않은 선택이 있음, 위 단은 아래 고를 수 있는 잎이 다 골라짐")
    hasFactor: bool | None = Field(default=None, description="잎만 — 기본 배출계수가 있다(없으면 고를 수 없다)")
    hasData: bool | None = Field(default=None, description="잎만 — 이 해에 입력값이 있다(지금은 늘 거짓 — S12a)")


class IndexTreeOut(Schema):
    year: int
    nodes: list[IndexTreeNodeOut]


class IndexSelectionSaveIn(StrictIn):
    facilityNodeIds: Annotated[list[NodeId], Field(max_length=MAX_SELECTIONS)] = Field(
        description="고를 잎(공통 풀 id) 전부 — 빠진 잎은 뺀다(데이터 있으면 숨김)"
    )


class IndexSelectionSaveOut(Schema):
    selected: int = Field(description="저장 뒤 숨기지 않은 선택 수")
    hiddenWithData: int = Field(description="뺐지만 데이터가 있어 숨긴 수")
