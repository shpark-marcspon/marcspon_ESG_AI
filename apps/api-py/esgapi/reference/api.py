"""reference 의 라우터. 경로 함수는 service/apis/reference.py 에 있고 여기서는 다시 내보내기만 한다.

config/api.py 가 이 이름(`esgapi.reference.api.router`)으로 들인다.
"""

from esgapi.reference.service.apis.reference import router as router
