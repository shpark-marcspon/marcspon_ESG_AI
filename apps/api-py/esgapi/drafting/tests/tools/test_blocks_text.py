"""쪽 글 어댑터 drafting-blocks@1(tools/blocks_text.py — RP2a §3 S1, 처분 ③ 가). 순수 층. 문서는 지어낸 것이다."""

import hashlib
import json

from esgapi.core.tests.artifact_fakes import FakeArtifactView, block, fake_document, table
from esgapi.drafting.tools import blocks_text

SHA = "b" * 64


def view(**document: object) -> FakeArtifactView:
    return FakeArtifactView.from_dicts(fake_document(SHA, **document))  # type: ignore[arg-type]


def test_s1_body_blocks_in_reading_order_with_tables_as_rows() -> None:
    found = view(
        page_count=3,
        no_text_pages=(3,),
        blocks=(
            block("h", "머리글 가상 회사", page=1, order=1, region="header"),
            block("p2", "둘째 문단", page=1, order=3),
            block("t", kind="table", table_id="t1", page=1, order=4),
            block("h1", "1. 지어낸 제목", page=1, order=2, kind="heading"),
            block("f", "- 1 -", page=1, order=5, region="footer"),
            block("q", "  둘째 쪽 글  ", page=2, order=1),
            block("x", "글자 층 없는 쪽", page=3, order=1),
        ),
        tables=(
            table(
                "t1",
                (("구분", "2024"), ("배출|량", "1,200"), ("", ""), ("줄\n바꿈", "3")),
                footnote_marks=((1, 1, "1)"),),
            ),
        ),
    )
    texts = blocks_text.page_texts(found)
    assert texts == [
        "1. 지어낸 제목\n\n둘째 문단\n\n| 구분 | 2024 |\n| 배출\\|량 | 1,2001) |\n| 줄 바꿈 | 3 |",
        "둘째 쪽 글",
        "",
    ]
    assert "머리글" not in texts[0] and "- 1 -" not in texts[0]


def test_s1_layout_1_blocks_without_region_are_body_and_missing_pages_are_empty() -> None:
    found = view(layout=1, page_count=4, blocks=(block("a", "첫 쪽", page=1, region=None), block("b", "넷째", page=4)))
    assert blocks_text.page_texts(found) == ["첫 쪽", "", "", "넷째"]


def test_s1_pages_sha256_by_hand() -> None:
    texts = ["가상 글", "", 'a"b\\']
    by_hand = hashlib.sha256('["가상 글","","a\\"b\\\\"]'.encode()).hexdigest()
    assert blocks_text.pages_sha256(texts) == by_hand
    assert by_hand == hashlib.sha256(json.dumps(texts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    assert blocks_text.pages_sha256(["가상 글"]) != blocks_text.pages_sha256(["가상 글", ""])
