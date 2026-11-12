"""흐름 translation.colab@158 시험의 도움: 지어낸 옵션(options@1)·끼움(가짜 앞 실행 저장소)·모의 공급사 둘 + 다리로
흐름을 끝까지 돌린다. 실호출 0 — 공급사는 MockProvider 뿐, 설정은 저장소 정본 models.json(엔진 시험의 client 그대로)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from esgapi.core.flows.binding import DocumentInput
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowRun
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderResponse
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows.binding_158 import TranslationBinding
from esgapi.translation.flows.colab_158 import RetryNotFound, RetrySource
from esgapi.translation.tests.engines.colab_158.support import client
from esgapi.translation.tests.flows.settings_store import DefaultOnlyStore, FileModels

SIMPLE = "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다."
SIMPLE_EN = "[BLOCK 1]\nVirtual Title\nVirtual body."


def options(**changes: Any) -> dict[str, Any]:
    """최소 옵션(용어집·peer·autofix·retry 생략). 지어낸 회사."""
    base: dict[str, Any] = {
        "company": {"name": "가상고객사", "preferredSubject": "가상 업종", "industryStandards": "GRI"},
        "part": "general",
        "style": {"compareAb": False, "single": "B"},
        "pages": {"start": None, "end": None},
        "ceoPageLimit": 6,
    }
    return {**base, **changes}


@dataclass
class FakeStore:
    """앞 실행 저장소(가짜). 회사 id·실행 id → 갈래. 없으면 RetryNotFound(남의 회사도)."""

    found: dict[tuple[int, int], RetrySource] = field(default_factory=lambda: {})
    asked: list[tuple[int, int]] = field(default_factory=lambda: [])

    def base(self, company_id: int, run_id: int) -> RetrySource:
        self.asked.append((company_id, run_id))
        return self.found.get((company_id, run_id), RetryNotFound())


def binding(store: FakeStore | None = None, max_usd: float = 5.0) -> TranslationBinding:
    return TranslationBinding(
        store=store or FakeStore(),
        settings=DefaultOnlyStore(),
        models=FileModels(),
        max_usd=lambda: max_usd,
        mock=lambda: False,
        spent_usd=lambda _c, _r: 0.0,
    )


def default_versions() -> dict[str, object]:
    """기본 판으로 만든 실행의 versions(판 열쇠 aiSettingId None·모델 sha — 다시 하기 대조용)."""
    return binding().versions_with(options(), company_id=1)


def document(text: str = SIMPLE) -> DocumentInput:
    return DocumentInput(content=text.encode(), media_type="application/pdf", file_name="synthetic.txt")


@dataclass(frozen=True)
class Ran:
    run: FlowRun
    openai: MockProvider
    """답을 심은 모의 공급사(세 경로 다 openai — MARC-ENT-402)."""


def mock_client(replies: Sequence[ProviderResponse] = ()) -> tuple[LlmClient, MockProvider]:
    openai = MockProvider("openai")
    for reply in replies:
        openai.enqueue(reply)
    return client({"anthropic": MockProvider("anthropic"), "openai": openai}), openai


def run_options(
    given: Mapping[str, Any],
    replies: Sequence[ProviderResponse] = (),
    *,
    text: str = SIMPLE,
    content: bytes | None = None,
    store: FakeStore | None = None,
    max_usd: float = 5.0,
    llm: LlmClient | None = None,
    versions: Mapping[str, object] | None = None,
) -> Ran:
    """옵션을 끼움으로 받아(회사 1) 흐름을 끝까지 돌린다. 심은 답이 남으면 실패."""
    doc = (
        document(text)
        if content is None
        else DocumentInput(content=content, media_type="application/pdf", file_name="x")
    )
    inputs = binding(store, max_usd).inputs_with(doc, given, company_id=1, versions=versions or {})
    made, openai = mock_client(replies)
    adapters = colab.TranslationAdapters(llm=llm or made, tenant="1", mock=False, spent_usd=lambda: 0.0)
    run = run_flow(colab.FLOW, inputs, adapters)
    assert openai.pending == 0, f"심은 답 {openai.pending} 개가 남았다"
    return Ran(run, openai)


def result_of(ran: Ran) -> dict[str, Any]:
    """주 결과 translation.result@1(결과는 둘 — 주 꼴 먼저, 요약 translation.digest@1 둘째. 밴드 TR3a)."""
    result, summary = ran.run.output.results
    assert (result["schemaVersion"], summary["schemaVersion"]) == ("translation.result@1", "translation.digest@1")
    return result


def digest_of(ran: Ran) -> dict[str, Any]:
    """둘째 결과 translation.digest@1."""
    return ran.run.output.results[1]
