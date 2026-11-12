"""읽기. Django ORM 을 쓰고, 결과는 순수 dataclass 로 바꿔 내보낸다. 쓰지 않는다.

★ 기준정보의 표에는 테넌트 칸도 RLS 도 없다. 어느 세션이 물어도 같은 행이 온다(전역 자료다).
  그래서 다른 Selector 와 달리 조회에 tenant 조건이 없고, 아래 표시 줄이 그것을 일부러 한 일로 적어 둔다
  (core/tests/test_selector_scope.py 가 읽는다). tenant 칸이 있는 표를 읽게 되면 표시 줄을 지우고 조건을 적는다.
"""

# tenant-scope: global — 이 파일이 읽는 표 넷(reference_*)에는 tenant 칸이 없다(전역 자료).

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from django.db.models import Count, Q

from esgapi.reference.calc import AssemblyMapping, FactorRecord, SourceRef, mapping_from_json
from esgapi.reference.jsonl import LicenseStatus
from esgapi.reference.models import FactorRecordRow, FactorScope3CategoryRow, MappingRow, SourceRow

# ── 조립이 읽는 것 ────────────────────────────────────────────────────


def record_of(row: FactorRecordRow) -> FactorRecord:
    """ORM 행 → 조립이 받는 낱줄. `value`(float)는 넘기지 않는다. row.source 가 같이 읽혀 있어야 한다."""
    source = row.source
    return FactorRecord(
        id=row.id,
        record_type=row.record_type,
        name_original=row.name_original,
        category_path=tuple(row.category_path),
        value_raw=row.value_raw,
        value_status=row.value_status,
        unit_numerator=row.unit_numerator,
        unit_denominator=row.unit_denominator,
        gas=row.gas,
        gas_basis=row.gas_basis,
        heating_value_basis=row.heating_value_basis,
        conditions=dict(row.conditions),
        source=SourceRef(
            id=source.id,
            name=source.name,
            url=source.url,
            version=source.version,
            retrieved=source.retrieved,
            file_name=source.file_name,
            file_sha256=source.file_sha256,
            locator=row.locator,
        ),
        synthetic=row.synthetic,
    )


def records_for_assembly(source_ids: Iterable[str]) -> list[FactorRecord]:
    """그 출처들의 낱줄 전부. 조립 함수가 이 묶음에서 낱줄을 고른다. 차례는 id 순이다(파일의 차례가 아니다)."""
    rows = FactorRecordRow.objects.filter(source_id__in=list(source_ids)).select_related("source").order_by("id")
    return [record_of(row) for row in rows]


@dataclass(frozen=True)
class MappingFound:
    mapping: AssemblyMapping


@dataclass(frozen=True)
class MappingAbsent:
    """대응표가 들어와 있지 않다(`import_factors` 를 돌리지 않았다)."""


@dataclass(frozen=True)
class MappingAmbiguous:
    """대응표가 둘 이상이다(지침의 판이 여럿). 어느 판으로 조립할지 고르는 입력이 아직 없다."""

    versions: tuple[str, ...]


def current_mapping() -> MappingFound | MappingAbsent | MappingAmbiguous:
    rows = list(MappingRow.objects.order_by("guideline_version")[:2])
    if not rows:
        return MappingAbsent()
    if len(rows) > 1:
        return MappingAmbiguous(tuple(MappingRow.objects.order_by("guideline_version").values_list("pk", flat=True)))
    return MappingFound(mapping_from_json(rows[0].body))


# ── 목록 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceView:
    id: str
    name: str
    publisher: str
    url: str
    version: str
    retrieved: str
    file_name: str
    file_sha256: str
    license_name: str
    license_url: str
    license_note: str | None
    license_status: str
    record_count: int


def _source_view(row: SourceRow, record_count: int) -> SourceView:
    return SourceView(
        id=row.id,
        name=row.name,
        publisher=row.publisher,
        url=row.url,
        version=row.version,
        retrieved=row.retrieved,
        file_name=row.file_name,
        file_sha256=row.file_sha256,
        license_name=row.license_name,
        license_url=row.license_url,
        license_note=row.license_note,
        license_status=row.license_status,
        record_count=record_count,
    )


def list_sources() -> list[SourceView]:
    """출처 전부(이용 조건 상태와 무관하게). 낱줄이 없는 출처(대응표만 가리키는 것)는 record_count 가 0 이다."""
    counts: Counter[str] = Counter()
    for item in FactorRecordRow.objects.values("source_id").annotate(n=Count("id")):
        counts[item["source_id"]] = item["n"]
    return [_source_view(row, counts[row.id]) for row in SourceRow.objects.order_by("id")]


def sources_by_id(source_ids: Iterable[str]) -> list[SourceView]:
    """그 id 의 출처들(조립 결과에 이용 조건을 같이 싣는 데 쓴다). 건수는 세지 않는다(0)."""
    return [_source_view(row, 0) for row in SourceRow.objects.filter(id__in=list(source_ids)).order_by("id")]


@dataclass(frozen=True)
class FactorView:
    """낱줄 하나(목록용). jsonl 의 칸 그대로에 출처의 이용 조건 둘을 붙였다."""

    id: str
    source_id: str
    license_status: str
    license_note: str | None
    locator: str
    record_type: str
    scope: str
    scope3_categories: tuple[int, ...]
    scope3_mapping_basis: str | None
    factor_type: str
    name_original: str
    name_ko: str | None
    name_en: str | None
    category_path: tuple[str, ...]
    classification: dict[str, Any] | None
    value: float | None
    value_raw: str | None
    value_status: str
    unit: str
    unit_numerator: str
    unit_denominator: str
    gas: str
    gas_basis: str
    heating_value_basis: str | None
    conditions: dict[str, str]
    region: str
    year: int | None
    spend: dict[str, Any] | None
    synthetic: bool


@dataclass(frozen=True)
class FactorPage:
    total: int
    items: list[FactorView]


def _factor_view(row: FactorRecordRow, categories: tuple[int, ...]) -> FactorView:
    return FactorView(
        id=row.id,
        source_id=row.source_id,
        license_status=row.source.license_status,
        license_note=row.source.license_note,
        locator=row.locator,
        record_type=row.record_type,
        scope=row.scope,
        scope3_categories=categories,
        scope3_mapping_basis=row.scope3_mapping_basis,
        factor_type=row.factor_type,
        name_original=row.name_original,
        name_ko=row.name_ko,
        name_en=row.name_en,
        category_path=tuple(row.category_path),
        classification=cast(dict[str, Any] | None, row.classification),
        value=row.value,
        value_raw=row.value_raw,
        value_status=row.value_status,
        unit=row.unit,
        unit_numerator=row.unit_numerator,
        unit_denominator=row.unit_denominator,
        gas=row.gas,
        gas_basis=row.gas_basis,
        heating_value_basis=row.heating_value_basis,
        conditions=dict(row.conditions),
        region=row.region,
        year=row.year,
        spend=cast(dict[str, Any] | None, row.spend),
        synthetic=row.synthetic,
    )


def find_factors(
    *,
    licenses: frozenset[LicenseStatus],
    source: str | None = None,
    record_type: str | None = None,
    scope: str | None = None,
    gas: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> FactorPage:
    """조건이 전부 맞는 낱줄을 id 순으로. `q` 는 이름 셋(원문·한글·영문)의 부분 일치다(대소문자 무시).

    검색 순위가 없다. 후보를 추려 순서를 매기는 일은 여기서 하지 않는다(Scope 3 의 후보 추리기는 다른 밴드).
    ★ `licenses` 에 없는 이용 조건 상태의 낱줄은 내지 않는다. 부르는 쪽이 기본(ok·unverified)을 넘긴다.
    """
    rows = FactorRecordRow.objects.filter(source__license_status__in=sorted(licenses))
    if source is not None:
        rows = rows.filter(source_id=source)
    if record_type is not None:
        rows = rows.filter(record_type=record_type)
    if scope is not None:
        rows = rows.filter(scope=scope)
    if gas is not None:
        rows = rows.filter(gas=gas)
    if q:
        rows = rows.filter(Q(name_original__icontains=q) | Q(name_ko__icontains=q) | Q(name_en__icontains=q))
    total = rows.count()
    page = list(rows.select_related("source").order_by("id")[offset : offset + limit])
    # 이 쪽의 낱줄들이 후보인 Scope 3 범주를 한 번에 읽는다.
    categories: dict[str, list[int]] = {}
    links = FactorScope3CategoryRow.objects.filter(record_id__in=[row.id for row in page])
    for record_id, category in links.values_list("record_id", "category"):
        categories.setdefault(record_id, []).append(category)
    return FactorPage(total=total, items=[_factor_view(row, tuple(sorted(categories.get(row.id, ())))) for row in page])


# ── Scope 3 의 후보 ───────────────────────────────────────────────────


@dataclass(frozen=True)
class Scope3CandidateView:
    """Scope 3 후보가 될 수 있는 낱줄 하나. 추리기와 계산이 읽는 칸만 담았다(`value` 는 「값이 있다」는 뜻으로만)."""

    id: str
    source_id: str
    license_status: str
    record_type: str
    gas: str
    value: float | None
    value_raw: str | None
    scope3_categories: tuple[int, ...]
    factor_type: str
    name_original: str
    category_path: tuple[str, ...]
    classification: dict[str, Any] | None
    unit: str
    unit_numerator: str
    unit_denominator: str
    region: str
    spend: dict[str, Any] | None


def scope3_candidate_records(*, licenses: frozenset[LicenseStatus]) -> list[Scope3CandidateView]:
    """Scope 3 후보의 자격 넷을 갖춘 낱줄 전부: 배출계수 · CO2e · 값이 있음 · Scope 3 범주가 하나 이상.

    범주·기반으로 더 거르는 일과 `value_raw` 의 판정은 여기서 하지 않는다(inventory 의 순수 층이 한다).
    ★ `licenses` 에 없는 이용 조건 상태의 낱줄은 내지 않는다. 부르는 쪽이 기본(ok·unverified)을 넘긴다.
    ★ 차례는 **id 의 유니코드 코드 포인트 순**이고 파이썬에서 놓는다(DB 의 collation 에 맡기지 않는다).
      id 에는 `_`·`-`·`:`·`.` 이 섞여 있어 DB 의 로캘 정렬과 코드 포인트 순이 갈린다. 추리기가 동점을 이 차례로
      가르므로 로컬과 운영 DB 에서 같은 답이 나오려면 차례가 DB 설정에 달려 있으면 안 된다.
      이 차례는 파일(jsonl)의 줄 순서가 아니다(표에 적재 순서 칸이 없다).
    쿼리는 둘이다(낱줄, 범주 연결). 캐시하지 않는다.
    """
    wanted = sorted(licenses)
    categories: dict[str, list[int]] = {}
    links = FactorScope3CategoryRow.objects.filter(
        record__record_type="emission_factor",
        record__gas="CO2e",
        record__value__isnull=False,
        record__source__license_status__in=wanted,
    )
    for record_id, category in links.values_list("record_id", "category"):
        categories.setdefault(record_id, []).append(category)
    rows = FactorRecordRow.objects.filter(
        record_type="emission_factor", gas="CO2e", value__isnull=False, source__license_status__in=wanted
    ).values(
        "id",
        "source_id",
        "source__license_status",
        "record_type",
        "gas",
        "value",
        "value_raw",
        "factor_type",
        "name_original",
        "category_path",
        "classification",
        "unit",
        "unit_numerator",
        "unit_denominator",
        "region",
        "spend",
    )
    found = [
        Scope3CandidateView(
            id=row["id"],
            source_id=row["source_id"],
            license_status=row["source__license_status"],
            record_type=row["record_type"],
            gas=row["gas"],
            value=row["value"],
            value_raw=row["value_raw"],
            scope3_categories=tuple(sorted(categories[row["id"]])),
            factor_type=row["factor_type"],
            name_original=row["name_original"],
            category_path=tuple(row["category_path"]),
            classification=cast(dict[str, Any] | None, row["classification"]),
            unit=row["unit"],
            unit_numerator=row["unit_numerator"],
            unit_denominator=row["unit_denominator"],
            region=row["region"],
            spend=cast(dict[str, Any] | None, row["spend"]),
        )
        for row in rows
        # 범주 연결이 없는 낱줄은 후보가 아니다(자격 넷째).
        if row["id"] in categories
    ]
    return sorted(found, key=lambda view: view.id)
