"""actions/branches.py(밴드 K1b-1 ②): 두 표를 한 트랜잭션에서 — 둘째 services 부름이 실패하면 첫째 것도 되돌아간다
(감독 보정 4 — 그 실패를 둘째 부름에 심는다). S12a ④: 사용 중 판정은 inventory selectors 를 넘긴다(여기서는 가짜로
무엇을 묻는지 잰다 — 진짜 입력 행으로는 inventory/tests/service/actions/test_entries.py) · 일괄 지움은 잠금 아래에서
다시 봐 늦은 쪽 404(L3). 업무 층(진짜 DB, 주인 역할). 이름·글은 지어낸 것이다."""

from collections.abc import Collection
from datetime import datetime
from typing import Any

import pytest
from django.utils import timezone

from esgapi.inventory.service.selectors import entries as entry_selectors
from esgapi.organization.models import Company, FacilityCode, Site, SiteFacility
from esgapi.organization.service.actions import branches as actions
from esgapi.organization.service.services import branches as services
from esgapi.organization.service.services.branches import FacilityRow, FacilityTaken, InUse

pytestmark = pytest.mark.django_db


@pytest.fixture
def company_id() -> int:
    return Company.register(name="가 회사", business_licence_number="111-11-11111", subdomain="tenant-a").pk


@pytest.fixture
def boiler() -> int:
    row = FacilityCode.objects.create(name="보일러", code="F0001")
    return row.pk


def seen(site: Site) -> datetime:
    """그 사업장의 지금 판(DB 의 updated_at) — save_branch 의 seen_at(K1b-3)."""
    return Site.unscoped.get(pk=site.pk).updated_at


class Planted(Exception):
    """둘째 services 부름에 심은 실패."""


def fail(*args: Any, **kwargs: Any) -> Any:
    raise Planted


def test_a_failure_in_the_second_write_of_put_changes_nothing(
    company_id: int, boiler: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = Site.for_company(company_id).create(name="가 공장")
    kept = SiteFacility.for_company(company_id).create(site=site, facility_code_id=boiler, detail_name="1호기")
    monkeypatch.setattr(services, "save_facilities", fail)
    with pytest.raises(Planted):
        actions.save_branch(
            company_id, site.pk, seen_at=seen(site), name="나 공장", inventory_enabled=False, facilities=[]
        )
    site.refresh_from_db()
    assert (site.name, site.inventory_enabled) == ("가 공장", True)  # 첫째 쓰기(사업장 고침)도 되돌아갔다
    assert SiteFacility.unscoped.get(pk=kept.pk).deleted_at is None


def test_a_failure_in_the_second_write_of_create_leaves_no_site(
    company_id: int, boiler: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "save_facilities", fail)
    with pytest.raises(Planted):
        actions.create_branch(
            company_id, name="가 공장", inventory_enabled=True, facilities=[FacilityRow(boiler, "1호기")]
        )
    assert Site.unscoped.count() == 0


def test_a_refused_second_write_rolls_the_first_back(
    company_id: int, boiler: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """둘째 쓰기가 경합으로 갈래(FacilityTaken)를 돌려주면 set_rollback — 사업장 고침도 0."""
    site = Site.for_company(company_id).create(name="가 공장")

    def taken(*args: object, **kwargs: object) -> FacilityTaken:
        return FacilityTaken()

    monkeypatch.setattr(services, "save_facilities", taken)
    found = actions.save_branch(
        company_id, site.pk, seen_at=seen(site), name="나 공장", inventory_enabled=True, facilities=[]
    )
    assert isinstance(found, FacilityTaken)
    site.refresh_from_db()
    assert site.name == "가 공장"


def test_a_facility_keeping_its_deleted_code_is_saved(company_id: int, boiler: int) -> None:
    """이미 쓰는 줄이 지운 코드를 그대로 두면 된다(새로 고를 때만 422 — ce ② 고침 b②)."""
    site = Site.for_company(company_id).create(name="가 공장")
    row = SiteFacility.for_company(company_id).create(site=site, facility_code_id=boiler, detail_name="1호기")
    FacilityCode.objects.filter(pk=boiler).update(deleted_at=timezone.now())
    kept = actions.save_branch(
        company_id,
        site.pk,
        seen_at=seen(site),
        name="가 공장",
        inventory_enabled=True,
        facilities=[FacilityRow(boiler, "1호기", id=row.pk)],
    )
    assert not isinstance(kept, actions.SaveRefused)
    assert [(f.facility_code, f.facility_name) for f in kept.facilities] == [("F0001", "보일러")]
    picked = actions.save_branch(
        company_id,
        site.pk,
        seen_at=seen(site),
        name="가 공장",
        inventory_enabled=True,
        facilities=[FacilityRow(boiler, "2호기")],
    )
    assert isinstance(picked, actions.CodeGone)


class Asked:
    """inventory 판정 자리에 끼우는 가짜 — 물은 id 를 적고 정한 id 를 「쓰인다」로."""

    def __init__(self, used: frozenset[int] = frozenset()) -> None:
        self.used = used
        self.asked: list[frozenset[int]] = []

    def __call__(self, company_id: int, ids: Collection[int]) -> frozenset[int]:
        self.asked.append(frozenset(ids))
        return self.used


def test_save_asks_the_inventory_about_dropped_and_recoded_lines_only(
    company_id: int, boiler: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """판단 2: 묻는 것은 빠진 줄 + 코드를 바꾸는 줄 — 세부시설명만 바꾸는 줄·새 줄은 묻지 않는다."""
    burner = FacilityCode.objects.create(name="버너", code="F0002").pk
    site = Site.for_company(company_id).create(name="가 공장")
    kept, recoded, dropped = (
        SiteFacility.for_company(company_id).create(site=site, facility_code_id=boiler, detail_name=name).pk
        for name in ("1호기", "2호기", "3호기")
    )
    asked = Asked()
    monkeypatch.setattr(entry_selectors, "facilities_in_use", asked)
    rows = [
        FacilityRow(boiler, "바꾼 1호기", id=kept),
        FacilityRow(burner, "2호기", id=recoded),
        FacilityRow(boiler, "4호기"),
    ]
    found = actions.save_branch(
        company_id, site.pk, seen_at=seen(site), name="가 공장", inventory_enabled=True, facilities=rows
    )
    assert not isinstance(found, actions.SaveRefused), found
    assert asked.asked == [frozenset({recoded, dropped})]


def test_a_used_line_refuses_the_whole_save(company_id: int, boiler: int, monkeypatch: pytest.MonkeyPatch) -> None:
    burner = FacilityCode.objects.create(name="버너", code="F0002").pk
    site = Site.for_company(company_id).create(name="가 공장")
    line = SiteFacility.for_company(company_id).create(site=site, facility_code_id=boiler, detail_name="1호기").pk
    monkeypatch.setattr(entry_selectors, "facilities_in_use", Asked(frozenset({line})))
    rows = [FacilityRow(burner, "1호기", id=line)]
    found = actions.save_branch(
        company_id, site.pk, seen_at=seen(site), name="나 공장", inventory_enabled=True, facilities=rows
    )
    assert found == InUse(frozenset({line}))
    site.refresh_from_db()
    assert site.name == "가 공장"  # 사업장 고침도 되돌아감(set_rollback)
    assert SiteFacility.unscoped.get(pk=line).facility_code_id == boiler


def test_delete_asks_the_inventory_about_the_sites(company_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    site = Site.for_company(company_id).create(name="가 공장")
    asked = Asked(frozenset({site.pk}))
    monkeypatch.setattr(entry_selectors, "sites_in_use", asked)
    assert actions.delete_branches(company_id, [site.pk]) == InUse(frozenset({site.pk}))
    assert asked.asked == [frozenset({site.pk})]
    assert Site.unscoped.get(pk=site.pk).deleted_at is None


def test_the_late_delete_of_the_same_ids_is_404(company_id: int) -> None:
    """L3: 같은 ids 를 지우는 둘째 요청은 잠금 아래에서 다시 봐 404(옛: 200 {count: 0}). 동시 두 연결은 ⑤."""
    first = Site.for_company(company_id).create(name="가 공장")
    second = Site.for_company(company_id).create(name="나 공장")
    assert actions.delete_branches(company_id, [first.pk, second.pk]) == 2
    assert actions.delete_branches(company_id, [first.pk, second.pk]) == actions.NotFound()
    assert actions.delete_branches(company_id, [second.pk]) == actions.NotFound()


def test_the_headquarters_is_refused_before_the_inventory_is_asked(
    company_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    hq = services.ensure_headquarters(company_id)
    asked = Asked()
    monkeypatch.setattr(entry_selectors, "sites_in_use", asked)
    assert actions.delete_branches(company_id, [hq]) == actions.HeadquartersLocked()
    assert asked.asked == []


def test_a_headquarters_check_race_in_the_toggle_is_headquarters_locked(
    company_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2-8: 판정이 경합으로 본사를 못 봐도 CHECK 가 받쳐 409 갈래(500 아님) — 행 0 바뀜."""
    hq = services.ensure_headquarters(company_id)

    def unseen(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(actions, "_batch_problem", unseen)
    assert actions.set_branches_inventory(company_id, [hq], enabled=False) == actions.HeadquartersLocked()
    assert actions.delete_branches(company_id, [hq]) == actions.HeadquartersLocked()  # 지움은 잠금 아래 판정이 먼저
    assert Site.unscoped.filter(pk=hq, deleted_at__isnull=True, inventory_enabled=True).exists()
