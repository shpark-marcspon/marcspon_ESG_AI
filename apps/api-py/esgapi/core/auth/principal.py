"""주체: 이 요청을 누가 하는가. 순수하다(표준 라이브러리와 core/tenancy/session 만 — 계약 다).

역할 둘(사용자 결정 2026-10-15 14:46, RPT-21 rev 2): 운영 관리자(kind admin, 회사 없음) · 고객사 사용자(kind service,
회사 하나). 원문:16-18 의 user_kind 다. 권한 표(core/permissions.py)는 이 kind 로만 가른다(level 은 권한에 0).

두 길에서 온다:
  Bearer   우리가 서명한 access 토큰(core/auth/tokens.py, 경로 쪽 인증은 core/auth/bearer.py)
  session  옛 쿠키 세션(교환 다리 — C1 이 걷는다). 쿠키 세션의 사용자는 늘 고객사 사용자다(교환 다리가 kind=service 로
           만든다). 세션의 역할(admin·editor·viewer)은 주체로 옮기지 않는다 — 1차 권한에 쓰이지 않는다(a-0-1 가2).
"""

from dataclasses import dataclass
from typing import Literal

from esgapi.core.tenancy.session import Session

Kind = Literal["admin", "service"]  # 운영 관리자 / 고객사 사용자 (원문:16-18)


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str  # 쿠키: Session.user_id / Bearer: sub (둘 다 users.pk 의 십진 글자)
    company_id: int | None  # service 는 늘 int, admin 은 늘 None (토큰 읽기가 짝을 검사한다)
    kind: Kind
    is_initial: bool  # 쿠키 길은 늘 False (교환 다리의 사용자는 비밀번호가 없다 — a-0-3)
    via: Literal["bearer", "session"]


def principal_of_session(session: Session) -> Principal:
    """쿠키 세션의 주체. 역할과 무관하게 고객사 사용자다."""
    return Principal(
        user_id=session.user_id, company_id=session.company_id, kind="service", is_initial=False, via="session"
    )
