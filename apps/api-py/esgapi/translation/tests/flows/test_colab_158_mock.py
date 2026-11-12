"""모의 경로(MARC-ISSUE-331, 밴드 TRR1 T1·P4, 순수): 끼움의 mock 이 거짓이면 요청·결과가 TRR1 앞과 바이트 같고, 참이면
경로 셋 다 `mock`(MOCK_MODELS) — 입력의 모델 칸·versions 는 그대로. 실호출 0, 문서는 지어낸 것."""

import hashlib
import json

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowRun
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.tests.engines.colab_158.run_digest import _docx_sha  # pyright: ignore[reportPrivateUsage]
from esgapi.translation.tests.engines.colab_158.support import ok
from esgapi.translation.tests.flows.support import SIMPLE_EN, binding, document, options
from esgapi.translation.tools.llm_bridge import MOCK_MAX_OUTPUT_TOKENS, MOCK_MODELS, MOCK_ROUTE

NO_ISSUES = ok("[]")
LIVE_REQUESTS_SHA256 = "7f7130ee967a1ad280493ded256291c8e86844960a32653e70ac1b60c27cab97"
"""작은 지어낸 글(support.SIMPLE) 한 번의 요청 둘(공급사 요청 JSON — 경로 모델·max_tokens·봉투 글째)의 sha256.
TRR1 앞(BASE b437aaad)의 같은 셈과 같은 값(보고 T1)."""
LIVE_RESULT_SHA256 = "701c9c37764b97cea2deab57ad8c551189110c6e3d870138356d54e23c79bbc7"
"""같은 실행의 result@1 JSON(ensure_ascii False, sort_keys) sha256 — BASE 와 같은 값."""
LIVE_WORD_SHA256 = {
    "translation-bilingual-single.docx": "a217c23cfddad94db12cd556b23d0fb0d15d7f00c68e978b149223cd8ec8b377",
    "translation-qa-single.docx": "b7cb2f840ac8df3155b00b16c5b93ea4c8f59f48d2175e14f652a78d6dd1ce26",
    "translation-autofix-single.docx": "a217c23cfddad94db12cd556b23d0fb0d15d7f00c68e978b149223cd8ec8b377",
}
"""같은 실행의 Word 지문(run_digest._docx_sha — core.xml 시각만 가림) — BASE 와 같은 값."""


def _client(providers: dict[str, MockProvider], *, synthetic: bool) -> LlmClient:
    """support.client 꼴 — mock 이면 실행기처럼 가상 모델 파일도 싣는다(core setup.build_client 의 mock)."""
    return LlmClient(
        config=load_config(default_config_sources(synthetic=synthetic)),
        providers=providers,
        prompts=PackagePromptStore(),
        log=MemorySink(),
        provider_retry={},
        sleep=lambda _ms: None,
    )


def _run(*, mock: bool, given: dict[str, object] | None = None) -> tuple[list[dict[str, object]], FlowRun]:
    openai, fake = MockProvider("openai"), MockProvider(MOCK_ROUTE)
    for provider in (openai, fake):
        provider.enqueue(ok(SIMPLE_EN)).enqueue(NO_ISSUES)
    llm = _client({"anthropic": MockProvider("anthropic"), "openai": openai, "mock": fake}, synthetic=mock)
    inputs = binding().inputs_with(document(), given or options(), company_id=1, versions={})
    run = run_flow(colab.FLOW, inputs, colab.TranslationAdapters(llm=llm, tenant="1", mock=mock, spent_usd=lambda: 0.0))
    used = fake if mock else openai
    assert (fake if not mock else openai).calls == []  # 다른 쪽은 부르지 않는다
    return [r.to_json() for r in used.calls], run


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def test_t1_the_live_path_requests_and_result_are_the_bytes_before_trr1() -> None:
    requests, run = _run(mock=False)
    result = run.output.results[0]
    assert [(r["apiModelId"], r["maxOutputTokens"]) for r in requests] == [("gpt-4.1-mini", 4096)] * 2
    assert _sha(requests) == LIVE_REQUESTS_SHA256
    assert _sha(result) == LIVE_RESULT_SHA256
    assert {f.name: _docx_sha(f.content) for f in run.output.files} == LIVE_WORD_SHA256
    settings = result["settings"]
    assert isinstance(settings, dict)
    assert settings["routes"] == {"translate": "light-openai-41", "review": "light-openai-41"}


def test_mock_adapters_call_the_mock_route_and_say_so_in_the_result() -> None:
    requests, run = _run(mock=True)
    assert {r["apiModelId"] for r in requests} == {"mock-synthetic"}
    assert [r["maxOutputTokens"] for r in requests] == [MOCK_MAX_OUTPUT_TOKENS] * 2  # min(자리 4096, 4000)
    settings = run.output.results[0]["settings"]
    assert isinstance(settings, dict) and settings["routes"] == {"translate": MOCK_ROUTE, "review": MOCK_ROUTE}


def test_mock_models_cover_every_role_with_the_mock_route() -> None:
    assert {MOCK_MODELS.translate_ceo.route, MOCK_MODELS.translate_other.route, MOCK_MODELS.review.route} == {"mock"}
    assert MOCK_MODELS.translate_ceo.max_output_tokens == MOCK_MAX_OUTPUT_TOKENS == 4000


def test_mock_adapters_leave_the_inputs_models_alone() -> None:
    """mock 은 부를 때만 갈아 끼운다 — 입력의 모델 칸(판 sha 의 원천)은 그대로."""
    inputs = binding().inputs_with(document(), options(), company_id=1, versions={})
    assert inputs.models != MOCK_MODELS
