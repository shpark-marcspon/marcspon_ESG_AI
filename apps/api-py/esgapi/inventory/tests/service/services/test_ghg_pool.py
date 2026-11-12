"""온실가스 풀 services(밴드 K1b-2a ② — service/services/ghg_pool.py). 업무 층, 주인 역할 연결.

단 규칙·이름 겹침·잎 PATCH 거절·만든 차례·권한(고객사 kind → Forbidden, 행 0). 거절은 다 행 0 을 같이 잰다.
"""

from collections.abc import Callable

import pytest
from django.db import IntegrityError
from django.db.models import QuerySet

from esgapi.inventory.models import GhgFactor, GhgIndexNode
from esgapi.inventory.service.services import ghg_pool as services
from esgapi.inventory.service.utils.ghg_pool import Forbidden, Invalid, NodeView, NotFound
from esgapi.inventory.tests.ghg_pool_support import ADMIN, CUSTOMER, activity, code, counts, factor, leaf, node

pytestmark = pytest.mark.django_db


def create(level: str, name: str, parent_id: int | None = None) -> object:
    return services.create_node(actor_kind=ADMIN, level=level, parent_id=parent_id, name=name)


def test_a_scope_is_a_root_and_the_others_step_down_one_level() -> None:
    scope = node("scope", "범위 가")
    kind = node("source_type", "유형 가", scope)
    made = create("activity", "  활동 가  ", kind)
    assert isinstance(made, NodeView)
    assert (made.level, made.name, made.parent_id, made.child_count) == ("activity", "활동 가", kind, 0)
    assert made.sort_order == made.id  # 기본 = 만든 차례


@pytest.mark.parametrize(("level", "parent"), [
    ("scope", "scope"),  # 범위는 부모가 없다
    ("source_type", None),
    ("source_type", "kind"),  # 유형 아래 유형
    ("activity", "scope"),  # 범위 아래 바로 활동(한 단 건너뜀)
    ("activity", "activity"),
])  # fmt: skip
def test_a_level_out_of_step_is_refused_on_parent_id(level: str, parent: str | None) -> None:
    scope = node("scope", "범위 가")
    kind = node("source_type", "유형 가", scope)
    act = node("activity", "활동 가", kind)
    before = counts()
    parent_id = {"scope": scope, "kind": kind, "activity": act, None: None}[parent]
    refused = create(level, "새 노드", parent_id)
    assert isinstance(refused, Invalid) and set(refused.fields) == {"parentId"}
    assert counts() == before


def test_a_leaf_level_is_not_made_here_and_a_name_is_needed() -> None:
    act = activity()
    before = counts()
    made = create("facility", "보일러", act)
    assert isinstance(made, Invalid) and set(made.fields) == {"level"}
    for name in ("", "   ", "가" * 101):
        refused = create("scope", name)
        assert isinstance(refused, Invalid) and set(refused.fields) == {"name"}
    assert counts() == before
    assert isinstance(create("scope", "가" * 100), NodeView)  # 짝: 100자는 된다


def test_a_missing_or_deleted_parent_is_404() -> None:
    scope = node("scope", "범위 가")
    assert create("source_type", "유형 가", 2_000_000_000) == NotFound()
    GhgIndexNode.objects.filter(pk=scope).update(deleted_at="2026-01-01T00:00:00+09:00")
    assert create("source_type", "유형 가", scope) == NotFound()


def test_names_are_unique_among_alive_siblings_and_roots() -> None:
    scope = node("scope", "범위 가")
    kind = node("source_type", "유형 가", scope)
    before = counts()
    assert create("scope", "범위 가") == Invalid({"name": services.NAME_TAKEN})
    assert create("source_type", "유형 가", scope) == Invalid({"name": services.NAME_TAKEN})
    assert counts() == before
    other = node("scope", "범위 나")
    assert isinstance(create("source_type", "유형 가", other), NodeView)  # 짝: 다른 부모
    GhgIndexNode.objects.filter(pk=kind).update(deleted_at="2026-01-01T00:00:00+09:00")
    assert isinstance(create("source_type", "유형 가", scope), NodeView)  # 짝: 지운 이름은 다시 쓴다


def test_rename_keeps_the_rules_and_refuses_a_leaf() -> None:
    act = activity()
    sibling = node("activity", "활동 나", GhgIndexNode.objects.get(pk=act).parent_id)
    renamed = services.rename_node(actor_kind=ADMIN, node_id=act, name=" 활동 다 ")
    assert isinstance(renamed, NodeView) and renamed.name == "활동 다"
    assert services.rename_node(actor_kind=ADMIN, node_id=sibling, name="활동 다") == Invalid(
        {"name": services.NAME_TAKEN}
    )
    assert isinstance(services.rename_node(actor_kind=ADMIN, node_id=act, name="활동 다"), NodeView)  # 자기 이름
    boiler = leaf(act, "가 보일러")
    refused = services.rename_node(actor_kind=ADMIN, node_id=boiler, name="새 이름")
    assert isinstance(refused, Invalid) and set(refused.fields) == {"level"}
    assert services.rename_node(actor_kind=ADMIN, node_id=2_000_000_000, name="x") == NotFound()
    assert GhgIndexNode.objects.get(pk=boiler).name == ""


def test_a_customer_kind_is_forbidden_and_writes_nothing() -> None:
    scope = node("scope", "범위 가")
    before = counts()
    assert services.create_node(actor_kind=CUSTOMER, level="scope", parent_id=None, name="범위 나") == Forbidden(
        "inventory_admin_ghg_nodes_create"
    )
    assert services.rename_node(actor_kind=CUSTOMER, node_id=scope, name="범위 다") == Forbidden(
        "inventory_admin_ghg_nodes_update"
    )
    op = "inventory_admin_ghg_nodes_delete"
    assert services.mark_nodes_deleted(actor_kind=CUSTOMER, operation_id=op, ids=[scope]) == Forbidden(op)
    assert counts() == before
    assert GhgIndexNode.objects.get(pk=scope).name == "범위 가"


# ── 제약 이름 가름(K1b-2u L1) · 삭제 조건(L2) ──────────────────────────
CREATE_FACTOR = "inventory_admin_ghg_factors_create"


def test_a_taken_factor_seed_key_is_its_own_refusal() -> None:
    boiler = leaf(activity(), "가 보일러")
    first = services.insert_factor(
        actor_kind=ADMIN, operation_id=CREATE_FACTOR, facility_node_id=boiler, is_default=False, seed_key="씨앗 가"
    )
    assert isinstance(first, int)
    again = services.insert_factor(
        actor_kind=ADMIN, operation_id=CREATE_FACTOR, facility_node_id=boiler, is_default=False, seed_key="씨앗 가"
    )
    assert again == Invalid({"seedKey": services.SEED_KEY_TAKEN})
    assert GhgFactor.objects.filter(facility_node_id=boiler).count() == 1


def test_a_second_default_is_still_the_default_race_refusal() -> None:
    boiler = leaf(activity(), "가 보일러")
    factor(boiler)  # 첫 계수 = 기본
    refused = services.insert_factor(
        actor_kind=ADMIN, operation_id=CREATE_FACTOR, facility_node_id=boiler, is_default=True, seed_key="씨앗 나"
    )
    assert refused == Invalid({"defaultFactorId": services.DEFAULT_RACE})


def _made_up(*args: object, **fields: object) -> object:
    raise IntegrityError("지어낸 제약 위반")


def _six_calls() -> dict[str, Callable[[], object]]:
    """except IntegrityError 를 가진 여섯 함수 — 지어낸 나무 위에서 부를 꼴."""
    act = activity()
    boiler = leaf(act, "가 보일러")
    made = factor(boiler)
    second, third = code("나 보일러"), code("다 보일러")  # 패치 앞에 만든다(시설 코드 만들기도 create·update 를 쓴다)
    return {
        "create_node": lambda: services.create_node(actor_kind=ADMIN, level="scope", parent_id=None, name="범위 새"),
        "rename_node": lambda: services.rename_node(actor_kind=ADMIN, node_id=act, name="활동 새"),
        "insert_leaf": lambda: services.insert_leaf(
            actor_kind=ADMIN, operation_id="inventory_admin_ghg_facilities_create", parent_id=act,
            facility_code_id=second, unit=("mass", "kg"), tooltip="",
        ),
        "update_leaf": lambda: services.update_leaf(
            actor_kind=ADMIN, operation_id="inventory_admin_ghg_facilities_save", node_id=boiler,
            facility_code_id=third, unit=("mass", "kg"), tooltip="",
        ),
        "insert_factor": lambda: services.insert_factor(
            actor_kind=ADMIN, operation_id=CREATE_FACTOR, facility_node_id=boiler, is_default=False
        ),
        "set_default_factor": lambda: services.set_default_factor(
            actor_kind=ADMIN, operation_id="inventory_admin_ghg_facilities_save", facility_node_id=boiler,
            factor_id=made.id,
        ),
    }  # fmt: skip


@pytest.mark.parametrize(
    "function", ["create_node", "rename_node", "insert_leaf", "update_leaf", "insert_factor", "set_default_factor"]
)
def test_an_unknown_constraint_is_raised_again(monkeypatch: pytest.MonkeyPatch, function: str) -> None:
    """이름 없는 IntegrityError(diag 없음 — 지어냄)는 여섯 함수 어디서도 갈래로 삼키지 않고 다시 던진다(500)."""
    call = _six_calls()[function]
    monkeypatch.setattr(GhgFactor.objects, "create", _made_up)
    monkeypatch.setattr(GhgIndexNode.objects, "create", _made_up)
    monkeypatch.setattr(QuerySet, "update", _made_up)
    with pytest.raises(IntegrityError, match="지어낸 제약 위반"):
        call()


def test_a_taken_node_seed_key_is_the_seed_key_refusal() -> None:
    """노드의 같은 씨앗 키(ghg_nodes_seed_key_unique)는 이름·코드 겹침이 아니라 seedKey 갈래다(K1b-2u R2)."""
    act = activity()
    first = services.create_node(actor_kind=ADMIN, level="scope", parent_id=None, name="범위 나", seed_key="씨앗 가")
    assert isinstance(first, NodeView)
    before = counts()
    again = services.create_node(actor_kind=ADMIN, level="scope", parent_id=None, name="범위 다", seed_key="씨앗 가")
    assert again == Invalid({"seedKey": services.SEED_KEY_TAKEN})
    leaf_op = "inventory_admin_ghg_facilities_create"
    one = services.insert_leaf(
        actor_kind=ADMIN, operation_id=leaf_op, parent_id=act, facility_code_id=code("가 보일러"), unit=("mass", "kg"),
        tooltip="", seed_key="씨앗 나",
    )  # fmt: skip
    assert isinstance(one, int)
    two = services.insert_leaf(
        actor_kind=ADMIN, operation_id=leaf_op, parent_id=act, facility_code_id=code("나 보일러"), unit=("mass", "kg"),
        tooltip="", seed_key="씨앗 나",
    )  # fmt: skip
    assert two == Invalid({"seedKey": services.SEED_KEY_TAKEN})
    assert counts()[0] == before[0] + 1  # 잎 하나만 더 섰다


def test_rename_and_leaf_and_version_updates_skip_a_deleted_row() -> None:
    act = activity()
    boiler = leaf(act, "가 보일러")
    made = factor(boiler)
    GhgIndexNode.objects.filter(pk__in=[act, boiler]).update(deleted_at="2026-01-01T00:00:00+09:00")
    GhgFactor.objects.filter(pk=made.id).update(is_default=False, deleted_at="2026-01-01T00:00:00+09:00")
    assert services.rename_node(actor_kind=ADMIN, node_id=act, name="활동 새") == NotFound()
    assert GhgIndexNode.objects.get(pk=act).name == "활동 가"
    saved = services.update_leaf(
        actor_kind=ADMIN,
        operation_id="inventory_admin_ghg_facilities_save",
        node_id=boiler,
        facility_code_id=code("나 보일러"),
        unit=("mass", "t"),
        tooltip="새 툴팁",
    )
    assert saved == NotFound()
    assert GhgIndexNode.objects.get(pk=boiler).tooltip == ""
    bumped = services.bump_factor_version(
        actor_kind=ADMIN, operation_id="inventory_admin_ghg_factors_save", factor_id=made.id
    )
    assert bumped == NotFound()
    assert GhgFactor.objects.get(pk=made.id).current_version == 1
