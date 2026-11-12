"""단락 구성 블록 → 블록 범위(engines/g1/ranges.py — 밴드 GE1 감독 답 C1). 「이어짐」= body 블록 읽는 차례의 이웃.
지어낸 문서 dict → FakeArtifactView."""

import pytest

from esgapi.greenwash.engines.g1 import passages as P
from esgapi.greenwash.engines.g1 import ranges as R
from esgapi.greenwash.tests.engines.g1.test_passages import long, para, view

OPEN = "가상회사는 사업장 전력 설비를 바꾸는 일을 해마다 이어 가며 그 결과를 점검하는 체계를 두고 있고"


def test_a_header_between_pages_does_not_split_the_range() -> None:
    """body 차례로 셈한다 — 모든 블록 차례였다면 머리 h2 가 끼어 범위가 둘이 된다."""
    v = view(
        [
            para("b1", OPEN, page=1, order=1),
            para("f1", "꼬리 글", page=1, order=2, region="footer"),
            para("h2", "머리 글", page=2, order=1, region="header"),
            para("b2", "그 점검 결과를 공개합니다.", page=2, order=2),
        ]
    )
    (passage,) = P.build_passages(v).passages
    assert passage.members == ["b1", "b2"]
    order = R.block_order(v)
    assert R.fold(passage.members, order) == [("b1", "b2")]
    every_block = {b.id: i for i, b in enumerate(v.blocks())}
    assert len(R.fold(passage.members, every_block)) == 2


def test_a_body_block_left_out_of_the_passage_splits_the_range() -> None:
    order = {"b1": 0, "b2": 1, "b3": 2, "b4": 3, "b5": 4}
    assert R.fold(["b1", "b2", "b4", "b5"], order) == [("b1", "b2"), ("b4", "b5")]
    assert R.fold(["b3"], order) == [("b3", "b3")]


def test_fold_sorts_into_reading_order_and_drops_repeats() -> None:
    order = {"b1": 0, "b2": 1, "b3": 2, "b9": 3}
    assert R.fold(["b3", "b1", "b2", "b1"], order) == [("b1", "b3")]


def test_a_block_outside_the_body_order_is_refused() -> None:
    with pytest.raises(ValueError, match="body 차례에 없는"):
        R.fold(["b1", "h1"], {"b1": 0})


def test_reading_the_ranges_gives_back_the_members() -> None:
    v = view(
        [
            para("b1", OPEN, page=1, order=1),
            para("b2", "그 점검 결과를 공개합니다.", page=2, order=1),
            para("b3", long(3), page=2, order=2),
            para("b4", long(4), page=3, order=1),
        ]
    )
    order = R.block_order(v)
    for passage in P.build_passages(v).passages:
        got = [b for first, last in R.fold(passage.members, order) for b in R.read(first, last, order)]
        assert got == sorted(dict.fromkeys(passage.members), key=order.__getitem__)


def test_a_reversed_range_is_refused() -> None:
    with pytest.raises(ValueError, match="거꾸로"):
        R.read("b2", "b1", {"b1": 0, "b2": 1})


def test_cap_keeps_the_first_ranges_and_says_so() -> None:
    ranges = [(f"b{i}", f"b{i}") for i in range(9)]
    assert R.cap(ranges, 8) == (ranges[:8], True)
    assert R.cap(ranges[:8], 8) == (ranges[:8], False)
