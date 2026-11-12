"""D6·D7·D9 거리기반 운송 손셈(C4-1·C9-1) — `pipeline.run` 으로 시트를 돌려 줄마다 코랩을 손으로 따라 센 값과 견준다.

코랩 줄(읽기판): 표준화 `standardize_c4_dist_sheet`(`:6657`, 무게 `or` `:6685-6689`, C9 은 「출고」 `:6696`) → 갈래
`:6001-6019`(「계산방식」 Spend 면 지출, 아니면 본 고리 `get_distance_km(출발, 도착)` — road·KR 고정 `:6013`) →
`calc_transport`(`:6628`: 운송수단 → 거리 칸(검증 없음) 없으면 `infer_distance` → 무게 → `TRANSPORT_EF_MAP`).
배출량 = 거리 × (무게 kg / 1000) × EF / 1000 — 손셈은 코랩 식의 차례 그대로 적는다. 계수는 support 의 지은 `운송`
시트(road 0.911 · rail 0.913 · sea 0.914 · air 0.915, parcel 은 코랩 기본값 0.18).
"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.activity import ActivityMeta
from esgapi.inventory.engines.scope3.colab_157.pipeline import (
    ColabRun,
    FailedSheet,
    ProcessedSheet,
    SheetOutcome,
    run,
)
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    DIST_MAIN,
    DIST_ROW,
    DIST_SUB,
    FakeGeocoder,
    Value,
    annual,
    monthly,
    sheet,
    transport_distance_sheet,
    transport_ef_sheet,
    transport_spend_sheet,
    workbook,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, TAGS
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import Replies
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

SCHEMA = "scope3.colab.result@1"


def by_text(answers: Mapping[str, str]) -> Replies:
    """사용자 글에 열쇠 글이 든 첫 답(차례대로 본다). 없으면 공급사 실패."""
    return Replies(lambda text: next((a for key, a in answers.items() if key in text), None))


def run_on(template: Sequence[Sheet], mock: Replies | None = None, geocoder: FakeGeocoder | None = None) -> ColabRun:
    book = workbook(sheet("구매_USEPA", BOOK_ROWS), transport_ef_sheet())
    result = run(
        workbook(*template), book, 2025, mock_client(mock or Replies()), geocoder or FakeGeocoder(), TAGS, ROUTE
    )
    assert isinstance(result, ColabRun)
    return result


def processed(outcome: SheetOutcome) -> ProcessedSheet:
    assert isinstance(outcome, ProcessedSheet), outcome
    return outcome


def rows_json(result: ColabRun, index: int = 0) -> list[dict[str, Any]]:
    data = result_to_dict(result, SCHEMA)
    sheets = cast("list[dict[str, Any]]", data["sheets"])
    return cast("list[dict[str, Any]]", sheets[index]["rows"])


def cell(frame: pd.DataFrame, i: int, column: str) -> object:
    value = frame.iloc[i][column]
    return None if value is None or (isinstance(value, float) and pd.isna(value)) else value


def emission(km: float, kg: float, ef: float) -> float:
    return km * (kg / 1000.0) * ef / 1000.0  # 코랩 :6650-6653


# ── D6 입력 거리·무게 단위 ──

WEIGHT_ROWS: list[list[Value]] = [
    DIST_ROW,  # 4 거리 91 · ton
    annual(
        ["가상국", "가상사업장", "가상트럭", "가상 수지", "kg", "가상시가", "가상시나", 900], 9500
    ),  # 5 900 km 그대로
    annual(["가상국", "가상사업장", "가상트럭", "가상 볼트", "g", None, None, 91], 9000000),  # 6
    annual(["가상국", "가상사업장", "가상트럭", "가상 판재", "metric ton", None, None, 91], 9.2),  # 7 공백 → 표
    annual(["가상국", "가상사업장", "가상트럭", "가상 상자", None, None, None, 91], 9300),  # 8 빈 단위 → kg
    annual(["가상국", "가상사업장", "가상트럭", "가상 롤", "lb", None, None, 91], 9400),  # 9
    annual(["가상국", "가상사업장", "가상트럭", "가상 팔레트", "가상팔레트", None, None, 91], 9.5),  # 10 단위 AI 9.5
    annual(["가상국", "가상사업장", "가상트럭", "가상 묶음", "가상묶음", None, None, 91], 9.6),  # 11 단위 AI 실패 → 1배
]


def test_input_distances_and_weight_units() -> None:
    mock = by_text({"입력 단위: 가상팔레트": '{"factor": 9.5}'})
    result = run_on([transport_distance_sheet("c4-1_운송거리", *WEIGHT_ROWS)], mock)
    frame = processed(result.sheets[0]).frame
    kgs = [9.1 * 1000.0, 9500 * 1.0, 9000000 * 0.001, 9.2 * 1000.0, 9300 * 1.0, 9400 * 0.45359237, 9.5 * 9.5, 9.6 * 1.0]
    kms = [91, 900, 91, 91, 91, 91, 91, 91]
    assert [cell(frame, i, "화물중량(kg)") for i in range(8)] == kgs
    assert [cell(frame, i, "운송거리(km)") for i in range(8)] == kms  # 입력은 검증 없이 그대로(900 도)
    assert [cell(frame, i, "배출량(tCO2e)") for i in range(8)] == [
        emission(k, w, 0.911) for k, w in zip(kms, kgs, strict=True)
    ]
    assert {cell(frame, i, "배출계수(거리기반)") for i in range(8)} == {0.911}
    # 무게 AI 는 표준화에서 먼저(시트 모든 줄) — 부름은 단위 AI 뿐(b1 units 의 두 프롬프트, 실패 단위는 다시 묻는다)
    assert "입력 단위: 가상팔레트" in mock.texts[0]
    assert all("가상팔레트" in t or "가상묶음" in t for t in mock.texts) and len(mock.texts) > 1
    rows = rows_json(result)
    assert [(r["activity"]["unit"], r["originSteps"][0]["via"], r["origin"]) for r in rows] == [
        ("ton", "rule", "rule"),
        ("kg", "rule", "rule"),
        ("g", "rule", "rule"),
        ("metric ton", "rule", "rule"),
        ("kg", "rule", "rule"),
        ("lb", "rule", "rule"),
        ("가상팔레트", "ai", "ai"),
        ("가상묶음", "ai_failed", "estimate"),
    ]
    assert {(r["distance"]["via"], r["distance"]["geoMode"], r["missing"] == []) for r in rows} == {
        ("input", None, True)
    }


WEIGHT_HEAD: list[Value] = [*DIST_MAIN[:8], "화물중량(kg)", *DIST_MAIN[8:]]
WEIGHT_SUB: list[Value] = [*DIST_SUB[:8], None, *DIST_SUB[8:]]


def test_a_zero_kg_input_is_converted_again_and_a_given_weight_has_no_unit_step() -> None:
    """코랩 `_patch_to_float(화물중량) or 환산` — 0 은 거짓이라 운송량에서 다시 환산한다(결함 후보)."""
    zero = ["가상국", "가상사업장", "가상트럭", "가상 영", "ton", None, None, 91, 0, 9.3, *([None] * 12)]
    given = ["가상국", "가상사업장", "가상트럭", "가상 입력", "ton", None, None, 91, 9400, 9.9, *([None] * 12)]
    c4 = sheet("c4-1_운송거리", {1: ["가상 안내"], 2: WEIGHT_HEAD, 3: WEIGHT_SUB, 4: zero, 5: given})
    result = run_on([c4])
    frame = processed(result.sheets[0]).frame
    assert [cell(frame, i, "화물중량(kg)") for i in range(2)] == [9.3 * 1000.0, 9400.0]
    rows = rows_json(result)
    assert [[s["step"] for s in r["originSteps"]] for r in rows] == [
        ["unit", "mode", "distance", "factor"],
        ["mode", "distance", "factor"],
    ]


def test_calc_transport_converts_the_raw_cargo_weight_when_the_sheet_left_none() -> None:
    """표준화는 운송량 셋(월·연간·운송량)만 보고 None 을 남긴다 → `calc_transport` 가 넷째 열쇠 「화물중량」
    (`:6642`)으로 다시 환산한다. frame 의 「화물중량(kg)」 은 빈 채로, 배출량은 그 무게로(검증 B2)."""
    head = [*DIST_MAIN[:8], "화물중량", *DIST_MAIN[8:]]
    sub = [*DIST_SUB[:8], None, *DIST_SUB[8:]]
    raw = ["가상국", "가상사업장", "가상트럭", "가상 화물", "ton", None, None, 91, 9.1, None, *([None] * 12)]
    result = run_on([sheet("c4-1_운송거리", {1: ["가상 안내"], 2: head, 3: sub, 4: raw})])
    frame = processed(result.sheets[0]).frame
    assert cell(frame, 0, "화물중량(kg)") is None
    assert cell(frame, 0, "배출량(tCO2e)") == emission(91, 9.1 * 1000.0, 0.911)
    (row,) = rows_json(result)
    assert row["originSteps"][0] == {"step": "unit", "origin": "rule", "via": "rule"}
    assert row["activity"]["baseValue"] == repr(9.1 * 1000.0) and row["missing"] == []


def test_monthly_amounts_are_folded_and_no_amount_is_no_weight() -> None:
    rows = [
        monthly(["가상국", "가상사업장", "가상트럭", "가상 월별", "ton", None, None, 91], {2: 9.6, 8: 9.7}),
        annual(["가상국", "가상사업장", "가상트럭", "가상 없음", "ton", None, None, 91], None),
    ]
    result = run_on([transport_distance_sheet("c4-1_운송거리", *rows)])
    frame = processed(result.sheets[0]).frame
    assert cell(frame, 0, "월운송량") == 9.6 + 9.7
    assert cell(frame, 0, "화물중량(kg)") == (9.6 + 9.7) * 1000.0
    assert (cell(frame, 1, "화물중량(kg)"), cell(frame, 1, "배출량(tCO2e)"), cell(frame, 1, "배출계수(거리기반)")) == (
        None,
        None,
        None,
    )
    got = rows_json(result)[1]
    assert (got["missing"], got["activity"]["baseValue"], got["co2e"]) == (["amount"], None, None)
    assert got["factor"]["value"] == "0.911"  # 맵의 값은 싣는다(셈에 못 썼을 뿐)


def test_a_code_missing_from_the_map_is_a_missing_factor_and_a_default_code_is_an_estimate() -> None:
    rows = [
        annual(
            ["가상국", "가상사업장", "가상 벌크선", "가상 광석", "ton", None, None, 91], 9.1
        ),  # sea_bulk — 맵에 없음
        annual(["가상국", "가상사업장", "가상택배", "가상 소포", "ton", None, None, 91], 9.1),  # parcel — 기본값
    ]
    result = run_on([transport_distance_sheet("c4-1_운송거리", *rows)])
    frame = processed(result.sheets[0]).frame
    assert (cell(frame, 0, "배출계수(거리기반)"), cell(frame, 0, "배출량(tCO2e)")) == (None, None)
    assert cell(frame, 1, "배출량(tCO2e)") == emission(91, 9100.0, 0.18)
    sea_bulk, parcel = rows_json(result)
    assert (sea_bulk["missing"], sea_bulk["origin"], sea_bulk["factor"]["code"], sea_bulk["factor"]["value"]) == (
        ["factor"],
        None,
        "sea_bulk",
        None,
    )
    assert (parcel["origin"], parcel["factor"]["column"], parcel["originSteps"][-1]) == (
        "estimate",
        None,
        {"step": "factor", "origin": "estimate", "via": "default"},
    )


# ── D6 본 고리와 두 번째 길 ──

MAIN_LOOP_ROW = annual(["가상국", "가상사업장", "가상 KTX 화물", "가상 레일", "ton", "가상시가", "가상시다", None], 9.1)


def test_the_main_loop_measures_road_kr_writes_the_cell_and_keeps_its_via() -> None:
    """운송수단은 철도(rail 보정 1.2)지만 본 고리는 road(1.3)·KR 고정 — 국가 칸 「가상국」 도 안 본다(P11·P12·P17)."""
    mock = by_text(
        {
            "가상시가": "Synthetic Ga",
            "가상시다": "Synthetic Da",
        }
    )
    straight = by_text({"출발지: 가상시가\n도착지: 가상시다\n국가 힌트: KR": '{"distance_km": 92}'})
    replies = Replies(lambda text: straight.answer(text) or mock.answer(text))
    geocoder = FakeGeocoder()
    result = run_on([transport_distance_sheet("c4-1_운송거리", MAIN_LOOP_ROW)], replies, geocoder)
    frame = processed(result.sheets[0]).frame
    assert cell(frame, 0, "운송거리(km)") == 92 * 1.3
    assert cell(frame, 0, "배출량(tCO2e)") == emission(92 * 1.3, 9100.0, 0.913)
    assert geocoder.queries == ["Synthetic Ga, KR", "Synthetic Da, KR"]
    (row,) = rows_json(result)
    assert row["distance"] == {
        "km": repr(92 * 1.3),
        "via": "ai_straight",
        "geoMode": "road",
        "departure": "가상시가",
        "arrival": "가상시다",
        "roundTrip": None,
        "people": None,
        "trips": None,
        "workdays": None,
    }
    assert (row["mode"], row["origin"]) == ({"value": "rail", "origin": "rule"}, "ai")  # distance 단계가 가장 약함
    assert [s["step"] for s in row["originSteps"]] == ["unit", "mode", "distance", "factor"]


AIR_ROW = annual(["가상국", "가상사업장", "가상항공 화물", "가상 의자", "kg", "가상시파", "가상시하", None], 9100)
AIR_ANSWERS = {
    "출발지: 가상시파\n도착지: 가상시하\n국가 힌트: KR": '{"distance_km": 902}',
    "출발지: 가상시파\n도착지: 가상시하\n운송수단: 도로(트럭)": '{"distance_km": 999}',
    "지역: 가상시파": '{"airport_name": "Synthetic Pa Airport", "iata": ""}',
    "지역: 가상시하": '{"airport_name": "Synthetic Ha Airport", "iata": ""}',
    "출발지: Synthetic Pa Airport\n도착지: Synthetic Ha Airport\n국가 힌트: 가상국": '{"distance_km": 95}',
    "Synthetic Pa Airport": "Synthetic Pa Airport",
    "Synthetic Ha Airport": "Synthetic Ha Airport",
    "가상시파": "Synthetic Pa",
    "가상시하": "Synthetic Ha",
}


def test_a_main_loop_none_goes_to_the_second_way_with_the_row_country_and_leaves_the_cell_empty() -> None:
    """C9-1: 본 고리(road·KR)가 직선 902 × 1.3 > 800 · 실거리 999 > 800 으로 None → `infer_distance`(air, 「가상국」)
    공항 AI 둘 → 직선 95 × 1.09(상한 없음). 다시 구한 거리는 칸에 안 남는다(o3 물을 거리 3)."""
    mock = by_text(AIR_ANSWERS)
    geocoder = FakeGeocoder()
    result = run_on([transport_distance_sheet("c9-1_운송거리", AIR_ROW)], mock, geocoder)
    frame = processed(result.sheets[0]).frame
    km = 95 * 1.09
    assert (cell(frame, 0, "운송거리(km)"), cell(frame, 0, "운송구분")) == (None, "출고")
    assert cell(frame, 0, "배출량(tCO2e)") == emission(km, 9100.0, 0.915)
    assert geocoder.queries == [
        "Synthetic Pa, KR",
        "Synthetic Ha, KR",
        "Synthetic Pa Airport",
        "Synthetic Ha Airport",
    ]
    (row,) = rows_json(result)
    assert (row["distance"]["km"], row["distance"]["via"], row["distance"]["geoMode"]) == (
        repr(km),
        "ai_straight+airport",
        "air",
    )
    assert row["kind"] == "transport_distance" and row["missing"] == []


def test_no_places_and_no_distance_is_a_missing_amount_without_a_distance_step() -> None:
    """코랩 `infer_distance` 는 빈 거리 칸의 NaN 을 `to_float` 로 그대로 받아 검증(`<= 0` 거짓)을 지나 「input」 으로
    낸다 — 계수는 채우고 배출량은 NaN(결함 후보). 값은 코랩대로, 산정 출처는 거리 없음."""
    no_way = annual(["가상국", "가상사업장", "가상트럭", "가상 길없음", "ton", None, None, None], 9.1)
    result = run_on([transport_distance_sheet("c4-1_운송거리", no_way)])
    frame = processed(result.sheets[0]).frame
    assert (cell(frame, 0, "배출계수(거리기반)"), cell(frame, 0, "배출량(tCO2e)")) == (0.911, None)
    (row,) = rows_json(result)
    assert (row["distance"]["km"], row["distance"]["via"], row["missing"], row["co2e"]) == (
        None,
        "none",
        ["amount"],
        None,
    )
    assert "distance" not in [s["step"] for s in row["originSteps"]]


def test_a_non_dict_json_answer_fails_the_sheet() -> None:
    cart = annual(["가상국", "가상사업장", "가상수레", "가상 부속", "ton", None, None, 91], 9.1)
    result = run_on([transport_distance_sheet("c4-1_운송거리", cart)], by_text({"텍스트:": '["가상"]'}))
    assert isinstance(result.sheets[0], FailedSheet)
    assert result.sheets[0].error.startswith("AttributeError")


# ── D7 C9-1·차례·「계산방식」 ──


def test_c4_1_then_c4_2_keep_the_template_order_and_kinds() -> None:
    result = run_on([transport_distance_sheet("c4-1_운송거리"), transport_spend_sheet("c4-2_운송금액")])
    kinds = [[m.kind for m in processed(o).metas if isinstance(m, ActivityMeta)] for o in result.sheets]
    assert kinds == [["transport_distance"], ["transport_spend"]]
    assert cell(processed(result.sheets[0]).frame, 0, "운송구분") == "입고"


def test_a_spend_calculation_method_in_c4_1_goes_to_the_spend_branch() -> None:
    """C4-1 표준화는 「계산방식」 열이 있으면 그 값을 둔다(`:6690`) — Spend 줄은 지출 셈, 빈 칸은 Distance."""
    head = [*DIST_MAIN[:8], "계산방식", *DIST_MAIN[8:]]
    sub = [*DIST_SUB[:8], None, *DIST_SUB[8:]]
    spend = ["가상국", "가상사업장", "가상트럭", "가상 지출", "ton", None, None, 91, "Spend", 9.1, *([None] * 12)]
    dist = ["가상국", "가상사업장", "가상트럭", "가상 거리", "ton", None, None, 91, None, 9.1, *([None] * 12)]
    result = run_on([sheet("c4-1_운송거리", {1: ["가상 안내"], 2: head, 3: sub, 4: spend, 5: dist})])
    done = processed(result.sheets[0])
    assert [m.kind for m in done.metas if isinstance(m, ActivityMeta)] == ["transport_spend", "transport_distance"]
    assert [cell(done.frame, i, "계산방식") for i in range(2)] == ["Spend", "Distance"]
    assert cell(done.frame, 0, "배출계수(거리기반)") is None
    assert cell(done.frame, 1, "배출량(tCO2e)") == emission(91, 9100.0, 0.911)
