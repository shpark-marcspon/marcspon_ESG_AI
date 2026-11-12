"""PDF 입력 어댑터(tools/pdf_tags.py — 밴드 TRD2 A1·A2·A3). 순수: 파서·엔진 호출 0, 문서는 지어낸 dict(docparse
분해 판 2 의 꼴 — 글·회사는 전부 지어낸 것).

A1 build: 태그 차례 · 블록·칸 글이 단위에 꼭 한 번 · 빈 표 건넘 · pipe 행 → 원 행 번호 · [VISUAL] 문턱 양쪽 ·
   같은 단 문단 뒤 제목이 새 묶음 · 머리글·꼬리말은 태그 글 밖·지도에 원문 · 원문 줄이 태그 꼴이면 예외 ·
   서명 꼴 짧은 줄 넷은 [VISUAL] 하나지만 줄마다 제 글(고치지 않음 — MARC-ISSUE-428).
A2 place 되돌림: 번역 = 원문(항등)이면 머리글·꼬리말 밖 단위는 모두 block/cell, 머리글·꼬리말은 source_only, 경고 0.
A3 place 흔듦: 문단 합침 group · 표 행 뺌·pipe 밖 줄 table · 태그 지움 missing · 번호 바꿈·겹침 unplaced ·
   쪽 지움 page_missing · 가운데 태그를 지워 번호가 당겨진 꼴 tag_shift(차례 뒤집힘 길·같은 종류 끝 빠짐 길 — 뒤
   단위가 엉뚱한 글을 받지 않음) · 길이 비율 밖 length_ratio ·
   언제나 번역 글자가 단위 번역 + unplaced 에 다 있다 ·
   태그·덩이 맞바꿈 흔듦 300번: 글 잃음 0, 엉뚱한 글은 늘 경고와 함께(고치지 않음 — MARC-ISSUE-428).
"""

import copy
import random
import re
from collections import Counter
from collections.abc import Callable
from typing import Any

import pytest

from esgapi.translation.engines.colab_158.pages import pages_to_map_merge, parse_pages
from esgapi.translation.tools import pdf_tags
from esgapi.translation.tools.pdf_tags import PdfTagsError, SourceTagLine, build, paragraphs, place

W, H = 600.0, 800.0


def block(
    page: int, order: int, text: str, bbox: list[float], kind: str = "paragraph", region: str = "body"
) -> dict[str, Any]:
    return {
        "id": f"p{page}-b{order}",
        "page": page,
        "order": order,
        "kind": kind,
        "bbox": bbox,
        "text": text,
        "font_size": 9.0,
        "region": region,
        "key": f"k{page:02d}{order:02d}",
    }


def table_block(page: int, order: int, tid: str, bbox: list[float]) -> dict[str, Any]:
    return {
        "id": f"p{page}-b{order}",
        "page": page,
        "order": order,
        "kind": "table",
        "bbox": bbox,
        "table_id": tid,
        "region": "body",
        "key": f"t{page:02d}{order:02d}",
    }


def table(tid: str, page: int, cells: list[list[str]], marks: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"id": tid, "page": page, "cells": cells, "footnote_marks": marks or []}


def page_meta(page: int, layer: str = "present") -> dict[str, Any]:
    return {"page": page, "width": W, "height": H, "text_layer": layer}


def document() -> dict[str, Any]:
    """1쪽: 머리글 · 제목 + 문단 둘(왼 단) · 문단(오른 단) · 표(빈 행·`|`·각주 표시) · 꼬리말.
    2쪽: 도표 라벨 넷 + 제목 + 문단 · 빈 바깥 표. 3쪽: 글자 층 없음."""
    blocks = [
        block(1, 1, "Synthetic report header", [40, 20, 300, 30], region="header"),
        block(1, 2, "Water stewardship", [40, 80, 280, 96], kind="heading"),
        block(1, 3, "가상 사업장은 물 사용량을 매년 줄였다.", [40, 100, 280, 140]),
        block(1, 4, "재이용률은 지난해보다 올랐다.", [40, 150, 280, 180]),
        block(1, 5, "오른쪽 단의 문단은 따로 묶인다.", [320, 100, 560, 140]),
        table_block(1, 6, "p1-t1", [40, 200, 560, 300]),
        block(1, 7, "7", [290, 760, 300, 770], region="footer"),
        block(2, 1, "2023", [40, 100, 70, 110]),
        block(2, 2, "2024", [80, 100, 110, 110]),
        block(2, 3, "12.5", [40, 120, 70, 130]),
        block(2, 4, "13.1", [80, 120, 110, 130]),
        block(2, 5, "Energy use", [40, 200, 280, 216], kind="heading"),
        block(2, 6, "가상 에너지 사용량은 늘었지만 원단위는 줄었다.", [40, 220, 280, 260]),
        table_block(2, 7, "p2-t1", [40, 300, 560, 400]),
    ]
    tables = [
        table(
            "p1-t1",
            1,
            [["구분", "2024", "2025"], ["", "", ""], ["취수량|합계", "1,200", "1,100"], ["재이용", "30", "35"]],
            [{"row": 2, "col": 1, "mark": "1)"}],
        ),
        table("p2-t1", 2, [["", ""], ["", ""]]),
    ]
    places = {"containers": [{"id": "p1-t1:r2c1", "bbox": [300, 240, 340, 250]}]}
    pages = [page_meta(1), page_meta(2), page_meta(3, "none")]
    return {"document": {"pages": pages, "blocks": blocks, "tables": tables}, "places": places}


def built() -> pdf_tags.Tagged:
    data = document()
    return build(data["document"], data["places"], page_start=None, page_end=None)


def page_map(text: str) -> dict[int, str]:
    return pages_to_map_merge(parse_pages(text))[0]


def tags_of(text: str) -> list[str]:
    return re.findall(r"(?m)^\[([A-Z]+(?: \d+)?)\]$", text)


# ── A1 build ──


def test_a1_tags_follow_the_reading_order_per_page() -> None:
    tagged = built()
    assert tags_of(tagged.text) == ["PAGE 1", "BLOCK 1", "BLOCK 2", "TABLE 1", "PAGE 2", "VISUAL 1", "BLOCK 1"]
    units = [(u["page"], u["tag"], u["kind"], [m["id"] for m in u["members"]]) for u in tagged.units]
    assert units == [
        (1, "BLOCK 1", "block", ["p1-b2", "p1-b3", "p1-b4"]),  # 제목이 연 묶음
        (1, "BLOCK 2", "block", ["p1-b5"]),  # 가로 겹침 0 — 단이 바뀜
        (1, "TABLE 1", "table", ["p1-t1"]),
        (1, None, "header", ["p1-b1"]),
        (1, None, "footer", ["p1-b7"]),
        (2, "VISUAL 1", "visual", ["p2-b1", "p2-b2", "p2-b3", "p2-b4"]),
        (2, "BLOCK 1", "block", ["p2-b5", "p2-b6"]),
    ]
    assert tagged.pages == [
        {"page": 1, "width": W, "height": H, "textLayer": "present"},
        {"page": 2, "width": W, "height": H, "textLayer": "present"},
        {"page": 3, "width": W, "height": H, "textLayer": "none"},
    ]


def test_a1_header_and_footer_stay_out_of_the_tagged_text() -> None:
    tagged = built()
    assert "Synthetic report header" not in tagged.text
    side = [u for u in tagged.units if u["tag"] is None]
    assert [m["source"] for u in side for m in u["members"]] == ["Synthetic report header", "7"]


def test_a1_empty_tables_and_image_pages_are_skipped() -> None:
    tagged = built()
    assert tagged.skipped == {"emptyTables": ["p2-t1"], "imageOnlyPages": [3]}
    assert tagged.warnings == [{"code": "image_only_page", "page": 3, "tag": None}]
    assert "[PAGE 3]" not in tagged.text


def test_a1_table_rows_map_back_over_the_dropped_empty_row() -> None:
    unit = next(u for u in built().units if u["kind"] == "table")
    assert unit["rows"] == [0, 2, 3]  # pipe 행 0·1·2 → 원 행(빈 행 1 은 엔진 함수가 버린다)
    cell = next(c for c in unit["cells"] if c["id"] == "p1-t1:r2c1")
    assert (cell["source"], cell["bbox"]) == ("1,2001)", [300, 240, 340, 250])  # 각주 표시는 칸 글 뒤
    assert next(c for c in unit["cells"] if c["id"] == "p1-t1:r3c0")["bbox"] is None
    assert "취수량&#124;합계" in unit["members"][0]["source"]


def test_a1_a_row_the_engine_keeps_as_a_line_break_keeps_its_row_number() -> None:
    blocks = [table_block(1, 1, "p1-t1", [40, 100, 560, 200])]
    tables = [table("p1-t1", 1, [["구분", "2024"], ["\n", ""], ["취수량", "1,200"]])]
    tagged = build({"pages": [page_meta(1)], "blocks": blocks, "tables": tables}, None, page_start=None, page_end=None)
    assert tagged.units[0]["rows"] == [0, 1, 2]  # 엔진은 줄바꿈뿐인 칸을 <br> 행으로 남긴다
    placed = place(tagged.units, page_map(tagged.text))
    assert {(c["row"], c["col"]): c["text"] for c in placed.units[0]["cells"]}[(2, 1)] == "1,200"


def test_a1_every_text_lands_in_exactly_one_unit() -> None:
    tagged = built()
    data = document()
    want = sorted(
        [b["id"] for b in data["document"]["blocks"] if b["kind"] != "table"]
        + [
            f"{t['id']}:r{i}c{j}"
            for t in data["document"]["tables"]
            for i, r in enumerate(t["cells"])
            for j, c in enumerate(r)
            if c
        ]
    )
    got = sorted(
        [c["id"] for u in tagged.units if u["kind"] == "table" for c in u["cells"]]
        + [m["id"] for u in tagged.units if u["kind"] != "table" for m in u["members"]]
    )
    assert got == want


def test_a1_a_dropped_block_breaks_the_build(monkeypatch: pytest.MonkeyPatch) -> None:
    real = pdf_tags._Page.emit  # pyright: ignore[reportPrivateUsage]

    def lossy(self: Any, kind: Any, blocks: Any) -> None:
        real(self, kind, blocks[:-1] if len(blocks) > 1 else blocks)

    monkeypatch.setattr(pdf_tags._Page, "emit", lossy)  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(PdfTagsError):
        built()


@pytest.mark.parametrize("line", ["[PAGE 3]", "**[PAGE 3]**", "[BLOCK 2]", "  [table 1]  "])
def test_a1_a_source_line_that_looks_like_a_tag_is_refused(line: str) -> None:
    data = document()
    data["document"]["blocks"][2]["text"] = f"앞 줄\n{line}"
    with pytest.raises(SourceTagLine):
        build(data["document"], data["places"], page_start=None, page_end=None)


def test_a1_visual_threshold_on_both_sides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf_tags, "VISUAL_MIN_RUN", 5)
    assert "VISUAL" not in " ".join(tags_of(built().text))  # 넷 < 다섯 — 글 묶음으로
    monkeypatch.setattr(pdf_tags, "VISUAL_MIN_RUN", 4)
    monkeypatch.setattr(pdf_tags, "VISUAL_MAX_CHARS", 3)
    assert "VISUAL" not in " ".join(tags_of(built().text))  # 「2023」 4자 > 3


def test_a1_a_signature_block_is_one_visual_with_each_line_placed() -> None:
    """고치지 않음 — sid:MARC-ISSUE-428 처분: 서명 꼴 짧은 줄 넷은 도표 라벨과 가를 신호가 없어 [VISUAL] 하나다(세로 한
    단을 빼면 실제 VISUAL 300 중 140 이 흔들린다). 영향은 상자 이름뿐 — 줄마다 제 글이 붙고 경고가 없다."""
    lines = ["가상직함", "가상이름", "2030년 1월 2일", "가상회사"]
    blocks = [block(1, n + 1, line, [40, 100 + n * 20, 200, 116 + n * 20]) for n, line in enumerate(lines)]
    tagged = build({"pages": [page_meta(1)], "blocks": blocks, "tables": []}, None, page_start=None, page_end=None)
    assert tags_of(tagged.text) == ["PAGE 1", "VISUAL 1"]
    assert [m["source"] for m in tagged.units[0]["members"]] == lines
    placed = place(tagged.units, page_map(tagged.text))
    assert placed.warnings == [] and placed.unplaced == []
    assert level(placed, 1, "VISUAL 1") == "block"
    assert placed.units[0]["translations"] == lines


def test_a1_a_heading_after_a_paragraph_in_the_same_column_opens_a_new_block() -> None:
    pages = [page_meta(1)]
    blocks = [
        block(1, 1, "가상 문단이 먼저 온다.", [40, 100, 280, 140]),
        block(1, 2, "Next topic", [40, 150, 280, 166], kind="heading"),
        block(1, 3, "제목 뒤 문단은 제목과 묶인다.", [40, 170, 280, 200]),
    ]
    tagged = build({"pages": pages, "blocks": blocks, "tables": []}, None, page_start=None, page_end=None)
    assert [(u["tag"], [m["id"] for m in u["members"]]) for u in tagged.units] == [
        ("BLOCK 1", ["p1-b1"]),
        ("BLOCK 2", ["p1-b2", "p1-b3"]),  # 가로 겹침 1 — 제목만이 묶음을 연다
    ]


def test_a1_the_page_range_limits_the_pages() -> None:
    data = document()
    tagged = build(data["document"], data["places"], page_start=2, page_end=2)
    assert tags_of(tagged.text) == ["PAGE 2", "VISUAL 1", "BLOCK 1"]
    assert {u["page"] for u in tagged.units} == {2}


# ── A2 place 되돌림 ──


def test_a2_identity_places_every_unit() -> None:
    tagged = built()
    placed = place(tagged.units, page_map(tagged.text))
    assert placed.unplaced == [] and placed.warnings == []
    levels = [(u["tag"], u["level"]) for u in placed.units]
    assert levels == [
        ("BLOCK 1", "block"),
        ("BLOCK 2", "block"),
        ("TABLE 1", "cell"),
        (None, "source_only"),
        (None, "source_only"),
        ("VISUAL 1", "block"),
        ("BLOCK 1", "block"),
    ]
    first = placed.units[0]["translations"]
    assert first == ["Water stewardship", "가상 사업장은 물 사용량을 매년 줄였다.", "재이용률은 지난해보다 올랐다."]
    cells = {(c["row"], c["col"]): c["text"] for c in placed.units[2]["cells"]}
    assert cells[(2, 0)] == "취수량|합계" and cells[(2, 1)] == "1,2001)" and (1, 0) not in cells


# ── A3 place 흔듦 ──


def shaken(edit: Any) -> tuple[pdf_tags.Tagged, pdf_tags.Placed, dict[int, str]]:
    tagged = built()
    pages = page_map(tagged.text)
    edit(pages)
    return tagged, place(tagged.units, pages), pages


def codes(placed: pdf_tags.Placed) -> list[tuple[str, int, str | None]]:
    return [(w["code"], w["page"], w["tag"]) for w in placed.warnings]


def level(placed: pdf_tags.Placed, page: int, tag: str) -> str:
    return next(u["level"] for u in placed.units if u["page"] == page and u["tag"] == tag)


def keeps_every_char(pages: dict[int, str], placed: pdf_tags.Placed) -> None:
    """번역 글의 태그 밖 글자가 단위 번역·칸·unplaced 에 다 있다(공백 무시, 머리 태그 줄 뺌)."""

    def squeeze(text: str) -> str:
        text = re.sub(r"(?m)^\[[A-Z]+(?: \d+)?\]$", "", text)
        return "".join(ch for ch in text.replace("&#124;", "|") if not ch.isspace() and ch not in "|-")

    have = "".join(squeeze(p) for p in pages.values())
    got = "".join(
        squeeze("".join(u["translations"] or []) + "".join(c["text"] for c in u.get("cells", []))) for u in placed.units
    ) + "".join(squeeze(x["text"]) for x in placed.unplaced)
    assert sorted(have) == sorted(got)


def test_a3_merged_paragraphs_fall_back_to_a_group() -> None:
    def edit(pages: dict[int, str]) -> None:
        pages[1] = pages[1].replace("매년 줄였다.\n\n재이용률", "매년 줄였다. 재이용률")

    _, placed, pages = shaken(edit)
    assert level(placed, 1, "BLOCK 1") == "group"
    keeps_every_char(pages, placed)


def test_a3_a_dropped_table_row_falls_back_to_the_table() -> None:
    def edit(pages: dict[int, str]) -> None:
        pages[1] = pages[1].replace("| 재이용 | 30 | 35 |\n", "").replace("\n| 재이용 | 30 | 35 |", "")

    _, placed, pages = shaken(edit)
    assert level(placed, 1, "TABLE 1") == "table"
    keeps_every_char(pages, placed)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("| 재이용 | 30 | 35 |", "| 재이용 | 30 | 35 |\n주: 가상 주석 한 줄"),  # 표 뒤 주석
        ("[TABLE 1]\n", "[TABLE 1]\n가상 표 캡션\n"),  # 표 머리 캡션
    ],
    ids=["note_after", "caption_before"],
)
def test_a3_a_line_outside_the_pipe_rows_keeps_the_table_whole(old: str, new: str) -> None:
    def edit(pages: dict[int, str]) -> None:
        pages[1] = pages[1].replace(old, new)

    _, placed, pages = shaken(edit)
    assert level(placed, 1, "TABLE 1") == "table"  # 칸으로 나누면 pipe 밖 줄이 사라진다
    keeps_every_char(pages, placed)


def test_a3_a_removed_last_tag_is_missing() -> None:
    def edit(pages: dict[int, str]) -> None:
        pages[2] = pages[2].split("\n[BLOCK 1]")[0]

    _, placed, pages = shaken(edit)
    assert level(placed, 2, "BLOCK 1") == "missing"
    assert ("tag_missing", 2, "BLOCK 1") in codes(placed)
    keeps_every_char(pages, placed)


def test_a3_unknown_and_repeated_tags_are_unplaced() -> None:
    def edit(pages: dict[int, str]) -> None:
        pages[2] = pages[2] + "\n\n[BLOCK 9]\nstray\n\n[VISUAL 1]\nagain"

    _, placed, pages = shaken(edit)
    assert [x["text"] for x in placed.unplaced] == ["[BLOCK 9]\nstray", "[VISUAL 1]\nagain"]
    assert codes(placed) == [("tag_extra", 2, "BLOCK 9"), ("tag_extra", 2, "VISUAL 1")]
    assert level(placed, 2, "VISUAL 1") == "block"
    keeps_every_char(pages, placed)


def test_a3_a_removed_page_is_page_missing() -> None:
    def edit(pages: dict[int, str]) -> None:
        del pages[2]

    _, placed, pages = shaken(edit)
    assert codes(placed) == [("page_missing", 2, None)]
    assert {u["level"] for u in placed.units if u["page"] == 2} == {"missing"}
    keeps_every_char(pages, placed)


def test_a3_a_middle_tag_removed_and_renumbered_is_a_shift() -> None:
    """1쪽 BLOCK 2 의 태그 줄을 지우고(글은 BLOCK 1 끝에 붙음) 뒤 번호를 당긴 꼴: 그 뒤 단위는 번호로 붙지 않는다."""

    def edit(pages: dict[int, str]) -> None:
        pages[1] = pages[1].replace("\n[BLOCK 2]\n", "\n")

    data = document()
    data["document"]["blocks"].insert(6, block(1, 8, "셋째 묶음은 뒤에 온다.", [40, 320, 280, 340], kind="heading"))
    tagged = build(data["document"], data["places"], page_start=None, page_end=None)
    assert tags_of(tagged.text)[:5] == ["PAGE 1", "BLOCK 1", "BLOCK 2", "TABLE 1", "BLOCK 3"]
    pages = page_map(tagged.text)
    edit(pages)
    pages[1] = pages[1].replace("[BLOCK 3]", "[BLOCK 2]")
    placed = place(tagged.units, pages)
    assert ("tag_shift", 1, "BLOCK 1") in codes(placed)
    shifted = [u for u in placed.units if u["page"] == 1 and u["tag"] in ("BLOCK 1", "BLOCK 2", "BLOCK 3")]
    assert {u["level"] for u in shifted} == {"missing"}  # 셋째 묶음 글이 BLOCK 2 에 붙지 않는다
    assert level(placed, 1, "TABLE 1") == "cell"
    keeps_every_char(pages, placed)


def same_kinds_document() -> dict[str, Any]:
    """1쪽: 제목 + 문단 묶음 셋(같은 단, 숫자만 다름) · 같은 모양 표 둘(숫자만 다름). 종류 사이 차례 뒤집힘이 없다."""
    blocks: list[dict[str, Any]] = []
    for n in range(3):
        top = 80 + n * 60
        blocks.append(block(1, 2 * n + 1, f"Site {n + 1}", [40, top, 280, top + 16], kind="heading"))
        blocks.append(block(1, 2 * n + 2, f"가상 사업장은 {n + 1}{n + 1}0 톤을 줄였다.", [40, top + 20, 280, top + 50]))
    blocks += [table_block(1, 7, "p1-t1", [40, 300, 560, 360]), table_block(1, 8, "p1-t2", [40, 380, 560, 440])]
    tables = [
        table("p1-t1", 1, [["구분", "2024"], ["취수량", "1,200"]]),
        table("p1-t2", 1, [["구분", "2025"], ["취수량", "1,100"]]),
    ]
    return {"pages": [page_meta(1)], "blocks": blocks, "tables": tables}


@pytest.mark.parametrize(
    ("kind", "count", "later"),
    [("BLOCK", 3, ["BLOCK 1", "BLOCK 2", "BLOCK 3"]), ("TABLE", 2, ["TABLE 1", "TABLE 2"])],
)
def test_a3_a_first_tag_of_one_kind_removed_and_renumbered_is_a_shift(kind: str, count: int, later: list[str]) -> None:
    """같은 종류만 이어진 쪽에서 그 종류 첫 태그 줄을 지우고(글은 앞 칸에 붙음) 뒤 번호를 당긴 꼴(차례 뒤집힘 없음):
    빠진 것이 끝 번호로만 보이고 문단 수·표 모양도 같아도, 뒤 단위는 엉뚱한 글을 받지 않는다(숫자 덩이로 가른다)."""
    tagged = build(same_kinds_document(), None, page_start=None, page_end=None)
    assert tags_of(tagged.text) == ["PAGE 1", "BLOCK 1", "BLOCK 2", "BLOCK 3", "TABLE 1", "TABLE 2"]
    pages = page_map(tagged.text)
    pages[1] = pages[1].replace(f"\n[{kind} 1]\n", "\n")
    for n in range(2, count + 1):
        pages[1] = pages[1].replace(f"[{kind} {n}]", f"[{kind} {n - 1}]")
    placed = place(tagged.units, pages)
    assert any(c[0] == "tag_shift" for c in codes(placed))
    assert {level(placed, 1, tag) for tag in later} == {"missing"}
    keeps_every_char(pages, placed)


SHAKES = 300
WARNED = {"tag_shift", "tag_extra", "tag_missing", "length_ratio"}
TAG_LINE = re.compile(r"(?m)^(\[[A-Z]+ \d+\])$")


def lookalike_document() -> dict[str, Any]:
    """쪽 둘: 같은 모양 묶음(숫자까지 같은 둘 + 숫자 다른 하나) · 같은 모양 표 둘. 숫자까지 같으면 번호로 못 가른다."""
    blocks: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    for page in (1, 2):
        names = ["갑", "을", "병"]
        amounts = [110, 110, 220 + page]
        for n, (name, amount) in enumerate(zip(names, amounts, strict=True)):
            top = 80 + n * 60
            blocks.append(block(page, 2 * n + 1, f"Site {name}", [40, top, 280, top + 16], kind="heading"))
            sentence = f"가상 사업장 {name}{page}은 {amount} 톤을 줄였다."
            blocks.append(block(page, 2 * n + 2, sentence, [40, top + 20, 280, top + 50]))
        for n, tid in enumerate((f"p{page}-t1", f"p{page}-t2")):
            blocks.append(table_block(page, 7 + n, tid, [40, 300 + n * 80, 560, 360 + n * 80]))
            tables.append(table(tid, page, [["구분", "2024"], [f"가상항목{page}{n}", "1,200"]]))
    return {"pages": [page_meta(1), page_meta(2)], "blocks": blocks, "tables": tables}


def _shaken_page(text: str, rng: random.Random) -> str:
    """같은 쪽 안에서 태그 줄 맞바꿈 · 덩이째 맞바꿈 · 태그 겹침 하나."""
    head, *rest = TAG_LINE.split(text)
    tags, bodies = rest[::2], [body.strip() for body in rest[1::2]]
    i, j = rng.sample(range(len(tags)), 2)
    match rng.choice(("tags", "chunks", "overlap")):
        case "tags":
            tags[i], tags[j] = tags[j], tags[i]
        case "chunks":
            tags[i], tags[j] = tags[j], tags[i]
            bodies[i], bodies[j] = bodies[j], bodies[i]
        case _:
            tags[j] = tags[i]
    return head.strip() + "".join(f"\n\n{tag}\n{body}" for tag, body in zip(tags, bodies, strict=True))


def _got_wrong_text(unit: dict[str, Any], got: dict[str, Any]) -> bool:
    """항등 번역이므로 붙은 글은 그 단위의 원문이어야 한다."""
    if got["level"] in ("missing", "source_only"):
        return False
    if got["level"] == "cell":
        source = {(c["row"], c["col"]): c["source"] for c in unit["cells"]}
        return any(source.get((c["row"], c["col"]), "") != c["text"] for c in got["cells"])
    return "\n\n".join(got["translations"]) != "\n\n".join(m["source"] for m in unit["members"])


def shake_lookalikes() -> tuple[int, Counter[str]]:
    """씨앗 고정 흔듦 SHAKES 번: ⓐ 글 잃음 0 ⓑ 엉뚱한 글이 있는 쪽엔 경고. 엉뚱한 글을 받은 단위 수·경고 갈래를 낸다."""
    tagged = build(lookalike_document(), None, page_start=None, page_end=None)
    identity = page_map(tagged.text)
    assert not any(
        _got_wrong_text(u, g) for u, g in zip(tagged.units, place(tagged.units, identity).units, strict=True)
    )
    rng = random.Random(428)  # noqa: S311 — 재현용 씨앗, 암호 아님
    wrong = 0
    warned: Counter[str] = Counter()
    for _ in range(SHAKES):
        pages = dict(identity)
        for page in rng.sample(sorted(pages), rng.choice((1, 2))):
            pages[page] = _shaken_page(pages[page], rng)
        placed = place(tagged.units, pages)
        keeps_every_char(pages, placed)
        warned.update(w["code"] for w in placed.warnings)
        bad = [u for u, g in zip(tagged.units, placed.units, strict=True) if _got_wrong_text(u, g)]
        wrong += len(bad)
        warned_pages = {w["page"] for w in placed.warnings if w["code"] in WARNED}
        assert {u["page"] for u in bad} <= warned_pages
    return wrong, warned


def test_a3_swapped_tags_lose_no_text_and_wrong_text_always_comes_with_a_warning() -> None:
    """고치지 않음 — sid:MARC-ISSUE-428 처분: 태그 줄만 바뀐 것과 덩이째 바뀐 것은 태그 글만으로 원리상 못 가른다.
    그래서 글을 잃지 않고 엉뚱한 글에는 늘 경고가 붙는 데까지를 못 박는다(웹은 tag_shift 를 원문과 맞대어 보라고
    보인다)."""
    wrong, warned = shake_lookalikes()
    assert wrong > 0  # 분모: 흔듦이 정말 엉뚱한 글을 만든다
    assert warned["tag_shift"] > 0 and warned["tag_extra"] > 0


def test_a3_a_page_outside_the_map_keeps_its_first_line() -> None:
    def edit(pages: dict[int, str]) -> None:
        pages[9] = "stray first line\nsecond"

    _, placed, pages = shaken(edit)
    assert placed.unplaced == [{"page": 9, "text": "stray first line\nsecond"}]  # [PAGE n] 꼴일 때만 뗀다
    assert ("tag_extra", 9, "PAGE 9") in codes(placed)
    keeps_every_char(pages, placed)


def test_a3_tags_out_of_order_are_a_shift() -> None:
    def edit(pages: dict[int, str]) -> None:
        head, rest = pages[1].split("\n[BLOCK 1]\n", 1)
        one, two = rest.split("\n[BLOCK 2]\n", 1)
        pages[1] = f"{head}\n[BLOCK 2]\n{two}\n[BLOCK 1]\n{one}"

    _, placed, pages = shaken(edit)
    assert any(c[0] == "tag_shift" for c in codes(placed))
    keeps_every_char(pages, placed)


def test_a3_a_length_far_off_is_warned() -> None:
    def edit(pages: dict[int, str]) -> None:
        pages[1] = pages[1].replace("오른쪽 단의 문단은 따로 묶인다.", "x")

    _, placed, _ = shaken(edit)
    assert ("length_ratio", 1, "BLOCK 2") in codes(placed)
    assert level(placed, 1, "BLOCK 2") == "block"


def test_place_does_not_change_its_inputs() -> None:
    tagged = built()
    units = copy.deepcopy(tagged.units)
    place(tagged.units, page_map(tagged.text))
    assert tagged.units == units


# ── S 끝 번호만 빠진 길의 무른 붙임(밴드 TRS5 경계 ②, sid:MARC-ISSUE-528) ──


def letter_document() -> dict[str, Any]:
    """1쪽 다단 편지 꼴(지어낸 것): BLOCK 셋(제목 + 문단 셋, 숫자 하나씩) · 오른 단 아래 서명 두 줄(BLOCK 4)."""
    blocks: list[dict[str, Any]] = []
    order = 0
    for n in range(3):
        top = 80 + n * 200
        order += 1
        blocks.append(block(1, order, f"가상 편지 {n + 1}", [40, top, 280, top + 16], kind="heading"))
        for m in range(3):
            order += 1
            text = f"가상 편지 {n + 1}의 문단 {m + 1}은 {n + 1}{m + 1}0 톤을 말한다."
            blocks.append(block(1, order, text, [40, top + 20 + m * 40, 280, top + 50 + m * 40]))
    blocks.append(block(1, order + 1, "가상 대표", [420, 700, 480, 712]))
    blocks.append(block(1, order + 2, "가상 이름", [420, 716, 480, 728]))
    return {"pages": [page_meta(1)], "blocks": blocks, "tables": []}


def re_paragraphed(tagged: pdf_tags.Tagged, edit: Callable[[str], str] | None = None) -> dict[int, str]:
    """엔진이 BLOCK 1~3 의 문단을 한 문단으로 다시 짜고(글자·숫자 그대로) 끝 BLOCK 4 태그 줄만 빠뜨린 번역."""
    pages = page_map(tagged.text)
    head, *rest = TAG_LINE.split(pages[1])
    parts = [head.strip()]
    for tag, body in zip(rest[::2], rest[1::2], strict=True):
        text = body.strip()
        if tag != "[BLOCK 4]":
            text = " ".join(paragraphs(text))
        parts.append(text if tag == "[BLOCK 4]" else f"{tag}\n{text}")
    pages[1] = "\n\n".join(parts)
    if edit is not None:
        pages[1] = edit(pages[1])
    return pages


def own(tagged: pdf_tags.Tagged, tag: str) -> str:
    return " ".join(m["source"] for u in tagged.units if u["tag"] == tag for m in u["members"])


def test_s1_units_with_only_their_paragraphs_merged_are_grouped_with_a_shift_each() -> None:
    tagged = build(letter_document(), None, page_start=None, page_end=None)
    assert tags_of(tagged.text) == ["PAGE 1", "BLOCK 1", "BLOCK 2", "BLOCK 3", "BLOCK 4"]
    pages = re_paragraphed(tagged)
    placed = place(tagged.units, pages)
    assert [(u["tag"], u["level"]) for u in placed.units] == [
        ("BLOCK 1", "group"),
        ("BLOCK 2", "group"),
        ("BLOCK 3", "group"),
        ("BLOCK 4", "missing"),
    ]
    assert placed.units[0]["translations"] == [own(tagged, "BLOCK 1")]
    assert placed.units[1]["translations"] == [own(tagged, "BLOCK 2")]
    third = placed.units[2]["translations"][0]
    assert third.startswith(own(tagged, "BLOCK 3")) and third.endswith("가상 대표\n\n가상 이름")  # 서명은 앞 단위 끝에
    assert placed.unplaced == []
    assert codes(placed) == [
        ("tag_shift", 1, "BLOCK 1"),
        ("tag_shift", 1, "BLOCK 2"),
        ("tag_shift", 1, "BLOCK 3"),
        ("tag_missing", 1, "BLOCK 4"),
    ]
    keeps_every_char(pages, placed)


def test_s2_a_unit_whose_numbers_differ_is_cut_from_there_as_before() -> None:
    tagged = build(letter_document(), None, page_start=None, page_end=None)
    pages = re_paragraphed(tagged, lambda text: text.replace("210 톤", "290 톤"))
    placed = place(tagged.units, pages)
    assert [u["level"] for u in placed.units] == ["group", "missing", "missing", "missing"]
    assert [x["text"].splitlines()[0] for x in placed.unplaced] == ["[BLOCK 2]", "[BLOCK 3]"]  # 떼어진 수 = 2
    assert codes(placed) == [("tag_shift", 1, "BLOCK 1"), ("tag_shift", 1, "BLOCK 2")]
    keeps_every_char(pages, placed)


def test_s3_a_unit_out_of_the_length_ratio_is_not_placed_loosely() -> None:
    tagged = build(letter_document(), None, page_start=None, page_end=None)

    def shorten(text: str) -> str:
        short = " ".join(pdf_tags._numbers(own(tagged, "BLOCK 1")))  # pyright: ignore[reportPrivateUsage]
        return text.replace(own(tagged, "BLOCK 1"), short)  # 숫자 덩이는 같고 길이만 비율 밖

    placed = place(tagged.units, re_paragraphed(tagged, shorten))
    assert [u["level"] for u in placed.units] == ["missing"] * 4
    assert codes(placed) == [("tag_shift", 1, "BLOCK 1")]
    assert len(placed.unplaced) == 3


def test_s4_a_table_is_never_placed_loosely() -> None:
    """표 모양이 달라도 숫자가 같은 표(행을 합친 꼴)는 지금 길 그대로 떼어진다 — 칸 자리를 잃은 글을 칸에
    붙이지 않는다."""
    blocks = [table_block(1, 1, "p1-t1", [40, 100, 560, 160]), table_block(1, 2, "p1-t2", [40, 200, 560, 260])]
    tables = [
        table("p1-t1", 1, [["구분", "2024"], ["가상항목", "1,200"]]),
        table("p1-t2", 1, [["구분", "2025"], ["가상항목", "1,100"]]),
    ]
    tagged = build({"pages": [page_meta(1)], "blocks": blocks, "tables": tables}, None, page_start=None, page_end=None)
    pages = page_map(tagged.text)
    pages[1] = pages[1].split("\n[TABLE 2]")[0].replace("| 구분 | 2024 |\n", "| 구분 2024 |\n")
    placed = place(tagged.units, pages)
    assert [u["level"] for u in placed.units] == ["missing", "missing"]
    assert codes(placed) == [("tag_shift", 1, "TABLE 1")]
    keeps_every_char(pages, placed)


def test_s6_units_that_fit_strictly_on_the_soft_path_add_no_shift() -> None:
    """항등 번역에서 끝 BLOCK 4 태그 줄만 빠짐: BLOCK 1·2 는 엄격히 맞아 경고 0, 서명 몸이 붙은 BLOCK 3 은 문단 수로
    BLOCK 4 를 되살린다(TRS6 — 되살린 둘에 tag_shift)."""
    tagged = build(letter_document(), None, page_start=None, page_end=None)
    pages = page_map(tagged.text)
    pages[1] = pages[1].replace("\n[BLOCK 4]\n", "\n")
    placed = place(tagged.units, pages)
    assert [u["level"] for u in placed.units] == ["block"] * 4
    assert codes(placed) == [("tag_shift", 1, "BLOCK 3"), ("tag_shift", 1, "BLOCK 4")]
    assert placed.unplaced == []
    keeps_every_char(pages, placed)
