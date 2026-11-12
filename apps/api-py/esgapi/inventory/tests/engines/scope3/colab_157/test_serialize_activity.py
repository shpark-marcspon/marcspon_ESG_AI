"""S8 결과 꼴(S3C-b1 ②): 지출·폐기물 줄(ColabActivityRowJson)의 칸과 산정 출처(발주서 2-5), C1·C2 줄은 `kind` 한 칸
말고 BASE 와 같음, `factorSheets`.

한 줄씩의 템플릿·계수 책은 `support.py` 의 짓개(C4-2·C9-2 「가상트럭」 키워드 · C6-2 「택시」 수동 표·이동수단 앞 표 ·
C5 정확히 같은 줄·ton). 기대값은 입력 칸의 글자로 다시 셈한 식이다(코랩 차례: 금액 × 계수 / 1000).
산정 출처의 갈래(mapping·unit ai·fx 1400·평균 계수·계수 없음)는 줄 메타를 직접 지어 serializer 에 넣는다.
"""

import hashlib
import json
from functools import cache
from typing import Any, cast

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.activity import (
    ActivityAmount,
    ActivityFactor,
    ActivityMeta,
    ActivityMode,
    ActivityOriginStep,
    fx_step,
    mapping_step,
    mode_step,
    transport_factor_step,
    unit_step,
    waste_factor_step,
)
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, ProcessedSheet, run
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict, sheet_to_dict
from esgapi.inventory.engines.scope3.colab_157.template import match_sheet_processor
from esgapi.inventory.tests.engines.scope3.colab_157 import test_purchase
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    INPUT_KEYS,
    SPEND_KRW_2025,
    FakeGeocoder,
    activity_book,
    row_input,
    sheet,
    transport_spend_sheet,
    travel_spend_sheet,
    waste_sheet,
    workbook,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, C1_ROWS, SHAPE, TAGS, replies
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client

GFT = "General Freight Trucking, Local"
# BASE 78d779e 의 S1 결과(C1 일곱 + C2 하나)의 줄 dict 들을 json.dumps(ensure_ascii=False) 한 글자의 sha256
# (2026-10-20 BASE 를 git archive 로 풀어 같은 식으로 잼 — 경계 ② 이전 serializer).
BASE_PURCHASE_ROWS_SHA256 = "f3e0114654b4699d715b0e3901b4ad4f5f192239858a63a56b8581b7e6c4c319"
# S3C-b2a BASE(ff6ba81)의 지출·폐기물 줄 넷(`outcome()`)을 json.dumps(ensure_ascii=False) 한 sha256 — 그 판을 git
# archive 로 꺼내 같은 셈으로 잼(밴드 보고). HEAD 는 `distance` 한 칸을 빼면 같아야 한다(발주서 D9)
BASE_ACTIVITY_ROWS_SHA256 = "f7a80080652fb5bc2ef0d44cc2b7c7f77a917bdaf674944542bfdc12100fb7e4"


@cache
def outcome() -> dict[str, Any]:
    template = workbook(
        sheet("C1_구매품서비스", {n: C1_ROWS[n] for n in (4, 5, 6)}),
        transport_spend_sheet("c4-2_운송금액"),
        waste_sheet("c5_사업장폐기물"),
        travel_spend_sheet("c6-2_출장비"),
        transport_spend_sheet("c9-2_운송금액"),
    )
    book = activity_book(sheet("구매_USEPA", BOOK_ROWS))
    result = run(template, book, 2025, mock_client(replies()), FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return result_to_dict(result, SHAPE)


def rows() -> dict[str, dict[str, Any]]:
    sheets = cast("list[dict[str, Any]]", outcome()["sheets"])
    return {row["rowId"]: row for s in sheets for row in s["rows"]}


def r(value: float) -> str:
    return repr(value)


def transport_row(row_id: str) -> dict[str, object]:
    return {
        "rowId": row_id,
        "kind": "transport_spend",
        "month": None,
        "activity": {"value": r(9500000.0), "unit": "KRW", "baseValue": r(9500000.0), "baseUnit": "KRW", "note": None},
        "factor": {
            "sheet": "운송_Spend",
            "title": GFT,
            "value": r(9.12e-05),
            "unit": "kgCO2e/KRW",
            "column": SPEND_KRW_2025,
            "code": "9001",
        },
        "co2e": r(9500000 * 9.12e-05 / 1000),
        "unit": "tCO2eq",
        "formula": "",  # 운송 Spend 갈래는 「계산식」 을 쓰지 않는다(코랩 :8032)
        "treatment": None,
        "biogenic": None,
        "mode": None,
        "distance": None,  # 거리 kind 만(S3C-b2a)
        "origin": "rule",
        "originSteps": [{"step": "factor", "origin": "rule", "via": "keyword:expanded"}],
        "missing": [],
        # S3R2: 지출 시트 짓개에는 국가 열이 없다(국가 null) · vehicle ← 운송수단(선택)
        "input": row_input(site="가상사업장", name="가상 철강 코일", vehicle="가상트럭"),
    }


def test_every_row_carries_its_kind() -> None:
    sheets = cast("list[dict[str, Any]]", outcome()["sheets"])
    assert [(s["sheet"], [row["kind"] for row in s["rows"]]) for s in sheets] == [
        ("C1_구매품서비스", ["purchase"]),
        ("c4-2_운송금액", ["transport_spend"]),
        ("c5_사업장폐기물", ["waste"]),
        ("c6-2_출장비", ["travel_spend"]),
        ("c9-2_운송금액", ["transport_spend"]),
    ]
    assert list(rows()["C1_구매품서비스!6"])[:3] == ["rowId", "kind", "month"]


def test_transport_spend_rows() -> None:
    assert rows()["c4-2_운송금액!6"] == transport_row("c4-2_운송금액!6")
    assert rows()["c9-2_운송금액!6"] == transport_row("c9-2_운송금액!6")
    assert list(rows()["c4-2_운송금액!6"]["factor"]) == ["sheet", "title", "value", "unit", "column", "code"]


def test_travel_spend_row_keeps_the_mode_out_of_the_row_origin() -> None:
    row = rows()["c6-2_출장비!6"]
    assert row["activity"] == {
        "value": r(9300000.0),
        "unit": "KRW",
        "baseValue": r(9300000.0),
        "baseUnit": "KRW",
        "note": None,
    }
    assert row["factor"] == {
        "sheet": "출장_Spend",
        "title": "Taxi Service",
        "value": r(9.1e-05),
        "unit": "kgCO2e/KRW",
        "column": SPEND_KRW_2025,
        "code": "9101",
    }
    assert row["co2e"] == r(9300000 * 9.1e-05 / 1000)
    assert row["formula"] == "배출량(tCO2e) = 출장비용(KRW) × EF(kgCO2e/KRW) / 1000 = 9.3e+06 × 9.1e-05 / 1000 = 0.8463"
    assert (row["treatment"], row["biogenic"], row["mode"]) == (None, None, {"value": "taxi", "origin": "rule"})
    assert row["originSteps"] == [
        {"step": "factor", "origin": "rule", "via": "manual"},
        {"step": "mode", "origin": "rule", "via": "rule_fix"},
    ]
    assert (row["origin"], row["missing"]) == ("rule", [])


def test_waste_row_co2e_is_the_fossil_share() -> None:
    row = rows()["c5_사업장폐기물!6"]
    total = 9500.0 * 9.1 / 1000
    biogenic = total * (1 - 0.01)
    assert row["activity"] == {
        "value": r(9.5),
        "unit": "ton",
        "baseValue": r(9500.0),
        "baseUnit": "kg",
        "note": "ton→kg (×1000.0)",
    }
    assert row["factor"] == {
        "sheet": "폐기물_C5",
        "title": None,  # lookup_waste_ef 가 이름을 내지 않는다
        "value": r(9.1),
        "unit": "kgCO2eq/kg",
        "column": "배출계수 (kgCO2eq/kg)",
        "code": None,
    }
    assert row["biogenic"] == {
        "fossilCo2e": r(total - biogenic),
        "biogenicCo2e": r(biogenic),
        "fcf": r(0.01),
        "note": "폐지류 소각: 생물기원 99% / 화석기원 1%",
    }
    assert row["co2e"] == r(total - biogenic)
    assert (row["treatment"], row["mode"], row["formula"]) == ("소각", None, "")
    assert row["originSteps"] == [
        {"step": "unit", "origin": "rule", "via": "rule"},
        {"step": "factor", "origin": "rule", "via": "exact"},
    ]
    assert (row["origin"], row["missing"]) == ("rule", [])


def test_factor_sheets_follow_the_factor_book() -> None:
    data = outcome()
    assert list(data)[:5] == ["schemaVersion", "status", "reportYear", "factorBook", "factorSheets"]
    assert data["factorSheets"] == [
        {"sheet": "운송_Spend", "read": "reloaded", "header": 2, "rows": 1},
        {"sheet": "출장_Spend", "read": "reloaded", "header": 2, "rows": 1},
        {"sheet": "폐기물_C5", "read": "reloaded", "header": 2, "rows": 1},
        {"sheet": "운송", "read": "empty", "header": None, "rows": 0},  # S3C-b2a — 기존 셋 뒤에 한 항목
        {"sheet": "출장_통근", "read": "empty", "header": None, "rows": 0},  # S3C-b2b — 그 뒤에 한 항목
        {"sheet": "에너지", "read": "empty", "header": None, "rows": 0},  # S3C-c1a — 그 뒤에 이 차례로 둘
        {"sheet": "에너지_C3", "read": "empty", "header": None, "rows": 0},
        {"sheet": "폐기물_C12", "read": "empty", "header": None, "rows": 0},  # S3C-c1b-1 — 그 뒤에 한 항목
    ]
    s1 = test_purchase.outcome()[0]  # 구매_USEPA 하나뿐인 계수 책 → 넷 다 빈 읽기
    assert s1["factorSheets"] == [
        {"sheet": name, "read": "empty", "header": None, "rows": 0}
        for name in ("운송_Spend", "출장_Spend", "폐기물_C5", "운송", "출장_통근", "에너지", "에너지_C3", "폐기물_C12")
    ]


def test_activity_rows_are_the_base_rows_plus_a_null_distance() -> None:
    """지출·폐기물 줄은 `mode` 다음의 `distance: null` 한 칸과 끝의 `input`(S3R2) 말고 BASE 와 글자까지 같다
    (S3C-b2a D9)."""
    activity_rows = [row for s in outcome()["sheets"] for row in s.get("rows", []) if row["kind"] != "purchase"]
    assert len(activity_rows) == 4
    for row in activity_rows:
        keys = list(row)
        assert row["distance"] is None and keys[keys.index("mode") + 1] == "distance"
        assert keys[-1] == "input" and list(row["input"]) == list(INPUT_KEYS)  # S3R2: 끝에 한 칸 더
    without = [{k: v for k, v in row.items() if k not in ("distance", "input")} for row in activity_rows]
    text = json.dumps(without, ensure_ascii=False)
    assert hashlib.sha256(text.encode()).hexdigest() == BASE_ACTIVITY_ROWS_SHA256


def test_purchase_rows_are_the_base_rows_plus_kind() -> None:
    """C1·C2 줄은 rowId 다음의 `kind: "purchase"` 한 칸과 끝의 `input`(S3R2) 말고 BASE 와 글자까지 같다."""
    s1 = test_purchase.outcome()[0]
    purchase_rows = [row for s in s1["sheets"] for row in s.get("rows", [])]
    assert len(purchase_rows) == 8
    assert all(list(row)[1] == "kind" and row["kind"] == "purchase" for row in purchase_rows)
    assert all(list(row)[-1] == "input" and list(row["input"]) == list(INPUT_KEYS) for row in purchase_rows)  # S3R2
    without_kind = [{k: v for k, v in row.items() if k not in ("kind", "input")} for row in purchase_rows]
    text = json.dumps(without_kind, ensure_ascii=False)
    assert hashlib.sha256(text.encode()).hexdigest() == BASE_PURCHASE_ROWS_SHA256


# ── 산정 출처(2-5): 줄 메타를 지어 serializer 로 ──


def meta(
    steps: tuple[ActivityOriginStep, ...],
    *,
    value: float | None = 9.5,
    factor_value: float | None = 9.1,
    mode: ActivityMode | None = None,
) -> ActivityMeta:
    return ActivityMeta(
        excel_row=6,
        kind="waste",
        month=None,
        activity=ActivityAmount(value, "kg", value, "kg", None),
        factor=ActivityFactor("폐기물_C5", None, factor_value, "kgCO2eq/kg", None, None),
        treatment="소각",
        biogenic=None,
        mode=mode,
        steps=steps,
    )


def serialized(*metas: ActivityMeta) -> list[dict[str, Any]]:
    processor = match_sheet_processor("c5_사업장폐기물")
    assert processor is not None
    frame = pd.DataFrame([{"배출량(tCO2e)": 9.5, "계산식": "가상식"}] * len(metas))
    data = sheet_to_dict(ProcessedSheet("c5_사업장폐기물", processor, frame, tuple(metas)), None)
    return cast("list[dict[str, Any]]", data["rows"])


def test_the_row_origin_is_the_weakest_numeric_step() -> None:
    """mapping·unit·fx·factor 가운데 가장 약한 것(estimate > ai > rule). mode 는 mode.origin 에만."""
    got = serialized(
        meta((mapping_step(), unit_step("ai"), waste_factor_step("exact"))),
        meta((fx_step("fx_default_1400"), transport_factor_step("keyword:raw"))),
        meta((unit_step("rule"), waste_factor_step("treatment_average"))),
        meta((transport_factor_step("title:raw"), mode_step("ai")), mode=ActivityMode("가상수단", "ai")),
        meta((unit_step("none"), transport_factor_step("default_title"))),
    )
    assert [(row["origin"], row["mode"]) for row in got] == [
        ("ai", None),
        ("estimate", None),
        ("estimate", None),
        ("rule", {"value": "가상수단", "origin": "ai"}),
        ("estimate", None),
    ]
    assert got[0]["originSteps"] == [
        {"step": "mapping", "origin": "rule", "via": "company_mapping"},
        {"step": "unit", "origin": "ai", "via": "ai"},
        {"step": "factor", "origin": "rule", "via": "exact"},
    ]
    assert [row["rowId"] for row in got] == [f"c5_사업장폐기물!6#{n}" for n in range(1, 6)]
    assert {(row["co2e"], row["formula"]) for row in got} == {(r(9.5), "가상식")}


def test_missing_says_which_number_is_absent() -> None:
    got = serialized(
        meta((unit_step("rule"),), factor_value=None),  # 계수 단계 없음(평균 표에도 없는 「기타」)
        meta((waste_factor_step("exact"),), factor_value=None),
        meta((waste_factor_step("exact"),), value=None),
        meta((waste_factor_step("exact"),), value=float("nan")),
    )
    assert [(row["origin"], row["missing"], row["activity"]["value"]) for row in got] == [
        (None, ["factor"], r(9.5)),
        ("rule", ["factorValue"], r(9.5)),
        ("rule", ["amount"], None),
        ("rule", ["amount"], None),
    ]
