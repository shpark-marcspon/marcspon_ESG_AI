"""쓰기. 검토 행과 표시 행. 읽지 않는다(읽기는 selectors/review.py). 부르는 쪽(actions/review.py)이 한 트랜잭션
안에서 검토 행을 먼저 만들거나 잠근 뒤 표시를 쓴다 — 표시 → 검토의 같은 회사 복합 외래 키(migrations/0001)가 그 차례를
요구한다.

    create_review(company_id, run_id)                     없으면 pending 으로 만든다(세이브포인트 안 INSERT)
    set_state(company_id, run_id, state, at, by)          상태(확정이면 때·사람)를 고친다
    write_marks(company_id, run_id, inserts, updates)     표시·고침을 넣고 고친다. 지우지 않는다(지우기 = NULL)
    append_rejudge(company_id, run_id, item_index, rejudge_run_id)
                                                          그 문장 행의 재판단 실행 id 목록 끝에 하나 붙인다(GRJ1 —
                                                          부르는 쪽이 검토 행을 잠근 뒤. 행이 없으면 만든다)
    import_review(company_id, rows, user_id)              실행 묶음(RX1b)의 검토 행을 넣는다 — 확정 사람 = user_id,
                                                          때 그대로, created_at·updated_at 은 묶음 값으로 되돌림.
                                                          같은 실행의 검토가 이미 있으면 False(쓰기 0)
    import_marks(company_id, rows, user_id)               실행 묶음의 표시 행을 넣는다 — 고친 칸의 사람 = user_id,
                                                          때 그대로, 시각 되돌림. 검토 다음에 부른다(복합 외래 키)

★ 만들기 경합: 두 PUT 이 같은 실행에 처음 겹치면 둘 다 INSERT 한다. 안쪽 atomic(세이브포인트)이 둘째의 IntegrityError
  (unique (company_id, run_id))를 받아 그 세이브포인트만 되돌린다 — 바깥 트랜잭션은 깨지지 않고, 부르는 쪽이 이어서
  FOR UPDATE 로 잠가 차례를 세운다. 넘기는 것은 어긴 제약이 REVIEW_UNIQUE 일 때뿐이다 — 다른 제약·이름을 못 읽음은
  다시 던진다(MARC-ISSUE-220 (2), core/service/services/documents.py 의 _unique_broken 꼴).
  생성자 <Row>(…) 는 쓰지 않는다(core/tests/isolation/test_static_rules.py 받침 ④).
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from django.db import IntegrityError, transaction

from esgapi.greenwash.models import GreenwashReviewMarkRow, GreenwashReviewRow

Decision = tuple[str | None, str | None]  # (decision, exclude_reason). (None, None) = 미검토
Columns = Mapping[str, Any]  # 표시 표의 칸 이름 → 값(decision·exclude_reason·고침 칸 아홉 — models.py)
REVIEW_UNIQUE = "greenwash_reviews_company_run_uniq"  # migrations/0001_initial.py


def _broken(err: IntegrityError) -> str | None:
    """IntegrityError 가 어긴 제약의 이름(psycopg 의 diag). 모르면 None."""
    diag = getattr(err.__cause__, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


def create_review(*, company_id: int, run_id: int) -> None:
    try:
        with transaction.atomic():
            GreenwashReviewRow.for_company(company_id).create(company_id=company_id, run_id=run_id, state="pending")
    except IntegrityError as err:
        if _broken(err) != REVIEW_UNIQUE:
            raise
        # 겹친 PUT 이 먼저 만들었다(머리말)


@transaction.atomic
def set_state(
    *, company_id: int, run_id: int, state: str, confirmed_at: datetime | None, confirmed_by_user_id: int | None
) -> None:
    GreenwashReviewRow.for_company(company_id).filter(run_id=run_id).update(
        state=state, confirmed_at=confirmed_at, confirmed_by_user_id=confirmed_by_user_id
    )


@transaction.atomic
def write_marks(
    *, company_id: int, run_id: int, inserts: Mapping[int, Columns], updates: Mapping[int, Columns]
) -> None:
    """inserts 는 행이 없던 itemIndex(행 전체 값 — 빠진 칸은 NULL), updates 는 행이 있던 itemIndex 의 바뀐 칸만
    (UPDATE 는 그 칸들만 쓴다 — 다른 칸의 값·때·사람은 그대로)."""
    for index, columns in sorted(inserts.items()):
        GreenwashReviewMarkRow.for_company(company_id).create(
            company_id=company_id, run_id=run_id, item_index=index, **columns
        )
    for index, columns in sorted(updates.items()):
        if columns:
            GreenwashReviewMarkRow.for_company(company_id).filter(run_id=run_id, item_index=index).update(**columns)


@transaction.atomic
def append_rejudge(*, company_id: int, run_id: int, item_index: int, rejudge_run_id: int) -> None:
    """붙이기만 한다(앞 id 는 그대로). 읽고 쓰기 사이의 경합은 부르는 쪽의 검토 행 FOR UPDATE 가 줄 세운다."""
    rows = GreenwashReviewMarkRow.for_company(company_id).filter(run_id=run_id, item_index=item_index)
    row = rows.first()
    if row is None:
        GreenwashReviewMarkRow.for_company(company_id).create(
            company_id=company_id, run_id=run_id, item_index=item_index, rejudge_run_ids=[rejudge_run_id]
        )
        return
    rows.update(rejudge_run_ids=[*(row.rejudge_run_ids or []), rejudge_run_id])


EDITS = (
    ("level_edited_at", "level_edited_by_user_id"),
    ("reasons_edited_at", "reasons_edited_by_user_id"),
    ("fix_edited_at", "fix_edited_by_user_id"),
    ("evidence_edited_at", "evidence_edited_by_user_id"),
)
TIMES = ("created_at", "updated_at")


@transaction.atomic
def import_review(*, company_id: int, rows: tuple[Columns, ...], user_id: int) -> bool:
    """rows 는 run_id(받는 쪽 새 id)·state·confirmed_at·created_at·updated_at. 넣기만 한다(있는 행 고침 0)."""
    runs = [row["run_id"] for row in rows]
    if GreenwashReviewRow.for_company(company_id).filter(run_id__in=runs).exists():
        return False
    for row in rows:
        made = GreenwashReviewRow.for_company(company_id).create(
            company_id=company_id,
            run_id=row["run_id"],
            state=row["state"],
            confirmed_at=row["confirmed_at"],
            confirmed_by_user_id=None if row["confirmed_at"] is None else user_id,
        )
        GreenwashReviewRow.for_company(company_id).filter(id=made.id).update(**{name: row[name] for name in TIMES})
    return True


@transaction.atomic
def import_marks(*, company_id: int, rows: tuple[Columns, ...], user_id: int) -> None:
    """rows 는 MARK 칸(run_id 는 새 id) + created_at·updated_at. 고친 칸의 사람은 때가 있을 때만 user_id."""
    for row in rows:
        people = {by: None if row[at] is None else user_id for at, by in EDITS}
        values = {name: value for name, value in row.items() if name not in TIMES}
        made = GreenwashReviewMarkRow.for_company(company_id).create(company_id=company_id, **values, **people)
        GreenwashReviewMarkRow.for_company(company_id).filter(id=made.id).update(**{name: row[name] for name in TIMES})
