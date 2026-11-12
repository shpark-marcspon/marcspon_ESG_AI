from django.apps import AppConfig
from django.conf import settings


class UserConfig(AppConfig):
    name = "esgapi.user"
    label = "user"

    def ready(self) -> None:
        # 마이그레이션 전용 설정으로 뜬 프로세스는 요청을 받지 않고 EDK 키도 모른다(config/settings/migrate.py).
        if settings.ESG_CONFIG is None:
            return
        # 서버가 뜰 때 EDK 공개키를 한 번 읽어 본다. PEM 이 틀렸으면 첫 요청이 아니라 여기서 멈춘다.
        from esgapi.user.service.services.user import edk_public_key

        edk_public_key()
