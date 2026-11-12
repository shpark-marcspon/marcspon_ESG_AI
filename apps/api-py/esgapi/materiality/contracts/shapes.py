"""입력 꼴 materiality.input@1 과 결과 꼴 materiality.result@1 의 정의. TypedDict → JSON 스키마(밴드 IR1a).

원천은 받은 중대성평가 IRO 코랩(MARC-ENT-155)이다. 1부(셀 17 규제·정책 조사, 셀 20 컨트로버시 키워드, 셀 22 컨트로버시
조사)는 코랩 그대로 재현한다 — 조사 호출에 기간이 안 가는 것까지(MARC-ENT-425 ①). 2부는 자리만 둔다(칸은 IR2a 가
JSON 꼴로 더하며 @2, MARC-ENT-425 ②).

입력은 꼴(키 있음·값의 타입)만 보고 값을 고치지 않는다 — 프롬프트가 산업·토픽 dict 의 파이썬 repr 을 글자째 싣는다
(발주서 §1-8). 엔진에 넘기는 dict 는 contracts/wire.py 가 코랩 키 이름·차례로 짓는다. 칸 이름은 camelCase 이고,
코랩 키가 데이터인 자리(valueChain 의 행, 결과 항목 Item)만 snake 키다.

결과의 갈래는 판별 칸 status 로 가른다: done·failed·not_run. 호출 실패·답을 읽지 못함·돌리지 않음·키워드 없음을 한
값으로 접지 않는다(발주서 §1-7). 모델의 JSON 은 받은 그대로(parsed) 싣고, 화면용 얇은 보기 items 를 곁에 둔다.

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다(use_attribute_docstrings). 프론트는 고정 파일
tests/data/flow-shapes/materiality.result@1.schema.json 을 읽는다. 꼴을 바꾸면 새 판이다. openapi 는 이름이 같은
컴포넌트를 하나로 합치므로 이름마다 Materiality 머리를 단다.
"""

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, Final, Literal, TypedDict

from pydantic import AfterValidator, ConfigDict, Field, JsonValue, TypeAdapter, with_config

INPUT_SHAPE: Final = "materiality.input@1"
RESULT_SHAPE: Final = "materiality.result@1"
FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True)

Count = Annotated[int, Field(ge=0)]
Sector = Literal["financial", "non_financial"]
"""financial = 금융권, non_financial = 비금융권(디자인 IR-02 의 금융/비금융). 규제 조사의 출처 목록(WHITELIST) 판을
고른다."""
Whitelist = Literal["cell71", "cell73"]
"""규제 조사 system 프롬프트 [8] 에 낀 출처 목록의 판: cell71 = 코랩 셀 71 금융권, cell73 = 코랩 셀 73 비금융권."""


@with_config(FORBID)
class MaterialityCompany(TypedDict):
    """기업 정보(코랩 셀 44 의 company). 1부 프롬프트에는 실리지 않는다."""

    name: str
    """기업명."""


@with_config(FORBID)
class MaterialityIndustry(TypedDict):
    """산업 하나(코랩 셀 11 industry 의 원소. 엔진에는 코랩 키 standard·industry_name·description 차례의 dict 로
    간다)."""

    standard: str
    """산업분류 기준(예: SASB·GICS·KSIC)."""
    industryName: str
    """산업명."""
    description: str
    """산업 설명."""


@with_config(FORBID)
class MaterialityTopic(TypedDict):
    """중대 토픽 하나(코랩 셀 11 topics 의 원소)."""

    topic: str
    """토픽명. 입력 안에서 겹치지 않는다."""
    description: str
    """토픽 설명(서브토픽을 모두 포괄하게)."""


@with_config(FORBID)
class MaterialitySubtopic(TypedDict):
    """서브토픽 하나(코랩 셀 44 subtopics_by_topic 의 원소)."""

    name: str
    description: str


@with_config(FORBID)
class MaterialityValueChainRow(TypedDict):
    """가치사슬 한 행(코랩 셀 44 value_chain 의 원소, 코랩 키 그대로 — MARC-ENT-421)."""

    business_unit: str
    business_unit_description: str
    value_chain_stage: str
    stakeholder: str
    business_activity: str


def _unique_topics(topics: list[MaterialityTopic]) -> list[MaterialityTopic]:
    names = [t["topic"] for t in topics]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    if duplicated:
        raise ValueError(f"topic 이 겹친다: {duplicated}")
    return topics


@with_config(FORBID)
class MaterialityInput(TypedDict):
    """materiality.input@1 — 중대성평가 IRO 한 건의 입력. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["materiality.input@1"]
    company: MaterialityCompany
    industries: Annotated[list[MaterialityIndustry], Field(min_length=1)]
    """산업 정의(코랩 셀 11 industry). 하나 이상."""
    topics: Annotated[list[MaterialityTopic], Field(min_length=1), AfterValidator(_unique_topics)]
    """중대 토픽 short-list(코랩 셀 11 topics). 하나 이상, topic 이 겹치면 거절한다(코랩은 뒤 것이 덮는다)."""
    geoScope: str
    """조사의 지리적 범위(코랩 location, 받은 글 그대로)."""
    userLocation: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    """웹 검색의 사용자 위치(코랩 user_location, ISO 3166-1 두 글자)."""
    mainLanguage: str
    """검색에 우선 쓸 언어(코랩 main_language)."""
    dateRange: str
    """조사 기간(코랩 date_range, 받은 글 그대로). 코랩대로 키워드 호출에만 간다."""
    sector: Sector
    latestEventMode: bool
    """2부의 서브토픽 영향 정의에서 웹 검색을 켤지(코랩 셀 44 latest_event_mode). 1부는 쓰지 않고 scope 에 남긴다."""
    subtopicsByTopic: dict[str, list[MaterialitySubtopic]] | None
    """토픽명 → 서브토픽 목록(코랩 셀 44). 2부 몫. 없는 토픽은 2부가 토픽 설명으로 하나 지어 넣는다."""
    valueChain: list[MaterialityValueChainRow] | None
    """가치사슬 활동 목록(코랩 셀 44 value_chain, MARC-ENT-421 의 선택 칸). 2부 몫."""


@with_config(FORBID)
class MaterialityScope(TypedDict):
    """무엇을 어떤 조건으로 조사했는지(입력에서 옮김)."""

    topicCount: Count
    """입력 토픽 수."""
    sector: Sector
    whitelist: Whitelist
    dateRange: str
    """입력의 조사 기간. 코랩대로 키워드 호출에만 갔다 — 규제·컨트로버시 조사 호출에는 안 갔다."""
    geoScope: str
    userLocation: str
    mainLanguage: str
    latestEventMode: bool


@with_config(FORBID)
class MaterialityPromptIds(TypedDict):
    """호출마다 쓴 프롬프트 id(core.llm 의 `모듈/이름@판`). 돌리지 않았거나 아직 없으면 null."""

    regulation: str | None
    keywords: str | None
    controversy: str | None


@with_config(FORBID)
class MaterialitySettings(TypedDict):
    """실행 설정(코랩 셀 8·11 의 상수). 실제로 불린 모델·사용량은 실행기의 기록이 진실이다. 모두 글자거나 null."""

    model: str | None
    """모델 이름(코랩 model)."""
    temperature: str | None
    """temperature(repr(float) 글자. 코랩 0.1)."""
    searchContextSize: str | None
    """웹 검색 도구의 search_context_size(코랩 low)."""
    promptIds: MaterialityPromptIds


FailureKind = Literal[
    "unparsable",
    "budget_exceeded",
    "truncated",
    "refusal",
    "provider_error",
    "timeout",
    "tool_executor_raised",
    "schema_mismatch",
]
"""실패 갈래. unparsable 밖은 core.llm 의 LlmResult·ToolLoopFailure 갈래 이름이다(dataverify 계약의 판별 복사 — 계약은
core 를 import 하지 않고, 시험이 견준다)."""


@with_config(FORBID)
class MaterialityFailure(TypedDict):
    """호출이나 답 읽기가 실패한 까닭."""

    kind: FailureKind
    """unparsable = 모델의 답을 읽지 못함(빈 답·`{` 없음·JSON 아님·꼴이 다름). 그 밖은 모델 호출의 실패 갈래(core.llm 의
    이름 그대로)."""
    message: str
    """실패 갈래의 설명(모델 글·공급사 메시지·고객 데이터는 싣지 않는다)."""


@with_config(FORBID)
class MaterialityTopicKeywords(TypedDict):
    """토픽 하나의 검색 키워드(코랩 topic_to_keywords 의 한 쌍)."""

    topic: str
    """모델이 낸 토픽명(입력 토픽명과 다를 수 있다 — 다르면 그 입력 토픽은 「(키워드 없음)」으로 조사된다)."""
    keywords: list[str]


@with_config(FORBID)
class MaterialityKeywordsDone(TypedDict):
    """키워드 도출(코랩 셀 20)을 마쳤다."""

    status: Literal["done"]
    byTopic: list[MaterialityTopicKeywords]
    """모델이 낸 차례. 같은 토픽이 둘이면 코랩처럼 한 줄(첫 자리, 뒤 것의 키워드)만 남는다."""
    raw: str
    """모델의 답 원문."""


@with_config(FORBID)
class MaterialityKeywordsFailed(TypedDict):
    """키워드 도출이 실패했다. 컨트로버시 조사는 키워드 없이 계속한다(코랩대로)."""

    status: Literal["failed"]
    raw: str | None
    """읽지 못한 답의 원문(unparsable). 호출이 실패했으면 null."""
    failure: MaterialityFailure


@with_config(FORBID)
class MaterialityKeywordsNotRun(TypedDict):
    """키워드 도출을 돌리지 않았다."""

    status: Literal["not_run"]
    message: str


MaterialityKeywords = Annotated[
    MaterialityKeywordsDone | MaterialityKeywordsFailed | MaterialityKeywordsNotRun, Field(discriminator="status")
]

Cell = str | None
"""항목 칸 하나. 모델이 낸 값이 글이면 그대로, 글이 아니면 json.dumps(ensure_ascii=False) 글자, 없거나 null 이면
null."""


@with_config(FORBID)
class MaterialityRegulationItem(TypedDict):
    """규제·정책 업데이트 하나(코랩 셀 17 의 UpdateItem 에서 셀 33 의 표시 칸 차례). 모델 JSON 의 얇은 보기다."""

    title: Cell
    summary: Cell
    jurisdiction: Cell
    authority: Cell
    event_date: Cell
    publish_date: Cell
    status: Cell
    primary_url: Cell
    region: str | None
    """그 항목이 들어 있던 results 의 키(예: KR·EU·US). results 가 dict 가 아니었으면 null. 엑셀 F 열 글에는 안
    넣는다."""


@with_config(FORBID)
class MaterialityControversyItem(TypedDict):
    """컨트로버시 하나(코랩 셀 22 의 ControversyItem 에서 셀 33 의 표시 칸 차례). 모델 JSON 의 얇은 보기다."""

    title: Cell
    date: Cell
    summary: Cell
    severity: Cell
    status: Cell
    url: Cell
    region: None
    """규제 항목과 칸을 맞춘 자리. 컨트로버시는 늘 null."""


@with_config(FORBID)
class MaterialityRegulationDone(TypedDict):
    """규제·정책 조사(코랩 셀 17)의 답을 JSON 객체로 읽었다."""

    status: Literal["done"]
    parsed: dict[str, JsonValue]
    """모델의 JSON 객체(받은 그대로)."""
    items: list[MaterialityRegulationItem]
    """parsed 에서 셀 33 규칙으로 뽑은 항목(dict 가 아닌 원소는 빼고 경고 items_skipped)."""
    selfCheck: dict[str, JsonValue] | None
    """parsed 의 self_check(객체일 때만, 아니면 null)."""
    topicNameMismatch: Literal[False]
    """코랩 셀 17 은 답의 topic_name 을 견주지 않는다 — 늘 false."""


@with_config(FORBID)
class MaterialityControversyDone(TypedDict):
    """컨트로버시 조사(코랩 셀 22)의 답을 JSON 객체로 읽었다."""

    status: Literal["done"]
    parsed: dict[str, JsonValue]
    """모델의 JSON 객체(받은 그대로). 답의 topic_name 이 입력 토픽명과 다르면 코랩대로 topic_name_expected 가 더해져
    있다."""
    items: list[MaterialityControversyItem]
    """parsed 에서 셀 33 규칙으로 뽑은 항목(dict 가 아닌 원소는 빼고 경고 items_skipped)."""
    selfCheck: dict[str, JsonValue] | None
    """parsed 의 self_check(객체일 때만, 아니면 null)."""
    topicNameMismatch: bool
    """답의 topic_name 이 입력 토픽명과 달랐는지(코랩 셀 22 의 견줌)."""


@with_config(FORBID)
class MaterialityOutcomeFailed(TypedDict):
    """호출이 실패했거나 답을 JSON 객체로 읽지 못했다."""

    status: Literal["failed"]
    raw: str | None
    """코랩 묶음의 원문 칸 그대로(utm 지운 답. 코랩대로 호출 실패면 빈 글). 원문이 없으면 null."""
    parseError: str | None
    """코랩 묶음의 parse_error 그대로 — 규제는 str(예외), 컨트로버시는 repr(예외) 이고 호출 실패면 no_result
    (코랩대로)."""
    failure: MaterialityFailure


@with_config(FORBID)
class MaterialityOutcomeNotRun(TypedDict):
    """돌리지 않았다."""

    status: Literal["not_run"]
    message: str


MaterialityRegulation = Annotated[
    MaterialityRegulationDone | MaterialityOutcomeFailed | MaterialityOutcomeNotRun, Field(discriminator="status")
]
MaterialityControversy = Annotated[
    MaterialityControversyDone | MaterialityOutcomeFailed | MaterialityOutcomeNotRun, Field(discriminator="status")
]


@with_config(FORBID)
class MaterialityTopicResult(TypedDict):
    """토픽 하나의 1부 결과(입력 차례)."""

    topic: str
    description: str
    keywordStr: str | None
    """컨트로버시 프롬프트에 실은 키워드 글 그대로(「, 」로 이음, 없으면 「(키워드 없음)」). 조사를 돌리지 않았으면
    null."""
    regulation: MaterialityRegulation
    controversy: MaterialityControversy


@with_config(FORBID)
class MaterialityPart1(TypedDict):
    """1부 — 웹 리서치(규제·정책·컨트로버시)."""

    keywords: MaterialityKeywords
    topics: list[MaterialityTopicResult]


@with_config(FORBID)
class MaterialityPart2NotRun(TypedDict):
    """2부 — IRO 분석. 이 판에서는 돌리지 않는다(칸은 다음 판)."""

    status: Literal["not_run"]
    message: str


WarningCode = Literal[
    "subtopic_autofilled",
    "subtopic_key_unmatched",
    "keywords_missing_for_topic",
    "keywords_duplicate_topic",
    "topic_name_mismatch",
    "items_skipped",
    "items_unrecognized",
]


@with_config(FORBID)
class MaterialityWarning(TypedDict):
    """경고 한 줄."""

    code: WarningCode
    """subtopic_autofilled = 서브토픽이 없어 토픽 설명으로 하나 지어 넣음, subtopic_key_unmatched = 서브토픽 키가 어느
    토픽명과도 맞지 않음(코랩은 조용히 버린다), keywords_missing_for_topic = 그 토픽의 키워드가 없어
    「(키워드 없음)」으로 조사함, keywords_duplicate_topic = 키워드 답에 같은 토픽이 둘 이상(뒤 것이 남음),
    topic_name_mismatch = 컨트로버시 답의 topic_name 이 입력 토픽명과 다름, items_skipped = 항목 목록에 객체가
    아닌 원소가 있어 보기에서 뺌, items_unrecognized = 답(done)에서 항목 목록 자리를 알아보지 못해 보기가 빔."""
    message: str
    topic: str | None
    """그 경고의 토픽(입력 토픽명). 토픽에 매이지 않으면 null."""


@with_config(FORBID)
class MaterialityResult(TypedDict):
    """materiality.result@1 — 중대성평가 IRO 한 건의 결과. schemaVersion 이 첫 키다. 사용량·비용은 싣지 않는다(실행기의
    기록이 진실이다)."""

    schemaVersion: Literal["materiality.result@1"]
    company: MaterialityCompany
    """입력의 company 그대로."""
    scope: MaterialityScope
    settings: MaterialitySettings
    part1: MaterialityPart1
    part2: MaterialityPart2NotRun
    warnings: list[MaterialityWarning]


# ── materiality.result@2 (밴드 IR2a, MARC-ENT-425 ②) ─────────────────────────────────────────────────────────
# 1부 칸은 @1 TypedDict 를 그대로 쓰고(part1·scope·company), 2부(코랩 셀 46 환경·사회 영향, 셀 50 재무 영향, 셀 55
# 재무 Impact Pathway)의 칸을 더한다. 모델의 JSON 은 받은 그대로(parsed) 싣고, 화면용 얇은 보기 rows 를 곁에 둔다. 2부의
# 출력 형식 절만 JSON 으로 바꿨고(프롬프트 글은 코랩 그대로) 키는 셀 50 의 JSON 꼴(snake)을 따른다 — rows 는 camelCase.

RESULT_SHAPE_V2: Final = "materiality.result@2"
Part2Source = Literal["result", "shortlist"]
"""2부 입력의 토픽별 규제·컨트로버시 글을 어디서 지었는지: result = 1부 결과 꼴 데이터(코랩 셀 39 의 RAW_JSON A1
길), shortlist = 사람이 고쳐 다시 올린 Short-list 엑셀(코랩 셀 39 의 고친 Shortlist 길 — 읽기는 다음 밴드)."""
Part2Phase = Literal["impact", "financial", "pathway"]
"""2부의 호출 단계: impact = 셀 46 환경·사회 영향, financial = 셀 50 재무 영향, pathway = 셀 55 재무 Impact Pathway."""
WarningPhase = Literal["regulation", "keywords", "controversy", "impact", "financial", "pathway", "report"]
"""경고가 난 단계(1부 셋 · 2부 셋 · report = 엑셀 짓기)."""


@with_config(FORBID)
class MaterialityPart2PromptIds(TypedDict):
    """2부 호출마다 쓴 프롬프트 id(core.llm 의 `모듈/이름@판`). 돌리지 않았으면 null."""

    impact: str | None
    financial: str | None
    pathway: str | None


@with_config(FORBID)
class MaterialityPart2Settings(TypedDict):
    """2부의 실행 설정(코랩 셀 46·50·55 의 상수). temperature 는 코랩 2부 러너(셀 8)가 싣지 않아 칸이 없다."""

    model: str | None
    """실제로 불린 모델(호출이 하나도 없었으면 null). 코랩 셀 46 model = gpt-4.1."""
    maxOutputTokens: Count
    """호출마다의 출력 토큰 상한(코랩은 주지 않는다 — 모델의 상한을 넘긴다)."""
    latestEventMode: bool
    """웹 검색(search_context_size low)을 켰는지(코랩 셀 44 latest_event_mode)."""
    promptIds: MaterialityPart2PromptIds


@with_config(FORBID)
class MaterialitySettings2(TypedDict):
    """실행 설정 — @1 의 1부 칸 그대로에 2부 칸(part2)을 더했다."""

    model: str | None
    """1부의 모델 이름(@1 그대로)."""
    temperature: str | None
    """1부의 temperature(@1 그대로)."""
    searchContextSize: str | None
    """1부 웹 검색 도구의 search_context_size(@1 그대로)."""
    promptIds: MaterialityPromptIds
    part2: MaterialityPart2Settings


@with_config(FORBID)
class MaterialityContextItem(TypedDict):
    """맥락 항목 하나(셀 50 JSON 꼴 context.regulations·controversies 의 원소 {title, summary, url}). 셀 65 지시의 키
    source 대신 셀 50 의 url 을 쓴다."""

    title: Cell
    summary: Cell
    url: Cell


@with_config(FORBID)
class MaterialityContext(TypedDict):
    """한 영향의 맥락(셀 50 정규화: context 가 객체가 아니면 빈 것, 두 칸이 목록이 아니면 빈 목록). 객체가 아닌 원소는
    보기에서 빼고 경고 items_skipped."""

    regulations: list[MaterialityContextItem]
    controversies: list[MaterialityContextItem]


@with_config(FORBID)
class MaterialityImpactRow(TypedDict):
    """환경·사회 영향 하나(셀 46 — 출력 형식 절을 셀 50 꼴 JSON 으로 바꾼 impacts 의 원소)."""

    impactDefinition: Cell
    impactType: Cell
    """모델이 낸 값 그대로(시킨 값은 긍정·부정 — 밖이면 경고 impact_type_unexpected, 값은 두고)."""
    valueChainActivities: list[str]
    """모델이 고른 가치사슬 활동(입력 valueChain 의 business_activity 글이어야 한다 — 아니면 경고
    value_chain_activity_unknown, 값은 두고). 목록이 아니면 빈 목록, 글이 아닌 원소는 json.dumps 글자."""
    context: MaterialityContext


@with_config(FORBID)
class MaterialityFinancialRow(TypedDict):
    """재무 영향 하나(셀 50 JSON 꼴 impacts 의 원소 + value_chain_activities)."""

    impactDefinition: Cell
    impactType: Cell
    """모델이 낸 값 그대로(시킨 값은 리스크·기회)."""
    riskType: Cell
    """모델이 낸 값 그대로(시킨 값은 리스크-규제 및 법률·리스크-평판·리스크-기술·리스크-시장 또는 null)."""
    valueChainActivities: list[str]
    context: MaterialityContext


@with_config(FORBID)
class MaterialityPathwayRow(TypedDict):
    """재무 Impact Pathway 하나(셀 55 — 출력 형식 절을 JSON 으로 바꾼 pathways 의 원소). 영향 유형·리스크 종류·맥락은
    모델 칸이 아니라 i 로 재무 rows 에서 잇는다(셀 65 「요약·편집 금지」)."""

    i: int | None
    """모델이 낸 행 번호(1부터, 재무 rows 의 차례). 정수(또는 숫자 글)가 아니면 null — 그 행은 잇지 못한다."""
    impactDefinition: Cell
    impactDriver: Cell
    """① Impact Driver."""
    businessImpact: Cell
    """② 비즈니스 영향."""
    financialImpact: Cell
    """③ 재무 영향."""
    impactType: Cell
    """i 번째 재무 row 의 impactType(잇지 못하면 null)."""
    riskType: Cell
    """i 번째 재무 row 의 riskType(잇지 못하면 null)."""
    context: MaterialityContext
    """i 번째 재무 row 의 context(잇지 못하면 빈 것)."""


@with_config(FORBID)
class MaterialityPart2Failed(TypedDict):
    """호출이 실패했거나 답을 JSON 객체로 읽지 못했다."""

    status: Literal["failed"]
    raw: str | None
    """모델의 답 원문(잘린 부분 글 포함). 호출이 실패해 답이 없으면 null."""
    parseError: str | None
    """읽기 실패의 까닭(예외 이름·위치 — 모델 글은 싣지 않는다). 호출 실패면 null."""
    failure: MaterialityFailure


@with_config(FORBID)
class MaterialityImpactDone(TypedDict):
    """환경·사회 영향(셀 46)의 답을 JSON 객체로 읽었다."""

    status: Literal["done"]
    parsed: dict[str, JsonValue]
    """모델의 JSON 객체(받은 그대로)."""
    rows: list[MaterialityImpactRow]
    """parsed.impacts 에서 셀 50 정규화 규칙으로 뽑은 보기(객체가 아닌 원소는 빼고 경고 rows_dropped)."""


@with_config(FORBID)
class MaterialityFinancialDone(TypedDict):
    """재무 영향(셀 50)의 답을 JSON 객체로 읽었다."""

    status: Literal["done"]
    parsed: dict[str, JsonValue]
    rows: list[MaterialityFinancialRow]


@with_config(FORBID)
class MaterialityPathwayDone(TypedDict):
    """재무 Impact Pathway(셀 55)의 답을 JSON 객체로 읽었다."""

    status: Literal["done"]
    parsed: dict[str, JsonValue]
    rows: list[MaterialityPathwayRow]
    """parsed.pathways 의 원소(모델 차례). 객체가 아닌 원소는 빼고 경고 rows_dropped."""


MaterialityImpact = Annotated[
    MaterialityImpactDone | MaterialityPart2Failed | MaterialityOutcomeNotRun, Field(discriminator="status")
]
MaterialityFinancial = Annotated[
    MaterialityFinancialDone | MaterialityPart2Failed | MaterialityOutcomeNotRun, Field(discriminator="status")
]
MaterialityPathway = Annotated[
    MaterialityPathwayDone | MaterialityPart2Failed | MaterialityOutcomeNotRun, Field(discriminator="status")
]
"""not_run = 재무가 실패했거나 rows 가 0 이라 부르지 않음(코랩 셀 55 의 [MISSING fin_impact])."""


@with_config(FORBID)
class MaterialitySubtopicResult(TypedDict):
    """서브토픽 하나의 2부 결과(입력 차례, 지어 넣은 것은 뒤 — 코랩 셀 46)."""

    name: str
    description: str
    autofilled: bool
    """서브토픽이 없어 토픽 설명으로 지어 넣었는지(코랩 셀 46)."""
    impact: MaterialityImpact
    financial: MaterialityFinancial
    pathway: MaterialityPathway


@with_config(FORBID)
class MaterialityPart2TopicResult(TypedDict):
    """토픽 하나의 2부 결과(입력 차례)."""

    topic: str
    description: str
    subtopics: list[MaterialitySubtopicResult]


@with_config(FORBID)
class MaterialityPart2Input(TypedDict):
    """2부 입력을 어디서 지었는지."""

    source: Part2Source


@with_config(FORBID)
class MaterialityPart2Done(TypedDict):
    """2부 — IRO 분석을 돌렸다(호출이 실패한 서브토픽도 이 갈래 안에 failed 로 남는다)."""

    status: Literal["done"]
    input: MaterialityPart2Input
    topics: list[MaterialityPart2TopicResult]


MaterialityPart2 = Annotated[MaterialityPart2NotRun | MaterialityPart2Done, Field(discriminator="status")]

WarningCode2 = Literal[
    "subtopic_autofilled",
    "subtopic_key_unmatched",
    "keywords_missing_for_topic",
    "keywords_duplicate_topic",
    "topic_name_mismatch",
    "items_skipped",
    "items_unrecognized",
    "answer_truncated",
    "xlsx_cell_truncated",
    "value_chain_activity_unknown",
    "pathway_row_mismatch",
    "rows_dropped",
    "impact_type_unexpected",
    "items_out_of_range",
    "item_date_unreadable",
]


@with_config(FORBID)
class MaterialityWarning2(TypedDict):
    """경고 한 줄(@1 의 칸 + phase·subtopic)."""

    code: WarningCode2
    """@1 의 일곱(뜻 그대로) + answer_truncated = 답이 출력 상한에서 잘림(읽혔으면 done, 못 읽었으면 failed·truncated),
    xlsx_cell_truncated = 엑셀 한 칸(32,767자)을 넘어 앞부분만 담고 표시를 붙임, value_chain_activity_unknown = 모델이
    고른 가치사슬 활동이 입력 valueChain 에 없음, pathway_row_mismatch = Pathway 행 수·영향 정의가 재무 rows 와 다르거나
    i 로 잇지 못함, rows_dropped = impacts·pathways 목록에서 객체가 아닌 원소를 뺌(셀 50 정규화), impact_type_unexpected
    = 영향 유형·리스크 종류가 시킨 값 밖(값은 그대로 둠), items_out_of_range = 2부 입력을 지을 때 날짜가 입력 dateRange
    밖인 1부 항목을 뺌(part1 칸은 원본 그대로), item_date_unreadable = 1부 항목의 날짜를 읽지 못해 거르지 않고 남김."""
    message: str
    topic: str | None
    """그 경고의 토픽(입력 토픽명). 토픽에 매이지 않으면 null."""
    phase: WarningPhase | None
    """경고가 난 단계. 1부 결과에서 옮겨 온 경고처럼 모르면 null."""
    subtopic: str | None
    """그 경고의 서브토픽 이름. 서브토픽에 매이지 않으면 null."""


@with_config(FORBID)
class MaterialityResult2(TypedDict):
    """materiality.result@2 — 중대성평가 IRO 한 건의 결과(1부 + 2부). schemaVersion 이 첫 키다. 1부 칸은 @1 꼴 그대로다.
    사용량·비용은 싣지 않는다(실행기의 기록이 진실이다)."""

    schemaVersion: Literal["materiality.result@2"]
    company: MaterialityCompany
    scope: MaterialityScope
    settings: MaterialitySettings2
    part1: MaterialityPart1
    part2: MaterialityPart2
    warnings: list[MaterialityWarning2]


@with_config(FORBID)
class Part2Topic(TypedDict):
    """2부 입력의 토픽 하나(엔진 꼴). 글 둘은 2부 user 프롬프트에 그대로 들어간다(코랩 셀 50 꼴 —
    json.dumps(묶음, ensure_ascii=False, indent=2) 또는 「제공된 … 정보 없음」)."""

    topic: str
    description: str
    regulationText: str
    controversyText: str


class Part2Input(TypedDict):
    """2부 엔진의 입력(결과 꼴이 아니다 — 저장하지 않는다). company = 회사명(코랩 {company}), industry = 코랩 셀 11 키의
    산업 목록, valueChain = 입력 그대로(없으면 null), subtopics = 코랩 셀 44 subtopics_by_topic 꼴(지어 넣기 전)."""

    company: str
    industry: list[dict[str, str]]
    valueChain: list[dict[str, str]] | None
    latestEventMode: bool
    topics: list[Part2Topic]
    subtopics: dict[str, list[dict[str, str]]]
    source: Part2Source


INPUT_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    INPUT_SHAPE: TypeAdapter[MaterialityInput](
        Annotated[MaterialityInput, Field(title=INPUT_SHAPE, description="중대성평가 IRO 한 건의 입력.")]
    )
}
"""입력 꼴 id → 검사기. validate_python(입력, strict=True) 로 꼴만 보고, 흐름은 받은 dict 를 그대로 쓴다."""


def check_input(received: Mapping[str, Any]) -> Mapping[str, Any]:
    """입력 꼴만 본다(strict). 지나면 받은 dict 를 그대로(같은 객체) 돌려준다 — 검사 결과(복사본)를 쓰지 않는다(발주서
    §1-8: 프롬프트가 받은 글을 그대로 싣는다). 꼴이 아니면 pydantic ValidationError."""
    INPUT_SHAPES[INPUT_SHAPE].validate_python(received, strict=True)
    return received


# @2 를 앞에 끼워 @1 의 줄을 그대로 둔다(IR2a: 더하기만 — 포매터가 @1 끝 줄에 쉼표를 달지 않게).
# fmt: off
RESULT_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    RESULT_SHAPE_V2: TypeAdapter[MaterialityResult2](
        Annotated[
            MaterialityResult2, Field(title=RESULT_SHAPE_V2, description="중대성평가 IRO 한 건의 결과(1부 + 2부).")
        ]
    ),
    RESULT_SHAPE: TypeAdapter[MaterialityResult](
        Annotated[MaterialityResult, Field(title=RESULT_SHAPE, description="중대성평가 IRO 한 건의 결과.")]
    )
}
# fmt: on
"""결과 꼴 id → 검사기. validate_python(결과, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""

REGULATION_ITEM_KEYS: Final[Sequence[str]] = tuple(
    k for k in MaterialityRegulationItem.__annotations__ if k != "region"
)
"""규제 항목의 표시 칸 차례(코랩 셀 33 R/1651)."""
CONTROVERSY_ITEM_KEYS: Final[Sequence[str]] = tuple(
    k for k in MaterialityControversyItem.__annotations__ if k != "region"
)
"""컨트로버시 항목의 표시 칸 차례(코랩 셀 33 R/1653)."""
