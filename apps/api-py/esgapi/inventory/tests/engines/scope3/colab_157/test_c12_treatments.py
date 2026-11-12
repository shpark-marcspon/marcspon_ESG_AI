"""S3Q1 ② C12 처리방법별 보기 칸(`treatments` — 발주서 Q5~Q7). 셈에 닿지 않는 적기만이다: 줄의 co2e·factor·생물기원은
test_product_eol_sheet.py 의 손셈(이 밴드 0줄)이 그대로 재고, 여기서는 새 칸이 가중 고리가 쓴 값과 같은지만 본다.
계수는 support 의 지은 `폐기물_C12`, 템플릿 줄은 test_product_eol_sheet.py 의 짓개(row·ROWS)다.
"""

from typing import Any, cast, get_args

from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.colab_157.product import C12_TREATMENTS
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.tests.engines.scope3.colab_157.support import c12_sheet, c15_sheet
from esgapi.inventory.tests.engines.scope3.colab_157.test_product_eol_sheet import (
    AVG,
    EF,
    PAPER,
    ROWS,
    SCHEMA,
    row,
    rows_json,
    run_on,
)

SHEET = "c12_판매제품폐기"


def parts(found: dict[str, Any]) -> list[tuple[str, str | None, str | None, bool]]:
    return [(p["treatment"], p["share"], p["factor"], p["used"]) for p in found["treatments"]["parts"]]


def test_the_contract_names_the_three_treatments_in_engine_order() -> None:
    assert get_args(shapes.C12Treatment) == C12_TREATMENTS == ("매립", "소각", "재활용")


def test_code_name_and_big_rows_carry_each_treatment_share_and_factor() -> None:
    """ROWS: 코드 셋(소·중·대분류)과 제품명(폐기물_C5 — 소각만 시트, 매립·재활용은 평균). 비중은 `_pct` 뒤 0~1."""
    rows = rows_json(run_on([c12_sheet(SHEET, *ROWS)]))
    assert [r["treatments"]["branch"] for r in rows] == ["code", "code", "code", "name"]
    assert parts(rows[0]) == [
        ("매립", "0.09", repr(EF["91"][0]), True),
        ("소각", "0.09", repr(EF["91"][1]), True),
        ("재활용", "0.9", repr(EF["91"][2]), True),
    ]
    assert parts(rows[2]) == [
        ("매립", "0.9", repr(EF["93"][0]), True),
        ("소각", "0.09", repr(EF["93"][1]), True),
        ("재활용", "0.09", repr(EF["93"][2]), True),
    ]
    assert parts(rows[3]) == [
        ("매립", "0.9", repr(AVG["매립"]), True),
        ("소각", "0.09", "9.1", True),
        ("재활용", "0.09", repr(AVG["재활용"]), True),
    ]
    first, rest = repr(0.09 + 0.09 + 0.9), repr(0.9 + 0.09 + 0.09)  # used 비중의 합(엔진 차례 — 표시용)
    assert [r["treatments"]["shareTotal"] for r in rows] == [first, rest, rest, rest]


ORDER_ROW = row(
    "92 | 가상 사업장", "92-01 | 가상 수지", "92-01-01 | 가상 폐수지 묶음", "가상수지병", 900, 1, "kg", (95, 3, 2)
)
"""매립 2 · 소각 3 · 재활용 95 — float 합의 차례에 따라 끝자리가 갈리는 지은 비중(엔진 차례 0.14, 거꾸로 0.13999…)."""


def test_the_used_parts_rebuild_the_weighted_factor_in_the_engine_order() -> None:
    """가중 배출계수는 새 칸이 아니라 줄의 factor.value 다 — used 줄을 엔진 차례(매립 → 소각 → 재활용)로 다시 셈하면
    글자까지 같다(새 칸이 고리의 값 그대로라는 뜻)."""
    rows = rows_json(run_on([c12_sheet(SHEET, *ROWS, ORDER_ROW)]))
    assert rows[-1]["factor"]["value"] == repr(0.0 + EF["92"][0] * 0.02 + EF["92"][1] * 0.03 + EF["92"][2] * 0.95)
    assert rows[-1]["factor"]["value"] != repr(0.0 + EF["92"][2] * 0.95 + EF["92"][1] * 0.03 + EF["92"][0] * 0.02)
    for got in rows:
        again = 0.0
        for _, share, factor, used in parts(got):
            if used and share is not None and factor is not None:
                again += float(factor) * float(share)
        assert repr(again) == got["factor"]["value"]


def test_a_treatment_without_a_share_is_not_used() -> None:
    """소각 비중만 빈 칸 0(없는 것 — `or`): 그 처리방법은 used false·share null, 합은 남은 둘."""
    rows = (row("92 | 가상 사업장", "92-01 | 가상 수지", "선택안함", "가상수지통", 900, 1, "kg", (50, 0, 50)),)
    (got,) = rows_json(run_on([c12_sheet(SHEET, *rows)]))
    assert parts(got) == [
        ("매립", "0.5", repr(EF["92"][0]), True),
        ("소각", None, repr(EF["92"][1]), False),
        ("재활용", "0.5", repr(EF["92"][2]), True),
    ]
    assert got["treatments"]["shareTotal"] == "1.0"


def test_no_share_at_all_is_the_average_branch_with_the_treatment_averages() -> None:
    """Q7: 비중이 하나도 없으면(0 셋) 세 평균의 평균 — parts 는 처리방법 평균·share null·used false, 합 null."""
    rows = (row(*PAPER, "가상종이판", 900, 1, "kg", (0, 0, 0)),)
    (got,) = rows_json(run_on([c12_sheet(SHEET, *rows)]))
    assert got["treatments"] == {
        "branch": "average",
        "shareTotal": None,
        "parts": [
            {"treatment": "매립", "share": None, "factor": repr(AVG["매립"]), "used": False},
            {"treatment": "소각", "share": None, "factor": repr(AVG["소각"]), "used": False},
            {"treatment": "재활용", "share": None, "factor": repr(AVG["재활용"]), "used": False},
        ],
    }
    assert got["factor"]["value"] == repr((AVG["매립"] + AVG["소각"] + AVG["재활용"]) / 3)


def test_a_code_that_finds_nothing_is_the_average_branch_with_shares() -> None:
    """코드가 시트에 없으면 처리방법 평균으로 가중 — branch average, 비중은 그대로 실린다."""
    rows = (row("99 | 가상 없음", "선택안함", "선택안함", "가상물건", 900, 1, "kg", (90, 9, 9)),)
    (got,) = rows_json(run_on([c12_sheet(SHEET, *rows)]))
    assert got["treatments"]["branch"] == "average"
    assert parts(got) == [
        ("매립", "0.09", repr(AVG["매립"]), True),
        ("소각", "0.09", repr(AVG["소각"]), True),
        ("재활용", "0.9", repr(AVG["재활용"]), True),
    ]


def test_colab_same_defect_an_empty_share_cell_stays_nan_and_blanks_the_weighted_factor() -> None:
    """MARC-ISSUE-390 흠 ① 그대로(고치지 않음): 빈 비중 칸은 NaN 이라 used true·share null, 합도 NaN → null,
    가중(factor.value)도 null. 칸이 있다고 수가 바뀌지 않는다."""
    rows = (row(*PAPER, "가상종이컵", 960, 0.9, "kg", (90, 9, None)),)
    (got,) = rows_json(run_on([c12_sheet(SHEET, *rows)]))
    assert parts(got) == [
        ("매립", None, repr(EF["91"][0]), True),
        ("소각", "0.09", repr(EF["91"][1]), True),
        ("재활용", "0.9", repr(EF["91"][2]), True),
    ]
    assert (got["treatments"]["shareTotal"], got["factor"]["value"], got["co2e"]) == (None, None, None)


def test_rows_without_a_factor_and_c15_rows_have_no_treatments_key() -> None:
    """판매량이 수가 아니면 factor null — treatments 키 없음. C15(investment)도 없음. 키는 input 바로 앞."""
    rows = (*ROWS[:1], row("91 | 가상 생활", "-", "-", "가상빈판", "가상", 1, "kg", (90, 9, 9)))
    data = result_to_dict(run_on([c12_sheet(SHEET, *rows), c15_sheet()]), SCHEMA)
    shapes.RESULT_SHAPES[SCHEMA].validate_python(data, strict=True)
    every = [r for s in cast("list[dict[str, Any]]", data["sheets"]) for r in s["rows"]]
    assert ["treatments" in r for r in every] == [True, False, False]
    assert list(every[0])[-2:] == ["treatments", "input"]
