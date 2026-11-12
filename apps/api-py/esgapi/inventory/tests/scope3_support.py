"""Scope 3 순수 테스트(커밋 경계 ①)가 같이 쓰는 것: 가상 행과 가상 계수.

★ 전부 가상(synthetic)이다. 값은 계산하기 쉬운 숫자로 지어냈고 실제 배출계수가 아니다.
esg-lab `ts/scope3/test/helpers.ts` 의 `row()` 와 가상 계수 가운데 후보가 되는 여덟을 옮겼다
(기체별 행과 값 없는 행은 후보가 아니라 `Factor` 가 되지 않는다. 그 둘은 scope3_catalog_support 에 낱줄로 있다).
"""

from typing import Any

from esgapi.inventory.engines.scope3.llm_first_1.types import (
    Basis,
    Factor,
    FactorClassification,
    InputRow,
    LicenseStatus,
    SpendInfo,
    TransportInfo,
)
from esgapi.inventory.engines.scope3.llm_first_1.units import unit_dim


def transport(
    *,
    origin: str = "여수",
    destination: str = "평택",
    mode: str = "트럭",
    weight_kg: str | None = "21000",
    distance_km: str | None = None,
) -> TransportInfo:
    return TransportInfo(origin, destination, mode, weight_kg, distance_km)


def row(item_name: str, **over: Any) -> InputRow:
    """TS `row()` 와 같은 기본값: 10 kg, 100000 KRW."""
    values: dict[str, Any] = {
        "row_id": "r1",
        "item_name": item_name,
        "quantity": "10",
        "unit": "kg",
        "amount": "100000",
        "currency": "KRW",
        "date": "2026-01-05",
        "org_unit": "본사",
        "transport": None,
    }
    values.update(over)
    return InputRow(**values)


def factor(
    factor_id: str,
    name: str,
    categories: tuple[int, ...],
    factor_type: Basis,
    per: str,
    value: str,
    *,
    license_status: LicenseStatus = "ok",
    naics: str | None = None,
    path: tuple[str, ...] = (),
    numerator: str = "kg CO2e",
) -> Factor:
    return Factor(
        id=factor_id,
        name=name,
        category_path=path,
        factor_type=factor_type,
        scope3_categories=categories,
        unit=f"{numerator}/{per}",
        unit_numerator=numerator,
        unit_denominator=per,
        denominator_dim=unit_dim(per),
        value_raw=value,
        license_status=license_status,
        source_id="synthetic",
        region="GLOBAL",
        classification=FactorClassification("NAICS 2017", naics) if naics is not None else None,
        spend=SpendInfo("USD", 2022, "purchaser") if factor_type == "spend" else None,
    )


USD_2022 = "2022 USD, purchaser price"

SYNTHETIC_FACTORS: tuple[Factor, ...] = (
    factor("syn:steel-kg", "합성 강판 (synthetic)", (1,), "activity", "kg", "2.5", path=("합성 자재", "금속")),
    factor(
        "syn:steel-t", "Synthetic steel sheet", (1,), "activity", "tonnes", "2400", path=("Synthetic material", "Metal")
    ),
    factor(
        "syn:pp-kg",
        "합성 폴리프로필렌 (synthetic)",
        (1,),
        "activity",
        "kg",
        "1.25",
        license_status="disputed",
        path=("합성 자재", "플라스틱"),
    ),
    factor("syn:truck", "Synthetic truck", (4, 9), "distance", "tonne.km", "0.1", path=("Synthetic freight", "Road")),
    factor("syn:rail", "Synthetic rail", (6, 7), "distance", "passenger.km", "0.04", path=("Synthetic travel", "Rail")),
    factor("syn:spend-computer", "Synthetic Computer Manufacturing", (1, 2), "spend", USD_2022, "0.5", naics="334111"),
    factor(
        "syn:spend-storage", "Synthetic Storage Device Manufacturing", (1, 2), "spend", USD_2022, "0.2", naics="334112"
    ),
    factor("syn:spend-legal", "Synthetic Legal Services", (1, 2), "spend", USD_2022, "0.1", naics="541199"),
)

FACTOR_BY_ID: dict[str, Factor] = {entry.id: entry for entry in SYNTHETIC_FACTORS}
