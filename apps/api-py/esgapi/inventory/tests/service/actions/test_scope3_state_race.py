# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 첫 잠금의 동시성(밴드 S3K2a ① — 발주서 Q8, 감독 처분 차례). 업무 층, 연결 둘, 진짜 커밋.

만드는 법(test_entries_race.py 꼴): 스레드 둘이 각자의 연결·각자의 transaction.atomic(durable=True) 에서 actions.lock 을
부른다. 행이 없을 때 둘 다 「빈 행 두기」에 닿게 한다: 먼저 간 쪽(T1)이 빈 행을 두고 행 잠금을 쥔 뒤 사건을 세우고,
다른 쪽(T2)은 그 사건 뒤에 출발해 lock_row(None) → ensure_row 의 INSERT 가 T1 의 커밋을 기다린다. T1 이 커밋하면 T2 의
INSERT 는 유일 제약에 걸리고(저장점 안이라 그것만 삼킴) 다시 잡은 행은 「이미 잠김」이다.
  - 둘 다 같은 runId: 둘 다 200, 핀 하나, 행 하나, 500 0.
  - T2 가 다른 runId(앞 실행): T2 는 409 stale_run, 핀은 T1 것.
★ 무효 조건: 스레드 둘 + 연결 둘로 만든 경합이다. T1 이 행 잠금을 쥔 채 GRACE 초 기다린다(T2 가 막혀 오지 않음).
값·이름은 지어낸 것이다.
"""

import threading
from collections.abc import Callable

import pytest
from django.db import connections, transaction

from esgapi.inventory.models import Scope3CategoryState
from esgapi.inventory.service.actions import scope3_state as actions
from esgapi.inventory.service.selectors import scope3_state as selectors
from esgapi.inventory.service.utils.entries import Actor
from esgapi.inventory.tests.service.actions.test_scope3_state import done_body, plant, processed

pytestmark = pytest.mark.django_db(transaction=True)

YEAR = 2025
CUSTOMER = Actor("service", 51)
OPERATOR = Actor("admin", 52)
GRACE = 2


def run(calls: dict[str, Callable[[], object]], done: dict[str, threading.Event]) -> dict[str, object]:
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            with transaction.atomic(durable=True):
                result: object = calls[name]()
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다(IntegrityError·교착 포함)
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result
        done[name].set()

    first = threading.Thread(target=call, args=("t1",))
    second = threading.Thread(target=call, args=("t2",))
    first.start()
    second.start()
    for thread in (first, second):
        thread.join(timeout=30)
    assert not [t for t in (first, second) if t.is_alive()]  # 교착 0
    assert not [value for value in results.values() if isinstance(value, BaseException)], results
    return results


def race(monkeypatch: pytest.MonkeyPatch, company_id: int, t1_run: int, t2_run: int) -> dict[str, object]:
    """T1 이 빈 행을 두고 행 잠금을 쥔 뒤 T2 를 출발시킨다. T2 는 행이 없던 때 읽은 것처럼 ensure_row 로 간다."""
    real_lock_row = selectors.lock_row
    t1_holds = threading.Event()
    done = {"t1": threading.Event(), "t2": threading.Event()}
    seen: dict[str, int] = {"t2": 0}

    def lock_row(company: int, year: int, category: str) -> selectors.Row | None:
        name = threading.current_thread().name
        if name == "t2-thread":
            seen["t2"] += 1
            if seen["t2"] == 1:
                return None  # 첫 읽기는 행이 없던 때(경합의 자리) — 곧장 ensure_row 로
        found = real_lock_row(company, year, category)
        if name == "t1-thread" and found is not None:  # 빈 행을 두고 다시 잡은 뒤(행 잠금을 쥔 채)
            t1_holds.set()
            done["t2"].wait(timeout=GRACE)  # 잠금이 있으면 T2 는 막혀 오지 않는다
        return found

    monkeypatch.setattr(selectors, "lock_row", lock_row)

    def t1() -> object:
        threading.current_thread().name = "t1-thread"
        return actions.lock(company_id, YEAR, "C4", t1_run, CUSTOMER)

    def t2() -> object:
        threading.current_thread().name = "t2-thread"
        assert t1_holds.wait(timeout=10)
        return actions.lock(company_id, YEAR, "C4", t2_run, OPERATOR)

    return run({"t1": t1, "t2": t2}, done)


def test_two_first_locks_with_the_same_run_make_one_row_and_one_pin(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a = companies[0]
    current = plant(a, done_body(processed(4, "1")))
    results = race(monkeypatch, a, current, current)
    assert isinstance(results["t1"], actions.CategoryState)
    assert isinstance(results["t2"], actions.CategoryState)
    rows = list(Scope3CategoryState.for_company(a).values_list("category", "pinned_run_id", "locked_by_user_id"))
    assert rows == [("C4", current, CUSTOMER.user_id)]  # 행 하나·핀 하나 — 먼저 건 사람


def test_a_second_first_lock_with_an_older_run_is_stale(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a = companies[0]
    older = plant(a, done_body(processed(4, "1")))
    current = plant(a, done_body(processed(4, "2")))
    results = race(monkeypatch, a, current, older)
    assert isinstance(results["t1"], actions.CategoryState)
    assert isinstance(results["t2"], actions.StaleRun)
    rows = list(Scope3CategoryState.for_company(a).values_list("category", "pinned_run_id"))
    assert rows == [("C4", current)]
