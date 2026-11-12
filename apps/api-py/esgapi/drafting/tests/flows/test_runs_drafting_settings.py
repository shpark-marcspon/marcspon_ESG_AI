# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행이 만들 때 적용한 AI 설정 판으로 공급사를 부른다(밴드 RPA1 ② §3 B9, 업무 층). 진짜 DB·진짜 판 행(service 로
저장·적용), 전역 BINDINGS 의 끼움(apps.py 가 단 것 — 판 읽기 RunSettingStore·모델 원천 RunModelSource) 그대로,
실행기는 함수를 직접 부른다(test_runs_drafting.py 의 world·프로젝트 넣기). 중대성평가 test_runs_materiality_settings.py
의 꼴.

    B9-1  표지 글(map_user·draft_system)·draft 칸 standard 경로·temperature 0.7·위끝 3,000 판 적용 → POST /runs →
          실행기 → 모의 공급사가 받은 S2 하나·S3 둘에 표지·판 모델 값, draft system 끝에 MARKER_RULES · 코드 글 판은
          기본 글에 판 모델 · 기본 판은 코드 값(versions 「기본 설정」)
    B9-2  진행 중 실행 고정: v1 적용 → POST /runs → v2 적용 → 실행기 → v1 의 글·모델 · 새 실행은 v2
    B9-3  판 행의 글·모델 한 글자 → versions_mismatch·호출 0 · 받기가 좁아짐 → POST /runs 409 AI_SETTING_UNUSABLE·행 0
    B9-4  실행기의 판 읽기는 실행의 회사만 · 운영 관리자 실행 기록의 「AI 설정」 칸 = 판 이름(기본 판 「기본 설정」)·
          검토 칸 null(EXTRAS 의 drafting)
공급사는 모의뿐(실제 공급사·키·네트워크 0). 글·입력은 지어낸 것이다.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from django.apps import apps
from django.test import Client

from esgapi.core.calc import ai_settings as core_ai_settings
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.core.llm.types import ProviderRequest
from esgapi.drafting.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.drafting.engines.v2.texts import MARKER_RULES, WRITING_RULES
from esgapi.drafting.flows import draft_v2
from esgapi.drafting.flows.binding_v2 import DefaultSetting, SavedSetting, SettingNotFound
from esgapi.drafting.models import DraftingAiSettingRow
from esgapi.drafting.service.selectors.ai_settings import RunSettingStore
from esgapi.drafting.service.services import ai_settings as settings_services
from esgapi.drafting.tests.flows.test_prompt_model_v2 import STANDARD, model_body, prompts_body
from esgapi.drafting.tests.flows.test_runs_drafting import (
    World,
    create,
    execute,
    new_run,
    project,
    run_count,
    run_of,
    script,
    world,
)
from esgapi.runs.service.selectors import operator as operator_selectors

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (world,)  # test_runs_drafting 의 고정물을 이 모듈에서도 이름으로 찾게(pytest 는 모듈의 이름을 본다)

EDITED: AiModelSettingsIn = model_body(route=STANDARD, temperature=0.7, cap=3000)
"""draft 칸만 기본과 다른 판(경로·temperature·위끝 — map 칸은 기본)."""
CODE = [(draft_v2.TEMPERATURE, draft_v2.MAX_OUTPUT_TOKENS)] * 3
EDITED_PAIRS = [(draft_v2.TEMPERATURE, draft_v2.MAX_OUTPUT_TOKENS), (0.7, 3000), (0.7, 3000)]
"""(temperature, 위끝) — S2 한 묶음 + S3 둘(script 의 차례)."""


def marked(tag: str) -> AiPromptsIn:
    return prompts_body(
        map_user=f"⟦RPA1-{tag}-map_user⟧ 지어낸 붙이기 입력 글\n{{목차}}\n{{페이지 글}}",
        draft_system=f"⟦RPA1-{tag}-draft_system⟧ 지어낸 초안 지시 글",
    )


def save(
    company_id: int, *, prompts: AiPromptsIn | None, model: AiModelSettingsIn | None = None, apply: bool = True
) -> int:
    created = settings_services.create_setting(
        company_id=company_id, created_by_user_id=9, title="시험 판 가", memo="", model_settings=model, prompts=prompts
    )
    assert isinstance(created, settings_services.Created), created
    if apply:
        applied = settings_services.apply_setting(company_id=company_id, setting_id=created.id, now=datetime.now(UTC))
        assert isinstance(applied, settings_services.Applied), applied
    return created.id


def calls_of(env: World, run_id: int) -> list[ProviderRequest]:
    before = len(env.mock.calls)
    script(env)
    execute(env, run_id)
    run = run_of(env, run_id)
    assert run.status == "done", (run.failed_step, run.error_code, run.error_message)
    assert env.mock.pending == 0
    return list(env.mock.calls[before:])


def joined(part: Any) -> str:
    """system·user 칸(글 또는 블록 목록 [{text, cache}])의 글."""
    return part if isinstance(part, str) else "".join(block["text"] for block in part)


def system_user(request: ProviderRequest) -> tuple[str, str]:
    body: dict[str, Any] = request.to_json()
    return joined(body["system"]), joined(body["user"])


def seen(calls: list[ProviderRequest]) -> str:
    return " ".join(" ".join(system_user(c)) for c in calls)


def pairs(calls: list[ProviderRequest]) -> list[tuple[float | None, int]]:
    return [(c.temperature, c.max_output_tokens) for c in calls]


def rewrite(company_id: int, setting_id: int, **fields: Any) -> None:
    """판 행을 고친다(판 불변을 어긴 행 — 시험만. 앱 역할은 UPDATE 를 applied·applied_at 둘만 받는다)."""
    rows = apps.get_model("drafting", "DraftingAiSettingRow")._meta.managers_map["unscoped"]
    rows.filter(company_id=company_id, pk=setting_id).update(**fields)


# ── B9-1 업무 양성 ──


def test_b9_the_applied_setting_reaches_the_provider(client: Client, world: World) -> None:
    a = world.company_a
    project_id, _ = project(world)
    setting_id = save(a, prompts=marked("a"), model=EDITED)
    run_id = new_run(client, project_id)
    versions = run_of(world, run_id).versions
    assert (versions["aiSetting"], versions["aiSettingId"]) == ("v1", setting_id)
    assert "promptsSha256" in versions and "modelSettingsSha256" in versions
    calls = calls_of(world, run_id)
    assert len(calls) == 3
    assert "⟦RPA1-a-map_user⟧" in system_user(calls[0])[1]  # S2 의 user 에만
    assert all("⟦RPA1-a-map_user⟧" not in seen([c]) for c in calls[1:])
    for draft in calls[1:]:  # S3 의 system = 저장 글 + 칸 밖 고정 꼬리
        system = system_user(draft)[0]
        assert system.startswith("⟦RPA1-a-draft_system⟧") and system.endswith(WRITING_RULES) and MARKER_RULES in system
    assert "⟦RPA1-a-draft_system⟧" not in seen(calls[:1])
    assert pairs(calls) == EDITED_PAIRS
    assert calls[0].api_model_id != calls[1].api_model_id == calls[2].api_model_id  # map mini · draft 4.1


def test_b9_a_code_text_setting_sends_the_default_texts_with_its_model(client: Client, world: World) -> None:
    a = world.company_a
    project_id, _ = project(world)
    save(a, prompts=None, model=EDITED)
    run_id = new_run(client, project_id)
    assert "promptsSha256" not in run_of(world, run_id).versions
    calls = calls_of(world, run_id)
    assert "⟦RPA1-" not in seen(calls)
    default_draft = draft_v2.DEFAULT_TEXTS.draft_system.strip().splitlines()[0]
    assert all(system_user(c)[0].startswith(default_draft) for c in calls[1:])  # 기본 글
    assert pairs(calls) == EDITED_PAIRS


def test_b9_the_default_setting_sends_the_code_values(client: Client, world: World) -> None:
    project_id, _ = project(world)
    run_id = new_run(client, project_id)
    versions = run_of(world, run_id).versions
    assert (versions["aiSetting"], versions["aiSettingId"]) == (DEFAULT_TITLE, None)
    calls = calls_of(world, run_id)
    assert pairs(calls) == CODE
    assert len({c.api_model_id for c in calls}) == 1


# ── B9-2 진행 중 실행 고정 ──


def test_b9_a_run_made_with_v1_ends_with_v1_after_v2_is_applied(client: Client, world: World) -> None:
    a = world.company_a
    project_id, _ = project(world)
    v1 = save(a, prompts=marked("v1"), model=EDITED)
    run_id = new_run(client, project_id)
    v2 = save(a, prompts=marked("v2"), model=model_body(temperature=1.5, cap=2000))
    assert v2 != v1
    assert DraftingAiSettingRow.for_company(a).get(applied=True).id == v2  # 적용은 v2 로 바뀌었다
    calls = calls_of(world, run_id)
    assert "⟦RPA1-v1-draft_system⟧" in seen(calls) and "⟦RPA1-v2-" not in seen(calls)
    assert pairs(calls) == EDITED_PAIRS
    assert run_of(world, run_id).versions["aiSettingId"] == v1
    later = new_run(client, project_id)  # 분모: 새 실행은 v2
    later_calls = calls_of(world, later)
    assert "⟦RPA1-v2-draft_system⟧" in seen(later_calls)
    assert pairs(later_calls)[1:] == [(1.5, 2000)] * 2


# ── B9-3 어긋남·좁아짐 ──


@pytest.mark.parametrize("field", ["prompts", "model_settings"])
def test_b9_a_setting_row_changed_after_the_run_was_made_fails_the_run(
    client: Client, world: World, field: str
) -> None:
    a = world.company_a
    project_id, _ = project(world)
    setting_id = save(a, prompts=marked("a"), model=EDITED)
    run_id = new_run(client, project_id)
    if field == "prompts":
        rewrite(a, setting_id, prompts=marked("a!"))
    else:
        rewrite(a, setting_id, model_settings=model_body(route=STANDARD, temperature=0.7, cap=3001))
    execute(world, run_id)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch")
    assert world.mock.calls == []


def test_b9_a_setting_the_narrowed_rules_refuse_cannot_make_a_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = world.company_a
    project_id, _ = project(world)
    save(a, prompts=marked("a"))
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)
    response = create(client, {"module": "drafting", "options": {"projectId": project_id}})
    assert response.status_code == 409, response.content.decode()
    assert response.json()["error"]["code"] == "AI_SETTING_UNUSABLE"
    assert run_count(world) == 0  # 행 0
    DraftingAiSettingRow.for_company(a).update(applied=False, applied_at=datetime.now(UTC))  # 분모: 기본 판이면 201
    assert create(client, {"module": "drafting", "options": {"projectId": project_id}}).status_code == 201


# ── B9-4 회사 조건·실행 기록 ──


def test_b9_the_run_store_reads_only_the_runs_company(world: World) -> None:
    """실행기의 판 읽기(RunSettingStore)는 회사 조건을 늘 적는다 — 남의 회사의 판 id 는 없음, 적용 판도 제 회사만."""
    a, b = world.company_a, world.company_b
    b_id = save(b, prompts=marked("b"))
    store = RunSettingStore()
    assert isinstance(store.get(b, b_id), SavedSetting)  # 분모: 제 회사면 판
    assert store.get(a, b_id) == SettingNotFound(b_id)
    assert isinstance(store.applied(a), DefaultSetting)
    assert store.applied(b) == store.get(b, b_id)


def test_b9_the_operator_run_log_names_the_setting(client: Client, world: World) -> None:
    a = world.company_a
    project_id, _ = project(world)
    default_run = new_run(client, project_id)
    setting_id = save(a, prompts=None)
    saved_run = new_run(client, project_id)
    for run_id, setting in ((default_run, (None, DEFAULT_TITLE)), (saved_run, (setting_id, "v1"))):
        detail = operator_selectors.operator_run_detail(actor_kind="admin", company_id=a, run_id=run_id)
        assert isinstance(detail, operator_selectors.OperatorRunDetail)
        assert (detail.run.ai_setting, detail.run.review) == (setting, None)
    pending = operator_selectors.operator_run_page(
        actor_kind="admin",
        company_id=a,
        module="drafting",
        status=None,
        date_from=None,
        date_to=None,
        q=None,
        limit=10,
        offset=0,
        review="pending",
    )
    assert isinstance(pending, operator_selectors.OperatorRunPage) and pending.count == 0  # 검토 화면 없음
