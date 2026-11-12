"""C3·C4·C5 — 짓는 길 ensure_artifact(services.py)를 진짜 DB 로 잰다. 업무 층(주인 역할·테스트마다 되돌림).
저장소는 FakeStorage(이음매 core/service/services/documents.default_storage), 파서는 FakeParser(HTTP 0).
"""

import hashlib
import uuid
from collections.abc import Callable
from typing import Any, cast

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from esgapi.core.documents import selectors, services
from esgapi.core.documents.contract import (
    EPOCH,
    NUL_REPLACEMENT,
    PARSE_FILE_NAME,
    PARSER_TEXT_MAX,
    ArtifactInvalid,
    ArtifactRef,
    ArtifactRefused,
    ArtifactUnreadable,
)
from esgapi.core.flows.binding import RunRetryLater
from esgapi.core.models import DocumentArtifactRow, DocumentArtifactUseRow, DocumentRow
from esgapi.core.resources.ports.parser import Parsed, ParseFailed, ParseFailureDetail, ParseResult
from esgapi.core.resources.ports.storage import StorageUnavailable
from esgapi.core.service.services import documents as document_services
from esgapi.core.tests.artifact_fakes import block, container, fake_document, fake_places, parsed_for, run, table
from esgapi.core.tests.resource_fakes import FakeParser, FakeStorage
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4 fake one"
OTHER = b"%PDF-1.4 fake two"


class World:
    """한 시험의 바깥: 저장소·파서(가짜)와 문서 행 심기."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, company_id: int) -> None:
        self.company_id = company_id
        self.storage = plug_storage(monkeypatch, FakeStorage())
        self.results: dict[str, ParseResult] = {}
        self.parser = FakeParser()
        self.made = 0  # 파서를 지은 수(부를 때만 짓는다)

    def document(
        self, pdf: bytes, *, sha: bool = True, page_count: int | None = 3, company_id: int | None = None
    ) -> tuple[int, str]:
        company = self.company_id if company_id is None else company_id
        key = f"companies/{company}/documents/{uuid.uuid4()}/original"
        etag = self.storage.put(key, pdf)
        row = DocumentRow.for_company(company).create(
            company_id=company,
            uploaded_by="u",
            file_name="가상.pdf",
            storage_key=key,
            size_bytes=len(pdf),
            etag=etag,
            sha256=hashlib.sha256(pdf).hexdigest() if sha else None,
            status="uploaded",
            page_count=page_count,
        )
        return row.id, etag

    def parser_returns(self, pdf: bytes, document: Any = None, places: Any = None, **kw: Any) -> None:
        if document is None:
            self.results[hashlib.sha256(pdf).hexdigest()] = parsed_for(pdf, **kw)
        else:
            self.results[hashlib.sha256(pdf).hexdigest()] = Parsed(document=document, char_places=places)
        self.renew()

    def parser_fails(self, pdf: bytes, kind: str, code: str | None = None) -> None:
        detail = ParseFailureDetail(status=422, code=code, message="가짜 실패")
        self.results[hashlib.sha256(pdf).hexdigest()] = ParseFailed(kind, detail)  # type: ignore[arg-type]
        self.renew()

    def renew(self) -> None:
        calls, layouts = self.parser.calls, self.parser.layouts
        self.parser = FakeParser(self.results)
        self.parser.calls, self.parser.layouts = calls, layouts

    def make_parser(self) -> FakeParser:
        self.made += 1
        return self.parser

    def ensure(
        self, document_id: int, etag: str, *, layout: int = 2, max_pages: int = 300, company_id: int | None = None
    ) -> Any:
        return services.ensure_artifact(
            self.company_id if company_id is None else company_id,
            document_id,
            etag,
            layout=layout,
            parser=self.make_parser,
            max_pages=max_pages,
        )


def rows() -> tuple[int, int]:
    return DocumentArtifactRow.unscoped.count(), DocumentArtifactUseRow.unscoped.count()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    return World(monkeypatch, companies[0])


# ── C3 짓는 길 ──


def test_first_ensure_parses_once_with_the_fixed_name_and_layout(world: World) -> None:
    document_id, etag = world.document(PDF)
    world.parser_returns(PDF, page_count=3)
    ref = world.ensure(document_id, etag)
    assert isinstance(ref, ArtifactRef) and ref.status == "ready"
    assert world.parser.calls == [(hashlib.sha256(PDF).hexdigest(), PARSE_FILE_NAME)] and world.parser.layouts == [2]
    assert (ref.source_sha256, ref.page_count, ref.parser.layout, ref.parser.name, ref.epoch) == (
        hashlib.sha256(PDF).hexdigest(),
        3,
        2,
        "docparse",
        EPOCH,
    )
    assert ref.body_bytes > 0 and rows() == (1, 1)


@pytest.mark.parametrize("sha", [True, False])
def test_again_reads_neither_storage_nor_parser_nor_writes(world: World, sha: bool) -> None:
    document_id, etag = world.document(PDF, sha=sha)
    world.parser_returns(PDF)
    first = world.ensure(document_id, etag)
    gets, made = len(world.storage.get_calls), world.made
    with CaptureQueriesContext(connection) as queries:
        again = world.ensure(document_id, etag)
    assert again == first and (len(world.storage.get_calls), world.made) == (gets, made)  # ⓐ — 저장소·파서 0
    assert [q["sql"] for q in queries.captured_queries if "INSERT" in q["sql"]] == []
    assert rows() == (1, 1)


@pytest.mark.parametrize("sha", [True, False])
def test_the_same_pdf_in_another_document_only_adds_a_use(world: World, sha: bool) -> None:
    first_id, first_etag = world.document(PDF)
    world.parser_returns(PDF)
    first = world.ensure(first_id, first_etag)
    second_id, second_etag = world.document(PDF, sha=sha)
    gets = len(world.storage.get_calls)
    second = world.ensure(second_id, second_etag)
    assert second == first and len(world.parser.calls) == 1 and world.made == 1  # ⓑ
    assert len(world.storage.get_calls) == gets + (0 if sha else 1)  # sha NULL 이면 바이트로 셈
    assert rows() == (1, 2)


def test_another_company_with_the_same_pdf_parses_anew(world: World, companies: tuple[int, int]) -> None:
    a, b = companies
    mine, my_etag = world.document(PDF)
    theirs, their_etag = world.document(PDF, company_id=b)
    world.parser_returns(PDF)
    first, second = world.ensure(mine, my_etag), world.ensure(theirs, their_etag, company_id=b)
    assert isinstance(first, ArtifactRef) and isinstance(second, ArtifactRef) and first.id != second.id
    assert len(world.parser.calls) == 2 and rows() == (2, 2)
    assert DocumentArtifactRow.for_company(b).count() == 1 and DocumentArtifactRow.for_company(a).count() == 1


def test_a_new_epoch_or_layout_is_a_new_row(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    document_id, etag = world.document(PDF)
    world.parser_returns(PDF)
    first = world.ensure(document_id, etag)
    monkeypatch.setattr(selectors, "EPOCH", EPOCH + 1)
    monkeypatch.setattr(services, "EPOCH", EPOCH + 1)
    second = world.ensure(document_id, etag)
    assert isinstance(second, ArtifactRef) and second.id != first.id and second.epoch == EPOCH + 1
    assert len(world.parser.calls) == 2 and rows() == (2, 2)
    world.parser_returns(PDF, layout=1)
    third = world.ensure(document_id, etag, layout=1)
    assert isinstance(third, ArtifactRef) and third.parser.layout == 1 and rows() == (3, 3)
    assert world.parser.layouts == [2, 2, 1]


# ── C4 실패 ──


def test_the_unreadable_branches(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    document_id, etag = world.document(PDF)
    world.parser_returns(PDF)
    assert world.ensure(document_id + 10_000, etag) == ArtifactUnreadable("document_missing")
    assert world.ensure(document_id, '"other"') == ArtifactUnreadable("object_changed")  # 행의 etag 다름
    key = DocumentRow.for_company(world.company_id).get(pk=document_id).storage_key
    world.storage.put(key, PDF, etag='"moved"')  # 객체의 etag 다름
    assert world.ensure(document_id, etag) == ArtifactUnreadable("object_changed")
    world.storage.put(key, OTHER, etag=etag)  # etag 같고 바이트가 행의 sha 와 다름
    assert world.ensure(document_id, etag) == ArtifactUnreadable("object_changed")
    del world.storage.objects[key]
    assert world.ensure(document_id, etag) == ArtifactUnreadable("ObjectMissing")
    world.storage.fail_with = StorageUnavailable("잠깐")
    with pytest.raises(RunRetryLater):
        world.ensure(document_id, etag)
    monkeypatch.setattr(document_services, "default_storage", lambda: None)
    assert world.ensure(document_id, etag) == ArtifactUnreadable("storage_unconfigured")
    assert world.made == 0 and rows() == (0, 0)


def test_too_many_pages_is_refused_before_the_parser(world: World) -> None:
    document_id, etag = world.document(PDF, page_count=301)
    world.parser_returns(PDF)
    assert world.ensure(document_id, etag) == ArtifactRefused("too_many_pages")
    assert (world.made, world.storage.get_calls, rows()) == (0, [], (0, 0))


@pytest.mark.parametrize("code", ["parse_timeout", "password_protected"])
def test_a_rejection_writes_no_row(world: World, code: str) -> None:
    document_id, etag = world.document(PDF)
    world.parser_fails(PDF, "rejected", code)
    assert world.ensure(document_id, etag) == ArtifactRefused(code)
    assert rows() == (0, 0)


def test_unavailable_retries_later_and_writes_no_row(world: World) -> None:
    document_id, etag = world.document(PDF)
    world.parser_fails(PDF, "unavailable", "busy")
    with pytest.raises(RunRetryLater):
        world.ensure(document_id, etag)
    assert rows() == (0, 0)


def test_an_invalid_answer_or_shape_raises(world: World) -> None:
    document_id, etag = world.document(PDF)
    world.parser_fails(PDF, "invalid_response")
    with pytest.raises(ArtifactInvalid):
        world.ensure(document_id, etag)
    world.parser_returns(PDF, layout=1)  # 판 2 를 물었는데 판 1 이 옴
    with pytest.raises(ArtifactInvalid):
        world.ensure(document_id, etag)
    sha = hashlib.sha256(PDF).hexdigest()
    world.parser_returns(PDF, fake_document(sha), fake_places("d" * 64))  # 글자 자리의 sha 다름
    with pytest.raises(ArtifactInvalid):
        world.ensure(document_id, etag)
    assert rows() == (0, 0)


def test_unknown_page_count_is_checked_after_parsing(world: World) -> None:
    document_id, etag = world.document(PDF, page_count=None)
    world.parser_returns(PDF, page_count=301)
    assert world.ensure(document_id, etag) == ArtifactRefused("too_many_pages")
    assert len(world.parser.calls) == 1 and rows() == (0, 0)


def test_over_the_limit_keeps_a_too_large_row_and_never_parses_again(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(services, "ARTIFACT_MAX_BYTES", 100)
    document_id, etag = world.document(PDF)
    world.parser_returns(PDF)
    first = world.ensure(document_id, etag)
    assert isinstance(first, ArtifactRef) and first.status == "too_large" and first.body_bytes > 100
    row = DocumentArtifactRow.for_company(world.company_id).get(pk=first.id)
    assert (row.document, row.char_places) == (None, None)
    other_id, other_etag = world.document(PDF)
    assert world.ensure(other_id, other_etag) == first and world.ensure(document_id, etag) == first
    assert len(world.parser.calls) == 1 and rows() == (1, 2)


# ── C5 경합 ──


def blind_once(real: Callable[..., ArtifactRef | None]) -> Callable[..., ArtifactRef | None]:
    """처음 한 번은 None, 그 뒤는 진짜 찾기."""
    seen: list[bool] = []

    def find(**kw: Any) -> ArtifactRef | None:
        if not seen:
            seen.append(True)
            return None
        return real(**kw)

    return find


def test_a_racing_artifact_insert_reads_the_winner(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    first_id, first_etag = world.document(PDF)
    world.parser_returns(PDF)
    first = world.ensure(first_id, first_etag)
    # 처음 한 번만 못 본다 — 다른 일꾼이 그 사이에 넣은 것과 같다
    monkeypatch.setattr(selectors, "find_by_source", blind_once(selectors.find_by_source))
    second_id, second_etag = world.document(PDF)
    second = world.ensure(second_id, second_etag)
    assert isinstance(second, ArtifactRef) and second.id == first.id
    assert len(world.parser.calls) == 2 and rows() == (1, 2)  # 파서는 두 번(1차 허용), 행은 하나


def test_a_racing_use_insert_reads_the_winner(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    document_id, etag = world.document(PDF)
    world.parser_returns(PDF)
    first = world.ensure(document_id, etag)
    monkeypatch.setattr(selectors, "find_artifact", blind_once(selectors.find_artifact))
    again = world.ensure(document_id, etag)
    assert again == first and rows() == (1, 1)


# ── NUL·이름 칸(QC3, MARC-ISSUE-481) ──


def test_nul_in_the_parser_text_is_stored_as_fffd_at_the_same_places(world: World) -> None:
    document_id, etag = world.document(PDF)
    sha = hashlib.sha256(PDF).hexdigest()
    document = fake_document(sha, blocks=[block("b1", "가\x00나")], tables=[table("t1", [["머리", "칸\x00"]])])
    box = container("b1", [run(0, 1.0, 2.0, [0.0, 1.0, 2.0], [1.0, 2.0, 3.0])])
    places = fake_places(sha, containers=[box, container("c\x00", [])])  # 글자 자리 쪽 글자 칸에도 NUL
    world.parser_returns(PDF, document, places)
    ref = world.ensure(document_id, etag)
    assert isinstance(ref, ArtifactRef) and ref.status == "ready"
    row = DocumentArtifactRow.for_company(world.company_id).get(pk=ref.id)
    stored, stored_places = cast("dict[str, Any]", row.document), cast("dict[str, Any]", row.char_places)
    text: str = stored["blocks"][0]["text"]
    assert text == f"가{NUL_REPLACEMENT}나"
    assert stored["tables"][0]["cells"] == [["머리", f"칸{NUL_REPLACEMENT}"]]
    assert len(text.encode("utf-16-le")) == len("가\x00나".encode("utf-16-le"))
    assert stored_places["containers"][0] == box  # 글자 자리 상자는 같은 자리
    assert stored_places["containers"][1]["id"] == f"c{NUL_REPLACEMENT}"
    assert world.ensure(document_id, etag) == ref and len(world.parser.calls) == 1  # uses 로 — 재분해 0


def test_a_long_parser_version_is_clipped_into_the_column(world: World) -> None:
    field = DocumentArtifactRow._meta.get_field
    assert field("parser_name").max_length == field("parser_version").max_length == PARSER_TEXT_MAX
    document_id, etag = world.document(PDF)
    sha = hashlib.sha256(PDF).hexdigest()
    document = fake_document(sha)
    document["parser"]["version"] = "9" * (PARSER_TEXT_MAX + 1)
    world.parser_returns(PDF, document, fake_places(sha))
    ref = world.ensure(document_id, etag)
    assert isinstance(ref, ArtifactRef) and ref.status == "ready"
    row = DocumentArtifactRow.for_company(world.company_id).get(pk=ref.id)
    assert row.parser_version == "9" * (PARSER_TEXT_MAX - 1) + "…" and ref.parser.version == row.parser_version
    assert world.ensure(document_id, etag) == ref and len(world.parser.calls) == 1  # uses 로 — 재분해 0
