"""쪽지를 잃었을 수 있는 일감을 큐에 다시 넣는다:  python manage.py requeue_jobs --tenant <회사 id> [--dry-run]

    --tenant <회사 id>                  필수. 이 회사의 일감만 본다(십진 숫자 글자. 꼴이 틀리면 2. 옵션 이름은 C1)
    --queued-older-than-seconds <N>     `queued` 로 이만큼 머문 일감을 고른다. 기본은 임대(JOB_LEASE_SECONDS)
    --dry-run                           고르기만 하고 넣지 않는다(브로커 없이도 된다)

고르는 것: 임대가 지난 `processing`(워커가 죽었거나 하드 시간 제한에 걸렸다)과 오래 머문 `queued`(큐 넣기가
실패했거나 큐가 비워졌다). 넣는 것은 쪽지뿐이다: 행은 건드리지 않는다. 받은 워커의 「잡기」가 상태와 임대를 다시 본다
(이미 끝났거나 남이 쥔 일감은 잡히지 않는다. 그래서 여러 번 돌려도 된다).

차례: 트랜잭션을 열고 그 회사의 일감을 고른다 → **블록을 나온 뒤**(커밋 뒤) 큐에 넣는다.
찍는 것: 고른 수·넣은 수·실패한 수와, 일감마다 id·상태·시도(파일 이름·저장소 키는 찍지 않는다).
종료 코드: 0 = 전부 넣었다(고른 것이 없어도 0), 1 = 브로커 설정이 없거나 넣다가 실패한 것이 있다, 2 = 쓰는 법이 틀렸다.

★ `--tenant` 가 필수인 까닭(무효 조건): 고르기(stale_jobs)는 회사를 인자로 받아 조건에 적고, 일감 표의 기본
  매니저는 회사를 정하지 않은 조회를 거절한다(core/isolation). 이 명령에는 회사를 가로질러 훑는 길이 없다
  → 운영에서 스스로 돌지 못한다(회사마다 사람이 돌린다). 가로지르는 다시 넣기와 주기적으로 돌리는 장치는 없다.
"""

from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from esgapi.core.calc.documents import COMPANY_ID_TEXT
from esgapi.core.conf import app_config, now
from esgapi.core.resources import queue as hooks
from esgapi.runs.service.selectors.jobs import stale_jobs

USAGE_ERROR = 2


class Command(BaseCommand):
    help = "임대가 지난 processing 과 오래 머문 queued 일감을 큐에 다시 넣는다(회사 하나씩)"

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
        # 갈고리는 브로커 설정이 없으면 조용히 돌아간다. 이 명령은 「넣었다」고 말해야 하므로 먼저 본다.
        if not dry_run and hooks.broker_settings() is None:
            raise CommandError("CELERY_BROKER_URL 이 없다. 큐에 넣을 수 없다(고르기만 하려면 --dry-run)", returncode=1)

        # durable: 다른 트랜잭션 안에서 불리면 거절한다(고르기의 커밋이 큐에 넣기보다 먼저 나가야 한다).
        with transaction.atomic(durable=True):
            stale = stale_jobs(company_id=company_id, now=now(), queued_older_than_s=older)
        # ★ 여기부터 트랜잭션 밖이다(커밋 뒤). 큐에 넣는 것을 블록 안에서 하지 않는다.

        sent = 0
        failed = 0
        for job in stale:
            line = f"{job.id} {job.status} attempts={job.attempts}"
            if dry_run:
                self.stdout.write(f"고름 {line}")
                continue
            try:
                hooks.enqueue_job(company_id=job.company_id, job_id=job.id, kind=job.kind)
            except Exception as err:  # 하나가 실패해도 나머지를 넣는다. 오류의 종류만 찍는다(주소·키가 들 수 있다)
                failed += 1
                self.stderr.write(f"실패 {line} ({type(err).__name__})")
            else:
                sent += 1
                self.stdout.write(f"넣음 {line}")
        self.stdout.write(f"고른 수 {len(stale)} · 넣은 수 {sent} · 실패한 수 {failed}")
        if failed:
            raise CommandError(f"넣지 못한 일감이 {failed}건이다", returncode=1)
