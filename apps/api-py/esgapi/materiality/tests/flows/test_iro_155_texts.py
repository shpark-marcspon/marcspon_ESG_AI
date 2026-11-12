"""흐름이 템플릿 글·모델 칸 값을 입력에서 읽는가(밴드 IR4 §3-1 4·6 · §3-2): 칸마다 표지가 그 호출의 자리에만 · 신뢰
출처 칸은 sector 의 판만 · 1부 temperature·출력 상한과 2부 출력 상한이 입력 값 · 새 칸은 기본값이 없음(처분 Q13) ·
어림 셋도 입력 값. 기본 글의 바이트는 tests/engines/colab_155/test_texts.py 와 §4-6 지문이 본다. 공급사는 모의만.
"""

from dataclasses import fields, replace
from typing import Any

import pytest

from esgapi.core.flows.types import FlowInputError
from esgapi.core.llm.client import ToolCallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.materiality.engines.colab_155 import constants
from esgapi.materiality.flows import colab_155, iro_155, part2_155
from esgapi.materiality.flows.colab_155 import DEFAULT_TEXTS, PromptTexts, StageModel
from esgapi.materiality.tests.flows import support

SYSTEM_KEYS = {
    "regulation": {"regulation_system"},
    "keywords": {"keywords_system"},
    "controversy": {"controversy_system"},
    "impact": {"impact_system"},
    "financial": {"financial_system"},
    "pathway": {"pathway_system"},
}
USER_KEYS: dict[str, tuple[str, ...]] = {
    "regulation": ("regulation_prefix", "regulation_input"),
    "keywords": ("keywords_prefix", "keywords_input"),
    "controversy": ("controversy_prefix", "controversy_input"),
    "impact": ("impact_input",),
    "financial": ("financial_input",),
    "pathway": ("pathway_input",),
}
WHITELIST_KEY = {"financial": "whitelist_financial", "non_financial": "whitelist_non_financial"}


def mark(key: str) -> str:
    return f"⟦IR4-{key}⟧"


def marked() -> PromptTexts:
    """칸마다 끝에 표지를 붙인 판(자리는 그대로 — 끼움·dedent 는 기본과 같다)."""
    return replace(
        DEFAULT_TEXTS, **{f.name: getattr(DEFAULT_TEXTS, f.name) + mark(f.name) for f in fields(PromptTexts)}
    )


def phase_of(request: Any) -> str:
    return request.prompt.split("/")[1].split("@")[0]


def assert_marks_only_where_they_belong(requests: list[Any], sector: str) -> None:
    keys = [f.name for f in fields(PromptTexts)]
    seen: set[str] = set()
    for request in requests:
        phase = phase_of(request)
        system, user = request.vars["system"], request.vars["user"]
        in_system = SYSTEM_KEYS[phase] | ({WHITELIST_KEY[sector]} if phase == "regulation" else set[str]())
        for key in keys:
            assert (mark(key) in system) == (key in in_system), (phase, key, "system")
            assert (mark(key) in user) == (key in USER_KEYS[phase]), (phase, key, "user")
        if len(USER_KEYS[phase]) == 2:  # 1부: 접두는 user 의 앞, 가변 입력은 뒤
            prefix, variable = USER_KEYS[phase][0], USER_KEYS[phase][1]
            assert user.index(mark(prefix) + colab_155.USER_JOIN) < user.index(mark(variable))
        seen |= {key for key in keys if mark(key) in system + user}
    other = WHITELIST_KEY["financial" if sector == "non_financial" else "non_financial"]
    assert seen == set(keys) - {other}  # 열여섯 칸이 다 어딘가에 실리고, 다른 판 칸은 어디에도 없다


@pytest.mark.parametrize("sector", ["non_financial", "financial"])
@pytest.mark.parametrize("latest", [False, True], ids=["call", "latest"])
def test_each_cell_lands_in_its_own_call_only(sector: str, latest: bool) -> None:
    received = {**support.received2(latest=latest), "sector": sector}
    mock = MockProvider("openai")
    support.script_iro(mock, received)
    spy = support.spy2(mock)
    support.run_iro(support.iro_inputs(received, texts=marked()), spy)
    assert mock.pending == 0
    assert len(spy.requests) == 14  # 1부 다섯(규제 둘·키워드·사건 둘) + 2부 아홉
    assert_marks_only_where_they_belong(spy.requests, sector)


@pytest.mark.parametrize("latest", [False, True], ids=["call", "latest"])
def test_the_model_cells_drive_the_requests_and_the_result(latest: bool) -> None:
    received = support.received2(latest=latest)
    mock = MockProvider("openai")
    support.script_iro(mock, received)
    spy = support.spy2(mock)
    research = StageModel(route=colab_155.ROUTE, temperature=0.7, max_output_tokens=8_000)
    analysis = StageModel(route=part2_155.ROUTE_PART2, temperature=None, max_output_tokens=9_000)
    done = support.run_iro(support.iro_inputs(received, research=research, analysis=analysis), spy)
    part1 = [r for r in spy.requests if phase_of(r) in colab_155.PHASES]
    part2 = [r for r in spy.requests if phase_of(r) in part2_155.PHASES2]
    assert [(r.temperature, r.max_output_tokens) for r in part1] == [(0.7, 8_000)] * 5
    assert [(r.temperature, r.max_output_tokens) for r in part2] == [
        (None, 9_000)
    ] * 9  # 2부는 temperature 를 안 싣는다
    assert all(isinstance(r, ToolCallRequest) == latest for r in part2)
    settings = support.result(done)["settings"]
    assert (settings["temperature"], settings["part2"]["maxOutputTokens"]) == ("0.7", 9_000)


def test_the_estimate_reads_the_texts_and_the_model_cells() -> None:
    received = support.received2()
    mock = MockProvider("openai")
    spy = support.spy2(mock)
    research = StageModel(route=colab_155.ROUTE, temperature=0.3, max_output_tokens=7_000)
    analysis = StageModel(route=part2_155.ROUTE_PART2, temperature=None, max_output_tokens=6_000)
    got = iro_155.estimate_iro(support.iro_inputs(received, texts=marked(), research=research, analysis=analysis), spy)
    phases = [phase_of(r) for r in spy.dry_runs]
    assert phases[:5] == ["regulation"] * 2 + ["keywords"] + ["controversy"] * 2
    for request in spy.dry_runs:
        system, user = request.vars["system"], request.vars["user"]
        phase = phase_of(request)
        assert all(mark(key) in system for key in SYSTEM_KEYS[phase])
        assert all(mark(key) in user for key in USER_KEYS[phase])
        if phase in colab_155.PHASES:
            assert (request.temperature, request.max_output_tokens) == (0.3, 7_000)
        else:
            assert (request.temperature, request.max_output_tokens) == (None, 6_000)
    assert {phase_of(r) for r in spy.dry_runs} == {*colab_155.PHASES, *part2_155.PHASES2}
    assert "호출마다 출력 상한(7,000)을 다 쓴다고 본 위끝" in got["assumptions"][0]
    assert any("출력 상한(6,000)" in line for line in got["assumptions"])


def test_the_part1_temperature_must_be_a_number() -> None:
    research = StageModel(route=colab_155.ROUTE, temperature=None, max_output_tokens=8_000)
    with pytest.raises(FlowInputError, match="temperature"):
        iro_155.part1_inputs(support.iro_inputs(research=research))


def test_the_new_cells_have_no_defaults() -> None:
    """처분 Q13 (가): 빠뜨리면 TypeError — 기본 글로 조용히 도는 길이 없다."""
    with pytest.raises(TypeError, match="texts"):
        colab_155.MaterialityInputs(
            received=support.received(),
            tags=support.TAGS,
            max_cost_usd=support.COST,
            temperature=0.1,
            max_output_tokens=16_384,
        )  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError, match="max_output_tokens"):
        part2_155.Part2Inputs(tags=support.TAGS, max_cost_usd=support.COST, texts=DEFAULT_TEXTS)  # pyright: ignore[reportCallIssue]
    for missing in ("texts", "research", "analysis"):
        given: dict[str, Any] = {
            "received": support.received2(),
            "tags": support.TAGS,
            "max_cost_usd": support.COST,
            "today": support.TODAY,
            **support.IRO_CODE,
        }
        del given[missing]
        with pytest.raises(TypeError, match=missing):
            iro_155.IroInputs(**given)


def test_the_code_values_are_the_flow_constants() -> None:
    assert (
        StageModel(
            route=colab_155.ROUTE, temperature=constants.TEMPERATURE, max_output_tokens=colab_155.MAX_OUTPUT_TOKENS
        )
        == colab_155.CODE_RESEARCH
    )
    assert (
        StageModel(route=part2_155.ROUTE_PART2, temperature=None, max_output_tokens=part2_155.MAX_OUTPUT_TOKENS_PART2)
        == part2_155.CODE_ANALYSIS
    )
    made = support.iro_inputs()
    assert (made.route1, made.route2) == (colab_155.ROUTE, part2_155.ROUTE_PART2)  # 읽기 이름(IR4 앞과 같다)


def test_the_binding_feeds_the_code_texts_and_models() -> None:
    """실행 길(binding)이 엔진에 넘기는 칸 셋이 코드 값이다 — 기본 글·리서치·분석 코드 모델(① 검증 권고 R1)."""
    made = support.binding().inputs(support.options(), company_id=1)
    assert (made.texts, made.research, made.analysis) == (
        DEFAULT_TEXTS,
        colab_155.CODE_RESEARCH,
        part2_155.CODE_ANALYSIS,
    )
