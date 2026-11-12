"""translation 의 흐름을 레지스트리에 단다. 전역 REGISTRY 에는 apps.py 의 ready() 가 한 번 부른다(greenwash 꼴).

순수 테스트는 새 FlowRegistry() 에 단다. 기본 흐름은 코드 상수다.
"""

from typing import Final

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import Flow
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows import pdf_158 as pdf

FLOWS: Final[tuple[Flow, ...]] = (colab.FLOW, pdf.FLOW)  # pdf@158 = PDF 입력(밴드 TRD2) — 기본은 colab 그대로
DEFAULTS: Final[dict[str, str]] = {"translation": colab.FLOW_ID}


def register(registry: FlowRegistry) -> None:
    """흐름을 달고 기본값을 정한다. 두 번 부르면 FlowRegistryError(같은 흐름 두 번)."""
    for flow in FLOWS:
        registry.register(flow)
    for module, flow_id in DEFAULTS.items():
        registry.set_default(module, flow_id)
