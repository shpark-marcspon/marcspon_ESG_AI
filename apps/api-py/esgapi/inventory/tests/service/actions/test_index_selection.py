"""고객사 인덱스 선택의 유스케이스(밴드 K1b-2b ② — service/actions/index_selection.py). 업무 층, 주인 역할 연결.

트리 읽기(index_tree)와 저장(save_selections): 해 만들기·잡은 판·뺌(삭제 표시·숨김)·422·회사 둘·0 씀.
회사·사업장·자산/시설은 conftest `companies` 와 organization services 로, 풀은 운영 관리자 actions 로 짓는다.
이름·값은 지어낸 것이다(실제 회사·계수 0).
"""

from collections.abc import Collection
from datetime import date

import pytest
from django.utils import timezone

from esgapi.inventory.models import CompanyIndexSelection, GhgFactor, InventoryYear
from esgapi.inventory.service.actions import entries as entry_actions
from esgapi.inventory.service.actions import ghg_pool as pool_actions
from esgapi.inventory.service.actions import index_selection as actions
from esgapi.inventory.service.selectors import index_selection as selectors
from esgapi.inventory.service.selectors.entries import sites_in_use
from esgapi.inventory.service.services import index_selection as services
from esgapi.inventory.service.utils.entries import IndexDetail
from esgapi.inventory.service.utils.ghg_pool import FacilityView, Invalid
from esgapi.inventory.service.utils.index_selection import MAX_SELECTIONS, IndexTree, SaveResult
from esgapi.inventory.tests.ghg_pool_support import ADMIN, activity, factor, node
from esgapi.inventory.tests.index_selection_support import (
    YEAR,
    current_version,
    edit_factor,
    pool_leaf,
    site,
    two_leaves,
)
from esgapi.organization.service.services.branches import mark_sites_deleted, set_inventory

pytestmark = pytest.mark.django_db

ON = date(2026, 10, 29)


def save(
    company_id: int, ids: list[int], with_data: actions.WithData = selectors.selections_with_data
) -> SaveResult | Invalid:
    return actions.save_selections(company_id, YEAR, ids, on=ON, with_data=with_data)


def saved(company_id: int, ids: list[int], with_data: actions.WithData = selectors.selections_with_data) -> SaveResult:
    result = save(company_id, ids, with_data)
    assert isinstance(result, SaveResult), result
    return result


def rows(company_id: int) -> list[tuple[int, int, bool, bool]]:
    """(잎, 잡은 판, 숨김, 삭제 표시) — 그 회사의 선택 전부, 잎 → id 차례."""
    return [
        (row.facility_node_id, row.factor_version_id, row.hidden, row.deleted_at is not None)
        for row in CompanyIndexSelection.for_company(company_id).order_by("facility_node_id", "id")
    ]


def tree(company_id: int, with_data: actions.WithData = selectors.selections_with_data) -> IndexTree:
    found = actions.index_tree(company_id, YEAR, on=ON, with_data=with_data)
    assert isinstance(found, IndexTree), found
    return found


def leaf_line(found: IndexTree, node_id: int) -> tuple[int, bool, bool | None, bool | None]:
    line = next(line for line in found.nodes if line.id == node_id)
    return line.available_count, line.selected, line.has_factor, line.has_data


# ── 해 ────────────────────────────────────────────────────────────


def test_the_first_save_makes_the_year_and_a_read_does_not(companies: tuple[int, int]) -> None:
    a, _ = companies
    boiler, _ = two_leaves()
    site(a, boiler.code_id)
    tree(a)
    assert InventoryYear.for_company(a).count() == 0  # GET 은 해를 만들지 않는다
    assert saved(a, [boiler.id]) == SaveResult(selected=1, hidden_with_data=0)
    assert [(row.year, row.decimals) for row in InventoryYear.for_company(a)] == [(YEAR, 2)]
    saved(a, [boiler.id])
    assert InventoryYear.for_company(a).count() == 1  # 다시 저장해도 해는 하나


def test_a_year_out_of_range_is_422_on_both(companies: tuple[int, int]) -> None:
    a, _ = companies
    assert actions.index_tree(a, 1989, on=ON) == Invalid({"year": "1990년부터 고를 수 있다"})
    assert actions.save_selections(a, 2027, [], on=ON) == Invalid({"year": "올해보다 뒤의 해는 고를 수 없다"})
    assert InventoryYear.unscoped.count() == 0


def test_a_year_made_by_a_racing_save_is_reused_without_500(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """해 만들기 경합: 먼저 선 행이 있는데 첫 읽기가 못 봤다 → create_year 가 제약에 걸려 YearTaken → 다시 읽어 쓴다."""
    a, _ = companies
    boiler, _ = two_leaves()
    site(a, boiler.code_id)
    services.create_year(a, YEAR)  # 다른 저장이 먼저 세운 행
    real = selectors.year_of
    calls: list[int] = []

    def blind_once(company_id: int, year: int) -> int | None:
        calls.append(year)
        return None if len(calls) == 1 else real(company_id, year)

    monkeypatch.setattr(selectors, "year_of", blind_once)
    assert saved(a, [boiler.id]).selected == 1
    assert len(calls) == 2  # 분모: 첫 읽기가 정말 못 봤고 다시 읽었다
    assert InventoryYear.for_company(a).count() == 1


# ── 잡은 판 ──────────────────────────────────────────────────────────


def test_a_choice_pins_the_default_version_and_keeps_it(companies: tuple[int, int]) -> None:
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    pinned = current_version(boiler.id)
    saved(a, [boiler.id])
    assert boiler.factor_id is not None
    edit_factor(boiler.factor_id, "고친 계수")  # 풀에서 고침 → 새 판
    assert current_version(boiler.id) != pinned  # 분모: 새 판이 정말 섰다
    saved(a, [boiler.id, burner.id])  # 다시 저장
    assert rows(a) == [(boiler.id, pinned, False, False), (burner.id, current_version(burner.id), False, False)]


def test_after_the_default_changes_only_new_choices_take_the_new_default(companies: tuple[int, int]) -> None:
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    saved(a, [boiler.id])
    first = current_version(boiler.id)
    other = factor(boiler.id, name="둘째 계수")
    switched = pool_actions.save_facility(
        actor_kind=ADMIN,
        node_id=boiler.id,
        facility_code_id=boiler.code_id,
        unit=("mass", "kg"),
        tooltip="",
        default_factor_id=other.id,
    )
    assert isinstance(switched, FacilityView), switched
    assert current_version(boiler.id) != first  # 분모: 기본이 바뀌었다
    saved(a, [boiler.id, burner.id])
    assert [version for _, version, _, _ in rows(a)] == [first, current_version(burner.id)]


# ── 뺌 ────────────────────────────────────────────────────────────────


def test_a_dropped_leaf_without_data_is_marked_deleted(companies: tuple[int, int]) -> None:
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    saved(a, [boiler.id, burner.id])
    assert saved(a, [burner.id]) == SaveResult(selected=1, hidden_with_data=0)
    assert [(leaf, hidden, deleted) for leaf, _, hidden, deleted in rows(a)] == [
        (boiler.id, False, True),
        (burner.id, False, False),
    ]
    saved(a, [boiler.id, burner.id])  # 다시 고름 → 새 행(지운 행은 그대로)
    assert [(leaf, deleted) for leaf, _, _, deleted in rows(a)] == [
        (boiler.id, True),
        (boiler.id, False),
        (burner.id, False),
    ]


def test_a_dropped_leaf_with_data_is_hidden_and_comes_back_with_its_version(companies: tuple[int, int]) -> None:
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    saved(a, [boiler.id, burner.id])
    pinned = current_version(boiler.id)
    seen: list[set[int]] = []

    def has_data(company_id: int, year_id: int, node_ids: Collection[int]) -> frozenset[int]:
        seen.append(set(node_ids))
        return frozenset({boiler.id})

    assert saved(a, [burner.id], with_data=has_data) == SaveResult(selected=1, hidden_with_data=1)
    assert seen == [{boiler.id}]  # 뺀 잎만 묻는다
    assert rows(a)[0] == (boiler.id, pinned, True, False)
    assert leaf_line(tree(a, with_data=has_data), boiler.id)[1:] == (False, True, True)  # 숨김 = 안 골라짐·데이터 있음
    assert boiler.factor_id is not None
    edit_factor(boiler.factor_id, "고친 계수")
    assert saved(a, [boiler.id, burner.id]) == SaveResult(selected=2, hidden_with_data=0)
    assert rows(a) == [(boiler.id, pinned, False, False), (burner.id, current_version(burner.id), False, False)]


def test_a_hidden_row_left_out_again_stays_hidden_with_its_version(companies: tuple[int, int]) -> None:
    """뺀 잎 = 숨기지 않은 지금 행 − 요청: 이미 숨긴 행은 다음 저장의 「뺀 잎」 이 아니다(다시 세지도 지우지도 않음)."""
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    saved(a, [boiler.id, burner.id])
    pinned = current_version(boiler.id)

    def has_data(company_id: int, year_id: int, node_ids: Collection[int]) -> frozenset[int]:
        return frozenset({boiler.id}) & frozenset(node_ids)

    assert saved(a, [burner.id], has_data).hidden_with_data == 1  # 분모: 정말 숨겼다
    assert saved(a, [burner.id]) == SaveResult(selected=1, hidden_with_data=0)  # 기본 with_data(입력 행 0)로 다시
    assert rows(a)[0] == (boiler.id, pinned, True, False)  # 숨김 그대로 · 삭제 아님 · 잡은 판 같음


def test_with_data_without_entry_rows_is_empty(companies: tuple[int, int]) -> None:
    """S12a: 입력 행이 없으면 빈 집합(행 있는 잎은 tests/service/selectors/test_entries.py 가 잰다)."""
    a, _ = companies
    assert selectors.selections_with_data(a, 1, [1, 2]) == frozenset()


# ── 422 — 하나라도 걸리면 0 씀(해도 안 만든다) ─────────────────────────


def test_every_refusal_is_422_and_writes_nothing(companies: tuple[int, int]) -> None:
    a, _ = companies
    parent = activity()
    boiler = pool_leaf(parent, "가 보일러")
    bare = pool_leaf(parent, "나 버너", with_factor=False)
    gone = pool_leaf(parent, "라 노")
    assert pool_actions.delete_nodes(actor_kind=ADMIN, ids=[gone.id]) == 1
    site(a, boiler.code_id, bare.code_id, gone.code_id)
    cases = {
        "TOO_MANY": [boiler.id, *range(10**9, 10**9 + MAX_SELECTIONS)],
        "NOT_A_LEAF": [boiler.id, parent],  # 잎 아님
        "NOT_A_LEAF unknown": [boiler.id, 10**9],  # 없는 id
        "NOT_A_LEAF deleted": [boiler.id, gone.id],  # 지운 잎
        "NO_FACTOR": [boiler.id, bare.id],
    }
    for name, ids in cases.items():
        message = getattr(actions, name.split()[0])
        assert save(a, ids) == Invalid({"facilityNodeIds": message}), name
    assert (InventoryYear.unscoped.count(), CompanyIndexSelection.unscoped.count()) == (0, 0)
    assert saved(a, [boiler.id, boiler.id]).selected == 1  # 짝: 바른 요청은 선다(겹친 id 는 걷는다)


def test_a_leaf_without_facilities_is_chosen_and_its_detail_is_empty(companies: tuple[int, int]) -> None:
    """S12-05(MARC-ENT-644): 이 회사에 그 코드의 자산/시설이 없는 잎도 고른다 — 잡은 판은 그때 기본 계수의 지금 판.
    상세는 블록 0(entries 0줄 — 그 코드의 자산/시설이 없는 사업장은 블록에 없다)."""
    a, _ = companies
    parent = activity()
    boiler = pool_leaf(parent, "가 보일러")
    nowhere = pool_leaf(parent, "다 가마")  # 이 회사 시설 없음
    site(a, boiler.code_id)
    assert leaf_line(tree(a), nowhere.id) == (0, False, True, False)  # 분모: 정말 시설 0 · 기본 계수 있음
    assert saved(a, [boiler.id, nowhere.id]) == SaveResult(selected=2, hidden_with_data=0)
    assert rows(a)[1] == (nowhere.id, current_version(nowhere.id), False, False)
    assert leaf_line(tree(a), nowhere.id) == (0, True, True, False)
    assert next(line for line in tree(a).nodes if line.id == parent).selected is True  # 위 단: 시설 0 잎도 셈 안
    found = entry_actions.index_detail(a, YEAR, nowhere.id)
    assert isinstance(found, IndexDetail), found
    assert found.sites == ()  # 블록 0 — 웹이 조직구조 안내를 보인다


def test_an_already_chosen_leaf_passes_without_facilities_or_a_default(companies: tuple[int, int]) -> None:
    """감독 판단 J1: 기본 계수 없음은 새 행이 필요한 잎만 거절한다(시설 0 은 S12-05 로 거절 아님) — 이미 고른 잎은
    잡은 판으로 남는다."""
    a, _ = companies
    boiler, burner = two_leaves()
    plant = site(a, boiler.code_id, burner.code_id)
    saved(a, [boiler.id, burner.id])
    pinned = current_version(boiler.id)
    assert boiler.factor_id is not None
    # 기본 계수 없음 — 잡힌 계수라 delete_factors 는 409(④)라 풀 행을 바로 지운다(검증 R4: 단언의 뜻 그대로)
    GhgFactor.objects.filter(pk=boiler.factor_id).update(is_default=False, deleted_at=timezone.now())
    assert mark_sites_deleted(a, [plant], sites_in_use=sites_in_use) == 1  # 시설 0
    assert leaf_line(tree(a), boiler.id) == (0, True, False, False)  # 분모: 정말 시설 0·계수 없음
    assert saved(a, [boiler.id, burner.id]) == SaveResult(selected=2, hidden_with_data=0)
    assert rows(a)[0] == (boiler.id, pinned, False, False)


def test_a_failure_in_a_later_services_call_leaves_nothing(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    saved(a, [boiler.id])
    before = rows(a)

    def broken(company_id: int, ids: Collection[int]) -> int:
        raise RuntimeError("심은 실패")

    monkeypatch.setattr(services, "mark_selections_deleted", broken)
    with pytest.raises(RuntimeError, match="심은 실패"):
        save(a, [burner.id])  # 새 행 넣기(첫 services) 뒤 삭제 표시(나중 services)에서 깨짐
    assert rows(a) == before


# ── 회사 둘 · 시설 수 ─────────────────────────────────────────────────


def test_one_companys_save_leaves_the_other_alone(companies: tuple[int, int]) -> None:
    a, b = companies
    boiler, burner = two_leaves()
    site(a, boiler.code_id, burner.code_id)
    site(b, boiler.code_id, burner.code_id)
    saved(b, [boiler.id, burner.id])
    before = rows(b)
    assert len(before) == 2  # 분모: B 에 행이 있다
    saved(a, [boiler.id])
    saved(a, [burner.id])
    assert rows(b) == before
    assert [leaf for leaf, _, _, deleted in rows(a) if not deleted] == [burner.id]
    assert leaf_line(tree(b), boiler.id)[1] is True and leaf_line(tree(a), boiler.id)[1] is False


def test_available_count_counts_only_this_companys_alive_inventory_sites(companies: tuple[int, int]) -> None:
    a, b = companies
    boiler, _ = two_leaves()
    site(a, boiler.code_id, boiler.code_id, name="가 공장")  # 같은 코드 둘(세부시설명이 다르다)
    off = site(a, boiler.code_id, name="나 공장")
    dropped = site(a, boiler.code_id, name="다 공장")
    site(b, boiler.code_id, name="남의 공장")
    assert leaf_line(tree(a), boiler.id)[0] == 4  # 분모: 셋 다 셈
    assert set_inventory(a, [off], enabled=False) == 1
    assert mark_sites_deleted(a, [dropped], sites_in_use=sites_in_use) == 1
    assert leaf_line(tree(a), boiler.id) == (2, False, True, False)
    assert leaf_line(tree(b), boiler.id)[0] == 1


def test_the_tree_rolls_up_counts_and_selection(companies: tuple[int, int]) -> None:
    a, _ = companies
    scope = node("scope", "범위 가")
    kind = node("source_type", "유형 가", scope)
    first, second = node("activity", "활동 가", kind), node("activity", "활동 나", kind)
    boiler, burner = pool_leaf(first, "가 보일러"), pool_leaf(second, "나 버너")
    site(a, boiler.code_id, burner.code_id)
    saved(a, [boiler.id])
    lines = {line.id: (line.level, line.available_count, line.selected) for line in tree(a).nodes}
    assert lines == {
        scope: ("scope", 2, False),
        kind: ("source_type", 2, False),
        first: ("activity", 1, True),
        second: ("activity", 1, False),
        boiler.id: ("facility", 1, True),
        burner.id: ("facility", 1, False),
    }
