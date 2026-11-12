"""T5 에너지 계수 시트 둘: `에너지` 는 첫 읽기 header_row=3(`:326`) → 셀 25 자동 머리글 다시 읽기(「활동유형」·
「CO2eq」·「기준단위」 `:7205`, 비지 않으면 갈음), `에너지_C3` 는 header_row=2(`:9048`) 한 번(다시 읽지 않음 —
`initial`).
"""

from esgapi.inventory.engines.scope3.colab_157.energy import energy_db_cols
from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    ENERGY_C3_SHEET,
    ENERGY_SHEET,
    read_energy_c3_sheet,
    read_energy_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, sheet, workbook

ENERGY_HEAD: list[Value] = [
    "구분",
    "배출활동",
    "활동유형(에너지원)",
    "투입량 기준단위",
    "순발열량",
    "CO2eq ★\n(kgCO2eq/단위)",
]
C3_HEAD: list[Value] = ["활동유형(에너지원)", "기준단위", "EF\n(kgCO2eq/단위)", "비고"]


def energy_rows(head_row: int) -> dict[int, list[Value]]:
    """제목 한 줄·안내 뒤 `head_row` 째 줄(1부터)이 머리글, 그다음 두 줄이 값."""
    rows: dict[int, list[Value]] = {1: ["가상 계수 책 — 에너지"]}
    rows.update({n: [f"가상 안내 {n}"] for n in range(2, head_row)})
    rows[head_row] = ENERGY_HEAD
    rows[head_row + 1] = ["가상 간접", "가상 전력 사용", "전력", "kWh", None, 0.0941]
    rows[head_row + 2] = ["가상 직접", "가상 이동연소", "경유", "L", 9.1, 0.942]
    return rows


def test_energy_sheet_with_the_header_on_row_four_is_read_the_same_both_ways() -> None:
    with legacy_strings():
        read = read_energy_sheet(workbook(sheet(ENERGY_SHEET, energy_rows(4))))
    assert (read.how, read.header, len(read.frame)) == ("reloaded", 3, 2)
    cols = energy_db_cols(read.frame)
    assert (cols.name, cols.unit, cols.ef) == ("활동유형(에너지원)", "투입량 기준단위", "CO2eq ★\n(kgCO2eq/단위)")


def test_energy_sheet_reload_finds_a_header_the_first_read_misses() -> None:
    """머리글이 셋째 줄이면 첫 읽기(넷째 줄을 머리글로)는 값 줄을 머리글로 보고, 다시 읽기가 셋째 줄을 찾아 갈음한다."""
    with legacy_strings():
        read = read_energy_sheet(workbook(sheet(ENERGY_SHEET, energy_rows(3))))
    assert (read.how, read.header, list(read.frame["활동유형(에너지원)"])) == ("reloaded", 2, ["전력", "경유"])


def test_energy_c3_is_read_once_on_row_three() -> None:
    rows: dict[int, list[Value]] = {
        1: ["가상 계수 책 — 에너지_C3"],
        2: ["가상 안내"],
        3: C3_HEAD,
        4: ["전력", "kWh", 0.0951, None],
    }
    with legacy_strings():
        read = read_energy_c3_sheet(workbook(sheet(ENERGY_C3_SHEET, rows)))
    assert (read.how, read.header, list(read.frame.columns), len(read.frame)) == ("initial", 2, C3_HEAD, 1)


def test_missing_energy_sheets_are_empty() -> None:
    book = workbook(sheet("가상시트", {1: ["가상"]}))
    with legacy_strings():
        assert read_energy_sheet(book).how == "empty"
        assert read_energy_c3_sheet(book).how == "empty"
