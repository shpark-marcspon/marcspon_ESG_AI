"""앱 drafting 의 ready()(밴드 RP1 ②): 전역 REGISTRY 에 흐름 하나·기본값을 달고, 전역 BINDINGS 에 문서 없는 끼움
하나(drafting.draft@v2 — RP2b 가 v1 을 갈음, B12)를 옵션 상한 기본값(16KiB)으로 단다(문서 갈래 get 은 NoBinding).
RP2c B7: 그 끼움의 앞 실행 포트는 runs 의 selector 로 읽는 RunBaseSource 다.
isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리의 ready 는 두 번 달지 않는다(달면 FlowRegistryError 로 터진다).
"""

from django.apps.registry import Apps
from django.conf import settings
from django.test.utils import isolate_apps

from esgapi.core.flows.binding import BINDINGS, NoBinding
from esgapi.core.flows.registry import REGISTRY
from esgapi.drafting.flows import draft_v2
from esgapi.drafting.flows.binding_v2 import DraftingBinding
from esgapi.drafting.service.actions.run_sources import RunBaseSource
from esgapi.drafting.service.selectors.ai_settings import RunModelSource, RunSettingStore
from esgapi.drafting.service.selectors.run_extras import RunSettingExtras
from esgapi.runs.extras import EXTRAS


def test_ready_registered_the_flow_and_the_default() -> None:
    assert REGISTRY.flows_of("drafting") == (draft_v2.FLOW,)
    assert REGISTRY.default_of("drafting") is draft_v2.FLOW
    assert REGISTRY.defaults()["drafting"] == "drafting.draft@v2"


def test_ready_registered_a_documentless_binding_with_the_default_limit() -> None:
    assert isinstance(BINDINGS.documentless("drafting.draft@v2"), DraftingBinding)
    assert BINDINGS.get("drafting.draft@v2") == NoBinding("drafting.draft@v2")
    assert BINDINGS.options_limit("drafting.draft@v2") == 16_384
    assert "drafting.draft@v2" in BINDINGS.flow_ids()
    assert not [flow_id for flow_id in BINDINGS.flow_ids() if flow_id.startswith("drafting.draft@v1")]  # v1 은 걷음


def test_b7_the_binding_reads_the_base_run_through_runs() -> None:
    binding = BINDINGS.documentless("drafting.draft@v2")
    assert isinstance(binding, DraftingBinding) and isinstance(binding.bases, RunBaseSource)


def test_rpa1_b6_the_binding_reads_the_ai_setting_and_the_run_log_shows_it() -> None:
    """RPA1 ②: 끼움의 판 읽기·모델 원천 포트는 service selectors, 실행 기록 AI 설정 칸은 EXTRAS 의 drafting."""
    binding = BINDINGS.documentless("drafting.draft@v2")
    assert isinstance(binding, DraftingBinding)
    assert isinstance(binding.settings, RunSettingStore) and isinstance(binding.models, RunModelSource)
    assert isinstance(EXTRAS.get("drafting"), RunSettingExtras)


def test_another_app_registry_does_not_register_again() -> None:
    before = (REGISTRY.defaults(), REGISTRY.flows_of("drafting"), BINDINGS.documentless(draft_v2.FLOW_ID))
    Apps(list(settings.INSTALLED_APPS))
    with isolate_apps("esgapi.drafting"):
        pass
    after = (REGISTRY.defaults(), REGISTRY.flows_of("drafting"), BINDINGS.documentless(draft_v2.FLOW_ID))
    assert after[:2] == before[:2]
    assert after[2] is before[2]
    assert BINDINGS.flow_ids().count(draft_v2.FLOW_ID) == 1
