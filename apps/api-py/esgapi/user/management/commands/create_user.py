"""계정 하나를 만든다(부트스트랩 — K2a). 첫 운영 관리자와 개발·시드용 고객사 사용자의 길이다.

    python manage.py create_user --admin --username <아이디> --name <이름> [--password-stdin]
    python manage.py create_user --company <서브도메인> --username <아이디> --name <이름> [--password-stdin]

운영 관리자(--admin)는 kind admin·회사 없음·level 99, 고객사 사용자(--company)는 그 회사의 kind service·level 79.
둘 다 is_initial — 첫 로그인 때 비밀번호를 바꿔야 한다. 이미 있으면 덮지 않는다(종료 1).
비밀번호는 명령줄 인자로 받지 않는다(ps·셸 기록에 남는다): --password-stdin 이면 표준 입력 한 줄, 아니면 tty 에서
두 번 묻는다(getpass). 찍는 것은 id·kind·서브도메인뿐이다.
이 파일은 표를 직접 쓰지 않는다 — 만들기는 user/service/services/user.py 의 create_operator(부르는 자리는 이 파일
하나 — HTTP 0)·create_customer_user(K2c 의 POST /users 가 같은 것). 회사 찾기는 교환과 같은 find_company.
"""

import sys
from getpass import getpass
from typing import Any, TextIO

from django.core.management.base import BaseCommand, CommandError, CommandParser

from esgapi.organization.service.selectors.organization import find_company
from esgapi.organization.service.utils.entities import CompanyUnknown
from esgapi.user.service.permissions.user import Forbidden
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import PasswordRejected, UsernameTaken


def add_target_arguments(parser: CommandParser) -> None:
    """--admin 또는 --company 하나(argparse 의 상호 배제 — 둘 다·둘 다 없음은 종료 2), --username, 비밀번호 받기."""
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--admin", action="store_true", help="운영 관리자(회사 없음)")
    target.add_argument("--company", metavar="SUBDOMAIN", help="고객사 사용자의 회사 서브도메인")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password-stdin", action="store_true", help="비밀번호를 표준 입력 한 줄로 받는다")


def read_secret(options: dict[str, Any]) -> str:
    """비밀번호를 받는다. 명령줄 인자로는 받지 않는다."""
    if options["password_stdin"]:
        stream: TextIO = options.get("stdin") or sys.stdin
        typed = stream.readline().rstrip("\n")
    else:
        typed = getpass("비밀번호: ")
        if typed != getpass("비밀번호 다시: "):
            raise CommandError("두 번 친 비밀번호가 다르다")
    if not typed:
        raise CommandError("비밀번호가 비었다")
    return typed


def company_id_of(subdomain: str) -> int:
    found = find_company(subdomain)
    if isinstance(found, CompanyUnknown):
        raise CommandError(f"서브도메인 {subdomain} 의 회사가 없다")
    return found.company.id


class Command(BaseCommand):
    # 테스트가 call_command(..., stdin=StringIO(...)) 로 표준 입력을 넘길 수 있게(--password-stdin)
    stealth_options = ("stdin",)
    help = "운영 관리자(--admin) 또는 고객사 사용자(--company) 하나를 만든다(이미 있으면 덮지 않는다)"

    def add_arguments(self, parser: CommandParser) -> None:
        add_target_arguments(parser)
        parser.add_argument("--name", required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        username: str = options["username"]
        name: str = options["name"]
        subdomain: str | None = options["company"]
        company_id = None if subdomain is None else company_id_of(subdomain)
        secret = read_secret(options)
        if company_id is None:
            result = create_operator(username=username, name=name, password=secret)
        else:
            result = create_customer_user(
                actor_kind="admin", company_id=company_id, username=username, name=name, password=secret
            )
        if isinstance(result, Forbidden):  # 셸을 쥔 사람은 운영 관리자다 — 표가 막으면(2차의 칸 바꿈) 멈춘다
            raise CommandError(result.message)
        if isinstance(result, UsernameTaken):
            raise CommandError("그 username 이 이미 있다(덮지 않는다)")
        if isinstance(result, PasswordRejected):
            raise CommandError("비밀번호를 쓸 수 없다: " + " ".join(result.messages))
        kind = "admin" if company_id is None else "service"
        self.stdout.write(f"{result.user_id} {kind} {subdomain or '-'}")
