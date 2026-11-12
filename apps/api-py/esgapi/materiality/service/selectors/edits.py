"""읽기. 결과 글 칸 고침의 머리·고침 표(밴드 IRS3 — materiality_result_edit_heads·materiality_result_edits). 쓰지 않는다
(쓰기는 services/edits.py). 잠그지 않는다 — 저장의 차례는 머리 revision 의 조건부 UPDATE 하나가 세운다(FOR UPDATE 0).

    head_revision(company_id, run_id)    그 실행 머리의 revision. 머리가 없으면 None(아직 저장 없음)
    current_edits(company_id, run_id)    주소마다 가장 큰 revision 의 고침 행(지금 값) — 주소 차례

★ 조회마다 회사 조건을 적는다(<표>.for_company(company_id) — core/tests/test_selector_scope.py). run_id 는 외래 키가
  아니다 — 부르는 쪽(actions)이 runs 의 find_run 으로 그 회사·중대성평가 실행인지 먼저 본다.
"""

from dataclasses import dataclass
from datetime import datetime

from esgapi.materiality.models import MaterialityResultEditHeadRow, MaterialityResultEditRow


@dataclass(frozen=True, slots=True)
class CurrentEdit:
    """칸 하나의 지금 값(가장 큰 revision 의 행)."""

    pointer: str
    value: str | None
    revision: int
    edited_by_user_id: int
    created_at: datetime


def head_revision(*, company_id: int, run_id: int) -> int | None:
    found = (
        MaterialityResultEditHeadRow.for_company(company_id)
        .filter(run_id=run_id)
        .values_list("revision", flat=True)
        .first()
    )
    return found


def current_edits(*, company_id: int, run_id: int) -> list[CurrentEdit]:
    rows = (
        MaterialityResultEditRow.for_company(company_id)
        .filter(run_id=run_id)
        .order_by("pointer", "-revision")
        .distinct("pointer")
    )
    return [
        CurrentEdit(
            pointer=row.pointer,
            value=row.value,
            revision=row.revision,
            edited_by_user_id=row.edited_by_user_id,
            created_at=row.created_at,
        )
        for row in rows
    ]
