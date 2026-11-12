"""온실가스 풀 selectors(밴드 K1b-2a ② — service/selectors/ghg_pool.py). 업무 층, 주인 역할 연결.

열 목록(범위 단·자식·childCount·차례)·검색(맞는 노드와 조상)·잎 상세(지금 판 요약)·판 하나·선택 목록·사용 중 자리·권한.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from esgapi.inventory.models import GhgFactor, GhgFactorVersion, GhgIndexNode
from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.selectors import ghg_pool as selectors
from esgapi.inventory.service.utils.ghg_pool import (
    GASES,
    FacilityView,
    FactorView,
    Forbidden,
    GasDraft,
    NodeView,
    NotFound,
)
from esgapi.inventory.tests.ghg_pool_support import ADMIN, CUSTOMER, activity, draft, factor, leaf, node

pytestmark = pytest.mark.django_db


def listed(parent_id: int | None = None, q: str | None = None) -> list[NodeView]:
    found = selectors.node_list(actor_kind=ADMIN, parent_id=parent_id, q=q)
    assert isinstance(found, list), found
    return found


def test_the_first_column_is_the_scopes_in_made_order_with_child_counts() -> None:
    first = node("scope", "범위 나")
    second = node("scope", "범위 가")
    node("source_type", "유형 가", first)
    gone = node("source_type", "유형 나", first)
    GhgIndexNode.objects.filter(pk=gone).update(deleted_at=timezone.now())
    found = listed()
    assert [(row.id, row.name, row.child_count) for row in found] == [(first, "범위 나", 1), (second, "범위 가", 0)]


def test_a_column_is_the_alive_children_of_a_parent() -> None:
    act = activity()
    boiler = leaf(act, "가 보일러")
    found = listed(act)
    assert [(row.id, row.level, row.name, row.facility_code_id is not None) for row in found] == [
        (boiler, "facility", "가 보일러", True)
    ]  # 잎의 이름은 코드 이름
    assert found[0].facility_code and found[0].facility_code.startswith("F")
    assert selectors.node_list(actor_kind=ADMIN, parent_id=2_000_000_000, q=None) == NotFound()


def test_search_finds_nodes_and_their_ancestors_case_insensitively() -> None:
    act = activity("가")
    kind = GhgIndexNode.objects.get(pk=act).parent_id
    scope = GhgIndexNode.objects.get(pk=kind).parent_id
    boiler = leaf(act, "Boiler 가")
    activity("나")
    found = listed(q="boiler")
    assert [row.id for row in found] == [scope, kind, act, boiler]  # 단 차례
    assert {row.id for row in listed(q="유형 가")} == {scope, kind}
    assert listed(q="없는 이름") == []


def test_the_leaf_detail_lists_alive_factors_with_their_current_version() -> None:
    act = activity()
    boiler = leaf(act, "가 보일러", unit=("volume", "L"))
    first = factor(boiler, name="계수 하나")
    second = factor(boiler, name="계수 둘")
    gone = factor(boiler, name="계수 셋")
    GhgFactor.objects.filter(pk=gone.id).update(deleted_at=timezone.now())
    actions.save_factor(actor_kind=ADMIN, factor_id=second.id, draft=draft(name="계수 둘 고침"))
    detail = selectors.facility_detail(actor_kind=ADMIN, node_id=boiler)
    assert isinstance(detail, FacilityView)
    assert (detail.parent_id, detail.facility_name, detail.unit, detail.tooltip) == (
        act,
        "가 보일러",
        ("volume", "L"),
        "",
    )
    assert [(f.id, f.name, f.is_default, f.version) for f in detail.factors] == [
        (first.id, "계수 하나", True, 1),
        (second.id, "계수 둘 고침", False, 2),
    ]
    assert selectors.facility_detail(actor_kind=ADMIN, node_id=act) == NotFound()  # 잎이 아니다


def test_a_factor_version_reads_any_version_and_lists_them() -> None:
    boiler = leaf(activity(), "가 보일러")
    made = factor(boiler, gases=(GasDraft("CH4", enabled=True, factor="0.25", gwp="2"),))
    actions.save_factor(actor_kind=ADMIN, factor_id=made.id, draft=draft(name="고친 이름"))
    now = selectors.factor_version(actor_kind=ADMIN, factor_id=made.id, version=None)
    old = selectors.factor_version(actor_kind=ADMIN, factor_id=made.id, version=1)
    assert isinstance(now, FactorView) and isinstance(old, FactorView)
    assert (now.version, now.name, now.versions) == (2, "고친 이름", (1, 2))
    assert (old.version, old.name, old.versions) == (1, "계수 가", (1, 2))
    assert [gas.gas for gas in old.gases] == list(GASES)
    ch4 = old.gases[GASES.index("CH4")]
    assert (ch4.enabled, ch4.factor, ch4.gwp) == (True, Decimal("0.25"), Decimal("2"))
    assert selectors.factor_version(actor_kind=ADMIN, factor_id=made.id, version=3) == NotFound()
    GhgFactor.objects.filter(pk=made.id).update(is_default=False, deleted_at=timezone.now())
    assert selectors.factor_version(actor_kind=ADMIN, factor_id=made.id, version=1) == NotFound()


def test_the_lock_skips_a_deleted_factor() -> None:
    made = factor(leaf(activity(), "가 보일러"))
    assert selectors.lock_factor(made.id) is not None
    GhgFactor.objects.filter(pk=made.id).update(is_default=False, deleted_at=timezone.now())
    assert selectors.lock_factor(made.id) is None


def test_the_route_reads_are_forbidden_to_a_customer_kind() -> None:
    made = factor(leaf(activity(), "가 보일러"))
    assert selectors.node_list(actor_kind=CUSTOMER, parent_id=None, q=None) == Forbidden(
        "inventory_admin_ghg_nodes_list"
    )
    assert selectors.facility_detail(actor_kind=CUSTOMER, node_id=made.facility_node_id) == Forbidden(
        "inventory_admin_ghg_facilities_get"
    )
    assert selectors.factor_version(actor_kind=CUSTOMER, factor_id=made.id, version=None) == Forbidden(
        "inventory_admin_ghg_factors_get"
    )
    assert selectors.options(actor_kind=CUSTOMER) == Forbidden("inventory_admin_ghg_options")
    assert isinstance(selectors.options(actor_kind=ADMIN), dict)


# ── K1b-2b: 고객사 트리의 읽기 둘 ──────────────────────────────────


def test_tree_nodes_are_every_alive_node_by_level_then_order() -> None:
    first = activity("가")
    second = activity("나")
    boiler = leaf(first, "가 보일러")
    gone = leaf(second, "나 버너")
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[gone]) == 1
    found = selectors.tree_nodes()
    assert [line.level for line in found] == [
        "scope",
        "scope",
        "source_type",
        "source_type",
        "activity",
        "activity",
        "facility",
    ]
    assert gone not in {line.id for line in found}  # 지운 잎은 빠진다
    line = next(line for line in found if line.id == boiler)
    assert (line.name, line.parent_id, line.facility_code_id is not None) == ("가 보일러", first, True)


def test_default_versions_give_the_current_version_of_the_alive_default() -> None:
    parent = activity()
    boiler, bare = leaf(parent, "가 보일러"), leaf(parent, "나 버너")
    made = factor(boiler)
    factor(boiler, name="둘째 계수")  # 기본 아님
    edited = actions.save_factor(actor_kind=ADMIN, factor_id=made.id, draft=draft(name="고친 계수"))
    assert isinstance(edited, FactorView) and edited.version == 2
    found = selectors.default_versions([boiler, bare])
    assert list(found) == [boiler]  # 기본 계수 없는 잎은 빠진다
    assert GhgFactorVersion.objects.get(pk=found[boiler]).version == 2
    GhgFactor.objects.filter(pk=made.id).update(is_default=False, deleted_at=timezone.now())
    assert selectors.default_versions([boiler]) == {}  # 지운 기본은 안 센다


def test_pinned_version_reads_a_version_of_a_deleted_factor() -> None:
    """L4: 회사가 잡은 판은 계수가 지워져도 읽힌다(factor_version 은 404 — 짝)."""
    made = factor(leaf(activity(), "가 보일러"))
    edited = actions.save_factor(actor_kind=ADMIN, factor_id=made.id, draft=draft(name="고친 계수"))
    assert isinstance(edited, FactorView)
    first = GhgFactorVersion.objects.get(factor_id=made.id, version=1)
    GhgFactor.objects.filter(pk=made.id).update(is_default=False, deleted_at=timezone.now())
    assert selectors.factor_version(actor_kind=ADMIN, factor_id=made.id, version=1) == NotFound()  # 짝
    found = selectors.pinned_version(first.pk)
    assert isinstance(found, FactorView)
    assert (found.id, found.version, found.name, found.versions) == (made.id, 1, "계수 가", (1, 2))
    assert [gas.gas for gas in found.gases] == list(GASES)  # 가스 일곱(factor_version 의 꼴)
    assert selectors.pinned_version(10**9) == NotFound()


def test_leaf_unit_is_the_unit_of_an_alive_leaf() -> None:
    parent = activity()
    boiler = leaf(parent, "가 보일러")
    assert selectors.leaf_unit(boiler) == ("mass", "kg")
    assert selectors.leaf_unit(parent) is None  # 잎 아님
    GhgIndexNode.objects.filter(pk=boiler).update(deleted_at=timezone.now())
    assert selectors.leaf_unit(boiler) is None
