"""흐름 drafting.draft@v2 — 전년도 보고서 PDF 쪽 글 → S2(쪽 → 목차 잎) → S3(잎마다 개조식, 블록·문장 근거) →
drafting.bullets@3(밴드 RP1 ②·RP2b·RP2c, 결정 MARC-ENT-501·514 2번·3번·512). RAG·임베딩·Agent 0 — 쪽 글·블록 글을
호출의 user 에
직접 싣는다(카톡 10-01).
쪽 글의 원천은 core 문서 산출물(밴드 RP2a ②, 결정 MARC-ENT-514): 포트 ArtifactSource 가 그 문서(etag)의 분해 한 벌을
  얻고(있으면 저장소·파서 0 — 같은 문서 다시 생성은 재파싱 0), 쪽 글은 tools/blocks_text(어댑터 drafting-blocks@1)가
  읽기 뷰에서 편다.

단계:
  extract   ensure(문서, etag) → 산출물. 쪽 300 초과·본문 상한 넘음·분해 시간 초과(too_many_pages·too_large·
            parse_timeout, 행 too_large) → rejected too_large·before_map. 그 밖 거절 code·원본 못 읽음·꼴 어김
            (ArtifactInvalid) → 단계 실패(글에 code 만). 잠깐 장애(RunRetryLater)는 그대로 올린다(다시 넣음).
            모든 쪽이 빈 글 → NoTextLayer(실행 실패). data 에 artifactId·pagesSha256·epoch·parser·pages(쪽 크기).
            too_large 행이어도 artifactId·epoch·parser 는 그 행 값(결과 basis — §2-0 ⑤), 분해 거절(행 0)이면 null
  map       앞 실행(inputs.base)이 있으면 flows/reuse 로 계획: 열쇠가 맞으면 S2 목차 줄은 새·바뀐·rebuild 잎만(없으면
            묶음 0·호출 0), 안 바뀐 잎의 쪽은 앞 결과 그대로(keptPages). data 의 reuse 에 {baseRunId, reason, s2Keys,
            keptPages}.
            위끝 ⓐ(공급사 전): S2 묶음 전부의 dry_run 위끝 + S3 는 잎마다 바닥값(재료 0 — 프롬프트·출력 상한만, 옮김이
            확정된 잎은 뺌) >
            max_usd → rejected over_budget·before_map(호출 0). 아니면 묶음마다 S2 — 실패한 묶음은 failedBatches.
            data 에 묶음의 쪽 번호(groups) — draft·report 의 쪽↔잎 대조는 뷰를 다시 열지 않는다
  draft     위끝 ⓑ(첫 S3 전, 이어 돌면 남은 잎만): 달린 재료로 잰 S3 위끝 + 지금까지 지출 > max_usd → rejected
            over_budget·before_draft(mapping 은 싣고 잎은 전부 not_run). 아니면 잎마다(목차 차례) 쪽 0 →
            no_material, 옮길 잎(reuse.reusable)은 앞 결과를 그대로(재료·호출 0 — origin), 아니면 S3(재료 =
            engines/v2/material 의 블록·문장 표지 글) → 답 다듬기(v2/answers) → 결정적 출처 검사(v2/checks). 재료의 id
            겹침(GivenConflict)은 첫 S3 전에 단계 실패. 재료가 상한에 걸려 실은 블록이 0 이면 no_material +
            material_truncated. data 의 출처는 {documentId, blockId, page, index, blockBox}(글자 상자 0)
  report    상자 지을 새 출처가 있으면(옮긴 잎은 건너뜀) 뷰를 글자 자리째(places=True) 한 번 열어 출처마다 블록을
            다시 짓고(v2/material.locate — 같은 규칙이라 번호가 같다) 상자(v2/places). 블록을 못 찾으면 draft data 의
            blockBox·sentence null + source_block_missing(실행은 done) → 결과 조립(basis = extract data, base·
            reusedFrom, 어긋나면 base_not_reused) →
            validate_python(strict) → dump_python(mode="json"). 출력 파일 0
돈 가드(colab_158 꼴): 부르기 전마다 지출(spent_usd 포트 — 이 실행의 앞 시도까지 + 이 시도의 앞 호출) ≥ min(max_usd,
  그 단계 위끝) 이면 그 호출과 뒤는 budget_exceeded(공급사 0).
이어 돌기(progress_155 꼴): S2 묶음마다·S3 잎마다 ctx.checkpoint({answers, spentUsd}) — 다음 시도는 resume 의 끝난
  자리를
  건너뛴다(공급사 0). 쪽 글은 단계 data 에 싣지 않는다(data 상한 16MiB) — map·draft 는 extract 가 적은 artifactId 로
  단계마다 뷰를 한 번(글자 자리 0), report 는 상자가 필요할 때만 글자 자리째 한 번 연다(DB 한 번 — 저장소·파서 0).
실패 갈래 이름(core.llm): CutOff → truncated · Refused → refusal · TimedOut → timeout · SchemaMismatch(재시도 뒤) →
  schema_mismatch · BudgetExceeded → budget_exceeded · ProviderFailed → provider_error. 실패 글에 모델·공급사 글 0.
mock(처분 ⑧ 가): adapters.mock 이면 두 단계 경로가 `mock` — versions·입력은 그대로(temperature 는 칸 값, 위끝은
  min(칸 값, MOCK_MAX_OUTPUT_TOKENS) — 가상 모델 상한 4000 을 넘는 판도 단계 실패 0, MARC-ISSUE-490).
모델 값(밴드 RPA1 ②, 처분 ③): S2·S3 의 경로·temperature·출력 상한은 입력 칸 inputs.models(단계마다 StageModel — AI
  설정 판의 칸, 기본은 흐름 상수 CODE_MODELS). 결과 settings 는 경로만 싣는다(결과 꼴 그대로).

이 파일은 django·settings·service 를 모른다 — DB·저장소·파서는 포트(DraftAdapters)로만(.importlinter 다, 축 시험).
core 의 문서 산출물은 순수한 계약·뷰(core/documents/contract·view)만 import 한다.
"""

import copy
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final, Protocol, TypedDict, cast

from pydantic import TypeAdapter, ValidationError, with_config

from esgapi.core.documents.contract import ArtifactInvalid, ArtifactRef, ArtifactRefused, ArtifactUnreadable
from esgapi.core.documents.view import DocArtifactView
from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, FlowOutputError, FlowStep, NoTextLayer, StepContext, StepOutput
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.types import (
    BudgetExceeded,
    CutOff,
    DryRunReport,
    LlmResult,
    ProviderFailed,
    Refused,
    SchemaMismatch,
    Success,
    Tags,
    TimedOut,
)
from esgapi.drafting.contracts import shapes, wire
from esgapi.drafting.contracts.shapes import FORBID
from esgapi.drafting.engines.v1 import mapping, pages, prompts
from esgapi.drafting.engines.v2 import answers as answer_engine
from esgapi.drafting.engines.v2 import checks, material, places
from esgapi.drafting.engines.v2 import prompts as v2_prompts
from esgapi.drafting.engines.v2 import texts as v2_texts
from esgapi.drafting.engines.v2.texts import DEFAULT_TEXTS, PromptTexts
from esgapi.drafting.flows import reuse
from esgapi.drafting.tools import blocks_text

FLOW_ID: Final = "drafting.draft@v2"
MODULE: Final = "drafting"
PROMPT_IDS: Final = {"map": "drafting/map@1", "draft": "drafting/draft@2"}
MOCK_ROUTE: Final = "mock"
MOCK_MAX_OUTPUT_TOKENS: Final = 4000
"""가상 모델 mock-synthetic 의 maxOutputTokens(core/llm/data/models.synthetic.json — MARC-ISSUE-490, 번역
llm_bridge 와 같은 값). live 길은 쓰지 않는다."""
ROUTE: Final = "light-openai-41"
MAX_OUTPUT_TOKENS: Final = 4000
SCHEMA_RETRIES: Final = 1
TIMEOUT_MS: Final = 120_000
TEMPERATURE: Final = 0.0
TOO_LARGE_CODES: Final = frozenset({"too_many_pages", "too_large", "parse_timeout"})
TOO_BIG: Final = "문서의 분해 결과가 저장 상한을 넘는다."
TOO_SLOW: Final = "문서 분해가 시간 안에 끝나지 않았다."
CUT: Final = "재료가 상한(쪽 8,000자·전체 40,000자, 표지 포함)을 넘어 일부 블록·문장을 뺐다."
OVER_BUDGET: Final = "비용 위끝이 실행 상한(DRAFTING_RUN_MAX_USD)을 넘어 부르지 않았다."
NOT_RUN: Final = "비용 위끝이 실행 상한을 넘어 초안을 짓지 않았다."
CUT_ALL: Final = "재료가 상한을 넘어 실은 블록이 없다."
BLOCK_MISSING: Final = "근거 블록을 산출물에서 다시 찾지 못해 블록 상자만 남겼다."
NOT_REUSED: Final[Mapping[str, str]] = {
    "base_rejected": "앞 실행이 거절로 끝나 이어 받지 않고 처음부터 지었다.",
    "versions": "앞 실행과 판이 달라 이어 받지 않고 처음부터 지었다.",
    "document": "앞 실행과 문서 분해가 달라 이어 받지 않고 처음부터 지었다.",
    "settings": "앞 실행과 모델 경로·프롬프트가 달라 이어 받지 않고 처음부터 지었다.",
}
FAILURE_MESSAGES: Final[Mapping[str, str]] = {
    "unparsable": "모델의 답을 읽지 못했다.",
    "provider_error": "모델 공급사가 오류로 답했다.",
    "timeout": "모델 호출이 시간 안에 끝나지 않았다.",
    "refusal": "모델이 답을 거절했다.",
    "truncated": "모델의 답이 출력 상한에서 잘렸다.",
    "budget_exceeded": "실행 비용 상한에 닿아 부르지 않았다.",
    "schema_mismatch": "모델의 답이 요구한 JSON 꼴이 아니었다(다시 부른 뒤에도).",
}

__all__ = ["DEFAULT_TEXTS", "PromptTexts"]


# ── 모델 답의 꼴(공급사에 싣는 JSON 스키마) ──


@with_config(FORBID)
class MapPage(TypedDict):
    page: int
    keys: list[str]


@with_config(FORBID)
class MapAnswer(TypedDict):
    pages: list[MapPage]


@with_config(FORBID)
class DraftSource(TypedDict):
    block: str
    s: int | None


@with_config(FORBID)
class DraftLine(TypedDict):
    text: str
    sources: list[DraftSource]


@with_config(FORBID)
class DraftAnswer(TypedDict):
    bullets: list[DraftLine]


# ── 입력·포트 ──


@dataclass(frozen=True, slots=True, kw_only=True)
class StageModel:
    """한 단계(S2·S3)가 부르는 모델 값 — AI 설정 판의 모델 칸 하나(경로·temperature·출력 상한, RPA1 ②)."""

    route: str
    temperature: float
    max_output_tokens: int


@dataclass(frozen=True, slots=True, kw_only=True)
class StageModels:
    """S2(map)·S3(draft)의 모델 값."""

    map: StageModel
    draft: StageModel


CODE_MODEL: Final = StageModel(route=ROUTE, temperature=TEMPERATURE, max_output_tokens=MAX_OUTPUT_TOKENS)
CODE_MODELS: Final = StageModels(map=CODE_MODEL, draft=CODE_MODEL)
"""코드 값의 모델(흐름 상수 그대로 — 기본 판·옛 실행의 요청은 RPA1 앞과 바이트 같다)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DraftInputs:
    project_id: int
    outline_id: int
    outline_sha256: str
    outline: Mapping[str, Any]
    """drafting.outline@1 정규형(만들 때 박은 판)."""
    document_id: int
    document_etag: str
    texts: PromptTexts
    models: StageModels
    """S2·S3 의 모델 값(기본값 없음 — 빠지면 조용히 코드 값이 되는 길 0)."""
    tags: Tags
    max_usd: float
    base: reuse.Base | None = None
    """이어 받을 앞 실행(옵션 base — 없으면 처음부터)."""
    rebuild: frozenset[str] = frozenset()
    """안 바뀌었어도 다시 만들 잎 key."""


class ArtifactSource(Protocol):
    """실행의 회사를 묶은 core 문서 산출물 읽기(몸은 service/actions/run_sources.RunArtifacts)."""

    def ensure(self, document_id: int, etag: str) -> ArtifactRef | ArtifactRefused | ArtifactUnreadable:
        """그 문서(etag)의 분해 한 벌(없으면 짓는다). ArtifactInvalid 는 던짐, 잠깐 장애는 RunRetryLater."""
        ...

    def view(self, document_id: int, artifact_id: int, *, places: bool = False) -> DocArtifactView:
        """그 문서에 이어진 그 산출물의 읽기 뷰(이어짐이 없으면 core 의 ArtifactNotFound — 단계 실패). places=True 면
        글자 자리째(상자)."""
        ...

    def file_name(self, document_id: int) -> str | None:
        """문서의 올린 이름(결과의 document.fileName). 없으면 None."""
        ...


class ArtifactFailed(RuntimeError):
    """문서 산출물을 얻지 못했다(실행 실패 — 글은 code 만)."""


class Llm(Protocol):
    def call[T](self, request: CallRequest[T]) -> LlmResult[T]: ...

    def dry_run[T](self, request: CallRequest[T]) -> DryRunReport: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class DraftAdapters:
    llm: Llm
    mock: bool
    spent_usd: Callable[[], float]
    artifacts: ArtifactSource


# ── 도움 ──


def _mocked(model: StageModel) -> StageModel:
    """mock 갈래의 모델 값 — 경로 MOCK_ROUTE, 위끝 min(칸 값, MOCK_MAX_OUTPUT_TOKENS)(MARC-ISSUE-490)."""
    return replace(model, route=MOCK_ROUTE, max_output_tokens=min(model.max_output_tokens, MOCK_MAX_OUTPUT_TOKENS))


def _models(inputs: DraftInputs, adapters: DraftAdapters) -> StageModels:
    """부를 모델 값. live 면 칸 값 그대로. mock 이면 경로 MOCK_ROUTE·위끝은 칸 값과 가상 모델 상한 중 작은 것
    (temperature 는 칸 값)."""
    if not adapters.mock:
        return inputs.models
    return StageModels(map=_mocked(inputs.models.map), draft=_mocked(inputs.models.draft))


def _nodes(inputs: DraftInputs) -> list[Mapping[str, Any]]:
    return list(inputs.outline["nodes"])


def _leaves(inputs: DraftInputs) -> list[tuple[str, tuple[str, ...], str]]:
    nodes = _nodes(inputs)
    paths = wire.title_paths(nodes)
    requirement = {node["key"]: node["requirement"] for node in nodes}
    return [(key, paths[key], requirement[key]) for key in wire.leaf_keys(nodes)]


def _view(inputs: DraftInputs, adapters: DraftAdapters, carried: Carried, *, places: bool = False) -> DocArtifactView:
    """extract 가 적은 산출물의 뷰(단계마다 한 번 — 473)."""
    artifact_id = cast("int", _data(carried, "extract")["artifactId"])
    return adapters.artifacts.view(inputs.document_id, artifact_id, places=places)


def failure(kind: str) -> dict[str, str]:
    return {"kind": kind, "message": FAILURE_MESSAGES[kind]}


def _failure_of(result: LlmResult[Any]) -> dict[str, str]:
    match result:
        case CutOff():
            return failure("truncated")
        case Refused():
            return failure("refusal")
        case TimedOut():
            return failure("timeout")
        case SchemaMismatch():
            return failure("schema_mismatch")
        case BudgetExceeded():
            return failure("budget_exceeded")
        case ProviderFailed():
            return failure("provider_error")
        case _:
            return failure("unparsable")


def map_request(
    inputs: DraftInputs, adapters: DraftAdapters, batch: Sequence[pages.Page], keys: Sequence[str] | None = None
) -> CallRequest[MapAnswer]:
    """S2 요청. keys 를 주면 그 잎만 목차 줄에 싣는다(이어 받기 — 다시 달 잎만)."""
    leaves = [leaf for leaf in _leaves(inputs) if keys is None or leaf[0] in keys]
    system, user = v2_prompts.map_texts(inputs.texts, prompts.outline_lines(leaves), pages.batch_text(batch))
    model = _models(inputs, adapters).map
    return CallRequest(
        prompt=PROMPT_IDS["map"],
        route=model.route,
        tags=inputs.tags,
        vars={"system": system, "user": user},
        schema=MapAnswer,
        schema_name="page_map",
        max_output_tokens=model.max_output_tokens,
        timeout_ms=TIMEOUT_MS,
        max_schema_retries=SCHEMA_RETRIES,
        temperature=model.temperature,
    )


def draft_request(
    inputs: DraftInputs, adapters: DraftAdapters, path: Sequence[str], requirement: str, body: str
) -> CallRequest[DraftAnswer]:
    system, user = v2_prompts.draft_texts(inputs.texts, path, requirement, body)
    system = v2_texts.draft_system(system)
    model = _models(inputs, adapters).draft
    return CallRequest(
        prompt=PROMPT_IDS["draft"],
        route=model.route,
        tags=inputs.tags,
        vars={"system": system, "user": user},
        schema=DraftAnswer,
        schema_name="bullets",
        max_output_tokens=model.max_output_tokens,
        timeout_ms=TIMEOUT_MS,
        max_schema_retries=SCHEMA_RETRIES,
        temperature=model.temperature,
    )


def _worst(adapters: DraftAdapters, request: CallRequest[Any]) -> float:
    return adapters.llm.dry_run(request).estimate.worst_case_usd


def _resumed(ctx: StepContext, keys: Sequence[object]) -> list[dict[str, Any]]:
    """resume 의 끝난 자리(차례가 이번 자리와 같아야 한다 — 아니면 ValueError 로 단계 실패)."""
    if ctx.resume is None:
        return []
    answers = ctx.resume.get("answers")
    if not isinstance(answers, list) or len(cast("list[object]", answers)) > len(keys):
        raise ValueError("resume 의 answers 가 이번 자리 수와 맞지 않는다")
    done = cast("list[dict[str, Any]]", answers)
    for at, answer in enumerate(done):
        if answer.get("at") != keys[at]:
            raise ValueError(f"resume 의 {at} 번째 답의 자리가 이번 차례와 다르다")
    return list(done)


@dataclass(slots=True)
class _Guard:
    """부르기 전마다 지출 ≥ 상한이면 막는다(상한 = min(max_usd, 그 단계 위끝))."""

    adapters: DraftAdapters
    cap: float

    def call[T](self, request: CallRequest[T]) -> LlmResult[T] | None:
        if self.adapters.spent_usd() >= self.cap:
            return None
        return self.adapters.llm.call(request)


def _data(carried: Carried, step: str) -> dict[str, Any]:
    return cast("dict[str, Any]", carried[step].data)


def _rejected(code: str, stage: str, message: str) -> dict[str, str]:
    return {"status": "rejected", "code": code, "stage": stage, "message": message}


def _settings(inputs: DraftInputs, adapters: DraftAdapters) -> dict[str, Any]:
    models = _models(inputs, adapters)
    return {"routes": {"map": models.map.route, "draft": models.draft.route}, "promptIds": dict(PROMPT_IDS)}


def _reason(inputs: DraftInputs, adapters: DraftAdapters, extract: Mapping[str, Any]) -> str | None:
    """앞 실행과 어긋난 까닭(앞 실행이 없으면 None)."""
    if inputs.base is None:
        return None
    return reuse.matched(inputs.base, extract, _settings(inputs, adapters))


def _plan(inputs: DraftInputs, adapters: DraftAdapters, carried: Carried) -> dict[str, Any]:
    """이어 받기의 계획(map data 의 reuse) — 앞 실행이 없으면 잎 전부 S2·옮김 0."""
    leaves = [key for key, _, _ in _leaves(inputs)]
    base = inputs.base
    if base is None:
        return {"baseRunId": None, "reason": None, "s2Keys": leaves, "keptPages": {}}
    reason = _reason(inputs, adapters, _data(carried, "extract"))
    changes = reuse.changes(base, _nodes(inputs))
    return {
        "baseRunId": base.run_id,
        "reason": reason,
        "s2Keys": reuse.s2_keys(base, leaves, changes, inputs.rebuild, reason),
        "keptPages": reuse.kept_pages(base, changes, inputs.rebuild, reason),
    }


def _reusable(
    inputs: DraftInputs, plan: Mapping[str, Any], key: str, leaf_pages: Sequence[int]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]] | None:
    if inputs.base is None:
        return None
    changes = reuse.changes(inputs.base, _nodes(inputs))
    reason = cast("str | None", plan["reason"])
    return reuse.reusable(inputs.base, key, leaf_pages, changes, inputs.rebuild, reason, inputs.document_id)


# ── 단계 ──


def _artifact(inputs: DraftInputs, adapters: DraftAdapters) -> ArtifactRef | ArtifactRefused:
    """그 문서의 산출물, 또는 쪽·크기·시간 거절(TOO_LARGE_CODES — rejected too_large). 그 밖은 ArtifactFailed."""
    try:
        got = adapters.artifacts.ensure(inputs.document_id, inputs.document_etag)
    except ArtifactInvalid:
        raise ArtifactFailed("artifact_invalid") from None
    match got:
        case ArtifactRefused(code=code) if code in TOO_LARGE_CODES:
            return got
        case ArtifactRefused(code=code) | ArtifactUnreadable(code=code):
            raise ArtifactFailed(code)
        case ArtifactRef():
            return got


def _too_large(got: ArtifactRef | ArtifactRefused) -> dict[str, str] | None:
    match got:
        case ArtifactRefused(code="too_many_pages"):
            return _rejected("too_large", "before_map", f"쪽이 {pages.PAGES_MAX}쪽을 넘는다.")
        case ArtifactRefused(code="parse_timeout"):
            return _rejected("too_large", "before_map", TOO_SLOW)
        case ArtifactRefused() | ArtifactRef(status="too_large"):
            return _rejected("too_large", "before_map", TOO_BIG)
        case ArtifactRef():
            return None


def _parser(row: ArtifactRef) -> dict[str, object]:
    return {"name": row.parser.name, "version": row.parser.version, "layout": row.parser.layout}


def _extract(inputs: DraftInputs, adapters: DraftAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    got = _artifact(inputs, adapters)
    file_name = adapters.artifacts.file_name(inputs.document_id)
    if file_name is None:
        raise ArtifactFailed("document_missing")
    rejection = _too_large(got)
    row = got if isinstance(got, ArtifactRef) else None
    if rejection is not None or row is None:
        data: dict[str, object] = {
            "fileName": file_name,
            "pageCount": 0 if row is None else row.page_count,
            "textPages": 0,
            "truncatedPages": [],
            "rejection": rejection,
            "artifactId": None if row is None else row.id,
            "pagesSha256": None,
            "epoch": None if row is None else row.epoch,
            "parser": None if row is None else _parser(row),
            "pages": [],
        }
        return StepOutput(data=data)
    view = adapters.artifacts.view(inputs.document_id, row.id)
    texts = blocks_text.page_texts(view)
    found = pages.pages_of(texts)
    data = {
        "fileName": file_name,
        "pageCount": len(found),
        "textPages": sum(not page.empty for page in found),
        "truncatedPages": [page.number for page in found if page.truncated],
        "rejection": None,
        "artifactId": row.id,
        "pagesSha256": blocks_text.pages_sha256(texts),
        "epoch": row.epoch,
        "parser": _parser(row),
        "pages": [{"page": p.page, "width": p.width, "height": p.height} for p in view.pages()],
    }
    if len(found) > pages.PAGES_MAX:
        data["rejection"] = _rejected("too_large", "before_map", f"쪽이 {pages.PAGES_MAX}쪽을 넘는다.")
    elif not any(not page.empty for page in found):
        raise NoTextLayer("모든 쪽에 글이 없다")
    return StepOutput(data=data)


def _map(inputs: DraftInputs, adapters: DraftAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    rejection = _data(carried, "extract")["rejection"]
    if rejection is not None:
        return StepOutput(data={"rejection": rejection, "batches": 0, "groups": [], "answers": []})
    plan = _plan(inputs, adapters, carried)
    keys = cast("list[str]", plan["s2Keys"])
    kept = cast("dict[str, list[int]]", plan["keptPages"])
    groups = pages.batches(pages.pages_of(blocks_text.page_texts(_view(inputs, adapters, carried)))) if keys else []
    numbers = [[page.number for page in batch] for batch in groups]
    requests = [map_request(inputs, adapters, batch, keys) for batch in groups]
    floor = sum(
        _worst(adapters, draft_request(inputs, adapters, path, req, ""))
        for key, path, req in _leaves(inputs)
        if not (key in kept and _reusable(inputs, plan, key, kept[key]))
    )
    bound = sum(_worst(adapters, request) for request in requests) + floor
    if bound > inputs.max_usd:
        rejected = _rejected("over_budget", "before_map", OVER_BUDGET)
        data: dict[str, object] = {
            "rejection": rejected,
            "batches": len(groups),
            "groups": numbers,
            "answers": [],
            "reuse": plan,
        }
        return StepOutput(data=data)
    guard = _Guard(adapters, min(inputs.max_usd, bound))
    answers = _resumed(ctx, list(range(len(groups))))
    for at in range(len(answers), len(groups)):
        result = guard.call(requests[at])
        if result is None:
            answer: dict[str, Any] = {"at": at, "pages": None, "failure": failure("budget_exceeded")}
        elif isinstance(result, Success):
            answer = {"at": at, "pages": cast("dict[str, Any]", result.data), "failure": None}
        else:
            answer = {"at": at, "pages": None, "failure": _failure_of(result)}
        answers.append(answer)
        ctx.checkpoint(
            {"answers": list(answers), "spentUsd": adapters.spent_usd()}, done=len(answers), total=len(groups)
        )
    return StepOutput(
        data={"rejection": None, "batches": len(groups), "groups": numbers, "answers": answers, "reuse": plan}
    )


def _page_map(
    inputs: DraftInputs, map_data: Mapping[str, Any]
) -> tuple[dict[str, list[int]], list[dict[str, Any]], list[dict[str, Any]]]:
    """S2 답 → (잎 → 쪽, failedBatches, 경고). 묶음의 쪽 번호는 map data 의 groups(뷰를 다시 열지 않는다). S2 는
    reuse.s2Keys 잎만 달고, 나머지 잎은 reuse.keptPages(앞 결과의 쪽)."""
    groups = cast("list[list[int]]", map_data["groups"])
    leaves = [key for key, _, _ in _leaves(inputs)]
    plan = cast("Mapping[str, Any]", map_data["reuse"])
    asked = cast("list[str]", plan["s2Keys"])
    page_keys: dict[int, list[str]] = {}
    failed: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for answer in cast("list[dict[str, Any]]", map_data["answers"]):
        batch = groups[cast("int", answer["at"])]
        if answer["failure"] is not None:
            first, last = batch[0], batch[-1]
            failed.append({"firstPage": first, "lastPage": last, "failure": answer["failure"]})
            continue
        got, said = mapping.map_batch(answer["pages"], batch_pages=batch, leaves=asked)
        page_keys.update(got)
        warnings += said
    found = mapping.leaf_pages(page_keys, leaves)
    found.update({key: list(kept) for key, kept in cast("dict[str, list[int]]", plan["keptPages"]).items()})
    return found, failed, warnings


def _draft(inputs: DraftInputs, adapters: DraftAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    map_data = _data(carried, "map")
    if map_data["rejection"] is not None:
        return StepOutput(data={"rejection": map_data["rejection"], "answers": []})
    leaf_to_pages, _, _ = _page_map(inputs, map_data)
    plan = cast("Mapping[str, Any]", map_data["reuse"])
    leaves = _leaves(inputs)
    answers = _resumed(ctx, [key for key, _, _ in leaves])
    moved = {
        key: found
        for key, _, _ in leaves[len(answers) :]
        if (found := _reusable(inputs, plan, key, leaf_to_pages[key])) is not None
    }
    todo = [leaf for leaf in leaves[len(answers) :] if leaf_to_pages[leaf[0]] and leaf[0] not in moved]
    view = _view(inputs, adapters, carried) if todo else None
    planned: dict[str, tuple[CallRequest[DraftAnswer], material.Material]] = {}
    cut_bare: set[str] = set()
    for key, path, requirement in todo:
        try:
            found = material.material(leaf_to_pages[key], cast("DocArtifactView", view))
        except material.GivenConflict as error:
            raise FlowOutputError(str(error)) from None
        if found.given:
            planned[key] = (draft_request(inputs, adapters, path, requirement, found.text), found)
        elif found.cut:
            cut_bare.add(key)
    spent = adapters.spent_usd()
    bound = spent + sum(_worst(adapters, request) for request, _ in planned.values())
    if bound > inputs.max_usd:
        return StepOutput(data={"rejection": _rejected("over_budget", "before_draft", OVER_BUDGET), "answers": []})
    guard = _Guard(adapters, min(inputs.max_usd, bound))
    for key, _, _ in leaves[len(answers) :]:
        answer: dict[str, Any] = {"at": key, "outcome": {"status": "no_material"}, "warnings": [], "origin": None}
        if key in moved:
            answer["outcome"], answer["warnings"], answer["origin"] = moved[key]
        elif key in cut_bare:
            answer["warnings"] = [mapping.warning("material_truncated", CUT_ALL, key=key)]
        if key in planned:
            request, found = planned[key]
            warnings: list[dict[str, Any]] = []
            if found.cut:
                warnings.append(mapping.warning("material_truncated", CUT, key=key))
            result = guard.call(request)
            if result is None:
                answer["outcome"] = {"status": "failed", "failure": failure("budget_exceeded")}
            elif isinstance(result, Success):
                lines, capped = answer_engine.trim(cast("Mapping[str, Any]", result.data), key)
                checked, said = checks.check(lines, key=key, given=found.given, document_id=inputs.document_id)
                for bullet in checked:
                    for source in bullet["sources"]:
                        source["blockBox"] = list(found.given[source["blockId"]].bbox)
                answer["outcome"] = {"status": "done", "bullets": checked}
                warnings += capped + said
            else:
                answer["outcome"] = {"status": "failed", "failure": _failure_of(result)}
            answer["warnings"] = warnings
        answers.append(answer)
        if key in planned:
            ctx.checkpoint(
                {"answers": list(answers), "spentUsd": adapters.spent_usd()}, done=len(answers), total=len(leaves)
            )
    return StepOutput(data={"rejection": None, "answers": answers})


def _basis(extract: Mapping[str, Any]) -> dict[str, Any] | None:
    """결과 머리 basis(§2-0 ⑤) — 산출물 행이 있으면 늘 값(too_large 행도), 분해 거절이면 null."""
    if extract["artifactId"] is None:
        return None
    return {
        "artifactId": extract["artifactId"],
        "parser": extract["parser"],
        "epoch": extract["epoch"],
        "pagesSha256": extract["pagesSha256"],
    }


def _base(inputs: DraftInputs, reason: str | None) -> dict[str, Any] | None:
    if inputs.base is None:
        return None
    return {
        "runId": inputs.base.run_id,
        "outlineId": inputs.base.outline_id,
        "matched": reason is None,
        "reason": reason,
    }


def _place(
    inputs: DraftInputs, adapters: DraftAdapters, carried: Carried, outcomes: Mapping[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """이 실행이 지은 done bullet 의 출처에 상자를 단다(제자리 — 옮긴 잎은 이미 상자가 있어 건너뜀). 출처가 하나라도
    있으면 뷰를 글자 자리째 한 번 연다(§2-0 ②). 블록을 다시 찾지 못하면 draft data 의 blockBox + sentence null 과
    경고 source_block_missing(이슈 482 — 실행은 done). 돌려주는 것은 그 경고."""
    bullets = [
        (key, bullet)
        for key, answer in outcomes.items()
        if answer["outcome"]["status"] == "done" and answer.get("origin") is None
        for bullet in answer["outcome"]["bullets"]
    ]
    if not any(bullet["sources"] for _, bullet in bullets):
        return []
    view = _view(inputs, adapters, carried, places=True)
    blocks: dict[str, material.GivenBlock | None] = {}
    warnings: list[dict[str, Any]] = []
    for key, bullet in bullets:
        placed: list[dict[str, Any]] = []
        for source in bullet["sources"]:
            block_id = source["blockId"]
            if block_id not in blocks:
                blocks[block_id] = material.locate(view, block_id)
            found = blocks[block_id]
            if found is None:
                placed.append(
                    {
                        "documentId": source["documentId"],
                        "blockId": block_id,
                        "page": source["page"],
                        "blockBox": source["blockBox"],
                        "sentence": None,
                    }
                )
                warnings.append(mapping.warning("source_block_missing", BLOCK_MISSING, key=key, page=source["page"]))
                continue
            placed.append(places.source(found, source["index"], view, source["documentId"]))
        bullet["sources"] = placed
    return warnings


def _report(inputs: DraftInputs, adapters: DraftAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    extract, map_data, draft = _data(carried, "extract"), _data(carried, "map"), _data(carried, "draft")
    rejection = draft["rejection"]
    leaves = _leaves(inputs)
    warnings: list[dict[str, Any]] = [
        mapping.warning("page_truncated", "쪽 글이 8,000자를 넘어 뒤를 잘랐다.", page=n)
        for n in cast("list[int]", extract["truncatedPages"])
    ]
    reason = _reason(inputs, adapters, extract)
    if reason is not None:
        warnings.append(mapping.warning("base_not_reused", NOT_REUSED[reason]))
    leaf_to_pages: dict[str, list[int]] = {key: [] for key, _, _ in leaves}
    failed: list[dict[str, Any]] = []
    if map_data["rejection"] is None:
        leaf_to_pages, failed, said = _page_map(inputs, map_data)
        warnings += said
    outcomes: dict[str, dict[str, Any]] = {
        answer["at"]: answer for answer in copy.deepcopy(cast("list[dict[str, Any]]", draft["answers"]))
    }
    missing = _place(inputs, adapters, carried, outcomes) if rejection is None else []
    result_leaves: list[dict[str, Any]] = []
    for key, path, _ in leaves:
        origin: dict[str, int] | None = None
        if rejection is not None:
            outcome: dict[str, Any] = {"status": "not_run", "reason": NOT_RUN}
        else:
            outcome = outcomes[key]["outcome"]
            origin = outcomes[key].get("origin")
            warnings += outcomes[key]["warnings"] + [w for w in missing if w["key"] == key]
        if rejection is None and not leaf_to_pages[key]:
            warnings.append(mapping.warning("mapping_incomplete", "어느 쪽에도 달리지 않은 잎이다.", key=key))
        result_leaves.append(
            {"key": key, "titlePath": list(path), "pages": leaf_to_pages[key], "reusedFrom": origin, "outcome": outcome}
        )
    result: dict[str, Any] = {
        "schemaVersion": shapes.RESULT_SHAPE,
        "basis": _basis(extract),
        "base": _base(inputs, reason),
        "projectId": inputs.project_id,
        "outlineId": inputs.outline_id,
        "outlineSha256": inputs.outline_sha256,
        "status": {"status": "done"} if rejection is None else rejection,
        "document": {
            "documentId": inputs.document_id,
            "fileName": extract["fileName"],
            "pageCount": extract["pageCount"],
            "textPages": extract["textPages"],
            "pages": extract["pages"],
        },
        "leaves": result_leaves,
        "mapping": {"batches": map_data["batches"], "failedBatches": failed},
        "settings": _settings(inputs, adapters),
        "warnings": warnings,
    }
    adapter = shapes.RESULT_SHAPES[shapes.RESULT_SHAPE]
    try:
        adapter.validate_python(result, strict=True)
    except ValidationError as error:
        raise FlowOutputError(
            f"결과가 {shapes.RESULT_SHAPE} 꼴을 지나지 못했다: {error.error_count()} errors"
        ) from None
    dumped = cast(
        "dict[str, object]",
        json.loads(json.dumps(adapter.dump_python(cast("shapes.DraftingResult", result), mode="json"))),
    )
    return StepOutput(data={"results": [dumped]})


FLOW: Final = make_flow(
    module=MODULE,
    id=FLOW_ID,
    input_shape=shapes.OUTLINE_SHAPE,
    inputs=DraftInputs,
    adapters=DraftAdapters,
    result_shapes=(shapes.RESULT_SHAPE,),
    steps=(
        FlowStep(name="extract", run=_extract),
        FlowStep(name="map", run=_map),
        FlowStep(name="draft", run=_draft),
        FlowStep(name="report", run=_report),
    ),
)

ANSWER_SHAPES: Final = {"map": TypeAdapter(MapAnswer), "draft": TypeAdapter(DraftAnswer)}
"""모델 답 꼴(시험이 고정 스키마를 견준다)."""
