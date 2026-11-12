"""테넌트 미들웨어. 세션을 읽어 요청에 붙인다. 트랜잭션을 열지 않는다.

    요청 ─▶ [이 미들웨어] 쿠키 → 세션 읽기(서명·만료) → 요청에 붙임(context.py)
                │    ─▶ django-ninja 의 경로 함수 ─▶ selector·service(세션의 테넌트를 인자로 받아 조건에 적는다)
            ◀─ 응답(그대로 돌려준다)

★ 테넌트는 세션에서 읽어 요청에 붙일 뿐, DB 에 싣지 않는다. 조회의 조건은 selector 가 인자로 받는다
  (회사 범위 표는 for_company(…) 로만 열린다 — core/isolation). 세션이 없으면 인증 경로가 401 로 끊는다.

★ 요청마다의 트랜잭션은 없다(EDK 리뉴얼 꼴): 한 표의 쓰기는 service 가 자기 블록(`with transaction.atomic():`)
  에서 끝내고, 여러 표는 actions 의 `@transaction.atomic` 함수 하나로, 큐 넣기·메일·바깥 API 는 `on_commit` 이나
  트랜잭션 밖에서 한다. 그래서 요청이 오류로 답해도 그 앞에서 커밋된 쓰기는 남는다 — 거절은 쓰기 앞에서 한다.
  이 미들웨어는 DB 에 닿지 않는다. DB 오류는 경로 안에서 나고 config/api.py 의 처리기가 답한다.
★ ATOMIC_REQUESTS 도 쓰지 않는다(사용자 결정 2026-10-15, EDK 원문:170).
"""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from esgapi.core.conf import app_config, now
from esgapi.core.tenancy.context import set_session_state
from esgapi.core.tenancy.session import read_session

SESSION_COOKIE = "esg_session"


class TenantMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # 테넌트는 여기서만 온다: 우리가 서명한 쿠키. 본문·쿼리·헤더(X-Tenant-Id 류)에서는 읽지 않는다.
        state = read_session(request.COOKIES.get(SESSION_COOKIE), secret=app_config().session_secret, now=now())
        set_session_state(request, state)
        return self.get_response(request)
