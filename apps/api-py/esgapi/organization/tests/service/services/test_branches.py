"""services/branches.py(밴드 K1b-1 · S12a ④): 사용 중 판정 둘은 기본값 없는 키워드 인자 — 가짜 함수로 409 갈래·행 0 을
잰다(진짜 판정은 inventory 쪽 시험). IntegrityError 갈래(S12a 2-8): 본사 CHECK 둘 → HeadquartersLocked, 다른 이름은 다시
던짐, BASE 가 삼키던 갈래(NameTaken·FacilityTaken)와 씨앗 경합(던짐)은 그대로. 업무 층(진짜 DB, 주인 역할).
이름·글은 지어낸 것이다."""

import inspect
from collections.abc import Collection

import pytest
from django.db import IntegrityError

from esgapi.organization.models import Company, FacilityCode, Site, SiteFacility
from esgapi.organization.service.selectors import branches as selectors
from esgapi.organization.service.services import branches as services

pytestmark = pytest.mark.django_db


@pytest.fixture
def company_id() -> int:
    return Company.register(name="가 회사", business_licence_number="111-11-11111", subdomain="tenant-a").pk


class Recorder:
    """부름을 적고 정한 id 를 「쓰인다」로 돌려주는 가짜."""

    def __init__(self, used: frozenset[int]) -> None:
        self.used = used
        self.calls: list[tuple[int, frozenset[int]]] = []

    def __call__(self, company_id: int, ids: Collection[int]) -> frozenset[int]:
        self.calls.append((company_id, frozenset(ids)))
        return self.used


def test_the_in_use_checks_have_no_default() -> None:
    """빈 기본값이 다시 끼어 판정이 조용히 빠지지 않게 — 부르는 쪽이 늘 넘긴다(S12a ④). 자리 둘은 걷혔다."""
    for function, name in (
        (services.mark_sites_deleted, "sites_in_use"),
        (services.save_facilities, "facilities_in_use"),
    ):
        parameter = inspect.signature(function).parameters[name]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty
    assert not hasattr(selectors, "sites_in_use") and not hasattr(selectors, "facilities_in_use")


def test_a_site_in_use_is_not_deleted(company_id: int) -> None:
    site = Site.for_company(company_id).create(name="가 공장")
    fake = Recorder(frozenset({site.pk}))
    assert services.mark_sites_deleted(company_id, [site.pk], sites_in_use=fake) == services.InUse(frozenset({site.pk}))
    assert fake.calls == [(company_id, frozenset({site.pk}))]
    assert Site.unscoped.get(pk=site.pk).deleted_at is None
    assert services.mark_sites_deleted(company_id, [site.pk], sites_in_use=Recorder(frozenset())) == 1  # 짝


def test_a_facility_in_use_is_not_dropped(company_id: int) -> None:
    site = Site.for_company(company_id).create(name="가 공장")
    boiler = FacilityCode.objects.create(name="보일러", code="F0001")
    row = SiteFacility.for_company(company_id).create(site=site, facility_code=boiler, detail_name="1호기")
    fake = Recorder(frozenset({row.pk}))
    found = services.save_facilities(company_id, site.pk, rows=[], drop={row.pk}, facilities_in_use=fake)
    assert found == services.InUse(frozenset({row.pk}))
    assert fake.calls == [(company_id, frozenset({row.pk}))]
    assert SiteFacility.unscoped.get(pk=row.pk).deleted_at is None


def test_two_ensure_calls_leave_one_headquarters(company_id: int) -> None:
    first = services.ensure_headquarters(company_id)
    assert services.ensure_headquarters(company_id) == first
    assert Site.unscoped.filter(company_id=company_id, is_headquarters=True).count() == 1


def test_a_recoded_facility_in_use_is_refused_and_a_renamed_one_is_not_asked(company_id: int) -> None:
    """recoded(코드 바꾸는 줄)도 판정에 든다 — 쓰이면 아무것도 안 씀. recoded 밖(세부시설명만 바꿈)은 묻지 않는다."""
    site = Site.for_company(company_id).create(name="가 공장")
    boiler = FacilityCode.objects.create(name="보일러", code="F0001")
    burner = FacilityCode.objects.create(name="버너", code="F0002")
    row = SiteFacility.for_company(company_id).create(site=site, facility_code=boiler, detail_name="1호기")
    fake = Recorder(frozenset({row.pk}))
    moved = [services.FacilityRow(burner.pk, "1호기", id=row.pk)]
    found = services.save_facilities(company_id, site.pk, rows=moved, recoded={row.pk}, facilities_in_use=fake)
    assert found == services.InUse(frozenset({row.pk}))
    assert fake.calls == [(company_id, frozenset({row.pk}))]
    assert SiteFacility.unscoped.get(pk=row.pk).facility_code_id == boiler.pk
    quiet = Recorder(frozenset())
    renamed = [services.FacilityRow(boiler.pk, "2호기", id=row.pk)]
    assert services.save_facilities(company_id, site.pk, rows=renamed, facilities_in_use=quiet) is None
    assert quiet.calls == [(company_id, frozenset())]
    assert SiteFacility.unscoped.get(pk=row.pk).detail_name == "2호기"


def test_the_temporary_delete_mark_touches_only_this_site(company_id: int) -> None:
    """R8: 고치는 줄의 「잠깐 삭제 표시」는 그 사업장 조건으로만 — 다른 사업장의 줄 id 를 넣어도 그 줄은 0 바뀜."""
    mine = Site.for_company(company_id).create(name="가 공장")
    other = Site.for_company(company_id).create(name="나 공장")
    boiler = FacilityCode.objects.create(name="보일러", code="F0001")
    theirs = SiteFacility.for_company(company_id).create(site=other, facility_code=boiler, detail_name="1호기")
    before = SiteFacility.unscoped.filter(pk=theirs.pk).values("deleted_at", "updated_at", "detail_name").get()
    found = services.save_facilities(
        company_id,
        mine.pk,
        rows=[services.FacilityRow(boiler.pk, "바꾼 이름", id=theirs.pk)],
        facilities_in_use=Recorder(frozenset()),
    )
    assert found is None
    after = SiteFacility.unscoped.filter(pk=theirs.pk).values("deleted_at", "updated_at", "detail_name").get()
    assert after == before  # 삭제 표시도 남지 않고 이름도 그대로
    assert before["deleted_at"] is None  # 분모: 살아 있는 줄이었다


# ── IntegrityError 갈래(S12a 2-8) ────────────────────────────────────


def _headquarters(company_id: int) -> Site:
    return Site.for_company(company_id).get(pk=services.ensure_headquarters(company_id))


def test_deleting_the_headquarters_past_the_check_is_headquarters_locked(company_id: int) -> None:
    """actions 의 판정을 지나 CHECK(sites_headquarters_alive)에 걸려도 500 이 아니라 HeadquartersLocked — 행 0 바뀜."""
    hq = _headquarters(company_id)
    plant = Site.for_company(company_id).create(name="가 공장")
    found = services.mark_sites_deleted(company_id, [hq.pk, plant.pk], sites_in_use=Recorder(frozenset()))
    assert found == services.HeadquartersLocked()
    assert set(Site.unscoped.filter(pk__in=[hq.pk, plant.pk]).values_list("deleted_at", flat=True)) == {None}


def test_turning_the_headquarters_off_past_the_check_is_headquarters_locked(company_id: int) -> None:
    hq = _headquarters(company_id)
    plant = Site.for_company(company_id).create(name="가 공장")
    assert services.set_inventory(company_id, [hq.pk, plant.pk], enabled=False) == services.HeadquartersLocked()
    assert set(Site.unscoped.filter(pk__in=[hq.pk, plant.pk]).values_list("inventory_enabled", flat=True)) == {True}
    assert services.set_inventory(company_id, [plant.pk], enabled=False) == 1  # 짝: 본사 아니면 됨


def test_a_constraint_not_in_the_table_is_raised_again(company_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """가름은 제약 이름으로만 — 표에 없는 이름이면 다시 던진다(본사 CHECK 를 표에서 빼 「모르는 제약」으로 잰다)."""
    hq = _headquarters(company_id)
    monkeypatch.setattr(services, "HEADQUARTERS_CHECKS", frozenset[str]())
    with pytest.raises(IntegrityError, match="sites_headquarters_alive"):
        services.mark_sites_deleted(company_id, [hq.pk], sites_in_use=Recorder(frozenset()))
    with pytest.raises(IntegrityError, match="sites_headquarters_inventory_on"):
        services.set_inventory(company_id, [hq.pk], enabled=False)


def test_a_name_race_is_still_name_taken(company_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """그대로(2-8): sites_name_unique_alive 는 만들기·고침 둘 다 NameTaken(판정이 경합으로 못 본 꼴을 심는다)."""
    Site.for_company(company_id).create(name="가 공장")
    plant = Site.for_company(company_id).create(name="나 공장")

    def unseen(*args: object, **kwargs: object) -> bool:
        return False

    monkeypatch.setattr(selectors, "name_taken", unseen)
    assert services.insert_site_row(company_id, name="가 공장") == services.NameTaken()
    assert (
        services.update_site_row(company_id, plant.pk, name="가 공장", inventory_enabled=True, after=plant.updated_at)
        == services.NameTaken()
    )


def test_a_facility_race_is_still_facility_taken(company_id: int) -> None:
    """그대로(2-8): site_facilities_unique_alive → FacilityTaken(판정 없이 services 를 바로 불러 제약에 닿게)."""
    site = Site.for_company(company_id).create(name="가 공장")
    boiler = FacilityCode.objects.create(name="보일러", code="F0001")
    SiteFacility.for_company(company_id).create(site=site, facility_code=boiler, detail_name="1호기")
    found = services.save_facilities(
        company_id, site.pk, rows=[services.FacilityRow(boiler.pk, "1호기")], facilities_in_use=Recorder(frozenset())
    )
    assert found == services.FacilityTaken()


def test_a_headquarters_seed_race_still_raises(company_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """그대로(2-8): ensure_headquarters 의 씨앗 경합은 던진다(sites_one_headquarters_per_company — 중복 0)."""
    services.ensure_headquarters(company_id)

    def unseen(*args: object) -> None:
        return None

    monkeypatch.setattr(selectors, "headquarters_of", unseen)
    monkeypatch.setattr(selectors, "alive_site_named", unseen)
    with pytest.raises(IntegrityError):
        services.ensure_headquarters(company_id)
    assert Site.unscoped.filter(company_id=company_id, is_headquarters=True).count() == 1
