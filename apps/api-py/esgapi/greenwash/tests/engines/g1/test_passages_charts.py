"""보정 a 도표 단위(engines/g1/passages.py — 밴드 GE1c ① T1~T8). 지어낸 문서·지어낸 도표 라벨 → FakeArtifactView."""

import hashlib
from collections.abc import Sequence
from typing import Any

import numpy as np
import pytest

from esgapi.core.tests.artifact_fakes import (
    FakeArtifactView,
    block,
    fake_chart_labels,
    fake_document,
    section,
    table,
)
from esgapi.greenwash.contracts import result2_shapes as r2
from esgapi.greenwash.engines.g1 import evidence as E
from esgapi.greenwash.engines.g1 import passages as P
from esgapi.greenwash.engines.g1 import ranges as R
from esgapi.greenwash.flows import engine_g1 as G

SHA = "d" * 64
CHART = "p2-c1"
TITLE = "가상 배출 추이"


def long(n: int) -> str:
    """200자 넘는 지어낸 문단(끝이 「다.」)."""
    return f"가상회사 {n}번 사업장은 설비를 바꾸어 전력 사용량을 줄였고 그 효과를 해마다 점검해 공개합니다. " * 4


def para(bid: str, text: str, *, page: int = 2, order: int = 1, region: str = "body") -> dict[str, Any]:
    return block(bid, text, page=page, order=order, region=region, section_id="s1")


def chart(cid: str = CHART, *, page: int = 2, title: str | None = TITLE) -> dict[str, Any]:
    return {
        "id": cid,
        "page": page,
        "bbox": [10.0, 10.0, 200.0, 200.0],
        "form": "bar",
        "orientation": "vertical",
        "title": title,
        "multi_series": True,
        "categories": ["2024", "2025"],
    }


def word(
    container: str,
    text: str,
    *,
    cid: str = CHART,
    role: str = "value",
    category: str | None = "2025",
    series: str | None = None,
) -> dict[str, Any]:
    label = {} if role != "value" else {"category": category, "series": series, "status": "ok"}
    return {
        "chart": cid,
        "container": container,
        "start": 0,
        "end": len(text),
        "text": text,
        "bbox": [20.0, 20.0, 30.0, 30.0],
        "role": role,
        "label": label,
    }


def view(
    blocks: Sequence[dict[str, Any]],
    *,
    tables: Sequence[dict[str, Any]] = (),
    charts: Sequence[dict[str, Any]] = (),
    words: Sequence[dict[str, Any]] = (),
    pages: int = 4,
    labels: bool = True,
) -> FakeArtifactView:
    doc = fake_document(
        SHA,
        page_count=pages,
        blocks=list(blocks),
        tables=list(tables),
        sections=[section("s1", "환경 경영", page_start=1, page_end=pages)],
    )
    cl = fake_chart_labels(SHA, charts=charts, words=words, page_count=pages) if labels else None
    return FakeArtifactView.from_dicts(doc, chart_labels=cl)


def built_of(v: FakeArtifactView) -> P.Built:
    return P.build_passages(v, v.chart_labels())


SHORT = "12 34 56 가상 수치"
T1 = table("t1", [["구분", "2025"], ["간접", "56"]], page=2)


def basic(**kw: Any) -> FakeArtifactView:
    """긴 문단 b1 · 짧은 조각 c1 · 표 t1 · 각주 n1 — 도표 값은 c1 · t1 칸 · b1(마지막) 에."""
    blocks = [
        para("b1", long(1), order=1),
        para("c1", SHORT, order=2),
        block("t1b", page=2, order=3, kind="table", table_id="t1", section_id="s1"),
        para("n1", "※ 가상 주석입니다.", order=4),
    ]
    words = [
        word("c1", "12", category="2024", series="직접"),
        word("c1", "34", category="2025"),
        word("c1", "9", role="tick"),
        word("c1", "77", category=None),
        word("t1:r1c1", "56", category="2025", series="간접"),
        word("b1", "1", category="2024"),
    ]
    return view(blocks, tables=[T1], charts=[chart()], words=words, **kw)


def chart_passage(b: P.Built) -> P.Passage:
    (p,) = [p for p in b.passages if "\n도표: " in p.text or p.text.startswith("도표: ")]
    return p


# ── T1 없음 = BASE 바이트 같음 ──


def _digest(b: P.Built) -> str:
    shape = (
        [(p.id, p.kind, p.pages, p.section_id, p.members, p.text, p.span) for p in b.passages],
        list(b.stat.items()),
        b.units,
        list(b.titles.items()),
        list(b.block_text.items()),
    )
    return hashlib.sha256(repr(shape).encode()).hexdigest()[:16]


def shapes() -> list[FakeArtifactView]:
    """지어낸 셋(라벨 칸 없음 · 라벨이 실려 있어도 넘기지 않음 · 머리·각주·짧은 단락)."""
    menu = [para(f"m{n}", "지속가능경영 쪽 메뉴", page=n, order=9) for n in (1, 2)]
    tiny = [para("a1", "〉 가상 배출량", page=3, order=1), block("t2b", page=3, order=2, kind="table", table_id="t2")]
    tiny[1]["section_id"] = "s1"
    t2 = table("t2", [["항목", "2025"], ["배출", "7"]], page=3)
    return [
        basic(labels=False),
        basic(),
        view(
            [para("h1", "머리띠", region="header"), *menu, *[para(f"b{n}", long(n), page=n) for n in (1, 2)], *tiny],
            tables=[t2],
        ),
    ]


BASE_DIGESTS = ["28cfccb624992b50", "28cfccb624992b50", "da26510204224ca6"]
"""BASE 9ad1e020 의 build_passages(view) 로 지은 셋의 _digest(GE1c 러너가 그 판 passages.py 로 잼 — 보고 ①)."""


def test_t1_no_labels_is_byte_identical_to_base() -> None:
    got = [_digest(P.build_passages(v)) for v in shapes()]
    assert got == BASE_DIGESTS
    assert [_digest(P.build_passages(v, None)) for v in shapes()] == BASE_DIGESTS
    assert all(not k.startswith("a ") for v in shapes() for k in P.build_passages(v).stat)


# ── T2 도표 글 꼴·자리 ──


def test_t2_chart_text_shape_kind_and_place() -> None:
    b = built_of(basic())
    p = chart_passage(b)
    want = (
        f"도표: {TITLE}\n2024 · 직접 | 12\n2025 | 34\n2025 · 간접 | 56\n2024 | 1\n"
        f"원문: {SHORT} / 구분 | 2025 / 간접 | 56\n주: ※ 가상 주석입니다."
    )
    assert p.kind == "table"
    assert p.text.split("\n", 1)[1] == want
    assert p.pages == [2]
    unit = next(u for u in b.units if u.id == CHART)
    assert unit.rows == (("2024", "직접", "12"), ("2025", "", "34"), ("2025", "간접", "56"), ("2024", "", "1"))
    # 자리 = 첫 그릇(c1) 바로 앞 — b1 문단 뒤
    ids = [u.id for u in b.units]
    assert ids == ["b1", CHART]
    assert b.stat["a 도표 단위"] == 1 and b.stat["a 흡수한 조각"] == 2 and b.stat["a 덮인 도표"] == 0


def test_t2_chart_goes_right_before_its_first_container() -> None:
    """첫 그릇이 긴 문단(안 먹힘)이어도 도표 단위는 그 바로 앞에 선다."""
    blocks = [para("b0", long(0), order=1), para("c1", long(1), order=2), para("b9", long(9), order=3)]
    v = view(blocks, charts=[chart()], words=[word("c1", "12")])
    assert [u.id for u in built_of(v).units] == ["b0", CHART, "c1", "b9"]


# ── T3 먹는 문턱 ──


@pytest.mark.parametrize(("n", "eaten"), [(200, True), (201, False)])
def test_t3_eats_containers_up_to_200_chars_and_tables(n: int, eaten: bool) -> None:
    text = ("가" * (n - 3)) + " 42"
    assert len(text) == n
    v = view([para("c1", text)], charts=[chart()], words=[word("c1", "42")])
    b = built_of(v)
    ids = [u.id for u in b.units]
    assert (("c1" not in ids) is eaten) and CHART in ids
    assert b.stat["a 흡수한 조각"] == (1 if eaten else 0)


# ── T4 표 칸 그릇 → 표 블록 ──


def test_t4_table_cell_container_maps_to_the_table_block() -> None:
    b = built_of(basic())
    assert "t1b" not in [u.id for u in b.units]
    assert "t1b" in chart_passage(b).members
    assert not [p for p in b.passages if p.members == ["t1b"]]


# ── T5 차례 b → e → a → c ──


def test_t5_footnote_after_a_chart_attaches_to_the_chart() -> None:
    b = built_of(basic())
    p = chart_passage(b)
    assert p.text.endswith("\n주: ※ 가상 주석입니다.")
    assert p.members[-1] == "n1"
    assert b.stat["c 표에 붙인 각주"] == 1


def test_t5_header_and_repeated_blocks_are_not_containers() -> None:
    menu = [para(f"m{n}", "가상 쪽 메뉴 12", page=n, order=9) for n in (1, 2)]
    blocks = [para("h1", "머리 12", region="header", order=1), *menu, para("b1", long(1), order=2)]
    words = [word("h1", "12"), word("m2", "12")]
    v = view(blocks, charts=[chart()], words=words)
    b = built_of(v)
    assert b.stat["a 도표 단위"] == 0
    assert CHART not in [u.id for u in b.units]


# ── T6 members = body 블록 · fold · 근거 꼴 ──


def _evidence_ok(b: P.Built, v: FakeArtifactView, pid: str) -> dict[str, object]:
    idx = E.Index(b, np.ones((len(b.passages), 4), dtype=np.float32))
    ev = G.document_evidence(idx, R.block_order(v), pid, [])
    r2.check_document_evidence([ev])
    return ev


def test_t6_chart_members_are_body_blocks_and_pass_fold_and_check() -> None:
    v = basic()
    b = built_of(v)
    p = chart_passage(b)
    assert p.members == ["c1", "t1b", "n1"]
    assert CHART not in p.members
    body = {x.id for x in v.blocks(region="body")}
    assert all(set(q.members) <= body for q in b.passages)
    ev = _evidence_ok(b, v, p.id)
    assert ev["blockRanges"] == [["c1", "n1"]]


def test_t6_a_chart_that_eats_nothing_keeps_all_its_containers() -> None:
    v = view(
        [para("b1", long(1), order=1), para("b2", long(2), order=2)],
        charts=[chart()],
        words=[word("b1", "1"), word("b2", "2")],
    )
    b = built_of(v)
    p = chart_passage(b)
    assert p.members == ["b1", "b2"]
    assert p.text.endswith("\n원문: ")
    _evidence_ok(b, v, p.id)


# ── T7 값 낱말만 ──


def test_t7_only_categorised_value_words_make_lines() -> None:
    body = chart_passage(built_of(basic())).text.split("\n원문: ")[0]
    assert "| 9" not in body and "| 77" not in body
    assert body.count(" | ") == 4


# ── T8 첫 그릇이 같은 도표 둘 = 랩 꼴 ──


def test_t8_two_charts_on_the_same_first_container_keep_the_last() -> None:
    charts = [chart("p2-c1", title="가상 앞 도표"), chart("p2-c2", title="가상 뒤 도표")]
    words = [word("c1", "12", cid="p2-c1"), word("c1", "34", cid="p2-c2")]
    b = built_of(view([para("c1", SHORT)], charts=charts, words=words))
    units = [u for u in b.units if u.kind == "table"]
    assert [u.id for u in units] == ["p2-c2"]
    assert b.stat["a 도표 단위"] == 2 and b.stat["a 덮인 도표"] == 1
    assert chart_passage(b).text.split("\n", 1)[1].startswith("도표: 가상 뒤 도표\n")


def test_empty_labels_build_the_same_passages_and_units_as_none() -> None:
    """빈 라벨(charts=()·words=()) = None 과 단락·units·글 바이트 같음 — stat 에만 0 인 a 열쇠."""
    for v in shapes()[1:]:
        empty_view = view([], charts=[], words=[])  # 꼴만 쓰려고 지음
        assert empty_view.chart_labels() is not None
        empty = P.build_passages(v, empty_view.chart_labels())
        none = P.build_passages(v)
        assert [(p.id, p.members, p.text) for p in empty.passages] == [(p.id, p.members, p.text) for p in none.passages]
        assert empty.units == none.units and empty.block_text == none.block_text
        assert {k: n for k, n in empty.stat.items() if k not in none.stat} == {
            "a 건너뜀: 도표 없음": 0,
            "a 건너뜀: 그릇 없음": 0,
            "a 건너뜀: 표 블록 없음": 0,
            "a 도표 단위": 0,
            "a 흡수한 조각": 0,
            "a 덮인 도표": 0,
        }


# ── 라벨이 문서와 어긋난 낱말은 건너뛰고 센다(critic 작은 것) ──


def test_a_word_of_an_unknown_chart_is_skipped_and_counted() -> None:
    b = built_of(view([para("c1", SHORT)], charts=[chart()], words=[word("c1", "12", cid="p9-c9")]))
    assert b.stat["a 건너뜀: 도표 없음"] == 1 and b.stat["a 도표 단위"] == 0
    assert [u.id for u in b.units] == ["c1"]


def test_a_word_in_an_unknown_container_is_skipped_and_counted() -> None:
    words = [word("zz9", "12"), word("c1", "34")]
    b = built_of(view([para("c1", SHORT)], charts=[chart()], words=words))
    assert b.stat["a 건너뜀: 그릇 없음"] == 1 and b.stat["a 도표 단위"] == 1
    assert "| 12" not in chart_passage(b).text


def test_a_word_in_a_table_without_a_block_is_skipped_and_counted() -> None:
    words = [word("t9:r0c0", "12"), word("c1", "34")]
    b = built_of(view([para("c1", SHORT)], charts=[chart()], words=words))
    assert b.stat["a 건너뜀: 표 블록 없음"] == 1 and b.stat["a 도표 단위"] == 1
    assert "| 12" not in chart_passage(b).text


def test_a_chart_filled_with_its_container_blocks_is_a_self_passage_of_that_block() -> None:
    """흡수 0 이라 members 를 그릇 블록으로 메운 도표 단락은 그 블록을 대상으로 한 주장에서 자기 단락으로 빠진다."""
    v = view([para("b1", long(1), order=1), para("b2", long(2), order=2)], charts=[chart()], words=[word("b1", "1")])
    b = built_of(v)
    p = chart_passage(b)
    assert p.members == ["b1"]
    idx = E.Index(b, np.ones((len(b.passages), 4), dtype=np.float32))
    assert p.id in idx.self_passages(E.Claim(text="가상 주장 문장", block_ids=("b1",)))


# ── 검증 1 B1·B2·R1 ──


def test_a_table_container_over_200_chars_is_still_eaten() -> None:
    """표 그릇은 칸 글 합이 200자를 넘어도 먹는다(랩 :118 「또는 표」)."""
    big = table("t1", [["구분", "2025"], *[[f"가상 항목 {k} 사업장 전력 사용량", f"{k}0"] for k in range(12)]], page=2)
    blocks = [para("b0", long(0), order=1), block("t1b", page=2, order=2, kind="table", table_id="t1", section_id="s1")]
    b = built_of(view(blocks, tables=[big], charts=[chart()], words=[word("t1:r1c1", "00")]))
    tb = next(u for u in P.units_of(view(blocks, tables=[big])) if u.id == "t1b")
    assert len(tb.text) > P.CHART_EAT_CHARS
    assert "t1b" not in [u.id for u in b.units]
    assert chart_passage(b).members == ["t1b"]


def test_a_chart_without_a_title_starts_with_an_empty_title_line() -> None:
    b = built_of(view([para("c1", SHORT)], charts=[chart(title=None)], words=[word("c1", "12")]))
    unit = next(u for u in b.units if u.id == CHART)
    assert unit.text.split("\n", 1)[0] == "도표: "


def test_chart_members_follow_reading_order_not_word_order() -> None:
    """낱말 차례(c2 → c1)가 읽는 차례(c1 → c2)와 달라도 members 는 읽는 차례다."""
    blocks = [para("c1", "가상 조각 하나 12", order=1), para("c2", "가상 조각 둘 34", order=2)]
    b = built_of(view(blocks, charts=[chart()], words=[word("c2", "34"), word("c1", "12")]))
    assert chart_passage(b).members == ["c1", "c2"]
