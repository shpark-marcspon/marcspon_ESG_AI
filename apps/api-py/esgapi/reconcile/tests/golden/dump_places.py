"""골든 덤프의 여덟째 구획 `places`: 값 후보마다 `locate_place`, 값 아님마다 `place_of_where`.

`dump.mts` 의 같은 구획과 견준다.
"""

from typing import Any

from esgapi.reconcile.calc.document import DocumentInvalid, validate_document
from esgapi.reconcile.calc.facts import extract_document
from esgapi.reconcile.calc.places import (
    PlacesInvalid,
    index_places,
    locate_place,
    place_of_where,
    same_source,
    validate_places,
)
from esgapi.reconcile.calc.types import Place, PlaceFound
from esgapi.reconcile.tests.golden.dump import DumpInputError

Json = Any
SECTIONS = ("places",)


def place_json(place: Place) -> Json:
    if isinstance(place, PlaceFound):
        return {
            "found": True,
            "page": place.page,
            "boxes": [list(box) for box in place.boxes],
            "containerBox": list(place.container_box),
            "covered": place.covered,
            "length": place.length,
        }
    return {"found": False, "reason": place.reason}


def dump_places(document_json: Json, places_json: Json, doc_id: str) -> dict[str, Json]:
    checked = validate_document(document_json)
    if isinstance(checked, DocumentInvalid):
        raise DumpInputError(f"document: {checked.where}: {checked.problem}")
    checked_places = validate_places(places_json)
    if isinstance(checked_places, PlacesInvalid):
        raise DumpInputError(f"char-places: {checked_places.where}: {checked_places.problem}")
    document, places = checked.document, checked_places.places
    extraction = extract_document(document, doc_id)
    index = index_places(places)
    return {
        "places": {
            "sameSource": same_source(document, places),
            "facts": [place_json(locate_place(fact.id, extraction, index)) for fact in extraction.facts],
            "nonValues": [place_json(place_of_where(item.where, index)) for item in extraction.non_values],
        }
    }
