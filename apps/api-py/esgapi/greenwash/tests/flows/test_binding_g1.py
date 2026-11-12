"""끼움 greenwash.engine@G1(flows/binding_g1 — 밴드 GE1b ② T9·T10·T11·T14): 실행 스위치 · 옵션 받기(E0 의 parts 글
그대로) · 판 열쇠(설정 세 층 — MARC-ENT-651) · 돌 때 판 대조 · 어댑터 · import 무게. 순수(DB 0). 값은 지어낸 것.
"""

import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, cast

import pytest

from esgapi.core.documents.contract import EPOCH
from esgapi.core.flows.binding import (
    DocumentInput,
    RunFactsBinding,
    RunOptionsRejected,
    RunVersionsMismatch,
    RunVersionsRejected,
)
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.llm.embedding import ClientEmbeddingPort
from esgapi.core.llm.prompts import PackagePromptStore, PromptRef, PromptTemplate
from esgapi.greenwash.flows import binding_e0, binding_g1, colab_e0, criteria_e0
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.tests.flows.test_engine_g1_flow import JsonDocument

PARTS: dict[str, object] = {"ceo": [1], "company": [2, 3], "climate": []}
DOCUMENT = DocumentInput(content=b"%PDF-synthetic", media_type="application/pdf", file_name="가상.pdf")
SHA64 = re.compile(r"^[0-9a-f]{64}$")


class RealModels:
    def config(self) -> LlmConfig:
        return load_config(default_config_sources(synthetic=False))


class Documents:
    def __init__(self) -> None:
        self.asked: list[tuple[int, int]] = []

    def for_run(self, company_id: int, run_id: int) -> E.G1Document:
        self.asked.append((company_id, run_id))
        return JsonDocument()


class ChangedPrompt:
    """하나의 지시문 sha 만 다른 PromptStore."""

    def __init__(self, changed: str) -> None:
        self.inner = PackagePromptStore()
        self.changed = changed

    def get(self, ref: PromptRef) -> PromptTemplate:
        got = self.inner.get(ref)
        return replace(got, hash="0" * 64) if got.id == self.changed else got


def binding(*, enabled: bool = True, prompts: Any = None, models: Any = None) -> binding_g1.G1Binding:
    return binding_g1.G1Binding(
        runs_enabled=lambda: enabled,
        documents=Documents(),
        models=models or RealModels(),
        prompts=prompts or PackagePromptStore(),
    )


def refusal(call: Any) -> str:
    with pytest.raises(RunOptionsRejected) as got:
        call()
    return got.value.message


# ── T9 스위치 · 옵션 ──


def test_the_switch_off_refuses_every_option_set_with_its_sentence() -> None:
    off = binding(enabled=False)
    for options in ({"parts": PARTS}, {}, {"nope": 1}):
        assert refusal(lambda o=options: off.check_options(o)) == binding_g1.SWITCH_OFF
    assert binding_g1.SWITCH_OFF == "그린워싱 2차 엔진 실행은 아직 열려 있지 않아요. 운영자에게 알려 주세요"


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"parts": []},
        {"parts": {"ceo": [1]}},
        {"parts": {"ceo": [1], "company": [], "climate": [], "board": []}},
        {"parts": {"ceo": [True], "company": [], "climate": []}},
        {"parts": {"ceo": [0], "company": [], "climate": []}},
        {"parts": {"ceo": [], "company": [], "climate": []}},
        {"parts": {"ceo": "1", "company": [], "climate": []}},
    ],
)
def test_the_parts_refusals_are_the_e0_sentences(options: Mapping[str, object]) -> None:
    on = binding()
    assert refusal(lambda: on.check_options(options)) == refusal(lambda: binding_e0.accept_options(options))


@pytest.mark.parametrize(
    ("options", "sentence"),
    [
        ({"parts": PARTS, "extraTerms": []}, "알 수 없는 옵션이에요: extraTerms"),
        ({"parts": PARTS, "reportYear": 2025, "a": 1}, "알 수 없는 옵션이에요: a, reportYear"),
        ({"parts": PARTS, "criteriaId": 3}, binding_g1.NULL_ONLY_REFUSED),
        ({"parts": PARTS, "industry": "가상"}, binding_g1.NULL_ONLY_REFUSED),
        ({"parts": PARTS, "humanEvidence": []}, binding_g1.NULL_ONLY_REFUSED),
    ],
)
def test_unknown_keys_and_filled_null_only_fields_are_refused(options: Mapping[str, object], sentence: str) -> None:
    assert refusal(lambda: binding().check_options(options)) == sentence


def test_accepted_options_become_the_inputs_with_the_default_third_layer() -> None:
    on = binding()
    options = {"parts": PARTS, "criteriaId": None, "industry": None, "humanEvidence": None}
    on.check_options(options)
    got = on.inputs(DOCUMENT, options)
    assert got.parts == {"ceo": (1,), "company": (2, 3), "climate": ()}
    assert got.criteria == E.default_criterion_lines() and got.categories == E.CATEGORIES == ()
    assert (got.criteria_id, got.variant, got.industry, got.human_evidence) == (None, None, None, None)


# ── T10 판 열쇠 ──


def test_the_version_keys_are_fixed_and_stable() -> None:
    on = binding()
    one = on.versions_with({"parts": PARTS}, company_id=1)
    assert one == on.versions_with({"parts": PARTS}, company_id=2) == on.versions({"parts": PARTS})
    assert list(one) == [
        "engine",
        "promptIds",
        "promptTextsSha256",
        "routes",
        "parserLayout",
        "epoch",
        "criteriaId",
        "criteriaVersion",
        "criteriaSha256",
        "categoriesSha256",
        "variant",
    ]
    assert "promptsSha256" not in one and "flow" not in one  # core ai_versions 와 다른 이름(R2) · flow 는 runs 가 붙임
    config = RealModels().config()
    assert one["engine"] == "G1"
    assert one["promptIds"] == {
        "facets": "greenwash/ge-facets@1",
        "rerank": "greenwash/ge-rerank@1",
        "judge": "greenwash/ge-judge@1",
        "detect": colab_e0.PROMPT_IDS["detect"],
    }
    shas = cast("dict[str, str]", one["promptTextsSha256"])
    assert set(shas) == {"facets", "rerank", "judge", "detect"} and all(SHA64.match(v) for v in shas.values())
    assert len(set(shas.values())) == 4
    assert one["routes"] == {
        "chat": {"route": E.ROUTE, "models": list(config.routes[E.ROUTE])},
        "embedding": {"route": E.EMBEDDING_ROUTE, "model": config.embedding_routes[E.EMBEDDING_ROUTE]},
    }
    assert (one["parserLayout"], one["epoch"], one["criteriaId"], one["variant"]) == (2, EPOCH, None, None)
    assert one["criteriaVersion"] == criteria_e0.DEFAULT_VERSION
    assert one["criteriaSha256"] == binding_g1.criteria_sha256(E.default_criterion_lines())
    assert one["categoriesSha256"] == binding_g1.categories_sha256(())


@dataclass
class OneRoute:
    """채팅 경로가 없는 모델 원천."""

    def config(self) -> LlmConfig:
        real = RealModels().config()
        return replace(real, routes={k: v for k, v in real.routes.items() if k != E.ROUTE})


def test_a_missing_route_refuses_the_versions() -> None:
    with pytest.raises(RunVersionsRejected):
        binding(models=OneRoute()).versions_with({"parts": PARTS}, company_id=1)


# ── T11 돌 때 판 대조 ──


def made() -> dict[str, object]:
    return {**binding().versions_with({"parts": PARTS}, company_id=1), "flow": E.FLOW_ID}


def test_the_same_versions_give_the_inputs() -> None:
    got = binding().inputs_with(DOCUMENT, {"parts": PARTS}, company_id=1, versions=made())
    assert got.parts["company"] == (2, 3)


@pytest.mark.parametrize(
    "prompt", ["greenwash/ge-judge@1", "greenwash/ge-facets@1", "greenwash/ge-rerank@1", "greenwash/detect@1"]
)
def test_a_changed_prompt_is_a_versions_mismatch(prompt: str) -> None:
    with pytest.raises(RunVersionsMismatch, match="promptTextsSha256"):
        binding(prompts=ChangedPrompt(prompt)).inputs_with(DOCUMENT, {"parts": PARTS}, company_id=1, versions=made())


@pytest.mark.parametrize(
    ("key", "value"), [("criteriaSha256", "0" * 64), ("epoch", EPOCH - 1), ("categoriesSha256", "1" * 64)]
)
def test_a_changed_key_is_a_versions_mismatch(key: str, value: object) -> None:
    with pytest.raises(RunVersionsMismatch, match=key):
        binding().inputs_with(DOCUMENT, {"parts": PARTS}, company_id=1, versions={**made(), key: value})


def test_a_route_gone_at_run_time_is_a_mismatch_not_a_refusal() -> None:
    with pytest.raises(RunVersionsMismatch):
        binding(models=OneRoute()).inputs_with(DOCUMENT, {"parts": PARTS}, company_id=1, versions=made())


@dataclass
class RenamedModel:
    """채팅 경로 이름은 그대로, 그 경로 안의 모델 이름만 다른 등록 모델로 바꾼 원천."""

    def config(self) -> LlmConfig:
        real = RealModels().config()
        other = next(name for name in real.models if name not in real.routes[E.ROUTE])
        return replace(real, routes={**real.routes, E.ROUTE: (other,)})


def test_a_renamed_model_inside_the_same_route_is_a_mismatch() -> None:
    with pytest.raises(RunVersionsMismatch, match="routes"):
        binding(models=RenamedModel()).inputs_with(DOCUMENT, {"parts": PARTS}, company_id=1, versions=made())


# ── 어댑터 ──


@dataclass(frozen=True)
class Ctx:
    company_id: int = 7
    run_id: int = 41
    module: str = "greenwash"
    flow_id: str = E.FLOW_ID
    attempt: int = 1
    calls: list[str] = field(default_factory=list[str])

    def llm(self) -> Any:
        self.calls.append("llm")
        return object()

    def embedding(self) -> Any:
        self.calls.append("embedding")
        return object()


def test_the_adapters_use_the_engine_routes_and_the_runs_document() -> None:
    documents = Documents()
    on = binding_g1.G1Binding(
        runs_enabled=lambda: True, documents=documents, models=RealModels(), prompts=PackagePromptStore()
    )
    ctx = Ctx()
    got = on.adapters(ctx)
    assert ctx.calls == ["llm", "embedding"]  # 대화 클라이언트 하나를 판정·탐지가 같이 쓴다
    assert documents.asked == [(7, 41)]
    assert isinstance(got.embedding, ClientEmbeddingPort)
    assert vars(got.embedding)["_route"] == E.EMBEDDING_ROUTE
    assert isinstance(got.detect, colab_e0.LlmChatBridge)
    assert (got.detect.route, got.detect.temperature, got.detect.client) == (E.ROUTE, None, got.client)
    assert (got.tags.tenant, got.tags.module) == ("7", "greenwash")
    assert isinstance(on, RunFactsBinding)


# ── T14 import 무게 ──

PROBE = """
import sys
import esgapi.greenwash.flows.binding_g1
print("pypdfium2" in sys.modules, "django" in sys.modules)
"""


def test_importing_the_g1_binding_loads_neither_pdfium_nor_django() -> None:
    done = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, check=True, timeout=60)
    assert done.stdout.strip().splitlines()[-1] == "False False"
