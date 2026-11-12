"""엔진이 받는 글 열넷과 다리가 받는 모델 칸 셋(TR4 §3-1). 실호출 0 — 모의 공급사뿐.

1. 기본 글 = 상수, 덩어리 둘이 조립 글 안에 있다. 2. 자동 수정 틀 둘 = 코랩 f-문자열 함수. 3. 기본 글·기본 칸의
요청은 BASE 와 바이트 같다(지문 — `texts_digest.py`, BASE 트리 대조는 `scripts/section4-TR4.sh`). 4. 칸 글 하나를 바꾸면
그 글이 쓰이는 자리의 system 에만 간다(user 0). 5. 모델 칸은 맡는 자리에만, 출력 상한은 min(자리 값, 칸 위끝).
"""

import dataclasses
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import DryRunReport
from esgapi.translation.engines.colab_158 import plan, prompts
from esgapi.translation.engines.colab_158.pipeline import EngineInput
from esgapi.translation.engines.colab_158.plan import CallPlan, PlannedCall
from esgapi.translation.engines.colab_158.texts import DEFAULT_TEXTS, PromptTexts
from esgapi.translation.tests.engines.colab_158.support import LIGHT, LIGHT_MODEL, STANDARD, STANDARD_MODEL, client, ok
from esgapi.translation.tests.engines.colab_158.texts_digest import PARTS, STYLES, calls_of, case_input, digest
from esgapi.translation.tools.llm_bridge import (
    CEO_TRANSLATE_ROUTE,
    DEFAULT_MODELS,
    REVIEW_ROUTE,
    REVIEW_SITES,
    TRANSLATE_ROUTE,
    TRANSLATE_SITES,
    CallModel,
    LlmBridge,
    TranslationModels,
    model_for,
)

PAGE_SYSTEM_SITES = ("cell", "table-batch", "section", "polish", "editorial-qa", "glossary-repair", "korean-repair")
"""쪽 system(회사 문체 + 용어 안내 + 고른 문체)을 싣는 일곱 자리."""
BASE_DIGEST = {
    "ceo_message/A": {
        "calls": "2d615f9810b3d21ce5dd010a16e95cf5328bebf01f9b56831b1f9174e7268b6f",
        "plan": "339269dcb22e6d1f9b35520d23aed8380fda66c0298b4cc4bcc593676e680b99",
    },
    "ceo_message/AB": {
        "calls": "69735806729821202d2a4a9c358703305e0e3b7b9775831aaee094e24cae0742",
        "plan": "c63ac9a0384d36da91d51d41e4983f1015ec093761830f071833b9c2a20468dd",
    },
    "ceo_message/B": {
        "calls": "1b6b63afd88e9887d4c7f0404f08198bf32def458d43c8282d168f172d860f6d",
        "plan": "e1146f293d7a267d89845f7d77e6ceebca400680f6d0c1920023e4db54dee279",
    },
    "general/A": {
        "calls": "2a246a858fbb64e80e5712a0e80be261968a0292f5b59cfa9312b14919e55c48",
        "plan": "b9627e848badd659b610e9cf494f604a8f3b1ccaba2edf21c92c1ec800b460c8",
    },
    "general/AB": {
        "calls": "39d2af8ed36d3c6a6b13e0567f4f57992ba84cf3ef3b7612c4d61e6f8bab0633",
        "plan": "92a7393b09660d26a1cdfd8a99663448db00f2787c1732eb9b1ad4fb11c88c3a",
    },
    "general/B": {
        "calls": "0cf956d08b56cd4768680f6f86e00a66e22d98e4eb7e2ac031e3a42e2a44c72e",
        "plan": "250e36289b11860abc8200c373b2c4576e80dd973a9fbdf4c6cbb96a4cd5890d",
    },
    "story/A": {
        "calls": "bcdd4d48ca5318cd683a85b0e7875380ac25e83f825207241aa1ba60baa5d2ee",
        "plan": "8fa2495c1afe0b7335a3cb813e7bf183a12ee8451ab2e4baeec44689df2ca926",
    },
    "story/AB": {
        "calls": "261436fd4d462dfc95b7f1ac715f85134c69c02b5bed5d8bd920004e3cb380cb",
        "plan": "80469fd2a847d172c00bbd255ca554ec98c37767924c0b2405ffd8efde4e688c",
    },
    "story/B": {
        "calls": "66c9248661cf94df232c1c9cb6263aa7aa17e40fdab9a932aaa19b8d816bf89f",
        "plan": "9f7249fbd4f0c3bc6fa08b396016b40972e25a868897239f231f2d6cd6a15d66",
    },
}
"""BASE(cf8b1a43) 트리에 texts_digest.py 를 넣어 잰 지문(TR4.out/texts-digest-base.json) — 경우 아홉."""


def peer(with_peer: bool) -> str | None:
    return "Virtual peer writes short sentences.\n" if with_peer else None


# ── 1. 기본 글 ──


def test_the_default_texts_are_the_engine_constants() -> None:
    assert (
        PromptTexts(
            ceo_message_tone=prompts.CEO_MESSAGE_TONE,
            story_tone=prompts.STORY_TONE,
            general_tone=prompts.GENERAL_TONE,
            style_a=prompts.STYLE_A_PROMPT,
            style_b=prompts.STYLE_B_PROMPT,
            style_rules=prompts.STYLE_RULES_BLOCK,
            subject_fragment_rules=prompts.SUBJECT_FRAGMENT_RULES_BLOCK,
            terminology_note=prompts.TERMINOLOGY_NOTE,
            table_rules=prompts.TABLE_TRANSLATION_RULES,
            polish=prompts.BILINGUAL_EDITORIAL_POLISH_PROMPT,
            editorial_qa=prompts.GENERIC_EDITORIAL_QA_PROMPT,
            review=prompts.QA_SYSTEM_PROMPT,
            autofix=DEFAULT_TEXTS.autofix,
            autofix_korean=DEFAULT_TEXTS.autofix_korean,
        )
        == DEFAULT_TEXTS
    )
    # 덩어리 둘은 그 상수 다섯·둘을 머리째 이은 글(앞 빈 줄 뗌)
    assert DEFAULT_TEXTS.style_rules.startswith("Official English report style guidance:\n")
    assert DEFAULT_TEXTS.style_rules.endswith(prompts.NUMBER_UNIT_PROMPT.strip())
    assert DEFAULT_TEXTS.subject_fragment_rules.startswith("Subject pronoun consistency guidance:\n")
    assert DEFAULT_TEXTS.subject_fragment_rules.endswith(prompts.FRAGMENTARY_CONTENT_PROMPT.strip())


@pytest.mark.parametrize("with_peer", [False, True])
@pytest.mark.parametrize("part", ["ceo_message", "story", "general"])
def test_the_blocks_sit_in_the_assembled_company_style(part: str, with_peer: bool) -> None:
    """덩어리 둘은 조립 글 안에 그대로 있다 — 문체·어휘 규칙은 톤 앞, 주어·짧은 글 규칙은 톤 뒤."""
    company = DEFAULT_TEXTS.company_style(part, "가상고객사", "가상 업종", "GRI", peer(with_peer))
    assert company == prompts.build_company_style_prompt(part, "가상고객사", "가상 업종", "GRI", peer(with_peer))
    tone = DEFAULT_TEXTS.tone_for(part).strip()
    rules, subject = DEFAULT_TEXTS.style_rules, DEFAULT_TEXTS.subject_fragment_rules
    assert company.index(rules) < company.index(tone) < company.index(subject)
    assert company.count(rules) == company.count(subject) == 1


def test_an_unknown_part_takes_the_general_tone() -> None:
    assert DEFAULT_TEXTS.tone_for("x") == DEFAULT_TEXTS.tone_for("general") == prompts.GENERAL_TONE
    assert DEFAULT_TEXTS.tone_for("ceo_message") == prompts.CEO_MESSAGE_TONE
    assert DEFAULT_TEXTS.tone_for("story") == prompts.STORY_TONE


# ── 2. 자동 수정 틀 ──


@pytest.mark.parametrize("page_num", [1, 7, 10, 123, 987654])
def test_the_autofix_templates_give_the_colab_text(page_num: int) -> None:
    assert DEFAULT_TEXTS.autofix_system(page_num) == prompts.autofix_system(page_num)
    assert DEFAULT_TEXTS.autofix_korean_system(page_num) == prompts.autofix_korean_system(page_num)
    assert "{page_num}" not in DEFAULT_TEXTS.autofix_system(page_num)


def test_the_autofix_templates_keep_the_slot_in_every_place() -> None:
    """틀은 쪽 번호 자리마다 자리표 — 자동 수정 하나, 보정 둘(R/6665·6755)."""
    assert DEFAULT_TEXTS.autofix.count("{page_num}") == 1
    assert DEFAULT_TEXTS.autofix_korean.count("{page_num}") == 2


# ── 3. 기본 바이트 같음 ──


def test_the_default_requests_are_the_base_digest() -> None:
    """지문의 값은 BASE(cf8b1a43) 트리에서 같은 파일로 잰 것이다(scripts/section4-TR4.sh 가 실행 때 다시 견준다)."""
    assert digest() == BASE_DIGEST


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("part", PARTS)
def test_naming_the_defaults_changes_no_byte(part: str, style: str) -> None:
    """texts·models 를 빼고 돈 것 = DEFAULT_* 를 이름으로 넘겨 돈 것(호출 열·계획 둘 다)."""
    bare = case_input(part, style)
    named = dataclasses.replace(bare, texts=DEFAULT_TEXTS)
    assert calls_of(bare) == calls_of(named, with_models(DEFAULT_MODELS))
    assert plan.plan(bare) == plan.plan(named)


# ── 4. 칸 글 양성 ──


def with_models(models: TranslationModels) -> Callable[[LlmClient, str], LlmBridge]:
    return lambda llm, part: LlmBridge(llm, part=part, tenant="tenant-synthetic", models=models)


def mark(field: str) -> str:
    return f"⟦TR4-{field}⟧"


def marked(field: str) -> PromptTexts:
    return dataclasses.replace(DEFAULT_TEXTS, **{field: mark(field)})


FIELD_SITES: dict[str, tuple[str, ...]] = {
    "style_rules": PAGE_SYSTEM_SITES,
    "subject_fragment_rules": PAGE_SYSTEM_SITES,
    "terminology_note": PAGE_SYSTEM_SITES,
    "table_rules": ("table-batch",),
    "polish": ("polish",),
    "editorial_qa": ("editorial-qa",),
    "review": ("review",),
    "autofix": ("autofix",),
    "autofix_korean": ("autofix-korean",),
}
"""글 → 그 글이 system 에 드는 자리(모든 파트·문체). 파트 톤·문체는 아래 따로(그 파트·그 문체에서만)."""
TONES = {"ceo_message_tone": "ceo_message", "story_tone": "story", "general_tone": "general"}
STYLE_FIELDS = {"style_a": "A", "style_b": "B"}


def system_text(request: dict[str, object]) -> str:
    return "".join(cast("str", segment["text"]) for segment in cast("list[dict[str, object]]", request["system"]))


def user_text(request: dict[str, object]) -> str:
    return repr(request["user"])


def carrying(field: str, inputs: EngineInput) -> tuple[set[str], set[str], set[str]]:
    """(그 표지가 system 에 든 자리, 표지가 없는 자리, 표지가 user 에 든 자리) — 돈 호출과 계획 둘 다."""
    texts = marked(field)
    given = dataclasses.replace(inputs, texts=texts)
    hit, miss, in_user = set[str](), set[str](), set[str]()
    for call in calls_of(given):
        request = cast("dict[str, object]", call["request"])
        site = cast("str", call["site"])
        (hit if mark(field) in system_text(request) else miss).add(site)
        if mark(field) in user_text(request):
            in_user.add(site)
    for planned in plan.plan(given).calls:
        (hit if mark(field) in planned.system else miss).add(f"plan:{planned.site}")
        if mark(field) in planned.user:
            in_user.add(f"plan:{planned.site}")
    return hit, miss, in_user


def every_site(sites: tuple[str, ...]) -> set[str]:
    return {*sites, *(f"plan:{site}" for site in sites)}


@pytest.mark.parametrize("field", sorted(FIELD_SITES))
def test_a_text_goes_to_its_sites_system_only(field: str) -> None:
    hit, miss, in_user = carrying(field, case_input("general", "AB"))
    assert hit == every_site(FIELD_SITES[field])
    assert not hit & miss  # 그 자리면 늘 든다
    assert in_user == set()


@pytest.mark.parametrize("field", sorted(TONES))
@pytest.mark.parametrize("part", PARTS)
def test_a_tone_goes_only_to_its_part(field: str, part: str) -> None:
    hit, miss, in_user = carrying(field, case_input(part, "AB"))
    if TONES[field] == part:
        assert hit == every_site(PAGE_SYSTEM_SITES)
        assert not hit & miss
    else:
        assert hit == set()
    assert in_user == set()


@pytest.mark.parametrize("field", sorted(STYLE_FIELDS))
@pytest.mark.parametrize("style", STYLES)
def test_a_style_goes_only_where_it_is_chosen(field: str, style: str) -> None:
    hit, _, in_user = carrying(field, case_input("story", style))
    chosen = style == "AB" or STYLE_FIELDS[field] == style
    assert hit == (every_site(PAGE_SYSTEM_SITES) if chosen else set())
    assert in_user == set()


# ── 5. 모델 칸 양성 ──

CEO = CallModel(LIGHT, 3000)
OTHER = CallModel(STANDARD, 2000)
REVIEW = CallModel(STANDARD, 1500)
SWAPPED = TranslationModels(translate_ceo=CEO, translate_other=OTHER, review=REVIEW)
"""기본과 다른 값 셋(경로가 기본과 뒤바뀜·위끝이 자리 값 사이)."""
MODEL_IDS = {LIGHT: LIGHT_MODEL, STANDARD: STANDARD_MODEL}


def expected_slot(site: str, part: str) -> CallModel:
    return model_for("review" if site in REVIEW_SITES else "translate", part, SWAPPED)


@pytest.mark.parametrize("part", PARTS)
def test_each_slot_drives_only_its_sites(part: str) -> None:
    calls = calls_of(case_input(part, "AB"), with_models(SWAPPED))
    assert {cast("str", c["site"]) for c in calls} == set(prompts.SITES)  # 분모: 열 자리를 다 불렀다
    for call in calls:
        site = cast("prompts.Site", call["site"])
        request = cast("dict[str, object]", call["request"])
        slot = expected_slot(site, part)
        assert request["apiModelId"] == MODEL_IDS[slot.route], site
        assert request["maxOutputTokens"] == min(prompts.MAX_TOKENS[site], slot.max_output_tokens), site
        assert "temperature" not in request, site


def test_the_cap_is_the_smaller_of_the_site_and_the_slot() -> None:
    """R4 (가): cell 은 칸 8192 에도 1024, 칸 2000 이면 table-batch 2000 — 자리 값이 칸 위끝보다 크면 눌릴 뿐 오류 0."""
    calls = calls_of(case_input("general", "A"), with_models(SWAPPED))
    caps: dict[prompts.Site, object] = {
        cast("prompts.Site", c["site"]): cast("dict[str, object]", c["request"])["maxOutputTokens"] for c in calls
    }
    assert caps["cell"] == 1024
    assert caps["table-batch"] == 2000
    assert caps["review"] == 1500
    default = calls_of(case_input("general", "A"))
    assert {cast("str", c["site"]): cast("dict[str, object]", c["request"])["maxOutputTokens"] for c in default} == {
        site: prompts.MAX_TOKENS[site] for site in caps
    }


class _DryRuns:
    """클라이언트의 dry_run 을 감싸 보고를 적는다(공급사 호출 0)."""

    def __init__(self, inner: LlmClient) -> None:
        self.inner = inner
        self.requests: list[CallRequest[Any]] = []
        self.reports: list[DryRunReport] = []

    def dry_run(self, request: CallRequest[Any]) -> DryRunReport:
        self.requests.append(request)
        report = self.inner.dry_run(request)
        self.reports.append(report)
        return report


def dry_runs(
    part: str, models: TranslationModels, given: CallPlan | None = None
) -> Iterator[tuple[prompts.Site, Any, Any]]:
    providers = {"anthropic": MockProvider("anthropic"), "openai": MockProvider("openai")}
    recorder = _DryRuns(client(providers))
    bridge = LlmBridge(cast("LlmClient", recorder), part=part, tenant="t", models=models)
    planned = plan.plan(case_input(part, "AB")) if given is None else given
    bridge.dry_run(planned)
    assert providers["openai"].calls == [] and providers["anthropic"].calls == []
    for call, request, report in zip(planned.calls, recorder.requests, recorder.reports, strict=True):
        yield call.site, request, report


@pytest.mark.parametrize("part", PARTS)
def test_the_dry_run_uses_the_slots_too(part: str) -> None:
    seen = set[str]()
    for site, request, report in dry_runs(part, SWAPPED):
        slot = expected_slot(site, part)
        assert request.route == slot.route, site
        assert request.max_output_tokens == min(prompts.MAX_TOKENS[site], slot.max_output_tokens), site
        assert request.temperature is None
        assert cast("dict[str, object]", report.request)["apiModelId"] == MODEL_IDS[slot.route]
        assert "temperature" not in cast("dict[str, object]", report.request)
        seen.add(site)
    assert seen == set(prompts.SITES)  # 분모: 계획이 열 자리를 다 셌다


def test_a_site_cap_over_the_slot_is_pressed_down_without_error() -> None:
    """R4 의 잠금(감독 10-23): 자리 값이 칸 위끝보다 크면 요청은 칸 위끝 — 설정 오류가 아니다."""
    one = CallPlan(part="general", calls=[PlannedCall("section", "translate", "s", "u", 10**7, 1, 1, "single")])
    ((_, request, report),) = list(dry_runs("general", SWAPPED, one))
    assert request.max_output_tokens == OTHER.max_output_tokens
    assert report.estimate.max_output_tokens == OTHER.max_output_tokens
    openai = MockProvider("openai").enqueue(ok("x"))
    LlmBridge(client({"openai": openai}), part="general", tenant="t", models=SWAPPED).complete(
        "section", "translate", "s", "u", 10**7
    )
    (sent,) = openai.calls
    assert sent.max_output_tokens == OTHER.max_output_tokens


def test_the_default_slots_are_the_route_constants_and_the_widest_site() -> None:
    """기본 위끝 = 그 칸이 맡는 자리 max_tokens 의 최댓값(R4) — 그래서 기본은 자리 값 그대로."""
    assert tuple(s for s in prompts.SITES if s != "review") == TRANSLATE_SITES
    assert REVIEW_SITES == ("review",)
    widest = max(prompts.MAX_TOKENS[s] for s in TRANSLATE_SITES)
    assert (
        TranslationModels(
            CallModel(CEO_TRANSLATE_ROUTE, widest),
            CallModel(TRANSLATE_ROUTE, widest),
            CallModel(REVIEW_ROUTE, prompts.MAX_TOKENS["review"]),
        )
        == DEFAULT_MODELS
    )
    assert all(prompts.MAX_TOKENS[s] <= widest for s in TRANSLATE_SITES)
