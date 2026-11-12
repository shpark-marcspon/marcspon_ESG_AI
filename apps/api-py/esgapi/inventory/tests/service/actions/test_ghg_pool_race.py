"""같은 잎에 첫 계수 만들기 둘이 겹칠 때(검증 ② B1): 둘 다 들어가고 기본은 하나다. 업무 층, 연결 둘, 진짜 커밋.

만드는 법(greenwash 의 이름 경합 시험 꼴): 스레드 둘이 각자의 연결·각자의 transaction.atomic(durable=True) 에서
actions.create_factor 를 부른다. 잎 잠금(selectors.lock_nodes) 바로 앞에 장벽을 두어 **둘 다 잠금 앞에 닿은 뒤에야**
잠금으로 간다.
  - 잠금이 있으면: 하나가 잠그고 「첫 계수 = 기본」 으로 넣는다. 다른 하나는 기다렸다가 계수 하나를 보고 기본 아님으로.
  - 잠금이 없으면(심은 고장 P13): 둘 다 「첫 계수」 로 보고 기본으로 넣어 둘째가 23505(one_default_alive) → 갈래.
★ 무효 조건: 스레드 둘 + 연결 둘로 만든 경합이다. gunicorn 일꾼 둘의 요청으로 잰 것이 아니다.
"""

import contextlib
import threading
from collections.abc import Callable, Collection
from datetime import date

import pytest
from django.db import connections, transaction

from esgapi.inventory.models import CompanyIndexSelection, GhgFactor, GhgIndexNode
from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.actions import index_selection as selection_actions
from esgapi.inventory.service.selectors import ghg_pool as selectors
from esgapi.inventory.service.services import ghg_pool as services
from esgapi.inventory.service.utils.ghg_pool import FactorView, InUse, Invalid, NodeInfo, NotFound, SeedRecord
from esgapi.inventory.service.utils.index_selection import SaveResult
from esgapi.inventory.tests.ghg_pool_support import ADMIN, activity, draft, factor, leaf
from esgapi.inventory.tests.index_selection_support import site as add_site
from esgapi.inventory.tests.index_selection_support import two_leaves


@pytest.mark.django_db(transaction=True)
def test_two_first_factors_on_one_leaf_end_with_one_default(monkeypatch: pytest.MonkeyPatch) -> None:
    boiler = leaf(activity(), "가 보일러")
    barrier = threading.Barrier(2)
    lock: Callable[[Collection[int]], dict[int, NodeInfo]] = selectors.lock_nodes

    def wait_then_lock(ids: Collection[int]) -> dict[int, NodeInfo]:
        barrier.wait(timeout=10)
        return lock(ids)

    monkeypatch.setattr(selectors, "lock_nodes", wait_then_lock)
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            with transaction.atomic(durable=True):
                result: object = actions.create_factor(actor_kind=ADMIN, node_id=boiler, draft=draft(name=name))
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result

    threads = [threading.Thread(target=call, args=(name,)) for name in ("계수 하나", "계수 둘")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]
    assert all(isinstance(result, FactorView) for result in results.values()), results
    assert sorted(result.is_default for result in results.values() if isinstance(result, FactorView)) == [False, True]
    assert GhgFactor.objects.filter(facility_node_id=boiler, is_default=True).count() == 1


@pytest.mark.django_db
def test_a_second_default_at_the_table_is_a_refusal_not_a_500() -> None:
    """잠금을 비껴 기본 둘째가 표에 닿아도(경합의 끝 꼴) IntegrityError 가 아니라 갈래다(500 0)."""
    boiler = leaf(activity(), "가 보일러")
    factor(boiler)
    refused = services.insert_factor(
        actor_kind=ADMIN, operation_id="inventory_admin_ghg_factors_create", facility_node_id=boiler, is_default=True
    )
    assert refused == Invalid({"defaultFactorId": services.DEFAULT_RACE})
    assert GhgFactor.objects.filter(facility_node_id=boiler).count() == 1


@pytest.mark.django_db
def test_a_node_deleted_between_the_alive_check_and_the_rename_is_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """K1b-2u L2: 살아 있음을 본 뒤·update 앞에 지워지면(이름 겹침 확인 자리에 끼움) NotFound 이고 이름은 그대로."""
    act = activity()
    taken: Callable[..., bool] = selectors.name_taken

    def delete_then_check(*args: object, **kwargs: object) -> bool:
        GhgIndexNode.objects.filter(pk=act).update(deleted_at="2026-01-01T00:00:00+09:00")
        return taken(*args, **kwargs)

    monkeypatch.setattr(selectors, "name_taken", delete_then_check)
    assert services.rename_node(actor_kind=ADMIN, node_id=act, name="활동 새") == NotFound()
    assert GhgIndexNode.objects.get(pk=act).name == "활동 가"


SEED_RECORDS = {
    "r:co2": SeedRecord("r:co2", "1.5", "kgCO2", "TJ", "CO2"),
    "r:ch4": SeedRecord("r:ch4", "0.5", "kgCH4", "TJ", "CH4"),
    "r:n2o": SeedRecord("r:n2o", "0.25", "kgN2O", "TJ", "N2O"),
    "r:ncv": SeedRecord("r:ncv", "10", "MJ", "kg", "none"),
}
SEED_PLAN = {
    "sources": ["r"],
    "tree": [{"key": "s", "name": "범위 가", "children": [{"key": "k", "name": "유형 가", "children": [
        {"key": "a", "name": "활동 가", "facilities": [{"code": "지어낸 연료", "unit": {"kind": "mass", "unit": "kg"},
         "factors": [{"key": "f", "name": "계수 가", "source": "지어낸 출처", "baseYear": 2024, "tier": 2,
                      "countryCode": "KR", "industryCode": "other", "ncv": "r:ncv",
                      "gases": {"CO2": "r:co2", "CH4": "r:ch4", "N2O": "r:n2o"}}]}]},
    ]}]}],
}  # fmt: skip


@pytest.mark.django_db
def test_a_seed_key_raced_in_by_another_seed_counts_as_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    """K1b-2u L1: 미리 찾은 씨앗 키 목록에 없던 계수가 넣는 순간 이미 있으면(다른 씨앗이 먼저 넣음 — 목록을 비워 흉내)
    seedKey 갈래 → 「이미 있음」 으로 세고 넘어간다(멱등, 건너뜀 0)."""

    def fake_records(source_ids: Collection[str]) -> dict[str, SeedRecord]:
        return dict(SEED_RECORDS)

    def none_seeded(keys: Collection[str]) -> frozenset[str]:
        return frozenset()

    monkeypatch.setattr(actions, "load_seed_records", fake_records)
    first = actions.seed_pool(actor_kind=ADMIN, plan=SEED_PLAN, gwp_set_id="kr-ets-decree-annex2")
    assert isinstance(first, actions.SeedReport) and first.made["factor"] == 1 and not first.skipped
    monkeypatch.setattr(selectors, "seeded_factors", none_seeded)
    again = actions.seed_pool(actor_kind=ADMIN, plan=SEED_PLAN, gwp_set_id="kr-ets-decree-annex2")
    assert isinstance(again, actions.SeedReport)
    assert (again.made["factor"], again.existing["factor"], again.skipped) == (0, 1, [])
    assert GhgFactor.objects.filter(seed_key="s/k/a/지어낸 연료#f").count() == 1


@pytest.mark.django_db
def test_seed_nodes_raced_in_by_another_seed_count_as_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    """K1b-2u R2: 미리 찾은 노드 열쇠 목록에 없던 노드·잎이 만드는 순간 이미 있으면(다른 씨앗이 먼저 넣음 — 첫 찾기만
    비워 흉내) 명령이 멈추지 않고 「이미 있음」 으로 세며, 그 아래로 이어 간다(건너뜀 0)."""

    def fake_records(source_ids: Collection[str]) -> dict[str, SeedRecord]:
        return dict(SEED_RECORDS)

    monkeypatch.setattr(actions, "load_seed_records", fake_records)
    first = actions.seed_pool(actor_kind=ADMIN, plan=SEED_PLAN, gwp_set_id="kr-ets-decree-annex2")
    assert isinstance(first, actions.SeedReport) and not first.skipped
    seeded: Callable[[Collection[str]], dict[str, tuple[int, bool]]] = selectors.seeded_nodes
    calls: list[int] = []

    def blind_first(keys: Collection[str]) -> dict[str, tuple[int, bool]]:
        calls.append(len(keys))
        return {} if len(calls) == 1 else seeded(keys)

    monkeypatch.setattr(selectors, "seeded_nodes", blind_first)
    before = GhgIndexNode.objects.count()
    again = actions.seed_pool(actor_kind=ADMIN, plan=SEED_PLAN, gwp_set_id="kr-ets-decree-annex2")
    assert isinstance(again, actions.SeedReport)
    assert (again.made, again.existing, again.skipped) == (
        {"node": 0, "facility": 0, "factor": 0, "code": 0},
        {"node": 3, "facility": 1, "factor": 1},
        [],
    )
    assert GhgIndexNode.objects.count() == before


@pytest.mark.django_db(transaction=True)
def test_a_company_save_and_an_admin_delete_of_the_same_leaf_end_with_one_side(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    """K1b-2b ⑥(가지 리뷰 M1): 고객사 저장(save_selections)과 운영 관리자 잎 지우기(delete_nodes)가 같은 잎에 겹칠 때.
    둘 다 잎 잠금(selectors.lock_nodes) 앞의 장벽에서 만난 뒤 잠금으로 간다. 잠금 뒤에 짧은 둘째 장벽을 두어 잠금이
    없으면(심은 고장 P26 — 저장의 lock_nodes → alive_nodes) 둘이 함께 판정으로 가게 한다.
      - 잠금이 있으면: 먼저 잠근 쪽만 선다 — 지우기가 먼저면 저장이 422 NOT_A_LEAF, 저장이 먼저면 지우기가 409 in_use.
      - 잠금이 없으면: 둘 다 서고 지운 잎을 가리키는 살아 있는 선택이 남는다.
    ★ 무효 조건: 스레드 둘 + 연결 둘로 만든 경합이다(gunicorn 일꾼 둘의 요청이 아니다). 둘째 장벽은 2초 기다림 —
      잠금에 막힌 쪽을 기다리다 깨지는 것이 정상이다(깨짐은 삼킨다)."""
    a, _ = companies
    boiler, _ = two_leaves()
    add_site(a, boiler.code_id)
    before = threading.Barrier(2)
    after = threading.Barrier(2)

    def meet(
        read: Callable[[Collection[int]], dict[int, NodeInfo]],
    ) -> Callable[[Collection[int]], dict[int, NodeInfo]]:
        def wrapped(ids: Collection[int]) -> dict[int, NodeInfo]:
            before.wait(timeout=10)
            found = read(ids)
            with contextlib.suppress(threading.BrokenBarrierError):  # 다른 쪽이 잠금에 막혀 있다(잠금이 있다는 뜻)
                after.wait(timeout=2)
            return found

        return wrapped

    # 잠금 읽기와 잠그지 않는 읽기 둘 다에 장벽 — 심은 고장(저장이 alive_nodes 로 읽음)도 같은 자리에서 만난다
    monkeypatch.setattr(selectors, "lock_nodes", meet(selectors.lock_nodes))
    monkeypatch.setattr(selectors, "alive_nodes", meet(selectors.alive_nodes))
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            with transaction.atomic(durable=True):
                if name == "save":
                    result: object = selection_actions.save_selections(a, 2025, [boiler.id], on=date(2026, 10, 29))
                else:
                    result = actions.delete_nodes(actor_kind=ADMIN, ids=[boiler.id])
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result

    threads = [threading.Thread(target=call, args=(name,)) for name in ("save", "delete")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]
    saved, deleted = results["save"], results["delete"]
    delete_first = (saved, deleted) == (Invalid({"facilityNodeIds": selection_actions.NOT_A_LEAF}), 1)
    save_first = isinstance(saved, SaveResult) and saved.selected == 1 and deleted == InUse(frozenset({boiler.id}))
    assert delete_first or save_first, results  # 한쪽만 선다
    gone = GhgIndexNode.objects.filter(deleted_at__isnull=False).values_list("id", flat=True)
    dangling = CompanyIndexSelection.unscoped.filter(deleted_at__isnull=True, facility_node_id__in=list(gone))
    assert dangling.count() == 0  # 지운 잎을 가리키는 살아 있는 선택 0
