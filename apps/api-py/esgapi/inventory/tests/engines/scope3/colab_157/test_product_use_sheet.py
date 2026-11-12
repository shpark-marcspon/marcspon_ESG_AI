"""S3C-c1b-2 C11 판매제품 사용 — 처리 때 셀 24 `standardize_c11_sheet`(`:6961`) → 셀 25 `:7613`(매핑 칸), 최종 값은
결과 후처리(`:8898`)가 다시 부르는 셀 27 `standardize_c11_sheet`(`:8720`). 값은 손셈이고 계수는 지은 것(support
`에너지` — 전력 0.0941 kWh · 경유 0.942 L · 도시가스(LNG) 0.943 Nm³ · 천연가스(LNG) 0.944 kg).

T1 C11 손셈(수량 × 제품당 연간 사용량(계수 단위) × 수명/12 · 수명 빈 칸이면 1년 · MWh 환산 · 매핑 칸 · 처리 때
값 ≠ 후처리 뒤 값 — 단위 불일치는 「산정 보류」 · 사슬에 단위 힌트) · T3 후처리 차례(C6_·C7_·C11_·C14_ 를 결과 시트
차례 하나로 — 가짜 공급사 기록, 처리 때 C11 부름도 차례에 듦) · 후처리 예외 → 처리 때 값 · AI 배수 캐시는 C3 와 같음 ·
T4 결과 꼴 ·
T7 `MARC-ISSUE-395` 2번(후처리 환산의 맥락 = `std_name or energy_name`).
"""

from collections.abc import Mapping, Sequence
from typing import Any, cast

import pandas as pd
import pytest

from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.colab_157 import energy, pipeline, product
from esgapi.inventory.engines.scope3.colab_157.energy import EnergyConversion, EnergyLookup
from esgapi.inventory.engines.scope3.colab_157.llm import LlmContext
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, ProcessedSheet, run
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.engines.scope3.colab_157.units import UnitFactorCache
from esgapi.inventory.tests.contracts.test_shapes import fits, typed
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    C11_ROW,
    ENERGY_EF_ROWS,
    TRAVEL_SPEND_ROWS,
    FakeGeocoder,
    Value,
    activity_factor_sheets,
    annual,
    c3_sheet,
    c11_sheet,
    c14_sheet,
    commute_sheet,
    energy_annual,
    energy_factor_sheets,
    row_input,
    sheet,
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
ELEC, DIESEL = 0.0941, 0.942
# 수명 빈 칸 · MWh(계수는 kWh — 단위 힌트 MWh 라 매칭 점수 0.95) · 경유 L 90 개월
MWH_ROW: list[Value] = ["가상국", None, None, "가상제품B", 950, "전력", 0.92, "MWh", None, "가상 적요 2"]
DIESEL_ROW: list[Value] = ["가상국", "가상그룹A", None, "가상제품C", 99, "경유", 9.3, "L", 90, None]
# 휘발유 계수가 kg 단위인 `에너지`(지은 줄) — L 입력은 처리 때 그대로 곱하고 최종은 산정 보류
GASOLINE_KG_ROWS: dict[int, list[Value]] = {
    **ENERGY_EF_ROWS,
    9: ["가상 직접", "가상 이동연소", "휘발유", "kg", 9.4, 0.945],
}


def by_text(answers: Mapping[str, str]) -> Replies:
    return Replies(lambda text: next((a for key, a in answers.items() if key in text), None))


def run_on(
    template: Sequence[Sheet], mock: Replies | None = None, energy_rows: Mapping[int, list[Value]] | None = None
) -> ColabRun:
    energy_sheets = energy_factor_sheets()
    if energy_rows is not None:
        energy_sheets = (sheet("에너지", energy_rows), energy_sheets[1])
    book = workbook(
        sheet("구매_USEPA", BOOK_ROWS), *activity_factor_sheets(), transport_ef_sheet(), travel_ef_sheet(),
        sheet("출장_Spend", TRAVEL_SPEND_ROWS), *energy_sheets,
    )  # fmt: skip
    result = run(workbook(*template), book, 2025, mock_client(mock or Replies()), FakeGeocoder(), TAGS, ROUTE)
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


def unit_calls(mock: Replies) -> list[tuple[str, str]]:
    """AI 배수 부름(`scope3-colab-unit-factor@1`)마다 (입력 단위, 맥락) — 프롬프트 글에서."""
    calls: list[tuple[str, str]] = []
    for text in mock.texts:
        if "입력 단위: " not in text:
            continue
        unit = text.split("입력 단위: ", 1)[1].split("\n", 1)[0]
        context = text.split("맥락: ", 1)[1].split("\n", 1)[0] if "맥락: " in text else ""
        calls.append((unit, context))
    return calls


def fail(*_: object, **__: object) -> object:
    raise ValueError("가상 후처리 실패")


# ── T1 C11 손셈 ──


def test_c11_rows_are_the_final_values_of_the_8720_pass() -> None:
    result = run_on([c11_sheet("c11_판매제품사용", C11_ROW, MWH_ROW, DIESEL_ROW)])
    frame = processed(result).frame
    totals = [900 * 9.1 * 8.0, 950 * 920.0 * 1.0, 99 * 9.3 * 7.5]
    assert column(frame, "사용기간(년)") == [8.0, 1.0, 7.5]
    assert column(frame, "총사용량") == totals
    assert column(frame, "배출계수(kgCO2eq/단위)") == [ELEC, ELEC, DIESEL]
    assert column(frame, "EF단위") == ["kWh", "kWh", "L"]
    assert column(frame, "EF매핑명") == ["전력", "전력", "경유"]
    assert column(frame, "단위환산비고") == [None, "MWh→kWh (×1000)", None]
    assert column(frame, "배출량(tCO2e)") == [
        t * ef / 1000.0 for t, ef in zip(totals, (ELEC, ELEC, DIESEL), strict=True)
    ]
    # 매핑 칸은 처리 때(`:7613`) 값 — 단위 힌트 MWh 는 kWh 계수에 0.95
    assert column(frame, "EF매핑방식") == ["exact_raw"] * 3
    assert column(frame, "EF매핑점수") == [1.0, 0.95, 1.0]
    assert column(frame, "수명(개월)")[:2] == [96, None]  # rename(`:6970`)


def test_a_unit_unlike_the_factor_unit_is_held_only_after_the_postprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """처리 때(`:6844` `_patch_convert_energy_to_ef_unit`)는 계수 단위(kg)와 다른 L 값을 그대로 곱하고, 최종(`:8720`
    `_fix_convert_to_ef_unit`)은 산정 보류 — 처리 때 값 ≠ 후처리 뒤 값. 후처리가 실패하면 처리 때 값이 남는다."""
    row: list[Value] = ["가상국", None, None, "가상제품G", 10, "휘발유", 9.1, "L", 24, None]
    final = processed(run_on([c11_sheet("c11_판매제품사용", row)], energy_rows=GASOLINE_KG_ROWS)).frame
    assert (column(final, "총사용량"), column(final, "배출량(tCO2e)")) == ([None], [None])
    assert column(final, "단위환산비고") == ["[단위 불일치로 산정 보류: L→kg]"]
    monkeypatch.setattr(product, "calc_c11_8720", fail)
    kept = processed(run_on([c11_sheet("c11_판매제품사용", row)], energy_rows=GASOLINE_KG_ROWS)).frame
    assert column(kept, "총사용량") == [10 * 9.1 * 2.0]
    assert column(kept, "배출량(tCO2e)") == [10 * 9.1 * 2.0 * 0.945 / 1000.0]
    assert column(kept, "단위환산비고") == [None]
    assert column(kept, "EF매핑명") == ["휘발유"]  # `:7613` 매핑 칸(처리 때)


def test_the_unit_hint_reaches_the_chain_at_every_step(monkeypatch: pytest.MonkeyPatch) -> None:
    """C11 은 처리 때(`:6961`)·매핑 칸(`:7613`)·최종(`:8720`) 모두 사슬에 단위 힌트를 넘긴다(C8·C13 본 고리 `:6157` 의
    반대 — c1a T4)."""
    seen: list[tuple[object, object]] = []
    original = product.lookup_energy_ef

    def spy(db: pd.DataFrame, energy_name: object, unit_hint: object = None) -> EnergyLookup:
        seen.append((energy_name, unit_hint))
        return original(db, energy_name, unit_hint=unit_hint)

    monkeypatch.setattr(product, "lookup_energy_ef", spy)
    run_on([c11_sheet("c11_판매제품사용", MWH_ROW)])
    # 처리 때(`:6961`·`:7613`) · 최종(`:8720`) · 채운 템플릿의 커서 표준화(`:9382` — `std_fn` 이 `:7613` 판이라
    # `:6961`·매핑 칸을 다시)
    assert seen == [("전력", "MWh")] * 5


def test_c11_row_json_carries_product_match_and_the_converted_use() -> None:
    (row,) = rows_json(run_on([c11_sheet("c11_판매제품사용", MWH_ROW)]))
    total = 950 * 920.0
    assert row == {
        "rowId": "c11_판매제품사용!3",
        "kind": "product_use",
        "month": None,
        "activity": {
            "value": "0.92", "unit": "MWh", "baseValue": "920.0", "baseUnit": "kWh", "note": "MWh→kWh (×1000)",
        },
        "factor": {
            "sheet": "에너지", "title": "전력", "value": "0.0941", "unit": "kWh", "column": "CO2eq ★\n(kgCO2eq/단위)",
            "code": None,
        },
        "co2e": repr(total * ELEC / 1000.0),
        "unit": "tCO2eq",
        "formula": "",
        "match": {"type": "exact_raw", "score": "0.95"},
        "allocation": None,
        "biogenic": None,
        "product": {"years": "1.0", "totalUsage": repr(total)},
        "investment": None,
        "origin": "rule",
        "originSteps": [
            {"step": "unit", "origin": "rule", "via": "rule"},
            {"step": "factor", "origin": "rule", "via": "exact_raw"},
        ],
        "missing": [],
        "input": row_input(country="가상국", name="가상제품B", energy="전력", productCount="950.0", useMonths=None),
    }  # fmt: skip


def test_c11_input_use_months_is_the_months_cell_and_activity_stays_the_raw_use() -> None:
    """S3R3: `input.useMonths` = 입력 칸 수명(개월)(96 → "96.0", 빈 칸 → null) · `activity.value`·`unit` 은 입력 날값
    (S3R2 Q9 — 「제품당 연간 에너지 사용량」 열은 activity 로 그린다)."""
    rows = rows_json(run_on([c11_sheet("c11_판매제품사용", C11_ROW, MWH_ROW, DIESEL_ROW)]))
    assert [row["input"]["useMonths"] for row in rows] == ["96.0", None, "90.0"]
    assert [(row["activity"]["value"], row["activity"]["unit"]) for row in rows] == [
        ("9.1", "kWh"), ("0.92", "MWh"), ("9.3", "L"),
    ]  # fmt: skip


def test_a_held_row_has_no_base_value_and_keeps_the_note() -> None:
    row: list[Value] = ["가상국", None, None, "가상제품G", 10, "휘발유", 9.1, "L", 24, None]
    (meta_row,) = rows_json(run_on([c11_sheet("c11_판매제품사용", row)], energy_rows=GASOLINE_KG_ROWS))
    assert meta_row["activity"]["value"] == "9.1"
    assert (meta_row["activity"]["baseValue"], meta_row["activity"]["note"]) == (
        None,
        "[단위 불일치로 산정 보류: L→kg]",
    )
    assert (meta_row["product"], meta_row["co2e"]) == ({"years": "2.0", "totalUsage": None}, None)


# ── T3 후처리 차례 ──


def test_postprocess_calls_follow_the_result_sheet_order() -> None:
    """결과 시트 차례 C14_ → C7_ → C11_ (템플릿 첫 처리 시트 차례): 후처리 부름이 그 차례로 섞인다(코랩 `:8887`).
    처리 때 C11 부름(날 이름 「전기」 맥락 `:6844`)은 시트 고리 안이고, 후처리 C11 부름(찾은 이름 「전력」 맥락
    `:8742`)은 lru 열쇠가 달라 또 부른다."""
    c14 = c14_sheet("c14_프랜차이즈", ["가상국", "가상가맹E", 9, "전기", 100, "가상단위B", None])
    commute = commute_sheet(
        "c7_임직원통근", annual(["가상국", "가상사업장", "가상승용차", 9, "가상시카", "가상시타", None], 99)
    )
    c11 = c11_sheet("c11_판매제품사용", ["가상국", None, None, "가상제품E", 10, "전기", 9.1, "가상와트", 24, None])
    mock = by_text({"가상와트": '{"factor": 9.9}', "가상단위B": '{"factor": 9.8}'})
    result = run_on([c14, commute, c11], mock)
    texts = mock.texts
    c11_main = next(i for i, t in enumerate(texts) if "입력 단위: 가상와트" in t and "맥락: 전기" in t)
    c14_post = next(i for i, t in enumerate(texts) if "입력 단위: 가상단위B" in t)
    city = [i for i, t in enumerate(texts) if "영어 도시명" in t and "가상시카" in t]
    c11_post = next(i for i, t in enumerate(texts) if "입력 단위: 가상와트" in t and "맥락: 전력" in t)
    assert city[0] < c11_main < c14_post < city[-1] < c11_post
    assert ("가상단위B", "전력") in unit_calls(mock)
    assert column(processed(result, 0).frame, "배출량(tCO2e)") == [(100 * 9.8) * ELEC / 1000.0]
    assert column(processed(result, 2).frame, "배출량(tCO2e)") == [10 * (9.1 * 9.9) * 2.0 * ELEC / 1000.0]


def test_the_postprocess_order_is_each_category_s_first_processed_sheet(monkeypatch: pytest.MonkeyPatch) -> None:
    """결과 시트 차례 = 코랩 `results` 에 Category 가 처음 들어간 차례(그 Category 의 첫 처리 시트 — `:6194`).
    C6-2(지출 — 후처리 기다림 없음) → C7 → C6-1 템플릿에서 C6_ 가 C7_ 보다 먼저(첫 「기다림」 시트 차례면 C7_ 먼저).
    C6 후처리는 이 입력에서 AI 를 부르지 않아 부름 기록으로는 안 보인다 — 후처리 입구 둘의 차례를 잰다(검증 B1)."""
    seen: list[str] = []
    activity_post, product_post = pipeline.postprocess_category, pipeline.postprocess_product_category

    def spy_activity(run: Any, category: str, pending: Any) -> Any:
        seen.append(category)
        return activity_post(run, category, pending)

    def spy_product(run: Any, category: str, pending: Any) -> Any:
        seen.append(category)
        return product_post(run, category, pending)

    monkeypatch.setattr(pipeline, "postprocess_category", spy_activity)
    monkeypatch.setattr(pipeline, "postprocess_product_category", spy_product)
    commute = commute_sheet(
        "c7_임직원통근", annual(["가상국", "가상사업장", "가상승용차", 9, "가상시카", "가상시타", None], 99)
    )
    trip = travel_distance_sheet("c6-1_출장거리", annual(["가상국", "가상본부", "가상버스", 9, None, None, 9.9], 9))
    c14 = c14_sheet()
    result = run_on([travel_spend_sheet(), commute, c14, trip])
    assert [o.sheet for o in result.sheets] == ["c6-2_출장비", "c7_임직원통근", "c14_프랜차이즈", "c6-1_출장거리"]
    assert seen == ["Category6", "Category7", "Category14"]


def test_a_postprocess_error_leaves_the_processing_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """C11_ 후처리 예외 → 그 결과 시트는 처리 때 값(`:8903-8905`, processed 그대로), C14_ 는 후처리 그대로."""
    monkeypatch.setattr(product, "calc_c11_8720", fail)
    row: list[Value] = ["가상국", None, None, "가상제품E", 10, "전기", 9.1, "kWh", None, None]
    result = run_on([c11_sheet("c11_판매제품사용", row), c14_sheet()])
    c11 = processed(result, 0)
    assert c11.status == "processed"
    assert column(c11.frame, "EF매핑명") == ["전력"]  # `:7613` 의 raw_name(처리 때)
    assert column(c11.frame, "배출량(tCO2e)") == [10 * 9.1 * ELEC / 1000.0]
    assert column(processed(result, 1).frame, "배출량(tCO2e)") == [9100 * DIESEL / 1000.0]


def test_c11_shares_the_unit_factor_cache_with_c3() -> None:
    """C3 의 (가상와트, kWh, 전력) 배수를 C11 후처리가 다시 묻지 않는다(코랩 lru_cache 하나 — 따를 표 5). 처리 때 C11 은
    날 이름 「전력」 이라 같은 열쇠."""
    mock = by_text({"가상와트": '{"factor": 9.9}'})
    c3 = c3_sheet("c3_연료에너지", energy_annual(["가상국", "가상사업장", "전력", "가상와트"], 9100))
    c11 = c11_sheet("c11_판매제품사용", ["가상국", None, None, "가상제품E", 10, "전력", 9.1, "가상와트", 24, None])
    result = run_on([c3, c11], mock)
    assert unit_calls(mock) == [("가상와트", "전력")]
    assert column(processed(result, 1).frame, "총사용량") == [10 * (9.1 * 9.9) * 2.0]  # 수량 × 환산값 × 연수


# ── T4 결과 꼴 ──


def test_serialized_product_use_rows_fit_the_contract_and_its_key_order() -> None:
    data = result_to_dict(run_on([c11_sheet("c11_판매제품사용", C11_ROW, MWH_ROW, DIESEL_ROW), c14_sheet()]), SCHEMA)
    shapes.RESULT_SHAPES[SCHEMA].validate_python(data, strict=True)
    assert fits(data, typed(shapes.Scope3ColabDone)) == []
    rows = [r for s in cast("list[dict[str, Any]]", data["sheets"]) for r in s["rows"]]
    assert [r["kind"] for r in rows] == ["product_use"] * 3 + ["franchise"]


# ── T7 MARC-ISSUE-395 2번: 후처리 환산의 맥락 ──


def test_the_postprocess_context_is_the_found_name_or_else_the_typed_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """`:8742` `std_name or energy_name`: 사슬이 「전기」 를 「전력」 으로 찾으면 맥락은 「전력」(프롬프트
    「맥락: 전력」 — rest 답 `expect` 와 같은 꼴), 사슬이 못 찾은 「항공유」(계수 시트·폴백 표에 없음 — std_name
    None)는 날 이름. 「nan」 글은 어느 줄에도 넘어가지 않는다(395-2 는 std_name 이 NaN 일 때만 드러남)."""
    contexts: list[str] = []
    original = energy.fix_convert_to_ef_unit

    def spy(
        context: LlmContext, cache: UnitFactorCache, value: object, input_unit: object, energy_name: str,
        ef_unit: object,
    ) -> EnergyConversion:  # fmt: skip
        contexts.append(energy_name)
        return original(context, cache, value, input_unit, energy_name, ef_unit)

    monkeypatch.setattr(product, "fix_convert_to_ef_unit", spy)
    monkeypatch.setattr(energy, "fix_convert_to_ef_unit", spy)
    mock = by_text({"가상와트": '{"factor": 9.9}', "가상리터": '{"factor": 0.5}'})
    c11 = c11_sheet(
        "c11_판매제품사용",
        ["가상국", None, None, "가상제품E", 10, "전기", 9.1, "가상와트", 24, None],
        ["가상국", None, None, "가상제품J", 10, "항공유", 9.1, "가상리터", None, None],
    )
    c14 = c14_sheet("c14_프랜차이즈", ["가상국", "가상가맹J", 9, "항공유", 100, "가상리터", None])
    result = run_on([c11, c14], mock)
    assert contexts == ["전력", "항공유", "항공유"]
    assert unit_calls(mock) == [("가상와트", "전기"), ("가상리터", "항공유"), ("가상와트", "전력")]
    assert column(processed(result, 0).frame, "EF매핑명") == ["전력", None]
    assert all(c != "nan" for _, c in unit_calls(mock))


# ── S3C-c2 검증 권고 2(S3C-r1 ⑤): 후처리 실패 = 예외뿐(빈 튜플은 실패가 아니다) ──


def post_failed_of(monkeypatch: pytest.MonkeyPatch, template: Sequence[Sheet]) -> frozenset[str]:
    seen: list[frozenset[str]] = []
    original = pipeline.build_outputs

    def spy(*args: Any) -> Any:
        seen.append(args[2])
        return original(*args)

    monkeypatch.setattr(pipeline, "build_outputs", spy)
    run_on(template)
    assert len(seen) == 1
    return seen[0]


def nothing(*_: object) -> tuple[()]:
    return ()


def test_an_empty_postprocess_is_not_a_failure_but_an_error_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """활동 갈래(C7)와 제품 갈래(C14) 둘 다: 후처리가 빈 튜플을 돌려주면 `post_failed` 가 아니고, 예외면 그렇다."""
    commute = commute_sheet(
        "c7_임직원통근", annual(["가상국", "가상사업장", "가상승용차", 9, "가상시카", "가상시타", None], 99)
    )
    template = [commute, c14_sheet()]
    assert post_failed_of(monkeypatch, template) == frozenset()
    monkeypatch.setattr(pipeline, "postprocess_category", nothing)
    monkeypatch.setattr(pipeline, "postprocess_product_category", nothing)
    assert post_failed_of(monkeypatch, template) == frozenset()
    monkeypatch.setattr(pipeline, "postprocess_category", fail)
    assert post_failed_of(monkeypatch, template) == frozenset({"Category7"})
    monkeypatch.setattr(pipeline, "postprocess_product_category", fail)
    assert post_failed_of(monkeypatch, template) == frozenset({"Category7", "Category14"})
