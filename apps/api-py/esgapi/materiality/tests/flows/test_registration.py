"""등록(처분 ⑧ 가, IR2b ⑦ 가): 새 레지스트리에 한 번 달면 흐름 둘과 기본 흐름(한 실행)이 서고, 두 번 달면 거절. 전역
REGISTRY 와 끼움은 IR3a 의 apps.py·binding_155."""

import pytest

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import FlowRegistryError
from esgapi.materiality.flows import colab_155, iro_155, registration


def test_registration_into_a_fresh_registry() -> None:
    registry = FlowRegistry()
    registration.register(registry)
    assert registry.defaults() == registration.DEFAULTS == {"materiality": "materiality.iro@155"}
    assert registry.flows_of("materiality") == (colab_155.FLOW, iro_155.FLOW)
    assert registry.default_of("materiality") is iro_155.FLOW
    with pytest.raises(FlowRegistryError, match=r"materiality\.colab@155 이 이미 있다"):
        registration.register(registry)


def test_the_flow_declaration() -> None:
    flow = colab_155.FLOW
    assert (flow.module, flow.id, flow.input_shape) == ("materiality", "materiality.colab@155", "materiality.input@1")
    assert flow.result_shapes == ("materiality.result@1",)
    assert flow.output_files == ("materiality-websearch.xlsx",)
    assert flow.steps == ("load", "regulation", "keywords", "controversy", "report")
    assert flow.adapter_names == ("llm",)
    assert flow.optional_adapters == ()
