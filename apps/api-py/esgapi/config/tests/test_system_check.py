"""Django 의 system check 가 경고 하나 없이 깨끗한가. 순수 층: DB 에 닿지 않는다.

`manage.py check --fail-level WARNING` 을 게이트에 넣는 자리다(`check` 는 --database 를 주지 않으면 DB 에 닿지 않는다).
보는 설정은 넷이다: base·migrate·test_business·test_security.
`--deploy` 는 보지 않는다: 그 검사의 경고는 이 서버가 일부러 켜지 않은 것(SecurityMiddleware 류, SECRET_KEY)을 켜야
사라진다. 켤지는 인프라의 결정이다.

설정 모듈은 읽는 순간 환경 변수를 보므로, 설정마다 새 프로세스에서 돌린다. 이 프로세스(test_business)에서는
오류 하나·경고 하나를 심어 「이 검사가 정말 빨개지는가」를 잰다.
"""

import io
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from django.conf import settings
from django.core import checks
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.http import HttpRequest, HttpResponse
from django.test import override_settings
from django.urls import path

from tests.support import keys

API_PY_DIR = Path(__file__).resolve().parents[3]
SETTINGS = ["base", "migrate", "test_business", "test_security"]
# 끈 검사는 auth.W004 하나다(username 이 회사 안에서만 unique — 결정 6, config/apps_list.py).
CLEAN = "System check identified no issues (1 silenced)."


def env_for(name: str) -> dict[str, str]:
    """설정 넷이 다 읽히는 환경(DB 주소는 닿지 않는 자리다. check 는 연결을 열지 않는다)."""
    env = {
        **os.environ,
        "DATABASE_URL_PY": "postgres://u:p@127.0.0.1:1/x",
        "DATABASE_URL_PY_OWNER": "postgres://o:p@127.0.0.1:1/x",
        "DJANGO_SETTINGS_MODULE": f"esgapi.config.settings.{name}",
    }
    keys.fill_env(env)
    return env


def check(**options: str) -> str:
    out = io.StringIO()
    call_command("check", stdout=out, stderr=out, **options)
    return out.getvalue()


def a_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse()


def test_the_system_check_is_clean() -> None:
    assert CLEAN in check(fail_level="WARNING")
    assert settings.SILENCED_SYSTEM_CHECKS == ["auth.W004"]
    with override_settings(SILENCED_SYSTEM_CHECKS=[]):  # 끄지 않으면 경고가 정확히 그 하나다
        assert sorted(message.id for message in checks.run_checks()) == ["auth.W004"]


def test_an_error_turns_it_red() -> None:
    """번역 검사만 돈다(--tag translation) — 모든 검사를 돌리면 auth 검사가 모델 이름을 gettext 로 지으며 잘못된 언어의
    번역을 찾다 OSError 가 나고, 그 이름이 앞 시험에서 캐시된 일꾼에서만 초록이었다(GE1b — xdist 일꾼 나눔 흔들림,
    밴드 탓 아님)."""
    with override_settings(LANGUAGE_CODE="not a code"), pytest.raises(SystemCheckError, match=r"translation\.E001"):
        call_command("check", "--tag", "translation", fail_level="WARNING", stdout=io.StringIO(), stderr=io.StringIO())


def test_a_warning_turns_it_red_only_because_of_the_fail_level() -> None:
    """경고(오류가 아닌 것)는 fail_level 을 WARNING 으로 줄 때만 실패다. 그 인자를 지우는 실수를 여기서 잡는다."""
    conf = types.ModuleType("go1_urlconf_with_a_warning")
    conf.__dict__["urlpatterns"] = [path("/starts-with-slash", a_view)]
    with override_settings(ROOT_URLCONF=conf):
        with pytest.raises(SystemCheckError, match=r"urls\.W002"):
            check(fail_level="WARNING")
        assert "urls.W002" in check()  # 기본 수준(ERROR)에서는 경고를 찍기만 하고 던지지 않는다


@pytest.mark.parametrize("name", SETTINGS)
def test_every_settings_module_passes_the_check(name: str) -> None:
    done = subprocess.run(
        [sys.executable, "-W", "error", "manage.py", "check", "--fail-level", "WARNING"],
        cwd=API_PY_DIR,
        env=env_for(name),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert CLEAN in done.stdout
