"""S3R2: 결과 줄의 입력 칸 `input`(MARC-ISSUE-524). 값은 전부 지어낸 것(`가상…`·`9…`).

- T1 짓기 단위(DB 0): 지어낸 frame 으로 21 처리기 key 마다 `input` = 아래 손 표(`EXPECTED`)인지. 표는 serializer 의
  원천 상수를 import 하지 않고 발주서 §1-2(C0 실측판)에서 손으로 옮겼다 — 둘이 어긋나면 여기서 빨개진다.
  가짜 열(`분류`·`품목/자산명`·`임차자산명`·`비고` …)을 같이 넣어 그 열을 잘못 고르면 빨개진다. 값 꼴(Q4)·후보 열 둘의
  카테고리 단위 고르기·같은 엑셀 줄(`#n`)·줄 자리(i 번째 frame 줄)·FORBID 키 차례.
- T2 엔진 끝까지(DB 0): 패키지 양식(v2.2)의 **머리 두 줄만** 남기고(아래 행은 전부 지움) 지어낸 줄 셋(연간·연간·월별)을
  양식 머리 글로 채운 21 시트 → `pipeline.run` → `result_to_dict`. 줄마다 `input` 이 그 줄 rowId 의 엑셀 칸 글(줄마다
  다른 표지 ` r<n>`)과 같다. 이 판은 월별 줄이 녹이기에 실패해 쪼개지지 않으므로(코랩 그대로 `waste.py:148`) `#n` 줄은
  T1 이 본다. 빈 시트에는 줄이 없고, C9-2 `mode` 는 null 그대로(Q5).
- T3 계약: `input` 은 줄 꼴 셋의 맨 끝 NotRequired — 옛 꼴 본문(`input` 없음) strict 통과, `input` 안의 모르는 키·빠진
  키는 세 줄 꼴 모두 거절.
- S3R3: 키 열여섯째 `useMonths`(C11 수명(개월) 혹은 평균 사용기간(개월) — 바꿈 뒤 「수명(개월)」). C11 밖 20 처리기는
  null. 계약에서는 `input` 안의 NotRequired 라 S3R3 전(키 열다섯)에 저장된 결과도 strict 통과하고(감독 처분 Q3), 나머지
  열다섯 키는 그대로 required.
"""

import io
import math
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path
from typing import Any, cast

import numpy as np
import openpyxl
import pandas as pd
import pytest
from pydantic import ValidationError

from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.colab_157.activity import ActivityAmount, ActivityFactor, ActivityMeta
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, ProcessedSheet, run
from esgapi.inventory.engines.scope3.colab_157.serialize import name_columns, result_to_dict, sheet_to_dict
from esgapi.inventory.engines.scope3.colab_157.template import (
    SHEET_PROCESSOR_MAP,
    SheetProcessor,
    match_sheet_processor,
)
from esgapi.inventory.tests.contracts.test_shapes import fits, typed
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    C9_DIST_MAIN,
    DIST_ROW,
    DIST_SUB,
    INPUT_KEYS,
    TRANSPORT_SPEND_TEMPLATE,
    ColabReplies,
    FakeGeocoder,
    activity_factor_sheets,
    energy_factor_sheets,
    row_input,
    sheet,
    transport_ef_sheet,
    travel_ef_sheet,
    waste_c12_ef_sheet,
    workbook,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, SHAPE, TAGS
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

# ── 손 표: 처리기 key → 입력 키 → frame 열(발주서 §1-2, C0-2 실측판). 후보가 둘이면 (앞, 뒤) ──
_LEASED = {"country": "국가", "name": "자산명", "energy": "에너지원"}
type Source = str | tuple[str, str]
_LEASED_TABLE: dict[str, Source] = dict(_LEASED)
EXPECTED: dict[str, dict[str, Source]] = {
    "c1": {"country": "국가", "site": "사업장", "name": "품목명"},
    "c2": {"country": "국가", "site": "사업장", "name": "자산명"},
    "c3": {"country": "국가", "site": "사업장", "energy": "에너지원"},
    "c4_dist": {"country": "국가", "site": "사업장", "name": ("자재명", "제품명")},
    "c4_spend": {"country": "국가", "site": "사업장", "name": ("자재명", "제품명"), "vehicle": "운송수단"},
    "c5": {"country": "국가", "site": "사업장", "name": ("폐기물 종류", "상세폐기물명")},
    "c6_dist": {"country": "국가", "site": "사업장", "people": "인원수"},
    "c6_spend": {"country": "국가", "site": "사업장", "vehicle": "이동수단", "people": "인원수"},
    "c7": {"country": "국가", "site": "사업장", "people": "인원수"},
    "c8_energy": _LEASED_TABLE,
    "c8_area": {**_LEASED, "buildingArea": "건물전체면적", "usedArea": "사용면적"},
    "c8_person": {**_LEASED, "buildingPeople": "건물전체인원수", "ownPeople": "자사인원수"},
    "c9_dist": {"country": "국가", "site": "사업장", "name": ("제품명", "자재명")},
    "c9_spend": {"country": "국가", "site": "사업장", "name": ("제품명", "자재명"), "vehicle": "운송수단"},
    "c11": {
        "country": "국가",
        "name": "제품명",
        "energy": "에너지명",
        "productCount": "제품수량",
        "useMonths": "수명(개월)",
    },
    "c12": {
        "country": "국가",
        "name": "제품명",
        "sales": "판매량",
        "weight": "제품중량",
        "weightUnit": "제품중량 단위",
    },
    "c13_energy": _LEASED_TABLE,
    "c13_area": {**_LEASED, "buildingArea": "건물전체면적", "usedArea": "사용면적"},
    "c13_person": {**_LEASED, "buildingPeople": "건물전체인원수", "ownPeople": "자사인원수"},
    "c14": {"country": "국가", "name": "프랜차이즈명", "energy": "에너지원", "stores": "가맹점수"},
    "c15": {"name": "피투자기업명"},
}
# 고르면 틀리는 열(이름이 비슷하거나 바꿈 전 이름·그룹 이름·필요 없는 원문)
DECOYS = (
    "분류",
    "품목/자산명",
    "임차자산명",
    "임대자산명",
    "출장주체",
    "교통수단",
    "출장수단",
    "비고",
    "거래처명",
    "그룹",
)


def processor_of(key: str) -> SheetProcessor:
    return next(p for p in SHEET_PROCESSOR_MAP.values() if p.key == key)


def row_meta(excel_row: int) -> ActivityMeta:
    """줄 꼴은 무엇이든 된다(input 은 처리기 key 로 고른다) — 활동 줄 메타 하나."""
    return ActivityMeta(
        excel_row=excel_row,
        kind="waste",
        month=None,
        activity=ActivityAmount(9.1, "kg", 9.1, "kg", None),
        factor=ActivityFactor("가상시트", None, 9.2, "kgCO2eq/kg", None, None),
        treatment=None,
        biogenic=None,
        mode=None,
        steps=(),
    )


def columns_of_table() -> list[str]:
    out: list[str] = []
    for table in EXPECTED.values():
        for source in table.values():
            for column in source if isinstance(source, tuple) else (source,):
                if column not in out:
                    out.append(column)
    return out


def frame_row(tag: str) -> dict[str, object]:
    """표의 모든 열 + 가짜 열에 줄 표지가 붙은 글."""
    return {column: f"가상 {column} {tag}" for column in (*columns_of_table(), *DECOYS)}


def rows_of(
    key: str,
    records: "list[Mapping[str, object]]",
    excel_rows: list[int] | None = None,
    names: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    processor = processor_of(key)
    excel = excel_rows if excel_rows is not None else [10 + i for i in range(len(records))]
    outcome = ProcessedSheet(f"{key}_가상", processor, pd.DataFrame(records), tuple(row_meta(n) for n in excel))
    return cast("list[dict[str, Any]]", sheet_to_dict(outcome, None, names)["rows"])


def expected_input(key: str, tag: str) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for field, source in EXPECTED[key].items():
        column = source[0] if isinstance(source, tuple) else source
        values[field] = f"가상 {column} {tag}"
    return row_input(**values)


# ── T1 ──


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_t1_every_processor_key_reads_its_table_columns(key: str) -> None:
    (row,) = rows_of(key, [frame_row("t1")])
    assert row["input"] == expected_input(key, "t1")


def test_t1_the_table_covers_the_21_processor_keys() -> None:
    assert sorted(EXPECTED) == sorted(p.key for p in SHEET_PROCESSOR_MAP.values())


def test_t1_input_is_the_last_key_with_the_closed_key_order() -> None:
    (row,) = rows_of("c1", [frame_row("t1")])
    assert list(row)[-1] == "input"
    assert list(row["input"]) == list(INPUT_KEYS)
    assert list(INPUT_KEYS) == list(shapes.ColabRowInputJson.__annotations__)


def test_t1_c1_c2_name_is_not_the_group_name() -> None:
    for key in ("c1", "c2"):
        (row,) = rows_of(key, [{**frame_row("t1"), "품목/자산명": "가상그룹이름"}])
        assert row["input"]["name"] not in ("가상그룹이름", "가상 분류 t1")


def test_t1_missing_columns_and_empty_values_are_null() -> None:
    (row,) = rows_of("c12", [{"제품명": "", "판매량": math.nan, "제품중량": None, "제품중량 단위": pd.NA}])
    assert row["input"] == row_input()


def test_t1_value_forms() -> None:
    """글은 글자 그대로(앞뒤 공백도), 수는 repr(float) — 정수 입력은 `<n>.0`."""
    record = {"국가": "  가상국 ", "제품명": "가상제품", "판매량": 13, "제품중량": 0.5, "제품중량 단위": "kg"}
    (row,) = rows_of("c12", [record])
    assert row["input"] == row_input(country="  가상국 ", name="가상제품", sales="13.0", weight="0.5", weightUnit="kg")
    (np_row,) = rows_of("c12", [{"판매량": np.int64(91), "제품중량": np.float64(9.25)}])
    assert (np_row["input"]["sales"], np_row["input"]["weight"]) == ("91.0", "9.25")
    (big,) = rows_of("c12", [{"판매량": 1e-05}])
    assert big["input"]["sales"] == "1e-05"


def test_t1_rows_read_their_own_frame_row_and_the_same_excel_row_shares_input() -> None:
    """i 번째 줄은 frame 의 i 번째 줄에서. 같은 엑셀 줄에서 나온 줄들(#n)은 같은 입력."""
    rows = rows_of("c5", [frame_row("a"), frame_row("a"), frame_row("b")], [7, 7, 8])
    assert [row["rowId"] for row in rows] == ["c5_가상!7#1", "c5_가상!7#2", "c5_가상!8"]
    assert rows[0]["input"] == rows[1]["input"] == expected_input("c5", "a")
    assert rows[2]["input"] == expected_input("c5", "b")


@pytest.mark.parametrize(
    ("key", "first", "second"), [("c4_dist", "자재명", "제품명"), ("c9_spend", "제품명", "자재명")]
)
def test_t1_two_candidate_columns_pick_the_first_with_a_value(key: str, first: str, second: str) -> None:
    both = rows_of(key, [{first: "가상 앞", second: "가상 뒤"}])
    assert both[0]["input"]["name"] == "가상 앞"
    only_second = rows_of(key, [{first: math.nan, second: "가상 뒤"}])
    assert only_second[0]["input"]["name"] == "가상 뒤"


def test_t1_the_name_column_is_chosen_once_per_category() -> None:
    """C4-1 에는 자재명이 비고 C4-2 에는 들었다 → 카테고리(C4) 의 열은 자재명 하나, C4-1 줄은 null(제품명으로
    넘지 않음)."""
    frames = {
        "c4_dist": pd.DataFrame([{"자재명": math.nan, "제품명": "가상 제품 a"}]),
        "c4_spend": pd.DataFrame([{"자재명": "가상 자재 b", "제품명": "가상 제품 b"}]),
    }
    outcomes = [ProcessedSheet(f"{k}_가상", processor_of(k), f, (row_meta(9),)) for k, f in frames.items()]
    names = name_columns(outcomes)
    assert names == {"Category4": "자재명"}
    dist = cast("list[dict[str, Any]]", sheet_to_dict(outcomes[0], None, names)["rows"])
    spend = cast("list[dict[str, Any]]", sheet_to_dict(outcomes[1], None, names)["rows"])
    assert (dist[0]["input"]["name"], spend[0]["input"]["name"]) == (None, "가상 자재 b")


def test_t1_no_key_outside_the_closed_list() -> None:
    for key in EXPECTED:
        (row,) = rows_of(key, [frame_row("t1")])
        assert set(row["input"]) == set(INPUT_KEYS)
        assert not any(value is not None and "가상 비고" in value for value in row["input"].values())


def test_t1_c11_use_months_value_forms() -> None:
    """S3R3: C11 `useMonths` ← 「수명(개월)」(바꿈 뒤 이름) — 정수는 `<n>.0`, 소수, 빈 글·NaN·None → null, 글은 그대로.
    바꿈 전 이름(양식 머리 글) 열은 읽지 않는다."""
    records: list[Mapping[str, object]] = [
        {"수명(개월)": 96},
        {"수명(개월)": 30.5},
        {"수명(개월)": ""},
        {"수명(개월)": math.nan},
        {"수명(개월)": None},
        {"수명(개월)": "가상 이삼년"},
        {"수명(개월) 혹은 평균 사용기간(개월)": 12},
        {"제품당 연간 에너지 사용량": 9.1, "사용기간(년)": 8.0},
    ]
    rows = rows_of("c11", records)
    assert [row["input"]["useMonths"] for row in rows] == ["96.0", "30.5", None, None, None, "가상 이삼년", None, None]


def test_t1_use_months_is_null_outside_c11() -> None:
    """S3R3: 「수명(개월)」 열이 frame 에 있어도 C11 밖 20 처리기는 `useMonths` null."""
    others = sorted(key for key in EXPECTED if key != "c11")
    assert len(others) == 20
    for key in others:
        (row,) = rows_of(key, [{**frame_row("t1"), "수명(개월)": 96}])
        assert row["input"]["useMonths"] is None, key
    (c11,) = rows_of("c11", [{**frame_row("t1"), "수명(개월)": 96}])
    assert c11["input"]["useMonths"] == "96.0"


def test_t1_use_months_is_the_last_input_key() -> None:
    assert list(INPUT_KEYS)[-1] == "useMonths"
    assert len(INPUT_KEYS) == 16


# ── T2: 패키지 양식 머리 두 줄 + 지어낸 줄 → 엔진 끝까지 ──

PACKAGE_TEMPLATE = Path(__file__).resolve().parents[4] / "data" / "scope3" / "scope3-template-v2.2.xlsx"
MONTHS = {f"{i}월" for i in range(1, 13)}
# 양식 머리 글(* 뗌) → 지어낸 값. FREE 는 줄마다 ` r<n>` 표지를 붙인다.
VALUES: dict[str, str | int | float] = {
    "국가": "가상국", "사업장": "가상사업장", "출장주체": "가상본부",
    "품목군": "컨설팅", "상세 품목명/서비스명": "가상 경영자문", "자산분류": "차량", "상세 자산명": "가상 지게차",
    "연간지출금액(원)": 9100000, "연간취득금액(원)": 9300000, "연간운송금액(원)": 9500000,
    "연료/에너지명": "전력", "연간사용량": 9100,
    "운송수단(선택)": "가상트럭", "운송수단": "가상트럭", "자재명/품목명": "가상 철강 코일", "제품명": "가상제품A",
    "중량단위": "ton", "출도착지": "가상시가", "출발지": "가상시가", "도착지": "가상시나", "운송거리(km)(선택)": 91,
    "연간운송량": 9.1, "폐기물 종류": "가상폐지", "상세 폐기물명(선택)": "가상 폐지 상세", "처리방법": "소각",
    "연간처리량": 9.5, "인원수": 9, "편도거리(km)(선택)": 99, "연간이동횟수": 9, "연간근무일수": 99,
    "출장항목": "가상 택시비", "임차자산명": "가상자산", "임대자산명": "가상자산", "에너지종류": "전력",
    "건물전체 면적": 9000, "사용 면적": 900, "건물전체 인원수": 90, "자사 인원수": 9, "건물전체 연간사용량": 99000,
    "그룹(선택)": "가상그룹A", "제품수량": 900, "에너지명": "전력", "제품당 연간 에너지 사용량": 9.1,
    "수명(개월) 혹은 평균 사용기간(개월)": 96, "폐기물 소분류(선택)": "91-02-01 | 가상 폐지 묶음",
    "판매량": 9100, "제품중량": 0.9, "제품중량 단위": "kg", "재활용 비중(%)(선택)": 90, "소각 비중(%)(선택)": 9,
    "매립 비중(%)(선택)": 9, "프랜차이즈명": "가상가맹A", "가맹점 수": 9, "연료 종류": "경유", "연료 사용량": 9100,
    "연료 단위": "L", "피투자기업명 (필수)": "가상투자처A", "지분율(%) (선택)": 9.5, "피투자기업 Scope1배출량": 910,
    "피투자기업 Scope2배출량": 920, "비고(선택)": "가상 비고",
}  # fmt: skip
FREE = {"사업장", "출장주체", "상세 품목명/서비스명", "상세 자산명", "자재명/품목명", "제품명", "상세 폐기물명(선택)",
        "출장항목", "임차자산명", "임대자산명", "프랜차이즈명", "피투자기업명 (필수)", "비고(선택)"}  # fmt: skip
UNIT = {"c3": "kWh", "c5": "ton", "c8_area": "L", "c13_area": "L"}
PER_SHEET: dict[str, dict[str, str | float | None]] = {
    "c8_area": {"에너지종류": "경유"},
    "c13_area": {"에너지종류": "경유"},
    "c6_dist": {"교통수단": "가상버스"},
    "c7": {"교통수단": "가상승용차", "출도착지": None, "도착지": None, "편도거리(km)(선택)": 9.9},
}
# 처리기 key → 입력 키 → 양식 머리 글(* 뗌). 이름 후보 둘인 시트는 이 판에서 앞 열에 값이 든다.
TEMPLATE_HEADS: dict[str, dict[str, str]] = {
    "c1": {"country": "국가", "site": "사업장", "name": "상세 품목명/서비스명"},
    "c2": {"country": "국가", "site": "사업장", "name": "상세 자산명"},
    "c3": {"country": "국가", "site": "사업장", "energy": "연료/에너지명"},
    "c4_dist": {"country": "국가", "site": "사업장", "name": "자재명/품목명"},
    "c4_spend": {"country": "국가", "site": "사업장", "name": "자재명/품목명", "vehicle": "운송수단(선택)"},
    "c5": {"country": "국가", "site": "사업장", "name": "폐기물 종류"},
    "c6_dist": {"country": "국가", "site": "출장주체", "people": "인원수"},
    "c6_spend": {"country": "국가", "site": "출장주체", "vehicle": "출장항목", "people": "인원수"},
    "c7": {"country": "국가", "site": "사업장", "people": "인원수"},
    "c8_energy": {"country": "국가", "name": "임차자산명", "energy": "에너지종류"},
    "c8_area": {"country": "국가", "name": "임차자산명", "energy": "에너지종류", "buildingArea": "건물전체 면적",
                "usedArea": "사용 면적"},
    "c8_person": {"country": "국가", "name": "임차자산명", "energy": "에너지종류", "buildingPeople": "건물전체 인원수",
                  "ownPeople": "자사 인원수"},
    "c9_dist": {"country": "국가", "site": "사업장", "name": "제품명"},
    "c9_spend": {"country": "국가", "site": "사업장", "name": "제품명", "vehicle": "운송수단"},
    "c11": {"country": "국가", "name": "제품명", "energy": "에너지명", "productCount": "제품수량",
            "useMonths": "수명(개월) 혹은 평균 사용기간(개월)"},
    "c12": {"country": "국가", "name": "제품명", "sales": "판매량", "weight": "제품중량",
            "weightUnit": "제품중량 단위"},
    "c13_energy": {"country": "국가", "name": "임대자산명", "energy": "에너지종류"},
    "c13_area": {"country": "국가", "name": "임대자산명", "energy": "에너지종류", "buildingArea": "건물전체 면적",
                 "usedArea": "사용 면적"},
    "c13_person": {"country": "국가", "name": "임대자산명", "energy": "에너지종류", "buildingPeople": "건물전체 인원수",
                   "ownPeople": "자사 인원수"},
    "c14": {"country": "국가", "name": "프랜차이즈명", "energy": "연료 종류", "stores": "가맹점 수"},
    "c15": {"name": "피투자기업명 (필수)"},
}  # fmt: skip


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _heads(ws: Any) -> tuple[int, int | None]:
    for r in range(1, 26):
        values = [_text(c.value) for c in ws[r] if _text(c.value)]
        if sum(v.startswith("*") for v in values) >= 2:
            sub = [_text(c.value) for c in ws[r + 1]]
            has_sub = sum(v in MONTHS for v in sub) >= 2 or any(v.startswith("연간") for v in sub)
            return r, (r + 1 if has_sub else None)
    raise AssertionError(f"{ws.title}: 머리 줄 없음")


def _names(ws: Any, main: int, sub: int | None) -> list[str]:
    out: list[str] = []
    for ci in range(1, ws.max_column + 1):
        m, s = _text(ws.cell(main, ci).value), _text(ws.cell(sub, ci).value) if sub else ""
        out.append((s if s and (not m or not m.startswith("*")) else m).lstrip("*").strip())
    return out


@cache
def package_run() -> tuple[dict[str, Any], dict[str, dict[str, object]]]:
    """(결과 dict, `시트!엑셀 줄` → {양식 머리 글: 넣은 값})."""
    book = openpyxl.load_workbook(PACKAGE_TEMPLATE)
    cells: dict[str, dict[str, object]] = {}
    for ws in book.worksheets:
        processor = match_sheet_processor(ws.title)
        if processor is None:
            continue
        main, sub = _heads(ws)
        last = sub or main
        if ws.max_row > last:
            ws.delete_rows(last + 1, ws.max_row - last)  # 머리 두 줄 아래 행(예시 글)은 전부 지운다
        names = _names(ws, main, sub)
        for offset, monthly in ((1, False), (2, False), (3, True)):
            row, record = last + offset, {}
            for ci, name in enumerate(names, start=1):
                if not name or ("배출" in name and "피투자" not in name):
                    continue
                value = UNIT.get(processor.key, "kWh") if name == "단위" else None
                if name != "단위":
                    value = PER_SHEET.get(processor.key, {}).get(name, VALUES.get(name))
                if value is None or (monthly and name.startswith(("연간", "건물전체 연간"))):
                    continue
                if name in FREE:
                    value = f"{value} r{offset}"
                ws.cell(row, ci).value = value  # pyright: ignore[reportAttributeAccessIssue] — 합친 칸이 아니다
                record[name] = value
            if monthly and sub:
                for ci, name in enumerate(names, start=1):
                    if name in ("1월", "2월"):
                        record[name] = 9.25 if name == "1월" else 9.75
                        ws.cell(row, ci).value = record[name]  # pyright: ignore[reportAttributeAccessIssue]
            cells[f"{ws.title}!{row}"] = record
    book.create_sheet("c2_자본가상")  # 빈 시트(머리 없음) — 줄 0
    out = io.BytesIO()
    book.save(out)
    factor_book = workbook(
        sheet("구매_USEPA", BOOK_ROWS),
        *activity_factor_sheets(),
        transport_ef_sheet(),
        travel_ef_sheet(),
        *energy_factor_sheets(),
        waste_c12_ef_sheet(),
    )
    template = read_workbook(out.getvalue())
    assert not isinstance(template, ReaderProblem)
    result = run(template, factor_book, 2025, mock_client(ColabReplies()), FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return result_to_dict(result, SHAPE), cells


def _expected_from_cells(key: str, record: Mapping[str, object]) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for field, head in TEMPLATE_HEADS[key].items():
        value = record.get(head)
        if value is None or isinstance(value, str):
            values[field] = value
        else:
            values[field] = repr(float(cast("float", value)))
    return row_input(**values)


def test_t2_every_row_input_equals_its_excel_cells() -> None:
    data, cells = package_run()
    processed = [s for s in data["sheets"] if s["status"] == "processed"]
    assert len(processed) == 21
    by_sheet = {match_sheet_processor(s["sheet"]).key: s for s in processed}  # pyright: ignore[reportOptionalMemberAccess]
    seen = 0
    for key, part in by_sheet.items():
        assert len(part["rows"]) == 3, part["sheet"]
        for row in part["rows"]:
            base = row["rowId"].split("#", 1)[0]
            assert row["input"] == _expected_from_cells(key, cells[base]), row["rowId"]
            seen += 1
    assert seen == 63


def test_t2_markers_differ_by_row_so_the_rows_line_up() -> None:
    data, _ = package_run()
    for part in (s for s in data["sheets"] if s["status"] == "processed"):
        sites = [row["input"]["site"] or row["input"]["name"] for row in part["rows"]]
        assert len(set(sites)) == 3, part["sheet"]


def test_t2_empty_sheets_have_no_rows_and_c9_2_mode_stays_null() -> None:
    data, _ = package_run()
    others = [s for s in data["sheets"] if s["status"] != "processed"]
    assert others and all("rows" not in s for s in others)
    assert {s["status"] for s in others} >= {"empty"}
    (c9_spend,) = [s for s in data["sheets"] if s["sheet"].startswith("C9-2")]
    assert all(row["mode"] is None and row["input"]["vehicle"] is not None for row in c9_spend["rows"])


# ── T3: 계약 ──


def test_t3_rows_fit_the_key_order_with_input_last() -> None:
    data, _ = package_run()
    assert fits(data, typed(shapes.Scope3ColabResult)) == []
    for shape in (shapes.ColabRowJson, shapes.ColabActivityRowJson, shapes.ColabEnergyRowJson):
        assert list(shape.__annotations__)[-1] == "input"
        assert "input" in shape.__optional_keys__


def test_t3_an_old_body_without_input_passes_strict() -> None:
    data, _ = package_run()
    old = {
        **data,
        "sheets": [
            {**s, "rows": [{k: v for k, v in row.items() if k != "input"} for row in s["rows"]]} if "rows" in s else s
            for s in data["sheets"]
        ],
    }
    shapes.RESULT_SHAPES[SHAPE].validate_python(old, strict=True)
    shapes.RESULT_SHAPES[SHAPE].validate_python(data, strict=True)


@pytest.mark.parametrize("kind_prefix", ["C1", "C4-2", "C3"])  # 줄 꼴 셋: 구매·활동·에너지
@pytest.mark.parametrize("change", ["unknown", "missing"])
def test_t3_input_rejects_unknown_and_missing_keys(kind_prefix: str, change: str) -> None:
    data, _ = package_run()
    (part,) = [s for s in data["sheets"] if s["sheet"].startswith(f"{kind_prefix}_")]
    row = dict(part["rows"][0])
    bad = dict(row["input"])
    if change == "unknown":
        bad["비고"] = "가상 비고"
    else:
        del bad["country"]
    one = {**data, "sheets": [{**part, "rows": [{**row, "input": bad}]}]}
    with pytest.raises(ValidationError):
        shapes.RESULT_SHAPES[SHAPE].validate_python(one, strict=True)


# ── B1(검증): 카테고리 단위 고르기를 실행 길(`result_to_dict`)로 ──


def c4_run(c4_1_item: str, c4_2_item: str) -> dict[str, Any]:
    """C4-1 은 이름 열이 `*제품명`(뒤 후보) 하나뿐인 머리, C4-2 는 `*자재명/품목명`(→ 자재명, 앞 후보)."""
    c4_1 = sheet(
        "c4-1_운송거리",
        {1: ["가상 안내 — c4-1"], 2: C9_DIST_MAIN, 3: DIST_SUB, 4: [*DIST_ROW[:3], c4_1_item, *DIST_ROW[4:]]},
    )
    c4_2 = sheet("c4-2_운송금액", {**TRANSPORT_SPEND_TEMPLATE, 6: ["가상사업장", c4_2_item, "가상트럭", 9500000]})
    factor_book = workbook(sheet("구매_USEPA", BOOK_ROWS), *activity_factor_sheets(), transport_ef_sheet())
    result = run(workbook(c4_1, c4_2), factor_book, 2025, mock_client(ColabReplies()), FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return result_to_dict(result, SHAPE)


def c4_names(data: Mapping[str, Any]) -> dict[str, str | None]:
    return {s["sheet"]: s["rows"][0]["input"]["name"] for s in data["sheets"] if s["status"] == "processed"}


def test_b1_the_run_picks_one_name_column_for_the_whole_category() -> None:
    """C4-2 의 자재명에 값이 들었으니 C4 의 열은 자재명 — 자재명이 없는 C4-1 줄은 null(제품명으로 넘지 않는다)."""
    assert c4_names(c4_run("가상 제품 b1", "가상 자재 b1")) == {"c4-1_운송거리": None, "c4-2_운송금액": "가상 자재 b1"}


def test_r1_a_blank_text_does_not_count_when_choosing_but_is_carried_as_is() -> None:
    """고르는 판정만 strip: C4-2 의 자재명이 공백뿐이면 C4 의 열은 제품명(C4-1 줄에 값, C4-2 줄은 제품명 열이 없어
    null)."""
    assert c4_names(c4_run("가상 제품 r1", "   ")) == {"c4-1_운송거리": "가상 제품 r1", "c4-2_운송금액": None}
    frames = [pd.DataFrame([{"자재명": "  ", "제품명": math.nan}, {"자재명": "가상 자재", "제품명": "가상 제품"}])]
    outcome = ProcessedSheet("c4-2_가상", processor_of("c4_spend"), frames[0], (row_meta(9), row_meta(10)))
    assert name_columns([outcome]) == {"Category4": "자재명"}
    rows = cast("list[dict[str, Any]]", sheet_to_dict(outcome, None)["rows"])
    assert [row["input"]["name"] for row in rows] == ["  ", "가상 자재"]  # 싣는 값은 글자 그대로(Q4)


def test_t2_c11_use_months_is_the_excel_cell() -> None:
    """S3R3: 패키지 판 C11 세 줄의 `useMonths` = 엑셀 칸 「수명(개월) 혹은 평균 사용기간(개월)」(정수 96 → "96.0"),
    월별 줄(셋째)도 같은 칸."""
    data, cells = package_run()
    (part,) = [s for s in data["sheets"] if s["sheet"].startswith("C11_")]
    got = [row["input"]["useMonths"] for row in part["rows"]]
    want = [_expected_from_cells("c11", cells[row["rowId"].split("#", 1)[0]])["useMonths"] for row in part["rows"]]
    assert got == want == ["96.0", "96.0", "96.0"]


def _with_input(data: dict[str, Any], change: "Callable[[dict[str, Any]], dict[str, Any]]") -> dict[str, Any]:
    return {
        **data,
        "sheets": [
            {**s, "rows": [{**row, "input": change(dict(row["input"]))} for row in s["rows"]]} if "rows" in s else s
            for s in data["sheets"]
        ],
    }


def test_t3_a_fifteen_key_input_saved_before_s3r3_passes_strict() -> None:
    """감독 처분 Q3: `useMonths` 는 `input` 안의 NotRequired — 키 열다섯(093f16c3~S3R3 저장 결과) 그대로 통과."""
    data, _ = package_run()
    old = _with_input(data, lambda i: {k: v for k, v in i.items() if k != "useMonths"})
    assert all(len(row["input"]) == 15 for s in old["sheets"] for row in s.get("rows", []))
    shapes.RESULT_SHAPES[SHAPE].validate_python(old, strict=True)
    assert "useMonths" in shapes.ColabRowInputJson.__optional_keys__
    assert shapes.ColabRowInputJson.__required_keys__ == frozenset(INPUT_KEYS[:15])


@pytest.mark.parametrize("value", [96, 96.0, True, ["96"]])
def test_t3_use_months_is_text_or_null_only(value: object) -> None:
    data, _ = package_run()
    bad = _with_input(data, lambda i: {**i, "useMonths": value})
    with pytest.raises(ValidationError):
        shapes.RESULT_SHAPES[SHAPE].validate_python(bad, strict=True)
