"""drafting 의 흐름을 레지스트리에 단다(밴드 RP1 ②). 전역 REGISTRY 에 다는 것과 실행기 끼움은 apps.py 다.
순수 테스트는 새 FlowRegistry() 에 단다."""

from typing import Final

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import Flow
from esgapi.drafting.flows import draft_v2

FLOWS: Final[tuple[Flow, ...]] = (draft_v2.FLOW,)
DEFAULTS: Final[dict[str, str]] = {"drafting": draft_v2.FLOW_ID}


def register(registry: FlowRegistry) -> None:
    """흐름을 달고 기본값을 정한다. 두 번 부르면 FlowRegistryError(같은 흐름 두 번)."""
    for flow in FLOWS:
        registry.register(flow)
    for module, flow_id in DEFAULTS.items():
        registry.set_default(module, flow_id)
