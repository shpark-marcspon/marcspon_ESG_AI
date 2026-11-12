"""입력 꼴 dataverify.input@1 과 결과 꼴 dataverify.result@2 의 정의. TypedDict → JSON 스키마(밴드 DV1a, @2 는 DV1e).

원천은 받은 데이터 검증 코랩(MARC-ENT-156)이다. 입력의 `data` 는 코랩 셀 2 의 dict(테마 → 항목 목록, 항목 키 11개)를
받은 그대로 두고, 그 밖의 칸은 camelCase 다. 입력은 꼴(키 있음·값의 타입)만 보고 값을 고치지 않는다 — 흐름은 검사를
지난 결과가 아니라 받은 dict 를 그대로 넘긴다(프롬프트가 입력을 json.dumps 로 글자째 싣는다. 발주서 §1-9).
항목(EdkItem)은 모르는 키를 받는다(코랩도 거르지 않는다). 결과 꼴은 모르는 키를 받지 않는다.

결과의 수(value·diff·tolerance·temperature)는 repr(float) 의 글자다(inventory/contracts/shapes.py 의 약속 — 십진은
문자열, 없음은 null). 갈래는 판별 칸으로 가른다: 단계는 status, 검사 기록은 kind. 「값 없음」(N/A)·도구 오류·
검사 FAIL 은 서로 다른 칸이나 갈래다.

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다(use_attribute_docstrings). 프론트는 고정 파일
tests/data/flow-shapes/dataverify.result@2.schema.json 을 읽는다. 꼴을 바꾸면 새 판이다.

@2(밴드 DV1e, MARC-ISSUE-206 2번): 실패 갈래를 message 앞머리가 아니라 failure.kind 로 가른다(core.llm 의 갈래 이름
그대로, call_failed 없앰) · 상한 실패의 자리 failure.budgetSource · 잘린 인사이트의 부분 원문 insight.partialText.
openapi 컴포넌트 이름이 다른 모듈의 것과 겹치던 셋(Settings·ResultWarning·ReviewDone)은 Dataverify 머리를 단다 —
겹치면 한 API 의 컴포넌트가 하나로 합쳐져 남의 꼴을 덮는다. 칸과 JSON 인스턴스는 그대로다.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, TypedDict

from pydantic import ConfigDict, Field, JsonValue, TypeAdapter, with_config

INPUT_SHAPE: Final = "dataverify.input@1"
RESULT_SHAPE: Final = "dataverify.result@2"
FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True)

Count = Annotated[int, Field(ge=0)]
Seq = Annotated[int, Field(ge=1)]
Year = Annotated[str, Field(pattern=r"^[0-9]{4}$")]

EdkValue = str | int | float | None
"""EDK 칸의 값. 수·글자(「1,234」 같은 쉼표 글자 포함)·null 을 받은 그대로 둔다."""

EdkItem = TypedDict(
    "EdkItem",
    {
        "ID": EdkValue,
        "테마": EdkValue,
        "항목": EdkValue,
        "대분류": EdkValue,
        "중분류": EdkValue,
        "소분류": EdkValue,
        "입력 방식": EdkValue,
        "단위": EdkValue,
        "values": dict[str, EdkValue],
        "핵심데이터": EdkValue,
        "메모": EdkValue,
    },
)
"""EDK 정량 데이터의 한 행(코랩 셀 2 의 항목 키 11개). values 는 연도 글자 → 값. 모르는 키(담당자 등)를 받는다."""
with_config(ConfigDict(extra="allow"))(EdkItem)


@with_config(FORBID)
class Company(TypedDict):
    """기업 정보(코랩 셀 10·18 USER 의 「기업 정보」 네 줄)."""

    name: str
    """기업명."""
    sasbIndustry: str
    """SASB 산업분류."""
    materialTopics: list[str]
    """주요 중대토픽. 프롬프트에는 「, 」로 이어 한 줄로 싣는다(코랩대로)."""
    reportingYear: Year
    """보고연도(YYYY)."""


@with_config(FORBID)
class DataverifyInput(TypedDict):
    """dataverify.input@1 — 데이터 검증 한 건의 입력. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["dataverify.input@1"]
    company: Company
    data: dict[str, list[EdkItem]]
    """테마 이름 → 항목 목록(코랩 셀 2 의 data 그대로). 검증 대상은 테마 「환경」뿐이다(코랩 셀 3)."""


@with_config(FORBID)
class Scope(TypedDict):
    """무엇을 봤는지."""

    themes: list[str]
    """검증한 테마(코랩대로 「환경」 하나). 입력에 그 테마가 없으면 빈 목록이다."""
    itemCount: Count
    """검증한 테마의 항목 수."""
    keyItemCount: Count
    """그 가운데 핵심데이터가 「Y」인 항목 수."""
    years: list[str]
    """그 항목들의 values 에 나온 연도 글자(겹침 없이, 오름차순)."""


@with_config(FORBID)
class MaxSteps(TypedDict):
    """단계마다 모델 호출의 최대 횟수(코랩 SET_MAX_STEPS). 그 단계를 돌리지 않았으면 null."""

    plan: int | None
    review: int | None
    insight: int | None


@with_config(FORBID)
class PromptIds(TypedDict):
    """단계마다 쓴 프롬프트 id(core.llm 의 `모듈/이름@판`). 그 단계를 돌리지 않았으면 null."""

    plan: str | None
    review: str | None
    insight: str | None


@with_config(FORBID)
class DataverifySettings(TypedDict):
    """실행 설정(코랩 셀 10·14·18 의 상수). 실제로 불린 모델·사용량은 실행기의 기록이 진실이다."""

    model: str | None
    """모델 이름(코랩 설정). 모델을 부르지 않았으면 null."""
    tolerance: str
    """검사 도구의 허용 오차(repr(float) 글자. 코랩 1.1)."""
    temperature: str | None
    """모델의 temperature(repr(float) 글자). 모델을 부르지 않았으면 null."""
    maxSteps: MaxSteps
    promptIds: PromptIds


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
"""실패 갈래. unparsable 밖은 core.llm 의 LlmResult·ToolLoopFailure 갈래 이름이다(손으로 적고 시험이 견준다 — 계약은
core 를 import 하지 않는다)."""


@with_config(FORBID)
class Failure(TypedDict):
    """단계가 실패한 까닭."""

    kind: FailureKind
    """unparsable = 모델의 답을 읽지 못함(계산 Plan 이 python list 가 아님). 그 밖은 모델 호출의 실패 갈래(core.llm 의
    이름 그대로): budget_exceeded = 비용 상한, truncated = 출력이 잘림, refusal = 모델이 거절, provider_error = 공급사
    오류, timeout = 시간 한도, tool_executor_raised = 도구 실행이 예외를 던짐, schema_mismatch = 답이 스키마에 맞지
    않음."""
    # 계약은 budget_exceeded + budgetSource null 도 받는다(꼴 검사는 갈래와 자리를 엮지 않는다).
    budgetSource: Literal["guard", "loop"] | None
    """budget_exceeded 일 때만 값: guard = 기존 비용 상한(BudgetLimit), loop = 단계 고리 한 번의 상한(max_cost_usd).
    그 밖의 갈래는 null."""
    # 상한의 자리는 고리(flows/colab_156.py failure_message)만 싣는다 — 끈 인사이트(ended_call)의 message 에는 없다.
    message: str
    """실패 갈래와 상한의 자리·공급사 상태 번호·도구 이름까지(모델 글·공급사 메시지·고객 데이터는 싣지 않는다)."""


@with_config(FORBID)
class PlanDone(TypedDict):
    """계산 Plan(코랩1번)을 마쳤다."""

    status: Literal["done"]
    partial: bool
    """true = 최대 횟수에 닿아 남은 도구 호출을 버리고 마지막 답을 썼다, false = 고리가 끝까지 돌았다."""
    formulas: list[str]
    """검증 산식(모델이 낸 python list 의 원소, 그 차례)."""
    raw: str
    """모델의 답 원문."""
    failure: None


@with_config(FORBID)
class PlanFailed(TypedDict):
    """계산 Plan 이 실패했다. partial 은 null 이다."""

    status: Literal["failed"]
    partial: None
    formulas: Annotated[list[str], Field(max_length=0)]
    raw: str | None
    """읽지 못한 답의 원문(unparsable). 호출이 실패했으면 null."""
    failure: Failure


@with_config(FORBID)
class PlanNotRun(TypedDict):
    """계산 Plan 을 돌리지 않았다."""

    status: Literal["not_run"]
    partial: None
    formulas: Annotated[list[str], Field(max_length=0)]
    raw: None
    failure: None


Plan = Annotated[PlanDone | PlanFailed | PlanNotRun, Field(discriminator="status")]

Item = Annotated[list[JsonValue], Field(min_length=4, max_length=4)]
"""값 조회가 받은 [대분류, 중분류, 소분류, 단위](모델이 준 인자 그대로 — 글자가 아닐 수 있고, 빠졌으면 null)."""


@with_config(FORBID)
class ValueCheck(TypedDict):
    """값 조회(value_of_by_name) 한 번. value 와 na 는 늘 맞물린다 — 값이 있으면 na false, 「N/A」면 value null·na
    true(contracts/wire.to_check 가 na 를 value 에서 지어 보장하고 시험이 못박는다). 꼴의 갈래로 가르지 않은 까닭:
    kind 안에서 na 로 한 번 더 가르면 JSON 스키마의 discriminator mapping 이 OpenAPI 꼴(글자 → $ref)을 벗어난다."""

    seq: Seq
    """검토 단계의 도구 호출 차례(1부터)."""
    tool: str
    """부른 도구의 이름."""
    kind: Literal["value"]
    item: Item
    year: JsonValue
    """연도(모델이 준 인자 그대로)."""
    value: str | None
    """찾은 값(repr(float) 글자). 도구가 「N/A」를 돌려줬으면 null 이고 na 가 true 다."""
    na: bool
    """도구가 「N/A」를 돌려줬는지(항목 없음·값 빔·수로 못 읽음)."""


@with_config(FORBID)
class ByNameItems(TypedDict, total=False):
    """이름형 도구(*_by_name·*_by_names)가 받은 항목(모델이 준 JSON 값 그대로 — 보통 [대분류, 중분류, 소분류, 단위]
    배열, addends 는 그 배열의 목록). 도구마다 쓰는 열쇠만 있다: sum_check_by_name = total·a·b,
    sum_n_check_by_names = addends·target, ratio_check_by_name = numerator·denominator·expected."""

    total: JsonValue
    a: JsonValue
    b: JsonValue
    addends: JsonValue
    target: JsonValue
    numerator: JsonValue
    denominator: JsonValue
    expected: JsonValue


@with_config(FORBID)
class RawItems(TypedDict, total=False):
    """단건 도구(sum_check·sum_n_check·ratio_check)가 받은 인자(모델이 준 JSON 값 그대로). 도구마다 쓰는 열쇠만 있다:
    sum_check = a·b·c, sum_n_check = addends·target, ratio_check = d·e·f."""

    a: JsonValue
    b: JsonValue
    c: JsonValue
    d: JsonValue
    e: JsonValue
    f: JsonValue
    addends: JsonValue
    target: JsonValue


@with_config(FORBID)
class CheckItems(TypedDict):
    """검사에 쓴 항목. 어느 쪽인지는 tool 로 가른다 — 이름형 도구는 byName, 단건 도구는 raw 이고 다른 쪽은 null."""

    byName: ByNameItems | None
    raw: RawItems | None


@with_config(FORBID)
class YearResult(TypedDict):
    """검사 한 해(단건 도구는 원소 하나, year 는 null)."""

    year: JsonValue
    """연도(모델이 준 인자 그대로). 단건 도구는 null."""
    ok: bool
    status: Literal["OK", "FAIL"]
    diff: str | None
    """차이(repr(float) 글자. 합계·부분합은 (더한 값) − 대상, 비율은 퍼센트 포인트). 계산하지 못했으면 null."""
    note: Literal["non-numeric", "division by zero"] | None
    """계산하지 못한 까닭(코랩의 note). 계산했으면 null."""
    explanation: str
    """도구가 쓴 설명 한 줄(영어, 코랩 그대로)."""


@with_config(FORBID)
class RuleCheck(TypedDict):
    """합계·부분합·비율 검사 한 번."""

    seq: Seq
    """검토 단계의 도구 호출 차례(1부터)."""
    tool: str
    """부른 도구의 이름(sum_check 와 sum_check_by_name 을 가른다)."""
    kind: Literal["check"]
    rule: Literal["sum", "sum_n", "ratio"]
    """sum = a + b ≈ 합계, sum_n = 더하는 항목들의 합 ≈ 대상, ratio = 분자 / 분모 × 100 ≈ 기대값(%)."""
    items: CheckItems
    tolerance: str | None
    """도구가 비교에 쓴 허용 오차(repr(float) 글자 — bool 은 도구처럼 1·0 으로). 수가 아니면 null 인데, 그때는 도구가
    허용 오차를 쓰지 않은 것이다(계산하지 못한 해뿐이거나 years 가 빔 — 썼다면 도구가 bad arguments 를 냈다)."""
    years: list[YearResult]
    """해마다의 판정(모델이 준 years 의 차례)."""


@with_config(FORBID)
class SearchFilter(TypedDict, total=False):
    """검색 거름(모델이 준 것만, 준 그대로 있다)."""

    대분류: JsonValue
    중분류: JsonValue
    소분류_contains: JsonValue


@with_config(FORBID)
class SearchCheck(TypedDict):
    """항목 검색(search_items) 한 번."""

    seq: Seq
    """검토 단계의 도구 호출 차례(1부터)."""
    tool: str
    kind: Literal["search"]
    filter: SearchFilter
    total: Count
    """거름에 맞은 항목 수(쪽 나눔 전)."""
    limit: JsonValue
    """쪽 크기(모델이 준 그대로, 주지 않았으면 분배기 기본 200)."""
    offset: JsonValue
    """건너뛴 수(모델이 준 그대로, 주지 않았으면 0)."""
    returned: Count
    """이번에 돌려준 항목 수."""


@with_config(FORBID)
class ErrorCheck(TypedDict):
    """도구가 오류를 돌려준 호출(모르는 도구·인자 틀림·도구 안의 예외). 또는 도구 출력이 이 꼴에 맞지 않은 호출 —
    엔진의 결함일 때만이고 메시지가 「shape mismatch: 」로 시작한다."""

    seq: Seq
    """검토 단계의 도구 호출 차례(1부터)."""
    tool: str
    kind: Literal["error"]
    message: str
    """오류 글(도구의 error 글 그대로, 꼴이 맞지 않으면 그 까닭)."""
    args: JsonValue
    """모델이 준 인자 그대로(보통 객체, 객체가 아니어도 그대로)."""


Check = Annotated[ValueCheck | RuleCheck | SearchCheck | ErrorCheck, Field(discriminator="kind")]
"""검사 기록 하나. kind 로 가른다."""


@with_config(FORBID)
class DataverifyReviewDone(TypedDict):
    """계산 검토(코랩2번)를 마쳤다."""

    status: Literal["done"]
    partial: bool
    """true = 최대 횟수에 닿아 남은 도구 호출을 버리고 마지막 답을 썼다, false = 고리가 끝까지 돌았다."""
    report: str
    """검토 리포트 원문(모델의 글)."""
    checks: list[Check]
    """도구 호출 기록(호출 차례)."""
    failure: None


@with_config(FORBID)
class ReviewFailed(TypedDict):
    """계산 검토가 실패했다. checks 는 실패 전까지의 호출이다."""

    status: Literal["failed"]
    partial: None
    report: None
    checks: list[Check]
    failure: Failure


@with_config(FORBID)
class ReviewNotRun(TypedDict):
    """계산 검토를 돌리지 않았다."""

    status: Literal["not_run"]
    partial: None
    report: None
    checks: Annotated[list[Check], Field(max_length=0)]
    failure: None


Review = Annotated[DataverifyReviewDone | ReviewFailed | ReviewNotRun, Field(discriminator="status")]


@with_config(FORBID)
class InsightRow(TypedDict):
    """인사이트 표의 한 줄(코랩 셀 18 출력 형식의 다섯 열)."""

    area: str
    """영역(환경/사회/지배구조)."""
    indicator: str
    """지표(소분류)."""
    observation: str
    """관찰 내용 및 스토리."""
    risk: str
    """잠재 리스크(데이터 품질·정보·해석)."""
    interpretation: str
    """해석·가설."""


@with_config(FORBID)
class WebSource(TypedDict):
    """웹 검색 출처."""

    title: str | None
    url: str


RowsParsed = Literal["parsed", "unparsed", "none"]
"""parsed = 리포트의 표를 rows 로 읽음, unparsed = 표를 읽지 못함(원문은 report), none = 리포트가 없음."""


@with_config(FORBID)
class InsightDone(TypedDict):
    """인사이트(코랩3번)를 마쳤다."""

    status: Literal["done"]
    partial: bool
    """true = 최대 횟수에 닿아 남은 도구 호출을 버리고 마지막 답을 썼다, false = 고리가 끝까지 돌았다."""
    report: str
    """인사이트 리포트 원문(모델의 글)."""
    rows: list[InsightRow]
    rowsParsed: RowsParsed
    sources: list[WebSource]
    failure: None


@with_config(FORBID)
class InsightFailed(TypedDict):
    """인사이트가 실패했다."""

    status: Literal["failed"]
    partial: None
    report: None
    rows: Annotated[list[InsightRow], Field(max_length=0)]
    rowsParsed: Literal["none"]
    sources: Annotated[list[WebSource], Field(max_length=0)]
    failure: Failure
    partialText: str | None
    """잘린 답의 부분 원문(모델의 글 — failure.kind 가 truncated 일 때만, 그 밖은 null). failure.message·warnings 에는
    싣지 않는다."""


@with_config(FORBID)
class InsightNotRun(TypedDict):
    """인사이트를 돌리지 않았다."""

    status: Literal["not_run"]
    partial: None
    report: None
    rows: Annotated[list[InsightRow], Field(max_length=0)]
    rowsParsed: Literal["none"]
    sources: Annotated[list[WebSource], Field(max_length=0)]
    failure: None


Insight = Annotated[InsightDone | InsightFailed | InsightNotRun, Field(discriminator="status")]


@with_config(FORBID)
class DataverifyWarning(TypedDict):
    """경고 한 줄."""

    code: str
    """경고의 종류(예: no_target_theme = 입력에 테마 「환경」이 없다)."""
    message: str


@with_config(FORBID)
class DataverifyResult(TypedDict):
    """dataverify.result@2 — 데이터 검증 한 건의 결과. schemaVersion 이 첫 키다. 사용량·비용은 싣지 않는다(실행기의
    기록이 진실이다)."""

    schemaVersion: Literal["dataverify.result@2"]
    company: Company
    """입력의 company 그대로."""
    scope: Scope
    settings: DataverifySettings
    plan: Plan
    review: Review
    insight: Insight
    warnings: list[DataverifyWarning]


INPUT_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    INPUT_SHAPE: TypeAdapter[DataverifyInput](
        Annotated[DataverifyInput, Field(title=INPUT_SHAPE, description="데이터 검증 한 건의 입력.")]
    )
}
"""입력 꼴 id → 검사기. validate_python(입력, strict=True) 로 꼴만 보고, 흐름은 받은 dict 를 그대로 쓴다."""


def check_input(received: Mapping[str, Any]) -> Mapping[str, Any]:
    """입력 꼴만 본다(strict). 지나면 받은 dict 를 그대로(같은 객체) 돌려준다 — 검사 결과(복사본)를 쓰지 않는다(발주서
    §1-9: 프롬프트가 받은 dict 를 글자째 싣는다). 꼴이 아니면 pydantic ValidationError."""
    INPUT_SHAPES[INPUT_SHAPE].validate_python(received, strict=True)
    return received


RESULT_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    RESULT_SHAPE: TypeAdapter[DataverifyResult](
        Annotated[DataverifyResult, Field(title=RESULT_SHAPE, description="데이터 검증 한 건의 결과.")]
    )
}
"""결과 꼴 id → 검사기. validate_python(결과, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""

CHECK: Final = TypeAdapter[ValueCheck | RuleCheck | SearchCheck | ErrorCheck](Check)
"""검사 기록 하나의 검사기(contracts/wire.to_check 가 쓴다)."""
