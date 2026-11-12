"""실행 만들기의 판 묶음 거절(밴드 G2c3 §3-2-3 — 끼움 일반). 업무 층: 진짜 DB, 흐름·끼움은 test_runs 의 시험 것
(actions.REGISTRY·actions.BINDINGS 를 바꿔 끼움)에 둘째 꼴(RunFactsBinding) 가짜 하나를 더 단다.

    versions_with 가 RunVersionsRejected → 409 AI_SETTING_UNUSABLE · message 는 끼움의 글 그대로 · 실행·단계 행 0 ·
    감사 0 · 쪽지 0. 분모: 옛 꼴 끼움(RunBinding)의 같은 요청은 201.

글은 지어낸 것이다(synthetic).
"""

from collections.abc import Mapping

import pytest
from django.test import Client

from esgapi.core.flows.binding import (
    BindingRegistry,
    DocumentInput,
    DocumentlessFactsBinding,
    RunFactsBinding,
    RunVersionsRejected,
)
from esgapi.runs.models import RunRow, RunStepRow
from esgapi.runs.service.actions import runs as actions
from esgapi.runs.tests.service.apis.test_runs import (
    BARE,
    PROBE,
    PROBE_TWO,
    BareBinding,
    ProbeBinding,
    ProbeInputs,
    World,
    bare,
    bare_body,
    create,
    document,
    error_of,
    run_lines,
    world,
)
from tests.support.http import login

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (world, bare)  # test_runs 의 고정물을 이 모듈에서도 이름으로 찾게(pytest 는 모듈의 이름을 본다)
REFUSED = "지어낸 거절 글: 이 회사의 판 묶음을 지금 지을 수 없어요"


class RefusingBinding(ProbeBinding):
    """둘째 꼴 끼움. 만들 때 판 묶음을 늘 못 짓는다."""

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        raise RunVersionsRejected(REFUSED)

    def inputs_with(
        self, document: DocumentInput, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> object:
        return ProbeInputs(document=document)


def test_a_binding_that_cannot_build_the_versions_is_409_and_writes_nothing(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    refusing = RefusingBinding()
    assert isinstance(refusing, RunFactsBinding)  # 분모: 실행 만들기가 versions_with 를 부르는 꼴이다
    bindings = BindingRegistry()
    bindings.register(PROBE.id, ProbeBinding())
    bindings.register(PROBE_TWO.id, refusing)
    monkeypatch.setattr(actions, "BINDINGS", bindings)
    login(client)
    doc = document(world.company_a)
    refused = create(client, {"module": "probe", "flowId": PROBE_TWO.id, "documentId": doc})
    assert error_of(refused) == (409, "AI_SETTING_UNUSABLE")
    assert refused.json()["error"]["message"] == REFUSED
    assert RunRow.for_company(world.company_a).count() == 0
    assert RunStepRow.for_company(world.company_a).count() == 0
    assert run_lines(world.company_a) == []
    assert world.sent == []
    made = create(client, {"module": "probe", "flowId": PROBE.id, "documentId": doc})  # 옛 꼴 끼움 — 그대로
    assert made.status_code == 201, made.content.decode()
    assert RunRow.for_company(world.company_a).count() == 1


# ── 문서 없는 흐름의 둘째 꼴(ND1 — DocumentlessFactsBinding) ──────────────


class BareFactsBinding(BareBinding):
    """문서 없는 둘째 꼴 끼움. 만들 때 그 회사의 판(지어낸 값)을 박는다. refuse 면 못 짓는다."""

    def __init__(self, *, refuse: bool = False) -> None:
        super().__init__()
        self.refuse = refuse

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        if self.refuse:
            raise RunVersionsRejected(REFUSED)
        return {"aiSettingId": company_id * 10, "rules": "bare-rules@2"}

    def inputs_with(self, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]) -> object:
        return dict(options)


def bare_facts(monkeypatch: pytest.MonkeyPatch, binding: BareFactsBinding) -> None:
    bindings = BindingRegistry()
    bindings.register(PROBE.id, ProbeBinding())
    bindings.register_documentless(BARE.id, binding)
    monkeypatch.setattr(actions, "BINDINGS", bindings)


def test_a_documentless_facts_binding_stamps_the_companys_versions(
    client: Client, world: World, bare: BareBinding, monkeypatch: pytest.MonkeyPatch
) -> None:
    """versions_with(회사)로 판 묶음을 박는다(versions 가 아니다 — P21). 이어 돌기는 앞 실행의 판 그대로."""
    binding = BareFactsBinding()
    assert isinstance(binding, DocumentlessFactsBinding)
    bare_facts(monkeypatch, binding)
    login(client)
    made = create(client, bare_body())
    assert made.status_code == 201, made.content.decode()
    run = RunRow.for_company(world.company_a).get(pk=made.json()["id"])
    assert run.versions == {"aiSettingId": world.company_a * 10, "rules": "bare-rules@2", "flow": BARE.id}
    # 이어 돌기: 앞 실행의 판(지금 끼움이 짓는 값과 다르게 바꿔 둠)
    old = {"aiSettingId": 1, "rules": "bare-rules@1", "flow": BARE.id}
    RunRow.for_company(world.company_a).filter(pk=run.pk).update(status="failed", versions=old)
    resumed = create(client, bare_body(resumeFromRunId=run.pk))
    assert resumed.status_code == 201, resumed.content.decode()
    assert RunRow.for_company(world.company_a).get(pk=resumed.json()["id"]).versions == old


def test_a_documentless_binding_that_cannot_build_the_versions_is_409_and_writes_nothing(
    client: Client, world: World, bare: BareBinding, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare_facts(monkeypatch, BareFactsBinding(refuse=True))
    login(client)
    refused = create(client, bare_body())
    assert error_of(refused) == (409, "AI_SETTING_UNUSABLE")
    assert refused.json()["error"]["message"] == REFUSED
    assert (RunRow.unscoped.count(), RunStepRow.unscoped.count()) == (0, 0)
    assert run_lines(world.company_a) == []
    assert world.sent == []
    bare_facts(monkeypatch, BareFactsBinding())  # 분모: 지을 수 있으면 201
    assert create(client, bare_body()).status_code == 201
