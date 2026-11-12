"""기본 글·기본 모델 칸의 공급사 요청이 BASE 와 바이트 같은지 재는 지문(TR4 §3-1-3). 실호출 0 — 모의 공급사뿐.

지어낸 문서 하나(서술 쪽 + pipe 표 쪽)를 세 파트 × 문체 셋(A·B·A/B 비교) = 아홉 경우로 `pipeline.run` 에 돌리고,
호출마다 (자리, 프롬프트 id, 설정 모델, 공급사 요청 몸 `ProviderRequest.to_json()` — 모델 id·system·user·
max_output_tokens·temperature 유무)를 적어 sha256 을 낸다. 같은 입력의 호출 계획(`plan.plan` — 자리·역할·system·user·
max_tokens·횟수)과 다리 `dry_run` 의 어림도 경우마다 지문을 낸다.

이 파일은 BASE 에도 있는 것(support·pipeline·plan·LlmBridge 의 옛 생성자)만 import 한다 —
`scripts/section4-TR4.sh` 가 이 파일을 BASE 트리(`git archive`)에 넣어 그쪽 엔진으로도 돌리고 두 지문을 견준다.

    uv run --frozen python -m esgapi.translation.tests.engines.colab_158.texts_digest
"""

import dataclasses
import hashlib
import json
import sys
from typing import Any

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, Usage
from esgapi.translation.engines.colab_158 import pipeline, plan
from esgapi.translation.engines.colab_158.pipeline import EngineInput
from esgapi.translation.engines.colab_158.ports import GatewayText, Role
from esgapi.translation.engines.colab_158.prompts import Site
from esgapi.translation.tests.engines.colab_158.support import client, make_input
from esgapi.translation.tools.llm_bridge import LlmBridge

USAGE = Usage(input_tokens=10, output_tokens=5, cache_read_tokens=0, cache_write_tokens=0)
"""가상 사용량."""
DOCUMENT = (
    "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 회사는 가상 사업을 넓혔습니다. 가상 지표를 관리합니다.\n"
    "[PAGE 2]\n[TABLE 1]\n| 구분 | 가상 값 |\n|---|---|\n| 가상 항목 | 12 |\n"
)
"""지어낸 문서: 서술 쪽(번역·윤문·범용 QA·용어집·한국어 자리) + 표 쪽(표 묶음·칸 자리)."""
GLOSSARY = (("가상 회사", "Virtual Co."),)
PARTS = ("ceo_message", "story", "general")
STYLES = ("A", "B", "AB")
REPLIES: dict[str, str] = {
    "review": json.dumps(
        [
            {
                "issue_type": "GRAMMAR",
                "severity": "HIGH",
                "page_num": 1,
                "original_span": "Virtual body",
                "suggestion": "Virtual text",
                "reason": "가상 이유",
            }
        ],
        ensure_ascii=False,
    ),
    "editorial-qa": json.dumps(
        {"quality_score": 99, "has_critical_issue": False, "issues": [], "revised_text": ""}, ensure_ascii=False
    ),
    "table-batch": "not json — 칸마다 다시(cell 자리)",
    "autofix": "[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual text.\n남은 가상 문장",
    "autofix-korean": "[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual text.",
}
"""자리마다 심는 답(지어낸 글). 그 밖 자리는 TRANSLATED, 한국어를 남기는 자리(LEFT_KOREAN)는 그 뒤에 국문 한 줄 —
한국어 보정 두 자리(korean-repair·autofix-korean)가 돈다."""
LEFT_KOREAN = ("section", "polish", "glossary-repair")
TRANSLATED = (
    "[BLOCK 1]\nVirtual Title\nThe virtual company expanded its virtual business across several virtual markets "
    "and manages its virtual indicators every year."
)
"""윤문·범용 QA 가 도는 길이(120자 넘음), 용어집 값(Virtual Co.)이 없어 용어집 보정이 돈다."""


def case_input(part: str, style: str) -> EngineInput:
    return make_input(DOCUMENT, part=part, base=GLOSSARY, compare_ab=style == "AB", single="A" if style == "A" else "B")


class _Answering:
    """다리를 감싸 자리마다 답을 하나 심고 부른다. 공급사가 받은 요청 몸을 자리와 함께 적는다."""

    def __init__(self, bridge: LlmBridge, openai: MockProvider) -> None:
        self.bridge = bridge
        self.openai = openai
        self.sites: list[str] = []

    def complete(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> GatewayText:
        text = REPLIES.get(site, TRANSLATED) + ("\n남은 가상 문장" if site in LEFT_KOREAN else "")
        self.openai.enqueue(Completed(text=text, usage=USAGE))
        self.sites.append(site)
        return self.bridge.complete(site, role, system, user, max_tokens)


def sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def calls_of(inputs: EngineInput, bridge_of: Any = None) -> list[dict[str, object]]:
    """`pipeline.run` 한 번의 호출 열. bridge_of(client, part) 가 있으면 그것으로 다리를 짓는다(시험이 칸을 바꿀 때)."""
    anthropic, openai = MockProvider("anthropic"), MockProvider("openai")
    log = MemorySink()
    llm = client({"anthropic": anthropic, "openai": openai}, log)
    bridge = (
        LlmBridge(llm, part=inputs.part, tenant="tenant-synthetic")
        if bridge_of is None
        else bridge_of(llm, inputs.part)
    )
    answering = _Answering(bridge, openai)
    pipeline.run(inputs, answering)
    assert anthropic.calls == []
    assert len(openai.calls) == len(answering.sites) == len(log.records)
    return [
        {"site": site, "prompt": record.prompt_id, "model": record.model, "request": sent.to_json()}
        for site, record, sent in zip(answering.sites, log.records, openai.calls, strict=True)
    ]


def plan_of(inputs: EngineInput) -> dict[str, object]:
    planned = plan.plan(inputs)
    estimate = LlmBridge(
        client({"anthropic": MockProvider("anthropic"), "openai": MockProvider("openai")}),
        part=inputs.part,
        tenant="tenant-synthetic",
    ).dry_run(planned)
    return {"calls": [dataclasses.asdict(c) for c in planned.calls], "dryRun": estimate}


def digest() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for part in PARTS:
        for style in STYLES:
            inputs = case_input(part, style)
            out[f"{part}/{style}"] = {"calls": sha(calls_of(inputs)), "plan": sha(plan_of(inputs))}
    return out


if __name__ == "__main__":
    json.dump(digest(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
