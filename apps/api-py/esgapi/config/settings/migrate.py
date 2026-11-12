"""Django 설정(마이그레이션 전용). migrate-py 컨테이너만 쓴다:  DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate

읽는 환경 변수는 DATABASE_URL_PY_OWNER 하나다(주인 역할의 주소). api 프로세스의 설정(base.py)은
이 주소를 모른다 → 요청을 처리하는 프로세스가 테이블을 바꾸거나 RLS 를 끌 길이 없다.
"""

import os

from esgapi.config.apps_list import AUTH_USER_MODEL as AUTH_USER_MODEL
from esgapi.config.apps_list import AUTHENTICATION_BACKENDS as AUTHENTICATION_BACKENDS
from esgapi.config.apps_list import INSTALLED_APPS as INSTALLED_APPS
from esgapi.config.apps_list import SILENCED_SYSTEM_CHECKS as SILENCED_SYSTEM_CHECKS
from esgapi.config.env import ConfigError, parse_database_url

_url = os.environ.get("DATABASE_URL_PY_OWNER", "")
if not _url:
    raise ConfigError("DATABASE_URL_PY_OWNER 가 없다")
_target = parse_database_url(_url, key="DATABASE_URL_PY_OWNER")

# 이 설정으로 뜬 프로세스는 요청을 받지 않는다. EDK 키도 세션 비밀도 모른다(None 은 그 뜻 하나다).
ESG_CONFIG = None

DEBUG = False
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": _target.host,
        "PORT": _target.port,
        "NAME": _target.name,
        "USER": _target.user,
        "PASSWORD": _target.password,
        "OPTIONS": {"connect_timeout": 5},
    }
}
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
