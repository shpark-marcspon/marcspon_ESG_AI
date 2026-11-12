"""S3C-c2 채운 템플릿 — `output_files.build_filled_template`(셀 30 `:9178-9469`).

T2 손셈(C14 꼴 템플릿에 회색 열 둘 — 배율 곱셈·비고 짝·위치 짝) · T4 커서(같은 Category 의 시트 둘, 회색 열 없는 시트도
옮김, 표준화 실패·빈 시트는 안 옮김, 다시 돌기 LLM·지오코더 부름 0) · T5 쓰기 규칙(`_EF_META_COLS` 일곱, 두 낱말 머리,
줄 안 마지막 칸, 병합 머리 끝·병합 칸 → 왼쪽 위, None 이면 안 씀, int64 빔은 행 dtype 이 object 일 때만, 15자 넘는
안내문). 여덟 판(filled 의 회색 칸 22 · 채움 20)은 §4 [9] 의 대조가 문다.
"""

import dataclasses
import json
from collections.abc import Sequence
from typing import Any, cast

import pandas as pd
import pytest

from esgapi.inventory.engines.scope3.colab_157 import output_files, pipeline
from esgapi.inventory.engines.scope3.colab_157.output_files import (
    EF_META_COLS,
    Cell,
    CellWrite,
    CellWriter,
    FilledSheet,
    OutputFiles,
    ResultSheet,
    TemplateView,
    build_filled_template,
    extract_ef_em,
    find_ef_em_columns,
    find_note_column,
)
from esgapi.inventory.engines.scope3.colab_157.pipeline import ProcessedSheet
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.engines.scope3.colab_157.template import SheetProcessor
from esgapi.inventory.tests.engines.scope3.colab_157.support import C14_MAIN, C14_ROW, Value, c11_sheet, sheet, workbook
from esgapi.inventory.tests.engines.scope3.colab_157.test_product_use_sheet import SCHEMA, by_text, run_on, unit_calls
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

EF_HEAD, EM_HEAD = "배출계수(tCO2e/단위)", "배출량(tCO2e)"
KWH_ROW: list[Value] = ["가상국", "가상가맹B", 95, "전력", 92000, "kWh", "가상 비고 2"]
DIESEL, ELEC = 0.942, 0.0941


def gray_c14(name: str, rows: Sequence[list[Value]], ef_head: str = EF_HEAD) -> Sheet:
    """support `c14_sheet` 꼴(안내 1줄, 머리 2줄, 데이터 3줄부터)에 회색 열 둘(H·I — 비고 G 뒤)."""
    return sheet(
        name, {1: [f"가상 안내 — {name}"], 2: [*C14_MAIN, ef_head, EM_HEAD], **{3 + i: r for i, r in enumerate(rows)}}
    )


def as_is(_: SheetProcessor, df: pd.DataFrame) -> pd.DataFrame:
    return df


def result(columns: Sequence[str], *rows: Sequence[Cell], name: str = "C14_프랜차이즈") -> ResultSheet:
    return ResultSheet(name, tuple(columns), tuple(tuple(r) for r in rows))


def file_value(x: float) -> float | int:
    """결과 파일을 다시 읽은 값(openpyxl `%.16g`)."""
    v = float(f"{x:.16g}")
    return int(v) if v.is_integer() else v


# ── T2 손셈 ──


def test_c14_gray_cells_from_the_pipeline_scale_by_multiplication() -> None:
    run = run_on([gray_c14("c14_프랜차이즈", [C14_ROW, KWH_ROW])])
    outputs = run.outputs
    assert isinstance(outputs, OutputFiles)
    scale = 1.0 / 1000.0
    assert outputs.writes == (
        CellWrite("c14_프랜차이즈", 3, 8, DIESEL * scale),
        CellWrite("c14_프랜차이즈", 3, 9, file_value(9100 * DIESEL / 1000.0)),
        CellWrite("c14_프랜차이즈", 4, 8, ELEC * scale),
        CellWrite("c14_프랜차이즈", 4, 9, file_value(92000 * ELEC / 1000.0)),
    )
    assert ELEC * scale == 9.410000000000001e-05 != ELEC / 1000  # 곱셈(`:9431`) — 나눗셈은 끝자리가 다르다
    assert outputs.filled_sheets == (FilledSheet("c14_프랜차이즈", "filled", 4, "note", 0),)


NOTE_COLUMNS = ("프랜차이즈명", "비고(선택)", "배출계수(kgCO2eq/단위)", "배출량(tCO2e)")


def test_note_pairing_follows_the_note_text_not_the_position() -> None:
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW, KWH_ROW]))
    flipped = result(NOTE_COLUMNS, ("가상가맹B", "가상 비고 2", 0.2, 2.5), ("가상가맹A", "가상 비고 1", 0.1, 1.5))
    writes, sheets = build_filled_template(template, [flipped], as_is)
    assert [(w.row, w.column, w.value) for w in writes] == [
        (3, 8, 0.1 / 1000),
        (3, 9, 1.5),
        (4, 8, 0.2 / 1000),
        (4, 9, 2.5),
    ]
    assert sheets[0].pairing == "note"


def test_blank_or_unmatched_notes_take_the_leftover_results_in_order() -> None:
    template = workbook(gray_c14("c14_프랜차이즈", [[*C14_ROW[:6], None], [*KWH_ROW[:6], "가상 비고 2"]]))
    rows = result(NOTE_COLUMNS, ("가", "가상 비고 2", 0.2, 2.5), ("나", "가상 비고 9", 0.1, 1.5))
    writes, _ = build_filled_template(template, [rows], as_is)
    assert [(w.row, w.value) for w in writes] == [(4, 0.2 / 1000), (4, 2.5), (3, 0.1 / 1000), (3, 1.5)]


def test_unmatched_result_rows_are_counted_when_the_template_has_fewer_data_rows() -> None:
    """`n` 이 데이터 줄보다 많으면(표준화가 줄을 늘림) 짝 없는 결과 줄이 남는다(`[주의] … n개` `:9452`)."""
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW]))
    rows = result(NOTE_COLUMNS, ("가", "가상 비고 1", 0.1, 1.5), ("나", "가상 비고 8", 0.2, 2.5))

    def doubled(_: SheetProcessor, df: pd.DataFrame) -> pd.DataFrame:
        return pd.concat([df, df], ignore_index=True)

    _, sheets = build_filled_template(template, [rows], doubled)
    assert sheets == (FilledSheet("c14_프랜차이즈", "filled", 2, "note", 1),)


def test_position_pairing_when_the_result_has_no_note_column() -> None:
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW, KWH_ROW]))
    rows = result(("프랜차이즈명", "배출계수", "배출량(tCO2e)"), ("나", 0.2, 2.5), ("가", 0.1, 1.5))
    writes, sheets = build_filled_template(template, [rows], as_is)
    assert [(w.row, w.value) for w in writes] == [(3, 0.2 / 1000), (3, 2.5), (4, 0.1 / 1000), (4, 1.5)]
    assert sheets[0].pairing == "position"


def test_a_none_value_writes_nothing() -> None:
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW]))
    rows = result(("프랜차이즈명", "배출계수", "배출량(tCO2e)"), ("가", None, None))
    writes, sheets = build_filled_template(template, [rows], as_is)
    assert (writes, sheets[0].filled, sheets[0].status) == ((), 0, "filled")


# ── T4 커서 ──

C14_RESULT = result(("프랜차이즈명", "배출계수", "배출량(tCO2e)"), ("가", 0.1, 1.5), ("나", 0.2, 2.5), ("다", 0.3, 3.5))


def plain_c14(name: str, rows: Sequence[list[Value]]) -> Sheet:
    return sheet(name, {1: [f"가상 안내 — {name}"], 2: list(C14_MAIN), **{3 + i: r for i, r in enumerate(rows)}})


def test_a_sheet_without_gray_columns_still_moves_the_cursor() -> None:
    template = workbook(plain_c14("c14_프랜차이즈", [C14_ROW, KWH_ROW]), gray_c14("c14_프랜차이즈2", [C14_ROW]))
    writes, sheets = build_filled_template(template, [C14_RESULT], as_is)
    assert [s.status for s in sheets] == ["no_gray_columns", "filled"]
    assert [w.value for w in writes] == [0.3 / 1000, 3.5]  # 셋째 결과 줄


def test_standardize_failure_and_empty_sheets_do_not_move_the_cursor() -> None:
    template = workbook(
        Sheet("c14_프랜차이즈0", {}, (), ()),  # 빈 시트 — 읽기가 빈 frame
        gray_c14("c14_프랜차이즈", [C14_ROW, KWH_ROW]),
        gray_c14("c14_프랜차이즈2", [C14_ROW]),
    )

    def fails_first(processor: SheetProcessor, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) == 2:
            raise ValueError("가상 표준화 실패")
        return df

    writes, sheets = build_filled_template(template, [C14_RESULT], fails_first)
    assert [s.status for s in sheets] == ["empty", "standardize_failed", "filled"]
    assert [w.value for w in writes] == [0.1 / 1000, 1.5]  # 첫 결과 줄


def test_a_sheet_without_a_result_sheet_is_no_result() -> None:
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW]))
    writes, sheets = build_filled_template(template, [], as_is)
    assert (writes, sheets) == ((), (FilledSheet("c14_프랜차이즈", "no_result", 0, None, 0),))


def test_an_exhausted_cursor_gives_filled_zero() -> None:
    """자른 결과가 비면 코랩은 로그 없이 넘긴다(`matched.empty` — 코드와 1:1)."""
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW]), gray_c14("c14_프랜차이즈2", [C14_ROW]))
    one = result(("프랜차이즈명", "배출계수", "배출량(tCO2e)"), ("가", 0.1, 1.5))
    _, sheets = build_filled_template(template, [one], as_is)
    assert sheets[1] == FilledSheet("c14_프랜차이즈2", "filled", 0, None, 0)


def test_restandardizing_calls_no_llm_and_hits_the_same_cache() -> None:
    """C11 의 커서 표준화(`:7613` = `:6961` 셈 포함)는 처리 때 AI 배수 캐시를 쓴다 — 부름은 처리 때 하나뿐."""
    calls: list[str] = []
    original = output_files.calc_c11_6961

    def spy(*args: object, **kwargs: object) -> object:
        calls.append("cursor")
        return cast(Any, original)(*args, **kwargs)

    mock = by_text({"가상와트": '{"factor": 9.9}'})
    c11 = c11_sheet("c11_판매제품사용", ["가상국", None, None, "가상제품E", 10, "전력", 9.1, "가상와트", 24, None])
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(output_files, "calc_c11_6961", spy)
        run = run_on([c11], mock)
    assert calls == ["cursor"]
    assert unit_calls(mock) == [("가상와트", "전력")]
    assert isinstance(run.outputs, OutputFiles)
    assert [s.status for s in run.outputs.filled_sheets] == ["no_gray_columns"]


# ── T5 쓰기 규칙 ──


@pytest.mark.parametrize("meta", sorted(EF_META_COLS))
def test_each_ef_meta_column_is_skipped(meta: str) -> None:
    row = pd.Series({meta: 5.0, "배출계수": 7.0, "배출량(tCO2e)": 1.0}, dtype=object)
    assert extract_ef_em(row) == (7.0, 1.0)


def test_ef_meta_columns_are_the_seven_of_9293() -> None:
    assert {
        "배출계수기준연도",
        "배출계수기준컬럼",
        "배출계수단위",
        "EF단위",
        "EF매핑명",
        "EF매핑방식",
        "EF매핑점수",
    } == EF_META_COLS


def test_emission_priority_and_excluded_names() -> None:
    row = pd.Series(
        {"추천EF1_예상배출량(tCO2e)": 9.0, "배출량(kgCO2e)": 8.0, "기타 배출량": 3.0, "배출량": 2.0}, dtype=object
    )
    assert extract_ef_em(row) == (None, 2.0)
    assert extract_ef_em(pd.Series({"기타 배출량": 3.0, "배출량(kgCO2e)": 8.0}, dtype=object)) == (None, 3.0)


def view(rows: dict[int, list[Value]], merges: tuple[str, ...] = ()) -> TemplateView:
    base = sheet("가상", rows)
    return TemplateView(Sheet("가상", base.cells, merges, ()))


def test_a_header_with_both_words_is_the_factor_and_the_last_cell_in_the_row_wins() -> None:
    ws = view({2: ["배출계수 앞", "배출량 앞", "배출계수와 배출량", "배출량 뒤"]})
    assert find_ef_em_columns(ws) == (2, 3, 4, "배출계수와 배출량")


def test_the_header_end_is_the_bottom_of_the_merged_header_cells() -> None:
    ws = view({2: ["가상", EF_HEAD, EM_HEAD], 4: ["가상값"]}, ("B2:B3", "C2:C3"))
    assert find_ef_em_columns(ws) == (3, 2, 3, EF_HEAD)


def test_a_merged_cell_write_goes_to_the_top_left() -> None:
    rows: dict[int, list[Value]] = {1: [*C14_MAIN, EF_HEAD, EM_HEAD], 2: C14_ROW}
    base = sheet("c14_프랜차이즈", rows)
    template = workbook(Sheet("c14_프랜차이즈", base.cells, ("H1:H1", "I2:J2"), ()))
    tmpl = TemplateView(template.sheets[0])
    assert tmpl.merge_of(2, 10) is not None and tmpl.value(2, 10) is None  # 왼쪽 위 밖 = MergedCell(None)
    writer = CellWriter("가상", tmpl)
    writer.set(2, 10, 1.5)
    writer.set(2, 8, None)
    assert writer.writes == [CellWrite("가상", 2, 9, 1.5)]


def test_colab_same_defect_int64_column_is_empty_when_the_row_is_object() -> None:
    """`matched.iloc[i]` 의 행 dtype 이 object 면 int64 칸은 `np.int64` 라 수가 아니다(감독 보정 3 — 코랩 그대로)."""
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW]))
    rows = result(("프랜차이즈명", "배출계수", "배출량(tCO2e)"), ("가", 2, 3))
    writes, sheets = build_filled_template(template, [rows], as_is)
    assert (writes, sheets[0].filled) == ((), 0)


def test_int64_with_float64_only_upcasts_the_row_and_fills() -> None:
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW]))
    rows = result(("배출계수", "배출량(tCO2e)"), (2, 3.5))
    writes, _ = build_filled_template(template, [rows], as_is)
    assert [w.value for w in writes] == [2 / 1000, 3.5]


def test_a_long_guide_sentence_is_not_the_note_column() -> None:
    ws = view({1: ["가상 안내: 분류방법 설명서를 먼저 읽고 비고를 적는다"], 2: ["가상", "비고(선택)"]})
    assert find_note_column(ws, 2) == 2


def test_the_kg_header_keeps_scale_one() -> None:
    template = workbook(gray_c14("c14_프랜차이즈", [C14_ROW], ef_head="배출계수(kgCO2e/원)"))
    rows = result(("배출계수", "배출량(tCO2e)"), (0.25, 3.5))
    writes, _ = build_filled_template(template, [rows], as_is)
    assert [w.value for w in writes] == [0.25, 3.5]


def test_pipeline_outputs_fail_softly(monkeypatch: pytest.MonkeyPatch) -> None:
    """T7: 내용 짓기에서 예외가 나면 `OutputsFailed` — 시트 결과는 그대로."""

    def broken(*_: object) -> OutputFiles:
        raise ValueError("가상 짓기 실패")

    good = run_on([gray_c14("c14_프랜차이즈", [C14_ROW])])
    monkeypatch.setattr(pipeline, "build_outputs", broken)
    bad = run_on([gray_c14("c14_프랜차이즈", [C14_ROW])])
    assert bad.outputs == output_files.OutputsFailed("ValueError: 가상 짓기 실패")
    assert [o.status for o in bad.sheets] == [o.status for o in good.sheets]
    for a, b in zip(good.sheets, bad.sheets, strict=True):
        assert isinstance(a, ProcessedSheet) and isinstance(b, ProcessedSheet)
        assert a.frame.equals(b.frame)


def test_done_runs_carry_outputs_and_the_result_dict_ignores_them() -> None:
    """T7: done 실행마다 `outputs` 가 채워지고, `result_to_dict` 는 그 칸을 읽지 않는다(계약 0줄)."""
    done = run_on([gray_c14("c14_프랜차이즈", [C14_ROW])])
    assert isinstance(done.outputs, OutputFiles)
    bare = dataclasses.replace(done, outputs=None)
    assert json.dumps(result_to_dict(done, SCHEMA), ensure_ascii=False) == json.dumps(
        result_to_dict(bare, SCHEMA), ensure_ascii=False
    )
