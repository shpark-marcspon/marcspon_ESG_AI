"""S5 회사별 매핑(C5) — `pipeline.run` 으로 C5 시트를 돌려 `_fill_missing_from_company_mapping`(`:6326-6370`, 부름
`:5978`)이 「폐기물 종류」 의 **빈 칸만** 「상세폐기물명」 으로 채우는지 본다.

코랩은 입력 파일을 openpyxl(`data_only=True`)로 다시 열어 `기업정보!C7`(고른 회사)과 `회사별_폐기물매핑`(2행부터 A 회사·
B 상세명·C 값)을 읽는다 — 여기서는 템플릿 `Workbook` 의 칸(수식 칸은 저장된 값). 시트가 없음·회사가 다름·C7 이 빔이면
그대로다. 빈 칸이 그대로면 `row.get("폐기물 종류") or row.get("상세폐기물명")` 에서 NaN 이 이겨 폐기물 이름이 ""
— 계수를 찾지 않는다(코랩 그대로).
"""

from esgapi.inventory.engines.scope3.colab_157.pipeline import ProcessedSheet
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, formula, sheet, sheet_cells
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import (
    activity_metas,
    column,
    processed,
    run_sheets,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_waste_sheet import W_ROWS
from esgapi.inventory.tools.scope3_sheets.grid import Cell, Sheet

C5_HEAD: list[Value] = [
    "*사업장",
    "*폐기물 종류",
    "상세 폐기물명(선택)",
    "*처리방법",
    "단위",
    "연간 입력",
    "월별 처리량",
]
C5_SUB: list[Value] = [None, None, None, None, None, "연간처리량", "1월"]
C5 = sheet(
    "c5_사업장폐기물",
    {
        4: C5_HEAD,
        5: C5_SUB,
        6: ["가상사업장", None, "가상 사무 종이", "소각", "kg", 9100],  # 빈 칸 → 매핑
        7: ["가상사업장", "가상폐수지", "가상 사무 종이", "매립", "kg", 9200],  # 찬 칸 → 그대로
        8: ["가상사업장", None, "가상 모르는 것", "소각", "kg", 9300],  # 매핑에 없음 → 빈 채로
    },
)
MAPPING_ROWS: dict[int, list[Value]] = {
    1: ["회사", "상세명", "폐기물 종류"],
    2: ["가상회사", "가상 사무 종이", None],  # C 칸은 아래 수식 칸(저장된 값 「가상폐지」)
    3: ["가상다른회사", "가상 사무 종이", "가상잔반"],
}
MAPPING = sheet_cells("회사별_폐기물매핑", MAPPING_ROWS, {"C2": formula("가상폐지")})


def company(c7: Cell | None) -> Sheet:
    return sheet_cells("기업정보", {1: ["가상 기업정보"]}, {"C7": c7} if c7 is not None else {})


def c5_with(*extra: Sheet) -> ProcessedSheet:
    outcomes = run_sheets([*extra, C5], [sheet("폐기물_C5", W_ROWS)])
    return processed(outcomes[-1])


def test_only_blank_cells_are_filled_from_the_mapping() -> None:
    """`기업정보!C7` 도 수식 칸(저장된 값 「가상회사」), 매핑 값 칸은 수식 칸(저장된 값 「가상폐지」)."""
    done = c5_with(company(formula("가상회사")), MAPPING)
    frame = done.frame
    assert column(frame, "폐기물 종류") == ["가상폐지", "가상폐수지", None]
    assert column(frame, "배출계수(kgCO2eq/kg)") == [9.31, 9.34, None]
    total = 9100 * 9.31 / 1000
    assert column(frame, "배출량(tCO2e)") == [total - total * (1 - 0.01), 9200 * 9.34 / 1000, None]
    assert [[(s.step, s.origin, s.via) for s in m.steps] for m in activity_metas(done)] == [
        [("mapping", "rule", "company_mapping"), ("unit", "rule", "rule"), ("factor", "rule", "exact")],
        [("unit", "rule", "rule"), ("factor", "rule", "exact")],
        [("unit", "rule", "rule")],  # 이름 "" → 계수를 찾지 않음
    ]


def unchanged(done: ProcessedSheet) -> None:
    assert column(done.frame, "폐기물 종류") == [None, "가상폐수지", None]
    assert column(done.frame, "배출량(tCO2e)") == [None, 9200 * 9.34 / 1000, None]
    assert not any(s.step == "mapping" for m in activity_metas(done) for s in m.steps)


def test_no_mapping_sheet_leaves_the_frame() -> None:
    unchanged(c5_with(company(formula("가상회사"))))


def test_another_company_leaves_the_frame() -> None:
    unchanged(c5_with(company(formula("가상없는회사")), MAPPING))


def test_a_blank_company_cell_leaves_the_frame() -> None:
    unchanged(c5_with(company(None), MAPPING))
    unchanged(c5_with(company(formula(None)), MAPPING))  # 저장된 값 없는 수식 칸(재계산 안 됨)
