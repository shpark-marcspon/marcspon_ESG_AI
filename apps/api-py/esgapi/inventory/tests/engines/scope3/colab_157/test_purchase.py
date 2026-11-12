"""S1 손셈: C1 한 시트(줄 일곱)·C2 한 시트(줄 하나)를 지어 `pipeline.run` 으로 돌리고 줄마다 손으로 짚은 값과 견준다.

줄마다 지나는 갈래(코랩 `_fix_rank_spend_candidates` `:8341` 네 단계, `classify_purchase_group` `:4618` 네 순위):
    C1!6  사용자 그룹 · 수작업 규칙(「컨설팅」)            C1!8  LLM 그룹 이름 · 옛 추천의 계열 제목 · 지수 표기
    C1!9  키워드 그룹 · 옛 추천의 rapidfuzz(LLM 번역)     C1!10 키워드 그룹 · 끝 대안(추정)
    C1!11 LLM 실패 → 기타 그룹                           C1!12 USD 금액 — 셈(원화 환산) ≠ 후처리(구매금액 그대로)
    C1!7  월별 줄(녹이기 ValueError → 월 합) · 키워드 점수 동점
    C2!6  사용자 그룹 「차량」 · 수작업 규칙(「지게차」)
기대값은 입력 칸의 글자로 다시 셈한 식이다(코랩과 같은 차례: 금액 × 계수 / 1000). rapidfuzz 점수만 잰 값이다
(`process.extract("Coffee and Tea", …, scorer=WRatio)` — 90·85.5·85.5, 2026-10-19 rapidfuzz 3.14.6 에서 잼).
엔진 문맥(`legacy_strings`)은 `run` 이 건다 — 시험은 기본 문맥에서 `run` 을 부른다(경계 ② 검증 N1).
"""

from functools import cache
from typing import Any, cast

import pandas as pd

from esgapi.core.llm.types import Tags
from esgapi.inventory.engines.scope3.colab_157.factor_book import load_purchase_usepa_as_krw_spend_db
from esgapi.inventory.engines.scope3.colab_157.llm import LlmCalls, LlmContext
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, ProcessedSheet, run
from esgapi.inventory.engines.scope3.colab_157.purchase import PurchaseBook, PurchaseRun, rank_spend_candidates
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    ColabReplies,
    FakeGeocoder,
    Value,
    sheet,
    workbook,
)
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools.scope3_sheets.grid import Sheet, Workbook

TAGS = Tags(tenant="가상회사", module="inventory")
SHAPE = "scope3.colab.result@1"

MCS, OSX, OSS = (
    "Management Consulting Services",
    "Office Supplies (except Paper) Manufacturing",
    "Office Supplies and Stationery Stores",
)
TRUCK = "Industrial Truck, Tractor, Trailer, and Stacker Machinery Manufacturing"
MISC = "Other Miscellaneous Durable Goods Merchant Wholesalers"
COFFEE = "Virtual Coffee and Tea Merchants"
KRW_2025 = "EF (kgCO2e/KRW)\n2025년말 기준\n(9,400 KRW/USD)"
HEAD: list[Value] = [
    "품목군",
    "상세 카테고리",
    "한국어 매핑 키워드",
    "NAICS 코드",
    "NAICS Title",
    "EF (kgCO2e/USD)",
    KRW_2025,
]
BOOK_ROWS: dict[int, list[Value]] = {
    1: ["가상 구매 계수 표"],
    3: HEAD,
    4: ["외주서비스", "가상세부", None, 9001, MCS, 0.95, 9.1e-05],
    5: ["사무용품", "가상세부", "가상토너", 9002, OSX, 0.93, 9.2e-05],
    6: ["사무용품", "가상세부", "가상토너, 가상복사지", 9003, OSS, 0.92, 9.3e-05],
    7: ["차량운송장비", "가상세부", None, 9004, TRUCK, 0.91, 9.4e-05],
    8: ["가상군", "가상세부", None, 9005, MISC, 0.9, 9.5e-05],
    9: ["가상군", "가상세부", None, 9006, COFFEE, 0.9, 9.6e-05],
}
C1_HEAD: list[Value] = [
    "*국가", "*사업장", "*품목군", "*상세 품목명/서비스명", "거래처명(선택)",
    "연간 입력", "월별 지출금액", None, "비고(선택)", "단위",
]  # fmt: skip
C1_SUB: list[Value] = [None, None, None, None, None, "연간지출금액(원)", "1월", "2월", None, None]
C1_ROWS: dict[int, list[Value]] = {
    4: C1_HEAD,
    5: C1_SUB,
    6: ["가상국", "가상사업장", "컨설팅", "가상 경영자문", None, 9100000],
    7: ["가상국", "가상사업장", None, "가상토너 교체", None, None, 9.5, 9000],
    8: ["가상국", "가상사업장", None, "가상 무엇", None, 9.5],
    9: ["가상국", "가상사업장", None, "가상 커피 원두", None, 9200],
    10: ["가상국", "가상사업장", None, "가상 생수 배달", None, 9300],
    11: ["가상국", "가상사업장", None, "가상 어떤것", None, 9400],
    12: ["가상국", "가상사업장", None, "가상 복사지", None, 9.9, None, None, None, "USD"],
}
C2_ROWS: dict[int, list[Value]] = {
    4: [
        "*국가",
        "*사업장",
        "*자산분류",
        "*상세 자산명",
        "자산번호(선택)",
        "거래처명(선택)",
        "연간 입력",
        "월별 취득금액",
        None,
        "비고(선택)",
    ],
    5: [None, None, None, None, None, None, "연간취득금액(원)", "1월", "2월", None],
    6: ["가상국", "가상사업장", "차량", "가상 지게차", None, None, 9300000],
}
FX_USD_2025 = 1422.44  # 코랩 :3462-3475 열두 달의 합 17069.29 ÷ 12 = 1422.4408 → round 2(:3651)

SAMPLES: tuple[Sheet, ...] = (
    sheet("구매_USEPA", BOOK_ROWS),
    sheet("C1_구매품서비스", C1_ROWS),
    sheet("C2_자본재", C2_ROWS),
)  # test_samples 가 본다


def book() -> Workbook:
    return workbook(sheet("구매_USEPA", BOOK_ROWS))


def replies() -> ColabReplies:
    return ColabReplies(groups={"가상 무엇": "가상장비"}, naics={"커피": '{"generic_english": "Coffee and Tea"}'})


@cache
def outcome() -> tuple[dict[str, Any], ColabRun, ColabReplies]:
    mock = replies()
    template = workbook(sheet("C1_구매품서비스", C1_ROWS), sheet("C2_자본재", C2_ROWS))
    result = run(template, book(), 2025, mock_client(mock), FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return result_to_dict(result, SHAPE), result, mock


def rows_of(sheet_index: int) -> dict[str, dict[str, Any]]:
    sheets = cast("list[dict[str, Any]]", outcome()[0]["sheets"])
    return {row["rowId"]: row for row in sheets[sheet_index]["rows"]}


def r(value: float) -> str:
    return repr(value)


def rec(title: str, ef: float, spend: float) -> dict[str, object]:
    return {"title": title, "value": r(ef), "expectedCo2e": r(spend * ef / 1000.0)}


def test_the_c1_rows_come_in_the_colab_order() -> None:
    """연간 줄 먼저, 월별 줄 뒤(`standardize_c1_sheet` 의 concat([연간, 월별]) — 코랩 그대로)."""
    assert list(rows_of(0)) == [f"C1_구매품서비스!{n}" for n in (6, 8, 9, 10, 11, 12, 7)]
    assert len(rows_of(1)) == 1  # 분모: C1 일곱 + C2 하나


def test_manual_rule_row() -> None:
    row = rows_of(0)["C1_구매품서비스!6"]
    assert row["factor"] == {"title": MCS, "value": r(9.1e-05), "unit": "kgCO2e/KRW", "column": KRW_2025,
                             "source": "manual_keyword"}  # fmt: skip
    assert row["co2e"] == r(9100000 * 9.1e-05 / 1000.0)
    assert row["recommendations"] == [rec(OSX, 9.2e-05, 9100000), rec(OSS, 9.3e-05, 9100000)]
    assert row["group"] == {"key": "user_컨설팅", "name": "컨설팅", "reason": "사용자입력: 컨설팅",
                            "family": "service_outsourcing", "category": "Category1", "llm": None}  # fmt: skip
    assert row["origin"] == "rule"
    assert row["originSteps"] == [
        {"step": "group", "origin": "rule", "via": "group_user"},
        {"step": "factor", "origin": "rule", "via": "manual_keyword"},
        {"step": "spend", "origin": "rule", "via": "KRW"},
    ]
    assert (row["amount"], row["spendKrw"], row["spendNote"], row["missing"]) == (
        r(9100000.0),
        r(9100000.0),
        "KRW 그대로",
        [],
    )


def test_llm_group_row_with_an_exponent_co2e() -> None:
    row = rows_of(0)["C1_구매품서비스!8"]
    assert row["group"] == {
        "key": "llm_가상장비",
        "name": "가상장비",
        "reason": "AI그룹핑: 가상 무엇",
        "family": "misc_purchase",
        "category": "Category1",
        "llm": {"outcome": "success", "answer": "가상장비", "reason": None},
    }
    assert row["originSteps"][0] == {"step": "group", "origin": "ai", "via": "group_llm"}
    # 계수는 옛 추천의 계열 제목(일반 사무용품 — 규칙)
    assert (row["factor"]["title"], row["factor"]["source"], row["origin"]) == (OSX, "legacy_fallback", "rule")
    assert row["co2e"] == r(9.5 * 9.2e-05 / 1000.0)
    assert "e-" in row["co2e"]  # 처분 ⑦: repr(float) 의 지수 표기를 그대로 낸다


def test_legacy_rapidfuzz_row_is_ai() -> None:
    """계열(커피) 제목이 계수 책에 없어 옛 추천은 LLM 번역 「Coffee and Tea」 의 rapidfuzz 만 낸다(≥ 78)."""
    row = rows_of(0)["C1_구매품서비스!9"]
    assert (row["factor"]["title"], row["factor"]["source"], row["origin"]) == (COFFEE, "legacy_fallback", "ai")
    assert row["co2e"] == r(9200 * 9.6e-05 / 1000.0)
    assert row["recommendations"] == [rec(OSS, 9.3e-05, 9200), rec(TRUCK, 9.4e-05, 9200)]
    assert row["group"]["reason"] == "키워드매칭: 커피, 원두"
    assert row["originSteps"][0] == {"step": "group", "origin": "rule", "via": "group_rule"}


def test_fallback_row_is_an_estimate() -> None:
    row = rows_of(0)["C1_구매품서비스!10"]
    assert (row["factor"]["title"], row["factor"]["source"], row["origin"]) == (MISC, "manual_title", "estimate")
    assert row["co2e"] == r(9300 * 9.5e-05 / 1000.0)
    assert row["recommendations"] == []


def test_llm_failure_row_keeps_the_colab_unknown() -> None:
    row = rows_of(0)["C1_구매품서비스!11"]
    assert row["group"] == {
        "key": "misc_purchase",
        "name": "가상 어떤것",
        "reason": "rule_unmatched",
        "family": "misc_purchase",
        "category": "Category1",
        "llm": {"outcome": "failed", "answer": "Unknown", "reason": "provider_error"},
    }
    assert row["originSteps"][0] == {"step": "group", "origin": "estimate", "via": "group_fallback"}
    assert row["co2e"] == r(9400 * 9.2e-05 / 1000.0)


def test_usd_row_post_fix_uses_the_input_amount() -> None:
    """★§2-3 왕복 값: 셈은 USD → 원화(연평균 환율)로 하지만, 코랩 후처리는 「구매금액」(USD 그대로)× 계수 / 1000 으로
    덮는다."""
    row = rows_of(0)["C1_구매품서비스!12"]
    assert row["spendKrw"] == r(9.9 * FX_USD_2025)
    assert row["spendNote"] == "USD → KRW (1,422 환율 적용)"
    assert row["amount"] == r(9.9)
    assert row["co2e"] == r(9.9 * 9.3e-05 / 1000.0)  # 9.9 × 1422.44 × … 가 아니다
    assert (row["factor"]["title"], row["factor"]["source"]) == (OSS, "db_keyword")
    assert row["originSteps"][2] == {"step": "spend", "origin": "rule", "via": "USD"}


def test_monthly_row_sums_its_months() -> None:
    row = rows_of(0)["C1_구매품서비스!7"]
    assert row["amount"] == r(9.5 + 9000)
    assert (row["factor"]["title"], row["factor"]["source"]) == (OSX, "db_keyword")
    assert row["recommendations"] == [rec(OSS, 9.3e-05, 9.5 + 9000)]
    assert row["co2e"] == r((9.5 + 9000) * 9.2e-05 / 1000.0)
    assert row["group"]["key"] == "toner_ink"


def test_c2_row() -> None:
    row = rows_of(1)["C2_자본재!6"]
    assert (row["factor"]["title"], row["factor"]["source"]) == (TRUCK, "manual_keyword")
    assert row["co2e"] == r(9300000 * 9.4e-05 / 1000.0)
    assert row["recommendations"] == [rec(OSX, 9.2e-05, 9300000), rec(OSS, 9.3e-05, 9300000)]
    # 코랩 `_infer_family_from_user_group`(:4567)은 차례대로 보므로 「차량」 이 탕비 낱말 「차」 에 먼저 걸린다
    # (코랩 그대로)
    assert (row["group"]["key"], row["group"]["family"], row["group"]["category"]) == (
        "user_차량",
        "pantry_supplies",
        "Category2",
    )


def test_keyword_scores_by_hand() -> None:
    """2단계 점수: 정확히 든 키워드는 80 + 길이(최대 20). 「가상토너」 넷 → 84, 「가상복사지」 다섯 → 85."""
    with legacy_strings():
        db = run_book()
        toner = rank_spend_candidates(db, "가상토너 교체", top_n=2)
        paper = rank_spend_candidates(db, "가상 복사지", top_n=1)
    assert [(c.title, c.score, c.source) for c in toner] == [(OSX, 84, "db_keyword"), (OSS, 84, "db_keyword")]
    assert [(c.title, c.score) for c in paper] == [(OSS, 85)]


def run_book() -> PurchaseRun:
    spend = load_purchase_usepa_as_krw_spend_db(book(), 2025)
    return PurchaseRun(
        PurchaseBook(spend.frame, spend.names, (), 2025), LlmContext(mock_client(replies()), ROUTE, TAGS, LlmCalls())
    )


def test_llm_calls_and_the_engine_context() -> None:
    """부른 수(그룹 이름은 줄마다, NAICS 고르기는 옛 추천에 닿은 줄마다 — 성공만 기억). 부를 때 글 추론은 2.x 꼴."""
    data, result, mock = outcome()
    assert data["llmCalls"] == {
        "inventory/scope3-colab-naics-pick@1": {"failed:provider_error": 7, "success": 1},
        "inventory/scope3-colab-group-name@1": {"success": 1, "failed:provider_error": 1},
    }
    assert mock.infer_string == [False] * 10
    processed = result.sheets[0]
    assert isinstance(processed, ProcessedSheet)
    frame: pd.DataFrame = processed.frame
    assert str(frame["입력방식"].dtype) == "object"  # 엔진 문맥이 빠지면 pandas 3 의 str
