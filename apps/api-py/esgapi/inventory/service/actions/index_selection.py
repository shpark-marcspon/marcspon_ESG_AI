"""고객사 인덱스 선택(S17)의 유스케이스 — 트리 읽기·선택 저장. 밴드 K1b-2b ②(결정 MARC-ENT-469 3·4). HTTP 를 모른다.

  index_tree        공통 풀(삭제 안 된 노드) + 이 회사 시설 수(availableCount) + 이 해의 선택.
                    **GET 은 해를 만들지 않는다**
  save_selections   해가 없으면 만들고, 고른 잎마다 그때 기본 계수의 지금 판을 잡는다(이 회사에 그 자산/시설이
                    없어도 고른다 — S12-05, MARC-ENT-644). 이미 고른 잎은 0 바뀜(잡은
                    판 그대로), 숨긴 잎을 다시 고르면 숨김을 푼다(판 그대로). 뺀 잎은 데이터가 있으면 숨김, 없으면
                    삭제 표시

★ 회사 id 는 부르는 쪽이 정한 것이다(고객사 사용자는 주체의 회사, 운영 관리자는 company_of 의 작업 회사).
★ 도메인을 넘는 것(조직구조의 사업장·자산/시설 — organization 의 selectors)은 여기서만 부른다(services·selectors 는
  남의 도메인 import 0 — .importlinter 바). 시설 수는 인벤토리 켠·삭제 안 된 사업장마다 자산/시설 목록을 읽어 센다
  (감독 판단 2 (가) — 사업장 수십이라 N+1 을 받아들임, S12a 에서 다시 봄).
★ 저장은 `@transaction.atomic` 하나: 판정을 쓰기 전에 다 한다(하나라도 걸리면 0 씀). 해 행 잠금(lock_year) → 풀 잎
  잠금(lock_nodes — 운영 관리자의 잎 저장·지우기와 줄 섬) 차례. services 는 모듈 이름으로 부른다(시험이 둘째 부름에
  실패를 심는다).
★ with_data(데이터 있는 잎)의 기본 인자 selectors.selections_with_data = 삭제 안 된 입력 행이 있는 잎(S12a ②).
"""

from collections.abc import Callable, Collection, Sequence
from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo

from django.db import transaction

from esgapi.inventory.service.selectors import ghg_pool as pool
from esgapi.inventory.service.selectors import index_selection as selectors
from esgapi.inventory.service.services import index_selection as services
from esgapi.inventory.service.utils.ghg_pool import Invalid
from esgapi.inventory.service.utils.index_selection import (
    LEAF,
    MAX_SELECTIONS,
    IndexTree,
    SaveResult,
    facility_counts,
    leaf_counts,
    rollup,
    year_problem,
)
from esgapi.organization.service.selectors.branches import facilities_of, search_sites

SEOUL: Final = ZoneInfo("Asia/Seoul")
TOO_MANY = f"한 번에 {MAX_SELECTIONS}개까지 고른다"
NOT_A_LEAF = "없거나 지운 자산/시설(잎)이다"
NO_FACTOR = "기본 배출계수가 없는 자산/시설이다"
RACE = "선택이 동시에 바뀌었다 — 다시 불러 저장한다"

WithData = Callable[[int, int, Collection[int]], frozenset[int]]


def today() -> date:
    """올해를 정하는 날 — Asia/Seoul(감독 판단 7)."""
    return datetime.now(SEOUL).date()


def company_facility_counts(company_id: int) -> dict[int, int]:
    """코드 id → 이 회사의 인벤토리 켠·삭제 안 된 사업장의 삭제 안 된 자산/시설 수."""
    sites = [branch for branch in search_sites(company_id).branches if branch.inventory_enabled]
    return facility_counts(row.facility_code_id for site in sites for row in facilities_of(company_id, site.id))


def index_tree(
    company_id: int, year: int, *, on: date | None = None, with_data: WithData = selectors.selections_with_data
) -> IndexTree | Invalid:
    """그 해의 트리(읽기 — 쓰지 않는다). 해가 없으면 선택 0 으로 보인다."""
    problem = year_problem(year, on or today())
    if problem is not None:
        return Invalid({"year": problem})
    nodes = pool.tree_nodes()
    counts = leaf_counts(nodes, company_facility_counts(company_id))
    factored = pool.default_versions(counts)
    year_id = selectors.year_of(company_id, year)
    chosen = selectors.selections_of(company_id, year_id) if year_id is not None else {}
    selected = {node_id for node_id, row in chosen.items() if not row.hidden}
    data: frozenset[int] = with_data(company_id, year_id, chosen) if year_id is not None else frozenset()
    return IndexTree(year=year, nodes=rollup(nodes, counts, selected, with_factor=factored.keys(), with_data=data))


def _year_id(company_id: int, year: int) -> int:
    found = selectors.year_of(company_id, year)
    if found is not None:
        return found
    made = services.create_year(company_id, year)
    if isinstance(made, services.YearTaken):  # 경합: 다른 저장이 먼저 세웠다 — 그 행을 쓴다
        again = selectors.year_of(company_id, year)
        if again is None:
            raise RuntimeError("inventory_years_company_year_unique 가 막았는데 행이 없다")
        return again
    return made


def _problem(wanted: Sequence[int], alive_leaves: set[int], versions: dict[int, int], new: set[int]) -> str | None:
    if len(wanted) > MAX_SELECTIONS:
        return TOO_MANY
    if any(node_id not in alive_leaves for node_id in wanted):
        return NOT_A_LEAF
    if any(node_id not in versions for node_id in new):
        return NO_FACTOR
    return None


@transaction.atomic
def save_selections(
    company_id: int,
    year: int,
    node_ids: Sequence[int],
    *,
    on: date | None = None,
    with_data: WithData = selectors.selections_with_data,
) -> SaveResult | Invalid:
    """그 해의 선택을 요청 잎 목록으로 맞춘다. 판정(422 — 연도 fields.year, 잎 fields.facilityNodeIds)에 걸리면 0 씀."""
    problem = year_problem(year, on or today())
    if problem is not None:
        return Invalid({"year": problem})
    wanted = list(dict.fromkeys(node_ids))  # 겹친 id 는 걷는다(차례는 처음 나온 대로)
    if len(wanted) > MAX_SELECTIONS:
        return Invalid({"facilityNodeIds": TOO_MANY})
    year_id = _year_id(company_id, year)
    selectors.lock_year(company_id, year)
    current = selectors.selections_of(company_id, year_id)
    locked = pool.lock_nodes(set(wanted) | set(current))
    alive_leaves = {node_id for node_id, info in locked.items() if info.level == LEAF}
    new = {node_id for node_id in wanted if node_id not in current}
    versions = pool.default_versions(new)
    found = _problem(wanted, alive_leaves, versions, new)
    if found is not None:
        transaction.set_rollback(True)  # 만든 해 행도 되돌린다(하나라도 걸리면 0 씀)
        return Invalid({"facilityNodeIds": found})

    keep = set(wanted)
    unhide = [current[node_id].id for node_id in wanted if node_id in current and current[node_id].hidden]
    dropped = {node_id for node_id, row in current.items() if not row.hidden and node_id not in keep}
    with_rows = with_data(company_id, year_id, dropped) & dropped
    inserted = services.insert_selections(
        company_id,
        year_id,
        [
            services.NewSelection(facility_node_id=node_id, factor_version_id=versions[node_id])
            for node_id in wanted
            if node_id in new
        ],
    )
    if isinstance(inserted, services.SelectionTaken):
        transaction.set_rollback(True)
        return Invalid({"facilityNodeIds": RACE})
    services.set_hidden(company_id, unhide, hidden=False)
    services.set_hidden(company_id, [current[node_id].id for node_id in with_rows], hidden=True)
    services.mark_selections_deleted(company_id, [current[node_id].id for node_id in dropped - with_rows])
    after = selectors.selections_of(company_id, year_id)
    return SaveResult(selected=sum(not row.hidden for row in after.values()), hidden_with_data=len(with_rows))
