"""쓰기. 유스케이스 하나: 교환(EDK 토큰 → 우리 세션). HTTP 를 모른다(요청·응답·상태 코드가 없다).

결과는 예외가 아니라 갈래로 돌려준다(utils/exchange.py 의 frozen dataclass).
service/apis/user.py 가 갈래를 응답으로 바꾼다.

유스케이스(exchange)는 바깥(검증·회사 찾기·DB)을 **함수 인자**로 받는다. 진짜 구현은 service/apis/user.py 의
exchange_ports() 가 꽂는다(회사 찾기는 organization 의 selectors 라 도메인을 넘는다 — 그 조립은 apis 에서).
테스트는 가짜 함수를 넘겨 DB 없이 「무엇을 어떤 차례로 시키는가」를 잰다(인터페이스나 DI 컨테이너가 아니다).

★ 교환은 임시 다리다(C1 이 걷는다). 같은 sub 가 다른 회사에 있으면 그 회사의 별개 사용자다(처분 2 ㉡ — 회사를 넘는
  조회를 하지 않는다. 결정 02:56 「회사 안 unique」).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from typing import Final

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import get_password_validators, validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from esgapi.core.auth.principal import Kind
from esgapi.core.conf import app_config
from esgapi.core.tenancy.session import Role, new_session
from esgapi.user.models import User
from esgapi.user.service.permissions.user import Forbidden, can_manage_customer_users
from esgapi.user.service.selectors import user as selectors
from esgapi.user.service.services.login import audit_actor, note
from esgapi.user.service.utils import entities
from esgapi.user.service.utils.exchange import (
    ExchangeOk,
    ExchangeRejected,
    ExchangeResult,
    TenantLookup,
    UserInactive,
    UserLookup,
    UsernameConflict,
    UserSaved,
    admit,
)
from esgapi.user.service.utils.login import PasswordRejected, UserCreated, UsernameTaken, UserNotFound
from esgapi.user.service.utils.tokens import (
    EdkClaims,
    TokenRejected,
    TokenResult,
    load_public_key,
    verify_edk_token,
)

# 주장의 역할 → 표의 level(처분 3, 개정 3 — 사용자 결정 「역할은 관리자·일반 둘」).
# 권한은 이 밴드에서 세션의 role 로만 본다.
LEVEL_OF_ROLE: Final[dict[Role, int]] = {"admin": 99, "editor": 79, "viewer": 79}

# ── 교환 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExchangePorts:
    """교환이 바깥에 시키는 일 셋. 인터페이스(추상 클래스)가 아니라 함수 셋의 묶음이다."""

    verify_token: Callable[[str], TokenResult]
    find_tenant: Callable[[str], TenantLookup]
    upsert_user: Callable[[int, EdkClaims], UserLookup]


def exchange(token: str, *, ports: ExchangePorts, now: datetime, session_ttl_seconds: int) -> ExchangeResult:
    """EDK 토큰 → 우리 세션. 검증 → 회사 조회 → 사용자 upsert → 세션 발급. 꺼진 사용자면 세션을 내지 않는다(D3)."""
    verified = ports.verify_token(token)
    if isinstance(verified, TokenRejected):
        # 서명이 확인되지 않은 토큰 안의 테넌트 ID 로는 DB 를 건드리지 않는다.
        return ExchangeRejected(verified.reason)
    claims = verified.claims

    # 테넌트 ID 는 서명이 확인된 토큰에서만 온다(요청 본문·헤더에서 받지 않는다). 조회마다 그 값을 조건으로 넘긴다.
    admitted = admit(claims, ports.find_tenant(claims.tenant_id))
    if isinstance(admitted, ExchangeRejected):
        return admitted

    saved = ports.upsert_user(admitted.tenant.company_id, admitted.claims)
    if isinstance(saved, UserInactive):
        return ExchangeRejected("user_inactive")
    if isinstance(saved, UsernameConflict):
        return ExchangeRejected("username_conflict")
    user = saved.user
    # 세션의 꼴과 발급은 core 의 것이다(core/tenancy/session.py). 언제 내주는가만 여기서 정한다.
    session = new_session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        company_id=user.company_id,
        role=user.role,
        now=now,
        ttl_seconds=session_ttl_seconds,
    )
    return ExchangeOk(user=user, tenant=admitted.tenant, session=session)


@cache
def edk_public_key() -> RSAPublicKey:
    return load_public_key(app_config().edk_public_key_pem)


def verify_token(token: str) -> TokenResult:
    config = app_config()
    # 키·aud·iss 는 전부 설정에서 온다. 요청이 고를 수 있는 것은 없다.
    return verify_edk_token(token, public_key=edk_public_key(), audience=config.edk_audience, issuer=config.edk_issuer)


def upsert_user(company_id: int, claims: EdkClaims) -> UserLookup:
    """그 회사에서 (kind=service, username=sub) 로 찾아 있으면 이름·level 을 덮어쓰고, 없으면 만든다.
    있는 행이 꺼져 있으면(is_active 거짓) 아무것도 쓰지 않고 UserInactive(D3). 있는 행이 비밀번호 사용자(쓸 수 있는
    비밀번호 — 교환이 만든 행은 늘 쓸 수 없는 값)면 아무것도 쓰지 않고 UsernameConflict(D5 — EDK 토큰이 비밀번호
    사용자의 행을 넘겨받지 못하게). 둘을 가르는 칸은 비밀번호의 쓸 수 있음이다(새 칸·마이그레이션 0).

    조회는 그 회사로 걸러진다(User.for_company) — 다른 회사의 같은 username 은 보지 않고 건드리지 않는다(처분 2 ㉡).
    새 행의 비밀번호는 쓸 수 없는 값이다(로그인은 K2). 같은 회사·같은 sub 의 교환이 겹치면 둘째의 INSERT 가 조건부
    UNIQUE(users_company_username_uniq)에 걸리고, update_or_create 가 그 블록을 되돌린 뒤 다시 찾아 덮어쓴다.
    무효 조건: 토큰의 테넌트가 틀리면 그 틀린 회사에서 찾고 만든다(서명이 확인된 토큰에서만 온다).
    """
    level = LEVEL_OF_ROLE[claims.role]
    # 이 블록이 트랜잭션이다(바깥 안에서 불리면 세이브포인트). 한 표라 service 안의 블록 하나다.
    with transaction.atomic():
        existing = selectors.find_customer(company_id, claims.external_id)
        if existing is not None and existing.has_usable_password():
            return UsernameConflict()
        if existing is not None and not existing.is_active:
            return UserInactive()
        row, _created = User.for_company(company_id).update_or_create(
            kind="service",
            username=claims.external_id,
            defaults={"name": claims.name, "level": level},
            create_defaults={
                "company_id": company_id,
                "name": claims.name,
                "level": level,
                "password": make_password(None),
            },
        )
    return UserSaved(
        entities.User(
            id=str(row.pk),
            company_id=company_id,
            tenant_id=claims.tenant_id,
            issuer=claims.issuer,
            external_id=row.username,
            name=row.name,
            role=claims.role,
        )
    )


# ── 계정 만들기·비밀번호 검사(K2a — 부트스트랩 명령이 부르고, K2c 의 HTTP 가 같은 것을 부른다) ─────────
# 거절은 값으로 돌려준다(UsernameTaken·PasswordRejected·Forbidden). 해시(PBKDF2 1,000,000 회)는 블록 밖에서 한다.
# 고객사 사용자를 만드는 service 는 첫 줄에서 권한을 묻는다(actor_kind — K2c, user/service/permissions). 명령은
# actor_kind="admin"(셸을 쥔 사람 = 운영 관리자), HTTP 는 토큰의 kind 를 넘긴다.

PASSWORD_MAX_LENGTH: Final = 1024  # 검사기 앞의 상한(긴 입력으로 해시를 오래 돌리지 않게)


def password_problems(password: str) -> PasswordRejected | None:
    """비밀번호 규칙은 8자 이상 하나다(사용자 결정 MARC-ENT-282 — 흔함·숫자만·이름과 비슷함 검사기는 끈다). Django 의
    검사기(최소 길이)를 명시해 부른다(설정 AUTH_PASSWORD_VALIDATORS 는 0줄 — 질문 7 의 권장안). 앞에 1,024자 상한.
    거절이면 검사기의 사람용 문장(비밀번호 글자는 싣지 않는다)."""
    if len(password) > PASSWORD_MAX_LENGTH:
        return PasswordRejected((f"비밀번호는 {PASSWORD_MAX_LENGTH}자 이하여야 한다",))
    validators = get_password_validators(PASSWORD_VALIDATORS)
    try:
        # 최소 길이 검사기는 사용자 속성을 보지 않는다 — 행을 만들기 전에도 검사할 수 있다.
        validate_password(password, None, password_validators=validators)
    except ValidationError as error:
        return PasswordRejected(tuple(str(message) for message in error.messages))
    return None


# 8자 이상 하나(MARC-ENT-282).
PASSWORD_VALIDATORS: Final = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]


def create_customer_user(
    *,
    actor_kind: Kind,
    company_id: int,
    username: str,
    name: str,
    password: str,
    actor_user_id: int | None = None,
) -> UserCreated | UsernameTaken | PasswordRejected | Forbidden:
    """그 회사의 고객사 사용자(kind service·level 79·is_initial)를 만든다. 운영 관리자만(첫 줄 — 막히면 아무것도 안
    읽고 안 쓴다). 같은 회사의 같은 username 이면 UsernameTaken. actor_user_id 는 기록 줄에만 싣는다(HTTP 몫).
    ★ 겹침 막기(UA1 — MARC-ENT-283): 같은 username 의 운영 관리자가 있어도 UsernameTaken 이다(서브도메인 없는 로그인은
      운영 관리자를 먼저 찾는다). 운영 관리자 만들기(명령 create_user --admin)는 회사를 넘는 조회가 필요해 막지 않는다 —
      명령으로 겹치게 만들면 그 고객사 사용자는 서브도메인 없는 로그인에서 가려진다."""
    if not can_manage_customer_users(actor_kind):
        return Forbidden("user_create")
    rejected = password_problems(password)
    if rejected is not None:
        return rejected
    if selectors.find_admin(username) is not None:
        return UsernameTaken()
    password_hash = make_password(password)
    try:
        with transaction.atomic():
            row = User.for_company(company_id).create(
                company_id=company_id,
                kind="service",
                username=username,
                name=name,
                level=79,
                is_initial=True,
                password=password_hash,
            )
    except IntegrityError:
        return UsernameTaken()
    # 감사의 때는 행이 생긴 때(date_joined — 새 시계 0). 행위자: HTTP 는 그 운영 관리자, 명령은 command(개정 1 B3)
    kind, who = audit_actor(actor_kind, actor_user_id)
    note(
        "user_created",
        row,
        now=row.date_joined,
        actor_user_id=actor_user_id,
        audit_actor_kind=kind,
        audit_actor_user_id=who,
    )
    return UserCreated(row.pk)


def create_operator(*, username: str, name: str, password: str) -> UserCreated | UsernameTaken | PasswordRejected:
    """운영 관리자(kind admin·회사 없음·level 99·is_initial)를 만든다. 부르는 자리는 create_user 명령 하나(HTTP 0)."""
    rejected = password_problems(password)
    if rejected is not None:
        return rejected
    password_hash = make_password(password)
    try:
        with transaction.atomic():
            row = User.register_admin(username=username, name=name, password=password_hash)
    except IntegrityError:
        return UsernameTaken()
    # 부르는 자리는 명령 하나 — 감사 행위자는 늘 command(개정 1 B3)
    note("user_created", row, now=row.date_joined, audit_actor_kind="command", audit_actor_user_id=None)
    return UserCreated(row.pk)


@dataclass(frozen=True)
class ResetPrepared:
    """초기화할 대상과 새 해시(검사기·해시는 action 앞에서 — 행 잠금 안에서 해시를 돌지 않는다)."""

    company_id: int | None
    user_id: int
    password_hash: str


def prepare_reset(
    *, company_id: int | None, username: str, password: str
) -> ResetPrepared | UserNotFound | PasswordRejected:
    """초기화 앞: 대상을 한 번 읽고(잠금 없음) 새 비밀번호를 검사하고 해시한다."""
    user = selectors.find_admin(username) if company_id is None else selectors.find_customer(company_id, username)
    if user is None or not user.has_usable_password():  # 교환이 만든 행(EDK 사용자)은 초기화하지 않는다(D5)
        return UserNotFound()
    rejected = password_problems(password)
    if rejected is not None:
        return rejected
    return ResetPrepared(company_id, user.pk, make_password(password))


def prepare_customer_reset(
    *, company_id: int, user_id: int, password: str
) -> ResetPrepared | UserNotFound | PasswordRejected:
    """HTTP 초기화 앞(K2c): 그 회사의 고객사 사용자를 id 로 한 번 읽고(잠금 없음 — User.for_company 의 kind service,
    회사를 넘는 조회 0) 새 비밀번호를 검사하고 해시한다. 남의 회사의 id·운영 관리자의 id·교환이 만든 행
    (비밀번호를 쓸 수 없음 — EDK 사용자, D5)이면 UserNotFound."""
    user = selectors.account(company_id, user_id)
    if user is None or not user.has_usable_password():
        return UserNotFound()
    rejected = password_problems(password)
    if rejected is not None:
        return rejected
    return ResetPrepared(company_id, user.pk, make_password(password))
