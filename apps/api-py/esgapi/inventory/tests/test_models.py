"""온실가스 풀 표 넷의 DB 제약(밴드 K1b-2a ① — migrations/0001_ghg_pool). 업무 층, 주인 역할 연결.

거절마다 됨의 짝을 둔다(제약이 너무 넓어 모든 행을 막는 것도 잡는다). 이름·값은 지어낸 것이다(실제 계수 0).
앱 역할의 권한(판·가스 UPDATE·DELETE 없음)은 tests/security/test_owner.py 가 앱 역할로 잰다.
"""

from decimal import Decimal
from typing import Any

import psycopg
import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from esgapi.inventory.models import GhgFactor, GhgFactorGas, GhgFactorVersion, GhgIndexNode
from esgapi.inventory.service.utils.ghg_pool import GASES
from esgapi.organization.service.selectors.facility_codes import alive_codes
from esgapi.organization.service.services.facility_codes import create_code
from esgapi.organization.service.utils.entities import FacilityCodeInfo

pytestmark = pytest.mark.django_db


def refused(constraint: str, make: Any) -> None:
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        make()


def sqlstate_of(make: Any) -> str | None:
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        make()
    cause = caught.value.__cause__
    assert isinstance(cause, psycopg.Error)
    return cause.sqlstate


def node(level: str, name: str, parent: GhgIndexNode | None = None, **fields: Any) -> GhgIndexNode:
    return GhgIndexNode.objects.create(level=level, name=name, parent=parent, **fields)


def code(name: str) -> int:
    """공통 코드 목록에 코드 하나(organization 의 services 로 — 남의 models 를 직접 열지 않는다, 계약 나)."""
    made = create_code(actor_kind="admin", name=name)
    assert isinstance(made, FacilityCodeInfo), made
    return made.id


@pytest.fixture
def activity() -> GhgIndexNode:
    scope = node("scope", "범위 가")
    kind = node("source_type", "유형 가", scope)
    return node("activity", "활동 가", kind)


def leaf(parent: GhgIndexNode, facility_code_id: int, **fields: Any) -> GhgIndexNode:
    values = {"unit_kind": "mass", "unit": "kg", **fields}
    return node("facility", "", parent, facility_code_id=facility_code_id, **values)


def version_fields(**fields: Any) -> dict[str, Any]:
    return {
        "version": 1,
        "name": "계수 가",
        "source": "지어낸 출처",
        "base_year": 2024,
        "tier": 1,
        "country_code": "KR",
        "industry_code": "other",
        "input_unit_kind": "mass",
        "input_unit": "kg",
        "factor_unit": "kg/kg",
        **fields,
    }


# ── 노드 ─────────────────────────────────────────────────────────────


def test_a_root_is_a_scope_and_a_scope_is_a_root(activity: GhgIndexNode) -> None:
    refused("ghg_nodes_root_is_scope", lambda: node("activity", "뿌리 활동"))
    refused("ghg_nodes_root_is_scope", lambda: node("scope", "자식 범위", activity))
    node("scope", "범위 나")  # 짝: 부모 없는 범위는 된다


def test_the_level_is_one_of_four() -> None:
    refused("ghg_nodes_level_check", lambda: node("planet", "x"))


def test_only_a_leaf_has_a_code_and_a_unit(activity: GhgIndexNode) -> None:
    boiler = code("가 보일러")
    refused("ghg_nodes_leaf_fields", lambda: node("facility", "", activity))  # 잎인데 코드·단위 없음
    refused("ghg_nodes_leaf_fields", lambda: leaf(activity, boiler, unit=None))
    refused("ghg_nodes_leaf_fields", lambda: node("activity", "활동 나", activity.parent, unit_kind="mass", unit="kg"))
    refused("ghg_nodes_leaf_fields", lambda: node("activity", "활동 다", activity.parent, facility_code_id=boiler))
    leaf(activity, boiler)  # 짝


def test_a_name_is_unique_under_a_parent_among_the_alive(activity: GhgIndexNode) -> None:
    kind = activity.parent
    assert kind is not None
    refused("ghg_nodes_name_unique_alive", lambda: node("activity", "활동 가", kind))
    node("activity", "활동 가", node("source_type", "유형 나", kind.parent))  # 짝: 다른 부모
    GhgIndexNode.objects.filter(pk=activity.pk).update(deleted_at=timezone.now())
    node("activity", "활동 가", kind)  # 짝: 지운 이름은 다시 쓴다


def test_a_root_name_is_unique_among_the_alive() -> None:
    first = node("scope", "범위 가")
    refused("ghg_nodes_root_name_unique_alive", lambda: node("scope", "범위 가"))
    GhgIndexNode.objects.filter(pk=first.pk).update(deleted_at=timezone.now())
    node("scope", "범위 가")


def test_leaves_with_empty_names_do_not_clash_by_name(activity: GhgIndexNode) -> None:
    leaf(activity, code("가 보일러"))
    leaf(activity, code("나 보일러"))  # 잎의 이름은 빈 글자 — 이름 unique 밖
    assert GhgIndexNode.objects.filter(level="facility").count() == 2


def test_a_code_is_unique_under_an_activity_among_the_alive(activity: GhgIndexNode) -> None:
    boiler = code("가 보일러")
    first = leaf(activity, boiler)
    refused("ghg_nodes_code_unique_alive", lambda: leaf(activity, boiler))
    other = node("activity", "활동 나", activity.parent)
    leaf(other, boiler)  # 짝: 다른 활동 아래
    GhgIndexNode.objects.filter(pk=first.pk).update(deleted_at=timezone.now())
    leaf(activity, boiler)  # 짝: 지운 잎의 코드는 다시 쓴다


def test_a_seed_key_is_unique(activity: GhgIndexNode) -> None:
    node("scope", "범위 나", seed_key="k1")
    refused("ghg_nodes_seed_key_unique", lambda: node("scope", "범위 다", seed_key="k1"))
    node("scope", "범위 라")
    node("scope", "범위 마")  # 짝: NULL 은 여럿


def test_a_used_code_cannot_be_hard_deleted(activity: GhgIndexNode) -> None:
    """코드 FK 는 PROTECT — ORM 을 비껴 지워도 DB 가 23503 으로 막는다."""
    boiler = code("가 보일러")
    leaf(activity, boiler)

    def delete_raw() -> None:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM organization_facility_codes WHERE id = %s", [boiler])
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    assert sqlstate_of(delete_raw) == "23503"
    assert boiler in alive_codes([boiler])


def test_no_pool_table_has_a_company_column_or_a_company_key() -> None:
    """공통 표 넷: 회사 칸 0 · 외래 키가 가리키는 것은 풀 표와 공통 코드 목록뿐(organization.Company 0 — 검증 R2)."""
    targets: set[str] = set()
    for model in (GhgIndexNode, GhgFactor, GhgFactorVersion, GhgFactorGas):
        fields = model._meta.concrete_fields
        assert not [field.attname for field in fields if "compan" in field.attname], model.__name__
        targets |= {field.related_model._meta.label for field in fields if field.is_relation and field.related_model}
    assert targets == {
        "inventory.GhgIndexNode",
        "inventory.GhgFactor",
        "inventory.GhgFactorVersion",
        "organization.FacilityCode",
    }


# ── 계수 ─────────────────────────────────────────────────────────────


def test_one_default_among_the_alive_factors_of_a_leaf(activity: GhgIndexNode) -> None:
    boiler = leaf(activity, code("가 보일러"))
    first = GhgFactor.objects.create(facility_node=boiler, is_default=True)
    refused("ghg_factors_one_default_alive", lambda: GhgFactor.objects.create(facility_node=boiler, is_default=True))
    GhgFactor.objects.create(facility_node=boiler)  # 짝: 기본 아닌 것은 여럿
    other = leaf(activity, code("나 보일러"))
    GhgFactor.objects.create(facility_node=other, is_default=True)  # 짝: 다른 잎
    GhgFactor.objects.filter(pk=first.pk).update(is_default=False, deleted_at=timezone.now())
    GhgFactor.objects.create(facility_node=boiler, is_default=True)  # 짝: 지운 뒤 새 기본


def test_a_deleted_factor_is_not_the_default(activity: GhgIndexNode) -> None:
    boiler = leaf(activity, code("가 보일러"))
    refused(
        "ghg_factors_default_alive",
        lambda: GhgFactor.objects.create(facility_node=boiler, is_default=True, deleted_at=timezone.now()),
    )
    GhgFactor.objects.create(facility_node=boiler, deleted_at=timezone.now())  # 짝


def test_a_factor_version_starts_at_one_and_seed_key_is_unique(activity: GhgIndexNode) -> None:
    boiler = leaf(activity, code("가 보일러"))
    refused("ghg_factors_version_positive", lambda: GhgFactor.objects.create(facility_node=boiler, current_version=0))
    GhgFactor.objects.create(facility_node=boiler, seed_key="k1")
    refused("ghg_factors_seed_key_unique", lambda: GhgFactor.objects.create(facility_node=boiler, seed_key="k1"))


# ── 판·가스 ──────────────────────────────────────────────────────────


@pytest.fixture
def factor(activity: GhgIndexNode) -> GhgFactor:
    return GhgFactor.objects.create(facility_node=leaf(activity, code("가 보일러")), is_default=True)


def test_a_version_number_is_unique_per_factor(factor: GhgFactor) -> None:
    GhgFactorVersion.objects.create(factor=factor, **version_fields())
    refused("ghg_factor_versions_unique", lambda: GhgFactorVersion.objects.create(factor=factor, **version_fields()))
    GhgFactorVersion.objects.create(factor=factor, **version_fields(version=2))  # 짝
    refused(
        "ghg_factor_versions_version_positive",
        lambda: GhgFactorVersion.objects.create(factor=factor, **version_fields(version=0)),
    )


@pytest.mark.parametrize(("fields", "constraint"), [
    ({"tier": 4}, "ghg_factor_versions_tier_check"),
    ({"base_year": 1989}, "ghg_factor_versions_base_year_range"),
    ({"base_year": 2101}, "ghg_factor_versions_base_year_range"),
    ({"ncv_enabled": True}, "ghg_factor_versions_ncv_consistent"),
    ({"ncv": Decimal("1")}, "ghg_factor_versions_ncv_consistent"),
    ({"ncv_enabled": True, "ncv": Decimal("1"), "ncv_unit_kind": "energy"}, "ghg_factor_versions_ncv_consistent"),
    (
        {"ncv_enabled": True, "ncv": Decimal("0"), "ncv_unit_kind": "energy", "ncv_unit": "MJ"},
        "ghg_factor_versions_ncv_positive",
    ),
])  # fmt: skip
def test_a_version_is_refused_out_of_rule(factor: GhgFactor, fields: dict[str, Any], constraint: str) -> None:
    refused(constraint, lambda: GhgFactorVersion.objects.create(factor=factor, **version_fields(**fields)))


def test_a_version_within_the_rules_is_taken(factor: GhgFactor) -> None:
    on = {"ncv_enabled": True, "ncv": Decimal("12.34"), "ncv_unit_kind": "energy", "ncv_unit": "MJ"}
    GhgFactorVersion.objects.create(factor=factor, **version_fields(tier=3, base_year=1990, **on))
    row = GhgFactorVersion.objects.create(factor=factor, **version_fields(version=2, base_year=2100))
    row.refresh_from_db()
    assert (row.emission_unit_kind, row.emission_unit, row.seed_record_ids, row.note) == ("mass", "tCO2-eq", [], "")


def test_gases_are_seven_names_once_per_version_and_enabled_ones_carry_values(factor: GhgFactor) -> None:
    version = GhgFactorVersion.objects.create(factor=factor, **version_fields())
    for gas in GASES:
        GhgFactorGas.objects.create(factor_version=version, gas=gas)  # 짝: 끈 줄은 값이 없어도 된다
    refused("ghg_factor_gases_unique", lambda: GhgFactorGas.objects.create(factor_version=version, gas="CO2"))
    other = GhgFactorVersion.objects.create(factor=factor, **version_fields(version=2))
    refused("ghg_factor_gases_gas_check", lambda: GhgFactorGas.objects.create(factor_version=other, gas="H2O"))
    for factor_value, gwp in ((None, Decimal("1")), (Decimal("1"), None), (Decimal("0"), Decimal("1"))):
        refused(
            "ghg_factor_gases_enabled_values",
            lambda f=factor_value, g=gwp: GhgFactorGas.objects.create(
                factor_version=other, gas="CO2", enabled=True, factor=f, gwp=g
            ),
        )
    refused(
        "ghg_factor_gases_enabled_values",
        lambda: GhgFactorGas.objects.create(
            factor_version=other, gas="CO2", enabled=True, factor=Decimal("1"), gwp=Decimal("0")
        ),
    )
    GhgFactorGas.objects.create(factor_version=other, gas="CO2", enabled=True, factor=Decimal("1"), gwp=Decimal("1"))


def test_decimals_keep_twelve_places(factor: GhgFactor) -> None:
    version = GhgFactorVersion.objects.create(factor=factor, **version_fields())
    gas = GhgFactorGas.objects.create(
        factor_version=version, gas="CH4", enabled=True, factor=Decimal("0.000000000001"), gwp=Decimal("1" * 18)
    )
    gas.refresh_from_db()
    assert (gas.factor, gas.gwp) == (Decimal("0.000000000001"), Decimal("1" * 18))


def test_the_partial_unique_indexes_carry_their_conditions() -> None:
    """부분 unique 의 조건은 글자로 잰다 — 「기본 하나」 의 deleted_at 조건은 CHECK(ghg_factors_default_alive)와 겹쳐
    행으로는 빨개지지 않는다(심은 고장 P2)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename IN ('ghg_index_nodes', 'ghg_factors')"
            " AND indexdef LIKE 'CREATE UNIQUE INDEX %%' AND indexname NOT LIKE '%%_pkey'"
        )
        found = {name: definition.split(" USING btree ", 1)[1] for name, definition in cursor.fetchall()}
    assert found == {
        "ghg_nodes_name_unique_alive": (
            "(parent_id, name) WHERE ((deleted_at IS NULL) AND (NOT ((level)::text = 'facility'::text)))"
        ),
        "ghg_nodes_root_name_unique_alive": "(name) WHERE ((deleted_at IS NULL) AND (parent_id IS NULL))",
        "ghg_nodes_code_unique_alive": "(parent_id, facility_code_id) WHERE (deleted_at IS NULL)",
        "ghg_nodes_seed_key_unique": "(seed_key) WHERE (seed_key IS NOT NULL)",
        "ghg_factors_one_default_alive": "(facility_node_id) WHERE ((deleted_at IS NULL) AND is_default)",
        "ghg_factors_seed_key_unique": "(seed_key) WHERE (seed_key IS NOT NULL)",
    }
