"""끼움의 등록부(core/flows/binding.py — 순수). 시험은 runs 쪽에 둔다(실행기의 입구라서)."""

from collections.abc import Mapping

import pytest

from esgapi.core.flows.binding import (
    BINDINGS,
    DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS,
    DOCUMENTLESS_OPTIONS_MAX_OCTETS,
    BindingRegistry,
    DocumentInput,
    DocumentlessFactsBinding,
    NoBinding,
    RunContext,
    RunFactsBinding,
)
from esgapi.core.flows.types import FlowRegistryError


class Binding:
    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object:
        return document

    def adapters(self, ctx: RunContext) -> object:
        return ctx

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {}


def test_a_flow_gets_one_binding_and_a_second_is_refused() -> None:
    registry = BindingRegistry()
    binding = Binding()
    registry.register("test.flow@1", binding)
    assert registry.get("test.flow@1") is binding
    with pytest.raises(FlowRegistryError, match="이미"):
        registry.register("test.flow@1", binding)  # 같은 객체여도
    assert registry.flow_ids() == ("test.flow@1",)


def test_a_flow_without_a_binding_is_a_branch_not_an_error() -> None:
    assert BindingRegistry().get("test.none@1") == NoBinding("test.none@1")


def test_the_process_registry_is_one_object() -> None:
    assert isinstance(BINDINGS, BindingRegistry)


# ── 문서 없는 흐름(ND1) ───────────────────────────────────────────────


class BareBinding:
    """문서 없는 끼움(DocumentlessBinding 꼴)."""

    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> object:
        return (dict(options), company_id)

    def adapters(self, ctx: RunContext) -> object:
        return ctx

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {}


def test_a_flow_is_bound_once_across_both_branches_in_either_order() -> None:
    registry = BindingRegistry()
    registry.register("test.doc@1", Binding())
    registry.register_documentless("test.bare@1", BareBinding())
    with pytest.raises(FlowRegistryError, match="이미"):
        registry.register_documentless("test.doc@1", BareBinding())  # 문서 갈래에 있음
    with pytest.raises(FlowRegistryError, match="이미"):
        registry.register("test.bare@1", Binding())  # 문서 없는 갈래에 있음
    with pytest.raises(FlowRegistryError, match="이미"):
        registry.register_documentless("test.bare@1", BareBinding())
    assert registry.flow_ids() == ("test.doc@1", "test.bare@1")  # 둘 다, 단 차례
    later = BindingRegistry()
    later.register_documentless("test.bare@1", BareBinding())
    later.register("test.doc@1", Binding())
    assert later.flow_ids() == ("test.bare@1", "test.doc@1")


@pytest.mark.parametrize("limit", [0, -1, DOCUMENTLESS_OPTIONS_MAX_OCTETS + 1])
def test_an_options_limit_outside_one_to_the_max_is_refused(limit: int) -> None:
    registry = BindingRegistry()
    with pytest.raises(FlowRegistryError, match="상한"):
        registry.register_documentless("test.bare@1", BareBinding(), max_options_bytes=limit)
    assert registry.flow_ids() == ()
    assert registry.documentless("test.bare@1") is None
    # 분모: 끝값 둘은 받는다
    registry.register_documentless("test.one@1", BareBinding(), max_options_bytes=1)
    registry.register_documentless("test.max@1", BareBinding(), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS)
    assert (registry.options_limit("test.one@1"), registry.options_limit("test.max@1")) == (
        1,
        DOCUMENTLESS_OPTIONS_MAX_OCTETS,
    )


def test_the_branch_and_the_options_limit_come_from_the_registry() -> None:
    registry = BindingRegistry()
    doc, bare, wide = Binding(), BareBinding(), BareBinding()
    registry.register("test.doc@1", doc)
    registry.register_documentless("test.bare@1", bare)
    registry.register_documentless("test.wide@1", wide, max_options_bytes=200 * 1024)
    assert registry.documentless("test.bare@1") is bare
    assert registry.documentless("test.doc@1") is None
    assert registry.documentless("test.none@1") is None
    assert registry.get("test.bare@1") == NoBinding("test.bare@1")  # 문서 갈래로는 없다
    assert registry.get("test.doc@1") is doc
    assert registry.options_limit("test.wide@1") == 200 * 1024
    assert registry.options_limit("test.bare@1") == DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS == 16 * 1024
    assert registry.options_limit("test.doc@1") == DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS
    assert registry.options_limit("test.none@1") == DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS


def test_a_document_flow_takes_its_registered_options_limit() -> None:
    """문서 흐름도 상한을 등록한다(밴드 TR3a — 영문번역 256KiB). 등록하지 않으면 DEFAULT 그대로."""
    registry = BindingRegistry()
    registry.register("test.doc@1", Binding())
    registry.register("test.wide@1", Binding(), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS)
    assert registry.options_limit("test.doc@1") == DOCUMENTLESS_OPTIONS_DEFAULT_OCTETS
    assert registry.options_limit("test.wide@1") == DOCUMENTLESS_OPTIONS_MAX_OCTETS == 256 * 1024
    assert registry.documentless("test.wide@1") is None  # 갈래는 문서 흐름 그대로


@pytest.mark.parametrize("limit", [0, -1, DOCUMENTLESS_OPTIONS_MAX_OCTETS + 1])
def test_a_document_flow_limit_outside_one_to_the_max_is_refused(limit: int) -> None:
    registry = BindingRegistry()
    with pytest.raises(FlowRegistryError, match="상한"):
        registry.register("test.doc@1", Binding(), max_options_bytes=limit)
    assert registry.flow_ids() == ()
    assert registry.get("test.doc@1") == NoBinding("test.doc@1")
    # 분모: 끝값 둘은 받는다
    registry.register("test.one@1", Binding(), max_options_bytes=1)
    registry.register("test.max@1", Binding(), max_options_bytes=DOCUMENTLESS_OPTIONS_MAX_OCTETS)
    assert (registry.options_limit("test.one@1"), registry.options_limit("test.max@1")) == (
        1,
        DOCUMENTLESS_OPTIONS_MAX_OCTETS,
    )


class BareFacts(BareBinding):
    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        return {"company": company_id}

    def inputs_with(self, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]) -> object:
        return (dict(options), company_id, dict(versions))


def test_the_second_shapes_check_names_only_so_the_branch_comes_first() -> None:
    """runtime_checkable 은 이름만 본다: 문서 없는 둘째 꼴 끼움은 RunFactsBinding 으로도 True 다. 그래서 갈래는 사전으로
    먼저 가른다(만들기·실행기 — P20)."""
    facts = BareFacts()
    assert isinstance(facts, DocumentlessFactsBinding)
    assert isinstance(facts, RunFactsBinding)  # 이 함정 때문에
    assert not isinstance(BareBinding(), DocumentlessFactsBinding)
