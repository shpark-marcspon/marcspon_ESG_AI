"""계수 책(마크스폰이 준 Scope 3 배출계수 xlsx, 11시트)의 꼴. **자료다**(코드가 아니다).

여기 적힌 것은 꼴뿐이다: 시트 이름, 머리글 줄 번호, 열 글자, 머리글의 글자, 단위 표기. 계수의 값·항목 이름은 없다.
머리글의 글자는 2026-10-13 에 받은 파일에서 읽어 적었다. 책이 새 판으로 바뀌면 이 파일을 다시 적는다
(글자 하나가 달라도 적재기는 그 시트를 `HeaderMismatch` 로 내고 적재하지 않는다 — 추측해서 맞추지 않는다).

- 머리글 줄 위의 줄은 제목·묶음 머리글이다(자리만 안다. 글자는 묶음 머리글만 견준다).
- 머리글 줄 아래에서 계수 행·주석 줄을 가르는 것은 꼴이 아니라 규칙이다(`factors.py`): 줄 번호를 여기 적지 않는다.
  그래서 빈 줄 뒤에 오는 줄(평균 줄)도 읽힌다.
- 원화 열 셋(`derived`)의 머리글에는 책이 적은 날짜와 환율이 들어 있다. 머리글의 글자로서 옮긴 것이고,
  어느 열이 쓰이는지는 여기서도 적재기에서도 고르지 않는다.
- 값 열의 `unit` 은 머리글 안의 단위 표기다(머리글의 부분 글자여야 한다 — 테스트가 지킨다). 접지도 환산하지도 않는다.
  `kgCO2eq` 와 `kgCO2e` 가 섞여 있는 것도 그대로다.
"""

from dataclasses import dataclass
from typing import Final, Literal

Role = Literal["label", "unit", "value", "derived"]


@dataclass(frozen=True, slots=True)
class Column:
    letter: str
    header: str
    role: Role  # label 이름표 · unit 단위 열(이름표이면서 값 열의 단위) · value 값 · derived 파생 수식
    unit: str | None = None  # 값 열만: 머리글 안의 단위 표기


@dataclass(frozen=True, slots=True)
class FactorSheetShape:
    name: str
    header_row: int
    columns: tuple[Column, ...]
    group_headers: tuple[tuple[str, str], ...] = ()  # 머리글 줄 위의 묶음 머리글 (칸, 글자)


@dataclass(frozen=True, slots=True)
class IndexSheetShape:
    """`목록` 시트: 템플릿의 탭과 책의 탭을 잇는 안내."""

    name: str
    header_row: int
    template_column: str
    template_header: str
    book_column: str
    book_header: str


# 원화 열 셋의 머리글(날짜와 환율이 머리글 글자 안에 있다). 출처: 받은 계수 책의 `구매_USEPA!I3:K3` ·
# `운송_Spend!H3:J3` · `출장_Spend!H3:J3`(세 시트의 글자가 같다). 확인 2026-10-13. 책이 적은 글자를 옮긴 것이고
# 우리가 고른 환율이 아니다 — 어느 열을 쓸지는 정해지지 않았다(마크스폰의 답 전).
_KRW_2023: Final = "EF (kgCO2e/KRW)\n2023년말 기준\n(2023-12-29\n1,264.50 KRW/USD)"
_KRW_2024: Final = "EF (kgCO2e/KRW)\n2024년말 기준\n(2024-12-30\n1,472.50 KRW/USD)"
_KRW_2025: Final = "EF (kgCO2e/KRW)\n2025년말 기준\n(2025-12-31\n1,439.00 KRW/USD)"
_KRW_UNIT: Final = "(kgCO2e/KRW)"

INDEX_SHEET: Final = IndexSheetShape(
    name="목록",
    header_row=5,
    template_column="B",
    template_header='"Scope3_템플릿" 파일의 각 탭',
    book_column="C",
    book_header='"배출계수_Scope3_DB" 파일의 각 탭',
)

FACTOR_SHEETS: Final[tuple[FactorSheetShape, ...]] = (
    FactorSheetShape(
        name="에너지",
        header_row=4,
        group_headers=(("A3", "← 배출활동 분류"), ("E3", "← 발열량 기준"), ("G3", "← 배출계수 (kgCO2eq/단위)")),
        columns=(
            Column("A", "구분", "label"),
            Column("B", "배출활동", "label"),
            Column("C", "활동유형\n(에너지원)", "label"),
            Column("D", "투입량 기준단위", "unit"),
            Column("E", "순발열량\n(MJ/단위)", "value", "(MJ/단위)"),
            Column("F", "CO2 계수\n(tC/TJ)", "value", "(tC/TJ)"),
            Column("G", "CO2만\n(kgCO2/단위)", "value", "(kgCO2/단위)"),
            Column("H", "Non-CO2\n(kgCO2eq/단위)", "value", "(kgCO2eq/단위)"),
            Column("I", "CO2eq\n(kgCO2eq/단위) ★", "value", "(kgCO2eq/단위) ★"),
        ),
    ),
    FactorSheetShape(
        name="에너지_C3",
        header_row=3,
        columns=(
            Column("A", "No.", "label"),
            Column("B", "활동유형\n(에너지원)", "label"),
            Column("C", "기준단위", "unit"),
            Column("D", "EF\n(kgCO2eq/단위) ★", "value", "(kgCO2eq/단위) ★"),
            Column("E", "출처/비고", "label"),
        ),
    ),
    FactorSheetShape(
        name="운송",
        header_row=2,
        columns=(
            Column("A", "대분류", "label"),
            Column("B", "구분", "label"),
            Column("C", "운송수단\n(EPD 원본명)", "label"),
            Column("D", "표준코드\n(코드 매핑용)", "label"),
            Column("E", "배출계수\n(kgCO2eq/ton·km)", "value", "(kgCO2eq/ton·km)"),
            Column("F", "비고", "label"),
        ),
    ),
    FactorSheetShape(
        name="출장_통근",
        header_row=2,
        columns=(
            Column("A", "구분", "label"),
            Column("B", "DEFRA 원본 분류", "label"),
            Column("C", "세부 유형 (Type)", "label"),
            Column("D", "표준코드", "label"),
            Column("E", "한국어 매핑 키워드", "label"),
            Column("F", "EF\n(kgCO2e/km)", "value", "(kgCO2e/km)"),
            Column("G", "비고", "label"),
        ),
    ),
    FactorSheetShape(
        name="폐기물_C5",
        header_row=3,
        group_headers=(("A2", "← 템플릿 입력값"), ("E2", "← 환경부 EPD 매핑값")),
        columns=(
            Column("A", "폐기물 종류\n(템플릿 드롭다운)", "label"),
            Column("B", "처리방법\n(템플릿 드롭다운)", "label"),
            Column("C", "매칭 키워드\n(추가 동의어)", "label"),
            Column("D", "구분\n(지정/일반/생활)", "label"),
            Column("E", "매핑 EPD 원본명", "label"),
            Column("F", "배출계수\n(kgCO2eq/kg)", "value", "(kgCO2eq/kg)"),
            Column("G", "비고", "label"),
        ),
    ),
    FactorSheetShape(
        name="폐기물_C12",
        header_row=2,
        columns=(
            Column("A", "대분류\n코드", "label"),
            Column("B", "중분류\n코드", "label"),
            Column("C", "소분류\n코드", "label"),
            Column("D", "폐기물 명칭", "label"),
            Column("E", "구분", "label"),
            Column("F", "매립 EF\n(kgCO2eq/kg)", "value", "(kgCO2eq/kg)"),
            Column("G", "소각 EF\n(kgCO2eq/kg)", "value", "(kgCO2eq/kg)"),
            Column("H", "재활용 EF\n(kgCO2eq/kg)", "value", "(kgCO2eq/kg)"),
        ),
    ),
    FactorSheetShape(
        name="구매_USEPA",
        header_row=3,
        group_headers=(("A2", "← 템플릿 입력값"), ("D2", "← NAICS 매핑"), ("G2", "← 참고")),
        columns=(
            Column("A", "품목군\n(C1/C2 템플릿)", "label"),
            Column("B", "상세 카테고리\n(세부 품목 유형)", "label"),
            Column("C", "한국어 매핑 키워드", "label"),
            Column("D", "NAICS 코드\n(2017)", "label"),
            Column("E", "NAICS Title\n(US EPA 원본)", "label"),
            Column("F", "EF\n(kgCO2eq/USD)", "value", "(kgCO2eq/USD)"),
            Column("G", "EF 단위\n설명", "unit"),
            Column("H", "비고", "label"),
            Column("I", _KRW_2023, "derived", _KRW_UNIT),
            Column("J", _KRW_2024, "derived", _KRW_UNIT),
            Column("K", _KRW_2025, "derived", _KRW_UNIT),
        ),
    ),
    FactorSheetShape(
        name="운송_Spend",
        header_row=3,
        columns=(
            Column("A", "운송 구분", "label"),
            Column("B", "NAICS 코드", "label"),
            Column("C", "NAICS Title (US EPA)", "label"),
            Column("D", "한국어 품목명", "label"),
            Column("E", "한국어 매핑 키워드", "label"),
            Column("F", "EF\n(kgCO2e/USD)", "value", "(kgCO2e/USD)"),
            Column("G", "비고", "label"),
            Column("H", _KRW_2023, "derived", _KRW_UNIT),
            Column("I", _KRW_2024, "derived", _KRW_UNIT),
            Column("J", _KRW_2025, "derived", _KRW_UNIT),
        ),
    ),
    FactorSheetShape(
        name="출장_Spend",
        header_row=3,
        columns=(
            Column("A", "출장 항목", "label"),
            Column("B", "NAICS 코드", "label"),
            Column("C", "NAICS Title (US EPA)", "label"),
            Column("D", "한국어 품목명", "label"),
            Column("E", "한국어 매핑 키워드", "label"),
            Column("F", "EF\n(kgCO2e/USD)", "value", "(kgCO2e/USD)"),
            Column("G", "비고", "label"),
            Column("H", _KRW_2023, "derived", _KRW_UNIT),
            Column("I", _KRW_2024, "derived", _KRW_UNIT),
            Column("J", _KRW_2025, "derived", _KRW_UNIT),
        ),
    ),
    FactorSheetShape(
        name="전력_국가별",
        header_row=2,
        columns=(
            Column("A", "국가", "label"),
            Column("B", "배출원", "label"),
            Column("C", "배출계수", "value"),  # 머리글에 단위가 없다. 단위는 D 열의 글자다
            Column("D", "단위", "unit"),
            Column("E", "기준연도", "label"),
            Column("F", "상태", "label"),
            Column("G", "계산기본값", "label"),
            Column("H", "발표일", "label"),
            Column("I", "발표기관", "label"),
            Column("J", "근거문서", "label"),
            Column("K", "산정용도", "label"),
            Column("L", "비고", "label"),
        ),
    ),
)
