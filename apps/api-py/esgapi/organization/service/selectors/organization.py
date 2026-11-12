"""읽기. Django ORM 을 쓰고, 결과는 service/utils/entities.py 의 것으로 바꿔 내보낸다. 쓰지 않는다.

★ 조회마다 회사 조건을 적는다(sites 는 `Site.for_company(company_id)`). sites 의 기본 매니저는 회사를 정하지 않은
  조회를 거절한다(core/isolation). 무효 조건: 조건의 입력은 세션의 회사다. 그 값이 틀리면 그 틀린 회사로 가른다.
★ 회사를 서브도메인으로 찾는 길은 이 파일의 find_company 하나다(Company.by_subdomain 을 부르는 유일한 자리 —
  core/tests/isolation/test_static_rules.py). 교환(user 의 apis 가 포트로 꽂는다)과 seed_company 가 이것을 쓴다.
★ 운영 관리자의 회사 고르기 둘(K2c): find_company_by_id(Company.for_company) · find_sole_company(Company.sole_candidates
  를 부르는 유일한 자리). user 의 apis(users.py)가 포트로 꽂는다. find_sole_company 는 서브도메인 없는 로그인(user 의
  apis/user.py — UA1, MARC-ENT-283)도 꽂는다.
"""

from collections.abc import Callable
from dataclasses import dataclass

from esgapi.core.auth.principal import Principal
from esgapi.organization.models import Company, Site
from esgapi.organization.service.permissions.organization import Forbidden, can_view_sites
from esgapi.organization.service.selectors import branches
from esgapi.organization.service.utils.entities import (
    CompanyActive,
    CompanyInactive,
    CompanyInfo,
    CompanyLookup,
    CompanyUnknown,
)
from esgapi.organization.service.utils.entities import Site as SiteInfo


def company_of(row: Company) -> CompanyInfo:
    return CompanyInfo(
        id=row.pk,
        name=row.name,
        subdomain=row.subdomain,
        business_licence_number=row.business_licence_number,
        is_active=row.is_active,
    )


def find_company(subdomain: str) -> CompanyLookup:
    """그 서브도메인의 회사. 없으면 미등록, 있어도 쓸 수 없으면 비활성 갈래."""
    row = Company.by_subdomain(subdomain)
    if row is None:
        return CompanyUnknown()
    company = company_of(row)
    return CompanyActive(company) if company.is_active else CompanyInactive(company)


# ── 운영 관리자의 회사 고르기(K2c — 사용자 관리 경로의 companyId) ─────────────────
# user 의 apis 가 포트로 꽂는다(user 의 service 는 organization 을 import 하지 못한다 — 계약 바).
# 회사 행 자체를 밖으로 내지 않는다: 칸 셋(id·subdomain·is_active)만.


@dataclass(frozen=True)
class CompanyRef:
    id: int
    subdomain: str
    is_active: bool


@dataclass(frozen=True)
class SoleCompany:
    company: CompanyRef


@dataclass(frozen=True)
class NoCompany:
    pass


@dataclass(frozen=True)
class ManyCompanies:
    pass


def company_ref(row: Company) -> CompanyRef:
    return CompanyRef(id=row.pk, subdomain=row.subdomain, is_active=row.is_active)


def _company_row(company_id: int) -> Company | None:
    return Company.for_company(company_id).first()


def find_company_by_id(company_id: int) -> CompanyRef | None:
    """그 id 의 회사(활성이든 아니든). 없으면 None."""
    row = _company_row(company_id)
    return None if row is None else company_ref(row)


def company_name(company_id: int) -> str:
    """그 id 의 회사 이름(점검 목록의 companyName — 밴드 OP1 Q7). 없으면 ""."""
    row = _company_row(company_id)
    return "" if row is None else row.name


def find_sole_company() -> SoleCompany | NoCompany | ManyCompanies:
    """회사가 정확히 하나면 그 회사(비활성도 든다 — 시드 회사의 기본. 서브도메인 없는 로그인은 부르는 쪽이 비활성을
    뺀다). 0 이면 NoCompany, 둘 이상이면 ManyCompanies.
    회사 표의 앞 두 행까지만 읽는다(Company.sole_candidates 를 부르는 유일한 자리 — test_static_rules)."""
    rows = Company.sole_candidates()
    if not rows:
        return NoCompany()
    if len(rows) > 1:
        return ManyCompanies()
    return SoleCompany(company_ref(rows[0]))


# ── 사업장 ────────────────────────────────────────────────────────────


def site_of(row: Site) -> SiteInfo:
    return SiteInfo(id=str(row.pk), company_id=row.company_id, external_id=row.external_id, name=row.name)


def all_sites(company_id: int) -> list[SiteInfo]:
    """그 회사의 사업장 전부(삭제 표시된 것은 빼고 — K1b-1), 만든 차례로. /branches 와 같은 안쪽 함수
    (branches.search_sites)를 부른다(감독 판단 1·N3)."""
    page = branches.search_sites(company_id, order="created")
    return [
        SiteInfo(id=str(branch.id), company_id=branch.company_id, external_id=branch.external_id, name=branch.name)
        for branch in page.branches
    ]


@dataclass(frozen=True)
class SiteList:
    sites: list[SiteInfo]


def list_sites(principal: Principal, *, all_sites: Callable[[int], list[SiteInfo]] = all_sites) -> SiteList | Forbidden:
    """사업장 보기. 권한은 여기서 본다. 회사는 주체의 것을 조회에 넘긴다
    (옛 교환 쿠키는 경로의 principal_of 가 principal_of_session 을 거쳐 넘긴다)."""
    # 경로의 첫 문장 permitted(core/auth/bearer.py)를 이 동작에서는 여기서 대신한다: 같은 표(is_allowed)를 읽는다.
    # company_id is None 은 permitted 에 없는 겹 확인이다 — 회사 없는 주체를 막는 깊은 방어라 남긴다
    # (밴드 CU1, 감독 처분 ②).
    if not can_view_sites(principal.kind) or principal.company_id is None:  # 회사 없는 주체는 고객사 사용자가 아니다
        return Forbidden("accounts_sites_list")
    return SiteList(all_sites(principal.company_id))
