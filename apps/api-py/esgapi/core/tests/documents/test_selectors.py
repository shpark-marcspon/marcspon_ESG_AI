"""C8·C9 — 읽기 포트(selectors.py)의 회사 범위와 jsonb 를 싣지 않음(e7 ⑬). 업무 층."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from esgapi.core.documents import selectors
from esgapi.core.documents.contract import ArtifactNotFound, ArtifactRef
from esgapi.core.documents.view import PlacesNotLoaded
from esgapi.core.tests.documents.test_services import PDF, World

pytestmark = pytest.mark.django_db

BODY_COLUMNS = ('"core_document_artifacts"."document"', '"core_document_artifacts"."char_places"')


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> tuple[World, int, str, ArtifactRef]:
    world = World(monkeypatch, companies[0])
    document_id, etag = world.document(PDF)
    world.parser_returns(PDF)
    ref = world.ensure(document_id, etag)
    assert isinstance(ref, ArtifactRef)
    return world, document_id, etag, ref


def test_another_company_sees_nothing(stored: tuple[World, int, str, ArtifactRef], companies: tuple[int, int]) -> None:
    world, document_id, etag, ref = stored
    a, b = companies
    assert selectors.find_artifact(company_id=a, document_id=document_id, etag=etag, layout=2) == ref
    assert selectors.find_artifact(company_id=b, document_id=document_id, etag=etag, layout=2) is None
    assert selectors.find_by_source(company_id=b, sha256=ref.source_sha256, layout=2) is None
    assert selectors.source_of(company_id=b, document_id=document_id) is None
    with pytest.raises(ArtifactNotFound):
        selectors.artifact_view(company_id=b, document_id=document_id, artifact_id=ref.id)
    assert selectors.artifact_view(company_id=a, document_id=document_id, artifact_id=ref.id).artifact_id == ref.id
    del world


def test_an_artifact_id_alone_does_not_open_it(stored: tuple[World, int, str, ArtifactRef]) -> None:
    world, _document_id, _etag, ref = stored
    other_id, _ = world.document(b"%PDF-1.4 not linked")  # 같은 회사, 이음 없는 문서
    with pytest.raises(ArtifactNotFound):
        selectors.artifact_view(company_id=world.company_id, document_id=other_id, artifact_id=ref.id)


def test_find_and_lists_carry_no_body(stored: tuple[World, int, str, ArtifactRef]) -> None:
    world, document_id, etag, ref = stored
    with CaptureQueriesContext(connection) as queries:
        selectors.find_artifact(company_id=world.company_id, document_id=document_id, etag=etag, layout=2)
        selectors.find_by_source(company_id=world.company_id, sha256=ref.source_sha256, layout=2)
    sql = " ".join(q["sql"] for q in queries.captured_queries)
    assert sql and not [column for column in BODY_COLUMNS if column in sql]
    with CaptureQueriesContext(connection) as queries:
        view = selectors.artifact_view(company_id=world.company_id, document_id=document_id, artifact_id=ref.id)
    sql = " ".join(q["sql"] for q in queries.captured_queries)
    assert BODY_COLUMNS[0] in sql and BODY_COLUMNS[1] not in sql  # places=False — 글자 자리 0
    with pytest.raises(PlacesNotLoaded):
        view.boxes("p1-b1", 0, 1)
    with CaptureQueriesContext(connection) as queries:
        selectors.artifact_view(company_id=world.company_id, document_id=document_id, artifact_id=ref.id, places=True)
    assert BODY_COLUMNS[1] in " ".join(q["sql"] for q in queries.captured_queries)
