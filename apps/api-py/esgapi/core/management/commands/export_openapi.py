"""서버를 띄우지 않고 OpenAPI 문서를 표준 출력으로 낸다:  python manage.py export_openapi

/api/openapi.json 이 내는 것과 같은 내용이다. scripts/gen-ts-types.sh 가 이것으로 프론트의 타입을 만든다.
"""

import json
from importlib import import_module
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from ninja import NinjaAPI


class Command(BaseCommand):
    help = "OpenAPI 문서(JSON)를 표준 출력으로 낸다"

    def handle(self, *args: Any, **options: Any) -> None:
        # NinjaAPI 는 주소표(설정의 ROOT_URLCONF = esgapi.config.urls)의 `api` 다.
        # core 가 config 를 직접 import 하지 않게 설정을 거쳐 찾는다.
        api: object = getattr(import_module(settings.ROOT_URLCONF), "api", None)
        if not isinstance(api, NinjaAPI):
            raise TypeError(f"{settings.ROOT_URLCONF} 에 NinjaAPI 인 `api` 가 없다")
        schema = api.get_openapi_schema(path_prefix="")
        self.stdout.write(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True))
