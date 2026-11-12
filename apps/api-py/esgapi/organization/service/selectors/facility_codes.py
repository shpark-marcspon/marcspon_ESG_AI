"""자산/시설 코드 목록(모든 고객사 공통 하나 — 결정 MARC-ENT-469 3)의 읽기. 밴드 K1b-1. 쓰지 않는다.

★ 코드 표(organization_facility_codes)에는 회사 칸이 없다(전역 자료). 그래서 조회에 회사 조건이 없고, 아래 표시 줄이
  그것을 일부러 한 일로 적어 둔다(core/tests/test_selector_scope.py 가 읽는다). 회사 칸이 있는 표를 읽게 되면 표시 줄을
  지우고 조건을 적는다 — 이 파일은 회사 데이터를 읽지 않는다(회사 넘는 집계 0. 「코드를 쓰는 회사 행 셈」은 K1b-2a 가
  ce 허락으로).
★ 운영 관리자 목록(admin_code_page)은 첫 문장에서 권한 표를 다시 읽는다(경로의 permitted 에 더해 — ALSO_INSIDE).
"""

# tenant-scope: global — 이 파일이 읽는 표 하나(organization_facility_codes)에는 회사 칸이 없다(전 고객사 공통).
# 회사 표(site_facilities)는 모델의 이름 붙은 입구 SiteFacility.used_code_ids(코드 id 만)로만 — S12S1 Q9, 7a 허락.

from collections.abc import Collection
from dataclasses import dataclass

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import is_allowed
from esgapi.organization.models import FacilityCode, SiteFacility
from esgapi.organization.service.permissions.organization import Forbidden
from esgapi.organization.service.utils.entities import FacilityCodeInfo


def code_of(row: FacilityCode) -> FacilityCodeInfo:
    return FacilityCodeInfo(id=row.pk, code=row.code or "", name=row.name)


def selectable_codes() -> list[FacilityCodeInfo]:
    """새로 고를 수 있는 코드(삭제 안 된 것) — 이름 가나다 → id. 페이지 없음."""
    return [code_of(row) for row in FacilityCode.objects.filter(deleted_at__isnull=True).order_by("name", "id")]


def alive_codes(ids: Collection[int]) -> dict[int, FacilityCodeInfo]:
    """ids 가운데 삭제 안 된 코드(사업장의 자산/시설이 고르는 코드의 확인 — 지운 코드는 빠진다)."""
    rows = FacilityCode.objects.filter(pk__in=list(ids), deleted_at__isnull=True)
    return {row.pk: code_of(row) for row in rows}


def code_name_taken(name: str, *, except_id: int | None = None) -> bool:
    """삭제 안 된 코드에 같은 이름(글자 그대로)이 있나. 고치는 행 자신은 뺀다."""
    rows = FacilityCode.objects.filter(name=name, deleted_at__isnull=True)
    if except_id is not None:
        rows = rows.exclude(pk=except_id)
    return rows.exists()


def facility_codes_in_use(ids: Collection[int]) -> frozenset[int]:
    """코드 가운데 사업장의 자산/시설이 쓰는 것 — **자리만**(회사 인자 없음, N1). 1차에는 늘 빈 집합이다:
    회사 넘는 집계는 K1b-2a 가 ce 허락으로 채운다(「쓰이는 코드 지우기 거절」도 그때). admin 목록의 inUse 도 여기서."""
    return frozenset()


def codes_on_site_facilities(ids: Collection[int]) -> frozenset[int]:
    """코드 가운데 어느 회사의 사업장 자산/시설(삭제 안 된 것)이 쓰는 것 — 코드 id 만(S12S1 Q9, 7a 허락). 부르는 자리는
    inventory 의 관리 명령 retire_ghg_seed 하나다(옛 씨앗 코드 지우기의 판정). 회사 표를 이 입구로만 연다 —
    facility_codes_in_use(관리자 화면 inUse·409 자리)는 그대로 둔다."""
    return SiteFacility.used_code_ids(ids)


@dataclass(frozen=True)
class AdminCode:
    code: FacilityCodeInfo
    in_use: bool


@dataclass(frozen=True)
class AdminCodePage:
    count: int
    codes: list[AdminCode]


def admin_code_page(*, actor_kind: Kind, offset: int, limit: int) -> AdminCodePage | Forbidden:
    """운영 관리자의 코드 목록(삭제 안 된 것) — 정렬 칸(만든 차례) → id. inUse 는 facility_codes_in_use 에서."""
    if not is_allowed("organization_admin_facility_codes_list", kind=actor_kind):
        return Forbidden("organization_admin_facility_codes_list")
    rows = FacilityCode.objects.filter(deleted_at__isnull=True)
    count = rows.count()
    page = [code_of(row) for row in rows.order_by("sort_order", "id")[offset : offset + limit]]
    used = facility_codes_in_use([code.id for code in page])
    return AdminCodePage(count=count, codes=[AdminCode(code=code, in_use=code.id in used) for code in page])
