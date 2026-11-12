"""흐름 materiality.iro@155 — 중대성평가 IRO 코랩 1부(규제·키워드·컨트로버시 조사)와 2부(환경·사회 영향·재무 영향·재무
Impact Pathway)를 사람 손 없이 한 실행으로 잇는다(밴드 IR2b, MARC-ENT-439·MARC-ENT-425).

    load → regulation → keywords → controversy → report → part2_seed → impact → financial → pathway → report_iro

입력 꼴 materiality.input@1(IroInputs.received) + 「오늘」(IroInputs.today), 결과 꼴 materiality.result@2 와 목록 요약
materiality.digest@1(밴드 IR3c),
출력 파일 둘(1부 리서치 materiality-websearch.xlsx·최종 보고 materiality-final-report.xlsx). 단계 몸은 새로 짓지
않는다 — 1부 다섯은 colab_155.FLOW.run_step 으로, 2부 넷은 part2_155.STEPS 의 함수로 그대로 부르고, 여기서는
입력·어댑터를 그 꼴로 바꿔 넘기고 씨앗과 끝 단계만 짓는다(1부 `_` 함수 import 0).

- load        「오늘」 검사 → 1부 load(입력 꼴·비용 상한 검사, 틀리면 FlowInputError — 공급사 호출 0) → dateRange 읽기
              (contracts/wire.parse_date_range — 문법 밖·달력에 없는 날·시작 > 끝이면 FlowInputError). data 에 window
              {start, end}(ISO 글)를 더한다.
- regulation·keywords·controversy·report   1부 그대로. 1부 호출에는 기간을 싣지 않는다(코랩대로 — 425 ①). report 의 @1
              결과와 1부 엑셀은 중간 산출물로만 남는다.
- part2_seed  1부 결과(@1)의 복사본에서 dateRange 밖 항목을 뺀 판(wire.part1_in_window)으로 2부 입력을 짓는다(425 ②).
              @2 의 part1 칸은 거르지 않은 1부 원본 그대로다. 경고 = 1부에서 옮긴 것 + 기간 경고(items_out_of_range·
              item_date_unreadable) + 1부 호출의 잘림(answer_truncated, subtopic null). spentUsd = 1부 지출 누계 —
              max_cost_usd 하나가 두 부를 덮는다.
- impact·financial·pathway   2부 그대로.
- report_iro  2부 report2 그대로(@2 조립·검사·최종 엑셀) + 1부 엑셀(carried 의 report 파일)을 함께 낸다. 결과 곁에
              @2 에서 센 요약 digest@1(outputs/digest — 목록 GET /materiality/runs 가 읽는다)을 둘째로 낸다.

「오늘」은 부르는 쪽(IR3a 끼움)이 실행 시각의 Asia/Seoul 날짜로 넣는다 — 이 파일은 시계를 읽지 않는다. 설정·환경
변수·키를 읽지 않고 SDK 클라이언트를 짓지 않는다. 다시 올린 엑셀 읽기(Part2Source shortlist)는 1차에 없다(439).
estimate_iro 는 공급사를 부르지 않는 두 부의 비용 위끝 어림이다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final, cast

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, FlowInputError, FlowStep, StepContext, StepOutput
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.types import Tags
from esgapi.materiality.contracts import shapes, wire
from esgapi.materiality.contracts.digest_shapes import DIGEST_SHAPE
from esgapi.materiality.flows import colab_155, part2_155
from esgapi.materiality.outputs import final_xlsx, xlsx
from esgapi.materiality.outputs.digest import digest

FLOW_ID: Final = "materiality.iro@155"
PART1_STEPS: Final = ("regulation", "keywords", "controversy", "report")
"""load 뒤 1부 단계(colab_155.FLOW 의 이름 그대로 — 1부 단계가 carried 에서 이 이름으로 읽는다)."""
PART1_CALL_STEPS: Final = ("regulation", "keywords", "controversy")
REPORT2: Final = "report2"
"""part2_155.STEPS 의 끝 함수 이름(이 흐름에서는 report_iro 단계가 부른다)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class IroInputs:
    """흐름의 입력.

    received      materiality.input@1 의 받은 dict 그대로(검사만 하고 고치지 않는다)
    tags          core.llm 의 기록·비용 꼬리표(테넌트, 모듈 materiality)
    max_cost_usd  실행 하나(1부 + 2부)의 비용 상한(USD, 0 보다 큰 유한한 수. 기본값 없음)
    today         dateRange 「오늘까지」의 끝 날(부르는 쪽이 실행 시각의 Asia/Seoul 날짜로. datetime·bool·글은 거절)
    texts         템플릿 글 열일곱(IR4 — 기본값 없음, 기본 글은 colab_155.DEFAULT_TEXTS. 판이 덮는 칸은 열넷 — IRA3)
    research      1부 모델 칸(경로·temperature·출력 상한 — IR4, 코드 값 colab_155.CODE_RESEARCH). temperature 는 수
    analysis      2부 모델 칸(코드 값 part2_155.CODE_ANALYSIS). temperature 는 읽지 않는다(2부는 싣지 않는다 — 코랩)
    route1·route2 는 두 칸의 경로(읽기만 — IR4 앞 이름)
    """

    received: Mapping[str, Any]
    tags: Tags
    max_cost_usd: float
    today: date
    texts: colab_155.PromptTexts
    research: colab_155.StageModel
    analysis: colab_155.StageModel

    @property
    def route1(self) -> str:
        return self.research.route

    @property
    def route2(self) -> str:
        return self.analysis.route


@dataclass(frozen=True, slots=True, kw_only=True)
class IroAdapters:
    """흐름의 어댑터. llm 은 부르는 쪽이 지은 클라이언트(LlmClient 가 1부·2부 입구 둘 다 맞는다)."""

    llm: part2_155.Part2Llm


def part1_inputs(inputs: IroInputs) -> colab_155.MaterialityInputs:
    temperature = inputs.research.temperature
    if temperature is None:
        raise FlowInputError("1부(리서치 모델 칸)의 temperature 는 수여야 한다(코랩 1부는 늘 싣는다)")
    return colab_155.MaterialityInputs(
        received=inputs.received,
        tags=inputs.tags,
        max_cost_usd=inputs.max_cost_usd,
        route=inputs.research.route,
        texts=inputs.texts,
        temperature=temperature,
        max_output_tokens=inputs.research.max_output_tokens,
    )


def part2_inputs(inputs: IroInputs) -> part2_155.Part2Inputs:
    return part2_155.Part2Inputs(
        tags=inputs.tags,
        max_cost_usd=inputs.max_cost_usd,
        route=inputs.analysis.route,
        texts=inputs.texts,
        max_output_tokens=inputs.analysis.max_output_tokens,
    )


def check_today(value: object) -> date:
    """「오늘」은 date(datetime 아님). 아니면 FlowInputError."""
    if not isinstance(value, date) or isinstance(value, datetime):
        raise FlowInputError(f"today 는 date 여야 한다(datetime·글 아님): {type(value).__name__}")
    return value


def window_of(received: Mapping[str, Any], today: date) -> tuple[date, date]:
    """입력 dateRange → (시작, 끝). 못 읽으면 FlowInputError(받은 글은 싣지 않는다)."""
    window = wire.parse_date_range(received["dateRange"], today)
    if window is None:
        raise FlowInputError("dateRange 문법 밖(「YYYY-MM-DD~오늘까지」 또는 「YYYY-MM-DD~YYYY-MM-DD」, 시작 ≤ 끝)")
    return window


def _load(inputs: IroInputs, adapters: IroAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    today = check_today(inputs.today)
    out = colab_155.FLOW.run_step(
        "load", part1_inputs(inputs), colab_155.MaterialityAdapters(llm=adapters.llm), carried, ctx
    )
    start, end = window_of(inputs.received, today)
    return StepOutput(
        data={**out.data, "window": {"start": start.isoformat(), "end": end.isoformat()}}, files=out.files
    )


def _part1_step(name: str) -> FlowStep[IroInputs, IroAdapters]:
    def run(inputs: IroInputs, adapters: IroAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
        return colab_155.FLOW.run_step(
            name, part1_inputs(inputs), colab_155.MaterialityAdapters(llm=adapters.llm), carried, ctx
        )

    return FlowStep(name=name, run=run)


def _seed(inputs: IroInputs, adapters: IroAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    (part1,) = cast("list[dict[str, Any]]", carried["report"].data["results"])
    window = cast("dict[str, str]", carried["load"].data["window"])
    windowed, window_warnings = wire.part1_in_window(
        part1, date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
    )
    part2_input, moved = wire.part2_input_from_result(inputs.received, windowed)
    calls = [call for step in PART1_CALL_STEPS for call in cast("list[dict[str, Any]]", carried[step].data["calls"])]
    data: dict[str, object] = {
        "input": part2_input,
        "result": part1,
        "warnings": [*moved, *window_warnings, *wire.truncated_warnings(calls)],
        "spentUsd": carried["controversy"].data["spentUsd"],
    }
    return StepOutput(data=data)


PART2: Final = dict(part2_155.STEPS)


def _part2_step(name: str) -> FlowStep[IroInputs, IroAdapters]:
    step = PART2[name]

    def run(inputs: IroInputs, adapters: IroAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
        return step(part2_inputs(inputs), part2_155.Part2Adapters(llm=adapters.llm), carried, ctx)

    return FlowStep(name=name, run=run)


def _report_iro(inputs: IroInputs, adapters: IroAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    out = PART2[REPORT2](part2_inputs(inputs), part2_155.Part2Adapters(llm=adapters.llm), carried, ctx)
    (result,) = cast("list[dict[str, Any]]", out.data["results"])
    return StepOutput(data={"results": [result, dict(digest(result))]}, files=(*carried["report"].files, *out.files))


FLOW: Final = make_flow(
    module="materiality",
    id=FLOW_ID,
    input_shape=shapes.INPUT_SHAPE,
    inputs=IroInputs,
    adapters=IroAdapters,
    result_shapes=(shapes.RESULT_SHAPE_V2, DIGEST_SHAPE),
    output_files=(xlsx.FILENAME, final_xlsx.FILENAME),
    steps=(
        FlowStep(name="load", run=_load),
        *(_part1_step(name) for name in PART1_STEPS),
        FlowStep(name=part2_155.SEED, run=_seed),
        *(_part2_step(name) for name in part2_155.PHASES2),
        FlowStep(name="report_iro", run=_report_iro),
    ),
)


# ── dry-run 어림(공급사 호출 0) ──────────────────────────────────────────────────────────────


def estimate_iro(
    inputs: IroInputs, llm: part2_155.Part2Llm, *, assumed_searches_per_call: int = 1, assumed_fin_rows: int = 2
) -> dict[str, Any]:
    """두 부의 비용 위끝을 공급사를 부르지 않고 어림한다: 1부 colab_155.estimate + 2부 part2_155.estimate_part2.
    2부 입력은 1부를 돌리지 않았으니 규제·컨트로버시 글을 「제공된 … 정보 없음」으로 짓는다(실제 글 몫은 들지 않는다 —
    unestimated part2_context_text). today·dateRange·입력 꼴·비용 상한이 틀리면 FlowInputError.

    꼴: {part1: <colab_155.estimate>, part2: <part2_155.estimate_part2>, totalUpperBoundUsd: {withoutRetry, withRetry}
    (2부는 재시도가 없어 둘 다에 같은 값), maxProviderCalls(1부 + 2부), unestimated, assumptions}."""
    check_today(inputs.today)
    part1 = colab_155.estimate(part1_inputs(inputs), llm, assumed_searches_per_call=assumed_searches_per_call)
    window_of(inputs.received, inputs.today)
    not_run = wire.not_run("어림 — 1부를 돌리지 않았다.")
    unrun: dict[str, Any] = {
        "schemaVersion": shapes.RESULT_SHAPE,
        "part1": {
            "topics": [
                {"topic": t["topic"], "regulation": not_run, "controversy": not_run}
                for t in wire.engine_topics(inputs.received)
            ]
        },
        "warnings": [],
    }
    part2_input, _ = wire.part2_input_from_result(inputs.received, unrun)
    part2 = part2_155.estimate_part2(part2_input, part2_inputs(inputs), llm, assumed_fin_rows=assumed_fin_rows)
    total1 = cast("dict[str, float]", part1["totalUpperBoundUsd"])
    total2 = cast("float", part2["totalUpperBoundUsd"])
    unestimated = list(cast("list[str]", part1["unestimated"]))
    unestimated += [part for part in cast("list[str]", part2["unestimated"]) if part not in unestimated]
    unestimated.append("part2_context_text")
    return {
        "part1": part1,
        "part2": part2,
        "totalUpperBoundUsd": {
            "withoutRetry": round_usd(total1["withoutRetry"] + total2),
            "withRetry": round_usd(total1["withRetry"] + total2),
        },
        "maxProviderCalls": cast("int", part1["maxProviderCalls"]) + cast("int", part2["maxProviderCalls"]),
        "unestimated": unestimated,
        "assumptions": [
            *cast("list[str]", part1["assumptions"]),
            *cast("list[str]", part2["assumptions"]),
            "2부 입력의 규제·컨트로버시 글은 「제공된 … 정보 없음」으로 어림했다(part2_context_text)",
        ],
    }
