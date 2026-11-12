"""흐름 테스트의 공용 가짜. 글은 전부 지은 것(sample_text). 실제 공급사·네트워크·키 0.

입력 bytes 는 정해 둔 b"synthetic-sample" 이고(가짜 PdfTextPort 는 bytes 를 보지 않고 표본 쪽 글을 돌려준다),
흐름이 그 sha256 을 스스로 센다 — 골든(tests/data/golden/)과 G1a.out/gw1-driver 가 같은 bytes·이름을 쓴다.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, cast

from esgapi.core.calc.ai_settings import AiStepSpec
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import NO_EVENTS, Carried, FlowEvents, FlowRun, StepOutput
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.types import Completed, ProviderRequest, ProviderResponse, TextPart
from esgapi.greenwash.contracts import wire
from esgapi.greenwash.engines.e0.ports import (
    CHAT_ENCODING,
    EMBEDDING_ENCODING,
    ChatReply,
    Message,
    MockEmbedding,
    ScriptedChat,
    TokenCounter,
    prompt_kind,
)
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.colab_e0 import ChatPort, EmbeddingPort, GreenwashAdapters
from esgapi.greenwash.flows.prompt_model_e0 import STEPS
from esgapi.greenwash.tests.sample_text import page_texts
from esgapi.greenwash.tools.ports import PositionValue

SAMPLE_BYTES: Final = b"synthetic-sample"
SAMPLE_NAME: Final = "synthetic-sample.pdf"
SAMPLE_PAGES: Final = {"ceo": "1", "company": "2", "climate": "3~4"}


class RealModels:
    """끼움의 모델 설정 원천(flows/binding_e0.ModelSettingsSource) — 패키지의 실제 설정과 STEPS(밴드 AS2b). 순수 시험이
    GreenwashBinding(models=…) 에 꽂는다(실행기의 selectors.RunModelSource 와 LLM_MODELS_FILE 없을 때 같은 값)."""

    config_value: Final = load_config(default_config_sources(synthetic=False))

    def config(self) -> LlmConfig:
        return self.config_value

    def steps(self) -> Sequence[AiStepSpec]:
        return STEPS


REAL_MODELS: Final = RealModels()


class SamplePdf:
    """sample_text.page_texts() 를 돌려주는 가짜 PdfTextPort."""

    def __init__(self, texts: Sequence[str] | None = None) -> None:
        self.texts = list(page_texts() if texts is None else texts)
        self.calls = 0

    def page_texts(self, pdf: bytes) -> list[str]:
        self.calls += 1
        return list(self.texts)


class Forbidden:
    """부르면 예외 — 호출 0 을 기계로 잰다(dry-run, 점검 쪽 없음)."""

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        self.calls += 1
        raise AssertionError("대화 포트를 부르면 안 된다")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        raise AssertionError("임베딩(문서)을 부르면 안 된다")

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        raise AssertionError("임베딩(질의)을 부르면 안 된다")


@dataclass
class BoxCoordinates:
    """상자를 지어 주는 가짜 좌표(문장 길이로 상자 하나 또는 둘)."""

    calls: list[tuple[int, str]] = field(default_factory=lambda: [])

    def locate(self, pdf: bytes, page: int, sentence: str) -> PositionValue | None:
        self.calls.append((page, sentence))
        boxes = [[72.0, 100.0, 520.0, 112.0]]
        if len(sentence) > 30:
            boxes.append([72.0, 114.0, 300.0, 126.0])
        return {"page": page, "boxes": boxes}


def char_counter() -> TokenCounter:
    """글자 수 = 토큰 수인 가짜 세기(GW1 test_pipeline 의 CHAR_COUNTER 와 같다)."""
    return TokenCounter({CHAT_ENCODING: len, EMBEDDING_ENCODING: len})


def inputs(*, dry_run: bool = False, ceo: str = "1", company: str = "2", climate: str = "3~4") -> colab.GreenwashInputs:
    return colab.GreenwashInputs(
        document=SAMPLE_BYTES,
        media_type="application/pdf",
        file_name=SAMPLE_NAME,
        ceo=ceo,
        company=company,
        climate=climate,
        dry_run=dry_run,
    )


def adapters(
    *,
    llm: ChatPort | None = None,
    embedding: EmbeddingPort | None = None,
    pdf: SamplePdf | None = None,
    coordinates: BoxCoordinates | None = None,
    tokens: TokenCounter | None = None,
) -> GreenwashAdapters:
    return GreenwashAdapters(
        pdf_text=pdf or SamplePdf(),
        llm=llm if llm is not None else ScriptedChat(),
        embedding=embedding if embedding is not None else MockEmbedding(),
        coordinates=coordinates,
        tokens=tokens,
    )


def run(
    given: colab.GreenwashInputs,
    used: GreenwashAdapters,
    *,
    start_at: str | None = None,
    carried: Carried | None = None,
    resume: Mapping[str, object] | None = None,
    events: FlowEvents = NO_EVENTS,
) -> FlowRun:
    return run_flow(colab.FLOW, given, used, start_at=start_at, carried=carried, resume=resume, events=events)


def result_of(flow_run: FlowRun) -> dict[str, Any]:
    (result,) = flow_run.output.results
    return result


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def message_hashes(sent: Sequence[Sequence[Message]]) -> list[str]:
    """보낸 메시지 목록마다 (system, user) 의 sha256 — 차례 그대로."""
    return [
        hashlib.sha256(json.dumps([m.content for m in msgs], ensure_ascii=False).encode("utf-8")).hexdigest()
        for msgs in sent
    ]


GOLDEN: Final = Path(__file__).resolve().parents[1] / "data" / "golden"
SHARED: Final = ("source", "config", "models", "promptVersion", "parts", "pages", "candidateStats", "wordCounts")
UNMAPPED: Final = ("calls", "messages")
"""GW1 결과에서 result_to_wire 를 걸지 않는 칸 — 원값(snake)으로 견준다(GC3 발주서 정한 것 7)."""


def golden(name: str) -> dict[str, Any]:
    """GW1 을 esg-lab 에서 돌린 결과(G1a.out/gw1-driver/make_golden.py — 만든 명령은 파일의 _made_by)."""
    return cast("dict[str, Any]", json.loads((GOLDEN / name).read_text(encoding="utf-8")))


def golden_wire(name: str) -> dict[str, Any]:
    """골든을 결과 꼴(camelCase)과 견줄 때 — calls·messages 를 뗀 나머지를 제품의 경계 wire.result_to_wire 로
    사상한다."""
    return _gw1_wire(golden(name))


def _gw1_wire(gw1: Mapping[str, Any]) -> dict[str, Any]:
    return wire.result_to_wire({k: v for k, v in gw1.items() if k not in UNMAPPED})


def as_gw1(result: Mapping[str, Any]) -> dict[str, Any]:
    """greenwash.result@1 → GW1 결과의 견줄 칸(발주서 §3-2).

    같은 이름의 칸 + items(position → span, exampleSentence 는 뺀다). GW1 쪽은 gw1_view 가 camelCase 로 사상한다.
    """
    items: list[dict[str, Any]] = []
    for item in cast("list[dict[str, Any]]", result["items"]):
        moved = {k: v for k, v in item.items() if k not in ("position", "exampleSentence")}
        moved["span"] = item["position"]
        items.append(moved)
    return {**{k: result[k] for k in SHARED}, "items": items}


def gw1_view(gw1: Mapping[str, Any]) -> dict[str, Any]:
    """GW1 결과(snake)의 견줄 칸 — wire.result_to_wire 로 사상한 것(GC3)."""
    mapped = _gw1_wire(gw1)
    return {**{k: mapped[k] for k in SHARED}, "items": mapped["items"]}


def chat_calls(sent: Sequence[Sequence[Message]]) -> dict[str, int]:
    """대화 포트가 받은 것의 종류별 수(GW1 calls.chat 과 같은 셈)."""
    pack = default_prompts(PROMPT_VERSION)
    out: dict[str, int] = {}
    for msgs in sent:
        kind = prompt_kind(msgs[0].content, pack)
        out[kind] = out.get(kind, 0) + 1
    return out


@dataclass
class Recorder:
    """사건 받는 쪽: 산출물과 진행을 적어 둔다. stop_after 가 있으면 judge 의 그 done 에서 partial 을 남기고 끊는다."""

    stop_after: int | None = None
    finished: dict[str, StepOutput] = field(default_factory=lambda: {})
    progress: list[tuple[str, int, int]] = field(default_factory=lambda: [])
    saved: dict[str, object] | None = None

    def step_started(self, flow_id: str, step: str) -> None:
        return None

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        self.finished[step] = output

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        return None

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        self.progress.append((step, done, total))
        if self.stop_after is not None and step == "judge" and done == self.stop_after:
            self.saved = dict(partial)
            raise Interrupted(done)


class Interrupted(Exception):
    """끊김을 흉내 낸다(사건 받는 쪽의 예외 — run_flow 는 그대로 올린다)."""


class FailingChat:
    """ScriptedChat 을 감싸, 탐지 프롬프트의 user 글이 가리키는 쪽이 fail_pages 에 들면 예외를 낸다(쪽 하나가 죽는 길 —
    GW1 의 스캔 루프는 그 예외를 삼켜 failed_pages 에 적는다, 흠 12·19)."""

    def __init__(self, fail_pages: Sequence[int]) -> None:
        self.inner = ScriptedChat()
        self.fail_pages = set(fail_pages)
        self.sent: list[list[Message]] = self.inner.sent

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        if messages[0].content == self.inner.pack.detect_system_prompt:
            page = int(messages[1].content.split("페이지", 1)[0].rsplit(" ", 1)[-1])
            if page in self.fail_pages:
                self.sent.append(list(messages))
                raise RuntimeError(f"가상의 실패: {page}쪽")
        return self.inner.invoke(messages)


def scripted_provider(calls: int) -> tuple[MockProvider, ScriptedChat]:
    """받은 요청의 system·user 글로 ScriptedChat 과 같은 대본 답을 돌려주는 모의 공급사(큐에 calls 개).
    test_colab_e0.scripted_provider 와 같은 꼴 — 끼움·실행기 시험(G1b)이 같이 쓴다."""
    script = ScriptedChat()

    def reply(request: ProviderRequest) -> ProviderResponse:
        system = "".join(seg.text for seg in request.system)
        user = "".join(part.text for part in request.user if isinstance(part, TextPart))
        return Completed(text=script.respond(system, user), usage=SYNTHETIC_USAGE)

    mock = MockProvider()
    for _ in range(calls):
        mock.enqueue(reply)
    return mock, script


def provider_hashes(requests: Sequence[ProviderRequest]) -> list[str]:
    """모의 공급사가 받은 요청마다 (system, user) 의 sha256 — message_hashes 와 같은 셈(골든 messages 와 견준다)."""
    pairs = [
        ["".join(seg.text for seg in r.system), "".join(p.text for p in r.user if isinstance(p, TextPart))]
        for r in requests
    ]
    return [sha256_text(json.dumps(pair, ensure_ascii=False)) for pair in pairs]
