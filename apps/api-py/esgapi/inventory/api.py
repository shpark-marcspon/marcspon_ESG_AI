"""inventory 의 라우터. 경로 함수는 service/apis/inventory.py 에 있고 여기서는 다시 내보내기만 한다.

config/api.py 가 이 이름(`esgapi.inventory.api.router`)으로 들인다.
"""

from esgapi.inventory.service.apis.inventory import router as router
