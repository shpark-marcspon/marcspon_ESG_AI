"""S3C-c1b-1 C12 판매제품 폐기 — 표준화 `:7000`(셀 24) · 본 고리 `:6170-6188` → `calc_c12_ef_and_emission` `:8949`.
값은 손셈이고 계수는 지은 것(support `폐기물_C12`·`폐기물_C5`)이다. 처리방법 평균(`WASTE_AVG_EF` `:353`)과 FCF
(`BIOGENIC_WASTE_FCF` `:362`)는 코랩 상수.

T1 C12 손셈(코드 갈래 셋·이름 갈래·FCF·처리비중·톤/그램) · 코랩과 같은 흠(`colab_same_defect_` — `MARC-ISSUE-390`
① 처리비중 빈 칸 ② 소분류 빈 칸, 감독 보정 5 의 둘: 0% 는 없는 것·1% 는 100%) · T3 계수 시트 `폐기물_C12` ·
T4 serialize 결과가 계약(strict)·키 차례를 지남 · T5 pipeline(열쇠·처리 열·AI 부름 0 — 열쇠 단언은 S3C-c1b-2 가
C11·C14 를 더해 고침).
이름·대분류 갈래 줄은 소분류·중분류 칸에 「선택안함」·「-」 를 넣어 짓는다(빈 칸은 흠 ② 로 간다 — 감독 보정 2).
"""

from collections.abc import Sequence
from typing import Any, cast

import pandas as pd

from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.colab_157.factor_book import read_waste_c12_sheet
from esgapi.inventory.engines.scope3.colab_157.pipeline import (
    ACTIVITY_KEYS,
    ENERGY_KEYS,
    PRODUCT_KEYS,
    PRODUCT_POST_KEYS,
    PURCHASE_KEYS,
    SUPPORTED_KEYS,
    ColabRun,
    ProcessedSheet,
    run,
)
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.engines.scope3.colab_157.template import SHEET_PROCESSOR_MAP
from esgapi.inventory.tests.contracts.test_shapes import fits, typed
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    C12_MAIN,
    ColabReplies,
    FakeGeocoder,
    Value,
    activity_factor_sheets,
    c12_sheet,
    c15_sheet,
    sheet,
    waste_c12_ef_sheet,
    workbook,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, TAGS
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

SCHEMA = "scope3.colab.result@1"
AVG = {"매립": 0.175965929, "소각": 1.176142131, "재활용": 0.029390317}  # 코랩 `WASTE_AVG_EF`(:353)
EF = {  # support `폐기물_C12` (매립, 소각, 재활용)
    "91": (0.961, 0.962, 0.0963),
    "92": (0.964, 0.965, 0.0966),
    "93": (0.967, 0.968, 0.0969),
}


def run_on(template: Sequence[Sheet], factor_sheets: Sequence[Sheet] | None = None) -> ColabRun:
    sheets = (*activity_factor_sheets(), waste_c12_ef_sheet()) if factor_sheets is None else factor_sheets
    book = workbook(sheet("구매_USEPA", BOOK_ROWS), *sheets)
    mock = ColabReplies()
    result = run(workbook(*template), book, 2025, mock_client(mock), FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return result


def processed(result: ColabRun, index: int = 0) -> ProcessedSheet:
    outcome = result.sheets[index]
    assert isinstance(outcome, ProcessedSheet), outcome
    return outcome


def column(frame: pd.DataFrame, name: str) -> list[object]:
    if name not in frame.columns:
        return [None] * len(frame)
    return [None if v is None or (isinstance(v, float) and pd.isna(v)) else v for v in frame[name]]


def rows_json(result: ColabRun, index: int = 0) -> list[dict[str, Any]]:
    sheets = cast("list[dict[str, Any]]", result_to_dict(result, SCHEMA)["sheets"])
    return cast("list[dict[str, Any]]", sheets[index]["rows"])


def row(
    big: Value, mid: Value, sub: Value, name: str, qty: Value, weight: Value, unit: Value, pcts: Sequence[Value]
) -> list[Value]:
    """C12 한 줄. pcts = (재활용, 소각, 매립) — 템플릿 열 차례."""
    return ["가상국", big, mid, sub, name, qty, weight, unit, *pcts, None, None]


PAPER = ("91 | 가상 생활", "91-02 | 가상 종이", "91-02-01 | 가상 폐지 묶음")  # 생물기원 코드(폐지류)


def weighted(efs: tuple[float, float, float], lf: float, inc: float, rec: float) -> float:
    """코랩 가중 차례(매립 → 소각 → 재활용, `:9001-9006`)."""
    return 0.0 + efs[0] * lf + efs[1] * inc + efs[2] * rec


# ── T1 C12 손셈 ──

ROWS = (
    # 1 소분류 코드 + 생물기원 코드(91-02 폐지류) — 처리비중 재활용 90·소각 9·매립 9(> 1 이라 ÷100)
    row(
        "91 | 가상 생활", "91-02 | 가상 종이", "91-02-01 | 가상 폐지 묶음", "가상종이상자", 9100, 0.9, "kg", (90, 9, 9)
    ),
    # 2 소분류 「선택안함」 → 중분류(생물기원 아님)
    row("92 | 가상 사업장", "92-01 | 가상 수지", "선택안함", "가상수지용기", 9200, 0.95, "kg", (9, 9, 90)),
    # 3 중·소분류 「-」 → 대분류, 톤
    row("93 | 가상 건설", "-", "-", "가상잔재판", 93, 0.009, "ton", (9, 9, 90)),
    # 4 코드 셋 「선택안함」 → 제품명으로 `폐기물_C5`(`:653` — 소각만 「가상폐지」 줄, 매립·재활용은 평균),
    #   이름으로 폐지류
    row("선택안함", "선택안함", "선택안함", "가상폐지", 940, 0.96, "g", (9, 9, 90)),
)


def test_c12_code_name_and_big_branches_by_hand() -> None:
    result = run_on([c12_sheet("c12_판매제품폐기", *ROWS)])
    frame = processed(result).frame
    w1 = weighted(EF["91"], 0.09, 0.09, 0.9)
    w2 = weighted(EF["92"], 0.9, 0.09, 0.09)
    w3 = weighted(EF["93"], 0.9, 0.09, 0.09)
    w4 = weighted((AVG["매립"], 9.1, AVG["재활용"]), 0.9, 0.09, 0.09)
    kg = [9100 * 0.9, 9200 * 0.95, 93 * (0.009 * 1000.0), 940 * (0.96 / 1000.0)]
    assert column(frame, "배출계수") == [w1, w2, w3, w4]
    total = [kg[0] * w1 / 1000.0, kg[1] * w2 / 1000.0, kg[2] * w3 / 1000.0, kg[3] * w4 / 1000.0]
    bio1 = kg[0] * 0.09 * EF["91"][1] / 1000.0 * (1 - 0.01)  # 생물기원 = 소각 몫 × (1−FCF)
    bio4 = kg[3] * 0.09 * 9.1 / 1000.0 * (1 - 0.01)
    assert column(frame, "생물기원 CO2e(tCO2e)") == [bio1, 0.0, 0.0, bio4]
    assert column(frame, "화석기원 CO2e(tCO2e)") == [total[0] - bio1, total[1], total[2], total[3] - bio4]
    assert column(frame, "배출량(tCO2e)") == column(frame, "화석기원 CO2e(tCO2e)")  # 화석기원으로 갈음(:9013)
    assert column(frame, "화석탄소비율(FCF)") == [0.01, None, None, 0.01]
    note = "폐지류 소각: 생물기원 99% / 화석기원 1%"
    assert column(frame, "바이오매스 구분") == [note, "해당없음", "해당없음", note]
    assert column(frame, "제품명") == ["가상종이상자", "가상수지용기", "가상잔재판", "가상폐지"]
    assert column(frame, "재활용 비중(%)") == [90, 9, 9, 9]  # 「(선택)」 을 뗀 이름(:7004)


def test_c12_rows_carry_the_found_code_branch_and_biogenic_split() -> None:
    rows = rows_json(run_on([c12_sheet("c12_판매제품폐기", *ROWS)]))
    assert [r["rowId"] for r in rows] == [f"c12_판매제품폐기!{n}" for n in (3, 4, 5, 6)]
    assert {r["kind"] for r in rows} == {"product_eol"}
    assert [(r["factor"]["sheet"], r["factor"]["code"]) for r in rows] == [
        ("폐기물_C12", "91-02-01"),
        ("폐기물_C12", "92-01"),
        ("폐기물_C12", "93"),
        ("폐기물_C5", None),
    ]
    assert {(r["factor"]["title"], r["factor"]["unit"], r["factor"]["column"]) for r in rows} == {
        (None, "kgCO2eq/kg", None)
    }
    assert [(r["origin"], r["originSteps"]) for r in rows] == [
        ("rule", [{"step": "factor", "origin": "rule", "via": "code"}]),
        ("rule", [{"step": "factor", "origin": "rule", "via": "code"}]),
        ("rule", [{"step": "factor", "origin": "rule", "via": "code"}]),
        ("estimate", [{"step": "factor", "origin": "estimate", "via": "name"}]),  # 매립·재활용은 평균
    ]
    assert [r["activity"] for r in rows] == [
        {"value": repr(9100 * 0.9), "unit": "kg", "baseValue": repr(9100 * 0.9), "baseUnit": "kg", "note": None},
        {"value": repr(9200 * 0.95), "unit": "kg", "baseValue": repr(9200 * 0.95), "baseUnit": "kg", "note": None},
        {
            "value": repr(93 * 0.009),
            "unit": "ton",
            "baseValue": repr(93 * (0.009 * 1000.0)),
            "baseUnit": "kg",
            "note": None,
        },
        {
            "value": repr(940 * 0.96),
            "unit": "g",
            "baseValue": repr(940 * (0.96 / 1000.0)),
            "baseUnit": "kg",
            "note": None,
        },
    ]
    first = rows[0]
    assert first["biogenic"]["fcf"] == "0.01"
    assert first["biogenic"]["note"] == "폐지류 소각: 생물기원 99% / 화석기원 1%"
    assert first["co2e"] == first["biogenic"]["fossilCo2e"]
    assert rows[1]["biogenic"] == {
        "fossilCo2e": rows[1]["co2e"],
        "biogenicCo2e": "0.0",
        "fcf": None,
        "note": "해당없음",
    }
    assert all(r[k] is None for r in rows for k in ("match", "allocation", "product", "investment"))
    assert all(r["missing"] == [] for r in rows)


def test_c12_code_with_no_match_falls_to_the_treatment_average() -> None:
    """코드가 계수 시트에 없으면 처리방법 평균(`:765`) — via average, estimate, code null."""
    rows = (row("99 | 가상 없음", "선택안함", "선택안함", "가상물건", 900, 1, "kg", (90, 9, 9)),)
    result = run_on([c12_sheet("c12_판매제품폐기", *rows)])
    assert column(processed(result).frame, "배출계수") == [
        weighted((AVG["매립"], AVG["소각"], AVG["재활용"]), 0.09, 0.09, 0.9)
    ]
    (got,) = rows_json(result)
    assert (got["factor"]["code"], got["originSteps"]) == (
        None,
        [{"step": "factor", "origin": "estimate", "via": "average"}],
    )


def test_helper_columns_and_rows_without_required_cells_are_dropped() -> None:
    """드롭다운 보조목록 열(`|`·코드 꼴 머리)과 제품명·판매량·제품중량이 다 들지 않은 줄을 지운다(:7016-7035)."""
    main = [*C12_MAIN, "91 | 가상 보조", "91-02-01"]
    rows = {
        1: ["가상 안내"],
        2: main,
        3: [*ROWS[0], None, "가상"],
        4: ["가상국", None, None, None, "가상빈줄", None, 0.9],
    }
    result = run_on([sheet("c12_판매제품폐기", rows)])
    frame = processed(result).frame
    assert "91 | 가상 보조" not in frame.columns
    assert "91-02-01" not in frame.columns
    assert column(frame, "제품명") == ["가상종이상자"]


# ── 코랩과 같은 흠(고치지 않음 — 기대값 코랩대로, `MARC-ENT-442`) ──


def test_colab_same_defect_empty_shares_blank_the_factor_and_fossil() -> None:
    """흠 ①(`MARC-ISSUE-390`): 처리비중 빈 칸은 NaN 이라 None 이 아니다 — 셋 다 비어도 평균 갈래(:8998)로 안 가고
    계수·배출량·화석기원이 빈다. 소각 비중이 있으면 생물기원만 남는다."""
    rows = (
        row(*PAPER, "가상종이봉투", 950, 0.99, "g", (None, None, None)),
        row(*PAPER, "가상종이컵", 960, 0.9, "kg", (90, 9, None)),
    )
    result = run_on([c12_sheet("c12_판매제품폐기", *rows)])
    frame = processed(result).frame
    assert column(frame, "배출계수") == [None, None]
    assert column(frame, "배출량(tCO2e)") == [None, None]
    assert column(frame, "화석기원 CO2e(tCO2e)") == [None, None]
    assert column(frame, "생물기원 CO2e(tCO2e)") == [None, 960 * 0.9 * 0.09 * EF["91"][1] / 1000.0 * (1 - 0.01)]
    assert column(frame, "화석탄소비율(FCF)") == [0.01, 0.01]
    first, second = rows_json(result)
    assert (first["factor"]["value"], first["co2e"], first["missing"]) == (None, None, ["factorValue"])
    assert second["missing"] == ["factorValue"]


def test_colab_same_defect_empty_sub_code_reads_nan_and_takes_the_average() -> None:
    """흠 ②: 소분류 칸이 비면(중·대분류 값과 상관없이) 코드가 글 「nan」 — 소분류 「nan」 을 찾다 처리방법 평균,
    생물기원 해당없음(:8941·:9016). 중분류 91-02 는 생물기원 코드인데도."""
    rows = (row("91 | 가상 생활", "91-02 | 가상 종이", None, "가상종이블록", 97, 0.9, "kg", (9, 9, 90)),)
    result = run_on([c12_sheet("c12_판매제품폐기", *rows)])
    frame = processed(result).frame
    ef = weighted((AVG["매립"], AVG["소각"], AVG["재활용"]), 0.9, 0.09, 0.09)
    assert column(frame, "배출계수") == [ef]
    assert column(frame, "배출량(tCO2e)") == [97 * 0.9 * ef / 1000.0]
    assert column(frame, "바이오매스 구분") == ["해당없음"]
    (got,) = rows_json(result)
    assert (got["factor"]["code"], got["origin"], got["originSteps"][0]["via"]) == (None, "estimate", "average")


def test_colab_same_defect_zero_percent_is_no_share() -> None:
    """감독 보정 5: 처리비중 `or`(:8973)로 0 은 없는 것 — 셋 다 0 이면 세 평균의 평균(:8998), 생물기원 안 나눔."""
    rows = (
        row("91 | 가상 생활", "91-02 | 가상 종이", "91-02-01 | 가상 폐지 묶음", "가상종이판", 900, 1, "kg", (0, 0, 0)),
    )
    result = run_on([c12_sheet("c12_판매제품폐기", *rows)])
    frame = processed(result).frame
    ef = (AVG["매립"] + AVG["소각"] + AVG["재활용"]) / 3
    assert column(frame, "배출계수") == [ef]
    assert column(frame, "바이오매스 구분") == ["해당없음"]
    (got,) = rows_json(result)
    assert (got["factor"]["code"], got["originSteps"]) == (
        None,
        [{"step": "factor", "origin": "estimate", "via": "average"}],
    )


def test_colab_same_defect_one_percent_is_the_whole() -> None:
    """감독 보정 5: `_pct`(:8968)는 1 이하를 비율로 본다 — 1% 가 100%."""
    rows = (
        row(
            "92 | 가상 사업장",
            "92-01 | 가상 수지",
            "92-01-01 | 가상 폐수지 묶음",
            "가상수지판",
            900,
            1,
            "kg",
            (0, 0, 1),
        ),
    )
    result = run_on([c12_sheet("c12_판매제품폐기", *rows)])
    assert column(processed(result).frame, "배출계수") == [0.0 + EF["92"][0] * 1]


# ── T3 계수 시트 ──


def test_waste_c12_sheet_reads_twice_and_keeps_codes_as_text() -> None:
    read = read_waste_c12_sheet(workbook(waste_c12_ef_sheet()))
    assert (read.sheet, read.how, read.header) == ("폐기물_C12", "reloaded", 1)
    assert read.frame["대분류\n코드"].tolist() == ["91", "92", "93"]  # str_cols — 수로 바꾸지 않음
    assert read.frame["소분류\n코드"].tolist() == ["91-02-01", "92-01-01", "93-01-01"]
    assert read.frame["매립 EF\n(kgCO2eq/kg)"].tolist() == [0.961, 0.964, 0.967]
    assert read_waste_c12_sheet(workbook(sheet("가상", {1: ["가상"]}))).how == "empty"


def test_factor_sheets_are_eight_with_waste_c12_last() -> None:
    result = run_on([c12_sheet()])
    assert [s.sheet for s in result.factor_sheets] == [
        "운송_Spend", "출장_Spend", "폐기물_C5", "운송", "출장_통근", "에너지", "에너지_C3", "폐기물_C12",
    ]  # fmt: skip
    assert (result.factor_sheets[-1].how, result.factor_sheets[-1].header) == ("reloaded", 1)


def test_without_the_waste_c12_sheet_codes_fall_to_the_average() -> None:
    result = run_on([c12_sheet()], factor_sheets=activity_factor_sheets())
    assert column(processed(result).frame, "배출계수") == [
        weighted((AVG["매립"], AVG["소각"], AVG["재활용"]), 0.09, 0.09, 0.9)
    ]
    assert result.factor_sheets[-1].how == "empty"


# ── T4 결과 꼴 · T5 pipeline ──


def test_serialized_product_rows_fit_the_contract_and_its_key_order() -> None:
    data = result_to_dict(run_on([c12_sheet("c12_판매제품폐기", *ROWS), c15_sheet()]), SCHEMA)
    shapes.RESULT_SHAPES[SCHEMA].validate_python(data, strict=True)
    assert fits(data, typed(shapes.Scope3ColabDone)) == []
    rows = [r for s in cast("list[dict[str, Any]]", data["sheets"]) for r in s["rows"]]
    assert [r["kind"] for r in rows] == ["product_eol"] * 4 + ["investment"]


def test_product_keys_are_their_own_set_and_no_sheet_stays_unsupported() -> None:
    """S3C-c1b-2 뒤: C11·C14 는 따로 둔 `PRODUCT_POST_KEYS` 이고 21키가 다 지원된다."""
    assert frozenset({"c12", "c15"}) == PRODUCT_KEYS
    assert frozenset({"c11", "c14"}) == PRODUCT_POST_KEYS
    assert SUPPORTED_KEYS == PURCHASE_KEYS | ACTIVITY_KEYS | ENERGY_KEYS | PRODUCT_KEYS | PRODUCT_POST_KEYS
    assert not (PRODUCT_KEYS | PRODUCT_POST_KEYS) & (PURCHASE_KEYS | ACTIVITY_KEYS | ENERGY_KEYS)
    left = sorted(p.key for p in SHEET_PROCESSOR_MAP.values() if p.key not in SUPPORTED_KEYS)
    assert left == []


def test_c12_and_c15_call_no_ai() -> None:
    result = run_on([c12_sheet("c12_판매제품폐기", *ROWS), c15_sheet()])
    assert result.llm_calls.by_prompt == {}


# ── 검증 권고 R2(10-27): 대분류 코드 + 생물기원 낱말 제품명 ──


def test_a_big_code_keeps_the_product_name_out_of_the_biogenic_group() -> None:
    """코드가 대분류뿐이면 생물기원 그룹은 코드 접두로도(중·소분류 없음) 제품명으로도(`not big` :9010) 고르지 않는다 —
    「종이」 가 든 이름이어도 해당없음."""
    rows = (row("91 | 가상 생활", "선택안함", "선택안함", "가상종이상자", 900, 1, "kg", (90, 9, 9)),)
    result = run_on([c12_sheet("c12_판매제품폐기", *rows)])
    frame = processed(result).frame
    ef = weighted(EF["91"], 0.09, 0.09, 0.9)
    assert column(frame, "배출계수") == [ef]
    assert column(frame, "생물기원 CO2e(tCO2e)") == [0.0]
    assert column(frame, "화석기원 CO2e(tCO2e)") == [900 * 1.0 * ef / 1000.0]
    assert column(frame, "바이오매스 구분") == ["해당없음"]
    (got,) = rows_json(result)
    assert (got["factor"]["code"], got["originSteps"][0]["via"]) == ("91", "code")
