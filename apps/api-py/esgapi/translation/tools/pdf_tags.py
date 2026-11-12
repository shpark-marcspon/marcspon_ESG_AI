"""PDF 입력 어댑터(흐름 translation.pdf@158 — 밴드 TRD2, 결정 MARC-ENT-471): docparse 분해 판 2 의 문서 모델 →
1차 엔진(colab_158, 0줄 — MARC-ENT-442)이 받는 태그 글, 그리고 엔진의 번역 글 → 블록·칸 단위 번역.

    build(document, char_places, *, page_start, page_end) -> Tagged
        쪽 범위의 블록을 읽는 차례(`order`)로 태그 글에 싣는다. 쪽마다 `[PAGE n]`, 태그 번호는 쪽·종류마다 1부터.
        - 글 블록(region body): 제목(`heading`)이 새 묶음을 연다. 앞 블록과 가로 겹침이 좁은 쪽 폭의 0.5 미만이어도
          새 묶음(단이 바뀜 — 3단 쪽도). 묶음 하나 = `[BLOCK n]`, 안은 멤버 글을 빈 줄로 잇는다.
        - 줄 묶기(밴드 TRS5): 파서가 줄 하나씩 준 한 줄 높이 문단 블록이 같은 단에서 좁은 틈으로 이어지고 앞 줄이 넓고
          단 오른쪽 끝까지 차 있으면 한 멤버(문단)로 잇는다(id·key = 첫 줄, 글은 공백 하나로 이음).
        - 단 넘김 잇기(TRS5): 앞 단의 끝 줄이 끝까지 차 있고 문장 끝 부호가 없으면 오른쪽 단 위로 올라간 다음 줄은 같은
          `[BLOCK n]` 의 새 멤버(상자가 단을 가로지르지 않게 멤버는 따로). 도표 라벨·표·제목 판정은 TRD2 ★④·TRS4 그대로.
        - 도표 라벨: 읽는 차례로 이어진 짧은 블록(`is_label`)이 `VISUAL_MIN_RUN` 개 이상이면 `[VISUAL n]` 하나(글은
          그대로 엔진이 번역한다). 그림 래스터는 읽지 않는다(사용자 결정 몫).
        - 여러 줄 블록 나누기(밴드 TRS6): 파서가 공백으로 이어 준 목록 블록은 `char_places` runs 의 인쇄 줄로 다시
          나눈다 — 짧게 끝난 줄 다음 줄이 불릿 기호로 시작하거나 「짧은 머리 :」 목록 꼴이면 그 줄부터 같은 `[BLOCK n]`
          의 새 멤버(id `<블록>:l<n>`, `BULLET_SHORT`).
        - 표: 칸 + 그 칸의 `footnote_marks` → 엔진의 `table_rows_to_markdown` → `[TABLE n]`. 그 함수가 칸이 다 빈 행을
          버리므로 pipe 행 → 원 행 번호 표(`rows`)를 지도에 싣는다. 칸이 다 빈 표는 건너뛴다(`skipped.emptyTables`,
          MARC-ISSUE-422 의 3). 쪽을 덮고 칸이 성기며 긴 글 칸이 있는 표(파서가 본문을 삼킨 꼴 — `TABLE_DEMOTE_*`)는
          칸마다 글 블록으로 낮춘다(TRS6 — `notes` table_demoted).
        - 이중 블록(TRS6): 같은 쪽에 같은 글·같은 자리(`DUPLICATE_BOX`)로 두 번 그린 블록은 앞 것만 싣는다(`notes`
          block_folded — Word 에서 제목이 두 번 나오던 꼴).
        - 머리글·꼬리말(region header·footer): 태그 글 밖. 지도에만 원문으로(단위 tag None — 번역하지 않음).
        - 글자 층 없는 쪽: 건너뛰고 경고 `image_only_page`.
        불변식: 범위 안 비지 않은 블록 글·칸 글이 단위 하나에 꼭 한 번(어기면 `PdfTagsError`). 블록·칸 글의 한 줄이 태그
        꼴(엔진의 `TOP_TAG_RE`·`PAGE_TAG_LINE_RE` — 엔진의 태그 복원 뒤)이면 태그 글이 깨지므로 `SourceTagLine`
        (조용히 고치지 않는다).
    place(units, page_texts) -> Placed
        page_texts = 쪽 번호 → 엔진 번역 글의 그 쪽 조각(`[PAGE n]` 줄 포함). 쪽 안을 태그로 잘라 지도의 단위에 붙인다.
        level: block(문단 수 == 멤버 수) · group(아니면 — 묶음 상자 하나) · cell(표 행·열 모양 같고 몸의 비지 않은 줄이
        다 pipe 행) · table(아니면 — 몸 전체)
        · source_only(머리글·꼬리말 — 건너뜀) · missing. 붙이지 못한 글은 쪽의 `unplaced` 로 — 번역 글을 버리는 길 0.
        경고 code: tag_missing · tag_extra(지도에 없는·겹친 태그, 태그 밖 글) · tag_shift(차례가 어긋나거나 태그가 빠져
        뒤 번호가 당겨진 꼴 — 그 뒤 단위는 번호로 붙이지 않는다. 글이 맞는지는 문단 수·표 모양·길이 비율·숫자 덩이로
        가른다) · page_missing · length_ratio. 끝 번호만 빠진 꼴(차례 뒤집힘 없음)에서 문단 수만 다르고 길이 비율·
        숫자 덩이가 맞는 block·visual 단위는 group 으로 붙이고 그 단위마다 tag_shift(밴드 TRS5 — 표는 그대로).
        TRS6: ① 태그 되살리기 — 빠진 단위(이어진 덩어리 k1..kr)의 바로 앞 붙은 단위 몸 문단 수가 앞 멤버 + 빠진
        멤버와 꼭 같으면 꼬리 문단을 kr 부터 되돌린다(엔진이 짧은 구획의 태그 줄을 빠뜨린 꼴 — 관찰 7건 모두 이 수,
        번호 당김 0). 되살린 단위와 그 앞 단위마다 tag_shift, `notes` tag_recovered. ② 무른 길의 숫자는 번역의 숫자가
        모두 원문 숫자로 설명되면 맞음(억→billion·'25→2025 꼴). ③ 단 넘김 멤버가 있는 block 은 문단 수가 그 수만큼
        적어도 맞음.

순수하다 — django·contracts·outputs import 0(tests/test_axes.py). 엔진은 순수 함수만 import 한다(page_tags.py 선례).
"""

import itertools
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from esgapi.translation.engines.colab_158.gates import TOP_TAG_RE, split_page_sections
from esgapi.translation.engines.colab_158.pages import PAGE_TAG_LINE_RE
from esgapi.translation.engines.colab_158.structured import (
    escape_md_cell_docx,
    normalize_structured_tags,
    table_rows_to_markdown,
)

ADAPTER_VERSION: Final = "pdf_tags@3"

VISUAL_MAX_CHARS: Final = 16
VISUAL_MIN_RUN: Final = 4
"""도표 라벨 묶기 문턱 둘(밴드 TRD2 ★④ — 공개 보고서 R1 의 랩 쪽 여섯, 분해 판 2): 라벨 = 문단 블록이고 공백 뺀 글자
≤ VISUAL_MAX_CHARS 이며 문장 끝 부호가 없는 것, 그것이 읽는 차례로 VISUAL_MIN_RUN 개 이상 이어지면 [VISUAL n] 하나.
후보 (8·12·16·20자) × (2·3·4·5개)에서 16자·4개는 묶음 넷(도표·그림 라벨 셋, 서명 블록 하나)·라벨 섞인 글 묶음 7
(묶기 끔 10)·계획 호출 290(끔 314). 3개로 내리면 「(단위: …)」 줄 셋을 따로 묶기 시작하고(호출 282), 12자로 내리면
도표 제목이 빠져 섞임이 9 로 돌아간다. 20자는 16자와 같은 갈림. 오탐(서명 블록)도 글은 그대로 엔진이 번역한다."""
COLUMN_OVERLAP: Final = 0.5
"""앞 블록과 가로 겹침이 좁은 쪽 폭의 이 비율 미만이면 단이 바뀐 것으로 보고 새 묶음을 연다."""
LENGTH_RATIO_MIN: Final = 0.6
LENGTH_RATIO_MAX: Final = 6.0
"""번역/원문 글자 수(공백 뺌) 비율이 이 범위 밖이면 경고 `length_ratio`(★④ — 랩 번역 실측 태그 단위 29개의 비율
1.32~4.0, 가운데 2.02). 아래 끝은 숫자·영문뿐인 단위(비율 약 1)를 남기고, 위 끝은 실측 최댓값의 1.5배."""

LINE_SINGLE_MAX: Final = 1.6
LINE_GAP_MAX: Final = 1.2
LINE_FULL_SLACK: Final = 5.0
LINE_MIN_WIDTH: Final = 15.0
"""줄 묶기 문턱 넷(밴드 TRS5 — 글자 크기의 배수. 근거 = C0 실측, 공개 보고서 R1~R6 의 같은 단 한 줄
블록 쌍 1,904, band-reports/TRS5.md).
- LINE_SINGLE_MAX: 한 줄 높이 = 블록 높이 ≤ 이 배수(R3 4쪽 한 줄 1.14 · 파서가 묶은 두 줄 2.6). 1.3 이면 R2·R3·R4 에서
  9줄이 덜 묶이고 2.0 은 같다.
- LINE_GAP_MAX: 이을 줄 틈 ≤ 이 배수(R3 4쪽 줄 틈 0.66·0.97, 문단 틈 1.40·2.14). 1.4 로 올리면 R3 에서 2줄이 더
  묶이고(문단 틈 1.40 꼴), 1.0 이면 2줄이, 0.8 이면 23줄이 덜 묶인다.
- LINE_FULL_SLACK: 앞 줄 오른쪽이 단 오른쪽 끝에서 이 배수 안(끝 아닌 줄의 가장 먼 것 4.8 — 4.0 이면 그 한 줄이 갈린다).
- LINE_MIN_WIDTH: 앞 줄 폭 ≥ 이 배수(왼 띠 목차 줄 약 8, 편지 줄 약 31 — 8 이면 R3 에서 185줄이 더 묶인다).
서명·목차·목록 같은 짧은 줄은 LINE_MIN_WIDTH 와 LINE_FULL_SLACK 두 거름이 함께 막는다(하나만 남기지 않는다). 문장 끝
부호는 끝까지 찬 줄이 문단 안에서도 마침표로 끝나므로 묶기 조건이 아니다(짧은 끝 줄·넓은 틈이 문단을 가른다).
한계: 단 끝에서 끝까지 찬 제목형 줄·캡션이 문장 끝 부호 없이 끝나면 다음 단과 한 묶음이 되고(글은 그대로), 하이픈이나
`:`·`;` 로 끝나 이어지는 문장은 단을 넘어 잇지 않는다."""
BULLET_SHORT: Final = 5.0
"""여러 줄 블록 나누기 문턱(밴드 TRS6 — 글자 크기의 배수, `LINE_FULL_SLACK` 과 같은 뜻): 앞 인쇄 줄 오른쪽이 블록
오른쪽 끝에서 이 배수 넘게 비고 다음 줄이 불릿 기호(+공백)로 시작하거나, 블록 첫 줄과 다음 줄이 둘 다 「짧은 머리 :」
꼴이면 다음 줄부터 새 멤버. 근거 = C0 실측(공개 보고서 R1~R6 의 여러 줄 본문 블록 3,910 · 줄 쌍 11,403,
band-reports/TRS6.md): 새 멤버 407, 표본 30 오탐 0. 「앞 줄 문장 끝」은 조건이 아니다 — 문장 안 줄의 15%(1,626/10,766)
가 오른쪽이 이만큼 비어(오른끝 들쭉날쭉) 문장 끝 + 짧은 줄 283 중 약 50 이 문단 안으로 추정. 줄 첫머리 x0 차도
내어쓰기 목록의 이어진 줄을 가를 수 있어 쓰지 않는다. 한계: 끝까지 찬 줄 뒤의 불릿(540)은 그대로 이어진다."""
TABLE_DEMOTE_AREA: Final = 0.5
TABLE_DEMOTE_FILL: Final = 0.4
TABLE_DEMOTE_CELL: Final = 300
"""쪽을 덮는 가짜 표 낮추기 문턱 셋(밴드 TRS6 — 셋 다): 표 상자 넓이 ≥ AREA × 쪽 넓이 · 비지 않은 칸 몫 ≤ FILL ·
가장 긴 칸 글자 ≥ CELL. 근거 = C0 실측(공개 보고서 R1~R6 의 파서 표 1,040): 낮춤 2(R1 14쪽 0.76·0.30·1,327자 ·
R3 57쪽 0.598·0.17·1,145자 — 둘 다 본문을 삼킨 꼴) + 이슈 611 꼴(0.80·0.29·443). 가장 가까운 음성: R5 9쪽 긴 칸 266 ·
R3 156쪽 207 · R5 81쪽 채움 0.39·긴 칸 62(색인표). 초안(넓이 0.6 그리고 채움 또는 긴 칸 하나)은 정상 글표 9
(색인표 채움 0.6 넘음)를 낮춰 버렸다."""
DUPLICATE_BOX: Final = 1.0
"""이중 블록 접기 문턱(밴드 TRS6 2-7 — pt): 같은 쪽에서 글이 같고 상자 네 값의 차가 모두 이 안인 블록은 파서가 같은
글을 두 번 그린 것(겹쳐 그린 글자 층)으로 보고 뒤의 것을 싣지 않는다(id 는 `joined` 로 센다 — `_check_once`). 근거 = C0
ⓓ(공개 보고서 R1~R6 의 같은 쪽·같은 글·상자 차 ≤ 1pt 쌍: R1 7 · R2 1 · R3 527 · R4 4 · R5 0 · R6 0, 전부 읽는 차례
이웃) · 이슈 612 a(Word 에서 제목이 두 번 — 제목 블록 둘이 따로 `[BLOCK n]` 이 됨).
VISUAL 문턱(`VISUAL_MIN_RUN`)은 접기 전 그린 수로 센다 — 문턱이 이중 그리기가 섞인 자료로 잰 값이라 VISUAL 판정은
바꾸지 않는다(R3 에서 접은 527 중 라벨 314, 그린 수로 세지 않으면 VISUAL 131 → 107. 감독 11-10)."""
_SAME_LINE: Final = 0.5  # runs 둘이 한 인쇄 줄 = 세로 겹침 > 작은 높이 × 이 몫(reconcile places `_same_line` 과 같다)
_SIZE_SAME: Final = 0.12  # 글자 크기 차 ≤ 이 배수(파서 blocks.py 다음 줄 잇기 선례)
_INDENT_MAX: Final = 2.5  # 같은 단의 x0 차 ≤ 이 배수 × 글자(첫 줄 들여쓰기 몫)
_GAP_MIN: Final = -0.35  # 줄 틈 아래 끝(겹친 줄 상자 몫)

_SENTENCE_END: Final = re.compile(r"[.!?。…:;]\s*$")
_PARAGRAPHS: Final = re.compile(r"\n\s*\n")
_SEPARATOR_ROW: Final = re.compile(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?")
_NUMBER: Final = re.compile(r"\d+(?:[.,]\d+)*")
_BULLET: Final = re.compile(r"[•·‧∙▪◦○●■□▶►※\-–]\s")
_HEAD: Final = re.compile(r"[^\s:：][^:：]{0,24}\s?[:：]\s")

type UnitKind = Literal["block", "visual", "table", "header", "footer"]
type Level = Literal["block", "group", "cell", "table", "source_only", "missing"]


class PdfTagsError(Exception):
    """어댑터의 불변식이 깨졌다(블록·칸 글이 단위에 꼭 한 번이 아님). 흐름은 단계 예외로 둔다."""


class SourceTagLine(PdfTagsError):
    """원문 블록·칸 글의 한 줄이 태그 꼴이다(태그 글이 깨진다)."""


@dataclass(frozen=True, slots=True)
class Tagged:
    text: str
    """엔진에 넣는 태그 글. 태그 단위가 없으면 빈 글."""
    units: list[dict[str, Any]]
    """단위 지도(JSON 값): {tag, page, kind, members:[{id, key, kind, bbox, source}], cells?, rows?}."""
    pages: list[dict[str, Any]]
    """범위 안 쪽: {page, width, height, textLayer}."""
    skipped: dict[str, list[Any]]
    """{emptyTables: [표 id], imageOnlyPages: [쪽]}."""
    warnings: list[dict[str, Any]]
    notes: list[dict[str, Any]] = field(default_factory=lambda: [])
    """layout 밖 기록(흐름이 싣지 않는다 — 시험·보고용): {code: table_demoted|runs_mismatch|block_folded, page, ...}."""


@dataclass(frozen=True, slots=True)
class Placed:
    units: list[dict[str, Any]]
    """지도 차례 그대로: {tag, page, level, translations: [글]|None, cells?: [{row, col, text}]}."""
    unplaced: list[dict[str, Any]] = field(default_factory=lambda: [])
    """{page, text} — 단위에 붙이지 못한 번역 글."""
    warnings: list[dict[str, Any]] = field(default_factory=lambda: [])
    """{code, page, tag}."""
    notes: list[dict[str, Any]] = field(default_factory=lambda: [])
    """layout 밖 기록(흐름이 싣지 않는다 — 시험·보고용): {code: tag_recovered, page, tag}."""


# ── build ──


def _squeezed_len(text: str) -> int:
    return len("".join(text.split()))


def is_label(block: Mapping[str, Any]) -> bool:
    """도표 라벨로 볼 만한 블록: 문단 블록이고 짧으며(공백 뺀 글자 ≤ VISUAL_MAX_CHARS) 문장 끝 부호가 없다."""
    text = str(block["text"])
    return block["kind"] == "paragraph" and _squeezed_len(text) <= VISUAL_MAX_CHARS and not _SENTENCE_END.search(text)


def _overlap_ratio(a: Sequence[float], b: Sequence[float]) -> float:
    narrow = min(a[2] - a[0], b[2] - b[0])
    if narrow <= 0:
        return 1.0
    return (min(a[2], b[2]) - max(a[0], b[0])) / narrow


def _check_source(text: str, where: str) -> None:
    for line in normalize_structured_tags(text).splitlines():
        if TOP_TAG_RE.match(line.strip()) or PAGE_TAG_LINE_RE.match(line):
            raise SourceTagLine(f"원문 {where} 의 한 줄이 태그 꼴이다")


def _member(block: Mapping[str, Any], source: str) -> dict[str, Any]:
    return {
        "id": block["id"],
        "key": block.get("key"),
        "kind": block["kind"],
        "bbox": list(block["bbox"]),
        "source": source,
    }


def _table_rows(table: Mapping[str, Any]) -> list[list[str]]:
    """칸 글 + 그 칸의 각주 표시(칸 글 뒤에 붙인다 — 파서의 숫자 칸에서 떼어 낸 것)."""
    rows = [[str(cell) for cell in row] for row in table["cells"]]
    for mark in table.get("footnote_marks", []):
        rows[mark["row"]][mark["col"]] += str(mark["mark"])
    return rows


def _table_unit(
    page: int, tag: str, block: Mapping[str, Any], table: Mapping[str, Any], boxes: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    rows = _table_rows(table)
    lines = table_rows_to_markdown(rows)
    kept = [i for i, row in enumerate(rows) if any(escape_md_cell_docx(cell) for cell in row)]  # 엔진이 남기는 행
    cells: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            if not text.strip():
                continue
            cid = f"{table['id']}:r{i}c{j}"
            box = boxes.get(cid)
            cells.append({"row": i, "col": j, "id": cid, "bbox": None if box is None else list(box), "source": text})
    member = _member(block, "\n".join(lines)) | {"id": table["id"]}
    return {"tag": tag, "page": page, "kind": "table", "members": [member], "cells": cells, "rows": kept}, lines


def _font(block: Mapping[str, Any]) -> float:
    return float(block.get("font_size") or 0.0)


def _one_line(block: Mapping[str, Any]) -> bool:
    """줄 묶기 후보: 본문 문단 블록이고 한 줄 높이(파서가 이미 묶은 여러 줄 문단은 아님)."""
    size, box = _font(block), block["bbox"]
    return (
        block["kind"] == "paragraph"
        and block.get("region", "body") == "body"
        and size > 0
        and box[3] - box[1] <= LINE_SINGLE_MAX * size
    )


def _column_rights(blocks: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """쪽의 본문 한 줄 블록마다 그 단의 오른쪽 끝 = 그 줄과 가로 겹침 ≥ COLUMN_OVERLAP 인 한 줄 블록들의 x1 최댓값."""
    lines = [b for b in blocks if b["kind"] == "paragraph" and str(b.get("text", "")).strip() and _one_line(b)]
    return {
        str(b["id"]): max(float(o["bbox"][2]) for o in lines if _overlap_ratio(b["bbox"], o["bbox"]) >= COLUMN_OVERLAP)
        for b in lines
    }


def _has_tag_line(text: str) -> bool:
    return any(TOP_TAG_RE.match(line.strip()) or PAGE_TAG_LINE_RE.match(line) for line in text.splitlines())


def _para_member(lines: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """줄 여럿 → 멤버 하나: id·key·kind = 첫 줄 · bbox = 줄 상자 합 · 글 = 줄 글을 공백 하나로 이음. 둘째 줄부터의 id 도
    낸다(글에 실은 줄과 센 줄이 같은 목록에서 나온다 — `_check_once`)."""
    first = lines[0]
    if len(lines) == 1:
        return _member(first, str(first["text"])), []
    boxes = [b["bbox"] for b in lines]
    member = _member(first, " ".join(str(b["text"]) for b in lines))
    member["bbox"] = [
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    ]
    return member, [str(b["id"]) for b in lines[1:]]


class _Page:
    """한 쪽의 태그 글 짓기(번호는 종류마다 1부터). 묶음(`group`)은 멤버마다 그 멤버의 줄(원 블록) 목록."""

    def __init__(self, page: int, rights: Mapping[str, float] | None = None) -> None:
        self.page = page
        self.lines: list[str] = [f"[PAGE {page}]"]
        self.units: list[dict[str, Any]] = []
        self.numbers: dict[str, int] = {}
        self.group: list[list[Mapping[str, Any]]] = []
        self.labels: list[Mapping[str, Any]] = []
        self.rights: Mapping[str, float] = rights or {}
        self.joined: list[str] = []
        """멤버에 이어 붙인 둘째 줄부터의 id(`_check_once` 가 함께 센다 — 지도 칸을 더하지 않는다)."""
        self.twins = 0
        """지금 라벨 덩이에서 접은 겹친 라벨 수(VISUAL 문턱은 접기 전 그린 수로 센다 — TRS6 2-7)."""

    def tag(self, kind: str) -> str:
        self.numbers[kind] = self.numbers.get(kind, 0) + 1
        return f"{kind} {self.numbers[kind]}"

    def emit(self, kind: UnitKind, blocks: Sequence[Sequence[Mapping[str, Any]]]) -> None:
        """blocks = 멤버마다 그 멤버의 줄(원 블록) 목록."""
        members: list[dict[str, Any]] = []
        for lines in blocks:
            member, joined = _para_member(lines)
            members.append(member)
            self.joined.extend(joined)
        tag = self.tag(kind.upper())
        self.lines.extend(["", f"[{tag}]", "\n\n".join(m["source"] for m in members)])
        self.units.append({"tag": tag, "page": self.page, "kind": kind, "members": members})

    def flush_group(self) -> None:
        if self.group:
            self.emit("block", self.group)
            self.group = []

    def _full(self, line: Mapping[str, Any]) -> bool:
        """줄 폭이 넓고(LINE_MIN_WIDTH) 단 오른쪽 끝까지 찼다(LINE_FULL_SLACK) — 문단이 다음 줄로 이어질 수 있는 줄."""
        size, box = _font(line), line["bbox"]
        right = self.rights.get(str(line["id"]))
        return (
            right is not None and box[2] - box[0] >= LINE_MIN_WIDTH * size and box[2] >= right - LINE_FULL_SLACK * size
        )

    def _continues(self, last: Mapping[str, Any], block: Mapping[str, Any]) -> bool:
        """block 이 last(지금 멤버의 끝 줄)와 같은 단·같은 문단의 다음 줄인가(2-1)."""
        if not (_one_line(last) and _one_line(block)):
            return False
        size, a, b = _font(last), last["bbox"], block["bbox"]
        gap = b[1] - a[3]
        return (
            abs(_font(block) - size) <= _SIZE_SAME * size
            and _overlap_ratio(a, b) >= COLUMN_OVERLAP
            and abs(b[0] - a[0]) <= _INDENT_MAX * size
            and _GAP_MIN * size <= gap <= LINE_GAP_MAX * size
            and self._full(last)
        )

    def _carries(self, last: Mapping[str, Any], block: Mapping[str, Any]) -> bool:
        """단이 바뀌었지만 last 의 문장이 끝나지 않은 채 끝까지 차 있고 block 이 오른쪽 단 위로 올라갔다(2-2)."""
        if not (_one_line(last) and _one_line(block)):
            return False
        size = _font(last)
        return (
            abs(_font(block) - size) <= _SIZE_SAME * size
            and block["bbox"][0] > last["bbox"][0]
            and block["bbox"][1] < last["bbox"][1]
            and self._full(last)
            and not _SENTENCE_END.search(str(last["text"]))
        )

    def flush_labels(self) -> None:
        """이어진 라벨 블록: 문턱 이상이면 [VISUAL n] 하나, 아니면 글 묶음으로 돌려보낸다."""
        labels, self.labels = self.labels, []
        drawn, self.twins = len(labels) + self.twins, 0
        if labels and drawn >= VISUAL_MIN_RUN:
            self.flush_group()
            self.emit("visual", [[b] for b in labels])
            return
        for block in labels:
            self.add_text(block)

    def add_text(self, block: Mapping[str, Any]) -> None:
        member = self.group[-1] if self.group else None
        last = member[-1] if member else None  # 판정은 끝 줄의 원 블록으로(이은 멤버의 합 상자가 아니라)
        if member is not None and last is not None:
            if self._continues(last, block) and not _has_tag_line(" ".join(str(b["text"]) for b in [*member, block])):
                member.append(block)
                return
            if block["kind"] == "heading" or (
                _overlap_ratio(last["bbox"], block["bbox"]) < COLUMN_OVERLAP and not self._carries(last, block)
            ):
                self.flush_group()
        self.group.append([block])

    def flush(self) -> None:
        self.flush_labels()
        self.flush_group()


def _same_line(a: Sequence[float], b: Sequence[float]) -> bool:
    """두 세로 범위 (y0, y1) 가 한 인쇄 줄인가(겹침 > 작은 높이 × `_SAME_LINE`)."""
    return min(a[1], b[1]) - max(a[0], b[0]) > _SAME_LINE * min(a[1] - a[0], b[1] - b[0])


def _print_lines(runs: Sequence[Mapping[str, Any]], size: int) -> list[dict[str, Any]] | None:
    """runs → 인쇄 줄 [{start, box:[x0,y0,x1,y1]}](세로로 겹치는 이웃 run 은 한 줄). 글과 안 맞으면(첫 start ≠ 0 ·
    start 가 늘지 않음 · 글 길이 넘음 · 좌표 없음) None."""
    lines: list[dict[str, Any]] = []
    previous = -1
    for run in runs:
        start, xs0, xs1 = int(run["start"]), run["x0"], run["x1"]
        if start <= previous or start >= size or not xs0 or not xs1 or (not lines and start != 0):
            return None
        previous = start
        y = (float(run["y0"]), float(run["y1"]))
        if lines and _same_line(lines[-1]["box"][1::2], y):
            box = lines[-1]["box"]
            box[1], box[2], box[3] = min(box[1], y[0]), max(box[2], float(xs1[-1])), max(box[3], y[1])
            continue
        lines.append({"start": start, "box": [float(xs0[0]), y[0], float(xs1[-1]), y[1]]})
    return lines


def _split_points(block: Mapping[str, Any], lines: Sequence[Mapping[str, Any]]) -> list[int]:
    """새 멤버를 여는 줄 차례(BULLET_SHORT): 앞 줄이 짧게 끝나고 다음 줄이 불릿 기호로 시작하거나, 블록 첫 줄과 다음
    줄이 둘 다 「짧은 머리 :」 꼴."""
    text, size, right = str(block["text"]), _font(block), float(block["bbox"][2])
    starts = [int(line["start"]) for line in lines] + [len(text)]
    first_head = _HEAD.match(text[starts[0] : starts[1]].strip()) is not None
    points: list[int] = []
    for i in range(1, len(lines)):
        after = text[starts[i] : starts[i + 1]].strip()
        short = right - float(lines[i - 1]["box"][2]) >= BULLET_SHORT * size
        listed = _BULLET.match(after) is not None or (first_head and _HEAD.match(after) is not None)
        if short and listed and text[starts[i - 1] : starts[i]].strip():
            points.append(i)
    return points


def _pieces(block: Mapping[str, Any], runs: Sequence[Mapping[str, Any]] | None) -> list[Mapping[str, Any]] | None:
    """여러 줄 본문 블록을 인쇄 줄로 나눈 조각 블록들(첫 조각 = 그 블록 id·key, 둘째부터 id `<블록>:l<n>` · n = 줄
    차례 · 상자 = 그 줄들 상자 합). 나눌 자리가 없으면 [블록], runs 가 글과 안 맞으면 None."""
    text = str(block["text"])
    if (
        runs is None
        or block["kind"] != "paragraph"
        or block.get("region", "body") != "body"
        or _font(block) <= 0
        or _one_line(block)
    ):
        return [block]
    lines = _print_lines(runs, len(text))
    if lines is None:
        return None
    if len(lines) < 2:
        return [block]
    points = _split_points(block, lines)
    if not points:
        return [block]
    pieces: list[Mapping[str, Any]] = []
    for a, b in zip([0, *points], [*points, len(lines)], strict=True):
        start, end = int(lines[a]["start"]), len(text) if b == len(lines) else int(lines[b]["start"])
        boxes = [line["box"] for line in lines[a:b]]
        piece = dict(block) | {
            "text": text[start:end].strip(),
            "bbox": [
                min(x[0] for x in boxes),
                min(x[1] for x in boxes),
                max(x[2] for x in boxes),
                max(x[3] for x in boxes),
            ],
        }
        if a:
            piece |= {"id": f"{block['id']}:l{a}", "key": None}
        pieces.append(piece)
    return pieces


def _twin(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """같은 글(앞뒤 공백 뺌)·같은 자리(상자 네 값 차 ≤ DUPLICATE_BOX)의 블록 둘인가."""
    return str(a["text"]).strip() == str(b["text"]).strip() and all(
        abs(float(x) - float(y)) <= DUPLICATE_BOX for x, y in zip(a["bbox"], b["bbox"], strict=True)
    )


def _demoted(table: Mapping[str, Any], meta: Mapping[str, Any], rows: Sequence[Sequence[str]]) -> bool:
    """쪽을 덮고 칸이 성기며 긴 글 칸이 있는 표인가(TABLE_DEMOTE_* — 셋 다)."""
    box = table.get("bbox")
    page_area = float(meta["width"]) * float(meta["height"])
    cells = [cell for row in rows for cell in row]
    filled = [cell for cell in cells if cell.strip()]
    if box is None or page_area <= 0 or not filled:
        return False
    area = (float(box[2]) - float(box[0])) * (float(box[3]) - float(box[1])) / page_area
    return (
        area >= TABLE_DEMOTE_AREA
        and len(filled) / len(cells) <= TABLE_DEMOTE_FILL
        and max(len(cell) for cell in filled) >= TABLE_DEMOTE_CELL
    )


def build(
    document: Mapping[str, Any],
    char_places: Mapping[str, Any] | None,
    *,
    page_start: int | None,
    page_end: int | None,
) -> Tagged:
    """머리말 build. document = docparse 문서 모델(분해 판 2), char_places = 글자 자리(칸 상자에 쓴다)."""
    containers = (char_places or {}).get("containers", [])
    boxes = {c["id"]: c["bbox"] for c in containers}
    runs_of = {c["id"]: c["runs"] for c in containers if c.get("runs")}
    tables = {t["id"]: t for t in document["tables"]}
    notes: list[dict[str, Any]] = []

    def wanted(page: int) -> bool:
        return (page_start is None or page >= page_start) and (page_end is None or page <= page_end)

    metas = [p for p in document["pages"] if wanted(int(p["page"]))]
    by_page: dict[int, list[Mapping[str, Any]]] = {}
    for block in document["blocks"]:
        by_page.setdefault(int(block["page"]), []).append(block)
    texts: list[str] = []
    units: list[dict[str, Any]] = []
    skipped: dict[str, list[Any]] = {"emptyTables": [], "imageOnlyPages": []}
    warnings: list[dict[str, Any]] = []
    expected: list[str] = []
    joined: list[str] = []
    for meta in metas:
        page = int(meta["page"])
        if meta["text_layer"] != "present":
            skipped["imageOnlyPages"].append(page)
            warnings.append({"code": "image_only_page", "page": page, "tag": None})
            continue
        built = _Page(page, _column_rights(by_page.get(page, [])))
        side: list[dict[str, Any]] = []
        drawn: list[Mapping[str, Any]] = []  # 이 쪽에 실은 글 블록(이중 블록 접기 — DUPLICATE_BOX)
        for block in sorted(by_page.get(page, []), key=lambda b: int(b["order"])):
            if block["kind"] == "table":
                table = tables[block["table_id"]]
                rows = _table_rows(table)
                for i, row in enumerate(rows):
                    for j, text in enumerate(row):
                        if text.strip():
                            _check_source(text, f"{table['id']}:r{i}c{j}")
                            expected.append(f"{table['id']}:r{i}c{j}")
                if not any(cell.strip() for row in rows for cell in row):
                    skipped["emptyTables"].append(table["id"])
                    continue
                if _demoted(table, meta, rows):  # 칸마다 글 블록으로(칸 id 그대로 — `_check_once` 의 셈 같음)
                    notes.append({"code": "table_demoted", "page": page, "table": table["id"]})
                    built.flush_labels()
                    for i, row in enumerate(rows):
                        for j, text in enumerate(row):
                            if not text.strip():
                                continue
                            cid = f"{table['id']}:r{i}c{j}"
                            box = boxes.get(cid) or table.get("bbox") or block["bbox"]
                            cell = {"id": cid, "kind": "paragraph", "region": "body", "bbox": list(box), "text": text}
                            built.add_text(cell)
                    continue
                built.flush()
                unit, lines = _table_unit(page, built.tag("TABLE"), block, table, boxes)
                built.lines.extend(["", f"[{unit['tag']}]", *lines])
                built.units.append(unit)
                continue
            text = str(block["text"])
            if not text.strip():
                continue
            _check_source(text, str(block["id"]))
            expected.append(str(block["id"]))
            twin = next((b for b in drawn if _twin(b, block)), None)
            if twin is not None:  # 같은 글을 같은 자리에 두 번 그렸다 — 앞 것만 싣는다
                joined.append(str(block["id"]))
                notes.append({"code": "block_folded", "page": page, "block": block["id"], "into": twin["id"]})
                if block.get("region", "body") in ("header", "footer"):
                    continue
                if is_label(block):  # 라벨 덩이의 그린 수에는 센다(VISUAL 판정은 접기 전 그대로)
                    built.twins += 1
                else:
                    built.flush_labels()
                continue
            drawn.append(block)
            region = block.get("region", "body")
            if region in ("header", "footer"):
                side.append({"tag": None, "page": page, "kind": region, "members": [_member(block, text)]})
                continue
            if is_label(block):
                built.labels.append(block)
                continue
            built.flush_labels()
            pieces = _pieces(block, runs_of.get(str(block["id"])))
            if pieces is None:
                notes.append({"code": "runs_mismatch", "page": page, "block": block["id"]})
                pieces = [block]
            built.add_text(pieces[0])
            for piece in pieces[1:]:  # 같은 묶음의 이은 멤버(add_text 를 거치지 않는다 — 단·제목 판정 밖)
                expected.append(str(piece["id"]))
                built.group.append([piece])
        built.flush()
        joined.extend(built.joined)
        if built.units:
            texts.append("\n".join(built.lines))
        units.extend(built.units)
        units.extend(side)
    _check_once(expected, units, joined)
    pages = [
        {"page": p["page"], "width": p["width"], "height": p["height"], "textLayer": p["text_layer"]} for p in metas
    ]
    text = "\n\n".join(texts) + "\n" if texts else ""
    return Tagged(text=text, units=units, pages=pages, skipped=skipped, warnings=warnings, notes=notes)


def _check_once(expected: Sequence[str], units: Sequence[Mapping[str, Any]], joined: Sequence[str] = ()) -> None:
    """joined = 멤버에 이어 붙인 줄 id(멤버 id 는 첫 줄 — 둘째 줄부터는 여기서 센다)."""
    seen: dict[str, int] = {}
    for uid in joined:
        seen[uid] = seen.get(uid, 0) + 1
    for unit in units:
        ids = [c["id"] for c in unit["cells"]] if unit["kind"] == "table" else [m["id"] for m in unit["members"]]
        for uid in ids:
            seen[uid] = seen.get(uid, 0) + 1
    want = {uid: 1 for uid in expected}
    if seen != want:
        bad = sorted(set(seen) ^ set(want)) + sorted(k for k in seen.keys() & want.keys() if seen[k] != 1)
        raise PdfTagsError(f"블록·칸 글이 단위에 꼭 한 번이 아니다: {len(bad)}곳")


# ── place ──


def _label(line: str) -> str | None:
    found = TOP_TAG_RE.match(line.strip())
    return None if found is None else " ".join(found.group(1).upper().split())


def paragraphs(body: str) -> list[str]:
    return [p.strip() for p in _PARAGRAPHS.split(body) if p.strip()]


def table_rows(body: str) -> list[list[str]]:
    """pipe 표 글 → 행마다 칸 글(구분 행은 뺀다). 칸 안의 `&#124;`·`<br>` 는 `|`·줄바꿈으로 되돌린다."""
    rows: list[list[str]] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line.startswith("|") or _SEPARATOR_ROW.fullmatch(line):
            continue
        line = line[1:-1] if line.endswith("|") and len(line) > 1 else line[1:]
        rows.append([c.strip().replace("&#124;", "|").replace("<br>", "\n") for c in line.split("|")])
    return rows


def _shape(rows: Sequence[Sequence[str]]) -> tuple[int, ...]:
    return tuple(len(r) for r in rows)


def _source_text(unit: Mapping[str, Any]) -> str:
    return "\n\n".join(str(m["source"]) for m in unit["members"])


def _ratio_ok(unit: Mapping[str, Any], body: str) -> bool:
    source = _squeezed_len(_source_text(unit))
    if source == 0:
        return True
    return LENGTH_RATIO_MIN <= _squeezed_len(body) / source <= LENGTH_RATIO_MAX


def _numbers(text: str) -> list[str]:
    return sorted(n.replace(",", "") for n in _NUMBER.findall(text))


def _number_key(number: str) -> str:
    """숫자 덩이의 정규형: 숫자만(`.`·`,` 뺌) 남기고 끝 0 을 뗀 것(114 ↔ 11.4 · 2 ↔ 200 · 5,000 ↔ 5)."""
    return number.replace(",", "").replace(".", "").rstrip("0") or "0"


def _numbers_explained(body: str, source: str) -> bool:
    """번역의 숫자 덩이가 모두 원문 숫자로 설명되는가(정규형이 같음 · 번역의 네 자리 19xx·20xx 는 끝 두 자리로도 —
    '25 ↔ 2025). 원문 숫자가 번역에서 사라지는 것(2위 → second)은 괜찮다."""
    have = {_number_key(n) for n in _NUMBER.findall(source)}
    for number in _NUMBER.findall(body):
        digits = number.replace(",", "").replace(".", "")
        if _number_key(number) in have:
            continue
        if len(digits) == 4 and digits[:2] in ("19", "20") and _number_key(digits[2:]) in have:
            continue
        return False
    return True


def _carry_count(unit: Mapping[str, Any]) -> int:
    """block 단위에서 단 넘김(TRS5 `_carries`)으로 갈린 멤버 쌍의 수: 다음 멤버가 오른쪽 단(가로 겹침 <
    COLUMN_OVERLAP · x0 큼) 위쪽(y0 가 앞 멤버 아래 끝보다 위)이다. 묶음 안에서 단이 바뀌는 길은 단 넘김뿐이다."""
    if unit["kind"] != "block":
        return 0
    boxes = [m["bbox"] for m in unit["members"]]
    return sum(
        1 for a, b in itertools.pairwise(boxes) if b[0] > a[0] and b[1] < a[3] and _overlap_ratio(a, b) < COLUMN_OVERLAP
    )


def _count_range(unit: Mapping[str, Any]) -> tuple[int, int]:
    """번역 문단 수로 맞는 범위: 멤버 수 − 단 넘김 수 ~ 멤버 수(엔진은 단을 넘은 문장을 한 문단으로 낸다)."""
    members = len(unit["members"])
    return members - _carry_count(unit), members


def _fits(unit: Mapping[str, Any], body: str) -> bool:
    """번호가 당겨졌는지 의심할 때 이 글이 이 단위의 것으로 맞는가(문단 수·표 모양·길이 비율·숫자 덩이 — 번역에서
    숫자는 그대로 남으니 같은 모양의 이웃 단위를 숫자로 가른다. 표는 칸마다). 문단 수는 단 넘김만큼 너그럽다."""
    if not _ratio_ok(unit, body):
        return False
    source = _source_text(unit)
    if unit["kind"] == "table":
        rows, want = table_rows(body), table_rows(source)
        if _shape(rows) != _shape(want):
            return False
        return all(
            _numbers(a) == _numbers(b)
            for got, row in zip(rows, want, strict=True)
            for a, b in zip(got, row, strict=True)
        )
    low, high = _count_range(unit)
    return low <= len(paragraphs(body)) <= high and _numbers(body) == _numbers(source)


def _loosely_fits(unit: Mapping[str, Any], body: str) -> bool:
    """`_fits` 에서 문단 수를 빼고 숫자를 너그럽게 본 것: 엔진이 문단을 다시 짜거나 숫자 꼴을 바꾼(억 → billion ·
    '25년 → 2025) block·visual 단위(표에는 부르지 않는다 — 칸 자리). 번역에 원문으로 설명 안 되는 숫자가 있으면
    맞지 않는다(이웃 단위의 글)."""
    return _ratio_ok(unit, body) and _numbers_explained(body, _source_text(unit))


def _pipe_only(body: str) -> bool:
    return all(line.strip().startswith("|") for line in body.splitlines() if line.strip())


def _placed(unit: Mapping[str, Any], body: str) -> dict[str, Any]:
    base: dict[str, Any] = {"tag": unit["tag"], "page": unit["page"]}
    if unit["kind"] == "table":
        source, rows = table_rows(_source_text(unit)), table_rows(body)
        if rows and _shape(rows) == _shape(source) and _pipe_only(body):  # pipe 밖 줄(주석·붙은 이웃 글)은 몸째
            original = unit["rows"]
            cells = [
                {"row": original[r], "col": c, "text": text}
                for r, row in enumerate(rows)
                for c, text in enumerate(row)
                if r < len(original)
            ]
            return base | {"level": "cell", "translations": None, "cells": cells}
        return base | {"level": "table", "translations": [body]}
    parts = paragraphs(body)
    if len(parts) == len(unit["members"]):
        return base | {"level": "block", "translations": parts}
    return base | {"level": "group", "translations": [body]}


def _missing(unit: Mapping[str, Any]) -> dict[str, Any]:
    return {"tag": unit["tag"], "page": unit["page"], "level": "missing", "translations": None}


def _section_text(lines: Sequence[str]) -> str:
    return "\n".join(lines).strip()


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """문단(`paragraphs`)마다 글 안의 [처음,끝) — 사이 글자를 그대로 두고 자르려고."""
    starts = [0, *(m.end() for m in _PARAGRAPHS.finditer(text))]
    ends = [*(m.start() for m in _PARAGRAPHS.finditer(text)), len(text)]
    return [(a, b) for a, b in zip(starts, ends, strict=True) if text[a:b].strip()]


_RECOVER_WAYS_MAX: Final = 4096  # 문단 수 나눔을 셀 때의 위 끝(단 넘김이 아주 많은 덩어리는 되살리지 않는다)


def _recover(
    page: int,
    expected: Sequence[Mapping[str, Any]],
    got: list[tuple[int, str, str]],
    missing: Sequence[int],
    placed: Placed,
) -> tuple[list[tuple[int, str, str]], list[int]]:
    """태그 되살리기(밴드 TRS6): 빠진 단위가 이어진 덩어리 k1..kr 이고 그 바로 앞 단위 p 가 붙어 있으면, p 몸의 문단
    수가 p 멤버 + Σ k 멤버(단 넘김 너그러움 `_count_range` 를 더해서 — 나누는 길이 꼭 하나일 때)와 같을 때만 p 몸의
    꼬리 문단을 kr 부터 차례로 떼어 그 단위의 몸으로 둔다. p 가 표면 pipe 행 뒤 꼬리 줄만 센다. 덩어리는 뒤에서부터.
    되살린 덩어리의 p 와 k 마다 tag_shift(문단 수로 옮긴 글 — 원문과 맞대어 보라), `notes` tag_recovered.
    근거: 엔진이 짧은 구획(멤버 1~3)의 태그 줄을 빠뜨리면 그 번역이 앞 구획 몸 끝에 붙는다 — 관찰 7건 모두 「앞 몸
    문단 = 앞 멤버 + 빠진 멤버」, 번호 당김 0(band-handoffs/TRS6-cause.md). 한계: 엔진이 빠진 글을 앞 문단과 한
    문단으로 합치면 수가 안 맞아 되살리지 않는다(지금 길 그대로)."""
    got = sorted(got)
    lost = set(missing)
    chunks: list[list[int]] = []
    for k in sorted(missing):
        if chunks and chunks[-1][-1] == k - 1:
            chunks[-1].append(k)
        else:
            chunks.append([k])
    for chunk in reversed(chunks):
        at = {k: n for n, (k, _, _) in enumerate(got)}
        p = chunk[0] - 1
        if p not in at or any(expected[k]["kind"] == "table" for k in chunk):
            continue
        _, label, body = got[at[p]]
        unit = expected[p]
        head = ""
        own = _count_range(unit)
        region = body
        if unit["kind"] == "table":
            lines = body.splitlines()
            pipes = [i for i, line in enumerate(lines) if line.strip().startswith("|")]
            if not pipes:
                continue
            head, region, own = (
                "\n".join(lines[: pipes[-1] + 1]).strip(),
                "\n".join(lines[pipes[-1] + 1 :]).strip(),
                (0, 0),
            )
        spans = _paragraph_spans(region)
        ranges = [own, *(_count_range(expected[k]) for k in chunk)]
        size = 1
        for low, high in ranges:
            size *= high - low + 1
        if not spans or size > _RECOVER_WAYS_MAX:
            continue
        ways = [c for c in itertools.product(*(range(low, high + 1) for low, high in ranges)) if sum(c) == len(spans)]
        if len(ways) != 1:
            continue
        end = len(spans)
        bodies: dict[int, str] = {}
        for k, count in zip(reversed(chunk), reversed(ways[0][1:]), strict=True):
            bodies[k] = region[spans[end - count][0] : spans[end - 1][1]]
            end -= count
        kept = head if unit["kind"] == "table" else region[: spans[end - 1][1]]
        got[at[p]] = (p, label, kept)
        got = sorted([*got, *((k, str(expected[k]["tag"]), bodies[k]) for k in chunk)])
        lost -= set(chunk)
        placed.warnings.append({"code": "tag_shift", "page": page, "tag": label})
        for k in chunk:
            placed.warnings.append({"code": "tag_shift", "page": page, "tag": expected[k]["tag"]})
            placed.notes.append({"code": "tag_recovered", "page": page, "tag": expected[k]["tag"]})
    return got, [k for k in missing if k in lost]


def _place_page(
    page: int, expected: Sequence[Mapping[str, Any]], content: str, out: dict[int, dict[str, Any]], placed: Placed
) -> None:
    """한 쪽: expected = 그 쪽의 태그 단위(지도 차례). out 은 단위 번호(id) → 붙인 결과."""
    unplaced, warnings = placed.unplaced, placed.warnings
    position = {str(u["tag"]): k for k, u in enumerate(expected)}
    got: list[tuple[int, str, str]] = []  # (지도 자리, 태그, 몸 글)
    seen: set[str] = set()
    shifted_from: int | None = None
    shift_kind = ""
    for section in split_page_sections(normalize_structured_tags(content)):
        head = section.lines[0] if section.lines else ""
        label = _label(head) if section.kind != "TEXT" else None
        if section.kind == "PAGE" or label is None:
            rest = _section_text(section.lines[1:] if section.kind == "PAGE" else section.lines)
            if rest:
                unplaced.append({"page": page, "text": rest})
                warnings.append({"code": "tag_extra", "page": page, "tag": None})
            continue
        body = _section_text(section.lines[1:])
        whole = _section_text(section.lines)
        if shifted_from is not None:
            unplaced.append({"page": page, "text": whole})
            continue
        if label not in position or label in seen:
            unplaced.append({"page": page, "text": whole})
            warnings.append({"code": "tag_extra", "page": page, "tag": label})
            continue
        if got and position[label] < got[-1][0]:  # 차례가 뒤집혔다 — 여기부터는 번호를 믿지 않는다
            shifted_from = len(got)
            shift_kind = label.split()[0]
            unplaced.append({"page": page, "text": whole})
            warnings.append({"code": "tag_shift", "page": page, "tag": label})
            continue
        seen.add(label)
        got.append((position[label], label, body))
    have = {k for k, _, _ in got}
    missing = [k for k in range(len(expected)) if k not in have]
    if shifted_from is None and missing:  # 끊긴 태그 줄을 문단 수로 먼저 되살린다(차례 뒤집힘 길은 그대로)
        got, missing = _recover(page, expected, got, missing, placed)
        have = {k for k, _, _ in got}
    shifted: set[int] = set(missing) if shifted_from is not None else set()
    if shifted_from is not None:  # 뒤집힌 태그의 종류는 앞에서 붙은 단위도 글이 맞는지 되짚는다(당겨진 번호의 앞쪽)
        kept = _cut_unfit(page, expected, got, shift_kind, placed)
        shifted |= {k for k, _, _ in got} - {k for k, _, _ in kept}
        got = kept
        have = {k for k, _, _ in got}
    elif missing:
        kept = _drop_shifted(page, expected, got, missing, placed)
        shifted = {k for k, _, _ in got} - {k for k, _, _ in kept}
        if shifted:  # 당겨진 꼴: 그 종류의 빠진 단위도 같은 까닭(tag_shift 하나로 말한다)
            kinds = {str(expected[k]["tag"]).split()[0] for k in shifted}
            shifted |= {k for k in missing if str(expected[k]["tag"]).split()[0] in kinds}
        got = kept
        have = {k for k, _, _ in got}
    for k, unit in enumerate(expected):
        if k in have:
            continue
        out[id(unit)] = _missing(unit)
        if k not in shifted:
            warnings.append({"code": "tag_missing", "page": page, "tag": unit["tag"]})
    for k, label, body in got:
        unit = expected[k]
        if not body:
            out[id(unit)] = _missing(unit)
            warnings.append({"code": "tag_missing", "page": page, "tag": label})
            continue
        out[id(unit)] = _placed(unit, body)
        if not _ratio_ok(unit, body):
            warnings.append({"code": "length_ratio", "page": page, "tag": label})


def _drop_shifted(
    page: int,
    expected: Sequence[Mapping[str, Any]],
    got: list[tuple[int, str, str]],
    missing: Sequence[int],
    placed: Placed,
) -> list[tuple[int, str, str]]:
    """태그가 빠졌고 그 종류의 빠진 것이 모두 뒤쪽이면(번호가 당겨진 꼴과 겉모양이 같다) 그 종류의 붙은 단위를
    차례로 보며 처음으로 글이 맞지 않는 단위부터 번호로 붙이지 않는다(`tag_shift`). 글은 unplaced 로."""
    keep = list(got)
    for kind in {str(expected[k]["tag"]).split()[0] for k in missing}:
        mine = [g for g in keep if g[1].split()[0] == kind]
        lost = [k for k in missing if str(expected[k]["tag"]).split()[0] == kind]
        if not mine or min(lost) < max(g[0] for g in mine):
            continue  # 가운데가 빠졌을 뿐(뒤 번호는 제자리) — 그냥 빠짐
        keep = _cut_unfit(page, expected, keep, kind, placed, soft=kind != "TABLE")
    return keep


def _cut_unfit(
    page: int,
    expected: Sequence[Mapping[str, Any]],
    got: list[tuple[int, str, str]],
    kind: str,
    placed: Placed,
    *,
    soft: bool = False,
) -> list[tuple[int, str, str]]:
    """그 종류의 붙은 단위를 차례로 보며 처음으로 글이 맞지 않는 단위(`_fits`)부터 떼어 unplaced 로(`tag_shift`).
    soft(끝 번호만 빠진 길 — `_drop_shifted`): 문단 수·숫자 꼴만 다른 단위(`_loosely_fits`)는 떼지 않고 붙이되 그
    단위마다 tag_shift(엉뚱한 글일 수 있다고 알린다). 비율이 틀리거나 원문으로 설명 안 되는 숫자가 있는 첫 단위부터는
    그대로 뗀다. 한계(TRS6): 숫자 정규형이 같은 이웃 글(숫자 없음·같은 숫자)은 무른 길에서 가르지 못하고 경고만 단다.
    숫자를 글로 바꾼 번역(2위 → second)은 원문 쪽 숫자가 사라질 뿐이라 맞음으로 본다."""
    mine = [g for g in got if g[1].split()[0] == kind]
    bad: int | None = None
    for n, (k, label, body) in enumerate(mine):
        if _fits(expected[k], body):
            continue
        if soft and _loosely_fits(expected[k], body):
            placed.warnings.append({"code": "tag_shift", "page": page, "tag": label})
            continue
        bad = n
        break
    if bad is None:
        return got
    cut = mine[bad:]
    placed.warnings.append({"code": "tag_shift", "page": page, "tag": cut[0][1]})
    for _, label, body in cut:
        placed.unplaced.append({"page": page, "text": f"[{label}]\n{body}".strip()})
    return [g for g in got if g not in cut]


def place(units: Sequence[Mapping[str, Any]], page_texts: Mapping[int, str]) -> Placed:
    """머리말 place. 결과 units 는 지도 차례 그대로."""
    placed = Placed(units=[])
    out: dict[int, dict[str, Any]] = {}
    pages: dict[int, list[Mapping[str, Any]]] = {}
    for unit in units:
        if unit["tag"] is None:
            out[id(unit)] = {"tag": None, "page": unit["page"], "level": "source_only", "translations": None}
        else:
            pages.setdefault(int(unit["page"]), []).append(unit)
    for page, expected in pages.items():
        content = page_texts.get(page)
        if content is None:
            placed.warnings.append({"code": "page_missing", "page": page, "tag": None})
            for unit in expected:
                out[id(unit)] = _missing(unit)
            continue
        _place_page(page, expected, content, out, placed)
    for page in sorted(set(page_texts) - set(pages)):
        lines = page_texts[page].splitlines()
        text = _section_text(lines[1:] if lines and PAGE_TAG_LINE_RE.match(lines[0]) else lines)
        if text:
            placed.unplaced.append({"page": page, "text": text})
            placed.warnings.append({"code": "tag_extra", "page": page, "tag": f"PAGE {page}"})
    placed.units.extend(out[id(u)] for u in units)
    return placed
