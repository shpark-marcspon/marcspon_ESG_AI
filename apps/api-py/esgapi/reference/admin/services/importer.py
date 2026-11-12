"""계수 표(jsonl)와 대응표(json)를 DB 에 들인다. 관리 명령 `import_factors` 가 부른다.

    esg-lab: 원자료(PDF·xlsx·csv·hwpx) ──(py/factors, 빌드 시점)──▶ factors.jsonl ──(여기)──▶ DB
  PDF 를 읽는 적재기는 옮기지 않았다. 앱은 그 산출물만 읽는다(런타임에 PDF 라이브러리가 없다).

규칙:
  - **트랜잭션 하나.** 한 줄이라도 꼴이 틀리면(걸러 낼 출처의 줄이어도) 아무것도 쓰지 않는다.
  - **한 줄씩 읽는다.** 파일을 통째로 쥐지 않는다. 쥐는 것은 본 id 의 집합과 쓰기 묶음(1,000줄)이다.
  - **id 로 upsert.** 같은 파일을 두 번 들여도 행 수가 그대로다.
  - **disputed 는 기본으로 뺀다.** `include` 에 명시한 상태의 낱줄만 쓴다. 뺀 출처는 출처 표에도 넣지 않는다.
  - **이번 파일에 나온 출처는 이번 파일이 정본이다.** 그 출처의 DB 행 가운데 이번에 쓰지 않은 것(파일에서 빠진 줄,
    include 밖으로 바뀐 줄)을 지운다(그 행의 Scope 3 범주 연결도 CASCADE 로).
    파일에 안 나온 출처의 행은 건드리지 않는다.
  - **주인 역할만 쓴다.** 앱 역할로 부르면 `not_owner` 갈래로 멈춘다(권한 오류를 삼키지 않는다).

무효 조건:
  - 파일에서 통째로 빠진 출처의 행은 DB 에 남는다(위 규칙은 이번 파일에 나온 출처에만 든다).
  - 행을 다 지운 출처의 출처 표 행은 남는다(낱줄 0 으로 보인다).
  - 남는 낱줄에서 더는 후보가 아니게 된 Scope 3 범주의 연결 행도 남는다.
  - 고시 별표(kr-ets-*)의 낱줄 id 에는 판이 없다. 다른 판의 파일을 들이면 같은 id 의 행과 출처 행을 덮어쓴다
    (판은 출처 표의 version 칸 하나가 말한다). 두 판을 나란히 둘 수 없다.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import psycopg.errors
from django.db import ProgrammingError, transaction
from pydantic import BaseModel, ConfigDict, ValidationError

from esgapi.reference.calc import MappingShapeError, mapping_from_json
from esgapi.reference.jsonl import LicenseStatus, LineInvalid, RecordIn, read_records
from esgapi.reference.models import FactorRecordRow, FactorScope3CategoryRow, MappingRow, SourceRow

BATCH: Final = 1000

Rejection = Literal[
    "not_owner",  # 앱 역할로 불렀다(쓰기 권한이 없다)
    "invalid_shape",  # jsonl 의 한 줄이 꼴에 맞지 않는다
    "duplicate_id",  # 한 파일에 같은 id 가 두 번 있다
    "inconsistent_source",  # 한 출처의 낱줄들이 서로 다른 출처·이용 조건 블록을 싣고 있다
    "empty",  # 낱줄이 한 건도 없다
    "mapping_invalid",  # 대응표의 꼴이 다르다
]


class ImportRejected(Exception):
    """들이지 않았다. `reason` 이 갈래의 이름이다. 이 예외가 나면 DB 에는 아무것도 쓰이지 않았다."""

    def __init__(self, reason: Rejection, message: str) -> None:
        super().__init__(message)
        self.reason: Rejection = reason
        self.message = message


@dataclass
class ImportReport:
    """들인 결과. 건수는 이번에 **쓴** 줄의 수다(DB 의 행 수가 아니다. 그것은 명령이 따로 센다)."""

    lines: int = 0
    written_by_source: Counter[str] = field(default_factory=Counter[str])
    written_by_license: Counter[str] = field(default_factory=Counter[str])
    skipped_by_source: Counter[str] = field(default_factory=Counter[str])
    # 이번 파일에 나온 출처의 기존 행 가운데 이번에 쓰지 않아 지운 것(빠진 줄·include 밖으로 바뀐 줄).
    deleted_by_source: Counter[str] = field(default_factory=Counter[str])
    scope3_links: int = 0
    mapping_version: str | None = None
    mapping_only_sources: list[str] = field(default_factory=list[str])

    @property
    def written(self) -> int:
        return sum(self.written_by_source.values())

    @property
    def skipped(self) -> int:
        return sum(self.skipped_by_source.values())

    @property
    def deleted(self) -> int:
        return sum(self.deleted_by_source.values())


class _MappingSource(BaseModel):
    """대응표의 `sources` 한 항목. 낱줄이 없는 출처(kr-ets-byl05)는 여기에만 있다. 이용 조건 블록이 없다."""

    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    publisher: str
    url: str
    version: str
    retrieved: str
    file_name: str
    file_sha256: str


class _MappingSources(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sources: dict[str, _MappingSource] = {}


_RECORD_UPDATE_FIELDS: Final = [
    f.attname for f in FactorRecordRow._meta.concrete_fields if not f.primary_key and f.attname != "created_at"
]


def _source_block(record: RecordIn) -> dict[str, Any]:
    """출처 표의 한 행이 될 값. 낱줄마다 다른 locator 는 뺀다."""
    source, license_ = record.source, record.license
    return {
        "name": source.name,
        "publisher": source.publisher,
        "url": source.url,
        "version": source.version,
        "retrieved": source.retrieved,
        "file_name": source.file_name,
        "file_sha256": source.file_sha256,
        "license_name": license_.name,
        "license_url": license_.url,
        "license_note": license_.note,
        "license_status": record.license_status,
    }


def _row(record: RecordIn) -> FactorRecordRow:
    return FactorRecordRow(
        id=record.id,
        source_id=record.source.id,
        locator=record.source.locator,
        schema_version=record.schema_version,
        record_type=record.record_type,
        scope=record.scope,
        scope3_mapping_basis=record.scope3_mapping_basis,
        factor_type=record.factor_type,
        name_original=record.name.original,
        name_ko=record.name.ko,
        name_en=record.name.en,
        category_path=record.category_path,
        classification=None if record.classification is None else record.classification.model_dump(),
        value=record.value,
        value_raw=record.value_raw,
        value_status=record.value_status,
        unit=record.unit,
        unit_numerator=record.unit_numerator,
        unit_denominator=record.unit_denominator,
        gas=record.gas,
        gas_basis=record.gas_basis,
        heating_value_basis=record.heating_value_basis,
        conditions=record.conditions,
        region=record.region,
        year=record.year,
        spend=None if record.spend is None else record.spend.model_dump(),
        adjusted=record.adjusted,
        synthetic=record.synthetic,
        extra=record.extra,
    )


def _flush(rows: list[FactorRecordRow], links: list[FactorScope3CategoryRow]) -> None:
    if rows:
        FactorRecordRow.objects.bulk_create(
            rows, update_conflicts=True, unique_fields=["id"], update_fields=_RECORD_UPDATE_FIELDS
        )
        rows.clear()
    if links:
        # (낱줄, 범주) 쌍이 이미 있으면 그대로 둔다.
        FactorScope3CategoryRow.objects.bulk_create(links, ignore_conflicts=True)
        links.clear()


def _delete_unwritten(written_ids: dict[str, set[str]], report: ImportReport) -> None:
    """이번 파일에 나온 출처마다, 그 출처의 DB 행 가운데 이번에 쓰지 않은 것을 지운다."""
    for source_id, written in written_ids.items():
        stale = [
            record_id
            for record_id in FactorRecordRow.objects.filter(source_id=source_id).values_list("id", flat=True).iterator()
            if record_id not in written
        ]
        for start in range(0, len(stale), BATCH):
            FactorRecordRow.objects.filter(id__in=stale[start : start + BATCH]).delete()
        if stale:
            report.deleted_by_source[source_id] += len(stale)


def _import_records(lines: Iterable[str], include: frozenset[LicenseStatus], report: ImportReport) -> None:
    seen_ids: set[str] = set()
    written_ids: dict[str, set[str]] = {}
    blocks: dict[str, dict[str, Any]] = {}
    rows: list[FactorRecordRow] = []
    links: list[FactorScope3CategoryRow] = []
    try:
        for line_no, record in read_records(lines):
            report.lines += 1
            if record.id in seen_ids:
                raise ImportRejected("duplicate_id", f"{line_no}행: 같은 id 가 두 번 있다 ({record.id})")
            seen_ids.add(record.id)
            source_id = record.source.id
            block = _source_block(record)
            known = blocks.get(source_id)
            if known is None:
                blocks[source_id] = block
                written_ids[source_id] = set()
            elif known != block:
                differing = ", ".join(sorted(key for key in block if block[key] != known[key]))
                raise ImportRejected(
                    "inconsistent_source", f"{line_no}행: 출처 {source_id} 의 블록이 앞 줄과 다르다 ({differing})"
                )
            # 꼴은 걸러 낼 줄도 다 본다. 쓰는 것만 거른다.
            if record.license_status not in include:
                report.skipped_by_source[source_id] += 1
                continue
            if known is None:
                SourceRow.objects.update_or_create(id=source_id, defaults=block)
            rows.append(_row(record))
            written_ids[source_id].add(record.id)
            links.extend(
                FactorScope3CategoryRow(record_id=record.id, category=category) for category in record.scope3_categories
            )
            report.written_by_source[source_id] += 1
            report.written_by_license[record.license_status] += 1
            report.scope3_links += len(record.scope3_categories)
            if len(rows) >= BATCH:
                _flush(rows, links)
        _flush(rows, links)
    except LineInvalid as err:
        raise ImportRejected("invalid_shape", str(err)) from err
    if report.lines == 0:
        raise ImportRejected("empty", "낱줄이 한 건도 없다")
    _delete_unwritten(written_ids, report)


def _import_mapping(body: object, include: frozenset[LicenseStatus], report: ImportReport) -> None:
    try:
        mapping = mapping_from_json(body)
        listed = _MappingSources.model_validate(body).sources
    except (MappingShapeError, ValidationError) as err:
        raise ImportRejected("mapping_invalid", str(err).splitlines()[0]) from err
    MappingRow.objects.update_or_create(guideline_version=mapping.guideline.version, defaults={"body": body})
    report.mapping_version = mapping.guideline.version
    # 대응표만 가리키는 출처(낱줄이 없다. kr-ets-byl05 의 최소 산정등급). 낱줄에서 온 출처 행은 건드리지 않는다.
    # 대응표에는 이용 조건 블록이 없다 → 「확인하지 못했다」(unverified)로 두고 이름·주소는 비운다
    # (문구를 지어내지 않는다).
    if "unverified" not in include:
        return
    for source_id, source in listed.items():
        _, created = SourceRow.objects.get_or_create(
            id=source_id,
            defaults={
                **source.model_dump(),
                "license_name": "",
                "license_url": "",
                "license_note": None,
                "license_status": "unverified",
            },
        )
        if created:
            report.mapping_only_sources.append(source_id)


def import_factors(
    lines: Iterable[str] | None, *, mapping_body: object | None, include: frozenset[LicenseStatus]
) -> ImportReport:
    """낱줄(없으면 건너뛴다)과 대응표(없으면 건너뛴다)를 한 트랜잭션으로 들인다."""
    report = ImportReport()
    try:
        with transaction.atomic():
            if lines is not None:
                _import_records(lines, include, report)
            if mapping_body is not None:
                _import_mapping(mapping_body, include, report)
    except ProgrammingError as err:
        if isinstance(err.__cause__, psycopg.errors.InsufficientPrivilege):
            raise ImportRejected(
                "not_owner",
                "이 연결의 역할에는 기준정보 표에 쓸 권한이 없다. 주인 역할의 설정으로 돌린다 "
                "(DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate)",
            ) from err
        raise
    return report
