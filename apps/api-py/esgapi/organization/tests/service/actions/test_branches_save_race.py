"""사업장 저장(PUT)의 낡은 판 거절 — 진짜 두 연결(밴드 K1b-3 ② — 발주서 2-4 · sid:MARC-ISSUE-427). 업무 층, 진짜 커밋.

만드는 법(inventory/tests/service/actions/test_entries_race.py 꼴): 스레드마다 각자의 연결·각자의
transaction.atomic(durable=True) 에서 actions 를 부른다.
  - R1 차례를 강제한다: A 는 update_site_row 를 마친 뒤(쓴 뒤·커밋 전) 멈춘다 → B 가 같은 판(v0)으로 출발해
    lock_branch 에서 막힌다 → 지켜보는 스레드가 pg_stat_activity 에서 B 연결의 잠금 기다림
    (wait_event_type = 'Lock')을 본 뒤 A 를 푼다 → A 커밋 → B 는 잠근 행의 새 판을 보고 Stale. 견줌이 잠금 앞
    (잠그지 않는 읽기)이면(심은 고장 P2) B 가 견줌을 지나 잠금 뒤 A 가 더한 줄을 지운다 — 빨강.
  - R2 같은 µs 시계(timezone.now 를 한 값으로 고정): 판이 늘 앞 판 + 1µs 이상이라 낡은 판이 지나지 않는다(P8 빨강).
  - R3 토글 뒤 옛 판으로 저장 → Stale(낡은 inventoryEnabled 로 덮지 않음). 직렬.
★ 무효 조건: 스레드 + 연결 둘(셋 — 지켜보는 쪽)로 만든 경합이다(gunicorn 일꾼 둘의 요청이 아니다). 교착 0: 스레드가
  30초 안에 끝나고 오류 0 을 단언한다. 이름·값은 지어낸 것이다.
"""

import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
from django.db import connection, connections, transaction
from django.utils import timezone

from esgapi.organization.models import FacilityCode, Site, SiteFacility
from esgapi.organization.service.actions import branches as actions
from esgapi.organization.service.services import branches as services
from esgapi.organization.service.services.branches import FacilityRow
from esgapi.organization.service.utils.entities import BranchDetail

pytestmark = pytest.mark.django_db(transaction=True)

WAIT = 10  # 사건·잠금 기다림을 보는 상한(초) — 넘으면 단언이 빨개진다


def run(calls: dict[str, Callable[[], object]]) -> dict[str, object]:
    """이름마다 스레드 하나(스레드 이름 = 이름) — 각자 연결·트랜잭션. 결과는 이름 → 값/예외."""
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

    threads = [threading.Thread(target=call, args=(name,), name=name) for name in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]  # 교착 0 — 다 끝났다
    assert not [value for value in results.values() if isinstance(value, BaseException)], results
    return results


def version(site: Site) -> datetime:
    return Site.unscoped.get(pk=site.pk).updated_at


@pytest.fixture
def plant(companies: tuple[int, int]) -> Site:
    return Site.for_company(companies[0]).create(name="가 공장")


@pytest.fixture
def boiler() -> int:
    return FacilityCode.objects.create(name="보일러", code="F0001").pk


@pytest.mark.parametrize("attempt", range(10))  # 차례를 강제한 채 열 번 — 고장 없는 판에서 늘 초록
def test_two_saves_from_one_version_are_200_and_stale(
    monkeypatch: pytest.MonkeyPatch, plant: Site, boiler: int, attempt: int
) -> None:
    """R1: 같은 판(v0)에서 시작한 저장 둘 — A(줄 X 더함) 200 · B(줄 0) Stale. 끝 상태에 X 있음, 판은 A 의 것."""
    v0 = version(plant)
    a_wrote, release = threading.Event(), threading.Event()
    b_pid: list[int] = []
    update_site_row = services.update_site_row

    def hold_a(*args: Any, **kwargs: Any) -> Any:
        found = update_site_row(*args, **kwargs)
        if threading.current_thread().name == "a":
            a_wrote.set()
            assert release.wait(timeout=WAIT)  # 쓴 뒤·커밋 전에 멈춘다
        return found

    monkeypatch.setattr(services, "update_site_row", hold_a)
    company_id = plant.company_id

    def a() -> object:
        rows = [FacilityRow(boiler, "X")]
        return actions.save_branch(
            company_id, plant.pk, seen_at=v0, name="가 공장", inventory_enabled=True, facilities=rows
        )

    def b() -> object:
        assert a_wrote.wait(timeout=WAIT)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            row = cursor.fetchone()
            assert row is not None
            b_pid.append(int(row[0]))
        return actions.save_branch(
            company_id, plant.pk, seen_at=v0, name="나 공장", inventory_enabled=True, facilities=[]
        )

    def watch() -> bool:
        """B 연결이 잠금을 기다리는 것을 본 뒤 A 를 푼다. 못 보면 WAIT 초 뒤 그대로 풀고 False."""
        seen = False
        deadline = time.monotonic() + WAIT
        with connection.cursor() as cursor:
            while time.monotonic() < deadline and not seen:
                if b_pid:
                    cursor.execute("SELECT pg_stat_clear_snapshot()")  # 트랜잭션 안의 통계 사진을 버린다
                    cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [b_pid[0]])
                    row = cursor.fetchone()
                    seen = row is not None and row[0] == "Lock"
                if not seen:
                    time.sleep(0.02)
        release.set()
        return seen

    results = run({"a": a, "b": b, "watch": watch})
    assert results["watch"] is True, results  # B 는 정말 잠금에서 기다렸다(차례가 강제됐다)
    saved = results["a"]
    assert isinstance(saved, BranchDetail), results
    assert results["b"] == actions.Stale(), results
    alive = list(
        SiteFacility.unscoped.filter(site_id=plant.pk, deleted_at__isnull=True).values_list("detail_name", flat=True)
    )
    assert alive == ["X"]  # B 가 A 의 줄을 지우지 않았다(lost update 0)
    stored = Site.unscoped.get(pk=plant.pk)
    assert (stored.name, stored.updated_at) == ("가 공장", saved.branch.updated_at)  # 판은 A 의 것


def test_the_same_microsecond_still_moves_the_version(monkeypatch: pytest.MonkeyPatch, plant: Site) -> None:
    """R2: 시계가 늘 같은 값을 내도 판은 앞 판 + 1µs — 1(v0) 200 → 2(v0) Stale · 1 의 판으로 3 200 →
    3 의 앞 판으로 4 Stale."""
    v0 = version(plant)
    monkeypatch.setattr(timezone, "now", lambda: v0)  # 저장마다 같은 µs
    company_id = plant.company_id

    def save(seen_at: datetime, name: str) -> object:
        return actions.save_branch(
            company_id, plant.pk, seen_at=seen_at, name=name, inventory_enabled=True, facilities=[]
        )

    first = save(v0, "하나")
    assert isinstance(first, BranchDetail), first
    v1 = first.branch.updated_at
    assert v1 > v0
    assert save(v0, "둘") == actions.Stale()
    third = save(v1, "셋")
    assert isinstance(third, BranchDetail), third
    assert third.branch.updated_at > v1
    assert save(v1, "넷") == actions.Stale()
    assert Site.unscoped.get(pk=plant.pk).name == "셋"


def test_a_toggle_after_the_read_refuses_the_old_version(plant: Site) -> None:
    """R3: 읽은 뒤 인벤토리 토글 → 옛 판의 저장은 Stale, 토글 값 그대로(낡은 inventoryEnabled 로 덮지 않음)."""
    v0 = version(plant)
    assert actions.set_branches_inventory(plant.company_id, [plant.pk], enabled=False) == 1
    found = actions.save_branch(
        plant.company_id, plant.pk, seen_at=v0, name="가 공장", inventory_enabled=True, facilities=[]
    )
    assert found == actions.Stale()
    assert Site.unscoped.get(pk=plant.pk).inventory_enabled is False
