"""흐름 dataverify.colab@156 — 데이터 검증 코랩 셀 10(계산 Plan)·14(계산 검토)·18(인사이트)의 Responses 고리를
core.llm 의 도구 호출 고리(`LlmClient.call_tools` — store:false, 앞 항목 다시 싣기, MARC-ENT-301) 위에서 돈다
(밴드 DV1b).

    load → plan → review → insight → report

입력 꼴 dataverify.input@1(DataverifyInputs.received), 결과 꼴 dataverify.result@2(contracts/shapes.py), 출력 파일
dataverify-report.xlsx. 엔진(engines/colab_156)과 계약(contracts)을 잇는 유일한 자리다.

- load     입력 꼴 검사(틀리면 FlowInputError), 단계마다의 비용 상한 검사(없거나 0 이하·수 아님 → FlowInputError
           — 공급사 호출 0), 테마 거르기 → scope. 대상 테마가 없으면 경고 no_target_theme 이고 뒤 세 단계는 돌지
           않는다(처분 ⑧).
- plan     함수 도구 여덟으로 고리(걸음 12). 답 글을 ast.literal_eval 로 읽어 산식 목록(처분 ⑨). 읽지 못하면 실패
           (unparsable, raw = 받은 글) — 검토는 돌지 않고 인사이트는 돈다(코랩 셀 18 은 Plan 을 쓰지 않는다).
- review   함수 도구 여덟으로 고리(걸음 len(산식)*3, 천장 REVIEW_MAX_STEPS_CAP — 처분 ②). 도구 실행마다 검사 기록 하나
           (끝남·부분·실패 모두 — 실패면 그때까지 실행한 것).
- insight  web_search 하나로 고리(걸음 12). 입력 web_search=False 면 도구 없이 `call` 한 번(처분 ④) — 그 갈래에는
           고리의 비용 상한(max_cost_usd.insight)이 실리지 않는다(`CallRequest` 에 칸이 없다. 걸음 하나·출력 상한이
           위끝이고, 기존 BudgetLimit 은 그대로 본다). 표 줄·출처를 읽는다.
- report   결과 조립 → 결과 꼴 검사(못 지나면 FlowOutputError — 흐름의 결함) → 엑셀. 둘째 결과로 요약
           dataverify.digest@1(outputs/digest — 목록 GET /dataverify/runs 가 읽는다, 밴드 DV1g).

고리 → 단계: 끝남 = done·partial false, 부분(걸음이 다했는데 아직 도구를 부름 — 코랩의 「부분 리포트」) = done·partial
true, 실패 = failed·failure.kind(core 의 갈래 이름 — 고리와 끈 인사이트의 호출이 같은 규칙, failure_parts). 실패
message 는 실패 갈래와 상한의 자리·상태 번호·도구 이름까지만 — 모델 글·공급사 메시지·고객 데이터를 싣지 않는다(잘린
인사이트의 부분 원문은 insight.partialText 에만). 새 정보는 결과 꼴을 바꾸지 않고 warnings 의 code 로 낸다(처분 ⑤):
review_steps_capped·web_search_disabled·insight_no_web_search·tool_arguments_unparsable·tool_output_too_large·
no_target_theme.

알려진 한계(감독 처분 — MARC-ISSUE-191 ③): 중간 걸음(함수 호출을 받은 걸음)의 url_citation 은 core 가 버려 sources 는
마지막 답의 것뿐이다. 부분으로 끝난 인사이트는 출처가 없다(core 의 ToolLoopPartial 에 citations 칸이 없다). Plan 단계의
도구 호출은 결과에 남지 않는다(꼴에 자리 없음 — 코랩도 남기지 않는다). 검토가 부분으로 끝나면 실행하지 않은 남은 호출은
검사 기록에 없다.

단계는 순수 함수다: 앞 단계의 산출물은 carried[<이름>].data(JSON 왕복한 값)에서만 읽는다. 테마를 거른 데이터는 싣지
않고 단계마다 받은 dict 에서 다시 거른다(프롬프트가 받은 dict 를 글자째 싣는다 — JSON 왕복이 흔들지 않게).
이 파일은 설정·환경 변수·키를 읽지 않고 SDK 클라이언트를 짓지 않는다. 클라이언트는 부르는 쪽이 지어
DataverifyAdapters 로 넘긴다. 전역 레지스트리에 다는 것과 실행기 끼움은 밴드 DV1d 다(apps.py 가 registration.py 와
flows/binding_156.py 의 끼움을 단다 — 문서 없는 흐름).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
from esgapi.core.llm.client import CallRequest, ToolCallRequest
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.errors import soft_deadline_in
from esgapi.core.llm.types import (
    CutOff,
    DryRunReport,
    FunctionTool,
    LlmResult,
    ProviderFailed,
    Success,
    Tags,
    Tool,
    ToolExecutor,
    ToolExecutorRaised,
    ToolLoopDone,
    ToolLoopFailed,
    ToolLoopPartial,
    ToolLoopResult,
    UrlCitation,
    WebSearchTool,
)
from esgapi.dataverify.contracts import shapes, wire
from esgapi.dataverify.contracts.digest_shapes import DIGEST_SHAPE
from esgapi.dataverify.engines.colab_156 import prompts, schemas
from esgapi.dataverify.engines.colab_156.inputs import THEMES, split_themes
from esgapi.dataverify.engines.colab_156.loop import ToolRunner, parse_hints, report_text, review_steps
from esgapi.dataverify.outputs import xlsx
from esgapi.dataverify.outputs.digest import digest

FLOW_ID: Final = "dataverify.colab@156"
STAGES: Final = ("plan", "review", "insight")

ROUTE: Final = "standard-openai-41"
"""core/llm/data/models.json 의 경로 이름(gpt-4.1 하나 — 코랩 셀 10·14·18 의 모델, MARC-ENT-305)."""
MAX_OUTPUT_TOKENS: Final = 32_768
"""걸음마다의 출력 상한. 코랩은 출력 상한을 주지 않는다 — core 의 기본(4,096) 대신 gpt-4.1 의 상한을 넘겨 근사한다
(models.json 의 gpt-4.1 maxOutputTokens, 출처 줄 「32,768 max output tokens」 2026-10-19 확인)."""
TIMEOUT_MS: Final = 300_000
"""걸음마다의 시간 한도(코랩 _post 의 timeout=300 — R/521)."""
TEMPERATURE: Final = 0.1
TOOL_CHOICE: Final = "auto"
PARALLEL_TOOL_CALLS: Final = False
SYSTEM_PLACEMENT: Final = "input_message"
"""코랩 첫 몸의 값(R/655-674): tool_choice auto·병렬 호출 끔·temperature 0.1·system 은 input 의 메시지."""
REVIEW_MAX_STEPS_CAP: Final = 36
"""계산 검토의 고리 걸음 천장(산식 12개 몫 — 처분 ②). 프롬프트의 걸음 글은 천장 없이 len*3 이다(review_prompt)."""
TOOL_OUTPUT_MAX_CHARS: Final = 100_000
"""도구 결과 글자의 상한(처분 ③). 넘으면 모델에 error 글을 돌려준다(engines/colab_156/loop.ToolRunner)."""

FUNCTION_TOOLS: Final[tuple[FunctionTool, ...]] = tuple(
    FunctionTool(name=tool["name"], description=tool["description"], parameters=tool["parameters"])
    for tool in schemas.TOOLS_RESPONSES
)
"""계산 Plan·검토의 함수 도구 여덟(코랩 TOOLS_RESPONSES 의 차례, strict 없음 — 코랩에 없다)."""
WEB_SEARCH: Final = WebSearchTool(search_context_size=schemas.TOOLS_RESPONSES_websearch[0]["search_context_size"])
"""인사이트의 web_search(코랩 TOOLS_RESPONSES_websearch)."""

Stage = Literal["plan", "review", "insight"]


@dataclass(frozen=True, slots=True, kw_only=True)
class StageCosts:
    """단계마다 고리 한 번의 비용 상한(USD, 0 보다 큰 유한한 수). 기본값이 없다 — 부르는 쪽이 정한다(처분 ②)."""

    plan: float
    review: float
    insight: float


@dataclass(frozen=True, slots=True, kw_only=True)
class DataverifyInputs:
    """흐름의 입력.

    received           dataverify.input@1 의 받은 dict 그대로(검사만 하고 고치지 않는다 — DV1a §1-9)
    tags               core.llm 의 기록·비용 꼬리표(테넌트, 모듈 dataverify)
    max_cost_usd       단계마다의 비용 상한(필수)
    texts              프롬프트 글 여섯(기본 prompts.DEFAULT_TEXTS — AI 설정 판이 갈아 끼운다, 밴드 DVA1)
    temperature        세 단계의 temperature(기본 TEMPERATURE — AI 설정 판의 모델 칸)
    route              경로 이름(모델 하나, 도구 고리를 지나는 모델)
    web_search         False 면 인사이트를 도구 없이 한 번 부른다(sources 빔, 경고 web_search_disabled)
    max_output_tokens  걸음마다의 출력 상한

    texts·temperature 는 기본값이 없다 — 부르는 쪽(binding_156)이 판의 값이나 코드 값을 정한다.
    """

    received: Mapping[str, Any]
    tags: Tags
    max_cost_usd: StageCosts
    texts: prompts.PromptTexts
    temperature: float
    route: str = ROUTE
    web_search: bool = True
    max_output_tokens: int = MAX_OUTPUT_TOKENS


class ToolLoopLlm(Protocol):
    """흐름이 쓰는 core.llm 의 입구(LlmClient 가 그대로 맞는다)."""

    def call_tools(self, request: ToolCallRequest, execute: ToolExecutor) -> ToolLoopResult: ...

    def dry_run_tools(self, request: ToolCallRequest) -> DryRunReport: ...

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]: ...

    def dry_run[T](self, request: CallRequest[T]) -> DryRunReport: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class DataverifyAdapters:
    """흐름의 어댑터. llm 은 부르는 쪽이 지은 클라이언트(실호출·모의는 부르는 쪽이 고른다)."""

    llm: ToolLoopLlm


# ── 고리 하나 ───────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LoopRun:
    """고리 한 번: core 의 결과와 그 고리의 도구 실행기(기록·건수)."""

    result: ToolLoopResult
    runner: ToolRunner


def loop_request(
    *,
    stage: Stage,
    system: str,
    user: str,
    max_steps: int,
    max_cost_usd: float,
    tags: Tags,
    route: str = ROUTE,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    temperature: float = TEMPERATURE,
) -> ToolCallRequest:
    """단계의 고리 요청. 도구는 Plan·검토가 함수 여덟, 인사이트가 web_search 하나(코랩 셀 10·14·18)."""
    tools: tuple[Tool, ...] = (WEB_SEARCH,) if stage == "insight" else FUNCTION_TOOLS
    return ToolCallRequest(
        prompt=prompts.PROMPT_IDS[stage],
        route=route,
        tags=tags,
        tools=tools,
        max_steps=max_steps,
        vars={"system": system, "user": user},
        max_output_tokens=max_output_tokens,
        timeout_ms=TIMEOUT_MS,
        temperature=temperature,
        tool_choice=TOOL_CHOICE,
        parallel_tool_calls=PARALLEL_TOOL_CALLS,
        max_cost_usd=max_cost_usd,
        system_placement=SYSTEM_PLACEMENT,
    )


def _soft_deadline(error: BaseException) -> bool:
    """엔진(도구 실행기·HINTS 읽기)에 주입하는 「다시 던질지」 판별 — Celery soft limit 이 사슬에 있으면 참
    (MARC-ISSUE-414. 엔진은 core 를 모른다)."""
    return soft_deadline_in(error) is not None


def run_loop(
    llm: ToolLoopLlm,
    *,
    stage: Stage,
    system: str,
    user: str,
    data_split: Mapping[str, Any],
    max_steps: int,
    max_cost_usd: float,
    tags: Tags,
    route: str = ROUTE,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    temperature: float = TEMPERATURE,
) -> LoopRun:
    """단계 함수가 쓰는 고리(대조 명령 scripts/dataverify_compare_dump.py 도 이것을 부른다). 실행기는 고리마다 새로
    짓는다(캐시 하나 — 코랩은 셀 사이에 전역 캐시라 같은 데이터면 같은 값)."""
    runner = ToolRunner(
        data=data_split, tolerance=prompts.TOLERANCE, max_output_chars=TOOL_OUTPUT_MAX_CHARS, reraise=_soft_deadline
    )
    request = loop_request(
        stage=stage,
        system=system,
        user=user,
        max_steps=max_steps,
        max_cost_usd=max_cost_usd,
        tags=tags,
        route=route,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    return LoopRun(result=llm.call_tools(request, runner), runner=runner)


def failure_message(result: ToolLoopFailed) -> str:
    """실패 갈래(+ 상한의 자리, 공급사 상태, 도구 이름·예외 이름). 모델 글·공급사 메시지는 싣지 않는다."""
    failure = result.failure
    message = failure.kind
    if result.budget_source is not None:
        message += f" ({result.budget_source})"
    if isinstance(failure, ProviderFailed):
        message += f" status={'none' if failure.status is None else failure.status}"
    if isinstance(failure, ToolExecutorRaised):
        message += f" {failure.name} {failure.error_class}"
    return message


# contracts/shapes.py 의 FailureKind 에서 unparsable 을 뺀 것과 같아야 한다(계약은 flows 를 모른다 — 견주는 시험 없음).
FailureKind = Literal[
    "budget_exceeded", "truncated", "refusal", "provider_error", "timeout", "tool_executor_raised", "schema_mismatch"
]
BudgetSource = Literal["guard", "loop"]


@dataclass(frozen=True, slots=True)
class FailureParts:
    """실패의 갈래(core 의 kind 그대로)·상한의 자리(budget_exceeded 일 때만)·잘린 답의 부분 원문(truncated 일 때만)."""

    kind: FailureKind
    budget_source: BudgetSource | None
    partial_text: str | None


def failure_parts(failure: object, kind: FailureKind, budget_source: BudgetSource | None) -> FailureParts:
    """고리(ToolLoopFailed)와 끈 인사이트의 `call` 이 같은 규칙으로 쓴다. 끈 인사이트의 상한 실패는 기존 비용
    상한(BudgetLimit)뿐이라 부르는 쪽이 "guard" 를 넘긴다(`CallRequest` 에는 고리 상한 칸이 없다)."""
    return FailureParts(
        kind=kind,
        budget_source=budget_source if kind == "budget_exceeded" else None,
        partial_text=failure.partial_text if isinstance(failure, CutOff) else None,
    )


@dataclass(frozen=True, slots=True)
class Ended:
    """고리(또는 호출)의 끝을 단계의 갈래로: done 이면 text·partial, failed 면 message·parts."""

    status: Literal["done", "failed"]
    partial: bool | None
    text: str | None
    message: str | None
    model: str | None
    parts: FailureParts | None = None


def _last_model(attempts: Sequence[Any]) -> str | None:
    return None if not attempts else cast("str", attempts[-1].model)


def ended(result: ToolLoopResult) -> Ended:
    model = _last_model(result.meta.attempts)
    match result:
        case ToolLoopDone():
            return Ended("done", False, report_text(result.text), None, model)
        case ToolLoopPartial():
            return Ended("done", True, report_text(result.text), None, model)
        case ToolLoopFailed():
            parts = failure_parts(result.failure, result.failure.kind, result.budget_source)
            return Ended("failed", None, None, failure_message(result), model, parts)


def ended_call(result: LlmResult[str]) -> Ended:
    """끈 인사이트의 `call` 결과. Success 가 아니면 실패(message 는 갈래 이름 + 공급사 상태)."""
    model = _last_model(result.meta.attempts)
    if isinstance(result, Success):
        return Ended("done", False, report_text(result.text), None, model)
    message: str = result.kind
    if isinstance(result, ProviderFailed):
        message += f" status={'none' if result.status is None else result.status}"
    return Ended("failed", None, None, message, model, failure_parts(result, result.kind, "guard"))


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def runner_warnings(stage: Stage, runner: ToolRunner) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if runner.unparsable_args:
        warnings.append(
            _warning(
                "tool_arguments_unparsable",
                f"{stage}: 도구 호출 {runner.unparsable_args}건의 인자가 JSON 이 아니어서 빈 객체로 실행했다",
            )
        )
    if runner.too_large:
        warnings.append(
            _warning(
                "tool_output_too_large",
                f"{stage}: 도구 결과 {runner.too_large}건이 {TOOL_OUTPUT_MAX_CHARS}자를 넘어 오류 글로 돌려줬다",
            )
        )
    return warnings


NON_FINITE: Final = {"nan": "NaN", "inf": "Infinity", "-inf": "-Infinity"}
"""모델 인자의 NaN·Infinity(json.loads 가 받는 JSON 밖 낱말) → 검사 기록에 싣는 글자(그 낱말 그대로)."""


def json_safe(value: Any) -> Any:
    """검사 기록의 메아리 칸(인자 그대로를 비추는 칸)에 싣는 사본: 유한하지 않은 float 를 글자 "NaN"·"Infinity"·
    "-Infinity" 로 바꾼다 — 단계 산출물은 JSON 으로 왕복해야 해서(run_flow, allow_nan=False) 그대로 실으면 흐름이
    멈춘다.
    도구 실행에 들어간 인자와 모델에 돌려준 글은 코랩 그대로다(감독 처분 — 코랩에는 메아리 기록이 없다)."""
    if isinstance(value, float) and not math.isfinite(value):
        return NON_FINITE[repr(value)]
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in cast("dict[Any, Any]", value).items()}
    if isinstance(value, list):
        return [json_safe(item) for item in cast("list[Any]", value)]
    return value


def failure_of(end: Ended) -> dict[str, str | None]:
    """실패한 끝 → 결과 꼴의 failure(kind·budgetSource 는 parts, message 는 끝의 글 그대로)."""
    parts = cast("FailureParts", end.parts)
    return {"kind": parts.kind, "budgetSource": parts.budget_source, "message": str(end.message)}


# ── 단계 ───────────────────────────────────────────────────────────────────────────────────


def _cost_ok(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float) and math.isfinite(value) and value > 0


def check_costs(costs: object) -> StageCosts:
    """단계 셋의 비용 상한(bool 아닌 유한한 수 > 0). 아니면 FlowInputError."""
    if not isinstance(costs, StageCosts):
        raise FlowInputError(f"max_cost_usd 는 StageCosts(plan·review·insight)여야 한다: {type(costs).__name__}")
    for stage in STAGES:
        value = cast("object", getattr(costs, stage))
        if not _cost_ok(value):
            raise FlowInputError(f"max_cost_usd.{stage} 는 0 보다 큰 유한한 수여야 한다: {value!r}")
    return costs


def check_received(received: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        return shapes.check_input(received)
    except ValidationError as error:
        raise FlowInputError(f"입력이 {shapes.INPUT_SHAPE} 꼴이 아니다: {error.error_count()} errors") from None


def _scope(data_split: Mapping[str, Any]) -> dict[str, Any]:
    items = [item for theme in data_split.values() for item in theme]
    years = sorted({str(year) for item in items for year in item["values"]})
    return {
        "themes": [theme for theme in THEMES if theme in data_split],
        "itemCount": len(items),
        "keyItemCount": sum(1 for item in items if item["핵심데이터"] == "Y"),
        "years": years,
    }


def _load(inputs: DataverifyInputs, adapters: DataverifyAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    received = check_received(inputs.received)
    check_costs(inputs.max_cost_usd)
    data_split = split_themes(received["data"])
    warnings: list[dict[str, str]] = []
    if not data_split:
        warnings.append(
            _warning("no_target_theme", f"입력에 대상 테마({', '.join(THEMES)})가 없어 세 단계를 돌리지 않았다")
        )
    return StepOutput(data={"scope": _scope(data_split), "warnings": warnings})


def _company(received: Mapping[str, Any]) -> dict[str, Any]:
    company = received["company"]
    return {
        "company_name": company["name"],
        "sasb_industry": company["sasbIndustry"],
        "material_topics": company["materialTopics"],
        "reporting_year": company["reportingYear"],
    }


def _stage_out(
    stage: dict[str, Any],
    *,
    max_steps: int | None,
    model: str | None,
    warnings: list[dict[str, str]],
    prompt_id: str | None,
) -> StepOutput:
    return StepOutput(
        data={"stage": stage, "maxSteps": max_steps, "promptId": prompt_id, "model": model, "warnings": warnings}
    )


PLAN_NOT_RUN: Final[dict[str, Any]] = {
    "status": "not_run",
    "partial": None,
    "formulas": [],
    "raw": None,
    "failure": None,
}
REVIEW_NOT_RUN: Final[dict[str, Any]] = {
    "status": "not_run",
    "partial": None,
    "report": None,
    "checks": [],
    "failure": None,
}
INSIGHT_NOT_RUN: Final[dict[str, Any]] = {
    "status": "not_run",
    "partial": None,
    "report": None,
    "rows": [],
    "rowsParsed": "none",
    "sources": [],
    "failure": None,
}


def _not_run(stage: dict[str, Any]) -> StepOutput:
    return _stage_out(dict(stage), max_steps=None, model=None, warnings=[], prompt_id=None)


def _plan(inputs: DataverifyInputs, adapters: DataverifyAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    data_split = split_themes(inputs.received["data"])
    if not data_split:
        return _not_run(PLAN_NOT_RUN)
    system, user = prompts.plan_prompt(**_company(inputs.received), data_split=data_split, texts=inputs.texts)
    run = run_loop(
        adapters.llm,
        stage="plan",
        system=system,
        user=user,
        data_split=data_split,
        max_steps=prompts.PLAN_MAX_STEPS,
        max_cost_usd=inputs.max_cost_usd.plan,
        tags=inputs.tags,
        route=inputs.route,
        max_output_tokens=inputs.max_output_tokens,
        temperature=inputs.temperature,
    )
    end = ended(run.result)
    stage: dict[str, Any]
    if end.status == "failed":
        stage = {
            "status": "failed",
            "partial": None,
            "formulas": [],
            "raw": None,
            "failure": failure_of(end),
        }
    else:
        raw = cast("str", end.text)
        hints = parse_hints(raw, reraise=_soft_deadline)
        if hints is None:
            failure = {
                "kind": "unparsable",
                "budgetSource": None,
                "message": "계산 Plan 의 답이 글자 원소의 python list 가 아니다",
            }
            stage = {"status": "failed", "partial": None, "formulas": [], "raw": raw, "failure": failure}
        else:
            stage = {"status": "done", "partial": end.partial, "formulas": hints, "raw": raw, "failure": None}
    return _stage_out(
        stage,
        max_steps=prompts.PLAN_MAX_STEPS,
        model=end.model,
        warnings=runner_warnings("plan", run.runner),
        prompt_id=prompts.PROMPT_IDS["plan"],
    )


def _review(inputs: DataverifyInputs, adapters: DataverifyAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    plan = cast("dict[str, Any]", carried["plan"].data["stage"])
    data_split = split_themes(inputs.received["data"])
    if not data_split or plan["status"] != "done":
        return _not_run(REVIEW_NOT_RUN)
    formulas = cast("list[str]", plan["formulas"])
    steps = review_steps(formulas, REVIEW_MAX_STEPS_CAP)
    system, user = prompts.review_prompt(hints=formulas, data_split=data_split, texts=inputs.texts)
    run = run_loop(
        adapters.llm,
        stage="review",
        system=system,
        user=user,
        data_split=data_split,
        max_steps=steps.loop_steps,
        max_cost_usd=inputs.max_cost_usd.review,
        tags=inputs.tags,
        route=inputs.route,
        max_output_tokens=inputs.max_output_tokens,
        temperature=inputs.temperature,
    )
    end = ended(run.result)
    checks = [
        wire.to_check(record.seq, record.name, json_safe(record.args), record.output, tolerance=prompts.TOLERANCE)
        for record in run.runner.records
    ]
    stage: dict[str, Any]
    if end.status == "failed":
        stage = {
            "status": "failed",
            "partial": None,
            "report": None,
            "checks": checks,
            "failure": failure_of(end),
        }
    else:
        stage = {"status": "done", "partial": end.partial, "report": end.text, "checks": checks, "failure": None}
    warnings: list[dict[str, str]] = []
    if steps.capped:
        warnings.append(
            _warning(
                "review_steps_capped",
                f"검토 걸음 {prompts.review_max_steps(formulas)}(산식 {len(formulas)}×3)을 천장 "
                f"{REVIEW_MAX_STEPS_CAP}으로 줄였다(프롬프트의 걸음 글은 그대로)",
            )
        )
    warnings.extend(runner_warnings("review", run.runner))
    return _stage_out(
        stage,
        max_steps=steps.loop_steps,
        model=end.model,
        warnings=warnings,
        prompt_id=prompts.PROMPT_IDS["review"],
    )


def _citations(result: ToolLoopResult) -> list[Mapping[str, Any]]:
    found: tuple[UrlCitation, ...] = result.citations if isinstance(result, ToolLoopDone) else ()
    return [{"url": citation.url, "title": citation.title} for citation in found]


def _insight(inputs: DataverifyInputs, adapters: DataverifyAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    data_split = split_themes(inputs.received["data"])
    if not data_split:
        return _not_run(INSIGHT_NOT_RUN)
    system, user = prompts.insight_prompt(**_company(inputs.received), data_split=data_split, texts=inputs.texts)
    warnings: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    if inputs.web_search:
        run = run_loop(
            adapters.llm,
            stage="insight",
            system=system,
            user=user,
            data_split=data_split,
            max_steps=prompts.INSIGHT_MAX_STEPS,
            max_cost_usd=inputs.max_cost_usd.insight,
            tags=inputs.tags,
            route=inputs.route,
            max_output_tokens=inputs.max_output_tokens,
            temperature=inputs.temperature,
        )
        end = ended(run.result)
        max_steps = prompts.INSIGHT_MAX_STEPS
        if end.status == "done":
            sources = cast("list[dict[str, Any]]", wire.to_sources(_citations(run.result)))
            if not isinstance(run.result, ToolLoopFailed) and run.result.hosted_calls == 0:
                warnings.append(
                    _warning(
                        "insight_no_web_search", "인사이트가 web_search 를 한 번도 실행하지 않았다(프롬프트는 1회 이상)"
                    )
                )
        warnings.extend(runner_warnings("insight", run.runner))
    else:
        request = CallRequest[str](
            prompt=prompts.PROMPT_IDS["insight"],
            route=inputs.route,
            tags=inputs.tags,
            vars={"system": system, "user": user},
            max_output_tokens=inputs.max_output_tokens,
            timeout_ms=TIMEOUT_MS,
            temperature=inputs.temperature,
        )
        end = ended_call(adapters.llm.call(request))
        max_steps = 1
        warnings.append(
            _warning("web_search_disabled", "web_search 를 끄고 인사이트를 도구 없이 한 번 불렀다(출처 없음)")
        )
    stage: dict[str, Any]
    if end.status == "failed":
        parts = cast("FailureParts", end.parts)
        stage = {**INSIGHT_NOT_RUN, "status": "failed", "failure": failure_of(end), "partialText": parts.partial_text}
    else:
        text = cast("str", end.text)
        rows, parsed = wire.to_insight_rows(text)
        stage = {
            "status": "done",
            "partial": end.partial,
            "report": text,
            "rows": rows,
            "rowsParsed": parsed,
            "sources": sources,
            "failure": None,
        }
    return _stage_out(
        stage, max_steps=max_steps, model=end.model, warnings=warnings, prompt_id=prompts.PROMPT_IDS["insight"]
    )


def _report(inputs: DataverifyInputs, adapters: DataverifyAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    load = carried["load"].data
    stages = {name: carried[name].data for name in STAGES}
    ran = [name for name in STAGES if cast("dict[str, Any]", stages[name]["stage"])["status"] != "not_run"]
    models = [stages[name]["model"] for name in ran if stages[name]["model"] is not None]
    warnings = list(cast("list[dict[str, str]]", load["warnings"]))
    for name in STAGES:
        warnings.extend(cast("list[dict[str, str]]", stages[name]["warnings"]))
    result: dict[str, Any] = {
        "schemaVersion": shapes.RESULT_SHAPE,
        "company": inputs.received["company"],
        "scope": load["scope"],
        "settings": {
            "model": models[-1] if models else None,
            "tolerance": repr(prompts.TOLERANCE),
            "temperature": repr(inputs.temperature) if ran else None,
            "maxSteps": {name: stages[name]["maxSteps"] for name in STAGES},
            "promptIds": {name: stages[name]["promptId"] for name in STAGES},
        },
        "plan": stages["plan"]["stage"],
        "review": stages["review"]["stage"],
        "insight": stages["insight"]["stage"],
        "warnings": warnings,
    }
    try:
        shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)
    except ValidationError as error:
        raise FlowOutputError(
            f"결과가 {shapes.RESULT_SHAPE} 꼴을 지나지 못했다: {error.error_count()} errors"
        ) from None
    report = OutputFile(name=xlsx.FILE_NAME, media_type=xlsx.MEDIA_TYPE, content=xlsx.build(result))
    return StepOutput(data={"results": [result, dict(digest(result))]}, files=(report,))


FLOW: Final = make_flow(
    module="dataverify",
    id=FLOW_ID,
    input_shape=shapes.INPUT_SHAPE,
    inputs=DataverifyInputs,
    adapters=DataverifyAdapters,
    result_shapes=(shapes.RESULT_SHAPE, DIGEST_SHAPE),
    output_files=(xlsx.FILE_NAME,),
    steps=(
        FlowStep(name="load", run=_load),
        FlowStep(name="plan", run=_plan),
        FlowStep(name="review", run=_review),
        FlowStep(name="insight", run=_insight),
        FlowStep(name="report", run=_report),
    ),
)


# ── dry-run 어림(견본 실행 발주서의 재료 — 공급사 호출 0) ──────────────────────────────────────


def estimate(inputs: DataverifyInputs, llm: ToolLoopLlm, *, hints_count: int | None = None) -> dict[str, Any]:
    """단계 셋의 비용 위끝을 공급사를 부르지 않고 어림한다(core 의 dry_run_tools·dry_run). 검토는 산식 수를 모르면
    천장(REVIEW_MAX_STEPS_CAP) 걸음으로, 알면 review_steps 로. 입력 꼴·비용 상한이 틀리면 FlowInputError.

    꼴: {perStage: {plan|review|insight: {maxSteps, loopUpperBoundUsd, maxProviderCalls}}, totalUpperBoundUsd,
    unestimated: [..], assumptions: [..]}. 대상 테마가 없으면 단계마다 null·합 0(세 단계를 돌리지 않는다)."""
    received = check_received(inputs.received)
    costs = check_costs(inputs.max_cost_usd)
    data_split = split_themes(received["data"])
    assumptions = [
        "어림이다(실측 아님): 걸음마다 출력 상한을 다 쓰고 그 출력이 다음 걸음 입력에 다시 실린다고 본 위끝",
        "도구 결과 글자가 다음 걸음 입력에 쌓이는 몫은 들지 않는다(tool_outputs)",
        "실제 지출은 단계마다 max_cost_usd 가 막는다 — 공급사를 부르기 전에만 보므로 한 걸음만큼 넘칠 수 있다",
        "web_search 를 끈 인사이트(도구 없는 호출 한 번)에는 max_cost_usd 가 실리지 않는다",
    ]
    if not data_split:
        return {
            "perStage": dict.fromkeys(STAGES),
            "totalUpperBoundUsd": 0.0,
            "unestimated": [],
            "assumptions": [*assumptions, "대상 테마가 없어 세 단계를 돌리지 않는다"],
        }
    company = _company(received)
    count = REVIEW_MAX_STEPS_CAP // 3 if hints_count is None else hints_count
    hints = [""] * count
    review_loop = REVIEW_MAX_STEPS_CAP if hints_count is None else review_steps(hints, REVIEW_MAX_STEPS_CAP).loop_steps
    if hints_count is None:
        assumptions.append(f"산식 수를 몰라 검토를 천장 {REVIEW_MAX_STEPS_CAP} 걸음으로 어림했다")
    assumptions.append("검토 프롬프트의 산식 글자는 빈 글로 어림했다(산식 글자 몫은 들지 않는다)")

    plan_system, plan_user = prompts.plan_prompt(**company, data_split=data_split, texts=inputs.texts)
    review_system, review_user = prompts.review_prompt(hints=hints, data_split=data_split, texts=inputs.texts)
    insight_system, insight_user = prompts.insight_prompt(**company, data_split=data_split, texts=inputs.texts)
    common: dict[str, Any] = {
        "tags": inputs.tags,
        "route": inputs.route,
        "max_output_tokens": inputs.max_output_tokens,
        "temperature": inputs.temperature,
    }
    loops: list[tuple[Stage, ToolCallRequest]] = [
        (
            "plan",
            loop_request(
                stage="plan",
                system=plan_system,
                user=plan_user,
                max_steps=prompts.PLAN_MAX_STEPS,
                max_cost_usd=costs.plan,
                **common,
            ),
        ),
        (
            "review",
            loop_request(
                stage="review",
                system=review_system,
                user=review_user,
                max_steps=review_loop,
                max_cost_usd=costs.review,
                **common,
            ),
        ),
    ]
    if inputs.web_search:
        loops.append(
            (
                "insight",
                loop_request(
                    stage="insight",
                    system=insight_system,
                    user=insight_user,
                    max_steps=prompts.INSIGHT_MAX_STEPS,
                    max_cost_usd=costs.insight,
                    **common,
                ),
            )
        )
    per_stage: dict[str, Any] = {}
    unestimated: list[str] = []
    for stage, request in loops:
        loop = llm.dry_run_tools(request).tool_loop
        if loop is None:
            raise AssertionError("dry_run_tools 는 고리 어림을 낸다")
        per_stage[stage] = {
            "maxSteps": loop.max_steps,
            "loopUpperBoundUsd": loop.loop_upper_bound_usd,
            "maxProviderCalls": loop.max_provider_calls,
        }
        unestimated.extend(part for part in loop.unestimated if part not in unestimated)
    if not inputs.web_search:
        report = llm.dry_run(
            CallRequest[str](
                prompt=prompts.PROMPT_IDS["insight"],
                route=inputs.route,
                tags=inputs.tags,
                vars={"system": insight_system, "user": insight_user},
                max_output_tokens=inputs.max_output_tokens,
                timeout_ms=TIMEOUT_MS,
                temperature=inputs.temperature,
            )
        )
        per_stage["insight"] = {
            "maxSteps": 1,
            "loopUpperBoundUsd": report.estimate.cost_upper_bound_usd,
            "maxProviderCalls": 1,
        }
        assumptions.append("web_search 를 꺼 인사이트는 도구 없는 호출 한 번이다")
    total = round_usd(sum(cast("float", per_stage[stage]["loopUpperBoundUsd"]) for stage in STAGES))
    return {
        "perStage": {stage: per_stage[stage] for stage in STAGES},
        "totalUpperBoundUsd": total,
        "unestimated": unestimated,
        "assumptions": assumptions,
    }
