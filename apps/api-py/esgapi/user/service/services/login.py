"""쓰기: 로그인(username·비밀번호 → 토큰 짝), refresh 잇기(rotate), 로그아웃(revoke), 비밀번호 확인의 셈.
HTTP 를 모른다.

결과는 예외가 아니라 갈래로 돌려준다(utils/login.py). service/apis/login.py 가 갈래를 응답으로 바꾼다.
★ 블록 안에서 던지지 않는다(K-B4): 재사용 탐지의 계보 끊기·실패 셈은 「오류로 답해도」 커밋되어야 한다.
  E1b 뒤 요청마다의 트랜잭션이 없으므로 이 파일의 블록이 정상으로 닫히면 커밋된다. 거절은 블록이 닫힌 뒤 값으로 나간다.
★ 비밀번호 확인(PBKDF2 1,000,000 회)은 블록 밖에서 한다 — 행 잠금을 쥔 채 돌지 않는다.
★ 해시 한 번(K-B8): invalid_credentials 로 끝나는 갈래(회사 없음·회사 비활성·사용자 없음·사용자 비활성·쓸 수 없는
  비밀번호·틀린 비밀번호)는 전부 check_password 를 정확히 한 번 돈다(Django 의 verify_password 가 encoded 가 None·쓸 수
  없는 값이면 스스로 가짜 해시를 한 번 돈다). 예외는 잠김 하나 — 해시 0.
  서브도메인 없는 고객사 길(UA1 — 운영 관리자가 없을 때 하나뿐인 쓸 수 있는 회사)도 같다: 찾기는 둘, 해시는 한 번.
★ 로그(로거 esgapi.auth): event 와 아는 경우 user_id·company_id·user_kind 만 extra 에 싣는다. username·비밀번호·토큰 0.
★ 감사 기록(AU1a): note 가 로그 한 줄과 함께 core 의 record_event 로 감사 줄 하나를 쓴다(사건 이름 → 행동은
  EVENT_ACTIONS 한 표). 부르는 자리는 그대로다(대개 업무 블록이 닫힌 뒤 — 감사는 자기 블록으로 따로 커밋된다.
  reset_password·update_customer_user 는 그 블록 안의 세이브포인트). record_event 는 던지지 않는다(K-B4). 해시를 돌지
  않는다(K-B8). 무효 조건: 업무 커밋과 감사 커밋 사이에 프로세스가 죽으면 그 사건의 감사 줄이 빠진다(되돌려진 사건이
  적히는 일은 없다). 모르는 아이디의 로그인 실패는 「누구인지 모름」(anonymous, 사람·대상 NULL)이다 — 넣은 username 은
  note 에 넘기지 않는다.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from esgapi.core.auth.tokens import (
    RefreshActive,
    new_access_claims,
    new_refresh_claims,
    read_refresh,
    sign_access,
    sign_refresh,
)
from esgapi.core.conf import app_config
from esgapi.core.service.services.audit import record_event
from esgapi.user.models import RefreshToken, User
from esgapi.user.service.selectors import user as selectors
from esgapi.user.service.utils.login import (
    AccountGone,
    AttemptLocked,
    AttemptRecorded,
    LockState,
    LoginOk,
    LoginRejected,
    RefreshOk,
    RefreshRejected,
    Revoked,
    TokenPair,
    after_failure,
    is_locked,
)

log = logging.getLogger("esgapi.auth")

# 사건 이름(로그의 event·감사의 event) → 감사의 행동(core/calc/audit.py 의 AUDIT_ACTIONS 하나). note 를 부르는 글자는
# 전부 여기 키다 — test_login.py::test_every_note_name_has_an_action_and_every_action_is_one_of_nine 이
# 제품의 note("…") 글자 집합과 견준다.
EVENT_ACTIONS: dict[str, str] = {
    "login_succeeded": "login",
    "login_failed": "login",
    "login_locked": "login",
    "logout": "logout",
    "user_created": "setting_change",
    "password_reset": "setting_change",
    "password_changed": "setting_change",
    "user_updated": "setting_change",
}


def audit_actor(actor_kind: str, actor_user_id: int | None) -> tuple[str, int | None]:
    """감사 행위자(개정 1 B3). 권한 인자 actor_kind 는 명령도 "admin" 을 넘기므로, 사람 id 가 없으면 명령이다."""
    return ("command", None) if actor_user_id is None else (actor_kind, actor_user_id)


def note(
    event: str,
    user: User | None = None,
    *,
    now: datetime,
    actor_user_id: int | None = None,
    fields: tuple[str, ...] | None = None,
    result: str = "success",
    reason: str | None = None,
    audit_actor_kind: str | None = None,
    audit_actor_user_id: int | None = None,
    audit_company_id: int | None = None,
) -> None:
    """사건 한 줄(가8). 메시지는 사건 이름뿐이고 값은 extra 에만 싣는다.
    운영 관리자가 HTTP 로 한 일(K2c·UA1 — 만들기·초기화·수정)이면 누가(actor_user_id) 누구에게(target_user_id)
    했는지 더한다.
    fields 는 바뀐 칸의 이름뿐이다(UA1 의 수정 — 값·이름 글자는 싣지 않는다).
    그리고 감사 줄 하나(AU1a): 대상은 그 user(아이디 = 그때의 이름), 회사는 user 의 회사(user 가 없으면
    audit_company_id). 감사 행위자를 넘기지 않으면 그 user 본인이고, user 도 없으면 anonymous 다."""
    extra: dict[str, object] = {"event": event}
    if fields is not None:
        extra["changed_fields"] = list(fields)
    if user is not None:
        extra |= {"user_id": user.pk, "company_id": user.company_id, "user_kind": user.kind}
    if actor_user_id is not None:
        extra |= {"actor_user_id": actor_user_id, "target_user_id": None if user is None else user.pk}
    log.info(event, extra=extra)
    if audit_actor_kind is None:
        audit_actor_kind, audit_actor_user_id = ("anonymous", None) if user is None else (user.kind, user.pk)
    record_event(
        at=now,
        company_id=audit_company_id if user is None else user.company_id,
        actor_kind=audit_actor_kind,
        actor_user_id=audit_actor_user_id,
        # 표에 없는 이름은 빈 행동 — check_event 가 거절한다(던지지 않는다). 사전의 .get 은 서비스의 읽기 규칙
        # (core/tests/test_selector_scope.py 의 READ_ENDS)이 ORM 읽기로 보므로 쓰지 않는다.
        action=next((action for name, action in EVENT_ACTIONS.items() if name == event), ""),
        event=event,
        result=result,
        reason=reason,
        target_kind=None if user is None else "user",
        target_id=None if user is None else user.pk,
        target_label=None if user is None else user.username,
        changed_fields=fields,
    )


@dataclass(frozen=True)
class LoginPorts:
    """로그인이 바깥에 시키는 일 둘: 서브도메인 → 쓸 수 있는 회사의 id(없거나 비활성이면 None), 그리고 서브도메인이
    없을 때 하나뿐인 쓸 수 있는 회사의 id(회사가 0·둘 이상이거나 그 하나가 비활성이면 None — UA1, MARC-ENT-283).
    회사 찾기는 organization 의 selectors 라 도메인을 넘는다 — service/apis/user.py 의 login_ports() 가 꽂는다."""

    company_id_of: Callable[[str], int | None]
    sole_company_id: Callable[[], int | None]


# ── 토큰 짝 ───────────────────────────────────────────────────────────


def issue_pair(user: User, *, company_is_active: bool | None, now: datetime, family: UUID | None = None) -> TokenPair:
    """새 access·refresh 짝. refresh 행 하나를 넣는다(한 표 블록 — 부르는 쪽의 블록 안이면 세이브포인트).
    family 를 넘기면 그 계보를 잇고(rotate), 없으면 새 계보다(로그인·비밀번호 바꾸기)."""
    secret = app_config().session_secret
    refresh_claims = new_refresh_claims(
        user_id=str(user.pk), company_id=user.company_id, jti=uuid4(), family=family or uuid4(), now=now
    )
    with transaction.atomic():
        RefreshToken.issue(
            jti=refresh_claims.jti,
            family=refresh_claims.family,
            user_id=user.pk,
            issued_at=refresh_claims.issued_at,
            expires_at=refresh_claims.expires_at,
        )
    access_claims = new_access_claims(
        user_id=str(user.pk),
        kind="admin" if user.kind == "admin" else "service",
        level=user.level,
        company_id=user.company_id,
        company_is_active=company_is_active,
        is_initial=user.is_initial,
        jti=uuid4(),
        now=now,
    )
    return TokenPair(
        access=sign_access(access_claims, secret=secret),
        refresh=sign_refresh(refresh_claims, secret=secret),
        access_expires_at=access_claims.expires_at,
        refresh_expires_at=refresh_claims.expires_at,
        is_initial=user.is_initial,
        kind=access_claims.kind,
    )


def company_is_active_of(user: User) -> bool | None:
    """토큰의 company_is_active 칸. 운영 관리자는 None. 고객사 사용자는 selectors.account 가 같이 읽은 회사의 값."""
    company = user.company
    return None if company is None else bool(company.is_active)


# ── 비밀번호 확인의 셈(로그인과 바꾸기가 같이 쓴다 — 처분 B9) ─────────────


def record_password_attempt(
    *, company_id: int | None, user_id: int, ok: bool, now: datetime
) -> AttemptRecorded | AttemptLocked | AccountGone:
    """비밀번호 확인 한 번의 결과를 적는다(한 표 블록). 블록 안에서 행을 잠가 다시 읽고, 그 사이 다른 요청이 커밋한
    잠금이 있으면 맞음·틀림 어느 쪽이든 아무것도 바꾸지 않는다(K-B2). 틀림이면 셈 +1(다섯째에 잠금), 맞음이면 셈 0."""
    with transaction.atomic():
        row = selectors.lock_account(company_id, user_id)
        if row is None or not row.is_active:
            return AccountGone()
        if is_locked(row.login_expiry_at, now):
            return AttemptLocked()
        if ok:
            row.login_failed_count, row.login_expiry_at, row.last_login = 0, None, now
            row.save(update_fields=["login_failed_count", "login_expiry_at", "last_login"])
        else:
            state = after_failure(LockState(row.login_failed_count, row.login_expiry_at), now)
            row.login_failed_count, row.login_expiry_at = state.login_failed_count, state.login_expiry_at
            row.save(update_fields=["login_failed_count", "login_expiry_at"])
    return AttemptRecorded()


# ── 로그인 ────────────────────────────────────────────────────────────


def login(
    *, subdomain: str | None, username: str, password: str, now: datetime, ports: LoginPorts
) -> LoginOk | LoginRejected:
    """고객사 사용자(서브도메인 있음) 또는 운영 관리자(서브도메인 없음 — U2)를 확인해 토큰 짝을 낸다.
    서브도메인이 없으면 운영 관리자를 먼저 찾고, 그 아이디의 운영 관리자가 없을 때만 하나뿐인 쓸 수 있는 회사의 고객사
    사용자를 찾는다(UA1 — MARC-ENT-283. 회사가 둘 이상이면 운영 관리자만). 고객사 행이 운영 관리자의 길을 가로채지
    못한다.
    모든 길의 실패는 같은 invalid_credentials 이고 해시를 한 번 돈다. 잠겼으면 비밀번호를 보지 않는다."""
    if subdomain is None:
        company_id: int | None = None
        user = selectors.find_admin(username)
        if user is None:  # 운영 관리자 먼저(처분 ⑩ ㄱ) — 찾기는 둘이어도 해시는 아래 한 번이다
            company_id = ports.sole_company_id()
            user = selectors.find_customer(company_id, username) if company_id is not None else None
    else:
        company_id = ports.company_id_of(subdomain)
        user = selectors.find_customer(company_id, username) if company_id is not None else None
    if user is not None and user.is_active and is_locked(user.login_expiry_at, now):
        note("login_locked", user, now=now, result="failure", reason="account_locked")
        return LoginRejected("account_locked")
    # 사용자가 없으면 쓸 수 없는 값(무작위 글자, 해시 0)을 넘긴다 — Django 의 verify_password 가 그 값에서 가짜 해시를
    # 한 번 돈다(None 을 넘기면 identify_hasher 가 TypeError 다. Django 5.2.18 확인).
    encoded = user.password if user is not None else make_password(None)
    ok = check_password(password, encoded)
    if user is None or not user.is_active:
        # 못 찾았으면 사람 0·넣은 아이디 글자 0 — 회사는 서브도메인(또는 하나뿐인 회사)으로 찾은 값(처분 ⑧)
        reason = "unknown_user" if user is None else "inactive_user"
        note("login_failed", user, now=now, result="failure", reason=reason, audit_company_id=company_id)
        return LoginRejected("invalid_credentials")
    attempt = record_password_attempt(company_id=company_id, user_id=user.pk, ok=ok, now=now)
    if isinstance(attempt, AttemptLocked):
        note("login_locked", user, now=now, result="failure", reason="account_locked")
        return LoginRejected("account_locked")
    if isinstance(attempt, AccountGone) or not ok:
        reason = "inactive_user" if isinstance(attempt, AccountGone) else "wrong_password"
        note("login_failed", user, now=now, result="failure", reason=reason)
        return LoginRejected("invalid_credentials")
    current = selectors.account(company_id, user.pk)
    if current is None:
        note("login_failed", user, now=now, result="failure", reason="inactive_user")
        return LoginRejected("invalid_credentials")
    note("login_succeeded", current, now=now)
    return LoginOk(issue_pair(current, company_is_active=company_is_active_of(current), now=now))


# ── refresh 잇기·로그아웃 ─────────────────────────────────────────────


def _revoke_family(family: UUID, now: datetime) -> None:
    RefreshToken.of_family(family).filter(revoked_at__isnull=True).update(revoked_at=now)


def refresh(token: str, *, now: datetime) -> RefreshOk | RefreshRejected:
    """refresh 를 새 짝으로 바꾼다(rotate). 한 표 블록 안에서 행을 잠그고:
    없음·끊김 → 거절, 이미 씀(재사용) → 그 계보 전부를 끊고 거절(처분 B3), 사용자·회사가 꺼짐 → 계보를 끊고 거절,
    아니면 옛 행에 used_at 을 적고 같은 계보로 새 행을 넣는다. 거절도 블록이 정상으로 닫혀 커밋된다(K-B4)."""
    read = read_refresh(token, secret=app_config().session_secret, now=now)
    if not isinstance(read, RefreshActive):
        return RefreshRejected("expired" if read.reason == "expired" else "unknown")
    claims = read.claims
    user_id = int(claims.user_id)
    with transaction.atomic():
        row = selectors.lock_refresh(claims.jti)
        if row is None or row.user_id != user_id or row.family != claims.family:
            outcome: TokenPair | RefreshRejected = RefreshRejected("unknown")
        elif row.revoked_at is not None:
            outcome = RefreshRejected("revoked")
        elif row.used_at is not None:
            _revoke_family(row.family, now)
            outcome = RefreshRejected("reused")
        else:
            # 회사 조건은 refresh 주장의 company_id 다(K-B3). row.user 를 따라가지 않는다.
            user = selectors.account(claims.company_id, user_id)
            if user is None or not user.is_active or company_is_active_of(user) is False:
                _revoke_family(row.family, now)
                outcome = RefreshRejected("inactive")
            else:
                row.used_at = now
                row.save(update_fields=["used_at"])
                outcome = issue_pair(user, company_is_active=company_is_active_of(user), now=now, family=row.family)
    if isinstance(outcome, RefreshRejected):
        if outcome.reason == "reused":
            log.info("refresh_reused", extra={"event": "refresh_reused", "user_id": user_id})
        return outcome
    return RefreshOk(outcome)


def revoke(token: str, *, now: datetime) -> Revoked | RefreshRejected:
    """로그아웃: 그 refresh 의 계보 전부를 끊는다. 만료된 refresh 도 받는다(로그아웃은 늘 된다).
    이미 끊겼어도 Revoked.
    감사 줄 하나와 로그 한 줄(logout)은 블록이 **닫힌 뒤**다(AU1a 개정 1 N1 — 블록 안이면 감사 쓰기의 DB 오류가 계보
    끊기를 되돌린다). 사람은 refresh 주장의 것이다(행을 읽지 않는다 — 주장에 kind 가 없어 회사 유무로 가른다)."""
    read = read_refresh(token, secret=app_config().session_secret, now=now, allow_expired=True)
    if not isinstance(read, RefreshActive):
        return RefreshRejected("unknown")
    claims = read.claims
    with transaction.atomic():
        _revoke_family(claims.family, now)
    note(
        "logout",
        None,
        now=now,
        audit_actor_kind="admin" if claims.company_id is None else "service",
        audit_actor_user_id=int(claims.user_id),
        audit_company_id=claims.company_id,
    )
    return Revoked()
