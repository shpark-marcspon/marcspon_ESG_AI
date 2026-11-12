"""PDF 입력 어댑터의 태그 되살리기·무른 길 숫자·단 넘김 문단 수(tools/pdf_tags.py — 밴드 TRS6 커밋 ①,
sid:MARC-ISSUE-532). 순수: 파서·엔진 호출 0. 쪽은 지어낸 두 단 쪽 하나(단 x 40/320 · 폭 240 · 글자 9 — 글·숫자는 전부
지어낸 것), 번역은 항등 번역에서 태그 줄을 지우거나 문단을 합친 편집.

T1 끝 탈락(앞 단위 몸 끝에 붙음) → 문단 수로 되살림 · 단 넘김·숫자 꼴 바뀐 단위는 그대로 group(떼이지 않음).
T2 가운데 탈락(뒤 표 그대로) · T2b 앞이 표(pipe 행 뒤 꼬리만) · T2c 한 쪽에 떨어진 탈락 둘 · T3 앞이 VISUAL ·
T4 연속 탈락 둘(뒤에서부터) · T5 수 안 맞음(하나 모자람)·T5b 하나 남음·T5c 나누는 길 둘 → 되살리지 않음(지금 길) ·
T6 되살리지 못한 끝 빠짐 + 숫자 꼴만 다른 앞 단위는 떼지 않음(원문에 없는 숫자는 뗌) · T7 차례 뒤집힘은 되살리지 않음 ·
T8 group 몸의 빈 줄 보존 · 단 넘김 하나인 단위(멤버 3, 문단 2)는 엄격 길에서 맞음.
불변: 시험마다 번역 글자가 다 있고(`keeps_every_char`) 단위 사이 상자 겹침 0.
"""

from typing import Any

import pytest

from esgapi.translation.tests.tools.test_pdf_tags import (
    block,
    codes,
    keeps_every_char,
    page_map,
    page_meta,
    table,
    table_block,
    tags_of,
)
from esgapi.translation.tools import pdf_tags
from esgapi.translation.tools.pdf_tags import build, paragraphs, place

X = (40.0, 320.0)
WIDTH = 240.0


class Sheet:
    """지어낸 쪽 하나를 읽는 차례로 쌓는다(단마다 위에서 아래로 — 블록 틈 12 는 줄 묶기 틈 밖)."""

    def __init__(self) -> None:
        self.blocks: list[dict[str, Any]] = []
        self.tables: list[dict[str, Any]] = []
        self.tops = [40.0, 40.0]
        self.serial = 0

    def put(self, text: str, *, col: int = 0, kind: str = "paragraph", one_line: bool = False) -> str:
        height = 12.0 if one_line else 16.0 if kind == "heading" else 20.0
        top = self.tops[col]
        self.blocks.append(block(1, len(self.blocks) + 1, text, [X[col], top, X[col] + WIDTH, top + height], kind=kind))
        self.tops[col] = top + height + 12.0
        return text

    def section(self, title: str, count: int, *, col: int = 0) -> list[str]:
        """제목 + 문단 count − 1(멤버 count). 문단마다 지어낸 숫자 하나."""
        texts = [self.put(f"가상 {title}", col=col, kind="heading")]
        for n in range(count - 1):
            self.serial += 1
            texts.append(self.put(f"가상 {title}의 문단 {n + 1}은 {self.serial}{n}7 톤을 말한다.", col=col))
        return texts

    def grid(self, cells: list[list[str]], *, col: int = 0) -> None:
        tid = f"p1-t{len(self.tables) + 1}"
        top = self.tops[col]
        self.blocks.append(table_block(1, len(self.blocks) + 1, tid, [X[col], top, X[col] + WIDTH, top + 40]))
        self.tables.append(table(tid, 1, cells))
        self.tops[col] = top + 52.0

    def tagged(self) -> pdf_tags.Tagged:
        document = {"pages": [page_meta(1)], "blocks": self.blocks, "tables": self.tables}
        return build(document, None, page_start=None, page_end=None)


def without(tagged: pdf_tags.Tagged, *tags: str) -> dict[int, str]:
    """항등 번역에서 태그 줄만 지운다(그 몸은 앞 단위 몸 끝에 빈 줄로 붙는다)."""
    pages = page_map(tagged.text)
    for tag in tags:
        assert f"\n[{tag}]\n" in pages[1]
        pages[1] = pages[1].replace(f"\n[{tag}]\n", "\n")
    return pages


def merged(pages: dict[int, str], first: str, second: str) -> dict[int, str]:
    """두 문단을 한 문단으로(엔진이 문단을 다시 짠 꼴)."""
    assert f"{first}\n\n{second}" in pages[1]
    pages[1] = pages[1].replace(f"{first}\n\n{second}", f"{first} {second}")
    return pages


def levels(placed: pdf_tags.Placed) -> list[tuple[str | None, str]]:
    return [(u["tag"], u["level"]) for u in placed.units]


def translation(placed: pdf_tags.Placed, tag: str) -> list[str]:
    return next(u["translations"] for u in placed.units if u["tag"] == tag)


def recovered(placed: pdf_tags.Placed) -> list[str]:
    assert {n["code"] for n in placed.notes} <= {"tag_recovered"}
    return [n["tag"] for n in placed.notes]


def no_overlap(tagged: pdf_tags.Tagged) -> None:
    """단위가 다른 멤버 상자끼리 겹침 0(되살리기는 글만 옮긴다 — 지도는 그대로)."""
    boxes = [(n, m["bbox"]) for n, u in enumerate(tagged.units) for m in u["members"]]
    for i, (n, a) in enumerate(boxes):
        for k, b in boxes[i + 1 :]:
            if n != k:
                assert min(a[2], b[2]) <= max(a[0], b[0]) or min(a[3], b[3]) <= max(a[1], b[1])


def check(tagged: pdf_tags.Tagged, pages: dict[int, str], placed: pdf_tags.Placed) -> None:
    keeps_every_char(pages, placed)
    no_overlap(tagged)


# ── T1 끝 탈락 ──


def carried_letter(third: int, last: int) -> tuple[pdf_tags.Tagged, dict[str, str]]:
    """BLOCK 1(2) · BLOCK 2(10 — 왼 단 끝 줄이 오른 단 위로 넘어감, 숫자 꼴 바뀔 글) · BLOCK 3(third) ·
    BLOCK 4(last)."""
    sheet = Sheet()
    sheet.section("서한", 2)
    sheet.put("가상 사업", kind="heading")
    year = sheet.put("가상 매출은 '25년 114억 원이었다.")
    for n in range(3):
        sheet.put(f"가상 사업의 둘째 문단 {n + 1}은 {n + 4}1 톤을 말한다.")
    left = sheet.put("가상 사업은 다음 해에도 이어지며", one_line=True)
    right = sheet.put("가상 목표까지 간다.", col=1, one_line=True)
    for n in range(3):
        sheet.put(f"가상 사업의 셋째 문단 {n + 1}은 {n + 7}2 톤을 말한다.", col=1)
    sheet.section("성과", third, col=1)
    for n in range(last):
        sheet.put(f"가상 맺음 글 {n + 1}은 서명을 대신한다.")
    return sheet.tagged(), {"year": year, "left": left, "right": right}


@pytest.mark.parametrize(("third", "last"), [(7, 2), (4, 1)], ids=["signature", "caption"])
def test_t1_a_dropped_last_tag_is_recovered_by_the_paragraph_count(third: int, last: int) -> None:
    tagged, text = carried_letter(third, last)
    assert tags_of(tagged.text) == ["PAGE 1", "BLOCK 1", "BLOCK 2", "BLOCK 3", "BLOCK 4"]
    assert [len(u["members"]) for u in tagged.units] == [2, 10, third, last]
    pages = merged(without(tagged, "BLOCK 4"), text["left"], text["right"])  # 단을 넘은 문장은 한 문단(9)
    pages[1] = pages[1].replace("'25년 114억 원", "2025 11.4 billion won")
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "block"), ("BLOCK 2", "group"), ("BLOCK 3", "block"), ("BLOCK 4", "block")]
    assert "2025 11.4 billion won" in translation(placed, "BLOCK 2")[0]  # 떼이지 않음
    assert translation(placed, "BLOCK 4") == [f"가상 맺음 글 {n + 1}은 서명을 대신한다." for n in range(last)]
    assert codes(placed) == [("tag_shift", 1, "BLOCK 3"), ("tag_shift", 1, "BLOCK 4")]
    assert recovered(placed) == ["BLOCK 4"]
    assert placed.unplaced == []
    check(tagged, pages, placed)


# ── T2 가운데 탈락 ──


@pytest.mark.parametrize(
    ("first", "title"),
    [(2, "가상 소제목"), (1, "가상 소제목"), (2, "[가상-1] 소제목")],
    ids=["2+1", "1+1", "bracket"],
)
def test_t2_a_dropped_middle_tag_is_recovered_before_the_table(first: int, title: str) -> None:
    sheet = Sheet()
    sheet.section("개요", first)
    sheet.put(title, kind="heading")
    sheet.grid([["구분", "2025"], ["가상항목", "1,100"]])
    tagged = sheet.tagged()
    assert tags_of(tagged.text) == ["PAGE 1", "BLOCK 1", "BLOCK 2", "TABLE 1"]
    pages = without(tagged, "BLOCK 2")
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "block"), ("BLOCK 2", "block"), ("TABLE 1", "cell")]
    assert translation(placed, "BLOCK 2") == [title]
    assert codes(placed) == [("tag_shift", 1, "BLOCK 1"), ("tag_shift", 1, "BLOCK 2")]
    assert recovered(placed) == ["BLOCK 2"]
    assert placed.unplaced == []
    check(tagged, pages, placed)


def test_t2b_a_block_dropped_after_a_table_takes_only_the_tail_after_the_pipe_rows() -> None:
    sheet = Sheet()
    sheet.grid([["구분", "2025"], ["가상항목", "1,100"]])
    sheet.put("가상 표의 주석은 표 아래에 붙는다.")
    sheet.section("다음", 2)
    tagged = sheet.tagged()
    assert tags_of(tagged.text) == ["PAGE 1", "TABLE 1", "BLOCK 1", "BLOCK 2"]
    pages = without(tagged, "BLOCK 1")
    placed = place(tagged.units, pages)
    assert levels(placed) == [("TABLE 1", "cell"), ("BLOCK 1", "block"), ("BLOCK 2", "block")]
    assert translation(placed, "BLOCK 1") == ["가상 표의 주석은 표 아래에 붙는다."]
    assert codes(placed) == [("tag_shift", 1, "TABLE 1"), ("tag_shift", 1, "BLOCK 1")]
    assert placed.unplaced == []
    check(tagged, pages, placed)


def test_t2c_two_separate_middle_drops_on_one_page_are_both_recovered() -> None:
    sheet = Sheet()
    for title, count in [("하나", 1), ("둘", 1), ("셋", 1), ("넷", 3), ("다섯", 2)]:
        sheet.section(title, count)
    tagged = sheet.tagged()
    assert [len(u["members"]) for u in tagged.units] == [1, 1, 1, 3, 2]
    pages = without(tagged, "BLOCK 2", "BLOCK 4")  # (1)+(1) · (1)+(3)
    placed = place(tagged.units, pages)
    assert levels(placed) == [(f"BLOCK {n}", "block") for n in range(1, 6)]
    assert codes(placed) == [("tag_shift", 1, f"BLOCK {n}") for n in (3, 4, 1, 2)]  # 덩어리는 뒤에서부터
    assert recovered(placed) == ["BLOCK 4", "BLOCK 2"]
    assert placed.unplaced == []
    check(tagged, pages, placed)


def test_t3_a_block_dropped_after_a_visual_is_recovered() -> None:
    sheet = Sheet()
    for n in range(9):
        sheet.put(f"가상 라벨 {n + 1}", one_line=True)
    sheet.section("본문", 1)
    sheet.section("다음", 2)
    tagged = sheet.tagged()
    assert tags_of(tagged.text) == ["PAGE 1", "VISUAL 1", "BLOCK 1", "BLOCK 2"]
    assert len(tagged.units[0]["members"]) == 9
    pages = without(tagged, "BLOCK 1")
    placed = place(tagged.units, pages)
    assert levels(placed) == [("VISUAL 1", "block"), ("BLOCK 1", "block"), ("BLOCK 2", "block")]
    assert codes(placed) == [("tag_shift", 1, "VISUAL 1"), ("tag_shift", 1, "BLOCK 1")]
    assert placed.unplaced == []
    check(tagged, pages, placed)


def test_t4_two_tags_dropped_in_a_row_are_recovered_from_the_back() -> None:
    sheet = Sheet()
    for title, count in [("하나", 3), ("둘", 1), ("셋", 2), ("넷", 2)]:
        sheet.section(title, count)
    tagged = sheet.tagged()
    pages = without(tagged, "BLOCK 2", "BLOCK 3")  # BLOCK 1 몸 = 3 + 1 + 2
    assert len(paragraphs(pages[1].split("[BLOCK 1]\n")[1].split("\n[BLOCK 4]")[0])) == 6
    placed = place(tagged.units, pages)
    assert levels(placed) == [(f"BLOCK {n}", "block") for n in range(1, 5)]
    assert translation(placed, "BLOCK 2") == ["가상 둘"]
    assert translation(placed, "BLOCK 3")[0] == "가상 셋"
    assert codes(placed) == [("tag_shift", 1, f"BLOCK {n}") for n in (1, 2, 3)]
    assert recovered(placed) == ["BLOCK 2", "BLOCK 3"]
    assert placed.unplaced == []
    check(tagged, pages, placed)


# ── T5 수가 안 맞으면 지금 길 ──


def three_blocks(second: int = 2) -> tuple[pdf_tags.Tagged, list[list[str]]]:
    sheet = Sheet()
    texts = [sheet.section(title, count) for title, count in [("하나", 2), ("둘", second), ("셋", 2)]]
    return sheet.tagged(), texts


def test_t5_a_middle_drop_one_paragraph_short_stays_missing() -> None:
    tagged, texts = three_blocks()
    pages = merged(without(tagged, "BLOCK 2"), *texts[1])  # 앞 몸 = 2 + 1(모자람)
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "group"), ("BLOCK 2", "missing"), ("BLOCK 3", "block")]
    assert codes(placed) == [("tag_missing", 1, "BLOCK 2")]
    assert placed.notes == [] and placed.unplaced == []
    check(tagged, pages, placed)


def test_t5_a_last_drop_one_paragraph_short_takes_the_soft_path() -> None:
    tagged, texts = three_blocks()
    pages = merged(without(tagged, "BLOCK 3"), *texts[2])
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "block"), ("BLOCK 2", "missing"), ("BLOCK 3", "missing")]
    assert codes(placed) == [("tag_shift", 1, "BLOCK 2")]  # 셋의 숫자가 둘의 원문으로 설명 안 됨 → 뗌
    assert [x["text"].splitlines()[0] for x in placed.unplaced] == ["[BLOCK 2]"]
    assert placed.notes == []
    check(tagged, pages, placed)


def test_t5b_one_paragraph_too_many_is_not_recovered() -> None:
    tagged, texts = three_blocks(second=1)
    pages = without(tagged, "BLOCK 2")
    first = texts[0][1]
    pages[1] = pages[1].replace(first, first.replace("은 ", "은\n\n", 1))  # 앞 몸 = 2 + 1 + 1(남음)
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "group"), ("BLOCK 2", "missing"), ("BLOCK 3", "block")]
    assert codes(placed) == [("tag_missing", 1, "BLOCK 2")]
    assert placed.notes == [] and placed.unplaced == []
    check(tagged, pages, placed)


def test_t5c_two_ways_to_split_the_paragraphs_are_not_recovered() -> None:
    """앞 단위·빠진 단위 둘 다 단 넘김 하나(멤버 3, 범위 2..3)이고 몸이 5문단 → (3,2)·(2,3) 두 길 → 되살리지 않음."""
    sheet = Sheet()
    sheet.put("가상 머리", kind="heading")
    first = sheet.put("가상 앞 글은 다음 단으로 이어지며", one_line=True)
    second = sheet.put("가상 앞 글의 끝이다.", col=1, one_line=True)
    sheet.put("가상 꼬리", kind="heading")
    sheet.put("가상 뒤 글도 다음 단으로 이어지며", one_line=True)
    sheet.put("가상 뒤 글의 끝이다.", col=1, one_line=True)
    tagged = sheet.tagged()
    assert [len(u["members"]) for u in tagged.units] == [3, 3]
    pages = merged(without(tagged, "BLOCK 2"), first, second)
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "group"), ("BLOCK 2", "missing")]
    assert codes(placed) == [("tag_shift", 1, "BLOCK 1"), ("tag_missing", 1, "BLOCK 2")]
    assert placed.notes == [] and placed.unplaced == []
    check(tagged, pages, placed)


# ── T6 무른 길의 숫자 꼴 ──


def number_letter() -> tuple[pdf_tags.Tagged, dict[int, str]]:
    """BLOCK 1~3(2) · BLOCK 4(2, 숫자 없는 서명) — 끝 태그 빠지고 서명 둘이 한 문단(되살릴 수 없음)."""
    sheet = Sheet()
    sheet.put("가상 하나", kind="heading")
    sheet.put("가상 목표는 '25년까지 2위를 지키는 것이다.")
    sheet.put("가상 둘", kind="heading")
    sheet.put("가상 투자는 114억 원이다.")
    sheet.put("가상 셋", kind="heading")
    sheet.put("가상 셋의 글에는 숫자가 없다.")
    sheet.put("가상 대표 드림.", col=1)
    sheet.put("가상 이름 올림.", col=1)
    tagged = sheet.tagged()
    assert [len(u["members"]) for u in tagged.units] == [2, 2, 2, 2]
    pages = merged(without(tagged, "BLOCK 4"), "가상 대표 드림.", "가상 이름 올림.")
    pages[1] = pages[1].replace("'25년까지 2위를", "until 2025 second").replace("114억 원", "11.4 billion won")
    return tagged, pages


def test_t6_units_whose_numbers_only_change_form_are_not_cut() -> None:
    tagged, pages = number_letter()
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "block"), ("BLOCK 2", "block"), ("BLOCK 3", "group"), ("BLOCK 4", "missing")]
    assert codes(placed) == [
        ("tag_shift", 1, "BLOCK 1"),
        ("tag_shift", 1, "BLOCK 2"),
        ("tag_shift", 1, "BLOCK 3"),
        ("tag_missing", 1, "BLOCK 4"),
    ]
    assert placed.notes == [] and placed.unplaced == []
    check(tagged, pages, placed)


def test_t6_a_number_the_source_does_not_explain_is_still_cut() -> None:
    tagged, pages = number_letter()
    pages[1] = pages[1].replace("11.4 billion won", "11.4 billion won in 39 sites")
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "block")] + [(f"BLOCK {n}", "missing") for n in (2, 3, 4)]
    assert codes(placed) == [("tag_shift", 1, "BLOCK 1"), ("tag_shift", 1, "BLOCK 2")]
    assert [x["text"].splitlines()[0] for x in placed.unplaced] == ["[BLOCK 2]", "[BLOCK 3]"]
    check(tagged, pages, placed)


# ── T7 차례 뒤집힘 ──


def test_t7_tags_out_of_order_are_not_recovered() -> None:
    """BLOCK 2 태그 줄 빠짐(앞 몸 문단 수는 되살릴 수 있는 2 + 1) + 뒤 BLOCK 4·5 차례 뒤집힘 → 되살리지 않고 기존 길."""
    sheet = Sheet()
    for title, count in [("하나", 2), ("둘", 1), ("셋", 2), ("넷", 2), ("다섯", 2)]:
        sheet.section(title, count)
    tagged = sheet.tagged()
    pages = without(tagged, "BLOCK 2")
    head, rest = pages[1].split("\n[BLOCK 4]\n")
    fourth, fifth = rest.split("\n[BLOCK 5]\n")
    pages[1] = f"{head}\n[BLOCK 5]\n{fifth.strip()}\n\n[BLOCK 4]\n{fourth.strip()}\n"
    placed = place(tagged.units, pages)
    assert levels(placed) == [(f"BLOCK {n}", "missing") for n in range(1, 6)]
    assert codes(placed) == [("tag_shift", 1, "BLOCK 4"), ("tag_shift", 1, "BLOCK 1")]
    assert placed.notes == []
    check(tagged, pages, placed)


# ── T8 group 몸 · 단 넘김 문단 수 ──


def test_t8_a_carried_block_fits_strictly_and_group_bodies_keep_their_blank_lines() -> None:
    sheet = Sheet()
    sheet.put("가상 머리", kind="heading")
    left = sheet.put("가상 사업은 다음 해에도 이어지며", one_line=True)
    right = sheet.put("가상 목표까지 간다.", col=1, one_line=True)
    sheet.section("둘", 2, col=1)
    sheet.put("가상 맺음 하나.", col=0)
    sheet.put("가상 맺음 둘.", col=0)
    tagged = sheet.tagged()
    assert [len(u["members"]) for u in tagged.units] == [3, 2, 2]
    pages = merged(merged(without(tagged, "BLOCK 3"), left, right), "가상 맺음 하나.", "가상 맺음 둘.")
    placed = place(tagged.units, pages)
    assert levels(placed) == [("BLOCK 1", "group"), ("BLOCK 2", "group"), ("BLOCK 3", "missing")]
    assert codes(placed) == [("tag_shift", 1, "BLOCK 2"), ("tag_missing", 1, "BLOCK 3")]  # BLOCK 1 은 엄격히 맞음
    assert translation(placed, "BLOCK 1") == [f"가상 머리\n\n{left} {right}"]
    (body,) = translation(placed, "BLOCK 2")
    assert body.count("\n\n") == 2  # 몸 안 빈 줄 그대로(화면 줄바꿈은 웹 몫)
    assert placed.unplaced == []
    check(tagged, pages, placed)
