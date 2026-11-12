"""colab_157 시험의 표본 짓개와 가짜(지어낸 값만 — 이름은 `가상…`, 수는 `9.` 로 시작).

- `sheet(name, rows)` / `workbook(...)`: 줄 번호 → 칸 값 목록으로 `Sheet`·`Workbook` 을 짓는다(`s3sheets_support` 의
  칸 짓개).
- `xlsx_bytes(workbook)`: 우리 읽개와 openpyxl(pandas)이 **둘 다** 여는 xlsx 바이트. `s3sheets_support.xlsx_parts` 에
  `[Content_Types].xml`(공유 문자열 Override 포함)과 `_rels/.rels` 를 더한다 — `to_xlsx` 바이트는 openpyxl 이 열지
  못한다 (`[Content_Types].xml` 이 없다).
- `FakeGeocoder`: 지오코더 포트의 가짜(S3C-a 에서는 부르는 곳 0, b 가 쓴다).
- `ColabReplies`: 코랩 프롬프트 둘(그룹 이름·NAICS 고르기)에 심어 둔 답을 내는 모의 공급사(네트워크 0). 모르는 글이면
  실패(코랩에서 예외가 날 자리). 부를 때의 pandas 글 추론 옵션을 적는다(엔진 문맥에서 불렸는지 — 경계 ② 검증 N1).
- (S3C-b1) `formula(cached)`: 저장된 값이 있거나(글·수) 없는(None) 수식 칸. `sheet_cells(name, rows, extra)`: `sheet` 에
  칸을 덧붙인다(수식 칸 등). `llm_context(mock)`: 모의 공급사 하나로 엔진의 `LlmContext` 를 짓는다.
- (S3C-b1 ②) 지출·폐기물 한 줄씩: 계수 시트 셋(`activity_factor_sheets()` — 운송_Spend·출장_Spend·폐기물_C5,
  `factor_layout.py` 꼴, 머리글 3행)과 그것에 구매_USEPA 를 더한 계수 책 `activity_book(usepa)`, 템플릿 시트 짓개
  `transport_spend_sheet(name)`(C4-2·C9-2)·`travel_spend_sheet()`(C6-2)·`waste_sheet()`(C5). 줄은 모두 규칙으로 닿는다
  (AI 부름 0): 운송 「가상트럭」 키워드 · 출장 「택시」 수동 표·이동수단 앞 표 · 폐기물 정확히 같은 줄·단위 ton.
  `ACTIVITY_SAMPLES` 는 test_samples 가 본다.
- (S3C-b2a ②) 거리 운송: 계수 시트 `운송`(`transport_ef_sheet()` — 제목 한 줄 뒤 둘째 줄 머리글, 코랩 첫 읽기
  header_row=1 `:330`), 템플릿 C4-1·C9-1 짓개 `transport_distance_sheet(name, *rows)`(esg-lab 거리판 머리글 꼴 — 안내 한
  줄, 머리글 둘, 데이터는 4행부터)와 줄 짓개 `annual(...)`·`monthly(...)`. `transport_distance_sheet()` 의 기본 줄은
  거리 입력·「가상트럭」·ton 이라 AI·지오코더 부름 0 이다.
- (S3C-b2b) 출장·통근 거리: 계수 시트 `출장_통근`(`travel_ef_sheet()` — 제목 한 줄 뒤 둘째 줄 머리글, 코랩 첫 읽기
  header_row=1 `:334`), 템플릿 C6-1·C7 짓개 `travel_distance_sheet(name, *rows)`·`commute_sheet(name, *rows)`(esg-lab
  거리판 머리글 꼴)와 줄 짓개 `annual(...)`·`monthly(...)`(앞 일곱 칸 = 국가·출장주체(사업장)·교통수단·인원수·출발지·
  도착지·편도거리). 기본 줄은 거리 입력·「가상버스」·「가상승용차」 라 AI·지오코더 부름 0 이다.
- (S3C-c1b-1) 판매제품 폐기·투자: 계수 시트 `폐기물_C12`(`waste_c12_ef_sheet()` — 제목 한 줄 뒤 둘째 줄 머리글, 코랩 첫
  읽기 header_row=1 `:342`, 코드 칸은 글), 템플릿 C12·C15 짓개 `c12_sheet(name, *rows)`·`c15_sheet(name, *rows)`(안내
  한 줄 뒤 한 줄 머리 — esg-lab 나머지 판 꼴). 코드는 지은 `9x` 꼴이고 `91-02` 만 코랩 생물기원 접두(폐지류)다.
"""

from collections.abc import Mapping, Sequence

import pandas as pd

from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderError, ProviderRequest, ProviderResponse, Tags
from esgapi.inventory.engines.scope3.colab_157.llm import LlmCalls, LlmContext
from esgapi.inventory.engines.scope3.colab_157.ports import Coordinates, NotFound
from esgapi.inventory.tests.s3sheets_support import number, text, xlsx_parts, zip_bytes
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client, user_text
from esgapi.inventory.tools.scope3_sheets.grid import Cell, FormulaCell, Sheet, Workbook, column_letters

type Value = str | int | float | None

CONTENT_TYPES = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    b'<Default Extension="xml" ContentType="application/xml"/>'
    b'<Override PartName="/xl/workbook.xml" '
    b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    b'<Override PartName="/xl/sharedStrings.xml" '
    b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
    b"</Types>"
)
ROOT_RELS = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    b'<Relationship Id="rId1" '
    b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    b'Target="xl/workbook.xml"/></Relationships>'
)


def cell_of(value: str | int | float) -> Cell:
    if isinstance(value, str):
        return text(value)
    return number(repr(value) if isinstance(value, float) else str(value))


def sheet(name: str, rows: Mapping[int, Sequence[Value]], first_column: int = 1) -> Sheet:
    cells: dict[str, Cell] = {}
    for row, values in rows.items():
        for offset, value in enumerate(values):
            if value is not None:
                cells[f"{column_letters(first_column + offset)}{row}"] = cell_of(value)
    return Sheet(name, cells, (), ())


def workbook(*sheets: Sheet) -> Workbook:
    return Workbook(tuple(sheets), ())


def formula(cached: str | int | float | None) -> FormulaCell:
    """저장된 값이 `cached` 인 수식 칸(None 이면 `<v>` 가 없는 칸 — 재계산 안 된 수식)."""
    if cached is None:
        return FormulaCell("=가상식()", None, None)
    stored = (
        text(cached) if isinstance(cached, str) else number(repr(cached) if isinstance(cached, float) else str(cached))
    )
    return FormulaCell("=가상식()", None, stored)


def sheet_cells(name: str, rows: Mapping[int, Sequence[Value]], extra: Mapping[str, Cell]) -> Sheet:
    """`sheet` 에 주소 → 칸을 덧붙인 시트(같은 주소면 덧붙인 칸이 이긴다)."""
    base = sheet(name, rows)
    return Sheet(name, {**base.cells, **extra}, (), ())


LLM_TAGS = Tags(tenant="가상회사", module="inventory")


def llm_context(mock: MockProvider) -> LlmContext:
    """모의 공급사 하나만 가진 엔진 문맥(경로 `mock`, 실행 하나의 부름 기록)."""
    return LlmContext(mock_client(mock), ROUTE, LLM_TAGS, LlmCalls())


def xlsx_bytes(book: Workbook) -> bytes:
    parts = xlsx_parts(book)
    parts["[Content_Types].xml"] = CONTENT_TYPES
    parts["_rels/.rels"] = ROOT_RELS
    return zip_bytes(parts)


class FakeGeocoder:
    """심어 둔 지명만 안다. 부른 글을 기록한다."""

    def __init__(self, known: Mapping[str, Coordinates] | None = None) -> None:
        self.known = dict(known or {})
        self.queries: list[str] = []

    def geocode(self, query: str) -> Coordinates | NotFound:
        self.queries.append(query)
        found = self.known.get(query)
        return found if found is not None else NotFound(query)


class ColabReplies(MockProvider):
    """그룹 이름 답은 품목명이 같을 때, NAICS 고르기 답은 「Original ERP text」 줄이 그 낱말을 품을 때 낸다."""

    def __init__(self, groups: Mapping[str, str] | None = None, naics: Mapping[str, str] | None = None) -> None:
        super().__init__()
        self.groups = dict(groups or {})
        self.naics = dict(naics or {})
        self.infer_string: list[bool] = []

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.infer_string.append(bool(pd.get_option("future.infer_string")))
        self.enqueue(self.reply)
        return super().invoke(request, options)

    def reply(self, request: ProviderRequest) -> ProviderResponse:
        text = user_text(request)
        if "Original ERP text:" in text:
            product = text.split("Original ERP text:\n", 1)[1].split("\n", 1)[0]
            answer = next((a for key, a in self.naics.items() if key in product), None)
        else:
            product = text.split("품목명: ", 1)[1].split("\n", 1)[0] if "품목명: " in text else ""
            answer = self.groups.get(product)
        if answer is None:
            return ProviderError(status=None, retryable=False, message="가상: 심어 둔 답이 없다")
        return Completed(text=answer, usage=SYNTHETIC_USAGE)


# ── S3C-b1 ②: 지출·폐기물 시트 넷과 계수 시트 셋(한 줄씩) ──

SPEND_USD = "EF (kgCO2e/USD)"
SPEND_KRW_2025 = "EF (kgCO2e/KRW)\n2025년말 기준\n(9,400 KRW/USD)"
TRANSPORT_SPEND_ROWS: dict[int, list[Value]] = {
    1: ["가상 운송 지출 계수 표"],
    3: ["운송 구분", "NAICS 코드", "NAICS Title (US EPA)", "한국어 품목명", "한국어 매핑 키워드", SPEND_USD, "비고",
        SPEND_KRW_2025],
    4: ["가상도로", 9001, "General Freight Trucking, Local", "가상 도로 화물", "가상트럭", 9.1, None, 9.12e-05],
}  # fmt: skip
TRAVEL_SPEND_ROWS: dict[int, list[Value]] = {
    1: ["가상 출장 지출 계수 표"],
    3: ["출장 항목", "NAICS 코드", "NAICS Title (US EPA)", "한국어 품목명", "한국어 매핑 키워드", SPEND_USD, "비고",
        SPEND_KRW_2025],
    4: ["가상택시", 9101, "Taxi Service", "가상 택시", "가상콜", 9.1, None, 9.1e-05],
}  # fmt: skip
WASTE_C5_ROWS: dict[int, list[Value]] = {
    1: ["가상 폐기물 계수 표"],
    3: ["폐기물 종류", "처리방법", "매칭 키워드", "구분", "매핑 EPD 원본명", "배출계수 (kgCO2eq/kg)", "비고"],
    4: ["가상폐지", "소각", "가상종이", "가상구분", "가상 EPD", 9.1, None],
}
TRANSPORT_SPEND_TEMPLATE: dict[int, list[Value]] = {
    4: ["*사업장", "*자재명/품목명", "운송수단(선택)", "연간 입력", "월별 운송금액", None],
    5: [None, None, None, "연간운송금액(원)", "1월", "2월"],
    6: ["가상사업장", "가상 철강 코일", "가상트럭", 9500000],
}
TRAVEL_SPEND_TEMPLATE: dict[int, list[Value]] = {
    4: ["*사업장", "*출장항목", "연간 입력", "월별 지출금액", None],
    5: [None, None, "연간지출금액(원)", "1월", "2월"],
    6: ["가상사업장", "가상 택시비", 9300000],
}
WASTE_TEMPLATE: dict[int, list[Value]] = {
    4: ["*사업장", "*폐기물 종류", "*처리방법", "단위", "연간 입력", "월별 처리량", None],
    5: [None, None, None, None, "연간처리량", "1월", "2월"],
    6: ["가상사업장", "가상폐지", "소각", "ton", 9.5],
}


def activity_factor_sheets() -> tuple[Sheet, Sheet, Sheet]:
    return (
        sheet("운송_Spend", TRANSPORT_SPEND_ROWS),
        sheet("출장_Spend", TRAVEL_SPEND_ROWS),
        sheet("폐기물_C5", WASTE_C5_ROWS),
    )


def activity_book(usepa: Sheet) -> Workbook:
    """구매_USEPA(부르는 쪽의 것) + 지출·폐기물 계수 시트 셋."""
    return workbook(usepa, *activity_factor_sheets())


def transport_spend_sheet(name: str = "c4-2_운송금액") -> Sheet:
    return sheet(name, TRANSPORT_SPEND_TEMPLATE)


def travel_spend_sheet(name: str = "c6-2_출장비") -> Sheet:
    return sheet(name, TRAVEL_SPEND_TEMPLATE)


def waste_sheet(name: str = "c5_사업장폐기물") -> Sheet:
    return sheet(name, WASTE_TEMPLATE)


# ── S3C-b2a ②: 거리 운송(C4-1·C9-1)과 계수 시트 `운송` ──

TRANSPORT_EF_HEAD: list[Value] = ["운송수단", "표준코드", "배출계수\n(kgCO2eq/ton·km)", "비고"]
# parcel 은 일부러 뺐다 — 코랩 기본값(0.18, `:6563`)이 남는다
TRANSPORT_EF_ROWS: dict[int, list[Value]] = {
    1: ["가상 운송 계수 표"],
    2: TRANSPORT_EF_HEAD,
    3: ["가상 도로", "road", 0.911],
    4: ["가상 철도", "rail", 0.913],
    5: ["가상 해상", "sea", 0.914],
    6: ["가상 항공", "air", 0.915],
}
MONTH_NAMES: list[Value] = [f"{i}월" for i in range(1, 13)]
DIST_MAIN: list[Value] = [
    "*국가", "*사업장", "운송수단(선택)", "*자재명/품목명", "*중량단위", "출발지", "도착지", "운송거리(km)(선택)",
    "연간 입력", "월별 운송량", *([None] * 11), "비고(선택)",
]  # fmt: skip
DIST_SUB: list[Value] = [*([None] * 8), "연간운송량", *MONTH_NAMES, None]
C9_DIST_MAIN: list[Value] = [*DIST_MAIN[:3], "*제품명", *DIST_MAIN[4:]]


def annual(prefix: Sequence[Value], amount: Value) -> list[Value]:
    """(국가, 사업장, 운송수단, 품목, 중량단위, 출발지, 도착지, 운송거리) + 연간운송량."""
    return [*prefix, amount, *([None] * 12)]


def monthly(prefix: Sequence[Value], months: Mapping[int, Value]) -> list[Value]:
    return [*prefix, None, *(months.get(i) for i in range(1, 13))]


DIST_ROW: list[Value] = annual(
    ["가상국", "가상사업장", "가상트럭", "가상 철강 코일", "ton", "가상시가", "가상시나", 91], 9.1
)


def transport_ef_sheet() -> Sheet:
    return sheet("운송", TRANSPORT_EF_ROWS)


def transport_distance_sheet(name: str = "c4-1_운송거리", *rows: list[Value]) -> Sheet:
    head = C9_DIST_MAIN if name.lower().startswith("c9") else DIST_MAIN
    body = rows or (DIST_ROW,)
    return sheet(name, {1: [f"가상 안내 — {name}"], 2: head, 3: DIST_SUB, **{4 + i: r for i, r in enumerate(body)}})


# ── S3C-b2b: 출장·통근 거리(C6-1·C7)와 계수 시트 `출장_통근` ──

TRAVEL_EF_HEAD: list[Value] = ["이동수단", "표준코드", "EF\n(kgCO2e/km)", "비고"]
TRAVEL_EF_ROWS: dict[int, list[Value]] = {
    1: ["가상 출장 통근 계수 표"],
    2: TRAVEL_EF_HEAD,
    3: ["가상 항공", "flight", 0.921],
    4: ["가상 기차", "train", 0.922],
    5: ["가상 버스", "bus", 0.923],
    6: ["가상 승용차", "car", 0.924],
    7: ["가상 지하철", "subway", 0.926],
}
TRAVEL_MAIN: list[Value] = [
    "*국가", "*출장주체", "*교통수단", "*인원수", "출발지", "도착지", "편도거리(km)(선택)", "연간 입력",
    "월별 이동횟수", *([None] * 11), "비고(선택)",
]  # fmt: skip
TRAVEL_SUB: list[Value] = [*([None] * 7), "연간이동횟수", *MONTH_NAMES, None]
COMMUTE_MAIN: list[Value] = [
    "*국가", "*사업장", "*교통수단", "*인원수", "출발지", "도착지", "편도거리(km)(선택)", "연간 입력", "월별 근무일수",
    *([None] * 11), "비고(선택)",
]  # fmt: skip
COMMUTE_SUB: list[Value] = [*([None] * 7), "연간근무일수", *MONTH_NAMES, None]
TRAVEL_ROW: list[Value] = annual(["가상국", "가상본부", "가상버스", 9, "가상시사", "가상시아", 99], 9)
COMMUTE_ROW: list[Value] = annual(["가상국", "가상사업장", "가상승용차", 9, None, None, 9.9], 99)


def travel_ef_sheet() -> Sheet:
    return sheet("출장_통근", TRAVEL_EF_ROWS)


def travel_distance_sheet(name: str = "c6-1_출장거리", *rows: list[Value]) -> Sheet:
    body = rows or (TRAVEL_ROW,)
    return sheet(
        name, {1: [f"가상 안내 — {name}"], 2: TRAVEL_MAIN, 3: TRAVEL_SUB, **{4 + i: r for i, r in enumerate(body)}}
    )


def commute_sheet(name: str = "c7_임직원통근", *rows: list[Value]) -> Sheet:
    body = rows or (COMMUTE_ROW,)
    return sheet(
        name, {1: [f"가상 안내 — {name}"], 2: COMMUTE_MAIN, 3: COMMUTE_SUB, **{4 + i: r for i, r in enumerate(body)}}
    )


ACTIVITY_SAMPLES: tuple[Sheet, ...] = (
    *activity_factor_sheets(),
    transport_spend_sheet(),
    travel_spend_sheet(),
    waste_sheet(),
    transport_ef_sheet(),  # S3C-b2a
    transport_distance_sheet("c4-1_운송거리"),
    transport_distance_sheet("c9-1_운송거리"),
    travel_ef_sheet(),  # S3C-b2b
    travel_distance_sheet(),
    commute_sheet(),
)


# ── S3C-c1a ②: 에너지 계열(C3·C8·C13)과 계수 시트 `에너지`(넷째 줄 머리글)·`에너지_C3`(셋째 줄) ──
# 에너지원 이름(전력·경유·도시가스(LNG)·천연가스(LNG))은 코랩 규칙이 읽는 분류어다(`ENERGY_BASE_UNIT` — esg-lab rest
# 판과 같음). 계수 값은 지은 것이다.

ENERGY_EF_HEAD: list[Value] = [
    "구분", "배출활동", "활동유형(에너지원)", "투입량 기준단위", "순발열량", "CO2eq ★\n(kgCO2eq/단위)",
]  # fmt: skip
ENERGY_EF_ROWS: dict[int, list[Value]] = {
    1: ["가상 계수 책 — 에너지"],
    2: ["가상 안내 1"],
    3: ["가상 안내 2"],
    4: ENERGY_EF_HEAD,
    5: ["가상 간접", "가상 전력 사용", "전력", "kWh", None, 0.0941],
    6: ["가상 직접", "가상 이동연소", "경유", "L", 9.1, 0.942],
    7: ["가상 직접", "가상 고정연소", "도시가스(LNG)", "Nm³", 9.2, 0.943],
    8: ["가상 직접", "가상 고정연소", "천연가스(LNG)", "kg", 9.3, 0.944],
}
ENERGY_C3_EF_HEAD: list[Value] = ["활동유형(에너지원)", "기준단위", "EF\n(kgCO2eq/단위)", "비고"]
# `도시가스(LNG)` 줄은 일부러 없다 — C3 이 `천연가스(LNG)`(kg)로 대체 매칭되고 발열량 다리를 탄다
ENERGY_C3_EF_ROWS: dict[int, list[Value]] = {
    1: ["가상 계수 책 — 에너지_C3"],
    2: ["가상 안내"],
    3: ENERGY_C3_EF_HEAD,
    4: ["전력", "kWh", 0.0951, None],
    5: ["경유", "L", 0.0952, None],
    6: ["천연가스(LNG)", "kg", 0.0953, None],
}


def energy_factor_sheets() -> tuple[Sheet, Sheet]:
    return sheet("에너지", ENERGY_EF_ROWS), sheet("에너지_C3", ENERGY_C3_EF_ROWS)


ENERGY_MONTHS: list[Value] = [*MONTH_NAMES]
C3_MAIN: list[Value] = ["*국가", "*사업장", "*연료/에너지명", "*단위", "연간 입력", "월별 사용량", *([None] * 11),
                        "비고(선택)"]  # fmt: skip
LEASED_ENERGY_MAIN: dict[str, list[Value]] = {
    family: ["*국가", f"*{asset}", "*에너지종류", "*단위", "연간 입력", "월별 사용량", *([None] * 11), "비고(선택)"]
    for family, asset in (("c8", "임차자산명"), ("c13", "임대자산명"))
}
ENERGY_SUB: list[Value] = [None, None, None, None, "연간사용량", *ENERGY_MONTHS, None]
LEASED_AREA_MAIN: dict[str, list[Value]] = {
    family: ["*국가", f"*{asset}", "*건물전체 면적", "*사용 면적", "*에너지종류", "*단위", "연간 입력",
             "건물전체 월별사용량", *([None] * 11), "비고(선택)"]
    for family, asset in (("c8", "임차자산명"), ("c13", "임대자산명"))
}  # fmt: skip
LEASED_PERSON_MAIN: dict[str, list[Value]] = {
    family: ["*국가", f"*{asset}", "*건물전체 인원수", "*자사 인원수", "*에너지종류", "*단위", "연간 입력",
             "건물전체 월별사용량", *([None] * 11), "비고(선택)"]
    for family, asset in (("c8", "임차자산명"), ("c13", "임대자산명"))
}  # fmt: skip
SHARE_SUB: list[Value] = [*([None] * 6), "건물전체 연간사용량", *ENERGY_MONTHS, None]


def energy_annual(prefix: Sequence[Value], amount: Value) -> list[Value]:
    """앞 칸들 + 연간 값(월 열둘·비고는 빔)."""
    return [*prefix, amount, *([None] * 12)]


def energy_monthly(prefix: Sequence[Value], months: Mapping[int, Value]) -> list[Value]:
    return [*prefix, None, *(months.get(i) for i in range(1, 13))]


C3_ROW: list[Value] = energy_annual(["가상국", "가상사업장", "전력", "kWh"], 9100)
LEASED_ENERGY_ROW: list[Value] = energy_annual(["가상국", "가상자산", "전력", "kWh"], 91000)
LEASED_AREA_ROW: list[Value] = energy_annual(["가상국", "가상자산", 9000, 900, "경유", "L"], 9100)
LEASED_PERSON_ROW: list[Value] = energy_annual(["가상국", "가상자산", 90, 9, "전력", "kWh"], 99000)


def _energy_template(name: str, main: list[Value], sub: list[Value], rows: Sequence[list[Value]]) -> Sheet:
    return sheet(name, {1: [f"가상 안내 — {name}"], 2: main, 3: sub, **{4 + i: r for i, r in enumerate(rows)}})


def c3_sheet(name: str = "c3_연료에너지", *rows: list[Value]) -> Sheet:
    return _energy_template(name, C3_MAIN, ENERGY_SUB, rows or (C3_ROW,))


def leased_sheet(name: str, *rows: list[Value]) -> Sheet:
    """`c8-1_…`·`c8-2_…`·`c8-3_…`·`c13-…` — 이름 머리(c8·c13)와 번호(1 에너지·2 면적·3 인원)로 머리글을 고른다."""
    family, number = name.split("-", 1)[0].lower(), name.split("-", 1)[1][0]
    if number == "1":
        return _energy_template(name, LEASED_ENERGY_MAIN[family], ENERGY_SUB, rows or (LEASED_ENERGY_ROW,))
    main = LEASED_AREA_MAIN[family] if number == "2" else LEASED_PERSON_MAIN[family]
    default = LEASED_AREA_ROW if number == "2" else LEASED_PERSON_ROW
    return _energy_template(name, main, SHARE_SUB, rows or (default,))


# ── S3C-c1b-1: 판매제품 폐기(C12)·투자(C15)와 계수 시트 `폐기물_C12` ──

WASTE_C12_EF_HEAD: list[Value] = [
    "대분류\n코드", "대분류", "중분류\n코드", "중분류", "소분류\n코드", "폐기물 명칭",
    "매립 EF\n(kgCO2eq/kg)", "소각 EF\n(kgCO2eq/kg)", "재활용 EF\n(kgCO2eq/kg)",
]  # fmt: skip
WASTE_C12_EF_ROWS: dict[int, list[Value]] = {
    1: ["가상 판매제품 폐기 계수 표"],
    2: WASTE_C12_EF_HEAD,
    3: ["91", "가상 생활", "91-02", "가상 종이", "91-02-01", "가상 폐지 묶음", 0.961, 0.962, 0.0963],
    4: ["92", "가상 사업장", "92-01", "가상 수지", "92-01-01", "가상 폐수지 묶음", 0.964, 0.965, 0.0966],
    5: ["93", "가상 건설", "93-01", "가상 잔재", "93-01-01", "가상 잔재 묶음", 0.967, 0.968, 0.0969],
}


def waste_c12_ef_sheet() -> Sheet:
    return sheet("폐기물_C12", WASTE_C12_EF_ROWS)


C12_MAIN: list[Value] = [
    "*국가", "폐기물 대분류(선택)", "폐기물 중분류(선택)", "폐기물 소분류(선택)", "*제품명", "*판매량", "*제품중량",
    "*제품중량 단위", "재활용 비중(%)(선택)", "소각 비중(%)(선택)", "매립 비중(%)(선택)", "기타 비중(%)(선택)",
    "설명/적요(선택)",
]  # fmt: skip
# 소분류 코드로 맞음 + 생물기원 코드(91-02 폐지류) + 처리비중 셋(재활용 90·소각 9·매립 9)
C12_ROW: list[Value] = [
    "가상국", "91 | 가상 생활", "91-02 | 가상 종이", "91-02-01 | 가상 폐지 묶음", "가상종이상자", 9100, 0.9, "kg",
    90, 9, 9, None, "가상 적요 1",
]  # fmt: skip
C15_MAIN: list[Value] = [
    "*피투자기업명 (필수)",
    "지분율(%) (선택)",
    "*피투자기업 Scope1배출량",
    "*피투자기업 Scope2배출량",
    "비고(선택)",
]
C15_ROW: list[Value] = ["가상투자처A", 9.5, 910, 920, "가상 비고 1"]


def _one_head_template(name: str, main: list[Value], rows: Sequence[list[Value]]) -> Sheet:
    return sheet(name, {1: [f"가상 안내 — {name}"], 2: main, **{3 + i: r for i, r in enumerate(rows)}})


def c12_sheet(name: str = "c12_판매제품폐기", *rows: list[Value]) -> Sheet:
    return _one_head_template(name, C12_MAIN, rows or (C12_ROW,))


def c15_sheet(name: str = "c15_투자", *rows: list[Value]) -> Sheet:
    return _one_head_template(name, C15_MAIN, rows or (C15_ROW,))


# ── S3C-c1b-2: 판매제품 사용(C11)·프랜차이즈(C14) — 계수 시트는 `에너지`(energy_factor_sheets) ──

C11_MAIN: list[Value] = [
    "*국가", "그룹(선택)", "*보고연도", "*제품명", "*제품수량", "*에너지명", "*제품당 연간 에너지 사용량", "*단위",
    "수명(개월) 혹은 평균 사용기간(개월)", "설명/적요(선택)",
]  # fmt: skip
# 수량 900 × 9.1 kWh × 96/12 년(전력 0.0941)
C11_ROW: list[Value] = ["가상국", "가상그룹A", None, "가상제품A", 900, "전력", 9.1, "kWh", 96, "가상 적요 1"]
C14_MAIN: list[Value] = [
    "*국가",
    "*프랜차이즈명",
    "*가맹점 수",
    "*연료 종류",
    "*연료 사용량",
    "*연료 단위",
    "비고(선택)",
]
# 경유 9100 L(0.942)
C14_ROW: list[Value] = ["가상국", "가상가맹A", 9, "경유", 9100, "L", "가상 비고 1"]


def c11_sheet(name: str = "c11_판매제품사용", *rows: list[Value]) -> Sheet:
    return _one_head_template(name, C11_MAIN, rows or (C11_ROW,))


def c14_sheet(name: str = "c14_프랜차이즈", *rows: list[Value]) -> Sheet:
    return _one_head_template(name, C14_MAIN, rows or (C14_ROW,))


# ── S3R2: 결과 줄의 입력 칸 `input`(키 열여섯 — S3R3 useMonths. 계약 ColabRowInputJson 의 차례를 손으로 다시 적음) ──

INPUT_KEYS: tuple[str, ...] = (
    "country", "site", "name", "vehicle", "energy", "people", "buildingArea", "usedArea", "buildingPeople", "ownPeople",
    "productCount", "sales", "weight", "weightUnit", "stores", "useMonths",
)  # fmt: skip


def row_input(**values: str | None) -> dict[str, str | None]:
    """기대하는 `input`: 준 키만 값, 나머지는 null(모르는 키는 실패)."""
    unknown = set(values) - set(INPUT_KEYS)
    assert not unknown, f"모르는 input 키 {sorted(unknown)}"
    return {key: values.get(key) for key in INPUT_KEYS}
