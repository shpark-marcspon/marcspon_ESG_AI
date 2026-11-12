"""주소표. API 의 경로는 전부 config/api.py 의 api 가 갖고 있고, 여기서는 그것을 /api 아래에 건다.
마지막 자리는 웹의 SPA fallback 이다(config/web.py): 화면 경로의 GET·HEAD 는 index.html, 그 밖은 JSON 404.

/api 아래에 거는 까닭: 같은 출처에서 웹 화면 경로(/greenwash…)와 API 경로(/greenwash…)가 겹친다(sid:MARC-ENT-198).
openapi 의 paths 키에는 접두가 없고 servers 의 "/api" 가 그것을 말한다(config/api.py).
"""

from django.urls import path, re_path

from esgapi.config.api import api, not_found, server_error
from esgapi.config.web import spa_fallback

urlpatterns = [path("api/", api.urls), re_path(r"^(?P<path>.*)$", spa_fallback)]

# 없는 경로의 404 와 ninja 밖에서 난 예외의 500 도 같은 오류 꼴로 낸다(Django 의 기본은 HTML 이다).
handler404 = not_found
handler500 = server_error
