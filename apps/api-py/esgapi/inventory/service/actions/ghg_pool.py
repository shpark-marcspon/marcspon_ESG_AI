"""온실가스 풀의 유스케이스 — 잎 만들기·저장, 계수 만들기·고치기, 노드·계수 일괄 지우기. 밴드 K1b-2a ②. HTTP 를 모른다.

함수마다 `@transaction.atomic` 하나: 표 하나씩 쓰는 services 함수를 한 트랜잭션에서 부른다(TWO_TABLE_FUNCTIONS 0).
첫 문장이 권한 표를 다시 읽는다(경로의 permitted 에 더해 — ALSO_INSIDE). 판정은 쓰기 전에 selectors 로 다 한다
(없는·삭제된 id 404 · 단 어긋남·겹침·검사 422 · 자식 있음·사용 중 409 — 하나라도 걸리면 아무것도 쓰지 않는다).
쓴 뒤 경합(제약)으로 services 가 갈래를 돌려주면 이 트랜잭션을 되돌리고(set_rollback) 그 갈래를 돌려준다 — 일부만 0.
★ 도메인을 넘는 것(시설 코드가 살아 있는가 — organization 의 selectors)은 여기서만 부른다(services·selectors 는 남의
  도메인 import 0 — .importlinter 바).
★ services 는 모듈 이름으로 부른다(services.insert_factor_version — 시험이 둘째 부름에 실패를 심는다).
★ 사용 중 판정(nodes_in_use·factors_in_use)은 고객사 인덱스 선택이 잎·잡은 판을 쓰는가다(K1b-2b ④ — sid:MARC-ISSUE-432).
  inventory 의 selectors/index_selection.py 가 모델의 이름 붙은 입구로 풀 id 집합만 돌려준다(회사 정보 0). 입력값이
  쓰는 것은 S12a(sid:MARC-ISSUE-418). 시험은 기본 인자 자리에 가짜도 넘긴다.
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from django.db import transaction

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import is_allowed
from esgapi.inventory.data_loader import read_data
from esgapi.inventory.service.selectors import ghg_pool as selectors
from esgapi.inventory.service.selectors import index_selection as index_selectors
from esgapi.inventory.service.services import ghg_pool as services
from esgapi.inventory.service.utils.ghg_pool import (
    FacilityView,
    FactorDraft,
    FactorValues,
    FactorView,
    Forbidden,
    HasChildren,
    InUse,
    Invalid,
    NodeView,
    NotFound,
    SeedFactor,
    SeedRecord,
    check_facility,
    check_factor,
    seed_factor,
)
from esgapi.organization.service.permissions.organization import Forbidden as CodesForbidden
from esgapi.organization.service.selectors.facility_codes import alive_codes, selectable_codes
from esgapi.organization.service.services.branches import InUse as CodesInUse
from esgapi.organization.service.services.facility_codes import CodesMissing, create_code, delete_codes
from esgapi.organization.service.utils.entities import FacilityCodeInfo
from esgapi.reference.service.selectors.reference import records_for_assembly

CODE_GONE = "없거나 지운 자산/시설 코드다"
DELETED_SEED_NODE = (
    "지운 씨앗 노드 — 아래 건너뜀"  # R9: 관리자가 지운 씨앗 노드는 되살리지 않고 그 아래를 통째로 건너뛴다
)

FacilityRefused = NotFound | Invalid | Forbidden
FactorRefused = NotFound | Invalid | Forbidden


def _code_problem(parent_id: int, facility_code_id: int, *, keep: int | None, except_id: int | None) -> Invalid | None:
    """새로 고른 코드가 살아 있고 같은 활동 아래 겹치지 않는가. 이미 쓰는 코드를 그대로 두면 지워졌어도 된다."""
    if facility_code_id != keep and facility_code_id not in alive_codes([facility_code_id]):
        return Invalid({"facilityCodeId": CODE_GONE})
    if selectors.code_taken(parent_id, facility_code_id, except_id=except_id):
        return Invalid({"facilityCodeId": services.CODE_TAKEN})
    return None


@transaction.atomic
def create_facility(
    *,
    actor_kind: Kind,
    parent_id: int,
    facility_code_id: int,
    unit: tuple[str, str] | None,
    tooltip: str,
    seed_key: str | None = None,
) -> FacilityView | FacilityRefused:
    """열 4(자산/시설) 잎 하나 — 부모는 배출활동, 코드는 공통 목록의 살아 있는 것."""
    if not is_allowed("inventory_admin_ghg_facilities_create", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_facilities_create")
    errors = check_facility(unit, tooltip)
    if errors or unit is None:
        return Invalid(errors)
    parent = selectors.lock_nodes([parent_id]).get(parent_id)  # 부모 잠금 — 같은 부모 지우기와 줄을 선다(R6)
    if parent is None:
        return NotFound()
    if parent.level != "activity":
        return Invalid({"parentId": "자산/시설은 배출활동 아래에 만든다"})
    problem = _code_problem(parent_id, facility_code_id, keep=None, except_id=None)
    if problem is not None:
        return problem
    made = services.insert_leaf(
        actor_kind=actor_kind,
        operation_id="inventory_admin_ghg_facilities_create",
        parent_id=parent_id,
        facility_code_id=facility_code_id,
        unit=unit,
        tooltip=tooltip,
        seed_key=seed_key,
    )
    if not isinstance(made, int):
        transaction.set_rollback(True)
        return made
    return selectors.facility_detail(actor_kind=actor_kind, node_id=made)


@transaction.atomic
def save_facility(
    *,
    actor_kind: Kind,
    node_id: int,
    facility_code_id: int,
    unit: tuple[str, str] | None,
    tooltip: str,
    default_factor_id: int | None,
    nodes_in_use: Callable[[Collection[int]], frozenset[int]] = index_selectors.nodes_in_use,
) -> FacilityView | FacilityRefused | InUse:
    """잎 저장(PUT) — 코드·1차 단위·툴팁, defaultFactorId 가 있으면 기본 바꾸기(그 잎의 삭제 안 된 계수만).
    어느 회사든 고른 잎이면 코드·1차 단위는 못 바꾼다(409 in_use — 감독 판단 8). 툴팁·기본 바꾸기는 된다."""
    if not is_allowed("inventory_admin_ghg_facilities_save", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_facilities_save")
    op = "inventory_admin_ghg_facilities_save"
    errors = check_facility(unit, tooltip)
    if errors or unit is None:
        return Invalid(errors)
    found = selectors.lock_nodes([node_id]).get(node_id)  # 잎 잠금 — 기본 바꾸기·첫 계수·승계가 줄을 선다(B1)
    if found is None or found.level != "facility" or found.parent_id is None:
        return NotFound()
    problem = _code_problem(found.parent_id, facility_code_id, keep=found.facility_code_id, except_id=node_id)
    if problem is not None:
        return problem
    changes_meaning = facility_code_id != found.facility_code_id or unit != selectors.leaf_unit(node_id)
    if changes_meaning and nodes_in_use([node_id]):  # 잎 잠금 뒤 — 회사 선택은 잎 잠금(lock_nodes)과 줄 선다
        return InUse(frozenset({node_id}))
    if default_factor_id is not None:
        target = selectors.alive_factors([default_factor_id]).get(default_factor_id)
        if target is None or target.facility_node_id != node_id:
            return Invalid({"defaultFactorId": "이 자산/시설의 삭제 안 된 계수가 아니다"})
    saved = services.update_leaf(
        actor_kind=actor_kind,
        operation_id=op,
        node_id=node_id,
        facility_code_id=facility_code_id,
        unit=unit,
        tooltip=tooltip,
    )
    if saved is not None:
        transaction.set_rollback(True)
        return saved
    if default_factor_id is not None:
        switched = services.set_default_factor(
            actor_kind=actor_kind, operation_id=op, facility_node_id=node_id, factor_id=default_factor_id
        )
        if switched is not None:
            transaction.set_rollback(True)
            return switched
    return selectors.facility_detail(actor_kind=actor_kind, node_id=node_id)


def _write_version(
    *,
    actor_kind: Kind,
    op: str,
    factor_id: int,
    version: int,
    values: FactorValues,
    seed_record_ids: Collection[str],
    seed_gwp_set_id: str | None,
) -> Forbidden | None:
    """판 한 줄 + 가스 일곱 줄(블록 안에서만 부른다)."""
    version_id = services.insert_factor_version(
        actor_kind=actor_kind,
        operation_id=op,
        factor_id=factor_id,
        version=version,
        values=values,
        seed_record_ids=list(seed_record_ids),
        seed_gwp_set_id=seed_gwp_set_id,
    )
    if not isinstance(version_id, int):
        return version_id
    written = services.insert_factor_gases(
        actor_kind=actor_kind, operation_id=op, version_id=version_id, gases=values.gases
    )
    return written if isinstance(written, Forbidden) else None


@transaction.atomic
def create_factor(
    *,
    actor_kind: Kind,
    node_id: int,
    draft: FactorDraft,
    seed_key: str | None = None,
    seed_record_ids: Collection[str] = (),
    seed_gwp_set_id: str | None = None,
) -> FactorView | FactorRefused:
    """잎의 계수 하나 = 정체 + 판 1 + 가스 일곱. 그 잎의 첫 계수(삭제 안 된 것 0)면 기본."""
    if not is_allowed("inventory_admin_ghg_factors_create", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_factors_create")
    op = "inventory_admin_ghg_factors_create"
    found = selectors.lock_nodes([node_id]).get(node_id)  # 잎 잠금 — 「첫 계수 = 기본」 판정이 겹치지 않는다(B1)
    if found is None or found.level != "facility":
        return NotFound()
    values = check_factor(draft)
    if not isinstance(values, FactorValues):
        return Invalid(values)
    first = not selectors.alive_factors_of([node_id])
    factor_id = services.insert_factor(
        actor_kind=actor_kind, operation_id=op, facility_node_id=node_id, is_default=first, seed_key=seed_key
    )
    if not isinstance(factor_id, int):
        transaction.set_rollback(True)
        return factor_id
    written = _write_version(
        actor_kind=actor_kind,
        op=op,
        factor_id=factor_id,
        version=1,
        values=values,
        seed_record_ids=seed_record_ids,
        seed_gwp_set_id=seed_gwp_set_id,
    )
    if written is not None:
        transaction.set_rollback(True)
        return written
    return selectors.factor_version(actor_kind=actor_kind, factor_id=factor_id, version=None)


@transaction.atomic
def save_factor(*, actor_kind: Kind, factor_id: int, draft: FactorDraft) -> FactorView | FactorRefused:
    """계수 고치기 = 정체 잠금 → current_version + 1 → 새 판 + 가스 일곱. 옛 판은 글자 그대로 남는다.
    바뀐 것이 없어도 새 판을 만든다[우리 해석 — 저장 = 판 하나]."""
    if not is_allowed("inventory_admin_ghg_factors_save", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_factors_save")
    op = "inventory_admin_ghg_factors_save"
    values = check_factor(draft)
    if not isinstance(values, FactorValues):
        return Invalid(values)
    if selectors.lock_factor(factor_id) is None:
        return NotFound()
    version = services.bump_factor_version(actor_kind=actor_kind, operation_id=op, factor_id=factor_id)
    if not isinstance(version, int):
        transaction.set_rollback(True)
        return version
    written = _write_version(
        actor_kind=actor_kind,
        op=op,
        factor_id=factor_id,
        version=version,
        values=values,
        seed_record_ids=(),
        seed_gwp_set_id=None,
    )
    if written is not None:
        transaction.set_rollback(True)
        return written
    return selectors.factor_version(actor_kind=actor_kind, factor_id=factor_id, version=None)


@transaction.atomic
def delete_nodes(
    *,
    actor_kind: Kind,
    ids: Collection[int],
    nodes_in_use: Callable[[Collection[int]], frozenset[int]] = index_selectors.nodes_in_use,
    factors_in_use: Callable[[Collection[int]], frozenset[int]] = index_selectors.factors_in_use,
) -> int | NotFound | HasChildren | InUse | Forbidden:
    """노드 여럿을 삭제 표시한다(잎이면 그 계수도). 하나라도 없거나 지웠으면 404, 요청 밖의 삭제 안 된 자식이 있으면
    409 has_children(아래부터 지운다 — 같은 요청에 자식도 있으면 된다), 쓰이는 것이 있으면 409 in_use."""
    if not is_allowed("inventory_admin_ghg_nodes_delete", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_nodes_delete")
    op = "inventory_admin_ghg_nodes_delete"
    wanted = set(ids)
    found = selectors.lock_nodes(wanted)  # 지울 노드 잠금 — 그 아래 만들기와 줄을 선다(R6)
    if not wanted or set(found) != wanted:
        return NotFound()
    blocked = frozenset(
        parent for parent, children in selectors.with_alive_children(wanted).items() if children - wanted
    )
    if blocked:
        return HasChildren(blocked)
    used = nodes_in_use(wanted)
    if used:
        return InUse(used)
    leaves = [node.id for node in found.values() if node.level == "facility"]
    factors = [factor.id for factor in selectors.alive_factors_of(leaves)]
    pinned = factors_in_use(factors)  # 잎의 계수 판을 회사가 잡았다(L3 — 잎은 안 골랐어도)
    if pinned:
        return InUse(pinned)
    if factors:
        cleared = services.mark_factors_deleted(actor_kind=actor_kind, operation_id=op, ids=factors)
        if not isinstance(cleared, int):
            transaction.set_rollback(True)
            return cleared
    deleted = services.mark_nodes_deleted(actor_kind=actor_kind, operation_id=op, ids=wanted)
    if not isinstance(deleted, int):
        transaction.set_rollback(True)
    return deleted


@transaction.atomic
def delete_factors(
    *,
    actor_kind: Kind,
    ids: Collection[int],
    factors_in_use: Callable[[Collection[int]], frozenset[int]] = index_selectors.factors_in_use,
) -> int | NotFound | InUse | Invalid | Forbidden:
    """계수 여럿을 삭제 표시한다. 하나라도 없거나 지웠으면 404, 쓰이는 것이 있으면 409. 기본을 지운 잎은 남은 첫 행
    (sort_order → id)이 기본을 잇는다(「삭제 안 된 계수가 있으면 기본 정확히 하나」)."""
    if not is_allowed("inventory_admin_ghg_factors_delete", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_factors_delete")
    op = "inventory_admin_ghg_factors_delete"
    wanted = set(ids)
    seen = selectors.alive_factors(wanted)
    selectors.lock_nodes({factor.facility_node_id for factor in seen.values()})  # 잎 잠금 — 승계가 겹치지 않는다(B1)
    found = selectors.alive_factors(wanted)  # 잠근 뒤 다시 읽는다
    if not wanted or set(found) != wanted:
        return NotFound()
    used = factors_in_use(wanted)
    if used:
        return InUse(used)
    orphaned = {factor.facility_node_id for factor in found.values() if factor.is_default}
    deleted = services.mark_factors_deleted(actor_kind=actor_kind, operation_id=op, ids=wanted)
    if not isinstance(deleted, int):
        transaction.set_rollback(True)
        return deleted
    for heir in _first_alive_per_node(orphaned):
        switched = services.set_default_factor(
            actor_kind=actor_kind, operation_id=op, facility_node_id=heir[0], factor_id=heir[1]
        )
        if switched is not None:
            transaction.set_rollback(True)
            return switched
    return deleted


def _first_alive_per_node(node_ids: Collection[int]) -> list[tuple[int, int]]:
    """잎마다 남은 첫 계수(sort_order → id) — (잎, 계수)."""
    heirs: dict[int, int] = {}
    for factor in selectors.alive_factors_of(node_ids):
        heirs.setdefault(factor.facility_node_id, factor.id)
    return sorted(heirs.items())


# ── ⓕ 씨앗(manage.py seed_ghg_pool) ─────────────────────────────────


@dataclass
class SeedReport:
    """단마다 만든 수·이미 있던 수, 계수 묶음마다 건너뛴 까닭."""

    made: dict[str, int] = field(default_factory=lambda: dict.fromkeys(("node", "facility", "factor", "code"), 0))
    existing: dict[str, int] = field(default_factory=lambda: dict.fromkeys(("node", "facility", "factor"), 0))
    skipped: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])


def load_seed_records(source_ids: Sequence[str]) -> dict[str, SeedRecord]:
    """reference 의 낱줄(읽기만 — sid:MARC-ENT-463) → 씨앗이 읽는 칸. 시험은 이 함수를 바꿔 끼운다."""
    return {
        record.id: SeedRecord(
            id=record.id,
            value_raw=record.value_raw,
            unit_numerator=record.unit_numerator,
            unit_denominator=record.unit_denominator,
            gas=record.gas,
        )
        for record in records_for_assembly(source_ids)
    }


def gwp_values(gwp_set_id: str) -> dict[str, str] | None:
    """gwp-sets.json 의 그 세트 값(글자). 없는 세트면 None."""
    sets: Any = read_data("gwp-sets.json")["gwpSets"]
    for found in sets:
        if found["id"] == gwp_set_id:
            return {gas: str(value) for gas, value in found["values"].items()}
    return None


def mass_to_kg() -> dict[str, str]:
    """unit-conversions.json 의 「<질량> → kg」 값(정의값 — 새 수치 0)."""
    rows: Any = read_data("unit-conversions.json")["unitConversions"]
    return {row["from"]: str(row["factor"]) for row in rows if row["to"] == "kg"}


def _seed_node(
    report: SeedReport,
    *,
    actor_kind: Kind,
    level: str,
    parent_id: int | None,
    name: str,
    key: str,
    known: dict[str, tuple[int, bool]],
) -> int | None:
    if key in known:
        node_id, deleted = known[key]
        if deleted:  # R9: 아래 하나하나를 「만들지 못했다」 로 세지 않고 한 줄만
            report.skipped.append((key, DELETED_SEED_NODE))
            return None
        report.existing["node"] += 1
        return node_id
    made = services.create_node(actor_kind=actor_kind, level=level, parent_id=parent_id, name=name, seed_key=key)
    if not isinstance(made, NodeView):
        raced = _raced_node(key)
        if raced is not None:
            report.existing["node"] += 1
            return raced
        report.skipped.append((key, f"노드를 만들지 못했다: {made!r}"))
        return None
    report.made["node"] += 1
    return made.id


def _raced_node(key: str) -> int | None:
    """만들기가 거절된 씨앗 노드를 그새 다른 씨앗이 넣었나(seedKey 갈래 — 이름·코드 겹침이 먼저 걸려도). 있으면 id."""
    found = selectors.seeded_nodes([key]).get(key)
    return None if found is None else found[0]


def _code_id(report: SeedReport, name: str, codes: dict[str, int]) -> int | None:
    """시설 코드는 이름으로 — 있으면 그대로, 없으면 organization 의 공통 목록에 만든다."""
    if name not in codes:
        made = create_code(actor_kind="admin", name=name)
        if not isinstance(made, FacilityCodeInfo):
            report.skipped.append((name, f"시설 코드를 만들지 못했다: {made!r}"))
            return None
        codes[name] = made.id
        report.made["code"] += 1
    return codes[name]


@transaction.atomic
def seed_pool(
    *, actor_kind: Kind, plan: Mapping[str, Any], gwp_set_id: str, dry_run: bool = False
) -> SeedReport | Invalid | Forbidden:
    """씨앗 파일(plan)로 풀을 채운다 — **멱등**: 씨앗 열쇠(seed_key)가 있는 노드·계수는 건드리지 않는다(관리자가 고친
    것을 덮지 않는다). 값은 reference 낱줄의 value_raw·gwp-sets.json 에서만(수치 0 — 씨앗 파일에 값 칸이 없다).
    회사 데이터 0. dry_run 이면 이 트랜잭션을 되돌린다."""
    if not is_allowed("inventory_admin_ghg_nodes_create", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_nodes_create")
    gwp = gwp_values(gwp_set_id)
    if gwp is None:
        return Invalid({"gwpSet": f"gwp-sets.json 에 {gwp_set_id} 가 없다"})
    records = load_seed_records(list(plan["sources"]))
    conversions = mass_to_kg()
    report = SeedReport()
    known = selectors.seeded_nodes(_node_keys(plan))
    seeded = selectors.seeded_factors(_factor_keys(plan))
    codes = {code.name: code.id for code in selectable_codes()}
    for scope in plan["tree"]:
        scope_id = _seed_node(
            report,
            actor_kind=actor_kind,
            level="scope",
            parent_id=None,
            name=scope["name"],
            key=scope["key"],
            known=known,
        )
        for kind in scope["children"] if scope_id is not None else ():
            kind_key = f"{scope['key']}/{kind['key']}"
            kind_id = _seed_node(
                report, actor_kind=actor_kind, level="source_type", parent_id=scope_id, name=kind["name"], key=kind_key,
                known=known,
            )  # fmt: skip
            for act in kind["children"] if kind_id is not None else ():
                act_key = f"{kind_key}/{act['key']}"
                act_id = _seed_node(
                    report, actor_kind=actor_kind, level="activity", parent_id=kind_id, name=act["name"], key=act_key,
                    known=known,
                )  # fmt: skip
                for leaf in act["facilities"] if act_id is not None else ():
                    _seed_leaf(report, actor_kind, act_id, f"{act_key}/{leaf['code']}", leaf, records, gwp, gwp_set_id,
                               conversions, known, seeded, codes)  # fmt: skip
    if dry_run:
        transaction.set_rollback(True)
    return report


def _seed_leaf(
    report: SeedReport,
    actor_kind: Kind,
    act_id: int | None,
    key: str,
    leaf: Mapping[str, Any],
    records: Mapping[str, SeedRecord],
    gwp: Mapping[str, str],
    gwp_set_id: str,
    conversions: Mapping[str, str],
    known: dict[str, tuple[int, bool]],
    seeded: frozenset[str],
    codes: dict[str, int],
) -> None:
    unit = (str(leaf["unit"]["kind"]), str(leaf["unit"]["unit"]))
    if key in known and known[key][1]:  # R9: 지운 씨앗 잎 — 그 계수도 건너뜀
        report.skipped.append((key, DELETED_SEED_NODE))
        return
    if key in known:
        report.existing["facility"] += 1
        leaf_id = known[key][0]
    else:
        code_id = _code_id(report, str(leaf["code"]), codes)
        if code_id is None or act_id is None:
            return
        made = create_facility(
            actor_kind=actor_kind, parent_id=act_id, facility_code_id=code_id, unit=unit, tooltip="", seed_key=key
        )
        raced = None if isinstance(made, FacilityView) else _raced_node(key)
        if raced is not None:
            report.existing["facility"] += 1
            leaf_id = raced
        elif not isinstance(made, FacilityView):
            report.skipped.append((key, f"잎을 만들지 못했다: {made!r}"))
            return
        else:
            report.made["facility"] += 1
            leaf_id = made.id
    for spec in leaf["factors"]:
        built = seed_factor(spec, leaf_key=key, input_unit=unit, records=records, gwp=gwp, mass_to_kg=conversions)
        if not isinstance(built, SeedFactor):
            report.skipped.append((built.seed_key, built.reason))
            continue
        if built.seed_key in seeded:
            report.existing["factor"] += 1
            continue
        made_factor = create_factor(
            actor_kind=actor_kind,
            node_id=leaf_id,
            draft=built.draft,
            seed_key=built.seed_key,
            seed_record_ids=built.record_ids,
            seed_gwp_set_id=gwp_set_id,
        )
        if isinstance(made_factor, Invalid) and "seedKey" in made_factor.fields:  # 경합으로 먼저 섰다 — 멱등
            report.existing["factor"] += 1
            continue
        if not isinstance(made_factor, FactorView):
            report.skipped.append((built.seed_key, f"계수를 만들지 못했다: {made_factor!r}"))
            continue
        report.made["factor"] += 1


def _node_keys(plan: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    for scope in plan["tree"]:
        keys.append(scope["key"])
        for kind in scope["children"]:
            kind_key = f"{scope['key']}/{kind['key']}"
            keys.append(kind_key)
            for act in kind["children"]:
                act_key = f"{kind_key}/{act['key']}"
                keys.append(act_key)
                keys += [f"{act_key}/{leaf['code']}" for leaf in act["facilities"]]
    return keys


def _factor_keys(plan: Mapping[str, Any]) -> list[str]:
    return [f"{key}#{spec['key']}" for key, leaf in _leaves(plan) for spec in leaf["factors"]]


def _leaves(plan: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    found: list[tuple[str, Mapping[str, Any]]] = []
    for scope in plan["tree"]:
        for kind in scope["children"]:
            for act in kind["children"]:
                act_key = f"{scope['key']}/{kind['key']}/{act['key']}"
                found += [(f"{act_key}/{leaf['code']}", leaf) for leaf in act["facilities"]]
    return found


# ── ⓖ 옛 씨앗 지우기(manage.py retire_ghg_seed — S12S1, 결정 MARC-ENT-676) ─────────────
# 씨앗은 멱등이라 옛 잎을 지우지 않는다. 씨앗 파일의 retired(옛 씨앗 노드 열쇠)를 세고, 셈이 전부 0 일 때만 있는 길
# delete_nodes·delete_codes(삭제 표시)로 옛 노드·그 계수·옛 잎의 시설 코드를 지운다. 회사 정보 0: 쓰임은 풀 id·코드 id
# 집합만 돌려주는 판정(nodes_in_use·factors_in_use · 사업장 판정 — 이것은 명령이 organization 에서 넘긴다, 기본값
# 없음)으로.
# ★ 옛 씨앗 열쇠는 지움 목록에만 — 새 씨앗 열쇠로 다시 쓰지 않는다(R9 가 지운 씨앗 노드 아래를 건너뛴다).
# ★ 지울 옛 코드 = 옛 잎(삭제 표시 포함)의 살아 있는 코드 가운데 다른 살아 있는 잎이 안 쓰는 것. 다른 잎이 쓰는 코드는
#   남기고 상태는 바꾸지 않는다. 사업장 셈은 지울 옛 코드에 대해서만 — 1 이상이면 blocked(덧 2, MARC-ENT-676).


@dataclass
class RetireReport:
    """옛 씨앗 셈(수만 — 회사 이름·id 0)과 상태 nothing(지울 것 없음)·ready(지울 수 있음)·blocked·done."""

    alive: int = 0  # 살아 있는 옛 씨앗 노드
    gone: int = 0  # 이미 지웠거나 없는 옛 씨앗 열쇠
    leaves_in_use: int = 0  # 회사 선택이 고른 옛 잎(숨김 포함)
    factors_in_use: int = 0  # 회사가 판을 잡았거나 입력 행이 덮어쓴 옛 잎의 계수
    foreign_children: int = 0  # 옛 노드 아래 씨앗 밖 살아 있는 자식(관리자가 더한 잎)
    foreign_factors: int = 0  # 옛 잎의 씨앗 아닌 계수(관리자가 더함)
    edited_factors: int = 0  # 고친 씨앗 계수(current_version ≥ 2)
    codes_on_sites: int = 0  # 지울 옛 코드 가운데 사업장 자산/시설(어느 회사든)이 쓰는 코드 수
    codes: int = 0  # 지울 옛 코드(옛 잎의 살아 있는 코드 − 다른 살아 있는 잎이 쓰는 것)
    codes_on_leaves: int = 0  # 옛 코드를 다른 살아 있는 잎(새 씨앗·관리자 잎)이 써서 남는 것 — 상태와 무관
    state: str = "nothing"
    deleted_nodes: int = 0
    deleted_codes: int = 0

    @property
    def blockers(self) -> int:
        used = self.leaves_in_use + self.factors_in_use + self.codes_on_sites
        return used + self.foreign_children + self.foreign_factors + self.edited_factors


# delete_codes 의 갈래는 organization 의 꼴이다(같은 이름의 Forbidden·InUse — 코드 id).
RetireRefused = Invalid | Forbidden | NotFound | HasChildren | InUse | CodesMissing | CodesInUse | CodesForbidden


@transaction.atomic
def retire_seed(
    *,
    actor_kind: Kind,
    plan: Mapping[str, Any],
    codes_on_sites: Callable[[Collection[int]], frozenset[int]],
    apply: bool = False,
    nodes_in_use: Callable[[Collection[int]], frozenset[int]] = index_selectors.nodes_in_use,
    factors_in_use: Callable[[Collection[int]], frozenset[int]] = index_selectors.factors_in_use,
) -> RetireReport | RetireRefused:
    """옛 씨앗(plan["retired"])을 센다. 기본은 셈만(쓰기 0). apply 면 같은 트랜잭션에서 옛 노드를 잠그고(lock_nodes) 그
    계수를 잠근 뒤 센다 — 전부 0 일 때만 delete_nodes(살아 있는 것만 넘김) → delete_codes. 셈이 하나라도 있으면
    blocked · 지움 0. 지우는 중 갈래(경합)가 나면 이 트랜잭션 전체를 되돌리고 그 갈래를 돌려준다.
    codes_on_sites = 사업장 자산/시설이 쓰는 코드 id(organization — 부르는 쪽이 넘긴다, 기본값 없음)."""
    for operation in ("inventory_admin_ghg_nodes_delete", "organization_admin_facility_codes_delete"):
        if not is_allowed(operation, kind=actor_kind):
            return Forbidden(operation)
    given: object = plan.get("retired")
    keys = [key for key in cast("list[object]", given) if isinstance(key, str)] if isinstance(given, list) else []
    if not keys or len(keys) != len(cast("list[object]", given)):
        return Invalid({"retired": "옛 씨앗 노드 열쇠 목록(글자)이 없다"})
    found = selectors.seeded_nodes(keys)
    alive = sorted(node_id for node_id, deleted in found.values() if not deleted)
    if apply:  # 셈 전에 잠근다(덧 3) — 그 아래 만들기·고르기·지우기와 줄을 선다(기다린 사이 지운 것은 빠진다)
        alive = sorted(selectors.lock_nodes(alive))
    report, codes = _retire_count(
        len(keys),
        [node_id for node_id, _ in found.values()],
        alive,
        nodes_in_use=nodes_in_use,
        factors_in_use=factors_in_use,
        codes_on_sites=codes_on_sites,
        lock=apply,
    )
    if not apply or report.state != "ready":
        return report
    if alive:
        deleted = delete_nodes(
            actor_kind=actor_kind, ids=alive, nodes_in_use=nodes_in_use, factors_in_use=factors_in_use
        )
        if not isinstance(deleted, int):
            transaction.set_rollback(True)
            return deleted
        report.deleted_nodes = deleted
    if codes:
        cleared = delete_codes(actor_kind=actor_kind, ids=codes, facility_codes_in_use=codes_on_sites)
        if not isinstance(cleared, int):
            transaction.set_rollback(True)
            return cleared
        report.deleted_codes = cleared
    report.state = "done"
    return report


def _retire_count(
    wanted: int,
    seeded: Collection[int],
    alive: Sequence[int],
    *,
    nodes_in_use: Callable[[Collection[int]], frozenset[int]],
    factors_in_use: Callable[[Collection[int]], frozenset[int]],
    codes_on_sites: Callable[[Collection[int]], frozenset[int]],
    lock: bool,
) -> tuple[RetireReport, list[int]]:
    """셈과 지울 옛 코드 id. 잎은 살아 있는 옛 노드 가운데 facility 단."""
    nodes = selectors.alive_nodes(alive)
    leaves = [node.id for node in nodes.values() if node.level == "facility"]
    marks = selectors.factor_marks(leaves)
    if lock:  # 셈과 지우기 사이에 계수 고치기가 끼지 않게(고치기도 lock_factor) — id 차례로 하나씩
        for mark in marks:
            selectors.lock_factor(mark.id)
        marks = selectors.factor_marks(leaves)
    children = selectors.with_alive_children(alive)
    alive_old_codes = set(alive_codes(set(selectors.leaf_codes(seeded).values())))
    kept = selectors.codes_on_other_leaves(alive_old_codes, except_ids=alive)
    codes = sorted(alive_old_codes - kept)
    report = RetireReport(
        alive=len(alive),
        gone=wanted - len(alive),
        leaves_in_use=len(nodes_in_use(leaves)),
        factors_in_use=len(factors_in_use([mark.id for mark in marks])),
        foreign_children=sum(len(found - set(alive)) for found in children.values()),
        foreign_factors=sum(not mark.seeded for mark in marks),
        edited_factors=sum(mark.seeded and mark.current_version >= 2 for mark in marks),
        codes_on_sites=len(codes_on_sites(codes)) if codes else 0,
        codes=len(codes),
        codes_on_leaves=len(kept),
    )
    report.state = "blocked" if report.blockers else "ready" if alive or codes else "nothing"
    return report, codes
