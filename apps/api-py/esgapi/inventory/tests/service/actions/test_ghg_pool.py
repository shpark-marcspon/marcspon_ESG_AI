"""온실가스 풀 actions(밴드 K1b-2a ② — service/actions/ghg_pool.py). 업무 층, 주인 역할 연결.

잎 만들기·저장(코드 확인·겹침·기본 바꾸기) · 계수 만들기(첫 계수 기본·가스 일곱) · 고치기(새 판, 옛 판 그대로) · 일괄
지우기(자식 있음·사용 중·잎이면 계수도·기본 승계·없는 id 404) · 중간 실패(둘째 services 부름) → 0 바뀜 · 권한.
거절은 다 행 0(counts 앞뒤 같음). 사용 중은 가짜를 넘겨 잰다(지금 자리는 늘 빈 집합 — K1b-2b·S12a).
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from esgapi.inventory.models import GhgFactor, GhgFactorGas, GhgFactorVersion, GhgIndexNode
from esgapi.inventory.service.actions import ghg_pool as actions
from esgapi.inventory.service.services import ghg_pool as services
from esgapi.inventory.service.utils.ghg_pool import (
    GASES,
    FacilityView,
    FactorView,
    Forbidden,
    GasDraft,
    HasChildren,
    InUse,
    Invalid,
    NotFound,
)
from esgapi.inventory.tests.ghg_pool_support import ADMIN, CUSTOMER, activity, code, counts, draft, factor, leaf, node
from esgapi.organization.service.services.facility_codes import delete_codes

pytestmark = pytest.mark.django_db


def make_leaf(parent_id: int, code_id: int, **fields: object) -> object:
    values: dict[str, object] = {"unit": ("mass", "kg"), "tooltip": "", **fields}
    return actions.create_facility(actor_kind=ADMIN, parent_id=parent_id, facility_code_id=code_id, **values)  # type: ignore[arg-type]


def alive_defaults(node_id: int) -> list[int]:
    return list(
        GhgFactor.objects.filter(facility_node_id=node_id, deleted_at__isnull=True, is_default=True).values_list(
            "id", flat=True
        )
    )


# ── 잎 ───────────────────────────────────────────────────────────────


def test_a_leaf_sits_under_an_activity_with_an_alive_code() -> None:
    act = activity()
    boiler = code("가 보일러")
    made = make_leaf(act, boiler, unit=("volume", "Nm3"), tooltip="설명")
    assert isinstance(made, FacilityView)
    assert (made.parent_id, made.facility_code_id, made.unit, made.tooltip, made.factors) == (
        act,
        boiler,
        ("volume", "Nm3"),
        "설명",
        [],
    )
    kind = GhgIndexNode.objects.get(pk=act).parent_id
    assert kind is not None
    before = counts()
    refused = make_leaf(kind, code("나 보일러"))
    assert isinstance(refused, Invalid) and set(refused.fields) == {"parentId"}  # 유형 아래 잎
    assert make_leaf(2_000_000_000, boiler) == NotFound()
    leaf_id = leaf(act, "다 보일러")
    before = counts()
    refused = make_leaf(leaf_id, code("라 보일러"))  # 잎 아래 잎(DB CHECK 로 못 막는 규칙 — 검증 ② B2)
    assert isinstance(refused, Invalid) and set(refused.fields) == {"parentId"}
    assert counts()[0] == before[0]
    assert make_leaf(act, boiler) == Invalid({"facilityCodeId": services.CODE_TAKEN})  # 같은 활동·같은 코드
    for fields, field in (
        ({"unit": ("mass", "lb")}, "unit"),
        ({"unit": None}, "unit"),
        ({"tooltip": "가" * 1001}, "tooltip"),
    ):
        refused = make_leaf(act, code(f"코드 {field} {len(str(fields))}"), **fields)
        assert isinstance(refused, Invalid) and field in refused.fields
    assert counts()[0] == before[0]


def test_a_deleted_code_is_refused_for_a_new_leaf_but_kept_by_its_leaf() -> None:
    act = activity()
    gone = code("지울 코드")
    leaf_id = make_leaf(act, gone)
    assert isinstance(leaf_id, FacilityView)
    assert delete_codes(actor_kind=ADMIN, ids=[gone]) == 1
    other = node("activity", "활동 나", GhgIndexNode.objects.get(pk=act).parent_id)
    assert make_leaf(other, gone) == Invalid({"facilityCodeId": actions.CODE_GONE})
    kept = actions.save_facility(
        actor_kind=ADMIN,
        node_id=leaf_id.id,
        facility_code_id=gone,
        unit=("mass", "t"),
        tooltip="",
        default_factor_id=None,
    )
    assert isinstance(kept, FacilityView) and kept.unit == ("mass", "t")  # 이미 쓰는 코드를 그대로 두면 된다
    switched = actions.save_facility(
        actor_kind=ADMIN,
        node_id=leaf_id.id,
        facility_code_id=code("새 코드"),
        unit=("mass", "t"),
        tooltip="",
        default_factor_id=None,
    )
    assert isinstance(switched, FacilityView) and switched.facility_name == "새 코드"
    back = actions.save_facility(
        actor_kind=ADMIN,
        node_id=leaf_id.id,
        facility_code_id=gone,
        unit=("mass", "t"),
        tooltip="",
        default_factor_id=None,
    )
    assert back == Invalid({"facilityCodeId": actions.CODE_GONE})  # 지운 코드로 되돌리기는 새로 고름


def test_save_switches_the_default_only_to_an_alive_factor_of_the_same_leaf() -> None:
    act = activity()
    boiler = leaf(act, "가 보일러")
    other = leaf(act, "나 보일러")
    first = factor(boiler)
    second = factor(boiler)
    foreign = factor(other)
    boiler_code = GhgIndexNode.objects.get(pk=boiler).facility_code_id
    assert boiler_code is not None

    def save(default_factor_id: int | None) -> object:
        return actions.save_facility(
            actor_kind=ADMIN,
            node_id=boiler,
            facility_code_id=boiler_code,
            unit=("mass", "kg"),
            tooltip="새 설명",
            default_factor_id=default_factor_id,
        )

    assert save(foreign.id) == Invalid({"defaultFactorId": "이 자산/시설의 삭제 안 된 계수가 아니다"})
    assert alive_defaults(boiler) == [first.id]
    assert GhgIndexNode.objects.get(pk=boiler).tooltip == ""  # 거절은 행 0
    saved = save(second.id)
    assert isinstance(saved, FacilityView)
    assert [(f.id, f.is_default) for f in saved.factors] == [(first.id, False), (second.id, True)]
    assert alive_defaults(boiler) == [second.id] and alive_defaults(other) == [foreign.id]
    assert save(None) and alive_defaults(boiler) == [second.id]  # 없으면 그대로
    assert (
        actions.save_facility(
            actor_kind=ADMIN,
            node_id=act,
            facility_code_id=boiler_code,
            unit=("mass", "kg"),
            tooltip="",
            default_factor_id=None,
        )
        == NotFound()
    )


# ── 계수 ─────────────────────────────────────────────────────────────


def test_the_first_factor_is_the_default_and_every_version_has_seven_gases() -> None:
    boiler = leaf(activity(), "가 보일러")
    first = factor(boiler, ncv_enabled=True, ncv="12.34", ncv_unit=("energy", "MJ"))
    second = factor(boiler)
    assert (first.is_default, second.is_default) == (True, False)
    assert (first.factor_unit, second.factor_unit) == ("kg/TJ", "kg/kg")
    assert first.ncv == Decimal("12.34") and first.ncv_enabled
    for made in (first, second):
        rows = GhgFactorGas.objects.filter(factor_version__factor_id=made.id).order_by("id")
        assert [row.gas for row in rows] == list(GASES)
    assert (
        actions.create_factor(
            actor_kind=ADMIN, node_id=GhgIndexNode.objects.get(pk=boiler).parent_id or 0, draft=draft()
        )
        == NotFound()
    )


def test_a_bad_draft_is_422_and_writes_nothing() -> None:
    boiler = leaf(activity(), "가 보일러")
    before = counts()
    refused = actions.create_factor(
        actor_kind=ADMIN, node_id=boiler, draft=draft(gases=(GasDraft("CO2", enabled=True, factor="1", gwp="0"),))
    )
    assert isinstance(refused, Invalid) and set(refused.fields) == {"gases.CO2.gwp"}
    assert counts() == before


def test_saving_makes_a_new_version_and_leaves_the_old_one_as_it_was() -> None:
    boiler = leaf(activity(), "가 보일러")
    made = factor(boiler, name="옛 이름", note="옛 비고")
    old_rows = list(GhgFactorVersion.objects.filter(factor_id=made.id).values())
    old_gases = list(GhgFactorGas.objects.filter(factor_version__factor_id=made.id).order_by("id").values())
    saved = actions.save_factor(
        actor_kind=ADMIN,
        factor_id=made.id,
        draft=draft(name="새 이름", gases=(GasDraft("N2O", enabled=True, factor="9.75", gwp="3"),)),
    )
    assert isinstance(saved, FactorView)
    assert (saved.version, saved.name, saved.versions, saved.is_default) == (2, "새 이름", (1, 2), True)
    assert list(GhgFactorVersion.objects.filter(factor_id=made.id, version=1).values()) == old_rows  # 글자 그대로
    assert (
        list(
            GhgFactorGas.objects.filter(factor_version__factor_id=made.id, factor_version__version=1)
            .order_by("id")
            .values()
        )
        == old_gases
    )
    assert GhgFactor.objects.get(pk=made.id).current_version == 2
    again = actions.save_factor(actor_kind=ADMIN, factor_id=made.id, draft=draft(name="새 이름"))
    assert isinstance(again, FactorView) and again.version == 3  # 바뀐 것이 없어도 새 판
    assert actions.save_factor(actor_kind=ADMIN, factor_id=2_000_000_000, draft=draft()) == NotFound()


def test_a_failure_in_the_second_services_call_leaves_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """중간 실패: 정체를 넣은 뒤 판 넣기(둘째 services 부름)가 터지면 정체도 남지 않는다(action 의 한 트랜잭션)."""
    boiler = leaf(activity(), "가 보일러")
    before = counts()

    def broken(**_: object) -> int:
        raise RuntimeError("심은 실패")

    monkeypatch.setattr(services, "insert_factor_version", broken)
    with pytest.raises(RuntimeError, match="심은 실패"):
        actions.create_factor(actor_kind=ADMIN, node_id=boiler, draft=draft())
    assert counts() == before


# ── 지우기 ───────────────────────────────────────────────────────────


def test_a_node_with_alive_children_outside_the_request_is_409() -> None:
    act = activity()
    kind = GhgIndexNode.objects.get(pk=act).parent_id
    assert kind is not None
    boiler = leaf(act, "가 보일러")
    before = counts()
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[kind]) == HasChildren(frozenset({kind}))
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[act]) == HasChildren(frozenset({act}))
    assert counts() == before and GhgIndexNode.objects.filter(deleted_at__isnull=False).count() == 0
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[kind, act, boiler]) == 3  # 아래까지 같이 지우면 된다


def test_deleting_a_leaf_deletes_its_factors() -> None:
    act = activity()
    boiler = leaf(act, "가 보일러")
    kept = leaf(act, "나 보일러")
    factor(boiler)
    factor(boiler)
    other = factor(kept)
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[boiler]) == 1
    assert GhgFactor.objects.filter(facility_node_id=boiler, deleted_at__isnull=True).count() == 0
    assert GhgFactor.objects.filter(facility_node_id=boiler, is_default=True).count() == 0
    assert alive_defaults(kept) == [other.id]
    assert GhgFactorVersion.objects.count() == 3  # 판은 그대로(고치지 않는다)


def test_a_node_in_use_is_409_and_unknown_ids_are_404_with_nothing_changed() -> None:
    act = activity()
    boiler = leaf(act, "가 보일러")
    before = counts()
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[boiler], nodes_in_use=lambda ids: frozenset(ids)) == InUse(
        frozenset({boiler})
    )
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[boiler, 2_000_000_000]) == NotFound()
    assert actions.delete_nodes(actor_kind=ADMIN, ids=[]) == NotFound()
    assert counts() == before
    assert GhgIndexNode.objects.filter(deleted_at__isnull=False).count() == 0


def test_deleting_the_default_passes_it_to_the_first_alive_factor() -> None:
    boiler = leaf(activity(), "가 보일러")
    first = factor(boiler)
    second = factor(boiler)
    third = factor(boiler)
    assert actions.delete_factors(actor_kind=ADMIN, ids=[first.id]) == 1
    assert alive_defaults(boiler) == [second.id]
    assert actions.delete_factors(actor_kind=ADMIN, ids=[third.id]) == 1  # 기본 아닌 것 — 기본 그대로
    assert alive_defaults(boiler) == [second.id]
    assert actions.delete_factors(actor_kind=ADMIN, ids=[second.id]) == 1
    assert alive_defaults(boiler) == []  # 남은 것이 없다
    fresh = factor(boiler)
    assert fresh.is_default  # 삭제 안 된 것 0 → 새 첫 계수가 기본


def test_a_factor_in_use_is_409_and_unknown_ids_are_404() -> None:
    boiler = leaf(activity(), "가 보일러")
    made = factor(boiler)
    before = counts()
    assert actions.delete_factors(actor_kind=ADMIN, ids=[made.id], factors_in_use=lambda ids: frozenset(ids)) == InUse(
        frozenset({made.id})
    )
    assert actions.delete_factors(actor_kind=ADMIN, ids=[made.id, 2_000_000_000]) == NotFound()
    assert counts() == before and alive_defaults(boiler) == [made.id]
    GhgFactor.objects.filter(pk=made.id).update(is_default=False, deleted_at=timezone.now())
    assert actions.delete_factors(actor_kind=ADMIN, ids=[made.id]) == NotFound()  # 이미 지운 것


# ── 권한 ─────────────────────────────────────────────────────────────


def test_every_action_is_forbidden_to_a_customer_kind_and_writes_nothing() -> None:
    act = activity()
    boiler = leaf(act, "가 보일러")
    made = factor(boiler)
    code_id = code("다 보일러")
    before = counts()
    calls = {
        "inventory_admin_ghg_facilities_create": lambda: actions.create_facility(
            actor_kind=CUSTOMER, parent_id=act, facility_code_id=code_id, unit=("mass", "kg"), tooltip=""
        ),
        "inventory_admin_ghg_facilities_save": lambda: actions.save_facility(
            actor_kind=CUSTOMER,
            node_id=boiler,
            facility_code_id=code_id,
            unit=("mass", "kg"),
            tooltip="",
            default_factor_id=None,
        ),
        "inventory_admin_ghg_factors_create": lambda: actions.create_factor(
            actor_kind=CUSTOMER, node_id=boiler, draft=draft()
        ),
        "inventory_admin_ghg_factors_save": lambda: actions.save_factor(
            actor_kind=CUSTOMER, factor_id=made.id, draft=draft()
        ),
        "inventory_admin_ghg_nodes_delete": lambda: actions.delete_nodes(actor_kind=CUSTOMER, ids=[boiler]),
        "inventory_admin_ghg_factors_delete": lambda: actions.delete_factors(actor_kind=CUSTOMER, ids=[made.id]),
    }
    for operation_id, call in calls.items():
        assert call() == Forbidden(operation_id), operation_id
    assert counts() == before
    assert GhgIndexNode.objects.filter(deleted_at__isnull=False).count() == 0
