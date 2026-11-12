"""outputs/final_xlsx.py: 최종 엑셀을 되읽어 시트 넷·B1·머리·No·라벨·url 합침·요약 줄·Pathway 없는 서브토픽 행 0·
RAW_JSON 왕복(A1 하나를 넘으면 A2…)·32,767자 칸 잘림 표시(발주서 §3 S4·S13, 셀 65 R/3368-3572). 기대값은 손으로
적었다(result2-sample.json 이 지은 「가상…」 값)."""

import copy
import io
import json
from pathlib import Path
from typing import Any, cast

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from esgapi.materiality.outputs import final_xlsx, xlsx

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"
SHEETS = ["1-1. Short-list 선정", "2-1. 환경사회 영향 식별", "2-2. 재무 영향 식별", "RAW_JSON"]


def example() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / "result2-sample.json").read_text(encoding="utf-8")))


def book_of(result: dict[str, Any]) -> tuple[dict[str, Worksheet], list[dict[str, Any]]]:
    content, cuts = final_xlsx.build_final(result)
    book = load_workbook(io.BytesIO(content))
    assert book.sheetnames == SHEETS
    return {name: cast("Worksheet", book[name]) for name in SHEETS}, cuts


def raw_text(raw: Worksheet) -> str:
    return "".join(str(raw.cell(row=r, column=1).value) for r in range(1, raw.max_row + 1))


def test_titles_and_headers() -> None:
    sheets, cuts = book_of(example())
    assert cuts == []
    short, soc, fin = sheets[SHEETS[0]], sheets[SHEETS[1]], sheets[SHEETS[2]]
    assert short["B1"].value == "1-1. Short-list 선정"
    assert [short[f"{c}4"].value for c in "BCFG"] == ["No", "Topic", "규제 및 정책", "컨트로버시 이슈"]
    assert soc["B1"].value == "2-1. 환경사회영향(Impact materiality) 식별"
    assert [soc[f"{c}5"].value for c in ("C", "D", "E", "Q", "R", "U")] == [
        "Topic",
        "No",
        "Subtopic",
        "영향 정의",
        "영향 유형 (긍정/부정)",
        "컨텍스트 요약 내용",
    ]
    assert fin["B1"].value == "2-2. 재무 영향(Financial materiality) 식별"
    assert [fin[f"{c}5"].value for c in ("C", "D", "E", "O", "P", "Q", "S", "T", "U", "AF")] == [
        "Topic",
        "No",
        "Subtopic",
        "영향 정의",
        "리스크/기회",
        "리스크 종류",
        "① Impact Driver",
        "② 비즈니스 영향",
        "③ 재무 영향",
        "컨텍스트 요약 내용",
    ]
    assert short["B4"].font.bold and short["B4"].alignment.wrap_text


def test_shortlist_rows_by_hand() -> None:
    sheets, _ = book_of(example())
    short = sheets[SHEETS[0]]
    assert [tuple(short[f"{c}{r}"].value for c in "BCFG") for r in range(5, short.max_row + 1)] == [
        (
            1,
            "가상토픽 하나",
            "1) [환경·사회] 제목: 가상 규정 가\n요약: 가상 규정 가의 요약\n출처: https://example.com/reg/가\n"
            "2) [재무] 제목: 가상 규정 나\n요약: 가상 규정 나의 요약\n출처: https://example.com/reg/나",
            "1) [환경·사회] 제목: 가상 사건 가\n요약: 가상 사건 가의 요약\n출처: https://example.com/con/가\n"
            "2) [재무] 제목: 가상 사건 나\n요약: 가상 사건 나의 요약\n출처: https://example.com/con/나",
        ),
        (2, "가상토픽 둘", None, None),
        (3, "가상토픽 셋", None, None),
    ]


def test_same_url_merges_and_gets_both_label() -> None:
    result = example()
    sub = result["part2"]["topics"][0]["subtopics"][0]
    shared = sub["impact"]["rows"][0]["context"]["regulations"][0]
    sub["financial"]["rows"][0]["context"]["regulations"] = [dict(shared, title="다른 제목")]
    sub["financial"]["rows"][1]["context"]["regulations"] = [
        dict(shared),
        {"title": "url 없음", "summary": None, "url": None},
    ]
    sheets, _ = book_of(result)
    assert sheets[SHEETS[0]]["F5"].value == (
        "1) [환경·사회·재무] 제목: 가상 규정 가\n요약: 가상 규정 가의 요약\n출처: https://example.com/reg/가\n"
        "2) [재무] 제목: url 없음\n요약: \n출처: "
    )


def test_empty_urls_are_never_merged() -> None:
    """url 이 null·빈 글·공백이면 서로 다른 항목으로 남는다(부재를 접지 않는다)."""
    soc = [{"title": "가", "summary": None, "url": ""}, {"title": "나", "summary": None, "url": "  "}]
    fin = [{"title": "다", "summary": None, "url": ""}, {"title": "라", "summary": None, "url": None}]
    got = final_xlsx.merged_items(soc, fin)
    assert [(label, item["title"]) for label, item in got] == [
        ("[환경·사회]", "가"),
        ("[환경·사회]", "나"),
        ("[재무]", "다"),
        ("[재무]", "라"),
    ]
    same = final_xlsx.merged_items(
        [{"title": "가", "url": "https://example.com/a"}], [{"title": "나", "url": " https://example.com/a "}]
    )
    assert [(label, item["title"]) for label, item in same] == [("[환경·사회·재무]", "가")]


def test_soc_and_fin_rows_by_hand() -> None:
    sheets, _ = book_of(example())
    soc, fin = sheets[SHEETS[1]], sheets[SHEETS[2]]
    assert soc.max_row == 6  # 영향 row 하나뿐(둘째 자리는 failed, 셋째는 rows 0)
    assert [soc[f"{c}6"].value for c in ("C", "D", "E", "Q", "R", "U")] == [
        "가상토픽 하나",
        1,
        "가상 서브토픽 가",
        "가상 시설 운영으로 전력 사용이 늘어 가상 배출 증가",
        "부정",
        "1. 가상 규정 가의 요약\n2. 가상 사건 가의 요약",
    ]
    assert fin.max_row == 7  # Pathway row 둘(Pathway 가 없는 서브토픽은 행 0)
    assert [fin[f"{c}6"].value for c in ("C", "D", "E", "O", "P", "Q", "S", "T", "U", "AF")] == [
        "가상토픽 하나",
        1,
        "가상 서브토픽 가",
        "가상 배출권 단가 상승으로 구매 비용이 늘어 비용 증가",
        "리스크",
        "리스크-규제 및 법률",
        "가상 배출권 규제 강화",
        "가상 조달 계획 조정 압력 증가",
        "비용: 가상 배출권 구매 비용 증가",
        "1. 가상 규정 나의 요약\n2. 가상 사건 나의 요약",
    ]
    assert [fin[f"{c}7"].value for c in ("D", "P", "Q", "AF")] == [2, "기회", None, None]


def test_summary_takes_three_at_most() -> None:
    context = {
        "regulations": [{"summary": f"규 {n}"} for n in range(1, 3)] + [{"summary": None}],
        "controversies": [{"summary": "컨 1"}, {"summary": "컨 2"}],
    }
    assert final_xlsx.summaries(context) == "1. 규 1\n2. 규 2\n3. 컨 1"
    assert final_xlsx.summaries({"regulations": [], "controversies": []}) is None


def test_raw_json_round_trips_and_splits() -> None:
    result = example()
    sheets, _ = book_of(result)
    assert json.loads(raw_text(sheets["RAW_JSON"])) == result
    big = copy.deepcopy(result)
    big["part2"]["topics"][0]["subtopics"][0]["impact"]["parsed"]["note"] = "가" * 70_000
    sheets, _ = book_of(big)
    raw = sheets["RAW_JSON"]
    assert raw.max_row == 3  # A1 하나로 끝내지 않는다(IR0 의 A1 잘림)
    assert len(str(raw["A1"].value)) == 32_767
    assert json.loads(raw_text(raw)) == big


def test_long_cell_is_cut_with_a_mark() -> None:
    result = example()
    row = result["part2"]["topics"][0]["subtopics"][0]["impact"]["rows"][0]
    row["impactDefinition"] = "가" * 40_000
    sheets, cuts = book_of(result)
    value = str(sheets[SHEETS[1]]["Q6"].value)
    assert len(value) == 32_767
    assert value.endswith("…(잘림: 원문 40000자)")
    assert value.startswith("가" * 100)
    assert cuts == [{"sheet": SHEETS[1], "cell": "Q6", "length": 40_000, "topic": "가상토픽 하나"}]


def test_fit_cell() -> None:
    assert xlsx.fit_cell("가" * 32_767) == ("가" * 32_767, None)
    cut, length = xlsx.fit_cell("가" * 32_768)
    assert length == 32_768 and len(cut) == 32_767 and cut.endswith("…(잘림: 원문 32768자)")


def test_part2_not_run_gives_headers_only() -> None:
    result = example()
    result["part2"] = {"status": "not_run", "message": "가상"}
    sheets, _ = book_of(result)
    assert sheets[SHEETS[0]].max_row == 4
    assert sheets[SHEETS[1]].max_row == 5 and sheets[SHEETS[2]].max_row == 5


def test_fin_items_come_from_financial_rows_even_without_pathway() -> None:
    """1-1 의 [재무] 항목은 재무 rows 에서(감독 처분 ⑤) — Pathway 가 실패·안 돌아도 남는다."""
    for pathway in (
        {"status": "failed", "raw": None, "parseError": None, "failure": {"kind": "timeout", "message": "timeout"}},
        {"status": "not_run", "message": "가상"},
    ):
        result = example()
        result["part2"]["topics"][0]["subtopics"][0]["pathway"] = pathway
        sheets, _ = book_of(result)
        short = sheets[SHEETS[0]]
        assert short["F5"].value == (
            "1) [환경·사회] 제목: 가상 규정 가\n요약: 가상 규정 가의 요약\n출처: https://example.com/reg/가\n"
            "2) [재무] 제목: 가상 규정 나\n요약: 가상 규정 나의 요약\n출처: https://example.com/reg/나"
        )
        assert sheets[SHEETS[2]].max_row == 5  # 2-2 는 Pathway row 만 — 행 0


def test_a_cell_over_only_in_utf16_units_is_cut() -> None:
    """BMP 밖 글자로 UTF-16 폭만 32,767 을 넘는 칸(코드포인트는 안) — 잘리고 cuts 의 length 는 UTF-16 단위
    (MARC-ISSUE-425, 밴드 IRS1 ①)."""
    result = example()
    row = result["part2"]["topics"][0]["subtopics"][0]["impact"]["rows"][0]
    row["impactDefinition"] = "\U0001f600" * 20_000
    sheets, cuts = book_of(result)
    value = str(sheets[SHEETS[1]]["Q6"].value)
    assert len(value.encode("utf-16-le")) // 2 <= 32_767
    assert value.endswith("…(잘림: 원문 40000자)")
    assert cuts == [{"sheet": SHEETS[1], "cell": "Q6", "length": 40_000, "topic": "가상토픽 하나"}]
    assert json.loads(raw_text(sheets["RAW_JSON"])) == result
