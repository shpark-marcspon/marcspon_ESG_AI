"""회사 하나를 등록한다(시드). 주인 역할 설정에서 돈다 — 앱 역할에는 company 의 INSERT 가 없다.

    DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate \
      python manage.py seed_company --name <이름> --business-licence-number <사업자번호> --subdomain <서브도메인>

없으면 만들고(쓸 수 있는 회사로) id 를 찍는다. 같은 서브도메인이 같은 값으로 이미 있으면 그대로 두고 id 를
찍는다(종료 0 — 두 번 돌려도 그대로). 같은 서브도메인이 다른 값으로 있거나,
사업자번호·서브도메인이 다른 회사와 겹치면 종료 1.
만드는 길은 Company.register 하나다(이 파일이 그것을 부르는 유일한 자리).

회사를 만든 뒤(「같은 값으로 이미 있음」 갈래도) 본사가 없으면 하나 세운다(services 의 ensure_headquarters — K1b-1,
두 번 돌려도 하나). ★ 회사 만들기와 본사 세우기는 **자동 커밋 둘**이다: 사이에서 실패하면 본사 없는 회사가 남고,
명령을 같은 값으로 다시 돌리면 메운다(「같은 값」 갈래도 본사를 본다).
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import IntegrityError

from esgapi.organization.models import Company
from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.services.branches import ensure_headquarters
from esgapi.organization.service.utils.entities import CompanyActive, CompanyUnknown


class Command(BaseCommand):
    help = "회사 하나를 등록한다(같은 값이면 두 번 돌려도 그대로)"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--name", required=True)
        parser.add_argument("--business-licence-number", required=True)
        parser.add_argument("--subdomain", required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        name: str = options["name"]
        licence: str = options["business_licence_number"]
        subdomain: str = options["subdomain"]
        found = find_company(subdomain)
        if isinstance(found, CompanyActive) and (found.company.name, found.company.business_licence_number) == (
            name,
            licence,
        ):
            ensure_headquarters(found.company.id)
            self.stdout.write(str(found.company.id))
            return
        if not isinstance(found, CompanyUnknown):
            raise CommandError(f"서브도메인 {subdomain} 의 회사가 다른 값으로 이미 있다(id {found.company.id})")
        try:
            # 한 행 INSERT 하나라 블록을 열지 않는다(명령은 자동 커밋으로 돈다). 겹치면 그 문만 실패한다.
            company = Company.register(name=name, business_licence_number=licence, subdomain=subdomain)
        except IntegrityError as err:
            raise CommandError(f"다른 회사와 겹친다: {err}") from err
        ensure_headquarters(company.pk)
        self.stdout.write(str(company.pk))
