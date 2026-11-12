"""쪽지를 잃었을 수 있는 흐름의 실행을 큐에 다시 넣는다:  python manage.py requeue_runs --tenant <회사 id> [--dry-run]

    --tenant <회사 id>                  필수. 이 회사의 실행만 본다(십진 숫자 글자. 꼴이 틀리면 2)
    --queued-older-than-seconds <N>     `queued` 로 이만큼 머문 실행을 고른다. 기본은 임대(JOB_LEASE_SECONDS)
    --dry-run                           고르기만 하고 넣지 않는다(브로커 없이도 된다)

requeue_jobs(같은 폴더)의 실행 판이다 — 인자·종료 코드·찍는 꼴이 같다.
고르는 것: 임대가 지난 `processing`(워커가 죽었거나 하드 시간 제한에 걸렸다 — 하드 제한으로 죽은 시도의 쪽지는
task_reject_on_worker_lost 로 다시 와도 임대가 살아 있어 잡히지 않는다)과 오래 머문 `queued`(큐 넣기가 실패했다).
넣는 것은 쪽지뿐이다: 행은 건드리지 않는다. 받은 워커의 「잡기」가 상태와 임대를 다시 본다(여러 번 돌려도 된다).

차례: 트랜잭션을 열고 그 회사의 실행을 고른다 → **블록을 나온 뒤**(커밋 뒤) 큐에 넣는다.
찍는 것: 고른 수·넣은 수·실패한 수와, 실행마다 id·상태·시도(흐름 id·옵션은 찍지 않는다).
종료 코드: 0 = 전부 넣었다(고른 것이 없어도 0), 1 = 브로커 설정이 없거나 넣다가 실패한 것이 있다, 2 = 쓰는 법이 틀렸다.

★ `--tenant` 가 필수인 까닭은 requeue_jobs 와 같다(회사를 가로질러 훑는 길이 없다 — 누가 언제 돌리는지는 배포의 일).
"""

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from esgapi.core.calc.documents import COMPANY_ID_TEXT
from esgapi.core.conf import app_config, now
from esgapi.core.resources import queue as hooks
from esgapi.runs.service.selectors.runs import stale_runs

USAGE_ERROR = 2


class Command(BaseCommand):
    help = "임대가 지난 processing 과 오래 머문 queued 실행을 큐에 다시 넣는다(회사 하나씩)"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--tenant", required=True, help="회사 id(필수, 십진 숫자)")
        parser.add_argument("--queued-older-than-seconds", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        company_text: str = options["tenant"]
        dry_run: bool = options["dry_run"]
        older: int | None = options["queued_older_than_seconds"]
        if COMPANY_ID_TEXT.match(company_text) is None:
            raise CommandError("--tenant 의 꼴이 틀렸다", returncode=USAGE_ERROR)
        company_id = int(company_text)
        if older is None:
            older = app_config().jobs.lease_s
        if older < 0:
            raise CommandError("--queued-older-than-seconds 는 0 이상이어야 한다", returncode=USAGE_ERROR)
        if not dry_run and hooks.broker_settings() is None:
            raise CommandError("CELERY_BROKER_URL 이 없다. 큐에 넣을 수 없다(고르기만 하려면 --dry-run)", returncode=1)

        # durable: 다른 트랜잭션 안에서 불리면 거절한다(고르기의 커밋이 큐에 넣기보다 먼저 나가야 한다).
        with transaction.atomic(durable=True):
            stale = stale_runs(company_id=company_id, now=now(), queued_older_than_s=older)
        # ★ 여기부터 트랜잭션 밖이다(커밋 뒤). 큐에 넣는 것을 블록 안에서 하지 않는다.

        sent = 0
        failed = 0
        for run in stale:
            line = f"{run.id} {run.status} attempts={run.attempts}"
            if dry_run:
                self.stdout.write(f"고름 {line}")
                continue
            try:
                hooks.enqueue_run(company_id=run.company_id, run_id=run.id)
            except Exception as err:  # 하나가 실패해도 나머지를 넣는다. 오류의 종류만 찍는다(주소·키가 들 수 있다)
                failed += 1
                self.stderr.write(f"실패 {line} ({type(err).__name__})")
            else:
                sent += 1
                self.stdout.write(f"넣음 {line}")
        self.stdout.write(f"고른 수 {len(stale)} · 넣은 수 {sent} · 실패한 수 {failed}")
        if failed:
            raise CommandError(f"넣지 못한 실행이 {failed}건이다", returncode=1)
