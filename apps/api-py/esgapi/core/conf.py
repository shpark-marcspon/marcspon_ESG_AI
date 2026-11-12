"""Django 설정에 실린 우리 설정(Config)을 꺼낸다. 값은 환경 변수에서 온 것이다(config/env.py)."""

from datetime import UTC, datetime

from django.conf import settings

from esgapi.config.env import Config


class NoAppConfigError(Exception):
    pass


def app_config() -> Config:
    config: object = settings.ESG_CONFIG
    if not isinstance(config, Config):
        # 마이그레이션 전용 설정(config/settings/migrate.py)에는 이 값이 없다(None).
        raise NoAppConfigError("이 프로세스의 설정에는 ESG_CONFIG 가 없다(요청을 받는 프로세스가 아니다)")
    return config


def now() -> datetime:
    return datetime.now(UTC)
