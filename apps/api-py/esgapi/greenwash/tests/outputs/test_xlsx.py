"""엑셀 greenwash-report.xlsx: 시트 넷, 문장 시트의 줄 수 = items 수, 칸 값이 결과의 칸과 같다(바이트가 아니라 읽은 값).

기대값은 xlsx.py 의 행 함수가 아니라 결과의 칸에서 바로 짓는다. 빈 글자 칸은 xlsx 에 값 없는 칸으로 남아
None 으로 읽힌다.
"""

import copy
import io
import json
from typing import Any

import pytest
from openpyxl import load_workbook

from esgapi.greenwash.engines.e0.gw1 import frequency_extras
from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.tests.flows import support as s


def read(content: bytes) -> dict[str, list[tuple[Any, ...]]]:
    book = load_workbook(io.BytesIO(content), read_only=True)
    return {name: [tuple(row) for row in book[name].iter_rows(values_only=True)] for name in book.sheetnames}


def text(value: str) -> str | None:
    return value or None


def expected_sentence_row(item: dict[str, Any]) -> tuple[Any, ...]:
    return (
        text(", ".join(item["parts"])),
        item["page"],
        item["level"],
        item["sentence"],
        text(", ".join(item["riskTags"])),
        text("\n".join(item["confirmedInEvidence"])),
        text("\n".join(item["missingFields"])),
        text("\n".join(item["reasonBullets"])),
        item["fixParagraph"],
        text(", ".join(str(p) for p in item["evidencePages"])),
        None,  # 예시 문장은 E0 에서 빈 칸
    )


@pytest.mark.parametrize("pages", [("1", "2", "3~4"), ("1~2", "2", "2~4")])
def test_the_workbook_holds_the_result(pages: tuple[str, str, str]) -> None:
    flow_run = s.run(s.inputs(ceo=pages[0], company=pages[1], climate=pages[2]), s.adapters())
    result = s.result_of(flow_run)
    (book,) = flow_run.output.files
    assert (book.name, book.media_type) == ("greenwash-report.xlsx", xlsx.MEDIA_TYPE)
    sheets = read(book.content)
    assert tuple(sheets) == xlsx.SHEETS

    assert sheets["문장"][0] == xlsx.SENTENCE_HEADER
    assert len(sheets["문장"]) - 1 == len(result["items"]) > 0
    assert sheets["문장"][1:] == [expected_sentence_row(item) for item in result["items"]]

    counts = result["counts"]
    summary = sheets["요약"][1:]
    want = [(f"등급 {level}", counts["byLevel"][level]) for level in ("High", "Mid", "Low")]
    for part in result["parts"]:
        want += [
            (f"{part['name']} · {level}", counts["byPart"][part["name"]][level]) for level in ("High", "Mid", "Low")
        ]
    want += [
        ("전체 문장 수", counts["total"]),
        ("점검 페이지 수", len(result["pages"])),
        ("인식 실패 페이지 수", len(result["candidateStats"]["failedPages"])),
    ]
    assert summary == want
    assert sheets["요약"][0] == ("이름", "수")

    assert sheets["단어 빈도"][0] == ("낱말", "수", "추가")
    assert sheets["단어 빈도"][1:] == [(w["term"], w["count"], None) for w in result["wordCounts"]["total"]]

    assert dict(sheets["설정"][1:]) == {
        "프롬프트 판": result["promptVersion"],
        "대화 모델(노트북 설정)": result["models"]["chat"],
        "임베딩 모델(노트북 설정)": result["models"]["embedding"],
        "매개변수": json.dumps(result["config"]["chat"], ensure_ascii=False),
        "조각 설정": json.dumps(result["config"]["chunking"], ensure_ascii=False),
        "추가 단어": None,  # 추가 단어가 없으면 빈 칸
    }


def test_control_characters_are_dropped_and_formulas_stay_text() -> None:
    result = copy.deepcopy(s.result_of(s.run(s.inputs(), s.adapters())))
    item = result["items"][0]
    item["sentence"] = "=SUM(A1:A2) 로 시작하는 문장"
    item["fixParagraph"] = "  앞\x0b가운데\x1f뒤\n줄바꿈과 앞뒤 공백은 남는다 "
    book = load_workbook(io.BytesIO(xlsx.build(result, added_terms=frequency_extras(result["extraTerms"]))))
    row = next(iter(book["문장"].iter_rows(min_row=2, max_row=2)))
    assert (row[3].value, row[3].data_type) == ("=SUM(A1:A2) 로 시작하는 문장", "s")
    assert row[8].value == "  앞가운데뒤\n줄바꿈과 앞뒤 공백은 남는다 "


def test_a_dry_run_result_has_no_workbook() -> None:
    result = s.result_of(s.run(s.inputs(dry_run=True), s.adapters(tokens=s.char_counter())))
    with pytest.raises(ValueError, match="dry-run"):
        xlsx.build(result, added_terms=frequency_extras(result["extraTerms"]))
