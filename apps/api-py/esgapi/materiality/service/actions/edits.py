"""결과 글 칸 고침의 읽기·저장(GET·POST /materiality/runs/{run_id}/result/edits — 밴드 IRS3 ②, 결정 MARC-ENT-561).
runs(실행·결과)·user(이름)를 엮으므로 Action 이다(Service·Selector 는 남의 도메인을 import 하지 않는다).

    edits_state(company_id, run_id)                                    materiality.result-edits@1 | 거절 갈래
    save(company_id, user_id, run_id, base_revision, changes, now)     저장 뒤 materiality.result-edits@1 | 거절 갈래

거절 갈래: NotFound·RunNotDone(actions/result.py 의 것 — 결과 GET 과 같은 404·409) · Invalid(400 INVALID_EDIT, 한국어
한 문장 — outputs/edits.check) · EditConflict(409 EDIT_CONFLICT, 지금 revision).
저장 차례(한 트랜잭션 — @transaction.atomic, 발주서 §2-5·critic 2차):
  1. 실행 찾기·갈래(find_run(company_id=…) — 남의 회사 실행은 없는 실행) → 원본 본문(result@2)
  2. 지금 고침(selectors.current_edits) → outputs/edits.check(원본 + 지금 고침 + 이 저장) — 거절이면 쓰기 0
  3. 머리가 없고 baseRevision ≠ 0 이면 머리를 만들기 전에 EditConflict(0). 없으면 revision 0 으로 만든다
  4. 조건부 UPDATE(bump_head — revision = base 일 때만 +1). 0 행이면 EditConflict(지금 revision) — 블록 되돌림
  5. 고침 행(revision = base + 1)
거절(400·409)은 블록 전체를 되돌린다(set_rollback) — 고아 머리 행 0. 감사 줄 0(고침 행이 이력 — 발주서 Q10).
★ 이름은 user 의 people_of(그 회사의 고객사 사용자와 운영 관리자)로 한 번에 푼다. 못 풀면 「알 수 없는 사용자」.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction

from esgapi.core.schemas import to_seoul_iso
from esgapi.materiality.contracts.edit_shapes import EDITS_SHAPE, MaterialityResultEdits
from esgapi.materiality.outputs import edits as rules
from esgapi.materiality.service.actions.result import NotFound, RunNotDone, original_result
from esgapi.materiality.service.selectors import edits as selectors
from esgapi.materiality.service.selectors.edits import CurrentEdit
from esgapi.materiality.service.services import edits as services
from esgapi.user.service.selectors.user import people_of

UNKNOWN_USER = "알 수 없는 사용자"


@dataclass(frozen=True, slots=True)
class Invalid:
    message: str


@dataclass(frozen=True, slots=True)
class EditConflict:
    revision: int


type Refusal = NotFound | RunNotDone | Invalid | EditConflict


def current_values(company_id: int, run_id: int) -> dict[str, str | None]:
    """바른 주소 → 지금 값."""
    return {row.pointer: row.value for row in selectors.current_edits(company_id=company_id, run_id=run_id)}


def _state(company_id: int, run_id: int, body: dict[str, Any]) -> MaterialityResultEdits:
    rows = selectors.current_edits(company_id=company_id, run_id=run_id)
    by_pointer: dict[str, CurrentEdit] = {row.pointer: row for row in rows}
    listed = rules.listing(body, {row.pointer: row.value for row in rows})
    wanted = {by_pointer[pointer].edited_by_user_id for pointer, _, _ in listed}
    found = people_of(company_id, wanted) if wanted else {}
    names = {user: found[user][1] for user in found if found[user][1].strip()}
    return {
        "schemaVersion": EDITS_SHAPE,
        "revision": selectors.head_revision(company_id=company_id, run_id=run_id) or 0,
        "edits": [
            {
                "pointer": pointer,
                "value": value,
                "original": original,
                "editedAt": to_seoul_iso(by_pointer[pointer].created_at),
                "editedBy": {"name": names.get(by_pointer[pointer].edited_by_user_id, UNKNOWN_USER)},
            }
            for pointer, value, original in listed
        ],
    }


def edits_state(*, company_id: int, run_id: int) -> MaterialityResultEdits | NotFound | RunNotDone:
    body = original_result(company_id=company_id, run_id=run_id)
    if isinstance(body, NotFound | RunNotDone):
        return body
    return _state(company_id, run_id, body)


@transaction.atomic
def save(
    *,
    company_id: int,
    user_id: int,
    run_id: int,
    base_revision: int,
    changes: Sequence[tuple[str, str | None]],
    now: datetime,
) -> MaterialityResultEdits | Refusal:
    body = original_result(company_id=company_id, run_id=run_id)
    if isinstance(body, NotFound | RunNotDone):
        return body
    checked = rules.check(body, current_values(company_id, run_id), changes)
    if isinstance(checked, rules.Invalid):
        return Invalid(checked.message)
    head = selectors.head_revision(company_id=company_id, run_id=run_id)
    if head is None and base_revision != 0:
        return EditConflict(0)  # 머리를 만들기 전에(critic 2차)
    if head is None:
        services.create_head(company_id=company_id, run_id=run_id)
    if services.bump_head(company_id=company_id, run_id=run_id, base_revision=base_revision, now=now) == 0:
        revision = selectors.head_revision(company_id=company_id, run_id=run_id) or 0  # 되돌림 표시 앞에 읽는다
        transaction.set_rollback(True)  # 겹친 저장이 만든 머리 말고는 이 블록이 쓴 것 0
        return EditConflict(revision)
    services.insert_edits(
        company_id=company_id, run_id=run_id, revision=base_revision + 1, user_id=user_id, changes=checked
    )
    return _state(company_id, run_id, body)
