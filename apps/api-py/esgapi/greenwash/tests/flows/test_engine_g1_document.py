"""흐름 greenwash.engine@G1 의 문서 포트와 ③ 업무 지식 칸(밴드 GE1b ② T12·T13 — B3 · MARC-ENT-651). 순수(DB 0).
문서는 지어낸 산출물 JSON(JsonDocument). 글은 지어낸 것.
"""

import json
from dataclasses import replace
from typing import Any, cast

import pytest

from esgapi.core.documents.contract import ArtifactRef, ArtifactRefused, ArtifactUnreadable
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowStepFailed
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderRequest, ProviderResponse
from esgapi.greenwash.engines.g1 import judge as jd
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.tests.flows.test_engine_g1_flow import (
    Answering,
    JsonDocument,
    adapters,
    inputs,
    result_of,
)


def judge_texts(provider: Answering) -> list[str]:
    return [
        repr(c)  # 요청 전체(system·user)의 글
        for c in provider.calls
        if c.json_schema is not None and c.json_schema.name == "judge"
    ]


# ── T12 ③ 칸이 판정 글로 ──


def test_a_changed_criterion_line_changes_the_judge_request() -> None:
    lines = E.default_criterion_lines()
    changed = (replace(lines[0], text="가상 기준 글 하나를 바꾼 줄"), *lines[1:])
    plain, other = Answering(), Answering()
    run_flow(E.g1_flow(), inputs(), adapters(plain))
    run_flow(E.g1_flow(), replace(inputs(), criteria=changed), adapters(other))
    assert all("가상 기준 글 하나를 바꾼 줄" in t for t in judge_texts(other))
    assert not any("가상 기준 글 하나를 바꾼 줄" in t for t in judge_texts(plain))
    assert all(lines[0].text not in t for t in judge_texts(other))


class Categorized(Answering):
    """판정 답의 category 를 「가상 갈래」로."""

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        got = super().invoke(request, options)
        if request.json_schema is None or request.json_schema.name != "judge" or not isinstance(got, Completed):
            return got
        return Completed(text=json.dumps({**json.loads(got.text), "category": "가상 갈래"}), usage=got.usage)


def test_categories_reach_the_prompt_and_the_category_check() -> None:
    """판의 카테고리 목록이 판정 글에 실리고, 판정의 category 가 그 목록 안이면 검사 pass(기본 빈 목록이면 fail)."""
    assert {i["errorCode"] for i in items_of(Categorized(), ())} == {"category_unknown"}
    provider = Categorized()
    result = result_of(run_flow(E.g1_flow(), replace(inputs(), categories=("가상 갈래",)), adapters(provider)))
    assert all("가상 갈래" in t for t in judge_texts(provider))
    assert {i["checks"]["categoryInList"] for s in result["segments"] for i in s["items"]} == {"pass"}


def items_of(provider: Answering, categories: tuple[str, ...]) -> list[dict[str, Any]]:
    result = result_of(run_flow(E.g1_flow(), replace(inputs(), categories=categories), adapters(provider)))
    return [i for s in result["segments"] for i in s["items"]]


@pytest.mark.parametrize(
    "bad",
    [
        {"criteria": ()},
        {"criteria": tuple(E.default_criterion_lines()) * 2},
        {"criteria": (jd.CriterionLine(id="x" * 25, group="high", text="가상"),)},
        {"criteria": (jd.CriterionLine(id="x", group="nogroup", text="가상"),)},
        {"criteria": (jd.CriterionLine(id="x", group="high", text="두\n줄"),)},
        {"criteria": (jd.CriterionLine(id="x", group="high", text="가" * 301),)},
        {"categories": ("", "가상")},
        {"categories": ("가상", "가상")},
        {"variant": "financial"},
    ],
)
def test_the_third_layer_fields_refuse_bad_shapes(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        E.G1Inputs(parts={"ceo": (1,), "company": (), "climate": ()}, **bad)


# ── T13 문서 포트 ──


class Refusing(JsonDocument):
    def __init__(self, answer: ArtifactRefused | ArtifactUnreadable) -> None:
        super().__init__()
        self.answer = answer
        self.viewed = 0

    def ensure(self) -> Any:
        self.ensured += 1
        return self.answer

    def view(self, ref: ArtifactRef) -> Any:
        self.viewed += 1
        return super().view(ref)


@pytest.mark.parametrize("answer", [ArtifactRefused("too_many_pages"), ArtifactUnreadable("object_changed")])
def test_a_refused_or_unreadable_document_fails_extract_and_reads_nothing_after(
    answer: ArtifactRefused | ArtifactUnreadable,
) -> None:
    doc = Refusing(answer)
    with pytest.raises(FlowStepFailed) as got:
        run_flow(E.g1_flow(), inputs(), replace(adapters(), document=doc))
    assert got.value.step == "extract"
    assert isinstance(got.value.__cause__, E.G1DocumentFailed) and got.value.__cause__.code == answer.code
    assert (doc.ensured, doc.viewed) == (1, 0)  # 뒤 단계 파싱·뷰 0회


def test_the_extract_data_names_the_artifact_without_db_ids() -> None:
    run = run_flow(E.g1_flow(), inputs(), adapters())
    data = run.steps["extract"].data
    assert {k: data[k] for k in ("sha256", "parserVersion", "pageCount", "fileName")} == {
        "sha256": "a" * 64,
        "parserVersion": JsonDocument().ensure().parser.version,
        "pageCount": 4,
        "fileName": "document.pdf",
    }
    assert not {k for k in data if k.lower().endswith("id")}
    assert result_of(run)["source"] == {"fileName": "document.pdf", "sha256": "a" * 64, "pageCount": 4}


class Changing(JsonDocument):
    """두 번째 ensure 부터 다른 sha(what="sha") 또는 같은 sha·다른 parserVersion(what="parser")의 산출물."""

    def __init__(self, what: str = "sha") -> None:
        super().__init__()
        self.what = what

    def ensure(self) -> Any:
        ref = cast("ArtifactRef", super().ensure())
        if self.ensured == 1:
            return ref
        if self.what == "sha":
            return replace(ref, source_sha256="b" * 64)
        return replace(ref, parser=replace(ref.parser, version=ref.parser.version + "-next"))


@pytest.mark.parametrize("what", ["sha", "parser"])
def test_a_changed_artifact_after_extract_is_a_named_failure(what: str) -> None:
    """sha 만 바뀜·parserVersion 만 바뀜이 각각 G1ArtifactChanged(검증 2 권고 1 — critic B3 의 두 칸)."""
    with pytest.raises(FlowStepFailed) as got:
        run_flow(E.g1_flow(), inputs(), replace(adapters(), document=Changing(what)))
    assert got.value.step == "index"
    assert isinstance(got.value.__cause__, E.G1ArtifactChanged)


def test_every_later_step_and_segment_asks_the_port_again() -> None:
    doc = JsonDocument()
    run = run_flow(E.g1_flow(), inputs(), replace(adapters(), document=doc))
    segments = len(cast("list[object]", run.steps["judge"].data["segments"]))
    assert doc.ensured == 3 + segments  # extract · index · candidates + 구획마다
