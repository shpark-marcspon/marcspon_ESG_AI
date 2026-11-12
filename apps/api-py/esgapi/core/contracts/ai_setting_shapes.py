"""모듈 공통 AI 설정 꼴 둘 — 단계마다의 프롬프트·모델 설정(밴드 AS1, 이슈 MARC-ISSUE-240, 결정 MARC-ENT-350·353·352).
밴드 AS3a-1(이슈 MARC-ISSUE-257, 결정 MARC-ENT-381·384·385)이 셋째 꼴(프롬프트 글 입력)을 더했다.
도메인을 모른다: 단계·허용 경로·기본값은 도메인이 넘기고(calc/ai_settings.py 의 AiStepSpec), 판 머리(번호·상태)는
도메인 꼴에 둔다.

    ai.prompt-model@2     AiPromptModel       응답. 도메인이 /ai-settings/<모듈>/{id}/prompt-model·
                                              /ai-settings/<모듈>/default/prompt-model 로 낸다(경로는 도메인마다).
                                              @1 + 칸마다 memo·defaultText·isDefault·outputSection·outputKept,
                                              판 밖 limits·fixed(AS3a-1)
    ai.model-settings@1   AiModelSettingsIn   입력. 새 판 저장 본문의 modelSettings 칸이고, 저장하는 꼴도 이것이다
                                              (calc/ai_settings.to_input 이 낸 정규형)
    ai.prompts@1          AiPromptsIn         입력. 새 판 저장 본문의 prompts 칸(본문에 싣는 것은 AS3a-2). 단계·칸
                                              전부 필수, 차례 = 모듈 명세(layout). 저장하는 꼴도 이것이다
                                              (calc/ai_settings.prompts_input 이 낸 정규형)

TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 core/tests/data/ai-setting/, 예시는
core/tests/data/ai-setting-examples/. 클래스 이름이 openapi 의 구성요소 이름이 되므로 `Ai` 로 시작한다.

**이 파일에 로직은 없다.** 규칙(calc/ai_settings.py 와 도메인):
- **모델 설정만 바꿔도 새 판이다.** 판 행은 불변이고 기존 판에 모델 설정을 붙이지 않는다. 적용은 판 단위다.
- 저장 판의 모델 설정은 늘 실제 값이다(저장 때 채움). `null`(코드 값)은 기본 판뿐이다 — 응답에서는 기본 판도 풀린
  값으로 보인다. 단계 안의 `temperature: null` 은 「싣지 않음」이라는 값이다(받지 않는 경로의 유일한 값).
- `editable.model`·`editable.prompts` = 이 모듈이 새 판에 모델 설정·프롬프트 글을 넣을 수 있다(모듈 능력, 판의
  상태 아님).
- **한 번 저장 = 판 하나**: 본문 하나에 기준표·모델·프롬프트가 같이 온다(판별 대상 단어(G2d MARC-ISSUE-246)가 오면 같은
  본문에 칸 하나 더함). **글·메모만 바꿔도 새 판이다.**
- 저장 글 없는 판 = 모듈 코드 글. **prompts 의 null 은 뜻이 있다**(코드 글을 쓴다) — 모델 설정의 「저장 판 null 없음」과
  다르다.
- 되돌림 = 웹이 `defaultText` 를 보낸다. 서버는 접지 않는다(기본 글과 같은 글도 그대로 저장, `isDefault` 로 보일 뿐).
- `outputSection` 은 기본 글의 출력 형식 절이다. `outputKept` false 는 화면 경고이고 저장을 막지 않는다.
- `fixed` = 판과 무관한 읽기 전용 코드 값(편집 0). `limits` = 받기 상한(이 파일의 상수 셋 — calc 가 import).
- 고르는 단위는 경로(이름 붙은 묶음 하나)다. `routeChoices` 는 그 단계에 고를 수 있는 경로(도메인 명세 차례)이고
  `acceptsTemperature`·`webSearchAvailable` 이 false 면 화면은 그 칸을 「–」로 둔다.
- `modelSettingsSha256` 은 실행 versions 에 실릴 값과 같은 셈이다(calc/ai_settings.model_settings_sha256 — 경로
  이름과 풀린 api_model_id 를 차례째 품는다. 배포로 경로→모델 짝이 바뀌면 같은 저장 값도 sha 가 달라진다).
- 고르기 목록과 받기에 넘기는 설정은 `default_config_sources(synthetic=False)` 로 지은 것만 쓴다(모의 경로가 목록에
  나오지 않게). core 의 함수는 설정을 받기만 한다.
- 오류: 꼴 틀림(모르는 키·타입·빠진 칸·bool 을 수로)은 부르는 쪽의 422 VALIDATION_ERROR(fields). 의미 거절은 400 이고
  code 는 calc/ai_settings.py 의 받기 차례 여섯이다. `maxOutputTokens < 1` 거절은 호출 층(위끝만 봄)보다 엄격하다.
  프롬프트 글 받기(AS3a-1)의 code 는 ai_prompt_* 여덟이고 field 경로는 422 의 fields 와 같은 규칙
  (`prompts.steps.<i>.prompts.<j>.text|memo`).
이 파일은 등록 길(apps.py 의 ready)에서 들이지 않는다.

**부품 넷과 ai.prompt-model@3**(밴드 AP1a, 결정 MARC-ENT-399, 이슈 MARC-ISSUE-280). 모듈은 부품을 조합한다(모듈 선언
calc/ai_settings.AiModuleSpec → compose). 경로는 아직 걸지 않았다(AP1b 부터).

    부품          응답 꼴                셈(calc/ai_settings.py)
    모델 칸       AiModelSlot           AiModelSlotSpec · check_model_settings · route_choices · model_settings_sha256
    프롬프트 묶음  AiPromptGroup         AiPromptGroupSpec · layout_of · check_prompts · prompt_entry · prompts_sha256
    판            (꼴 없음 — 모듈마다)  next_version_name · version_status · ai_versions(AiVersionsCommon) · VERSION_*
    고정 값       AiFixedGroup          (셈 없음 — 모듈이 넘긴다)

    ai.prompt-model@3     AiPromptModel3      응답. @2 의 steps 대신 models(모델 칸)·promptGroups(프롬프트 묶음) 둘.
                                              칸 안의 값 꼴(AiModelSetting·AiRouteChoice·AiPromptEntry·AiFixedGroup·
                                              AiPromptLimits·AiPromptModelEditable)은 @2 와 같은 클래스다

- **입력 @1 의 steps = 칸 목록**: ai.model-settings@1 의 `steps[i]` 는 모델 칸 i, ai.prompts@1 의 `steps[i]` 는 프롬프트
  묶음 i 다. 입력 꼴·거절 code·fields 경로는 그대로다(이름만 「단계」로 남았다).
- **sha 앞바이트 불변**: model_settings_sha256·prompts_sha256 의 직렬화 바이트(열쇠 `steps` 포함)는 바꾸지 않는다 —
  바꾸면 저장 판·실행이 전부 versions_mismatch(MARC-ENT-352). 그래서 옛 판 행은 그대로 읽힌다(마이그레이션 0).
- 칸의 `routeChoices` 는 지금 쓸 수 있는 경로만이고 쓸 수 없는 것은 `unavailableRoutes`(명세 차례)에 이름만 둔다.
  **routeChoices ≥1 은 compose 가 보장한다**(칸의 고른 경로는 늘 쓸 수 있어야 하고, 아니면 LlmConfigError).
- `modelSlots` 는 묶음의 글을 받는 모델 칸 key(화면 안내 — 실행 규칙 아님, 빈 목록 허용).
- 옛 @2(AiPromptModel·AiPromptStep·고정 파일·예시)는 AP1b·AP1c 가 걷는다.
- 판 이름·제목·메모 상한(VERSION_*)은 모듈 판 꼴이 쓴다. 판 목록·하나의 꼴은 모듈마다다(MARC-ENT-350).
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, NotRequired, TypedDict

from pydantic import ConfigDict, Field, TypeAdapter, with_config

from esgapi.core.llm.client import TEMPERATURE_MAX, TEMPERATURE_MIN

PROMPT_MODEL_SHAPE: Final = "ai.prompt-model@2"
PROMPT_MODEL_V3_SHAPE: Final = "ai.prompt-model@3"
MODEL_SETTINGS_SHAPE: Final = "ai.model-settings@1"
PROMPTS_SHAPE: Final = "ai.prompts@1"

PROMPT_TEXT_MAX_CHARS: Final = 8000
"""프롬프트 글 하나의 글자 수 상한(받기 규칙 5)."""
PROMPT_MEMO_MAX_CHARS: Final = 500
"""칸 메모 하나의 글자 수 상한(앞뒤 공백을 뺀 값, 받기 규칙 7)."""
PROMPTS_MAX_OCTETS: Final = 131072
"""저장 꼴(calc/ai_settings.prompts_input) 직렬화의 UTF-8 바이트 상한(받기 규칙 8 — 도메인 DB 크기 CHECK 와 같은 값)."""

VERSION_NAME_PATTERN: Final = r"^v[1-9][0-9]{0,14}$"
"""판 이름의 꼴 — 서버가 회사 안에서 v1, v2, … 로 매긴다(calc/ai_settings.next_version_name)."""
VERSION_NAME_MAX_CHARS: Final = 16
"""판 이름 글자 수 상한."""
VERSION_TITLE_MAX_CHARS: Final = 40
"""판 제목 글자 수 상한(MARC-ENT-387 — 1~40자)."""
VERSION_MEMO_MAX_CHARS: Final = 200
"""판 메모 글자 수 상한(0~200자)."""

FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True)
STRICT_FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True, strict=True)

Sha256 = Annotated[str, Field(pattern="^[0-9a-f]{64}$")]
Temperature = Annotated[float, Field(ge=TEMPERATURE_MIN, le=TEMPERATURE_MAX)]
OutputTokens = Annotated[int, Field(ge=1)]


@with_config(FORBID)
class AiModelRef(TypedDict):
    """경로가 푼 모델 하나."""

    key: str
    """설정 파일의 모델 이름."""
    label: str
    """보이는 이름."""
    provider: str
    """공급사."""


@with_config(FORBID)
class AiModelSetting(TypedDict):
    """한 단계의 모델 설정(풀린 값)."""

    route: str
    """경로 이름."""
    models: Annotated[list[AiModelRef], Field(min_length=1)]
    """경로의 모델(첫째가 주, 나머지가 대체 차례)."""
    temperature: Temperature | None
    """null = 싣지 않음."""
    webSearch: bool
    maxOutputTokens: OutputTokens
    """답의 출력 상한(토큰)."""


@with_config(FORBID)
class AiRouteChoice(TypedDict):
    """그 단계에 고를 수 있는 경로 하나와 그 능력."""

    route: str
    models: Annotated[list[AiModelRef], Field(min_length=1)]
    acceptsTemperature: bool
    """경로 모델 전부가 temperature 를 받는다."""
    webSearchAvailable: bool
    """그 단계가 도구 고리를 지나고 경로가 web_search 를 실을 수 있다."""
    maxOutputTokensMax: OutputTokens
    """경로 모델 출력 상한의 최솟값."""


@with_config(FORBID)
class AiPromptEntry(TypedDict):
    """프롬프트 칸 하나: 판의 글·메모와 그 칸의 엔진 기본 글."""

    key: str
    label: str
    """칸 이름(서버 글 — 웹은 글 표를 따로 두지 않는다)."""
    promptId: str
    promptVersion: str
    sha256: Sha256
    """text 의 UTF-8 sha256."""
    text: str
    """전문."""
    memo: str
    """판의 칸 메모(저장 글 없는 판은 모듈 기본 메모)."""
    defaultText: str
    """그 칸의 엔진 기본 글(기준표로 지은 글이 아니다). 웹은 이 글을 보내 되돌린다."""
    isDefault: bool
    """text == defaultText(바이트)."""
    outputSection: str | None
    """defaultText 의 출력 형식 절. 없으면 null."""
    outputKept: bool
    """text 안에 outputSection 이 바이트 그대로 있다(null 이면 true). false 는 화면 경고, 저장은 안 막는다."""


@with_config(FORBID)
class AiPromptStep(TypedDict):
    """단계 하나: 모델 설정 · 고를 수 있는 경로 · 프롬프트."""

    key: str
    label: str
    model: AiModelSetting
    routeChoices: Annotated[list[AiRouteChoice], Field(min_length=1)]
    prompts: Annotated[list[AiPromptEntry], Field(min_length=1)]


@with_config(FORBID)
class AiPromptModelEditable(TypedDict):
    """이 모듈이 새 판에 넣을 수 있는 것(모듈 능력)."""

    prompts: bool
    model: bool


@with_config(FORBID)
class AiPromptLimits(TypedDict):
    """프롬프트 받기 상한(contracts/ai_setting_shapes.py 의 상수 — calc 가 import)."""

    textMax: int
    """글 하나의 글자 수 상한."""
    memoMax: int
    """메모 하나의 글자 수 상한(앞뒤 공백을 뺀 값)."""


@with_config(FORBID)
class AiFixedItem(TypedDict):
    """읽기 전용 코드 값 하나."""

    key: str
    label: str
    value: int | str | list[str] | None
    """값. null = 이름만(값 없는 항목)."""


@with_config(FORBID)
class AiFixedGroup(TypedDict):
    """읽기 전용 코드 값 묶음 하나(판과 무관, 편집 0)."""

    key: str
    label: str
    items: list[AiFixedItem]


@with_config(FORBID)
class AiPromptModel(TypedDict):
    """ai.prompt-model@2 — 한 판의 단계마다 프롬프트·모델 설정, 받기 상한, 읽기 전용 코드 값. schemaVersion 이 첫
    키다."""

    schemaVersion: Literal["ai.prompt-model@2"]
    module: str
    settingName: str
    """판 이름."""
    editable: AiPromptModelEditable
    modelSettingsSha256: Sha256
    """실행 versions 에 실릴 값과 같은 셈."""
    steps: Annotated[list[AiPromptStep], Field(min_length=1)]
    """단계(차례 고정)."""
    limits: AiPromptLimits
    fixed: list[AiFixedGroup]
    """판과 무관한 읽기 전용 코드 값. 없으면 []."""


@with_config(FORBID)
class AiModelSlot(TypedDict):
    """모델 칸 하나: 모델 설정 · 지금 고를 수 있는 경로 · 지금 쓸 수 없는 경로."""

    key: str
    label: str
    model: AiModelSetting
    routeChoices: Annotated[list[AiRouteChoice], Field(min_length=1)]
    """지금 쓸 수 있는 경로만(명세 차례)."""
    unavailableRoutes: list[str]
    """명세가 허용했지만 지금 설정으로는 쓸 수 없는 경로 이름(명세 차례). 없으면 []."""


@with_config(FORBID)
class AiPromptGroup(TypedDict):
    """프롬프트 묶음 하나: 그 묶음의 칸과 그 글을 받는 모델 칸."""

    key: str
    label: str
    modelSlots: list[str]
    """이 묶음의 글을 받는 모델 칸 key(화면 안내 — 실행 규칙 아님). 없으면 []."""
    prompts: Annotated[list[AiPromptEntry], Field(min_length=1)]


@with_config(FORBID)
class AiPromptModel3(TypedDict):
    """ai.prompt-model@3 — 한 판의 모델 칸·프롬프트 묶음, 받기 상한, 읽기 전용 코드 값. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["ai.prompt-model@3"]
    module: str
    settingName: str
    """판 이름."""
    editable: AiPromptModelEditable
    modelSettingsSha256: Sha256
    """실행 versions 에 실릴 값과 같은 셈."""
    models: Annotated[list[AiModelSlot], Field(min_length=1)]
    """모델 칸(차례 고정 = 입력 ai.model-settings@1 의 steps 차례)."""
    promptGroups: Annotated[list[AiPromptGroup], Field(min_length=1)]
    """프롬프트 묶음(차례 고정 = 입력 ai.prompts@1 의 steps 차례)."""
    limits: AiPromptLimits
    fixed: list[AiFixedGroup]
    """판과 무관한 읽기 전용 코드 값. 없으면 []."""


AiVersionStatus = Literal["applied", "past", "testing"]
"""판의 상태: 지금 적용 · 적용했던 판 · 한 번도 적용 안 함(calc/ai_settings.version_status)."""


@with_config(FORBID)
class AiVersionsCommon(TypedDict):
    """실행 versions 의 공통 열쇠(calc/ai_settings.ai_versions — 경로에 싣지 않는다). 모듈 열쇠는 모듈이 더한다."""

    aiSettingId: int | None
    """판 id. 기본 판 None."""
    modelSettingsSha256: str
    promptsSha256: NotRequired[str]
    """저장 글 판만."""


@with_config(STRICT_FORBID)
class AiModelStepIn(TypedDict):
    """한 단계의 모델 설정 입력. 다섯 칸 다 필수. 범위·능력은 받기(calc/ai_settings.check_model_settings)가 본다."""

    key: str
    route: str
    temperature: float | None
    """null = 싣지 않음."""
    webSearch: bool
    maxOutputTokens: int


@with_config(STRICT_FORBID)
class AiModelSettingsIn(TypedDict):
    """ai.model-settings@1 — 단계마다의 모델 설정 입력(명세 차례). 꼴 id 는 본문에 싣지 않는다."""

    steps: list[AiModelStepIn]


@with_config(STRICT_FORBID)
class AiPromptIn(TypedDict):
    """프롬프트 칸 하나의 입력. 세 칸 다 필수. 글·메모 규칙은 받기(calc/ai_settings.check_prompts)가 본다."""

    key: str
    text: str
    """전문(바이트 그대로 받는다)."""
    memo: str
    """칸 메모(앞뒤 공백을 뺀 값이 정규형)."""


@with_config(STRICT_FORBID)
class AiPromptStepIn(TypedDict):
    """한 단계의 프롬프트 칸 입력(모듈 명세 차례, 칸 전부)."""

    key: str
    prompts: list[AiPromptIn]


@with_config(STRICT_FORBID)
class AiPromptsIn(TypedDict):
    """ai.prompts@1 — 단계마다의 프롬프트 글 입력(명세 차례, 단계 전부). 꼴 id 는 본문에 싣지 않는다."""

    steps: list[AiPromptStepIn]


PROMPT_MODEL: Final = TypeAdapter(AiPromptModel)
PROMPT_MODEL_V3: Final = TypeAdapter(AiPromptModel3)
MODEL_SETTINGS: Final = TypeAdapter(AiModelSettingsIn)
PROMPTS: Final = TypeAdapter(AiPromptsIn)
SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    PROMPT_MODEL_SHAPE: PROMPT_MODEL,
    PROMPT_MODEL_V3_SHAPE: PROMPT_MODEL_V3,
    MODEL_SETTINGS_SHAPE: MODEL_SETTINGS,
    PROMPTS_SHAPE: PROMPTS,
}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
