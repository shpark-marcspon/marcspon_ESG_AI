"""앱 greenwash 의 ready() 가 흐름 곁에 끼움을 단다(밴드 G1b): 전역 BINDINGS 의 greenwash.colab@E0 은 기본 경로(실제
이름)의 GreenwashBinding 하나다. 다른 앱 레지스트리의 ready 는 두 번 달지 않는다(달면 FlowRegistryError 로 터진다).
"""

from django.apps.registry import Apps
from django.conf import settings
from django.test.utils import isolate_apps

from esgapi.core.flows.binding import BINDINGS
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.binding_e0 import GreenwashBinding


def test_ready_registered_the_binding_with_the_real_routes() -> None:
    binding = BINDINGS.get(colab.FLOW_ID)
    assert isinstance(binding, GreenwashBinding)
    assert (binding.chat_route, binding.embedding_route) == ("light-openai-41", "light-openai")
    assert colab.FLOW_ID in BINDINGS.flow_ids()


def test_another_app_registry_does_not_bind_again() -> None:
    before = BINDINGS.get(colab.FLOW_ID)
    Apps(list(settings.INSTALLED_APPS))
    with isolate_apps("esgapi.greenwash"):
        pass
    assert BINDINGS.get(colab.FLOW_ID) is before
