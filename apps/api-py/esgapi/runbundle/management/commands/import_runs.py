"""묶음 zip 하나를 그 회사에 새 id 로 다 넣거나 0 을 넣는다(RX1a):

    python manage.py import_runs <묶음> --company <id> --user <id> --orphans-out <파일> [--dry-run] [--max-bytes N]

--company 의 회사가 있고 --user 가 그 회사의 사람(고객사 사용자 또는 운영 관리자)이어야 한다. 묶음 안의 회사·사람·id 는
믿지 않는다(새 id, 회사·사람은 이 인자). --dry-run 은 문을 다 지난 뒤 셈만 찍고 쓰지 않는다.
--orphans-out: 블록 앞에서 0600 으로 만든다(이미 있으면 거절). 행을 다 넣은 뒤 저장소에 올리다 실패하면 그때까지 올린
키(키만)를 이 파일에 쓴다(행은 되돌려진다 — 인프라가 그 키를 자기 자격으로 지운다). 그 쓰기도 실패하면 키를 stderr 로.
커밋 단계의 오류는 새 연결로 다시 보아 커밋됐으면 경고 한 줄(고아 0, 종료 0), 모르면 「확인 불가 키(지우지 말 것)」
머리로 파일과 stderr 에(종료 1). 파일 첫 줄은 머리(# …) — 갈래를 가른다. 고아가 없으면 빈 파일은 지운다.
찍는 것: 옛 실행 id → 새 id 지도와 표별 행 수(값·키·사람 0).
종료 코드: 0 = 넣었다(또는 --dry-run), 1 = 거절(쓰기 0) 또는 올린 뒤 실패(--orphans-out), 2 = 쓰는 법이 틀렸다.
거절 밖의 예외(지도 밖 id·꼴·제약 위반 등 — 올리기 앞이라 행은 되돌려졌다)도
「거절(쓰기 0) — <예외 이름>: <글>」 한 줄과 종료 1 이다. 트레이스백은 --verbose 일 때만.
"""

from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from esgapi.core.calc.documents import COMPANY_ID_TEXT
from esgapi.runbundle.calc.bundle import Refused
from esgapi.runbundle.service.actions import import_
from esgapi.runbundle.service.actions.import_ import ImportFailed

USAGE_ERROR = 2


class Command(BaseCommand):
    help = "묶음 zip 하나를 그 회사에 새 id 로 넣는다(실행 묶음 RX1a)"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("bundle")
        parser.add_argument("--company", required=True, help="회사 id(필수, 십진 숫자)")
        parser.add_argument("--user", required=True, help="넣은 사람 id(필수, 십진 숫자)")
        parser.add_argument("--orphans-out", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--max-bytes", type=int, default=import_.DEFAULT_MAX_BYTES)
        parser.add_argument("--verbose", action="store_true", help="거절 밖 예외의 트레이스백을 그대로 낸다")

    def handle(self, *args: Any, **options: Any) -> None:
        for flag in ("company", "user"):
            if COMPANY_ID_TEXT.match(str(options[flag])) is None:
                raise CommandError(f"--{flag} 의 꼴이 틀렸다", returncode=USAGE_ERROR)
        max_bytes: int = options["max_bytes"]
        if max_bytes < 1:
            raise CommandError("--max-bytes 는 1 이상이다", returncode=USAGE_ERROR)
        try:
            done = import_.run(
                path=Path(options["bundle"]),
                company_id=int(options["company"]),
                user_id=int(options["user"]),
                orphans_out=Path(options["orphans_out"]),
                dry_run=options["dry_run"],
                max_bytes=max_bytes,
            )
        except Refused as err:
            raise CommandError(f"거절: {err}", returncode=1) from None
        except ImportFailed as err:
            if not err.written or err.rolled_back is None:  # 쓰기 실패 · 커밋 여부 확인 불가 — 머리 줄 + 키를 stderr 로
                self.stderr.write("\n".join([err.head, *err.keys]))
            raise CommandError(str(err), returncode=1) from None
        except Exception as err:  # 거절 밖 예외 — 쓰기 앞이거나 블록 안이라 되돌려졌다(쓰기 0)
            if options["verbose"]:
                raise
            raise CommandError(f"거절(쓰기 0) — {type(err).__name__}: {err}", returncode=1) from None
        counts = " ".join(f"{table}={count}" for table, count in done.counts.items())
        if done.commit_error is not None:
            self.stderr.write(f"경고: 커밋 단계에서 {done.commit_error} 가 났으나 다시 보니 커밋됐다(고아 0)")
        if done.dry_run:
            self.stdout.write(f"(dry-run) 묶음 {done.bundle_id} · {counts}")
            return
        for old_id, new_id in sorted(done.runs.items()):
            self.stdout.write(f"실행 {old_id} → {new_id}")
        self.stdout.write(f"묶음 {done.bundle_id} 넣음 · {counts}")
