"""앱 greenwash 의 ready(): 전역 앱 레지스트리에서만 흐름을 단다.

isolate_apps·Apps(...) 가 지은 다른 앱 레지스트리의 ready 에서 두 번 달지 않는다.
"""

from django.apps.registry import Apps
from django.conf import settings
from django.test.utils import isolate_apps

from esgapi.core.flows.registry import REGISTRY


def test_another_app_registry_does_not_register_again() -> None:
    before = (REGISTRY.defaults(), REGISTRY.flows_of("greenwash"))
    Apps(list(settings.INSTALLED_APPS))
    with isolate_apps("esgapi.greenwash"):
        pass
    after = (REGISTRY.defaults(), REGISTRY.flows_of("greenwash"))
    assert after == before
    assert len(REGISTRY.flows_of("greenwash")) == 4  # colab@E0 · rewrite@R1 · rejudge@E0(GRJ1) · engine@G1(GE1b ③)
