"""미들웨어가 읽어 둔 세션의 상태를 요청에 붙이고, 경로 쪽에서 꺼낸다."""

from typing import cast

from django.http import HttpRequest

from esgapi.core.tenancy.session import SessionAbsent, SessionState

_ATTR = "esg_session_state"


def set_session_state(request: HttpRequest, state: SessionState) -> None:
    setattr(request, _ATTR, state)


def session_state_of(request: HttpRequest) -> SessionState:
    # 미들웨어를 거치지 않은 요청이면 「세션 없음」이다(믿을 것이 없다).
    return cast(SessionState, getattr(request, _ATTR, SessionAbsent()))
