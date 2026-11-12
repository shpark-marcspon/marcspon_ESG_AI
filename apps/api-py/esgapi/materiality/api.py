"""materiality 의 라우터. 경로 함수는 service/apis/materiality.py 에 있고 여기서는 다시 내보내기만 한다.

config/api.py 가 이 이름(`esgapi.materiality.api.router`)으로 들여 /materiality 아래에 **Bearer 인증(머리가 없으면 옛
교환 쿠키, K2b)을 꽂아** 건다(/greenwash·/translation·/dataverify 와 같음). ai_settings_router 는
/ai-settings/materiality 에 운영 관리자 Bearer(라우터의 auth — IR4, dataverify 와 같은 꼴).
"""

from esgapi.materiality.service.apis.ai_settings import router as ai_settings_router
from esgapi.materiality.service.apis.materiality import router as router

__all__ = ["ai_settings_router", "router"]
