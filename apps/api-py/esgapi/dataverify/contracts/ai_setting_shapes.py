"""AI 설정 판 꼴 셋 — 회사별 데이터 검증 AI 설정의 판(밴드 DVA1 ②, 결정 MARC-ENT-399·381·387). 경로는
`/ai-settings/dataverify`(service/apis/ai_settings.py — 운영 관리자만). 영문번역 판 꼴(translation/contracts/
ai_setting_shapes.py)의 판별 복사다(이름 접두만 다름 — 모듈끼리 import 하지 않는다).

    dataverify.ai-settings@1          DataverifyAiSettingList     GET /ai-settings/dataverify · PUT …/applied 의 응답
    dataverify.ai-setting@1           DataverifyAiSetting         GET /ai-settings/dataverify/{id} · POST 의 응답
    dataverify.ai-setting-default@1   DataverifyAiSettingDefault  GET /ai-settings/dataverify/default 의 응답
판의 프롬프트 글·모델 설정은 ai.prompt-model@3(core 꼴 — …/{id}/prompt-model·…/default/prompt-model)으로 본다.

TypedDict(모르는 키 금지) → JSON 스키마. 클래스 이름이 openapi 의 구성요소 이름이 되므로 `DataverifyAiSetting` 으로
시작한다.

**이 파일에 로직은 없다.** 규칙(service/services·actions/ai_settings.py):
- 판은 회사별 불변 행이다. 저장 = 새 판, 고쳐 쓰기·지우기 없음. 판 번호는 서버가 회사 안에서 `v1`, `v2`, … 로
  매긴다(core next_version_name). 판 이름(title)은 받은 1~40자.
- 기본 판(엔진 코드 글·모델 칸 기본값, 이름 DEFAULT_NAME)은 코드에 고정이고 목록의 items 에 없다. 적용 판이 없으면 곧
  기본 판이다(`applied.kind = "default"`).
- 상태(status)는 응답에서 센다(core version_status): 지금 적용 → `applied`, 적용한 적이 있고 지금 아님 → `past`, 한
  번도 → `testing`.
- 판 본문은 이름 + 모델 설정(선택 — 없으면 코드 값) + 프롬프트 글(선택 — 없으면 코드 글) + 메모(0~200자)다. 한 번
  저장 = 판 하나.
- id 는 int, 때는 +09:00 이 붙은 ISO 8601. items 는 새 것 먼저(id 내림).
- `createdBy.name` 은 저장한 운영 관리자의 지금 이름이고, 못 풀면 null.
이 파일은 등록 길(apps.py 의 ready)에서 들이지 않는다.
"""

from collections.abc import Mapping
from typing import Final, Literal, TypedDict

from pydantic import TypeAdapter, with_config

from esgapi.core.contracts.ai_setting_shapes import VERSION_MEMO_MAX_CHARS, VERSION_TITLE_MAX_CHARS, AiVersionStatus
from esgapi.dataverify.contracts.shapes import FORBID, Count

LIST_SHAPE: Final = "dataverify.ai-settings@1"
SETTING_SHAPE: Final = "dataverify.ai-setting@1"
DEFAULT_SHAPE: Final = "dataverify.ai-setting-default@1"

DEFAULT_NAME: Final = "colab_156"
"""기본 판의 판 번호 자리 글(엔진 판 — flows/binding_156.ENGINE 과 같은 글자, 시험이 견준다. 계약은 flows 를 모른다
— tests/test_axes.py, 그래서 import 하지 않고 글자로 적는다)."""
DEFAULT_TITLE: Final = "기본 설정"
"""기본 판의 이름(목록 default.title·ai-setting-default@1 의 title·실행 versions.aiSetting)."""
TITLE_MAX_CHARS: Final = VERSION_TITLE_MAX_CHARS
"""판 이름 글자 수 상한(저장 본문 DataverifyAiSettingCreate.title — core 판 상수)."""
MEMO_MAX_CHARS: Final = VERSION_MEMO_MAX_CHARS
"""메모 글자 수 상한(저장 본문 DataverifyAiSettingCreate.memo — core 판 상수)."""


@with_config(FORBID)
class DataverifyAiSettingAuthor(TypedDict):
    """판을 저장한 운영 관리자."""

    id: int
    """사용자 id."""
    name: str | None
    """지금 이름. 못 풀면 null."""


@with_config(FORBID)
class DataverifyAiSettingSummary(TypedDict):
    """저장된 판 하나의 요약(목록의 줄)."""

    id: int
    name: str
    """판 번호(v1, v2, …)."""
    title: str
    """판 이름(1~40자)."""
    status: AiVersionStatus
    createdAt: str
    """저장한 때(+09:00 ISO 8601)."""
    createdBy: DataverifyAiSettingAuthor
    memo: str
    """메모(0~200자)."""


@with_config(FORBID)
class DataverifyAiSettingAppliedDefault(TypedDict):
    """적용 판 없음 = 기본 판."""

    kind: Literal["default"]


@with_config(FORBID)
class DataverifyAiSettingAppliedSaved(TypedDict):
    """저장된 판 하나가 적용됨."""

    kind: Literal["saved"]
    id: int
    """적용된 판의 id."""


@with_config(FORBID)
class DataverifyAiSettingDefaultRef(TypedDict):
    """기본 판의 번호 자리 글과 이름."""

    name: str
    """DEFAULT_NAME."""
    title: str
    """DEFAULT_TITLE."""


@with_config(FORBID)
class DataverifyAiSettingList(TypedDict):
    """dataverify.ai-settings@1 — 한 회사의 판 목록과 지금 적용 판. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["dataverify.ai-settings@1"]
    companyId: int
    """대상 고객사의 id."""
    applied: DataverifyAiSettingAppliedDefault | DataverifyAiSettingAppliedSaved
    """지금 적용 판. 저장된 판이 적용돼 있지 않으면 기본 판."""
    default: DataverifyAiSettingDefaultRef
    """기본 판(코드에 고정)."""
    items: list[DataverifyAiSettingSummary]
    """저장된 판(새 것 먼저 — id 내림). limit·offset 의 한 쪽."""
    total: Count
    """저장된 판의 전체 수."""


@with_config(FORBID)
class DataverifyAiSetting(TypedDict):
    """dataverify.ai-setting@1 — 저장된 판 하나(요약). 글·모델은 …/{id}/prompt-model. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["dataverify.ai-setting@1"]
    id: int
    name: str
    """판 번호(v1, v2, …)."""
    title: str
    """판 이름(1~40자)."""
    status: AiVersionStatus
    createdAt: str
    """저장한 때(+09:00 ISO 8601)."""
    createdBy: DataverifyAiSettingAuthor
    memo: str
    """메모(0~200자)."""


@with_config(FORBID)
class DataverifyAiSettingDefault(TypedDict):
    """dataverify.ai-setting-default@1 — 기본 판(엔진 코드 글·모델 칸 기본값). schemaVersion 이 첫 키다."""

    schemaVersion: Literal["dataverify.ai-setting-default@1"]
    name: str
    """DEFAULT_NAME."""
    title: str
    """DEFAULT_TITLE."""


LIST_SHAPES: Final[Mapping[str, TypeAdapter[DataverifyAiSettingList]]] = {
    LIST_SHAPE: TypeAdapter(DataverifyAiSettingList)
}
SETTING_SHAPES: Final[Mapping[str, TypeAdapter[DataverifyAiSetting]]] = {
    SETTING_SHAPE: TypeAdapter(DataverifyAiSetting)
}
DEFAULT_SHAPES: Final[Mapping[str, TypeAdapter[DataverifyAiSettingDefault]]] = {
    DEFAULT_SHAPE: TypeAdapter(DataverifyAiSettingDefault)
}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
