"""흐름 materiality.colab@155 — 중대성평가 IRO 코랩 1부(셀 17 규제·정책 조사, 셀 20 컨트로버시 키워드, 셀 22 컨트로버시
조사)의 셀 8 러너 호출을 core.llm 의 도구 호출 고리(`LlmClient.call_tools` — web_search 하나, 걸음 1) 위에서 돈다
(밴드 IR1b, MARC-ENT-425 ①).

    load → regulation → keywords → controversy → report

입력 꼴 materiality.input@1(MaterialityInputs.received), 결과 꼴 materiality.result@1(contracts/shapes.py), 출력 파일
materiality-websearch.xlsx. 엔진(engines/colab_155)과 계약(contracts)·출력(outputs)을 잇는 유일한 자리다. 차례는 코랩
셀 차례다(규제 전부 → 키워드 → 컨트로버시 전부, MARC-ENT-196).

- load         입력 꼴 검사·실행 비용 상한 검사(틀리면 FlowInputError — 공급사 호출 0), 출처 목록 판, 서브토픽 경고.
- regulation   토픽마다 한 번(system = 규제 system [8] 판, user = 접두 + USER_JOIN + 가변).
- keywords     한 번(기간은 이 호출에만 간다 — 코랩대로).
- controversy  키워드 답을 다시 읽어 토픽마다 키워드 글을 짓고 토픽마다 한 번. 키워드가 실패·못 읽음이면 전부
               「(키워드 없음)」(코랩은 셀 20 이 멈춘다 — IR1a 처분 ⑩).
- report       묶음 → 결과 칸(contracts/wire) → 결과 꼴 검사(못 지나면 FlowOutputError — 흐름의 결함) → JSON 판
               (dump_json — NaN·Infinity 는 null) → 엑셀.

호출 하나(run_call)의 갈래: 끝남 → 답 글. 잘림(CutOff) → 같은 요청을 한 번 더(코랩 셀 8 의 incomplete 재시도), 둘째도
잘리면 그 부분 글을 답 글로 쓰고 failure truncated. 거부·공급사 오류·시간 초과·상한·실행기 예외 → 답 글 없음(재시도
없음). 부분(걸음 1 에서 모델이 함수를 부름 — web_search 하나뿐이라 닿지 않아야 한다) → provider_error. 실패 message 는
갈래 이름과 상한의 자리·공급사 상태 번호까지만 — 모델 글·공급사 메시지를 싣지 않는다.

실행 비용 상한(max_cost_usd, 실행 하나): 재시도를 포함한 공급사 호출마다 그 앞에서, 앞 호출들의 비용
(meta.attempts[*].cost_usd 합, None 은 0) 이 상한 이상이면 부르지 않는다(failed·budget_exceeded (run), 뒤도 같다).
닿으면 막는 문이라 보장은 「지출 ≤ 상한 + 호출 하나」다. core 고리의 max_cost_usd 는 걸음 앞에서만 보므로 걸음 1 에서는
막지 못해 싣지 않는다. 잘린 답의 web_search 건수 요금은 core 가 세지 않는다(그 몫은 누계에 없다).

단계 안 진행(밴드 IRW6, MARC-ISSUE-378): regulation·controversy 는 토픽마다 checkpoint(done = 끝난 토픽 수,
total = 토픽 수, 부분 산출물 = 그 단계 data 꼴의 앞부분)를 내고 resume 이 오면 끝난 토픽을 건너뛴다
(flows/progress_155). keywords 는 호출 하나라 내지 않는다. resume 없이 checkpoint 만 내면 안 된다 — 실행기가
checkpoint 뒤마다 양보하고 진행 있는 시도는 상한에 세지 않아, 시도마다 처음부터 같은 호출을 되풀이한다(progress_155
머리).

단계는 순수 함수다: 앞 단계의 산출물은 carried[<이름>].data(JSON 왕복한 값)에서만 읽고, 중간 단계 data 는 글·수·
failure 만 싣는다(모델의 JSON 은 report 가 다시 읽는다 — NaN 이 단계 왕복을 깨지 않게, MARC-ISSUE-345 1).
estimate 는 공급사를 부르지 않는 비용 위끝 어림이다(core 의 dry_run_tools — 견본 실행 IRL 의 재료).
이 파일은 설정·환경 변수·키를 읽지 않고 SDK 클라이언트를 짓지 않는다. 클라이언트는 부르는 쪽이 지어
MaterialityAdapters 로 넘긴다. 전역 레지스트리에 다는 것과 실행기 끼움은 IR3a 의 apps.py·binding_155 다.
"""

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Literal, Protocol, cast

from pydantic import ValidationError

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import (
    Carried,
    FlowInputError,
    FlowOutputError,
    FlowStep,
    OutputFile,
    StepContext,
    StepOutput,
)
from esgapi.core.llm.client import ToolCallRequest
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.types import (
    ApproximateLocation,
    CutOff,
    DryRunReport,
    ProviderFailed,
    Tags,
    ToolExecutor,
    ToolLoopDone,
    ToolLoopFailed,
    ToolLoopPartial,
    ToolLoopResult,
    WebSearchTool,
)
from esgapi.materiality.contracts import shapes, wire
from esgapi.materiality.engines.colab_155 import constants, outcomes, parsing, prompts, whitelists
from esgapi.materiality.engines.colab_155.inputs import industry_text, resolve_subtopics
from esgapi.materiality.engines.colab_155.texts import DEFAULT_TEXTS as DEFAULT_TEXTS
from esgapi.materiality.engines.colab_155.texts import PromptTexts as PromptTexts
from esgapi.materiality.engines.colab_155.texts import whitelist_text
from esgapi.materiality.flows import progress_155
from esgapi.materiality.outputs import xlsx

FLOW_ID: Final = "materiality.colab@155"
Phase = Literal["regulation", "keywords", "controversy"]
PHASES: Final[tuple[Phase, ...]] = ("regulation", "keywords", "controversy")

ROUTE: Final = "standard-openai-4o"
"""core/llm/data/models.json 의 경로 이름(gpt-4o 하나 — 코랩 셀 11 model, constants.MODEL)."""
PROMPT_IDS: Final[Mapping[Phase, str]] = {phase: f"materiality/{phase}@1" for phase in PHASES}
"""단계 → core.llm 프롬프트 id(봉투 prompts/<단계>/1.md — `=== system ===` {{system}} `=== user ===` {{user}})."""
USER_JOIN: Final = "\n\n"
"""코랩은 user 메시지 둘(접두 — 고정, 가변)을 보낸다. core 의 요청은 user 하나라 접두 + 이 글 + 가변으로
잇는다(처분 ②)."""
MAX_OUTPUT_TOKENS: Final = 16_384
"""걸음마다의 출력 상한. 코랩은 주지 않는다(공급사 기본) — core 의 기본(4,096) 대신 gpt-4o 의 상한을 넘겨 근사한다
(models.json 의 gpt-4o maxOutputTokens, 출처 줄 「16,384 max output tokens」 2026-10-23 확인)."""
TIMEOUT_MS: Final = 600_000
"""호출의 시간 한도. 코랩은 주지 않는다 — SDK 기본 600초(openai _constants.py DEFAULT_TIMEOUT)."""
MAX_STEPS: Final = 1
TOOL_CHOICE: Final = "auto"
SYSTEM_PLACEMENT: Final = "input_message"
"""코랩 셀 8 의 몸: tool_choice auto·system 은 input 의 메시지·temperature constants.TEMPERATURE. 병렬 호출 칸은
없다."""
NO_COST: Final = 0.0
RUN_MAX_COST_USD: Final = 5.0
"""실행 하나(1부 + 2부)의 비용 상한(USD). MARC-ENT-262 의 한 번 5 USD 선 — 보장은 「지출 ≤ 상한 + 호출 하나」
(IR3a 처분 ⑥). 무효 조건: 실호출을 켜는 밴드(runs/context.py 가 키를 싣는 때 — LLM_RUN_MAX_USD 가 둘째 문)가 오면
그 발주서에서 다시 정한다. 이 한 자리에서 정의하고 binding_155 는 다시 내보낸다(MARC-ISSUE-412 ①, 밴드 IRS1)."""


def web_search(user_location: str) -> WebSearchTool:
    """코랩 셀 8 의 web_search(search_context_size low, user_location approximate·입력의 userLocation)."""
    return WebSearchTool(
        search_context_size=constants.SEARCH_CONTEXT_SIZE, user_location=ApproximateLocation(country=user_location)
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class StageModel:
    """모델 칸 하나의 값(밴드 IR4 — AI 설정 판의 research·analysis 칸이 흐름에 오는 꼴). temperature None = 안 실음."""

    route: str
    temperature: float | None
    max_output_tokens: int


CODE_RESEARCH: Final = StageModel(route=ROUTE, temperature=constants.TEMPERATURE, max_output_tokens=MAX_OUTPUT_TOKENS)
"""1부(리서치 모델 칸)의 코드 값 — 기본 판·옛 실행."""


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterialityInputs:
    """흐름의 입력.

    received           materiality.input@1 의 받은 dict 그대로(검사만 하고 고치지 않는다 — IR1a §1-8)
    tags               core.llm 의 기록·비용 꼬리표(테넌트, 모듈 materiality)
    max_cost_usd       실행 하나의 비용 상한(USD, 0 보다 큰 유한한 수. 기본값 없음 — 처분 ⑦)
    route              경로 이름(모델 하나, 도구 고리를 지나는 모델)
    texts              템플릿 글(IR4 — 기본값 없음, 기본 글은 DEFAULT_TEXTS)
    temperature        호출마다의 temperature(IR4 — 코드 값 constants.TEMPERATURE)
    max_output_tokens  걸음마다의 출력 상한(IR4 — 코드 값 MAX_OUTPUT_TOKENS)
    """

    received: Mapping[str, Any]
    tags: Tags
    max_cost_usd: float
    route: str = ROUTE
    texts: PromptTexts
    temperature: float
    max_output_tokens: int


class ToolLoopLlm(Protocol):
    """흐름이 쓰는 core.llm 의 입구(LlmClient 가 그대로 맞는다)."""

    def call_tools(self, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult: ...

    def dry_run_tools(self, request: ToolCallRequest) -> DryRunReport: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterialityAdapters:
    """흐름의 어댑터. llm 은 부르는 쪽이 지은 클라이언트(실호출·모의는 부르는 쪽이 고른다)."""

    llm: ToolLoopLlm


# ── 호출 하나 ───────────────────────────────────────────────────────────────────────────────


def call_request(
    *, phase: Phase, system: str, prefix: str, variable: str, inputs: MaterialityInputs
) -> ToolCallRequest:
    """호출 하나의 요청(코랩 셀 8 run_web_search_prompt 의 몸을 core 의 칸으로)."""
    return ToolCallRequest(
        prompt=PROMPT_IDS[phase],
        route=inputs.route,
        tags=inputs.tags,
        tools=(web_search(inputs.received["userLocation"]),),
        max_steps=MAX_STEPS,
        vars={"system": system, "user": prefix + USER_JOIN + variable},
        max_output_tokens=inputs.max_output_tokens,
        timeout_ms=TIMEOUT_MS,
        temperature=inputs.temperature,
        tool_choice=TOOL_CHOICE,
        system_placement=SYSTEM_PLACEMENT,
    )


def no_function(name: str, arguments: str) -> str:
    """실행 함수 — 함수 도구를 주지 않아 닿지 않는다(닿으면 core 가 tool_executor_raised 로 돌려준다)."""
    raise RuntimeError(f"함수 도구는 없다: {name}")


@dataclass(frozen=True, slots=True)
class Called:
    """호출 하나의 끝: 답 글(없으면 None)·실패(없으면 None)·이 호출 뒤 실행 누계·기록 한 줄."""

    text: str | None
    failure: shapes.MaterialityFailure | None
    spent: float
    record: dict[str, Any]


def _cost(result: ToolLoopResult) -> float:
    return sum(attempt.cost_usd or NO_COST for attempt in result.meta.attempts)


def _hosted(result: ToolLoopResult) -> int:
    if isinstance(result, ToolLoopDone | ToolLoopPartial):
        return result.hosted_calls
    return sum(step.hosted_calls for step in result.steps)


def _model(results: Sequence[ToolLoopResult]) -> str | None:
    attempts = [attempt for result in results for attempt in result.meta.attempts]
    return attempts[-1].model if attempts else None


def failure_message(result: ToolLoopFailed) -> str:
    """실패 갈래(+ 상한의 자리, 공급사 상태). 모델 글·공급사 메시지는 싣지 않는다(dataverify flows 의 판별 복사 —
    실행기 예외의 도구 이름은 뺀다: 함수 도구가 없다)."""
    failure = result.failure
    message = failure.kind
    if result.budget_source is not None:
        message += f" ({result.budget_source})"
    if isinstance(failure, ProviderFailed):
        message += f" status={'none' if failure.status is None else failure.status}"
    return message


def failure_of(kind: shapes.FailureKind, message: str) -> shapes.MaterialityFailure:
    return {"kind": kind, "message": message}


def run_call(
    llm: ToolLoopLlm,
    *,
    phase: Phase,
    topic: str | None,
    system: str,
    prefix: str,
    variable: str,
    inputs: MaterialityInputs,
    spent: float,
) -> Called:
    """호출 하나(재시도 포함). 공급사 호출마다 그 앞에서 실행 누계를 상한에 견준다(처분 ⑦)."""
    request = call_request(phase=phase, system=system, prefix=prefix, variable=variable, inputs=inputs)
    results: list[ToolLoopResult] = []
    text: str | None = None
    failure: shapes.MaterialityFailure | None = None
    ending = "budget_exceeded"
    for attempt in range(1 + constants.RETRY_ON_INCOMPLETE):
        if spent >= inputs.max_cost_usd:
            text, failure, ending = None, failure_of("budget_exceeded", "budget_exceeded (run)"), "budget_exceeded"
            break
        result = llm.call_tools(request, no_function)
        results.append(result)
        spent += _cost(result)
        match result:
            case ToolLoopDone():
                text, failure, ending = result.text, None, "done"
                break
            case ToolLoopPartial():
                text, ending = None, "partial"
                failure = failure_of("provider_error", "provider_error unexpected_function_call")
                break
            case ToolLoopFailed(failure=CutOff()) if attempt < constants.RETRY_ON_INCOMPLETE:
                continue  # 코랩 셀 8: incomplete 면 같은 요청을 한 번 더
            case ToolLoopFailed(failure=CutOff() as cut):
                text, failure, ending = cut.partial_text, failure_of("truncated", "truncated"), "truncated"
                break
            case ToolLoopFailed():
                kind = cast("shapes.FailureKind", result.failure.kind)
                text, failure, ending = None, failure_of(kind, failure_message(result)), kind
                break
    record = {
        "phase": phase,
        "topic": topic,
        "ending": ending,
        "hostedCalls": sum(_hosted(result) for result in results),
        "costUsd": round_usd(sum(_cost(result) for result in results)),
        "model": _model(results),
        "attempts": len(results),
    }
    return Called(text=text, failure=failure, spent=spent, record=record)


# ── 단계 ───────────────────────────────────────────────────────────────────────────────────


def _cost_ok(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float) and math.isfinite(value) and value > 0


def check_cost(value: object) -> float:
    """실행 비용 상한(bool 아닌 유한한 수 > 0). 아니면 FlowInputError."""
    if not _cost_ok(value):
        raise FlowInputError(f"max_cost_usd 는 0 보다 큰 유한한 수여야 한다: {value!r}")
    return cast("float", value)


def check_received(received: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        return shapes.check_input(received)
    except ValidationError as error:
        raise FlowInputError(f"입력이 {shapes.INPUT_SHAPE} 꼴이 아니다: {error.error_count()} errors") from None


def _load(inputs: MaterialityInputs, adapters: MaterialityAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    received = check_received(inputs.received)
    check_cost(inputs.max_cost_usd)
    name, _ = whitelists.whitelist_for(received["sector"])
    _, pairs = resolve_subtopics(wire.engine_subtopics(received), wire.engine_topics(received))
    return StepOutput(data={"whitelist": name, "warnings": list(wire.subtopic_warnings(pairs))})


def _spent(carried: Carried, phase: Phase) -> float:
    """앞 단계까지의 실행 누계(USD). 규제가 첫 돈 단계다."""
    before = PHASES.index(phase)
    return NO_COST if before == 0 else cast("float", carried[PHASES[before - 1]].data["spentUsd"])


@dataclass(frozen=True, slots=True)
class Message:
    """호출 하나의 글(코랩 셀 8 의 system·user 접두·user 가변)과 그 자리(단계·토픽)."""

    phase: Phase
    topic: str | None
    system: str
    prefix: str
    variable: str


def regulation_messages(received: Mapping[str, Any], *, texts: PromptTexts) -> list[Message]:
    """셀 17: 토픽마다 규제 system([8] 판은 sector 로 고른 신뢰 출처 칸 글)·접두·가변."""
    name, _ = whitelists.whitelist_for(received["sector"])
    system = prompts.render(texts.regulation_system, {prompts.WHITELIST_SLOT: whitelist_text(texts, name)})
    industry = industry_text(wire.engine_industry(received))
    return [
        Message(
            "regulation",
            t["topic"],
            system,
            texts.regulation_prefix,
            prompts.regulation_user(
                t["topic"], t["description"], industry, received["geoScope"], received["mainLanguage"], texts=texts
            ),
        )
        for t in wire.engine_topics(received)
    ]


def keywords_message(received: Mapping[str, Any], *, texts: PromptTexts) -> Message:
    """셀 20: 키워드 한 번(기간은 이 호출에만 간다)."""
    variable = prompts.keywords_user(
        wire.engine_industry(received),
        received["dateRange"],
        received["mainLanguage"],
        wire.engine_topics(received),
        texts=texts,
    )
    return Message("keywords", None, texts.keywords_system, texts.keywords_prefix, variable)


def controversy_messages(
    received: Mapping[str, Any], by_topic: Mapping[str, list[str]], *, texts: PromptTexts
) -> list[Message]:
    """셀 22: 토픽마다 컨트로버시 system·접두·가변(키워드 글은 by_topic 에서 — 없으면 「(키워드 없음)」)."""
    industry = wire.engine_industry(received)
    return [
        Message(
            "controversy",
            t["topic"],
            texts.controversy_system,
            texts.controversy_prefix,
            prompts.controversy_user(
                t["topic"],
                t["description"],
                industry,
                received["geoScope"],
                received["mainLanguage"],
                parsing.keyword_str(by_topic, t["topic"]),
                texts=texts,
            ),
        )
        for t in wire.engine_topics(received)
    ]


def call_message(llm: ToolLoopLlm, message: Message, inputs: MaterialityInputs, spent: float) -> Called:
    return run_call(
        llm,
        phase=message.phase,
        topic=message.topic,
        system=message.system,
        prefix=message.prefix,
        variable=message.variable,
        inputs=inputs,
        spent=spent,
    )


def _regulation(
    inputs: MaterialityInputs, adapters: MaterialityAdapters, carried: Carried, ctx: StepContext
) -> StepOutput:
    """셀 17: 토픽마다 규제·정책 조사(토픽마다 checkpoint, resume 이면 끝난 토픽을 건너뜀)."""
    messages = regulation_messages(inputs.received, texts=inputs.texts)
    p = progress_155.start(ctx, [(cast("str", m.topic),) for m in messages], _spent(carried, "regulation"))
    for message in messages[len(p.answers) :]:
        called = call_message(adapters.llm, message, inputs, p.spent)
        p.add({"topic": message.topic, "text": called.text, "failure": called.failure}, called.record, called.spent)
    return StepOutput(data=p.data())


def _keywords(
    inputs: MaterialityInputs, adapters: MaterialityAdapters, carried: Carried, ctx: StepContext
) -> StepOutput:
    """셀 20: 컨트로버시 키워드 한 번."""
    called = call_message(
        adapters.llm, keywords_message(inputs.received, texts=inputs.texts), inputs, _spent(carried, "keywords")
    )
    return StepOutput(
        data={"text": called.text, "failure": called.failure, "calls": [called.record], "spentUsd": called.spent}
    )


def keywords_by_topic(text: str | None) -> dict[str, list[str]]:
    """키워드 답 글 → 토픽별 키워드. 호출 실패·못 읽음이면 빈 dict(토픽마다 「(키워드 없음)」 — IR1a 처분 ⑩)."""
    if text is None:
        return {}
    parsed = parsing.parse_keywords(text)
    return parsed.by_topic if isinstance(parsed, parsing.KeywordsParsed) else {}


def _controversy(
    inputs: MaterialityInputs, adapters: MaterialityAdapters, carried: Carried, ctx: StepContext
) -> StepOutput:
    """셀 22: 토픽마다 컨트로버시 조사(키워드 글은 셀 20 의 답에서. 토픽마다 checkpoint·resume — regulation 과 같다)."""
    by_topic = keywords_by_topic(cast("str | None", carried["keywords"].data["text"]))
    messages = controversy_messages(inputs.received, by_topic, texts=inputs.texts)
    p = progress_155.start(ctx, [(cast("str", m.topic),) for m in messages], _spent(carried, "controversy"))
    for message in messages[len(p.answers) :]:
        called = call_message(adapters.llm, message, inputs, p.spent)
        keyword_str = parsing.keyword_str(by_topic, cast("str", message.topic))
        p.add(
            {"topic": message.topic, "keywordStr": keyword_str, "text": called.text, "failure": called.failure},
            called.record,
            called.spent,
        )
    return StepOutput(data=p.data())


def keywords_outcome(text: str | None, failure: shapes.MaterialityFailure | None) -> tuple[dict[str, Any], list[Any]]:
    """키워드 답 → 결과 칸과 경고. 호출 실패면 raw null·core 갈래, 못 읽으면 raw 그대로·unparsable(엔진의 까닭) — 잘린
    답을 못 읽으면 failure 는 truncated 그대로."""
    if text is None:
        return dict(wire.keywords_failed(None, failure=failure)), []
    parsed = parsing.parse_keywords(text)
    if isinstance(parsed, parsing.KeywordsParsed):
        return dict(wire.keywords_done(parsed.by_topic, text)), list(wire.duplicate_keyword_warnings(parsed.duplicates))
    return dict(wire.keywords_failed(text, failure=failure, reason=parsed.reason)), []


def _report(inputs: MaterialityInputs, adapters: MaterialityAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    received = inputs.received
    load = carried["load"].data
    regulation = cast("list[dict[str, Any]]", carried["regulation"].data["answers"])
    keywords = carried["keywords"].data
    controversy = cast("list[dict[str, Any]]", carried["controversy"].data["answers"])
    warnings: list[Any] = list(cast("list[Any]", load["warnings"]))

    regulation_outcomes: list[wire.Outcome] = []
    for answer in regulation:
        outcome, more = wire.regulation_outcome(
            outcomes.regulation_bundle(answer["text"]), answer["topic"], failure=answer["failure"]
        )
        regulation_outcomes.append(outcome)
        warnings += more
    keywords_cell, more = keywords_outcome(
        cast("str | None", keywords["text"]), cast("shapes.MaterialityFailure | None", keywords["failure"])
    )
    warnings += more
    topics: list[shapes.MaterialityTopicResult] = []
    for t, reg, answer in zip(wire.engine_topics(received), regulation_outcomes, controversy, strict=True):
        con, more = wire.controversy_outcome(
            outcomes.controversy_bundle(answer["text"], t["topic"]), t["topic"], failure=answer["failure"]
        )
        warnings += more
        topics.append(wire.topic_result(t, keyword_str=answer["keywordStr"], regulation=reg, controversy=con))

    calls = [call for phase in PHASES for call in cast("list[dict[str, Any]]", carried[phase].data["calls"])]
    models = [cast("str", call["model"]) for call in calls if call["model"] is not None]
    settings: shapes.MaterialitySettings = {
        "model": models[-1] if models else None,
        "temperature": repr(inputs.temperature),
        "searchContextSize": constants.SEARCH_CONTEXT_SIZE,
        "promptIds": {
            "regulation": PROMPT_IDS["regulation"],
            "keywords": PROMPT_IDS["keywords"],
            "controversy": PROMPT_IDS["controversy"],
        },
    }
    result = wire.build_result(
        received,
        whitelist=cast("shapes.Whitelist", load["whitelist"]),
        settings=settings,
        keywords=keywords_cell,
        topics=topics,
        warnings=warnings,
    )
    adapter = shapes.RESULT_SHAPES[shapes.RESULT_SHAPE]
    try:
        adapter.validate_python(result, strict=True)
    except ValidationError as error:
        raise FlowOutputError(
            f"결과가 {shapes.RESULT_SHAPE} 꼴을 지나지 못했다: {error.error_count()} errors"
        ) from None
    # JSON 판(감독 10-23 — dump_python(mode="json") 은 NaN 을 그대로 두고 dump_json 은 null 로 낸다, pydantic 2.13.5).
    # 단계 data·엑셀은 이 판에서 짓는다: 모델 JSON 의 NaN·Infinity 가 run_flow 왕복(allow_nan=False)을 깨지 않게.
    dumped = cast("dict[str, Any]", json.loads(adapter.dump_json(result)))
    report = OutputFile(name=xlsx.FILENAME, media_type=xlsx.MEDIA_TYPE, content=xlsx.build_websearch(dumped))
    return StepOutput(data={"results": [dumped]}, files=(report,))


FLOW: Final = make_flow(
    module="materiality",
    id=FLOW_ID,
    input_shape=shapes.INPUT_SHAPE,
    inputs=MaterialityInputs,
    adapters=MaterialityAdapters,
    result_shapes=(shapes.RESULT_SHAPE,),
    output_files=(xlsx.FILENAME,),
    steps=(
        FlowStep(name="load", run=_load),
        FlowStep(name="regulation", run=_regulation),
        FlowStep(name="keywords", run=_keywords),
        FlowStep(name="controversy", run=_controversy),
        FlowStep(name="report", run=_report),
    ),
)


# ── dry-run 어림(견본 실행 IRL 의 재료 — 공급사 호출 0) ──────────────────────────────────────


def estimate(inputs: MaterialityInputs, llm: ToolLoopLlm, *, assumed_searches_per_call: int = 1) -> dict[str, Any]:
    """실행 하나의 비용 위끝을 공급사를 부르지 않고 어림한다(core 의 dry_run_tools). 호출 1 + 2N 개를 실제와 같은 값으로
    짓되, 위끝 셈에만 응답 하나당 web_search 건수를 assumed_searches_per_call 로 둔다(실제 요청에는 상한을 싣지 않는다
    — 코랩대로). 컨트로버시의 키워드 글은 「(키워드 없음)」으로 어림한다(실제 키워드 글 몫은 들지 않는다).
    입력 꼴·비용 상한이 틀리면 FlowInputError.

    꼴: {perPhase: {regulation|keywords|controversy: {calls, upperBoundUsd}}, totalUpperBoundUsd: {withoutRetry,
    withRetry}, maxProviderCalls, unestimated: [..], assumptions: [..]}. withRetry 는 호출마다 잘림 재시도까지 다 쓴다고
    본 위끝(× (1 + RETRY_ON_INCOMPLETE)), maxProviderCalls 는 (1 + RETRY_ON_INCOMPLETE) × (1 + 2N)."""
    received = check_received(inputs.received)
    check_cost(inputs.max_cost_usd)
    assumed = cast("object", assumed_searches_per_call)
    if isinstance(assumed, bool) or not isinstance(assumed, int) or assumed < 1:
        raise FlowInputError(f"assumed_searches_per_call 은 1 이상의 정수여야 한다: {assumed!r}")
    planned = [
        *regulation_messages(received, texts=inputs.texts),
        keywords_message(received, texts=inputs.texts),
        *controversy_messages(received, {}, texts=inputs.texts),
    ]
    per_phase: dict[str, dict[str, Any]] = {phase: {"calls": 0, "upperBoundUsd": NO_COST} for phase in PHASES}
    unestimated: list[str] = []
    for message in planned:
        request = call_request(
            phase=message.phase, system=message.system, prefix=message.prefix, variable=message.variable, inputs=inputs
        )
        loop = llm.dry_run_tools(replace(request, max_hosted_calls=assumed)).tool_loop
        if loop is None:
            raise AssertionError("dry_run_tools 는 고리 어림을 낸다")
        per_phase[message.phase]["calls"] += 1
        per_phase[message.phase]["upperBoundUsd"] += loop.loop_upper_bound_usd
        unestimated.extend(part for part in loop.unestimated if part not in unestimated)
    unestimated.append("controversy_keywords")
    total = sum(cast("float", per_phase[phase]["upperBoundUsd"]) for phase in PHASES)
    for phase in PHASES:
        per_phase[phase]["upperBoundUsd"] = round_usd(per_phase[phase]["upperBoundUsd"])
    attempts = 1 + constants.RETRY_ON_INCOMPLETE
    return {
        "perPhase": per_phase,
        "totalUpperBoundUsd": {"withoutRetry": round_usd(total), "withRetry": round_usd(total * attempts)},
        "maxProviderCalls": attempts * len(planned),
        "unestimated": unestimated,
        "assumptions": [
            f"어림이다(실측 아님): 호출마다 출력 상한({inputs.max_output_tokens:,})을 다 쓴다고 본 위끝",
            f"응답 하나당 web_search 를 {assumed}건으로 셈했다(실제 요청에는 건수 상한이 없다 — 코랩대로)",
            "검색 내용 토큰(모델 단가로 과금)은 얼마나 실릴지 몰라 들지 않는다(web_search_content)",
            "컨트로버시의 키워드 글은 「(키워드 없음)」으로 어림했다(controversy_keywords)",
            "실제 지출은 max_cost_usd 가 막는다 — 공급사 호출마다 그 앞에서만 보므로 호출 하나만큼 넘칠 수 있다",
        ],
    }
