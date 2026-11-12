# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행이 만들 때의 AI 설정 판을 versions 에 박고 실행기가 그 판으로 조립한다(밴드 G2c2 §3-2-5~8). 업무 층: 진짜 DB,
저장소는 가짜, 태스크는 함수를 직접 부른다(test_binding_e0_runs.py 의 world 를 그대로 쓰고 실행기의 끼움만 진짜 판
읽기 RunSettingStore 로 바꾼다 — 실행 만들기는 전역 BINDINGS 의 끼움(그것도 RunSettingStore)을 쓴다).

    3-2-5  고정: A 에 v1 적용 → POST /runs → versions.aiSettingId = v1 → 적용 v2 로 → 실행기 → judge 의 EVAL 이 v1 것
    3-2-6  적용 판 없는 회사의 실행 → aiSettingId None, 결과 = 기준표 이전과 바이트 같음
    3-2-7  B 회사의 적용은 A 의 실행에 닿지 않음
    3-2-8  옛 꼴 versions(열쇠 없음) 실행도 실행기가 끝냄
    + 실행에 박힌 판을 다시 지을 수 없으면(sha 다름·없는 판·남의 회사의 판 — G2c3) 실행 실패 — 조용히 기본 판으로
      가지 않음(error_code versions_mismatch — G2c3 Q2 (나), MARC-ENT-352)
    G2c3 §3-2-1  받기 규칙이 좁아져 적용 판을 못 받는 회사의 POST /runs → 409 AI_SETTING_UNUSABLE, 행·감사 0
    G2c3 §3-2-5  만든 뒤 받기 규칙이 좁아져 실행기가 판을 다시 못 지음 → failed·versions_mismatch, 공급사 호출 0
    AS3a-2 §3-4-3  넷 다 고친 저장 글 판 적용 → POST /runs → 실행기 → 공급사가 받은 system 글 = 저장 글(종류마다)
    AS3a-2 §3-4-4  만든 뒤 글 받기가 좁아짐 → versions_mismatch·호출 0 · 적용 뒤 좁아짐 → POST /runs 409·행 0

기준 글은 지어낸 것이다(synthetic). 실제 공급사·키·네트워크 0.
"""

import copy
import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from django.apps import apps
from django.test import Client

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.calc.ai_settings import (
    AcceptedModelSettings,
    AiStepSpec,
    check_model_settings,
    model_settings_sha256,
    prompts_sha256,
)
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn
from esgapi.core.flows.binding import BindingRegistry
from esgapi.core.llm.config import LlmConfig
from esgapi.core.llm.log import sha256_text
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.models import AuditEventRow, DocumentRow
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import criteria_e0, prompt_model_e0
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding, SavedSetting
from esgapi.greenwash.flows.criteria_e0 import build_eval_prompt, default_criteria
from esgapi.greenwash.service.actions import ai_settings as settings_actions
from esgapi.greenwash.service.selectors.ai_settings import RunModelSource, RunSettingStore
from esgapi.greenwash.service.services import ai_settings as settings_services
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.flows import test_criteria_flow as flow_cases
from esgapi.greenwash.tests.flows.test_binding_e0_prompts import KEYS, SAVED, accepted_saved, code_texts
from esgapi.greenwash.tests.flows.test_binding_e0_runs import (
    DEFAULT_MODEL_SHA,
    MINIMAL,
    World,
    create,
    document,
    execute,
    expected,
    new_run,
    result_body,
    run_of,
    sample_pages,
    world,
)
from esgapi.runs import context, tasks
from tests.support.http import login

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (world,)  # test_binding_e0_runs 의 고정물을 이 모듈에서도 이름으로 찾게(pytest 는 모듈의 이름을 본다)


def criteria(text: str, name: str | None = None) -> GreenwashCriteria:
    made = copy.deepcopy(default_criteria())
    made["rows"][9]["text"] = text
    if name is not None:
        made["version"] = name
    return made


V1_TEXT = "지어낸 기준 글 하나: 정량 수치 없이 쓴 환경 성과"
V2_TEXT = "지어낸 기준 글 둘: 기준연도 없이 쓴 감축 목표"


@pytest.fixture
def settings_world(world: World, monkeypatch: pytest.MonkeyPatch) -> World:
    bindings = BindingRegistry()
    bindings.register(
        colab.FLOW_ID,
        GreenwashBinding(
            store=RunSettingStore(), models=RunModelSource(), chat_route="mock", embedding_route="mock-gw1"
        ),
    )
    monkeypatch.setattr(tasks, "BINDINGS", bindings)
    sample_pages(monkeypatch)
    return world


def save_and_apply(company_id: int, text: str, *, apply: bool = True) -> int:
    created = settings_services.create_setting(
        company_id=company_id, created_by_user_id=9, title="지어낸 판", criteria=criteria(text), memo=""
    )
    assert isinstance(created, settings_services.Created)
    if apply:
        settings_services.apply_setting(company_id=company_id, setting_id=created.id, now=datetime.now(UTC))
    return created.id


def eval_systems(env: World) -> list[str]:
    return [system for system, _ in flow_cases.pairs(env.mock.calls)]


def rewrite_versions(company_id: int, run_id: int, versions: dict[str, Any]) -> None:
    rows = apps.get_model("runs", "RunRow")._meta.managers_map["unscoped"]
    rows.filter(company_id=company_id, pk=run_id).update(versions=versions)


def test_a_run_keeps_the_version_applied_when_it_was_made(client: Client, settings_world: World) -> None:
    env = settings_world
    a = env.company_a
    v1 = save_and_apply(a, V1_TEXT)
    v1_criteria = criteria(V1_TEXT, "v1")
    run_id = new_run(client, env, MINIMAL)
    made = run_of(env, run_id).versions
    assert made == {
        "aiSetting": "v1",
        "evalPromptSha256": colab.run_versions(v1_criteria)["evalPromptSha256"],
        "aiSettingId": v1,
        "flow": colab.FLOW_ID,
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
    }
    save_and_apply(a, V2_TEXT)  # 만든 뒤 적용을 v2 로 바꾼다
    env.mock = flow_cases.scripted_provider(40, colab.eval_pack(v1_criteria, PROMPT_VERSION))
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("done", None), run
    systems = eval_systems(env)
    v1_eval = build_eval_prompt(v1_criteria, PROMPT_VERSION)
    v2_eval = build_eval_prompt(criteria(V2_TEXT, "v2"), PROMPT_VERSION)
    assert systems.count(v1_eval) >= 1
    assert v2_eval not in systems and default_prompts(PROMPT_VERSION).eval_system_prompt not in systems
    assert run.versions == made  # 실행의 판 묶음은 그대로


def test_a_company_without_a_setting_runs_byte_for_byte_as_before(client: Client, settings_world: World) -> None:
    env = settings_world
    run_id = new_run(client, env, MINIMAL)
    assert run_of(env, run_id).versions == {
        **colab.run_versions(None),
        "aiSettingId": None,
        "flow": colab.FLOW_ID,
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
    }
    execute(env, run_id)
    assert run_of(env, run_id).status == "done"
    # 저장된 결과는 jsonb 라 열쇠 차례가 바뀐다 — 정렬한 JSON 의 바이트로 견준다
    got = json.dumps(result_body(env, run_id), ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert got == json.dumps(expected(MINIMAL), ensure_ascii=False, sort_keys=True).encode("utf-8")


def test_another_companys_apply_does_not_reach_this_run(client: Client, settings_world: World) -> None:
    env = settings_world
    save_and_apply(env.company_b, V1_TEXT)
    run_id = new_run(client, env, MINIMAL)
    assert run_of(env, run_id).versions["aiSettingId"] is None
    execute(env, run_id)
    assert run_of(env, run_id).status == "done"
    assert result_body(env, run_id) == expected(MINIMAL)


def test_an_old_run_without_the_key_finishes(client: Client, settings_world: World) -> None:
    env = settings_world
    save_and_apply(env.company_a, V1_TEXT)  # 지금 적용이 있어도 옛 실행은 기본 판(만들 때 박은 것이 없다)
    run_id = new_run(client, env, MINIMAL)
    rewrite_versions(env.company_a, run_id, {**colab.run_versions(None), "flow": colab.FLOW_ID})  # G1b 꼴
    execute(env, run_id)
    assert run_of(env, run_id).status == "done"
    assert result_body(env, run_id) == expected(MINIMAL)


@pytest.mark.parametrize("broken", ["sha", "missing", "text-id", "default-sha", "foreign"])
def test_a_run_whose_version_cannot_be_rebuilt_fails(client: Client, settings_world: World, broken: str) -> None:
    env = settings_world
    a = env.company_a
    v1 = save_and_apply(a, V1_TEXT, apply=broken != "default-sha")
    foreign = save_and_apply(env.company_b, V1_TEXT, apply=False)  # B 에 같은 글의 판(v1 — 같은 sha), 적용 안 함
    run_id = new_run(client, env, MINIMAL)
    versions = dict(run_of(env, run_id).versions)
    if broken == "default-sha":  # 기본 판으로 만든 실행(aiSettingId None)의 sha 가 지금 기본 판과 다름
        assert versions["aiSettingId"] is None
        versions["evalPromptSha256"] = "0" * 64
    elif broken == "sha":
        versions["evalPromptSha256"] = "0" * 64
    elif broken == "missing":
        versions["aiSettingId"] = v1 + 1000
    elif broken == "foreign":  # 남의 회사에 실제로 있는 판 id(MARC-ISSUE-231) — 회사 조건만이 막는다
        found = RunSettingStore().get(env.company_b, foreign)
        assert isinstance(found, SavedSetting)  # 분모: 그 id 는 B 에 있다
        assert colab.run_versions(found.criteria)["evalPromptSha256"] == versions["evalPromptSha256"]  # 분모: 같은 sha
        versions["aiSettingId"] = foreign
    else:
        versions["aiSettingId"] = str(v1)
    rewrite_versions(a, run_id, versions)
    env.sink = MemorySink()
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch"), run
    assert env.mock.calls == []  # 공급사에 아무것도 가지 않았다(기본 판으로 조용히 돌지 않음)


# ── G2c3 못 받는 저장 판 ──


def narrow(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    """받기 규칙을 좁힌다: 기준 글 상한을 저장한 글 길이 − 1 로(저장할 때는 받았던 판이 이제 거절된다)."""
    monkeypatch.setattr(criteria_e0, "TEXT_CHARS", len(text) - 1)


def counts(company_id: int) -> tuple[int, int, int]:
    """그 회사의 (실행 행, 단계 행, 감사 run_created) 수."""
    runs = apps.get_model("runs", "RunRow").for_company(company_id).count()  # pyright: ignore[reportAttributeAccessIssue]
    steps = apps.get_model("runs", "RunStepRow").for_company(company_id).count()  # pyright: ignore[reportAttributeAccessIssue]
    lines = AuditEventRow.for_company(company_id).filter(action="run", event="run_created").count()
    return runs, steps, lines


def test_a_run_on_an_applied_version_the_rules_no_longer_take_is_409(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = settings_world
    a, b = env.company_a, env.company_b
    save_and_apply(a, V1_TEXT)
    new_run(client, env, MINIMAL)  # 분모: 좁히기 전엔 201
    before = counts(a)
    assert before[0] == 1 and before[2] == 1
    narrow(monkeypatch, V1_TEXT)
    refused = create(client, {"module": "greenwash", "documentId": document(env), "options": MINIMAL})
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "AI_SETTING_UNUSABLE")
    message = refused.json()["error"]["message"]
    # 글 전문을 박는다 — 판 이름 하나뿐이고 회사 id·기준 글은 없다(조각 검사는 회사 id 가 한 자리면 「(v1)」 에 걸린다)
    assert message == (
        "적용한 AI 설정 판(v1)이 지금 규칙에 맞지 않아요. "
        "운영 관리자가 판을 다시 저장해 적용하거나 기본 판으로 되돌려야 해요"
    )
    assert counts(a) == before  # 실행·단계 행 0, 감사 0
    login(client, tenant_id="tenant-b")  # 분모: 기본 판 회사 B 의 같은 요청은 좁혀도 201
    doc_b = DocumentRow.for_company(b).create(
        company_id=b,
        uploaded_by="1",
        file_name="지어낸-보고서.pdf",
        storage_key=f"companies/{b}/documents/g2c3/original",
        size_bytes=10,
        status="uploaded",
    )
    made = create(client, {"module": "greenwash", "documentId": doc_b.pk, "options": MINIMAL})
    assert made.status_code == 201, made.content.decode()


def test_a_run_whose_version_the_rules_no_longer_take_fails_as_versions_mismatch(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = settings_world
    save_and_apply(env.company_a, V1_TEXT)
    run_id = new_run(client, env, MINIMAL)
    assert run_of(env, run_id).versions["aiSetting"] == "v1"
    narrow(monkeypatch, V1_TEXT)  # 만든 뒤 배포로 받기 규칙이 좁아졌다
    env.sink = MemorySink()
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch"), run
    assert env.mock.calls == []  # 공급사에 아무것도 가지 않았다


# ── AS2b 3-4 판의 모델 설정 적용(실행기 끝까지) ──

AS2B_MODELS = Path(__file__).resolve().parents[1] / "data" / "llm" / "models.as2b.json"
STANDARD: AiModelSettingsIn = {
    "steps": [
        {"key": "judge", "route": "standard-openai-41", "temperature": 0.7, "webSearch": False, "maxOutputTokens": 2000}
    ]
}


def save_model(company_id: int, model_settings: AiModelSettingsIn, *, apply: bool = True) -> int:
    """기본 판과 같은 기준표 + 모델 설정의 판(eval 은 기본 글 — 응답 대본을 그대로 쓴다)."""
    created = settings_services.create_setting(
        company_id=company_id,
        created_by_user_id=9,
        title="지어낸 판",
        criteria=default_criteria(),
        memo="",
        model_settings=model_settings,
    )
    assert isinstance(created, settings_services.Created), created
    if apply:
        settings_services.apply_setting(company_id=company_id, setting_id=created.id, now=datetime.now(UTC))
    return created.id


def run_client_on_real_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    """★D: 실행 클라이언트만 실제 경로 이름 둘을 모의 모델로 잇는 시험 파일로(받기·sha 의 원천은 그대로 — N1)."""
    real = context.llm_settings
    monkeypatch.setattr(context, "llm_settings", lambda: replace(real(), models_file=str(AS2B_MODELS)))


def worker_config(monkeypatch: pytest.MonkeyPatch, config: LlmConfig) -> None:
    def moved(self: RunModelSource) -> LlmConfig:
        return config

    monkeypatch.setattr(RunModelSource, "config", moved)


def worker_steps(monkeypatch: pytest.MonkeyPatch, steps: Sequence[AiStepSpec]) -> None:
    def moved(self: RunModelSource) -> Sequence[AiStepSpec]:
        return steps

    monkeypatch.setattr(RunModelSource, "steps", moved)


def sent(env: World) -> set[tuple[str, float | None, int]]:
    return {(call.api_model_id, call.temperature, call.max_output_tokens) for call in env.mock.calls}


def test_a_run_on_a_model_setting_calls_that_model(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """3-4-4: A 에 standard·0.7·2000 판 적용 → POST /runs → 실행기 → judge 호출이 그 셋. 기본 판으로 되돌린 실행은
    지은 그대로(모의 경로·0.0·1300)."""
    env = settings_world
    run_client_on_real_routes(monkeypatch)
    save_model(env.company_a, STANDARD)
    run_id = new_run(client, env, MINIMAL)
    found = check_model_settings(RunModelSource().config(), STANDARD, steps=RunModelSource().steps())
    assert isinstance(found, AcceptedModelSettings)
    assert run_of(env, run_id).versions["modelSettingsSha256"] == model_settings_sha256(found)
    execute(env, run_id)
    assert run_of(env, run_id).status == "done", run_of(env, run_id)
    assert sent(env) == {("as2b-standard", 0.7, 2000)}

    settings_services.apply_setting(company_id=env.company_a, setting_id=None, now=datetime.now(UTC))
    env.mock, _ = s.scripted_provider(40)
    default_run = new_run(client, env, MINIMAL)
    execute(env, default_run)
    assert run_of(env, default_run).status == "done"
    assert sent(env) == {("mock-synthetic", 0.0, 1300)}  # 분모: 기본 판은 지은 다리 그대로


def test_the_default_route_with_another_temperature_calls_with_that_temperature(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """검증 2 B1: 기본 경로(light-openai-41)·기본 상한에 temperature 만 0.7 인 판도 「기본값과 같음」이 아니다 — 판정
    단계 전체를 견준다(경로만 견주면 지은 다리 0.0 으로 부른다)."""
    env = settings_world
    run_client_on_real_routes(monkeypatch)
    light: AiModelSettingsIn = {
        "steps": [
            {
                "key": "judge",
                "route": "light-openai-41",
                "temperature": 0.7,
                "webSearch": False,
                "maxOutputTokens": 1300,
            }
        ]
    }
    save_model(env.company_a, light)
    run_id = new_run(client, env, MINIMAL)
    execute(env, run_id)
    assert run_of(env, run_id).status == "done", run_of(env, run_id)
    assert sent(env) == {("as2b-light", 0.7, 1300)}


@pytest.mark.parametrize("change", ["pair", "route", "cap"])
def test_a_run_whose_model_moved_after_it_was_made_fails(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """3-4-5·6·8: 만든 뒤 워커 원천의 짝이 바뀌거나·명세에서 경로가 빠지거나·상한이 내려가면 failed·versions_mismatch,
    공급사 호출 0."""
    env = settings_world
    run_client_on_real_routes(monkeypatch)
    save_model(env.company_a, STANDARD)
    run_id = new_run(client, env, MINIMAL)
    config = RunModelSource().config()
    if change == "pair":
        worker_config(monkeypatch, replace(config, routes={**config.routes, "standard-openai-41": ("gpt-4.1-mini",)}))
    elif change == "route":
        worker_steps(
            monkeypatch, tuple(replace(spec, routes=("light-openai-41",)) for spec in RunModelSource().steps())
        )
    else:
        worker_config(monkeypatch, lowered(config))
    env.sink = MemorySink()
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch"), run
    assert env.mock.calls == []


def lowered(config: LlmConfig) -> LlmConfig:
    """gpt-4.1(standard-openai-41)의 출력 상한을 1000 으로(처분 1)."""
    model = config.models["gpt-4.1"]
    entry = model.entry.model_copy(update={"max_output_tokens": 1000})
    return replace(config, models={**config.models, "gpt-4.1": replace(model, entry=entry)})


def test_a_default_run_whose_default_model_moved_fails(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """3-4-7: 기본 판 실행 뒤 워커 명세의 기본 temperature 가 바뀌면 versions_mismatch."""
    env = settings_world
    run_id = new_run(client, env, MINIMAL)
    judge = replace(prompt_model_e0.JUDGE, default={**copy.deepcopy(prompt_model_e0.JUDGE.default), "temperature": 0.5})
    worker_steps(monkeypatch, (judge,))
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch"), run
    assert env.mock.calls == []


def test_a_board_whose_model_is_no_longer_taken_is_409_everywhere(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """3-4-6·8 만들기 쪽: 적용 판의 모델이 지금 받기에 안 맞으면 POST /runs 409(행·감사 0), 적용·prompt-model 409,
    같은 값의 새 판은 400 AI_MODEL_MAX_OUTPUT_RANGE."""
    env = settings_world
    a = env.company_a
    v1 = save_model(a, STANDARD)
    new_run(client, env, MINIMAL)  # 분모: 바뀌기 전엔 201
    v2 = save_model(a, STANDARD, apply=False)
    before = counts(a)
    worker_config(monkeypatch, lowered(RunModelSource().config()))
    refused = create(client, {"module": "greenwash", "documentId": document(env), "options": MINIMAL})
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "AI_SETTING_UNUSABLE")
    assert counts(a) == before
    unusable = settings_services.apply_setting(company_id=a, setting_id=v2, now=datetime.now(UTC))
    assert unusable == settings_services.SettingUnusable("ai_model_max_output_range", "v2")
    shown = settings_actions.prompt_model(actor_kind="admin", company_id=a, setting_id=v1)
    assert shown == settings_services.SettingUnusable("ai_model_max_output_range", "v1")
    again = settings_services.create_setting(
        company_id=a,
        created_by_user_id=9,
        title="지어낸 판",
        criteria=default_criteria(),
        memo="",
        model_settings=STANDARD,
    )
    assert isinstance(again, settings_services.ModelRefused) and again.code == "ai_model_max_output_range"


# ── AS3a-2 3-4 판의 저장 프롬프트 글(실행기 끝까지) ──


def save_prompts(company_id: int) -> int:
    created = settings_services.create_setting(
        company_id=company_id,
        created_by_user_id=9,
        title="지어낸 판",
        criteria=default_criteria(),
        memo="",
        prompts=SAVED,
    )
    assert isinstance(created, settings_services.Created)
    settings_services.apply_setting(company_id=company_id, setting_id=created.id, now=datetime.now(UTC))
    return created.id


def test_a_run_on_saved_texts_calls_the_provider_with_those_texts(client: Client, settings_world: World) -> None:
    """3-4-3: 넷 다 고친 판(출력절 그대로) → 공급사가 받은 system 글 = 저장 글(종류마다 ≥1) · 기본 판으로 되돌린 실행은
    바닥 그대로(열쇠 없음·결과 같음)."""
    env = settings_world
    a = env.company_a
    saved = save_prompts(a)
    run_id = new_run(client, env, MINIMAL)
    pack = colab.pack_from(accepted_saved())
    made = run_of(env, run_id).versions
    assert made == {
        "aiSetting": "v1",
        "evalPromptSha256": sha256_text(pack.eval_system_prompt),
        "aiSettingId": saved,
        "flow": colab.FLOW_ID,
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
        "promptsSha256": prompts_sha256(accepted_saved()),
    }
    env.mock = flow_cases.scripted_provider(40, pack)
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("done", None), run
    kinds = flow_cases.kinds(env.mock.calls, pack)
    assert "unknown" not in kinds and set(kinds) == set(KEYS)
    assert not set(eval_systems(env)) & set(code_texts().values())  # 코드 글 0
    assert run.versions == made

    settings_services.apply_setting(company_id=a, setting_id=None, now=datetime.now(UTC))
    env.mock, _ = s.scripted_provider(40)
    default_run = new_run(client, env, MINIMAL)
    assert "promptsSha256" not in run_of(env, default_run).versions
    execute(env, default_run)
    assert run_of(env, default_run).status == "done"
    assert result_body(env, default_run) == expected(MINIMAL)


def narrow_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    """프롬프트 글 받기를 좁힌다: 글 상한 10자(저장할 때는 받았던 글이 이제 거절된다)."""
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)


def test_a_run_whose_saved_texts_the_rules_no_longer_take_fails(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """3-4-4 워커 쪽: 만든 뒤 글 받기가 좁아지면 failed·versions_mismatch, 공급사 호출 0."""
    env = settings_world
    save_prompts(env.company_a)
    run_id = new_run(client, env, MINIMAL)
    assert "promptsSha256" in run_of(env, run_id).versions
    narrow_prompts(monkeypatch)
    env.sink = MemorySink()
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch"), run
    assert env.mock.calls == []


def test_a_run_on_saved_texts_the_rules_no_longer_take_is_409(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """3-4-4 만들기 쪽(3-1-7 에서 옮김): 적용 뒤 글 받기가 좁아지면 POST /runs 409 AI_SETTING_UNUSABLE, 행·감사 0."""
    env = settings_world
    a = env.company_a
    save_prompts(a)
    new_run(client, env, MINIMAL)  # 분모: 좁히기 전엔 201
    before = counts(a)
    narrow_prompts(monkeypatch)
    refused = create(client, {"module": "greenwash", "documentId": document(env), "options": MINIMAL})
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "AI_SETTING_UNUSABLE")
    assert "지어낸 머리" not in refused.json()["error"]["message"]  # 글 0
    assert counts(a) == before
