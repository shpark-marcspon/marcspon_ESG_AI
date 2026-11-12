"""자리 ID → 쪽과 상자. TS `places.test.ts` 13건의 뜻을 옮겼다(`factPlaces` 를 쓰는 단언은 `place_of_where` 로).

UTF-16 2건이 읽는 esg-lab 의 본보기 파일은 사본으로 들이지 않고 **같은 뜻의 본보기를 직접 지었다**.
거기에 글자 자리의 읽는 쪽 검증, 정본 스키마와의 구조 대조, 지은 문서 골든의 상자 구획을 더했다.
★ 문서와 숫자, 좌표는 전부 지어낸 것이다(synthetic).
"""

import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from esgapi.reconcile.calc.facts import extract_document, extract_grids
from esgapi.reconcile.calc.notation import scan_numbers
from esgapi.reconcile.calc.places import (
    PLACES_SHAPE,
    READ_FIELDS,
    PlacesInvalid,
    PlacesOk,
    container_id_of,
    index_places,
    locate_place,
    place_of_where,
    same_source,
    span_boxes,
    validate_places,
)
from esgapi.reconcile.calc.shape import read_fields
from esgapi.reconcile.calc.types import (
    PLACE_MISSING_REASONS,
    CharPlaces,
    DocModel,
    DocSource,
    Extraction,
    FactWhere,
    Grid,
    PlaceContainer,
    PlaceFound,
    PlaceMissing,
    PlaceRun,
    Span,
    Unlinked,
)
from esgapi.reconcile.tests.calc.test_document_ts import contradictions
from esgapi.reconcile.tests.golden import dump, dump_places
from esgapi.reconcile.tests.support import HEADER, BlockSpec, TableSpec, synthetic_document

HERE = Path(__file__).resolve().parent
SCHEMAS = HERE / "data" / "schemas"
GOLDEN = HERE / "golden"
Json = Any
W = 5  # 가짜 글자 자리: 그릇마다 한 줄, 글자마다 폭 5pt


def fake_container(container_id: str, kind: str, text: str, line: int, break_at: int | None = None) -> PlaceContainer:
    """빈칸에서 토막을 끊는다(분해가 조각 사이에 끼운 빈칸처럼 좌표가 없다). `break_at` 부터는 다음 줄이다."""
    runs: list[tuple[int, float, list[float], list[float]]] = []
    current: tuple[int, float, list[float], list[float]] | None = None
    for i, ch in enumerate(text):
        if ch == " ":
            current = None
            continue
        second = break_at is not None and i >= break_at
        y0 = 100 + 20 * line + (12 if second else 0)
        x = 10 + W * (i - (break_at or 0)) if second else 10 + W * i
        if current is None or current[1] != y0:
            current = (i, y0, [], [])
            runs.append(current)
        current[2].append(x)
        current[3].append(x + W)
    xs = [v for run in runs for v in (*run[2], *run[3])]
    bbox = (min(xs), min(run[1] for run in runs), max(xs), max(run[1] + 10 for run in runs))
    made = tuple(PlaceRun(start, y0, y0 + 10, tuple(x0), tuple(x1)) for start, y0, x0, x1 in runs)
    return PlaceContainer(container_id, kind, 1, bbox, made)  # pyright: ignore[reportArgumentType]


def fake_places(document: DocModel, skip: tuple[str, ...] = (), breaks: dict[str, int] | None = None) -> CharPlaces:
    containers: list[PlaceContainer] = []
    unlinked: list[Unlinked] = []

    def add(container_id: str, kind: str, text: str) -> None:
        if text == "":
            return
        if container_id in skip:
            unlinked.append(Unlinked(container_id, 1, "text_differs_from_chunks"))
        else:
            containers.append(
                fake_container(container_id, kind, text, len(containers), (breaks or {}).get(container_id))
            )

    for block in document.blocks:
        if block.kind != "table":
            add(block.id, "block", block.text or "")
    for table in document.tables:
        for i, row in enumerate(table.cells):
            for j, text in enumerate(row):
                add(f"{table.id}:r{i}c{j}", "cell", text)
    return CharPlaces(document.source, tuple(containers), tuple(unlinked))


SENTENCE = "임직원 59,498명이 참여했고 협력사 500곳과 공급사 500곳이 함께했다."


# 문서·뽑기·자리는 시험마다(함수 범위) 만든다. 모듈 상수로 두면 mutmut 이 변이를 켜기 전에 한 번 굳어 그 값만 읽는
# 시험이 어느 변이에서도 원본을 본다(scripts/weekly.sh 의 ② — 거짓 생존. MARC-ISSUE-154, 밴드 NK1).
@pytest.fixture
def document() -> DocModel:
    return synthetic_document(
        "places",
        [
            TableSpec(
                "p1-t1",
                cells=[
                    ["구분", "단위", "2023", "2024"],
                    ["직접 배출", "tCO2eq", "1,200", "1,350"],
                    ["간접 배출", "tCO2eq", "5,000", "기준연도 대비 42% 감축, 전년 대비 42% 증가"],
                ],
            )
        ],
        [
            BlockSpec("p1-b1", SENTENCE),
            BlockSpec("p1-b2", "123,456", bbox=(100, 300, 150, 320)),
            BlockSpec("p1-b3", "폐기물은 모두 1, 234 톤이었다."),
        ],
    )


@pytest.fixture
def extraction(document: DocModel) -> Extraction:
    return extract_document(document, "doc")


@pytest.fixture
def places(document: DocModel) -> CharPlaces:
    return fake_places(document, breaks={"p1-b3": len("폐기물은 모두 1, ")})


def container(places: CharPlaces, container_id: str) -> PlaceContainer:
    return next(item for item in places.containers if item.id == container_id)


def x_of(text: str, needle: str, occurrence: int = 1) -> tuple[float, float]:
    at = -1
    for _ in range(occurrence):
        at = text.index(needle, at + 1)
    return (10 + W * at, 10 + W * (at + len(needle)))


def found(extraction: Extraction, places: CharPlaces, fact_id: str) -> PlaceFound:
    place = locate_place(fact_id, extraction, places)
    assert isinstance(place, PlaceFound), fact_id
    return place


def test_every_candidate_id_gets_a_box_in_all_four_buckets(extraction: Extraction, places: CharPlaces) -> None:
    assert {fact.bucket for fact in extraction.facts} == {
        "table_cell",
        "table_text_cell",
        "sentence",
        "number_only_block",
    }
    for fact in extraction.facts:
        assert found(extraction, places, fact.id).found is True
    # TS 는 여기서 `factPlaces`(명령의 표)로 한 번 더 센다. 같은 뜻을 `place_of_where` 로.
    index = index_places(places)
    assert sum(1 for fact in extraction.facts if place_of_where(fact.where, index).found) == len(extraction.facts) == 11


def test_a_numeric_cell_is_the_whole_cell_text_and_equals_the_container_box(
    extraction: Extraction, places: CharPlaces
) -> None:
    place = found(extraction, places, "p1-t1:r1c2")
    assert (place.page, place.boxes, place.covered, place.length) == (1, (container(places, "p1-t1:r1c2").bbox,), 5, 5)


def test_a_number_glued_to_hangul_covers_only_the_number(extraction: Extraction, places: CharPlaces) -> None:
    fact = next(item for item in extraction.facts if item.raw == "59,498")
    place = found(extraction, places, fact.id)
    x0, x1 = x_of(SENTENCE, "59,498")
    assert place.boxes == ((x0, 100, x1, 110),)
    assert x1 < x_of(SENTENCE, "59,498명이")[1]  # 낱말 전체가 아니다


def test_the_same_number_twice_in_a_paragraph_does_not_get_mixed_up(extraction: Extraction, places: CharPlaces) -> None:
    twins = [item for item in extraction.facts if item.where.block_id == "p1-b1" and item.raw == "500"]
    assert [item.where.span.occurrence for item in twins if item.where.span] == [1, 2]
    first, second = found(extraction, places, twins[0].id), found(extraction, places, twins[1].id)
    assert first.boxes[0][:3] == (x_of(SENTENCE, "500", 1)[0], 100, x_of(SENTENCE, "500", 1)[1])
    assert second.boxes[0][:3] == (x_of(SENTENCE, "500", 2)[0], 100, x_of(SENTENCE, "500", 2)[1])
    assert first != second


def test_two_equal_numbers_inside_a_text_cell_are_separate_too(extraction: Extraction, places: CharPlaces) -> None:
    text = "기준연도 대비 42% 감축, 전년 대비 42% 증가"
    twins = [found(extraction, places, "p1-t1:r2c3#n1"), found(extraction, places, "p1-t1:r2c3#n2")]
    assert [place.boxes[0][0] for place in twins] == [x_of(text, "42%", 1)[0], x_of(text, "42%", 2)[0]]
    assert [place.boxes[0][2] for place in twins] == [x_of(text, "42%", 1)[1], x_of(text, "42%", 2)[1]]


def test_a_span_over_two_lines_has_two_boxes(extraction: Extraction, places: CharPlaces) -> None:
    """(심은 파손 11 이 한 줄 판정의 문턱을 0 으로 바꾸면 한 뼘이라도 겹치는 두 줄이 한 상자로 합쳐진다)"""
    target = container(places, "p1-b3")
    start = len("폐기물은 모두 ")
    boxes, covered = span_boxes(target, start, start + len("1, 234"))
    assert len(boxes) == 2
    assert boxes[1][1] > boxes[0][3] - 10  # 둘째 줄은 12pt 아래다(줄 높이 10)
    assert covered == len("1, 234") - 1  # 끼운 빈칸에는 좌표가 없다
    # 분해가 줄 사이에 빈칸을 끼우므로 숫자 뽑기는 두 덩어리로 본다. 덩어리마다 상자가 하나다.
    parts = [found(extraction, places, item.id) for item in extraction.facts if item.where.block_id == "p1-b3"]
    assert [len(place.boxes) for place in parts] == [1, 1]
    # 앞 덩어리 `1` 은 쉼표를 빼고 덮는다(쉼표는 숫자 덩어리 밖이다). 뒤 덩어리 `234` 는 둘째 줄의 상자와 같다.
    first, second = boxes
    assert [place.boxes[0] for place in parts] == [(first[0], first[1], first[2] - W, first[3]), second]


def test_lines_that_overlap_by_less_than_half_stay_two_boxes() -> None:
    """한 줄 판정: 겹친 높이가 낮은 쪽 높이의 **절반을 넘어야** 한 줄이다. 조금 겹친 두 줄은 상자 둘이다.

    (심은 파손 11)
    """
    slightly = PlaceContainer(
        "x",
        "block",
        1,
        (10, 100, 30, 118),
        (PlaceRun(0, 100, 110, (10, 15), (15, 20)), PlaceRun(2, 108, 118, (10,), (15,))),  # 2pt 겹친다(높이 10)
    )
    assert len(span_boxes(slightly, 0, 3)[0]) == 2
    exactly_half = PlaceContainer(
        "x", "block", 1, (10, 100, 30, 115), (PlaceRun(0, 100, 110, (10,), (15,)), PlaceRun(1, 105, 115, (15,), (20,)))
    )
    assert len(span_boxes(exactly_half)[0]) == 2  # 꼭 절반은 「넘는다」가 아니다


def test_runs_on_the_same_line_are_merged_into_one_box() -> None:
    mixed = PlaceContainer(
        "x",
        "block",
        1,
        (10, 100, 30, 110),
        (PlaceRun(0, 100, 110, (10, 15), (15, 20)), PlaceRun(2, 102, 109, (20,), (24,))),
    )
    assert span_boxes(mixed, 0, 3) == (((10, 100, 24, 110),), 3)
    assert span_boxes(mixed) == (((10, 100, 24, 110),), 3)
    assert span_boxes(mixed, 3, 9) == ((), 0)


def test_missing_places_come_with_a_reason(document: DocModel, extraction: Extraction, places: CharPlaces) -> None:
    assert locate_place("p9-b9#n1", extraction, places) == PlaceMissing("unknown_id")
    assert locate_place("p1-t1:r1c2", extraction, None) == PlaceMissing("no_places")
    partial = fake_places(document, skip=("p1-t1:r1c2",))
    assert locate_place("p1-t1:r1c2", extraction, partial) == PlaceMissing("container_unlinked")
    assert locate_place("p1-t1:r1c3", extraction, partial).found is True
    assert locate_place("p1-t1:r1c2", extraction, CharPlaces(places.source, (), ())) == PlaceMissing(
        "container_missing"
    )
    sheet = Grid("s1", "x", "sheet", None, "Sheet1", (("구분", "값"), ("가", "12")), HEADER, "ok", (), (), ())
    excel = extract_grids([sheet], "x", "x.xlsx")
    assert len(excel.facts) == 1
    assert locate_place(excel.facts[0].id, excel, places) == PlaceMissing("not_in_document")
    far = FactWhere(1, None, None, None, None, None, "p1-b1", Span(900, 903, 1))
    assert place_of_where(far, index_places(places)) == PlaceMissing("no_glyphs_in_span")
    assert place_of_where(far, None) == PlaceMissing("no_places")
    assert PlaceMissing("no_places").found is False
    # 못 찾는 까닭 여섯이 다 나왔다.
    assert set(PLACE_MISSING_REASONS) == {
        "unknown_id",
        "no_places",
        "container_unlinked",
        "container_missing",
        "not_in_document",
        "no_glyphs_in_span",
    }
    assert container_id_of(far) == "p1-b1"
    assert container_id_of(excel.facts[0].where) is None


def test_a_numeric_cell_in_two_pieces() -> None:
    """조각이 둘인 숫자 칸: 길이는 칸의 글 전체, 그릇의 상자는 모든 토막을 감싼다."""
    document = synthetic_document(
        "places-two", [TableSpec("p1-t1", cells=[["구분", "값"], ["가", "△ 1,200"], ["나", "300"]])]
    )
    made = fake_places(document, breaks={"p1-t1:r1c1": 2})
    place = locate_place("p1-t1:r1c1", extract_document(document, "doc"), made)
    assert isinstance(place, PlaceFound)
    assert (place.length, place.covered, len(place.boxes)) == (len("△ 1,200"), len("△ 1,200") - 1, 2)
    assert place.container_box == (10, place.boxes[0][1], 10 + W * 5, place.boxes[1][3])


def test_a_long_run() -> None:
    n = 300_000
    long = PlaceContainer(
        "x", "block", 1, (0, 0, n, 10), (PlaceRun(0, 0, 10, tuple(range(n)), tuple(range(1, n + 1))),)
    )
    assert span_boxes(long)[0] == ((0, 0, n, 10),)


def test_document_and_places_must_come_from_the_same_pdf(document: DocModel, places: CharPlaces) -> None:
    assert same_source(document, places) is True
    other = CharPlaces(
        DocSource(places.source.file_name, "f" * 64, places.source.page_count), places.containers, places.unlinked
    )
    assert same_source(document, other) is False


# ── 자리의 단위 (UTF-16). esg-lab 의 본보기(`char-places-utf16.json`)와 같은 뜻으로 직접 지었다 ──

UTF16_TEXT = "😀 임직원 59,498명, 🌱 재생에너지 12%"


def utf16_container() -> PlaceContainer:
    """글자마다 폭 5pt, 보충 평면 글자는 10pt 인 한 줄. 보충 평면 글자의 두 자리는 같은 가로 범위를 가진다."""
    x0: list[float] = []
    x1: list[float] = []
    x = 10.0
    for ch in UTF16_TEXT:
        wide = ord(ch) > 0xFFFF
        width = 10.0 if wide else 5.0
        for _ in range(2 if wide else 1):
            x0.append(x)
            x1.append(x + width)
        x += width
    return PlaceContainer(
        "p1-b1", "block", 1, (10.0, 100.0, x, 110.0), (PlaceRun(0, 100.0, 110.0, tuple(x0), tuple(x1)),)
    )


def test_the_example_has_hangul_and_supplementary_characters_and_one_place_per_utf16_unit() -> None:
    units = len(UTF16_TEXT.encode("utf-16-le")) // 2
    assert any("가" <= ch <= "힣" for ch in UTF16_TEXT)
    assert len(UTF16_TEXT) < units  # 코드포인트 수 < UTF-16 자리 수
    last = utf16_container().runs[-1]
    assert last.start + len(last.x0) == units == 28


def test_the_positions_from_scan_numbers_give_the_expected_boxes() -> None:
    """숫자 뽑기가 낸 start·end(UTF-16)로 상자를 그대로 얻는다.

    (심은 파손 2 가 자리를 코드포인트로 바꾸면 한 칸씩 밀린다)
    """
    tokens = [token for token in scan_numbers(UTF16_TEXT) if token.kind == "value"]
    assert [(token.raw, token.start, token.end) for token in tokens] == [("59,498", 7, 13), ("12%", 25, 28)]
    target = utf16_container()
    # 😀(10pt) + 빈칸 + 임직원 + 빈칸 = 35pt → `59,498` 은 x 45~75.
    assert span_boxes(target, tokens[0].start, tokens[0].end)[0] == ((45.0, 100.0, 75.0, 110.0),)
    assert span_boxes(target, tokens[1].start, tokens[1].end)[0] == ((135.0, 100.0, 150.0, 110.0),)
    units = UTF16_TEXT.encode("utf-16-le")
    for token in tokens:
        assert units[2 * token.start : 2 * token.end].decode("utf-16-le") == token.raw


# ── 글자 자리의 읽는 쪽 검증 ─────────────────────────────────────────────────


def load(path: Path) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_schema_copy_is_the_original_and_every_field_we_read_is_in_it() -> None:
    digest = hashlib.sha256((SCHEMAS / "char-places.schema.json").read_bytes()).hexdigest()
    assert digest == "438ff9193d2a0d17be70acd8c67cbe1a327a3747cae5230b07c83c9116152955"
    assert digest in (SCHEMAS / "README.md").read_text(encoding="utf-8")
    # 정본은 x0·x1 에 글자가 하나 이상이기를 요구한다. 읽는 쪽은 더 넓게 받는다(빈 토막은 상자를 내지 않을 뿐이다).
    # 표는 시험 안에서 낸다 — 모듈 상수 READ_FIELDS 는 import 때 굳어 mutmut 의 변이가 닿지 않는다(MARC-ISSUE-154).
    fields = read_fields(PLACES_SHAPE)
    assert fields == READ_FIELDS
    assert contradictions(fields, load(SCHEMAS / "char-places.schema.json")) == []
    assert len(fields) == 27
    assert {field.path for field in fields if not field.required} == set()


def test_the_synthetic_places_validate_and_wrong_shapes_are_named_branches() -> None:
    raw = load(GOLDEN / "synthetic" / "char-places.json")
    checked = validate_places(raw)
    assert isinstance(checked, PlacesOk)
    assert (len(checked.places.containers), len(checked.places.unlinked)) == (124, 1)

    def broken(change: Callable[[Any], object]) -> PlacesInvalid:
        changed = copy.deepcopy(raw)
        change(changed)
        result = validate_places(changed)
        assert isinstance(result, PlacesInvalid)
        assert result.ok is False
        return result

    assert broken(lambda r: r.update(unit="codepoint")).where == "unit"
    assert broken(lambda r: r.update(schema_version="0.2")).where == "schema_version"
    assert broken(lambda r: r["containers"][0].update(runs=[])).problem == "길이가 1 이상이어야 한다(받은 것 0)"
    assert broken(lambda r: r["containers"][0].update(kind="line")).where == "containers[0].kind"
    assert broken(lambda r: r["containers"][0]["runs"][0].update(start="0")).where == "containers[0].runs[0].start"
    assert broken(lambda r: r.pop("unlinked")).where == "unlinked"
    # ★ TS 와 다르게 한 것: x0 과 x1 의 길이가 다르면 떨어뜨린다(TS 는 검사하지 않고 NaN 상자를 낸다).
    uneven = broken(lambda r: r["containers"][0]["runs"][0]["x1"].pop())
    assert (uneven.where, uneven.problem) == ("containers[0].runs[0]", "x0 과 x1 의 길이가 다르다")


# ── 지은 문서 골든의 상자 구획 ───────────────────────────────────────────────


def test_the_places_section_of_the_synthetic_golden_equals_the_committed_ts_dump() -> None:
    synthetic = GOLDEN / "synthetic"
    ts = load(synthetic / "ts-dump.json")["places"]
    py = dump_places.dump_places(load(synthetic / "document.json"), load(synthetic / "char-places.json"), "synthetic")[
        "places"
    ]
    assert dump.first_difference(ts, py, "places") is None
    reasons = [place.get("reason") for place in (*py["facts"], *py["nonValues"])]
    # 지은 문서에는 못 찾는 갈래 셋과 두 줄에 걸친 숫자가 들어 있다.
    assert {"container_unlinked", "container_missing", "no_glyphs_in_span"} <= set(reasons)
    assert any(place["found"] and len(place["boxes"]) == 2 for place in py["facts"])
    found_count = sum(1 for place in py["facts"] if place["found"])
    assert (found_count, len(py["facts"])) == (dump.size("places", py), 99)
    digest = load(GOLDEN / "lab-digest.places.json")["synthetic"]["sections"]["places"]
    assert (
        digest == {"count": found_count, "sha256": dump.digest(py)} == {"count": found_count, "sha256": dump.digest(ts)}
    )


@pytest.mark.parametrize("reason", PLACE_MISSING_REASONS)
def test_missing_reason_is_a_literal_branch(reason: str) -> None:
    assert PlaceMissing(reason).reason == reason  # pyright: ignore[reportArgumentType]
