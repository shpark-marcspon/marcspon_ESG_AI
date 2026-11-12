"""단락 짓기와 보정 b~f(engines/g1/passages.py — 밴드 GE1 T5). 지어낸 문서 dict → FakeArtifactView."""

from collections.abc import Sequence
from typing import Any

import pytest

from esgapi.core.tests.artifact_fakes import FakeArtifactView, block, fake_document, section, table
from esgapi.greenwash.engines.g1 import passages as P

SHA = "c" * 64


def long(n: int) -> str:
    """150자 넘는 지어낸 문단(끝이 「다.」). n 이 다르면 글이 달라 되풀이 뺌(e)에 안 걸린다."""
    return f"가상회사 {n}번 사업장은 전력 사용량을 줄이는 설비를 들였고 그 효과를 해마다 점검합니다. " * 3


LONG = long(0)


def view(
    blocks: list[dict[str, Any]],
    *,
    tables: Sequence[dict[str, Any]] = (),
    pages: int = 20,
    sections: list[dict[str, Any]] | None = None,
) -> FakeArtifactView:
    secs = sections or [section("s1", "환경 경영", page_start=1, page_end=pages)]
    doc = fake_document(SHA, page_count=pages, blocks=blocks, tables=list(tables), sections=secs)
    return FakeArtifactView.from_dicts(doc)


def para(
    bid: str, text: str, *, page: int = 1, order: int = 1, region: str = "body", sid: str = "s1"
) -> dict[str, Any]:
    return block(bid, text, page=page, order=order, region=region, section_id=sid)


def test_paragraphs_join_until_a_sentence_ends_past_150_chars() -> None:
    built = P.build_passages(
        view([para("b1", "짧은 첫 줄", order=1), para("b2", long(2), order=2), para("b3", long(3), order=3)])
    )
    assert [p.members for p in built.passages] == [["b1", "b2"], ["b3"]]
    assert built.passages[0].text.startswith("환경 경영\n짧은 첫 줄 ")
    assert [p.id for p in built.passages] == ["P1", "P2"]


def test_b_drops_header_and_footer_blocks() -> None:
    blocks = [
        para("h1", "머리띠 글자 묶음", region="header"),
        para("b1", LONG, order=2),
        para("f1", "꼬리", region="footer", order=3),
    ]
    built = P.build_passages(view(blocks))
    assert [m for p in built.passages for m in p.members] == ["b1"]
    assert built.stat["b 머리·꼬리 뺌"] == 2


def test_e_drops_text_repeated_on_30_percent_of_pages() -> None:
    blocks = [para(f"m{n}", "지속가능경영 쪽 메뉴", page=n, order=1) for n in (1, 2)]
    blocks += [para(f"b{n}", long(n), page=n, order=2) for n in (1, 2, 3)]
    built = P.build_passages(view(blocks, pages=6))
    members = [m for p in built.passages for m in p.members]
    assert "m1" not in members and "m2" not in members
    assert built.stat["e 되풀이 글 뺌"] == 2


def test_c_attaches_a_footnote_to_the_previous_table_on_the_page() -> None:
    blocks = [
        para("b1", LONG, order=1),
        block("t1b", page=1, order=2, kind="table", table_id="t1", section_id="s1"),
        para("n1", "1) 국내 사업장만 셈했습니다.", order=3),
    ]
    built = P.build_passages(view(blocks, tables=[table("t1", [["항목", "2025"], ["전력", "120"]])]))
    tab = next(p for p in built.passages if p.kind == "table")
    assert tab.text.endswith("항목 | 2025\n전력 | 120\n주: 1) 국내 사업장만 셈했습니다.")
    assert tab.members == ["t1b", "n1"]
    assert built.stat["c 표에 붙인 각주"] == 1


def test_c_leaves_a_footnote_without_a_table_on_its_page() -> None:
    blocks = [para("b1", LONG, order=1), para("n1", "* 추정치입니다.", page=2, order=1)]
    built = P.build_passages(view(blocks))
    assert built.stat.get("c 표에 붙인 각주", 0) == 0
    assert any("n1" in p.members for p in built.passages if p.kind == "paragraph")


def test_d_splits_a_bulleted_summary_with_spans() -> None:
    items = [f"• 가상 성과 {k}: 사업장 설비를 바꾸어 에너지 사용을 줄였고 그 결과를 점검했습니다" for k in range(10)]
    text = " ".join(items)
    assert len(text) > P.SPLIT_MIN
    built = P.build_passages(view([para("b1", text)]))
    assert built.stat["d 쪼갠 요약 단락"] == 1
    assert len(built.passages) >= 2
    for p in built.passages:
        assert p.members == ["b1"] and p.span is not None
        start, end = p.span
        assert 0 <= start < end <= len(text)
    spans = [p.span for p in built.passages]
    assert spans == sorted(spans, key=lambda s: s[0] if s else 0)


def test_f_folds_a_tiny_paragraph_into_the_next_table() -> None:
    blocks = [
        para("b1", LONG, order=1),
        para("a1", "〉 가상 배출량", order=2),
        block("t1b", page=1, order=3, kind="table", table_id="t1", section_id="s1"),
    ]
    built = P.build_passages(view(blocks, tables=[table("t1", [["항목", "2025"], ["배출", "7"]])]))
    tab = next(p for p in built.passages if p.kind == "table")
    assert tab.members == ["a1", "t1b"]
    assert tab.text.split("\n", 1)[0].endswith(" · 〉 가상 배출량")
    assert built.stat["f 묶은 짧은 단락"] == 1
    assert all("a1" not in p.members for p in built.passages if p.kind == "paragraph")


def test_section_titles_come_from_the_view() -> None:
    secs = [section("s1", "기후 대응", page_start=1, page_end=1), section("s2", None, page_start=2, page_end=2)]
    blocks = [para("b1", long(1), sid="s1"), para("b2", long(2), page=2, sid="s2")]
    built = P.build_passages(view(blocks, sections=secs))
    assert built.titles == {"s1": "기후 대응", "s2": ""}
    assert built.passages[1].text.startswith("가상회사 2번")


def test_the_same_view_builds_the_same_passages() -> None:
    blocks = [para("b1", "짧은 첫 줄", order=1), para("b2", LONG, order=2)]
    a, b = P.build_passages(view(blocks)), P.build_passages(view(blocks))
    assert [(p.id, p.text, p.members) for p in a.passages] == [(p.id, p.text, p.members) for p in b.passages]


def test_a_paragraph_continues_over_a_page_break_only_when_the_sentence_is_open() -> None:
    open_end = "가상회사는 사업장 전력 설비를 바꾸는 일을 해마다 이어 가며 그 결과를 점검하는 체계를 두고 있고"
    blocks = [para("b1", open_end, page=1), para("b2", "그 점검 결과를 공개합니다.", page=2)]
    assert [p.members for p in P.build_passages(view(blocks)).passages] == [["b1", "b2"]]
    blocks = [para("b1", open_end + "습니다.", page=1), para("b2", "다음 쪽 새 문단입니다.", page=2)]
    assert [p.members for p in P.build_passages(view(blocks)).passages] == [["b1"], ["b2"]]


# ── 642-1 짧은 문서(GE1b T2) ──


def short_view(pages: int, *, menu_pages: Sequence[int] = ()) -> FakeArtifactView:
    """쪽마다 다른 긴 문단 하나 + menu_pages 쪽에 같은 메뉴 글(되풀이 후보)."""
    blocks = [para(f"b{n}", long(n), page=n, order=2) for n in range(1, pages + 1)]
    blocks += [para(f"m{n}", "지속가능경영 쪽 메뉴", page=n, order=1) for n in menu_pages]
    return view(blocks, pages=pages)


@pytest.mark.parametrize("pages", [1, 2, 3])
def test_a_one_to_three_page_document_keeps_its_paragraphs(pages: int) -> None:
    """642-1: 0.3×쪽 수가 1 아래여도 한 쪽에만 나온 글은 되풀이가 아니다 — 단락 > 0(BASE 는 0)."""
    built = P.build_passages(short_view(pages))
    assert len(built.passages) > 0
    assert sorted(m for p in built.passages for m in p.members) == sorted(f"b{n}" for n in range(1, pages + 1))
    assert built.stat["e 되풀이 글 뺌"] == 0


def test_text_on_two_pages_of_a_short_document_is_still_a_repeat() -> None:
    built = P.build_passages(short_view(3, menu_pages=(1, 2)))
    assert "m1" not in [m for p in built.passages for m in p.members]
    assert built.stat["e 되풀이 글 뺌"] == 2


@pytest.mark.parametrize("pages", [4, 5, 6, 7, 10])
def test_four_pages_or_more_build_the_same_passages_as_before(pages: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """642-1: 4쪽 이상은 문턱 하한 2 를 더해도 앞(0.3×쪽 수)과 같은 단락·셈(손셈 — 보고 「경계 0」)."""
    shapes = [short_view(pages, menu_pages=tuple(range(1, k + 1))) for k in range(1, pages + 1)]
    now = [P.build_passages(v) for v in shapes]
    monkeypatch.setattr(P, "REPEAT_MIN_PAGES", 0)  # 앞 문턱(하한 없음)
    before = [P.build_passages(v) for v in shapes]
    assert [(b.passages, b.stat) for b in now] == [(b.passages, b.stat) for b in before]
