"""사업장 넓힘·코드 목록·사업장별 자산/시설의 DB 제약(밴드 K1b-1 ① — migrations/0002). 업무 층, 주인 역할 연결.

거절마다 됨의 짝을 둔다(제약이 너무 넓어 모든 행을 막는 것도 잡는다). 이름·글은 지어낸 것이다.
"""

from typing import Any

import psycopg
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from esgapi.organization.models import Company, FacilityCode, Site, SiteFacility

pytestmark = pytest.mark.django_db


def company(subdomain: str, licence: str) -> int:
    return Company.register(name=f"{subdomain} 회사", business_licence_number=licence, subdomain=subdomain).pk


@pytest.fixture
def companies() -> tuple[int, int]:
    return company("tenant-a", "111-11-11111"), company("tenant-b", "222-22-22222")


def site(company_id: int, name: str, **fields: Any) -> Site:
    return Site.for_company(company_id).create(name=name, **fields)


def code(name: str, **fields: Any) -> FacilityCode:
    return FacilityCode.objects.create(name=name, **fields)


def refused(constraint: str, make: Any) -> None:
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        make()


def sqlstate_of(make: Any) -> str | None:
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        make()
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error)
    return cause.sqlstate


# ── sites 의 칸 넷과 제약 넷 ─────────────────────────────────────────


def test_a_new_site_takes_the_defaults(companies: tuple[int, int]) -> None:
    a, _ = companies
    row = site(a, "가 공장")
    row.refresh_from_db()
    assert (row.is_headquarters, row.inventory_enabled, row.deleted_at, row.updated_at is not None) == (
        False,
        True,
        None,
        True,
    )


def test_one_headquarters_per_company(companies: tuple[int, int]) -> None:
    a, b = companies
    site(a, "본사", is_headquarters=True)
    refused("sites_one_headquarters_per_company", lambda: site(a, "둘째 본사", is_headquarters=True))
    site(b, "본사", is_headquarters=True)  # 짝: 다른 회사는 따로 하나
    site(a, "가 공장")  # 짝: 본사 아닌 것은 몇이든
    assert Site.for_company(a).filter(is_headquarters=True).count() == 1


def test_a_name_is_unique_among_the_alive_sites_of_a_company(companies: tuple[int, int]) -> None:
    a, b = companies
    first = site(a, "가 공장")
    refused("sites_name_unique_alive", lambda: site(a, "가 공장"))
    site(b, "가 공장")  # 짝: 다른 회사는 같은 이름을 쓴다
    Site.for_company(a).filter(pk=first.pk).update(deleted_at=timezone.now())
    site(a, "가 공장")  # 짝: 지운 이름은 다시 쓴다
    assert Site.unscoped.filter(name="가 공장").count() == 3


def test_a_headquarters_cannot_be_marked_deleted(companies: tuple[int, int]) -> None:
    a, _ = companies
    hq = site(a, "본사", is_headquarters=True)
    refused(
        "sites_headquarters_alive",
        lambda: Site.for_company(a).filter(pk=hq.pk).update(deleted_at=timezone.now()),
    )
    other = site(a, "가 공장")
    Site.for_company(a).filter(pk=other.pk).update(deleted_at=timezone.now())  # 짝: 보통 사업장은 지운다


def test_a_headquarters_keeps_the_inventory_on(companies: tuple[int, int]) -> None:
    a, _ = companies
    refused("sites_headquarters_inventory_on", lambda: site(a, "본사", is_headquarters=True, inventory_enabled=False))
    site(a, "가 공장", inventory_enabled=False)  # 짝: 보통 사업장은 끈다


# ── 코드 목록(공통) ──────────────────────────────────────────────────


def test_a_facility_code_name_is_unique_among_the_alive_codes() -> None:
    first = code("보일러", code="F0001")
    refused("facility_codes_name_unique_alive", lambda: code("보일러", code="F0002"))
    FacilityCode.objects.filter(pk=first.pk).update(deleted_at=timezone.now())
    code("보일러", code="F0002")  # 짝: 지운 이름은 다시 쓴다
    refused(
        "organization_facility_codes_code_key", lambda: code("냉동기", code="F0001")
    )  # code 는 지워도 겹치지 않는다


def test_a_facility_code_has_no_company_column() -> None:
    assert "company_id" not in {field.attname for field in FacilityCode._meta.concrete_fields}


# ── 사업장별 자산/시설 ────────────────────────────────────────────────


def test_a_facility_is_unique_per_site_code_and_detail_among_the_alive(companies: tuple[int, int]) -> None:
    a, _ = companies
    plant = site(a, "가 공장")
    other_plant = site(a, "나 공장")
    boiler = code("보일러", code="F0001")
    rows = SiteFacility.for_company(a)
    first = rows.create(site=plant, facility_code=boiler, detail_name="1호기")
    refused("site_facilities_unique_alive", lambda: rows.create(site=plant, facility_code=boiler, detail_name="1호기"))
    rows.create(site=plant, facility_code=boiler, detail_name="2호기")  # 짝: 세부시설명이 다르면 된다
    rows.create(site=other_plant, facility_code=boiler, detail_name="1호기")  # 짝: 다른 사업장
    rows.filter(pk=first.pk).update(deleted_at=timezone.now())
    rows.create(site=plant, facility_code=boiler, detail_name="1호기")  # 짝: 지운 것은 다시 쓴다
    assert rows.count() == 4


def test_a_facility_cannot_point_at_another_companys_site(companies: tuple[int, int]) -> None:
    """같은 회사 외래 키(site_facilities_site_id_same_company_fk): INSERT 도 UPDATE 도 그 문에서 23503."""
    a, b = companies
    mine = site(a, "가 공장")
    theirs = site(b, "나 공장")
    boiler = code("보일러", code="F0001")
    fields = {"facility_code_id": boiler.pk, "detail_name": "1호기"}
    assert sqlstate_of(lambda: SiteFacility.unscoped.create(company_id=a, site_id=theirs.pk, **fields)) == "23503"
    row = SiteFacility.unscoped.create(company_id=a, site_id=mine.pk, **fields)  # 짝: 내 사업장은 된다
    assert sqlstate_of(lambda: SiteFacility.unscoped.filter(pk=row.pk).update(site_id=theirs.pk)) == "23503"
    assert SiteFacility.unscoped.get(pk=row.pk).site_id == mine.pk


def test_the_used_code_entrance_answers_code_ids_across_companies_and_skips_deleted(
    companies: tuple[int, int],
) -> None:
    """S12S1 Q9(7a 허락 ④): SiteFacility.used_code_ids — 어느 회사의 사업장이든 쓰는 코드 id 만(회사를 가리지 않음) ·
    삭제 표시한 행은 쓰는 것이 아니다 · 묻지 않은 코드는 내지 않는다. 돌려주는 것은 코드 id 집합뿐(회사 id·행 0)."""
    a, b = companies
    first, second, third, unused = (code(f"지어낸 설비 {n}", code=f"F900{n}") for n in range(4))
    SiteFacility.for_company(a).create(site=site(a, "가 공장"), facility_code=first, detail_name="가")
    SiteFacility.for_company(b).create(site=site(b, "나 공장"), facility_code=second, detail_name="나")
    gone = SiteFacility.for_company(b).create(site=site(b, "다 공장"), facility_code=third, detail_name="다")
    SiteFacility.for_company(b).filter(pk=gone.pk).update(deleted_at=timezone.now())
    asked = [first.pk, second.pk, third.pk, unused.pk]
    assert SiteFacility.used_code_ids(asked) == frozenset({first.pk, second.pk})  # 두 회사 다 · 지운 행 빠짐
    assert SiteFacility.used_code_ids([second.pk]) == frozenset({second.pk})  # 묻지 않은 코드는 내지 않는다
    assert SiteFacility.used_code_ids([]) == frozenset()
    assert all(isinstance(found, int) for found in SiteFacility.used_code_ids(asked))
