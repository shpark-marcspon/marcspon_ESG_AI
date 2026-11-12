"""자산/시설 코드 목록(모든 고객사 공통)의 쓰기 — 운영 관리자만. 밴드 K1b-1. HTTP 를 모른다.

표 하나(organization_facility_codes)라 함수마다 `with transaction.atomic()` 블록 하나(actions 없음). 함수마다 첫 문장이
권한 표를 다시 읽는다(경로의 permitted 에 더해 — ALSO_INSIDE). 회사 데이터를 읽거나 쓰지 않는다.
★ code 는 만들 때 F<id 네 자리> — INSERT 뒤 같은 블록의 UPDATE 가 채운다(감독 판단 3). 블록이 깨지면 둘 다 되돌아가
  code 가 빈 행이 남지 않는다. 이름을 고쳐도 code 는 그대로다.
★ 지우기는 삭제 표시다(하드 지우기 0 — site_facilities 의 FK 는 PROTECT). 새 선택 목록에서만 빠지고, 이미 쓰는 사업장의
  자산/시설은 그 코드의 글자·이름을 그대로 보인다. 「쓰이는 코드 지우기 거절」은 facility_codes_in_use(자리만)가
  채워질 때.
"""

from collections.abc import Callable, Collection
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import is_allowed
from esgapi.organization.models import FacilityCode
from esgapi.organization.service.permissions.organization import Forbidden
from esgapi.organization.service.selectors import facility_codes as selectors
from esgapi.organization.service.services.branches import InUse
from esgapi.organization.service.utils.entities import FacilityCodeInfo


@dataclass(frozen=True)
class CodeNameTaken:
    """삭제 안 된 코드에 같은 이름이 있다(422 fields.name)."""


@dataclass(frozen=True)
class CodesMissing:
    """없거나 이미 지운 코드가 있다(404 — 아무것도 바꾸지 않았다)."""


def code_text(code_id: int) -> str:
    """새 코드의 글자 — F + id 네 자리(넘으면 그 자리 수 그대로)."""
    return f"F{code_id:04d}"


def create_code(*, actor_kind: Kind, name: str) -> FacilityCodeInfo | CodeNameTaken | Forbidden:
    if not is_allowed("organization_admin_facility_codes_create", kind=actor_kind):
        return Forbidden("organization_admin_facility_codes_create")
    if selectors.code_name_taken(name):
        return CodeNameTaken()
    try:
        with transaction.atomic():
            row = FacilityCode.objects.create(name=name)
            code = code_text(row.pk)
            FacilityCode.objects.filter(pk=row.pk).update(code=code, sort_order=row.pk)
    except IntegrityError:  # 같은 이름이 경합으로 먼저 섰다(facility_codes_name_unique_alive)
        return CodeNameTaken()
    return FacilityCodeInfo(id=row.pk, code=code, name=name)


def rename_code(
    *, actor_kind: Kind, code_id: int, name: str
) -> FacilityCodeInfo | CodeNameTaken | CodesMissing | Forbidden:
    if not is_allowed("organization_admin_facility_codes_update", kind=actor_kind):
        return Forbidden("organization_admin_facility_codes_update")
    found = selectors.alive_codes([code_id]).get(code_id)
    if found is None:
        return CodesMissing()
    if selectors.code_name_taken(name, except_id=code_id):
        return CodeNameTaken()
    try:
        with transaction.atomic():
            FacilityCode.objects.filter(pk=code_id).update(name=name, updated_at=timezone.now())  # code 는 그대로
    except IntegrityError:
        return CodeNameTaken()
    return FacilityCodeInfo(id=code_id, code=found.code, name=name)


def delete_codes(
    *,
    actor_kind: Kind,
    ids: Collection[int],
    facility_codes_in_use: Callable[[Collection[int]], frozenset[int]] = selectors.facility_codes_in_use,
) -> int | CodesMissing | InUse | Forbidden:
    """코드 여럿을 삭제 표시한다. 하나라도 없거나 이미 지웠으면 404(일부만 처리 0), 쓰이는 것이 있으면 409."""
    if not is_allowed("organization_admin_facility_codes_delete", kind=actor_kind):
        return Forbidden("organization_admin_facility_codes_delete")
    wanted = set(ids)
    if set(selectors.alive_codes(wanted)) != wanted:
        return CodesMissing()
    used = facility_codes_in_use(wanted)
    if used:
        return InUse(used)
    now = timezone.now()
    with transaction.atomic():
        return FacilityCode.objects.filter(pk__in=list(wanted)).update(deleted_at=now, updated_at=now)
