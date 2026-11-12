"""[모두 받기] — 묶음의 끝난 파트 자동수정 병기본을 zip 하나로(GET /translation/documents/{document_id}/batches/
{batch_key}/archive 의 몸 — 밴드 TR3b ③, MARC-ISSUE-200). runs(실행 열쇠·결과·파일 행·저장소 바이트)를 엮으므로 Action
이다. 묶음을 찾는 길은 service/actions/batches.py 의 하나 보기와 같다(run_keys·digest — 옵션 본문·결과 본문 0).

    archive(company_id, document_id, batch_key)   Archive | NotFound | NothingFinished | TooLarge

규칙(발주서 TR3b §2-5):
  - 넣는 것: 파트마다 최신 실행이 done 이고 digest status done 이면 문체마다 files.autofix 의 이름 그대로(TR3a — 이름
    규칙 한 벌). digest 없는 옛 실행은 그 실행의 출력 파일 가운데 이름이 `translation-autofix-` 로 시작하는 것.
  - 이름은 있는데 행이 없거나 저장소에 객체가 없으면(output_bytes None) 그 항목을 빼고 missing 에 센다(부르는 쪽이 머리
    X-Archive-Missing·구조 로그). 저장소 없음·거절·닿지 못함은 503 셋을 그대로 던진다(runs 의 output_bytes).
  - 넣은 것이 0 이면 NothingFinished, 행의 크기 합이 ARCHIVE_MAX_BYTES 를 넘으면 바이트를 읽기 전에 TooLarge.
  - 문서가 그 회사에 없으면(남의 회사 문서·없는 문서) 묶음 하나 보기와 같은 NotFound(MARC-ISSUE-324).
  - 항목 `<part>-<파일 이름>`, zip `translation-<document_id>-<batch_key 앞 8>.zip` — 둘 다 ASCII.
★ 목록·하나 보기 경로의 메모리는 늘리지 않는다: runs_of 를 부르지 않고 파트 최신 실행의 바이트만 차례로 읽는다.
★ zip 은 통째 바이트로 복사하지 않는다: SPOOL_MAX_BYTES 까지 메모리, 넘으면 임시 파일에 쓰고 파일째 넘긴다. 항목은
  WRITE_CHUNK 씩 흘려 압축한다(writestr 는 항목의 압축본을 통째로 한 벌 더 들었다 — 밴드 TRS2, MARC-ISSUE-399. 잰 값은
  band-reports/TRS2.md). 저장소에서 읽은 항목 바이트 한 벌은 그대로다(runs 의 output_bytes 가 bytes 를 준다).
"""

import logging
import tempfile
import time
import zipfile
from dataclasses import dataclass
from typing import IO, Final

from esgapi.core.service.selectors import documents as document_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.services import files as file_services
from esgapi.translation.contracts.digest_shapes import TranslationDigest
from esgapi.translation.service.actions import batches

logger = logging.getLogger(__name__)

ARCHIVE_MAX_BYTES: Final = 64 * 1024 * 1024
"""넣는 바이트 합의 상한(어림 — 파일 하나 상한 max_upload_bytes 50MiB × 많아야 여섯 안쪽으로 잡은 값, 추정)."""
OLD_AUTOFIX_PREFIX: Final = "translation-autofix-"
SPOOL_MAX_BYTES: Final = 8 * 1024 * 1024
"""zip 을 메모리에 두는 문턱 — 넘으면 임시 파일로 넘어간다(SpooledTemporaryFile, MARC-ISSUE-324)."""
WRITE_CHUNK: Final = 1024 * 1024
"""항목을 zip 에 흘려 쓰는 조각(압축기에 한 번에 넣는 바이트)."""


@dataclass(frozen=True, slots=True)
class Archive:
    """data 는 처음으로 감은 zip 파일 — 부르는 쪽이 흘려보내고 닫는다(FileResponse 가 응답 끝에 닫음)."""

    name: str
    data: IO[bytes]
    entries: tuple[str, ...]
    missing: int


@dataclass(frozen=True, slots=True)
class NothingFinished:
    """내려받을 끝난 파트가 없다(빠진 항목 수 missing)."""

    missing: int


@dataclass(frozen=True, slots=True)
class TooLarge:
    total_bytes: int


def _wanted(company_id: int, run_id: int, digest: TranslationDigest | None) -> list[str]:
    """그 실행에서 넣을 파일 이름(문체 차례)."""
    if digest is None:  # 요약을 남기기 전의 옛 실행 — 출력 파일 이름으로
        return [
            f.name
            for f in run_selectors.run_files(company_id=company_id, run_id=run_id)
            if f.step is None and f.name.startswith(OLD_AUTOFIX_PREFIX)
        ]
    if digest["status"] != "done":
        return []
    return [name for v in digest["variants"] if (name := v["files"]["autofix"]) is not None]


def archive(
    *, company_id: int, document_id: int, batch_key: str
) -> Archive | batches.NotFound | NothingFinished | TooLarge:
    found = batches.find(company_id=company_id, document_id=document_id, batch_key=batch_key)  # 묶음 찾기 한 벌
    if isinstance(found, batches.NotFound):
        return found
    if document_id not in document_selectors.documents_of(company_id=company_id, document_ids=[document_id]):
        return batches.NotFound()  # 묶음 하나 보기(batches.batch)와 같은 자리·같은 갈래
    rows: list[tuple[str, int, run_selectors.RunFile]] = []
    missing = 0
    for key in found.group.latest():
        if key.status != "done":
            continue
        for name in _wanted(company_id, key.id, found.digests.get(key.id)):
            row = run_selectors.output_file(company_id=company_id, run_id=key.id, name=name)
            if row is None:
                missing += 1
                logger.warning("translation_archive_missing run_id=%s name=%s", key.id, name)
                continue
            rows.append((f"{key.part}-{name}", key.id, row))
    total = sum(row.size_bytes for _, _, row in rows)
    if total > ARCHIVE_MAX_BYTES:
        return TooLarge(total)
    spool = tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_BYTES)  # noqa: SIM115 — 응답이 닫는다
    try:
        entries = _write(spool, rows)
    except BaseException:
        spool.close()
        raise
    if not entries:
        spool.close()
        return NothingFinished(missing + len(rows))
    spool.seek(0)
    return Archive(
        name=f"translation-{document_id}-{batch_key[:8]}.zip",
        data=spool,
        entries=tuple(entries),
        missing=missing + len(rows) - len(entries),
    )


def _write(target: IO[bytes], rows: list[tuple[str, int, run_selectors.RunFile]]) -> list[str]:
    """rows 를 차례로 읽어 zip 으로 쓴다. 넣은 항목 이름(저장소에 객체가 없는 것은 빼고 로그 한 줄)."""
    entries: list[str] = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for entry, run_id, row in rows:
            data = file_services.output_bytes(row)  # 저장소 없음·거절·닿지 못함은 503 셋을 던진다
            if data is None:
                logger.warning("translation_archive_missing run_id=%s name=%s", run_id, row.name)
                continue
            _put(zipped, entry, data)
            entries.append(entry)
    return entries


def _put(zipped: zipfile.ZipFile, entry: str, data: bytes) -> None:
    """writestr(entry, data) 와 같은 항목(이름·시각·권한 0o600·압축)을 WRITE_CHUNK 씩 흘려 쓴다."""
    info = zipfile.ZipInfo(entry, date_time=time.localtime(time.time())[:6])
    info.compress_type = zipped.compression
    info.compress_level = zipped.compresslevel
    info.external_attr = 0o600 << 16
    info.file_size = len(data)
    view = memoryview(data)
    with zipped.open(info, "w") as stream:
        for start in range(0, len(view), WRITE_CHUNK):
            stream.write(view[start : start + WRITE_CHUNK])
