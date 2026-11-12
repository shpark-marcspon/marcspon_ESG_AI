"""최종 엑셀(materiality-final-report.xlsx) — 코랩 셀 65 의 Code Interpreter 지시(R/3368-3572)를 서버 openpyxl 로
(MARC-ENT-425 ③, 밴드 IR2a).

결과 꼴 @2(JSON 판)에서만 짓는다. 시트 넷(셀 65 「반드시 4개」):
- `1-1. Short-list 선정`: B1 제목, 4행 머리 B No·C Topic·F 규제 및 정책·G 컨트로버시 이슈. 한 행 = 2부 토픽(입력 차례).
  F·G = 환경·사회(SOC — 영향 rows 의 context) + 재무(FIN — 재무 rows 의 context; Pathway 가 실패·안 돌아도 남는다 — 감독
  처분 ⑤)를 모은다.
  출처(url)가 같을 때만 하나로 합치고(양쪽이면 라벨 [환경·사회·재무]), 항목마다 `n) [라벨] 제목: …\\n요약: …\\n출처: …`.
- `2-1. 환경사회 영향 식별`: B1 제목, 5행 머리 C Topic·D No·E Subtopic·Q 영향 정의·R 영향 유형 (긍정/부정)·
  U 컨텍스트 요약 내용. 한 행 = 영향 row. U 는 context 의 summary 를 규제 → 컨트로버시 차례로 셋까지 `1. …` 줄로
  (새 문장 0).
- `2-2. 재무 영향 식별`: B1 제목, 5행 머리 C·D·E·O 영향 정의·P 리스크/기회·Q 리스크 종류·S ① Impact Driver·T ② 비즈니스
  영향·U ③ 재무 영향·AF 컨텍스트 요약 내용. 한 행 = Pathway row(Pathway 가 없는 서브토픽은 행 0).
- `RAW_JSON`: A1 = json.dumps(결과, ensure_ascii=False), 32,767자를 넘으면 A2, A3 …(코랩은 A1 하나 — IR0 의 A1 잘림을
  되풀이하지 않는다).
No 는 시트 안 전체 순번, null 은 빈 칸, 출처 키는 url(셀 65 지시의 source 대신 셀 50 꼴). 글자 칸은 1부 엑셀
(outputs/xlsx.py)의 cell_text·put_cell 을 쓰고, 32,767자를 넘는 칸은 fit_cell 로 앞부분 + 「…(잘림: 원문 n자)」를 담는다
(openpyxl 은 말없이 자른다) — 자른 칸은 돌려주는 cuts 에 적어 흐름이 경고 xlsx_cell_truncated 로 단다.
코랩과 다른 자리: 셀 65 는 모델(Code Interpreter)이 지시를 읽고 파일을 짓는다 — 여기는 지시를 결정적으로 옮긴다. 컬럼
너비·색은 정하지 않는다(openpyxl 기본, 셀 65 「불필요한 색상·병합 금지」).
"""

import io
import json
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, Final, cast

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from .xlsx import MEDIA_TYPE, fit_cell, no_lone_surrogates, put_cell, raw_json_chunks

FILENAME: Final = "materiality-final-report.xlsx"
MEDIA: Final = MEDIA_TYPE
SHORTLIST: Final = "1-1. Short-list 선정"
SOC_SHEET: Final = "2-1. 환경사회 영향 식별"
FIN_SHEET: Final = "2-2. 재무 영향 식별"
RAW_JSON: Final = "RAW_JSON"
TITLES: Final[Mapping[str, str]] = {
    SHORTLIST: "1-1. Short-list 선정",
    SOC_SHEET: "2-1. 환경사회영향(Impact materiality) 식별",
    FIN_SHEET: "2-2. 재무 영향(Financial materiality) 식별",
}
"""시트 → B1 제목(셀 65 R/3481·R/3512·R/3534 의 글)."""
SHORTLIST_HEADER: Final = {"B": "No", "C": "Topic", "F": "규제 및 정책", "G": "컨트로버시 이슈"}
SOC_HEADER: Final = {
    "C": "Topic",
    "D": "No",
    "E": "Subtopic",
    "Q": "영향 정의",
    "R": "영향 유형 (긍정/부정)",
    "U": "컨텍스트 요약 내용",
}
FIN_HEADER: Final = {
    "C": "Topic",
    "D": "No",
    "E": "Subtopic",
    "O": "영향 정의",
    "P": "리스크/기회",
    "Q": "리스크 종류",
    "S": "① Impact Driver",
    "T": "② 비즈니스 영향",
    "U": "③ 재무 영향",
    "AF": "컨텍스트 요약 내용",
}
SOC_LABEL: Final = "[환경·사회]"
FIN_LABEL: Final = "[재무]"
BOTH_LABEL: Final = "[환경·사회·재무]"
SUMMARY_LIMIT: Final = 3
"""컨텍스트 요약 내용의 줄 수 위끝(셀 65 「요약의 내용 2~3개」)."""

Cut = dict[str, Any]
"""자른 칸 하나 {sheet, cell, length(원문 글자 수), topic}."""


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _subtopics(result: Mapping[str, Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
    part2 = result["part2"]
    if part2["status"] != "done":
        return
    for topic in part2["topics"]:
        for sub in topic["subtopics"]:
            yield topic["topic"], sub


def _rows(outcome: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return list(outcome["rows"]) if outcome["status"] == "done" else []


def _items(rows: Sequence[Mapping[str, Any]], side: str) -> list[Mapping[str, Any]]:
    return [item for row in rows for item in row["context"][side]]


def merged_items(
    soc: Sequence[Mapping[str, Any]], fin: Sequence[Mapping[str, Any]]
) -> list[tuple[str, Mapping[str, Any]]]:
    """SOC → FIN 차례로 모으되 url 이 같은(null·빈 글 아님 — 앞뒤 공백은 떼고 견줌) 항목은 처음 것 하나로(양쪽에서
    왔으면 라벨 [환경·사회·재무])."""
    out: list[list[Any]] = []
    by_url: dict[str, list[Any]] = {}
    for label, items in ((SOC_LABEL, soc), (FIN_LABEL, fin)):
        for item in items:
            given = item.get("url")
            url = given.strip() if isinstance(given, str) and given.strip() else None  # 빈 url 은 합치지 않는다
            if url is not None and url in by_url:
                seen = by_url[url]
                if seen[0] != label:
                    seen[0] = BOTH_LABEL
                continue
            entry = [label, item]
            out.append(entry)
            if url is not None:
                by_url[url] = entry
    return [(cast("str", label), cast("Mapping[str, Any]", item)) for label, item in out]


def listing(items: Sequence[tuple[str, Mapping[str, Any]]]) -> str | None:
    """`1) [라벨] 제목: …\\n요약: …\\n출처: …` 를 줄바꿈으로 잇는다. 항목이 없으면 null."""
    if not items:
        return None
    return "\n".join(
        f"{n}) {label} 제목: {_text(item.get('title'))}\n"
        f"요약: {_text(item.get('summary'))}\n출처: {_text(item.get('url'))}"
        for n, (label, item) in enumerate(items, 1)
    )


def summaries(context: Mapping[str, Any]) -> str | None:
    """컨텍스트 요약 내용: summary 를 규제 → 컨트로버시 차례로 셋까지 `1. …` 줄로(null summary 는 뺀다)."""
    found = [item.get("summary") for side in ("regulations", "controversies") for item in context[side]]
    lines = [s for s in found if s is not None][:SUMMARY_LIMIT]
    return "\n".join(f"{n}. {s}" for n, s in enumerate(lines, 1)) or None


def shortlist_rows(result: Mapping[str, Any]) -> list[tuple[int, str, str | None, str | None]]:
    """(No, Topic, F, G) — 2부 토픽 차례."""
    part2 = result["part2"]
    topics = cast("list[Mapping[str, Any]]", part2["topics"] if part2["status"] == "done" else [])
    out: list[tuple[int, str, str | None, str | None]] = []
    for no, topic in enumerate(topics, 1):
        soc_rows = [row for sub in topic["subtopics"] for row in _rows(sub["impact"])]
        fin_rows = [row for sub in topic["subtopics"] for row in _rows(sub["financial"])]  # 재무 rows(감독 ⑤)
        f = listing(merged_items(_items(soc_rows, "regulations"), _items(fin_rows, "regulations")))
        g = listing(merged_items(_items(soc_rows, "controversies"), _items(fin_rows, "controversies")))
        out.append((no, topic["topic"], f, g))
    return out


class _Sheet:
    """칸 쓰기 + 자른 칸 적기."""

    def __init__(self, sheet: Worksheet, cuts: list[Cut]) -> None:
        self.sheet = sheet
        self.cuts = cuts

    def put(self, ref: str, value: object, *, topic: str | None = None, bold: bool = False) -> None:
        if isinstance(value, str):
            value, cut = fit_cell(value)
            if cut is not None:
                self.cuts.append({"sheet": self.sheet.title, "cell": ref, "length": cut, "topic": topic})
        put_cell(self.sheet, ref, value, bold=bold)


def _header(sheet: _Sheet, title: str, row: int, header: Mapping[str, str]) -> None:
    sheet.put("B1", title, bold=True)
    for col, text in header.items():
        sheet.put(f"{col}{row}", text, bold=True)


def build_final(result: Mapping[str, Any]) -> tuple[bytes, list[Cut]]:
    """결과 꼴 @2(JSON 판) → 최종 엑셀 바이트와 자른 칸 목록."""
    book = Workbook()
    cuts: list[Cut] = []
    first = book.active
    assert first is not None  # noqa: S101 — 새 Workbook 은 시트 하나를 갖고 시작한다
    first.title = SHORTLIST
    short = _Sheet(first, cuts)
    _header(short, TITLES[SHORTLIST], 4, SHORTLIST_HEADER)
    for r, (no, topic, f, g) in enumerate(shortlist_rows(result), 5):
        short.put(f"B{r}", no)
        short.put(f"C{r}", topic, topic=topic)
        short.put(f"F{r}", f, topic=topic)
        short.put(f"G{r}", g, topic=topic)

    soc = _Sheet(book.create_sheet(SOC_SHEET), cuts)
    _header(soc, TITLES[SOC_SHEET], 5, SOC_HEADER)
    r = 6
    for topic, sub in _subtopics(result):
        for row in _rows(sub["impact"]):
            values = {
                "C": topic,
                "D": r - 5,
                "E": sub["name"],
                "Q": row["impactDefinition"],
                "R": row["impactType"],
                "U": summaries(row["context"]),
            }
            for col, value in values.items():
                soc.put(f"{col}{r}", value, topic=topic)
            r += 1

    fin = _Sheet(book.create_sheet(FIN_SHEET), cuts)
    _header(fin, TITLES[FIN_SHEET], 5, FIN_HEADER)
    r = 6
    for topic, sub in _subtopics(result):
        for row in _rows(sub["pathway"]):
            values = {
                "C": topic,
                "D": r - 5,
                "E": sub["name"],
                "O": row["impactDefinition"],
                "P": row["impactType"],
                "Q": row["riskType"],
                "S": row["impactDriver"],
                "T": row["businessImpact"],
                "U": row["financialImpact"],
                "AF": summaries(row["context"]),
            }
            for col, value in values.items():
                fin.put(f"{col}{r}", value, topic=topic)
            r += 1

    raw = book.create_sheet(RAW_JSON)
    for n, chunk in enumerate(raw_json_chunks(result), 1):
        cell = raw.cell(row=n, column=1)
        cell.value = no_lone_surrogates(chunk)
        cell.data_type = "s"  # 조각이 `=` 로 시작해도 글자 칸
    out = io.BytesIO()
    book.save(out)
    return out.getvalue(), cuts


def raw_json_text(sheet_values: Sequence[str]) -> dict[str, Any]:
    """RAW_JSON 의 A1, A2 … 를 이어 결과로 되읽는다(시험·다시 올린 엑셀 읽기의 재료).

    RAW_JSON 은 xlsx_cell_truncated 경고 전의 판이다 — 다시 올린 엑셀 읽기는 1차에 없고(MARC-ENT-439), shortlist 길을
    만드는 밴드가 되읽은 결과에 xlsx_cell_truncated 를 다시 단다."""
    return cast("dict[str, Any]", json.loads("".join(sheet_values)))
