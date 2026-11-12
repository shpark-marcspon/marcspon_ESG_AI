"""패키지에 실린 기준정보 표. 순수 층."""

from esgapi.inventory.data_loader import DATA_FILES, default_tables, read_data
from esgapi.inventory.tests.support import AR5_GWP, DIESEL_ID, ELECTRICITY_ID, ETS_GWP


def test_default_tables_hold_the_sample_factors_conversions_and_two_gwp_sets() -> None:
    tables = default_tables()
    assert [f.id for f in tables.factors] == [
        DIESEL_ID,
        "kr-ets-sample:city-gas-lng:stationary:commercial:tier2",
        ELECTRICITY_ID,
    ]
    assert [s.id for s in tables.gwp_sets] == [ETS_GWP, AR5_GWP]
    assert len(tables.unit_conversions) == 25
    assert default_tables() is tables  # 한 번만 읽는다


def test_no_synthetic_number_ships_in_the_package() -> None:
    """가상 계수와 가상 GWP 세트는 시험 자료(tests/data)에만 있다. 패키지 자료의 수치는 출처가 있거나 정의값이다."""
    tables = default_tables()
    assert {r.source.kind for r in [*tables.factors, *tables.gwp_sets]} == {"cited"}
    assert {c.source.kind for c in tables.unit_conversions} == {"definition"}
    for name in DATA_FILES:
        assert "synthetic" not in str(read_data(name).keys())
