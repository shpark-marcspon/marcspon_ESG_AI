"""/branches 와 자산/시설 코드 목록 경로의 요청·응답 꼴(JSON). 밴드 K1b-1. 여기 적힌 것이 OpenAPI 문서와 프론트의 타입
(generated/api.d.ts)이 된다.

필드 이름은 camelCase, 시각은 +09:00(KstDateTime), id 는 숫자 id 의 십진 글자(옛 SiteOut.id 꼴). 본문은 StrictIn —
모르는 칸(companyId·tenantId 포함)은 422, 타입을 바꿔 받지 않는다(true 는 1 이 아니다). 이름·세부시설명은 앞뒤 공백을
걷어 받고, 걷은 뒤 빈 글자면 422.
사업장 상세는 그 판의 버전(updatedAt)을 내고, 저장(PUT)은 본문 updatedAt 으로 그 판을 돌려받는다 — 잠근 행과
다르면 409 stale(밴드 K1b-3 · sid:MARC-ISSUE-427). 요청 칸은 글자다(StrictIn 이 글자 → datetime 을 거절한다) —
시간대가 있는 ISO 만.
"""

from datetime import datetime
from typing import Annotated

from ninja import Schema
from pydantic import AfterValidator, Field

from esgapi.core.schemas import KstDateTime, PageNumberPage, StrictIn

IDS_MAX = 100  # 일괄 요청 하나의 id 상한(한 쪽 pageSize 상한과 같다)
FACILITIES_MAX = 200  # 사업장 하나의 자산/시설 줄 상한(한 요청)


def _stripped(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("빈 글자는 받지 않는다(앞뒤 공백을 걷은 뒤)")
    return value


BranchName = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_stripped)]
DetailName = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_stripped)]
CodeName = Annotated[str, Field(min_length=1, max_length=100), AfterValidator(_stripped)]


def parse_seen_at(text: str) -> datetime:
    """본문 updatedAt(ISO 8601, 시간대 있음) → aware datetime. 꼴이 틀리거나 시간대가 없으면 ValueError."""
    value = datetime.fromisoformat(text)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("시간대가 있는 ISO 8601 시각만 받는다")
    return value


def _aware_iso(value: str) -> str:
    parse_seen_at(value)  # 보기만 한다 — 칸은 글자 그대로(apis 가 같은 함수로 datetime 을 만든다)
    return value


SeenAt = Annotated[
    str,
    Field(min_length=1, max_length=40, description="상세(GET·PUT 응답)의 updatedAt 을 그대로 — 다르면 409 stale"),
    AfterValidator(_aware_iso),
]
RowId = Annotated[int, Field(ge=1)]
Ids = Annotated[list[RowId], Field(min_length=1, max_length=IDS_MAX)]


class BranchOut(Schema):
    id: str
    name: str
    isHeadquarters: bool
    inventoryEnabled: bool
    externalId: str | None
    createdAt: KstDateTime


class BranchFacilityOut(Schema):
    id: str
    facilityCodeId: str
    facilityCode: str = Field(description="코드 글자(F0001 꼴). 코드가 지워졌어도 그대로 보인다")
    facilityName: str
    detailName: str


class BranchDetailOut(BranchOut):
    facilities: list[BranchFacilityOut]
    updatedAt: KstDateTime = Field(description="이 판의 버전 — 저장(PUT) 본문 updatedAt 에 그대로 돌려준다")


class BranchPageOut(PageNumberPage[BranchOut]):
    pass


class BranchFacilityIn(StrictIn):
    id: RowId | None = Field(
        default=None,
        description="PUT 에서만: 있으면 그 줄을 고친다, 없으면 새로(빠진 기존 줄은 삭제 표시). POST 에 있으면 404",
    )
    facilityCodeId: RowId
    detailName: DetailName


class BranchCreateIn(StrictIn):
    name: BranchName
    inventoryEnabled: bool = True
    facilities: Annotated[list[BranchFacilityIn], Field(default_factory=list, max_length=FACILITIES_MAX)]


class BranchSaveIn(StrictIn):
    name: BranchName
    inventoryEnabled: bool
    facilities: Annotated[list[BranchFacilityIn], Field(max_length=FACILITIES_MAX)]
    updatedAt: SeenAt


class BranchInventoryIn(StrictIn):
    ids: Ids
    enabled: bool


class BranchIdsIn(StrictIn):
    ids: Ids


class CountOut(Schema):
    count: int = Field(description="바뀐 행 수")


class FacilityCodeOut(Schema):
    id: str
    code: str
    name: str


class FacilityCodesOut(Schema):
    items: list[FacilityCodeOut]


class AdminFacilityCodeOut(FacilityCodeOut):
    inUse: bool


class AdminFacilityCodePageOut(PageNumberPage[AdminFacilityCodeOut]):
    pass


class FacilityCodeNameIn(StrictIn):
    name: CodeName
