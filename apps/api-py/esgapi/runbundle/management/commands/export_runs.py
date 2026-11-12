"""한 회사의 끝난 실행을 묶음 zip 하나로 쓴다(RX1a):

    python manage.py export_runs --company <id> (--runs 1,2 | --module m --from YYYY-MM-DD --to YYYY-MM-DD)
                                 --out <경로> [--max-runs 200]

고르는 것: --runs 는 그 실행들(done 만 — 아니면 거절), --module·--from·--to 는 그 모듈의 실행 가운데 created_at 이 서울
날짜 양끝 안의 done(나머지는 상태별 「건너뜀」으로 센다 — --max-runs 는 모든 상태를 센다). 이어 가기 사슬의 앞 실행은
done·failed 를 기록으로 더 싣고, carrier 가 말한 앞 실행은 같은 모듈 done 만 — 아니면 --runs 는 거절, 창은 그 실행을
건너뛰고 「참조 밖 n」으로 찍는다(RX1b Qb8·Qb10).
--out 은 0600 으로 쓰고 이미 있으면 거절한다. 머리의 appCommit 은 환경 변수 APP_COMMIT(없으면 "unknown" + 경고).
찍는 것: 묶음 id·실행 수(닫힘 몫)·표별 행 수·JSON·blob·zip 바이트·zip sha256(값·키·사람 0).
종료 코드: 0 = 썼다, 1 = 거절(파일 0 — 거절 밖 예외도 「거절(쓰기 0) — <예외 이름>: <글>」 한 줄, 트레이스백은
--verbose 일 때만), 2 = 쓰는 법이 틀렸다.
★ 묶음은 「원본과 같은 취급」이다 — 저장소·GitHub·S3 에 두지 않는다(Q10).
"""

import os
import re
from argparse import ArgumentParser
from datetime import date
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from esgapi.core.calc.documents import COMPANY_ID_TEXT
from esgapi.runbundle.calc.bundle import Refused
from esgapi.runbundle.service.actions import export
from esgapi.runbundle.service.actions.export import RunIds, Window

USAGE_ERROR = 2
RUN_IDS = re.compile(r"[1-9][0-9]*(,[1-9][0-9]*)*")


def _date(text: str, flag: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise CommandError(f"{flag} 은 YYYY-MM-DD 여야 한다", returncode=USAGE_ERROR) from None


class Command(BaseCommand):
    help = "한 회사의 끝난 실행을 묶음 zip 하나로 쓴다(실행 묶음 RX1a)"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--company", required=True, help="회사 id(필수, 십진 숫자)")
        parser.add_argument("--runs", default=None, help="실행 id 들(쉼표)")
        parser.add_argument("--module", default=None)
        parser.add_argument("--from", dest="first", default=None)
        parser.add_argument("--to", dest="last", default=None)
        parser.add_argument("--out", required=True)
        parser.add_argument("--max-runs", type=int, default=export.DEFAULT_MAX_RUNS)
        parser.add_argument("--verbose", action="store_true", help="거절 밖 예외의 트레이스백을 그대로 낸다")

    def handle(self, *args: Any, **options: Any) -> None:
        company_text: str = options["company"]
        if COMPANY_ID_TEXT.match(company_text) is None:
            raise CommandError("--company 의 꼴이 틀렸다", returncode=USAGE_ERROR)
        runs: str | None = options["runs"]
        window = (options["module"], options["first"], options["last"])
        selection: RunIds | Window
        if runs is not None and window == (None, None, None):
            if RUN_IDS.fullmatch(runs) is None:
                raise CommandError("--runs 는 쉼표로 이은 양의 정수다", returncode=USAGE_ERROR)
            selection = RunIds(tuple(int(part) for part in runs.split(",")))
        elif runs is None and None not in window:
            selection = Window(
                module=str(options["module"]),
                first=_date(str(options["first"]), "--from"),
                last=_date(str(options["last"]), "--to"),
            )
        else:
            raise CommandError("--runs 하나 또는 --module·--from·--to 셋을 준다", returncode=USAGE_ERROR)
        max_runs: int = options["max_runs"]
        if max_runs < 1:
            raise CommandError("--max-runs 는 1 이상이다", returncode=USAGE_ERROR)
        app_commit = os.environ.get("APP_COMMIT", "")
        if not app_commit:
            self.stderr.write("경고: APP_COMMIT 이 없어 appCommit 을 unknown 으로 적는다")
            app_commit = "unknown"
        try:
            done = export.run(
                company_id=int(company_text),
                selection=selection,
                out=Path(options["out"]),
                app_commit=app_commit,
                max_runs=max_runs,
            )
        except Refused as err:
            raise CommandError(f"거절: {err}", returncode=1) from None
        except Exception as err:  # 거절 밖 예외 — 내보내기는 DB·저장소에 쓰지 않고 --out 은 마지막에 생긴다
            if options["verbose"]:
                raise
            raise CommandError(f"거절(쓰기 0) — {type(err).__name__}: {err}", returncode=1) from None
        counts = " ".join(f"{table}={count}" for table, count in done.counts.items())
        self.stdout.write(
            f"묶음 {done.bundle_id} · 실행 {done.runs}(닫힘 {done.closure}) · {counts} · JSON {done.json_bytes}B · "
            f"blob {done.blob_bytes}B · zip {done.zip_bytes}B sha256={done.zip_sha256}"
        )
        if done.skipped or done.out_of_reference:
            skipped = " ".join(f"{status}={count}" for status, count in sorted(done.skipped.items()))
            self.stdout.write(f"건너뜀 {skipped or '0'} · 참조 밖 {done.out_of_reference}")
