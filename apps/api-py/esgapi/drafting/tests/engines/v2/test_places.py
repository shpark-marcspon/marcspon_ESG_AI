"""출처 상자(engines/v2/places.py — RP2b B6): 블록 상자 · 문장 줄 상자(UTF-16 범위) · 토막 없음 → null · 표 행 = 칸 합
하나. 순수 층(지어낸 글자 자리)."""

from typing import Any

from esgapi.core.tests.artifact_fakes import FakeArtifactView, block, container, fake_document, fake_places, run, table
from esgapi.drafting.engines.v2 import material, places

SHA = "d" * 64
TEXT = "가상 문장. 둘째 문장은 두 줄이다."  # 문장 0 = [0, 6) · 문장 1 = [7, 19)


def xs(start: float, count: int, width: float = 4.0) -> tuple[list[float], list[float]]:
    x0 = [start + width * i for i in range(count)]
    return x0, [x + width for x in x0]


def view(containers: list[dict[str, Any]]) -> FakeArtifactView:
    rows = [["구분", "값"], ["사용량", "300"]]
    document = fake_document(
        SHA,
        blocks=[
            block("p1-b1", TEXT, bbox=(50.0, 100.0, 300.0, 140.0)),
            block("p1-b2", "토막 없는 문단.", order=2),
            block("p1-b3", kind="table", table_id="p1-t1", order=3),
        ],
        tables=[table("p1-t1", rows)],
    )
    return FakeArtifactView.from_dicts(document, fake_places(SHA, containers=containers))


def lines() -> list[dict[str, Any]]:
    """p1-b1: 첫 줄 = 자리 0~12(y 100~110, x 50 부터 4pt), 둘째 줄 = 자리 13~19(y 112~122, x 50 부터)."""
    first, second = xs(50.0, 13), xs(50.0, 6)
    return [
        container("p1-b1", [run(0, 100.0, 110.0, *first), run(13, 112.0, 122.0, *second)]),
        container("p1-t1:r1c0", [run(0, 130.0, 138.0, *xs(20.0, 3))], kind="cell"),
        container("p1-t1:r1c1", [run(0, 131.0, 139.0, *xs(120.0, 3))], kind="cell"),
    ]


def given(v: FakeArtifactView, block_id: str) -> material.GivenBlock:
    found = material.locate(v, block_id)
    assert found is not None
    return found


def test_b6_the_block_box_is_the_bbox_and_a_one_line_sentence_has_one_box() -> None:
    v = view(lines())
    found = places.source(given(v, "p1-b1"), 0, v, 31)
    # 문장 0 = 자리 [0, 6) — 첫 줄 토막 안: x0 = 50, x1 = 50 + 4·5 + 4 = 74
    assert found == {
        "documentId": 31,
        "blockId": "p1-b1",
        "page": 1,
        "blockBox": [50.0, 100.0, 300.0, 140.0],
        "sentence": {"index": 0, "boxes": [[50.0, 100.0, 74.0, 110.0]]},
    }


def test_b6_a_two_line_sentence_has_a_box_per_line() -> None:
    v = view(lines())
    found = places.source(given(v, "p1-b1"), 1, v, 31)
    # 문장 1 = [7, 19): 첫 줄 자리 7~12 → x 50+28=78 ~ 50+48+4=102 · 둘째 줄 자리 13~18 → x 50 ~ 50+20+4=74
    assert found["sentence"] == {"index": 1, "boxes": [[78.0, 100.0, 102.0, 110.0], [50.0, 112.0, 74.0, 122.0]]}


def test_b6_no_runs_or_no_index_is_a_null_sentence() -> None:
    v = view(lines())
    assert places.source(given(v, "p1-b2"), 0, v, 31)["sentence"] is None  # 그 블록의 토막이 없음
    assert places.source(given(v, "p1-b1"), None, v, 31)["sentence"] is None
    assert places.source(given(v, "p1-b1"), 5, v, 31)["sentence"] is None  # 범위 밖(검사가 이미 None 으로)
    assert view([]).boxes("p1-b1", 0, 3) is None


def test_b6_a_table_row_is_one_union_box_of_its_cells() -> None:
    v = view(lines())
    found = places.source(given(v, "p1-t1"), 1, v, 31)
    # 칸 r1c0 = x 20~32, y 130~138 · 칸 r1c1 = x 120~132, y 131~139 → 합 하나
    assert found["blockId"] == "p1-t1" and found["blockBox"] == [10.0, 30.0, 190.0, 90.0]
    assert found["sentence"] == {"index": 1, "boxes": [[20.0, 130.0, 132.0, 139.0]]}
    assert places.source(given(v, "p1-t1"), 0, v, 31)["sentence"] is None  # 머리 행 칸엔 토막이 없음
