"""온실가스 인덱스 풀·시설별 배출계수 풀 경로의 요청·응답 꼴(JSON). 밴드 K1b-2a ③. 여기 적힌 것이 OpenAPI 문서와
프론트의 타입(generated/api.d.ts)이 된다.

필드 이름은 camelCase, 시각은 +09:00(KstDateTime), **응답 id 는 숫자 id 의 십진 글자·요청 id 는 정수**
(sid:MARC-ISSUE-92).
**Decimal 은 글자로 주고받는다**(예 「1234.5」 — 지수 표기 0·끝 0 걷음, 요청이 숫자 꼴이 아니면 422 — utils 의
parse_decimal). 본문은 StrictIn — 모르는 칸(companyId·tenantId 포함)은 422, 타입을 바꿔 받지 않는다.
칸별 검사(S20 「확인」)는 utils 의 check_factor·check_facility 가 하고 경로가 422 fields.<칸> 으로 낸다.
이름은 Ghg 를 앞에 붙인다(OpenAPI 컴포넌트 이름이 다른 모듈과 겹치지 않게).
"""

from typing import Annotated

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import KstDateTime, StrictIn

IDS_MAX = 100  # 일괄 요청 하나의 id 상한(organization 의 IDS_MAX 와 같다)
RowId = Annotated[int, Field(ge=1)]
Ids = Annotated[list[RowId], Field(min_length=1, max_length=IDS_MAX)]
Text100 = Annotated[str, Field(max_length=100)]
Text200 = Annotated[str, Field(max_length=200)]
Text1000 = Annotated[str, Field(max_length=1000)]
Short = Annotated[str, Field(max_length=40)]
NumberText = Annotated[str, Field(max_length=40, description="숫자 글자(정수 18자리·소수 12자리까지, 지수·부호 없음)")]


class GhgUnitIn(StrictIn):
    kind: Short
    unit: Short


class GhgUnitOut(Schema):
    kind: str
    unit: str


# ── 노드 ─────────────────────────────────────────────────────────────


class GhgNodeOut(Schema):
    id: str
    level: str = Field(description="scope · source_type · activity · facility")
    name: str = Field(description="잎은 시설 코드 이름")
    parentId: str | None
    sortOrder: int
    childCount: int
    facilityCodeId: str | None = None
    facilityCode: str | None = Field(default=None, description="잎만 — 코드 글자(F0001 꼴)")


class GhgNodesOut(Schema):
    items: list[GhgNodeOut]


class GhgNodeCreateIn(StrictIn):
    level: Short = Field(description="scope · source_type · activity(열 1~3 — 잎은 facilities)")
    parentId: RowId | None = None
    name: Text100


class GhgNodeRenameIn(StrictIn):
    name: Text100


class GhgIdsIn(StrictIn):
    ids: Ids


class GhgCountOut(Schema):
    count: int


# ── 잎(자산/시설) ────────────────────────────────────────────────────


class GhgFactorSummaryOut(Schema):
    id: str
    name: str
    inputUnit: GhgUnitOut
    isDefault: bool
    sortOrder: int
    version: int


class GhgFacilityOut(Schema):
    id: str
    parentId: str
    facilityCodeId: str
    facilityCode: str
    facilityName: str
    unit: GhgUnitOut
    tooltip: str
    factors: list[GhgFactorSummaryOut]


class GhgFacilityCreateIn(StrictIn):
    parentId: RowId
    facilityCodeId: RowId
    unit: GhgUnitIn
    tooltip: Text1000 = ""


class GhgFacilitySaveIn(StrictIn):
    facilityCodeId: RowId
    unit: GhgUnitIn
    tooltip: Text1000 = ""
    defaultFactorId: RowId | None = None


# ── 계수 ─────────────────────────────────────────────────────────────


class GhgGasIn(StrictIn):
    gas: Short
    enabled: bool
    factor: NumberText | None = None
    gwp: NumberText | None = None


class GhgGasOut(Schema):
    gas: str
    enabled: bool
    factor: str | None
    gwp: str | None


class GhgFactorIn(StrictIn):
    """계수 한 건(만들기·고치기 같은 꼴). id·version·seed*·시각 칸이 없다. 빠진 가스는 끈 줄로 채운다."""

    name: Text200
    source: Text200
    baseYear: int | None = None
    tier: int | None = None
    countryCode: Short
    industryCode: Short
    inputUnit: GhgUnitIn
    emissionUnit: GhgUnitIn | None = Field(default=None, description="없으면 질량 / tCO2-eq")
    ncvEnabled: bool = False
    ncv: NumberText | None = None
    ncvUnit: GhgUnitIn | None = None
    factorUnit: Short | None = Field(default=None, description="없으면 기본값(순발열량 켬 kg/TJ, 끔 kg/<투입 단위>)")
    gases: Annotated[list[GhgGasIn], Field(max_length=7)]
    note: Text1000 = ""


class GhgFactorOut(Schema):
    id: str
    facilityNodeId: str
    version: int
    versions: list[int]
    isDefault: bool
    sortOrder: int
    name: str
    source: str
    baseYear: int
    tier: int
    countryCode: str
    industryCode: str
    inputUnit: GhgUnitOut
    emissionUnit: GhgUnitOut
    ncvEnabled: bool
    ncv: str | None
    ncvUnit: GhgUnitOut | None
    factorUnit: str
    gases: list[GhgGasOut] = Field(description="늘 일곱 줄 — CO2·CH4·N2O·HFCs·PFCs·SF6·NF3")
    note: str
    seedRecordIds: list[str]
    seedGwpSetId: str | None
    createdAt: KstDateTime = Field(description="계수(정체)를 만든 때")
    updatedAt: KstDateTime = Field(description="이 판을 만든 때")


# ── 선택 목록 ────────────────────────────────────────────────────────


class GhgUnitKindOut(Schema):
    kind: str
    units: list[str]


class GhgCodeNameOut(Schema):
    code: str
    name: str


class GhgDefaultsOut(Schema):
    emissionUnit: GhgUnitOut
    factorUnitWithNcv: str
    factorUnitWithoutNcv: str


class GhgOptionsOut(Schema):
    gases: list[str]
    units: list[GhgUnitKindOut]
    countries: list[GhgCodeNameOut]
    industries: list[GhgCodeNameOut]
    defaults: GhgDefaultsOut
