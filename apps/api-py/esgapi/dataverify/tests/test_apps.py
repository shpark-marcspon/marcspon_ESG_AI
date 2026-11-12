"""앱 dataverify 의 ready()(밴드 DV1d §3-1-7): 전역 REGISTRY 에 흐름 하나·기본값을 달고, 전역 BINDINGS 에 문서 없는 끼움
하나를 옵션 상한 256KiB 로 단다(문서 갈래 get 은 NoBinding). isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리의 ready
는 두 번 달지 않는다(달면 FlowRegistryError 로 터진다).
"""

from django.apps.registry import Apps
from django.conf import settings
from django.test.utils import isolate_apps

from esgapi.core.flows.binding import BINDINGS, NoBinding
from esgapi.core.flows.registry import REGISTRY
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.flows.binding_156 import DataverifyBinding


def test_ready_registered_the_flow_and_the_default() -> None:
    assert REGISTRY.flows_of("dataverify") == (colab_156.FLOW,)
    assert REGISTRY.default_of("dataverify") is colab_156.FLOW
    assert REGISTRY.defaults()["dataverify"] == "dataverify.colab@156"


def test_ready_registered_a_documentless_binding_with_the_256kib_limit() -> None:
    assert isinstance(BINDINGS.documentless("dataverify.colab@156"), DataverifyBinding)
    assert BINDINGS.get("dataverify.colab@156") == NoBinding("dataverify.colab@156")
    assert BINDINGS.options_limit("dataverify.colab@156") == 262_144
    assert "dataverify.colab@156" in BINDINGS.flow_ids()


def test_another_app_registry_does_not_register_again() -> None:
    before = (REGISTRY.defaults(), REGISTRY.flows_of("dataverify"), BINDINGS.documentless(colab_156.FLOW_ID))
    Apps(list(settings.INSTALLED_APPS))
    with isolate_apps("esgapi.dataverify"):
        pass
    after = (REGISTRY.defaults(), REGISTRY.flows_of("dataverify"), BINDINGS.documentless(colab_156.FLOW_ID))
    assert after[:2] == before[:2]
    assert after[2] is before[2]
    assert BINDINGS.flow_ids().count(colab_156.FLOW_ID) == 1
