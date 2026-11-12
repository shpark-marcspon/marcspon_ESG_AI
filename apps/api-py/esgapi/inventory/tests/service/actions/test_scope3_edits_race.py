# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 잠그기 ∥ 제외의 동시성(밴드 S3K2b-1 ① — 발주서 Q4·P13). 업무 층, 연결 둘, 진짜 커밋.

test_scope3_state_race.py 꼴: 스레드 둘이 각자의 연결·각자의 transaction.atomic(durable=True) 에서 부른다. 먼저 간
쪽(T1)이 그 (해, 카테고리) 행을 FOR UPDATE 로 쥔 뒤 사건을 세우고 GRACE 초 안에서 T2 를 기다린다 — 잠금이 있으면 T2 는
막혀 오지 않는다. 판정(잠김)이 그 잠금 아래에 있으니 어느 쪽이 먼저든 「잠긴 뒤 사건」은 0 이다.
  - 잠그기 먼저: T2(제외)는 T1 의 커밋 뒤 잠긴 행을 읽어 409 locked · 사건 0.
  - 제외 먼저: T2(잠그기)는 T1 의 커밋 뒤에 잠근다 — 사건은 잠금 앞이다.
★ 무효 조건: 스레드 둘 + 연결 둘로 만든 경합이다. 값·이름은 지어낸 것이다.
"""

import threading

import pytest

from esgapi.inventory.models import Scope3CategoryState, Scope3RowEdit
from esgapi.inventory.service.actions import scope3_edits as edits
from esgapi.inventory.service.actions import scope3_state as state
from esgapi.inventory.service.selectors import scope3_state as selectors
from esgapi.inventory.service.utils.entries import Actor, Locked
from esgapi.inventory.service.utils.scope3_factors import Custom, FactorBody
from esgapi.inventory.tests.service.actions.test_scope3_state import done_body, plant, processed
from esgapi.inventory.tests.service.actions.test_scope3_state_race import GRACE, run

pytestmark = pytest.mark.django_db(transaction=True)

YEAR = 2025
CUSTOMER = Actor("service", 61)
ROW = "가상_C5!20"


def held(monkeypatch: pytest.MonkeyPatch) -> tuple[threading.Event, dict[str, threading.Event]]:
    """T1 이 행을 쥔 뒤 사건을 세우고 T2 를 GRACE 초 기다리게 한다."""
    real = selectors.lock_row
    t1_holds = threading.Event()
    done = {"t1": threading.Event(), "t2": threading.Event()}

    def lock_row(company: int, year: int, category: str) -> selectors.Row | None:
        found = real(company, year, category)
        if threading.current_thread().name == "t1-thread" and found is not None:
            t1_holds.set()
            done["t2"].wait(timeout=GRACE)
        return found

    monkeypatch.setattr(selectors, "lock_row", lock_row)
    return t1_holds, done


def test_a_lock_first_refuses_the_exclude(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a = companies[0]
    current = plant(a, done_body(processed(5, "1", "2")))
    Scope3CategoryState.for_company(a).create(year=YEAR, category="C5")  # 행이 있어야 T1 이 쥔다
    t1_holds, done = held(monkeypatch)

    def t1() -> object:
        threading.current_thread().name = "t1-thread"
        return state.lock(a, YEAR, "C5", current, CUSTOMER)

    def t2() -> object:
        assert t1_holds.wait(timeout=10)
        return edits.exclude(a, current, "C5", [ROW], "가상 사유", CUSTOMER)

    results = run({"t1": t1, "t2": t2}, done)
    assert isinstance(results["t1"], state.CategoryState)
    assert isinstance(results["t2"], Locked)
    assert Scope3RowEdit.for_company(a).count() == 0
    assert list(Scope3CategoryState.for_company(a).values_list("pinned_run_id", flat=True)) == [current]


def test_an_exclude_first_lands_before_the_lock(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a = companies[0]
    current = plant(a, done_body(processed(5, "1", "2")))
    Scope3CategoryState.for_company(a).create(year=YEAR, category="C5")
    t1_holds, done = held(monkeypatch)

    def t1() -> object:
        threading.current_thread().name = "t1-thread"
        return edits.exclude(a, current, "C5", [ROW], "가상 사유", CUSTOMER)

    def t2() -> object:
        assert t1_holds.wait(timeout=10)
        return state.lock(a, YEAR, "C5", current, CUSTOMER)

    results = run({"t1": t1, "t2": t2}, done)
    assert isinstance(results["t1"], edits.EditResult)
    assert isinstance(results["t2"], state.CategoryState)
    event = Scope3RowEdit.for_company(a).get()
    lock = Scope3CategoryState.for_company(a).get()
    assert lock.locked_at is not None and event.created_at <= lock.locked_at  # 사건은 잠금 앞이다


def custom_factor() -> FactorBody:
    return FactorBody(ROW, "custom", None, Custom("가상 계수", "2.0", "가상 출처"), "가상 사유")


def editable_body() -> dict[str, object]:
    row = {
        "rowId": ROW,
        "kind": "purchase",
        "amount": "1000.0",
        "factor": {"title": "가상", "value": "0.5", "unit": "kgCO2e/KRW", "column": "가상 열"},
        "co2e": "0.5",
    }
    return done_body({"sheet": "가상_C5", "category": "Category5", "status": "processed", "rows": [row]})


def test_a_lock_first_refuses_the_factor_edit(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a = companies[0]
    current = plant(a, editable_body())
    Scope3CategoryState.for_company(a).create(year=YEAR, category="C5")
    t1_holds, done = held(monkeypatch)

    def t1() -> object:
        threading.current_thread().name = "t1-thread"
        return state.lock(a, YEAR, "C5", current, CUSTOMER)

    def t2() -> object:
        assert t1_holds.wait(timeout=10)
        return edits.factor(a, current, "C5", custom_factor(), CUSTOMER)

    results = run({"t1": t1, "t2": t2}, done)
    assert isinstance(results["t1"], state.CategoryState)
    assert isinstance(results["t2"], Locked)
    assert Scope3RowEdit.for_company(a).count() == 0


def test_a_factor_edit_first_lands_before_the_lock(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    a = companies[0]
    current = plant(a, editable_body())
    Scope3CategoryState.for_company(a).create(year=YEAR, category="C5")
    t1_holds, done = held(monkeypatch)

    def t1() -> object:
        threading.current_thread().name = "t1-thread"
        return edits.factor(a, current, "C5", custom_factor(), CUSTOMER)

    def t2() -> object:
        assert t1_holds.wait(timeout=10)
        return state.lock(a, YEAR, "C5", current, CUSTOMER)

    results = run({"t1": t1, "t2": t2}, done)
    assert isinstance(results["t1"], edits.EditResult)
    assert isinstance(results["t2"], state.CategoryState)
    assert Scope3RowEdit.for_company(a).count() == 1
