"""쓰기. 유스케이스 하나: 감사 기록 한 줄(record_event). HTTP 를 모른다. 모든 앱의 기록 지점이 이것을 부른다
(core 는 업무를 모르고 업무는 core 를 딛는다 — `.importlinter` 계약 가).

결과는 예외가 아니라 갈래로 돌려준다: AuditRecorded(썼다) · AuditRefused(쓰지 않았다 — 꼴 밖이거나 DB 가 거절).
★ 던지지 않는다(K-B4): 부르는 쪽이 업무 블록 안일 수 있다(reset_password·update_customer_user 의 @transaction.atomic).
  꼴은 쓰기 전에 순수 함수(core/calc/audit.py 의 check_event)에서 보고, DB 오류(권한·CHECK·값)는 자기 블록(부르는 쪽이
  블록 안이면 세이브포인트) **밖에서** 잡아 그 블록만 되돌린다 — 업무는 그대로 이어진다(처분 ⑱ (가)).
  잡으면 경고 한 줄(로거 esgapi.audit, event audit_refused): 글에는 예외의 클래스 이름과 SQLSTATE 만 싣는다.
  예외 글(str(error))·exc_info·PG 의 DETAIL(「Failing row contains …」 — 넣은 값이 그대로 실린다)은 싣지 않는다.
★ 기록 실패는 업무를 바꾸지 않는다(§1-6). 무효 조건: 운영에서 권한이 빠지면 경고 줄만 남고 감사 줄은 빠진다(알림은 2차).
★ 부르는 자리는 업무 블록이 닫힌 뒤가 보통이다(처분 ⑨ (가)): 업무 커밋과 이 커밋 사이에 프로세스가 죽으면 그 사건의
  줄이 빠진다(되돌려진 사건이 적히는 일은 없다 — 성공 뒤에만 부른다).

회사 칸이 있는 줄은 AuditEventRow.for_company(company_id) 로, 회사 칸이 NULL 인 줄은 이름 붙은 입구
AuditEventRow.operator_rows() 로 쓴다(core/tests/isolation/test_static_rules.py 의 AUDIT_ENTRANCES).
요청 id 는 관측의 문맥(core/observability/context.py)에서 읽는다 — 요청 밖(명령)이면 NULL.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from django.db import DatabaseError, transaction

from esgapi.core.calc.audit import EventRefused, audit_detail, check_event
from esgapi.core.models import AuditEventRow
from esgapi.core.observability.context import current_request_id

log = logging.getLogger("esgapi.audit")


@dataclass(frozen=True, slots=True)
class AuditRecorded:
    id: int


@dataclass(frozen=True, slots=True)
class AuditRefused:
    """쓰지 않았다. why 는 어긋난 칸의 이름(꼴 밖) 또는 db_error 다(값은 싣지 않는다)."""

    why: str


def _sqlstate(error: BaseException) -> str | None:
    """Django 의 DB 예외는 psycopg 의 예외를 __cause__ 로 품는다. 거기의 SQLSTATE(core/llm/sink_db.py 와 같은 꼴)."""
    for candidate in (error, error.__cause__):
        code = cast("object", getattr(candidate, "sqlstate", None))
        if isinstance(code, str):
            return code
    return None


def record_event(
    *,
    at: datetime,
    company_id: int | None,
    actor_kind: str,
    actor_user_id: int | None,
    action: str,
    event: str,
    result: str,
    reason: str | None = None,
    target_kind: str | None = None,
    target_id: int | None = None,
    target_label: str | None = None,
    changed_fields: tuple[str, ...] | None = None,
    module: str | None = None,
) -> AuditRecorded | AuditRefused:
    """감사 기록 한 줄. 꼴이 맞으면 한 표 블록에서 넣는다. 던지지 않는다(위 머리말).
    뒤 밴드가 칸을 더할 때는 이름 있는 인자 하나와 detail 의 이름 있는 칸 하나를 같이 더한다
    (detail 을 통째로 받지 않는다)."""
    refused = check_event(
        company_id=company_id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        action=action,
        event=event,
        result=result,
        reason=reason,
        target_kind=target_kind,
        target_id=target_id,
        target_label=target_label,
        changed_fields=changed_fields,
        module=module,
    )
    if isinstance(refused, EventRefused):
        log.warning("audit_refused field=%s", refused.field, extra={"event": "audit_refused"})
        return AuditRefused(refused.field)
    fields = {
        "at": at,
        "actor_kind": actor_kind,
        "actor_user_id": actor_user_id,
        "action": action,
        "event": event,
        "result": result,
        "reason": reason,
        "target_kind": target_kind,
        "target_id": target_id,
        "target_label": target_label,
        "detail": audit_detail(changed_fields, module),
        "request_id": current_request_id(),
    }
    try:
        # 블록은 하나다(두 갈래가 같은 블록 — 쓰기를 블록 둘로 쪼개지 않는다). 부르는 쪽의 블록 안이면 세이브포인트.
        with transaction.atomic():
            if company_id is not None:
                row = AuditEventRow.for_company(company_id).create(company_id=company_id, **fields)
            else:
                row = AuditEventRow.operator_rows().create(company_id=None, **fields)
    except DatabaseError as error:
        # 세이브포인트 블록 **밖에서** 잡는다(안에서 잡으면 Django 가 되돌리지 않아 바깥 트랜잭션이 깨진 채 남는다).
        log.warning(
            "audit_refused error_class=%s sqlstate=%s",
            type(error).__name__,
            _sqlstate(error),
            extra={"event": "audit_refused"},
        )
        return AuditRefused("db_error")
    return AuditRecorded(row.id)
