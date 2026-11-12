"""outputs/xlsx.build: 결과를 엑셀로 짓고 openpyxl 로 다시 읽으면 시트 이름·머리글·칸 값이 결과와 같은가(발주서 §3 S10).

칸 값은 결과 꼴에서 손으로 기대값을 적어 견준다(머리글은 모듈 상수가 아니라 글자로 — 상수를 고쳐도 빨갛게).
제어 문자·`=` 시작 글자·32,767자 경계(★e — 정확히 32,767자는 한 칸, 32,768자는 두 칸)도 본다.
바이트는 실행마다 달라 견주지 않는다.
"""

import copy
import io
import json
from pathlib import Path
from typing import Any, cast

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from esgapi.dataverify.contracts import shapes
from esgapi.dataverify.outputs import xlsx

EXAMPLE = Path(__file__).resolve().parents[1] / "data" / "examples" / "result-sample.json"
LIMIT = 32_767


def example() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLE.read_text(encoding="utf-8")))


def read(result: dict[str, Any]) -> dict[str, list[list[Any]]]:
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)
    book = load_workbook(io.BytesIO(xlsx.build(result)))
    sheets: dict[str, list[list[Any]]] = {}
    for sheet in book.worksheets:
        assert isinstance(sheet, Worksheet)
        sheets[sheet.title] = [["" if v is None else v for v in row] for row in sheet.iter_rows(values_only=True)]
    return sheets


def test_the_sheets_and_headers() -> None:
    sheets = read(example())
    assert list(sheets) == ["요약", "계산 계획", "검증 결과", "검토 글", "리스크", "출처", "설정"]
    assert sheets["요약"][0] == ["이름", "값"]
    assert sheets["계산 계획"][0] == ["번호", "산식"]
    assert sheets["검증 결과"][0] == [
        "순번",
        "도구",
        "규칙",
        "항목",
        "연도",
        "판정",
        "차이(diff)",
        "허용 오차",
        "메모(note)",
        "설명(explanation)",
    ]
    assert sheets["검토 글"][0] == ["계산 검토 리포트"]
    assert sheets["리스크"][0] == [
        "영역(환경/사회/지배구조)",
        "지표(소분류)",
        "관찰 내용 및 스토리",
        "잠재 리스크(데이터 품질·정보·해석)",
        "해석·가설",
    ]
    assert sheets["출처"][0] == ["제목", "URL"]
    assert sheets["설정"][0] == ["이름", "값"]


def test_the_summary_and_settings_come_from_the_result() -> None:
    result = example()
    sheets = read(result)
    summary = dict((row[0], row[1]) for row in sheets["요약"][1:])
    assert summary == {
        "기업명": "가상건설",
        "SASB 산업분류": "Engineering & Construction Services",
        "주요 중대토픽": "기후변화 대응\n안전보건",
        "보고연도": "2025",
        "대상 테마": "환경",
        "항목 수": 12,
        "핵심 항목 수": 4,
        "연도": "2022, 2023, 2024",
        "단계 · 계산 계획": "마침",
        "단계 · 계산 검토": "마침(최대 횟수에 닿음 — 남은 도구 호출을 버림)",
        "단계 · 리스크 진단": "마침",
        "경고": "",
    }
    settings = dict((row[0], row[1]) for row in sheets["설정"][1:])
    assert settings == {
        "모델": "gpt-4.1",
        "판정 허용 오차": "0.0",
        "temperature": "0.1",
        "최대 횟수 · 계산 계획": 12,
        "최대 횟수 · 계산 검토": 6,
        "최대 횟수 · 리스크 진단": 12,
        "프롬프트 id · 계산 계획": "dataverify/plan@1",
        "프롬프트 id · 계산 검토": "dataverify/review@1",
        "프롬프트 id · 리스크 진단": "dataverify/insight@1",
    }
    assert sheets["계산 계획"][1:] == [[n, f] for n, f in enumerate(result["plan"]["formulas"], start=1)]
    assert sheets["검토 글"][1:] == [[result["review"]["report"]]]


def test_the_verify_sheet_has_a_row_per_check_and_per_year() -> None:
    result = example()
    rows = read(result)["검증 결과"][1:]
    expected_count = sum(len(c["years"]) if c["kind"] == "check" else 1 for c in result["review"]["checks"])
    assert len(rows) == expected_count
    by_seq: dict[int, list[list[Any]]] = {}
    for row in rows:
        by_seq.setdefault(row[0], []).append(row)
    assert by_seq[1] == [
        [
            1,
            "search_items",
            "검색",
            "대분류 = 온실가스 배출량",
            "",
            "",
            "",
            "",
            "",
            "맞은 항목 6 · 돌려준 항목 6 (limit 200, offset 0)",
        ]
    ]
    assert by_seq[2] == [
        [
            2,
            "value_of_by_name",
            "값 조회",
            "온실가스 배출량 | 직접 배출량 | Scope 1 | tCO2eq",
            "2024",
            "",
            "",
            "",
            "",
            "값 = 1300.0",
        ]
    ]
    assert by_seq[3][0][-1] == "값 없음(N/A)"
    four = by_seq[4]
    assert [r[4] for r in four] == ["2023", "2024"]
    assert [r[5] for r in four] == ["OK", "FAIL"]
    assert [r[6] for r in four] == ["0.0", "5.0"]
    assert {r[7] for r in four} == {"0.0"}
    assert four[0][3] == (
        "total: 온실가스 배출량 | 총 배출량 | Scope 1+2 | tCO2eq\n"
        "a: 온실가스 배출량 | 직접 배출량 | Scope 1 | tCO2eq\n"
        "b: 온실가스 배출량 | 간접 배출량 | Scope 2 | tCO2eq"
    )
    assert four[1][9] == result["review"]["checks"][3]["years"][1]["explanation"]
    assert (by_seq[5][0][2], by_seq[5][0][5]) == ("오류", "오류")
    assert json.loads(by_seq[5][0][3]) == result["review"]["checks"][4]["args"]
    assert by_seq[5][0][9] == "runtime error in sum_check_by_name: name 'e' is not defined"
    assert by_seq[6][0][2:10] == [
        "부분합",
        'addends = [1200.0, "N/A"]\ntarget = 1500.0',
        "",
        "계산 불가",
        "",
        "0.0",
        "non-numeric",
        "Input values are not numeric.",
    ]
    assert by_seq[7][0][5:9] == ["계산 불가", "", "0.0", "division by zero"]
    assert by_seq[8][0][2] == "오류"


def test_the_risk_sheet_and_sources() -> None:
    result = example()
    result["insight"]["sources"].append({"title": None, "url": "https://example.org/a/?utm_source=openai"})
    sheets = read(result)
    keys = ("area", "indicator", "observation", "risk", "interpretation")
    assert sheets["리스크"][1:] == [[row[k] for k in keys] for row in result["insight"]["rows"]]
    assert sheets["출처"][1:] == [["가상 기준서", "https://example.org/standard"], ["", "https://example.org/a"]]


def test_an_unparsed_risk_table_is_one_raw_cell() -> None:
    result = example()
    result["insight"] = {**result["insight"], "rows": [], "rowsParsed": "unparsed"}
    sheets = read(result)
    assert sheets["리스크"] == [["리스크 진단 원문(표를 읽지 못함)"], [result["insight"]["report"]]]


def test_stages_that_did_not_run_or_failed() -> None:
    result = example()
    result["plan"] = {
        "status": "failed",
        "partial": None,
        "formulas": [],
        "raw": "가상 답",
        "failure": {"kind": "unparsable", "budgetSource": None, "message": "python list 가 아님"},
    }
    result["review"] = {"status": "not_run", "partial": None, "report": None, "checks": [], "failure": None}
    result["insight"] = {
        "status": "not_run",
        "partial": None,
        "report": None,
        "rows": [],
        "rowsParsed": "none",
        "sources": [],
        "failure": None,
    }
    result["warnings"] = [{"code": "no_target_theme", "message": "가상 경고"}]
    sheets = read(result)
    summary = dict((row[0], row[1]) for row in sheets["요약"][1:])
    assert summary["단계 · 계산 계획"] == "실패 — unparsable: python list 가 아님"
    assert summary["단계 · 계산 검토"] == "돌리지 않음"
    assert summary["경고"] == "no_target_theme: 가상 경고"
    assert sheets["계산 계획"] == [["번호", "산식"]]
    assert sheets["검증 결과"][1:] == []
    assert sheets["검토 글"][1:] == [[""]]
    assert sheets["리스크"][1:] == [[""]]


def test_control_characters_are_dropped_and_formulas_stay_text() -> None:
    result = example()
    result["review"]["report"] = "=SUM(A1:A2)\x00\x07 가상"
    result["insight"]["rows"][0]["risk"] = "=1+1"
    sheets = read(result)
    assert sheets["검토 글"][1] == ["=SUM(A1:A2) 가상"]
    assert sheets["리스크"][1][3] == "=1+1"
    book = load_workbook(io.BytesIO(xlsx.build(result)))
    assert book["검토 글"]["A2"].data_type == "s"


def test_long_text_is_split_into_continuation_rows_at_32767() -> None:
    """★e — 정확히 32,767자는 한 칸, 32,768자는 두 칸(둘째는 같은 열의 아랫줄)."""
    result = example()
    result["review"]["report"] = "가" * LIMIT
    assert read(result)["검토 글"][1:] == [["가" * LIMIT]]
    result["review"]["report"] = "가" * LIMIT + "나"
    assert read(result)["검토 글"][1:] == [["가" * LIMIT], ["나"]]
    long_result = copy.deepcopy(example())
    long_result["insight"]["rows"][0]["observation"] = "다" * (LIMIT * 2 + 5)
    risk = read(long_result)["리스크"]
    first = long_result["insight"]["rows"][0]
    assert risk[1] == [first["area"], first["indicator"], "다" * LIMIT, first["risk"], first["interpretation"]]
    assert risk[2] == ["", "", "다" * LIMIT, "", ""]
    assert risk[3] == ["", "", "다" * 5, "", ""]
    assert risk[4][0] == long_result["insight"]["rows"][1]["area"]
    check = long_result["review"]["checks"][3]
    check["years"][0]["explanation"] = "라" * (LIMIT + 1)
    rows = read(long_result)["검증 결과"]
    at = next(i for i, row in enumerate(rows) if row[0] == 4)
    assert rows[at][9] == "라" * LIMIT
    assert rows[at + 1] == ["", "", "", "", "", "", "", "", "", "라"]


def test_the_limit_counts_utf16_units_so_a_character_outside_the_bmp_counts_twice() -> None:
    """가지 리뷰 3 — Excel 은 UTF-16 단위로 센다. BMP 밖 글자(이모지)는 둘이고, 칸 사이에서 갈라지지 않는다."""
    emoji = "\U0001f600"
    assert xlsx.utf16_length(emoji) == 2
    exact = emoji * (LIMIT // 2) + "가"  # 2 × 16,383 + 1 = 32,767
    assert xlsx.split_text(exact) == [exact]
    over = emoji * (LIMIT // 2 + 1)  # 32,768 단위
    parts = xlsx.split_text(over)
    assert parts == [emoji * (LIMIT // 2), emoji]
    assert all(xlsx.utf16_length(part) <= LIMIT for part in parts)
    straddle = "가" * (LIMIT - 1) + emoji  # 마지막 글자가 한도에 걸친다 → 통째로 다음 칸
    assert xlsx.split_text(straddle) == ["가" * (LIMIT - 1), emoji]
    result = example()
    result["review"]["report"] = over
    assert read(result)["검토 글"][1:] == [[emoji * (LIMIT // 2)], [emoji]]


def test_any_result_that_fits_the_shape_builds() -> None:
    """모델 인자를 비추는 칸(byName·item·filter·limit·offset·args)은 아무 JSON 값이나 받는다 — 그래도 엑셀이 지어진다
    (⑤ 검증 중요 1)."""
    result = example()
    checks = result["review"]["checks"]
    checks[3]["items"]["byName"] = {"total": 5, "a": None, "b": [1, [2], {"x": True}, "가"]}
    checks[6]["items"]["byName"] = {"numerator": True, "denominator": 2.5, "expected": {"k": 1}}
    checks[0]["limit"] = True
    checks[0]["offset"] = None
    checks[1]["item"] = [5, True, None, ["가"]]
    checks[7]["args"] = [1, 2]
    rows = read(result)["검증 결과"][1:]
    by_seq = {row[0]: row for row in rows}
    assert by_seq[4][3] == 'total: 5\na: \nb: 1 | [2] | {"x": true} | 가'
    assert by_seq[7][3] == 'numerator: true\ndenominator: 2.5\nexpected: {"k": 1}'
    assert by_seq[1][9] == "맞은 항목 6 · 돌려준 항목 6 (limit true, offset )"
    assert by_seq[2][3] == '5 | true |  | ["가"]'
    assert by_seq[8][3] == "[1, 2]"
    result["review"]["checks"] = [
        {
            "seq": 1,
            "tool": "sum_n_check_by_names",
            "kind": "check",
            "rule": "sum_n",
            "items": {"byName": {"addends": 7, "target": [1, 2, 3, 4]}, "raw": None},
            "tolerance": None,
            "years": [],
        },
        {
            "seq": 2,
            "tool": "sum_n_check_by_names",
            "kind": "check",
            "rule": "sum_n",
            "items": {"byName": {"addends": [3, ["가", "나", "다", "라"]], "target": "x"}, "raw": None},
            "tolerance": "1.1",
            "years": [],
        },
    ]
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)
    assert xlsx.build(result)  # years 가 비어 줄은 없지만 지어진다


def test_a_failed_stage_line_carries_the_core_kind() -> None:
    """@2: 실패 줄은 「실패 — <kind>: <message>」 — kind 는 core 의 갈래 이름(call_failed 없음). 끝난 단계 줄은
    그대로다."""
    result = example()
    before = dict((row[0], row[1]) for row in read(example())["요약"][1:])
    result["insight"] = {
        "status": "failed",
        "partial": None,
        "report": None,
        "rows": [],
        "rowsParsed": "none",
        "sources": [],
        "failure": {"kind": "budget_exceeded", "budgetSource": "loop", "message": "budget_exceeded (loop)"},
        "partialText": None,
    }
    summary = dict((row[0], row[1]) for row in read(result)["요약"][1:])
    assert summary["단계 · 리스크 진단"] == "실패 — budget_exceeded: budget_exceeded (loop)"
    assert summary["단계 · 계산 계획"] == before["단계 · 계산 계획"]
    assert summary["단계 · 계산 검토"] == before["단계 · 계산 검토"]
