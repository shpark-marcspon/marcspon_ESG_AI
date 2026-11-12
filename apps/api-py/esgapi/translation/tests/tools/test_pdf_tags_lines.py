"""PDF 입력 어댑터의 줄 묶기·단 넘김 잇기(tools/pdf_tags.py — 밴드 TRS5 경계 ①, sid:MARC-ISSUE-527). 순수: 파서·엔진
호출 0. 쪽은 지어낸 3단 쪽 하나의 꼴(쪽 폭 960 · 글자 7.7 · 줄 높이 8.8 · 줄 틈 5.1 · 문단 틈 10.8 · 단 x 164/423/682 ·
폭 240 — 좌표 꼴만 다단 공개 보고서를 본뜨고 글은 전부 지어낸 것).

L1 한 단 줄 다섯 → 멤버 하나(글 = 줄 글 공백 이음 · 상자 = 합 · id·key = 첫 줄) · 항등 place 는 block·경고 0.
L2 문단 틈·짧은 끝 줄 각각이 문단을 가른다. L3 끝까지 찬 줄이 마침표로 끝나도 틈이 좁으면 같은 문단.
L4 단 넘김: 끝까지 차고 문장이 안 끝난 단 끝 줄 → 다음 단 첫 줄이 같은 [BLOCK n] 의 새 멤버(상자가 단을
   가로지르지 않음) · 단 끝이 마침표면 새 [BLOCK n].
L5 가드: 서명 꼴 짧은 줄 넷은 [VISUAL] 그대로 · 라벨 문턱 미만 짧은 줄 셋은 줄마다 · 여러 줄 높이 블록 ·
   글자 크기 다른 줄.
L6 불변식: 묶인 줄이 단위에서 빠지면 PdfTagsError.
"""

import re
from typing import Any

import pytest

from esgapi.translation.engines.colab_158.pages import pages_to_map_merge, parse_pages
from esgapi.translation.tools import pdf_tags
from esgapi.translation.tools.pdf_tags import PdfTagsError, build, place

FONT = 7.7
LINE = 8.8
STEP = LINE + 5.1  # 줄 틈 5.1 = 0.66 × 글자
PARA = 10.8  # 문단 틈 = 1.40 × 글자
COLS = (164.0, 423.0, 682.0)
COL_W = 240.0
SHORT_END = 150.0  # 문단 끝 줄 — 폭은 넓지만(≥ LINE_MIN_WIDTH × 글자) 단 오른쪽 끝에서 멀다


def line(
    order: int,
    col: int,
    top: float,
    text: str,
    *,
    width: float = COL_W,
    font: float = FONT,
    height: float = LINE,
    kind: str = "paragraph",
) -> dict[str, Any]:
    x0 = COLS[col]
    return {
        "id": f"p1-b{order}",
        "page": 1,
        "order": order,
        "kind": kind,
        "bbox": [x0, top, x0 + width, top + height],
        "text": text,
        "font_size": font,
        "region": "body",
        "key": f"k01{order:02d}",
    }


def doc(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pages": [{"page": 1, "width": 960.0, "height": 595.0, "text_layer": "present"}],
        "blocks": blocks,
        "tables": [],
    }


def built(blocks: list[dict[str, Any]]) -> pdf_tags.Tagged:
    return build(doc(blocks), None, page_start=None, page_end=None)


def members(tagged: pdf_tags.Tagged) -> list[tuple[str, list[str]]]:
    return [(u["tag"], [m["id"] for m in u["members"]]) for u in tagged.units]


def paragraph(start: int, col: int, top: float, texts: list[str], *, last: float = SHORT_END) -> list[dict[str, Any]]:
    """한 문단: 줄마다 단 폭이 찬 줄, 끝 줄만 폭 last."""
    return [
        line(start + n, col, top + n * STEP, text, width=last if n == len(texts) - 1 else COL_W)
        for n, text in enumerate(texts)
    ]


LETTER = [
    "가상 회사의 올해 편지는 여러 줄로 이어지는",
    "긴 문단이며 파서가 줄 하나씩 블록으로 주었고",
    "어댑터가 같은 단의 이어진 줄을 한 문단으로",
    "묶어야 엔진이 문장을 온전히 받아 번역할 수",
    "있다.",
]


def page_map(text: str) -> dict[int, str]:
    return pages_to_map_merge(parse_pages(text))[0]


def tags_of(text: str) -> list[str]:
    return re.findall(r"(?m)^\[([A-Z]+(?: \d+)?)\]$", text)


# ── L1 ──


def test_l1_lines_of_one_paragraph_become_one_member() -> None:
    blocks = paragraph(1, 0, 100, LETTER)
    tagged = built(blocks)
    assert members(tagged) == [("BLOCK 1", ["p1-b1"])]
    (member,) = tagged.units[0]["members"]
    assert member["source"] == " ".join(LETTER)
    assert (member["id"], member["key"], member["kind"]) == ("p1-b1", "k0101", "paragraph")
    assert member["bbox"] == [COLS[0], 100, COLS[0] + COL_W, 100 + 4 * STEP + LINE]
    assert tagged.text == "[PAGE 1]\n\n[BLOCK 1]\n" + " ".join(LETTER) + "\n"
    placed = place(tagged.units, page_map(tagged.text))
    assert placed.warnings == [] and placed.unplaced == []
    assert (placed.units[0]["level"], placed.units[0]["translations"]) == ("block", [" ".join(LETTER)])


# ── L2·L3 ──


def test_l2_a_short_last_line_ends_the_paragraph() -> None:
    first = paragraph(1, 0, 100, LETTER[:2])  # 끝 줄 폭 150 — 단 끝에서 멀다
    second = paragraph(3, 0, 100 + 2 * STEP, LETTER[2:])  # 틈은 줄 틈 그대로
    tagged = built(first + second)
    assert members(tagged) == [("BLOCK 1", ["p1-b1", "p1-b3"])]


def test_l2_a_paragraph_gap_ends_the_paragraph() -> None:
    first = paragraph(1, 0, 100, [*LETTER[:1], "가상 문단의 끝 줄도 단 끝까지 찼다"], last=COL_W)  # 끝까지 참
    top = 100 + STEP + LINE + PARA  # 문단 틈 1.40 × 글자
    second = paragraph(3, 0, top, LETTER[2:])
    tagged = built(first + second)
    assert members(tagged) == [("BLOCK 1", ["p1-b1", "p1-b3"])]


def test_l3_a_full_line_ending_with_a_full_stop_still_joins_over_a_line_gap() -> None:
    texts = ["가상 문장이 줄 끝에서 마침표로 끝났다.", "같은 문단의 다음 문장이 이 줄에 온다."]
    tagged = built(paragraph(1, 0, 100, texts))
    assert members(tagged) == [("BLOCK 1", ["p1-b1"])]
    assert tagged.units[0]["members"][0]["source"] == " ".join(texts)


# ── L4 ──


def two_columns(end: str) -> list[dict[str, Any]]:
    """1단 문단(끝 줄이 끝까지 차고 글이 end 로 끝남) → 2단 위쪽 문단."""
    left = paragraph(1, 0, 400, [LETTER[0], LETTER[1] + end], last=COL_W)
    right = paragraph(3, 1, 120, LETTER[2:])
    return left + right


def test_l4_a_sentence_running_over_the_column_end_stays_in_the_block_as_a_new_member() -> None:
    tagged = built(two_columns(""))
    assert members(tagged) == [("BLOCK 1", ["p1-b1", "p1-b3"])]
    left, right = tagged.units[0]["members"]
    assert left["bbox"][2] <= COLS[1] and right["bbox"][0] >= COLS[1]  # 상자가 단을 가로지르는 멤버 0
    assert tagged.text == f"[PAGE 1]\n\n[BLOCK 1]\n{left['source']}\n\n{right['source']}\n"
    placed = place(tagged.units, page_map(tagged.text))
    assert placed.warnings == [] and placed.units[0]["level"] == "block"


def test_l4_a_column_ending_with_a_full_stop_opens_a_new_block() -> None:
    tagged = built(two_columns("."))
    assert members(tagged) == [("BLOCK 1", ["p1-b1"]), ("BLOCK 2", ["p1-b3"])]


def test_l4_a_short_column_end_opens_a_new_block() -> None:
    left = paragraph(1, 0, 400, LETTER[:2])  # 끝 줄 폭 150, 부호 없음
    tagged = built(left + paragraph(3, 1, 120, LETTER[2:]))
    assert members(tagged) == [("BLOCK 1", ["p1-b1"]), ("BLOCK 2", ["p1-b3"])]


# ── L5 가드 ──


def test_l5_a_signature_of_four_short_lines_stays_one_visual() -> None:
    lines = ["가상직함", "가상이름", "2030년 1월 2일", "가상회사"]
    blocks = [line(n + 1, 2, 480 + n * STEP, text, width=60) for n, text in enumerate(lines)]
    tagged = built(blocks)
    assert members(tagged) == [("VISUAL 1", ["p1-b1", "p1-b2", "p1-b3", "p1-b4"])]
    assert [m["source"] for m in tagged.units[0]["members"]] == lines


def test_l5_three_short_lines_below_the_label_run_stay_one_member_each() -> None:
    lines = ["가상 목차 하나", "가상 목차 둘", "가상 목차 셋"]  # 라벨 셋 < VISUAL_MIN_RUN — 글 묶음으로 돌아온다
    blocks = [line(n + 1, 0, 100 + n * STEP, text, width=60) for n, text in enumerate(lines)]  # 다 같이 끝까지 참
    tagged = built(blocks)
    assert members(tagged) == [("BLOCK 1", ["p1-b1", "p1-b2", "p1-b3"])]


def test_l5_multi_line_blocks_from_the_parser_stay_as_they_are() -> None:
    blocks = [
        line(1, 0, 100, "파서가 이미 묶은 가상 문단 하나는 여러 줄 높이다", height=3 * LINE),
        line(2, 0, 100 + 3 * LINE + 4.0, "파서가 이미 묶은 가상 문단 둘도 여러 줄 높이다", height=3 * LINE),
    ]
    assert members(built(blocks)) == [("BLOCK 1", ["p1-b1", "p1-b2"])]


def test_l5_a_line_of_another_font_size_does_not_join() -> None:
    blocks = [*paragraph(1, 0, 100, LETTER[:1], last=COL_W), line(2, 0, 100 + STEP, LETTER[1], font=9.0)]
    assert members(built(blocks)) == [("BLOCK 1", ["p1-b1", "p1-b2"])]


# ── L6 ──


def test_l6_a_joined_line_dropped_from_its_unit_breaks_the_build(monkeypatch: pytest.MonkeyPatch) -> None:
    real = pdf_tags._para_member  # pyright: ignore[reportPrivateUsage]

    def lossy(lines: Any) -> tuple[dict[str, Any], list[str]]:
        return real(lines[:-1] if len(lines) > 1 else lines)

    monkeypatch.setattr(pdf_tags, "_para_member", lossy)
    with pytest.raises(PdfTagsError):
        built(paragraph(1, 0, 100, LETTER))


def test_l6_every_line_lands_in_exactly_one_unit_once() -> None:
    blocks = two_columns("") + paragraph(10, 2, 120, LETTER)
    tagged = built(blocks)
    text = re.sub(r"\s+", "", "".join(m["source"] for u in tagged.units for m in u["members"]))
    assert sorted(text) == sorted(re.sub(r"\s+", "", "".join(b["text"] for b in blocks)))


# ── L8 가드 음성 시험(검증 권고 R1·R2) ──


def test_l8_a_first_line_lower_in_the_next_column_opens_a_new_block() -> None:
    left = paragraph(1, 0, 400, [LETTER[0], LETTER[1]], last=COL_W)  # 끝까지 참 · 부호 없음
    tagged = built(left + paragraph(3, 1, 500, LETTER[2:]))  # 옆 단이지만 아래쪽(캡션 꼴)
    assert members(tagged) == [("BLOCK 1", ["p1-b1"]), ("BLOCK 2", ["p1-b3"])]


def test_l8_a_first_line_of_another_font_size_in_the_next_column_opens_a_new_block() -> None:
    left = paragraph(1, 0, 400, [LETTER[0], LETTER[1]], last=COL_W)
    right = [line(3, 1, 120, LETTER[2], font=9.0)]
    assert members(built(left + right)) == [("BLOCK 1", ["p1-b1"]), ("BLOCK 2", ["p1-b3"])]


def test_l8_a_line_shifted_three_font_sizes_in_the_same_column_does_not_join() -> None:
    first = paragraph(1, 0, 100, LETTER[:1], last=COL_W)
    shift = 3 * FONT
    second = [
        line(2, 0, 100 + STEP, LETTER[1], width=COL_W - shift)
        | {"bbox": [COLS[0] + shift, 100 + STEP, COLS[0] + COL_W, 100 + STEP + LINE]}
    ]
    assert members(built(first + second)) == [("BLOCK 1", ["p1-b1", "p1-b2"])]


def test_l8_a_line_overlapping_the_line_above_does_not_join() -> None:
    first = paragraph(1, 0, 100, LETTER[:1], last=COL_W)
    second = [line(2, 0, 100 + 1.0, LETTER[1])]  # 틈 = −7.8 < −0.35 × 글자(겹쳐 찍힌 줄)
    assert members(built(first + second)) == [("BLOCK 1", ["p1-b1", "p1-b2"])]


def test_l8_lines_that_would_join_into_a_tag_line_stay_apart() -> None:
    blocks = [line(1, 0, 100, "[BLOCK"), line(2, 0, 100 + STEP, "2]")]  # 줄마다는 태그 꼴이 아니다
    tagged = built(blocks)
    assert members(tagged) == [("BLOCK 1", ["p1-b1", "p1-b2"])]
    assert "[BLOCK 2]" not in tagged.text.splitlines()


# ── T9 쪽을 덮는 표 낮추기(밴드 TRS6 2-6) ──


def grid_block(order: int, tid: str, bbox: list[float]) -> dict[str, Any]:
    return {"id": f"p1-b{order}", "page": 1, "order": order, "kind": "table", "bbox": bbox, "table_id": tid}


def sparse_cells(filled: int, long: int) -> list[list[str]]:
    """13×4 격자 — 첫 열 13칸 + 첫 행에서 오른쪽으로 채워 filled 칸, 6행 첫 칸만 long 자 글(본문을 삼킨 꼴)."""
    cells = [[""] * 4 for _ in range(13)]
    spots = [(r, 0) for r in range(13)] + [(r, c) for r in range(13) for c in range(1, 4)]
    for n, (r, c) in enumerate(spots[:filled]):
        cells[r][c] = f"가상 칸 {n + 1}"
    cells[5][0] = ("가상 본문 문장이 표 칸 안으로 들어왔다. " * 30)[:long].strip()
    return cells


def covering(bbox: list[float], filled: int = 15, long: int = 400) -> tuple[pdf_tags.Tagged, list[list[str]]]:
    """쪽을 덮는 표(p1-t1) · 그 안의 작은 표(p1-t2) · 같은 쪽 보통 자료표(p1-t3)."""
    big = sparse_cells(filled, long)
    tables = [
        {"id": "p1-t1", "page": 1, "bbox": bbox, "cells": big, "footnote_marks": []},
        {"id": "p1-t2", "page": 1, "bbox": [200, 100, 400, 160], "cells": [["가상", "1"], ["가상 둘", "2"]]},
        {"id": "p1-t3", "page": 1, "bbox": [100, 565, 500, 590], "cells": [["구분", "2025"], ["가상항목", "1,100"]]},
    ]
    blocks = [
        grid_block(1, "p1-t1", bbox),
        grid_block(2, "p1-t2", [200, 100, 400, 160]),
        grid_block(3, "p1-t3", [100, 565, 500, 590]),
    ]
    document = doc(blocks) | {"tables": tables}
    return build(document, None, page_start=None, page_end=None), big


def test_t9_a_table_covering_the_page_is_demoted_to_text_cells() -> None:
    tagged, big = covering([100, 30, 900, 560])  # 넓이 0.74 · 채움 15/52 = 0.29 · 긴 칸 400
    assert tags_of(tagged.text) == ["PAGE 1", "BLOCK 1", "TABLE 1", "TABLE 2"]
    cells = [f"p1-t1:r{r}c{c}" for r, row in enumerate(big) for c, text in enumerate(row) if text.strip()]
    assert members(tagged) == [("BLOCK 1", cells), ("TABLE 1", ["p1-t2"]), ("TABLE 2", ["p1-t3"])]
    assert tagged.notes == [{"code": "table_demoted", "page": 1, "table": "p1-t1"}]
    placed = place(tagged.units, page_map(tagged.text))
    assert [u["level"] for u in placed.units] == ["block", "cell", "cell"]
    assert placed.warnings == [] and placed.unplaced == []


@pytest.mark.parametrize(
    ("bbox", "filled", "long"),
    [([100, 30, 900, 380], 15, 400), ([100, 30, 900, 560], 21, 400), ([100, 30, 900, 560], 15, 299)],
    ids=["area-0.49", "fill-0.40+", "cell-299"],
)
def test_t9_a_table_just_below_any_threshold_stays_a_table(bbox: list[float], filled: int, long: int) -> None:
    tagged, _ = covering(bbox, filled, long)
    assert tags_of(tagged.text) == ["PAGE 1", "TABLE 1", "TABLE 2", "TABLE 3"]
    assert tagged.notes == []


# ── T10 여러 줄 블록 나누기(밴드 TRS6 2-5) ──

LISTED = "가상 관리 : 가상 설비를 점검한다 가상 교육 : 가상 직원을 가르친다 가상 보고 : 가상 결과를 알린다"
RUNNING = "가상 문단은 끝까지 찬 줄로 이어지고 - 다음 줄에서 끝난다."


def run(text: str, at: str, top: float, x0: float, x1: float) -> dict[str, Any]:
    return {"start": text.index(at), "y0": top, "y1": top + LINE, "x0": [x0, x0 + 6.0], "x1": [x0 + 5.0, x1]}


def multi(order: int, col: int, text: str, lines: int) -> dict[str, Any]:
    return line(order, col, 100, text, height=(lines - 1) * STEP + LINE)


def listed_places(first: Any = None) -> dict[str, Any]:
    left, right = COLS[0], COLS[1]
    listed = [
        run(LISTED, "가상 관리", 100, left, 250),
        run(LISTED, "가상 설비", 100.4, 252, 330) | {"y1": 100.4 + LINE},  # 같은 인쇄 줄의 둘째 run(글꼴 바뀜)
        run(LISTED, "가상 교육", 100 + STEP, left, 340),
        run(LISTED, "가상 보고", 100 + 2 * STEP, left, 320),
    ]
    if first is not None:
        listed[0] = listed[0] | {"start": first}
    running = [run(RUNNING, "가상 문단", 100, right, right + COL_W), run(RUNNING, "- 다음", 100 + STEP, right, 520)]
    boxes = {"p1-b1": [left, 100, left + COL_W, 136.6], "p1-b2": [right, 100, right + COL_W, 122.7]}
    return {"containers": [{"id": i, "bbox": boxes[i], "runs": r} for i, r in [("p1-b1", listed), ("p1-b2", running)]]}


def test_t10_a_listed_block_is_split_on_its_printed_lines() -> None:
    blocks = [multi(1, 0, LISTED, 3), multi(2, 1, RUNNING, 2), multi(3, 2, RUNNING, 2)]
    tagged = build(doc(blocks), listed_places(), page_start=None, page_end=None)
    assert members(tagged) == [
        ("BLOCK 1", ["p1-b1", "p1-b1:l1", "p1-b1:l2"]),  # 첫 줄의 run 둘은 한 줄 — 갈리지 않음
        ("BLOCK 2", ["p1-b2"]),  # 끝까지 찬 줄 뒤는 불릿 꼴이어도 그대로
        ("BLOCK 3", ["p1-b3"]),  # runs 없음
    ]
    first = tagged.units[0]["members"]
    assert " ".join(m["source"] for m in first) == LISTED
    assert [m["key"] for m in first] == ["k0101", None, None]
    assert tagged.notes == []
    placed = place(tagged.units, page_map(tagged.text))
    assert [u["level"] for u in placed.units] == ["block"] * 3
    assert placed.units[0]["translations"] == [m["source"] for m in first]
    assert placed.warnings == []


def test_t10_runs_that_do_not_match_the_text_leave_the_block_whole() -> None:
    tagged = build(doc([multi(1, 0, LISTED, 3)]), listed_places(first=3), page_start=None, page_end=None)
    assert members(tagged) == [("BLOCK 1", ["p1-b1"])]
    assert tagged.notes == [{"code": "runs_mismatch", "page": 1, "block": "p1-b1"}]


# ── T11 이중 블록 접기(밴드 TRS6 2-7 · MARC-ISSUE-612 a) ──


def twin_heading(shift: float, text: str = "1. 가상 개요") -> list[dict[str, Any]]:
    first = line(1, 0, 80, "1. 가상 개요", kind="heading", width=120)
    second = line(2, 0, 80, text, kind="heading", width=120)
    second["bbox"] = [x + shift for x in second["bbox"]]
    return [first, second, multi(3, 0, LETTER[0] + " " + LETTER[1], 2) | {"bbox": [164, 100, 404, 122.7]}]


def test_t11_a_block_drawn_twice_in_the_same_place_is_placed_once() -> None:
    tagged = built(twin_heading(0.6))
    assert members(tagged) == [("BLOCK 1", ["p1-b1", "p1-b3"])]
    assert tagged.text.count("1. 가상 개요") == 1
    assert tagged.notes == [{"code": "block_folded", "page": 1, "block": "p1-b2", "into": "p1-b1"}]
    placed = place(tagged.units, page_map(tagged.text))
    assert [u["level"] for u in placed.units] == ["block"] and placed.warnings == []


@pytest.mark.parametrize(
    ("shift", "text"), [(1.5, "1. 가상 개요"), (0.0, "1-1. 가상 개요")], ids=["moved", "other-text"]
)
def test_t11_a_twin_off_by_more_than_a_point_or_with_other_text_stays(shift: float, text: str) -> None:
    tagged = built(twin_heading(shift, text))
    assert members(tagged) == [("BLOCK 1", ["p1-b1"]), ("BLOCK 2", ["p1-b2", "p1-b3"])]
    assert tagged.notes == []


@pytest.mark.parametrize("count", [4, 2], ids=["four-drawn-eight", "two-drawn-four"])
def test_t11_labels_drawn_twice_keep_their_visual_with_each_label_once(count: int) -> None:
    """겹친 라벨 넷(그린 수 여덟): VISUAL 문턱은 접기 전 그린 수로 세므로 VISUAL 그대로(감독 11-10), 멤버는 넷.
    겹친 라벨 둘(그린 수 넷 — BASE 에서 VISUAL)도 VISUAL 그대로, 멤버 둘."""
    blocks: list[dict[str, Any]] = []
    for n in range(count):
        for again in range(2):
            label = line(len(blocks) + 1, 0, 100 + n * 20, f"가상 {n + 1}", width=40)
            label["bbox"] = [x + 0.3 * again for x in label["bbox"]]
            blocks.append(label)
    tagged = built(blocks)
    assert members(tagged) == [("VISUAL 1", [f"p1-b{2 * n + 1}" for n in range(count)])]
    assert [n["block"] for n in tagged.notes] == [f"p1-b{2 * n + 2}" for n in range(count)]
