"""inventory 의 흐름 셋을 레지스트리에 단다. 전역 REGISTRY 에는 apps.py 의 ready() 가 한 번 부른다.

순수 테스트는 새 FlowRegistry() 에 단다. 기본 흐름은 코드 상수다(실행기 밴드가 어드민 표로 옮긴다).
"""

from typing import Final

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import Flow
from esgapi.inventory.flows import scope3_colab_157 as scope3_colab
from esgapi.inventory.flows import scope3_llm_first_1 as scope3
from esgapi.inventory.flows import scope12_engine_1 as scope12

FLOWS: Final[tuple[Flow, ...]] = (scope12.FLOW, scope3.FLOW, scope3_colab.FLOW)
# Scope 3 의 기본은 코랩 흐름(밴드 S3K1 — 끼움 flows/binding_157.py). llm-first@1 은 등록만(끼움 없음 — 지정하면 422)
DEFAULTS: Final[dict[str, str]] = {"inventory.scope12": "scope12.engine@1", "inventory.scope3": "scope3.colab@157"}


def register(registry: FlowRegistry) -> None:
    """흐름을 차례로 달고 기본값을 정한다. 두 번 부르면 FlowRegistryError(같은 흐름 두 번)."""
    for flow in FLOWS:
        registry.register(flow)
    for module, flow_id in DEFAULTS.items():
        registry.set_default(module, flow_id)
