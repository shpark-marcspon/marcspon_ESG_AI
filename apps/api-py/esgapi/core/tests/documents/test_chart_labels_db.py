"""CHL1 ② — 도표 라벨 셋째 칸 chart_labels 의 DB 층: 짓는 길(T10·T12) · EPOCH(T13) · 이주 0005(T15) · 회사 범위(T16).

업무 층(주인 역할·시험마다 되돌림). 파서는 FakeParser, 도표·낱말은 지어낸 것이다.
"""

import hashlib
from typing import Any, cast

import pytest
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from esgapi.core.documents import selectors, services
from esgapi.core.documents.contract import (
    EPOCH,
    ArtifactInvalid,
    ArtifactNotFound,
    ArtifactRef,
    ArtifactRefused,
    body_bytes,
)
from esgapi.core.documents.view import ChartLabels, ChartLabelsNotLoaded, ChartLabelsUnavailable
from esgapi.core.flows.binding import RunRetryLater
from esgapi.core.models import DocumentArtifactRow, DocumentArtifactUseRow
from esgapi.core.resources.ports.parser import Parsed, ParseFailed, ParseFailureDetail, ParseFailureKind, ParseResult
from esgapi.core.tests.artifact_fakes import fake_chart_labels, fake_document, parsed_for
from esgapi.core.tests.documents.test_chart_labels import CHART, word
from esgapi.core.tests.documents.test_services import PDF, World, rows
from esgapi.core.tests.documents.test_tables import artifact
from esgapi.core.tests.resource_fakes import FakeParser

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    return World(monkeypatch, companies[0])


def sha_of(pdf: bytes) -> str:
    return hashlib.sha256(pdf).hexdigest()


def labels_for(pdf: bytes, *words: dict[str, Any]) -> dict[str, Any]:
    return fake_chart_labels(sha_of(pdf), charts=(CHART,), words=words)


def stored(world: World, *, layout: int = 2, chart_labels: dict[str, Any] | None = None) -> tuple[int, ArtifactRef]:
    document_id, etag = world.document(PDF)
    world.parser_returns(PDF, layout=layout, chart_labels=chart_labels)
    ref = world.ensure(document_id, etag, layout=layout)
    assert isinstance(ref, ArtifactRef)
    return document_id, ref


# ── T10 짓는 길이 판 2 에서만 charts 로 부른다 ─────────────────────────────


def test_layout_2_asks_the_parser_for_chart_labels_and_stores_them(world: World) -> None:
    document_id, ref = stored(world, chart_labels=labels_for(PDF, word("16.2")))
    assert world.parser.charts == [True] and world.parser.layouts == [2]
    assert ref.epoch == EPOCH
    view = selectors.artifact_view(
        company_id=world.company_id, document_id=document_id, artifact_id=ref.id, charts=True
    )
    got = view.chart_labels()
    assert got is not None and [w.text for w in got.values()] == ["16.2"]


def test_layout_1_does_not_ask_for_chart_labels(world: World) -> None:
    document_id, ref = stored(world, layout=1)
    assert world.parser.charts == [False] and world.parser.layouts == [1]
    row = DocumentArtifactRow.for_company(world.company_id).get(pk=ref.id)
    assert row.chart_labels is None
    view = selectors.artifact_view(
        company_id=world.company_id, document_id=document_id, artifact_id=ref.id, charts=True
    )
    assert view.chart_labels() is None


def test_a_parser_that_gave_no_labels_stores_null(world: World) -> None:
    """`Parsed.chart_labels is None`(가짜·옛 꼴) → 칸 NULL(1-3 ⑥ — 엄격함은 http 어댑터에서). EPOCH 2·판 2 행의 빈 칸은
    「라벨 못 지음」(ChartLabelsUnavailable — None 이 아니다, ④ N1)."""
    document_id, ref = stored(world, chart_labels=None)
    assert DocumentArtifactRow.for_company(world.company_id).get(pk=ref.id).chart_labels is None
    view = selectors.artifact_view(
        company_id=world.company_id, document_id=document_id, artifact_id=ref.id, charts=True
    )
    with pytest.raises(ChartLabelsUnavailable):
        view.chart_labels()


# ── T11 꼴 · T12 크기 ─────────────────────────────────────────────────────


def test_chart_labels_of_another_pdf_are_refused_and_write_no_row(world: World) -> None:
    document_id, etag = world.document(PDF)
    world.parser_returns(PDF, chart_labels=fake_chart_labels("c" * 64, charts=(CHART,)))
    with pytest.raises(ArtifactInvalid, match=r"chartLabels 의 source\.sha256"):
        world.ensure(document_id, etag)
    assert rows() == (0, 0)


def test_nul_in_chart_labels_is_stored_as_fffd(world: World) -> None:
    _document_id, ref = stored(world, chart_labels=labels_for(PDF, word("1\x006")))
    row = DocumentArtifactRow.for_company(world.company_id).get(pk=ref.id)
    assert row.chart_labels is not None
    words = cast("list[dict[str, object]]", row.chart_labels["words"])
    assert words[0]["text"] == "1�6"


def test_the_third_part_counts_toward_too_large(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    _document_id, small = stored(world, chart_labels=labels_for(PDF, word("16.2")))
    row = DocumentArtifactRow.for_company(world.company_id).get(pk=small.id)
    assert small.status == "ready" and row.document is not None and row.char_places is not None
    without = body_bytes(row.document, row.char_places)
    assert small.body_bytes > without  # 셋째가 합에 든다
    # 상한을 「두 칸까지는 들고 셋째에서 넘는」 자리로 내리면 too_large(세 칸 NULL)
    monkeypatch.setattr(services, "ARTIFACT_MAX_BYTES", without)
    other = b"%PDF-1.4 fake three"
    document_id, etag = world.document(other)
    world.parser_returns(other, chart_labels=labels_for(other, word("16.2")))
    ref = world.ensure(document_id, etag)
    assert isinstance(ref, ArtifactRef) and ref.status == "too_large"
    big = DocumentArtifactRow.for_company(world.company_id).get(pk=ref.id)
    assert (big.document, big.char_places, big.chart_labels) == (None, None, None)


def test_the_database_refuses_chart_labels_on_a_too_large_row(companies: tuple[int, int]) -> None:
    a, _b = companies
    with pytest.raises(IntegrityError):
        artifact(a, status="too_large", document=None, char_places=None, chart_labels={})
    ready = artifact(a, source_sha256="f" * 64, chart_labels=None)  # ready 행의 NULL 은 받는다
    assert ready.chart_labels is None
    assert artifact(a, source_sha256="d" * 64, chart_labels={"charts": []}).chart_labels == {"charts": []}


# ── T13 EPOCH ─────────────────────────────────────────────────────────────


def test_an_epoch_1_row_is_not_reused_but_still_reads(world: World) -> None:
    document_id, etag = world.document(PDF)
    old = artifact(world.company_id, source_sha256=sha_of(PDF), epoch=1, document=_old_document(), char_places={})
    with transaction.atomic():
        DocumentArtifactUseRow.for_company(world.company_id).create(
            company_id=world.company_id,
            document_id=document_id,
            document_etag=etag,
            artifact_id=old.id,
            contract=old.contract,
            layout=2,
            epoch=1,
        )
    world.parser_returns(PDF, chart_labels=labels_for(PDF))
    new = world.ensure(document_id, etag)
    assert isinstance(new, ArtifactRef) and new.id != old.id and new.epoch == EPOCH == 2
    assert world.parser.charts == [True]  # 옛 판은 다시 쓰지 않고 한 번 다시 분해했다
    view = selectors.artifact_view(
        company_id=world.company_id, document_id=document_id, artifact_id=old.id, charts=True
    )
    assert view.chart_labels() is None  # 옛 행은 읽히고 칸은 없다


def _old_document() -> dict[str, Any]:
    return fake_document(sha_of(PDF))


# ── T14 DB 뷰가 안 실음 ────────────────────────────────────────────────────


def test_a_view_opened_without_charts_does_not_read_the_column(world: World) -> None:
    document_id, ref = stored(world, chart_labels=labels_for(PDF, word("16.2")))
    with CaptureQueriesContext(connection) as queries:
        view = selectors.artifact_view(company_id=world.company_id, document_id=document_id, artifact_id=ref.id)
    sql = " ".join(q["sql"] for q in queries.captured_queries)
    assert '"core_document_artifacts"."chart_labels"' not in sql
    with pytest.raises(ChartLabelsNotLoaded):
        view.chart_labels()
    with CaptureQueriesContext(connection) as queries:
        selectors.artifact_view(company_id=world.company_id, document_id=document_id, artifact_id=ref.id, charts=True)
    assert '"core_document_artifacts"."chart_labels"' in " ".join(q["sql"] for q in queries.captured_queries)


# ── T15 이주 0005 ─────────────────────────────────────────────────────────


def test_the_column_is_nullable_jsonb_without_default_and_the_app_role_may_only_read_and_insert() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_type, is_nullable, column_default FROM information_schema.columns"
            " WHERE table_name = 'core_document_artifacts' AND column_name = 'chart_labels'"
        )
        assert cursor.fetchall() == [("jsonb", "YES", None)]
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'core_document_artifacts_body_check'"
        )
        (definition,) = cursor.fetchone() or ("",)
        assert "chart_labels IS NULL" in definition and definition.count("chart_labels") == 1
        cursor.execute(
            "SELECT has_column_privilege('esg_app', 'core_document_artifacts', 'chart_labels', p)"
            " FROM unnest(ARRAY['SELECT', 'INSERT', 'UPDATE']) AS p"
        )
        assert [r[0] for r in cursor.fetchall()] == [True, True, False]


# ── T16 회사 범위 ─────────────────────────────────────────────────────────


def test_another_company_does_not_see_the_labels(world: World, companies: tuple[int, int]) -> None:
    document_id, ref = stored(world, chart_labels=labels_for(PDF, word("16.2")))
    _a, b = companies
    with pytest.raises(ArtifactNotFound):
        selectors.artifact_view(company_id=b, document_id=document_id, artifact_id=ref.id, charts=True)
    assert DocumentArtifactRow.for_company(b).filter(pk=ref.id).values_list("chart_labels", flat=True).first() is None
    # 같은 회사라도 이음(uses) 없는 문서로는 못 연다(uses ⋈ core_documents — 산출물 id 만으로는 안 됨)
    unlinked, _etag = world.document(b"%PDF-1.4 not linked")
    with pytest.raises(ArtifactNotFound):
        selectors.artifact_view(company_id=world.company_id, document_id=unlinked, artifact_id=ref.id, charts=True)


# ── ④ N1 라벨 실패가 본 분해를 죽이지 않는다 · N3 빈 라벨 ─────────────────────


def refused(code: str, *, kind: ParseFailureKind = "rejected", status: int = 422) -> ParseFailed:
    return ParseFailed(kind, ParseFailureDetail(status=status, code=code, message="가짜 거절"))


class ChartsAwareParser(FakeParser):
    """charts 참/거짓에 따라 다른 결과를 내는 가짜(표 대신 둘)."""

    def __init__(self, with_charts: ParseResult, without: ParseResult) -> None:
        super().__init__()
        self.with_charts, self.without = with_charts, without

    def parse(self, pdf: bytes, *, file_name: str, layout: int = 1, charts: bool = False) -> ParseResult:
        super().parse(pdf, file_name=file_name, layout=layout, charts=charts)
        return self.with_charts if charts else self.without


def plug(world: World, with_charts: ParseResult, without: ParseResult) -> tuple[int, str]:
    document_id, etag = world.document(PDF)
    world.parser = ChartsAwareParser(with_charts, without)
    return document_id, etag


def good() -> Parsed:
    return parsed_for(PDF)


@pytest.mark.parametrize("code", ["parse_failed", "output_schema_invalid", "bad_charts"])
def test_a_refused_charts_request_is_parsed_again_without_labels(
    world: World, code: str, caplog: pytest.LogCaptureFixture
) -> None:
    document_id, etag = plug(world, refused(code), good())
    ref = world.ensure(document_id, etag)
    assert isinstance(ref, ArtifactRef) and ref.status == "ready" and ref.epoch == EPOCH
    assert world.parser.charts == [True, False]  # 라벨 요청이 거절되어 한 번 더(라벨 없이)
    row = DocumentArtifactRow.for_company(world.company_id).get(pk=ref.id)
    assert row.chart_labels is None and row.document is not None
    view = selectors.artifact_view(
        company_id=world.company_id, document_id=document_id, artifact_id=ref.id, charts=True
    )
    with pytest.raises(ChartLabelsUnavailable):
        view.chart_labels()
    (line,) = [r.getMessage() for r in caplog.records if "라벨 없이 다시 분해" in r.getMessage()]
    assert f"code {code}" in line and f"document_id={document_id}" in line


def test_a_second_refusal_is_refused_as_before(world: World) -> None:
    document_id, etag = plug(world, refused("parse_failed"), refused("parse_failed"))
    got = world.ensure(document_id, etag)
    assert isinstance(got, ArtifactRefused) and got.code == "parse_failed"
    assert world.parser.charts == [True, False] and rows() == (0, 0)


def test_a_parse_timeout_is_not_retried_and_refused_as_before(world: World) -> None:
    """첫 부름이 이미 파서 상한을 썼다 — 다시 부르면 일감 상한에 잘린다(④ 검증 B1). 지금처럼 Refused 한 번."""
    document_id, etag = plug(world, refused("parse_timeout"), good())
    got = world.ensure(document_id, etag)
    assert isinstance(got, ArtifactRefused) and got.code == "parse_timeout"
    assert world.parser.charts == [True] and rows() == (0, 0)


@pytest.mark.parametrize("code", ["password_protected", "not_a_pdf", "too_many_pages"])
def test_a_refusal_before_parsing_is_not_retried(world: World, code: str) -> None:
    document_id, etag = plug(world, refused(code), good())
    got = world.ensure(document_id, etag)
    assert isinstance(got, ArtifactRefused) and got.code == code
    assert world.parser.charts == [True] and rows() == (0, 0)


def test_an_unavailable_parser_is_not_retried_without_labels(world: World) -> None:
    document_id, etag = plug(world, refused("busy", kind="unavailable", status=503), good())
    with pytest.raises(RunRetryLater):
        world.ensure(document_id, etag)
    assert world.parser.charts == [True] and rows() == (0, 0)


def test_layout_1_is_never_retried(world: World) -> None:
    document_id, etag = world.document(PDF)
    world.parser = ChartsAwareParser(good(), refused("parse_failed"))
    got = world.ensure(document_id, etag, layout=1)
    assert isinstance(got, ArtifactRefused) and world.parser.charts == [False]


def test_found_nothing_reads_back_as_empty_labels_not_none(world: World) -> None:
    """N3: 찾았는데 0 인 라벨(jsonb {charts: [], words: [], …})은 DB 에서 읽어도 빈 ChartLabels 다."""
    document_id, ref = stored(world, chart_labels=fake_chart_labels(sha_of(PDF)))
    row = DocumentArtifactRow.for_company(world.company_id).get(pk=ref.id)
    assert row.chart_labels is not None and row.chart_labels["charts"] == []
    view = selectors.artifact_view(
        company_id=world.company_id, document_id=document_id, artifact_id=ref.id, charts=True
    )
    assert view.chart_labels() == ChartLabels(charts=(), words=())
