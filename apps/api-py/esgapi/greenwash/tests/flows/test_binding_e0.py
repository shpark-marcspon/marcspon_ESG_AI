"""끼움 GreenwashBinding(flows/binding_e0.py — 밴드 G1b): 옵션 받기의 차례와 문장, 쪽 배열 → 노트북 쪽 글자, 판 묶음,
어댑터의 꼴(LlmChatBridge·꼬리표·기본 경로), 그리고 끼움으로 지은 입력·어댑터로 돈 흐름이 골든과 같음(대조 A·B 의 꼴).
순수 층(DB 없음). 모의 공급사·모의 임베딩만 쓴다 — 실제 공급사·키 0. 글과 숫자는 지은 것(synthetic)이다.
"""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest

from esgapi.config.env import LlmSettings
from esgapi.core.flows.binding import DocumentInput, RunContext, RunOptionsRejected
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.embedding import ClientEmbeddingPort, EmbeddingClient
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.setup import build_embedding_client
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Tags
from esgapi.greenwash.engines.e0.parts import build_section_pages, parse_pages
from esgapi.greenwash.flows import binding_e0
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding, pages_to_notebook
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows.settings_store import DefaultOnlyStore
from esgapi.greenwash.tests.flows.support import REAL_MODELS
from esgapi.greenwash.tools.coordinates import PdfiumCoordinates
from esgapi.greenwash.tools.pdftext_pypdf import PypdfText

MINIMAL: dict[str, Any] = {"parts": {"ceo": [1], "company": [2], "climate": [3, 4]}}
DOCUMENT = DocumentInput(content=s.SAMPLE_BYTES, media_type="application/pdf", file_name=s.SAMPLE_NAME)


@dataclass
class FakeContext:
    """RunContext 의 가짜. llm()·embedding() 은 넣어 둔 클라이언트를 돌려준다(부른 수를 센다)."""

    client: LlmClient | None = None
    embedder: EmbeddingClient | None = None
    company_id: int = 7
    run_id: int = 41
    module: str = "greenwash"
    flow_id: str = colab.FLOW_ID
    attempt: int = 1
    dry_run: bool = False
    asked: list[str] = field(default_factory=lambda: [])

    def llm(self) -> LlmClient:
        self.asked.append("llm")
        assert self.client is not None
        return self.client

    def embedding(self) -> EmbeddingClient:
        self.asked.append("embedding")
        assert self.embedder is not None
        return self.embedder


def mock_client(mock: MockProvider, sink: MemorySink) -> LlmClient:
    return LlmClient(
        config=load_config(default_config_sources(synthetic=True)),
        providers={"mock": mock},
        prompts=PackagePromptStore(),
        log=sink,
    )


def context(mock: MockProvider | None = None, sink: MemorySink | None = None) -> FakeContext:
    used = sink or MemorySink()
    return FakeContext(
        client=mock_client(mock or MockProvider(), used),
        embedder=build_embedding_client(LlmSettings(), mock=True, sink=used),
    )


def as_context(ctx: FakeContext) -> RunContext:
    return ctx


def rejected(options: Mapping[str, object]) -> str:
    with pytest.raises(RunOptionsRejected) as caught:
        GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).check_options(options)
    return caught.value.message


# ── §3-1-1 옵션 받기 ──


@pytest.mark.parametrize(
    "options",
    [
        pytest.param(MINIMAL, id="minimal"),
        pytest.param({**MINIMAL, "extraTerms": ["  친환경 포장  ", "", "녹색 채권"]}, id="extra-terms"),
        pytest.param({"parts": {"ceo": [], "company": [], "climate": [300]}}, id="one-part"),
        pytest.param({"parts": {"ceo": [2, 1], "company": [2], "climate": [2]}}, id="overlap"),
    ],
)
def test_good_options_pass(options: Mapping[str, object]) -> None:
    GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).check_options(options)


@pytest.mark.parametrize(
    ("options", "message"),
    [
        pytest.param({**MINIMAL, "criteria": {}}, "알 수 없는 옵션이에요: criteria", id="criteria"),
        pytest.param({**MINIMAL, "reportYear": 2026}, "알 수 없는 옵션이에요: reportYear", id="report-year"),
        pytest.param(
            {**MINIMAL, "previousDocumentId": 3, "reportYear": 2026},
            "알 수 없는 옵션이에요: previousDocumentId, reportYear",
            id="two-unknown",
        ),
        pytest.param({}, "파트별 점검 페이지(parts)를 넣어 주세요", id="no-parts"),
        pytest.param({"parts": [1, 2]}, "파트별 점검 페이지(parts)를 넣어 주세요", id="parts-list"),
        pytest.param(
            {"parts": {"ceo": [1], "company": [], "climate": [], "cfo": [2]}}, "알 수 없는 파트예요: cfo", id="part-key"
        ),
        pytest.param(
            {"parts": {"ceo": [1], "company": []}},
            "파트 셋(ceo·company·climate)의 페이지를 모두 넣어 주세요",
            id="part-missing",
        ),
        pytest.param(
            {"parts": {"ceo": [0], "company": [], "climate": []}}, "페이지 번호는 1~300 사이여야 해요", id="page-0"
        ),
        pytest.param(
            {"parts": {"ceo": [301], "company": [], "climate": []}}, "페이지 번호는 1~300 사이여야 해요", id="page-301"
        ),
        pytest.param(
            {"parts": {"ceo": [True], "company": [], "climate": []}},
            "페이지 번호는 정수의 목록으로 넣어 주세요",
            id="page-bool",
        ),
        pytest.param(
            {"parts": {"ceo": ["3"], "company": [], "climate": []}},
            "페이지 번호는 정수의 목록으로 넣어 주세요",
            id="page-text",
        ),
        pytest.param(
            {"parts": {"ceo": [1.0], "company": [], "climate": []}},
            "페이지 번호는 정수의 목록으로 넣어 주세요",
            id="page-float",
        ),
        pytest.param(
            {"parts": {"ceo": "3~5", "company": [], "climate": []}},
            "페이지 번호는 정수의 목록으로 넣어 주세요",
            id="pages-text",
        ),
        pytest.param(
            {"parts": {"ceo": [], "company": [], "climate": []}}, "점검할 페이지를 하나 이상 골라 주세요", id="empty"
        ),
        pytest.param(
            {**MINIMAL, "extraTerms": ["가"] * 101},
            "추가 단어는 100개까지만 보낼 수 있어요",
            id="extra-101-before-normalize",
        ),
        pytest.param(
            {**MINIMAL, "extraTerms": ["녹색(인증)"]},
            "추가 단어에는 괄호나 따옴표를 쓸 수 없어요",
            id="extra-parenthesis",
        ),
        pytest.param({**MINIMAL, "extraTerms": "녹색"}, "추가 단어는 단어의 목록으로 넣어요", id="extra-text"),
        pytest.param(
            {**MINIMAL, "extraTerms": [f"단어{i}" for i in range(31)]},
            "추가 단어는 30개까지 넣을 수 있어요",
            id="extra-31",
        ),
    ],
)
def test_bad_options_are_refused_with_the_sentence(options: Mapping[str, object], message: str) -> None:
    assert rejected(options) == message


def test_the_extra_terms_sentences_are_accept_extra_terms_own() -> None:
    """추가 단어 규칙의 문장은 흐름 입력의 받기(colab_e0.accept_extra_terms)의 것 그대로다(MARC-ISSUE-100 (2))."""
    for terms in (["녹색(인증)"], ["..."], ["가" * 31]):
        with pytest.raises(ValueError) as flow_refused:
            colab.accept_extra_terms(terms)
        assert rejected({**MINIMAL, "extraTerms": terms}) == str(flow_refused.value)


def test_the_hundred_limit_counts_before_normalizing() -> None:
    """100개는 거르기 전 수다 — 빈 것·겹친 것 100개는 받기 전에 지나고, 거른 뒤 30개 안이면 받는다."""
    GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).check_options(
        {**MINIMAL, "extraTerms": ["녹색"] * 50 + [""] * 50}
    )
    assert rejected({**MINIMAL, "extraTerms": ["녹색"] * 51 + [""] * 50}) == "추가 단어는 100개까지만 보낼 수 있어요"


# ── §3-1-2 쪽 배열 → 노트북 쪽 글자 ──


@pytest.mark.parametrize(
    ("pages", "text"),
    [
        ([], ""),
        ([5], "5"),
        (list(range(6, 15)), "6~14"),
        ([*range(25, 38), *range(55, 75)], "25~37,55~74"),
        ([3, 4], "3~4"),
        ([9, 1, 3, 2, 9, 7], "1~3,7,9"),
        ([2, 2, 2], "2"),
    ],
)
def test_pages_to_notebook(pages: list[int], text: str) -> None:
    assert pages_to_notebook(pages) == text


@pytest.mark.parametrize(
    "pages", [[], [5], list(range(6, 15)), [*range(25, 38), *range(55, 75)], [9, 1, 3, 2, 9, 7], [1, 300]]
)
def test_the_notebook_reader_gives_the_set_back(pages: list[int]) -> None:
    """노트북의 쪽 글자 읽개(engines/e0/parts.parse_pages · build_section_pages)가 원래 집합을 돌려준다(★C)."""
    text = pages_to_notebook(pages)
    assert parse_pages(text) == sorted(set(pages))
    section, manual = build_section_pages(text, "", "", 300)
    assert section["CEO 메시지"] == manual == sorted(set(pages))


def test_inputs_carry_the_document_the_pages_and_the_terms() -> None:
    options = {"parts": {"ceo": [6, 7, 8], "company": [2], "climate": []}, "extraTerms": [" 녹색 채권 ", "녹색채권"]}
    built = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).inputs(DOCUMENT, options)
    assert (built.document, built.media_type, built.file_name) == (s.SAMPLE_BYTES, "application/pdf", s.SAMPLE_NAME)
    assert (built.ceo, built.company, built.climate) == ("6~8", "2", "")
    assert built.extra_terms == ("녹색 채권",)  # accept_extra_terms 가 거른 것
    assert (built.criteria, built.dry_run) == (None, False)


def test_inputs_refuse_what_check_options_refuses() -> None:
    with pytest.raises(RunOptionsRejected):
        GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).inputs(
            DOCUMENT, {"parts": {"ceo": [], "company": [], "climate": []}}
        )


# ── §3-1-3 판 묶음 ──


def test_versions_are_run_versions_without_flow() -> None:
    versions = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).versions(MINIMAL)
    assert versions == colab.run_versions(None)
    assert sorted(versions) == ["aiSetting", "evalPromptSha256"]
    assert versions["aiSetting"] == "colab-2026-01-15-v1"
    assert (
        GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).versions({**MINIMAL, "extraTerms": ["녹색"]})
        == versions
    )  # 추가 단어는 판에 닿지 않는다


# ── §3-1-4 어댑터 ──


def test_the_default_binding_uses_the_real_route_names() -> None:
    """모의 경로가 제품 기본으로 새지 않는다(발주서 개정 1, B1)."""
    binding = GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore())
    assert (binding.chat_route, binding.embedding_route) == ("light-openai-41", "light-openai")
    assert binding.chat_route == colab.CHAT_ROUTE
    ctx = context()
    built = binding.adapters(as_context(ctx))
    assert isinstance(built.llm, colab.LlmChatBridge) and built.llm.route == "light-openai-41"
    assert isinstance(built.embedding, ClientEmbeddingPort)
    assert built.embedding._route == "light-openai"  # pyright: ignore[reportPrivateUsage]


def test_adapters_are_a_bridge_with_the_tenant_tags_and_a_new_pdfium_coordinates_per_call() -> None:
    ctx = context()
    built = GreenwashBinding(
        models=REAL_MODELS, store=DefaultOnlyStore(), chat_route="mock", embedding_route="mock-gw1"
    ).adapters(as_context(ctx))
    assert type(built.llm) is colab.LlmChatBridge
    assert built.llm.tags == Tags(tenant="7", module="greenwash")
    assert built.llm.client is ctx.client
    assert isinstance(built.pdf_text, PypdfText) and isinstance(built.pdf_text, colab.PDF_TEXT)
    assert isinstance(built.coordinates, PdfiumCoordinates) and built.tokens is None
    assert built.coordinates.document is None and built.coordinates.stats() == {}  # 짓기만 — 문서는 locate 가 연다
    again = GreenwashBinding(
        models=REAL_MODELS, store=DefaultOnlyStore(), chat_route="mock", embedding_route="mock-gw1"
    ).adapters(as_context(context()))
    assert isinstance(again.coordinates, PdfiumCoordinates)
    assert again.coordinates is not built.coordinates  # 시도마다 새것
    embedding = built.embedding
    assert isinstance(embedding, ClientEmbeddingPort)
    assert embedding._tags == Tags(tenant="7", module="greenwash")  # pyright: ignore[reportPrivateUsage]
    assert embedding._batch_size == colab.CHUNK_ARGS["embedding_batch_size"] == 50  # pyright: ignore[reportPrivateUsage]
    assert ctx.asked == ["llm", "embedding"]


# ── §3-1-5 끼움으로 지은 입력·어댑터로 돈 흐름 = 골든 ──


def test_the_bound_inputs_are_the_golden_inputs() -> None:
    assert (
        binding_e0.GreenwashBinding(models=REAL_MODELS, store=DefaultOnlyStore()).inputs(DOCUMENT, MINIMAL)
        == s.inputs()
    )  # 쪽 글자 "1" / "2" / "3~4"


def test_the_bound_flow_matches_the_golden_through_core_llm() -> None:
    gw1 = s.golden("sample-mock.json")
    mock, _ = s.scripted_provider(20)
    sink = MemorySink()
    binding = GreenwashBinding(
        models=REAL_MODELS, store=DefaultOnlyStore(), chat_route="mock", embedding_route="mock-gw1"
    )
    built = binding.adapters(as_context(context(mock, sink)))
    used = dataclasses.replace(built, pdf_text=s.SamplePdf())  # 표본 bytes 는 PDF 가 아니다 — 쪽 글은 가짜 읽개가
    result = s.result_of(s.run(binding.inputs(DOCUMENT, MINIMAL), used))
    assert s.as_gw1(result) == s.gw1_view(gw1)
    assert s.provider_hashes(mock.calls) == gw1["messages"] and len(gw1["messages"]) == 12
    chat = [r for r in sink.records if r.prompt_id.startswith("greenwash/")]
    assert len(chat) == 12 and {r.tenant for r in sink.records} == {"7"}
