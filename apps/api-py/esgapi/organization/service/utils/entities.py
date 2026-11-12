"""조직의 낱말: 회사, 사업장(옛 /sites 의 Site · /branches 의 Branch), 자산/시설 코드, 사업장별 자산/시설.
순수하다(표준 라이브러리만).

DB 의 표(models.Company)와 갈라 둔 까닭: selectors 가 행을 이것으로 바꿔 내보내고, 행은 selectors 밖으로 나가지 않는다.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CompanyInfo:
    """회사 하나. id 는 DB 의 숫자 id, subdomain 은 EDK 토큰의 tenant_id 주장과 같은 글자다."""

    id: int
    name: str
    subdomain: str
    business_licence_number: str
    is_active: bool


# ── 회사를 찾아본 결과 ─────────────────────────────────────────────────
# ★ 없음과 쓸 수 없음을 None 이나 bool 로 접지 않는다. 갈래마다 이름이 있다.


@dataclass(frozen=True)
class CompanyActive:
    company: CompanyInfo


@dataclass(frozen=True)
class CompanyInactive:
    """등록은 됐지만 쓸 수 없는 회사(is_active 거짓)."""

    company: CompanyInfo


@dataclass(frozen=True)
class CompanyUnknown:
    """등록되지 않은 서브도메인."""


CompanyLookup = CompanyActive | CompanyInactive | CompanyUnknown


@dataclass(frozen=True)
class Site:
    """사업장. id 는 숫자 id 의 십진 글자(응답의 꼴이 글자라서),
    external_id 는 EDK 가 준 사업장 ID 이고 우리 쪽에서 만든 사업장이면 None 이다.
    (여기의 None 은 「못 봤다」가 아니라 「EDK 쪽 ID 가 없는 사업장」 하나만 뜻한다.)
    """

    id: str
    company_id: int
    external_id: str | None
    name: str


# ── 사업장(Branch — 표 sites, K1b-1)·자산/시설 코드(공통)·사업장별 자산/시설 ─────────────


@dataclass(frozen=True)
class Branch:
    """사업장 하나(/branches 의 꼴). id 는 DB 의 숫자 id(응답에서는 십진 글자 — 옛 SiteOut.id 꼴)."""

    id: int
    company_id: int
    name: str
    is_headquarters: bool
    inventory_enabled: bool
    external_id: str | None
    created_at: datetime
    updated_at: datetime  # 판의 버전(K1b-3 — PUT 이 견준다)


@dataclass(frozen=True)
class BranchFacility:
    """사업장의 자산/시설 하나. 코드는 공통 목록의 행이다 — 그 코드가 지워져도(삭제 표시) 글자·이름이 그대로 보인다."""

    id: int
    facility_code_id: int
    facility_code: str
    facility_name: str
    detail_name: str


@dataclass(frozen=True)
class BranchDetail:
    branch: Branch
    facilities: list[BranchFacility]


@dataclass(frozen=True)
class BranchPage:
    count: int
    branches: list[Branch]


@dataclass(frozen=True)
class FacilityCodeInfo:
    """자산/시설 코드 하나(모든 고객사 공통). code 는 F0001 꼴 — 만든 뒤 바뀌지 않는다."""

    id: int
    code: str
    name: str
