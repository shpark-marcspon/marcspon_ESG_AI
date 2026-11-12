"""판정 기준표 꼴 greenwash.criteria@1 의 정의 — 그린워싱 판정(EVAL) 프롬프트에서 사람이 고칠 수 있는 15줄.
**초안 판 — 프론트 AD-02 가 한 번 지은 뒤 굳힘.**

초안 판의 뜻: 프론트가 AI 설정 화면(AD-02)을 이 꼴로 한 번 지은 뒤 굳힌다. 굳히기 전에는 `@1` 안에서 감독 승인으로
칸을 고칠 수 있다. 굳힌 뒤에 꼴을 바꾸면 새 판(@2)이다.

TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/criteria/greenwash.criteria@1.schema.json,
예시는 tests/data/contract-examples/criteria/. 클래스 이름이 openapi 의 구성요소 이름이 되므로 `Greenwash` 로 시작한다.

**이 파일에 로직은 없다.** 틀(고정 글)·기본 판·조립·받기는 E0 판에 묶여 flows/criteria_e0.py 에 있다. 규칙:
- 줄은 15줄 고정이다(MARC-ENT-312). 줄 id·차례·구분(category)·판정 결과(verdict)는 고칠 수 없다. 줄 추가·삭제는 2차.
  id 를 바꾸면 계약 판 올림이다. 차례·개수·category/verdict 짝은 꼴로 막기 어려워 받기(criteria_e0.accept_criteria)가
  막는다.
- 사용(enabled)을 끈 줄은 프롬프트에서 줄째 빠진다. 한 구분의 줄을 모두 꺼도 받는다 — 그 등급 칸은 비운다(절 머리는
  남고 줄만 빠진다. MARC-ENT-329).
- `terms` 는 대상 키워드(targetKeyword) 줄에서만 값(낱말 목록)이고 그 밖은 null 이다. 키워드 줄의 `text` 는 묶음
  이름이고 고칠 수 없다(틀의 글이 두 묶음 이름을 부른다). 키워드 낱말은 프롬프트에만 들어간다 — 문장 거르기(engines
  heuristics 의 환경 낱말)·낱말 빈도(GREEN_TERMS)와는 별개다.
- 근거 가이드라인(`guideline`)은 화면 기록용이고 프롬프트에 들어가지 않는다(MARC-ENT-329).
- 「바뀐 것」(판 사이의 차이)은 웹이 줄 `id` 로 센다. 이 꼴은 차이를 싣지 않는다.
- `version` 은 이 기준표가 든 AI 설정 판의 이름이다(MARC-ENT-244 — 판의 축은 AI 설정 묶음 하나). 기본 판은
  `colab-2026-01-15-v1`. 어느 판으로 판정했는지는 실행 판 묶음의 `aiSetting` 으로 잇는다(결과 꼴 result@1 은 그대로).
- 틀 안의 고정 규칙(Low 금지, 근거 비면 NonRisk 금지, 출력 JSON 꼴, 각 절 머리)은 이 꼴 밖이다.

이 파일은 등록 길(apps.py 의 ready)에서 들이지 않는다.

**받기 수의 표기(밴드 G2c2 Q7)**: 글·낱말·가이드라인·판 이름의 길이, 낱말 수, 줄 수, 한 줄(줄바꿈 없음)을 JSON 스키마에
`minLength`·`maxLength`·`minItems`·`maxItems`·`pattern` 으로 **표기만** 한다(WithJsonSchema — 검증에 쓰지 않는다). 받기
(criteria_e0.accept_criteria)의 검증 길·거절 code·문장은 그대로다 — 꼴 검사에 걸면 꼴 거절(CRITERIA_SHAPE)이 먼저 서서
code 가 바뀐다. 수는 criteria_e0 의 받기 상수(TEXT_CHARS·TERMS_MAX·TERM_CHARS·GUIDELINE_CHARS·VERSION_CHARS·ROW_COUNT)와
같아야 한다(tests/contracts/test_ai_setting_shapes.py 가 견준다 — import 하지 않는 까닭: criteria_e0 가 이 파일을
들인다).
표기는 앞뒤 공백을 지운 뒤의 수다(받기가 지운 뒤 잰다).
"""

from collections.abc import Mapping
from typing import Annotated, Final, Literal, TypedDict

from pydantic import ConfigDict, Field, TypeAdapter, WithJsonSchema, with_config

SHAPE: Final = "greenwash.criteria@1"

# 이 꼴은 G2c-2 의 저장 본문으로도 들어온다. 중첩 TypedDict 에 strict 를 따로 둔다(review_shapes 의 STRICT_FORBID 와
# 같은 까닭). JSON 스키마는 바뀌지 않는다(strict 는 스키마에 나오지 않는다).
STRICT_FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True, strict=True)

ONE_LINE: Final = "^[^\r\n]*$"
"""한 줄 표기(줄바꿈 없음). 받기는 보이지 않는 글자까지 막는다(criteria_e0.INVISIBLE) — 표기는 줄바꿈만."""

CriterionText = Annotated[
    str, WithJsonSchema({"type": "string", "minLength": 1, "maxLength": 300, "pattern": ONE_LINE})
]
"""기준 글(표기: 1~300자, 한 줄)."""
CriterionTerm = Annotated[str, WithJsonSchema({"type": "string", "minLength": 1, "maxLength": 30, "pattern": ONE_LINE})]
"""대상 키워드 낱말 하나(표기: 1~30자, 한 줄)."""
CriterionTerms = Annotated[list[CriterionTerm], Field(json_schema_extra={"minItems": 1, "maxItems": 30})]
"""대상 키워드 낱말 목록(표기: 1~30개)."""
GuidelineText = Annotated[
    str, WithJsonSchema({"type": "string", "minLength": 1, "maxLength": 200, "pattern": ONE_LINE})
]
"""근거 가이드라인 글(표기: 1~200자, 한 줄)."""
CriteriaVersion = Annotated[
    str,
    WithJsonSchema({"type": "string", "minLength": 1, "maxLength": 64, "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$"}),
]
"""판 이름(표기: 1~64자, 영문·숫자로 시작하고 영문·숫자·`.`·`_`·`-`)."""

GreenwashCriterionId = Literal[
    "keyword-ghg",
    "keyword-exclusion",
    "evidence-quantity",
    "evidence-baseline",
    "evidence-boundary",
    "evidence-offset",
    "high-1",
    "high-2",
    "high-3",
    "high-4",
    "mid-1",
    "exception-1",
    "exception-2",
    "exception-3",
    "exception-4",
]
"""줄 id(계약 — 바꾸면 판 올림). 이 차례가 줄의 차례다(order 1..15)."""

GreenwashCriterionCategory = Literal["targetKeyword", "coreEvidence", "high", "mid", "exception"]
"""구분: 대상 키워드 · 핵심 근거 · High · Mid · 예외 조항."""

GreenwashCriterionVerdict = Literal["coreEvidenceApplies", "highIfMissing", "High", "Mid", "NonRisk"]
"""판정 결과. 구분으로 정해진다(targetKeyword → coreEvidenceApplies, coreEvidence → highIfMissing, high → High,
mid → Mid, exception → NonRisk)."""


@with_config(STRICT_FORBID)
class GreenwashCriterionGuideline(TypedDict):
    """근거 가이드라인(기관·조항). 화면 기록용 — 프롬프트에 들어가지 않는다."""

    text: GuidelineText
    """가이드라인 글(1~200자, 한 줄)."""
    status: Literal["draft", "confirmed"]
    """초안 · 확인됨."""


@with_config(STRICT_FORBID)
class GreenwashCriterionRow(TypedDict):
    """기준표의 한 줄."""

    id: GreenwashCriterionId
    """줄 id(고칠 수 없음)."""
    category: GreenwashCriterionCategory
    """구분(고칠 수 없음)."""
    order: int
    """1..15, id 차례와 같다(웹 정렬용, 고칠 수 없음)."""
    enabled: bool
    """사용. 끈 줄은 프롬프트에서 줄째 빠진다."""
    text: CriterionText
    """기준 글(1~300자, 한 줄). targetKeyword 는 묶음 이름(고칠 수 없음)."""
    terms: CriterionTerms | None
    """targetKeyword 만 낱말 목록(1~30개, 낱말마다 1~30자·쉼표 없음·한 줄·같은 묶음 안 중복 없음), 그 밖은 null."""
    verdict: GreenwashCriterionVerdict
    """판정 결과. category 로 정해짐(고칠 수 없음)."""
    guideline: GreenwashCriterionGuideline | None
    """근거 가이드라인. 없으면 null. 프롬프트 밖."""


@with_config(STRICT_FORBID)
class GreenwashCriteria(TypedDict):
    """greenwash.criteria@1 — 판정 기준표 한 벌. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.criteria@1"]
    version: CriteriaVersion
    """이 기준표가 든 AI 설정 판의 이름(1~64자, 영문·숫자로 시작하고 영문·숫자·`.`·`_`·`-`). 기본 판
    `colab-2026-01-15-v1`."""
    rows: Annotated[list[GreenwashCriterionRow], Field(json_schema_extra={"minItems": 15, "maxItems": 15})]
    """늘 15줄, GreenwashCriterionId 의 차례 그대로."""


CRITERIA_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashCriteria]]] = {SHAPE: TypeAdapter(GreenwashCriteria)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
