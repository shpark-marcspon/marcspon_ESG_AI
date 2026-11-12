"""greenwash 의 흐름을 레지스트리에 단다. 전역 REGISTRY 에는 apps.py 의 ready() 가 한 번 부른다.

순수 테스트는 새 FlowRegistry() 에 단다. 기본 흐름은 코드 상수다(실행기 밴드가 어드민 표로 옮긴다).
결과 꼴(contracts/shapes.py)은 이 길에서 들이지 않는다.
rewrite 는 E0 뒤에 따로 부르는 흐름(결과를 받는다)이라 기본값이 아니다. rejudge(GRJ1)는 검토 화면이 E0 결과의 문장
하나를 다시 판정하는 문서 없는 흐름이라 기본값이 아니다. engine@G1(2차 엔진, GE1b ③)은 flowId 로 고르는 흐름이라
기본값이 아니고, 실행 시작은 끼움의 환경 스위치(기본 꺼짐 — GREENWASH_G1_RUNS_ENABLED)가 막는다.
"""

from typing import Final

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import Flow
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import engine_g1
from esgapi.greenwash.flows import rejudge_e0 as rejudge
from esgapi.greenwash.flows import rewrite_r1 as rewrite

FLOWS: Final[tuple[Flow, ...]] = (colab.FLOW, rewrite.FLOW, rejudge.FLOW, engine_g1.g1_flow())
DEFAULTS: Final[dict[str, str]] = {"greenwash": "greenwash.colab@E0"}


def register(registry: FlowRegistry) -> None:
    """흐름을 달고 기본값을 정한다. 두 번 부르면 FlowRegistryError(같은 흐름 두 번)."""
    for flow in FLOWS:
        registry.register(flow)
    for module, flow_id in DEFAULTS.items():
        registry.set_default(module, flow_id)
