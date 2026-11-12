"""흐름 greenwash.rejudge@E0 — 검토 화면의 「근거 고치기 → 재판단」(밴드 GRJ1, 결정 MARC-ENT-617, 화면 GW-05 r4).

원 실행(greenwash.colab@E0)의 문장 하나를 사람이 고친 근거(남긴 AI 칩 + 더한 조각)로 **원 실행의 AI 설정 판 그대로**
한 번 다시 판정한다. 판정 함수는 엔진(engines/e0/checker.py)의 eval_high_mid_or_nonrisk·eval_low_only 를 부르기만
한다(ENT-442 — 엔진 사본 0). 문서 없는 흐름이다(BINDINGS.register_documentless — 입력은 옵션뿐, apps.py).

    옵션     contracts/rejudge_shapes.GreenwashRejudgeOptions(서버가 굳힌다 — service/actions/rejudge.py)
    결과     greenwash.rejudge@1(contracts/rejudge_shapes.GreenwashRejudgeResult)
    단계     judge 하나

★ 만드는 길은 그린 경로 하나다(POST /greenwash/runs/{runId}/items/{itemIndex}/rejudge, 덧붙임 3·감독 R2): 그 경로가
  creating(options, versions) 안에서만 runs 의 create_run 을 부르고, 끼움의 check_options 와 versions_with 가 그
  문(contextvar, _from_review 한 곳)을 본다. 문이 비었거나 옵션이 다르면 check_options 가 RunOptionsRejected —
  POST /runs 로 바로 만들기도, 실패한 재판단을 resumeFromRunId 로 이어 돌기도(create_run 은 이어 돌기에서
  versions_with 를 부르지 않고 앞 판을 베낀다 — check_options 는 부른다) 400 invalid_options(행 0). versions_with 의
  같은 검사는 그물이다(검증 1 B1).
  문은 프로세스 안 값이라 HTTP 로 지어 넣을 수 없고, creating 을 벗어나면(예외여도) 되돌린다.
★ 판(versions)은 원 실행의 것을 베낀다(Q2 — 같은 실행 안 일관). 만들 때 GreenwashBinding.run_setting 으로 지금 다시
  지을 수 있는지 보고, 못 지으면 RunVersionsRejected(만들기 409 — 행 0).

이 파일은 순수다(django 0 — .importlinter 계약 다).
"""

from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.core.calc.ai_settings import AcceptedStep
from esgapi.core.flows.binding import RunContext, RunOptionsRejected, RunVersionsMismatch, RunVersionsRejected
from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, FlowStep, StepContext, StepOutput
from esgapi.core.llm.types import Tags
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.engines.e0.checker import GreenwashingChecker
from esgapi.greenwash.engines.e0.heuristics import cap_evidence_context, normalize_text_for_llm
from esgapi.greenwash.engines.e0.ports import ChatPort
from esgapi.greenwash.engines.e0.prompts import PromptPack
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.flows.binding_e0 import NO_SETTING, GreenwashBinding

FLOW_ID: Final = "greenwash.rejudge@E0"
RESULT_SHAPE: Final = "greenwash.rejudge@1"
INPUT_SHAPE: Final = "greenwash.rejudge-options@1"
OPTIONS_MAX_OCTETS: Final = 64 * 1024
"""옵션의 앱 상한(바이트). 더한 조각 10 × 1,000자(한글 3바이트)와 칩 여섯·문장을 넉넉히 덮는다."""
NOT_FROM_REVIEW: Final = "재판단은 검토 화면의 [재판단]으로만 만들 수 있어요"


@dataclass(frozen=True, slots=True)
class _Gate:
    options: Mapping[str, object]
    versions: Mapping[str, object]


_GATE: ContextVar[_Gate | None] = ContextVar("greenwash_rejudge_gate", default=None)


@contextmanager
def creating(options: Mapping[str, object], versions: Mapping[str, object]) -> Generator[None]:
    """그린 경로(service/actions/rejudge.py)가 create_run 을 부르는 동안만 문을 연다. 벗어나면(예외여도) 닫는다."""
    token = _GATE.set(_Gate(options=dict(options), versions=dict(versions)))
    try:
        yield
    finally:
        _GATE.reset(token)


def _from_review(options: Mapping[str, object]) -> _Gate | None:
    """이 옵션으로 그린 경로가 문을 열었는가 — 열었으면 그 문, 아니면 None(check_options·versions_with 가 같이 쓴다)."""
    gate = _GATE.get()
    if gate is None or dict(gate.options) != dict(options):
        return None
    return gate


def gate_open() -> bool:
    """문이 열려 있는가(시험이 요청 사이에 새지 않는지 본다)."""
    return _GATE.get() is not None


LOW_TAGS: Final = ("선언적 문장",)
"""Low 길의 고정 위험 태그 — 엔진 analyze_page 의 Low 확정 칸 그대로(engines/e0/checker.py)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class RejudgeInputs:
    """greenwash.rejudge-options@1 을 받은 값과 원 실행의 판(GreenwashBinding.run_setting — 칸 뜻은 colab 의
    같은 이름)."""

    options: Mapping[str, object]
    criteria: GreenwashCriteria | None = None
    prompts: PromptPack | None = None
    model: AcceptedStep | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class RejudgeAdapters:
    """흐름의 어댑터. 대화는 LlmChatBridge(ctx.llm()) — judge 가 원 판으로 바꿔 끼운다(colab.judge_chat)."""

    llm: ChatPort


def evidence_context(kept: Sequence[str], added: Sequence[Mapping[str, object]], *, per_chunk: int, total: int) -> str:
    """엔진에 넣는 근거 글. 엔진 build_evidence 와 같은 꼴: 조각마다 normalize_text_for_llm(strip) → per_chunk 를 넘으면
    자르고 " ..." → 쪽이 있으면 `[p.N]\n<글>`(칩·쪽 없는 조각은 글만, 감독 Q1) → "\n\n" 로 이어 strip → 전체
    cap_evidence_context(total). 차례는 남긴 칩(기준 판단 차례) 다음 더한 조각(받은 차례)."""
    pieces: list[tuple[str, object]] = [(chip, None) for chip in kept]
    pieces += [(str(piece["text"]), piece.get("page")) for piece in added]
    parts: list[str] = []
    for text, page in pieces:
        content = normalize_text_for_llm(text.strip())
        if len(content) > per_chunk:
            content = content[:per_chunk] + " ..."
        parts.append(content if page is None else f"[p.{page}]\n{content}")
    return cap_evidence_context("\n\n".join(parts).strip(), max_total_chars=total)


def evidence_pages(added: Sequence[Mapping[str, object]]) -> list[int]:
    """보낸 조각 가운데 쪽이 있는 것의 쪽(오름·겹침 없음)."""
    return sorted({int(cast("int", piece["page"])) for piece in added if piece.get("page") is not None})


def _strs(value: object) -> list[str]:
    return [str(v) for v in cast("list[object]", value)] if isinstance(value, list) else []


def prompt_version_of(options: Mapping[str, object]) -> str:
    """판정 프롬프트 판 글자. 만들 때 원 실행의 config 로 셈해 굳힌 promptVersion 칸(GRS1 — MARC-ISSUE-632)이 있으면
    그것, 없으면(그 칸 앞에 만든 옛 재판단 옵션) 지금 코드의 SCAN_CONFIG 로 셈한다."""
    frozen = options.get("promptVersion")
    if isinstance(frozen, str) and frozen:
        return frozen
    return colab.judged_prompt_version(dict(colab.SCAN_CONFIG))


def judge(inputs: RejudgeInputs, adapters: RejudgeAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    """원 실행의 판으로 문장 하나를 다시 판정한다 — 엔진의 eval_low_only·eval_high_mid_or_nonrisk 를 부르기만 한다.
    대화 실패(공급사 오류·시간)는 그대로 올라가 실행이 failed 가 된다(기준 판단은 앞 그대로 — 읽는 쪽
    review.judgments)."""
    options = inputs.options
    kept = _strs(options["kept"])
    added = cast("list[dict[str, object]]", list(cast("list[object]", options["added"])))
    sentence = str(options["sentence"])
    context = evidence_context(
        kept,
        added,
        per_chunk=int(cast("int", options["maxCharsPerChunk"])),
        total=int(cast("int", options["maxCharsEvidenceTotal"])),
    )
    version = prompt_version_of(options)
    llm, pack = colab.judge_chat(
        adapters.llm, prompts=inputs.prompts, criteria=inputs.criteria, model=inputs.model, version=version
    )
    checker = GreenwashingChecker(docs=[], vectorstore=None, llm=llm, cfg=colab.scan_cfg(), prompts=pack)
    pages = evidence_pages(added)
    outcome = "judged"
    if options["lowOnly"] is True:
        low: dict[str, Any] = checker.eval_low_only(sentence, context)
        item: dict[str, object] = {
            "level": "Low",
            "riskTags": list(LOW_TAGS),
            "confirmedInEvidence": [],
            "missingFields": [],
            "reasonBullets": _strs(low.get("reason_bullets", [])),
            "fixParagraph": str(low.get("fix_paragraph", "")),
            "evidencePages": pages,
            "evidenceInternal": "",
        }
    else:
        out: dict[str, Any] = checker.eval_high_mid_or_nonrisk(sentence, context)
        decision = out.get("decision", "Mid")
        if decision == "NonRisk":
            outcome = "nonrisk"
        item = {
            "level": None if decision == "NonRisk" else decision,
            "riskTags": _strs(out.get("risk_tags", [])),
            "confirmedInEvidence": _strs(out.get("confirmed_in_evidence", [])),
            "missingFields": _strs(out.get("missing_fields", [])),
            "reasonBullets": _strs(out.get("reason_bullets", [])),
            "fixParagraph": str(out.get("fix_paragraph", "")),
            "evidencePages": pages,
            "evidenceInternal": str(out.get("evidence_internal", "")),
        }
    result: dict[str, object] = {
        "schemaVersion": RESULT_SHAPE,
        "fromRunId": options["fromRunId"],
        "itemIndex": options["itemIndex"],
        "sentence": sentence,
        "kept": kept,
        "added": added,
        "outcome": outcome,
        "item": item,
    }
    return StepOutput(data={"results": [result]})


STEPS: Final[tuple[FlowStep[RejudgeInputs, RejudgeAdapters], ...]] = (FlowStep(name="judge", run=judge),)

FLOW: Final = make_flow(
    module="greenwash",
    id=FLOW_ID,
    input_shape=INPUT_SHAPE,
    inputs=RejudgeInputs,
    adapters=RejudgeAdapters,
    result_shapes=(RESULT_SHAPE,),
    output_files=(),
    steps=STEPS,
)


def accept_options(options: Mapping[str, object]) -> None:
    """옵션 꼴(GreenwashRejudgeOptions, strict·모르는 키 금지). 어기면 RunOptionsRejected(한 문장).
    꼴은 늦게 들인다 — 이 파일은 등록 길(apps.py)에 있어 pydantic 꼴 짓기를 시작에 싣지 않는다(registration.py 머리)."""
    from pydantic import ValidationError

    from esgapi.greenwash.contracts.rejudge_shapes import OPTIONS

    try:
        OPTIONS.validate_python(dict(options), strict=True)
    except ValidationError as refused:
        raise RunOptionsRejected("재판단 옵션의 꼴이 맞지 않아요") from refused


class RejudgeBinding:
    """greenwash.rejudge@E0 의 끼움(문서 없는 갈래 — DocumentlessBinding + DocumentlessFactsBinding)."""

    def __init__(self, *, setting: GreenwashBinding) -> None:
        self.setting = setting

    def check_options(self, options: Mapping[str, object]) -> None:
        accept_options(options)
        if _from_review(options) is None:  # 새로 만들기와 이어 돌기 둘 다 여기를 지난다(검증 1 B1)
            raise RunOptionsRejected(NOT_FROM_REVIEW)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        # 판은 늘 versions_with(원 실행의 판)다 — 이 길은 실행기·만들기가 부르지 않는다(DocumentlessFactsBinding)
        raise RunVersionsRejected(NOT_FROM_REVIEW)

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        gate = _from_review(options)
        if gate is None:  # 그물 — check_options 가 먼저 막는다
            raise RunVersionsRejected(NOT_FROM_REVIEW)
        versions = {key: value for key, value in gate.versions.items() if key != "flow"}
        try:
            self.setting.run_setting(company_id=company_id, versions=versions)
        except RunVersionsMismatch as refused:
            raise RunVersionsRejected(
                "이 점검을 돌린 AI 설정 판을 지금 다시 쓸 수 없어 재판단할 수 없어요"
            ) from refused
        return versions

    def inputs(self, options: Mapping[str, object], *, company_id: int) -> RejudgeInputs:
        return RejudgeInputs(options=dict(options))  # 판 없는 길 — 이 흐름의 실행은 늘 versions 가 있어 닿지 않는다

    def inputs_with(
        self, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> RejudgeInputs:
        """원 실행의 판(versions 는 만들 때 베낀 것)을 다시 지어 싣는다 — colab 끼움 inputs_with 와 같은 run_setting."""
        setting = self.setting.run_setting(
            company_id=company_id, versions={key: value for key, value in versions.items() if key != "flow"}
        )
        if setting == NO_SETTING:
            return RejudgeInputs(options=dict(options))
        return RejudgeInputs(
            options=dict(options), criteria=setting.criteria, prompts=setting.prompts, model=setting.model
        )

    def adapters(self, ctx: RunContext) -> RejudgeAdapters:
        tags = Tags(tenant=str(ctx.company_id), module=ctx.module)
        return RejudgeAdapters(llm=colab.LlmChatBridge(ctx.llm(), route=self.setting.chat_route, tags=tags))
