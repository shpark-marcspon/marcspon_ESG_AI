"""모델과 마이그레이션이 어긋나지 않는가. 업무 층(makemigrations 가 DB 의 적용 기록을 읽는다).

모든 모듈을 한 번에 본다. 모델을 고치고 makemigrations 를 잊으면 여기서 걸린다.
"""

from io import StringIO

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_models_and_migrations_agree() -> None:
    out = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
    except SystemExit as stop:  # --check 는 만들 것이 있으면 종료 코드 1 로 끝낸다
        raise AssertionError(f"만들지 않은 마이그레이션이 있다:\n{out.getvalue()}") from stop
