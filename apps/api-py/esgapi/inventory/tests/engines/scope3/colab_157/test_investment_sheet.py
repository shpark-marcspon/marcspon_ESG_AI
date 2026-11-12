"""S3C-c1b-1 C15 투자 — 표준화 `:5610-5634` 가 「배출량」(단위 없는 이름) = (Scope1 + Scope2) × 지분율 / 100 을 짓고 본
고리는 `pass`(`:6192`). 계수를 쓰지 않는다(factor null·missing `factor`).

T2 C15 손셈 · 코랩과 같은 흠 ③(`colab_same_defect_` — `MARC-ISSUE-390`: 빈 칸은 `to_float(NaN) or 0` 을 지나 배출량이
빈다) · 칸 이름의 rename.
"""

from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, c15_sheet, row_input
from esgapi.inventory.tests.engines.scope3.colab_157.test_product_eol_sheet import column, processed, rows_json, run_on

ROWS: tuple[list[Value], ...] = (
    ["가상투자처A", 9.5, 910, 920, "가상 비고 1"],
    ["가상투자처B", 90, 930, 9, None],
)


def test_c15_emission_is_scope_sum_times_share_by_hand() -> None:
    frame = processed(run_on([c15_sheet("c15_투자", *ROWS)])).frame
    assert column(frame, "피투자기업명") == ["가상투자처A", "가상투자처B"]  # 「피투자기업명 (필수)」 rename
    assert column(frame, "지분율(%)") == [9.5, 90]
    assert column(frame, "배출량") == [(910.0 + 920.0) * (9.5 / 100), (930.0 + 9.0) * (90.0 / 100)]
    assert "배출량(tCO2e)" not in frame.columns  # 단위 붙은 이름은 짓지 않는다(:5630)


def test_c15_rows_carry_the_investment_and_no_factor() -> None:
    first, second = rows_json(run_on([c15_sheet("c15_투자", *ROWS)]))
    assert first == {
        "rowId": "c15_투자!3",
        "kind": "investment",
        "month": None,
        "activity": {"value": "1830.0", "unit": "tCO2eq", "baseValue": None, "baseUnit": "tCO2eq", "note": None},
        "factor": None,
        "co2e": repr((910.0 + 920.0) * (9.5 / 100)),
        "unit": "tCO2eq",
        "formula": "",
        "match": None,
        "allocation": None,
        "biogenic": None,
        "product": None,
        "investment": {"share": "9.5", "scope1": "910.0", "scope2": "920.0"},
        "origin": None,
        "originSteps": [],
        "missing": ["factor"],
        "input": row_input(name="가상투자처A"),
    }
    assert second["co2e"] == repr((930.0 + 9.0) * (90.0 / 100))


def test_colab_same_defect_empty_scope2_blanks_the_emission() -> None:
    """흠 ③: 표준화는 「빈 것은 0」 을 노리나 빈 칸은 NaN 이라 `or 0` 을 지나 배출량이 빈다(:5634). (그 열이 통째로
    비면 읽기가 열을 지워 배출량을 짓지 않는다 — 그래서 채운 줄을 하나 앞에 둔다.)"""
    result = run_on([c15_sheet("c15_투자", ROWS[0], ["가상투자처B", 90, 930, None, None])])
    assert column(processed(result).frame, "배출량") == [(910.0 + 920.0) * (9.5 / 100), None]
    _, got = rows_json(result)
    assert (got["co2e"], got["activity"]["value"], got["missing"]) == (None, None, ["amount", "factor"])
    assert got["investment"] == {"share": "90.0", "scope1": "930.0", "scope2": None}
