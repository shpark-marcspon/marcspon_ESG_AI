"""자리 → 쪽과 상자. 문서 분해가 곁에 낸 글자 자리(`char-places.json`, 형식 0.1)를 읽는다.

esg-lab `ts/reconcile/src/domain/places.ts`(133줄)를 옮겼다. 읽는 쪽 검증은 `compare/places-cli.ts:17-23` 의 zod 를
옮겼다.
여기서 하는 일은 「그릇의 글에서 몇 번째 글자부터 몇 번째 글자까지」를 상자로 바꾸는 것뿐이다.
숫자가 어디인지는 숫자 뽑기(`facts.py`)가 이미 정했다(`where.span`). 이 파일에는 숫자를 알아보는 규칙이 없다.
PDF 를 열지 않는다. 좌표는 PDF pt, 왼쪽 위 원점이다. **자리의 단위는 UTF-16** 이다(`unit: "utf16"`).

★ TS 와 다르게 한 것: 토막의 `x0`·`x1` 길이가 다르면 검증에서 떨어뜨린다(TS 는 검사하지 않고 NaN 상자를 낸다).
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, cast

from esgapi.reconcile.calc.document import SOURCE_SHAPE, read_source
from esgapi.reconcile.calc.shape import (
    Arr,
    Const,
    Enum,
    Field,
    Int,
    Json,
    Num,
    Obj,
    ReadField,
    Str,
    as_int,
    check,
    read_fields,
)
from esgapi.reconcile.calc.types import (
    Box,
    CharPlaces,
    DocModel,
    Extraction,
    FactWhere,
    Place,
    PlaceContainer,
    PlaceFound,
    PlaceIndex,
    PlaceMissing,
    PlaceRun,
    Unlinked,
)

SCHEMA_VERSION: Final = "0.1"
UNIT: Final = "utf16"
# 두 세로 범위가 한 줄인가의 문턱: 겹친 높이가 낮은 쪽 높이의 절반을 넘는다. places.ts:64
_SAME_LINE_RATIO: Final = 0.5

PLACES_SHAPE: Final = Obj(
    {
        "schema_version": Field(Const(SCHEMA_VERSION)),
        "source": Field(SOURCE_SHAPE),
        "unit": Field(Const(UNIT)),
        "containers": Field(
            Arr(
                Obj(
                    {
                        "id": Field(Str()),
                        "kind": Field(Enum(("block", "cell"))),
                        "page": Field(Int()),
                        "bbox": Field(Arr(Num(), length=4)),
                        "runs": Field(
                            Arr(
                                Obj(
                                    {
                                        "start": Field(Int()),
                                        "y0": Field(Num()),
                                        "y1": Field(Num()),
                                        "x0": Field(Arr(Num())),
                                        "x1": Field(Arr(Num())),
                                    }
                                ),
                                min_length=1,
                            )
                        ),
                    }
                )
            )
        ),
        "unlinked": Field(Arr(Obj({"id": Field(Str()), "page": Field(Int()), "reason": Field(Str())}))),
    }
)

READ_FIELDS: Final[tuple[ReadField, ...]] = read_fields(PLACES_SHAPE)


@dataclass(frozen=True, slots=True)
class PlacesOk:
    places: CharPlaces
    ok: Literal[True] = True


@dataclass(frozen=True, slots=True)
class PlacesInvalid:
    where: str
    problem: str
    ok: Literal[False] = False


PlacesResult = PlacesOk | PlacesInvalid


def validate_places(raw: Json) -> PlacesResult:
    """JSON 값(dict)을 검증해 `CharPlaces` 로. 틀리면 첫 번째로 틀린 자리 하나를 갈래로 돌려준다."""
    problem = check(raw, PLACES_SHAPE)
    if problem is not None:
        return PlacesInvalid(problem.where, problem.problem)
    data = cast("Mapping[str, Json]", raw)
    containers: list[PlaceContainer] = []
    for ci, c in enumerate(data["containers"]):
        runs: list[PlaceRun] = []
        for ri, r in enumerate(c["runs"]):
            if len(r["x0"]) != len(r["x1"]):
                return PlacesInvalid(f"containers[{ci}].runs[{ri}]", "x0 과 x1 의 길이가 다르다")
            runs.append(PlaceRun(as_int(r["start"]), r["y0"], r["y1"], tuple(r["x0"]), tuple(r["x1"])))
        bbox = c["bbox"]
        containers.append(
            PlaceContainer(c["id"], c["kind"], as_int(c["page"]), (bbox[0], bbox[1], bbox[2], bbox[3]), tuple(runs))
        )
    unlinked = tuple(Unlinked(u["id"], as_int(u["page"]), u["reason"]) for u in data["unlinked"])
    return PlacesOk(CharPlaces(read_source(data["source"]), tuple(containers), unlinked))


def _same_line(a: Box, b: Box) -> bool:
    """두 세로 범위가 한 줄인가 (`py/docparse/charplaces.py` 의 `same_line` 과 같다). places.ts:62-65"""
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    return overlap > _SAME_LINE_RATIO * min(a[3] - a[1], b[3] - b[1])


def span_boxes(
    container: PlaceContainer, start: int | None = None, end: int | None = None
) -> tuple[tuple[Box, ...], int]:
    """그릇의 글자 범위 [start, end) 의 상자(줄마다 하나)와 좌표가 있던 글자의 수. 범위를 안 주면 글 전체.

    places.ts:68-88
    """
    boxes: list[Box] = []
    covered = 0
    for run in container.runs:
        run_end = run.start + len(run.x0)
        lo = max(run.start if start is None else start, run.start)
        hi = min(run_end if end is None else end, run_end)
        if lo >= hi:
            continue
        covered += hi - lo
        x0 = math.inf
        x1 = -math.inf
        for k in range(lo - run.start, hi - run.start):
            x0 = min(x0, run.x0[k])
            x1 = max(x1, run.x1[k])
        box: Box = (x0, run.y0, x1, run.y1)
        if boxes and _same_line(boxes[-1], box):
            last = boxes[-1]
            boxes[-1] = (min(last[0], box[0]), min(last[1], box[1]), max(last[2], box[2]), max(last[3], box[3]))
        else:
            boxes.append(box)
    return tuple(boxes), covered


def container_id_of(where: FactWhere) -> str | None:
    """자리가 가리키는 그릇의 ID: 표의 칸이면 `표ID:r행c열`, 글 블록이면 블록 ID. 문서 모델의 자리가 아니면 None."""
    if where.sheet is not None:
        return None
    if where.grid_id is not None and where.row is not None and where.col is not None:
        return f"{where.grid_id}:r{where.row}c{where.col}"
    return where.block_id


def index_places(places: CharPlaces) -> PlaceIndex:
    return PlaceIndex(
        containers={container.id: container for container in places.containers},
        unlinked=frozenset(item.id for item in places.unlinked),
    )


def place_of_where(where: FactWhere, index: PlaceIndex | None) -> Place:
    """자리(`where`) 하나의 쪽과 상자. 글 속 숫자면 그 글자 범위, 표의 숫자 칸이면 칸의 글 전체다. places.ts:107-118"""
    if index is None:
        return PlaceMissing("no_places")
    container_id = container_id_of(where)
    if container_id is None:
        return PlaceMissing("not_in_document")
    container = index.containers.get(container_id)
    if container is None:
        return PlaceMissing("container_unlinked" if container_id in index.unlinked else "container_missing")
    span = where.span
    boxes, covered = span_boxes(container, span.start if span else None, span.end if span else None)
    if len(boxes) == 0:
        return PlaceMissing("no_glyphs_in_span")
    last = container.runs[-1]
    length = span.end - span.start if span else last.start + len(last.x0)
    return PlaceFound(container.page, boxes, container.bbox, covered, length)


def locate_place(fact_id: str, extraction: Extraction, places: CharPlaces | PlaceIndex | None) -> Place:
    """값 후보의 ID(`p3-t1:r2c4`, `p3-t1:r2c4#n1`, `p3-b2#n3`) → 쪽과 상자. places.ts:124-129

    `extraction` 은 같은 문서 모델에서 뽑은 것이어야 한다. `places` 가 없으면(좌표 없이 분해한 문서) `no_places` 다.
    """
    fact = next((item for item in extraction.facts if item.id == fact_id), None)
    if fact is None:
        return PlaceMissing("unknown_id")
    if places is None:
        return PlaceMissing("no_places")
    return place_of_where(fact.where, index_places(places) if isinstance(places, CharPlaces) else places)


def same_source(document: DocModel, places: CharPlaces) -> bool:
    """문서 모델과 글자 자리가 같은 PDF 의 것인가. 다르면 자리가 엉뚱한 곳을 가리킨다."""
    return document.source.sha256 == places.source.sha256
