"""Scope 1·2 입력(S2 리스트·S3 상세·S12 히스토리) 경로의 요청·응답 꼴(JSON). 밴드 S12a ③. 여기 적힌 것이 OpenAPI
문서와 프론트의 타입(generated/api.d.ts)이 된다.

필드 이름은 camelCase, 시각은 +09:00(KstDateTime), **응답 id 는 숫자 id 의 십진 글자·요청 id 는 정수**
(sid:MARC-ISSUE-92). **Decimal 은 글자로 주고받는다**(지수 표기 0·끝 0 걷음 — 금액은 0 이상·소수 6자리·정수 18자리,
꼴이 틀리면 422 fields.rows.<i>.values.<j>.amount). 본문은 StrictIn — 모르는 칸(companyId 포함)은 422.
회사는 본문이 아니라 인증 주체에서만 정한다(core/auth/bearer.py 의 company_of). **판 칸이 없다** — 셈은 그 회사
선택 행이 잡은 판으로만 한다(418 노트 L3). S12a-2: 행 계수 바꿈은 **계수 id**(factorId — 그 계수의 지금 판을 서버가
잡음) 또는 직접입력(custom)을 받고, 판 id 는 여전히 받지 않는다.
연도별 값(`values`)은 열쇠가 해의 십진 글자(「2025」)인 객체 — Y-2·Y-1·Y 셋, 행이 없거나 다 N/A·빈 칸이면 null.
배출량은 늘 tCO2-eq(`unit`). 이름은 Entry 를 앞에 붙인다(OpenAPI 컴포넌트 이름이 다른 모듈과 겹치지 않게).
"""

from typing import Annotated, Literal

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import KstDateTime, PageNumberPage, StrictIn
from esgapi.inventory.service.schemas.ghg_pool import GhgFactorIn, GhgGasOut, GhgUnitOut
from esgapi.inventory.service.utils.entries import MEMO_MAX, REASON_MAX

IDS_MAX = 100  # 일괄 지움 하나의 id 상한(organization·풀의 IDS_MAX 와 같다)
# 저장 한 번의 행 수는 actions 가 센다(MAX_ROWS_PER_SAVE — 넘으면 422 fields.rows). 여기 max_length 는 끝없는 본문만
# 막는 겉 울타리다(그 위는 ninja 의 422 꼴).
ROWS_FENCE = 1000
VALUES_FENCE = 12  # 한 행의 칸 상한(입력주기 S7 — 월 12 · 분기 4 · 연 1, 가장 많은 월)
RowId = Annotated[int, Field(ge=1)]
Ids = Annotated[list[RowId], Field(min_length=1, max_length=IDS_MAX)]
# S12a-2: 칸은 블록 입력주기의 것 — 월 YYYY-MM · 분기 YYYY-Qn · 연 YYYY(밖이면 422). S12a-3: 설명 글자도 고침(488-2).
Slot = Annotated[str, Field(max_length=7, description="블록 입력주기의 칸 — 월 YYYY-MM · 분기 YYYY-Qn · 연 YYYY")]
AmountText = Annotated[str, Field(max_length=40, description="0 이상 숫자 글자(소수 6자리·정수 18자리, 지수 없음)")]
YearValues = dict[str, str | None]
EMISSION_UNIT: Literal["tCO2-eq"] = "tCO2-eq"


# ── ⓗ 해 · ⓘ 리스트 ───────────────────────────────────────────────


class EntryYearOut(Schema):
    year: int
    configured: bool = Field(description="숨기지 않은 인덱스 선택이 있다")


class EntryYearsOut(Schema):
    years: list[EntryYearOut] = Field(description="새 해 먼저")


class EntryListRowOut(Schema):
    nodeId: str = Field(description="공통 풀의 잎 id(상세 경로의 node_id)")
    path: list[str] = Field(description="Scope → 배출원 유형 → 배출활동 → 자산/시설 이름")
    values: YearValues = Field(description="Y-2·Y-1·Y 의 배출량(켠 사업장 합, tCO2-eq 글자 | null)")
    hasMemo: bool
    estimated: bool = Field(description="그 해 월 값 하나라도 추정")
    locked: bool


class EntryScopeOut(Schema):
    scopeId: str = Field(description="뿌리 노드 id")
    scopeName: str
    values: YearValues
    rows: list[EntryListRowOut]


class EntryRowsOut(Schema):
    year: int
    years: list[int] = Field(description="Y-2·Y-1·Y")
    configured: bool = Field(description="거짓이면 scopes 가 빈 목록(빈 상태 — 오류 아님)")
    decimals: int = Field(description="표시 자릿수(저장값은 그대로)")
    unit: Literal["tCO2-eq"] = EMISSION_UNIT
    scopes: list[EntryScopeOut]


# ── ⓐ 상세 ────────────────────────────────────────────────────────


class EntryFactorOut(Schema):
    versionId: str = Field(description="선택이 잡은 판 id — 셈은 이 판으로만")
    factorId: str
    name: str
    source: str
    version: int
    inputUnit: GhgUnitOut
    ncvEnabled: bool
    ncv: str | None
    ncvUnit: GhgUnitOut | None
    factorUnit: str
    gases: list[GhgGasOut] = Field(description="늘 일곱 줄 — CO2·CH4·N2O·HFCs·PFCs·SF6·NF3")
    isCustom: bool = Field(
        description="늘 거짓(풀 계수의 판) — 직접입력 계수는 EntryCustomFactorOut(isCustom 참)"
    )  # S12a-3: 설명 고침(488-2)


class EntryCustomFactorOut(Schema):
    """행 전용 직접입력 계수(S9·S11 — 고치지 않는다, 바꾸면 새 계수)."""

    customId: str
    name: str
    source: str
    baseYear: int
    tier: int
    countryCode: str
    industryCode: str
    inputUnit: GhgUnitOut
    ncvEnabled: bool
    ncv: str | None
    ncvUnit: GhgUnitOut | None
    factorUnit: str
    gases: list[GhgGasOut] = Field(description="늘 일곱 줄 — CO2·CH4·N2O·HFCs·PFCs·SF6·NF3")
    note: str
    isCustom: bool = Field(description="늘 참")


class EntrySiteTotalOut(Schema):
    siteId: str
    siteName: str
    values: YearValues


class EntryTotalsOut(Schema):
    years: list[int]
    all: YearValues
    bySite: list[EntrySiteTotalOut]


class EntryFacilityOut(Schema):
    id: str = Field(description="사업장 자산/시설 id(저장 본문의 siteFacilityId)")
    detailName: str
    hasRow: bool = Field(description="이미 입력 행이 있다(새 행은 rowId 없이 — 있으면 rowId 로 고친다)")


class EntrySlotOut(Schema):
    slot: str
    amount: str | None
    estimated: bool


class EntryRowOut(Schema):
    rowId: str
    siteFacilityId: str
    detailName: str
    unit: str
    na: bool
    values: list[EntrySlotOut] = Field(description="저장된 칸만(빈 칸은 없거나 amount null)")
    emission: str | None = Field(description="tCO2-eq 글자. N/A·빈 행·셈 못 함이면 null")
    emissionProblem: str | None = Field(
        description="셈 못 함의 까닭(unit_conversion_missing · factor_unit_invalid · emission_out_of_range)"
    )
    factor: EntryFactorOut | EntryCustomFactorOut | None = Field(
        description="행의 계수 덮어쓰기 — null 이면 선택의 factor. 셈 차례: 직접입력 > 행 판 > 선택 판"
    )


class EntrySiteOut(Schema):
    siteId: str
    siteName: str
    facilities: list[EntryFacilityOut] = Field(description="그 잎 코드의 자산/시설(삭제 안 된 것)")
    rows: list[EntryRowOut]
    period: str = Field(description="블록 입력주기 month · quarter · year(S7 — 저장 안 했으면 month)")
    slots: list[str] = Field(description="그 주기의 칸(행 values 는 이 칸만 — 옛 주기 칸 값은 숨김)")


class EntryLockedByOut(Schema):
    id: str
    name: str


class EntryIndexOut(Schema):
    year: int
    nodeId: str
    name: str
    path: list[str]
    decimals: int
    memo: str
    locked: bool
    lockedAt: KstDateTime | None
    lockedBy: EntryLockedByOut | None
    unit: Literal["tCO2-eq"] = EMISSION_UNIT
    unitOptions: list[str] = Field(description="행 단위로 고를 수 있는 것(잎의 1차 단위 먼저)")
    factor: EntryFactorOut
    totals: EntryTotalsOut
    sites: list[EntrySiteOut] = Field(description="켠 사업장 중 그 잎 코드 자산/시설이 있는 것")


# ── ⓙ 히스토리 ─────────────────────────────────────────────────────


class EntryHistoryActorOut(Schema):
    kind: str = Field(description="service(고객사 사용자) · admin(운영 관리자)")
    id: str | None
    name: str | None


class EntryFactorRefOut(Schema):
    versionId: str | None = Field(description="풀 계수 판 id(직접입력이면 null)")
    customId: str | None = Field(description="직접입력 계수 id(풀 판이면 null)")
    name: str
    isCustom: bool


class EntryHistoryOut(Schema):
    historyId: str
    at: KstDateTime
    kind: str = Field(description="value · na_on · na_off · unit · period · factor")  # S12a-3: 설명 고침(488-2)
    slot: str | None
    before: str | None
    after: str | None
    unit: str
    actor: EntryHistoryActorOut
    reason: str | None = Field(description="계수 바꿈·복구의 사유")
    restorable: bool = Field(
        description="복구할 수 있다(value·period·factor · 안 잠김 · 그 행의 맨 위 줄 아님 · 낡지 않음)"
    )
    beforeFactor: EntryFactorRefOut | None = Field(description="factor 줄의 앞 계수(다른 종류는 null)")
    afterFactor: EntryFactorRefOut | None = Field(description="factor 줄의 뒤 계수(다른 종류는 null)")


class EntryHistoryPageOut(PageNumberPage[EntryHistoryOut]):
    pass


# ── 요청 ──────────────────────────────────────────────────────────


class EntrySlotIn(StrictIn):
    slot: Slot
    amount: AmountText | None = Field(default=None, description="null = 빈 칸")
    estimated: bool = False


class EntryRowIn(StrictIn):
    rowId: RowId | None = Field(default=None, description="고칠 행 — 없으면 새 행(그 자산/시설에 행이 없어야 함)")
    siteFacilityId: RowId
    unit: Annotated[str, Field(max_length=20)]
    na: bool = False
    values: Annotated[list[EntrySlotIn], Field(max_length=VALUES_FENCE)] = Field(
        description="바꿀 칸만 — 빠진 칸은 그대로(빈 목록이면 값 0 바뀜)"
    )


class EntrySaveIn(StrictIn):
    rows: Annotated[list[EntryRowIn], Field(max_length=ROWS_FENCE)]


class EntryIdsIn(StrictIn):
    ids: Ids


class EntryMemoIn(StrictIn):
    memo: str = Field(description=f"{MEMO_MAX}자까지(넘으면 422 fields.memo — actions 가 센다)")


class EntryDecimalsIn(StrictIn):
    decimals: int


class EntryPeriodIn(StrictIn):
    period: Annotated[str, Field(max_length=8, description="month · quarter · year(밖이면 422 fields.period)")]


class EntryRowFactorIn(StrictIn):
    factorId: RowId | None = Field(default=None, description="같은 잎의 풀 계수 id — 서버가 그 지금 판을 잡는다")
    custom: GhgFactorIn | None = Field(default=None, description="행 전용 직접입력 계수(관리자 풀 계수 입력 꼴)")
    reason: str | None = Field(default=None, description=f"사유 1~{REASON_MAX}자(필수 — actions 가 센다)")


class EntryRestoreIn(StrictIn):
    reason: str | None = Field(default=None, description=f"사유 {REASON_MAX}자까지 — factor 줄 복구는 필수")


class EntryMemoOut(Schema):
    memo: str


class EntryDecimalsOut(Schema):
    decimals: int


class EntryCountOut(Schema):
    count: int


class EntryUploadOut(Schema):
    """일괄 올리기의 결과(S12b-2): 새 행 · 채운 칸 · 같은 값이라 둔 칸 · 올린 잎에서 셈하지 못한 행."""

    added: int
    filled: int
    unchanged: int
    unresolved: int
