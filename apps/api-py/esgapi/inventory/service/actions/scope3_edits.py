"""Scope 3 줄 덧판의 몸 — 산정 제외·복구와 그 읽기. 밴드 S3K2b-1 ①(결정 MARC-ENT-570·559·469 4, 발주서 Q3·Q4).

남의 도메인(runs·user)을 엮으므로 Action 이다. 실행은 runs 의 selectors 로만 읽고, 잠금 행·지금 결과는
actions/scope3_state 의 것을 그대로 쓴다(두 번째 정본 0). models 를 직접 열지 않는다.

    exclude / restore(company_id, run_id, category, row_ids, reason, actor)   카테고리 하나 안의 줄 여럿
    factor(company_id, run_id, category, body, actor)                         줄 하나의 계수 수정(S3K2b-2)
    edits(company_id, run_id)                                                 사건이 있는 줄의 지금 상태
    history(company_id, run_id, row_id, offset, limit)                        사건(새 것 먼저)

판정 차례(Q4): ① 몸 → ② 모르는 카테고리 404 → ③ 이 회사 Scope 3 실행이 아님 404(없음·남의 회사·다른 모듈 같은 바이트) →
④ 그 (해, 카테고리) 행 FOR UPDATE(해 = 실행 options.reportYear, 꼴이 아니면 stale_run) → ⑤ 잠김 409 locked(잠근 실행
자신이어도 — 풀면 R 로 돌아간다) → ⑥ 그 잠금 아래에서 지금 결과를 다시 셈, 이 실행이 아니면 409 stale_run(옛 실행은
히스토리 읽기만) → ⑦ 그 실행 그 카테고리의 줄이 아니면 422 → ⑧ 이미 그 상태인 줄은 건너뜀, 나머지 줄마다 사건 하나.
거절이면 ④ 가 둔 빈 상태 행도 되돌린다(어느 거절이든 행 0).
계수 수정은 ⑦ 까지 같고 ⑧ 고칠 수 없는 줄 409 factor_not_editable → ⑨ 그 줄에 없는 추천 순위 422 → ⑩ 지금 계수 상태와
같은 고름이면 사건 0, 아니면 셈해 사건 하나. 고친 값은 사건에 남고 결과 본문은 덮지 않는다(MARC-ENT-442).
사건은 쓰기 전에 한 번 읽고 쓴 것을 메모리에서 합친다(561 L4).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import uuid4

from django.db import transaction

from esgapi.inventory.flows.binding_157 import MODULE
from esgapi.inventory.service.actions import scope3_state
from esgapi.inventory.service.actions.scope3_state import CategoryState, StaleRun
from esgapi.inventory.service.selectors import scope3_edits as selectors
from esgapi.inventory.service.services import scope3_edits as services
from esgapi.inventory.service.utils.entries import Actor, Locked
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound
from esgapi.inventory.service.utils.index_selection import YEAR_FIRST, YEAR_LAST
from esgapi.inventory.service.utils.scope3_edits import (
    FACTOR_AXIS,
    REASON_BAD,
    ROW_AXIS,
    ROW_IDS_UNKNOWN,
    SCOPE3_REASON_MAX,
    EditKind,
    Event,
    check_body,
    fold,
    row_of,
    rows_of,
)
from esgapi.inventory.service.utils.scope3_factors import (
    Choice,
    Custom,
    Factor,
    FactorBody,
    check_factor_body,
    chosen,
    editable,
    same_choice,
)
from esgapi.inventory.service.utils.scope3_state import CATEGORIES, Base
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.user.service.selectors.user import people_of

EXCLUDE: Final = "exclude"
RESTORE: Final = "restore"
FACTOR: Final = "factor"


@dataclass(frozen=True, slots=True)
class FactorNotEditable:
    """이 줄은 계수를 고칠 수 없다(C12·C15·칸이 모자란 줄·본문과 식이 어긋난 줄 — 409)."""


@dataclass(frozen=True, slots=True)
class RowState:
    """사건이 있는 줄의 지금 상태. by = (users.pk, 이름) — 못 찾으면 None."""

    row_id: str
    category: str
    excluded: bool
    factor: Factor | None
    at: datetime
    by: tuple[int, str] | None


@dataclass(frozen=True, slots=True)
class EditResult:
    category: CategoryState
    rows: tuple[RowState, ...]


@dataclass(frozen=True, slots=True)
class Edits:
    run_id: int
    rows: tuple[RowState, ...]


@dataclass(frozen=True, slots=True)
class HistoryLine:
    id: int
    row_id: str
    category: str
    kind: EditKind
    reason: str
    at: datetime
    by: tuple[int, str] | None
    batch_id: str | None
    factor: Factor | None


@dataclass(frozen=True, slots=True)
class HistoryPage:
    count: int
    lines: tuple[HistoryLine, ...]


def _scope3_run(company_id: int, run_id: int) -> run_selectors.Run | None:
    """이 회사의 Scope 3 실행. 없음·남의 회사·다른 모듈은 None(같은 404)."""
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    return run if run is not None and run.module == MODULE else None


def _year_of(run: run_selectors.Run) -> int | None:
    """실행의 해(options.reportYear) — 정수가 아니거나 범위 밖이면 None."""
    year = run.options.get("reportYear")
    if not isinstance(year, int) or isinstance(year, bool) or not YEAR_FIRST <= year <= YEAR_LAST:
        return None
    return year


def _by(event: Event, people: dict[int, tuple[str, str]]) -> tuple[int, str] | None:
    person = people.get(event.actor_user_id)
    return None if person is None else (event.actor_user_id, person[1])


def _state(lines: Sequence[Event], people: dict[int, tuple[str, str]]) -> RowState:
    """줄 하나의 축 사건들 → 지금 상태. 때·사람은 두 축 중 가장 큰 id 사건(R5)."""
    last = max(lines, key=lambda event: event.id)
    return RowState(
        row_id=last.row_id,
        category=last.category,
        excluded=any(event.kind == EXCLUDE for event in lines),
        factor=next((event.factor for event in lines if event.factor is not None), None),
        at=last.at,
        by=_by(last, people),
    )


def _states(company_id: int, events: Sequence[Event], only: frozenset[str] | None = None) -> tuple[RowState, ...]:
    """사건 → 줄의 지금 상태(rowId 차례). only 를 주면 그 줄만."""
    split: dict[str, list[Event]] = {}
    for (_, row_id, _), event in fold(events).items():
        if only is None or row_id in only:
            split.setdefault(row_id, []).append(event)
    people = people_of(company_id, {event.actor_user_id for lines in split.values() for event in lines})
    return tuple(_state(split[row_id], people) for row_id in sorted(split))


def _judged(
    result: Mapping[str, object] | None, category: str, body: FactorBody, flow: str
) -> Factor | Invalid | FactorNotEditable:
    """판정 ⑦~⑨ — 사건에 남길 값(또는 거절)."""
    row = row_of(result, category, body.row_id)
    if result is None or row is None:
        return Invalid({"rowId": ROW_IDS_UNKNOWN})
    if not editable(row, result.get("schemaVersion"), flow):
        return FactorNotEditable()
    book = result.get("factorBook")
    wanted = chosen(body, row, cast("Mapping[str, object]", book) if isinstance(book, Mapping) else {})
    if wanted is None:  # editable 이 막았어야 한다 — 500 이 아니라 닫힌 쪽으로(처분 B3)
        return FactorNotEditable()
    return wanted


def _refused[T](found: T) -> T:
    transaction.set_rollback(True)  # ④ 가 둔 빈 상태 행도 되돌린다 — 어느 거절이든 행 0(scope3_state.lock 꼴)
    return found


def _held(
    company_id: int, run_id: int, category: str
) -> tuple[int, run_selectors.Run, Base] | NotFound | Locked | StaleRun:
    """판정 ②~⑥: (해, 실행, 지금 결과). ④ 뒤 거절은 빈 상태 행도 되돌린다.

    실행 done 전이는 카테고리 행을 잡지 않는다: ⑥ 직후 새 실행이 R 이 되면 편집은 밀린 실행에 붙고(570 상 옛 실행
    히스토리에 남고 셈에서 빠짐) 응답 category 는 옛 base — 웹은 응답 뒤 연도 상태를 다시 읽는다(S3W3)."""
    if category not in CATEGORIES:
        return NotFound()
    run = _scope3_run(company_id, run_id)
    if run is None:
        return NotFound()
    year = _year_of(run)
    if year is None:
        return StaleRun()
    row = scope3_state.hold_row(company_id, year, category)
    if row.lock is not None:
        return _refused(Locked())
    base = scope3_state.base_of(company_id, year)
    if base.run_id != run_id:
        return _refused(StaleRun())
    return year, run, base


def _edit(
    company_id: int, run_id: int, category: str, row_ids: Sequence[str], reason: str, actor: Actor, kind: EditKind
) -> EditResult | Invalid | NotFound | Locked | StaleRun:
    stripped = check_body(row_ids, reason)
    if isinstance(stripped, Invalid):
        return stripped
    held = _held(company_id, run_id, category)
    if not isinstance(held, tuple):
        return held
    year, _, base = held
    if not set(row_ids) <= rows_of(base.body, category):
        return _refused(Invalid({"rowIds": ROW_IDS_UNKNOWN}))
    events = selectors.events_of(company_id, [run_id])
    now = fold(events)
    wanted = kind == EXCLUDE

    def is_excluded(row_id: str) -> bool:
        event = now.get((run_id, row_id, ROW_AXIS))
        return event is not None and event.kind == EXCLUDE

    changed = [row_id for row_id in row_ids if is_excluded(row_id) != wanted]
    if changed:
        events = [*events, *services.add_events(company_id, run_id, category, kind, stripped, actor, changed, uuid4())]
    return EditResult(
        category=scope3_state.category_state(company_id, year, category, base, events=events),
        rows=_states(company_id, events, frozenset(row_ids)),
    )


@transaction.atomic
def exclude(
    company_id: int, run_id: int, category: str, row_ids: Sequence[str], reason: str, actor: Actor
) -> EditResult | Invalid | NotFound | Locked | StaleRun:
    """줄들을 산정에서 뺀다 — 그 카테고리 지금 결과 실행의 줄만. 이미 빠진 줄은 건너뛴다."""
    return _edit(company_id, run_id, category, row_ids, reason, actor, EXCLUDE)


@transaction.atomic
def restore(
    company_id: int, run_id: int, category: str, row_ids: Sequence[str], reason: str, actor: Actor
) -> EditResult | Invalid | NotFound | Locked | StaleRun:
    """뺀 줄을 되돌린다 — 새 사건 하나(지우지 않는다). 빠져 있지 않은 줄은 건너뛴다."""
    return _edit(company_id, run_id, category, row_ids, reason, actor, RESTORE)


def check_factor(
    row_id: str, choice: Choice, rank: int | None, custom: Custom | None, reason: str
) -> FactorBody | Invalid:
    """몸 검사(판정 ①) — 사유 규칙은 제외·복구와 같다."""
    return check_factor_body(row_id, choice, rank, custom, reason, SCOPE3_REASON_MAX, REASON_BAD)


@transaction.atomic
def factor(
    company_id: int, run_id: int, category: str, body: FactorBody | Invalid, actor: Actor
) -> EditResult | Invalid | NotFound | Locked | StaleRun | FactorNotEditable:
    """지금 결과 실행의 줄 하나의 계수를 고른다(적용·추천 n·직접 입력). AI 를 안 부르고 식으로 센다.
    같은 고름이면 사건 0. 실행 done 틈은 `_held` 글과 같다 — 응답 뒤 웹이 연도 상태를 다시 읽는다."""
    if isinstance(body, Invalid):
        return body
    held = _held(company_id, run_id, category)
    if not isinstance(held, tuple):
        return held
    year, run, base = held
    wanted = _judged(base.body, category, body, run.flow_id)
    if not isinstance(wanted, Factor):
        return _refused(wanted)
    events = selectors.events_of(company_id, [run_id])
    last = fold(events).get((run_id, body.row_id, FACTOR_AXIS))
    if not same_choice(None if last is None else last.factor, body, wanted):
        events = [
            *events,
            *services.add_events(
                company_id, run_id, category, FACTOR, body.reason, actor, [body.row_id], uuid4(), wanted
            ),
        ]
    return EditResult(
        category=scope3_state.category_state(company_id, year, category, base, events=events),
        rows=_states(company_id, events, frozenset({body.row_id})),
    )


def edits(company_id: int, run_id: int) -> Edits | NotFound:
    """그 실행에서 사건이 하나라도 있는 줄의 지금 상태. 옛 실행도 읽는다."""
    if _scope3_run(company_id, run_id) is None:
        return NotFound()
    return Edits(run_id=run_id, rows=_states(company_id, selectors.events_of(company_id, [run_id])))


def history(company_id: int, run_id: int, row_id: str | None, *, offset: int, limit: int) -> HistoryPage | NotFound:
    """그 실행의 사건(새 것 먼저). row_id 를 주면 그 줄만. 옛 실행도 읽는다(570 — 옛 편집은 그 실행 히스토리에 남음)."""
    if _scope3_run(company_id, run_id) is None:
        return NotFound()
    count, events = selectors.history_page(company_id, run_id, row_id, offset=offset, limit=limit)
    people = people_of(company_id, {event.actor_user_id for event in events})
    return HistoryPage(
        count=count,
        lines=tuple(
            HistoryLine(
                id=event.id,
                row_id=event.row_id,
                category=event.category,
                kind=event.kind,
                reason=event.reason,
                at=event.at,
                by=_by(event, people),
                batch_id=event.batch_id,
                factor=event.factor,
            )
            for event in events
        ),
    )
