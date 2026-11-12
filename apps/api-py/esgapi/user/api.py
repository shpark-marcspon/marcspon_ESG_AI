"""user 의 라우터. 경로 함수는 service/apis/user.py(교환·/me)와 service/apis/login.py(로그인·토큰·자기 계정 — K2a)에
있고 여기서는 다시 내보내기만 한다. 감사 기록 조회(AU1a — AD-05)는 service/apis/audit.py,
운영 관리자 실행 기록(AU1b-2 — AD-04)은 service/apis/run_logs.py.

config/api.py 가 이 이름(`esgapi.user.api.router`)으로 들인다.
"""

from esgapi.user.service.apis.audit import router as audit_router
from esgapi.user.service.apis.login import router as login_router
from esgapi.user.service.apis.run_logs import router as run_logs_router
from esgapi.user.service.apis.user import router as router

router.add_router("", login_router)
router.add_router("", audit_router)
router.add_router("", run_logs_router)
