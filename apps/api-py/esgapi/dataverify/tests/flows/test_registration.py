"""등록(처분 ① 가): 새 레지스트리에 한 번 달면 기본 흐름이 서고, 두 번 달면 거절. 전역 REGISTRY 와 끼움은 DV1d."""

import pytest

from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import FlowRegistryError
from esgapi.dataverify.flows import colab_156, registration


def test_registration_into_a_fresh_registry() -> None:
    registry = FlowRegistry()
    registration.register(registry)
    assert registry.defaults() == registration.DEFAULTS == {"dataverify": "dataverify.colab@156"}
    assert registry.flows_of("dataverify") == (colab_156.FLOW,)
    assert registry.default_of("dataverify") is colab_156.FLOW
    with pytest.raises(FlowRegistryError, match=r"dataverify\.colab@156 이 이미 있다"):
        registration.register(registry)


def test_the_flow_declaration() -> None:
    flow = colab_156.FLOW
    assert (flow.module, flow.id, flow.input_shape) == ("dataverify", "dataverify.colab@156", "dataverify.input@1")
    assert flow.result_shapes == ("dataverify.result@2", "dataverify.digest@1")
    assert flow.output_files == ("dataverify-report.xlsx",)
    assert flow.steps == ("load", "plan", "review", "insight", "report")
    assert flow.adapter_names == ("llm",)
    assert flow.optional_adapters == ()
