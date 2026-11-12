"""S3Q1 ③ 배출계수 출처 글(service/utils/scope3_sources.py — 발주서 Q9·Q10). 순수 층.

책은 메모리에서 짓는다(지어낸 시트 머리·줄 비고 — 실제 책의 글은 단언에 쓰지 않는다). 패키지 책은 셈만 본다
(머리 출처가 있는 시트 수·C3 비고 수 — 글은 보고 ★E 표에만).
"""

import copy
import io
from typing import Any

from openpyxl import Workbook

from esgapi.inventory.service.utils import scope3_sources as sources
from esgapi.inventory.service.utils.scope3_sources import SourceTexts, head_source, read_sources, source_text


def book_bytes(sheets: dict[str, list[list[object]]]) -> bytes:
    book = Workbook()
    book.remove(book.active)  # type: ignore[arg-type]
    for title, rows in sheets.items():
        sheet = book.create_sheet(title)
        for values in rows:
            sheet.append(values)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


C3_ROWS: list[list[object]] = [
    ["가상 C3 표  |  가상 쓰임  |  출처: 가상 기관 셋"],
    ["산정식: 가상"],
    ["No.", "활동유형\n(에너지원)", "기준단위", "EF\n(kgCO2eq/단위) ★", "출처/비고"],
    [1, "가상전기", "kWh", 0.1, "가상 지침 갑 0.5-0.4"],
    [2, "가상가스", "Nm³", 0.2, "가상 표지"],
    [3, "가상가스", "Nm³", 0.3, "가상 둘째 줄(첫 줄이 이긴다)"],
    [4, "가상비고없음", "kg", 0.4, None],
]

BOOK = book_bytes(
    {
        "목록": [[None, "가상 안내"]],
        "에너지": [["가상 에너지 표  |  가상 쓰임  |  출처: 가상 기관 하나 (가상 2099)"], ["구분"]],
        "에너지_C3": C3_ROWS,
        "운송": [["가상 운송 표 | 가상 쓰임 | 출처:   가상 기관 둘  "]],
        "폐기물_C5": [["가상 C5 표  |  가상 매핑"]],
        "폐기물_C12": [["가상 C12 표  |  가상 법 별표 가상 개정"]],
        "구매_USEPA": [["가상 구매 표 | 가상 원본 | 가상 매핑"]],
        "빈머리": [[None]],
    }
)


def test_the_head_text_is_after_the_source_word_or_the_second_part_for_the_exception() -> None:
    assert head_source("에너지", "가 | 나 | 출처: 다 (라)") == "다 (라)"
    assert head_source("운송", "가|출처:  다  ") == "다"
    assert head_source("폐기물_C12", "가 | 나 다") == "나 다"  # 예외 표 — 「출처:」 없이 둘째 토막
    assert head_source("폐기물_C12", "가") is None
    assert head_source("폐기물_C5", "가 | 나") == "환경부 환경성적표지"  # 마크스폰이 준 글(MARC-ENT-634 답)
    assert head_source("폐기물_C5", None) == "환경부 환경성적표지"
    assert head_source("구매_USEPA", "가 | 나") is None  # 「출처:」 없음 → 지금 꼴
    assert head_source("에너지", "가 | 출처:") is None  # 빈 글
    assert head_source("에너지", None) is None
    assert head_source("에너지", 3) is None


def test_a_book_reads_into_heads_and_c3_notes() -> None:
    texts = read_sources(BOOK)
    assert dict(texts.heads) == {
        "에너지": "가상 기관 하나 (가상 2099)",
        "에너지_C3": "가상 기관 셋",
        "운송": "가상 기관 둘",
        "폐기물_C5": "환경부 환경성적표지",
        "폐기물_C12": "가상 법 별표 가상 개정",
    }
    assert dict(texts.c3_notes) == {"가상전기": "가상 지침 갑 0.5-0.4", "가상가스": "가상 표지"}  # 같은 이름은 첫 줄


def test_c3_rows_take_their_note_first_then_the_head() -> None:
    texts = read_sources(BOOK)
    assert source_text(texts, "에너지_C3", "가상전기") == "가상 지침 갑 0.5-0.4"
    assert source_text(texts, "에너지_C3", " 가상가스 ") == "가상 표지"
    assert source_text(texts, "에너지_C3", "가상비고없음") == "가상 기관 셋"
    assert source_text(texts, "에너지_C3", None) == "가상 기관 셋"
    assert source_text(texts, "에너지", "가상전기") == "가상 기관 하나 (가상 2099)"  # 다른 시트는 비고를 보지 않는다
    assert source_text(texts, "폐기물_C5", "가상") == "환경부 환경성적표지"
    assert source_text(texts, "구매_USEPA", "가상") is None
    assert source_text(texts, "없는시트", None) is None


def test_a_broken_book_is_an_empty_table() -> None:
    assert read_sources(b"not an xlsx") == SourceTexts()


def test_the_packaged_book_has_eight_heads_and_twelve_c3_notes() -> None:
    """패키지 책(책 v1.1, 밴드 S3V1): 「출처:」 다섯 + 에너지_C3 + 폐기물_C12 예외 + 폐기물_C5 준 글 = 여덟,
    C3 활동유형 열둘(모두 다른 이름 — 엔진 iloc[0] 과 같은 줄. Nm³ 도시가스 줄은 MARC-ENT-649 답 전까지 남김).
    머리 출처가 없는 둘은 열쇠가 없다."""
    texts = sources.packaged_sources()
    assert sorted(texts.heads) == sorted(
        ["에너지", "에너지_C3", "운송", "출장_통근", "폐기물_C5", "폐기물_C12", "운송_Spend", "출장_Spend"]
    )
    assert not {"구매_USEPA", "전력_국가별"} & set(texts.heads)
    assert len(texts.c3_notes) == 12


TEXTS = read_sources(BOOK)


def body() -> dict[str, Any]:
    def factor(sheet: str, title: str | None) -> dict[str, Any]:
        return {"sheet": sheet, "title": title, "value": "0.1", "unit": "kgCO2eq/kWh", "column": None, "code": None}

    return {
        "schemaVersion": "scope3.colab.result@1",
        "status": "done",
        "sheets": [
            {
                "sheet": "가상_C3",
                "category": "Category3",
                "status": "processed",
                "rows": [
                    {"rowId": "가상_C3!5", "kind": "fuel_energy", "factor": factor("에너지_C3", "가상전기")},
                    {"rowId": "가상_C3!6", "kind": "fuel_energy", "factor": None},
                    {"rowId": "가상_C3!7", "kind": "waste", "factor": factor("폐기물_C5", None)},
                    {"rowId": "가상_C3!8", "kind": "product_eol", "factor": factor("폐기물_C12", None)},
                    {"rowId": "가상_C1!6", "kind": "purchase", "factor": {"sheet": "에너지", "source": "usepa"}},
                    {"rowId": "가상_C3!9", "kind": "fuel_energy", "factor": factor("전력_국가별", None)},
                ],
            },
            {"sheet": "가상_빈", "status": "not_target"},
        ],
        "factorSheets": [{"sheet": "에너지"}],
    }


def test_with_sources_adds_source_text_to_activity_and_energy_rows_only() -> None:
    given = body()
    kept = copy.deepcopy(given)
    out: Any = sources.with_sources(given, TEXTS)
    assert given == kept  # 받은 본문은 그대로
    rows = out["sheets"][0]["rows"]
    assert rows[0]["factor"]["sourceText"] == "가상 지침 갑 0.5-0.4"
    assert rows[1]["factor"] is None
    assert rows[2]["factor"]["sourceText"] == "환경부 환경성적표지"  # 마크스폰이 준 글(MARC-ENT-634 답)
    assert rows[3]["factor"]["sourceText"] == "가상 법 별표 가상 개정"
    assert "sourceText" not in rows[4]["factor"]  # 구매 줄은 이 밴드 밖
    assert "sourceText" not in rows[5]["factor"]  # 머리 출처 없는 시트 — 키 없음(웹 지금 꼴)
    assert out["sheets"][1] == kept["sheets"][1]
    assert out["factorSheets"] == kept["factorSheets"]  # 칸을 더하지 않는다(줄에 싣는 쪽 하나)
    without = copy.deepcopy(out)
    for row in without["sheets"][0]["rows"]:
        if isinstance(row["factor"], dict):
            row["factor"].pop("sourceText", None)
    assert without == kept  # 더한 칸 밖은 글자째 같다


def test_with_sources_passes_odd_bodies_through() -> None:
    assert sources.with_sources({"status": "rejected"}, TEXTS) == {"status": "rejected"}
    odd = {"sheets": ["가상", {"rows": "가상"}, {"rows": ["가상", {"factor": "가상"}]}]}
    assert sources.with_sources(odd, TEXTS) == odd
