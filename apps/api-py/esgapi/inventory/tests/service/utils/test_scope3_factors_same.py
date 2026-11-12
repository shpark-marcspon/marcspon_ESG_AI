# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""같은-계수 대조(밴드 S3K2b-2 C0-2 — 결정 MARC-ENT-442): 줄 전부에 그 줄의 계수를 넣으면 본문 co2e 와 글자가 같다.

★ 표본은 저장한 JSON 이 아니라 여기서 엔진으로 짓는다(`run_flow` — 모의 공급사, 키 0). 그래서 엔진 식이 바뀌면 이 시험이
  빨개진다 — utils/scope3_factors 의 다시 적은 식이 엔진을 지키는 자리다. kind 마다 줄 ≥ 1 을 단언한다(빈 표본 금지).
값·이름은 지어낸 것이다.
"""

from functools import cache
from typing import Any

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderRequest, ProviderResponse, Tags
from esgapi.inventory.engines.scope3.colab_157 import pipeline
from esgapi.inventory.engines.scope3.colab_157.ports import NoGeocoder
from esgapi.inventory.flows import binding_157
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.service.utils.scope3_factors import editable, recompute
from esgapi.inventory.service.utils.scope3_state import FLOW_ID, RESULT_SHAPE
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    C3_ROW,
    C11_ROW,
    C14_ROW,
    COMMUTE_ROW,
    DIST_ROW,
    TRANSPORT_SPEND_ROWS,
    TRAVEL_ROW,
    WASTE_TEMPLATE,
    activity_factor_sheets,
    annual,
    c3_sheet,
    c11_sheet,
    c12_sheet,
    c14_sheet,
    c15_sheet,
    commute_sheet,
    energy_annual,
    energy_factor_sheets,
    leased_sheet,
    sheet,
    transport_distance_sheet,
    transport_ef_sheet,
    transport_spend_sheet,
    travel_distance_sheet,
    travel_ef_sheet,
    travel_spend_sheet,
    waste_c12_ef_sheet,
    workbook,
    xlsx_bytes,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, C1_ROWS, C2_ROWS, replies
from esgapi.inventory.tests.scope3_llm_support import user_text
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

ANSWERS = {
    "출발지: 가상시가\n도착지: 가상시다\n국가 힌트: KR": '{"distance_km": 92}',
    "가상시가": "Synthetic Ga",
    "가상시다": "Synthetic Da",
}


class Script(MockProvider):
    """openai 자리의 모의 공급사 — 거리 물음은 ANSWERS, 나머지는 구매 시트의 답."""

    def __init__(self) -> None:
        super().__init__("openai")
        self.purchase = replies()

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.enqueue(self.reply)
        return super().invoke(request, options)

    def reply(self, request: ProviderRequest) -> ProviderResponse:
        text = user_text(request)
        answer = next((a for key, a in ANSWERS.items() if key in text), None)
        if answer is not None:
            return Completed(text=answer, usage=SYNTHETIC_USAGE)
        return self.purchase.reply(request)


WASTE = {
    **WASTE_TEMPLATE,
    7: ["가상사업장", "가상폐지", "매립", "kg", 900],
    8: ["가상사업장", "가상 음식물 찌꺼기", "소각", "kg", 910],
    9: ["가상사업장", "가상 폐플라스틱", "소각", "kg", 920],
    10: ["가상사업장", "가상폐지", "재활용", "kg", 930],
}


def template() -> Any:
    return workbook(
        sheet("C1_구매품서비스", C1_ROWS),
        sheet("C2_자본재", C2_ROWS),
        c3_sheet(
            "c3_연료에너지",
            C3_ROW,
            energy_annual(["가상국", "가상사업장", "경유", "L"], 930),
            energy_annual(["가상국", "가상사업장", "도시가스(LNG)", "Nm³"], 940),
            energy_annual(["가상국", "가상사업장", "전력", "MWh"], 9.7),
        ),
        transport_distance_sheet(
            "c4-1_운송거리",
            DIST_ROW,
            annual(["가상국", "가상사업장", "가상트럭", "가상 판재", "kg", None, None, 73], 930),
        ),
        transport_spend_sheet(),
        sheet("c5_사업장폐기물", WASTE),
        travel_distance_sheet(
            "c6-1_출장거리",
            TRAVEL_ROW,
            [*annual(["가상국", "가상본부", "가상버스", 9, None, None, 99], 9), "가상 왕복"],
            annual(["가상국", "가상지사", "가상기차", 7, None, None, 9.9], 3),
        ),
        travel_spend_sheet(),
        commute_sheet(
            "c7_임직원통근",
            COMMUTE_ROW,
            [*annual(["가상국", "가상사업장", "가상버스", 13, None, None, 7.7], 210), "가상 왕복"],
        ),
        leased_sheet("c8-1_에너지사용량 아는 경우"),
        leased_sheet("c8-2_면적"),
        leased_sheet("c8-3_인원"),
        transport_distance_sheet("c9-1_운송거리", DIST_ROW),
        c11_sheet(
            "c11_판매제품사용",
            C11_ROW,
            ["가상국", None, None, "가상제품B", 950, "전력", 0.92, "MWh", None, None],
            ["가상국", "가상그룹A", None, "가상제품C", 99, "경유", 9.3, "L", 90, None],
        ),
        c12_sheet(),
        leased_sheet("c13-1_에너지사용량 아는 경우"),
        leased_sheet("c13-2_면적"),
        leased_sheet("c13-3_인원"),
        c14_sheet("c14_프랜차이즈", C14_ROW, ["가상국", "가상가맹B", 95, "전력", 92000, "kWh", None]),
        c15_sheet(),
    )


def book(*, usd: bool = False) -> Any:
    spend = activity_factor_sheets()
    if usd:  # 운송 지출 원화 열 없는 판(USD 갈래)
        rows = {k: v[:7] for k, v in TRANSPORT_SPEND_ROWS.items()}
        spend = (sheet("운송_Spend", rows), *spend[1:])
    return workbook(
        sheet("구매_USEPA", BOOK_ROWS),
        *spend,
        transport_ef_sheet(),
        travel_ef_sheet(),
        *energy_factor_sheets(),
        waste_c12_ef_sheet(),
    )


def sample(*, usd: bool = False) -> dict[str, Any]:
    tpl = xlsx_bytes(template())
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": Script()},
        prompts=PackagePromptStore(),
        log=MemorySink(),
    )
    inputs = colab.ColabInputs(
        template=tpl, report_year=2025, route=binding_157.ROUTE, tags=Tags(tenant="9", module="inventory.scope3")
    )
    bk = read_workbook(xlsx_bytes(book(usd=usd)))
    assert not isinstance(bk, ReaderProblem)
    result = run_flow(colab.FLOW, inputs, colab.ColabAdapters(llm=client, factor_book=bk, geocoder=NoGeocoder()))
    (only,) = result.output.results
    return only


KINDS = (
    "purchase",
    "transport_spend",
    "travel_spend",
    "waste",
    "transport_distance",
    "travel_distance",
    "commute",
    "fuel_energy",
    "leased_asset",
    "leased_out_asset",
    "product_use",
    "franchise",
)
"""식이 있는 kind 열둘. `product_eol`·`investment` 는 고칠 수 없다(Q5 ⓐⓒ)."""


def rows_of(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for found in body["sheets"] for row in found.get("rows") or ()]


@cache
def krw() -> tuple[dict[str, Any], ...]:
    return tuple(rows_of(sample()))


@cache
def usd() -> tuple[dict[str, Any], ...]:
    return tuple(rows_of(sample(usd=True)))


def co2e_of(row: dict[str, Any], value: str) -> str | None:
    found = recompute(row, float(value))
    return None if found is None else found.co2e


@pytest.mark.parametrize("kind", KINDS)
def test_the_same_factor_gives_the_same_letters(kind: str) -> None:
    rows = [row for row in krw() if row["kind"] == kind]
    assert rows, f"{kind} 표본이 비었다"
    assert [(row["rowId"], co2e_of(row, row["factor"]["value"])) for row in rows] == [
        (row["rowId"], row["co2e"]) for row in rows
    ]
    assert all(editable(row, RESULT_SHAPE, FLOW_ID) for row in rows)


def test_the_usd_branch_of_transport_spend_is_the_same_too() -> None:
    rows = [row for row in usd() if row["kind"] == "transport_spend"]
    assert rows
    assert {row["factor"]["unit"] for row in rows} == {"kgCO2e/USD"}
    assert [co2e_of(row, row["factor"]["value"]) for row in rows] == [row["co2e"] for row in rows]


def test_the_sample_has_the_rows_that_make_the_order_of_the_product_matter() -> None:
    """왕복계수가 1 이 아닌 C6-1·C7 줄, 소각 + fcf 인 C5 줄이 표본에 든다(B4)."""
    assert {row["distance"]["roundTrip"] for row in krw() if row["kind"] == "travel_distance"} == {"1.0", "2.0"}
    assert {row["distance"]["roundTrip"] for row in krw() if row["kind"] == "commute"} == {"1.0", "2.0"}
    burned = [row for row in krw() if row["kind"] == "waste" and row["biogenic"]["fcf"] is not None]
    assert {row["treatment"] for row in burned} == {"소각"}
    assert len({row["biogenic"]["fcf"] for row in burned}) >= 2


def test_the_biogenic_split_is_the_same_too() -> None:
    for row in krw():
        if row["kind"] == "waste":
            found = recompute(row, float(row["factor"]["value"]))
            assert found is not None
            assert found.biogenic_co2e == row["biogenic"]["biogenicCo2e"], row["rowId"]


def test_a_purchase_recommendation_recomputes_to_its_expected_co2e() -> None:
    pairs = [(rec["value"], rec["expectedCo2e"], row) for row in krw() for rec in row.get("recommendations") or ()]
    assert pairs
    assert [co2e_of(row, value) for value, _, row in pairs] == [expected for _, expected, _ in pairs]


def test_recommendations_appear_only_on_purchase_rows() -> None:
    assert {row["kind"] for row in krw() if row.get("recommendations")} == {"purchase"}


def test_c12_and_c15_rows_are_not_editable() -> None:
    kinds = {row["kind"]: row for row in krw()}
    assert not editable(kinds["product_eol"], RESULT_SHAPE, FLOW_ID)
    assert not editable(kinds["investment"], RESULT_SHAPE, FLOW_ID)


def test_rows_of_a_sheet_whose_postprocess_failed_are_not_editable(monkeypatch: pytest.MonkeyPatch) -> None:
    """후처리 실패 시트(R6): C6·C7 은 본문 co2e 가 null 인데 식은 값을 낸다 → 자기 대조가 막는다. C14 는 factor null.
    C11 은 처리 때 값이 식과 같아 고칠 수 있다."""

    def boom(*_: object) -> tuple[()]:
        raise ValueError("가상 후처리 실패")

    monkeypatch.setattr(pipeline, "postprocess_category", boom)
    monkeypatch.setattr(pipeline, "postprocess_product_category", boom)
    rows = rows_of(sample())
    by_kind = {
        kind: {editable(row, RESULT_SHAPE, FLOW_ID) for row in rows if row["kind"] == kind}
        for kind in ("travel_distance", "commute", "franchise", "product_use", "travel_spend")
    }
    assert by_kind == {
        "travel_distance": {False},
        "commute": {False},
        "franchise": {False},
        "product_use": {True},
        "travel_spend": {True},
    }
