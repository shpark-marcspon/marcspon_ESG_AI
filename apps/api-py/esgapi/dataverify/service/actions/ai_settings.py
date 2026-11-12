"""회사별 AI 설정 판의 읽기·저장·적용(밴드 DVA1 ② — 운영 관리자의 경로 /ai-settings/dataverify). dataverify 의
selector·service 에 user(운영 관리자 이름 풀기)·core(감사)를 엮어 조립하므로 Action 이다(Service·Selector 는 남의
도메인을 import 하지 않는다 — `.importlinter` 계약 바). 영문번역 actions/ai_settings.py 의 판별 복사.

    setting_list(actor_kind, company_id, limit, offset)                      목록(dataverify.ai-settings@1)
    setting_detail(actor_kind, company_id, setting_id)                       판 하나(dataverify.ai-setting@1)
    save_setting(actor_kind, actor_user_id, company_id, title, memo, now, model_settings, prompts)
                                                                             새 판 + 감사 setting_change
    apply_setting(actor_kind, actor_user_id, company_id, setting_id, now)    적용 바꾸기 + 감사 setting_change
    default_setting(actor_kind)                                              기본 판(ai-setting-default@1 — DB 0)
    prompt_model(actor_kind, company_id, setting_id)                         판 하나의 프롬프트·모델(ai.prompt-model@3)
    default_prompt_model(actor_kind)                                         기본 판의 프롬프트·모델(DB 0)

★ 공개 일곱의 첫 문장이 자기 동작 칸의 권한 검사다(core/permissions.py — 운영 관리자만. 경로의 permitted 에 더해 —
  core/tests/test_permissions.py 의 ALSO_INSIDE). 막히면 아무것도 읽거나 쓰지 않는다.
★ 감사(MARC-ENT-295·244 — AD-05): 저장·적용마다 action setting_change, target_kind ai_setting, module dataverify,
  대상 회사의 줄. 감사는 업무 블록(services 의 atomic) **뒤**다 — 블록이 실패하면 줄 0, 감사가 거절돼도 응답은
  그대로다(record_event 는 던지지 않는다). 받기 거절·없는 판·못 받는 판의 적용·같은 판 다시 적용은 줄 0. 저장의
  changed_fields 는 memo·model_settings·prompts(판의 칸을 늘 함께 정한다). target_label 은 판 번호(v<n>) 그대로다.
  결과는 늘 success. 프롬프트·모델 읽기 둘은 감사 0(읽기).
★ 프롬프트·모델: 조립은 flows/prompt_model_156(순수 — core compose), 설정·명세는 selectors.RunModelSource(실행기와
  같은 원천). 저장 판의 모델 칸은 그 판에 저장한 값을 지금 설정으로 다시 받은 것, 기본 판은 명세의 기본값(defaults).
  지금 받기 규칙에 안 맞는 저장 판은 services.SettingUnusable(적용 막기와 같은 갈래 — 경로 409 AI_SETTING_UNUSABLE).
★ createdBy.name 은 user 의 names_of(운영 관리자 입구)로 지금 이름을 푼다. 못 풀면 null(계약).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from esgapi.core.auth.principal import Kind
from esgapi.core.calc.ai_settings import ModelSettingRefused, PromptRefused, defaults, version_status
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptModel3, AiPromptsIn
from esgapi.core.permissions import is_allowed
from esgapi.core.schemas import to_seoul_iso
from esgapi.core.service.services.audit import record_event
from esgapi.dataverify.contracts.ai_setting_shapes import (
    DEFAULT_NAME,
    DEFAULT_SHAPE,
    DEFAULT_TITLE,
    LIST_SHAPE,
    SETTING_SHAPE,
    DataverifyAiSetting,
    DataverifyAiSettingAppliedDefault,
    DataverifyAiSettingAppliedSaved,
    DataverifyAiSettingDefault,
    DataverifyAiSettingList,
    DataverifyAiSettingSummary,
)
from esgapi.dataverify.flows import prompt_model_156
from esgapi.dataverify.service.selectors import ai_settings as selectors
from esgapi.dataverify.service.services import ai_settings as services
from esgapi.user.service.selectors.user import names_of

LABEL_MAX = 255  # core_audit_events.target_label 의 길이
MODULE: Final = "dataverify"  # 감사 줄의 module


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


def _summary(setting: selectors.AiSettingHead, names: dict[int, str]) -> DataverifyAiSettingSummary:
    return {
        "id": setting.id,
        "name": setting.name,
        "title": setting.title,
        "status": version_status(setting.applied, setting.applied_at),
        "createdAt": to_seoul_iso(setting.created_at),
        "createdBy": {"id": setting.created_by_user_id, "name": names.get(setting.created_by_user_id)},
        "memo": setting.memo,
    }


def _one(setting: selectors.AiSetting, company_id: int) -> DataverifyAiSetting:
    return {"schemaVersion": SETTING_SHAPE, **_summary(setting, _names((setting,), company_id))}


def _list(company_id: int, limit: int, offset: int) -> DataverifyAiSettingList:
    page = selectors.ai_setting_page(company_id=company_id, limit=limit, offset=offset)
    names = _names(page.items, company_id)
    applied: DataverifyAiSettingAppliedDefault | DataverifyAiSettingAppliedSaved = (
        {"kind": "default"} if page.applied_id is None else {"kind": "saved", "id": page.applied_id}
    )
    return {
        "schemaVersion": LIST_SHAPE,
        "companyId": company_id,
        "applied": applied,
        "default": {"name": DEFAULT_NAME, "title": DEFAULT_TITLE},
        "items": [_summary(s, names) for s in page.items],
        "total": page.total,
    }


def setting_list(*, actor_kind: Kind, company_id: int, limit: int, offset: int) -> DataverifyAiSettingList | Forbidden:
    if not is_allowed("dataverify_ai_setting_list", kind=actor_kind):
        return Forbidden("dataverify_ai_setting_list")
    return _list(company_id, limit, offset)


def setting_detail(*, actor_kind: Kind, company_id: int, setting_id: int) -> DataverifyAiSetting | NotFound | Forbidden:
    if not is_allowed("dataverify_ai_setting_get", kind=actor_kind):
        return Forbidden("dataverify_ai_setting_get")
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
    model_settings: AiModelSettingsIn | None = None,
    prompts: AiPromptsIn | None = None,
) -> DataverifyAiSetting | services.ModelRefused | services.PromptsRefused | services.NameConflict | Forbidden:
    """받은 이름·모델 설정(빠지면 코드 값)·프롬프트 글(빠지면 코드 글)로 새 판. 받기 거절·번호 경합 소진이면 행 0·
    감사 0."""
    if not is_allowed("dataverify_ai_setting_create", kind=actor_kind):
        return Forbidden("dataverify_ai_setting_create")
    created = services.create_setting(
        company_id=company_id,
        created_by_user_id=actor_user_id,
        title=title,
        memo=memo,
        model_settings=model_settings,
        prompts=prompts,
    )
    if isinstance(created, services.ModelRefused | services.PromptsRefused | services.NameConflict):
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
        changed_fields=("memo", "model_settings", "prompts"),
        module=MODULE,
    )
    found = selectors.ai_setting_detail(company_id=company_id, setting_id=created.id)
    if isinstance(found, selectors.SettingMissing):  # 방금 쓴 행이 없다(지우는 길이 없다 — 일어나지 않는다)
        raise RuntimeError("방금 만든 dataverify_ai_settings 의 행이 없다")
    return _one(found, company_id)


def apply_setting(
    *, actor_kind: Kind, actor_user_id: int, company_id: int, setting_id: int | None, now: datetime
) -> DataverifyAiSettingList | services.SettingUnusable | services.ApplyConflict | NotFound | Forbidden:
    """그 회사의 적용 판을 setting_id 로(None = 기본 판). 응답은 바꾼 뒤의 목록 첫 쪽(새 것 먼저 20). 지금 받기에
    안 맞는 판이면 SettingUnusable, 겹친 적용에 걸리면 ApplyConflict 그대로(둘 다 쓰기·감사 0)."""
    if not is_allowed("dataverify_ai_setting_apply", kind=actor_kind):
        return Forbidden("dataverify_ai_setting_apply")
    changed = services.apply_setting(company_id=company_id, setting_id=setting_id, now=now)
    if isinstance(changed, selectors.SettingMissing):
        return NotFound()
    if isinstance(changed, (services.SettingUnusable, services.ApplyConflict)):
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
            target_label=(changed.after_name or DEFAULT_NAME)[:LABEL_MAX],
            changed_fields=("applied",),
            module=MODULE,
        )
    return _list(company_id, 20, 0)


def default_setting(*, actor_kind: Kind) -> DataverifyAiSettingDefault | Forbidden:
    """기본 판(엔진 코드 글·모델 칸 기본값 — 코드에 고정, DB 0)."""
    if not is_allowed("dataverify_ai_setting_default", kind=actor_kind):
        return Forbidden("dataverify_ai_setting_default")
    return {"schemaVersion": DEFAULT_SHAPE, "name": DEFAULT_NAME, "title": DEFAULT_TITLE}


def prompt_model(
    *, actor_kind: Kind, company_id: int, setting_id: int
) -> AiPromptModel3 | NotFound | services.SettingUnusable | Forbidden:
    """고른 회사의 판 하나의 묶음 셋·모델 칸 하나(그 판에 저장한 값). 없거나 남의 회사의 판이면 NotFound, 모델 설정·
    프롬프트 글이 지금 받기에 안 맞으면 SettingUnusable(판 번호째)."""
    if not is_allowed("dataverify_ai_setting_prompt_model", kind=actor_kind):
        return Forbidden("dataverify_ai_setting_prompt_model")
    found = selectors.ai_setting_detail(company_id=company_id, setting_id=setting_id)
    if isinstance(found, selectors.SettingMissing):
        return NotFound()
    source = selectors.RunModelSource()
    config = source.config()
    model = prompt_model_156.accept_model(config, found.model_settings, steps=source.steps())
    if isinstance(model, ModelSettingRefused):
        return services.SettingUnusable(model.code, found.name)
    prompts = None if found.prompts is None else prompt_model_156.accept_prompts(found.prompts)
    if isinstance(prompts, PromptRefused):
        return services.SettingUnusable(prompts.code, found.name)
    return prompt_model_156.prompt_model(config, setting_name=found.name, model=model, prompts=prompts)


def default_prompt_model(*, actor_kind: Kind) -> AiPromptModel3 | Forbidden:
    """기본 판(엔진 코드 글 그대로)의 묶음 셋·모델 칸 하나. DB 0."""
    if not is_allowed("dataverify_ai_setting_default_prompt_model", kind=actor_kind):
        return Forbidden("dataverify_ai_setting_default_prompt_model")
    source = selectors.RunModelSource()
    config = source.config()
    return prompt_model_156.prompt_model(config, setting_name=DEFAULT_NAME, model=defaults(config, source.steps()))
