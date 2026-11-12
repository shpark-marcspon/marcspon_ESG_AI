"""흐름 translation.colab@158(밴드 TR2): 실행의 문서·옵션 → 엔진 colab_158 → translation.result@1 + Word.

단계 셋(소프트 시간 제한 240초는 단계마다 — 긴 문서의 시도 시간은 후속 이슈):
    prepare    공급사 호출 0. 문서 바이트 판정(`PK\\x03\\x04` = docx → tools/docx_reader, `%PDF-` = 받지 않음, 그 밖 =
               UTF-8 strict 글 — 실행기가 넘기는 꼴(늘 application/pdf)은 믿지 않는다) → 원문 글자·쪽 조각 상한(계획 앞)
               → 실패 쪽만 다시의 앞 실행 대조 → 호출 계획(plan / retry_plan) → 계획 호출 수 상한 → 다리 `dry_run`
               (설정 오류는 여기서 예외: 공급사 미등록·출력 상한 초과 = LlmConfigError → setup_error, 봉투 빠짐 =
               PromptError → step_error — 둘 다 failed·failedStep prepare) → 위끝(tools/run_bound.py — 자리별 실측
               비율 × 다리 어림 + 마지막 호출 여유) → 금액 상한(over_budget).
               산출 {rejection|None, pageCount, calls, totalEstimateUsd(새 위끝), ceilingUsd(다리의 엄격 합 — 비교용),
               perSite(자리마다 calls·estimateUsd·ratio), warnings, sourceSha256}.
    translate  거절이면 엔진을 부르지 않고 거절 결과를, 아니면 `pipeline.run`/`retry` 한 번 → wire.to_result.
               엔진은 호출 일지(tools/call_journal.py — MARC-ISSUE-268 의 1)를 거쳐 부른다: 호출마다 답을 적고 약 20초
               마다 체크포인트, 다음 시도는 ctx.resume 의 일지를 되감는다(공급사 0 — 엔진 0줄, MARC-ENT-442).
               소프트 제한·체크포인트 예외·일지 넘침은 엔진의 except 에 삼켜지지 않고 단계 밖으로 나간다.
               실행 중 상한 = min(max_usd, prepare 위끝)(밴드 TRE1 G1): 이 실행의 지출(adapters.spent_usd — 호출 기록
               합) ≥ 상한이면 over_budget(공급사 0). 그 밖은 일지가 실제 호출마다 허용액(상한 − 지출)에서 머리 여유를
               미리 빼고 실비로 되돌리다가 모자라면 그 자리에서 over_budget 으로 끝낸다(call_journal 머리말 (d)) —
               그래서 어떤 입력에서도 실비 ≤ prepare 위끝이다(위끝을 넘을 입력은 산출 0 의 over_budget).
    report     결과 꼴 strict(못 지나면 FlowOutputError) + Word(outputs.files.build_word_files) → 출력 파일.
               Word 하나를 짓다 실패하면(WordFailed) 그 파일만 없다(코랩 셀 54·63 의 except 와 같음).
               결과는 둘: 주 결과 translation.result@1(바이트 그대로) + 요약 translation.digest@1(outputs.digest —
               실제로 지은 Word 이름으로 셈, 밴드 TR3a).

거절(result status rejected — 실행은 done): 엔진의 셋(no_pages·ceo_page_limit) + unsupported_input + 이 흐름의 넷
(too_large·over_budget·retry_source_not_found·retry_source_mismatch). 위끝·상한 값은 prepare 산출에만 싣는다(고객 응답에
단계 데이터는 없다).

흐름은 설정·키를 읽지 않는다 — 금액 상한은 끼움이 입력에 실어 준다(apps.py 가 꽂은 함수로 읽은 값).
"""

import dataclasses
import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any, Final, Literal, cast

from pydantic import ValidationError

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, FlowOutputError, FlowStep, OutputFile, StepContext, StepOutput
from esgapi.core.llm.client import LlmClient
from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE
from esgapi.translation.contracts.shapes import RESULT_SHAPE, RESULT_SHAPES
from esgapi.translation.contracts.wire import to_result
from esgapi.translation.engines.colab_158 import gates, pipeline, plan, review_rules
from esgapi.translation.engines.colab_158.pages import PageChunk, pages_to_map_merge, parse_pages
from esgapi.translation.engines.colab_158.pipeline import EngineInput
from esgapi.translation.engines.colab_158.plan import CallPlan
from esgapi.translation.engines.colab_158.texts import PromptTexts
from esgapi.translation.outputs.digest import digest
from esgapi.translation.outputs.failures import WordFailed
from esgapi.translation.outputs.files import build_word_files
from esgapi.translation.tools import call_journal, run_bound
from esgapi.translation.tools.docx_reader import DocxRejected, read_docx
from esgapi.translation.tools.llm_bridge import MOCK_MODELS, LlmBridge, TranslationModels, model_for, prompt_ids

FLOW_ID: Final = "translation.colab@158"
INPUT_SHAPE: Final = "translation.run@1"
"""흐름 입력의 이름표(실행의 문서 + options@1 + 끼움이 읽은 것 — greenwash.document@1 꼴)."""

MAX_PAGE_CHUNKS: Final = 300
"""쪽 조각 상한(감독 처분 Q6)."""
MAX_SOURCE_CHARS: Final = 200_000
"""원문 글자 상한(★D, 추정): 지어낸 10·30쪽(쪽당 국문 1,300자, 모의 영문 답 = 국문 글자 × 2.5)에서 A/B·자동수정
켬의 result@1 이 원문 글자당 약 24.6바이트 — 결과 상한 8MiB(runs/models.py)에 약 34만 자. 1.7배 여유를 둔 값."""
MAX_PLANNED_CALLS: Final = 20_000
"""계획 호출 수 상한(감독 처분 Q6 — 근거 없는 어림. 10쪽 지어낸 문서가 282)."""

WORD_MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
WORD_KINDS: Final = ("bilingual", "qa", "autofix")
WORD_VARIANTS: Final = ("single", "a", "b")
OUTPUT_FILES: Final = tuple(f"translation-{kind}-{variant}.docx" for kind in WORD_KINDS for variant in WORD_VARIANTS)
"""선언한 출력 파일 아홉(문체 × 갈래). 실제로 짓는 것은 결과에 따라 그보다 적다(outputs/files.py)."""

CONSTANTS: Final[Mapping[str, int]] = {
    "editorialQaMinScore": gates.GENERIC_EDITORIAL_QA_MIN_SCORE,
    "tableBatchSize": gates.TABLE_BATCH_SIZE,
    "polishMinChars": gates.EDITORIAL_POLISH_MIN_CHARS,
    "polishMaxChars": gates.EDITORIAL_POLISH_MAX_CHARS,
    "koreanRepairRounds": gates.MAX_UNTRANSLATED_REPAIR_ROUNDS,
    "autofixKoreanRepairRounds": review_rules.PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS,
}

OVER_BUDGET_MESSAGE: Final = "예상 비용의 위끝이 한 실행의 금액 상한을 넘어요(운영 관리자 확인)"

type RejectionKind = Literal[
    "no_pages",
    "ceo_page_limit",
    "unsupported_input",
    "too_large",
    "over_budget",
    "retry_source_not_found",
    "retry_source_mismatch",
]


# ── 앞 실행(실패 쪽만 다시)의 갈래 — 끼움이 store 로 읽어 싣는다 ──

type AiKey = tuple[object, object, object]
"""실행 versions 의 AI 설정 판 열쇠(aiSettingId, modelSettingsSha256, promptsSha256 — 저장 글 판이 아니면 셋째 None).
다시 하기는 앞 실행과 이번 실행의 이것이 같아야 한다(MARC-ISSUE-326)."""

AI_KEY_FIELDS: Final = ("aiSettingId", "modelSettingsSha256", "promptsSha256")


def ai_key(versions: Mapping[str, object]) -> AiKey | None:
    """versions 의 판 열쇠. aiSettingId 열쇠가 없으면(TR4 앞 옛 실행) None — 대조할 수 없다."""
    if "aiSettingId" not in versions:
        return None
    setting_id, model_sha, prompts_sha = (versions.get(name) for name in AI_KEY_FIELDS)
    return (setting_id, model_sha, prompts_sha)


@dataclass(frozen=True, slots=True)
class RetryFound:
    """같은 회사·영문번역·끝남·결과 done 인 앞 실행. base = 문체 → 번역 글(자동수정 전)."""

    base: Mapping[str, str]
    source_sha256: str
    labels: tuple[str, ...]
    ai_key: AiKey | None
    """앞 실행 versions 의 판 열쇠(옛 실행은 None)."""


@dataclass(frozen=True, slots=True)
class RetryNotFound:
    """없음(남의 회사·다른 모듈·앞 결과가 거절이어도 이 갈래)."""


@dataclass(frozen=True, slots=True)
class RetryNotDone:
    """있지만 끝나지 않았다."""

    status: str


type RetrySource = RetryFound | RetryNotFound | RetryNotDone


@dataclass(frozen=True, slots=True)
class RetryRequest:
    from_run_id: int
    pages: tuple[int, ...]
    source: RetrySource
    ai_key: AiKey | None
    """이번 실행 versions 의 판 열쇠(끼움이 싣는다. 회사 없는 inputs 는 None)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TranslationRunInputs:
    """흐름의 입력(translation.run@1). options 는 끼움이 받은 options@1 을 엔진 칸으로 푼 것."""

    document: bytes
    company_name: str
    preferred_subject: str
    industry_standards: str
    glossary_base: tuple[tuple[str, str], ...]
    glossary_final: tuple[tuple[str, str], ...]
    part: str
    compare_ab: bool
    single_style: str
    peer_group_style_prompt: str | None
    page_start: int | None
    page_end: int | None
    ceo_page_limit: int | None
    autofix: bool
    retry: RetryRequest | None
    max_usd: float
    """한 실행의 금액 상한(USD — 끼움이 돌 때 apps.py 가 꽂은 함수로 읽은 값)."""
    texts: PromptTexts
    """엔진의 글 열넷(TR4 — 끼움이 적용 판에서 짓는다. 기본 판·옛 실행은 DEFAULT_TEXTS)."""
    models: TranslationModels
    """모델 칸 셋(TR4 — 같은 자리. 기본은 DEFAULT_MODELS)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TranslationAdapters:
    llm: LlmClient
    tenant: str
    """호출 꼬리표의 tenant(회사 id 글자)."""
    mock: bool
    """실행기가 모의 공급사만 싣는가(끼움이 싣는다 — MARC-ISSUE-331). 참이면 입력의 모델 칸 대신 MOCK_MODELS 로 부른다
    (입력·versions·modelSettingsSha256 은 그대로). 거짓이면 입력의 모델 칸 그대로(live 길 — 바이트 같음)."""
    spent_usd: Callable[[], float]
    """이 실행이 지금까지 쓴 돈(USD — 호출 기록 core_llm_call_logs 의 cost_usd 합, 실패 줄은 NULL). 끼움이 회사·실행 id
    를 묶어 싣는다(apps.py 가 꽂은 함수 — 흐름은 selector 를 모른다)."""


# ── 문서 판정 ──


@dataclass(frozen=True, slots=True)
class DocxDocument:
    text: str


@dataclass(frozen=True, slots=True)
class TextDocument:
    text: str


@dataclass(frozen=True, slots=True)
class UnsupportedDocument:
    kind: Literal["pdf", "not_utf8", "docx_rejected"]
    detail: str
    """사람에게 보일 까닭의 꼴만(문서 글은 싣지 않는다)."""


type ReadDocument = DocxDocument | TextDocument | UnsupportedDocument


def read_document(data: bytes) -> ReadDocument:
    """바이트 머리로 가른다. 실행기가 넘기는 꼴 이름은 보지 않는다(늘 application/pdf — runs/tasks.py)."""
    if data.startswith(b"PK\x03\x04"):
        read = read_docx(data)
        if isinstance(read, DocxRejected):
            return UnsupportedDocument("docx_rejected", f"Word 문서를 읽지 못했어요({read.kind})")
        return DocxDocument(read.text)
    if data.startswith(b"%PDF-"):
        return UnsupportedDocument("pdf", "PDF 는 받지 않아요 — Word(docx)나 글(txt·md)로 올려 주세요")
    try:
        return TextDocument(data.decode("utf-8"))
    except UnicodeDecodeError:
        return UnsupportedDocument("not_utf8", "글 문서는 UTF-8 이어야 해요")


def engine_input(inputs: TranslationRunInputs, text: str) -> EngineInput:
    return EngineInput(
        text=text,
        company_name=inputs.company_name,
        preferred_subject=inputs.preferred_subject,
        industry_standards=inputs.industry_standards,
        glossary_base=inputs.glossary_base,
        glossary_final=inputs.glossary_final,
        part=inputs.part,
        compare_ab=inputs.compare_ab,
        single_style=inputs.single_style,
        peer_group_style_prompt=inputs.peer_group_style_prompt,
        page_start=inputs.page_start,
        page_end=inputs.page_end,
        ceo_page_limit=inputs.ceo_page_limit,
        autofix=inputs.autofix,
        texts=inputs.texts,
    )


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _labels(inputs: TranslationRunInputs) -> tuple[str, ...]:
    return ("A", "B") if inputs.compare_ab else ("single",)


def _rejection(
    kind: RejectionKind, message: str, page_count: int | None = None, limit: int | None = None
) -> dict[str, Any]:
    return {"kind": kind, "message": message, "page_count": page_count, "limit": limit}


# ── prepare ──


def _prepared(rejection: Mapping[str, Any] | None, source_sha256: str, **estimate: object) -> StepOutput:
    data: dict[str, object] = {
        "rejection": None if rejection is None else dict(rejection),
        "sourceSha256": source_sha256,
        "pageCount": estimate.get("pageCount"),
        "calls": estimate.get("calls"),
        "totalEstimateUsd": estimate.get("totalEstimateUsd"),
        "ceilingUsd": estimate.get("ceilingUsd"),
        "perSite": estimate.get("perSite", {}),
        "warnings": estimate.get("warnings", []),
    }
    return StepOutput(data=data)


def _retry_check(inputs: TranslationRunInputs, source_sha256: str) -> dict[str, Any] | None:
    retry = inputs.retry
    if retry is None:
        return None
    source = retry.source
    if not isinstance(source, RetryFound):
        return _rejection(
            "retry_source_not_found", "다시 돌릴 앞 번역 실행을 찾지 못했어요(끝난 영문번역 실행이어야 해요)"
        )
    same_setting = source.ai_key is not None and source.ai_key == retry.ai_key  # 옛 실행(열쇠 없음)은 섞일 수 있어 거절
    if source.source_sha256 != source_sha256 or source.labels != _labels(inputs) or not same_setting:
        return _rejection("retry_source_mismatch", "앞 번역 실행과 원문이나 문체 묶음, AI 설정 판이 달라요")
    return None


def _plan_of(inputs: TranslationRunInputs, engine: EngineInput) -> CallPlan:
    retry = inputs.retry
    if retry is None:
        return plan.plan(engine)
    source = cast("RetryFound", retry.source)
    return plan.retry_plan(engine, cast("Mapping[Any, str]", source.base), retry.pages)


def _source_chars(inputs: TranslationRunInputs, text: str, chunks: Sequence[PageChunk]) -> int:
    """MAX_SOURCE_CHARS 로 재는 글자 수: 쪽 범위가 있으면 범위 안 조각 글자(엔진이 받는 글 — 표 pipe 줄 포함), 없으면
    문서 전체(조각 합은 머리 글·끝 빈 줄을 빼고, 쪽 태그 없는 글에서 0 이다)."""
    if inputs.page_start is None and inputs.page_end is None:
        return len(text)
    return sum(len(chunk.content) for chunk in chunks)


def prepare(
    inputs: TranslationRunInputs, adapters: TranslationAdapters, carried: Carried, ctx: StepContext
) -> StepOutput:
    """머리말 prepare. 공급사 호출 0 — 다리의 dry_run 만(그 안의 설정 오류는 예외로 올라간다)."""
    read = read_document(inputs.document)
    if isinstance(read, UnsupportedDocument):
        return _prepared(_rejection("unsupported_input", read.detail), sha256_of(""))
    text = read.text
    source_sha256 = sha256_of(text)
    engine = engine_input(inputs, text)
    _, chunks, _ = pipeline.source_and_pages(engine)
    if _source_chars(inputs, text, chunks) > MAX_SOURCE_CHARS:
        message = f"원문이 너무 길어요(글자 {MAX_SOURCE_CHARS:,}자까지)"
        return _prepared(_rejection("too_large", message, None, MAX_SOURCE_CHARS), source_sha256)
    if len(chunks) > MAX_PAGE_CHUNKS:
        message = f"쪽이 너무 많아요(쪽 조각 {MAX_PAGE_CHUNKS}개까지)"
        return _prepared(_rejection("too_large", message, len(chunks), MAX_PAGE_CHUNKS), source_sha256)
    refused = _retry_check(inputs, source_sha256)
    if refused is not None:
        return _prepared(refused, source_sha256)
    planned = _plan_of(inputs, engine)
    if planned.rejection is not None:
        return _prepared(dataclasses.asdict(planned.rejection), source_sha256, pageCount=len(chunks))
    calls = sum(c.count for c in planned.calls)
    if calls > MAX_PLANNED_CALLS:
        message = f"번역 호출이 너무 많아요(호출 {MAX_PLANNED_CALLS:,}번까지)"
        return _prepared(_rejection("too_large", message, None, MAX_PLANNED_CALLS), source_sha256, calls=calls)
    estimate, max_guard = _bridge(inputs, adapters).dry_run_with_max(planned)
    bound = run_bound.run_bound(estimate, max_guard)
    rejection = None
    if bound["totalUsd"] > inputs.max_usd:
        rejection = _rejection("over_budget", OVER_BUDGET_MESSAGE)
    return _prepared(
        rejection,
        source_sha256,
        pageCount=len(chunks),
        calls=calls,
        totalEstimateUsd=bound["totalUsd"],
        ceilingUsd=bound["ceilingUsd"],
        perSite={site: dict(value) for site, value in bound["perSite"].items()},
        warnings=list(estimate["warnings"]),
    )


# ── translate ──


def _models(inputs: TranslationRunInputs, adapters: TranslationAdapters) -> TranslationModels:
    """실제로 부를 모델 칸: 실행기가 mock 이면 MOCK_MODELS, 아니면 입력의 칸(MARC-ISSUE-331)."""
    return MOCK_MODELS if adapters.mock else inputs.models


def _bridge(inputs: TranslationRunInputs, adapters: TranslationAdapters) -> LlmBridge:
    return LlmBridge(adapters.llm, part=inputs.part, tenant=adapters.tenant, models=_models(inputs, adapters))


def _settings(inputs: TranslationRunInputs, adapters: TranslationAdapters) -> dict[str, Any]:
    """결과의 settings — routes 는 실제로 쓴 경로(mock 이면 `mock`)."""
    models = _models(inputs, adapters)
    routes = {role: model_for(role, inputs.part, models).route for role in ("translate", "review")}
    return {
        "routes": routes,
        "prompt_ids": prompt_ids(),
        "constants": CONSTANTS,
    }


def _retry_info(inputs: TranslationRunInputs, run: Mapping[str, Any]) -> dict[str, Any] | None:
    if inputs.retry is None:
        return None
    skipped = [w["page_num"] for w in run["warnings"] if w["code"] == "retry_page_missing"]
    return {"fromRunId": inputs.retry.from_run_id, "pages": list(inputs.retry.pages), "skippedPages": skipped}


def _rejected_run(inputs: TranslationRunInputs, rejection: Mapping[str, Any], text: str | None) -> dict[str, Any]:
    """엔진을 부르지 않은 거절의 기록(엔진 기록 asdict 와 같은 꼴 — wire 는 옮기기만)."""
    page_numbers: list[int] = []
    duplicates: dict[int, int] = {}
    if text is not None:
        source_text, chunks, _ = pipeline.source_and_pages(engine_input(inputs, text))
        page_numbers = [p.page_num for p in chunks]
        _, duplicates = pages_to_map_merge(parse_pages(source_text))
    return {
        "part": inputs.part,
        "variant_labels": _labels(inputs),
        "page_numbers": page_numbers,
        "duplicate_pages": duplicates,
        "rejection": dict(rejection),
        "variants": [],
        "warnings": [],
    }


def _cap(inputs: TranslationRunInputs, prepared: Mapping[str, object]) -> float:
    """실행 중 상한 = min(max_usd, prepare 위끝)(머리말 translate)."""
    return min(inputs.max_usd, cast("float", prepared["totalEstimateUsd"]))


def _over_budget(inputs: TranslationRunInputs, spent: float, prepared: Mapping[str, object]) -> dict[str, Any] | None:
    """시도를 넘는 금액 상한(머리말 translate): 지출이 이미 상한에 닿았으면 공급사 0. 그 밖은 일지의 호출 전 판정."""
    if spent >= _cap(inputs, prepared):
        return _rejection("over_budget", OVER_BUDGET_MESSAGE)
    return None


def translate(
    inputs: TranslationRunInputs, adapters: TranslationAdapters, carried: Carried, ctx: StepContext
) -> StepOutput:
    prepared = carried["prepare"].data
    source_sha256 = cast("str", prepared["sourceSha256"])
    read = read_document(inputs.document)
    text = None if isinstance(read, UnsupportedDocument) else read.text
    rejection = prepared["rejection"]
    resumed = call_journal.EMPTY
    spent = 0.0
    if rejection is None and text is not None:
        spent = adapters.spent_usd()
        resumed = call_journal.read_resume(
            ctx.resume, source_sha256=source_sha256, calls=cast("int", prepared["calls"])
        )
        rejection = _over_budget(inputs, spent, prepared)
    if rejection is not None or text is None:  # 글이 없으면 prepare 가 unsupported_input 으로 거절했다
        run = _rejected_run(inputs, cast("Mapping[str, Any]", rejection), text)
        retry = None
    else:
        engine = engine_input(inputs, text)
        gateway = call_journal.JournalGateway(
            _bridge(inputs, adapters),
            resume=resumed,
            source_sha256=source_sha256,
            calls=cast("int", prepared["calls"]),
            checkpoint=ctx.checkpoint,
            allowance_usd=_cap(inputs, prepared) - spent,
        )
        if inputs.retry is None:
            engine_call = partial(pipeline.run, engine, gateway)
        else:
            source = cast("RetryFound", inputs.retry.source)
            base = cast("Mapping[Any, str]", source.base)
            engine_call = partial(pipeline.retry, engine, gateway, base, inputs.retry.pages)
        try:
            done = call_journal.unescaped(engine_call)  # 엔진 밖으로 빼낸 예외(소프트 제한·체크포인트·넘침)를 되던진다
        except call_journal.OverBudget:  # 이 시도의 남은 허용액을 다 썼다(머리말 translate)
            done = None
        if done is None:
            run = _rejected_run(inputs, _rejection("over_budget", OVER_BUDGET_MESSAGE), text)
            retry = None
        else:
            run = dataclasses.asdict(done)
            retry = _retry_info(inputs, run)
    settings = _settings(inputs, adapters)
    result = to_result(
        run,
        routes=settings["routes"],
        prompt_ids=settings["prompt_ids"],
        constants=settings["constants"],
        source_sha256=source_sha256,
        retry=retry,
    )
    return StepOutput(data={"result": result})


# ── report ──


def word_name(kind: str, variant: str) -> str:
    return f"translation-{kind}-{variant.lower()}.docx"


def word_files(result: Mapping[str, Any]) -> tuple[OutputFile, ...]:
    built = build_word_files(cast("Any", result))
    return tuple(
        OutputFile(name=word_name(item.kind, item.variant), media_type=WORD_MEDIA_TYPE, content=item.content)
        for item in built.built
        if not isinstance(item.content, WordFailed)
    )


def report(
    inputs: TranslationRunInputs, adapters: TranslationAdapters, carried: Carried, ctx: StepContext
) -> StepOutput:
    result = carried["translate"].data["result"]
    try:
        RESULT_SHAPES[RESULT_SHAPE].validate_python(result, strict=True)
    except ValidationError as error:
        raise FlowOutputError(f"결과가 {RESULT_SHAPE} 꼴이 아니다: 오류 {error.error_count()}개") from None
    checked = cast("Mapping[str, Any]", result)
    files = word_files(checked)
    summary = digest(checked, {f.name for f in files}, name=word_name)
    return StepOutput(data={"results": [dict(checked), dict(summary)]}, files=files)


STEPS: Final[Sequence[FlowStep[TranslationRunInputs, TranslationAdapters]]] = (
    FlowStep(name="prepare", run=prepare),
    FlowStep(name="translate", run=translate),
    FlowStep(name="report", run=report),
)

FLOW: Final = make_flow(
    module="translation",
    id=FLOW_ID,
    input_shape=INPUT_SHAPE,
    inputs=TranslationRunInputs,
    adapters=TranslationAdapters,
    result_shapes=(RESULT_SHAPE, DIGEST_SHAPE),
    output_files=OUTPUT_FILES,
    steps=tuple(STEPS),
)
prepared = _prepared  # 공개 이름 둘: PDF 흐름(pdf_158)이 파서 앞·파서의 거절을 같은 꼴로 싣는다
rejection = _rejection
