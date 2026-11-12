"""PDF 하나를 파서에 보내 값 후보와 상자의 색인까지 잇는다. 저장·큐·경로 없음. Django 를 쓰지 않는다.

차례: 포트 호출 → 문서 모델 검증 → 글자 자리 검증 + 같은 PDF 인지(sha256) → 값 후보 뽑기.
실패는 던지지 않고 `ParseProblem` 의 갈래로 돌려준다. 파서의 실패 세 갈래는 이름 그대로 올라온다.

★ 무효 조건: 떠 있는 파서(services/parser)와 맞물려 돌린 적이 없다(PD2 병합 뒤). 이 파일의 테스트는 가짜 파서로 잰다.
  이것을 부르는 경로·태스크는 아직 없다.
"""

from dataclasses import dataclass
from typing import Literal

from esgapi.config.env import Config
from esgapi.core.resources import parser as parser_adapters
from esgapi.core.resources.ports.parser import DocumentParser, ParseFailed
from esgapi.reconcile.calc.document import DocumentInvalid, validate_document
from esgapi.reconcile.calc.facts import extract_document
from esgapi.reconcile.calc.places import PlacesInvalid, index_places, same_source, validate_places
from esgapi.reconcile.calc.types import DocModel, Extraction, PlaceIndex

ParseProblemKind = Literal[
    "rejected",  # 파서: 이 입력은 다시 해도 안 된다
    "unavailable",  # 파서: 잠깐의 문제일 수 있다
    "invalid_response",  # 파서: 200 인데 약속한 꼴이 아니다
    "document_invalid",  # 문서 모델이 읽는 쪽의 꼴이 아니다
    "places_invalid",  # 글자 자리가 읽는 쪽의 꼴이 아니다
    "places_source_mismatch",  # 글자 자리가 다른 PDF 의 것이다(sha256 이 다르다). 다른 문서의 상자를 내지 않는다
]
PARSE_PROBLEM_KINDS: tuple[ParseProblemKind, ...] = (
    "rejected",
    "unavailable",
    "invalid_response",
    "document_invalid",
    "places_invalid",
    "places_source_mismatch",
)


@dataclass(frozen=True, slots=True)
class ParsedInput:
    document: DocModel
    extraction: Extraction
    place_index: PlaceIndex | None  # None 이면 글자 자리 없이 분해한 문서다: 값 후보는 있고 자리는 `no_places` 다
    warnings: tuple[str, ...] = ()  # 파서가 붙인 경고가 그대로 올라온다
    ok: Literal[True] = True


@dataclass(frozen=True, slots=True)
class ParseProblem:
    kind: ParseProblemKind
    detail: str
    code: str | None = None  # 파서가 준 오류 코드(`password_protected` …). 파서의 실패일 때만
    status: int | None = None  # 파서의 HTTP 상태 코드. 파서의 실패일 때만
    ok: Literal[False] = False


class ParserNotConfiguredError(Exception):
    """PARSER_URL 이 없다."""


def default_parser(config: Config) -> DocumentParser:
    """설정의 주소와 시간 제한으로 http 어댑터를 만든다. 주소가 없으면 조용히 가짜로 넘어가지 않고 이름 있는 오류다."""
    if config.parser_url is None:
        raise ParserNotConfiguredError("PARSER_URL 이 없다. 파서를 부르려면 환경 변수 PARSER_URL 에 파서의 주소를 준다")
    return parser_adapters.make("http", base_url=config.parser_url, timeout_s=config.parser_timeout_ms / 1000)


def parse_and_extract(
    pdf: bytes, *, file_name: str, parser: DocumentParser, doc_id: str, kinds: bool = False
) -> ParsedInput | ParseProblem:
    result = parser.parse(pdf, file_name=file_name)
    if isinstance(result, ParseFailed):
        return ParseProblem(result.kind, result.detail.message, code=result.detail.code, status=result.detail.status)

    checked = validate_document(result.document)
    if isinstance(checked, DocumentInvalid):
        return ParseProblem("document_invalid", f"{checked.where}: {checked.problem}")
    document = checked.document

    place_index: PlaceIndex | None = None
    if result.char_places is not None:
        places = validate_places(result.char_places)
        if isinstance(places, PlacesInvalid):
            return ParseProblem("places_invalid", f"{places.where}: {places.problem}")
        if not same_source(document, places.places):
            return ParseProblem(
                "places_source_mismatch",
                f"문서 모델의 sha256 {document.source.sha256} 과 "
                f"글자 자리의 sha256 {places.places.source.sha256} 이 다르다",
            )
        place_index = index_places(places.places)

    extraction = extract_document(document, doc_id, kinds=kinds)
    return ParsedInput(document, extraction, place_index, result.warnings)
