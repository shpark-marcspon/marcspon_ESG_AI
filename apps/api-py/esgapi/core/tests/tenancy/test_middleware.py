"""테넌트 미들웨어(esgapi/core/tenancy/middleware.py)를 DB 없이 잰다. 순수 층.

★ 미들웨어는 세션을 읽어 요청에 붙이고 응답을 그대로 돌려준다. 트랜잭션을 열지 않고 DB 에 닿지 않는다.
  순수 층은 pytest-django 가 DB 접근을 막으므로, 미들웨어가 연결을 맺으려 들면(atomic() 진입 포함) 여기서 빨갛다.
무효 조건: 경로 함수는 지어낸 것이다(django-ninja 를 거치지 않는다). 경로 안의 트랜잭션 상태는 보안 층이 잰다.
"""

from datetime import timedelta

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from esgapi.core.conf import app_config, now
from esgapi.core.tenancy.context import session_state_of
from esgapi.core.tenancy.middleware import SESSION_COOKIE, TenantMiddleware
from esgapi.core.tenancy.session import Session, SessionAbsent, SessionActive, SessionState, sign_session

SESSION = Session(
    user_id="user-1", tenant_id="tenant-a", company_id=1, role="editor", expires_at=now() + timedelta(hours=1)
)


def signed_request() -> HttpRequest:
    request = RequestFactory().post("/sites")
    request.COOKIES[SESSION_COOKIE] = sign_session(SESSION, secret=app_config().session_secret)
    return request


def test_the_middleware_reaches_no_database() -> None:
    calls: list[str] = []
    answer = HttpResponse(status=201)

    def get_response(request: HttpRequest) -> HttpResponse:
        calls.append(request.path)
        return answer

    middleware = TenantMiddleware(get_response)
    assert middleware(RequestFactory().get("/me")) is answer  # 세션 없음
    assert middleware(signed_request()) is answer  # 서명된 세션
    assert calls == ["/me", "/sites"]


def test_an_error_response_is_passed_through() -> None:
    for status in (409, 500):
        answer = HttpResponse(status=status)
        # 감싸거나 503 으로 바꾸지 않는다: 같은 객체가 나온다.
        assert TenantMiddleware(lambda request, answer=answer: answer)(signed_request()) is answer


def test_the_session_is_attached_before_the_route_runs() -> None:
    seen: list[SessionState] = []

    def get_response(request: HttpRequest) -> HttpResponse:
        seen.append(session_state_of(request))
        return HttpResponse(status=200)

    TenantMiddleware(get_response)(signed_request())
    TenantMiddleware(get_response)(RequestFactory().get("/me"))
    assert len(seen) == 2
    active, absent = seen
    assert isinstance(active, SessionActive)
    assert (active.session.tenant_id, active.session.role, active.session.user_id) == ("tenant-a", "editor", "user-1")
    assert isinstance(absent, SessionAbsent)
