"""inventory 경로 셋(POST /inventory/calc · /scope3/shortlist · /scope3/classify)의 요청 꼴과 경로 전용 응답 꼴(JSON).

여기 적힌 것과 contracts/shapes.py 의 결과 꼴이 OpenAPI 문서와 프론트의 타입(generated/api.d.ts)이 된다.

응답의 꼴은 이 파일에 다시 적지 않는다(밴드 RR1, sid:MARC-ENT-268). 결과 JSON 의 원천은 contracts/shapes.py 의
TypedDict 이고 경로는 그것을 그대로 쓴다 — Scope 1·2 의 응답은 shapes.Scope12Body, Scope 3 의 조각(분류·LLM 실패·
사용량·근거)은 이 파일의 경로 전용 꼴이 칸의 타입으로 쓴다. 그 TypedDict 의 이름이 OpenAPI components 의 이름이 된다
(이름을 바꾸면 generated/ 가 바뀐다). 이 파일에 남는 것은 요청 꼴 여덟(`*In`)과 결과 꼴에 없는 경로 전용 응답 꼴
여덟(Scope 3 의 추리기·분류의 맨 위와 후보)뿐이다. 응답 꼴의 쌍둥이 Schema 를 여기 다시 적게 되면 이 문장은 거짓이다.

필드 이름은 camelCase 다. 요청 꼴의 클래스 이름에 `Calc`·`Scope3` 을 붙인 까닭: OpenAPI 의 components 는 이름
하나의 자리를 모듈들이 같이 쓴다(겹친 이름은 ninja 가 조용히 덮어쓴다 — tests/test_route_shapes.py 가 겹침 0 을 잰다).

「없음」을 적는 법이 둘이다(응답 쪽은 contracts/shapes.py 에서는 NotRequired 와 `X | None`).
  - 선택 칸: 없으면 키를 뺀다. null 은 받지 않고(요청), 내보내지도 않는다(응답). 아래에서 `= absent()` 로 적은 칸이다.
  - 「없음」이 값인 칸: 늘 있고 null 일 수 있다. `X | None` 으로 적고 기본값을 두지 않은 칸이다.
"""

from typing import Annotated, Any, Literal

from ninja import Schema
from pydantic import Field, StringConstraints

from esgapi.core.calc.guards import IntOnly
from esgapi.core.schemas import NotBool, StrictIn
from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import ShortlistMethod
from esgapi.inventory.engines.scope3.llm_first_1.types import CandidateBasis, FallbackReason, LicenseStatus
from esgapi.inventory.engines.scope12.engine_1.aggregate import GroupKey
from esgapi.inventory.engines.scope12.engine_1.types import FacilityUse, SourceType


def _without_default(schema: dict[str, Any]) -> None:
    schema.pop("default", None)


def absent(description: str | None = None) -> Any:
    """선택 칸의 기본값. 키가 없으면 그 칸은 「주지 않은 것」으로 남고(model_fields_set 에 없다), null 은 타입이 막는다.

    OpenAPI 에는 「없어도 되는 칸」으로만 나간다(기본값 null 을 적지 않는다: 그 칸의 타입에 null 이 없다).
    """
    return Field(default=None, json_schema_extra=_without_default, description=description)


# ── 요청 ──────────────────────────────────────────────────────────────


# 요청의 바닥은 core 의 StrictIn 이다(모르는 칸 거절 + 타입을 바꿔 받지 않음).
# 파이썬에서는 True == 1 이라 Literal[1, 2, 3, 4] 가 true 를 등급 1 로 받는다(엄격 모드에서도). 먼저 거른다(NotBool).
TierIn = Annotated[shapes.Tier, NotBool, IntOnly]


class CalcTiersIn(StrictIn):
    calorific: TierIn
    co2: TierIn
    nonCo2: TierIn
    oxidation: TierIn | None = Field(description="산화계수의 산정등급. 식에 산화계수 항이 없으면 null")


class CalcRowIn(StrictIn):
    """활동 데이터 한 행. 수량은 십진 문자열이다(JSON 의 수로 보내지 않는다)."""

    id: str
    orgUnit: str
    period: str
    sourceType: SourceType
    amount: str = Field(description='사용량. 십진 문자열(예: "1234.5"), 음수·지수 표기 불가, 64자까지')
    unit: str
    fuel: str = absent()
    factorYear: int = absent()
    factorId: str = absent()
    sector: str = absent()
    parameterTiers: CalcTiersIn = absent()
    facilityUse: FacilityUse = absent()
    variant: str = absent()


class CalcIn(StrictIn):
    rows: list[CalcRowIn] = Field(description="활동 데이터. 1,000행까지(넘으면 413)")
    gwpSetId: str = Field(description="GWP 세트의 id. 기본값이 없다")
    # 느슨하게 받는다: 꼴은 표 검사(engines/scope12/engine_1/tables.py 의 validate_tables)가 보고,
    # 틀리면 invalid_tables 로 답한다.
    tables: dict[str, Any] = absent("기준정보 표({unitConversions, factors, gwpSets}). 안 주면 패키지에 실린 표를 쓴다")
    groupBy: list[GroupKey] = Field(default=["scope", "sourceType"], description="집계의 묶음 기준")


# ── Scope 3: 후보 추리기와 분류 ───────────────────────────────────────
# 키의 이름은 esg-lab 의 TS(`ts/scope3`)가 내던 camelCase 를 따른다. 저장하지 않는다.
# 「없음」을 적는 법은 위와 같다: 선택 칸은 키를 빼고(`absent()`), 「없음」이 값인 칸은 늘 있고 null 일 수 있다.

# 범주: AI 를 적용하는 여섯. 파이썬에서는 True == 1 이라 true 가 범주 1 로 통과하지 못하게 먼저 거른다.
Scope3CategoryIn = Annotated[Literal[1, 2, 4, 6, 7, 9], NotBool, IntOnly]
# 품목명의 길이 상한(어림이다. 실측한 값이 아니다).
Scope3ItemName = Annotated[str, StringConstraints(min_length=1, max_length=200)]
Scope3Text = Annotated[str, StringConstraints(max_length=200)]
# 바깥에서 온 수는 64자까지다(esgapi/core/calc/decimal.py 의 EXTERNAL_MAX_LENGTH). 꼴(십진)은 계산하는 자리에서 본다.
Scope3Number = Annotated[str, StringConstraints(max_length=64)]
# 영어 검색어: 8개까지, 각 1~60자(분류 응답의 스키마와 같다).
Scope3Keyword = Annotated[str, StringConstraints(min_length=1, max_length=60)]


class Scope3TransportIn(StrictIn):
    """운송 행의 부가 정보. 무게가 있으면 그 행의 활동량은 톤·km 로 본다(숫자를 읽지는 않는다)."""

    mode: Scope3Text
    origin: Scope3Text = absent()
    destination: Scope3Text = absent()
    weightKg: Scope3Number = absent()
    distanceKm: Scope3Number = absent()


class Scope3ShortlistRowIn(StrictIn):
    itemName: Scope3ItemName
    unit: Scope3Text = absent()
    transport: Scope3TransportIn = absent()


class Scope3ShortlistIn(StrictIn):
    row: Scope3ShortlistRowIn
    category: Scope3CategoryIn
    keywords: Annotated[list[Scope3Keyword], Field(max_length=8)] = absent("분류 단계가 낸 영어 검색어")
    basis: CandidateBasis = absent(
        "physical 은 활동(물량)·거리 기반, spend 는 지출 기반. 주지 않으면 단위가 맞는 활동·거리 기반 후보가 있을 때 "
        "그것을, 없으면 지출 기반을 쓴다"
    )
    method: ShortlistMethod = absent("추리는 방식. 기본 lexical-v2(낱말 단위 BM25)")
    bigrams: bool = absent("lexical-v2 에서 한글 두 글자 조각을 낱말로 더할지. 기본 true")
    size: Annotated[int, Field(ge=1, le=50)] = absent("추린 목록의 길이. 기본 25")
    license: Annotated[str, StringConstraints(min_length=1, max_length=40)] = absent(
        "후보로 받을 이용 조건 상태를 쉼표로(ok, unverified, disputed). 기본 ok,unverified. disputed 는 명시해야 나온다"
    )


class Scope3CandidateOut(Schema):
    """추린 후보 하나. 계수 값은 싣지 않는다. `path` 는 분류 경로가 있고 이름이 그 첫 마디로 시작하지 않을 때만 있다."""

    id: str
    name: str
    path: str = absent()
    per: str
    source: str
    region: str
    licenseStatus: LicenseStatus


class Scope3RejectedOut(Schema):
    id: str
    reason: Literal["invalid_value_raw"]


class Scope3CatalogOut(Schema):
    """후보 자격은 갖췄는데 `value_raw` 가 엄격 십진이 아니라 빠진 줄(앞 20건과 총수). 조용히 빼지 않는다."""

    rejected: list[Scope3RejectedOut]
    rejectedTotal: int


class Scope3ShortlistedOut(Schema):
    """추린 후보.

    ★ 동점은 「표 순서」로 가른다. 여기서 표 순서는 **계수 id 의 유니코드 코드 포인트 순**이다(기준정보의 표에는 적재
    순서가 없다). esg-lab 의 TS 는 파일의 줄 순서였으므로 동점인 후보의 차례가 그것과 다를 수 있다.
    """

    status: Literal["shortlisted"]
    basis: CandidateBasis
    fallbackReason: FallbackReason | None
    method: ShortlistMethod
    description: str
    total: int = Field(description="추리기 전 후보 수")
    shown: int
    lexicalMatches: int = Field(description="낱말이 한 군데라도 겹친 후보 수. 0 이면 목록은 표의 앞 순서일 뿐이다")
    candidates: list[Scope3CandidateOut]
    evidence: list[shapes.CandidateEvidenceJson] = Field(
        description="그 후보가 왜 그 자리에 왔는지. 낱말이 겹치지 않아 표 순서로 채워진 후보는 `lexical` 이 없다. "
        "경로는 rrfScore 를 내지 않는다(RRF 를 거친 흐름 결과에만)."
    )
    catalog: Scope3CatalogOut


class Scope3NoCandidatesOut(Schema):
    """조건에 맞는 후보가 없다. `physical` 은 활동·거리 기반 후보가 없던 까닭(지출 기반만 물었으면 null)."""

    status: Literal["no_candidates"]
    physical: FallbackReason | None
    catalog: Scope3CatalogOut


Scope3ShortlistOut = Annotated[Scope3ShortlistedOut | Scope3NoCandidatesOut, Field(discriminator="status")]


class Scope3RowIn(StrictIn):
    """구매·물류·출장·통근 내역의 한 행. 수량·금액은 십진 문자열이다. 분류에는 품목명·단위·통화·운송 수단만 쓰인다."""

    rowId: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    itemName: Scope3ItemName
    quantity: Scope3Number = absent()
    unit: Scope3Text = absent()
    amount: Scope3Number = absent()
    currency: Scope3Text = absent()
    date: Scope3Text = absent()
    orgUnit: Scope3Text = absent()
    transport: Scope3TransportIn = absent()


class Scope3ClassifyIn(StrictIn):
    rows: list[Scope3RowIn] = Field(description="한 번에 1,000행까지(넘으면 413 too_many_rows). 묶음은 20개까지")


class Scope3GroupClassifiedOut(Schema):
    key: str
    rowIds: list[str]
    status: Literal["classified"]
    classification: shapes.ClassificationJson


class Scope3GroupFailedOut(Schema):
    key: str
    rowIds: list[str]
    status: Literal["classification_failed"]
    llm: shapes.LlmFailureJson


class Scope3ClassifyOut(Schema):
    """묶음마다의 분류. ★ `synthetic` 은 늘 true 다: 지금 경로는 모의 공급사뿐이고 실제 모델의 판단이 아니다."""

    synthetic: Literal[True]
    route: Literal["mock"]
    groups: list[Annotated[Scope3GroupClassifiedOut | Scope3GroupFailedOut, Field(discriminator="status")]]
    usage: shapes.UsageJson
