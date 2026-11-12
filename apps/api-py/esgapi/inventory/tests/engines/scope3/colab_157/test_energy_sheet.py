"""S3C-c1a ② 에너지 시트 갈래 — C3(`:5078` 표준화 · 본 고리 `:6070-6113`)·C8·C13(뒤 정의 표준화 `:6901`·`:6908`·
`:6949-6958` · 본 고리 `:6146-6168`). 값은 손셈이고 계수는 지은 것(support `에너지`·`에너지_C3`)이다.

T3 C3 손셈(월별 먼저·연간 뒤, 「사용량」 은 환산 전, `에너지_C3` 없음) · T4 C8·C13 손셈(산정방식 셋·비율·사슬은
단위 힌트 없이) · T5 계수 시트(새 둘은 활동 다섯 뒤에 이 차례 — 끝은 S3C-c1b-1 의 `폐기물_C12`) · T7 pipeline
(열쇠·처리 열·AI 부름 한 번) · R1 C3 가스 별칭 차례 · T6 serialize 가 낸 줄의 계약.
"""

from collections.abc import Sequence
from typing import Any, cast

import pandas as pd
import pytest

from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.colab_157 import energy
from esgapi.inventory.engines.scope3.colab_157.energy import c3_alias_candidates, lookup_energy_ef_c3
from esgapi.inventory.engines.scope3.colab_157.pipeline import (
    ACTIVITY_KEYS,
    ENERGY_KEYS,
    PURCHASE_KEYS,
    SUPPORTED_KEYS,
    ColabRun,
    ProcessedSheet,
    run,
)
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.tests.contracts.test_shapes import fits, typed
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    FakeGeocoder,
    Value,
    c3_sheet,
    energy_annual,
    energy_factor_sheets,
    energy_monthly,
    leased_sheet,
    sheet,
    workbook,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, TAGS
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import Replies
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

SCHEMA = "scope3.colab.result@1"
UNIT_PROMPT = "입력 단위: 가상와트"


def unit_replies() -> Replies:
    return Replies(lambda text: '{"factor": 9.9}' if UNIT_PROMPT in text else None)


def run_on(
    template: Sequence[Sheet], factor_sheets: Sequence[Sheet] | None = None, mock: Replies | None = None
) -> ColabRun:
    sheets = energy_factor_sheets() if factor_sheets is None else factor_sheets
    book = workbook(sheet("구매_USEPA", BOOK_ROWS), *sheets)
    result = run(workbook(*template), book, 2025, mock_client(mock or unit_replies()), FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return result


def processed(result: ColabRun, index: int) -> ProcessedSheet:
    outcome = result.sheets[index]
    assert isinstance(outcome, ProcessedSheet), outcome
    return outcome


def column(frame: pd.DataFrame, name: str) -> list[object]:
    if name not in frame.columns:
        return [None] * len(frame)
    return [None if v is None or (isinstance(v, float) and pd.isna(v)) else v for v in frame[name]]


def rows_json(result: ColabRun, index: int) -> list[dict[str, Any]]:
    sheets = cast("list[dict[str, Any]]", result_to_dict(result, SCHEMA)["sheets"])
    return cast("list[dict[str, Any]]", sheets[index]["rows"])


# ── T3 C3 ──

C3_ROWS = (
    energy_annual(["가상국", "가상사업장A", "전력", "kWh"], 9100),
    energy_monthly(["가상국", "가상사업장A", "경유", "L"], {1: 910, 2: 920}),
    energy_annual(["가상국", "가상사업장B", "전력", "가상와트"], 99),  # 단위 AI
    energy_annual(
        ["가상국", "가상사업장B", "도시가스", "Nm³"], 9300
    ),  # `에너지_C3` 에 도시가스(LNG) 없음 → 발열량 다리
)


def test_c3_monthly_rows_come_first_and_usage_stays_before_conversion() -> None:
    result = run_on([c3_sheet("c3_연료에너지", *C3_ROWS)])
    frame = processed(result, 0).frame
    assert column(frame, "에너지원") == ["경유", "전력", "전력", "도시가스"]  # 월별 먼저, 연간 뒤(따를 표 2)
    assert column(frame, "사용량") == [1830.0, 9100, 99, 9300]  # 환산 전(따를 표 3 — C3 3번 꼴)
    assert column(frame, "배출계수(kgCO2eq/단위)") == [0.0952, 0.0951, 0.0951, 0.0953]
    assert column(frame, "EF단위") == ["L", "kWh", "kWh", "kg"]
    assert column(frame, "EF매핑명") == ["경유", "전력", "전력", "천연가스(LNG)"]
    assert column(frame, "단위환산비고") == [
        None,
        None,
        "가상와트→kWh (AI 판단: ×9.9)",
        "Nm³→kg (발열량 환산: 도시가스→천연가스(LNG), ×0.779352)",
    ]
    assert column(frame, "배출량(tCO2e)") == [
        1830.0 * 0.0952 / 1000,
        9100 * 0.0951 / 1000,
        99 * 9.9 * 0.0951 / 1000,
        9300 * 38.5 / 49.4 * 0.0953 / 1000,
    ]


def test_c3_rows_carry_the_conversion_factor_and_origin() -> None:
    rows = rows_json(run_on([c3_sheet("c3_연료에너지", *C3_ROWS)]), 0)
    assert [r["rowId"] for r in rows] == ["c3_연료에너지!5", "c3_연료에너지!4", "c3_연료에너지!6", "c3_연료에너지!7"]
    assert {r["kind"] for r in rows} == {"fuel_energy"}
    ai, bridged = rows[2], rows[3]
    assert ai["activity"] == {
        "value": "99.0",
        "unit": "가상와트",
        "baseValue": repr(99 * 9.9),
        "baseUnit": "kWh",
        "note": "가상와트→kWh (AI 판단: ×9.9)",
    }
    assert ai["factor"] == {
        "sheet": "에너지_C3",
        "title": "전력",
        "value": "0.0951",
        "unit": "kWh",
        "column": "EF\n(kgCO2eq/단위)",
        "code": None,
    }
    assert (ai["origin"], ai["originSteps"]) == (
        "ai",
        [{"step": "unit", "origin": "ai", "via": "ai"}, {"step": "factor", "origin": "rule", "via": "exact_raw"}],
    )
    assert (bridged["activity"]["baseValue"], bridged["activity"]["baseUnit"]) == (repr(9300 * 38.5 / 49.4), "kg")
    assert bridged["originSteps"] == [
        {"step": "unit", "origin": "rule", "via": "lhv"},
        {"step": "factor", "origin": "rule", "via": "alias_exact"},
    ]
    assert all(r[k] is None for r in rows for k in ("match", "allocation", "biogenic", "product", "investment"))
    assert all(r["missing"] == [] for r in rows)


def test_c3_without_the_energy_c3_sheet_has_no_factor() -> None:
    """`에너지_C3` 가 없으면 코랩 `energy_c3_ef_db` 는 빈 frame — 계수·배출량이 빈다(`에너지` 시트로 넘어가지
    않는다)."""
    result = run_on([c3_sheet()], factor_sheets=energy_factor_sheets()[:1])
    frame = processed(result, 0).frame
    assert (column(frame, "배출계수(kgCO2eq/단위)"), column(frame, "배출량(tCO2e)")) == ([None], [None])
    (row,) = rows_json(result, 0)
    assert (row["factor"]["title"], row["factor"]["value"], row["co2e"]) == (None, None, None)
    assert (row["origin"], row["originSteps"], row["missing"]) == (None, [], ["factor"])
    assert next(s for s in result.factor_sheets if s.sheet == "에너지_C3").how == "empty"


# ── R1 C3 가스 별칭 차례(`_c3_energy_alias_candidates` `:9069`) ──


def test_c3_gas_aliases_put_city_gas_first_unless_the_unit_is_kg() -> None:
    assert c3_alias_candidates("LNG") == ["LNG", "도시가스(LNG)", "천연가스(LNG)"]
    assert c3_alias_candidates("LNG", "kg") == ["LNG", "천연가스(LNG)", "도시가스(LNG)"]
    db = pd.DataFrame(
        {
            "활동유형(에너지원)": ["천연가스(LNG)", "도시가스(LNG)"],
            "기준단위": ["kg", "Nm³"],
            "EF\n(kgCO2eq/단위)": [0.91, 0.92],
        }
    )
    got = lookup_energy_ef_c3(db, "LNG")  # 본 고리는 힌트 없이 부른다(`:6081`)
    assert (got.name, got.ef, got.unit, got.via) == ("도시가스(LNG)", 0.92, "Nm³", "alias_exact")


# ── T4 C8·C13 ──


def leased_template(family: str) -> list[Sheet]:
    energy_name, area_name, person_name = {
        "c8": ("c8-1_에너지사용량 아는 경우", "c8-2_면적", "c8-3_인원"),
        "c13": ("c13-1_에너지사용량 아는경우", "c13-2_면적", "c13-3_인원"),
    }[family]
    return [
        leased_sheet(
            energy_name,
            energy_annual(["가상국", "가상자산A", "전력", "kWh"], 91000),
            energy_monthly(["가상국", "가상자산A", "도시가스(LNG)", "Nm³"], {3: 930, 4: 940}),
        ),
        leased_sheet(
            area_name,
            energy_annual(["가상국", "가상자산A", 9000, 900, "경유", "L"], 9100),
            energy_monthly(["가상국", "가상자산B", 9500, 950, "전력", "kWh"], {1: 9100, 2: 9200}),
        ),
        leased_sheet(
            person_name, energy_monthly(["가상국", "가상자산B", 90, 9, "천연가스(LNG)", "kg"], {6: 960, 7: 970})
        ),
    ]


@pytest.mark.parametrize(("family", "kind"), [("c8", "leased_asset"), ("c13", "leased_out_asset")])
def test_leased_three_methods_by_hand(family: str, kind: str) -> None:
    result = run_on(leased_template(family))
    frames = [processed(result, i).frame for i in range(3)]
    joined = pd.concat(frames, ignore_index=True)  # 코랩 `:6238`
    assert column(joined, "산정방식") == ["에너지사용량", "에너지사용량", "면적배분", "면적배분", "인원배분"]
    assert column(joined, "건물전체사용량") == [None, None, 9100.0, 18300.0, 1930.0]  # 월별은 접어 합(뒤 정의)
    assert column(joined, "면적비율") == [None, None, 900 / 9000, 950 / 9500, None]
    assert column(joined, "인원비율") == [None, None, None, None, 9 / 90]
    assert column(joined, "사용량") == [91000.0, 1870.0, 9100.0 * 0.1, 18300.0 * 0.1, 1930.0 * 0.1]
    assert column(joined, "배출계수(kgCO2eq/단위)") == [0.0941, 0.943, 0.942, 0.0941, 0.944]
    assert column(joined, "EF단위") == ["kWh", "Nm³", "L", "kWh", "kg"]
    assert column(joined, "배출량(tCO2e)") == [
        91000.0 * 0.0941 / 1000,
        1870.0 * 0.943 / 1000,
        9100.0 * 0.1 * 0.942 / 1000,
        18300.0 * 0.1 * 0.0941 / 1000,
        1930.0 * 0.1 * 0.944 / 1000,
    ]
    assert "EF매핑명" not in joined.columns  # C8·C13 결과에는 계수 이름 열이 없다
    rows = [row for i in range(3) for row in rows_json(result, i)]
    assert {r["kind"] for r in rows} == {kind}
    assert [r["allocation"] for r in rows] == [
        {"method": "에너지사용량", "buildingTotal": None, "areaRatio": None, "personRatio": None},
        {"method": "에너지사용량", "buildingTotal": None, "areaRatio": None, "personRatio": None},
        {"method": "면적배분", "buildingTotal": "9100.0", "areaRatio": "0.1", "personRatio": None},
        {"method": "면적배분", "buildingTotal": "18300.0", "areaRatio": "0.1", "personRatio": None},
        {"method": "인원배분", "buildingTotal": "1930.0", "areaRatio": None, "personRatio": "0.1"},
    ]
    assert [r["factor"]["title"] for r in rows] == ["전력", "도시가스(LNG)", "경유", "전력", "천연가스(LNG)"]
    assert [r["match"] for r in rows] == [{"type": "exact_raw", "score": "1.0"}] * 5
    assert {r["factor"]["sheet"] for r in rows} == {"에너지"}


def test_leased_rows_call_the_chain_without_a_unit_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    """본 고리 `:6157` 은 `lookup_energy_ef(energy_name)` — 힌트를 넘기는 것은 C11·C14(c1b)뿐."""
    seen: list[tuple[object, object]] = []
    chain = energy.lookup_energy_ef

    def spy(db: pd.DataFrame, energy_name: object, unit_hint: object = None) -> energy.EnergyLookup:
        seen.append((energy_name, unit_hint))
        return chain(db, energy_name, unit_hint)

    monkeypatch.setattr(energy, "lookup_energy_ef", spy)
    run_on(leased_template("c8"))
    assert seen == [
        ("전력", None),
        ("도시가스(LNG)", None),
        ("경유", None),
        ("전력", None),
        ("천연가스(LNG)", None),
    ]


def test_a_gas_name_without_a_hint_takes_city_gas_not_the_unit_priority_title() -> None:
    """「LNG」 + kg: 힌트가 있었다면 단위 우선 별칭(천연가스 kg, `:8240`)이지만, 본 고리는 힌트가 없어 별칭 첫 후보."""
    result = run_on(
        [leased_sheet("c8-1_에너지사용량 아는 경우", energy_annual(["가상국", "가상자산", "LNG", "kg"], 99))]
    )
    (row,) = rows_json(result, 0)
    assert (row["factor"]["title"], row["factor"]["value"], row["match"]) == (
        "도시가스(LNG)",
        "0.943",
        {"type": "alias_exact", "score": "0.97"},
    )


# ── T5·T7 pipeline ──


def test_energy_keys_are_their_own_set() -> None:
    assert {"c3", "c8_energy", "c8_area", "c8_person", "c13_energy", "c13_area", "c13_person"} == ENERGY_KEYS
    assert ENERGY_KEYS <= SUPPORTED_KEYS  # 남은 열쇠는 test_product_eol_sheet(S3C-c1b-1)
    assert not ENERGY_KEYS & (PURCHASE_KEYS | ACTIVITY_KEYS)


def test_factor_sheets_put_the_energy_two_after_the_activity_five() -> None:
    result = run_on([c3_sheet()])
    assert [(s.sheet, s.how, s.header) for s in result.factor_sheets][5:7] == [
        ("에너지", "reloaded", 3),
        ("에너지_C3", "initial", 2),
    ]
    assert [s.sheet for s in result.factor_sheets][:7] == [
        "운송_Spend",
        "출장_Spend",
        "폐기물_C5",
        "운송",
        "출장_통근",
        "에너지",
        "에너지_C3",
    ]  # fmt: skip — 끝의 `폐기물_C12`(S3C-c1b-1)는 test_product_eol_sheet


def test_the_unit_ai_is_asked_once_for_c3_and_c8_alike() -> None:
    """따를 표 5: C3 3번과 C8-1 3번(가상와트·kWh·전력)은 한 번 — C8-1 은 실행 캐시(C5 무게 배수와 같은 것)."""
    mock = unit_replies()
    same = energy_annual(["가상국", "가상자산B", "전력", "가상와트"], 99)
    result = run_on(
        [c3_sheet("c3_연료에너지", C3_ROWS[2]), leased_sheet("c8-1_에너지사용량 아는 경우", same)], mock=mock
    )
    assert len(mock.texts) == 1
    assert mock.texts[0].startswith(
        "단위 환산 배수를 추정하라.\n입력 단위: 가상와트\n목표(기준) 단위: kWh\n맥락: 전력\n"
    )
    (c8,) = rows_json(result, 1)
    assert (c8["activity"]["baseValue"], c8["originSteps"][0]) == (
        repr(99 * 9.9),
        {"step": "unit", "origin": "ai", "via": "ai"},
    )
    assert result_to_dict(result, SCHEMA)["llmCalls"] == {"inventory/scope3-colab-unit-factor@1": {"success": 1}}


# ── T6 serialize 가 낸 줄이 계약(키 차례까지)을 지난다 ──


def test_serialized_energy_rows_fit_the_contract_and_its_key_order() -> None:
    result = run_on([c3_sheet("c3_연료에너지", *C3_ROWS), *leased_template("c13")])
    data = result_to_dict(result, SCHEMA)
    shapes.RESULT_SHAPES[SCHEMA].validate_python(data, strict=True)
    assert fits(data, typed(shapes.Scope3ColabDone)) == []
    rows = [row for s in cast("list[dict[str, Any]]", data["sheets"]) for row in s["rows"]]
    assert [r["kind"] for r in rows] == ["fuel_energy"] * 4 + ["leased_out_asset"] * 5


# ── 검증 권고 R3·R4·R5(경계 2 검증, 10-27) ──


def test_a_fallback_factor_is_an_estimate() -> None:
    """R3 — 발주서 2-2: 사슬이 통합 DB 에 없는 이름을 폴백 계수(`ENERGY_FALLBACK_EF_PATCH` `:6805`)로 답하면
    estimate."""
    result = run_on(
        [leased_sheet("c8-1_에너지사용량 아는 경우", energy_annual(["가상국", "가상자산", "휘발유", "L"], 99))]
    )
    (row,) = rows_json(result, 0)
    assert (row["factor"]["title"], row["factor"]["column"], row["match"]) == (
        "휘발유",
        None,
        {"type": "legacy_lookup", "score": None},
    )
    assert row["originSteps"] == [{"step": "factor", "origin": "estimate", "via": "fallback_patch"}]
    assert (row["origin"], row["missing"]) == ("estimate", [])


def test_a_zero_building_total_leaves_the_share_and_usage_empty() -> None:
    """R4 — 코랩 `(used / total) if total else None`: 건물전체 면적 0 → 면적비율·사용량·배출량이 빈다."""
    result = run_on([leased_sheet("c8-2_면적", energy_annual(["가상국", "가상자산", 0, 900, "경유", "L"], 9100))])
    frame = processed(result, 0).frame
    assert (column(frame, "면적비율"), column(frame, "사용량"), column(frame, "배출량(tCO2e)")) == (
        [None],
        [None],
        [None],
    )
    (row,) = rows_json(result, 0)
    assert (row["allocation"]["areaRatio"], row["activity"]["value"], row["co2e"]) == (None, None, None)
    assert row["missing"] == ["amount"]


def test_a_zero_factor_gives_no_emission_like_the_colab() -> None:
    """R5 — 코랩 `… if (usage is not None and ef_val) else None`: 계수 0 이면 배출량이 0 이 아니라 빈다(코랩과 같음)."""
    head: list[Value] = ["활동유형(에너지원)", "기준단위", "EF\n(kgCO2eq/단위)"]
    c3_book = sheet("에너지_C3", {1: ["가상"], 2: ["가상 안내"], 3: head, 4: ["전력", "kWh", 0]})
    result = run_on([c3_sheet()], factor_sheets=[energy_factor_sheets()[0], c3_book])
    frame = processed(result, 0).frame
    assert (column(frame, "배출계수(kgCO2eq/단위)"), column(frame, "배출량(tCO2e)")) == ([0.0], [None])
    (row,) = rows_json(result, 0)
    assert (row["factor"]["value"], row["co2e"], row["missing"]) == ("0.0", None, [])
