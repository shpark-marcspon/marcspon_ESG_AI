"""사업장(Branch — 표 sites)과 사업장별 자산/시설(표 site_facilities)의 쓰기. 밴드 K1b-1. HTTP 를 모른다.

**함수마다 표 하나**를 쓴다(저마다 `with transaction.atomic()` 블록 하나). 두 표를 한 번에 쓰는 일은
service/actions/branches.py 의 `@transaction.atomic` 이 이 함수들을 부른다(TWO_TABLE_FUNCTIONS 0).
읽기는 selectors 로만 한다(services 는 읽지 않는다). 판정은 먼저 조회로 하고, 경합(제약)에 걸리면 IntegrityError 를
갈래로 바꾼다 — **try 는 블록 바깥**이다(savepoint 가 되돌린 뒤 잡는다 — 바깥 트랜잭션이 깨진 채 남지 않게).
사용 중 판정(sites_in_use·facilities_in_use)은 **기본값 없는 키워드 인자**다 — actions 가 inventory selectors 의
판정을 넘긴다(S12a ④ · sid:MARC-ISSUE-418. 빈 기본값이 다시 끼어 판정이 조용히 빠지지 않게).
본사 CHECK 둘(sites_headquarters_alive·sites_headquarters_inventory_on)은 제약 이름으로 가려 HeadquartersLocked 로,
그 밖의 제약은 다시 던진다(S12a 2-8 — 판정은 actions 가 먼저, CHECK 는 경합의 뒤받침).
"""

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from django.db import IntegrityError, transaction
from django.utils import timezone

from esgapi.organization.models import Site, SiteFacility
from esgapi.organization.service.selectors import branches as selectors
from esgapi.organization.service.utils.entities import Branch

# 본사의 이름(새로 세울 때). migrations/0003 이 문면에 굳힌 값과 같다(시험이 견준다).
HEADQUARTERS_NAME: Final = "본사"

InUseCheck = Callable[[int, Collection[int]], frozenset[int]]

# 본사 CHECK 의 이름(models.py) — 본사 지움·끔이 경합으로 제약에 걸리면 409 headquarters_locked(S12a 2-8).
HEADQUARTERS_CHECKS: Final = frozenset({"sites_headquarters_alive", "sites_headquarters_inventory_on"})


@dataclass(frozen=True)
class NameTaken:
    """같은 회사의 삭제 안 된 사업장에 같은 이름이 있다(422 fields.name)."""


@dataclass(frozen=True)
class FacilityTaken:
    """그 사업장 안에 같은 (코드, 세부시설명)의 삭제 안 된 자산/시설이 있다 — 또는 한 요청에 같은 줄 id 가 두 번
    (actions 의 판정, R6). 422 fields.facilities."""


@dataclass(frozen=True)
class HeadquartersLocked:
    """본사는 지울 수 없고 인벤토리를 끌 수 없다(409 headquarters_locked — 일괄이면 요청 전체 거절)."""


@dataclass(frozen=True)
class InUse:
    """다른 표가 쓰는 행이다(409 in_use). ids 는 걸린 것."""

    ids: frozenset[int]


@dataclass(frozen=True)
class FacilityRow:
    """자산/시설 한 줄의 값(코드 id·세부시설명). id 가 있으면 고침, 없으면 새로."""

    facility_code_id: int
    detail_name: str
    id: int | None = None


def _broken(err: IntegrityError) -> str | None:
    """IntegrityError 가 어긴 제약의 이름(psycopg 의 diag). 모르면 None."""
    diag = getattr(err.__cause__, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


def insert_site_row(
    company_id: int, *, name: str, inventory_enabled: bool = True, external_id: str | None = None
) -> Branch | NameTaken:
    """사업장 하나를 만든다 — 옛 POST /sites 와 POST /branches 가 같이 부르는 안쪽 함수(N3)."""
    if selectors.name_taken(company_id, name):
        return NameTaken()
    try:
        with transaction.atomic():
            row = Site.for_company(company_id).create(
                name=name, inventory_enabled=inventory_enabled, external_id=external_id
            )
    except IntegrityError:  # 같은 이름이 경합으로 먼저 섰다(sites_name_unique_alive)
        return NameTaken()
    return selectors.branch_of(row)


def update_site_row(
    company_id: int, branch_id: int, *, name: str, inventory_enabled: bool, after: datetime
) -> NameTaken | None:
    """사업장의 이름·인벤토리 사용을 고친다(본사 끄기 거절은 actions 가 먼저 본다 — 제약이 뒤를 받친다).
    after 는 잠근 행의 updated_at 이다 — 새 판은 늘 그보다 크다(시계가 같은 µs 를 내도 판이 바뀐다, K1b-3 판단 2)."""
    if selectors.name_taken(company_id, name, except_id=branch_id):
        return NameTaken()
    try:
        with transaction.atomic():
            Site.for_company(company_id).filter(pk=branch_id).update(
                name=name,
                inventory_enabled=inventory_enabled,
                updated_at=max(timezone.now(), after + timedelta(microseconds=1)),
            )
    except IntegrityError:
        return NameTaken()
    return None


def set_inventory(company_id: int, ids: Collection[int], *, enabled: bool) -> int | HeadquartersLocked:
    """사업장 여럿의 인벤토리 사용을 바꾼다. 고친 행 수. 본사 끄기가 경합으로 CHECK 에 걸리면 HeadquartersLocked."""
    try:
        with transaction.atomic():
            return (
                Site.for_company(company_id)
                .filter(pk__in=list(ids), deleted_at__isnull=True)
                .update(inventory_enabled=enabled, updated_at=timezone.now())
            )
    except IntegrityError as err:  # sites_headquarters_inventory_on — 다른 이름은 다시 던진다
        if _broken(err) in HEADQUARTERS_CHECKS:
            return HeadquartersLocked()
        raise


def mark_sites_deleted(
    company_id: int, ids: Collection[int], *, sites_in_use: InUseCheck
) -> int | InUse | HeadquartersLocked:
    """사업장 여럿을 삭제 표시한다(본사 거절은 actions 가 먼저 — CHECK 가 뒤를 받친다: HeadquartersLocked).
    쓰이는 것이 있으면 아무것도 쓰지 않고 InUse."""
    used = sites_in_use(company_id, ids)
    if used:
        return InUse(used)
    now = timezone.now()
    try:
        with transaction.atomic():
            return (
                Site.for_company(company_id)
                .filter(pk__in=list(ids), deleted_at__isnull=True)
                .update(deleted_at=now, updated_at=now)
            )
    except IntegrityError as err:  # sites_headquarters_alive — 다른 이름은 다시 던진다
        if _broken(err) in HEADQUARTERS_CHECKS:
            return HeadquartersLocked()
        raise


def mark_facilities_of_sites_deleted(company_id: int, site_ids: Collection[int]) -> int:
    """지운 사업장의 삭제 안 된 자산/시설을 같이 삭제 표시한다(사업장 밖에서 읽어도 유령 행 0 — R5). 고친 행 수."""
    now = timezone.now()
    with transaction.atomic():
        return (
            SiteFacility.for_company(company_id)
            .filter(site_id__in=list(site_ids), deleted_at__isnull=True)
            .update(deleted_at=now, updated_at=now)
        )


def save_facilities(
    company_id: int,
    site_id: int,
    *,
    rows: Sequence[FacilityRow],
    drop: Collection[int] = (),
    recoded: Collection[int] = (),
    facilities_in_use: InUseCheck,
) -> FacilityTaken | InUse | None:
    """그 사업장의 자산/시설을 한 블록에서 쓴다: drop 을 삭제 표시 → id 있는 줄 고침 → id 없는 줄 새로.
    drop(빠진 줄)과 recoded(id 있는 줄 가운데 코드를 바꾸는 것 — actions 가 가른다) 중 쓰이는 것이 있으면 아무것도
    쓰지 않고 InUse(S12a 판단 2 — 쓰이는 줄의 세부시설명 바꿈은 된다).
    지우는 것을 먼저 해 같은 (코드, 세부시설명)을 다시 쓰는 요청이 제약에 걸리지 않게 한다.
    고침은 두 단계다(가지 리뷰 M1): id 있는 줄을 한 문장으로 잠깐 삭제 표시해 부분 unique(site_facilities_unique_alive
    — deleted_at IS NULL 인 것끼리) 밖으로 뺀 뒤, 줄마다 최종 값과 deleted_at NULL 로 되살린다. 그래서 맞바꾸기
    (#1↔#2)·사슬(#1→#2 의 값, #2→새 값)이 줄 차례에 걸리지 않고, 끝 상태가 정말 겹칠 때만 FacilityTaken 이다.
    블록 안이라 잠깐의 삭제 표시는 밖에 보이지 않는다(블록이 깨지면 둘 다 되돌아간다)."""
    used = facilities_in_use(company_id, {*drop, *recoded})
    if used:
        return InUse(used)
    now = timezone.now()
    try:
        with transaction.atomic():
            facilities = SiteFacility.for_company(company_id)
            if drop:
                facilities.filter(site_id=site_id, pk__in=list(drop)).update(deleted_at=now, updated_at=now)
            kept = [row for row in rows if row.id is not None]
            if kept:  # ① 고칠 줄을 부분 unique 밖으로(한 문장)
                facilities.filter(site_id=site_id, pk__in=[row.id for row in kept]).update(deleted_at=now)
            for row in kept:  # ② 최종 값으로 되살림
                facilities.filter(site_id=site_id, pk=row.id).update(
                    facility_code_id=row.facility_code_id, detail_name=row.detail_name, deleted_at=None, updated_at=now
                )
            for row in rows:
                if row.id is None:
                    facilities.create(
                        site_id=site_id, facility_code_id=row.facility_code_id, detail_name=row.detail_name
                    )
    except IntegrityError:  # 같은 (코드, 세부시설명) — 고치는 차례에 겹치거나 경합(site_facilities_unique_alive)
        return FacilityTaken()
    return None


def ensure_headquarters(company_id: int) -> int:
    """그 회사에 삭제 안 된 본사가 없으면 하나 세우고 본사의 id 를 돌려준다 — 본사를 세우는 유일한 자리
    (seed_company 가 부른다).

    규칙은 0003 과 같다: 삭제 안 된 「본사」 이름 사업장이 있으면 그 행을 본사로(인벤토리 켬), 없으면 「본사」 하나.
    이미 있으면 그대로다(두 번 불러도 하나). 「있나」는 selectors 가 본다(services 는 읽지 않는다).
    동시에 둘이 부르면 늦은 쪽은 제약(sites_one_headquarters_per_company·이름 unique)에 걸려 IntegrityError 다 — 중복 0.
    """
    found = selectors.headquarters_of(company_id)
    if found is not None:
        return found.id
    named = selectors.alive_site_named(company_id, HEADQUARTERS_NAME)
    with transaction.atomic():
        sites = Site.for_company(company_id)
        if named is None:
            return sites.create(name=HEADQUARTERS_NAME, is_headquarters=True, inventory_enabled=True).pk
        sites.filter(pk=named).update(is_headquarters=True, inventory_enabled=True, updated_at=timezone.now())
    return named
