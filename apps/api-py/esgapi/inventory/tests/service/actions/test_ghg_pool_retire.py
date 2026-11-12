"""옛 씨앗 지우기 ⓖ retire_seed 와 명령 retire_ghg_seed(밴드 S12S1 ② — 결정 MARC-ENT-676). 업무 층, 주인 역할 연결.

지어낸 옛 계획(활동 하나 아래 연료 잎 둘)을 씨앗으로 넣고, 새 계획(연료 = 활동, 그 아래 설비 잎)의 retired 로 센다.
기본 = 셈만(쓰기 0) · 셈이 전부 0 이면 --apply 가 옛 잎·활동·계수·코드를 삭제 표시(범위·유형은 살림) ·
두 번째는 nothing ·
쓰는 선택·잡은 판·덮어쓴 행·씨앗 밖 자식·씨앗 아닌 계수·고친 씨앗 계수·사업장이 쓰는 지울 코드 → 각각 blocked·지움 0.
회사 정보는 셈 줄에 0(수만). 이름·값은 지어낸 것이다(실제 계수·기업 0).
"""

import contextlib
import copy
import io
import json
import threading
from collections.abc import Callable, Collection
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections, transaction

from esgapi.inventory.models import CompanyIndexSelection, GhgFactor, GhgIndexNode
from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.actions import index_selection as selection_actions
from esgapi.inventory.service.selectors import ghg_pool as selectors
from esgapi.inventory.service.selectors.index_selection import factors_in_use as factors_in_use_of_pool
from esgapi.inventory.service.selectors.index_selection import nodes_in_use as nodes_in_use_of_pool
from esgapi.inventory.service.utils.ghg_pool import FacilityView, InUse, Invalid, NodeInfo, SeedRecord
from esgapi.inventory.service.utils.index_selection import SaveResult
from esgapi.inventory.tests.ghg_pool_support import ADMIN, CUSTOMER, code, counts, factor
from esgapi.inventory.tests.index_selection_support import YEAR, edit_factor
from esgapi.inventory.tests.index_selection_support import site as add_site
from esgapi.organization.service.selectors.facility_codes import codes_on_site_facilities, selectable_codes

pytestmark = pytest.mark.django_db

ON = date(2026, 10, 29)
RECORDS = {
    "s:co2-l": SeedRecord("s:co2-l", "1,234.5", "kgCO2", "L", "CO2"),
    "s:ch4-l": SeedRecord("s:ch4-l", "2.5", "kgCH4", "L", "CH4"),
    "s:n2o-l": SeedRecord("s:n2o-l", "0.25", "kgN2O", "L", "N2O"),
}
GASES = {"CO2": "s:co2-l", "CH4": "s:ch4-l", "N2O": "s:n2o-l"}
FUELS = ("지어낸 연료 가", "지어낸 연료 나")
EQUIPMENT = "지어낸 설비"


def group() -> dict[str, Any]:
    return {
        "key": "g",
        "name": "지어낸 묶음",
        "source": "지어낸 출처",
        "baseYear": 2024,
        "baseYearBasis": "지어냄",
        "tier": 2,
        "countryCode": "KR",
        "industryCode": "other",
        "gases": GASES,
    }


def leaf(code: str) -> dict[str, Any]:
    return {"code": code, "unit": {"kind": "volume", "unit": "L"}, "factors": [group()]}


def tree(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"key": "s1", "name": "범위 가", "children": [{"key": "k", "name": "유형 가", "children": activities}]},
    ]


# 옛 계획: 활동 하나 아래 연료 잎 둘(옛 씨앗 꼴) · 새 계획: 연료 = 활동, 그 아래 설비 잎 하나(새 꼴) + retired
OLD: dict[str, Any] = {
    "sources": ["s"],
    "tree": tree([{"key": "old", "name": "지어낸 옛 활동", "facilities": [leaf(fuel) for fuel in FUELS]}]),
}
RETIRED = ["s1/k/old", *(f"s1/k/old/{fuel}" for fuel in FUELS)]
NEW: dict[str, Any] = {
    "sources": ["s"],
    "tree": tree(
        [{"key": f"fuel{index}", "name": fuel, "facilities": [leaf(EQUIPMENT)]} for index, fuel in enumerate(FUELS)]
    ),
    "retired": RETIRED,
}
SET = "kr-ets-decree-annex2"


@pytest.fixture(autouse=True)
def fake_records(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(source_ids: list[str]) -> dict[str, SeedRecord]:
        return dict(RECORDS)

    monkeypatch.setattr(actions, "load_seed_records", fake)


def seed(plan: dict[str, Any]) -> actions.SeedReport:
    report = actions.seed_pool(actor_kind=ADMIN, plan=plan, gwp_set_id=SET)
    assert isinstance(report, actions.SeedReport), report
    return report


def retire(plan: dict[str, Any] = NEW, **fields: Any) -> actions.RetireReport:
    report = actions.retire_seed(
        actor_kind=fields.pop("actor_kind", ADMIN), plan=plan, codes_on_sites=codes_on_site_facilities, **fields
    )
    assert isinstance(report, actions.RetireReport), report
    return report


def node(key: str) -> GhgIndexNode:
    return GhgIndexNode.objects.get(seed_key=key)


def old_leaf_ids() -> list[int]:
    return [node(key).pk for key in RETIRED[1:]]


def old_code_ids() -> list[int]:
    rows = GhgIndexNode.objects.filter(pk__in=old_leaf_ids()).order_by("id").values_list("facility_code_id", flat=True)
    return [code_id for code_id in rows if code_id is not None]


def alive_code_names() -> list[str]:
    return [code.name for code in selectable_codes()]


def choose(company_id: int, *leaf_ids: int) -> None:
    saved = selection_actions.save_selections(company_id, YEAR, list(leaf_ids), on=ON)
    assert isinstance(saved, SaveResult) and saved.selected == len(leaf_ids), saved


def test_counting_alone_writes_nothing() -> None:
    seed(OLD)
    before = (counts(), alive_code_names())
    report = retire()
    assert (report.alive, report.gone, report.codes, report.blockers, report.state) == (3, 0, 2, 0, "ready")
    assert (counts(), alive_code_names()) == before
    assert GhgIndexNode.objects.filter(deleted_at__isnull=False).count() == 0


def test_apply_marks_the_old_nodes_factors_and_codes_and_keeps_the_scope_and_kind() -> None:
    seed(OLD)
    report = retire(apply=True)
    assert (report.state, report.deleted_nodes, report.deleted_codes) == ("done", 3, 2)
    assert all(node(key).deleted_at is not None for key in RETIRED)
    assert GhgFactor.objects.filter(facility_node_id__in=old_leaf_ids(), deleted_at__isnull=True).count() == 0
    assert node("s1").deleted_at is None and node("s1/k").deleted_at is None  # 범위·유형은 살림
    assert set(FUELS) & set(alive_code_names()) == set()  # 옛 코드 삭제 표시
    again = retire(apply=True)
    assert (again.state, again.alive, again.gone, again.codes) == ("nothing", 0, 3, 0)  # 두 번째 = nothing


def test_the_new_seed_after_retiring_makes_only_new_leaves_and_never_revives_the_old() -> None:
    seed(OLD)
    retire(apply=True)
    made = seed(NEW)
    assert (made.made["facility"], made.made["factor"], made.made["code"]) == (2, 2, 1)  # 설비 코드 하나를 둘이 같이
    assert made.skipped == []
    replay = seed(OLD)  # 옛 계획을 다시 돌려도 R9 로 되살아나지 않는다
    assert replay.skipped == [("s1/k/old", actions.DELETED_SEED_NODE)]
    assert all(node(key).deleted_at is not None for key in RETIRED)
    assert retire().state == "nothing"


def test_a_partly_deleted_old_seed_passes_only_the_alive_ones() -> None:
    seed(OLD)
    first = old_leaf_ids()[0]
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[first]) == 1
    report = retire(apply=True)
    assert (report.alive, report.gone, report.deleted_nodes, report.state) == (2, 1, 2, "done")  # 404 0


def test_a_chosen_old_leaf_blocks_and_nothing_is_deleted(companies: tuple[int, int]) -> None:
    a, _ = companies
    seed(OLD)
    add_site(a, old_code_ids()[0])
    choose(a, old_leaf_ids()[0])
    before = (counts(), alive_code_names())
    report = retire(apply=True)
    # 잎을 고르면 기본 계수 판을 잡는다(쓰는 잎 1 · 잡힌 계수 1) · 그 잎 코드를 사업장이 쓴다(1)
    assert (report.leaves_in_use, report.factors_in_use, report.codes_on_sites, report.state) == (1, 1, 1, "blocked")
    assert (report.deleted_nodes, report.deleted_codes) == (0, 0)
    assert (counts(), alive_code_names()) == before
    assert GhgIndexNode.objects.filter(deleted_at__isnull=False).count() == 0


def test_a_site_facility_on_an_old_code_alone_blocks(companies: tuple[int, int]) -> None:
    """덧 2: 회사가 옛 잎을 안 골라도 사업장 자산/시설이 지울 옛 코드를 쓰면 blocked · 노드·코드 지움 0."""
    _, b = companies
    seed(OLD)
    add_site(b, old_code_ids()[1])
    report = retire(apply=True)
    assert (report.blockers, report.codes_on_sites, report.state) == (1, 1, "blocked")
    assert GhgIndexNode.objects.filter(deleted_at__isnull=False).count() == 0
    assert set(FUELS) <= set(alive_code_names())


def test_a_row_override_on_an_old_factor_blocks() -> None:
    """입력 행이 덮어쓴 판(factors_in_use 의 InventoryEntryRow 몫)도 막는다 — 판정 자리에 지어낸 쓰임을 넘긴다."""
    seed(OLD)
    pinned = GhgFactor.objects.filter(facility_node_id=old_leaf_ids()[0]).values_list("id", flat=True).first()
    assert pinned is not None

    def overridden(ids: Collection[int]) -> frozenset[int]:
        return frozenset({pinned}) & frozenset(ids)

    report = retire(apply=True, factors_in_use=overridden)
    assert (report.factors_in_use, report.state, report.deleted_nodes) == (1, "blocked", 0)


def test_an_admin_leaf_under_an_old_activity_blocks() -> None:
    seed(OLD)
    made = actions.create_facility(
        actor_kind=ADMIN,
        parent_id=node("s1/k/old").pk,
        facility_code_id=code("지어낸 관리자 설비"),
        unit=("volume", "L"),
        tooltip="",
    )
    assert isinstance(made, FacilityView), made
    report = retire(apply=True)
    assert (report.foreign_children, report.state, report.deleted_nodes) == (1, "blocked", 0)


def test_an_admin_factor_on_an_old_leaf_blocks() -> None:
    seed(OLD)
    factor(old_leaf_ids()[0], name="지어낸 관리자 계수")
    report = retire(apply=True)
    assert (report.foreign_factors, report.state, report.deleted_nodes) == (1, "blocked", 0)


def test_an_edited_seed_factor_blocks() -> None:
    seed(OLD)
    seeded = GhgFactor.objects.get(seed_key=f"s1/k/old/{FUELS[1]}#g")
    edit_factor(seeded.pk, "지어낸 고친 이름")
    report = retire(apply=True)
    assert (report.edited_factors, report.state, report.deleted_nodes) == (1, "blocked", 0)
    assert GhgFactor.objects.get(pk=seeded.pk).deleted_at is None  # 고친 것이 남는다


def test_an_old_code_used_by_another_leaf_is_kept_and_does_not_block(companies: tuple[int, int]) -> None:
    """다른 살아 있는 잎이 쓰는 옛 코드는 지우지 않고 상태도 바꾸지 않는다 — 그 코드의 사업장 행도 막지 않는다."""
    a, _ = companies
    seed(OLD)
    seed(NEW)
    kept = old_code_ids()[0]
    other = actions.create_facility(
        actor_kind=ADMIN, parent_id=node("s1/k/fuel0").pk, facility_code_id=kept, unit=("volume", "L"), tooltip=""
    )
    assert isinstance(other, FacilityView), other
    add_site(a, kept)
    report = retire(apply=True)
    assert (report.codes_on_leaves, report.codes, report.codes_on_sites) == (1, 1, 0)
    assert (report.state, report.deleted_nodes, report.deleted_codes) == ("done", 3, 1)
    assert FUELS[0] in alive_code_names() and FUELS[1] not in alive_code_names()


def test_a_customer_kind_cannot_retire_and_a_plan_without_retired_is_invalid() -> None:
    seed(OLD)
    refused = actions.retire_seed(actor_kind=CUSTOMER, plan=NEW, codes_on_sites=codes_on_site_facilities)
    assert refused == actions.Forbidden("inventory_admin_ghg_nodes_delete")
    bad: list[dict[str, Any]] = [OLD, {**NEW, "retired": []}, {**NEW, "retired": ["s1/k/old", 1]}]
    for plan in bad:
        assert isinstance(
            actions.retire_seed(actor_kind=ADMIN, plan=plan, codes_on_sites=codes_on_site_facilities), Invalid
        )
    assert GhgIndexNode.objects.filter(deleted_at__isnull=False).count() == 0


def run(*args: str, plan: dict[str, Any], tmp_path: Path) -> str:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    out = io.StringIO()
    call_command("retire_ghg_seed", "--plan", str(path), *args, stdout=out)
    return out.getvalue()


def test_the_command_counts_by_default_and_applies_only_when_asked(tmp_path: Path) -> None:
    seed(OLD)
    before = counts()
    counted = run(plan=NEW, tmp_path=tmp_path)
    assert counted.splitlines()[-1] == "RETIRE=ready" and counts() == before
    applied = run("--apply", plan=NEW, tmp_path=tmp_path)
    assert applied.splitlines()[-1] == "RETIRE=done" and "지움 노드 3 · 코드 2" in applied
    assert run("--apply", plan=NEW, tmp_path=tmp_path).splitlines()[-1] == "RETIRE=nothing"


def test_the_command_stops_on_blocked_apply_and_prints_numbers_only(tmp_path: Path, companies: tuple[int, int]) -> None:
    a, b = companies
    seed(OLD)
    add_site(a, old_code_ids()[0])
    choose(a, old_leaf_ids()[0])
    out = io.StringIO()
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(NEW, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(CommandError, match="지움 0"):
        call_command("retire_ghg_seed", "--plan", str(path), "--apply", stdout=out)
    text = out.getvalue()
    assert text.splitlines()[-1] == "RETIRE=blocked"
    assert "막음 회사 선택이 고른 옛 잎(숨김 포함) 1" in text
    assert GhgIndexNode.objects.filter(deleted_at__isnull=False).count() == 0
    # 회사 정보 0: 회사 이름 칸 없음 · 숫자는 셈뿐(회사 id 를 크게 띄워 셈 수와 겹치지 않게 본다)
    assert all(word not in text for word in ("company", "회사 id", f"={a}", f"={b}"))
    numbers = {int(token) for token in text.replace("·", " ").split() if token.isdigit()}
    assert numbers <= {0, 1, 2, 3}, text


def test_the_packaged_seed_file_has_retired_keys_the_command_reads() -> None:
    """패키지 씨앗(먼저 그 옛 꼴을 넣지 않음)에 셈만 → nothing(옛 노드 0) · 쓰기 0."""
    out = io.StringIO()
    call_command("retire_ghg_seed", stdout=out)
    assert out.getvalue().splitlines()[-1] == "RETIRE=nothing"
    assert counts() == (0, 0, 0, 0)


@pytest.mark.django_db(transaction=True)
def test_a_company_save_and_an_apply_on_the_same_old_leaf_end_with_one_side(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    """고객사 저장(save_selections)과 --apply 가 같은 옛 잎에 겹칠 때 — 둘 다 노드 잠금 앞의 장벽에서 만난 뒤 잠금으로.
    지우기가 먼저면 저장이 422 NOT_A_LEAF, 저장이 먼저면 지우기가 blocked(지움 0). ★ 스레드 둘 + 연결 둘의 경합이다.
    ★ 실제로는 늘 저장이 먼저 잠근다(검증 권고 — 셈이 저장보다 길다). 그래서 잠금 차례는 아래 부른 차례 시험이 문다."""
    a, _ = companies
    seed(OLD)
    target = old_leaf_ids()[0]  # 사업장 행 0 — 있으면 지울 옛 코드를 사업장이 써 늘 blocked(지우기 먼저 갈래에 못 닿음)
    before = threading.Barrier(2)
    seen = threading.local()
    lock: Callable[[Collection[int]], dict[int, NodeInfo]] = selectors.lock_nodes

    def meet(ids: Collection[int]) -> dict[int, NodeInfo]:
        if not getattr(seen, "met", False):  # 스레드마다 첫 잠금에서만 만난다(지우기는 잠금을 두 번 부른다)
            seen.met = True
            with contextlib.suppress(threading.BrokenBarrierError):
                before.wait(timeout=10)
        return lock(ids)

    monkeypatch.setattr(selectors, "lock_nodes", meet)
    results: dict[str, object] = {}
    guard = threading.Lock()

    def call(name: str) -> None:
        try:
            with transaction.atomic(durable=True):
                if name == "save":
                    result: object = selection_actions.save_selections(a, YEAR, [target], on=ON)
                else:
                    result = actions.retire_seed(
                        actor_kind=ADMIN, plan=NEW, apply=True, codes_on_sites=codes_on_site_facilities
                    )
        except BaseException as err:  # 스레드 밖으로 넘겨 단언한다
            result = err
        finally:
            connections.close_all()
        with guard:
            results[name] = result

    threads = [threading.Thread(target=call, args=(name,)) for name in ("save", "retire")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not [thread for thread in threads if thread.is_alive()]
    saved, retired = results["save"], results["retire"]
    assert isinstance(retired, actions.RetireReport), results
    retire_first = saved == Invalid({"facilityNodeIds": selection_actions.NOT_A_LEAF}) and retired.state == "done"
    save_first = isinstance(saved, SaveResult) and retired.state == "blocked" and retired.deleted_nodes == 0
    assert retire_first or save_first, results  # 한쪽만 선다
    gone = GhgIndexNode.objects.filter(deleted_at__isnull=False).values_list("id", flat=True)
    dangling = CompanyIndexSelection.unscoped.filter(deleted_at__isnull=True, facility_node_id__in=list(gone))
    assert dangling.count() == 0  # 지운 잎을 가리키는 살아 있는 선택 0


def test_counting_does_not_change_the_plan() -> None:
    kept = copy.deepcopy(NEW)
    seed(OLD)
    retire(apply=True)
    assert kept == NEW


def test_apply_locks_the_old_nodes_and_their_factors_before_it_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """덧 3: --apply 는 lock_nodes(옛 노드) → lock_factor(그 계수 하나씩) 뒤에 센다(쓰임·잡힌 계수 판정이 잠금 뒤).
    셈만은 잠그지 않는다. 부른 차례로 단언한다(경합 시험은 차례 하나만 보므로 — 검증 B1)."""
    seed(OLD)
    events: list[str] = []

    def record(name: str, call: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            events.append(name)
            return call(*args, **kwargs)

        return wrapped

    for name in ("lock_nodes", "lock_factor", "alive_nodes"):
        monkeypatch.setattr(selectors, name, record(name, getattr(selectors, name)))
    nodes_judge = record("nodes_in_use", nodes_in_use_of_pool)
    factors_judge = record("factors_in_use", factors_in_use_of_pool)
    counted = retire(nodes_in_use=nodes_judge, factors_in_use=factors_judge)
    assert counted.state == "ready" and "lock_nodes" not in events and "lock_factor" not in events  # 셈만 = 잠금 0
    events.clear()
    applied = retire(apply=True, nodes_in_use=nodes_judge, factors_in_use=factors_judge)
    assert applied.state == "done"
    judged = min(events.index("nodes_in_use"), events.index("factors_in_use"))
    assert events[0] == "lock_nodes" and events.index("alive_nodes") > 0  # 노드 잠금이 셈의 첫 읽기보다 먼저
    locks = [index for index, name in enumerate(events) if name == "lock_factor"]
    assert len(locks) == len(FUELS) and max(locks) < judged  # 옛 잎 계수 둘 다 판정 전에 잠금


def test_old_codes_alone_left_after_a_hand_delete_are_ready_then_nothing() -> None:
    """옛 노드를 관리자가 손으로 다 지웠어도 그 잎의 옛 코드가 살아 있으면 ready — --apply 가 코드만 지우고 다음은
    nothing(덧 2 의 nothing = 살아 있는 옛 노드 0 이고 지울 옛 코드 0)."""
    seed(OLD)
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[node(key).pk for key in RETIRED]) == 3
    counted = retire()
    assert (counted.alive, counted.codes, counted.state) == (0, 2, "ready")
    applied = retire(apply=True)
    assert (applied.state, applied.deleted_nodes, applied.deleted_codes) == ("done", 0, 2)
    assert retire().state == "nothing"


def test_the_command_says_refused_for_a_refusal_and_blocked_only_for_a_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """가지 리뷰 MINOR1: 쓰임이 막은 거절(지우는 중 경합 — InUse·HasChildren·코드 InUse)만 RETIRE=blocked,
    그 밖의 거절은 RETIRE=refused <타입>(계획에 retired 없음 = Invalid)."""
    seed(OLD)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(OLD, ensure_ascii=False), encoding="utf-8")  # retired 칸 없음
    out = io.StringIO()
    with pytest.raises(CommandError, match="Invalid"):
        call_command("retire_ghg_seed", "--plan", str(path), stdout=out)
    assert out.getvalue().splitlines()[-1] == "RETIRE=refused Invalid"

    def raced(**_: Any) -> InUse:
        return InUse(frozenset({1}))

    monkeypatch.setattr(actions, "retire_seed", raced)  # 지우는 중 쓰임이 새로 걸린 꼴
    out = io.StringIO()
    with pytest.raises(CommandError, match="InUse"):
        call_command("retire_ghg_seed", "--apply", stdout=out)
    assert out.getvalue().splitlines()[-1] == "RETIRE=blocked"
