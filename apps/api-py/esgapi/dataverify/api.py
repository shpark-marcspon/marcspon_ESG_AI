"""dataverify 의 라우터. 경로 함수는 service/apis/dataverify.py 에 있고 여기서는 다시 내보내기만 한다.

config/api.py 가 이 이름(`esgapi.dataverify.api.router`)으로 들여 /dataverify 아래에 **Bearer 인증(머리가 없으면 옛
교환 쿠키, K2b)을 꽂아** 건다(/greenwash·/translation 과 같음). 둘째 라우터 `ai_settings_router`(service/apis/
ai_settings.py — DVA1)는 /ai-settings/dataverify 아래에 운영 관리자의 Bearer(access_token_auth)로 건다.
"""

from esgapi.dataverify.service.apis.ai_settings import router as ai_settings_router
from esgapi.dataverify.service.apis.dataverify import router as router

__all__ = ["ai_settings_router", "router"]
