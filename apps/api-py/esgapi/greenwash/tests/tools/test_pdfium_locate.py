# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
"""문장 위치 — PdfiumCoordinates(밴드 G1d, 발주서 §3 (b)·(c)·(d)). PDF 는 전부 지은 것(tests/pdfbuild.py), 글도 지은 것.

상자 기하(자리·크기·줄 수)는 LATIN 글꼴로 짓는다. KOREAN 글꼴은 글리프가 없어 너비가 /W 의 어림이라 찾기·되읽기만
단언한다(예외: 합자는 KOREAN 글꼴 하나로 ASCII + 합자를 잇는다 — LATIN 의 cp1252 에는 U+FB00 이 없다).

허용 오차: 가로 X_TOL. pdfium 의 글자 상자는 글리프의 잉크 상자라 지은 자리(전진 폭)와 옆 여백만큼 다르다 —
Helvetica 대체 글꼴 10pt 에서 실측 0.2~0.5pt(왼쪽), 오른쪽은 마지막 글자의 오른쪽 여백만큼 안쪽. 세로는 바닥선을 끼고
글자 크기 안(top 은 바닥선 위 0.5×크기~1×크기, bottom 은 바닥선 위아래 0.3×크기 안).
"""

import dataclasses
import gc
import weakref
from collections.abc import Sequence
from typing import Any

import pypdfium2 as pdfium
import pytest

from esgapi.core.flows.types import StepContext, StepOutput
from esgapi.greenwash.engines.e0.ports import MockEmbedding, ScriptedChat
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.colab_e0 import GreenwashAdapters
from esgapi.greenwash.tests import pdfbuild as b
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows.test_colab_e0 import check_shape
from esgapi.greenwash.tests.sample_text import page_texts
from esgapi.greenwash.tools import pdfium_locate as pl
from esgapi.greenwash.tools.coordinates import (
    HEAD_KEEP_MIN,
    MAX_LINES,
    MAX_SENTENCE_CHARS,
    READBACK_EXTRA_MAX,
    TAIL_GAP_MAX,
    TAIL_KEEP_MIN,
    TAIL_LEFT_MAX,
    PdfiumCoordinates,
    is_compact,
)
from esgapi.greenwash.tools.pdftext_pypdf import PypdfText
from esgapi.greenwash.tools.ports import PositionValue

X_TOL = 1.0
SIZE = 10
W, H = 612, 792

Line = tuple[float, float, str]  # (x, 바닥선 y, 글) — 왼쪽 위 원점


def build(
    *pages: Sequence[Line],
    font: str = b.LATIN,
    crop: tuple[float, float, float, float] | None = None,
    rotation: int = 0,
) -> bytes:
    doc = b.Doc()
    for lines in pages:
        page = doc.new_page(W, H)
        for x, y, text in lines:
            page.insert_text((x, y), text, fontsize=SIZE, font=font)
        if crop is not None:
            page.set_cropbox(crop)
        if rotation:
            page.set_rotation(rotation)
    return doc.tobytes()


def locate(pdf: bytes, page: int, sentence: str) -> tuple[PositionValue | None, dict[str, int]]:
    with PdfiumCoordinates() as coordinates:
        return coordinates.locate(pdf, page, sentence), coordinates.stats()


def boxes_of(position: PositionValue | None) -> list[list[float]]:
    assert position is not None
    return position["boxes"]


def assert_line_box(box: Sequence[float], x: float, baseline: float, text: str) -> None:
    left, top, right, bottom = box
    assert abs(left - x) <= X_TOL, (box, x)
    assert x + b.text_length(text, SIZE) - 2 * X_TOL <= right <= x + b.text_length(text, SIZE) + X_TOL, box
    assert baseline - SIZE <= top <= baseline - 0.5 * SIZE, box
    assert baseline - 0.3 * SIZE <= bottom <= baseline + 0.3 * SIZE, box


ONE = "Scope 1 emissions fell by twelve percent."
TWO = ("Our plants cut water use by a fifth", "over the last three reporting years.")
THREE = (
    "We replaced the old boilers at all",
    "four sites with heat pumps and now",
    "buy only certified renewable power.",
)


# ── (b) 한 줄·여러 줄·쪽 번호 ──


def test_one_line_is_one_box_on_the_page_counted_from_one_with_a_top_left_origin() -> None:
    pdf = build([(72, 300, "Filler text on the first page.")], [(72, 100, ONE)])
    position, stats = locate(pdf, 2, ONE)
    assert position is not None and position["page"] == 2
    (box,) = boxes_of(position)
    assert_line_box(box, 72, 100, ONE)
    assert stats["found_tier1"] == 1
    assert locate(pdf, 1, ONE)[0] is None


def test_two_and_three_lines_give_a_box_per_line() -> None:
    pdf = build(
        [(72, 100 + 14 * i, t) for i, t in enumerate(TWO)] + [(72, 300 + 14 * i, t) for i, t in enumerate(THREE)]
    )
    with PdfiumCoordinates() as coordinates:
        two = boxes_of(coordinates.locate(pdf, 1, " ".join(TWO)))
        three = boxes_of(coordinates.locate(pdf, 1, " ".join(THREE)))
        assert coordinates.stats()["found_tier1"] == 2
    assert len(two) == 2 and len(three) == 3
    for i, (box, text) in enumerate(zip(two, TWO, strict=True)):
        assert_line_box(box, 72, 100 + 14 * i, text)
    for i, (box, text) in enumerate(zip(three, THREE, strict=True)):
        assert_line_box(box, 72, 300 + 14 * i, text)


def test_a_header_glued_to_the_sentence_is_dropped_and_only_the_body_is_boxed() -> None:
    # 쪽머리는 쪽 위에 있지만 내용 차례로는 본문 뒤(pdfium 의 차례 = 본문, 쪽머리). 문장은 「쪽머리 + 본문」 꼴.
    body = "Waste sent to landfill dropped to zero at the main site this year."
    pdf = build([(72, 200, body), (72, 40, "Annual Review")])
    position, stats = locate(pdf, 1, "Annual Review " + body)
    (box,) = boxes_of(position)
    assert_line_box(box, 72, 200, body)
    assert stats == {"opened": 1, "found_head": 1}


def test_the_header_is_not_dropped_when_too_little_of_the_sentence_would_remain() -> None:
    body = "Fleet fuel use fell."
    pdf = build([(72, 200, body), (72, 40, "Our Annual Sustainability Review Edition")])
    position, stats = locate(pdf, 1, "Our Annual Sustainability Review Edition " + body)
    assert position is None and stats["none_not_found"] == 1


def test_a_ligature_is_found_and_its_split_letter_does_not_open_a_new_box() -> None:
    word = "The eﬀect on oﬃce energy use"  # ﬀ·ﬃ — pypdf 는 합자 그대로, pdfium 은 푼 글자 둘을 같은 상자로
    pdf = build([(72, 100, word)], font=b.KOREAN)
    position, stats = locate(pdf, 1, word)
    (box,) = boxes_of(position)
    assert abs(box[0] - 72) <= X_TOL, box
    assert stats["found_tier1"] == 1


def test_compatibility_forms_are_found_at_tier_one_by_nfkc() -> None:
    # 전각 숫자·％ 는 NFKC 만 푼다(casefold 는 합자 ﬀ·ﬁ 를 이미 풀지만 전각은 그대로 둔다 — 파손 3 이 겨누는 자리)
    pdf = build([(72, 100, "Water use fell 12% in 2024.")])
    position, stats = locate(pdf, 1, "Water use fell \uff11\uff12\uff05 in \uff12\uff10\uff12\uff14.")
    assert position is not None and stats["found_tier1"] == 1


def test_punctuation_that_differs_is_found_at_tier_two() -> None:
    # 쉼표·쌍점이 쪽에만 있다 — 1단(문장부호 그대로)으로는 못 찾고 2단(글자·숫자만)으로 찾는다
    pdf = build([(72, 100, "Scope 1: 1,200 tCO2eq in 2024.")])
    position, stats = locate(pdf, 1, "Scope 1 1200 tCO2eq in 2024")
    (box,) = boxes_of(position)
    assert_line_box(box, 72, 100, "Scope 1: 1,200 tCO2eq in 2024")  # 문장에 없는 끝 마침표는 상자 밖
    assert stats == {"opened": 1, "found_tier2": 1}


def test_the_guard_numbers_are_the_ones_the_order_set() -> None:
    # 테스트가 상수를 import 해 스스로 맞추지 않도록 값을 못 박는다(발주서 「정한 것」 5·7, 문턱은 (h) 로 정한 값)
    assert (MAX_SENTENCE_CHARS, MAX_LINES, HEAD_KEEP_MIN, READBACK_EXTRA_MAX) == (250, 10, 0.4, 0.3)


# ── (b) None 의 갈래 ──


def test_the_same_sentence_twice_on_a_page_is_none() -> None:
    pdf = build([(72, 100, ONE), (72, 300, ONE)])
    position, stats = locate(pdf, 1, ONE)
    assert position is None and stats["none_multiple"] == 1


def test_a_sentence_not_on_the_page_is_none() -> None:
    position, stats = locate(build([(72, 100, ONE)]), 1, "Nothing like this is printed anywhere.")
    assert position is None and stats["none_not_found"] == 1


def test_a_long_sentence_and_an_eleven_line_block_are_none() -> None:
    # 41자 줄 여섯 = 251자 문장(가드 + 1). 가드가 없으면 6줄로 찾힌다(파손 7).
    long_lines = [(f"part{i} " + "solar wind water heat soil air land sea " * 2)[:41] for i in range(6)]
    long_sentence = " ".join(long_lines)
    assert len(long_sentence) == MAX_SENTENCE_CHARS + 1 and all(x == x.strip() for x in long_lines)
    exact = long_sentence[:-1]  # 250자 — 가드 바로 안쪽
    assert len(exact) == MAX_SENTENCE_CHARS and exact == exact.strip()
    block = [f"row {i:02d} value {i * 7:03d}" for i in range(MAX_LINES + 1)]
    pdf = build(
        [(72, 60 + 14 * i, t) for i, t in enumerate(long_lines)] + [(72, 300 + 14 * i, t) for i, t in enumerate(block)]
    )
    with PdfiumCoordinates() as coordinates:
        assert coordinates.locate(pdf, 1, long_sentence) is None
        assert coordinates.locate(pdf, 1, exact) is not None
        assert coordinates.locate(pdf, 1, " ".join(block)) is None
        assert coordinates.stats()["none_chunk"] == 2
        # 가드 바로 안쪽은 찾는다
        assert coordinates.locate(pdf, 1, " ".join(block[:MAX_LINES])) is not None


def test_quotes_dashes_invisible_letters_and_the_truncation_tail_are_found_at_tier_one() -> None:
    pdf = build(
        [(72, 100, 'We said "net-zero" by 2040 and meant it.'), (72, 200, "Emissions fell sharply in every region.")]
    )
    with PdfiumCoordinates() as coordinates:
        assert coordinates.locate(pdf, 1, "We said “net–ze\xadro” by​ 2040 and meant it.") is not None
        tail = coordinates.locate(pdf, 1, "Emissions fell sharply in" + pl.TRUNC_TAIL)
        assert coordinates.stats() == {"opened": 1, "found_tier1": 2}
    (box,) = boxes_of(tail)
    assert_line_box(box, 72, 200, "Emissions fell sharply in")


# ── (b) 되읽기 ──


def readback(pdf: bytes, position: PositionValue) -> str:
    """받은 상자를 pdfium 좌표로 되돌려 다른 손으로 글을 다시 읽는다(크롭 = 미디어인 쪽)."""
    doc = pdfium.PdfDocument(pdf)
    try:
        textpage = doc[position["page"] - 1].get_textpage()
        return "".join(textpage.get_text_bounded(x0, H - y1, x1, H - y0) for x0, y0, x1, y1 in position["boxes"])
    finally:
        doc.close()


def test_every_box_reads_back_the_sentence_in_order() -> None:
    sentences = [ONE, " ".join(TWO), " ".join(THREE)]
    pdf = build(
        [(72, 100, ONE)]
        + [(72, 200 + 14 * i, t) for i, t in enumerate(TWO)]
        + [(72, 400 + 14 * i, t) for i, t in enumerate(THREE)]
    )
    with PdfiumCoordinates() as coordinates:
        for sentence in sentences:
            position = coordinates.locate(pdf, 1, sentence)
            assert position is not None
            assert pl.readback_ok(
                pl.norm_str(sentence, 2), pl.readback_norm(readback(pdf, position)), READBACK_EXTRA_MAX
            )


def test_korean_is_found_and_reads_back() -> None:
    sentence = "가상상사는 2024년에 폐기물 재활용률 85%를 달성했습니다."
    pdf = build([(72, 100, "기후변화 대응"), (72, 130, sentence)], font=b.KOREAN)
    position, stats = locate(pdf, 1, sentence)
    assert position is not None and stats["found_tier1"] == 1
    assert pl.norm_str(sentence, 2) in pl.readback_norm(readback(pdf, position))


def test_a_box_that_reads_back_someone_elses_text_is_none() -> None:
    # 문장 위에 다른 글이 겹쳐 찍혀(내용 차례로는 뒤) 상자를 되읽으면 남의 글이 30% 넘게 덧붙는다
    pdf = build([(72, 100, "Net zero by 2040."), (72, 100, "OVERPRINTED STAMP")])
    position, stats = locate(pdf, 1, "Net zero by 2040.")
    assert position is None and stats["none_readback"] == 1


def test_readback_allows_a_few_extra_letters_but_not_many() -> None:
    needle = pl.norm_str("net zero by 2040", 2)
    assert pl.readback_ok(needle, "a" + needle[:5] + "x" + needle[5:], READBACK_EXTRA_MAX)
    assert not pl.readback_ok(needle, "x" * len(needle) + needle, READBACK_EXTRA_MAX)
    assert not pl.readback_ok(needle, needle[::-1], READBACK_EXTRA_MAX)
    assert pl.readback_norm("eﬀﬀect") == pl.readback_norm("effect") == "effect"


# ── (b) 문서 한 번 열기, 실패 ──


def test_the_same_bytes_open_the_document_once_and_new_bytes_close_the_old_one() -> None:
    first = build([(72, 100, ONE)])
    second = build([(72, 120, ONE)])
    with PdfiumCoordinates() as coordinates:
        for _ in range(3):
            assert coordinates.locate(first, 1, ONE) is not None
        assert (
            coordinates.locate(bytes(bytearray(first)), 1, ONE) is not None
        )  # 같은 내용, 다른 객체 → sha256 으로 같음
        assert coordinates.stats()["opened"] == 1
        old = coordinates.document
        assert coordinates.locate(second, 1, ONE) is not None
        assert old is not None and old.closed
        assert coordinates.stats()["opened"] == 2
    assert coordinates.document is None and old.closed


def test_many_documents_leave_one_open_and_a_dropped_adapter_is_closed_by_the_collector() -> None:
    coordinates = PdfiumCoordinates()
    seen: list[pl.PdfiumDocument] = []
    for i in range(20):
        coordinates.locate(build([(72, 100 + i, ONE)]), 1, ONE)
        assert coordinates.document is not None
        seen.append(coordinates.document)
    assert [d.closed for d in seen] == [True] * 19 + [False]
    alive = weakref.ref(seen[-1].pdf)
    seen.clear()
    del coordinates
    gc.collect()
    assert alive() is None


def test_broken_bytes_and_a_page_out_of_range_are_none_and_counted() -> None:
    with PdfiumCoordinates() as coordinates:
        assert coordinates.locate(b"%PDF-1.4 not really", 1, ONE) is None
        pdf = build([(72, 100, ONE)])
        assert coordinates.locate(pdf, 2, ONE) is None
        assert coordinates.locate(pdf, 0, ONE) is None
        stats = coordinates.stats()
    assert stats["none_error"] == 3 and stats["error:IndexError"] == 2
    assert sum(v for k, v in stats.items() if k.startswith("error:")) == 3


def test_a_rotated_page_is_none() -> None:
    position, stats = locate(build([(72, 100, ONE)], rotation=90), 1, ONE)
    assert position is None and stats["none_rotated"] == 1


# ── (d) 좌표계 ──


def test_the_upper_sentence_has_the_smaller_top_as_built() -> None:
    upper, lower = "Upper line about solar panels.", "Lower line about wind turbines."
    pdf = build([(72, 500, lower), (72, 80, upper)])  # 내용 차례와 위아래를 엇갈려 놓는다
    with PdfiumCoordinates() as coordinates:
        (up,) = boxes_of(coordinates.locate(pdf, 1, upper))
        (down,) = boxes_of(coordinates.locate(pdf, 1, lower))
    assert up[1] < up[3] < down[1] < down[3]
    assert_line_box(up, 72, 80, upper)
    assert_line_box(down, 72, 500, lower)


def test_a_cropped_page_measures_from_the_crop_top_left() -> None:
    lines = [(100.0, 200.0, ONE)]
    (plain,) = boxes_of(locate(build(lines), 1, ONE)[0])
    (cropped,) = boxes_of(locate(build(lines, crop=(50, 40, 560, 700)), 1, ONE)[0])
    assert cropped == pytest.approx([plain[0] - 50, plain[1] - 40, plain[2] - 50, plain[3] - 40], abs=0.011)
    # mediabox 밖으로 나간 cropbox 는 mediabox 로 잘린다 → 미디어 기준과 같다
    (oversized,) = boxes_of(locate(build(lines, crop=(-30, -20, W + 40, H + 10)), 1, ONE)[0])
    assert oversized == plain


def test_pure_helpers() -> None:
    chars = list("Ab c­d")
    assert pl.norm_map(chars, 1) == ("abcd", [0, 1, 3, 5])
    assert pl.find_all("abab", "ab") == [0, 2]
    assert list(pl.head_drops("aa bb cc dd ee", 1, 0.6)) == ["bb cc dd ee", "cc dd ee"]
    assert pl.drop_unplaced([(0, 0, 0, 0), (1, 0, 2, 1), (1, 0, 2, 1), (2, 0, 3, 1)]) == [(1, 0, 2, 1), (2, 0, 3, 1)]
    assert pl.group_lines([(0, 0, 5, 10), (5, 0, 10, 10), (0, -14, 5, -4)]) == [(0, 0, 10, 10), (0, -14, 5, -4)]
    # 세로 가운데가 줄의 위아래에서 높이(10)의 25% 안이면 같은 줄, 넘으면 새 줄
    assert len(pl.group_lines([(0, 0, 5, 10), (5, 0 + 12.4, 10, 10 + 2.4)])) == 1
    assert len(pl.group_lines([(0, 0, 5, 10), (5, 15.1 - 5, 10, 15.1 + 5)])) == 2
    # 왼쪽 끝이 현재 오른쪽 끝 − 0.5×높이보다 앞이면(뒤로 감) 같은 높이라도 새 줄
    assert len(pl.group_lines([(0, 0, 20, 10), (14.9, 0, 18, 10)])) == 2
    assert len(pl.group_lines([(0, 0, 20, 10), (15.1, 0, 18, 10)])) == 1
    # 너비만 0(높이 있음)인 글자는 남긴다 — 둘 다 0 일 때만 뺀다(AND)
    assert pl.drop_unplaced([(1, 0, 1, 5), (2, 3, 4, 3)]) == [(1, 0, 1, 5), (2, 3, 4, 3)]
    assert pl.to_top_left((10, 20, 30, 40), (5, 0, 100, 100)) == [5, 60, 25, 80]


# ── (c) 흐름 ──


def sample_pdf() -> bytes:
    """sample_text 네 쪽을 KOREAN 글꼴로(한국어라 LATIN 의 cp1252 에 못 담는다). 기하는 단언하지 않는다."""
    doc = b.Doc()
    for text in page_texts():
        page = doc.new_page(1400, 1100)
        for i, line in enumerate(text.split("\n")):
            page.insert_text((40, 40 + 10 * i), line, fontsize=8, font=b.KOREAN)
    return doc.tobytes()


def flow_result(coordinates: PdfiumCoordinates | None) -> dict[str, Any]:
    given = dataclasses.replace(s.inputs(), document=sample_pdf())
    used = GreenwashAdapters(
        pdf_text=PypdfText(), llm=ScriptedChat(), embedding=MockEmbedding(), coordinates=coordinates
    )
    return s.result_of(s.run(given, used))


def test_the_flow_fills_positions_that_fit_the_shape_and_none_without_coordinates() -> None:
    with PdfiumCoordinates() as coordinates:
        boxed = flow_result(coordinates)
        stats = coordinates.stats()
    check_shape(boxed)
    items = boxed["items"]
    assert items
    found = [i for i in items if i["position"] is not None]
    assert all(i["position"]["page"] == i["page"] and i["position"]["boxes"] for i in found)
    assert any(i["sentence"].startswith("가상상사는 100% 무공해 공정") for i in found)
    assert stats["opened"] == 1 and stats.get("found_tier1", 0) == len(found)
    plain = flow_result(None)
    assert [i["position"] for i in plain["items"]] == [None] * len(plain["items"])
    assert [(i["page"], i["sentence"]) for i in plain["items"]] == [(i["page"], i["sentence"]) for i in items]


class Exploding:
    def locate(self, pdf: bytes, page: int, sentence: str) -> PositionValue | None:
        raise AssertionError("dry-run 에서 좌표를 부르면 안 된다")


def test_dry_run_does_not_call_coordinates() -> None:
    carried = {"judge": StepOutput(data={"results": [{"page": 1, "sentence": ONE}, {"page": 2, "sentence": ONE}]})}
    used = GreenwashAdapters(
        pdf_text=PypdfText(), llm=ScriptedChat(), embedding=MockEmbedding(), coordinates=Exploding()
    )
    out = colab.locate(s.inputs(dry_run=True), used, carried, StepContext(resume=None))
    assert out.data == {"positions": [None, None]}
    # 같은 carried 로 dry-run 이 아니면 부른다(이 테스트가 헛돌지 않음)
    with pytest.raises(AssertionError, match="dry-run"):
        colab.locate(s.inputs(), used, carried, StepContext(resume=None))


# ── 대체 갈래 found_tail(밴드 HL1, MARC-ISSUE-313 F1) ──
# pypdf 문장 자르기가 쪽 머리띠 줄을 첫 문장 앞에 붙여 문장이 250자를 넘고, 온 문장은 pdfium 쪽 글에 이어진 채로 없다.
# 그릴 차례 = pdfium 의 글 차례: 본문을 먼저, 머리띠·옆 탭을 뒤에 그려 「머리띠 + 옆 탭 + 본문」이 쪽 글에서 끊긴다.

BANNER = (
    "Imaginary Holdings Integrated Annual Review Twenty Thirty Edition",
    "Quarterly Outlook Volume Seven Planet Section Overview Pages",
)
TAB = "Climate"
BODY = (
    "Our twelve plants switched their boilers to captured biogas and",
    "the delivery fleet now runs on batteries charged by rooftop solar",
    "panels installed across every warehouse in the eastern region.",
)
FAR = "Readers may ask the team at any time."


def banner_page(body: Sequence[Line]) -> list[Line]:
    return [*body, (72, 30, BANNER[0]), (72, 44, BANNER[1]), (560, 200, TAB)]


def glued(*body: str) -> str:
    return " ".join([*BANNER, TAB, *body])


def test_a_banner_glued_sentence_is_boxed_by_its_compact_tail() -> None:
    pdf = build(banner_page([(72, 200 + 14 * i, t) for i, t in enumerate(BODY)]))
    sentence = glued(*BODY)
    assert len(sentence) > MAX_SENTENCE_CHARS
    with PdfiumCoordinates() as coordinates:
        position = coordinates.locate(pdf, 1, sentence)
        assert coordinates.stats() == {"opened": 1, "found_tail": 1}
    boxes = boxes_of(position)
    assert len(boxes) == 3
    for i, (box, text) in enumerate(zip(boxes, BODY, strict=True)):
        assert_line_box(box, 72, 200 + 14 * i, text)
    assert position is not None
    assert pl.readback_norm(readback(pdf, position)) == pl.norm_str(" ".join(BODY), 2)  # 머리띠·옆 탭은 상자 밖


def test_a_banner_glued_sentence_whose_tail_is_scattered_is_none() -> None:
    lower = [(72, 200, BODY[0]), (72, 214, BODY[1]), (72, 600, FAR)]  # 셋째 줄이 쪽 아래로 멀리
    aside = [(72, 200, BODY[0]), (72, 214, BODY[1]), (300, 228, FAR)]  # 셋째 줄이 왼쪽 끝에서 튐
    pdf = build(banner_page(lower), banner_page(aside))
    sentence = glued(BODY[0], BODY[1], FAR)
    assert len(sentence) > MAX_SENTENCE_CHARS
    with PdfiumCoordinates() as coordinates:
        assert coordinates.locate(pdf, 1, sentence) is None
        assert coordinates.locate(pdf, 2, sentence) is None
        assert coordinates.stats() == {"opened": 1, "none_chunk": 2}


def test_a_banner_glued_sentence_whose_body_is_itself_too_long_is_none() -> None:
    # 본문 다섯 줄이 촘촘해도 250자를 넘으면 덩어리 — 더 짧은 나머지로 본문 한 토막만 칠하지도 않는다
    long_body = (*BODY, *BODY[:2])
    assert len(" ".join(long_body)) > MAX_SENTENCE_CHARS
    pdf = build(banner_page([(72, 200 + 14 * i, t) for i, t in enumerate(long_body)]))
    position, stats = locate(pdf, 1, glued(*long_body))
    assert position is None and stats == {"opened": 1, "none_chunk": 1}


def test_a_banner_glued_sentence_whose_body_is_on_the_page_twice_is_none() -> None:
    # 남은 조각이 두 군데면 어느 쪽도 칠하지 않는다(대체 갈래의 여러 곳 가드)
    twice = [(72, 200 + 14 * i, t) for i, t in enumerate(BODY)] + [(72, 500 + 14 * i, t) for i, t in enumerate(BODY)]
    position, stats = locate(build(banner_page(twice)), 1, glued(*BODY))
    assert position is None and stats == {"opened": 1, "none_chunk": 1}


def test_a_banner_glued_sentence_whose_tail_box_reads_back_someone_elses_text_is_none() -> None:
    # 본문 줄마다 다른 글이 겹쳐 찍혀(내용 차례로는 머리띠 뒤) 상자를 되읽으면 남의 글이 덧붙는다(대체 갈래의 되읽기)
    body = [(72, 200 + 14 * i, t) for i, t in enumerate(BODY)]
    stamps = [(72, 200 + 14 * i, "OVERPRINTED STAMP " * 3) for i in range(len(BODY))]
    position, stats = locate(build(banner_page(body) + stamps), 1, glued(*BODY))
    assert position is None and stats == {"opened": 1, "none_chunk": 1}


def test_sentences_found_today_do_not_take_the_tail_branch() -> None:
    pdf = build(banner_page([(72, 200 + 14 * i, t) for i, t in enumerate(BODY)]))
    with PdfiumCoordinates() as coordinates:
        body = boxes_of(coordinates.locate(pdf, 1, " ".join(BODY)))
        head = boxes_of(coordinates.locate(pdf, 1, f"{TAB} " + " ".join(BODY)))
        tail = boxes_of(coordinates.locate(pdf, 1, glued(*BODY)))
        assert coordinates.stats() == {"opened": 1, "found_tier1": 1, "found_head": 1, "found_tail": 1}
    assert body == head == tail


def test_the_tail_numbers_and_the_compact_rule() -> None:
    assert (TAIL_KEEP_MIN, TAIL_GAP_MAX, TAIL_LEFT_MAX) == (0.4, 1.2, 1.0)
    line = (72.0, 700.0, 400.0, 710.0)  # 높이 10

    def below(dy: float, dx: float = 0.0) -> pl.Box:
        return (line[0] + dx, line[1] - dy, line[2], line[3] - dy)

    assert is_compact([line]) and is_compact([line, below(14), below(28)])
    assert is_compact([(200.0, 700.0, 400.0, 710.0), below(14)])  # 첫 줄은 줄 가운데서 시작해도 된다
    assert not is_compact([line, below(10 + 13)])  # 틈 13 > 1.2 × 10
    assert not is_compact([line, below(-14)])  # 위로 감
    assert not is_compact([line, below(14, dx=11)])  # 둘째 줄이 오른쪽으로 튐
    assert not is_compact([(60.0, 700.0, 400.0, 710.0), below(14, dx=0), below(28, dx=-11)])  # 셋째 줄이 왼쪽으로 튐
