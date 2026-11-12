"""Django 설정(api 프로세스용). 값은 전부 환경 변수에서 온다(esgapi/config/env.py).

Django 의 것 가운데 켠 것은 ORM·마이그레이션·URL·미들웨어 틀,
그리고 사용자 표가 기대는 contrib 둘(contenttypes·auth)이다.
admin, 세션, AuthenticationMiddleware, Django 의 정적 파일 앱(staticfiles·collectstatic)은 켜지 않았다(로그인은 K2).
웹 빌드의 정적 서빙은 whitenoise 미들웨어가 WEB_DIST_DIR 을 URL 뿌리에서 낸다(아래 WHITENOISE_*, config/web.py).
"""

import os

from esgapi.config.apps_list import AUTH_USER_MODEL as AUTH_USER_MODEL
from esgapi.config.apps_list import AUTHENTICATION_BACKENDS as AUTHENTICATION_BACKENDS
from esgapi.config.apps_list import INSTALLED_APPS as INSTALLED_APPS
from esgapi.config.apps_list import SILENCED_SYSTEM_CHECKS as SILENCED_SYSTEM_CHECKS
from esgapi.config.env import Config, ConfigError, DbTarget, load_config
from esgapi.config.web import IMMUTABLE_FILE_TEST, WebOn, WebRefused, add_headers, read_web_dist
from esgapi.core.observability.jsonlog import logging_config

# 마이그레이션용 설정(migrate.py)에서는 이 값이 None 이다. 요청을 받는 프로세스에서는 늘 Config 다.
ESG_CONFIG: Config = load_config(os.environ)

DEBUG = False  # 켜는 길이 없다. 오류의 속사정(스택)은 기록에만 남긴다.

# Host 헤더 검사는 하지 않는다: 로드밸런서(ALB)의 상태 확인은 IP 로 온다. 받을 호스트는 ALB 의 규칙이 거른다.
# 무효 조건: 이 컨테이너가 ALB 없이 바깥에 바로 열리면 이 줄은 틀렸다.
ALLOWED_HOSTS = ["*"]

# SECRET_KEY 를 두지 않는다: Django 의 서명 기능(세션·CSRF·signing)을 쓰지 않는다.
# 누가 그것을 쓰려 들면 Django 가 「SECRET_KEY 가 비었다」로 막는다. 우리 세션의 비밀은 SESSION_SECRET 이다.

# request ID 가 먼저(바깥)다: 커밋 뒤 갈고리의 기록과 접근 줄에도 id 가 실려야 한다(정적 파일의 요청도 한 줄씩).
# whitenoise 는 늘 건다(꺼짐은 WHITENOISE_ROOT = None). 테넌트 앞이라 정적 파일은 세션을 읽지 않는다.
MIDDLEWARE = [
    "esgapi.core.observability.middleware.RequestIdMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "esgapi.core.tenancy.middleware.TenantMiddleware",
]

# ── 웹 빌드의 정적 서빙(sid:MARC-ENT-198) ──
# WEB_DIST_DIR: 웹 빌드(apps/web/dist)의 절대 경로. 이미지는 /app/web. 비면 꺼짐(시험 설정·호스트 개발 — 화면 경로도
# JSON 404). 상대 경로이거나 index.html 이 없으면 기동을 거부한다. config/env.py 는 순수 모듈이라 여기서 읽는다.
_web = read_web_dist(os.environ.get("WEB_DIST_DIR"))
if isinstance(_web, WebRefused):
    raise ConfigError(_web.reason)
WHITENOISE_ROOT: str | None = str(_web.root) if isinstance(_web, WebOn) else None
# whitenoise 의 기본은 모든 파일에 Access-Control-Allow-Origin: * 다. 같은 출처라 필요 없다.
WHITENOISE_ALLOW_ALL_ORIGINS = False
WHITENOISE_IMMUTABLE_FILE_TEST = IMMUTABLE_FILE_TEST
WHITENOISE_ADD_HEADERS_FUNCTION = add_headers
# WHITENOISE_INDEX_FILE 은 켜지 않는다: 켜면 /index.html → / 돌려보내기와 max-age 60 이 붙는다. / 는 fallback 이 낸다.
ROOT_URLCONF = "esgapi.config.urls"

# 템플릿은 /api/docs(문서 화면) 한 장을 그리는 데만 쓰인다(django-ninja 가 쓴다). 우리 템플릿은 없다.
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates"}]

# 요청 본문의 상한(바이트). Django 의 기본값 그대로를 우리 설정으로 적어 둔다(값을 바꾸지 않았다. 고른 값이 아니다).
# 출처: 설치된 django 5.2.18 의 django/conf/global_settings.py:315
# 「DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440  # i.e. 2.5 MB」(확인 2026-10-13).
# 넘으면 config/api.py 가 413 body_too_large 로 답한다.
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440


def database_settings(target: DbTarget) -> dict[str, object]:
    return {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": target.host,
        "PORT": target.port,
        "NAME": target.name,
        "USER": target.user,
        "PASSWORD": target.password,
        # 연결을 요청 사이에 다시 쓴다(60초). 연결에 테넌트를 싣지 않는다(조회마다 조건으로 거른다 — core/isolation).
        # ★ 연결에 상태를 남기는 SET 을 더하면 이 연결을 다음에 쓰는 다른 요청으로 샌다.
        "CONN_MAX_AGE": 60,
        # 다시 쓰기 전에 연결이 살아 있는지 본다(DB 가 재시작했으면 새로 맺는다).
        "CONN_HEALTH_CHECKS": True,
        # 요청마다의 트랜잭션은 없다. 쓰기는 service 의 블록(core/tenancy/middleware.py 의 머리 글).
        "ATOMIC_REQUESTS": False,
        "OPTIONS": {"connect_timeout": 2},
    }


DATABASES = {"default": database_settings(ESG_CONFIG.database)}

USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 기록은 표준 출력으로. 컨테이너 플랫폼이 모아 간다. 한 줄 JSON 이고, 칸은 jsonlog.FIELDS 의 닫힌 목록이다.
LOGGING = logging_config()
