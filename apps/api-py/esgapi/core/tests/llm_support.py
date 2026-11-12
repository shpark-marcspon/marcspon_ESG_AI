"""core/llm 의 테스트가 같이 쓰는 준비물(esg-lab 의 test/helpers.ts 를 옮긴 것). 테스트 파일이 아니다.

여기의 토큰 수·단가는 전부 가상(synthetic) 값이다. 단가는 data/models.synthetic.json 의 것이다.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import LlmConfig, ModelConfig, default_config_sources, load_config
from esgapi.core.llm.prompts import FilePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.retry import RetryPolicy
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Scope, Tags, Usage
from esgapi.core.resources.ports.llm import Provider

TAGS = Tags(tenant="tenant-synthetic", module="scope3")

# 모의 모델(mock-synthetic) 단가로 정확히 0.0001 USD 가 되는 가상 사용량: 60×1 + 20×2 = 100 → 100/1e6.
USAGE_SYNTHETIC = Usage(input_tokens=60, output_tokens=20, cache_read_tokens=0, cache_write_tokens=0)

LONG_GUIDE = "용어집 항목. " * 400

PROMPTS = {
    "t/plain/1.md": "=== system ===\n짧게 답한다.\n\n=== user ===\n{{question}}\n",
    "t/plain/2.md": "=== system ===\n길게 답한다.\n\n=== user ===\n{{question}}\n",
    "t/cached-short/1.md": "=== system cache ===\n짧은 지침.\n\n=== user ===\n{{question}}\n",
    "t/cached-long/1.md": f"=== system cache ===\n{LONG_GUIDE}\n\n=== user ===\n{{{{question}}}}\n",
}


def write_prompts(root: Path) -> Path:
    for path, body in PROMPTS.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return root


def synthetic_config() -> LlmConfig:
    """실제 모델 + 가상 모델(mock-synthetic, mock-b-synthetic)."""
    return load_config(default_config_sources(synthetic=True))


def config_with(key: str = "mock-synthetic", **overrides: Any) -> LlmConfig:
    """가상 설정의 모델 하나에 항목을 덧씌운 설정. 설정 파일은 건드리지 않는다."""
    config = synthetic_config()
    model = config.models[key]
    changed = ModelConfig(key=key, entry=model.entry.model_copy(update=overrides))
    return LlmConfig(models={**config.models, key: changed}, routes=config.routes, token_estimate=config.token_estimate)


class LedgerSink(MemorySink):
    """다른 호출이 같은 꼬리표로 쓴 돈을 흉내 낼 수 있는 기록. `add_spent` 는 누적에만 더하고 기록 줄은 만들지
    않는다.
    """

    def __init__(self) -> None:
        super().__init__()
        self._others: list[tuple[Tags, float]] = []

    def add_spent(self, tags: Tags, cost_usd: float) -> None:
        self._others.append((tags, cost_usd))

    def spent(self, scope: Scope) -> float:
        others = sum(cost for tags, cost in self._others if scope.matches(tags.tenant, tags.module))
        return round((super().spent(scope) + others) * 1e8) / 1e8


@dataclass
class Harness:
    client: LlmClient
    mock: MockProvider
    mock_b: MockProvider
    log: LedgerSink
    sleeps: list[float]


def harness(
    prompt_root: Path,
    *,
    limits: Sequence[BudgetLimit] = (),
    store_bodies: bool = False,
    config: LlmConfig | None = None,
    providers: Mapping[str, Provider] | None = None,
    provider_retry: Mapping[str, RetryPolicy] | None = None,
    sleep: Callable[[float], None] | None = None,
    jitter: Callable[[], float] | None = None,
) -> Harness:
    mock = MockProvider()
    mock_b = MockProvider("mock-b")
    log = LedgerSink()
    sleeps: list[float] = []
    client = LlmClient(
        config=config or synthetic_config(),
        providers=providers if providers is not None else {"mock": mock, "mock-b": mock_b},
        prompts=FilePromptStore(prompt_root),
        log=log,
        limits=limits,
        store_bodies=store_bodies,
        provider_retry=provider_retry,
        # 재시도 전의 대기는 받아 적기만 하고 실제로 기다리지 않는다.
        sleep=sleep or sleeps.append,
        # 재시도 대기의 흩뜨림은 0(흩뜨림 없음 — retry.py 머리, LB1). 지터를 재는 시험만 따로 준다.
        jitter=jitter or (lambda: 0.0),
    )
    return Harness(client=client, mock=mock, mock_b=mock_b, log=log, sleeps=sleeps)
