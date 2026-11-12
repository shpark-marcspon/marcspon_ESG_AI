"""S2 운송 Spend 손셈(C4-2·C9-2) — `pipeline.run` 으로 시트를 돌려 줄마다 코랩을 손으로 따라 센 값과 견준다.

코랩 줄(읽기판): 표준화 `standardize_c4_spend_sheet`(`:6701`, 월 접기 `_patch_collapse_monthly_to_value` `:6509`) →
갈래 `:6001-6019` → `calc_transport_spend_emission`(`:8032-8073`) → `lookup_transport_spend_ef`(`:7752`, 확장 글 →
원문) → 붙잡은 옛 판(`:865-913`: 키워드 → 한국어명 → Title → 「General Freight Trucking, Local」). 계수 열은 늦은
묶임의 `_get_spend_ef_col`(`:7979` — 보고연도 원화 열, 없으면 USD 열), USD 갈래 환율은 `get_bok_usd_krw_monthly_avg`
(`:3632` — 그 달 → 연평균 round 2 → 1400, 표는 2025 하나 `:3462`).
배출량 = 운송금액 × EF / 1000(원화 열) 또는 (운송금액 / 환율) × EF / 1000(USD 갈래).
손셈은 코랩 식의 차례 그대로 적는다.

이 파일의 `run_sheets`·`Replies` 는 같은 폴더의 지출·폐기물 손셈 파일(S3·S4·S5)도 쓴다.
"""

from collections.abc import Callable, Sequence
from typing import Any

import pandas as pd

from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderError, ProviderRequest, ProviderResponse
from esgapi.inventory.engines.scope3.colab_157.activity import ActivityMeta
from esgapi.inventory.engines.scope3.colab_157.constants import BOK_USD_KRW_MONTHLY_AVG_2025
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, ProcessedSheet, SheetOutcome, run
from esgapi.inventory.tests.engines.scope3.colab_157.support import FakeGeocoder, Value, sheet, workbook
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, TAGS
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client, user_text
from esgapi.inventory.tools.scope3_sheets.grid import Sheet


class Replies(MockProvider):
    """사용자 글로 답을 고르는 모의 공급사(네트워크 0). `answer` 가 None 을 내면 공급사 실패. 받은 글을 적는다."""

    def __init__(self, answer: Callable[[str], str | None] = lambda _: None) -> None:
        super().__init__()
        self.answer = answer
        self.texts: list[str] = []

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.enqueue(self.reply)
        return super().invoke(request, options)

    def reply(self, request: ProviderRequest) -> ProviderResponse:
        text = user_text(request)
        self.texts.append(text)
        answer = self.answer(text)
        if answer is None:
            return ProviderError(status=None, retryable=False, message="가상: 심어 둔 답이 없다")
        return Completed(text=answer, usage=SYNTHETIC_USAGE)


def run_sheets(
    template: Sequence[Sheet], factor_sheets: Sequence[Sheet], year: int = 2025, mock: MockProvider | None = None
) -> tuple[SheetOutcome, ...]:
    """구매_USEPA(셀 9 이 읽는 시트 — 없으면 실행 거절)와 계수 시트로 템플릿을 돌린다."""
    book = workbook(sheet("구매_USEPA", BOOK_ROWS), *factor_sheets)
    result = run(workbook(*template), book, year, mock_client(mock or Replies()), FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return result.sheets


def processed(outcome: SheetOutcome) -> ProcessedSheet:
    assert isinstance(outcome, ProcessedSheet), outcome
    return outcome


def activity_metas(done: ProcessedSheet) -> list[ActivityMeta]:
    metas = [m for m in done.metas if isinstance(m, ActivityMeta)]
    assert len(metas) == len(done.metas) == len(done.frame)
    return metas


def column(frame: pd.DataFrame, name: str) -> list[Any]:
    """칸 값 목록(NaN → None)."""
    return [None if isinstance(v, float) and v != v else v for v in frame[name].tolist()]


USD = "EF (kgCO2e/USD)"
KRW_2024 = "EF (kgCO2e/KRW)\n2024년말 기준\n(9,300 KRW/USD)"
KRW_2025 = "EF (kgCO2e/KRW)\n2025년말 기준\n(9,400 KRW/USD)"
GFT = "General Freight Trucking, Local"  # 코랩 기본 줄이 찾는 공개 NAICS Title(값은 지어낸 것)
T_HEAD: list[Value] = ["운송 구분", "NAICS 코드", "NAICS Title", "한국어명", "한국어 키워드", USD, KRW_2024, KRW_2025]
T_ROWS: dict[int, list[Value]] = {
    1: ["가상 운송 지출 계수 표"],
    3: T_HEAD,
    4: ["가상도로", 9001, GFT, "가상 도로 화물", "가상트럭", 9.1, 9.11e-05, 9.12e-05],
    5: ["가상택배", 9002, "Virtual Couriers", "가상 소포", "courier", 9.2, 9.21e-05, 9.22e-05],
    6: ["가상해상", 9003, "Virtual Deep Sea Freight", "가상 해상 운송", "가상선적", 9.3, 9.31e-05, 9.32e-05],
}
# 원화 열 없음(USD 갈래 `:8053-8073`)
USD_ROWS: dict[int, list[Value]] = {n: row[:6] for n, row in T_ROWS.items()}
# 기본 줄 없음 — 확장 글이 아무것도 못 찾아 원문으로 한 번 더(`:7767`)
NO_DEFAULT_ROWS: dict[int, list[Value]] = {
    **T_ROWS,
    4: ["가상도로", 9001, "Virtual Road", "가상 도로 화물", "가상트럭", 9.1, 9.11e-05, 9.12e-05],
}

C4_HEAD: list[Value] = ["*사업장", "운송수단(선택)", "*자재명/품목명", "연간 입력", "월별 운송금액", None]
# 표준 템플릿에는 없는 「발생월」 열(지어냄) — USD 갈래의 월 환율은 이 열로만 닿는다
C4_MONTH_HEAD: list[Value] = [*C4_HEAD, "발생월"]
C4_SUB: list[Value] = [None, None, None, "연간운송금액(원)", "1월", "2월"]


def c4(*rows: list[Value], name: str = "c4-2_운송금액", head: list[Value] = C4_HEAD) -> Sheet:
    return sheet(name, {4: head, 5: C4_SUB, **{6 + i: row for i, row in enumerate(rows)}})


def transport_outcome(
    *rows: list[Value], book: dict[int, list[Value]] = T_ROWS, year: int = 2025, head: list[Value] = C4_HEAD
) -> SheetOutcome:
    (outcome,) = run_sheets([c4(*rows, head=head)], [sheet("운송_Spend", book)], year)
    return outcome


def transport(
    *rows: list[Value], book: dict[int, list[Value]] = T_ROWS, year: int = 2025, head: list[Value] = C4_HEAD
) -> ProcessedSheet:
    return processed(transport_outcome(*rows, book=book, year=year, head=head))


def vias(done: ProcessedSheet) -> list[list[tuple[str, str, str]]]:
    return [[(s.step, s.origin, s.via) for s in m.steps] for m in activity_metas(done)]


def test_krw_column_of_the_report_year_and_the_lookup_steps() -> None:
    """원화 열(2025) · 확장 힌트로만 걸림 · q="" 버릇 · 한국어명 · Title · 기본 제목, 줄 여섯."""
    done = transport(
        ["가상사업장", "가상 택배", "가상부품", 9100000],  # parcel 힌트 「courier」 로만 키워드(원문은 기본 줄뿐)
        ["가상사업장", None, "가상부품", 9200000],  # 운송수단 빈 칸: NaN 이 `or` 에서 이겨 q="" → 한국어명 첫 줄
        ["가상사업장", "가상 소포", "가상부품", 9300000],  # 코드 없음 → 확장 글 = 원문, 한국어명
        ["가상사업장", "virtual deep", "가상부품", 9400000],  # NAICS Title 부분 일치
        ["가상사업장", "가상 무엇", "가상부품", 9500000],  # 기본 제목(General Freight Trucking, Local)
        ["가상사업장", "가상트럭 배송", "가상부품", 9600000],  # road 힌트 + 키워드 「가상트럭」
    )
    frame = done.frame
    assert column(frame, "운송금액") == [9100000.0, 9200000.0, 9300000.0, 9400000.0, 9500000.0, 9600000.0]
    assert column(frame, "EF(kgCO2e/KRW)") == [9.22e-05, 9.12e-05, 9.22e-05, 9.32e-05, 9.12e-05, 9.12e-05]
    assert column(frame, "배출량(tCO2e)") == [
        9100000 * 9.22e-05 / 1000,
        9200000 * 9.12e-05 / 1000,
        9300000 * 9.22e-05 / 1000,
        9400000 * 9.32e-05 / 1000,
        9500000 * 9.12e-05 / 1000,
        9600000 * 9.12e-05 / 1000,
    ]
    assert column(frame, "배출계수단위") == ["kgCO2e/KRW"] * 6
    assert column(frame, "NAICS_Title") == [
        "Virtual Couriers",
        GFT,
        "Virtual Couriers",
        "Virtual Deep Sea Freight",
        GFT,
        GFT,
    ]
    assert column(frame, "NAICS") == ["9002", "9001", "9002", "9003", None, "9001"]  # 기본 줄은 코드 None(`:912`)
    assert column(frame, "Spend방식") == ["운송_Spend_KRW_EF"] * 6
    assert column(frame, "EF적용금액(KRW)") == column(frame, "운송금액")
    assert column(frame, "__excel_row__") == [6, 7, 8, 9, 10, 11]
    assert vias(done) == [
        [("factor", "rule", "keyword:expanded")],
        [("factor", "rule", "korean_name:expanded")],
        [("factor", "rule", "korean_name:expanded")],
        [("factor", "rule", "title:expanded")],
        [("factor", "estimate", "default_title:expanded")],
        [("factor", "rule", "keyword:expanded")],
    ]
    metas = activity_metas(done)
    assert [m.origin for m in metas] == ["rule", "rule", "rule", "rule", "estimate", "rule"]
    assert {m.factor.column for m in metas} == {KRW_2025}
    assert {(m.activity.unit, m.factor.unit) for m in metas} == {("KRW", "kgCO2e/KRW")}


def test_the_2024_report_year_takes_the_2024_krw_column() -> None:
    done = transport(["가상사업장", "가상 택배", "가상부품", 9100000], year=2024)
    assert column(done.frame, "EF(kgCO2e/KRW)") == [9.21e-05]
    assert column(done.frame, "배출량(tCO2e)") == [9100000 * 9.21e-05 / 1000]
    assert activity_metas(done)[0].factor.column == KRW_2024


def test_the_raw_text_is_tried_after_the_expanded_text_finds_nothing() -> None:
    """「가상 해상」 → sea 힌트를 단 확장 글은 어디에도 안 걸리고(기본 줄 없음) 원문이 한국어명에 걸린다."""
    done = transport(["가상사업장", "가상 해상", "가상부품", 9100000], book=NO_DEFAULT_ROWS)
    assert column(done.frame, "EF(kgCO2e/KRW)") == [9.32e-05]
    assert column(done.frame, "배출량(tCO2e)") == [9100000 * 9.32e-05 / 1000]
    assert vias(done) == [[("factor", "rule", "korean_name:raw")]]


def test_no_factor_anywhere_leaves_the_emission_empty() -> None:
    done = transport(["가상사업장", "가상 무엇", "가상부품", 9100000], book=NO_DEFAULT_ROWS)
    assert column(done.frame, "EF(kgCO2e/KRW)") == [None]
    assert column(done.frame, "배출량(tCO2e)") == [None]
    meta = activity_metas(done)[0]
    assert (meta.steps, meta.origin, meta.factor.value) == ((), None, None)


def test_monthly_sum_and_annual_column() -> None:
    """월별 줄은 1월~12월 합이 운송금액(`:6509` — 합이 0 이 아니면 그것), 연간 줄은 연간운송금액(원). 월 열은 지운다."""
    done = transport(
        ["가상사업장", "가상 택배", "가상부품", None, 9100, 9200],
        ["가상사업장", "가상 택배", "가상부품", 9300000],
    )
    frame = done.frame
    assert column(frame, "입력방식") == ["월별", "연간"]
    assert column(frame, "운송금액") == [9100.0 + 9200.0, 9300000.0]
    assert column(frame, "배출량(tCO2e)") == [(9100.0 + 9200.0) * 9.22e-05 / 1000, 9300000 * 9.22e-05 / 1000]
    assert not {"1월", "2월", "연간운송금액(원)"} & set(frame.columns)


def test_c9_is_the_same_calculation_shipped_out() -> None:
    (outcome,) = run_sheets(
        [c4(["가상사업장", "가상 택배", "가상부품", 9100000], name="c9-2_운송금액")], [sheet("운송_Spend", T_ROWS)]
    )
    done = processed(outcome)
    assert (done.processor.key, column(done.frame, "운송구분")) == ("c9_spend", ["출고"])
    assert column(done.frame, "배출량(tCO2e)") == [9100000 * 9.22e-05 / 1000]


ANNUAL_FX = round(sum(BOK_USD_KRW_MONTHLY_AVG_2025.values()) / len(BOK_USD_KRW_MONTHLY_AVG_2025), 2)


def test_usd_branch_month_and_annual() -> None:
    """원화 열이 없으면 USD 계수: 금액 / 환율. 월은 지어낸 「발생월」 열로만(9월 → 1391.83), 없으면 연평균(round 2)."""
    month = transport(
        ["가상사업장", "가상 택배", "가상부품", 9100000, None, None, 9], book=USD_ROWS, head=C4_MONTH_HEAD
    )
    annual = transport(["가상사업장", "가상 택배", "가상부품", 9200000], book=USD_ROWS)
    frame = pd.concat([month.frame, annual.frame], ignore_index=True)
    assert column(frame, "배출계수단위") == ["kgCO2e/USD"] * 2
    assert column(frame, "EF(kgCO2e/USD)") == [9.2, 9.2]
    assert column(frame, "적용환율(KRW/USD)") == [1391.83, ANNUAL_FX]
    assert column(frame, "USD환산금액") == [9100000 / 1391.83, 9200000 / ANNUAL_FX]
    assert column(frame, "배출량(tCO2e)") == [9100000 / 1391.83 * 9.2 / 1000, 9200000 / ANNUAL_FX * 9.2 / 1000]
    assert column(frame, "Spend방식") == ["운송_Spend_USD_EF_fallback"] * 2
    assert "EF(kgCO2e/KRW)" not in frame.columns
    assert [*vias(month), *vias(annual)] == [
        [("fx", "rule", "fx_month"), ("factor", "rule", "keyword:expanded")],
        [("fx", "rule", "fx_annual"), ("factor", "rule", "keyword:expanded")],
    ]
    metas = [*activity_metas(month), *activity_metas(annual)]
    assert [m.month for m in metas] == [9, None]
    assert [(m.activity.base_value, m.activity.base_unit) for m in metas] == [
        (9100000 / 1391.83, "USD"),
        (9200000 / ANNUAL_FX, "USD"),
    ]
    assert {m.factor.column for m in metas} == {USD}


def test_usd_branch_without_a_table_for_the_year_is_1400() -> None:
    done = transport(
        ["가상사업장", "가상 택배", "가상부품", 9100000, None, None, 9], book=USD_ROWS, year=2024, head=C4_MONTH_HEAD
    )
    assert column(done.frame, "적용환율(KRW/USD)") == [1400.0]
    assert column(done.frame, "배출량(tCO2e)") == [9100000 / 1400.0 * 9.2 / 1000]
    meta = activity_metas(done)[0]
    assert [(s.step, s.origin, s.via) for s in meta.steps] == [
        ("fx", "estimate", "fx_default_1400"),
        ("factor", "rule", "keyword:expanded"),
    ]
    assert meta.origin == "estimate"


def test_usd_branch_with_a_blank_month_cell_fails_the_sheet() -> None:
    """코랩 버릇: 「발생월」 열이 있고 칸이 비면 `to_float(NaN)` 이 NaN, `int(월) if 월` 에서 NaN 이 참이라
    `int(nan)` 이 ValueError — 코랩도 그 시트를 `[error]` 로 건너뛴다(`:8059-8060`·`:6199`).
    원화 열 갈래는 월을 읽지 않아 지나간다."""
    rows: tuple[list[Value], ...] = (
        ["가상사업장", "가상 택배", "가상부품", 9100000, None, None, 9],
        ["가상사업장", "가상 택배", "가상부품", 9200000],
    )
    outcome = transport_outcome(*rows, book=USD_ROWS, head=C4_MONTH_HEAD)
    assert (outcome.status, getattr(outcome, "error", None)) == (
        "failed",
        "ValueError: cannot convert float NaN to integer",
    )
    assert transport_outcome(*rows, head=C4_MONTH_HEAD).status == "processed"
