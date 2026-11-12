"""앱 materiality 의 ready()(밴드 IR3a §3-1-7): 전역 REGISTRY 에 흐름 둘·기본값(한 실행)을 달고, 전역 BINDINGS 에 문서
없는 끼움 하나(materiality.iro@155)를 옵션 상한 256KiB 로 단다(문서 갈래 get 은 NoBinding). 1부 단독 colab@155 는
끼우지 않는다(처분 ⑧ 가). isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리의 ready 는 두 번 달지 않는다(달면
FlowRegistryError 로 터진다).
"""

from django.apps.registry import Apps
from django.conf import settings
from django.test.utils import isolate_apps

from esgapi.core.flows.binding import BINDINGS, NoBinding
from esgapi.core.flows.registry import REGISTRY
from esgapi.materiality.flows import colab_155, iro_155
from esgapi.materiality.flows.binding_155 import MaterialityBinding


def test_ready_registered_the_two_flows_and_the_default() -> None:
    assert REGISTRY.flows_of("materiality") == (colab_155.FLOW, iro_155.FLOW)
    assert REGISTRY.default_of("materiality") is iro_155.FLOW
    assert REGISTRY.defaults()["materiality"] == "materiality.iro@155"


def test_ready_registered_a_documentless_binding_with_the_256kib_limit() -> None:
    assert isinstance(BINDINGS.documentless("materiality.iro@155"), MaterialityBinding)
    assert BINDINGS.get("materiality.iro@155") == NoBinding("materiality.iro@155")
    assert BINDINGS.options_limit("materiality.iro@155") == 262_144
    assert "materiality.iro@155" in BINDINGS.flow_ids()


def test_the_part1_flow_alone_is_not_bound() -> None:
    assert BINDINGS.documentless("materiality.colab@155") is None
    assert BINDINGS.get("materiality.colab@155") == NoBinding("materiality.colab@155")
    assert "materiality.colab@155" not in BINDINGS.flow_ids()


def test_another_app_registry_does_not_register_again() -> None:
    before = (REGISTRY.defaults(), REGISTRY.flows_of("materiality"), BINDINGS.documentless(iro_155.FLOW_ID))
    Apps(list(settings.INSTALLED_APPS))
    with isolate_apps("esgapi.materiality"):
        pass
    after = (REGISTRY.defaults(), REGISTRY.flows_of("materiality"), BINDINGS.documentless(iro_155.FLOW_ID))
    assert after[:2] == before[:2]
    assert after[2] is before[2]
    assert BINDINGS.flow_ids().count(iro_155.FLOW_ID) == 1
