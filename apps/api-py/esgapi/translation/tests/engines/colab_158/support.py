"""흐름 시험의 도움: 실제 설정(models.json) + 모의 공급사 둘 + 다리(tools/llm_bridge.py)로 `pipeline.run` 을 돌리고,
호출마다 (자리, 역할, system, user, max_tokens, 모델, 경로)를 적는다. 실호출 0 — 공급사는 MockProvider 뿐이다.

모의 답은 `Completed`·`Truncated`·`Refusal`·`ProviderError` 를 키워드 인자로 짓는다(TL1 겹침 — 위치 인자 0).
재시도는 끈다(`provider_retry={}`) — 재시도가 심어 둔 답을 먹지 않게.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, ProviderError, ProviderResponse, Refusal, Truncated, Usage
from esgapi.translation.engines.colab_158 import pipeline
from esgapi.translation.engines.colab_158.pipeline import EngineInput
from esgapi.translation.engines.colab_158.ports import GatewayText, Role
from esgapi.translation.engines.colab_158.prompts import Site
from esgapi.translation.engines.colab_158.records import TranslationRun
from esgapi.translation.tools.llm_bridge import LlmBridge, route_for

USAGE = Usage(input_tokens=10, output_tokens=5, cache_read_tokens=0, cache_write_tokens=0)
"""가상 사용량(실제 값이 아니다)."""


def ok(text: str) -> Completed:
    return Completed(text=text, usage=USAGE)


def cut(text: str) -> Truncated:
    return Truncated(text=text, usage=USAGE)


def refuse(text: str) -> Refusal:
    return Refusal(text=text, category=None, usage=USAGE)


def fail() -> ProviderError:
    return ProviderError(status=500, retryable=False, message="가상 공급사 오류")


@dataclass(frozen=True)
class Call:
    site: Site
    role: Role
    system: str
    user: str
    max_tokens: int
    model: str
    route: str

    @property
    def row(self) -> tuple[str, int, str, str]:
        """호출 열의 한 줄: (프롬프트 자리, max_tokens, 모델, 경로)."""
        return (self.site, self.max_tokens, self.model, self.route)


@dataclass
class Recording:
    """다리를 감싸 호출을 적는다. 모델은 그 호출에 응답한 모의 공급사가 받은 요청의 api_model_id."""

    bridge: LlmBridge
    part: str
    providers: dict[str, MockProvider]
    calls: list[Call] = field(default_factory=list[Call])

    def complete(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> GatewayText:
        before = {name: len(p.calls) for name, p in self.providers.items()}
        try:
            return self.bridge.complete(site, role, system, user, max_tokens)
        finally:
            sent = [p.calls[-1] for name, p in self.providers.items() if len(p.calls) > before[name]]
            model = sent[0].api_model_id if sent else "(없음)"
            self.calls.append(Call(site, role, system, user, max_tokens, model, route_for(role, self.part)))


@dataclass(frozen=True)
class Flow:
    run: TranslationRun
    calls: list[Call]
    anthropic: MockProvider
    openai: MockProvider

    @property
    def rows(self) -> list[tuple[str, int, str, str]]:
        return [c.row for c in self.calls]

    @property
    def sites(self) -> list[str]:
        return [c.site for c in self.calls]

    def codes(self) -> list[str]:
        return [w.code for w in self.run.warnings]


def client(providers: dict[str, MockProvider], log: MemorySink | None = None) -> LlmClient:
    return LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers=providers,
        prompts=PackagePromptStore(),
        log=MemorySink() if log is None else log,
        provider_retry={},
        sleep=lambda _ms: None,
    )


def run_flow(inputs: EngineInput, replies: Sequence[ProviderResponse]) -> Flow:
    """심은 답을 openai 모의에 차례로 넣고 돌린다(세 경로 다 openai — MARC-ENT-402). 끝에 남은 답이 없어야 한다(손셈한
    호출 수와 같음)."""
    anthropic, openai = MockProvider("anthropic"), MockProvider("openai")
    for reply in replies:
        openai.enqueue(reply)
    providers = {"anthropic": anthropic, "openai": openai}
    recording = Recording(
        LlmBridge(client(providers), part=inputs.part, tenant="tenant-synthetic"), inputs.part, providers
    )
    result = pipeline.run(inputs, recording)
    assert openai.pending == 0, f"심은 답 {openai.pending} 개가 남았다"
    return Flow(result, recording.calls, anthropic, openai)


def make_input(
    text: str,
    *,
    part: str = "general",
    base: Sequence[tuple[str, str]] = (),
    final: Sequence[tuple[str, str]] = (),
    compare_ab: bool = False,
    single: str = "B",
    peer: str | None = None,
    start: int | None = None,
    end: int | None = None,
    ceo_page_limit: int | None = 6,
    autofix: bool = True,
) -> EngineInput:
    return EngineInput(
        text=text,
        company_name="가상고객사",
        preferred_subject="가상 업종",
        industry_standards="GRI",
        glossary_base=tuple(base),
        glossary_final=tuple(final),
        part=part,
        compare_ab=compare_ab,
        single_style=single,
        peer_group_style_prompt=peer,
        page_start=start,
        page_end=end,
        ceo_page_limit=ceo_page_limit,
        autofix=autofix,
    )


LIGHT_MODEL = "gpt-4.1-mini"
STANDARD_MODEL = "gpt-4.1"
LIGHT = "light-openai-41"
STANDARD = "standard-openai-41"
