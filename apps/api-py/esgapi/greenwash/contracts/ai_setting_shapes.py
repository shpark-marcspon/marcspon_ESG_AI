"""AI 설정 판 꼴 셋 — 회사별 그린워싱 판정 기준표의 판(밴드 G2c2, 결정 MARC-ENT-341·244·312). 경로는
`/ai-settings/greenwash`(service/apis/ai_settings.py — 운영 관리자만).

    greenwash.ai-settings@2          GreenwashAiSettingList     GET /ai-settings/greenwash · PUT …/applied 의 응답
    greenwash.ai-setting@3           GreenwashAiSetting         GET /ai-settings/greenwash/{id} · POST 의 응답
    greenwash.ai-setting-default@3   GreenwashAiSettingDefault  GET /ai-settings/greenwash/default 의 응답
@2 = @1 + 판 이름 title(밴드 AS3a-2, 결정 MARC-ENT-387): 저장 판은 받은 이름(옛 판 null — 0005 가 채우지 않는다. 화면은
「v<n>」만), 기본 판과 목록 default 는 서버 글 DEFAULT_TITLE.
판 하나·기본 판 @3 = @2 + 대상 단어 terms(밴드 G2d, 결정 MARC-ENT-394): 저장 판은 받은 {text, enabled} 목록(받은 차례)
이거나 null(코드 기본 목록 — 옛 판·terms 없는 저장), 기본 판은 늘 null(글자는 GET /greenwash/terms/default). 목록
ai-settings@2 는 그대로.

TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/ai-setting/, 예시는
tests/data/contract-examples/ai-setting/. 클래스 이름이 openapi 의 구성요소 이름이 되므로 `GreenwashAiSetting` 으로
시작한다.

**이 파일에 로직은 없다.** 규칙(service/services·actions/ai_settings.py):
- 판은 회사별 불변 행이다. 저장 = 새 판, 고쳐 쓰기·지우기 없음. 판 이름은 서버가 회사 안에서 `v1`, `v2`, … 로 매기고
  받은 `criteria.version` 은 그 이름으로 덮는다(Q5).
- 기본 판(코랩 원본 기준표, 이름 `colab-2026-01-15-v1`)은 코드에 고정이고 목록의 items 에 없다. 적용 판이 없으면 곧
  기본 판이다(`applied.kind = "default"`).
- 상태(status)는 응답에서 센다: 지금 적용 → `applied`, 적용한 적이 있고 지금 아님 → `past`, 한 번도 → `testing`
  (웹 VersionStatus 그대로).
- 판 본문은 이름(title 1~40자) + 기준표(greenwash.criteria@1) + 모델 설정 + 프롬프트 글(선택 — 없으면 코드 글) +
  대상 단어(선택 — 없으면 코드 기본 목록, G2d) + 메모(0~200자)다(Q6·AS2b·AS3a-2). 한 번 저장 = 판 하나. 대상 단어는
  의심 낱말 빈도 목록만 바꾼다 — 환경 신호·처리 값은 판 밖(E0 상수, MARC-ENT-394).
- `evalPromptSha256` 은 실제로 쓸 판정(EVAL) 프롬프트의 sha256(저장할 때 지은 기록)이다 — 저장 글이 있으면 그 EVAL,
  없으면 그 기준표로 지은 글. 실행은 만들 때 다시 지은 값을 versions 에 박는다.
- id 는 int, 때는 +09:00 이 붙은 ISO 8601. items 는 새 것 먼저(id 내림).
- `createdBy.name` 은 저장한 운영 관리자의 지금 이름이고, 못 풀면 null.
이 파일은 등록 길(apps.py 의 ready)에서 들이지 않는다.
"""

from collections.abc import Mapping
from typing import Final, Literal, TypedDict

from pydantic import TypeAdapter, with_config

from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.contracts.shapes import FORBID, Count
from esgapi.greenwash.contracts.terms_shapes import GreenwashTerm

LIST_SHAPE: Final = "greenwash.ai-settings@2"
SETTING_SHAPE: Final = "greenwash.ai-setting@3"
DEFAULT_SHAPE: Final = "greenwash.ai-setting-default@3"

DEFAULT_TITLE: Final = "기본 설정"
"""기본 판의 이름(목록 default.title·ai-setting-default@2 의 title — MARC-ENT-387 노트). 낱말은 디자인이 바꾼다."""
TITLE_MAX_CHARS: Final = 40
"""판 이름 글자 수 상한(저장 본문 GreenwashAiSettingCreate.title). greenwash/models.py 의 AI_SETTING_TITLE_MAX_CHARS 와
같아야 한다(tests/contracts/test_ai_setting_shapes.py 가 견준다)."""

MEMO_MAX_CHARS: Final = 200
"""메모 글자 수 상한(저장 본문 GreenwashAiSettingCreate.memo 의 max_length). greenwash/models.py 의
AI_SETTING_MEMO_MAX_CHARS(칸 varchar(200))와 같아야 한다(tests/contracts/test_ai_setting_shapes.py 가 견준다)."""

GreenwashAiSettingStatus = Literal["applied", "past", "testing"]
"""판의 상태: 지금 적용 · 적용했던 판 · 한 번도 적용 안 함."""


@with_config(FORBID)
class GreenwashAiSettingAuthor(TypedDict):
    """판을 저장한 운영 관리자."""

    id: int
    """사용자 id."""
    name: str | None
    """지금 이름. 못 풀면 null."""


@with_config(FORBID)
class GreenwashAiSettingSummary(TypedDict):
    """저장된 판 하나의 요약(목록의 줄)."""

    id: int
    name: str
    """판 이름(v1, v2, …)."""
    title: str | None
    """판 이름 — 옛 판 null."""
    status: GreenwashAiSettingStatus
    createdAt: str
    """저장한 때(+09:00 ISO 8601)."""
    createdBy: GreenwashAiSettingAuthor
    memo: str
    """메모(0~200자)."""
    evalPromptSha256: str
    """실제 쓸 판정 프롬프트(저장 글이 있으면 그 EVAL)의 sha256(저장할 때)."""


@with_config(FORBID)
class GreenwashAiSettingAppliedDefault(TypedDict):
    """적용 판 없음 = 기본 판."""

    kind: Literal["default"]


@with_config(FORBID)
class GreenwashAiSettingAppliedSaved(TypedDict):
    """저장된 판 하나가 적용됨."""

    kind: Literal["saved"]
    id: int
    """적용된 판의 id."""


@with_config(FORBID)
class GreenwashAiSettingDefaultRef(TypedDict):
    """기본 판의 이름과 판정 프롬프트 sha256."""

    name: str
    title: str
    """기본 판 이름(DEFAULT_TITLE)."""
    evalPromptSha256: str


@with_config(FORBID)
class GreenwashAiSettingList(TypedDict):
    """greenwash.ai-settings@2 — 한 회사의 판 목록과 지금 적용 판. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.ai-settings@2"]
    companyId: int
    """대상 고객사의 id."""
    applied: GreenwashAiSettingAppliedDefault | GreenwashAiSettingAppliedSaved
    """지금 적용 판. 저장된 판이 적용돼 있지 않으면 기본 판."""
    default: GreenwashAiSettingDefaultRef
    """기본 판(코드에 고정)."""
    items: list[GreenwashAiSettingSummary]
    """저장된 판(새 것 먼저 — id 내림). limit·offset 의 한 쪽."""
    total: Count
    """저장된 판의 전체 수."""


@with_config(FORBID)
class GreenwashAiSetting(TypedDict):
    """greenwash.ai-setting@3 — 저장된 판 하나(요약 + 기준표 + 대상 단어). schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.ai-setting@3"]
    id: int
    name: str
    """판 이름(v1, v2, …). criteria.version 과 같다."""
    title: str | None
    """판 이름 — 옛 판 null."""
    status: GreenwashAiSettingStatus
    createdAt: str
    """저장한 때(+09:00 ISO 8601)."""
    createdBy: GreenwashAiSettingAuthor
    memo: str
    """메모(0~200자)."""
    evalPromptSha256: str
    """실제 쓸 판정 프롬프트(저장 글이 있으면 그 EVAL)의 sha256(저장할 때)."""
    criteria: GreenwashCriteria
    """판정 기준표(greenwash.criteria@1, version = 판 이름)."""
    terms: list[GreenwashTerm] | None
    """대상 단어(받은 차례). null = 코드 기본 목록(옛 판·terms 없이 저장한 판)."""


@with_config(FORBID)
class GreenwashAiSettingDefault(TypedDict):
    """greenwash.ai-setting-default@3 — 기본 판(코랩 원본 기준표). schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.ai-setting-default@3"]
    name: str
    """기본 판 이름(colab-2026-01-15-v1)."""
    title: str
    """기본 판 이름(DEFAULT_TITLE)."""
    criteria: GreenwashCriteria
    """기본 판 기준표."""
    evalPromptSha256: str
    """기본 판으로 지은 판정 프롬프트의 sha256."""
    terms: None
    """늘 null — 기본 판의 대상 단어는 코드 기본 목록(글자는 GET /greenwash/terms/default)."""


LIST_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashAiSettingList]]] = {
    LIST_SHAPE: TypeAdapter(GreenwashAiSettingList)
}
SETTING_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashAiSetting]]] = {SETTING_SHAPE: TypeAdapter(GreenwashAiSetting)}
DEFAULT_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashAiSettingDefault]]] = {
    DEFAULT_SHAPE: TypeAdapter(GreenwashAiSettingDefault)
}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
