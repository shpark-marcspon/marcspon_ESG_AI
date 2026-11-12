"""사업장(/branches)의 유스케이스 넷 — 만들기·저장(PUT)·인벤토리 토글·일괄 삭제. 밴드 K1b-1 ②. HTTP 를 모른다.

함수마다 `@transaction.atomic` 하나: 표 하나씩 쓰는 services 함수(sites·site_facilities)를 한 트랜잭션에서 부른다
(B1·ce ① — TWO_TABLE_FUNCTIONS 0). 판정은 쓰기 전에 selectors 로 다 한다(남의 회사·삭제된 id 404, 본사 지움·끔 409,
지운 코드 422, 요청 안 겹침 422 — 하나라도 걸리면 아무것도 쓰지 않는다). 쓴 뒤 경합(제약)으로 둘째 쓰기가 갈래를
돌려주면 이 트랜잭션을 되돌리고(set_rollback) 그 갈래를 돌려준다 — 「일부만 처리」 0.
services 는 모듈 이름으로 부른다(services.save_facilities — 시험이 둘째 부름에 실패를 심는다).
회사 id 는 부르는 쪽이 정한 것이다(고객사 사용자는 주체의 회사, 운영 관리자는 company_of 의 작업 회사).
사용 중 판정은 inventory selectors(sites_in_use·facilities_in_use — 살아 있는 입력 행)를 services 에 넘긴다(S12a ④ ·
sid:MARC-ISSUE-418): 쓰이는 사업장 지움·쓰이는 자산/시설 뺌·코드 바꿈은 409 in_use(세부시설명 바꿈은 된다). 판정은
잠금 아래에서 한다 — 저장은 lock_branch, 일괄 지움은 lock_branches(id 차례). 입력 저장도 그 사업장의 lock_branch 를
잡으므로 둘이 줄 선다. inventory 행은 읽기만 하고 잠그지 않는다(입력 저장의 해 → 선택 → 사업장 차례와 고리 0).
저장은 본문의 판(seen_at — 상세의 updatedAt)을 잠근 행의 updated_at 과 견준다 — 다르면 아무것도 쓰지 않고
Stale(409 stale · K1b-3 · sid:MARC-ISSUE-427). 잠근 뒤에 견주므로 같은 판에서 시작한 저장 둘은 앞이 이기고 뒤가
Stale 이다(lost update 0).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from esgapi.inventory.service.selectors import entries as entry_selectors
from esgapi.organization.service.selectors import branches as selectors
from esgapi.organization.service.selectors import facility_codes as code_selectors
from esgapi.organization.service.services import branches as services
from esgapi.organization.service.services.branches import (
    FacilityRow,
    FacilityTaken,
    HeadquartersLocked,
    InUse,
    NameTaken,
)
from esgapi.organization.service.utils.entities import BranchDetail, BranchFacility


@dataclass(frozen=True)
class NotFound:
    """없거나 남의 회사거나 삭제 표시된 사업장·자산/시설이다(404 — 아무것도 바꾸지 않았다)."""


@dataclass(frozen=True)
class CodeGone:
    """없거나 지운 코드를 새로 골랐다(422 fields.facilityCodeId)."""


@dataclass(frozen=True)
class Stale:
    """본문의 판이 잠근 행의 판과 다르다 — 그사이 다른 곳이 저장했다(409 stale — 아무것도 바꾸지 않았다)."""


SaveRefused = NotFound | Stale | NameTaken | FacilityTaken | CodeGone | HeadquartersLocked | InUse


def _facility_problem(
    rows: Sequence[FacilityRow], current: dict[int, BranchFacility]
) -> NotFound | CodeGone | FacilityTaken | None:
    """자산/시설 줄의 판정: 같은 줄 id 두 번 422 → 남의·지운 id 404 → 새로 고른 코드가 지운 것 422 → 요청 안
    (코드, 세부시설명) 겹침 422. 이미 쓰는 줄이 같은 코드를 그대로 두면 그 코드가 지워졌어도 된다(ce ② 고침 b②)."""
    row_ids = [row.id for row in rows if row.id is not None]
    if len(set(row_ids)) != len(row_ids):  # 같은 줄을 두 번 — 어느 쪽이 이기는지 조용히 고르지 않는다(R6)
        return FacilityTaken()
    if any(row.id is not None and row.id not in current for row in rows):
        return NotFound()
    picked = {
        row.facility_code_id
        for row in rows
        if row.id is None or current[row.id].facility_code_id != row.facility_code_id
    }
    if set(code_selectors.alive_codes(picked)) != picked:
        return CodeGone()
    keys = [(row.facility_code_id, row.detail_name) for row in rows]
    if len(set(keys)) != len(keys):
        return FacilityTaken()
    return None


@transaction.atomic
def create_branch(
    company_id: int, *, name: str, inventory_enabled: bool, facilities: Sequence[FacilityRow]
) -> BranchDetail | SaveRefused:
    problem = _facility_problem(facilities, {})  # 만들기에 줄 id 가 있으면 404(그 사업장에 아직 줄이 없다)
    if problem is not None:
        return problem
    made = services.insert_site_row(company_id, name=name, inventory_enabled=inventory_enabled)
    if isinstance(made, NameTaken):
        return made
    saved = services.save_facilities(
        company_id, made.id, rows=facilities, facilities_in_use=entry_selectors.facilities_in_use
    )
    if saved is not None:
        transaction.set_rollback(True)
        return saved
    found = selectors.branch_detail(company_id, made.id)
    return NotFound() if found is None else found  # 방금 같은 트랜잭션에서 만들었다 — None 일 수 없다


@transaction.atomic
def save_branch(
    company_id: int,
    branch_id: int,
    *,
    seen_at: datetime,
    name: str,
    inventory_enabled: bool,
    facilities: Sequence[FacilityRow],
) -> BranchDetail | SaveRefused:
    """PUT: 이름·인벤토리 고침 + 자산/시설 — id 있는 줄 고침, 없는 줄 새로, 빠진 기존 줄 삭제 표시. 한 트랜잭션."""
    branch = selectors.lock_branch(company_id, branch_id)
    if branch is None:
        return NotFound()
    if branch.updated_at != seen_at:  # 잠근 행과 견준다(순간 비교 — 표기·시간대 무관)
        return Stale()
    if branch.is_headquarters and not inventory_enabled:
        return HeadquartersLocked()
    current = {facility.id: facility for facility in selectors.facilities_of(company_id, branch_id)}
    problem = _facility_problem(facilities, current)
    if problem is not None:
        return problem
    drop = set(current) - {row.id for row in facilities if row.id is not None}
    recoded = {
        row.id for row in facilities if row.id is not None and current[row.id].facility_code_id != row.facility_code_id
    }
    renamed = services.update_site_row(
        company_id, branch_id, name=name, inventory_enabled=inventory_enabled, after=branch.updated_at
    )
    if renamed is not None:
        return renamed
    saved = services.save_facilities(
        company_id,
        branch_id,
        rows=facilities,
        drop=drop,
        recoded=recoded,
        facilities_in_use=entry_selectors.facilities_in_use,
    )
    if saved is not None:
        transaction.set_rollback(True)
        return saved
    found = selectors.branch_detail(company_id, branch_id)
    return NotFound() if found is None else found  # 잠근 행이다 — None 일 수 없다


def _batch_problem(
    company_id: int, ids: Collection[int], *, touches_headquarters: bool
) -> NotFound | HeadquartersLocked | None:
    found = selectors.alive_branches(company_id, ids)
    if len(found) != len(set(ids)):
        return NotFound()
    if touches_headquarters and any(branch.is_headquarters for branch in found):
        return HeadquartersLocked()
    return None


@transaction.atomic
def set_branches_inventory(
    company_id: int, ids: Collection[int], *, enabled: bool
) -> int | NotFound | HeadquartersLocked:
    """인벤토리 사용 일괄. 끄는 요청에 본사가 섞이면 요청 전체 409(켜기는 본사가 섞여도 된다 — 이미 켜져 있다)."""
    # 일괄 지움과 같은 id 차례로 먼저 잠그고 그 아래에서 판정한다(470 M1 — 동시 지움에 500·교착 0)
    selectors.lock_branches(company_id, ids)
    problem = _batch_problem(company_id, ids, touches_headquarters=not enabled)
    if problem is not None:
        return problem
    return services.set_inventory(company_id, set(ids), enabled=enabled)  # 경합으로 본사 CHECK 면 HeadquartersLocked


@transaction.atomic
def delete_branches(company_id: int, ids: Collection[int]) -> int | NotFound | HeadquartersLocked | InUse:
    """일괄 삭제 표시. 본사가 섞이면 요청 전체 409, 쓰이는 사업장이 있으면 409 in_use — 둘 다 행 0.
    먼저 사업장 행을 id 차례로 잠그고(lock_branches) 그 아래에서 「있나」를 다시 본다 — 같은 ids 를 지우는 두 요청의
    늦은 쪽은 404(L3). 지운 사업장의 자산/시설도 같은 트랜잭션에서 삭제 표시한다(R5 — 사업장 밖에서 읽어도 유령 행 0).
    셈은 사업장 수."""
    locked = selectors.lock_branches(company_id, ids)
    if len(locked) != len(set(ids)):
        return NotFound()
    if any(branch.is_headquarters for branch in locked):
        return HeadquartersLocked()
    deleted = services.mark_sites_deleted(company_id, set(ids), sites_in_use=entry_selectors.sites_in_use)
    if isinstance(deleted, InUse | HeadquartersLocked):
        return deleted
    services.mark_facilities_of_sites_deleted(company_id, set(ids))
    return deleted
