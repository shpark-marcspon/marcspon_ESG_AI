"""S4 폐기물 손셈(C5) — `pipeline.run` 으로 시트를 돌려 줄마다 코랩을 손으로 따라 센 값과 견준다.

코랩 줄(읽기판): 표준화 `standardize_c5_sheet`(`:5198` — 「연간처리량」 → 「처리량」) + `_melt_monthly_or_annual`
(`:4858`: 「처리량」 이 이미 열이라 `melt(value_name="처리량")` 이 ValueError → 녹이지 않은 월별 줄, 월별 줄이 먼저
`:4900-4914`) →
갈래 `:6110-6147`(`_sum_monthly` `:5928` 로 월 합, 단위 `_safe_text(row.get("단위") or "kg")` → `convert_to_base_unit`
`:3997`(규칙 `_WEIGHT_TO_KG` `:3683` → AI 배수 `:3809` → 1:1), 계수 `lookup_waste_ef` `:653`(정확 → 부분 → 키워드 →
처리방법 무시 → 처리방법 평균 `WASTE_AVG_EF` `:353`), 생물기원 `biogenic_fossil_split(emission, emission, group)`
`:395-416`: 생물기원 = 소각 × (1−FCF), 화석기원 = 전체 − 생물기원, 배출량(tCO2e) = 화석기원).
배출량 = 처리량 × 단위 배수 × EF / 1000. 평균 계수·FCF 는 코랩 상수 값이다(우리가 원천을 확인하지 않았다 —
constants.py).
"""

from esgapi.inventory.engines.scope3.colab_157.constants import WASTE_AVG_EF
from esgapi.inventory.engines.scope3.colab_157.pipeline import ProcessedSheet
from esgapi.inventory.tests.engines.scope3.colab_157.support import Value, sheet
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import (
    Replies,
    activity_metas,
    column,
    processed,
    run_sheets,
)

W_HEAD: list[Value] = ["폐기물 종류", "처리방법", "매칭 키워드", "배출계수 (kgCO2eq/kg)"]
W_ROWS: dict[int, list[Value]] = {
    1: ["가상 폐기물 계수 표"],
    3: W_HEAD,
    4: ["가상폐지", "소각", "가상골판지", 9.31],
    5: ["가상폐지", "재활용", "가상골판지", 9.32],
    6: ["가상폐수지", "매립", "가상수지찌꺼기", 9.34],
    7: ["가상음식물", "소각", "가상잔반통", 9.35],
}
C5_HEAD: list[Value] = ["*사업장", "*폐기물 종류", "*처리방법", "단위", "연간 입력", "월별 처리량", None]
C5_SUB: list[Value] = [None, None, None, None, "연간처리량", "1월", "2월"]
EF_COLUMN = "배출계수 (kgCO2eq/kg)"


def waste(*rows: list[Value], mock: Replies | None = None) -> ProcessedSheet:
    template = sheet("c5_사업장폐기물", {4: C5_HEAD, 5: C5_SUB, **{6 + i: row for i, row in enumerate(rows)}})
    (outcome,) = run_sheets([template], [sheet("폐기물_C5", W_ROWS)], mock=mock)
    return processed(outcome)


def steps(done: ProcessedSheet) -> list[list[tuple[str, str, str]]]:
    return [[(s.step, s.origin, s.via) for s in m.steps] for m in activity_metas(done)]


def test_factor_lookup_steps_and_averages() -> None:
    """정확 · 부분 · 키워드 · 처리방법 무시 · 처리방법 평균 · 처리방법 없음 → 소각 평균 · 「기타」 → 계수 없음."""
    done = waste(
        ["가상사업장", "가상폐지", "소각", "kg", 9100],
        ["가상사업장", "가상폐", "소각", "kg", 9200],  # 소각 줄 가운데 「가상폐」 를 품은 첫 줄(가상폐지)
        ["가상사업장", "가상골판지 묶음", "재활용", "kg", 9300],  # 키워드 「가상골판지」
        ["가상사업장", "가상폐수지", "소각", "kg", 9400],  # 소각 줄에 없음 → 전체에서 부분 일치(매립 줄)
        ["가상사업장", "가상무엇", "재활용", "kg", 9500],  # 안 걸림 → 재활용 평균
        ["가상사업장", "가상무엇", None, "kg", 9600],  # 처리방법 없음 → 소각 평균
        ["가상사업장", "가상무엇", "기타", "kg", 9700],  # 평균 표에 「기타」 없음 → None
    )
    frame = done.frame
    assert column(frame, "처리량") == [9100.0, 9200.0, 9300.0, 9400.0, 9500.0, 9600.0, 9700.0]
    efs = [9.31, 9.31, 9.32, 9.34, WASTE_AVG_EF["재활용"], WASTE_AVG_EF["소각"], None]
    assert column(frame, "배출계수(kgCO2eq/kg)") == efs
    assert WASTE_AVG_EF["재활용"] == 0.029390317 and WASTE_AVG_EF["소각"] == 1.176142131
    assert column(frame, "처리방법_정규화") == ["소각", "소각", "재활용", "소각", "재활용", None, "기타"]
    # 생물기원: 가상폐지·가상폐(「폐지」 아님 — 그룹 없음) 소각만 본다. 가상폐지 소각은 폐지류 FCF 0.01.
    total = [9100 * 9.31 / 1000, 9200 * 9.31 / 1000, 9300 * 9.32 / 1000, 9400 * 9.34 / 1000,
             9500 * 0.029390317 / 1000, 9600 * 1.176142131 / 1000]  # fmt: skip
    bio0 = total[0] * (1 - 0.01)
    assert column(frame, "생물기원 CO2e(tCO2e)") == [bio0, 0.0, 0.0, 0.0, 0.0, 0.0, None]
    assert column(frame, "화석기원 CO2e(tCO2e)") == [total[0] - bio0, *total[1:], None]
    assert column(frame, "배출량(tCO2e)") == column(frame, "화석기원 CO2e(tCO2e)")
    assert column(frame, "바이오매스 구분") == ["폐지류 소각: 생물기원 99% / 화석기원 1%", *["해당없음"] * 5, None]
    assert steps(done) == [
        [("unit", "rule", "rule"), ("factor", "rule", "exact")],
        [("unit", "rule", "rule"), ("factor", "rule", "partial")],
        [("unit", "rule", "rule"), ("factor", "rule", "keyword")],
        [("unit", "rule", "rule"), ("factor", "rule", "any_treatment")],
        [("unit", "rule", "rule"), ("factor", "estimate", "treatment_average")],
        [("unit", "rule", "rule"), ("factor", "estimate", "treatment_average")],
        [("unit", "rule", "rule")],  # 「기타」: factor 단계 없음(serialize 가 missing: factor)
    ]
    metas = activity_metas(done)
    assert [m.origin for m in metas] == ["rule", "rule", "rule", "rule", "estimate", "estimate", None]
    assert [m.factor.column for m in metas] == [EF_COLUMN] * 4 + [None] * 3
    assert [m.treatment for m in metas] == column(frame, "처리방법_정규화")


def test_biogenic_three_cases() -> None:
    """음식물 소각 → 생물기원 100%(FCF 0) · 폐지 소각 → FCF 0.01 · 매립 → 해당없음. 화석 = 전체 − 소각 × (1−FCF)."""
    done = waste(
        ["가상사업장", "가상음식물", "소각", "kg", 9100],
        ["가상사업장", "가상폐지", "소각", "kg", 9200],
        ["가상사업장", "가상폐수지", "매립", "kg", 9300],
    )
    frame = done.frame
    food, paper, landfill = 9100 * 9.35 / 1000, 9200 * 9.31 / 1000, 9300 * 9.34 / 1000
    assert column(frame, "생물기원 CO2e(tCO2e)") == [food * (1 - 0.0), paper * (1 - 0.01), 0.0]
    assert column(frame, "화석기원 CO2e(tCO2e)") == [food - food * (1 - 0.0), paper - paper * (1 - 0.01), landfill]
    assert column(frame, "배출량(tCO2e)") == column(frame, "화석기원 CO2e(tCO2e)")
    assert column(frame, "화석탄소비율(FCF)") == [0.0, 0.01, None]
    assert column(frame, "바이오매스 구분") == [
        "음식물류 소각: 생물기원 100% / 화석기원 0%",
        "폐지류 소각: 생물기원 99% / 화석기원 1%",
        "해당없음",
    ]
    biogenic = [m.biogenic for m in activity_metas(done)]
    assert [(b.fossil, b.biogenic, b.fcf) if b else None for b in biogenic] == [
        (food - food * (1 - 0.0), food * (1 - 0.0), 0.0),
        (paper - paper * (1 - 0.01), paper * (1 - 0.01), 0.01),
        (landfill, 0.0, None),
    ]


def unit_answers(text: str) -> str | None:
    if "입력 단위: 가상포대\n" in text:
        return '{"factor": 9.5}'
    if "입력 단위: \n" in text:  # 빈 단위 버릇 — unit_raw=""
        return '{"factor": 9.0}'
    return None  # 「가상단위」: JSON 셋 · 단순 둘 모두 실패


def test_unit_rule_ai_none_and_the_empty_unit_cell() -> None:
    """ton·g 규칙 · AI 배수 · AI 실패(1:1) · 「단위」 열이 있고 칸이 빔 → NaN 이 `or "kg"` 를 이겨 ""
    → AI(unit_raw="")."""
    mock = Replies(unit_answers)
    done = waste(
        ["가상사업장", "가상폐수지", "매립", "ton", 9.1],
        ["가상사업장", "가상폐수지", "매립", "g", 9200000],
        ["가상사업장", "가상폐수지", "매립", "가상포대", 9300],
        ["가상사업장", "가상폐수지", "매립", "가상단위", 9400],
        ["가상사업장", "가상폐수지", "매립", None, 9500],
        mock=mock,
    )
    frame = done.frame
    assert column(frame, "처리량") == [9.1, 9200000.0, 9300.0, 9400.0, 9500.0]  # kg 환산 전
    assert column(frame, "단위환산비고") == [
        "ton→kg (×1000.0)",
        "g→kg (×0.001)",
        "AI 판단: 가상포대→kg (×9.5)",
        None,  # 배수 1.0 — 비고 없음
        "AI 판단: →kg (×9.0)",
    ]
    assert column(frame, "배출량(tCO2e)") == [
        9.1 * 1000.0 * 9.34 / 1000,
        9200000 * 0.001 * 9.34 / 1000,
        9300 * 9.5 * 9.34 / 1000,
        9400 * 9.34 / 1000,
        9500 * 9.0 * 9.34 / 1000,
    ]
    metas = activity_metas(done)
    assert [(m.activity.unit, m.activity.base_value, m.activity.base_unit) for m in metas] == [
        ("ton", 9.1 * 1000.0, "kg"),
        ("g", 9200000 * 0.001, "kg"),
        ("가상포대", 9300 * 9.5, "kg"),
        ("가상단위", 9400.0, "가상단위"),
        ("", 9500 * 9.0, "kg"),
    ]
    assert [[(s.origin, s.via) for s in m.steps if s.step == "unit"] for m in metas] == [
        [("rule", "rule")],
        [("rule", "rule")],
        [("ai", "ai")],
        [("estimate", "none")],
        [("ai", "ai")],
    ]
    assert [m.origin for m in metas] == ["rule", "rule", "ai", "estimate", "ai"]
    # 부름: 가상포대 JSON 1 · 가상단위 JSON 3 + 단순 2 · 빈 단위 JSON 1
    assert len(mock.texts) == 1 + 3 + 2 + 1
    assert [t.split("\n", 2)[1] for t in mock.texts if t.startswith("단위 환산")] == [
        "입력 단위: 가상포대",
        *["입력 단위: 가상단위"] * 3,
        "입력 단위: ",
    ]
    assert sum(t.startswith('"1 가상단위"는 "kg"') for t in mock.texts) == 2


def test_monthly_rows_come_first_unmelted_and_summed() -> None:
    """`melt` ValueError(「처리량」 이 이미 열) → 녹이지 않은 월별 줄이 앞, 연간 줄이 뒤. 월별 처리량 = 1월 + 2월."""
    done = waste(
        ["가상사업장", "가상폐지", "재활용", "kg", 9100],
        ["가상사업장", "가상폐지", "재활용", "kg", None, 9200, 9300],
        ["가상사업장", "가상폐수지", "매립", "kg", 9400],
    )
    frame = done.frame
    assert column(frame, "__excel_row__") == [7, 6, 8]
    assert [m.excel_row for m in activity_metas(done)] == [7, 6, 8]
    assert column(frame, "입력방식") == ["월별", "연간", "연간"]
    assert column(frame, "처리량") == [9200.0 + 9300.0, 9100.0, 9400.0]
    assert column(frame, "1월") == [9200.0, None, None]  # 녹지 않았다(발생월 열 없음)
    assert "발생월" not in frame.columns
    assert column(frame, "배출량(tCO2e)") == [(9200.0 + 9300.0) * 9.32 / 1000, 9100 * 9.32 / 1000, 9400 * 9.34 / 1000]
    assert [m.month for m in activity_metas(done)] == [None, None, None]


def test_monthly_only_and_annual_only_sheets() -> None:
    monthly = waste(
        ["가상사업장", "가상폐지", "재활용", "kg", None, 9100, 9200],
        ["가상사업장", "가상폐수지", "매립", "kg", None, None, 9300],
    )
    assert column(monthly.frame, "__excel_row__") == [6, 7]
    assert [m.excel_row for m in activity_metas(monthly)] == [6, 7]
    assert column(monthly.frame, "처리량") == [9100.0 + 9200.0, 9300.0]
    assert column(monthly.frame, "배출량(tCO2e)") == [(9100.0 + 9200.0) * 9.32 / 1000, 9300.0 * 9.34 / 1000]

    annual = waste(["가상사업장", "가상폐지", "재활용", "kg", 9100], ["가상사업장", "가상폐수지", "매립", "kg", 9200])
    assert column(annual.frame, "__excel_row__") == [6, 7]
    assert [m.excel_row for m in activity_metas(annual)] == [6, 7]
    assert column(annual.frame, "처리량") == [9100.0, 9200.0]
    assert not {"1월", "2월"} & set(annual.frame.columns)  # 연간 줄은 월 열을 지운다
    assert column(annual.frame, "배출량(tCO2e)") == [9100 * 9.32 / 1000, 9200 * 9.34 / 1000]
