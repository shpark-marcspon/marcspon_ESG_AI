"""쓰기. 결과 글 칸 고침의 머리·고침 표(밴드 IRS3 — 결정 MARC-ENT-561). 표마다 함수 하나다. 읽지 않는다(읽기는
selectors/edits.py). 부르는 쪽(actions/edits.save — @transaction.atomic)이 한 트랜잭션 안에서 머리를 만들고(없으면)
revision 을 올린 뒤 고침을 넣는다 — 고침 → 머리의 같은 회사 복합 외래 키(migrations/0002)가 그 차례를 요구한다.

    create_head(company_id, run_id)                           없으면 revision 0 으로 만든다(세이브포인트 안 INSERT)
    bump_head(company_id, run_id, base_revision, now)         revision = base 일 때만 +1(조건부 UPDATE). 고친 행 수
    insert_edits(company_id, run_id, revision, user_id, changes)   고침 행을 넣는다(불변 — 저장 = 새 행)

★ 만들기 경합: 두 저장이 같은 실행에 처음 겹치면 둘 다 INSERT 한다. 안쪽 atomic(세이브포인트)이 둘째의 IntegrityError
  (unique (company_id, run_id))를 받아 그 세이브포인트만 되돌린다 — 넘기는 것은 어긴 제약이 HEAD_UNIQUE 일 때뿐이다
  (다른 제약·이름을 못 읽음은 다시 던진다 — greenwash services/review.py 의 create_review 꼴).
★ 낙관 잠금: bump_head 는 `UPDATE … SET revision = revision + 1 WHERE company_id = ? AND run_id = ? AND revision = base`
  하나다(FOR UPDATE 0). 겹친 저장은 앞 것이 커밋할 때까지 그 행에서 기다리고, 다시 본 조건이 어긋나면 0 행 — 부르는
  쪽이 409 EDIT_CONFLICT. 앱 역할의 머리 UPDATE 권한은 (revision, updated_at) 두 칸뿐이다(save() 0).
생성자 <Row>(…) 는 쓰지 않는다(core/tests/isolation/test_static_rules.py 받침 ④).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final

from django.db import IntegrityError, transaction
from django.db.models import F

from esgapi.materiality.models import MaterialityResultEditHeadRow, MaterialityResultEditRow

HEAD_UNIQUE: Final = "materiality_result_edit_heads_company_run_uniq"  # migrations/0002_result_edits.py


def _broken(err: IntegrityError) -> str | None:
    """IntegrityError 가 어긴 제약의 이름(psycopg 의 diag). 모르면 None."""
    diag = getattr(err.__cause__, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


def create_head(*, company_id: int, run_id: int) -> None:
    try:
        with transaction.atomic():
            MaterialityResultEditHeadRow.for_company(company_id).create(
                company_id=company_id, run_id=run_id, revision=0
            )
    except IntegrityError as err:
        if _broken(err) != HEAD_UNIQUE:
            raise
        # 겹친 저장이 먼저 만들었다(머리말)


@transaction.atomic
def bump_head(*, company_id: int, run_id: int, base_revision: int, now: datetime) -> int:
    return (
        MaterialityResultEditHeadRow.for_company(company_id)
        .filter(run_id=run_id, revision=base_revision)
        .update(revision=F("revision") + 1, updated_at=now)
    )


@transaction.atomic
def insert_edits(
    *, company_id: int, run_id: int, revision: int, user_id: int, changes: Sequence[tuple[str, str | None]]
) -> None:
    for pointer, value in changes:
        MaterialityResultEditRow.for_company(company_id).create(
            company_id=company_id,
            run_id=run_id,
            revision=revision,
            pointer=pointer,
            value=value,
            edited_by_user_id=user_id,
        )
