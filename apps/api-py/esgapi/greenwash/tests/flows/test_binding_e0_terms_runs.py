# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""판의 대상 단어로 세는 실행 — 업무 끝까지(밴드 G2d ③ §3-3-6). 진짜 DB, 판 읽기는 진짜 RunSettingStore, 실행
만들기는 전역 BINDINGS 의 끼움(test_binding_e0_settings_runs.py 의 settings_world 그대로).

    3-3-6  단어 판 적용 → POST /runs(versions.termsSha256) → 실행기 → 결과 terms·빈도에 더한 낱말 · 기본 판 회사 B 의
           실행은 열쇠·칸 없음 · 적용 뒤 받기를 좁힘 → POST /runs 409 AI_SETTING_UNUSABLE·실행 행 0(W5) · 만든 뒤
           받기를 좁힘 → 실행기 failed·versions_mismatch·공급사 호출 0

단어는 지어낸 것이다. 실제 공급사·키·네트워크 0.
"""

from datetime import UTC, datetime

import pytest
from django.test import Client

from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.models import DocumentRow
from esgapi.greenwash.engines.e0.gw1 import GREEN_TERMS
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import terms_e0
from esgapi.greenwash.flows.criteria_e0 import default_criteria
from esgapi.greenwash.flows.terms_e0 import terms_sha256
from esgapi.greenwash.service.services import ai_settings as settings_services
from esgapi.greenwash.tests.flows.test_binding_e0_runs import (
    DEFAULT_MODEL_SHA,
    MINIMAL,
    World,
    create,
    document,
    execute,
    new_run,
    result_body,
    run_of,
    world,
)
from esgapi.greenwash.tests.flows.test_binding_e0_settings_runs import counts, settings_world
from esgapi.greenwash.tests.flows.test_binding_e0_terms import ADDED, board
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (world, settings_world)  # 고정물을 이 모듈에서도 이름으로 찾게(pytest 는 모듈의 이름을 본다)


def save_terms(company_id: int) -> int:
    created = settings_services.create_setting(
        company_id=company_id,
        created_by_user_id=9,
        title="지어낸 판",
        criteria=default_criteria(),
        memo="",
        terms=board(ADDED),
    )
    assert isinstance(created, settings_services.Created), created
    settings_services.apply_setting(company_id=company_id, setting_id=created.id, now=datetime.now(UTC))
    return created.id


def narrow_terms(monkeypatch: pytest.MonkeyPatch) -> None:
    """단어 받기를 좁힌다: 개수 상한 2(저장할 때는 받았던 판이 이제 거절된다)."""
    monkeypatch.setattr(terms_e0, "TERMS_MAX", 2)


def test_a_run_on_a_board_counts_the_board_words(client: Client, settings_world: World) -> None:
    env = settings_world
    saved = save_terms(env.company_a)
    run_id = new_run(client, env, MINIMAL)
    made = run_of(env, run_id).versions
    assert made == {
        **colab.run_versions(default_criteria()),
        "aiSetting": "v1",  # 판 이름(그 회사의 첫 판)
        "aiSettingId": saved,
        "flow": colab.FLOW_ID,
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
        "termsSha256": terms_sha256([*GREEN_TERMS, ADDED]),
    }
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("done", None), run
    body = result_body(env, run_id)
    assert body["terms"] == [*GREEN_TERMS, ADDED]
    assert {row["term"]: row["count"] for row in body["wordCounts"]["total"]}[ADDED] == 1
    assert run.versions == made


def test_a_default_company_run_has_no_terms(client: Client, settings_world: World) -> None:
    """회사 B(기본 판)는 A 의 단어 판에 닿지 않는다 — 열쇠·칸 없음."""
    env = settings_world
    save_terms(env.company_a)
    b = env.company_b
    login(client, tenant_id="tenant-b")
    doc_b = DocumentRow.for_company(b).create(
        company_id=b,
        uploaded_by="1",
        file_name="지어낸-보고서.pdf",
        storage_key=f"companies/{b}/documents/g2d/original",
        size_bytes=10,
        status="uploaded",
    )
    made = create(client, {"module": "greenwash", "documentId": doc_b.pk, "options": MINIMAL})
    assert made.status_code == 201, made.content.decode()
    found = run_selectors.find_run(company_id=b, run_id=made.json()["id"])
    assert found is not None
    assert "termsSha256" not in found.versions and found.versions["aiSettingId"] is None


def test_a_board_the_rules_no_longer_take_is_409(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """W5: 적용 뒤 단어 받기가 좁아지면 POST /runs 409 AI_SETTING_UNUSABLE, 실행 행·단계·감사 0."""
    env = settings_world
    a = env.company_a
    save_terms(a)
    new_run(client, env, MINIMAL)  # 분모: 좁히기 전엔 201
    before = counts(a)
    narrow_terms(monkeypatch)
    refused = create(client, {"module": "greenwash", "documentId": document(env), "options": MINIMAL})
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "AI_SETTING_UNUSABLE")
    assert ADDED not in refused.json()["error"]["message"]  # 단어 0
    assert counts(a) == before


def test_a_run_whose_board_the_rules_no_longer_take_fails(
    client: Client, settings_world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """만든 뒤 단어 받기가 좁아지면 실행기 failed·versions_mismatch, 공급사 호출 0."""
    env = settings_world
    save_terms(env.company_a)
    run_id = new_run(client, env, MINIMAL)
    assert "termsSha256" in run_of(env, run_id).versions
    narrow_terms(monkeypatch)
    env.sink = MemorySink()
    execute(env, run_id)
    run = run_of(env, run_id)
    assert (run.status, run.error_code) == ("failed", "versions_mismatch"), run
    assert env.mock.calls == []
