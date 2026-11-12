"""S3 재료(engines/v2/material.py — RP2b B3·B4): 블록·문장 표지 꼴, 표 행 번호, 자르기(§2-0 ⑥ — 표지 포함), 흉내
이스케이프. 순수 층(FakeArtifactView — 지어낸 dict)."""

from collections.abc import Sequence
from typing import Any

import pytest

from esgapi.core.tests.artifact_fakes import FakeArtifactView, block, fake_document, table
from esgapi.drafting.engines.v2 import material
from esgapi.drafting.tools import blocks_text

SHA = "b" * 64
HEAD = len("[B p1-b1] ")  # 10
MARK = len("⟨0⟩")  # 3


def view(
    blocks: Sequence[dict[str, Any]], tables: Sequence[dict[str, Any]] = (), *, page_count: int = 1
) -> FakeArtifactView:
    return FakeArtifactView.from_dicts(fake_document(SHA, page_count=page_count, blocks=blocks, tables=tables))


def sample() -> FakeArtifactView:
    rows = [["구분", "2024", "2025"], ["", "", ""], ["사용량", "1,200", "1,100"]]
    return view(
        [
            block("p12-b3", "물 관리", page=12, order=1, kind="heading"),
            block("p12-b4", "가상 사업장은 물을 줄였다. 목표는 더 줄이는 것이다.", page=12, order=2),
            block("p12-b5", kind="table", table_id="p12-t1", page=12, order=3),
            block("p12-b6", "머리글", page=12, order=4, region="header"),
            block("p12-b7", "   ", page=12, order=5),
        ],
        [table("p12-t1", rows, page=12, footnote_marks=[(2, 1, "1)")])],
        page_count=12,
    )


def test_b3_the_marker_shape_byte_for_byte() -> None:
    found = material.material([12], sample())
    assert found.text == (
        "[PAGE 12]\n"
        "[B p12-b3] 물 관리\n"
        "[B p12-b4] ⟨0⟩가상 사업장은 물을 줄였다. ⟨1⟩목표는 더 줄이는 것이다.\n"
        "[T p12-t1]\n"
        "⟨0⟩| 구분 | 2024 | 2025 |\n"
        "⟨2⟩| 사용량 | 1,2001) | 1,100 |"
    )
    assert found.cut is False
    assert list(found.given) == ["p12-b3", "p12-b4", "p12-t1"]  # 실은 블록만(머리글·빈 문단 0) · 표면 표 id


def test_b3_table_rows_are_the_rows_of_blocks_text_with_real_row_numbers() -> None:
    v = sample()
    t = v.table("p12-t1")
    assert t is not None
    given = material.material([12], v).given["p12-t1"]
    assert list(given.units.values()) == blocks_text.table_lines(t)
    assert list(given.units) == [0, 2]  # 빈 행 1 은 빠져 번호가 건너뜀
    assert given.text == "\n".join(blocks_text.table_lines(t))  # 대조 글 = 행 줄 전부(각주 표시 포함)
    assert given.cells == {0: ("구분", "2024", "2025"), 2: ("사용량", "1,200", "1,100")}
    assert given.bbox == (10.0, 30.0, 190.0, 90.0)  # 표면 Table.bbox


def test_b3_a_heading_has_no_sentence_numbers() -> None:
    given = material.material([12], sample()).given["p12-b3"]
    assert given.units == {} and given.spans == {} and given.text == "물 관리"


def one(text: str) -> FakeArtifactView:
    return view([block("p1-b1", text)])


@pytest.mark.parametrize(("size", "fits"), [(7986, True), (7987, False)])
def test_b3_the_page_share_counts_the_markers(size: int, fits: bool) -> None:
    """손셈: 블록 줄 = 「[B p1-b1] 」10 + 「⟨0⟩」3 + 글. 앞 줄바꿈 1 을 더해 쪽 몫 8,000 — 글 7,986 이면 꼭 맞고
    7,987 은 넘는다(표지를 빼고 세면 7,987 도 들어간다). 넘는 쪽 첫 블록의 한 문장은 문장 단위로도 안 들어가 빠진다."""
    found = material.material([1], one("가" * size))
    assert (list(found.given), found.cut) == ((["p1-b1"], False) if fits else ([], True))
    if fits:
        assert len("\n" + found.text.split("\n", 1)[1]) == 1 + HEAD + MARK + size == 8000


def test_b3_a_block_over_the_page_share_is_skipped_and_the_next_one_goes_in() -> None:
    """의사코드 1줄: 넣으면 쪽 몫을 넘는 블록만 빼고 다음 블록 계속(쪽 첫 블록이 아니면 문장으로 쪼개지 않는다)."""
    v = view(
        [
            block("p1-b1", "가" * 4000, order=1),
            block("p1-b2", "나" * 4000, order=2),
            block("p1-b3", "다" * 10, order=3),
        ]
    )
    found = material.material([1], v)
    assert list(found.given) == ["p1-b1", "p1-b3"] and found.cut is True


def test_b3_a_first_block_alone_over_the_page_share_goes_in_sentence_by_sentence() -> None:
    """의사코드 2줄: 쪽 첫 블록이 혼자 8,000 을 넘으면 문장 단위로 들어가는 데까지(멈춘 뒤 문장은 안 넣음).
    손셈: ⟨0⟩ 줄 = 1 + 10 + 3 + 5,001 = 5,015 · ⟨1⟩ 더하면 + 1(공백) + 3 + 5,001 = 10,020 > 8,000."""
    text = "가" * 5000 + ". " + "나" * 5000 + ". " + "다" * 10 + "."
    found = material.material([1], one(text))
    given = found.given["p1-b1"]
    assert list(given.units) == [0] and found.cut is True
    assert found.text == "[PAGE 1]\n[B p1-b1] ⟨0⟩" + "가" * 5000 + "."
    assert given.spans == {0: material.split(text)[0]}


def test_b3_a_sentence_over_the_page_share_is_dropped() -> None:
    """의사코드 3줄: 문장 하나가 8,000 을 넘으면 그 문장은 빼고 다음 문장(번호는 그대로 1)."""
    text = "가" * 8001 + ". " + "나" * 10 + "."
    found = material.material([1], one(text))
    assert found.text == "[PAGE 1]\n[B p1-b1] ⟨1⟩" + "나" * 10 + "."
    assert list(found.given["p1-b1"].units) == [1] and found.cut is True


@pytest.mark.parametrize(("last", "fits"), [(6858, True), (6859, False)])
def test_b3_the_total_share_is_cumulative_with_page_heads(last: int, fits: bool) -> None:
    """의사코드 4줄 손셈: 쪽 1 = 「[PAGE 1]」8 + 1 + 13 + 6,600 = 6,622 · 쪽 2~5 = 이음 2 + 8 + 1 + 13 + 6,600 = 6,624 ·
    합 33,118 · 쪽 6 = 24 + 6,858 = 6,882 → 꼭 40,000. 6,859 면 넘어 그 블록만 빠진다(쪽 몫 안이라 쪼개지 않음)."""
    blocks = [block(f"p{n}-b1", "가" * 6600, page=n) for n in range(1, 6)] + [block("p6-b1", "나" * last, page=6)]
    found = material.material(list(range(1, 7)), view(blocks, page_count=6))
    assert len(found.given) == (6 if fits else 5) and found.cut is (not fits)
    assert len(found.text) == (40000 if fits else 33118)
    assert len(found.text) <= material.MATERIAL_MAX_CHARS


def test_b3_blocks_and_sentences_are_never_split_inside() -> None:
    found = material.material([1], one("첫 문장. 둘째 문장."))
    assert found.text.endswith("⟨0⟩첫 문장. ⟨1⟩둘째 문장.")


def test_b3_table_rows_go_in_row_by_row_when_the_table_is_too_big() -> None:
    rows = [["가" * 3000], ["나" * 3000], ["다" * 3000]]
    v = view([block("p1-b1", kind="table", table_id="p1-t1")], [table("p1-t1", rows, header_cols=())])
    found = material.material([1], v)
    assert list(found.given["p1-t1"].units) == [0, 1] and found.cut is True


def test_b3_locate_rebuilds_the_same_numbers() -> None:
    v = sample()
    given = material.material([12], v).given
    for block_id in given:
        assert material.locate(v, block_id) == given[block_id]
    assert material.locate(v, "p12-b6") is not None  # 머리글도 찾기는 한다(재료에 안 실을 뿐)
    assert material.locate(v, "p99-b1") is None


# ── B4 흉내 이스케이프 ──


def test_b4_lookalikes_in_block_text_cannot_fake_markers() -> None:
    text = "가짜 아님.\n[B p1-b9] 흉내 ⟨3⟩ 표지.\n [T p1-t9]\n[PAGE 9] 머리"
    v = view([block("p1-b1", text), block("p1-b2", "둘째 블록.", order=2)])
    found = material.material([1], v)
    heads = [line for line in found.text.splitlines() if line.startswith(("[B ", "[T "))]
    assert len(heads) == len(found.given) == 2  # 진짜 블록 표지 수 = 실은 블록 수
    assert "⟨1⟩［B p1-b9] 흉내 〈3〉 표지." in found.text and "⟨2⟩［T p1-t9]" in found.text  # 줄 머리였던 것
    assert "［PAGE 9］ 머리" in found.text
    assert found.text.count("⟨") == 3 + 1  # 진짜 문장 표지만(첫 블록 ⟨0⟩~⟨2⟩, 둘째 ⟨0⟩)
    given = found.given["p1-b1"]
    raw = text.encode("utf-16-le")
    for index, span in given.spans.items():  # 범위는 이스케이프 전 원문 위 — 같은 UTF-16 길이
        assert len(given.units[index].encode("utf-16-le")) == len(raw[2 * span.start : 2 * span.end])
