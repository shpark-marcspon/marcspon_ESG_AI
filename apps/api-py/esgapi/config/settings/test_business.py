"""테스트용 설정 — 순수 층과 업무 층(esgapi/*/tests). 환경 변수를 채운 뒤 진짜 설정(base.py)을 그대로 읽는다.

Django 의 연결은 **주인 역할**이다(TEST_DATABASE_URL_PY_OWNER). pytest-django 가 그 연결로 테스트 DB 를 만들고
(이름 앞에 test_ 를 붙인다. pytest-xdist 로 돌리면 워커마다 뒤에 _gw0, _gw1 … 을 더 붙인다) 마이그레이션하고,
@pytest.mark.django_db 테스트를 트랜잭션으로 감싸 끝나면 되돌린다.

★ 로컬 compose 의 주인 역할은 superuser 다. 테넌트를 명시해 심고(<Row>.unscoped), 앱 역할로 붙어 재는
  테넌트 경계·역할·연결 상태는 보안 층(tests/security)이 잰다.
주소가 없으면 닿지 않는 주소가 들어간다. 순수 테스트(django_db 표시 없음)는 그래도 돈다.
"""

import os

from tests.support import keys

os.environ["DATABASE_URL_PY"] = os.environ.get(
    "TEST_DATABASE_URL_PY_OWNER", "postgres://unused:unused@127.0.0.1:1/unused"
)
keys.fill_env(os.environ)

os.environ.pop("LLM_RUN_MODE", None)  # 셸의 live 를 들이지 않는다 — 실호출 길은 시험의 이음매로만(LH1·LV1 가지 ①)
from esgapi.config.settings.base import *  # noqa: E402, F403

# 정적 서빙은 시험 설정에서 늘 꺼짐: 셸의 WEB_DIST_DIR 이 섞여도 화면 경로는 JSON 404(시험은 override_settings 로 켠다).
WHITENOISE_ROOT = None  # pyright: ignore[reportConstantRedefinition] — base.py 의 값을 덮는 자리
