"""T2·T3·T5·T6·T7·T9(경계 ②) 출장·통근 거리 시트 — `pipeline.run` 으로 C6-1·C7 을 돌려 본 고리·후처리 값을
손셈과 견준다.

코랩 줄(읽기판): 갈래 C6 `:6021-6051`(거리 쪽 `:6037-6048` — 본 고리 ×2 `:6045-6046`)·C7 `:6053-6066`, 후처리
`_fix_result_c6`(`:8821`)·`_fix_result_c7`(`:8845`)는 모든 시트 뒤(`:8920`)에 결과 시트(C6_ = C6-1+C6-2 를 합친 것)마다.
계수는 support 의 지은 `출장_통근`(flight 0.921 · train 0.922 · bus 0.923 · car 0.924 · subway 0.926).
"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157 import activity
from esgapi.inventory.engines.scope3.colab_157.pipeline import SUPPORTED_KEYS, ColabRun, ProcessedSheet, run
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.engines.scope3.colab_157.template import SHEET_PROCESSOR_MAP
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    TRAVEL_MAIN,
    TRAVEL_SPEND_ROWS,
    TRAVEL_SPEND_TEMPLATE,
    TRAVEL_SUB,
    FakeGeocoder,
    Value,
    annual,
    commute_sheet,
    monthly,
    sheet,
    transport_distance_sheet,
    transport_ef_sheet,
    travel_distance_sheet,
    travel_ef_sheet,
    travel_spend_sheet,
    workbook,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, TAGS
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import Replies
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

SCHEMA = "scope3.colab.result@1"
KRW_TAXI = 9.1e-05  # support 출장_Spend 「Taxi Service」 의 2025 원화 열


def by_text(answers: Mapping[str, str]) -> Replies:
    return Replies(lambda text: next((a for key, a in answers.items() if key in text), None))


def run_on(template: Sequence[Sheet], mock: Replies | None = None) -> ColabRun:
    book = workbook(sheet("구매_USEPA", BOOK_ROWS), transport_ef_sheet(), travel_ef_sheet(), *spend_sheets())
    result = run(workbook(*template), book, 2025, mock_client(mock or Replies()), FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return result


def spend_sheets() -> list[Sheet]:
    return [sheet("출장_Spend", TRAVEL_SPEND_ROWS)]


def processed(result: ColabRun, index: int) -> ProcessedSheet:
    outcome = result.sheets[index]
    assert isinstance(outcome, ProcessedSheet), outcome
    return outcome


def cell(frame: pd.DataFrame, i: int, column: str) -> object:
    if column not in frame.columns:
        return None
    value = frame.iloc[i][column]
    return None if value is None or (isinstance(value, float) and pd.isna(value)) else value


def rows_json(result: ColabRun, index: int) -> list[dict[str, Any]]:
    sheets = cast("list[dict[str, Any]]", result_to_dict(result, SCHEMA)["sheets"])
    return cast("list[dict[str, Any]]", sheets[index]["rows"])


ROAD = {
    "출발지: 가상시가\n도착지: 가상시다\n국가 힌트: KR": '{"distance_km": 92}',
    "가상시가": "Synthetic Ga",
    "가상시다": "Synthetic Da",
}


# ── T2 C6-1 시트 ──


def test_c6_1_rows_are_the_postprocessed_values() -> None:
    rows: list[list[Value]] = [
        annual(["가상국", "가상본부", "가상버스", 9, "가상시사", "가상시아", 99], 9),  # 거리 입력
        [*annual(["가상국", "가상본부", "가상버스", 9, None, None, 99], 9), "가상 왕복"],  # 왕복 낱말 → 1
        annual(["가상국", "가상지사", "가상택시", None, "가상시가", "가상시다", None], 9.5),  # 본 고리가 거리를 채움
        monthly(["가상국", "가상지사", "가상기차", 9, None, None, 9.9], {3: 9, 7: 9}),  # 월별(먼저) — 횟수 18
        annual(["가상국", "가상지사", "가상버스", 9, None, None, None], 9),  # 거리 없음
    ]
    result = run_on([travel_distance_sheet("c6-1_출장거리", *rows)], by_text(ROAD))
    done = processed(result, 0)
    frame = done.frame
    taxi = 0.14861  # DEFRA 기본(코랩 값) — 지은 계수 책에 taxi 없음
    expected = [
        9.9 * 2 * 9 * 18.0 * 0.922 / 1000.0,
        99.0 * 2 * 9 * 9 * 0.923 / 1000.0,
        99.0 * 1 * 9 * 9 * 0.923 / 1000.0,
        92 * 1.3 * 2 * 1 * 9.5 * taxi / 1000.0,
        None,
    ]
    assert [cell(frame, i, "배출량(tCO2e)") for i in range(5)] == expected
    assert [cell(frame, i, "배출량") for i in range(5)] == expected  # 본 고리 ×2 를 후처리가 덮음(왕복 줄)
    assert [cell(frame, i, "거리왕복계수") for i in range(5)] == [2, 2, 1, 2, 2]
    assert [cell(frame, i, "이동횟수") for i in range(5)] == [18.0, 9, 9, 9.5, 9]
    assert cell(frame, 3, "이동거리(km)") == 92 * 1.3  # 본 고리가 채움
    assert cell(frame, 0, "출장비용") is None  # 월별 합(`_sum_monthly_spend`)을 후처리가 비움
    assert cell(frame, 2, "계산식") == (
        "배출량(tCO2e) = 이동거리 × 왕복계수 × 인원수 × 이동횟수 × EF / 1000 = 99 × 1 × 9 × 9 × 0.923 / 1000 = "
        f"{expected[2]:g}"
    )
    got = rows_json(result, 0)
    assert [r["kind"] for r in got] == ["travel_distance"] * 5
    assert [(r["distance"]["via"], r["distance"]["geoMode"]) for r in got] == [
        ("input", None), ("input", None), ("input", None), ("ai_straight", "road"), ("none", None),
    ]  # fmt: skip
    assert got[3]["distance"] | {"km": None} == {
        "km": None, "via": "ai_straight", "geoMode": "road", "departure": "가상시가", "arrival": "가상시다",
        "roundTrip": "2.0", "people": "1.0", "trips": "9.5", "workdays": None,
    }  # fmt: skip
    assert got[3]["origin"] == "estimate" and got[3]["factor"] == {  # 거리 ai · 계수 DEFRA 기본(estimate)
        "sheet": "출장_통근", "title": None, "value": repr(taxi), "unit": "kgCO2e/km", "column": None, "code": "taxi",
    }  # fmt: skip
    assert got[1]["activity"] == {
        "value": "9.0", "unit": "회", "baseValue": repr(99.0 * 2 * 9 * 9), "baseUnit": "pkm", "note": None,
    }  # fmt: skip
    assert (got[1]["factor"]["column"], got[1]["origin"]) == ("EF\n(kgCO2e/km)", "rule")
    assert (got[4]["missing"], got[4]["co2e"], got[4]["formula"]) == (["amount"], None, "")


def test_a_zero_factor_mode_takes_the_car_factor_as_an_estimate() -> None:
    result = run_on(
        [travel_distance_sheet("c6-1_출장거리", annual(["가상국", "가상본부", "가상 도보", 9, None, None, 9.9], 9))]
    )
    (row,) = rows_json(result, 0)
    assert row["co2e"] == repr(9.9 * 2 * 9 * 9 * 0.924 / 1000.0)
    assert (row["mode"], row["factor"]["code"], row["origin"]) == (
        {"value": "walk", "origin": "rule"},
        "walk",
        "estimate",
    )
    assert row["originSteps"][-1] == {"step": "factor", "origin": "estimate", "via": "car_fallback"}


# ── T3 C7 시트 ──

FAR = {
    "출발지: 가상시카\n도착지: 가상시타\n국가 힌트: KR": '{"distance_km": 94}',
    "가상시카": "Synthetic Ka",
    "가상시타": "Synthetic Ta",
}


def test_c7_rows_are_the_postprocessed_values() -> None:
    rows: list[list[Value]] = [
        annual(["가상국", "가상사업장A", "가상승용차", 9, "가상시카", "가상시타", None], 99),  # > 100 km 교차검증
        monthly(["가상국", "가상사업장B", "가상지하철", 9, None, None, 9.9], {1: 9, 2: 9}),  # 월별(먼저) — 18일
        annual(["가상국", "가상사업장A", "가상버스 지하철", 9, None, None, 9.9], None),  # 평균 · 245일
        annual(["가상국", "가상사업장A", "가상호텔", 9, None, None, 9.9], 99),  # 계수 없음
    ]
    result = run_on([commute_sheet("c7_임직원통근", *rows)], by_text(FAR))
    frame = processed(result, 0).frame
    avg = (0.923 + 0.926) / 2
    expected = [
        9 * 9.9 * 2 * 18.0 * 0.926 / 1000.0,
        9 * (94 * 1.3) * 2 * 99 * 0.924 / 1000.0,
        9 * 9.9 * 2 * 245 * avg / 1000.0,
        None,
    ]
    assert [cell(frame, i, "배출량(tCO2e)") for i in range(4)] == expected
    assert [cell(frame, i, "평균통근거리(km)") for i in range(4)] == [9.9, 94 * 1.3, 9.9, 9.9]
    assert [cell(frame, i, "정규화이동수단") for i in range(4)] == ["subway", "car", "bus", "lodging"]
    assert cell(frame, 1, "계산식") == (
        "배출량(tCO2e) = 평균통근거리 × 왕복계수 × 근무일수 × 직원수 × EF / 1000 = "
        f"{94 * 1.3:g} × 2 × 99 × 9 × 0.924 / 1000 = {expected[1]:g}"
    )
    got = rows_json(result, 0)
    assert [r["kind"] for r in got] == ["commute"] * 4
    assert (got[1]["distance"]["via"], got[1]["distance"]["geoMode"], got[1]["origin"]) == (
        "commute_ai_check", "road", "ai",
    )  # fmt: skip
    assert (got[0]["distance"]["workdays"], got[0]["distance"]["trips"], got[0]["activity"]["unit"]) == (
        "18.0",
        None,
        "일",
    )
    assert (got[2]["originSteps"][-1], got[2]["distance"]["workdays"]) == (
        {"step": "factor", "origin": "rule", "via": "bus_subway_avg"}, "245.0",
    )  # fmt: skip
    assert (got[3]["missing"], got[3]["origin"], got[3]["factor"]["value"]) == (["factor"], None, None)


# ── T5 합친 후처리 ──

SPEND_WITH_NOTE: dict[int, list[Value]] = {
    4: [*TRAVEL_SPEND_TEMPLATE[4], "비고(선택)"],
    5: [*TRAVEL_SPEND_TEMPLATE[5], None],
    6: ["가상사업장", None, 9300000, None, None, "가상 택시비"],
}


def test_c6_1_columns_change_a_c6_2_row_in_the_merged_postprocess() -> None:
    """C6-2 만이면 「출장수단」·「이동수단」 열이 전부 비어 지워지고 `출장항목 or 출장수단 or 이동수단 or 비고` 가 비고
    「가상 택시비」 에 닿는다(Taxi Service). C6-1 과 합치면 그 열이 남아 C6-2 줄 칸이 NaN(참) — 품목 글이 빈 글이라
    계수를 못 찾는다(배출량 None)."""
    c62 = sheet("c6-2_출장비", SPEND_WITH_NOTE)
    alone = run_on([c62])
    assert cell(processed(alone, 0).frame, 0, "배출량(tCO2e)") == 9300000 * KRW_TAXI / 1000.0
    merged = run_on([travel_distance_sheet(), c62])
    assert cell(processed(merged, 1).frame, 0, "배출량(tCO2e)") is None
    assert cell(processed(merged, 0).frame, 0, "배출량(tCO2e)") == 99.0 * 2 * 9 * 9 * 0.923 / 1000.0
    (spend,) = rows_json(merged, 1)
    assert (spend["kind"], spend["co2e"], spend["missing"]) == ("travel_spend", None, ["factor"])


def test_the_postprocess_takes_trip_people_before_head_count() -> None:
    """`_fix_result_c6` 의 인원 = `출장인원 or 인원수`(`:8827`) — 두 칸이 다른 줄(템플릿에 「출장인원」 열이 따로 있어
    표준화가 복사하지 않음)은 출장인원(검증 R1·V3, P15)."""
    head = {1: ["가상 안내"], 2: [*TRAVEL_MAIN, "출장인원"], 3: [*TRAVEL_SUB, None]}
    row = [*annual(["가상국", "가상본부", "가상버스", 9, None, None, 99], 9), None, 9.5]
    result = run_on([sheet("c6-1_출장거리", {**head, 4: row}), travel_spend_sheet()])
    assert cell(processed(result, 0).frame, 0, "배출량(tCO2e)") == 99.0 * 2 * 9.5 * 9 * 0.923 / 1000.0
    assert rows_json(result, 0)[0]["distance"]["people"] == "9.5"


def test_c6_2_alone_keeps_the_b1_values_and_calls() -> None:
    mock = by_text({})
    result = run_on([travel_spend_sheet()], mock)
    assert cell(processed(result, 0).frame, 0, "배출량(tCO2e)") == 9300000 * KRW_TAXI / 1000.0
    assert mock.texts == []


# ── T6 후처리 차례·예외 ──


def test_postprocess_runs_after_every_sheet_and_retries_the_failed_city() -> None:
    """C7 1번: 도시 정규화가 실패(캐시 안 됨) → AI 직선·실거리도 None → 본 고리 거리 None. 후처리 `calc_commute` 가 거리
    길을 다시 타 도시 정규화를 또 부른다 — **C6-1 본 고리(이동수단 AI) 뒤에**(코랩 `:8920` 차례, P9)."""
    commute = commute_sheet(
        "c7_임직원통근", annual(["가상국", "가상사업장", "가상승용차", 9, "가상시카", "가상시타", None], 99)
    )
    trip = travel_distance_sheet("c6-1_출장거리", annual(["가상국", "가상본부", "가상이동", 9, None, None, 9.9], 9))
    mock = by_text({"입력값: 가상이동": '{"mode": "train"}'})
    result = run_on([commute, trip], mock)
    texts = mock.texts
    mode_at = next(i for i, t in enumerate(texts) if "입력값: 가상이동" in t)
    city_at = [i for i, t in enumerate(texts) if "영어 도시명" in t and "가상시카" in t]
    assert city_at[0] < mode_at < city_at[-1]
    assert cell(processed(result, 0).frame, 0, "배출량(tCO2e)") is None
    assert cell(processed(result, 1).frame, 0, "배출량(tCO2e)") == 9.9 * 2 * 9 * 9 * 0.922 / 1000.0


def test_a_postprocess_error_leaves_the_main_loop_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """후처리 예외 → 그 결과 시트는 본 고리 값(R5): 왕복 줄의 「배출량」 = 본 고리 ×2
    (`if ef_val and dist_km and n_trips`),
    「배출량(tCO2e)」 은 없음. 다른 결과 시트(C7)는 후처리 그대로."""

    def boom(_: object) -> object:
        raise ValueError("가상 후처리 실패")

    monkeypatch.setattr(activity, "fix_c6_distance", boom)
    row = [*annual(["가상국", "가상본부", "가상버스", 9, None, None, 99], 9), "가상 왕복"]
    result = run_on([travel_distance_sheet("c6-1_출장거리", row), commute_sheet()])
    c6 = processed(result, 0)
    assert cell(c6.frame, 0, "배출량") == 99.0 * 2 * 0.923 * 9 * 9 / 1000  # 코랩 :6046 의 차례
    assert (cell(c6.frame, 0, "배출량(tCO2e)"), cell(c6.frame, 0, "거리왕복계수")) == (None, None)
    (meta_row,) = rows_json(result, 0)
    assert (meta_row["co2e"], meta_row["distance"]["roundTrip"]) == (None, "1.0")
    assert cell(processed(result, 1).frame, 0, "배출량(tCO2e)") == 9 * 9.9 * 2 * 99 * 0.924 / 1000.0


# ── T7 pipeline·결과 꼴 ──


def test_c6_1_and_c7_are_supported_and_the_travel_factor_sheet_is_reported() -> None:
    assert {"c6_dist", "c7"} <= SUPPORTED_KEYS
    assert sorted(k for k, p in SHEET_PROCESSOR_MAP.items() if p.key not in SUPPORTED_KEYS) == []  # S3C-c1b-2 뒤
    data = result_to_dict(run_on([travel_distance_sheet(), commute_sheet()]), SCHEMA)
    sheets = cast("list[dict[str, Any]]", data["factorSheets"])
    assert next(s for s in sheets if s["sheet"] == "출장_통근") == {
        "sheet": "출장_통근",
        "read": "initial",
        "header": 1,
        "rows": 5,
    }


# ── T9 덧붙임 1·2 ──


def test_rows_that_never_called_the_distance_way_have_no_geo_mode() -> None:
    """출발·도착 빈칸(C4-1·C6-1)과 NaN 거리 칸 — 거리 길을 안 불렀으니 geoMode null(덧붙임 1, P13)."""
    no_way = annual(["가상국", "가상사업장", "가상트럭", "가상 길없음", "ton", None, None, None], 9.1)
    c6 = annual(["가상국", "가상본부", "가상버스", 9, None, None, None], 9)
    result = run_on([transport_distance_sheet("c4-1_운송거리", no_way), travel_distance_sheet("c6-1_출장거리", c6)])
    assert [(r["distance"]["via"], r["distance"]["geoMode"]) for i in (0, 1) for r in rows_json(result, i)] == [
        ("none", None), ("none", None),
    ]  # fmt: skip


def test_a_template_distance_equal_to_a_main_loop_value_is_input() -> None:
    """같은 수라도 칸에서 집은 값은 input, 본 고리가 채운 값은 그 길(덧붙임 2) — C4-1·C6-1 둘 다."""
    km = 92 * 1.3
    c4 = [
        annual(["가상국", "가상사업장", "가상트럭", "가상 채움", "ton", "가상시가", "가상시다", None], 9.1),
        annual(["가상국", "가상사업장", "가상트럭", "가상 같은수", "ton", "가상시가", "가상시다", km], 9.1),
    ]
    c6 = [
        annual(["가상국", "가상본부", "가상버스", 9, "가상시가", "가상시다", None], 9),
        annual(["가상국", "가상본부", "가상버스", 9, "가상시가", "가상시다", km], 9),
    ]
    result = run_on(
        [transport_distance_sheet("c4-1_운송거리", *c4), travel_distance_sheet("c6-1_출장거리", *c6)], by_text(ROAD)
    )
    for i in (0, 1):
        got = rows_json(result, i)
        assert [(r["distance"]["km"], r["distance"]["via"], r["distance"]["geoMode"]) for r in got] == [
            (repr(km), "ai_straight", "road"), (repr(km), "input", None),
        ]  # fmt: skip
