"""Scope 3 배출계수 출처 글(밴드 S3Q1 ③ — 발주서 Q9·Q10, 시안 댓글 5db0a413). 순수: 바이트 → 글 표, 본문 → 새 본문.

활동·에너지 줄의 출처 칸은 지금 계수 책의 시트 이름이다(`factor.sheet`). 이 파일은 책 바이트(scope3_files.FACTOR_BOOK —
고정 바이트, MARC-ENT-521)를 한 번 읽어 시트마다 머리(A1) 출처 글과 `에너지_C3` 의 줄 비고(「출처/비고」 열)를 짓고,
결과 경로가 읽을 때 줄의 `factor` 에 `sourceText` 를 더한다(저장된 결과·엔진은 그대로 — 옛 결과도 새 글).
    머리 글   A1 은 「<표 이름> | <쓰임> | 출처: <글>」 꼴. 「출처:」 뒤 글. 예외 표(HEAD_SECOND_PART)는 둘째 토막.
              마크스폰이 글을 준 시트는 그 글(HEAD_GIVEN — 폐기물_C5, MARC-ENT-634 답). 그 밖에 「출처:」 가 없는
              시트(구매_USEPA·전력_국가별)는 None → 칸을 싣지 않음(웹은 지금 꼴).
    C3 비고   `에너지_C3` 줄은 계수 제목(엔진 found.name — 책의 활동유형 칸 글자)과 같은 첫 줄의 「출처/비고」 글이
              먼저, 없으면 머리 글. 수 자취가 섞인 글도 그대로.
구매 줄(kind purchase)은 출처가 갈래 코드라 건드리지 않는다(이 밴드 밖). 사건(고친 줄)의 출처는 그대로(Q11).
"""

import functools
import io
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, cast

from openpyxl import load_workbook

from esgapi.inventory.flows.binding_157 import FileMissing
from esgapi.inventory.service.utils import scope3_files

SOURCE_WORD: Final = "출처:"
HEAD_SECOND_PART: Final = frozenset({"폐기물_C12"})
"""「출처:」 낱말 없이 둘째 토막이 출처인 시트(Q10 예외 표)."""
HEAD_GIVEN: Final = {"폐기물_C5": "환경부 환경성적표지"}
"""머리에 「출처:」 가 없어 마크스폰이 글을 준 시트(MARC-ENT-634 답, 밴드 S3V1) — 시트 머리 글과 상관없이 이 글."""
C3_SHEET: Final = "에너지_C3"
C3_HEADER_ROW: Final = 3  # 엑셀 3행 = 엔진 `ENERGY_C3_HEADER_ROW`(0 기준 2)
C3_NAME_WORD: Final = "활동유형"
C3_NOTE_WORD: Final = "출처"


@dataclass(frozen=True)
class SourceTexts:
    """시트 → 머리 출처 글, `에너지_C3` 활동유형 → 줄 비고. 없는 것은 열쇠가 없다."""

    heads: Mapping[str, str] = field(default_factory=dict[str, str])
    c3_notes: Mapping[str, str] = field(default_factory=dict[str, str])


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def head_source(sheet: str, a1: object) -> str | None:
    """A1 글 → 출처 글(Q10). 꼴이 아니면 None."""
    if sheet in HEAD_GIVEN:
        return HEAD_GIVEN[sheet]
    text = _text(a1)
    if text is None:
        return None
    parts = [part.strip() for part in text.split("|")]
    if sheet in HEAD_SECOND_PART:
        return parts[1] or None if len(parts) > 1 else None
    for part in parts:
        if part.startswith(SOURCE_WORD):
            return part.removeprefix(SOURCE_WORD).strip() or None
    return None


def read_sources(content: bytes) -> SourceTexts:
    """책 바이트 → 글 표. 읽지 못하면 빈 표(던지지 않는다 — 출처 글은 꾸밈이라 결과를 막지 않는다)."""
    try:
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:  # 깨진 책이면 출처 글만 없다
        return SourceTexts()
    try:
        heads: dict[str, str] = {}
        notes: dict[str, str] = {}
        for sheet in book.worksheets:
            rows = sheet.iter_rows(values_only=True)
            first = next(rows, ())
            found = head_source(sheet.title, first[0] if first else None)
            if found is not None:
                heads[sheet.title] = found
            if sheet.title == C3_SHEET:
                notes = _c3_notes(sheet.iter_rows(min_row=C3_HEADER_ROW, values_only=True))
        return SourceTexts(heads, notes)
    finally:
        book.close()


def _c3_notes(rows: object) -> dict[str, str]:
    """「출처/비고」 열: 머리 줄(엑셀 3행)에서 활동유형·출처 열을 찾고 아래 줄마다 이름 → 글.
    같은 이름은 첫 줄(엔진 찾기의 iloc[0] 과 같은 줄)."""
    iterator = iter(cast("list[tuple[object, ...]]", rows))
    header = next(iterator, ())
    names = [str(cell) if cell is not None else "" for cell in header]
    name_col = next((i for i, name in enumerate(names) if C3_NAME_WORD in name), None)
    note_col = next((i for i, name in enumerate(names) if C3_NOTE_WORD in name), None)
    if name_col is None or note_col is None:
        return {}
    notes: dict[str, str] = {}
    for row in iterator:
        name = _text(row[name_col]) if len(row) > name_col else None
        note = _text(row[note_col]) if len(row) > note_col else None
        if name is not None and note is not None and name not in notes:
            notes[name] = note
    return notes


@functools.lru_cache(maxsize=2)
def _parsed(content: bytes) -> SourceTexts:
    return read_sources(content)


def packaged_sources() -> SourceTexts:
    """패키지 책의 글 표. 바이트는 부를 때마다 읽고(약 100KB — 끼움과 같은 읽기) 글 표는 바이트로 캐시한다(책이 고정
    바이트라 실제로는 한 번 짓는다 — 바이트가 바뀌면 다시 짓는다). 책이 없으면 빈 표."""
    content = scope3_files.FACTOR_BOOK.read()
    return SourceTexts() if isinstance(content, FileMissing) else _parsed(content)


def source_text(texts: SourceTexts, sheet: str, title: object) -> str | None:
    """한 줄의 출처 글: C3 는 줄 비고 먼저, 그 밖은 시트 머리. 없으면 None."""
    if sheet == C3_SHEET:
        name = _text(title)
        note = None if name is None else texts.c3_notes.get(name)
        if note is not None:
            return note
    return texts.heads.get(sheet)


def _with_row(row: object, texts: SourceTexts) -> object:
    if not isinstance(row, Mapping):
        return row
    found = cast("Mapping[str, object]", row)
    factor = found.get("factor")
    if found.get("kind") == "purchase" or not isinstance(factor, Mapping):
        return found
    cells = cast("Mapping[str, object]", factor)
    sheet = cells.get("sheet")
    text = source_text(texts, sheet, cells.get("title")) if isinstance(sheet, str) else None
    if text is None:
        return found
    return {**found, "factor": {**cells, "sourceText": text}}


def with_sources(body: Mapping[str, object], texts: SourceTexts) -> dict[str, object]:
    """결과 본문 → 활동·에너지 줄 factor 에 sourceText 를 더한 새 본문(받은 본문은 고치지 않는다). 그 밖 칸은 그대로."""
    sheets = body.get("sheets")
    if not isinstance(sheets, list):
        return dict(body)
    out: list[object] = []
    for item in cast("list[object]", sheets):
        found = cast("Mapping[str, object]", item) if isinstance(item, Mapping) else None
        if found is None or not isinstance(found.get("rows"), list):
            out.append(cast("object", item))
            continue
        rows = cast("list[object]", found["rows"])
        out.append({**found, "rows": [_with_row(row, texts) for row in rows]})
    return {**body, "sheets": out}
