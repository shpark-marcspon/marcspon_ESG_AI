"""입력 꼴 translation.input@1 과 결과 꼴 translation.result@1 의 정의. TypedDict → JSON 스키마(밴드 TR1a).

원천은 받은 영문번역 코랩(보고서_AI번역_v3_1, MARC-ENT-158)이다. 입력 칸은 코랩이 컨설턴트에게 고치라고 한 칸(★
셀 — 회사 정보·용어집·파트·문체·peer 문체 글)과 쪽 범위·CEO 쪽 한도·자동수정 스위치뿐이다. 게이트 스위치·문턱 96·
표 묶음 24 같은 그 밖의 상수는 엔진 판(engines/colab_158)의 상수다 — 바꾸면 새 판이다(MARC-ENT-270).

용어집은 짝의 목록 둘(base·final)이다. 엔진이 코랩의 `{**GLOSSARY, **FINAL_GLOSSARY}` 처럼 접는다(같은 key 는 자리는
base 의 것·값은 final 의 것). JSON 객체로 받지 않는 까닭: 길이가 같은 key 의 차례가 프롬프트 글을 가르는데 객체의
키 차례는 전송을 지나며 보장되지 않는다.

결과는 갈래를 한 값으로 접지 않는다: 쪽 번역 실패(fragments[].status error — 코랩 W7 의 [TRANSLATION_ERROR])·검수
JSON 못 읽음(review.status parse_failed — 코랩 W8)·점수 없음(editorialQa.scoreDefaulted — 코랩 W2 의 100)·게이트가
안 돈 까닭(editorialQa.reason, 코랩 글자)·자동수정 멈춤(autofix.status stopped). 사용량·비용은 싣지 않는다(실행
기록이 진실이다). 입력 칸은 되싣지 않는다.

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다(use_attribute_docstrings). 프론트는 고정 파일
tests/data/flow-shapes/translation.result@1.schema.json 을 읽는다. 칸을 더하는 것은 @1 안, 빼거나 바꾸면 @2 다.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, TypedDict

from pydantic import ConfigDict, Field, JsonValue, TypeAdapter, with_config

INPUT_SHAPE: Final = "translation.input@1"
RESULT_SHAPE: Final = "translation.result@1"
FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True)

Count = Annotated[int, Field(ge=0)]
PageNum = Annotated[int, Field(ge=0)]
"""쪽 번호(코랩 `[PAGE n]` 의 n — 숫자 글자를 int 로 읽은 것이라 0 도 된다)."""
Part = Literal["ceo_message", "story", "general"]
VariantLabel = Literal["single", "A", "B"]


# ── 입력 ──


@with_config(FORBID)
class StructuredText(TypedDict):
    """구조 태그가 든 국문 글(코랩 셀 7 의 txt·md 갈래 — 코랩은 docx 도 이 글로 바꿔 받는다).

    쪽은 한 줄 전체가 `[PAGE n]` 인 줄로만 갈린다. 태그가 없으면 결과는 rejected(no_pages)다."""

    kind: Literal["structuredText"]
    text: str


Document = Annotated[StructuredText, Field(discriminator="kind")]
"""번역할 문서. 판별 칸 kind — docx 는 올리기 길과 함께 TR2 가 정한다. 그때까지는 tools/docx_reader.read_docx 의 글을
structuredText 로(MARC-ISSUE-200)."""


@with_config(FORBID)
class Company(TypedDict):
    """회사 기본 정보(코랩 셀 22). 기본값이 없다 — 코랩의 값은 한 고객사의 글이다."""

    name: str
    """회사 이름(코랩 COMPANY_NAME)."""
    preferredSubject: str
    """산업·주제 글(코랩 PREFERRED_SUBJECT)."""
    industryStandards: str
    """준수 기준 글(코랩 INDUSTRY_STANDARDS). 번역 system 글의 「Reporting frameworks:」 줄과 회사 문체 글에 든다."""


@with_config(FORBID)
class GlossaryPair(TypedDict):
    """용어집 한 짝(국문 key → 영문 value)."""

    ko: str
    en: str


@with_config(FORBID)
class Glossary(TypedDict):
    """용어집(코랩 셀 10 GLOSSARY·셀 13 FINAL_GLOSSARY). 저장소에 기본 용어집은 없다."""

    base: list[GlossaryPair]
    """평가 용어집(코랩 GLOSSARY). 목록 안 같은 ko 는 뒤가 이긴다(dict 처럼)."""
    final: list[GlossaryPair]
    """최종 용어집(코랩 FINAL_GLOSSARY). base 와 같은 ko 면 값은 이것이, 자리는 base 의 것이 이긴다."""


@with_config(FORBID)
class Style(TypedDict):
    """번역 문체(코랩 셀 40)."""

    compareAb: bool
    """true = A·B 두 문체로 각각 번역(코랩 USE_AB_STYLE). 코랩 기본 false."""
    single: Literal["A", "B"]
    """compareAb 가 false 일 때 쓰는 문체(코랩 SINGLE_STYLE). 코랩 기본 B."""


@with_config(FORBID)
class PeerGroupStyle(TypedDict):
    """peer group 문체 글(코랩 셀 27 PEER_GROUP_STYLE_PROMPT — 고객사 맞춤 글이라 입력으로 받는다)."""

    prompt: str


@with_config(FORBID)
class PageRange(TypedDict):
    """번역할 쪽 범위(코랩 셀 6 PAGE_START·PAGE_END). null 이면 그쪽 끝이 열린다."""

    start: int | None
    end: int | None


@with_config(FORBID)
class TranslationInput(TypedDict):
    """translation.input@1 — 영문번역 한 건의 입력. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["translation.input@1"]
    document: Document
    company: Company
    glossary: Glossary
    part: Part
    """번역할 파트(코랩 셀 38 CURRENT_PART). ceo_message 면 번역 모델이 경로 standard(Sonnet)다."""
    style: Style
    peerGroupStyle: PeerGroupStyle | None
    """null = peer 문체를 싣지 않음(코랩 USE_PEER_GROUP_STYLE=False). 코랩 기본은 켬 — 「코랩과 다른 자리」."""
    pages: PageRange
    ceoPageLimit: Annotated[int, Field(ge=0)] | None
    """ceo_message 파트에서 번역할 수 있는 쪽 조각 수의 상한(코랩 셀 49 CEO_PAGE_LIMIT, 코랩 값 6). null = 제한 없음."""
    autofix: bool
    """검수 이슈 기반 자동수정을 돌릴지(코랩 셀 67 APPLY_PART_QA_AUTOFIX, 코랩 값 true)."""


# ── 결과 ──


@with_config(FORBID)
class Rejection(TypedDict):
    """번역을 시작하지 않은 까닭(코랩이 실행을 멈춘 자리)."""

    kind: Literal[
        "no_pages",
        "ceo_page_limit",
        "unsupported_input",
        "too_large",
        "over_budget",
        "retry_source_not_found",
        "retry_source_mismatch",
    ]
    """no_pages = 쪽 범위 안에 [PAGE n] 쪽이 없음(코랩 ValueError), ceo_page_limit = CEO 파트의 쪽 조각 수가 상한을
    넘음(코랩 eval_js 경고 + SystemExit), unsupported_input = 받지 않는 문서 꼴. 아래 넷은 실행이 공급사를 부르기 전에
    멈춘 것(코랩에 없는 자리 — TR2): too_large = 쪽 조각·원문 글자·계획 호출 수가 상한을 넘음, over_budget = 호출
    비용의 위끝이 한 실행의 금액 상한을 넘음, retry_source_not_found = 다시 돌릴 앞 실행이 없음(남의 회사·다른 모듈·
    끝나지 않음·앞 결과가 거절이어도 이 갈래), retry_source_mismatch = 앞 실행의 원문·문체 묶음이 이 실행과 다름."""
    message: str
    pageCount: Count | None
    """번역 대상 쪽 조각 수(ceo_page_limit 일 때). 그 밖은 null."""
    limit: Count | None
    """CEO 쪽 한도(ceo_page_limit 일 때). 그 밖은 null."""


@with_config(FORBID)
class Routes(TypedDict):
    """역할별 core.llm 경로."""

    translate: str
    """번역·윤문·게이트·자동수정의 경로(파트 ceo_message 면 standard, 아니면 light-anthropic)."""
    review: str
    """검수의 경로(파트와 무관하게 light-anthropic — 코랩 W3)."""


@with_config(FORBID)
class EngineConstants(TypedDict):
    """엔진 판의 상수(코랩 기본값). 결과에 비추기만 한다."""

    editorialQaMinScore: int
    """범용 QA 점수 문턱(코랩 GENERIC_EDITORIAL_QA_MIN_SCORE 96)."""
    tableBatchSize: int
    """표 칸 JSON 묶음의 칸 수(코랩 24)."""
    polishMinChars: int
    """윤문·쪽 게이트의 최소 글자 수(공백 뺌, 코랩 EDITORIAL_POLISH_MIN_CHARS 120)."""
    polishMaxChars: int
    """윤문·범용 QA 의 최대 글자 수(코랩 EDITORIAL_POLISH_MAX_CHARS 6000)."""
    koreanRepairRounds: int
    """구획마다 한국어 잔존 보정의 최대 횟수(코랩 MAX_UNTRANSLATED_REPAIR_ROUNDS 2)."""
    autofixKoreanRepairRounds: int
    """자동수정 뒤 한국어 보정의 최대 횟수(코랩 PART_QA_AUTOFIX_MAX_KOREAN_REPAIR_ROUNDS 1)."""


@with_config(FORBID)
class RetryInfo(TypedDict):
    """실패 쪽만 다시 돌린 실행(코랩 셀 50 RETRY_PAGES — TR2)."""

    fromRunId: Annotated[int, Field(ge=1)]
    """번역 글을 가져온 앞 실행."""
    pages: list[PageNum]
    """다시 번역하라고 고른 쪽(옵션 그대로)."""
    skippedPages: list[PageNum]
    """고른 쪽 가운데 원문에 없어 건너뛴 쪽(코랩 「원문에서 찾을 수 없음, 건너뜀」 — 경고 retry_page_missing 과
    같은 쪽)."""


@with_config(FORBID)
class Settings(TypedDict):
    """실행 설정. 실제로 불린 모델·사용량은 실행 기록이 진실이다."""

    part: Part
    variants: list[VariantLabel]
    """번역한 문체(["single"] 또는 ["A","B"])."""
    routes: Routes
    promptIds: list[str]
    """이 판이 쓰는 core.llm 프롬프트 id(`translation/<자리>@<판>` — 쪽 system 일곱 자리는 @2)."""
    engine: Literal["colab_158"]
    constants: EngineConstants
    retry: RetryInfo | None
    """실패 쪽만 다시 돌린 실행이면 그 앞 실행과 쪽, 아니면 null."""


@with_config(FORBID)
class DocumentInfo(TypedDict):
    """원문을 쪽으로 나눈 결과."""

    pageNumbers: list[PageNum]
    """번역 대상 쪽 조각의 쪽 번호(쪽 범위를 거른 뒤, 원문 차례 — 같은 번호가 두 번 나오면 두 번)."""
    duplicatePages: dict[str, Annotated[int, Field(ge=2)]]
    """원문에서 같은 [PAGE n] 이 여러 번 나와 합친 쪽(쪽 번호 글자 → 나온 횟수, 코랩 셀 18). 없으면 빈 객체."""
    sourceSha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    """원문 글(문서를 글로 읽은 것 — 셀 7 앞)의 UTF-8 sha256. 실패 쪽만 다시 돌릴 때 앞 실행과 같은 원문인지 본다."""


@with_config(FORBID)
class EditorialQa(TypedDict):
    """범용 Editorial QA 게이트 한 번의 기록(코랩 GENERIC_EDITORIAL_QA_LOGS 한 줄). 점수는 LLM 이 낸다."""

    ran: bool
    """false = 게이트를 부르지 않음(reason 이 skipped_…)."""
    reason: Literal[
        "skipped_table_or_short_text",
        "skipped_too_long",
        "json_parse_failed",
        "no_revised_text",
        "score_and_issues_acceptable",
        "structure_tag_changed",
        "korean_leftover_increased",
        "revised_text_applied",
    ]
    """코랩의 reason 글자 그대로."""
    qualityScore: int | None
    """LLM 의 quality_score(0-100). 게이트가 안 돌았거나 JSON 을 못 읽었으면 null."""
    scoreDefaulted: bool
    """true = quality_score 가 없거나 정수로 못 읽어 코랩이 100 으로 친 것(코랩 W2)."""
    hasCriticalIssue: bool | None
    applied: bool
    """true = revised_text 를 번역문으로 썼다."""
    issues: JsonValue
    """LLM 이 낸 issues 그대로(코랩도 꼴을 보지 않는다). 없으면 []."""


@with_config(FORBID)
class Fragment(TypedDict):
    """쪽 조각 하나의 번역(코랩 셀 49 run_translation 의 한 바퀴 — 같은 쪽 번호가 두 번 나오면 조각도 둘)."""

    pageNum: PageNum
    status: Literal["translated", "error"]
    """error = 쪽 안에서 예외가 났다(LLM 호출 실패·한국어 잔존 등). 번역 글은 코랩대로
    `[TRANSLATION_ERROR page=n]` + 원문이고, 그 글이 병기·검수·자동수정으로 흘러간다(코랩 W7)."""
    error: str | None
    """status error 의 까닭(예외 글). translated 면 null."""
    editorialQa: EditorialQa | None
    """그 문체의 범용 QA 기록. 쪽이 그 게이트에 닿기 전에 실패했으면 null."""
    remainingKorean: list[str]
    """쪽이 한국어 잔존으로 실패했으면(error 가 「[치명] 번역 결과에 한국어가 남아…」) 남은 줄 — 코랩 셈 그대로 40줄·
    줄당 300자까지(error 글에는 앞 10줄만). 그 밖은 빈 목록. 용어집에 넣을 낱말을 화면이 고르게 한다."""


@with_config(FORBID)
class ReviewIssue(TypedDict):
    """검수 이슈 하나."""

    issueType: str
    """이슈 유형(코랩 ALLOWED_ISSUE_TYPES 열 가운데 하나 — 모델 이슈는 거른 뒤라 그 안이다)."""
    severity: str
    """심각도(모델이 낸 글자를 대문자로 — HIGH·MEDIUM·LOW 밖의 글자도 코랩대로 남는다)."""
    originalSpan: str
    """고칠 영문 구간. 번역문에 없으면 코랩대로 빈 글이다."""
    suggestion: str
    reason: str
    source: Literal["model", "glossary_rule"]
    """model = 검수 LLM 이 냄(거름 sanitize_issues 를 지남), glossary_rule = 용어집 정확 매칭 검사가 냄(결정적)."""


@with_config(FORBID)
class SeverityCounts(TypedDict):
    """심각도별 이슈 수(코랩 QA Word 요약표의 셈 — 글자가 정확히 HIGH·MEDIUM·LOW 인 것만)."""

    high: Count
    medium: Count
    low: Count


@with_config(FORBID)
class ReviewDone(TypedDict):
    """검수를 돌렸다."""

    status: Literal["reviewed", "parse_failed"]
    """parse_failed = 검수 LLM 의 답을 JSON 으로 못 읽어 모델 이슈 0 으로 친 것(코랩 W8). 용어집 검사 이슈는 남는다."""
    issues: list[ReviewIssue]
    counts: SeverityCounts
    message: None


@with_config(FORBID)
class ReviewStopped(TypedDict):
    """검수가 이 쪽에서 멈췄거나(call_failed — LLM 호출 실패, 코랩은 셀이 멈춘다) 앞 쪽이 멈춰 돌지 않았다(not_run)."""

    status: Literal["call_failed", "not_run"]
    issues: Annotated[list[ReviewIssue], Field(max_length=0)]
    counts: SeverityCounts
    message: str | None
    """call_failed 의 까닭. not_run 이면 null."""


Review = Annotated[ReviewDone | ReviewStopped, Field(discriminator="status")]


@with_config(FORBID)
class Page(TypedDict):
    """검수한 쪽 하나(코랩 셀 65 의 공통 쪽 — 원문과 번역에 다 있는 쪽 번호, 오름차순)."""

    pageNum: PageNum
    translated: str
    """그 쪽의 영문 번역(같은 번호의 조각을 합친 글)."""
    bilingual: str
    """그 쪽의 국문 병기본(제목 첫 줄에만 국문 병기)."""
    review: Review


@with_config(FORBID)
class GlossaryMiss(TypedDict):
    """용어집 반영 검사의 미반영 하나(코랩 셀 57 — 보고만, 결과를 바꾸지 않는다)."""

    pageNum: PageNum
    termKo: str
    termEn: str
    sourceCount: Count
    """그 쪽 원문에 국문 key 가 나온 횟수."""


@with_config(FORBID)
class SpanReplacement(TypedDict):
    """자동수정의 직접 치환 하나(이슈의 originalSpan → suggestion)."""

    issueType: str
    originalSpan: str
    suggestion: str


@with_config(FORBID)
class KoreanRepairRound(TypedDict):
    """자동수정 뒤 한국어 보정 한 번."""

    changed: bool
    remainingKorean: list[str]
    reason: Literal["table_pipe_signature_changed_safe_current_used"] | None
    """표 pipe 구조가 바뀌어 보정본을 버렸으면 그 까닭(코랩 글자). 아니면 null."""


@with_config(FORBID)
class AutofixPage(TypedDict):
    """자동수정한 쪽 하나(이슈나 남은 한국어가 있는 쪽만)."""

    pageNum: PageNum
    changed: bool
    reason: Literal["llm_repair_applied", "no_change_needed", "table_pipe_signature_changed_safe_current_used"]
    issueCount: Count
    spanReplacements: list[SpanReplacement]
    koreanRepairRounds: list[KoreanRepairRound]
    remainingKoreanAfter: list[str]


@with_config(FORBID)
class AutofixStop(TypedDict):
    """자동수정이 멈춘 자리(코랩은 셀이 멈춰 자동수정 파일을 쓰지 않는다)."""

    kind: Literal["remaining_korean", "call_failed"]
    """remaining_korean = 보정 뒤에도 한국어가 남음(코랩 ValueError), call_failed = LLM 호출 실패."""
    pageNum: PageNum
    remainingKorean: list[str]
    message: str


@with_config(FORBID)
class AutofixDone(TypedDict):
    """자동수정을 끝까지 돌렸다."""

    status: Literal["done"]
    pages: list[AutofixPage]
    translatedText: str
    """자동수정을 반영한 영문 번역 전문(쪽 번호 차례, 쪽 사이 빈 줄 하나)."""
    bilingualText: str
    """그 글로 다시 지은 국문 병기본 전문."""
    stop: None
    notRunReason: None


@with_config(FORBID)
class AutofixStopped(TypedDict):
    """자동수정이 멈췄다. 앞 쪽들의 결과도 버린다(코랩은 파일을 쓰지 않았다)."""

    status: Literal["stopped"]
    pages: Annotated[list[AutofixPage], Field(max_length=0)]
    translatedText: None
    bilingualText: None
    stop: AutofixStop
    notRunReason: None


@with_config(FORBID)
class AutofixNotRun(TypedDict):
    """자동수정을 돌리지 않았다."""

    status: Literal["not_run"]
    pages: Annotated[list[AutofixPage], Field(max_length=0)]
    translatedText: None
    bilingualText: None
    stop: None
    notRunReason: Literal["disabled", "review_stopped", "earlier_variant_stopped"]
    """disabled = 입력 autofix false, review_stopped = 검수가 멈춤, earlier_variant_stopped = 앞 문체의 자동수정이
    멈춤."""


Autofix = Annotated[AutofixDone | AutofixStopped | AutofixNotRun, Field(discriminator="status")]


@with_config(FORBID)
class Variant(TypedDict):
    """문체 하나의 결과."""

    label: VariantLabel
    translatedText: str
    """영문 번역 전문(코랩 번역 txt — 조각을 빈 줄 하나로 이은 것)."""
    bilingualText: str
    """국문 병기본 전문(코랩 병기 txt)."""
    fragments: list[Fragment]
    pages: list[Page]
    glossaryCheck: list[GlossaryMiss]
    autofix: Autofix


@with_config(FORBID)
class ResultWarning(TypedDict):
    """경고 한 줄 — 코랩이 print("[주의] …") 하던 자리마다 code 하나."""

    code: str
    """예: polish_tags_changed(윤문이 구조 태그를 바꿔 원 번역 유지), table_json_fallback(표 JSON 을 못 읽어 칸 단위
    번역), llm_truncated·llm_refused(LLM 답이 잘림·거절 — 코랩대로 그 글로 계속), duplicate_pages(같은 쪽 합침)."""
    message: str
    pageNum: PageNum | None
    variant: VariantLabel | None


@with_config(FORBID)
class TranslationDone(TypedDict):
    """translation.result@1 — 번역을 돌렸다."""

    schemaVersion: Literal["translation.result@1"]
    status: Literal["done"]
    rejection: None
    settings: Settings
    document: DocumentInfo
    variants: Annotated[list[Variant], Field(min_length=1)]
    warnings: list[ResultWarning]


@with_config(FORBID)
class TranslationRejected(TypedDict):
    """translation.result@1 — 번역을 시작하지 않았다."""

    schemaVersion: Literal["translation.result@1"]
    status: Literal["rejected"]
    rejection: Rejection
    settings: Settings
    document: DocumentInfo
    variants: Annotated[list[Variant], Field(max_length=0)]
    warnings: list[ResultWarning]


TranslationResult = Annotated[TranslationDone | TranslationRejected, Field(discriminator="status")]


INPUT_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    INPUT_SHAPE: TypeAdapter[TranslationInput](
        Annotated[TranslationInput, Field(title=INPUT_SHAPE, description="영문번역 한 건의 입력.")]
    )
}
"""입력 꼴 id → 검사기. validate_python(입력, strict=True) 로 꼴만 본다."""


def check_input(received: Mapping[str, Any]) -> Mapping[str, Any]:
    """입력 꼴만 본다(strict). 지나면 받은 dict 를 그대로(같은 객체) 돌려준다. 꼴이 아니면 pydantic ValidationError."""
    INPUT_SHAPES[INPUT_SHAPE].validate_python(received, strict=True)
    return received


RESULT_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    RESULT_SHAPE: TypeAdapter[TranslationDone | TranslationRejected](
        Annotated[TranslationResult, Field(title=RESULT_SHAPE, description="영문번역 한 건의 결과.")]
    )
}
"""결과 꼴 id → 검사기. validate_python(결과, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
