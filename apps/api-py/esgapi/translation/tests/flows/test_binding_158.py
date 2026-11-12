"""끼움 TranslationBinding(밴드 TR2 §3-1-7, 순수): options@1 strict 받기와 문장, 생략값(빈 용어집·peer 안 실음·autofix
true), 판 묶음, 금액 상한은 돌 때 읽음, 고정 스키마. 옵션은 지어낸 값이다."""

import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.calc.ai_settings import defaults, model_settings_sha256
from esgapi.core.flows.binding import RunOptionsRejected
from esgapi.translation.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.translation.contracts.options_shapes import GLOSSARY_PAIRS_MAX, OPTIONS_SHAPES, RETRY_PAGES_MAX, SHAPE
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows.binding_158 import TranslationBinding
from esgapi.translation.flows.prompt_model_158 import MODELS
from esgapi.translation.tests.flows.settings_store import DefaultOnlyStore, FileModels, file_config
from esgapi.translation.tests.flows.support import FakeStore, binding, document, options
from esgapi.translation.tools.llm_bridge import prompt_ids

RUN_OPTIONS_MAX_OCTETS = 16 * 1024
"""runs 의 옵션 상한 기본값(runs/models.py — 다른 모듈의 models 는 들이지 않는다, 계약 나).
값은 runs/tests/test_models_values.py 가 못 박는다."""
PINNED = Path(__file__).resolve().parents[1] / "data" / "flow-shapes" / "options" / f"{SHAPE}.schema.json"


def refused(given: dict[str, Any]) -> str:
    with pytest.raises(RunOptionsRejected) as caught:
        binding().check_options(given)
    return caught.value.message


def test_the_options_schema_is_pinned() -> None:
    pinned = json.dumps(OPTIONS_SHAPES[SHAPE].json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert pinned == PINNED.read_text(encoding="utf-8")


def test_the_retry_page_limit_matches_the_schema() -> None:
    schema = OPTIONS_SHAPES[SHAPE].json_schema()
    retry = schema["$defs"]["TranslationRetryOption"]["properties"]["pages"]
    assert (retry["minItems"], retry["maxItems"]) == (1, RETRY_PAGES_MAX)


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (options(criteria={}), "알 수 없는 옵션이에요: criteria"),
        (options(retry={"fromRunId": 1, "pages": [1], "x": 1}), "알 수 없는 옵션이에요: retry.x"),
        (options(retry={"fromRunId": 1, "pages": []}), "옵션 retry.pages의 값이 맞지 않아요"),
        (options(retry={"fromRunId": 1, "pages": list(range(1, 302))}), "옵션 retry.pages의 값이 맞지 않아요"),
        (options(retry={"fromRunId": 1, "pages": [0]}), "옵션 retry.pages의 값이 맞지 않아요"),
        (options(retry={"fromRunId": 1, "pages": [3, 3]}), "다시 번역할 쪽 번호가 겹쳐요"),
        (options(retry={"fromRunId": 0, "pages": [1]}), "옵션 retry.fromRunId의 값이 맞지 않아요"),
        (options(retry={"fromRunId": True, "pages": [1]}), "옵션 retry.fromRunId의 값이 맞지 않아요"),
        (options(autofix="yes"), "옵션 autofix의 값이 맞지 않아요"),
        ({k: v for k, v in options().items() if k != "part"}, "옵션 part의 값이 맞지 않아요"),
    ],
    ids=["unknown", "retry_unknown", "pages_0", "pages_301", "page_0", "dup", "from_0", "from_bool", "autofix", "part"],
)
def test_refused_options_say_one_sentence_with_key_names_only(given: dict[str, Any], message: str) -> None:
    assert refused(given) == message


BATCH = "0f1e2d3c-4b5a-4978-8a6b-5c4d3e2f1a0b"
"""지어낸 묶음 id(소문자 uuid)."""


@pytest.mark.parametrize(
    "batch",
    [BATCH.upper(), "0f1e2d3c4b5a49788a6b5c4d3e2f1a0b", f"{BATCH}x", f" {BATCH}", "", 12345, None],
    ids=["upper", "no_dashes", "tail", "space", "empty", "number", "null"],
)
def test_a_batch_id_that_is_not_a_lowercase_uuid_is_refused(batch: object) -> None:
    assert refused(options(batchId=batch)) == "옵션 batchId의 값이 맞지 않아요"


def test_a_batch_id_is_accepted_and_does_not_reach_the_flow_inputs() -> None:
    """묶음 id 는 실행 행의 옵션에만 남는다 — 흐름 입력(엔진·결과)은 묶음 id 와 무관하다(다시 하기 재현)."""
    b = binding()
    b.check_options(options(batchId=BATCH))
    given = b.inputs_with(document(), options(batchId=BATCH), company_id=1, versions={})
    assert given == b.inputs_with(document(), options(), company_id=1, versions={})


def test_each_glossary_list_takes_at_most_five_hundred_pairs() -> None:
    binding().check_options(options(glossary={"base": synthetic_glossary(500), "final": synthetic_glossary(500)}))
    assert refused(options(glossary={"base": synthetic_glossary(501)})) == "옵션 glossary.base의 값이 맞지 않아요"
    assert refused(options(glossary={"final": synthetic_glossary(501)})) == "옵션 glossary.final의 값이 맞지 않아요"
    schema = OPTIONS_SHAPES[SHAPE].json_schema()["$defs"]["TranslationOptionGlossary"]["properties"]
    assert schema["base"]["maxItems"] == schema["final"]["maxItems"] == GLOSSARY_PAIRS_MAX == 500


def test_three_hundred_retry_pages_are_accepted() -> None:
    binding().check_options(options(retry={"fromRunId": 1, "pages": list(range(1, 301))}))


def test_omitted_glossary_and_peer_are_the_same_request_as_empty_ones() -> None:
    """생략 = 빈 용어집·peer 안 실음·autofix true(저장소에 기본 용어집 없음)."""
    b = binding()
    omitted = b.inputs_with(document(), options(), company_id=1, versions={})
    given = b.inputs_with(
        document(),
        options(glossary={"base": [], "final": []}, peerGroupStyle=None, autofix=True),
        company_id=1,
        versions={},
    )
    half = b.inputs_with(document(), options(glossary={}), company_id=1, versions={})
    assert omitted == given == half
    assert (omitted.glossary_base, omitted.glossary_final, omitted.peer_group_style_prompt) == ((), (), None)
    assert omitted.autofix is True and omitted.retry is None


def test_the_versions_name_the_engine_flow_and_prompt_ids() -> None:
    versions = binding().versions_with(options(), company_id=1)
    assert versions == {
        "engine": "colab_158",
        "flow": colab.FLOW_ID,
        "promptIds": prompt_ids(),
        # TR4 ③ 기본 판의 판 열쇠(공통 셋은 core ai_versions — test_binding_158_settings.py)
        "aiSetting": DEFAULT_TITLE,
        "aiSettingId": None,
        "modelSettingsSha256": model_settings_sha256(defaults(file_config(), MODELS)),
    }
    assert binding().versions(options()) == {"engine": "colab_158", "flow": colab.FLOW_ID, "promptIds": prompt_ids()}


def test_the_budget_is_read_when_the_run_is_built_not_when_bound() -> None:
    seen: list[float] = []

    def limit() -> float:
        seen.append(3.0)
        return 3.0

    b = TranslationBinding(
        store=FakeStore(),
        settings=DefaultOnlyStore(),
        models=FileModels(),
        max_usd=limit,
        mock=lambda: False,
        spent_usd=lambda _c, _r: 0.0,
    )
    assert seen == []
    assert b.inputs_with(document(), options(), company_id=1, versions={}).max_usd == 3.0
    assert seen == [3.0]


def test_retry_reads_the_source_with_the_runs_company() -> None:
    store = FakeStore()
    binding(store).inputs_with(document(), options(retry={"fromRunId": 9, "pages": [2]}), company_id=4, versions={})
    assert store.asked == [(4, 9)]


def synthetic_glossary(n: int) -> list[dict[str, str]]:
    """지어낸 용어집 n 짝(국문 6자·영문 약 20자 — 실제 용어집이 아니다)."""
    return [{"ko": f"가상용어{i:04d}", "en": f"Virtual Term {i:04d}"} for i in range(n)]


def test_a_synthetic_164_plus_164_glossary_is_over_the_default_options_limit() -> None:
    """B2: 지어낸 164 + 164 짝을 실은 옵션은 runs 의 기본 옵션 상한(16KiB)을 넘는다 — 영문번역은 상한 256KiB 로
    등록해(apps.py, 밴드 TR3a) 실행 만들기가 받는다(업무 시험 test_runs_translation)."""
    given = options(glossary={"base": synthetic_glossary(164), "final": synthetic_glossary(164)})
    binding().check_options(given)
    size = len(json.dumps(given, ensure_ascii=False, separators=(",", ":")).encode())
    assert size > RUN_OPTIONS_MAX_OCTETS, size
