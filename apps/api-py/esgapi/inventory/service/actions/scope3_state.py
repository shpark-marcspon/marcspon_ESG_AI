"""Scope 3 연도 상태·카테고리 잠금의 몸. 밴드 S3K2a ①(결정 MARC-ENT-559·515·469 2, 발주서 Q3·Q6·Q8·Q10·Q11).

남의 도메인(runs)을 엮으므로 Action 이다(scope3_runs.py 꼴). 실행은 runs 의 selectors(run_page·results_of·find_run)로만
읽는다 — 회사 조건이 붙어 남의 회사 실행은 없는 실행이다. models 를 직접 열지 않는다.

    year_state(company_id, year)                     해의 기준 실행 R·latest · 카테고리 열넷의 지금 결과(잠겼으면 핀)
    year_values(company_id, year)                    카테고리 → 지금 결과 값(대시보드 — 같은 재료, 이름 조회 0)
    lock(company_id, year, category, run_id, actor)  잠그기(고객사·운영 관리자 대행) — 처분 차례(아래)
    unlock(company_id, year, category, actor_kind)   풀기(운영 관리자만 — 첫 문장 is_allowed)

「지금 결과」는 저장하지 않는다: 읽을 때마다 R 을 다시 고른다(Q6 — 만든 차례 첫 「done + 결과 done」). 그래서 새 done 이
오면 잠기지 않은 카테고리는 **전부** 새 실행 것으로 바뀐다(559). 잠긴 카테고리는 핀 실행 것(Q10).
R 고르기는 run_page 를 200 씩(만든 차례), 본문은 done 후보마다 하나씩 읽고 첫 결과 done 에서 멈춘다. 핀 본문은 한 번에
(핀 = R 이면 다시 읽지 않는다 — 같은 본문은 요청 안에서 한 번).
S3K2b-1(570): 지금 결과 실행의 줄 편집 사건을 한 번에 읽어 합에서 제외를 빼고 editedRows 를 센다. 새 done 이 오면
잠기지 않은 카테고리는 새 실행으로 가므로 옛 편집은 셈에서 빠지고(그 실행 히스토리에 남음), 잠긴 카테고리는 핀 실행의
것을 쓴다. S3K2b-2: 같은 사건의 축 둘을 접어 계수 고친 줄은 사건의 배출량으로 센다(결과 본문은 덮지 않는다).

잠그기 판정 차례(감독 처분 — critic r2·C0 Q-a): FOR UPDATE(행이 없으면 빈 행을 두고 다시 — Q8) → current 다시 셈 →
  ① current 없음·잠금 자격 없음(Q11) → NotComputed ② runId 가 이 회사 실행이 아님(남의 회사·없음) → RunNotFound
  ③ runId ≠ current.runId → StaleRun ④ 이미 잠김이면 그대로(멱등), 아니면 핀 쓰기.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast

from django.db import transaction
from django.utils import timezone

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import is_allowed
from esgapi.inventory.flows.binding_157 import MODULE
from esgapi.inventory.service.selectors import scope3_edits as edit_selectors
from esgapi.inventory.service.selectors import scope3_state as selectors
from esgapi.inventory.service.services import scope3_state as services
from esgapi.inventory.service.utils.entries import Actor
from esgapi.inventory.service.utils.ghg_pool import Forbidden, Invalid, NotFound
from esgapi.inventory.service.utils.index_selection import YEAR_FIRST, YEAR_LAST
from esgapi.inventory.service.utils.scope3_edits import Event, Now, co2e_of, edited_rows, excluded_of, fold
from esgapi.inventory.service.utils.scope3_state import (
    CATEGORIES,
    RESULT_SHAPE,
    Base,
    Candidate,
    Value,
    base_run,
    category_value,
    lockable,
)
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.user.service.selectors.user import people_of

UNLOCK: Final = "inventory_scope3_unlock"
PAGE: Final = 200
BAD_YEAR = f"{YEAR_FIRST}~{YEAR_LAST}년이다"


@dataclass(frozen=True, slots=True)
class NotComputed:
    """그 카테고리의 지금 결과에 셈한 시트가 없다(R 없음·failed 만·empty 만 — Q11). 잠글 수 없다(409)."""


@dataclass(frozen=True, slots=True)
class StaleRun:
    """보낸 runId 가 그 카테고리의 지금 결과 실행이 아니다(사용자가 본 뒤 새 실행이 끝났다 — 409)."""


@dataclass(frozen=True, slots=True)
class RunNotFound:
    """보낸 runId 가 이 회사의 실행이 아니다(없음·남의 회사 — 같은 404)."""


@dataclass(frozen=True, slots=True)
class Current:
    run_id: int
    value: Value


@dataclass(frozen=True, slots=True)
class CategoryState:
    category: str
    current: Current | None
    locked_at: datetime | None
    locked_by: tuple[int, str] | None  # (users.pk, 이름 — 못 찾으면 빈 글자)
    edited_rows: int  # 지금 결과 실행에서 지금 상태가 AI 원안과 다른 줄 수(570)


@dataclass(frozen=True, slots=True)
class YearState:
    year: int
    base_run_id: int | None
    latest: tuple[int, str] | None
    categories: tuple[CategoryState, ...]
    edited_rows_unlocked: int  # 잠기지 않은 카테고리의 edited_rows 합 — 다시 올리기 전 경고(570)


def year_problem(year: int) -> Invalid | None:
    return None if YEAR_FIRST <= year <= YEAR_LAST else Invalid({"year": BAD_YEAR})


def _candidates(company_id: int) -> Iterator[Candidate]:
    """그 회사의 Scope 3 실행을 만든 차례(새 것 먼저)로 — run_page 를 쪽마다(부르는 쪽이 멈추면 더 읽지 않는다)."""
    offset = 0
    while True:
        page = run_selectors.run_page(
            company_id=company_id, module=MODULE, status=None, document_id=None, limit=PAGE, offset=offset
        )
        for run, _ in page.runs:
            yield Candidate(id=run.id, status=run.status, flow_id=run.flow_id, purpose=run.purpose, options=run.options)
        offset += PAGE
        if offset >= page.count or not page.runs:
            return


def bodies(company_id: int, run_ids: list[int]) -> dict[int, Mapping[str, object]]:
    """실행들의 코랩 결과 본문(scope3.colab.result@1 첫 것). 없는 실행은 열쇠가 없다."""
    found: dict[int, Mapping[str, object]] = {}
    if not run_ids:
        return found
    for run_id, results in run_selectors.results_of(
        company_id=company_id, run_ids=run_ids, schema_versions=[RESULT_SHAPE]
    ).items():
        for result in results:
            body: object = result.body
            if isinstance(body, Mapping):
                found[run_id] = cast("Mapping[str, object]", body)
                break
    return found


def base_of(company_id: int, year: int) -> Base:
    """그 해의 latest·R(본문까지). actions/scope3_edits 도 이것으로 지금 결과를 다시 센다."""
    return base_run(_candidates(company_id), year, lambda run_id: bodies(company_id, [run_id]).get(run_id))


def run_of(base: Base, lock: selectors.Lock | None) -> int | None:
    """그 카테고리의 지금 결과 실행 — 잠겼으면 핀, 아니면 R."""
    return base.run_id if lock is None else lock.pinned_run_id


def pinned_bodies(
    company_id: int,
    base: Base,
    locks: Mapping[str, selectors.Lock],
    known: Mapping[int, Mapping[str, object]] | None = None,
) -> dict[int, Mapping[str, object]]:
    """핀 실행의 본문 — 이미 손에 든 본문(R·known)은 다시 읽지 않는다(같은 본문은 요청 안에서 한 번)."""
    found: dict[int, Mapping[str, object]] = dict(known or {})
    if base.run_id is not None and base.body is not None:
        found[base.run_id] = base.body
    wanted = {lock.pinned_run_id for lock in locks.values()}
    return found | bodies(company_id, sorted(wanted - set(found)))


def _current(
    category: str,
    base: Base,
    lock: selectors.Lock | None,
    pinned: Mapping[int, Mapping[str, object]],
    now: Now,
) -> Current | None:
    run_id = run_of(base, lock)
    if run_id is None:
        return None
    body = base.body if lock is None else pinned.get(run_id)
    excluded, fixed = excluded_of(now, run_id, category), co2e_of(now, run_id, category)
    return Current(run_id=run_id, value=category_value(body, category, excluded, fixed))


def _lines(
    company_id: int,
    base: Base,
    locks: Mapping[str, selectors.Lock],
    categories: tuple[str, ...],
    known: Mapping[int, Mapping[str, object]] | None = None,
    events: Sequence[Event] | None = None,
) -> tuple[dict[str, Current | None], dict[str, int]]:
    """카테고리마다 지금 결과(제외 뺌·계수 고침 듦)와 고친 줄 수 — 연도 상태·대시보드의 한 재료. 사건은 쿼리 하나로.
    events 를 주면 그것을 쓴다(편집 응답 — 방금 읽고 쓴 것을 다시 읽지 않는다, 561 L4)."""
    pinned = pinned_bodies(company_id, base, locks, known)
    if events is None:
        run_ids = {run_of(base, locks.get(category)) for category in categories} - {None}
        events = edit_selectors.events_of(company_id, cast("set[int]", run_ids))
    now = fold(events)
    current = {category: _current(category, base, locks.get(category), pinned, now) for category in categories}
    edited = {
        category: 0 if line is None else edited_rows(now, line.run_id, category) for category, line in current.items()
    }
    return current, edited


def _states(
    company_id: int,
    base: Base,
    locks: Mapping[str, selectors.Lock],
    categories: tuple[str, ...],
    known: Mapping[int, Mapping[str, object]] | None = None,
    events: Sequence[Event] | None = None,
) -> tuple[CategoryState, ...]:
    current, edited = _lines(company_id, base, locks, categories, known, events)
    names = people_of(company_id, {lock.locked_by_user_id for lock in locks.values()})
    found: list[CategoryState] = []
    for category in categories:
        lock = locks.get(category)
        found.append(
            CategoryState(
                category=category,
                current=current[category],
                locked_at=None if lock is None else lock.locked_at,
                locked_by=None
                if lock is None
                else (lock.locked_by_user_id, names.get(lock.locked_by_user_id, ("", ""))[1]),
                edited_rows=edited[category],
            )
        )
    return tuple(found)


def year_state(company_id: int, year: int) -> YearState | Invalid:
    """그 해의 Scope 3 상태 — R·latest · 카테고리 열넷(C 번호 차례)의 지금 결과·잠금. 행을 만들지 않는다."""
    problem = year_problem(year)
    if problem is not None:
        return problem
    base = base_of(company_id, year)
    locks = selectors.locks_of(company_id, year)
    categories = _states(company_id, base, locks, CATEGORIES)
    return YearState(
        year=year,
        base_run_id=base.run_id,
        latest=base.latest,
        categories=categories,
        edited_rows_unlocked=sum(line.edited_rows for line in categories if line.locked_at is None),
    )


def year_values(company_id: int, year: int) -> dict[str, Value | None] | Invalid:
    """카테고리 → 지금 결과 값(합·processed 수·failed 수) — year_state 와 같은 재료·같은 셈(제외 뺌, 잠겼으면 핀).
    지금 결과가 없는 카테고리는 None. 사람 이름은 읽지 않는다(대시보드는 쓰지 않는다)."""
    problem = year_problem(year)
    if problem is not None:
        return problem
    base = base_of(company_id, year)
    current, _ = _lines(company_id, base, selectors.locks_of(company_id, year), CATEGORIES)
    return {category: None if line is None else line.value for category, line in current.items()}


def category_state(
    company_id: int,
    year: int,
    category: str,
    base: Base,
    known: Mapping[int, Mapping[str, object]] | None = None,
    events: Sequence[Event] | None = None,
) -> CategoryState:
    """카테고리 하나의 상태 — 판정에 쓴 base·본문 그대로(잠금 시간 안에서 R 을 다시 고르지 않는다 — 549 ①).
    events 를 주면 그 실행의 사건 전부여야 한다(편집 응답 — 안 잠긴 카테고리의 지금 결과 실행 하나)."""
    (only,) = _states(company_id, base, selectors.locks_of(company_id, year), (category,), known, events)
    return only


def hold_row(company_id: int, year: int, category: str) -> selectors.Row:
    """그 (해, 카테고리) 행을 FOR UPDATE 로 쥔다(블록 안에서만). 없으면 빈 행을 두고(경합이면 먼저 선 것) 다시 잡는다
    (Q8). 거절할 때는 부르는 쪽이 set_rollback 으로 빈 행을 되돌린다. 잠그기·줄 편집이 같은 행으로 줄을 선다."""
    row = selectors.lock_row(company_id, year, category)
    if row is None:
        services.ensure_row(company_id, year, category)
        row = selectors.lock_row(company_id, year, category)
    if row is None:  # 바로 위에서 두었다 — 닫힌 쪽으로
        raise RuntimeError("잠금 행이 없다")
    return row


def _refusal(current: Current | None, run_id: int, company_id: int) -> NotComputed | RunNotFound | StaleRun | None:
    """잠그기 판정(처분 차례): 자격 없음 → 이 회사 실행 아님 → 지금 결과 실행 아님. 지나면 None."""
    if current is None or not lockable(current.value):
        return NotComputed()
    if run_selectors.find_run(company_id=company_id, run_id=run_id) is None:
        return RunNotFound()
    if run_id != current.run_id:
        return StaleRun()
    return None


@transaction.atomic
def lock(
    company_id: int, year: int, category: str, run_id: int, actor: Actor
) -> CategoryState | Invalid | NotFound | NotComputed | RunNotFound | StaleRun:
    """카테고리를 잠근다 — 보낸 runId(사용자가 본 실행)가 지금 결과 실행일 때만 그것을 핀. 이미 잠겼으면 그대로."""
    problem = year_problem(year)
    if problem is not None:
        return problem
    if category not in CATEGORIES:
        return NotFound()
    row = hold_row(company_id, year, category)
    base = base_of(company_id, year)
    pinned = pinned_bodies(company_id, base, {} if row.lock is None else {category: row.lock})
    current = _current(category, base, row.lock, pinned, {})  # 판정은 시트 단위(자격·실행 id) — 제외와 무관
    refused = _refusal(current, run_id, company_id)
    if refused is not None:
        transaction.set_rollback(True)  # 거절이면 첫 잠금이 둔 빈 행도 되돌린다 — 어느 거절이든 행 0(branches.py 꼴)
        return refused
    if row.lock is None:
        services.set_lock(company_id, row.id, locked_at=timezone.now(), user_id=actor.user_id, run_id=run_id)
    return category_state(company_id, year, category, base, pinned)


@transaction.atomic
def unlock(
    company_id: int, year: int, category: str, *, actor_kind: Kind
) -> CategoryState | Invalid | NotFound | Forbidden:
    """잠금을 푼다 — 운영 관리자만(경로의 permitted 에 더해 첫 문장에서 다시). 안 잠겼으면 그대로. 행 만들기 0."""
    if not is_allowed(UNLOCK, kind=actor_kind):
        return Forbidden(UNLOCK)
    problem = year_problem(year)
    if problem is not None:
        return problem
    if category not in CATEGORIES:
        return NotFound()
    row = selectors.lock_row(company_id, year, category)
    if row is not None and row.lock is not None:
        services.clear_lock(company_id, row.id)
    return category_state(company_id, year, category, base_of(company_id, year))
