"""설정 넷(base·migrate·test_business·test_security)이 같은 app 목록을 쓰는가. 순수 층.

목록은 config/apps_list.py 의 상수 하나다. 어느 설정이 목록을 따로 적기 시작하면(예: 마이그레이션용 설정에서
모듈 하나를 빠뜨리면 그 모듈의 표가 만들어지지 않는다) 여기서 걸린다.
설정 모듈은 읽는 순간 환경 변수를 보거나 덮으므로, 하나씩 새 프로세스에서 읽는다.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from esgapi.config.apps_list import INSTALLED_APPS
from tests.support import keys

API_PY_DIR = Path(__file__).resolve().parents[3]
SETTINGS = ["base", "migrate", "test_business", "test_security"]


def env_for_all() -> dict[str, str]:
    env = {
        **os.environ,
        "DATABASE_URL_PY": "postgres://u:p@127.0.0.1:1/x",
        "DATABASE_URL_PY_OWNER": "postgres://o:p@127.0.0.1:1/x",
    }
    keys.fill_env(env)
    return env


@pytest.mark.parametrize("name", SETTINGS)
def test_every_settings_module_uses_the_one_app_list(name: str) -> None:
    code = f"import json, esgapi.config.settings.{name} as s; print(json.dumps(s.INSTALLED_APPS))"
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=API_PY_DIR, env=env_for_all(), capture_output=True, text=True, check=True
    )
    assert json.loads(done.stdout) == INSTALLED_APPS


def test_the_app_list_is_core_and_the_four_modules() -> None:
    assert INSTALLED_APPS[0] == "esgapi.core"
    assert sorted(app.removeprefix("esgapi.") for app in INSTALLED_APPS[1:]) == sorted(
        [
            "django.contrib.contenttypes",
            "django.contrib.auth",
            "organization",
            "user",
            "inventory",
            "reference",
            "reconcile",
            "greenwash",
            "translation",
            "dataverify",
            "materiality",
            "drafting",
            "runs",
            "runbundle",
        ]
    )


@pytest.mark.parametrize("name", [name for name in SETTINGS if name != "migrate"])
def test_the_request_id_middleware_is_first(name: str) -> None:
    """요청을 받는 설정 셋의 미들웨어는 정확히 이 셋, 이 차례다(migrate 는 요청을 받지 않아 MIDDLEWARE 가 없다)."""
    code = f"import json, esgapi.config.settings.{name} as s; print(json.dumps(s.MIDDLEWARE))"
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=API_PY_DIR, env=env_for_all(), capture_output=True, text=True, check=True
    )
    assert json.loads(done.stdout) == [
        "esgapi.core.observability.middleware.RequestIdMiddleware",
        "whitenoise.middleware.WhiteNoiseMiddleware",
        "esgapi.core.tenancy.middleware.TenantMiddleware",
    ]
