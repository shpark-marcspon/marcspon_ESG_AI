"""테스트용 설정 — 보안 층(tests/security). 환경 변수를 채운 뒤 진짜 설정(base.py)을 그대로 읽는다.

Django 의 연결은 **앱 역할**(esg_app)이다(RLS 는 없다 — 격리는 조건과 core/isolation 의 받침).
pytest-django 의 테스트 DB 만들기를 쓰지 않는다
(까닭과 방법은 tests/security/conftest.py). 고르는 법:  pytest --ds=esgapi.config.settings.test_security -m security
DB 는 둘로 갈린다:
  TEST_DATABASE_URL_PY        앱 역할의 주소. 테스트의 요청은 전부 이 역할로 돈다.
  TEST_DATABASE_URL_PY_OWNER  주인 역할의 주소. 테스트 DB 를 만들고 마이그레이션하고 자료를 심는 데만 쓴다.
"""

import os

from tests.support import keys
from tests.support.db import TEST_DB_SUFFIX

_app_url = os.environ.get("TEST_DATABASE_URL_PY", "postgres://esg_app:unused@127.0.0.1:1/unused")
os.environ["DATABASE_URL_PY"] = _app_url + TEST_DB_SUFFIX
keys.fill_env(os.environ)

os.environ.pop("LLM_RUN_MODE", None)  # 셸의 live 를 들이지 않는다 — 실호출 길은 시험의 이음매로만(LH1·LV1 가지 ①)
from esgapi.config.settings.base import *  # noqa: E402, F403

# 정적 서빙은 시험 설정에서 늘 꺼짐: 셸의 WEB_DIST_DIR 이 섞여도 화면 경로는 JSON 404(시험은 override_settings 로 켠다).
WHITENOISE_ROOT = None  # pyright: ignore[reportConstantRedefinition] — base.py 의 값을 덮는 자리
