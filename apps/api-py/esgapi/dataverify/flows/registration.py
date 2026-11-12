"""dataverify 의 흐름을 레지스트리에 단다(밴드 DV1b). 전역 REGISTRY 에 다는 것과 실행기 끼움은 밴드 DV1d 의 apps.py
다(flows/binding_156.py — 문서 없는 흐름). 순수 테스트는 새 FlowRegistry() 에 단다.
"""

from typing import Final

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import Flow
from esgapi.dataverify.flows import colab_156

FLOWS: Final[tuple[Flow, ...]] = (colab_156.FLOW,)
DEFAULTS: Final[dict[str, str]] = {"dataverify": "dataverify.colab@156"}


def register(registry: FlowRegistry) -> None:
    """흐름을 달고 기본값을 정한다. 두 번 부르면 FlowRegistryError(같은 흐름 두 번)."""
    for flow in FLOWS:
        registry.register(flow)
    for module, flow_id in DEFAULTS.items():
        registry.set_default(module, flow_id)
