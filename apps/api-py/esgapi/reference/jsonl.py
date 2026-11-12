"""계수 표(jsonl) 한 줄의 꼴. esg-lab 의 적재기(`py/factors`)가 쓴 산출물을 읽는 자리다. Django 를 모른다.

꼴의 정본은 esg-lab 의 `schemas/factor.schema.json`(schema_version 0.1)이다. 여기는 그것을 Pydantic 으로 옮긴 것이고
(jsonschema 를 새로 들이지 않는다), 스키마의 `allOf` 다섯(값 상태 ↔ 값, 지출 계수 ↔ spend, 발열량 ↔ 순·총,
scope3 ↔ 범주)까지 같이 본다. 모르는 칸이 있으면 거절한다(판이 바뀐 파일을 조용히 읽지 않는다).

파일을 여는 일은 여기서 하지 않는다. 줄을 받아 꼴을 보고 내준다.
"""

from collections.abc import Iterable, Iterator
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from esgapi.reference.calc.types import FactorRecord, SourceRef

SCHEMA_VERSION = "0.1"

LicenseStatus = Literal["ok", "disputed", "unverified"]
LICENSE_STATUSES: tuple[LicenseStatus, ...] = ("ok", "disputed", "unverified")

_Text = Annotated[str, Field(min_length=1)]
_Url = Annotated[str, Field(pattern=r"^https?://\S+$")]
_Day = Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")]


class _Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class NameIn(_Shape):
    original: _Text
    ko: str | None
    en: str | None


class ClassificationIn(_Shape):
    system: _Text
    code: _Text


class SpendIn(_Shape):
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    price_year: int
    price_basis: _Text


class SourceIn(_Shape):
    id: _Text
    name: _Text
    publisher: _Text
    url: _Url
    version: _Text
    retrieved: _Day
    file_name: _Text
    file_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    locator: _Text


class LicenseIn(_Shape):
    name: _Text
    url: _Url
    note: str | None


class RecordIn(_Shape):
    schema_version: Literal["0.1"]
    id: _Text
    record_type: Literal["emission_factor", "heating_value", "energy_conversion", "oxidation_factor"]
    scope: Literal["scope1", "scope2", "scope3", "outside_of_scopes", "unspecified"]
    scope3_categories: list[Annotated[int, Field(ge=1, le=15)]]
    scope3_mapping_basis: str | None
    factor_type: Literal["activity", "distance", "spend"]
    name: NameIn
    category_path: list[str]
    classification: ClassificationIn | None
    value: float | None
    value_raw: str | None
    value_status: Literal["ok", "not_available_in_source", "not_applicable_in_source"]
    unit: _Text
    unit_numerator: _Text
    unit_denominator: _Text
    gas: Literal["CO2e", "CO2", "CH4", "N2O", "C", "none"]
    gas_basis: Literal["co2e", "gas_mass", "carbon_mass", "not_applicable"]
    heating_value_basis: Literal["net", "gross"] | None
    conditions: dict[str, str]
    region: Annotated[str, Field(min_length=2)]
    year: int | None
    spend: SpendIn | None
    # 환율·물가 보정 값. 정본 스키마에 꼴이 있지만 지금 산출물은 전부 null 이다. 꼴은 풀지 않고 그대로 싣는다.
    adjusted: dict[str, object] | None
    source: SourceIn
    license: LicenseIn
    license_status: LicenseStatus
    synthetic: bool
    extra: dict[str, object]

    @model_validator(mode="after")
    def _cross_field_rules(self) -> Self:
        if not self.id.startswith(f"{self.source.id}:"):
            raise ValueError("id 는 `<source.id>:` 로 시작한다")
        if len(set(self.scope3_categories)) != len(self.scope3_categories):
            raise ValueError("scope3_categories 에 같은 범주가 두 번 있다")
        if (self.factor_type == "spend") != (self.spend is not None):
            raise ValueError("spend 는 지출 계수(factor_type=spend)에만, 그때는 꼭 있다")
        if self.value_status == "ok":
            if self.value is None or not self.value_raw:
                raise ValueError("value_status 가 ok 이면 value 와 value_raw 가 있다")
        elif self.value is not None:
            raise ValueError("value_status 가 ok 가 아니면 value 는 null 이다")
        if self.record_type == "heating_value":
            if self.heating_value_basis is None or self.gas != "none":
                raise ValueError("발열량 낱줄은 순·총(heating_value_basis)이 있고 gas 가 none 이다")
        elif self.heating_value_basis is not None:
            raise ValueError("발열량이 아닌 낱줄에 heating_value_basis 가 있다")
        if (self.scope == "scope3") != bool(self.scope3_categories):
            raise ValueError("scope3_categories 는 scope3 낱줄에만, 그때는 하나 이상 있다")
        if self.scope3_categories and not self.scope3_mapping_basis:
            raise ValueError("scope3 범주가 있으면 scope3_mapping_basis 가 있다")
        return self


class LineInvalid(ValueError):
    """jsonl 의 한 줄이 꼴에 맞지 않는다. 몇째 줄의 어느 칸이 왜 틀렸는지를 싣는다(받은 값은 싣지 않는다)."""

    def __init__(self, line_no: int, where: str) -> None:
        super().__init__(f"{line_no}행: {where}")
        self.line_no = line_no
        self.where = where


def read_records(lines: Iterable[str]) -> Iterator[tuple[int, RecordIn]]:
    """줄을 하나씩 받아 (줄 번호, 낱줄)을 내준다. 한 번에 한 줄만 쥔다. 빈 줄은 건너뛴다."""
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            yield line_no, RecordIn.model_validate_json(line)
        except ValidationError as err:
            where = "; ".join(
                f"{'.'.join(str(part) for part in e['loc']) or '<줄>'} ({e['type']}: {e['msg']})"
                for e in err.errors()[:5]
            )
            raise LineInvalid(line_no, where) from err


def to_calc(record: RecordIn) -> FactorRecord:
    """조립이 읽는 칸만 추린다. `value`(float)는 넘기지 않는다."""
    source = record.source
    return FactorRecord(
        id=record.id,
        record_type=record.record_type,
        name_original=record.name.original,
        category_path=tuple(record.category_path),
        value_raw=record.value_raw,
        value_status=record.value_status,
        unit_numerator=record.unit_numerator,
        unit_denominator=record.unit_denominator,
        gas=record.gas,
        gas_basis=record.gas_basis,
        heating_value_basis=record.heating_value_basis,
        conditions=dict(record.conditions),
        source=SourceRef(
            id=source.id,
            name=source.name,
            url=source.url,
            version=source.version,
            retrieved=source.retrieved,
            file_name=source.file_name,
            file_sha256=source.file_sha256,
            locator=source.locator,
        ),
        synthetic=record.synthetic,
    )
