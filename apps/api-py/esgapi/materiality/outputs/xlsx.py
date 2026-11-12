"""1부 엑셀(materiality-websearch.xlsx) — 코랩 셀 33 의 Code Interpreter 지시(R/1598-1682)를 서버 openpyxl 로
(MARC-ENT-425 ③).

결과 꼴에서만 짓는다: 코랩 payload 는 contracts/wire.websearch_payload(결과 → 코랩 묶음, 역함수)로 되짓고, 항목 추출은
셀 33 규칙 1~4, 표시 글은 셀 33 의 칸 차례로 `key: value` 를 「, 」로 잇는다(값은 str() — 코랩 지시. null 칸은 뺀다).
새 셈은 없다.
- Shortlist: A 열 빈칸, B1 「1-1. Short-list 선정」, 3행 머리 B·C·F·G(굵게·줄바꿈). 토픽은 두 묶음 키의 합집합을
  sorted()(한글 음절은 가나다), No 는 토픽 순번(그 토픽의 행마다 반복). 행 수 = max(규제, 컨트로버시) 또는 1.
  Notes 행은 self_check.notes 가 있는 쪽만(번호 없음). 모든 칸 wrap_text·top.
- RAW_JSON: A1 = json.dumps(payload, ensure_ascii=False). 한 칸이 담는 UTF-16 32,767 단위를 넘으면 A2, A3 … 로 이어
  담는다(BMP 밖 글자는 가르지 않고 다음 조각으로).
  짝 없는 서로게이트는 Shortlist 글자 칸과 RAW_JSON 조각 모두 「?」로 갈음한다(그 글만 원문과 다르다).
코랩과 다른 자리(발주서 처분 ⑪ 가): 묶음에 parsed 가 없는 토픽(파싱 실패·호출 실패)은 항목 0 에 「(파싱 실패)」 한 줄,
돌리지 않은 토픽은 payload 에서 빠진다. 파일 이름은 materiality-websearch.xlsx(코랩 materiality_websearch.xlsx).
글자 칸은 greenwash/outputs/xlsx.py 꼴로 두 가지만 다듬는다(판별 복사): xlsx 가 담지 못하는 제어 문자를 지우고, `=` 로
시작해도 수식이 아니라 글자 칸으로 둔다. openpyxl 의 xlsx 는 만든 시각이 들어가 바이트가 실행마다 다르다.
"""

import io
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet

from ..contracts.shapes import CONTROVERSY_ITEM_KEYS, REGULATION_ITEM_KEYS
from ..contracts.wire import controversy_elements, regulation_elements, websearch_payload

FILENAME: Final = "materiality-websearch.xlsx"
MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHORTLIST: Final = "Shortlist"
RAW_JSON: Final = "RAW_JSON"
TITLE: Final = "1-1. Short-list 선정"
HEADER: Final = {"B": "No", "C": "Topic", "F": "규제 및 정책", "G": "컨트로버시 이슈"}
PARSE_FAILED: Final = "(파싱 실패)"
NOTES: Final = "[Notes] "
CELL_LIMIT: Final = 32767
"""xlsx 한 칸이 담는 글자 수 — UTF-16 단위(Excel 이 세는 것. BMP 밖 글자는 둘)."""


def utf16_units(text: str) -> int:
    """글의 UTF-16 단위 수(MARC-ISSUE-425). 글자마다 ord 로 잰다 — encode 로 재면 짝 없는 서로게이트에서 죽는다
    (fit_cell·raw_json_chunks 는 no_lone_surrogates 앞에서 불린다). 짝 없는 서로게이트는 「?」 한 글자로 갈음되니 1."""
    return len(text) + sum(1 for ch in text if ord(ch) > 0xFFFF)


def utf16_cut(text: str, limit: int, start: int = 0) -> int:
    """text[start:] 에서 UTF-16 폭 합이 limit 을 넘지 않는 가장 긴 앞부분의 끝 자리(코드포인트). 그 자리에서 자르면 BMP
    밖 글자가 갈리지 않는다 — 경계에 걸친 글자는 다음 조각으로. dataverify/outputs/xlsx.py split_text 의 판별 복사."""
    used = 0
    end = start
    while end < len(text):  # text[start:] 를 베끼지 않는다 — 큰 RAW_JSON 은 조각마다 다시 걷는다
        width = 2 if ord(text[end]) > 0xFFFF else 1
        if used + width > limit:
            break
        used += width
        end += 1
    return end


def no_lone_surrogates(value: str) -> str:
    """짝 없는 서로게이트(예 \\ud800 — UTF-8 로 쓸 수 없다)를 「?」로 갈음한다. 그대로 두면 저장 때 파일 전체가 깨진다
    (감독 처분 사소 2). 한 글자를 한 글자로 바꾸니 RAW_JSON 조각의 길이는 그대로다."""
    return value.encode("utf-8", "replace").decode("utf-8")


def cell_text(value: str) -> str:
    """xlsx 가 담지 못하는 제어 문자를 지우고(greenwash/outputs/xlsx.py 의 판별 복사) 짝 없는 서로게이트를 갈음한다."""
    return no_lone_surrogates(ILLEGAL_CHARACTERS_RE.sub("", value))


TRUNCATED_MARK: Final = "…(잘림: 원문 {length}자)"
"""한 칸을 넘는 글의 끝 표시(밴드 IR2a 처분 ⑮ — openpyxl 은 32,767자에서 말없이 자른다)."""


def fit_cell(text: str) -> tuple[str, int | None]:
    """한 칸(UTF-16 32,767 단위 — Excel 이 세는 글자 수, BMP 밖 글자는 둘)에 담을 글과, 잘랐으면 원문의 UTF-16 단위
    수(안 잘랐으면 None). 넘으면 앞부분 + 「…(잘림: 원문 n자)」로 합이 32,767(BMP 밖 글자가 경계에 걸치면 32,766)
    단위다(MARC-ISSUE-425)."""
    length = utf16_units(text)
    if length <= CELL_LIMIT:
        return text, None
    mark = TRUNCATED_MARK.format(length=length)
    keep = utf16_cut(text, CELL_LIMIT - utf16_units(mark))
    return text[:keep] + mark, length


def _put(sheet: Worksheet, ref: str, value: object, *, bold: bool = False) -> None:
    cell = sheet[ref]
    cell.value = cell_text(value) if isinstance(value, str) else value
    if cell.data_type == "f":  # `=` 로 시작하는 글 — 수식이 아니라 글자로
        cell.data_type = "s"
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    if bold:
        cell.font = Font(bold=True)


def put_cell(sheet: Worksheet, ref: str, value: object, *, bold: bool = False) -> None:
    """_put 의 공개 이름(최종 엑셀 outputs/final_xlsx.py 가 같은 칸 다듬기를 쓴다 — 밴드 IR2a)."""
    _put(sheet, ref, value, bold=bold)


def display(item: Any, keys: Sequence[str]) -> str:
    """셀 33 R/1650-1655: dict 면 칸 차례로 있는 칸만(null 뺌) `key: value` 를 「, 」로, 글이면 그대로, 그 밖은
    str()."""
    if isinstance(item, dict):
        d = cast("dict[str, Any]", item)
        return ", ".join(f"{k}: {d[k]}" for k in keys if k in d and d[k] is not None)
    return str(item)


def _root(bundle: Any, key: str) -> tuple[Any, bool]:
    """셀 33 규칙 1: 묶음이 dict 이고 key(parsed·json) 가 있으면 그 값. 돌려주는 bool 은 「파싱 실패」(그 값이 None)."""
    if isinstance(bundle, dict) and key in bundle:
        value = cast("dict[str, Any]", bundle)[key]
        return value, value is None
    return cast("Any", bundle), False


def regulation_list(bundle: Any) -> tuple[list[Any], bool]:
    """셀 33 reg_items 규칙 1~4(R/1636-1641)와 「파싱 실패」(처분 ⑪)."""
    if bundle is None:
        return [], False
    root, failed = _root(bundle, "parsed")
    if failed:
        return [], True
    found, matched = regulation_elements(root)
    return ([element for _, element in found] if matched else [root]), False


def controversy_list(bundle: Any) -> tuple[list[Any], bool]:
    """셀 33 cont_items 규칙 1~4(R/1643-1648)와 「파싱 실패」(처분 ⑪)."""
    if bundle is None:
        return [], False
    root, failed = _root(bundle, "json")
    if failed:
        return [], True
    found, matched = controversy_elements(root)
    return (found if matched else [root]), False


def note(bundle: Any) -> str | None:
    """셀 33 R/1667-1668: 묶음의 self_check.notes, 또는 parsed.self_check.notes·json.self_check.notes."""
    if not isinstance(bundle, dict):
        return None
    d = cast("dict[str, Any]", bundle)
    for root in (d, d.get("parsed"), d.get("json")):
        if isinstance(root, dict):
            check = cast("dict[str, Any]", root).get("self_check")
            if isinstance(check, dict):
                value = cast("dict[str, Any]", check).get("notes")
                if value is not None:
                    return str(value)
    return None


def shortlist_rows(payload: Mapping[str, Mapping[str, Any]]) -> list[tuple[int, str, str | None, str | None]]:
    """Shortlist 의 몸 행(No, Topic, F, G). 빈 칸은 None."""
    regulation = payload["regulation_updates_by_topic"]
    controversy = payload["controversies_by_topic"]
    rows: list[tuple[int, str, str | None, str | None]] = []
    for no, topic in enumerate(sorted(set(regulation) | set(controversy)), 1):
        reg_bundle, con_bundle = regulation.get(topic), controversy.get(topic)
        reg, reg_failed = regulation_list(reg_bundle)
        con, con_failed = controversy_list(con_bundle)
        reg_cells = [f"{i}) {display(x, REGULATION_ITEM_KEYS)}" for i, x in enumerate(reg, 1)]
        con_cells = [f"{i}) {display(x, CONTROVERSY_ITEM_KEYS)}" for i, x in enumerate(con, 1)]
        if reg_failed:
            reg_cells = [PARSE_FAILED]
        if con_failed:
            con_cells = [PARSE_FAILED]
        for i in range(max(len(reg_cells), len(con_cells), 1)):
            f = reg_cells[i] if i < len(reg_cells) else None
            g = con_cells[i] if i < len(con_cells) else None
            rows.append((no, topic, f, g))
        reg_note, con_note = note(reg_bundle), note(con_bundle)
        if reg_note is not None or con_note is not None:
            rows.append(
                (
                    no,
                    topic,
                    None if reg_note is None else NOTES + reg_note,
                    None if con_note is None else NOTES + con_note,
                )
            )
    return rows


def raw_json_chunks(payload: Mapping[str, Any]) -> list[str]:
    """RAW_JSON 의 글을 UTF-16 32,767 단위 안으로 자른 조각(A1, A2, …). BMP 밖 글자는 가르지 않고 다음 조각으로.
    이으면 json.dumps(payload, ensure_ascii=False)."""
    text = json.dumps(payload, ensure_ascii=False)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = utf16_cut(text, CELL_LIMIT, start)
        chunks.append(text[start:end])
        start = end
    return chunks or [""]


def build_websearch(result: Mapping[str, Any]) -> bytes:
    """결과 꼴 한 건 → 1부 엑셀 바이트."""
    payload = websearch_payload(result)
    book = Workbook()
    sheet = book.active
    assert sheet is not None  # noqa: S101 — 새 Workbook 은 시트 하나를 갖고 시작한다
    sheet.title = SHORTLIST
    _put(sheet, "B1", TITLE, bold=True)
    for col, text in HEADER.items():
        _put(sheet, f"{col}3", text, bold=True)
    for r, (no, topic, f, g) in enumerate(shortlist_rows(payload), 4):
        _put(sheet, f"B{r}", no)
        _put(sheet, f"C{r}", topic)
        _put(sheet, f"F{r}", None if f is None else fit_cell(f)[0])  # 넘으면 표시(IR2a 처분 ⑮)
        _put(sheet, f"G{r}", None if g is None else fit_cell(g)[0])
    raw = book.create_sheet(RAW_JSON)
    for r, chunk in enumerate(raw_json_chunks(payload), 1):
        cell = raw.cell(row=r, column=1)
        cell.value = no_lone_surrogates(chunk)
        cell.data_type = "s"  # 조각이 `=` 로 시작해도 글자 칸
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
