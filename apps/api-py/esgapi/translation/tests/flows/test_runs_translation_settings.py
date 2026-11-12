# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행이 만들 때 적용한 AI 설정 판으로 공급사를 부른다(밴드 TR4 §3-4-3~7, 업무 층). 진짜 DB·진짜 판 행(service 로
저장·적용), 전역 BINDINGS 의 끼움(apps.py 가 단 것 — 판 읽기 RunSettingStore·모델 원천 RunModelSource) 그대로,
실행기는 함수를 직접 부른다(test_runs_translation.py 의 world).

    3-4-3  표지 글·다른 모델 칸 판 적용 → POST /runs(스토리·문체 B·표 쪽) → 실행기 → 모의 공급사가 받은 system 에
           표지(user 0) · 그 밖 파트 칸의 경로·위끝(min) · temperature 0
    3-4-4  회사 섞임 0: A·B 판·C 기본이 같은 워커에서 각자 제 값 · 운영 관리자의 작업 회사 B 로 POST /runs → B 의 판
    3-4-5  dry-run(prepare 어림): 스토리 톤 +4,000자·그 밖 파트 칸 standard → 기본보다 크고 models.json 으로
           센 값과 같다
    3-4-6  판 행의 글·모델 한 글자 → versions_mismatch·호출 0 · 받기가 좁아짐 → POST /runs 409 AI_SETTING_UNUSABLE·행 0
    3-4-7  운영 관리자 실행 기록의 「AI 설정」 칸 = 판 이름(기본 판 「기본 설정」)·검토 칸 null
    TRS1   다시 하기(retry)는 앞 실행과 판 열쇠가 같아야 한다: 앞 판 v1 → 이번 판 v2 · 판 열쇠 없는 옛 앞 실행 →
           retry_source_mismatch·호출 0 · 같은 판이면 진행(MARC-ISSUE-326)
공급사는 모의뿐(실제 공급사·키·네트워크 0). 글·문서는 지어낸 것이다.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from django.apps import apps
from django.test import Client
from django.urls import get_resolver

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.conf import app_config, now
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.types import Completed, ProviderRequest, Usage
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.translation.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.translation.engines.colab_158.plan import plan
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows import prompt_model_158 as pm
from esgapi.translation.models import TranslationAiSettingRow
from esgapi.translation.service.services import ai_settings as settings_services
from esgapi.translation.tests.engines.colab_158.support import LIGHT, LIGHT_MODEL, STANDARD, STANDARD_MODEL, client
from esgapi.translation.tests.engines.colab_158.texts_digest import DOCUMENT
from esgapi.translation.tests.flows.support import SIMPLE_EN, options
from esgapi.translation.tests.flows.test_prompt_model_158 import model_body, prompts_body
from esgapi.translation.tests.flows.test_runs_translation import (
    World,
    document,
    execute,
    result_body,
    run_of,
    scripted,
    world,
)
from esgapi.translation.tools.llm_bridge import LlmBridge
from esgapi.translation.tools.run_bound import run_bound
from tests.support.http import bearer, login

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (
    world,
)  # test_runs_translation 의 고정물을 이 모듈에서도 이름으로 찾게(pytest 는 모듈의 이름을 본다)

USAGE = Usage(input_tokens=10, output_tokens=5, cache_read_tokens=0, cache_write_tokens=0)
MODEL_IDS = {LIGHT: LIGHT_MODEL, STANDARD: STANDARD_MODEL}
OPERATOR_ID = 9001
OTHER = model_body(("translate_ceo", LIGHT, 3000), ("translate_other", STANDARD, 2000), ("review", STANDARD, 1500))
"""기본과 다른 칸 셋(경로가 기본과 뒤바뀜·위끝이 자리 값 사이)."""


def marked(tag: str) -> AiPromptsIn:
    return prompts_body(
        tone_story=f"⟦TR4-{tag}-tone_story⟧ 지어낸 스토리 톤",
        style_b=f"⟦TR4-{tag}-style_b⟧ 지어낸 문체 B",
        table_rules=f"⟦TR4-{tag}-table_rules⟧ 지어낸 표 규칙",
    )


def save(
    company_id: int, *, prompts: AiPromptsIn | None, model: AiModelSettingsIn | None = None, apply: bool = True
) -> int:
    created = settings_services.create_setting(
        company_id=company_id, created_by_user_id=9, title="지어낸 판", memo="", model_settings=model, prompts=prompts
    )
    assert isinstance(created, settings_services.Created), created
    if apply:
        applied = settings_services.apply_setting(company_id=company_id, setting_id=created.id, now=datetime.now(UTC))
        assert isinstance(applied, settings_services.Applied), applied
    return created.id


def system_of(request: ProviderRequest) -> str:
    return "".join(segment.text for segment in request.system)


def answer(request: ProviderRequest) -> Completed:
    """검수면 이슈 없음, 범용 QA 면 통과 점수, 그 밖은 지어낸 영문(표 묶음은 JSON 이 아니라 칸마다 다시 — 칸 자리)."""
    system = system_of(request)
    if "ESG report proofreader" in system:
        return Completed(text="[]", usage=USAGE)
    if "Return JSON only:" in system:
        body = {"quality_score": 99, "has_critical_issue": False, "issues": [], "revised_text": ""}
        return Completed(text=json.dumps(body), usage=USAGE)
    return Completed(text=SIMPLE_EN, usage=USAGE)


def answering(env: World, n: int = 80) -> None:
    for _ in range(n):
        env.mock.enqueue(answer)


STORY = options(part="story", style={"compareAb": False, "single": "B"})


def run_in(client: Client, env: World, company: int, given: dict[str, Any] = STORY, **headers: Any) -> Any:
    body = {"module": "translation", "documentId": document(env, company, DOCUMENT.encode()), "options": given}
    return client.post("/api/runs", data=body, content_type="application/json", **headers)


def made(client: Client, env: World, company: int, given: dict[str, Any] = STORY) -> int:
    login(client, tenant_id="tenant-a" if company == env.company_a else "tenant-b")
    response = run_in(client, env, company, given)
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    return run_id


def calls_of(env: World, run_id: int, company: int) -> list[ProviderRequest]:
    before = len(env.mock.calls)
    answering(env)
    execute(env, run_id, company)
    assert run_of(env, run_id, company).status == "done", run_of(env, run_id, company)
    return list(env.mock.calls[before:])


def rewrite(company_id: int, setting_id: int, **fields: Any) -> None:
    """판 행을 고친다(판 불변을 어긴 행 — 시험만. 앱 역할은 UPDATE 를 applied·applied_at 둘만 받는다)."""
    rows = apps.get_model("translation", "TranslationAiSettingRow")._meta.managers_map["unscoped"]
    rows.filter(company_id=company_id, pk=setting_id).update(**fields)


# ── 3-4-3 업무 양성 ──


def test_the_applied_setting_reaches_the_provider(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    setting_id = save(a, prompts=marked("a"), model=OTHER)
    run_id = made(client, world, a)
    versions = run_of(world, run_id).versions
    assert (versions["aiSetting"], versions["aiSettingId"]) == ("v1", setting_id)
    assert "promptsSha256" in versions
    calls = calls_of(world, run_id, a)
    systems = [system_of(c) for c in calls]
    assert any("⟦TR4-a-tone_story⟧" in s and "⟦TR4-a-style_b⟧" in s for s in systems)
    assert any("⟦TR4-a-table_rules⟧" in s for s in systems)  # 표 쪽 — 표 묶음 자리
    assert all("⟦TR4-" not in repr(c.user) for c in calls)  # user 0
    review = [c for c, s in zip(calls, systems, strict=True) if "ESG report proofreader" in s]
    translate = [c for c, s in zip(calls, systems, strict=True) if "ESG report proofreader" not in s]
    assert review and translate
    assert {c.api_model_id for c in translate} == {MODEL_IDS[STANDARD]}  # 그 밖 파트 칸
    assert all(c.max_output_tokens <= 2000 for c in translate)
    assert {(c.api_model_id, c.max_output_tokens) for c in review} == {(MODEL_IDS[STANDARD], 1500)}
    assert all(c.temperature is None for c in calls)


def test_a_code_text_setting_sends_the_default_texts_with_its_models(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    save(a, prompts=None, model=OTHER)
    run_id = made(client, world, a)
    assert "promptsSha256" not in run_of(world, run_id).versions
    calls = calls_of(world, run_id, a)
    assert all("⟦TR4-" not in system_of(c) for c in calls)
    assert any(pm.default_text("tone_story") in system_of(c) for c in calls)
    assert {c.api_model_id for c in calls} == {MODEL_IDS[STANDARD]}


# ── 3-4-4 회사 섞임 0 ──


def test_each_company_runs_with_its_own_setting_on_one_worker(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]
) -> None:
    scripted(monkeypatch, world)
    a, b = world.company_a, world.company_b
    save(a, prompts=marked("a"))
    save(b, prompts=marked("b"))
    run_a = made(client, world, a)
    run_b = made(client, world, b)
    seen_a = " ".join(system_of(c) for c in calls_of(world, run_a, a))
    seen_b = " ".join(system_of(c) for c in calls_of(world, run_b, b))
    assert "⟦TR4-a-tone_story⟧" in seen_a and "⟦TR4-b-" not in seen_a
    assert "⟦TR4-b-tone_story⟧" in seen_b and "⟦TR4-a-" not in seen_b
    TranslationAiSettingRow.for_company(b).update(applied=False, applied_at=datetime.now(UTC))  # B 를 기본 판으로
    run_c = made(client, world, b)
    assert run_of(world, run_c, b).versions["aiSettingId"] is None
    seen_c = " ".join(system_of(c) for c in calls_of(world, run_c, b))
    assert "⟦TR4-" not in seen_c and pm.default_text("tone_story") in seen_c


def operator() -> dict[str, Any]:
    claims = new_access_claims(
        user_id=str(OPERATOR_ID),
        kind="admin",
        level=99,
        company_id=None,
        company_is_active=None,
        is_initial=False,
        jti=uuid4(),
        now=now(),
    )
    return bearer(sign_access(claims, secret=app_config().session_secret))


def test_an_operator_working_on_company_b_runs_with_bs_setting(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a, b = world.company_a, world.company_b
    save(a, prompts=marked("a"))
    b_id = save(b, prompts=marked("b"))
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: b)
    response = run_in(client, world, b, STORY, **operator())
    assert response.status_code == 201, response.content.decode()
    run_id = response.json()["id"]
    assert run_of(world, run_id, b).versions["aiSettingId"] == b_id
    seen = " ".join(system_of(c) for c in calls_of(world, run_id, b))
    assert "⟦TR4-b-tone_story⟧" in seen and "⟦TR4-a-" not in seen


# ── 3-4-5 dry-run ──


def estimate_of(env: World, run_id: int, company: int) -> float:
    prepared = run_selectors.step_output(company_id=company, run_id=run_id, step="prepare")
    assert isinstance(prepared, run_selectors.StepFound), prepared
    total = prepared.data["totalEstimateUsd"]
    assert isinstance(total, float)
    return total


def test_the_estimate_counts_the_saved_texts_and_slot_models(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    default_run = made(client, world, a)
    calls_of(world, default_run, a)
    longer = prompts_body(tone_story=pm.default_text("tone_story") + "가" * 4_000)
    other = model_body(("translate_ceo", STANDARD, 8192), ("translate_other", STANDARD, 8192), ("review", LIGHT, 4096))
    save(a, prompts=longer, model=other)
    saved_run = made(client, world, a)
    calls_of(world, saved_run, a)
    estimated = estimate_of(world, saved_run, a)
    assert estimated > estimate_of(world, default_run, a)
    # models.json 으로 센 값: 같은 판 값의 입력으로 다리 dry_run 을 손으로 부른다(실행기 밖 — 공급사 호출 0)
    run_inputs = world_inputs(world, saved_run, a)
    assert run_inputs.models.translate_other.route == STANDARD and len(run_inputs.texts.story_tone) > 4_000
    bridge = LlmBridge(client_of(), part="story", tenant=str(a), models=run_inputs.models)
    summary, max_single = bridge.dry_run_with_max(plan(colab.engine_input(run_inputs, DOCUMENT)))
    assert estimated == pytest.approx(run_bound(summary, max_single)["totalUsd"])  # 새 위끝(밴드 TRE1)
    assert ceiling_of(world, saved_run, a) == pytest.approx(summary["totalEstimateUsd"])  # 엄격 합은 ceilingUsd


def ceiling_of(env: World, run_id: int, company: int) -> float:
    prepared = run_selectors.step_output(company_id=company, run_id=run_id, step="prepare")
    assert isinstance(prepared, run_selectors.StepFound), prepared
    ceiling = prepared.data["ceilingUsd"]
    assert isinstance(ceiling, float)
    return ceiling


def world_inputs(env: World, run_id: int, company: int) -> colab.TranslationRunInputs:
    """그 실행을 실행기가 지을 입력(전역 BINDINGS 의 끼움 — 만들 때의 versions 로)."""
    from esgapi.core.flows.binding import BINDINGS, DocumentInput

    run = run_of(env, run_id, company)
    binding: Any = BINDINGS.get(colab.FLOW_ID)
    doc = DocumentInput(content=DOCUMENT.encode(), media_type="text/plain", file_name="synthetic.txt")
    return binding.inputs_with(doc, run.options, company_id=company, versions=run.versions)


def client_of() -> Any:
    from esgapi.core.llm.providers.mock import MockProvider

    return client({"openai": MockProvider("openai"), "anthropic": MockProvider("anthropic")})


# ── 3-4-6 어긋남·좁아짐 ──


@pytest.mark.parametrize("field", ["prompts", "model_settings"])
def test_a_setting_row_changed_after_the_run_was_made_fails_the_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    setting_id = save(a, prompts=marked("a"), model=OTHER)
    run_id = made(client, world, a)
    if field == "prompts":
        rewrite(a, setting_id, prompts=marked("a!"))
    else:
        bumped = [(step["key"], step["route"], step["maxOutputTokens"] + 1) for step in OTHER["steps"]]
        rewrite(a, setting_id, model_settings=model_body(*bumped))
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch")
    assert world.mock.calls == []


def test_a_setting_the_narrowed_rules_refuse_cannot_make_a_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = world.company_a
    save(a, prompts=marked("a"))
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)
    login(client)
    response = run_in(client, world, a)
    assert response.status_code == 409, response.content.decode()
    assert response.json()["error"]["code"] == "AI_SETTING_UNUSABLE"
    runs = apps.get_model("runs", "RunRow")._meta.managers_map["unscoped"]
    assert runs.filter(company_id=a).count() == 0  # 행 0
    login(client, tenant_id="tenant-b")  # 분모: 기본 판 회사 B 의 같은 요청은 좁혀도 201
    assert run_in(client, world, world.company_b).status_code == 201


def test_a_run_made_before_narrowing_fails_with_versions_mismatch(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    save(a, prompts=marked("a"))
    run_id = made(client, world, a)
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch")
    assert world.mock.calls == []


# ── TRS1 다시 하기의 판 열쇠(MARC-ISSUE-326) ──


def retried(client: Client, env: World, from_run_id: int) -> dict[str, Any]:
    """같은 글의 새 문서로 retry 실행을 만들어 돌린 결과."""
    run_id = made(client, env, env.company_a, {**STORY, "retry": {"fromRunId": from_run_id, "pages": [1]}})
    answering(env)
    execute(env, run_id)
    assert run_of(env, run_id).status == "done"
    return result_body(env, run_id)


def test_a_retry_under_another_setting_than_the_source_run_is_a_mismatch(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    save(a, prompts=marked("v1"), model=OTHER)
    first = made(client, world, a)
    calls_of(world, first, a)
    save(a, prompts=marked("v2"), model=OTHER)  # 같은 모델 칸·다른 글 — 판 id·글 sha 가 다르다
    before = len(world.mock.calls)
    body = retried(client, world, first)
    assert body["rejection"]["kind"] == "retry_source_mismatch"
    assert "AI 설정 판" in body["rejection"]["message"]
    assert len(world.mock.calls) == before  # 호출 0


def test_a_retry_under_the_same_setting_as_the_source_run_goes_on(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    save(a, prompts=marked("v1"), model=OTHER)
    first = made(client, world, a)
    calls_of(world, first, a)
    body = retried(client, world, first)
    assert body["status"] == "done"
    assert body["settings"]["retry"]["fromRunId"] == first


def test_a_retry_of_an_old_run_without_the_setting_key_is_a_mismatch(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    first = made(client, world, a)
    calls_of(world, first, a)
    runs = apps.get_model("runs", "RunRow")._meta.managers_map["unscoped"]
    row = runs.get(company_id=a, pk=first)
    old = {k: v for k, v in row.versions.items() if k not in colab.AI_KEY_FIELDS and k != "aiSetting"}
    runs.filter(company_id=a, pk=first).update(versions=old)  # TR4 앞 옛 실행의 versions 꼴
    before = len(world.mock.calls)
    assert retried(client, world, first)["rejection"]["kind"] == "retry_source_mismatch"
    assert len(world.mock.calls) == before


# ── 3-4-7 실행 기록 「AI 설정」 칸 ──


def test_the_operator_run_log_names_the_setting(client: Client, world: World) -> None:
    a = world.company_a
    default_run = made(client, world, a)
    setting_id = save(a, prompts=None)
    saved_run = made(client, world, a)
    for run_id, setting in ((default_run, (None, DEFAULT_TITLE)), (saved_run, (setting_id, "v1"))):
        detail = operator_selectors.operator_run_detail(actor_kind="admin", company_id=a, run_id=run_id)
        assert isinstance(detail, operator_selectors.OperatorRunDetail)
        assert (detail.run.ai_setting, detail.run.review) == (setting, None)
    pending = operator_selectors.operator_run_page(
        actor_kind="admin",
        company_id=a,
        module="translation",
        status=None,
        date_from=None,
        date_to=None,
        q=None,
        limit=10,
        offset=0,
        review="pending",
    )
    assert isinstance(pending, operator_selectors.OperatorRunPage) and pending.count == 0  # 검토 화면 없음
