"""쓰기. 회사별 AI 설정 판(표 translation_ai_settings — 밴드 TR4 ②). 읽기는 selectors/ai_settings.py, 감사·권한·이름
풀기는 부르는 쪽(actions/ai_settings.py)이다. 그린워싱 services/ai_settings.py 의 판별 복사(기준표·대상 단어·판정 sha
뺌 — 모듈끼리 import 하지 않는다).

    create_setting(company_id, created_by_user_id, title, memo, model_settings, prompts, models)
                                                                     받기 → 새 판 하나(번호 v<n>) — 블록 하나
    apply_setting(company_id, setting_id | None, now, models)        회사의 적용 판을 바꾼다(None = 기본 판) — 블록 하나
    import_setting(company_id, row, user_id)                         실행 묶음(RX1b)의 판 행 → 새 판(다음 v<n>,
                                                                     적용 안 함) — 받기를 다시 거치지 않는다(칸
                                                                     바이트 그대로)

★ 저장 = 새 행이다(고쳐 쓰기·지우기 없음 — 앱 역할에게 글·모델 칸 UPDATE·DELETE 권한이 없다, 마이그레이션 0001).
★ 한 번 저장 = 판 하나: 이름(title)·모델·프롬프트 글·메모가 한 본문이다. 받기 차례는 모델 → 프롬프트(쓰기 앞 —
  하나라도 거절이면 행 0). 모델 설정은 빠지면 코드 값(defaults(설정, MODELS)), 있으면 prompt_model_158.accept_model —
  거절이면 ModelRefused. 저장은 늘 그 정규형(to_input)이다(null 0). 프롬프트 글은 prompt_model_158.accept_prompts(core
  check_prompts) — 거절이면 PromptsRefused(code·문장·칸 경로). 저장 칸은 받은 정규형(글 바이트 그대로·메모 strip)
  또는 None(코드 글 — 코드 글과 같은 글을 보내도 접지 않는다). 받기의 원천은 models(기본 selectors.RunModelSource —
  실행기와 같은 원천).
★ 번호 경합: 같은 회사에 두 저장이 겹치면 둘이 같은 v<n> 을 셀 수 있다. INSERT 는 세이브포인트 안이고 unique
  (company_id, name) 위반만 다시 센다(NAME_RETRIES 번까지). 다른 제약 위반은 그대로 올라간다.
★ 적용 바꾸기: 그 회사의 판 행을 id 차례로 FOR UPDATE 로 잡고(selectors.lock_settings) 옛 판을 false 로 내린 뒤 새 판을
  true 로 올린다(부분 unique (company_id) WHERE applied 가 그 차례를 요구한다). 이미 그 판이면 쓰지 않는다(Unchanged).
  적용은 QuerySet.update(applied, applied_at) 하나다 — 앱 역할의 칸 단위 UPDATE 권한이 그 두 칸뿐이다.
  잠근 뒤에 생긴 적용 행(잠금이 못 본 행)과 겹쳐 그 부분 unique 에 걸리면 블록 전체를 되돌리고(옛 판을 내린 것도)
  ApplyConflict(경로 409 — 밴드 TRP1 S2). 다른 제약 위반은 그대로 올라간다.
★ 못 받는 판: 받기 규칙이 좁아져 지금 받기에 맞지 않게 된 저장 판은 적용하지 않는다(SettingUnusable — 쓰기 0). 잠근
  뒤 그 한 행의 모델 설정·프롬프트 글을 그 차례로 받기에 넣는다. 이미 적용된 그 판을 다시 보내도 같다(Unchanged 보다
  앞). 기본 판(None)으로 되돌리기는 늘 된다(막힌 회사의 출구).
생성자 <Row>(…) 는 쓰지 않는다(core/tests/isolation/test_static_rules.py 받침 ④).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from django.db import IntegrityError, transaction

from esgapi.core.calc.ai_settings import (
    ModelSettingRefused,
    PromptRefused,
    defaults,
    next_version_name,
    prompts_input,
    to_input,
)
from esgapi.core.contracts.ai_setting_shapes import AiModelSettingsIn, AiPromptsIn
from esgapi.translation.flows import prompt_model_158
from esgapi.translation.flows.prompt_model_158 import ModelSettingsSource
from esgapi.translation.models import TranslationAiSettingRow
from esgapi.translation.service.selectors import ai_settings as selectors

NAME_UNIQUE: Final = "translation_ai_settings_company_name_uniq"
APPLIED_UNIQUE: Final = "translation_ai_settings_one_applied_uniq"
NAME_RETRIES: Final = 5
RUN_MODELS: Final = selectors.RunModelSource()
"""모델 설정 받기의 기본 원천(실행기와 같은 RunModelSource — 시험 이음매는 그 클래스의 config·steps)."""


@dataclass(frozen=True, slots=True)
class Created:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class ModelRefused:
    """모델 설정 받기의 거절. code 는 ModelSettingRefused.code(소문자 ai_model_* — 나갈 때 대문자), message 는 화면에
    보일 한 문장."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class PromptsRefused:
    """프롬프트 글 받기의 거절. code 는 PromptRefused.code(소문자 ai_prompt_* — 나갈 때 대문자), message 는 화면에 보일
    한 문장, field 는 어긴 칸의 점 경로(prompts.steps.<i>.prompts.<j>.text|memo — 422 의 fields 와 같은 규칙)."""

    code: str
    message: str
    field: str


@dataclass(frozen=True, slots=True)
class NameConflict:
    """겹친 저장이 NAME_RETRIES 번 내리 같은 번호를 먼저 썼다(쓰지 않았다 — 다시 보내면 된다)."""


@dataclass(frozen=True, slots=True)
class ApplyConflict:
    """올린 판이 겹친 적용과 부분 unique(APPLIED_UNIQUE)에 걸렸다(블록 전체를 되돌렸다 — 쓰기 0, 다시 보내면 된다)."""


@dataclass(frozen=True, slots=True)
class Applied:
    before_id: int | None  # 바꾸기 전 적용 판(None = 기본 판)
    after_id: int | None
    after_name: str | None


@dataclass(frozen=True, slots=True)
class SettingUnusable:
    """그 판의 모델 설정·프롬프트 글이 지금 받기 규칙에 맞지 않는다(쓰지 않았다). code 는 ModelSettingRefused.code
    (ai_model_*)·PromptRefused.code(ai_prompt_*), name 은 판 번호."""

    code: str
    name: str


@dataclass(frozen=True, slots=True)
class Unchanged:
    """이미 그 판이 적용돼 있다(쓰지 않았다)."""


def _constraint(error: IntegrityError) -> str | None:
    """Django 의 IntegrityError 가 품은 psycopg 예외의 제약 이름."""
    diag = getattr(error.__cause__, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


@transaction.atomic
def create_setting(
    *,
    company_id: int,
    created_by_user_id: int,
    title: str,
    memo: str,
    model_settings: AiModelSettingsIn | None = None,
    prompts: AiPromptsIn | None = None,
    models: ModelSettingsSource = RUN_MODELS,
) -> Created | ModelRefused | PromptsRefused | NameConflict:
    """받은 이름·모델 설정(None 이면 코드 값)·프롬프트 글(None 이면 코드 글)로 새 판 하나. 받기 거절이면 쓰지 않는다
    (행 0 — 차례 모델 → 프롬프트). 번호 경합이 다시 시도를 다 쓰면 NameConflict. title 은 본문 꼴을 지난 값(strip 뒤
    1~40자)이다."""
    config = models.config()
    if model_settings is None:
        model = defaults(config, models.steps())
    else:
        found = prompt_model_158.accept_model(config, model_settings, steps=models.steps())
        if isinstance(found, ModelSettingRefused):
            return ModelRefused(found.code, found.message)
        model = found
    texts = None if prompts is None else prompt_model_158.accept_prompts(prompts)
    if isinstance(texts, PromptRefused):
        return PromptsRefused(texts.code, texts.message, texts.field)
    stored = to_input(model)
    stored_prompts = None if texts is None else prompts_input(texts)
    for _ in range(NAME_RETRIES):
        name = next_version_name(selectors.setting_names(company_id))
        try:
            with transaction.atomic():
                row = TranslationAiSettingRow.for_company(company_id).create(
                    company_id=company_id,
                    name=name,
                    title=title,
                    model_settings=stored,
                    prompts=stored_prompts,
                    memo=memo,
                    created_by_user_id=created_by_user_id,
                )
        except IntegrityError as error:
            if _constraint(error) != NAME_UNIQUE:
                raise
            continue  # 겹친 저장이 같은 번호를 먼저 썼다(머리말)
        return Created(row.id, row.name)
    return NameConflict()


@transaction.atomic
def import_setting(company_id: int, *, row: Mapping[str, object], user_id: int) -> tuple[int, str] | NameConflict:
    """실행 묶음(RX1b)이 실은 판 칸(name·title·memo·model_settings·prompts)을 받기를 거치지 않고 그대로 새 판 하나로
    (MARC-ENT-442 — 실행 versions 의 sha 와 맞아야 한다). 이름은 받는 회사의 다음 v<n>, 적용 판·기본 판은 건드리지
    않는다(applied=False). 번호 경합이 다시 시도를 다 쓰면 NameConflict(부르는 쪽이 거절)."""
    for _ in range(NAME_RETRIES):
        name = next_version_name(selectors.setting_names(company_id))
        try:
            with transaction.atomic():
                made = TranslationAiSettingRow.for_company(company_id).create(
                    company_id=company_id,
                    name=name,
                    title=row["title"],
                    model_settings=row["model_settings"],
                    prompts=row["prompts"],
                    memo=row["memo"],
                    created_by_user_id=user_id,
                )
        except IntegrityError as error:
            if _constraint(error) != NAME_UNIQUE:
                raise
            continue
        return (made.id, made.name)
    return NameConflict()


def unusable(found: selectors.AiSetting, models: ModelSettingsSource = RUN_MODELS) -> SettingUnusable | None:
    """그 판의 모델 설정 → 프롬프트 글을 지금 받기에 다시 넣는다. 거절이면 SettingUnusable, 지나면 None."""
    model = prompt_model_158.accept_model(models.config(), found.model_settings, steps=models.steps())
    if isinstance(model, ModelSettingRefused):
        return SettingUnusable(model.code, found.name)
    texts = None if found.prompts is None else prompt_model_158.accept_prompts(found.prompts)
    if isinstance(texts, PromptRefused):
        return SettingUnusable(texts.code, found.name)
    return None


@transaction.atomic
def apply_setting(
    *, company_id: int, setting_id: int | None, now: datetime, models: ModelSettingsSource = RUN_MODELS
) -> Applied | Unchanged | SettingUnusable | ApplyConflict | selectors.SettingMissing:
    """그 회사의 적용 판을 setting_id 로(None 이면 기본 판). 없거나 남의 회사의 id 면 SettingMissing, 지금 받기에
    안 맞는 판이면 SettingUnusable(둘 다 쓰지 않는다). 겹친 적용에 걸리면 ApplyConflict(블록 전체를 되돌린다)."""
    settings = selectors.lock_settings(company_id)
    if setting_id is not None and setting_id not in settings:
        return selectors.SettingMissing()
    if setting_id is not None:
        found = selectors.ai_setting_detail(company_id=company_id, setting_id=setting_id)
        if isinstance(found, selectors.SettingMissing):  # 잠근 행이다(지우는 길이 없다 — 일어나지 않는다)
            return found
        refused = unusable(found, models)
        if refused is not None:
            return refused
    before = next((s.id for s in settings.values() if s.applied), None)
    if before == setting_id:
        return Unchanged()
    if before is not None:
        TranslationAiSettingRow.for_company(company_id).filter(id=before).update(applied=False)
    if setting_id is None:
        return Applied(before_id=before, after_id=None, after_name=None)
    try:
        with transaction.atomic():
            TranslationAiSettingRow.for_company(company_id).filter(id=setting_id).update(applied=True, applied_at=now)
    except IntegrityError as error:
        if _constraint(error) != APPLIED_UNIQUE:
            raise
        transaction.set_rollback(True)  # 옛 판을 내린 것도 되돌린다(머리말)
        return ApplyConflict()
    return Applied(before_id=before, after_id=setting_id, after_name=settings[setting_id].name)
