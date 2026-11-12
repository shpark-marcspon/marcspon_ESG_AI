"""세션 쿠키가 경로와 닿는 자리 둘: ninja 의 인증, 쿠키 싣기·지우기.

세션의 꼴·서명·읽기는 core/tenancy/session.py 에, 쿠키를 읽어 테넌트를 싣는 일은 core/tenancy/middleware.py 에 있다.
"""

from typing import Final

from django.http import HttpRequest, HttpResponse
from ninja.security import APIKeyCookie

from esgapi.core.auth.bearer import permitted
from esgapi.core.conf import app_config
from esgapi.core.exceptions import ApplicationError
from esgapi.core.tenancy.context import session_state_of
from esgapi.core.tenancy.middleware import SESSION_COOKIE
from esgapi.core.tenancy.session import Session, SessionAbsent, SessionActive, SessionRejection, sign_session

# ── ninja 의 인증 ─────────────────────────────────────────────────────

SESSION_REJECTIONS: Final[dict[SessionRejection, tuple[str, str]]] = {
    "malformed": ("session_malformed", "세션의 꼴이 아니다. 다시 교환한다"),
    "bad_signature": ("session_bad_signature", "세션의 서명이 맞지 않는다. 다시 교환한다"),
    "expired": ("session_expired", "세션이 만료됐다. 다시 교환한다"),
}


def _no_session() -> ApplicationError:
    return ApplicationError("unauthenticated", "no_session", "세션이 없다. 먼저 /auth/exchange 로 교환한다")


class SessionCookie(APIKeyCookie):
    """세션이 있어야 하는 경로에 건다(auth=session_cookie). 통과하면 경로 함수의 request.auth 가 Session 이다.

    쿠키를 여기서 다시 검증하지 않는다: 미들웨어가 이미 읽어 두었고(서명·만료), 테넌트도 이미 DB 에 실었다.
    여기서는 그 상태가 「살아 있는 세션」인지만 보고, 아니면 갈래에 맞는 401 을 낸다.

    미들웨어만으로 하지 않는 까닭: 어느 경로가 세션을 요구하는지가 경로 선언과 OpenAPI 문서에 드러나게.

    csrf=False: django-ninja 의 쿠키 인증은 기본으로 Django 의 CSRF 검사를 켠다. 이 뼈대는 Django 의
    CSRF(토큰)를 쓰지 않는다. 다른 사이트에서 온 POST 에 쿠키가 실리지 않게 하는 것은 쿠키의 SameSite=Lax 다.
    무효 조건: 같은 사이트(하위 도메인)의 다른 앱이 보내는 요청은 SameSite 가 막지 못한다.
    """

    param_name = SESSION_COOKIE

    def __init__(self) -> None:
        super().__init__(csrf=False)

    def authenticate(self, request: HttpRequest, key: str | None) -> Session:
        state = session_state_of(request)
        if isinstance(state, SessionActive):
            return state.session
        if isinstance(state, SessionAbsent):
            raise _no_session()
        code, message = SESSION_REJECTIONS[state.reason]
        raise ApplicationError("unauthenticated", code, message)


session_cookie = SessionCookie()


def session_of(request: HttpRequest) -> Session:
    """auth=session_cookie 가 걸린 경로에서 세션을 꺼낸다(django-ninja 가 request.auth 에 넣어 둔다)."""
    session: object = getattr(request, "auth", None)
    if not isinstance(session, Session):
        raise _no_session()
    return session


def permitted_session(request: HttpRequest, operation_id: str) -> Session:
    """세션을 꺼내고 그 동작의 권한을 본다(권한 표: core/permissions.py). 쿠키 세션의 주체는 고객사 사용자다.
    그 동작이 고객사 사용자의 일이 아니면 403 forbidden."""
    session = session_of(request)
    permitted(request, operation_id)
    return session


# ── 쿠키 싣기·지우기 ──────────────────────────────────────────────────


def set_session_cookie(response: HttpResponse, session: Session) -> None:
    config = app_config()
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(session, secret=config.session_secret),
        max_age=config.session_ttl_seconds,
        httponly=True,  # 자바스크립트가 읽지 못한다(XSS 로 세션을 빼 가지 못하게)
        # secure: 클라이언트가 HTTPS 로만 되보내라는 표시. 로컬(http)에서 어떻게 되는지는 클라이언트마다 다르다.
        #   잰 것(2026-10-07): curl 8.7.1 은 http://localhost 와 http://127.0.0.1 에 이 쿠키를 싣는다.
        #                      httpx 0.28.1 은 두 주소 모두 싣지 않는다(쿠키는 받아 두지만 /me 가 401).
        #   재지 않은 것: 브라우저. 크롬·파이어폭스는 http://localhost 를 봐주고 사파리는 아니라고 알려져 있다.
        #   무효 조건: 위는 그 버전·그 두 주소에서만 잰 것이다. 다른 버전, 다른 호스트 이름(예: 컨테이너 이름)은 모른다.
        secure=True,
        samesite="Lax",  # 다른 사이트에서 온 POST 에는 싣지 않는다
        path="/",
    )


def clear_session_cookie(response: HttpResponse) -> None:
    # 같은 이름·같은 속성의 빈 쿠키를 「수명 0」으로 보내면 브라우저가 지운다.
    response.set_cookie(SESSION_COOKIE, "", max_age=0, httponly=True, secure=True, samesite="Lax", path="/")
