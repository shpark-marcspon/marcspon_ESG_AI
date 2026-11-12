"""끼움 DataverifyBinding(밴드 DV1d §3-1, 순수): options@1 strict 받기와 문장(열쇠 길만 — 값 0), input 판정이
shapes.check_input 과 같음, 입력(받은 dict 그대로·회사 꼬리표·비용 상한·web_search 늘 True), 판 묶음, 포트 꼴. 옵션은
지어낸 값이다. 기대값은 손으로 적었다(상수를 불러 붙이지 않는다).
끝의 「source」 절은 밴드 DV1f §3-1-2~4(입력 출처 칸 — 받기 표·255자 경계·흐름 그대로).
"""

import copy
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import ValidationError

from esgapi.core.flows.binding import DocumentlessBinding, DocumentlessFactsBinding, RunOptionsRejected
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.embedding import EmbeddingClient
from esgapi.core.llm.types import Tags
from esgapi.dataverify.contracts import shapes
from esgapi.dataverify.flows import colab_156
from esgapi.dataverify.flows.binding_156 import STAGE_COSTS, DataverifyBinding, accept_options
from esgapi.dataverify.tests.flows.support import binding, options, received

SECRET = "가상비밀값-7f3a"
"""거절 문장에 실리면 안 되는 지어낸 값."""


def refused(given: Any) -> str:
    with pytest.raises(RunOptionsRejected) as caught:
        binding().check_options(given)
    return caught.value.message


def changed(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """지은 input 을 고친 것."""
    given = received()
    change(given)
    return given


def first_item(given: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = given["data"]["환경"][0]
    return item


# ── 3-1-1 옵션 받기 표 ──


def test_synthetic_options_are_accepted() -> None:
    binding().check_options(options())


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({}, "옵션 input이(가) 없어요"),
        (options(webSearch=False), "알 수 없는 옵션이에요: webSearch"),
        (options(maxCostUsd=1.0), "알 수 없는 옵션이에요: maxCostUsd"),
        (options(webSearch=True, maxCostUsd=1.0), "알 수 없는 옵션이에요: maxCostUsd, webSearch"),
        ({"input": changed(lambda x: x.update(extra=SECRET))}, "알 수 없는 옵션이에요: input.extra"),
        ({"input": changed(lambda x: x["company"].update(ceo=SECRET))}, "알 수 없는 옵션이에요: input.company.ceo"),
        ({"input": changed(lambda x: x.pop("company"))}, "옵션 input.company이(가) 없어요"),
        ({"input": changed(lambda x: x["company"].pop("name"))}, "옵션 input.company.name이(가) 없어요"),
        (
            {"input": changed(lambda x: x.update(schemaVersion="dataverify.input@2"))},
            "옵션 input.schemaVersion의 값이 맞지 않아요",
        ),
        (
            {"input": changed(lambda x: x["company"].update(reportingYear="24"))},
            "옵션 input.company.reportingYear의 값이 맞지 않아요",
        ),
        (
            {"input": changed(lambda x: first_item(x).update(values=[SECRET]))},
            "옵션 input.data.환경.values의 값이 맞지 않아요",
        ),
        ({"input": SECRET}, "옵션 input의 값이 맞지 않아요"),
        ([SECRET], "옵션 전체의 값이 맞지 않아요"),
    ],
    ids=[
        "empty",
        "webSearch",
        "maxCostUsd",
        "both",
        "input-extra",
        "company-extra",
        "company-missing",
        "name-missing",
        "schemaVersion",
        "reportingYear",
        "values-list",
        "input-text",
        "not-object",
    ],
)
def test_refused_options_say_one_sentence_with_key_paths_only(given: Any, message: str) -> None:
    said = refused(given)
    assert said == message
    assert SECRET not in said


def test_an_unknown_key_in_an_item_is_accepted() -> None:
    binding().check_options({"input": changed(lambda x: first_item(x).update(담당자="가상 담당자"))})


def test_a_value_planted_in_a_wrong_field_does_not_reach_the_sentence() -> None:
    said = refused({"input": changed(lambda x: x["company"].update(name=[SECRET]))})
    assert said == "옵션 input.company.name의 값이 맞지 않아요"
    assert SECRET not in said and "7f3a" not in said


# ── 3-1-2 같은 판정(shapes.check_input) ──

SAME_TABLE: list[Callable[[dict[str, Any]], None]] = [
    lambda x: None,
    lambda x: first_item(x).update(담당자="가상 담당자"),
    lambda x: x.update(extra=1),
    lambda x: x.pop("data"),
    lambda x: x.update(schemaVersion="dataverify.input@2"),
    lambda x: x["company"].update(reportingYear="2024년"),
    lambda x: x["company"].update(materialTopics="가상 토픽"),
    lambda x: first_item(x).update(values=[1]),
    lambda x: first_item(x).update(values={"2024": True}),
    lambda x: first_item(x).pop("메모"),
    lambda x: x.update(data={"환경": {}}),
    lambda x: x["company"].update(reportingYear=2024),
]


def _passes(call: Callable[[], object], error: type[Exception]) -> bool:
    try:
        call()
    except error:
        return False
    return True


@pytest.mark.parametrize("change", SAME_TABLE, ids=[str(n) for n in range(len(SAME_TABLE))])
def test_the_input_verdict_is_the_same_as_check_input(change: Callable[[dict[str, Any]], None]) -> None:
    given = changed(change)
    by_binding = _passes(lambda: accept_options({"input": copy.deepcopy(given)}), RunOptionsRejected)
    by_shapes = _passes(lambda: shapes.check_input(copy.deepcopy(given)), ValidationError)
    assert by_binding == by_shapes


def test_the_same_table_has_both_verdicts() -> None:
    verdicts = {_passes(lambda c=c: shapes.check_input(changed(c)), ValidationError) for c in SAME_TABLE}
    assert verdicts == {True, False}


# ── 3-1-3 inputs ──


def test_inputs_pass_the_received_input_as_is_with_the_company_tags() -> None:
    given = options()
    made = binding().inputs(given, company_id=42)
    assert made.received is given["input"]
    assert list(made.received) == ["schemaVersion", "company", "data"]
    assert made.tags == Tags(tenant="42", module="dataverify")
    assert made.max_cost_usd is STAGE_COSTS
    assert made.web_search is True
    assert (made.route, made.max_output_tokens) == ("standard-openai-41", 32_768)


def test_inputs_keep_the_item_key_order_of_the_received_input() -> None:
    item = {"메모": "", "ID": "E-001", **{k: v for k, v in first_item(received()).items() if k not in ("메모", "ID")}}
    given = changed(lambda x: x["data"].update(환경=[item]))
    made = binding().inputs({"input": given}, company_id=7)
    assert list(made.received["data"]["환경"][0])[:2] == ["메모", "ID"]


def test_inputs_refuse_options_that_do_not_fit() -> None:
    with pytest.raises(RunOptionsRejected):
        binding().inputs({}, company_id=1)


# ── 3-1-4 STAGE_COSTS 손값 ──


def test_the_stage_costs_are_one_three_one_usd() -> None:
    assert (STAGE_COSTS.plan, STAGE_COSTS.review, STAGE_COSTS.insight) == (1.0, 3.0, 1.0)
    assert colab_156.check_costs(STAGE_COSTS) is STAGE_COSTS


# ── 3-1-5 versions ──


def test_versions_are_engine_flow_prompt_ids_and_route() -> None:
    assert binding().versions(options()) == {
        "engine": "colab_156",
        "flow": "dataverify.colab@156",
        "promptIds": {"plan": "dataverify/plan@1", "review": "dataverify/review@1", "insight": "dataverify/insight@1"},
        "route": "standard-openai-41",
    }


def test_the_binding_has_the_facts_branch() -> None:
    assert isinstance(binding(), DocumentlessFactsBinding)  # DVA1 ③ — 판 열쇠를 박고 판으로 입력을 짓는 길


# ── 3-1-6 포트 꼴 ──


def _parameters(owner: object, name: str) -> list[tuple[str, Any]]:
    signature = inspect.signature(getattr(owner, name))
    return [(p.name, p.kind) for p in signature.parameters.values() if p.name != "self"]


@pytest.mark.parametrize("name", ["check_options", "inputs", "adapters", "versions"])
def test_the_binding_has_the_documentless_port_shape(name: str) -> None:
    assert _parameters(DataverifyBinding, name) == _parameters(DocumentlessBinding, name)
    assert "document" not in dict(_parameters(DataverifyBinding, name))


@dataclass
class FakeContext:
    """RunContext 꼴의 가짜. llm() 은 미리 지은 표시 객체를 돌려준다."""

    marker: object = field(default_factory=object)
    company_id: int = 9
    run_id: int = 1
    module: str = "dataverify"
    flow_id: str = "dataverify.colab@156"
    attempt: int = 1
    dry_run: bool = False
    asked: int = 0

    def llm(self) -> LlmClient:
        self.asked += 1
        return self.marker  # pyright: ignore[reportReturnType]

    def embedding(self) -> EmbeddingClient:
        raise AssertionError("데이터 검증은 임베딩을 쓰지 않는다")


def test_adapters_use_the_run_client() -> None:
    ctx = FakeContext()
    made = binding().adapters(ctx)
    assert made.llm is ctx.marker
    assert ctx.asked == 1


# ── DV1f 3-1-2 source 받기 표 ──

NAME = "가상출처파일-zq7x.json"
"""지은 파일 이름. 거절 문장에 이름 글자가 실리지 않는지는 SECRET 을 품은 이름으로 본다."""


def with_source(source: object) -> dict[str, Any]:
    return options(source=source)


@pytest.mark.parametrize(
    "source",
    [{"kind": "file", "name": NAME}, {"kind": "paste"}, {"kind": "file", "name": "가상 보고서 (1).JSON"}],
    ids=["file", "paste", "any-extension"],
)
def test_a_source_is_accepted(source: dict[str, Any]) -> None:
    given = with_source(source)
    assert accept_options(given) == given


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ({"kind": "paste", "name": SECRET}, "알 수 없는 옵션이에요: source.name"),
        ({"kind": "file"}, "옵션 source.name이(가) 없어요"),
        ({"kind": "file", "name": ""}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": (SECRET + "가" * 256)[:256]}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}/b.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}\\b.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}\x00.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}\x1f.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}\x7f.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}\x85.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}\u202enosj.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}\u2066.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": f"{SECRET}\u061c.json"}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "file", "name": 7}, "옵션 source.name의 값이 맞지 않아요"),
        ({"kind": "url", "name": SECRET}, "옵션 source의 값이 맞지 않아요"),
        ({"name": SECRET}, "옵션 source의 값이 맞지 않아요"),
        ({"kind": "file", "name": NAME, "path": SECRET}, "알 수 없는 옵션이에요: source.path"),
        ({"kind": "paste", "text": SECRET}, "알 수 없는 옵션이에요: source.text"),
        (SECRET, "옵션 source의 값이 맞지 않아요"),
        (None, "옵션 source의 값이 맞지 않아요"),
    ],
    ids=[
        "paste-with-name",
        "file-without-name",
        "empty-name",
        "256-chars",
        "slash",
        "backslash",
        "c0-nul",
        "c0-us",
        "del",
        "c1-nel",
        "bidi-rlo",
        "bidi-lri",
        "bidi-alm",
        "name-number",
        "unknown-kind",
        "no-kind",
        "file-extra-key",
        "paste-extra-key",
        "source-text",
        "source-null",
    ],
)
def test_refused_sources_say_one_sentence_without_the_name(source: object, message: str) -> None:
    said = refused(with_source(source))
    assert said == message
    assert SECRET not in said and "7f3a" not in said


def test_the_old_body_without_a_source_is_still_accepted() -> None:
    given = options()
    assert "source" not in given
    assert accept_options(given) == given


# ── DV1f 3-1-3 255자 경계(글자 수) ──


@pytest.mark.parametrize(("name", "fits"), [("가" * 255, True), ("가" * 256, False), ("😀" * 255, True), ("a", True)])
def test_the_name_length_counts_characters_up_to_255(name: str, fits: bool) -> None:
    given = with_source({"kind": "file", "name": name})
    assert _passes(lambda: accept_options(given), RunOptionsRejected) is fits


def test_the_accepted_name_is_kept_byte_for_byte() -> None:
    name = " 가상\u00a0이름\u200d.json "  # 앞뒤 빈칸·NBSP·ZWJ 는 거절 집합 밖 — 서버는 고치지 않는다
    given = with_source({"kind": "file", "name": name})
    assert accept_options(given) == given
    assert given["source"]["name"].encode("utf-8") == name.encode("utf-8")


# ── DV1f 3-1-4 흐름 그대로 ──


@pytest.mark.parametrize("source", [{"kind": "file", "name": NAME}, {"kind": "paste"}], ids=["file", "paste"])
def test_the_source_does_not_reach_the_flow_inputs_or_versions(source: dict[str, Any]) -> None:
    bare, given = options(), with_source(source)
    made = binding().inputs(given, company_id=42)
    assert made.received is given["input"]
    assert made == binding().inputs(bare, company_id=42)
    assert "source" not in made.received and NAME not in repr(made)
    assert binding().versions(given) == binding().versions(bare)
