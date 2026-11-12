"""`scope3colab_dump` 의 꼴: 짓개로 만든 작은 템플릿·계수 책·짜 둔 답으로 돌려 `scope3colab.rows/1` 의 칸·줄 수를 본다.

순수 층에서 돈다(DB·네트워크 0). 숫자·글의 값은 `engines/scope3/colab_157/test_purchase.py`(C1·C2)와
`test_transport_spend.py`·`test_travel_spend.py`·`test_waste_sheet.py`(C4·C9·C6·C5)가 문다 — 여기는 꼴만(S9: 열쇠·item·
칸 차례·줄 수, 지원 안 함 시트 두 경우, 결과 파일의 `%.16g` 자름).
"""

import io
import json
import zipfile
from pathlib import Path
from typing import Any, cast

import openpyxl
import pandas as pd
import pytest
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

from esgapi.inventory.engines.scope3.colab_157 import pipeline
from esgapi.inventory.tests import scope3colab_dump as dump_module
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    C11_ROW,
    C12_ROW,
    Value,
    c3_sheet,
    c11_sheet,
    c12_sheet,
    c14_sheet,
    c15_sheet,
    energy_annual,
    energy_factor_sheets,
    energy_monthly,
    leased_sheet,
    sheet,
    waste_c12_ef_sheet,
    workbook,
    xlsx_bytes,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, C1_ROWS, C2_ROWS, MCS
from esgapi.inventory.tests.engines.scope3.colab_157.test_transport_spend import C4_HEAD, C4_SUB, T_ROWS
from esgapi.inventory.tests.engines.scope3.colab_157.test_travel_spend import C6_HEAD, C6_SUB, V_ROWS
from esgapi.inventory.tests.engines.scope3.colab_157.test_waste_sheet import C5_SUB, W_ROWS
from esgapi.inventory.tests.scope3colab_dump import (
    ENERGY_C3_FIELDS,
    FIELDS,
    FRANCHISE_FIELDS,
    INVESTMENT_FIELDS,
    LEASED_FIELDS,
    PRODUCT_EOL_FIELDS,
    PRODUCT_USE_FIELDS,
    SCHEMA,
    SHEET_FIELDS,
    RecordingGeocoder,
    dump,
    main,
    number_text,
    read_book,
)
from esgapi.inventory.tools.scope3_sheets.grid import FormulaCell, NumberCell, Sheet, TextCell, Workbook
from esgapi.inventory.tools.xlsx_reader import read_workbook

C1_ONE = {n: C1_ROWS[n] for n in (4, 5, 6)}  # 사용자 그룹 「컨설팅」 · 수작업 규칙


def inputs(tmp_path: Path, answers: list[dict[str, Any]]) -> list[str]:
    template = tmp_path / "template.xlsx"
    book = tmp_path / "book.xlsx"
    answers_path = tmp_path / "answers.json"
    template.write_bytes(xlsx_bytes(workbook(sheet("C1_구매품서비스", C1_ONE), sheet("C2_자본재", C2_ROWS))))
    book.write_bytes(xlsx_bytes(workbook(sheet("구매_USEPA", BOOK_ROWS))))
    answers_path.write_text(json.dumps({"synthetic": True, "answers": answers}, ensure_ascii=False), "utf-8")
    return ["--template", str(template), "--factor-book", str(book), "--answers", str(answers_path)]


# 두 줄 모두 후보가 다섯이 안 돼 옛 추천(NAICS 고르기 LLM)에 닿는다 — 한 번씩, 줄 차례대로
ANSWERS = [
    {"text": '{"generic_english": ""}', "expect": "가상 경영자문"},
    {"text": '{"generic_english": ""}', "expect": "가상 지게차"},
]


def test_dump_writes_the_rows_shape(tmp_path: Path, capsys: Any) -> None:
    assert main(inputs(tmp_path, ANSWERS)) == 0
    data = json.loads(capsys.readouterr().out)
    assert (data["schema"], data["side"], data["not_compared"]) == (SCHEMA, "engine", [])
    assert [(r["sheet"], r["row"], r["item"]) for r in data["rows"]] == [
        ("C1", 1, "가상 경영자문"),
        ("C2", 1, "가상 지게차"),
    ]
    for row in data["rows"]:
        assert set(row) == {"sheet", "row", "item", "fields"}
        assert list(row["fields"]) == [name for name, _, _ in FIELDS]
    c1 = data["rows"][0]["fields"]
    assert (c1["대표EF"], c1["대표EF_배출계수"], c1["구매금액(KRW)"]) == (MCS, repr(9.1e-05), repr(9100000.0))
    assert c1["추천EF3"] is None  # 후보 셋 — 넷째 추천 열은 없다(null)


def test_dump_fails_when_an_answer_is_left_over(tmp_path: Path, capsys: Any) -> None:
    extra = [*ANSWERS, {"text": "가상", "expect": None}]
    assert main(inputs(tmp_path, extra)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "3 가운데 2 만 쓰였다" in captured.err


def test_dump_fails_when_the_call_order_differs(tmp_path: Path, capsys: Any) -> None:
    assert main(inputs(tmp_path, ANSWERS[::-1])) == 2
    assert "부름 차례가 어긋남" in capsys.readouterr().err


def openpyxl_bytes(value: str | CellRichText) -> bytes:
    """openpyxl 이 쓴 xlsx(절대 Target · inlineStr) — esg-lab 이 짓는 입력과 같은 꼴."""
    book = openpyxl.Workbook()
    sheet_ = book.active
    assert sheet_ is not None
    sheet_.title = "가상시트"
    sheet_["A1"] = value
    sheet_["B1"] = 9.5
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def test_openpyxl_inline_strings_keep_their_escapes(tmp_path: Path) -> None:
    raw = openpyxl_bytes("가상 & <글>")
    with zipfile.ZipFile(io.BytesIO(raw)) as parts:
        assert b'Target="/xl/' in parts.read("xl/_rels/workbook.xml.rels")
        sheet_xml = parts.read("xl/worksheets/sheet1.xml")
    assert b't="inlineStr"' in sheet_xml and b"&amp; &lt;" in sheet_xml
    path = tmp_path / "book.xlsx"
    path.write_bytes(raw)
    cells = read_book(path).sheets[0].cells
    assert cells["A1"] == TextCell("가상 & <글>")
    assert isinstance(cells["B1"], NumberCell)  # 수 칸은 그대로 읽힌다


def test_rich_inline_strings_are_joined_without_a_bypass(tmp_path: Path) -> None:
    """T5: 서식 조각 inlineStr 도 우회 없이 이어 읽는다(MARC-ISSUE-241 — 옛 dump 우회는 이 꼴에서 도구 실패였다)."""
    path = tmp_path / "book.xlsx"
    path.write_bytes(openpyxl_bytes(CellRichText(["가상", TextBlock(InlineFont(b=True), "굵게")])))
    with zipfile.ZipFile(path) as parts:
        assert b"<r>" in parts.read("xl/worksheets/sheet1.xml")
    assert read_book(path).sheets[0].cells["A1"] == TextCell("가상굵게")


def test_an_openpyxl_saved_workbook_reads_as_openpyxl_reads_it() -> None:
    """T4: openpyxl `Workbook().save` 꼴(절대 Target·inlineStr·셈하지 않은 수식·참거짓)을 우리 읽개가
    2-0 a 정답지대로 읽는다."""
    book = openpyxl.Workbook()
    sheet_ = book.active
    assert sheet_ is not None
    sheet_.title = "가상시트"
    sheet_.append(["가상 & 이름", 3, 1.5, "=B1*2", True, False, None, ""])
    raw = io.BytesIO()
    book.save(raw)
    read = read_workbook(raw.getvalue())
    assert isinstance(read, Workbook), read
    assert read.sheets[0].cells == {
        "A1": TextCell("가상 & 이름"),
        "B1": NumberCell("3", "3"),
        "C1": NumberCell("1.5", "1.5"),
        "D1": FormulaCell("B1*2", None, None),
        "E1": TextCell("TRUE"),
        "F1": TextCell("FALSE"),
    }  # G1(None)은 쓰이지 않고, H1("")은 `<is>` 없는 `<c t="inlineStr">` 로 쓰여 칸 없음
    with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as parts:
        assert b'<c r="H1" t="inlineStr"></c>' in parts.read("xl/worksheets/sheet1.xml")
    again = openpyxl.load_workbook(io.BytesIO(raw.getvalue()), data_only=True)["가상시트"]
    assert [c.value for c in again[1]] == ["가상 & 이름", 3, 1.5, None, True, False, None, None]


def test_a_pandas_to_excel_frame_with_gaps_reads_as_pandas_reads_it() -> None:
    """T4: `DataFrame.to_excel` 의 NaN·None 칸은 `<c t="inlineStr"/>`(값 없음) 또는 빈 칸 — 우리 읽개에서 칸 없음."""
    frame = pd.DataFrame({"이름": ["가상", None], "값": [1.25, float("nan")], "수": [1, 2], "여부": [True, False]})
    raw = io.BytesIO()
    cast(Any, frame).to_excel(raw, index=False)
    read = read_workbook(raw.getvalue())
    assert isinstance(read, Workbook), read
    assert read.sheets[0].cells == {
        "A1": TextCell("이름"),
        "B1": TextCell("값"),
        "C1": TextCell("수"),
        "D1": TextCell("여부"),
        "A2": TextCell("가상"),
        "B2": NumberCell("1.25", "1.25"),
        "C2": NumberCell("1", "1"),
        "D2": TextCell("TRUE"),
        "C3": NumberCell("2", "2"),
        "D3": TextCell("FALSE"),
    }
    again = cast(Any, pd).read_excel(io.BytesIO(raw.getvalue()))
    assert again.iloc[0].tolist() == ["가상", 1.25, 1, True]
    assert pd.isna(again.iloc[1]["이름"]) and pd.isna(again.iloc[1]["값"])


def test_the_dump_writers_output_reads_back_with_our_reader() -> None:
    """T4: c2 쓰개 둘이 쓴 결과 파일·채운 템플릿을 우리 읽개가 `ReaderProblem` 없이 읽는다. 채운 칸 = `CellWrite` 값,
    수식 칸 글자 = 원본(채운 템플릿은 셈하지 않은 수식의 빈 `<v/>` 꼴이 된다)."""
    result = dump_module.write_result_file(
        (
            dump_module.ResultSheet(
                "C1_가상", ("이름", "배출량", "여부", "빈"), (("가상", 0.5, True, None), ("나", 2, False, None))
            ),
        )
    )
    read = read_workbook(result)
    assert isinstance(read, Workbook), read
    assert read.sheets[0].cells["A2"] == TextCell("가상")
    assert read.sheets[0].cells["B2"] == NumberCell("0.5", "0.5")
    assert (read.sheets[0].cells["C2"], read.sheets[0].cells["C3"]) == (TextCell("TRUE"), TextCell("FALSE"))
    assert "D2" not in read.sheets[0].cells
    template = openpyxl.Workbook()
    first = template.active
    assert first is not None
    first.title = "가상"
    first.append(["안내", None, "=1+2"])
    raw = io.BytesIO()
    template.save(raw)
    writes = (dump_module.CellWrite("가상", 1, 2, 9.41e-05), dump_module.CellWrite("가상", 2, 1, 3))
    filled = read_workbook(dump_module.write_filled_template(raw.getvalue(), writes))
    assert isinstance(filled, Workbook), filled
    assert filled.sheets[0].cells == {
        "A1": TextCell("안내"),
        "B1": NumberCell("9.41e-05", "0.0000941"),
        "C1": FormulaCell("1+2", None, None),
        "A2": NumberCell("3", "3"),
    }


# ── S9: 지출·폐기물 열쇠(C4·C9·C6·C5) ──

C9_HEAD: list[Value] = ["*사업장", "운송수단(선택)", "*제품명", "연간 입력", "월별 운송금액", None]
C5_HEAD: list[Value] = [
    "*사업장",
    "*폐기물 종류",
    "상세 폐기물명(선택)",
    "*처리방법",
    "단위",
    "연간 입력",
    "월별 처리량",
    None,
]
C5_SUB_DETAIL: list[Value] = [None, *C5_SUB]
DIST_HEAD: list[Value] = ["*사업장", "*자재명/품목명", "출발지", "도착지", "연간 입력", "월별 운송량"]
DIST_SUB: list[Value] = [None, None, None, None, "연간운송량", "1월"]
C11_HEAD: list[Value] = ["*국가", "*제품명", "*제품수량", "*에너지명", "*제품당 연간 에너지 사용량", "*단위"]


def template_sheet(name: str, head: list[Value], sub: list[Value], *rows: list[Value]) -> Sheet:
    return sheet(name, {4: head, 5: sub, **{6 + i: row for i, row in enumerate(rows)}})


C4_1_HEADER_ONLY = template_sheet("c4-1_운송거리", DIST_HEAD, DIST_SUB)
ACTIVITY_TEMPLATE: tuple[Sheet, ...] = (
    C4_1_HEADER_ONLY,  # 머리글만 → 읽기 실패(코랩 `[error]`)로 결과에 없다
    template_sheet("c4-2_운송금액", C4_HEAD, C4_SUB, ["가상사업장", "가상 택배", "가상부품", 9100000],
                   ["가상사업장", "가상 소포", "가상원료", 9200000]),
    # 같은 Category4 의 둘째 시트 — 코랩은 한 결과 시트로 합친다(row 가 이어진다)
    template_sheet("c4-2_운송금액(가상)", C4_HEAD, C4_SUB, ["가상사업장", "가상 택배", "가상포장", 9300000]),
    template_sheet("c5_사업장폐기물", C5_HEAD, C5_SUB_DETAIL, ["가상사업장", "가상폐지", None, "소각", "kg", 9100],
                   ["가상사업장", "가상폐수지", None, "매립", "kg", None, 9200, 9300]),
    template_sheet("c6-2_출장비", C6_HEAD, C6_SUB, ["가상사업장", "가상 택시비", 9100000]),
    template_sheet("c9-2_운송금액", C9_HEAD, C4_SUB, ["가상사업장", "가상 택배", "가상완제품", 9400000]),
)  # fmt: skip
ACTIVITY_BOOK = (
    sheet("구매_USEPA", BOOK_ROWS),
    sheet("운송_Spend", T_ROWS),
    sheet("출장_Spend", V_ROWS),
    sheet("폐기물_C5", W_ROWS),
)


def activity_inputs(tmp_path: Path, template: tuple[Sheet, ...]) -> list[str]:
    paths = (tmp_path / "template.xlsx", tmp_path / "book.xlsx", tmp_path / "answers.json")
    paths[0].write_bytes(xlsx_bytes(workbook(*template)))
    paths[1].write_bytes(xlsx_bytes(workbook(*ACTIVITY_BOOK)))
    paths[2].write_text(json.dumps({"synthetic": True, "answers": []}), "utf-8")  # 모두 규칙으로 닿는다(AI 0)
    return ["--template", str(paths[0]), "--factor-book", str(paths[1]), "--answers", str(paths[2])]


def test_activity_keys_items_fields_and_row_order(tmp_path: Path, capsys: Any) -> None:
    assert main(activity_inputs(tmp_path, ACTIVITY_TEMPLATE)) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["not_compared"] == []
    assert [(r["sheet"], r["row"], r["item"]) for r in data["rows"]] == [
        ("C4", 1, "가상부품"),
        ("C4", 2, "가상원료"),
        ("C4", 3, "가상포장"),  # 둘째 C4-2 시트 — 이어 셈
        ("C5", 1, "가상폐수지"),  # 월별 줄이 먼저(코랩 `_melt_monthly_or_annual` 의 concat)
        ("C5", 2, "가상폐지"),
        ("C6", 1, "가상 택시비"),
        ("C9", 1, "가상완제품"),
    ]
    for row in data["rows"]:
        assert list(row["fields"]) == [name for name, _, _ in SHEET_FIELDS[row["sheet"]]]
    by_key = {(r["sheet"], r["row"]): r["fields"] for r in data["rows"]}
    assert by_key[("C4", 1)] == {
        "운송금액": repr(9100000.0),
        "EF(kgCO2e/KRW)": repr(9.22e-05),
        "배출계수단위": "kgCO2e/KRW",
        "배출량(tCO2e)": repr(float("%.16g" % (9100000 * 9.22e-05 / 1000))),
    }
    c5 = by_key[("C5", 1)]
    assert (c5["처리량"], c5["처리방법_정규화"], c5["화석탄소비율(FCF)"], c5["바이오매스 구분"]) == (
        str(9200 + 9300),  # 정수 칸의 월 합은 정수(코랩도 정수로 쓴다)
        "매립",
        None,
        "해당없음",
    )
    assert by_key[("C5", 2)]["바이오매스 구분"] == "폐지류 소각: 생물기원 99% / 화석기원 1%"
    c6 = by_key[("C6", 1)]
    assert (c6["EF_DB"], c6["NAICS"], c6["정규화이동수단"]) == ("Taxi Service", "9203", "taxi")
    assert c6["계산식"] is not None and c6["계산식"].startswith("배출량(tCO2e) = 출장비용(KRW)")


def test_the_activity_template_asks_the_geocoder_nothing(tmp_path: Path) -> None:
    """지출·폐기물 시트와 머리글만인 C4-1 은 지오코더를 부르지 않는다(S3C-b2a — 거절하던 가짜를 기록하는 가짜로
    바꿈)."""
    args = activity_inputs(tmp_path, ACTIVITY_TEMPLATE)
    geocoder = RecordingGeocoder()
    dump(Path(args[1]), Path(args[3]), Path(args[5]), 2025, geocoder)
    assert geocoder.queries == []


def test_the_field_names_follow_the_o2_table() -> None:
    """S3C-o2 보고 「b1 이 따를 표」 = esg-lab rows.py(49e4515) 의 칸 이름·차례."""
    names = {key: [name for name, _, _ in fields] for key, fields in SHEET_FIELDS.items()}
    assert names["C4"] == names["C9"] == ["운송금액", "EF(kgCO2e/KRW)", "배출계수단위", "배출량(tCO2e)"]
    assert names["C6"] == [
        "출장비용", "EF_DB", "NAICS", "배출계수", "배출계수단위", "배출량(tCO2e)", "계산식", "정규화이동수단",
    ]  # fmt: skip
    assert names["C5"] == [
        "처리량", "배출계수(kgCO2eq/kg)", "처리방법_정규화", "화석기원 CO2e(tCO2e)", "생물기원 CO2e(tCO2e)",
        "화석탄소비율(FCF)", "바이오매스 구분", "배출량(tCO2e)", "단위환산비고",
    ]  # fmt: skip
    assert names["C1"] == names["C2"] == [name for name, _, _ in FIELDS]
    assert all(name == column for fields in SHEET_FIELDS.values() if fields is not FIELDS for name, column, _ in fields)


def test_the_item_is_the_first_candidate_column_with_a_value(tmp_path: Path, capsys: Any) -> None:
    """C5 의 「폐기물 종류」 칸이 모두 비면 다음 후보 「상세폐기물명」(코랩은 전부 빈 열을 지운다)."""
    c5 = template_sheet(
        "c5_사업장폐기물", C5_HEAD, C5_SUB_DETAIL, ["가상사업장", None, "가상 사무 종이", "소각", "kg", 9100]
    )
    assert main(activity_inputs(tmp_path, (c5,))) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [(r["sheet"], r["row"], r["item"]) for r in rows] == [("C5", 1, "가상 사무 종이")]


def test_an_unsupported_sheet_with_data_rows_fails_the_tool(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S3C-c1b-2 부터 21키를 다 처리해 지원 안 함 시트가 남지 않는다 — 가짜로 c11 을 지원 열쇠에서 빼고 본다(단언 뜻
    그대로: 견주는 열쇠의 지원 안 함 시트에 데이터 줄이 있으면 도구 실패)."""
    monkeypatch.setattr(pipeline, "SUPPORTED_KEYS", pipeline.SUPPORTED_KEYS - {"c11"})
    c11 = sheet("c11_판매제품사용", {4: C11_HEAD, 5: ["가상국", "가상제품", 9, "전력", 9.1, "kWh"]})
    assert main(activity_inputs(tmp_path, (*ACTIVITY_TEMPLATE, c11))) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "C11: 지원하지 않는 시트 'c11_판매제품사용' 에 데이터 줄이 있다" in captured.err


# ── S3C-c1a ②: C3·C8·C13(따를 표 1·3 — C8·C13 은 시트 셋 이어 셈, C11 은 S3C-c1b-2 부터 견줌) ──


def energy_inputs(tmp_path: Path, template: tuple[Sheet, ...]) -> list[str]:
    paths = (tmp_path / "template.xlsx", tmp_path / "book.xlsx", tmp_path / "answers.json")
    paths[0].write_bytes(xlsx_bytes(workbook(*template)))
    paths[1].write_bytes(xlsx_bytes(workbook(*ACTIVITY_BOOK, *energy_factor_sheets())))
    paths[2].write_text(json.dumps({"synthetic": True, "answers": []}), "utf-8")  # 모두 규칙으로 닿는다(AI 0)
    return ["--template", str(paths[0]), "--factor-book", str(paths[1]), "--answers", str(paths[2])]


ENERGY_TEMPLATE: tuple[Sheet, ...] = (
    c3_sheet("c3_연료에너지", energy_annual(["가상국", "가상사업장", "전력", "kWh"], 9100),
             energy_monthly(["가상국", "가상사업장", "경유", "L"], {1: 910})),
    leased_sheet("c8-1_에너지사용량 아는 경우", energy_annual(["가상국", "가상자산", "전력", "kWh"], 91000)),
    leased_sheet("c8-2_면적", energy_annual(["가상국", "가상자산", 9000, 900, "경유", "L"], 9100),
                 energy_annual(["가상국", "가상자산", 9000, 90, "전력", "kWh"], 9200)),
    leased_sheet("c8-3_인원", energy_annual(["가상국", "가상자산", 90, 9, "전력", "kWh"], 99000)),
    sheet("c11_판매제품사용", {4: C11_HEAD, 5: ["가상국", "가상제품", 9, "전력", 9.1, "kWh"]}),
    leased_sheet("c13-1_에너지사용량 아는경우", energy_annual(["가상국", "가상자산", "경유", "L"], 9400)),
    leased_sheet("c13-3_인원", energy_annual(["가상국", "가상자산", 90, 9, "천연가스(LNG)", "kg"], 1930)),
)  # fmt: skip


def test_energy_keys_items_fields_and_continued_rows(tmp_path: Path, capsys: Any) -> None:
    assert (SHEET_FIELDS["C3"], SHEET_FIELDS["C8"], SHEET_FIELDS["C13"]) == (
        ENERGY_C3_FIELDS,
        LEASED_FIELDS,
        LEASED_FIELDS,
    )
    assert main(energy_inputs(tmp_path, ENERGY_TEMPLATE)) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["not_compared"] == []  # C11 도 S3C-c1b-2 부터 견주는 열쇠
    assert [(r["sheet"], r["row"], r["item"]) for r in data["rows"]] == [
        ("C3", 1, "경유"),  # 월별 먼저
        ("C3", 2, "전력"),
        ("C8", 1, "전력"),
        ("C8", 2, "경유"),  # C8-2 — 이어 셈
        ("C8", 3, "전력"),
        ("C8", 4, "전력"),  # C8-3
        ("C11", 1, "가상제품"),  # S3C-c1b-2
        ("C13", 1, "경유"),
        ("C13", 2, "천연가스(LNG)"),  # C13-3 — C13-2 가 없어도 이어 셈
    ]
    assert all("branch" not in r for r in data["rows"])
    c3, c8_area = data["rows"][0]["fields"], data["rows"][3]["fields"]
    assert list(c3) == [name for name, _, _ in ENERGY_C3_FIELDS]
    assert c3 == {
        "사용량": "910.0",
        "배출계수(kgCO2eq/단위)": "0.0952",
        "EF단위": "L",
        "EF매핑명": "경유",
        "단위환산비고": None,
        "배출량(tCO2e)": repr(910.0 * 0.0952 / 1000),
    }
    assert c8_area == {
        "산정방식": "면적배분",
        "건물전체사용량": "9100.0",
        "면적비율": "0.1",
        "인원비율": None,
        "사용량": "910.0",
        "배출계수(kgCO2eq/단위)": "0.942",
        "EF단위": "L",
        "단위환산비고": None,
        "배출량(tCO2e)": repr(9100.0 * 0.1 * 0.942 / 1000),
    }


def test_the_leased_item_prefers_the_energy_source_column(tmp_path: Path, capsys: Any) -> None:
    """C8 item 후보는 「에너지원」 → 「에너지종류」(따를 표 1). 두 열이 다 있으면 표준화가 rename 하지 않아 둘 다
    남는다."""
    month_group: list[Value] = [None] * 11
    head: list[Value] = [
        "*국가", "*임차자산명", "에너지원", "*에너지종류", "*단위", "연간 입력", "월별 사용량", *month_group,
    ]  # fmt: skip
    sub: list[Value] = [None, None, None, None, None, "연간사용량", *(f"{i}월" for i in range(1, 13))]
    c8 = sheet(
        "c8-1_에너지사용량 아는 경우",
        {1: ["가상 안내"], 2: head, 3: sub, 4: ["가상국", "가상자산", "전력", "가상 전기", "kWh", 91000]},
    )
    assert main(energy_inputs(tmp_path, (c8,))) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [(r["sheet"], r["row"], r["item"]) for r in rows] == [("C8", 1, "전력")]


def test_numbers_are_the_result_file_values() -> None:
    """openpyxl 은 수를 `%.16g` 로 쓴다 — 17자리 float 는 파일에서 잘린다(S3C-b1 대조의 C9 줄)."""
    assert repr(1845000 * 0.000914 / 1000) == "1.6863299999999999"
    assert number_text(1845000 * 0.000914 / 1000) == "1.68633"
    assert number_text(0.08472100000000005) == "0.08472100000000005"  # 16자리는 그대로
    assert (number_text(9.1e-05), number_text(9100000.0), number_text(9)) == ("9.1e-05", "9100000.0", "9")
    assert (number_text(float("nan")), number_text(float("inf")), number_text(None)) == (None, None, None)


# ── S3C-c1b-1: C12·C15(따를 표 1·3 — C12 item 「제품명」, C15 item 「피투자기업명」 rename, C15 배출량은 단위 없는
# 이름) ──


def test_product_keys_items_and_fields(tmp_path: Path, capsys: Any) -> None:
    assert (SHEET_FIELDS["C12"], SHEET_FIELDS["C15"]) == (PRODUCT_EOL_FIELDS, INVESTMENT_FIELDS)
    paths = (tmp_path / "template.xlsx", tmp_path / "book.xlsx", tmp_path / "answers.json")
    second: list[Value] = [
        "가상국", "92 | 가상 사업장", "92-01 | 가상 수지", "선택안함", "가상수지용기", 9200, 0.95, "kg",
        9, 9, 90, None, None,
    ]  # fmt: skip
    template = (c12_sheet("c12_판매제품폐기", C12_ROW, second), c15_sheet())
    paths[0].write_bytes(xlsx_bytes(workbook(*template)))
    paths[1].write_bytes(xlsx_bytes(workbook(*ACTIVITY_BOOK, waste_c12_ef_sheet())))
    paths[2].write_text(json.dumps({"synthetic": True, "answers": []}), "utf-8")  # AI 0
    args = ["--template", str(paths[0]), "--factor-book", str(paths[1]), "--answers", str(paths[2])]
    assert main(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["not_compared"] == []
    assert [(r["sheet"], r["row"], r["item"]) for r in data["rows"]] == [
        ("C12", 1, "가상종이상자"),
        ("C12", 2, "가상수지용기"),
        ("C15", 1, "가상투자처A"),
    ]
    first, _, c15 = (r["fields"] for r in data["rows"])
    ef = 0.0 + 0.961 * 0.09 + 0.962 * 0.09 + 0.0963 * 0.9
    total = 9100 * 0.9 * ef / 1000.0
    bio = 9100 * 0.9 * 0.09 * 0.962 / 1000.0 * (1 - 0.01)
    assert first == {
        "배출계수": number_text(ef),
        "화석기원 CO2e(tCO2e)": number_text(total - bio),
        "생물기원 CO2e(tCO2e)": number_text(bio),
        "화석탄소비율(FCF)": "0.01",
        "바이오매스 구분": "폐지류 소각: 생물기원 99% / 화석기원 1%",
        "배출량(tCO2e)": number_text(total - bio),
    }
    assert c15 == {"배출량": number_text((910.0 + 920.0) * (9.5 / 100))}


# ── S3C-c1b-2: C11·C14(따를 표 1·3 — 결과 후처리 뒤 값, EF매핑방식·점수는 견주지 않음) ──


def test_product_use_and_franchise_keys_items_and_fields(tmp_path: Path, capsys: Any) -> None:
    assert (SHEET_FIELDS["C11"], SHEET_FIELDS["C14"]) == (PRODUCT_USE_FIELDS, FRANCHISE_FIELDS)
    assert (dump_module.ITEM_COLUMNS["C11"], dump_module.ITEM_COLUMNS["C14"]) == (
        ("제품명", "에너지명"),
        ("프랜차이즈명",),
    )
    paths = (tmp_path / "template.xlsx", tmp_path / "book.xlsx", tmp_path / "answers.json")
    second: list[Value] = ["가상국", None, None, "가상제품B", 950, "전력", 0.92, "MWh", None, None]
    paths[0].write_bytes(xlsx_bytes(workbook(c11_sheet("c11_판매제품사용", C11_ROW, second), c14_sheet())))
    paths[1].write_bytes(xlsx_bytes(workbook(*ACTIVITY_BOOK, *energy_factor_sheets())))
    paths[2].write_text(json.dumps({"synthetic": True, "answers": []}), "utf-8")  # 모두 규칙으로 닿는다(AI 0)
    args = ["--template", str(paths[0]), "--factor-book", str(paths[1]), "--answers", str(paths[2])]
    assert main(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["not_compared"] == []
    assert [(r["sheet"], r["row"], r["item"]) for r in data["rows"]] == [
        ("C11", 1, "가상제품A"),
        ("C11", 2, "가상제품B"),
        ("C14", 1, "가상가맹A"),
    ]
    first, mwh, c14 = (r["fields"] for r in data["rows"])
    assert list(first) == [name for name, _, _ in PRODUCT_USE_FIELDS]
    assert first == {
        "사용기간(년)": "8.0",
        "총사용량": number_text(900 * 9.1 * 8.0),
        "배출계수(kgCO2eq/단위)": "0.0941",
        "EF단위": "kWh",
        "EF매핑명": "전력",
        "단위환산비고": None,
        "배출량(tCO2e)": number_text(900 * 9.1 * 8.0 * 0.0941 / 1000.0),
    }
    assert (mwh["사용기간(년)"], mwh["총사용량"], mwh["단위환산비고"]) == (
        "1.0",
        number_text(950 * 920.0),
        "MWh→kWh (×1000)",
    )
    assert list(c14) == [name for name, _, _ in FRANCHISE_FIELDS]
    assert c14 == {
        "사용량": "9100.0",
        "배출계수(kgCO2eq/단위)": "0.942",
        "EF단위": "L",
        "EF매핑명": "경유",
        "단위환산비고": None,
        "배출량(tCO2e)": number_text(9100.0 * 0.942 / 1000.0),
        "계산식": f"배출량(tCO2e) = 사용량 × EF / 1000 = 9100 × 0.942 / 1000 = {9100.0 * 0.942 / 1000.0:g}",
    }


# ── S3C-c2: 출력 파일 둘(T6 원본 불변 · T8 덤프 인자) ──


def file_args(tmp_path: Path) -> list[str]:
    return ["--result-file", str(tmp_path / "out_result.xlsx"), "--filled-file", str(tmp_path / "out_filled.xlsx")]


def test_dump_writes_the_two_output_files_and_keeps_the_json(tmp_path: Path, capsys: Any) -> None:
    assert main(inputs(tmp_path, ANSWERS)) == 0
    plain = capsys.readouterr().out
    assert main([*inputs(tmp_path, ANSWERS), *file_args(tmp_path)]) == 0
    assert capsys.readouterr().out == plain  # 파일 인자는 JSON 을 바꾸지 않는다
    result = openpyxl.load_workbook(tmp_path / "out_result.xlsx")
    assert result.sheetnames == ["C1_구매품서비스", "C2_자본재"]
    filled = openpyxl.load_workbook(tmp_path / "out_filled.xlsx")
    assert filled.sheetnames == openpyxl.load_workbook(tmp_path / "template.xlsx").sheetnames


def test_outputs_failed_fails_the_tool_only_when_files_are_asked(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object) -> object:
        raise ValueError("가상 짓기 실패")

    monkeypatch.setattr(pipeline, "build_outputs", broken)
    assert main(inputs(tmp_path, ANSWERS)) == 0
    capsys.readouterr()
    assert main([*inputs(tmp_path, ANSWERS), *file_args(tmp_path)]) == 2
    assert "OutputsFailed" in capsys.readouterr().err
    assert not (tmp_path / "out_result.xlsx").exists()


def test_the_filled_writer_opens_the_original_template_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[bytes] = []
    original = openpyxl.load_workbook

    def spy(source: io.BytesIO) -> Any:
        seen.append(source.getvalue())
        return original(source)

    monkeypatch.setattr(dump_module.openpyxl, "load_workbook", spy)
    args = inputs(tmp_path, ANSWERS)
    assert main([*args, *file_args(tmp_path)]) == 0
    assert seen == [(tmp_path / "template.xlsx").read_bytes()]


def test_the_filled_template_keeps_every_cell_outside_the_writes(tmp_path: Path) -> None:
    """T6: 회색 칸 밖 칸·수식 글자·시트 차례가 원본과 같다(openpyxl 로 열어 견줌)."""
    book = openpyxl.Workbook()
    first = book.active
    assert first is not None
    first.title = "c14_프랜차이즈"
    first.append(["가상 안내"])
    first.append(["프랜차이즈명", "배출계수(tCO2e/단위)", "배출량(tCO2e)", "가상 식"])
    first.append(["가상A", None, None, "=SUM(1,2)"])
    book.create_sheet("가상 둘").append(["가상", 9.5])
    raw = io.BytesIO()
    book.save(raw)
    writes = (
        dump_module.CellWrite("c14_프랜차이즈", 3, 2, 9.41e-05),
        dump_module.CellWrite("c14_프랜차이즈", 3, 3, 0.9),
    )
    out = openpyxl.load_workbook(io.BytesIO(dump_module.write_filled_template(raw.getvalue(), writes)))
    before = openpyxl.load_workbook(io.BytesIO(raw.getvalue()))
    assert out.sheetnames == before.sheetnames
    for name in before.sheetnames:
        old = {c.coordinate: c.value for row in before[name].iter_rows() for c in row}
        new = {c.coordinate: c.value for row in out[name].iter_rows() for c in row}
        changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
        assert changed == ({"B3", "C3"} if name == "c14_프랜차이즈" else set())
    assert out["c14_프랜차이즈"]["D3"].value == "=SUM(1,2)"
    assert (out["c14_프랜차이즈"]["B3"].value, out["c14_프랜차이즈"]["C3"].value) == (9.41e-05, 0.9)
