"""사업장 일괄 토글 대 일괄 지움의 동시성(밴드 S12a-2 ④ — 470 M1 · 발주서 2-5). 업무 층, 연결 둘, 진짜 커밋.

만드는 법(inventory/tests/service/actions/test_entries_race.py 꼴): 스레드 둘이 각자의 연결·각자의 transaction.atomic(
durable=True) 에서 actions 를 부른다. 지움이 lock_branches 를 쥔 뒤 사건을 세우고, 토글은 그 사건 뒤에 출발한다. 지움은
토글의 「있나」 판정(alive_branches)을 2초까지 기다린다 — 토글이 먼저 잠그면(M1) 잠금에 막혀 오지 않으니 2초 뒤 그대로
가고, 잠그지 않으면(심은 고장 P27) 토글이 지움 커밋 전에 판정을 마쳐 지워진 사업장을 200 {count: 0} 으로 「처리」한다.
★ 무효 조건: 스레드 둘 + 연결 둘로 만든 경합이다(gunicorn 일꾼 둘의 요청이 아니다). 이름은 지어낸 것이다.
"""

import threading
from collections.abc import Callable, Collection

import pytest
from django.db import connections, transaction

from esgapi.inventory.service.selectors import entries as entry_selectors
from esgapi.organization.models import Company, Site
from esgapi.organization.service.actions import branches as actions
from esgapi.organization.service.selectors import branches as selectors

pytestmark = pytest.mark.django_db(transaction=True)

GRACE = 2  # 지움이 토글의 판정을 기다리는 초(토글이 잠금에 막혀 있으면 그대로 지나간다)


def run(calls: dict[str, Callable[[], object]]) -> dict[str, object]:
    """이름마다 스레드 하나 — 각자 연결·트랜잭션. 결과는 이름 → 값/예외(교착 40P01 의 OperationalError 포함)."""
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            with transaction.atomic(durable=True):
                result: object = calls[name]()
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result

    threads = [threading.Thread(target=call, args=(name,)) for name in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]  # 교착 0 — 둘 다 끝났다
    assert not [value for value in results.values() if isinstance(value, BaseException)], results  # 500 0
    return results


@pytest.mark.parametrize("enabled", [False, True])
def test_a_toggle_racing_a_delete_of_the_same_ids_waits_and_is_404(
    monkeypatch: pytest.MonkeyPatch, enabled: bool
) -> None:
    """같은 {A,B} 지움이 먼저 잠갔다 → 토글은 lock_branches 에 막혔다가 지움 커밋 뒤 「있나」를 다시 봐 404(지움 200).
    토글의 잠금이 없으면(P27) 지움 커밋 전에 판정을 마치고 지워진 사업장에 UPDATE 0 행 → 200 {count: 0}."""
    company_id = Company.register(name="가 회사", business_licence_number="111-11-11111", subdomain="tenant-a").pk
    ids = [
        Site.for_company(company_id).create(name=name, inventory_enabled=not enabled).pk
        for name in ("가 공장", "나 공장")
    ]
    deleting, checked = threading.Event(), threading.Event()
    lock_branches = selectors.lock_branches

    def locked_first(company_id: int, ids: Collection[int]) -> object:
        found = lock_branches(company_id, ids)
        deleting.set()  # 첫 부름은 지움이다 — 토글은 이 사건 뒤에 출발한다
        return found

    monkeypatch.setattr(selectors, "lock_branches", locked_first)
    alive_branches = selectors.alive_branches

    def signal_checked(company_id: int, ids: Collection[int]) -> object:
        found = alive_branches(company_id, ids)
        checked.set()
        return found

    monkeypatch.setattr(selectors, "alive_branches", signal_checked)
    sites_in_use = entry_selectors.sites_in_use

    def wait_for_toggle(company_id: int, ids: Collection[int]) -> frozenset[int]:
        found = sites_in_use(company_id, ids)
        checked.wait(timeout=GRACE)  # 토글이 잠금에 막혀 있으면 그대로 지나간다
        return found

    monkeypatch.setattr(entry_selectors, "sites_in_use", wait_for_toggle)

    def toggle() -> object:
        assert deleting.wait(timeout=10)
        return actions.set_branches_inventory(company_id, ids, enabled=enabled)

    results = run({"delete": lambda: actions.delete_branches(company_id, ids), "toggle": toggle})
    assert results == {"delete": 2, "toggle": actions.NotFound()}, results
    assert Site.unscoped.filter(pk__in=ids, deleted_at__isnull=False).count() == 2
    assert Site.unscoped.filter(pk__in=ids, inventory_enabled=enabled).count() == 0  # 지워진 사업장을 토글이 고침 0


def test_a_toggle_and_a_delete_meeting_before_the_locks_end_in_one_of_the_two_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """같은 {A,B} 를 거꾸로 적은 토글과 지움이 잠금 앞에서 만난다 → id 차례로 줄 서 「지움 200·토글 404」 또는
    「토글 200·지움 200」(500·교착 0). 응답 갈래는 그대로다."""
    company_id = Company.register(name="나 회사", business_licence_number="222-22-22222", subdomain="tenant-b").pk
    ids = [Site.for_company(company_id).create(name=name).pk for name in ("다 공장", "라 공장")]
    barrier = threading.Barrier(2)
    lock_branches = selectors.lock_branches

    def meet(company_id: int, ids: Collection[int]) -> object:
        barrier.wait(timeout=10)
        return lock_branches(company_id, ids)

    monkeypatch.setattr(selectors, "lock_branches", meet)
    results = run(
        {
            "delete": lambda: actions.delete_branches(company_id, ids),
            "toggle": lambda: actions.set_branches_inventory(company_id, list(reversed(ids)), enabled=False),
        }
    )
    assert results in (
        {"delete": 2, "toggle": actions.NotFound()},
        {"delete": 2, "toggle": 2},
    ), results
    assert Site.unscoped.filter(pk__in=ids, deleted_at__isnull=False).count() == 2
