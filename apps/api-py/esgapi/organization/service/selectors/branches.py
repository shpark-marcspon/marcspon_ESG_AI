"""사업장(Branch — 표 sites)과 사업장별 자산/시설의 읽기. 밴드 K1b-1. 쓰지 않는다.

★ 조회마다 회사 조건을 적는다(`Site.for_company(company_id)`·`SiteFacility.for_company(company_id)`). 회사 id 는 부르는
  쪽이 정한 것이다(고객사 사용자는 주체의 회사, 운영 관리자는 core/auth/bearer.py 의 company_of 가 고른 작업 회사). 무효
  조건: 그 값이 틀리면 그 틀린 회사로 가른다.
★ 옛 /sites 둘과 /branches 가 같은 안쪽 함수를 부른다(search_sites — 감독 판단 1·N3). 삭제 표시된 행은 어느 쪽에도
  안 보인다.
★ 행 잠금(select_for_update)은 여기에만 있다(lock_branch — PUT 이 사업장 행을 잠그고 고친다 · lock_branches — 일괄
  지움이 사업장 행을 id 차례로 잠근다, S12a ④. 입력 저장의 lock_branch 와 줄 서 지움 대 입력 경합을 막는다).
★ 사용 중 판정(sites_in_use·facilities_in_use)은 여기 없다 — 쓰는 표(inventory 입력 행)의 selectors 에 있고
  actions 가 services 에 넘긴다(S12a ④ · sid:MARC-ISSUE-418).
"""

from collections.abc import Collection
from typing import Literal

from django.db.models import QuerySet

from esgapi.organization.models import Site, SiteFacility
from esgapi.organization.service.utils.entities import Branch, BranchDetail, BranchFacility, BranchPage

Order = Literal["created", "headquarters"]
_ORDER: dict[Order, tuple[str, ...]] = {
    "created": ("created_at", "id"),  # 옛 GET /sites 의 차례 그대로
    "headquarters": ("-is_headquarters", "id"),  # /branches: 본사 먼저 → id 오름
}


def branch_of(row: Site) -> Branch:
    return Branch(
        id=row.pk,
        company_id=row.company_id,
        name=row.name,
        is_headquarters=row.is_headquarters,
        inventory_enabled=row.inventory_enabled,
        external_id=row.external_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _alive(company_id: int) -> QuerySet[Site]:
    return Site.for_company(company_id).filter(deleted_at__isnull=True)


def search_sites(
    company_id: int, *, q: str | None = None, order: Order = "created", offset: int = 0, limit: int | None = None
) -> BranchPage:
    """그 회사의 삭제 안 된 사업장. q 는 이름 부분 일치(대소문자 무시). count 는 자르기 전 수."""
    rows = _alive(company_id)
    if q:
        rows = rows.filter(name__icontains=q)
    ordered = rows.order_by(*_ORDER[order])
    if limit is None:  # 자르지 않는 부름(옛 GET /sites): 문 하나 — 셈은 읽은 행 수
        found = [branch_of(row) for row in ordered[offset:]]
        return BranchPage(count=offset + len(found), branches=found)
    return BranchPage(count=rows.count(), branches=[branch_of(row) for row in ordered[offset : offset + limit]])


def facilities_of(company_id: int, site_id: int) -> list[BranchFacility]:
    """그 사업장의 삭제 안 된 자산/시설 — 코드 이름 → 세부시설명 → id. 코드가 지워졌어도 글자·이름 그대로."""
    rows = (
        SiteFacility.for_company(company_id)
        .filter(site_id=site_id, deleted_at__isnull=True)
        .select_related("facility_code")
        .order_by("facility_code__name", "detail_name", "id")
    )
    return [
        BranchFacility(
            id=row.pk,
            facility_code_id=row.facility_code_id,
            facility_code=row.facility_code.code or "",
            facility_name=row.facility_code.name,
            detail_name=row.detail_name,
        )
        for row in rows
    ]


def branch_detail(company_id: int, branch_id: int) -> BranchDetail | None:
    """사업장 하나와 그 자산/시설. 없거나 남의 회사거나 삭제 표시면 None."""
    row = _alive(company_id).filter(pk=branch_id).first()
    if row is None:
        return None
    return BranchDetail(branch=branch_of(row), facilities=facilities_of(company_id, row.pk))


def lock_branch(company_id: int, branch_id: int) -> Branch | None:
    """PUT 의 사업장 행을 잠근다(그 트랜잭션 끝까지). 없거나 남의 회사거나 삭제 표시면 None."""
    row = _alive(company_id).select_for_update().filter(pk=branch_id).first()
    return None if row is None else branch_of(row)


def lock_branches(company_id: int, ids: Collection[int]) -> list[Branch]:
    """일괄 지움의 사업장 행을 id 차례로 잠근다(그 트랜잭션 끝까지 — 두 요청이 서로 다른 차례로 잡아 교착하지 않게).
    삭제 안 된 것만 — 먼저 지운 요청이 끝난 뒤 잠금을 얻으면 그 행은 빠진다(늦은 쪽 404). 남의 회사 id 는 안 든다."""
    return [branch_of(row) for row in _alive(company_id).select_for_update().filter(pk__in=list(ids)).order_by("id")]


def alive_branches(company_id: int, ids: Collection[int]) -> list[Branch]:
    """그 회사의 삭제 안 된 사업장 가운데 ids 에 든 것(일괄 토글·삭제의 「있나」). 남의 회사 id 는 안 든다."""
    return [branch_of(row) for row in _alive(company_id).filter(pk__in=list(ids)).order_by("id")]


def name_taken(company_id: int, name: str, *, except_id: int | None = None) -> bool:
    """그 회사의 삭제 안 된 사업장에 같은 이름(글자 그대로)이 있나. 고치는 행 자신은 뺀다."""
    rows = _alive(company_id).filter(name=name)
    if except_id is not None:
        rows = rows.exclude(pk=except_id)
    return rows.exists()


def headquarters_of(company_id: int) -> Branch | None:
    """그 회사의 삭제 안 된 본사(정확히 하나 — 제약 sites_one_headquarters_per_company). 없으면 None."""
    row = _alive(company_id).filter(is_headquarters=True).first()
    return None if row is None else branch_of(row)


def alive_site_named(company_id: int, name: str) -> int | None:
    """그 회사의 삭제 안 된 사업장 가운데 그 이름(글자 그대로)의 id. 없으면 None(이름은 삭제 안 된 것끼리 하나뿐)."""
    return _alive(company_id).filter(name=name).values_list("id", flat=True).first()
