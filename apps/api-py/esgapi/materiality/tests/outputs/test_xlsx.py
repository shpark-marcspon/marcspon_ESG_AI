"""outputs/xlsx.py: 1부 엑셀을 되읽어 시트·B1·머리·F/G·Notes·RAW_JSON 왕복(32,767·32,768자 경계, `=` 로 시작하는 조각도
글자 칸)(발주서 §3 S9, 셀 33 R/1598-1682)."""

import copy
import io
import json
from pathlib import Path
from typing import Any, cast

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from esgapi.materiality.contracts import wire
from esgapi.materiality.outputs import xlsx

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"


def load_example() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / "result-sample.json").read_text(encoding="utf-8")))


def sheets(result: dict[str, Any]) -> tuple[Worksheet, Worksheet]:
    book = load_workbook(io.BytesIO(xlsx.build_websearch(result)))
    assert book.sheetnames == ["Shortlist", "RAW_JSON"]
    return cast("Worksheet", book["Shortlist"]), cast("Worksheet", book["RAW_JSON"])


def body(sheet: Worksheet) -> list[tuple[Any, ...]]:
    return [tuple(sheet[f"{c}{r}"].value for c in "ABCDEFG") for r in range(4, sheet.max_row + 1)]


def raw_text(raw: Worksheet) -> str:
    return "".join(str(raw.cell(row=r, column=1).value) for r in range(1, raw.max_row + 1))


def test_header_and_title() -> None:
    sheet, _ = sheets(load_example())
    assert sheet["A1"].value is None
    assert sheet["B1"].value == "1-1. Short-list 선정"
    assert sheet["B1"].font.bold
    assert [sheet[f"{c}3"].value for c in "ABCDEFG"] == [
        None,
        "No",
        "Topic",
        None,
        None,
        "규제 및 정책",
        "컨트로버시 이슈",
    ]
    assert all(sheet[f"{c}3"].font.bold and sheet[f"{c}3"].alignment.wrap_text for c in "BCFG")


def test_rows_follow_cell_33() -> None:
    sheet, _ = sheets(load_example())
    rows = body(sheet)
    # 토픽 합집합 sorted(): 가상토픽 둘 < 가상토픽 하나(셋은 돌리지 않아 빠짐)
    assert rows == [
        (None, 1, "가상토픽 둘", None, None, "(파싱 실패)", "(파싱 실패)"),
        (
            None,
            2,
            "가상토픽 하나",
            None,
            None,
            "1) title: 가상 규정 가, summary: 가상 규정 가의 요약., jurisdiction: 대한민국, authority: 가상부, "
            "event_date: 2025-03-01, publish_date: 2025-03-02, status: 시행 중, primary_url: https://example.go.kr/virtual/a",
            "1) title: 가상 사건 다, date: 2025-07-01, summary: 가상 사건 다의 요약., severity: 중간, status: 조사중, "
            "url: https://example.com/virtual/c",
        ),
        (
            None,
            2,
            "가상토픽 하나",
            None,
            None,
            "2) title: 가상 지침 나, summary: 가상 지침 나의 요약., jurisdiction: EU, authority: Virtual Commission, "
            "publish_date: 2025-05-10, status: 채택, primary_url: https://example.europa.eu/virtual/b",
            None,
        ),
        (None, 2, "가상토픽 하나", None, None, "[Notes] 가상 점검 메모.", "[Notes] 가상 컨트로버시 메모."),
    ]
    assert all(sheet[f"{c}{r}"].alignment.vertical == "top" for c in "BCFG" for r in range(4, sheet.max_row + 1))


def test_raw_json_is_the_colab_payload() -> None:
    result = load_example()
    _, raw = sheets(result)
    assert raw["A1"].value == json.dumps(wire.websearch_payload(result), ensure_ascii=False)
    assert raw.max_row == 1


def big_result(length: int) -> dict[str, Any]:
    """RAW_JSON 글이 정확히 length 자가 되게 규제 원문을 늘린다(조각의 머리가 `=` 가 되게)."""
    result = load_example()
    failed = result["part1"]["topics"][1]["regulation"]
    failed["raw"] = ""
    base = len(json.dumps(wire.websearch_payload(result), ensure_ascii=False))
    failed["raw"] = "=" * (length - base)
    return result


def test_raw_json_splits_at_32767() -> None:
    for length, rows in ((32767, 1), (32768, 2), (65535, 3)):
        result = big_result(length)
        _, raw = sheets(result)
        assert raw.max_row == rows
        assert raw_text(raw) == json.dumps(wire.websearch_payload(result), ensure_ascii=False)
        for r in range(1, rows + 1):
            assert raw.cell(row=r, column=1).data_type == "s"
        if rows > 1:
            assert len(str(raw["A1"].value)) == 32767
        if rows == 3:  # 규제 원문의 `=` 줄이 32,767 경계를 넘는다 — 둘째 조각이 `=` 로 시작해도 글자 칸
            assert str(raw.cell(row=2, column=1).value).startswith("=")


def test_text_cells_stay_text_and_lose_control_characters() -> None:
    result = load_example()
    con = copy.deepcopy(result["part1"]["topics"][0]["controversy"])
    con["parsed"]["results"]["items"][0]["title"] = "가상\x01제목"
    result["part1"]["topics"][0]["controversy"] = con
    result["part1"]["topics"][0]["topic"] = "=가상토픽"
    sheet, raw = sheets(result)
    assert sheet["C4"].value == "=가상토픽"
    assert sheet["C4"].data_type == "s"
    assert "가상제목" in str(sheet["G4"].value)
    assert "\\u0001" in raw_text(raw)  # RAW_JSON 은 json 이스케이프라 그대로 되읽힌다


def test_rule_4_takes_the_whole_root_as_one_item() -> None:
    result = load_example()
    result["part1"]["topics"] = result["part1"]["topics"][:1]
    for side in ("regulation", "controversy"):
        topic = result["part1"]["topics"][0][side]
        topic["parsed"] = {"topic_name": "가상토픽 하나"}
    sheet, _ = sheets(result)
    # 규칙 4: 목록이 없으면 묶음 값 통째가 항목 하나 — 표시 칸이 없어 「1) 」
    assert body(sheet) == [(None, 1, "가상토픽 하나", None, None, "1) ", "1) ")]


def test_no_items_means_one_empty_row() -> None:
    """셀 33 R/1663: n=0 이면 1행, F/G 빈칸."""
    result = load_example()
    result["part1"]["topics"] = result["part1"]["topics"][:1]
    result["part1"]["topics"][0]["regulation"]["parsed"] = {"results": {}}
    result["part1"]["topics"][0]["controversy"]["parsed"] = {"items": []}
    sheet, _ = sheets(result)
    assert body(sheet) == [(None, 1, "가상토픽 하나", None, None, None, None)]


def test_notes_only_on_the_side_that_has_them() -> None:
    """셀 33 R/1667-1671·처분 ⑪: Notes 행은 한쪽만 있어도 생기고, 없는 쪽 칸은 빈칸."""
    result = load_example()
    result["part1"]["topics"] = result["part1"]["topics"][:1]
    del result["part1"]["topics"][0]["controversy"]["parsed"]["self_check"]
    sheet, _ = sheets(result)
    assert body(sheet)[-1] == (None, 1, "가상토픽 하나", None, None, "[Notes] 가상 점검 메모.", None)
    del result["part1"]["topics"][0]["regulation"]["parsed"]["self_check"]
    sheet, _ = sheets(result)
    assert all(not str(row[5] or "").startswith("[Notes]") for row in body(sheet))


def test_a_lone_surrogate_does_not_break_the_file() -> None:
    """감독 처분 사소 2: 짝 없는 서로게이트(\\ud800)는 「?」로 — 파일은 저장되고 나머지 글은 그대로."""
    result = load_example()
    result["part1"]["topics"][0]["controversy"]["parsed"]["results"]["items"][0]["title"] = "가상\ud800제목"
    result["part1"]["topics"][1]["regulation"]["raw"] = "가상 원문 \ud800 끝"
    sheet, raw = sheets(result)
    assert "title: 가상?제목" in str(sheet["G5"].value)
    text = raw_text(raw)
    assert "가상 원문 ? 끝" in text
    assert text == xlsx.no_lone_surrogates(json.dumps(wire.websearch_payload(result), ensure_ascii=False))


def test_long_f_cell_is_cut_with_a_mark() -> None:
    """32,767자를 넘는 F 칸은 앞부분 + 「…(잘림: 원문 n자)」(밴드 IR2a 처분 ⑮ — openpyxl 의 말없는 자름 대신)."""
    result = load_example()
    item = result["part1"]["topics"][0]["regulation"]["parsed"]["results"]["KR"][0]
    item["title"] = "가" * 40_000
    sheet, _ = sheets(result)
    r = next(r for r in range(4, sheet.max_row + 1) if sheet[f"C{r}"].value == "가상토픽 하나")  # 토픽은 가나다 차례
    text = str(sheet[f"F{r}"].value)
    assert len(text) == 32_767
    assert text.startswith("1) title: " + "가" * 100)
    expected_length = len(xlsx.display(item, xlsx.REGULATION_ITEM_KEYS)) + len("1) ")
    assert text.endswith(f"…(잘림: 원문 {expected_length}자)")
    assert sheet[f"G{r}"].value is not None and len(str(sheet[f"G{r}"].value)) < 32_767  # 짧은 칸은 그대로


# ── UTF-16 단위(MARC-ISSUE-425, 밴드 IRS1 ①): Excel 은 칸 글자를 UTF-16 단위로 센다 — BMP 밖 글자는 둘.
SMILE = "\U0001f600"  # BMP 밖(UTF-16 둘)
OLD_HAN = "\U00020000"  # BMP 밖 옛 한자


def width(text: str) -> int:
    """시험 쪽 셈(구현과 따로): surrogatepass 로 UTF-16 을 지어 잰다 — 짝 없는 서로게이트도 한 단위."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def has_lone_surrogate(text: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def test_utf16_units() -> None:
    assert xlsx.utf16_units("") == 0
    assert xlsx.utf16_units("가") == 1
    assert xlsx.utf16_units(SMILE) == 2
    assert xlsx.utf16_units("\ud800") == 1  # 짝 없는 서로게이트 — 「?」 한 글자로 갈음된다
    assert xlsx.utf16_units("가" + SMILE + OLD_HAN + "a") == 6


def test_fit_cell_counts_utf16_units_at_the_boundary() -> None:
    exact = SMILE * 16_383 + "a"  # 폭 32,767
    assert xlsx.fit_cell(exact) == (exact, None)
    over = SMILE * 16_384  # 코드포인트 16,384 · 폭 32,768
    cut, length = xlsx.fit_cell(over)
    assert length == 32_768
    assert width(cut) <= 32_767
    assert cut.endswith("…(잘림: 원문 32768자)")
    kept = cut.removesuffix("…(잘림: 원문 32768자)")
    assert over.startswith(kept) and kept
    assert not has_lone_surrogate(cut)


def test_fit_cell_does_not_split_a_character_on_the_boundary() -> None:
    """남길 폭이 홀수면 BMP 밖 글자는 다음 칸으로 — 결과 폭 32,766. 앞에 「가」 하나를 두면 꼭 맞아 32,767."""
    mark = "…(잘림: 원문 32768자)"
    cut, _ = xlsx.fit_cell(SMILE * 16_384)
    assert (32_767 - width(mark)) % 2 == 1
    assert width(cut) == 32_766
    assert cut == SMILE * ((32_767 - width(mark)) // 2) + mark
    cut, length = xlsx.fit_cell("가" + SMILE * 16_384)
    assert length == 32_769
    assert width(cut) == 32_767
    assert cut.removesuffix("…(잘림: 원문 32769자)").endswith(SMILE)


def test_fit_cell_takes_a_lone_surrogate() -> None:
    cut, length = xlsx.fit_cell("\ud800" + "가" * 32_767)
    assert length == 32_768
    assert width(cut) == 32_767
    assert cut.startswith("\ud800가")  # 갈음은 칸에 넣을 때(cell_text) 한다


def test_raw_json_chunks_stay_within_utf16_units() -> None:
    result = load_example()
    result["part1"]["topics"][1]["regulation"]["raw"] = SMILE * 20_000 + OLD_HAN * 3
    text = json.dumps(wire.websearch_payload(result), ensure_ascii=False)
    assert len(text) < 32_767 < width(text)  # 코드포인트로는 한 조각, UTF-16 으로는 둘
    chunks = xlsx.raw_json_chunks(wire.websearch_payload(result))
    assert len(chunks) == 2
    assert "".join(chunks) == text
    assert all(width(c) <= 32_767 for c in chunks)
    assert width(chunks[0]) >= 32_766  # 앞 조각은 꽉 채운다(경계에 걸친 글자만 다음으로)
    _, raw = sheets(result)
    assert raw.max_row == 2
    assert raw_text(raw) == text
    assert width(str(raw["A1"].value)) <= 32_767  # 되읽은 칸도 Excel 기준 안


def test_long_f_cell_with_astral_characters_is_cut() -> None:
    """코드포인트로는 32,767 안이나 UTF-16 으로 넘는 F 칸도 앞부분 + 표시."""
    result = load_example()
    item = result["part1"]["topics"][0]["regulation"]["parsed"]["results"]["KR"][0]
    item["title"] = SMILE * 20_000
    sheet, _ = sheets(result)
    r = next(r for r in range(4, sheet.max_row + 1) if sheet[f"C{r}"].value == "가상토픽 하나")
    text = str(sheet[f"F{r}"].value)
    assert len(text) < 32_767
    assert width(text) <= 32_767
    expected = width("1) " + xlsx.display(item, xlsx.REGULATION_ITEM_KEYS))
    assert text.endswith(f"…(잘림: 원문 {expected}자)")
    assert text.startswith("1) title: " + SMILE * 100)
