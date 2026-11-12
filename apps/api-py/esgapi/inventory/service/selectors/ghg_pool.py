"""온실가스 인덱스 풀·시설별 배출계수 풀(모든 고객사 공통 하나 — 결정 MARC-ENT-469 3)의 읽기. 밴드 K1b-2a ②.
쓰지 않는다.

★ 풀 표 넷(ghg_index_nodes·ghg_factors·ghg_factor_versions·ghg_factor_gases)에는 회사 칸이 없다(전역 자료). 그래서
  조회에 회사 조건이 없고, 아래 표시 줄이 그것을 일부러 한 일로 적어 둔다(core/tests/test_selector_scope.py 가 읽는다).
  이 파일은 회사 데이터를 읽지 않는다. 풀 표를 여는 길은 여기와 services 뿐이다.
★ 경로가 바로 부르는 읽기 넷(node_list·facility_detail·factor_version·options)은 첫 문장에서 권한 표를 다시 읽는다
  (경로의 permitted 에 더해 — ALSO_INSIDE). 나머지는 services·actions 의 판정용이다.
★ 행 잠금은 여기만(lock_factor — 고치기의 정체 잠금 · lock_nodes — 잎의 기본 바꾸기와 부모 아래 만들기·지우기를
  줄 세우는 노드 잠금, 검증 ② B1·R6). 사용 중 판정(nodes_in_use·factors_in_use)은 회사 표를 읽으므로 여기 없다 —
  inventory/service/selectors/index_selection.py(K1b-2b ④, sid:MARC-ISSUE-432).
"""

# tenant-scope: global — 이 파일이 읽는 표 넷(ghg_*)에는 회사 칸이 없다(전 고객사 공통). 시설 코드는 잎의 FK 로만.

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from django.db.models import Count, F, Q, QuerySet

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import is_allowed
from esgapi.inventory.models import GhgFactor, GhgFactorGas, GhgFactorVersion, GhgIndexNode
from esgapi.inventory.service.utils.ghg_pool import (
    GASES,
    LEVELS,
    FacilityView,
    FactorInfo,
    FactorSummary,
    FactorView,
    Forbidden,
    GasValues,
    NodeInfo,
    NodeView,
    NotFound,
)
from esgapi.inventory.service.utils.ghg_pool import (
    options as option_body,
)


def _alive_nodes() -> QuerySet[GhgIndexNode]:
    return GhgIndexNode.objects.filter(deleted_at__isnull=True)


def _alive_factors() -> QuerySet[GhgFactor]:
    return GhgFactor.objects.filter(deleted_at__isnull=True)


def _info(row: GhgIndexNode) -> NodeInfo:
    return NodeInfo(id=row.pk, level=row.level, parent_id=row.parent_id, facility_code_id=row.facility_code_id)


def _factor_info(row: GhgFactor) -> FactorInfo:
    return FactorInfo(
        id=row.pk,
        facility_node_id=row.facility_node_id,
        is_default=row.is_default,
        sort_order=row.sort_order,
        current_version=row.current_version,
    )


def _child_counts(ids: Collection[int]) -> dict[int, int]:
    rows = _alive_nodes().filter(parent_id__in=list(ids)).values("parent_id").annotate(n=Count("id"))
    return {row["parent_id"]: row["n"] for row in rows}


def _view(row: GhgIndexNode, child_count: int) -> NodeView:
    code = row.facility_code if row.level == "facility" else None
    return NodeView(
        id=row.pk,
        level=row.level,
        name=code.name if code is not None else row.name,
        parent_id=row.parent_id,
        sort_order=row.sort_order,
        child_count=child_count,
        facility_code_id=row.facility_code_id,
        facility_code=(code.code or "") if code is not None else None,
    )


def _with_ancestors(ids: set[int]) -> set[int]:
    """맞는 노드들에 그 조상(삭제 안 된 것)을 더한다. 단이 넷이라 많아야 세 번 오른다."""
    found = set(ids)
    frontier = set(ids)
    while frontier:
        parents = {
            parent for parent in _alive_nodes().filter(pk__in=list(frontier)).values_list("parent_id", flat=True)
        }
        frontier = {parent for parent in parents if parent is not None} - found
        found |= frontier
    return found


def node_list(*, actor_kind: Kind, parent_id: int | None, q: str | None) -> list[NodeView] | NotFound | Forbidden:
    """열 하나(parentId 없음 → 범위 단, 있음 → 그 노드의 자식). q 가 있으면 이름(잎은 코드 이름) 부분 일치(대소문자
    무시)하는 노드와 그 조상 — 이때 parentId 는 보지 않는다[우리 해석]. 차례: 단 → sort_order → id. 페이지 없음."""
    if not is_allowed("inventory_admin_ghg_nodes_list", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_nodes_list")
    rows = _alive_nodes().select_related("facility_code")
    if q is not None:
        matched = rows.filter(Q(name__icontains=q) | Q(level="facility", facility_code__name__icontains=q))
        rows = rows.filter(pk__in=list(_with_ancestors(set(matched.values_list("id", flat=True)))))
    elif parent_id is not None:
        if not _alive_nodes().filter(pk=parent_id).exists():
            return NotFound()
        rows = rows.filter(parent_id=parent_id)
    else:
        rows = rows.filter(parent__isnull=True)
    found = list(rows)
    counts = _child_counts([row.pk for row in found])
    found.sort(key=lambda row: (LEVELS.index(row.level), row.sort_order, row.pk))
    return [_view(row, counts.get(row.pk, 0)) for row in found]


def tree_nodes() -> list[NodeView]:
    """삭제 안 된 노드 전부(고객사 인덱스 선택 S17 의 트리 — K1b-2b). 차례: 단 → sort_order → id. 페이지 없음."""
    found = list(_alive_nodes().select_related("facility_code"))
    counts = _child_counts([row.pk for row in found])
    found.sort(key=lambda row: (LEVELS.index(row.level), row.sort_order, row.pk))
    return [_view(row, counts.get(row.pk, 0)) for row in found]


def default_versions(leaf_ids: Collection[int]) -> dict[int, int]:
    """잎 → 그 잎의 기본 계수(삭제 안 된 것)의 지금 판 id. 기본 계수가 없는 잎은 빠진다(K1b-2b — 회사 선택이 잡는
    판)."""
    rows = GhgFactorVersion.objects.filter(
        factor__facility_node_id__in=list(leaf_ids),
        factor__is_default=True,
        factor__deleted_at__isnull=True,
        version=F("factor__current_version"),
    ).values_list("factor__facility_node_id", "id")
    return dict(rows)


def current_version_id(factor_id: int, node_id: int) -> int | None:
    """삭제 안 된 계수가 그 잎의 것이면 그 지금 판 id, 아니면 None(S12a-2 — 행 계수 바꿈·복구. default_versions 꼴)."""
    return (
        GhgFactorVersion.objects.filter(
            factor_id=factor_id,
            factor__facility_node_id=node_id,
            factor__deleted_at__isnull=True,
            version=F("factor__current_version"),
        )
        .values_list("id", flat=True)
        .first()
    )


def alive_nodes(ids: Collection[int]) -> dict[int, NodeInfo]:
    """ids 가운데 삭제 안 된 노드."""
    return {row.pk: _info(row) for row in _alive_nodes().filter(pk__in=list(ids))}


def lock_nodes(ids: Collection[int]) -> dict[int, NodeInfo]:
    """노드 잠금(블록 안에서만 부른다). 삭제 안 된 것만 — 기다린 사이 지워졌으면 빠진다(FOR UPDATE 가 조건을 다시 본다).
    id 차례로 잠가 둘이 서로 기다리는 일을 막는다. 같은 잎의 첫 계수·기본 바꾸기·승계, 같은 부모 아래 만들기·지우기가
    이 잠금에서 줄을 선다."""
    rows = _alive_nodes().select_for_update().filter(pk__in=sorted(ids)).order_by("id")
    return {row.pk: _info(row) for row in rows}


def name_taken(parent_id: int | None, name: str, *, except_id: int | None = None) -> bool:
    """같은 부모(뿌리면 뿌리끼리) 아래 삭제 안 된 잎 아닌 노드에 같은 이름(글자 그대로)이 있나."""
    rows = _alive_nodes().filter(name=name).exclude(level="facility")
    rows = rows.filter(parent__isnull=True) if parent_id is None else rows.filter(parent_id=parent_id)
    if except_id is not None:
        rows = rows.exclude(pk=except_id)
    return rows.exists()


def code_taken(parent_id: int, facility_code_id: int, *, except_id: int | None = None) -> bool:
    """같은 활동 아래 삭제 안 된 잎에 같은 시설 코드가 있나."""
    rows = _alive_nodes().filter(parent_id=parent_id, facility_code_id=facility_code_id)
    if except_id is not None:
        rows = rows.exclude(pk=except_id)
    return rows.exists()


def with_alive_children(ids: Collection[int]) -> dict[int, frozenset[int]]:
    """ids 가운데 삭제 안 된 자식이 있는 노드 → 그 자식 id."""
    found: dict[int, set[int]] = {}
    for child, parent in _alive_nodes().filter(parent_id__in=list(ids)).values_list("id", "parent_id"):
        found.setdefault(parent, set()).add(child)
    return {parent: frozenset(children) for parent, children in found.items()}


def seeded_nodes(keys: Collection[str]) -> dict[str, tuple[int, bool]]:
    """씨앗 열쇠 → (노드 id, 삭제 표시됨). 삭제 표시된 것도 낸다 — 씨앗은 관리자가 지운 것을 되살리지 않고 그 아래를
    건너뛴다(K1b-2b ⑤ — R9)."""
    rows = GhgIndexNode.objects.filter(seed_key__in=list(keys)).values_list("seed_key", "id", "deleted_at")
    return {key: (node_id, deleted_at is not None) for key, node_id, deleted_at in rows if key is not None}


def seeded_factors(keys: Collection[str]) -> frozenset[str]:
    """이미 있는 씨앗 계수의 열쇠(삭제 표시된 것도 — 관리자가 고치거나 지운 것을 덮지 않는다)."""
    rows = GhgFactor.objects.filter(seed_key__in=list(keys)).values_list("seed_key", flat=True)
    return frozenset(key for key in rows if key is not None)


def leaf_codes(ids: Collection[int]) -> dict[int, int]:
    """잎 id → 시설 코드 id(삭제 표시된 잎도 — S12S1: 옛 씨앗 잎의 코드는 이름이 아니라 잎 행에서 찾는다)."""
    rows = GhgIndexNode.objects.filter(pk__in=list(ids), level="facility").values_list("id", "facility_code_id")
    return {node_id: code_id for node_id, code_id in rows if code_id is not None}


def codes_on_other_leaves(code_ids: Collection[int], *, except_ids: Collection[int]) -> frozenset[int]:
    """코드 가운데 except_ids 밖의 삭제 안 된 잎이 쓰는 것(S12S1 — 옛 씨앗 코드를 새 씨앗·관리자 잎이 쓰면 남긴다)."""
    rows = _alive_nodes().filter(level="facility", facility_code_id__in=list(code_ids)).exclude(pk__in=list(except_ids))
    return frozenset(rows.values_list("facility_code_id", flat=True))


@dataclass(frozen=True)
class FactorMark:
    """씨앗 지우기의 판정용 계수 한 줄(S12S1): 씨앗이 만든 것인가 · 지금 판 번호(2 이상 = 관리자가 고침)."""

    id: int
    facility_node_id: int
    seeded: bool
    current_version: int


def factor_marks(node_ids: Collection[int]) -> list[FactorMark]:
    """잎들의 삭제 안 된 계수 — id 차례(S12S1 씨앗 지우기의 셈. 잠그려면 actions 가 lock_factor 를 하나씩 부른다)."""
    rows = _alive_factors().filter(facility_node_id__in=list(node_ids)).order_by("id")
    return [
        FactorMark(
            id=row.pk,
            facility_node_id=row.facility_node_id,
            seeded=row.seed_key is not None,
            current_version=row.current_version,
        )
        for row in rows
    ]


def alive_factors(ids: Collection[int]) -> dict[int, FactorInfo]:
    return {row.pk: _factor_info(row) for row in _alive_factors().filter(pk__in=list(ids))}


def alive_factors_of(node_ids: Collection[int]) -> list[FactorInfo]:
    """잎들의 삭제 안 된 계수 — sort_order → id 차례(기본 승계의 「남은 첫 행」)."""
    rows = _alive_factors().filter(facility_node_id__in=list(node_ids)).order_by("sort_order", "id")
    return [_factor_info(row) for row in rows]


def lock_factor(factor_id: int) -> FactorInfo | None:
    """고치기의 정체 잠금(같은 계수를 둘이 동시에 고쳐 같은 판 번호를 노리는 일을 줄 세운다). 블록 안에서만 부른다."""
    row = _alive_factors().select_for_update().filter(pk=factor_id).first()
    return None if row is None else _factor_info(row)


def _summaries(node_id: int) -> list[FactorSummary]:
    current = (
        GhgFactorVersion.objects.filter(
            factor__facility_node_id=node_id, factor__deleted_at__isnull=True, version=F("factor__current_version")
        )
        .select_related("factor")
        .order_by("factor__sort_order", "factor_id")
    )
    return [
        FactorSummary(
            id=row.factor_id,
            name=row.name,
            input_unit=(row.input_unit_kind, row.input_unit),
            is_default=row.factor.is_default,
            sort_order=row.factor.sort_order,
            version=row.version,
        )
        for row in current
    ]


def facility_detail(*, actor_kind: Kind, node_id: int) -> FacilityView | NotFound | Forbidden:
    """잎 하나 + 삭제 안 된 계수의 지금 판 요약. 잎이 아니거나 없으면 404."""
    if not is_allowed("inventory_admin_ghg_facilities_get", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_facilities_get")
    row = _alive_nodes().select_related("facility_code").filter(pk=node_id, level="facility").first()
    if row is None or row.parent_id is None or row.facility_code_id is None:
        return NotFound()
    code = row.facility_code
    return FacilityView(
        id=row.pk,
        parent_id=row.parent_id,
        facility_code_id=row.facility_code_id,
        facility_code=(code.code or "") if code is not None else "",
        facility_name=code.name if code is not None else "",
        unit=(row.unit_kind or "", row.unit or ""),
        tooltip=row.tooltip,
        factors=_summaries(row.pk),
    )


def factor_version(*, actor_kind: Kind, factor_id: int, version: int | None) -> FactorView | NotFound | Forbidden:
    """삭제 안 된 계수의 판 하나(version 없음 → 지금 판) + 판 번호 목록. 없는 판이면 404."""
    if not is_allowed("inventory_admin_ghg_factors_get", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_factors_get")
    factor = _alive_factors().filter(pk=factor_id).first()
    if factor is None:
        return NotFound()
    wanted = factor.current_version if version is None else version
    row = GhgFactorVersion.objects.filter(factor_id=factor_id, version=wanted).first()
    if row is None:
        return NotFound()
    return _version_view(factor, row)


def pinned_version(version_id: int) -> FactorView | NotFound:
    """회사가 잡은 판 하나(K1b-2b ④ — L4). **계수의 삭제 표시와 상관없이** 판 + 가스 일곱(factor_version 의 꼴).
    경로 0 — 입력·셈(S12a)이 쓴다. 없는 판 id 면 NotFound."""
    row = GhgFactorVersion.objects.select_related("factor").filter(pk=version_id).first()
    if row is None:
        return NotFound()
    return _version_view(row.factor, row)


def leaf_unit(node_id: int) -> tuple[str, str] | None:
    """삭제 안 된 잎의 1차 단위(종류, 단위). 잎이 아니면 None(K1b-2b ④ — 잎 저장의 단위 바뀜 판정)."""
    row = _alive_nodes().filter(pk=node_id, level="facility").values_list("unit_kind", "unit").first()
    if row is None or row[0] is None or row[1] is None:
        return None
    return row[0], row[1]


def _version_view(factor: GhgFactor, row: GhgFactorVersion) -> FactorView:
    factor_id = factor.pk
    gases = {gas.gas: gas for gas in GhgFactorGas.objects.filter(factor_version_id=row.pk)}
    versions = tuple(
        GhgFactorVersion.objects.filter(factor_id=factor_id).order_by("version").values_list("version", flat=True)
    )
    return FactorView(
        id=factor.pk,
        facility_node_id=factor.facility_node_id,
        version=row.version,
        is_default=factor.is_default,
        sort_order=factor.sort_order,
        name=row.name,
        source=row.source,
        base_year=row.base_year,
        tier=row.tier,
        country_code=row.country_code,
        industry_code=row.industry_code,
        input_unit=(row.input_unit_kind, row.input_unit),
        emission_unit=(row.emission_unit_kind, row.emission_unit),
        ncv=row.ncv,
        ncv_unit=(row.ncv_unit_kind, row.ncv_unit) if row.ncv_unit_kind and row.ncv_unit else None,
        factor_unit=row.factor_unit,
        gases=tuple(
            GasValues(gas, gases[gas].enabled, gases[gas].factor, gases[gas].gwp)
            if gas in gases
            else GasValues(gas, enabled=False, factor=None, gwp=None)
            for gas in GASES
        ),
        note=row.note,
        seed_record_ids=tuple(row.seed_record_ids),
        seed_gwp_set_id=row.seed_gwp_set_id,
        created_at=factor.created_at,
        updated_at=row.created_at,
        versions=versions,
    )


def options(*, actor_kind: Kind) -> Mapping[str, object] | Forbidden:
    """선택 목록(가스·단위·국가·산업·기본값). DB 를 읽지 않는다 — 목록은 utils 의 상수."""
    if not is_allowed("inventory_admin_ghg_options", kind=actor_kind):
        return Forbidden("inventory_admin_ghg_options")
    return option_body()
