"""Scope 1·2 입력의 동시성(밴드 S12a ⑤ — 발주서 2-7). 업무 층, 연결 둘, 진짜 커밋.

만드는 법(test_ghg_pool_race.py 꼴): 스레드 둘이 각자의 연결·각자의 transaction.atomic(durable=True) 에서 actions 를
부른다. 한쪽이 잠금을 쥔 자리(또는 판정을 마친 자리)에 사건(Event)을 두고, 다른 쪽은 그 사건 뒤에 출발한다. 먼저 간
쪽은 다른 쪽의 「판정 마침」을 2초까지 기다린다 — 잠금이 있으면 다른 쪽이 잠금에 막혀 오지 않으니 2초 뒤 그대로 가고,
잠금이 없으면(심은 고장 P24~P26) 다른 쪽이 판정을 마쳐 둘이 함께 쓰기로 가 데이터가 깨진다.
  - 잠금 차례: 입력 저장 = 해 → 선택 → 사업장(lock_branch) → 행. 조직구조의 사업장 지움 = lock_branches(id 차례),
    사업장 저장(코드 바꿈) = lock_branch — inventory 행은 읽기만. 잠그기·풀기·지움·메모 = 선택(lock_selection) 만.
  - 교착 0: 시험마다 두 스레드가 30초 안에 끝나고 오류(교착 40P01 포함) 0 을 단언한다.
  - S12a-2 ④(발주서 2-6): 주기 바꿈·계수 바꿈·복구도 해 잠금에서 입력 저장과 줄 선다 — 그래서 그 안의 행 다시 읽기
    (lock_rows)가 지키는 것은 「잠금 전 읽은 행으로 셈·히스토리를 쓰지 않음」이다(P30·P31). 계수 바꿈은 잎(lock_nodes)
    에서 풀 계수 지우기와 줄 서고(P28), 블록의 사업장(lock_branch)에서 조직구조의 지움과 줄 선다(P29).
★ 무효 조건: 스레드 둘 + 연결 둘로 만든 경합이다(gunicorn 일꾼 둘의 요청이 아니다). 기다림 2초는 잠금에 막힌 쪽을
  기다리다 지나가는 것이 정상이다. 이름·값은 지어낸 것이다(실제 회사·계수 0).
"""

import threading
from collections.abc import Callable, Collection
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.db import connections, transaction

from esgapi.inventory.models import (
    CompanyIndexSelection,
    InventoryEntryHistory,
    InventoryEntryPeriod,
    InventoryEntryRow,
)
from esgapi.inventory.service.actions import entries as actions
from esgapi.inventory.service.actions import ghg_pool as pool_actions
from esgapi.inventory.service.actions import index_selection as selection_actions
from esgapi.inventory.service.selectors import entries as selectors
from esgapi.inventory.service.selectors import ghg_pool as pool_selectors
from esgapi.inventory.service.selectors import index_selection as index_selectors
from esgapi.inventory.service.selectors import index_selection as selections
from esgapi.inventory.service.utils.entries import Actor, IndexDetail, RowInput, SlotInput
from esgapi.inventory.service.utils.ghg_pool import GasDraft, Invalid, NotFound
from esgapi.inventory.service.utils.index_selection import SaveResult
from esgapi.inventory.tests.entries_support import Place, place
from esgapi.inventory.tests.ghg_pool_support import ADMIN, activity, factor
from esgapi.inventory.tests.index_selection_support import YEAR, Leaf, pool_leaf
from esgapi.organization.service.actions import branches as branch_actions
from esgapi.organization.service.selectors import branches as branch_selectors
from esgapi.organization.service.services.branches import FacilityRow, InUse

pytestmark = pytest.mark.django_db(transaction=True)

CUSTOMER = Actor("service", 11)
OPERATOR = Actor("admin", 12)
JAN = f"{YEAR}-01"
GRACE = 2  # 먼저 간 쪽이 다른 쪽의 판정을 기다리는 초(잠금이 있으면 그대로 지나간다)


@pytest.fixture
def leaf() -> Leaf:
    return pool_leaf(activity(), "가 보일러")


@pytest.fixture
def here(companies: tuple[int, int], leaf: Leaf) -> Place:
    return place(companies[0], leaf)


def one_row(where: Place, amount: str | None, row_id: int | None = None) -> RowInput:
    return RowInput(
        site_facility_id=where.facility_id,
        unit="kg",
        na=False,
        values=(SlotInput(JAN, amount, False),),
        row_id=row_id,
    )


def save(where: Place, amount: str | None, row_id: int | None = None) -> object:
    return actions.save_rows(
        where.company_id, YEAR, where.node_id, where.site_id, (one_row(where, amount, row_id),), CUSTOMER
    )


def run(calls: dict[str, Callable[[], object]], done: dict[str, threading.Event] | None = None) -> dict[str, object]:
    """이름마다 스레드 하나 — 각자 연결·트랜잭션. 커밋(또는 실패) 뒤 done[이름] 을 세운다. 결과는 이름 → 값/예외."""
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            with transaction.atomic(durable=True):
                result: object = calls[name]()
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다(교착 OperationalError 포함)
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result
        if done is not None and name in done:
            done[name].set()

    threads = [threading.Thread(target=call, args=(name,)) for name in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]  # 교착 0 — 둘 다 끝났다
    assert not [value for value in results.values() if isinstance(value, BaseException)], results
    return results


def hold_after_rows(monkeypatch: pytest.MonkeyPatch, locked: threading.Event, other: threading.Event) -> None:
    """입력 저장이 해·선택·사업장·행 잠금을 쥔 뒤 locked 를 세우고 other(다른 쪽 판정 마침)를 GRACE 초 기다린다."""
    lock_rows = selectors.lock_rows

    def wrapped(company_id: int, selection_id: int, site_id: int) -> list[selectors.RowState]:
        found = lock_rows(company_id, selection_id, site_id)
        locked.set()
        other.wait(timeout=GRACE)
        return found

    monkeypatch.setattr(selectors, "lock_rows", wrapped)


def signal_after(monkeypatch: pytest.MonkeyPatch, target: Any, name: str, checked: threading.Event) -> None:
    """target.<name>(판정 읽기)을 부른 뒤 checked 를 세운다."""
    read: Callable[[int, Collection[int]], frozenset[int]] = getattr(target, name)

    def wrapped(company_id: int, ids: Collection[int]) -> frozenset[int]:
        found = read(company_id, ids)
        checked.set()
        return found

    monkeypatch.setattr(target, name, wrapped)


def dangling_on_deleted_sites() -> int:
    return InventoryEntryRow.unscoped.filter(
        deleted_at__isnull=True, site_facility__site__deleted_at__isnull=False
    ).count()


# ── 입력 저장 대 사업장 지움(e7 조건 ⑤ — 두 차례 겹침) ─────────────────


def test_a_save_holding_the_site_makes_the_delete_wait_and_refuse(monkeypatch: pytest.MonkeyPatch, here: Place) -> None:
    """저장이 먼저 사업장을 잠갔다 → 지움은 lock_branches 에 막혔다가 저장 커밋 뒤 행을 보고 409 in_use.
    지움의 잠금이 없으면(P26) 저장 커밋 전에 판정(행 0)을 마쳐 사업장을 지운다 → 지운 사업장에 살아 있는 행.
    저장의 잠금이 없으면(P24) 지움이 사업장을 먼저 잠가 판정한 뒤 저장이 행을 넣는다 → 같은 깨짐."""
    saving, checked = threading.Event(), threading.Event()
    hold_after_rows(monkeypatch, saving, checked)
    signal_after(monkeypatch, selectors, "sites_in_use", checked)

    def delete() -> object:
        assert saving.wait(timeout=10)
        return branch_actions.delete_branches(here.company_id, [here.site_id])

    results = run({"save": lambda: save(here, "1"), "delete": delete})
    assert isinstance(results["save"], IndexDetail), results
    assert results["delete"] == InUse(frozenset({here.site_id}))
    assert dangling_on_deleted_sites() == 0


def test_a_delete_holding_the_site_makes_the_save_wait_and_miss(monkeypatch: pytest.MonkeyPatch, here: Place) -> None:
    """지움이 먼저 사업장을 잠갔다 → 저장은 lock_branch 에 막혔다가 지움 커밋 뒤 사업장이 없어 404.
    저장의 잠금이 없으면(P24) 지움의 판정(행 0) 뒤 저장이 커밋해 지운 사업장에 살아 있는 행이 남는다."""
    deleting, saved = threading.Event(), threading.Event()
    lock_branches = branch_selectors.lock_branches

    def locked_first(company_id: int, ids: Collection[int]) -> object:
        found = lock_branches(company_id, ids)
        deleting.set()
        return found

    monkeypatch.setattr(branch_selectors, "lock_branches", locked_first)
    sites_in_use = selectors.sites_in_use

    def wait_for_save(company_id: int, ids: Collection[int]) -> frozenset[int]:
        found = sites_in_use(company_id, ids)
        saved.wait(timeout=GRACE)  # 저장이 막혀 있으면 그대로 지나간다
        return found

    monkeypatch.setattr(selectors, "sites_in_use", wait_for_save)

    def save_after() -> object:
        assert deleting.wait(timeout=10)
        return save(here, "1")

    results = run(
        {"delete": lambda: branch_actions.delete_branches(here.company_id, [here.site_id]), "save": save_after},
        done={"save": saved},
    )
    assert results == {"delete": 1, "save": NotFound()}, results
    assert InventoryEntryRow.unscoped.count() == 0
    assert dangling_on_deleted_sites() == 0


# ── 입력 저장 대 코드 바꿈(save_branch) ───────────────────────────────


def test_a_save_holding_the_site_makes_the_recode_wait_and_refuse(
    monkeypatch: pytest.MonkeyPatch, here: Place, leaf: Leaf
) -> None:
    """저장이 먼저 사업장을 잠갔다 → 코드 바꿈은 lock_branch 에 막혔다가 행을 보고 409 in_use. 바뀐 코드에 행 0.
    저장의 잠금이 없으면(P24) 코드 바꿈이 먼저 판정(행 0)·커밋한 뒤 저장이 다른 코드 자산/시설에 행을 넣는다."""
    other_code = pool_leaf(activity("나"), "라 버너").code_id
    saving, checked = threading.Event(), threading.Event()
    hold_after_rows(monkeypatch, saving, checked)
    signal_after(monkeypatch, selectors, "facilities_in_use", checked)

    found = branch_selectors.branch_detail(here.company_id, here.site_id)
    assert found is not None
    seen_at = found.branch.updated_at  # 지금 판(K1b-3) — 입력 저장은 사업장 행을 잠그기만 하고 쓰지 않는다

    def recode() -> object:
        assert saving.wait(timeout=10)
        moved = FacilityRow(other_code, "0호기", id=here.facility_id)
        return branch_actions.save_branch(
            here.company_id, here.site_id, seen_at=seen_at, name="가 공장", inventory_enabled=True, facilities=[moved]
        )

    results = run({"save": lambda: save(here, "1"), "recode": recode})
    assert isinstance(results["save"], IndexDetail), results
    assert results["recode"] == InUse(frozenset({here.facility_id}))
    alive = InventoryEntryRow.unscoped.filter(deleted_at__isnull=True)
    assert alive.count() == 1
    assert alive.exclude(site_facility__facility_code_id=leaf.code_id).count() == 0  # 바뀐 코드에 살아 있는 행 0


# ── 입력 저장 대 S17 저장(그 잎 뺌) ──────────────────────────────────


def test_a_save_before_s17_drops_the_leaf_hides_it(monkeypatch: pytest.MonkeyPatch, here: Place) -> None:
    """저장이 해를 잠근 채 → S17 은 lock_year 에 막혔다가 행을 보고 숨김(삭제 표시 0)."""
    saving, never = threading.Event(), threading.Event()
    hold_after_rows(monkeypatch, saving, never)

    def drop() -> object:
        assert saving.wait(timeout=10)
        return selection_actions.save_selections(here.company_id, YEAR, [], on=date(2026, 10, 29))

    results = run({"save": lambda: save(here, "1"), "drop": drop})
    assert isinstance(results["save"], IndexDetail), results
    assert results["drop"] == SaveResult(selected=0, hidden_with_data=1)
    selection = CompanyIndexSelection.unscoped.get(pk=here.selection_id)
    assert (selection.hidden, selection.deleted_at) == (True, None)
    assert InventoryEntryRow.unscoped.filter(deleted_at__isnull=True).count() == 1


# ── 잠그기 대 입력 저장(P25 를 무는 시험) ──────────────────────────────


def test_no_value_changes_after_the_lock(monkeypatch: pytest.MonkeyPatch, here: Place) -> None:
    """저장이 선택을 잠그고 잠김 판정을 지났다 → 잠그기는 lock_selection 에 막혔다가 저장 커밋 뒤 잠근다.
    선택 잠금이 없으면(P25) 잠그기가 먼저 커밋하고 저장이 그 뒤에 값을 써 잠긴 뒤 바뀐 값이 생긴다."""
    saving, locked = threading.Event(), threading.Event()
    hold_after_rows(monkeypatch, saving, locked)

    def lock() -> object:
        assert saving.wait(timeout=10)
        return actions.lock_index(here.company_id, YEAR, here.node_id, CUSTOMER)

    results = run({"save": lambda: save(here, "1"), "lock": lock}, done={"lock": locked})
    assert isinstance(results["save"], IndexDetail) and isinstance(results["lock"], IndexDetail), results
    selection = CompanyIndexSelection.unscoped.get(pk=here.selection_id)
    assert selection.locked_at is not None
    written = list(InventoryEntryHistory.unscoped.values_list("created_at", flat=True))
    assert len(written) == 1  # 분모: 저장이 값 한 칸을 썼다
    assert [at for at in written if at > selection.locked_at] == []  # 잠긴 뒤 바뀐 값 0


# ── 같은 칸 저장 둘 · 같은 ids 지움 둘 ─────────────────────────────────


def meet_before(monkeypatch: pytest.MonkeyPatch, target: Any, name: str) -> None:
    """target.<name>(잠금) 앞에서 둘이 만난 뒤 잠금으로 간다."""
    barrier = threading.Barrier(2)
    lock: Callable[..., Any] = getattr(target, name)

    def wrapped(*args: Any) -> Any:
        barrier.wait(timeout=10)
        return lock(*args)

    monkeypatch.setattr(target, name, wrapped)


def test_two_saves_of_one_cell_chain_the_history(monkeypatch: pytest.MonkeyPatch, here: Place) -> None:
    """같은 칸 저장 둘 → 해 잠금으로 줄 서 히스토리가 사슬이 된다(뒤 before = 앞 after)."""
    first = save(here, "1")
    assert isinstance(first, IndexDetail), first
    (row,) = first.sites[0].rows
    meet_before(monkeypatch, selections, "lock_year")
    results = run({"ten": lambda: save(here, "10", row.id), "twenty": lambda: save(here, "20", row.id)})
    assert all(isinstance(result, IndexDetail) for result in results.values()), results
    lines = list(InventoryEntryHistory.unscoped.filter(slot=JAN).order_by("id").values_list("before", "after"))
    assert len(lines) == 3, lines  # 분모: 처음 하나 + 둘
    assert all(lines[index][0] == lines[index - 1][1] for index in range(1, 3)), lines


def test_two_deletes_of_the_same_ids_are_200_and_404(monkeypatch: pytest.MonkeyPatch, here: Place) -> None:
    """같은 ids 일괄 지움 둘 → lock_branches 로 줄 서 늦은 쪽은 잠금 아래에서 다시 봐 404."""
    meet_before(monkeypatch, branch_selectors, "lock_branches")
    meet_before(monkeypatch, branch_selectors, "alive_branches")  # 심은 고장(잠그지 않는 읽기)도 같은 자리에서 만난다
    ids = [here.site_id]
    results = run(
        {
            "first": lambda: branch_actions.delete_branches(here.company_id, ids),
            "second": lambda: branch_actions.delete_branches(here.company_id, ids),
        }
    )
    assert sorted(map(repr, results.values())) == sorted([repr(1), repr(branch_actions.NotFound())]), results


# ── S12a-2 ④: 주기 바꿈·계수 바꿈·복구의 동시성(발주서 2-6) ─────────────────────────────

Q1 = f"{YEAR}-Q1"
FEB = f"{YEAR}-02"
WHY = "지어낸 사유"


def first_row(where: Place, amount: str) -> int:
    """그 자리에 1월 값 하나인 행을 저장한다(커밋 — 시험 밖 트랜잭션). 행 id."""
    found = save(where, amount)
    assert isinstance(found, IndexDetail), found
    (row,) = found.sites[0].rows
    return row.id


def second_factor(leaf: Leaf) -> int:
    """같은 잎의 둘째 풀 계수(CO2 4 kg/kg — 지어낸 값). 계수 id."""
    return factor(leaf.id, name="계수 나", gases=(GasDraft("CO2", enabled=True, factor="4", gwp="1"),)).id


def change_factor(where: Place, row_id: int, factor_id: int) -> object:
    return actions.set_row_factor(
        where.company_id, YEAR, where.node_id, row_id, factor_id=factor_id, custom=None, reason=WHY, actor=OPERATOR
    )


def emission(row_id: int) -> object:
    return InventoryEntryRow.unscoped.get(pk=row_id).emission


def chained(row_id: int, slot: str) -> list[tuple[str | None, str | None]]:
    lines = list(
        InventoryEntryHistory.unscoped.filter(row_id=row_id, kind="value", slot=slot)
        .order_by("id")
        .values_list("before", "after")
    )
    assert all(lines[index][0] == lines[index - 1][1] for index in range(1, len(lines))), lines  # 뒤 before = 앞 after
    return lines


def signal_after_read(monkeypatch: pytest.MonkeyPatch, read: threading.Event) -> None:
    """계수 바꿈·복구의 첫 읽기(row_of — 잠그기 전)를 마친 뒤 read 를 세운다."""
    row_of = selectors.row_of

    def wrapped(company_id: int, selection_id: int, row_id: int) -> selectors.RowState | None:
        found = row_of(company_id, selection_id, row_id)
        read.set()
        return found

    monkeypatch.setattr(selectors, "row_of", wrapped)


def test_a_period_change_holding_the_block_makes_the_save_wait_and_refuse_the_old_slot(
    monkeypatch: pytest.MonkeyPatch, here: Place
) -> None:
    """주기 바꿈(월 → 분기)이 먼저 블록을 잡았다 → 월 칸 저장은 해 잠금에 막혔다가 바뀐 주기를 보고 422. 바뀐 뒤 옛 주기
    칸에 쓴 값 0 · 행 배출량 = 분기 칸 셈(없음)."""
    rid = first_row(here, "1000")
    changing, checked = threading.Event(), threading.Event()
    hold_after_rows(monkeypatch, changing, checked)

    def save_after() -> object:
        assert changing.wait(timeout=10)
        return actions.save_rows(
            here.company_id,
            YEAR,
            here.node_id,
            here.site_id,
            (RowInput(here.facility_id, "kg", False, (SlotInput(FEB, "1000", False),), row_id=rid),),
            CUSTOMER,
        )

    results = run(
        {
            "period": lambda: actions.set_period(
                here.company_id, YEAR, here.node_id, here.site_id, "quarter", CUSTOMER
            ),
            "save": save_after,
        },
        done={"save": checked},
    )
    assert isinstance(results["period"], IndexDetail), results
    assert isinstance(results["save"], Invalid), results
    changed_at = InventoryEntryHistory.unscoped.get(kind="period").created_at
    late = InventoryEntryHistory.unscoped.filter(kind="value", created_at__gt=changed_at)
    assert late.count() == 0  # 바뀐 뒤 옛 주기 칸에 쓴 값 0
    assert InventoryEntryPeriod.unscoped.get(selection_id=here.selection_id, site_id=here.site_id).period == "quarter"
    assert emission(rid) is None  # 분기 칸 0 — 셈할 것 없음


def test_a_factor_change_waiting_behind_a_save_figures_with_the_saved_value(
    monkeypatch: pytest.MonkeyPatch, here: Place, leaf: Leaf
) -> None:
    """저장(1000 → 2000)이 블록을 잡은 사이 계수 바꿈이 행을 먼저 읽었다 → 해 잠금에 막혔다가 잠금 아래에서 행을 다시
    읽어 2000 kg × 4 = 8 t. 다시 읽지 않으면(P30 — 잠금 전 읽은 행) 1000 kg × 4 = 4 t 로 낡은 셈을 쓴다."""
    rid = first_row(here, "1000")
    other = second_factor(leaf)
    saving, read = threading.Event(), threading.Event()
    hold_after_rows(monkeypatch, saving, read)
    signal_after_read(monkeypatch, read)

    def change_after() -> object:
        assert saving.wait(timeout=10)
        return change_factor(here, rid, other)

    results = run({"save": lambda: save(here, "2000", rid), "change": change_after})
    assert isinstance(results["save"], IndexDetail) and isinstance(results["change"], IndexDetail), results
    assert emission(rid) == Decimal(8)  # 마지막 계수 × 마지막 값(낡은 셈 0)


def test_a_restore_waiting_behind_a_save_chains_the_history(monkeypatch: pytest.MonkeyPatch, here: Place) -> None:
    """1 → 2 뒤, 저장(→ 3)이 블록을 잡은 사이 복구(첫 줄의 뒤 1)가 행을 먼저 읽었다 → 해 잠금에 막혔다가 잠금 아래에서
    다시 읽어 3 → 1 줄을 쌓는다(사슬). 다시 읽지 않으면(P31) 낡은 2 를 before 로 적어 사슬이 끊긴다."""
    rid = first_row(here, "1")
    assert isinstance(save(here, "2", rid), IndexDetail)
    first_line = InventoryEntryHistory.unscoped.filter(row_id=rid, kind="value").order_by("id").first()
    assert first_line is not None and first_line.after == "1"
    saving, read = threading.Event(), threading.Event()
    hold_after_rows(monkeypatch, saving, read)
    signal_after_read(monkeypatch, read)

    def restore_after() -> object:
        assert saving.wait(timeout=10)
        return actions.restore(here.company_id, YEAR, here.node_id, rid, first_line.pk, reason=None, actor=CUSTOMER)

    results = run({"save": lambda: save(here, "3", rid), "restore": restore_after})
    assert isinstance(results["save"], IndexDetail) and isinstance(results["restore"], IndexDetail), results
    lines = chained(rid, JAN)
    assert [after for _, after in lines] == ["1", "2", "3", "1"], lines  # 분모: 처음·둘째·저장·복구


@pytest.mark.parametrize("kind", ["period", "factor", "restore"])
def test_no_change_after_the_lock_from_a_period_factor_or_restore(
    monkeypatch: pytest.MonkeyPatch, here: Place, leaf: Leaf, kind: str
) -> None:
    """주기 바꿈·계수 바꿈·복구가 선택을 잡았다 → 잠그기는 lock_selection 에 막혔다가 그 커밋 뒤 잠근다.
    잠긴 뒤 바뀜 0."""
    rid = first_row(here, "1")
    assert isinstance(save(here, "2", rid), IndexDetail)
    other = second_factor(leaf)
    first_line = InventoryEntryHistory.unscoped.filter(row_id=rid, kind="value").order_by("id").first()
    assert first_line is not None
    if kind == "period":  # 주기 행을 먼저 둔다 — 첫 INSERT 의 외래키 KEY SHARE 가 선택 잠금을 대신하지 않게(5d B3)
        assert isinstance(
            actions.set_period(here.company_id, YEAR, here.node_id, here.site_id, "year", CUSTOMER), IndexDetail
        )
    calls: dict[str, Callable[[], object]] = {
        "period": lambda: actions.set_period(here.company_id, YEAR, here.node_id, here.site_id, "quarter", CUSTOMER),
        "factor": lambda: change_factor(here, rid, other),
        "restore": lambda: actions.restore(
            here.company_id, YEAR, here.node_id, rid, first_line.pk, reason=None, actor=CUSTOMER
        ),
    }
    writing, locked = threading.Event(), threading.Event()
    hold_after_rows(monkeypatch, writing, locked)
    before = InventoryEntryHistory.unscoped.count()

    def lock() -> object:
        assert writing.wait(timeout=10)
        return actions.lock_index(here.company_id, YEAR, here.node_id, CUSTOMER)

    results = run({"write": calls[kind], "lock": lock}, done={"lock": locked})
    assert isinstance(results["write"], IndexDetail) and isinstance(results["lock"], IndexDetail), results
    selection = CompanyIndexSelection.unscoped.get(pk=here.selection_id)
    assert selection.locked_at is not None
    written = list(InventoryEntryHistory.unscoped.values_list("created_at", flat=True))
    assert len(written) == before + 1  # 분모: 그 쓰기가 줄 하나를 쌓았다
    assert [at for at in written if at > selection.locked_at] == []  # 잠긴 뒤 바뀐 것 0


def test_a_factor_change_racing_the_pool_delete_of_that_factor_leaves_no_row_on_it(
    monkeypatch: pytest.MonkeyPatch, here: Place, leaf: Leaf
) -> None:
    """풀 계수 지우기가 잎을 먼저 잠그고 「쓰이나」(행 0)를 봤다 → 계수 바꿈은 lock_nodes 에 막혔다가 지움 커밋 뒤 그
    계수가 없어 422 — 「지움 200·바꿈 422」. 잎 잠금이 없으면(P28) 바꿈이 지움 커밋 전에 계수의 지금 판을 읽어 행에
    잡고, 지운 계수를 잡은 살아 있는 행이 남는다(B1)."""
    rid = first_row(here, "1000")
    other = second_factor(leaf)
    deleting, read = threading.Event(), threading.Event()
    lock_nodes = pool_selectors.lock_nodes

    def locked_first(ids: Collection[int]) -> object:
        found = lock_nodes(ids)
        deleting.set()  # 첫 부름은 지움이다 — 바꿈은 이 사건 뒤에 출발한다
        return found

    monkeypatch.setattr(pool_selectors, "lock_nodes", locked_first)
    current_version_id = pool_selectors.current_version_id

    def signal_read(factor_id: int, node_id: int) -> int | None:
        found = current_version_id(factor_id, node_id)
        read.set()
        return found

    monkeypatch.setattr(pool_selectors, "current_version_id", signal_read)

    def in_use_then_wait(ids: Collection[int]) -> frozenset[int]:
        found = index_selectors.factors_in_use(ids)
        read.wait(timeout=GRACE)  # 바꿈이 잎 잠금에 막혀 있으면 그대로 지나간다
        return found

    def change_after() -> object:
        assert deleting.wait(timeout=10)
        return change_factor(here, rid, other)

    results = run(
        {
            "delete": lambda: pool_actions.delete_factors(
                actor_kind=ADMIN, ids=[other], factors_in_use=in_use_then_wait
            ),
            "change": change_after,
        }
    )
    assert results == {"delete": 1, "change": Invalid({"factorId": actions.BAD_FACTOR})}, results
    alive = InventoryEntryRow.unscoped.filter(deleted_at__isnull=True)
    assert alive.count() == 1
    assert alive.filter(factor_version__factor__deleted_at__isnull=False).count() == 0  # 지운 계수를 잡은 행 0


def test_a_site_delete_holding_the_site_makes_the_period_change_wait_and_miss(
    monkeypatch: pytest.MonkeyPatch, here: Place
) -> None:
    """행 없는 블록 — 사업장 지움이 먼저 잠갔다 → 주기 바꿈은 lock_branch 에 막혔다가 지움 커밋 뒤 사업장이 없어 404.
    주기 바꿈의 사업장 잠금이 없으면(P29) 지움 커밋 전에 주기를 써 지운 사업장에 주기 줄이 남는다."""
    deleting, changed = threading.Event(), threading.Event()
    lock_branches = branch_selectors.lock_branches

    def locked_first(company_id: int, ids: Collection[int]) -> object:
        found = lock_branches(company_id, ids)
        deleting.set()
        return found

    monkeypatch.setattr(branch_selectors, "lock_branches", locked_first)
    sites_in_use = selectors.sites_in_use

    def wait_for_change(company_id: int, ids: Collection[int]) -> frozenset[int]:
        found = sites_in_use(company_id, ids)
        changed.wait(timeout=GRACE)  # 주기 바꿈이 막혀 있으면 그대로 지나간다
        return found

    monkeypatch.setattr(selectors, "sites_in_use", wait_for_change)

    def period_after() -> object:
        assert deleting.wait(timeout=10)
        return actions.set_period(here.company_id, YEAR, here.node_id, here.site_id, "quarter", CUSTOMER)

    results = run(
        {"delete": lambda: branch_actions.delete_branches(here.company_id, [here.site_id]), "period": period_after},
        done={"period": changed},
    )
    assert results == {"delete": 1, "period": NotFound()}, results
    assert InventoryEntryPeriod.unscoped.filter(site_id=here.site_id).count() == 0  # 지운 사업장에 주기 줄 0
