"""S3C-c2 T1 결과 파일 꼴 — `output_files.build_result_file`(셀 23 `:6205-6246` + 셀 27 후처리 `:8878-8911`).

지어낸 처리 때 줄·후처리 뒤 줄로 시트 차례·열(합집합 → DROP → 빈 열)·후처리 열의 **실행 술어**(감독 보정 1)·후처리 예외
(`:8903-8905`)를 본다. 여덟 판의 시트·열·줄 수(o4b ⑦)는 §4 [9] 의 대조(`outputs.json` 차이 0)가 문다.
"""

import numpy as np
import pandas as pd
import pytest
from openpyxl.compat.strings import safe_string

from esgapi.inventory.engines.scope3.colab_157.output_files import (
    OutputFiles,
    ProcessedPart,
    ResultSheet,
    build_result_file,
    build_result_sheet,
    reread,
)
from esgapi.inventory.engines.scope3.colab_157.template import SHEET_PROCESSOR_MAP, TEMPLATE_ROW
from esgapi.inventory.tests.engines.scope3.colab_157.support import C11_ROW, c11_sheet
from esgapi.inventory.tests.engines.scope3.colab_157.test_product_use_sheet import MWH_ROW, run_on

type Row = dict[str, object]


def part(key: str, before: list[Row], after: list[Row] | None = None) -> ProcessedPart:
    """`key` 는 SHEET_PROCESSOR_MAP 의 시트 키. after 를 주면 후처리 시트(before = 처리 때 줄)."""
    processor = SHEET_PROCESSOR_MAP[key]
    frame = pd.DataFrame(after if after is not None else before)
    return ProcessedPart(key, processor, frame, (), tuple(before) if after is not None else None)


def column(sheet: ResultSheet, name: str) -> list[object]:
    i = sheet.columns.index(name)
    return [row[i] for row in sheet.rows]


C6_DIST: Row = {"이동수단": "가상버스", "이동거리(km)": 9.0, "계산방식": "Distance", "출장비용": None, TEMPLATE_ROW: 4}
C6_SPEND: Row = {"출장수단": "가상택시", "출장비용": 9100, "계산방식": "Spend", "NAICS": "가상코드", TEMPLATE_ROW: 4}
C6_SPEND_EMPTY: Row = {"출장수단": "가상택시", "출장비용": None, "계산방식": "Spend", TEMPLATE_ROW: 5}


def c6_after(row: Row, writes: Row) -> Row:
    return {**row, **writes}


DIST_WRITES: Row = {"배출량(tCO2e)": 0.9, "배출량": 0.9, "출장비용": None, "거리왕복계수": 2, "계산식": "가상식"}
SPEND_WRITES: Row = {
    "배출량(tCO2e)": 0.91, "배출량": 0.91, "Spend방식": "출장", "EF_DB": "가상", "NAICS": "가상코드", "배출계수": 0.1,
    "배출계수단위": "kgCO2e/KRW", "계산식": "가상식",
}  # fmt: skip


def test_c6_post_columns_follow_the_executed_writes_in_row_order() -> None:
    """C6-1(Distance) 뒤 C6-2(Spend): b = C6-1 열 → C6-2 만의 열(DROP 의 NAICS 는 빠짐), 그 뒤 후처리가 처음 쓴 차례.
    Distance 줄의 `출장비용 = None`(`:8834`)은 b 에 없으면 값이 None 이어도 열을 만든다."""
    dist = c6_after(C6_DIST, {**DIST_WRITES, "정규화이동수단": "bus"})
    spend = c6_after(C6_SPEND, {**SPEND_WRITES, "정규화이동수단": "taxi"})
    before_dist = {k: v for k, v in C6_DIST.items() if k != "출장비용"}
    sheets = build_result_file(
        [part("c6-1_출장거리", [before_dist], [dist]), part("c6-2_출장비", [C6_SPEND], [spend])], frozenset()
    )
    (c6,) = sheets
    assert c6.name == "C6_출장"
    assert c6.columns == (
        "이동수단", "이동거리(km)", "계산방식", "출장수단", "출장비용",  # b(처리 때 합집합, DROP·줄 번호·빈 열 뺌)
        "배출량(tCO2e)", "배출량", "거리왕복계수", "계산식", "정규화이동수단",  # Distance 줄(`:8832-8842`)
        "Spend방식", "EF_DB", "NAICS", "배출계수", "배출계수단위",  # Spend 줄의 새 열(`:8641`)
    )  # fmt: skip
    assert column(c6, "출장비용") == [None, 9100]
    assert column(c6, "NAICS") == [None, "가상코드"]  # DROP 열도 후처리가 쓰면 다시 생긴다


def test_the_early_spend_return_writes_two_columns_even_when_none() -> None:
    """출장비용이 없으면 `{"배출량(tCO2e)": None, "Spend방식": "출장"}`(`:8644`) — None 이어도 열이 생긴다."""
    after = c6_after(C6_SPEND_EMPTY, {"배출량(tCO2e)": None, "Spend방식": "출장", "정규화이동수단": "taxi"})
    (c6,) = build_result_file([part("c6-2_출장비", [C6_SPEND_EMPTY], [after])], frozenset())
    assert c6.columns == ("출장수단", "계산방식", "배출량(tCO2e)", "Spend방식", "정규화이동수단")
    assert column(c6, "배출량(tCO2e)") == [None]


C14_BEFORE: list[Row] = [
    {"프랜차이즈명": "가상A", "사용량": 9, "EF매핑명": "경유", TEMPLATE_ROW: 3},
    {"프랜차이즈명": "가상B", "사용량": 92, "EF매핑명": "전력", TEMPLATE_ROW: 4},
]
C14_POST: Row = {"배출계수(kgCO2eq/단위)": 0.9, "EF단위": "kWh", "EF매핑명": "전력", "배출량(tCO2e)": 0.9, "계산식": ""}


def test_a_conditional_column_first_appears_on_the_row_that_runs_it() -> None:
    """C14 `if unit_note:`(`:8870`) 가 둘째 줄에서만 참이면 단위환산비고는 그 줄에서 끝에 붙는다(계산식 뒤)."""
    after = [{**C14_BEFORE[0], **C14_POST}, {**C14_BEFORE[1], **C14_POST, "단위환산비고": "MWh→kWh"}]
    (c14,) = build_result_file([part("c14_프랜차이즈", C14_BEFORE, after)], frozenset())
    assert c14.columns == (
        "프랜차이즈명", "사용량", "EF매핑명", "배출계수(kgCO2eq/단위)", "EF단위", "배출량(tCO2e)", "계산식",
        "단위환산비고",
    )  # fmt: skip
    assert column(c14, "단위환산비고") == [None, "MWh→kWh"]
    assert column(c14, "계산식") == [None, None]  # 빈 글은 openpyxl 이 빈 칸으로 쓴다


def test_a_failed_postprocess_keeps_the_first_file_columns() -> None:
    after = [{**r, **C14_POST} for r in C14_BEFORE]
    (c14,) = build_result_file([part("c14_프랜차이즈", C14_BEFORE, after)], frozenset({"Category14"}))
    assert c14.columns == ("프랜차이즈명", "사용량", "EF매핑명")
    assert column(c14, "EF매핑명") == ["경유", "전력"]  # 처리 때 값(후처리 값 「전력」 이 아니다)


def test_first_file_columns_drop_rules() -> None:
    """빈 글 열은 notna 라 남고(다시 읽으면 빈 칸), 전부 None 열·DROP 열·우리 줄 번호 열은 없다."""
    rows: list[Row] = [
        {"품목": "가상", "빈 글": "", "없음": None, "출처시트": "가상", "1월": 9, TEMPLATE_ROW: 3},
        {"품목": "가상2", "빈 글": "", "없음": None, "출처시트": "가상", "1월": 9, TEMPLATE_ROW: 4},
    ]
    sheet = build_result_sheet("Category12", [part("c12_판매제품폐기", rows)], False)
    assert sheet.columns == ("품목", "빈 글")
    assert column(sheet, "빈 글") == [None, None]


def test_first_round_trip_values_go_into_the_second_file() -> None:
    """후처리 없는 시트도 첫 왕복을 거친다(감독 보정 4): `=…` 글 → None, 수 꼴 글만 든 열 → 수."""
    rows: list[Row] = [{"가": "=가상식", "나": "1"}, {"가": "가상", "나": "2"}]
    sheet = build_result_sheet("Category15", [part("c15_투자", rows)], False)
    assert sheet.rows == ((None, 1), ("가상", 2))


def test_result_sheet_order_is_the_first_processed_category() -> None:
    sheets = build_result_file(
        [
            part("c4-2_운송금액", [{"가": 1}]),
            part("c1_구매품서비스", [{"가": 2}]),
            part("c4-1_운송거리", [{"가": 3}]),
        ],
        frozenset(),
    )
    assert [(s.name, len(s.rows)) for s in sheets] == [("C4_업스트림운송", 2), ("C1_구매품서비스", 1)]


def test_c11_unit_note_sits_before_the_mapping_columns_like_colab() -> None:
    """C11 처리 때 frame(`:6961` → `:7613`): 단위환산비고(둘째 줄에서만)는 매핑 칸 셋보다 앞(product.py 의 줄 dict 는
    끝으로 민다 — 결과 파일 열 차례만 코랩 꼴로, rest 판 실측)."""
    outputs = run_on([c11_sheet("c11_판매제품사용", C11_ROW, MWH_ROW)]).outputs
    assert isinstance(outputs, OutputFiles)
    (c11,) = outputs.result
    assert c11.columns[-5:] == ("배출량(tCO2e)", "단위환산비고", "EF매핑명", "EF매핑방식", "EF매핑점수")


# ── S3C-c2 검증 권고 1(S3C-r1 2-0 i): 수의 글자 ──

SIXTEEN_G: list[object] = [
    0,
    -7,
    2**53 + 1,
    10**20,
    1e-05,
    0.1 + 0.2,
    -0.0,
    1.4803074,
    9.410000000000001e-05,
    1e16,
    123456789012345678.0,
    np.int64(5),
    np.float64(0.1 + 0.2),
]


@pytest.mark.parametrize("value", SIXTEEN_G, ids=[repr(v) for v in SIXTEEN_G])
def test_the_number_text_is_openpyxl_s_safe_string(value: object) -> None:
    """`format(v, ".16g")` 는 openpyxl `safe_string` 의 `"%.16g" % v` 와 같은 글자다(정수도 float 로 —
    2**53+1 은 …992)."""
    assert format(value, ".16g") == safe_string(value)


def test_reread_numbers_carry_the_16g_cut() -> None:
    """결과 파일을 다시 읽은 값은 16자리로 자른 수다(0.1+0.2 → 0.3, 2**53+1 → 2**53)."""
    frame = reread(["값"], [[0.1 + 0.2], [2**53 + 1], [1e-05]])
    assert frame["값"].tolist() == [0.3, float(2**53), 1e-05]
