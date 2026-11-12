"""온실가스 풀의 쓰기 — 운영 관리자만. 밴드 K1b-2a ②. HTTP 를 모른다.

표 하나씩: 함수마다 `with transaction.atomic()` 블록 하나(여러 표는 actions 의 @transaction.atomic 이 이 함수들을 한
트랜잭션에서 부른다 — TWO_TABLE_FUNCTIONS 0). 함수마다 첫 문장이 권한 표를 다시 읽는다(경로의 permitted 에 더해).
경로가 바로 부르는 둘(create_node·rename_node)은 자기 동작 이름으로, actions 가 부르는 것은 받은 operation_id 로.
★ 제약 경합(IntegrityError)은 제약 이름으로 가려 갈래로 바꾼다(모르는 제약은 다시 던진다 — 500). try 는 블록
  **바깥**이다(블록이 저장점이라 바깥 트랜잭션은 산다).
★ 판(ghg_factor_versions)·가스(ghg_factor_gases)는 넣기만 한다(앱 역할에 UPDATE·DELETE 없음 — 0001 의 grant).
  계수 고치기는 정체의 current_version 을 올리고 새 판을 넣는다(옛 판 0 바뀜).
★ 지우기는 삭제 표시(노드·계수). 기본 계수 끔 → 켬은 한 블록 안 두 문장(부분 unique 에 안 걸린다 — 옛 것을 먼저 끈다).
회사 데이터를 읽거나 쓰지 않는다.
"""

from collections.abc import Collection, Sequence

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import is_allowed
from esgapi.inventory.models import GhgFactor, GhgFactorGas, GhgFactorVersion, GhgIndexNode
from esgapi.inventory.service.selectors import ghg_pool as selectors
from esgapi.inventory.service.utils.ghg_pool import (
    LEVELS,
    FactorValues,
    Forbidden,
    GasValues,
    Invalid,
    NodeView,
    NotFound,
    clean_name,
    parent_level,
)

NAME_TAKEN = "같은 부모 아래 같은 이름이 있다"
CODE_TAKEN = "같은 배출활동 아래 같은 자산/시설 코드가 있다"
DEFAULT_RACE = "기본 배출계수가 동시에 바뀌었다 — 다시 불러 저장한다"
SEED_KEY_TAKEN = "같은 씨앗 키가 이미 있다"

_NAME_UNIQUE = ("ghg_nodes_name_unique_alive", "ghg_nodes_root_name_unique_alive")
_CODE_UNIQUE = ("ghg_nodes_code_unique_alive",)
_ONE_DEFAULT = ("ghg_factors_one_default_alive",)
_FACTOR_SEED_KEY = ("ghg_factors_seed_key_unique",)
_NODE_SEED_KEY = ("ghg_nodes_seed_key_unique",)


def constraint_name(exc: IntegrityError) -> str | None:
    """걸린 제약 이름(psycopg 3 의 diag.constraint_name). 알 수 없으면 None."""
    diag = getattr(exc.__cause__, "diag", None)
    return getattr(diag, "constraint_name", None)


def _name_problem(parent_id: int | None, name: str, except_id: int | None = None) -> Invalid | None:
    if selectors.name_taken(parent_id, name, except_id=except_id):
        return Invalid({"name": NAME_TAKEN})
    return None


def create_node(
    *, actor_kind: Kind, level: str, parent_id: int | None, name: str, seed_key: str | None = None
) -> NodeView | Invalid | NotFound | Forbidden:
    """열 1~3(범위·유형·활동)의 노드 하나. 단 규칙: 범위는 부모 없음, 그 밖은 부모 단 = 자기 단 − 1."""
    if not is_allowed("inventory_admin_ghg_nodes_create", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_nodes_create")
    if level not in LEVELS[:3]:
        return Invalid({"level": "열 1~3(scope·source_type·activity)만 만든다 — 잎은 facilities"})
    cleaned = clean_name(name)
    if cleaned is None:
        return Invalid({"name": "이름은 1~100자다"})
    want_parent = parent_level(level)
    if (want_parent is None) != (parent_id is None):
        return Invalid(
            {"parentId": "배출범위는 부모가 없다" if want_parent is None else f"{level} 은 {want_parent} 아래에 만든다"}
        )
    try:
        with transaction.atomic():
            if parent_id is not None:  # 부모 잠금 — 같은 부모를 지우는 일과 줄을 선다(검증 ② R6)
                parent = selectors.lock_nodes([parent_id]).get(parent_id)
                if parent is None:
                    return NotFound()
                if parent.level != want_parent:
                    return Invalid({"parentId": f"{level} 은 {want_parent} 아래에 만든다"})
            problem = _name_problem(parent_id, cleaned)
            if problem is not None:
                return problem
            row = GhgIndexNode.objects.create(level=level, parent_id=parent_id, name=cleaned, seed_key=seed_key)
            GhgIndexNode.objects.filter(pk=row.pk).update(sort_order=row.pk)  # 기본 = 만든 차례
    except IntegrityError as exc:  # 같은 이름(또는 같은 씨앗 키)이 경합으로 먼저 섰다
        hit = constraint_name(exc)
        if hit in _NODE_SEED_KEY:
            return Invalid({"seedKey": SEED_KEY_TAKEN})
        if hit not in _NAME_UNIQUE:
            raise
        return Invalid({"name": NAME_TAKEN})
    return NodeView(id=row.pk, level=level, name=cleaned, parent_id=parent_id, sort_order=row.pk, child_count=0)


def rename_node(*, actor_kind: Kind, node_id: int, name: str) -> NodeView | Invalid | NotFound | Forbidden:
    """열 1~3 노드의 이름 고치기. 잎은 PATCH 로 고치지 않는다(PUT facilities)."""
    if not is_allowed("inventory_admin_ghg_nodes_update", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_nodes_update")
    found = selectors.alive_nodes([node_id]).get(node_id)
    if found is None:
        return NotFound()
    if found.level == "facility":
        return Invalid({"level": "자산/시설은 PUT /admin/ghg-index/facilities/{node_id} 로 고친다"})
    cleaned = clean_name(name)
    if cleaned is None:
        return Invalid({"name": "이름은 1~100자다"})
    problem = _name_problem(found.parent_id, cleaned, except_id=node_id)
    if problem is not None:
        return problem
    try:
        with transaction.atomic():
            changed = GhgIndexNode.objects.filter(pk=node_id, deleted_at__isnull=True).update(
                name=cleaned, updated_at=timezone.now()
            )
    except IntegrityError as exc:
        if constraint_name(exc) not in _NAME_UNIQUE:
            raise
        return Invalid({"name": NAME_TAKEN})
    if not changed:  # 살아 있음을 본 뒤 지워졌다(L2)
        return NotFound()
    listed = selectors.node_list(actor_kind=actor_kind, parent_id=found.parent_id, q=None)
    if isinstance(listed, list):
        for view in listed:
            if view.id == node_id:
                return view
    return NotFound()  # 같은 트랜잭션에서 방금 고친 행이다 — 여기 오지 않는다


def insert_leaf(
    *,
    actor_kind: Kind,
    operation_id: str,
    parent_id: int,
    facility_code_id: int,
    unit: tuple[str, str],
    tooltip: str,
    seed_key: str | None = None,
) -> int | Invalid | Forbidden:
    """잎 하나를 넣는다(판정은 부르는 action 이 끝냈다). 같은 활동 아래 같은 코드 경합은 422 fields.facilityCodeId."""
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    try:
        with transaction.atomic():
            row = GhgIndexNode.objects.create(
                level="facility",
                parent_id=parent_id,
                name="",
                facility_code_id=facility_code_id,
                unit_kind=unit[0],
                unit=unit[1],
                tooltip=tooltip,
                seed_key=seed_key,
            )
            GhgIndexNode.objects.filter(pk=row.pk).update(sort_order=row.pk)
    except IntegrityError as exc:
        hit = constraint_name(exc)
        if hit in _NODE_SEED_KEY:
            return Invalid({"seedKey": SEED_KEY_TAKEN})
        if hit not in _CODE_UNIQUE:
            raise
        return Invalid({"facilityCodeId": CODE_TAKEN})
    return row.pk


def update_leaf(
    *,
    actor_kind: Kind,
    operation_id: str,
    node_id: int,
    facility_code_id: int,
    unit: tuple[str, str],
    tooltip: str,
) -> Invalid | NotFound | Forbidden | None:
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    try:
        with transaction.atomic():
            changed = GhgIndexNode.objects.filter(pk=node_id, deleted_at__isnull=True).update(
                facility_code_id=facility_code_id,
                unit_kind=unit[0],
                unit=unit[1],
                tooltip=tooltip,
                updated_at=timezone.now(),
            )
    except IntegrityError as exc:
        if constraint_name(exc) not in _CODE_UNIQUE:
            raise
        return Invalid({"facilityCodeId": CODE_TAKEN})
    return None if changed else NotFound()


def mark_nodes_deleted(*, actor_kind: Kind, operation_id: str, ids: Collection[int]) -> int | Forbidden:
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    now = timezone.now()
    with transaction.atomic():
        return GhgIndexNode.objects.filter(pk__in=list(ids), deleted_at__isnull=True).update(
            deleted_at=now, updated_at=now
        )


def insert_factor(
    *, actor_kind: Kind, operation_id: str, facility_node_id: int, is_default: bool, seed_key: str | None = None
) -> int | Invalid | Forbidden:
    """계수 정체 하나(판 1). sort_order = 만든 차례. 부르는 쪽이 잎을 잠갔다(selectors.lock_nodes) — 그래도 기본 둘이
    겹치면(ghg_factors_one_default_alive) 500 대신 갈래로 돌려준다. 같은 씨앗 키 경합(ghg_factors_seed_key_unique)은
    seedKey 갈래."""
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    try:
        with transaction.atomic():
            row = GhgFactor.objects.create(
                facility_node_id=facility_node_id, is_default=is_default, current_version=1, seed_key=seed_key
            )
            GhgFactor.objects.filter(pk=row.pk).update(sort_order=row.pk)
    except IntegrityError as exc:
        name = constraint_name(exc)
        if name in _FACTOR_SEED_KEY:
            return Invalid({"seedKey": SEED_KEY_TAKEN})
        if name not in _ONE_DEFAULT:
            raise
        return Invalid({"defaultFactorId": DEFAULT_RACE})
    return row.pk


def bump_factor_version(*, actor_kind: Kind, operation_id: str, factor_id: int) -> int | NotFound | Forbidden:
    """정체의 current_version + 1 → 새 판 번호. 부르는 쪽이 정체를 잠갔다(selectors.lock_factor). 지워진 정체면
    NotFound."""
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    with transaction.atomic():
        changed = GhgFactor.objects.filter(pk=factor_id, deleted_at__isnull=True).update(
            current_version=F("current_version") + 1, updated_at=timezone.now()
        )
        if not changed:
            return NotFound()
        return GhgFactor.objects.filter(pk=factor_id).values_list("current_version", flat=True).get()


def set_default_factor(
    *, actor_kind: Kind, operation_id: str, facility_node_id: int, factor_id: int
) -> Invalid | Forbidden | None:
    """그 잎의 기본을 factor_id 로 — 옛 기본 끔 → 새 기본 켬(한 블록, 차례가 부분 unique 를 지킨다). 부르는 쪽이 잎을
    잠갔다 — 그래도 겹치면 500 대신 갈래."""
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    now = timezone.now()
    try:
        with transaction.atomic():
            GhgFactor.objects.filter(facility_node_id=facility_node_id, is_default=True).exclude(pk=factor_id).update(
                is_default=False, updated_at=now
            )
            GhgFactor.objects.filter(pk=factor_id, deleted_at__isnull=True).update(is_default=True, updated_at=now)
    except IntegrityError as exc:
        if constraint_name(exc) not in _ONE_DEFAULT:
            raise
        return Invalid({"defaultFactorId": DEFAULT_RACE})
    return None


def mark_factors_deleted(*, actor_kind: Kind, operation_id: str, ids: Collection[int]) -> int | Forbidden:
    """삭제 표시(기본 표시도 끈다 — ghg_factors_default_alive). 기본 승계는 부르는 action 이 한다."""
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    now = timezone.now()
    with transaction.atomic():
        return GhgFactor.objects.filter(pk__in=list(ids), deleted_at__isnull=True).update(
            is_default=False, deleted_at=now, updated_at=now
        )


def insert_factor_version(
    *,
    actor_kind: Kind,
    operation_id: str,
    factor_id: int,
    version: int,
    values: FactorValues,
    seed_record_ids: Sequence[str] = (),
    seed_gwp_set_id: str | None = None,
) -> int | Forbidden:
    """판 한 줄을 넣는다(고치지 않는다 — 고치기는 새 판)."""
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    ncv_unit = values.ncv_unit
    with transaction.atomic():
        row = GhgFactorVersion.objects.create(
            factor_id=factor_id,
            version=version,
            name=values.name,
            source=values.source,
            base_year=values.base_year,
            tier=values.tier,
            country_code=values.country_code,
            industry_code=values.industry_code,
            input_unit_kind=values.input_unit[0],
            input_unit=values.input_unit[1],
            emission_unit_kind=values.emission_unit[0],
            emission_unit=values.emission_unit[1],
            ncv_enabled=values.ncv is not None,
            ncv=values.ncv,
            ncv_unit_kind=ncv_unit[0] if ncv_unit else None,
            ncv_unit=ncv_unit[1] if ncv_unit else None,
            factor_unit=values.factor_unit,
            note=values.note,
            seed_record_ids=list(seed_record_ids),
            seed_gwp_set_id=seed_gwp_set_id,
        )
    return row.pk


def insert_factor_gases(
    *, actor_kind: Kind, operation_id: str, version_id: int, gases: Sequence[GasValues]
) -> int | Forbidden:
    """판의 가스 일곱 줄(고정 차례 — 검사가 일곱을 채워 넘긴다)."""
    if not is_allowed(operation_id, kind=actor_kind):
        return Forbidden(operation_id)
    with transaction.atomic():
        rows = GhgFactorGas.objects.bulk_create(
            GhgFactorGas(factor_version_id=version_id, gas=gas.gas, enabled=gas.enabled, factor=gas.factor, gwp=gas.gwp)
            for gas in gases
        )
    return len(rows)
