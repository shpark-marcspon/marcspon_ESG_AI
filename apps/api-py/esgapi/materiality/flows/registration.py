"""materiality 의 흐름을 레지스트리에 단다(밴드 IR1b, 한 실행 흐름과 기본값은 IR2b — MARC-ENT-439). 전역 REGISTRY 에
다는 것과 실행기 끼움은 IR3a 의 apps.py·binding_155 다.
순수 테스트는 새 FlowRegistry() 에 단다.
"""

from typing import Final

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import Flow
from esgapi.materiality.flows import colab_155, iro_155

FLOWS: Final[tuple[Flow, ...]] = (colab_155.FLOW, iro_155.FLOW)
"""1부 단독(@1 — IRL 견본·대조 몫)과 1부 → 2부 한 실행(@2)."""
DEFAULTS: Final[dict[str, str]] = {"materiality": iro_155.FLOW_ID}


def register(registry: FlowRegistry) -> None:
    """흐름을 달고 기본값을 정한다. 두 번 부르면 FlowRegistryError(같은 흐름 두 번)."""
    for flow in FLOWS:
        registry.register(flow)
    for module, flow_id in DEFAULTS.items():
        registry.set_default(module, flow_id)
