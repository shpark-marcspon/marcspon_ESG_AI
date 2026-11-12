"""중대성평가 IRO AI 설정 판의 선언과 ai.prompt-model@3(밴드 IR4 §3-3-1 — 순수 층, DB 0). dataverify
tests/flows/test_prompt_model_156.py 의 꼴.

    선언      check_module(SPEC) · 모델 칸 둘·묶음 여섯·칸 열넷이 발주서 2-1 · 기본 값이 흐름 코드 값 · promptId 문법
    @3        기본 판 strict · defaultText == 엔진 글 · outputSection 여섯 · editable 둘 true
    받기      research temperature null 거절 · analysis temperature 값 거절(core code 그대로) · core 꼴 code · 자리 지킴
              (날 글 칸 자리 전부 + 규제 지시 글 {신뢰 출처 목록}) · 지시·접두 글은 통째 바꿔도 됨 ·
              신뢰 출처 같은 글 거절
    옛 판     accept_stored(셋을 그 단계에서만 뗌 · 다른 단계·모르는 칸은 거절) · 저장 받기는 열일곱 거절 ·
              legacy_sha256 = 받은 그대로의 core sha · 셋은 늘 기본 글(IRA3 — MARC-ENT-569)
    잇기      texts_from·models_from 이 칸 key → 엔진·흐름 값 ·
              models_from(defaults) == 코드 값(M4)
    고정 값   한 번은 글자로 · AST: 0·1 밖 수·경로·단가 글자 0
설정은 패키지의 실제 파일이다(가상 경로 0). 글은 지어낸 것이다. 실제 AI 호출 0.
"""

import ast
import copy
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AcceptedPrompt,
    AcceptedPrompts,
    AcceptedPromptStep,
    ModelSettingRefused,
    PromptRefused,
    check_module,
    defaults,
    layout_of,
    prompts_sha256,
    unusable_routes,
)
from esgapi.core.contracts.ai_setting_shapes import PROMPT_MODEL_V3, AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.config import LlmConfig, default_config_sources, load_config
from esgapi.core.llm.prompts import parse_prompt_id
from esgapi.materiality.contracts import ai_setting_shapes as shapes
from esgapi.materiality.engines.colab_155 import texts
from esgapi.materiality.engines.colab_155.texts import DEFAULT_TEXTS
from esgapi.materiality.flows import binding_155, colab_155, part2_155
from esgapi.materiality.flows import prompt_model_155 as pm
from esgapi.materiality.flows.colab_155 import StageModel

CONFIG: LlmConfig = load_config(default_config_sources(synthetic=False))
RESEARCH_ROUTE = "standard-openai-4o"
ANALYSIS_ROUTE = "standard-openai-41"
KEYS = [f.name for f in dataclasses.fields(DEFAULT_TEXTS)]
LEGACY = ["regulation_input", "keywords_input", "controversy_input"]
"""엔진 칸이지만 판 칸이 아닌 셋(IRA3 — MARC-ENT-569)."""
BOARD_KEYS = [key for key in KEYS if key not in LEGACY]
"""판 칸 열넷(엔진 칸 차례에서 셋을 뺀 차례)."""
CODE_MODEL = (colab_155.CODE_RESEARCH, part2_155.CODE_ANALYSIS)


def model_body(
    *,
    route: str = RESEARCH_ROUTE,
    temperature: Any = 0.1,
    web_search: bool = True,
    cap: int = 16384,
    analysis_route: str = ANALYSIS_ROUTE,
    analysis_temperature: Any = None,
    analysis_web_search: bool = False,
    analysis_cap: int = 32768,
) -> AiModelSettingsIn:
    return {
        "steps": [
            {
                "key": "research",
                "route": route,
                "temperature": temperature,
                "webSearch": web_search,
                "maxOutputTokens": cap,
            },
            {
                "key": "analysis",
                "route": analysis_route,
                "temperature": analysis_temperature,
                "webSearch": analysis_web_search,
                "maxOutputTokens": analysis_cap,
            },
        ]
    }


def prompts_body(**changed: str) -> AiPromptsIn:
    """기본 글 열넷(메모 = 기본 메모) — changed 의 칸만 그 글. layout 밖 key 는 거절(조용히 버리면 거짓 초록 — IRA3)."""
    assert set(changed) <= {k for _, ks in pm.LAYOUT for k in ks}, sorted(changed)
    return {
        "steps": [
            {
                "key": group,
                "prompts": [
                    {"key": key, "text": changed.get(key, pm.default_text(key)), "memo": pm.DEFAULT_MEMOS[key]}
                    for key in keys
                ],
            }
            for group, keys in pm.LAYOUT
        ]
    }


LEGACY_LAYOUT: list[tuple[str, list[str]]] = [
    ("regulation", ["regulation_system", "regulation_prefix", "regulation_input"]),
    (
        "controversy",
        [
            "keywords_system",
            "keywords_prefix",
            "keywords_input",
            "controversy_system",
            "controversy_prefix",
            "controversy_input",
        ],
    ),
    ("impact", ["impact_system", "impact_input"]),
    ("financial", ["financial_system", "financial_input"]),
    ("pathway", ["pathway_system", "pathway_input"]),
    ("whitelist", ["whitelist_non_financial", "whitelist_financial"]),
]
"""옛 판(IRA3 앞 — 칸 열일곱)의 layout."""
OLD_TEXT = "⟦지어낸 옛 글⟧"


def legacy_body(**changed: str) -> AiPromptsIn:
    """옛 판의 저장 글(칸 열일곱) — 셋은 「⟦지어낸 옛 글⟧ <칸>」, 나머지는 기본 글(changed 의 칸만 그 글)."""
    assert set(changed) <= set(KEYS), sorted(changed)

    def text(key: str) -> str:
        if key in changed:
            return changed[key]
        return f"{OLD_TEXT} {key}" if key in LEGACY else pm.default_text(key)

    return {
        "steps": [
            {
                "key": group,
                "prompts": [
                    {"key": key, "text": text(key), "memo": "" if key in LEGACY else pm.DEFAULT_MEMOS[key]}
                    for key in keys
                ],
            }
            for group, keys in LEGACY_LAYOUT
        ]
    }


def accepted_prompts(given: AiPromptsIn) -> AcceptedPrompts:
    found = pm.accept_prompts(given)
    assert isinstance(found, AcceptedPrompts), found
    return found


def default_body() -> Any:
    return pm.prompt_model(CONFIG, setting_name=shapes.DEFAULT_NAME, model=defaults(CONFIG, pm.MODELS))


def position(key: str) -> tuple[int, int]:
    """칸 key → (묶음 차례, 묶음 안 차례)."""
    for i, (_, keys) in enumerate(pm.LAYOUT):
        if key in keys:
            return i, list(keys).index(key)
    raise KeyError(key)


# ── 선언 ──


def test_the_declaration_is_the_order() -> None:
    check_module(pm.SPEC)
    assert [(s.key, s.label, s.routes, s.tool_loop) for s in pm.MODELS] == [
        ("research", "리서치 모델", (RESEARCH_ROUTE,), True),
        ("analysis", "분석 모델", (ANALYSIS_ROUTE,), True),
    ]
    assert (pm.MODELS[0].routes, pm.MODELS[1].routes) == ((colab_155.ROUTE,), (part2_155.ROUTE_PART2,))
    assert [(g.key, g.label, g.prompt_keys, g.model_slots) for g in pm.GROUPS] == [
        (
            "regulation",
            "규제·정책 리서치",
            ("regulation_system", "regulation_prefix"),
            ("research",),
        ),
        (
            "controversy",
            "컨트로버시 리서치",
            ("keywords_system", "keywords_prefix", "controversy_system", "controversy_prefix"),
            ("research",),
        ),
        ("impact", "환경·사회 영향 정의", ("impact_system", "impact_input"), ("analysis",)),
        ("financial", "재무 영향 정의", ("financial_system", "financial_input"), ("analysis",)),
        ("pathway", "재무 영향 경로", ("pathway_system", "pathway_input"), ("analysis",)),
        ("whitelist", "신뢰 출처 목록", ("whitelist_non_financial", "whitelist_financial"), ("research",)),
    ]
    assert layout_of(pm.SPEC) == pm.LAYOUT
    assert [key for _, group in pm.LAYOUT for key in group] == BOARD_KEYS  # 칸 열넷 = 엔진 칸 차례에서 셋 뺌
    assert set(pm.LABELS) == set(pm.FIELDS) == set(pm.DEFAULT_MEMOS) == set(pm.PROMPT_IDS) == set(BOARD_KEYS)
    assert set(pm.FIELDS.values()) == set(BOARD_KEYS)
    assert len(BOARD_KEYS) == 14
    assert pm.PROMPT_VERSION == binding_155.ENGINE == shapes.DEFAULT_NAME
    assert unusable_routes(CONFIG, pm.MODELS) == ()


def test_the_default_model_values_are_the_flow_constants() -> None:
    model = defaults(CONFIG, pm.MODELS)  # ★D: 지금 설정에서 기본값이 받기를 지난다
    assert [(s.key, s.route, s.temperature, s.web_search, s.max_output_tokens) for s in model.steps] == [
        ("research", colab_155.ROUTE, colab_155.CODE_RESEARCH.temperature, True, colab_155.MAX_OUTPUT_TOKENS),
        ("analysis", part2_155.ROUTE_PART2, None, False, part2_155.MAX_OUTPUT_TOKENS_PART2),
    ]
    assert pm.models_from(model) == CODE_MODEL  # M4: 기본 판의 모델 = 흐름 코드 값


# ── @3 ──


def test_the_default_prompt_model_is_strict_v3() -> None:
    body = default_body()
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    assert (body["schemaVersion"], body["module"], body["settingName"]) == (
        "ai.prompt-model@3",
        "materiality",
        "colab_155",
    )
    assert body["editable"] == {"prompts": True, "model": True}
    assert [(s["key"], s["label"], s["unavailableRoutes"]) for s in body["models"]] == [
        ("research", "리서치 모델", []),
        ("analysis", "분석 모델", []),
    ]
    assert [[c["route"] for c in s["routeChoices"]] for s in body["models"]] == [[RESEARCH_ROUTE], [ANALYSIS_ROUTE]]
    assert [s["model"]["webSearch"] for s in body["models"]] == [True, False]
    assert [s["model"]["temperature"] for s in body["models"]] == [0.1, None]
    assert [g["key"] for g in body["promptGroups"]] == [
        "regulation",
        "controversy",
        "impact",
        "financial",
        "pathway",
        "whitelist",
    ]
    assert [g["modelSlots"] for g in body["promptGroups"]] == [["research"]] * 2 + [["analysis"]] * 3 + [["research"]]
    assert [group["key"] for group in body["fixed"]] == ["tools", "processing"]


def test_each_entry_is_the_engine_text_the_board_memo_and_the_call_prompt_id() -> None:
    body = default_body()
    entries = {p["key"]: (group["key"], p) for group in body["promptGroups"] for p in group["prompts"]}
    assert list(entries) == BOARD_KEYS
    for key, (_, entry) in entries.items():
        engine = getattr(DEFAULT_TEXTS, pm.FIELDS[key])
        assert entry["text"] == entry["defaultText"] == engine, key
        assert (entry["memo"], entry["label"], entry["isDefault"]) == (pm.DEFAULT_MEMOS[key], pm.LABELS[key], True)
        parse_prompt_id(entry["promptId"])  # core 프롬프트 id 문법
        assert entry["promptVersion"] == "colab_155"
        assert len(engine) <= body["limits"]["textMax"], key
    assert {
        key: entries[key][1]["promptId"] for key in ("regulation_prefix", "whitelist_financial", "pathway_input")
    } == {
        "regulation_prefix": "materiality/regulation@1",
        "whitelist_financial": "materiality/regulation@1",
        "pathway_input": "materiality/pathway@1",
    }
    memos = [key for key in BOARD_KEYS if pm.DEFAULT_MEMOS[key]]
    assert memos == ["regulation_system", "keywords_system", "impact_system", "financial_system", "pathway_system"]
    assert "{신뢰 출처 목록}" in entries["regulation_system"][1]["text"]


def test_six_texts_carry_an_output_section() -> None:
    body = default_body()
    sections = {p["key"]: p["outputSection"] for g in body["promptGroups"] for p in g["prompts"]}
    assert {key for key, section in sections.items() if section is not None} == {
        "regulation_system",
        "keywords_prefix",
        "controversy_system",
        "impact_system",
        "financial_system",
        "pathway_system",
    }
    con = DEFAULT_TEXTS.controversy_system
    assert sections["controversy_system"] == con[con.index("[OUTPUT] 출력 형식 강제") : con.index("[작성 규칙]")]
    assert (sections["regulation_system"] or "").startswith("[10] 출력 형식 강제 — JSON ONLY\n")
    assert DEFAULT_TEXTS.impact_system.endswith(sections["impact_system"] or "-")


def test_a_saved_text_keeps_or_breaks_its_output_section_and_is_not_folded() -> None:
    kept = DEFAULT_TEXTS.impact_system.replace("You are", "You (지어낸 고침) are", 1)
    broken = DEFAULT_TEXTS.pathway_system.replace("[FINAL OUTPUT — JSON ONLY]", "[결과 꼴]")
    saved = accepted_prompts(prompts_body(impact_system=kept, pathway_system=broken, keywords_system="⟦지어낸 지시⟧"))
    body = pm.prompt_model(CONFIG, setting_name="v1", model=defaults(CONFIG, pm.MODELS), prompts=saved)
    PROMPT_MODEL_V3.validate_python(body, strict=True)
    entries = {p["key"]: p for g in body["promptGroups"] for p in g["prompts"]}
    assert kept != DEFAULT_TEXTS.impact_system
    assert (entries["impact_system"]["outputKept"], entries["pathway_system"]["outputKept"]) == (True, False)
    assert entries["keywords_system"]["outputKept"] is True  # 절 없는 칸
    assert [key for key, e in entries.items() if not e["isDefault"]] == [
        "keywords_system",
        "impact_system",
        "pathway_system",
    ]
    assert pm.texts_from(accepted_prompts(prompts_body())) == DEFAULT_TEXTS  # 기본 글과 같은 저장 글 — 접지 않음


# ── 받기 ──


def test_a_null_research_temperature_is_refused() -> None:
    found = pm.accept_model(CONFIG, model_body(temperature=None))
    assert found == ModelSettingRefused(
        "ai_model_temperature_range", "temperature 는 0~2 사이 수로 넣어 주세요", "research"
    )


@pytest.mark.parametrize("value", [0.3, 0.0])
def test_an_analysis_temperature_is_refused_with_the_core_code(value: float) -> None:
    found = pm.accept_model(CONFIG, model_body(analysis_temperature=value))
    assert isinstance(found, ModelSettingRefused)
    assert (found.code, found.step) == ("ai_model_temperature_unsupported", "analysis")


@pytest.mark.parametrize(
    ("body", "code", "step"),
    [
        (model_body(temperature=2.5), "ai_model_temperature_range", "research"),
        (model_body(route="standard-openai-41"), "ai_model_route_unknown", "research"),
        (model_body(analysis_route="standard-openai-4o"), "ai_model_route_unknown", "analysis"),
        (model_body(web_search=False), "ai_model_web_search_fixed", "research"),
        (model_body(analysis_web_search=True), "ai_model_web_search_fixed", "analysis"),
        (model_body(cap=40000), "ai_model_max_output_range", "research"),
        (model_body(analysis_cap=40000), "ai_model_max_output_range", "analysis"),
    ],
)
def test_the_core_model_rules_still_refuse(body: AiModelSettingsIn, code: str, step: str) -> None:
    found = pm.accept_model(CONFIG, body)
    assert isinstance(found, ModelSettingRefused)
    assert (found.code, found.step) == (code, step)


def test_an_edited_model_is_accepted() -> None:
    found = pm.accept_model(CONFIG, model_body(temperature=0, cap=8000, analysis_cap=9000))
    assert isinstance(found, AcceptedModelSettings)
    assert pm.models_from(found) == (
        StageModel(route=RESEARCH_ROUTE, temperature=0.0, max_output_tokens=8000),
        StageModel(route=ANALYSIS_ROUTE, temperature=None, max_output_tokens=9000),
    )


REQUIRED_CASES = [(key, slot) for key in BOARD_KEYS for slot in texts.REQUIRED.get(key, ())]


@pytest.mark.parametrize(("key", "slot"), REQUIRED_CASES)
def test_a_guarded_text_must_keep_every_slot(key: str, slot: str) -> None:
    text = pm.default_text(key).replace(slot, "(지운 자리)")
    found = pm.accept_prompts(prompts_body(**{key: text}))
    i, j = position(key)
    assert found == PromptRefused(
        "ai_prompt_placeholder_missing",
        f"{pm.LABELS[key]}에서 {slot} 자리를 지우면 안 돼요",
        f"prompts.steps.{i}.prompts.{j}.text",
    )


def test_the_slot_cases_cover_every_guarded_slot() -> None:
    assert len(REQUIRED_CASES) == 1 + 8 + 8 + 1  # 판 칸 열넷의 자리(셋의 기본 글 자리는 엔진 test_texts.py — IRA3)


@pytest.mark.parametrize(
    "key", ["regulation_prefix", "keywords_system", "controversy_prefix", "impact_system", "whitelist_financial"]
)
def test_an_unguarded_text_may_be_replaced_whole(key: str) -> None:
    assert isinstance(pm.accept_prompts(prompts_body(**{key: f"⟦지어낸 {key}⟧"})), AcceptedPrompts)


def test_moved_slots_are_kept() -> None:
    moved = "⟦지어낸 입력 글⟧ " + "".join(reversed(texts.PLACEHOLDERS["impact_input"]))
    assert len(texts.PLACEHOLDERS["impact_input"]) == 8
    assert isinstance(pm.accept_prompts(prompts_body(impact_input=moved)), AcceptedPrompts)


def test_two_same_whitelists_are_refused_by_core() -> None:
    same = DEFAULT_TEXTS.whitelist_financial
    found = pm.accept_prompts(prompts_body(whitelist_non_financial=same))
    assert isinstance(found, PromptRefused)
    assert found.code == "ai_prompt_text_duplicate"


def test_the_core_prompt_rules_run_first() -> None:
    found = pm.accept_prompts(prompts_body(regulation_prefix="  "))
    assert isinstance(found, PromptRefused)
    assert (found.code, found.field) == ("ai_prompt_text_empty", "prompts.steps.0.prompts.1.text")


# ── 잇기 ──


def test_texts_from_maps_each_key_to_its_engine_field() -> None:
    marks = {key: f"⟦IR4-{key}⟧" + pm.default_text(key) for key in BOARD_KEYS}
    made = pm.texts_from(accepted_prompts(prompts_body(**marks)))
    assert {key: getattr(made, pm.FIELDS[key]) for key in BOARD_KEYS} == marks
    assert pm.texts_from(None) is DEFAULT_TEXTS


# ── 고정 값 ──


def test_the_fixed_values_once_in_letters() -> None:
    tools, processing = pm.fixed_groups()
    assert (tools["key"], tools["label"], processing["key"], processing["label"]) == (
        "tools",
        "웹 검색",
        "processing",
        "실행 규칙",
    )
    assert [(item["key"], item["value"]) for item in tools["items"]] == [
        ("research", "리서치 두 단계는 늘 웹 검색 · 검색 범위 low · 위치는 새 평가의 기준 국가"),
        ("analysis", "영향·재무 단계는 새 평가에서 최신 이슈 반영을 켰을 때만 · 검색 범위 low"),
    ]
    assert [(item["key"], item["value"]) for item in processing["items"]] == [
        ("calls", "규제·이슈는 토픽마다 · 키워드는 실행마다 한 번 · 영향·재무·경로는 서브토픽마다"),
        ("max_steps", 1),
        ("retry", 1),
        ("max_cost_usd", "5.0"),
        ("whitelist", "입력의 업종 구분(금융·비금융)"),
        ("analysis_temperature", "싣지 않음(코랩 2부)"),
    ]
    assert default_body()["fixed"] == pm.fixed_groups()


def _literals(tree: ast.AST) -> list[object]:
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and id(node) not in docstrings and not isinstance(node.value, bool)
    ]


def test_the_flow_file_writes_no_number_route_or_price() -> None:
    tree = ast.parse(Path(pm.__file__).read_text(encoding="utf-8"))
    found = _literals(tree)
    assert {value for value in found if isinstance(value, int | float)} <= {0, 1}
    assert [v for v in found if isinstance(v, str) and ("openai" in v or "gpt" in v or "claude" in v)] == []
    assert [v for v in found if isinstance(v, str) and any(ch.isdigit() for ch in v) and "$" in v] == []


def test_no_import_inside_a_body_and_none_of_binding_155() -> None:
    """import 는 모듈 맨 위에만이고 binding_155 를 가리키는 것 0 — binding_155 가 이 파일을 import 하니 고리가 없다
    (MARC-ISSUE-412 ①, 밴드 IRS1)."""
    tree = ast.parse(Path(pm.__file__).read_text(encoding="utf-8"))
    top = {id(node) for node in tree.body}
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]
    assert imports
    assert [node.lineno for node in imports if id(node) not in top] == []
    names = [alias.name for node in imports if isinstance(node, ast.Import) for alias in node.names] + [
        f"{node.module}.{alias.name}" for node in imports if isinstance(node, ast.ImportFrom) for alias in node.names
    ]
    assert [n for n in names if "binding_155" in n] == []


def test_the_cost_cap_letters_come_from_the_flow_constant() -> None:
    _, processing = pm.fixed_groups()
    cap = next(item for item in processing["items"] if item["key"] == "max_cost_usd")
    assert cap["value"] == repr(colab_155.RUN_MAX_COST_USD)


# ── 옛 판(칸 열일곱 — IRA3, MARC-ENT-569) ──


def test_a_stored_legacy_setting_is_read_as_fourteen() -> None:
    """★A: 옛 판 → 칸 열넷(남은 칸 글·메모 바이트 그대로·차례 그대로), 원본은 안 바뀜."""
    given = legacy_body(impact_system="⟦지어낸 영향 지시⟧")
    before = copy.deepcopy(given)
    found = pm.accept_stored(given)
    assert isinstance(found, AcceptedPrompts), found
    assert given == before
    assert [(s.key, [p.key for p in s.prompts]) for s in found.steps] == [(k, list(ks)) for k, ks in pm.LAYOUT]
    stored = {p["key"]: (p["text"], p["memo"]) for s in given["steps"] for p in s["prompts"]}
    assert {p.key: (p.text, p.memo) for s in found.steps for p in s.prompts} == {k: stored[k] for k in BOARD_KEYS}


def test_a_fourteen_setting_is_read_as_accept_prompts() -> None:
    body = prompts_body(impact_system="⟦지어낸 영향 지시⟧")
    assert pm.accept_stored(body) == pm.accept_prompts(body)
    assert pm.legacy_sha256(body) is None


def test_a_legacy_key_in_another_step_or_an_unknown_key_is_still_refused() -> None:
    moved = legacy_body()
    impact = moved["steps"][2]["prompts"]
    impact.append({"key": "regulation_input", "text": "⟦지어낸 옮긴 칸⟧", "memo": ""})
    found = pm.accept_stored(moved)
    assert isinstance(found, PromptRefused)
    assert (found.code, found.field) == ("ai_prompt_keys_fixed", "prompts.steps.2.prompts")
    unknown = legacy_body()
    unknown["steps"][0]["prompts"].append({"key": "⟦지어낸 칸⟧", "text": "⟦지어낸 글⟧", "memo": ""})
    found = pm.accept_stored(unknown)
    assert isinstance(found, PromptRefused)
    assert (found.code, found.field) == ("ai_prompt_keys_fixed", "prompts.steps.0.prompts")


def test_a_legacy_setting_is_refused_on_save() -> None:
    """★B: 저장 받기(accept_prompts)는 열일곱을 받지 않는다."""
    found = pm.accept_prompts(legacy_body())
    assert isinstance(found, PromptRefused)
    assert (found.code, found.field) == ("ai_prompt_keys_fixed", "prompts.steps.0.prompts")


def test_the_legacy_sha_is_the_core_sha_of_the_seventeen_as_given() -> None:
    """★C: 옛 판의 sha = 받은 그대로(열일곱)의 core prompts_sha256 · 메모는 안 듦."""
    given = legacy_body()
    as_given = AcceptedPrompts(
        steps=tuple(
            AcceptedPromptStep(
                key=s["key"],
                prompts=tuple(AcceptedPrompt(key=p["key"], text=p["text"], memo=p["memo"]) for p in s["prompts"]),
            )
            for s in given["steps"]
        )
    )
    assert pm.legacy_sha256(given) == prompts_sha256(as_given)
    memo = copy.deepcopy(given)
    memo["steps"][0]["prompts"][2]["memo"] = "⟦지어낸 메모⟧"
    assert pm.legacy_sha256(memo) == pm.legacy_sha256(given)
    fourteen = pm.accept_stored(given)
    assert isinstance(fourteen, AcceptedPrompts)
    assert pm.legacy_sha256(given) != prompts_sha256(fourteen)


def test_a_legacy_settings_three_texts_are_always_the_engine_defaults() -> None:
    """★D: 옛 판의 셋 글은 실행에 안 쓰인다(texts_from 의 셋 = DEFAULT_TEXTS) · 남은 칸은 저장 글."""
    found = pm.accept_stored(legacy_body(impact_system="⟦지어낸 영향 지시⟧"))
    assert isinstance(found, AcceptedPrompts)
    made = pm.texts_from(found)
    assert {key: getattr(made, key) for key in LEGACY} == {key: getattr(DEFAULT_TEXTS, key) for key in LEGACY}
    assert made.impact_system == "⟦지어낸 영향 지시⟧"
    assert not any(OLD_TEXT in getattr(made, f.name) for f in dataclasses.fields(made))
    body = default_body()
    assert sum(len(g["prompts"]) for g in body["promptGroups"]) == 14
    assert [len(g["prompts"]) for g in body["promptGroups"]] == [2, 4, 2, 2, 2, 2]
    assert sum(p["outputSection"] is not None for g in body["promptGroups"] for p in g["prompts"]) == 6
