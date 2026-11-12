"""번역 판 `layout=2` 의 글 손질(밴드 TRD1 커밋 ③): L4 줄 끝 위첨자 문단 잇기.

엔진은 줄 끝 위첨자를 다음 줄 객체의 머리에 붙여 「1)and the」 꼴 조각을 낸다. 합성 1쪽(`layout2_doc._page_superscript`)
에 두 갈래가 있다: 위첨자 조각의 y0 가 소수 자리만 위라 같은 줄의 왼쪽 조각보다 먼저 정렬되는 줄(「1)」), 위첨자 상자가
왼쪽 조각과 조금 겹치는 줄(「2)」). 기본 판(1) 산출에는 단언하지 않는다(발주서 §0 라).
"""

import pytest

from docparse.document import parse_pdf_places
from docparse.engine import open_pdf
from docparse.layout import page_chunks

from . import layout2_doc

PARAGRAPH = [
    "The supply chain plan sets yearly targets for each",
    "partner and reviews progress twice a year so that",
    "the figures stay consistent with the method",
    "1)and the",
    "review panel confirms every change before the",
    "data is published together with the external",
    "2)audit",
    "opinion on the last page of the annex.",
]


@pytest.fixture(scope="module")
def pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("layout2-text") / "layout2.pdf"
    path.write_bytes(layout2_doc.build())
    return path


def test_l4_line_end_superscripts_keep_the_paragraph_whole(pdf):
    document, _ = parse_pdf_places(pdf, layout=2)
    page1 = [b for b in document["blocks"] if b["page"] == 1]
    texts = [b["text"] for b in page1]
    assert texts == [
        "Synthetic layout two report - header band",
        "Line end superscripts",
        " ".join(PARAGRAPH),  # 위첨자 글자(1)·2))는 버리지 않고 글의 차례대로 남는다
        "A second paragraph follows after a clear gap and has no superscript at all, so it stays as it is.",
        "1",
    ]
    assert [b["order"] for b in page1] == list(range(1, len(page1) + 1))


def test_l4_superscript_head_records_where_the_body_starts(pdf):
    with open_pdf(pdf) as opened:
        chunks, _ = page_chunks(opened[0])
    heads = {c.text: c for c in chunks if c.text in ("1)and the", "2)audit")}
    assert set(heads) == {"1)and the", "2)audit"}
    for c in heads.values():
        assert c.body_x0 is not None and c.x0 < c.body_x0 < c.x1  # 위첨자 뒤 본문 글자의 x0
    assert all(c.body_x0 is None for c in chunks if c.text not in heads)


def test_l4_a_smaller_superscript_head_does_not_lift_the_line_bottom():
    """줄 안에서 위첨자 머리 조각만 글씨가 조금 작으면(밑이 위) 그 밑을 줄 밑으로 삼지 않는다: 다음 줄이 같은 문단이다.

    조각은 손으로 짓는다: 왼쪽 조각(8.7pt) · y0 가 조금 위이고 왼쪽 조각과 조금 겹치는 위첨자 머리 조각(7.9pt) ·
    다음 줄(7.9pt). 다음 줄의 y0 는 왼쪽 조각의 밑에서 재면 줄 간격 거름 안이고 위첨자 머리 조각의 밑에서 재면 밖이다.
    """
    from docparse.blocks import build_text_blocks
    from docparse.layout import Chunk

    left = Chunk(40.0, 120.0, 200.0, 131.9, "first line of the note", 8.7)
    head = Chunk(199.8, 119.95, 300.0, 130.9, "3)with a smaller tail", 7.9, body_x0=204.0)
    below = Chunk(40.0, 136.5, 250.0, 145.5, "second line of the note", 7.9)
    blocks = build_text_blocks([below, head, left], layout=2)
    assert [b["text"] for b in blocks] == ["first line of the note 3)with a smaller tail second line of the note"]
