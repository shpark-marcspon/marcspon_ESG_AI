"""그린워싱 AI 설정 판의 경로 일곱(밴드 G2c2 다섯 + AS2a 프롬프트·모델 읽기 둘 — 운영 관리자만). config/api.py 가
이 router 를 /ai-settings/greenwash 아래에 건다. 인증은 이 라우터의 **Bearer access(access_token_auth)** 다 —
/greenwash 의 회사 범위 인증(CompanyScopedAuth)은 운영 관리자에게 401 이라 자리를 따로 둔다(MARC-ENT-335 — 모듈 AI
설정은 /ai-settings/<모듈>).

    GET /ai-settings/greenwash?companyId=&limit=&offset=   판 목록과 지금 적용 판(greenwash.ai-settings@2)
    GET /ai-settings/greenwash/default                     기본 판(greenwash.ai-setting-default@3 — DB 0)
    GET /ai-settings/greenwash/default/prompt-model        기본 판의 프롬프트·모델(ai.prompt-model@3 — DB 0, AS2a·AP1b)
    GET /ai-settings/greenwash/{setting_id}?companyId=     판 하나(greenwash.ai-setting@3)
    GET /ai-settings/greenwash/{setting_id}/prompt-model?companyId=  판 하나의 프롬프트·모델(ai.prompt-model@3, AP1b)
    POST /ai-settings/greenwash?companyId=                 새 판 저장(본문 GreenwashAiSettingCreate) → 201
    PUT /ai-settings/greenwash/applied?companyId=          적용 판 바꾸기(본문 GreenwashAiSettingApply) → 목록

차례(user 의 run_logs.py 와 같다): 인증(Bearer) → permitted(is_initial → 표) → 회사 고르기(user 의 chosen_company — 같은
규칙: 없으면 하나뿐인 회사, 여럿이면 400 company_ambiguous, 없는 회사 404) → actions(첫 문장이 다시 권한). 고객사
사용자의 403 은 회사 세기·DB 읽기 0 이다. 경로는 models 를 import 하지 않는다(`.importlinter` 계약 라).
오류: 없는 판·남의 회사의 판 404 `not_found`(같은 몸) · 받기 거절 400 `CRITERIA_*`(criteria_e0.MESSAGES 의 code·문장) ·
본문 꼴 위반 422 `VALIDATION_ERROR`(StrictIn — 메모 201자 포함) · 겹친 저장이 이름 다시 시도를 다 쓰면 409
`NAME_CONFLICT`(행 0) · 지금 받기 규칙에 안 맞는 저장 판의 적용 409 `AI_SETTING_UNUSABLE`(쓰기·감사 0, 기본 판으로
되돌리기는 늘 됨 — 밴드 G2c3. 그 판이 적용된 회사의 POST /runs 도 같은 code) · 그런 판의 프롬프트·모델 읽기도 409
`AI_SETTING_UNUSABLE`(판 상세는 200 — AS2a. 모델 설정이 안 맞으면 모델 문장 — AS2b) · 모델 설정 받기 거절 400
`AI_MODEL_*`(core/calc/ai_settings 의 code·문장 — NaN·Infinity 는 AI_MODEL_TEMPERATURE_RANGE, 행 0·감사 0. 꼴 틀림 —
true·"5"·webSearch 0 — 은 422, AS2b) · 프롬프트 글 받기 거절 400 `AI_PROMPT_*`(core/calc/ai_settings 의 code·문장 +
fields `{"prompts.steps.<i>.prompts.<j>.text|memo": [문장]}` — 422 와 같은 경로 규칙, 행 0·감사 0. 꼴 틀림은 422,
AS3a-2) · 판 이름 title 없음·빈 글·41자·NUL 422 `fields.title` · 메모 NUL·짝 없는 서로게이트 422 `fields.memo`
(GWB1). 지금 받기에 안 맞는 저장 글 판의 적용·프롬프트·모델 읽기도 409 `AI_SETTING_UNUSABLE`(프롬프트 문장) · 대상
단어 받기 거절 400 `TERMS_*`(flows/terms_e0 의 code·문장 + fields `{"terms.<i>.text" | "terms": [문장]}`, 행 0·감사 0.
꼴 틀림 — 1001개·201자·칸 빠짐·모르는 칸·bool 아닌 enabled — 은 422, G2d). 지금 받기에 안 맞는 단어 판의 적용도
409 `AI_SETTING_UNUSABLE`(적용 문장 그대로).
★ 테넌트·사용자 id 는 인증 주체(토큰)에서만 온다. 대상 회사는 쿼리 companyId 하나다(본문에 회사·사용자 칸 없음).
"""

from typing import Annotated

from django.http import HttpRequest
from ninja import Router, Status
from ninja.params.functions import Query
from pydantic import Field, StringConstraints, ValidationInfo, field_validator

from esgapi.core.auth.bearer import access_token_auth, permitted
from esgapi.core.calc.ai_settings import has_bad_chars
from esgapi.core.conf import now
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptModel3, AiPromptsIn
from esgapi.core.exceptions import ApplicationError, ErrorBody
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES, StrictIn
from esgapi.greenwash.contracts.ai_setting_shapes import (
    MEMO_MAX_CHARS,
    TITLE_MAX_CHARS,
    GreenwashAiSetting,
    GreenwashAiSettingDefault,
    GreenwashAiSettingList,
)
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.contracts.terms_shapes import TERMS_SENT_MAX, GreenwashTermIn
from esgapi.greenwash.service.actions import ai_settings as actions
from esgapi.greenwash.service.services.ai_settings import (
    CriteriaRefused,
    ModelRefused,
    NameConflict,
    PromptsRefused,
    SettingUnusable,
    TermsRefused,
)
from esgapi.user.service.apis.users import chosen_company, company_ports

# 인증은 라우터에 단다(user 의 run_logs.py 가 경로마다 다는 것과 같은 Bearer access) — config/api.py 는 자리만 건다.
router = Router(tags=["그린워싱 AI 설정"], auth=access_token_auth)

NOT_FOUND = "그런 AI 설정 판이 없다"
NAME_CONFLICT = "같은 회사의 판 저장이 겹쳐 이름을 매기지 못했다. 다시 저장해 달라"
ERRORS: dict[int, type[ErrorBody]] = {**TOKEN_ERROR_RESPONSES, 404: ErrorBody}
"""회사를 고르는 넷: 없는 회사·없는 판(404). 400·409 는 TOKEN_*_ERROR_RESPONSES 에 든다."""
BODY_ERRORS: dict[int, type[ErrorBody]] = {**TOKEN_BODY_ERROR_RESPONSES, 404: ErrorBody}

CompanyId = Annotated[
    int | None, Query(description="대상 고객사의 id. 없으면 하나뿐인 회사(둘 이상이면 400 company_ambiguous)")
]


class GreenwashAiSettingCreate(StrictIn):
    """새 판 저장의 본문 — 한 번 저장 = 판 하나(이름·기준표·모델·프롬프트·메모가 한 본문, AS3a-2). 모르는 칸을
    거절하고 타입을 바꿔 받지 않는다(StrictIn).

    criteria 의 version 은 서버가 매긴 판 이름(v1, v2, …)으로 덮는다. 받기 규칙(15줄 고정·글 1~300자 등)을 어기면 400
    `CRITERIA_*`(문장은 화면에 그대로 보일 꼴). 받기 차례: 꼴(422) → 기준표 → 모델 → 프롬프트 → 대상 단어(400) —
    하나라도 거절이면 행 0·감사 0.
    """

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX_CHARS)] = Field(
        description="판 이름(앞뒤 공백을 뺀 1~40자, 겹침 허용). 판 번호 name(v<n>)은 서버가 매긴다"
    )
    criteria: GreenwashCriteria | None = Field(
        default=None, description="판정 기준표(greenwash.criteria@1). 빠지거나 null 이면 기본 기준표"
    )
    # AS2b: 받기 거절은 400 AI_MODEL_*, 꼴 틀림(true·"5"·webSearch 0 — core 꼴이 strict)은 422
    modelSettings: AiModelSettingsIn | None = Field(
        default=None,
        description="판정 단계의 모델 설정(ai.model-settings@1). 빠지거나 null 이면 코드 값. 모델 설정만 바꿔도 새 판",
    )
    # AS3a-2: 받기 거절은 400 AI_PROMPT_* + fields, 꼴 틀림(칸 빠짐·모르는 칸 — core 꼴이 strict)은 422
    prompts: AiPromptsIn | None = Field(
        default=None,
        description="판정 단계의 프롬프트 글(ai.prompts@1 — 넷 전부). 빠지거나 null 이면 코드 글. 글만 바꿔도 새 판",
    )
    # G2d: 꼴(목록 1000·글 200 — 느슨한 그물)은 422, 규칙(글 1~30자·괄호·따옴표·보이지 않는 글자·키 겹침·100개·켠 것
    # ≥ 1)은 받기의 400 TERMS_* + fields
    terms: list[GreenwashTermIn] | None = Field(
        default=None,
        max_length=TERMS_SENT_MAX,
        description=(
            "대상 단어({text, enabled} 목록 — 의심 낱말 빈도 목록). 빠지거나 null 이면 코드 기본 목록. 켠 낱말만 이"
            " 차례로 센다. 판정할 문장을 고르는 환경 신호에는 넣지 않는다. 단어만 바꿔도 새 판"
        ),
    )
    memo: str = Field(default="", max_length=MEMO_MAX_CHARS, description="메모(0~200자)")

    # memo 도 같은 거절(GWB1 — NUL 은 Postgres DataError 로 500 이었다, MARC-ISSUE-289)
    @field_validator("title", "memo")
    @classmethod
    def _no_bad_characters(cls, value: str, info: ValidationInfo) -> str:
        if has_bad_chars(value):
            raise ValueError(f"{'판 이름' if info.field_name == 'title' else '메모'}에 쓸 수 없는 글자가 있다")
        return value


class GreenwashAiSettingApply(StrictIn):
    """적용 판 바꾸기의 본문. id 가 null 이면 기본 판(코랩 원본)으로 되돌린다. 이미 그 판이면 바꾸지 않는다(200)."""

    id: int | None


def _unusable_view(found: SettingUnusable) -> str:
    """prompt-model 의 409 문장 — 원인(모델 설정 ai_model_* · 프롬프트 글 ai_prompt_* · 기준표)으로 가른다(AS2a 리뷰
    L4·AS3a-2)."""
    if found.code.startswith("ai_model_"):
        return f"AI 설정 판({found.name})의 모델 설정이 지금 고를 수 있는 모델에 맞지 않아요. 판을 다시 저장해 주세요"
    if found.code.startswith("ai_prompt_"):
        return f"AI 설정 판({found.name})의 프롬프트 글이 지금 규칙에 맞지 않아요. 판을 다시 저장해 주세요"
    return f"AI 설정 판({found.name})이 지금 규칙에 맞지 않아 프롬프트를 지을 수 없어요. 판을 다시 저장해 주세요"


def _forbidden(refused: actions.Forbidden) -> ApplicationError:
    return ApplicationError("forbidden", "forbidden", f"운영 관리자만 한다({refused.operation_id})")


@router.get("", operation_id="greenwash_ai_setting_list", response={200: GreenwashAiSettingList, **ERRORS})
def ai_setting_list(
    request: HttpRequest,
    companyId: CompanyId = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> GreenwashAiSettingList:
    """운영 관리자만. 고른 회사의 저장된 판(새 것 먼저)과 지금 적용 판·기본 판."""
    principal = permitted(request, "greenwash_ai_setting_list")
    company_id = chosen_company(companyId, company_ports())
    found = actions.setting_list(actor_kind=principal.kind, company_id=company_id, limit=limit, offset=offset)
    if isinstance(found, actions.Forbidden):
        raise _forbidden(found)
    return found


@router.get(
    "/default",
    operation_id="greenwash_ai_setting_default",
    response={200: GreenwashAiSettingDefault, **TOKEN_ERROR_RESPONSES},
)
def ai_setting_default(request: HttpRequest) -> GreenwashAiSettingDefault:
    """운영 관리자만. 기본 판(코랩 원본 기준표 — 코드에 고정). 회사를 고르지 않는다."""
    principal = permitted(request, "greenwash_ai_setting_default")
    found = actions.default_setting(actor_kind=principal.kind)
    if isinstance(found, actions.Forbidden):
        raise _forbidden(found)
    return found


@router.get(
    "/default/prompt-model",
    operation_id="greenwash_ai_setting_default_prompt_model",
    response={200: AiPromptModel3, **TOKEN_ERROR_RESPONSES},
)
def ai_setting_default_prompt_model(request: HttpRequest) -> AiPromptModel3:
    """운영 관리자만. 기본 판의 판정 단계 프롬프트 넷(전문·sha)과 모델 칸·고를 수 있는 경로. 회사를 고르지 않는다.
    /{setting_id}/prompt-model 보다 먼저 건다(그 자리가 글자를 다 받는다 — 뒤에 걸면 422)."""
    principal = permitted(request, "greenwash_ai_setting_default_prompt_model")
    found = actions.default_prompt_model(actor_kind=principal.kind)
    if isinstance(found, actions.Forbidden):
        raise _forbidden(found)
    return found


@router.put(
    "/applied", operation_id="greenwash_ai_setting_apply", response={200: GreenwashAiSettingList, **BODY_ERRORS}
)
def ai_setting_apply(
    request: HttpRequest, body: GreenwashAiSettingApply, companyId: CompanyId = None
) -> GreenwashAiSettingList:
    """운영 관리자만. 고른 회사의 적용 판을 바꾼다(id null = 기본 판). 바뀌면 감사 setting_change 한 줄, 이미 그
    판이면 바꿈·감사 0. 없거나 남의 회사의 판이면 404. 응답은 바꾼 뒤의 목록 첫 쪽."""
    principal = permitted(request, "greenwash_ai_setting_apply")
    company_id = chosen_company(companyId, company_ports())
    changed = actions.apply_setting(
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        company_id=company_id,
        setting_id=body.id,
        now=now(),
    )
    if isinstance(changed, actions.Forbidden):
        raise _forbidden(changed)
    if isinstance(changed, actions.NotFound):
        raise ApplicationError("not_found", "not_found", NOT_FOUND)
    if isinstance(changed, SettingUnusable):
        raise ApplicationError(
            "conflict",
            "ai_setting_unusable",
            f"AI 설정 판({changed.name})이 지금 규칙에 맞지 않아 적용할 수 없어요. 판을 다시 저장해 적용해 주세요",
        )
    return changed


@router.get("/{setting_id}", operation_id="greenwash_ai_setting_get", response={200: GreenwashAiSetting, **ERRORS})
def ai_setting_get(request: HttpRequest, setting_id: int, companyId: CompanyId = None) -> GreenwashAiSetting:
    """운영 관리자만. 고른 회사의 판 하나(기준표째). 없거나 남의 회사의 판이면 404.

    ★ 자리는 Django 의 int 변환기가 아니라 ninja 의 int 검사다: 인증·권한이 경로 인자 검사보다 먼저 선다(보안 층의
    401·403 훑기가 자리 글자 그대로 보낸다). 숫자 아닌 id 는 422. /default·/applied 는 이 경로보다 먼저 걸어야 그쪽으로
    간다(이 자리가 글자를 다 받는다 — 뒤에 걸면 PUT /applied 가 405)."""
    principal = permitted(request, "greenwash_ai_setting_get")
    company_id = chosen_company(companyId, company_ports())
    found = actions.setting_detail(actor_kind=principal.kind, company_id=company_id, setting_id=setting_id)
    if isinstance(found, actions.Forbidden):
        raise _forbidden(found)
    if isinstance(found, actions.NotFound):
        raise ApplicationError("not_found", "not_found", NOT_FOUND)
    return found


@router.get(
    "/{setting_id}/prompt-model",
    operation_id="greenwash_ai_setting_prompt_model",
    response={200: AiPromptModel3, **ERRORS},
)
def ai_setting_prompt_model(request: HttpRequest, setting_id: int, companyId: CompanyId = None) -> AiPromptModel3:
    """운영 관리자만. 고른 회사의 판 하나의 판정 단계 프롬프트 넷(eval 은 그 판의 기준표로 지은 글 — sha 가 그 판의
    evalPromptSha256)과 모델 칸·고를 수 있는 경로. 없거나 남의 회사의 판이면 404, 지금 받기 규칙에 안 맞는 판이면
    409."""
    principal = permitted(request, "greenwash_ai_setting_prompt_model")
    company_id = chosen_company(companyId, company_ports())
    found = actions.prompt_model(actor_kind=principal.kind, company_id=company_id, setting_id=setting_id)
    if isinstance(found, actions.Forbidden):
        raise _forbidden(found)
    if isinstance(found, actions.NotFound):
        raise ApplicationError("not_found", "not_found", NOT_FOUND)
    if isinstance(found, SettingUnusable):
        raise ApplicationError("conflict", "ai_setting_unusable", _unusable_view(found))
    return found


@router.post("", operation_id="greenwash_ai_setting_create", response={201: GreenwashAiSetting, **BODY_ERRORS})
def ai_setting_create(
    request: HttpRequest, body: GreenwashAiSettingCreate, companyId: CompanyId = None
) -> Status[GreenwashAiSetting]:
    """운영 관리자만. 고른 회사에 새 판을 저장한다(판 번호는 서버가 v<n>, 이름 title 은 본문). 감사 setting_change 한
    줄. criteria 가 빠지면 기본 기준표, modelSettings 가 빠지면 코드 값, prompts 가 빠지면 코드 글이고, 있으면 받기를
    거친 정규형을 저장한다(무엇 하나만 바꿔도 새 판). terms 가 빠지면 코드 기본 목록. 프롬프트만 따로 저장하는 경로는
    없다. 받기 차례 기준표 → 모델 → 프롬프트 → 대상 단어, 프롬프트·단어 거절은 400 AI_PROMPT_*·TERMS_* 에 fields(어긴
    칸의 점 경로)."""
    principal = permitted(request, "greenwash_ai_setting_create")
    company_id = chosen_company(companyId, company_ports())
    saved = actions.save_setting(
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        company_id=company_id,
        title=body.title,
        memo=body.memo,
        now=now(),
        criteria=body.criteria,
        model_settings=body.modelSettings,
        prompts=body.prompts,
        terms=body.terms,
    )
    if isinstance(saved, actions.Forbidden):
        raise _forbidden(saved)
    if isinstance(saved, CriteriaRefused | ModelRefused):
        raise ApplicationError("invalid_input", saved.code, saved.message)
    if isinstance(saved, PromptsRefused | TermsRefused):
        raise ApplicationError("invalid_input", saved.code, saved.message, fields={saved.field: [saved.message]})
    if isinstance(saved, NameConflict):
        raise ApplicationError("conflict", "name_conflict", NAME_CONFLICT)
    return Status(201, saved)
