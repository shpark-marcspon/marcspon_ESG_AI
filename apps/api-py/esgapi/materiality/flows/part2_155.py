"""중대성평가 IRO 코랩 2부(셀 46 환경·사회 영향, 셀 50 재무 영향, 셀 55 재무 Impact Pathway)의 단계 넷 — core.llm 위
gpt-4.1 호출(밴드 IR2a, MARC-ENT-425 ②).

    <씨앗 단계 SEED> → impact → financial → pathway → report2

흐름(make_flow)·등록은 여기 없다 — 1부 → 2부 한 실행과 흐름 id·입력 꼴은 IR2b(MARC-ENT-322), 전역 등록은 IR3a 끼움. 씨앗
단계(이름 SEED)의 data 는 {input: Part2Input, result: 1부 결과(@1·@2 JSON 판), warnings: 옮겨 올 경고(@2 꼴),
spentUsd: 앞까지의 실행 누계} 이다(contracts/wire.part2_input_from_result 의 산출 + 1부의 spentUsd). 시험은
tests/flows/support.py 의 시험용 흐름(씨앗 → 넷)으로 run_flow 를 돈다.

- impact     토픽(입력 차례) → 서브토픽(지어 넣은 뒤 차례 — 코랩 셀 46)마다 한 번(system = IMPACT_SYSTEM).
- financial  같은 차례로 한 번씩(셀 50 — 셀 51 은 쓰지 않는다: 결함 ④).
- pathway    재무 답을 다시 읽어 행이 있으면 그 행의 표(part2_render.pathway_table)로 한 번, 재무가 실패·못 읽음·행 0
             이면 부르지 않는다(코랩 셀 55 의 [MISSING fin_impact]).
- report2    답 → 결과 칸(contracts/wire, failure 는 매번 넘긴다) → @2 조립 → 꼴 검사(못 지나면 FlowOutputError) →
             JSON 판(dump_json — NaN·Infinity 는 null) → 최종 엑셀(outputs/final_xlsx — 자른 칸은 경고
             xlsx_cell_truncated 를 더해 다시 검사). 결과는 {"results": [JSON 판]} 하나(core 의 끝 산출물 규칙 —
             호출 기록은 앞 단계 data 의 calls).

호출 하나(run_part2_call): 코랩 2부 러너(셀 8 subtopic_impactdef_prompt)대로 temperature·tool_choice 를 싣지 않고 재시도
없음. latestEventMode 거짓 → LlmClient.call(스키마 없음 — 처분 ⑤, system 은 instructions 칸 — 처분 ⑥), 참 →
call_tools(web_search low·user_location 없음·걸음 1·system 은 input 의 system 메시지 — 처분 ⑦). 끝남 → 답 글, 잘림 →
부분 글 + failure truncated(읽히면 report2 가 done 으로 — 잘림 경고는 기록의 ending 으로), 그 밖 → 답 없음(core 갈래
이름). 실패 message 는 갈래 이름·상한 자리·공급사 상태 번호까지 — 모델 글·공급사 메시지 0.

실행 비용 상한(max_cost_usd, IR1b 처분 ⑦ 꼴): 공급사 호출마다 그 앞에서 앞 단계 spentUsd(씨앗에 1부가 있으면 그것까지)
+ 이 단계 누계가 상한 이상이면 부르지 않는다(failed·budget_exceeded (run), 뒤도 같다). 보장은 「지출 ≤ 상한 + 호출
하나」.
단계 안 진행(밴드 IRW6, MARC-ISSUE-378): impact·financial·pathway 는 자리(토픽 × 서브토픽)마다 checkpoint(done = 끝난
자리 수 — pathway 의 건너뜀 자리도 한 자리, total = 자리 수, 부분 산출물 = 그 단계 data 꼴의 앞부분)를 내고 resume 이
오면 끝난 자리를 건너뛴다(flows/progress_155). resume 없이 checkpoint 만 내면 안 된다 — 실행기가 checkpoint 뒤마다
양보하고 진행 있는 시도는 상한에 세지 않아, 시도마다 처음부터 같은 호출을 되풀이한다(progress_155 머리).
단계는 순수 함수다: 앞 산출물은 carried[<이름>].data 에서만, 중간 data 는 글·수·failure 만(모델 JSON 은 report2 가 다시
읽는다 — MARC-ISSUE-345 1). 이 파일은 설정·환경 변수·키를 읽지 않고 SDK 클라이언트를 짓지 않는다.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Literal, Protocol, cast

from pydantic import ValidationError

from esgapi.core.flows.types import Carried, FlowOutputError, OutputFile, StepContext, StepOutput
from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.types import (
    CutOff,
    DryRunReport,
    LlmResult,
    ProviderFailed,
    Success,
    Tags,
    ToolExecutor,
    ToolLoopDone,
    ToolLoopFailed,
    ToolLoopPartial,
    ToolLoopResult,
    WebSearchTool,
)
from esgapi.materiality.contracts import shapes, wire
from esgapi.materiality.engines.colab_155 import constants, part2_parsing, part2_prompts, part2_render
from esgapi.materiality.engines.colab_155.inputs import resolve_subtopics
from esgapi.materiality.flows import progress_155
from esgapi.materiality.flows.colab_155 import PromptTexts, StageModel, check_cost, failure_message, no_function
from esgapi.materiality.outputs import final_xlsx

Phase2 = Literal["impact", "financial", "pathway"]
PHASES2: Final[tuple[Phase2, ...]] = ("impact", "financial", "pathway")
SEED: Final = "part2_seed"
"""씨앗 단계의 이름(2부 단계가 읽는 자리). IR2b 의 흐름이 이 이름의 단계를 둔다."""
ROUTE_PART2: Final = "standard-openai-41"
"""core/llm/data/models.json 의 경로(gpt-4.1 하나 — 코랩 셀 46·50 model, constants.MODEL_PART2)."""
PROMPT_IDS2: Final[Mapping[Phase2, str]] = {phase: f"materiality/{phase}@1" for phase in PHASES2}
"""단계 → 프롬프트 id(봉투 prompts/<단계>/1.md — `=== system ===` {{system}} `=== user ===` {{user}})."""
MAX_OUTPUT_TOKENS_PART2: Final = 32_768
"""호출마다의 출력 상한. 코랩은 주지 않는다(공급사 기본) — core 의 기본(4,096) 대신 gpt-4.1 의 상한을 넘긴다
(models.json 의 gpt-4.1 maxOutputTokens, 출처 줄 「32,768 max output tokens」 2026-10-19 확인 — 처분 ⑫)."""
TIMEOUT_MS_PART2: Final = 600_000
"""호출의 시간 한도. 코랩은 주지 않는다 — SDK 기본 600초(1부와 같다)."""
MAX_STEPS_PART2: Final = 1
SYSTEM_PLACEMENT_LATEST: Final = "input_message"
"""latestEventMode 참(도구 고리)의 system 자리 — 코랩 input 의 system 메시지. 거짓(call)은 core 가 instructions 칸에
싣는다(core 0줄 — 처분 ⑥)."""
NO_COST: Final = 0.0
CODE_ANALYSIS: Final = StageModel(route=ROUTE_PART2, temperature=None, max_output_tokens=MAX_OUTPUT_TOKENS_PART2)
"""2부(분석 모델 칸)의 코드 값 — 기본 판·옛 실행. temperature 는 싣지 않는다(코랩 2부)."""


def web_search_part2() -> WebSearchTool:
    """코랩 셀 8 subtopic_impactdef_prompt 의 web_search(search_context_size low, user_location 없음)."""
    return WebSearchTool(search_context_size=constants.PART2_SEARCH_CONTEXT_SIZE)


@dataclass(frozen=True, kw_only=True)
class Part2Inputs:
    """2부 단계의 입력.

    tags               core.llm 의 기록·비용 꼬리표(테넌트, 모듈 materiality)
    max_cost_usd       실행 하나의 비용 상한(USD, 0 보다 큰 유한한 수. 기본값 없음 — 처분 ⑬)
    route              경로 이름(gpt-4.1 하나)
    texts              템플릿 글(IR4 — 기본값 없음, 기본 글은 DEFAULT_TEXTS)
    max_output_tokens  호출마다의 출력 상한(IR4 — 코드 값 MAX_OUTPUT_TOKENS_PART2). temperature 는 싣지 않는다
    """

    tags: Tags
    max_cost_usd: float
    route: str = ROUTE_PART2
    texts: PromptTexts
    max_output_tokens: int


class Part2Llm(Protocol):
    """2부가 쓰는 core.llm 의 입구(LlmClient 가 그대로 맞는다)."""

    def call(self, request: CallRequest[str]) -> LlmResult[str]: ...

    def dry_run(self, request: CallRequest[str]) -> DryRunReport: ...

    def call_tools(self, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult: ...

    def dry_run_tools(self, request: ToolCallRequest) -> DryRunReport: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class Part2Adapters:
    """2부의 어댑터. llm 은 부르는 쪽이 지은 클라이언트(실호출·모의는 부르는 쪽이 고른다)."""

    llm: Part2Llm


# ── 호출 하나 ───────────────────────────────────────────────────────────────────────────────


def part2_request(
    *, phase: Phase2, system: str, user: str, inputs: Part2Inputs, latest: bool
) -> CallRequest[str] | ToolCallRequest:
    """호출 하나의 요청. temperature·tool_choice 는 싣지 않는다(코랩 2부 러너)."""
    prompt_vars = {"system": system, "user": user}
    if latest:
        return ToolCallRequest(
            prompt=PROMPT_IDS2[phase],
            route=inputs.route,
            tags=inputs.tags,
            tools=(web_search_part2(),),
            max_steps=MAX_STEPS_PART2,
            vars=prompt_vars,
            max_output_tokens=inputs.max_output_tokens,
            timeout_ms=TIMEOUT_MS_PART2,
            system_placement=SYSTEM_PLACEMENT_LATEST,
        )
    return CallRequest(
        prompt=PROMPT_IDS2[phase],
        route=inputs.route,
        tags=inputs.tags,
        vars=prompt_vars,
        max_output_tokens=inputs.max_output_tokens,
        timeout_ms=TIMEOUT_MS_PART2,
    )


@dataclass(frozen=True, slots=True)
class Called2:
    """호출 하나의 끝: 답 글(없으면 None)·실패(없으면 None)·잘렸는지·이 호출 뒤 실행 누계·기록 한 줄."""

    text: str | None
    failure: shapes.MaterialityFailure | None
    truncated: bool
    spent: float
    record: dict[str, Any]


def _cost(result: LlmResult[str] | ToolLoopResult) -> float:
    return sum(attempt.cost_usd or NO_COST for attempt in result.meta.attempts)


def _model(result: LlmResult[str] | ToolLoopResult | None) -> str | None:
    if result is None or not result.meta.attempts:
        return None
    return result.meta.attempts[-1].model


def _hosted(result: LlmResult[str] | ToolLoopResult | None) -> int:
    if isinstance(result, ToolLoopDone | ToolLoopPartial):
        return result.hosted_calls
    if isinstance(result, ToolLoopFailed):
        return sum(step.hosted_calls for step in result.steps)
    return 0


def _failure(kind: str, message: str) -> shapes.MaterialityFailure:
    return {"kind": cast("shapes.FailureKind", kind), "message": message}


def _call_failure_message(result: LlmResult[str]) -> str:
    """call 의 실패 갈래(+ 공급사 상태). 모델 글·공급사 메시지는 싣지 않는다."""
    message = result.kind
    if isinstance(result, ProviderFailed):
        message += f" status={'none' if result.status is None else result.status}"
    return message


def _ending(result: LlmResult[str] | ToolLoopResult) -> tuple[str | None, shapes.MaterialityFailure | None, str]:
    """(답 글, 실패, 기록의 ending). 잘림은 부분 글과 failure truncated(재시도 없음 — 코랩 2부 러너)."""
    match result:
        case Success():
            return result.text, None, "done"
        case ToolLoopDone():
            return result.text, None, "done"
        case CutOff():
            return result.partial_text, _failure("truncated", "truncated"), "truncated"
        case ToolLoopFailed(failure=CutOff() as cut):
            return cut.partial_text, _failure("truncated", "truncated"), "truncated"
        case ToolLoopPartial():
            return None, _failure("provider_error", "provider_error unexpected_function_call"), "partial"
        case ToolLoopFailed():
            return None, _failure(result.failure.kind, failure_message(result)), result.failure.kind
        case _:
            return None, _failure(result.kind, _call_failure_message(result)), result.kind


def run_part2_call(
    llm: Part2Llm,
    *,
    phase: Phase2,
    topic: str,
    subtopic: str,
    system: str,
    user: str,
    inputs: Part2Inputs,
    latest: bool,
    spent: float,
) -> Called2:
    """호출 하나(재시도 없음). 공급사 호출 앞에서 실행 누계를 상한에 견준다(처분 ⑬)."""
    result: LlmResult[str] | ToolLoopResult | None = None
    if spent >= inputs.max_cost_usd:
        text, failure, ending = None, _failure("budget_exceeded", "budget_exceeded (run)"), "budget_exceeded"
    else:
        request = part2_request(phase=phase, system=system, user=user, inputs=inputs, latest=latest)
        result = llm.call_tools(request, no_function) if isinstance(request, ToolCallRequest) else llm.call(request)
        spent += _cost(result)
        text, failure, ending = _ending(result)
    record = {
        "phase": phase,
        "topic": topic,
        "subtopic": subtopic,
        "ending": ending,
        "hostedCalls": _hosted(result),
        "costUsd": round_usd(NO_COST if result is None else _cost(result)),
        "model": _model(result),
    }
    return Called2(text=text, failure=failure, truncated=ending == "truncated", spent=spent, record=record)


# ── 단계 ───────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Slot:
    """서브토픽 하나의 자리(토픽 입력 차례, 서브토픽 지어 넣은 뒤 차례)."""

    topic: Mapping[str, str]
    subtopic: Mapping[str, str]
    autofilled: bool


def slots(part2_input: Mapping[str, Any]) -> tuple[list[Slot], list[tuple[str, str]]]:
    """코랩 셀 46 의 차례: 토픽마다 서브토픽(없으면 토픽 설명으로 하나 지어 넣음 — 경고 갈래도)."""
    topics = cast("list[Mapping[str, str]]", part2_input["topics"])
    resolved, pairs = resolve_subtopics(
        cast("Mapping[str, list[dict[str, str]]]", part2_input["subtopics"]),
        [{"topic": t["topic"], "description": t["description"]} for t in topics],
    )
    autofilled = {name for code, name in pairs if code == "subtopic_autofilled"}
    out = [Slot(t, s, t["topic"] in autofilled) for t in topics for s in resolved[t["topic"]]]
    return out, list(pairs)


def _seed(carried: Carried) -> Mapping[str, Any]:
    return carried[SEED].data


def _spent(carried: Carried, phase: Phase2) -> float:
    """앞 단계까지의 실행 누계(USD). impact 는 씨앗의 spentUsd(1부까지)."""
    before = PHASES2.index(phase)
    step = SEED if before == 0 else PHASES2[before - 1]
    return cast("float", carried[step].data["spentUsd"])


def impact_messages(part2_input: Mapping[str, Any], *, texts: PromptTexts) -> list[tuple[Slot, str, str]]:
    """셀 46: 자리마다 (자리, system, user)."""
    value_chain = cast("list[dict[str, str]]", part2_input["valueChain"] or [])  # 처분 ⑪
    return [
        (
            slot,
            texts.impact_system,
            part2_prompts.impact_user(
                part2_input["company"],
                part2_input["industry"],
                value_chain,
                slot.topic["topic"],
                slot.subtopic["name"],
                slot.subtopic["description"],
                slot.topic["controversyText"],
                slot.topic["regulationText"],
                texts=texts,
            ),
        )
        for slot in slots(part2_input)[0]
    ]


def financial_messages(part2_input: Mapping[str, Any], *, texts: PromptTexts) -> list[tuple[Slot, str, str]]:
    """셀 50: 자리마다 (자리, system, user)."""
    value_chain = cast("list[dict[str, str]]", part2_input["valueChain"] or [])
    return [
        (
            slot,
            texts.financial_system,
            part2_prompts.financial_user(
                part2_input["company"],
                part2_input["industry"],
                value_chain,
                slot.topic["topic"],
                slot.subtopic["name"],
                slot.subtopic["description"],
                slot.topic["controversyText"],
                slot.topic["regulationText"],
                texts=texts,
            ),
        )
        for slot in slots(part2_input)[0]
    ]


def financial_rows(text: str | None) -> list[dict[str, Any]]:
    """재무 답 글 → 행(못 읽거나 답이 없으면 빈 목록)."""
    if text is None:
        return []
    return part2_parsing.read_answer(text, part2_parsing.IMPACTS)["rows"] or []


def _answers(
    llm: Part2Llm,
    phase: Phase2,
    messages: Sequence[tuple[Slot, str, str] | tuple[Slot, None, None]],
    inputs: Part2Inputs,
    latest: bool,
    spent: float,
    ctx: StepContext,
) -> StepOutput:
    """자리마다 한 번(건너뜀 자리도 한 자리 — done 이 total 에 닿게). 자리마다 checkpoint, resume 이면 끝난 자리를
    건너뜀."""
    keys = [(slot.topic["topic"], slot.subtopic["name"]) for slot, _, _ in messages]
    p = progress_155.start(ctx, keys, spent)
    for slot, system, user in messages[len(p.answers) :]:
        topic, subtopic = slot.topic["topic"], slot.subtopic["name"]
        if system is None or user is None:  # pathway: 재무가 실패·못 읽음·행 0
            p.add(
                {
                    "topic": topic,
                    "subtopic": subtopic,
                    "text": None,
                    "failure": None,
                    "truncated": False,
                    "skipped": True,
                },
                None,
                p.spent,
            )
            continue
        called = run_part2_call(
            llm,
            phase=phase,
            topic=topic,
            subtopic=subtopic,
            system=system,
            user=user,
            inputs=inputs,
            latest=latest,
            spent=p.spent,
        )
        p.add(
            {
                "topic": topic,
                "subtopic": subtopic,
                "text": called.text,
                "failure": called.failure,
                "truncated": called.truncated,
                "skipped": False,
            },
            called.record,
            called.spent,
        )
    return StepOutput(data=p.data())


def _impact(inputs: Part2Inputs, adapters: Part2Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    """셀 46: 서브토픽마다 환경·사회 영향."""
    check_cost(inputs.max_cost_usd)
    part2_input = _seed(carried)["input"]
    latest = cast("bool", part2_input["latestEventMode"])
    return _answers(
        adapters.llm,
        "impact",
        impact_messages(part2_input, texts=inputs.texts),
        inputs,
        latest,
        _spent(carried, "impact"),
        ctx,
    )


def _financial(inputs: Part2Inputs, adapters: Part2Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    """셀 50: 서브토픽마다 재무 영향."""
    part2_input = _seed(carried)["input"]
    latest = cast("bool", part2_input["latestEventMode"])
    messages = financial_messages(part2_input, texts=inputs.texts)
    return _answers(adapters.llm, "financial", messages, inputs, latest, _spent(carried, "financial"), ctx)


def pathway_messages(
    part2_input: Mapping[str, Any], financial: Sequence[Mapping[str, Any]], *, texts: PromptTexts
) -> list[tuple[Slot, str, str] | tuple[Slot, None, None]]:
    """셀 55: 자리마다 재무 답의 행이 있으면 (자리, system, user = 표를 실은 글), 없으면 (자리, None, None)."""
    out: list[tuple[Slot, str, str] | tuple[Slot, None, None]] = []
    for slot, answer in zip(slots(part2_input)[0], financial, strict=True):
        rows = financial_rows(cast("str | None", answer["text"]))
        if not rows:
            out.append((slot, None, None))
            continue
        table = part2_render.pathway_table(slot.topic["topic"], slot.subtopic["name"], rows)
        out.append((slot, texts.pathway_system, part2_prompts.pathway_user(table, texts=texts)))
    return out


def _pathway(inputs: Part2Inputs, adapters: Part2Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    """셀 55: 재무 행이 있는 서브토픽마다 재무 Impact Pathway."""
    part2_input = _seed(carried)["input"]
    latest = cast("bool", part2_input["latestEventMode"])
    financial = cast("list[dict[str, Any]]", carried["financial"].data["answers"])
    messages = pathway_messages(part2_input, financial, texts=inputs.texts)
    return _answers(adapters.llm, "pathway", messages, inputs, latest, _spent(carried, "pathway"), ctx)


def _read(text: str | None, key: str) -> dict[str, Any] | None:
    return None if text is None else part2_parsing.read_answer(text, key)


def subtopic_outcomes(
    slot: Slot,
    known: Sequence[str],
    impact: Mapping[str, Any],
    financial: Mapping[str, Any],
    pathway: Mapping[str, Any],
) -> tuple[shapes.MaterialitySubtopicResult, list[shapes.MaterialityWarning2]]:
    """자리 하나의 답 셋 → 서브토픽 결과와 경고(failure 는 매번 넘긴다)."""
    topic, subtopic = slot.topic["topic"], slot.subtopic["name"]
    imp_text = cast("str | None", impact["text"])
    imp, w1 = wire.impact_outcome(
        imp_text,
        _read(imp_text, part2_parsing.IMPACTS),
        topic=topic,
        subtopic=subtopic,
        known_activities=known,
        failure=impact["failure"],
    )
    fin_text = cast("str | None", financial["text"])
    fin_read = _read(fin_text, part2_parsing.IMPACTS)
    fin, w2 = wire.financial_outcome(
        fin_text, fin_read, topic=topic, subtopic=subtopic, known_activities=known, failure=financial["failure"]
    )
    path_text = cast("str | None", pathway["text"])
    path_read = _read(path_text, part2_parsing.PATHWAYS)
    if path_read is not None and path_read["rows"] is not None:
        fin_rows: list[dict[str, Any]] = [] if fin_read is None else fin_read["rows"] or []
        joined, mismatch = part2_parsing.join_pathway(path_read["rows"], fin_rows)
        path_read = {**path_read, "rows": joined, "mismatch": mismatch}
    path, w3 = wire.pathway_outcome(
        path_text,
        path_read,
        topic=topic,
        subtopic=subtopic,
        skipped=cast("bool", pathway["skipped"]),
        failure=pathway["failure"],
    )
    result = wire.subtopic_result(slot.subtopic, autofilled=slot.autofilled, impact=imp, financial=fin, pathway=path)
    return result, [*w1, *w2, *w3]


def part2_calls(carried: Carried) -> list[dict[str, Any]]:
    """2부 단계 셋의 호출 기록(차례대로)."""
    return [call for phase in PHASES2 for call in cast("list[dict[str, Any]]", carried[phase].data["calls"])]


def build_part2_result(carried: Carried, *, max_output_tokens: int) -> dict[str, Any]:
    """carried(씨앗 + 단계 셋) → @2 결과 꼴(검사 전 — report2 가 검사하고 JSON 판으로)."""
    seed = _seed(carried)
    part2_input = cast("Mapping[str, Any]", seed["input"])
    seed_result = cast("Mapping[str, Any]", seed["result"])
    every, pairs = slots(part2_input)
    known = wire.value_chain_activities(part2_input)
    warnings: list[shapes.MaterialityWarning2] = [wire.as_warning2(w) for w in seed["warnings"]]
    warnings += [wire.as_warning2(w) for w in wire.subtopic_warnings(pairs)]
    answers = [cast("list[dict[str, Any]]", carried[phase].data["answers"]) for phase in PHASES2]
    by_topic: dict[str, list[shapes.MaterialitySubtopicResult]] = {}
    for slot, impact, financial, pathway in zip(every, *answers, strict=True):
        result, more = subtopic_outcomes(slot, known, impact, financial, pathway)
        by_topic.setdefault(slot.topic["topic"], []).append(result)
        warnings += more
    calls = part2_calls(carried)
    warnings += wire.truncated_warnings(calls)
    models = [cast("str", call["model"]) for call in calls if call["model"] is not None]
    part2_settings: shapes.MaterialityPart2Settings = {
        "model": models[-1] if models else None,
        "maxOutputTokens": max_output_tokens,
        "latestEventMode": cast("bool", part2_input["latestEventMode"]),
        "promptIds": {
            "impact": PROMPT_IDS2["impact"],
            "financial": PROMPT_IDS2["financial"],
            "pathway": PROMPT_IDS2["pathway"],
        },
    }
    topics = [(t, by_topic.get(t["topic"], [])) for t in cast("list[Mapping[str, str]]", part2_input["topics"])]
    part2 = wire.part2_done(cast("shapes.Part2Source", part2_input["source"]), topics)
    return dict(
        wire.build_result_v2(
            seed_result, part1_result=seed_result, part2_settings=part2_settings, part2=part2, warnings=warnings
        )
    )


def dump_v2(result: Mapping[str, Any]) -> dict[str, Any]:
    """@2 꼴 검사(못 지나면 FlowOutputError — 흐름의 결함) → JSON 판(dump_json — NaN·Infinity 는 null)."""
    adapter = shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2]
    try:
        adapter.validate_python(result, strict=True)
    except ValidationError as error:
        raise FlowOutputError(
            f"결과가 {shapes.RESULT_SHAPE_V2} 꼴을 지나지 못했다: {error.error_count()} errors"
        ) from None
    return cast("dict[str, Any]", json.loads(adapter.dump_json(result)))


def cut_warnings(cuts: Sequence[Mapping[str, Any]]) -> list[shapes.MaterialityWarning2]:
    """최종 엑셀에서 자른 칸마다 xlsx_cell_truncated(처분 ⑮)."""
    return [
        wire.warning2(
            "xlsx_cell_truncated",
            f"엑셀 「{cut['sheet']}」 {cut['cell']} 칸이 32,767자를 넘어 앞부분만 담았다(원문 {cut['length']}자).",
            topic=cut["topic"],
            phase="report",
        )
        for cut in cuts
    ]


def _report2(inputs: Part2Inputs, adapters: Part2Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    """@2 조립 → 검사 → JSON 판 → 최종 엑셀 → 자른 칸 경고를 더해 다시 검사(엑셀 RAW_JSON 은 그 경고 전의 판)."""
    dumped = dump_v2(build_part2_result(carried, max_output_tokens=inputs.max_output_tokens))
    content, cuts = final_xlsx.build_final(dumped)
    if cuts:
        dumped = dump_v2({**dumped, "warnings": [*dumped["warnings"], *cut_warnings(cuts)]})
    report = OutputFile(name=final_xlsx.FILENAME, media_type=final_xlsx.MEDIA, content=content)
    return StepOutput(data={"results": [dumped]}, files=(report,))


STEPS: Final = (
    ("impact", _impact),
    ("financial", _financial),
    ("pathway", _pathway),
    ("report2", _report2),
)
"""2부 단계 넷(이름, 함수) — FlowStep 으로 감싸는 것은 흐름을 짓는 쪽(IR2b·시험)."""


# ── dry-run 어림(공급사 호출 0) ──────────────────────────────────────────────────────────────


def _planned(phase: Phase2, messages: Sequence[tuple[Slot, str, str]]) -> list[tuple[Phase2, str, str]]:
    return [(phase, system, user) for _, system, user in messages]


def estimate_part2(
    part2_input: Mapping[str, Any], inputs: Part2Inputs, llm: Part2Llm, *, assumed_fin_rows: int = 2
) -> dict[str, Any]:
    """2부의 비용 위끝을 공급사를 부르지 않고 어림한다(core 의 dry_run·dry_run_tools). 46·50 은 실제 글로, 55 는 재무 행
    assumed_fin_rows 개를 지어낸 표로 짓는다(실제 표 글 몫은 들지 않는다 — unestimated pathway_input). 비용 상한이
    틀리면 FlowInputError.

    꼴: {perPhase: {impact|financial|pathway: {calls, upperBoundUsd}}, totalUpperBoundUsd,
    maxProviderCalls(= 3 × 자리 수), assumptions: [..], unestimated: [..]}."""
    check_cost(inputs.max_cost_usd)
    if (
        isinstance(assumed_fin_rows, bool)
        or not isinstance(cast("object", assumed_fin_rows), int)
        or assumed_fin_rows < 1
    ):
        raise ValueError(f"assumed_fin_rows 는 1 이상의 정수여야 한다: {assumed_fin_rows!r}")
    latest = cast("bool", part2_input["latestEventMode"])
    planned = _planned("impact", impact_messages(part2_input, texts=inputs.texts)) + _planned(
        "financial", financial_messages(part2_input, texts=inputs.texts)
    )
    assumed: list[dict[str, Any]] = [
        {
            "impact_definition": f"(어림) 재무 영향 {n}",
            "impact_type": "리스크",
            "risk_type": "리스크-시장",
            "context": {},
        }
        for n in range(1, assumed_fin_rows + 1)
    ]
    for slot in slots(part2_input)[0]:
        table = part2_render.pathway_table(slot.topic["topic"], slot.subtopic["name"], assumed)
        planned.append(("pathway", inputs.texts.pathway_system, part2_prompts.pathway_user(table, texts=inputs.texts)))
    per_phase: dict[str, dict[str, Any]] = {phase: {"calls": 0, "upperBoundUsd": NO_COST} for phase in PHASES2}
    unestimated: list[str] = []
    for phase, system, user in planned:
        request = part2_request(phase=phase, system=system, user=user, inputs=inputs, latest=latest)
        if isinstance(request, ToolCallRequest):
            loop = llm.dry_run_tools(replace(request, max_hosted_calls=1)).tool_loop
            if loop is None:
                raise AssertionError("dry_run_tools 는 고리 어림을 낸다")
            bound = loop.loop_upper_bound_usd
            unestimated.extend(part for part in loop.unestimated if part not in unestimated)
        else:
            report = llm.dry_run(request)
            bound = report.estimate.cost_upper_bound_usd
            unestimated.extend(part for part in report.estimate.unestimated_parts if part not in unestimated)
        per_phase[phase]["calls"] += 1
        per_phase[phase]["upperBoundUsd"] += bound
    unestimated.append("pathway_input")
    total = sum(cast("float", per_phase[phase]["upperBoundUsd"]) for phase in PHASES2)
    for phase in PHASES2:
        per_phase[phase]["upperBoundUsd"] = round_usd(per_phase[phase]["upperBoundUsd"])
    assumptions = [
        f"어림이다(실측 아님): 호출마다 출력 상한({inputs.max_output_tokens:,})을 다 쓴다고 본 위끝",
        f"Pathway 입력 표는 재무 행 {assumed_fin_rows}개의 지어낸 표로 셈했다(pathway_input)",
        "재무가 실패·행 0 이면 Pathway 를 부르지 않는다 — 위끝은 셋 다 부른다고 본다",
        "실제 지출은 max_cost_usd 가 막는다 — 공급사 호출마다 그 앞에서만 보므로 호출 하나만큼 넘칠 수 있다",
    ]
    if latest:
        assumptions.append(
            "latestEventMode 참: 응답 하나당 web_search 를 1건으로 셈했다(실제 요청에는 건수 상한이 없다)"
        )
    return {
        "perPhase": per_phase,
        "totalUpperBoundUsd": round_usd(total),
        "maxProviderCalls": len(planned),
        "assumptions": assumptions,
        "unestimated": unestimated,
    }
