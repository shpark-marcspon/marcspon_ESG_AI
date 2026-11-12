"""Scope 3 후보 추리기의 조립: 기준정보(reference)의 낱줄을 읽어 inventory 의 추리기에 넘긴다.

도메인 둘을 부르므로 Action 이다. Service·Selector 는 남의 도메인을 import 하지 않는다(`.importlinter` 계약 바).
"""

from collections.abc import Mapping, Sequence

from esgapi.inventory.engines.scope3.llm_first_1.catalog import ListFactorCatalog, RawRecord
from esgapi.inventory.engines.scope3.llm_first_1.shortlister import ShortlistMethod
from esgapi.inventory.engines.scope3.llm_first_1.types import CandidateBasis, LicenseStatus, SupportedCategory
from esgapi.inventory.service.services import inventory as services
from esgapi.reference.service.selectors import reference as reference_selectors


def scope3_catalog(licenses: frozenset[LicenseStatus]) -> ListFactorCatalog:
    """기준정보의 표에서 Scope 3 후보를 읽어 순수 층의 카탈로그로 만든다. 표 순서는 id 의 코드 포인트 순이다."""
    views = reference_selectors.scope3_candidate_records(licenses=licenses)
    return ListFactorCatalog(
        RawRecord(
            id=view.id,
            record_type=view.record_type,
            gas=view.gas,
            value=view.value,
            value_raw=view.value_raw,
            scope3_categories=view.scope3_categories,
            factor_type=view.factor_type,
            name_original=view.name_original,
            category_path=view.category_path,
            unit=view.unit,
            unit_numerator=view.unit_numerator,
            unit_denominator=view.unit_denominator,
            license_status=view.license_status,
            source_id=view.source_id,
            region=view.region,
            classification=view.classification,
            spend=view.spend,
        )
        for view in views
    )


def scope3_shortlist_output(
    *,
    row: Mapping[str, object],
    category: SupportedCategory,
    keywords: Sequence[str] | None,
    basis: CandidateBasis | None,
    method: ShortlistMethod | None,
    bigrams: bool | None,
    size: int | None,
    license_text: str | None,
) -> dict[str, object]:
    """경로가 부른다: 이용 조건을 읽고 → 기준정보에서 후보를 읽고 → inventory 의 추리기에 넘긴다."""
    licenses = services.scope3_licenses(license_text)
    return services.scope3_shortlist_output(
        row=row,
        category=category,
        keywords=keywords,
        basis=basis,
        method=method,
        bigrams=bigrams,
        size=size,
        catalog=scope3_catalog(licenses),
    )
