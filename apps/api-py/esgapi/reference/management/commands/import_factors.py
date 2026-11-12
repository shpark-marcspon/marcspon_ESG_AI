"""계수 표와 대응표를 DB 에 들인다.

    python manage.py import_factors [<factors.jsonl>] [--mapping <json>] [--include-license ok,unverified]

  인자 없이           패키지에 실린 사본(지침 별표·GIR 공표 600건)과 대응표를 들인다
  <factors.jsonl>     그 파일을 들인다(esg-lab 의 `data/factors/factors.jsonl`). 대응표는 --mapping 을 줄 때만
  --include-license   들일 이용 조건 상태. 기본 ok,unverified — **disputed(KEITI)는 명시해야만 들어온다**

주인 역할의 설정으로만 돈다:
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate python manage.py import_factors
    docker compose run --rm migrate-py python manage.py import_factors            (compose)
앱 역할의 설정으로 부르면 `not_owner` 로 멈춘다. 규칙과 무효 조건은
esgapi/reference/admin/services/importer.py 의 머리말.
"""

import json
import resource
import sys
import time
from argparse import ArgumentParser
from importlib import resources
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from esgapi.reference.admin.services.importer import ImportRejected, ImportReport, import_factors
from esgapi.reference.licenses import DEFAULT_LICENSES_TEXT, LicenseListInvalid, parse_license_list
from esgapi.reference.models import FactorRecordRow, FactorScope3CategoryRow, MappingRow, SourceRow

DATA = resources.files("esgapi.reference.data")
PACKAGED_FACTORS = "factors.kr.jsonl"
PACKAGED_MAPPING = "mappings.kr-ets.json"


def _peak_rss_mb() -> float:
    """이 프로세스가 가장 많이 쥐었던 메모리(MB). ru_maxrss 의 단위가 macOS 는 바이트, 리눅스는 KB 다."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


class Command(BaseCommand):
    help = "계수 표(jsonl)와 대응표(json)를 DB 에 들인다. 주인 역할의 설정으로만 돈다"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("factors", nargs="?", help="계수 표(jsonl)의 경로. 생략하면 패키지에 실린 사본")
        parser.add_argument("--mapping", help="조립용 대응표(json)의 경로. 계수 표를 생략했으면 패키지의 사본")
        parser.add_argument(
            "--include-license",
            default=DEFAULT_LICENSES_TEXT,
            help="들일 이용 조건 상태를 쉼표로(ok, unverified, disputed). 기본 %(default)s",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            include = parse_license_list(options["include_license"])
        except LicenseListInvalid as err:
            raise CommandError(f"invalid_license_list: {err}") from err
        factors: str | None = options["factors"]
        mapping: str | None = options["mapping"]
        started = time.monotonic()
        try:
            mapping_body, mapping_from = self._mapping(mapping, packaged=factors is None)
            if factors is None:
                factors_from = f"패키지 사본 {PACKAGED_FACTORS}"
                with DATA.joinpath(PACKAGED_FACTORS).open(encoding="utf-8") as lines:
                    report = import_factors(lines, mapping_body=mapping_body, include=include)
            else:
                factors_from = factors
                with Path(factors).open(encoding="utf-8") as lines:
                    report = import_factors(lines, mapping_body=mapping_body, include=include)
        except ImportRejected as err:
            raise CommandError(f"{err.reason}: {err.message}") from err
        except (OSError, json.JSONDecodeError) as err:
            raise CommandError(f"unreadable_file: {type(err).__name__}: {err}") from err
        self._print(report, factors_from, mapping_from, sorted(include), time.monotonic() - started)

    def _mapping(self, path: str | None, *, packaged: bool) -> tuple[object | None, str]:
        if path is not None:
            return json.loads(Path(path).read_text(encoding="utf-8")), path
        if packaged:
            body = json.loads(DATA.joinpath(PACKAGED_MAPPING).read_text(encoding="utf-8"))
            return body, f"패키지 사본 {PACKAGED_MAPPING}"
        return None, "건너뜀(--mapping 없음)"

    def _print(self, report: ImportReport, factors: str, mapping: str, include: list[str], seconds: float) -> None:
        out = self.stdout.write
        out(f"계수 표: {factors}")
        out(f"대응표: {mapping}" + (f" → {report.mapping_version}" if report.mapping_version else ""))
        out(f"들인 이용 조건 상태: {','.join(include)}")
        out(f"읽은 줄 {report.lines} = 쓴 줄 {report.written} + 걸러 낸 줄 {report.skipped}")
        out("출처별 쓴 줄:")
        for source_id, count in sorted(report.written_by_source.items()):
            out(f"  {source_id}\t{count}")
        out("출처별 걸러 낸 줄(이용 조건 상태가 위 목록에 없다):")
        for source_id, count in sorted(report.skipped_by_source.items()):
            out(f"  {source_id}\t{count}")
        if not report.skipped_by_source:
            out("  (없음)")
        out(f"출처별 지운 줄(이번 파일의 그 출처에서 쓰지 않은 기존 행, 모두 {report.deleted}):")
        for source_id, count in sorted(report.deleted_by_source.items()):
            out(f"  {source_id}\t{count}")
        if not report.deleted_by_source:
            out("  (없음)")
        out("license_status 별 쓴 줄: " + ", ".join(f"{k} {v}" for k, v in sorted(report.written_by_license.items())))
        out(f"쓴 줄의 Scope 3 범주 연결: {report.scope3_links}")
        if report.mapping_only_sources:
            out(f"대응표만 가리키는 출처(낱줄 없음, unverified 로 둠): {', '.join(report.mapping_only_sources)}")
        # 아래는 이번에 쓴 것이 아니라 지금 DB 에 있는 것이다(파일에 안 나온 출처의 행도 든다).
        out(
            "지금 DB: "
            f"출처 {SourceRow.objects.count()}, 낱줄 {FactorRecordRow.objects.count()}, "
            f"범주 연결 {FactorScope3CategoryRow.objects.count()}, 대응표 {MappingRow.objects.count()}"
        )
        by_status = dict.fromkeys(("ok", "unverified", "disputed"), 0)
        for row in FactorRecordRow.objects.values_list("source__license_status", flat=True).iterator():
            by_status[row] += 1
        out("지금 DB 의 license_status 별 낱줄: " + ", ".join(f"{k} {v}" for k, v in by_status.items()))
        out(f"걸린 시간 {seconds:.2f}초, 최대 메모리 {_peak_rss_mb():.0f} MB")
