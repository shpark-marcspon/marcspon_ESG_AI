"""Scope 1·2 입력의 유스케이스(밴드 S12a ② — service/actions/entries.py). 업무 층, 주인 역할 연결.

셈 저장 = 손셈 · 잡은 판(풀 고침 뒤에도 같은 값) · 히스토리 · N/A · 422 · 잠김 409 · 남의·꺼진 사업장·다른 코드 ·
리스트 Y-2·Y-1·Y · 자릿수 · S17 숨김 · 0 씀. 풀은 운영 관리자 actions 로, 사업장은 organization services 로 짓는다
(organization models import 0). 이름·값은 지어낸 것이다(실제 회사·계수 0).

손셈(지어낸 계수 — ghg_pool_support.draft: 투입 kg · 순발열량 끔 · CO2 계수 1.5 · GWP 1 · 계수 단위 kg/kg):
  1000 kg + 1000 kg = 2000 kg × 1.5 kg/kg = 3000 kg = 3 tCO2-eq
  2 t → 2000 kg(t→kg 쌍) → 3 tCO2-eq
풀이 그 계수를 CO2 3 으로 고쳐 새 판이 서도 잡은 판(1.5)으로 셈한다.
"""

from datetime import date
from decimal import Decimal

import pytest

from esgapi.inventory.models import (
    CompanyIndexSelection,
    GhgFactorVersion,
    InventoryCustomFactor,
    InventoryEntryHistory,
    InventoryEntryPeriod,
    InventoryEntryRow,
    InventoryEntryValue,
    InventoryYear,
)
from esgapi.inventory.service.actions import entries as actions
from esgapi.inventory.service.actions import ghg_pool as pool_actions
from esgapi.inventory.service.actions import index_selection as selection_actions
from esgapi.inventory.service.services import entries as services
from esgapi.inventory.service.utils.entries import (
    CUSTOM_UNIT_MISMATCH,
    MAX_ROWS_PER_SAVE,
    POOL_UNIT_MISMATCH,
    Actor,
    CustomView,
    FactorRef,
    HistoryLine,
    HistoryPage,
    IndexDetail,
    Locked,
    RestoreStale,
    RowInput,
    RowList,
    RowView,
    SlotInput,
    YearLine,
    custom_unit_problem,
)
from esgapi.inventory.service.utils.ghg_pool import (
    FacilityView,
    FactorDraft,
    FactorValues,
    FactorView,
    Forbidden,
    GasDraft,
    Invalid,
    NotFound,
    check_factor,
)
from esgapi.inventory.service.utils.ghg_pool import InUse as PoolInUse
from esgapi.inventory.service.utils.index_selection import SaveResult
from esgapi.inventory.tests.entries_support import Place, entry_row, place
from esgapi.inventory.tests.ghg_pool_support import ADMIN, activity, code, draft, factor
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf, current_version, edit_factor, pool_leaf, site
from esgapi.organization.service.actions import branches as branch_actions
from esgapi.organization.service.selectors.branches import branch_detail, facilities_of
from esgapi.organization.service.services.branches import FacilityRow, InUse, set_inventory
from esgapi.organization.service.utils.entities import BranchDetail

pytestmark = pytest.mark.django_db

CUSTOMER = Actor("service", 11)
OPERATOR_ACTOR = Actor("admin", 12)
JAN, FEB, MAR = f"{YEAR}-01", f"{YEAR}-02", f"{YEAR}-03"


@pytest.fixture
def leaf() -> Leaf:
    return pool_leaf(activity(), "가 보일러")


@pytest.fixture
def here(companies: tuple[int, int], leaf: Leaf) -> Place:
    return place(companies[0], leaf)


def row(
    where: Place,
    *values: tuple[str, str | None],
    unit: str = "kg",
    na: bool = False,
    facility: int | None = None,
    row_id: int | None = None,
    estimated: bool = False,
) -> RowInput:
    return RowInput(
        site_facility_id=where.facility_id if facility is None else facility,
        unit=unit,
        na=na,
        values=tuple(SlotInput(slot, amount, estimated) for slot, amount in values),
        row_id=row_id,
    )


def save(where: Place, *rows: RowInput, actor: Actor = CUSTOMER, site_id: int | None = None) -> object:
    return actions.save_rows(
        where.company_id, YEAR, where.node_id, where.site_id if site_id is None else site_id, rows, actor
    )


def saved(where: Place, *rows: RowInput, actor: Actor = CUSTOMER) -> IndexDetail:
    found = save(where, *rows, actor=actor)
    assert isinstance(found, IndexDetail), found
    return found


def detail(where: Place) -> IndexDetail:
    found = actions.index_detail(where.company_id, YEAR, where.node_id)
    assert isinstance(found, IndexDetail), found
    return found


def counts(company_id: int) -> tuple[int, int, int]:
    return (
        InventoryEntryRow.for_company(company_id).count(),
        InventoryEntryValue.for_company(company_id).count(),
        InventoryEntryHistory.for_company(company_id).count(),
    )


def history(company_id: int) -> list[tuple[str, str | None, str | None, str | None]]:
    return [
        (line.kind, line.slot, line.before, line.after)
        for line in InventoryEntryHistory.for_company(company_id).order_by("id")
    ]


def only_row(found: IndexDetail) -> tuple[int, Decimal | None, str | None]:
    (block,) = found.sites
    (line,) = block.rows
    return line.id, line.emission, line.emission_problem


# ── 셈 · 잡은 판 ───────────────────────────────────────────────────


def test_the_saved_emission_is_the_hand_calc(here: Place) -> None:
    found = saved(here, row(here, (JAN, "1000"), (FEB, "1000")))
    _, emission, problem = only_row(found)
    assert (emission, problem) == (Decimal(3), None)
    assert found.totals.all == {YEAR - 2: None, YEAR - 1: None, YEAR: Decimal(3)}
    assert [(total.site_id, total.values[YEAR]) for total in found.totals.by_site] == [(here.site_id, Decimal(3))]
    assert found.unit_options == ("kg", "g", "t")
    assert found.path == ("범위 가", "유형 가", "활동 가", found.name)
    assert found.factor.version == 1


def test_a_row_in_tonnes_follows_the_conversion(here: Place) -> None:
    _, emission, _ = only_row(saved(here, row(here, (JAN, "2"), unit="t")))
    assert emission == Decimal(3)


def test_the_pinned_version_is_used_after_the_pool_changes(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    assert leaf.factor_id is not None
    edited = pool_actions.save_factor(
        actor_kind=ADMIN,
        factor_id=leaf.factor_id,
        draft=draft(gases=(GasDraft("CO2", enabled=True, factor="3", gwp="1"),)),
    )
    assert isinstance(edited, FactorView) and edited.version == 2
    assert current_version(here.node_id) != here.version_id
    found = saved(here, row(here, (JAN, "2000"), row_id=rid))
    assert only_row(found)[1] == Decimal(3)  # 판 1(1.5)로: 2000 × 1.5 kg — 판 2(3)였으면 6
    assert found.factor.version == 1
    selection = CompanyIndexSelection.for_company(here.company_id).get(pk=here.selection_id)
    assert selection.factor_version_id == here.version_id  # 저장이 잡은 판을 바꾸지 않는다


# ── 히스토리 · N/A ─────────────────────────────────────────────────


def test_each_changed_value_writes_one_history_line(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"), (FEB, None))))
    assert history(here.company_id) == [("value", JAN, None, "1000")]  # 없는 칸을 빈 칸으로는 0
    saved(here, row(here, (JAN, "1000.000"), row_id=rid))
    assert len(history(here.company_id)) == 1  # 같은 값 0
    saved(here, row(here, (JAN, "5"), (FEB, "0.5"), row_id=rid))
    saved(here, row(here, (JAN, None), row_id=rid))
    assert history(here.company_id)[1:] == [
        ("value", JAN, "1000", "5"),
        ("value", FEB, None, "0.5"),
        ("value", JAN, "5", None),
    ]
    (line,) = InventoryEntryHistory.for_company(here.company_id).filter(after="0.5")
    assert (line.actor_kind, line.actor_user_id, line.unit) == ("service", CUSTOMER.user_id, "kg")


def test_na_writes_on_and_off_and_stays_out_of_the_sums(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    second = site(here.company_id, leaf.code_id, name="나 공장")
    other = Place(**{**here.__dict__, "site_id": second, "facility_id": facilities_of(here.company_id, second)[0].id})
    saved(other, row(other, (JAN, "2000")))
    rid = row_at(saved(here, row(here, (JAN, "1000"))), here.site_id).id
    found = saved(here, row(here, (JAN, "1000"), na=True, row_id=rid))
    assert only_row_of(found, here.site_id) == (None, None)
    assert found.totals.all[YEAR] == Decimal(3)  # N/A 행은 합에서 빠진다(2000 kg 만)
    assert history(here.company_id)[-1] == ("na_on", None, None, None)
    found = saved(here, row(here, (JAN, "1000"), row_id=rid))
    assert history(here.company_id)[-1] == ("na_off", None, None, None)
    assert found.totals.all[YEAR] == Decimal("4.5")


def row_at(found: IndexDetail, site_id: int) -> RowView:
    (block,) = [block for block in found.sites if block.site_id == site_id]
    (line,) = block.rows
    return line


def only_row_of(found: IndexDetail, site_id: int) -> tuple[Decimal | None, str | None]:
    line = row_at(found, site_id)
    return line.emission, line.emission_problem


def test_an_empty_row_has_no_emission(here: Place) -> None:
    found = saved(here, row(here))
    assert only_row(found)[1:] == (None, None)
    assert found.totals.all[YEAR] is None


# ── 422 — 하나라도 걸리면 0 씀 ─────────────────────────────────────


def test_every_refusal_is_422_and_writes_nothing(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    a, b = companies
    there = place(b, leaf)
    other_code = pool_leaf(activity("나"), "다 버너")
    elsewhere = site(a, other_code.code_id, name="다 공장")
    (wrong,) = facilities_of(a, elsewhere)
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1"))))
    b_row = entry_row(there)
    before = counts(a), history(a)
    good = row(here, (JAN, "2"), row_id=rid)
    cases: list[tuple[tuple[RowInput, ...], str]] = [
        ((good,) * (MAX_ROWS_PER_SAVE + 1), "rows"),
        ((good, row(here, facility=wrong.id)), "rows.1.siteFacilityId"),  # 다른 코드의 자산/시설
        ((good, row(here, facility=there.facility_id)), "rows.1.siteFacilityId"),  # 남의 회사
        ((row(here, (JAN, "2")),), "rows.0.siteFacilityId"),  # 새 행인데 이미 있음
        ((good, good), "rows.1.siteFacilityId"),  # 두 번
        ((row(here, (JAN, "2"), row_id=b_row.pk),), "rows.0.rowId"),  # 남의 행
        ((row(here, (JAN, "2"), unit="L", row_id=rid),), "rows.0.unit"),
        ((row(here, (JAN, "2"), (f"{YEAR + 1}-01", "1"), row_id=rid),), "rows.0.values.1.slot"),
        ((row(here, (JAN, "2"), (JAN, "3"), row_id=rid),), "rows.0.values.1.slot"),
        ((row(here, (JAN, "-1"), row_id=rid),), "rows.0.values.0.amount"),
        ((row(here, (JAN, "1e3"), row_id=rid),), "rows.0.values.0.amount"),
        ((row(here, (JAN, "1.1234567"), row_id=rid),), "rows.0.values.0.amount"),
    ]
    for rows, key in cases:
        found = save(here, *rows)
        assert isinstance(found, Invalid) and key in found.fields, (key, found)
        assert (counts(a), history(a)) == before, key
    assert detail(here).sites[0].rows[0].values[0].amount == Decimal(1)


def test_a_facility_of_another_code_on_the_same_site_is_refused(here: Place, leaf: Leaf) -> None:
    other_code = pool_leaf(activity("나"), "라 버너")
    mixed = site(here.company_id, leaf.code_id, other_code.code_id, name="라 공장")
    (wrong,) = [f for f in facilities_of(here.company_id, mixed) if f.facility_code_id == other_code.code_id]
    found = save(here, row(here, (JAN, "1"), facility=wrong.id), site_id=mixed)
    assert isinstance(found, Invalid) and found.fields == {"rows.0.siteFacilityId": actions.NOT_HERE}, found
    assert counts(here.company_id) == (0, 0, 0)


def test_a_save_writes_nothing_when_a_later_step_fails(here: Place, monkeypatch: pytest.MonkeyPatch) -> None:
    """한 트랜잭션(@transaction.atomic): 셈 칸 쓰기가 터지면 앞의 행·값·히스토리도 되돌린다."""

    def boom(*_: object) -> int:
        raise RuntimeError("심은 실패")

    monkeypatch.setattr(services, "update_rows", boom)
    with pytest.raises(RuntimeError):
        save(here, row(here, (JAN, "1")))
    assert counts(here.company_id) == (0, 0, 0)


# ── 사업장 · 회사 ─────────────────────────────────────────────────


def test_other_company_or_disabled_sites_are_not_found(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    _, b = companies
    there = place(b, leaf)
    assert save(here, row(here), site_id=there.site_id) == NotFound()
    set_inventory(here.company_id, [here.site_id], enabled=False)
    assert save(here, row(here)) == NotFound()
    assert counts(here.company_id) == (0, 0, 0)


def test_a_save_in_a_does_not_touch_b(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    _, b = companies
    there = place(b, leaf)
    saved(here, row(here, (JAN, "1")))
    assert counts(b) == (0, 0, 0)
    found = actions.index_detail(b, YEAR, there.node_id)
    assert isinstance(found, IndexDetail) and found.sites[0].rows == ()


def test_disabled_site_rows_leave_detail_list_and_sums(here: Place, leaf: Leaf) -> None:
    second = site(here.company_id, leaf.code_id, name="나 공장")
    other = Place(**{**here.__dict__, "site_id": second, "facility_id": facilities_of(here.company_id, second)[0].id})
    saved(here, row(here, (JAN, "1000")))
    saved(other, row(other, (JAN, "2000")))
    set_inventory(here.company_id, [here.site_id], enabled=False)
    found = detail(here)
    assert [block.site_id for block in found.sites] == [second] and found.totals.all[YEAR] == Decimal(3)
    listed = actions.list_rows(here.company_id, YEAR)
    assert isinstance(listed, RowList)
    (scope,) = listed.scopes
    assert scope.rows[0].values[YEAR] == Decimal(3) and scope.values[YEAR] == Decimal(3)  # 켠 사업장 몫만
    set_inventory(here.company_id, [second], enabled=False)
    assert detail(here).sites == () and detail(here).totals.all[YEAR] is None
    listed = actions.list_rows(here.company_id, YEAR)
    assert isinstance(listed, RowList)
    (scope,) = listed.scopes
    assert scope.rows[0].values[YEAR] is None and scope.values[YEAR] is None
    assert counts(here.company_id)[0] == 2  # 행은 남는다(판단 9)


def test_an_estimate_only_change_writes_the_value_but_no_history(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    saved(here, row(here, (JAN, "1000"), row_id=rid, estimated=True))
    (value,) = InventoryEntryValue.for_company(here.company_id).all()
    assert (value.amount, value.estimated) == (Decimal(1000), True)
    assert history(here.company_id) == [("value", JAN, None, "1000")]  # 추정 표시만 — 히스토리 0


def test_hidden_or_missing_index_is_not_found(here: Place) -> None:
    assert actions.index_detail(here.company_id, YEAR - 1, here.node_id) == NotFound()
    assert actions.index_detail(here.company_id, YEAR, here.node_id + 9999) == NotFound()
    CompanyIndexSelection.for_company(here.company_id).filter(pk=here.selection_id).update(hidden=True)
    assert actions.index_detail(here.company_id, YEAR, here.node_id) == NotFound()
    assert save(here, row(here)) == NotFound()


# ── 잠금 · 메모 · 지움 ──────────────────────────────────────────────


def test_a_locked_index_refuses_writes_until_an_operator_unlocks(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1"))))
    before = counts(here.company_id)
    locked = actions.lock_index(here.company_id, YEAR, here.node_id, CUSTOMER)
    assert isinstance(locked, IndexDetail) and locked.locked_at is not None
    assert locked.locked_by == (CUSTOMER.user_id, "")  # 지어낸 id 라 이름 없음
    again = actions.lock_index(here.company_id, YEAR, here.node_id, OPERATOR_ACTOR)
    assert isinstance(again, IndexDetail) and again.locked_at == locked.locked_at  # 이미 잠김 — 0 바뀜
    assert save(here, row(here, (JAN, "2"), row_id=rid)) == Locked()
    assert actions.delete_rows(here.company_id, YEAR, here.node_id, [rid]) == Locked()
    assert actions.set_memo(here.company_id, YEAR, here.node_id, "글") == Locked()
    assert counts(here.company_id) == before
    assert actions.unlock_index(here.company_id, YEAR, here.node_id, actor_kind="service") == Forbidden(actions.UNLOCK)
    unlocked = actions.unlock_index(here.company_id, YEAR, here.node_id, actor_kind="admin")
    assert isinstance(unlocked, IndexDetail) and (unlocked.locked_at, unlocked.locked_by) == (None, None)
    assert isinstance(save(here, row(here, (JAN, "2"), row_id=rid)), IndexDetail)


def test_memo(here: Place) -> None:
    assert actions.set_memo(here.company_id, YEAR, here.node_id, "지어낸 메모") == "지어낸 메모"
    assert detail(here).memo == "지어낸 메모"
    assert isinstance(actions.set_memo(here.company_id, YEAR, here.node_id, "가" * 2001), Invalid)
    assert actions.set_memo(here.company_id, YEAR - 1, here.node_id, "") == NotFound()


def test_delete_marks_rows_and_keeps_values_and_history(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    _, b = companies
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1"))))
    b_row = entry_row(place(b, leaf))
    assert actions.delete_rows(here.company_id, YEAR, here.node_id, [rid, b_row.pk]) == NotFound()  # 하나라도 — 0
    assert actions.delete_rows(here.company_id, YEAR, here.node_id, [rid]) == 1
    assert detail(here).sites[0].rows == ()
    assert detail(here).sites[0].facilities[0].has_row is False
    assert counts(here.company_id) == (1, 1, 1)  # 삭제 표시 — 값·히스토리 그대로
    assert actions.delete_rows(here.company_id, YEAR, here.node_id, [rid]) == NotFound()
    assert actions.delete_rows(here.company_id, YEAR, here.node_id, []) == NotFound()
    assert isinstance(saved(here, row(here, (JAN, "4"))), IndexDetail)  # 지운 자리에 새 행


# ── 자릿수 · 해 · 리스트 · 히스토리 · S17 ───────────────────────────


def test_decimals_change_display_only(here: Place) -> None:
    saved(here, row(here, (JAN, "1000")))
    assert actions.set_decimals(here.company_id, YEAR, 3) == 3
    found = detail(here)
    assert (found.decimals, only_row(found)[1]) == (3, Decimal("1.5"))
    assert isinstance(actions.set_decimals(here.company_id, YEAR, 4), Invalid)
    assert actions.set_decimals(here.company_id, YEAR - 1, 1) == NotFound()


def past_year(where: Place, year: int) -> Place:
    """같은 사업장·자산/시설에 다른 해의 선택 하나."""
    year_id = InventoryYear.for_company(where.company_id).create(year=year).pk
    selection_id = (
        CompanyIndexSelection.for_company(where.company_id)
        .create(inventory_year_id=year_id, facility_node_id=where.node_id, factor_version_id=where.version_id)
        .pk
    )
    return Place(**{**where.__dict__, "year_id": year_id, "selection_id": selection_id})


def test_years_and_the_three_year_list(here: Place) -> None:
    old = past_year(here, YEAR - 2)
    entry_row(old, emission=Decimal("1.5"))
    saved(here, row(here, (JAN, "1000"), estimated=True))
    assert actions.years(here.company_id) == [YearLine(YEAR, True), YearLine(YEAR - 2, True)]
    found = actions.list_rows(here.company_id, YEAR)
    assert isinstance(found, RowList) and found.configured and found.years == (YEAR - 2, YEAR - 1, YEAR)
    (scope,) = found.scopes
    assert scope.scope_name == "범위 가"
    (line,) = scope.rows
    assert line.values == {YEAR - 2: Decimal("1.5"), YEAR - 1: None, YEAR: Decimal("1.5")}
    assert (line.estimated, line.has_memo, line.locked) == (True, False, False)
    assert scope.values == line.values
    assert actions.list_rows(here.company_id, YEAR, "보일러") == found
    assert actions.list_rows(here.company_id, YEAR, "범위") == found  # 조상 이름도
    empty = actions.list_rows(here.company_id, YEAR, "없는 이름")
    assert isinstance(empty, RowList) and empty.scopes == ()
    assert isinstance(actions.list_rows(here.company_id, YEAR, "가" * 101), Invalid)
    none = actions.list_rows(here.company_id, YEAR - 1)
    assert isinstance(none, RowList) and (none.configured, none.scopes, none.decimals) == (False, (), 2)


def test_row_history_pages_and_refuses_deleted_rows(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1"), (FEB, "2"))))
    page = actions.row_history(here.company_id, YEAR, here.node_id, rid, offset=0, limit=1)
    assert not isinstance(page, NotFound)
    assert page.count == 2 and len(page.lines) == 1 and page.lines[0].actor_kind == "service"
    assert actions.row_history(here.company_id, YEAR - 1, here.node_id, rid, offset=0, limit=1) == NotFound()
    actions.delete_rows(here.company_id, YEAR, here.node_id, [rid])
    assert actions.row_history(here.company_id, YEAR, here.node_id, rid, offset=0, limit=1) == NotFound()


def test_s17_hides_a_dropped_leaf_with_rows(here: Place) -> None:
    saved(here, row(here))  # 값 없는 행도 「데이터 있음」(판단 1)
    result = selection_actions.save_selections(here.company_id, YEAR, [], on=date(2026, 10, 29))
    assert result == SaveResult(selected=0, hidden_with_data=1)
    selection = CompanyIndexSelection.for_company(here.company_id).get(pk=here.selection_id)
    assert (selection.hidden, selection.deleted_at) == (True, None)


# ── 조직구조 쪽 사용 중(④ — sid:MARC-ISSUE-418 · 발주서 2-6 · 판단 1·2) ─────────────────────


def test_a_site_with_alive_rows_is_not_deleted(here: Place) -> None:
    """L1-a: 살아 있는 입력 행이 있는 사업장 지움은 InUse — 사업장·자산/시설·행 0 바뀜. 값 없는 행도 셈(판단 1)."""
    rid, _, _ = only_row(saved(here, row(here)))
    other = site(here.company_id, here_code(here), name="나 공장")
    found = branch_actions.delete_branches(here.company_id, [here.site_id, other])
    assert found == InUse(frozenset({here.site_id}))
    assert [f.id for f in facilities_of(here.company_id, here.site_id)] == [here.facility_id]
    assert len(facilities_of(here.company_id, other)) == 1  # 요청 전체 거절 — 쓰이지 않는 쪽도 그대로
    actions.delete_rows(here.company_id, YEAR, here.node_id, [rid])
    assert branch_actions.delete_branches(here.company_id, [here.site_id, other]) == 2  # 지운 행은 안 셈


def test_a_hidden_selections_rows_still_keep_the_site(here: Place) -> None:
    """숨긴 인덱스에 행이 있으면 그 사업장은 숨김 풀기 전 못 지운다(데이터 보존 — 발주서 §6 W12)."""
    saved(here, row(here))
    selection_actions.save_selections(here.company_id, YEAR, [], on=date(2026, 10, 29))
    assert CompanyIndexSelection.for_company(here.company_id).get(pk=here.selection_id).hidden  # 분모: 숨김
    assert branch_actions.delete_branches(here.company_id, [here.site_id]) == InUse(frozenset({here.site_id}))


def here_code(where: Place) -> int:
    (facility,) = facilities_of(where.company_id, where.site_id)
    return facility.facility_code_id


def save_branch(where: Place, *facilities: FacilityRow) -> BranchDetail | branch_actions.SaveRefused:
    found = branch_detail(where.company_id, where.site_id)
    assert found is not None
    return branch_actions.save_branch(
        where.company_id,
        where.site_id,
        seen_at=found.branch.updated_at,  # 지금 판(K1b-3) — 입력 저장은 사업장 행을 쓰지 않는다
        name="가 공장",
        inventory_enabled=True,
        facilities=facilities,
    )


def test_a_used_facility_cannot_be_dropped_or_recoded_but_can_be_renamed(here: Place) -> None:
    """L1-b: 쓰이는 자산/시설 뺌·코드 바꿈은 InUse(행 0 바뀜), 세부시설명 바꿈은 됨(판단 2).
    행은 같은 자산/시설을 가리킨다."""
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1"))))
    code = here_code(here)
    other_code = pool_leaf(activity("나"), "라 버너").code_id
    spare = FacilityRow(code, "예비")
    assert save_branch(here, spare) == InUse(frozenset({here.facility_id}))  # 뺌
    moved = FacilityRow(other_code, "0호기", id=here.facility_id)
    assert save_branch(here, moved) == InUse(frozenset({here.facility_id}))  # 코드 바꿈
    assert [(f.id, f.facility_code_id, f.detail_name) for f in facilities_of(here.company_id, here.site_id)] == [
        (here.facility_id, code, "0호기")
    ]
    renamed = save_branch(here, FacilityRow(code, "새 이름", id=here.facility_id), spare)
    assert isinstance(renamed, BranchDetail), renamed
    assert sorted(f.detail_name for f in renamed.facilities) == ["새 이름", "예비"]
    assert InventoryEntryRow.for_company(here.company_id).get(pk=rid).site_facility_id == here.facility_id
    (unused,) = [f.id for f in facilities_of(here.company_id, here.site_id) if f.detail_name == "예비"]
    recoded = save_branch(
        here, FacilityRow(code, "새 이름", id=here.facility_id), FacilityRow(other_code, "예비", id=unused)
    )
    assert not isinstance(recoded, branch_actions.SaveRefused), recoded  # 짝: 안 쓰이는 줄은 코드를 바꿈


def test_another_companys_rows_do_not_keep_my_site(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    """B 의 행은 A 의 사업장 지움·코드 바꿈을 막지 않는다(판정은 회사 조건 — 분모: B 에 행이 있다)."""
    there = place(companies[1], leaf)
    saved(there, row(there, (JAN, "1")))
    assert counts(companies[1])[0] == 1
    assert branch_actions.delete_branches(here.company_id, [here.site_id]) == 1


# ── S12a-2 ②: 입력주기(S7) · 계수 바꿈(S9·S11) · 복구(S12) · 470 M2·M4 ───────────────────────────
#
# 손셈(지어낸 계수): 선택이 잡은 판 CO2 1.5 kg/kg · 같은 잎 둘째 계수 CO2 4 kg/kg · 직접입력 CO2 2 kg/kg(GWP 1).
#   1000 kg × 1.5 = 1.5 t · × 4 = 4 t · × 2 = 2 t.
# 계수 바꿈의 운영 관리자 칸은 core/permissions.py 의 표(H1 — ③)가 세운다.

Q1, Q2 = f"{YEAR}-Q1", f"{YEAR}-Q2"
WHY = "지어낸 사유"


def second_factor(leaf: Leaf, gas: str = "4") -> int:
    """같은 잎의 둘째 계수(기본 아님) — 계수 id."""
    return factor(leaf.id, name="계수 나", gases=(GasDraft("CO2", enabled=True, factor=gas, gwp="1"),)).id


def custom_draft(**fields: object) -> FactorDraft:
    """직접입력 계수(투입 kg · CO2 2 kg/kg)."""
    base: dict[str, object] = {"name": "가 직접 계수", "gases": (GasDraft("CO2", enabled=True, factor="2", gwp="1"),)}
    return draft(**(base | fields))


def period(where: Place, value: str, actor: Actor = CUSTOMER) -> object:
    return actions.set_period(where.company_id, YEAR, where.node_id, where.site_id, value, actor)


def change_factor(
    where: Place,
    rid: int,
    *,
    factor_id: int | None = None,
    custom: FactorDraft | None = None,
    reason: str | None = WHY,
    actor: Actor = OPERATOR_ACTOR,
) -> object:
    return actions.set_row_factor(
        where.company_id, YEAR, where.node_id, rid, factor_id=factor_id, custom=custom, reason=reason, actor=actor
    )


def restore(where: Place, rid: int, line_id: int, *, reason: str | None = None, actor: Actor = CUSTOMER) -> object:
    return actions.restore(where.company_id, YEAR, where.node_id, rid, line_id, reason=reason, actor=actor)


def lines_of(where: Place, rid: int) -> list[HistoryLine]:
    page = actions.row_history(where.company_id, YEAR, where.node_id, rid, offset=0, limit=100)
    assert isinstance(page, HistoryPage), page
    return list(page.lines)


def line_id(where: Place, kind: str, *, after: str | None = None, nth: int = 0) -> int:
    """그 회사의 kind 줄 가운데 nth 번째(오래된 차례)."""
    rows = InventoryEntryHistory.for_company(where.company_id).filter(kind=kind).order_by("id")
    if after is not None:
        rows = rows.filter(after=after)
    return list(rows.values_list("id", flat=True))[nth]


def row_factor(where: Place, rid: int) -> tuple[int | None, int | None]:
    found = InventoryEntryRow.for_company(where.company_id).get(pk=rid)
    return found.factor_version_id, found.custom_factor_id


# ── ⓚ 입력주기 ──────────────────────────────────────────────────────


def test_a_period_change_hides_old_slots_and_switching_back_shows_them(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"), (FEB, "1000"))))
    found = period(here, "quarter")
    assert isinstance(found, IndexDetail), found
    (block,) = found.sites
    assert (block.period, block.slots) == ("quarter", (Q1, Q2, f"{YEAR}-Q3", f"{YEAR}-Q4"))
    assert block.rows[0].values == () and only_row(found)[1:] == (None, None)  # 월 칸은 셈·상세에서 빠진다
    assert found.totals.all[YEAR] is None
    kept = InventoryEntryValue.for_company(here.company_id).order_by("slot").values_list("slot", "amount")
    assert list(kept) == [(JAN, Decimal(1000)), (FEB, Decimal(1000))]  # DB 에는 남는다(판단 E)
    assert history(here.company_id)[-1] == ("period", None, "month", "quarter")
    saved(here, row(here, (Q1, "1000"), row_id=rid))
    assert only_row(detail(here))[1] == Decimal("1.5")
    back = period(here, "month")
    assert isinstance(back, IndexDetail)
    assert [value.slot for value in back.sites[0].rows[0].values] == [JAN, FEB]
    assert only_row(back)[1] == Decimal(3)  # 되바꾸면 옛 월 값이 다시 보이고 셈에 든다
    assert history(here.company_id)[-1] == ("period", None, "quarter", "month")


def test_each_row_of_the_block_gets_a_period_line_and_same_period_changes_nothing(here: Place, leaf: Leaf) -> None:
    mixed = site(here.company_id, leaf.code_id, leaf.code_id, name="나 공장")
    other = Place(**{**here.__dict__, "site_id": mixed, "facility_id": facilities_of(here.company_id, mixed)[0].id})
    second = facilities_of(here.company_id, mixed)[1].id
    saved(other, row(other, (JAN, "1")), row(other, (JAN, "2"), facility=second))
    saved(here, row(here, (JAN, "3")))
    before = len(history(here.company_id))
    assert isinstance(period(other, "year"), IndexDetail)
    lines = history(here.company_id)[before:]
    assert lines == [("period", None, "month", "year")] * 2  # 그 블록의 행마다 — 다른 블록 0
    assert isinstance(period(other, "year"), IndexDetail)
    assert len(history(here.company_id)) == before + 2  # 같은 주기 — 0 바뀜
    stored = InventoryEntryPeriod.for_company(here.company_id).values_list("site_id", "period")
    assert list(stored) == [(mixed, "year")]


def test_a_block_without_rows_keeps_its_period(here: Place) -> None:
    found = period(here, "year")
    assert isinstance(found, IndexDetail) and found.sites[0].slots == (str(YEAR),)
    assert counts(here.company_id) == (0, 0, 0)
    assert saved(here, row(here, (str(YEAR), "1000"))).sites[0].rows[0].emission == Decimal("1.5")


def test_a_save_takes_only_the_slots_of_the_block_period(here: Place) -> None:
    period(here, "quarter")
    before = counts(here.company_id)
    found = save(here, row(here, (Q1, "1"), (JAN, "1")))
    assert isinstance(found, Invalid) and found.fields == {"rows.0.values.1.slot": actions.BAD_SLOT}, found
    assert isinstance(save(here, row(here, (str(YEAR), "1"))), Invalid)
    assert counts(here.company_id) == before


def test_period_refusals(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    there = place(companies[1], leaf)
    no_code = site(here.company_id, pool_leaf(activity("나"), "마 버너").code_id, name="마 공장")
    assert period(here, "week") == Invalid({"period": actions.BAD_PERIOD})
    assert actions.set_period(here.company_id, YEAR, here.node_id, there.site_id, "year", CUSTOMER) == NotFound()
    assert actions.set_period(here.company_id, YEAR, here.node_id, no_code, "year", CUSTOMER) == NotFound()
    set_inventory(here.company_id, [here.site_id], enabled=False)
    assert period(here, "year") == NotFound()
    set_inventory(here.company_id, [here.site_id], enabled=True)
    actions.lock_index(here.company_id, YEAR, here.node_id, CUSTOMER)
    assert period(here, "year") == Locked()
    assert InventoryEntryPeriod.for_company(here.company_id).count() == 0


# ── ⓛ 계수 바꿈 ─────────────────────────────────────────────────────


def test_a_pool_factor_of_the_same_leaf_pins_its_current_version(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    other = second_factor(leaf)
    found = change_factor(here, rid, factor_id=other)
    assert isinstance(found, IndexDetail), found
    assert only_row(found)[1] == Decimal(4)
    version_id = current_version_of(other)
    assert row_factor(here, rid) == (version_id, None)
    (line,) = found.sites[0].rows
    assert isinstance(line.factor, FactorView) and line.factor.name == "계수 나"
    (top, *_) = lines_of(here, rid)
    assert (top.kind, top.reason, top.unit, top.slot, top.before, top.after) == ("factor", WHY, "kg", None, None, None)
    assert top.before_factor == FactorRef(here.version_id, None, "계수 가")
    assert top.after_factor == FactorRef(version_id, None, "계수 나")
    assert (top.actor_kind, top.actor_user_id) == ("admin", OPERATOR_ACTOR.user_id)
    saved(here, row(here, (JAN, "2000"), row_id=rid))
    assert only_row(detail(here))[1] == Decimal(8)  # 저장도 행 판으로 셈(판단 C)


def test_picking_the_selections_factor_clears_the_override(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    change_factor(here, rid, factor_id=second_factor(leaf))
    assert leaf.factor_id is not None
    edit_factor(leaf.factor_id, "계수 가 고침")  # 선택 계수에 새 판 — 선택은 옛 판을 잡고 있다
    found = change_factor(here, rid, factor_id=leaf.factor_id)
    assert isinstance(found, IndexDetail)
    assert row_factor(here, rid) == (None, None)  # 지금 판이 아니라 선택의 잡은 판(판단 C)
    assert only_row(found)[1] == Decimal("1.5") and found.sites[0].rows[0].factor is None
    assert lines_of(here, rid)[0].after_factor == FactorRef(here.version_id, None, "계수 가")
    before = len(history(here.company_id))
    assert isinstance(change_factor(here, rid, factor_id=leaf.factor_id), IndexDetail)
    assert len(history(here.company_id)) == before  # 같은 계수 — 0 바뀜


def test_a_custom_factor_is_the_hand_calc_and_beats_every_version(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    change_factor(here, rid, factor_id=second_factor(leaf))
    found = change_factor(here, rid, custom=custom_draft())
    assert isinstance(found, IndexDetail), found
    assert only_row(found)[1] == Decimal(2)  # 1000 kg × 2 kg/kg — 행 판(4)·선택 판(1.5) 아님
    (custom,) = InventoryCustomFactor.for_company(here.company_id).all()
    assert row_factor(here, rid) == (None, custom.pk)
    assert custom.gases[0] == {"gas": "CO2", "enabled": True, "factor": "2", "gwp": "1"}
    assert (custom.actor_kind, custom.actor_user_id) == ("admin", OPERATOR_ACTOR.user_id)
    (line,) = found.sites[0].rows
    assert isinstance(line.factor, CustomView) and line.factor.is_custom and line.factor.name == "가 직접 계수"
    assert lines_of(here, rid)[0].after_factor == FactorRef(None, custom.pk, "가 직접 계수")


def test_every_factor_refusal_writes_nothing(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    elsewhere = pool_leaf(activity("나"), "바 버너")
    assert elsewhere.factor_id is not None
    before = counts(here.company_id), InventoryCustomFactor.for_company(here.company_id).count()
    cases: list[tuple[dict[str, object], str]] = [
        ({"factor_id": elsewhere.factor_id}, "factorId"),  # 다른 잎
        ({"factor_id": 10**9}, "factorId"),
        ({}, "factorId"),  # 둘 다 없음
        ({"factor_id": leaf.factor_id, "custom": custom_draft()}, "factorId"),  # 둘 다
        ({"factor_id": leaf.factor_id, "reason": ""}, "reason"),
        ({"factor_id": leaf.factor_id, "reason": "   "}, "reason"),
        ({"factor_id": leaf.factor_id, "reason": None}, "reason"),
        ({"factor_id": leaf.factor_id, "reason": "가" * 501}, "reason"),
        ({"custom": custom_draft(emission_unit=("mass", "kgCO2-eq"))}, "custom.emissionUnit"),
        ({"custom": custom_draft(tier=4)}, "custom.tier"),
        (
            {"custom": custom_draft(gases=(GasDraft("CO2", enabled=True, factor="-1", gwp="1"),))},
            "custom.gases.CO2.factor",
        ),
    ]
    for fields, key in cases:
        found = change_factor(here, rid, **fields)  # type: ignore[arg-type]
        assert isinstance(found, Invalid) and key in found.fields, (fields, found)
    assert isinstance(change_factor(here, rid, factor_id=leaf.factor_id, reason="가" * 500), IndexDetail)
    assert (counts(here.company_id), InventoryCustomFactor.for_company(here.company_id).count()) == before
    assert change_factor(here, rid, factor_id=leaf.factor_id, actor=CUSTOMER) == Forbidden(actions.ROW_FACTOR)
    there = place(companies[1], leaf)
    b_rid = entry_row(there).pk
    assert change_factor(here, b_rid, factor_id=leaf.factor_id) == NotFound()  # 남의 회사 행
    actions.delete_rows(here.company_id, YEAR, here.node_id, [rid])
    assert change_factor(here, rid, factor_id=leaf.factor_id) == NotFound()  # 지운 행
    assert (counts(here.company_id)[1:], row_factor(here, rid)) == (before[0][1:], (None, None))


def test_a_locked_index_refuses_factor_changes(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    actions.lock_index(here.company_id, YEAR, here.node_id, CUSTOMER)
    before = counts(here.company_id)
    assert change_factor(here, rid, factor_id=second_factor(leaf)) == Locked()
    assert change_factor(here, rid, custom=custom_draft()) == Locked()
    assert (counts(here.company_id), row_factor(here, rid)) == (before, (None, None))
    assert InventoryCustomFactor.for_company(here.company_id).count() == 0


# ── 548: 직접입력 계수의 행 단위 셈 검사(W12-3 ①) ─────────────────────
# 잎 1차 단위 kg → 행 단위 선택지 kg·g·t(unit-conversions.json 의 g→kg·t→kg). 환산표에 없는 쌍은 셈이 못 한다.


def mismatch_of(found: object) -> dict[str, str]:
    assert isinstance(found, Invalid), found
    return dict(found.fields)


def test_a_custom_input_unit_no_row_unit_converts_to_is_422_input_unit(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    gwh = custom_draft(input_unit=("electricity", "GWh"))  # kg·g·t → GWh 쌍 0 · 분모 GWh = 투입 · kg → t 됨
    assert mismatch_of(change_factor(here, rid, custom=gwh)) == {"custom.inputUnit": CUSTOM_UNIT_MISMATCH}


def test_every_row_unit_must_convert_not_only_the_leafs_first(here: Place) -> None:
    """kg·g → g 는 되지만 t → g 쌍이 없다 — 1차만 보면 지나는 계수(S2)."""
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    grams = custom_draft(input_unit=("mass", "g"), factor_unit="kg/g")
    assert mismatch_of(change_factor(here, rid, custom=grams)) == {"custom.inputUnit": CUSTOM_UNIT_MISMATCH}


def test_a_custom_whose_units_all_convert_passes_even_off_the_leafs_first_unit(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    tonnes = custom_draft(input_unit=("mass", "t"))  # kg·g·t → t 다 됨 · 분모 t · kg → t
    found = change_factor(here, rid, custom=tonnes)
    assert isinstance(found, IndexDetail), found
    assert only_row(found)[1:] == (Decimal("0.002"), None)  # 1000 kg = 1 t × 2 kg/t = 2 kg = 0.002 t
    in_tonnes = saved(here, row(here, (JAN, "3"), unit="t", row_id=rid))
    assert only_row(in_tonnes)[1:] == (Decimal("0.006"), None)  # 2차 단위 행도 셈이 됨


def test_ncv_off_a_denominator_the_input_cannot_reach_is_422_factor_unit(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    per_gram = custom_draft(input_unit=("mass", "t"), factor_unit="kg/g")  # 행 → t 됨 · t → g 쌍 0
    assert mismatch_of(change_factor(here, rid, custom=per_gram)) == {"custom.factorUnit": CUSTOM_UNIT_MISMATCH}


def checked(**fields: object) -> FactorValues:
    found = check_factor(custom_draft(**fields))
    assert isinstance(found, FactorValues), found
    return found


# 지어낸 환산표(순수 시험 — 진짜 표에선 에너지 쌍이 다 이어져 있어 ncvUnit·분자 갈래가 나오지 않는다)
MADE_UP = {("g", "kg"): Decimal("0.001"), ("t", "kg"): Decimal(1000), ("kg", "t"): Decimal("0.001")}


def test_the_pure_check_names_each_field_in_the_calcs_order() -> None:
    rows = ("kg", "g", "t")
    assert custom_unit_problem(rows, checked(input_unit=("mass", "kg")), MADE_UP) == {}
    on = checked(ncv_enabled=True, ncv="2", ncv_unit=("energy", "MJ"), factor_unit="kg/TJ")  # MJ → TJ 쌍 0
    assert custom_unit_problem(rows, on, MADE_UP) == {"custom.ncvUnit": CUSTOM_UNIT_MISMATCH}
    assert custom_unit_problem(rows, on, MADE_UP | {("MJ", "TJ"): Decimal("0.000001")}) == {}
    no_tonnes = {key: value for key, value in MADE_UP.items() if key != ("kg", "t")}
    assert custom_unit_problem(rows, checked(), no_tonnes) == {"custom.factorUnit": CUSTOM_UNIT_MISMATCH}  # 분자 → t
    assert custom_unit_problem(rows, checked(input_unit=("electricity", "GWh")), no_tonnes) == {
        "custom.inputUnit": CUSTOM_UNIT_MISMATCH,
        "custom.factorUnit": CUSTOM_UNIT_MISMATCH,
    }  # 열쇠는 뭉치지 않는다
    assert custom_unit_problem(("kg",), checked(input_unit=("mass", "g"), factor_unit="kg/g"), MADE_UP) == {
        "custom.inputUnit": CUSTOM_UNIT_MISMATCH  # kg → g 쌍도 이 표엔 없다
    }
    assert custom_unit_problem(("g",), checked(input_unit=("mass", "kg")), MADE_UP) == {}  # g → kg 쌍


def liquid_leaf(first_input: str = "L") -> Leaf:
    """잎 단위 L(선택지 L·kL·m3) — 첫 계수가 그 잎의 기본(선택이 잡는 판)이 된다."""
    code_id = code("지어낸 액체 탱크")
    made = pool_actions.create_facility(
        actor_kind=ADMIN, parent_id=activity("다"), facility_code_id=code_id, unit=("volume", "L"), tooltip=""
    )
    assert isinstance(made, FacilityView), made
    return Leaf(id=made.id, code_id=code_id, factor_id=factor(made.id, input_unit=("volume", first_input)).id)


def test_a_pool_factor_off_the_leafs_units_is_422_and_writes_nothing(companies: tuple[int, int]) -> None:
    """558: 548 의 풀 쪽 — 고칠 칸이 없어 키는 factorId 하나, 행·히스토리는 그대로."""
    liquid = liquid_leaf()
    where = place(companies[0], liquid)
    rid, emission_before, _ = only_row(saved(where, row(where, (JAN, "100"), unit="L")))
    assert emission_before is not None
    gas = factor(liquid.id, name="계수 기체", input_unit=("volume", "Nm3"))  # L·kL·m3 → Nm3 쌍 0
    before = counts(where.company_id), row_factor(where, rid)
    assert mismatch_of(change_factor(where, rid, factor_id=gas.id)) == {"factorId": POOL_UNIT_MISMATCH}
    assert (counts(where.company_id), row_factor(where, rid)) == before
    assert only_row(detail(where))[1:] == (emission_before, None)


def test_a_pool_factor_every_row_unit_reaches_still_saves(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    tonnes = factor(leaf.id, name="계수 톤", input_unit=("mass", "t"))  # kg·g·t → t 다 됨 · 분모 t · kg → t
    assert isinstance(change_factor(here, rid, factor_id=tonnes.id), IndexDetail)
    assert only_row(detail(here))[1:] == (Decimal("0.0015"), None)  # 1000 kg = 1 t × 1.5 kg/t = 1.5 kg


def test_a_pool_factor_only_one_row_unit_cannot_reach_is_422(here: Place, leaf: Leaf) -> None:
    """kg 행은 셈이 되지만(kg → g 쌍) 선택지 t → g 쌍이 없다 — 지금 행 단위 하나가 아니라 선택지 전부를 본다."""
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    grams = factor(leaf.id, name="계수 그램", input_unit=("mass", "g"), factor_unit="kg/g")
    assert mismatch_of(change_factor(here, rid, factor_id=grams.id)) == {"factorId": POOL_UNIT_MISMATCH}


def test_the_pool_unit_check_reads_the_factors_current_version(here: Place, leaf: Leaf) -> None:
    """고르면 지금 판을 잡으므로 대조도 지금 판으로 — 첫 판이 맞아도 지금 판이 안 맞으면 거절."""
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    other = factor(leaf.id, name="계수 나")
    edited = pool_actions.save_factor(
        actor_kind=ADMIN, factor_id=other.id, draft=draft(name="계수 나", input_unit=("electricity", "GWh"))
    )
    assert isinstance(edited, FactorView) and edited.version == 2
    assert mismatch_of(change_factor(here, rid, factor_id=other.id)) == {"factorId": POOL_UNIT_MISMATCH}


def test_the_pool_unit_check_comes_before_409_and_a_bad_factor_stays_after_it(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    off = factor(leaf.id, name="계수 전력", input_unit=("electricity", "GWh"))
    fits = second_factor(leaf)
    actions.lock_index(here.company_id, YEAR, here.node_id, CUSTOMER)
    before = counts(here.company_id), row_factor(here, rid)
    assert mismatch_of(change_factor(here, rid, factor_id=off.id)) == {"factorId": POOL_UNIT_MISMATCH}
    assert change_factor(here, rid, factor_id=fits) == Locked()  # 단위가 맞으면 잠김 409
    assert change_factor(here, rid, factor_id=10**9) == Locked()  # 없는 계수의 차례는 그대로 409 뒤
    assert (counts(here.company_id), row_factor(here, rid)) == before


def test_going_back_to_the_pinned_factor_is_not_unit_checked(companies: tuple[int, int]) -> None:
    """C0-2 처분: 되돌리기는 행 덮어쓰기를 풀 뿐이라 잡은 판이 안 맞아도 받는다 — 셈 문제는 그대로 남는다."""
    gassy = liquid_leaf("Nm3")  # 잎의 잡은 판이 안 맞는다
    where = place(companies[0], gassy)
    rid, _, _ = only_row(saved(where, row(where, (JAN, "100"), unit="L")))
    assert only_row(detail(where))[1:] == (None, "unit_conversion_missing")
    fits = factor(gassy.id, name="계수 액체", input_unit=("volume", "L"))
    assert isinstance(change_factor(where, rid, factor_id=fits.id), IndexDetail)
    assert only_row(detail(where))[2] is None
    back = change_factor(where, rid, factor_id=gassy.factor_id)
    assert isinstance(back, IndexDetail), back
    assert row_factor(where, rid) == (None, None)
    assert only_row(back)[1:] == (None, "unit_conversion_missing")


def test_the_unit_check_comes_after_404_and_before_409_and_writes_nothing(
    companies: tuple[int, int], here: Place, leaf: Leaf
) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    gwh = custom_draft(input_unit=("electricity", "GWh"))
    there = place(companies[1], leaf)
    assert change_factor(here, entry_row(there).pk, custom=gwh) == NotFound()  # 남의 행 — 단위 422 보다 앞
    assert isinstance(change_factor(here, rid, custom=gwh, reason=""), Invalid)  # 본문 422 가 먼저
    assert set(mismatch_of(change_factor(here, rid, custom=gwh, reason=""))) == {"reason"}
    actions.lock_index(here.company_id, YEAR, here.node_id, CUSTOMER)
    before = counts(here.company_id), InventoryCustomFactor.for_company(here.company_id).count()
    assert mismatch_of(change_factor(here, rid, custom=gwh)) == {"custom.inputUnit": CUSTOM_UNIT_MISMATCH}
    assert change_factor(here, rid, custom=custom_draft()) == Locked()  # 단위가 맞으면 잠김 409
    assert (counts(here.company_id), InventoryCustomFactor.for_company(here.company_id).count()) == before
    assert row_factor(here, rid) == (None, None)


def test_a_unit_refusal_leaves_rows_customs_and_history_as_they_were(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    change_factor(here, rid, factor_id=second_factor(leaf))
    before = counts(here.company_id), InventoryCustomFactor.for_company(here.company_id).count(), row_factor(here, rid)
    emission = only_row(detail(here))[1]
    assert isinstance(change_factor(here, rid, custom=custom_draft(input_unit=("electricity", "GWh"))), Invalid)
    after = counts(here.company_id), InventoryCustomFactor.for_company(here.company_id).count(), row_factor(here, rid)
    assert after == before and only_row(detail(here))[1] == emission == Decimal(4)


def test_a_row_already_on_a_custom_keeps_it_when_the_next_custom_is_refused(here: Place) -> None:
    """검증 R-a(W12-3 ②): 직접입력 행에 어긋난 직접입력 → 422 · 행의 계수·직접입력 수·히스토리 그대로."""
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    assert isinstance(change_factor(here, rid, custom=custom_draft()), IndexDetail)
    before = counts(here.company_id), InventoryCustomFactor.for_company(here.company_id).count(), row_factor(here, rid)
    gwh = custom_draft(name="나 직접 계수", input_unit=("electricity", "GWh"))
    assert mismatch_of(change_factor(here, rid, custom=gwh)) == {"custom.inputUnit": CUSTOM_UNIT_MISMATCH}
    after = counts(here.company_id), InventoryCustomFactor.for_company(here.company_id).count(), row_factor(here, rid)
    assert after == before and before[2][1] is not None
    assert only_row(detail(here))[1:] == (Decimal(2), None)  # 앞 직접입력(2 kg/kg)으로 셈 그대로


# ── B1: 행이 잡은 풀 계수 지움 ──────────────────────────────────────


def test_a_pool_factor_pinned_by_a_row_cannot_be_deleted(here: Place, leaf: Leaf) -> None:
    """행이 덮어쓴 풀 계수는 지움 409 in_use(4-1). 히스토리 줄만 가리키면 막지 않는다(감독 길 i)."""
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    other = second_factor(leaf)
    change_factor(here, rid, factor_id=other)
    assert pool_actions.delete_factors(actor_kind=ADMIN, ids=[other]) == PoolInUse(frozenset({other}))
    change_factor(here, rid, custom=custom_draft())  # 행은 이제 직접입력 — 히스토리 줄만 other 를 가리킨다
    assert pool_actions.delete_factors(actor_kind=ADMIN, ids=[other]) == 1
    actions.delete_rows(here.company_id, YEAR, here.node_id, [rid])
    third = second_factor(leaf, "5")
    entry = saved(here, row(here, (JAN, "1")))
    change_factor(here, entry.sites[0].rows[0].id, factor_id=third)
    actions.delete_rows(here.company_id, YEAR, here.node_id, [entry.sites[0].rows[0].id])
    assert pool_actions.delete_factors(actor_kind=ADMIN, ids=[third]) == 1  # 지운 행은 안 셈


def test_a_factor_line_of_a_deleted_pool_factor_is_not_restorable(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    other = second_factor(leaf)
    change_factor(here, rid, factor_id=other)
    change_factor(here, rid, custom=custom_draft())
    gone = line_id(here, "factor")
    assert [line.restorable for line in lines_of(here, rid) if line.id == gone] == [True]  # 분모: 지우기 전엔 됨
    assert pool_actions.delete_factors(actor_kind=ADMIN, ids=[other]) == 1
    assert [line.restorable for line in lines_of(here, rid) if line.id == gone] == [False]
    before = counts(here.company_id)
    assert restore(here, rid, gone, reason=WHY, actor=OPERATOR_ACTOR) == RestoreStale()
    assert counts(here.company_id) == before
    assert row_factor(here, rid)[0] is None  # 지운 계수의 판을 행에 다시 잡지 않는다


# ── ⓜ 복구 ──────────────────────────────────────────────────────────


def test_a_value_restore_goes_to_the_lines_after_with_a_new_line(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    saved(here, row(here, (JAN, "2000"), row_id=rid))
    saved(here, row(here, (JAN, "3000"), row_id=rid))
    target = line_id(here, "value", after="2000")
    found = restore(here, rid, target, reason=" 지어낸 까닭 ")
    assert isinstance(found, IndexDetail), found
    assert found.sites[0].rows[0].values[0].amount == Decimal(2000)  # after(2000) — before(1000) 아님(판단 D)
    assert only_row(found)[1] == Decimal(3)
    assert history(here.company_id)[-1] == ("value", JAN, "3000", "2000")
    assert InventoryEntryHistory.for_company(here.company_id).order_by("-id")[0].reason == "지어낸 까닭"
    assert len(history(here.company_id)) == 4  # 지우기 0 — 쌓기만


def test_a_period_restore_and_a_factor_restore_go_to_the_after(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    period(here, "quarter")
    period(here, "year")
    found = restore(here, rid, line_id(here, "period", after="quarter"))
    assert isinstance(found, IndexDetail) and found.sites[0].period == "quarter"
    assert history(here.company_id)[-1] == ("period", None, "year", "quarter")
    other = second_factor(leaf)
    change_factor(here, rid, factor_id=other)
    change_factor(here, rid, custom=custom_draft())
    to_other = line_id(here, "factor", nth=0)
    found = restore(here, rid, to_other, reason=WHY, actor=OPERATOR_ACTOR)
    assert isinstance(found, IndexDetail)
    assert row_factor(here, rid) == (current_version_of(other), None)
    to_custom = line_id(here, "factor", nth=1)
    restore(here, rid, to_custom, reason=WHY, actor=OPERATOR_ACTOR)
    assert row_factor(here, rid)[1] is not None
    (custom_id,) = InventoryCustomFactor.for_company(here.company_id).values_list("id", flat=True)
    assert row_factor(here, rid) == (None, custom_id)  # 같은 직접입력 행(새로 만들지 않음)


def test_a_factor_restore_pins_the_factors_current_version(here: Place, leaf: Leaf) -> None:
    """판단 C(MARC-ENT-517): 줄이 적은 판이 아니라 그 계수의 지금 판 — 복구 사이 풀에서 새 판이 서면 새 판을 잡는다."""
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    other = second_factor(leaf)
    change_factor(here, rid, factor_id=other)
    old_version = current_version_of(other)
    change_factor(here, rid, custom=custom_draft())
    edited = edit_factor(other, "계수 나 고침")  # 새 판(CO2 1.5 — ghg_pool_support.draft)
    assert edited.version == 2 and current_version_of(other) != old_version  # 분모: 판이 둘
    found = restore(here, rid, line_id(here, "factor", nth=0), reason=WHY, actor=OPERATOR_ACTOR)
    assert isinstance(found, IndexDetail), found
    assert row_factor(here, rid) == (current_version_of(other), None)
    assert only_row(found)[1] == Decimal("1.5")  # 새 판(1.5)으로 셈 — 옛 판(4)이면 4
    assert lines_of(here, rid)[0].after_factor == FactorRef(current_version_of(other), None, "계수 나 고침")


def test_restoring_to_the_selections_version_clears_the_override(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    change_factor(here, rid, factor_id=second_factor(leaf))
    assert leaf.factor_id is not None
    change_factor(here, rid, factor_id=leaf.factor_id)  # after = 선택 판
    change_factor(here, rid, custom=custom_draft())
    edit_factor(leaf.factor_id, "계수 가 고침")  # 선택 계수가 새 판을 얻어도 복구는 선택의 잡은 판(None) — 5d 닫힘 1
    back = line_id(here, "factor", nth=1)
    assert isinstance(restore(here, rid, back, reason=WHY, actor=OPERATOR_ACTOR), IndexDetail)
    assert row_factor(here, rid) == (None, None)
    assert only_row(detail(here))[1] == Decimal("1.5")


def test_restore_refusals(companies: tuple[int, int], here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    saved(here, row(here, (JAN, "1000"), na=True, row_id=rid))
    saved(here, row(here, (JAN, "1000"), unit="t", row_id=rid))
    change_factor(here, rid, factor_id=second_factor(leaf))
    saved(here, row(here, (JAN, "2"), unit="t", row_id=rid))
    before = counts(here.company_id)
    assert restore(here, rid, line_id(here, "na_on")) == Invalid({"historyId": actions.NOT_RESTORABLE})
    assert restore(here, rid, line_id(here, "unit")) == Invalid({"historyId": actions.NOT_RESTORABLE})
    top = lines_of(here, rid)[0].id
    assert restore(here, rid, top) == Invalid({"historyId": actions.TOP_LINE})
    factor_line = line_id(here, "factor")
    assert restore(here, rid, factor_line, reason=WHY) == Forbidden(actions.ROW_FACTOR)  # 고객사
    assert restore(here, rid, factor_line, actor=OPERATOR_ACTOR) == Invalid({"reason": actions.NEED_REASON})
    assert isinstance(restore(here, rid, line_id(here, "value"), reason="가" * 501), Invalid)
    assert restore(here, rid, line_id(here, "value")) == RestoreStale()  # kg 줄 — 행은 이제 t
    there = place(companies[1], leaf)
    b_row = entry_row(there)
    b_line = InventoryEntryHistory.for_company(companies[1]).create(
        row_id=b_row.pk, kind="value", slot=JAN, before=None, after="1", unit="kg", actor_kind="service"
    )
    assert restore(here, rid, b_line.pk) == NotFound()  # 남의 회사 줄
    assert restore(here, b_row.pk, b_line.pk) == NotFound()
    assert restore(here, rid, 10**9) == NotFound()
    assert counts(here.company_id) == before


def test_a_line_of_another_row_of_my_company_is_not_found(here: Place, leaf: Leaf) -> None:
    """(5d ③ B2) 같은 회사·같은 잎의 다른 행 R2 의 줄을 R1 경로로 복구 → 404 · 두 행·히스토리 0 바뀜(줄 읽기의 행
    조건)."""
    r1, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    other_site = site(here.company_id, leaf.code_id, name="가 둘째 공장")
    (facility,) = facilities_of(here.company_id, other_site)
    second = save(here, row(here, (JAN, "3000"), facility=facility.id), site_id=other_site)
    assert isinstance(second, IndexDetail), second
    r2 = row_at(second, other_site).id
    saved_again = save(here, row(here, (JAN, "4000"), facility=facility.id, row_id=r2), site_id=other_site)
    assert isinstance(saved_again, IndexDetail), saved_again
    r2_lines = lines_of(here, r2)
    assert [line.after for line in r2_lines] == ["4000", "3000"]  # 분모: R2 의 줄 둘 — 아래 것은 맨 위가 아님
    assert r2_lines[1].restorable is True  # R2 경로라면 복구되는 줄이다
    before = (counts(here.company_id), history(here.company_id), detail(here))
    assert restore(here, r1, r2_lines[1].id) == NotFound()
    assert (counts(here.company_id), history(here.company_id), detail(here)) == before


def test_a_value_line_of_an_old_period_is_stale(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    saved(here, row(here, (JAN, "2000"), row_id=rid))
    period(here, "quarter")
    old = line_id(here, "value", nth=0)
    assert [line.restorable for line in lines_of(here, rid) if line.id == old] == [False]
    assert restore(here, rid, old) == RestoreStale()
    period(here, "month")
    assert isinstance(restore(here, rid, old), IndexDetail)  # 되바꾸면 다시 됨


def test_a_locked_index_refuses_restores(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    saved(here, row(here, (JAN, "2000"), row_id=rid))
    actions.lock_index(here.company_id, YEAR, here.node_id, CUSTOMER)
    first = line_id(here, "value")
    assert [line.restorable for line in lines_of(here, rid)] == [False, False]
    before = counts(here.company_id)
    assert restore(here, rid, first) == Locked()
    assert counts(here.company_id) == before


def test_history_lines_carry_reason_and_restorable(here: Place, leaf: Leaf) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    saved(here, row(here, (JAN, "1000"), na=True, row_id=rid))
    saved(here, row(here, (JAN, "1000"), row_id=rid))
    change_factor(here, rid, factor_id=second_factor(leaf))
    found = [(line.kind, line.restorable, line.reason) for line in lines_of(here, rid)]
    assert found == [
        ("factor", False, WHY),  # 맨 위 줄
        ("na_off", False, None),
        ("na_on", False, None),
        ("value", True, None),
    ]
    assert [line.before_factor is None for line in lines_of(here, rid)] == [False, True, True, True]


# ── 470 M2 · M4 ─────────────────────────────────────────────────────


def test_a_unit_change_writes_a_unit_line_before_the_value_lines(here: Place) -> None:
    rid, _, _ = only_row(saved(here, row(here, (JAN, "1000"))))
    saved(here, row(here, (JAN, "2"), unit="t", row_id=rid))
    assert history(here.company_id)[1:] == [("unit", None, "kg", "t"), ("value", JAN, "1000", "2")]
    unit_line, value_line = InventoryEntryHistory.for_company(here.company_id).order_by("id")[1:]
    assert (unit_line.unit, value_line.unit) == ("t", "t")
    saved(here, row(here, (JAN, "2"), unit="t", row_id=rid))
    assert len(history(here.company_id)) == 3  # 같은 단위 — 0


def test_the_list_estimate_counts_only_enabled_sites_and_block_slots(here: Place, leaf: Leaf) -> None:
    second = site(here.company_id, leaf.code_id, name="나 공장")
    other = Place(**{**here.__dict__, "site_id": second, "facility_id": facilities_of(here.company_id, second)[0].id})
    saved(other, row(other, (JAN, "1"), estimated=True))
    saved(here, row(here, (JAN, "1")))

    def estimated() -> bool:
        found = actions.list_rows(here.company_id, YEAR)
        assert isinstance(found, RowList)
        return found.scopes[0].rows[0].estimated

    assert estimated()  # 분모
    period(other, "quarter")
    assert not estimated()  # 추정 칸이 지금 주기 밖
    period(other, "month")
    assert estimated()
    set_inventory(here.company_id, [second], enabled=False)
    assert not estimated()  # 꺼진 사업장의 행(M4)


def current_version_of(factor_id: int) -> int:
    """계수의 가장 새 판 id(DB 에서 — 시험의 기대값)."""
    found = GhgFactorVersion.objects.filter(factor_id=factor_id).order_by("-version").first()
    assert found is not None, factor_id
    return found.pk
