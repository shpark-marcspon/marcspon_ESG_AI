"""회사별 AI 설정 판의 읽기·저장·적용(밴드 G2c2 — 운영 관리자의 경로 /ai-settings/greenwash). greenwash 의 selector·
service 에 user(운영 관리자 이름 풀기)·core(감사)를 엮어 조립하므로 Action 이다(Service·Selector 는 남의 도메인을
import 하지 않는다 — `.importlinter` 계약 바).

    setting_list(actor_kind, company_id, limit, offset)                      목록(greenwash.ai-settings@2)
    setting_detail(actor_kind, company_id, setting_id)                       판 하나(greenwash.ai-setting@3)
    save_setting(actor_kind, actor_user_id, company_id, title, memo, now, criteria, model_settings, prompts, terms)
                                                                             새 판 + 감사 setting_change
    apply_setting(actor_kind, actor_user_id, company_id, setting_id, now)    적용 바꾸기 + 감사 setting_change
    default_setting(actor_kind)                                              기본 판(ai-setting-default@3 — DB 0)
    prompt_model(actor_kind, company_id, setting_id)                         판 하나의 프롬프트·모델(AS2a)
    default_prompt_model(actor_kind)                                         기본 판의 프롬프트·모델(DB 0)

★ 공개 일곱의 첫 문장이 자기 동작 칸의 권한 검사다(core/permissions.py — 운영 관리자만. 경로의 permitted 에 더해 —
  core/tests/test_permissions.py 의 ALSO_INSIDE). 막히면 아무것도 읽거나 쓰지 않는다. 기본 판은 DB 를 읽지 않지만 같은
  꼴이다(운영 관리자 칸 전부가 ALSO_INSIDE). 실행기가 판을 읽는 길은 권한 없는 selector 다(주체가 없다 — G2c2 ③).
★ 감사(MARC-ENT-295·244 — AD-05): 저장·적용마다 action setting_change, target_kind ai_setting, 대상 회사의 줄.
  감사는 업무 블록(services 의 atomic) **뒤**다 — 블록이 실패하면 줄 0, 감사가 거절돼도(AuditRefused) 응답은 그대로다
  (record_event 는 던지지 않는다). 받기 거절(기준표·모델 설정·프롬프트 글)·없는 판·못 받는 판의 적용(G2c3)·같은 판
  다시 적용은 줄 0. 저장의 changed_fields 는 criteria·memo·model_settings·prompts·terms(AS2b Q-B4·AS3a-2 J8·G2d —
  판의 칸을 늘 함께 정한다). target_label 은 판 번호(v<n>) 그대로다.
  결과는 늘 success. 프롬프트·모델 읽기 둘은 감사 0(읽기).
★ 프롬프트·모델(AS2a·AS2b): 조립은 flows/prompt_model_e0(순수), 설정·명세는 selectors.RunModelSource(실행기와 같은
  원천). 저장 판의 모델 칸은 그 판에 저장한 값을 지금 설정으로 다시 받은 것(AS2b), 기본 판은 명세의 기본값(defaults).
  지금 받기 규칙에 안 맞는 저장 판(기준표든 모델 설정이든 프롬프트 글이든)은 services.SettingUnusable(G2c3 의 적용
  막기와 같은 갈래 — 경로 409 AI_SETTING_UNUSABLE). 잡는 예외는 CriteriaRejected 하나다(모델·프롬프트 거절은 값).
  받기 차례는 적용(services.apply_setting)과 같이 기준표 → 모델 → 프롬프트(MARC-ISSUE-257 2번). 저장 판의 프롬프트
  칸은 저장 글·메모(AS3a-2), 없으면 코드 글.
★ 판 이름(AS3a-2, MARC-ENT-387): 저장 판은 행의 title(옛 판 None), 기본 판과 목록 default 는 DEFAULT_TITLE.
★ 대상 단어(G2d, MARC-ENT-394): 판 하나는 행의 terms(None = 코드 기본 목록), 기본 판은 늘 None. 적용의 다시 받기는
  services.apply_setting 이 한다. 프롬프트·모델 읽기(prompt_model)는 단어를 보지 않는다(처분 G2d-order-review-2 N2).
★ createdBy.name 은 user 의 names_of(운영 관리자 입구)로 지금 이름을 푼다. 못 풀면 null(계약).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from esgapi.core.auth.principal import Kind
from esgapi.core.calc.ai_settings import ModelSettingRefused, PromptRefused, defaults
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptModel3, AiPromptsIn
from esgapi.core.permissions import is_allowed
from esgapi.core.schemas import to_seoul_iso
from esgapi.core.service.services.audit import record_event
from esgapi.greenwash.contracts.ai_setting_shapes import (
    DEFAULT_SHAPE,
    DEFAULT_TITLE,
    LIST_SHAPE,
    SETTING_SHAPE,
    GreenwashAiSetting,
    GreenwashAiSettingAppliedDefault,
    GreenwashAiSettingAppliedSaved,
    GreenwashAiSettingDefault,
    GreenwashAiSettingList,
    GreenwashAiSettingSummary,
)
from esgapi.greenwash.flows import colab_e0, prompt_model_e0
from esgapi.greenwash.flows.criteria_e0 import DEFAULT_VERSION, CriteriaRejected, accept_criteria, default_criteria
from esgapi.greenwash.service.selectors import ai_settings as selectors
from esgapi.greenwash.service.services import ai_settings as services
from esgapi.user.service.selectors.user import names_of

LABEL_MAX = 255  # core_audit_events.target_label 의 길이
MODULE: Final = "greenwash"  # 감사 줄의 module(AD4S — report.py 의 MODULE 과 같은 꼴)


@dataclass(frozen=True, slots=True)
class Forbidden:
    """운영 관리자가 아니다(아무것도 읽거나 쓰지 않았다)."""

    operation_id: str


@dataclass(frozen=True, slots=True)
class NotFound:
    """그런 판이 없다(남의 회사의 판도 이 갈래)."""


def _names(settings: tuple[selectors.AiSettingHead, ...], company_id: int) -> dict[int, str]:
    found = names_of(company_id, set(), {s.created_by_user_id for s in settings})
    return {user_id: name for user_id, (_username, name) in found.items() if name.strip()}


def _summary(setting: selectors.AiSettingHead, names: dict[int, str]) -> GreenwashAiSettingSummary:
    return {
        "id": setting.id,
        "name": setting.name,
        "title": setting.title,
        "status": selectors.status_of(setting.applied, setting.applied_at),
        "createdAt": to_seoul_iso(setting.created_at),
        "createdBy": {"id": setting.created_by_user_id, "name": names.get(setting.created_by_user_id)},
        "memo": setting.memo,
        "evalPromptSha256": setting.eval_prompt_sha256,
    }


def _one(setting: selectors.AiSetting, company_id: int) -> GreenwashAiSetting:
    return {
        "schemaVersion": SETTING_SHAPE,
        **_summary(setting, _names((setting,), company_id)),
        "criteria": setting.criteria,
        "terms": setting.terms,
    }


def _list(company_id: int, limit: int, offset: int) -> GreenwashAiSettingList:
    page = selectors.ai_setting_page(company_id=company_id, limit=limit, offset=offset)
    names = _names(page.items, company_id)
    applied: GreenwashAiSettingAppliedDefault | GreenwashAiSettingAppliedSaved = (
        {"kind": "default"} if page.applied_id is None else {"kind": "saved", "id": page.applied_id}
    )
    return {
        "schemaVersion": LIST_SHAPE,
        "companyId": company_id,
        "applied": applied,
        "default": {
            "name": DEFAULT_VERSION,
            "title": DEFAULT_TITLE,
            "evalPromptSha256": str(colab_e0.run_versions(None)["evalPromptSha256"]),
        },
        "items": [_summary(s, names) for s in page.items],
        "total": page.total,
    }


def setting_list(*, actor_kind: Kind, company_id: int, limit: int, offset: int) -> GreenwashAiSettingList | Forbidden:
    if not is_allowed("greenwash_ai_setting_list", kind=actor_kind):
        return Forbidden("greenwash_ai_setting_list")
    return _list(company_id, limit, offset)


def setting_detail(*, actor_kind: Kind, company_id: int, setting_id: int) -> GreenwashAiSetting | NotFound | Forbidden:
    if not is_allowed("greenwash_ai_setting_get", kind=actor_kind):
        return Forbidden("greenwash_ai_setting_get")
    found = selectors.ai_setting_detail(company_id=company_id, setting_id=setting_id)
    return NotFound() if isinstance(found, selectors.SettingMissing) else _one(found, company_id)


def save_setting(
    *,
    actor_kind: Kind,
    actor_user_id: int,
    company_id: int,
    title: str,
    memo: str,
    now: datetime,
    criteria: object = None,
    model_settings: AiModelSettingsIn | None = None,
    prompts: AiPromptsIn | None = None,
    terms: object = None,
) -> (
    GreenwashAiSetting
    | services.CriteriaRefused
    | services.ModelRefused
    | services.PromptsRefused
    | services.TermsRefused
    | services.NameConflict
    | Forbidden
):
    """받은 이름·기준표(빠지면 기본 기준표)·모델 설정(빠지면 코드 값)·프롬프트 글(빠지면 코드 글)·대상 단어(빠지면
    코드 기본 목록)로 새 판. 받기 거절·이름 경합 소진이면 행 0·감사 0."""
    if not is_allowed("greenwash_ai_setting_create", kind=actor_kind):
        return Forbidden("greenwash_ai_setting_create")
    created = services.create_setting(
        company_id=company_id,
        created_by_user_id=actor_user_id,
        title=title,
        memo=memo,
        criteria=criteria,
        model_settings=model_settings,
        prompts=prompts,
        terms=terms,
    )
    if isinstance(
        created,
        services.CriteriaRefused
        | services.ModelRefused
        | services.PromptsRefused
        | services.TermsRefused
        | services.NameConflict,
    ):
        return created
    record_event(
        at=now,
        company_id=company_id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        action="setting_change",
        event="ai_setting_created",
        result="success",
        target_kind="ai_setting",
        target_id=created.id,
        target_label=created.name[:LABEL_MAX],
        changed_fields=("criteria", "memo", "model_settings", "prompts", "terms"),
        module=MODULE,
    )
    found = selectors.ai_setting_detail(company_id=company_id, setting_id=created.id)
    if isinstance(found, selectors.SettingMissing):  # 방금 쓴 행이 없다(지우는 길이 없다 — 일어나지 않는다)
        raise RuntimeError("방금 만든 greenwash_ai_settings 의 행이 없다")
    return _one(found, company_id)


def apply_setting(
    *, actor_kind: Kind, actor_user_id: int, company_id: int, setting_id: int | None, now: datetime
) -> GreenwashAiSettingList | services.SettingUnusable | NotFound | Forbidden:
    """그 회사의 적용 판을 setting_id 로(None = 기본 판). 응답은 바꾼 뒤의 목록 첫 쪽(새 것 먼저 20). 지금 받기에
    안 맞는 판이면 SettingUnusable 그대로(쓰기·감사 0)."""
    if not is_allowed("greenwash_ai_setting_apply", kind=actor_kind):
        return Forbidden("greenwash_ai_setting_apply")
    changed = services.apply_setting(company_id=company_id, setting_id=setting_id, now=now)
    if isinstance(changed, selectors.SettingMissing):
        return NotFound()
    if isinstance(changed, services.SettingUnusable):
        return changed
    if isinstance(changed, services.Applied):
        record_event(
            at=now,
            company_id=company_id,
            actor_kind=actor_kind,
            actor_user_id=actor_user_id,
            action="setting_change",
            event="ai_setting_applied",
            result="success",
            target_kind="ai_setting",
            target_id=changed.after_id,
            target_label=(changed.after_name or DEFAULT_VERSION)[:LABEL_MAX],
            changed_fields=("applied",),
            module=MODULE,
        )
    return _list(company_id, 20, 0)


def default_setting(*, actor_kind: Kind) -> GreenwashAiSettingDefault | Forbidden:
    """기본 판(코랩 원본 기준표 — 코드에 고정, DB 0)."""
    if not is_allowed("greenwash_ai_setting_default", kind=actor_kind):
        return Forbidden("greenwash_ai_setting_default")
    return {
        "schemaVersion": DEFAULT_SHAPE,
        "name": DEFAULT_VERSION,
        "title": DEFAULT_TITLE,
        "criteria": default_criteria(),
        "evalPromptSha256": str(colab_e0.run_versions(None)["evalPromptSha256"]),
        "terms": None,
    }


def prompt_model(
    *, actor_kind: Kind, company_id: int, setting_id: int
) -> AiPromptModel3 | NotFound | services.SettingUnusable | Forbidden:
    """고른 회사의 판 하나의 프롬프트 넷·모델 칸(그 판에 저장한 값). 없거나 남의 회사의 판이면 NotFound, 기준표나
    모델 설정·프롬프트 글이 지금 받기에 안 맞으면 SettingUnusable(판 이름째 — 기준 글은 싣지 않는다)."""
    if not is_allowed("greenwash_ai_setting_prompt_model", kind=actor_kind):
        return Forbidden("greenwash_ai_setting_prompt_model")
    found = selectors.ai_setting_detail(company_id=company_id, setting_id=setting_id)
    if isinstance(found, selectors.SettingMissing):
        return NotFound()
    try:
        accept_criteria(found.criteria)
    except CriteriaRejected as refused:
        return services.SettingUnusable(refused.code, found.name)
    source = selectors.RunModelSource()
    config = source.config()
    model = prompt_model_e0.accept_model(config, found.model_settings, steps=source.steps())
    if isinstance(model, ModelSettingRefused):
        return services.SettingUnusable(model.code, found.name)
    prompts = None if found.prompts is None else prompt_model_e0.accept_prompts(found.prompts)
    if isinstance(prompts, PromptRefused):
        return services.SettingUnusable(prompts.code, found.name)
    return prompt_model_e0.prompt_model(
        config,
        setting_name=found.name,
        criteria=found.criteria,
        model=model,
        editable_model=prompt_model_e0.EDITABLE_MODEL,
        prompts=prompts,
    )


def default_prompt_model(*, actor_kind: Kind) -> AiPromptModel3 | Forbidden:
    """기본 판(코랩 원본 — 엔진 글 그대로)의 프롬프트 넷·모델 칸. DB 0."""
    if not is_allowed("greenwash_ai_setting_default_prompt_model", kind=actor_kind):
        return Forbidden("greenwash_ai_setting_default_prompt_model")
    source = selectors.RunModelSource()
    config = source.config()
    return prompt_model_e0.prompt_model(
        config,
        setting_name=DEFAULT_VERSION,
        criteria=None,
        model=defaults(config, source.steps()),
        editable_model=prompt_model_e0.EDITABLE_MODEL,
    )
