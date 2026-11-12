# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""실행이 만들 때 적용한 AI 설정 판으로 공급사를 부른다(밴드 IR4 §3-4-2~6, 업무 층). 진짜 DB·진짜 판 행(service 로
저장·적용), 전역 BINDINGS 의 끼움(apps.py 가 단 것 — 판 읽기 RunSettingStore·모델 원천 RunModelSource) 그대로,
실행기는 함수를 직접 부른다(test_runs_materiality.py 의 world). 데이터 검증 test_runs_dataverify_settings.py 의 꼴.

    3-4-2  진행 중 실행 고정: v1 적용 → POST /runs → v2 적용 → 워커 → v1 의 글·모델(시안 「이미 돌고 있는 실행은
           v1 로 끝나요」)
    3-4-3  표지 글·research temperature 0.3·위끝 8,000·analysis 위끝 9,000 판 적용 → POST /runs → 실행기 → 모의
           공급사가 받은 1부 다섯·2부 아홉 요청에 표지·판 모델 값 · 코드 글 판은 기본 글에 판 모델
    3-4-4  회사 섞임 0: A·B 판·C(기본)가 같은 워커에서 각자 제 값 · 운영 관리자의 작업 회사 B 로 POST /runs → B 의 판
    3-4-5  판 행의 글·모델 한 글자 → versions_mismatch·호출 0 · 받기가 좁아짐 → POST /runs 409 AI_SETTING_UNUSABLE·행 0
           · 만든 뒤 좁아짐 → versions_mismatch
    3-4-6  운영 관리자 실행 기록의 「AI 설정」 칸 = 판 이름(기본 판 「기본 설정」)·검토 칸 null
    IRA3   옛 판(칸 열일곱) 행 적용 → POST /runs 201 · 끝까지 · 옛 셋 글 0
    3-4-7  load 뒤 이어 돌기 → 박힌 판의 글(앞 실행의 versions 를 물려받음)
공급사는 모의뿐(실제 공급사·키·네트워크 0). 글·입력은 지어낸 것이다.
"""

import contextlib
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
from esgapi.core.llm.types import ProviderRequest
from esgapi.materiality.contracts.ai_setting_shapes import DEFAULT_TITLE
from esgapi.materiality.flows import colab_155, iro_155, part2_155
from esgapi.materiality.flows import prompt_model_155 as pm
from esgapi.materiality.flows.binding_155 import DefaultSetting, SavedSetting, SettingNotFound
from esgapi.materiality.models import MaterialityAiSettingRow
from esgapi.materiality.service.selectors.ai_settings import RunSettingStore
from esgapi.materiality.service.services import ai_settings as settings_services
from esgapi.materiality.tests.flows.support import options, script_iro
from esgapi.materiality.tests.flows.test_prompt_model_155 import OLD_TEXT, legacy_body, model_body, prompts_body
from esgapi.materiality.tests.flows.test_runs_materiality import RetryAsked, World, scripted, world
from esgapi.runs import tasks
from esgapi.runs.service.selectors import operator as operator_selectors
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import bearer, login

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (
    world,
)  # test_runs_materiality 의 고정물을 이 모듈에서도 이름으로 찾게(pytest 는 모듈의 이름을 본다)

OPERATOR_ID = 9001
EDITED: AiModelSettingsIn = model_body(temperature=0.3, cap=8000, analysis_cap=9000)
"""기본과 다른 칸(research temperature·위끝 · analysis 위끝 — 경로는 칸마다 하나뿐이다)."""
PART1 = 5
"""1부 요청 수(규제 둘·키워드·사건 둘 — 토픽 둘 입력). 그 뒤 아홉이 2부."""
DEFAULT_IMPACT = pm.default_text("impact_system").strip().splitlines()[0][:24]
"""기본 영향 지시 글의 첫 줄 앞 — 코드 글이 실렸는지 보는 표지."""


def marked(tag: str) -> AiPromptsIn:
    return prompts_body(
        impact_system=f"⟦IR4-{tag}-impact_system⟧ 지어낸 영향 지시 글",
        regulation_prefix=pm.default_text("regulation_prefix") + f"⟦IR4-{tag}-regulation_prefix⟧",
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


def tenant_of(env: World, company: int) -> str:
    return "tenant-a" if company == env.company_a else "tenant-b"


def run_in(client: Client, **headers: Any) -> Any:
    body = {"module": "materiality", "options": options()}
    return client.post("/api/runs", data=body, content_type="application/json", **headers)


def made(client: Client, env: World, company: int) -> int:
    login(client, tenant_id=tenant_of(env, company))
    response = run_in(client)
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    return run_id


def run_of(env: World, run_id: int, company: int) -> run_selectors.Run:
    found = run_selectors.find_run(company_id=company, run_id=run_id)
    assert found is not None
    return found


def execute(env: World, run_id: int, company: int) -> None:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(env, company_id=str(company), run_id=str(run_id))


def calls_of(env: World, run_id: int, company: int) -> list[ProviderRequest]:
    before = len(env.mock.calls)
    script_iro(env.mock, options()["input"])
    execute(env, run_id, company)
    assert run_of(env, run_id, company).status == "done", run_of(env, run_id, company)
    assert env.mock.pending == 0
    return list(env.mock.calls[before:])


def system_user(request: ProviderRequest) -> tuple[str, str]:
    body: dict[str, Any] = request.to_json()
    return json.dumps(body["system"], ensure_ascii=False), json.dumps(body["user"], ensure_ascii=False)


def seen(calls: list[ProviderRequest]) -> str:
    return " ".join(" ".join(system_user(c)) for c in calls)


def models_of(calls: list[ProviderRequest]) -> tuple[list[tuple[float | None, int]], list[tuple[float | None, int]]]:
    """(1부 요청의 (temperature, 위끝), 2부 요청의 (temperature, 위끝))."""
    pairs = [(c.temperature, c.max_output_tokens) for c in calls]
    return pairs[:PART1], pairs[PART1:]


CODE = (
    [(colab_155.CODE_RESEARCH.temperature, colab_155.CODE_RESEARCH.max_output_tokens)] * PART1,
    [(None, part2_155.CODE_ANALYSIS.max_output_tokens)] * 9,
)
EDITED_PAIRS = ([(0.3, 8000)] * PART1, [(None, 9000)] * 9)


def rewrite(company_id: int, setting_id: int, **fields: Any) -> None:
    """판 행을 고친다(판 불변을 어긴 행 — 시험만. 앱 역할은 UPDATE 를 applied·applied_at 둘만 받는다)."""
    rows = apps.get_model("materiality", "MaterialityAiSettingRow")._meta.managers_map["unscoped"]
    rows.filter(company_id=company_id, pk=setting_id).update(**fields)


# ── 3-4-3 업무 양성 ──


def test_the_applied_setting_reaches_the_provider(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    setting_id = save(a, prompts=marked("a"), model=EDITED)
    run_id = made(client, world, a)
    versions = run_of(world, run_id, a).versions
    assert (versions["aiSetting"], versions["aiSettingId"]) == ("v1", setting_id)
    assert "promptsSha256" in versions
    calls = calls_of(world, run_id, a)
    assert len(calls) == PART1 + 9
    regulation = [c for c in calls[:PART1] if "⟦IR4-a-regulation_prefix⟧" in system_user(c)[1]]
    assert len(regulation) == 2  # 규제 둘(토픽 둘)의 user 에만
    impact = [c for c in calls if "⟦IR4-a-impact_system⟧" in system_user(c)[0]]
    assert impact and all(c in calls[PART1:] for c in impact)  # 2부 영향 호출의 system 에만
    assert models_of(calls) == EDITED_PAIRS
    assert {c.api_model_id for c in calls[:PART1]} != {c.api_model_id for c in calls[PART1:]}  # 리서치·분석 모델 둘


def test_a_code_text_setting_sends_the_default_texts_with_its_model(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    save(a, prompts=None, model=EDITED)
    run_id = made(client, world, a)
    assert "promptsSha256" not in run_of(world, run_id, a).versions
    calls = calls_of(world, run_id, a)
    assert "⟦IR4-" not in seen(calls)
    assert json.dumps(DEFAULT_IMPACT, ensure_ascii=False)[1:-1] in seen(calls)  # 기본 글(영향 지시 글의 첫 줄)
    assert models_of(calls) == EDITED_PAIRS


def test_the_default_setting_sends_the_code_values(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    run_id = made(client, world, a)
    assert run_of(world, run_id, a).versions["aiSetting"] == DEFAULT_TITLE
    assert models_of(calls_of(world, run_id, a)) == CODE


# ── 3-4-2 진행 중 실행 고정 ──


def test_a_run_made_with_v1_ends_with_v1_after_v2_is_applied(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    v1 = save(a, prompts=marked("v1"), model=EDITED)
    run_id = made(client, world, a)
    v2 = save(a, prompts=marked("v2"), model=model_body(temperature=1.5, cap=4000))
    assert v2 != v1
    assert MaterialityAiSettingRow.for_company(a).get(applied=True).id == v2  # 적용은 v2 로 바뀌었다
    calls = calls_of(world, run_id, a)
    assert "⟦IR4-v1-impact_system⟧" in seen(calls) and "⟦IR4-v2-" not in seen(calls)
    assert models_of(calls) == EDITED_PAIRS
    assert run_of(world, run_id, a).versions["aiSettingId"] == v1
    later = made(client, world, a)  # 분모: 새 실행은 v2
    later_calls = calls_of(world, later, a)
    assert "⟦IR4-v2-impact_system⟧" in seen(later_calls)
    assert models_of(later_calls)[0] == [(1.5, 4000)] * PART1


# ── 3-4-4 회사 섞임 0 ──


def test_each_company_runs_with_its_own_setting_on_one_worker(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a, b = world.company_a, world.company_b
    save(a, prompts=marked("a"), model=EDITED)
    save(b, prompts=marked("b"))
    run_a = made(client, world, a)
    run_b = made(client, world, b)
    calls_a = calls_of(world, run_a, a)
    calls_b = calls_of(world, run_b, b)
    assert "⟦IR4-a-impact_system⟧" in seen(calls_a) and "⟦IR4-b-" not in seen(calls_a)
    assert "⟦IR4-b-impact_system⟧" in seen(calls_b) and "⟦IR4-a-" not in seen(calls_b)
    assert models_of(calls_a) == EDITED_PAIRS
    assert models_of(calls_b) == CODE  # B 판은 모델 칸이 기본값
    MaterialityAiSettingRow.for_company(b).update(applied=False, applied_at=datetime.now(UTC))  # B 를 기본 판으로
    run_c = made(client, world, b)
    assert run_of(world, run_c, b).versions["aiSettingId"] is None
    assert "⟦IR4-" not in seen(calls_of(world, run_c, b))


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
    response = run_in(client, **operator())
    assert response.status_code == 201, response.content.decode()
    run_id = response.json()["id"]
    assert run_of(world, run_id, b).versions["aiSettingId"] == b_id
    found = seen(calls_of(world, run_id, b))
    assert "⟦IR4-b-impact_system⟧" in found and "⟦IR4-a-" not in found


def test_the_run_store_reads_only_the_runs_company(world: World) -> None:
    """실행기의 판 읽기(RunSettingStore)는 회사 조건을 늘 적는다 — 남의 회사의 판 id 는 없음, 적용 판도 제 회사만."""
    a, b = world.company_a, world.company_b
    b_id = save(b, prompts=marked("b"))
    store = RunSettingStore()
    assert isinstance(store.get(b, b_id), SavedSetting)  # 분모: 제 회사면 판
    assert store.get(a, b_id) == SettingNotFound(b_id)
    assert isinstance(store.applied(a), DefaultSetting)
    assert store.applied(b) == store.get(b, b_id)


# ── 3-4-5 어긋남·좁아짐 ──


@pytest.mark.parametrize("field", ["prompts", "model_settings"])
def test_a_setting_row_changed_after_the_run_was_made_fails_the_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    setting_id = save(a, prompts=marked("a"), model=EDITED)
    run_id = made(client, world, a)
    if field == "prompts":
        rewrite(a, setting_id, prompts=marked("a!"))
    else:
        rewrite(a, setting_id, model_settings=model_body(temperature=0.3, cap=8000, analysis_cap=9001))
    execute(world, run_id, a)
    run = run_of(world, run_id, a)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch")
    assert world.mock.calls == []


def test_a_setting_the_narrowed_rules_refuse_cannot_make_a_run(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    a = world.company_a
    save(a, prompts=marked("a"))
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)
    login(client)
    response = run_in(client)
    assert response.status_code == 409, response.content.decode()
    assert response.json()["error"]["code"] == "AI_SETTING_UNUSABLE"
    runs = apps.get_model("runs", "RunRow")._meta.managers_map["unscoped"]
    assert runs.filter(company_id=a).count() == 0  # 행 0
    login(client, tenant_id="tenant-b")  # 분모: 기본 판 회사 B 의 같은 요청은 좁혀도 201
    assert run_in(client).status_code == 201


def test_a_run_made_before_narrowing_fails_with_versions_mismatch(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    a = world.company_a
    save(a, prompts=marked("a"))
    run_id = made(client, world, a)
    monkeypatch.setattr(core_ai_settings, "PROMPT_TEXT_MAX_CHARS", 10)
    execute(world, run_id, a)
    run = run_of(world, run_id, a)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch")
    assert world.mock.calls == []


# ── 3-4-7 이어 돌기 ──


def test_a_resumed_run_keeps_the_setting_it_was_made_with(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2부 첫 단계에서 끊긴 실행을 v2 적용 뒤 이어 돌려도 앞 versions(v1)를 물려받아 v1 의 글·모델로 남은 단계를
    부른다."""
    scripted(monkeypatch, world)
    a = world.company_a
    v1 = save(a, prompts=marked("v1"), model=EDITED)
    first = made(client, world, a)
    original = iro_155.part2_inputs
    tries = {"n": 0}

    def once_failing(inputs: Any) -> Any:
        tries["n"] += 1
        if tries["n"] == 1:
            raise RuntimeError("가상 실패 — 한 번")
        return original(inputs)

    monkeypatch.setattr(iro_155, "part2_inputs", once_failing)
    script_iro(world.mock, options()["input"])
    execute(world, first, a)
    run = run_of(world, first, a)
    assert (run.status, run.failed_step) == ("failed", "impact")
    assert run.versions["aiSettingId"] == v1
    save(a, prompts=marked("v2"), model=model_body(temperature=1.5, cap=4000))
    before = len(world.mock.calls)
    login(client, tenant_id=tenant_of(world, a))
    body = {"module": "materiality", "options": {}, "resumeFromRunId": first}
    response = client.post("/api/runs", data=body, content_type="application/json")
    assert response.status_code == 201, response.content.decode()
    resumed: int = response.json()["id"]
    assert run_of(world, resumed, a).versions == run.versions  # 앞 versions 그대로(v1)
    execute(world, resumed, a)
    assert run_of(world, resumed, a).status == "done"
    calls = list(world.mock.calls[before:])
    assert len(calls) == 9 and world.mock.pending == 0  # 2부만(1부는 앞 실행의 것을 옮김)
    assert "⟦IR4-v1-impact_system⟧" in seen(calls) and "⟦IR4-v2-" not in seen(calls)
    assert [(c.temperature, c.max_output_tokens) for c in calls] == [(None, 9000)] * 9


# ── 3-4-6 실행 기록 「AI 설정」 칸 ──


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
        module="materiality",
        status=None,
        date_from=None,
        date_to=None,
        q=None,
        limit=10,
        offset=0,
        review="pending",
    )
    assert isinstance(pending, operator_selectors.OperatorRunPage) and pending.count == 0  # 검토 화면 없음


# ── 옛 판(칸 열일곱 — IRA3, MARC-ENT-569) ──


def test_an_applied_legacy_version_runs_with_the_default_three(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """옛 판 행(ORM — import_setting 꼴)을 적용한 회사의 실행 만들기 201 · 끝까지 · 옛 셋 글은 요청에 0."""
    scripted(monkeypatch, world)
    a = world.company_a
    setting_id = (
        MaterialityAiSettingRow.for_company(a)
        .create(
            company_id=a,
            name="v1",
            title="⟦지어낸 옛 판⟧",
            model_settings=model_body(),
            prompts=legacy_body(),
            memo="",
            created_by_user_id=9,
        )
        .id
    )
    applied = settings_services.apply_setting(company_id=a, setting_id=setting_id, now=datetime.now(UTC))
    assert isinstance(applied, settings_services.Applied), applied
    run_id = made(client, world, a)
    versions = run_of(world, run_id, a).versions
    assert (versions["aiSetting"], versions["aiSettingId"]) == ("v1", setting_id)
    assert versions["promptsSha256"] != pm.legacy_sha256(legacy_body())  # 새 실행은 열넷 sha
    calls = calls_of(world, run_id, a)
    assert len(calls) == PART1 + 9
    assert OLD_TEXT not in seen(calls)
