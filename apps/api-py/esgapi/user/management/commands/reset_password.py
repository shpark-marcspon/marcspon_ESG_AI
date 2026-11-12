"""계정 하나의 비밀번호를 초기화한다(부트스트랩 — K2a). 운영 관리자가 자기 비밀번호를 잃었을 때의 길이다.

    python manage.py reset_password --admin --username <아이디> [--password-stdin]
    python manage.py reset_password --company <서브도메인> --username <아이디> [--password-stdin]

새 비밀번호를 싣고 is_initial 참(다음 로그인 때 바꿔야 함)·실패 셈 0·잠금 풀림·그 사용자의 refresh 계보 전부 끊음.
비밀번호 받기는 create_user 와 같다(명령줄 인자로 받지 않는다). 없는 사용자·검사기 거절은 종료 1.
초기화는 user/service/actions/password.py 의 reset_password(K2c 의 HTTP 초기화가 같은 것), 검사기·해시는 그 앞의
services.user.prepare_reset 이다 — 이 파일은 표를 직접 쓰지 않는다.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from esgapi.core.conf import now
from esgapi.user.management.commands.create_user import add_target_arguments, company_id_of, read_secret
from esgapi.user.service.actions.password import reset_password
from esgapi.user.service.permissions.user import Forbidden
from esgapi.user.service.services.user import prepare_reset
from esgapi.user.service.utils.login import PasswordRejected, UserNotFound


class Command(BaseCommand):
    # 테스트가 call_command(..., stdin=StringIO(...)) 로 표준 입력을 넘길 수 있게(--password-stdin)
    stealth_options = ("stdin",)
    help = "운영 관리자(--admin) 또는 고객사 사용자(--company) 하나의 비밀번호를 초기화한다"

    def add_arguments(self, parser: CommandParser) -> None:
        add_target_arguments(parser)

    def handle(self, *args: Any, **options: Any) -> None:
        subdomain: str | None = options["company"]
        company_id = None if subdomain is None else company_id_of(subdomain)
        secret = read_secret(options)
        prepared = prepare_reset(company_id=company_id, username=options["username"], password=secret)
        if isinstance(prepared, UserNotFound):
            raise CommandError("그 사용자가 없다")
        if isinstance(prepared, PasswordRejected):
            raise CommandError("비밀번호를 쓸 수 없다: " + " ".join(prepared.messages))
        done = reset_password(
            actor_kind="admin",
            company_id=prepared.company_id,
            user_id=prepared.user_id,
            password_hash=prepared.password_hash,
            now=now(),
        )
        if isinstance(done, Forbidden):  # 셸을 쥔 사람은 운영 관리자다 — 표가 막으면(2차의 칸 바꿈) 멈춘다
            raise CommandError(done.message)
        if isinstance(done, UserNotFound):
            raise CommandError("그 사용자가 없다")
        kind = "admin" if company_id is None else "service"
        self.stdout.write(f"{done.user_id} {kind} {subdomain or '-'}")
