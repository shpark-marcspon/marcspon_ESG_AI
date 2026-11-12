"""계정 수정(UA1 — 결정 MARC-ENT-281 의 4): 이름·사용 중지. 사용 중지가 바뀌면 users 와 user_refresh_tokens 두 표에
쓴다 → `@transaction.atomic` 함수(E1b 의 규칙).

차례: 권한(첫 줄) → 행 잠금(Selector) → 대상 확인(그 회사의 고객사 사용자, 쓸 수 있는 비밀번호) → 칸 싣기 →
is_active 가 바뀌었으면 그 사람의 끊기지 않은 refresh 전부 끊기 → 기록 줄.
★ 끊는 까닭: 사용 중지 뒤 다시 사용하면 옛 refresh 가 되살아나지 않게(처분 ②·개정 2 N1 — 켤 때도 끊는다. 같은 값을
  다시 보내면 끊지 않는다). 이미 낸 access 는 만료(30분)까지 통한다 — access 검사는 DB 를 읽지 않는다(R13).
행 잠금은 Selector 를 부른다(select_for_update 는 user/service/selectors 에만). 거절은 값으로 돌려준다.
"""

from datetime import datetime

from django.db import transaction

from esgapi.core.auth.principal import Kind
from esgapi.user.models import RefreshToken
from esgapi.user.service.permissions.user import Forbidden, can_manage_customer_users, is_resettable
from esgapi.user.service.selectors import user as selectors
from esgapi.user.service.services import login as services
from esgapi.user.service.utils.login import UserNotFound, UserUpdated


@transaction.atomic
def update_customer_user(
    *,
    actor_kind: Kind,
    company_id: int,
    user_id: int,
    name: str | None,
    is_active: bool | None,
    now: datetime,
    actor_user_id: int | None = None,
) -> UserUpdated | UserNotFound | Forbidden:
    """그 회사의 고객사 사용자의 이름·사용 여부를 바꾼다. 운영 관리자만(첫 줄 — 막히면 아무것도 안 읽고 안 쓴다).
    남의 회사의 id·운영 관리자의 id·없는 id·교환이 만든 행(비밀번호를 쓸 수 없음 — D5)이면 UserNotFound(행 0 변화).
    None 인 칸은 그대로 둔다. 같은 값을 다시 보내도 UserUpdated(멱등 — 그때 refresh 는 끊지 않는다)."""
    if not can_manage_customer_users(actor_kind):
        return Forbidden("user_update")
    row = selectors.lock_account(company_id, user_id)
    if row is None or not is_resettable(row.kind) or not row.has_usable_password():
        return UserNotFound()
    fields: list[str] = []
    if name is not None and name != row.name:
        row.name = name
        fields.append("name")
    if is_active is not None and is_active != row.is_active:
        row.is_active = is_active
        fields.append("is_active")
    if fields:
        row.save(update_fields=fields)
    if "is_active" in fields:
        RefreshToken.of_user(row.pk).filter(revoked_at__isnull=True).update(revoked_at=now)
    # 감사 줄은 이 블록의 세이브포인트다(K-B4). 멱등 수정(바뀐 칸 0)도 한 줄 — changed_fields 빈 목록(개정 1 N6)
    kind, who = services.audit_actor(actor_kind, actor_user_id)
    services.note(
        "user_updated",
        row,
        now=now,
        actor_user_id=actor_user_id,
        fields=tuple(fields),
        audit_actor_kind=kind,
        audit_actor_user_id=who,
    )
    return UserUpdated(row.pk)
