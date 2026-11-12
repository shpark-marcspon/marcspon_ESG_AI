"""등록: 새 레지스트리에 한 번 달면 기본 흐름이 서고, 두 번 달면 거절. 전역 REGISTRY 에는 앱의 ready() 가 달았다."""

import pytest

from esgapi.core.flows.registry import REGISTRY, FlowRegistry
from esgapi.core.flows.types import FlowRegistryError
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows import engine_g1, registration
from esgapi.greenwash.flows import rejudge_e0 as rejudge
from esgapi.greenwash.flows import rewrite_r1 as rewrite


def test_registration_into_a_fresh_registry() -> None:
    registry = FlowRegistry()
    registration.register(registry)
    assert registry.defaults() == registration.DEFAULTS == {"greenwash": "greenwash.colab@E0"}
    assert registry.flows_of("greenwash") == (colab.FLOW, rewrite.FLOW, rejudge.FLOW, registration.FLOWS[-1])
    assert registration.FLOWS[-1].id == engine_g1.FLOW_ID  # 2차 엔진(GE1b ③) — 기본값 아님
    assert registry.default_of("greenwash") is colab.FLOW
    with pytest.raises(FlowRegistryError, match=r"greenwash\.colab@E0 이 이미 있다"):
        registration.register(registry)


def test_ready_registered_the_flow_as_the_default() -> None:
    assert REGISTRY.default_of("greenwash") is colab.FLOW
    assert REGISTRY.flows_of("greenwash") == (colab.FLOW, rewrite.FLOW, rejudge.FLOW, registration.FLOWS[-1])
    assert {k: v for k, v in REGISTRY.defaults().items() if k in registration.DEFAULTS} == registration.DEFAULTS
