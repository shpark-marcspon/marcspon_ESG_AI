"""C7 — 읽기 뷰 DocArtifactView(view.py). 순수 층 + DB 뷰와 가짜 뷰의 값 같음(업무 층 하나)."""

import hashlib
from typing import Any

import pytest

from esgapi.core.documents.view import DocArtifactView, PlacesNotLoaded
from esgapi.core.tests.artifact_fakes import FakeArtifactView, block, container, fake_document, fake_places, run
from esgapi.core.tests.documents.test_structure import sample

SHA = "c" * 64
EMOJI_TEXT = "ab\U0001f600cd"  # UTF-16 여섯 자리(보충 평면 글자 하나가 둘)


def places() -> dict[str, Any]:
    return fake_places(
        SHA,
        page_count=2,
        containers=[
            # 한 토막: 보충 평면 글자는 두 자리에 같은 상자
            container("p1-e", [run(0, 10, 20, [0, 1, 2, 2, 4, 5], [1, 2, 4, 4, 5, 6])]),
            # 두 토막 한 줄(글자 크기만 다름 — 겹친 높이 8 > 낮은 쪽 8 의 절반)
            container("p1-b2", [run(0, 10, 20, [0, 1, 2], [1, 2, 3]), run(3, 12, 20, [3, 4], [4, 5])]),
            # 두 줄
            container("p2-b1", [run(0, 10, 20, [0, 1, 2], [1, 2, 3]), run(3, 30, 40, [0, 1], [1, 2])], page=2),
            container(
                "p1-t1:r1c1", [run(0, 50, 60, [100, 105, 108, 112, 116], [104, 107, 111, 115, 120])], kind="cell"
            ),
        ],
    )


def document() -> dict[str, Any]:
    doc = sample()
    doc["blocks"].append(block("p1-e", EMOJI_TEXT, order=6, section_id="s2"))
    return doc


def view(*, with_places: bool = True) -> DocArtifactView:
    return FakeArtifactView.from_dicts(document(), places() if with_places else None, artifact_id=7)


def test_pages_blocks_cells() -> None:
    v = view()
    assert (v.artifact_id, v.source_sha256, v.page_count) == (7, SHA, 2)
    assert [p.page for p in v.pages()] == [1, 2]
    assert [b.id for b in v.blocks()] == ["p1-h", "p1-b1", "p1-b2", "p1-b3", "p1-f", "p1-e", "p2-b1", "p2-b2"]
    assert [b.id for b in v.blocks(page=1, region="body")] == ["p1-b1", "p1-b2", "p1-b3", "p1-e"]
    assert [b.id for b in v.blocks(region="footer")] == ["p1-f"]
    assert [b.id for b in v.body_blocks(2)] == ["p2-b1", "p2-b2"]
    found = v.block("p1-b3")
    assert found is not None and (found.kind, found.table_id, found.text) == ("table", "p1-t1", "")
    assert v.block("없음") is None and v.table("없음") is None
    t = v.table("p1-t1")
    assert t is not None and (t.header_rows, t.header_cols, t.header_basis) == (
        (0,),
        (0,),
        "rows_before_first_numeric_row",
    )
    assert (v.cell("p1-t1", 1, 1), v.cell("p1-t1", 2, 0), v.cell("p1-t1", 0, 9)) == ("1,200", None, None)
    assert v.relations("next_block", "p1-b2") == ("p1-b3",) and v.title_path("p1-b2")[-1] == "물 사용 현황"


def test_a_block_without_region_is_body() -> None:
    v = FakeArtifactView.from_dicts(fake_document(SHA, layout=1, blocks=[block("p1-b1", "가", region=None)]))
    assert [b.region for b in v.blocks()] == ["body"]


def test_boxes_one_line_two_lines_and_surrogates() -> None:
    v = view()
    assert v.boxes("p1-e", 2, 4) == ((2.0, 10.0, 4.0, 20.0),)  # 보충 평면 글자 하나 = 두 자리
    assert v.boxes("p1-e", 4, 6) == ((4.0, 10.0, 6.0, 20.0),)  # 그 뒤 글자(자리는 UTF-16)
    assert v.boxes("p1-b2", 0, 5) == ((0.0, 10.0, 5.0, 20.0),)  # 두 토막 한 줄
    assert v.boxes("p2-b1", 1, 5) == ((1.0, 10.0, 3.0, 20.0), (0.0, 30.0, 2.0, 40.0))  # 두 줄
    assert v.boxes("p1-t1:r1c1", 0, 1) == ((100.0, 50.0, 104.0, 60.0),)  # 칸
    assert v.boxes("p1-b1", 0, 2) is None  # 줄 토막 없음
    assert v.boxes("p1-e", 6, 9) == ()  # 범위 밖


def test_boxes_need_places() -> None:
    with pytest.raises(PlacesNotLoaded):
        view(with_places=False).boxes("p1-e", 0, 1)


def test_the_view_hands_out_no_dicts() -> None:
    v = view()
    t = v.table("p1-t1")
    assert t is not None and isinstance(t.cells, tuple) and isinstance(t.cells[0], tuple)
    with pytest.raises(AttributeError):
        t.status = "failed"  # type: ignore[misc]


@pytest.mark.django_db
def test_the_fake_view_equals_the_stored_view(companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch) -> None:
    from esgapi.core.documents import selectors
    from esgapi.core.tests.documents.test_services import World

    a, _ = companies
    world = World(monkeypatch, a)
    pdf = b"%PDF-1.4 view"
    sha = hashlib.sha256(pdf).hexdigest()
    doc, pl = document(), places()
    doc["source"]["sha256"] = pl["source"]["sha256"] = sha
    document_id, etag = world.document(pdf)
    world.parser_returns(pdf, doc, pl)
    ref = world.ensure(document_id, etag)
    stored = selectors.artifact_view(company_id=a, document_id=document_id, artifact_id=ref.id, places=True)
    fake = FakeArtifactView.from_dicts(doc, pl, artifact_id=ref.id)
    assert (stored.pages(), stored.blocks(), stored.page_count) == (fake.pages(), fake.blocks(), fake.page_count)
    assert stored.table("p1-t1") == fake.table("p1-t1")
    for args in (("p1-e", 2, 4), ("p2-b1", 1, 5), ("p1-t1:r1c1", 0, 3)):
        assert stored.boxes(*args) == fake.boxes(*args)
    assert [stored.relations(n, "p1-b2") for n in ("next_block", "title_path")] == [
        fake.relations(n, "p1-b2") for n in ("next_block", "title_path")
    ]
