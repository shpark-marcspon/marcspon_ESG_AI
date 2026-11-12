"""`reconcile/service/services/parse.py`: 파서 포트 → 문서 모델 검증 → 글자 자리 → 값 후보. 순수 층(가짜 파서).

★ 무효 조건: 떠 있는 파서와 맞물려 돌린 적이 없다. 가짜 파서는 지은 문서의 JSON 을 **그대로** 돌려준다.
★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.config.env import Config, DbTarget
from esgapi.core.resources.parser import HttpParser
from esgapi.core.resources.ports.parser import PARSE_FAILURE_KINDS, Parsed, ParseFailed, ParseFailureDetail, ParseResult
from esgapi.core.tests.resource_fakes import FakeParser
from esgapi.reconcile.calc.places import locate_place
from esgapi.reconcile.calc.types import PlaceFound, PlaceMissing
from esgapi.reconcile.service.services.parse import (
    PARSE_PROBLEM_KINDS,
    ParsedInput,
    ParseProblem,
    ParserNotConfiguredError,
    default_parser,
    parse_and_extract,
)

SYNTHETIC = Path(__file__).resolve().parent / "golden" / "synthetic"
PDF = b"%PDF-1.7 (synthetic bytes, not a real pdf)"
Json = Any


def load(name: str) -> Json:
    return json.loads((SYNTHETIC / name).read_text(encoding="utf-8"))


def run(result: ParseResult, *, kinds: bool = False) -> ParsedInput | ParseProblem:
    parser = FakeParser({hashlib.sha256(PDF).hexdigest(): result})
    return parse_and_extract(PDF, file_name="reconcile-doc.synthetic.pdf", parser=parser, doc_id="doc", kinds=kinds)


def problem(result: ParseResult) -> ParseProblem:
    found = run(result)
    assert isinstance(found, ParseProblem)
    assert found.ok is False
    return found


def test_from_pdf_bytes_to_candidates_and_boxes() -> None:
    found = run(Parsed(load("document.json"), load("char-places.json")), kinds=True)
    assert isinstance(found, ParsedInput)
    assert (found.ok, found.warnings) == (True, ())
    assert len(found.extraction.facts) == 99
    assert found.extraction.doc_id == "doc"
    assert found.extraction.kinds is not None
    assert found.place_index is not None
    places = [locate_place(fact.id, found.extraction, found.place_index) for fact in found.extraction.facts]
    boxes = [place for place in places if isinstance(place, PlaceFound)]
    assert (len(boxes), len(places)) == (81, 99)  # 못 찾은 18 은 지은 문서가 일부러 뺀 그릇의 것이다
    assert {place.reason for place in places if isinstance(place, PlaceMissing)} == {
        "container_unlinked",
        "container_missing",
        "no_glyphs_in_span",
    }
    plain = run(Parsed(load("document.json"), load("char-places.json")))
    assert isinstance(plain, ParsedInput)
    assert plain.extraction.kinds is None


def test_a_document_of_the_wrong_shape_is_document_invalid() -> None:
    broken = load("document.json")
    broken["blocks"][0]["bbox"] = [1, 2, 3]
    found = problem(Parsed(broken, load("char-places.json")))
    assert (found.kind, found.detail) == ("document_invalid", "blocks[0].bbox: 길이가 4 이어야 한다(받은 것 3)")


def test_places_of_the_wrong_shape_are_places_invalid() -> None:
    broken = load("char-places.json")
    broken["unit"] = "codepoint"
    found = problem(Parsed(load("document.json"), broken))
    assert (found.kind, found.detail) == ("places_invalid", "unit: 'utf16' 여야 한다")


def test_places_from_another_pdf_are_refused_and_no_box_comes_out() -> None:
    """글자 자리의 sha256 이 다르면 붙이지 않는다: 다른 PDF 의 상자를 내지 않는다. (심은 파손 16 이 받아들인다)"""
    other = copy.deepcopy(load("char-places.json"))
    other["source"]["sha256"] = "f" * 64
    found = problem(Parsed(load("document.json"), other))
    assert found.kind == "places_source_mismatch"
    assert "5" * 64 in found.detail
    assert "f" * 64 in found.detail


def test_without_places_the_candidates_still_come_and_every_place_is_no_places() -> None:
    """글자 자리 없이 분해한 산출. 경고는 그대로 올라온다.

    (가짜 파서만 이렇게 돌려준다. http 어댑터에서는 invalid_response 다)
    """
    found = run(Parsed(load("document.json"), None, warnings=("char_places_missing",)))
    assert isinstance(found, ParsedInput)
    assert len(found.extraction.facts) == 99
    assert found.place_index is None
    assert found.warnings == ("char_places_missing",)
    reasons = {locate_place(fact.id, found.extraction, found.place_index) for fact in found.extraction.facts}
    assert reasons == {PlaceMissing("no_places")}


@pytest.mark.parametrize("kind", PARSE_FAILURE_KINDS)
def test_the_three_parser_failures_come_up_as_they_are(kind: str) -> None:
    detail = ParseFailureDetail(status=422, code="password_protected", message="암호가 걸린 PDF 다")
    found = problem(ParseFailed(kind, detail))  # pyright: ignore[reportArgumentType]
    assert (found.kind, found.detail, found.code, found.status) == (
        kind,
        "암호가 걸린 PDF 다",
        "password_protected",
        422,
    )


def test_a_pdf_the_fake_does_not_know_is_rejected() -> None:
    found = parse_and_extract(b"unknown", file_name="x.pdf", parser=FakeParser(), doc_id="doc")
    assert isinstance(found, ParseProblem)
    assert (found.kind, found.code) == ("rejected", "unknown_pdf")


def test_every_problem_kind_is_reachable() -> None:
    assert set(PARSE_PROBLEM_KINDS) == {
        *PARSE_FAILURE_KINDS,
        "document_invalid",
        "places_invalid",
        "places_source_mismatch",
    }


def config(parser_url: str | None, timeout_ms: int = 30_000) -> Config:
    return Config(
        database=DbTarget("h", 5432, "n", "u", "p"),
        edk_public_key_pem="",
        edk_audience="",
        edk_issuer="",
        session_secret="",
        session_ttl_seconds=1,
        parser_url=parser_url,
        parser_timeout_ms=timeout_ms,
    )


def test_default_parser_builds_the_http_adapter_from_the_config() -> None:
    parser = default_parser(config("http://parser.invalid:8000", 12_500))
    assert isinstance(parser, HttpParser)
    assert (parser.base_url, parser.timeout_s) == ("http://parser.invalid:8000", 12.5)


def test_default_parser_without_an_address_is_a_named_error_not_a_silent_fake() -> None:
    with pytest.raises(ParserNotConfiguredError, match="PARSER_URL 이 없다"):
        default_parser(config(None))
