"""엔진 JSON 덤프(개정 1 B1 — esg-lab 대조 도구 TR1-o 가 부른다): 지어낸 입력 + 대본 → 모의 공급사 둘로 `pipeline.run` →
호출 열과 `TranslationRun` 을 JSON 으로. 실호출 0 — 공급사는 MockProvider 뿐, 설정은 저장소 정본 models.json.
계약(contracts)을 import 하지 않는다(엔진의 기록 그대로 — TR1-o 는 코랩 쪽과 이 꼴로 견준다).

    uv run --frozen python -m esgapi.translation.tools.compare_dump \
        --input <입력 JSON> --script <대본 JSON> --out <경로>

입력 JSON = translation.input@1 꼴(document.kind structuredText). 대본 JSON = {"anthropic": [답…], "openai": [답…]},
답 = {"kind": "completed"|"truncated"|"refusal"|"error", "text": "…"}(error 는 text 를 메시지로, 다시 시도 안 함).
출력 = {"calls": [{"site", "role", "system", "user", "maxTokens", "model", "route"}…], "run": <TranslationRun asdict>,
"unusedReplies": {"anthropic": n, "openai": n}}.
"""

import argparse
import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

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
from esgapi.translation.tools.llm_bridge import LlmBridge, route_for

USAGE = Usage(input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0)
"""모의 답의 사용량(가상 0 — 덤프는 비용을 보지 않는다)."""


class DumpCall(TypedDict):
    site: str
    role: str
    system: str
    user: str
    maxTokens: int
    model: str | None
    route: str


class Dump(TypedDict):
    calls: list[DumpCall]
    run: dict[str, Any]
    unusedReplies: dict[str, int]


def engine_input(received: Mapping[str, Any]) -> EngineInput:
    """translation.input@1 dict → 엔진 입력(꼴 검사는 하지 않는다 — 지어낸 입력을 받는 도구다)."""
    document, company, glossary = received["document"], received["company"], received["glossary"]
    if document["kind"] != "structuredText":
        raise ValueError(f"받지 않는 문서 꼴: {document['kind']}")
    peer = received["peerGroupStyle"]
    return EngineInput(
        text=document["text"],
        company_name=company["name"],
        preferred_subject=company["preferredSubject"],
        industry_standards=company["industryStandards"],
        glossary_base=tuple((g["ko"], g["en"]) for g in glossary["base"]),
        glossary_final=tuple((g["ko"], g["en"]) for g in glossary["final"]),
        part=received["part"],
        compare_ab=received["style"]["compareAb"],
        single_style=received["style"]["single"],
        peer_group_style_prompt=None if peer is None else peer["prompt"],
        page_start=received["pages"]["start"],
        page_end=received["pages"]["end"],
        ceo_page_limit=received["ceoPageLimit"],
        autofix=received["autofix"],
    )


def reply(spec: Mapping[str, Any]) -> ProviderResponse:
    kind, text = spec["kind"], spec["text"]
    if kind == "completed":
        return Completed(text=text, usage=USAGE)
    if kind == "truncated":
        return Truncated(text=text, usage=USAGE)
    if kind == "refusal":
        return Refusal(text=text, category=None, usage=USAGE)
    if kind == "error":
        return ProviderError(status=None, retryable=False, message=text)
    raise ValueError(f"모르는 답 꼴: {kind}")


class _Recording:
    """다리를 감싸 호출을 적는다. 모델 = 그 호출에 응답한 모의 공급사가 받은 요청의 api_model_id."""

    def __init__(self, bridge: LlmBridge, part: str, providers: Mapping[str, MockProvider]) -> None:
        self.bridge = bridge
        self.part = part
        self.providers = providers
        self.calls: list[DumpCall] = []

    def complete(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> GatewayText:
        before = {name: len(p.calls) for name, p in self.providers.items()}
        try:
            return self.bridge.complete(site, role, system, user, max_tokens)
        finally:
            sent = [p.calls[-1] for name, p in self.providers.items() if len(p.calls) > before[name]]
            self.calls.append(
                DumpCall(
                    site=site,
                    role=role,
                    system=system,
                    user=user,
                    maxTokens=max_tokens,
                    model=sent[0].api_model_id if sent else None,
                    route=route_for(role, self.part),
                )
            )


def dump(received: Mapping[str, Any], script: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dump:
    providers = {"anthropic": MockProvider("anthropic"), "openai": MockProvider("openai")}
    for name, provider in providers.items():
        for spec in script.get(name, ()):
            provider.enqueue(reply(spec))
    inputs = engine_input(received)
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers=providers,
        prompts=PackagePromptStore(),
        log=MemorySink(),
        provider_retry={},
        sleep=lambda _ms: None,
    )
    recording = _Recording(LlmBridge(client, part=inputs.part, tenant="compare-dump"), inputs.part, providers)
    run = pipeline.run(inputs, recording)
    return Dump(
        calls=recording.calls,
        run=dataclasses.asdict(run),
        unusedReplies={name: p.pending for name, p in providers.items()},
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="영문번역 엔진 colab_158 의 JSON 덤프(모의 공급사, 실호출 0)")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    received = json.loads(args.input.read_text(encoding="utf-8"))
    script = json.loads(args.script.read_text(encoding="utf-8"))
    result = dump(received, script)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
